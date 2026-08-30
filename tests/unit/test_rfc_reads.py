"""Tests hors SAP de la famille de lectures de preuves du canal RFC
(`Read Change Documents`, `Get Idoc Status`, `Read Application Log`,
`Get Job Log`) et de sa logique pure ``sapfx_common.rfc_reads``.

Les deux pièges payés live le 2026-08-29 y ont leur contre-épreuve : le
tampon de 512 octets de RFC_READ_TABLE (JAMAIS les deux valeurs CDPOS dans
une même projection) et ``BP_JOBLOG_READ`` non appelable à distance (la
chaîne XBP, avec un logoff qui s'exécute MÊME sur échec).
"""
import pytest

from sapfx_common import rfc_reads
from SapApiLibrary import SapApiLibrary


# --- logique pure ------------------------------------------------------------

def test_normalize_date_accepte_les_deux_formes_et_nomme_l_argument():
    assert rfc_reads.normalize_date("20260829", "date_from") == "20260829"
    assert rfc_reads.normalize_date("2026-08-29", "date_from") == "20260829"
    with pytest.raises(ValueError, match="date_from"):
        rfc_reads.normalize_date("hier", "date_from")


def test_build_options_ignore_none_prefixe_and_et_cite_abap():
    clauses = rfc_reads.build_options([
        ("OBJECTCLAS", "IDENTITY"), ("OBJECTID", None),
        ("USERNAME", "O'Neil")])
    assert clauses == ["OBJECTCLAS EQ 'IDENTITY'",
                       "AND USERNAME EQ 'O''Neil'"]
    assert rfc_reads.append_clause([], "UDATE GE '20260101'") == [
        "UDATE GE '20260101'"]


def test_merge_change_items_recolle_les_deux_projections():
    new = [{"CHANGENR": "1", "TABNAME": "T", "TABKEY": "K", "FNAME": "F",
            "CHNGIND": "U", "VALUE_NEW": "après"}]
    old = [{"CHANGENR": "1", "TABNAME": "T", "TABKEY": "K", "FNAME": "F",
            "CHNGIND": "U", "VALUE_OLD": "avant"},
           {"CHANGENR": "2", "TABNAME": "T", "TABKEY": "K", "FNAME": "G",
            "CHNGIND": "D", "VALUE_OLD": "seul"}]
    merged = rfc_reads.merge_change_items(new, old)
    assert merged[0]["VALUE_NEW"] == "après" and merged[0]["VALUE_OLD"] == "avant"
    # une ligne vue d'un seul côté ne disparaît pas
    orphan = [item for item in merged if item["CHANGENR"] == "2"]
    assert orphan and orphan[0]["VALUE_OLD"] == "seul" and orphan[0]["VALUE_NEW"] == ""


def test_attach_change_items_groupe_par_changenr():
    headers = [{"CHANGENR": "1"}, {"CHANGENR": "2"}]
    items = [{"CHANGENR": "1", "FNAME": "A"}, {"CHANGENR": "1", "FNAME": "B"},
             {"CHANGENR": "9", "FNAME": "hors en-têtes"}]
    documents = rfc_reads.attach_change_items(headers, items)
    assert [len(d["items"]) for d in documents] == [2, 0]


def test_classify_idoc_status_et_le_repli_unmapped():
    assert rfc_reads.classify_idoc_status("53") == "success"
    assert rfc_reads.classify_idoc_status("51") == "error"
    assert rfc_reads.classify_idoc_status("64") == "in_progress"
    assert rfc_reads.classify_idoc_status("3") == "success"    # zfill
    # un statut hors barème n'est JAMAIS un succès
    assert rfc_reads.classify_idoc_status("99") == "unmapped"
    assert rfc_reads.classify_idoc_status("") == "unmapped"


def test_summarize_idoc_statuses_toutes_categories_presentes():
    counts = rfc_reads.summarize_idoc_statuses([{"STATUS": "53"},
                                                {"STATUS": "51"}])
    assert counts == {"success": 1, "error": 1, "in_progress": 0,
                      "unmapped": 0}


def test_normalize_log_header_convertit_les_numc_en_entiers():
    header = rfc_reads.normalize_log_header(
        {"OBJECT": "/IWFND/", "MSG_CNT_AL": "000004", "MSG_CNT_E": "000004",
         "MSG_CNT_A": "000000"})
    assert header == {"OBJECT": "/IWFND/", "total": 4, "error": 4, "abort": 0}
    totals = rfc_reads.summarize_log_headers([header, {"error": 1, "total": 2}])
    assert totals["error"] == 5 and totals["total"] == 6


def test_normalize_job_log_lines_json_safe():
    lines = rfc_reads.normalize_job_log_lines(
        [{"MSGID": "00", "MSGNO": 516, "TEXT": "Job   started  "}])
    assert lines == [{"MSGID": "00", "MSGNO": "516", "TEXT": "Job   started"}]


# --- keywords sur doublures --------------------------------------------------

def _reading_lib(responses):
    """Une SapApiLibrary dont `read_rfc_table` sert des réponses par table et
    enregistre chaque lecture (table, champs, options, plafond)."""
    lib = SapApiLibrary()
    lib.reads = []

    def read_rfc_table(table, fields, alias="default", options=None,
                       rowcount=0, delimiter="|"):
        lib.reads.append({"table": table, "fields": list(fields),
                          "options": list(options or []),
                          "rowcount": rowcount})
        queue = responses.get(table)
        return queue.pop(0) if queue else []

    lib.read_rfc_table = read_rfc_table
    return lib


_CD_HEADER = {"OBJECTCLAS": "IDENTITY", "OBJECTID": "DEVELOPER",
              "CHANGENR": "0000000022", "USERNAME": "DDIC",
              "UDATE": "20170406", "UTIME": "081500", "TCODE": "SU01",
              "CHANGE_IND": "U"}


def test_read_change_documents_deux_projections_jamais_les_deux_valeurs():
    """La contre-épreuve du tampon de 512 octets : les postes CDPOS sont lus
    en DEUX projections, et aucune lecture ne demande VALUE_NEW et VALUE_OLD
    ensemble (la forme qui sort en DATA_BUFFER_EXCEEDED, AD/E/559)."""
    lib = _reading_lib({
        "CDHDR": [[dict(_CD_HEADER)]],
        "CDPOS": [
            [{"CHANGENR": "0000000022", "TABNAME": "SUSR", "TABKEY": "K",
              "FNAME": "KEY", "CHNGIND": "I", "VALUE_NEW": "X"}],
            [{"CHANGENR": "0000000022", "TABNAME": "SUSR", "TABKEY": "K",
              "FNAME": "KEY", "CHNGIND": "I", "VALUE_OLD": ""}],
        ]})
    documents = lib.read_change_documents("IDENTITY", object_id="DEVELOPER",
                                          date_from="2017-01-01")
    assert len(documents) == 1
    assert documents[0]["items"][0]["VALUE_NEW"] == "X"
    header_read = lib.reads[0]
    assert header_read["options"] == ["OBJECTCLAS EQ 'IDENTITY'",
                                      "AND OBJECTID EQ 'DEVELOPER'",
                                      "AND UDATE GE '20170101'"]
    item_reads = [r for r in lib.reads if r["table"] == "CDPOS"]
    assert len(item_reads) == 2
    for read in item_reads:
        assert not ({"VALUE_NEW", "VALUE_OLD"} <= set(read["fields"]))


def test_read_change_documents_sans_postes_ne_lit_qu_une_table():
    lib = _reading_lib({"CDHDR": [[dict(_CD_HEADER)]]})
    documents = lib.read_change_documents("IDENTITY", include_items=False)
    assert documents[0]["items"] == []
    assert [r["table"] for r in lib.reads] == ["CDHDR"]


def test_get_idoc_status_classe_compte_et_historise():
    lib = _reading_lib({
        "EDIDC": [[{"DOCNUM": "0000000001", "STATUS": "53"},
                   {"DOCNUM": "0000000002", "STATUS": "51"},
                   {"DOCNUM": "0000000003", "STATUS": "99"}]],
        "EDIDS": [[{"DOCNUM": "0000000001", "COUNTR": "1", "STATUS": "53"}]],
    })
    result = lib.get_idoc_status(message_type="MATMAS", include_history=True)
    assert [i["category"] for i in result["idocs"]] == [
        "success", "error", "unmapped"]
    assert result["counts"] == {"success": 1, "error": 1, "in_progress": 0,
                                "unmapped": 1}
    assert result["idocs"][0]["history"][0]["COUNTR"] == "1"
    history_read = lib.reads[-1]
    assert history_read["table"] == "EDIDS"
    assert history_read["options"][0] == "DOCNUM EQ '0000000001'"
    assert history_read["options"][1].startswith("OR DOCNUM EQ ")


def test_get_idoc_status_vide_rend_des_comptes_a_zero_sans_historique():
    lib = _reading_lib({"EDIDC": [[]]})
    result = lib.get_idoc_status(include_history=True)
    assert result == {"idocs": [], "counts": {"success": 0, "error": 0,
                                              "in_progress": 0, "unmapped": 0}}
    assert [r["table"] for r in lib.reads] == ["EDIDC"]


def test_read_application_log_convertit_filtre_et_totalise():
    lib = _reading_lib({"BALHDR": [[
        {"LOGNUMBER": "1", "OBJECT": "/IWFND/", "MSG_CNT_AL": "000004",
         "MSG_CNT_A": "000000", "MSG_CNT_E": "000004", "MSG_CNT_W": "000000",
         "MSG_CNT_I": "000000", "MSG_CNT_S": "000000"}]]})
    result = lib.read_application_log(log_object="/IWFND/",
                                      with_problems_only=True)
    assert result["headers"][0]["error"] == 4
    assert result["totals"]["error"] == 4 and result["totals"]["total"] == 4
    options = lib.reads[0]["options"]
    assert options[0] == "OBJECT EQ '/IWFND/'"
    assert options[1] == "AND ( MSG_CNT_E GT 0 OR MSG_CNT_A GT 0 )"


def test_get_job_log_chaine_xbp_et_logoff_meme_sur_echec():
    """La contre-épreuve de `CALL_FUNCTION_NOT_REMOTE` : le journal passe par
    la chaîne XBP, et `BAPI_XMI_LOGOFF` part MÊME quand la lecture échoue
    (une session XMI orpheline reste ouverte côté serveur)."""
    lib = SapApiLibrary()
    lib.calls = []

    def call_bapi(name, alias="default", **params):
        lib.calls.append(name)
        if name == "BAPI_XBP_JOB_JOBLOG_READ":
            assert params["JOBNAME"] == "SAP_TEST"
            assert params["EXTERNAL_USER_NAME"] == "AUDITOR"
            return {"RETURN": {"TYPE": ""},
                    "JOB_PROTOCOL": [{"MSGID": "00", "MSGNO": "516",
                                      "TEXT": "Job started "}]}
        return {"RETURN": {"TYPE": ""}}

    lib.call_bapi = call_bapi
    lib.call_rfc = lambda name, alias="default", **params: lib.calls.append(name)
    lines = lib.get_job_log("SAP_TEST", "10284100", external_user="AUDITOR")
    assert lines == [{"MSGID": "00", "MSGNO": "516", "TEXT": "Job started"}]
    assert lib.calls == ["BAPI_XMI_LOGON", "BAPI_XBP_JOB_JOBLOG_READ",
                         "BAPI_XMI_LOGOFF"]

    # échec de lecture : le logoff part quand même, l'erreur remonte
    def failing_bapi(name, alias="default", **params):
        lib.calls.append(name)
        if name == "BAPI_XBP_JOB_JOBLOG_READ":
            raise AssertionError("job inconnu")
        return {"RETURN": {"TYPE": ""}}

    lib.calls = []
    lib.call_bapi = failing_bapi
    with pytest.raises(AssertionError, match="job inconnu"):
        lib.get_job_log("SAP_TEST", "10284100", external_user="AUDITOR")
    assert "BAPI_XMI_LOGOFF" in lib.calls


def test_date_invalide_echoue_en_nommant_l_argument():
    lib = _reading_lib({})
    with pytest.raises(ValueError, match="date_from"):
        lib.read_change_documents("IDENTITY", date_from="pas-une-date")
