"""Plugin rf-mcp pour SapEccLibrary : perception écran SAP GUI desktop + guidance.

Côté ECC, SapEccLibrary EST la bibliothèque active de la session : son state
provider est donc bien sollicité par rf-mcp (contrairement au cas Fiori, où
Browser est la lib web active). ``get_page_source`` exécute, dans le contexte RF
live, le keyword de perception ``Get Screen Signature`` (mixin ``_perception.py``
de SapEccLibrary ; validé e2e contre un A4H vivant).
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

from ._filtering import filter_ecc_signature, normalize_level
from ._guidance import COMMON_HINTS, ECC_HINTS, ECC_RECOMMENDATION
from ._last_seen import LastSeenCompactor
from ._rf_context import finalize_state, perception_text, structured_state
from ._staleness import attach_staleness

# Keyword de perception de SapEccLibrary : retourne la signature texte de l'écran
# actif (une ligne par contrôle, champs éditables préfixés `* `).
PERCEPTION_KEYWORD = "Get Screen Signature"

_UNCHANGED_MARKER = "(unchanged since the previous perception call for this session)"

# En-tête auto-descriptif du mode différentiel : l'agent qui reçoit un diff au
# lieu d'un écran complet doit pouvoir le comprendre sans guidance préalable.
_DIFF_HEADER = (
    "(diff since the previous perception for this session -- '- ' removed, "
    "'+ ' added, '~ ' renamed or value-changed, '= N unchanged line(s)'; "
    "pass full_source=true for the complete screen)\n")

class EccStateProvider(LibraryStateProvider):
    """Vue de l'écran SAP GUI desktop courant pour l'agent.

    ``SapEccLibrary`` a un ``ROBOT_LIBRARY_SCOPE = SUITE`` : chaque suite Robot,
    donc chaque namespace de session rf-mcp, reçoit sa propre instance et sa
    propre connexion COM. Le provider peut ainsi servir plusieurs sessions sans
    transférer d'objet COM ; la compaction reste indexée par ``session_id``.
    """

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
            # Toujours interroger l'écran réel : rien ne garantit qu'aucune action
            # n'a eu lieu depuis le dernier appel, et servir un état périmé juste
            # après une action casserait la boucle perception -> action.
            sig = await perception_text(session, PERCEPTION_KEYWORD)
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        # La comparaison/le diff portent sur la signature COMPLÈTE (pas la vue
        # filtrée), pour qu'un changement de filtering_level entre deux appels ne
        # soit jamais confondu avec un changement d'écran.
        previous = self._last_seen.swap(session.session_id, sig)
        unchanged = previous is not None and previous == sig
        fmt = "ecc-screen-signature"
        served_diff = False
        if unchanged:
            # Agent prudent qui revérifie sans avoir agi : marqueur compact.
            page_source = _UNCHANGED_MARKER
        elif previous is not None and not full_source:
            # Écran déjà vu qui a changé : servir « ce qui a changé » (diff
            # intelligent, renommages appariés) plutôt que tout re-décrire,
            # sauf si le diff ne fait pas gagner de place (écran entièrement
            # remplacé), auquel cas la vue complète reste la plus honnête.
            candidate = _DIFF_HEADER + diff_perception(previous, sig,
                                                       pair_renames=True)
            if len(candidate) < len(sig):
                page_source = candidate
                fmt = "ecc-screen-signature-diff"
                served_diff = True
            else:
                page_source = self._full_view(sig, filtered, filtering_level)
        else:
            page_source = self._full_view(sig, filtered, filtering_level)
        result: Dict[str, Any] = {
            "success": True,
            "session_id": session.session_id,
            "page_source_length": len(page_source),
            "format": fmt,
            "page_source": page_source,
            "unchanged_since_last_call": unchanged,
            "diff_since_last_call": served_diff,
            "filtered": bool(filtered) and not unchanged and not served_diff,
            "cross_session_sharing_detected": False,
            "session_isolation": "suite",
        }
        return attach_staleness(result)

    @staticmethod
    def _full_view(sig: str, filtered: bool, filtering_level: str) -> str:
        if filtered:
            return filter_ecc_signature(sig, normalize_level(filtering_level))
        return sig

    async def get_application_state(self, session) -> Optional[Dict[str, Any]]:
        """État applicatif structuré (idée validée chez les MCP SAP standalone :
        exposer où en est la session, pas seulement l'écran). ``connected`` est
        déduit d'une lecture RÉELLE (la transaction active via le contexte RF),
        jamais d'une machine à états optimiste qui pourrait désynchroniser.

        Sections best-effort au-delà de la transaction (chaque échec est
        consigné dans ``collection_errors`` sans faire tomber l'état) :

        - ``windows``/``modal_open``/``modal_titles`` : la pile de fenêtres
          réelle. C'est le garde-fou du piège vu live sur SESSION_MANAGER :
          ``Run Transaction`` peut rapporter un succès alors qu'un MODAL
          d'erreur est resté ouvert et neutralise l'OK-code ;
        - ``status_message`` : type (E/S/W/I, l'ancre d'assertion
          locale-indépendante) + texte (contexte humain, jamais une assertion) ;
        - ``telemetry`` : compteurs ``session.Info`` du dernier aller-retour.
        """
        state: Dict[str, Any] = {"active_library": "SapEccLibrary"}
        collection_errors: Dict[str, str] = {}
        # La transaction n'est PAS une section comme les autres : elle est la
        # preuve de vie de la session. Son échec court-circuite (connected =
        # False + state_error), il ne dégrade pas.
        fatal: Dict[str, str] = {}
        transaction = await structured_state(session, "Get Current Transaction",
                                             fatal)
        if transaction is None:
            state["connected"] = False
            state["state_error"] = fatal.get(
                "Get Current Transaction",
                "Get Current Transaction n'a rien retourné")
            return finalize_state(state)
        state["connected"] = True
        state["transaction"] = transaction

        windows = await structured_state(session, "Get Open Windows",
                                         collection_errors)
        if windows is not None:
            state["windows"] = windows
            modal = [w for w in windows
                     if isinstance(w, dict) and w.get("modal")]
            state["modal_open"] = bool(modal)
            if modal:
                state["modal_titles"] = [w.get("title", "") for w in modal]
        status = await structured_state(session, "Get Status Message",
                                        collection_errors)
        if status is not None:
            try:
                msg_type, text = status
            except (TypeError, ValueError):
                collection_errors["Get Status Message"] = (
                    "forme inattendue : %r" % (status,))
            else:
                state["status_message"] = {"type": msg_type, "text": text}
        telemetry = await structured_state(session, "Get Session Telemetry",
                                           collection_errors)
        if telemetry is not None:
            state["telemetry"] = telemetry
        return finalize_state(state, collection_errors)


class SapEccPlugin(StaticLibraryPlugin):
    """Décrit SapEccLibrary à rf-mcp + perception écran + guidance."""

    def __init__(self) -> None:
        metadata = LibraryMetadata(
            name="SapEccLibrary",
            package_name="SapEccLibrary",
            import_path="SapEccLibrary",
            description="Pilotage du client lourd SAP GUI (ECC / S/4HANA backend) "
            "via l'API SAP GUI Scripting (COM).",
            library_type="external",
            categories=["desktop", "sap", "ecc"],
            contexts=["desktop"],
            technology_tags=["sapgui", "com", "win32"],
            use_cases=["test SAP GUI desktop", "test transaction ECC", "ALV grid"],
            installation_command="pip install -e .",
            load_priority=61,
        )
        capabilities = LibraryCapabilities(
            contexts=["desktop"],
            features=["screen-signature", "alv-grid"],
            technology=["sapgui", "com"],
            supports_page_source=True,
            supports_application_state=True,
        )
        hints = LibraryHints(
            standard_keywords=[
                "Run Transaction", "Input Text", "Send Vkey", "Read Grid",
                "Wait Until Busy Done", "Wait Until Element Present",
                PERCEPTION_KEYWORD,
            ],
            error_hints=COMMON_HINTS + ECC_HINTS,
        )
        super().__init__(metadata=metadata, capabilities=capabilities, hints=hints)
        self._provider = EccStateProvider()

    def get_state_provider(self) -> LibraryStateProvider:
        return self._provider

    def get_prompt_bundle(self) -> PromptBundle:
        return PromptBundle(recommendation=ECC_RECOMMENDATION)

    def get_keyword_library_map(self) -> Dict[str, str]:
        # Keywords ajoutés/surchargés par le fork (mixins + SapEccLibrary.py) :
        # les centaines de keywords hérités de l'upstream vendored passent par la
        # découverte standard de rf-mcp ; la carte d'intention couvre la
        # valeur ajoutée du fork (vérifiée par test contre la lib réelle).
        return {
            kw.lower(): "SapEccLibrary"
            for kw in (
                # navigation / statut (overrides locale-indépendants)
                "Run Transaction", "Get Current Transaction",
                "Get Status Message", "Status Message Should Be Success",
                # amorçage connexion
                "Open Sap Logon", "Close Sap Logon",
                "Connect To Session With Retry", "Open Connection By String",
                "Attach To Open Session",
                # multi-session par alias (multiplexage, jamais du parallélisme)
                "Open Sap Session", "Create Gui Session", "Switch Sap Session",
                "Get Active Sap Session", "List Sap Sessions",
                "Close Sap Session", "Close All Sap Sessions",
                # synchronisation (+ réglage dynamique des attentes)
                "Wait Until Busy Done", "Wait Until Element Present",
                "Wait Until Element Value Is", "Click Element With Retry",
                "Set Default Timeout", "Set Poll Interval",
                # grilles ALV par titre
                "Read Grid", "Read Full Grid", "Get Grid Column Ids",
                "Get Column Id By Title", "Get Cell Value By Column Title",
                "Set Cell Value By Column Title", "Find Row By Column Value",
                "Select Row By Column Value", "Get Cell Value By Row Content",
                "Read Abap List",
                # tables de dynpro classiques (GuiTableControl, par titre)
                "Read Table Control", "Get Table Control Cell",
                "Set Table Control Cell", "Find Table Control Row",
                # aide à la recherche (matchcode)
                "Pick F4 Value",
                # inventaire DDIC (classification DD02L par lots, artefact).
                # `Reach Se16 Selection Screen` ouvre l'écran de sélection en UN
                # seul endroit (statut type E, popup de choix des champs,
                # dialogue de génération) : hors de la carte, un agent
                # ré-improvise ces trois branches, soit exactement les copies
                # divergentes que ce keyword a supprimées.
                "Reach Se16 Selection Screen", "Fill Multiple Selection",
                "Classify Ddic Objects", "Get Ddic Classification Map",
                "Validate Ddic Scope", "Record Ddic Probe",
                "Sample Ddic Objects For Probe", "Merge Ddic Name Lists",
                "Write Ddic Inventory Artifact",
                "Compare Ddic Inventory Artifacts",
                # essentiels upstream que l'agent utilise en permanence
                "Input Text", "Send Vkey",
                # diagnostic / préflight scripting + télémétrie
                "Get Scripting Status", "Scripting Should Be Fully Enabled",
                "Enable Test Tool Mode", "Get Session Telemetry",
                "Get List Rendering Status", "Abap List Should Be Readable",
                "Get Client Security Status", "Client Security Should Be Hardened",
                # auto-réparation de localisateurs
                "Resolve Element With Healing", "Get Closest Element Ids",
                # localisateurs humains (libellé visible + géométrie) + vocabulaire
                "Find Element By Label", "Fill Field By Label",
                "Read Field By Label", "Click Button By Label",
                "Lookup Business Term",
                # perception
                PERCEPTION_KEYWORD, "Get Open Windows",
                "Get Screenshot As Base64", "Log Screenshot",
                "Get Annotated Screenshot", "Log Annotated Screenshot",
                # carte numérotée + action par référence @N (boucle courte)
                "Get Screen Map", "Resolve Screen Ref",
                "Click Screen Ref", "Fill Screen Ref",
                # assertions visuelles + sentinelle de dérive
                "Get Screen Perceptual Hash", "Screen Should Match Baseline",
                "Get Element Perceptual Hash", "Element Should Match Baseline",
                "Get Screen Tile Hashes", "Check Screen Against Watch",
                # effecteur coordonnées (zones hors API : GuiShell/GuiChart)
                "Get Element Screen Region", "Click Element At Offset",
                # pont navigateur embarqué (WebView2/CDP dans une fenêtre SAP)
                "Enable Embedded Browser Debugging",
                "Get Embedded Browser Page Id", "Switch To Embedded Browser Page",
            )
        }
