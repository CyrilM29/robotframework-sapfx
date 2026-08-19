"""Rapport de dérive des localisateurs depuis la télémétrie de healing.

Le maillon qui transforme le healing en **maintenance préventive** : la
télémétrie (``SAPFX_HEALING_LOG``, JSONL cumulatif, voir
``sapfx_common.healing_telemetry``) enregistre chaque réparation au fil des
runs ; ce script la relit, agrège par localisateur d'origine, et sépare :

* les **dérives stables** : le même localisateur réparé N fois (``--min-count``)
  vers LA même cible : le vrai id a changé, la correction dans ``resources/``
  est sans ambiguïté. Le script la localise dans les fichiers ``.resource`` et
  propose le remplacement (``--apply`` l'exécute) ;
* les **dérives instables** : réparé vers des cibles différentes selon les
  runs : à examiner par un humain (ou l'agent sap-healer), jamais auto-patché.

Règle maison respectée : on ne patche QUE la couche ``resources/``, jamais
les tests, jamais silencieusement (le rapport liste tout, ``--apply`` est
opt-in et re-liste ce qu'il a fait).

Codes retour : 0 = aucune dérive récurrente (ou toutes appliquées via
``--apply``) ; 1 = dérives détectées à traiter, utilisable tel quel dans un
job planifié pour alerter.

Usage::

    python scripts/healing_drift_report.py --log healing.jsonl
    python scripts/healing_drift_report.py --log healing.jsonl --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_MIN_COUNT = 2


@dataclass
class Drift:
    """Agrégat d'un localisateur d'origine sur l'ensemble du journal."""
    channel: str
    original: str
    targets: Counter = field(default_factory=Counter)
    count: int = 0
    first_seen: str = ""
    last_seen: str = ""

    @property
    def stable(self) -> bool:
        return len(self.targets) == 1

    @property
    def healed(self) -> Optional[str]:
        return next(iter(self.targets)) if self.stable else None


@dataclass
class Patch:
    """Un remplacement proposé dans un fichier .resource.

    ``original`` porte le localisateur qui a motivé le patch : la dérive dont
    il vient est ainsi connue sans la redéduire du texte de la ligne, ce que
    faisait le rapport (par sous-chaîne) au risque d'attribuer un patch à la
    mauvaise dérive quand deux ids se contiennent.
    """
    path: Path
    line_no: int
    before: str
    after: str
    original: str = ""


def load_events(log_path: Path) -> list[dict]:
    """Lit le JSONL en best-effort (les lignes illisibles sont ignorées, c'est
    le même contrat tolérant que l'écriture de la télémétrie). ``utf-8-sig`` :
    un journal retouché/concaténé sous Windows arrive volontiers avec un BOM
    (constaté au premier essai CLI, Out-File PowerShell)."""
    events = []
    for line in log_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("original") and event.get("healed"):
            events.append(event)
    return events


def aggregate(events: Iterable[dict], min_count: int = DEFAULT_MIN_COUNT,
              since: str = "") -> list[Drift]:
    """Agrège par (canal, localisateur d'origine) ; ne retient que les dérives
    vues au moins ``min_count`` fois (``since`` : ISO, ignore le plus ancien)."""
    drifts: dict[tuple[str, str], Drift] = {}
    for event in events:
        timestamp = str(event.get("timestamp", ""))
        if since and timestamp and timestamp < since:
            continue
        key = (str(event.get("channel", "?")), str(event["original"]))
        drift = drifts.setdefault(key, Drift(channel=key[0], original=key[1]))
        drift.targets[str(event["healed"])] += 1
        drift.count += 1
        drift.first_seen = min(filter(None, (drift.first_seen, timestamp)),
                               default=timestamp)
        drift.last_seen = max(drift.last_seen, timestamp)
    recurring = [d for d in drifts.values() if d.count >= min_count]
    recurring.sort(key=lambda d: (-d.count, d.original))
    return recurring


def find_in_resources(resources_dir: Path, locator: str) -> list[tuple[Path, int, str]]:
    """Occurrences (fichier, ligne 1-based, contenu) du localisateur dans les
    ``.resource`` : recherche de sous-chaîne exacte, les ids SAP ne se
    prêtent pas aux faux positifs."""
    hits = []
    for path in sorted(resources_dir.glob("*.resource")):
        for line_no, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1):
            if locator in line:
                hits.append((path, line_no, line))
    return hits


def propose_patches(drifts: Iterable[Drift], resources_dir: Path) -> list[Patch]:
    """Patches pour les dérives **stables** dont l'origine vit dans
    ``resources/`` (les instables et les localisateurs inline restent au
    rapport, à traiter par un humain ou sap-healer). TOUTES les occurrences
    du localisateur sur la ligne sont remplacées, y compris un écho en
    commentaire de fin de ligne : une ligne de resource ne porte qu'un
    localisateur et ses échos, les laisser diverger serait pire."""
    patches = []
    for drift in drifts:
        if not drift.stable:
            continue
        healed = drift.healed or ""
        for path, line_no, line in find_in_resources(resources_dir, drift.original):
            patches.append(Patch(path=path, line_no=line_no, before=line,
                                 after=line.replace(drift.original, healed),
                                 original=drift.original))
    return patches


def apply_patches(patches: Iterable[Patch]) -> int:
    """Applique les remplacements (fichier par fichier) ; retourne le nombre
    de lignes modifiées."""
    by_file: dict[Path, list[Patch]] = {}
    for patch in patches:
        by_file.setdefault(patch.path, []).append(patch)
    changed = 0
    for path, file_patches in by_file.items():
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        for patch in file_patches:
            index = patch.line_no - 1
            if index < len(lines) and patch.before in lines[index]:
                lines[index] = lines[index].replace(patch.before, patch.after)
                changed += 1
        path.write_text("".join(lines), encoding="utf-8")
    return changed


def render_markdown(drifts: list[Drift], patches: list[Patch]) -> str:
    """Rapport lisible : dérives stables (avec patch localisé ou non), puis
    instables (cibles multiples), prêt à coller dans une issue/PR."""
    if not drifts:
        return "Aucune dérive récurrente dans la télémétrie de healing.\n"
    lines = ["# Dérives de localisateurs (télémétrie de healing)", ""]
    stable = [d for d in drifts if d.stable]
    unstable = [d for d in drifts if not d.stable]
    if stable:
        lines += ["## Stables : correction sans ambiguïté", ""]
        for drift in stable:
            lines.append("- `%s` (%s) réparé %d fois vers `%s` "
                         "(vu %s → %s)" % (drift.original, drift.channel,
                                           drift.count, drift.healed,
                                           drift.first_seen or "?",
                                           drift.last_seen or "?"))
        lines.append("")
    if patches:
        lines += ["### Patches proposés dans resources/", ""]
        for patch in patches:
            lines += ["- %s:%d" % (patch.path, patch.line_no),
                      "  - avant : `%s`" % patch.before.strip(),
                      "  - après : `%s`" % patch.after.strip()]
        lines.append("")
    patched_originals = {p.original for p in patches}
    orphans = [d for d in stable if d.original not in patched_originals]
    if orphans:
        lines += ["### Stables mais hors resources/ (localisateur inline ?)", ""]
        lines += ["- `%s`" % d.original for d in orphans]
        lines.append("")
    if unstable:
        lines += ["## Instables : cibles multiples, examen humain requis", ""]
        for drift in unstable:
            targets = ", ".join("`%s` (%d×)" % (t, n)
                                for t, n in drift.targets.most_common())
            lines.append("- `%s` (%s, %d réparations) → %s"
                         % (drift.original, drift.channel, drift.count, targets))
        lines.append("")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    # Console Windows en cp1252 : le rapport contient des caractères hors
    # page de code (flèches) : on force UTF-8 en best-effort plutôt que de
    # planter à l'affichage (constaté au premier essai CLI). Ces quatre lignes
    # sont la copie assumée de ``scripts/_common.py`` : ce script est EMBARQUÉ
    # dans le pack Windows et doit y tourner seul, sans voisin.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log", default=os.environ.get("SAPFX_HEALING_LOG", ""),
                        help="journal JSONL (défaut : $SAPFX_HEALING_LOG)")
    parser.add_argument("--min-count", type=int, default=DEFAULT_MIN_COUNT,
                        help="réparations minimales pour être une dérive (défaut 2)")
    parser.add_argument("--since", default="",
                        help="ignorer les événements antérieurs (ISO 8601)")
    parser.add_argument("--resources-dir", default="resources",
                        help="répertoire des .resource à patcher (défaut resources/)")
    parser.add_argument("--apply", action="store_true",
                        help="applique les patches des dérives STABLES")
    args = parser.parse_args(argv)
    if not args.log:
        parser.error("--log requis (ou SAPFX_HEALING_LOG dans l'environnement)")
    log_path = Path(args.log)
    if not log_path.exists():
        print("Journal absent (%s) : aucune télémétrie encore émise." % log_path)
        return 0
    drifts = aggregate(load_events(log_path), args.min_count, args.since)
    resources_dir = Path(args.resources_dir)
    patches = propose_patches(drifts, resources_dir) if resources_dir.is_dir() else []
    print(render_markdown(drifts, patches))
    if args.apply and patches:
        changed = apply_patches(patches)
        print("%d ligne(s) de resources/ mises à jour : relancer la suite "
              "pour valider, puis committer." % changed)
        return 0
    return 1 if drifts else 0


if __name__ == "__main__":
    sys.exit(main())
