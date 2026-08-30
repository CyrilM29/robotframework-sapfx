"""Mixin etat du canal web : repos reel, runtime, messages UI5.

`Wait For Ui5 Idle` (XHR/fetch instrumentes a l'injection + busy + calme
continu : « rendu » ne veut pas dire « donnees arrivees »),
`Ui5 Runtime Is Present` (la SEULE sonde qui n'injecte pas le bundle : une
observation ne doit rien modifier), `Get Ui5 Application State` (portee de
frame + runtime + messages en UN aller-retour de contexte RF) et
`Get Ui5 Messages` / `Ui5 Should Have No Messages Of Type` (assertion par
TYPE, convention #3 cote web). Aussi deux lectures d'etat de session :
`Get Session Cookie Summary` (cookies sans leur valeur, predicat
« expiration FUTURE » : la sentinelle 1969 d'un cookie de session ne passe
jamais pour une expiration), `Get Page Languages` (langue servie) et
`Get Ui5 Theme` (theme DEMANDE et theme APPLIQUE : ils divergent le temps
que le runtime echange ses feuilles de style).

Extrait de ``SapFioriLibrary.py`` (convention #13).
"""

import time

from robot.utils import secs_to_timestr, timestr_to_secs

from sapfx_common.polling import poll_until
from sapfx_common.web_cookies import summarize_cookies

from .._ui5_js import (
    GET_MESSAGES_JS,
    IDLE_STATE_JS,
    PAGE_LANGUAGES_PROBE_JS,
    UI5_READY_PROBE_JS,
    UI5_RUNTIME_PROBE_JS,
    UI5_THEME_PROBE_JS,
)
from .._ui5_runtime import applied_theme




class StateKeywords:
    """Mixin compose dans :class:`SapFioriLibrary` (voir ce module).
    Suppose la page active de Browser accessible via ``self._browser()``
    et la plomberie de ``_base.py`` disponible par composition."""

    def wait_for_ui5_idle(self, timeout=None, settle="300 ms"):
        """Attend que la page soit **réellement au repos** : plus aucune
        requête réseau en vol (XHR et fetch, instrumentés par le bundle à son
        injection), aucun indicateur busy UI5 visible, et un calme continu
        d'au moins ``settle``.

        Le tueur de flakiness des apps Fiori : « rendu » ne veut pas dire
        « données arrivées ». Après un Go de FilterBar, un tri ou une
        navigation, la vue existe déjà pendant que l'OData voyage encore ;
        asserter à ce moment lit l'AVANT. Ce keyword est l'équivalent de
        l'autoWaiter d'OPA5, réimplémenté au niveau réseau/DOM : il ne dépend
        PAS du runtime UI5, les pages Web Components et hybrides en profitent
        aussi (dans la portée de frame courante). Ne compte que les requêtes
        lancées APRÈS la première injection du bundle : exactement le besoin
        (agir, puis attendre). ``timeout`` et ``settle`` sont des temps
        Robot : un nombre NU est en secondes (``settle=2000`` = 2 000 s, pas
        2 s), écrire ``settle=2 s`` ; le message d'échec affiche le calme
        exigé en ms pour rendre une mauvaise unité visible.
        ``timeout`` défaut = ``ui5_timeout``. Retourne
        l'état final ``{"pending", "busy", "quiet_ms"}`` (JSON-safe). Jamais
        une pause fixe : convention n°2. ::

            Click Ui5 Control    controlType=Button    properties={'text': 'Go'}
            Wait For Ui5 Idle
            ${rows}=    Read Ui5 Table    controlType=Table

        **Portée exacte** (vérifiée live sur cap-sflight) : ce keyword attend
        le repos des requêtes DÉJÀ parties ; il ne devine pas qu'une requête
        *va* partir. Au tout premier chargement d'une app, il peut donc
        rendre la main avant que la vue n'ait lancé son ``initialLoad`` :
        y enchaîner l'attente d'un contrôle (`Ui5 Control Should Be Visible`,
        ou la résolution qui sonde déjà le rendu) reste la façon d'attendre
        un PREMIER rendu. C'est APRÈS une action (Go, tri, navigation), là où
        la vue est déjà là et où seules les données manquent, qu'il est
        décisif."""
        budget = timestr_to_secs(timeout if timeout is not None else self.ui5_timeout)
        settle_ms = timestr_to_secs(settle) * 1000.0
        state = {}
        last_error = {}

        def _check():
            try:
                result = self._evaluate(IDLE_STATE_JS) or {}
            except Exception as exc:      # noqa: BLE001 (sondage : on continue)
                last_error["error"] = exc
                return False
            last_error.clear()
            state.clear()
            state.update(result)
            return (not result.get("busy")
                    and int(result.get("pending") or 0) == 0
                    and float(result.get("quiet_ms") or 0) >= settle_ms)

        if not poll_until(_check, budget, step=self.poll_interval):
            # Le `settle` CALCULÉ est affiché : un nombre nu est des SECONDES
            # Robot (settle=2000 = 2 000 000 ms), et sans ce chiffre l'état
            # final (quiet_ms confortable, pending=0) semble contredire
            # l'échec au lieu de dénoncer l'unité.
            if state:
                detail = "dernier état : %s" % state
            elif "error" in last_error:
                exc = last_error["error"]
                detail = (
                    "dernier état : illisible, la sonde d'inactivité échoue "
                    "dans la portée courante (%s: %s ; portée de frame : %s). "
                    "Frame sans bundle évaluable (Set/Push Ui5 Frame manquant "
                    "ou de trop ?) ou page/contexte détruit : Get Page "
                    "Composition tranche."
                    % (type(exc).__name__, exc,
                       self.get_ui5_frame_stack() or "aucune"))
            else:
                detail = ("dernier état : illisible, la sonde d'inactivité "
                          "n'a rien rendu dans la portée courante (portée de "
                          "frame : %s)." % (self.get_ui5_frame_stack()
                                            or "aucune"))
            raise AssertionError(
                "La page n'est pas revenue au repos après %s (calme continu "
                "exigé : %d ms ; %s). Log Fiori Diagnostics donne le détail "
                "(console, erreurs, composition)."
                % (secs_to_timestr(budget), settle_ms, detail))
        return dict(state)

    def ui5_runtime_is_present(self):
        """Y a-t-il un **runtime UI5** dans la portée courante (page, ou frame
        ciblée par `Set Ui5 Frame` / `Push Ui5 Frame`) ? Retourne ``True`` ou
        ``False``, jamais d'échec : une page injoignable répond ``False``.

        C'est la sonde à poser AVANT un keyword qui exige le runtime
        (`Get Ui5 Messages`, `Get Ui5 Page Tree`) quand on ne sait pas encore
        sur quoi on est tombé : pages UI5 Web Components sans runtime, WebGUI
        classique (moteur ``sid``), zones non-SAP d'une page hybride (moteur
        ``dom``) sont des cibles LÉGITIMES de cette bibliothèque, et y voir un
        échec est un faux signal. `Get Page Composition` répond à la même
        question en plus détaillé, au prix d'une analyse complète de la page.

        Contrairement à tous les autres keywords web, cette sonde n'injecte
        PAS le bundle ``__SAPFX`` : elle ne modifie donc rien (pas
        d'instrumentation ``fetch`` ni ``XMLHttpRequest``, pas de hook
        ``MessageToast``), ce qui la rend utilisable par une pure
        observation, l'état applicatif servi aux agents notamment. ::

            ${ui5}=    Ui5 Runtime Is Present
            IF    ${ui5}    Ui5 Should Have No Messages Of Type    Error
        """
        try:
            return bool(self._evaluate(UI5_RUNTIME_PROBE_JS))
        except Exception:      # noqa: BLE001 (sonde : jamais d'échec)
            return False

    def get_ui5_application_state(self):
        """L'état du canal web en **UN seul appel** : portée de frame active,
        présence d'un runtime UI5, et messages UI5 quand il y en a un.
        Retourne un dict JSON-safe ``{"frame_stack": [...], "ui5_runtime":
        bool, "messages": {...}}`` (``messages`` absent hors runtime UI5,
        remplacé par ``messages_error`` si leur lecture a échoué).

        Le « où en suis-je » de la page, à joindre au diagnostic d'un échec ou
        à servir à un agent. Il existe parce qu'un état assemblé keyword par
        keyword coûte un aller-retour par section : à travers rf-mcp, chacun
        traverse le contexte Robot Framework, ce qui domine largement le coût
        du JS. Le state provider MCP l'appelle donc une fois plutôt que trois.

        L'ordre compte et n'est pas négociable : le runtime est sondé par
        `Ui5 Runtime Is Present` (aucune injection) AVANT de lire les
        messages, qui exigent le runtime et installent le bundle. Une page
        sans UI5 (moteurs wc/sid/dom) est donc décrite honnêtement, sans
        échec et sans être instrumentée pour rien. ::

            ${etat}=    Get Ui5 Application State
            Log         Portée : ${etat}[frame_stack]
        """
        state = {"frame_stack": self.get_ui5_frame_stack(),
                 "ui5_runtime": self.ui5_runtime_is_present()}
        if state["ui5_runtime"]:
            try:
                state["messages"] = self.get_ui5_messages()
            except Exception as exc:      # noqa: BLE001 (état best-effort)
                state["messages_error"] = str(exc)
        return state

    def ui5_runtime_is_ready(self):
        """Le moteur UI5 de la portée courante est-il **inactif** (pas
        seulement chargé) ? Retourne ``True``/``False``, jamais d'échec :
        runtime présent (Core hérité OU module ``Element``, UI5 2.x
        supprimant ``sap.ui.getCore()``), aucune mise à jour d'UI en attente
        (``getUIDirty`` quand le Core l'expose), aucun indicateur
        d'occupation visible.

        Le prédicat du ``Wait For UI5 Ready`` de la couche resources (qui le
        sonde en ``Wait Until Keyword Succeeds`` via `Ui5 Runtime Should Be
        Ready`). Lecture PURE, sans bundle : à la différence de `Wait For Ui5
        Idle`, cette sonde n'instrumente rien : c'est le témoin « moteur au
        repos », pas « réseau au repos »."""
        try:
            return bool(self._evaluate(UI5_READY_PROBE_JS))
        except Exception:      # noqa: BLE001 (sonde : jamais d'échec)
            return False

    def ui5_runtime_should_be_ready(self):
        """Assertion : le moteur UI5 est chargé ET inactif. La forme à sonder
        dans un ``Wait Until Keyword Succeeds`` (voir
        `Ui5 Runtime Is Ready`)."""
        if not self.ui5_runtime_is_ready():
            raise AssertionError(
                "Le moteur UI5 n'est pas (encore) inactif sur la portée "
                "courante : runtime absent, mise à jour d'UI en attente, ou "
                "indicateur d'occupation visible. `Get Page Composition` "
                "tranche si la page n'est pas UI5 du tout.")

    def get_session_cookie_summary(self):
        """Cookies du contexte Browser COURANT, réduits à ce qui peut entrer
        dans un test : liste triée de ``{name, domain, future_expiration}``.
        Aucune VALEUR de cookie n'est retournée ni journalisée : un jeton de
        session ne doit jamais finir dans un log.

        ``future_expiration`` est le prédicat qui a un sens, et pas
        « expiration renseignée » : la bibliothèque Browser rend un cookie de
        SESSION (sans expiration) avec une date de **1969** (epoch moins un),
        qu'un test naïf lirait comme une expiration renseignée donc
        permanente : les six cookies d'un site passaient pour permanents et
        le test était vert à l'envers (leçon live 2026-08-26, campagne de
        résilience Work Zone ; logique pure ``sapfx_common.web_cookies``). ::

            ${cookies}=    Get Session Cookie Summary
            ${permanents}=    Evaluate    [c for c in $cookies if c['future_expiration']]
        """
        try:
            from Browser.utils.data_types import CookieType
            kind = CookieType.dictionary
        except ImportError:               # Browser absent (fakes de test)
            kind = "dictionary"
        raw = self._browser().get_cookies(kind)
        return summarize_cookies(raw, time.time())

    def get_page_languages(self):
        """La **langue réellement servie** : dict JSON-safe ``{document,
        navigator}`` (attribut ``lang`` du document de la portée courante,
        langue déclarée du navigateur). C'est la mesure qui tranche « le
        réglage de langue est-il appliqué » sans lire un seul texte localisé
        (convention #3) : le document sert ``fr`` ou ne le sert pas. Lecture
        pure (aucune injection), respecte la portée de frame."""
        result = self._evaluate(PAGE_LANGUAGES_PROBE_JS)
        return result if isinstance(result, dict) else {"document": "",
                                                        "navigator": ""}

    def get_ui5_theme(self):
        """Le **thème** du runtime UI5 : dict JSON-safe ``{requested, applied}``.

        Deux valeurs et non une, parce qu'elles divergent et que la différence
        est mesurable. ``requested`` est le thème que le runtime a reçu ordre
        d'appliquer (module ``sap/ui/core/Theming``, repli sur la configuration
        du Core hérité que UI5 2.x supprime) ; ``applied`` est celui que le
        document porte réellement, extrait de la classe technique
        ``sapUiTheme-<clé>`` de ``<html>``.

        Le témoin **locale-safe** d'un changement de thème (convention n°3) :
        l'entrée de menu qui l'a choisi porte un libellé traduit, la clé
        technique ``sap_horizon_dark`` non. Relevé live sur le Demo Kit OpenUI5
        (2026-08-30) : juste après le clic, ``applied`` est VIDE le temps que le
        runtime échange les feuilles de style, alors que ``requested`` porte déjà
        la cible. Asserter le thème demande donc d'attendre la valeur voulue,
        jamais de lire une fois. Lecture pure (aucune injection du bundle, donc
        aucune instrumentation de la page), respecte la portée de frame.
        """
        result = self._evaluate(UI5_THEME_PROBE_JS)
        if not isinstance(result, dict):
            return {"requested": "", "applied": ""}
        return {"requested": str(result.get("requested") or ""),
                "applied": applied_theme(result.get("classes"))}

    def get_ui5_messages(self, include_toasts=True):
        """Lit les **messages UI5** de la page : le MessageManager (module
        ``Messaging`` des UI5 récents, ``getMessageManager()`` sinon) plus les
        ``MessageToast`` récents, captés par un hook posé à l'injection du
        bundle (un toast est éphémère à l'écran, pas dans cette liste ; ceux
        émis avant l'injection sont perdus, best-effort). Retourne un dict
        JSON-safe ``{"messages": [{"type", "message", "target",
        "description"}], "toasts": [{"text", "time"}]}``.

        La perception des messages du canal web, miroir du type de message de
        barre d'état ECC : ASSERTER sur le ``type`` (Error/Warning/Success),
        jamais sur le texte localisé (convention n°3), via
        `Ui5 Should Have No Messages Of Type`. Runtime UI5 absent sur la
        portée courante = échec actionnable nommant `Ui5 Runtime Is Present`
        (la sonde à poser d'abord quand la page peut ne pas être UI5)."""
        result = self._evaluate(GET_MESSAGES_JS)
        if result is None:
            raise AssertionError(
                "Pas de runtime UI5 sur la page/frame courante : Get Ui5 "
                "Messages lit le MessageManager UI5. Vérifier la portée de "
                "frame (Set/Push Ui5 Frame), sonder Ui5 Runtime Is Present "
                "avant l'appel, ou Get Page Composition pour le détail.")
        if not include_toasts:
            result.pop("toasts", None)
        return result

    def ui5_should_have_no_messages_of_type(self, message_type="Error"):
        """Échoue si le MessageManager UI5 porte AU MOINS un message du type
        donné (``Error``, ``Warning``…) : l'assertion **locale-safe** du canal
        web (convention n°3 : on juge le TYPE, le texte n'est joint au message
        d'échec que pour le lecteur humain). Typiquement après une soumission
        de formulaire : l'app peut afficher l'écran suivant ET porter une
        erreur de validation dans sa MessagePopover. ::

            Click Ui5 Control    controlType=Button    properties={'text': 'Save'}
            Wait For Ui5 Idle
            Ui5 Should Have No Messages Of Type    Error
        """
        wanted = str(message_type).strip().casefold()
        result = self.get_ui5_messages()
        offending = [m for m in result.get("messages", [])
                     if str(m.get("type", "")).strip().casefold() == wanted]
        if offending:
            detail = "\n".join(
                "  - %s : %s" % (m.get("type"), m.get("message"))
                for m in offending[:5])
            raise AssertionError(
                "La page porte %d message(s) UI5 de type %s :\n%s"
                % (len(offending), message_type, detail))
