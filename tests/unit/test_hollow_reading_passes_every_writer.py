"""La contre-épreuve : un relevé CREUX traverse les cinq écrivains au vert.

Ces tests ne vérifient pas une propriété souhaitable. Ils établissent une
propriété gênante, et c'est leur raison d'être : sur un relevé dont toutes les
cellules sont vides, les cinq formats écrivent un fichier, le relisent, et la
confrontation ligne à ligne réussit. Comparer du vide à du vide ne rougit
jamais.

C'est ce qui rend la garde de contenu indispensable EN AMONT de l'écriture.
Une revue indépendante l'a relevé le 2026-09-15 : la suite d'extraction
refusait bien un relevé creux, mais dans un scénario, donc après coup, et les
cinq scénarios d'écriture qui suivaient passaient tous en produisant des
fichiers creux. Le refus a été déplacé dans le Suite Setup ; ces tests
documentent pourquoi il ne peut pas vivre ailleurs.

Le jour où l'un de ces tests échoue, c'est qu'un écrivain a gagné une garde
propre : il faudra alors le dire ici plutôt que de supprimer le test.
"""
from __future__ import annotations

import pytest

from sapfx_common._tabular import blank_rows
from sapfx_common.table_csv import read_table_csv, write_table_csv
from sapfx_common.table_json import read_table_json, write_table_json
from sapfx_common.table_svg import write_table_svg
from sapfx_common.table_xlsx import read_table_xlsx, write_table_xlsx

COLONNES = ["NAME", "USER_VALUE", "DEFAULT_VALUE"]
#: Le relevé tel qu'une ALV non défilée le rend : les lignes existent, les
#: cellules sont vides. Mesuré live, 1502 lignes sur 1639 avaient cette forme.
CREUX = [{colonne: "" for colonne in COLONNES} for _ in range(5)]


def test_le_releve_creux_est_bien_detecte_en_amont():
    # La seule mesure qui le distingue d'un relevé plein : elle porte sur le
    # CONTENU, pas sur le nombre de lignes.
    assert len(CREUX) == 5
    assert blank_rows(CREUX, COLONNES) == 5


@pytest.mark.parametrize("ecrire,relire", [
    (write_table_csv, read_table_csv),
    (write_table_json, read_table_json),
    (write_table_xlsx, read_table_xlsx),
])
def test_l_aller_retour_d_un_releve_creux_reussit(ecrire, relire, tmp_path):
    cible = tmp_path / "creux"
    verdict = ecrire(str(cible), CREUX, columns=COLONNES)
    assert verdict["rows"] == 5
    assert verdict["truncated_rows"] is False
    # La confrontation que la suite fait passer pour une preuve de fidélité :
    # elle réussit, parce que les deux côtés sont vides.
    assert relire(str(cible)) == CREUX


def test_le_svg_d_un_releve_creux_est_un_document_valide(tmp_path):
    cible = tmp_path / "creux.svg"
    verdict = write_table_svg(str(cible), CREUX, columns=COLONNES)
    assert verdict["rows"] == 5
    contenu = cible.read_text(encoding="utf-8")
    assert contenu.startswith("<svg")
    # Et le piège propre au SVG : le témoin de contenu qu'utilisait la suite
    # est une valeur du relevé, donc une chaîne VIDE sur un relevé creux, et
    # `in` avec une chaîne vide est toujours vrai.
    temoin = CREUX[0]["NAME"]
    assert temoin == ""
    assert temoin in contenu, "c'est précisément le contrôle qui ne prouve rien"


def test_un_document_creux_porte_moins_de_textes_que_de_lignes(tmp_path):
    # La mesure qui, elle, distingue : une cellule vide n'écrit aucun élément
    # de texte, donc un document creux en porte moins qu'il n'a de lignes.
    # C'est l'assertion que la suite a adoptée pour le SVG.
    cible = tmp_path / "creux.svg"
    write_table_svg(str(cible), CREUX, columns=COLONNES)
    contenu = cible.read_text(encoding="utf-8")
    assert contenu.count("<text") < len(CREUX)

    plein = [{c: "valeur" for c in COLONNES} for _ in range(5)]
    cible_pleine = tmp_path / "plein.svg"
    write_table_svg(str(cible_pleine), plein, columns=COLONNES)
    assert cible_pleine.read_text(encoding="utf-8").count("<text") >= len(plein)
