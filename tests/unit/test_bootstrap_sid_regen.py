"""Tests unitaires hors SAP/hors navigateur des keywords qui n'en avaient pas
(écarts relevés par l'audit) : amorçage du Logon Pad, connexion par chaîne,
lecture de cellule par titre, wrappers du moteur WebGUI ``sid``, et le
régénérateur du Recorder web. Convention #5 du CLAUDE.md."""
import pytest

from SapEccLibrary.keywords._connection import ConnectionKeywords
from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary
from SapFioriLibrary._ui5_js import sid_xpath

from test_logic import make_lib, _grid_lib


# --- Open Sap Logon / Close Sap Logon -----------------------------------------

class FakeProc:
    def __init__(self, running=True):
        self.pid = 4242
        self._running = running
        self.terminated = False

    def poll(self):
        return None if self._running else 0

    def terminate(self):
        self.terminated = True
        self._running = False

    def wait(self, timeout=None):
        return 0  # terminate() ci-dessus a déjà fait "sortir" le process simulé


def test_open_sap_logon_launches_exe_then_waits_for_engine(tmp_path, monkeypatch):
    import SapEccLibrary.keywords._connection as conn
    exe = tmp_path / "saplogon.exe"
    exe.write_text("")
    launched = []
    monkeypatch.setattr(conn.subprocess, "Popen",
                        lambda args, close_fds: (launched.append(args), FakeProc())[1])
    lib = make_lib(ConnectionKeywords)
    waited = []
    lib._wait_for_scripting_engine = lambda timeout: waited.append(timeout)
    lib.open_sap_logon(path=str(exe), timeout="5s")
    assert launched == [[str(exe)]]
    assert waited == ["5s"]
    assert isinstance(lib._saplogon_proc, FakeProc)


def test_close_sap_logon_terminates_only_own_process():
    lib = make_lib(ConnectionKeywords)
    proc = FakeProc(running=True)
    lib._saplogon_proc = proc
    lib.close_sap_logon()
    assert proc.terminated
    assert lib._saplogon_proc is None


def test_close_sap_logon_is_noop_without_own_process():
    lib = make_lib(ConnectionKeywords)
    lib._saplogon_proc = None
    lib.close_sap_logon()                      # ne doit pas lever


def test_close_sap_logon_skips_already_exited_process():
    lib = make_lib(ConnectionKeywords)
    proc = FakeProc(running=False)             # déjà terminé -> pas de terminate()
    lib._saplogon_proc = proc
    lib.close_sap_logon()
    assert not proc.terminated


def test_close_sap_logon_survives_process_that_wont_exit():
    import subprocess as _subprocess

    class StubbornProc(FakeProc):
        def wait(self, timeout=None):
            raise _subprocess.TimeoutExpired(cmd="saplogon.exe", timeout=timeout)

    lib = make_lib(ConnectionKeywords)
    proc = StubbornProc(running=True)
    lib._saplogon_proc = proc
    lib.close_sap_logon()                      # ne doit pas lever malgré le TimeoutExpired
    assert proc.terminated
    assert lib._saplogon_proc is None


# --- Open Connection By String -------------------------------------------------

class FakeChildren:
    def __init__(self, count):
        self.Count = count
        self._sessions = {0: "session-0"}

    def __call__(self, index):
        return self._sessions[index]


class FakeConnection:
    def __init__(self, count=1):
        self.Children = FakeChildren(count)


class FakeSapApp:
    def __init__(self, connection=None, error=None):
        self._connection = connection
        self._error = error
        self.opened_with = None

    def OpenConnectionByConnectionString(self, connection_string, sync):
        self.opened_with = (connection_string, sync)
        if self._error:
            raise self._error
        return self._connection


def test_open_connection_by_string_sets_session_when_ready():
    lib = make_lib(ConnectionKeywords, timeout=1.0)
    lib.sapapp = FakeSapApp(connection=FakeConnection(count=1))
    lib.open_connection_by_string("/H/vhcala4hci/S/3200")
    assert lib.sapapp.opened_with == ("/H/vhcala4hci/S/3200", True)
    assert lib.session == "session-0"


def test_open_connection_by_string_requires_scripting_engine():
    lib = make_lib(ConnectionKeywords)
    lib.sapapp = object()                      # pas de OpenConnectionByConnectionString
    with pytest.raises(Warning, match="Not connected to the scripting engine"):
        lib.open_connection_by_string("/H/host/S/3200")


def test_open_connection_by_string_wraps_com_errors():
    lib = make_lib(ConnectionKeywords)
    lib.sapapp = FakeSapApp(error=RuntimeError("partner not reached"))
    with pytest.raises(ValueError, match="Cannot open connection"):
        lib.open_connection_by_string("/H/down/S/3200")


def test_open_connection_by_string_times_out_without_session():
    lib = make_lib(ConnectionKeywords, timeout=0.3)
    lib.sapapp = FakeSapApp(connection=FakeConnection(count=0))   # jamais de session
    with pytest.raises(AssertionError, match="no session appeared"):
        lib.open_connection_by_string("/H/slow/S/3200")


# --- Get Cell Value By Column Title ---------------------------------------------

def test_get_cell_value_by_column_title_resolves_column_then_reads():
    lib = _grid_lib()
    assert lib.get_cell_value_by_column_title("grid", 1, "Name") == "Globex"


# --- wrappers du moteur WebGUI sid ----------------------------------------------

class FakeBrowser:
    def __init__(self):
        self.clicks = []
        self.fills = []
        self.waits = []

    def click(self, selector):
        self.clicks.append(selector)

    def fill_text(self, selector, text):
        self.fills.append((selector, text))

    def wait_for_elements_state(self, selector, state):
        self.waits.append((selector, state))


def _fiori(browser):
    lib = SapFioriLibrary(ui5_timeout="1s")
    lib._browser = lambda: browser
    return lib


def test_resolve_sid_returns_sid_xpath_selector():
    lib = _fiori(FakeBrowser())
    assert lib.resolve_sid("wnd[0]/usr/ctxtVBAK-VBELN") == sid_xpath("wnd[0]/usr/ctxtVBAK-VBELN")


def test_click_sid_clicks_resolved_selector():
    browser = FakeBrowser()
    _fiori(browser).click_sid("wnd[0]/tbar[0]/btn[0]")
    assert browser.clicks == [sid_xpath("wnd[0]/tbar[0]/btn[0]")]


def test_fill_sid_input_fills_resolved_selector():
    browser = FakeBrowser()
    _fiori(browser).fill_sid_input("wnd[0]/usr/ctxtX", "4711")
    assert browser.fills == [(sid_xpath("wnd[0]/usr/ctxtX"), "4711")]


def test_sid_should_be_visible_waits_on_visible_state():
    browser = FakeBrowser()
    _fiori(browser).sid_should_be_visible("wnd[0]/usr/ctxtX")
    (selector, state), = browser.waits
    assert selector == sid_xpath("wnd[0]/usr/ctxtX")
    # L'état part en ENUM quand Browser est installé : l'appel Python direct
    # (get_library_instance) ne bénéficie pas de la conversion d'arguments de
    # Robot, et l'API interne de Browser rejette la chaîne "visible" (KeyError
    # — attrapé live par fiori_hybrid_smoke). Sans Browser (CI unit), la
    # chaîne reste le repli — d'où la comparaison sur le NOM.
    assert getattr(state, "name", state) == "visible"


# --- regen_recorder : écrit le même contenu dans les deux cibles ----------------

def test_regen_recorder_writes_snippet_to_both_targets(tmp_path, monkeypatch):
    import SapFioriLibrary.regen_recorder as regen
    from SapFioriLibrary._ui5_js import spy_snippet

    targets = [str(tmp_path / "recorder_snippet.js"),
               str(tmp_path / "extension_recorder.js")]
    monkeypatch.setattr(regen, "TARGETS", targets)
    regen.main()
    contents = [open(t, encoding="utf-8").read() for t in targets]
    assert contents[0] == contents[1] == spy_snippet()
