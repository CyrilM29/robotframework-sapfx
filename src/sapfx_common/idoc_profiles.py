"""Profils partenaire d'ALE/EDI (``EDP13`` sortant, ``EDP21`` entrant). Logique pure.

Un IDoc sortant n'est expédié que si un profil sortant existe pour
(partenaire, type de message), et son entrant n'est posté que si un profil
entrant existe pour (partenaire émetteur, type de message). Sans le second,
le sortant reste VERT à 03 pendant que l'entrant naît en 56 : le piège central
de la chaîne, mesuré sur A4H le 2026-10-01. La suite qui provisionne ces
profils doit donc le faire de façon idempotente et les défaire sans toucher à
ce que l'image livre.

Trois règles encodées ici, sur le patron de ``write_simulation`` :

* une LISTE BLANCHE de types de message est obligatoire, et une liste vide
  refuse tout au lieu d'autoriser tout ;
* les profils livrés avec l'image (``RSRQST``, ``RSINFO``, ``RSSEND``, ceux du
  système BW) ne se modifient ni ne se retirent JAMAIS, même listés ;
* un profil déjà présent mais DIFFÉRENT n'est pas écrasé : l'écart est refusé
  champ par champ (un « ensure » qui réécrit en silence est une écriture qu'on
  n'a pas demandée).

Typed.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from sapfx_common.robot_args import as_name_list

#: Types de message dont les profils sont livrés avec l'image trial (le
#: reliquat du système BW) : jamais modifiés ni retirés.
PROTECTED_MESSAGE_TYPES = ("RSRQST", "RSINFO", "RSSEND")

#: Modes de sortie d'un profil sortant (``EDP13-OUTMOD``) : 1 = collecter,
#: 2 = transférer immédiatement, 4 = collecter puis transférer.
OUTPUT_MODES = ("1", "2", "4")

#: Modes de traitement d'un profil entrant (``EDP21-INMOD``) : 1 = tout de
#: suite, 3 = par programme d'arrière-plan. ``2`` est obsolète et ``4`` refusé
#: par le module (mesuré, PARAMETER_ERROR E0/436).
PROCESSING_MODES = ("1", "3")

OUTBOUND_READ_FIELDS = ("RCVPRN", "RCVPRT", "RCVPFC", "MESTYP", "MESCOD",
                        "MESFCT", "TEST", "IDOCTYP", "RCVPOR", "OUTMOD",
                        "PCKSIZ")
INBOUND_READ_FIELDS = ("SNDPRN", "SNDPRT", "SNDPFC", "MESTYP", "MESCOD",
                       "MESFCT", "TEST", "EVCODE", "INMOD")


def require_in_list(message_type: Any, allowed: Any) -> str:
    """Le type de message en majuscules s'il est dans la liste blanche, sinon
    un refus qui nomme les deux. Une liste vide refuse tout au lieu
    d'autoriser tout."""
    names = [name.upper() for name in as_name_list(allowed, "allowed_message_types")]
    if not names:
        raise ValueError(
            "allowed_message_types est obligatoire et ne peut pas être vide : "
            "une liste vide refuse tout (liste blanche des types de message "
            "autorisés à l'écriture).")
    wanted = str(message_type).strip().upper()
    if not wanted:
        raise ValueError("Le type de message est vide.")
    if wanted not in names:
        raise ValueError(
            "Le type de message %s n'est pas dans la liste blanche %s."
            % (wanted, names))
    return wanted


def require_allowed(message_type: Any, allowed: Any) -> str:
    """Comme `require_in_list`, et un profil livré avec l'image (``RSRQST``,
    ``RSINFO``, ``RSSEND``) est refusé même listé."""
    wanted = str(message_type).strip().upper()
    if wanted in PROTECTED_MESSAGE_TYPES:
        raise ValueError(
            "Le type de message %s est un profil LIVRÉ avec l'image (%s) : il "
            "ne se modifie ni ne se retire, même listé." %
            (wanted, ", ".join(PROTECTED_MESSAGE_TYPES)))
    return require_in_list(message_type, allowed)


def validate_mode(value: Any, allowed: Sequence[str], argument: str) -> str:
    """Un mode parmi ``allowed``, sinon un refus qui liste les valeurs."""
    text = str(value).strip()
    if text not in allowed:
        raise ValueError(
            "L'argument %s vaut %r : valeurs admises %s." % (argument, value, ", ".join(allowed)))
    return text


def outbound_key(client: str, partner: str, partner_type: str,
                 message_type: str) -> dict[str, str]:
    """La clé d'un profil sortant (``EDK13``)."""
    return {"MANDT": str(client).strip(), "RCVPRN": str(partner).strip(),
            "RCVPRT": str(partner_type).strip(), "RCVPFC": "",
            "MESTYP": str(message_type).strip(), "MESCOD": "", "MESFCT": "",
            "TEST": ""}


def inbound_key(client: str, partner: str, partner_type: str,
                message_type: str) -> dict[str, str]:
    """La clé d'un profil entrant (``EDK21``)."""
    return {"MANDT": str(client).strip(), "SNDPRN": str(partner).strip(),
            "SNDPRT": str(partner_type).strip(), "SNDPFC": "",
            "MESTYP": str(message_type).strip(), "MESCOD": "", "MESFCT": "",
            "TEST": ""}


def package_size_value(value: Any) -> str:
    """La taille de paquet sur quatre chiffres (``NUMC``)."""
    text = str(value).strip()
    if not text.isdigit() or int(text) < 1:
        raise ValueError("package_size doit être un entier d'au moins 1, reçu %r." % (value,))
    return text.zfill(4)[-4:]


def outbound_record(key: Mapping[str, str], idoc_type: str, port: str,
                    output_mode: str, package_size: Any, user: str,
                    language: str) -> dict[str, str]:
    """L'enregistrement d'un profil sortant (``EDP13``) à insérer."""
    if not str(idoc_type).strip() or not str(port).strip():
        raise ValueError("idoc_type et port sont obligatoires pour un profil sortant.")
    record = dict(key)
    record.update({
        "IDOCTYP": str(idoc_type).strip().upper(), "RCVPOR": str(port).strip(),
        "OUTMOD": validate_mode(output_mode, OUTPUT_MODES, "output_mode"),
        "PCKSIZ": package_size_value(package_size), "SYNCHK": "X",
        "USRTYP": "US", "USRKEY": str(user).strip(),
        "USRLNG": str(language).strip()[:1]})
    return record


def inbound_record(key: Mapping[str, str], process_code: str, processing: str,
                   user: str, language: str) -> dict[str, str]:
    """L'enregistrement d'un profil entrant (``EDP21``) à insérer."""
    if not str(process_code).strip():
        raise ValueError("process_code est obligatoire pour un profil entrant.")
    record = dict(key)
    record.update({
        "EVCODE": str(process_code).strip().upper(),
        "INMOD": validate_mode(processing, PROCESSING_MODES, "processing"),
        "SYNCHK": "X", "USRTYP": "US", "USRKEY": str(user).strip(),
        "USRLNG": str(language).strip()[:1]})
    return record


def profile_differences(existing: Mapping[str, Any], wanted: Mapping[str, Any],
                        fields: Sequence[str]) -> list[str]:
    """Les écarts entre un profil lu et le profil voulu, champ par champ,
    sur les seuls champs FONCTIONNELS (jamais l'utilisateur de service, qui
    dépend de qui a créé la ligne). Les nombres se comparent comme nombres
    (``0001`` égale ``1``)."""
    diffs: list[str] = []
    for field in fields:
        have = _comparable(existing.get(field, ""))
        want = _comparable(wanted.get(field, ""))
        if have != want:
            diffs.append("%s : présent %r, voulu %r" % (field, have, want))
    return diffs


def _comparable(value: Any) -> str:
    text = str(value).strip()
    return str(int(text)) if text.isdigit() else text


def normalize_outbound(row: Mapping[str, Any]) -> dict[str, str]:
    """Un profil sortant lu, en clés parlantes."""
    return {"partner": _text(row, "RCVPRN"), "partner_type": _text(row, "RCVPRT"),
            "message_type": _text(row, "MESTYP"),
            "idoc_type": _text(row, "IDOCTYP"), "port": _text(row, "RCVPOR"),
            "output_mode": _text(row, "OUTMOD"),
            "package_size": _comparable(row.get("PCKSIZ", "")),
            "partner_function": _text(row, "RCVPFC"),
            "message_code": _text(row, "MESCOD"),
            "message_function": _text(row, "MESFCT"), "test": _text(row, "TEST")}


def normalize_inbound(row: Mapping[str, Any]) -> dict[str, str]:
    """Un profil entrant lu, en clés parlantes."""
    return {"partner": _text(row, "SNDPRN"), "partner_type": _text(row, "SNDPRT"),
            "message_type": _text(row, "MESTYP"),
            "process_code": _text(row, "EVCODE"), "processing": _text(row, "INMOD"),
            "partner_function": _text(row, "SNDPFC"),
            "message_code": _text(row, "MESCOD"),
            "message_function": _text(row, "MESFCT"), "test": _text(row, "TEST")}


def _text(row: Mapping[str, Any], name: str) -> str:
    return str(row.get(name, "")).strip()


def sort_profiles(profiles: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    """Les profils dans un ordre stable (partenaire, type, message), pour un
    instantané comparable d'un passage à l'autre."""
    return sorted((dict(profile) for profile in profiles),
                  key=lambda p: (p["partner"], p["partner_type"],
                                 p["message_type"], p["message_code"],
                                 p["message_function"], p["test"]))
