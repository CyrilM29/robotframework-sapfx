"""Croisement ECC/API : verdicts de couple, candidats d'ecriture, artefact et comparaison. Doublures dans _cross_channel_fixtures."""
from sapfx_common import cross_channel as cc
import json
import pytest

from _cross_channel_fixtures import (  # noqa: F401
    CANDIDATES,
    SE16_AFFORDANCES,
    SNWD_PD_FIELDS,
    _artifact,
    _metadata,
    _record,
)



def test_un_couple_equal_confronte_les_deux_comptes():
    verdict = cc.build_couple_verdict(
        {"entity_set": "ProductSet", "service": "/svc", "table": "SNWD_PD",
         "expected": "equal"}, 205, 205)
    assert verdict["verdict"] == "match"
    assert verdict["match"] is True


def test_un_couple_equal_qui_diverge_est_un_ecart():
    verdict = cc.build_couple_verdict(
        {"entity_set": "ContactSet", "table": "SNWD_CONTACT",
         "expected": "equal"}, 41, 0)
    assert verdict["verdict"] == "mismatch"
    assert verdict["match"] is False


def test_un_couple_sous_filtre_consigne_l_ecart_sans_filtre_au_lieu_de_le_masquer():
    verdict = cc.build_couple_verdict(
        {"entity_set": "SEPMRA_C_PD_Product", "table": "SNWD_PD",
         "api_filter": "IsActiveEntity eq true",
         "expected": "equal_under_filter"}, 205, 205, 214)
    assert verdict["match"] is True
    assert verdict["api_count_unfiltered"] == 214


def test_un_couple_non_comparable_n_est_jamais_asserte_en_egalite():
    verdict = cc.build_couple_verdict(
        {"entity_set": "ShoppingCarts", "expected": "not_comparable",
         "reason": "perimetre utilisateur"}, 1, None)
    assert verdict["verdict"] == "not_compared"
    assert verdict["match"] is False
    assert verdict["reason"] == "perimetre utilisateur"


def test_un_comptage_manquant_ne_devient_jamais_un_succes():
    verdict = cc.build_couple_verdict(
        {"entity_set": "X", "expected": "equal"}, 5, None)
    assert verdict["verdict"] == "not_compared"


def test_un_verdict_attendu_inconnu_est_refuse():
    with pytest.raises(ValueError):
        cc.build_couple_verdict({"entity_set": "X", "expected": "presque"})


def test_seule_une_capacite_declaree_engage_le_silence_du_service_ne_prouve_rien():
    shortlist = cc.shortlist_write_candidates(CANDIDATES)
    assert [c["entity_set"] for c in shortlist] == ["SalesOrderSet"]
    assert shortlist[0]["evidence"] == "declared"


def test_la_liste_blanche_metier_tranche_apres_la_garde_de_declaration():
    assert cc.shortlist_write_candidates(CANDIDATES, ["ProductSet"]) == []
    retenu = cc.shortlist_write_candidates(CANDIDATES, ["SalesOrderSet"])
    assert len(retenu) == 1


def test_la_liste_blanche_reste_appliquee_apres_un_premier_candidat_retenu():
    """Régression : la liste blanche ne doit pas cesser de filtrer une fois un
    candidat retenu (le filtre porte sur CHAQUE entrée, pas sur la première)."""
    candidates = {"candidates": [
        {"entity_set": "Retenu", "allowed": ["updatable"],
         "declared": ["updatable"], "evidence": "declared", "keys": ["Id"]},
        {"entity_set": "Ecarte", "allowed": ["updatable"],
         "declared": ["updatable"], "evidence": "declared", "keys": ["Id"]}]}
    shortlist = cc.shortlist_write_candidates(candidates, ["Retenu"])
    assert [c["entity_set"] for c in shortlist] == ["Retenu"]


def test_la_reversibilite_ne_se_deduit_jamais_d_une_declaration():
    shortlist = cc.shortlist_write_candidates(CANDIDATES)
    assert shortlist[0]["reversibility_observed"] == "unknown"


def test_une_capacite_autorisee_par_defaut_reste_visible_comme_telle():
    """Un entity set peut passer la garde en déclarant des RESTRICTIONS tout en
    devant sa seule capacité autorisée au silence du service : mesuré live sur
    deux candidats sur deux. La fiche le dit au lieu de le taire."""
    candidates = {"candidates": [
        {"entity_set": "Products", "addressable": True,
         "allowed": ["updatable"], "declared": ["creatable", "deletable"],
         "evidence": "declared", "keys": ["Id"]}]}
    fiche = cc.shortlist_write_candidates(candidates)[0]
    assert fiche["evidence"] == "declared"
    assert fiche["allowed"] == ["updatable"]
    assert fiche["declared_allowed"] == []


def test_une_capacite_a_la_fois_autorisee_et_declaree_est_signalee_comme_telle():
    fiche = cc.shortlist_write_candidates({"candidates": [
        {"entity_set": "Reviews", "addressable": True,
         "allowed": ["creatable", "updatable"], "declared": ["creatable"],
         "evidence": "declared", "keys": ["Id"]}]})[0]
    assert fiche["declared_allowed"] == ["creatable"]


def test_la_qualification_d_ecriture_est_atteignable_par_un_keyword():
    metadata = _metadata({
        "Reviews": {"keys": ["Id"], "properties": {},
                    "capabilities": {"addressable": True, "creatable": True,
                                     "updatable": True, "deletable": True},
                    "declared_capabilities": ["creatable"]}})
    qualified = cc.write_simulation_candidates(metadata)
    assert qualified["candidates"][0]["entity_set"] == "Reviews"
    assert qualified["service_declares_restrictions"] is True


def test_la_carte_des_criteres_se16_est_derivee_de_la_perception():
    criteria = cc.selection_criteria(SE16_AFFORDANCES)
    assert criteria == {"NODE_KEY": "wnd[0]/usr/txtI1-LOW",
                        "BP_ROLE": "wnd[0]/usr/ctxtI2-LOW",
                        "EMAIL_ADDRESS": "wnd[0]/usr/txtI3-LOW"}


def test_un_libelle_traduit_n_entre_jamais_dans_la_carte_des_criteres():
    criteria = cc.selection_criteria(SE16_AFFORDANCES)
    assert "MAXIMUM NO. OF HITS" not in criteria
    assert all(not locator.endswith("MAX_SEL") for locator in criteria.values())


def test_la_carte_ignore_les_bornes_hautes_et_les_elements_sans_libelle():
    criteria = cc.selection_criteria(SE16_AFFORDANCES)
    assert all(locator.endswith("-LOW") for locator in criteria.values())


def test_la_carte_accepte_une_liste_de_lignes():
    criteria = cc.selection_criteria(SE16_AFFORDANCES.splitlines())
    assert criteria["BP_ROLE"] == "wnd[0]/usr/ctxtI2-LOW"


def test_la_fiche_de_table_releve_la_dependance_au_mandant_et_les_cles():
    record = cc.describe_ddic_table("snwd_pd", SNWD_PD_FIELDS, 205)
    assert record["table"] == "SNWD_PD"
    assert record["client_dependent"] is True
    assert record["key_fields"] == ["CLIENT", "NODE_KEY"]
    assert record["entry_count"] == 205


def test_une_table_sans_champ_mandant_n_est_pas_declaree_dependante():
    record = cc.describe_ddic_table("T", [{"FIELDNAME": "A", "DATATYPE": "CHAR"}])
    assert record["client_dependent"] is False
    assert record["entry_count"] is None


def test_l_artefact_recalcule_son_resume_depuis_ses_sections():
    artifact = _artifact()
    assert artifact["summary"]["couples"] == 1
    assert artifact["summary"]["couples_matched"] == 1
    assert artifact["summary"]["entity_sets"] == 1
    assert artifact["summary"]["probe_verdicts"] == {"available": 1}
    assert artifact["schema_version"] == cc.SCHEMA_VERSION


def test_l_artefact_est_serialise_de_facon_deterministe():
    text = cc.cross_channel_artifact_json(_artifact())
    assert text.endswith("\n")
    assert json.loads(text)["target_id"] == "a4h"
    assert text == cc.cross_channel_artifact_json(_artifact())


def test_l_empreinte_exclut_l_horodatage():
    assert cc.cross_channel_hash(_artifact(observed="2026-01-01T00:00:00+00:00")) \
        == cc.cross_channel_hash(_artifact(observed="2030-12-31T23:59:59+00:00"))


def test_l_empreinte_change_avec_le_perimetre():
    assert cc.cross_channel_hash(_artifact()) != \
        cc.cross_channel_hash(_artifact(services=("/svc", "/autre")))


def test_les_parametres_de_campagne_font_partie_de_l_artefact():
    artifact = _artifact()
    assert artifact["scope"]["client"] == "001"
    assert artifact["scope"]["max_couples"] == 5


def test_deux_releves_identiques_ne_produisent_aucun_ecart():
    comparison = cc.compare_cross_channel_artifacts(
        _artifact(observed="2026-01-01T00:00:00+00:00"),
        _artifact(observed="2026-08-22T10:00:00+00:00"))
    assert comparison["compatible"] is True
    assert comparison["only_in_a"] == comparison["only_in_b"] == []
    assert comparison["addressability_changed"] == []
    assert comparison["volume_verdict_changed"] == []
    assert comparison["field_contract_changed"] == []
    assert comparison["common"] == 1


def test_la_comparaison_accepte_le_texte_json_d_un_fichier():
    text = cc.cross_channel_artifact_json(_artifact())
    comparison = cc.compare_cross_channel_artifacts(text, text)
    assert comparison["compatible"] is True


def test_un_texte_illisible_est_refuse_avec_sa_cause():
    with pytest.raises(ValueError) as err:
        cc.compare_cross_channel_artifacts("{pas du json", _artifact())
    assert "illisible" in str(err.value)


def test_des_perimetres_differents_marquent_la_comparaison_non_equivalente():
    comparison = cc.compare_cross_channel_artifacts(
        _artifact(), _artifact(services=("/svc", "/autre")))
    assert comparison["compatible"] is False
    assert comparison["incompatibility_reasons"] == ["scope.services diffère"]


def test_un_entity_set_apparu_ou_disparu_est_un_ecart_de_disponibilite():
    a = _artifact()
    b = _artifact()
    b["services"][0]["entity_sets"].append(_record("Nouveau"))
    comparison = cc.compare_cross_channel_artifacts(a, b)
    assert comparison["only_in_b"] == ["/svc|Nouveau"]
    assert comparison["only_in_a"] == []


def test_une_adressabilite_changee_est_un_ecart_de_disponibilite():
    a = _artifact()
    b = _artifact()
    b["services"][0]["entity_sets"][0]["addressable"] = False
    comparison = cc.compare_cross_channel_artifacts(a, b)
    assert comparison["addressability_changed"] == [
        {"entity_set": "/svc|ProductSet", "a": True, "b": False}]


def test_un_verdict_volumetrique_change_est_un_ecart_distinct():
    a = _artifact()
    b = _artifact()
    b["couples"][0]["verdict"] = "mismatch"
    comparison = cc.compare_cross_channel_artifacts(a, b)
    assert comparison["volume_verdict_changed"] == [
        {"entity_set": "ProductSet", "a": "match", "b": "mismatch"}]


def test_un_contrat_de_champs_degrade_est_un_ecart_de_schema():
    a = _artifact()
    b = _artifact()
    b["field_contracts"][0]["summary"]["matched"] = 12
    comparison = cc.compare_cross_channel_artifacts(a, b)
    assert len(comparison["field_contract_changed"]) == 1
    assert comparison["field_contract_changed"][0]["entity_set"] == "ProductSet"


def test_un_schema_different_bloque_la_comparaison():
    a = _artifact()
    b = dict(_artifact(), schema_version=99)
    with pytest.raises(ValueError):
        cc.compare_cross_channel_artifacts(a, b)


def test_le_rapport_markdown_nomme_les_cibles_et_les_ecarts():
    a = _artifact()
    b = _artifact(target="s4h")
    b["services"][0]["entity_sets"][0]["addressable"] = False
    report = cc.render_cross_channel_report(
        cc.compare_cross_channel_artifacts(a, b))
    assert "`a4h`" in report and "`s4h`" in report
    assert "adressabilité changée : 1" in report


def test_le_rapport_annonce_un_perimetre_non_equivalent():
    report = cc.render_cross_channel_report(
        cc.compare_cross_channel_artifacts(
            _artifact(), _artifact(services=("/svc", "/autre"))))
    assert "non équivalents" in report
