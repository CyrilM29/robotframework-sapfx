"""Mixin des observations de *sécurité du transport* du canal API.

Ce que ces keywords ajoutent, et pourquoi ils ne font pas doublon avec les
lectures de configuration : les autres canaux LISENT ce que le système
déclare, celui-ci OBSERVE ce que le système fait sur le fil. La différence
n'est pas théorique.

Mesuré le 2026-09-14 sur ABAP Platform 2023 (release 758) : le paramètre qui
pilote le drapeau ``HttpOnly`` des cookies vaut ``3``, ce que le canal RFC lit
et ce que l'écran confirme venir du noyau. Aucun des trois cookies de session
ne porte le drapeau, ticket d'authentification compris, et aucun ne porte
``Secure`` même servi en HTTPS. Un audit qui s'arrête à la valeur du paramètre
conclut à une protection qui n'existe pas.

L'enseignement transposable dépasse ce paramètre : *la valeur d'un paramètre
de sécurité n'est pas un curseur*. Lire ``3`` comme « plus durci que ``0`` »
est un réflexe, et l'observation le dément. Un contrôle « au moins 3 » serait
vert et faux.

Logique pure dans ``sapfx_common.http_security``. Ajouté à côté de
``_rfc_surface.py`` plutôt que dedans (convention #13) : ce mixin parle HTTP,
son voisin parle RFC.
"""
from __future__ import annotations

from typing import Any, Optional

from sapfx_common import http_security

from ._rfc_surface import RfcSurfaceKeywords


class HttpSecurityKeywords(RfcSurfaceKeywords):
    """Mixin de :class:`SapApiLibrary` : la sécurité observée du transport."""

    def get_api_cookie_security(self, alias: str = "default",
                                probe_path: Optional[str] = None
                                ) -> dict[str, Any]:
        """Observe les *propriétés de transport des cookies* que la cible
        pose, et rend ``{"total", "names", "without_httponly",
        "without_secure", "without_samesite", "all_protected", "over_https",
        "cookies"}``.

        ``probe_path`` déclenche d'abord un appel de lecture pour que la cible
        pose ses cookies : sans lui, une session fraîchement ouverte n'a rien
        à observer et le résumé serait vide, ce qui se lirait comme « aucun
        cookie non protégé ». C'est le faux positif le plus facile à commettre
        ici, donc le keyword rend ``total`` et l'appelant peut le garder.

        *Aucune valeur de cookie n'est lue ni rendue.* Le keyword constate
        des propriétés de transport ; un identifiant de session recopié dans
        un rapport ou un artefact committé serait un secret exposé.

        Exemple :
        | ${cookies}=    `Get Api Cookie Security`    alias=a4h    probe_path=/sap/opu/odata/iwfnd/catalogservice;v=2/ServiceCollection/$count
        | Should Be True    ${cookies}[total] > 0
        | Log    ${cookies}[without_httponly]
        """
        session = self._session(alias)
        if probe_path:
            self._request(alias, "GET", str(probe_path), None)
        fiches = []
        for cookie in session.cookies:
            # `http.cookiejar` range les attributs non standard à part
            # (HttpOnly en fait partie, sans accesseur dédié) et les conserve
            # TELS QU'ÉCRITS par le serveur. Un en-tête HTTP étant insensible
            # à la casse, deviner une ou deux orthographes laisse passer les
            # autres, et chaque oubli produit un faux « non protégé » : c'est
            # exactement la conclusion que cette campagne publie, donc le
            # lecteur doit être insensible à la casse. Verrouillé par un test
            # hors SAP qui éprouve cinq orthographes ET le cas positif, sans
            # lequel un lecteur aveugle rendrait le résultat attendu.
            # L'API publique (`has_nonstandard_attr`) exige de NOMMER une
            # casse ; seule la table brute permet de comparer sans en
            # présumer. D'où l'accès défensif plutôt que l'attribut direct.
            attributs = {str(k).lower(): v for k, v in
                         (getattr(cookie, "_rest", None) or {}).items()}
            fiches.append({
                "name": cookie.name,
                "secure": bool(cookie.secure),
                "httponly": "httponly" in attributs,
                "samesite": attributs.get("samesite"),
                "path": cookie.path,
                "domain": cookie.domain,
            })
        return http_security.summarize_cookie_security(
            fiches, over_https=str(session.base_url).lower().startswith("https"))

    def get_api_security_headers(self, path: str, alias: str = "default",
                                 expected: Any = None) -> dict[str, Any]:
        """Observe les *en-têtes de sécurité* de la réponse à une lecture, et
        rend ``{"present", "missing", "values", "count_present",
        "count_expected"}``.

        Aucun de ces en-têtes n'est obligatoire : ce sont des protections que
        le navigateur applique quand le serveur les demande. Une cible qui n'en
        pose aucun laisse ces protections à la charge de ce qui est devant
        elle, et c'est un constat de posture, pas une non-conformité.

        La comparaison est insensible à la casse, comme les en-têtes HTTP :
        une lecture sensible à la casse déclarerait absent un en-tête présent.

        Exemple :
        | ${headers}=    `Get Api Security Headers`    /sap/opu/odata/iwfnd/catalogservice;v=2/ServiceCollection/$count    alias=a4h
        | Log    ${headers}[missing]
        """
        _, headers, _ = self._request(alias, "GET", str(path), None)
        return http_security.assess_security_headers(headers, expected)

    def confront_security_control(self, control: str, declared: Any,
                                  observed: Any,
                                  expectation: Any = True) -> dict[str, Any]:
        """Confronte ce qu'un paramètre DÉCLARE et ce que le fil MONTRE, et
        rend le verdict de la confrontation.

        C'est le keyword qui fait d'une campagne multi-canal autre chose qu'une
        juxtaposition de lectures : un canal de configuration donne la valeur,
        celui-ci donne l'effet, et seul leur croisement dit si la protection
        existe.

        ``verdict`` vaut ``confirmed``, ``declared_without_effect`` (le faux
        positif de conformité, mesuré sur la cible), ``effect_without_declaration``
        ou ``undetermined``. Une observation absente rend toujours
        ``undetermined`` et jamais une conformité.

        La valeur déclarée est rapportée telle quelle et *jamais interprétée
        comme un niveau* : lire une échelle numérique comme un curseur de
        durcissement est précisément l'erreur que l'observation a démentie.

        Exemple :
        | ${cookies}=    `Get Api Cookie Security`    alias=a4h    probe_path=/sap/opu/odata/iwfnd/catalogservice;v=2/ServiceCollection/$count
        | ${verdict}=    `Confront Security Control`    cookies.httponly    1    ${cookies}[all_protected]
        | Should Be Equal    ${verdict}[verdict]    declared_without_effect
        """
        vu: Optional[bool]
        if observed is None or str(observed).strip() == "":
            vu = None
        elif isinstance(observed, bool):
            vu = observed
        else:
            vu = str(observed).strip().lower() in ("true", "yes", "1", "x")
        attendu = expectation
        if not isinstance(attendu, bool):
            attendu = str(attendu).strip().lower() in ("true", "yes", "1", "x")
        return http_security.confront_declared_and_observed(
            control, declared, vu, attendu)
