"""SapApiLibrary, le canal **API** du projet : OData (Gateway/CAP) et RFC.

Le troisième canal, à côté du GUI desktop (``SapEccLibrary``) et du web
(``SapFioriLibrary``). Raison d'être : un test SAP robuste **prépare et
vérifie ses données par l'API** et ne passe par l'écran que pour ce qu'il
teste vraiment : le setup/teardown GUI est lent et fragile, l'API est
rapide et déterministe. Le keyword métier type croise les canaux :
compter par SE16 ET par OData, puis exiger l'égalité (voir
``tests/robot/flagship_cross_paradigm.robot``).

Volontairement en **stdlib pure** (``urllib`` + ``http.cookiejar``) : aucune
dépendance nouvelle à épingler (la leçon pywin32 de la convention 6). Couvre :

* OData **v2** (Gateway embarqué ECC/S4 : enveloppe ``{"d": ...}``) et **v4**
  (CAP, S/4 moderne : ``{"value": [...]}``), mêmes keywords, détection de
  l'enveloppe ; CRUD complet (POST/PATCH/DELETE avec ``If-Match``), pagination
  server-driven suivie sur demande, function imports/actions, ``$batch``
  multipart (changeset atomique) ;
* la **fabrique de données de test** : entités créées enregistrées par
  session (``track=True``), nettoyage garanti en teardown
  (`Delete Created Entities`), création idempotente (`Ensure Odata Entity`) ;
* la **perception du canal** (il n'a pas d'écran) : ``$metadata`` parsé
  (`Get Odata Metadata`, entity sets/clés/libellés ``sap:label``), catalogue
  Gateway (`List Odata Services`), préflight actionnable
  (`Get Gateway Status` / `Gateway Should Be Active` /
  `Wait Until Api Available`) et télémétrie (`Get Api Telemetry`) ;
* le protocole **CSRF** SAP (``X-CSRF-Token: Fetch`` puis rejeu du token et
  des cookies sur les écritures, re-fetch et rejeu UNE fois sur 403 CSRF) ;
* l'authentification **Basic**, **OAuth2 client credentials** (S/4 Cloud,
  BTP : ``token_url``/``client_id``/``client_secret``) et le **certificat
  client mTLS** (``client_cert``/``client_key``) ;
* le **RFC** en option : ``Call Rfc`` s'appuie sur `pyrfc` (SAP NW RFC SDK)
  s'il est installé, sinon échoue avec la marche à suivre ; jamais de
  dépendance dure à un SDK propriétaire. Au-dessus : le pattern **BAPI**
  (`Call Bapi` vérifie les BAPIRET2 par TYPE, `Commit/Rollback Bapi
  Transaction`) et `Wait For Background Job` (TBTCO via RFC_READ_TABLE).

Erreurs auto-corrigibles (politique maison) : un échec HTTP nomme le statut,
l'URL effective et le début du corps de réponse.
"""
from __future__ import annotations

from typing import Any, Optional, Union

from robot.api import logger
from robot.api.types import Secret
from robot.utils import timestr_to_secs

from sapfx_common.secrets import reveal_secret
from sapfx_common.session_context import current_execution_namespace

from ._core import _ApiCore
from ._discovery import DiscoveryKeywords
from ._http import (  # noqa: F401  (re-exports : surface historique du module)
    _TRUTHY,
    _ApiSession,
    _RequestError,
    _SameOriginRedirectHandler,
    _as_bool,
)
from ._odata_read import OdataReadKeywords
from ._odata_write import OdataWriteKeywords
from ._rfc import RfcKeywords

class SapApiLibrary(OdataWriteKeywords, DiscoveryKeywords,
                    OdataReadKeywords, RfcKeywords, _ApiCore):
    """Bibliothèque Robot Framework pour parler aux APIs SAP (OData v2/v4, RFC).

    == Sessions ==
    `Open Api Session` mémorise URL de base, authentification (Basic, OAuth2
    client credentials via ``token_url``/``client_id``/``client_secret``,
    certificat client mTLS via ``client_cert``/``client_key``, ou clé d'API
    en en-tête via ``api_key``), client SAP et cookies ; tous les keywords OData s'y réfèrent par ``alias`` (plusieurs
    systèmes simultanés possibles). Exemple::

        Open Api Session    http://vhcala4hci:50000    user=DEVELOPER
        ...    password=${SAP_PASSWORD}    sap_client=001
        ${n}=    Get Odata Count    /sap/opu/odata/sap/SEPMRA_SHOP/Products

    == OData v2 et v4 ==
    `Get Odata Entities` renvoie la liste quelle que soit l'enveloppe
    (``d.results`` v2, ``value`` v4), et suit la pagination server-driven
    avec ``follow_next=True`` ; `Get Odata Count` lit ``$count``.
    Écritures : `Post Odata`, `Patch Odata`, `Delete Odata` (protocole CSRF
    SAP automatique, ``If-Match`` géré), `Call Odata Function` (function
    imports v2, actions v4) et `Post Odata Batch` (multipart, changeset
    atomique).

    == Fabrique de données de test ==
    ``track=True`` sur `Post Odata` (ou `Register Created Entity`) mémorise
    chaque entité créée ; `Delete Created Entities` les supprime en teardown
    (ordre inverse, best-effort, rapport JSON-safe) ; `Ensure Odata Entity`
    crée seulement si absent. Le patron maison : préparer et nettoyer par
    l'API, ne piloter l'écran que pour ce qu'on teste.

    == Perception et préflight (le canal sans écran) ==
    `Get Odata Metadata` parse le ``$metadata`` (entity sets, clés,
    propriétés, libellés ``sap:label``) ; `Find Odata Property By Label` est
    le localisateur « libellé humain » du canal API ; `List Odata Services`
    lit le catalogue Gateway ; `Get Gateway Status` /
    `Gateway Should Be Active` diagnostiquent une Gateway désactivée (le cas
    A4H ``/IWFND/CM_COS/003``) en nommant la remédiation ;
    `Wait Until Api Available` attend qu'un système (re)démarre ;
    `Get Api Telemetry` et `List Api Sessions` exposent l'état JSON-safe.

    == RFC et BAPI (optionnel) ==
    `Open Rfc Connection` / `Call Rfc` utilisent `pyrfc` si installé
    (SAP NW RFC SDK requis) ; sinon l'erreur donne la marche à suivre.
    `Call Bapi` vérifie les messages ``BAPIRET2`` par TYPE (``E``/``A``/``X``
    = échec listant les messages, convention n°3 : jamais le texte localisé) ;
    `Commit Bapi Transaction` / `Rollback Bapi Transaction` ferment la LUW.
    `Wait For Background Job` suit un job de fond (TBTCO via RFC_READ_TABLE).
    `Close All Api Sessions` ferme AUSSI les connexions RFC du namespace
    (une connexion RFC orpheline = une session utilisateur restée ouverte
    côté serveur) ; `Close All Rfc Connections` existe seul au besoin.
    """

    __version__ = "0.7.0"
    ROBOT_LIBRARY_SCOPE = "SUITE"
    ROBOT_LIBRARY_DOC_FORMAT = "ROBOT"

    def __init__(self, default_timeout: str = "30s") -> None:
        """``default_timeout`` : délai réseau par défaut des sessions ouvertes
        sans ``timeout`` explicite (chaîne de temps Robot : ``30s``, ``500 ms``)."""
        self.default_timeout = timestr_to_secs(default_timeout)
        self._sessions_by_namespace: dict[str, dict[str, _ApiSession]] = {}
        self._rfc_by_namespace: dict[str, dict[str, Any]] = {}

    def _api_sessions(self) -> dict[str, _ApiSession]:
        namespace = current_execution_namespace()
        return self._sessions_by_namespace.setdefault(namespace, {})

    def _rfc_connections(self) -> dict[str, Any]:
        namespace = current_execution_namespace()
        return self._rfc_by_namespace.setdefault(namespace, {})

    def open_api_session(self, base_url: str, user: Optional[str] = None,
                         password: Optional[Union[str, Secret]] = None,
                         sap_client: Optional[str] = None,
                         alias: str = "default", timeout: Optional[str] = None,
                         verify_tls: bool = True,
                         client_cert: Optional[str] = None,
                         client_key: Optional[str] = None,
                         token_url: Optional[str] = None,
                         client_id: Optional[str] = None,
                         client_secret: Optional[Union[str, Secret]] = None,
                         oauth_scope: Optional[str] = None,
                         api_key: Optional[Union[str, Secret]] = None,
                         api_key_header: str = "APIKey") -> str:
        """Ouvre une session API vers ``base_url`` (mémorise auth,
        ``sap-client`` ajouté à chaque requête, cookies). Retourne l'alias.

        Quatre modes d'authentification, cumulables avec ``sap_client`` :
        **Basic** (``user``/``password``), **OAuth2 client credentials**
        (``token_url`` + ``client_id`` + ``client_secret`` [+
        ``oauth_scope``] : token demandé au premier appel, rafraîchi à
        expiration et rejoué UNE fois sur 401 ; si Basic est aussi fourni, le
        Bearer l'emporte), **mTLS** (``client_cert`` [+ ``client_key``] :
        certificat client présenté au serveur), et **clé d'API**
        (``api_key``, envoyée dans l'en-tête ``api_key_header``, ``APIKey``
        par défaut : c'est l'authentification du bac à sable SAP Business
        Accelerator Hub, api.sap.com). La clé n'est jamais journalisée, et
        une clé vide est REFUSÉE : l'en-tête partirait sans authentifier et
        l'échec n'arriverait qu'au premier appel, en HTTP 401 muet sur sa
        cause. ``verify_tls=False`` accepte un certificat serveur
        auto-signé (systèmes de test)."""
        alias = self._validate_alias(alias)
        secs = timestr_to_secs(timeout) if timeout else self.default_timeout
        tls_verified = _as_bool(verify_tls)
        if not tls_verified:
            logger.warn("TLS certificate verification is disabled for API session '%s'."
                        % alias)
        if user is not None and base_url.lower().startswith("http://"):
            logger.warn(
                "API session '%s' sends Basic credentials over plain http:// "
                "(cleartext). Acceptable on an isolated test system; prefer "
                "https:// anywhere else." % alias)
        if token_url and not client_id:
            raise ValueError(
                "OAuth2 client credentials : token_url fourni sans client_id "
                "(client_secret recommandé aussi).")
        if token_url and user is not None:
            logger.warn(
                "API session '%s' : Basic ET OAuth2 fournis, le token Bearer "
                "l'emporte sur l'en-tête Basic." % alias)
        if api_key is not None:
            if not (reveal_secret(api_key) or "").strip():
                raise ValueError(
                    "Open Api Session : api_key fourni mais vide. Une clé "
                    "vide enverrait l'en-tête sans authentifier, et l'échec "
                    "n'arriverait qu'au premier appel, sous la forme d'un "
                    "HTTP 401 muet sur sa cause.")
            if not api_key_header.strip():
                raise ValueError(
                    "Open Api Session : api_key_header vide (l'en-tête "
                    "attendu par le bac à sable api.sap.com est 'APIKey').")
            if base_url.lower().startswith("http://"):
                logger.warn(
                    "API session '%s' sends its API key over plain http:// "
                    "(cleartext). Acceptable on an isolated test system; "
                    "prefer https:// anywhere else." % alias)
        self._api_sessions()[alias] = _ApiSession(
            base_url, user, password, sap_client, secs, tls_verified,
            client_cert=client_cert, client_key=client_key,
            token_url=token_url, client_id=client_id,
            client_secret=client_secret, oauth_scope=oauth_scope,
            api_key=api_key, api_key_header=api_key_header)
        return alias

    def close_api_session(self, alias: str = "default") -> None:
        """Oublie la session ``alias`` (cookies et token CSRF compris).
        Avertit si des entités créées suivies n'ont pas été nettoyées
        (`Delete Created Entities`) : jamais de fuite silencieuse."""
        session = self._api_sessions().pop(alias, None)
        if session is not None and session.created_entities:
            logger.warn(
                "API session '%s' fermée avec %d entité(s) créée(s) non "
                "nettoyée(s) (Delete Created Entities avant fermeture) : %s"
                % (alias, len(session.created_entities),
                   ", ".join(session.created_entities[:5])))

    def close_all_api_sessions(self) -> None:
        """Oublie toutes les sessions API **et ferme les connexions RFC** du
        namespace courant (teardown de suite) : une connexion RFC orpheline
        est une session utilisateur restée ouverte côté serveur SAP, la même
        leçon que le ``Close All Sap Sessions`` du canal GUI."""
        namespace = current_execution_namespace()
        sessions = self._sessions_by_namespace.pop(namespace, {})
        leftovers = {alias: len(session.created_entities)
                     for alias, session in sessions.items()
                     if session.created_entities}
        if leftovers:
            logger.warn(
                "Sessions API fermées avec des entités créées non nettoyées "
                "(Delete Created Entities avant le teardown) : %s"
                % ", ".join("%s (%d)" % item for item in sorted(leftovers.items())))
        self.close_all_rfc_connections()

    def close_all_rfc_connections(self) -> None:
        """Ferme toutes les connexions RFC du namespace courant (best-effort :
        une connexion déjà morte n'empêche pas la fermeture des autres)."""
        namespace = current_execution_namespace()
        connections = self._rfc_by_namespace.pop(namespace, {})
        for alias, connection in connections.items():
            try:
                connection.close()
            except Exception as exc:
                logger.warn("RFC connection '%s' did not close cleanly: %s"
                            % (alias, exc))

    def list_api_sessions(self) -> dict[str, Any]:
        """Retourne l'état **JSON-safe** du canal API dans le namespace
        courant : ``{"api_sessions": [{alias, base_url, sap_client,
        authenticated, oauth, csrf_token_cached, requests, errors,
        created_entities}], "rfc_connections": [alias…]}``.

        JAMAIS de credentials : ``authenticated`` dit seulement si la session
        porte une authentification Basic OU une clé d'API, ``oauth`` si elle
        porte un client OAuth2, ``csrf_token_cached`` si un token CSRF a déjà
        été obtenu ;
        ``requests``/``errors`` viennent de la télémétrie (détail :
        `Get Api Telemetry`), ``created_entities`` compte les entités suivies
        par la fabrique de données. C'est la perception du canal API (il n'a
        pas d'écran), consommée par le state provider rf-mcp (`SapApiPlugin`)
        et utile en débogage de suite multi-alias."""
        return {
            "api_sessions": [
                {"alias": alias,
                 "base_url": session.base_url,
                 "sap_client": session.sap_client,
                 "authenticated": ("Authorization" in session.headers
                                   or session.api_key_header is not None),
                 "oauth": session.token_url is not None,
                 "csrf_token_cached": session.csrf_token is not None,
                 "requests": session.telemetry["requests"],
                 "errors": session.telemetry["errors"],
                 "created_entities": len(session.created_entities)}
                for alias, session in sorted(self._api_sessions().items())],
            "rfc_connections": sorted(self._rfc_connections()),
        }

    def get_api_telemetry(self, alias: str = "default") -> dict[str, Any]:
        """Télémétrie JSON-safe de la session ``alias`` : nombre de requêtes,
        d'erreurs, temps réseau cumulé (secondes), dernier statut, dernière
        URL, dernière erreur. Jamais de credentials ni de corps de réponse :
        consommable tel quel à travers rf-mcp."""
        session = self._session(alias)
        data = dict(session.telemetry)
        data["seconds"] = round(float(data["seconds"]), 3)
        data["alias"] = alias
        data["base_url"] = session.base_url
        return data
