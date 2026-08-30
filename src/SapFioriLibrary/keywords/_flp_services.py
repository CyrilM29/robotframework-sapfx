"""Mixin services launchpad (ushell) : catalogue, groupes, intents, compte.

Les lectures des SERVICES d'un launchpad (`sap.ushell.Container`) : `Get Flp
User`, `List Flp Apps` (SearchableContent), `List Flp Catalogs` / `List Flp
Groups` (LaunchPage), `Get Flp Intent Support` (CrossApplicationNavigation),
plus les deux prédicats `Flp Container Is Present` et `Flp Service Is
Available`. Toutes sont des lectures PURES (aucune injection du bundle,
comme `Get Ushell Config`) : une observation ne modifie rien.

Promues de page objects où le même JS inline vivait en double (convention
#12 : une capacité générique n'a rien à faire dans la couche métier).
Extrait au format des autres mixins (convention #13).
"""

import json

from .._ui5_js import (
    FLP_APPS_PROBE_JS,
    FLP_CATALOGS_PROBE_JS,
    FLP_CONTAINER_PROBE_JS,
    FLP_GROUPS_PROBE_JS,
    FLP_INTENT_SUPPORT_PROBE_JS,
    FLP_SERVICE_PROBE_JS,
    FLP_USER_PROBE_JS,
)

from sapfx_common.robot_args import as_name_list


class FlpServiceKeywords:
    """Mixin compose dans :class:`SapFioriLibrary` (voir ce module).
    Suppose la page active de Browser accessible via ``self._browser()``
    et la plomberie de ``_base.py`` disponible par composition."""

    def _flp_result(self, result, service=None):
        """Traduit les sentinelles des sondes ushell en échec actionnable."""
        if isinstance(result, dict) and result.get("__no_container"):
            raise AssertionError(
                "Aucun conteneur ushell (`sap.ushell.Container`) sur la "
                "portée courante : cette page n'est pas un launchpad, ou la "
                "portée de frame est posée sur l'application au lieu du "
                "shell (vérifier avec `Get Ui5 Frame Stack`, revenir au "
                "shell avec `Pop Ui5 Frame`). `Flp Container Is Present` "
                "répond sans échouer.")
        if isinstance(result, dict) and "__no_service" in result:
            raise AssertionError(
                "Le service ushell '%s' n'est pas disponible sur ce "
                "launchpad (%s). Certains services n'existent que sur les "
                "ushell récents (SearchableContent est absent en 1.71, son "
                "module répond 404) : brancher avec `Flp Service Is "
                "Available` avant d'en dépendre."
                % (service or "?", result.get("__no_service") or "cause inconnue"))
        return result

    def flp_container_is_present(self):
        """Y a-t-il un **conteneur ushell** (`sap.ushell.Container`) dans la
        portée courante ? Retourne ``True``/``False``, jamais d'échec : une
        page injoignable répond ``False``.

        C'est la première marche d'attente d'un launchpad : le conteneur est
        présent bien avant que la page soit au repos, donc « conteneur là »
        puis « shell rendu » sont deux attentes distinctes. Lecture pure,
        aucune injection (même contrat que `Ui5 Runtime Is Present`). ::

            Wait Until Keyword Succeeds    60s    1s    Flp Container Should Be Present
        """
        try:
            return bool(self._evaluate(FLP_CONTAINER_PROBE_JS))
        except Exception:      # noqa: BLE001 (sonde : jamais d'échec)
            return False

    def flp_container_should_be_present(self):
        """Assertion : le conteneur ushell est là. La forme à sonder dans un
        ``Wait Until Keyword Succeeds`` (le prédicat `Flp Container Is
        Present`, lui, ne peut pas servir de condition d'attente seul)."""
        if not self.flp_container_is_present():
            raise AssertionError(
                "Aucun conteneur ushell (`sap.ushell.Container`) sur la "
                "portée courante : pas (encore) un launchpad chargé, ou "
                "portée de frame posée sur l'application (`Get Ui5 Frame "
                "Stack`).")

    def flp_service_is_available(self, service):
        """Le **service ushell** nommé existe-t-il sur ce launchpad ?
        Retourne ``True``/``False``, jamais d'échec : c'est un prédicat de
        branchement, pas une assertion, et il vaut mieux qu'un test de
        version (qui supposerait ce que la sonde mesure). Relevé live :
        ``SearchableContent`` est absent du ushell 1.71 (module 404) et
        présent en 1.120 comme une façade sur ``LaunchPage``. ::

            ${dispo}=    Flp Service Is Available    SearchableContent
            IF    ${dispo}    ${apps}=    List Flp Apps
        """
        try:
            return bool(self._evaluate(FLP_SERVICE_PROBE_JS,
                                       arg=str(service)))
        except Exception:      # noqa: BLE001 (sonde : jamais d'échec)
            return False

    def get_flp_user(self):
        """Identité de l'utilisateur du launchpad, lue au conteneur ushell :
        dict JSON-safe ``{id, language, theme}``. Les trois valeurs
        TECHNIQUES qui permettent de prouver qu'un parcours n'a rien modifié
        (relevé live 2026-08-26, campagne zone utilisateur Work Zone).
        Conteneur absent = échec actionnable nommant la portée de frame et
        `Flp Container Is Present`."""
        return self._flp_result(self._evaluate(FLP_USER_PROBE_JS))

    def list_flp_apps(self):
        """Inventaire des applications du launchpad par le service
        **SearchableContent** : ce que l'utilisateur a le DROIT d'ouvrir, et
        non ce que la page affiche. Liste de dicts JSON-safe ``{title,
        viz_title, intent, target_url}`` (``intent`` = le hash sans ``#`` ni
        paramètres, la clé stable ; ``viz_title`` = le titre porté par la
        visualisation quand il diffère du libellé de l'app). Service absent
        (ushell 1.71) = échec actionnable nommant `Flp Service Is Available` ;
        sur ce ushell-là, passer par `List Flp Catalogs` (LaunchPage)."""
        return self._flp_result(self._evaluate(FLP_APPS_PROBE_JS),
                                service="SearchableContent") or []

    def list_flp_catalogs(self, include_tiles=True):
        """Catalogues assignés à l'utilisateur, lus au service **LaunchPage**
        (le ushell classique ABAP) : liste de dicts ``{id, tiles}`` où
        ``tiles`` est ``[{intent, target_url}]``. C'est le catalogue de
        DROITS, pas le rendu de la page. ``include_tiles=False`` saute la
        lecture des tuiles (un aller-retour par catalogue en moins quand
        seuls les ids comptent). Les résultats de l'adaptateur ABAP arrivent
        en ``progress`` : les deux formes de réponse sont acceptées."""
        include = str(include_tiles).strip().lower() not in ("false", "no", "0", "")
        return self._flp_result(
            self._evaluate(FLP_CATALOGS_PROBE_JS,
                           arg="tiles" if include else "no_tiles"),
            service="LaunchPage") or []

    def list_flp_groups(self):
        """Groupes de l'accueil du launchpad et volume de chacun (service
        **LaunchPage**) : liste de dicts ``{id, tile_count}``. Même source de
        vérité que `List Flp Catalogs` (droits, pas rendu)."""
        return self._flp_result(self._evaluate(FLP_GROUPS_PROBE_JS),
                                service="LaunchPage") or []

    def get_flp_intent_support(self, intents):
        """Résolvabilité d'une LISTE d'intents en un aller-retour, par le
        service **CrossApplicationNavigation** (``isIntentSupported``) :
        liste de dicts ``{intent, supported}`` dans l'ordre donné. ``intents``
        accepte une liste, une chaîne à virgules ou une liste-littérale
        (frontière rf-mcp : tout arrive en chaîne). Un intent assigné mais
        non ouvrable est un ÉCART légitime à rapporter, pas une erreur :
        c'est l'appelant qui juge. ::

            ${verdicts}=    Get Flp Intent Support    ${intents}
            ${non_resolus}=    Evaluate    [v['intent'] for v in $verdicts if not v['supported']]
        """
        wanted = as_name_list(intents, argument="intents")
        return self._flp_result(
            self._evaluate(FLP_INTENT_SUPPORT_PROBE_JS,
                           arg=json.dumps(wanted)),
            service="CrossApplicationNavigation") or []
