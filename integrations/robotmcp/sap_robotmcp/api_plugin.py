"""Plugin rf-mcp pour SapApiLibrary : le 3e canal (OData v2/v4, RFC).

Le canal API n'a pas d'écran : ``get_page_source`` répond par une explication
actionnable (la perception EST la valeur de retour des keywords), et
``get_application_state`` sert l'état réel du canal via le keyword
``List Api Sessions`` (alias ouverts, base_url, sap-client, authentifié,
jamais de credentials). Comme pour l'ECC, cet état n'est routé par aucun
chemin rf-mcp 0.31 : il se consomme via l'outil ``sapfx_state`` de la
surcouche (voir ``sap_robotmcp.server``).
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

from ._guidance import API_HINTS, API_RECOMMENDATION
from ._rf_context import finalize_state, structured_state

STATE_KEYWORD = "List Api Sessions"

_NO_SCREEN = (
    "Le canal API n'a pas d'écran à percevoir : la perception EST la valeur "
    "de retour des keywords (Get Odata Entities, Get Odata Count…). Pour "
    "l'état du canal (alias ouverts, base_url), utiliser la section "
    "application_state (keyword List Api Sessions).")


class ApiStateProvider(LibraryStateProvider):
    """État du canal API : pas de page source, un état applicatif réel."""

    async def get_page_source(
        self,
        session: Any,
        *,
        full_source: bool = False,
        filtered: bool = False,
        filtering_level: str = "standard",
        include_reduced_dom: bool = True,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        # Réponse explicite (et non une page vide) pour les appelants qui ne
        # lisent PAS la capacité déclarée : rf-mcp lui-même appelle le provider
        # sans la consulter. La surcouche, elle, refuse la section en amont et
        # reprend ce même motif via `unsupported_reason`.
        return {"success": False, "error": _NO_SCREEN, "supported": False}

    @staticmethod
    def unsupported_reason(section: str) -> Optional[str]:
        """Motif LISIBLE d'une section que ce canal ne sert pas, pour que le
        refus porté par la capacité déclarée reste actionnable."""
        return _NO_SCREEN if section == "page_source" else None

    async def get_application_state(self, session: Any) -> Optional[Dict[str, Any]]:
        """État réel du canal API (alias ouverts, base_url, authentifié),
        même contrat que les canaux ECC et Fiori : ``connected`` dit si le
        canal a répondu à sa lecture d'état de base, ``state_error`` porte la
        cause sinon.

        Le saut de thread et le contrat best-effort passent par le helper
        partagé : une copie locale ici, et une évolution du contrat (timeout,
        normalisation des erreurs) ne s'appliquerait qu'aux deux autres
        canaux, sans que rien ne le signale."""
        state: Dict[str, Any] = {"active_library": "SapApiLibrary"}
        fatal: Dict[str, str] = {}
        channel = await structured_state(session, STATE_KEYWORD, fatal,
                                         needs_com=False)
        if channel is None:
            state["connected"] = False
            state["state_error"] = fatal.get(
                STATE_KEYWORD, "%s n'a rien retourné" % STATE_KEYWORD)
            return finalize_state(state)
        state["connected"] = True
        state.update(channel if isinstance(channel, dict)
                     else {"channel_state": channel})
        return finalize_state(state)


class SapApiPlugin(StaticLibraryPlugin):
    """Décrit SapApiLibrary à rf-mcp + état du canal + guidance."""

    def __init__(self) -> None:
        metadata = LibraryMetadata(
            name="SapApiLibrary",
            package_name="SapApiLibrary",
            import_path="SapApiLibrary",
            description="Canal API SAP : OData v2/v4 (Gateway, CAP/S4) et RFC "
            "optionnel ; préparation et recoupement des données de test, "
            "stdlib pure.",
            library_type="external",
            categories=["api", "sap"],
            contexts=["api"],
            technology_tags=["odata", "rfc", "gateway"],
            use_cases=["test API SAP", "OData $count", "préparation de données",
                       "recoupement cross-canal"],
            installation_command="pip install -e .",
            load_priority=62,
        )
        capabilities = LibraryCapabilities(
            contexts=["api"],
            features=["odata-v2", "odata-v4", "csrf", "rfc"],
            technology=["odata", "rfc"],
            supports_page_source=False,
            supports_application_state=True,
        )
        hints = LibraryHints(
            standard_keywords=[
                "Open Api Session", "Gateway Should Be Active",
                "Get Odata Entities", "Get Odata Count", "Post Odata",
                "Delete Created Entities", "Get Odata Metadata",
                "Close All Api Sessions", STATE_KEYWORD,
            ],
            error_hints=API_HINTS,
        )
        super().__init__(metadata=metadata, capabilities=capabilities, hints=hints)
        self._provider = ApiStateProvider()

    def get_state_provider(self) -> LibraryStateProvider:
        return self._provider

    def get_prompt_bundle(self) -> PromptBundle:
        return PromptBundle(recommendation=API_RECOMMENDATION)

    def get_keyword_library_map(self) -> Dict[str, str]:
        # Surface publique complète de SapApiLibrary (vérifiée par test
        # contre la bibliothèque réelle).
        return {
            kw.lower(): "SapApiLibrary"
            for kw in (
                # sessions par alias + télémétrie
                "Open Api Session", "Close Api Session",
                "Close All Api Sessions", STATE_KEYWORD,
                "Get Api Telemetry",
                # OData v2/v4 : lectures (pagination server-driven comprise)
                "Get Odata", "Get Odata Entities", "Get Odata Count",
                # OData v2/v4 : écritures (CRUD complet, CSRF/If-Match gérés)
                "Post Odata", "Patch Odata", "Delete Odata",
                "Call Odata Function", "Post Odata Batch",
                # fabrique de données de test (cycle réversible par l'API)
                "Ensure Odata Entity", "Register Created Entity",
                "Get Created Entities", "Delete Created Entities",
                # perception et découverte du canal (le canal sans écran)
                "Get Odata Metadata", "Find Odata Property By Label",
                "List Odata Services", "Lookup Business Term",
                # préflight Gateway (le miroir API des préflights GUI)
                "Get Gateway Status", "Gateway Should Be Active",
                "Wait Until Api Available",
                # RFC optionnel (pyrfc) + pattern BAPI + jobs de fond
                "Open Rfc Connection", "Call Rfc", "Close Rfc Connection",
                "Close All Rfc Connections", "Call Bapi",
                "Commit Bapi Transaction", "Rollback Bapi Transaction",
                "Wait For Background Job",
            )
        }
