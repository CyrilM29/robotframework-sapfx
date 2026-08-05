"""Tests hors réseau de SapApiLibrary : la frontière `_transport` est stubbée
par une fausse réponse HTTP : sessions, construction d'URL (options système
OData, sap-client), enveloppes v2/v4, $count, protocole CSRF, erreurs
auto-corrigibles, RFC optionnel (pyrfc factice injecté)."""
import io
import importlib
import json
import sys
import urllib.error

import pytest
from robot.api.types import Secret

from SapApiLibrary import SapApiLibrary
from SapApiLibrary.SapApiLibrary import _SameOriginRedirectHandler


class _FakeResponse(io.BytesIO):
    def __init__(self, body=b"", status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _lib_with(responses):
    """Bibliothèque dont le transport rejoue `responses` (liste de
    _FakeResponse ou d'exceptions) en enregistrant chaque requête urllib."""
    lib = SapApiLibrary()
    lib.requests_seen = []
    queue = list(responses)

    def fake_transport(session, request):
        lib.requests_seen.append(request)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    lib._transport = fake_transport
    return lib


def _json_response(payload, status=200, headers=None):
    return _FakeResponse(json.dumps(payload).encode("utf-8"), status, headers)


# --- sessions et URLs -------------------------------------------------------------

def test_keyword_sans_session_guide_vers_open_api_session():
    with pytest.raises(RuntimeError) as err:
        SapApiLibrary().get_odata("/x")
    assert "Open Api Session" in str(err.value)


def test_list_api_sessions_expose_l_etat_sans_jamais_les_credentials():
    lib = SapApiLibrary()
    lib.open_api_session("http://vhcala4hci:50000/", user="DEVELOPER",
                         password=Secret("très-secret"), sap_client="001")
    lib.open_api_session("http://autre:443", alias="anonyme")
    state = lib.list_api_sessions()
    assert state["api_sessions"] == [
        {"alias": "anonyme", "base_url": "http://autre:443",
         "sap_client": None, "authenticated": False,
         "csrf_token_cached": False},
        {"alias": "default", "base_url": "http://vhcala4hci:50000",
         "sap_client": "001", "authenticated": True,
         "csrf_token_cached": False},
    ]
    assert state["rfc_connections"] == []
    # ni le mot de passe ni le header Authorization ne fuient
    assert "très-secret" not in json.dumps(state)
    assert "Authorization" not in json.dumps(state)


def test_list_api_sessions_vide_puis_apres_teardown():
    lib = SapApiLibrary()
    assert lib.list_api_sessions() == {"api_sessions": [],
                                       "rfc_connections": []}
    lib.open_api_session("http://x:1")
    lib.close_all_api_sessions()
    assert lib.list_api_sessions()["api_sessions"] == []


def test_list_api_sessions_compte_les_connexions_rfc():
    lib = SapApiLibrary()
    lib._rfc_connections()["prod"] = object()   # connexion pyrfc factice
    assert lib.list_api_sessions()["rfc_connections"] == ["prod"]


def test_url_composee_avec_options_systeme_et_sap_client():
    lib = _lib_with([_json_response({"value": []})])
    lib.open_api_session("http://host:50000", user="U", password="P",
                         sap_client="001")
    lib.get_odata("/sap/opu/odata/sap/SRV/Products", top="5", filter="Price gt 1")
    url = lib.requests_seen[0].full_url
    assert url.startswith("http://host:50000/sap/opu/odata/sap/SRV/Products?")
    assert "%24top=5" in url and "%24filter=Price+gt+1" in url
    assert "sap-client=001" in url
    assert lib.requests_seen[0].get_header("Authorization", "").startswith("Basic ")


def test_secret_est_deballe_uniquement_dans_l_entete_basic():
    lib = _lib_with([_json_response({"value": []})])
    lib.open_api_session("https://host", user="U", password=Secret("P"))
    lib.get_odata("/Products")
    authorization = lib.requests_seen[0].get_header("Authorization")
    assert authorization == "Basic VTpQ"


def test_url_absolue_et_redirection_cross_origin_sont_refusees():
    lib = _lib_with([])
    lib.open_api_session("https://host")
    with pytest.raises(ValueError, match="Cross-origin API URL blocked"):
        lib.get_odata("https://attacker.invalid/Products")

    handler = _SameOriginRedirectHandler("https://host")
    with pytest.raises(urllib.error.URLError, match="Cross-origin API redirect blocked"):
        handler.redirect_request(None, None, 302, "Found", {},
                                 "https://attacker.invalid/steal")


def test_close_api_session_oublie_l_alias():
    lib = _lib_with([])
    lib.open_api_session("http://h")
    lib.close_api_session()
    with pytest.raises(RuntimeError):
        lib.get_odata("/x")


def test_sessions_api_sont_isolees_par_namespace_rfmcp(monkeypatch):
    namespace = {"value": "rfmcp:a"}
    api_module = importlib.import_module("SapApiLibrary.SapApiLibrary")
    monkeypatch.setattr(api_module, "current_execution_namespace",
                        lambda: namespace["value"])
    lib = SapApiLibrary()
    lib.open_api_session("http://a", alias="shared")

    namespace["value"] = "rfmcp:b"
    with pytest.raises(RuntimeError, match="Aucune session API 'shared'"):
        lib._session("shared")
    lib.open_api_session("http://b", alias="shared")

    namespace["value"] = "rfmcp:a"
    assert lib._session("shared").base_url == "http://a"
    namespace["value"] = "rfmcp:b"
    assert lib._session("shared").base_url == "http://b"
    lib.close_all_api_sessions()

    namespace["value"] = "rfmcp:a"
    assert lib._session("shared").base_url == "http://a"


# --- enveloppes v2/v4 et $count ----------------------------------------------------

def test_get_odata_entities_enveloppe_v2_et_v4():
    v2 = {"d": {"results": [{"Id": "1"}, {"Id": "2"}]}}
    v4 = {"value": [{"Id": "3"}]}
    lib = _lib_with([_json_response(v2), _json_response(v4)])
    lib.open_api_session("http://h")
    assert [e["Id"] for e in lib.get_odata_entities("/A")] == ["1", "2"]
    assert [e["Id"] for e in lib.get_odata_entities("/B")] == ["3"]


def test_get_odata_entities_entite_seule_v2():
    lib = _lib_with([_json_response({"d": {"Id": "42"}})])
    lib.open_api_session("http://h")
    assert lib.get_odata_entities("/A('42')") == [{"Id": "42"}]


def test_get_odata_count_lit_l_entier_meme_avec_bom():
    lib = _lib_with([_FakeResponse("﻿205".encode("utf-8"))])
    lib.open_api_session("http://h")
    assert lib.get_odata_count("/Products") == 205
    # $count vit dans le CHEMIN (jamais urlencodé), pas en paramètre
    assert lib.requests_seen[0].full_url.endswith("/Products/$count")


def test_get_odata_count_sans_entier_echoue_clairement():
    lib = _lib_with([_FakeResponse(b"<html>oops</html>")])
    lib.open_api_session("http://h")
    with pytest.raises(AssertionError) as err:
        lib.get_odata_count("/Products")
    assert "$count" in str(err.value)


# --- CSRF -------------------------------------------------------------------------

def test_post_odata_applique_le_protocole_csrf():
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK123"}),   # fetch
        _json_response({"d": {"Id": "NEW"}}, status=201),          # post
    ])
    lib.open_api_session("http://h")
    result = lib.post_odata("/Products", {"Name": "X"})
    assert result["d"]["Id"] == "NEW"
    fetch, post = lib.requests_seen
    assert fetch.get_header("X-csrf-token") == "Fetch"
    assert post.get_header("X-csrf-token") == "TOK123"
    assert post.data == json.dumps({"Name": "X"}).encode("utf-8")


def test_post_odata_204_retourne_dict_vide_et_token_reutilise():
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        _FakeResponse(b"", status=204),
        _FakeResponse(b"", status=204),   # 2e post : pas de nouveau fetch
    ])
    lib.open_api_session("http://h")
    assert lib.post_odata("/A", {"k": 1}) == {}
    assert lib.post_odata("/A", {"k": 2}) == {}
    assert len(lib.requests_seen) == 3   # fetch + 2 posts


# --- erreurs auto-corrigibles --------------------------------------------------------

def test_erreur_http_nomme_statut_url_et_corps():
    error = urllib.error.HTTPError(
        "http://h/x", 403, "Forbidden", None, io.BytesIO(b"CSRF token missing"))
    lib = _lib_with([error])
    lib.open_api_session("http://h")
    with pytest.raises(AssertionError) as err:
        lib.get_odata("/x")
    message = str(err.value)
    assert "403" in message and "CSRF token missing" in message


def test_systeme_injoignable_suggere_les_verifications():
    lib = _lib_with([urllib.error.URLError("connexion refusée")])
    lib.open_api_session("http://h")
    with pytest.raises(AssertionError) as err:
        lib.get_odata("/x")
    assert "injoignable" in str(err.value)


def test_reponse_non_json_echoue_avec_extrait():
    lib = _lib_with([_FakeResponse(b"<xml>atom feed</xml>")])
    lib.open_api_session("http://h")
    with pytest.raises(AssertionError) as err:
        lib.get_odata("/x")
    assert "JSON" in str(err.value) and "atom" in str(err.value)


# --- RFC optionnel -------------------------------------------------------------------

def test_call_rfc_sans_connexion_guide_vers_open_rfc_connection():
    with pytest.raises(RuntimeError) as err:
        SapApiLibrary().call_rfc("STFC_CONNECTION")
    assert "Open Rfc Connection" in str(err.value)


def test_open_rfc_connection_sans_pyrfc_donne_la_marche_a_suivre(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyrfc", None)
    with pytest.raises((RuntimeError, ImportError)) as err:
        SapApiLibrary().open_rfc_connection(ashost="h", sysnr="00")
    assert "pyrfc" in str(err.value)


def test_call_rfc_via_pyrfc_factice(monkeypatch):
    calls = {}

    class FakeConnection:
        def __init__(self, **params):
            calls["params"] = params

        def call(self, name, **kwargs):
            calls["call"] = (name, kwargs)
            return {"ECHOTEXT": kwargs.get("REQUTEXT", "")}

        def close(self):
            calls["closed"] = True

    fake_pyrfc = type(sys)("pyrfc")
    fake_pyrfc.Connection = FakeConnection
    monkeypatch.setitem(sys.modules, "pyrfc", fake_pyrfc)
    lib = SapApiLibrary()
    lib.open_rfc_connection(ashost="vhcala4hci", sysnr="00", client="001",
                            user="U", passwd=Secret("P"))
    result = lib.call_rfc("STFC_CONNECTION", REQUTEXT="ping")
    assert result == {"ECHOTEXT": "ping"}
    assert calls["params"]["passwd"] == "P"
    assert calls["call"][0] == "STFC_CONNECTION"
    lib.close_rfc_connection()
    assert calls.get("closed") is True
