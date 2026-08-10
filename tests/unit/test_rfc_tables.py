"""Tests de ``sapfx_common.rfc_tables`` : paramètres RFC_READ_TABLE (limite
72 caractères des clauses OPTIONS), parsing des lignes DATA, littéraux ABAP,
et le verdict d'attente d'un job de fond (statuts TBTCO)."""
import pytest

from sapfx_common.rfc_tables import (
    abap_quote,
    job_wait_verdict,
    parse_read_table,
    read_table_params,
    summarize_job_statuses,
)


def test_read_table_params_structure():
    params = read_table_params("TBTCO", ["STATUS", "JOBCOUNT"],
                               ["JOBNAME EQ 'ZJOB'"], rowcount=5)
    assert params == {
        "QUERY_TABLE": "TBTCO",
        "DELIMITER": "|",
        "FIELDS": [{"FIELDNAME": "STATUS"}, {"FIELDNAME": "JOBCOUNT"}],
        "OPTIONS": [{"TEXT": "JOBNAME EQ 'ZJOB'"}],
        "ROWCOUNT": 5,
    }
    assert "ROWCOUNT" not in read_table_params("T000", ["MANDT"])


def test_read_table_params_refuse_les_clauses_trop_longues():
    with pytest.raises(ValueError, match="72"):
        read_table_params("TBTCO", ["STATUS"], ["JOBNAME EQ '%s'" % ("X" * 80)])


def test_abap_quote_double_les_quotes_internes():
    assert abap_quote("ZJOB") == "'ZJOB'"
    assert abap_quote("O'Neil") == "'O''Neil'"


def test_parse_read_table_decoupe_et_depouille():
    result = {
        "FIELDS": [{"FIELDNAME": "STATUS"}, {"FIELDNAME": "JOBCOUNT"}],
        "DATA": [{"WA": "F  |12345678"}, {"WA": "R"}],
    }
    assert parse_read_table(result) == [
        {"STATUS": "F", "JOBCOUNT": "12345678"},
        {"STATUS": "R", "JOBCOUNT": ""},   # colonne finale absente complétée
    ]
    assert parse_read_table({}) == []


def test_summarize_et_verdicts():
    rows = [{"STATUS": "F"}, {"STATUS": "F"}, {"STATUS": "R"}]
    counts = summarize_job_statuses(rows)
    assert counts == {"F": 2, "R": 1}
    assert job_wait_verdict(counts)["state"] == "waiting"
    assert job_wait_verdict({"F": 2})["state"] == "done"
    assert job_wait_verdict({})["state"] == "missing"
    aborted = job_wait_verdict({"A": 1, "F": 3})
    assert aborted["state"] == "aborted"
    assert "cancelled" in aborted["detail"]


def test_verdict_statut_inconnu_reste_prudent():
    # un statut hors domaine connu ne doit pas conclure « done » à tort
    assert job_wait_verdict({"Z": 1})["state"] == "waiting"
