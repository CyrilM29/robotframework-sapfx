"""Les PREUVES VISUELLES d'une cartographie (backlog § 2.76, lot 4,
2026-10-12) : pour une interface relevée par RFC, l'écran d'administration
SAP GUI qui la montre, capturé et VÉRIFIÉ.

Le relevé lit des tables ; l'architecte reconnaît des écrans. Une preuve
visuelle joint à une interface la capture de l'écran où un administrateur
irait la constater : SM59 pour une destination RFC, WE20 pour un profil
partenaire IDoc, SICF pour un chemin HTTP servi, ``/IWFND/MAINT_SERVICE``
pour un service OData client. Trois règles :

- une capture n'est une preuve que si l'écran affiche bien l'objet visé :
  les champs lus à l'écran (destination, partenaire et son type, segments du
  chemin) sont confrontés à l'interface, et un écart rend la preuve
  ``verified`` faux, rapportée comme telle, jamais rattachée ;
- le plan vient du relevé lui-même (indication ``proof`` posée par le
  collecteur), jamais d'un nom deviné : une interface sans écran
  d'administration (tRFC en échec, appelant entrant, ligne du référentiel
  seule) n'a pas de preuve et le plan le dit ;
- un manifeste pris sur une autre cible (SID, mandant ou release) est
  ignoré en entier.

Ce module est pur : la navigation SAP GUI et la capture vivent dans l'outil
(``tools/landscape_map/proofs_sapgui.py``). Typed.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Optional

SCREENS = ("SM59", "WE20", "SICF", "MAINT_SERVICE")
TARGET_KEYS = ("system", "client", "basis_release")

__all__ = ["SCREENS", "proof_plan", "path_segments", "verify_proof", "proof_file_name",
           "proof_manifest", "attach_proofs"]


def _key(item: Mapping[str, Any]) -> str:
    return str(item.get("key") or item.get("id") or "")


def path_segments(path: Any) -> list[str]:
    """Les segments d'un chemin ICF, en minuscules (SICF les affiche ainsi)."""
    return [s.lower() for s in str(path or "").strip().split("/") if s]


def proof_plan(model: Mapping[str, Any], only_findings: bool = False) -> dict[str, Any]:
    """Le plan de capture : ``{entries, without_screen}``. Une entrée par
    interface qui porte une indication ``proof`` reconnue (``key``, ``id``,
    ``status`` et les champs de l'écran) ; ``without_screen`` liste les clés
    des interfaces qui n'en ont pas. ``only_findings`` ne garde que les
    interfaces non confirmées, celles que l'architecte doit trancher."""
    entries: list[dict[str, Any]] = []
    without: list[str] = []
    for item in model.get("interfaces") or []:
        if only_findings and item.get("status") == "confirmed":
            continue
        hint = item.get("proof") or {}
        if hint.get("screen") not in SCREENS:
            without.append(_key(item))
            continue
        entries.append({"key": _key(item), "id": item.get("id"), "status": item.get("status"), **dict(hint)})
    return {"entries": entries, "without_screen": without}


def verify_proof(entry: Mapping[str, Any], facts: Mapping[str, Any]) -> list[str]:
    """Les écarts entre ce que l'écran affiche (``facts``) et l'objet visé
    (``entry``). Liste vide : l'écran montre bien l'interface."""
    screen = entry.get("screen")
    gaps: list[str] = []

    def same(field: str, label: str) -> None:
        want, got = str(entry.get(field) or "").strip(), str(facts.get(field) or "").strip()
        if want.upper() != got.upper():
            gaps.append("%s : attendu %r, l'écran affiche %r" % (label, want, got))

    if screen == "SM59":
        same("destination", "destination")
        if entry.get("rfc_type"):
            same("rfc_type", "type de connexion")
    elif screen == "WE20":
        same("partner", "partenaire")
        same("partner_type", "type de partenaire")
        listed = {str(m).strip().upper() for m in facts.get("message_types") or []}
        if str(entry.get("message_type") or "").upper() not in listed:
            gaps.append("type de message %s absent des paramètres %s affichés (%s)" % (
                entry.get("message_type"), "sortants" if entry.get("direction") == "outbound" else "entrants",
                ", ".join(sorted(listed)) or "aucun"))
    elif screen == "MAINT_SERVICE":
        same("service", "service")
        same("namespace", "espace de noms")
        # le registre écrit 0001, le catalogue affiche 1 : une version se compare en nombre
        want, got = str(entry.get("version") or "").strip(), str(facts.get("version") or "").strip()
        if (int(want) if want.isdigit() else want) != (int(got) if got.isdigit() else got):
            gaps.append("version : attendue %r, l'écran affiche %r" % (want, got))
    elif screen == "SICF":
        wanted = path_segments(entry.get("path"))
        shown = [str(s).lower() for s in facts.get("path_segments") or []]
        if wanted != shown:
            gaps.append("chemin : attendu /%s, l'arbre affiche /%s" % ("/".join(wanted), "/".join(shown)))
    else:
        gaps.append("écran %r inconnu" % screen)
    return gaps


def proof_file_name(entry: Mapping[str, Any]) -> str:
    """Un nom de fichier stable et sûr pour la capture d'une interface."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", _key(entry)).strip("-").lower()
    return "preuve-%s-%s.png" % (str(entry.get("screen", "")).lower(), slug[:80] or "interface")


def proof_manifest(target: Mapping[str, Any], proofs: list[Mapping[str, Any]],
                   taken_at: str = "") -> dict[str, Any]:
    """Le manifeste des captures : ``{target, taken_at, proofs}``, chaque
    preuve portant ``key``, ``screen``, ``file``, ``facts``, ``gaps`` et
    ``verified`` (aucun écart)."""
    rows = []
    for proof in proofs:
        gaps = list(proof.get("gaps") or [])
        rows.append({"key": proof.get("key"), "screen": proof.get("screen"), "file": proof.get("file", ""),
                     "facts": dict(proof.get("facts") or {}), "gaps": gaps,
                     "verified": not gaps and bool(proof.get("file")),
                     "error": str(proof.get("error") or "")})
    return {"target": {k: str((target or {}).get(k) or "").strip() for k in TARGET_KEYS},
            "taken_at": taken_at, "proofs": rows}


def attach_proofs(model: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Les preuves rattachées au relevé : ``{by_key, rejected, ignored_reason}``.
    ``by_key`` ne porte que les preuves VÉRIFIÉES d'interfaces présentes ;
    ``rejected`` liste les autres avec leur raison (écart, erreur, clé
    absente) ; un manifeste d'une autre cible est ignoré en entier."""
    current = {k: str((model.get("target") or {}).get(k) or "").strip() for k in TARGET_KEYS}
    taken = {k: str((manifest.get("target") or {}).get(k) or "").strip() for k in TARGET_KEYS}
    if any(taken[k] and taken[k] != current[k] for k in TARGET_KEYS):
        return {"by_key": {}, "rejected": [], "ignored_reason": "preuves prises sur %s, relevé de %s" % (
            "/".join(taken[k] for k in TARGET_KEYS), "/".join(current[k] for k in TARGET_KEYS))}
    keys = {_key(i) for i in model.get("interfaces") or []}
    by_key: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, str]] = []
    for proof in manifest.get("proofs") or []:
        key = str(proof.get("key") or "")
        reason: Optional[str] = None
        if key not in keys:
            reason = "aucune interface %s dans ce relevé" % key
        elif proof.get("error"):
            reason = str(proof["error"])
        elif not proof.get("verified"):
            reason = "; ".join(proof.get("gaps") or []) or "capture absente"
        if reason:
            rejected.append({"key": key, "reason": reason})
        else:
            by_key[key] = {**proof, "taken_at": manifest.get("taken_at", "")}
    return {"by_key": by_key, "rejected": rejected, "ignored_reason": ""}
