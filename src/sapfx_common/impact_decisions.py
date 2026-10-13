"""La décision HUMAINE sur un impact de changement, consignée (backlog § 2.3,
2026-10-09, demande de Cyril) : l'analyse propose les suites à rejouer, un
humain décide pour chacune, et le rapport le dit.

L'analyse ne décide rien : elle désigne, preuves à l'appui, ce que le
transport touche. Restait à garder la trace de ce qu'un humain en a fait :
rejouer une suite (``replay``) ou l'écarter (``skip``), avec sa raison et
son nom. Le geste a deux temps :

1. :func:`decision_template` rend un modèle à remplir : le transport,
   l'EMPREINTE de l'impact (:func:`change_impact.change_impact_hash`) et une
   ligne par suite à juger (celles qui exécutent ou peuvent exécuter, puis
   celles qui ne font que nommer, pour information) ;
2. :func:`apply_decisions` rapporte le fichier rempli sur les suites :
   chacune porte sa ``decision`` (``{decision, reason, by, at}`` ou
   ``None``), et le résumé dit ce qui est à rejouer, écarté, non décidé,
   et les décisions qui ne désignent aucune suite.

Trois règles. Une suite ne s'écarte qu'avec sa RAISON. Une décision dit QUI
l'a prise (le fichier ou la ligne). Et une décision ne couvre que l'impact
qu'elle a vu : si le transport ou les références ont changé depuis
(empreinte ou numéro différents), toutes les décisions sont PÉRIMÉES et
ignorées, jamais appliquées à un autre contenu. Le nom est une déclaration,
pas une signature : committer le fichier rempli donne sa trace. Typed.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Optional, Sequence

DECISIONS = ("replay", "skip")


def _request(impact: Mapping[str, Any]) -> str:
    return str((impact.get("request") or {}).get("request") or "")


def must_decide(suite: Mapping[str, Any]) -> bool:
    """Une suite qui exécute, ou peut exécuter, un objet transporté (ou dont
    l'atteinte est inconnue) : tant qu'un humain ne l'a pas écartée, elle est
    à rejouer."""
    return (suite.get("reach") != "named"
            and suite.get("strength") in ("object", "unknown"))


def decision_template(impact: Mapping[str, Any], suites: Sequence[Mapping[str, Any]],
                      decided_by: str = "") -> dict[str, Any]:
    """Le modèle de décisions à remplir par un humain : ``{request,
    impact_hash, decided_by, decided_at, decisions}``, une ligne par suite
    (``suite``, ``reach``, ``strength``, ``tests``, ``decision`` vide,
    ``reason`` vide), celles à rejouer d'abord.

    Exemple :
    | ${template}=    `Get Change Impact Decision Template`    ${impact}    ${suites}
    | Should Be Equal    ${template}[request]    A4HK900041
    """
    from .change_impact import change_impact_hash

    rows = [{"suite": s["suite"], "reach": s.get("reach"), "strength": s.get("strength"),
             "tests": list(s.get("tests") or []), "decision": "", "reason": ""}
            for s in sorted(suites, key=lambda s: not must_decide(s))]
    return {"request": _request(impact), "impact_hash": change_impact_hash(impact),
            "decided_by": str(decided_by or ""), "decided_at": "", "decisions": rows}


def read_decisions(path: str) -> dict[str, Any]:
    """Un fichier de décisions JSON (``utf-8-sig`` : une édition sous
    Windows peut poser une marque d'ordre d'octets)."""
    with open(path, encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("fichier de décisions %s : un objet JSON est attendu." % path)
    return data


def _table(decisions: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    who_default = str(decisions.get("decided_by") or "").strip()
    when_default = str(decisions.get("decided_at") or "").strip()
    table: dict[str, dict[str, str]] = {}
    for row in decisions.get("decisions") or []:
        suite = str(row.get("suite") or "").strip()
        decision = str(row.get("decision") or "").strip().lower()
        if not suite or not decision:
            continue                                   # pas encore décidée
        if decision not in DECISIONS:
            raise ValueError("décision %r pour %s : attendue %s."
                             % (decision, suite, " ou ".join(DECISIONS)))
        who = str(row.get("decided_by") or who_default).strip()
        if not who:
            raise ValueError("décision sur %s sans auteur : renseigner decided_by (le "
                             "fichier ou la ligne)." % suite)
        reason = str(row.get("reason") or "").strip()
        if decision == "skip" and not reason:
            raise ValueError("%s écartée sans raison : une suite ne s'écarte qu'avec sa "
                             "raison." % suite)
        table[suite] = {"decision": decision, "reason": reason, "by": who,
                        "at": str(row.get("decided_at") or when_default).strip()}
    return table


def apply_decisions(impact: Mapping[str, Any], suites: Sequence[Mapping[str, Any]],
                    decisions: Any) -> dict[str, Any]:
    """Les décisions d'un humain rapportées sur les suites : ``{suites,
    summary}``. ``decisions`` est le fichier rempli (un chemin) ou son
    contenu. Chaque suite reçoit ``decision`` (``{decision, reason, by,
    at}`` ou ``None``) ; ``summary`` rend ``stale`` (et ``stale_reason``),
    ``replay``, ``skip``, ``undecided`` (les suites à rejouer qu'aucun humain
    n'a jugées) et ``orphans`` (les décisions qui ne désignent aucune suite).

    Exemple :
    | ${applied}=    `Apply Change Impact Decisions`    ${impact}    ${suites}    ${decisions}
    | Should Be Empty    ${applied}[summary][undecided]
    """
    from .change_impact import change_impact_hash

    data = read_decisions(decisions) if isinstance(decisions, str) else dict(decisions or {})
    expected, request = change_impact_hash(impact), _request(impact)
    stale_reason = ""
    if str(data.get("request") or request) != request:
        stale_reason = ("décisions prises pour le transport %s, impact du transport %s"
                        % (data.get("request"), request))
    elif str(data.get("impact_hash") or "") != expected:
        stale_reason = ("l'impact a changé depuis la décision (empreinte %s, attendue %s)"
                        % (str(data.get("impact_hash") or "absente")[:12], expected[:12]))
    table = {} if stale_reason else _table(data)
    out = [{**s, "decision": table.get(s["suite"])} for s in suites]
    known = {s["suite"] for s in suites}
    summary = {
        "stale": bool(stale_reason), "stale_reason": stale_reason, "request": request,
        "replay": [s["suite"] for s in out if (s["decision"] or {}).get("decision") == "replay"],
        "skip": [s["suite"] for s in out if (s["decision"] or {}).get("decision") == "skip"],
        "undecided": [s["suite"] for s in out if must_decide(s) and not s["decision"]],
        "orphans": sorted(set(table) - known),
    }
    return {"suites": out, "summary": summary}


def still_to_replay(suites: Sequence[Mapping[str, Any]]) -> list[str]:
    """Les suites qui restent à rejouer : à décider et non écartées par un
    humain (``decision`` absente, ``replay``, ou décisions périmées)."""
    return [s["suite"] for s in suites if must_decide(s)
            and (s.get("decision") or {}).get("decision") != "skip"]


def render_decisions(summary: Optional[Mapping[str, Any]],
                     suites: Sequence[Mapping[str, Any]]) -> list[str]:
    """La section Markdown « Décisions humaines » du rapport."""
    if summary is None:
        return []
    lines = ["## Décisions humaines", ""]
    if summary.get("stale"):
        return lines + ["**Décisions périmées, ignorées** : %s. Refaire le modèle et "
                        "décider sur l'impact actuel." % summary.get("stale_reason"), ""]
    decided = [s for s in suites if s.get("decision")]
    for suite in decided:
        d = suite["decision"]
        # « à rejouer, décidé par » : une décision ``replay`` dit ce qui reste à
        # faire, jamais qu'une suite a été rejouée
        lines.append("- `%s` : %s par %s%s%s" % (
            suite["suite"], "à rejouer, décidé" if d["decision"] == "replay" else "écartée", d["by"],
            " le %s" % d["at"] if d.get("at") else "",
            " (%s)" % d["reason"] if d.get("reason") else ""))
    if not decided:
        lines.append("Aucune décision consignée.")
    undecided = summary.get("undecided") or []
    lines += ["", "Non décidées, donc à rejouer : %s" % (
        ", ".join("`%s`" % s for s in undecided) if undecided else "aucune.")]
    if summary.get("orphans"):
        lines.append("Décisions qui ne désignent aucune suite de l'impact : %s"
                     % ", ".join("`%s`" % s for s in summary["orphans"]))
    return lines + [""]
