"""Sentinelle de dérive d'écrans : détecter qu'un écran a changé, SANS test.

Renverse le paradigme : au lieu d'écrire des tests qui savent ce qu'ils
vérifient, la sentinelle **mémorise ce que les écrans critiques étaient**
(perception structurée + empreinte visuelle) et signale, run après run, tout
ce qui a bougé : champ disparu, bouton déplacé, colonne renommée, rendu
altéré. Un système SAP après support pack : la sentinelle raconte la dérive
écran par écran avant qu'un seul test scripté n'échoue. Ce qu'elle remonte
devient l'entrée du sap-planner (couvrir la zone qui bouge) ou du sap-healer
(réparer le localisateur qui a dérivé).

Deux canaux par écran, complémentaires :

* **structurel** : la signature de perception (``Get Screen Signature``),
  diffée ligne à ligne par :mod:`sapfx_common.perception_diff` : dit *quoi* a
  changé (ids, types, textes) ;
* **visuel** : le hash perceptuel (:mod:`sapfx_common.visual_hash`) couvre
  ce que la perception structurée ne voit pas (GuiShell opaques, rendu), en
  distance de Hamming.

Même politique que le reste de la maison : la sentinelle **constate et
explique, ne devine jamais** : première visite = référence enregistrée
(WARNING), ensuite chaque écart est nommé. Module pur (aucun COM/IO), typé,
testé hors SAP ; l'E/S vit dans le keyword ``Check Screen Against Watch``.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Sequence

from .perception_diff import diff_perception
from .visual_hash import hamming_distance, tile_rect

# Marqueur « identiques » de diff_lines/diff_perception : la sentinelle s'y
# réfère plutôt que de re-comparer les textes (une seule source de vérité).
NO_CHANGE_MARKER = "(no change since the previous perception)"

# Seuil visuel par défaut : aligné sur Screen Should Match Baseline (5 bits
# sur 64 : tolère l'anticrénelage, signale un vrai changement local).
VISUAL_THRESHOLD = 5


@dataclass(frozen=True)
class WatchOutcome:
    """Le verdict de la sentinelle pour UN écran surveillé."""
    name: str
    status: str                      # baseline-created | unchanged | drifted
    structural_diff: Optional[str] = None   # blocs -/~/+ si dérive structurelle
    visual_distance: Optional[int] = None   # Hamming, None si pas d'empreinte
    visual_tiles: Optional[str] = None      # dérive localisée par tuile, si dispo

    @property
    def drifted(self) -> bool:
        return self.status == "drifted"


def compare_watch(name: str, baseline_signature: str, current_signature: str,
                  baseline_hash: Optional[str] = None,
                  current_hash: Optional[str] = None,
                  visual_threshold: int = VISUAL_THRESHOLD) -> WatchOutcome:
    """Compare l'écran courant à sa référence mémorisée.

    Dérive **structurelle** : le diff de perception n'est pas vide, rendu en
    diff *intelligent* (``pair_renames`` : les ids qui se ressemblent sont
    appariés en ``~ ancien -> nouveau`` par le scoring de healing, au lieu de
    deux lignes ``-``/``+`` brutes ; un sous-écran renuméroté se lit comme un
    renommage, pas comme quarante changements). Dérive **visuelle** : les deux
    empreintes existent et leur distance dépasse ``visual_threshold`` (une
    empreinte absente d'un côté n'est jamais une dérive : Pillow optionnel, la
    sentinelle reste utilisable sans). L'un OU l'autre suffit à déclarer
    ``drifted`` ; le canal tuiles s'ajoute ensuite via
    :func:`apply_tile_verdict`."""
    diff = diff_perception(baseline_signature, current_signature,
                           pair_renames=True)
    structural = diff if diff != NO_CHANGE_MARKER else None
    visual: Optional[int] = None
    if baseline_hash and current_hash:
        visual = hamming_distance(baseline_hash, current_hash)
    visually_drifted = visual is not None and visual > visual_threshold
    if structural or visually_drifted:
        return WatchOutcome(name=name, status="drifted",
                            structural_diff=structural, visual_distance=visual)
    return WatchOutcome(name=name, status="unchanged", visual_distance=visual)


def locate_tile_drift(distances: Sequence[int], tiles_x: int, tiles_y: int,
                      image_width: int, image_height: int,
                      threshold: int = VISUAL_THRESHOLD,
                      elements: Sequence[tuple[str, int, int, int, int]] = ()
                      ) -> str:
    """Rend lisible une dérive visuelle **par tuile** : pour chaque tuile dont
    la distance dépasse ``threshold``, sa position (ligne, colonne, 1-based),
    son rectangle en pixels, la distance, et, si la géométrie des éléments est
    fournie (``(id, left, top, width, height)`` relatifs à l'image), les
    éléments qui recouvrent la tuile, du plus petit (le plus spécifique) au
    plus grand. C'est la réponse à « la dérive visuelle est OÙ ? » : « dans la
    région de ``cntlGRID1`` », pas « quelque part sur l'écran ».
    Chaîne vide si aucune tuile ne dépasse le seuil."""
    lines: list[str] = []
    for index, distance in enumerate(distances):
        if distance <= threshold:
            continue
        left, top, width, height = tile_rect(index, image_width, image_height,
                                             tiles_x, tiles_y)
        row, col = divmod(index, tiles_x)
        line = ("tuile (%d,%d) [%d,%d %dx%d] : %d bits"
                % (row + 1, col + 1, left, top, width, height, distance))
        overlapping = sorted(
            ((ew * eh, eid) for eid, el, et, ew, eh in elements
             if ew > 0 and eh > 0
             and el < left + width and el + ew > left
             and et < top + height and et + eh > top),
        )
        if overlapping:
            line += " ; éléments : %s" % ", ".join(
                eid for _, eid in overlapping[:3])
        lines.append(line)
    return "\n".join(lines)


def apply_tile_verdict(outcome: WatchOutcome,
                       tile_report: Optional[str]) -> WatchOutcome:
    """Intègre le canal **tuiles** au verdict : un rapport non vide est une
    dérive visuelle *localisée* : elle fait foi même si le hash global est
    resté sous le seuil (c'est précisément le cas que les tuiles rattrapent :
    un changement local dilué dans l'écran entier). Sans rapport, le verdict
    est inchangé."""
    if not tile_report:
        return outcome
    return replace(outcome, status="drifted", visual_tiles=tile_report)


def render_watch_report(outcomes: Sequence[WatchOutcome]) -> str:
    """Rapport Markdown d'un passage de sentinelle : les dérives d'abord (avec
    leur diff), puis les références créées, puis l'inchangé en une ligne :
    prêt à coller dans une issue ou à archiver à côté du run."""
    drifted = [o for o in outcomes if o.status == "drifted"]
    created = [o for o in outcomes if o.status == "baseline-created"]
    unchanged = [o for o in outcomes if o.status == "unchanged"]
    lines = ["# Sentinelle d'écrans : %d surveillé(s), %d dérive(s)"
             % (len(outcomes), len(drifted)), ""]
    for outcome in drifted:
        lines.append("## DÉRIVE : %s" % outcome.name)
        if outcome.visual_distance is not None:
            lines.append("- distance visuelle : %d bits" % outcome.visual_distance)
        if outcome.visual_tiles:
            lines.append("- dérive visuelle localisée :")
            lines += ["  - %s" % tile for tile in outcome.visual_tiles.splitlines()]
        if outcome.structural_diff:
            lines += ["- changements structurels :", "", "```diff",
                      outcome.structural_diff, "```"]
        lines.append("")
    if created:
        lines.append("## Références créées (première visite)")
        lines += ["- %s" % o.name for o in created]
        lines.append("")
    if unchanged:
        lines.append("## Inchangés : %s" % ", ".join(o.name for o in unchanged))
        lines.append("")
    return "\n".join(lines)
