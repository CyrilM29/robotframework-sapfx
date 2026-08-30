"""Transport HTTP du canal API (prive) : session, redirections, encodages.

Le socle reseau de ``SapApiLibrary``, en stdlib pure : l'etat d'une session
(:class:`_ApiSession` : base_url, auth Basic/OAuth2/mTLS/cle d'API, cookies,
cache ``$metadata``, telemetrie), le garde de redirection same-origin, la
decompression systematique des corps lus (le bac a sable api.sap.com sert son
``$metadata`` en gzip SANS qu'aucun ``Accept-Encoding`` ait ete envoye), et
les utilitaires d'URL et d'en-tetes.

Extrait de ``SapApiLibrary.py`` (convention #13). La bibliotheque publique et
ses mixins vivent a cote ; rien ici n'est un keyword.
"""
from __future__ import annotations

import base64
import gzip
import re
import ssl
import urllib.parse
import urllib.request
import zlib
from http.cookiejar import CookieJar
from typing import Any, Optional, Union

from robot.api.types import Secret

from sapfx_common.secrets import reveal_secret

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


def _decompress(headers: Any, raw: bytes) -> bytes:
    """Corps décompressé quand le serveur l'a encodé, rendu tel quel sinon.

    Relevé live le 2026-08-22 sur le bac à sable SAP Business Accelerator
    Hub : ses documents ``$metadata`` arrivent en ``Content-Encoding: gzip``
    alors que le client n'a JAMAIS envoyé d'``Accept-Encoding``. Sans cette
    frontière, les octets compressés remontent tels quels au parseur XML,
    qui échoue par « not well-formed (invalid token): line 1, column 0 » :
    un message qui accuse le document alors que le fautif est le transport,
    et qui envoie donc chercher au mauvais endroit.

    Un encodage inconnu, ou un corps annoncé compressé qui ne l'est pas,
    est rendu inchangé : le diagnostic du niveau au-dessus (JSON illisible,
    XML illisible, avec statut et URL) vaut mieux qu'une exception ici.
    """
    encoding = str(_header(headers, "Content-Encoding") or "").strip().lower()
    if not raw or encoding in ("", "identity"):
        return raw
    try:
        if encoding == "gzip":
            return gzip.decompress(raw)
        if encoding == "deflate":
            try:
                return zlib.decompress(raw)
            except zlib.error:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
    except (OSError, zlib.error, EOFError):
        return raw
    return raw


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
                 oauth_scope: Optional[str] = None,
                 api_key: Optional[Union[str, Secret]] = None,
                 api_key_header: str = "APIKey",
                 extra_headers: Optional[dict] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.sap_client = sap_client
        self.timeout = timeout
        self.headers: dict[str, str] = {"Accept": "application/json"}
        if user is not None:
            token = base64.b64encode(
                ("%s:%s" % (user, reveal_secret(password) or "")).encode(
                    "utf-8")).decode("ascii")
            self.headers["Authorization"] = "Basic %s" % token
        # Clé d'API en en-tête (bac à sable SAP Business Accelerator Hub).
        self.api_key_header: Optional[str] = None
        if api_key is not None:
            self.api_key_header = api_key_header
            self.headers[api_key_header] = reveal_secret(api_key) or ""
        # En-têtes par défaut de l'appelant, appliqués en DERNIER : ils
        # peuvent surcharger l'``Accept`` maison (un approuter BTP arbitre
        # HTML/JSON sur cet en-tête, relevé live 2026-08-26) ; les valeurs ne
        # sont jamais journalisées.
        if extra_headers:
            self.headers.update({str(k): str(v)
                                 for k, v in dict(extra_headers).items()})
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
