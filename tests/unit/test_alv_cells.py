"""Tests hors SAP de `sapfx_common.alv_cells` (convention #5).

Le sujet : une grille SAP GUI rend du TEXTE, et tout texte n'est pas une
donnée. Un code d'icône n'est ni un booléen ni un libellé, et un libellé
d'état est une traduction. Mesures du 2026-09-14 sur ABAP Platform 2023.
"""
from sapfx_common.alv_cells import (
    cell_is_data,
    distinct_icons,
    establish_icon_meaning,
    icon_code,
    is_icon,
)


def test_un_code_d_icone_est_reconnu():
    assert icon_code("@07@") == "07"
    assert icon_code("  @5B@  ") == "5B"
    assert is_icon("@07@") is True


def test_une_valeur_ordinaire_n_est_pas_une_icone():
    for valeur in ("10", "DISABLED", "", "  ", "a@b", "@@", "email@domaine"):
        assert icon_code(valeur) is None, valeur
        assert is_icon(valeur) is False, valeur


def test_une_icone_n_est_pas_une_donnee():
    """La garde à poser avant toute comparaison entre canaux : une colonne
    d'icônes confrontée à un booléen échoue toujours, et le message accuse
    alors le système au lieu de la lecture."""
    assert cell_is_data("@07@") is False
    assert cell_is_data("") is False
    assert cell_is_data("X") is True


def test_une_colonne_a_un_seul_code_ne_discrimine_rien():
    """Mesuré sur la cible : tout compte existant porte le même pictogramme,
    donc cette colonne ne mesure PAS un état, contrairement à ce qu'on croit
    en la lisant."""
    lignes = [{"LOCKED": "@07@"}, {"LOCKED": "@07@"}, {"LOCKED": ""}]
    assert distinct_icons(lignes, "LOCKED") == {"07": 2}


def test_une_icone_s_etablit_en_la_croisant_avec_une_verite_connue():
    """La méthode de croisement : le sens du pictogramme est ÉTABLI sur le
    périmètre où les deux canaux se recouvrent, puis applicable au périmètre
    que seul l'écran atteint.

    Le contraste est ici fourni par un SECOND code associé à l'autre état.
    """
    lignes = [{"MANDT": "001", "USERNAME": "DDIC", "LOCKED": "@07@"},
              {"MANDT": "001", "USERNAME": "SAP*", "LOCKED": "@08@"},
              {"MANDT": "000", "USERNAME": "DDIC", "LOCKED": "@07@"}]
    # Le canal sans écran n'atteint que le mandant 001.
    connu = {"001/DDIC": False, "001/SAP*": True}
    verdict = establish_icon_meaning(lignes, "LOCKED",
                                     ["MANDT", "USERNAME"], connu)
    assert verdict["meanings"] == {"07": False, "08": True}
    assert verdict["discriminating"] is True
    assert verdict["ambiguous"] == []
    assert verdict["coverage"] == 2
    assert verdict["unmatched"] == ["000/DDIC"]


def test_un_recoupement_sans_contraste_ne_conclut_rien():
    """Le second repli sûr, ajouté sur réserve de revue indépendante : un seul
    code et un seul état ne permettent pas de distinguer « ce code signifie
    cet état » de « ce code signifie que la ligne existe ». C'est exactement
    la situation de la cible, et l'hypothèse concurrente y est soutenue par
    les lignes à cellule vide, qui sont les comptes inexistants."""
    lignes = [{"K": "001/DDIC", "I": "@07@"}, {"K": "001/SAP*", "I": "@07@"},
              {"K": "000/DDIC", "I": "@07@"}, {"K": "001/ABSENT", "I": ""}]
    verdict = establish_icon_meaning(lignes, "I", ["K"],
                                     {"001/DDIC": False, "001/SAP*": False})
    assert verdict["meanings"] == {}
    assert verdict["discriminating"] is False
    assert verdict["not_discriminating"] == ["07"]
    assert verdict["coverage"] == 2


def test_le_contraste_peut_venir_des_deux_etats_sur_un_seul_code():
    """Deux états observés sur un même code le rendent ambigu, ce qui est une
    conclusion (négative) et non une absence de contraste."""
    verdict = establish_icon_meaning(
        [{"K": "a", "I": "@07@"}, {"K": "b", "I": "@07@"}], "I", ["K"],
        {"a": True, "b": False})
    assert verdict["discriminating"] is True
    assert verdict["ambiguous"] == ["07"]
    assert verdict["meanings"] == {}


def test_un_code_ambigu_n_est_jamais_traduit():
    """Le repli sûr : interpréter un pictogramme de travers dans un rapport de
    sécurité est pire que ne pas l'interpréter, puisque la traduction sera lue
    comme un fait."""
    lignes = [{"K": "a", "I": "@07@"}, {"K": "b", "I": "@07@"}]
    verdict = establish_icon_meaning(lignes, "I", ["K"],
                                     {"a": True, "b": False})
    assert verdict["meanings"] == {}
    assert verdict["ambiguous"] == ["07"]


def test_etablir_sans_aucun_recouvrement_ne_conclut_rien():
    verdict = establish_icon_meaning([{"K": "z", "I": "@07@"}], "I", ["K"], {})
    assert verdict["meanings"] == {}
    assert verdict["coverage"] == 0
    assert verdict["unmatched"] == ["z"]
