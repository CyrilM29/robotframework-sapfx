"""Primitives de synchronisation partagées ECC/Fiori.

Avant ce module, chaque bibliothèque portait sa propre boucle « sonder jusqu'à
échéance » et « retenter sur exception » (trois implémentations quasi identiques :
`_waits.py`, `_connection.py`, `SapFioriLibrary._act_with_retry`). Les trois
formes canoniques vivent désormais ici ; les mixins/keywords ne gardent que leurs
messages d'erreur métier.
"""
from __future__ import annotations

import time
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


def poll_until(check: Callable[[], T], timeout_secs: float, step: float = 0.2) -> T:
    """Répète ``check()`` jusqu'à ce qu'il retourne une valeur *truthy* ou que
    ``timeout_secs`` soit écoulé. Retourne la dernière valeur obtenue (truthy en
    cas de succès, falsy en cas d'expiration) : l'appelant décide du message
    d'échec. ``check`` ne doit pas lever : envelopper les sondes COM/JS fragiles
    dans un try/except retournant falsy.

    Sonde au moins une fois, même avec un délai nul ou négatif.
    """
    deadline = time.time() + float(timeout_secs)
    while True:
        result = check()
        if result:
            return result
        if time.time() >= deadline:
            return result
        time.sleep(step)


def retry_call(action: Callable[[], T], attempts: int = 3, interval: float = 0.25,
               deadline: Optional[float] = None,
               on_error: Optional[Callable[[int, Exception], None]] = None) -> T:
    """Appelle ``action()`` en retentant sur exception, au plus ``attempts`` fois
    espacées de ``interval`` secondes. Retourne le résultat de la première
    tentative réussie ; relève la **dernière** exception quand toutes échouent.

    ``deadline`` (epoch, optionnel) borne les relances dans le temps en plus du
    compte : plus aucune tentative n'est lancée une fois l'échéance passée.
    ``on_error(attempt, err)`` (optionnel) est appelé après chaque échec, pour
    journaliser sans dupliquer la boucle chez l'appelant.
    """
    attempts = int(attempts)
    last: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return action()
        except Exception as err:
            last = err
            if on_error is not None:
                on_error(attempt, err)
            if deadline is not None and time.time() >= deadline:
                break
            if attempt < attempts:
                time.sleep(interval)
    assert last is not None   # atteint uniquement après au moins un échec (attempts >= 1)
    raise last


def retry_until(action: Callable[[], T], timeout_secs: float, step: float = 0.5) -> T:
    """Appelle ``action()`` jusqu'à ce qu'il réussisse (aucune exception) ou que
    ``timeout_secs`` soit écoulé ; relève alors la dernière exception. Variante
    bornée par le temps (et non par un compte d'essais) de `retry_call` : le
    rythme d'attente est ``step`` secondes entre deux tentatives."""
    deadline = time.time() + float(timeout_secs)
    while True:
        try:
            return action()
        except Exception:
            if time.time() >= deadline:
                raise
            time.sleep(step)
