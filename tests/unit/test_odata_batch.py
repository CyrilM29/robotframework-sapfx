"""Tests du multipart ``$batch`` OData (``sapfx_common.odata_batch``) :
assemblage (lectures indépendantes, écritures en changeset atomique ou non,
Content-ID), parsing de réponse (changesets aplatis, boundary citée)."""
import pytest

from sapfx_common.odata_batch import build_batch, parse_batch_response


def test_build_batch_lectures_et_changeset_atomique():
    body, content_type = build_batch(
        [{"method": "GET", "path": "Products('1')"},
         {"method": "POST", "path": "Products", "payload": {"Id": "A"}},
         {"method": "PATCH", "path": "Products('2')",
          "payload": {"Name": "B"}, "headers": {"If-Match": "*"}}],
        boundary="b1", changeset_boundary="c1")
    text = body.decode("utf-8")
    assert content_type == "multipart/mixed; boundary=b1"
    assert "GET Products('1') HTTP/1.1" in text
    # UN seul changeset pour les deux écritures (unité atomique SAP)
    assert text.count("boundary=c1") == 1
    assert "POST Products HTTP/1.1" in text
    assert "PATCH Products('2') HTTP/1.1" in text
    assert "Content-ID: 1" in text and "Content-ID: 2" in text
    assert "If-Match: *" in text
    assert text.endswith("--b1--\r\n")
    # la lecture reste HORS du changeset : elle apparaît avant son ouverture
    assert text.index("GET Products") < text.index("boundary=c1")


def test_build_batch_non_atomique_un_changeset_par_ecriture():
    body, _ = build_batch(
        [{"method": "POST", "path": "A", "payload": {}},
         {"method": "DELETE", "path": "A('1')"}],
        boundary="b1", changeset_boundary="c1", atomic=False)
    text = body.decode("utf-8")
    assert "boundary=c1_1" in text and "boundary=c1_2" in text


def test_build_batch_valide_les_operations():
    with pytest.raises(ValueError, match="aucune opération"):
        build_batch([])
    with pytest.raises(ValueError, match="méthode"):
        build_batch([{"method": "FETCH", "path": "A"}])
    with pytest.raises(ValueError, match="path"):
        build_batch([{"method": "GET"}])
    with pytest.raises(ValueError, match="dict"):
        build_batch(["GET A"])


_RESPONSE = (
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
    b"Location: http://h/svc/Products('A')\r\n"
    b"\r\n"
    b'{"d": {"Id": "A"}}\r\n'
    b"--c1\r\n"
    b"Content-Type: application/http\r\n"
    b"\r\n"
    b"HTTP/1.1 204 No Content\r\n"
    b"\r\n"
    b"\r\n"
    b"--c1--\r\n"
    b"--b1--\r\n"
)


def test_parse_batch_response_aplatit_les_changesets():
    responses = parse_batch_response(
        _RESPONSE, 'multipart/mixed; boundary="b1"')
    assert [r["status"] for r in responses] == [200, 201, 204]
    assert responses[0]["json"] == {"d": {"Id": "1"}}
    assert responses[1]["headers"]["location"] == "http://h/svc/Products('A')"
    assert responses[1]["reason"] == "Created"
    assert responses[2]["json"] is None and responses[2]["body"] == ""


def test_parse_batch_response_sans_boundary_est_actionnable():
    with pytest.raises(ValueError, match="boundary"):
        parse_batch_response(b"whatever", "application/json")


def test_roundtrip_boundaries_generees():
    body, content_type = build_batch([{"method": "GET", "path": "A"}])
    assert content_type.startswith("multipart/mixed; boundary=batch_")
    assert body.decode("utf-8").count("GET A HTTP/1.1") == 1
