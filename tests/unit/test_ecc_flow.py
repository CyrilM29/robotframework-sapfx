"""Tests end-to-end « hors SAP » du flux ECC, sur une session COM simulée.

Ils exercent le vrai enchaînement de keywords de SapEccLibrary — saisie, exécution
de transaction avec détection robuste *indépendante de la langue* (comparaison de
``session.Info.Transaction``, validée en live sur ABAP Platform A4H), et assertions
sur la barre de statut — sans serveur SAP ni COM Windows.
"""
import pytest

from SapEccLibrary import SapEccLibrary


# --- doublures (fakes) de l'API SAP GUI Scripting -----------------------------

class FakeField:
    """Champ texte : expose un attribut `text` modifiable."""
    def __init__(self, text=""):
        self.text = text


class FakeStatusBar:
    """Barre de statut : `messageType` ('S','W','E','I','A','') + `text`."""
    def __init__(self, message_type="", text=""):
        self.messageType = message_type
        self.text = text


class FakeWindow:
    """Fenêtre : enregistre les VKey envoyées via `sendVKey`."""
    def __init__(self):
        self.sent_vkeys = []

    def sendVKey(self, vkey):
        self.sent_vkeys.append(vkey)


class FakeInfo:
    """GuiSessionInfo minimal : expose la transaction active."""
    def __init__(self, transaction="SESSION_MANAGER"):
        self.Transaction = transaction


class FakeSession:
    """GuiSession minimale : résout `findById`, expose `Busy` et `Info`."""
    def __init__(self, objects, transaction="SESSION_MANAGER"):
        self._objects = objects
        self.Busy = False
        self.Info = FakeInfo(transaction)

    def findById(self, element_id, raise_on_missing=True):
        key = element_id.replace(" ", "")  # send_vkey vendored interroge "wnd[ 0]"
        if key in self._objects:
            return self._objects[key]
        if raise_on_missing:
            raise KeyError(element_id)
        return None


def make_lib(status_type="S", status_text="Données sauvegardées",
             current_tx="SESSION_MANAGER"):
    """Construit une instance SapEccLibrary branchée sur une session simulée.

    ``current_tx`` est la transaction que ``session.Info.Transaction`` renverra
    *après* l'exécution — pour simuler un succès (== tcode demandé) ou un échec
    (transaction inexistante : reste sur SESSION_MANAGER)."""
    window = FakeWindow()
    objects = {
        "wnd[0]/tbar[0]/okcd": FakeField(),
        "wnd[0]": window,
        "wnd[0]/sbar": FakeStatusBar(status_type, status_text),
    }
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(objects, transaction=current_tx)
    return lib, window, objects


# --- Run Transaction (override basé sur Info.Transaction) ----------------------

def test_run_transaction_ouvre_prefixe_n_et_envoie_entree():
    lib, window, objects = make_lib(current_tx="SE16")
    lib.run_transaction("SE16")
    assert objects["wnd[0]/tbar[0]/okcd"].text == "/nSE16"  # /n ajouté automatiquement
    assert window.sent_vkeys == ["0"]                       # Entrée envoyée


def test_run_transaction_transaction_inconnue_leve_une_erreur():
    # La transaction n'a pas démarré -> Info.Transaction reste SESSION_MANAGER.
    lib, _, _ = make_lib(status_type="S", status_text="Transaction ZZZNONE does not exist",
                         current_tx="SESSION_MANAGER")
    with pytest.raises(ValueError, match="ZZZNONE"):
        lib.run_transaction("ZZZNONE")


def test_run_transaction_skip_if_error_ne_leve_pas():
    lib, _, _ = make_lib(current_tx="SESSION_MANAGER")
    lib.run_transaction("ZZZNONE", skip_if_error=True)  # ne doit pas lever


def test_run_transaction_commande_systeme_retourne_tot():
    # '/nex' ne déclenche pas la vérification de transaction active.
    lib, window, _ = make_lib(current_tx="SESSION_MANAGER")
    lib.run_transaction("/nex")
    assert window.sent_vkeys == ["0"]


def test_run_transaction_prefixe_o_compare_sans_le_prefixe():
    # '/oSE16' (ouvrir dans une nouvelle session) : l'okcode passe tel quel et la
    # comparaison ignore le préfixe /o -> SE16 == SE16, pas d'erreur.
    lib, _, objects = make_lib(current_tx="SE16")
    lib.run_transaction("/oSE16")
    assert objects["wnd[0]/tbar[0]/okcd"].text == "/oSE16"


def test_run_transaction_prefixe_i_compare_sans_le_prefixe():
    # '/iSE38' : préfixe /i strippé pour la comparaison -> SE38 == SE38.
    lib, _, objects = make_lib(current_tx="SE38")
    lib.run_transaction("/iSE38")
    assert objects["wnd[0]/tbar[0]/okcd"].text == "/iSE38"


def test_run_transaction_namespace_tcode_recoit_bien_le_prefixe_n():
    # Régression : '/BEV1/RCA01' (tcode de namespace client, PAS un préfixe de
    # navigation) était traité comme déjà préfixé -> aucun '/n' n'était ajouté.
    lib, _, objects = make_lib(current_tx="BEV1/RCA01")
    lib.run_transaction("/BEV1/RCA01")
    assert objects["wnd[0]/tbar[0]/okcd"].text == "/n/BEV1/RCA01"


def test_run_transaction_prefixe_n_explicite_sur_tcode_namespace():
    # Un préfixe de navigation explicite + tcode de namespace doit aussi se
    # comparer correctement. NB : ce fake simule un retour SANS le '/' initial —
    # une tolérance ; la forme constatée live est AVEC (test suivant).
    lib, _, objects = make_lib(current_tx="BEV1/RCA01")
    lib.run_transaction("/n/BEV1/RCA01")
    assert objects["wnd[0]/tbar[0]/okcd"].text == "/n/BEV1/RCA01"  # inchangé, déjà préfixé


def test_run_transaction_namespace_quand_api_renvoie_le_slash_initial():
    # Forme VÉRIFIÉE LIVE (A4H, SAP GUI 8.00, 2026-07-21) : ``Info.Transaction``
    # rend le tcode de namespace AVEC son '/' initial (forme sy-tcode —
    # '/IWFND/MAINT_SERVICE' observé). La comparaison normalise les deux côtés
    # au lieu de parier sur une seule forme de l'API.
    lib, _, objects = make_lib(current_tx="/BEV1/RCA01")
    lib.run_transaction("/BEV1/RCA01")
    assert objects["wnd[0]/tbar[0]/okcd"].text == "/n/BEV1/RCA01"


def test_run_transaction_namespace_commencant_par_i_recoit_le_prefixe_n():
    # '/IWFND/MAINT_SERVICE' : les 2 premiers caractères ('/I') ressemblent au
    # préfixe /i, mais le reste ('WFND/MAINT_SERVICE') contient un '/' sans en
    # commencer -> c'est un namespace, pas un préfixe : /n doit être ajouté
    # (sans quoi SAP interprète l'OK-code brut comme la commande système /i).
    lib, _, objects = make_lib(current_tx="/IWFND/MAINT_SERVICE")
    lib.run_transaction("/IWFND/MAINT_SERVICE")
    assert objects["wnd[0]/tbar[0]/okcd"].text == "/n/IWFND/MAINT_SERVICE"


def test_run_transaction_prefixe_explicite_sur_namespace_commencant_par_i():
    # '/n/IWFND/...' : préfixe réel suivi d'un namespace en I — envoyé tel quel,
    # et la comparaison retire le préfixe PUIS les '/' de tête des deux côtés.
    lib, _, objects = make_lib(current_tx="IWFND/MAINT_SERVICE")
    lib.run_transaction("/n/IWFND/MAINT_SERVICE")
    assert objects["wnd[0]/tbar[0]/okcd"].text == "/n/IWFND/MAINT_SERVICE"


def test_get_current_transaction():
    lib, _, _ = make_lib(current_tx="SE16")
    assert lib.get_current_transaction() == "SE16"


# --- Input Password (override Secret-compatible) -------------------------------

class FakePasswordField(FakeField):
    """Champ mot de passe : `get_element_type` vendored lit l'attribut `type`."""
    type = "GuiPasswordField"


def test_input_password_deballe_un_secret_avant_la_frontiere_com():
    # RF 7.4 : `-v "SAP_PASSWORD: Secret:..."` livre un objet Secret au keyword ;
    # la valeur doit être déballée avant d'atteindre COM (le champ reçoit la
    # chaîne, jamais l'objet ni son masque '<secret>').
    from robot.api.types import Secret
    lib, _, objects = make_lib()
    objects["wnd[0]/usr/pwdRSYST-BCODE"] = FakePasswordField()
    lib.input_password("wnd[0]/usr/pwdRSYST-BCODE", Secret("s3cr3t"))
    assert objects["wnd[0]/usr/pwdRSYST-BCODE"].text == "s3cr3t"


def test_input_password_conserve_le_comportement_chaine():
    lib, _, objects = make_lib()
    objects["wnd[0]/usr/pwdRSYST-BCODE"] = FakePasswordField()
    lib.input_password("wnd[0]/usr/pwdRSYST-BCODE", "plain")
    assert objects["wnd[0]/usr/pwdRSYST-BCODE"].text == "plain"


# --- poll_interval configurable -------------------------------------------------

def test_poll_interval_defaults_to_a_tenth_of_a_second():
    assert SapEccLibrary(screenshots_on_error=False).poll_interval == 0.1


def test_poll_interval_accepts_a_custom_robot_time_string():
    lib = SapEccLibrary(screenshots_on_error=False, poll_interval="0.5s")
    assert lib.poll_interval == 0.5


def test_poll_interval_is_the_actual_sleep_step_used_by_wait_until_busy_done(monkeypatch):
    import sapfx_common.polling as polling_mod

    class AlwaysBusySession:
        Busy = True   # ne devient jamais libre -> sonde jusqu'au timeout

    sleeps = []
    monkeypatch.setattr(polling_mod.time, "sleep", lambda s: sleeps.append(s))
    lib = SapEccLibrary(screenshots_on_error=False, poll_interval="0.05s")
    lib.session = AlwaysBusySession()
    with pytest.raises(AssertionError, match="still busy"):
        lib.wait_until_busy_done(timeout="0.3s")
    assert sleeps
    assert all(s == 0.05 for s in sleeps)   # jamais le 0.1s de production en dur


# --- réglage dynamique des timeouts -------------------------------------------

def test_set_default_timeout_change_la_valeur_et_retourne_l_ancienne():
    lib = SapEccLibrary(screenshots_on_error=False, default_timeout="30s")
    old = lib.set_default_timeout("2 min")
    assert lib.default_timeout == 120.0
    assert old == "30 seconds"     # format Robot, redonnable tel quel au keyword


def test_set_default_timeout_l_ancienne_valeur_restaure_en_teardown():
    lib = SapEccLibrary(screenshots_on_error=False, default_timeout="45s")
    old = lib.set_default_timeout("1s")
    lib.set_default_timeout(old)
    assert lib.default_timeout == 45.0


def test_set_default_timeout_est_bien_le_repli_des_attentes():
    class AlwaysBusySession:
        Busy = True

    lib = SapEccLibrary(screenshots_on_error=False, default_timeout="10s",
                        poll_interval="0.01s")
    lib.session = AlwaysBusySession()
    lib.set_default_timeout("0.05s")
    with pytest.raises(AssertionError, match="still busy after 0.05"):
        lib.wait_until_busy_done()   # sans timeout explicite -> nouvelle valeur


def test_set_poll_interval_change_le_pas_et_retourne_l_ancien(monkeypatch):
    import sapfx_common.polling as polling_mod

    class AlwaysBusySession:
        Busy = True

    sleeps = []
    monkeypatch.setattr(polling_mod.time, "sleep", lambda s: sleeps.append(s))
    lib = SapEccLibrary(screenshots_on_error=False, poll_interval="0.1s")
    lib.session = AlwaysBusySession()
    old = lib.set_poll_interval("0.05s")
    assert old == "100 milliseconds"
    with pytest.raises(AssertionError, match="still busy"):
        lib.wait_until_busy_done(timeout="0.3s")
    assert sleeps
    assert all(s == 0.05 for s in sleeps)   # le nouveau pas, pas celui de l'import


# --- helpers de barre de statut ----------------------------------------------

def test_get_status_message_retourne_type_et_texte():
    lib, _, _ = make_lib(status_type="S", status_text="OK")
    assert lib.get_status_message() == ("S", "OK")


def test_status_message_should_be_success_ok_sur_S():
    lib, _, _ = make_lib(status_type="S")
    lib.status_message_should_be_success()  # ne doit pas lever


def test_status_message_should_be_success_leve_sur_E():
    lib, _, _ = make_lib(status_type="E", status_text="échec")
    with pytest.raises(AssertionError, match="success status"):
        lib.status_message_should_be_success()


# --- petit flux combiné -------------------------------------------------------

def test_flux_transaction_puis_assertion_succes():
    lib, window, objects = make_lib(status_type="S", status_text="Enregistré",
                                    current_tx="VA01")
    lib.run_transaction("VA01")
    lib.wait_until_busy_done(timeout="1s")  # Busy=False -> retour immédiat
    lib.status_message_should_be_success()
    assert lib.get_current_transaction() == "VA01"
    assert objects["wnd[0]/tbar[0]/okcd"].text == "/nVA01"
