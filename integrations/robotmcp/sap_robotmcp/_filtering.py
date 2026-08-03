"""Filtrage de la perception SAP pour ``get_page_source(filtered=True, ...)``.

``LibraryStateProvider.get_page_source`` (contrat rf-mcp réel, vérifié dans
``robotmcp/plugins/contracts.py`` / ``page_source_service.py``) accepte
``filtered: bool`` et ``filtering_level: str`` (``"minimal"``/``"standard"``/
``"aggressive"``) — le provider Browser intégré les utilise pour réduire
progressivement le HTML renvoyé (scripts/style retirés en minimal, éléments non
visuels en plus en standard, éléments cachés en plus en aggressive). Nos
providers SAP acceptaient ces deux paramètres sans jamais les utiliser
(toujours la perception complète) ; ce module leur donne un sens réel, sur le
même principe de progressivité, pour réduire la taille de la réponse sur les
écrans SAP très chargés (SE16 à 40 champs, tables UI5 volumineuses...).

Toujours **post-traitement pur** sur le texte déjà obtenu du keyword de
perception réel (jamais un raccourci qui saute le sondage de l'écran) : la
fraîcheur de la perception n'est jamais sacrifiée pour la taille.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

FILTERING_LEVELS = ("minimal", "standard", "aggressive")

# --- ECC : signature texte (une ligne par contrôle, "* " = éditable) ----------


def filter_ecc_signature(signature: str, level: str = "standard") -> str:
    """Réduit une signature d'écran ECC (`Get Screen Signature`) selon ``level``.

    - ``minimal``    : retire les lignes non éditables et sans texte visible
      (bruit structurel pur : rien à lire, rien à remplir).
    - ``standard``    : + retire les conteneurs de mise en page connus
      (barres d'outils, onglets, splitters...) même s'ils portent un peu de texte.
    - ``aggressive``  : ne garde que les champs éditables (``* ``) — la vue la
      plus compacte, pour un agent qui veut juste "que puis-je remplir ?".

    L'en-tête ``# screen ...`` est toujours conservé."""
    lines = signature.splitlines()
    if not lines:
        return signature
    header, body = lines[0], lines[1:]
    kept = [line for line in body if _keep_ecc_line(line, level)]
    return "\n".join([header, *kept])


# Types structurels connus (mise en page pure, jamais éditables ni porteurs
# d'une information que l'agent agirait dessus) -- retirés dès "standard".
_ECC_STRUCTURAL_TYPES = {
    "GuiContainerShell", "GuiScrollContainer", "GuiSimpleContainer",
    "GuiSplitterContainer", "GuiTabStrip", "GuiToolbar", "GuiStatusbar",
}


def _keep_ecc_line(line: str, level: str) -> bool:
    parts = line.split("\t")
    if len(parts) < 3:
        return True   # format inattendu -> ne pas risquer de perdre une info
    # 4e colonne optionnelle (géométrie `@x,y LxH` de include_geometry) ignorée :
    # la décision de filtrage ne porte que sur id/type/texte.
    marked_id, etype, text = parts[0], parts[1], parts[2]
    editable = marked_id.startswith("* ")
    if level == "aggressive":
        return editable
    if editable:
        return True
    if not text.strip():
        return False   # bruit structurel pur, dans tous les niveaux filtrés
    if level == "standard" and etype in _ECC_STRUCTURAL_TYPES:
        return False
    return True


# --- Fiori : arbre XML de contrôles UI5 (Get Ui5 Page Tree) --------------------

# Types de contrôle (forme courte) sur lesquels un agent agit ou lit une valeur
# directement -- jamais élagués, quel que soit le niveau.
_UI5_INTERACTIVE_TAGS = {
    "Button", "Input", "TextArea", "CheckBox", "RadioButton", "Select",
    "ComboBox", "MultiComboBox", "DatePicker", "SearchField", "Link", "Switch",
    "Table", "List", "StandardListItem", "ColumnListItem", "Dialog",
}


def filter_ui5_tree(xml_text: str, level: str = "standard") -> str:
    """Élague l'arbre de contrôles UI5 (`Get Ui5 Page Tree`) selon ``level``.

    Élagage **ascendant** (feuilles d'abord) : un nœud n'est retiré que s'il
    n'a AUCUN descendant survivant -- un nœud "pas intéressant en soi" mais
    ancêtre d'un nœud conservé reste toujours présent. La hiérarchie/le chemin
    XPath de tout ce qui survit est donc garanti intact (jamais de "trou").

    - ``minimal``   : retire seulement les feuilles totalement vides (aucun
      attribut significatif, pas de texte).
    - ``standard``   : + retire les feuilles non interactives et sans texte/valeur.
    - ``aggressive`` : + retire aussi les feuilles non interactives même
      porteuses de texte (ne garde que les contrôles réellement actionnables).

    Entrée non parsable (XML malformé) : retournée telle quelle, inchangée --
    on ne fait jamais échouer une perception sur un filtre best-effort."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return xml_text
    _prune(root, level)
    return ET.tostring(root, encoding="unicode")


def _is_leaf_worth_keeping(node: ET.Element, level: str) -> bool:
    if node.tag in _UI5_INTERACTIVE_TAGS:
        return True
    if level == "aggressive":
        return False
    has_text = bool((node.get("text") or node.get("value") or "").strip())
    if level == "minimal":
        return has_text or bool(node.attrib)
    return has_text   # "standard"


def _prune(node: ET.Element, level: str) -> None:
    for child in list(node):
        _prune(child, level)
    for child in list(node):
        if len(child) == 0 and not _is_leaf_worth_keeping(child, level):
            node.remove(child)


def normalize_level(level: str, fallback: str = "standard") -> str:
    """Normalise ``level`` vers l'une des ``FILTERING_LEVELS`` connues ; retombe
    sur ``fallback`` pour une valeur absente/invalide plutôt que de lever --
    un paramètre de perception mal orthographié ne doit jamais faire échouer
    tout l'appel de l'agent."""
    if level in FILTERING_LEVELS:
        return level
    return fallback
