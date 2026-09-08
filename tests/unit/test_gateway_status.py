"""Tests du classifieur de sonde Gateway (``sapfx_common.gateway_status``) :
chaque état porte sa remédiation nommée, le cas fondateur étant le HTTP 500
``/IWFND/CM_COS/003`` d'une Gateway désactivée (conteneur A4H re-créé). Le
second cas fondateur (2026-08-26, site SAP Build Work Zone) : une cible
derrière un fournisseur d'identité ne renvoie JAMAIS de défi, toute route
répond 200 avec une page HTML de connexion, et le classifieur d'avant y
voyait « Catalogue Gateway joignable »."""
from sapfx_common.gateway_status import (
    CATALOG_SERVICE_PATH,
    CROSS_ORIGIN_REDIRECT_MARKER,
    classify_gateway_probe,
    format_gateway_failure,
    looks_like_html,
    refused_by_sap_backend,
)

# En-têtes RÉELS d'un 401 formé par le serveur ABAP derrière la couche de
# gestion d'API du bac à sable SAP Business Accelerator Hub (relevé live le
# 2026-09-06). Le corps est une page HTML en ALLEMAND, ce qui est exactement
# la raison pour laquelle le discriminant est ici et pas dans le texte.
_BACKEND_401_HEADERS = {
    "Content-Type": "text/html; charset=utf-8",
    "sap-authenticated": "false",
    "sap-system": "EJS",
    "www-authenticate": 'Basic realm="SAP NetWeaver Application Server [EJS/100][alias]"',
    "sap-server": "true",
}

# Réponse de la couche de gestion d'API elle-même quand elle refuse la clé :
# son propre format, son propre code d'erreur, aucun marqueur ABAP.
_EDGE_401_BODY = ('{"fault":{"faultstring":"Invalid ApiKey",'
                  '"detail":{"errorcode":"oauth.v2.InvalidApiKey"}}}')


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
    assert classify_gateway_probe(418, body="")["status"] == "unexpected"


def test_redirection_est_un_idp_pas_un_systeme_eteint():
    # Le garde same-origin refuse la redirection en URLError : sans le
    # marqueur, ce cas se classait « unreachable » avec la remédiation
    # « docker start », l'inverse de la vérité sur BTP.
    blocked = classify_gateway_probe(
        None, error="%s: https://tenant.example/oauth2/authorize"
        % CROSS_ORIGIN_REDIRECT_MARKER)
    assert blocked["status"] == "identity_provider_redirect"
    assert "client credentials" in blocked["remediation"]
    assert "clé de service" in blocked["remediation"]
    # Un vrai 3xx (redirection non suivie) porte le même verdict.
    redirect = classify_gateway_probe(302, body="")
    assert redirect["status"] == "identity_provider_redirect"
    # Et une URLError SANS le marqueur reste un système injoignable.
    assert classify_gateway_probe(
        None, error="connexion refusée")["status"] == "unreachable"


def test_200_html_est_une_page_de_login_jamais_un_ok():
    # Le « vert et faux » relevé live : HTTP 200, corps HTML d'amorçage de
    # connexion, aucune donnée servie.
    page = classify_gateway_probe(
        200, body="<!DOCTYPE html><html><head><script>login</script>")
    assert page["status"] == "login_page"
    assert page["remediation"] is not None
    # Des DONNÉES en 200 restent un ok : JSON du catalogue, XML $metadata.
    assert classify_gateway_probe(
        200, body='{"d": {"results": []}}')["status"] == "ok"
    assert classify_gateway_probe(
        200, body='<?xml version="1.0"?><edmx:Edmx/>')["status"] == "ok"


def test_looks_like_html_est_structurel_jamais_textuel():
    # Le critère est la STRUCTURE du document (convention #3 : un mot comme
    # « login » dépendrait de la langue du serveur).
    assert looks_like_html("<!doctype html><html lang='en'>")
    assert looks_like_html("﻿  \n<HTML><body>")
    assert not looks_like_html('{"value": []}')
    assert not looks_like_html('<?xml version="1.0"?><edmx:Edmx/>')
    assert not looks_like_html("")
    # Un corps qui PARLE de HTML sans en être n'en est pas.
    assert not looks_like_html('{"error": "expected <html> tag"}')


def test_format_gateway_failure_concatene_detail_et_remediation():
    message = format_gateway_failure(classify_gateway_probe(
        500, body="/IWFND/CM_COS/003"))
    assert "gateway_inactive" in message
    assert "/IWFND/IWF_ACTIVATE" in message


def test_refused_by_sap_backend_lit_les_en_tetes_jamais_le_texte():
    # Trois marqueurs, chacun suffisant, tous structurels.
    assert refused_by_sap_backend(_BACKEND_401_HEADERS)
    assert refused_by_sap_backend({"sap-authenticated": "false"})
    assert refused_by_sap_backend({"WWW-Authenticate":
                                   'Basic realm="SAP NetWeaver Application Server [X]"'})
    assert refused_by_sap_backend({"Sap-System": "EJS"})   # casse indifférente
    # La couche de gestion d'API n'en porte aucun.
    assert not refused_by_sap_backend({"Content-Type": "application/json"})
    assert not refused_by_sap_backend({})
    assert not refused_by_sap_backend(None)
    # Un serveur ABAP qui a bien authentifié n'est pas un refus de sa part.
    assert not refused_by_sap_backend({"sap-authenticated": "true"})
    # Un itérable de NOMS ne porte aucune valeur : pas de devinette.
    assert not refused_by_sap_backend(["sap-authenticated"])


def test_401_dedouble_selon_la_couche_qui_refuse():
    # Le cas vécu le 2026-09-06 : clé d'API VALIDE (la couche de gestion la
    # laisse passer), système ABAP derrière qui refuse. Diagnostiquer
    # « vérifier vos identifiants » enverrait régénérer une clé saine.
    derriere = classify_gateway_probe(401, body="<html>Anmeldung fehlgeschlagen",
                                      headers=_BACKEND_401_HEADERS,
                                      edge_credential=True)
    assert derriere["status"] == "backend_auth_failed"
    assert "ACCEPTÉE" in derriere["detail"] or "acceptée" in derriere["detail"]
    assert "Ne pas régénérer" in derriere["remediation"]
    # La couche de gestion refusant la clé reste un auth_failed ordinaire.
    devant = classify_gateway_probe(401, body=_EDGE_401_BODY, headers={
        "Content-Type": "application/json"}, edge_credential=True)
    assert devant["status"] == "auth_failed"
    # Sans couche devant (Basic sur un ABAP), les MÊMES marqueurs signifient
    # que ce sont les identifiants du client qui sont refusés : la
    # distinction ne tient qu'au mode d'authentification, jamais aux en-têtes.
    direct = classify_gateway_probe(401, headers=_BACKEND_401_HEADERS,
                                    edge_credential=False)
    assert direct["status"] == "auth_failed"
    # Compatibilité : l'appel historique à trois arguments est inchangé.
    assert classify_gateway_probe(401, "", None)["status"] == "auth_failed"
