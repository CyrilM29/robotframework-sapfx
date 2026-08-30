"""Tests hors SAP de la **classification et des verdicts** de posture de
sécurité : ``sapfx_common.security_baseline`` (logique pure, convention #5).

L'artefact, la comparaison et le rapport sont dans le fichier voisin
``test_security_posture_artifact.py`` (convention #13).

Chaque propriété verrouillée ici a sa contre-épreuve, parce qu'un garde qui ne
peut pas échouer est pire qu'absent. Les quatre qui comptent :

- **Le piège central** : le module ABAP rend ``RC = 4`` et une chaîne VIDE pour
  un paramètre sans valeur effective, indiscernable d'un paramètre légitimement
  vide. Les deux cas sont testés en COUPLE : pris séparément, la distinction
  resterait cosmétique.
- ``not_measurable`` n'est jamais un succès et reste distinct de
  ``deviation`` : les deux ne se corrigent pas au même endroit (le contrôle
  contre le système).
- Un comparateur numérique sur une valeur non numérique LÈVE en nommant le
  contrôle : il ne fabrique pas un verdict.
- Un verrou d'utilisateur est un MASQUE de bits, pas une énumération, et un
  masque illisible ou non cartographié reste verrouillé.

Le vocabulaire de ``unknown`` n'est PAS asserté ici : ce statut couvre deux
cas que le canal ne sépare pas (paramètre absent de la release, ou connu et
non positionné), donc seuls le statut et ``value is None`` sont des propriétés.
"""
import pytest

from sapfx_common import security_baseline

#: Le couple (comparateur, attendu plausible) de CHAQUE comparateur admis. Le
#: test de couverture juste en dessous fait échouer l'ajout d'un comparateur
#: qui n'aurait pas sa contre-épreuve « jamais conforme sur une mesure
#: absente ».
_CAS_PAR_COMPARATEUR = [
    ("equals", "3"),
    ("at_least", "8"),
    ("at_most", "5"),
    ("one_of", ["A", "B"]),
    ("enabled", "1"),
    ("disabled", "0"),
]


# --- classify_parameter : le piège central ----------------------------------

def test_un_parametre_sans_valeur_effective_rend_unknown_et_jamais_une_chaine_vide():
    fiche = security_baseline.classify_parameter("login/inexistant", 4, "")
    assert fiche == {"name": "login/inexistant", "status": "unknown",
                     "value": None}
    assert fiche["value"] is None


def test_un_parametre_legitimement_vide_reste_defined():
    """Le symétrique du précédent, et c'est le COUPLE qui prouve la
    distinction : le système rend la même chaîne vide dans les deux cas, seul
    le code de retour les sépare."""
    fiche = security_baseline.classify_parameter("login/ticket_only_by_http",
                                                 0, "")
    assert fiche == {"name": "login/ticket_only_by_http", "status": "defined",
                     "value": ""}


@pytest.mark.parametrize("code", [4, "4", 8, "8", -1, 2])
def test_tout_code_de_retour_non_nul_rend_unknown(code):
    fiche = security_baseline.classify_parameter("login/x", code, "valeur")
    assert fiche["status"] == "unknown" and fiche["value"] is None


@pytest.mark.parametrize("code", [None, "oui", "RC=0", object()])
def test_un_code_de_retour_illisible_ne_fabrique_pas_une_mesure(code):
    # Le repli sûr : si le code de retour ne se lit pas, la lecture ne peut
    # pas être présentée comme une mesure.
    fiche = security_baseline.classify_parameter("login/x", code, "8")
    assert fiche["status"] == "unknown" and fiche["value"] is None


@pytest.mark.parametrize("code", [0, "0", " 0 "])
def test_un_code_de_retour_nul_vaut_mesure(code):
    fiche = security_baseline.classify_parameter("login/x", code, "8")
    assert fiche == {"name": "login/x", "status": "defined", "value": "8"}


@pytest.mark.parametrize("code", [None, "", "   "])
def test_un_code_de_retour_absent_est_un_refus_et_jamais_une_mesure(code):
    # Le repli sûr, dans le sens qui compte : un appelant qui ne transmet pas
    # le code de retour ne doit pas fabriquer une mesure à partir de rien.
    # Avant correction, la chaîne vide passait pour un zéro et rendait
    # « defined », alors que None rendait bien « unknown » : deux absences
    # traitées à l'opposé l'une de l'autre.
    fiche = security_baseline.classify_parameter("login/x", code, "8")
    assert fiche == {"name": "login/x", "status": "unknown", "value": None}


def test_le_nom_est_depouille_et_la_valeur_normalisee_en_chaine():
    fiche = security_baseline.classify_parameter(
        "  login/fails_to_session_end  ", 0, 3)
    assert fiche == {"name": "login/fails_to_session_end",
                     "status": "defined", "value": "3"}


def test_la_casse_du_nom_est_preservee():
    # Le canal est sensible à la casse : normaliser ici rendrait tout le lot
    # sans valeur effective, avec un code de retour parfaitement plausible.
    fiche = security_baseline.classify_parameter("Login/Min_Password_Lng", 0, "8")
    assert fiche["name"] == "Login/Min_Password_Lng"


def test_un_nom_de_parametre_vide_est_refuse():
    with pytest.raises(ValueError, match="vide"):
        security_baseline.classify_parameter("   ", 0, "8")


# --- classify_user_lock : un masque de bits, pas une énumération ------------

def test_un_verrou_cumule_rend_les_deux_causes_jamais_inconnu():
    # 96 = 32 + 64 : le cas qu'une table de correspondance plate rendrait
    # « inconnu » alors qu'il est parfaitement normal.
    assert security_baseline.classify_user_lock(96) == {
        "uflag": 96, "locked": True,
        "reasons": ["locked_by_admin", "locked_by_failed_logons"]}


@pytest.mark.parametrize("uflag,attendu", [
    (0, []),
    ("0", []),
    ("", []),
    (32, ["locked_by_admin"]),
    (64, ["locked_by_failed_logons"]),
    ("64", ["locked_by_failed_logons"]),
    (128, ["locked_globally"]),
    (224, ["locked_by_admin", "locked_by_failed_logons", "locked_globally"]),
])
def test_les_bits_du_masque_sont_lus_un_a_un(uflag, attendu):
    verdict = security_baseline.classify_user_lock(uflag)
    assert verdict["reasons"] == attendu
    assert verdict["locked"] is bool(attendu)


def test_chaque_bit_declare_produit_sa_propre_cause():
    # Dérivé de LOCK_FLAGS : un bit ajouté au barème sans être lu par le
    # masque fait échouer ce test.
    for bit, cause in security_baseline.LOCK_FLAGS:
        verdict = security_baseline.classify_user_lock(bit)
        assert verdict["reasons"] == [cause]
        assert verdict["locked"] is True


def test_un_bit_non_cartographie_reste_verrouille():
    # Le repli sûr : un masque que le barème ne connaît pas ne peut pas faire
    # passer un compte pour actif.
    seul = security_baseline.classify_user_lock(1)
    assert seul == {"uflag": 1, "locked": True, "reasons": ["unmapped_bits"]}
    melange = security_baseline.classify_user_lock(33)
    assert melange["locked"] is True
    assert melange["reasons"] == ["locked_by_admin", "unmapped_bits"]


@pytest.mark.parametrize("brut", [None, "X", "12 34", "0x40"])
def test_un_uflag_illisible_ne_rend_jamais_locked_faux(brut):
    verdict = security_baseline.classify_user_lock(brut)
    assert verdict["locked"] is True
    assert verdict["reasons"] == ["unreadable"]


# --- evaluate_control : non mesuré n'est pas non conforme -------------------

def test_le_bareme_de_comparateurs_est_couvert_en_entier():
    assert [c for c, _ in _CAS_PAR_COMPARATEUR] == list(
        security_baseline.COMPARISONS)


@pytest.mark.parametrize("comparaison,attendu", _CAS_PAR_COMPARATEUR)
def test_une_mesure_absente_n_est_jamais_conforme(comparaison, attendu):
    """Aucun comparateur ne peut rendre ``compliant`` sur un paramètre resté
    sans valeur effective. Celui qui mord vraiment est ``enabled`` : sans la
    garde, il lit le ``None`` d'une mesure absente comme une valeur non nulle
    et déclare le contrôle conforme, exactement le vert-et-faux visé."""
    verdict = security_baseline.evaluate_control(
        {"key": "k", "parameter": "login/x", "comparison": comparaison,
         "expected": attendu},
        {"name": "login/x", "status": "unknown", "value": None})
    assert verdict["verdict"] == "not_measurable"
    assert verdict["measured"] is None
    assert verdict["reason"]


def test_un_parametre_sans_valeur_ne_peut_pas_passer_pour_active():
    # Le piège central bout en bout : la mesure réelle et la faute de frappe
    # arrivent avec la même apparence, un seul des deux verdicts est un
    # jugement.
    controle = {"key": "snc", "parameter": "snc/enable",
                "comparison": "enabled", "expected": "1"}
    mesure = security_baseline.evaluate_control(
        controle, security_baseline.classify_parameter("snc/enable", 0, "1"))
    assert mesure["verdict"] == "compliant"
    faute = security_baseline.evaluate_control(
        controle, security_baseline.classify_parameter("snc/enabl", 4, ""))
    assert faute["verdict"] == "not_measurable"


def test_un_ecart_et_une_mesure_absente_ne_se_confondent_pas():
    controle = {"key": "longueur", "parameter": "login/min_password_lng",
                "comparison": "at_least", "expected": "8", "severity": "high"}
    ecart = security_baseline.evaluate_control(
        controle, security_baseline.classify_parameter(
            "login/min_password_lng", 0, "3"))
    absente = security_baseline.evaluate_control(
        controle, security_baseline.classify_parameter(
            "login/min_password_lng", 4, ""))
    assert ecart["verdict"] == "deviation" and ecart["measured"] == "3"
    assert absente["verdict"] == "not_measurable"
    # seul le cas non mesurable porte sa cause : les deux ne se corrigent pas
    # au même endroit
    assert "reason" in absente and "reason" not in ecart


@pytest.mark.parametrize("comparaison,attendu,mesure,verdict", [
    ("equals", "3", "3", "compliant"),
    ("equals", 3, "3", "compliant"),
    ("equals", "3", "4", "deviation"),
    ("at_least", "8", "8", "compliant"),
    ("at_least", "8", "12", "compliant"),
    ("at_least", "8", "3", "deviation"),
    ("at_most", "5", "5", "compliant"),
    ("at_most", "5", "6", "deviation"),
    ("one_of", "A,B", "B", "compliant"),
    ("one_of", ["A", "B"], "C", "deviation"),
    ("enabled", "1", "1", "compliant"),
    ("enabled", "1", "0", "deviation"),
    ("enabled", "1", "OFF", "deviation"),
    ("enabled", "1", "", "deviation"),
    ("disabled", "0", "OFF", "compliant"),
    ("disabled", "0", "off", "compliant"),
    ("disabled", "0", "N", "compliant"),
    ("disabled", "0", "", "compliant"),
    ("disabled", "0", "1", "deviation"),
])
def test_chaque_comparateur_tranche_comme_annonce(comparaison, attendu, mesure,
                                                  verdict):
    rendu = security_baseline.evaluate_control(
        {"key": "k", "parameter": "p", "comparison": comparaison,
         "expected": attendu},
        {"name": "p", "status": "defined", "value": mesure})
    assert rendu["verdict"] == verdict


def test_un_comparateur_numerique_sur_une_valeur_non_numerique_leve():
    """Comparer numériquement un paramètre qui vaut ``OFF`` ne rend pas le
    système non conforme : cela rend le CONTRÔLE faux. L'erreur nomme le
    contrôle, son comparateur et la valeur reçue, plutôt que d'inventer un
    verdict."""
    with pytest.raises(ValueError, match="entier") as erreur:
        security_baseline.evaluate_control(
            {"key": "snc", "parameter": "snc/enable",
             "comparison": "at_least", "expected": "1"},
            security_baseline.classify_parameter("snc/enable", 0, "OFF"))
    message = str(erreur.value)
    assert "snc" in message and "at_least" in message
    assert "'OFF'" in message and "la valeur mesurée" in message
    assert "mal déclaré" in message


def test_un_attendu_non_numerique_est_signale_du_cote_du_controle():
    with pytest.raises(ValueError, match="attendu") as erreur:
        security_baseline.evaluate_control(
            {"key": "longueur", "parameter": "login/min_password_lng",
             "comparison": "at_most", "expected": "huit"},
            {"name": "login/min_password_lng", "status": "defined",
             "value": "8"})
    assert "'huit'" in str(erreur.value)


def test_un_comparateur_inconnu_est_refuse_en_listant_les_admis():
    with pytest.raises(ValueError, match="inconnu") as erreur:
        security_baseline.evaluate_control(
            {"key": "k", "comparison": "matches", "expected": "x"},
            {"name": "k", "status": "defined", "value": "x"})
    message = str(erreur.value)
    for admis in security_baseline.COMPARISONS:
        assert admis in message


def test_un_controle_sans_cle_est_refuse():
    with pytest.raises(ValueError, match="clé"):
        security_baseline.evaluate_control(
            {"comparison": "equals", "expected": "1"},
            {"name": "p", "status": "defined", "value": "1"})


def test_one_of_normalise_l_attendu_en_liste_lisible():
    verdict = security_baseline.evaluate_control(
        {"key": "k", "parameter": "p", "comparison": "one_of",
         "expected": "A, B"},
        {"name": "p", "status": "defined", "value": "A"})
    assert verdict["expected"] == ["A", "B"]


def test_la_severite_par_defaut_et_la_justification_optionnelle():
    minimal = security_baseline.evaluate_control(
        {"key": "k", "parameter": "p", "comparison": "equals", "expected": "1"},
        {"name": "p", "status": "defined", "value": "1"})
    assert minimal["severity"] == "medium" and "rationale" not in minimal
    complet = security_baseline.evaluate_control(
        {"key": "k", "parameter": "p", "comparison": "equals", "expected": "1",
         "severity": "high", "rationale": "note SAP 2467"},
        {"name": "p", "status": "defined", "value": "1"})
    assert complet["severity"] == "high"
    assert complet["rationale"] == "note SAP 2467"


# --- evaluate_controls ------------------------------------------------------

def test_l_ordre_des_controles_est_preserve_et_l_indexation_par_parametre():
    verdicts = security_baseline.evaluate_controls(
        [{"key": "c1", "parameter": "b", "comparison": "equals",
          "expected": "2"},
         {"key": "c2", "parameter": "a", "comparison": "equals",
          "expected": "1"}],
        [{"name": "a", "status": "defined", "value": "1"},
         {"name": "b", "status": "defined", "value": "2"}])
    assert [v["key"] for v in verdicts] == ["c1", "c2"]
    assert all(v["verdict"] == "compliant" for v in verdicts)


def test_un_controle_dont_le_parametre_n_a_pas_ete_mesure_est_not_measurable():
    # Ne rien mesurer et mesurer un paramètre sans valeur laissent l'auditeur
    # dans le même état : aucun des deux n'est un succès.
    verdicts = security_baseline.evaluate_controls(
        [{"key": "absent", "parameter": "login/jamais_lu",
          "comparison": "enabled", "expected": "1"}], [])
    assert verdicts[0]["verdict"] == "not_measurable"
    assert verdicts[0]["measured"] is None


def test_un_controle_sans_parametre_prend_sa_cle_comme_parametre():
    verdicts = security_baseline.evaluate_controls(
        [{"key": "login/disable_multi_gui_login", "comparison": "equals",
          "expected": "1"}],
        [{"name": "login/disable_multi_gui_login", "status": "defined",
          "value": "1"}])
    assert verdicts[0]["parameter"] == "login/disable_multi_gui_login"
    assert verdicts[0]["verdict"] == "compliant"


# --- summarize_verdicts -----------------------------------------------------

_LOT = [
    {"key": "z_ecart", "verdict": "deviation", "severity": "high"},
    {"key": "a_ecart", "verdict": "deviation", "severity": "low"},
    {"key": "m_ecart", "verdict": "deviation", "severity": "high"},
    {"key": "ok", "verdict": "compliant", "severity": "medium"},
    {"key": "z_muet", "verdict": "not_measurable", "severity": "high"},
    {"key": "a_muet", "verdict": "not_measurable", "severity": "high"},
]


def test_le_resume_compte_par_verdict_et_par_severite_en_listes_triees():
    resume = security_baseline.summarize_verdicts(_LOT)
    assert resume == {
        "total": 6, "compliant": 1, "deviation": 3, "not_measurable": 2,
        "deviations_by_severity": {"high": 2, "low": 1},
        "deviating_keys": ["a_ecart", "m_ecart", "z_ecart"],
        "not_measurable_keys": ["a_muet", "z_muet"],
    }
    # tri stable : c'est ce dont dépend le hash de l'artefact
    assert list(resume["deviations_by_severity"]) == ["high", "low"]


def test_les_non_mesurables_ne_gonflent_pas_les_comptes_par_severite():
    # Deux contrôles muets de sévérité « high » sont dans le lot : les compter
    # comme des écarts ferait passer un contrôle mal écrit pour un système mal
    # configuré.
    resume = security_baseline.summarize_verdicts(_LOT)
    assert resume["deviations_by_severity"]["high"] == 2
    assert resume["not_measurable"] == 2


def test_un_lot_vide_resume_a_zero():
    assert security_baseline.summarize_verdicts([]) == {
        "total": 0, "compliant": 0, "deviation": 0, "not_measurable": 0,
        "deviations_by_severity": {}, "deviating_keys": [],
        "not_measurable_keys": []}
