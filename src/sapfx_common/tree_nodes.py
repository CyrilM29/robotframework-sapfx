"""Arbres SAP GUI (``GuiShell`` de sous-type ``Tree``) : logique pure.

Un arbre de l'API Scripting expose ses nœuds par CLÉ opaque
(``GetAllNodeKeys``), et le texte d'un nœud par ``GetNodeTextByKey`` pour un
arbre simple (``GetTreeType() = 1``, le menu SAP Easy Access) ou par
``GetItemText(clé, colonne)`` pour un arbre à colonnes (type 2, l'IMG de
SPRO, dont ``GetNodeTextByKey`` rend une chaîne vide). Les clés sont
rendues TELLES QUELLES : celles d'un arbre à colonnes sont complétées à
gauche (``'01  1      1'``, relevé live sur SPRO et SICF), et une clé
« nettoyée » échoue par un ``com_error`` sans message.

Ce module porte la partie sans COM : le modèle d'un nœud, la recherche par
texte (contrat d'ambiguïté maison : TOUS les matches, l'appelant tranche),
la résolution d'un CHEMIN de textes (``Favorites > URL - ABAP Samples``) niveau
par niveau, et les messages d'échec listant les candidats. Typé, testé hors
SAP ; les E/S COM vivent dans ``SapEccLibrary.keywords._trees``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable, Optional, Sequence

PATH_SEPARATOR = ">"


@dataclass(frozen=True)
class TreeNode:
    """Un nœud d'arbre normalisé : ``key`` opaque (jamais nettoyée), ``text``
    (colonne principale pour un arbre à colonnes), ``level`` quand l'API le
    donne (0 = racine), ``folder`` (porte des enfants), ``columns`` = les
    autres colonnes d'un arbre de type 2."""
    key: str
    text: str = ""
    level: Optional[int] = None
    folder: bool = False
    children: Optional[int] = None
    columns: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _normalize(text: object) -> str:
    return " ".join(str(text if text is not None else "").split()).casefold()


def text_matches(actual: object, wanted: object, exact: bool = False) -> bool:
    """Comparaison de textes de nœud : blancs normalisés, casse ignorée ;
    ``exact=False`` accepte ``wanted`` comme préfixe."""
    a, w = _normalize(actual), _normalize(wanted)
    if not w:
        return False
    return a == w if exact else a.startswith(w)


def find_nodes_by_text(nodes: Iterable[TreeNode], text: str,
                       exact: bool = False) -> list[TreeNode]:
    """TOUS les nœuds dont le texte correspond, ordre de l'arbre conservé.
    L'ambiguïté est rendue, jamais tranchée."""
    return [node for node in nodes if text_matches(node.text, text, exact)]


def split_path(path: str, separator: str = PATH_SEPARATOR) -> list[str]:
    """``"Favorites > URL - ABAP Samples"`` -> ``["Favorites", "URL - ABAP Samples"]``
    (segments vides retirés, blancs de bordure retirés)."""
    return [part.strip() for part in str(path or "").split(separator)
            if part.strip()]


def format_candidates(nodes: Sequence[TreeNode], limit: int = 15) -> str:
    """Liste lisible ``clé -> texte`` pour un message d'échec actionnable."""
    lines = ["  - %r -> %s" % (node.key, node.text or "(sans texte)")
             for node in list(nodes)[:limit]]
    if len(nodes) > limit:
        lines.append("  ... (%d nœuds en tout)" % len(nodes))
    return "\n".join(lines)


def unique_match(nodes: Sequence[TreeNode], text: str, exact: bool,
                 context: str) -> TreeNode:
    """Le seul nœud correspondant, ou une ``ValueError`` actionnable : aucun
    match (les textes disponibles listés) ou plusieurs (les candidats listés,
    le remède ``exact=True`` nommé)."""
    matches = find_nodes_by_text(nodes, text, exact)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(
            "Aucun nœud %r %s. Nœuds disponibles :\n%s"
            % (text, context, format_candidates(list(nodes))))
    raise ValueError(
        "Nœud %r ambigu %s : %d correspondances (préciser le texte, ou "
        "exact=True) :\n%s" % (text, context, len(matches),
                               format_candidates(matches)))


def is_progid(text: object) -> bool:
    """Vrai si ``text`` est un ProgID COM (``SAP.TableTreeControl.1``,
    ``SAPGUI.GridViewCtrl.1``) : ce que le ``Text`` d'un shell rend en guise de
    valeur, et qui n'est JAMAIS une donnée d'écran."""
    value = str(text if text is not None else "").strip()
    if not value or " " in value:
        return False
    parts = value.split(".")
    return (len(parts) >= 3 and parts[0].upper() in ("SAP", "SAPGUI")
            and parts[-1].isdigit())
