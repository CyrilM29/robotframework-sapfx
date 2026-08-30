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
                # Clé COMPOSITE d'un service draft-enabled : un POST y crée un
                # BROUILLON, que ni le $count ni une lecture ordinaire ne
                # rendent, et l'URI annoncée en Location n'est pas adressable.
                "Build Draft Entity Path",
                # perception et découverte du canal (le canal sans écran)
                "Get Odata Metadata", "Find Odata Property By Label",
                "List Odata Services", "Lookup Business Term",
                # sonde d'existence TOLÉRANTE : elle consigne statut HTTP et
                # code technique par entity set au lieu de s'arrêter au premier
                # refus. À ne pas confondre avec `Read Business Entities In One
                # Roundtrip`, dont le tout ou rien est le bon comportement pour
                # PRÉPARER des données, et le mauvais pour SONDER.
                "Probe Odata Entity Sets",
                # lecture HTTP brute et tolérante : ce que le serveur SERT
                # quand ce n'est pas de l'OData (page HTML d'un approuter BTP,
                # découverte OpenID, corps exact d'un refus). Née de la
                # reconnaissance Work Zone 2026-08-26, où lire un corps HTML
                # exigeait de le détourner du message d'échec de Get Odata.
                "Get Http Response",
                # Le verdict STRUCTUREL d'une réponse brute : trois familles
                # de 404 se cachent sous un même statut (routeur de
                # plateforme, application, ressource) et un 200 au corps HTML
                # n'est PAS une donnée. Le complément tolérant du préflight.
                "Classify Http Response",
                # préflight Gateway (le miroir API des préflights GUI) ; les
                # états couvrent aussi une cible derrière un IdP (BTP) :
                # identity_provider_redirect, login_page (HTTP 200 dont le
                # corps est une page de connexion, le « vert et faux »)
                "Get Gateway Status", "Gateway Should Be Active",
                "Wait Until Api Available",
                # RFC optionnel (pyrfc) + pattern BAPI + jobs de fond
                "Open Rfc Connection", "Call Rfc", "Close Rfc Connection",
                "Close All Rfc Connections", "Call Bapi",
                "Commit Bapi Transaction", "Rollback Bapi Transaction",
                "Wait For Background Job",
                # préflight du canal RFC (le binding et le runtime natif sont
                # deux absences distinctes, deux remèdes distincts) et
                # perception d'identité : un canal ouvert ne dit pas encore
                # vers QUOI.
                "Get Rfc Channel Status", "Rfc Channel Should Be Available",
                "Get Rfc Connection Attributes",
                # lecture générique de table (miroir sans écran de Read Grid)
                # et classification d'un refus par CODE technique : le texte
                # d'un échec RFC est localisé, son code ne l'est pas.
                # L'identifiant de message (classe, type, numéro) est le
                # critère FIN qui le complète, tout aussi non localisé : le
                # code est stable mais grossier, deux causes très différentes
                # pouvant le partager.
                "Read Rfc Table", "Rfc Should Fail With Code",
                "Rfc Should Fail With Message Id",
                # perception des jobs de fond : quels jobs la cible porte
                # déjà pour chaque issue de l'attente, et ce que la
                # bibliothèque cartographie des statuts. C'est ce qui permet
                # d'éprouver l'attente en LECTURE SEULE, sans créer ni
                # annuler un job, et sans graver des noms d'exploitation.
                "Find Background Job Cases", "Get Background Job Status Model",
                # surface du canal : un relevé déterministe par cible, et sa
                # comparaison HORS système. « Quels modules ici et pas
                # là-bas » ne se répond pas par une note dans un document.
                "Write Rfc Surface Artifact", "Read Rfc Surface Artifact",
                "Compare Rfc Surface Artifacts",
                # posture de CONFIGURATION DE SÉCURITÉ. Le module de lecture
                # ne refuse pas un paramètre inconnu : il rend un code de
                # retour non nul et une chaîne VIDE, et il est SENSIBLE À LA
                # CASSE. Un agent qui lirait un paramètre « à la main » aurait
                # donc une réponse plausible et fausse ; ces keywords jugent
                # sur le code de retour, gardent « non mesurable » distinct de
                # « non conforme », et n'en font jamais un succès.
                "Read Profile Parameters", "Profile Parameters Should Be Defined",
                "Read Standard Users Status",
                # la posture se compare à une référence committée PAR CIBLE :
                # la question utile n'est pas « ce système est-il durci »
                # (jugement discutable, rouge à vie sur un bac à sable) mais
                # « sa configuration a-t-elle bougé » (réponse binaire).
                "Build Security Posture", "Write Security Posture",
                "Read Security Posture",
                "Security Posture Should Not Have Drifted",
                # deux inventaires dont la lecture brute induit en erreur :
                # le journal d'audit peut être ARMÉ sans filtrer (10 slots
                # déclarés, zéro actif, mesuré sur les deux releases), donc
                # « rsau/enable vaut 1 » n'est pas « l'audit enregistre » ; et
                # l'information de logon d'une destination RFC n'est pas dans
                # une colonne mais dans un agrégat de marqueurs.
                "Get Audit Configuration", "Read Rfc Destination Inventory",
                # lectures de PREUVES d'exploitation (la famille que Read Rfc
                # Table débloque) : documents de modification CDHDR/CDPOS
                # (l'assertion d'audit), statuts d'IDoc jugés par CODE,
                # journaux applicatifs comptés par sévérité (BALHDR), et le
                # journal d'un job par la chaîne XBP (BP_JOBLOG_READ n'est
                # pas appelable à distance : mesuré live 2026-08-29).
                "Read Change Documents", "Get Idoc Status",
                "Read Application Log", "Get Job Log",
            )
        }
