"""Mixin ecritures OData et fabrique de donnees de test.

`Post Odata` / `Patch Odata` / `Delete Odata` (protocole CSRF automatique,
``If-Match`` gere), et la fabrique : ``track=True`` memorise chaque entite
creee par session, `Ensure Odata Entity` cree seulement si absent,
`Delete Created Entities` nettoie en teardown (ordre inverse, rapport
JSON-safe). ``_entity_uri`` resout l'URI annoncee par le serveur contre le
SERVICE, pas la base de session (lecon cap-sflight 2026-08-19 : un
``Location`` relatif au service supprimait a la racine, 404 et donnee
laissee en place).

Extrait de ``SapApiLibrary.py`` (convention #13).
"""
from __future__ import annotations

import json
import urllib.parse
from typing import Any, Optional

from robot.api import logger

from ._core import _ApiCore
from ._http import (
    _KEY_SUFFIX,
    _ApiSession,
    _as_bool,
    _header,
    _url_origin,
)


class OdataWriteKeywords(_ApiCore):
    """Mixin de :class:`SapApiLibrary` : ecritures et fabrique de donnees."""

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

    @staticmethod
    def _if_match_header(if_match: Optional[str]) -> Optional[dict[str, str]]:
        if if_match in (None, "", "None"):
            return None
        return {"If-Match": str(if_match)}

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

    def build_draft_entity_path(self, entity_set: str, key_field: str,
                                key_value: str,
                                active: str = "false") -> str:
        """Chemin ADRESSABLE d'une entité d'un service OData v4
        **draft-enabled** : ``<set>(<clé>=<valeur>,IsActiveEntity=<actif>)``.

        Sur un service draft-enabled, la clé est COMPOSITE : l'identifiant
        seul ne désigne rien, il faut lui adjoindre l'état actif ou brouillon.
        C'est du savoir de PROTOCOLE, pas du vocabulaire d'un site : il vivait
        dans la couche resources, promu ici (convention #12).

        Deux pièges que ce keyword rend visibles (mesurés live sur cap-sflight,
        2026-08-19) : un POST y crée un BROUILLON, que ni le ``$count`` ni une
        lecture ordinaire ne rendent (les deux ne voient que les entités
        ACTIVES), donc un compte inchangé ne prouve AUCUN nettoyage ; et l'URI
        que le serveur annonce en ``Location`` (``…Travel.drafts('…')``) n'est
        pas adressable, d'où le chemin construit ici et confié à
        `Register Created Entity`. ::

            ${chemin}=    Build Draft Entity Path    /processor/Travel
            ...    TravelUUID    ${uuid}
            Register Created Entity    ${chemin}
        """
        path = str(entity_set).strip().rstrip("/")
        if not path:
            raise ValueError("Build Draft Entity Path : entity_set vide.")
        field = str(key_field).strip()
        if not field:
            raise ValueError("Build Draft Entity Path : key_field vide.")
        return "%s(%s=%s,IsActiveEntity=%s)" % (
            path, field, str(key_value).strip(), str(active).strip())

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
