"""Garde d'écriture du canal écran, consultée avant le geste d'enregistrement.

`Click Element` et `Send Vkey` appellent `check_save_gesture` : avec la
politique par défaut (``full``) le geste passe et il est journalisé ; une
politique imposée par l'environnement (``SAPFX_SESSION_POLICY``) peut le
refuser AVANT que rien ne parte vers SAP. Logique pure dans
``sapfx_common.session_policy``, garde et trace dans ``sapfx_common.policy_gate``.
"""
from sapfx_common.policy_gate import gate_for
from sapfx_common.session_policy import is_save_gesture

LIBRARY = "SapEccLibrary"
APPROVE_KEYWORD = "Approve Next Write"


def _screen_transaction(library) -> str:
    """La transaction de l'écran, lue sans geste (``session.Info``), vide si
    illisible : elle nomme la cible d'un enregistrement, jamais au prix de
    l'erreur du geste lui-même."""
    try:
        return str(library.session.Info.Transaction or "").strip()
    except Exception:                       # noqa: BLE001 (best-effort)
        return ""


def check_save_gesture(library, vkey=None, element_id=None) -> None:
    """Interroge la politique avant un geste d'enregistrement de l'écran
    (``Click Element``, ``Send Vkey``) ; rien n'est lu pour un autre geste."""
    if is_save_gesture(vkey=vkey, element_id=element_id):
        gate_for(library, LIBRARY, APPROVE_KEYWORD).check_save_gesture(
            vkey=vkey, element_id=element_id, transaction=_screen_transaction(library))
