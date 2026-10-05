"""Création d'un IDoc SORTANT, logique pure (aucun appel réseau).

Ce que `Create Outbound Idoc` assemble avant de parler au système : le
découpage d'un segment lu dans le dictionnaire, la donnée ``SDATA`` bâtie
champ par champ, l'arbre de segments aplati avec ses numéros (``SEGNUM``,
``PSGNUM``, ``HLEVEL``) et validé contre la syntaxe du type, et
l'enregistrement de contrôle. Les entrées/sorties (modules ``EDI_*``) vivent
dans ``SapApiLibrary._rfc_idoc``.

Trois faits mesurés le 2026-10-01 (A4H 1909) y sont encodés :

* le découpage d'un segment se DÉRIVE du dictionnaire (``DDIF_FIELDINFO_GET``
  sur le type de segment), jamais d'une copie de mémoire : un décalage d'un
  caractère écrit la valeur dans le champ voisin sans la moindre erreur. Les
  offsets sont comptés en CARACTÈRES par cumul des longueurs, car l'``OFFSET``
  du dictionnaire est en octets UTF-16 (306 pour 153 caractères) ;
* les segments se rattachent à l'identifiant PROVISOIRE de l'ouverture, mais
  le numéro de l'IDoc est celui que rend la clôture (``IDOC_CONTROL-DOCNUM``) ;
* ``REFINT`` et ``ARCKEY`` sont refusés à l'ouverture (``E0/051``) : le
  marqueur d'une exécution va dans la DONNÉE d'un segment, pas dans le
  contrôle.

Typed.
"""
from __future__ import annotations

import ast
import json
from typing import Any, Mapping, Optional, Sequence

#: Longueur maximale de ``EDIDD-SDATA`` (la donnée d'un segment).
SDATA_LENGTH = 1000

#: Types internes acceptés dans un segment : un segment d'IDoc est une chaîne
#: de caractères, les autres types (entier, packé) ne s'y découpent pas.
CHARACTER_TYPES = ("C", "N", "D", "T")

#: Clés admises dans la description d'un segment.
SEGMENT_KEYS = ("segment", "fields", "data", "children")

#: Occurrences maximales que le dictionnaire annonce pour « sans limite ».
UNBOUNDED_OCCURRENCES = 999999999


def normalize_docnum(value: Any) -> str:
    """Numéro d'IDoc sur 16 chiffres (la forme de ``EDIDC-DOCNUM``).

    Un numéro non numérique ou plus long que le champ est refusé en le
    nommant : ``Get Idoc Status`` filtre sur une égalité de chaînes, donc
    ``7`` ne retrouverait jamais ``0000000000000007``."""
    text = str(value).strip()
    if not text.isdigit() or len(text) > 16:
        raise ValueError(
            "Le numéro d'IDoc doit être numérique, 16 chiffres au plus "
            "(reçu %r)." % (value,))
    return text.zfill(16)


def parse_segments(value: Any) -> list[dict[str, Any]]:
    """Les segments à créer, en liste de dictionnaires.

    Via ``execute_step`` (rf-mcp) tout argument arrive en chaîne : une liste
    sérialisée en JSON (ou en littéral Python) est donc acceptée comme la
    liste elle-même. Chaque segment : ``{"segment": nom, "fields": {...}}``
    (ou ``"data"`` brut) et ``"children"`` pour les enfants. Une clé inconnue
    est refusée en la nommant (une faute de frappe sur ``children`` ferait
    sinon disparaître tout un sous-arbre sans erreur)."""
    items = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("L'argument segments est vide.")
        try:
            items = json.loads(text)
        except ValueError:
            try:
                items = ast.literal_eval(text)
            except (ValueError, SyntaxError) as err:
                raise ValueError(
                    "L'argument segments n'est ni une liste ni un JSON "
                    "lisible : %s." % err) from None
    if isinstance(items, Mapping):
        items = [items]
    if not isinstance(items, (list, tuple)) or not items:
        raise ValueError(
            "L'argument segments doit être une liste non vide de segments "
            "{'segment': nom, 'fields': {...}, 'children': [...]}.")
    return [_check_segment(item, "segments[%d]" % index)
            for index, item in enumerate(items)]


def _check_segment(item: Any, where: str) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise ValueError("%s doit être un dictionnaire, reçu %r." % (where, item))
    unknown = sorted(set(item) - set(SEGMENT_KEYS))
    if unknown:
        raise ValueError(
            "%s : clé(s) inconnue(s) %s (admises : %s)."
            % (where, ", ".join(unknown), ", ".join(SEGMENT_KEYS)))
    name = str(item.get("segment", "")).strip().upper()
    if not name:
        raise ValueError("%s : la clé 'segment' (nom du segment) est absente." % where)
    if "fields" in item and "data" in item:
        raise ValueError("%s (%s) : 'fields' et 'data' s'excluent." % (where, name))
    children = item.get("children") or []
    if not isinstance(children, (list, tuple)):
        raise ValueError("%s (%s) : 'children' doit être une liste." % (where, name))
    checked: dict[str, Any] = {"segment": name}
    if "data" in item:
        checked["data"] = "" if item["data"] is None else str(item["data"])
    else:
        fields = item.get("fields") or {}
        if not isinstance(fields, Mapping):
            raise ValueError("%s (%s) : 'fields' doit être un dictionnaire." % (where, name))
        checked["fields"] = dict(fields)
    checked["children"] = [
        _check_segment(child, "%s.children[%d]" % (where, index))
        for index, child in enumerate(children)]
    return checked


def collect_segment_names(segments: Sequence[Mapping[str, Any]]) -> list[str]:
    """Les types de segment qui demandent un découpage (ceux décrits par
    ``fields``), sans doublon, dans l'ordre de première apparition."""
    names: list[str] = []

    def visit(items: Sequence[Mapping[str, Any]]) -> None:
        for item in items:
            if "fields" in item and item["segment"] not in names:
                names.append(item["segment"])
            visit(item.get("children", []))

    visit(segments)
    return names


def segment_layout(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Découpage d'un segment depuis les lignes DFIES du dictionnaire :
    ``[{"name", "offset", "length", "type"}]``, offsets en caractères (cumul
    des longueurs). Un champ non caractère est refusé en le nommant."""
    layout: list[dict[str, Any]] = []
    offset = 0
    for row in rows:
        name = str(row.get("FIELDNAME", "")).strip()
        if not name:
            continue
        length = int(str(row.get("LENG") or "0").strip() or 0)
        inttype = (str(row.get("INTTYPE", "C")).strip() or "C")
        if inttype not in CHARACTER_TYPES:
            raise ValueError(
                "Le champ %s a le type interne %r : seul un champ caractère "
                "(C, N, D, T) se découpe dans la donnée d'un segment."
                % (name, inttype))
        if length <= 0:
            continue
        layout.append({"name": name, "offset": offset, "length": length,
                       "type": str(row.get("DATATYPE", "")).strip() or "CHAR"})
        offset += length
    if offset > SDATA_LENGTH:
        raise ValueError(
            "Le segment fait %d caractères, au-delà de SDATA (%d)."
            % (offset, SDATA_LENGTH))
    return layout


def layout_length(layout: Sequence[Mapping[str, Any]]) -> int:
    """Longueur totale d'un segment découpé."""
    return sum(int(field["length"]) for field in layout)


def build_sdata(segment: str, layout: Sequence[Mapping[str, Any]],
                fields: Mapping[str, Any]) -> str:
    """La donnée ``SDATA`` d'un segment depuis ses champs, aux positions du
    dictionnaire, complétée de blancs sur la longueur du segment.

    Un champ inconnu ou une valeur trop longue échoue en nommant segment,
    champ et longueur : tronquer en silence écrirait une donnée fausse que
    seul l'effet métier trahirait. Un champ ``NUMC`` numérique est complété de
    zéros à gauche (sa forme interne)."""
    known = {str(field["name"]): field for field in layout}
    buffer = [" "] * layout_length(layout)
    for key, value in fields.items():
        name = str(key).strip().upper()
        field = known.get(name)
        if field is None:
            raise ValueError(
                "Le segment %s n'a pas de champ %s (champs : %s)."
                % (segment, name, ", ".join(sorted(known)) or "aucun"))
        text = "" if value is None else str(value)
        length = int(field["length"])
        if str(field["type"]).upper() == "NUMC" and text.isdigit():
            text = text.zfill(length)
        if len(text) > length:
            raise ValueError(
                "Le champ %s-%s fait %d caractères au plus, la valeur en a %d."
                % (segment, name, length, len(text)))
        offset = int(field["offset"])
        buffer[offset:offset + length] = list(text.ljust(length))
    return "".join(buffer)


def decode_sdata(layout: Sequence[Mapping[str, Any]], data: Any) -> dict[str, str]:
    """La donnée d'un segment relue champ par champ (blancs de fin retirés) :
    l'inverse de `build_sdata`, sur le même découpage."""
    text = str(data)
    return {str(field["name"]):
            text[int(field["offset"]):int(field["offset"]) + int(field["length"])].rstrip()
            for field in layout}


def syntax_tree(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """La syntaxe d'un type d'IDoc (``EDI_IDOC_SYNTAX_GET``) en
    ``[{"segment", "parent", "min", "max", "mandatory", "level"}]``."""
    tree: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("SEGTYP", "")).strip()
        if not name:
            continue
        tree.append({
            "segment": name,
            "parent": str(row.get("PARSEG", "")).strip(),
            "min": _as_int(row.get("OCCMIN")),
            "max": _as_int(row.get("OCCMAX")),
            "mandatory": str(row.get("MUSTFL", "")).strip() == "X",
            "level": _as_int(row.get("HLEVEL"))})
    return tree


def _as_int(value: Any) -> int:
    text = str(value if value is not None else "").strip()
    return int(text) if text.isdigit() else 0


def flatten_segments(segments: Sequence[Mapping[str, Any]],
                     layouts: Mapping[str, Sequence[Mapping[str, Any]]],
                     syntax: Optional[Sequence[Mapping[str, Any]]] = None
                     ) -> list[dict[str, str]]:
    """L'arbre de segments aplati dans l'ordre d'écriture, prêt pour
    ``EDI_SEGMENT_ADD_NEXT`` : ``SEGNAM``, ``SEGNUM`` séquentiel sur six
    chiffres, ``PSGNUM`` (numéro du parent, ``000000`` à la racine), ``HLEVEL``
    (le niveau que le TYPE déclare quand ``syntax`` est fourni, la profondeur
    sinon : ``TXTRAW01`` met sa racine au niveau 2) et ``SDATA``.

    Avec ``syntax`` (``syntax_tree``), chaque segment est confronté au type :
    appartenance, parent attendu, nombre d'occurrences et segments
    obligatoires. Le refus tombe AVANT toute écriture, avec le nom du segment :
    le contrôle de syntaxe de la clôture n'arrive qu'une fois l'IDoc créé."""
    by_name = {entry["segment"]: entry for entry in syntax or []}
    rows: list[dict[str, str]] = []
    counter = [0]

    def emit(items: Sequence[Mapping[str, Any]], parent_name: str,
             parent_num: int, depth: int) -> None:
        seen: dict[str, int] = {}
        for item in items:
            name = str(item["segment"])
            if syntax is not None:
                _check_placement(name, parent_name, by_name)
                seen[name] = seen.get(name, 0) + 1
                limit = by_name[name]["max"] or UNBOUNDED_OCCURRENCES
                if seen[name] > limit:
                    raise ValueError(
                        "Le segment %s apparaît %d fois sous %s, le type en "
                        "admet %d au plus." % (name, seen[name],
                                               parent_name or "la racine", limit))
            counter[0] += 1
            number = counter[0]
            if "data" in item:
                data = str(item["data"])
                if len(data) > SDATA_LENGTH:
                    raise ValueError(
                        "La donnée brute du segment %s fait %d caractères, "
                        "au-delà de %d." % (name, len(data), SDATA_LENGTH))
            else:
                layout = layouts.get(name)
                if layout is None:
                    raise ValueError(
                        "Aucun découpage lu pour le segment %s." % name)
                data = build_sdata(name, layout, item.get("fields", {}))
            # le niveau vient de la SYNTAXE du type quand on l'a : `TXTRAW01`
            # déclare sa racine au niveau 2, et un niveau calculé d'après la
            # profondeur (1) faisait échouer le contrôle de syntaxe
            level = by_name[name]["level"] if syntax is not None and by_name[name]["level"] else depth
            rows.append({"SEGNAM": name, "SEGNUM": "%06d" % number,
                         "PSGNUM": "%06d" % parent_num,
                         "HLEVEL": "%02d" % level, "SDATA": data})
            children = item.get("children", [])
            if syntax is not None:
                _check_mandatory(name, children, syntax)
            emit(children, name, number, depth + 1)

    if syntax is not None:
        _check_mandatory("", segments, syntax)
    emit(segments, "", 0, 1)
    return rows


def _check_placement(name: str, parent_name: str,
                     by_name: Mapping[str, Mapping[str, Any]]) -> None:
    entry = by_name.get(name)
    if entry is None:
        raise ValueError(
            "Le segment %s n'appartient pas au type d'IDoc (segments : %s)."
            % (name, ", ".join(sorted(by_name)) or "aucun"))
    if entry["parent"] != parent_name:
        raise ValueError(
            "Le segment %s doit être rattaché à %s, pas à %s."
            % (name, entry["parent"] or "la racine", parent_name or "la racine"))


def _check_mandatory(parent_name: str, children: Sequence[Mapping[str, Any]],
                     syntax: Sequence[Mapping[str, Any]]) -> None:
    present = {str(child["segment"]) for child in children}
    for entry in syntax:
        if (entry["parent"] == parent_name and entry["mandatory"]
                and entry["segment"] not in present):
            raise ValueError(
                "Le segment obligatoire %s manque sous %s."
                % (entry["segment"], parent_name or "la racine"))


def control_record(client: str, message_type: str, idoc_type: str,
                   receiver_port: str, receiver_partner: str,
                   sender_partner: str, sender_port: str,
                   receiver_partner_type: str = "LS",
                   sender_partner_type: str = "LS",
                   output_mode: str = "2") -> dict[str, str]:
    """L'enregistrement de contrôle d'un IDoc sortant (``DIRECT`` = 1).

    Ni ``REFINT`` ni ``ARCKEY`` : l'ouverture les refuse (``E0/051``). Elle
    refuse aussi un contrôle sans ``OUTMOD`` (le mode de sortie, repris du
    profil sortant : 2 = transfert immédiat). Longueurs vérifiées contre les
    champs d'``EDIDC`` avant l'appel."""
    record = {
        "MANDT": str(client).strip(), "DIRECT": "1",
        "MESTYP": str(message_type).strip(), "IDOCTP": str(idoc_type).strip(),
        "RCVPOR": str(receiver_port).strip(),
        "RCVPRT": str(receiver_partner_type).strip(),
        "RCVPRN": str(receiver_partner).strip(),
        "SNDPOR": str(sender_port).strip(),
        "SNDPRT": str(sender_partner_type).strip(),
        "SNDPRN": str(sender_partner).strip(),
        "OUTMOD": str(output_mode).strip()}
    limits = {"MESTYP": 30, "IDOCTP": 30, "RCVPOR": 10, "RCVPRT": 2,
              "RCVPRN": 10, "SNDPOR": 10, "SNDPRT": 2, "SNDPRN": 10, "OUTMOD": 1}
    argument = {"MESTYP": "message_type", "IDOCTP": "idoc_type",
                "RCVPOR": "receiver_port", "RCVPRT": "receiver_partner_type",
                "RCVPRN": "receiver_partner", "SNDPOR": "sender_port",
                "SNDPRT": "sender_partner_type", "SNDPRN": "sender_partner",
                "OUTMOD": "output_mode"}
    for field, limit in limits.items():
        if not record[field]:
            raise ValueError("L'argument %s est vide." % argument[field])
        if len(record[field]) > limit:
            raise ValueError(
                "L'argument %s (%r) dépasse les %d caractères de %s."
                % (argument[field], record[field], limit, field))
    return record


def default_sender_port(system_id: str) -> str:
    """Le port émetteur par défaut : ``SAP`` suivi de l'identifiant système
    (``SAPA4H``, la forme que les IDocs de l'image portent)."""
    return ("SAP" + str(system_id).strip())[:10]


def resolve_logical_system(rows: Sequence[Mapping[str, Any]], client: str) -> str:
    """Le système logique du mandant depuis ``T000`` (``LOGSYS``) ; un mandant
    sans système logique est refusé en le disant."""
    for row in rows:
        if str(row.get("MANDT", "")).strip() == str(client).strip():
            logsys = str(row.get("LOGSYS", "")).strip()
            if logsys:
                return logsys
    raise ValueError(
        "Le mandant %s n'a pas de système logique (T000-LOGSYS vide) : "
        "renseigner sender_partner ou l'attribuer (BD54)." % client)
