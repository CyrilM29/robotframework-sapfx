"""Certificat TLS d'un système ABAP et services de son ICM, logique pure.

Né du scénario 12 (2026-10-08, ABAP Platform 2023, release 758) : lire la date
de validité du certificat du PSE « SSL serveur standard » de STRUST, la juger,
et la croiser avec les services réellement actifs de l'ICM (SMICM) et avec le
certificat présenté sur le fil. Trois faits mesurés ce jour-là fondent ce
module :

- **le module de lecture d'un certificat rend ses dates en temps ASN.1**
  (``SSFR_PARSE_CERTIFICATE`` : ``EV_VALIDTO = 20380101000001Z``, UTC), forme
  indépendante de la langue et du format de date de l'utilisateur, à
  l'inverse de l'écran ;
- **un certificat absent ne lève rien** : ``SSFR_GET_OWNCERTIFICATE`` rend un
  DER VIDE avec un message ``1S/E/406`` dans sa table de retour, et
  ``SSFR_PARSE_CERTIFICATE`` sur un DER vide rend des dates VIDES avec
  ``1S/E/309``. Une date vide n'est donc jamais un « valide » : elle donne le
  verdict ``unknown``, qui échoue comme un certificat expiré ;
- **les deux conteneurs du banc portent le MÊME certificat** (même numéro de
  série, même échéance) et les mêmes services ICM : rien ici ne prouve la
  cible, la release se prouve canal par canal ailleurs.

Typed.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

# Verdicts d'échéance. Seul ``valid`` est un succès : ``unknown`` (date
# illisible ou absente) et ``not_yet_valid`` échouent comme ``expired``.
EXPIRY_VERDICTS = ("valid", "expiring", "expired", "not_yet_valid", "unknown")


def parse_certificate_time(value: Any) -> Optional[datetime]:
    """Temps ASN.1 d'un certificat en ``datetime`` UTC.

    Accepte la forme généralisée ``AAAAMMJJhhmmssZ`` (celle que rend
    ``SSFR_PARSE_CERTIFICATE``) et la forme UTC courte ``AAMMJJhhmmssZ``
    (années 50 à 99 = 19xx, 00 à 49 = 20xx, RFC 5280). Vide rend ``None``.
    Une forme illisible est REFUSÉE en la nommant, jamais rendue
    approximative : une échéance devinée ferait un verdict faux."""
    raw = "" if value is None else str(value).strip()
    if not raw:
        return None
    text = raw[:-1] if raw.upper().endswith("Z") else raw
    try:
        if len(text) == 14 and text.isdigit():
            moment = datetime.strptime(text, "%Y%m%d%H%M%S")
        elif len(text) == 12 and text.isdigit():
            year = int(text[:2])
            century = 1900 if year >= 50 else 2000
            moment = datetime.strptime(str(century + year) + text[2:], "%Y%m%d%H%M%S")
        else:
            raise ValueError(raw)
    except ValueError:
        raise ValueError("Date de certificat illisible : %r (attendu AAAAMMJJhhmmssZ ou "
                         "AAMMJJhhmmssZ, temps ASN.1 en UTC)." % raw) from None
    return moment.replace(tzinfo=timezone.utc)


def _now(now: Any) -> datetime:
    if now is None or str(now).strip() == "":
        return datetime.now(timezone.utc)
    if isinstance(now, datetime):
        return now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    text = str(now).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Instant de référence illisible : %r (attendu ISO 8601, "
                         "par exemple 2026-10-08 ou 2026-10-08T12:00:00Z)." % text) from None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def certificate_expiry_verdict(valid_to: Any, valid_from: Any = None, warning_days: Any = 30,
                               now: Any = None) -> dict[str, Any]:
    """Juge l'échéance d'un certificat et rend ``{"verdict", "valid_to",
    "valid_from", "now", "days_remaining", "warning_days"}`` (dates en ISO
    UTC, ``days_remaining`` entier arrondi vers le bas, négatif une fois
    expiré).

    ``verdict`` : ``expired`` (échéance passée), ``expiring`` (moins de
    ``warning_days`` jours restants), ``not_yet_valid`` (début de validité
    futur), ``unknown`` (échéance absente), sinon ``valid``. ``now`` (ISO)
    fixe l'instant de référence : c'est ainsi qu'une garde d'expiration se
    voit MORDRE sans toucher au certificat."""
    try:
        days = int(str(warning_days).strip())
    except ValueError:
        raise ValueError("warning_days doit être un nombre entier de jours, reçu %r." % (warning_days,)) from None
    if days < 0:
        raise ValueError("warning_days ne peut pas être négatif (reçu %d)." % days)
    reference = _now(now)
    end = parse_certificate_time(valid_to)
    start = parse_certificate_time(valid_from)
    result: dict[str, Any] = {
        "valid_to": end.isoformat() if end else None,
        "valid_from": start.isoformat() if start else None,
        "now": reference.isoformat(),
        "warning_days": days,
        "days_remaining": None,
    }
    if end is None:
        result["verdict"] = "unknown"
        return result
    remaining = end - reference
    result["days_remaining"] = remaining.days
    if remaining.total_seconds() <= 0:
        result["verdict"] = "expired"
    elif start is not None and start > reference:
        result["verdict"] = "not_yet_valid"
    elif remaining < timedelta(days=days):
        result["verdict"] = "expiring"
    else:
        result["verdict"] = "valid"
    return result


def describe_expiry_failure(subject: str, verdict: Mapping[str, Any]) -> str:
    """Le message d'échec d'une garde d'échéance : il nomme toujours
    l'échéance MESURÉE, l'instant de référence et le seuil."""
    kind = verdict.get("verdict")
    label = subject or "le certificat"
    if kind == "unknown":
        return ("Échéance de %s illisible ou absente : aucune date n'a été lue, ce qui n'est "
                "jamais une validité (certificat absent du PSE ?)." % label)
    head = {"expired": "est EXPIRÉ", "expiring": "expire bientôt",
            "not_yet_valid": "n'est pas encore valide"}.get(str(kind), "n'est pas valide")
    return ("%s %s : échéance mesurée %s, instant de référence %s, %s jour(s) restant(s), "
            "seuil d'alerte %s jour(s)%s." % (
                label[:1].upper() + label[1:], head, verdict.get("valid_to"), verdict.get("now"),
                verdict.get("days_remaining"), verdict.get("warning_days"),
                (", début de validité %s" % verdict.get("valid_from")) if kind == "not_yet_valid" else ""))


def certificate_fingerprint(der: Any) -> str:
    """Empreinte SHA-256 (hexadécimal minuscule) d'un certificat DER ; vide
    pour un DER vide. Accepte des octets ou leur forme hexadécimale."""
    data = _as_bytes(der)
    return hashlib.sha256(data).hexdigest() if data else ""


def _as_bytes(der: Any) -> bytes:
    if der is None:
        return b""
    if isinstance(der, (bytes, bytearray)):
        return bytes(der)
    text = str(der).strip()
    try:
        return bytes.fromhex(text)
    except ValueError:
        raise ValueError("Certificat illisible : ni octets ni hexadécimal.") from None


def bapiret_errors(rows: Optional[Sequence[Mapping[str, Any]]]) -> list[dict[str, str]]:
    """Les messages bloquants (``E``/``A``/``X``) d'une table BAPIRET2, avec
    leur identité ``CLASSE/TYPE/NUMÉRO`` : la seule forme comparable (le
    texte est localisé)."""
    found = []
    for row in rows or []:
        kind = str(row.get("TYPE", "")).strip().upper()
        if kind in ("E", "A", "X"):
            found.append({"identity": "%s/%s/%s" % (str(row.get("ID", "")).strip(), kind,
                                                    str(row.get("NUMBER", "")).strip()),
                          "message": str(row.get("MESSAGE", "")).strip()})
    return found


# --------------------------------------------------------------------- #
# Identités STRUST
# --------------------------------------------------------------------- #
class StrustIdentityNotFoundError(AssertionError):
    """L'identité STRUST demandée n'a pas de PSE en base (``1S/E/406``) ou ne
    porte pas de certificat propre : un constat, jamais une validité."""


def strust_identity(value: Any) -> tuple[str, str]:
    """``SSLS/DFAULT`` ou la clé de l'arbre de STRUST ``SSLSDFAULT`` en
    ``(contexte, application)``. Le contexte fait toujours 4 caractères
    (relevé sur les 13 identités de la 758 : ``SSLS``, ``SSLC``, ``PROG``,
    ``WSSE``, ``SMIM``, ``SSFA``), ce qui rend la clé d'arbre découpable."""
    text = "" if value is None else str(value).strip()
    if "/" in text:
        context, _, application = text.partition("/")
    else:
        context, application = text[:4], text[4:]
    context, application = context.strip().upper(), application.strip()
    if len(context) != 4 or not application:
        raise ValueError("Identité STRUST illisible : %r (attendu CONTEXTE/APPLICATION, par "
                         "exemple SSLS/DFAULT, ou la clé d'arbre SSLSDFAULT)." % value)
    return context, application


def normalize_strust_identities(rows: Optional[Sequence[Mapping[str, Any]]]) -> list[dict[str, str]]:
    """Les identités de ``SSFR_GET_ALL_STRUST_IDENTITIES`` en
    ``{identity, context, application, tree_key, description}``, dans l'ordre
    du module (celui de l'arbre de STRUST)."""
    found = []
    for row in rows or []:
        context = str(row.get("PSE_CONTEXT", "")).strip()
        application = str(row.get("PSE_APPLIC", "")).strip()
        found.append({"identity": "%s/%s" % (context, application), "context": context,
                      "application": application, "tree_key": context + application,
                      "description": str(row.get("PSE_DESCRIPT", "")).strip()})
    return found


def describe_certificate(identity: str, der: Any, parsed: Mapping[str, Any]) -> dict[str, Any]:
    """La fiche JSON-safe du certificat propre d'une identité, à partir du DER
    (``SSFR_GET_OWNCERTIFICATE``) et de son analyse (``SSFR_PARSE_CERTIFICATE``).
    Une date illisible lève ; une date absente sur un DER présent lève aussi
    (le module n'a pas su lire ce qu'il a rendu)."""
    data = _as_bytes(der)
    valid_from_raw = str(parsed.get("EV_VALIDFROM", "") or "").strip()
    valid_to_raw = str(parsed.get("EV_VALIDTO", "") or "").strip()
    start = parse_certificate_time(valid_from_raw)
    end = parse_certificate_time(valid_to_raw)
    if end is None or start is None:
        raise StrustIdentityNotFoundError(
            "Le certificat de l'identité STRUST %s a été lu (%d octets) mais son analyse ne rend "
            "pas de dates (EV_VALIDFROM=%r, EV_VALIDTO=%r) : aucune échéance n'est jugeable."
            % (identity, len(data), valid_from_raw, valid_to_raw))
    subject = str(parsed.get("EV_SUBJECT", "") or "").strip()
    issuer = str(parsed.get("EV_ISSUER", "") or "").strip()
    return {"identity": identity, "subject": subject, "issuer": issuer,
            "self_signed": bool(subject) and subject == issuer,
            "serial": str(parsed.get("EV_SERIALNO", "") or "").strip(),
            "valid_from": start.isoformat(), "valid_to": end.isoformat(),
            "valid_from_raw": valid_from_raw, "valid_to_raw": valid_to_raw,
            "algorithm": str(parsed.get("EV_ALGID", "") or "").strip(),
            "der_sha256": certificate_fingerprint(data),
            # l'empreinte que STRUST AFFICHE (« Checksum (SHA1) ») : un repère, pas une sécurité
            "der_sha1": hashlib.sha1(data, usedforsecurity=False).hexdigest() if data else "",
            "der_length": len(data)}


# --------------------------------------------------------------------- #
# Services de l'ICM
# --------------------------------------------------------------------- #
#: Codes de protocole de ``ICM_SINFO-PROTOCOL``, relevés le 2026-10-08 en
#: confrontant ``ICM_GET_INFO`` à la liste des services de SMICM (758). Un code
#: hors carte rend ``unmapped``, jamais un protocole deviné.
ICM_PROTOCOLS = {1: "HTTP", 2: "HTTPS", 4: "SMTP"}


def normalize_icm_services(info: Mapping[str, Any]) -> dict[str, Any]:
    """La réponse de ``ICM_GET_INFO`` en ``{status_code, services}``, chaque
    service ``{protocol, protocol_code, port, host, active, keep_alive,
    processing_timeout, external_bind}`` (``port`` en texte, tel que l'ICM le
    déclare : ``0`` pour un service sans port ; ``active`` booléen lu sur le
    drapeau ``ACTIVE``). ``THRLIST`` (octets bruts) n'est pas rendu."""
    services = []
    for row in info.get("SERVLIST") or []:
        try:
            code = int(row.get("PROTOCOL"))
        except (TypeError, ValueError):
            code = -1
        services.append({
            "protocol": ICM_PROTOCOLS.get(code, "unmapped"), "protocol_code": code,
            "port": str(row.get("SERVICE", "")).strip(),
            "host": str(row.get("HOSTNAME", "")).strip(),
            "active": str(row.get("ACTIVE", "")).strip().upper() == "X",
            "keep_alive": row.get("KEEPALIVE"), "processing_timeout": row.get("PROC_TIMEOUT"),
            "external_bind": str(row.get("EXTBIND", "")).strip()})
    data = info.get("INFO_DATA") or {}
    return {"status_code": data.get("STATUS"), "services": services}


def icm_service_verdict(services: Sequence[Mapping[str, Any]], protocol: Any,
                        port: Any = None) -> dict[str, Any]:
    """Cherche le service ``protocol`` (``HTTPS``...) sur ``port`` (tout port
    si absent) et rend ``{"verdict", "matches", "protocol", "port"}`` :
    ``active`` (au moins un service correspondant actif), ``inactive`` (il
    existe, aucun n'est actif) ou ``absent``. Distinguer les deux échecs est
    tout l'intérêt : un service déclaré mais arrêté ne se répare pas comme un
    service jamais déclaré."""
    wanted = str(protocol or "").strip().upper()
    if not wanted:
        raise ValueError("Le protocole du service ICM est vide (HTTP, HTTPS, SMTP...).")
    wanted_port = None if port in (None, "", "None") else str(port).strip()
    matches = [dict(s) for s in services
               if str(s.get("protocol", "")).upper() == wanted
               and (wanted_port is None or str(s.get("port", "")) == wanted_port)]
    if any(s.get("active") for s in matches):
        verdict = "active"
    elif matches:
        verdict = "inactive"
    else:
        verdict = "absent"
    return {"verdict": verdict, "matches": matches, "protocol": wanted, "port": wanted_port}


def describe_icm_service_failure(verdict: Mapping[str, Any],
                                 services: Sequence[Mapping[str, Any]]) -> str:
    """Le message d'échec d'une garde de service ICM : la cause (``inactif``
    ou ``absent``) et TOUS les services déclarés avec leur état."""
    target = "%s%s" % (verdict.get("protocol"),
                       " sur le port %s" % verdict["port"] if verdict.get("port") else "")
    listing = ", ".join("%s %s (%s)" % (s.get("protocol"), s.get("port"),
                                        "actif" if s.get("active") else "inactif")
                        for s in services) or "aucun"
    cause = ("déclaré mais INACTIF" if verdict.get("verdict") == "inactive"
             else "ABSENT de la configuration de l'ICM")
    return "Service ICM %s %s. Services déclarés : %s." % (target, cause, listing)
