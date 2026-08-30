"""Posture de **configuration de sécurité** d'un système ABAP, logique pure.

Ce que ce module tranche, et qui n'existait nulle part ailleurs dans le dépôt :
une valeur de paramètre de profil lue sur un système ne se juge pas comme une
donnée métier. Trois raisons, toutes payées live le 2026-08-29 en montant les
campagnes `secu_configuration_*` contre les deux releases du poste.

1. **Une mesure absente n'est pas une valeur.** ``TH_GET_PARAMETER`` ne lève
   aucune exception sur un paramètre inconnu : il rend ``RC = 4`` et une chaîne
   VIDE. Un contrôle qui lit la valeur sans regarder le code de retour prend
   donc un nom mal orthographié pour un paramètre à zéro, et conclut « SNC est
   désactivé » là où il n'a rien mesuré du tout. D'où `classify_parameter` :
   un code de retour non nul rend ``unknown`` avec ``value = None``, jamais
   une chaîne vide.
2. **Non mesuré n'est pas non conforme.** Les deux méritent d'être signalés,
   mais leur remède diffère (corriger le système contre corriger le contrôle),
   et les fondre ferait passer une campagne mal écrite pour un système mal
   configuré. `evaluate_control` garde donc ``not_measurable`` distinct de
   ``deviation``, et un contrôle non mesurable n'est JAMAIS conforme : c'est
   le repli sûr, le même que ``unmapped`` dans `classify_idoc_status` et
   `job_wait_verdict`.
3. **Un comparateur mal choisi est un défaut du contrôle, pas du système.**
   Comparer numériquement ``system/secure_communication`` (qui vaut ``OFF``)
   ne rend pas un système non conforme : cela rend le contrôle faux. Ce cas
   lève une erreur nommant le contrôle, son comparateur et la valeur reçue,
   plutôt que d'inventer un verdict.

Le reste du module sert la **sentinelle** : une posture se compare à une
référence committée (`compare_posture`), ce qui transforme un audit ponctuel
en détection de dérive de configuration, et se sérialise en artefact
déterministe hashé hors horodatage (`posture_artifact`), le patron que le
dépôt applique déjà à l'inventaire DDIC et au croisement entre canaux.

Typé, sans dépendance : les E/S vivent dans le mixin `_rfc_security.py`.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping, Optional, Sequence

__all__ = [
    "COMPARISONS",
    "LOCK_FLAGS",
    "classify_parameter",
    "classify_user_lock",
    "compare_posture",
    "evaluate_control",
    "evaluate_controls",
    "posture_artifact",
    "posture_hash",
    "render_posture_report",
    "summarize_verdicts",
]

#: Les comparateurs admis par un contrôle. Volontairement peu nombreux : un
#: contrôle de sécurité qui aurait besoin d'autre chose est un contrôle qui
#: mérite son propre keyword, pas une mini-grammaire d'expressions.
COMPARISONS = ("equals", "at_least", "at_most", "one_of", "enabled", "disabled")

#: Bits du champ ``USR02-UFLAG``. Un verrou est un masque, pas une énumération :
#: un utilisateur verrouillé par l'administration ET par des échecs de
#: connexion porte 96, valeur qu'une table de correspondance plate ne connaît
#: pas et rendrait « inconnu » sur un cas parfaitement normal.
LOCK_FLAGS = ((32, "locked_by_admin"), (64, "locked_by_failed_logons"),
              (128, "locked_globally"))

_NUMERIC_COMPARISONS = ("at_least", "at_most")


def classify_parameter(name: str, return_code: Any,
                       value: Any) -> dict[str, Any]:
    """Classe UNE lecture de paramètre de profil en fiche JSON-safe.

    Rend ``{"name", "status", "value"}`` où ``status`` vaut ``defined``
    (mesuré, ``value`` porte la chaîne rendue par le système) ou ``unknown``
    (aucune valeur effective, ``value`` vaut ``None``).

    La règle qui justifie la fonction : le code de retour fait foi AVANT la
    valeur. ``TH_GET_PARAMETER`` répond ``RC = 4`` et une chaîne vide pour un
    nom sans valeur effective, or une chaîne vide est indiscernable d'un
    paramètre légitimement vide. Laisser passer la valeur brute revient à
    fabriquer une mesure là où il n'y en a pas.

    Un code de retour ABSENT ou illisible (chaîne vide comprise) est traité
    comme un refus, jamais comme un succès : c'est le repli sûr, et il évite
    qu'un appelant qui oublierait de transmettre le code fabrique des mesures
    à partir de rien.

    ``unknown`` couvre DEUX cas que ce canal ne sépare pas, et le vocabulaire
    est prudent pour cette raison : le paramètre est inconnu de la release, ou
    il est connu du noyau et simplement non positionné. La table dictionnaire
    qui trancherait (``TPFYPROPTY``) a été mesurée VIDE sur les deux releases
    du banc le 2026-08-29, donc affirmer « ce paramètre n'existe pas sur cette
    release » dirait plus que la mesure.
    """
    label = str(name).strip()
    if not label:
        raise ValueError("Le nom du paramètre de profil est vide.")
    raw_code = str(return_code).strip() if return_code is not None else ""
    try:
        code = int(raw_code) if raw_code else -1
    except (TypeError, ValueError):
        code = -1
    if code != 0:
        return {"name": label, "status": "unknown", "value": None}
    return {"name": label, "status": "defined", "value": str(value)}


def classify_user_lock(uflag: Any) -> dict[str, Any]:
    """Classe un ``USR02-UFLAG`` en verdict de verrouillage lisible.

    Rend ``{"uflag", "locked", "reasons"}``, où ``uflag`` est l'entier lu (ou
    ``None`` sur une valeur illisible, dont la forme brute est alors reportée
    sous ``raw_uflag`` : le champ garde son type quoi qu'il arrive, un
    consommateur n'ayant pas à traiter tantôt un entier tantôt une chaîne). ``reasons`` liste les causes
    portées par le masque (``locked_by_admin``, ``locked_by_failed_logons``,
    ``locked_globally``), donc un utilisateur verrouillé pour deux raisons les
    porte toutes les deux, et un masque inconnu reste ``locked`` avec la
    mention ``unmapped_bits`` plutôt que d'être pris pour un compte actif.
    """
    try:
        mask = int(str(uflag).strip() or "0")
    except (TypeError, ValueError):
        return {"uflag": None, "raw_uflag": str(uflag), "locked": True,
                "reasons": ["unreadable"]}
    reasons = [label for bit, label in LOCK_FLAGS if mask & bit]
    remainder = mask
    for bit, _ in LOCK_FLAGS:
        remainder &= ~bit
    if remainder:
        reasons.append("unmapped_bits")
    return {"uflag": mask, "locked": bool(reasons), "reasons": reasons}


def _as_int(control_key: str, comparison: str, raw: Any, origin: str) -> int:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        raise ValueError(
            f"Contrôle '{control_key}' : le comparateur '{comparison}' exige "
            f"un entier, or {origin} vaut {raw!r}. C'est le contrôle qui est "
            f"mal déclaré, pas le système qui est non conforme : corriger le "
            f"comparateur (voir COMPARISONS) ou l'attendu."
        ) from None


def evaluate_control(control: Mapping[str, Any],
                     reading: Mapping[str, Any]) -> dict[str, Any]:
    """Confronte UN contrôle déclaré à SA mesure, et rend le verdict.

    ``control`` porte ``key`` (identifiant stable du contrôle), ``parameter``
    (le paramètre mesuré), ``comparison`` (parmi `COMPARISONS`), ``expected``
    et, optionnellement, ``severity`` et ``rationale``. ``reading`` est une
    fiche produite par `classify_parameter`.

    Le verdict vaut ``compliant``, ``deviation`` ou ``not_measurable``. Ce
    dernier couvre le paramètre que le système ne connaît pas : il n'est pas
    fondu dans ``deviation`` parce qu'il ne se corrige pas au même endroit, et
    il n'est jamais compté comme un succès.
    """
    key = str(control.get("key") or control.get("parameter") or "").strip()
    if not key:
        raise ValueError("Un contrôle de sécurité doit porter une clé.")
    comparison = str(control.get("comparison", "equals")).strip().lower()
    if comparison not in COMPARISONS:
        raise ValueError(
            f"Contrôle '{key}' : comparateur '{comparison}' inconnu. "
            f"Admis : {', '.join(COMPARISONS)}.")

    expected = control.get("expected")
    verdict: dict[str, Any] = {
        "key": key,
        "parameter": str(control.get("parameter") or key),
        "comparison": comparison,
        "expected": expected,
        "severity": str(control.get("severity", "medium")),
        "measured": reading.get("value"),
        "status": str(reading.get("status", "unknown")),
    }
    if control.get("rationale"):
        verdict["rationale"] = str(control["rationale"])

    if verdict["status"] != "defined":
        verdict["verdict"] = "not_measurable"
        verdict["reason"] = (
            "aucune valeur effective pour ce paramètre : il est inconnu de la "
            "release, ou connu et non positionné. Vérifier l'orthographe ET la "
            "casse du nom avant de conclure à une absence de durcissement")
        return verdict

    measured = str(reading.get("value"))
    if comparison in _NUMERIC_COMPARISONS:
        got = _as_int(key, comparison, measured, "la valeur mesurée")
        want = _as_int(key, comparison, expected, "l'attendu")
        ok = got >= want if comparison == "at_least" else got <= want
    elif comparison == "one_of":
        allowed = [str(v) for v in _as_sequence(expected)]
        ok = measured in allowed
        verdict["expected"] = allowed
    elif comparison == "enabled":
        ok = measured not in ("", "0", "OFF", "off", "N", "n")
    elif comparison == "disabled":
        ok = measured in ("", "0", "OFF", "off", "N", "n")
    else:
        ok = measured == str(expected)

    verdict["verdict"] = "compliant" if ok else "deviation"
    return verdict


def _as_sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, (list, tuple)):
        return value
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [value]


def evaluate_controls(controls: Iterable[Mapping[str, Any]],
                      readings: Iterable[Mapping[str, Any]]
                      ) -> list[dict[str, Any]]:
    """Confronte un LOT de contrôles à un lot de mesures, dans l'ordre des
    contrôles.

    Les mesures sont indexées par nom de paramètre. Un contrôle dont le
    paramètre n'a pas été mesuré du tout reçoit ``not_measurable`` comme s'il
    avait été refusé par le système : ne rien mesurer et mesurer un inconnu
    laissent l'auditeur dans le même état, et aucun des deux n'est un succès.
    """
    by_name = {str(r.get("name")): r for r in readings}
    verdicts = []
    for control in controls:
        parameter = str(control.get("parameter") or control.get("key") or "")
        reading = by_name.get(parameter, {"name": parameter,
                                          "status": "unknown", "value": None})
        verdicts.append(evaluate_control(control, reading))
    return verdicts


def summarize_verdicts(verdicts: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Résume un lot de verdicts : comptes par verdict et par sévérité.

    Rend ``{"total", "compliant", "deviation", "not_measurable",
    "deviations_by_severity", "deviating_keys", "not_measurable_keys"}``.
    Les listes de clés sont triées, donc deux exécutions aux mêmes mesures
    produisent le même résumé, ce dont dépend le hash de l'artefact.
    """
    items = list(verdicts)
    counts = {"compliant": 0, "deviation": 0, "not_measurable": 0}
    by_severity: dict[str, int] = {}
    for item in items:
        verdict = str(item.get("verdict", "not_measurable"))
        counts[verdict] = counts.get(verdict, 0) + 1
        if verdict == "deviation":
            severity = str(item.get("severity", "medium"))
            by_severity[severity] = by_severity.get(severity, 0) + 1
    return {
        "total": len(items),
        "compliant": counts["compliant"],
        "deviation": counts["deviation"],
        "not_measurable": counts["not_measurable"],
        "deviations_by_severity": dict(sorted(by_severity.items())),
        "deviating_keys": sorted(str(i["key"]) for i in items
                                 if i.get("verdict") == "deviation"),
        "not_measurable_keys": sorted(str(i["key"]) for i in items
                                      if i.get("verdict") == "not_measurable"),
    }


def compare_posture(current: Iterable[Mapping[str, Any]],
                    reference: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare une posture mesurée à une **référence** committée.

    C'est ce qui fait d'un audit ponctuel une sentinelle : la question posée
    n'est plus « ce système est-il durci » (jugement discutable, et qui rend
    une suite rouge en permanence sur un bac à sable) mais « sa configuration
    de sécurité a-t-elle bougé depuis la dernière fois », qui a une réponse
    binaire et actionnable.

    Rend ``{"drifted", "changed", "appeared", "disappeared", "unchanged"}``.
    Un paramètre passé de mesuré à inconnu compte comme un changement, pas
    comme une disparition : il est toujours contrôlé, c'est sa mesure qui a
    changé de nature.
    """
    now = {str(r.get("name")): r for r in current}
    before = {str(r.get("name")): r for r in reference}
    changed = []
    for name in sorted(set(now) & set(before)):
        was, is_ = before[name], now[name]
        if (str(was.get("status")), was.get("value")) != \
                (str(is_.get("status")), is_.get("value")):
            changed.append({
                "name": name,
                "before": {"status": str(was.get("status")),
                           "value": was.get("value")},
                "after": {"status": str(is_.get("status")),
                          "value": is_.get("value")},
            })
    appeared = sorted(set(now) - set(before))
    disappeared = sorted(set(before) - set(now))
    return {
        "drifted": bool(changed or appeared or disappeared),
        "changed": changed,
        "appeared": appeared,
        "disappeared": disappeared,
        "unchanged": len(set(now) & set(before)) - len(changed),
    }


def posture_hash(payload: Mapping[str, Any]) -> str:
    """Hash SHA-256 d'une posture, **horodatage exclu**.

    Deux campagnes aux mêmes mesures sur la même cible rendent le même hash,
    ce qui permet de comparer deux exécutions sans les relire ligne à ligne.
    """
    stripped = {k: v for k, v in payload.items()
                if k not in ("generated_at", "hash")}
    blob = json.dumps(stripped, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def posture_artifact(identity: Mapping[str, Any],
                     readings: Iterable[Mapping[str, Any]],
                     verdicts: Iterable[Mapping[str, Any]],
                     observations: Optional[Mapping[str, Any]] = None,
                     generated_at: Optional[str] = None) -> dict[str, Any]:
    """Assemble l'artefact déterministe d'une posture de sécurité.

    ``identity`` doit porter ce qui PROUVE la cible. Sur ce poste, ni
    l'identifiant système ni le nom d'hôte applicatif ne la prouvent (les deux
    conteneurs annoncent ``A4H`` et ``vhcala4h``) et l'adresse IP est volatile :
    les ancres sont la release et le kernel. La fonction n'impose pas de clé
    mais refuse une identité vide, parce que comparer deux artefacts anonymes
    revient à comparer deux inconnues.

    Les listes sont triées et le hash est calculé hors horodatage.
    """
    ident = {str(k): str(v) for k, v in dict(identity).items() if str(v).strip()}
    if not ident:
        raise ValueError(
            "L'artefact de posture exige l'identité de la cible mesurée "
            "(release et kernel au minimum) : sans elle, deux artefacts ne "
            "sont pas comparables.")
    measured = sorted((dict(r) for r in readings),
                      key=lambda r: str(r.get("name")))
    judged = sorted((dict(v) for v in verdicts), key=lambda v: str(v.get("key")))
    payload: dict[str, Any] = {
        "identity": dict(sorted(ident.items())),
        "readings": measured,
        "verdicts": judged,
        "summary": summarize_verdicts(judged),
    }
    if observations:
        payload["observations"] = json.loads(
            json.dumps(dict(observations), sort_keys=True, ensure_ascii=False))
    if generated_at:
        payload["generated_at"] = str(generated_at)
    payload["hash"] = posture_hash(payload)
    return payload


def render_posture_report(artifact: Mapping[str, Any]) -> str:
    """Rend un rapport Markdown de la posture, pour le journal Robot.

    Le rapport nomme d'abord ce qui n'a PAS pu être mesuré, avant les écarts :
    un auditeur qui lit une liste d'écarts sans savoir combien de contrôles
    sont restés muets se croit devant un système presque conforme.
    """
    lines: list[str] = ["# Posture de sécurité"]
    identity = dict(artifact.get("identity", {}))
    if identity:
        lines.append("")
        lines.append("| Identité | Valeur |")
        lines.append("|---|---|")
        for key, value in identity.items():
            lines.append(f"| {key} | {value} |")

    summary = dict(artifact.get("summary", {}))
    lines.append("")
    lines.append(
        f"**{summary.get('total', 0)} contrôles** : "
        f"{summary.get('compliant', 0)} conformes, "
        f"{summary.get('deviation', 0)} écarts, "
        f"{summary.get('not_measurable', 0)} non mesurables.")

    verdicts = list(artifact.get("verdicts", []))
    unmeasured = [v for v in verdicts if v.get("verdict") == "not_measurable"]
    if unmeasured:
        lines.append("")
        lines.append("## Non mesurables (à corriger AVANT de lire les écarts)")
        for item in unmeasured:
            lines.append(f"- `{item.get('parameter')}` : {item.get('reason', '')}")

    deviations = [v for v in verdicts if v.get("verdict") == "deviation"]
    if deviations:
        lines.append("")
        lines.append("## Écarts")
        lines.append("")
        lines.append("| Sévérité | Contrôle | Mesuré | Attendu |")
        lines.append("|---|---|---|---|")
        for item in sorted(deviations, key=lambda v: str(v.get("severity"))):
            lines.append(
                f"| {item.get('severity')} | `{item.get('parameter')}` "
                f"| `{item.get('measured')}` "
                f"| {item.get('comparison')} `{item.get('expected')}` |")
    if not deviations and not unmeasured:
        lines.append("")
        lines.append("Aucun écart : la posture mesurée suit la cible déclarée.")
    return "\n".join(lines)
