"""Tests hors SAP de l'**artefact de posture, de la comparaison et du
rapport** : la seconde moitié de ``sapfx_common.security_baseline``
(convention #13, la classification et les verdicts vivent dans le fichier
voisin ``test_security_baseline.py``).

Ce qui est verrouillé ici est ce qui rend une sentinelle de configuration
honnête :

- le hash ignore l'horodatage, et RIEN d'autre (deux relevés identiques à deux
  moments se reconnaissent, une seule mesure changée non) ;
- un artefact refuse une identité vide, parce que comparer deux artefacts
  anonymes revient à comparer deux inconnues ;
- un paramètre passé de mesuré à sans valeur est un CHANGEMENT, jamais une
  disparition : il est toujours contrôlé, c'est sa mesure qui a changé de
  nature ;
- le rapport nomme ce qui n'a PAS pu être mesuré AVANT les écarts.
"""
import pytest

from sapfx_common import security_baseline

_REFERENCE = [
    {"name": "login/min_password_lng", "status": "defined", "value": "8"},
    {"name": "login/fails_to_user_lock", "status": "defined", "value": "5"},
]

_IDENTITE = {"release": "758", "kernel": "793", "system_id": "A4H"}


def _artefact(readings=None, identity=None, verdicts=None, observations=None,
              generated_at="2026-08-29T10:00:00+00:00"):
    return security_baseline.posture_artifact(
        _IDENTITE if identity is None else identity,
        list(_REFERENCE) if readings is None else readings,
        [] if verdicts is None else verdicts,
        observations=observations, generated_at=generated_at)


# --- compare_posture : la sentinelle ----------------------------------------

def test_une_posture_identique_ne_derive_pas():
    assert security_baseline.compare_posture(
        list(_REFERENCE), list(_REFERENCE)) == {
        "drifted": False, "changed": [], "appeared": [], "disappeared": [],
        "unchanged": 2}


def test_un_parametre_devenu_sans_valeur_est_un_changement_pas_une_disparition():
    # Il est toujours contrôlé : c'est sa MESURE qui a changé de nature.
    courant = [{"name": "login/min_password_lng", "status": "unknown",
                "value": None}, dict(_REFERENCE[1])]
    verdict = security_baseline.compare_posture(courant, _REFERENCE)
    assert verdict["disappeared"] == []
    assert verdict["changed"] == [{
        "name": "login/min_password_lng",
        "before": {"status": "defined", "value": "8"},
        "after": {"status": "unknown", "value": None}}]
    assert verdict["drifted"] is True and verdict["unchanged"] == 1


def test_une_valeur_changee_un_ajout_et_un_retrait_sont_rendus_separement():
    courant = [{"name": "login/min_password_lng", "status": "defined",
                "value": "6"},
               {"name": "gw/reg_no_conn_info", "status": "defined",
                "value": "255"}]
    verdict = security_baseline.compare_posture(courant, _REFERENCE)
    assert [c["name"] for c in verdict["changed"]] == ["login/min_password_lng"]
    assert verdict["changed"][0]["before"]["value"] == "8"
    assert verdict["changed"][0]["after"]["value"] == "6"
    assert verdict["appeared"] == ["gw/reg_no_conn_info"]
    assert verdict["disappeared"] == ["login/fails_to_user_lock"]
    assert verdict["drifted"] is True


@pytest.mark.parametrize("courant", [
    [dict(_REFERENCE[0])],                                   # une disparition
    _REFERENCE + [{"name": "rsau/enable", "status": "defined", "value": "1"}],
    [dict(_REFERENCE[0], value="9"), dict(_REFERENCE[1])],   # une valeur
])
def test_drifted_est_vrai_des_qu_une_seule_chose_bouge(courant):
    assert security_baseline.compare_posture(courant, _REFERENCE)["drifted"]


def test_les_listes_de_la_comparaison_sont_triees():
    courant = list(_REFERENCE) + [
        {"name": "z/tardif", "status": "defined", "value": "1"},
        {"name": "a/precoce", "status": "defined", "value": "1"}]
    verdict = security_baseline.compare_posture(courant, _REFERENCE)
    assert verdict["appeared"] == ["a/precoce", "z/tardif"]


# --- posture_hash et posture_artifact ---------------------------------------

def test_le_hash_ignore_l_horodatage_et_le_hash_precedent():
    charge = {"identity": {"release": "758"}, "readings": list(_REFERENCE)}
    nu = security_baseline.posture_hash(charge)
    assert len(nu) == 64
    assert security_baseline.posture_hash(
        dict(charge, generated_at="hier", hash="peu importe")) == nu


def test_deux_artefacts_aux_memes_mesures_partagent_leur_hash():
    tot = _artefact(generated_at="2026-01-01T00:00:00+00:00")
    tard = _artefact(generated_at="2026-12-31T23:59:59+00:00")
    assert tot["generated_at"] != tard["generated_at"]
    assert tot["hash"] == tard["hash"]


def test_le_hash_change_des_qu_une_mesure_ou_l_identite_change():
    reference = _artefact()["hash"]
    modifie = _artefact(readings=[dict(_REFERENCE[0], value="12"),
                                  dict(_REFERENCE[1])])["hash"]
    assert modifie != reference
    assert _artefact(identity=dict(_IDENTITE, release="754"))["hash"] \
        != reference


def test_l_horodatage_est_optionnel():
    sans = security_baseline.posture_artifact(_IDENTITE, _REFERENCE, [])
    assert "generated_at" not in sans
    assert sans["hash"] == _artefact()["hash"]


@pytest.mark.parametrize("identite", [{}, {"release": "  ", "kernel": ""}])
def test_une_identite_vide_est_refusee(identite):
    # Comparer deux artefacts anonymes revient à comparer deux inconnues.
    with pytest.raises(ValueError, match="identité"):
        _artefact(identity=identite)


def test_les_listes_de_l_artefact_sont_triees():
    artefact = _artefact(
        readings=[{"name": "z", "status": "defined", "value": "1"},
                  {"name": "a", "status": "defined", "value": "2"}],
        verdicts=[{"key": "z", "verdict": "compliant"},
                  {"key": "a", "verdict": "compliant"}])
    assert [r["name"] for r in artefact["readings"]] == ["a", "z"]
    assert [v["key"] for v in artefact["verdicts"]] == ["a", "z"]
    assert list(artefact["identity"]) == ["kernel", "release", "system_id"]


def test_l_ordre_de_lecture_ne_change_pas_le_hash():
    # Le corollaire du tri : deux campagnes qui lisent les mêmes paramètres
    # dans un ordre différent produisent le même artefact.
    assert _artefact(readings=list(reversed(_REFERENCE)))["hash"] == \
        _artefact()["hash"]


def test_le_resume_de_l_artefact_est_recalcule_depuis_les_verdicts():
    artefact = _artefact(verdicts=[
        {"key": "a", "verdict": "deviation", "severity": "high"},
        {"key": "b", "verdict": "not_measurable", "severity": "low"}])
    assert artefact["summary"]["deviation"] == 1
    assert artefact["summary"]["not_measurable_keys"] == ["b"]


def test_les_observations_sont_optionnelles_et_serialisees_triees():
    assert "observations" not in _artefact()
    artefact = _artefact(observations={"z": 1, "a": {"c": 2, "b": 3}})
    assert list(artefact["observations"]) == ["a", "z"]
    assert list(artefact["observations"]["a"]) == ["b", "c"]


def test_l_identite_est_normalisee_en_chaines():
    artefact = _artefact(identity={"release": 758, "kernel": " 793 "})
    assert artefact["identity"] == {"kernel": " 793 ", "release": "758"}


# --- render_posture_report --------------------------------------------------

_VERDICTS_RAPPORT = [
    {"key": "a", "parameter": "login/min_password_lng", "verdict": "deviation",
     "severity": "low", "measured": "3", "comparison": "at_least",
     "expected": "8"},
    {"key": "b", "parameter": "gw/reg_no_conn_info", "verdict": "deviation",
     "severity": "high", "measured": "0", "comparison": "equals",
     "expected": "255"},
    {"key": "c", "parameter": "login/absent_ici", "verdict": "not_measurable",
     "severity": "high", "measured": None, "reason": "aucune valeur effective"},
]


def test_le_rapport_nomme_les_non_mesurables_avant_les_ecarts():
    # Un auditeur qui lit une liste d'écarts sans savoir combien de contrôles
    # sont restés muets se croit devant un système presque conforme.
    rapport = security_baseline.render_posture_report(
        _artefact(verdicts=_VERDICTS_RAPPORT))
    assert rapport.index("Non mesurables") < rapport.index("## Écarts")
    assert "login/absent_ici" in rapport
    assert "**3 contrôles** : 0 conformes, 2 écarts, 1 non mesurables." \
        in rapport


def test_les_ecarts_du_rapport_sont_ordonnes_par_severite():
    rapport = security_baseline.render_posture_report(
        _artefact(verdicts=_VERDICTS_RAPPORT))
    assert rapport.index("gw/reg_no_conn_info") < rapport.index(
        "login/min_password_lng")


def test_le_rapport_porte_l_identite_de_la_cible():
    rapport = security_baseline.render_posture_report(_artefact())
    assert "| release | 758 |" in rapport
    assert "| kernel | 793 |" in rapport


def test_un_rapport_sans_ecart_ni_muet_le_dit():
    rapport = security_baseline.render_posture_report(_artefact(verdicts=[
        {"key": "a", "parameter": "login/x", "verdict": "compliant"}]))
    assert "Aucun écart" in rapport
    assert "## Écarts" not in rapport and "Non mesurables" not in rapport
