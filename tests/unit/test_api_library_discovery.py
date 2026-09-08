"""Tests hors reseau de SapApiLibrary : $metadata, catalogue, Gateway, telemetrie, BAPI et jobs. Doublures dans _api_library_fixtures ; OAuth2/mTLS dans test_api_library_oauth.py."""
from SapApiLibrary import SapApiLibrary
import gzip
import io
import json
import pytest
import urllib.error

from _api_library_fixtures import (  # noqa: F401
    _BATCH_RESPONSE,
    _FakeResponse,
    _JobConn,
    _METADATA_V2,
    _json_response,
    _lib_with,
    _sent_header,
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
    assert (_sent_header(batch, "Content-Type") or "").startswith(
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


def test_get_odata_metadata_parse_et_met_en_cache():
    lib = _lib_with([_FakeResponse(_METADATA_V2.encode("utf-8")),
                     _FakeResponse(_METADATA_V2.encode("utf-8"))])
    lib.open_api_session("http://h")
    metadata = lib.get_odata_metadata("/sap/opu/odata/sap/ZSVC")
    assert lib.requests_seen[0].full_url.endswith("/ZSVC/$metadata")
    assert _sent_header(lib.requests_seen[0], "Accept") == "application/xml"
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


def test_reponse_gzip_non_demandee_est_decompressee():
    """Relevé live sur le bac à sable SAP Business Accelerator Hub : le
    `$metadata` revient en `Content-Encoding: gzip` alors que le client
    n'envoie AUCUN `Accept-Encoding`. Sans décompression, les octets
    compressés atteignaient le parseur XML, qui accusait le document
    (« invalid token: line 1, column 0 ») là où le fautif était le
    transport."""
    comprime = gzip.compress(_METADATA_V2.encode("utf-8"))
    assert comprime[:2] == b"\x1f\x8b"
    lib = _lib_with([_FakeResponse(comprime,
                                   headers={"Content-Encoding": "gzip"})])
    lib.open_api_session("https://sandbox.api.sap.com/s4hanacloud")
    metadata = lib.get_odata_metadata("/sap/opu/odata/sap/ZSVC")
    assert metadata["version"] == "2.0"
    assert metadata["entity_sets"]["Products"]["keys"] == ["Id"]


def test_corps_json_gzippe_est_lu_comme_du_json():
    lib = _lib_with([_FakeResponse(
        gzip.compress(json.dumps({"value": [{"Id": "1"}]}).encode("utf-8")),
        headers={"content-encoding": "GZIP"})])   # casse indifférente
    lib.open_api_session("https://host")
    assert lib.get_odata_entities("/Products") == [{"Id": "1"}]


def test_encodage_inconnu_laisse_le_corps_intact():
    """Un encodage qu'on ne sait pas défaire (brotli ici) ne doit pas lever
    dans la couche transport : le diagnostic du niveau au-dessus nomme le
    statut, l'URL et un extrait, ce qu'une exception de zlib ne ferait pas."""
    lib = _lib_with([_FakeResponse(b"\x0b\x02\x80brotli",
                                   headers={"Content-Encoding": "br"})])
    lib.open_api_session("https://host")
    with pytest.raises(AssertionError, match="illisible"):
        lib.get_odata("/Products")


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


def test_gateway_status_200_html_nest_plus_un_vert_et_faux():
    # Le cas Work Zone (2026-08-26) : toute route déclarée répond 200 avec la
    # page HTML d'amorçage de connexion. `Gateway Should Be Active` passait.
    lib = _lib_with([_FakeResponse(
        b"<!DOCTYPE html><html><head><script>bootstrap login</script>")])
    lib.open_api_session("https://site.example")
    status = lib.get_gateway_status()
    assert status["status"] == "login_page"
    lib2 = _lib_with([_FakeResponse(b"<!DOCTYPE html><html>")])
    lib2.open_api_session("https://site.example")
    with pytest.raises(AssertionError, match="aucune donnée"):
        lib2.gateway_should_be_active()


def test_gateway_status_redirection_cross_origin_classee_idp():
    # Le garde same-origin lève une URLError marquée : elle doit ressortir en
    # identity_provider_redirect, jamais en « système éteint ».
    lib = _lib_with([urllib.error.URLError(
        "Cross-origin API redirect blocked: https://tenant/oauth2/authorize")])
    lib.open_api_session("https://site.example")
    status = lib.get_gateway_status()
    assert status["status"] == "identity_provider_redirect"
    assert "clé de service" in status["remediation"]


def test_les_sondes_alimentent_la_telemetrie():
    # Mesuré live avant correctif (reconnaissance BTP) : ~15 sondes réseau,
    # `requests: 2`. Une reconnaissance faite de sondes doit compter, sinon
    # `Api Channel Should Show Activity` échoue sur un canal qui a bien
    # traversé le réseau. Un refus de sonde reste un RÉSULTAT : errors à 0.
    lib = _lib_with([
        _json_response({"d": {"results": []}}),
        urllib.error.HTTPError("http://h/x", 404, "NF", None,
                               io.BytesIO(b"not here")),
        urllib.error.URLError("down"),
    ])
    lib.open_api_session("http://h")
    lib.get_gateway_status()
    lib.get_gateway_status()
    lib.get_gateway_status()
    telemetry = lib.get_api_telemetry()
    assert telemetry["requests"] == 3
    assert telemetry["errors"] == 0
    assert telemetry["last_status"] == 404  # l'URLError n'a pas de statut


def test_get_http_response_lit_le_corps_brut_sans_lever():
    # Né de la reconnaissance BTP : lire une page HTML exigeait de la
    # détourner du message d'échec de Get Odata.
    lib = _lib_with([
        _FakeResponse(b"<!DOCTYPE html><html>page</html>", status=200,
                      headers={"Content-Type": "text/html"}),
        urllib.error.HTTPError("http://h/absent", 404, "NF",
                               {"X-Marker": "yes"}, io.BytesIO(b"rien ici")),
        urllib.error.URLError("connexion refusée"),
    ])
    lib.open_api_session("http://h")
    ok = lib.get_http_response("/site")
    assert ok["status"] == 200
    assert ok["body"].startswith("<!DOCTYPE html>")
    assert ok["headers"]["Content-Type"] == "text/html"
    assert ok["truncated"] is False and ok["error"] is None
    assert ok["url"].startswith("http://h/site")
    refus = lib.get_http_response("/absent")
    assert refus["status"] == 404 and "rien ici" in refus["body"]
    down = lib.get_http_response("/down")
    assert down["status"] is None and "connexion refusée" in down["error"]


def test_get_http_response_tronque_en_le_disant_et_pose_ses_en_tetes():
    lib = _lib_with([_FakeResponse(b"A" * 50)])
    lib.open_api_session("http://h")
    court = lib.get_http_response("/big", max_chars=10,
                                  headers={"Accept": "text/html"})
    assert court["body"] == "A" * 10 and court["truncated"] is True
    assert _sent_header(lib.requests_seen[-1], "Accept") == "text/html"


def test_open_api_session_headers_surchargent_l_accept_maison():
    # Un approuter BTP arbitre HTML/JSON sur l'Accept : la session doit
    # pouvoir le poser une fois pour toutes.
    lib = _lib_with([_json_response({"value": []})])
    lib.open_api_session("http://h",
                         headers={"Accept": "text/html", "X-Custom": "v"})
    lib.get_odata_entities("/svc/Set")
    assert _sent_header(lib.requests_seen[-1], "Accept") == "text/html"
    assert _sent_header(lib.requests_seen[-1], "X-Custom") == "v"


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
