"""Critères d'un écran de sélection SE16 rendu par le **WebGUI**, logique pure.

Le miroir web de ``Get Se16 Selection Criteria`` (canal écran SAP GUI), et il
existe pour la même raison : les critères d'un écran de sélection SE16 sont
POSITIONNELS (``I1-LOW``, ``I2-LOW``...), leur ordre suit le choix des champs
de sélection, qui persiste par utilisateur, et le préfixe de type varie d'un
champ à l'autre (mesuré live le 2026-09-21 sur ``SNWD_PD`` : ``txtI1-LOW``
pour ``NODE_KEY`` mais ``ctxtI2-LOW`` pour ``PRODUCT_ID``). Un localisateur
gravé dans une couche métier est donc faux de deux façons à la fois, et il le
devient en SILENCE : l'écran répond, un autre critère se remplit, et la
lecture qui suit rend des lignes parfaitement lisibles qui ne sont pas celles
qu'on a demandées.

Ce que l'écran donne et qui rend la dérivation possible : SE16 affiche en
libellé le nom TECHNIQUE du champ (``PRODUCT_ID``) et non son texte court
traduit, donc l'appariement reste indépendant de la langue (convention 3).

L'appariement est géométrique : un libellé est sur la même LIGNE que son champ
et à sa GAUCHE. Le recouvrement vertical est préféré à une tolérance en
pixels, parce qu'il s'adapte tout seul à l'échelle de rendu : la leçon du
2026-09-21 sur le canal écran, où des distances gravées en pixels ont cessé de
rattacher le moindre libellé dès que la session a changé de densité.

Toute ambiguïté est REMONTÉE avec ses candidats, jamais tranchée en silence :
un premier-match arbitraire ici se paierait par un filtre appliqué au mauvais
champ, c'est-à-dire par un résultat faux et plausible.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

# Un libellé d'écran de sélection SE16 qui est un nom de champ : majuscules,
# chiffres et soulignés. Les champs de portée générale de l'écran (le nombre
# maximal de résultats) portent une phrase traduite et sont ainsi écartés sans
# qu'on ait à les connaître.
TECHNICAL_LABEL = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Le segment final d'un SID de critère : un préfixe de type quelconque
# (``txt``, ``ctxt``...), ``I``, le rang, puis la borne basse. Seule la borne
# BASSE est retenue : c'est celle d'une sélection par égalité, la seule que ce
# contrat promet (même périmètre que le keyword du canal écran).
SELECTION_FIELD = re.compile(r"^[A-Za-z]*I(\d+)-LOW$")

# Marge d'un pixel sur la frontière horizontale : les rectangles viennent d'un
# arrondi côté navigateur, et un libellé qui finit pile au bord de son champ
# ne doit pas se retrouver écarté pour une unité de rendu.
_EDGE_TOLERANCE = 1.0


def is_technical_label(text: object) -> bool:
    """Ce texte est-il un nom TECHNIQUE de champ (et non un libellé traduit) ?"""
    return bool(TECHNICAL_LABEL.match(str(text or "").strip()))


def selection_field_rank(sid: object) -> int | None:
    """Le rang ``N`` d'un SID de critère ``I<N>-LOW``, ou ``None``.

    Le rang n'est pas une donnée à exploiter (il change avec le choix des
    champs de sélection) : il sert à reconnaître un critère parmi les autres
    champs de l'écran, rien de plus.
    """
    segment = str(sid or "").rsplit("/", 1)[-1]
    found = SELECTION_FIELD.match(segment)
    return int(found.group(1)) if found else None


def _rectangle(item: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    """``(haut, bas, gauche, droite)`` d'une entrée de sonde, ou ``None`` quand
    la géométrie manque : une entrée illisible est ignorée, jamais devinée."""
    try:
        top = float(item.get("top"))          # type: ignore[arg-type]
        bottom = float(item.get("bottom"))    # type: ignore[arg-type]
        left = float(item.get("left"))        # type: ignore[arg-type]
        right = float(item.get("right"))      # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return (top, bottom, left, right)


def _overlaps_vertically(label: tuple[float, float, float, float],
                         field: tuple[float, float, float, float]) -> bool:
    """Les deux rectangles partagent-ils une bande horizontale ? C'est le test
    « même ligne », et il est auto-échelonné : il ne suppose aucune distance."""
    return min(label[1], field[1]) - max(label[0], field[0]) > 0


def _contains(outer: tuple[float, float, float, float],
              inner: tuple[float, float, float, float]) -> bool:
    """Le rectangle ``outer`` englobe-t-il ``inner`` (à une unité de rendu) ?"""
    return (outer[0] <= inner[0] + _EDGE_TOLERANCE
            and outer[1] >= inner[1] - _EDGE_TOLERANCE
            and outer[2] <= inner[2] + _EDGE_TOLERANCE
            and outer[3] >= inner[3] - _EDGE_TOLERANCE)


def drop_accelerator_fragments(
    labels: list[tuple[str, tuple[float, float, float, float]]],
) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Retire les FRAGMENTS d'un libellé, en gardant le libellé entier.

    Une release du WebGUI isole le caractère d'ACCÉLÉRATEUR clavier d'un
    libellé dans son propre élément (mesuré le 2026-09-21 : ``CATEGORY`` se
    rend en un parent ``CATEGORY`` contenant une feuille ``C``), là où l'autre
    rend le libellé d'un bloc. Sans ce tri, l'écran paraît porter des champs
    d'un caractère, et la barre de menus en ajoute autant qu'elle a
    d'entrées : sur la 2023, quatre critères se disputaient un champ nommé
    « C ».

    Le critère est structurel et non typographique : un fragment est
    géométriquement INCLUS dans son libellé ET son texte y est contenu. Deux
    libellés distincts, eux, ne s'englobent jamais, donc aucun vrai libellé ne
    peut être retiré par cette règle.
    """
    gardes: list[tuple[str, tuple[float, float, float, float]]] = []
    for texte, zone in labels:
        fragment = any(
            len(autre) > len(texte)
            and texte in autre
            and _contains(englobant, zone)
            for autre, englobant in labels
        )
        if not fragment:
            gardes.append((texte, zone))
    return gardes


def selection_criteria(labels: Iterable[Mapping[str, Any]],
                       fields: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """Carte ``{CHAMP_TECHNIQUE: SID}`` des critères d'un écran de sélection.

    ``labels`` : les textes visibles de l'écran avec leur rectangle.
    ``fields`` : les champs de saisie avec leur SID et leur rectangle.

    Un critère sans libellé technique à sa gauche est ignoré (l'écran en porte
    d'autres que les critères de table). Deux libellés candidats à la même
    distance, ou un même nom de champ revendiqué par deux critères, lèvent une
    ``ValueError`` nommant les candidats.
    """
    brutes: list[tuple[str, tuple[float, float, float, float]]] = []
    for entry in labels or ():
        texte = str(entry.get("text", "") or "").strip()
        rectangle = _rectangle(entry)
        if rectangle is not None and is_technical_label(texte):
            brutes.append((texte, rectangle))
    etiquettes = drop_accelerator_fragments(brutes)

    # Deux relevés, et la distinction compte. `criteres_zones` porte les seuls
    # critères, ceux qu'on va apparier. `champs_zones` porte TOUS les champs de
    # l'écran, critères ou non : c'est contre eux que se juge l'interposition
    # ci-dessous, parce qu'un libellé appartient au premier champ à sa droite
    # quelle que soit la NATURE de ce champ. Ne considérer que les critères
    # laisserait passer le cas réellement silencieux, celui où le propriétaire
    # légitime du libellé n'est pas un critère : la garde de doublon ne le voit
    # pas, et la carte nomme alors un critère d'après le libellé d'un autre.
    criteres_zones: list[tuple[str, tuple[float, float, float, float]]] = []
    champs_zones: list[tuple[float, float, float, float]] = []
    for entry in fields or ():
        sid = str(entry.get("sid", "") or "").strip()
        zone = _rectangle(entry)
        if zone is None:
            continue
        champs_zones.append(zone)
        if selection_field_rank(sid) is not None:
            criteres_zones.append((sid, zone))

    criteres: dict[str, str] = {}
    origine: dict[str, str] = {}
    for sid, zone in criteres_zones:
        candidats = [(texte, rectangle) for texte, rectangle in etiquettes
                     if _overlaps_vertically(rectangle, zone)
                     and rectangle[3] <= zone[2] + _EDGE_TOLERANCE]
        if not candidats:
            continue
        plus_proche = max(candidats, key=lambda item: item[1][3])
        # Un libellé appartient au PREMIER critère à sa droite, et à lui seul.
        # Sans cette règle, un critère dépourvu de libellé propre adopte celui
        # d'un voisin : les candidats n'étant bornés par aucune distance, le
        # « plus proche à gauche » peut se trouver très loin, et la garde de
        # doublon ci-dessous ne le voit que si le propriétaire légitime
        # revendique AUSSI ce libellé, donc seulement quand les deux critères
        # partagent une ligne. C'était la seule mauvaise carte qui passait sans
        # protester, c'est-à-dire exactement ce que cette dérivation existe
        # pour empêcher (réserve de la revue indépendante du 2026-09-21).
        #
        # La règle est STRUCTURELLE et non métrique : elle ne suppose aucune
        # distance, donc elle survit à un changement d'échelle de rendu, là où
        # un seuil en pixels a déjà cessé de rattacher le moindre libellé dès
        # que la densité d'affichage a changé (leçon du 2026-09-21, canal
        # écran). Un critère dont le libellé appartient à un autre est traité
        # comme un critère SANS libellé, donc ignoré : l'appelant reçoit alors
        # la liste de ce que l'écran porte vraiment, jamais un nom emprunté.
        interpose = any(
            _overlaps_vertically(plus_proche[1], autre)
            and plus_proche[1][3] <= autre[2] + _EDGE_TOLERANCE
            and autre[2] < zone[2] - _EDGE_TOLERANCE
            for autre in champs_zones
        )
        if interpose:
            continue
        # Dédoublonné par TEXTE : le même libellé est rendu à plusieurs
        # niveaux du DOM (un `div`, son `span`, son `label`), donc trois
        # candidats au même bord droit. Ce n'est pas une ambiguïté, c'est un
        # seul libellé vu trois fois ; seuls des textes DISTINCTS à égale
        # distance en sont une.
        exaequo = {texte for texte, rectangle in candidats
                   if abs(rectangle[3] - plus_proche[1][3]) <= _EDGE_TOLERANCE}
        if len(exaequo) > 1:
            raise ValueError(
                "Critère %s : plusieurs libellés techniques sont à la même "
                "distance (%s). L'écran n'est pas appariable en l'état : "
                "percevoir la page avant de filtrer."
                % (sid, ", ".join(sorted(exaequo))))
        nom = plus_proche[0]
        if nom in criteres:
            raise ValueError(
                "Le champ %s est revendiqué par deux critères (%s et %s) : "
                "l'écran de sélection n'est pas appariable en l'état."
                % (nom, origine[nom], sid))
        criteres[nom] = sid
        origine[nom] = sid
    return dict(sorted(criteres.items()))


def missing_criterion_message(field: str, criteria: Mapping[str, str]) -> str:
    """Le message d'un critère absent, qui LISTE ce que l'écran porte vraiment.

    Un nom de champ absent est le plus souvent un champ qui n'a pas été retenu
    dans le choix des champs de sélection (réglage persistant par utilisateur),
    pas une faute de frappe : la liste tranche entre les deux sans retourner
    sur le système.
    """
    connus = ", ".join(sorted(criteria)) or "aucun"
    return ("Aucun critère de sélection %s sur l'écran courant. Critères "
            "présents : %s." % (field, connus))
