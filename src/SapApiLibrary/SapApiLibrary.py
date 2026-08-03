"""SapApiLibrary — le canal **API** du projet : OData (Gateway/CAP) et RFC.

Le troisième canal, à côté du GUI desktop (``SapEccLibrary``) et du web
(``SapFioriLibrary``). Raison d'être : un test SAP robuste **prépare et
vérifie ses données par l'API** et ne passe par l'écran que pour ce qu'il
teste vraiment — le setup/teardown GUI est lent et fragile, l'API est
rapide et déterministe. Le keyword métier type croise les canaux :
compter par SE16 ET par OData, puis exiger l'égalité (voir
``tests/robot/flagship_cross_paradigm.robot``).

Volontairement en **stdlib pure** (``urllib`` + ``http.cookiejar``) : aucune
dépendance nouvelle à épingler (la leçon pywin32 de la convention 6). Couvre :

* OData **v2** (Gateway embarqué ECC/S4 : enveloppe ``{"d": ...}``) et **v4**
  (CAP, S/4 moderne : ``{"value": [...]}``) — mêmes keywords, détection de
  l'enveloppe ;
* le protocole **CSRF** SAP (``X-CSRF-Token: Fetch`` puis rejeu du token et
  des cookies sur les écritures) ;
* le **RFC** en option : ``Call Rfc`` s'appuie sur `pyrfc` (SAP NW RFC SDK)
  s'il est installé, sinon échoue avec la marche à suivre — jamais de
  dépendance dure à un SDK propriétaire.

Erreurs auto-corrigibles (politique maison) : un échec HTTP nomme le statut,
l'URL effective et le début du corps de réponse.
"""
from __future__ import annotations

import base64
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from typing import Any, Optional, Union

from robot.api import logger
from robot.api.types import Secret
from robot.utils import timestr_to_secs

from sapfx_common.secrets import reveal_secret
from sapfx_common.session_context import current_execution_namespace

_TRUTHY = ("1", "true", "yes", "on")

# Extrait de corps de réponse joint aux erreurs HTTP : assez pour lire le
# message Gateway (<message>...</message>), pas de quoi noyer le log.
_BODY_EXCERPT = 400


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUTHY


def _url_origin(url: str) -> tuple[str, str, Optional[int]]:
    parsed = urllib.parse.urlsplit(url)
    default_port = 443 if parsed.scheme.lower() == "https" else 80
    return (parsed.scheme.lower(), (parsed.hostname or "").lower(),
            parsed.port or default_port)


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
    """État d'une session API : URL de base, auth, cookies, client SAP."""

    def __init__(self, base_url: str, user: Optional[str],
                 password: Optional[Union[str, Secret]], sap_client: Optional[str],
                 timeout: float, verify_tls: bool) -> None:
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
        handlers: list[urllib.request.BaseHandler] = [
            urllib.request.HTTPCookieProcessor(self.cookies),
            _SameOriginRedirectHandler(self.base_url)]
        if not verify_tls:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            handlers.append(urllib.request.HTTPSHandler(context=context))
        self.opener = urllib.request.build_opener(*handlers)
        self.csrf_token: Optional[str] = None


class SapApiLibrary:
    """Bibliothèque Robot Framework pour parler aux APIs SAP (OData v2/v4, RFC).

    == Sessions ==
    `Open Api Session` mémorise URL de base, authentification Basic, client SAP
    et cookies ; tous les keywords OData s'y réfèrent par ``alias`` (plusieurs
    systèmes simultanés possibles). Exemple::

        Open Api Session    http://vhcala4hci:50000    user=DEVELOPER
        ...    password=${SAP_PASSWORD}    sap_client=001
        ${n}=    Get Odata Count    /sap/opu/odata/sap/SEPMRA_SHOP/Products

    == OData v2 et v4 ==
    `Get Odata Entities` renvoie la liste quelle que soit l'enveloppe
    (``d.results`` v2, ``value`` v4) ; `Get Odata Count` lit ``$count``.
    `Post Odata` applique le protocole CSRF SAP automatiquement.

    == RFC (optionnel) ==
    `Open Rfc Connection` / `Call Rfc` utilisent `pyrfc` si installé
    (SAP NW RFC SDK requis) — sinon l'erreur donne la marche à suivre.
    """

    __version__ = "0.6.4"
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
                         verify_tls: bool = True) -> str:
        """Ouvre une session API vers ``base_url`` (mémorise auth Basic,
        ``sap-client`` ajouté à chaque requête, cookies). ``verify_tls=False``
        accepte un certificat auto-signé (systèmes de test). Retourne l'alias."""
        secs = timestr_to_secs(timeout) if timeout else self.default_timeout
        tls_verified = _as_bool(verify_tls)
        if not tls_verified:
            logger.warn("TLS certificate verification is disabled for API session '%s'."
                        % alias)
        self._api_sessions()[alias] = _ApiSession(
            base_url, user, password, sap_client, secs, tls_verified)
        return alias

    def close_api_session(self, alias: str = "default") -> None:
        """Oublie la session ``alias`` (cookies et token CSRF compris)."""
        self._api_sessions().pop(alias, None)

    def close_all_api_sessions(self) -> None:
        """Oublie toutes les sessions API (teardown de suite)."""
        namespace = current_execution_namespace()
        self._sessions_by_namespace.pop(namespace, None)

    def list_api_sessions(self) -> dict[str, Any]:
        """Retourne l'état **JSON-safe** du canal API dans le namespace
        courant : ``{"api_sessions": [{alias, base_url, sap_client,
        authenticated, csrf_token_cached}], "rfc_connections": [alias…]}``.

        JAMAIS de credentials : ``authenticated`` dit seulement si la session
        porte une authentification Basic, ``csrf_token_cached`` si un token
        CSRF a déjà été obtenu. C'est la perception du canal API (il n'a pas
        d'écran) — consommée par le state provider rf-mcp (`SapApiPlugin`)
        et utile en débogage de suite multi-alias."""
        return {
            "api_sessions": [
                {"alias": alias,
                 "base_url": session.base_url,
                 "sap_client": session.sap_client,
                 "authenticated": "Authorization" in session.headers,
                 "csrf_token_cached": session.csrf_token is not None}
                for alias, session in sorted(self._api_sessions().items())],
            "rfc_connections": sorted(self._rfc_connections()),
        }

    # -- OData -----------------------------------------------------------------

    def get_odata(self, path: str, alias: str = "default",
                  **query: str) -> Any:
        """GET OData → JSON décodé tel quel (enveloppe v2/v4 comprise). Les
        arguments nommés deviennent des paramètres de requête (``top=5`` →
        ``$top=5`` : le préfixe ``$`` des options système OData est ajouté aux
        noms connus — top/skip/filter/select/orderby/format/expand/count)."""
        status, _, body = self._request(alias, "GET", path, query)
        return self._decode_json(body, status, path)

    def get_odata_entities(self, path: str, alias: str = "default",
                           **query: str) -> list:
        """GET OData → la **liste d'entités**, quelle que soit la version :
        ``d.results`` (v2), ``value`` (v4), ou l'entité seule dans une liste."""
        payload = self.get_odata(path, alias=alias, **query)
        if isinstance(payload, dict):
            envelope = payload.get("d", payload)
            if isinstance(envelope, dict) and isinstance(
                    envelope.get("results"), list):
                return envelope["results"]
            if isinstance(payload.get("value"), list):
                return payload["value"]
            return [envelope]
        if isinstance(payload, list):
            return payload
        raise AssertionError(
            "Réponse OData inattendue pour '%s' : ni enveloppe v2 (d.results) "
            "ni v4 (value) — reçu %r" % (path, type(payload).__name__))

    def get_odata_count(self, entity_path: str, alias: str = "default",
                        **query: str) -> int:
        """``GET <entity_path>/$count`` → entier (v2 et v4). Le chemin est
        celui de l'entity set (``.../Products``) ; les filtres passent en
        arguments nommés (``filter=Price gt 100``)."""
        path = "%s/$count" % entity_path.rstrip("/")
        status, _, body = self._request(alias, "GET", path, query,
                                        headers={"Accept": "text/plain"})
        text = body.decode("utf-8-sig", errors="replace").strip()
        digits = "".join(ch for ch in text if ch.isdigit())
        if not digits:
            raise AssertionError(
                "$count sur '%s' n'a pas retourné un entier (statut %d) : %r"
                % (entity_path, status, text[:_BODY_EXCERPT]))
        return int(digits)

    def post_odata(self, path: str, payload: Any, alias: str = "default",
                   **query: str) -> Any:
        """POST OData avec le protocole **CSRF** SAP : un GET préalable avec
        ``X-CSRF-Token: Fetch`` obtient le token (mémorisé avec les cookies de
        session), rejoué sur l'écriture. ``payload`` : dict (sérialisé JSON) ou
        chaîne déjà sérialisée. Retourne le JSON de la réponse (``{}`` si 204)."""
        session = self._session(alias)
        if session.csrf_token is None:
            _, headers, _ = self._request(
                alias, "GET", path, None, headers={"X-CSRF-Token": "Fetch"})
            session.csrf_token = headers.get("x-csrf-token") or headers.get(
                "X-CSRF-Token") or ""
        body = payload if isinstance(payload, (str, bytes)) else json.dumps(payload)
        extra = {"Content-Type": "application/json"}
        if session.csrf_token:
            extra["X-CSRF-Token"] = session.csrf_token
        status, _, raw = self._request(alias, "POST", path, query,
                                       headers=extra, body=body)
        if status == 204 or not raw.strip():
            return {}
        return self._decode_json(raw, status, path)

    # -- RFC (optionnel, via pyrfc) ---------------------------------------------

    def open_rfc_connection(self, alias: str = "default", **params: Any) -> str:
        """Ouvre une connexion RFC via `pyrfc` (``ashost=``, ``sysnr=``,
        ``client=``, ``user=``, ``passwd=``...). Échec explicite avec la marche
        à suivre si `pyrfc`/le SDK NW RFC ne sont pas installés — le RFC reste
        **optionnel**, rien d'autre dans la bibliothèque n'en dépend."""
        try:
            import pyrfc
        except ImportError:
            raise RuntimeError(
                "Call Rfc a besoin de pyrfc (et du SAP NW RFC SDK) : "
                "pip install pyrfc — voir https://github.com/SAP/PyRFC. "
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
                "Aucune connexion RFC '%s' — appeler Open Rfc Connection "
                "d'abord." % alias)
        return connection.call(function_name, **params)

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

    def _session(self, alias: str) -> _ApiSession:
        sessions = self._api_sessions()
        session = sessions.get(alias)
        if session is None:
            raise RuntimeError(
                "Aucune session API '%s' — appeler Open Api Session d'abord "
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
        if session.sap_client:
            params.append(("sap-client", session.sap_client))
        if params:
            separator = "&" if "?" in url else "?"
            url += separator + urllib.parse.urlencode(params)
        return url

    def _request(self, alias: str, method: str, path: str,
                 query: Optional[dict] = None,
                 headers: Optional[dict] = None,
                 body: Any = None) -> tuple[int, dict, bytes]:
        """Requête HTTP d'une session : retourne (statut, en-têtes, corps).
        >= 400 → AssertionError auto-corrigible (statut, URL, extrait du corps)."""
        session = self._session(alias)
        url = self._build_url(session, path, query)
        merged = dict(session.headers)
        merged.update(headers or {})
        data = body.encode("utf-8") if isinstance(body, str) else body
        request = urllib.request.Request(url, data=data, headers=merged,
                                         method=method.upper())
        try:
            response = self._transport(session, request)
        except urllib.error.HTTPError as err:
            excerpt = err.read()[:_BODY_EXCERPT].decode("utf-8", errors="replace")
            raise AssertionError(
                "%s %s -> HTTP %d %s.\nDébut de la réponse : %s"
                % (method.upper(), url, err.code, err.reason, excerpt))
        except urllib.error.URLError as err:
            raise AssertionError(
                "%s %s injoignable : %s (système démarré ? port ouvert ? "
                "vérifier base_url/verify_tls)." % (method.upper(), url, err.reason))
        with response:
            payload = response.read()
            return (response.status, dict(response.headers), payload)

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
                "Réponse de '%s' (statut %d) illisible en JSON (%s) — ajouter "
                "format=json ou vérifier le chemin.\nDébut : %s"
                % (path, status, err, excerpt))
