"""Onglets d'un ``GuiTabStrip``, logique pure.

Un tabstrip SAP GUI porte des ``GuiTab`` dont l'id se termine par
``tabp<CLÉ>`` (``tabpLOGO``, ``tabpDEFA``...) : la CLÉ est technique et stable,
le ``Text`` est localisé. ``GuiTabStrip.SelectedTab`` rend l'onglet actif sous
la forme d'un objet COM dont l'``Id`` est ABSOLU
(``/app/con[0]/ses[0]/wnd[0]/usr/tabsTABSTRIP1/tabpADDR``) là où la perception
travaille en ids RELATIFS (``wnd[0]/...``). Mesuré le 2026-09-08 sur ABAP 2023
(SU01 : douze onglets, contre onze sur la 754, ``tabpUSAT`` étant nouveau : un
page object qui grave la liste des onglets d'une release est faux sur
l'autre). Typé, testé hors SAP.
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

TAB_PREFIX = "tabp"


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def relative_id(element_id: Any) -> str:
    """Un id absolu (``/app/con[0]/ses[0]/wnd[0]/...``) ramené à la forme
    relative de la perception (``wnd[0]/...``) ; un id déjà relatif est rendu
    tel quel."""
    text = _text(element_id)
    index = text.find("wnd[")
    return text[index:] if index >= 0 else text


def tab_key(tab_id: Any) -> str:
    """La clé technique d'un onglet : le suffixe de son dernier segment après
    ``tabp`` (``.../tabpLOGO`` -> ``LOGO``) ; vide si la forme n'est pas celle-là."""
    last = relative_id(tab_id).rsplit("/", 1)[-1]
    return last[len(TAB_PREFIX):] if last.startswith(TAB_PREFIX) else ""


def describe_tabs(elements: Iterable[Any], tabstrip_id: str,
                  selected_id: Any = "") -> list[dict[str, Any]]:
    """Les onglets d'un tabstrip depuis une perception (``ScreenElement`` ou
    tout objet à ``id``/``type``/``text``) : ``[{id, key, text, selected}]``
    dans l'ordre de perception ; ``selected`` compare à l'id (relatif) de
    ``SelectedTab``."""
    prefix = tabstrip_id.rstrip("/") + "/"
    selected = relative_id(selected_id)
    tabs: list[dict[str, Any]] = []
    for element in elements:
        element_id = _text(getattr(element, "id", ""))
        if getattr(element, "type", "") != "GuiTab" or not element_id.startswith(prefix):
            continue
        tabs.append({"id": element_id, "key": tab_key(element_id),
                     "text": _text(getattr(element, "text", "")).strip(),
                     "selected": bool(selected) and element_id == selected})
    return tabs


def find_tab_by_key(tabs: Sequence[dict[str, Any]], key: Any) -> dict[str, Any] | None:
    wanted = _text(key).strip().upper()
    for tab in tabs:
        if tab.get("key", "").upper() == wanted:
            return tab
    return None


def find_tabs_by_label(tabs: Sequence[dict[str, Any]], label: Any,
                       exact: bool = False) -> list[dict[str, Any]]:
    """TOUS les onglets dont le texte correspond (égalité, ou préfixe
    insensible à la casse) : l'ambiguïté est tranchée par l'appelant."""
    wanted = " ".join(_text(label).split()).casefold()
    if not wanted:
        return []
    matches = []
    for tab in tabs:
        text = " ".join(_text(tab.get("text")).split()).casefold()
        if (text == wanted) if exact else text.startswith(wanted):
            matches.append(tab)
    return matches


def format_tabs(tabs: Sequence[dict[str, Any]]) -> str:
    """Les onglets pour un message d'échec : ``LOGO=Logon Data (actif)``."""
    return ", ".join("%s=%s%s" % (tab.get("key") or tab.get("id"), tab.get("text", ""),
                                  " (actif)" if tab.get("selected") else "")
                     for tab in tabs) or "aucun onglet perçu"
