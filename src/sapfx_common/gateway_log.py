"""Journal d'erreurs et registre des services de la Gateway SAP (FES), logique pure.

Né du scénario 11 (2026-10-07, a4h, release 754), qui demandait de compter les entrées du journal d'erreurs de la Gateway
(``/IWFND/ERROR_LOG``, table ``/IWFND/SU_ERRLOG``) avant et après un appel
OData invalide. Trois faits mesurés rendent ce compte trompeur, et ce module
existe pour qu'aucun test n'ait à les redécouvrir :

- *le journal REGROUPE les erreurs identiques* : le même appel rejoué ne crée
  pas d'entrée, il fait monter ``ERROR_COUNT`` de l'entrée existante (son
  premier horodatage reste, le dernier avance), et l'identifiant d'opération
  (``OPID``) de l'entrée CHANGE à chaque regroupement. Ni le nombre d'entrées
  ni l'``OPID`` ne sont donc des ancres ; l'URI de la requête l'est ;
- *un service inexistant* est journalisé en ``/IWFND/MED/170`` sans nom de
  service (``SERVICE_NAME`` vide) et avec un statut HTTP ``000``, alors que le
  client a reçu 403 : le statut journalisé n'est pas celui du fil ;
- *les entrées expirent* (``EXPIRY_DATE``, 14 jours mesurés) : un compte « à
  l'instant T » dépend aussi des purges.

Les horodatages du journal (``TIMESTAMP``, ``FIRST_TSTMP``, ``DEC 21``) sont
en heure SYSTÈME, rendus tels quels en ISO sans fuseau.

L'ancre la plus forte d'une entrée est son ``TRANSACTION_ID`` : c'est celui
que le corps de la réponse d'erreur OData porte (``transactionid``), et
celui que l'écran affiche (mesuré par le planner sur la 754).

Le registre des services (``/IWFND/I_MED_SRH``) relie le nom technique d'un
service (``SEPMRA_PROD_MAN``) à son identifiant d'enregistrement local
(``ZSEPMRA_PROD_MAN_0001``) et à sa version. Son ``IS_ACTIVE`` est un champ
CLÉ de version de l'objet modèle (domaine ``/IWFND/MED_MDL_ACTIVE_FLAG``,
``A`` actif, ``I`` inactif), constant sur la cible : il dit qu'une version
active de l'enregistrement existe, PAS que le service est servi (cela se
mesure par le canal API et par l'activation du nœud ICF).

Typed.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Sequence

from sapfx_common import __version__ as _package_version
from robot.api.deco import keyword

#: Version de ce module quand Robot l'importe comme bibliothèque (Libdoc, journal) :
#: celle du paquet, jamais une seconde valeur à aligner à chaque release.
ROBOT_LIBRARY_VERSION = _package_version

#: Seules les fonctions décorées par ``@keyword`` deviennent des keywords :
#: Robot lit aussi ``__all__``, mais le chargeur de rf-mcp ne lit que ce
#: drapeau, et sans lui y publiait les fonctions importées d'ailleurs.
ROBOT_AUTO_KEYWORDS = False

#: Les keywords que ``Library    sapfx_common.gateway_log`` expose. Un assistant
#: interne de la bibliothèque (``icf_name_field``, appelé par ``_rfc_gateway``)
#: n'y entre pas : il n'est pas un keyword.
__all__ = ["sap_timestamp_to_iso", "error_log_verdict"]

ERROR_LOG_TABLE = "/IWFND/SU_ERRLOG"
REGISTRY_TABLE = "/IWFND/I_MED_SRH"
# Projection du journal : moins de 512 caractères par ligne (tampon de
# RFC_READ_TABLE), l'URI comprise (255).
ERROR_LOG_FIELDS = ["SAPCLIENT", "OPID", "USERNAME", "TIMESTAMP", "ERROR_COUNT", "FIRST_TSTMP", "EXPIRY_DATE",
                    "T100_MSGID", "T100_MSGNO", "SERVICE_NAME", "SERVICE_VERSION", "HTTP_STATUS", "LOCATION",
                    "TRANSACTION_ID", "REQUEST_URI"]
REGISTRY_FIELDS = ["SRV_IDENTIFIER", "IS_ACTIVE", "NAMESPACE", "SERVICE_NAME", "SERVICE_VERSION",
                   "IS_SAP_SERVICE", "CHANGED_TIMESTMP"]
VERDICTS = ("new", "aggregated", "unchanged", "missing")


def _text(value: Any) -> str:
    return "" if value is None else str(value)


@keyword
def sap_timestamp_to_iso(value: Any) -> str:
    """``20261007132105.1180900`` (horodatage ABAP long) en
    ``2026-10-07T13:21:05.118090`` ; vide rend vide. Un horodatage illisible
    est REFUSÉ en le nommant, jamais rendu approximatif.

    Exemple :
    | ${iso}=    `Sap Timestamp To Iso`    20261008141654.1538840
    | Should Be Equal    ${iso}    2026-10-08T14:16:54.153884
    """
    raw = _text(value).strip()
    if not raw or raw.strip("0.") == "":
        return ""
    whole, _, frac = raw.partition(".")
    if len(whole) != 14 or not whole.isdigit() or (frac and not frac.isdigit()):
        raise ValueError("Horodatage ABAP illisible : %r (attendu AAAAMMJJhhmmss[.fraction])." % raw)
    iso = "%s-%s-%sT%s:%s:%s" % (whole[0:4], whole[4:6], whole[6:8], whole[8:10], whole[10:12], whole[12:14])
    return iso + ("." + frac[:6].ljust(6, "0") if frac else "")


def iso_to_sap_timestamp(value: Any) -> str:
    """``2026-10-07T13:21:05`` (ou ``…T13:21:05.118090``) en
    ``20261007132105`` : la borne d'une clause ``TIMESTAMP GE`` côté serveur.
    Un ISO illisible est refusé en le nommant.

    Exemple :
    | ${stamp}=    `Iso To Sap Timestamp`    2026-10-07T15:34:12
    | Should Be Equal    ${stamp}    20261007153412
    """
    raw = _text(value).strip().replace("-", "").replace(":", "").replace("T", "").replace(" ", "")
    whole = raw.split(".", 1)[0]
    if len(whole) == 8:
        whole += "000000"
    if len(whole) != 14 or not whole.isdigit():
        raise ValueError("Horodatage ISO illisible : %r (attendu AAAA-MM-JJ[Thh:mm:ss])." % _text(value))
    return whole


def abap_date_to_iso(value: Any) -> str:
    """Une date ABAP ``AAAAMMJJ`` (``20261007``) en ``2026-10-07`` ; vide ou
    ``00000000`` rend vide. Une date illisible est REFUSÉE en la nommant,
    jamais rendue approximative.

    Exemple :
    | ${date}=    `Abap Date To Iso`    20261021
    | Should Be Equal    ${date}    2026-10-21
    """
    raw = _text(value).strip()
    if not raw or raw == "00000000":
        return ""
    if len(raw) != 8 or not raw.isdigit():
        raise ValueError("Date ABAP illisible : %r (attendu AAAAMMJJ)." % raw)
    return "%s-%s-%s" % (raw[0:4], raw[4:6], raw[6:8])


def message_identity(message_class: Any, message_number: Any) -> str:
    """``/IWFND/MED`` et ``170`` donnent ``/IWFND/MED/170`` ; sans classe,
    vide (jamais une identité inventée). Le journal ne porte pas de type de
    message : l'identité est classe et numéro.

    Exemple :
    | ${identity}=    `Message Identity`    /IWFND/MED    170
    | Should Be Equal    ${identity}    /IWFND/MED/170
    """
    mclass = _text(message_class).strip().upper()
    number = _text(message_number).strip()
    if not mclass:
        return ""
    if number.isdigit():
        number = number.zfill(3)
    return "%s/%s" % (mclass, number)


def normalize_error_entry(row: Mapping[str, Any]) -> dict[str, Any]:
    """Une entrée du journal, JSON-safe : ``identity``, ``count`` (entier),
    ``first_seen`` et ``last_seen`` (ISO, heure système), ``expiry``,
    ``request_uri``, ``service_name`` (vide pour un service inexistant),
    ``logged_http_status`` (le statut ÉCRIT au journal, ``000`` gardé tel quel :
    il n'est pas celui du fil), ``service_version``, ``transaction_id`` (celui
    de la réponse HTTP, l'ancre la plus forte), ``user``, ``location`` et
    ``opid`` (rendu pour le lecteur, jamais une ancre : il change à chaque
    regroupement, comme ``transaction_id`` et ``last_seen``, qui prennent ceux
    du DERNIER appel regroupé). ``client`` est le mandant qui a SERVI la
    requête : la preuve, côté système, du mandant d'un appel HTTP.

    Exemple :
    | ${rows}=    Read Rfc Table    /IWFND/SU_ERRLOG    T100_MSGID,T100_MSGNO,ERROR_COUNT,REQUEST_URI
    | ...    alias=a4h    options=T100_MSGID = '/IWFND/MED' AND T100_MSGNO = '170'    rowcount=1
    | ${entry}=    `Normalize Error Entry`    ${rows}[0]
    | Should Be Equal    ${entry}[identity]    /IWFND/MED/170
    """
    count_raw = _text(row.get("ERROR_COUNT")).strip()
    try:
        count = int(count_raw or 0)
    except ValueError as err:
        raise ValueError("ERROR_COUNT illisible : %r." % count_raw) from err
    return {
        "identity": message_identity(row.get("T100_MSGID"), row.get("T100_MSGNO")),
        "message_class": _text(row.get("T100_MSGID")).strip(),
        "message_number": _text(row.get("T100_MSGNO")).strip(),
        "count": count,
        "first_seen": sap_timestamp_to_iso(row.get("FIRST_TSTMP")),
        "last_seen": sap_timestamp_to_iso(row.get("TIMESTAMP")),
        "expiry": abap_date_to_iso(row.get("EXPIRY_DATE")),
        "request_uri": _text(row.get("REQUEST_URI")).strip(),
        "service_name": _text(row.get("SERVICE_NAME")).strip(),
        "logged_http_status": _text(row.get("HTTP_STATUS")).strip(),
        "service_version": _text(row.get("SERVICE_VERSION")).strip(),
        "transaction_id": _text(row.get("TRANSACTION_ID")).strip().upper(),
        "user": _text(row.get("USERNAME")).strip(),
        "client": _text(row.get("SAPCLIENT")).strip(),
        "location": _text(row.get("LOCATION")).strip(),
        "opid": _text(row.get("OPID")).strip(),
    }


def select_entries(entries: Iterable[Mapping[str, Any]], uri_contains: Optional[str] = None,
                   identity: Optional[str] = None, user: Optional[str] = None,
                   since: Optional[str] = None,
                   transaction_id: Optional[str] = None) -> list[dict[str, Any]]:
    """Les entrées normalisées qui répondent aux critères (tous facultatifs),
    triées de la plus ancienne à la plus récente activité. ``uri_contains``
    compare SANS casse dans l'URI (la Gateway met le nom de service en
    majuscules mais l'appelant peut l'écrire autrement) ; ``since`` est un
    ISO comparé à la dernière activité.

    Exemple :
    | ${selected}=    `Select Entries`    ${entries}    identity=/IWFND/MED/170    user=DEVELOPER
    | Should Not Be Empty    ${selected}
    """
    out = []
    for entry in entries:
        e = dict(entry)
        if uri_contains and _text(uri_contains).lower() not in e["request_uri"].lower():
            continue
        if identity and e["identity"].upper() != _text(identity).strip().upper():
            continue
        if user and e["user"].upper() != _text(user).strip().upper():
            continue
        if since and e["last_seen"] < _text(since).strip():
            continue
        if transaction_id and e.get("transaction_id", "") != _text(transaction_id).strip().upper():
            continue
        out.append(e)
    return sorted(out, key=lambda e: (e["last_seen"], e["opid"]))


def single_entry(entries: list[dict[str, Any]], uri_contains: str) -> Optional[dict[str, Any]]:
    """L'entrée unique d'une URI, ``None`` si aucune ; plusieurs = refus qui
    les nomme (un fragment trop court désigne plusieurs requêtes).

    ``entries`` est la sélection DÉJÀ faite sur l'URI (`Select Entries` avec
    ``uri_contains``) : la fonction ne filtre pas, ``uri_contains`` ne sert
    qu'à nommer la requête dans le refus.

    Exemple :
    | ${selected}=    Select Entries    ${entries}    uri_contains=${unique_uri}
    | ${entry}=    `Single Entry`    ${selected}    ${unique_uri}
    | Should Be Equal    ${entry}[request_uri]    ${unique_uri}
    """
    if not entries:
        return None
    if len(entries) > 1:
        raise AssertionError(
            "%d entrées du journal d'erreurs Gateway contiennent %r dans leur URI : %s. "
            "Utiliser un fragment qui désigne UNE requête (un nom de service unique par run)."
            % (len(entries), uri_contains, "; ".join(e["request_uri"] for e in entries)))
    return entries[0]


@keyword
def error_log_verdict(before: Optional[Mapping[str, Any]], after: Optional[Mapping[str, Any]]) -> str:
    """Ce que le journal a fait d'une requête, entre deux lectures de SON
    entrée : ``new`` (absente avant, présente après), ``aggregated`` (présente
    avant, compteur monté), ``unchanged`` (même compteur) ou ``missing``
    (absente après). Jamais déduit d'un nombre d'entrées.

    Exemple :
    | &{before}=    Create Dictionary    count=${1}
    | &{after}=    Create Dictionary    count=${2}
    | ${verdict}=    `Error Log Verdict`    ${before}    ${after}
    | Should Be Equal    ${verdict}    aggregated
    """
    if not after:
        return "missing"
    if not before:
        return "new"
    return "aggregated" if int(after["count"]) > int(before["count"]) else "unchanged"


def normalize_registration(row: Mapping[str, Any]) -> dict[str, Any]:
    """Une ligne du registre ``/IWFND/I_MED_SRH`` en dictionnaire :
    ``identifier``, ``service_name``, ``namespace``, ``version`` (entier),
    ``active_version``, ``is_active_flag``, ``is_sap_service`` et ``changed``
    (ISO). ``active_version`` dit que la ligne est la version ACTIVE du
    service (``IS_ACTIVE`` = ``A`` sur les 47 services mesurés), jamais que le
    service est servi : cela se lit sur son nœud ICF.

    Exemple :
    | ${registration}=    `Normalize Registration`    ${rows}[0]
    | Should Be Equal    ${registration}[identifier]    ZSEPMRA_PROD_MAN_0001
    | Should Be True    ${registration}[active_version]
    """
    version = _text(row.get("SERVICE_VERSION")).strip()
    return {
        "identifier": _text(row.get("SRV_IDENTIFIER")).strip(),
        "service_name": _text(row.get("SERVICE_NAME")).strip(),
        "namespace": _text(row.get("NAMESPACE")).strip(),
        "version": int(version) if version.isdigit() else 0,
        "active_version": _text(row.get("IS_ACTIVE")).strip().upper() == "A",
        "is_active_flag": _text(row.get("IS_ACTIVE")).strip(),
        "is_sap_service": _text(row.get("IS_SAP_SERVICE")).strip().upper() == "X",
        "changed": sap_timestamp_to_iso(row.get("CHANGED_TIMESTMP")),
    }


def registration_verdict(rows: Iterable[Mapping[str, Any]], service_name: str, version: int = 1,
                         namespace: str = "") -> dict[str, Any]:
    """L'enregistrement d'un service : ``found``, ``active_version`` (une
    version active de l'enregistrement existe : jamais la preuve que le
    service est servi) et ses lignes.
    Le nom et l'espace de noms se comparent en majuscules ; une version
    différente ne compte pas comme le service demandé.

    Exemple :
    | ${verdict}=    `Registration Verdict`    ${rows}    SEPMRA_PROD_MAN
    | Should Be True    ${verdict}[found]
    """
    name = _text(service_name).strip().upper()
    ns = _text(namespace).strip().upper()
    if not name:
        raise ValueError("Le nom de service est vide.")
    matches = [normalize_registration(r) for r in rows]
    matches = [m for m in matches if m["service_name"].upper() == name and m["namespace"].upper() == ns
               and m["version"] == int(version)]
    return {"service_name": name, "namespace": ns, "version": int(version), "found": bool(matches),
            "active_version": any(m["active_version"] for m in matches), "registrations": matches}


def split_icf_path(path: Any, default_host: str = "DEFAULT_HOST") -> tuple[str, list[str]]:
    """``/sap/opu/odata`` donne ``("DEFAULT_HOST", ["SAP", "OPU", "ODATA"])`` ;
    un chemin qui commence par l'hôte virtuel lui-même (``/default_host/sap``)
    le perd en tête. Un autre hôte virtuel se nomme par ``default_host``,
    jamais deviné d'après le chemin. Noms en majuscules, comme ICF les
    stocke.

    Exemple :
    | ${host}    ${segments}=    `Split Icf Path`    /sap/opu/odata
    | Should Be Equal    ${host}    DEFAULT_HOST
    | Should Be Equal    ${segments}    ${{ ['SAP', 'OPU', 'ODATA'] }}
    """
    parts = [p.strip().upper() for p in _text(path).replace("\\", "/").split("/") if p.strip()]
    if not parts:
        raise ValueError("Chemin ICF vide.")
    host = default_host.strip().upper()
    return (host, parts[1:]) if parts[0] == host else (host, parts)


ICF_NAME_LENGTH = 15


def icf_name_field(segment: str) -> str:
    """Le champ de la table ``ICFSERVICE`` qui porte un segment de chemin : ``ICF_NAME``
    (15 caractères) pour un nom court ; au-delà, ICF stocke un nom GÉNÉRÉ
    (``BXI0002653``) et le vrai nom dans ``ICFALTNME`` (mesuré le 2026-10-17
    sur ``appl_soap_management``, 754 et 758). Filtrer ``ICF_NAME`` sur un nom
    long fait lever ``SAPSQL_DATA_LOSS`` à ``RFC_READ_TABLE``."""
    return "ICF_NAME" if len(segment) <= ICF_NAME_LENGTH else "ICFALTNME"


def icf_activation(rows: Sequence[Mapping[str, Any]], name: str) -> bool:
    """L'activation d'un nœud ICF depuis ses lignes ``ICFSERVLOC`` : ``X`` =
    actif, aucune ligne = inactif ; plusieurs lignes = refus qui les nomme
    (jamais la première prise en silence).

    Exemple :
    | ${rows}=    Read Rfc Table    ICFSERVLOC    ICF_NAME,ICFPARGUID,ICFACTIVE    alias=a4h
    | ...    options=ICF_NAME = 'ODATA'
    | ${active}=    `Icf Activation`    ${rows}    ODATA
    | Should Be True    ${active}
    """
    if len(rows) > 1:
        raise AssertionError(
            "Plusieurs lignes d'activation ICFSERVLOC pour le nœud %s : %s." %
            (name, "; ".join("%s=%r" % (_text(r.get("ICFPARGUID")).strip(), _text(r.get("ICFACTIVE")).strip())
                             for r in rows)))
    return bool(rows) and _text(rows[0].get("ICFACTIVE")).strip().upper() == "X"
