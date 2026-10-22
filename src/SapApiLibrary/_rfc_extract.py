"""Mixin d'*extraction tabulaire* du canal RFC (2026-09-16).

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

from sapfx_common import rfc_extract
from sapfx_common.argument_types import TableNameInput

from ._rfc_spool import RfcSpoolKeywords


class RfcExtractKeywords(RfcSpoolKeywords):
    """Mixin de :class:`SapApiLibrary` : extraire un tableau par le canal RFC."""

    def count_rfc_table_rows(self, table: TableNameInput, alias: str = "default") -> int:
        """Compte les lignes d'une table *sans en rapatrier aucune*, par un
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
        apparier les deux annoncerait des lignes manquantes qui n'existent
        pas. Il suit en revanche le mandant
        de la connexion, donc il compte bien la même population que la
        lecture (sur A4H, ``USR02`` est annoncée à 5 lignes et le mandant 001
        en rend exactement 5, alors que le mandant 000 existe et porte au
        moins un utilisateur).

        Ce que le module ne sait pas compter, il l'annonce par un total
        NÉGATIF, refusé ici en nommant la cause (mesuré le 2026-09-29 sur les
        deux releases du banc) : ``-1`` pour un objet absent du dictionnaire
        ou une structure, ``-2`` pour une VUE (vue de base de données ou vue
        SQL d'une CDS). Une vue se compte en lisant sa seule colonne clé
        (`Read Rfc Table`), ou se borne par le total d'un canal tiers. Un zéro, lui, désigne une
        table réellement vide, que seul un plancher de lignes distingue d'un
        relevé intègre.

        Exemple :
        | ${total}=    `Count Rfc Table Rows`    SNWD_PD    alias=a4h
        | Should Be Equal As Integers    ${total}    205
        """
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

