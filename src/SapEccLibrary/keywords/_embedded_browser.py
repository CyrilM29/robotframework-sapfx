"""Pont contrôle-navigateur-embarqué (WebView2/CDP) vers la bibliothèque Browser.

Certains écrans SAP GUI/Business Client récents embarquent un contrôle
navigateur (Edge WebView2 : aide F1 moderne, certains écrans Business Client)
DANS une fenêtre SAP GUI classique. Idée documentée par RoboSAPiens (imbus,
Apache-2.0, voir NOTICE) : activer le débogage distant du contrôle WebView2
puis piloter la page qu'il héberge avec la bibliothèque Browser (Playwright) via
CDP (Chrome DevTools Protocol), sans jamais quitter la session SAP GUI ni le
canal ECC.

Ce mixin ne fait QUE le pont :

1. `Enable Embedded Browser Debugging` positionne la variable d'environnement
   lue par WebView2 à son démarrage : à appeler AVANT `Open Sap Logon` (ou tout
   lancement du client SAP), jamais après ;
2. `Get Embedded Browser Page Id` / `Switch To Embedded Browser Page` retrouvent
   puis activent, dans la bibliothèque Browser, la page hébergée par le contrôle
   embarqué (recherche par titre, sondée jusqu'à rendu).

Le pilotage lui-même (clic, saisie) reste celui de la bibliothèque Browser ;
même méthode d'accès (``BuiltIn().get_library_instance``) que
``SapFioriLibrary``, avec laquelle elle est déjà utilisée côté Fiori.

Prérequis (documentés, non automatisables depuis Robot) :

* Options SAP GUI (ou SAP Business Client) -> Interaction Design -> Control
  Settings -> Browser Control = Edge ;
* Edge (Chromium) et la bibliothèque Browser (``robotframework-browser``,
  extra ``web`` du projet) installés sur le poste ;
* la bibliothèque Browser importée dans la suite (``Library    Browser``).
"""
from typing import TYPE_CHECKING, Any, Optional

import os

from robot.libraries.BuiltIn import BuiltIn

from sapfx_common.polling import poll_until

# Indicateurs Chromium ajoutés par WebView2 au démarrage : active le protocole
# DevTools distant sur `port`. WebView2 ne lit cette variable qu'à la création
# du contrôle (donc au lancement du process hôte SAP Logon/NWBC) -- d'où
# l'obligation d'appeler `Enable Embedded Browser Debugging` AVANT `Open Sap
# Logon`, jamais après.
_CDP_ARGS_TEMPLATE = ("--enable-features=msEdgeDevToolsWdpRemoteDebugging "
                     "--remote-debugging-port=%d")
_WEBVIEW2_ENV_VAR = "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"
_DEFAULT_CDP_PORT = 4711

_TRUTHY = ("1", "true", "yes", "on")


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUTHY


class EmbeddedBrowserKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.default_timeout``/
    ``self.poll_interval`` (secondes, float), définis par ``__init__``."""

    if TYPE_CHECKING:
        # Contrat du composite (SapEccLibrary), pour mypy seulement : les
        # keywords annotés (type GuiElementId) font vérifier leurs corps.
        def _timeout_secs(self, *args: Any, **kwargs: Any) -> Any: ...
        poll_interval: Any
        def take_screenshot(self, *args: Any, **kwargs: Any) -> Any: ...

    def enable_embedded_browser_debugging(self, port: int = _DEFAULT_CDP_PORT):
        """Active le débogage distant CDP des contrôles WebView2 embarqués.

        Positionne ``WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS`` dans l'environnement
        du *process courant*. WebView2 ne lit cette variable qu'à la création
        du contrôle : ce keyword doit donc être appelé AVANT `Open Sap Logon`
        (ou tout lancement de SAP Logon/Business Client héritant de cet
        environnement, p.ex. via la bibliothèque Process) : l'appeler après
        coup n'a aucun effet sur un client déjà démarré.

        Retourne le port effectif (à repasser à `Get Embedded Browser Page Id`
        / `Switch To Embedded Browser Page` si vous changez la valeur par
        défaut). Idempotent : les arguments déjà présents dans la variable sont
        conservés, les nouveaux leur sont concaténés plutôt que de les écraser.

        Exemple :
        | ${port}=    `Enable Embedded Browser Debugging`
        | Should Be Equal As Integers    ${port}    4711
        | # then `Open Sap Logon`: SAP Logon reads the variable only when it starts
        """
        port = int(port)
        flags = _CDP_ARGS_TEMPLATE % port
        existing = os.environ.get(_WEBVIEW2_ENV_VAR, "").strip()
        os.environ[_WEBVIEW2_ENV_VAR] = ("%s %s" % (existing, flags)).strip() if existing else flags
        return port

    def get_embedded_browser_page_id(self, title, port: int = _DEFAULT_CDP_PORT,
                                     exact: bool = False, timeout=None,
                                     element: Optional[str] = None):
        """Retourne l'id (catalogue Browser) de la page hébergée par le contrôle
        WebView2 embarqué dont le titre correspond à ``title``.

        Se connecte au point de terminaison CDP ``http://localhost:<port>``
        (``Connect To Browser`` de la bibliothèque Browser, ``use_cdp=True``)
        s'il n'est pas déjà atteint, puis sonde le catalogue des pages jusqu'à
        ``timeout`` (``default_timeout`` de la bibliothèque par défaut) : le
        contrôle se rend de façon asynchrone après l'action SAP GUI qui
        l'affiche.

        ``exact=False`` (défaut) : correspondance par sous-chaîne insensible à
        la casse (les titres de page WebView2 embarquent souvent un suffixe
        dynamique). Échoue en listant les titres de page réellement ouverts si
        aucun ne correspond, erreur auto-corrigible.

        ``element`` (un sélecteur de la bibliothèque Browser) ne retient que les
        pages qui portent cet élément : la voie des pages SANS titre, comme le
        dialogue de saisie des démos ABAP (``cl_demo_input``), où un titre vide
        désigne toutes les pages. La page active de la bibliothèque Browser est
        rendue telle qu'elle était. La recherche ne porte que sur le navigateur
        que le pont a rattaché (une page web ouverte par la même suite n'est
        jamais candidate), et une connexion tenue est réutilisée, jamais
        rouverte. Si plusieurs pages restent candidates, le
        keyword échoue en les listant (adresse et titre) : jamais la première
        en silence.

        Exemple :
        | ${page}=    `Get Embedded Browser Page Id`    ${EMPTY}    element=css=#enterButton
        | Should Start With    ${page}    page=
        """
        browser = self._browser()
        timeout_secs = self._timeout_secs(timeout)
        exact = _as_bool(exact)
        self._last_page_check_error = None
        # La recherche ne porte que sur le navigateur que le PONT a rattaché : une
        # page web ouverte par la même suite n'est jamais candidate. Une connexion
        # tenue est réutilisée (en ouvrir une seconde écraserait son identifiant,
        # et `Disconnect From Embedded Browser` ne fermerait plus la première).
        bridged = getattr(self, "_embedded_browser_id", None)
        page_id = self._find_embedded_page_id(browser, title, exact, element) if bridged else None
        if page_id is None:
            if not bridged:
                self._connect_to_embedded_browser(browser, port)
            page_id = poll_until(
                lambda: self._find_embedded_page_id(browser, title, exact, element),
                timeout_secs, step=self.poll_interval)
        if not page_id:
            titles = self._embedded_page_titles(browser)
            hint = ("\nPages ouvertes :\n%s" % "\n".join("  - %s" % t for t in titles)
                   if titles else
                   "\n(Aucune page ouverte sur ce point de terminaison CDP.)")
            self.take_screenshot()
            carrying = " carrying element '%s'" % element if element else ""
            check_error = getattr(self, "_last_page_check_error", None)
            if check_error is not None:
                hint += "\nDernière vérification d'élément en erreur : %s" % check_error
            raise AssertionError(
                "No embedded browser page with a title matching '%s'%s within "
                "%.1fs (CDP endpoint http://localhost:%s). Is the SAP GUI/"
                "Business Client screen that renders it open, and was "
                "`Enable Embedded Browser Debugging` called BEFORE the SAP "
                "client started?%s" % (title, carrying, timeout_secs, port, hint))
        return page_id

    def switch_to_embedded_browser_page(self, title, port: int = _DEFAULT_CDP_PORT,
                                        exact: bool = False, timeout=None,
                                        element: Optional[str] = None):
        """Comme `Get Embedded Browser Page Id` (``element`` compris), puis active
        cette page dans la bibliothèque Browser (``Switch Page``) : tous les
        keywords Browser suivants (``Click``, ``Fill Text``, ``Get Text``...)
        agissent alors sur le contrôle embarqué. Retourne l'id de la page
        désormais active.

        Exemple :
        | ${page}=    `Switch To Embedded Browser Page`    ${EMPTY}    element=css=#enterButton
        | Should Start With    ${page}    page=
        """
        page_id = self.get_embedded_browser_page_id(title, port=port, exact=exact,
                                                     timeout=timeout, element=element)
        self._browser().switch_page(page_id)
        return page_id

    def disconnect_from_embedded_browser(self) -> bool:
        """Ferme la connexion CDP que le pont a ouverte vers le contrôle WebView2
        embarqué, sans toucher au contrôle lui-même : à appeler AVANT le geste
        SAP GUI qui referme l'écran portant le contrôle (un dialogue, un retour).

        Mesuré le 2026-10-21 sur SAP GUI 8.00 : si le contrôle disparaît pendant
        que la bibliothèque Browser lui est rattachée, le processus Playwright de
        celle-ci s'arrête (code 1) et toute connexion suivante échoue, si bien
        qu'un second écran à contrôle embarqué du même run devient injoignable.
        Déconnecté d'abord, le pont se reconnecte au contrôle suivant.

        Seul le navigateur rattaché par le pont est fermé : un navigateur web
        ouvert par la même suite reste ouvert. Rend ``True`` quand une connexion
        a été fermée, ``False`` quand le pont n'en tenait aucune.

        Exemple :
        | ${page}=    `Switch To Embedded Browser Page`    ${EMPTY}    element=css=#enterButton
        | ${closed}=    `Disconnect From Embedded Browser`
        | Should Be True    ${closed}
        """
        browser_id = getattr(self, "_embedded_browser_id", None)
        if not browser_id:
            return False
        self._embedded_browser_id = None
        self._browser().close_browser(browser_id)
        return True

    def click_embedded_browser_element_and_disconnect(self, selector: str,
                                                      delay: str = "0.5s") -> bool:
        """Clique ``selector`` dans la page active du contrôle embarqué quand ce
        clic REFERME le contrôle (un formulaire qui poste vers ``SAPEVENT``, le
        bouton qui valide un dialogue SAP), en déconnectant le pont AVANT que le
        contrôle ne disparaisse.

        Un ``Click`` de la bibliothèque Browser attend la navigation que la
        soumission déclenche ; pendant ce temps SAP GUI détruit le contrôle, le
        processus Playwright s'arrête (code 1) et la déconnexion n'est plus
        possible (mesuré le 2026-10-21). Ici le clic est ARMÉ dans la page (un
        minuteur de ``delay``, exécuté par le contrôle lui-même), puis le pont se
        déconnecte aussitôt : la déconnexion, locale, dispose de toute la marge
        de ``delay`` (0,5 s par défaut) ; un pont perdu malgré elle ferait
        échouer le geste suivant, jamais un faux vert. L'élément est cherché AVANT toute déconnexion : absent, le
        keyword échoue sans rien avoir déclenché. Rend ``True`` AVANT que le clic
        ne parte : l'appelant attend ensuite ACTIVEMENT l'effet côté SAP (la
        fenêtre du contrôle remplacée ou refermée), jamais une pause fixe, et ne
        se rattache pas à la page entre-temps (elle peut encore être affichée).

        Exemple :
        | ${page}=    `Switch To Embedded Browser Page`    ${EMPTY}    element=css=#enterButton
        | ${armed}=    `Click Embedded Browser Element And Disconnect`    selector=css=#enterButton
        | Should Be True    ${armed}
        """
        browser = self._browser()
        delay_ms = max(0, int(round(self._timeout_secs(delay) * 1000)))
        armed = browser.evaluate_javascript(
            selector,
            "(element) => { setTimeout(() => element.click(), %d); return true; }" % delay_ms)
        if armed is not True:
            raise AssertionError(
                "The click on '%s' could not be armed in the embedded page (got %r): "
                "nothing was triggered." % (selector, armed))
        self.disconnect_from_embedded_browser()
        return True

    # -- helpers (méthodes internes) ------------------------------------------

    def _browser(self):
        """Instance active de la bibliothèque Browser : message d'erreur clair
        si la suite a oublié de l'importer (même garde que côté
        ``SapFioriLibrary``)."""
        try:
            return BuiltIn().get_library_instance("Browser")
        except Exception as err:
            raise RuntimeError(
                "Embedded browser keywords need the Browser library imported "
                "in the suite (`Library    Browser`). Original error: %s" % err)

    def _connect_to_embedded_browser(self, browser, port):
        try:
            self._embedded_browser_id = browser.connect_to_browser(
                "http://localhost:%d" % int(port), use_cdp=True)
        except Exception as err:
            raise RuntimeError(
                "Could not reach the embedded browser control's CDP endpoint "
                "at http://localhost:%s. Checklist: SAP GUI options -> "
                "Interaction Design -> Control Settings -> Browser Control = "
                "Edge; `Enable Embedded Browser Debugging` called BEFORE the "
                "SAP client started; the transaction/screen rendering the "
                "control is open. Original error: %s" % (port, err))

    def _embedded_pages(self, browser):
        bridged = getattr(self, "_embedded_browser_id", None)
        for info in browser.get_browser_catalog():
            if bridged and info.get("id") != bridged:
                continue
            for context in info.get("contexts", []) or []:
                for page in context.get("pages", []) or []:
                    yield page

    def _find_embedded_page_id(self, browser, title, exact, element=None):
        wanted = (title or "").strip().casefold()
        candidates = []
        for page in self._embedded_pages(browser):
            page_title = (page.get("title") or "").strip().casefold()
            if (page_title == wanted) if exact else (wanted in page_title):
                candidates.append(page)
        if element:
            candidates = [page for page in candidates
                          if self._page_has_element(browser, page.get("id"), element)]
        if len(candidates) > 1:
            listed = "\n".join("  - %s (title '%s')" % (page.get("url", ""), page.get("title", ""))
                               for page in candidates)
            raise AssertionError(
                "Several embedded browser pages match the title '%s'%s; name the "
                "one to use with `element=` (a selector that only it carries):\n%s"
                % (title, " and the element '%s'" % element if element else "", listed))
        return candidates[0].get("id") if candidates else None

    def _page_has_element(self, browser, page_id, element):
        """Vrai si la page ``page_id`` porte ``element`` ; la page active de la
        bibliothèque Browser est rendue telle qu'elle était. Une page qui se
        ferme pendant la lecture (le contrôle remplace la sienne) ne porte rien ;
        la cause est gardée pour le message d'échec, jamais avalée en silence."""
        previous = None
        try:
            previous = browser.switch_page(page_id)
            return int(browser.get_element_count(element)) > 0
        except Exception as err:
            self._last_page_check_error = "%s: %s" % (type(err).__name__, err)
            return False
        finally:
            if previous and previous != page_id and not str(previous).upper().startswith("NO "):
                try:
                    browser.switch_page(previous)
                except Exception:
                    pass

    def _embedded_page_titles(self, browser):
        try:
            return [page.get("title", "") for page in self._embedded_pages(browser)]
        except Exception:
            return []
