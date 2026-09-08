"""Tests hors SAP : `Wait Until Busy Done` ne maquille plus une exception de
sonde en « still busy » (relevé live sous rf-mcp le 2026-09-07 : un accès COM
cross-thread sortait en « SAP session was still busy after 30 seconds » sur un
écran au repos)."""
import pytest

from SapEccLibrary import SapEccLibrary


class ProbeFailsSession:
    def __init__(self, error):
        self._error = error

    @property
    def Busy(self):
        raise self._error

    @property
    def Id(self):
        return "/app/con[0]/ses[0]"


class BusySession:
    Busy = True
    Id = "/app/con[0]/ses[0]"


def _lib(session):
    lib = SapEccLibrary(screenshots_on_error=False, poll_interval="0.01s")
    lib.session = session
    return lib


def test_une_sonde_qui_leve_est_nommee_dans_le_message():
    with pytest.raises(AssertionError, match="could not be probed") as exc:
        _lib(ProbeFailsSession(AttributeError("<unknown>.Busy"))).wait_until_busy_done("0.05s")
    assert "use_context=true" in str(exc.value)
    assert "still busy" not in str(exc.value)


def test_un_serveur_vraiment_occupe_garde_le_message_historique():
    with pytest.raises(AssertionError, match="still busy after"):
        _lib(BusySession()).wait_until_busy_done("0.05s")
