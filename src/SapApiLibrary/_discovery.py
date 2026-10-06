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

from sapfx_common import abap_components, cds_source, gateway_status, odata_metadata
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
        "keys", "properties": {nom: {"type", "nullable", "label",
        "max_length", "precision", "scale"}}}}, "function_imports",
        "actions"}``. C'est la *perception* du canal
        API : ce que `Get Screen Signature` est à un écran, ce keyword l'est
        à un service (exploration agent, plans de test, discovery).

        Mis en cache par session et par racine de service (le $metadata ne
        bouge pas en cours de suite) ; ``refresh=True`` force le
        rechargement.

        Exemple :
        | ${meta}=    `Get Odata Metadata`    /sap/opu/odata/sap/SEPMRA_SHOP    alias=a4h
        | Dictionary Should Contain Key    ${meta}[entity_sets]    Products
        | Log    ${meta}[entity_sets][Products][keys]
        """
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
        actionnable listant un extrait des libellés connus.

        Exemple :
        | ${hits}=    `Find Odata Property By Label`    /sap/opu/odata/sap/SEPMRA_SHOP    Price
        | ...    alias=a4h    entity_set=Products
        | Should Be Equal    ${hits}[0][property]    Price
        """
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
        (``ServiceCollection``) : la *découverte* du canal API. Retourne
        une liste JSON-safe ``{"id", "title", "technical_name",
        "service_url", "version"}`` par service. ``catalog_path`` remplace le
        chemin standard au besoin ; les options OData passent en arguments
        nommés (``top=10``).

        Exemple :
        | ${services}=    `List Odata Services`    alias=a4h
        | Should Not Be Empty    ${services}
        | Log    ${services}[0][technical_name]
        """
        path = catalog_path or gateway_status.CATALOG_SERVICE_PATH
        query.setdefault("format", "json")
        entries = self.get_odata_entities(path, alias=alias, **query)
        return odata_metadata.simplify_catalog_entries(entries)

    def get_abap_software_components(self, alias: str = "default") -> dict[str, Any]:
        """Composants logiciels installés du système ABAP, lus par *HTTP seul*
        (API des outils ABAP, ``/sap/bc/adt/system/components``) : ``{"release",
        "components": {nom: {"release", "sp_package", "sp_level",
        "description"}}}``, ``release`` étant celle de ``SAP_BASIS``.

        La preuve d'IDENTITÉ d'une cible quand ni SAP GUI ni RFC ne sont
        disponibles : les deux conteneurs ABAP du banc annoncent le même
        identifiant système et le même nom d'hôte, et ``/sap/public/info`` est
        inactif sur les deux, si bien que le seul discriminant HTTP connu était
        jusqu'ici le volume du catalogue Gateway. Relevé le 2026-09-24 : cette
        ressource rend ``SAP_BASIS 758`` sur ABAP Platform 2023.

        Exige le service ICF des outils ABAP et l'autorisation d'y lire ; un
        refus HTTP échoue avec son statut, un corps qui n'est pas le flux
        attendu (page de connexion) échoue en le disant, jamais un inventaire
        vide. Lecture seule.

        Exemple :
        | ${components}=    `Get Abap Software Components`    alias=a4h
        | Should Be Equal    ${components}[release]    754
        """
        _, _, body = self._request(alias, "GET", abap_components.COMPONENTS_PATH,
                                   headers={"Accept": abap_components.ATOM_FEED})
        components = abap_components.parse_adt_components(body)
        return {"release": abap_components.abap_release(components),
                "components": components}

    def get_cds_header_annotations(self, name: str,
                                   alias: str = "default") -> dict[str, Any]:
        """Les annotations d'EN-TÊTE d'une vue CDS ABAP avec leur *VALEUR*,
        lues dans sa source DDL par l'API des outils ABAP
        (``/sap/bc/adt/ddic/ddl/sources/<nom>/source/main``) : un dict aux clés
        en majuscules et pointées, comme dans le dictionnaire
        (``{"ANALYTICS.DATACATEGORY": "#DIMENSION",
        "ANALYTICS.DATAEXTRACTION.ENABLED": "true",
        "ABAPCATALOG.SQLVIEWNAME": "SEPM_IPO", ...}``).

        Le complément de ce que le canal RFC ne sait pas lire : le dictionnaire
        des annotations (``DDHEADANNO``) nomme chaque annotation, mais sa
        colonne de valeur (1300 caractères) dépasse ``RFC_READ_TABLE``, si bien
        qu'une garde par RFC constate qu'une annotation EXISTE et jamais ce
        qu'elle VAUT : ``dataExtraction.enabled: false`` y ressemble à
        ``true`` (revue indépendante du 2026-09-29).

        Les commentaires (``//``, ``--``, ``/* */``) sont retirés : une
        annotation commentée n'existe pas. Exige le service ICF des outils
        ABAP et l'autorisation d'y lire ; un refus HTTP échoue avec son
        statut, une réponse qui n'est pas une définition DDL (page de
        connexion) échoue en le disant, jamais un dictionnaire vide. Lecture
        seule. Logique pure : ``sapfx_common.cds_source``.

        Exemple :
        | ${annotations}=    `Get Cds Header Annotations`    SEPM_I_PurchaseOrder    alias=a4h
        | Should Be Equal    ${annotations}[ABAPCATALOG.SQLVIEWNAME]    SEPM_IPO
        """
        _, _, body = self._request(alias, "GET", cds_source.ddl_source_path(name),
                                   headers={"Accept": "text/plain"})
        texte = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
        try:
            return cds_source.header_annotations(texte)
        except ValueError as err:
            raise AssertionError("Vue CDS %s : %s" % (name, err)) from err

    def get_http_response(self, path: str, alias: str = "default",
                          max_chars: int = 20000,
                          headers: Optional[dict] = None,
                          **query: str) -> dict[str, Any]:
        """Lecture HTTP *brute et tolérante* d'un chemin de la session :
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
        ses assertions ; pour un verdict classé, `Get Gateway Status`.

        Exemple :
        | ${response}=    `Get Http Response`    /sap/opu/odata/sap/SEPMRA_SHOP/Products('AR-FB-1000')    alias=a4h    max_chars=200
        | Should Be Equal As Integers    ${response}[status]    200
        """
        status, resp_headers, body, truncated, error, url = \
            self._probe_response(alias, path, query or None,
                                 max_chars=int(max_chars),
                                 extra_headers=headers)
        return {"status": status,
                "headers": {str(k): str(v) for k, v in resp_headers.items()},
                "body": body, "truncated": bool(truncated),
                "error": error, "url": url}

    def classify_http_response(self, response: dict) -> str:
        """Range une réponse de `Get Http Response` dans une *famille de
        reconnaissance*, par des critères purement structurels : statut,
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
        ressource ou l'hôte entier.

        Exemple :
        | ${response}=    `Get Http Response`    /sap/opu/odata/sap/ZZ_NO_SUCH_SERVICE/$metadata    alias=a4h
        | ${family}=    `Classify Http Response`    ${response}
        | Should Be Equal    ${family}    forbidden
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
        d'un tel site ne renvoie de défi d'authentification).

        Sur une session ouverte par *clé d'API* (une couche de gestion
        d'API devant le système), un 401 se dédouble : ``auth_failed`` quand
        la couche refuse la clé, et ``backend_auth_failed`` quand elle
        l'ACCEPTE et que le système ABAP derrière refuse (relevé live le
        2026-09-06 sur le bac à sable SAP Business Accelerator Hub). Les
        deux méritent des remèdes opposés, et le second interdit
        explicitement de régénérer une clé saine. Ne lève jamais : le
        miroir API de `Get Scripting Status`.

        Exemple :
        | ${gateway}=    `Get Gateway Status`    alias=a4h
        | Should Be Equal    ${gateway}[status]    ok
        """
        session = self._session(alias)
        path = catalog_path or gateway_status.CATALOG_SERVICE_PATH
        code, headers, excerpt, _, error, _ = self._probe_response(
            alias, path, {"format": "json", "top": "1"})
        result = gateway_status.classify_gateway_probe(
            code, excerpt, error, headers=headers,
            edge_credential=session.api_key_header is not None)
        result["catalog_path"] = path
        result["base_url"] = session.base_url
        return result

    def gateway_should_be_active(self, alias: str = "default",
                                 catalog_path: Optional[str] = None) -> None:
        """Échoue (message auto-corrigible nommant la remédiation) si la
        Gateway OData n'est pas opérationnelle : à appeler en Suite Setup
        avant tout test OData, comme `Scripting Should Be Fully Enabled`
        côté GUI.

        Exemple :
        | `Gateway Should Be Active`    alias=a4h
        """
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
        diagnostic classé et sa remédiation.

        Exemple :
        | `Wait Until Api Available`    alias=a4h    timeout=2m
        """
        secs = timestr_to_secs(timeout)
        step = timestr_to_secs(poll)
        target = path or gateway_status.CATALOG_SERVICE_PATH
        started = time.monotonic()
        last: dict[str, Any] = {"status": "unknown", "detail": "aucune sonde"}

        session = self._session(alias)

        def probe() -> bool:
            code, headers, excerpt, _, error, _ = self._probe_response(
                alias, target, {"format": "json", "top": "1"})
            last.clear()
            last.update(gateway_status.classify_gateway_probe(
                code, excerpt, error, headers=headers,
                edge_credential=session.api_key_header is not None))
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
        """Résout un *terme métier* (français ou anglais, synonymes
        compris) vers sa fiche SAP : canonique, champ ABAP, table de
        référence, domaine. Le même vocabulaire partagé que les canaux GUI
        (``sapfx_common.vocabulary``, concept issu de playwright-praman,
        Apache-2.0, NOTICE) : côté API il donne la table à compter par SE16
        ou le champ à filtrer en ``$filter``. Ambiguïté ou score sous
        ``threshold`` = échec listant les candidats, jamais de premier-match
        silencieux. Dict JSON-safe (rf-mcp).

        Exemple :
        | ${entry}=    `Lookup Business Term`    customer
        | Should Be Equal    ${entry}[abap_field]    KUNNR
        """
        return lookup_as_dict(term, domain=domain, threshold=float(threshold))
