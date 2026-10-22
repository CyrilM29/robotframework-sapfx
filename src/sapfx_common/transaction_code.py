"""Le code de transaction SAP : le type d'argument et la règle qui dit quelle
transaction une valeur désigne (backlog 2.83, lot 1, 2026-10-20).

Un argument de keyword est un texte ; rien ne dit qu'il nomme une transaction.
``TransactionCode`` le dit à Robot (qui convertit), à Libdoc (qui publie le
type et la liste des keywords qui l'emploient), aux agents MCP et aux outils de
couverture (une matrice de traçabilité). Comme les autres types
métier d'arguments (``VirtualKey``, ``FlpIntent``...), il rend la valeur
INCHANGÉE (le corps du keyword la normalise comme avant) et ne refuse que ce
qui ne pouvait pas marcher : un code vide.

Ce que la valeur DÉSIGNE n'est pas la valeur brute : ``/nSE16`` démarre SE16,
``/nex`` ne démarre rien. ``transaction_touched`` porte cette règle, une seule
fois, pour la garde de la politique de session, le journal des touches et les
outils qui lisent Libdoc.

Typed.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

__all__ = ["SYSTEM_OK_CODES", "TransactionCode", "TransactionCodeInput", "bare_transaction",
           "require_transaction_code", "transaction_touched"]

#: OK-codes qui pilotent la session sans démarrer de transaction : nouvelle
#: session, nouvelle fenêtre, fin de session, retour à l'écran de départ.
SYSTEM_OK_CODES = frozenset({"/N", "/NEX", "/NEND", "/I", "/O"})

_NAMESPACED = re.compile(r"^/[A-Z0-9_]+/[A-Z0-9_]")
_UNRESOLVED = ("${", "@{", "&{", "%{")


def bare_transaction(okcode: str) -> str:
    """Le code de transaction d'un OK-code (``/nSE16`` -> ``SE16``), un
    OK-code système rendu tel quel en majuscules (``/NEX``). Un tcode de
    namespace garde son ``/`` (``/IWFND/MAINT_SERVICE``)."""
    code = str(okcode or "").strip().upper()
    if code in SYSTEM_OK_CODES:
        return code
    if re.match(r"^/[NO]/", code):            # /n/IWFND/MAINT_SERVICE
        return code[2:]
    if re.match(r"^/[A-Z0-9_]+/", code):      # /IWFND/MAINT_SERVICE, /NAMESPACE/X
        return code
    if re.match(r"^/[NO]", code):             # /nSE16
        return code[2:]
    return code


def transaction_touched(value: object) -> Optional[str]:
    """La transaction qu'un code ou un OK-code démarre, en majuscules, ou
    ``None`` quand il n'en démarre aucune : un OK-code système (``/nex``,
    ``/n``, ``/o``), une commande de session (``/h``, ``/bend``), une valeur
    vide ou encore une variable Robot non résolue (``${TCODE}``), que
    l'appelant doit rapporter « inconnue » et jamais ignorer.

    ``/*SE16`` (démarrer en sautant l'écran initial) désigne SE16 ; un code de
    namespace garde son ``/`` initial."""
    text = str(value or "").strip()
    if not text or any(marker in text for marker in _UNRESOLVED):
        return None
    code = bare_transaction(text)
    if code.startswith("/*"):
        code = code[2:]
    if not code or code in SYSTEM_OK_CODES:
        return None
    if code.startswith("/") and not _NAMESPACED.match(code):
        return None
    return code


def require_transaction_code(value: object) -> str:
    text = str(value)
    if not text.strip():
        raise ValueError(
            "Code de transaction vide : donner un code (SE16) ou un OK-code "
            "(/nSE16, /nex).")
    return text


class TransactionCode(str):
    """Code d'une transaction SAP, ou OK-code qui la démarre : ``SE16``,
    ``/nSE16`` (depuis n'importe quel écran), ``/n/IWFND/MAINT_SERVICE``
    (transaction de namespace : son ``/`` initial fait partie du code). Les
    OK-codes système (``/nex``, ``/nend``, ``/n``, ``/o``, ``/i``) sont admis
    mais ne désignent aucune transaction. Un code vide est refusé avant tout
    geste. La transaction touchée par une valeur est celle que rend
    ``sapfx_common.transaction_code.transaction_touched``.
    """

    # Convertisseur sans docstring : Libdoc publierait la sienne à la place du
    # contrat de la classe. Il rend une chaîne ORDINAIRE, celle reçue.
    @classmethod
    def from_value(cls, value: str | int) -> str:
        return require_transaction_code(value)


#: L'annotation des keywords : le type à l'exécution (Robot convertit, Libdoc
#: publie), une chaîne pour mypy (les appels Python directs).
if TYPE_CHECKING:
    TransactionCodeInput = str
else:
    TransactionCodeInput = TransactionCode
