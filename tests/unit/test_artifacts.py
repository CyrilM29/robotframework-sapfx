"""Tests hors SAP de ``sapfx_common.artifacts`` : l'artefact JSON déterministe
générique (empreinte sur un périmètre DÉCLARÉ, horodatage exclu, relecture qui
recalcule l'empreinte, comparaison qui refuse deux périmètres différents)."""
import json

import pytest

from sapfx_common.artifacts import (
    artifact_hash,
    build_deterministic_artifact,
    compare_deterministic_artifacts,
    deterministic_json,
    read_deterministic_artifact,
    write_deterministic_artifact,
)

REGISTER = {"capabilities": {"tree.read_nodes": {"verdict": "covered", "preuve": "25 nœuds"},
                             "combobox.select_by_key": {"verdict": "covered", "preuve": "' '"}},
            "target": {"system_id": "A4H", "client": "001"}}


def test_l_empreinte_ne_depend_ni_de_l_ordre_ni_de_l_horodatage():
    shuffled = {"target": dict(REGISTER["target"]),
                "capabilities": dict(reversed(list(REGISTER["capabilities"].items())))}
    assert artifact_hash(REGISTER) == artifact_hash(shuffled)
    a = build_deterministic_artifact(REGISTER, timestamp="2026-09-07T20:00:00+00:00")
    b = build_deterministic_artifact(REGISTER, timestamp="2026-09-08T09:00:00+00:00")
    assert a["sha256"] == b["sha256"] == artifact_hash(REGISTER)
    assert a["generated_at"] != b["generated_at"]
    assert a["hash_scope"] == {"hashed_keys": [],
                               "excluded_keys": ["generated_at", "hash_scope", "sha256"]}


def test_le_perimetre_hache_restreint_l_empreinte_aux_cles_nommees():
    only_caps = artifact_hash(REGISTER, hashed_keys="capabilities")
    other_target = dict(REGISTER, target={"system_id": "A4H", "client": "000"})
    assert artifact_hash(other_target, hashed_keys="capabilities") == only_caps
    assert artifact_hash(other_target) != artifact_hash(REGISTER)
    assert artifact_hash(REGISTER, hashed_keys=["capabilities", "target"]) != only_caps
    with pytest.raises(ValueError, match="absente"):
        artifact_hash(REGISTER, hashed_keys="nope")
    with pytest.raises(ValueError, match="dictionnaire"):
        artifact_hash(["pas", "un", "dict"])


def test_ecriture_relecture_et_verification_de_l_empreinte(tmp_path):
    path = write_deterministic_artifact(tmp_path / "reg.json", REGISTER,
                                        hashed_keys="capabilities", timestamp=False)
    raw = (tmp_path / "reg.json").read_bytes()
    assert b"\r\n" not in raw and raw.endswith(b"\n")
    assert raw.decode("utf-8") == deterministic_json(json.loads(raw))   # forme canonique
    artifact = read_deterministic_artifact(path)
    assert "generated_at" not in artifact
    assert artifact["capabilities"] == REGISTER["capabilities"]
    assert artifact["hash_scope"]["hashed_keys"] == ["capabilities"]
    # Un artefact édité après coup est REFUSÉ, jamais comparé.
    data = json.loads(raw)
    data["capabilities"]["tree.read_nodes"]["verdict"] = "gap"
    (tmp_path / "edited.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="invalide"):
        read_deterministic_artifact(tmp_path / "edited.json")
    (tmp_path / "foreign.json").write_text(json.dumps(REGISTER), encoding="utf-8")
    with pytest.raises(ValueError, match="Write Deterministic Artifact"):
        read_deterministic_artifact(tmp_path / "foreign.json")


def test_la_comparaison_nomme_les_chemins_et_refuse_deux_perimetres(tmp_path):
    a = write_deterministic_artifact(tmp_path / "a.json", REGISTER, hashed_keys="capabilities")
    changed = json.loads(json.dumps(REGISTER))
    changed["capabilities"]["tree.read_nodes"]["verdict"] = "gap"
    changed["capabilities"]["menu.select_by_path"] = {"verdict": "covered", "preuve": ""}
    b = write_deterministic_artifact(tmp_path / "b.json", changed, hashed_keys="capabilities")
    result = compare_deterministic_artifacts(a, b)
    assert result["identical"] is False
    assert [d["path"] for d in result["differences"]] == [
        "capabilities.menu.select_by_path", "capabilities.tree.read_nodes.verdict"]
    assert result["differences"][1] == {"path": "capabilities.tree.read_nodes.verdict",
                                        "a": '"covered"', "b": '"gap"'}
    same = compare_deterministic_artifacts(a, read_deterministic_artifact(a))
    assert same["identical"] is True and same["differences"] == []
    c = write_deterministic_artifact(tmp_path / "c.json", REGISTER)   # tout haché
    with pytest.raises(ValueError, match="non probante"):
        compare_deterministic_artifacts(a, c)


def test_les_listes_de_cles_arrivent_aussi_en_chaine_a_virgules():
    artifact = build_deterministic_artifact(REGISTER, hashed_keys="capabilities, target",
                                            excluded_keys="notes", timestamp="x")
    assert artifact["hash_scope"]["hashed_keys"] == ["capabilities", "target"]
    assert "notes" in artifact["hash_scope"]["excluded_keys"]
    assert artifact["generated_at"] == "x"
