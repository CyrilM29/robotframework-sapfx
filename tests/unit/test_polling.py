"""Tests unitaires de ``sapfx_common.polling``, les primitives de synchronisation
partagées par les deux canaux (convention #5 du CLAUDE.md)."""
import time

import pytest

from sapfx_common.polling import poll_until, retry_call, retry_until


# --- poll_until ---------------------------------------------------------------

def test_poll_until_returns_truthy_result_immediately():
    assert poll_until(lambda: "value", timeout_secs=1) == "value"


def test_poll_until_probes_at_least_once_even_with_zero_timeout():
    calls = {"n": 0}

    def check():
        calls["n"] += 1
        return False

    assert poll_until(check, timeout_secs=0) is False
    assert calls["n"] == 1


def test_poll_until_keeps_probing_until_truthy():
    state = {"n": 0}

    def check():
        state["n"] += 1
        return state["n"] >= 3          # truthy au 3e sondage

    assert poll_until(check, timeout_secs=2, step=0.01) is True
    assert state["n"] == 3


def test_poll_until_returns_last_falsy_value_on_timeout():
    assert poll_until(lambda: [], timeout_secs=0.05, step=0.01) == []


def test_poll_until_expire_meme_si_l_horloge_murale_est_figee(monkeypatch):
    """L'échéance se mesure sur ``time.monotonic()``, jamais sur l'horloge
    murale : une resynchronisation NTP (ici : horloge figée, le cas extrême)
    ne doit ni allonger ni raccourcir le budget réel de l'attente. C'est la
    primitive de TOUTES les attentes des deux canaux."""
    monkeypatch.setattr(time, "time", lambda: 0.0)
    calls = {"n": 0}

    def check():
        calls["n"] += 1
        if calls["n"] > 500:   # borne de sûreté : sans elle, une régression
            raise AssertionError(   # vers time.time() ferait boucler sans fin
                "poll_until n'a pas expiré avec l'horloge murale figée : "
                "l'échéance est-elle repassée sur time.time() ?")
        return None

    assert poll_until(check, timeout_secs=0.02, step=0.001) is None
    assert calls["n"] >= 2


# --- retry_call ---------------------------------------------------------------

def test_retry_call_returns_first_success():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient")
        return "ok"

    assert retry_call(flaky, attempts=3, interval=0.01) == "ok"
    assert calls["n"] == 2


def test_retry_call_raises_last_error_after_attempts():
    def always_fail():
        raise RuntimeError("still broken")

    with pytest.raises(RuntimeError, match="still broken"):
        retry_call(always_fail, attempts=2, interval=0.01)


def test_retry_call_reports_each_failure_to_on_error():
    seen = []

    def always_fail():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        retry_call(always_fail, attempts=3, interval=0.01,
                   on_error=lambda attempt, err: seen.append((attempt, str(err))))
    assert [a for a, _ in seen] == [1, 2, 3]


def test_retry_call_stops_early_when_deadline_passed():
    calls = {"n": 0}

    def always_fail():
        calls["n"] += 1
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        retry_call(always_fail, attempts=100, interval=0.01,
                   deadline=time.monotonic() - 1)   # échéance déjà passée
    assert calls["n"] == 1


# --- retry_until --------------------------------------------------------------

def test_retry_until_returns_result_on_success():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise Warning("not ready")
        return "engine"

    assert retry_until(flaky, timeout_secs=2, step=0.01) == "engine"
    assert calls["n"] == 3


def test_retry_until_raises_last_error_on_timeout():
    with pytest.raises(Warning, match="never ready"):
        retry_until(lambda: (_ for _ in ()).throw(Warning("never ready")),
                    timeout_secs=0.05, step=0.01)
