"""Le contrat d'extraction tabulaire du canal **RFC** (2026-09-16).

Le quatrième canal rejoint :mod:`sapfx_common.table_extract`, et il y entre
avec le même défaut que les deux canaux web : ``RFC_READ_TABLE`` borné par
``ROWCOUNT`` rend exactement N lignes, propres, ordonnées et complètes, sans
qu'aucun champ de la réponse ne signale qu'il en manque. Mesuré le 2026-09-16
sur A4H (release 754) : 50 lignes demandées sur la table ``SNWD_PD`` qui en
compte 205, identifiants produits consécutifs, aucun témoin.

Ce dépôt a déjà payé ce piège une fois, et pas sur une extraction : un
``rowcount=200`` sur une table de 4719 lignes avait fait écrire « tous les
runs sont terminés » là où quatre statuts cohabitaient. La leçon vaut donc
d'être outillée plutôt que rappelée.

**Ce qui distingue ce canal des trois autres : d'où vient le total déclaré.**
Une ALV publie son ``RowCount``, une grille WebGUI son ``totalRows``, une
table UI5 la longueur de son binding. ``RFC_READ_TABLE``, lui, ne déclare
RIEN : il rend des lignes et se tait. Le total doit donc venir d'ailleurs, et
le choix de cet ailleurs est la seule décision qui compte ici.

Le compter par une SECONDE lecture ``RFC_READ_TABLE`` serait le piège de la
garde qui compare deux lectures de la même source, relevé par une revue
indépendante le 2026-09-14 sur ce dépôt : comparer deux nombres que le même
module produit de la même façon, c'est écrire une assertion vraie quoi qu'il
arrive. Le total vient donc d'un module DIFFÉRENT,
``EM_GET_NUMBER_OF_ENTRIES``, qui compte côté serveur sans rapatrier une seule
ligne (mesuré : de l'ordre de 0,02 s pour 28 782 lignes, contre 0,8 s pour les lire).

**Sa portée, mesurée et non supposée.** Le module compte la table ENTIÈRE, il
n'accepte aucune clause de sélection. Il suit en revanche le mandant de la
connexion : sur A4H, ``USR02`` est annoncée à 5 lignes et la lecture du
mandant 001 en rend exactement 5, alors que le mandant 000 existe (``T000``
en porte deux) et qu'un utilisateur y ouvre des sessions, donc y possède une
ligne ``USR02``. Les deux mesures portent bien sur la même population.

Conséquence directe, et c'est la règle de ce module : un total qui vaut pour
la table entière ne borne PAS une lecture filtrée. Les apparier produirait un
« relevé incomplet » parfaitement faux sur une lecture pourtant intègre. Un
filtre sans total fourni est donc refusé À L'ENTRÉE, plutôt que transformé en
verdict trompeur.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from sapfx_common.robot_args import as_optional_int

__all__ = ["COUNT_FUNCTION", "BUFFER_ERROR_CODE", "UNKNOWN_OBJECT_ROWS",
           "VIEW_ROWS", "entries_total", "require_bounded_scope",
           "describe_rfc_source", "count_function_missing_message",
           "buffer_exceeded_remedy"]

#: Le module qui COMPTE, distinct de celui qui LIT. C'est cette distinction
#: qui fait que la garde d'extraction mesure quelque chose.
COUNT_FUNCTION = "EM_GET_NUMBER_OF_ENTRIES"

#: Les deux totaux NÉGATIFS que rend le module, mesurés le 2026-09-29 sur les
#: deux releases du banc (754 et 758), à l'identique. ``-1`` : l'objet est
#: absent du dictionnaire (faute de frappe, nom en minuscules) ou n'est pas
#: une table porteuse de données (une structure). ``-2`` : l'objet est une
#: VUE, vue de base de données comme ``DD02V`` ou vue SQL d'une CDS comme
#: ``SEPM_IPO`` (le nom de l'entité CDS elle-même rend aussi ``-2``). Une
#: table réellement vide, elle, rend ``0``.
UNKNOWN_OBJECT_ROWS = -1
VIEW_ROWS = -2

#: Le refus du serveur quand la ligne PROJETÉE dépasse son tampon. Mesuré le
#: 2026-09-16 sur A4H : la projection complète de ``SNWD_PD`` fait 533 octets
#: et sort en ``DATA_BUFFER_EXCEEDED`` (``AD/E/559``), les paramètres du
#: message portant le nom de la table et la limite de 512.
BUFFER_ERROR_CODE = "DATA_BUFFER_EXCEEDED"


def buffer_exceeded_remedy(table: Any, fields: Any = None) -> str:
    """Le remède à journaliser quand la projection dépasse le tampon serveur.

    Il est JOURNALISÉ et le refus d'origine est relayé intact, jamais
    enveloppé : l'envelopper coûterait son attribut de code technique, donc la
    possibilité d'asserter le refus par son CODE plutôt que par son texte
    localisé (convention n°3). Une assertion perdue vaut plus cher qu'un
    message amélioré.

    Ce que le refus du serveur ne dit pas, et qui vaut d'être écrit : la limite
    porte sur la LIGNE PROJETÉE, pas sur la table ni sur son contenu, et il
    existe une sortie que personne ne devine, lire en DEUX projections qui
    partagent la clé puis les recoller côté client. C'est exactement ce que
    fait déjà `Read Change Documents` pour CDPOS, dont les deux colonnes de
    valeurs font 254 octets chacune.
    """
    nom = str(table or "?").strip().upper()
    combien = ""
    try:
        combien = " (%d champ(s) demandé(s))" % len(list(fields))
    except TypeError:
        pass
    return (
        "Projection trop large pour %s%s : le serveur borne la LIGNE PROJETÉE "
        "à 512 octets, et le refus (%s) porte sur cette largeur, pas sur la "
        "table ni sur ses données. Deux sorties : restreindre la projection "
        "aux colonnes réellement extraites, ou lire en DEUX projections qui "
        "partagent la colonne clé et les recoller côté client (le patron de "
        "Read Change Documents). La largeur d'une ligne se calcule en sommant "
        "les longueurs des champs dans DD03L." % (nom, combien, BUFFER_ERROR_CODE))


def _negative_total_message(table: str, raw: Any, total: Optional[int]) -> str:
    """Le refus d'un total que le module rend négatif (ou vide), par CAUSE."""
    if total == VIEW_ROWS:
        return (
            "%s annonce %r pour %s : c'est une VUE (vue de base de données ou "
            "vue SQL d'une CDS), que ce module ne compte pas. Pour un simple "
            "comptage, lire la seule colonne clé de la vue (Read Rfc Table) et "
            "compter les lignes ; pour borner une extraction, fournir le total "
            "d'un canal TIERS par declared_rows= (le $count d'un service OData "
            "qui projette la vue), un comptage par le module qui lit ne bornant "
            "rien." % (COUNT_FUNCTION, raw, table))
    if total == UNKNOWN_OBJECT_ROWS:
        return (
            "%s annonce %r pour %s : l'objet est absent du dictionnaire (nom "
            "mal orthographié, en minuscules) ou n'est pas une table porteuse "
            "de données (une structure). Vérifier le nom et sa classe dans "
            "DD02L. Un total qu'on ne sait pas lire ne vaut pas zéro."
            % (COUNT_FUNCTION, raw, table))
    return (
        "%s annonce un total illisible pour %s (reçu %r) : un total qu'on ne "
        "sait pas lire ne vaut pas zéro." % (COUNT_FUNCTION, table, raw))


def entries_total(response: Mapping[str, Any], table: Any) -> int:
    """Le total d'une table dans la réponse de :data:`COUNT_FUNCTION`.

    La réponse porte ``IT_TABLES``, une liste de ``{TABNAME, TABROWS}``. Le
    module rend une ligne par objet DEMANDÉ, y compris pour un objet qu'il ne
    sait pas compter, qu'il annonce alors par un total NÉGATIF
    (:data:`UNKNOWN_OBJECT_ROWS`, :data:`VIEW_ROWS`) : refusé ici en nommant
    la cause et le remède, jamais pris pour zéro. Une note antérieure (plan
    du 2026-09-16) affirmait qu'une table inexistante était annoncée à zéro ;
    elle n'avait jamais été provoquée sur une cible, et la mesure du
    2026-09-29 la dément sur les deux releases (``-1``). Le zéro reste une
    valeur légitime (une table réellement vide existe) que seul l'appelant
    peut interpréter, d'où le plancher de lignes de la garde d'extraction.
    """
    voulue = str(table or "").strip().upper()
    if not voulue:
        raise ValueError(
            "Aucune table nommée : %s ne peut pas compter ce qu'on ne lui "
            "désigne pas." % COUNT_FUNCTION)
    lignes = response.get("IT_TABLES")
    if not isinstance(lignes, Sequence) or isinstance(lignes, (str, bytes)):
        raise ValueError(
            "Réponse inattendue de %s : la table IT_TABLES est absente ou "
            "n'est pas une liste (reçu %s). Le canal RFC a répondu, mais pas "
            "ce module : vérifier qu'il est bien libéré pour l'appel distant "
            "sur la cible." % (COUNT_FUNCTION, type(lignes).__name__))
    vues: list[str] = []
    for ligne in lignes:
        if not isinstance(ligne, Mapping):
            continue
        nom = str(ligne.get("TABNAME") or "").strip().upper()
        vues.append(nom)
        if nom == voulue:
            brut = ligne.get("TABROWS")
            try:
                total = as_optional_int(brut, "TABROWS")
            except ValueError as err:
                raise ValueError(
                    "%s annonce un total illisible pour %s (reçu %r) : un "
                    "total qu'on ne sait pas lire ne vaut pas zéro, sans quoi "
                    "un relevé vide serait déclaré complet. Détail : %s"
                    % (COUNT_FUNCTION, voulue, brut, err)) from err
            if total is None or total < 0:
                raise ValueError(_negative_total_message(voulue, brut, total))
            return total
    raise ValueError(
        "%s n'a rendu aucune ligne pour la table %s (tables rendues : %s). "
        "Sans total, la complétude du relevé n'est pas mesurable."
        % (COUNT_FUNCTION, voulue, ", ".join(vues) or "aucune"))


def require_bounded_scope(table: Any, options: Any,
                          declared_rows: Any = None) -> Optional[int]:
    """Refuse d'apparier une lecture FILTRÉE à un total de table entière.

    Rend le total explicitement fourni (converti), ou ``None`` quand il faut
    aller le mesurer. Lève quand la lecture porte une clause de sélection sans
    qu'aucun total n'ait été fourni : dans ce cas précis, le seul total que le
    canal sache produire décrit une AUTRE population que la lecture, et les
    confronter afficherait des lignes manquantes qui n'ont jamais existé.

    Le refus est à l'ENTRÉE, avant le moindre aller-retour réseau, parce
    qu'un refus qui constate après coup n'empêche rien : la leçon de la garde
    de cible qui rougissait dans un scénario pendant que les suivants
    écrivaient les fichiers du mauvais système (2026-09-15).
    """
    fourni = as_optional_int(declared_rows, "declared_rows")
    if fourni is not None and fourni < 0:
        raise ValueError(
            "declared_rows ne peut pas être négatif (reçu %s)." % fourni)
    if fourni is not None:
        return fourni
    clauses = _clause_text(options)
    if not clauses:
        return None
    raise ValueError(
        "Lecture FILTRÉE de %s sans total fourni : %s compte la table "
        "ENTIÈRE et n'accepte aucune clause de sélection, donc son total "
        "décrirait une autre population que la clause %r. Les confronter "
        "annoncerait des lignes manquantes qui n'existent pas. Deux sorties "
        "honnêtes : retirer le filtre pour extraire la table entière, ou "
        "passer declared_rows= mesuré autrement (le $count du service OData "
        "qui projette la même table, un comptage d'écran SE16)."
        % (str(table or "?").strip().upper(), COUNT_FUNCTION, clauses))


def _clause_text(options: Any) -> str:
    """Les clauses de sélection ramenées à un texte, vide quand il n'y en a pas.

    ``options`` arrive en chaîne, en liste de chaînes, ou en liste de
    dictionnaires ``{TEXT: ...}`` (la forme que le module ABAP attend) : les
    trois transitent par la frontière Robot, et une liste vide ne filtre rien.
    """
    if options is None:
        return ""
    if isinstance(options, str):
        return options.strip()
    if isinstance(options, Mapping):
        return str(options.get("TEXT") or "").strip()
    if isinstance(options, Sequence):
        morceaux = [_clause_text(item) for item in options]
        return " ".join(m for m in morceaux if m).strip()
    return str(options).strip()


def describe_rfc_source(table: Any, fields: Any = None, options: Any = None,
                        rowcount: Any = 0) -> str:
    """Le libellé de provenance que le relevé porte, et que ses refus citent.

    Il nomme la table, le nombre de champs projetés et, surtout, le PLAFOND
    demandé quand il y en a un : c'est l'information qui manque le plus au
    lecteur d'un relevé court, puisque le canal ne la redonne nulle part.
    """
    nom = str(table or "?").strip().upper()
    morceaux = ["la table %s (RFC)" % nom]
    if fields is not None:
        try:
            morceaux.append("%d colonne(s) projetée(s)" % len(list(fields)))
        except TypeError:
            pass
    borne = as_optional_int(rowcount, "rowcount") or 0
    if borne:
        morceaux.append("PLAFOND demandé %d" % borne)
    clauses = _clause_text(options)
    if clauses:
        morceaux.append("filtre %s" % clauses)
    return ", ".join(morceaux)


def count_function_missing_message(table: Any, error: Any) -> str:
    """Le refus quand la cible ne libère pas le module de comptage.

    ``EM_GET_NUMBER_OF_ENTRIES`` n'est pas garanti appelable à distance
    partout (une cible durcie restreint ``S_RFC`` module par module). Le dire
    en nommant les replis vaut mieux qu'un code technique nu, qui enverrait
    chercher un défaut de connexion là où le canal fonctionne parfaitement.
    """
    return (
        "Impossible de compter %s par %s (%s). Ce module n'est pas libéré "
        "pour l'appel distant sur cette cible, ou l'autorisation S_RFC le "
        "restreint. Sans lui le canal RFC ne DÉCLARE aucun total, donc la "
        "complétude n'est pas mesurable : passer declared_rows= mesuré "
        "autrement (le $count du service OData qui projette la table, le "
        "compteur « Number of Entries » de SE16), plutôt que de tenir une "
        "lecture bornée pour un inventaire."
        % (str(table or "?").strip().upper(), COUNT_FUNCTION, error))
