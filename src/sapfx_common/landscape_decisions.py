"""Les décisions de l'ARCHITECTE sur une cartographie, consignées (backlog
§ 2.76, lot 3, 2026-10-12).

La cartographie ne décide rien : elle désigne ce qui est à vérifier (une
interface active absente du référentiel, une interface documentée
introuvable, une source unique...). Restait à garder la trace de ce qu'un
humain en a fait, interface par interface :

- ``accept`` : le flux est reconnu tel quel (raison obligatoire) ;
- ``document`` : il est légitime et doit entrer au référentiel ;
- ``retire`` : il est à décommissionner (raison obligatoire) ;
- ``investigate`` : il reste à instruire.

Le geste a deux temps, comme pour l'analyse d'impact
(:mod:`sapfx_common.impact_decisions`) : :func:`decision_template` rend un
modèle à remplir, :func:`apply_decisions` rapporte le fichier rempli sur le
relevé.

La différence tient à la péremption. Un transport ne change pas, une
cartographie si : chaque relevé a sa fenêtre et ses volumes, donc son
empreinte. Lier les décisions à l'empreinte les périmerait toutes au relevé
suivant, et l'architecte referait le même travail chaque semaine. Une
décision est donc liée à la CLÉ STABLE de l'interface (``RFC:…``,
``IDOC:IN:…``) et au VERDICT qu'elle portait quand l'humain a tranché :

- verdict inchangé : la décision s'applique, au relevé suivant aussi ;
- verdict changé : la décision est PÉRIMÉE et nommée (un flux accepté
  « dormant » qui redevient actif doit être revu), jamais appliquée ;
- autre cible (SID, mandant ou release) : tout le fichier est périmé ;
- clé absente du relevé : la décision est orpheline et listée.

L'empreinte du relevé décidé est consignée pour la traçabilité, sans servir
de critère. Le nom est une déclaration, pas une signature : committer le
fichier rempli donne sa trace. Typed.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from .artifacts import artifact_hash

DECISIONS = ("accept", "document", "retire", "investigate")
REASON_REQUIRED = ("accept", "retire")
TARGET_KEYS = ("system", "client", "basis_release")

__all__ = ["DECISIONS", "REASON_REQUIRED", "interface_key", "must_decide", "survey_hash",
           "decision_template", "read_decisions", "apply_decisions", "summary_line"]


def interface_key(item: Mapping[str, Any]) -> str:
    """La clé stable d'une interface, à défaut son numéro (une entrée
    saisie à la main n'en porte pas toujours)."""
    return str(item.get("key") or item.get("id") or "")


def must_decide(item: Mapping[str, Any]) -> bool:
    """Une interface qu'un humain doit trancher : tout ce qui n'est pas
    ``confirmed`` (deux sources indépendantes et documentée)."""
    return item.get("status") != "confirmed"


def survey_hash(model: Mapping[str, Any]) -> str:
    """L'empreinte du relevé, horodatage exclu."""
    return artifact_hash({k: v for k, v in model.items() if k not in ("sha256", "hash_scope")})


def _target(model: Mapping[str, Any]) -> dict[str, str]:
    target = model.get("target") or {}
    return {k: str(target.get(k) or "").strip() for k in TARGET_KEYS}


def decision_template(model: Mapping[str, Any], decided_by: str = "") -> dict[str, Any]:
    """Le modèle à remplir par l'architecte : ``{target, survey_hash,
    decided_by, decided_at, decisions}``, une ligne par interface à trancher
    (``key``, ``id``, ``party``, ``channel``, ``status``, ``decision`` vide,
    ``reason`` vide), les verdicts les plus graves d'abord.
    """
    from .landscape import STATUS_RANK

    names = {n["id"]: n.get("name", n["id"]) for n in model.get("nodes") or []}
    items = [i for i in model.get("interfaces") or [] if must_decide(i)]
    items.sort(key=lambda i: (-STATUS_RANK.get(i.get("status", ""), 0), interface_key(i)))
    rows = [{"key": interface_key(i), "id": i.get("id"), "party": names.get(i.get("party"), i.get("party")),
             "channel": i.get("channel", ""), "status": i.get("status"), "decision": "", "reason": ""}
            for i in items]
    return {"target": _target(model), "survey_hash": survey_hash(model),
            "decided_by": str(decided_by or ""), "decided_at": "", "decisions": rows}


def read_decisions(path: str) -> dict[str, Any]:
    """Un fichier de décisions JSON (``utf-8-sig`` : une édition sous Windows
    peut poser une marque d'ordre d'octets)."""
    with open(path, encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("fichier de décisions %s : un objet JSON est attendu." % path)
    return data


def _rows(data: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    who_default = str(data.get("decided_by") or "").strip()
    when_default = str(data.get("decided_at") or "").strip()
    table: dict[str, dict[str, str]] = {}
    for row in data.get("decisions") or []:
        key = str(row.get("key") or "").strip()
        decision = str(row.get("decision") or "").strip().lower()
        if not key or not decision:
            continue                                   # pas encore tranchée
        if decision not in DECISIONS:
            raise ValueError("décision %r pour %s : attendue %s." % (decision, key, ", ".join(DECISIONS)))
        if key in table:
            raise ValueError("deux décisions pour l'interface %s : une seule est admise." % key)
        who = str(row.get("decided_by") or who_default).strip()
        if not who:
            raise ValueError("décision sur %s sans auteur : renseigner decided_by (le fichier ou "
                             "la ligne)." % key)
        reason = str(row.get("reason") or "").strip()
        if decision in REASON_REQUIRED and not reason:
            raise ValueError("%s : « %s » exige une raison." % (key, decision))
        table[key] = {"decision": decision, "reason": reason, "by": who,
                      "at": str(row.get("decided_at") or when_default).strip(),
                      "status": str(row.get("status") or "").strip()}
    return table


def apply_decisions(model: Mapping[str, Any], decisions: Any) -> dict[str, Any]:
    """Les décisions rapportées sur le relevé : ``{interfaces, summary}``.
    ``decisions`` est le fichier rempli (un chemin) ou son contenu. Chaque
    interface reçoit ``decision`` (``{decision, reason, by, at}`` ou
    ``None``) ; ``summary`` rend ``target_mismatch`` (et sa raison),
    ``same_survey``, un compte par décision (``accept``, ``document``,
    ``retire``, ``investigate`` : les clés tranchées), ``undecided`` (à
    trancher, aucune décision valide), ``stale`` (``{key, decided_on, now}`` :
    le verdict a changé depuis) et ``orphans`` (clés absentes du relevé).
    """
    data = read_decisions(decisions) if isinstance(decisions, str) else dict(decisions or {})
    current = _target(model)
    decided = {k: str((data.get("target") or {}).get(k) or "").strip() for k in TARGET_KEYS}
    mismatch = [k for k in TARGET_KEYS if decided[k] and decided[k] != current[k]]
    target_reason = ("décisions prises pour %s, relevé de %s" % (
        "/".join(decided[k] for k in TARGET_KEYS), "/".join(current[k] for k in TARGET_KEYS))
        if mismatch else "")
    table = {} if mismatch else _rows(data)
    by_key = {interface_key(i): i for i in model.get("interfaces") or []}
    out: list[dict[str, Any]] = []
    stale: list[dict[str, str]] = []
    for item in model.get("interfaces") or []:
        key = interface_key(item)
        row = table.get(key)
        applied: Optional[dict[str, str]] = None
        if row and row["status"] and row["status"] != item.get("status"):
            stale.append({"key": key, "decided_on": row["status"], "now": str(item.get("status"))})
        elif row:
            applied = {k: row[k] for k in ("decision", "reason", "by", "at")}
        out.append({**item, "decision": applied})
    summary: dict[str, Any] = {
        "target_mismatch": bool(mismatch), "target_reason": target_reason,
        "same_survey": str(data.get("survey_hash") or "") == survey_hash(model),
        "undecided": [interface_key(i) for i in out if must_decide(i) and not i["decision"]],
        "stale": stale, "orphans": sorted(set(table) - set(by_key)),
    }
    for name in DECISIONS:
        summary[name] = [interface_key(i) for i in out if (i["decision"] or {}).get("decision") == name]
    return {"interfaces": out, "summary": summary}


def summary_line(summary: Mapping[str, Any]) -> str:
    """Une phrase de synthèse pour un rapport ou une ligne de commande."""
    if summary.get("target_mismatch"):
        return "Décisions ignorées : %s." % summary.get("target_reason")
    parts = ["%d %s" % (len(summary.get(name) or []), label) for name, label in (
        ("accept", "acceptées"), ("document", "à documenter"), ("retire", "à décommissionner"),
        ("investigate", "à instruire"))]
    text = "Décisions de l'architecte : %s ; %d non tranchées" % (", ".join(parts),
                                                                  len(summary.get("undecided") or []))
    if summary.get("stale"):
        text += " ; %d périmées (verdict changé depuis)" % len(summary["stale"])
    if summary.get("orphans"):
        text += " ; %d sans interface dans ce relevé" % len(summary["orphans"])
    return text + "."
