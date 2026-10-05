"""Plomberie partagee des mixins Fiori (prive) : evaluation JS, retries.

Le socle que tous les mixins atteignent par composition : acces a la page
active de Browser (``_browser``), evaluation JS dans la portee de frame
courante (``_evaluate``/``_eval_scope``), boucle de resolution avec sondage
(``_resolve``), action avec relance (``_act_with_retry``), choix d'un match
(``_pick*``), attente de visibilite par enum interne (``_wait_visible`` : la
conversion d'arguments RF n'existe pas via ``get_library_instance``), capture
PNG (``_page_png``) et les reglages dynamiques `Set Ui5 Timeout` /
`Set Poll Interval` (ancienne valeur retournee, restaurable en teardown).

Extrait de ``SapFioriLibrary.py`` (convention #13).
"""

from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn
from robot.utils import secs_to_timestr, timestr_to_secs

from sapfx_common.polling import poll_until, retry_until

from .._ui5_js import (
    RESOLVE_ROLE_JS,
)
from .._ui5_runtime import (
    build_control_selector,
    selector_to_json,
)




class FioriBase:
    """Mixin compose dans :class:`SapFioriLibrary` (voir ce module).
    Suppose la page active de Browser accessible via ``self._browser()``
    et la plomberie de ``_base.py`` disponible par composition."""

    #: Poses par ``SapFioriLibrary.__init__`` ; declares ici pour mypy.
    ui5_timeout: float
    poll_interval: float

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

    def _page_png(self):
        """Capture PNG de la page active via la bibliothèque Browser :
        ``return_as=bytes`` quand disponible (Browser récents), sinon repli
        sur le fichier retourné par `Take Screenshot`. Stubbable en test.

        Le repli fichier LIT le chemin déjà rendu quand Browser en a rendu un
        malgré ``return_as=bytes`` : il ne reprend jamais une seconde capture,
        qui montrerait un autre instant de la page que celle qu'on croit
        décrire (et paierait deux fois le coût)."""
        browser = self._browser()
        raw = None
        try:
            from Browser.utils.data_types import ScreenshotReturnType
        except ImportError:                 # Browser absent (fakes de test) ou
            pass                            # arborescence interne déplacée
        else:
            try:
                raw = browser.take_screenshot(
                    return_as=ScreenshotReturnType.bytes, log_screenshot=False)
            except TypeError:               # Browser sans log_screenshot...
                try:
                    raw = browser.take_screenshot(
                        return_as=ScreenshotReturnType.bytes)
                except TypeError:           # ...ou sans return_as du tout
                    raw = None
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw)
        path = raw if isinstance(raw, str) else browser.take_screenshot()
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
