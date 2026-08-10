"""Bundle JavaScript en page pour la résolution et la capture de contrôles UI5.

Porté (et simplifié pour fonctionner comme un bundle injecté unique, sans fork de Playwright)
depuis **playwright-sap** par Arpit Sureka, https://github.com/ArpitSureka/playwright-sap
Sous licence Apache-2.0. Voir le fichier NOTICE du projet.

Techniques adoptées depuis ce projet :
  * un *arbre de contrôles* UI5 reflétant la hiérarchie des contrôles, permettant des localisateurs
    XPath hiérarchiques (`//Table//Button[@text='Create']`) : bien plus expressifs
    qu'un parcours à plat du registre ;
  * extraction des propriétés propres et héritées via les métadonnées du contrôle ;
  * un comparateur de propriétés robuste (sous-chaîne insensible à la casse, plus /regex/) ;
  * navigation depuis l'élément racine d'un contrôle jusqu'à l'élément interne interactif ;
  * une liste de propriétés autorisées ordonnée par priorité, utilisée par le Spy pour
    choisir un sélecteur stable.

Le bundle définit un espace de noms idempotent `window.__SAPFX`. `build_call()` enveloppe une
méthode de l'espace de noms dans une expression de fonction que `Evaluate JavaScript` du navigateur
peut exécuter. Le modèle de sélecteur Python pur réside dans `_ui5_runtime.py`.
"""

from importlib import resources

# Propriétés ordonnées par priorité à placer dans l'arbre / à utiliser comme sélecteur,
# portées depuis playwright-sap `allowedRolesAndProperties.ts`. Classées par utilité.
ALLOWED_PROPERTY_PRIORITY = [
    "text", "title", "viewName", "value", "src", "key",
    "icon", "number", "description", "headerText", "href", "label",
    "selectedKey", "placeholder", "target", "name", "header", "tooltip",
    "html", "htmlText", "alt", "subtitle", "info", "state", "valueStateText",
    "noDataText", "count", "status", "design", "type", "level", "intro",
]

# Propriétés portant de façon fiable un texte significatif pour l'utilisateur (idéales pour un sélecteur stable).
OBVIOUS_TEXT_PROPERTIES = [
    "text", "title", "value", "description", "headerText", "header", "htmlText",
    "noDataText",
]

# Types de contrôles adressables par type seul (sans propriété), par ex. pour nth().
ALLOW_WITHOUT_PROPERTIES = [
    "SearchField", "PullToRefresh", "Row", "ColumnListItem", "Column",
    "CustomListItem", "GridListItem", "StandardListItem", "Table", "List",
    "Page", "ToolbarSeparator",
]


def _js_string_array(items):
    return "[" + ",".join("'%s'" % i for i in items) + "]"


def _read_js_template(name):
    """Charge un gabarit JS embarqué dans le paquet (fichier ``.js.tpl`` à
    côté de ce module) : le JS garde coloration, diffs lisibles et outillage
    JS ; le Python n'héberge plus des milliers de lignes de chaîne. Fins de
    ligne LF garanties par ``.gitattributes`` (le gabarit du bundle est
    formaté ensuite par ``%`` : ses ``%s`` sont les deux listes autorisées)."""
    return resources.files(__package__).joinpath(name).read_text(encoding="utf-8")


# Picto aicabra (medaillon du projet, assets/logo.png redimensionne 28px) embarque
# en data-URI pour le panneau du recorder : le bundle reste auto-contenu (aucune
# requete reseau, CSP-safe ; si une CSP img-src stricte bloque le data:, l'onerror
# masque l'image, purement cosmetique). Regenere en place par gen_icons.py.
_AICABRA_ICON = (
    "data:image/png;base64,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"
    "AOp5q7AAAAAElFTkSuQmCC"
)


# Le bundle injecté. Idempotent (garde sur window.__SAPFX). Le JS vit dans
# _ui5_bundle.js.tpl (gabarit % : les deux %s sont les listes autorisées).
BUNDLE = (_read_js_template("_ui5_bundle.js.tpl")
          % (_js_string_array(ALLOWED_PROPERTY_PRIORITY),
             _js_string_array(ALLOW_WITHOUT_PROPERTIES))).strip()


def build_call(method):
    """Retourne une expression de fonction qui (ré)installe le bundle puis appelle
    ``window.__SAPFX.<method>(arg)``. Commence par '(' : Playwright ne *lance* pas
    un littéral de fonction commençant par un espace.

    Double forme d'appel (même fonction) :
    * sans sélecteur Browser  -> Playwright appelle ``fn(arg)`` ;
    * avec sélecteur Browser (support iframe Work Zone/cFLP) -> Playwright
      appelle ``fn(element, arg)`` et exécute la fonction **dans le contexte de
      la frame de l'élément** : ``window`` y est la fenêtre de la frame, donc le
      bundle s'installe et résout dans l'app embarquée, pas dans le shell.
    On détecte la forme au nombre d'arguments réellement reçus."""
    return ("(first, second) => { const arg = (second === undefined) ? first : second; "
            "%s; return window.__SAPFX.%s(arg); }" % (BUNDLE, method))


RESOLVE_ROLE_JS = build_call("resolveByRole")
RESOLVE_XPATH_JS = build_call("resolveByXPath")
RESOLVE_WC_JS = build_call("resolveByWc")
RESOLVE_DOM_JS = build_call("resolveByDom")
PAGE_COMPOSITION_JS = build_call("pageComposition")
BEST_XPATH_JS = build_call("bestXpath")
READ_TABLE_JS = build_call("readTable")
DUMP_TREE_JS = build_call("dumpTree")
IDLE_STATE_JS = build_call("idleState")
GET_MESSAGES_JS = build_call("getMessages")


def sid_xpath(sid):
    """Sélecteur navigateur pour un élément SAP WebGUI par son ``SID`` stable.

    Les éléments WebGUI (SAP GUI for HTML) portent un attribut ``lsdata`` où le ``SID``
    (``wnd[0]/usr/...``, le même espace d'ids que le scripting SAP GUI) apparaît sous DEUX
    encodages constatés : JSON ``"SID":"…"`` (fixtures, anciens ITS) ou littéral JS ``SID:'…'``
    (clé non citée, guillemets simples : le WebGUI live S/4 1909, découvert par l'exploration
    agent du 2026-07-18 : l'ancien sélecteur JSON-seul ne matchait RIEN sur un vrai système).
    On compare donc avec deux ``contains()`` XPath, un par encodage. ``sid`` ne doit jamais
    contenir de guillemet (les ids SAP GUI n'en ont jamais) : un guillemet casserait le
    littéral XPath et pourrait rediriger le sélecteur vers un élément arbitraire de la page,
    donc on le rejette plutôt que de l'interpoler tel quel."""
    if "'" in sid or '"' in sid:
        raise ValueError("Invalid SAP GUI SID (must not contain a quote character): %r" % sid)
    return ("xpath=//*[contains(@lsdata, '\"SID\":\"%s\"')"
            " or contains(@lsdata, \"SID:'%s'\")]" % (sid, sid))


# Extrait Spy DevTools autonome, généré depuis le même BUNDLE afin que la logique de capture
# ne diverge jamais du résolveur de la bibliothèque. `tools/recorder_web/recorder_snippet.js`
# est cette chaîne avec un commentaire d'en-tête ; `tests/unit/test_sid_and_spy.py` vérifie que
# le fichier reste synchronisé.
_SPY_LISTENER = _read_js_template("_ui5_spy_listener.js.tpl").strip()

_SPY_HEADER = """\
/*
 * Recorder de localisation UI5 / WebGUI : survolez pour surligner, cliquez pour capturer,
 * ou « rec » pour enregistrer un déroulé d'actions rejouable.
 *
 * Deux façons de l'exécuter sur n'importe quelle page Fiori / SAPUI5 / OpenUI5 (ou une page
 * SAP WebGUI classique pour la capture SID) :
 *   1. collez ce fichier entier dans la console DevTools, ou
 *   2. chargez l'extension navigateur dans tools/recorder_web/extension et cliquez sur son icône.
 *
 * Mode capture (au clic) : lignes prêtes à coller, copiées dans le presse-papiers :
 *   Resolve Ui5 Control    controlType=...    properties={...}
 *   Resolve Ui5 By Xpath    //PlusCourt/Unique/Chemin
 *   Resolve Sid    wnd[0]/usr/...        (éléments WebGUI classiques uniquement)
 *   Resolve Wc Control    tag=...    text=...   (pages UI5 Web Components, hors registre UI5)
 *   Resolve Dom Element    role=...    name=...   (zones non-SAP : React/Angular/vanilla)
 * Mode record (bouton « rec ») : suit vos manipulations en steps ordonnés
 *   (Click/Fill sur les 5 moteurs role/xpath/sid/wc/dom ; clic droit = menu d'assertions
 *   visible/texte, Alt+clic = raccourci ; Entrée capturée en Keyboard Key ; nav -> Wait For
 *   UI5 Ready quand le runtime UI5 est là, Wait For Load State sinon ; re-saisie du même
 *   champ et attentes consécutives compactées).
 *   Steps éditables (déplacer/supprimer/ÉDITER au double-clic), nommables, persistés
 *   (sessionStorage : survivent à un rechargement de page). « play » REJOUE le déroulé
 *   dans la page (mêmes moteurs de résolution, repli xpath essayé, arrêt sur le premier
 *   échec, validation avant export). « +test » démarre un nouveau scénario (marqueur ;
 *   chaque export produit alors plusieurs *** Test Cases ***). Les steps UI5 naissent
 *   avec leur repli xpath en commentaire : l'export resource-first les convertit en
 *   Resolve Ui5 With Fallback (auto-réparables au replay). « export » ouvre un menu :
 *   .robot COMPLET (Settings + New Browser/New Page + steps, keyword Wait For UI5 Ready
 *   embarqué), paire resource-first (.resource keywords métier + .robot sans
 *   localisateur, convention n°1), plan specs/ (.spec.md, l'entrée du cycle
 *   plan -> generate -> heal), rapport HTML auto-contenu (documentation du déroulé :
 *   phrase métier + ligne exacte par step, jamais un test), et IMPORT d'un .robot
 *   exporté (le cycle d'édition se
 *   referme). Un panneau ne peut pas instrumenter une iframe cross-origin :
 *   avertissement affiché, l'extension (allFrames) injecte un panneau par frame.
 *
 * GÉNÉRÉ depuis src/SapFioriLibrary/_ui5_js.py (BUNDLE + écouteur recorder) afin que la
 * logique de capture ne diverge jamais du résolveur de la bibliothèque. Ne pas éditer
 * manuellement : exécuter `python -m SapFioriLibrary.regen_recorder`. Techniques portées depuis
 * playwright-sap (Apache-2.0) ; voir le NOTICE du projet.
 *
 * Le survol met en surbrillance le contrôle ; Échap ou window.__ui5SpyStop() arrête.
 */
"""


def spy_snippet():
    """Retourne le programme Spy autonome complet (en-tête + bundle + écouteur de survol/clic).
    Utilisé à la fois comme extrait à coller dans DevTools et comme script de contenu injecté
    par l'extension."""
    # Le picto aicabra (data-URI) est injecté par token : le gabarit du
    # listener est brut (ses '%' sont littéraux), aucun formatage %s dedans.
    listener = _SPY_LISTENER.replace("__AICABRA_ICON__", _AICABRA_ICON)
    return "%s\n%s\n%s\n" % (_SPY_HEADER, BUNDLE, listener)
