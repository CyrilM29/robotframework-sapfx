"""Tests de `sapfx_common.robot_args` : la normalisation des arguments qui
franchissent la frontière Robot/MCP. Via ``execute_step`` (rf-mcp), TOUT
argument arrive en chaîne ; trois incidents d'agents du 2026-08-27 (relecture
CabrIA) fixent le contrat : chaîne à virgules et liste-littérale acceptées là
où une liste est attendue, et une conversion d'entier qui NOMME son argument
au lieu du ``TypeError: int() ...`` nu."""
import pytest

from sapfx_common.robot_args import (as_name_list, as_optional_int,
                                     displayed_count)


# --- displayed_count ---------------------------------------------------------

def test_displayed_count_ignore_les_separateurs_de_milliers():
    # Le même compteur selon le profil d'affichage : la vérité est 4136.
    assert displayed_count("4.136") == 4136
    assert displayed_count("4,136") == 4136
    assert displayed_count("4 136 ") == 4136


def test_displayed_count_texte_autour_et_entrees_vides():
    assert displayed_count("Number of entries: 205") == 205
    assert displayed_count("") == 0
    assert displayed_count(None) == 0
    assert displayed_count("aucun chiffre") == 0


# --- as_name_list ------------------------------------------------------------

def test_as_name_list_liste_et_tuple_normalises():
    assert as_name_list(["A", " B ", ""]) == ["A", "B"]
    assert as_name_list(("A",)) == ["A"]


def test_as_name_list_chaine_a_virgules():
    # L'incident fondateur : "FIELDNAME,POSITION,..." traité comme UN nom
    # de colonne introuvable, chaque colonne pourtant dans « Available ».
    assert as_name_list("FIELDNAME,POSITION, KEYFLAG") == [
        "FIELDNAME", "POSITION", "KEYFLAG"]


def test_as_name_list_valeur_seule_none_et_vide():
    assert as_name_list("CARRID") == ["CARRID"]
    assert as_name_list(None) == []
    assert as_name_list("   ") == []


def test_as_name_list_liste_litterale_serialisee():
    # La 2e variante vécue : un agent qui sérialise sa liste Python.
    assert as_name_list("['TABNAME', 'TABCLASS']") == ["TABNAME", "TABCLASS"]
    assert as_name_list("('A', 'B')") == ["A", "B"]


def test_as_name_list_preserve_la_casse():
    """Contrairement à ``rfc_tables.as_field_list`` (qui capitalise pour le
    dictionnaire ABAP) : ici l'appelant décide de la casse."""
    assert as_name_list("a,B") == ["a", "B"]


def test_as_name_list_litterale_illisible_echec_nommant_l_argument():
    with pytest.raises(ValueError, match="columns"):
        as_name_list("['TABNAME', <cassé>]")


# --- as_optional_int ---------------------------------------------------------

def test_as_optional_int_conversions_ordinaires():
    assert as_optional_int(None, "max_rows") is None
    assert as_optional_int("", "max_rows") is None
    assert as_optional_int(" 42 ", "max_rows") == 42
    assert as_optional_int(7, "max_rows") == 7


def test_as_optional_int_liste_nomme_l_argument_et_le_remede():
    """L'incident : ``${cols}`` liste passée en POSITION de ``max_rows``
    sortait en ``TypeError: int() ... not 'list'`` nu. L'erreur nomme
    l'argument, le décalage positionnel probable, et le remède fourni par
    l'appelant."""
    with pytest.raises(ValueError) as err:
        as_optional_int(["A", "B"], "max_rows",
                        hint="Une liste de colonnes se passe par columns=.")
    message = str(err.value)
    assert "max_rows" in message
    assert "POSITIONNELS" in message
    assert "columns=" in message


def test_as_optional_int_refuse_booleen_et_texte():
    with pytest.raises(ValueError, match="max_rows"):
        as_optional_int(True, "max_rows")
    with pytest.raises(ValueError, match="max_rows"):
        as_optional_int("beaucoup", "max_rows")
