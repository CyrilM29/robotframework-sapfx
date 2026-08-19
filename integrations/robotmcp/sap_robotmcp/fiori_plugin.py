"""Plugin rf-mcp pour SapFioriLibrary : perception UI5 + guidance.

Subtilité vérifiée dans rf-mcp : le state provider de page source n'est invoqué
que pour la **bibliothèque web active**, résolue à ``Browser`` ici (SapFioriLibrary
ne pilote pas la page, elle s'appuie sur la page de Browser). Le provider Browser
builtin l'emporte donc, et CE provider n'est en pratique pas appelé pour la page.

La perception UI5 passe donc avant tout par un **keyword** que l'agent appelle
explicitement, ``Get Ui5 Page Tree`` (implémenté dans SapFioriLibrary : il exécute
le JS d'arbre de _ui5_js.py sur la page Browser active ; validé e2e), plus les
hints qui l'y invitent. On fournit tout de même un state provider en repli, au cas
où SapFioriLibrary serait la lib active (sessions hybrides), via le même pattern
RF-context.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from robotmcp.plugins.base import StaticLibraryPlugin
from robotmcp.plugins.contracts import (
    LibraryCapabilities,
    LibraryHints,
    LibraryMetadata,
    LibraryStateProvider,
    PromptBundle,
)
from sapfx_common.perception_diff import diff_perception

from ._filtering import filter_ui5_tree, normalize_level
from ._guidance import COMMON_HINTS, FIORI_HINTS, FIORI_RECOMMENDATION
from ._last_seen import LastSeenCompactor
from ._rf_context import finalize_state, perception_text, structured_state
from ._staleness import attach_staleness

# Keyword de perception de SapFioriLibrary : retourne l'arbre de contrôles UI5
# sérialisé en XML (exécute le JS d'arbre de _ui5_js.py sur la page Browser active).
PERCEPTION_KEYWORD = "Get Ui5 Page Tree"

# Keyword d'état applicatif : tout l'état du canal web en UN aller-retour
# (portée de frame, runtime UI5, messages). Assemblé côté bibliothèque parce
# qu'à travers rf-mcp, c'est la traversée du contexte RF qui coûte, pas le JS.
STATE_KEYWORD = "Get Ui5 Application State"

_UNCHANGED_MARKER = "(unchanged since the previous perception call for this session)"

# En-tête auto-descriptif du mode différentiel (cf. ecc_plugin._DIFF_HEADER) :
# ici le diff porte sur l'arbre XML éclaté une balise par ligne.
_DIFF_HEADER = (
    "(diff since the previous perception for this session, one XML tag per "
    "line -- '- ' removed, '+ ' added, '= N unchanged line(s)'; pass "
    "full_source=true for the complete tree)\n")


class FioriStateProvider(LibraryStateProvider):
    """Repli : vue de l'arbre de contrôles UI5 si SapFioriLibrary est lib active."""

    def __init__(self) -> None:
        self._last_seen = LastSeenCompactor()

    async def get_page_source(
        self,
        session,
        *,
        full_source: bool = False,
        filtered: bool = False,
        filtering_level: str = "standard",
        include_reduced_dom: bool = True,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        try:
            # Toujours interroger la page réelle (cf. EccStateProvider.get_page_source
            # pour le raisonnement) : jamais de cache qui risquerait de servir un
            # arbre périmé juste après une action.
            tree = await perception_text(session, PERCEPTION_KEYWORD,
                                         needs_com=False)
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        # Comparaison/diff sur l'arbre COMPLET (cf. EccStateProvider : un
        # changement de filtering_level entre deux appels ne doit jamais passer
        # pour un changement de page).
        previous = self._last_seen.swap(session.session_id, tree)
        unchanged = previous is not None and previous == tree
        fmt = "ui5-control-tree"
        served_diff = False
        if unchanged:
            page_source = _UNCHANGED_MARKER
        elif previous is not None and not full_source:
            # Arbre déjà vu qui a changé : servir le diff (une balise par
            # ligne), sauf s'il ne fait pas gagner de place (page remplacée).
            candidate = _DIFF_HEADER + diff_perception(previous, tree, xml=True)
            if len(candidate) < len(tree):
                page_source = candidate
                fmt = "ui5-control-tree-diff"
                served_diff = True
            else:
                page_source = self._full_view(tree, filtered, filtering_level)
        else:
            page_source = self._full_view(tree, filtered, filtering_level)
        result: Dict[str, Any] = {
            "success": True,
            "session_id": session.session_id,
            "page_source_length": len(page_source),
            "format": fmt,
            "page_source": page_source,
            "unchanged_since_last_call": unchanged,
            "diff_since_last_call": served_diff,
            "filtered": bool(filtered) and not unchanged and not served_diff,
        }
        return attach_staleness(result)

    @staticmethod
    def _full_view(tree: str, filtered: bool, filtering_level: str) -> str:
        if filtered:
            return filter_ui5_tree(tree, normalize_level(filtering_level))
        return tree

    async def get_application_state(self, session) -> Optional[Dict[str, Any]]:
        """État applicatif RÉEL du canal Fiori (miroir de l'état enrichi ECC,
        servi en direct par ``sapfx_state``), jamais un cache :

        - ``connected`` : le canal a répondu à sa lecture d'état ; faux =
          ``state_error`` porte la cause, comme sur les canaux ECC et API ;
        - ``frame_stack`` : la portée iframe active (Work Zone/cFLP), le
          contexte à connaître avant toute résolution ;
        - ``ui5_runtime`` : y a-t-il un runtime UI5 dans cette portée ;
        - ``ui5_messages`` : MessageManager + toasts récents (assertion par
          TYPE, convention n°3 côté web), présents SEULEMENT si oui.

        Le tout en **un** aller-retour de contexte RF (`Get Ui5 Application
        State` assemble côté bibliothèque) : cette section est servie à chaque
        tour d'agent, et c'est la traversée du contexte qui coûte, pas le JS.

        Hors runtime UI5, la section messages est rangée en ``not_applicable``,
        jamais en erreur : `Get Ui5 Messages` échoue durement dans ce cas, or
        les pages UI5 Web Components (moteur ``wc``), le WebGUI classique
        (``sid``) et les zones non-SAP d'une page hybride (``dom``) sont des
        cibles LÉGITIMES de cette bibliothèque. Les lire sans condition faisait
        porter à ces sessions une erreur de collecte permanente, à chaque tour.
        Le keyword sonde donc le runtime d'abord, avec la seule expression web
        du dépôt qui n'injecte PAS le bundle ``__SAPFX`` : une simple lecture
        d'état ne doit pas instrumenter ``fetch``/``XMLHttpRequest`` dans
        l'application sous test.
        """
        state: Dict[str, Any] = {"active_library": "SapFioriLibrary"}
        fatal: Dict[str, str] = {}
        live = await structured_state(session, STATE_KEYWORD, fatal,
                                      needs_com=False)
        if not isinstance(live, dict):
            state["connected"] = False
            state["state_error"] = fatal.get(
                STATE_KEYWORD,
                "%s a retourné une forme inattendue : %r"
                % (STATE_KEYWORD, type(live).__name__))
            return finalize_state(state)

        state["connected"] = True
        state["frame_stack"] = live.get("frame_stack", [])
        runtime = bool(live.get("ui5_runtime"))
        state["ui5_runtime"] = runtime
        collection_errors: Dict[str, str] = {}
        not_applicable: Dict[str, str] = {}
        if not runtime:
            not_applicable["ui5_messages"] = (
                "pas de runtime UI5 dans la portée courante : page UI5 Web "
                "Components, WebGUI (moteur sid), zone non-SAP (moteur dom) "
                "ou page pas encore chargée. Section sans objet, pas une "
                "erreur ; Get Page Composition en donne le détail.")
        elif "messages" in live:
            state["ui5_messages"] = live["messages"]
        else:
            collection_errors["ui5_messages"] = str(
                live.get("messages_error") or "lecture des messages indisponible")
        return finalize_state(state, collection_errors, not_applicable)


class SapFioriPlugin(StaticLibraryPlugin):
    """Décrit SapFioriLibrary à rf-mcp + perception UI5 + guidance."""

    def __init__(self) -> None:
        metadata = LibraryMetadata(
            name="SapFioriLibrary",
            package_name="SapFioriLibrary",
            import_path="SapFioriLibrary",
            description="Résolution de contrôles UI5 (role/xpath) et sid WebGUI "
            "pour SAP Fiori / S/4HANA, aux côtés de la bibliothèque Browser.",
            library_type="external",
            categories=["web", "sap", "ui5"],
            contexts=["web"],
            technology_tags=["ui5", "sapui5", "fiori", "playwright"],
            use_cases=["test SAP Fiori", "test SAPUI5", "test SAP GUI for HTML"],
            installation_command="pip install -e .",
            load_priority=60,
        )
        capabilities = LibraryCapabilities(
            contexts=["web"],
            features=["ui5-control-tree", "ui5-xpath", "webgui-sid",
                      "ui5-web-components"],
            technology=["ui5", "playwright"],
            supports_page_source=True,
            # Le provider Fiori SERT un état applicatif (portée de frame
            # active, messages UI5 récents) : la capacité doit le déclarer,
            # comme les plugins miroirs ECC et API. La déclarer fausse ne se
            # voyait pas (l'overlay appelle les providers en direct, sans lire
            # le drapeau), mais tout consommateur qui, lui, respecte la
            # capacité déclarée sauterait silencieusement cet état.
            supports_application_state=True,
        )
        hints = LibraryHints(
            standard_keywords=[
                "Resolve Ui5 Control", "Click Ui5 Control", "Fill Ui5 Input",
                "Get Ui5 Xpath", "Resolve Ui5 By Xpath", PERCEPTION_KEYWORD,
            ],
            error_hints=COMMON_HINTS + FIORI_HINTS,
        )
        super().__init__(metadata=metadata, capabilities=capabilities, hints=hints)
        self._provider = FioriStateProvider()

    def get_state_provider(self) -> LibraryStateProvider:
        return self._provider

    def get_prompt_bundle(self) -> PromptBundle:
        return PromptBundle(recommendation=FIORI_RECOMMENDATION)

    # SapFioriLibrary cohabite avec Browser dans la même suite, jamais à sa place.
    def get_incompatible_libraries(self) -> list:
        return ["SeleniumLibrary"]

    def get_keyword_library_map(self) -> Dict[str, str]:
        # Surface publique complète de SapFioriLibrary (rf-mcp retombe sur sa
        # découverte standard pour le reste, mais la carte d'intention doit être
        # exhaustive, vérifiée par test contre la lib réelle).
        return {
            kw.lower(): "SapFioriLibrary"
            for kw in (
                # résolution role / xpath / fallback
                "Resolve Ui5 Control", "Resolve Ui5 By Xpath", "Get Ui5 Xpath",
                "Resolve Ui5 With Fallback",
                # contexte de frame (Work Zone / cFLP : apps dans des iframes,
                # pile pour les frames IMBRIQUÉES)
                "Set Ui5 Frame", "Push Ui5 Frame", "Pop Ui5 Frame",
                "Get Ui5 Frame Stack",
                # actions
                "Click Ui5 Control", "Click Ui5 By Xpath", "Fill Ui5 Input",
                # lecture / assertions
                "Read Ui5 Table", "Get Ui5 Text", "Ui5 Control Should Be Visible",
                "Ui5 Text Should Be", "Get Ui5 Match Count",
                # repos réseau/busy + messages applicatifs + upload
                "Wait For Ui5 Idle", "Get Ui5 Messages",
                "Ui5 Should Have No Messages Of Type", "Upload File Via Ui5",
                # sonde de runtime : la question à poser AVANT tout keyword qui
                # exige UI5 (pages wc/sid/dom = cibles légitimes, pas des pannes)
                # + l'état du canal en un appel (ce que sert sapfx_state)
                "Ui5 Runtime Is Present", STATE_KEYWORD,
                # moteur WebGUI sid (SAP GUI for HTML)
                "Resolve Sid", "Click Sid", "Fill Sid Input", "Sid Should Be Visible",
                # moteur Web Components (pages ui5-* hors registre UI5)
                "Resolve Wc Control", "Click Wc Control", "Fill Wc Input",
                "Get Wc Text", "Wc Control Should Be Visible", "Get Wc Match Count",
                # moteur DOM générique (zones NON-SAP d'une page hybride)
                "Resolve Dom Element", "Click Dom Element", "Fill Dom Input",
                "Get Dom Text", "Dom Element Should Be Visible",
                "Get Dom Match Count",
                # perception + diagnostic
                PERCEPTION_KEYWORD, "Get Page Composition",
                "Get Fiori Diagnostics", "Log Fiori Diagnostics",
                # carte numérotée + action par référence @N (boucle courte)
                "Get Ui5 Page Map", "Resolve Ui5 Ref",
                "Click Ui5 Ref", "Fill Ui5 Ref",
                # navigation FLP par intent + login IDP + vocabulaire métier
                "Open Fiori App", "Log In Via Identity Provider",
                "Lookup Business Term",
                # assertions visuelles (parité du canal ECC)
                "Get Ui5 Perceptual Hash", "Ui5 Screen Should Match Baseline",
                # réglage dynamique des attentes
                "Set Ui5 Timeout", "Set Poll Interval",
            )
        }
