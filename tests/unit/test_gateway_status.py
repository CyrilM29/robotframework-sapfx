"""Tests du classifieur de sonde Gateway (``sapfx_common.gateway_status``) :
chaque état porte sa remédiation nommée, le cas fondateur étant le HTTP 500
``/IWFND/CM_COS/003`` d'une Gateway désactivée (conteneur A4H re-créé)."""
from sapfx_common.gateway_status import (
    CATALOG_SERVICE_PATH,
    classify_gateway_probe,
    format_gateway_failure,
)


def test_ok_et_unreachable():
    assert classify_gateway_probe(200)["status"] == "ok"
    assert classify_gateway_probe(200)["remediation"] is None
    down = classify_gateway_probe(None, error="connexion refusée")
    assert down["status"] == "unreachable"
    assert "docker start" in down["remediation"]
    assert "connexion refusée" in down["detail"]


def test_auth_et_autorisations():
    assert classify_gateway_probe(401)["status"] == "auth_failed"
    assert "sap_client" in classify_gateway_probe(401)["remediation"]
    forbidden = classify_gateway_probe(403)
    assert forbidden["status"] == "forbidden"
    assert "S_SERVICE" in forbidden["remediation"]


def test_catalogue_introuvable_nomme_le_chemin_standard():
    result = classify_gateway_probe(404)
    assert result["status"] == "catalog_not_found"
    assert CATALOG_SERVICE_PATH in result["remediation"]


def test_gateway_inactive_reconnue_au_marqueur_et_remediation_img():
    result = classify_gateway_probe(
        500, body="<message>error /IWFND/CM_COS/003 occurred</message>")
    assert result["status"] == "gateway_inactive"
    assert "/IWFND/IWF_ACTIVATE" in result["remediation"]
    assert "ecc-validation.md" in result["remediation"]


def test_500_sans_marqueur_reste_une_erreur_serveur():
    result = classify_gateway_probe(500, body="ASSERTION_FAILED dump")
    assert result["status"] == "server_error"
    assert "ASSERTION_FAILED" in result["detail"]


def test_statut_inattendu():
    assert classify_gateway_probe(302, body="")["status"] == "unexpected"


def test_format_gateway_failure_concatene_detail_et_remediation():
    message = format_gateway_failure(classify_gateway_probe(
        500, body="/IWFND/CM_COS/003"))
    assert "gateway_inactive" in message
    assert "/IWFND/IWF_ACTIVATE" in message
