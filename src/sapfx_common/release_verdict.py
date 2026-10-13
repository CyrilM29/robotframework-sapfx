"""Verdict GO / NO-GO d'un run, calculé sur son ``output.xml`` (backlog § 2.8,
2026-10-08).

**Des critères de décision explicites d'abord, jamais un nombre magique** (la
nuance de la revue externe du 2026-09-06 : un score global peut attendre).
Chaque critère est un FAIT compté sur le run (``release_facts``) et une
sévérité qui dépend du profil ; le verdict est NO-GO dès qu'un critère
bloquant échoue, et le rapport dit lequel, avec ses preuves.

Trois profils, au barème visible dans :data:`PROFILES` :

- ``strict`` : tout bloque, y compris un critère qu'on n'a pas pu MESURER
  (un journal de healing absent ne prouve pas l'absence de dérive) ;
- ``standard`` (défaut) : échecs, erreurs d'exécution, sauts sans raison et
  plans qui ont bougé bloquent ; captures dans un test vert, avertissements et
  localisateurs réparés sont signalés ;
- ``ramp_up`` : une campagne en construction ; les échecs ne bloquent qu'au
  delà de :data:`RAMP_UP_MAX_FAILED_RATIO` des tests exécutés (surchargeable).

Les deux critères qui n'existent nulle part ailleurs sont les nôtres : les
localisateurs RÉPARÉS pendant le run (un run vert qui a réparé trois
localisateurs n'est pas le même qu'un run vert qui n'en a réparé aucun) et
les suites dont le PLAN a bougé depuis la génération.

Robot Framework : ``Library    sapfx_common.release_verdict`` pour juger un
run précédent dans une suite de restitution. Ligne de commande :
``python -m sapfx_common.release_verdict output.xml --profile standard``,
code retour 0 pour GO, 1 pour NO-GO, 2 pour une erreur d'usage.

Typed.
"""
from __future__ import annotations

import argparse
import re
import sys
from typing import Any, Mapping, Optional, Sequence

from sapfx_common.artifacts import build_deterministic_artifact, write_deterministic_artifact
from sapfx_common.release_facts import collect_run_facts

__all__ = ["judge_release", "release_verdict", "render_verdict_report",
           "release_verdict_should_be_go"]

RAMP_UP_MAX_FAILED_RATIO = 0.10

CRITERIA = (
    ("executed", "Au moins un test exécuté"),
    ("execution_errors", "Erreurs d'exécution (import, syntaxe)"),
    ("failed", "Tests en échec"),
    ("unexplained_skips", "Tests sautés sans raison"),
    ("skipped", "Tests sautés"),
    ("green_screenshots", "Tests verts qui ont écrit une capture sur erreur"),
    ("warnings", "Avertissements d'exécution"),
    ("healings", "Localisateurs réparés pendant le run"),
    ("stale_specs", "Suites dont le plan a bougé depuis la génération"),
    ("untraced_suites", "Suites sans plan"),
)

_B, _W, _I = "blocking", "warning", "info"
PROFILES: dict[str, dict[str, str]] = {
    "strict": {"executed": _B, "execution_errors": _B, "failed": _B,
               "unexplained_skips": _B, "skipped": _B, "green_screenshots": _B,
               "warnings": _B, "healings": _B, "stale_specs": _B, "untraced_suites": _W},
    "standard": {"executed": _B, "execution_errors": _B, "failed": _B,
                 "unexplained_skips": _B, "skipped": _W, "green_screenshots": _W,
                 "warnings": _W, "healings": _W, "stale_specs": _B, "untraced_suites": _I},
    "ramp_up": {"executed": _B, "execution_errors": _B, "failed": "ratio",
                "unexplained_skips": _W, "skipped": _I, "green_screenshots": _I,
                "warnings": _I, "healings": _I, "stale_specs": _W, "untraced_suites": _I},
}

_STALE = ("changed", "obsolete", "missing", "unreadable")

#: Les messages que Robot met lui-même sur un saut (mesurés sur la 7.5) : ils
#: disent COMMENT le test a été sauté, jamais POURQUOI. Le dernier cache un
#: ÉCHEC (``robot:skip-on-failure``), le texte d'origine suivant.
_DEFAULT_SKIP = re.compile(
    r"^(Skipped with Skip keyword\.|(Failed test|Test) skipped using '[^']+' "
    r"(tag|command line option)\.)")


def unexplained_skip(message: str) -> bool:
    """Un saut sans raison : message vide, ou message par défaut de Robot."""
    text = str(message or "").strip()
    return not text or bool(_DEFAULT_SKIP.match(text))


def _measures(facts: Mapping[str, Any]) -> dict[str, tuple[Optional[int], list[str]]]:
    """``{critère: (valeur, preuves)}`` ; ``None`` = non mesuré."""
    tests = list(facts.get("tests") or [])
    executed = [t for t in tests if t["status"] in ("PASS", "FAIL")]
    failed = [t for t in tests if t["status"] == "FAIL"]
    skipped = [t for t in tests if t["status"] == "SKIP"]
    silent = [t for t in skipped if unexplained_skip(t.get("message", ""))]
    shots = [t for t in tests if t["status"] == "PASS" and t.get("screenshots")]
    healings = facts.get("healings")
    trace = list(facts.get("traceability") or [])
    stale = [e for e in trace if e["status"] in _STALE]
    untraced = [e for e in trace if e["status"] == "untraced"]
    return {
        "executed": (len(executed), []),
        "execution_errors": (len(facts.get("errors") or []), list(facts.get("errors") or [])),
        "failed": (len(failed), ["%s : %s" % (t["name"], t["message"][:160]) for t in failed]),
        "unexplained_skips": (len(silent), ["%s : %s" % (t["name"], t["message"][:160] or "(vide)")
                                              for t in silent]),
        "skipped": (len(skipped), ["%s : %s" % (t["name"], t["message"][:160]) for t in skipped]),
        "green_screenshots": (len(shots), ["%s (%d)" % (t["name"], t["screenshots"])
                                           for t in shots]),
        "warnings": (len(facts.get("warnings") or []), list(facts.get("warnings") or [])),
        "healings": (None if healings is None else len(healings),
                     ["%s -> %s" % (h.get("original"), h.get("healed"))
                      for h in (healings or [])]),
        "stale_specs": (len(stale), ["%s : %s (%s)" % (e["suite"], e["spec"], e["status"])
                                     for e in stale]),
        "untraced_suites": (len(untraced), [e["suite"] for e in untraced]),
    }


def judge_release(facts: Mapping[str, Any], profile: str = "standard",
                  max_failed_ratio: Any = None) -> dict[str, Any]:
    """Le verdict d'un run depuis ses faits (`collect_run_facts`) : ``{"verdict",
    "profile", "summary", "criteria", "blocking", "not_measured", "run",
    "thresholds"}``. Logique pure."""
    name = str(profile or "standard").strip().lower().replace("-", "_")
    if name not in PROFILES:
        raise ValueError("Profil %r inconnu (attendus : %s)." % (profile, ", ".join(PROFILES)))
    ratio = RAMP_UP_MAX_FAILED_RATIO if max_failed_ratio in (None, "") else float(max_failed_ratio)
    measures = _measures(facts)
    tests = list(facts.get("tests") or [])
    executed = measures["executed"][0] or 0
    criteria = []
    for key, label in CRITERIA:
        value, evidence = measures[key]
        severity = PROFILES[name][key]
        if value is None:
            status = "fail" if name == "strict" and severity == _B else "not_measured"
        elif key == "executed":
            status = "pass" if value > 0 else "fail"
        elif value == 0:
            status = "pass"
        elif severity == "ratio":
            severity = _B if executed and value / executed > ratio else _W
            status = "fail" if severity == _B else "warn"
        else:
            status = {_B: "fail", _W: "warn", _I: "info"}[severity]
        criteria.append({"id": key, "label": label, "severity": severity, "value": value,
                         "status": status, "evidence": evidence[:10],
                         "evidence_total": len(evidence)})
    blocking = [c["id"] for c in criteria if c["status"] == "fail"]
    return {
        "verdict": "NO-GO" if blocking else "GO", "profile": name,
        "summary": {"total": len(tests), "executed": executed,
                    "passed": sum(t["status"] == "PASS" for t in tests),
                    "failed": measures["failed"][0], "skipped": measures["skipped"][0]},
        "criteria": criteria, "blocking": blocking,
        "not_measured": [c["id"] for c in criteria if c["value"] is None],
        "run": dict(facts.get("run") or {}),
        "thresholds": {"max_failed_ratio": ratio},
    }


def release_verdict(output_xml: str, profile: str = "standard",
                    healing_log: Optional[str] = None, max_failed_ratio: Any = None,
                    artifact_path: Optional[str] = None) -> dict[str, Any]:
    """Le verdict d'un run depuis son ``output.xml``, en artefact déterministe
    (empreinte SHA-256 hors horodatage : deux jugements du même run ont la
    même) ; écrit dans ``artifact_path`` s'il est donné."""
    verdict = judge_release(collect_run_facts(output_xml, healing_log), profile,
                            max_failed_ratio)
    if artifact_path:
        write_deterministic_artifact(str(artifact_path), verdict)
    return build_deterministic_artifact(verdict)


def render_verdict_report(verdict: Mapping[str, Any]) -> str:
    """Le rapport Markdown d'un verdict : les critères NON MESURÉS d'abord (une
    liste d'écarts sans eux donne l'illusion d'un run presque irréprochable),
    puis le tableau, puis les preuves de ce qui bloque ou alerte."""
    s = verdict["summary"]
    lines = ["# Verdict de run : %s" % verdict["verdict"], "",
             "Profil `%s`, %d tests (%d exécutés, %d verts, %d en échec, %d sautés)."
             % (verdict["profile"], s["total"], s["executed"], s["passed"], s["failed"],
                s["skipped"]), ""]
    if verdict["not_measured"]:
        lines += ["**Non mesuré** : %s." % ", ".join(verdict["not_measured"]), ""]
    lines += ["| Critère | Valeur | Sévérité | Statut |", "|---|---:|---|---|"]
    for c in verdict["criteria"]:
        value = "n/m" if c["value"] is None else str(c["value"])
        lines.append("| %s | %s | %s | %s |" % (c["label"], value, c["severity"], c["status"]))
    for c in verdict["criteria"]:
        if c["status"] in ("fail", "warn") and c["evidence"]:
            lines += ["", "**%s** (%s) :" % (c["label"], c["status"])]
            lines += ["- %s" % item for item in c["evidence"]]
            if c["evidence_total"] > len(c["evidence"]):
                lines.append("- ... et %d de plus" % (c["evidence_total"] - len(c["evidence"])))
    return "\n".join(lines) + "\n"


def release_verdict_should_be_go(verdict: Mapping[str, Any]) -> None:
    """Échoue en nommant les critères bloquants si le verdict est NO-GO."""
    if verdict["verdict"] != "GO":
        raise AssertionError("Verdict NO-GO (profil %s) : %s." % (
            verdict["profile"], "; ".join(
                "%s = %s" % (c["label"], c["value"]) for c in verdict["criteria"]
                if c["status"] == "fail")))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sapfx_common.release_verdict",
        description="Verdict GO / NO-GO d'un run Robot Framework depuis son output.xml.")
    parser.add_argument("output_xml")
    parser.add_argument("--profile", default="standard", choices=sorted(PROFILES))
    parser.add_argument("--healing-log", default=None)
    parser.add_argument("--max-failed-ratio", default=None)
    parser.add_argument("--json", dest="json_path", default=None)
    parser.add_argument("--markdown", dest="markdown_path", default=None)
    args = parser.parse_args(argv)
    try:
        verdict = release_verdict(args.output_xml, args.profile, args.healing_log,
                                  args.max_failed_ratio, args.json_path)
    except Exception as exc:                 # noqa: BLE001 (erreur d'usage nommée)
        print("Verdict impossible : %s" % exc, file=sys.stderr)
        return 2
    report = render_verdict_report(verdict)
    if args.markdown_path:
        with open(args.markdown_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(report)
    sys.stdout.write(report)
    return 0 if verdict["verdict"] == "GO" else 1


if __name__ == "__main__":                   # pragma: no cover
    # Sous Windows les flux standard suivent l'encodage du poste : un accent
    # du rapport y tuerait le processus.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())
