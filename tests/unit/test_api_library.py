"""Tests hors reseau de SapApiLibrary : sessions, URL, auth, erreurs, RFC de base. Doublures partagees dans _api_library_fixtures (convention #13)."""
from SapApiLibrary import SapApiLibrary
from SapApiLibrary.SapApiLibrary import _SameOriginRedirectHandler
from robot.api.types import Secret
import importlib
import io
import json
import pytest
import sys
import urllib.error

from _api_library_fixtures import (  # noqa: F401
    _FakeResponse,
    _json_response,
    _lib_with,
    _sent_header,
)



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
    assert "%24top=5" in url and "%24filter=Price%20gt%201" in url
    assert "sap-client=001" in url
    assert (_sent_header(lib.requests_seen[0], "Authorization") or "").startswith("Basic ")


def test_espaces_de_query_encodes_en_pourcent_20_jamais_en_plus():
    """Un `$filter` contient toujours des espaces. Encodés « à la formulaire
    HTML » (`+`), ils passent sur une Gateway SAP v2 mais font échouer un
    service OData v4 en HTTP 400 : constaté live contre CAP, qui répond
    « Expected "(", "/", or a whitespace but "+" found »."""
    lib = _lib_with([_json_response({"value": []})])
    lib.open_api_session("http://host:4004")
    lib.get_odata("/processor/Travel", filter="TravelID eq 1 and BookingFee gt 0")
    url = lib.requests_seen[0].full_url
    assert "+" not in url, url
    assert "%24filter=TravelID%20eq%201%20and%20BookingFee%20gt%200" in url


def test_encodage_de_query_ne_change_que_l_espace():
    """Corollaire du test précédent, et garde-fou de non-régression : le
    correctif est délibérément limité au caractère fautif. Sur tout le reste
    l'encodage doit rester IDENTIQUE à celui, éprouvé, qui était servi aux
    Gateway en production. `urlencode` encode déjà un vrai `+` en `%2B`, donc
    remplacer les `+` restants par `%20` décrit exactement l'écart attendu."""
    params = {"filter": "Name eq 'A B' and Qty gt 1",
              "select": "Id,Name", "expand": "to_Supplier/Address",
              "search": "a+b & c=d"}
    lib = _lib_with([_json_response({"value": []})])
    lib.open_api_session("http://host:50000")
    lib.get_odata("/SRV/Products", **params)
    query = lib.requests_seen[0].full_url.split("?", 1)[1]
    historique = urllib.parse.urlencode(
        [("$" + k if k in SapApiLibrary._SYSTEM_QUERY else k, v)
         for k, v in params.items()])
    assert query == historique.replace("+", "%20")
    assert "+" not in query


def test_secret_est_deballe_uniquement_dans_l_entete_basic():
    lib = _lib_with([_json_response({"value": []})])
    lib.open_api_session("https://host", user="U", password=Secret("P"))
    lib.get_odata("/Products")
    authorization = _sent_header(lib.requests_seen[0], "Authorization")
    assert authorization == "Basic VTpQ"


def test_cle_api_envoyee_en_entete_et_jamais_dans_l_url():
    """Le bac à sable SAP Business Accelerator Hub (api.sap.com) authentifie
    par une clé dans l'en-tête `APIKey`, pas en Basic ni en query : une clé
    passée en paramètre d'URL finirait dans les journaux du serveur."""
    lib = _lib_with([_json_response({"value": []})])
    lib.open_api_session("https://sandbox.api.sap.com/s4hanacloud",
                         api_key=Secret("cle-tres-secrete"))
    lib.get_odata("/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_BusinessPartner")
    request = lib.requests_seen[0]
    assert _sent_header(request, "APIKey") == "cle-tres-secrete"
    assert _sent_header(request, "Authorization") is None
    assert "cle-tres-secrete" not in request.full_url


def test_cle_api_entete_personnalisable():
    lib = _lib_with([_json_response({"value": []})])
    lib.open_api_session("https://host", api_key="k",
                         api_key_header="X-Api-Key")
    lib.get_odata("/Products")
    assert _sent_header(lib.requests_seen[0], "X-Api-Key") == "k"
    assert _sent_header(lib.requests_seen[0], "APIKey") is None


def test_cle_api_vide_refusee_a_l_ouverture_pas_au_premier_appel():
    """Une clé vide enverrait l'en-tête sans authentifier : l'échec
    arriverait au premier appel en HTTP 401, muet sur sa cause."""
    lib = _lib_with([])
    with pytest.raises(ValueError, match="api_key fourni mais vide"):
        lib.open_api_session("https://host", api_key=Secret("   "))
    with pytest.raises(ValueError, match="api_key_header vide"):
        lib.open_api_session("https://host", api_key="k", api_key_header=" ")


def test_cle_api_compte_comme_authentification_sans_jamais_fuiter():
    lib = SapApiLibrary()
    lib.open_api_session("https://sandbox.api.sap.com/s4hanacloud",
                         api_key=Secret("cle-tres-secrete"))
    state = lib.list_api_sessions()
    assert state["api_sessions"][0]["authenticated"] is True
    assert state["api_sessions"][0]["oauth"] is False
    assert "cle-tres-secrete" not in json.dumps(state)
    assert "APIKey" not in json.dumps(state)


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


def test_post_odata_applique_le_protocole_csrf():
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK123"}),   # fetch
        _json_response({"d": {"Id": "NEW"}}, status=201),          # post
    ])
    lib.open_api_session("http://h")
    result = lib.post_odata("/Products", {"Name": "X"})
    assert result["d"]["Id"] == "NEW"
    fetch, post = lib.requests_seen
    assert _sent_header(fetch, "X-CSRF-Token") == "Fetch"
    assert _sent_header(post, "X-CSRF-Token") == "TOK123"
    assert post.data == json.dumps({"Name": "X"}).encode("utf-8")


def test_post_odata_lit_le_token_csrf_quelle_que_soit_la_casse_de_l_en_tete():
    # Les en-têtes HTTP sont insensibles à la casse et ``dict(response.headers)``
    # conserve la casse ENVOYÉE : un relais qui répond ``X-Csrf-Token`` ne doit
    # pas faire tomber le token à vide (l'écriture partirait sans token et le
    # 403 qui suit se lirait comme une interdiction).
    lib = _lib_with([
        _json_response({}, headers={"X-Csrf-Token": "TOK123"}),   # fetch
        _json_response({"d": {"Id": "NEW"}}, status=201),          # post
    ])
    lib.open_api_session("http://h")
    lib.post_odata("/Products", {"Name": "X"})
    _, post = lib.requests_seen
    assert _sent_header(post, "X-CSRF-Token") == "TOK123"


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


def test_get_odata_count_rejette_les_chiffres_noyes_dans_du_texte():
    # Une page HTML (login ITS, message d'erreur) contenant des chiffres ne
    # doit JAMAIS devenir un comptage : ce serait un faux positif silencieux.
    lib = _lib_with([_FakeResponse(b"<html>session expires in 30 minutes</html>")])
    lib.open_api_session("http://h")
    with pytest.raises(AssertionError, match="non numérique"):
        lib.get_odata_count("/Products")
