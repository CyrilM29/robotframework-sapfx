"""Diff structuré entre deux perceptions d'écran (ECC ou Fiori).

La littérature agents/LLM (observation masking, diff-based history) et la
pratique (rf-mcp compacte déjà les perceptions byte-identiques) convergent :
après une action, ce qui intéresse l'agent est « **ce qui a changé** », pas la
re-description complète d'un écran déjà vu. Ce module rend un diff ligne à
ligne compact : lignes retirées (``- ``), ajoutées (``+ ``), et un simple
compteur pour l'inchangé — de l'ordre de 10× moins de tokens qu'une perception
complète sur un écran qui n'a bougé qu'à la marge.

``pair_renames=True`` ajoute le **diff intelligent** : dans chaque bloc
modifié, les lignes disparues/apparues dont les ids se ressemblent (scoring de
:mod:`sapfx_common.healing` — le même qui répare les localisateurs) sont
appariées en une seule ligne ``~ ancien -> nouveau`` au lieu d'une paire
``-``/``+`` brute. Un sous-écran renuméroté (``SAPLMEGUI:0013`` → ``:0015``)
passe de « 40 lignes ont bougé » à « N renommages, 2 vrais changements ».

Module pur (difflib), typé, partagé par ``Get Screen Signature`` (ECC) et
``Get Ui5 Page Tree`` (Fiori).
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Optional

from .healing import gui_id_similarity

# Frontière entre deux balises XML collées : point d'insertion de sauts de
# ligne pour rendre un arbre sérialisé diffable ligne à ligne.
_XML_BOUNDARY = re.compile(r">\s*<")

# Score minimal (gui_id_similarity, [0, 1]) pour apparier deux lignes en
# renommage : en dessous, disparu + apparu restent deux événements distincts.
# 0.6 = le terminal doit rester reconnaissable (le seuil qu'adopte aussi le
# healing pour proposer une réparation).
RENAME_THRESHOLD = 0.6


def split_xml_lines(xml_text: str) -> list[str]:
    """Éclate un XML sérialisé en une balise par ligne (diffable), sans altérer
    le contenu (les frontières ``><`` deviennent ``>\\n<``)."""
    return _XML_BOUNDARY.sub(">\n<", (xml_text or "").strip()).splitlines()


def _parse_perception_line(line: str) -> Optional[tuple[str, str, str]]:
    """Décompose une ligne de signature ECC (``[* ]<id>\\t<Type>\\t<texte>``) en
    ``(id, type, texte)`` — ``None`` si la ligne n'a pas ce format (entête,
    balise XML Fiori…), auquel cas elle ne participe pas à l'appariement."""
    body = line[2:] if line[:2] in ("* ", "  ") else line
    parts = body.split("\t")
    if len(parts) < 2 or not parts[0].strip():
        return None
    return parts[0].strip(), parts[1].strip(), parts[2] if len(parts) > 2 else ""


def _pair_block(removed: list[str], added: list[str]) -> list[str]:
    """Apparie les lignes d'un bloc modifié par similarité d'ids (glouton, le
    meilleur score d'abord, chaque ligne utilisée au plus une fois). Émet les
    paires en ``~``, le reste en ``-``/``+`` dans l'ordre du document."""
    parsed_removed = [_parse_perception_line(line) for line in removed]
    parsed_added = [_parse_perception_line(line) for line in added]
    scored: list[tuple[float, int, int]] = []
    for i, old in enumerate(parsed_removed):
        if old is None:
            continue
        for j, new in enumerate(parsed_added):
            if new is None:
                continue
            score = gui_id_similarity(old[0], new[0],
                                      old[1] or None, new[1] or None)
            if score >= RENAME_THRESHOLD:
                scored.append((score, i, j))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    paired: dict[int, tuple[int, float]] = {}
    used_added: set[int] = set()
    for score, i, j in scored:
        if i in paired or j in used_added:
            continue
        paired[i] = (j, score)
        used_added.add(j)
    out: list[str] = []
    for i, line in enumerate(removed):
        if i not in paired:
            out.append("- %s" % line)
            continue
        j, score = paired[i]
        old = parsed_removed[i]
        new = parsed_added[j]
        assert old is not None and new is not None
        if old[0] == new[0]:
            # même id, contenu modifié : un changement de VALEUR, pas d'identité
            out.append("~ %s\t%s\ttexte : %r -> %r"
                       % (old[0], new[1], old[2].strip(), new[2].strip()))
        else:
            out.append("~ %s -> %s\t%s\t(similarité %d%%)"
                       % (old[0], new[0], new[1], round(score * 100)))
    for j, line in enumerate(added):
        if j not in used_added:
            out.append("+ %s" % line)
    return out


def diff_lines(previous: list[str], current: list[str],
               pair_renames: bool = False) -> str:
    """Diff ligne à ligne compact entre deux perceptions.

    Formats de sortie :
    - ``(no change since the previous perception)`` si identiques ;
    - sinon, blocs ``- ligne`` (disparue) / ``+ ligne`` (apparue) dans l'ordre du
      document, les passages communs résumés en ``= N unchanged line(s)`` ;
    - avec ``pair_renames=True``, les paires disparue/apparue d'un même bloc
      dont les ids se ressemblent deviennent ``~ ancien -> nouveau  (similarité
      N%)`` (ou ``~ id … texte : 'a' -> 'b'`` quand seule la valeur a changé).
    """
    if previous == current:
        return "(no change since the previous perception)"
    out: list[str] = []
    matcher = SequenceMatcher(None, previous, current, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            out.append("= %d unchanged line(s)" % (i2 - i1))
        elif pair_renames:
            out.extend(_pair_block(previous[i1:i2], current[j1:j2]))
        else:
            out.extend("- %s" % line for line in previous[i1:i2])
            out.extend("+ %s" % line for line in current[j1:j2])
    return "\n".join(out)


def diff_perception(previous: str | None, current: str, xml: bool = False,
                    pair_renames: bool = False) -> str:
    """Diff entre la perception précédente (ou ``None`` au premier appel) et la
    courante. Au premier appel, retourne la perception complète (rien à differ).
    ``xml=True`` éclate d'abord les deux côtés en une balise par ligne.
    ``pair_renames=True`` active l'appariement des renommages (voir
    :func:`diff_lines`) — pensé pour les signatures ECC à 3 colonnes."""
    if previous is None:
        return current
    if xml:
        return diff_lines(split_xml_lines(previous), split_xml_lines(current),
                          pair_renames=pair_renames)
    return diff_lines(previous.splitlines(), current.splitlines(),
                      pair_renames=pair_renames)
