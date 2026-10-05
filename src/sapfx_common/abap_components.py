"""Composants logiciels d'un système ABAP lus par HTTP (API des outils ABAP).

Logique pure du keyword `Get Abap Software Components` (SapApiLibrary). Il
existe parce que les deux conteneurs ABAP du banc annoncent le même
identifiant système et le même nom d'hôte, et que, sans SAP GUI ni RFC, le
seul discriminant HTTP connu jusqu'ici était le VOLUME du catalogue Gateway
(`/sap/public/info` étant inactif sur les deux). Relevé le 2026-09-24 : la
ressource ``/sap/bc/adt/system/components`` de l'API des outils ABAP rend la
liste des composants installés en flux Atom, ``SAP_BASIS`` compris, donc la
RELEASE du système se prouve par HTTP seul (758 sur ABAP Platform 2023).

Chaque entrée porte l'identifiant du composant dans ``atom:id`` et un titre
à quatre champs séparés par ``;`` : release, paquet de support, niveau de
support, description (``758;SAPK-75802INSAPBASIS;0002;SAP Basis Component``).
"""
from __future__ import annotations

from typing import Any
from xml.etree import ElementTree

COMPONENTS_PATH = "/sap/bc/adt/system/components"
ATOM_FEED = "application/atom+xml;type=feed"
_FIELDS = ("release", "sp_package", "sp_level", "description")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_adt_components(xml_text: Any) -> dict[str, dict[str, str]]:
    """Flux Atom des composants -> ``{composant: {release, sp_package,
    sp_level, description}}``.

    Refuse un corps qui n'est pas ce flux (page de connexion HTML, erreur) en
    le disant, au lieu de rendre un dictionnaire vide : « aucun composant » et
    « pas lu » ne se confondent pas."""
    text = xml_text.decode("utf-8", "replace") if isinstance(xml_text, bytes) else str(xml_text)
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as err:
        raise ValueError(
            "La réponse de %s n'est pas un flux Atom lisible (%s) : page de "
            "connexion, service ADT inactif, ou autorisation manquante ?"
            % (COMPONENTS_PATH, err))
    if _local(root.tag) != "feed":
        raise ValueError("La réponse de %s n'est pas un flux Atom (élément racine %s)."
                         % (COMPONENTS_PATH, _local(root.tag)))
    components: dict[str, dict[str, str]] = {}
    for entry in root:
        if _local(entry.tag) != "entry":
            continue
        values = {_local(child.tag): (child.text or "").strip() for child in entry}
        name = values.get("id", "")
        if not name:
            continue
        parts = values.get("title", "").split(";", len(_FIELDS) - 1)
        parts += [""] * (len(_FIELDS) - len(parts))
        components[name] = dict(zip(_FIELDS, parts, strict=True))
    if not components:
        raise ValueError("Le flux de %s ne porte aucun composant : lecture non probante."
                         % COMPONENTS_PATH)
    return components


def abap_release(components: dict[str, dict[str, str]]) -> str:
    """La release ABAP du système : celle du composant ``SAP_BASIS``."""
    basis = components.get("SAP_BASIS")
    if not basis or not basis.get("release"):
        raise ValueError("Aucun composant SAP_BASIS dans l'inventaire : release "
                         "illisible (composants lus : %s)." % ", ".join(sorted(components)))
    return basis["release"]
