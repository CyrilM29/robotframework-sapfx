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

import asyncio
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
from ._rf_context import run_keyword_in_context
from ._staleness import staleness_warning

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
        return {"success": False, "error": _NO_SCREEN}

    async def get_application_state(self, session: Any) -> Optional[Dict[str, Any]]:
        state: Dict[str, Any] = {"active_library": "SapApiLibrary"}
        try:
            channel = await asyncio.to_thread(
                run_keyword_in_context, session, STATE_KEYWORD,
                allow_structured=True)
        except Exception as exc:
            state["state_error"] = str(exc)
        else:
            state.update(channel if isinstance(channel, dict)
                         else {"channel_state": channel})
        warning = staleness_warning()
        if warning:
            state["stale_code_warning"] = warning
        return state


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
                "Open Api Session", "Get Odata Entities", "Get Odata Count",
                "Post Odata", "Close All Api Sessions", STATE_KEYWORD,
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
                # sessions par alias
                "Open Api Session", "Close Api Session",
                "Close All Api Sessions", STATE_KEYWORD,
                # OData v2/v4
                "Get Odata", "Get Odata Entities", "Get Odata Count",
                "Post Odata",
                # RFC optionnel (pyrfc)
                "Open Rfc Connection", "Call Rfc", "Close Rfc Connection",
            )
        }
