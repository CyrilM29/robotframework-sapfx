"""Tests hors SAP de la logique pure du canal RFC (``sapfx_common.rfc_channel``).

Deux jobs, tous deux vérifiables sans `pyrfc` ni serveur : classer une absence
du canal (et nommer SON remède), et classer un refus par son code technique
plutôt que par son texte.
"""
import pytest

from sapfx_common import rfc_channel


class FakeRfcError(Exception):
    """Doublure d'une exception pyrfc : c'est ``key`` qui porte le code, et
    ``msg_class``/``msg_type``/``msg_number`` l'identifiant de message des
    refus APPLICATIFS (un refus du runtime client n'en porte aucun)."""

    def __init__(self, key, message, code=5, msg_class=None, msg_type=None,
                 msg_number=None):
        super().__init__(message)
        self.key = key
        self.message = message
        self.code = code
        if msg_class is not None:
            self.msg_class = msg_class
            self.msg_type = msg_type
            self.msg_number = msg_number


# --- absence du canal : deux causes, deux remèdes -------------------------

def test_module_absent_renvoie_vers_l_installation_du_binding():
    verdict = rfc_channel.classify_import_failure(
        ModuleNotFoundError("No module named 'pyrfc'", name="pyrfc"))
    assert verdict["reason"] == "module_absent"
    assert "pyrfc==3.3.1" in verdict["remediation"]
    assert rfc_channel.PYTHON_FLOOR in verdict["remediation"]


def test_runtime_natif_absent_renvoie_vers_le_provisionnement_du_sdk():
    verdict = rfc_channel.classify_import_failure(
        ImportError("DLL load failed while importing _cyrfc: introuvable."))
    assert verdict["reason"] == "runtime_absent"
    assert "install-rfc.ps1" in verdict["remediation"]


def test_runtime_natif_absent_aussi_sur_la_forme_posix():
    verdict = rfc_channel.classify_import_failure(
        ImportError("libsapnwrfc.so: cannot open shared object file"))
    assert verdict["reason"] == "runtime_absent"


def test_autre_echec_d_import_reste_rendu_tel_quel():
    verdict = rfc_channel.classify_import_failure(
        RuntimeError("codepage table incompatible"))
    assert verdict["reason"] == "import_failed"
    assert "codepage" in verdict["detail"]


def test_les_deux_etats_sont_json_safe_et_de_meme_forme():
    indisponible = rfc_channel.unavailable_status(
        ModuleNotFoundError("No module named 'pyrfc'", name="pyrfc"))
    disponible = rfc_channel.available_status("3.3.1")
    assert set(indisponible) == set(disponible)
    assert indisponible["available"] is False and disponible["available"] is True
    assert disponible["version"] == "3.3.1"


# --- refus : le code technique, jamais le texte ---------------------------

def test_le_code_technique_est_lu_dans_la_cle_de_l_exception():
    err = FakeRfcError("TABLE_NOT_AVAILABLE", "ID:DA Type:E Number:131 ZZ")
    assert rfc_channel.rfc_error_code(err) == "TABLE_NOT_AVAILABLE"


def test_une_erreur_sans_code_technique_ne_s_en_invente_pas():
    # Les gardes propres à la bibliothèque (alias jamais ouvert, clause trop
    # longue) n'ont pas de code serveur : les confondre avec un refus SAP
    # rendrait un oracle de refus vert sur la mauvaise cause.
    assert rfc_channel.rfc_error_code(RuntimeError("Aucune connexion RFC")) == ""


def test_la_fiche_d_un_refus_porte_classe_code_et_texte():
    fiche = rfc_channel.describe_rfc_error(
        FakeRfcError("RFC_LOGON_FAILURE", "Name or password is incorrect", code=2))
    assert fiche == {"class": "FakeRfcError", "code": "RFC_LOGON_FAILURE",
                     "numeric_code": 2,
                     "message": "Name or password is incorrect",
                     "message_class": "", "message_type": "",
                     "message_number": "", "message_id": ""}


# --- refus : l'identifiant de message, plus fin et tout aussi non localisé -

def test_un_refus_applicatif_porte_son_identifiant_de_message():
    # Relevé live (ABAP Platform 2023, 2026-08-28) : une table absente est
    # refusée par le message DA/E/131. Le code, lui, dirait seulement
    # TABLE_NOT_AVAILABLE.
    identite = rfc_channel.rfc_message_identity(
        FakeRfcError("TABLE_NOT_AVAILABLE", "ZZ_TABLE", msg_class="DA",
                     msg_type="E", msg_number="131"))
    assert identite == {"message_class": "DA", "message_type": "E",
                        "message_number": "131", "message_id": "DA/E/131"}


def test_un_refus_du_runtime_client_n_invente_aucun_identifiant():
    # Mesuré live : RFC_INVALID_PARAMETER est levé côté client, sans jamais
    # atteindre l'application, donc sans message ABAP. Lui prêter un
    # identifiant serait inventer une preuve.
    identite = rfc_channel.rfc_message_identity(
        FakeRfcError("RFC_INVALID_PARAMETER", "field ZZ not found", code=20))
    assert identite["message_id"] == ""
    assert identite["message_class"] == ""


def test_un_identifiant_partiel_ne_devient_pas_un_identifiant():
    identite = rfc_channel.rfc_message_identity(
        FakeRfcError("X", "m", msg_class="DA", msg_type="E", msg_number=""))
    assert identite["message_id"] == ""
    assert identite["message_class"] == "DA"


def test_le_message_d_ecart_d_identifiant_nomme_les_deux_et_le_code():
    message = rfc_channel.format_message_id_mismatch(
        "L'appel « Read Rfc Table »", "DA/E/131",
        FakeRfcError("TABLE_WITHOUT_DATA", "SCARR", msg_class="AD",
                     msg_type="E", msg_number="718"))
    assert "DA/E/131" in message and "AD/E/718" in message
    assert "TABLE_WITHOUT_DATA" in message


def test_l_ecart_d_identifiant_dit_quand_il_n_y_en_a_aucun():
    message = rfc_channel.format_message_id_mismatch(
        "L'appel « Call Rfc »", "FL/E/046",
        FakeRfcError("RFC_INVALID_PARAMETER", "field ZZ", code=20))
    assert "aucun identifiant de message" in message


def test_le_message_d_ecart_nomme_les_deux_codes():
    message = rfc_channel.format_code_mismatch(
        "L'appel « Read Rfc Table »", "TABLE_NOT_AVAILABLE",
        FakeRfcError("TABLE_WITHOUT_DATA", "ID:AD Type:E Number:718 SCARR"))
    assert "TABLE_NOT_AVAILABLE" in message and "TABLE_WITHOUT_DATA" in message
    assert "FakeRfcError" in message


def test_le_message_d_absence_de_refus_dit_que_rien_n_a_echoue():
    message = rfc_channel.format_missing_failure(
        "L'appel « Call Rfc »", "FU_NOT_FOUND")
    assert "FU_NOT_FOUND" in message and "réussi" in message


# --- frontière Robot vers pyrfc -------------------------------------------

class DotLike(dict):
    """Ce que Robot Framework construit : une SOUS-CLASSE de dict.

    ``pyrfc`` contrôle le type exact d'un paramètre de structure, donc il la
    refuse. Sans normalisation, aucune suite ne peut passer de structure.
    """


def test_une_sous_classe_de_dict_redevient_un_dict_nu():
    normalise = rfc_channel.plain_rfc_value(DotLike(RFCCHAR4="ABCD"))
    assert normalise == {"RFCCHAR4": "ABCD"}
    assert type(normalise) is dict


def test_la_normalisation_descend_dans_les_tables_et_les_structures():
    entree = DotLike(TABLE=[DotLike(A="1"), DotLike(B=DotLike(C="2"))])
    normalise = rfc_channel.plain_rfc_value(entree)
    assert type(normalise["TABLE"]) is list
    assert type(normalise["TABLE"][0]) is dict
    assert type(normalise["TABLE"][1]["B"]) is dict


def test_aucun_scalaire_n_est_converti_au_passage():
    # « 0400 » est un numéro de liaison, pas l'entier 400 : une conversion
    # « intelligente » corromprait tous les champs caractère numériques du
    # dictionnaire ABAP.
    params = rfc_channel.plain_rfc_parameters(
        DotLike(CONNID="0400", MAX_ROWS=3, PRICE=1.5, RAW=b"\x01"))
    assert params == {"CONNID": "0400", "MAX_ROWS": 3, "PRICE": 1.5,
                      "RAW": b"\x01"}
    assert isinstance(params["CONNID"], str)


@pytest.mark.parametrize("valeur", ["", None, 0])
def test_une_cle_vide_vaut_absence_de_code(valeur):
    err = FakeRfcError("x", "m")
    err.key = valeur
    assert rfc_channel.rfc_error_code(err) == ""
