"""Pont contrôle-navigateur-embarqué (WebView2/CDP) vers la bibliothèque Browser.

Certains écrans SAP GUI/Business Client récents embarquent un contrôle
navigateur (Edge WebView2 — aide F1 moderne, certains écrans Business Client)
DANS une fenêtre SAP GUI classique. Idée documentée par RoboSAPiens (imbus,
Apache-2.0 — voir NOTICE) : activer le débogage distant du contrôle WebView2
puis piloter la page qu'il héberge avec la bibliothèque Browser (Playwright) via
CDP (Chrome DevTools Protocol) — sans jamais quitter la session SAP GUI ni le
canal ECC.

Ce mixin ne fait QUE le pont :

1. `Enable Embedded Browser Debugging` positionne la variable d'environnement
   lue par WebView2 à son démarrage — à appeler AVANT `Open Sap Logon` (ou tout
   lancement du client SAP), jamais après ;
2. `Get Embedded Browser Page Id` / `Switch To Embedded Browser Page` retrouvent
   puis activent, dans la bibliothèque Browser, la page hébergée par le contrôle
   embarqué (recherche par titre, sondée jusqu'à rendu).

Le pilotage lui-même (clic, saisie) reste celui de la bibliothèque Browser —
même méthode d'accès (``BuiltIn().get_library_instance``) que
``SapFioriLibrary``, avec laquelle elle est déjà utilisée côté Fiori.

Prérequis (documentés, non automatisables depuis Robot) :

* Options SAP GUI (ou SAP Business Client) -> Interaction Design -> Control
  Settings -> Browser Control = Edge ;
* Edge (Chromium) et la bibliothèque Browser (``robotframework-browser``,
  extra ``web`` du projet) installés sur le poste ;
* la bibliothèque Browser importée dans la suite (``Library    Browser``).
"""
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
    ``self.poll_interval`` (secondes, float) — définis par ``__init__``."""

    def enable_embedded_browser_debugging(self, port=_DEFAULT_CDP_PORT):
        """Active le débogage distant CDP des contrôles WebView2 embarqués.

        Positionne ``WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS`` dans l'environnement
        du **process courant**. WebView2 ne lit cette variable qu'à la création
        du contrôle : ce keyword doit donc être appelé AVANT `Open Sap Logon`
        (ou tout lancement de SAP Logon/Business Client héritant de cet
        environnement, p.ex. via la bibliothèque Process) — l'appeler après
        coup n'a aucun effet sur un client déjà démarré.

        Retourne le port effectif (à repasser à `Get Embedded Browser Page Id`
        / `Switch To Embedded Browser Page` si vous changez la valeur par
        défaut). Idempotent : les arguments déjà présents dans la variable sont
        conservés, les nouveaux leur sont concaténés plutôt que de les écraser.

        Exemple::

            Enable Embedded Browser Debugging
            Open Sap Logon
            Connect To Session
            # ... naviguer jusqu'à l'écran qui affiche le contrôle embarqué ...
            Switch To Embedded Browser Page    Help
            Click    text=Continue
        """
        port = int(port)
        flags = _CDP_ARGS_TEMPLATE % port
        existing = os.environ.get(_WEBVIEW2_ENV_VAR, "").strip()
        os.environ[_WEBVIEW2_ENV_VAR] = ("%s %s" % (existing, flags)).strip() if existing else flags
        return port

    def get_embedded_browser_page_id(self, title, port=_DEFAULT_CDP_PORT,
                                     exact=False, timeout=None):
        """Retourne l'id (catalogue Browser) de la page hébergée par le contrôle
        WebView2 embarqué dont le titre correspond à ``title``.

        Se connecte au point de terminaison CDP ``http://localhost:<port>``
        (``Connect To Browser`` de la bibliothèque Browser, ``use_cdp=True``)
        s'il n'est pas déjà atteint, puis sonde le catalogue des pages jusqu'à
        ``timeout`` (``default_timeout`` de la bibliothèque par défaut) — le
        contrôle se rend de façon asynchrone après l'action SAP GUI qui
        l'affiche.

        ``exact=False`` (défaut) : correspondance par sous-chaîne insensible à
        la casse (les titres de page WebView2 embarquent souvent un suffixe
        dynamique). Échoue en listant les titres de page réellement ouverts si
        aucun ne correspond — erreur auto-corrigible."""
        browser = self._browser()
        timeout_secs = self._timeout_secs(timeout)
        exact = _as_bool(exact)
        page_id = self._find_embedded_page_id(browser, title, exact)
        if page_id is None:
            self._connect_to_embedded_browser(browser, port)
            page_id = poll_until(
                lambda: self._find_embedded_page_id(browser, title, exact),
                timeout_secs, step=self.poll_interval)
        if not page_id:
            titles = self._embedded_page_titles(browser)
            hint = ("\nPages ouvertes :\n%s" % "\n".join("  - %s" % t for t in titles)
                   if titles else
                   "\n(Aucune page ouverte sur ce point de terminaison CDP.)")
            self.take_screenshot()
            raise AssertionError(
                "No embedded browser page with a title matching '%s' within "
                "%.1fs (CDP endpoint http://localhost:%s). Is the SAP GUI/"
                "Business Client screen that renders it open, and was "
                "`Enable Embedded Browser Debugging` called BEFORE the SAP "
                "client started?%s" % (title, timeout_secs, port, hint))
        return page_id

    def switch_to_embedded_browser_page(self, title, port=_DEFAULT_CDP_PORT,
                                        exact=False, timeout=None):
        """Comme `Get Embedded Browser Page Id`, puis active cette page dans la
        bibliothèque Browser (``Switch Page``) : tous les keywords Browser
        suivants (``Click``, ``Fill Text``, ``Get Text``...) agissent alors sur
        le contrôle embarqué. Retourne l'id de la page désormais active."""
        page_id = self.get_embedded_browser_page_id(title, port=port, exact=exact,
                                                     timeout=timeout)
        self._browser().switch_page(page_id)
        return page_id

    # -- helpers (méthodes internes) ------------------------------------------

    def _browser(self):
        """Instance active de la bibliothèque Browser — message d'erreur clair
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
            browser.connect_to_browser("http://localhost:%d" % int(port), use_cdp=True)
        except Exception as err:
            raise RuntimeError(
                "Could not reach the embedded browser control's CDP endpoint "
                "at http://localhost:%s. Checklist: SAP GUI options -> "
                "Interaction Design -> Control Settings -> Browser Control = "
                "Edge; `Enable Embedded Browser Debugging` called BEFORE the "
                "SAP client started; the transaction/screen rendering the "
                "control is open. Original error: %s" % (port, err))

    @staticmethod
    def _embedded_pages(browser):
        for info in browser.get_browser_catalog():
            for context in info.get("contexts", []) or []:
                for page in context.get("pages", []) or []:
                    yield page

    def _find_embedded_page_id(self, browser, title, exact):
        wanted = (title or "").strip().casefold()
        for page in self._embedded_pages(browser):
            page_title = (page.get("title") or "").strip()
            if exact:
                if page_title.casefold() == wanted:
                    return page.get("id")
            elif wanted in page_title.casefold():
                return page.get("id")
        return None

    def _embedded_page_titles(self, browser):
        try:
            return [page.get("title", "") for page in self._embedded_pages(browser)]
        except Exception:
            return []
