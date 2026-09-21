"""D'où vient la valeur d'un paramètre de profil SAP, logique pure.

Un audit de configuration lit la valeur EFFECTIVE d'un paramètre et s'arrête
là. C'est ce que rend le canal RFC, et cela suffit pour dire si un système est
durci. Cela ne suffit pas pour dire **pourquoi**, et la différence compte
davantage qu'il n'y paraît.

Mesuré le 2026-09-14 sur ABAP Platform 2023 (release 758, kernel 793) en
croisant l'écran du rapport de paramètres avec le canal RFC : sur les **42**
paramètres de sécurité audités par les campagnes du dépôt, **39** portent leur
valeur par DÉFAUT, 3 sont déclarés dans le profil d'instance et **aucun n'y
est modifié** (les trois y répètent exactement le défaut). Le durcissement
supérieur de cette release, que les campagnes précédentes constataient sans
pouvoir l'expliquer, n'est donc pas un réglage d'exploitant.

D'où la distinction que porte ce module entre « posé dans le profil » et
« modifié par le profil » : seule la seconde désigne une décision humaine, et
c'est un run qui l'a imposée en démentant une première lecture manuelle trop
rapide.

**Limite de ce que la colonne permet d'affirmer**, et elle vaut d'être dite :
le rapport donne une valeur « par défaut » sans préciser si elle est compilée
dans le noyau ou héritée d'un profil par défaut. Ce module parle donc de
l'origine PROFIL D'INSTANCE contre DÉFAUT, et laisse à l'appelant le soin de
ne pas surinterpréter le second terme.

**Pourquoi cette distinction change la lecture d'une dérive.** Une sentinelle
qui surveille ces valeurs surveille en réalité le NOYAU. Un écart y apparaîtra
lors d'une montée de version, pas parce que quelqu'un a modifié le système, et
le remède n'est pas le même. Inversement, un paramètre de sécurité qui
APPARAÎT dans le profil est une décision humaine, et c'est exactement ce qu'un
audit veut voir.

Le second piège est un piège de MESURE, pas d'interprétation : la colonne de
valeur de profil du rapport est tronquée à 60 caractères sans le dire. Comparer
cette valeur à celle du canal RFC, qui est complète, fabrique un écart sur
toute valeur longue. Treize paramètres de la cible sont exactement à cette
longueur.

Typé, sans dépendance : les E/S vivent dans la couche qui lit l'écran.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

__all__ = [
    "PROFILE_VALUE_WIDTH",
    "ORIGINS",
    "classify_parameter_origin",
    "compare_channels",
    "discriminating_parameter_names",
    "proven_truncations",
    "summarize_origins",
    "looks_truncated",
    "truncated_profile_names",
]

#: La largeur de la colonne de valeur de profil du rapport, mesurée sur la
#: cible : au-delà, la valeur est coupée SANS avertissement. La colonne de
#: valeur par défaut, elle, tient 128 caractères.
PROFILE_VALUE_WIDTH = 60

#: Les origines possibles d'une valeur effective.
ORIGINS = ("profile", "kernel", "divergent", "not_measured")


def looks_truncated(value: Any, width: int = PROFILE_VALUE_WIDTH) -> bool:
    """Dit si une valeur lue à l'écran est SUSPECTE de troncature.

    Le critère est la longueur exacte : une valeur qui occupe très précisément
    la largeur de la colonne a probablement été coupée. C'est un soupçon, pas
    une preuve, et c'est volontaire : il n'existe aucun marqueur de troncature
    dans la donnée rendue, donc une valeur légitimement longue de 60 caractères
    est indiscernable d'une valeur coupée.

    L'employer pour ÉCARTER une comparaison plutôt que pour la déclarer
    fausse : comparer une valeur peut-être tronquée à une valeur complète
    fabrique un écart qui n'existe pas.
    """
    return len(str(value or "").strip()) >= int(width)


def classify_parameter_origin(name: str, effective: Any, profile: Any,
                              default: Any,
                              width: int = PROFILE_VALUE_WIDTH
                              ) -> dict[str, Any]:
    """Dit d'où vient la valeur effective d'UN paramètre.

    ``effective`` est la valeur mesurée par le canal sans écran, ``profile``
    et ``default`` les deux colonnes du rapport d'écran. Rend
    ``{"name", "origin", "effective", "profile", "default", "truncated",
    "comparable"}``.

    ``origin`` vaut :

    - ``profile`` : le profil d'instance porte une valeur et l'effectif la
      suit. C'est une décision humaine, donc ce qu'un audit veut voir ;
    - ``kernel`` : le profil ne porte rien et l'effectif suit le défaut. La
      valeur vient du noyau, et une dérive y viendra d'une montée de version,
      pas d'une modification du système ;
    - ``divergent`` : l'effectif ne suit ni l'un ni l'autre. À regarder, sauf
      si la valeur de profil est suspecte de troncature, auquel cas la
      comparaison n'est simplement pas probante ;
    - ``not_measured`` : l'effectif n'a pas été lu.

    ``comparable`` est faux quand la valeur de profil atteint la largeur de
    colonne : la comparaison est alors ÉCARTÉE plutôt que tranchée, parce
    qu'une valeur coupée comparée à une valeur complète produit un faux écart.
    C'est le cas de treize paramètres sur la cible, dont aucun n'est de
    sécurité, mais la garde ne dépend pas de cette chance.
    """
    nom = str(name or "").strip()
    if not nom:
        raise ValueError("Un paramètre doit porter un nom.")
    eff = None if effective is None else str(effective).strip()
    prof = str(profile or "").strip()
    defa = str(default or "").strip()
    tronquee = bool(prof) and looks_truncated(prof, width)

    if eff is None:
        origine = "not_measured"
    elif prof:
        origine = "profile" if eff == prof else "divergent"
    elif eff == defa:
        origine = "kernel"
    else:
        origine = "divergent"

    # Une valeur de profil coupée ne peut pas être confrontée à une valeur
    # complète : on refuse de conclure plutôt que d'inventer un écart.
    if origine == "divergent" and tronquee and eff is not None:
        origine = "profile" if eff.startswith(prof) else "divergent"

    return {
        "name": nom,
        "origin": origine,
        "effective": eff,
        "profile": prof or None,
        "default": defa or None,
        "truncated": tronquee,
        "comparable": not tronquee,
        # « Posé dans le profil » n'est pas « modifié par le profil », et la
        # distinction porte tout le sens d'un audit. Mesuré sur la cible : les
        # trois seuls paramètres de sécurité déclarés dans le profil y portent
        # EXACTEMENT la valeur du défaut (deux chemins de fichiers de contrôle
        # d'accès et un indicateur de compatibilité), donc aucun ne durcit ni
        # n'affaiblit quoi que ce soit. Sans ce champ, ils se lisent comme
        # trois décisions humaines de durcissement, alors qu'ils ne changent
        # rien.
        "profile_changes_value": bool(prof) and prof != defa,
    }


def summarize_origins(fiches: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Résume un lot de classements : combien viennent du profil, du noyau,
    et lesquels divergent.

    Les listes sont triées, donc deux relevés identiques produisent le même
    résumé, ce dont dépend toute comparaison entre deux passages.

    ``profile_backed`` est la liste qui intéresse un audit : ce sont les
    paramètres qu'une décision humaine a posés. Sur la cible elle est VIDE
    pour le périmètre de sécurité, et c'est le résultat.
    """
    retenues = [dict(f) for f in fiches]
    par_origine: dict[str, list[str]] = {}
    for fiche in retenues:
        par_origine.setdefault(str(fiche.get("origin")), []).append(
            str(fiche.get("name")))
    return {
        "total": len(retenues),
        "by_origin": {k: sorted(v) for k, v in sorted(par_origine.items())},
        "profile_backed": sorted(par_origine.get("profile", [])),
        "kernel_backed": sorted(par_origine.get("kernel", [])),
        "divergent": sorted(par_origine.get("divergent", [])),
        "not_comparable": sorted(f["name"] for f in retenues
                                 if not f.get("comparable")),
        # La liste qui compte vraiment pour un audit : les paramètres que le
        # profil MODIFIE, par opposition à ceux qu'il se contente de répéter.
        "profile_changing": sorted(f["name"] for f in retenues
                                   if f.get("profile_changes_value")),
        "profile_redundant": sorted(
            f["name"] for f in retenues
            if f.get("profile") and not f.get("profile_changes_value")),
    }


def truncated_profile_names(screen_rows: Iterable[Mapping[str, Any]],
                            name_key: str = "NAME",
                            profile_key: str = "USER_VALUE",
                            width: int = PROFILE_VALUE_WIDTH) -> list[str]:
    """Les paramètres dont la valeur de profil atteint la largeur de colonne,
    donc SUSPECTS de troncature.

    Promu ici depuis une compréhension écrite dans une suite (convention 12) :
    c'est une capacité, et la largeur y était dupliquée en dur, de sorte qu'un
    changement de l'une des deux copies aurait rendu l'autre incohérente sans
    que rien ne le dise.
    """
    return sorted({
        str(r.get(name_key, "")).strip() for r in screen_rows
        if looks_truncated(r.get(profile_key), width)
        and str(r.get(name_key, "")).strip()})


def proven_truncations(screen_rows: Iterable[Mapping[str, Any]],
                       effective: Mapping[str, Any], name_key: str = "NAME",
                       profile_key: str = "USER_VALUE") -> list[str]:
    """Les paramètres dont la troncature de la colonne de profil est PROUVÉE
    par l'autre canal, et non seulement soupçonnée.

    La preuve est double : la valeur complète mesurée sans écran doit
    COMMENCER par la valeur lue à l'écran, et être strictement plus longue.
    Une valeur simplement longue ne suffit donc pas, et une valeur différente
    non plus.

    Sans cette fonction, un scénario qui veut « prouver la troncature » ne
    peut que relire son propre critère de sélection (la longueur), ce qui ne
    peut pas échouer. Le distinguo a été imposé par une revue indépendante.
    """
    par_nom = {str(r.get(name_key, "")).strip(): str(r.get(profile_key, "")
                                                     or "").strip()
               for r in screen_rows}
    prouves = []
    for nom, valeur in effective.items():
        ecran = par_nom.get(str(nom).strip())
        complete = str(valeur or "")
        if not ecran:
            continue
        if complete.startswith(ecran) and len(complete) > len(ecran):
            prouves.append(str(nom).strip())
    return sorted(prouves)


def discriminating_parameter_names(screen_rows: Iterable[Mapping[str, Any]],
                                   name_key: str = "NAME",
                                   profile_key: str = "USER_VALUE",
                                   default_key: str = "DEFAULT_VALUE",
                                   limit: Optional[int] = None) -> list[str]:
    """Les paramètres dont la valeur de profil DIFFÈRE du défaut, donc les
    seuls qui puissent servir de témoins.

    Un paramètre dont le profil répète le défaut ne discrimine rien : quelle
    que soit la source que suit la valeur effective, elle est la même. Une
    contre-épreuve bâtie sur de tels paramètres ne prouverait donc rien, et
    c'est la raison d'être de ce sélecteur.
    """
    noms = [str(r.get(name_key, "")).strip() for r in screen_rows
            if str(r.get(profile_key, "") or "").strip()
            and str(r.get(profile_key, "") or "").strip()
            != str(r.get(default_key, "") or "").strip()
            and str(r.get(name_key, "")).strip()]
    ordonnes = sorted(set(noms))
    return ordonnes[:int(limit)] if limit else ordonnes


def compare_channels(screen_rows: Iterable[Mapping[str, Any]],
                     effective: Mapping[str, Any],
                     names: Optional[Iterable[str]] = None,
                     name_key: str = "NAME", profile_key: str = "USER_VALUE",
                     default_key: str = "DEFAULT_VALUE",
                     width: int = PROFILE_VALUE_WIDTH) -> dict[str, Any]:
    """Croise un relevé d'ÉCRAN et les valeurs effectives d'un autre canal.

    ``screen_rows`` est le rapport de paramètres tel que la grille le rend,
    ``effective`` la carte ``{nom: valeur}`` mesurée sans écran. ``names``
    restreint le croisement au périmètre voulu ; un nom absent du rapport
    d'écran est rendu ``missing_from_screen`` plutôt qu'omis, parce qu'une
    absence de mesure n'est pas une absence de problème.

    C'est ce croisement qui répond à « ce durcissement est-il un réglage ou un
    défaut », question à laquelle aucun des deux canaux ne répond seul.
    """
    par_nom = {str(r.get(name_key, "")).strip(): r for r in screen_rows}
    vises = [str(n).strip() for n in (names or effective.keys())]
    fiches = []
    absents = []
    for nom in vises:
        ligne = par_nom.get(nom)
        if ligne is None:
            absents.append(nom)
            continue
        fiches.append(classify_parameter_origin(
            nom, effective.get(nom), ligne.get(profile_key),
            ligne.get(default_key), width=width))
    resume = summarize_origins(fiches)
    resume["missing_from_screen"] = sorted(absents)
    resume["entries"] = sorted(fiches, key=lambda f: f["name"])
    return resume
