"""Tests hors réseau de SapApiLibrary : la frontière `_transport` est stubbée
par une fausse réponse HTTP : sessions, construction d'URL (options système
OData, sap-client), enveloppes v2/v4, $count, protocole CSRF, erreurs
auto-corrigibles, RFC optionnel (pyrfc factice injecté)."""
import io
import importlib
import json
import ssl
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
         "sap_client": None, "authenticated": False, "oauth": False,
         "csrf_token_cached": False, "requests": 0, "errors": 0,
         "created_entities": 0},
        {"alias": "default", "base_url": "http://vhcala4hci:50000",
         "sap_client": "001", "authenticated": True, "oauth": False,
         "csrf_token_cached": False, "requests": 0, "errors": 0,
         "created_entities": 0},
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


def test_close_all_api_sessions_ferme_aussi_les_connexions_rfc():
    closed = []

    class FakeConnection:
        def __init__(self, name):
            self.name = name

        def close(self):
            closed.append(self.name)

    lib = SapApiLibrary()
    lib._rfc_connections()["a"] = FakeConnection("a")
    lib._rfc_connections()["b"] = FakeConnection("b")
    lib.close_all_api_sessions()
    assert sorted(closed) == ["a", "b"]
    assert lib.list_api_sessions()["rfc_connections"] == []


def test_close_all_rfc_connections_best_effort_sur_connexion_morte():
    closed = []

    class DeadConnection:
        def close(self):
            raise RuntimeError("already gone")

    class LiveConnection:
        def close(self):
            closed.append("live")

    lib = SapApiLibrary()
    lib._rfc_connections()["dead"] = DeadConnection()
    lib._rfc_connections()["live"] = LiveConnection()
    lib.close_all_rfc_connections()   # la morte n'empêche pas la vivante
    assert closed == ["live"]
    assert lib.list_api_sessions()["rfc_connections"] == []


# --- garde-fous d'ouverture de session ----------------------------------------------

def test_open_api_session_alias_vide_refuse():
    with pytest.raises(ValueError, match="non-empty"):
        SapApiLibrary().open_api_session("http://h", alias="   ")


def test_open_api_session_credentials_sur_http_clair_avertit(monkeypatch):
    warnings = []
    api_module = importlib.import_module("SapApiLibrary.SapApiLibrary")
    monkeypatch.setattr(api_module.logger, "warn",
                        lambda msg: warnings.append(msg))
    lib = SapApiLibrary()
    lib.open_api_session("http://h", user="U", password="P")
    assert any("http://" in w for w in warnings)
    warnings.clear()
    lib.open_api_session("https://h", user="U", password="P", alias="tls")
    lib.open_api_session("http://h", alias="anon")   # pas de credentials
    assert warnings == []


# --- $count strict -------------------------------------------------------------------

def test_get_odata_count_rejette_les_chiffres_noyes_dans_du_texte():
    # Une page HTML (login ITS, message d'erreur) contenant des chiffres ne
    # doit JAMAIS devenir un comptage : ce serait un faux positif silencieux.
    lib = _lib_with([_FakeResponse(b"<html>session expires in 30 minutes</html>")])
    lib.open_api_session("http://h")
    with pytest.raises(AssertionError, match="non numérique"):
        lib.get_odata_count("/Products")


# --- rejeu CSRF sur token expiré ----------------------------------------------------

def test_post_odata_rejoue_une_fois_sur_403_csrf_expire():
    expired = urllib.error.HTTPError(
        "http://h/A", 403, "Forbidden", None,
        io.BytesIO(b"CSRF token validation failed"))
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "OLD"}),   # fetch initial
        expired,                                                # post refusé
        _json_response({}, headers={"x-csrf-token": "NEW"}),   # re-fetch
        _json_response({"d": {"Id": "OK"}}, status=201),        # post rejoué
    ])
    lib.open_api_session("http://h")
    assert lib.post_odata("/A", {"k": 1})["d"]["Id"] == "OK"
    assert len(lib.requests_seen) == 4
    assert lib.requests_seen[3].get_header("X-csrf-token") == "NEW"


def test_post_odata_403_sans_csrf_remonte_sans_rejeu():
    denied = urllib.error.HTTPError(
        "http://h/A", 403, "Forbidden", None,
        io.BytesIO(b"No authorization for this service"))
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        denied,
    ])
    lib.open_api_session("http://h")
    with pytest.raises(AssertionError, match="403"):
        lib.post_odata("/A", {"k": 1})
    assert len(lib.requests_seen) == 2   # aucun rejeu aveugle


# --- CRUD complet : PATCH / DELETE ---------------------------------------------------

def test_patch_odata_applique_csrf_et_if_match():
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        _FakeResponse(b"", status=204),
    ])
    lib.open_api_session("http://h")
    assert lib.patch_odata("/Products('1')", {"Name": "X"}) == {}
    patch = lib.requests_seen[1]
    assert patch.get_method() == "PATCH"
    assert patch.get_header("If-match") == "*"
    assert patch.get_header("X-csrf-token") == "TOK"
    assert patch.data == json.dumps({"Name": "X"}).encode("utf-8")


def test_delete_odata_if_match_desactivable():
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        _FakeResponse(b"", status=204),
    ])
    lib.open_api_session("http://h")
    assert lib.delete_odata("/Products('1')", if_match=None) == {}
    delete = lib.requests_seen[1]
    assert delete.get_method() == "DELETE"
    assert delete.get_header("If-match") is None


def test_delete_odata_rejoue_une_fois_sur_403_csrf():
    expired = urllib.error.HTTPError(
        "http://h/A('1')", 403, "Forbidden", None,
        io.BytesIO(b"CSRF token validation failed"))
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "OLD"}),
        expired,
        _json_response({}, headers={"x-csrf-token": "NEW"}),
        _FakeResponse(b"", status=204),
    ])
    lib.open_api_session("http://h")
    assert lib.delete_odata("/A('1')") == {}
    assert lib.requests_seen[3].get_header("X-csrf-token") == "NEW"


def test_call_odata_function_get_et_post():
    lib = _lib_with([_json_response({"d": {"ok": True}})])
    lib.open_api_session("http://h")
    assert lib.call_odata_function("/Refresh", code="'FR'")["d"]["ok"] is True
    assert "code=%27FR%27" in lib.requests_seen[0].full_url

    lib2 = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        _FakeResponse(b"", status=204),
    ])
    lib2.open_api_session("http://h")
    assert lib2.call_odata_function("/Accept", method="POST") == {}
    assert lib2.requests_seen[1].get_method() == "POST"


# --- pagination server-driven --------------------------------------------------------

def test_get_odata_entities_suit_la_pagination_v2():
    page1 = {"d": {"results": [{"Id": "1"}],
                   "__next": "http://h/svc/A?$skiptoken=2"}}
    page2 = {"d": {"results": [{"Id": "2"}]}}
    lib = _lib_with([_json_response(page1), _json_response(page2)])
    lib.open_api_session("http://h")
    ids = [e["Id"] for e in lib.get_odata_entities("/svc/A", follow_next=True)]
    assert ids == ["1", "2"]
    assert "skiptoken=2" in lib.requests_seen[1].full_url


def test_get_odata_entities_pagination_v4_relative_au_service():
    page1 = {"value": [{"Id": "1"}], "@odata.nextLink": "A?$skiptoken=x"}
    page2 = {"value": [{"Id": "2"}]}
    lib = _lib_with([_json_response(page1), _json_response(page2)])
    lib.open_api_session("http://h")
    ids = [e["Id"] for e in lib.get_odata_entities("/svc/A", follow_next=True)]
    assert ids == ["1", "2"]
    assert lib.requests_seen[1].full_url.startswith("http://h/svc/A?")


def test_pagination_tronquee_est_annoncee(monkeypatch):
    warnings = []
    api_module = importlib.import_module("SapApiLibrary.SapApiLibrary")
    monkeypatch.setattr(api_module.logger, "warn",
                        lambda msg: warnings.append(msg))
    page = {"d": {"results": [{"Id": "1"}], "__next": "http://h/A?$skiptoken=2"}}
    lib = _lib_with([_json_response(page)])
    lib.open_api_session("http://h")
    assert len(lib.get_odata_entities("/A", follow_next=True, max_pages=1)) == 1
    assert any("max_pages" in w for w in warnings)


def test_sans_follow_next_une_seule_page_comportement_historique():
    page = {"d": {"results": [{"Id": "1"}], "__next": "http://h/A?$skiptoken=2"}}
    lib = _lib_with([_json_response(page)])
    lib.open_api_session("http://h")
    assert len(lib.get_odata_entities("/A")) == 1
    assert len(lib.requests_seen) == 1


# --- fabrique de données de test -----------------------------------------------------

def test_post_odata_track_enregistre_l_uri_v2():
    created = {"d": {"__metadata": {"uri": "http://h/svc/Products('9')"},
                     "Id": "9"}}
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        _json_response(created, status=201),
    ])
    lib.open_api_session("http://h")
    lib.post_odata("/svc/Products", {"Id": "9"}, track=True)
    assert lib.get_created_entities() == ["http://h/svc/Products('9')"]
    assert lib.list_api_sessions()["api_sessions"][0]["created_entities"] == 1


def test_post_odata_track_relativise_une_origine_etrangere():
    created = {"d": {"__metadata": {"uri": "http://proxy:99/svc/Products('9')"}}}
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        _json_response(created, status=201),
    ])
    lib.open_api_session("http://h")
    lib.post_odata("/svc/Products", {"Id": "9"}, track=True)
    assert lib.get_created_entities() == ["/svc/Products('9')"]


def test_delete_created_entities_lifo_et_rapport():
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        _FakeResponse(b"", status=204),
        _FakeResponse(b"", status=204),
    ])
    lib.open_api_session("http://h")
    lib.register_created_entity("/svc/A('1')")
    lib.register_created_entity("/svc/A('2')")
    report = lib.delete_created_entities()
    assert report == {"deleted": ["/svc/A('2')", "/svc/A('1')"], "failed": []}
    assert lib.get_created_entities() == []
    assert "A('2')" in lib.requests_seen[1].full_url   # LIFO sur le réseau


def test_delete_created_entities_best_effort_puis_strict():
    boom = urllib.error.HTTPError("http://h/svc/A('2')", 500, "ISE", None,
                                  io.BytesIO(b"locked"))
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        boom,
        _FakeResponse(b"", status=204),
    ])
    lib.open_api_session("http://h")
    lib.register_created_entity("/svc/A('1')")
    lib.register_created_entity("/svc/A('2')")
    report = lib.delete_created_entities()
    assert [f["uri"] for f in report["failed"]] == ["/svc/A('2')"]
    assert report["deleted"] == ["/svc/A('1')"]

    lib2 = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        urllib.error.HTTPError("http://h/x", 500, "ISE", None, io.BytesIO(b"")),
    ])
    lib2.open_api_session("http://h")
    lib2.register_created_entity("/svc/B('1')")
    with pytest.raises(AssertionError, match="strict"):
        lib2.delete_created_entities(strict=True)


def test_close_api_session_avertit_des_entites_non_nettoyees(monkeypatch):
    warnings = []
    api_module = importlib.import_module("SapApiLibrary.SapApiLibrary")
    monkeypatch.setattr(api_module.logger, "warn",
                        lambda msg: warnings.append(msg))
    lib = SapApiLibrary()
    lib.open_api_session("http://h")
    lib.register_created_entity("/svc/A('1')")
    lib.close_api_session()
    assert any("Delete Created Entities" in w for w in warnings)


def test_ensure_odata_entity_existante_ne_cree_rien():
    lib = _lib_with([_json_response({"d": {"Id": "X"}})])
    lib.open_api_session("http://h")
    result = lib.ensure_odata_entity("/svc/Products('X')", {"Id": "X"})
    assert result == {"created": False, "entity": {"d": {"Id": "X"}}}
    assert len(lib.requests_seen) == 1


def test_ensure_odata_entity_absente_cree_sur_l_entity_set():
    absent = urllib.error.HTTPError("http://h/svc/Products('X')", 404,
                                    "Not Found", None, io.BytesIO(b"not found"))
    lib = _lib_with([
        absent,
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        _json_response({"d": {"Id": "X"}}, status=201),
    ])
    lib.open_api_session("http://h")
    result = lib.ensure_odata_entity("/svc/Products('X')", {"Id": "X"})
    assert result["created"] is True
    assert lib.requests_seen[2].full_url.endswith("/svc/Products")


def test_ensure_odata_entity_sans_cle_exige_create_path():
    absent = urllib.error.HTTPError("http://h/svc/Products", 404, "Not Found",
                                    None, io.BytesIO(b""))
    lib = _lib_with([absent])
    lib.open_api_session("http://h")
    with pytest.raises(ValueError, match="create_path"):
        lib.ensure_odata_entity("/svc/Products", {"Id": "X"})


# --- $batch --------------------------------------------------------------------------

_BATCH_RESPONSE = (
    b"--b1\r\n"
    b"Content-Type: application/http\r\n"
    b"\r\n"
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: application/json\r\n"
    b"\r\n"
    b'{"d": {"Id": "1"}}\r\n'
    b"--b1\r\n"
    b"Content-Type: multipart/mixed; boundary=c1\r\n"
    b"\r\n"
    b"--c1\r\n"
    b"Content-Type: application/http\r\n"
    b"\r\n"
    b"HTTP/1.1 201 Created\r\n"
    b"\r\n"
    b'{"d": {"Id": "NEW"}}\r\n'
    b"--c1--\r\n"
    b"--b1--\r\n"
)


def test_post_odata_batch_multipart_csrf_et_reponses_aplaties():
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        _FakeResponse(_BATCH_RESPONSE, status=202,
                      headers={"Content-Type": "multipart/mixed; boundary=b1"}),
    ])
    lib.open_api_session("http://h")
    operations = [
        {"method": "GET", "path": "Products('1')"},
        {"method": "POST", "path": "Products", "payload": {"Id": "NEW"}},
    ]
    responses = lib.post_odata_batch("/svc", operations)
    assert [r["status"] for r in responses] == [200, 201]
    assert responses[1]["json"]["d"]["Id"] == "NEW"
    # le fetch CSRF vise la RACINE du service (GET sur $batch n'existe pas)
    assert lib.requests_seen[0].full_url == "http://h/svc/"
    batch = lib.requests_seen[1]
    assert batch.full_url.endswith("/svc/$batch")
    assert batch.get_header("Content-type", "").startswith(
        "multipart/mixed; boundary=")
    assert b"POST Products HTTP/1.1" in batch.data
    assert b"Content-ID: 1" in batch.data


def test_post_odata_batch_echec_partiel_leve_sauf_optout():
    failing = (
        b"--b1\r\n"
        b"Content-Type: application/http\r\n"
        b"\r\n"
        b"HTTP/1.1 400 Bad Request\r\n"
        b"\r\n"
        b"boom\r\n"
        b"--b1--\r\n"
    )
    def make_lib():
        lib = _lib_with([
            _json_response({}, headers={"x-csrf-token": "TOK"}),
            _FakeResponse(failing, status=202,
                          headers={"Content-Type": "multipart/mixed; boundary=b1"}),
        ])
        lib.open_api_session("http://h")
        return lib

    with pytest.raises(AssertionError, match="1 opération"):
        make_lib().post_odata_batch("/svc", [{"method": "GET", "path": "A"}])
    responses = make_lib().post_odata_batch(
        "/svc", [{"method": "GET", "path": "A"}], fail_on_error=False)
    assert responses[0]["status"] == 400


def test_post_odata_batch_accepte_les_operations_en_json():
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        _FakeResponse(_BATCH_RESPONSE, status=202,
                      headers={"Content-Type": "multipart/mixed; boundary=b1"}),
    ])
    lib.open_api_session("http://h")
    operations = json.dumps([{"method": "GET", "path": "Products('1')"},
                             {"method": "POST", "path": "Products",
                              "payload": {"Id": "NEW"}}])
    assert len(lib.post_odata_batch("/svc", operations)) == 2
    with pytest.raises(ValueError, match="JSON"):
        lib.post_odata_batch("/svc", "pas-du-json")


# --- perception : $metadata, libellés, catalogue -------------------------------------

_METADATA_V2 = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="1.0" xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
 <edmx:DataServices xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" m:DataServiceVersion="2.0">
  <Schema Namespace="ZSVC" xmlns="http://schemas.microsoft.com/ado/2008/09/edm" xmlns:sap="http://www.sap.com/Protocols/SAPData">
   <EntityType Name="Product">
    <Key><PropertyRef Name="Id"/></Key>
    <Property Name="Id" Type="Edm.String" Nullable="false" sap:label="Product ID"/>
    <Property Name="Name" Type="Edm.String" sap:label="Product Name"/>
   </EntityType>
   <EntityContainer Name="ZC" m:IsDefaultEntityContainer="true">
    <EntitySet Name="Products" EntityType="ZSVC.Product"/>
    <FunctionImport Name="Refresh" ReturnType="Edm.String" m:HttpMethod="POST"/>
   </EntityContainer>
  </Schema>
 </edmx:DataServices>
</edmx:Edmx>"""


def test_get_odata_metadata_parse_et_met_en_cache():
    lib = _lib_with([_FakeResponse(_METADATA_V2.encode("utf-8")),
                     _FakeResponse(_METADATA_V2.encode("utf-8"))])
    lib.open_api_session("http://h")
    metadata = lib.get_odata_metadata("/sap/opu/odata/sap/ZSVC")
    assert lib.requests_seen[0].full_url.endswith("/ZSVC/$metadata")
    assert lib.requests_seen[0].get_header("Accept") == "application/xml"
    assert metadata["version"] == "2.0"
    products = metadata["entity_sets"]["Products"]
    assert products["keys"] == ["Id"]
    assert products["properties"]["Id"]["label"] == "Product ID"
    assert metadata["function_imports"][0]["http_method"] == "POST"
    # cache : pas de nouvelle requête…
    lib.get_odata_metadata("/sap/opu/odata/sap/ZSVC")
    assert len(lib.requests_seen) == 1
    # …sauf refresh explicite
    lib.get_odata_metadata("/sap/opu/odata/sap/ZSVC", refresh=True)
    assert len(lib.requests_seen) == 2


def test_find_odata_property_by_label_et_echec_actionnable():
    lib = _lib_with([_FakeResponse(_METADATA_V2.encode("utf-8"))])
    lib.open_api_session("http://h")
    found = lib.find_odata_property_by_label("/svc", "product id")
    assert found == [{"entity_set": "Products", "property": "Id",
                      "label": "Product ID", "type": "Edm.String",
                      "match": "exact"}]
    with pytest.raises(AssertionError) as err:
        lib.find_odata_property_by_label("/svc", "Fournisseur")
    message = str(err.value)
    assert "Product ID" in message and "Get Odata Metadata" in message


def test_list_odata_services_simplifie_le_catalogue():
    catalog = {"d": {"results": [{
        "ID": "ZSVC_0001", "Title": "Demo", "TechnicalServiceName": "ZSVC",
        "ServiceUrl": "http://h/sap/opu/odata/sap/ZSVC",
        "TechnicalServiceVersion": "0001", "Ignore": "x"}]}}
    lib = _lib_with([_json_response(catalog)])
    lib.open_api_session("http://h")
    services = lib.list_odata_services()
    assert services == [{"id": "ZSVC_0001", "title": "Demo",
                         "technical_name": "ZSVC",
                         "service_url": "http://h/sap/opu/odata/sap/ZSVC",
                         "version": "0001"}]
    url = lib.requests_seen[0].full_url
    assert "catalogservice" in url and "%24format=json" in url


# --- préflight Gateway ---------------------------------------------------------------

def test_get_gateway_status_ok_inactive_et_injoignable():
    ok = _lib_with([_json_response({"d": {"results": []}})])
    ok.open_api_session("http://h")
    assert ok.get_gateway_status()["status"] == "ok"

    inactive = _lib_with([urllib.error.HTTPError(
        "http://h/cat", 500, "ISE", None,
        io.BytesIO(b"<message>error /IWFND/CM_COS/003 occurred</message>"))])
    inactive.open_api_session("http://h")
    status = inactive.get_gateway_status()
    assert status["status"] == "gateway_inactive"
    assert "/IWFND/IWF_ACTIVATE" in status["remediation"]

    down = _lib_with([urllib.error.URLError("connexion refusée")])
    down.open_api_session("http://h")
    assert down.get_gateway_status()["status"] == "unreachable"


def test_gateway_should_be_active_nomme_la_remediation():
    lib = _lib_with([urllib.error.HTTPError(
        "http://h/cat", 500, "ISE", None,
        io.BytesIO(b"/IWFND/CM_COS/003"))])
    lib.open_api_session("http://h")
    with pytest.raises(AssertionError, match="IWF_ACTIVATE"):
        lib.gateway_should_be_active()


def test_wait_until_api_available_reussit_apres_echecs():
    lib = _lib_with([urllib.error.URLError("boot en cours"),
                     _json_response({"d": {"results": []}})])
    lib.open_api_session("http://h")
    result = lib.wait_until_api_available(timeout="2s", poll="0.01s")
    assert result["available"] is True and result["status"] == "ok"
    assert result["waited_seconds"] >= 0


def test_wait_until_api_available_timeout_avec_diagnostic():
    lib = _lib_with([urllib.error.URLError("down")] * 5)
    lib.open_api_session("http://h")
    with pytest.raises(AssertionError) as err:
        lib.wait_until_api_available(timeout="0.05s", poll="0.01s")
    assert "indisponible" in str(err.value)
    assert "docker start" in str(err.value)


# --- OAuth2 client credentials et mTLS -----------------------------------------------

def test_oauth_bearer_token_demande_une_fois_et_jamais_fuite():
    lib = _lib_with([_json_response({"value": []}),
                     _json_response({"value": []})])
    token_requests = []

    def fake_token_transport(session, request):
        token_requests.append(request)
        return _json_response({"access_token": "tok-1", "expires_in": 3600})

    lib._token_transport = fake_token_transport
    lib.open_api_session("https://api", token_url="https://ias/token",
                         client_id="cid", client_secret=Secret("csec"))
    lib.get_odata("/x")
    lib.get_odata("/y")
    assert len(token_requests) == 1   # token mis en cache
    assert lib.requests_seen[0].get_header("Authorization") == "Bearer tok-1"
    token_request = token_requests[0]
    assert token_request.get_header("Authorization", "").startswith("Basic ")
    assert b"grant_type=client_credentials" in token_request.data
    state = lib.list_api_sessions()
    assert state["api_sessions"][0]["oauth"] is True
    assert "csec" not in json.dumps(state)


def test_oauth_401_renouvelle_le_token_et_rejoue():
    denied = urllib.error.HTTPError("https://api/x", 401, "Unauthorized",
                                    None, io.BytesIO(b""))
    lib = _lib_with([denied, _json_response({"value": []})])
    issued = iter(["tok-old", "tok-new"])
    lib._token_transport = lambda session, request: _json_response(
        {"access_token": next(issued), "expires_in": 3600})
    lib.open_api_session("https://api", token_url="https://ias/token",
                         client_id="cid", client_secret="s")
    lib.get_odata("/x")
    assert lib.requests_seen[1].get_header("Authorization") == "Bearer tok-new"


def test_token_url_sans_client_id_refuse():
    with pytest.raises(ValueError, match="client_id"):
        SapApiLibrary().open_api_session("https://api",
                                         token_url="https://ias/token")


def test_client_cert_charge_le_contexte_mtls(monkeypatch):
    loaded = []
    monkeypatch.setattr(
        ssl.SSLContext, "load_cert_chain",
        lambda self, certfile, keyfile=None, password=None:
        loaded.append((certfile, keyfile)))
    lib = SapApiLibrary()
    lib.open_api_session("https://api", client_cert="client.pem",
                         client_key="client.key")
    assert loaded == [("client.pem", "client.key")]
    assert lib._session("default").tls_context is not None


# --- télémétrie du canal -------------------------------------------------------------

def test_telemetrie_compte_requetes_erreurs_et_statuts():
    boom = urllib.error.HTTPError("http://h/ko", 500, "ISE", None,
                                  io.BytesIO(b"boom"))
    lib = _lib_with([_json_response({"value": []}), boom])
    lib.open_api_session("http://h")
    lib.get_odata("/ok")
    with pytest.raises(AssertionError):
        lib.get_odata("/ko")
    telemetry = lib.get_api_telemetry()
    assert telemetry["requests"] == 2 and telemetry["errors"] == 1
    assert telemetry["last_status"] == 500
    assert telemetry["alias"] == "default"
    row = lib.list_api_sessions()["api_sessions"][0]
    assert row["requests"] == 2 and row["errors"] == 1


# --- BAPI (RETURN vérifié par TYPE) et job de fond -----------------------------------

def test_call_bapi_verifie_return_par_type():
    class FakeConn:
        def call(self, name, **kwargs):
            if name == "BAPI_FAIL":
                return {"RETURN": [{"TYPE": "E", "ID": "XX", "NUMBER": "001",
                                    "MESSAGE": "boom"}]}
            return {"RETURN": {"TYPE": "S", "MESSAGE": "ok"}, "OUT": 1}

    lib = SapApiLibrary()
    lib._rfc_connections()["default"] = FakeConn()
    assert lib.call_bapi("BAPI_OK")["OUT"] == 1
    with pytest.raises(AssertionError) as err:
        lib.call_bapi("BAPI_FAIL")
    message = str(err.value)
    assert "E XX/001" in message and "Rollback Bapi Transaction" in message


def test_commit_et_rollback_bapi_transaction():
    recorded = []

    class FakeConn:
        def call(self, name, **kwargs):
            recorded.append((name, kwargs))
            return {"RETURN": []}

    lib = SapApiLibrary()
    lib._rfc_connections()["default"] = FakeConn()
    lib.commit_bapi_transaction()
    lib.commit_bapi_transaction(wait=False)
    lib.rollback_bapi_transaction()
    assert recorded == [("BAPI_TRANSACTION_COMMIT", {"WAIT": "X"}),
                        ("BAPI_TRANSACTION_COMMIT", {}),
                        ("BAPI_TRANSACTION_ROLLBACK", {})]


class _JobConn:
    """Connexion RFC factice : rejoue une séquence de listes de statuts TBTCO
    (la dernière liste est resservie une fois la séquence épuisée)."""

    def __init__(self, sequences):
        self.sequences = list(sequences)
        self.params = []

    def call(self, name, **kwargs):
        self.params.append((name, kwargs))
        statuses = (self.sequences.pop(0) if len(self.sequences) > 1
                    else self.sequences[0])
        return {"FIELDS": [{"FIELDNAME": "STATUS"}],
                "DATA": [{"WA": status} for status in statuses]}


def test_wait_for_background_job_attend_puis_reussit():
    lib = SapApiLibrary()
    conn = _JobConn([["R"], ["F"]])
    lib._rfc_connections()["default"] = conn
    result = lib.wait_for_background_job("ZJOB", timeout="2s", poll="0.01s")
    assert result["state"] == "done" and result["statuses"] == {"F": 1}
    name, kwargs = conn.params[0]
    assert name == "RFC_READ_TABLE"
    assert kwargs["QUERY_TABLE"] == "TBTCO"
    assert kwargs["OPTIONS"] == [{"TEXT": "JOBNAME EQ 'ZJOB'"}]


def test_wait_for_background_job_annule_echoue():
    lib = SapApiLibrary()
    lib._rfc_connections()["default"] = _JobConn([["A", "F"]])
    with pytest.raises(AssertionError, match="annulé"):
        lib.wait_for_background_job("ZJOB", timeout="1s", poll="0.01s")


def test_wait_for_background_job_timeout_actionnable():
    lib = SapApiLibrary()
    lib._rfc_connections()["default"] = _JobConn([[]])
    with pytest.raises(AssertionError) as err:
        lib.wait_for_background_job("ZJOB", timeout="0.05s", poll="0.01s")
    assert "jobcount" in str(err.value)


def test_wait_for_background_job_sans_connexion_guide():
    with pytest.raises(RuntimeError, match="Open Rfc Connection"):
        SapApiLibrary().wait_for_background_job("ZJOB")


def test_lookup_business_term_meme_vocabulaire_que_les_canaux_gui():
    info = SapApiLibrary().lookup_business_term("compagnie aérienne",
                                                domain="FLIGHT")
    assert info["abap_field"] == "CARRID"
