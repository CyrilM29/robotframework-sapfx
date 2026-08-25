"""Tests hors reseau de SapApiLibrary : CSRF, ecritures, pagination, fabrique de donnees, $batch. Doublures dans _api_library_fixtures."""
from SapApiLibrary import SapApiLibrary
import importlib
import io
import json
import pytest
import urllib.error

from _api_library_fixtures import (  # noqa: F401
    _FakeResponse,
    _json_response,
    _lib_with,
    _sent_header,
)



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
    assert _sent_header(lib.requests_seen[3], "X-CSRF-Token") == "NEW"


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


def test_post_odata_rejoue_sur_403_avec_en_tete_csrf_required():
    # Le juge fiable du protocole SAP : l'en-tête x-csrf-token: Required de la
    # réponse, même quand le corps ne prononce jamais « csrf ».
    expired = urllib.error.HTTPError(
        "http://h/A", 403, "Forbidden",
        {"x-csrf-token": "Required"}, io.BytesIO(b"Access denied"))
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "OLD"}),
        expired,
        _json_response({}, headers={"x-csrf-token": "NEW"}),
        _json_response({"d": {"Id": "OK"}}, status=201),
    ])
    lib.open_api_session("http://h")
    assert lib.post_odata("/A", {"k": 1})["d"]["Id"] == "OK"
    assert _sent_header(lib.requests_seen[3], "X-CSRF-Token") == "NEW"


def test_post_odata_403_en_tete_non_required_remonte_meme_si_le_texte_dit_csrf():
    # Un 403 dont l'en-tête x-csrf-token porte un token (pas « Required »)
    # est une interdiction réelle : pas de rejeu, même si le corps dit csrf.
    denied = urllib.error.HTTPError(
        "http://h/A", 403, "Forbidden",
        {"x-csrf-token": "abc123"}, io.BytesIO(b"CSRF protection: forbidden"))
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        denied,
    ])
    lib.open_api_session("http://h")
    with pytest.raises(AssertionError, match="403"):
        lib.post_odata("/A", {"k": 1})
    assert len(lib.requests_seen) == 2


def test_post_odata_rejoue_sur_403_dont_le_relais_a_vide_l_en_tete_csrf():
    """Un relais peut transmettre ``x-csrf-token:`` SANS valeur. L'en-tête
    présent mais vide n'est plus un signal : sans repli sur le texte, une
    écriture qui se rétablissait seule après le timeout Gateway (~30 min)
    échouerait désormais définitivement."""
    expired = urllib.error.HTTPError(
        "http://h/A", 403, "Forbidden",
        {"x-csrf-token": "  "}, io.BytesIO(b"CSRF token validation failed"))
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "OLD"}),
        expired,
        _json_response({}, headers={"x-csrf-token": "NEW"}),
        _json_response({"d": {"Id": "OK"}}, status=201),
    ])
    lib.open_api_session("http://h")
    assert lib.post_odata("/A", {"k": 1})["d"]["Id"] == "OK"
    assert _sent_header(lib.requests_seen[3], "X-CSRF-Token") == "NEW"


def test_post_odata_rejoue_sur_un_required_decore_par_un_relais():
    """« Required; expired » reste un Required : la valeur est lue sur son
    PREMIER mot, pas comparée à l'identique."""
    expired = urllib.error.HTTPError(
        "http://h/A", 403, "Forbidden",
        {"x-csrf-token": "Required; expired"}, io.BytesIO(b"Access denied"))
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "OLD"}),
        expired,
        _json_response({}, headers={"x-csrf-token": "NEW"}),
        _json_response({"d": {"Id": "OK"}}, status=201),
    ])
    lib.open_api_session("http://h")
    assert lib.post_odata("/A", {"k": 1})["d"]["Id"] == "OK"
    assert _sent_header(lib.requests_seen[3], "X-CSRF-Token") == "NEW"


def test_patch_odata_applique_csrf_et_if_match():
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        _FakeResponse(b"", status=204),
    ])
    lib.open_api_session("http://h")
    assert lib.patch_odata("/Products('1')", {"Name": "X"}) == {}
    patch = lib.requests_seen[1]
    assert patch.get_method() == "PATCH"
    assert _sent_header(patch, "If-Match") == "*"
    assert _sent_header(patch, "X-CSRF-Token") == "TOK"
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
    assert _sent_header(delete, "If-Match") is None


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
    assert _sent_header(lib.requests_seen[3], "X-CSRF-Token") == "NEW"


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


def test_pagination_ne_double_pas_le_sap_client_deja_porte_par_le_lien():
    # Le lien de page suivante est fabriqué par le SERVEUR et reconduit en
    # général les options de la requête d'origine, sap-client compris : le
    # réajouter donnerait sap-client=001&sap-client=001.
    page1 = {"d": {"results": [{"Id": "1"}],
                   "__next": "http://h/svc/A?$skiptoken=2&sap-client=001"}}
    page2 = {"d": {"results": [{"Id": "2"}]}}
    lib = _lib_with([_json_response(page1), _json_response(page2)])
    lib.open_api_session("http://h", sap_client="001")
    lib.get_odata_entities("/svc/A", follow_next=True)
    next_url = lib.requests_seen[1].full_url
    assert next_url.count("sap-client=") == 1
    # ...et le paramètre reste ajouté quand le lien ne le porte PAS.
    assert lib.requests_seen[0].full_url.count("sap-client=001") == 1


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


def test_post_odata_track_resout_un_location_relatif_au_service():
    """Un service OData v4 renvoie un `Location` relatif au SERVICE
    (`Travel.drafts('…')`, constaté live sur CAP, sans `@odata.id`). Résolu
    contre la base de session il perdait `/processor`, la suppression partait
    sur la racine (404) et la donnée restait : `Delete Created Entities`
    rendait un rapport en échec alors que le `$count` des entités actives,
    lui, semblait restauré."""
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        _json_response({"TravelUUID": "u1"}, status=201,
                       headers={"Location": "Travel.drafts('u1')"}),
    ])
    lib.open_api_session("http://h:4004")
    lib.post_odata("/processor/Travel", {}, track=True)
    assert lib.get_created_entities() == [
        "http://h:4004/processor/Travel.drafts('u1')"]


def test_post_odata_track_puis_suppression_vise_bien_le_service():
    """Bout en bout du cas précédent : l'URI suivie est celle que le DELETE
    doit atteindre, préfixe de service compris."""
    lib = _lib_with([
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        _json_response({"TravelUUID": "u1"}, status=201,
                       headers={"Location": "Travel.drafts('u1')"}),
        _json_response({}, headers={"x-csrf-token": "TOK"}),
        _FakeResponse(b"", status=204),
    ])
    lib.open_api_session("http://h:4004")
    lib.post_odata("/processor/Travel", {}, track=True)
    report = lib.delete_created_entities()
    assert report["failed"] == []
    assert lib.requests_seen[-1].full_url == (
        "http://h:4004/processor/Travel.drafts('u1')")


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
