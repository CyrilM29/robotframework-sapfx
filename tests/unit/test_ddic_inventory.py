"""Tests hors SAP de ``sapfx_common.ddic_inventory`` (logique pure).

Couvre les garanties que la spec exige de la campagne d'inventaire : périmètre
refusé sans borne, barème restreint au domaine relevé, absence DD02L signalée
(jamais une table vide), artefact déterministe, hash insensible à
l'horodatage, comparaison qui refuse les périmètres non équivalents.
"""
import pytest

from sapfx_common.ddic_inventory import (
    bounded_union,
    build_inventory,
    build_object_entry,
    classification_map,
    compare_inventories,
    comparison_hash,
    inventory_json,
    normalize_class,
    record_probe,
    render_comparison_report,
    sample_for_probe,
    validate_scope,
)

A4H_DOMAIN = ["TRANSP", "INTTAB", "VIEW", "APPEND"]


# ---------------------------------------------------------------- périmètre

def test_validate_scope_normalizes_and_deduplicates():
    scope = validate_scope([" SAPBC_DATAMODEL ", "SAPBC_DATAMODEL"],
                           ["SNWD", ""], "100", "7")
    assert scope == {"packages": ["SAPBC_DATAMODEL"], "prefixes": ["SNWD"],
                     "object_types": ["TABL", "VIEW"],
                     "max_objects": 100, "batch_size": 7}
    # Les types d'objets font partie du périmètre comparé : normalisés aussi.
    custom = validate_scope(["PKG"], [], 10, 5, object_types=["tabl"])
    assert custom["object_types"] == ["TABL"]


def test_validate_scope_refuses_empty_selection():
    with pytest.raises(ValueError, match="au moins un package ou un préfixe"):
        validate_scope([], ["  "], 10, 5)


@pytest.mark.parametrize("bad", [0, -3, "abc", None])
def test_validate_scope_refuses_unbounded_limits(bad):
    with pytest.raises(ValueError, match="max_objects"):
        validate_scope(["PKG"], [], bad, 5)


def test_bounded_union_sorts_dedupes_and_flags_truncation():
    names, truncated = bounded_union([["SPFLI", "SCARR"], ["SCARR", "SBOOK"]], 10)
    assert names == ["SBOOK", "SCARR", "SPFLI"] and truncated is False
    names, truncated = bounded_union([["A", "B", "C"]], 2)
    assert names == ["A", "B"] and truncated is True


# ------------------------------------------------------------ classification

def test_classification_map_restricted_to_observed_domain():
    assert classification_map(A4H_DOMAIN) == {
        "TRANSP": "table", "VIEW": "view", "INTTAB": "non_consultable_ddic"}
    # APPEND présent dans le domaine mais sans observation : hors barème.
    assert normalize_class("APPEND", classification_map(A4H_DOMAIN)) == "unknown"
    # Un domaine plus pauvre restreint d'autant.
    assert classification_map(["TRANSP"]) == {"TRANSP": "table"}


def test_classification_map_extra_is_validated():
    extended = classification_map(A4H_DOMAIN,
                                  extra={"APPEND": "non_consultable_ddic"})
    assert extended["APPEND"] == "non_consultable_ddic"
    with pytest.raises(ValueError, match="Classe normalisée inconnue"):
        classification_map(A4H_DOMAIN, extra={"APPEND": "banane"})


def test_build_object_entry_absent_from_dd02l_is_flagged_not_empty():
    entry = build_object_entry("ZDOESNOTEXIST", classification_map(A4H_DOMAIN))
    assert entry["ddic"]["present"] is False
    assert entry["class"] == "unknown"
    assert entry["class_reason"] == "absent_from_dd02l"
    assert entry["probe"]["status"] == "not_probed"


def test_build_object_entry_keeps_raw_values():
    row = {"TABNAME": "SFL_AUX", "TABCLASS": "INTTAB",
           "AS4LOCAL": "A", "AS4VERS": "0000"}
    entry = build_object_entry("SFL_AUX", classification_map(A4H_DOMAIN),
                               package="SAPBC_DATAMODEL", tadir_type="TABL",
                               dd02l_row=row)
    assert entry["class"] == "non_consultable_ddic"
    assert entry["ddic"] == {"present": True, "tabclass": "INTTAB",
                             "as4local": "A", "as4vers": "0000"}


# ------------------------------------------------------------------- sondes

def test_record_probe_validates_status_and_marks_count():
    entry = build_object_entry("SCARR", classification_map(A4H_DOMAIN),
                               dd02l_row={"TABCLASS": "TRANSP"})
    record_probe(entry, "selection_screen_reached", entry_count=18)
    assert entry["probe"]["status"] == "selection_screen_reached"
    assert entry["entry_count"] == 18
    assert entry["entry_count_reason"] == "measured"
    with pytest.raises(ValueError, match="Statut de sonde inconnu"):
        record_probe(entry, "explosion")


def test_sample_for_probe_is_deterministic_and_bounded():
    cmap = classification_map(A4H_DOMAIN)
    entries = [build_object_entry(n, cmap, dd02l_row={"TABCLASS": c})
               for n, c in [("SPFLI", "TRANSP"), ("SCARR", "TRANSP"),
                            ("SBOOK", "TRANSP"), ("SFL_AUX", "INTTAB"),
                            ("SCUS_BOOK", "VIEW")]]
    assert sample_for_probe(entries, per_class=2) == [
        "SBOOK", "SCARR", "SCUS_BOOK", "SFL_AUX"]


# ----------------------------------------------------------------- artefact

def _small_inventory(observed="2026-08-17T12:00:00+00:00", **overrides):
    cmap = classification_map(A4H_DOMAIN)
    entries = [
        build_object_entry("SCARR", cmap, dd02l_row={"TABCLASS": "TRANSP"}),
        build_object_entry("SFL_AUX", cmap, dd02l_row={"TABCLASS": "INTTAB"}),
    ]
    scope = {"packages": ["SAPBC_DATAMODEL"], "prefixes": [],
             "object_types": ["TABL"], "max_objects": 10, "batch_size": 7}
    scope.update(overrides)
    return build_inventory("a4h", scope, entries, observed)


def test_build_inventory_sorts_and_recomputes_summary():
    inventory = _small_inventory()
    assert [e["object_name"] for e in inventory["objects"]] == ["SCARR",
                                                                "SFL_AUX"]
    assert inventory["summary"]["discovered"] == 2
    assert inventory["summary"]["table"] == 1
    assert inventory["summary"]["non_consultable_ddic"] == 1
    assert inventory["summary"]["probed"] == 0
    # La somme des classes couvre tous les objets (critère du scénario 8).
    total = sum(inventory["summary"][c] for c
                in ("table", "view", "non_consultable_ddic", "unknown"))
    assert total == inventory["summary"]["discovered"]


def test_inventory_json_is_deterministic():
    assert inventory_json(_small_inventory()) == inventory_json(
        _small_inventory())
    assert inventory_json(_small_inventory()).endswith("\n")


def test_comparison_hash_ignores_timestamp_only():
    base = comparison_hash(_small_inventory(observed="2026-08-17T12:00:00+00:00"))
    later = comparison_hash(_small_inventory(observed="2026-08-18T09:30:00+00:00"))
    assert base == later
    different = comparison_hash(_small_inventory(max_objects=99))
    assert base != different


# -------------------------------------------------------------- comparaison

def test_compare_inventories_reports_sets_and_reclassification():
    cmap = classification_map(A4H_DOMAIN)
    inv_a = build_inventory(
        "ecc", {"packages": ["P"], "prefixes": [], "object_types": ["TABL"],
                "max_objects": 10, "batch_size": 7},
        [build_object_entry("SCARR", cmap, dd02l_row={"TABCLASS": "TRANSP"}),
         build_object_entry("OLDONLY", cmap, dd02l_row={"TABCLASS": "TRANSP"})],
        "2026-01-01T00:00:00+00:00")
    inv_b = build_inventory(
        "s4h", {"packages": ["P"], "prefixes": [], "object_types": ["TABL"],
                "max_objects": 10, "batch_size": 7},
        [build_object_entry("SCARR", cmap, dd02l_row={"TABCLASS": "VIEW"})],
        "2026-02-02T00:00:00+00:00")
    result = compare_inventories(inv_a, inv_b)
    assert result["compatible"] is True
    assert result["only_in_a"] == ["OLDONLY"] and result["only_in_b"] == []
    assert result["reclassified"] == [
        {"object_name": "SCARR", "a": "table", "b": "view"}]
    report = render_comparison_report(result)
    assert "SCARR" in report and "table -> view" in report


def test_compare_inventories_flags_incompatible_selection():
    inv_a = _small_inventory()
    inv_b = _small_inventory()
    inv_b["selection"]["packages"] = ["OTHER_PKG"]
    result = compare_inventories(inv_a, inv_b)
    assert result["compatible"] is False
    assert any("packages" in r for r in result["incompatibility_reasons"])
    assert "non équivalents" in render_comparison_report(result)


def test_compare_inventories_refuses_schema_mismatch():
    inv_a, inv_b = _small_inventory(), _small_inventory()
    inv_b["schema_version"] = 2
    with pytest.raises(ValueError, match="schema_version"):
        compare_inventories(inv_a, inv_b)
