"""Les FAITS d'un run, lus après coup dans son ``output.xml`` et à côté
(backlog § 2.8, 2026-10-08) : la matière que ``release_verdict`` juge.

Avant ce module, rien ne reliait un run à un livrable : ``output.xml`` n'était
jamais lu. Les faits sont ceux qu'un taux de réussite tait :

- les tests exécutés, échoués, sautés, et les sauts SANS raison ;
- les tests VERTS qui ont pourtant écrit une capture (un échec rattrapé
  quelque part, voir `Get Error Screenshots`) ;
- les avertissements et les erreurs d'exécution (section ``errors`` de
  ``output.xml`` : une bibliothèque qui ne s'importe pas y est, pas dans un
  test) ;
- les localisateurs RÉPARÉS pendant la fenêtre du run (journal
  ``SAPFX_HEALING_LOG``, horodaté en UTC ; les heures d'``output.xml`` sont
  locales, d'où la conversion) ;
- la traçabilité vers les plans : chaque suite exécutée porte-t-elle un
  marqueur ``Spec:`` et ce plan a-t-il bougé depuis (empreinte différente, ou
  marqué ``PÉRIMÉE``) ? La règle du marqueur est celle de
  ``scripts/check_spec_sync.py``, reprise ici parce que la bibliothèque livrée
  ne peut pas dépendre d'un script privé ; un test unitaire tient les deux
  égales.

Ce qui ne se lit pas est dit ``None`` (jamais zéro) : un journal de healing
absent ne prouve pas qu'aucun localisateur n'a dérivé.

Typed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

MARKER = re.compile(
    r"Spec:\s*(?P<spec>specs/[^\s]+\.md)\s*"
    r"\(sha256:(?P<digest>[0-9a-f]{12})(?:,\s*(?P<date>\d{4}-\d{2}-\d{2}))?\)")
STALE = re.compile(r"^>\s*\*\*Statut\s*:\s*PÉRIMÉE", re.MULTILINE)


def spec_digest(spec_path: Path) -> str:
    """Empreinte (12 hex) d'un plan, fins de ligne normalisées."""
    text = spec_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _utc(moment: Optional[datetime]) -> Optional[datetime]:
    """Une heure d'``output.xml`` (locale, sans fuseau) en UTC."""
    if moment is None:
        return None
    return moment.astimezone(timezone.utc)


def _iso(moment: Optional[datetime]) -> Optional[str]:
    return moment.isoformat(timespec="seconds") if moment else None


def suite_traceability(suite_path: Path) -> dict[str, Any]:
    """Le lien d'une suite vers son plan : ``{"suite", "spec", "status"}``
    avec ``status`` parmi ``untraced`` (aucun marqueur), ``current``,
    ``changed`` (le plan a bougé depuis la génération), ``obsolete`` (plan
    marqué ``PÉRIMÉE``), ``missing`` (plan introuvable) ou ``unreadable``."""
    entry: dict[str, Any] = {"suite": suite_path.name, "spec": None, "status": "untraced"}
    try:
        text = suite_path.read_text(encoding="utf-8")
    except OSError:
        entry["status"] = "unreadable"
        return entry
    match = MARKER.search(text)
    if not match:
        return entry
    entry["spec"] = match.group("spec")
    root = next((parent for parent in suite_path.resolve().parents
                 if (parent / "specs").is_dir()), None)
    spec = root / match.group("spec") if root else None
    if spec is None or not spec.is_file():
        entry["status"] = "missing"
    elif STALE.search(spec.read_text(encoding="utf-8")):
        entry["status"] = "obsolete"
    elif spec_digest(spec) != match.group("digest"):
        entry["status"] = "changed"
    else:
        entry["status"] = "current"
    return entry


def healings_between(log_path: Optional[str], start: Optional[datetime],
                     end: Optional[datetime]) -> Optional[list[dict[str, Any]]]:
    """Les réparations de localisateurs consignées entre ``start`` et ``end``
    (UTC), ``None`` si le journal n'est pas lisible ou la fenêtre inconnue."""
    if not log_path or start is None or end is None:
        return None
    try:
        lines = Path(log_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    # Le journal est horodaté à la SECONDE, le run à la microseconde : une
    # réparation faite pendant un run court tomberait avant son début.
    start = start.replace(microsecond=0)
    end = end.replace(microsecond=0) + timedelta(seconds=1)
    found = []
    for line in lines:
        try:
            event = json.loads(line)
            moment = datetime.fromisoformat(str(event["timestamp"]))
        except (ValueError, KeyError, TypeError):
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        if start <= moment <= end:
            found.append({key: event.get(key) for key in ("channel", "original", "healed")})
    return found


def collect_run_facts(output_xml: str, healing_log: Optional[str] = None) -> dict[str, Any]:
    """Les faits d'un run depuis son ``output.xml`` (chemin), JSON-safe.

    ``healing_log`` : le journal de healing à croiser (par défaut
    ``SAPFX_HEALING_LOG``) ; sans journal lisible, ``healings`` vaut
    ``None``, jamais une liste vide."""
    from robot.api import ExecutionResult, ResultVisitor

    result = ExecutionResult(str(output_xml))
    tests: list[dict[str, Any]] = []
    sources: set[str] = set()

    class Visitor(ResultVisitor):
        current: Optional[dict[str, Any]] = None

        def start_test(self, test: Any) -> None:
            self.current = {"name": test.full_name, "status": test.status,
                            "message": str(test.message or "").strip(),
                            "screenshots": 0}
            tests.append(self.current)
            source = getattr(test, "source", None) or getattr(test.parent, "source", None)
            if source:
                sources.add(str(source))

        def end_test(self, test: Any) -> None:
            self.current = None

        def visit_message(self, message: Any) -> None:
            current = self.current
            if current is not None and message.html and "<img" in str(message.message):
                current["screenshots"] += 1

    result.visit(Visitor())
    suite = result.suite
    start, end = _utc(getattr(suite, "start_time", None)), _utc(getattr(suite, "end_time", None))
    log = healing_log if healing_log is not None else os.environ.get("SAPFX_HEALING_LOG", "")
    healings = healings_between(log.strip() or None, start, end)
    return {
        "run": {"name": suite.name, "start": _iso(start), "end": _iso(end),
                "suites": sorted(Path(s).name for s in sources)},
        "tests": sorted(tests, key=lambda t: t["name"]),
        "warnings": sorted(str(m.message)[:200] for m in result.errors.messages
                           if m.level == "WARN"),
        "errors": sorted(str(m.message)[:200] for m in result.errors.messages
                         if m.level == "ERROR"),
        "healings": healings,
        "traceability": sorted((suite_traceability(Path(s)) for s in sources),
                               key=lambda e: e["suite"]),
    }
