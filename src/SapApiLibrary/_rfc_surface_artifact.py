"""Mixin de la *surface du canal RFC* : l'artefact déterministe d'une cible
et la comparaison de deux cibles (`Write Rfc Surface Artifact`,
`Read Rfc Surface Artifact`, `Compare Rfc Surface Artifacts`), hors ligne,
logique pure dans ``sapfx_common.rfc_surface``.

Extrait de ``_rfc.py`` le 2026-10-06 (convention n°13).
"""
from __future__ import annotations

import datetime
import json
from typing import Any, Iterable, Mapping, Optional

from robot.api import logger

from sapfx_common import rfc_surface

from ._rfc_spool import RfcSpoolKeywords


class RfcSurfaceArtifactKeywords(RfcSpoolKeywords):
    """Mixin de :class:`SapApiLibrary` : la surface du canal RFC en artefact."""

    def write_rfc_surface_artifact(
            self, path: str, target_id: str, identity: Mapping[str, Any],
            measures: Mapping[str, Any],
            components: Optional[Iterable[Mapping[str, Any]]] = None
    ) -> dict[str, Any]:
        """Écrit l'artefact déterministe de la *surface du canal RFC* d'une
        cible et retourne sa preuve : ``{path, sha256, summary}``.

        La surface d'un canal, ce sont ses décomptes (modules ouverts à
        distance, interfaces métier publiées, objets du modèle de
        programmation, volumétries des jeux de démonstration) plus l'inventaire
        des composants logiciels installés. La question « quels modules ici et
        pas là-bas » ne se répond pas par une note dans un document : elle se
        répond par un artefact produit sur chaque cible et comparé par
        `Compare Rfc Surface Artifacts`.

        ``identity`` porte l'identité de la cible (``system_id``, ``client``,
        ``release``, ``kernel``, ``database``, ``operating_system``,
        ``host``), et elle n'est pas décorative : sans elle, comparer deux
        artefacts revient à comparer deux inconnues. Le hash EXCLUT
        l'horodatage, donc deux exécutions sur la même cible lisant les mêmes
        chiffres produisent le même hash. Une mesure non entière, un périmètre
        vide ou un composant sans nom sont refusés à l'écriture plutôt que
        comparés plus tard. Hors ligne : n'ouvre aucune connexion.

        Exemple :
        | ${products}=    `Count Rfc Table Rows`    SNWD_PD    alias=a4h
        | &{identity}=    Create Dictionary    system_id=A4H    client=001    release=754    kernel=777
        | &{measures}=    Create Dictionary    epm_products=${products}
        | ${proof}=    `Write Rfc Surface Artifact`    ${OUTPUT DIR}/surface_a4h.json    a4h
        | ...    ${identity}    ${measures}
        | Log    ${proof}[sha256]
        """
        observed = datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds")
        surface = rfc_surface.build_surface(
            target_id, identity, measures, observed, components=components)
        digest = rfc_surface.comparison_hash(surface)
        with open(str(path), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(rfc_surface.surface_json(surface))
        logger.info("Surface RFC écrite dans %s (sha256 %s)." % (path, digest))
        return {"path": str(path), "sha256": digest,
                "summary": surface["summary"]}

    def read_rfc_surface_artifact(self, path: str) -> dict[str, Any]:
        """Relit un artefact écrit par `Write Rfc Surface Artifact` et le rend
        tel quel (dict JSON-safe : identité, périmètre, mesures, composants).

        Le symétrique de l'écriture, pour qu'une suite n'ait jamais à ouvrir le
        fichier elle-même : les primitives de cette bibliothèque s'atteignent
        par un keyword, jamais par un import improvisé dans un test. Hors
        ligne : ne joint aucune cible.

        Exemple :
        | ${surface}=    `Read Rfc Surface Artifact`    ${OUTPUT DIR}/surface_a4h.json
        | Should Be Equal    ${surface}[identity][release]    754
        """
        with open(str(path), encoding="utf-8") as handle:
            return dict(json.load(handle))

    def compare_rfc_surface_artifacts(self, path_a: str,
                                      path_b: str) -> dict[str, Any]:
        """Compare deux artefacts écrits par `Write Rfc Surface Artifact`.

        Charge les deux fichiers, journalise le rapport Markdown et retourne
        la comparaison JSON-safe : différences d'identité, écarts de mesure, et
        les composants logiciels rendus dans les trois catégories utiles
        (communs, propres à la première cible, propres à la seconde), avec les
        changements de release des communs.

        Le périmètre est une PORTE : deux artefacts dont les ensembles de
        mesures diffèrent sont marqués non comparables et seules les mesures
        communes sont chiffrées, parce qu'une mesure absente d'un côté ne vaut
        pas zéro. Hors ligne : aucune cible n'est jointe, la comparaison se
        fait sur les fichiers.

        Exemple :
        | ${comparison}=    `Compare Rfc Surface Artifacts`    ${OUTPUT DIR}/surface_a4h.json
        | ...    ${OUTPUT DIR}/surface_abap2023.json
        | Log    ${comparison}
        """
        with open(str(path_a), encoding="utf-8") as handle:
            surface_a = json.load(handle)
        with open(str(path_b), encoding="utf-8") as handle:
            surface_b = json.load(handle)
        try:
            comparison = rfc_surface.compare_surfaces(surface_a, surface_b)
        except ValueError as error:
            raise AssertionError(
                "Compare Rfc Surface Artifacts : %s" % error) from error
        logger.info(rfc_surface.render_surface_report(comparison))
        return comparison
