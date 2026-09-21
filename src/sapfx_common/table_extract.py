"""Le contrat d'EXTRACTION d'un tableau, commun aux canaux (2026-09-15).

Les cinq écrivains de restitution (:mod:`sapfx_common.table_svg`,
:mod:`table_xlsx`, :mod:`table_csv`, :mod:`table_json`, :mod:`table_parquet`)
sont indépendants du canal : ils prennent des lignes et des colonnes. Ce qui ne
l'est PAS, c'est la LECTURE qui les alimente, et c'est là que vit le seul
risque sérieux de cette capacité.

**Les quatre canaux matérialisent leur tableau paresseusement, chacun à sa
façon, et aucun ne le dit spontanément.** Mesuré les 2026-09-15 et 16 sur les
cibles du banc :

===========  ==================================  ===================  ==========================
Canal        Ce qui est rendu                    Ce qui est déclaré   Ce qui trahit l'amputation
===========  ==================================  ===================  ==========================
SAP GUI      toutes les lignes, mais les         ``RowCount``         des lignes VIDES
(ALV)        cellules non défilées sont VIDES
WebGUI       une page de 200 lignes,             ``totalRows`` du     **rien**
(ITS)        renumérotées ``row[1]``...          ``lsdata``
UI5          ``growingThreshold`` lignes         ``getLength()`` du   **rien**
(sap.m)      (30 mesurées sur 4133)              binding
RFC          ``ROWCOUNT`` lignes exactement      **rien du tout**,    **rien**
(READ_TABLE) (50 mesurées sur 205)               total à mesurer
                                                 par un AUTRE module
===========  ==================================  ===================  ==========================

Trois canaux sur quatre ne laissent AUCUNE trace : les lignes rendues sont
propres, complètes, correctement numérotées, et le fichier produit ressemble
trait pour trait à un inventaire. Seule la confrontation au total DÉCLARÉ
distingue « le tableau tient en N lignes » de « la lecture s'est arrêtée à N
lignes ».

Le RFC est le cas limite : il ne déclare RIEN. Son total vient donc d'un
module de comptage distinct de celui qui lit, et c'est cette indépendance qui
fait que la garde mesure quelque chose plutôt que de comparer une lecture à
elle-même (voir :mod:`sapfx_common.rfc_extract`).

D'où ce module : **une seule règle de refus, pour les quatre canaux**. La
faire vivre dans chaque suite reviendrait à la réécrire à chaque nouveau
canal, et une revue indépendante a déjà relevé le 2026-09-15 qu'une garde
oubliée sur un seul chemin suffit à produire cinq fichiers creux, tous verts.

Importable comme bibliothèque Robot (``Library    sapfx_common.table_extract``),
sur le patron de :mod:`sapfx_common.artifacts` : les primitives pures
s'atteignent par un KEYWORD, jamais par un ``Evaluate __import__(...)``.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from sapfx_common._tabular import blank_rows, normalize_rows, table_columns
from sapfx_common.robot_args import as_name_list, as_optional_int

__all__ = ["build_table_extract", "table_extract_should_be_complete",
           "describe_table_extract", "project_extract_rows"]


def _titles(columns: Sequence[str],
            headers: Optional[Mapping[str, Any]]) -> dict[str, str]:
    """La carte ``{colonne: titre affiché}``, réduite aux colonnes rendues.

    Une colonne sans titre garde son identifiant : mieux vaut un nom technique
    qu'une colonne sans nom.
    """
    carte: dict[str, str] = {}
    for colonne in columns:
        brut = (headers or {}).get(str(colonne))
        texte = "" if brut is None else str(brut).strip()
        carte[str(colonne)] = texte or str(colonne)
    return carte


def _keyless(rows: Sequence[Mapping[str, Any]], key: str) -> int:
    """Combien de lignes n'ont pas de valeur dans la colonne CLÉ.

    Une ligne sans sa clé est un relevé partiel qu'un compte de lignes ne voit
    pas : le cas d'une grille dont la première fenêtre seule a été chargée.
    """
    return sum(1 for ligne in rows if not str(ligne.get(key) or "").strip())


def _declared_is_final(value: Any) -> bool:
    """Le total déclaré est-il ARRÊTÉ, ou la source compte-t-elle encore ?

    Seul un faux EXPLICITE vaut « provisoire ». Une source qui n'expose pas la
    notion (un modèle client connaît ses données, son binding n'a pas
    d'``isLengthFinal``) rend ``None``, et son total est bien définitif : le
    traiter comme provisoire refuserait des relevés légitimement complets.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() not in ("false", "no", "0", "")
    return bool(value)


def build_table_extract(rows: Any, columns: Any = None,
                        headers: Optional[Mapping[str, Any]] = None,
                        declared_rows: Any = None, source: Any = "",
                        key: Any = "",
                        declared_final: Any = True) -> dict[str, Any]:
    """Assemble un relevé tabulaire et SON CONTRAT, sous une forme JSON-safe.

    ``rows`` est ce qu'un lecteur de canal a rendu (`Read Full Grid`,
    `Read Ui5 Table`, `Read Webgui Grid`), ``declared_rows`` ce que la source
    DÉCLARE contenir. Les deux ne coïncident pas toujours, et c'est justement
    le sujet.

    ``declared_rows`` vaut ``None`` quand le canal ne le dit pas ; la clé
    ``complete`` vaut alors ``None`` et JAMAIS ``True`` : une complétude non
    mesurée n'est pas une complétude constatée (même repli sûr que
    ``classify_idoc_status`` ou ``job_wait_verdict``, où un statut hors carte
    n'est jamais un succès).

    ``key``, facultative, nomme la colonne qui ne peut pas être vide (le nom
    d'un paramètre, un identifiant) : les lignes qui la laissent vide sont
    comptées à part, parce qu'un relevé peut avoir le bon nombre de lignes et
    des clés manquantes.

    ``complete`` exige l'ÉGALITÉ et non « au moins autant » : un relevé plus
    long que le total déclaré n'est pas un relevé complet mais un relevé dont
    la lecture et le total ne décrivent pas le même instant, et la garde le
    refuse comme tel (relevé par une revue indépendante le 2026-09-16 : ce cas
    passait, et la campagne ne rougissait qu'après avoir écrit ses fichiers).

    ``declared_final`` à ``False`` dit que le total lui-même est PROVISOIRE :
    la source n'a pas fini de compter (`isLengthFinal` d'un binding OData). Il
    ne borne alors rien, et l'égalité ``lu == déclaré`` peut être vraie un
    instant puis fausse le suivant : un tel total est traité exactement comme
    un total absent. La notion vit ici et non dans le seul canal qui la porte,
    sans quoi son contrôle resterait dans un scénario et disparaîtrait dès
    qu'on joue un autre scénario seul.
    """
    lignes = normalize_rows(rows)
    demandees = as_name_list(columns, "columns") or None
    colonnes = table_columns(lignes, demandees)
    # Ce que l'assemblage LAISSE DE CÔTÉ. Une colonne sans nom n'est pas une
    # colonne extractible et se retire d'elle-même (une table UI5 en porte une
    # pour son indicateur de brouillon, mesuré sur cap-sflight le 2026-09-15),
    # mais le retrait ne doit pas être MUET : une clé NOMMÉE qui figure dans
    # les lignes sans figurer dans les colonnes est le témoin d'un décalage,
    # c'est-à-dire d'un relevé où les valeurs ont glissé d'un cran. Le fichier
    # produit serait alors complet, propre, fidèle au relevé, et faux.
    ignorees = [cle for cle in table_columns(lignes) if cle not in colonnes]
    lu = len(lignes)
    declare = as_optional_int(declared_rows, "declared_rows")
    if declare is not None and declare < 0:
        raise ValueError(
            "declared_rows ne peut pas être négatif (reçu %s). Passer None "
            "quand le canal ne déclare pas de total." % declare)
    vides = blank_rows(lignes, colonnes)
    cle = str(key or "").strip()
    sans_cle = _keyless(lignes, cle) if cle else 0
    arrete = _declared_is_final(declared_final)
    manquantes = None if declare is None else max(0, declare - lu)
    if declare is None or not arrete:
        complet: Optional[bool] = None
    else:
        complet = (lu == declare and vides == 0 and sans_cle == 0)
    return {"rows": lignes, "columns": colonnes,
            "headers": _titles(colonnes, headers), "row_count": lu,
            "ignored_columns": ignorees,
            "declared_rows": declare, "declared_final": arrete,
            "missing_rows": manquantes,
            "blank_rows": vides, "keyless_rows": sans_cle, "key": cle,
            "complete": complet, "source": str(source or "")}


def table_extract_should_be_complete(extract: Mapping[str, Any],
                                     min_rows: Any = 0,
                                     min_columns: Any = 0) -> dict[str, Any]:
    """LA garde d'extraction, partagée par les quatre canaux.

    Refuse un relevé AVANT qu'il ne soit écrit, en nommant laquelle des quatre
    causes s'applique. Elle s'appelle en Suite Setup et non dans un scénario :
    un refus qui constate après coup n'empêche rien, et sur un relevé amputé
    les cinq écritures passent au vert (comparer une lecture partielle à
    elle-même ne rougit jamais). La leçon a été payée deux fois, une fois sur
    la CIBLE et une fois sur le CONTENU.

    Le total non DÉCLARÉ est refusé lui aussi : accepter le silence est
    exactement le défaut que ce module existe pour empêcher, puisque le canal
    qui se tait est celui qui ne laisse aucune autre trace.
    """
    source = str(extract.get("source") or "le relevé")
    lu = int(extract.get("row_count") or 0)
    declare = extract.get("declared_rows")
    vides = int(extract.get("blank_rows") or 0)
    sans_cle = int(extract.get("keyless_rows") or 0)
    colonnes = list(extract.get("columns") or [])
    plancher_lignes = as_optional_int(min_rows, "min_rows") or 0
    plancher_colonnes = as_optional_int(min_columns, "min_columns") or 0

    if declare is not None and not extract.get("declared_final", True):
        raise AssertionError(
            "RELEVÉ REFUSÉ (%s) : le total de %s lignes que la source annonce "
            "est lui-même PROVISOIRE (elle n'a pas fini de compter), donc il "
            "ne borne rien et l'égalité avec les %d ligne(s) lues peut être "
            "vraie un instant et fausse le suivant. Attendre que la source ait "
            "arrêté son total, ou fournir un total mesuré autrement."
            % (source, declare, lu))

    if declare is None:
        raise AssertionError(
            "RELEVÉ REFUSÉ (%s) : la source n'a DÉCLARÉ aucun total, donc la "
            "complétude de ces %d ligne(s) n'est pas mesurable. C'est le cas "
            "le plus dangereux : trois des quatre canaux rendent une lecture "
            "partielle sans aucune trace (lignes propres et renumérotées), "
            "donc le fichier produit ressemblerait à un inventaire. Fournir "
            "declared_rows (Get Row Count sur une ALV, Get Ui5 Table Info sur "
            "une table UI5, Read Webgui Grid sur une grille WebGUI, "
            "Count Rfc Table Rows sur une lecture RFC, qui est le seul canal "
            "où ce refus est le cas NOMINAL puisqu'il ne déclare jamais rien "
            "de lui-même)."
            % (source, lu))

    if lu > int(declare):
        raise AssertionError(
            "RELEVÉ REFUSÉ (%s) : %d ligne(s) lues pour %d DÉCLARÉES, soit %d "
            "de PLUS que ce que la source annonce contenir. La lecture et le "
            "total ne décrivent pas le même instant (total de grille périmé, "
            "longueur de binding lue avant la dernière page), donc aucun des "
            "deux ne peut servir de preuve à l'autre. Relire les deux à la "
            "suite."
            % (source, lu, int(declare), lu - int(declare)))

    if lu < int(declare):
        raise AssertionError(
            "RELEVÉ REFUSÉ (%s) : %d ligne(s) lues pour %d DÉCLARÉES, il en "
            "manque %d. La source n'a matérialisé qu'une partie de son "
            "tableau : une ALV ne charge qu'au défilement, le WebGUI n'envoie "
            "qu'une page renumérotée à partir de 1, une table UI5 s'arrête à "
            "son seuil de croissance. Aucun fichier ne doit être écrit : il "
            "serait un extrait présenté comme un inventaire."
            % (source, lu, int(declare), int(declare) - lu))

    if vides:
        raise AssertionError(
            "RELEVÉ REFUSÉ (%s) : %d ligne(s) sur %d sont ENTIÈREMENT vides. "
            "Le nombre de lignes est pourtant juste : une ALV rend ses lignes "
            "non chargées en cellules vides au lieu de lever, donc le relevé "
            "se relit fidèlement et se compare à lui-même sans écart. Lire "
            "avec Read Full Grid." % (source, vides, lu))

    if sans_cle:
        raise AssertionError(
            "RELEVÉ REFUSÉ (%s) : %d ligne(s) sur %d n'ont pas de valeur dans "
            "la colonne clé %r. La lecture est partielle là où le compte ne "
            "le montre pas."
            % (source, sans_cle, lu, str(extract.get("key") or "")))

    if lu < plancher_lignes:
        raise AssertionError(
            "RELEVÉ REFUSÉ (%s) : %d ligne(s) seulement, le plancher attendu "
            "est %d. La source n'a probablement pas rendu ce qu'on croit lire."
            % (source, lu, plancher_lignes))

    if len(colonnes) < plancher_colonnes:
        raise AssertionError(
            "RELEVÉ REFUSÉ (%s) : %d colonne(s) seulement (%s), le plancher "
            "attendu est %d. L'extraction serait amputée."
            % (source, len(colonnes), ", ".join(colonnes) or "aucune",
               plancher_colonnes))

    return dict(extract)


def describe_table_extract(extract: Mapping[str, Any]) -> str:
    """Une ligne de journal qui dit ce qui a RÉELLEMENT été lu.

    Le total déclaré y figure toujours, y compris quand il coïncide : c'est ce
    qui distingue un journal qui prouve d'un journal qui rassure.
    """
    declare = extract.get("declared_rows")
    lu = int(extract.get("row_count") or 0)
    if declare is not None and not extract.get("declared_final", True):
        completude = ("%d ligne(s) pour un total de %d encore PROVISOIRE "
                      "(complétude non mesurable)" % (lu, int(declare)))
    elif declare is None:
        completude = "%d ligne(s), total NON DÉCLARÉ (complétude non mesurée)" % lu
    elif lu == int(declare):
        completude = "%d/%d ligne(s), complet" % (lu, int(declare))
    else:
        completude = ("%d/%d ligne(s), INCOMPLET (%d manquantes)"
                      % (lu, int(declare), int(declare) - lu))
    ignorees = [str(c) for c in (extract.get("ignored_columns") or [])]
    reste = ""
    if ignorees:
        reste = ", colonne(s) LAISSÉE(S) DE CÔTÉ : %s" % ", ".join(
            repr(c) for c in ignorees)
    return "%s : %s, %d colonne(s) [%s], %d ligne(s) vide(s)%s" % (
        str(extract.get("source") or "relevé"), completude,
        len(list(extract.get("columns") or [])),
        ", ".join(str(c) for c in extract.get("columns") or []),
        int(extract.get("blank_rows") or 0), reste)


def project_extract_rows(extract: Mapping[str, Any], headers: Any,
                         row_limit: Any = None) -> list[dict[str, Any]]:
    """Le relevé mis dans la forme que le fichier écrit doit porter.

    L'inverse exact d'une relecture, et donc la moitié de l'assertion reine :
    le fichier relu se confronte à CECI, jamais au relevé brut.

    Deux réductions, nécessaires pour des raisons différentes. ``row_limit``
    ramène aux lignes RÉELLEMENT écrites, sans quoi une extraction bornée
    comparerait un extrait à un relevé complet et échouerait sur une
    troncature pourtant demandée. ``headers`` re-clé sur les en-têtes DU
    FICHIER, sans quoi la confrontation opposerait des identifiants techniques
    à des titres affichés et déclarerait un écart là où les deux portent la
    même donnée sous deux noms.

    Promue ici le 2026-09-16, sur la remarque d'une revue indépendante : la
    même idée existait en quatre exemplaires, trois en Robot dans les suites
    de canal et une quatrième inlinée dans la couche d'export. Le risque
    n'était pas le coût d'entretien mais la DIVERGENCE : quatre corps qui
    prétendent vérifier les mêmes fichiers finissent par ne plus vérifier la
    même chose.
    """
    colonnes = [str(c) for c in (extract.get("columns") or [])]
    libelles = [str(h) for h in as_name_list(headers, "headers")]
    if len(libelles) != len(colonnes):
        raise ValueError(
            "Le fichier annonce %d en-tête(s) pour %d colonne(s) du relevé "
            "(%s contre %s) : les deux ne décrivent pas le même tableau, donc "
            "la confrontation ne prouverait rien."
            % (len(libelles), len(colonnes), ", ".join(libelles) or "aucun",
               ", ".join(colonnes) or "aucune"))
    borne = as_optional_int(row_limit, "row_limit")
    lignes = normalize_rows(extract.get("rows") or [])
    if borne is not None:
        lignes = lignes[:borne]
    return [{libelle: ligne.get(colonne, "")
             for colonne, libelle in zip(colonnes, libelles, strict=True)}
            for ligne in lignes]
