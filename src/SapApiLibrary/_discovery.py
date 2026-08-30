"""Mixin perception et preflight du canal API (il n'a pas d'ecran).

`Get Odata Metadata` (``$metadata`` v2/v4 parse : entity sets, cles,
proprietes, libelles ``sap:label``, capacites par entity set),
`Find Odata Property By Label` (le localisateur « libelle humain » cote API,
contrat d'ambiguite maison), `List Odata Services` (catalogue Gateway),
`Get Gateway Status` / `Gateway Should Be Active` / `Wait Until Api
Available` (chaque etat avec sa remediation NOMMEE, le cas fondateur etant
la Gateway desactivee d'un conteneur A4H re-cree) et `Lookup Business Term`.

Extrait de ``SapApiLibrary.py`` (convention #13).
"""
from __future__ import annotations

import time
from typing import Any, Optional

from robot.utils import timestr_to_secs

from sapfx_common import gateway_status, odata_metadata
from sapfx_common.polling import poll_until
from sapfx_common.vocabulary import lookup_as_dict

from ._http import _as_bool
from ._odata_read import OdataReadKeywords


class DiscoveryKeywords(OdataReadKeywords):
    """Mixin de :class:`SapApiLibrary` : perception et preflight du canal.
    Herite des lectures (`List Odata Services` lit le catalogue par
    `Get Odata Entities`)."""

    def get_odata_metadata(self, service_path: str, alias: str = "default",
                           refresh: bool = False) -> dict[str, Any]:
        """Télécharge et parse le ``$metadata`` du service (v2 ET v4) en dict
        JSON-safe : ``{"version", "entity_sets": {nom: {"entity_type",
        "keys", "properties": {nom: {"type", "nullable", "label"}}}},
        "function_imports", "actions"}``. C'est la **perception** du canal
        API : ce que `Get Screen Signature` est à un écran, ce keyword l'est
        à un service (exploration agent, plans de test, discovery).

        Mis en cache par session et par racine de service (le $metadata ne
        bouge pas en cours de suite) ; ``refresh=True`` force le
        rechargement."""
        session = self._session(alias)
        key = service_path.rstrip("/")
        if not _as_bool(refresh) and key in session.metadata_cache:
            return session.metadata_cache[key]
        status, _, body = self._request(
            alias, "GET", key + "/$metadata", None,
            headers={"Accept": "application/xml"})
        try:
            parsed = odata_metadata.parse_metadata(
                body.decode("utf-8-sig", errors="replace"))
        except ValueError as err:
            raise AssertionError(
                "%s (service '%s', statut %d)." % (err, service_path, status))
        parsed["service_path"] = key
        session.metadata_cache[key] = parsed
        return parsed

    def find_odata_property_by_label(self, service_path: str, label: str,
                                     alias: str = "default",
                                     entity_set: Optional[str] = None
                                     ) -> list[dict[str, Any]]:
        """Cherche les propriétés du service dont le libellé humain
        (``sap:label`` du $metadata) correspond à ``label`` : le localisateur
        « intention utilisateur » du canal API, pendant des localisateurs par
        libellé du canal GUI. Retourne TOUS les candidats ``{"entity_set",
        "property", "label", "type", "match"}`` (contrat d'ambiguïté maison :
        l'appelant tranche, jamais de premier-match silencieux) ;
        ``entity_set`` restreint la recherche. Aucun candidat = échec
        actionnable listant un extrait des libellés connus."""
        metadata = self.get_odata_metadata(service_path, alias=alias)
        candidates = odata_metadata.find_property_by_label(
            metadata, label, entity_set)
        if not candidates:
            known = odata_metadata.known_labels(metadata)
            raise AssertionError(
                "Aucune propriété au libellé « %s » dans '%s'%s. Libellés "
                "connus (extrait) : %s. Explorer avec Get Odata Metadata."
                % (label, service_path,
                   " (entity set %s)" % entity_set if entity_set else "",
                   ", ".join(known) if known else
                   "aucun (service sans sap:label)"))
        return candidates

    def list_odata_services(self, alias: str = "default",
                            catalog_path: Optional[str] = None,
                            **query: str) -> list[dict[str, Any]]:
        """Liste les services OData actifs de la Gateway via son catalogue
        (``ServiceCollection``) : la **découverte** du canal API. Retourne
        une liste JSON-safe ``{"id", "title", "technical_name",
        "service_url", "version"}`` par service. ``catalog_path`` remplace le
        chemin standard au besoin ; les options OData passent en arguments
        nommés (``top=10``)."""
        path = catalog_path or gateway_status.CATALOG_SERVICE_PATH
        query.setdefault("format", "json")
        entries = self.get_odata_entities(path, alias=alias, **query)
        return odata_metadata.simplify_catalog_entries(entries)

    def get_http_response(self, path: str, alias: str = "default",
                          max_chars: int = 20000,
                          headers: Optional[dict] = None,
                          **query: str) -> dict[str, Any]:
        """Lecture HTTP **brute et tolérante** d'un chemin de la session :
        retourne ``{"status", "headers", "body", "truncated", "error",
        "url"}`` sans JAMAIS lever. C'est la perception de ce que le serveur
        SERT vraiment, quand ce n'est pas de l'OData : la page HTML d'un
        approuter BTP, un document de découverte OpenID, le corps exact d'un
        refus. Né d'une reconnaissance live (2026-08-26, site SAP Build Work
        Zone) où lire un corps HTML exigeait de le détourner du message
        d'échec de `Get Odata` : un détournement, pas une méthode.

        ``status`` est ``None`` avec ``error`` renseigné quand la connexion
        elle-même a échoué (système éteint, ou redirection cross-origin vers
        un fournisseur d'identité, refusée par le garde same-origin : le
        message le dit). ``body`` est décodé UTF-8 (remplacement) et tronqué
        à ``max_chars`` (``truncated`` le signale : troncature jamais
        muette). ``headers`` ajoute des en-têtes à CETTE requête (poser
        ``Accept`` autrement, sans toucher la session) ; les options de query
        passent en arguments nommés. Compte dans la télémétrie comme toute
        traversée réseau. Pour de l'OData, préférer `Get Odata Entities` et
        ses assertions ; pour un verdict classé, `Get Gateway Status`."""
        status, resp_headers, body, truncated, error, url = \
            self._probe_response(alias, path, query or None,
                                 max_chars=int(max_chars),
                                 extra_headers=headers)
        return {"status": status,
                "headers": {str(k): str(v) for k, v in resp_headers.items()},
                "body": body, "truncated": bool(truncated),
                "error": error, "url": url}

    def classify_http_response(self, response: dict) -> str:
        """Range une réponse de `Get Http Response` dans une **famille de
        reconnaissance**, par des critères purement structurels : statut,
        en-tête technique du routeur de plateforme, et forme du corps (JSON ou
        HTML), jamais un texte localisé (convention #3).

        Familles : ``unreachable``, ``unknown_route`` (404 portant
        ``x-cf-routererror`` : le préfixe n'est routé vers AUCUNE
        application), ``missing_route`` (404 sans cet en-tête : une
        application a répondu, cette route-là n'existe pas), ``forbidden``,
        ``dialog`` (4xx au corps JSON : l'application traite et explique),
        ``login_page`` (2xx au corps HTML : PAS une donnée, le « vert et
        faux » d'une cible derrière un fournisseur d'identité), ``data``,
        ``other``.

        Le complément tolérant de `Get Gateway Status`, pour cartographier un
        canal plutôt que le valider : trois familles de 404 se cachent sous un
        même statut, et c'est la couche qui répond qu'il s'agit d'identifier.
        Toujours sonder AUSSI un chemin volontairement absent sur le même hôte
        (le témoin absurde) : sans lui, on ne sait pas si un 404 qualifie la
        ressource ou l'hôte entier. ::

            ${reponse}=    Get Http Response    /odata
            ${famille}=    Classify Http Response    ${reponse}
        """
        return gateway_status.classify_http_response(
            response.get("status"), response.get("headers"),
            response.get("body") or "")

    def get_gateway_status(self, alias: str = "default",
                           catalog_path: Optional[str] = None) -> dict[str, Any]:
        """Préflight du canal API : sonde le catalogue Gateway et classe le
        résultat en dict JSON-safe ``{"status", "http_status", "detail",
        "remediation", "catalog_path", "base_url"}``. États : ``ok``,
        ``unreachable``, ``auth_failed``, ``forbidden``,
        ``catalog_not_found``, ``gateway_inactive`` (le cas A4H : conteneur
        re-créé → HTTP 500 ``/IWFND/CM_COS/003``, remédiation = activité IMG
        ``/IWFND/IWF_ACTIVATE``), ``server_error``, et les deux états d'une
        cible derrière un fournisseur d'identité (relevés live sur un site
        SAP Build Work Zone, 2026-08-26) : ``identity_provider_redirect``
        (redirection vers l'IdP, ou refus du garde same-origin) et
        ``login_page`` (HTTP 200 dont le corps est une page HTML de
        connexion : un « vert et faux » sans ce classement, car AUCUNE route
        d'un tel site ne renvoie de défi d'authentification). Ne lève
        jamais : le miroir API de `Get Scripting Status`."""
        session = self._session(alias)
        path = catalog_path or gateway_status.CATALOG_SERVICE_PATH
        code, excerpt, error = self._probe(alias, path,
                                           {"format": "json", "top": "1"})
        result = gateway_status.classify_gateway_probe(code, excerpt, error)
        result["catalog_path"] = path
        result["base_url"] = session.base_url
        return result

    def gateway_should_be_active(self, alias: str = "default",
                                 catalog_path: Optional[str] = None) -> None:
        """Échoue (message auto-corrigible nommant la remédiation) si la
        Gateway OData n'est pas opérationnelle : à appeler en Suite Setup
        avant tout test OData, comme `Scripting Should Be Fully Enabled`
        côté GUI."""
        result = self.get_gateway_status(alias=alias, catalog_path=catalog_path)
        if result["status"] != "ok":
            raise AssertionError(gateway_status.format_gateway_failure(result))

    def wait_until_api_available(self, alias: str = "default",
                                 path: Optional[str] = None,
                                 timeout: str = "2m",
                                 poll: str = "2s") -> dict[str, Any]:
        """Attend que le canal API réponde (sonde ``path``, défaut le
        catalogue Gateway, jusqu'à un statut ``ok``) : le préflight d'un
        système qui (re)démarre, typiquement l'A4H après ``docker start``
        (le boot ABAP prend plusieurs minutes). Jamais de ``time.sleep`` dans
        une suite : ce keyword EST l'attente. Retourne ``{"available": True,
        "waited_seconds", "status"}`` ; échec au timeout avec le dernier
        diagnostic classé et sa remédiation."""
        secs = timestr_to_secs(timeout)
        step = timestr_to_secs(poll)
        target = path or gateway_status.CATALOG_SERVICE_PATH
        started = time.monotonic()
        last: dict[str, Any] = {"status": "unknown", "detail": "aucune sonde"}

        def probe() -> bool:
            code, excerpt, error = self._probe(alias, target,
                                               {"format": "json", "top": "1"})
            last.clear()
            last.update(gateway_status.classify_gateway_probe(code, excerpt, error))
            return last["status"] == "ok"

        if not poll_until(probe, secs, max(0.1, step)):
            raise AssertionError(
                "API toujours indisponible après %s (sonde %s).\n%s"
                % (timeout, target, gateway_status.format_gateway_failure(last)))
        return {"available": True,
                "waited_seconds": round(time.monotonic() - started, 2),
                "status": "ok"}

    def lookup_business_term(self, term: str, domain: Optional[str] = None,
                             threshold: float = 0.8) -> dict[str, Any]:
        """Résout un **terme métier** (français ou anglais, synonymes
        compris) vers sa fiche SAP : canonique, champ ABAP, table de
        référence, domaine. Le même vocabulaire partagé que les canaux GUI
        (``sapfx_common.vocabulary``, concept issu de playwright-praman,
        Apache-2.0, NOTICE) : côté API il donne la table à compter par SE16
        ou le champ à filtrer en ``$filter``. Ambiguïté ou score sous
        ``threshold`` = échec listant les candidats, jamais de premier-match
        silencieux. Dict JSON-safe (rf-mcp)."""
        return lookup_as_dict(term, domain=domain, threshold=float(threshold))
