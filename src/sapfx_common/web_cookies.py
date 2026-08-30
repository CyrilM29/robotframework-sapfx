"""Résumé JSON-safe des cookies d'un contexte navigateur, logique pure.

Né de la promotion (convention #12) d'une lambda qui vivait dans le page
object de session Work Zone : le prédicat qui a un sens est « expiration
FUTURE », jamais « expiration renseignée ». La bibliothèque Browser rend un
cookie de SESSION (sans expiration) avec une date de 1969 (epoch moins un) :
un prédicat naïf le lirait comme un cookie permanent, et un test de perte de
session serait vert à l'envers (leçon live 2026-08-26, campagne Work Zone).

Aucune VALEUR de cookie n'entre jamais ici : le résumé ne porte que le nom,
le domaine et le prédicat d'expiration, ce qui peut entrer dans un test (et
dans un log) sans fuiter un jeton de session.
"""
from __future__ import annotations

from typing import Any


def expires_in_future(expires: Any, now: float) -> bool:
    """Vrai seulement pour une expiration RÉELLEMENT future.

    ``expires`` tel que le rend la bibliothèque Browser : un ``datetime``
    (cookie persistant, y compris la sentinelle 1969 d'un cookie de session),
    une chaîne, un nombre epoch, ou rien. Une chaîne n'est jamais comparée
    (on ne devine pas son format), une sentinelle passée rend faux."""
    if not expires or isinstance(expires, str):
        return False
    timestamp = getattr(expires, "timestamp", None)
    if callable(timestamp):
        try:
            return float(timestamp()) > now
        except (OverflowError, OSError, ValueError):
            return False
    try:
        return float(expires) > now
    except (TypeError, ValueError):
        return False


def summarize_cookies(entries: Any, now: float) -> list[dict[str, Any]]:
    """Cookies -> liste triée de ``{name, domain, future_expiration}``.

    Trie par (domaine, nom) pour un résultat déterministe ; ne retourne et ne
    lit JAMAIS la valeur d'un cookie. ``entries`` est la liste de dicts que
    rend ``Get Cookies`` de Browser (``dictionary``)."""
    out = []
    for cookie in entries or []:
        out.append({
            "name": str(cookie.get("name") or ""),
            "domain": str(cookie.get("domain") or ""),
            "future_expiration": expires_in_future(cookie.get("expires"), now),
        })
    return sorted(out, key=lambda e: (e["domain"], e["name"]))
