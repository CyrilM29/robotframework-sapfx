"""Ce qu'une cellule d'ALV rend vraiment, logique pure.

Une grille SAP GUI rend du TEXTE, et tout texte n'est pas une donnée. Deux
formes, mesurées le 2026-09-14 sur ABAP Platform 2023 en lisant le rapport des
comptes standards, trompent une lecture naïve et demandent chacune un
traitement opposé.

**Un code d'icône n'est pas une valeur.** La colonne de verrouillage de ce
rapport rend ``@07@`` pour tout compte existant et une chaîne vide pour les
autres. Ce n'est ni un booléen, ni un libellé : c'est l'identifiant d'une
icône, que le client résout en image. Le lire comme une donnée donne une
colonne de `@07@` dont on ne sait rien, et la comparer à un booléen d'un autre
canal échoue toujours. En revanche il a une qualité précieuse : il est
INDÉPENDANT DE LA LANGUE, là où le libellé qu'il remplace ne l'est pas.

**Un libellé d'état est une traduction.** La colonne de statut de mot de passe
du même rapport rend ``Exists; Password not trivial.`` en anglais, et autre
chose ailleurs. La convention du dépôt interdit d'asserter dessus : cette
colonne se RAPPORTE, elle ne se juge pas.

La conséquence pratique est la méthode de croisement que ce module sert : une
icône ne s'interprète pas seule, elle s'interprète en la confrontant, sur le
périmètre où les deux canaux se recouvrent, à une valeur dont le sens est
établi. L'interprétation ainsi ÉTABLIE peut ensuite s'appliquer au périmètre
que seul l'écran atteint.

Typé, sans dépendance.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Optional

__all__ = [
    "ICON_PATTERN",
    "icon_code",
    "is_icon",
    "cell_is_data",
    "distinct_icons",
    "establish_icon_meaning",
]

#: La forme d'un identifiant d'icône dans une cellule d'ALV : ``@07@``,
#: ``@5B\\QTexte@``… Seule la partie identifiante est retenue.
ICON_PATTERN = re.compile(r"^@([0-9A-Za-z]{1,4})(?:\\\\Q.*)?@$")


def icon_code(value: Any) -> Optional[str]:
    """Rend l'identifiant d'icône d'une cellule, ou ``None`` si ce n'en est
    pas une.

    ``@07@`` rend ``"07"``. Une valeur ordinaire rend ``None``, ce qui permet
    d'écrire ``if icon_code(cell) is None`` pour distinguer une donnée d'un
    pictogramme sans jamais comparer à une chaîne littérale.
    """
    texte = str(value or "").strip()
    trouve = ICON_PATTERN.match(texte)
    return trouve.group(1).upper() if trouve else None


def is_icon(value: Any) -> bool:
    """Dit si la cellule porte une icône plutôt qu'une donnée."""
    return icon_code(value) is not None


def cell_is_data(value: Any) -> bool:
    """Dit si la cellule porte quelque chose d'exploitable comme une DONNÉE.

    Faux pour une icône et pour une cellule vide. C'est la garde à poser avant
    toute comparaison entre deux canaux : une colonne d'icônes confrontée à un
    booléen échoue systématiquement, et le message d'échec accuse alors le
    système au lieu de la lecture.
    """
    texte = str(value or "").strip()
    return bool(texte) and not is_icon(texte)


def distinct_icons(rows: Iterable[Mapping[str, Any]], column: str
                   ) -> dict[str, int]:
    """Compte les identifiants d'icône distincts d'une colonne.

    Une colonne qui ne porte qu'UN seul code ne discrimine rien : c'est le cas
    de la colonne de verrouillage sur la cible, où tout compte existant porte
    le même pictogramme. Le savoir évite de croire qu'on a mesuré un état.
    """
    comptes: dict[str, int] = {}
    for ligne in rows:
        code = icon_code(ligne.get(column))
        if code is not None:
            comptes[code] = comptes.get(code, 0) + 1
    return dict(sorted(comptes.items()))


def establish_icon_meaning(rows: Iterable[Mapping[str, Any]], column: str,
                           key_columns: Iterable[str],
                           known: Mapping[str, bool]) -> dict[str, Any]:
    """ÉTABLIT ce que veut dire un code d'icône, en le confrontant à une
    vérité connue par ailleurs.

    ``rows`` est le relevé d'écran, ``column`` la colonne d'icônes,
    ``key_columns`` les colonnes qui identifient une ligne (par exemple
    mandant et utilisateur), et ``known`` une carte ``{clé: booléen}`` mesurée
    par un autre canal sur le périmètre où les deux se recouvrent.

    Rend ``{"meanings", "ambiguous", "unmatched", "coverage",
    "discriminating", "not_discriminating"}`` où ``meanings`` associe chaque
    code au booléen qu'il représente, quand le recoupement est CONCLUANT.

    Deux replis sûrs, et le second a été ajouté sur réserve de revue.

    Un code qui correspond aux deux valeurs booléennes selon les lignes est
    rendu ``ambiguous`` et n'est JAMAIS traduit. Interpréter un pictogramme de
    travers dans un rapport de sécurité est pire que ne pas l'interpréter,
    puisque la traduction sera lue comme un fait.

    Un recoupement SANS CONTRASTE ne conclut rien non plus : si toutes les
    lignes recoupées portent le même code et le même booléen, « ce code
    signifie cet état » est indiscernable de « ce code signifie simplement que
    la ligne existe ». Mesuré sur la cible : deux lignes, un code, un état, et
    l'hypothèse concurrente était parfaitement soutenue par les lignes à
    cellule vide, qui sont exactement les comptes inexistants. Il faut donc
    deux codes distincts, ou les deux valeurs booléennes, pour que
    ``meanings`` soit rempli ; sinon ``discriminating`` vaut faux et les codes
    vus sont rendus dans ``not_discriminating``.

    C'est la méthode qui permet d'appliquer ensuite l'interprétation au
    périmètre que seul l'écran atteint, là où aucune vérité de référence n'est
    disponible.
    """
    colonnes = [str(c) for c in key_columns]
    observations: dict[str, set[bool]] = {}
    non_apparies: list[str] = []
    apparies = 0
    for ligne in rows:
        cle = "/".join(str(ligne.get(c, "")).strip() for c in colonnes)
        code = icon_code(ligne.get(column))
        if code is None:
            continue
        if cle not in known:
            non_apparies.append(cle)
            continue
        apparies += 1
        observations.setdefault(code, set()).add(bool(known[cle]))

    ambigus = sorted(code for code, valeurs in observations.items()
                     if len(valeurs) > 1)
    # Le CONTRASTE, sans lequel un recoupement ne conclut rien, et c'est une
    # réserve de revue indépendante : si toutes les lignes recoupées portent
    # le même code ET le même booléen, « ce code signifie cet état » est
    # indiscernable de « ce code signifie simplement que la ligne existe ».
    # Mesuré sur la cible : deux lignes, un seul code, un seul état. Il faut
    # donc soit deux codes distincts, soit les deux valeurs booléennes
    # observées, pour qu'un sens soit ÉTABLI plutôt que supposé.
    etats_vus = {v for valeurs in observations.values() for v in valeurs}
    discriminant = len(observations) > 1 or len(etats_vus) > 1
    meanings = ({code: next(iter(valeurs)) for code, valeurs in
                 observations.items() if len(valeurs) == 1}
                if discriminant else {})
    return {
        "meanings": dict(sorted(meanings.items())),
        "ambiguous": ambigus,
        "unmatched": sorted(set(non_apparies)),
        "coverage": apparies,
        "discriminating": discriminant,
        # Les codes observés sans contraste suffisant : ils ne sont PAS
        # traduits, et le dire explicitement vaut mieux qu'une carte vide dont
        # on ne saurait pas si elle signifie « rien vu » ou « rien conclu ».
        "not_discriminating": ([] if discriminant
                               else sorted(observations.keys())),
    }
