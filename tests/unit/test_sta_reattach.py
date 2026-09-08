"""Tests hors SAP du rail STA **ré-attachant** (2026-09-07) : depuis un thread
étranger, ``lib.session`` rend un proxy ré-acquis via le moteur de scripting
(``FindById`` de l'id mémorisé au bind), mis en cache par thread ; sur le
thread propriétaire l'objet d'origine ; sans moteur, repli défensif ; en mode
strict, refus actionnable."""
import threading

import pytest

from SapEccLibrary import SapEccLibrary


class FakeSession:
    def __init__(self, sid="/app/con[0]/ses[0]"):
        self.Id = sid


class FakeEngine:
    def __init__(self):
        self.found = []

    def FindById(self, session_id):
        self.found.append(session_id)
        return ("proxy", session_id, threading.get_ident())


def _run_in_thread(fn):
    box = {}

    def worker():
        try:
            box["value"] = fn()
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc
    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(5)
    if "error" in box:
        raise box["error"]
    return box["value"]


def test_le_thread_proprietaire_recoit_l_objet_d_origine():
    lib = SapEccLibrary(screenshots_on_error=False)
    session = FakeSession()
    lib.session = session
    assert lib.session is session


def test_un_thread_etranger_recoit_un_proxy_reattache_et_mis_en_cache():
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession()
    engine = FakeEngine()
    lib._acquire_scripting_engine = lambda: engine
    first = _run_in_thread(lambda: (lib.session, lib.session))
    assert first[0][0] == "proxy" and first[0][1] == "/app/con[0]/ses[0]"
    assert first[0] is first[1]           # cache par thread : un seul FindById
    assert engine.found == ["/app/con[0]/ses[0]"]


def test_sans_moteur_le_repli_defensif_rend_l_objet_d_origine(monkeypatch):
    lib = SapEccLibrary(screenshots_on_error=False)
    session = FakeSession()
    lib.session = session
    lib._acquire_scripting_engine = lambda: None
    assert _run_in_thread(lambda: lib.session) is session


def test_un_rebind_efface_les_proxies_du_thread_precedent():
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession("/app/con[0]/ses[0]")
    engine = FakeEngine()
    lib._acquire_scripting_engine = lambda: engine
    _run_in_thread(lambda: lib.session)
    lib.session = FakeSession("/app/con[0]/ses[1]")
    proxy = _run_in_thread(lambda: lib.session)
    assert proxy[1] == "/app/con[0]/ses[1]"


def test_le_mode_strict_refuse_le_thread_etranger(monkeypatch):
    monkeypatch.setenv("SAPFX_STRICT_COM_THREAD", "1")
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession()
    with pytest.raises(RuntimeError, match="SAPFX_STRICT_COM_THREAD"):
        _run_in_thread(lambda: lib.session)
