"""Tests unitaires hors SAP pour la logique déterministe ajoutée par le fork.

Ces tests exercent les mixins directement contre de faux objets COM — sans SAP,
sans COM Windows, sans exécuteur Robot Framework. Ils valident le *nouveau*
comportement (attentes, relance, grille par titre, vérification de transaction
indépendante de la locale), et non le code vendeur amont.
"""

import pytest

from SapEccLibrary.keywords._connection import ConnectionKeywords
from SapEccLibrary.keywords._grid import GridKeywords
from SapEccLibrary.keywords._waits import WaitKeywords


# --- faux objets -------------------------------------------------------------

class FakeGrid:
    def __init__(self):
        self.ColumnOrder = ["MANDT", "MTEXT"]
        self._titles = {"MANDT": "Client", "MTEXT": "Name"}
        self._cells = {(0, "MANDT"): "100", (0, "MTEXT"): "Acme",
                       (1, "MANDT"): "200", (1, "MTEXT"): "Globex"}
        self.RowCount = 2
        self.VisibleRowCount = 1          # fenêtre de lazy-loading
        self.selected = None
        self.loaded = []                  # historique des FirstVisibleRow positionnés
        self._first = 0

    @property
    def FirstVisibleRow(self):
        return self._first

    @FirstVisibleRow.setter
    def FirstVisibleRow(self, value):
        self._first = value
        self.loaded.append(value)

    def GetDisplayedColumnTitle(self, col_id):
        return self._titles[col_id]

    def GetCellValue(self, row, col_id):
        return self._cells[(row, col_id)]

    def set_cell(self, row, col_id, text):
        self._cells[(row, col_id)] = text


class FakeSession:
    """GuiSession minimal : un drapeau ``Busy`` qui bascule, plus une recherche id->objet."""
    def __init__(self, busy_polls=0, objects=None):
        self._busy_remaining = busy_polls
        self._objects = objects or {}

    @property
    def Busy(self):
        if self._busy_remaining > 0:
            self._busy_remaining -= 1
            return True
        return False

    def findById(self, element_id, raise_on_missing=True):
        if element_id in self._objects:
            return self._objects[element_id]
        if raise_on_missing:
            raise KeyError(element_id)
        return None


def make_lib(*mixins, session=None, timeout=2.0, poll_interval=0.01):
    """Construit une instance de bibliothèque jetable à partir des mixins donnés,
    avec les attributs minimaux qu'ils lisent (`session`, `default_timeout`,
    `poll_interval`, `take_screenshot`). ``poll_interval`` par défaut à 10ms
    (au lieu des 0.1s de production) pour que les tests de timeout restent rapides."""
    cls = type("TestLib", tuple(mixins), {})
    lib = cls()
    lib.session = session
    lib.default_timeout = timeout
    lib.poll_interval = poll_interval
    lib.take_screenshot = lambda *a, **k: None
    return lib


# --- attentes ----------------------------------------------------------------

def test_wait_until_busy_done_returns_when_idle():
    lib = make_lib(WaitKeywords, session=FakeSession(busy_polls=2))
    lib.wait_until_busy_done(timeout="2s")  # bascule vers non-occupé après 2 sondages


def test_wait_until_busy_done_times_out():
    lib = make_lib(WaitKeywords, session=FakeSession(busy_polls=10_000))
    with pytest.raises(AssertionError, match="still busy"):
        lib.wait_until_busy_done(timeout="0.3s")


def test_wait_until_element_present_found():
    session = FakeSession(objects={"wnd[0]/usr/x": object()})
    lib = make_lib(WaitKeywords, session=session)
    assert lib.wait_until_element_present("wnd[0]/usr/x", timeout="1s") is not None


def test_wait_until_element_present_times_out():
    lib = make_lib(WaitKeywords, session=FakeSession(objects={}))
    with pytest.raises(AssertionError, match="did not appear"):
        lib.wait_until_element_present("missing", timeout="0.3s")


def test_wait_until_element_value_is_returns_when_value_matches():
    lib = make_lib(WaitKeywords, session=FakeSession(objects={"f": object()}))
    lib.get_value = lambda element_id: "DONE"
    lib.wait_until_element_value_is("f", "DONE", timeout="1s")  # ne doit pas lever


def test_wait_until_element_value_is_times_out_on_mismatch():
    lib = make_lib(WaitKeywords, session=FakeSession(objects={"f": object()}))
    lib.get_value = lambda element_id: "OTHER"
    with pytest.raises(AssertionError, match="expected 'DONE'"):
        lib.wait_until_element_value_is("f", "DONE", timeout="0.3s")


# --- grille ------------------------------------------------------------------

def _grid_lib():
    grid = FakeGrid()
    session = FakeSession(objects={"grid": grid})
    lib = make_lib(GridKeywords, session=session)
    # GridKeywords s'appuie sur des helpers amont ; on substitue ceux qu'il appelle.
    lib.element_should_be_present = lambda element_id, message=None: None
    lib.get_cell_value = lambda table_id, row, col: session.findById(table_id).GetCellValue(row, col)
    lib.set_cell_value = lambda table_id, row, col, text: session.findById(table_id).set_cell(row, col, text)
    lib.select_table_row = lambda table_id, row: setattr(session.findById(table_id), "selected", row)
    return lib


def test_get_column_id_by_title_is_case_insensitive():
    lib = _grid_lib()
    assert lib.get_column_id_by_title("grid", "name") == "MTEXT"


def test_get_column_id_by_title_unknown_lists_available():
    lib = _grid_lib()
    with pytest.raises(ValueError, match="No column titled"):
        lib.get_column_id_by_title("grid", "Nonexistent")


def test_read_grid_returns_dicts_keyed_by_title():
    lib = _grid_lib()
    rows = lib.read_grid("grid")
    assert rows == [
        {"Client": "100", "Name": "Acme"},
        {"Client": "200", "Name": "Globex"},
    ]


def test_read_grid_respects_max_rows():
    lib = _grid_lib()
    assert len(lib.read_grid("grid", max_rows=1)) == 1


def test_set_cell_value_by_column_title_resolves_column_then_writes():
    lib = _grid_lib()
    lib.set_cell_value_by_column_title("grid", 0, "Name", "Zzz")
    assert lib.session.findById("grid").GetCellValue(0, "MTEXT") == "Zzz"


def test_find_row_by_column_value_exact_and_case_insensitive():
    lib = _grid_lib()
    assert lib.find_row_by_column_value("grid", "Name", "Globex") == 1
    assert lib.find_row_by_column_value("grid", "Name", "absent") == -1
    # par défaut sensible à la casse ; option insensible
    assert lib.find_row_by_column_value("grid", "Name", "globex") == -1
    assert lib.find_row_by_column_value("grid", "Name", "globex", ignore_case=True) == 1


def test_select_row_by_column_value_selects_and_returns_index():
    lib = _grid_lib()
    assert lib.select_row_by_column_value("grid", "Client", "200") == 1
    assert lib.session.findById("grid").selected == 1


def test_select_row_by_column_value_raises_when_absent():
    lib = _grid_lib()
    with pytest.raises(ValueError, match="'Name' = 'nope'"):
        lib.select_row_by_column_value("grid", "Name", "nope")


def test_get_cell_value_by_row_content_addresses_the_row_by_its_content():
    # l'adressage « contenu @ colonne » : aucun index de ligne dans le test
    lib = _grid_lib()
    assert lib.get_cell_value_by_row_content("grid", "Name", "Globex", "Client") == "200"
    assert lib.get_cell_value_by_row_content("grid", "Client", "100", "Name") == "Acme"


def test_get_cell_value_by_row_content_raises_when_no_row_matches():
    lib = _grid_lib()
    with pytest.raises(ValueError, match="'Name' = 'nope'"):
        lib.get_cell_value_by_row_content("grid", "Name", "nope", "Client")


def test_read_full_grid_pages_through_window_then_reads_all():
    lib = _grid_lib()
    rows = lib.read_full_grid("grid")
    grid = lib.session.findById("grid")
    # parcouru par fenêtres de VisibleRowCount(=1) -> positions 0 puis 1 visitées
    assert 0 in grid.loaded and 1 in grid.loaded
    assert grid.FirstVisibleRow == 0          # position initiale restaurée
    assert rows == [
        {"Client": "100", "Name": "Acme"},
        {"Client": "200", "Name": "Globex"},
    ]


def test_read_full_grid_respects_explicit_page_step():
    lib = _grid_lib()
    lib.read_full_grid("grid", page_step=2)   # fenêtre explicite > VisibleRowCount(=1)
    grid = lib.session.findById("grid")
    # une seule fenêtre (pas de fenêtre) -> seule la position 0 est visitée
    assert grid.loaded == [0, 0]              # position initiale, puis restauration


def test_read_full_grid_respects_max_rows():
    lib = _grid_lib()
    rows = lib.read_full_grid("grid", max_rows=1)
    grid = lib.session.findById("grid")
    # total plafonné à 1 -> une seule fenêtre balayée (position 0 uniquement)
    assert grid.loaded == [0, 0]
    assert rows == [{"Client": "100", "Name": "Acme"}]


def test_get_grid_column_ids_returns_technical_ids_in_display_order():
    lib = _grid_lib()
    assert lib.get_grid_column_ids("grid") == ["MANDT", "MTEXT"]


def test_grid_raises_value_error_when_element_is_not_an_alv_grid():
    lib = _grid_lib()
    lib.session._objects["not_a_grid"] = object()   # pas de ColumnOrder
    with pytest.raises(ValueError, match="not an ALV GridView"):
        lib.get_grid_column_ids("not_a_grid")


# --- retry sur clic (synchronisation) ----------------------------------------

def test_click_element_with_retry_succeeds_after_transient_failure():
    lib = make_lib(WaitKeywords, session=FakeSession(objects={"btn": object()}))
    calls = {"n": 0}

    def flaky(element_id):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("element not ready")

    lib.click_element = flaky
    lib.click_element_with_retry("btn", retries=3, interval="0.01s")
    assert calls["n"] == 2                     # a réussi au 2e essai


def test_click_element_with_retry_gives_up_when_never_present():
    lib = make_lib(WaitKeywords, session=FakeSession(objects={}))
    lib.click_element = lambda element_id: None
    with pytest.raises(AssertionError, match="Could not click"):
        lib.click_element_with_retry("missing", retries=2, interval="0.01s")


# --- connexion ---------------------------------------------------------------

def test_resolve_saplogon_path_prefers_explicit(tmp_path):
    exe = tmp_path / "saplogon.exe"
    exe.write_text("")
    lib = make_lib(ConnectionKeywords)
    assert lib._resolve_saplogon_path(str(exe)) == str(exe)


def test_resolve_saplogon_path_raises_when_missing(monkeypatch):
    # Déterministe quel que soit l'environnement : on neutralise les chemins par
    # défaut et la variable SAPLOGON_PATH (sinon, sur une machine où SAP GUI est
    # installé, le fallback trouverait le vrai saplogon.exe et ne lèverait pas).
    import SapEccLibrary.keywords._connection as conn
    monkeypatch.setattr(conn, "_DEFAULT_SAPLOGON_PATHS", ())
    monkeypatch.delenv("SAPLOGON_PATH", raising=False)
    lib = make_lib(ConnectionKeywords)
    with pytest.raises(ValueError, match="Could not locate saplogon"):
        lib._resolve_saplogon_path(r"C:\nope\saplogon.exe")


def test_connect_with_retry_succeeds_after_failures():
    lib = make_lib(ConnectionKeywords)
    calls = {"n": 0}

    def flaky(explicit_wait=0):
        calls["n"] += 1
        if calls["n"] < 3:
            raise Warning("not ready")

    lib.connect_to_session = flaky
    lib.connect_to_session_with_retry(retries=5, retry_interval="0.01s")
    assert calls["n"] == 3


def test_connect_with_retry_gives_up():
    lib = make_lib(ConnectionKeywords)

    def always_fail(explicit_wait=0):
        raise Warning("nope")

    lib.connect_to_session = always_fail
    with pytest.raises(AssertionError, match="after 2 attempts"):
        lib.connect_to_session_with_retry(retries=2, retry_interval="0.01s")


class _FakeComCollection:
    """Collection COM factice : ``Count`` + appel par index (style ``Children(0)``)."""
    def __init__(self, items):
        self._items = items

    @property
    def Count(self):
        return len(self._items)

    def __call__(self, index):
        return self._items[index]


class _FakeOpenConnection:
    def __init__(self, sessions):
        self.Children = _FakeComCollection(sessions)


class _FakeEngine:
    def __init__(self, connections):
        self.Children = _FakeComCollection(connections)


def test_attach_to_open_session_binds_connection_and_session_by_index():
    # Le prérequis de replay des suites générées par le recorder : Connect To
    # Session n'obtient que le moteur — Attach To Open Session complète la
    # chaîne connection/session par index (découvert par le replay live d'un
    # export, 2026-07-19).
    lib = make_lib(ConnectionKeywords)
    session_a, session_b = object(), object()
    conn = _FakeOpenConnection([session_a, session_b])
    lib.connect_to_session = lambda: setattr(lib, "sapapp", _FakeEngine([conn]))
    lib.attach_to_open_session()
    assert lib.connection is conn
    assert lib.session is session_a
    lib.attach_to_open_session(session_index=1)
    assert lib.session is session_b


def test_attach_to_open_session_errors_are_actionable():
    lib = make_lib(ConnectionKeywords)
    lib.connect_to_session = lambda: setattr(lib, "sapapp", _FakeEngine([]))
    with pytest.raises(RuntimeError, match="Aucune connexion SAP GUI ouverte"):
        lib.attach_to_open_session()
    empty_conn = _FakeOpenConnection([])
    lib.connect_to_session = lambda: setattr(lib, "sapapp", _FakeEngine([empty_conn]))
    with pytest.raises(RuntimeError, match="pas de session"):
        lib.attach_to_open_session()


class _FakeBase:
    """Base factice exposant le connect_to_session que l'override doit appeler."""
    def connect_to_session(self, explicit_wait=0):
        self.delegated_wait = explicit_wait
        return "delegated"


def test_connect_to_session_coinitialise_puis_delegue(monkeypatch):
    # L'override doit initialiser COM sur le thread courant (indispensable quand
    # rf-mcp exécute le keyword hors du thread principal) puis déléguer à la base.
    import pythoncom
    calls = []
    monkeypatch.setattr(pythoncom, "CoInitialize", lambda: calls.append(1), raising=False)
    lib = make_lib(ConnectionKeywords, _FakeBase)
    result = lib.connect_to_session(5)
    assert calls == [1]
    assert result == "delegated"
    assert lib.delegated_wait == 5


def test_connect_to_session_tolere_coinitialize_absent(monkeypatch):
    # En run Robot classique (ou stub de test sans CoInitialize), l'absence/échec de
    # CoInitialize est avalé et la délégation a quand même lieu.
    import pythoncom
    monkeypatch.delattr(pythoncom, "CoInitialize", raising=False)
    lib = make_lib(ConnectionKeywords, _FakeBase)
    assert lib.connect_to_session() == "delegated"
