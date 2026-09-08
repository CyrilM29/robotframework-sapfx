"""Tests hors reseau de l'authentification du canal API (SapApiLibrary) :
OAuth2 client credentials (cache, echeance, renouvellement, garde de
redirection du token endpoint) et mTLS. Doublures dans _api_library_fixtures ;
extrait de test_api_library_discovery.py (convention #13)."""
import io
import json
import ssl
import time
import urllib.error
import urllib.request

import pytest
from robot.api.types import Secret

from SapApiLibrary import SapApiLibrary
from SapApiLibrary.SapApiLibrary import _ApiSession, _SameOriginRedirectHandler

from _api_library_fixtures import (  # noqa: F401
    _json_response,
    _lib_with,
    _sent_header,
)


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
    assert _sent_header(lib.requests_seen[0], "Authorization") == "Bearer tok-1"
    token_request = token_requests[0]
    assert (_sent_header(token_request, "Authorization") or "").startswith("Basic ")
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
    assert _sent_header(lib.requests_seen[1], "Authorization") == "Bearer tok-new"


def test_token_url_sans_client_id_refuse():
    with pytest.raises(ValueError, match="client_id"):
        SapApiLibrary().open_api_session("https://api",
                                         token_url="https://ias/token")


def test_token_opener_ne_transmet_pas_les_identifiants_cross_origin():
    # Le gestionnaire de redirection standard d'urllib CONSERVE l'en-tête
    # Authorization (ici le Basic client_id:client_secret) en suivant une
    # redirection vers un autre hôte : la preuve de non-transmission est que
    # la redirection cross-origin n'est jamais SUIVIE. La garde est épinglée
    # sur l'origine du token endpoint LUI-MÊME : l'hôte API est cross-origin
    # aussi (un token endpoint ne redirige pas légitimement vers l'API).
    session = _ApiSession("https://api.example", None, None, None, 30.0, True)
    request = urllib.request.Request(
        "https://ias.example/oauth/token",
        data=b"grant_type=client_credentials", method="POST",
        headers={"Authorization": "Basic c2VjcmV0"})
    opener = SapApiLibrary._token_opener(session, request)
    redirect = next(h for h in opener.handlers
                    if isinstance(h, _SameOriginRedirectHandler))
    for lure in ("https://evil.example/collect",
                 "https://api.example/collect",
                 "http://ias.example/oauth/token"):   # même hôte, schéma dégradé
        with pytest.raises(urllib.error.URLError, match="Cross-origin"):
            redirect.redirect_request(request, None, 302, "Found", {}, lure)
    # Une redirection restée sur l'origine du token endpoint est suivie.
    followed = redirect.redirect_request(
        request, None, 302, "Found", {}, "https://ias.example/oauth/token2")
    assert followed.full_url == "https://ias.example/oauth/token2"


def test_token_opener_reutilise_le_contexte_tls_de_la_session():
    # Le refactor de la garde ne doit pas perdre le contexte mTLS/verify_tls.
    session = _ApiSession("https://api.example", None, None, None, 30.0, False)
    request = urllib.request.Request("https://ias.example/token", data=b"x",
                                     method="POST")
    opener = SapApiLibrary._token_opener(session, request)
    assert any(getattr(handler, "_context", None) is session.tls_context
               for handler in opener.handlers)


def test_oauth_echeance_jamais_au_dela_de_la_duree_annoncee():
    # Un token annoncé 10 s était gardé 30 s (plancher max(30, 0.9*durée))
    # puis rejoué expiré : l'échéance locale reste SOUS la durée annoncée.
    lib = _lib_with([_json_response({"value": []})])
    lib._token_transport = lambda session, request: _json_response(
        {"access_token": "tok", "expires_in": 10})
    lib.open_api_session("https://api", token_url="https://ias/token",
                         client_id="cid", client_secret="s")
    lib.get_odata("/x")
    session = lib._api_sessions()["default"]
    margin = session.token_expiry - time.monotonic()
    assert 0 < margin <= 9.001   # 90 % de la durée annoncée, jamais plus


def test_oauth_expires_in_zero_expire_aussitot():
    # `expires_in: 0` n'est pas « absent » : le token expire aussitôt et se
    # redemande à chaque requête (l'ancien `or 300` le gardait 5 minutes).
    lib = _lib_with([_json_response({"value": []}),
                     _json_response({"value": []})])
    issued = []

    def transport(session, request):
        issued.append(request)
        return _json_response({"access_token": "tok-%d" % len(issued),
                               "expires_in": 0})

    lib._token_transport = transport
    lib.open_api_session("https://api", token_url="https://ias/token",
                         client_id="cid", client_secret="s")
    lib.get_odata("/x")
    lib.get_odata("/y")
    assert len(issued) == 2


def test_oauth_expires_in_absent_garde_le_defaut_et_le_cache():
    # Seul un champ ABSENT vaut le défaut de 300 s : le token est mis en
    # cache, et son échéance ne dépasse pas ce défaut non plus.
    lib = _lib_with([_json_response({"value": []}),
                     _json_response({"value": []})])
    issued = []

    def transport(session, request):
        issued.append(request)
        return _json_response({"access_token": "tok"})

    lib._token_transport = transport
    lib.open_api_session("https://api", token_url="https://ias/token",
                         client_id="cid", client_secret="s")
    lib.get_odata("/x")
    lib.get_odata("/y")
    assert len(issued) == 1
    session = lib._api_sessions()["default"]
    margin = session.token_expiry - time.monotonic()
    assert 0 < margin <= 300


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
