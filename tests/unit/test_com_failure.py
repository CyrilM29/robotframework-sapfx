"""Tests hors SAP de la classification des pannes COM cross-thread
(``sapfx_common.com_safety``) : les deux formes relevées live sous rf-mcp le
2026-09-07 (``com_error`` RPC_E_WRONG_THREAD et ``AttributeError`` de proxy
« <unknown>.X ») doivent être reconnues, et rien d'autre."""
from pythoncom import com_error

from sapfx_common.com_safety import (
    RPC_E_WRONG_THREAD,
    describe_com_failure,
    is_wrong_thread_error,
)


def test_com_error_rpc_e_wrong_thread_est_reconnue_par_args_et_hresult():
    assert is_wrong_thread_error(com_error(RPC_E_WRONG_THREAD, "interface d'un autre thread", None, None))

    class WithHresult(Exception):
        hresult = RPC_E_WRONG_THREAD
    assert is_wrong_thread_error(WithHresult("x"))


def test_attributeerror_de_proxy_pywin32_est_reconnue_et_pas_une_vraie_absence():
    assert is_wrong_thread_error(AttributeError("<unknown>.GetObjectTree"))
    assert not is_wrong_thread_error(AttributeError("GetObjectTree absent"))
    assert not is_wrong_thread_error(com_error(-2147352567, "autre panne", None, None))
    assert not is_wrong_thread_error(ValueError("rien à voir"))


def test_describe_com_failure_nomme_le_remede_de_session_seulement_pour_le_cross_thread():
    text = describe_com_failure(AttributeError("<unknown>.Info"))
    assert "use_context=true" in text and "Attach To Open Session" in text
    assert "use_context" not in describe_com_failure(ValueError("boom"))
