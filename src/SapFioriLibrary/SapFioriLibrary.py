"""SapFioriLibrary : automatisation SAP Fiori / S/4HANA web avec support UI5.

Phase 2 du projet. Une bibliothèque Robot Framework légère qui s'utilise *aux côtés* de
la bibliothèque Browser (Playwright) : Browser gère la page et effectue les clics/saisies ;
cette bibliothèque convertit un **sélecteur de contrôle UI5** stable (par type de contrôle
+ propriétés, ou par un **UI5 XPath** hiérarchique) en cible DOM utilisable par Browser.

La résolution s'appuie sur un bundle JS injecté (`_ui5_js.py`) qui construit un arbre
reflétant la hiérarchie des contrôles UI5 et y effectue les correspondances. Les techniques
d'arbre, de XPath et de correspondance de propriétés sont portées depuis playwright-sap
(Apache-2.0) ; voir le fichier NOTICE du projet.

Validé de bout en bout contre le OpenUI5 Demo Kit public avec Robot Framework 7.4
et Browser 20 (voir `tests/robot/fiori_smoke.robot`).

Utilisation dans une suite::

    Library    Browser
    Library    SapFioriLibrary

    New Browser    chromium    headless=False
    New Page       https://sdk.openui5.org/
    ${sel}=    Resolve Ui5 Control     controlType=sap.m.Button    properties={'text': 'Download'}
    ${sel}=    Resolve Ui5 By Xpath    //Page//Button[@text='Download']
    Click      ${sel}

La couche métier (`resources/fiori_keywords.resource`) encapsule ceci afin que les tests
se lisent de la même façon que du côté ECC : voir `docs/fiori-architecture.md`.
"""
from robot.api import logger
from robot.api.types import Secret
from robot.libraries.BuiltIn import BuiltIn
from robot.utils import secs_to_timestr, timestr_to_secs

from sapfx_common.auth_flows import resolve_preset
from sapfx_common.fiori_diagnostics import (
    normalize_console_entries,
    normalize_page_errors,
    parse_sections,
    render_diagnostics_report,
    summarize_issues,
    tail_entries,
)
from sapfx_common.healing_telemetry import record_healing
from sapfx_common.perception_diff import diff_perception
from sapfx_common.polling import poll_until, retry_until
from sapfx_common.secrets import reveal_secret
from sapfx_common.session_context import current_execution_namespace
from sapfx_common.vocabulary import lookup_as_dict

from ._ui5_js import (
    BEST_XPATH_JS,
    DUMP_TREE_JS,
    PAGE_COMPOSITION_JS,
    READ_TABLE_JS,
    RESOLVE_DOM_JS,
    RESOLVE_ROLE_JS,
    RESOLVE_WC_JS,
    RESOLVE_XPATH_JS,
    sid_xpath,
)
from ._ui5_runtime import (
    _coerce_dict,
    build_control_selector,
    build_dom_selector,
    build_intent_hash,
    build_wc_selector,
    recommended_engines,
    selector_to_json,
    ui5_page_map,
)

# Sélecteur descendant qui remonte de la racine d'un contrôle jusqu'à son élément interactif
# (idée portée depuis playwright-sap getUniqueInteractableHTMLElements).
_INTERACTABLE = ("input, textarea, select, button, "
                 "[role=button], [role=checkbox], [role=radio], [role=link], a")


class SapFioriLibrary:
    """Résout les contrôles UI5 en sélecteurs utilisables par Browser. Nécessite que la
    bibliothèque Browser soit importée dans la même suite (elle réutilise la page active de Browser)."""

    __version__ = "0.6.5"
    ROBOT_LIBRARY_SCOPE = "SUITE"
    ROBOT_LIBRARY_DOC_FORMAT = "ROBOT"

    def _context_state(self):
        namespace = current_execution_namespace()
        return self._state_by_namespace.setdefault(namespace, {})

    @property
    def _frame_stack(self):
        return self._context_state().setdefault("frame_stack", [])

    @property
    def _ui5_frame(self):
        """Portée de frame courante : chaîne ``a >>> b`` (frames imbriquées,
        pile `Push Ui5 Frame`) ou ``None`` (page principale)."""
        stack = self._frame_stack
        return " >>> ".join(stack) if stack else None

    @_ui5_frame.setter
    def _ui5_frame(self, value):
        # compat : assigner une valeur remplace TOUTE la pile (Set Ui5 Frame).
        self._context_state()["frame_stack"] = [value] if value else []

    @property
    def _last_page_tree(self):
        return self._context_state().get("last_page_tree")

    @_last_page_tree.setter
    def _last_page_tree(self, value):
        self._context_state()["last_page_tree"] = value

    def __init__(self, ui5_timeout="15s", poll_interval="0.25s"):
        """``ui5_timeout`` définit la durée pendant laquelle la résolution sonde la présence
        d'un contrôle (rendu de manière asynchrone) avant d'abandonner.

        ``poll_interval`` est le délai entre deux sondages (résolution de contrôle,
        arbre UI5, retry anti *stale element*) : la valeur par défaut convient à un
        navigateur local, mais un environnement distant/plus lent (CI partagée,
        Fiori sur un serveur éloigné) peut bénéficier d'un intervalle plus large
        pour réduire le nombre d'aller-retours JS inutiles."""
        self.ui5_timeout = ui5_timeout
        self.poll_interval = timestr_to_secs(poll_interval)
        self._state_by_namespace = {}
        self._ui5_frame = None
        self._last_page_tree = None

    def set_ui5_timeout(self, timeout):
        """Change le ``ui5_timeout`` de la bibliothèque et retourne l'ancienne valeur.

        ``ui5_timeout`` est le budget de sondage par défaut de la résolution de
        contrôles, de l'arbre UI5 et des retries anti *stale element*, fixé à
        l'import de la bibliothèque, ajustable ici en cours de suite (élargir
        autour d'une app Fiori particulièrement lourde, sans l'imposer à toute
        la suite). Accepte les chaînes de temps Robot (``30s``, ``2 min``).
        L'ancienne valeur est retournée dans le même format, prête à être
        restaurée en teardown :

        | ${old}= | Set Ui5 Timeout | 45s |
        | ... étapes sur l'app lente ... | |
        | Set Ui5 Timeout | ${old} | |

        Le pendant Fiori de `Set Default Timeout` (SapEccLibrary). Portée :
        l'instance de bibliothèque (scope ``SUITE``) ; le réglage ne déborde
        jamais sur la suite suivante.
        """
        previous = secs_to_timestr(timestr_to_secs(self.ui5_timeout))
        timestr_to_secs(timeout)   # valide la chaîne AVANT de l'adopter
        self.ui5_timeout = timeout
        return previous

    def set_poll_interval(self, interval):
        """Change le ``poll_interval`` de la bibliothèque et retourne l'ancienne valeur.

        ``poll_interval`` est le délai entre deux sondages (résolution de
        contrôle, arbre UI5, retry anti *stale element*) : élargissez-le en
        cours de suite pour un navigateur distant/lent (moins d'aller-retours
        JS), resserrez-le pour un run local réactif. Accepte les chaînes de
        temps Robot (``0.5s``, ``250 ms``) ; retourne l'ancienne valeur dans le
        même format, restaurable comme pour `Set Ui5 Timeout`. Même nom et même
        contrat que le keyword miroir de SapEccLibrary : dans une suite
        important les deux bibliothèques, qualifier l'appel
        (``SapFioriLibrary.Set Poll Interval``) ou régler
        `Set Library Search Order`. Portée : l'instance (scope ``SUITE``).
        """
        previous = secs_to_timestr(self.poll_interval)
        self.poll_interval = timestr_to_secs(interval)
        return previous

    # -- contexte de frame (Work Zone / cFLP : apps dans des iframes) ----------

    def set_ui5_frame(self, frame_selector=None):
        """Cible une **iframe** pour toute la résolution UI5 à venir.

        SAP Build Work Zone et le cFLP ouvrent chaque application dans une
        iframe (souvent cross-origin) : le shell top-level n'a PAS les contrôles
        de l'app dans son registre UI5. Donner ici le sélecteur Browser de
        l'iframe (ex. ``iframe[id*="application"]``) fait exécuter le bundle de
        résolution **dans la frame de l'app** et préfixe tous les sélecteurs
        retournés avec ``<frame> >>>`` (chaînage de frames Browser/Playwright).

        Sans argument (ou vide), revient à la page principale, le mode nominal
        pour un FLP ABAP classique (apps dans le même document). Exemple::

            Set Ui5 Frame    iframe[id*="application-"]
            Click Ui5 Control    controlType=Button    properties={'text': 'Go'}
            Set Ui5 Frame    ${EMPTY}    # retour à la page principale

        Remplace TOUTE la pile de frames (voir `Push Ui5 Frame` pour les
        frames imbriquées d'une page hybride)."""
        self._ui5_frame = str(frame_selector).strip() if frame_selector else None
        logger.info("UI5 resolution scope: %s"
                    % (self._ui5_frame or "main page (no frame)"))

    def push_ui5_frame(self, frame_selector):
        """**Empile** une frame sur la portée courante : le mode « pages
        hybrides » de `Set Ui5 Frame`, pour les frames IMBRIQUÉES (un shell
        Work Zone qui embarque une app, qui embarque elle-même une transaction
        WebGUI) : chaque niveau s'empile, la portée effective est le chaînage
        ``niveau1 >>> niveau2`` de Browser. Dépiler avec `Pop Ui5 Frame`. ::

            Push Ui5 Frame    iframe[id*="application-"]
            Push Ui5 Frame    iframe[name="webgui"]
            Click Sid    wnd[0]/tbar[1]/btn[8]
            Pop Ui5 Frame        # retour au niveau app
            Pop Ui5 Frame        # retour à la page principale
        """
        selector = str(frame_selector).strip() if frame_selector else ""
        if not selector:
            raise ValueError("Push Ui5 Frame needs a non-empty frame selector "
                             "(use Set Ui5 Frame with no argument to reset).")
        self._frame_stack.append(selector)
        logger.info("UI5 resolution scope: %s" % self._ui5_frame)

    def pop_ui5_frame(self):
        """Dépile la frame la plus récente (`Push Ui5 Frame`) et retourne son
        sélecteur. Échoue si la pile est vide : un pop de trop est un bug de
        scénario, jamais ignoré silencieusement."""
        stack = self._frame_stack
        if not stack:
            raise AssertionError(
                "Pop Ui5 Frame: the frame stack is empty (already on the main "
                "page). Pair each Pop with a Push Ui5 Frame.")
        popped = stack.pop()
        logger.info("UI5 resolution scope: %s"
                    % (self._ui5_frame or "main page (no frame)"))
        return popped

    def get_ui5_frame_stack(self):
        """Retourne la pile de frames courante (liste de sélecteurs, du niveau
        le plus externe au plus interne ; vide = page principale). Lecture
        seule, JSON-safe, pour le débogage et les agents rf-mcp."""
        return list(self._frame_stack)

    # -- mots-clés de résolution ----------------------------------------------

    def resolve_ui5_control(self, index=0, **selector_parts):
        """Résout un contrôle UI5 par type/propriétés vers un sélecteur Browser.

        Accepte l'un des paramètres suivants : ``controlType`` (``sap.m.Button`` ou simplement
        ``Button``), ``properties`` (sous-chaîne + insensible à la casse, ou ``/regex/flags``),
        ``id``, ``bindingPath``, ``viewId``. Retourne ``css=[id="<controlId>"]``.

        Lorsque plusieurs contrôles correspondent, ``index`` (base 0) en sélectionne un ;
        le nombre de correspondances est journalisé afin qu'un sélecteur ambigu soit visible
        et ne soit jamais tronqué silencieusement.

        ``idSuffix`` matche la **fin** de l'id du contrôle : le motif des ids
        stables Fiori Elements V4 (``idSuffix=fe::table::<Entity>::LineItem::Table``),
        dont le préfixe app/route varie mais dont le suffixe est déterministe.
        """
        selector = build_control_selector(**selector_parts)
        ids = self._resolve(RESOLVE_ROLE_JS, selector_to_json(selector), str(selector))
        if not ids:
            raise AssertionError(
                "No UI5 control matched %s on the current page.%s"
                % (selector, self._relaxed_hint(selector_parts)))
        return self._pick(ids, int(index), str(selector))

    def resolve_ui5_by_xpath(self, xpath, index=0):
        """Résout un contrôle via un **UI5 XPath hiérarchique** sur l'arbre des contrôles.

        Les noms de balises de l'arbre correspondent aux types courts des contrôles et les
        attributs aux propriétés des contrôles, ce qui permet d'exprimer l'ancestralité et
        des prédicats, par exemple::

            //Table//ColumnListItem//Button[@text='Edit']
            //Page[@title='Orders']//SearchField

        Retourne ``css=[id="<controlId>"]`` pour la ``index``-ième correspondance (la première
        par défaut). Remarque : la correspondance d'attributs XPath est exacte/`contains()`
        selon XPath 1.0 ; utiliser `Resolve Ui5 Control` pour une correspondance insensible
        à la casse ou par sous-chaîne.
        """
        ids = self._resolve(RESOLVE_XPATH_JS, xpath, xpath)
        return self._pick(ids, int(index), "xpath %s" % xpath)

    def ui5_control_should_be_visible(self, **selector_parts):
        """Vérifie qu'au moins un contrôle UI5 correspond au sélecteur et est rendu."""
        selector = build_control_selector(**selector_parts)
        ids = self._resolve(RESOLVE_ROLE_JS, selector_to_json(selector), str(selector))
        if not ids:
            raise AssertionError("Expected a UI5 control matching %s, found none.%s"
                                 % (selector, self._relaxed_hint(selector_parts)))

    def get_ui5_match_count(self, **selector_parts):
        """Retourne le nombre de contrôles rendus qui correspondent actuellement au sélecteur (0+).
        N'attend pas : utile pour les assertions sur la cardinalité de listes/tableaux."""
        selector = build_control_selector(**selector_parts)
        ids = self._evaluate(RESOLVE_ROLE_JS, arg=selector_to_json(selector)) or []
        return len(ids)

    def get_ui5_xpath(self, index=0, **selector_parts):
        """Résout un contrôle puis retourne son **UI5 XPath unique le plus court**.

        Porté depuis playwright-sap : le ``//suffixe`` le plus court du chemin du contrôle dans
        l'arbre qui résout toujours vers exactement ce contrôle. Pratique pour la génération de
        code et pour convertir un contrôle trouvé en localisateur hiérarchique stable et lisible::

            ${xpath}=    Get Ui5 Xpath    controlType=SearchField    # -> //SearchField
            ${sel}=      Resolve Ui5 By Xpath    ${xpath}
        """
        selector = build_control_selector(**selector_parts)
        ids = self._resolve(RESOLVE_ROLE_JS, selector_to_json(selector), str(selector))
        dom_id = self._pick_id(ids, index, selector)
        xpath = self._evaluate(BEST_XPATH_JS, arg=dom_id)
        if not xpath:
            raise AssertionError("Could not compute a UI5 XPath for control '%s'." % dom_id)
        return xpath

    def resolve_ui5_with_fallback(self, xpath=None, sid=None, wc=None, dom=None,
                                  attempt_timeout="3s", **selector_parts):
        """Résout un contrôle par **chaîne de fallback** : rôle -> UI5 XPath -> SID -> WC -> DOM.

        Le pattern d'auto-réparation des localisateurs (jamais silencieux) : on
        essaie chaque forme de sélecteur fournie, dans l'ordre de stabilité
        décroissante, avec ``attempt_timeout`` par tentative. Si un repli
        aboutit, un WARNING journalise quel localisateur primaire a dérivé : le
        test passe, la dérive est visible et corrigeable dans ``resources/``
        (et consignée dans le journal de télémétrie si ``SAPFX_HEALING_LOG``
        est défini, voir ``sapfx_common.healing_telemetry``). ::

            ${sel}=    Resolve Ui5 With Fallback
            ...    controlType=Button    properties={'text': 'Commander'}
            ...    xpath=//Dialog//Button[2]
            ...    sid=wnd[0]/tbar[1]/btn[8]
            ...    wc={'tag': 'Button', 'text': 'Commander'}

        ``wc=`` (dict ou littéral de dict) est le repli Web Components
        (`Resolve Wc Control`), pour une app re-plateformée en UI5 Web
        Components dont le registre UI5 a disparu. ``dom=`` (dict ou littéral
        de dict, clés de `Resolve Dom Element`) est le DERNIER repli : le
        moteur DOM générique, pour une zone re-plateformée hors de tout cadre
        SAP (widget React/Angular…). Échoue (avec le détail par moteur) si
        aucune forme ne résout. Au moins une forme (rôle, ``xpath=``,
        ``sid=``, ``wc=`` ou ``dom=``) est requise."""
        attempts = []
        if selector_parts:
            selector = build_control_selector(**selector_parts)
            attempts.append(("role %s" % selector, lambda: self._pick(
                self._resolve(RESOLVE_ROLE_JS, selector_to_json(selector),
                              str(selector), timeout=attempt_timeout),
                0, str(selector))))
        if xpath:
            attempts.append(("xpath %s" % xpath, lambda: self._pick(
                self._resolve(RESOLVE_XPATH_JS, xpath, xpath, timeout=attempt_timeout),
                0, "xpath %s" % xpath)))
        if sid:
            def _try_sid():
                selector = self.resolve_sid(sid)
                self._wait_visible(selector, timeout=attempt_timeout)
                return selector
            attempts.append(("sid %s" % sid, _try_sid))
        if wc:
            wc_selector = build_wc_selector(**_coerce_dict(wc, "wc"))
            attempts.append(("wc %s" % wc_selector, lambda: self._pick_wc(
                self._resolve(RESOLVE_WC_JS, selector_to_json(wc_selector),
                              "wc %s" % wc_selector, timeout=attempt_timeout),
                0, "wc %s" % wc_selector)))
        if dom:
            dom_selector = build_dom_selector(**_coerce_dict(dom, "dom"))
            attempts.append(("dom %s" % dom_selector, lambda: self._pick_wc(
                self._resolve(RESOLVE_DOM_JS, selector_to_json(dom_selector),
                              "dom %s" % dom_selector, timeout=attempt_timeout),
                0, "dom %s" % dom_selector, noun="DOM element")))
        if not attempts:
            raise ValueError("Resolve Ui5 With Fallback needs at least one of: "
                             "role selector parts, xpath=, sid=, wc=, dom=.")
        failures = []
        for position, (description, attempt) in enumerate(attempts):
            try:
                resolved = attempt()
            except Exception as err:
                failures.append("%s -> %s" % (description, err))
                continue
            if position > 0:
                logger.warn(
                    "Localisateur réparé par fallback (%s) ; le localisateur "
                    "primaire a dérivé : %s. Mettre à jour resources/."
                    % (description, " ; ".join(failures)))
                record_healing("fiori", original=attempts[0][0], healed=description,
                               engine=description.split(" ", 1)[0])
            return resolved
        raise AssertionError(
            "No fallback resolved the control. Attempts: %s\n"
            "Every engine failed. Call Log Fiori Diagnostics for the whole "
            "picture (page composition, UI5 tree, console errors, frame "
            "scope), or Get Page Composition if you only need the engines "
            "to try." % " ; ".join(failures))

    # -- moteur 'sid' SAP WebGUI (SAP GUI for HTML) ---------------------------

    def resolve_sid(self, sid):
        """Résout un élément **SAP WebGUI** par son ``SID`` stable vers un sélecteur
        Browser. Le SID est l'identifiant de script SAP GUI (``wnd[0]/usr/ctxtVBAK-VBELN``)
        porté dans l'attribut ``lsdata`` de l'élément sur les pages WebGUI classiques /
        SAP GUI for HTML, *pas* Fiori/UI5. Retourne un sélecteur ``xpath=``.
        Respecte `Set Ui5 Frame` (page WebGUI embarquée dans un launchpad)."""
        return self._scoped_selector(sid_xpath(sid))

    def click_sid(self, sid):
        """Clique sur un élément SAP WebGUI par son SID."""
        self._browser().click(self.resolve_sid(sid))

    def fill_sid_input(self, sid, text):
        """Remplit un champ de saisie SAP WebGUI (par SID) avec ``text``."""
        base = self.resolve_sid(sid)
        self._browser().fill_text(base, text)

    def sid_should_be_visible(self, sid):
        """Vérifie qu'un élément SAP WebGUI avec le SID donné est visible."""
        self._wait_visible(self.resolve_sid(sid))

    # -- moteur Web Components (pages UI5 Web Components, hors registre UI5) ---

    def resolve_wc_control(self, index=0, **selector_parts):
        """Résout un **UI5 Web Component** (custom element ``ui5-*``) en sélecteur Browser.

        Troisième moteur de résolution, pour les pages « pur Web Components »
        (ex. home SuccessFactors, apps ui5-webcomponents) où il n'y a PAS de
        runtime UI5 classique : le registre est vide, `Resolve Ui5 Control` et
        `Resolve Ui5 By Xpath` ne voient rien. Scanne les hôtes custom elements
        du light DOM ; leurs internals vivent dans des shadow roots ouverts, que
        le CSS de Playwright perce pour le clic/la saisie.

        Clés : ``tag`` (type court ``Button`` ou tag complet ``ui5-button``,
        matche aussi les tags **scopés** ``ui5-button-<suffixe>``), ``text``
        (sous-chaîne insensible à la casse ou ``/regex/`` sur le textContent),
        ``name`` (**nom accessible** de l'hôte, accname simplifié :
        ``aria-labelledby``, ``aria-label``, ``accessible-name``/
        ``accessibleName`` (la convention UI5 Web Components), label,
        texte ; le localisateur au plus près de l'intention utilisateur),
        ``properties`` (attributs/propriétés de l'hôte, mêmes règles de matching
        que le moteur role), ``id`` / ``idSuffix``. Retourne un sélecteur
        ``css=`` : un chemin light-DOM ancré à l'ancêtre à id le plus proche,
        car les hôtes WC n'ont souvent pas d'id propre. ::

            ${sel}=    Resolve Wc Control    tag=Button    text=Créer
            Click    ${sel}
        """
        selector = build_wc_selector(**selector_parts)
        description = "wc %s" % selector
        paths = self._resolve(RESOLVE_WC_JS, selector_to_json(selector), description)
        if not paths:
            raise AssertionError(
                "No ui5-* web component matched %s on the current page. This engine "
                "scans light-DOM custom elements (tag prefix ui5-). For a classic "
                "UI5 app, use Resolve Ui5 Control instead." % (selector,))
        return self._pick_wc(paths, int(index), description)

    def wc_control_should_be_visible(self, **selector_parts):
        """Vérifie qu'au moins un Web Component ``ui5-*`` correspond au sélecteur
        et est rendu (rect non nul). Pendant WC de `Ui5 Control Should Be Visible`."""
        selector = build_wc_selector(**selector_parts)
        paths = self._resolve(RESOLVE_WC_JS, selector_to_json(selector), "wc %s" % selector)
        if not paths:
            raise AssertionError(
                "Expected a ui5-* web component matching %s, found none." % (selector,))

    def get_wc_match_count(self, **selector_parts):
        """Nombre de Web Components ``ui5-*`` rendus qui correspondent au sélecteur
        (0+). N'attend pas ; pendant WC de `Get Ui5 Match Count`."""
        selector = build_wc_selector(**selector_parts)
        paths = self._evaluate(RESOLVE_WC_JS, arg=selector_to_json(selector)) or []
        return len(paths)

    def click_wc_control(self, index=0, **selector_parts):
        """Résout un Web Component ``ui5-*`` et clique dessus via Browser.
        Re-résout à chaque tentative (*stale element*, cf. `Click Ui5 Control`)."""
        self._act_with_retry(
            lambda: self._browser().click(
                self.resolve_wc_control(index=index, **selector_parts)),
            "click wc %s" % (selector_parts or "index %s" % index))

    def fill_wc_input(self, text, index=0, **selector_parts):
        """Résout un champ de saisie Web Component (``ui5-input``…) et le remplit.

        L'``<input>`` réel vit dans le **shadow root** (ouvert) de l'hôte : le
        sélecteur descend dedans via le CSS de Playwright, qui perce les shadow
        roots ouverts. Re-résout puis ré-essaie en cas d'échec transitoire."""
        def _fill():
            selector = build_wc_selector(**selector_parts)
            paths = self._resolve(RESOLVE_WC_JS, selector_to_json(selector),
                                  "wc %s" % selector)
            path = self._pick_id(paths, int(index), "wc %s" % selector,
                                 noun="web component")
            self._browser().fill_text(
                self._scoped_selector("css=%s input, %s textarea" % (path, path)), text)
        self._act_with_retry(_fill, "fill wc %s" % (selector_parts or "index %s" % index))

    def get_wc_text(self, index=0, **selector_parts):
        """Résout un Web Component ``ui5-*`` et retourne son texte visible."""
        return self._browser().get_text(self.resolve_wc_control(index=index, **selector_parts))

    # -- moteur DOM générique (zones non-SAP d'une page hybride) ---------------

    def resolve_dom_element(self, index=0, **selector_parts):
        """Résout un **élément DOM générique** en sélecteur Browser : le 5e
        moteur, pour les zones NON-SAP d'une page hybride.

        Un shell Fiori peut embarquer un widget React/Angular/vanilla (portlet
        Work Zone, aide custom, composant maison) qu'aucun moteur SAP ne voit :
        pas de registre UI5, pas d'hôte ``ui5-*``, pas de ``lsdata`` WebGUI.
        Ce moteur le fait entrer dans la même grammaire que les autres,
        polling jusqu'au rendu, chaîne de fallback (``dom=``) et télémétrie de
        healing comprises, au lieu de retomber sur des sélecteurs Browser
        bruts hors bibliothèque.

        Clés : ``css`` (sélecteur CSS de base restreignant le scan), ``tag``,
        ``text`` (sous-chaîne insensible à la casse ou ``/regex/``), ``role``
        (rôle ARIA **calculé** : attribut ``role`` explicite OU rôle implicite
        de la sémantique HTML : ``button``, ``a[href]`` -> ``link``,
        ``input[type=checkbox]`` -> ``checkbox``, ``h1``-``h6`` ->
        ``heading``… ; insensible à la casse), ``name`` (**nom accessible**,
        accname simplifié : ``aria-labelledby``, ``aria-label``,
        ``label[for]``/englobant, ``alt``, texte… ; le localisateur au plus
        près de l'intention utilisateur, comme le ``getByRole(name=…)`` de
        Playwright), ``id`` / ``idSuffix``, ``properties`` (attributs, mêmes
        règles de matching que les moteurs role/wc). Seuls les éléments RENDUS
        (rect non nul) sont retournés. Respecte `Set Ui5 Frame` /
        `Push Ui5 Frame`. ::

            ${sel}=    Resolve Dom Element    role=button    name=Valider
            Click    ${sel}

        Sur une zone SAP, préférer TOUJOURS le moteur dédié (`Resolve Ui5
        Control`, `Resolve Sid`, `Resolve Wc Control`), plus stable ; `Get
        Page Composition` dit lequel s'applique où."""
        selector = build_dom_selector(**selector_parts)
        description = "dom %s" % selector
        paths = self._resolve(RESOLVE_DOM_JS, selector_to_json(selector), description)
        if not paths:
            raise AssertionError(
                "No DOM element matched %s on the current page (an invalid css= "
                "value also yields zero matches). For a SAP region, use the "
                "dedicated engine instead. Call Get Page Composition to see "
                "which technologies this page hosts." % (selector,))
        return self._pick_wc(paths, int(index), description, noun="DOM element")

    def dom_element_should_be_visible(self, **selector_parts):
        """Vérifie qu'au moins un élément DOM générique correspond au sélecteur
        et est rendu (rect non nul). Pendant DOM de `Ui5 Control Should Be Visible`."""
        selector = build_dom_selector(**selector_parts)
        paths = self._resolve(RESOLVE_DOM_JS, selector_to_json(selector),
                              "dom %s" % selector)
        if not paths:
            raise AssertionError(
                "Expected a DOM element matching %s, found none." % (selector,))

    def get_dom_match_count(self, **selector_parts):
        """Nombre d'éléments DOM rendus qui correspondent au sélecteur (0+).
        N'attend pas ; pendant DOM de `Get Ui5 Match Count`."""
        selector = build_dom_selector(**selector_parts)
        paths = self._evaluate(RESOLVE_DOM_JS, arg=selector_to_json(selector)) or []
        return len(paths)

    def click_dom_element(self, index=0, **selector_parts):
        """Résout un élément DOM générique et clique dessus via Browser.
        Re-résout à chaque tentative (*stale element*, cf. `Click Ui5 Control`)."""
        self._act_with_retry(
            lambda: self._browser().click(
                self.resolve_dom_element(index=index, **selector_parts)),
            "click dom %s" % (selector_parts or "index %s" % index))

    def fill_dom_input(self, text, index=0, **selector_parts):
        """Résout un champ de saisie DOM générique et le remplit avec ``text``.

        La cible peut être l'``<input>``/``<textarea>`` lui-même OU un
        conteneur : le sélecteur émis matche d'abord l'élément résolu s'il est
        saisissable, sinon descend vers son premier champ interne. Re-résout
        puis ré-essaie en cas d'échec transitoire."""
        def _fill():
            selector = build_dom_selector(**selector_parts)
            paths = self._resolve(RESOLVE_DOM_JS, selector_to_json(selector),
                                  "dom %s" % selector)
            path = self._pick_id(paths, int(index), "dom %s" % selector,
                                 noun="DOM element")
            self._browser().fill_text(
                self._scoped_selector(
                    "css=%s:is(input, textarea), %s input, %s textarea"
                    % (path, path, path)), text)
        self._act_with_retry(_fill, "fill dom %s" % (selector_parts or "index %s" % index))

    def get_dom_text(self, index=0, **selector_parts):
        """Résout un élément DOM générique et retourne son texte visible."""
        return self._browser().get_text(self.resolve_dom_element(index=index, **selector_parts))

    # -- sonde de composition (perception des pages hybrides) ------------------

    def get_page_composition(self, include_frames=True):
        """Sonde la **composition technologique** de la page courante : la
        perception d'une page HYBRIDE (shell UI5 + iframe WebGUI + widget web
        générique cohabitant dans le même écran).

        Retourne un dict JSON-safe (utilisable à travers rf-mcp) :

        * ``ui5_runtime`` / ``ui5_version`` / ``ui5_controls`` : runtime UI5
          classique présent (moteurs *role*/*xpath* utilisables) ;
        * ``wc_hosts`` : hôtes UI5 Web Components (moteur *wc*) ;
        * ``webgui_elements`` : éléments ``lsdata`` SAP GUI for HTML (moteur *sid*) ;
        * ``frameworks`` : indices React/Angular/Vue (moteur *dom*) ;
        * ``engines`` : les moteurs recommandés pour CETTE région, dans
          l'ordre d'essai de `Resolve Ui5 With Fallback` ;
        * ``frames`` : chaque iframe du document avec son sélecteur Browser
          réutilisable (`Set Ui5 Frame` / `Push Ui5 Frame`) et, si
          ``include_frames`` (défaut), SA composition sondée à son tour
          (champ ``composition``). C'est là que l'hybridation se voit : un
          launchpad Work Zone rapporte un shell sans contrôles et une app
          UI5 par frame. Une frame insondable porte un champ ``error`` au
          lieu de faire échouer la perception (best-effort). La descente
          fait UN niveau : pour aller plus profond, `Push Ui5 Frame` puis
          re-sonder.

        Respecte `Set Ui5 Frame` / `Push Ui5 Frame` : la sonde part de la
        portée courante. Lecture seule, le pendant hybride de `Get Ui5 Page
        Tree`, à appeler en premier sur un écran inconnu pour savoir QUEL
        moteur adresser où."""
        composition = self._evaluate(PAGE_COMPOSITION_JS, arg=None)
        if not isinstance(composition, dict):
            raise AssertionError(
                "Could not probe the page composition (no document?). "
                "Is a page open in the Browser library?")
        composition["engines"] = recommended_engines(composition)
        if include_frames:
            for frame in composition.get("frames", []):
                frame_scope = self._scoped_selector(frame["selector"])
                try:
                    sub = self._browser().evaluate_javascript(
                        "%s >>> css=body" % frame_scope,
                        PAGE_COMPOSITION_JS, arg=None)
                    if isinstance(sub, dict):
                        sub["engines"] = recommended_engines(sub)
                        frame["composition"] = sub
                    else:
                        frame["error"] = "frame document not probeable"
                except Exception as err:
                    frame["error"] = str(err)
        return composition

    # -- diagnostic agrégé (inspiré des briques Browser 20) --------------------

    def get_fiori_diagnostics(self, sections="composition,tree,console,errors,aria",
                              tree_timeout="3s", full_logs=False,
                              max_log_entries=50, aria_selector="css=body"):
        """Agrège en UN dict JSON-safe les vues de diagnostic de la page
        courante : la perception « pourquoi ça ne marche pas » d'un écran
        Fiori/hybride, pensée pour rf-mcp et le débogage de suite :

        * ``composition`` : la sonde `Get Page Composition` (technologies par
          région + moteurs recommandés + iframes) ;
        * ``ui5_tree`` : l'arbre de contrôles UI5 (XML, portée courante),
          sondé pendant ``tree_timeout`` seulement (défaut 3s : un diagnostic
          sur une page non-UI5 ne doit pas bloquer ``ui5_timeout`` entier) ;
          ``None`` si absent, ce qui devient une anomalie NOMMANT les
          moteurs/frames de repli. Ne touche PAS l'état ``mode=diff`` de
          `Get Ui5 Page Tree` ;
        * ``console`` / ``page_errors`` : `Get Console Log` / `Get Page
          Errors` de Browser 20, normalisés en dicts à forme stable
          ``{type, text, location, time}`` / ``{name, message, stack, time}``.
          Par défaut (``full_logs=False``, la sémantique Browser), chaque
          appel ne retourne que les entrées NOUVELLES depuis le précédent,
          l'esprit ``mode=diff`` ; ``full_logs=True`` relit tout. Les listes
          gardent les ``max_log_entries`` plus récentes (troncature annoncée
          dans ``console_dropped``/``page_errors_dropped``, jamais
          silencieuse) ;
        * ``aria`` : snapshot ARIA YAML (`Get Aria Snapshot`) de
          ``aria_selector`` (défaut ``css=body``, préfixé par la frame
          courante) : la vue sémantique des zones NON-SAP qu'aucun moteur ne
          modélise ;
        * ``issues`` : la synthèse actionnable, erreurs JS/console comptées
          (première citée), arbre UI5 absent avec les moteurs recommandés à
          la place, sections insondables.

        ``sections`` (chaîne ``a,b,c`` ou liste) restreint la collecte ;
        section inconnue = erreur listant les valides. Chaque section est
        best-effort : une collecte qui échoue est consignée dans
        ``collection_errors`` (et dans ``issues``) au lieu de faire échouer
        le diagnostic. Lecture seule. Respecte `Set Ui5 Frame` /
        `Push Ui5 Frame` (composition, arbre et ARIA sondent la portée
        courante ; console et erreurs de page sont PAR PAGE, toutes frames
        confondues, c'est Playwright qui les collecte). ::

            ${diag}=    Get Fiori Diagnostics
            Should Be Empty    ${diag}[issues]
        """
        wanted = parse_sections(sections)
        browser = self._browser()
        diagnostics = {"sections": wanted, "frame_scope": self._ui5_frame}
        collection_errors = {}
        for key in ("url", "title"):
            try:
                diagnostics[key] = str(getattr(browser, "get_%s" % key)())
            except Exception:
                pass    # contexte facultatif : une page absente se voit dans les sections
        if "composition" in wanted:
            try:
                diagnostics["composition"] = self.get_page_composition()
            except Exception as err:
                collection_errors["composition"] = str(err)
        if "tree" in wanted:
            def _dump_tree():
                try:
                    return self._evaluate(DUMP_TREE_JS, arg=None)
                except Exception:
                    return None
            diagnostics["ui5_tree"] = poll_until(
                _dump_tree, timestr_to_secs(tree_timeout),
                step=self.poll_interval) or None
        if "console" in wanted:
            try:
                entries = normalize_console_entries(
                    browser.get_console_log(full=bool(full_logs)))
                kept, dropped = tail_entries(entries, int(max_log_entries))
                diagnostics["console"] = kept
                if dropped:
                    diagnostics["console_dropped"] = dropped
            except Exception as err:
                collection_errors["console"] = str(err)
        if "errors" in wanted:
            try:
                entries = normalize_page_errors(
                    browser.get_page_errors(full=bool(full_logs)))
                kept, dropped = tail_entries(entries, int(max_log_entries))
                diagnostics["page_errors"] = kept
                if dropped:
                    diagnostics["page_errors_dropped"] = dropped
            except Exception as err:
                collection_errors["errors"] = str(err)
        if "aria" in wanted:
            try:
                diagnostics["aria"] = str(browser.get_aria_snapshot(
                    self._scoped_selector(str(aria_selector))))
            except Exception as err:
                collection_errors["aria"] = str(err)
        if collection_errors:
            diagnostics["collection_errors"] = collection_errors
        diagnostics["issues"] = summarize_issues(diagnostics)
        return diagnostics

    def log_fiori_diagnostics(self, sections="composition,tree,console,errors,aria",
                              tree_timeout="3s", full_logs=False,
                              max_log_entries=50, aria_selector="css=body"):
        """Collecte `Get Fiori Diagnostics` (mêmes paramètres) puis écrit le
        **rapport Markdown** dans le log Robot : anomalies d'abord, puis chaque
        section en résumé compact. Retourne le dict complet, pour enchaîner une
        assertion sur ``issues`` après coup. Le réflexe de fin de test en échec::

            [Teardown]    Run Keyword If Test Failed    Log Fiori Diagnostics
        """
        diagnostics = self.get_fiori_diagnostics(
            sections=sections, tree_timeout=tree_timeout, full_logs=full_logs,
            max_log_entries=max_log_entries, aria_selector=aria_selector)
        logger.info(render_diagnostics_report(diagnostics))
        return diagnostics

    # -- raccourcis d'interaction ---------------------------------------------

    def click_ui5_control(self, index=0, **selector_parts):
        """Résout le contrôle et clique dessus via la bibliothèque Browser.

        Re-résout puis re-clique en cas d'échec transitoire : entre la résolution et
        le clic, une vue Fiori peut se redessiner et invalider l'élément (*stale
        element*). Chaque tentative repart d'une résolution fraîche."""
        self._act_with_retry(
            lambda: self._browser().click(
                self.resolve_ui5_control(index=index, **selector_parts)),
            "click %s" % (selector_parts or "index %s" % index))

    def click_ui5_by_xpath(self, xpath, index=0):
        """Résout un **UI5 XPath hiérarchique** puis clique le contrôle obtenu.

        Pendant de `Click Ui5 Control` pour les localisateurs XPath (ex. cibler un
        bouton à l'intérieur d'un dialogue : ``//Dialog//Button[@text='OK']``).
        Re-résout à chaque tentative pour absorber un re-rendu (*stale element*)."""
        self._act_with_retry(
            lambda: self._browser().click(self.resolve_ui5_by_xpath(xpath, index=index)),
            "click xpath %s" % xpath)

    def fill_ui5_input(self, text, index=0, **selector_parts):
        """Résout un champ de saisie UI5 et le remplit avec ``text`` via Browser.

        Les champs UI5 composites (``sap.m.Input``, ``SearchField``…) rendent un élément
        interne ``<input>``/``<textarea>`` ; on s'y positionne, il est impossible de saisir
        directement dans le ``<div>`` racine du contrôle. Re-résout puis ré-essaie en
        cas d'échec transitoire (*stale element* après re-rendu).
        """
        def _fill():
            selector = build_control_selector(**selector_parts)
            ids = self._resolve(RESOLVE_ROLE_JS, selector_to_json(selector), str(selector))
            if not ids:
                raise AssertionError(
                    "No UI5 control matched %s on the current page.%s"
                    % (selector, self._relaxed_hint(selector_parts)))
            dom_id = self._pick_id(ids, int(index), selector)
            attr = '[id="%s"]' % dom_id
            self._browser().fill_text(
                self._scoped_selector("css=%s input, %s textarea" % (attr, attr)), text)
        self._act_with_retry(_fill, "fill %s" % (selector_parts or "index %s" % index))

    def read_ui5_table(self, index=0, **selector_parts):
        """Lit une table UI5 en une liste de dicts ``[{en-tête: valeur, ...}]``.

        Pendant Fiori de `Read Grid` (ECC). Résout la table (``sap.m.Table`` ou
        ``sap.ui.table.Table``) puis extrait ses lignes via le bundle : clés = textes
        d'en-tête de colonne (ou ``col<i>`` à défaut). Ne lit que les lignes
        **instanciées** : ``sap.ui.table.Table`` virtualise, faire défiler d'abord
        pour les grandes tables. Les lignes d'en-tête de groupe sont ignorées.
        """
        selector = build_control_selector(**selector_parts)
        ids = self._resolve(RESOLVE_ROLE_JS, selector_to_json(selector), str(selector))
        dom_id = self._pick_id(ids, index, selector, noun="table")
        rows = self._evaluate(READ_TABLE_JS, arg=dom_id)
        return rows or []

    def get_ui5_text(self, index=0, **selector_parts):
        """Résout un contrôle et retourne son texte visible via `Get Text` de Browser."""
        return self._browser().get_text(self.resolve_ui5_control(index=index, **selector_parts))

    def ui5_text_should_be(self, expected, index=0, **selector_parts):
        """Vérifie que le texte visible du contrôle résolu vaut ``expected``
        (comparaison exacte après trim). C'est l'assertion de VALEUR émise par le
        recorder web (Shift+Alt+clic), pendant de `Ui5 Control Should Be Visible`
        pour le contenu. ::

            Ui5 Text Should Be    42,00 EUR    idSuffix=fe::HeaderInfo::NetAmount
        """
        actual = self.get_ui5_text(index=index, **selector_parts)
        if str(actual).strip() != str(expected).strip():
            raise AssertionError(
                "UI5 control %s text is %r, expected %r."
                % (selector_parts or ("index %s" % index), actual, expected))

    def get_ui5_page_tree(self, mode="full"):
        """Retourne l'arbre des contrôles UI5 de la page courante, sérialisé en XML.

        Chaque nœud = un contrôle : balise = type court (``Button``), attributs =
        ``id``, ``controlType`` plein, et les propriétés primitives autorisées
        (``text``, ``value``…). C'est le pendant Fiori de `Get Screen Signature`
        (ECC) : une vue de l'écran qu'un agent IA (plugin rf-mcp) lit pour *voir*
        les contrôles disponibles avant d'en déduire un sélecteur role/xpath stable.

        ``mode=diff`` retourne le **différentiel** depuis l'appel précédent de ce
        keyword sur cette instance (balises ``- `` disparues / ``+ `` apparues,
        inchangé résumé) : après une action, « ce qui a changé » suffit à l'agent
        pour une fraction des tokens. Premier appel en diff : arbre complet.
        La page est TOUJOURS relue (jamais de cache) ; seul le rendu diffère.

        Lecture seule. Sonde jusqu'à ``ui5_timeout`` que le noyau UI5 soit prêt.
        Respecte `Set Ui5 Frame` (arbre de l'app embarquée, pas du shell).
        Lève une exception si la page n'est pas une application UI5."""
        def _dump_tree():
            try:
                return self._evaluate(DUMP_TREE_JS, arg=None)
            except Exception:
                # transitoire pendant un re-rendu (ex. navigation par hash) : le
                # sondage doit continuer, pas s'interrompre sur la première erreur.
                return None

        tree = poll_until(_dump_tree, timestr_to_secs(self.ui5_timeout), step=self.poll_interval)
        if not tree:
            raise AssertionError(
                "No UI5 control tree on the current page (UI5 not ready, or "
                "not a UI5 app). Call Get Page Composition to see which "
                "technologies this page hosts (and which engines/frames to "
                "use), or Log Fiori Diagnostics for the full report.")
        previous = self._last_page_tree
        self._last_page_tree = tree
        if str(mode).strip().lower() == "diff":
            return diff_perception(previous, tree, xml=True)
        return tree

    # -- carte numérotée + action par référence (@N) ---------------------------
    # Miroir Fiori de Get Screen Map / Click Screen Ref (ECC) : le patron
    # « map / @e1 » agent-first (cf. Vibium) : la carte numérote les cibles
    # actionnables de l'arbre UI5, l'agent agit par numéro. Références
    # éphémères (dernière carte de l'instance), re-vérifiées avant chaque
    # action contre le registre UI5 rendu.

    def get_ui5_page_map(self, include_types=None):
        """Retourne la **carte numérotée** de la page UI5 courante : une ligne
        par cible actionnable : champs saisissables (``* ``, valeur courante
        affichée) et cibles cliquables, avec libellé humain (text/title/
        placeholder/tooltip, ``?`` à défaut), id de contrôle et type court ::

            # ui5 page map : 2 actionable target(s)
            @1\t* Search\tcontainer---app--searchField\tSearchField\t=
            @2\t  Go\tcontainer---app--goBtn\tButton

        Chaque numéro devient une **référence éphémère** pour `Resolve Ui5
        Ref`, `Click Ui5 Ref` et `Fill Ui5 Ref` : l'agent lit la carte puis
        agit par ``@N`` sans recopier l'id (la résolution re-vérifie que le
        contrôle est toujours rendu). ``include_types`` (types courts séparés
        par des virgules, ex. ``ColumnListItem,StandardListItem``) remplace la
        sélection par défaut, utile pour numéroter les lignes d'une liste.
        Respecte `Set Ui5 Frame`. Lecture seule ; ne touche pas la mémoire du
        ``mode=diff`` de `Get Ui5 Page Tree`. Dans une SUITE, rester sur les
        localisateurs de ``resources/`` (convention #1) : les ``@N`` sont
        réservés au pilotage interactif."""
        def _dump_tree():
            try:
                return self._evaluate(DUMP_TREE_JS, arg=None)
            except Exception:
                return None

        tree = poll_until(_dump_tree, timestr_to_secs(self.ui5_timeout),
                          step=self.poll_interval)
        if not tree:
            raise AssertionError(
                "No UI5 control tree on the current page (UI5 not ready, or "
                "not a UI5 app). No map to number. Call Get Page Composition "
                "to see which technologies this page hosts (and which "
                "engines/frames to use).")
        lines, refs = ui5_page_map(tree, include_types)
        self._ui5_refs = refs
        header = "# ui5 page map : %d actionable target(s)" % len(refs)
        return "\n".join([header] + lines)

    def _validate_ui5_ref(self, ref):
        """Valide une référence ``@N``/``N`` contre la dernière carte :
        échec IMMÉDIAT (hors budget de retry) si aucune carte n'a été relevée
        ou si le numéro est inconnu. Retourne ``(numéro, id de contrôle)``."""
        refs = getattr(self, "_ui5_refs", None)
        if not refs:
            raise AssertionError(
                "Aucune carte numérotée mémorisée : appeler d'abord "
                "Get Ui5 Page Map pour relever les références @N de la page.")
        number = str(ref).strip().lstrip("@")
        if number not in refs:
            raise AssertionError(
                "Référence @%s inconnue : la dernière carte expose @1..@%d "
                "(relever la carte à jour avec Get Ui5 Page Map)."
                % (number, len(refs)))
        return number, refs[number]

    def resolve_ui5_ref(self, ref):
        """Résout une référence ``@N`` de la dernière `Get Ui5 Page Map` en
        **sélecteur Browser** (``css=[id="…"]``, préfixé par la frame active),
        jamais en silence : échec actionnable si aucune carte n'a été
        relevée, si le numéro est inconnu, ou si le contrôle n'est plus rendu
        (page naviguée, vue redessinée ; le remède est nommé : re-percevoir
        avec `Get Ui5 Page Map`). Accepte ``3`` ou ``@3``."""
        number, control_id = self._validate_ui5_ref(ref)
        try:
            ids = self._evaluate(
                RESOLVE_ROLE_JS,
                arg=selector_to_json(build_control_selector(id=control_id))) or []
        except Exception:
            ids = []
        if not ids:
            raise AssertionError(
                "La cible @%s (%s) n'est plus rendue sur la page : "
                "re-percevoir avec Get Ui5 Page Map avant d'agir par "
                "référence." % (number, control_id))
        return self._scoped_selector('css=[id="%s"]' % control_id)

    def click_ui5_ref(self, ref):
        """Clique la cible ``@N`` de la dernière carte : résolution
        `Resolve Ui5 Ref` (fraîcheur re-vérifiée) puis clic Browser, avec la
        même absorption des *stale elements* que `Click Ui5 Control`
        (re-résolution à chaque tentative). Retourne le sélecteur cliqué
        (journalisé : la trace reste rejouable dans une suite)."""
        number, _control_id = self._validate_ui5_ref(ref)

        def _do():
            selector = self.resolve_ui5_ref(ref)
            self._browser().click(selector)
            return selector
        selector = self._act_with_retry(_do, "click ui5 ref @%s" % number)
        logger.info("Click Ui5 Ref @%s -> %s" % (number, selector))
        return selector

    def fill_ui5_ref(self, ref, text):
        """Saisit ``text`` dans la cible ``@N`` de la dernière carte : même
        chemin composite que `Fill Ui5 Input` (l'élément interne
        ``<input>``/``<textarea>`` du contrôle, jamais son ``<div>`` racine),
        fraîcheur re-vérifiée avant chaque tentative. Retourne le sélecteur
        du contrôle rempli. La valeur saisie n'est jamais un localisateur."""
        number, _control_id = self._validate_ui5_ref(ref)

        def _do():
            self.resolve_ui5_ref(ref)
            control_id = self._ui5_refs[number]
            attr = '[id="%s"]' % control_id
            self._browser().fill_text(
                self._scoped_selector("css=%s input, %s textarea"
                                      % (attr, attr)), text)
            return self._scoped_selector('css=[id="%s"]' % control_id)
        selector = self._act_with_retry(_do, "fill ui5 ref @%s" % number)
        logger.info("Fill Ui5 Ref @%s -> %s" % (number, selector))
        return selector

    # -- assertion visuelle (parité du canal ECC) -------------------------------

    def get_ui5_perceptual_hash(self, hash_size=8):
        """Capture la page courante (bibliothèque Browser) et retourne son
        **hash perceptuel** (dHash hexadécimal, ``hash_size²`` bits) : le
        pendant Fiori de `Get Screen Perceptual Hash` (ECC), même cœur pur
        ``sapfx_common.visual_hash``.

        Couvre ce que l'arbre UI5 ne dit pas : un canvas, une image, un
        thème/rendu globalement altéré. Nécessite Pillow (extra ``visual``)."""
        pixels = self._decode_image_to_gray(self._page_png())
        from sapfx_common.visual_hash import dhash_hex
        return dhash_hex(pixels, int(hash_size))

    def ui5_screen_should_match_baseline(self, name, threshold=5,
                                         baseline_directory="visual_baselines",
                                         hash_size=8):
        """Assertion de **non-régression visuelle** de la page Fiori courante,
        même sémantique *snapshot* que `Screen Should Match Baseline` (ECC),
        même module partagé (``sapfx_common.visual_baseline``) :

        * premier passage : la capture devient la baseline ``<name>.png``
          (WARNING journalisé, à committer si le rendu fait référence) ;
        * ensuite : distance de Hamming vs le hash recalculé depuis la
          baseline ; au-delà de ``threshold`` (défaut 5 sur 64 bits), échec
          auto-corrigible avec ``<name>.actual.png`` sauvé à côté.

        Retourne la distance mesurée (0 pour une baseline nouvellement créée)."""
        from sapfx_common.visual_baseline import match_baseline
        outcome = match_baseline(name, self._page_png(),
                                 self._decode_image_to_gray,
                                 str(baseline_directory), int(threshold),
                                 int(hash_size), what="La page")
        if outcome.created:
            logger.warn("Baseline visuelle créée (%s), premier passage : "
                        "committer ce PNG s'il fait référence."
                        % outcome.baseline_path)
        else:
            logger.info("Conforme à la baseline (distance %d <= %d)."
                        % (outcome.distance, int(threshold)))
        return outcome.distance

    # -- navigation launchpad, authentification IDP, vocabulaire métier ---------
    # (concepts issus de l'analyse de playwright-praman, Apache-2.0, voir NOTICE ;
    #  réimplémentés sur nos moteurs, jamais portés verbatim)

    def open_fiori_app(self, intent, **params):
        """Navigue le launchpad vers un **intent sémantique**
        ``SemanticObject-action`` (``Shell-home``, ``SalesOrder-manage``…),
        paramètres nommés émis en query string::

            Open Fiori App    SalesOrder-manage    SalesOrder=1234

        C'est la voie STABLE de navigation FLP : le hash d'intent survit aux
        réorganisations de catalogue, au thème et à la langue, contrairement
        au clic de tuile par titre (`Open App` de la resource, qui reste la
        voie « comme l'utilisateur »). Intent invalide = échec immédiat avec
        la forme attendue. Ne fait QUE naviguer : enchaîner avec
        ``Wait For UI5 Ready`` (le keyword resource `Open App By Intent`
        fait les deux)."""
        hash_ = build_intent_hash(intent, params or None)
        browser = self._browser()
        base = str(browser.get_url()).split("#", 1)[0]
        browser.go_to(base + hash_)
        logger.info("FLP navigation: %s" % hash_)

    def log_in_via_identity_provider(self, username, password: str | Secret,
                                     preset="sap-ias",
                                     username_selector=None,
                                     password_selector=None,
                                     submit_selector=None, timeout=None):
        """Déroule le formulaire de connexion d'un **fournisseur d'identité**
        (IDP) : le passage obligé d'un launchpad d'entreprise, qui redirige
        vers SAP IAS, Azure AD/Entra ou un IDP maison plutôt que d'afficher
        un login SAP classique.

        ``preset`` choisit la fiche de sélecteurs (``sap-ias``, défaut BTP,
        ``azure-ad``, ``generic``) ; chaque sélecteur reste surchargeable
        individuellement (IDP maison = ``generic`` + les trois sélecteurs).
        Gère les DEUX déroulés : une page (utilisateur + mot de passe
        ensemble) et deux étapes (utilisateur → Suivant → mot de passe →
        connexion), détectés dynamiquement. Échoue en nommant l'étape qui
        bloque (formulaire jamais apparu / mot de passe jamais proposé /
        formulaire toujours là après soumission = identifiants refusés ?).

        La valeur du mot de passe n'est pas journalisée par ce keyword ;
        ``password`` accepte aussi le type ``Secret`` de Robot Framework 7.4
        (``-v "IDP_PASSWORD: Secret:<motdepasse>"`` en ligne de commande) :
        la valeur est alors masquée partout, même en TRACE. À appeler après
        ``New Page <url du launchpad>`` ; enchaîner avec ``Wait For UI5
        Ready``."""
        idp = resolve_preset(preset, username_selector, password_selector,
                             submit_selector)
        browser = self._browser()
        budget = timestr_to_secs(timeout if timeout is not None else self.ui5_timeout)

        def _count(selector):
            # `>> visible=true` : ne compter que les éléments VISIBLES : un
            # formulaire deux-étapes garde son champ mot de passe caché dans le
            # DOM dès la première page (constaté sur la fixture IDP : compter
            # les éléments attachés fait prendre à tort la branche une-page).
            try:
                return int(browser.get_element_count(
                    "%s >> visible=true" % selector))
            except Exception:
                return 0

        if not poll_until(lambda: _count(idp.username_selector) > 0,
                          budget, step=self.poll_interval):
            raise AssertionError(
                "Formulaire IDP introuvable : aucun élément ne matche %r "
                "(preset %s). Mauvais preset, ou la page n'a pas redirigé "
                "vers l'IDP." % (idp.username_selector, idp.name))
        browser.fill_text(idp.username_selector, username)
        if _count(idp.password_selector):
            browser.fill_text(idp.password_selector, reveal_secret(password))
            browser.click(idp.submit_selector)
        else:
            # déroulé en deux étapes : utilisateur → « Suivant » → mot de passe
            browser.click(idp.submit_selector)
            if not poll_until(lambda: _count(idp.password_selector) > 0,
                              budget, step=self.poll_interval):
                raise AssertionError(
                    "Le champ mot de passe (%r) n'est jamais apparu après "
                    "l'étape utilisateur (preset %s) : utilisateur inconnu de "
                    "l'IDP, ou sélecteur à surcharger."
                    % (idp.password_selector, idp.name))
            browser.fill_text(idp.password_selector, reveal_secret(password))
            browser.click(idp.submit_selector)
        if not poll_until(lambda: _count(idp.username_selector) == 0,
                          budget, step=self.poll_interval):
            raise AssertionError(
                "Toujours sur le formulaire IDP (%s) après soumission : "
                "identifiants refusés, ou étape supplémentaire (MFA ?) non "
                "couverte par ce keyword." % idp.name)
        logger.info("IDP login (%s) submitted for user %s." % (idp.name, username))

    def lookup_business_term(self, term, domain=None, threshold=0.8):
        """Résout un **terme métier** (français ou anglais, synonymes compris)
        vers sa fiche SAP : canonique, champ ABAP, table, domaine::

            ${info}=    Lookup Business Term    fournisseur
            # -> {'canonical': 'vendor', 'abap_field': 'LIFNR', 'table': 'LFA1', ...}

        Vocabulaire partagé ECC↔Fiori (``sapfx_common.vocabulary`` : MM/SD/FI
        + modèle Flight de démo). Ambiguïté ou score sous ``threshold`` =
        échec listant les candidats, jamais de premier-match silencieux.
        ``domain`` (``MM``/``SD``/``FI``/``FLIGHT``) restreint la recherche.
        Dict JSON-safe (utilisable à travers rf-mcp)."""
        return lookup_as_dict(term, domain=domain, threshold=float(threshold))

    def _page_png(self):
        """Capture PNG de la page active via la bibliothèque Browser :
        ``return_as=bytes`` quand disponible (Browser récents), sinon repli
        sur le fichier retourné par `Take Screenshot`. Stubbable en test."""
        browser = self._browser()
        try:
            from Browser.utils.data_types import ScreenshotReturnType
            try:
                raw = browser.take_screenshot(
                    return_as=ScreenshotReturnType.bytes, log_screenshot=False)
            except TypeError:   # Browser sans log_screenshot
                raw = browser.take_screenshot(return_as=ScreenshotReturnType.bytes)
            return bytes(raw)
        except (ImportError, TypeError):
            path = browser.take_screenshot()
            with open(path, "rb") as fh:
                return fh.read()

    @staticmethod
    def _decode_image_to_gray(image_bytes):
        """PNG → matrice de gris, la même frontière image que le canal ECC
        (impl partagée ``sapfx_common.visual_baseline``, Pillow importé à
        l'appel seulement). Stubbable en test."""
        from sapfx_common.visual_baseline import decode_image_to_gray
        return decode_image_to_gray(image_bytes)

    # -- internes -------------------------------------------------------------

    def _eval_scope(self):
        """Sélecteur Browser du contexte d'exécution JS : ``<frame> >>> css=body``
        quand une iframe est ciblée (`Set Ui5 Frame`), sinon ``None`` (page).
        Avec un sélecteur, Browser passe l'élément résolu à la fonction et
        l'exécute dans le contexte JS de SA frame ; voir `build_call`."""
        return ("%s >>> css=body" % self._ui5_frame) if self._ui5_frame else None

    def _evaluate(self, js, arg=None):
        """Exécute une fonction du bundle dans le bon contexte (page ou frame)."""
        return self._browser().evaluate_javascript(self._eval_scope(), js, arg=arg)

    def _scoped_selector(self, selector):
        """Préfixe un sélecteur Browser avec la frame ciblée (chaînage ``>>>``)."""
        return "%s >>> %s" % (self._ui5_frame, selector) if self._ui5_frame else selector

    def _resolve(self, js, arg, description, timeout=None):
        """Exécute ``js`` (un résolveur du bundle) dans la page, en sondant jusqu'à ce qu'il
        retourne au moins un identifiant de contrôle ou que ``timeout`` (défaut :
        ``ui5_timeout``) soit écoulé.

        Les applications Fiori rendent les vues de manière asynchrone, donc un contrôle
        n'est souvent pas dans l'arbre au moment où le noyau UI5 est prêt. Le sondage est
        l'équivalent web du `Wait Until Element Present` ECC ; jamais une pause fixe.
        Retourne une liste d'identifiants (potentiellement vide).
        """
        def _check():
            try:
                return self._evaluate(js, arg=arg) or []
            except Exception:
                # transitoire pendant un re-rendu Fiori : le sondage doit continuer,
                # pas s'interrompre sur la première erreur JS (contrat de poll_until).
                return []

        budget = timestr_to_secs(timeout if timeout is not None else self.ui5_timeout)
        return poll_until(_check, budget, step=self.poll_interval)

    def _act_with_retry(self, action, description):
        """Exécute ``action`` en la retentant sur exception, bornée par ``ui5_timeout``.

        ``action`` doit ré-résoudre son élément à chaque appel (le passer en lambda)
        afin qu'une nouvelle tentative reparte d'un id frais : c'est ce qui absorbe les
        *stale elements* après un re-rendu Fiori. Le budget de relance est borné dans
        le temps (pas par un nombre fixe de tentatives) afin de couvrir réellement
        ``ui5_timeout``, y compris pour un re-rendu qui se stabilise après plus d'une
        seconde. La dernière erreur est relevée si le délai s'épuise."""
        try:
            return retry_until(action, timestr_to_secs(self.ui5_timeout), step=self.poll_interval)
        except Exception as last:
            raise AssertionError("Could not %s after retries. Last error: %s"
                                 % (description, last))

    def _pick_id(self, ids, index, description, noun="control"):
        """Sélectionne ``ids[index]`` avec un message d'erreur explicite (jamais un
        ``IndexError`` brut) si la résolution n'a rien trouvé ou si ``index`` dépasse.
        Partagé par tous les mots-clés qui résolvent puis indexent une liste de
        correspondances (`_pick`, `get_ui5_xpath`, `read_ui5_table`)."""
        if not ids:
            raise AssertionError("No UI5 %s matched %s on the current page." % (noun, description))
        try:
            return ids[int(index)]
        except IndexError:
            raise AssertionError(
                "%s matched %s %s(s); index %s is out of range."
                % (description, len(ids), noun, index))

    def _pick(self, ids, index, description):
        dom_id = self._pick_id(ids, index, description)
        if len(ids) > 1:
            logger.info("%s matched %s controls; using index %s." % (description, len(ids), index))
        # Sélecteur d'attribut (pas `id=`, qui n'est pas un moteur Playwright) afin que
        # les identifiants UI5 contenant `--`/`__` soient résolus correctement.
        # Préfixé par la frame ciblée le cas échéant (Set Ui5 Frame).
        return self._scoped_selector('css=[id="%s"]' % dom_id)

    def _pick_wc(self, paths, index, description, noun="web component"):
        """Pendant WC/DOM de `_pick` : les correspondances sont des CHEMINS CSS
        light-DOM (pas des ids : les hôtes WC et les éléments DOM génériques
        n'en ont souvent pas)."""
        path = self._pick_id(paths, index, description, noun=noun)
        if len(paths) > 1:
            logger.info("%s matched %s %s(s); using index %s."
                        % (description, len(paths), noun, index))
        return self._scoped_selector("css=%s" % path)

    def _relaxed_hint(self, selector_parts):
        """Suffixe de message d'erreur AUTO-CORRIGIBLE quand un sélecteur role ne
        matche rien : re-sonde (sans attente) avec le ``controlType`` seul pour
        dire si le type est rendu du tout, et combien : l'agent (ou l'humain)
        sait immédiatement si ce sont les propriétés qui ont dérivé ou si le
        contrôle n'existe pas. Best-effort : jamais d'erreur masquée."""
        ctype = selector_parts.get("controlType")
        if not ctype or len(selector_parts) <= 1:
            return (" Call Get Ui5 Page Tree (mode=diff after the first call) "
                    "to inspect the rendered controls.")
        try:
            ids = self._evaluate(
                RESOLVE_ROLE_JS,
                arg=selector_to_json(build_control_selector(controlType=ctype))) or []
        except Exception:
            return ""
        if not ids:
            return (" No control of type %s is rendered at all: wrong screen, "
                    "or the view is still loading." % ctype)
        return (" %d control(s) of type %s ARE rendered; the other selector "
                "parts (properties/bindingPath/idSuffix) likely diverged; call "
                "Get Ui5 Page Tree to compare." % (len(ids), ctype))

    def _wait_visible(self, selector, timeout=None):
        """Attend qu'un sélecteur soit visible via Browser, en passant l'état
        sous sa forme **enum** (``ElementState.visible``) : en appel Python
        direct (``get_library_instance``), la conversion d'arguments de Robot
        n'a pas lieu et l'API interne de Browser rejette la chaîne ``"visible"``
        (KeyError, attrapé live par le smoke hybride). ``timeout`` accepte une
        chaîne de temps Robot et est converti en ``timedelta`` pour la même
        raison. Repli chaîne si Browser n'est pas installé (fakes de test)."""
        try:
            from Browser.utils.data_types import ElementState
            state = ElementState.visible
        except ImportError:
            state = "visible"
        kwargs = {}
        if timeout is not None:
            from datetime import timedelta
            kwargs["timeout"] = timedelta(seconds=timestr_to_secs(timeout))
        self._browser().wait_for_elements_state(selector, state, **kwargs)

    def _browser(self):
        """Retourne l'instance active de la bibliothèque Browser, avec un message d'erreur
        explicite si la suite a oublié de l'importer."""
        try:
            return BuiltIn().get_library_instance("Browser")
        except Exception as err:
            raise RuntimeError(
                "SapFioriLibrary needs the Browser library imported in the suite "
                "(`Library    Browser`). Original error: %s" % err
            )
