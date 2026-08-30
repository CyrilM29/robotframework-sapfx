"""Tests hors SAP des keywords du canal RFC ajoutés pour la campagne A4H.

Aucun `pyrfc`, aucun serveur : une doublure de connexion suffit à verrouiller
ce qui compte, c'est-à-dire ce qui part sur le réseau (paramètres de lecture),
ce qui n'y part JAMAIS (clause trop longue), et la façon dont un refus est
jugé (code technique, pas texte).
"""
import sys

import pytest
from robot.api.types import Secret

from SapApiLibrary import SapApiLibrary


class FakeRfcError(Exception):
    def __init__(self, key, message="refus simulé"):
        super().__init__(message)
        self.key = key
        self.message = message
        self.code = 5


class FakeConnection:
    """Doublure de ``pyrfc.Connection`` : enregistre les appels reçus."""

    def __init__(self, **params):
        self.params = params
        self.calls = []
        self.closed = False
        self.attributes = {"sysId": "A4H", "client": "001", "user": "DEVELOPER",
                           "partnerRel": "754", "kernelRel": 777}
        self.raises = None

    def get_connection_attributes(self):
        return self.attributes

    def call(self, name, **kwargs):
        self.calls.append((name, kwargs))
        if self.raises is not None:
            raise self.raises
        return {
            "FIELDS": [{"FIELDNAME": entry["FIELDNAME"]}
                       for entry in kwargs.get("FIELDS", [])],
            "DATA": [{"WA": "LH|Lufthansa"}, {"WA": "AA|American Airlines"}],
        }

    def close(self):
        self.closed = True


def _lib_with_connection(alias="a4h"):
    lib = SapApiLibrary()
    connection = FakeConnection()
    lib._rfc_connections()[alias] = connection
    return lib, connection


def _fake_pyrfc(monkeypatch, connection_factory=FakeConnection, version="3.3.1"):
    module = type(sys)("pyrfc")
    module.Connection = connection_factory
    module.__version__ = version
    monkeypatch.setitem(sys.modules, "pyrfc", module)
    return module


# --- préflight : le canal est-il là ---------------------------------------

def test_le_statut_du_canal_est_disponible_quand_pyrfc_s_importe(monkeypatch):
    _fake_pyrfc(monkeypatch)
    status = SapApiLibrary().get_rfc_channel_status()
    assert status["available"] is True and status["version"] == "3.3.1"


def test_un_import_qui_reussit_ne_suffit_pas_au_statut(monkeypatch):
    """Mesuré à la première exécution CI du préflight ``runtime_absent``
    (2026-08-29) : le ``__init__`` de pyrfc 3.3.1 AVALE l'échec de chargement
    du runtime natif (``except Exception: print``) et rend un module sans
    ``Connection``. Faire confiance à l'import déclarait le canal disponible
    exactement là où il ne l'est pas : le statut classe ``runtime_absent``."""
    module = type(sys)("pyrfc")
    module.__version__ = "3.3.1"          # pas de Connection : module avalé
    monkeypatch.setitem(sys.modules, "pyrfc", module)
    status = SapApiLibrary().get_rfc_channel_status()
    assert status["available"] is False
    assert status["reason"] == "runtime_absent"
    assert "install-rfc" in status["remediation"]


def test_l_ouverture_sur_un_binding_vide_nomme_cause_et_remede(monkeypatch):
    """Sans ce verdict, `Open Rfc Connection` sortait en ``AttributeError:
    module 'pyrfc' has no attribute 'Connection'``, qui ne nomme ni cause ni
    remède."""
    module = type(sys)("pyrfc")
    module.__version__ = "3.3.1"
    monkeypatch.setitem(sys.modules, "pyrfc", module)
    with pytest.raises(RuntimeError) as err:
        SapApiLibrary().open_rfc_connection(ashost="localhost")
    message = str(err.value)
    assert "runtime_absent" in message
    assert "install-rfc" in message


def test_le_statut_du_canal_n_echoue_jamais_et_nomme_le_remede(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyrfc", None)
    status = SapApiLibrary().get_rfc_channel_status()
    assert status["available"] is False
    assert status["remediation"]   # une suite peut se sauter en le citant


def test_la_variante_assertive_echoue_en_nommant_la_cause(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyrfc", None)
    with pytest.raises(AssertionError) as err:
        SapApiLibrary().rfc_channel_should_be_available()
    assert "Canal RFC indisponible" in str(err.value)


def test_la_variante_assertive_rend_le_statut_quand_le_canal_est_la(monkeypatch):
    _fake_pyrfc(monkeypatch)
    assert SapApiLibrary().rfc_channel_should_be_available()["available"] is True


# --- perception d'identité -------------------------------------------------

def test_les_attributs_de_connexion_sont_rendus_en_chaines():
    lib, _ = _lib_with_connection()
    attrs = lib.get_rfc_connection_attributes(alias="a4h")
    assert attrs["sysId"] == "A4H"
    # 777 arrive en entier de pyrfc selon les versions : l'état servi à un
    # agent doit rester homogène.
    assert attrs["kernelRel"] == "777"


def test_les_attributs_d_un_alias_inconnu_nomment_l_ouverture():
    with pytest.raises(RuntimeError) as err:
        SapApiLibrary().get_rfc_connection_attributes(alias="jamais-ouvert")
    assert "Open Rfc Connection" in str(err.value)


# --- lecture de table ------------------------------------------------------

def test_la_lecture_projette_borne_et_filtre():
    lib, connection = _lib_with_connection()
    rows = lib.read_rfc_table("SCARR", "carrid, carrname", alias="a4h",
                              options="CARRID EQ 'LH'", rowcount="2")
    name, params = connection.calls[0]
    assert name == "RFC_READ_TABLE"
    assert params["QUERY_TABLE"] == "SCARR"
    assert params["FIELDS"] == [{"FIELDNAME": "CARRID"}, {"FIELDNAME": "CARRNAME"}]
    assert params["OPTIONS"] == [{"TEXT": "CARRID EQ 'LH'"}]
    assert params["ROWCOUNT"] == 2
    assert rows[0] == {"CARRID": "LH", "CARRNAME": "Lufthansa"}


def test_une_structure_construite_par_robot_traverse_la_frontiere():
    # Le defaut trouve live le 2026-08-27 : pyrfc refuse une sous-classe de
    # dict pour un parametre de structure, et Robot n'en construit pas d'autre.
    class DotLike(dict):
        pass

    lib, connection = _lib_with_connection()
    lib.call_rfc("STFC_STRUCTURE", alias="a4h",
                 IMPORTSTRUCT=DotLike(RFCCHAR4="ABCD"))
    _, params = connection.calls[0]
    assert type(params["IMPORTSTRUCT"]) is dict


def test_la_lecture_accepte_aussi_des_listes():
    lib, connection = _lib_with_connection()
    lib.read_rfc_table("SCARR", ["CARRID", "CARRNAME"], alias="a4h",
                       options=["MANDT EQ '001'", "CARRID EQ 'LH'"])
    _, params = connection.calls[0]
    assert [clause["TEXT"] for clause in params["OPTIONS"]] == [
        "MANDT EQ '001'", "CARRID EQ 'LH'"]
    assert "ROWCOUNT" not in params   # 0 = toutes les lignes


def test_une_clause_trop_longue_n_atteint_jamais_le_reseau():
    lib, connection = _lib_with_connection()
    clause = "CARRID EQ 'LH' AND CARRNAME EQ 'Lufthansa' AND CURRCODE EQ 'EUR' " \
             "AND MANDT EQ '001'"
    assert len(clause) > 72
    with pytest.raises(ValueError) as err:
        lib.read_rfc_table("SCARR", "CARRID", alias="a4h", options=clause)
    assert "AND" in str(err.value)          # le remède est nommé
    assert connection.calls == []           # rien n'est parti


# --- refus jugés par leur code technique -----------------------------------

def test_le_code_attendu_rend_la_fiche_du_refus():
    lib, connection = _lib_with_connection()
    connection.raises = FakeRfcError("TABLE_NOT_AVAILABLE")
    fiche = lib.rfc_should_fail_with_code(
        "TABLE_NOT_AVAILABLE", "Read Rfc Table", "ZZ_ABSENTE", "MANDT", alias="a4h")
    assert fiche["code"] == "TABLE_NOT_AVAILABLE"


def test_un_autre_code_echoue_en_nommant_les_deux():
    lib, connection = _lib_with_connection()
    connection.raises = FakeRfcError("TABLE_WITHOUT_DATA")
    with pytest.raises(AssertionError) as err:
        lib.rfc_should_fail_with_code("TABLE_NOT_AVAILABLE", "Call Rfc",
                                      "RFC_READ_TABLE", alias="a4h")
    assert "TABLE_NOT_AVAILABLE" in str(err.value)
    assert "TABLE_WITHOUT_DATA" in str(err.value)


def test_un_appel_qui_reussit_est_un_echec_distinct():
    lib, _ = _lib_with_connection()
    with pytest.raises(AssertionError) as err:
        lib.rfc_should_fail_with_code("TABLE_NOT_AVAILABLE", "Read Rfc Table",
                                      "SCARR", "CARRID", alias="a4h")
    assert "réussi" in str(err.value)


def test_un_keyword_hors_perimetre_est_refuse_en_listant_les_valides():
    with pytest.raises(ValueError) as err:
        SapApiLibrary().rfc_should_fail_with_code("X", "Get Odata Count", "/x")
    assert "Read Rfc Table" in str(err.value)


# --- refus jugés par leur identifiant de message ---------------------------

def test_l_identifiant_de_message_attendu_rend_la_fiche_du_refus():
    lib, connection = _lib_with_connection()
    erreur = FakeRfcError("TABLE_NOT_AVAILABLE")
    erreur.msg_class, erreur.msg_type, erreur.msg_number = "DA", "E", "131"
    connection.raises = erreur
    fiche = lib.rfc_should_fail_with_message_id(
        "DA/E/131", "Read Rfc Table", "ZZ_ABSENTE", "MANDT", alias="a4h")
    # Les deux oracles se complètent : la même fiche porte les deux critères.
    assert fiche["message_id"] == "DA/E/131"
    assert fiche["code"] == "TABLE_NOT_AVAILABLE"


def test_un_autre_identifiant_echoue_en_nommant_les_deux():
    lib, connection = _lib_with_connection()
    erreur = FakeRfcError("TABLE_WITHOUT_DATA")
    erreur.msg_class, erreur.msg_type, erreur.msg_number = "AD", "E", "718"
    connection.raises = erreur
    with pytest.raises(AssertionError) as err:
        lib.rfc_should_fail_with_message_id("DA/E/131", "Read Rfc Table",
                                            "SCARR", "ZZ_CHAMP", alias="a4h")
    assert "DA/E/131" in str(err.value) and "AD/E/718" in str(err.value)


def test_un_refus_sans_identifiant_echoue_au_lieu_de_se_comparer_a_du_vide():
    # Le cas du refus levé côté client : lui demander un identifiant de
    # message doit échouer en le disant, pas passer parce que « vide == vide ».
    lib, connection = _lib_with_connection()
    connection.raises = FakeRfcError("RFC_INVALID_PARAMETER")
    with pytest.raises(AssertionError) as err:
        lib.rfc_should_fail_with_message_id("FL/E/046", "Call Rfc", "RFC_PING",
                                            alias="a4h")
    assert "aucun identifiant de message" in str(err.value)


def test_l_oracle_par_identifiant_distingue_aussi_l_appel_qui_reussit():
    lib, _ = _lib_with_connection()
    with pytest.raises(AssertionError) as err:
        lib.rfc_should_fail_with_message_id("DA/E/131", "Read Rfc Table",
                                            "SCARR", "CARRID", alias="a4h")
    assert "réussi" in str(err.value)


def test_un_refus_d_ouverture_traverse_le_mot_de_passe_secret(monkeypatch):
    vus = {}

    class RefusantConnection(FakeConnection):
        def __init__(self, **params):
            vus.update(params)
            raise FakeRfcError("RFC_LOGON_FAILURE", "Client 999 is not available")

    _fake_pyrfc(monkeypatch, RefusantConnection)
    lib = SapApiLibrary()
    fiche = lib.rfc_should_fail_with_code(
        "RFC_LOGON_FAILURE", "Open Rfc Connection", alias="ko", ashost="h",
        client="999", user="U", passwd=Secret("vrai-mot-de-passe"))
    assert fiche["code"] == "RFC_LOGON_FAILURE"
    # Le Secret a bien été déballé à la frontière : le refus porte donc sur le
    # mandant, pas sur un mot de passe mangé en route par le transport.
    assert vus["passwd"] == "vrai-mot-de-passe"
    assert lib.list_api_sessions()["rfc_connections"] == []


# --- jobs de fond : la perception qui évite de graver des noms -------------

class JobLogConnection(FakeConnection):
    """Doublure servant un journal de jobs : un job terminé, un annulé qui
    porte aussi des runs terminés, un dans le pipeline, un hors carte."""

    JOURNAL = ["ZFINI|F", "ZFINI|F", "ZANNULE|F", "ZANNULE|A",
               "ZPIPELINE|S", "ZINCONNU|Z"]

    def call(self, name, **kwargs):
        self.calls.append((name, kwargs))
        rows = self.JOURNAL
        if kwargs.get("ROWCOUNT"):
            rows = rows[:kwargs["ROWCOUNT"]]
        return {"FIELDS": kwargs.get("FIELDS", []),
                "DATA": [{"WA": row} for row in rows]}


def test_le_catalogue_des_cas_d_attente_est_lu_sur_la_cible():
    lib = SapApiLibrary()
    connection = JobLogConnection()
    lib._rfc_connections()["a4h"] = connection
    catalogue = lib.find_background_job_cases(alias="a4h")
    name, params = connection.calls[0]
    assert name == "RFC_READ_TABLE" and params["QUERY_TABLE"] == "TBTCO"
    assert "ROWCOUNT" not in params        # tout le journal par défaut
    assert catalogue["rows"] == 6
    assert catalogue["statuses"] == {"F": 3, "A": 1, "S": 1, "Z": 1}
    assert catalogue["jobs"]["ZANNULE"] == {"F": 1, "A": 1}
    assert catalogue["cases"]["done"] == ["ZFINI"]
    assert catalogue["cases"]["aborted_with_finished"] == ["ZANNULE"]
    assert catalogue["cases"]["pipeline"] == ["ZPIPELINE"]
    assert catalogue["cases"]["unmapped"] == ["ZINCONNU"]


def test_un_plafond_de_lecture_fausse_le_catalogue():
    # Le défaut de mesure que ce keyword existe pour empêcher : plafonnée, la
    # lecture ne voit que des runs terminés et fait conclure que la cible ne
    # porte que des jobs terminés. D'où rowcount=0 par défaut.
    lib = SapApiLibrary()
    lib._rfc_connections()["a4h"] = JobLogConnection()
    tronque = lib.find_background_job_cases(alias="a4h", rowcount=2)
    assert tronque["rows"] == 2
    assert tronque["statuses"] == {"F": 2}
    assert tronque["cases"]["aborted"] == []


def test_le_modele_de_statuts_dit_ce_qu_il_ne_cartographie_pas():
    modele = SapApiLibrary().get_background_job_status_model()
    assert modele["labels"]["A"] == "cancelled"
    assert "S" in modele["pending"] and "F" not in modele["pending"]
    # Le point du contrat : un statut hors carte est reconnaissable comme tel,
    # au lieu de recevoir un sens inventé.
    assert "Z" not in modele["labels"]


def test_une_ouverture_qui_reussit_par_erreur_ne_laisse_rien_ouvert(monkeypatch):
    _fake_pyrfc(monkeypatch)
    lib = SapApiLibrary()
    with pytest.raises(AssertionError):
        lib.rfc_should_fail_with_code("RFC_LOGON_FAILURE", "Open Rfc Connection",
                                      alias="ko", ashost="h")
    assert lib.list_api_sessions()["rfc_connections"] == []
