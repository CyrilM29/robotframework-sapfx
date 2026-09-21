"""Les keywords de grille qui servent l'EXTRACTION d'un tableau (2026-09-15).

Séparés de `test_logic.py` par la convention #13 (aucun fichier de code
au-delà de 500 lignes) et le long d'une vraie couture : ces deux keywords ne
servent pas à piloter un écran mais à en SORTIR le contenu, `Get Grid Column
Titles` pour l'en-tête que le lecteur reconnaît et `Count Blank Grid Rows`
pour refuser un relevé creux. Ils réutilisent les faux objets COM de
`test_logic`, qui reste le foyer du pilotage de grille.
"""
from __future__ import annotations

from test_logic import _grid_lib, _wrapped_grid_lib

# Convention #5 : tout keyword a son test hors SAP. Le chemin que les tests de
# logique pure ne couvrent PAS est justement celui-ci : le résolveur `_grid`
# (qui traverse les splitters) et la normalisation des arguments de frontière.


def test_les_titres_de_colonnes_sont_rendus_par_identifiant_technique():
    """La carte `{id: titre AFFICHÉ}` : les clés restent techniques (elles
    seules sont indépendantes de la langue), les titres servent d'en-tête aux
    fichiers livrés."""
    lib = _grid_lib()
    assert lib.get_grid_column_titles("grid") == {"MANDT": "Client",
                                                 "MTEXT": "Name"}


def test_les_titres_sont_atteints_a_travers_un_splitter():
    """Le même résolveur que les autres lectures : une release qui enveloppe
    son ALV dans un splitter ne doit pas priver l'extraction de ses en-têtes."""
    lib, grid = _wrapped_grid_lib(depth=1)
    assert lib.get_grid_column_titles("grid") == {"MANDT": "Client",
                                                 "MTEXT": "Name"}


def test_les_lignes_entierement_vides_sont_comptees_par_le_keyword():
    lib = _grid_lib()
    releve = [{"MANDT": "100", "MTEXT": "Acme"},
              {"MANDT": "", "MTEXT": ""},
              {"MANDT": " ", "MTEXT": "\t"}]
    assert lib.count_blank_grid_rows(releve) == 2


def test_le_comptage_accepte_les_colonnes_sous_les_formes_de_la_frontiere():
    """Via rf-mcp et la ligne de commande Robot, une liste arrive en chaîne ;
    et la carte de titres est le geste naturel de l'appelant."""
    lib = _grid_lib()
    releve = [{"MANDT": "", "MTEXT": "Acme"}]
    assert lib.count_blank_grid_rows(releve, "MANDT") == 1
    assert lib.count_blank_grid_rows(releve, ["MANDT"]) == 1
    assert lib.count_blank_grid_rows(releve, {"MANDT": "Client"}) == 1
    # Sans restriction, la ligne porte une valeur : elle n'est pas vide.
    assert lib.count_blank_grid_rows(releve) == 0
