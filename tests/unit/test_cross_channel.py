"""Croisement ECC/API : perimetre, catalogue, normalisation, contrat de service, sondes. Doublures dans _cross_channel_fixtures (convention #13)."""
from sapfx_common import cross_channel as cc
import pytest

from _cross_channel_fixtures import (  # noqa: F401
    CATALOG,
    PARTNER_PROPERTIES,
    PRODUCT_PROPERTIES,
    SNWD_BPA_FIELDS,
    SNWD_PD_FIELDS,
    _contract,
    _metadata,
    _record,
)



def test_le_perimetre_est_normalise_deduplique_et_trie():
    scope = cc.validate_cross_channel_scope(
        ["/b ", "/a", "/b"], "001", "001", 10, 5, 2)
    assert scope["services"] == ["/a", "/b"]
    assert scope["client"] == "001"
    assert scope["max_entity_sets"] == 10


def test_un_service_seul_compte_pour_un_service_pas_pour_ses_caracteres():
    scope = cc.validate_cross_channel_scope("/svc", "001", "001", 1, 1, 1)
    assert scope["services"] == ["/svc"]


def test_des_mandants_divergents_refusent_l_execution():
    with pytest.raises(ValueError) as err:
        cc.validate_cross_channel_scope(["/svc"], "001", "002", 1, 1, 1)
    assert "Mandants divergents" in str(err.value)
    assert "001" in str(err.value) and "002" in str(err.value)


def test_un_mandant_absent_refuse_l_execution_au_lieu_de_supposer():
    with pytest.raises(ValueError):
        cc.validate_cross_channel_scope(["/svc"], "001", "", 1, 1, 1)


def test_un_perimetre_vide_ou_non_borne_est_refuse():
    with pytest.raises(ValueError):
        cc.validate_cross_channel_scope([], "001", "001", 1, 1, 1)
    with pytest.raises(ValueError):
        cc.validate_cross_channel_scope(["/svc"], "001", "001", 0, 1, 1)
    with pytest.raises(ValueError):
        cc.validate_cross_channel_scope(["/svc"], "001", "001", 1, "beaucoup", 1)


def test_le_catalogue_reconnait_un_service_par_son_chemin_publie():
    coverage = cc.catalog_coverage(
        ["/sap/opu/odata/iwbep/GWSAMPLE_BASIC"], CATALOG)
    assert coverage["published"] == ["/sap/opu/odata/iwbep/GWSAMPLE_BASIC"]
    assert coverage["missing"] == []
    assert coverage["catalog_size"] == 2


def test_un_service_du_perimetre_absent_du_catalogue_est_rapporte():
    coverage = cc.catalog_coverage(
        ["/sap/opu/odata/sap/SEPMRA_PROD_MAN"], CATALOG)
    assert coverage["missing"] == ["/sap/opu/odata/sap/SEPMRA_PROD_MAN"]
    assert coverage["published"] == []


def test_le_prefixe_z_du_nom_technique_ne_masque_pas_un_service_publie():
    catalog = [{"technical_name": "ZSEPMRA_SHOP", "service_url": ""}]
    coverage = cc.catalog_coverage(["/autre/chemin/SEPMRA_SHOP"], catalog)
    assert coverage["missing"] == []


@pytest.mark.parametrize("name, expected", [
    ("ProductID", "PRODUCT_ID"),
    ("TaxTarifCode", "TAX_TARIF_CODE"),
    ("DimUnit", "DIM_UNIT"),
    ("WebAddress", "WEB_ADDRESS"),
    ("PRODUCT_ID", "PRODUCT_ID"),
    (".INCLUDE", "INCLUDE"),
    ("", ""),
])
def test_la_normalisation_consciente_des_acronymes(name, expected):
    assert cc.normalize_identifier(name) == expected


def test_la_normalisation_naive_casse_les_acronymes_et_c_est_mesurable():
    assert cc.normalize_identifier("ProductID", acronym_aware=False) == \
        "PRODUCT_I_D"
    assert cc.normalize_identifier("ProductID") == "PRODUCT_ID"


def test_le_rapprochement_apparie_par_normalisation_et_laisse_le_reste_orphelin():
    report = cc.compare_odata_properties_with_ddic_fields(
        PRODUCT_PROPERTIES, SNWD_PD_FIELDS, keys=["ProductID"])
    assert report["summary"]["matched"] == 15
    assert report["summary"]["properties"] == 21
    assert report["unmatched_keys"] == []
    orphans = {p["property"] for p in report["unmatched_properties"]}
    assert orphans == {"Description", "DescriptionLanguage", "Name",
                       "NameLanguage", "SupplierID", "SupplierName"}
    # Les lignes techniques de la table sont orphelines côté DDIC, et ce n'est
    # pas une anomalie.
    assert ".INCLUDE" in report["unmatched_fields"]
    assert "CLIENT" in report["unmatched_fields"]


def test_les_trois_ensembles_partitionnent_les_proprietes():
    report = cc.compare_odata_properties_with_ddic_fields(
        PRODUCT_PROPERTIES, SNWD_PD_FIELDS)
    summary = report["summary"]
    assert summary["matched"] + summary["unmatched_properties"] == \
        summary["properties"]


def test_la_normalisation_naive_apparie_moins_et_perd_la_cle():
    aware = cc.compare_odata_properties_with_ddic_fields(
        PRODUCT_PROPERTIES, SNWD_PD_FIELDS, keys=["ProductID"])
    naive = cc.compare_odata_properties_with_ddic_fields(
        PRODUCT_PROPERTIES, SNWD_PD_FIELDS, keys=["ProductID"],
        acronym_aware=False)
    assert naive["summary"]["matched"] == aware["summary"]["matched"] - 1
    assert naive["unmatched_keys"] == ["ProductID"]


def test_un_renommage_metier_n_est_rattrape_que_par_un_alias_declare():
    sans = cc.compare_odata_properties_with_ddic_fields(
        PARTNER_PROPERTIES, SNWD_BPA_FIELDS, keys=["BusinessPartnerID"])
    assert sans["summary"]["matched"] == 9
    assert sans["unmatched_keys"] == ["BusinessPartnerID"]

    avec = cc.compare_odata_properties_with_ddic_fields(
        PARTNER_PROPERTIES, SNWD_BPA_FIELDS, keys=["BusinessPartnerID"],
        aliases={"BusinessPartnerID": "BP_ID",
                 "BusinessPartnerRole": "BP_ROLE"})
    assert avec["summary"]["matched"] == 11
    assert avec["unmatched_keys"] == []
    via = {m["property"]: m["via"] for m in avec["matched"]}
    assert via["BusinessPartnerID"] == "alias"
    assert via["CompanyName"] == "normalization"


def test_une_propriete_de_type_complexe_est_classee_comme_telle():
    report = cc.compare_odata_properties_with_ddic_fields(
        PARTNER_PROPERTIES, SNWD_BPA_FIELDS)
    reasons = {p["property"]: p["reason"]
               for p in report["unmatched_properties"]}
    assert reasons["Address"] == "complex_type"


def test_un_alias_est_prioritaire_sur_la_normalisation():
    report = cc.compare_odata_properties_with_ddic_fields(
        {"Category": {"type": "Edm.String"}},
        [{"FIELDNAME": "CATEGORY"}, {"FIELDNAME": "CATEGORIE_METIER"}],
        aliases={"Category": "CATEGORIE_METIER"})
    assert report["matched"] == [{"property": "Category",
                                  "field": "CATEGORIE_METIER", "via": "alias"}]
    assert "CATEGORY" in report["unmatched_fields"]


def test_le_rapprochement_est_independant_de_l_ordre_de_lecture():
    direct = cc.compare_odata_properties_with_ddic_fields(
        PRODUCT_PROPERTIES, SNWD_PD_FIELDS)
    inverse = cc.compare_odata_properties_with_ddic_fields(
        PRODUCT_PROPERTIES, list(reversed(SNWD_PD_FIELDS)))
    assert direct == inverse


def test_une_liste_de_noms_suffit_comme_source_de_proprietes():
    report = cc.compare_odata_properties_with_ddic_fields(
        ["ProductID"], SNWD_PD_FIELDS)
    assert report["summary"]["matched"] == 1


def test_la_fiche_de_contrat_expose_capacites_declarees_et_draft():
    metadata = _metadata({
        "SEPMRA_C_PD_Product": {
            "keys": ["ProductUUID", "IsActiveEntity"],
            "label": "Produit",
            "capabilities": {"addressable": True, "creatable": False,
                             "updatable": True, "deletable": False},
            "declared_capabilities": ["creatable"],
            "properties": {"ProductUUID": {"type": "Edm.Guid"},
                           "IsActiveEntity": {"type": "Edm.Boolean"}},
        }})
    contract = cc.describe_service_contract(metadata, 10)
    record = contract["entity_sets"][0]
    assert record["draft_enabled"] is True
    assert record["declared_capabilities"] == ["creatable"]
    assert record["property_count"] == 2
    assert contract["declared"] is True
    assert contract["truncated"] is False


def test_une_borne_atteinte_rend_la_troncature_visible():
    metadata = _metadata({name: {"keys": [], "properties": {},
                                 "capabilities": {}, "declared_capabilities": []}
                          for name in ("A", "B", "C")})
    contract = cc.describe_service_contract(metadata, 2)
    assert [r["entity_set"] for r in contract["entity_sets"]] == ["A", "B"]
    assert contract["truncated"] is True


def test_un_ensemble_declare_non_adressable_et_refuse_n_est_pas_une_anomalie():
    verdicts = cc.classify_entity_set_probes(
        _contract(_record("Ok"), _record("Draft", addressable=False)),
        [{"entity_set": "Ok", "status": 200, "count": 3, "error_code": ""},
         {"entity_set": "Draft", "status": 403, "count": None,
          "error_code": "CX_SADL_GW_PRIVIL_VIOLATION"}])
    by_name = {v["entity_set"]: v for v in verdicts}
    assert by_name["Ok"]["verdict"] == "available"
    assert by_name["Draft"]["verdict"] == "declared_not_addressable"
    assert by_name["Draft"]["error_code"] == "CX_SADL_GW_PRIVIL_VIOLATION"


def test_un_ensemble_declare_adressable_et_refuse_est_l_anomalie():
    verdicts = cc.classify_entity_set_probes(
        _contract(_record("Ok")),
        [{"entity_set": "Ok", "status": 500, "count": None,
          "error_code": "SY/530"}])
    assert verdicts[0]["verdict"] == "unexpected_refusal"


def test_un_ensemble_non_sonde_n_est_jamais_confondu_avec_un_compte_nul():
    verdicts = cc.classify_entity_set_probes(_contract(_record("Ok")), [])
    assert verdicts[0]["verdict"] == "not_probed"
    assert verdicts[0]["count"] is None


def test_les_verdicts_couvrent_tous_les_ensembles_de_la_fiche():
    contract = _contract(_record("A"), _record("B"),
                         _record("C", addressable=False))
    verdicts = cc.classify_entity_set_probes(
        contract, [{"entity_set": "A", "status": 200, "count": 1,
                    "error_code": ""}])
    assert len(verdicts) == len(contract["entity_sets"])


@pytest.mark.parametrize("payload, expected", [
    ({"error": {"code": "CX_SADL_GW_PRIVIL_VIOLATION"}},
     "CX_SADL_GW_PRIVIL_VIOLATION"),
    ('{"error": {"code": "ZZ/001"}}', "ZZ/001"),
    ({"odata.error": {"code": "V4/001"}}, "V4/001"),
    ({"d": {"results": []}}, ""),
    ("205", ""),
    (None, ""),
])
def test_le_code_d_erreur_odata_est_l_ancre_independante_de_la_langue(
        payload, expected):
    assert cc.odata_error_code(payload) == expected
