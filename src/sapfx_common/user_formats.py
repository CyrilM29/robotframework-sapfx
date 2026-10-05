"""Formats de l'utilisateur SAP (date, notation décimale, heure) : logique pure.

Un dynpro n'accepte une date que dans le FORMAT de l'utilisateur connecté
(``SU3`` / ``SU01``, onglet Defaults : clé ``DATFM``), et lit un nombre selon
sa NOTATION DÉCIMALE (clé ``DCPFM``). Relevé live sur A4H le 2026-09-07 :
l'utilisateur DEVELOPER du trial est en ``DD.MM.YYYY`` et en notation
``1.234.567,89``, si bien qu'une saisie ISO ``2026-09-01`` est refusée par un
message de type ``E`` (``00``/``065``) et qu'un ``1000.50`` serait lu comme
mille cinquante mille... Ce module convertit dans les deux sens à partir des
CLÉS techniques (jamais des libellés localisés de la combo, qui, eux, changent
avec la langue de session), pour les keywords `Input Date`, `Input Number` et
`Get User Formats`.

Les clés et leurs formes sont celles de la table ``USR01``, stables depuis
des décennies : ``DATFM`` 1 à 6 (les formes grégoriennes), ``DCPFM`` vide /
``X`` / ``Y``. Les calendriers japonais, islamique et iranien (``DATFM`` 7 à
C) sont refusés explicitement : convertir une date grégorienne vers ces
calendriers n'est pas une mise en forme, et le refus est plus honnête qu'une
date fausse. Module pur, typé, testé hors SAP.
"""
from __future__ import annotations

import datetime as _dt
import re
from decimal import Decimal, InvalidOperation
from typing import Mapping

# DATFM (USR01-DATFM) -> patron strftime, séparateur, ordre.
DATE_FORMATS: Mapping[str, str] = {
    "1": "%d.%m.%Y",
    "2": "%m/%d/%Y",
    "3": "%m-%d-%Y",
    "4": "%Y.%m.%d",
    "5": "%Y/%m/%d",
    "6": "%Y-%m-%d",
}

# Libellé technique (locale-safe) de chaque clé, pour les messages.
DATE_FORMAT_LABELS: Mapping[str, str] = {
    "1": "DD.MM.YYYY", "2": "MM/DD/YYYY", "3": "MM-DD-YYYY",
    "4": "YYYY.MM.DD", "5": "YYYY/MM/DD", "6": "YYYY-MM-DD",
}

# DCPFM (USR01-DCPFM) -> (séparateur de milliers, séparateur décimal).
DECIMAL_FORMATS: Mapping[str, tuple[str, str]] = {
    "": (".", ","),
    "X": (",", "."),
    "Y": (" ", ","),
}

DECIMAL_FORMAT_LABELS: Mapping[str, str] = {
    "": "1.234.567,89", "X": "1,234,567.89", "Y": "1 234 567,89",
}

_ISO_DATE = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})\s*$")


def normalize_date_key(key: object) -> str:
    """Clé ``DATFM`` telle que SAP la rend (chaîne, blancs retirés)."""
    return str(key if key is not None else "").strip()


def normalize_decimal_key(key: object) -> str:
    """Clé ``DCPFM`` : la clé de la notation ``1.234.567,89`` est VIDE, et une
    combo la rend parfois comme ``" "`` (un blanc) : les deux sont la même."""
    return str(key if key is not None else "").strip().upper()


def format_date(iso_date: str, date_format_key: object) -> str:
    """``2026-09-01`` -> la forme attendue par l'utilisateur (``01.09.2026``
    pour la clé ``1``). ``iso_date`` accepte aussi un ``datetime.date``.
    Refuse en nommant la clé pour un calendrier non grégorien ou inconnu, et
    en nommant la date pour une date invalide : jamais une date fausse."""
    key = normalize_date_key(date_format_key)
    pattern = DATE_FORMATS.get(key)
    if pattern is None:
        raise ValueError(
            "Format de date DATFM %r non pris en charge (clés grégoriennes : %s) : "
            "un calendrier japonais, islamique ou iranien ne se dérive pas d'une "
            "date ISO, saisir la valeur telle que l'utilisateur la voit."
            % (key, ", ".join("%s=%s" % kv for kv in DATE_FORMAT_LABELS.items())))
    if isinstance(iso_date, _dt.date):
        value = iso_date
    else:
        match = _ISO_DATE.match(str(iso_date))
        if match is None:
            raise ValueError(
                "Date %r attendue en ISO 8601 (AAAA-MM-JJ) pour la conversion vers "
                "le format de l'utilisateur." % (iso_date,))
        try:
            value = _dt.date(int(match.group(1)), int(match.group(2)),
                             int(match.group(3)))
        except ValueError as exc:
            raise ValueError("Date %r invalide : %s" % (iso_date, exc))
    return value.strftime(pattern)


def parse_date(text: str, date_format_key: object) -> str:
    """La forme utilisateur (``01.09.2026`` en clé ``1``) -> ISO ``2026-09-01``.
    Une chaîne vide rend une chaîne vide (champ non renseigné)."""
    key = normalize_date_key(date_format_key)
    pattern = DATE_FORMATS.get(key)
    if pattern is None:
        raise ValueError("Format de date DATFM %r non pris en charge." % (key,))
    raw = str(text or "").strip()
    if not raw:
        return ""
    try:
        return _dt.datetime.strptime(raw, pattern).date().isoformat()
    except ValueError:
        raise ValueError(
            "Date %r ne suit pas le format de l'utilisateur %s (DATFM %s)."
            % (raw, DATE_FORMAT_LABELS[key], key))


def format_number(value: object, decimal_format_key: object,
                  decimals: int | None = None,
                  thousands: bool = False) -> str:
    """``1234.5`` -> ``1234,5`` (clé vide), ``1234.5`` (clé ``X``)... La valeur
    est un nombre Python OU une chaîne en notation TECHNIQUE (point décimal,
    sans séparateur de milliers). ``decimals`` fixe le nombre de décimales ;
    ``thousands=True`` insère le séparateur de milliers de l'utilisateur (un
    champ de saisie SAP l'accepte, mais ne l'exige jamais : défaut à False)."""
    key = normalize_decimal_key(decimal_format_key)
    if key not in DECIMAL_FORMATS:
        raise ValueError(
            "Notation décimale DCPFM %r inconnue (attendu : vide, X ou Y)." % (key,))
    thousands_sep, decimal_sep = DECIMAL_FORMATS[key]
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError(
            "Nombre %r attendu en notation technique (point décimal, sans "
            "séparateur de milliers)." % (value,))
    if decimals is not None:
        number = number.quantize(Decimal(1).scaleb(-int(decimals)))
    sign = number.as_tuple().sign
    text = format(abs(number), "f")
    integer_part, _, fraction = text.partition(".")
    if thousands:
        groups: list[str] = []
        while len(integer_part) > 3:
            groups.insert(0, integer_part[-3:])
            integer_part = integer_part[:-3]
        groups.insert(0, integer_part)
        integer_part = thousands_sep.join(groups)
    result = integer_part
    if fraction:
        result += decimal_sep + fraction
    return ("-" if sign else "") + result


def parse_number(text: str, decimal_format_key: object) -> str:
    """La forme utilisateur (``1.234,50`` en clé vide) -> notation technique
    ``1234.50`` (chaîne, pour ne perdre aucune décimale). Vide -> vide.
    Un signe négatif SAP en suffixe (``100-``) est reconnu."""
    key = normalize_decimal_key(decimal_format_key)
    if key not in DECIMAL_FORMATS:
        raise ValueError(
            "Notation décimale DCPFM %r inconnue (attendu : vide, X ou Y)." % (key,))
    thousands_sep, decimal_sep = DECIMAL_FORMATS[key]
    raw = str(text or "").strip()
    if not raw:
        return ""
    negative = raw.endswith("-") or raw.startswith("-")
    raw = raw.strip("-").strip()
    raw = raw.replace(thousands_sep, "")
    raw = raw.replace(decimal_sep, ".")
    try:
        number = Decimal(raw)
    except InvalidOperation:
        raise ValueError(
            "Nombre %r ne suit pas la notation décimale de l'utilisateur %s "
            "(DCPFM %r)." % (text, DECIMAL_FORMAT_LABELS[key], key))
    return ("-" if negative else "") + format(number, "f")


def describe_formats(date_format_key: object, decimal_format_key: object,
                     time_format_key: object = "") -> dict:
    """Le dict JSON-safe que rend `Get User Formats` : les CLÉS techniques
    et leur forme, jamais un libellé localisé."""
    date_key = normalize_date_key(date_format_key)
    decimal_key = normalize_decimal_key(decimal_format_key)
    return {
        "date_format": date_key,
        "date_pattern": DATE_FORMAT_LABELS.get(date_key, ""),
        "decimal_notation": decimal_key,
        "decimal_example": DECIMAL_FORMAT_LABELS.get(decimal_key, ""),
        "time_format": str(time_format_key if time_format_key is not None else "").strip(),
        "gregorian": date_key in DATE_FORMATS,
    }
