"""Tests hors SAP du **registre de sessions par alias** (multi-session ECC) et
de ses rails de sûreté : affinité de thread COM STA, ``Secret`` aux frontières,
teardown isolé. Fake COM (convention #5), aucun serveur SAP ni pywin32 requis.
"""
import threading

import pytest
from robot.api.types import Secret

from SapEccLibrary import SapEccLibrary


# --- doublures (fakes) de l'API SAP GUI Scripting -----------------------------

class FakeField:
    def __init__(self, text=""):
        self.text = text


class FakeWindow:
    def __init__(self):
        self.sent_vkeys = []

    def sendVKey(self, vkey):
        self.sent_vkeys.append(vkey)


class FakeInfo:
    def __init__(self, user="DEVELOPER", system="A4H", client="001",
                 transaction="SESSION_MANAGER"):
        self.User = user
        self.SystemName = system
        self.Client = client
        self.Transaction = transaction


class FakeSession:
    """GuiSession minimale : login RSYST-*, Busy, Info, createSession."""

    def __init__(self, sid="/app/con[0]/ses[0]", connection=None, user="DEVELOPER"):
        self.Id = sid
        self.Busy = False
        self.Info = FakeInfo(user=user)
        self.connection = connection
        self._objects = {
            "wnd[0]": FakeWindow(),
            "wnd[0]/usr/txtRSYST-MANDT": FakeField(),
            "wnd[0]/usr/txtRSYST-BNAME": FakeField(),
            "wnd[0]/usr/pwdRSYST-BCODE": FakeField(),
            "wnd[0]/usr/txtRSYST-LANGU": FakeField(),
        }

    def findById(self, element_id, raise_on_missing=True):
        key = element_id.replace(" ", "")   # send_vkey vendored interroge "wnd[ 0]"
        if key in self._objects:
            return self._objects[key]
        if raise_on_missing:
            raise KeyError(element_id)
        return None

    def createSession(self):
        new = FakeSession("/app/con[0]/ses[%d]" % len(self.connection.sessions),
                          connection=self.connection)
        self.connection.sessions.append(new)


class FakeChildren:
    def __init__(self, sessions):
        self._sessions = sessions

    @property
    def Count(self):
        return len(self._sessions)

    def __call__(self, index):
        return self._sessions[index]


class FakeConnection:
    def __init__(self):
        self.sessions = []
        self.Children = FakeChildren(self.sessions)
        self.closed_session_ids = []
        self.closed = False

    def CloseSession(self, sid):
        self.closed_session_ids.append(sid)
        self.sessions[:] = [s for s in self.sessions if s.Id != sid]

    def CloseConnection(self):
        self.closed = True


class FakeSapApp:
    """Moteur de scripting : chaque OpenConnectionByConnectionString crée une
    connexion fraîche portant une session déjà prête."""

    def __init__(self):
        self.opened = []

    def OpenConnectionByConnectionString(self, connection_string, sync):
        self.opened.append(connection_string)
        connection = FakeConnection()
        connection.sessions.append(
            FakeSession("/app/con[%d]/ses[0]" % len(self.opened), connection=connection))
        return connection


def make_lib(**kwargs):
    kwargs.setdefault("screenshots_on_error", False)
    kwargs.setdefault("default_timeout", "1s")
    lib = SapEccLibrary(**kwargs)
    lib.sapapp = FakeSapApp()
    return lib


# --- compatibilité : la session historique vit dans l'alias "default" ----------

def test_default_alias_is_backward_compatible():
    lib = make_lib()
    assert lib.get_active_sap_session() == "default"
    session = FakeSession()
    lib.session = session
    assert lib.session is session
    entries = lib.list_sap_sessions()
    assert [e["alias"] for e in entries] == ["default"]
    assert entries[0]["active"] and entries[0]["connected"]


# --- Open Sap Session -----------------------------------------------------------

def test_open_sap_session_binds_alias_and_activates():
    lib = make_lib()
    lib.open_sap_session("erp_qa", connection_string="/H/hosta/S/3200")
    assert lib.get_active_sap_session() == "erp_qa"
    assert lib.session.Id == "/app/con[1]/ses[0]"
    assert lib.sapapp.opened == ["/H/hosta/S/3200"]


def test_open_sap_session_requires_exactly_one_target():
    lib = make_lib()
    with pytest.raises(ValueError, match="exactly one"):
        lib.open_sap_session("x")
    with pytest.raises(ValueError, match="exactly one"):
        lib.open_sap_session("x", connection_string="/H/a/S/3200",
                             connection_name="A4H entry")


def test_open_sap_session_rejects_duplicate_alias():
    lib = make_lib()
    lib.open_sap_session("erp", connection_string="/H/a/S/3200")
    with pytest.raises(ValueError, match="already connected"):
        lib.open_sap_session("erp", connection_string="/H/b/S/3200")


def test_open_sap_session_logs_in_and_unwraps_secret():
    lib = make_lib()
    lib.open_sap_session("erp", connection_string="/H/a/S/3200",
                         user="DEVELOPER", password=Secret("s3cr3t"),
                         client="001", language="EN")
    session = lib.session
    assert session.findById("wnd[0]/usr/txtRSYST-BNAME").text == "DEVELOPER"
    assert session.findById("wnd[0]/usr/pwdRSYST-BCODE").text == "s3cr3t"   # déballé
    assert session.findById("wnd[0]/usr/txtRSYST-MANDT").text == "001"
    assert session.findById("wnd[0]/usr/txtRSYST-LANGU").text == "EN"
    assert session.findById("wnd[0]").sent_vkeys == ["0"]                    # Entrée


def test_open_sap_session_failed_login_rolls_back_alias():
    lib = make_lib()

    class NotLoggedApp(FakeSapApp):
        def OpenConnectionByConnectionString(self, cs, sync):
            connection = super().OpenConnectionByConnectionString(cs, sync)
            connection.sessions[0].Info.User = ""     # login jamais complété
            return connection

    lib.sapapp = NotLoggedApp()
    with pytest.raises(AssertionError, match="did not complete"):
        lib.open_sap_session("erp", connection_string="/H/a/S/3200",
                             user="BADUSER", password="wrong")
    # rollback : pas d'alias fantôme, pas de bascule silencieuse
    assert lib.get_active_sap_session() == "default"
    assert "erp" not in [e["alias"] for e in lib.list_sap_sessions()
                         if e["connected"]]


def test_open_sap_session_failure_message_names_multi_logon_alternative():
    lib = make_lib()

    class NotLoggedApp(FakeSapApp):
        def OpenConnectionByConnectionString(self, cs, sync):
            connection = super().OpenConnectionByConnectionString(cs, sync)
            connection.sessions[0].Info.User = ""
            return connection

    lib.sapapp = NotLoggedApp()
    with pytest.raises(AssertionError, match="Create Gui Session"):
        lib.open_sap_session("erp", connection_string="/H/a/S/3200",
                             user="DEV", password="x")


# --- Create Gui Session (2e fenêtre, même connexion, sans re-login) -------------

def test_create_gui_session_branches_the_active_connection():
    lib = make_lib()
    lib.open_sap_session("erp", connection_string="/H/a/S/3200")
    base = lib.session
    lib.create_gui_session("verif")
    assert lib.get_active_sap_session() == "verif"
    assert lib.session is not base
    assert lib.session.connection is base.connection      # même connexion
    assert len(base.connection.sessions) == 2


def test_create_gui_session_requires_an_active_connection():
    lib = make_lib()
    with pytest.raises(AssertionError, match="No active SAP connection"):
        lib.create_gui_session("verif")


def test_create_gui_session_timeout_names_the_server_limit():
    lib = make_lib(default_timeout="0.1s")
    lib.open_sap_session("erp", connection_string="/H/a/S/3200")
    lib.session.createSession = lambda: None              # le serveur refuse (silencieux)
    with pytest.raises(AssertionError, match="rdisp/max_alt_modes"):
        lib.create_gui_session("verif")
    assert "verif" not in [e["alias"] for e in lib.list_sap_sessions()]


# --- Switch / List --------------------------------------------------------------

def test_switch_routes_state_per_alias():
    lib = make_lib()
    lib.open_sap_session("a", connection_string="/H/a/S/3200")
    lib.open_sap_session("b", connection_string="/H/b/S/3200")
    session_b = lib.session
    lib.switch_sap_session("a")
    assert lib.session.Id == "/app/con[1]/ses[0]"
    lib.switch_sap_session("b")
    assert lib.session is session_b


def test_switch_unknown_alias_lists_connected_aliases():
    lib = make_lib()
    lib.open_sap_session("erp", connection_string="/H/a/S/3200")
    with pytest.raises(ValueError) as err:
        lib.switch_sap_session("nope")
    assert "erp" in str(err.value)
    assert "Open Sap Session" in str(err.value)


def test_list_sap_sessions_is_json_safe_and_best_effort():
    lib = make_lib()
    lib.open_sap_session("erp", connection_string="/H/a/S/3200")
    del lib.session.Info                      # session « morte » : Info inaccessible
    entries = lib.list_sap_sessions()
    for entry in entries:
        for key, value in entry.items():
            assert isinstance(value, (str, bool)), (key, value)   # jamais d'objet COM
    erp = next(e for e in entries if e["alias"] == "erp")
    assert erp["connected"] and "system" not in erp               # best-effort


def test_list_sap_sessions_reports_session_info():
    lib = make_lib()
    lib.open_sap_session("erp", connection_string="/H/a/S/3200")
    erp = next(e for e in lib.list_sap_sessions() if e["alias"] == "erp")
    assert (erp["system"], erp["client"], erp["user"]) == ("A4H", "001", "DEVELOPER")


# --- Close : teardown isolé ------------------------------------------------------

def test_close_session_closes_only_that_window():
    lib = make_lib()
    lib.open_sap_session("erp", connection_string="/H/a/S/3200")
    connection = lib.session.connection
    lib.create_gui_session("verif")
    verif_id = lib.session.Id
    assert lib.close_sap_session("verif") is True
    assert connection.closed_session_ids == [verif_id]    # SEULE la fenêtre visée
    assert connection.closed is False                     # la connexion reste debout
    assert lib.get_active_sap_session() == "erp"          # bascule sur un alias restant
    assert lib.session.Id == "/app/con[1]/ses[0]"


def test_close_last_alias_falls_back_to_close_connection():
    lib = make_lib()
    lib.open_sap_session("erp", connection_string="/H/a/S/3200")
    connection = lib.session.connection

    def broken_close(sid):
        raise RuntimeError("CloseSession unavailable")
    connection.CloseSession = broken_close
    assert lib.close_sap_session("erp") is True
    assert connection.closed is True                      # dernier alias : connexion fermée


def test_close_never_closes_a_connection_still_shared():
    lib = make_lib()
    lib.open_sap_session("erp", connection_string="/H/a/S/3200")
    connection = lib.session.connection
    lib.create_gui_session("verif")

    def broken_close(sid):
        raise RuntimeError("CloseSession unavailable")
    connection.CloseSession = broken_close
    assert lib.close_sap_session("verif") is False        # best-effort : pas d'échec
    assert connection.closed is False                     # 'erp' l'utilise encore


def test_close_unknown_alias_fails_with_known_list():
    lib = make_lib()
    with pytest.raises(ValueError, match="Unknown or unbound"):
        lib.close_sap_session("nope")


def test_close_all_sap_sessions_resets_to_default():
    lib = make_lib()
    lib.open_sap_session("a", connection_string="/H/a/S/3200")
    lib.open_sap_session("b", connection_string="/H/b/S/3200")
    closed = lib.close_all_sap_sessions()
    assert sorted(closed) == ["a", "b"]
    assert lib.get_active_sap_session() == "default"
    assert not any(e["connected"] for e in lib.list_sap_sessions())


# --- rail de sûreté : affinité de thread COM (STA) -------------------------------

def _read_session_in_thread(lib):
    outcome = []

    def worker():
        try:
            _ = lib.session
            outcome.append("ok")
        except RuntimeError as err:
            outcome.append(err)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    return outcome[0]


def test_cross_thread_access_is_allowed_by_default(monkeypatch):
    monkeypatch.delenv("SAPFX_STRICT_COM_THREAD", raising=False)
    lib = make_lib()
    lib.session = FakeSession()
    assert _read_session_in_thread(lib) == "ok"           # marshaling : mode rf-mcp


def test_strict_mode_refuses_cross_thread_access(monkeypatch):
    monkeypatch.setenv("SAPFX_STRICT_COM_THREAD", "1")
    lib = make_lib()
    lib.session = FakeSession()
    outcome = _read_session_in_thread(lib)
    assert isinstance(outcome, RuntimeError)
    assert "Switch Sap Session" in str(outcome)           # erreur actionnable, pas RPC_E_WRONG_THREAD


def test_strict_mode_rebind_takes_thread_ownership(monkeypatch):
    monkeypatch.setenv("SAPFX_STRICT_COM_THREAD", "1")
    lib = make_lib()
    outcome = []

    def worker():
        lib.session = FakeSession()       # re-bind volontaire depuis CE thread
        try:
            _ = lib.session
            outcome.append("ok")
        except RuntimeError as err:
            outcome.append(err)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert outcome[0] == "ok"
    with pytest.raises(RuntimeError):     # le main thread n'est plus propriétaire
        _ = lib.session
