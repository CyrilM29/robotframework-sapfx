"""Tests hors navigateur de la lecture de PROPRIÉTÉS de contrôles UI5.

`Get Ui5 Property` / `Get Ui5 Properties` existent parce que lire le texte
RENDU d'un contrôle impose deux contraintes dont une assertion n'a pas besoin :
la visibilité, et tout ce que le contrôle dessine en plus de la valeur. Les cas
couverts ici sont ceux relevés live sur un launchpad Work Zone le 2026-08-24 :
un élément de liste dont le rendu ajoute un compteur, et un contrôle rendu mais
masqué par une colonne repliée.

La résolution en page (le JS injecté) est exercée par les suites live ; ici on
valide le contrat Python autour du navigateur avec une doublure de la
bibliothèque Browser (convention #5).
"""
import json

import pytest

from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary
from SapFioriLibrary._ui5_js import READ_PROPERTY_JS


class FakeBrowser:
    """Doublure de Browser : sert la réponse cannée de `readProperty` et
    mémorise la charge utile reçue, pour vérifier ce qui part vraiment au JS."""

    def __init__(self, reponse):
        self.reponse = reponse
        self.charges = []

    def evaluate_javascript(self, selector, js, arg=None):
        if js == READ_PROPERTY_JS:
            self.charges.append(arg)
            return self.reponse
        return None

    def get_text(self, selector):        # jamais appelé : c'est tout l'intérêt
        raise AssertionError("Get Text ne doit pas être sollicité pour lire une propriété")


def _lib(browser):
    lib = SapFioriLibrary(ui5_timeout="2s")
    lib._browser = lambda: browser
    return lib


def test_lit_la_valeur_de_chaque_controle_matche():
    browser = FakeBrowser({"values": ["Accessories", "Printers"], "unknown": False, "available": []})
    valeurs = _lib(browser).get_ui5_properties("title", controlType="StandardListItem")
    assert valeurs == ["Accessories", "Printers"]


def test_la_charge_utile_porte_la_propriete_et_le_selecteur():
    browser = FakeBrowser({"values": [], "unknown": False, "available": []})
    _lib(browser).get_ui5_properties("title", controlType="StandardListItem", viewId="vue--liste")
    charge = json.loads(browser.charges[0])
    assert charge["property"] == "title"
    assert charge["selector"]["viewId"] == "vue--liste"
    assert charge["selector"]["controlType"] == "StandardListItem"


def test_une_propriete_inconnue_echoue_en_listant_ce_qui_existe():
    """Une faute de frappe doit se voir : sans ce garde, la lecture rendrait une
    liste de None, et l'assertion échouerait deux étapes plus loin sur une
    comparaison incompréhensible."""
    browser = FakeBrowser(
        {"values": [], "unknown": True, "available": ["description", "info", "title"]})
    with pytest.raises(AssertionError) as erreur:
        _lib(browser).get_ui5_properties("titre", controlType="StandardListItem")
    message = str(erreur.value)
    assert "titre" in message
    assert "description, info, title" in message


def test_sans_runtime_ui5_l_echec_nomme_la_sonde_et_la_portee():
    """`readProperty` rend `null` hors page UI5 : le message doit envoyer vers la
    sonde de runtime et la pile de frames, les deux seules causes réelles."""
    browser = FakeBrowser(None)
    with pytest.raises(AssertionError) as erreur:
        _lib(browser).get_ui5_properties("title", controlType="Button")
    message = str(erreur.value)
    assert "Ui5 Runtime Is Present" in message
    assert "Get Ui5 Frame Stack" in message


def test_aucune_correspondance_rend_une_liste_vide_et_non_une_erreur():
    """Lecture, pas assertion : compter zéro est un résultat, exiger une présence
    est le travail de `Ui5 Control Should Be Visible`."""
    browser = FakeBrowser({"values": [], "unknown": False, "available": []})
    assert _lib(browser).get_ui5_properties("title", controlType="Button") == []


def test_la_variante_unitaire_selectionne_par_index():
    browser = FakeBrowser({"values": ["a", "b", "c"], "unknown": False, "available": []})
    assert _lib(browser).get_ui5_property("title", index=1, controlType="StandardListItem") == "b"


def test_la_variante_unitaire_echoue_quand_rien_ne_matche():
    browser = FakeBrowser({"values": [], "unknown": False, "available": []})
    with pytest.raises(AssertionError, match="No UI5 control matched"):
        _lib(browser).get_ui5_property("title", controlType="Button")


def test_la_variante_unitaire_echoue_sur_un_index_hors_bornes():
    browser = FakeBrowser({"values": ["a"], "unknown": False, "available": []})
    with pytest.raises(AssertionError, match="index 3 is out of range"):
        _lib(browser).get_ui5_property("title", index=3, controlType="StandardListItem")


def test_le_bundle_expose_bien_la_fonction_appelee():
    """Contre-épreuve du câblage : le nom appelé côté Python doit exister dans le
    bundle JS livré, sinon l'erreur n'apparaîtrait qu'en live."""
    from SapFioriLibrary._ui5_js import BUNDLE

    assert "readProperty: readProperty" in BUNDLE
    assert "window.__SAPFX.readProperty(arg)" in READ_PROPERTY_JS
