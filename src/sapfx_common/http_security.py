"""Ce qu'une réponse HTTP révèle de la posture de sécurité, logique pure.

Le troisième canal d'une campagne SAP n'a ni écran ni module fonction : il a
des en-têtes. Son intérêt n'est pas de lire une configuration de plus, c'est
d'observer l'EFFET de celle que les deux autres canaux déclarent.

Le cas qui a motivé ce module, mesuré le 2026-09-14 sur ABAP Platform 2023
(release 758) : le paramètre qui pilote le drapeau ``HttpOnly`` des cookies
vaut ``3``, valeur que le canal RFC lit et que l'écran confirme venir du
noyau. Sur le fil, **aucun des trois cookies de session ne porte ce drapeau**,
ticket d'authentification compris, et aucun ne porte ``Secure`` même servi en
HTTPS.

Deux enseignements, et le second est le plus important.

1. Un audit qui s'arrête à la valeur du paramètre conclut que les cookies sont
   protégés. Ils ne le sont pas.
2. **La valeur d'un paramètre de sécurité n'est pas un curseur.** On lit
   volontiers ``3`` comme « plus durci que ``0`` ». L'observation dit que non :
   quelle que soit la sémantique exacte que SAP donne à cette échelle, ``3``
   ne produit pas de drapeau ``HttpOnly`` sur cette cible. Un contrôle écrit
   « au moins 3 » serait donc vert et faux. Seule l'observation tranche, et
   c'est précisément ce qu'aucun des deux autres canaux ne peut faire.

`confront_declared_and_observed` encode cette confrontation et garde
`undetermined` distinct de tout verdict : une observation absente ne vaut
jamais une conformité, sur le patron du repli sûr des modules voisins.

Typé, sans dépendance : les E/S vivent dans le mixin qui parle HTTP.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

__all__ = [
    "SECURITY_HEADERS",
    "parse_set_cookie",
    "summarize_cookie_security",
    "assess_security_headers",
    "confront_declared_and_observed",
]

#: Les en-têtes de réponse dont l'ABSENCE est un constat de posture. Aucun
#: n'est obligatoire, tous sont des protections de navigateur, et une cible
#: qui n'en pose aucun laisse ces protections à la charge de ce qui est devant.
SECURITY_HEADERS = (
    "strict-transport-security",
    "content-security-policy",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
)

#: Les attributs d'un cookie dont la présence se constate sans ambiguïté.
_FLAG_ATTRIBUTES = ("httponly", "secure")


def parse_set_cookie(header: Any) -> dict[str, Any]:
    """Décompose UN en-tête ``Set-Cookie`` en ``{"name", "httponly",
    "secure", "samesite", "path", "domain"}``.

    Accepte aussi une fiche DÉJÀ décomposée (un mapping portant au moins
    ``name``), pour qu'un appelant qui tient un bocal à cookies n'ait pas à
    reconstruire un en-tête artificiel afin de le faire re-parser.

    La VALEUR du cookie n'est jamais rendue : ce module constate des
    propriétés de transport, il ne manipule pas de jeton de session. Un
    identifiant de session recopié dans un rapport ou un artefact serait un
    secret exposé, et l'artefact est fait pour être committé.
    """
    if isinstance(header, Mapping):
        nom_direct = str(header.get("name", "")).strip()
        if not nom_direct:
            raise ValueError("Une fiche de cookie doit porter un nom.")
        return {
            "name": nom_direct,
            "httponly": bool(header.get("httponly")),
            "secure": bool(header.get("secure")),
            "samesite": header.get("samesite") or None,
            "path": header.get("path") or None,
            "domain": header.get("domain") or None,
        }
    brut = str(header or "").strip()
    if not brut:
        raise ValueError("Un en-tête Set-Cookie ne peut pas être vide.")
    morceaux = [m.strip() for m in brut.split(";")]
    nom = morceaux[0].split("=", 1)[0].strip()
    if not nom:
        raise ValueError(f"En-tête Set-Cookie sans nom de cookie : {brut[:40]!r}")
    bas = [m.lower() for m in morceaux[1:]]
    fiche: dict[str, Any] = {"name": nom}
    for attribut in _FLAG_ATTRIBUTES:
        fiche[attribut] = any(m == attribut for m in bas)
    fiche["samesite"] = next(
        (m.split("=", 1)[1].strip() for m in bas if m.startswith("samesite=")),
        None)
    for cle in ("path", "domain"):
        fiche[cle] = next(
            (m.split("=", 1)[1].strip() for m in bas
             if m.startswith(cle + "=")), None)
    return fiche


def summarize_cookie_security(headers: Iterable[Any],
                              over_https: bool = False) -> dict[str, Any]:
    """Résume la posture de transport des cookies posés par une réponse.

    Rend ``{"total", "names", "without_httponly", "without_secure",
    "without_samesite", "all_protected"}``, les listes étant triées et ne
    portant que des NOMS.

    ``over_https`` indique si la réponse a été servie en HTTPS. L'absence de
    ``Secure`` ne se juge pas de la même façon sur un canal en clair, où le
    drapeau n'aurait de toute façon rien à protéger : le résumé le RAPPORTE
    dans les deux cas et laisse l'appelant décider, parce qu'exiger ``Secure``
    d'un banc servi en HTTP rendrait une suite rouge à vie.
    """
    fiches = [parse_set_cookie(h) for h in headers]
    return {
        "total": len(fiches),
        "over_https": bool(over_https),
        "names": sorted(f["name"] for f in fiches),
        "without_httponly": sorted(f["name"] for f in fiches
                                   if not f["httponly"]),
        "without_secure": sorted(f["name"] for f in fiches if not f["secure"]),
        "without_samesite": sorted(f["name"] for f in fiches
                                   if not f["samesite"]),
        "all_protected": bool(fiches) and all(f["httponly"] for f in fiches),
        "cookies": sorted(fiches, key=lambda f: f["name"]),
    }


def assess_security_headers(headers: Mapping[str, Any],
                            expected: Optional[Iterable[str]] = None
                            ) -> dict[str, Any]:
    """Dit lesquels des en-têtes de sécurité la réponse porte, et lesquels
    manquent.

    La comparaison est insensible à la casse : un en-tête HTTP l'est, et une
    lecture sensible à la casse déclarerait absent un en-tête présent.
    """
    vus = {str(k).strip().lower(): str(v) for k, v in headers.items()}
    attendus = [str(h).strip().lower()
                for h in (expected if expected is not None else SECURITY_HEADERS)]
    presents = [h for h in attendus if h in vus]
    return {
        "present": sorted(presents),
        "missing": sorted(h for h in attendus if h not in vus),
        "values": {h: vus[h] for h in sorted(presents)},
        "count_present": len(presents),
        "count_expected": len(attendus),
    }


def confront_declared_and_observed(control: str, declared: Any,
                                   observed: Optional[bool],
                                   expectation: Optional[bool] = True
                                   ) -> dict[str, Any]:
    """Confronte ce qu'un paramètre DÉCLARE et ce que le fil MONTRE.

    ``declared`` est la valeur lue par un canal de configuration (elle est
    rapportée telle quelle, jamais interprétée comme un niveau), ``observed``
    le fait constaté sur la réponse HTTP, et ``expectation`` l'effet qu'un
    lecteur du paramètre s'attendrait à voir.

    Rend ``{"control", "declared", "observed", "verdict", "note"}`` où
    ``verdict`` vaut :

    - ``confirmed`` : l'effet attendu est observé ;
    - ``declared_without_effect`` : le paramètre est posé et l'effet n'est pas
      là. C'est le faux positif de conformité que ce module existe pour
      attraper, et le cas mesuré sur la cible ;
    - ``effect_without_declaration`` : l'effet est là sans que le paramètre
      l'annonce, donc quelque chose d'autre le produit ;
    - ``undetermined`` : l'observation n'a pas eu lieu. JAMAIS une conformité.

    **La valeur déclarée n'est pas interprétée comme un niveau**, et c'est
    délibéré : lire une échelle numérique comme un curseur de durcissement est
    exactement l'erreur que l'observation a démentie ici.
    """
    nom = str(control or "").strip()
    if not nom:
        raise ValueError("Un contrôle doit porter un nom.")
    valeur = None if declared is None else str(declared).strip()
    attendu = bool(expectation)

    if observed is None:
        verdict = "undetermined"
        note = ("L'effet n'a pas été observé : aucun verdict. Une observation "
                "absente ne vaut jamais une conformité.")
    elif bool(observed) == attendu:
        verdict = "confirmed"
        note = "L'effet attendu est observé sur la réponse."
    elif attendu:
        verdict = "declared_without_effect"
        note = ("Le paramètre est positionné et l'effet n'est PAS observé sur "
                "le fil. Un audit qui s'arrête à la valeur conclut à une "
                "protection qui n'existe pas. La valeur d'un paramètre de "
                "sécurité n'est pas un curseur : seule l'observation dit ce "
                "qu'elle produit.")
    else:
        verdict = "effect_without_declaration"
        note = ("L'effet est observé sans que le paramètre l'annonce : autre "
                "chose le produit, et cette autre chose n'est pas surveillée.")
    return {"control": nom, "declared": valeur, "observed": observed,
            "verdict": verdict, "note": note}
