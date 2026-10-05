"""Mixin d'**extraction tabulaire** du canal RFC (2026-09-16).

Le quatrième canal rejoint le contrat commun de
:mod:`sapfx_common.table_extract`, celui que l'écran SAP GUI, le WebGUI et
UI5 partagent depuis le 2026-09-15. Il apporte le même piège et une
difficulté de plus : ``RFC_READ_TABLE`` tronque en silence comme le WebGUI,
et contrairement aux trois autres canaux il ne DÉCLARE aucun total, donc le
total doit être mesuré par un module distinct. Le raisonnement, ses mesures
et la règle du filtre vivent dans :mod:`sapfx_common.rfc_extract`.

Voisin de ``_rfc_reads.py`` et non ajouté dedans (convention #13) : celui-là
lit des PREUVES d'exploitation que l'on juge (documents de modification,
statuts d'IDoc, journaux), celui-ci rend un tableau que l'on RESTITUE, et les
deux n'ont ni le même contrat de sortie ni les mêmes gardes.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from robot.api import logger

from sapfx_common import rfc_channel, rfc_extract, rfc_tables, table_extract

from ._rfc_spool import RfcSpoolKeywords


class RfcExtractKeywords(RfcSpoolKeywords):
    """Mixin de :class:`SapApiLibrary` : extraire un tableau par le canal RFC."""

    def count_rfc_table_rows(self, table: str, alias: str = "default") -> int:
        """Compte les lignes d'une table **sans en rapatrier aucune**, par un
        module DIFFÉRENT de celui qui lit.

        C'est le total déclaré du canal RFC, et son intérêt tient entièrement
        à cette différence. Compter par une seconde `Read Rfc Table` serait
        comparer deux nombres que le même module produit de la même façon,
        c'est-à-dire écrire une garde vraie quoi qu'il arrive : le défaut
        exact qu'une revue indépendante a relevé sur ce dépôt le 2026-09-14.
        Ici le comptage se fait côté serveur (mesuré sur A4H : de l'ordre de 0,02 s
        pour 28 782 lignes, contre 0,8 s pour les lire), et il ne peut pas être
        tronqué par le plafond qui, lui, menace la lecture.

        Deux propriétés à connaître, toutes deux mesurées et non supposées.
        Le module compte la table ENTIÈRE et n'accepte aucune clause de
        sélection : il ne sait donc pas borner une lecture filtrée, et
        `Extract Rfc Table` refuse de les apparier plutôt que d'annoncer des
        lignes manquantes qui n'existent pas. Il suit en revanche le mandant
        de la connexion, donc il compte bien la même population que la
        lecture (sur A4H, ``USR02`` est annoncée à 5 lignes et le mandant 001
        en rend exactement 5, alors que le mandant 000 existe et porte au
        moins un utilisateur).

        Ce que le module ne sait pas compter, il l'annonce par un total
        NÉGATIF, refusé ici en nommant la cause (mesuré le 2026-09-29 sur les
        deux releases du banc) : ``-1`` pour un objet absent du dictionnaire
        ou une structure, ``-2`` pour une VUE (vue de base de données ou vue
        SQL d'une CDS). Une vue se compte en lisant sa seule colonne clé
        (`Read Rfc Table`), ou se borne par le total d'un canal tiers
        (`declared_rows=` d'`Extract Rfc Table`). Un zéro, lui, désigne une
        table réellement vide, que seul un plancher de lignes distingue d'un
        relevé intègre."""
        nom = str(table or "").strip().upper()
        if not nom:
            raise ValueError(
                "Aucune table nommée : Count Rfc Table Rows a besoin du nom "
                "de la table à compter.")
        try:
            reponse = self.call_rfc(rfc_extract.COUNT_FUNCTION, alias=alias,
                                    IT_TABLES=[{"TABNAME": nom}])
        except Exception as err:   # noqa: BLE001 : re-levé en nommant le remède
            raise RuntimeError(
                rfc_extract.count_function_missing_message(nom, err)) from err
        return rfc_extract.entries_total(reponse, nom)

    def extract_rfc_table(self, table: str, fields: Any,
                          alias: str = "default", options: Any = None,
                          rowcount: Any = 0, key: Any = "",
                          headers: Optional[Mapping[str, Any]] = None,
                          declared_rows: Any = None,
                          delimiter: str = "|") -> dict[str, Any]:
        """Extrait un tableau par RFC et rend le relevé **avec son contrat**,
        dans la forme commune aux quatre canaux.

        Le miroir sans écran d'`Extract Displayed Report` (SAP GUI),
        d'`Extract Displayed WebGui Grid` et d'`Extract Displayed Ui5 Table` :
        même dictionnaire en sortie, donc même garde
        (`Table Extract Should Be Complete`) et mêmes écrivains de fichiers.
        Une règle par canal est une règle qu'un canal de plus fait oublier.

        Le total déclaré est mesuré par `Count Rfc Table Rows`, sauf si
        ``declared_rows`` est fourni : le passer permet de PROUVER la
        complétude par un canal tiers (le ``$count`` du service OData qui
        projette la même table), ce qui est la preuve la plus forte que ce
        dépôt sache produire, puisque ni le module de lecture ni celui de
        comptage n'y participent.

        Ce que le canal ne sait pas faire, et qui doit se lire ici plutôt que
        se découvrir à l'usage : il n'expose **aucun libellé affiché**. Les
        colonnes sont des noms de champs ABAP, stables et indépendants de la
        langue, donc le contraire exact du canal UI5, dont les seules clés
        disponibles sont des titres traduits. Passer ``headers`` permet à la
        couche métier de donner des en-têtes humains au fichier livré, sans
        que le relevé perde ses clés techniques.

        ``rowcount`` borne la lecture, et c'est justement le geste dangereux :
        le module rend alors exactement N lignes, propres et ordonnées, sans
        aucun témoin de la troncature (mesuré le 2026-09-16 : 50 lignes
        rendues sur les 205 de ``SNWD_PD``). La garde partagée le voit parce
        que le total, lui, vient d'ailleurs.

        Dernière limite du canal, et elle porte sur la LARGEUR et non sur la
        hauteur : le serveur borne la ligne PROJETÉE à 512 octets. Extraire
        « toute la table » échoue donc sur les tables larges (mesuré :
        ``SNWD_PD`` fait 533 octets sur ses 24 champs, refus
        ``DATA_BUFFER_EXCEEDED`` / ``AD/E/559``). Le refus est relayé INTACT,
        pour rester assertable par son code, et son remède est journalisé en
        avertissement, parce que la sortie de secours (lire en deux
        projections qui partagent la clé, puis recoller) ne se devine pas."""
        nom = str(table or "").strip().upper()
        projection = rfc_tables.as_field_list(fields)
        if not projection:
            raise ValueError(
                "Aucune colonne projetée pour %s : une extraction RFC nomme "
                "les champs à lire (le module ne sait pas rendre « toutes les "
                "colonnes », et une ligne projetée reste bornée à 512 octets)."
                % (nom or "?"))
        # Le refus du couple filtre + total de table entière tombe AVANT le
        # moindre aller-retour : un refus qui constate après coup n'empêche
        # rien, et la lecture d'une grosse table n'est pas gratuite.
        declare = rfc_extract.require_bounded_scope(nom, options, declared_rows)
        try:
            lignes = self.read_rfc_table(nom, projection, alias=alias,
                                         options=options,
                                         rowcount=int(rowcount or 0),
                                         delimiter=delimiter)
        except Exception as err:   # noqa: BLE001 : le refus est RELAYÉ intact
            if rfc_channel.rfc_error_code(err).upper() == rfc_extract.BUFFER_ERROR_CODE:
                # Journalisé, jamais enveloppé : envelopper coûterait le code
                # technique du refus, donc la possibilité de l'asserter
                # autrement que par un texte localisé (convention n°3).
                logger.warn(rfc_extract.buffer_exceeded_remedy(nom, projection))
            raise
        if declare is None:
            declare = self.count_rfc_table_rows(nom, alias=alias)
        return table_extract.build_table_extract(
            lignes, columns=projection, headers=headers,
            declared_rows=declare, key=key,
            source=rfc_extract.describe_rfc_source(nom, projection, options,
                                                   rowcount))
