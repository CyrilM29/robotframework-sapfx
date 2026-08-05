"""Primitives d'auto-réparation de localisateurs, partagées ECC <-> Fiori.

Le pattern (état de l'art Healenium / Katalon / UiPath) : quand un localisateur
ne résout plus, on **score** les candidats présents à l'écran contre ce qu'on
sait de la cible, et on ne « répare » qu'au-dessus d'un seuil, jamais en
silence (l'appelant journalise la réparation et le score).

Un id SAP GUI (``wnd[0]/usr/subSUB0:SAPLMEGUI:0013/.../ctxtMEPO_TOPLINE-BSART``)
est structurellement un XPath absolu : il casse par renumérotation de
sous-écrans (customizing, variantes de dynpro, release SAP) alors que son
**segment terminal** (type + nom du champ dynpro, très stables) identifie
toujours la cible. Le scoring pondère donc lourdement le segment terminal, puis
la ressemblance de chemin (LCS sur les segments), à la Healenium.

Module pur (aucune dépendance COM/navigateur), typé, testé hors SAP.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Iterable, NamedTuple, Optional, Sequence

# Poids du score composite d'un id SAP GUI. Le segment terminal (ctxtVBAK-VBELN)
# est l'invariant le plus fort ; le chemin absorbe les renumérotations.
_WEIGHT_TERMINAL = 0.5
_WEIGHT_PATH = 0.35
_WEIGHT_TYPE = 0.15

# Préfixes de type des ids SAP GUI (txtNAME, ctxtNAME, btnNAME...) : séparer le
# préfixe du nom permet de comparer « même champ, autre type de contrôle ».
_ID_TYPE_PREFIXES = ("ctxt", "txt", "pwd", "btn", "chk", "rad", "cmb", "lbl",
                     "tbl", "cntl", "sub", "ssub", "tabs", "tabp", "shellcont",
                     "shell", "usr", "wnd", "sbar", "tbar", "mbar", "okcd")


class ScoredCandidate(NamedTuple):
    """Un candidat de réparation : id (ou libellé) et score dans [0, 1]."""
    candidate: str
    score: float


def split_segments(element_id: str) -> list[str]:
    """Segments d'un id SAP GUI (séparateur ``/``), vides retirés."""
    return [seg for seg in (element_id or "").split("/") if seg]


def _terminal_name(segment: str) -> str:
    """Nom « métier » du segment terminal, préfixe de type retiré
    (``ctxtMEPO_TOPLINE-BSART`` -> ``MEPO_TOPLINE-BSART``)."""
    for prefix in _ID_TYPE_PREFIXES:
        if segment.startswith(prefix) and len(segment) > len(prefix):
            return segment[len(prefix):]
    return segment


def _ratio(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _sequence_ratio(a: Sequence[str], b: Sequence[str]) -> float:
    """Similarité entre deux chemins (séquences de segments), comparés au niveau
    CARACTÈRE sur leur forme jointe : un segment renuméroté
    (``subSUB0:SAPLMEGUI:0013`` -> ``:0015``) reste presque identique et doit
    garder son crédit : le traiter en atome (match/mismatch binaire) écraserait
    le score des dérives les plus courantes."""
    if not a and not b:
        return 1.0
    return _ratio("/".join(a), "/".join(b))


def gui_id_similarity(target_id: str, candidate_id: str,
                      target_type: Optional[str] = None,
                      candidate_type: Optional[str] = None) -> float:
    """Score composite [0, 1] entre l'id SAP GUI attendu et un id présent à
    l'écran : segment terminal (poids 0.5), chemin (0.35), type (0.15).

    Le type n'est pris en compte que si les DEUX sont fournis ; sinon son poids
    est redistribué proportionnellement (score comparable avec ou sans types).
    """
    target_segments = split_segments(target_id)
    candidate_segments = split_segments(candidate_id)
    if not target_segments or not candidate_segments:
        return 0.0
    terminal = _ratio(_terminal_name(target_segments[-1]),
                      _terminal_name(candidate_segments[-1]))
    path = _sequence_ratio(target_segments[:-1], candidate_segments[:-1])
    if target_type and candidate_type:
        type_score = 1.0 if target_type == candidate_type else 0.0
        return (_WEIGHT_TERMINAL * terminal + _WEIGHT_PATH * path
                + _WEIGHT_TYPE * type_score)
    scale = _WEIGHT_TERMINAL + _WEIGHT_PATH
    return (_WEIGHT_TERMINAL * terminal + _WEIGHT_PATH * path) / scale


def closest_gui_ids(target_id: str,
                    candidates: Iterable[tuple[str, str]],
                    limit: int = 5,
                    target_type: Optional[str] = None) -> list[ScoredCandidate]:
    """Les ``limit`` ids les plus proches de ``target_id`` parmi ``candidates``
    (paires ``(id, type)``), triés par score décroissant puis id (déterminisme).

    C'est la brique des messages d'erreur auto-corrigibles (pattern UiPath
    « closest matches » / MCP SEP-1303) ET de la réparation au runtime : mêmes
    candidats, seule la décision diffère (afficher vs adopter au-dessus d'un
    seuil)."""
    scored = [ScoredCandidate(cid, gui_id_similarity(target_id, cid, target_type, ctype))
              for cid, ctype in candidates]
    scored.sort(key=lambda sc: (-sc.score, sc.candidate))
    return scored[:max(0, int(limit))]


def format_suggestions(scored: Sequence[ScoredCandidate],
                       minimum: float = 0.05) -> str:
    """Rend une liste scorée en bloc lisible pour un message d'erreur (une ligne
    par candidat, score en %). Les scores sous ``minimum`` sont omis (bruit)."""
    lines = ["  - %s  (similarité %d%%)" % (sc.candidate, round(sc.score * 100))
             for sc in scored if sc.score >= minimum]
    return "\n".join(lines)
