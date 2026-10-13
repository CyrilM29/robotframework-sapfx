"""État du mode *Espaces et Pages* d'un launchpad, logique pure (fiche
scénario 14, 2026-10-13).

Un launchpad ABAP récent peut remplacer l'accueil classique à groupes par des
espaces et des pages. Savoir lequel des deux est actif ne se lit PAS dans une
seule clé : mesuré sur ABAP Platform 2023 (SAPUI5 1.120.15), la configuration
déclare ``ushell.spaces.myHome.enabled = true`` alors que le mode est inactif
et que l'accueil rendu est le tableau de bord classique. Un détecteur qui
conclut « actif » dès qu'une clé existe sous ``ushell.spaces`` se trompe donc
sur un système réel.

D'où trois lectures de natures différentes, chacune classée en ``active``,
``inactive`` ou ``unreadable`` :

* **déclaré** : la rubrique ``ushell.spaces`` de la configuration servie ;
* **effectif** : le service ``Menu`` du conteneur ushell, ce que le shell a
  décidé avant de rendre ;
* **rendu** : les types PLEINS des contrôles de l'accueil (le nom court ne
  suffit pas : la page du tableau de bord classique est un ``sap.m.Page``).

Le verdict exige que les trois concordent. Une lecture illisible donne
``unreadable`` (jamais ``inactive`` faute d'avoir pu lire), deux lectures
lisibles qui divergent donnent ``inconsistent``.
"""

from typing import Any, Dict, Iterable, List, Optional

ACTIVE = "active"
INACTIVE = "inactive"
UNREADABLE = "unreadable"
INCONSISTENT = "inconsistent"

# Types pleins qui distinguent les deux mises en page (relevés en 1.120 pour
# la branche classique ; la classe de section de la branche espaces est vue
# CHARGEABLE dans ce runtime, jamais vue rendue sur le banc).
CLASSIC_HOME_TYPE = "sap.ushell.components.homepage.DashboardContent"
CLASSIC_GROUP_TYPE = "sap.ushell.ui.launchpad.TileContainer"
SPACES_SECTION_TYPE = "sap.ushell.ui.launchpad.Section"

# Clés sous ``ushell.spaces`` dont la présence est connue SANS effet sur le
# mode (``myHome`` : vraie sur la 2023, mode inactif). Toute autre clé que
# ``enabled`` rend la lecture illisible : elle est nommée, jamais ignorée.
DEFAULT_IGNORED_KEYS = ("myHome",)


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "x", "1", "yes")
    return bool(value)


def classify_declared(spaces: Any, config_present: bool = True,
                      ignored_keys: Iterable[str] = DEFAULT_IGNORED_KEYS
                      ) -> Dict[str, Any]:
    """Classe la rubrique ``ushell.spaces`` de la configuration.

    ``spaces`` vaut ``None`` quand la configuration existe sans cette
    rubrique (mode classique). ``config_present`` faux = configuration
    illisible."""
    if not config_present:
        return {"state": UNREADABLE, "reason": "configuration ushell absente"}
    if spaces is None:
        return {"state": INACTIVE, "reason": "rubrique ushell.spaces absente",
                "keys": []}
    if not isinstance(spaces, dict):
        return {"state": UNREADABLE,
                "reason": "rubrique ushell.spaces illisible (%s)" % type(spaces).__name__}
    ignored = set(ignored_keys or ())
    keys = sorted(str(k) for k in spaces)
    unknown = [k for k in keys if k != "enabled" and k not in ignored]
    if unknown:
        return {"state": UNREADABLE, "keys": keys,
                "reason": "clé(s) inconnue(s) sous ushell.spaces : %s "
                          "(à mesurer, puis à déclarer dans ignored_keys si "
                          "elle est sans effet)" % ", ".join(unknown)}
    if "enabled" in spaces and _truthy(spaces["enabled"]):
        return {"state": ACTIVE, "keys": keys,
                "reason": "ushell.spaces.enabled vrai"}
    return {"state": INACTIVE, "keys": keys,
            "reason": "ushell.spaces.enabled absent ou faux"}


def classify_effective(menu: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Classe l'état du service ``Menu`` (``Get Flp Menu State``)."""
    if not isinstance(menu, dict) or not menu.get("available"):
        return {"state": UNREADABLE, "reason": "service Menu indisponible"}
    enabled = menu.get("menu_enabled")
    entries = menu.get("entries")
    if enabled is None or not isinstance(entries, int):
        return {"state": UNREADABLE,
                "reason": "service Menu sans réponse lisible (%s)"
                          % (", ".join(menu.get("errors") or []) or "?")}
    if enabled:
        return {"state": ACTIVE, "reason": "isMenuEnabled vrai, %d entrée(s)" % entries}
    if entries == 0:
        return {"state": INACTIVE, "reason": "isMenuEnabled faux, aucune entrée"}
    return {"state": UNREADABLE,
            "reason": "isMenuEnabled faux mais %d entrée(s) de menu" % entries}


DEFAULT_ROOT_INTENT = "Shell-home"


def is_home_hash(hash_value: Any, root_intent: Any = DEFAULT_ROOT_INTENT) -> bool:
    """Le fragment courant désigne-t-il l'accueil du launchpad ? Vide, ``#``
    ou l'intent racine (paramètres et route interne admis)."""
    root = str(root_intent or DEFAULT_ROOT_INTENT)
    text = str(hash_value or "").lstrip("#")
    if not text:
        return True
    return text == root or text.startswith(root + "?") or text.startswith(root + "&")


def classify_rendered(types: Optional[Dict[str, int]],
                      on_home: bool = True, location: str = "") -> Dict[str, Any]:
    """Classe l'accueil rendu à partir de l'histogramme des types pleins
    (``Get Ui5 Control Types``). Hors de l'accueil (``on_home`` faux : App
    Finder, application ouverte), la lecture est ILLISIBLE : la structure de
    l'accueil ne se juge que sur l'accueil."""
    if not on_home:
        return {"state": UNREADABLE, "location": location,
                "reason": "l'écran courant (%s) n'est pas l'accueil" % (location or "?")}
    counts = {str(k): int(v) for k, v in (types or {}).items()}
    total = sum(counts.values())
    home = counts.get(CLASSIC_HOME_TYPE, 0)
    groups = counts.get(CLASSIC_GROUP_TYPE, 0)
    sections = counts.get(SPACES_SECTION_TYPE, 0)
    base = {"controls": total, "classic_home": home, "groups": groups,
            "sections": sections}
    if total == 0:
        return dict(base, state=UNREADABLE, reason="aucun contrôle rendu")
    if home and groups and not sections:
        return dict(base, state=INACTIVE, reason="accueil classique à groupes")
    if sections and not home:
        return dict(base, state=ACTIVE, reason="sections d'une page d'espace")
    if home and sections:
        return dict(base, state=UNREADABLE,
                    reason="les deux mises en page sont rendues")
    return dict(base, state=UNREADABLE,
                reason="aucune des deux mises en page reconnue")


def classify_spaces_mode(declared: Dict[str, Any], effective: Dict[str, Any],
                         rendered: Dict[str, Any]) -> Dict[str, Any]:
    """Verdict des trois lectures classées : ``active`` / ``inactive`` quand
    elles concordent, ``unreadable`` si l'une est illisible, ``inconsistent``
    si deux lectures lisibles divergent. ``reasons`` nomme chaque lecture."""
    signals = {"declared": declared, "effective": effective, "rendered": rendered}
    reasons: List[str] = ["%s=%s (%s)" % (name, s.get("state"), s.get("reason", ""))
                          for name, s in signals.items()]
    states = {name: str(s.get("state")) for name, s in signals.items()}
    if UNREADABLE in states.values():
        state = UNREADABLE
    elif len(set(states.values())) > 1:
        state = INCONSISTENT
    else:
        state = states["declared"]
    return {"state": state, "declared": declared, "effective": effective,
            "rendered": rendered, "reasons": reasons}


def describe_spaces_mode(verdict: Dict[str, Any]) -> str:
    """Résumé d'une ligne d'un verdict, pour un journal ou un échec."""
    return "mode Espaces et Pages : %s ; %s" % (
        verdict.get("state"), " ; ".join(verdict.get("reasons") or []))
