"""Mixin DdicKeywords : classification DD02L par lots, sonde canari, artefact d'inventaire. Doublures dans _ddic_keywords_fixtures."""
import json
import pytest

from _ddic_keywords_fixtures import (  # noqa: F401
    CMAP,
    _Recorder,
    _entry,
)



def test_classify_single_name_skips_the_dialog():
    lib = _Recorder(rows=[{"TABNAME": "SCARR", "TABCLASS": "TRANSP",
                           "AS4LOCAL": "A", "AS4VERS": "0000"}])
    entries = lib.classify_ddic_objects(["scarr"], CMAP)
    assert entries["SCARR"]["class"] == "table"
    assert not any(c[0] == "click" and "VALU_PUSH" in c[1] for c in lib.calls)


def test_classify_reads_only_the_technical_columns_it_consumes():
    lib = _Recorder(rows=[{"TABNAME": "SCARR", "TABCLASS": "TRANSP"}])
    lib.classify_ddic_objects(["SCARR"], CMAP)
    reads = [c for c in lib.calls if c[0] == "read_grid"]
    assert reads and reads[0][3] == ("TABNAME", "TABCLASS", "AS4LOCAL", "AS4VERS")


def test_classify_batches_and_flags_missing_objects():
    rows = [{"TABNAME": "SCARR", "TABCLASS": "TRANSP"},
            {"TABNAME": "SFL_AUX", "TABCLASS": "INTTAB"},
            {"TABNAME": "SCUS_BOOK", "TABCLASS": "VIEW"}]
    lib = _Recorder(rows=rows)
    names = ["SCARR", "SFL_AUX", "SCUS_BOOK", "ZGHOST"]
    entries = lib.classify_ddic_objects(names, CMAP, batch_size=2)
    assert entries["SCARR"]["class"] == "table"
    assert entries["SFL_AUX"]["class"] == "non_consultable_ddic"
    assert entries["SCUS_BOOK"]["class"] == "view"
    ghost = entries["ZGHOST"]
    assert ghost["ddic"]["present"] is False
    assert ghost["class"] == "unknown"
    assert ghost["class_reason"] == "absent_from_dd02l"
    # 4 noms, lots de 2 : deux passages SE16 complets.
    assert [c for c in lib.calls if c[0] == "run_transaction"] == [
        ("run_transaction", "SE16")] * 2


def test_classify_honours_a_batch_size_larger_than_the_legacy_cap():
    rows = [{"TABNAME": f"T{i}", "TABCLASS": "TRANSP"} for i in range(9)]
    lib = _Recorder(rows=rows, visible=12)
    lib.classify_ddic_objects([f"T{i}" for i in range(9)], CMAP, batch_size=9)
    # Un seul passage SE16 : le plafond figé à 7 ne s'impose plus au dialogue.
    assert [c for c in lib.calls if c[0] == "run_transaction"] == [
        ("run_transaction", "SE16")]


def test_classify_refuses_a_non_positive_batch_size():
    lib = _Recorder()
    with pytest.raises(AssertionError, match="strictly positive"):
        lib.classify_ddic_objects(["SCARR"], CMAP, batch_size=0)
    with pytest.raises(AssertionError, match="strictly positive"):
        lib.classify_ddic_objects(["SCARR"], CMAP, batch_size=-3)


def test_classify_refuses_a_lone_string():
    with pytest.raises(AssertionError, match="must be a LIST"):
        _Recorder().classify_ddic_objects("SCARR", CMAP)


def test_classify_active_only_filters_on_as4local():
    lib = _Recorder(rows=[{"TABNAME": "SCARR", "TABCLASS": "TRANSP"}])
    lib.classify_ddic_objects(["SCARR"], CMAP, active_only=True)
    assert ("input", "wnd[0]/usr/ctxtI2-LOW", "A") in lib.calls
    lib2 = _Recorder(rows=[{"TABNAME": "SCARR", "TABCLASS": "TRANSP"}])
    lib2.classify_ddic_objects(["SCARR"], CMAP, active_only="False")
    assert not any(c[1].endswith("I2-LOW") for c in lib2.calls
                   if c[0] == "input")


def test_classify_treats_an_empty_selection_screen_as_no_matching_row():
    """Écran de sélection conservé = aucune ligne (cas légitime), à condition
    que la sonde canari confirme les critères positionnels."""
    lib = _Recorder(rows=[{"TABNAME": "DD02L", "TABCLASS": "TRANSP"}])
    entries = lib.classify_ddic_objects(["ZGHOST"], CMAP)
    assert entries["ZGHOST"]["class"] == "unknown"
    assert entries["ZGHOST"]["class_reason"] == "absent_from_dd02l"


def test_classify_fails_when_the_data_browser_is_not_in_alv_mode():
    """Ni grille ni écran de sélection : sortie liste classique. L'ancien code
    rapportait « absent de DD02L » pour TOUT le lot, campagne verte et fausse."""
    lib = _Recorder(rows=[{"TABNAME": "SCARR", "TABCLASS": "TRANSP"}],
                    alv_mode=False)
    with pytest.raises(AssertionError, match="Use ALV Grid In Data Browser"):
        lib.classify_ddic_objects(["SCARR"], CMAP)


def test_classify_fails_when_the_row_cap_is_reached():
    """Plafond ATTEINT = troncature possible : les noms suivants seraient
    marqués absents à tort. L'échec le dit au lieu de mentir."""
    rows = [{"TABNAME": "SCARR", "TABCLASS": "TRANSP"} for _ in range(20)]
    lib = _Recorder(rows=rows)
    with pytest.raises(AssertionError, match="row cap"):
        lib.classify_ddic_objects(["SCARR"], CMAP)


def test_classify_canary_probe_detects_shifted_positional_criteria():
    """Lot vide + canari vide = les critères I1/I2 ne sont plus TABNAME/AS4LOCAL
    (choix des champs persistant par utilisateur)."""
    lib = _Recorder(rows=[], screen="selection")
    with pytest.raises(AssertionError, match="canary probe"):
        lib.classify_ddic_objects(["ZGHOST"], CMAP)


def test_classify_canary_probe_runs_once_per_instance():
    lib = _Recorder(rows=[{"TABNAME": "DD02L", "TABCLASS": "TRANSP"}],
                    screen="selection")
    lib.classify_ddic_objects(["ZGHOST", "ZOTHER"], CMAP, batch_size=1)
    canary = [c for c in lib.calls
              if c[0] == "input" and c[1].endswith("I1-LOW") and c[2] == "DD02L"]
    assert len(canary) == 1


def test_sample_keyword_accepts_the_entries_dict():
    lib = _Recorder()
    entries = {
        "SCARR": {"object_name": "SCARR", "class": "table"},
        "SFLIGHT": {"object_name": "SFLIGHT", "class": "table"},
        "SBOOK": {"object_name": "SBOOK", "class": "table"},
        "SFL_AUX": {"object_name": "SFL_AUX", "class": "non_consultable_ddic"},
    }
    assert lib.sample_ddic_objects_for_probe(entries, per_class=2) == [
        "SBOOK", "SCARR", "SFL_AUX"]
    assert lib.sample_ddic_objects_for_probe(entries, per_class=1,
                                             classes="table") == ["SBOOK"]


def test_merge_name_lists_keyword_returns_names_and_truncation():
    lib = _Recorder()
    names, truncated = lib.merge_ddic_name_lists([["B", "A"], ["A", "C"]], 2)
    assert names == ["A", "B"]
    assert truncated is True


def test_classification_map_keyword_translates_an_invalid_extra():
    lib = _Recorder()
    assert lib.get_ddic_classification_map(["TRANSP"]) == {"TRANSP": "table"}
    with pytest.raises(AssertionError, match="Classe normalisée inconnue"):
        lib.get_ddic_classification_map(["TRANSP"], {"APPEND": "table_bidon"})


def test_write_artifact_round_trips_and_hash_ignores_timestamp(tmp_path):
    lib = _Recorder()
    scope = {"packages": ["SAPBC_DATAMODEL"], "prefixes": [],
             "object_types": ["TABL"], "max_objects": 10, "batch_size": 7}
    entries = {"SCARR": _entry()}
    path = tmp_path / "inventory.json"
    proof = lib.write_ddic_inventory_artifact(str(path), "a4h", scope, entries)
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["summary"]["table"] == 1
    assert on_disk["target_id"] == "a4h"
    proof2 = lib.write_ddic_inventory_artifact(str(path), "a4h", scope, entries)
    assert proof["sha256"] == proof2["sha256"]  # l'horodatage ne compte pas
    assert proof["summary"]["discovered"] == 1


def test_compare_artifacts_keyword_reads_two_files(tmp_path):
    lib = _Recorder()
    scope = {"packages": ["P"], "prefixes": [], "object_types": ["TABL"],
             "max_objects": 10, "batch_size": 7}
    path_a, path_b = tmp_path / "a.json", tmp_path / "b.json"
    lib.write_ddic_inventory_artifact(str(path_a), "a4h", scope,
                                      {"SCARR": _entry()})
    lib.write_ddic_inventory_artifact(
        str(path_b), "s4h", scope,
        {"SCARR": _entry(klass="view"), "ZNEW": _entry("ZNEW")})
    comparison = lib.compare_ddic_inventory_artifacts(str(path_a), str(path_b))
    assert comparison["compatible"] is True
    assert comparison["only_in_b"] == ["ZNEW"]
    assert comparison["reclassified"] == [
        {"object_name": "SCARR", "a": "table", "b": "view"}]


def test_validate_and_probe_keywords_translate_errors():
    lib = _Recorder()
    with pytest.raises(AssertionError, match="package ou un préfixe"):
        lib.validate_ddic_scope([], [], 10, 7)
    entry = {"probe": {}, "entry_count": None, "entry_count_reason": ""}
    with pytest.raises(AssertionError, match="Statut de sonde inconnu"):
        lib.record_ddic_probe(entry, "explosion")
    lib.record_ddic_probe(entry, "rejected", message_type="E")
    assert entry["probe"]["message_type"] == "E"


def test_validate_scope_keyword_accepts_a_scalar_override():
    """-v CAMPAIGN_PACKAGES:X passe un SCALAIRE : le nom ne doit pas être
    éclaté en lettres."""
    lib = _Recorder()
    scope = lib.validate_ddic_scope("SAPBC_DATAMODEL", "", 10, 7)
    assert scope["packages"] == ["SAPBC_DATAMODEL"]
