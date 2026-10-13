"""Politique de session : ce qu'un run (ou un agent) a le droit de faire sur
SAP, décidé AVANT le geste, logique pure (backlog § 2.1, 2026-10-08).

**Un garde-fou d'exploitation, pas un contrôle de sécurité.** La politique
vit côté client : qui contrôle le poste peut la contourner, et la vraie
barrière reste l'autorisation SAP de l'utilisateur (un rôle d'affichage, comme
les rôles de test ``ZSAPFX_EPM_DISPLAY``). Elle sert à ce qu'un agent ou une
suite ne touche pas par mégarde à ce qu'il ne devait pas toucher, et à ce que
chaque geste d'écriture soit décidé, nommé et journalisé.

Trois modes, du plus permissif au plus strict :

- ``full`` (défaut, le comportement d'avant) : les écritures passent, et sont
  journalisées ;
- ``explore`` : chaque écriture exige une approbation explicite juste avant
  (`Approve Next Write`), consommée par le geste qu'elle autorise ;
- ``read_only`` : toute écriture est refusée.

Ce qui compte comme ÉCRITURE, par canal, et la limite de chacun :

- **écran SAP GUI** : le geste d'enregistrement (touche virtuelle 11,
  ``Ctrl+S``, et le bouton ``tbar[0]/btn[11]``). Un bouton qui valide sans
  passer par lui (une suppression qui écrit aussitôt) n'est pas reconnu : la
  liste des transactions permises est le second garde, l'autorisation SAP le
  vrai ;
- **HTTP (OData)** : toute méthode autre que ``GET`` et ``HEAD``, sauf un
  ``$batch`` dont aucune partie n'écrit ;
- **RFC** : tout module fonction hors de la liste de LECTURE. Un appel RFC
  synchrone valide en base à son retour (pas seulement sur
  ``BAPI_TRANSACTION_COMMIT``), donc refuser le seul commit ne protégerait
  rien : seule une liste blanche tient. :data:`READ_FUNCTIONS` porte les
  modules qu'appellent les keywords de LECTURE de la bibliothèque ; une suite
  en déclare d'autres (``functions.read``). C'est une DÉCLARATION, pas une
  preuve qu'un module n'écrit pas.

Les listes de transactions s'appliquent dans tous les modes : une transaction
bloquée l'est toujours, et une liste ``allowed`` non vide n'admet qu'elle. Les
OK-codes système (``/n``, ``/nex``, ``/nend``, ``/i``, ``/o``) passent
toujours : ils naviguent ou referment.

Une politique chargée depuis l'environnement (``SAPFX_SESSION_POLICY``, chemin
d'un fichier JSON) est VERROUILLÉE : un keyword peut la durcir (mode plus
strict, transactions ou modules bloqués en plus), jamais la relâcher. Son
empreinte SHA-256 accompagne chaque entrée du journal d'audit.

QUI approuve, en mode ``explore`` (2026-10-09) : ``approval`` vaut ``agent``
(défaut : le keyword d'approbation suffit, donc un agent peut s'approuver
lui-même, la décision restant explicite et journalisée) ou ``human`` (le
keyword est refusé, l'approbation ne vient que d'un canal où un humain
répond, l'outil ``sapfx_approve_write`` de la surcouche ``sapfx-mcp`` qui lui
pose la question par élicitation MCP). Passer de ``agent`` à ``human`` durcit,
l'inverse relâche. Une approbation peut aussi être LIÉE à une cible
(:func:`target_matches`) : un geste qui ne lui correspond pas est refusé.

Typed.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
from typing import Any, Iterable, Mapping, Optional

ENV_VAR = "SAPFX_SESSION_POLICY"

MODES = ("full", "explore", "read_only")

#: Qui peut approuver une écriture en mode ``explore``, du moins au plus strict.
APPROVERS = ("agent", "human")

SYSTEM_OK_CODES = frozenset({"/N", "/NEX", "/NEND", "/I", "/O"})

SAVE_VKEY = 11
SAVE_BUTTON_SUFFIX = "tbar[0]/btn[11]"

READ_HTTP_METHODS = frozenset({"GET", "HEAD"})

#: Les modules fonction qu'appellent les keywords de LECTURE de SapApiLibrary
#: (relevé du 2026-10-08 sur ``src/``), plus les trois sondes classiques du
#: canal. ``SUSR_LOGIN_CHECK_RFC`` n'y est PAS : une vérification ratée
#: incrémente le compteur d'échecs du compte. ``BAPI_XMI_LOGON`` et
#: ``BAPI_XMI_LOGOFF`` ouvrent et ferment la session XBP des lectures de
#: journal et de spool ; ``BAPI_TRANSACTION_ROLLBACK`` n'écrit rien.
READ_FUNCTIONS = frozenset({
    "RFC_READ_TABLE", "RFC_SYSTEM_INFO", "RFC_PING", "STFC_CONNECTION",
    "TH_GET_PARAMETER", "EM_GET_NUMBER_OF_ENTRIES", "DDIF_FIELDINFO_GET",
    "EDI_IDOC_SYNTAX_GET", "EDI_DOCUMENT_OPEN_FOR_READ", "EDI_SEGMENTS_GET_ALL",
    "EDI_DOCUMENT_CLOSE_READ", "EDI_AGREE_OUT_MESSTYPE_READ",
    "EDI_AGREE_IN_MESSTYPE_READ", "BAPI_XMI_LOGON", "BAPI_XMI_LOGOFF",
    "BAPI_XBP_JOB_JOBLOG_READ", "BAPI_XBP_JOB_SPOOLLIST_READ",
    "BAPI_XBP_GET_SPOOL_AS_DAT", "BAPI_XBP_GET_SPOOL_ATTRIBUTES",
    "BAPI_USER_GET_DETAIL", "AUTHORITY_CHECK", "PRGN_RFC_READ_TRANSACTIONS",
    "RSAU_GET_AUDIT_CONFIG", "RSAU_READ_LOG", "SXPG_COMMAND_LIST_GET",
    "BAPI_TRANSACTION_ROLLBACK", "SSFR_GET_ALL_STRUST_IDENTITIES",
    "SSFR_GET_OWNCERTIFICATE", "SSFR_PARSE_CERTIFICATE", "ICM_GET_INFO",
    "SWNC_COLLECTOR_GET_AGGREGATES",
})


class SessionPolicyError(AssertionError):
    """Un geste refusé par la politique de session (ou une politique
    invalide) : un échec de test, jamais une erreur technique."""


def _names(value: Any, argument: str) -> list[str]:
    """Liste de noms en majuscules depuis une liste, une chaîne à virgules
    ou rien (via ``execute_step`` tout arrive en chaîne)."""
    if value in (None, ""):
        return []
    if isinstance(value, str):
        items: Iterable[Any] = value.split(",")
    elif isinstance(value, (list, tuple, set, frozenset)):
        items = value
    else:
        raise SessionPolicyError("%s : liste de noms attendue, reçu %r." % (argument, value))
    return sorted({str(item).strip().upper() for item in items if str(item).strip()})


def normalize_policy(raw: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """La forme canonique d'une politique (clés connues seulement, noms en
    majuscules et triés). Une clé inconnue ou un mode inconnu sont REFUSÉS :
    une faute de frappe dans un fichier de politique ne doit pas laisser
    passer ce qu'elle voulait interdire."""
    raw = dict(raw or {})
    unknown = set(raw) - {"mode", "approval", "transactions", "functions"}
    if unknown:
        raise SessionPolicyError(
            "Clé(s) de politique inconnue(s) : %s (connues : mode, approval, "
            "transactions, functions)." % ", ".join(sorted(unknown)))
    mode = str(raw.get("mode") or "full").strip().lower()
    if mode not in MODES:
        raise SessionPolicyError("Mode %r inconnu (attendus : %s)." % (mode, ", ".join(MODES)))
    approval = str(raw.get("approval") or "agent").strip().lower()
    if approval not in APPROVERS:
        raise SessionPolicyError("Approbation %r inconnue (attendues : %s)."
                                 % (approval, ", ".join(APPROVERS)))
    transactions = dict(raw.get("transactions") or {})
    functions = dict(raw.get("functions") or {})
    for name, section, keys in (("transactions", transactions, {"allowed", "blocked"}),
                                ("functions", functions, {"read", "blocked"})):
        extra = set(section) - keys
        if extra:
            raise SessionPolicyError(
                "Clé(s) inconnue(s) dans %s : %s (connues : %s)."
                % (name, ", ".join(sorted(extra)), ", ".join(sorted(keys))))
    return {
        "mode": mode,
        "approval": approval,
        "transactions": {"allowed": _names(transactions.get("allowed"), "transactions.allowed"),
                         "blocked": _names(transactions.get("blocked"), "transactions.blocked")},
        "functions": {"read": _names(functions.get("read"), "functions.read"),
                      "blocked": _names(functions.get("blocked"), "functions.blocked")},
    }


def policy_hash(policy: Mapping[str, Any]) -> str:
    """Empreinte SHA-256 de la forme canonique : deux politiques égales ont la
    même empreinte, quel que soit l'ordre de leurs listes."""
    canonical = json.dumps(normalize_policy(policy), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_policy_file(path: str) -> dict[str, Any]:
    """Lit un fichier de politique JSON (``utf-8-sig`` : un fichier édité sous
    Windows porte volontiers une marque d'ordre d'octets)."""
    try:
        with open(path, encoding="utf-8-sig") as handle:
            raw = json.load(handle)
    except (OSError, ValueError) as exc:
        raise SessionPolicyError(
            "Fichier de politique illisible (%s) : %s." % (path, exc)) from exc
    if not isinstance(raw, dict):
        raise SessionPolicyError("Le fichier de politique %s n'est pas un objet JSON." % path)
    return normalize_policy(raw)


def environment_policy() -> Optional[dict[str, Any]]:
    """La politique imposée par l'environnement (``SAPFX_SESSION_POLICY``),
    ``None`` sans variable. Un chemin donné mais illisible ÉCHOUE : une
    politique voulue et absente ne vaut jamais « aucune politique »."""
    path = os.environ.get(ENV_VAR, "").strip()
    return load_policy_file(path) if path else None


def _strictness(mode: str) -> int:
    return MODES.index(mode)


def tightening_refusals(locked: Mapping[str, Any], wanted: Mapping[str, Any]) -> list[str]:
    """Ce en quoi ``wanted`` RELÂCHERAIT la politique verrouillée ``locked``
    (vide si ``wanted`` ne fait que la durcir ou la garder)."""
    locked, wanted = normalize_policy(locked), normalize_policy(wanted)
    refusals = []
    if _strictness(wanted["mode"]) < _strictness(locked["mode"]):
        refusals.append("mode %s moins strict que %s" % (wanted["mode"], locked["mode"]))
    if APPROVERS.index(wanted["approval"]) < APPROVERS.index(locked["approval"]):
        refusals.append("approbation par %s au lieu de %s" % (wanted["approval"],
                                                              locked["approval"]))
    for section, key in (("transactions", "blocked"), ("functions", "blocked")):
        dropped = set(locked[section][key]) - set(wanted[section][key])
        if dropped:
            refusals.append("%s.%s retirés : %s" % (section, key, ", ".join(sorted(dropped))))
    was, now = set(locked["transactions"]["allowed"]), set(wanted["transactions"]["allowed"])
    if was and (not now or not now <= was):
        refusals.append("transactions.allowed élargie (%s)" % (", ".join(sorted(now - was))
                                                               or "liste vidée"))
    added = set(wanted["functions"]["read"]) - set(locked["functions"]["read"])
    if added:
        refusals.append("functions.read élargie : %s" % ", ".join(sorted(added)))
    return refusals


def _matches(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def target_matches(pattern: str, target: str) -> bool:
    """La cible d'un geste correspond-elle au motif d'une approbation ? Un
    motif vide couvre tout geste. Seul ``*`` est un joker (sans casse) : une
    cible d'écran porte des crochets (``wnd[0]/tbar[0]/btn[11]``), qu'un motif
    ``fnmatch`` lirait comme une classe de caractères."""
    wanted = str(pattern or "").strip()
    if not wanted:
        return True
    regex = ".*".join(re.escape(part) for part in wanted.split("*"))
    return re.fullmatch(regex, str(target or "").strip(), re.IGNORECASE) is not None


def bare_transaction(okcode: str) -> str:
    """Le code de transaction d'un OK-code (``/nSE16`` -> ``SE16``), un
    OK-code système rendu tel quel en majuscules (``/NEX``). Un tcode de
    namespace garde son ``/`` (``/IWFND/MAINT_SERVICE``)."""
    code = str(okcode or "").strip().upper()
    if code in SYSTEM_OK_CODES:
        return code
    if re.match(r"^/[NO]/", code):            # /n/IWFND/MAINT_SERVICE
        return code[2:]
    if re.match(r"^/[A-Z0-9_]+/", code):      # /IWFND/MAINT_SERVICE, /NAMESPACE/X
        return code
    if re.match(r"^/[NO]", code):             # /nSE16
        return code[2:]
    return code


def decide_transaction(policy: Mapping[str, Any], okcode: str) -> tuple[str, str]:
    """``(allow|deny, motif)`` pour le lancement de ``okcode``."""
    policy = normalize_policy(policy)
    code = bare_transaction(okcode)
    if code in SYSTEM_OK_CODES:
        return "allow", "OK-code système"
    lists = policy["transactions"]
    if _matches(code, lists["blocked"]):
        return "deny", "transaction %s bloquée par la politique" % code
    if lists["allowed"] and not _matches(code, lists["allowed"]):
        return "deny", ("transaction %s hors de la liste permise (%s)"
                        % (code, ", ".join(lists["allowed"])))
    return "allow", "transaction permise"


def decide_write(policy: Mapping[str, Any], approved: bool) -> tuple[str, str]:
    """``(allow|deny|confirm, motif)`` pour un geste d'ÉCRITURE ; ``approved``
    dit si une approbation explicite l'attend (mode ``explore``)."""
    mode = normalize_policy(policy)["mode"]
    if mode == "full":
        return "allow", "mode full"
    if mode == "read_only":
        return "deny", "écriture refusée en mode read_only"
    if approved:
        return "allow", "écriture approuvée (mode explore)"
    return "confirm", "écriture soumise à approbation en mode explore"


def is_write_function(policy: Mapping[str, Any], function: str) -> bool:
    """Un module fonction compte comme ÉCRITURE s'il n'est ni dans
    :data:`READ_FUNCTIONS` ni déclaré en lecture par la politique."""
    name = str(function or "").strip().upper()
    declared = normalize_policy(policy)["functions"]["read"]
    return name not in READ_FUNCTIONS and not _matches(name, declared)


def function_blocked(policy: Mapping[str, Any], function: str) -> bool:
    name = str(function or "").strip().upper()
    return _matches(name, normalize_policy(policy)["functions"]["blocked"])


_BATCH_WRITE = re.compile(r"^(POST|PUT|PATCH|MERGE|DELETE)\s+\S+\s+HTTP/", re.MULTILINE)


def is_write_request(method: str, path: str, body: Any = None) -> bool:
    """Une requête HTTP écrit-elle ? Toute méthode hors ``GET``/``HEAD``, sauf
    un ``$batch`` dont aucune partie ne porte une méthode d'écriture."""
    verb = str(method or "").strip().upper()
    if verb in READ_HTTP_METHODS:
        return False
    if str(path or "").split("?", 1)[0].rstrip("/").endswith("$batch") and body is not None:
        text = body.decode("utf-8", "replace") if isinstance(body, (bytes, bytearray)) else str(body)
        return bool(_BATCH_WRITE.search(text))
    return True


def is_save_gesture(vkey: Optional[int] = None, element_id: Optional[str] = None) -> bool:
    """Le geste d'enregistrement de SAP GUI : touche 11 (``Ctrl+S``) ou le
    bouton ``tbar[0]/btn[11]`` d'une fenêtre."""
    if vkey is not None and int(vkey) == SAVE_VKEY:
        return True
    return bool(element_id) and str(element_id).strip().endswith(SAVE_BUTTON_SUFFIX)


def describe_policy(policy: Mapping[str, Any], locked: bool) -> dict[str, Any]:
    """La vue JSON-safe d'une politique : forme canonique, empreinte et
    verrou."""
    canonical = normalize_policy(policy)
    return {**canonical, "hash": policy_hash(canonical), "locked": bool(locked),
            "read_functions_preset": sorted(READ_FUNCTIONS)}
