"""Mixin moteurs sid / wc / dom : les pages sans registre UI5 classique.

Le moteur **sid** (SAP GUI for HTML : le ``SID`` stable de ``lsdata``, plus
la perception du canal : `Webgui Is Present`, `Get Webgui Element Count`,
`List Webgui Menus` / `List Webgui Menu Items`), le
moteur **wc** (UI5 Web Components en light-DOM, tags scopes compris,
``name=`` lisant ``accessible-name``/``accessibleName``) et le moteur **dom**
generique (zones NON-SAP d'une page hybride : CSS + texte + role ARIA calcule
+ nom accessible + attributs).

Extrait de ``SapFioriLibrary.py`` (convention #13).
"""



from sapfx_common.secrets import reveal_secret

from .._ui5_js import (
    RESOLVE_DOM_JS,
    RESOLVE_WC_JS,
    WEBGUI_COUNT_PROBE_JS,
    WEBGUI_MENU_ITEMS_PROBE_JS,
    WEBGUI_MENUS_PROBE_JS,
    sid_xpath,
)
from .._ui5_runtime import (
    build_dom_selector,
    build_wc_selector,
    selector_to_json,
)




class EngineKeywords:
    """Mixin compose dans :class:`SapFioriLibrary` (voir ce module).
    Suppose la page active de Browser accessible via ``self._browser()``
    et la plomberie de ``_base.py`` disponible par composition."""

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

    def webgui_is_present(self):
        """Y a-t-il une page **WebGUI** (SAP GUI for HTML) rendue dans la
        portée courante ? Retourne ``True``/``False``, jamais d'échec : une
        page injoignable répond ``False``. Le témoin est la présence
        d'éléments porteurs de ``lsdata`` (l'attribut où vit le SID) : le
        miroir sid de `Ui5 Runtime Is Present`, lecture pure sans injection.
        Zéro élément ``lsdata`` = la session WebGUI n'est pas (ou plus)
        rendue : c'est aussi l'assertion locale-indépendante de fin de
        session après un log off (avec `Get Webgui Element Count`)."""
        try:
            return int(self._evaluate(WEBGUI_COUNT_PROBE_JS) or 0) > 0
        except Exception:      # noqa: BLE001 (sonde : jamais d'échec)
            return False

    def get_webgui_element_count(self, window=None):
        """Nombre d'éléments WebGUI (porteurs de ``lsdata``) dans la portée
        courante (0+). Sans argument : TOUS les éléments ``lsdata`` (rendus
        ou non) : le témoin de fin de session après un log off (le compte
        doit tomber à 0, assertion 100 % locale-indépendante). Avec
        ``window=N`` : seuls les éléments VISIBLES de la fenêtre ``wnd[N]``
        (``window=1`` = le popup courant, dont on attend la disparition après
        fermeture). N'attend pas : c'est une mesure, à sonder dans un
        ``Wait Until Keyword Succeeds``."""
        arg = None if window is None or str(window).strip() == "" \
            else str(int(window))
        return int(self._evaluate(WEBGUI_COUNT_PROBE_JS, arg=arg) or 0)

    def list_webgui_menus(self, window=0):
        """Ids DOM **visibles** des menus de la barre de menus WebGUI de la
        fenêtre ``window`` (``wnd[N]/mbar/menu[i]…-BtnChoiceMenu``), dans
        l'ordre du DOM. La structure d'ids et le suffixe de rendu sont un
        savoir du canal WebGUI (relevés live 2026-07-18), pas d'un site : la
        POSITION qui compte (System = avant-dernier, Help = dernier, la
        convention SAP) reste à l'appelant. Liste vide = aucun menu visible
        (barre pas encore rendue : sonder dans un ``Wait Until Keyword
        Succeeds``)."""
        return list(self._evaluate(WEBGUI_MENUS_PROBE_JS,
                                   arg=str(int(window))) or [])

    def list_webgui_menu_items(self, menu_id):
        """Items **directs et visibles** d'un menu WebGUI ouvert : ``menu_id``
        est l'id rendu par `List Webgui Menus` (le suffixe ``-BtnChoiceMenu``
        est accepté et retiré). Un item direct n'a plus aucun ``/`` après le
        préfixe du menu (les sous-menus en ont) ; Log Off = dernier item du
        menu System (convention SAP, à la charge de l'appelant). Liste vide =
        menu pas (encore) ouvert."""
        return list(self._evaluate(WEBGUI_MENU_ITEMS_PROBE_JS,
                                   arg=str(menu_id)) or [])

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
        roots ouverts. Re-résout puis ré-essaie en cas d'échec transitoire.
        ``text`` accepte le type ``Secret``, déballé à la frontière."""
        text = reveal_secret(text)

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
        puis ré-essaie en cas d'échec transitoire.

        ``text`` accepte le type ``Secret`` de Robot Framework 7.4, déballé
        ICI à la frontière du navigateur : c'est par ce moteur que se remplit
        le mot de passe d'une page de connexion ICF, qui n'est pas du UI5."""
        text = reveal_secret(text)

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
