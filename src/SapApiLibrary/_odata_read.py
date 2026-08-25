"""Mixin lectures OData : GET, comptage, fonctions, ``$batch``, sondes.

`Get Odata` / `Get Odata Entities` (enveloppes v2 ``d.results`` et v4
``value`` detectees, pagination server-driven suivie sur demande),
`Get Odata Count`, `Call Odata Function`, `Post Odata Batch` (multipart
v2 ET v4, changeset atomique) et `Probe Odata Entity Sets` (la sonde
d'existence TOLERANTE : consigne statut HTTP et code technique OData par
entity set au lieu de s'arreter au premier refus).

Extrait de ``SapApiLibrary.py`` (convention #13).
"""
from __future__ import annotations

import json
import urllib.parse
from typing import Any, Optional

from robot.api import logger

from sapfx_common.cross_channel import odata_error_code
from sapfx_common.odata_batch import build_batch, parse_batch_response

from ._core import _ApiCore
from ._http import _BODY_EXCERPT, _as_bool, _header


class OdataReadKeywords(_ApiCore):
    """Mixin de :class:`SapApiLibrary` : les lectures du canal OData."""

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

    def probe_odata_entity_sets(self, service_path: str, entity_sets: Any,
                                alias: str = "default",
                                max_entity_sets: Any = 50) -> dict[str, Any]:
        """**Sonde tolérante** d'existence : compte chaque entity set en UN
        aller-retour ``$batch`` et ENREGISTRE les refus au lieu d'échouer.

        C'est le mode qui manquait au canal. `Post Odata Batch` échoue en bloc
        au premier refus, et c'est le bon comportement pour préparer un jeu de
        données (un échec partiel silencieux corromprait la préparation) ;
        c'est le mauvais pour une sonde, qui doit consigner et poursuivre.
        Le comportement tout ou rien reste donc intact, et ce keyword vit à
        côté.

        Retourne ``{"service_path", "probed": [...], "truncated"}`` ; chaque
        entrée porte ``{"entity_set", "status", "reason", "count",
        "error_code"}``. Le diagnostic est le **statut HTTP** et le **code
        technique** OData (``error.code``), jamais le message, dépendant de la
        langue de la session (convention 3) : c'est ce couple qui distingue un
        refus d'autorisation d'un entity set inexistant. ``count`` vaut
        l'entier lu quand la lecture a abouti, ``None`` sinon : un compte nul
        n'est jamais confondu avec un accès refusé.

        ``max_entity_sets`` borne le lot ; une borne atteinte est rapportée
        (``truncated``), jamais un succès silencieux. Lecture seule, malgré le
        POST que le protocole ``$batch`` impose (et le jeton CSRF qui va avec).
        """
        names = [str(name).strip() for name in (
            [entity_sets] if isinstance(entity_sets, str) else entity_sets)
            if str(name).strip()]
        try:
            limit = int(str(max_entity_sets).strip())
        except (TypeError, ValueError):
            limit = 0
        if limit < 1:
            raise AssertionError(
                "Probe Odata Entity Sets : max_entity_sets doit être un entier "
                "strictement positif.")
        kept, truncated = names[:limit], len(names) > limit
        if not kept:
            return {"service_path": service_path, "probed": [],
                    "truncated": truncated}
        operations = [{"method": "GET", "path": "%s/$count" % name}
                      for name in kept]
        responses = self.post_odata_batch(service_path, operations,
                                          alias=alias, fail_on_error=False)
        if len(responses) != len(kept):
            # Attribuer des verdicts à des réponses décalées serait pire que
            # de ne rien rendre : chaque entity set hériterait du statut du
            # voisin, et le rapport serait vert et faux.
            raise AssertionError(
                "Probe Odata Entity Sets : le $batch a renvoyé %d réponse(s) "
                "pour %d opération(s) ; les verdicts ne peuvent pas être "
                "attribués sans risque d'inversion."
                % (len(responses), len(kept)))
        probed: list[dict[str, Any]] = []
        for name, response in zip(kept, responses, strict=True):
            status = int(response.get("status", 0))
            body = str(response.get("body", "")).strip()
            count = int(body) if status < 400 and body.isdigit() else None
            probed.append({
                "entity_set": name,
                "status": status,
                "reason": str(response.get("reason", "")),
                "count": count,
                "error_code": odata_error_code(response.get("json")),
            })
        if truncated:
            logger.warn(
                "Probe Odata Entity Sets : sondage borné à %d entity set(s) "
                "sur %d ; les suivants restent NON sondés (jamais un compte "
                "nul) : augmenter max_entity_sets pour tout couvrir."
                % (limit, len(names)))
        return {"service_path": service_path, "probed": probed,
                "truncated": truncated}
