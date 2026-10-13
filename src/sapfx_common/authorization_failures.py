"""Journal des échecs d'autorisation d'un utilisateur (SU53), logique pure.

SU53, lu par un administrateur pour un AUTRE utilisateur (« Display for
Different User »), rend une grille ALV dont chaque ligne est un contrôle
d'autorisation échoué : l'objet (``OBJCT``), le code de retour (``RC``) et
jusqu'à dix couples champ/valeur. Relevé le 2026-10-12 sur ABAP Platform 2023
(758) : les couples ont pour identifiants de colonne ``FIEL1``/``VAL01`` à
``FIEL9``/``VAL09``, puis ``FIEL0``/``VAL10`` pour le dixième (l'irrégularité
est de SAP, elle est encodée ici une fois).

Trois propriétés du journal, mesurées, dictent ce module :

- **un message d'écran ne nomme pas l'objet en cause** : SE16 refuse une
  table par ``MO/E/419``, sans paramètre, que la cause soit ``S_TABU_DIS`` ou
  ``S_TABU_NAM`` ; c'est le journal qui la nomme ;
- **une ligne en échec n'est pas un blocage** : SE16 contrôle ``S_TABU_DIS``
  OU ``S_TABU_NAM``, et un accès RÉUSSI laisse lui aussi des lignes en échec
  (l'alternative non détenue) ; un contrôle réussi n'est jamais journalisé ;
- **le journal persiste et s'accumule** entre sessions et entre runs, son
  fuseau horaire n'est pas établi : on ne le compare pas à une horloge, on
  compare deux lectures (avant le geste, après le geste) par
  :func:`new_failures`, qui compte les occurrences.

``RC`` relevé : ``4`` = l'objet est détenu, pas pour ces valeurs ; ``12`` =
aucune autorisation de cet objet dans le profil. Les textes de la grille sont
localisés : ils sont rendus pour le lecteur, jamais comparés.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable, Mapping

_PAIRS = tuple(("FIEL%d" % (index % 10), "VAL%02d" % index) for index in range(1, 11))
_SCALAR_COLUMNS = ("DATE", "TIME", "INSTANCE", "TYPETEXT", "DISP_NAME", "FORUSER",
                   "RC", "OBJCT")

#: Colonnes techniques à lire dans la grille de SU53, dans l'ordre.
FAILURE_COLUMNS: tuple[str, ...] = _SCALAR_COLUMNS + tuple(
    column for pair in _PAIRS for column in pair)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _return_code(value: Any) -> int | None:
    text = _text(value)
    return int(text) if text.isdigit() else None


def title_names_user(title: Any, user: Any) -> bool:
    """Vrai si le titre de la fenêtre SU53 porte le nom ``user`` comme mot
    entier. Le titre est traduit (« Display Authorization Data for User
    X » en EN) mais le nom est une donnée : c'est la garde qui empêche
    d'attribuer à un utilisateur le journal d'un autre. La frontière du mot
    suit les caractères admis dans un nom d'utilisateur SAP (lettres,
    chiffres, ``_ . - @ & /``) : ``SAPFX_TAB`` ne matche pas dans
    ``SAPFX_TABDIS``, ni ``ABC`` dans ``ABC-1`` ; un deux-points ou un
    guillemet accolé au nom par une traduction reste une frontière."""
    name = _text(user).upper()
    if not name:
        return False
    pattern = r"(?<![A-Z0-9_.@&/-])%s(?![A-Z0-9_.@&/-])" % re.escape(name)
    return re.search(pattern, _text(title).upper()) is not None


def parse_failure_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Une ligne de la grille SU53 (clés = identifiants techniques de
    colonne) vers ``{date, time, instance, application, display_name,
    for_user, object, rc, fields}``. ``fields`` est la carte ordonnée
    ``{CHAMP: valeur}`` des couples non vides ; ``rc`` vaut ``None`` quand la
    cellule n'est pas un entier (jamais un zéro inventé)."""
    fields: dict[str, str] = {}
    for name_column, value_column in _PAIRS:
        name = _text(row.get(name_column)).upper()
        if name:
            fields[name] = _text(row.get(value_column))
    return {
        "date": _text(row.get("DATE")),
        "time": _text(row.get("TIME")),
        "instance": _text(row.get("INSTANCE")),
        "application": _text(row.get("TYPETEXT")),
        "display_name": _text(row.get("DISP_NAME")),
        "for_user": _text(row.get("FORUSER")),
        "object": _text(row.get("OBJCT")).upper(),
        "rc": _return_code(row.get("RC")),
        "fields": fields,
    }


def parse_failure_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Toutes les lignes lues, dans l'ordre de la grille (le plus récent en
    tête). Une ligne SANS OBJET est REFUSÉE, jamais filtrée : c'est la forme
    d'une ligne d'ALV non chargée (cellules vides), et l'écarter en silence
    rendrait un repère « avant » creux, donc une ligne d'un run précédent
    présentée comme nouvelle (revue du 2026-10-12). Aucune ligne de ce genre
    n'a été vue sur un journal réel (100 lignes lues, 0 vide)."""
    entries = [parse_failure_row(row) for row in rows]
    blank = [index for index, entry in enumerate(entries) if not entry["object"]]
    if blank:
        raise AssertionError(
            "The authorization check journal has %d line(s) without an object "
            "(rows %s of %d): the grid was not fully loaded, and a partial read "
            "would make an older failure look new. Read it again."
            % (len(blank), ", ".join(str(i) for i in blank[:10]), len(entries)))
    return entries


def failure_key(entry: Mapping[str, Any]) -> str:
    """Clé d'identité d'une entrée : instant, instance, objet, code et
    couples. Deux contrôles au même instant sur les mêmes valeurs sont
    distingués par leur NOMBRE, pas par leur clé (voir :func:`new_failures`)."""
    fields = entry.get("fields") or {}
    pairs = ",".join("%s=%s" % (name, value) for name, value in fields.items())
    return "|".join((_text(entry.get("date")), _text(entry.get("time")),
                     _text(entry.get("instance")), _text(entry.get("object")),
                     _text(entry.get("rc")), pairs))


def new_failures(before: Iterable[Mapping[str, Any]],
                 after: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Les entrées de ``after`` absentes de ``before``, en comptant les
    occurrences : une entrée présente deux fois après et une fois avant
    compte UNE fois comme nouvelle. L'ordre de ``after`` est conservé."""
    remaining = Counter(failure_key(entry) for entry in before)
    fresh = []
    for entry in after:
        key = failure_key(entry)
        if remaining[key] > 0:
            remaining[key] -= 1
        else:
            fresh.append(dict(entry))
    return fresh


def _normalized_fields(fields: Mapping[str, Any] | None) -> dict[str, str]:
    return {_text(name).upper(): _text(value) for name, value in (fields or {}).items()}


def matching_failures(entries: Iterable[Mapping[str, Any]], authorization_object: str,
                      rc: Any = None, fields: Mapping[str, Any] | None = None
                      ) -> list[dict[str, Any]]:
    """Les entrées de l'objet ``authorization_object`` dont chaque champ
    demandé porte exactement la valeur demandée (les autres champs sont
    libres) et, si ``rc`` est donné, de ce code de retour."""
    wanted_object = _text(authorization_object).upper()
    wanted_fields = _normalized_fields(fields)
    wanted_rc = None if rc is None or _text(rc) == "" else _return_code(rc)
    if rc is not None and _text(rc) != "" and wanted_rc is None:
        raise ValueError("rc must be an integer return code (4, 12...), got %r." % (rc,))
    matches = []
    for entry in entries:
        if _text(entry.get("object")).upper() != wanted_object:
            continue
        if wanted_rc is not None and entry.get("rc") != wanted_rc:
            continue
        actual = _normalized_fields(entry.get("fields"))
        if all(actual.get(name) == value for name, value in wanted_fields.items()):
            matches.append(dict(entry))
    return matches


def describe_failure(entry: Mapping[str, Any]) -> str:
    """Une ligne lisible : ``S_TABU_DIS RC=4 ACTVT=03 DICBERCLS=SS``."""
    fields = entry.get("fields") or {}
    pairs = " ".join("%s=%s" % (name, value) for name, value in fields.items())
    return ("%s RC=%s %s" % (entry.get("object", ""), entry.get("rc"), pairs)).strip()


def format_failure_absence(entries: list[Mapping[str, Any]], authorization_object: str,
                           rc: Any = None, fields: Mapping[str, Any] | None = None,
                           sample: int = 10) -> str:
    """Le message d'échec quand aucune entrée ne correspond : l'attendu,
    puis ce que le journal porte (échantillon borné, nombre total dit)."""
    wanted_rc = "any" if rc is None or _text(rc) == "" else _text(rc)
    expected = describe_failure({"object": _text(authorization_object).upper(),
                                 "rc": wanted_rc, "fields": _normalized_fields(fields)})
    if not entries:
        return ("No authorization check failure matches '%s': the journal read is "
                "EMPTY (no failure recorded, or none since the reference read)." % expected)
    lines = [describe_failure(entry) for entry in entries[:sample]]
    more = "" if len(entries) <= sample else " (%d more not shown)" % (len(entries) - sample)
    return ("No authorization check failure matches '%s'. The %d entries read%s:\n  %s"
            % (expected, len(entries), more, "\n  ".join(lines)))
