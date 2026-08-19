"""Briques partagées par les scripts d'outillage du dépôt.

Deux besoins revenaient copiés d'un garde à l'autre, et divergeaient :

* **la sortie console**. Les rapports contiennent des caractères hors cp1252
  (flèches, « ≠ »), et sous Windows les flux standard de Python sont ouverts
  dans l'encodage du poste : imprimer un rapport y lève ``UnicodeEncodeError``
  sur ``stdout`` (erreurs strictes) et produit du mojibake sur ``stderr``
  (erreurs ``backslashreplace``). Quatre gardes reconfiguraient leur
  ``stdout``, dix non : un consommateur programmatique (CI, hook post-édition,
  agent) recevait donc un mélange de deux encodages. ``force_utf8_stdio()``
  tranche pour tout le monde, ``stderr`` compris ;
* **la version du projet**. Trois lectures de ``pyproject.toml`` cohabitaient,
  dont deux prenaient la première ligne ``version = "…"`` toutes sections
  confondues : exactes tant que le fichier n'en porte qu'une, fausses le jour
  où un ``[tool.*]`` en déclare une plus haut. La lecture consciente des
  sections devient la seule.

Périmètre : les scripts d'outillage du dépôt. Les deux scripts EMBARQUÉS dans
le pack Windows (``check_spec_sync.py``, ``healing_drift_report.py``) gardent
volontairement leur version en ligne de ces quelques lignes : ils doivent
rester exécutables seuls depuis la racine du pack, sans voisin.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

#: ``version = "…"`` en début de ligne (la forme normalisée d'un pyproject).
_VERSION_LINE = re.compile(r'version\s*=\s*"([^"]+)"')


def force_utf8_stdio() -> None:
    """Force ``stdout`` et ``stderr`` en UTF-8, en remplaçant l'irreprésentable.

    ``hasattr`` : sous pytest (ou toute capture), les flux ne sont pas des
    ``TextIOWrapper`` et n'ont pas de ``reconfigure``. Ne jamais faire échouer
    un garde sur son propre affichage.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def read_project_version(pyproject_text: str) -> str:
    """Extrait ``version`` de la section ``[project]`` d'un pyproject.toml.

    Regex volontairement (pas ``tomllib``) : compatible avec le plancher
    ``requires-python`` du dépôt et suffisant pour un champ que nous
    contrôlons. La section est SUIVIE, elle : une ``version`` déclarée par un
    ``[tool.*]`` n'est pas celle du projet.
    """
    in_project = False
    for line in pyproject_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_project = stripped == "[project]"
            continue
        if in_project:
            match = _VERSION_LINE.match(stripped)
            if match:
                return match.group(1)
    raise ValueError("version introuvable dans la section [project] du pyproject.toml")


def project_version(root: Path | str) -> str:
    """La version déclarée par le ``pyproject.toml`` de ``root``."""
    text = (Path(root) / "pyproject.toml").read_text(encoding="utf-8")
    return read_project_version(text)
