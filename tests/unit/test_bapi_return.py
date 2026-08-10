"""Tests de la lecture BAPIRET2 (``sapfx_common.bapi_return``) : décision par
TYPE de message (convention n°3), formes table/structure/absente tolérées,
message d'échec listant les bloquants et rappelant le rollback."""
from sapfx_common.bapi_return import (
    failing_messages,
    format_bapi_failure,
    iter_bapi_messages,
)


def test_iter_normalise_table_et_structure():
    table = {"RETURN": [
        {"TYPE": "S", "ID": "OK", "NUMBER": "000", "MESSAGE": "créé"},
        {"TYPE": "E", "ID": "XX", "NUMBER": "001", "MESSAGE": "boom"},
    ]}
    assert [m["type"] for m in iter_bapi_messages(table)] == ["S", "E"]
    structure = {"RETURN": {"TYPE": "W", "MESSAGE": "attention"}}
    assert iter_bapi_messages(structure) == [
        {"type": "W", "id": "", "number": "", "message": "attention"}]


def test_iter_tolere_absence_et_lignes_vides():
    assert iter_bapi_messages({}) == []
    assert iter_bapi_messages({"RETURN": []}) == []
    # structure RETURN initiale non remplie (tout à blanc) : ignorée
    assert iter_bapi_messages(
        {"RETURN": {"TYPE": "", "ID": "", "NUMBER": "", "MESSAGE": ""}}) == []


def test_iter_respecte_return_key_alternatif():
    result = {"ET_RETURN": [{"TYPE": "A", "MESSAGE": "abort"}]}
    assert iter_bapi_messages(result, "ET_RETURN")[0]["type"] == "A"


def test_failing_filtre_e_a_x_seulement():
    messages = iter_bapi_messages({"RETURN": [
        {"TYPE": "S"}, {"TYPE": "W", "MESSAGE": "warn"}, {"TYPE": "I", "MESSAGE": "info"},
        {"TYPE": "E", "MESSAGE": "err"}, {"TYPE": "A", "MESSAGE": "abort"},
        {"TYPE": "X", "MESSAGE": "dump"},
    ]})
    assert [m["type"] for m in failing_messages(messages)] == ["E", "A", "X"]


def test_format_liste_les_messages_et_rappelle_le_rollback():
    failing = [{"type": "E", "id": "V1", "number": "045", "message": "bloqué"}]
    message = format_bapi_failure("BAPI_SALESORDER_CREATEFROMDAT2", failing)
    assert "BAPI_SALESORDER_CREATEFROMDAT2" in message
    assert "E V1/045 : bloqué" in message
    assert "Rollback Bapi Transaction" in message
