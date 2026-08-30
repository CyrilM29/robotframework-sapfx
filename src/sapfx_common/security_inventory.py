"""Inventaires de sécurité d'un système ABAP, logique pure.

Voisin de `security_baseline.py`, qui juge des PARAMÈTRES. Ici on classe deux
inventaires dont la lecture brute induit en erreur, chacun pour une raison
différente et chacune mesurée le 2026-08-29 sur les deux releases du banc.

**Le journal d'audit.** `rsau/enable` valait 1 sur les deux cibles, et une
campagne s'arrêtant là conclut « audit actif ». Le relevé complet dit autre
chose : 10 slots de filtrage DÉCLARÉS, **zéro actif**. Le journal est armé au
niveau du noyau et ne filtre rien, donc il n'enregistre pas ce qu'un auditeur
croit qu'il enregistre. `classify_audit_configuration` sépare donc « armé » de
« filtrant » et rend `armed_without_filter`, l'état qui ressemble le plus à un
faux positif de conformité dans tout ce domaine.

**Les destinations RFC.** Une destination qui stocke un logon vers un autre
système est un chemin d'élévation classique, et l'information n'est pas dans
une colonne : elle est enfouie dans un agrégat de marqueurs mono-lettres
(`RFCOPTIONS`). `classify_rfc_destination` en extrait ce qui est établi sans
ambiguïté et **s'arrête là** : les marqueurs non documentés de façon fiable ne
sont pas devinés, et la fonction ne prétend jamais lire un secret, seulement
constater qu'il en existe un.

Typé, sans dépendance : les E/S vivent dans le mixin `_rfc_security.py`.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Optional

__all__ = [
    "OPTION_MARKERS",
    "classify_audit_configuration",
    "classify_rfc_destination",
    "summarize_destinations",
]

#: Les marqueurs de ``RFCDES-RFCOPTIONS`` dont la signification est établie.
#: Volontairement court : le reste (``Y=``, ``h=``, ``z=``, ``W=``…) n'est pas
#: documenté de façon fiable, et deviner un marqueur de sécurité serait pire
#: que de ne pas le lire.
OPTION_MARKERS = {
    "H": "target_host",
    "S": "target_sysnr",
    "M": "target_client",
    "U": "logon_user",
    "L": "logon_language",
    "I": "target_port",
}

#: La marque d'un mot de passe conservé dans le stockage sécurisé. La valeur
#: elle-même n'est jamais exposée par ce canal, et c'est le comportement
#: attendu : on constate qu'un secret existe, pas lequel.
_STORED_PASSWORD = re.compile(r"(?:^|,)\s*v=", re.IGNORECASE)


def classify_audit_configuration(config: Mapping[str, Any]) -> dict[str, Any]:
    """Classe la configuration du **journal d'audit de sécurité**.

    ``config`` est la réponse brute du module de lecture (``ENABLE``,
    ``SLOTCOUNT``, ``SLOTINFO``, ``VERSION``, ``FILESTATUS``…). Rend
    ``{"enabled", "slots_declared", "slots_active", "filtering", "verdict",
    "version", "file_status"}``.

    Le verdict distingue trois états, et la distinction est tout l'intérêt de
    la fonction :

    - ``disabled`` : le journal n'est pas armé ;
    - ``armed_without_filter`` : il est armé et **aucun slot n'est actif**,
      donc il n'enregistre pas ce qu'un lecteur de `rsau/enable` croit qu'il
      enregistre. Mesuré sur les deux releases du banc : 10 slots déclarés,
      zéro actif. C'est le faux positif de conformité le plus coûteux du
      domaine, parce que le paramètre à lui seul dit « actif » ;
    - ``filtering`` : armé, avec au moins un slot actif.

    Un ``SLOTINFO`` absent ou illisible ne compte JAMAIS comme des slots
    actifs : le repli sûr, ici, est de ne pas inventer une couverture d'audit.
    """
    enabled = str(config.get("ENABLE", "")).strip().upper() == "X"
    try:
        declared = int(str(config.get("SLOTCOUNT", 0)).strip() or "0")
    except (TypeError, ValueError):
        declared = 0
    slots = config.get("SLOTINFO") or []
    active = 0
    if isinstance(slots, Iterable) and not isinstance(slots, (str, bytes)):
        for slot in slots:
            if isinstance(slot, Mapping) and \
                    str(slot.get("ENABLE", "")).strip().upper() == "X":
                active += 1
    if not enabled:
        verdict = "disabled"
    elif active == 0:
        verdict = "armed_without_filter"
    else:
        verdict = "filtering"
    return {
        "enabled": enabled,
        "slots_declared": declared,
        "slots_active": active,
        "filtering": active > 0,
        "verdict": verdict,
        "version": str(config.get("VERSION", "")),
        "file_status": str(config.get("FILESTATUS", "")),
    }


def _parse_options(blob: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in str(blob).split(","):
        chunk = part.strip()
        if len(chunk) < 2 or chunk[1] != "=":
            continue
        marker, value = chunk[0], chunk[2:].strip()
        name = OPTION_MARKERS.get(marker)
        if name and value:
            parsed[name] = value
    return parsed


def classify_rfc_destination(destination: str, rfctype: Any,
                             options: Any = "") -> dict[str, Any]:
    """Classe UNE destination RFC : où elle pointe, et si elle porte un logon.

    Rend ``{"destination", "type", "stored_logon", "stored_password",
    "target_host", "target_sysnr", "target_client", "logon_user"}``, les
    champs de cible étant absents quand le marqueur correspondant n'est pas
    présent.

    ``stored_password`` ne dit PAS quel est le mot de passe : il constate
    qu'une destination en conserve un, ce qui est exactement l'information
    d'audit recherchée (une destination à logon stocké est un chemin
    d'élévation vers le système cible, indépendamment de la valeur du secret).
    La valeur reste chiffrée et n'est jamais exposée par ce canal.

    Les marqueurs non établis sont IGNORÉS plutôt que devinés : sur un
    inventaire de sécurité, une interprétation approximative vaut moins que
    l'absence d'interprétation, parce qu'elle serait lue comme un fait.
    """
    name = str(destination).strip()
    if not name:
        raise ValueError("Une destination RFC doit porter un nom.")
    parsed = _parse_options(options or "")
    fiche: dict[str, Any] = {
        "destination": name,
        "type": str(rfctype).strip(),
        "stored_logon": "logon_user" in parsed,
        "stored_password": bool(_STORED_PASSWORD.search(str(options or ""))),
    }
    fiche.update(parsed)
    return fiche


def summarize_destinations(fiches: Iterable[Mapping[str, Any]],
                           types: Optional[Iterable[str]] = None
                           ) -> dict[str, Any]:
    """Résume un inventaire de destinations : comptes par type, et la liste
    de celles qui portent un logon ou un mot de passe stocké.

    ``types`` restreint le résumé (par exemple aux destinations ABAP et HTTP,
    les seules qui portent un logon vers un système tiers). Les listes sont
    triées, donc deux relevés identiques produisent le même résumé, ce dont
    dépend toute comparaison entre deux cibles.
    """
    retenues = [dict(f) for f in fiches]
    if types is not None:
        garde = {str(t).strip() for t in types}
        retenues = [f for f in retenues if str(f.get("type", "")) in garde]
    par_type: dict[str, int] = {}
    for fiche in retenues:
        cle = str(fiche.get("type", ""))
        par_type[cle] = par_type.get(cle, 0) + 1
    return {
        "total": len(retenues),
        "by_type": dict(sorted(par_type.items())),
        "with_stored_logon": sorted(str(f["destination"]) for f in retenues
                                    if f.get("stored_logon")),
        "with_stored_password": sorted(str(f["destination"]) for f in retenues
                                       if f.get("stored_password")),
    }
