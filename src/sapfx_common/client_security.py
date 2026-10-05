"""Posture de sécurité du poste client SAP GUI : logique pure, sans COM.

Contexte : jusqu'en janvier 2025, l'historique de saisie de SAP GUI for
Windows (fichiers ``SAPHistory*.db``) était protégé par un chiffrement XOR à
clé statique réutilisée : une seule saisie connue suffisait à reconstituer la
clé et déchiffrer tout l'historique (CVE-2025-0055, note SAP 3472837 ;
chiffrement renforcé à partir de SAP GUI for Windows 8.00 PL9 ; la variante
SAP GUI for Java est la CVE-2025-0056). Sur un poste de TEST c'est aggravé : les suites tapent des
données dans de vrais champs, donc tout ce qu'un run saisit peut se retrouver
persisté dans l'historique local du poste. Deux parades complémentaires :

- un client **patché** (8.00 PL9+ ou 8.10+) : :func:`input_history_cve_status`
  classe la version du client ;
- l'historique de saisie **désactivé** (Options SAP GUI → Local Data →
  History) : :func:`find_history_databases` constate la présence de bases
  d'historique sur le poste (des fichiers présents = l'historique a été actif,
  et leur contenu reste à purger même après désactivation).

La frontière COM/E-S assertive vit dans ``SapEccLibrary`` (mixin
``_diagnostics.py``, keywords ``Get Client Security Status`` /
``Client Security Should Be Hardened``). Ici : fonctions pures + un scan
filesystem best-effort, unit-testables sans SAP.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional, Sequence, Union

INPUT_HISTORY_PATCHED = "patched"
INPUT_HISTORY_VULNERABLE = "vulnerable"
INPUT_HISTORY_UNKNOWN = "unknown"

# CVE-2025-0055 : chiffrement de l'historique renforcé à partir de 8.00 PL9 ;
# les branches publiées après le correctif (8.10+) embarquent le fix.
_FIXED_BRANCH = (8, 0)
_FIXED_PATCHLEVEL = 9


def _as_int(value: object) -> Optional[int]:
    """``int`` défensif : ``None`` si la valeur est absente ou non numérique
    (les propriétés COM remontent selon les versions int, chaîne, ou rien)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def input_history_cve_status(major: object, minor: object,
                             patchlevel: object) -> str:
    """Classe la version du client SAP GUI vis-à-vis de la vulnérabilité de
    l'historique de saisie (CVE-2025-0055).

    Retourne ``"patched"`` (8.00 PL9+, ou branche postérieure type 8.10),
    ``"vulnerable"`` (8.00 PL < 9) ou ``"unknown"`` (version non exposée,
    non numérique, ou branche antérieure à 8.00, à vérifier via les notes
    de sécurité SAP de janvier 2025)."""
    version_major = _as_int(major)
    version_minor = _as_int(minor)
    if version_major is None or version_minor is None:
        return INPUT_HISTORY_UNKNOWN
    version = (version_major, version_minor)
    if version > _FIXED_BRANCH:
        return INPUT_HISTORY_PATCHED
    if version < _FIXED_BRANCH:
        return INPUT_HISTORY_UNKNOWN
    pl = _as_int(patchlevel)
    if pl is None:
        return INPUT_HISTORY_UNKNOWN
    return INPUT_HISTORY_PATCHED if pl >= _FIXED_PATCHLEVEL \
        else INPUT_HISTORY_VULNERABLE


def default_history_dirs() -> list[Path]:
    """Emplacements connus des bases d'historique de saisie SAP GUI sur le
    poste courant : le répertoire documenté des options SAP GUI
    (``%APPDATA%\\SAP\\SAP GUI\\History``) et l'emplacement cache relevé par
    l'analyse de la CVE (``AppData\\LocalLow\\SAPGUI\\Cache\\History``).
    Best-effort : un répertoire absent est simplement ignoré au scan."""
    dirs: list[Path] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        dirs.append(Path(appdata) / "SAP" / "SAP GUI" / "History")
    profile = os.environ.get("USERPROFILE")
    if profile:
        dirs.append(Path(profile) / "AppData" / "LocalLow" / "SAPGUI"
                    / "Cache" / "History")
    return dirs


def find_history_databases(
        dirs: Optional[Iterable[Union[str, Path]]] = None) -> list[str]:
    """Liste les bases d'historique de saisie (``*.db``) trouvées dans
    ``dirs`` (défaut : :func:`default_history_dirs`). Jamais d'exception :
    répertoire absent ou illisible = ignoré. Ordre déterministe."""
    candidates: Sequence[Path]
    if dirs is None:
        candidates = default_history_dirs()
    else:
        candidates = [Path(d) for d in dirs]
    found: list[str] = []
    for directory in candidates:
        try:
            if not directory.is_dir():
                continue
            found.extend(str(path) for path in sorted(directory.glob("*.db")))
        except OSError:
            continue
    return found
