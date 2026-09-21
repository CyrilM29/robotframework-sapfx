"""Les en-têtes AFFICHÉS, propriété transverse aux cinq formats.

Née d'un retour sur la première extraction de RSPARAM (2026-09-15) : le
fichier livré portait les identifiants techniques des colonnes (`NAME`,
`USER_VALUE`), que seul un développeur reconnaît, là où l'écran affiche
« Parameter Name » et « User-Defined Value ».

Les deux lectures ont chacune leur usage et les confondre produit deux défauts
opposés : un test qui asserte sur des titres affichés dépend de la langue de
session (convention 3), un fichier livré avec des ids techniques ne ressemble
pas à l'écran dont il vient. D'où la carte `{id: titre}` que rend
`Get Grid Column Titles` : les clés de lecture restent techniques, l'en-tête
devient celui de SAP.

Le cas limite qui compte est le libellé DUPLIQUÉ, qu'une ALV peut afficher :
toléré là où l'en-tête est décoratif (SVG, CSV, XLSX), refusé là où il devient
une clé (JSON, Parquet), car une colonne y disparaîtrait d'un fichier
d'apparence complète.
"""
from __future__ import annotations

import pytest

from sapfx_common.table_csv import render_table_csv
from sapfx_common.table_json import render_table_json, table_records
from sapfx_common.table_svg import render_table_svg
from sapfx_common.table_xlsx import build_xlsx, read_table_xlsx, write_table_xlsx

# La carte réellement relevée sur RSPARAM (ABAP Platform 2023, release 758).
TITRES = {
    "NAME": "Parameter Name",
    "USER_VALUE": "User-Defined Value",
    "DEFAULT_VALUE": "System Default Value",
}
RELEVE = [{"NAME": "login/min_password_lng", "USER_VALUE": "",
           "DEFAULT_VALUE": "10"}]


def test_le_csv_porte_les_titres_sap_et_garde_l_ordre():
    entete = render_table_csv(RELEVE, headers=TITRES).splitlines()[0]
    assert entete == "Parameter Name,User-Defined Value,System Default Value"


def test_le_svg_porte_les_titres_sap():
    svg = render_table_svg(RELEVE, headers=TITRES)
    assert "Parameter Name" in svg
    assert ">NAME<" not in svg


def test_le_classeur_porte_les_titres_sap(tmp_path):
    cible = tmp_path / "t.xlsx"
    verdict = write_table_xlsx(str(cible), RELEVE, headers=TITRES)
    assert verdict["headers"][0] == "Parameter Name"
    relu = read_table_xlsx(str(cible))
    assert list(relu[0]) == list(TITRES.values())
    assert relu[0]["Parameter Name"] == "login/min_password_lng"


def test_le_json_porte_les_titres_sap():
    fiches = table_records(RELEVE, headers=TITRES)
    assert list(fiches[0]) == list(TITRES.values())
    assert "Parameter Name" in render_table_json(RELEVE, headers=TITRES)


def test_une_colonne_absente_de_la_carte_garde_son_identifiant():
    # Une carte partielle ne doit pas produire de colonne sans nom.
    entete = render_table_csv(RELEVE, headers={"NAME": "Parameter Name"})
    assert entete.splitlines()[0].split(",")[1] == "USER_VALUE"


def test_un_libelle_vide_garde_l_identifiant():
    entete = render_table_csv(RELEVE, headers={"NAME": "   "})
    assert entete.splitlines()[0].startswith("NAME,")


def test_sans_carte_l_en_tete_reste_technique():
    assert render_table_csv(RELEVE).splitlines()[0] == (
        "NAME,USER_VALUE,DEFAULT_VALUE")


def test_un_libelle_duplique_est_tolere_la_ou_l_en_tete_est_decoratif():
    doublons = {"NAME": "Valeur", "USER_VALUE": "Valeur",
                "DEFAULT_VALUE": "Valeur"}
    assert render_table_csv(RELEVE, headers=doublons).splitlines()[0] == (
        "Valeur,Valeur,Valeur")
    assert build_xlsx(RELEVE, headers=doublons)


def test_un_libelle_duplique_est_refuse_la_ou_il_devient_une_cle():
    doublons = {"NAME": "Valeur", "USER_VALUE": "Valeur"}
    with pytest.raises(ValueError) as echec:
        table_records(RELEVE, headers=doublons)
    assert "même libellé" in str(echec.value)
    assert "NAME" in str(echec.value) and "USER_VALUE" in str(echec.value)


def test_une_ligne_entierement_vide_est_comptee():
    # Le témoin qu'un compte de lignes ne donne pas : une ALV lue sur des
    # lignes non chargées rend des cellules vides au lieu de lever, donc le
    # relevé a le bon nombre de lignes et ne contient rien.
    from sapfx_common._tabular import blank_rows

    lignes = [{"A": "x", "B": ""}, {"A": "", "B": ""}, {"A": " ", "B": "\t"}]
    assert blank_rows(lignes) == 2


def test_le_comptage_de_lignes_vides_se_restreint_aux_colonnes_voulues():
    from sapfx_common._tabular import blank_rows

    lignes = [{"A": "", "B": "valeur"}]
    assert blank_rows(lignes) == 0
    assert blank_rows(lignes, ["A"]) == 1


def test_la_carte_de_colonnes_est_acceptee_comme_liste_de_colonnes():
    # `Get Grid Column Titles` rend un mapping, et le passer tel quel en
    # `columns` est le geste naturel : la frontière Robot doit le prendre.
    from sapfx_common.robot_args import as_name_list

    assert as_name_list(TITRES) == ["NAME", "USER_VALUE", "DEFAULT_VALUE"]
