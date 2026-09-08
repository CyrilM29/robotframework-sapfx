"""Tests hors SAP de l'identité d'un message de la barre de statut : la logique
pure (``sapfx_common.status_message``) et le mixin ``StatusBarKeywords``
(``MessageId`` padding retiré, ``MessageNumber``, ``MessageParameter`` méthode)."""
import pytest
from pythoncom import com_error

from SapEccLibrary import SapEccLibrary
from sapfx_common.status_message import (
    format_identity_mismatch,
    identity_matches,
    message_identity,
    normalize_message_class,
    normalize_message_number,
)


def test_la_classe_perd_son_padding_de_champ_abap_et_le_numero_reste_tel_quel():
    assert normalize_message_class("MO                  ") == "MO"
    assert normalize_message_class(" mo ") == "MO"
    assert normalize_message_number(" 402 ") == "402"
    assert normalize_message_number(2) == "002"          # SAP affiche trois chiffres
    assert normalize_message_number("") == ""


def test_message_identity_a_la_forme_du_canal_rfc_et_reste_vide_sans_message():
    identity = message_identity("E", "MO                  ", "402",
                                "Table ZZ is not active", ["ZZ", "", ""])
    assert identity["identity"] == "MO/E/402"
    assert identity["class"] == "MO" and identity["number"] == "402"
    assert identity["parameters"] == ["ZZ"]                 # vides de queue retirés
    empty = message_identity("", "", "", "")
    assert empty["identity"] == "" and empty["type"] == ""   # jamais une identité inventée


def test_identity_matches_et_le_message_d_echec():
    identity = message_identity("E", "MO", "402", "texte localisé")
    assert identity_matches(identity, "mo", 402)
    assert identity_matches(identity, "MO", "402", "E")
    assert not identity_matches(identity, "MO", "410")
    assert not identity_matches(identity, "MO", "402", "S")
    assert "attendu MO/E/410, lu MO/E/402" in format_identity_mismatch(identity, "MO", "410", "E")
    assert "aucun message identifiable" in format_identity_mismatch(
        message_identity("", "", "", ""), "MO", "402")


class _StatusBar:
    def __init__(self, mtype="E", mid="MO                  ", number="402",
                 text="Table ZZ is not active", parameters=("ZZ",)):
        self.MessageType = mtype
        self.MessageId = mid
        self.MessageNumber = number
        self.Text = text
        self._parameters = list(parameters)

    def MessageParameter(self, index):  # noqa: N802 (API COM)
        if index >= len(self._parameters):
            raise com_error("index out of range")
        return self._parameters[index]


def _lib(sbar):
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = type("S", (), {"findById": lambda self, eid, raise_on_missing=True: sbar,
                                 "Busy": False})()
    return lib


def test_get_status_message_identity_lit_la_barre_et_status_message_should_be_asserte():
    lib = _lib(_StatusBar())
    identity = lib.get_status_message_identity()
    assert identity["identity"] == "MO/E/402" and identity["parameters"] == ["ZZ"]
    assert lib.status_message_should_be("MO", "402")["class"] == "MO"
    with pytest.raises(AssertionError, match="attendu MO/\\*/410, lu MO/E/402"):
        lib.status_message_should_be("MO", "410")
    with pytest.raises(AssertionError, match="aucun message identifiable"):
        _lib(_StatusBar("", "", "", "")).status_message_should_be("MO", "402")


def test_une_barre_sans_methode_parameter_rend_une_liste_vide():
    sbar = _StatusBar()
    del sbar._parameters
    sbar.MessageParameter = None
    assert _lib(sbar).get_status_message_identity()["parameters"] == []
