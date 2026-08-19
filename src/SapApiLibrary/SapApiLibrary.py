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

import base64
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from typing import Any, Optional, Union

from robot.api import logger
from robot.api.types import Secret
from robot.utils import timestr_to_secs

from sapfx_common import bapi_return, gateway_status, odata_metadata, rfc_tables
from sapfx_common.odata_batch import build_batch, parse_batch_response
from sapfx_common.polling import poll_until
from sapfx_common.secrets import reveal_secret
from sapfx_common.session_context import current_execution_namespace
from sapfx_common.vocabulary import lookup_as_dict

_TRUTHY = ("1", "true", "yes", "on")

# Extrait de corps de réponse joint aux erreurs HTTP : assez pour lire le
# message Gateway (<message>...</message>), pas de quoi noyer le log.
_BODY_EXCERPT = 400

# Suffixe de clé OData (``Products('X')`` -> ``Products``) : ce qu'on retire
# pour déduire l'entity set d'un chemin d'entité.
_KEY_SUFFIX = re.compile(r"\([^()]*\)\s*$")

# Encodage des paramètres de query. Le défaut d'``urlencode`` est celui des
# formulaires HTML (``application/x-www-form-urlencoded``), qui rend l'espace
# par ``+`` : une Gateway SAP v2 le tolère, un service OData v4 (CAP) le
# REFUSE en HTTP 400 (« Expected "(", "/", or a whitespace but "+" found »),
# et un ``$filter`` contient toujours des espaces (``TravelID eq 1``).
# ``quote`` rend l'espace par ``%20`` et se comporte comme ``quote_plus`` sur
# TOUT le reste : le correctif est donc strictement limité au caractère
# fautif, et l'encodage déjà servi aux Gateway en production ne bouge pas.
_QUERY_QUOTE = urllib.parse.quote


def _as_bool(value: Any) -> bool:
    # Booléens « à la Robot Framework » (_TRUTHY) : sémantique distincte du
    # _as_bool COM strict d'object_tree ("true" seul) ; ne pas fusionner.
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUTHY


def _url_origin(url: str) -> tuple[str, str, Optional[int]]:
    parsed = urllib.parse.urlsplit(url)
    default_port = 443 if parsed.scheme.lower() == "https" else 80
    return (parsed.scheme.lower(), (parsed.hostname or "").lower(),
            parsed.port or default_port)


def _has_query_param(url: str, name: str) -> bool:
    """Vrai si ``url`` porte DÉJÀ ce paramètre de requête.

    Sert au ``sap-client`` : les liens de pagination server-driven
    (``__next`` v2, ``@odata.nextLink`` v4) sont fabriqués par le serveur et
    reconduisent en général les options de la requête d'origine, ``sap-client``
    compris. Le réajouter produirait ``sap-client=001&sap-client=001``, que
    tous les serveurs ne tolèrent pas de la même façon."""
    query = urllib.parse.urlsplit(url).query
    if not query:
        return False
    return any(key == name for key, _ in
               urllib.parse.parse_qsl(query, keep_blank_values=True))


def _header(headers: Optional[dict], name: str) -> Optional[str]:
    """Lecture insensible à la casse d'un en-tête HTTP."""
    wanted = name.lower()
    for key, value in (headers or {}).items():
        if str(key).lower() == wanted:
            return value
    return None


class _RequestError(AssertionError):
    """Échec HTTP auto-corrigible porteur du statut et des en-têtes de la
    réponse : le protocole CSRF juge sur l'en-tête ``x-csrf-token`` (la voie
    fiable), pas sur le texte du message."""

    def __init__(self, message: str, status: int, headers: dict):
        super().__init__(message)
        self.status = status
        self.headers = dict(headers)


def _csrf_rejected(err: AssertionError) -> bool:
    """Vrai pour le 403 « token CSRF requis/expiré » à rejouer UNE fois.

    Trois cas, dans cet ordre :

    - en-tête ``x-csrf-token`` commençant par ``Required`` : le signal POSITIF
      du protocole SAP, rejeu (la valeur peut être décorée par un relais,
      ``Required; expired``, d'où la lecture du premier mot) ;
    - en-tête portant un VRAI token : le serveur en a fourni un, la requête
      n'a donc pas été refusée faute de token : interdiction réelle, aucun
      rejeu (le rejouer serait un faux espoir) ;
    - en-tête absent OU vidé par un relais : plus aucun signal fiable, on
      retombe sur le texte de la réponse. Refuser ici casserait
      DÉFINITIVEMENT une écriture qui se rétablissait seule au-delà du
      timeout Gateway (~30 min), alors qu'un rejeu inutile ne coûte qu'un
      aller-retour avant que l'erreur d'origine ne revienne à l'identique.

    Seuls les échecs HTTP passent par ici (``_request`` lève toujours un
    ``_RequestError``) : une AssertionError d'une autre origine (URL
    injoignable, auth OAuth) n'est jamais un rejet CSRF."""
    if not isinstance(err, _RequestError) or err.status != 403:
        return False
    marker = _header(err.headers, "x-csrf-token")
    raw = "" if marker is None else str(marker).strip()
    if raw:
        first = raw.replace(";", " ").replace(",", " ").split()[0].lower()
        return first == "required"
    return "csrf" in str(err).lower()


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse qu'une redirection transporte l'authentification vers un autre hôte."""

    def __init__(self, base_url: str) -> None:
        self._origin = _url_origin(base_url)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if _url_origin(newurl) != self._origin:
            raise urllib.error.URLError(
                "Cross-origin API redirect blocked: %s" % newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _ApiSession:
    """État d'une session API : URL de base, auth, cookies, client SAP,
    entités créées (fabrique de données), cache $metadata, télémétrie."""

    def __init__(self, base_url: str, user: Optional[str],
                 password: Optional[Union[str, Secret]], sap_client: Optional[str],
                 timeout: float, verify_tls: bool,
                 client_cert: Optional[str] = None,
                 client_key: Optional[str] = None,
                 token_url: Optional[str] = None,
                 client_id: Optional[str] = None,
                 client_secret: Optional[Union[str, Secret]] = None,
                 oauth_scope: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.sap_client = sap_client
        self.timeout = timeout
        self.headers: dict[str, str] = {"Accept": "application/json"}
        if user is not None:
            token = base64.b64encode(
                ("%s:%s" % (user, reveal_secret(password) or "")).encode(
                    "utf-8")).decode("ascii")
            self.headers["Authorization"] = "Basic %s" % token
        self.cookies = CookieJar()
        self.tls_context: Optional[ssl.SSLContext] = None
        if not verify_tls or client_cert:
            context = ssl.create_default_context()
            if not verify_tls:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            if client_cert:
                context.load_cert_chain(client_cert, client_key)
            self.tls_context = context
        handlers: list[urllib.request.BaseHandler] = [
            urllib.request.HTTPCookieProcessor(self.cookies),
            _SameOriginRedirectHandler(self.base_url)]
        if self.tls_context is not None:
            handlers.append(urllib.request.HTTPSHandler(context=self.tls_context))
        self.opener = urllib.request.build_opener(*handlers)
        self.csrf_token: Optional[str] = None
        # OAuth2 client credentials (S/4 Cloud, BTP).
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.oauth_scope = oauth_scope
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0.0
        # Fabrique de données : URIs des entités créées via track=True (LIFO).
        self.created_entities: list[str] = []
        # Perception : cache $metadata par racine de service.
        self.metadata_cache: dict[str, dict[str, Any]] = {}
        # Télémétrie du canal (jamais de credentials, jamais de corps).
        self.telemetry: dict[str, Any] = {
            "requests": 0, "errors": 0, "seconds": 0.0,
            "last_status": None, "last_url": None, "last_error": None}


class SapApiLibrary:
    """Bibliothèque Robot Framework pour parler aux APIs SAP (OData v2/v4, RFC).

    == Sessions ==
    `Open Api Session` mémorise URL de base, authentification (Basic, OAuth2
    client credentials via ``token_url``/``client_id``/``client_secret``, ou
    certificat client mTLS via ``client_cert``/``client_key``), client SAP et
    cookies ; tous les keywords OData s'y réfèrent par ``alias`` (plusieurs
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

    __version__ = "0.6.7"
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

    # -- sessions --------------------------------------------------------------

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
                         oauth_scope: Optional[str] = None) -> str:
        """Ouvre une session API vers ``base_url`` (mémorise auth,
        ``sap-client`` ajouté à chaque requête, cookies). Retourne l'alias.

        Trois modes d'authentification, cumulables avec ``sap_client`` :
        **Basic** (``user``/``password``), **OAuth2 client credentials**
        (``token_url`` + ``client_id`` + ``client_secret`` [+
        ``oauth_scope``] : token demandé au premier appel, rafraîchi à
        expiration et rejoué UNE fois sur 401 ; si Basic est aussi fourni, le
        Bearer l'emporte), **mTLS** (``client_cert`` [+ ``client_key``] :
        certificat client présenté au serveur). ``verify_tls=False`` accepte
        un certificat serveur auto-signé (systèmes de test)."""
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
        self._api_sessions()[alias] = _ApiSession(
            base_url, user, password, sap_client, secs, tls_verified,
            client_cert=client_cert, client_key=client_key,
            token_url=token_url, client_id=client_id,
            client_secret=client_secret, oauth_scope=oauth_scope)
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
        porte une authentification Basic, ``oauth`` si elle porte un client
        OAuth2, ``csrf_token_cached`` si un token CSRF a déjà été obtenu ;
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
                 "authenticated": "Authorization" in session.headers,
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

    # -- OData : lectures -------------------------------------------------------

    def get_odata(self, path: str, alias: str = "default",
                  **query: str) -> Any:
        """GET OData → JSON décodé tel quel (enveloppe v2/v4 comprise). Les
        arguments nommés deviennent des paramètres de requête (``top=5`` →
        ``$top=5`` : le préfixe ``$`` des options système OData est ajouté aux
        noms connus : top/skip/filter/select/orderby/format/expand/count)."""
        status, _, body = self._request(alias, "GET", path, query)
        return self._decode_json(body, status, path)

    def get_odata_entities(self, path: str, alias: str = "default",
                           follow_next: Any = False, max_pages: Any = 100,
                           **query: str) -> list:
        """GET OData → la **liste d'entités**, quelle que soit la version :
        ``d.results`` (v2), ``value`` (v4), ou l'entité seule dans une liste.

        ``follow_next=True`` suit la pagination server-driven (``__next`` v2,
        ``@odata.nextLink`` v4) jusqu'à épuisement : sans lui, un serveur qui
        pagine (S/4 plafonne souvent à 100) renverrait une page PARTIELLE,
        le faux positif silencieux type. ``max_pages`` borne le suivi ; toute
        troncature est annoncée en WARNING (jamais silencieuse)."""
        payload = self.get_odata(path, alias=alias, **query)
        entities = self._extract_entities(payload, path)
        if not _as_bool(follow_next):
            return entities
        session = self._session(alias)
        base_for_join = self._build_url(session, path, None)
        pages = 1
        next_link = self._next_link(payload)
        while next_link:
            if pages >= int(max_pages):
                logger.warn(
                    "Get Odata Entities : pagination tronquée à %d page(s) "
                    "(%d entités lues), un lien de page suivante reste non "
                    "suivi : augmenter max_pages pour tout lire."
                    % (pages, len(entities)))
                break
            target = urllib.parse.urljoin(base_for_join, next_link)
            status, _, body = self._request(alias, "GET", target, None)
            payload = self._decode_json(body, status, target)
            entities.extend(self._extract_entities(payload, target))
            next_link = self._next_link(payload)
            pages += 1
        return entities

    @staticmethod
    def _extract_entities(payload: Any, path: str) -> list:
        if isinstance(payload, dict):
            envelope = payload.get("d", payload)
            if isinstance(envelope, dict) and isinstance(
                    envelope.get("results"), list):
                return list(envelope["results"])
            if isinstance(payload.get("value"), list):
                return list(payload["value"])
            return [envelope]
        if isinstance(payload, list):
            return list(payload)
        raise AssertionError(
            "Réponse OData inattendue pour '%s' : ni enveloppe v2 (d.results) "
            "ni v4 (value), reçu %r" % (path, type(payload).__name__))

    @staticmethod
    def _next_link(payload: Any) -> Optional[str]:
        """Lien de page suivante server-driven : ``d.__next`` (v2) ou
        ``@odata.nextLink`` (v4), ``None`` sinon."""
        if not isinstance(payload, dict):
            return None
        envelope = payload.get("d")
        if isinstance(envelope, dict) and envelope.get("__next"):
            return str(envelope["__next"])
        link = payload.get("@odata.nextLink")
        return str(link) if link else None

    def get_odata_count(self, entity_path: str, alias: str = "default",
                        **query: str) -> int:
        """``GET <entity_path>/$count`` → entier (v2 et v4). Le chemin est
        celui de l'entity set (``.../Products``) ; les filtres passent en
        arguments nommés (``filter=Price gt 100``)."""
        path = "%s/$count" % entity_path.rstrip("/")
        status, _, body = self._request(alias, "GET", path, query,
                                        headers={"Accept": "text/plain"})
        text = body.decode("utf-8-sig", errors="replace").strip()
        # Le texte ENTIER doit être l'entier : extraire les chiffres d'une
        # réponse quelconque (page de login HTML, message d'erreur) fabriquerait
        # un comptage plausible et donc un faux positif de test silencieux.
        if not text.isdigit():
            raise AssertionError(
                "$count sur '%s' n'a pas retourné un entier (statut %d) : %r "
                "(réponse non numérique : page de login ou d'erreur ? "
                "vérifier base_url, l'authentification et le chemin)."
                % (entity_path, status, text[:_BODY_EXCERPT]))
        return int(text)

    # -- OData : écritures ------------------------------------------------------

    def post_odata(self, path: str, payload: Any, alias: str = "default",
                   track: bool = False, **query: str) -> Any:
        """POST OData avec le protocole **CSRF** SAP : un GET préalable avec
        ``X-CSRF-Token: Fetch`` obtient le token (mémorisé avec les cookies de
        session), rejoué sur l'écriture ; token expiré (403 CSRF) = re-fetch
        et rejeu UNE fois. ``payload`` : dict (sérialisé JSON) ou chaîne déjà
        sérialisée. Retourne le JSON de la réponse (``{}`` si 204).

        ``track=True`` enregistre l'entité créée dans la **fabrique de
        données** de la session (URI lue dans ``__metadata.uri`` v2,
        ``@odata.id`` v4 ou l'en-tête ``Location``) : `Delete Created
        Entities` la supprimera en teardown. Réponse sans URI identifiable =
        WARNING invitant à `Register Created Entity` (jamais silencieux)."""
        body = payload if isinstance(payload, (str, bytes)) else json.dumps(payload)
        status, headers, raw = self._write_request(alias, "POST", path, query, body)
        result: Any = {}
        if status != 204 and raw.strip():
            result = self._decode_json(raw, status, path)
        if _as_bool(track):
            session = self._session(alias)
            uri = self._entity_uri(session, result, headers,
                                   self._build_url(session, path, None))
            if uri:
                session.created_entities.append(uri)
                logger.info("Entité créée suivie pour nettoyage : %s" % uri)
            else:
                logger.warn(
                    "Post Odata track=True : impossible d'identifier l'URI de "
                    "l'entité créée (ni __metadata.uri, ni @odata.id, ni "
                    "Location) : appeler Register Created Entity avec son "
                    "chemin pour garantir le nettoyage.")
        return result

    def patch_odata(self, path: str, payload: Any, alias: str = "default",
                    if_match: Optional[str] = "*", **query: str) -> Any:
        """PATCH OData (mise à jour partielle d'une entité, v2 et v4) avec le
        protocole CSRF et l'en-tête ``If-Match`` (défaut ``*`` : beaucoup
        d'entity sets SAP l'exigent ; passer l'ETag exact pour du verrouillage
        optimiste réel, ou ``${NONE}`` pour ne pas l'envoyer). ``path`` vise
        l'entité avec sa clé (``.../Products('X')``). Retourne le JSON de la
        réponse (``{}`` si 204, le cas nominal)."""
        body = payload if isinstance(payload, (str, bytes)) else json.dumps(payload)
        status, _, raw = self._write_request(
            alias, "PATCH", path, query, body,
            extra_headers=self._if_match_header(if_match))
        if status == 204 or not raw.strip():
            return {}
        return self._decode_json(raw, status, path)

    def delete_odata(self, path: str, alias: str = "default",
                     if_match: Optional[str] = "*", **query: str) -> Any:
        """DELETE OData (v2 et v4) avec le protocole CSRF et ``If-Match``
        (mêmes règles que `Patch Odata`). ``path`` vise l'entité avec sa clé.
        Retourne ``{}`` (204, le cas nominal) ou le JSON de la réponse.

        Avec `Post Odata` ``track=True`` et `Delete Created Entities`, ferme
        le cycle de données **réversible** par l'API : créer, tester, tout
        remettre en l'état sans passer par l'écran."""
        status, _, raw = self._write_request(
            alias, "DELETE", path, query, None,
            extra_headers=self._if_match_header(if_match))
        if status == 204 or not raw.strip():
            return {}
        return self._decode_json(raw, status, path)

    def call_odata_function(self, path: str, method: str = "GET",
                            payload: Any = None, alias: str = "default",
                            **query: str) -> Any:
        """Appelle un **function import** (v2) ou une **action/fonction**
        (v4) : beaucoup de logique métier SAP n'est accessible que par là.
        ``method=GET`` pour les fonctions de lecture (paramètres en arguments
        nommés, littéraux OData à la charge de l'appelant : ``code='FR'``) ;
        ``method=POST`` pour les actions (``payload`` dict ou chaîne, CSRF
        appliqué). Retourne le JSON décodé (``{}`` si 204)."""
        method = str(method).upper().strip()
        if method == "GET":
            return self.get_odata(path, alias=alias, **query)
        body = None
        if payload is not None:
            body = payload if isinstance(payload, (str, bytes)) else json.dumps(payload)
        status, _, raw = self._write_request(alias, method, path, query, body)
        if status == 204 or not raw.strip():
            return {}
        return self._decode_json(raw, status, path)

    def post_odata_batch(self, service_path: str, operations: Any,
                         alias: str = "default", atomic: bool = True,
                         fail_on_error: bool = True) -> list[dict[str, Any]]:
        """Envoie un ``$batch`` OData (multipart, v2 ET v4) : N opérations en
        UN aller-retour. ``operations`` : liste de dicts ``{"method",
        "path", "payload"?, "headers"?}`` (chemins relatifs à la racine du
        service) ou la même liste en chaîne JSON (pratique via rf-mcp).

        ``atomic=True`` (défaut) : toutes les écritures dans UN changeset,
        l'unité atomique SAP (tout passe ou tout est annulé) : le bon réglage
        pour préparer un jeu de données. ``atomic=False`` : une écriture par
        changeset (échecs indépendants). Retourne la liste ordonnée des
        réponses ``{"status", "reason", "headers", "body", "json"}`` ;
        ``fail_on_error=True`` échoue si une réponse est >= 400 (les échecs
        partiels silencieux sont l'ennemi d'un jeu de données)."""
        if isinstance(operations, str):
            try:
                operations = json.loads(operations)
            except json.JSONDecodeError as err:
                raise ValueError(
                    "Post Odata Batch : 'operations' n'est ni une liste ni du "
                    "JSON valide (%s)." % err)
        body, content_type = build_batch(operations, atomic=_as_bool(atomic))
        root = service_path.rstrip("/")
        status, headers, raw = self._write_request(
            alias, "POST", root + "/$batch", None, body,
            extra_headers={"Content-Type": content_type},
            csrf_fetch_path=root + "/")
        responses = parse_batch_response(raw, _header(headers, "Content-Type") or "")
        failures = [r for r in responses if r["status"] >= 400]
        if failures and _as_bool(fail_on_error):
            detail = "; ".join(
                "HTTP %d %s : %s" % (r["status"], r["reason"], r["body"][:120])
                for r in failures[:3])
            raise AssertionError(
                "$batch sur '%s' : %d opération(s) sur %d en échec (batch "
                "HTTP %d). Premières erreurs : %s"
                % (service_path, len(failures), len(responses), status, detail))
        return responses

    @staticmethod
    def _if_match_header(if_match: Optional[str]) -> Optional[dict[str, str]]:
        if if_match in (None, "", "None"):
            return None
        return {"If-Match": str(if_match)}

    # -- fabrique de données de test --------------------------------------------

    def ensure_odata_entity(self, entity_path: str, payload: Any,
                            alias: str = "default",
                            create_path: Optional[str] = None,
                            track: bool = False) -> dict[str, Any]:
        """Création **idempotente** : GET sur ``entity_path`` (l'entité avec
        sa clé, ``.../Products('X')``) ; si elle existe, ne touche à rien ;
        si 404, POST ``payload`` sur ``create_path`` (défaut : ``entity_path``
        privé de son suffixe de clé ``(...)``). Retourne ``{"created": bool,
        "entity": <JSON>}``. ``track=True`` suit l'entité créée pour
        `Delete Created Entities` (une entité qui existait déjà n'est JAMAIS
        suivie : on ne supprime pas ce qu'on n'a pas créé)."""
        status, _, body = self._request(alias, "GET", entity_path, None,
                                        allowed_errors=(404,))
        if status != 404:
            return {"created": False,
                    "entity": self._decode_json(body, status, entity_path)}
        target = create_path or _KEY_SUFFIX.sub("", entity_path)
        if target == entity_path:
            raise ValueError(
                "Ensure Odata Entity : impossible de déduire l'entity set "
                "(le chemin ne finit pas par une clé '(…)') : fournir "
                "create_path.")
        entity = self.post_odata(target, payload, alias=alias, track=track)
        return {"created": True, "entity": entity}

    def register_created_entity(self, entity_path: str,
                                alias: str = "default") -> None:
        """Enregistre manuellement une entité dans la **fabrique de données**
        de la session (quand `Post Odata` ``track=True`` n'a pas pu identifier
        l'URI, ou pour une entité créée autrement). ``entity_path`` : le
        chemin de l'entité avec sa clé, tel que `Delete Odata` l'accepte."""
        path = str(entity_path).strip()
        if not path:
            raise ValueError("Register Created Entity : chemin vide.")
        self._session(alias).created_entities.append(path)

    def get_created_entities(self, alias: str = "default") -> list[str]:
        """Les entités actuellement suivies par la fabrique de données de la
        session (copie JSON-safe, ordre de création)."""
        return list(self._session(alias).created_entities)

    def delete_created_entities(self, alias: str = "default",
                                strict: bool = False) -> dict[str, Any]:
        """Supprime toutes les entités suivies de la session, en ordre
        **inverse** de création (LIFO : les dépendants d'abord), best-effort :
        un échec n'empêche pas les suivantes. Retourne le rapport JSON-safe
        ``{"deleted": [...], "failed": [{"uri", "error"}]}`` et le journalise.

        Pensé pour un teardown de suite (jamais bloquant par défaut) ;
        ``strict=True`` échoue à la fin si au moins une suppression a échoué."""
        session = self._session(alias)
        report: dict[str, Any] = {"deleted": [], "failed": []}
        while session.created_entities:
            uri = session.created_entities.pop()
            try:
                self.delete_odata(uri, alias=alias)
            except AssertionError as err:
                report["failed"].append({"uri": uri, "error": str(err)[:300]})
            else:
                report["deleted"].append(uri)
        if report["failed"]:
            logger.warn(
                "Delete Created Entities : %d suppression(s) en échec sur %d "
                "(détail dans le rapport retourné). Une URI suivie est celle "
                "que le SERVEUR a annoncée (Location / @odata.id / "
                "__metadata.uri) et elle n'est pas toujours adressable : un "
                "service OData v4 draft-enabled répond par exemple "
                "\"Travel.drafts('...')\" alors que seule la clé composite "
                "\"Travel(TravelUUID=...,IsActiveEntity=false)\" existe. Sur "
                "un 404, enregistrer le chemin qui répond avec Register "
                "Created Entity plutôt que de compter sur Post Odata "
                "track=True."
                % (len(report["failed"]),
                   len(report["failed"]) + len(report["deleted"])))
        else:
            logger.info("Delete Created Entities : %d entité(s) supprimée(s)."
                        % len(report["deleted"]))
        if report["failed"] and _as_bool(strict):
            raise AssertionError(
                "Delete Created Entities (strict) : %d suppression(s) en "
                "échec : %s" % (len(report["failed"]),
                                "; ".join(f["uri"] for f in report["failed"])))
        return report

    def _entity_uri(self, session: _ApiSession, payload: Any,
                    headers: Optional[dict],
                    request_url: Optional[str] = None) -> Optional[str]:
        """URI de l'entité créée : ``__metadata.uri`` (v2), ``@odata.id``
        (v4) ou en-tête ``Location`` ; ramenée en chemin relatif quand son
        origine diffère de la session (reverse-proxy).

        Une URI **relative** se résout contre l'URL de la REQUÊTE (RFC 3986),
        jamais contre la base de session : un service OData v4 répond
        ``Location: Travel.drafts('…')``, relatif au service. Recollée à la
        base, elle perdait son préfixe de service et la suppression partait
        sur la racine (404), laissant la donnée derrière elle alors que le
        ``$count`` des entités actives, lui, semblait restauré."""
        uri: Optional[str] = None
        if isinstance(payload, dict):
            envelope = payload.get("d", payload)
            if isinstance(envelope, dict):
                metadata = envelope.get("__metadata")
                if isinstance(metadata, dict):
                    uri = metadata.get("uri")
                uri = uri or envelope.get("@odata.id")
            if not uri:
                uri = payload.get("@odata.id")
        uri = uri or _header(headers, "Location")
        if not uri:
            return None
        uri = str(uri)
        if request_url and not uri.startswith(("http://", "https://")):
            uri = urllib.parse.urljoin(request_url, uri)
        if uri.startswith(("http://", "https://")) and (
                _url_origin(uri) != _url_origin(session.base_url)):
            parsed = urllib.parse.urlsplit(uri)
            return parsed.path + ("?" + parsed.query if parsed.query else "")
        return uri

    # -- perception et préflight du canal ---------------------------------------

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

    def get_gateway_status(self, alias: str = "default",
                           catalog_path: Optional[str] = None) -> dict[str, Any]:
        """Préflight du canal API : sonde le catalogue Gateway et classe le
        résultat en dict JSON-safe ``{"status", "http_status", "detail",
        "remediation", "catalog_path", "base_url"}``. États : ``ok``,
        ``unreachable``, ``auth_failed``, ``forbidden``,
        ``catalog_not_found``, ``gateway_inactive`` (le cas A4H : conteneur
        re-créé → HTTP 500 ``/IWFND/CM_COS/003``, remédiation = activité IMG
        ``/IWFND/IWF_ACTIVATE``), ``server_error``. Ne lève jamais : le
        miroir API de `Get Scripting Status`."""
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

    # -- RFC et BAPI (optionnel, via pyrfc) --------------------------------------

    def open_rfc_connection(self, alias: str = "default", **params: Any) -> str:
        """Ouvre une connexion RFC via `pyrfc` (``ashost=``, ``sysnr=``,
        ``client=``, ``user=``, ``passwd=``...). Échec explicite avec la marche
        à suivre si `pyrfc`/le SDK NW RFC ne sont pas installés : le RFC reste
        **optionnel**, rien d'autre dans la bibliothèque n'en dépend."""
        try:
            import pyrfc
        except ImportError:
            raise RuntimeError(
                "Call Rfc a besoin de pyrfc (et du SAP NW RFC SDK) : "
                "pip install pyrfc, voir https://github.com/SAP/PyRFC. "
                "Les keywords OData, eux, fonctionnent sans.")
        self._rfc_connections()[alias] = pyrfc.Connection(
            **{name: reveal_secret(value) for name, value in params.items()})
        return alias

    def call_rfc(self, function_name: str, alias: str = "default",
                 **params: Any) -> Any:
        """Appelle le module fonction ``function_name`` sur la connexion RFC
        ``alias`` (ouverte par `Open Rfc Connection`) et retourne le résultat
        (dict pyrfc)."""
        connection = self._rfc_connections().get(alias)
        if connection is None:
            raise RuntimeError(
                "Aucune connexion RFC '%s' : appeler Open Rfc Connection "
                "d'abord." % alias)
        return connection.call(function_name, **params)

    def call_bapi(self, function_name: str, alias: str = "default",
                  return_key: str = "RETURN", **params: Any) -> Any:
        """Appelle une **BAPI** et vérifie sa table ``RETURN`` (BAPIRET2) :
        un message de type ``E``/``A``/``X`` = échec listant les messages
        bloquants (décision par TYPE, jamais par texte localisé : convention
        n°3) et rappelant `Rollback Bapi Transaction`. Sinon retourne le
        résultat complet (dict pyrfc). Le pattern SAP de préparation de
        données robuste : `Call Bapi` puis `Commit Bapi Transaction`."""
        result = self.call_rfc(function_name, alias=alias, **params)
        messages = bapi_return.iter_bapi_messages(result, return_key)
        failing = bapi_return.failing_messages(messages)
        if failing:
            raise AssertionError(
                bapi_return.format_bapi_failure(function_name, failing))
        return result

    def commit_bapi_transaction(self, alias: str = "default",
                                wait: bool = True) -> Any:
        """``BAPI_TRANSACTION_COMMIT`` sur la connexion RFC ``alias`` :
        rend durables les écritures des BAPIs précédentes. ``wait=True``
        (défaut) attend la fin de la mise à jour (``WAIT='X'``) : le réglage
        sûr pour enchaîner une vérification. La table RETURN est vérifiée
        comme dans `Call Bapi`."""
        params = {"WAIT": "X"} if _as_bool(wait) else {}
        return self.call_bapi("BAPI_TRANSACTION_COMMIT", alias=alias, **params)

    def rollback_bapi_transaction(self, alias: str = "default") -> Any:
        """``BAPI_TRANSACTION_ROLLBACK`` sur la connexion RFC ``alias`` :
        annule la LUW en cours (le réflexe après un `Call Bapi` en échec, et
        un teardown sûr des préparations de données interrompues)."""
        return self.call_rfc("BAPI_TRANSACTION_ROLLBACK", alias=alias)

    def wait_for_background_job(self, jobname: str, alias: str = "default",
                                timeout: str = "10m", poll: str = "5s",
                                jobcount: Optional[str] = None) -> dict[str, Any]:
        """Attend la fin d'un **job de fond** (facturation, IDoc, génération
        de données…) en lisant la table ``TBTCO`` via ``RFC_READ_TABLE``
        (remote-enabled partout, aucun écran occupé). Succès quand plus aucun
        run du job n'est dans le pipeline (P/S/Y/R) et qu'au moins un est
        ``F`` (fini) : retourne ``{"state": "done", "statuses",
        "waited_seconds"}``. Un run annulé (``A``) = échec immédiat ; timeout
        = échec actionnable (statuts vus, suggestion ``jobcount=`` si
        plusieurs runs portent ce nom, journal SM37). Nécessite une connexion
        `Open Rfc Connection` sur ``alias``."""
        if self._rfc_connections().get(alias) is None:
            raise RuntimeError(
                "Aucune connexion RFC '%s' : appeler Open Rfc Connection "
                "d'abord (Wait For Background Job lit TBTCO via "
                "RFC_READ_TABLE)." % alias)
        secs = timestr_to_secs(timeout)
        step = timestr_to_secs(poll)
        options = ["JOBNAME EQ %s" % rfc_tables.abap_quote(jobname)]
        if jobcount:
            options.append("AND JOBCOUNT EQ %s" % rfc_tables.abap_quote(jobcount))
        params = rfc_tables.read_table_params("TBTCO", ["STATUS"], options)
        started = time.monotonic()
        state: dict[str, Any] = {
            "verdict": {"state": "missing", "detail": "aucune sonde encore"},
            "counts": {}, "error": None}

        def probe() -> bool:
            try:
                result = self.call_rfc("RFC_READ_TABLE", alias=alias, **params)
            except Exception as err:
                state["error"] = str(err)
                return False
            rows = rfc_tables.parse_read_table(result)
            counts = rfc_tables.summarize_job_statuses(rows)
            state["verdict"] = rfc_tables.job_wait_verdict(counts)
            state["counts"] = counts
            state["error"] = None
            return state["verdict"]["state"] in ("done", "aborted")

        poll_until(probe, secs, max(0.1, step))
        verdict = state["verdict"]
        waited = round(time.monotonic() - started, 2)
        if verdict["state"] == "done":
            return {"state": "done", "statuses": state["counts"],
                    "waited_seconds": waited}
        if verdict["state"] == "aborted":
            raise AssertionError(
                "Le job de fond '%s' a été annulé (statut A). %s Journal "
                "détaillé : SM37." % (jobname, verdict["detail"]))
        raise AssertionError(
            "Le job de fond '%s' n'a pas fini après %s : %s%s Préciser "
            "jobcount= si plusieurs runs portent ce nom ; journal : SM37."
            % (jobname, timeout, verdict["detail"],
               " Dernière erreur RFC : %s." % state["error"]
               if state["error"] else ""))

    def close_rfc_connection(self, alias: str = "default") -> None:
        """Ferme la connexion RFC ``alias`` (silencieux si absente)."""
        connection = self._rfc_connections().pop(alias, None)
        if connection is not None:
            connection.close()

    # -- plomberie ---------------------------------------------------------------

    # Options système OData acceptées sans le préfixe `$` (ergonomie Robot :
    # `top=5` au lieu de `$top=5` impossible en argument nommé).
    _SYSTEM_QUERY = ("top", "skip", "filter", "select", "orderby", "format",
                     "expand", "count", "search", "inlinecount")

    @staticmethod
    def _validate_alias(alias: Any) -> str:
        """Alias non vide, sans blancs parasites (miroir du canal GUI :
        ``_validate_session_alias`` de SapEccLibrary)."""
        alias = str(alias).strip()
        if not alias:
            raise ValueError("API session alias must be a non-empty string.")
        return alias

    def _session(self, alias: str) -> _ApiSession:
        sessions = self._api_sessions()
        session = sessions.get(alias)
        if session is None:
            raise RuntimeError(
                "Aucune session API '%s' : appeler Open Api Session d'abord "
                "(sessions ouvertes : %s)."
                % (alias, ", ".join(sorted(sessions)) or "aucune"))
        return session

    def _build_url(self, session: _ApiSession, path: str,
                   query: Optional[dict]) -> str:
        if path.startswith(("http://", "https://")):
            if _url_origin(path) != _url_origin(session.base_url):
                raise ValueError(
                    "Cross-origin API URL blocked: %s" % path)
            url = path
        else:
            url = session.base_url + "/" + path.lstrip("/")
        params = []
        for key, value in (query or {}).items():
            name = "$" + key if key in self._SYSTEM_QUERY else key
            params.append((name, value))
        if session.sap_client and not _has_query_param(url, "sap-client"):
            params.append(("sap-client", session.sap_client))
        if params:
            separator = "&" if "?" in url else "?"
            url += separator + urllib.parse.urlencode(
                params, quote_via=_QUERY_QUOTE)
        return url

    def _request(self, alias: str, method: str, path: str,
                 query: Optional[dict] = None,
                 headers: Optional[dict] = None,
                 body: Any = None,
                 allowed_errors: tuple = (),
                 _retried_auth: bool = False) -> tuple[int, dict, bytes]:
        """Requête HTTP d'une session : retourne (statut, en-têtes, corps).
        >= 400 → AssertionError auto-corrigible (statut, URL, extrait du
        corps), SAUF les statuts listés dans ``allowed_errors`` (retournés
        avec l'extrait du corps : le GET d'existence d'`Ensure Odata Entity`
        attend son 404). Session OAuth2 : token Bearer garanti avant l'appel,
        renouvelé et rejoué UNE fois sur 401. La télémétrie de session est
        alimentée ici (compteurs, durées, dernier statut)."""
        session = self._session(alias)
        url = self._build_url(session, path, query)
        merged = dict(session.headers)
        if session.token_url:
            merged["Authorization"] = "Bearer %s" % self._ensure_oauth_token(session)
        merged.update(headers or {})
        data = body.encode("utf-8") if isinstance(body, str) else body
        request = urllib.request.Request(url, data=data, headers=merged,
                                         method=method.upper())
        telemetry = session.telemetry
        telemetry["requests"] += 1
        telemetry["last_url"] = url
        started = time.monotonic()
        try:
            response = self._transport(session, request)
        except urllib.error.HTTPError as err:
            telemetry["seconds"] += time.monotonic() - started
            telemetry["last_status"] = err.code
            if err.code == 401 and session.token_url and not _retried_auth:
                session.access_token = None
                return self._request(alias, method, path, query, headers, body,
                                     allowed_errors, _retried_auth=True)
            excerpt = err.read()[:_BODY_EXCERPT].decode("utf-8", errors="replace")
            if err.code in allowed_errors:
                return (err.code, dict(err.headers or {}),
                        excerpt.encode("utf-8"))
            telemetry["errors"] += 1
            telemetry["last_error"] = "HTTP %d %s" % (err.code, err.reason)
            raise _RequestError(
                "%s %s -> HTTP %d %s.\nDébut de la réponse : %s"
                % (method.upper(), url, err.code, err.reason, excerpt),
                err.code, dict(err.headers or {}))
        except urllib.error.URLError as err:
            telemetry["seconds"] += time.monotonic() - started
            telemetry["errors"] += 1
            telemetry["last_error"] = str(err.reason)
            raise AssertionError(
                "%s %s injoignable : %s (système démarré ? port ouvert ? "
                "vérifier base_url/verify_tls)." % (method.upper(), url, err.reason))
        with response:
            payload = response.read()
            telemetry["seconds"] += time.monotonic() - started
            telemetry["last_status"] = response.status
            return (response.status, dict(response.headers), payload)

    def _probe(self, alias: str, path: str,
               query: Optional[dict] = None) -> tuple[Optional[int], str, Optional[str]]:
        """Sonde tolérante pour les préflights : retourne (statut ou None,
        extrait du corps, erreur de connexion ou None) SANS jamais lever :
        c'est le classifieur (``sapfx_common.gateway_status``) qui juge."""
        session = self._session(alias)
        url = self._build_url(session, path, query)
        merged = dict(session.headers)
        if session.token_url:
            try:
                merged["Authorization"] = "Bearer %s" % self._ensure_oauth_token(session)
            except AssertionError as err:
                return None, "", str(err)
        request = urllib.request.Request(url, headers=merged, method="GET")
        try:
            response = self._transport(session, request)
        except urllib.error.HTTPError as err:
            excerpt = err.read()[:_BODY_EXCERPT].decode("utf-8", errors="replace")
            return err.code, excerpt, None
        except urllib.error.URLError as err:
            return None, "", str(err.reason)
        except Exception as err:   # réponse malformée, timeout socket…
            return None, "", str(err)
        with response:
            excerpt = response.read()[:_BODY_EXCERPT].decode(
                "utf-8", errors="replace")
            return response.status, excerpt, None

    def _write_request(self, alias: str, method: str, path: str,
                       query: Optional[dict], body: Any,
                       extra_headers: Optional[dict] = None,
                       csrf_fetch_path: Optional[str] = None
                       ) -> tuple[int, dict, bytes]:
        """Écriture OData avec le protocole CSRF, générique à POST / PATCH /
        DELETE / $batch : token obtenu au besoin, re-fetch et rejeu UNE fois
        sur le 403 CSRF, jugé sur l'en-tête ``x-csrf-token: Required`` de la
        réponse avec repli texte (timeout de sécurité Gateway, ~30 min).
        Toute autre erreur remonte telle quelle."""
        session = self._session(alias)
        try:
            return self._send_with_csrf(session, alias, method, path, query,
                                        body, extra_headers, csrf_fetch_path)
        except AssertionError as err:
            if not _csrf_rejected(err):
                raise
            session.csrf_token = None
            return self._send_with_csrf(session, alias, method, path, query,
                                        body, extra_headers, csrf_fetch_path)

    def _send_with_csrf(self, session: _ApiSession, alias: str, method: str,
                        path: str, query: Optional[dict], body: Any,
                        extra_headers: Optional[dict] = None,
                        csrf_fetch_path: Optional[str] = None
                        ) -> tuple[int, dict, bytes]:
        """Une écriture avec token CSRF, obtenu d'abord si la session n'en a
        pas (GET sur ``csrf_fetch_path``, défaut le chemin visé ; $batch
        fetche sur la racine du service : GET sur $batch n'existe pas).

        L'en-tête du token est lu par ``_header`` (insensible à la casse,
        comme du côté du juge de rejeu) : les en-têtes HTTP sont
        insensibles à la casse et ``dict(response.headers)`` conserve la
        casse ENVOYÉE. Un relais qui répond ``X-Csrf-Token`` faisait
        auparavant tomber le token à vide sans un mot, et l'écriture sans
        token revenait en 403 présenté comme une interdiction."""
        if session.csrf_token is None:
            _, headers, _ = self._request(
                alias, "GET", csrf_fetch_path or path, None,
                headers={"X-CSRF-Token": "Fetch"})
            session.csrf_token = _header(headers, "x-csrf-token") or ""
        extra = {"Content-Type": "application/json"}
        if extra_headers:
            extra.update(extra_headers)
        if session.csrf_token:
            extra["X-CSRF-Token"] = session.csrf_token
        return self._request(alias, method, path, query, headers=extra, body=body)

    def _ensure_oauth_token(self, session: _ApiSession) -> str:
        """Token OAuth2 client credentials valide de la session : réutilisé
        tant qu'il n'expire pas, redemandé sinon (échec = AssertionError
        actionnable nommant le token endpoint ; le secret n'apparaît jamais)."""
        if session.access_token and time.monotonic() < session.token_expiry:
            return session.access_token
        form = {"grant_type": "client_credentials"}
        if session.oauth_scope:
            form["scope"] = session.oauth_scope
        credentials = base64.b64encode(
            ("%s:%s" % (session.client_id,
                        reveal_secret(session.client_secret) or "")).encode(
                "utf-8")).decode("ascii")
        request = urllib.request.Request(
            session.token_url or "", data=urllib.parse.urlencode(form).encode("ascii"),
            method="POST",
            headers={"Authorization": "Basic %s" % credentials,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "Accept": "application/json"})
        try:
            response = self._token_transport(session, request)
        except urllib.error.HTTPError as err:
            excerpt = err.read()[:_BODY_EXCERPT].decode("utf-8", errors="replace")
            raise AssertionError(
                "Le token endpoint %s a refusé le client (HTTP %d) : %s "
                "(vérifier client_id/client_secret/oauth_scope)."
                % (session.token_url, err.code, excerpt))
        except urllib.error.URLError as err:
            raise AssertionError(
                "Token endpoint %s injoignable : %s." % (session.token_url,
                                                         err.reason))
        with response:
            raw = response.read()
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            raise AssertionError(
                "Réponse illisible du token endpoint %s (%s) : %s"
                % (session.token_url, err,
                   raw[:_BODY_EXCERPT].decode("utf-8", errors="replace")))
        token = payload.get("access_token")
        if not token:
            raise AssertionError(
                "Réponse du token endpoint %s sans access_token (clés : %s)."
                % (session.token_url, ", ".join(sorted(payload)) or "aucune"))
        lifetime = float(payload.get("expires_in") or 300)
        session.access_token = str(token)
        session.token_expiry = time.monotonic() + max(30.0, lifetime * 0.9)
        return session.access_token

    @staticmethod
    def _token_transport(session: _ApiSession, request: urllib.request.Request):
        """Frontière réseau du token endpoint (stubbable en test unitaire).
        Volontairement HORS de l'opener de session : le token endpoint
        (IAS, XSUAA) vit légitimement sur un autre hôte que l'API, la garde
        same-origin ne s'y applique pas ; le contexte TLS de la session
        (mTLS, verify_tls) est réutilisé."""
        if session.tls_context is not None:
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=session.tls_context))
            return opener.open(request, timeout=session.timeout)
        return urllib.request.urlopen(request, timeout=session.timeout)

    @staticmethod
    def _transport(session: _ApiSession, request: urllib.request.Request):
        """Frontière réseau (stubbable en test unitaire) : exécute la requête
        via l'opener de la session (cookies rejoués automatiquement, contexte
        TLS éventuel installé par le HTTPSHandler de l'opener)."""
        return session.opener.open(request, timeout=session.timeout)

    @staticmethod
    def _decode_json(body: bytes, status: int, path: str) -> Any:
        try:
            return json.loads(body.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            excerpt = body[:_BODY_EXCERPT].decode("utf-8", errors="replace")
            raise AssertionError(
                "Réponse de '%s' (statut %d) illisible en JSON (%s) : ajouter "
                "format=json ou vérifier le chemin.\nDébut : %s"
                % (path, status, err, excerpt))
