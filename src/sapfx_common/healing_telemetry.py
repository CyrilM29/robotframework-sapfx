"""Journal cumulatif des réparations de localisateurs (télémétrie de healing).

Le healing (``Resolve Element With Healing`` côté ECC, ``Resolve Ui5 With
Fallback`` côté Fiori) journalise déjà chaque réparation en WARNING dans le log
Robot, visible mais volatile : chaque run écrase le précédent. Ce module y
ajoute un journal **JSONL cumulatif** (une ligne JSON par réparation, en append)
qui survit aux runs : en le relisant sur une semaine de CI, on voit *quels*
localisateurs dérivent de façon récurrente : le healing devient un outil de
maintenance préventive des ``resources/``, pas seulement une rustine de runtime.

Opt-in par variable d'environnement : ``SAPFX_HEALING_LOG=<chemin du fichier>``
(désactivé si absente/vide, zéro coût). Best-effort par contrat : la télémétrie
ne fait JAMAIS échouer un test (toute erreur d'E/S est avalée), et n'écrit
jamais de valeur saisie, uniquement des localisateurs.

Module pur (aucune dépendance COM/navigateur/Robot), typé, testé hors SAP.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Optional

ENV_VAR = "SAPFX_HEALING_LOG"

# Sérialise les appends concurrents du même process (deux libs GLOBAL peuvent
# réparer dans des threads différents, ex. rf-mcp). Entre process, l'append
# POSIX/NTFS d'une ligne courte suffit.
_lock = threading.Lock()


def telemetry_path() -> Optional[str]:
    """Chemin du journal configuré, ou ``None`` si la télémétrie est désactivée."""
    path = os.environ.get(ENV_VAR, "").strip()
    return path or None


def record_healing(channel: str, original: str, healed: str,
                   score: Optional[float] = None,
                   engine: Optional[str] = None) -> bool:
    """Consigne une réparation de localisateur dans le journal JSONL.

    ``channel`` identifie le canal (``ecc`` / ``fiori``), ``original`` le
    localisateur primaire qui a dérivé, ``healed`` ce qui a été retenu à la
    place ; ``score`` (ECC : similarité [0,1]) et ``engine`` (Fiori : moteur de
    repli, xpath/sid/wc) sont facultatifs. Retourne ``True`` si une ligne a été
    écrite, ``False`` sinon (désactivé ou erreur d'E/S, jamais d'exception)."""
    path = telemetry_path()
    if not path:
        return False
    event: dict[str, object] = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "channel": channel,
        "original": original,
        "healed": healed,
    }
    if score is not None:
        event["score"] = round(float(score), 3)
    if engine:
        event["engine"] = engine
    try:
        with _lock, open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        return False
    return True
