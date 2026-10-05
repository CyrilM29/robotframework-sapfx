"""Jobs de fond : retrouver UN run, juger son état d'un coup, garder sa
suppression. Logique pure, socle du mixin ``SapApiLibrary._rfc_jobs``.

Trois faits mesurés sur A4H (S/4HANA 1909, release 754) le 2026-10-01, en
planifiant des jobs par SM36 (fiche scénario 9), justifient le module :

- **SM36 ne rend jamais le ``JOBCOUNT``.** Le message de sauvegarde
  ``BT/S/112`` porte le nom du job et un statut en TEXTE localisé, et le même
  message sert pour « Released » et « Scheduled ». Le run se retrouve donc
  dans ``TBTCO`` par son nom, et seul un nom UNIQUE le désigne sans
  ambiguïté : `select_job_run` refuse zéro run comme plusieurs, en nommant
  ceux qu'il voit, au lieu de prendre le premier.
- **« Encore dans le pipeline » et « statut hors carte » ne sont pas la même
  issue.** `rfc_tables.job_wait_verdict` les fond dans ``waiting`` (pour
  l'attente, c'est juste : dans les deux cas on continue d'attendre), mais un
  constat ponctuel doit les séparer : un job en ``P`` ou ``S`` attend son
  démarrage, un job en ``Z`` (105 runs sur la cible, suspendus par une mise à
  niveau) n'est cartographié nulle part ici. `job_state` rend les cinq issues
  distinctes, sans exception.
- **Un job non démarré se SUPPRIME, il ne se laisse pas** : un ``S`` part
  tout seul plus tard, un ``P`` ne part jamais et encombre le journal. La
  suppression n'est pourtant pas un geste anodin, d'où une liste blanche de
  préfixes OBLIGATOIRE (une liste vide refuse tout, patron de
  ``write_simulation.validate_write_target`` et de ``Delete Idoc``) et un
  refus des statuts qui ne sont pas « non démarré ».
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Sequence

from .rfc_tables import JOB_STATUS_LABELS, PENDING_JOB_STATUSES, summarize_job_statuses
from .robot_args import as_name_list

#: Champs de ``TBTCO`` lus pour décrire un run (largeur cumulée < 512 octets).
JOB_RUN_FIELDS = ("JOBNAME", "JOBCOUNT", "STATUS", "SDLUNAME", "SDLDATE",
                  "SDLTIME", "AUTHCKMAN", "STRTDATE", "STRTTIME", "ENDDATE",
                  "ENDTIME", "JOBCLASS", "SDLSTRTDT", "SDLSTRTTM")

#: Les cinq issues d'un constat ponctuel.
JOB_STATES = ("done", "aborted", "pipeline", "unmapped", "missing")

#: Statuts qu'un job doit porter pour être supprimé par défaut : NON démarré.
DELETABLE_BY_DEFAULT = ("P", "S")

#: Statut jamais supprimable : un job ACTIF (le supprimer laisserait un
#: processus de travail orphelin, et SAP le refuse de toute façon).
ACTIVE_STATUS = "R"


def _timestamp(date: Any, time: Any) -> str:
    """``AAAAMMJJhhmmss`` depuis une date et une heure ``TBTCO`` ; vide quand
    la date n'est pas renseignée (``00000000`` ou blanc : un job non démarré
    n'a ni début ni fin)."""
    date_text = str(date or "").strip()
    time_text = str(time or "").strip()
    if not date_text or set(date_text) == {"0"}:
        return ""
    return date_text + (time_text or "000000")


def normalize_timestamp(value: Any, argument: str = "scheduled_after") -> str:
    """Horodatage technique ``AAAAMMJJhhmmss`` depuis ce qu'un appelant peut
    passer : ``20261001130542``, ``2026-10-01 13:05:42``, ``2026-10-01T13:05``,
    ``20261001`` (minuit). Les seuls chiffres comptent ; moins de 8 chiffres
    ou plus de 14 = refus NOMMANT l'argument. Une heure absente vaut minuit."""
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) < 8 or len(digits) > 14:
        raise ValueError(
            "%s : horodatage illisible %r ; attendu AAAAMMJJ[hhmmss] ou "
            "AAAA-MM-JJ hh:mm:ss (heure système de la cible, celle de TBTCO)."
            % (argument, value))
    return digits.ljust(14, "0")


def describe_job_run(row: Mapping[str, Any]) -> dict[str, Any]:
    """Un run ``TBTCO`` en dict JSON-safe : ``jobname``, ``jobcount``,
    ``status``, ``status_label`` (``"?"`` hors carte), ``scheduled_by``,
    ``client``, ``job_class``, et quatre horodatages techniques
    (``scheduled_at``, ``planned_start_at``, ``started_at``, ``ended_at``,
    heure SYSTÈME, vides quand l'étape n'a pas eu lieu). ``planned_start_at``
    est le départ DEMANDÉ (``SDLSTRTDT``/``SDLSTRTTM``) : la seule preuve
    qu'une date saisie à l'écran est bien celle que le job portera (une
    inversion jour/mois qui reste valide et future serait sinon verte)."""
    status = str(row.get("STATUS", "")).strip().upper()
    return {
        "jobname": str(row.get("JOBNAME", "")).strip(),
        "jobcount": str(row.get("JOBCOUNT", "")).strip(),
        "status": status,
        "status_label": JOB_STATUS_LABELS.get(status, "?"),
        "scheduled_by": str(row.get("SDLUNAME", "")).strip(),
        "client": str(row.get("AUTHCKMAN", "")).strip(),
        "job_class": str(row.get("JOBCLASS", "")).strip(),
        "scheduled_at": _timestamp(row.get("SDLDATE"), row.get("SDLTIME")),
        "planned_start_at": _timestamp(row.get("SDLSTRTDT"), row.get("SDLSTRTTM")),
        "started_at": _timestamp(row.get("STRTDATE"), row.get("STRTTIME")),
        "ended_at": _timestamp(row.get("ENDDATE"), row.get("ENDTIME")),
    }


def _run_line(run: Mapping[str, Any]) -> str:
    return "%s/%s (statut %s, par %s, planifié %s)" % (
        run["jobname"], run["jobcount"], run["status"] or "?",
        run["scheduled_by"] or "?", run["scheduled_at"] or "?")


def select_job_run(rows: Iterable[Mapping[str, Any]], jobname: str,
                   owner: Optional[str] = None,
                   scheduled_after: Optional[str] = None) -> dict[str, Any]:
    """Le run UNIQUE d'un nom de job, après filtres facultatifs : ``owner``
    (l'utilisateur qui l'a planifié, ``SDLUNAME``) et ``scheduled_after``
    (planifié à cet instant ou après, horodatage technique).

    Zéro run = ``AssertionError`` qui dit si des runs existaient AVANT
    filtrage (et lesquels) ; plusieurs runs = ``AssertionError`` qui les
    liste : le premier venu n'est jamais pris, parce qu'un nom réutilisé
    ferait lire le run d'une autre exécution, parfaitement plausible."""
    runs = [describe_job_run(row) for row in rows]
    candidates = list(runs)
    applied = []
    if owner:
        wanted = str(owner).strip().upper()
        candidates = [run for run in candidates if run["scheduled_by"].upper() == wanted]
        applied.append("planifié par %s" % wanted)
    if scheduled_after:
        floor = normalize_timestamp(scheduled_after)
        candidates = [run for run in candidates
                      if run["scheduled_at"] and run["scheduled_at"] >= floor]
        applied.append("planifié à partir de %s" % floor)
    if len(candidates) == 1:
        return candidates[0]
    seen = "; ".join(_run_line(run) for run in runs[:10]) or "aucun"
    if not candidates:
        raise AssertionError(
            "Aucun run du job %r%s. Runs portant ce nom : %s. Un job sauvé "
            "par SM36 apparaît dans TBTCO dès la sauvegarde : un nom absent "
            "veut dire que la sauvegarde n'a pas eu lieu (dialogue resté "
            "ouvert, refus)." % (jobname, (" " + ", ".join(applied)) if applied else "",
                                 seen))
    raise AssertionError(
        "%d runs du job %r%s : %s. Le JOBCOUNT ne se devine pas, un nom "
        "réutilisé désigne plusieurs runs : planifier sous un nom UNIQUE "
        "(horodaté) ou passer jobcount= aux keywords qui l'acceptent."
        % (len(candidates), jobname, (" " + ", ".join(applied)) if applied else "",
           "; ".join(_run_line(run) for run in candidates[:10])))


def job_state(counts: Mapping[str, int]) -> dict[str, Any]:
    """L'état d'un job en UN constat, sans attente : ``{"state", "detail"}``
    où ``state`` vaut ``done``, ``aborted``, ``pipeline``, ``unmapped`` ou
    ``missing``.

    Même priorité que `rfc_tables.job_wait_verdict` (un run annulé prime,
    puis un run en attente), mais ``pipeline`` (au moins un statut
    ``P``/``S``/``Y``/``R``) et ``unmapped`` (aucun statut de la carte en
    attente, et des statuts hors carte comme ``Z``) restent DISTINCTS. Un
    ``F`` accompagné d'un statut hors carte n'est pas ``done`` : rien ne dit
    que le statut inconnu est une fin."""
    if not counts:
        return {"state": "missing",
                "detail": "Aucun run sous ce nom dans TBTCO."}
    described = ", ".join(
        "%s=%d (%s)" % (status, count, JOB_STATUS_LABELS.get(status, "?"))
        for status, count in sorted(counts.items()))
    if counts.get("A"):
        return {"state": "aborted", "detail": "Au moins un run annulé : %s." % described}
    if any(counts.get(status) for status in PENDING_JOB_STATUSES):
        return {"state": "pipeline",
                "detail": "Au moins un run encore dans le pipeline : %s." % described}
    unknown = sorted(status for status in counts if status not in JOB_STATUS_LABELS)
    if unknown:
        return {"state": "unmapped",
                "detail": "Statut(s) hors carte %s : ni une fin ni une attente "
                          "connue (%s)." % (", ".join(unknown), described)}
    return {"state": "done", "detail": "Terminé : %s." % described}


def job_status_report(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Le constat ponctuel complet depuis des lignes ``TBTCO`` (``JOBCOUNT``,
    ``STATUS``) : ``{"state", "detail", "statuses", "runs"}``, chaque run
    ``{jobcount, status, label}`` trié par ``JOBCOUNT``."""
    counts = summarize_job_statuses(rows)
    verdict = job_state(counts)
    runs = sorted(
        ({"jobcount": str(row.get("JOBCOUNT", "")).strip(),
          "status": str(row.get("STATUS", "")).strip().upper(),
          "label": JOB_STATUS_LABELS.get(str(row.get("STATUS", "")).strip().upper(), "?")}
         for row in rows),
        key=lambda run: run["jobcount"])
    return {"state": verdict["state"], "detail": verdict["detail"],
            "statuses": counts, "runs": runs}


def expected_job_state(value: Any) -> str:
    """Normalise l'état attendu d'une assertion ; un état inconnu est refusé
    en listant les cinq issues (une faute de frappe ne doit jamais devenir
    une assertion qui ne peut pas passer, ni une qui passe toujours)."""
    state = str(value).strip().lower()
    if state not in JOB_STATES:
        raise ValueError("État de job inconnu %r ; attendu : %s."
                         % (value, ", ".join(JOB_STATES)))
    return state


def validate_job_deletion(jobname: str, allowed_prefixes: Any,
                          allowed_statuses: Any = None) -> dict[str, Any]:
    """Garde AVANT tout appel de la suppression d'un job : rend
    ``{"prefixes", "statuses"}`` normalisés, ou lève ``ValueError``.

    ``allowed_prefixes`` est OBLIGATOIRE et une liste vide refuse tout : la
    liste blanche est le point de passage de la suppression, pas une
    formalité. Le nom doit commencer par l'un des préfixes (comparaison sans
    casse, les noms de job SAP étant en majuscules). ``allowed_statuses``
    (défaut ``P,S`` : non démarré) ne peut jamais contenir ``R``."""
    prefixes = [p.upper() for p in as_name_list(allowed_prefixes, "allowed_prefixes")]
    if not prefixes:
        raise ValueError(
            "Delete Background Job refuse une liste blanche VIDE : "
            "allowed_prefixes est obligatoire (préfixes des jobs que la suite "
            "a créés, par exemple SAPFX_JOB_).")
    name = str(jobname or "").strip().upper()
    if not name or not any(name.startswith(prefix) for prefix in prefixes):
        raise ValueError(
            "Le job %r ne porte aucun préfixe de la liste blanche (%s) : "
            "suppression refusée avant tout appel." % (jobname, ", ".join(prefixes)))
    statuses = [s.upper() for s in as_name_list(allowed_statuses, "allowed_statuses")] \
        if allowed_statuses not in (None, "") else list(DELETABLE_BY_DEFAULT)
    if ACTIVE_STATUS in statuses:
        raise ValueError(
            "allowed_statuses ne peut pas contenir %s : un job ACTIF ne se "
            "supprime pas (attendre sa fin)." % ACTIVE_STATUS)
    return {"prefixes": prefixes, "statuses": statuses}


def deletion_refusal(run: Mapping[str, Any], statuses: Sequence[str],
                     owner: str = "", client: str = "") -> str:
    """Le message de refus d'un run qui ne doit pas être supprimé, ou une
    chaîne vide quand il peut l'être : run planifié par un AUTRE utilisateur
    que ``owner``, run d'un autre mandant que ``client`` (la liste blanche de
    préfixes ne tient que par le nommage : la revue indépendante du
    2026-10-01 l'a relevé), run actif, statut hors des supprimables."""
    if owner and str(run.get("scheduled_by", "")).casefold() != str(owner).casefold():
        return ("Le run %s/%s a été planifié par %s, pas par %s : suppression "
                "refusée, jamais le job d'autrui." % (
                    run.get("jobname"), run.get("jobcount"),
                    run.get("scheduled_by") or "?", owner))
    if client and str(run.get("client", "")).strip() != str(client).strip():
        return ("Le run %s/%s appartient au mandant %s, pas %s : suppression "
                "refusée." % (run.get("jobname"), run.get("jobcount"),
                              run.get("client") or "?", client))
    status = str(run.get("status", "")).upper()
    if status == ACTIVE_STATUS:
        return ("Le run %s/%s est ACTIF (R) : suppression refusée, attendre "
                "sa fin." % (run.get("jobname"), run.get("jobcount")))
    if status not in statuses:
        return ("Le run %s/%s est en %s (%s), hors des statuts supprimables "
                "%s : suppression refusée. Un job terminé porte son journal "
                "et son spool, les preuves d'une exécution ; l'élargir se fait "
                "par allowed_statuses, en connaissance de cause."
                % (run.get("jobname"), run.get("jobcount"), status or "?",
                   JOB_STATUS_LABELS.get(status, "?"), ", ".join(statuses)))
    return ""
