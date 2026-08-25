"""Mixin resolution UI5 : moteurs role et xpath, popups, chaine de repli.

`Resolve Ui5 Control` (controlType/properties/bindingPath/viewId/idSuffix/
containedIn), `Resolve Ui5 By Xpath` (arbre de controles), `Get Ui5 Xpath`
(le plus court unique), `Get Ui5 Ids`, les popups OUVERTS (`Get Ui5 Open
Popups`, `Click Ui5 Dialog Button` : confirmation par POSITION, jamais le
texte localise) et `Resolve Ui5 With Fallback` (chaine
role->xpath->sid->wc->dom, reparation journalisee + telemetrie).

Extrait de ``SapFioriLibrary.py`` (convention #13).
"""
import json

from robot.api import logger

from sapfx_common.healing_telemetry import record_healing

from .._ui5_js import (
    BEST_XPATH_JS,
    DIALOG_BUTTON_JS,
    OPEN_POPUPS_JS,
    RESOLVE_DOM_JS,
    RESOLVE_ROLE_JS,
    RESOLVE_WC_JS,
    RESOLVE_XPATH_JS,
)
from .._ui5_runtime import (
    _coerce_dict,
    build_control_selector,
    build_dom_selector,
    build_wc_selector,
    selector_to_json,
)




class LocatorKeywords:
    """Mixin compose dans :class:`SapFioriLibrary` (voir ce module).
    Suppose la page active de Browser accessible via ``self._browser()``
    et la plomberie de ``_base.py`` disponible par composition."""

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

        ``viewId`` restreint aux contrôles de cette **vue** : la vue propriétaire
        est cherchée en remontant la hiérarchie, et à défaut l'identifiant donné
        est cherché dans l'id du contrôle. La seconde forme sert à porter la
        recherche sur un CONTENEUR (``viewId=<id de la liste>`` ne retient que
        les lignes de cette liste, dont les ids de fabrique le contiennent) ;
        la première couvre les contrôles à id entièrement généré, que la seconde
        ne pouvait pas voir.

        ``containedIn`` restreint aux contrôles dont le **nœud DOM** descend de
        celui du contrôle désigné (id exact, sinon suffixe d'id, sinon nœud DOM
        de cet id : c'est la valeur que `Get Ui5 Ids` vient de servir). ``viewId`` suit
        la propriété (vue, agrégations), ``containedIn`` suit le rendu : ce sont
        deux relations distinctes, et c'est pourquoi la seconde ne remplace pas
        la première. Elle existe pour le cas mesuré live où un contrôle est rendu
        DANS un autre par un composant séparé (une tuile de launchpad dont le
        titre et le compteur ne sont ni dans sa vue, ni dans ses agrégations, ni
        dans son contexte de liaison). Conteneur absent ou non rendu = aucune
        correspondance.
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

    def get_ui5_ids(self, **selector_parts):
        """Retourne les **identifiants** des contrôles rendus qui correspondent au
        sélecteur, dans l'ordre du registre (liste, vide si rien ne matche).

        Le complément de `Get Ui5 Match Count` (combien) et de
        `Get Ui5 Properties` (quelles valeurs) : celui-ci répond **lesquels**.
        C'est la lecture qui manquait quand l'ancre documentée est un SUFFIXE
        d'identifiant : sur un shell dont les préfixes de vue sont générés et
        les positions de liste variables, seule la liste des ids réellement
        rendus permet de découvrir les entrées présentes au lieu de les
        supposer. ::

            ${ids}=    Get Ui5 Ids    controlType=sap.m.StandardListItem
            # ['__list0-0-recentActivitiesBtn', '__list0-4-ActionModeBtn', ...]

        Accepte les mêmes parties de sélecteur que `Resolve Ui5 Control`, dont
        ``containedIn`` (containment DOM), qui répond à « quels contrôles sont
        rendus À L'INTÉRIEUR de celui-ci », question qu'aucune autre partie ne
        pose : ``viewId`` suit la vue propriétaire ou l'id de fabrique, donc la
        propriété, quand ``containedIn`` suit le rendu. ::

            ${tuiles}=    Get Ui5 Ids    controlType=sap.ushell.ui.launchpad.Tile
            ${titre}=     Get Ui5 Property    header    controlType=sap.m.GenericTile
            ...           containedIn=${tuiles}[0]

        N'attend pas et ne lève pas : c'est une lecture, pas une assertion
        (voir `Ui5 Control Should Be Visible` pour exiger une présence). Comme
        tous les moteurs de la bibliothèque, ne voit que les contrôles RENDUS :
        un contrôle déclaré mais sans nœud DOM n'y figure pas, ce qui est le
        comportement voulu (`visible` peut valoir vrai sur un contrôle que le
        shell n'a jamais construit).
        """
        selector = build_control_selector(**selector_parts)
        ids = self._evaluate(RESOLVE_ROLE_JS, arg=selector_to_json(selector)) or []
        return [str(i) for i in ids]

    def get_ui5_open_popups(self):
        """Retourne les popups actuellement **OUVERTS** (dialogues et popovers),
        une liste de dicts JSON-safe ``{id, controlType, kind, state, buttons}``.

        Le pendant Fiori de `Get Open Windows` (ECC), et il existe pour la même
        raison qu'un test ne doit jamais deviner : un dialogue fermé reste
        **rendu**. Mesuré live sur un launchpad ABAP, le dialogue « À propos »
        garde son nœud DOM après acquittement, donc `Get Ui5 Match Count` en
        rapporte encore 1 : ni un comptage ni une résolution ne distinguent
        ouvert de fermé. La source qui le sait est ``sap.m.InstanceManager``.

        ``state`` porte la propriété d'état du dialogue quand elle existe
        (``Error``, ``Warning``, ``None``) : c'est l'ancre locale-indépendante
        d'un refus, là où le titre et le texte sont traduits. ``kind`` vaut
        ``dialog`` ou ``popover``, ``buttons`` compte les boutons rendus. ::

            ${popups}=    Get Ui5 Open Popups
            Should Be Equal    ${popups}[0][state]    Error

        Lecture pure. Échoue seulement si la portée courante n'a pas de runtime
        UI5 (sonder d'abord avec `Ui5 Runtime Is Present`).
        """
        result = self._evaluate(OPEN_POPUPS_JS, arg=None)
        if result is None:
            raise AssertionError(
                "Aucun runtime UI5 sur la portée courante : impossible de lister "
                "les popups ouverts. Sonder d'abord avec `Ui5 Runtime Is Present`, "
                "et vérifier la portée de frame avec `Get Ui5 Frame Stack`.")
        return [dict(entry) for entry in result]

    def click_ui5_dialog_button(self, position=0):
        """Clique le bouton d'index ``position`` (base 0) du **dialogue ouvert le
        plus récent**, et non un bouton désigné par son libellé.

        L'adresse d'un bouton de dialogue est sa POSITION : les boutons d'une
        MessageBox portent un identifiant généré (``__mbox-btn-0``) et un texte
        TRADUIT. Deux campagnes live l'ont payé, l'une en français et l'autre en
        anglais, sur des dialogues par ailleurs identiques. ::

            Click Ui5 Dialog Button              # le premier bouton : acquitter
            Click Ui5 Dialog Button    1         # le second : annuler

        Échoue en nommant la cause : aucun dialogue ouvert (et `Get Ui5 Open
        Popups` pour le constater), ou position hors des boutons rendus, avec
        leur nombre. Ne referme rien de lui-même : c'est le dialogue qui décide
        de ce que fait son bouton.
        """
        payload = json.dumps({"position": int(position)})
        result = self._evaluate(DIALOG_BUTTON_JS, arg=payload)
        if result is None:
            raise AssertionError(
                "Aucun runtime UI5 sur la portée courante : impossible de cliquer "
                "un bouton de dialogue. Sonder d'abord avec `Ui5 Runtime Is Present`.")
        result = dict(result)
        error = result.get("error")
        if error == "no_dialog":
            raise AssertionError(
                "Aucun dialogue UI5 ouvert : rien à cliquer en position %s. "
                "`Get Ui5 Open Popups` dit ce qui est réellement ouvert."
                % position)
        if error == "out_of_range":
            raise AssertionError(
                "Le dialogue ouvert '%s' porte %s bouton(s) rendu(s) : la position "
                "%s est hors bornes." % (result.get("dialog"), result.get("count"), position))
        if error:
            raise AssertionError(
                "Impossible de désigner le bouton en position %s du dialogue ouvert "
                "(%s)." % (position, error))
        dom_id = result.get("id")
        self._act_with_retry(
            lambda: self._browser().click(self._scoped_selector('css=[id="%s"]' % dom_id)),
            "click dialog button at position %s" % position)

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
