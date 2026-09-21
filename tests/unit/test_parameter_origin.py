"""Tests hors SAP de `sapfx_common.parameter_origin` (convention #5).

Le sujet : d'où vient la valeur effective d'un paramètre de profil. Le canal
sans écran rend l'effectif sans dire s'il vient du profil ou du noyau ; le
rapport d'écran porte les deux colonnes. Chaque test fige une mesure du
2026-09-14 sur ABAP Platform 2023.
"""
import pytest

from sapfx_common.parameter_origin import (
    PROFILE_VALUE_WIDTH,
    classify_parameter_origin,
    compare_channels,
    discriminating_parameter_names,
    looks_truncated,
    proven_truncations,
    summarize_origins,
    truncated_profile_names,
)


# --------------------------------------------------------------------- #
# Les trois sélecteurs promus depuis la suite (convention #12)
# --------------------------------------------------------------------- #
_LIGNES = [
    {"NAME": "court", "USER_VALUE": "abc", "DEFAULT_VALUE": "abc"},
    {"NAME": "coupe", "USER_VALUE": "x" * PROFILE_VALUE_WIDTH,
     "DEFAULT_VALUE": ""},
    {"NAME": "discriminant", "USER_VALUE": "12", "DEFAULT_VALUE": "10"},
    {"NAME": "noyau", "USER_VALUE": "", "DEFAULT_VALUE": "5"},
]


def test_les_valeurs_a_la_largeur_de_colonne_sont_selectionnees():
    assert truncated_profile_names(_LIGNES) == ["coupe"]


def test_seuls_les_parametres_dont_le_profil_differe_discriminent():
    """Un paramètre dont le profil répète le défaut ne prouve rien : quelle
    que soit la source suivie, la valeur est la même."""
    assert discriminating_parameter_names(_LIGNES) == ["coupe", "discriminant"]
    assert discriminating_parameter_names(_LIGNES, limit=1) == ["coupe"]


def test_la_troncature_se_prouve_par_prefixe_et_longueur():
    """Le distinguo imposé par la revue : sans lui, un scénario ne peut que
    relire son propre critère de sélection, ce qui ne peut pas échouer."""
    prouves = proven_truncations(
        _LIGNES, {"coupe": "x" * PROFILE_VALUE_WIDTH + "SUITE"})
    assert prouves == ["coupe"]


def test_une_valeur_identique_n_est_pas_une_troncature():
    assert proven_truncations(_LIGNES,
                              {"coupe": "x" * PROFILE_VALUE_WIDTH}) == []


def test_une_valeur_differente_n_est_pas_une_troncature():
    assert proven_truncations(_LIGNES, {"coupe": "TOUT AUTRE CHOSE"}) == []


def test_un_parametre_absent_de_l_ecran_ne_prouve_rien():
    assert proven_truncations(_LIGNES, {"inconnu": "quoi que ce soit"}) == []


def test_valeur_posee_dans_le_profil_est_une_decision_humaine():
    fiche = classify_parameter_origin("login/min_password_lng", "12", "12", "10")
    assert fiche["origin"] == "profile"
    assert fiche["comparable"] is True


def test_valeur_absente_du_profil_vient_du_noyau():
    """Le résultat de la cible : sur les 42 paramètres de sécurité audités,
    39 portent leur valeur par défaut et les 3 déclarés au profil y répètent
    exactement le défaut, donc aucun n'y est modifié."""
    fiche = classify_parameter_origin("login/min_password_lng", "10", "", "10")
    assert fiche["origin"] == "kernel"
    assert fiche["profile"] is None


def test_effectif_qui_ne_suit_ni_profil_ni_defaut_est_signale():
    fiche = classify_parameter_origin("x", "99", "12", "10")
    assert fiche["origin"] == "divergent"


def test_effectif_non_mesure_n_est_pas_un_verdict_d_origine():
    fiche = classify_parameter_origin("x", None, "12", "10")
    assert fiche["origin"] == "not_measured"
    assert fiche["effective"] is None


def test_parametre_sans_nom_refuse():
    with pytest.raises(ValueError, match="nom"):
        classify_parameter_origin("", "1", "", "1")


# --------------------------------------------------------------------- #
# La troncature silencieuse de la colonne de profil
# --------------------------------------------------------------------- #
def test_une_valeur_a_la_largeur_de_colonne_est_suspecte():
    assert looks_truncated("x" * PROFILE_VALUE_WIDTH) is True
    assert looks_truncated("x" * (PROFILE_VALUE_WIDTH - 1)) is False
    assert looks_truncated("") is False


def test_une_valeur_tronquee_ne_fabrique_pas_un_faux_ecart():
    """Le piège mesuré : la colonne de profil est coupée à 60 caractères sans
    le dire, et la confronter à la valeur complète de l'autre canal invente un
    écart. Ici l'effectif COMMENCE par la valeur coupée, donc l'origine reste
    le profil."""
    profil = "immediate /usr/sap/A4H/SYS/exe/uc/linuxx86_64/sapcpe pf=/usr"
    effectif = profil + "/sap/A4H/SYS/profile/A4H_D00_vhcala4hci"
    fiche = classify_parameter_origin("Execute_00", effectif, profil, "")
    assert len(profil) == PROFILE_VALUE_WIDTH
    assert fiche["truncated"] is True
    assert fiche["comparable"] is False
    assert fiche["origin"] == "profile"


def test_une_valeur_tronquee_qui_ne_prefixe_pas_reste_divergente():
    """Contre-épreuve : la tolérance ne doit pas absoudre n'importe quoi."""
    profil = "A" * PROFILE_VALUE_WIDTH
    fiche = classify_parameter_origin("x", "B" * 80, profil, "")
    assert fiche["origin"] == "divergent"


# --------------------------------------------------------------------- #
# Résumés et croisement
# --------------------------------------------------------------------- #
def test_resume_isole_ce_qu_un_audit_veut_voir():
    """`profile_backed` est la liste des décisions humaines. Sur la cible elle
    est VIDE pour le périmètre de sécurité, et c'est le résultat."""
    fiches = [
        classify_parameter_origin("a", "1", "", "1"),
        classify_parameter_origin("b", "2", "", "2"),
        classify_parameter_origin("c", "9", "9", "3"),
    ]
    resume = summarize_origins(fiches)
    assert resume["total"] == 3
    assert resume["kernel_backed"] == ["a", "b"]
    assert resume["profile_backed"] == ["c"]
    assert resume["divergent"] == []


def test_pose_dans_le_profil_n_est_pas_modifie_par_le_profil():
    """La distinction qui porte le sens d'un audit, et que le run live a fait
    apparaître : les trois seuls paramètres de sécurité déclarés dans le
    profil de la cible y portent EXACTEMENT la valeur du défaut (deux chemins
    de fichiers de contrôle d'accès et un indicateur de compatibilité), donc
    aucun ne durcit ni n'affaiblit quoi que ce soit."""
    repete = classify_parameter_origin("gw/sec_info", "/p/secinfo",
                                       "/p/secinfo", "/p/secinfo")
    modifie = classify_parameter_origin("x", "12", "12", "10")
    assert repete["origin"] == "profile"
    assert repete["profile_changes_value"] is False
    assert modifie["profile_changes_value"] is True


def test_resume_separe_ce_que_le_profil_modifie_de_ce_qu_il_repete():
    fiches = [
        classify_parameter_origin("repete", "1", "1", "1"),
        classify_parameter_origin("modifie", "9", "9", "1"),
        classify_parameter_origin("noyau", "1", "", "1"),
    ]
    resume = summarize_origins(fiches)
    assert resume["profile_backed"] == ["modifie", "repete"]
    assert resume["profile_changing"] == ["modifie"]
    assert resume["profile_redundant"] == ["repete"]


def test_resume_est_trie_donc_comparable():
    a = summarize_origins([classify_parameter_origin(n, "1", "", "1")
                           for n in ("b", "a")])
    b = summarize_origins([classify_parameter_origin(n, "1", "", "1")
                           for n in ("a", "b")])
    assert a == b


def test_croisement_des_deux_canaux():
    ecran = [
        {"NAME": "login/min_password_lng", "USER_VALUE": "",
         "DEFAULT_VALUE": "10"},
        {"NAME": "rdisp/gui_auto_logout", "USER_VALUE": "",
         "DEFAULT_VALUE": "3600"},
        {"NAME": "DIR_HOME", "USER_VALUE": "/tmp", "DEFAULT_VALUE": "/x"},
    ]
    effectif = {"login/min_password_lng": "10", "rdisp/gui_auto_logout": "3600",
                "DIR_HOME": "/tmp"}
    resume = compare_channels(ecran, effectif)
    assert resume["kernel_backed"] == ["login/min_password_lng",
                                       "rdisp/gui_auto_logout"]
    assert resume["profile_backed"] == ["DIR_HOME"]
    assert resume["missing_from_screen"] == []


def test_croisement_signale_un_parametre_absent_du_rapport_ecran():
    """Une absence de mesure n'est pas une absence de problème : le nom est
    RENDU plutôt qu'omis du résumé."""
    resume = compare_channels([{"NAME": "a", "USER_VALUE": "",
                                "DEFAULT_VALUE": "1"}],
                              {"a": "1", "inconnu": "2"})
    assert resume["missing_from_screen"] == ["inconnu"]
    assert resume["total"] == 1


def test_croisement_restreint_au_perimetre_demande():
    ecran = [{"NAME": "a", "USER_VALUE": "", "DEFAULT_VALUE": "1"},
             {"NAME": "b", "USER_VALUE": "", "DEFAULT_VALUE": "2"}]
    resume = compare_channels(ecran, {"a": "1", "b": "2"}, names=["a"])
    assert resume["total"] == 1 and resume["kernel_backed"] == ["a"]
