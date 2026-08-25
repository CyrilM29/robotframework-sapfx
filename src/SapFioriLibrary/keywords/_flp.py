"""Mixin launchpad, IDP et vocabulaire metier (ports de playwright-praman).

`Open Fiori App` (navigation FLP par **intent** ``SemanticObject-action`` :
le hash stable, cross-catalogue/theme/langue), `Log In Via Identity
Provider` (presets sap-ias/azure-ad/generic, une-page et deux-etapes
detectes dynamiquement, mot de passe jamais journalise) et
`Lookup Business Term` (le vocabulaire partage des trois canaux).

Concepts issus de playwright-praman (Apache-2.0, NOTICE), reimplementes sur
nos moteurs. Extrait de ``SapFioriLibrary.py`` (convention #13).
"""

from robot.api import logger
from robot.api.types import Secret
from robot.utils import timestr_to_secs

from sapfx_common.auth_flows import resolve_preset
from sapfx_common.polling import poll_until
from sapfx_common.secrets import reveal_secret
from sapfx_common.vocabulary import lookup_as_dict

from .._ui5_runtime import (
    build_intent_hash,
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
