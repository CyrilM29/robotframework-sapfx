"""Modèle de sélecteur de contrôle UI5 (données pures — sans navigateur, sans Playwright).

Tout l'enjeu du côté Fiori est de ne plus combattre les identifiants DOM dynamiques de
SAPUI5 (``__xmlview0--__button12``). On s'adresse aux *contrôles UI5* par leurs attributs
stables et sémantiques ; la résolution en page se trouve dans `_ui5_js.py`, l'exécution
en page dans `SapFioriLibrary`.

Ce module se contente de construire et de valider le dictionnaire de sélecteur de rôle,
de sorte que sa logique est entièrement testable hors ligne.
"""
from __future__ import annotations

import ast
import json
import re
from typing import Any
from urllib.parse import quote

# Sélecteurs dont la valeur est un dict (propriété -> attendu). Robot Framework passe
# un argument nommé `properties={'text': 'X'}` comme une *chaîne* ; on l'accepte aussi
# bien sous forme de chaîne littérale que de vrai dict (appel Python direct / tests).
_DICT_KEYS = ("properties", "bindingPath")

# Clés de sélecteur comprises par le résolveur de registre. Limitées à ce que l'on peut
# réellement et fiablement faire correspondre — une faute de frappe ou une clé non prise
# en charge échoue rapidement au lieu de correspondre silencieusement au mauvais contrôle.
_ALLOWED_KEYS = {
    "id",            # identifiant exact du contrôle, p. ex. "sdk---app--searchField"
    "idSuffix",      # FIN de l'identifiant — le motif des ids stables Fiori Elements
                     # ("fe::table::<Entity>::LineItem::Table" ; le préfixe app/route varie)
    "controlType",   # p. ex. "sap.m.Button"
    "properties",    # dict propriété -> valeur attendue, p. ex. {"text": "Create"}
    "bindingPath",   # dict, p. ex. {"path": "/Orders", "propertyPath": "Status"}
    "viewId",        # restreint aux contrôles dont l'identifiant contient cet identifiant de vue
}


def build_control_selector(**kwargs: Any) -> dict[str, Any]:
    """Construit un dictionnaire de sélecteur de contrôle UI5 à partir des arguments nommés.

    Rejette les clés inconnues immédiatement (avec la liste des clés valides) afin qu'une
    faute de frappe échoue rapidement devant l'auteur du test plutôt que de ne rien
    correspondre silencieusement dans le navigateur.

    Exemple::

        build_control_selector(controlType="sap.m.Button", properties={"text": "Go"})
    """
    unknown = set(kwargs) - _ALLOWED_KEYS
    if unknown:
        raise ValueError(
            "Unknown UI5 selector key(s): %s. Allowed: %s"
            % (sorted(unknown), sorted(_ALLOWED_KEYS))
        )
    selector = {k: v for k, v in kwargs.items() if v is not None}
    if not selector:
        raise ValueError("Empty UI5 selector — provide at least one of: %s"
                         % sorted(_ALLOWED_KEYS))
    for key in _DICT_KEYS:
        if key in selector:
            selector[key] = _coerce_dict(selector[key], key)
    return selector


def _coerce_dict(value: Any, key: str) -> dict[str, Any]:
    """Accepte un dict tel quel, ou parse une chaîne littérale de dict.

    Robot transmet ``properties={'text': 'X'}`` comme la chaîne ``"{'text': 'X'}"`` ;
    on la convertit via ``ast.literal_eval`` (sûr — littéraux uniquement). Un appel
    Python direct (et les tests) passe déjà un dict, laissé intact."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            raise ValueError(
                "UI5 selector '%s' must be a dict or a dict literal string, got: %r"
                % (key, value))
        if not isinstance(parsed, dict):
            raise ValueError(
                "UI5 selector '%s' must be a dict, got %s"
                % (key, type(parsed).__name__))
        return parsed
    raise ValueError(
        "UI5 selector '%s' must be a dict or a dict literal string, got %s"
        % (key, type(value).__name__))


def selector_to_json(selector: dict[str, Any]) -> str:
    """Sérialise un dictionnaire de sélecteur en JSON compact et déterministe pour l'intégration en JS."""
    return json.dumps(selector, sort_keys=True, separators=(",", ":"))


# Clés du sélecteur du moteur **Web Components** (`Resolve Wc Control`) : les pages
# « pur UI5 Web Components » (ex. home SuccessFactors) rendent des custom elements
# <ui5-button>… SANS runtime UI5 classique — registre vide, moteurs role/xpath
# aveugles. Ce moteur scanne les hôtes custom elements du light DOM.
_WC_ALLOWED_KEYS = {
    "tag",         # 'Button' (type court) ou 'ui5-button' (tag complet) ; matche
                   # aussi les tags SCOPÉS ui5-button-<suffixe> (scoping UI5 WC)
    "text",        # sous-chaîne insensible à la casse (ou /regex/flags) sur le textContent
    "name",        # NOM ACCESSIBLE de l'hôte (accname simplifié : aria-labelledby,
                   # aria-label, accessible-name/accessibleName — la convention
                   # UI5 Web Components —, label, texte…) ; mêmes règles de matching
    "id",          # id exact de l'élément hôte
    "idSuffix",    # FIN de l'id de l'hôte (même sémantique que le moteur role)
    "properties",  # dict attribut/propriété -> attendu (mêmes règles de matching
                   # que le moteur role : sous-chaîne insensible à la casse, /regex/)
}


def build_wc_selector(**kwargs: Any) -> dict[str, Any]:
    """Construit et valide le sélecteur du moteur Web Components.

    Mêmes garanties que :func:`build_control_selector` : une clé inconnue échoue
    immédiatement (avec la liste des clés valides), ``properties`` accepte un dict
    ou sa forme littérale chaîne (passage Robot Framework)."""
    unknown = set(kwargs) - _WC_ALLOWED_KEYS
    if unknown:
        raise ValueError(
            "Unknown WC selector key(s): %s. Allowed: %s"
            % (sorted(unknown), sorted(_WC_ALLOWED_KEYS))
        )
    selector = {k: v for k, v in kwargs.items() if v is not None}
    if not selector:
        raise ValueError("Empty WC selector — provide at least one of: %s"
                         % sorted(_WC_ALLOWED_KEYS))
    if "properties" in selector:
        selector["properties"] = _coerce_dict(selector["properties"], "properties")
    return selector


# Clés du sélecteur du moteur **DOM générique** (`Resolve Dom Element`) : le 5e
# moteur, pour les zones NON-SAP d'une page hybride (widget React/Angular/
# vanilla dans un shell Fiori, portlet Work Zone…) qu'aucun moteur SAP ne voit.
_DOM_ALLOWED_KEYS = {
    "css",         # sélecteur CSS de base (querySelectorAll) restreignant le scan
    "tag",         # nom de balise exact (button, a, input…)
    "text",        # sous-chaîne insensible à la casse ou /regex/ sur le textContent
    "role",        # rôle ARIA CALCULÉ : attribut role explicite OU rôle implicite
                   # de la sémantique HTML (button, a[href] -> link, input[type] ->
                   # textbox/checkbox/…, h1-h6 -> heading…) — insensible à la casse
    "name",        # NOM ACCESSIBLE (accname simplifié : aria-labelledby, aria-label,
                   # label[for]/englobant, alt, value de bouton, texte, title,
                   # placeholder) ; mêmes règles de matching que text
    "id",          # id exact de l'élément
    "idSuffix",    # FIN de l'id (même sémantique que les moteurs role/wc)
    "properties",  # dict attribut -> attendu (mêmes règles de matching que role/wc)
}


def build_dom_selector(**kwargs: Any) -> dict[str, Any]:
    """Construit et valide le sélecteur du moteur DOM générique.

    Mêmes garanties que :func:`build_control_selector` : une clé inconnue échoue
    immédiatement (avec la liste des clés valides), ``properties`` accepte un
    dict ou sa forme littérale chaîne (passage Robot Framework)."""
    unknown = set(kwargs) - _DOM_ALLOWED_KEYS
    if unknown:
        raise ValueError(
            "Unknown DOM selector key(s): %s. Allowed: %s"
            % (sorted(unknown), sorted(_DOM_ALLOWED_KEYS))
        )
    selector = {k: v for k, v in kwargs.items() if v is not None}
    if not selector:
        raise ValueError("Empty DOM selector — provide at least one of: %s"
                         % sorted(_DOM_ALLOWED_KEYS))
    if "properties" in selector:
        selector["properties"] = _coerce_dict(selector["properties"], "properties")
    return selector


def recommended_engines(composition: dict[str, Any]) -> list[str]:
    """Ordre d'essai des moteurs de résolution pour une composition sondée.

    Fonction pure (testable hors navigateur) derrière la clé ``engines`` de
    `Get Page Composition` : traduit les technologies détectées dans une
    région en moteurs concrets, du plus stable au plus générique — le même
    ordre que la chaîne de `Resolve Ui5 With Fallback`. ``dom`` ferme toujours
    la liste : une page a toujours un DOM."""
    engines: list[str] = []
    if composition.get("ui5_runtime"):
        engines += ["role", "xpath"]
    if composition.get("webgui_elements"):
        engines.append("sid")
    if composition.get("wc_hosts"):
        engines.append("wc")
    engines.append("dom")
    return engines


# --- Carte numérotée de page (@N) --------------------------------------------
# Pendant Fiori de la carte ECC (patron « map / @e1 » agent-first, cf. Vibium) :
# l'arbre de contrôles UI5 est réduit aux cibles ACTIONNABLES, numérotées, pour
# que l'agent agisse par référence (`Click Ui5 Ref`) sans recopier un id.

# Types courts SAISISSABLES (marqués ``*`` — la valeur courante est affichée).
UI5_EDITABLE_TYPES = frozenset({
    "Input", "MultiInput", "MaskInput", "TextArea", "SearchField",
    "ComboBox", "MultiComboBox", "DatePicker", "DateRangeSelection",
    "TimePicker", "DateTimePicker", "StepInput",
})

# Types courts actionnables PAR CLIC (boutons, liens, cases, onglets…). Les
# lignes de liste/table (ColumnListItem…) sont volontairement exclues du
# défaut — elles noieraient la carte ; les viser via ``include_types``.
UI5_CLICKABLE_TYPES = frozenset({
    "Button", "ToggleButton", "OverflowToolbarButton", "Link", "CheckBox",
    "RadioButton", "Switch", "Select", "MenuItem", "IconTabFilter", "Tab",
    "SegmentedButtonItem", "FileUploader",
})

UI5_ACTIONABLE_TYPES = UI5_EDITABLE_TYPES | UI5_CLICKABLE_TYPES

# Attributs de l'arbre portant le libellé humain d'une cible, par priorité.
_MAP_LABEL_ATTRIBUTES = ("text", "title", "placeholder", "tooltip")


def ui5_page_map(tree_xml: str,
                 include_types: Any = None) -> tuple[list[str], dict[str, str]]:
    """Réduit l'arbre XML des contrôles (``Get Ui5 Page Tree``) à la **carte
    numérotée** des cibles actionnables : ``(lignes, refs)``.

    Chaque ligne : ``@N\\t<marque><libellé ou ?>\\t<id>\\t<TypeCourt>`` —
    marque ``* `` pour un champ saisissable (suivi de ``= <valeur>``), deux
    espaces pour une cible cliquable. ``refs`` mappe ``"N" -> id de contrôle``
    (l'id DOM stable rendu par le registre UI5), l'ordre est celui du
    document. ``include_types`` (chaîne ``"A,B"`` ou itérable de types courts)
    remplace la sélection par défaut — p. ex. ``ColumnListItem`` pour
    numéroter les lignes d'une table. Pure (aucun navigateur) ; lève
    ``ValueError`` si le XML est invalide."""
    import xml.etree.ElementTree as ElementTree
    try:
        root = ElementTree.fromstring(tree_xml)
    except ElementTree.ParseError as exc:
        raise ValueError("Arbre UI5 illisible (XML invalide) : %s" % exc)
    if include_types:
        if isinstance(include_types, str):
            wanted = {part.strip() for part in include_types.split(",")
                      if part.strip()}
        else:
            wanted = {str(part).strip() for part in include_types}
    else:
        wanted = set(UI5_ACTIONABLE_TYPES)
    lines: list[str] = []
    refs: dict[str, str] = {}
    for element in root.iter():
        if element.tag not in wanted:
            continue
        control_id = element.get("id") or ""
        if not control_id:
            continue
        editable = element.tag in UI5_EDITABLE_TYPES
        label = next((element.get(attr) for attr in _MAP_LABEL_ATTRIBUTES
                      if element.get(attr)), None)
        number = str(len(refs) + 1)
        line = "@%s\t%s%s\t%s\t%s" % (number, "* " if editable else "  ",
                                      label if label is not None else "?",
                                      control_id, element.tag)
        if editable:
            line += "\t= %s" % (element.get("value") or "")
        refs[number] = control_id
        lines.append(line)
    return lines, refs


# --- Navigation launchpad (FLP) : intent sémantique -> hash -------------------
# Concept issu de l'analyse de playwright-praman (Apache-2.0 — NOTICE) : on
# navigue un launchpad par son INTENT « SemanticObject-action » (le hash
# stable, cross-thème, cross-catalogue), jamais en cliquant des tuiles par
# position. La partie pure (validation + construction du hash) vit ici.

_INTENT_RE = re.compile(r"^[A-Za-z_][\w]*-[A-Za-z_][\w]*$")


def build_intent_hash(intent: str, params: dict[str, Any] | None = None) -> str:
    """Construit le hash de navigation FLP d'un intent ``SemanticObject-action``.

    ``build_intent_hash("SalesOrder-manage", {"SalesOrder": "1234"})`` →
    ``#SalesOrder-manage?SalesOrder=1234``. Valide la forme de l'intent
    (échec immédiat avec la forme attendue — pas de hash silencieusement
    cassé) ; les paramètres sont encodés URL et émis en ordre déterministe."""
    intent = str(intent).strip().lstrip("#")
    if not _INTENT_RE.match(intent):
        raise ValueError(
            "Intent FLP invalide : %r — forme attendue 'SemanticObject-action' "
            "(ex. 'Shell-home', 'SalesOrder-manage')." % intent)
    hash_ = "#" + intent
    if params:
        pairs = "&".join(
            "%s=%s" % (quote(str(k), safe=""), quote(str(v), safe=""))
            for k, v in sorted(params.items()))
        hash_ += "?" + pairs
    return hash_
