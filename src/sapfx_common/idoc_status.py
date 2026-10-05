"""Statut d'un IDoc : attente, lien sortant/entrant, pose de statut. Logique pure.

L'attente d'un statut est le point où un test d'intégration asynchrone ment
facilement, de deux façons opposées : il prend un statut d'ERREUR pour un
statut « encore en cours » et attend jusqu'au délai avant d'échouer sans dire
pourquoi, ou il prend un statut hors barème pour un succès. Le verdict ici
suit le patron de ``rfc_tables.job_wait_verdict`` : le CODE décide (jamais le
texte localisé de TEDS1, convention n°3), un statut d'erreur est un échec
IMMÉDIAT qui nomme le code réel, et un statut hors barème n'est jamais un
succès.

Le lien entre un IDoc sortant et l'IDoc entrant que son bouclage tRFC crée
est le TID de la transaction tRFC (``EDIDS-TID``), porté par le statut 03 du
sortant ET par le premier statut de l'entrant (mesuré sur A4H, deux chaînes
sur deux). Aucune proximité d'horodatage n'est utilisée : deux envois dans la
même seconde ne se départageraient pas.

Typed.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from sapfx_common.idoc import normalize_docnum
from sapfx_common.rfc_reads import IDOC_STATUS_CATEGORIES, classify_idoc_status

#: Les champs d'un enregistrement de l'historique (``EDIDS``) que les
#: keywords rendent : l'ordre (``COUNTR``), le statut, l'auteur, l'origine, le
#: message par IDENTIFIANT (jamais par texte) et ses paramètres, et le TID
#: qui relie le sortant à l'entrant. Moins de 400 caractères : sous le tampon
#: de 512 octets de ``RFC_READ_TABLE``.
HISTORY_FIELDS = ("DOCNUM", "COUNTR", "LOGDAT", "LOGTIM", "STATUS", "REPID",
                  "UNAME", "STAMID", "STAMNO", "TID",
                  "STAPA1", "STAPA2", "STAPA3", "STAPA4")

#: Ce qui fait normalement avancer un IDoc resté à un statut donné. Dit dans
#: l'échec d'un délai dépassé : « statut 30 après 30 s » ne désigne rien,
#: « rien ne l'a expédié » désigne le geste manquant.
ADVANCE_HINTS = {
    "01": "il est créé mais le statut 30 n'a pas été posé (Set Idoc Status, ou "
          "ready_for_dispatch à la création)",
    "30": "il est prêt à l'expédition mais rien ne l'a expédié (moniteur WE14, "
          "rapport RSEOUT00)",
    "50": "il est reçu mais pas encore passé à l'application (BD87)",
    "64": "il est prêt pour l'application mais personne ne l'a traité "
          "(BD87, rapport RBDAPP01, ou le mode de traitement du profil "
          "entrant, 3 = programme d'arrière-plan)",
    "62": "il est passé à l'application, qui ne l'a pas terminé (relire "
          "l'historique de l'IDoc : le dernier enregistrement dit où "
          "l'application s'est arrêtée)",
}


def normalize_status(status: Any) -> str:
    """Le code de statut sur deux chiffres (``'3'`` devient ``'03'``), vide si
    le statut est vide."""
    text = str(status).strip()
    return text.zfill(2) if text else ""


def parse_expected(expected: Any) -> Optional[list[str]]:
    """Ce que l'appelant attend : ``None`` pour ``success`` (la catégorie du
    barème), sinon la liste des codes acceptés (liste ou chaîne à virgules).
    Un code qui n'est pas numérique à un ou deux chiffres est refusé."""
    if expected is None:
        return None
    if isinstance(expected, bool):
        raise ValueError("L'argument expected n'accepte pas un booléen, reçu %r." % (expected,))
    if isinstance(expected, int):
        parts = [str(expected)]
    elif isinstance(expected, str):
        parts = [part.strip() for part in expected.replace(";", ",").split(",")]
    else:
        parts = [str(part).strip() for part in expected]
    parts = [part for part in parts if part]
    if not parts:
        raise ValueError("L'argument expected est vide : 'success' ou des codes de statut.")
    if len(parts) == 1 and parts[0].lower() == "success":
        return None
    codes: list[str] = []
    for part in parts:
        if not part.isdigit() or len(part) > 2:
            raise ValueError(
                "L'argument expected accepte 'success' ou des codes de statut "
                "à un ou deux chiffres, reçu %r." % part)
        codes.append(part.zfill(2))
    return codes


def wait_verdict(status: Any, expected: Any = "success") -> dict[str, str]:
    """Verdict de l'attente d'un IDoc depuis son statut courant :
    ``{"state", "status", "category"}`` où ``state`` vaut ``missing`` (aucun
    statut lu : l'IDoc n'existe pas), ``reached``, ``error`` (catégorie
    erreur, jamais attendue), ``unmapped`` (hors barème, jamais un succès) ou
    ``waiting`` (en cours)."""
    code = normalize_status(status)
    if not code:
        return {"state": "missing", "status": "", "category": "unmapped"}
    category = classify_idoc_status(code)
    targets = parse_expected(expected)
    if targets is None:
        reached = category == "success"
    else:
        reached = code in targets
    if reached:
        state = "reached"
    elif category == "error":
        state = "error"
    elif category == "unmapped":
        state = "unmapped"
    else:
        state = "waiting"
    return {"state": state, "status": code, "category": category}


def describe_last_record(history: Sequence[Mapping[str, Any]]) -> str:
    """Le dernier enregistrement de l'historique, par IDENTIFIANT de message
    et paramètres (des données, pas du texte localisé)."""
    if not history:
        return "aucun enregistrement de statut lu"
    last = max(history, key=lambda row: str(row.get("COUNTR", "")))
    identifier = str(last.get("STAMID", "")).strip()
    message = ("message %s/%s" % (identifier, str(last.get("STAMNO", "")).strip() or "?")
               if identifier else "sans identifiant de message")
    params = [str(last.get("STAPA%d" % index, "")).strip() for index in range(1, 5)]
    params = [param for param in params if param]
    return "dernier enregistrement : statut %s, origine %s, %s%s" % (
        str(last.get("STATUS", "")).strip() or "?",
        str(last.get("REPID", "")).strip() or "?", message,
        ", paramètres %s" % params if params else "")


def format_wait_failure(docnum: str, verdict: Mapping[str, str],
                        history: Sequence[Mapping[str, Any]],
                        expected: Any) -> str:
    """Le message d'un échec IMMÉDIAT (statut d'erreur ou hors barème) : il
    nomme le code réel, jamais « encore en cours »."""
    wanted = parse_expected(expected)
    target = "un statut de succès" if wanted is None else "le statut %s" % "/".join(wanted)
    if verdict["state"] == "missing":
        return ("L'IDoc %s n'existe pas (aucun enregistrement EDIDC) : vérifier "
                "le numéro capturé à la création." % docnum)
    if verdict["state"] == "unmapped":
        return ("L'IDoc %s est au statut %s, absent du barème de la "
                "bibliothèque (jamais pris pour un succès, jamais attendu "
                "indéfiniment) ; %s. Attendu : %s."
                % (docnum, verdict["status"], describe_last_record(history), target))
    return ("L'IDoc %s est au statut d'ERREUR %s : aucune attente ne le fera "
            "avancer ; %s. Attendu : %s."
            % (docnum, verdict["status"], describe_last_record(history), target))


def format_wait_timeout(docnum: str, timeout: str, verdict: Mapping[str, str],
                        history: Sequence[Mapping[str, Any]],
                        expected: Any) -> str:
    """Le message d'un délai dépassé : le dernier statut ET ce qui le fait
    normalement avancer."""
    wanted = parse_expected(expected)
    target = "un statut de succès" if wanted is None else "le statut %s" % "/".join(wanted)
    hint = ADVANCE_HINTS.get(verdict["status"])
    cause = ("Pourquoi : %s." % hint if hint
             else "Ce statut n'a pas de cause d'attente documentée ici.")
    return ("L'IDoc %s est resté au statut %s (%s) après %s, %s attendu. %s %s."
            % (docnum, verdict["status"], verdict["category"], timeout, target,
               cause, describe_last_record(history).capitalize()))


def refuse_success_status(status: Any) -> str:
    """Le code de statut à poser, ou un refus. Un test qui pourrait poser
    lui-même un statut de SUCCÈS (03, 12, 16, 41, 53) fabriquerait la preuve
    qu'il prétend mesurer : seuls les statuts hors succès se posent."""
    code = normalize_status(status)
    if not code.isdigit() or len(code) != 2:
        raise ValueError("Le statut doit être un code à deux chiffres, reçu %r." % (status,))
    if classify_idoc_status(code) == "success":
        raise ValueError(
            "Le statut %s est un statut de SUCCÈS (%s) : il ne se pose pas "
            "à la main, il se constate. Un test qui le poserait lui-même ne "
            "prouverait rien." % (code, ", ".join(IDOC_STATUS_CATEGORIES["success"])))
    return code


def tids_of(history: Sequence[Mapping[str, Any]]) -> list[str]:
    """Les TID non vides d'un historique, sans doublon, dans l'ordre."""
    tids: list[str] = []
    for row in sorted(history, key=lambda r: str(r.get("COUNTR", ""))):
        tid = str(row.get("TID", "")).strip()
        if tid and tid not in tids:
            tids.append(tid)
    return tids


def counterpart_candidates(docnum: str, rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Les AUTRES numéros d'IDoc dont un enregistrement de statut porte le TID
    cherché (``rows`` = ``EDIDS`` filtré sur ce TID), triés."""
    own = normalize_docnum(docnum)
    return sorted({normalize_docnum(row["DOCNUM"]) for row in rows
                   if str(row.get("DOCNUM", "")).strip()
                   and normalize_docnum(row["DOCNUM"]) != own})
