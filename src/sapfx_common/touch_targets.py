"""Ce qu'un argument, un keyword ou un appel TOUCHE sur le système SAP : le
contrat que lisent les outils de couverture (backlog 2.83, lots 1 à 3,
2026-10-20).

Une matrice de traçabilité relie un plan à une suite, la suite à ses keywords,
et veut finir sur « la transaction, le service OData, la table ou
le module fonction réellement touché ». Le cœur d'un outil ne peut pas le
deviner d'après le NOM d'un argument. La bibliothèque le dit de deux façons,
qui se lisent ici :

- **par un type d'argument** : Libdoc publie, pour chaque keyword, le type de
  chacun de ses arguments (``TransactionCode``, ``ODataPath``,
  ``ODataServicePath``, ``RfcFunctionName``, ``TableName``, ``FlpIntent``).
  ``touched_by_argument(type, valeur)`` dit ce que cette valeur désigne ;
- **par un tag de keyword** : un keyword qui lance lui-même une transaction
  (``Reach Se16 Selection Screen`` démarre SE16) le déclare par le tag Libdoc
  ``touches:transaction:SE16``. ``parse_touch_tag`` le lit ; une garde des
  tests tient les tags égaux à ce que le code appelle.

Une valeur qu'on ne sait pas lire (variable Robot non résolue, service OData
inconnu) rend une cible ``resolved: False`` avec sa raison, jamais une
cible devinée ni un oubli. « Touché » n'est pas « testé » : une transaction
démarrée par un keyword n'est pas vérifiée pour autant.

Typed.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

from sapfx_common.flp_tiles import normalize_intent
from sapfx_common.odata_path import parse_odata_path
from sapfx_common.transaction_code import transaction_touched

__all__ = ["TOUCH_KINDS", "TOUCH_TAG_PREFIX", "TOUCH_TYPES", "parse_touch_tag",
           "touch_tag", "touched_by_argument", "touched_by_http_path"]

#: Les genres d'objet SAP qu'on sait nommer. ``http_resource`` n'est produit que par
#: `touched_by_http_path`, jamais par un type d'argument : c'est une requête HTTP dont le
#: chemin ne se lit pas comme de l'OData.
TOUCH_KINDS = ("transaction", "odata_service", "odata_entity_set", "rfc_function",
               "table", "flp_intent", "http_resource")

#: Le type d'argument (nom publié par Libdoc) -> le genre d'objet qu'il touche.
TOUCH_TYPES = {
    "TransactionCode": "transaction",
    "ODataPath": "odata_entity_set",
    "ODataServicePath": "odata_service",
    "RfcFunctionName": "rfc_function",
    "TableName": "table",
    "FlpIntent": "flp_intent",
}

TOUCH_TAG_PREFIX = "touches:"

_UNRESOLVED = ("${", "@{", "&{", "%{")


def touch_tag(kind: str, identifier: str) -> str:
    """Le tag Libdoc d'un keyword qui touche ``identifier`` en interne :
    ``touches:transaction:SE16``."""
    if kind not in TOUCH_KINDS:
        raise ValueError("Genre de touche inconnu %r : attendu %s." % (kind, ", ".join(TOUCH_KINDS)))
    clean = str(identifier or "").strip()
    if not clean:
        raise ValueError("Une touche déclarée porte l'identifiant de ce qu'elle touche.")
    return "%s%s:%s" % (TOUCH_TAG_PREFIX, kind, clean)


def parse_touch_tag(tag: Any) -> Optional[dict[str, str]]:
    """``{"kind", "id"}`` d'un tag ``touches:<genre>:<identifiant>``, ou ``None``
    pour tout autre tag."""
    text = str(tag or "").strip()
    if not text.startswith(TOUCH_TAG_PREFIX):
        return None
    kind, _, identifier = text[len(TOUCH_TAG_PREFIX):].partition(":")
    if kind not in TOUCH_KINDS or not identifier:
        return None
    return {"kind": kind, "id": identifier}


def _unresolved(kind: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {"kind": kind, "id": None, "resolved": False, "reason": reason, **extra}


def _odata_targets(value: str, service_roots: Iterable[Any],
                   with_entity_set: bool) -> list[dict[str, Any]]:
    parsed = parse_odata_path(value, service_roots)
    if parsed["confidence"] == "unresolved":
        kind = "odata_entity_set" if with_entity_set else "odata_service"
        if not with_entity_set and parsed["reason"].startswith("service non reconnu"):
            # Un chemin de service est, par contrat, la racine du service : on
            # la garde telle quelle, le nom n'en est simplement pas déduit.
            return [{"kind": "odata_service", "id": parsed["path"], "resolved": True,
                     "service": None, "service_root": parsed["path"], "confidence": "declared"}]
        return [_unresolved(kind, parsed["reason"], path=parsed["path"])]
    service = {"kind": "odata_service", "id": parsed["service_root"], "resolved": True,
               "service": parsed["service"], "service_root": parsed["service_root"],
               "confidence": parsed["confidence"]}
    if not with_entity_set or not parsed["entity_set"]:
        return [service]
    return [service, {"kind": "odata_entity_set", "id": parsed["entity_set"], "resolved": True,
                      "service": parsed["service"], "service_root": parsed["service_root"],
                      "key": parsed["key"], "navigation": parsed["navigation"],
                      "confidence": parsed["confidence"]}]


def touched_by_http_path(path: Any, service_roots: Iterable[Any] = ()) -> list[dict[str, Any]]:
    """Ce qu'une REQUÊTE HTTP touche. Un chemin qui se lit comme de l'OData rend son service
    puis son entity set (comme ``ODataPath``) ; tout autre chemin (service de démarrage du
    launchpad, version UI5, ``manifest.json``, ressource SOAP ou ICF) rend la ressource
    elle-même, ``http_resource``, jamais un service ou un entity set déclaré à tort. Une
    valeur vide ou une variable non résolue reste inconnue (``resolved: False``)."""
    targets = touched_by_argument("ODataPath", path, service_roots)
    if (len(targets) == 1 and not targets[0]["resolved"] and targets[0].get("path")
            and str(targets[0]["reason"]).startswith("service non reconnu")):
        return [{"kind": "http_resource", "id": targets[0]["path"], "resolved": True}]
    return targets


def touched_by_argument(type_name: str, value: Any,
                        service_roots: Iterable[Any] = ()) -> list[dict[str, Any]]:
    """Les objets SAP qu'une VALEUR touche, d'après le type de l'argument qui la
    porte (le nom que publie Libdoc). Rend une liste de cibles ``{kind, id,
    resolved, ...}`` : vide pour un type qui ne touche rien, une cible
    ``resolved: False`` (avec ``reason``) pour une valeur illisible.

    ``ODataPath`` rend deux cibles quand l'entity set se lit : le service puis
    l'entity set. ``service_roots`` : les racines de service que l'appelant
    connaît (les valeurs des arguments ``ODataServicePath``), pour les chemins
    qui ne portent pas de préfixe ``/sap/opu/odata``."""
    kind = TOUCH_TYPES.get(str(type_name))
    if kind is None:
        return []
    text = str(value if value is not None else "").strip()
    if not text:
        return [_unresolved(kind, "valeur vide")]
    if any(marker in text for marker in _UNRESOLVED):
        return [_unresolved(kind, "variable Robot non résolue", value=text)]
    if kind == "transaction":
        code = transaction_touched(text)
        if code is None:
            return []                  # OK-code système : il ne démarre rien
        return [{"kind": kind, "id": code, "resolved": True}]
    if kind == "flp_intent":
        intent = normalize_intent(text)
        return [{"kind": kind, "id": intent, "resolved": True}] if intent else [
            _unresolved(kind, "intent illisible", value=text)]
    if kind in ("odata_service", "odata_entity_set"):
        return _odata_targets(text, service_roots, with_entity_set=kind == "odata_entity_set")
    return [{"kind": kind, "id": text.upper(), "resolved": True}]
