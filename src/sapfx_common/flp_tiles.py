"""Tuiles d'un launchpad Fiori : intent, compteur affiché, configuration.

Logique pure derrière `Get Flp Tile Counter`, `Wait For Flp Tile Counter` et
`Get Flp Tile Configuration` (SapFioriLibrary), née de la fiche scénario 7
(2026-09-29) : confronter le compteur d'une tuile dynamique à un agrégat lu
par un autre canal. Trois faits mesurés sur les launchpads ABAP du banc
(SAPUI5 1.71 et 1.120) en font une capacité et non une lecture triviale.

* **Le compteur n'est pas chargé quand la tuile est rendue.** Le contenu
  numérique vaut d'abord la valeur d'attente ``...``, avec un état ``Loaded``
  sur la tuile ET sur le contenu : l'état ne prouve rien. Seule une valeur
  numérique prouve que la requête de la tuile est revenue (mesuré : ``...`` à
  263 ms, ``19`` à 421 ms). Une tuile dont le service ne rend pas un nombre
  reste sur ``...`` pour toujours (``Repository-manage`` sur les deux
  releases).
* **Le compteur est un nombre FORMATÉ.** Le formateur de la tuile groupe les
  milliers selon la notation de l'utilisateur (``1.950`` pour 1950 quand la
  notation décimale est vide), et le rendu est TRONQUÉ à cinq caractères
  (``10.000`` affiché ``10.00``) quand la propriété garde la valeur entière.
  Un nombre se lit donc avec les symboles EFFECTIFS de la page, jamais en
  retirant tous les points, et un rendu tronqué est signalé : ce qu'on voit
  n'est plus le nombre.
* **L'intent ne se lit pas au même endroit selon la release.** La propriété
  ``target`` de la tuile le porte en 1.71 et est vide en 1.120, où seule
  l'ancre HTML de la tuile le porte ; la configuration de la tuile, elle, le
  porte sur les deux (``navigation_target_url``).
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping, Optional, Sequence

from sapfx_common.user_formats import DECIMAL_FORMATS, normalize_decimal_key

__all__ = ["PENDING_VALUES", "split_intent", "normalize_intent",
           "number_symbols", "tile_counter_verdict", "select_tiles",
           "describe_tile_candidates", "parse_debug_info", "split_service_url",
           "fresh_responses", "fresh_response_verdict", "response_body_check",
           "decode_tile_configuration",
           "symbols_for_decimal_notation"]

#: Valeurs d'un contenu numérique dont la requête n'est pas (ou jamais)
#: revenue. ``...`` est la valeur d'attente mesurée sur 1.71 et 1.120.
PENDING_VALUES = frozenset({"", "...", "…"})

_SPACES = re.compile(r"[\s  ]+")


def split_intent(text: Any) -> tuple[str, str]:
    """``(SemanticObject-action, paramètres)`` depuis une cible, un fragment
    ou une URL complète.

    ``https://h/flp?sap-client=001#EPMPurchaseOrder-approve?b=2&a=1&/route``
    rend ``("EPMPurchaseOrder-approve", "a=1&b=2")`` : la requête de l'URL du
    launchpad n'est pas l'intent, la route interne de l'application (après
    ``&/``) non plus, et les paramètres sont TRIÉS pour que deux écritures du
    même intent se comparent. Une URL sans fragment rend ``("", "")``, jamais
    une valeur devinée.
    """
    brut = str(text or "").strip()
    if not brut:
        return "", ""
    if "#" in brut:
        brut = brut.split("#", 1)[1]
    elif "://" in brut or brut.startswith("/"):
        return "", ""
    brut = brut.split("&/", 1)[0]
    intent, _, parametres = brut.partition("?")
    paires = sorted(p for p in parametres.split("&") if p.strip())
    return intent.strip(), "&".join(paires)


def normalize_intent(text: Any) -> str:
    """``SemanticObject-action`` seul (paramètres retirés), pour l'affichage
    et les messages ; la SÉLECTION d'une tuile compare aussi les paramètres
    (:func:`select_tiles`)."""
    return split_intent(text)[0]


def number_symbols(sample: Any) -> dict[str, str]:
    """Les symboles de groupement et de décimale d'une page, déduits d'un
    ÉCHANTILLON que la page a formaté : ``1234567.5`` avec groupement et une
    décimale (``1.234.567,5`` → ``{"group": ".", "decimal": ","}``).

    Déduire les symboles d'un nombre connu formaté par la page elle-même, plutôt
    que de lire un réglage, tient sur toutes les versions : c'est l'API
    publique du formateur, et c'est le même formateur que celui de la tuile.
    Un échantillon illisible rend ``{}`` : la conversion n'acceptera alors
    qu'une valeur faite de chiffres seuls.
    """
    texte = _SPACES.sub(" ", str(sample or "")).strip()
    # Groupes NOMMÉS : `\1567` se lirait comme une référence au groupe 15.
    forme = re.fullmatch(r"1(?P<g>\D+)234(?P=g)567(?P<d>\D+)5", texte)
    if not forme or forme.group("g") == forme.group("d"):
        return {}
    return {"group": forme.group("g"), "decimal": forme.group("d")}


def tile_counter_verdict(value: Any, scale: Any = "", rendered: Any = None,
                         symbols: Optional[Mapping[str, str]] = None
                         ) -> dict[str, Any]:
    """Le verdict d'un compteur de tuile : ``{loaded, number, truncated,
    reason}``.

    * ``loaded`` faux tant que la valeur est la valeur d'attente (``...``) :
      c'est le SEUL témoin de chargement, l'état de la tuile valant
      ``Loaded`` avant comme après.
    * ``number`` n'est rempli que pour un ENTIER lu sans ambiguïté : chiffres
      seuls, ou groupes de trois séparés par le symbole de groupement de la
      page. Un facteur d'échelle (``K``, ``M``), un symbole de décimale ou
      toute autre forme laissent ``number`` à ``None`` avec la raison : une
      approximation n'est pas un nombre qu'on compare.
    * ``truncated`` vrai quand le texte RENDU n'est pas la valeur (plus son
      facteur) : le nombre de la propriété reste lu, et c'est à l'appelant de
      décider si un compteur que l'utilisateur voit tronqué est acceptable.
    """
    brut = "" if value is None else str(value)
    valeur = _SPACES.sub("", brut)
    facteur = _SPACES.sub("", "" if scale is None else str(scale))
    verdict: dict[str, Any] = {"loaded": False, "number": None,
                               "truncated": False, "reason": ""}
    if valeur in PENDING_VALUES:
        verdict["reason"] = ("valeur d'attente %r : la requête de la tuile "
                             "n'est pas revenue, ou son service ne rend pas "
                             "un nombre" % brut)
        return verdict
    verdict["loaded"] = True
    if rendered is not None:
        vu = _SPACES.sub("", str(rendered))
        if vu != valeur + facteur:
            verdict["truncated"] = True
    if facteur:
        verdict["reason"] = ("facteur d'échelle %r : le compteur %r est une "
                             "approximation, pas un nombre" % (facteur, brut))
        return verdict
    nombre = _as_integer(valeur, symbols or {})
    if nombre is None:
        verdict["reason"] = ("forme %r non lisible comme un entier avec les "
                             "symboles de la page %s" % (brut, dict(symbols or {})))
        return verdict
    verdict["number"] = nombre
    if verdict["truncated"]:
        verdict["reason"] = ("rendu tronqué : la tuile affiche %r pour la "
                             "valeur %r" % (str(rendered).strip(), brut))
    return verdict


def _as_integer(valeur: str, symbols: Mapping[str, str]) -> Optional[int]:
    if re.fullmatch(r"-?\d+", valeur):
        return int(valeur)
    groupe = symbols.get("group") or ""
    if not groupe or groupe.isdigit():
        return None
    motif = r"-?\d{1,3}(?:%s\d{3})+" % re.escape(groupe)
    if re.fullmatch(motif, valeur):
        return int(valeur.replace(groupe, ""))
    return None


def select_tiles(tiles: Sequence[Mapping[str, Any]], intent: Any,
                 ignore_parameters: bool = False) -> list[Mapping[str, Any]]:
    """Les tuiles dont l'intent est celui demandé, casse comprise (un objet
    sémantique y est sensible), PARAMÈTRES COMPRIS : ``X-y?p=1`` est une autre
    tuile que ``X-y``, qui ouvre la même application sur un autre jeu de
    données et compte donc autre chose. ``ignore_parameters`` ne compare que
    l'objet et l'action, par décision explicite de l'appelant."""
    voulu, parametres = split_intent(intent)
    if not voulu:
        raise ValueError("Aucun intent désigné : passer `SemanticObject-action` "
                         "(par exemple `EPMPurchaseOrder-approve`).")
    retenues = []
    for t in tiles:
        base, siens = split_intent(t.get("intent"))
        if base == voulu and (ignore_parameters or siens == parametres):
            retenues.append(t)
    return retenues


def describe_tile_candidates(tiles: Sequence[Mapping[str, Any]]) -> str:
    """La liste des tuiles vues, paramètres compris, pour un échec qui dit ce
    qui existe."""
    if not tiles:
        return "aucune tuile rendue"
    parts = []
    for t in tiles:
        base, parametres = split_intent(t.get("intent"))
        nom = (base or "?") + ("?" + parametres if parametres else "")
        parts.append("%s (%s)" % (nom, t.get("tile_id") or t.get("tile_instance_id")
                                  or t.get("chip_id") or "?"))
    return ", ".join(parts)


def parse_debug_info(raw: Any) -> dict[str, str]:
    """Le chip et l'instance que la propriété ``debugInfo`` d'une tuile
    rendue déclare (chaîne JSON mesurée sur 1.71 : ``chipId``,
    ``chipInstanceId``, ``catalogId``). Rend ``{}`` pour une chaîne vide ou
    illisible : ces identifiants servent à un RECOUPEMENT, leur absence se
    constate, elle ne s'invente pas."""
    try:
        donnees = json.loads(str(raw or ""))
    except ValueError:
        return {}
    if not isinstance(donnees, dict):
        return {}
    cles = {"chip_id": "chipId", "chip_instance_id": "chipInstanceId",
            "catalog_id": "catalogId"}
    return {k: str(donnees[v]) for k, v in cles.items() if donnees.get(v)}


def split_service_url(url: Any) -> tuple[str, str]:
    """``(chemin, requête)`` de l'adresse d'un service de tuile : une adresse
    qui porte une requête (``$filter``) ne compte pas la même chose que son
    chemin nu, d'où la séparation plutôt qu'une comparaison par sous-chaîne."""
    chemin, _, requete = str(url or "").strip().partition("?")
    return chemin, requete


def fresh_responses(entries: Sequence[Mapping[str, Any]], since_ms: Any
                    ) -> list[dict[str, Any]]:
    """Les réponses d'une requête PARTIE après le déclenchement d'un
    rafraîchissement : ``[{start, end, status}]`` triées par fin de réponse,
    en millisecondes de la MÊME horloge que le déclenchement
    (``performance.timeOrigin + performance.now()``).

    La requête doit être PARTIE après le déclenchement (``start >= since``),
    pas seulement terminée après lui : une requête du rafraîchissement
    périodique, lancée avant et revenue après, n'est pas encadrée par une
    mesure faite juste avant la demande (contre-revue du 2026-09-29). Le
    statut est rendu tel quel (``None`` quand le navigateur ne l'expose pas) :
    c'est à l'appelant d'exiger un succès. Une entrée illisible est ignorée,
    jamais prise pour fraîche."""
    try:
        depuis = float(since_ms)
    except (TypeError, ValueError):
        return []
    fraiches = []
    for entree in entries or []:
        if not isinstance(entree, Mapping):
            continue
        brut_debut, brut_fin = entree.get("start"), entree.get("end")
        if brut_debut is None or brut_fin is None:
            continue
        try:
            debut, fin = float(brut_debut), float(brut_fin)
        except (TypeError, ValueError):
            continue
        if debut >= depuis and fin >= debut:
            statut = entree.get("status")
            fraiches.append({"start": debut, "end": fin,
                             "status": statut if isinstance(statut, int) else None,
                             "transfer": _taille(entree.get("transfer")),
                             "body": _taille(entree.get("body"))})
    return sorted(fraiches, key=lambda r: r["end"])


def _taille(valeur: Any) -> Optional[int]:
    return valeur if isinstance(valeur, int) and not isinstance(valeur, bool) else None


def response_body_check(response: Mapping[str, Any], number: Any) -> str:
    """Le lien entre la réponse retenue et le nombre lu sur la tuile (revue
    n°3 du 2026-09-29) : un statut 200 prouve qu'une réponse est arrivée, pas
    que la valeur affichée en vient.

    * ``"matched"`` : réponse venue du RÉSEAU (``transferSize > 0``) et corps
      de la longueur exacte de l'entier affiché (le corps d'un ``$count`` est
      l'entier en chiffres seuls : 2 octets pour ``19``, mesuré). Un lien de
      LONGUEUR, pas d'identité : ``18`` et ``19`` ne se distinguent pas.
    * ``"cached"`` : corps servi par le cache du navigateur
      (``transferSize == 0``, corps non vide) : la tuile n'a rien redemandé
      au serveur, à refuser.
    * ``"mismatch"`` : corps d'une autre longueur que le nombre affiché : la
      valeur lue ne vient pas (encore) de cette réponse.
    * ``"not_exposed"`` : le navigateur n'expose pas les tailles (réponse
      d'une autre origine sans ``Timing-Allow-Origin``) : non mesurable, dit
      comme tel, jamais pris pour un lien établi.
    """
    corps, transfert = response.get("body"), response.get("transfer")
    if not corps:
        return "not_exposed"
    if not transfert:
        return "cached"
    try:
        attendu = len(str(abs(int(number))))
    except (TypeError, ValueError):
        return "mismatch"
    return "matched" if corps == attendu else "mismatch"


def fresh_response_verdict(responses: Sequence[Mapping[str, Any]]
                           ) -> tuple[Optional[Mapping[str, Any]], str]:
    """``(réponse retenue, raison)`` parmi les réponses fraîches : la dernière
    réponse en succès (statut 200) si elle existe ; sinon ``None`` et la
    raison, qui distingue « rien n'est revenu » (attendre encore) d'une
    réponse revenue en ÉCHEC ou sans statut lisible (état stable, à refuser :
    la tuile garde alors son ANCIENNE valeur, qui passerait pour fraîche)."""
    if not responses:
        return None, ""
    succes = [r for r in responses if r.get("status") == 200]
    if succes:
        return succes[-1], ""
    statuts = sorted({str(r.get("status")) for r in responses})
    if all(r.get("status") is None for r in responses):
        return None, ("le navigateur n'expose pas le statut de la réponse "
                      "(responseStatus) : la fraîcheur n'est pas prouvable")
    return None, ("le service a répondu %s au lieu de 200 : la tuile garde "
                  "sa valeur précédente, qui n'est pas fraîche" % ", ".join(statuts))


def decode_tile_configuration(raw: Any) -> dict[str, Any]:
    """Le contenu du paramètre ``tileConfiguration`` d'une tuile ABAP, qui est
    une chaîne JSON : dictionnaire décodé, ou ``{}`` si le paramètre est vide.

    Une chaîne qui n'est pas un objet JSON lève en le disant : une
    configuration illisible ne vaut pas une configuration vide (une tuile
    statique n'a simplement pas de ``service_url``).
    """
    texte = str(raw or "").strip()
    if not texte:
        return {}
    try:
        donnees = json.loads(texte)
    except ValueError as err:
        raise ValueError("Configuration de tuile illisible (%s) : %r"
                         % (err, texte[:120])) from err
    if not isinstance(donnees, dict):
        raise ValueError("Configuration de tuile inattendue (%s au lieu d'un "
                         "objet JSON)." % type(donnees).__name__)
    return donnees


def symbols_for_decimal_notation(decimal_format_key: Any) -> dict[str, str]:
    """Les symboles qu'une notation décimale SAP (``USR01-DCPFM``) impose :
    vide → ``{"group": ".", "decimal": ","}``, ``X`` → ``,`` et ``.``, ``Y``
    → espace et ``,``. Le contrôle CROISÉ des symboles qu'une page applique :
    une page qui formaterait selon la langue du navigateur plutôt que selon
    l'utilisateur lirait ``1,950`` là où l'utilisateur voit ``1.950``. Une
    clé inconnue lève en le disant."""
    cle = normalize_decimal_key(decimal_format_key)
    if cle not in DECIMAL_FORMATS:
        raise ValueError("Notation décimale DCPFM %r inconnue (attendu : vide, "
                         "X ou Y)." % (decimal_format_key,))
    groupe, decimale = DECIMAL_FORMATS[cle]
    return {"group": groupe, "decimal": decimale}
