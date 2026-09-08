"""Plomberie des requetes du canal API (prive) : URL, erreurs, CSRF, OAuth2.

La classe de base :class:`_ApiCore` dont heritent tous les mixins de
``SapApiLibrary`` : resolution d'alias, construction d'URL (queries encodees
``%20``, jamais ``+`` : un service OData v4 refuse l'espace formulaire),
``_request`` (erreurs auto-corrigibles nommant statut, URL et extrait du
corps, telemetrie alimentee ici), ``_probe`` (sonde tolerante des
preflights), l'ecriture sous protocole CSRF SAP (re-fetch et rejeu UNE fois
sur le 403 CSRF) et le renouvellement du token OAuth2 client credentials.

Extrait de ``SapApiLibrary.py`` (convention #13).
"""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from sapfx_common.secrets import reveal_secret

from ._http import (
    _BODY_EXCERPT,
    _QUERY_QUOTE,
    _ApiSession,
    _RequestError,
    _SameOriginRedirectHandler,
    _csrf_rejected,
    _decompress,
    _has_query_param,
    _header,
    _url_origin,
)


class _ApiCore:
    """Socle des mixins : etat commun et plomberie HTTP. ``_api_sessions`` /
    ``_rfc_connections`` (partition par namespace rf-mcp) sont fournis par
    :class:`SapApiLibrary` ; les mixins n'y accedent qu'a travers ``self``."""

    default_timeout: float

    def _api_sessions(self) -> dict[str, _ApiSession]:
        raise NotImplementedError   # fourni par SapApiLibrary

    def _rfc_connections(self) -> dict[str, Any]:
        raise NotImplementedError   # fourni par SapApiLibrary

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
            excerpt = _decompress(err.headers, err.read())[
                :_BODY_EXCERPT].decode("utf-8", errors="replace")
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
            payload = _decompress(response.headers, response.read())
            telemetry["seconds"] += time.monotonic() - started
            telemetry["last_status"] = response.status
            return (response.status, dict(response.headers), payload)

    def _probe(self, alias: str, path: str,
               query: Optional[dict] = None) -> tuple[Optional[int], str, Optional[str]]:
        """Sonde tolérante pour les préflights : retourne (statut ou None,
        extrait du corps, erreur de connexion ou None) SANS jamais lever :
        c'est le classifieur (``sapfx_common.gateway_status``) qui juge."""
        status, _, body, _, error, _ = self._probe_response(alias, path, query)
        return status, body, error

    def _probe_response(self, alias: str, path: str,
                        query: Optional[dict] = None,
                        max_chars: int = _BODY_EXCERPT,
                        extra_headers: Optional[dict] = None,
                        ) -> tuple[Optional[int], dict, str, bool,
                                   Optional[str], str]:
        """La sonde tolérante COMPLÈTE : retourne (statut ou None, en-têtes de
        réponse, corps décodé tronqué à ``max_chars``, tronqué ?, erreur de
        connexion ou None, URL effective) sans jamais lever. ``_probe`` en est
        la vue réduite ; `Get Http Response` l'expose en keyword.

        La télémétrie de session est alimentée ici aussi (compteur, durée,
        dernier statut) : une sonde traverse le réseau autant qu'une lecture,
        et une reconnaissance faite entièrement de sondes doit compter pour
        ``Api Channel Should Show Activity``. Mesuré avant le correctif
        (2026-08-26, site Work Zone BTP) : ~15 sondes réseau, ``requests: 2``.
        Seul ``errors`` reste hors sonde : un refus est ici un RÉSULTAT
        consigné, pas un échec du canal."""
        session = self._session(alias)
        url = self._build_url(session, path, query)
        merged = dict(session.headers)
        if session.token_url:
            try:
                merged["Authorization"] = "Bearer %s" % self._ensure_oauth_token(session)
            except AssertionError as err:
                return None, {}, "", False, str(err), url
        merged.update(extra_headers or {})
        request = urllib.request.Request(url, headers=merged, method="GET")
        telemetry = session.telemetry
        telemetry["requests"] += 1
        telemetry["last_url"] = url
        started = time.monotonic()

        def cut(raw_headers: Any, payload: bytes) -> tuple[str, bool]:
            text = _decompress(raw_headers, payload).decode(
                "utf-8", errors="replace")
            return text[:max_chars], len(text) > max_chars

        try:
            response = self._transport(session, request)
        except urllib.error.HTTPError as err:
            telemetry["seconds"] += time.monotonic() - started
            telemetry["last_status"] = err.code
            body, truncated = cut(err.headers, err.read())
            return err.code, dict(err.headers or {}), body, truncated, None, url
        except urllib.error.URLError as err:
            telemetry["seconds"] += time.monotonic() - started
            return None, {}, "", False, str(err.reason), url
        except Exception as err:   # réponse malformée, timeout socket…
            telemetry["seconds"] += time.monotonic() - started
            return None, {}, "", False, str(err), url
        with response:
            body, truncated = cut(response.headers, response.read())
            telemetry["seconds"] += time.monotonic() - started
            telemetry["last_status"] = response.status
            return (response.status, dict(response.headers), body, truncated,
                    None, url)

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
            excerpt = _decompress(err.headers, err.read())[
                :_BODY_EXCERPT].decode("utf-8", errors="replace")
            raise AssertionError(
                "Le token endpoint %s a refusé le client (HTTP %d) : %s "
                "(vérifier client_id/client_secret/oauth_scope)."
                % (session.token_url, err.code, excerpt))
        except urllib.error.URLError as err:
            raise AssertionError(
                "Token endpoint %s injoignable : %s." % (session.token_url,
                                                         err.reason))
        with response:
            raw = _decompress(response.headers, response.read())
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
        raw_lifetime = payload.get("expires_in")
        lifetime = 300.0 if raw_lifetime in (None, "") else float(raw_lifetime)
        session.access_token = str(token)
        # L'échéance locale reste TOUJOURS sous la durée annoncée : la marge
        # de renouvellement (10 %) se SOUSTRAIT de la durée, elle ne s'y
        # substitue pas. L'ancien plancher de 30 s gardait un token annoncé
        # 10 s pendant 30 s, donc rejoué expiré (401 assuré, masqué par le
        # rejeu). Un ``expires_in`` de 0 est respecté (token renouvelé à
        # chaque appel) ; seul un champ ABSENT vaut le défaut de 300 s.
        session.token_expiry = time.monotonic() + max(0.0, lifetime * 0.9)
        return session.access_token

    @staticmethod
    def _token_opener(session: _ApiSession, request: urllib.request.Request
                      ) -> urllib.request.OpenerDirector:
        """Opener du token endpoint, porteur de SA garde de redirection,
        épinglée sur l'origine du token endpoint LUI-MÊME (indépendante de
        l'hôte API). Le gestionnaire de redirection standard d'urllib
        CONSERVE l'en-tête ``Authorization`` (ici le Basic
        client_id:client_secret) en suivant une redirection vers un autre
        hôte : sans cette garde, un token endpoint compromis ou mal
        configuré rejouerait les identifiants du client vers l'hôte de son
        choix. Le contexte TLS de la session (mTLS, verify_tls) est
        réutilisé."""
        handlers: list[urllib.request.BaseHandler] = [
            _SameOriginRedirectHandler(request.full_url)]
        if session.tls_context is not None:
            handlers.append(
                urllib.request.HTTPSHandler(context=session.tls_context))
        return urllib.request.build_opener(*handlers)

    @classmethod
    def _token_transport(cls, session: _ApiSession,
                         request: urllib.request.Request):
        """Frontière réseau du token endpoint (stubbable en test unitaire).
        Volontairement HORS de l'opener de session : le token endpoint
        (IAS, XSUAA) vit légitimement sur un autre hôte que l'API, donc la
        garde same-origin de la SESSION ne s'y applique pas ; il porte la
        SIENNE (voir ``_token_opener``)."""
        opener = cls._token_opener(session, request)
        return opener.open(request, timeout=session.timeout)

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
