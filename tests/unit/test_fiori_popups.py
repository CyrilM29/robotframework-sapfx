"""Tests hors navigateur des popups OUVERTS et de l'acquittement par POSITION.

Les trois mots-clés couverts ici sont nés d'une campagne live sur le launchpad
Fiori d'un serveur ABAP (2026-08-24), et chacun ferme un trou mesuré :

* `Get Ui5 Ids` : l'ancre documentée d'un shell est le SUFFIXE d'identifiant,
  or la bibliothèque savait compter les correspondances et lire leurs
  propriétés sans jamais dire LESQUELLES avaient matché ;
* `Get Ui5 Open Popups` : un dialogue FERMÉ reste RENDU (le dialogue « À
  propos » du launchpad garde son nœud DOM après acquittement), donc aucun
  comptage ne distingue ouvert de fermé ;
* `Click Ui5 Dialog Button` : les boutons d'une MessageBox portent un id
  généré (`__mbox-btn-0`) et un texte TRADUIT, donc leur seule adresse
  locale-indépendante est leur position.

La résolution en page (le JS injecté) est exercée par les suites live ; ici on
valide le contrat Python autour du navigateur avec une doublure de la
bibliothèque Browser (convention #5).
"""
import json

import pytest

from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary
from SapFioriLibrary._ui5_js import (
    DIALOG_BUTTON_JS,
    OPEN_POPUPS_JS,
    RESOLVE_ROLE_JS,
)


class FakeBrowser:
    """Doublure de Browser : sert une réponse cannée par fonction du bundle et
    mémorise ce qui a réellement été demandé (charges utiles, clics)."""

    def __init__(self, reponses):
        self.reponses = reponses
        self.charges = []
        self.clics = []

    def evaluate_javascript(self, selector, js, arg=None):
        self.charges.append((js, arg))
        if js in self.reponses:
            return self.reponses[js]
        raise AssertionError("fonction de bundle non attendue par ce test")

    def click(self, selector):
        self.clics.append(selector)


def _lib(browser):
    lib = SapFioriLibrary(ui5_timeout="2s")
    lib._browser = lambda: browser
    return lib


# --- Get Ui5 Ids -------------------------------------------------------------

def test_les_ids_rendus_sont_retournes_dans_l_ordre_du_registre():
    browser = FakeBrowser({RESOLVE_ROLE_JS: ["__list0-0-recentActivitiesBtn",
                                             "__list0-4-ActionModeBtn"]})
    ids = _lib(browser).get_ui5_ids(controlType="sap.m.StandardListItem")
    assert ids == ["__list0-0-recentActivitiesBtn", "__list0-4-ActionModeBtn"]


def test_les_ids_partent_avec_le_selecteur_demande():
    browser = FakeBrowser({RESOLVE_ROLE_JS: []})
    _lib(browser).get_ui5_ids(idSuffix="-UserSettingsEntry")
    _, charge = browser.charges[0]
    assert json.loads(charge)["idSuffix"] == "-UserSettingsEntry"


def test_aucune_correspondance_rend_une_liste_vide_et_non_une_erreur():
    """Lecture, pas assertion : découvrir zéro entrée est un résultat exploitable
    (c'est ainsi qu'on constate qu'une entrée déclarée n'est pas rendue)."""
    browser = FakeBrowser({RESOLVE_ROLE_JS: None})
    assert _lib(browser).get_ui5_ids(controlType="Button") == []


# --- Get Ui5 Open Popups -----------------------------------------------------

def test_les_popups_ouverts_portent_leur_etat_et_leur_nombre_de_boutons():
    browser = FakeBrowser({OPEN_POPUPS_JS: [
        {"id": "__dialog4", "controlType": "sap.m.Dialog", "kind": "dialog",
         "state": "Error", "buttons": 3},
    ]})
    popups = _lib(browser).get_ui5_open_popups()
    assert popups[0]["state"] == "Error"
    assert popups[0]["kind"] == "dialog"
    assert popups[0]["buttons"] == 3


def test_aucun_popup_ouvert_est_une_liste_vide():
    """Le cas nominal après acquittement : c'est CE constat que le comptage de
    correspondances ne pouvait pas rendre, le contrôle restant rendu."""
    browser = FakeBrowser({OPEN_POPUPS_JS: []})
    assert _lib(browser).get_ui5_open_popups() == []


def test_sans_runtime_ui5_l_echec_nomme_la_sonde_et_la_portee():
    browser = FakeBrowser({OPEN_POPUPS_JS: None})
    with pytest.raises(AssertionError) as erreur:
        _lib(browser).get_ui5_open_popups()
    message = str(erreur.value)
    assert "Ui5 Runtime Is Present" in message
    assert "Get Ui5 Frame Stack" in message


# --- Click Ui5 Dialog Button -------------------------------------------------

def test_le_bouton_est_designe_par_sa_position_et_clique_par_son_id():
    browser = FakeBrowser({DIALOG_BUTTON_JS: {"id": "__mbox-btn-0", "count": 2,
                                              "dialog": "__confirm0"}})
    _lib(browser).click_ui5_dialog_button()
    assert browser.clics == ['css=[id="__mbox-btn-0"]']
    _, charge = browser.charges[0]
    assert json.loads(charge)["position"] == 0


def test_la_position_demandee_est_bien_celle_transmise():
    browser = FakeBrowser({DIALOG_BUTTON_JS: {"id": "__mbox-btn-1", "count": 2,
                                              "dialog": "__confirm0"}})
    _lib(browser).click_ui5_dialog_button(1)
    _, charge = browser.charges[0]
    assert json.loads(charge)["position"] == 1
    assert browser.clics == ['css=[id="__mbox-btn-1"]']


def test_sans_dialogue_ouvert_l_echec_nomme_la_perception():
    browser = FakeBrowser({DIALOG_BUTTON_JS: {"error": "no_dialog"}})
    with pytest.raises(AssertionError) as erreur:
        _lib(browser).click_ui5_dialog_button()
    assert "Get Ui5 Open Popups" in str(erreur.value)
    assert browser.clics == []


def test_une_position_hors_bornes_dit_combien_de_boutons_existent():
    browser = FakeBrowser({DIALOG_BUTTON_JS: {"error": "out_of_range", "count": 2,
                                              "dialog": "__confirm0"}})
    with pytest.raises(AssertionError) as erreur:
        _lib(browser).click_ui5_dialog_button(5)
    message = str(erreur.value)
    assert "__confirm0" in message
    assert "2 bouton" in message
    assert browser.clics == []


def test_le_bundle_expose_bien_les_fonctions_appelees():
    """Contre-épreuve du câblage : les noms appelés côté Python doivent exister
    dans le bundle JS livré, sinon l'erreur n'apparaîtrait qu'en live."""
    from SapFioriLibrary._ui5_js import BUNDLE

    assert "openPopups: openPopups" in BUNDLE
    assert "dialogButton: dialogButton" in BUNDLE
    assert "window.__SAPFX.openPopups(arg)" in OPEN_POPUPS_JS
    assert "window.__SAPFX.dialogButton(arg)" in DIALOG_BUTTON_JS
