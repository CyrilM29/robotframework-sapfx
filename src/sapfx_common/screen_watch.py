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
from typing import List, Optional, Sequence, Tuple

from .perception_diff import diff_perception
from .visual_baseline import describe_geometry_mismatch, format_geometry
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
    geometry_note: Optional[str] = None     # référence et capture pas à la même échelle

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


@dataclass(frozen=True)
class TilesReference:
    """Le contenu d'un fichier de référence ``*.tiles.txt`` : le découpage et le
    ``hash_size`` **de la référence** (rejouer avec une autre configuration ne
    doit jamais fabriquer une dérive), la géométrie de capture d'origine, et
    les empreintes tuile par tuile."""
    tiles_x: int
    tiles_y: int
    hash_size: int
    geometry: Tuple[int, int]
    hashes: List[str]


def format_dhash_reference(hash_hex: str,
                           geometry: Optional[Tuple[int, int]] = None) -> str:
    """Contenu d'un fichier ``*.dhash.txt`` : l'empreinte, et la **géométrie**
    de la capture qui l'a produite quand elle est connue. Sans elle, une
    référence ne peut pas dire si une dérive future n'est qu'un changement
    d'échelle : c'est le manque que ce second champ comble."""
    if geometry is None:
        return hash_hex
    return "%s %s" % (hash_hex, format_geometry(geometry))


def parse_dhash_reference(text: str) -> Tuple[Optional[str],
                                              Optional[Tuple[int, int]]]:
    """Lecture tolérante de ``*.dhash.txt`` : ``(empreinte, géométrie)``. Les
    références écrites avant l'ajout de la géométrie (empreinte seule) restent
    lisibles, géométrie ``None``, donc utilisables telles quelles."""
    parts = text.strip().split()
    if not parts:
        return None, None
    geometry = None
    if len(parts) > 1 and "x" in parts[1]:
        try:
            width, height = (int(v) for v in parts[1].split("x", 1))
            geometry = (width, height)
        except ValueError:
            geometry = None
    return parts[0], geometry


def format_tiles_reference(hashes: Sequence[str], tiles_x: int, tiles_y: int,
                           hash_size: int,
                           geometry: Tuple[int, int]) -> str:
    """Contenu d'un fichier ``*.tiles.txt`` : en-tête (découpage, hash_size,
    géométrie) puis les empreintes. Format historique conservé."""
    return "%d %d %d %d %d\n%s" % (tiles_x, tiles_y, hash_size,
                                   geometry[0], geometry[1], " ".join(hashes))


def parse_tiles_reference(text: str) -> Optional[TilesReference]:
    """Lecture de ``*.tiles.txt``, ``None`` si le fichier est illisible (une
    référence abîmée ne doit jamais devenir une dérive)."""
    try:
        header, hashes_line = text.splitlines()[:2]
        values = [int(v) for v in header.split()[:5]]
        tiles_x, tiles_y, hash_size, width, height = values
    except (ValueError, IndexError):
        return None
    return TilesReference(tiles_x=tiles_x, tiles_y=tiles_y,
                          hash_size=hash_size, geometry=(width, height),
                          hashes=hashes_line.split())


def annotate_geometry(outcome: WatchOutcome,
                      reference_geometry: Optional[Tuple[int, int]],
                      current_geometry: Optional[Tuple[int, int]],
                      per_resolution: bool = False) -> WatchOutcome:
    """Ajoute au verdict la note d'échelle quand la référence VISUELLE et la
    capture ne sont pas à la même géométrie : le canal structurel, lui, est
    insensible à la résolution, donc une dérive purement visuelle dans ce cas
    demande d'abord de regarder l'écran, pas le système testé."""
    note = describe_geometry_mismatch(reference_geometry, current_geometry,
                                      reference="référence")
    if not note:
        return outcome
    if not per_resolution:
        note += ("Pour donner à chaque poste sa propre référence visuelle : "
                 "per_resolution=True (canal structurel toujours partagé).\n")
    return replace(outcome, geometry_note=note.rstrip("\n"))


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
        if outcome.geometry_note:
            lines += ["- %s" % part
                      for part in outcome.geometry_note.splitlines() if part]
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
