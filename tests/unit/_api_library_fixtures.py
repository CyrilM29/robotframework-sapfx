"""Doublures et helpers partages des tests du canal API (SapApiLibrary) : transport stubbe via lib._transport (extraits, convention #13)."""
# ruff: noqa: F401  (surface re-exportee vers les fichiers de tests decoupes)
import gzip


import io


import importlib


import json


import ssl


import sys


import urllib.error


import urllib.parse


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


def _sent_header(request, name):
    """En-tête réellement porté par la requête, cherché SANS regarder la
    casse : urllib normalise les noms qu'il transmet (`APIKey` part en
    `Apikey`), ce qu'un serveur HTTP conforme traite à l'identique, et
    `Request.get_header` est devenu une correspondance exacte en Python
    3.14. La propriété testée est « l'en-tête est envoyé avec cette
    valeur », jamais l'orthographe retenue par urllib."""
    for key, value in request.headers.items():
        if key.lower() == name.lower():
            return value
    return None


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
