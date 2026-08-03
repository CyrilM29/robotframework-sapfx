"""Compaction des perceptions identiques et consécutives (state providers rf-mcp).

Un agent prudent appelle souvent la perception (Get Screen Signature / Get Ui5
Page Tree) plusieurs fois sans qu'aucune action n'ait eu lieu entre deux appels
— la réponse est alors, à l'octet près, identique à la précédente. On ne peut
pas sauter le parcours COM/DOM lui-même sans risque (rien ne garantit qu'aucune
action n'a eu lieu entre-temps, et servir un état périmé juste après un clic
casserait la boucle perception -> action que ces mêmes state providers
existent pour servir) : on continue donc TOUJOURS à interroger l'écran réel.

En revanche, une fois la vraie valeur obtenue, la comparer au dernier envoi
pour cette session est sûre à 100% (c'est un fait déjà constaté, pas une
prédiction) : si rien n'a changé, on économise la bande passante/les tokens en
renvoyant un marqueur compact au lieu de retexpédier un texte parfois long.
"""
from __future__ import annotations

from typing import Dict, Optional


class LastSeenCompactor:
    """Retient le dernier texte renvoyé par ``session_id`` et signale les répétitions."""

    def __init__(self) -> None:
        self._store: Dict[str, str] = {}   # session_id -> dernier texte envoyé

    def swap(self, session_id: str, value: str) -> Optional[str]:
        """Enregistre ``value`` comme dernier envoi pour ``session_id`` et
        retourne l'envoi PRÉCÉDENT (``None`` au tout premier appel pour cette
        session) — la brique du diff différentiel des state providers."""
        previous = self._store.get(session_id)
        self._store[session_id] = value
        return previous

    def compact(self, session_id: str, value: str) -> bool:
        """Enregistre ``value`` comme dernier envoi pour ``session_id`` et retourne
        ``True`` si elle est identique à l'envoi précédent (``False`` sinon, y
        compris au tout premier appel pour cette session)."""
        previous = self.swap(session_id, value)
        return previous is not None and previous == value

    def reset(self, session_id: Optional[str] = None) -> None:
        """Oublie l'historique (toutes sessions, ou seulement ``session_id``)."""
        if session_id is None:
            self._store.clear()
        else:
            self._store.pop(session_id, None)
