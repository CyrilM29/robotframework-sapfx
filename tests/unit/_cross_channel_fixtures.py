"""Doublures et helpers partages des tests du croisement ECC/API (logique pure cross_channel) (extraits, convention #13)."""
# ruff: noqa: F401  (surface re-exportee vers les fichiers de tests decoupes)
import json


import pytest


from sapfx_common import cross_channel as cc


PRODUCT_PROPERTIES = {
    "Category": {"type": "Edm.String"},
    "ChangedAt": {"type": "Edm.DateTime"},
    "CreatedAt": {"type": "Edm.DateTime"},
    "CurrencyCode": {"type": "Edm.String"},
    "Depth": {"type": "Edm.Decimal"},
    "Description": {"type": "Edm.String"},
    "DescriptionLanguage": {"type": "Edm.String"},
    "DimUnit": {"type": "Edm.String"},
    "Height": {"type": "Edm.Decimal"},
    "MeasureUnit": {"type": "Edm.String"},
    "Name": {"type": "Edm.String"},
    "NameLanguage": {"type": "Edm.String"},
    "Price": {"type": "Edm.Decimal"},
    "ProductID": {"type": "Edm.String"},
    "SupplierID": {"type": "Edm.String"},
    "SupplierName": {"type": "Edm.String"},
    "TaxTarifCode": {"type": "Edm.Byte"},
    "TypeCode": {"type": "Edm.String"},
    "WeightMeasure": {"type": "Edm.Decimal"},
    "WeightUnit": {"type": "Edm.String"},
    "Width": {"type": "Edm.Decimal"},
}


SNWD_PD_FIELDS = [
    {"FIELDNAME": name, "POSITION": "%04d" % index,
     "KEYFLAG": "X" if name in ("CLIENT", "NODE_KEY") else "",
     "DATATYPE": "CLNT" if name == "CLIENT" else "CHAR"}
    for index, name in enumerate(
        [".INCLUDE", "CATEGORY", "CHANGED_AT", "CHANGED_BY", "CLIENT",
         "CREATED_AT", "CREATED_BY", "CURRENCY_CODE", "DEPTH", "DESC_GUID",
         "DIM_UNIT", "DUMMY_FIELD_PD", "HEIGHT", "MEASURE_UNIT", "NAME_GUID",
         "NODE_KEY", "PRICE", "PRODUCT_ID", "PRODUCT_PIC_URL",
         "SUPPLIER_GUID", "TAX_TARIF_CODE", "TYPE_CODE", "WEIGHT_MEASURE",
         "WEIGHT_UNIT", "WIDTH"], start=1)]


PARTNER_PROPERTIES = {
    "Address": {"type": "GWSAMPLE_BASIC.CT_Address"},
    "BusinessPartnerID": {"type": "Edm.String"},
    "BusinessPartnerRole": {"type": "Edm.String"},
    "ChangedAt": {"type": "Edm.DateTime"},
    "CompanyName": {"type": "Edm.String"},
    "CreatedAt": {"type": "Edm.DateTime"},
    "CurrencyCode": {"type": "Edm.String"},
    "EmailAddress": {"type": "Edm.String"},
    "FaxNumber": {"type": "Edm.String"},
    "LegalForm": {"type": "Edm.String"},
    "PhoneNumber": {"type": "Edm.String"},
    "WebAddress": {"type": "Edm.String"},
}


SNWD_BPA_FIELDS = [
    {"FIELDNAME": name, "POSITION": "%04d" % index, "KEYFLAG": "",
     "DATATYPE": "CLNT" if name == "CLIENT" else "CHAR"}
    for index, name in enumerate(
        [".INCLUDE", "ADDRESS_GUID", "APPROVAL_STATUS", "BP_ID", "BP_ROLE",
         "CHANGED_AT", "CHANGED_BY", "CLIENT", "COMPANY_NAME", "CREATED_AT",
         "CREATED_BY", "CURRENCY_CODE", "DUMMY_FIELD_BPA", "EMAIL_ADDRESS",
         "FAX_NUMBER", "LEGAL_FORM", "NODE_KEY", "PHONE_NUMBER",
         "WEB_ADDRESS"], start=1)]


SE16_AFFORDANCES = "\n".join([
    "* NODE_KEY\twnd[0]/usr/txtI1-LOW\tGuiTextField\t= 000000",
    "* ?\twnd[0]/usr/txtI1-HIGH\tGuiTextField\t= ",
    "  ?\twnd[0]/usr/btn%_I1_%_APP_%-VALU_PUSH\tGuiButton",
    "* BP_ROLE\twnd[0]/usr/ctxtI2-LOW\tGuiCTextField\t= ",
    "* EMAIL_ADDRESS\twnd[0]/usr/txtI3-LOW\tGuiTextField\t= ",
    "* Maximum No. of Hits\twnd[0]/usr/txtMAX_SEL\tGuiTextField\t= 200",
])


def _metadata(entity_sets):
    return {"version": "2.0", "service_path": "/svc", "entity_sets": entity_sets}


CATALOG = [
    {"id": "ZGWSAMPLE_BASIC_0001", "title": "GWSAMPLE_BASIC",
     "technical_name": "ZGWSAMPLE_BASIC",
     "service_url": "http://h:50000/sap/opu/odata/iwbep/GWSAMPLE_BASIC"},
    {"id": "ZSEPMRA_SHOP_0001", "title": "SEPMRA_SHOP",
     "technical_name": "ZSEPMRA_SHOP",
     "service_url": "http://h:50000/sap/opu/odata/sap/SEPMRA_SHOP"},
]


def _contract(*records):
    return {"service_path": "/svc", "entity_sets": list(records)}


def _record(name, addressable=True):
    return {"entity_set": name, "addressable": addressable, "keys": [],
            "declared_capabilities": [], "draft_enabled": False,
            "property_count": 0, "label": None, "creatable": True,
            "updatable": True, "deletable": True}


CANDIDATES = {"service_declares_restrictions": True, "candidates": [
    {"entity_set": "ProductSet", "addressable": True,
     "allowed": ["creatable", "updatable", "deletable"], "declared": [],
     "evidence": "default", "keys": ["ProductID"]},
    {"entity_set": "SalesOrderSet", "addressable": True,
     "allowed": ["creatable", "deletable"], "declared": ["updatable"],
     "evidence": "declared", "keys": ["SalesOrderID"]},
]}


def _artifact(target="a4h", services=("/svc",), observed="2026-08-22T10:00:00+00:00"):
    scope = cc.validate_cross_channel_scope(list(services), "001", "001",
                                            10, 5, 2)
    contract = cc.describe_service_contract(_metadata({
        "ProductSet": {"keys": ["ProductID"], "properties": {},
                       "capabilities": {"addressable": True},
                       "declared_capabilities": []}}), 10)
    probes = cc.classify_entity_set_probes(
        contract, [{"entity_set": "ProductSet", "status": 200, "count": 205,
                    "error_code": ""}])
    couple = cc.build_couple_verdict(
        {"entity_set": "ProductSet", "service": "/svc", "table": "SNWD_PD",
         "expected": "equal"}, 205, 205)
    field = cc.compare_odata_properties_with_ddic_fields(
        PRODUCT_PROPERTIES, SNWD_PD_FIELDS)
    contracts = [{"entity_set": "ProductSet", "service": "/svc",
                  "table": "SNWD_PD", "summary": field["summary"]}]
    return cc.build_cross_channel_artifact(
        target, scope, observed,
        catalog=cc.catalog_coverage(list(services), []),
        services=[contract], probes=probes, couples=[couple],
        contracts=contracts,
        tables=[cc.describe_ddic_table("SNWD_PD", SNWD_PD_FIELDS, 205)],
        candidates=cc.shortlist_write_candidates(CANDIDATES))
