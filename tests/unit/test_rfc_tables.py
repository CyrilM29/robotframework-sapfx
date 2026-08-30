"""Tests de ``sapfx_common.rfc_tables`` : paramètres RFC_READ_TABLE (limite
72 caractères des clauses OPTIONS), parsing des lignes DATA, littéraux ABAP,
et le verdict d'attente d'un job de fond (statuts TBTCO)."""
import pytest

from sapfx_common.rfc_tables import (
    abap_quote,
    group_job_statuses,
    job_wait_cases,
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


# --- le journal relu comme un catalogue de cas d'attente -------------------

#: Un journal de jobs miniature, calqué sur ce qu'une cible réelle porte :
#: des jobs terminés, un annulé qui porte AUSSI des runs terminés, un encore
#: dans le pipeline, et un dont aucun statut n'est cartographié.
JOURNAL = [
    {"JOBNAME": "RSUPG_RUN_TASK_ONCE", "STATUS": "F"},
    {"JOBNAME": "RSUPG_RUN_TASK_ONCE", "STATUS": "F"},
    {"JOBNAME": "EU_PUT", "STATUS": "F"},
    {"JOBNAME": "EU_PUT", "STATUS": "A"},
    {"JOBNAME": "EU_PUT", "STATUS": "Z"},
    {"JOBNAME": "RDDIMPDP", "STATUS": "F"},
    {"JOBNAME": "RDDIMPDP", "STATUS": "S"},
    {"JOBNAME": "SAP_COLLECTOR", "STATUS": "Z"},
    {"JOBNAME": "ZZ_ANNULE_SEC", "STATUS": "A"},
    {"JOBNAME": "", "STATUS": "F"},          # ligne sans job : ignorée
    {"JOBNAME": "RDDIMPDP", "STATUS": ""},   # ligne sans statut : ignorée
]


def test_group_job_statuses_compte_par_job():
    grouped = group_job_statuses(JOURNAL)
    assert grouped["EU_PUT"] == {"F": 1, "A": 1, "Z": 1}
    assert grouped["RDDIMPDP"] == {"F": 1, "S": 1}
    assert "" not in grouped               # la ligne sans nom n'invente pas un job
    assert group_job_statuses([]) == {}


def test_job_wait_cases_classe_chaque_issue():
    cases = job_wait_cases(group_job_statuses(JOURNAL))
    assert cases["done"] == ["RSUPG_RUN_TASK_ONCE"]
    assert cases["aborted"] == ["EU_PUT", "ZZ_ANNULE_SEC"]   # trié
    assert cases["pipeline"] == ["RDDIMPDP"]
    assert cases["unmapped"] == ["SAP_COLLECTOR"]


def test_seul_un_job_annule_ET_termine_prouve_la_priorite():
    # La branche « annulé » ne vaut que jouée sur un job qui porte AUSSI des
    # runs terminés : sinon elle ne prouve pas que le A prime sur les F, elle
    # constate seulement qu'un A tout seul échoue.
    cases = job_wait_cases(group_job_statuses(JOURNAL))
    assert cases["aborted_with_finished"] == ["EU_PUT"]
    assert "ZZ_ANNULE_SEC" in cases["aborted"]


def test_un_statut_non_cartographie_n_est_pas_du_pipeline():
    # Le verdict range les deux dans « waiting » : le catalogue les sépare,
    # parce que ce ne sont pas les mêmes preuves (attendre pour une raison
    # connue, ou continuer d'attendre devant l'inconnu).
    cases = job_wait_cases({"A": {"S": 1}, "B": {"Z": 1}, "C": {"Z": 1, "R": 1}})
    assert cases["pipeline"] == ["A", "C"]
    assert cases["unmapped"] == ["B"]


def test_job_wait_cases_rend_toutes_ses_cles_sur_un_journal_vide():
    # Une branche sans cible doit pouvoir se SAUTER en le disant : elle a
    # besoin d'une liste vide, pas d'une clé absente.
    cases = job_wait_cases({})
    assert cases == {"done": [], "aborted": [], "aborted_with_finished": [],
                     "pipeline": [], "unmapped": []}
