"""Mixin contexte de frame : apps Work Zone / cFLP dans des iframes.

`Set Ui5 Frame` (remplace toute la pile, selecteurs prefixes ``>>>``),
`Push/Pop Ui5 Frame` (frames IMBRIQUEES, portee chainee ``a >>> b``),
`Get Ui5 App Frame` / `Push Ui5 App Frame` (la frame APPLICATIVE d'un
launchpad reconnue par ce qu'elle est, jamais par un id genere
``__container<N>``) et `Get Ui5 Frame Stack`.

Extrait de ``SapFioriLibrary.py`` (convention #13).
"""

from robot.api import logger


from .._ui5_runtime import (
    choose_app_frame,
)




class FrameKeywords:
    """Mixin compose dans :class:`SapFioriLibrary` (voir ce module).
    Suppose la page active de Browser accessible via ``self._browser()``
    et la plomberie de ``_base.py`` disponible par composition."""

    # -- contexte de frame (Work Zone / cFLP : apps dans des iframes) ----------

    def set_ui5_frame(self, frame_selector=None):
        """Cible une **iframe** pour toute la résolution UI5 à venir.

        SAP Build Work Zone et le cFLP ouvrent chaque application dans une
        iframe (souvent cross-origin) : le shell top-level n'a PAS les contrôles
        de l'app dans son registre UI5. Donner ici le sélecteur Browser de
        l'iframe fait exécuter le bundle de résolution **dans la frame de
        l'app** et préfixe tous les sélecteurs retournés avec ``<frame> >>>``
        (chaînage de frames Browser/Playwright).

        **Ne PAS écrire le sélecteur à la main sur un launchpad** : mesuré live
        le 2026-08-23 sur SAP Build Work Zone, l'iframe de l'application porte
        un identifiant GÉNÉRÉ par UI5, différent à chaque exécution
        (``__container1``, puis ``__container4``, puis ``__container3`` pour la
        même application), et aucun identifiant ne contient « application ».
        Utiliser `Get Ui5 App Frame`, qui désigne la frame par ce qu'elle est
        (visible, chargeant un document, occupant la zone de contenu), ou son
        raccourci `Push Ui5 App Frame`.

        Sans argument (ou vide), revient à la page principale, le mode nominal
        pour un FLP ABAP classique (apps dans le même document). Exemple::

            ${frame}=    Get Ui5 App Frame
            Set Ui5 Frame    ${frame}
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

    def get_ui5_app_frame(self):
        """Sélecteur de l'iframe qui porte l'**application** du launchpad.

        Un cFLP ouvre chaque application dans une iframe dont l'identifiant est
        GÉNÉRÉ par UI5 : relevé live le 2026-08-23 sur SAP Build Work Zone, la
        même application reçoit ``__container1`` à une exécution et
        ``__container4`` à la suivante, le compteur dépendant du nombre de
        composants instanciés. Écrire ``iframe[id="__container1"]`` dans un test
        revient donc à parier sur un compteur, et le pari se perd au run
        suivant.

        Ce keyword désigne la frame par ce qu'elle EST : visible, chargeant un
        document, occupant la plus grande surface, c'est-à-dire la zone de
        contenu du shell. Retourne un sélecteur positionnel
        ``iframe >> nth=N``, à passer à `Push Ui5 Frame` ou `Set Ui5 Frame`.

        Échoue en NOMMANT ce qui a été trouvé quand aucune application n'est
        ouverte : sur l'accueil du launchpad il n'y a aucune iframe, et le
        diagnostic doit dire cela plutôt que « sélecteur introuvable »."""
        frames = self._browser().evaluate_javascript(
            self._eval_scope(),
            "() => [...document.querySelectorAll('iframe')].map(f => ("
            "{src: f.src || '', width: f.clientWidth, height: f.clientHeight}))",
            arg=None)
        if not isinstance(frames, list):
            frames = []
        index = choose_app_frame(frames)
        if index is None:
            raise AssertionError(
                "Aucune iframe d'application dans cette page (%d iframe(s) "
                "présente(s) : %s). Une application est-elle ouverte ? Sur "
                "l'accueil d'un launchpad il n'y en a aucune : naviguer par "
                "`Open App By Intent` ou cliquer une tuile d'abord."
                % (len(frames),
                   ", ".join("%sx%s %s" % (f.get("width"), f.get("height"),
                                           str(f.get("src") or "")[:60])
                             for f in frames) or "aucune"))
        return "iframe >> nth=%d" % index

    def push_ui5_app_frame(self):
        """Empile la frame de l'application du launchpad, sans avoir à en
        connaître l'identifiant généré. Raccourci de `Get Ui5 App Frame` suivi
        de `Push Ui5 Frame` : la façon recommandée d'entrer dans une
        application ouverte par un cFLP. Retourne le sélecteur empilé."""
        selector = self.get_ui5_app_frame()
        self.push_ui5_frame(selector)
        return selector

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
