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

from robot.utils import timestr_to_secs

from sapfx_common.session_context import current_execution_namespace

from .keywords import (
    ActionKeywords,
    CompositionKeywords,
    EngineKeywords,
    FioriBase,
    FlpKeywords,
    FrameKeywords,
    LocatorKeywords,
    PerceptionKeywords,
    StateKeywords,
)


class SapFioriLibrary(FrameKeywords, LocatorKeywords, EngineKeywords,
                      CompositionKeywords, ActionKeywords, StateKeywords,
                      PerceptionKeywords, FlpKeywords, FioriBase):
    """Résout les contrôles UI5 en sélecteurs utilisables par Browser. Nécessite que la
    bibliothèque Browser soit importée dans la même suite (elle réutilise la page active de Browser)."""

    __version__ = "0.7.0"
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
