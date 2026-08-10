"""Tests du parseur $metadata OData (``sapfx_common.odata_metadata``) :
v2 (edmx Microsoft, sap:label) et v4 (edmx OASIS), recherche de propriété
par libellé (contrat d'ambiguïté : tous les candidats), catalogue simplifié."""
import pytest

from sapfx_common.odata_metadata import (
    find_property_by_label,
    known_labels,
    parse_metadata,
    simplify_catalog_entries,
)

_V2 = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="1.0" xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
 <edmx:DataServices xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" m:DataServiceVersion="2.0">
  <Schema Namespace="ZSVC" Alias="Self" xmlns="http://schemas.microsoft.com/ado/2008/09/edm" xmlns:sap="http://www.sap.com/Protocols/SAPData">
   <EntityType Name="Carrier">
    <Key><PropertyRef Name="CarrierID"/></Key>
    <Property Name="CarrierID" Type="Edm.String" Nullable="false" sap:label="Airline"/>
    <Property Name="CarrierName" Type="Edm.String" sap:label="Airline Name"/>
    <Property Name="Currency" Type="Edm.String"/>
   </EntityType>
   <EntityContainer Name="ZC" m:IsDefaultEntityContainer="true">
    <EntitySet Name="Carriers" EntityType="Self.Carrier"/>
    <FunctionImport Name="Regenerate" ReturnType="Edm.String" m:HttpMethod="POST"/>
   </EntityContainer>
  </Schema>
 </edmx:DataServices>
</edmx:Edmx>"""

_V4 = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx" Version="4.0">
 <edmx:DataServices>
  <Schema xmlns="http://docs.oasis-open.org/odata/ns/edm" Namespace="TravelService">
   <EntityType Name="Travel">
    <Key><PropertyRef Name="TravelUUID"/></Key>
    <Property Name="TravelUUID" Type="Edm.Guid" Nullable="false"/>
    <Property Name="Description" Type="Edm.String"/>
   </EntityType>
   <Action Name="acceptTravel" IsBound="true"/>
   <EntityContainer Name="EntityContainer">
    <EntitySet Name="Travel" EntityType="TravelService.Travel"/>
   </EntityContainer>
  </Schema>
 </edmx:DataServices>
</edmx:Edmx>"""


def test_parse_v2_sets_cles_labels_et_function_imports():
    metadata = parse_metadata(_V2)
    assert metadata["version"] == "2.0"
    carriers = metadata["entity_sets"]["Carriers"]
    assert carriers["keys"] == ["CarrierID"]
    assert carriers["properties"]["CarrierID"] == {
        "type": "Edm.String", "nullable": False, "label": "Airline"}
    assert carriers["properties"]["Currency"]["label"] is None
    assert metadata["function_imports"] == [{
        "name": "Regenerate", "http_method": "POST",
        "return_type": "Edm.String"}]


def test_parse_v2_resout_le_type_reference_par_alias():
    # EntitySet référence "Self.Carrier" (l'alias du schéma), pas "ZSVC.Carrier"
    metadata = parse_metadata(_V2)
    assert metadata["entity_sets"]["Carriers"]["properties"]


def test_parse_v4_version_actions_et_cles():
    metadata = parse_metadata(_V4)
    assert metadata["version"] == "4.0"
    assert metadata["entity_sets"]["Travel"]["keys"] == ["TravelUUID"]
    assert {"kind": "action", "name": "acceptTravel",
            "bound": True} in metadata["actions"]


def test_parse_xml_illisible_est_actionnable():
    with pytest.raises(ValueError, match=r"\$metadata"):
        parse_metadata("<html>page de login</html><oops")


def test_find_property_by_label_exact_avant_partiel():
    metadata = parse_metadata(_V2)
    exact = find_property_by_label(metadata, "airline")
    assert [c["property"] for c in exact] == ["CarrierID"]
    assert exact[0]["match"] == "exact"
    partial = find_property_by_label(metadata, "airl")
    # pas d'exact : TOUS les partiels remontent (ambiguïté à l'appelant)
    assert sorted(c["property"] for c in partial) == ["CarrierID", "CarrierName"]
    assert find_property_by_label(metadata, "fournisseur") == []


def test_find_property_by_label_restreint_a_un_entity_set():
    metadata = parse_metadata(_V2)
    assert find_property_by_label(metadata, "airline", entity_set="Autre") == []


def test_known_labels_echantillon_trie():
    metadata = parse_metadata(_V2)
    assert known_labels(metadata) == ["Airline", "Airline Name"]


def test_simplify_catalog_entries_tolerant():
    entries = [
        {"ID": "Z1", "Title": "Un", "TechnicalServiceName": "ZSVC",
         "ServiceUrl": "http://h/svc", "TechnicalServiceVersion": "0001"},
        {"Id": "Z2", "Description": "Deux", "TechnicalName": "ZSVC2"},
        "pas-un-dict",
    ]
    assert simplify_catalog_entries(entries) == [
        {"id": "Z1", "title": "Un", "technical_name": "ZSVC",
         "service_url": "http://h/svc", "version": "0001"},
        {"id": "Z2", "title": "Deux", "technical_name": "ZSVC2",
         "service_url": None, "version": None},
    ]
