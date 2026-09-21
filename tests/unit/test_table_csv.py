"""L'écriture d'un relevé en CSV (`sapfx_common.table_csv`).

Le CSV passe pour le format trivial des trois, et c'est précisément ce qui le
rend dangereux : chacun de ses pièges produit un fichier lisible et faux. Ces
tests verrouillent les quatre, dans l'ordre où ils coûtent cher : l'encodage
(des accents détruits à l'ouverture), le séparateur (une colonne unique), les
formules (une valeur négative lue comme un calcul, une valeur hostile comme
une exécution) et les fins de ligne (un fichier différent selon le poste).
"""
from __future__ import annotations

import pytest

from sapfx_common.table_csv import (
    formula_risk_cells,
    looks_like_formula,
    read_table_csv,
    render_table_csv,
    write_table_csv,
)

RELEVE = [
    {"NAME": "login/min_password_lng", "USER_VALUE": "", "DEFAULT_VALUE": "10"},
    {"NAME": "gw/reg_info", "USER_VALUE": "/usr/sap/reg_info",
     "DEFAULT_VALUE": "/usr/sap/reg_info"},
]


def test_l_en_tete_puis_les_lignes_sont_ecrits_dans_l_ordre_demande():
    texte = render_table_csv(RELEVE, columns=["NAME", "DEFAULT_VALUE"])
    lignes = texte.splitlines()
    assert lignes[0] == "NAME,DEFAULT_VALUE"
    assert lignes[1] == "login/min_password_lng,10"


def test_les_fins_de_ligne_sont_fixes_quel_que_soit_le_poste():
    # RFC 4180, et surtout : deux écritures de la même donnée doivent produire
    # le même fichier, comme pour les deux autres formats.
    assert render_table_csv(RELEVE).endswith("\r\n")
    assert "\n" not in render_table_csv(RELEVE).replace("\r\n", "")


def test_une_valeur_portant_le_separateur_est_protegee():
    texte = render_table_csv([{"V": "a,b"}])
    assert texte.splitlines()[1] == '"a,b"'


def test_le_point_virgule_est_disponible_pour_un_excel_francais():
    texte = render_table_csv(RELEVE, columns=["NAME"], delimiter=";")
    assert texte.splitlines()[0] == "NAME"
    texte = render_table_csv([{"A": "1", "B": "2"}], delimiter=";")
    assert texte.splitlines()[1] == "1;2"


def test_un_separateur_de_plusieurs_caracteres_est_refuse_en_le_disant():
    with pytest.raises(ValueError) as echec:
        render_table_csv(RELEVE, delimiter=", ")
    assert "UN caractère" in str(echec.value)


def test_une_valeur_negative_est_reperee_comme_formule():
    # Le cas concret : un relevé de paramètres porte de vraies valeurs
    # négatives, donc le sujet n'est pas théorique.
    assert looks_like_formula("-1")
    assert looks_like_formula("=1+1")
    assert looks_like_formula("@SUM")
    assert not looks_like_formula("10")
    assert not looks_like_formula(None)


def test_une_amorce_precedee_de_blancs_reste_une_formule():
    # Un tableur ignore les blancs de tête avant de décider.
    assert looks_like_formula("  =1+1")


def test_les_cellules_a_risque_sont_comptees_sans_rien_changer():
    lignes = [{"V": "-1"}, {"V": "10"}, {"V": "=A1"}]
    assert formula_risk_cells(lignes) == 2
    assert render_table_csv(lignes).splitlines()[1] == "-1"


def test_la_neutralisation_est_explicite_et_jamais_implicite():
    lignes = [{"V": "=cmd|' /c calc'!A1"}]
    nu = render_table_csv(lignes)
    protege = render_table_csv(lignes, neutralize_formulas=True)
    assert nu.splitlines()[1].startswith("=cmd")
    assert protege.splitlines()[1].startswith("'=cmd")


def test_le_verdict_compte_le_risque_meme_sans_neutralisation(tmp_path):
    verdict = write_table_csv(str(tmp_path / "t.csv"), [{"V": "-1"}])
    assert verdict["formula_cells"] == 1
    assert verdict["neutralized_cells"] == 0


def test_le_verdict_compte_ce_qui_a_ete_neutralise(tmp_path):
    verdict = write_table_csv(str(tmp_path / "t.csv"), [{"V": "-1"}],
                              neutralize_formulas=True)
    assert verdict["neutralized_cells"] == 1


def test_la_marque_d_ordre_d_octets_est_ecrite_par_defaut(tmp_path):
    # Sans elle, Excel ouvre un CSV UTF-8 en codage local et détruit les
    # accents ; les lecteurs standard, eux, la tolèrent.
    cible = tmp_path / "t.csv"
    verdict = write_table_csv(str(cible), [{"V": "éàü"}])
    assert cible.read_bytes().startswith(b"\xef\xbb\xbf")
    assert verdict["encoding"] == "utf-8-sig"


def test_la_marque_peut_etre_retiree(tmp_path):
    cible = tmp_path / "t.csv"
    write_table_csv(str(cible), [{"V": "éàü"}], byte_order_mark=False)
    assert not cible.read_bytes().startswith(b"\xef\xbb\xbf")


def test_l_aller_retour_rend_exactement_le_releve_ecrit(tmp_path):
    cible = tmp_path / "t.csv"
    write_table_csv(str(cible), RELEVE)
    assert read_table_csv(str(cible)) == RELEVE


def test_la_relecture_ne_colle_pas_la_marque_au_premier_nom_de_colonne(tmp_path):
    cible = tmp_path / "t.csv"
    write_table_csv(str(cible), RELEVE)
    assert list(read_table_csv(str(cible))[0]) == ["NAME", "USER_VALUE",
                                                   "DEFAULT_VALUE"]


def test_la_relecture_deduit_le_separateur_d_un_fichier_recu(tmp_path):
    # Un CSV reçu ne dit pas quel séparateur il emploie : supposer la virgule
    # rendrait une colonne unique dont le nom serait toute la ligne.
    cible = tmp_path / "t.csv"
    write_table_csv(str(cible), RELEVE, delimiter=";")
    assert read_table_csv(str(cible)) == RELEVE


def test_la_relecture_garde_les_valeurs_en_texte(tmp_path):
    cible = tmp_path / "t.csv"
    write_table_csv(str(cible), [{"MANDT": "000"}])
    assert read_table_csv(str(cible))[0] == {"MANDT": "000"}


def test_un_fichier_vide_rend_un_releve_vide(tmp_path):
    cible = tmp_path / "vide.csv"
    cible.write_text("", encoding="utf-8")
    assert read_table_csv(str(cible)) == []


def test_le_verdict_signale_un_fichier_incomplet(tmp_path):
    lignes = [{"N": str(i)} for i in range(5)]
    verdict = write_table_csv(str(tmp_path / "t.csv"), lignes, max_rows=2)
    assert verdict["rows"] == 2
    assert verdict["total_rows"] == 5
    assert verdict["truncated_rows"] is True


def test_une_colonne_absente_echoue_en_listant_ce_qui_existe():
    with pytest.raises(ValueError) as echec:
        render_table_csv(RELEVE, columns=["ABSENTE"])
    assert "ABSENTE" in str(echec.value)
