"""Ce que l'appelant Robot attend d'un keyword : un échec avalé ou non.

Une bibliothèque ne voit pas, en principe, le contexte de son appelant. Or la
capture sur erreur en dépend : une SONDE (`Run Keyword And Return Status`),
un refus attendu (`Run Keyword And Expect Error`) ou un échec toléré
(`Run Keyword And Ignore Error`) échouent par construction, et chacun
laissait un PNG dans le dossier de sortie d'un run vert. Mesuré le
2026-10-08 sur le registre de capacités de la 754 : 21/21 et 9 captures,
toutes sous l'un de ces trois keywords de BuiltIn (backlog § 2.72).

La pile des étapes en cours de Robot (``EXECUTION_CONTEXTS.current.steps``,
Robot 7.4 et plus) porte le propriétaire et le nom de chaque keyword
englobant : il suffit d'y chercher un de ces trois enveloppeurs. Trois cas
gardent volontairement la capture : `Run Keyword And Warn On Failure` (l'échec
devient un avertissement du log, qu'une image aide à comprendre),
`Wait Until Keyword Succeeds` (le dernier essai remonte l'échec) et un bloc
``TRY`` (un ``EXCEPT`` qui ne correspond pas laisse l'échec remonter, et la
pile ne dit pas lequel s'appliquera).

La lecture est best-effort : une pile illisible rend ``None``, que
l'appelant traite comme « échec non attendu », c'est-à-dire le comportement
d'avant. Une capture de trop vaut mieux qu'une capture perdue sur un vrai
échec.
"""
import re
from typing import Iterable, Optional, Tuple

#: Les keywords de BuiltIn qui avalent l'échec de ce qu'ils exécutent, en
#: forme normalisée (minuscules, sans espaces ni soulignés).
SWALLOWING_KEYWORDS = frozenset({
    "runkeywordandexpecterror",
    "runkeywordandignoreerror",
    "runkeywordandreturnstatus",
})

Frame = Tuple[Optional[str], Optional[str]]


def _normalize(name: Optional[str]) -> str:
    return re.sub(r"[\s_]", "", str(name or "")).lower()


def swallowing_wrapper(frames: Iterable[Frame]) -> Optional[str]:
    """Le keyword de BuiltIn qui avale l'échec, le plus proche, ou ``None``.

    ``frames`` : les keywords englobants, ``(propriétaire, nom)``, du plus
    extérieur au plus intérieur. Un homonyme d'une autre bibliothèque ou
    d'une resource ne compte pas : seul BuiltIn a ce contrat."""
    for owner, name in reversed(list(frames)):
        if _normalize(owner) == "builtin" and _normalize(name) in SWALLOWING_KEYWORDS:
            return str(name)
    return None


def is_direct_call(frames: Optional[Iterable[Frame]], keyword_name: str) -> bool:
    """Vrai si le keyword le plus intérieur est ``keyword_name`` : l'utilisateur
    l'a appelé lui-même, ce n'est pas un keyword qui s'en sert en interne."""
    frames = list(frames or [])
    return bool(frames) and _normalize(frames[-1][1]) == _normalize(keyword_name)


def current_keyword_frames() -> Optional[list]:
    """Les keywords englobants de l'exécution Robot en cours, ``None`` hors
    exécution ou si la pile ne se lit pas."""
    try:
        from robot.running.context import EXECUTION_CONTEXTS
        context = EXECUTION_CONTEXTS.current
        if context is None:
            return None
        frames = []
        for _data, result, _implementation in context.steps:
            if getattr(result, "type", None) == "KEYWORD":
                frames.append((getattr(result, "owner", None), getattr(result, "name", None)))
        return frames
    except Exception:                       # noqa: BLE001 (best-effort, voir le module)
        return None


def failure_expected_by_caller() -> Optional[str]:
    """Le nom du keyword de BuiltIn qui attend ou avale l'échec en cours,
    ``None`` s'il n'y en a pas ou si la pile ne se lit pas."""
    frames = current_keyword_frames()
    if not frames:
        return None
    return swallowing_wrapper(frames)
