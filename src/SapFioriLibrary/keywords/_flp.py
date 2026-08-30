"""Mixin launchpad, IDP et vocabulaire metier (ports de playwright-praman).

`Open Fiori App` (navigation FLP par **intent** ``SemanticObject-action`` :
le hash stable, cross-catalogue/theme/langue), `Log In Via Identity
Provider` (presets sap-ias/azure-ad/generic, une-page et deux-etapes
detectes dynamiquement, mot de passe jamais journalise) et
`Lookup Business Term` (le vocabulaire partage des trois canaux).

Concepts issus de playwright-praman (Apache-2.0, NOTICE), reimplementes sur
nos moteurs. Extrait de ``SapFioriLibrary.py`` (convention #13).
"""

from urllib.parse import urljoin

from robot.api import logger
from robot.api.types import Secret
from robot.utils import timestr_to_secs

from sapfx_common.auth_flows import resolve_preset
from sapfx_common.polling import poll_until
from sapfx_common.secrets import reveal_secret
from sapfx_common.vocabulary import lookup_as_dict

from .._ui5_js import (
    USHELL_CONFIG_PROBE_JS,
)
from .._ui5_runtime import (
    build_intent_hash,
    parse_location,
)

from ._base import FioriBase


class FlpKeywords(FioriBase):
    """Mixin compose dans :class:`SapFioriLibrary` (voir ce module).
    Suppose la page active de Browser accessible via ``self._browser()``
    et la plomberie de ``_base.py`` disponible par composition."""

    # -- navigation launchpad, authentification IDP, vocabulaire métier ---------
    # (concepts issus de l'analyse de playwright-praman, Apache-2.0, voir NOTICE ;
    #  réimplémentés sur nos moteurs, jamais portés verbatim)

    def open_fiori_app(self, intent, **params):
        """Navigue le launchpad vers un **intent sémantique**
        ``SemanticObject-action`` (``Shell-home``, ``SalesOrder-manage``…),
        paramètres nommés émis en query string::

            Open Fiori App    SalesOrder-manage    SalesOrder=1234

        C'est la voie STABLE de navigation FLP : le hash d'intent survit aux
        réorganisations de catalogue, au thème et à la langue, contrairement
        au clic de tuile par titre (`Open App` de la resource, qui reste la
        voie « comme l'utilisateur »). Intent invalide = échec immédiat avec
        la forme attendue. Ne fait QUE naviguer : enchaîner avec
        ``Wait For UI5 Ready`` (le keyword resource `Open App By Intent`
        fait les deux)."""
        hash_ = build_intent_hash(intent, params or None)
        browser = self._browser()
        base = str(browser.get_url()).split("#", 1)[0]
        browser.go_to(base + hash_)
        logger.info("FLP navigation: %s" % hash_)

    def get_page_location(self, url=None, base=None):
        """Décompose l'adresse RÉELLEMENT atteinte par le navigateur en dict
        JSON-safe ``{url, scheme, host, path, query, fragment, intent,
        intent_params}`` : le « où suis-je » du canal web, l'inverse de
        `Open Fiori App`. ::

            ${ou}=    Get Page Location
            Should Be Equal    ${ou}[intent]    ShoppingCart-display

        ``intent`` n'est renseigné que si le fragment porte bien la forme
        ``SemanticObject-action`` (un fragment d'ancre ordinaire laisse
        ``None``, jamais une navigation FLP inventée), et ``intent_params``
        rend ses paramètres décodés.

        ``host`` est la partie qui compte pour un launchpad protégé : c'est
        elle qui distingue un fournisseur d'identité du site lui-même. Sans ce
        constat, une page de connexion servie par le site rendrait vert un
        test censé prouver la redirection (leçon live 2026-08-26, campagnes
        Work Zone). Lecture pure, aucune injection : cette adresse fait foi
        là où l'état servi par un serveur MCP peut être en retard d'une
        navigation par hash.

        ``url=`` décompose CETTE adresse au lieu de celle du navigateur
        (aucune page requise : la comparaison « l'hôte atteint diffère de
        celui du site » se calcule alors sans ``Evaluate __import__``, que la
        convention #12 proscrit dans la couche resources). ``base=`` résout
        d'abord ``url`` contre cette base (une adresse RELATIVE relevée dans
        la page redevient absolue avant décomposition) : ::

            ${site}=    Get Page Location    url=${WORKZONE_SITE}
            ${cible}=    Get Page Location    url=${href}    base=${WORKZONE_SITE}
        """
        if base is not None and url is None:
            raise ValueError(
                "Get Page Location: base= sans url= n'a pas de sens (base "
                "sert à résoudre une adresse relative fournie via url=).")
        if url is None:
            return parse_location(self._browser().get_url())
        target = urljoin(str(base), str(url)) if base is not None else str(url)
        return parse_location(target)

    def get_ushell_config(self, path=None):
        """Lit la **configuration ushell** de la page
        (``window['sap-ushell-config']``) en dict JSON-safe : la source la
        plus locale-indépendante d'un launchpad, qui DÉCLARE ce que le shell
        offre avant de le rendre (services, renderer, réglages de session).
        Relevé live (2026-08-26, site SAP Build Work Zone) : c'est elle qui
        dit que la recherche `searchCEPNew` est désactivée, que 24 services
        sont déclarés et que la session expire à 19 minutes, autant de faits
        qu'aucun contrôle rendu ne porte. ::

            ${cfg}=    Get Ushell Config
            ${to}=     Get Ushell Config    path=ushell.sessionTimeoutIntervalInMinutes

        ``path`` (pointé) descend dans la configuration ; un chemin absent =
        échec listant les clés disponibles au premier niveau, jamais un
        ``None`` muet. Page sans configuration ushell (pas un launchpad, ou
        portée de frame posée sur l'application au lieu du shell) = échec
        nommant les deux causes. **Lecture pure** : comme
        `Ui5 Runtime Is Present`, ce keyword n'injecte PAS le bundle
        ``__SAPFX``, donc n'instrumente rien dans la page observée. Les
        fonctions sont écartées de la sérialisation et un cycle d'objets est
        coupé (``<cycle>``)."""
        result = self._browser().evaluate_javascript(
            self._eval_scope(), USHELL_CONFIG_PROBE_JS,
            arg=str(path) if path else None)
        if isinstance(result, dict) and result.get("__no_config"):
            raise AssertionError(
                "Aucune configuration ushell (`window['sap-ushell-config']`) "
                "sur la portée courante : cette page n'est pas un launchpad, "
                "ou la portée de frame est posée sur l'application au lieu du "
                "shell (vérifier avec `Get Ui5 Frame Stack`, revenir au shell "
                "avec `Pop Ui5 Frame`).")
        if isinstance(result, dict) and "__missing_path" in result:
            known = result.get("__known_keys") or []
            raise AssertionError(
                "Chemin '%s' absent de la configuration ushell. Clés de "
                "premier niveau disponibles : %s. Explorer avec "
                "`Get Ushell Config` sans argument."
                % (result["__missing_path"],
                   ", ".join(str(k) for k in known) or "aucune"))
        return result

    def log_in_via_identity_provider(self, username, password: str | Secret,
                                     preset="sap-ias",
                                     username_selector=None,
                                     password_selector=None,
                                     submit_selector=None, timeout=None):
        """Déroule le formulaire de connexion d'un **fournisseur d'identité**
        (IDP) : le passage obligé d'un launchpad d'entreprise, qui redirige
        vers SAP IAS, Azure AD/Entra ou un IDP maison plutôt que d'afficher
        un login SAP classique.

        ``preset`` choisit la fiche de sélecteurs (``sap-ias``, défaut BTP,
        ``azure-ad``, ``generic``) ; chaque sélecteur reste surchargeable
        individuellement (IDP maison = ``generic`` + les trois sélecteurs).
        Gère les DEUX déroulés : une page (utilisateur + mot de passe
        ensemble) et deux étapes (utilisateur → Suivant → mot de passe →
        connexion), détectés dynamiquement. Échoue en nommant l'étape qui
        bloque (formulaire jamais apparu / mot de passe jamais proposé /
        formulaire toujours là après soumission = identifiants refusés ?).

        La valeur du mot de passe n'est pas journalisée par ce keyword ;
        ``password`` accepte aussi le type ``Secret`` de Robot Framework 7.4
        (``-v "IDP_PASSWORD: Secret:<motdepasse>"`` en ligne de commande) :
        la valeur est alors masquée partout, même en TRACE. À appeler après
        ``New Page <url du launchpad>`` ; enchaîner avec ``Wait For UI5
        Ready``."""
        idp = resolve_preset(preset, username_selector, password_selector,
                             submit_selector)
        browser = self._browser()
        budget = timestr_to_secs(timeout if timeout is not None else self.ui5_timeout)

        def _count(selector):
            # `>> visible=true` : ne compter que les éléments VISIBLES : un
            # formulaire deux-étapes garde son champ mot de passe caché dans le
            # DOM dès la première page (constaté sur la fixture IDP : compter
            # les éléments attachés fait prendre à tort la branche une-page).
            try:
                return int(browser.get_element_count(
                    "%s >> visible=true" % selector))
            except Exception:
                return 0

        if not poll_until(lambda: _count(idp.username_selector) > 0,
                          budget, step=self.poll_interval):
            raise AssertionError(
                "Formulaire IDP introuvable : aucun élément ne matche %r "
                "(preset %s). Mauvais preset, ou la page n'a pas redirigé "
                "vers l'IDP." % (idp.username_selector, idp.name))
        browser.fill_text(idp.username_selector, username)
        if _count(idp.password_selector):
            browser.fill_text(idp.password_selector, reveal_secret(password))
            browser.click(idp.submit_selector)
        else:
            # déroulé en deux étapes : utilisateur → « Suivant » → mot de passe
            browser.click(idp.submit_selector)
            if not poll_until(lambda: _count(idp.password_selector) > 0,
                              budget, step=self.poll_interval):
                raise AssertionError(
                    "Le champ mot de passe (%r) n'est jamais apparu après "
                    "l'étape utilisateur (preset %s) : utilisateur inconnu de "
                    "l'IDP, ou sélecteur à surcharger."
                    % (idp.password_selector, idp.name))
            browser.fill_text(idp.password_selector, reveal_secret(password))
            browser.click(idp.submit_selector)
        if not poll_until(lambda: _count(idp.username_selector) == 0,
                          budget, step=self.poll_interval):
            raise AssertionError(
                "Toujours sur le formulaire IDP (%s) après soumission : "
                "identifiants refusés, ou étape supplémentaire (MFA ?) non "
                "couverte par ce keyword." % idp.name)
        logger.info("IDP login (%s) submitted for user %s." % (idp.name, username))

    def lookup_business_term(self, term, domain=None, threshold=0.8):
        """Résout un **terme métier** (français ou anglais, synonymes compris)
        vers sa fiche SAP : canonique, champ ABAP, table, domaine::

            ${info}=    Lookup Business Term    fournisseur
            # -> {'canonical': 'vendor', 'abap_field': 'LIFNR', 'table': 'LFA1', ...}

        Vocabulaire partagé ECC↔Fiori (``sapfx_common.vocabulary`` : MM/SD/FI
        + modèle Flight de démo). Ambiguïté ou score sous ``threshold`` =
        échec listant les candidats, jamais de premier-match silencieux.
        ``domain`` (``MM``/``SD``/``FI``/``FLIGHT``) restreint la recherche.
        Dict JSON-safe (utilisable à travers rf-mcp)."""
        return lookup_as_dict(term, domain=domain, threshold=float(threshold))
