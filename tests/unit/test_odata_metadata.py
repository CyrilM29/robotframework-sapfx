"""Tests du parseur $metadata OData (``sapfx_common.odata_metadata``) :
v2 (edmx Microsoft, sap:label) et v4 (edmx OASIS), recherche de propriété
par libellé (contrat d'ambiguïté : tous les candidats), catalogue simplifié."""
import pytest

from sapfx_common.odata_metadata import (
    find_property_by_label,
    known_labels,
    parse_metadata,
    simplify_catalog_entries,
    write_simulation_candidates,
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


# Le service qui DÉCLARE ses restrictions, calqué sur ce qui a été relevé
# live : un seul entity set non adressable (celui qui répond 403), un entity
# set ouvert au cycle complet, un autre en lecture seule.
_V2_ANNOTE = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="1.0" xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
 <edmx:DataServices xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" m:DataServiceVersion="2.0">
  <Schema Namespace="ZSVC" xmlns="http://schemas.microsoft.com/ado/2008/09/edm" xmlns:sap="http://www.sap.com/Protocols/SAPData">
   <EntityType Name="Review">
    <Key><PropertyRef Name="ReviewID"/></Key>
    <Property Name="ReviewID" Type="Edm.String" Nullable="false"/>
   </EntityType>
   <EntityContainer Name="ZC" m:IsDefaultEntityContainer="true">
    <EntitySet Name="Reviews" EntityType="ZSVC.Review" sap:label="Avis"
               sap:creatable="true" sap:updatable="true" sap:deletable="true"/>
    <EntitySet Name="Catalogue" EntityType="ZSVC.Review"
               sap:creatable="false" sap:updatable="false" sap:deletable="false"/>
    <EntitySet Name="DraftAdmin" EntityType="ZSVC.Review"
               sap:addressable="false" sap:creatable="false"
               sap:updatable="false" sap:deletable="false"/>
   </EntityContainer>
  </Schema>
 </edmx:DataServices>
</edmx:Edmx>"""


def test_entity_set_porte_ses_annotations_sap_et_leur_declaration():
    sets = parse_metadata(_V2_ANNOTE)["entity_sets"]
    assert sets["Reviews"]["label"] == "Avis"
    assert sets["Reviews"]["capabilities"]["creatable"] is True
    assert "creatable" in sets["Reviews"]["declared_capabilities"]
    # Non déclaré dans le document : la valeur reste le défaut de la Gateway,
    # et surtout elle n'apparaît PAS comme déclarée.
    assert sets["Reviews"]["capabilities"]["pageable"] is True
    assert "pageable" not in sets["Reviews"]["declared_capabilities"]


def test_addressable_faux_predit_le_refus_avant_tout_appel():
    sets = parse_metadata(_V2_ANNOTE)["entity_sets"]
    non_adressables = [n for n, i in sets.items()
                       if not i["capabilities"]["addressable"]]
    assert non_adressables == ["DraftAdmin"]


def test_entity_set_sans_annotation_garde_les_defauts_de_la_gateway():
    carriers = parse_metadata(_V2)["entity_sets"]["Carriers"]
    assert carriers["capabilities"]["addressable"] is True
    assert carriers["capabilities"]["searchable"] is False
    assert carriers["declared_capabilities"] == []


def test_candidats_ecriture_quand_le_service_declare_ses_restrictions():
    rapport = write_simulation_candidates(parse_metadata(_V2_ANNOTE))
    assert rapport["service_declares_restrictions"] is True
    retenus = {c["entity_set"]: c for c in rapport["candidates"]}
    # Seul l'entity set réellement ouvert reste candidat : les deux autres
    # ferment les trois opérations, donc ne sont pas proposés du tout.
    assert list(retenus) == ["Reviews"]
    # Ordre CRUD (créer, modifier, supprimer), pas alphabétique.
    assert retenus["Reviews"]["declared"] == ["creatable", "updatable", "deletable"]
    assert retenus["Reviews"]["keys"] == ["ReviewID"]


_V2_PARTIEL = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="1.0" xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
 <edmx:DataServices xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" m:DataServiceVersion="2.0">
  <Schema Namespace="ZSVC" xmlns="http://schemas.microsoft.com/ado/2008/09/edm" xmlns:sap="http://www.sap.com/Protocols/SAPData">
   <EntityType Name="T"><Key><PropertyRef Name="Id"/></Key>
    <Property Name="Id" Type="Edm.String" Nullable="false"/></EntityType>
   <EntityContainer Name="ZC" m:IsDefaultEntityContainer="true">
    <EntitySet Name="SalesOrderSet" EntityType="ZSVC.T" sap:updatable="true"/>
    <EntitySet Name="VH_CurrencySet" EntityType="ZSVC.T"/>
   </EntityContainer>
  </Schema>
 </edmx:DataServices>
</edmx:Edmx>"""


def test_un_service_peut_declarer_sur_un_set_et_se_taire_sur_un_autre():
    # La forme réellement rencontrée live : la garde au niveau du SERVICE est
    # vraie, alors qu'une aide à la recherche reste candidate par simple
    # défaut. C'est le cas que la garde par entity set doit rattraper.
    rapport = write_simulation_candidates(parse_metadata(_V2_PARTIEL))
    assert rapport["service_declares_restrictions"] is True
    par_nom = {c["entity_set"]: c for c in rapport["candidates"]}
    assert par_nom["SalesOrderSet"]["evidence"] == "declared"
    assert par_nom["VH_CurrencySet"]["evidence"] == "default"
    assert par_nom["VH_CurrencySet"]["declared"] == []
    # Une aide à la recherche paraît supprimable, sans que rien ne l'appuie.
    assert "deletable" in par_nom["VH_CurrencySet"]["allowed"]


_V2_INTERDICTIONS = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="1.0" xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
 <edmx:DataServices xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" m:DataServiceVersion="2.0">
  <Schema Namespace="ZSVC" xmlns="http://schemas.microsoft.com/ado/2008/09/edm" xmlns:sap="http://www.sap.com/Protocols/SAPData">
   <EntityType Name="T"><Key><PropertyRef Name="Id"/></Key>
    <Property Name="Id" Type="Edm.String" Nullable="false"/></EntityType>
   <EntityContainer Name="ZC" m:IsDefaultEntityContainer="true">
    <EntitySet Name="Products" EntityType="ZSVC.T"
               sap:creatable="false" sap:deletable="false"/>
   </EntityContainer>
  </Schema>
 </edmx:DataServices>
</edmx:Edmx>"""


def test_une_annotation_presente_n_est_pas_une_annotation_permissive():
    # La forme des deux seuls candidats d'une cible réelle : l'entity set
    # DÉCLARE deux interdictions et se tait sur le troisième verbe. Compter la
    # présence de l'annotation, et non sa valeur, le faisait passer pour
    # appuyé alors que sa seule capacité autorisée vient du silence.
    rapport = write_simulation_candidates(parse_metadata(_V2_INTERDICTIONS))
    produits = rapport["candidates"][0]
    assert produits["entity_set"] == "Products"
    assert produits["allowed"] == ["updatable"]
    assert produits["declared"] == ["creatable", "deletable"]
    assert produits["declared_allowed"] == []
    assert produits["evidence"] == "default"


def test_un_service_muet_ne_prouve_aucune_capacite_d_ecriture():
    # Le piège relevé live : un service qui n'annote RIEN rend tous ses
    # entity sets modifiables par défaut, aides à la recherche comprises.
    # La garde doit dire que le document ne prouve rien.
    rapport = write_simulation_candidates(parse_metadata(_V2))
    assert rapport["service_declares_restrictions"] is False
    assert [c["entity_set"] for c in rapport["candidates"]] == ["Carriers"]
    assert rapport["candidates"][0]["declared"] == []


def test_service_v4_ne_declare_rien_en_attributs_sap():
    # Les restrictions v4 s'expriment en Org.OData.Capabilities.V1 : la
    # fonction ne doit pas faire semblant de les avoir lues.
    rapport = write_simulation_candidates(parse_metadata(_V4))
    assert rapport["service_declares_restrictions"] is False


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
