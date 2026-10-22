"""Mixin du mode *Espaces et Pages* d'un launchpad et de l'histogramme des
types de contrôles rendus (fiche scénario 14, 2026-10-13).

`Get Flp Menu State` lit l'état EFFECTIF du shell (service ``Menu``),
`Get Ui5 Control Types` l'histogramme des types PLEINS rendus, et
`Get Flp Spaces Mode` / `Flp Spaces Mode Should Be` croisent ces deux
lectures avec la configuration DÉCLARÉE. Toutes sont des lectures pures : le
bundle ``__SAPFX`` n'est pas injecté. La règle vit dans
``sapfx_common.flp_spaces``, les sondes dans ``_flp_spaces_js``.
"""

import json

from sapfx_common import flp_spaces
from sapfx_common.robot_args import OptionalNameListInput, as_name_list

from .._flp_spaces_js import (
    FLP_MENU_STATE_PROBE_JS,
    PAGE_HASH_PROBE_JS,
    UI5_CONTROL_TYPES_PROBE_JS,
)
from .._ui5_js import USHELL_CONFIG_PROBE_JS


class FlpSpacesKeywords:
    """Mixin composé dans :class:`SapFioriLibrary` (voir ce module). Suppose
    ``self._evaluate`` et ``self._flp_result`` disponibles par composition."""

    def get_flp_menu_state(self):
        """État EFFECTIF du mode Espaces et Pages, lu au service *Menu* du
        conteneur ushell : dict JSON-safe ``{available, menu_enabled,
        entries, spaces, default_space, my_home_space, show_my_home,
        errors}``. ``spaces`` est la hiérarchie des espaces affectés à
        l'utilisateur (``[{id, title, pages: [{id, title}]}]``), ``entries``
        le nombre d'entrées du menu des espaces.

        C'est ce que le shell a DÉCIDÉ avant de rendre, là où la
        configuration (`Get Ushell Config`) dit ce qui est DÉCLARÉ : mesuré
        sur ABAP Platform 2023, la configuration porte
        ``ushell.spaces.myHome.enabled = true`` et ce service répond
        ``menu_enabled = False``, zéro entrée, ``spaces = []``. Une méthode
        absente ou qui lève est nommée dans ``errors`` et sa valeur reste
        ``None``, jamais remplacée par une valeur plausible. Conteneur ou
        service absent = échec actionnable. Lecture pure. Limite dite : sur
        un système actif, ``menu_enabled`` vrai est une hypothèse SAP
        générale, jamais observée sur le banc (le mode n'y est pas actif).

        Exemple :
        | ${menu}=    `Get Flp Menu State`
        | Should Not Be True    ${menu}[menu_enabled]
        | Should Be Equal As Integers    ${menu}[entries]    0
        """
        return self._flp_result(self._evaluate(FLP_MENU_STATE_PROBE_JS),
                                service="Menu")

    def get_ui5_control_types(self, namespace=None, container_id=None):
        """Histogramme des *types PLEINS* des contrôles UI5 RENDUS (nœud DOM
        présent) : dict ``{type: nombre}``, trié par type. ``namespace``
        restreint aux types qui commencent par ce préfixe
        (``sap.ushell.``) ; ``container_id`` aux contrôles rendus DANS le
        nœud DOM de cet identifiant (descendants stricts).

        C'est l'inventaire d'un écran par classe : là où ``Get Ui5 Match
        Count    controlType=…`` répond pour UN type nommé, ce keyword rend
        tous les types rendus en un appel, sans rien supposer de leurs noms.
        Un contrôle dont la lecture lève fait échouer le keyword en le
        comptant, jamais un histogramme amputé en silence. Pas de runtime
        UI5 ou conteneur absent = échec qui le dit. Lecture pure, sans
        bundle.

        Exemple :
        | ${types}=    `Get Ui5 Control Types`    namespace=sap.ushell.
        | Should Be Equal As Integers    ${types}[sap.ushell.ui.launchpad.TileContainer]    2
        | Dictionary Should Not Contain Key    ${types}    sap.ushell.ui.launchpad.Section
        """
        opts = {"namespace": str(namespace) if namespace else "",
                "container_id": str(container_id) if container_id else ""}
        result = self._evaluate(UI5_CONTROL_TYPES_PROBE_JS, arg=json.dumps(opts))
        if not isinstance(result, dict) or result.get("__no_runtime"):
            raise AssertionError(
                "Aucun runtime UI5 sur la portée courante : pas de types de "
                "contrôles à compter (vérifier `Ui5 Runtime Is Present` et la "
                "portée de frame avec `Get Ui5 Frame Stack`).")
        if result.get("errors"):
            raise AssertionError(
                "%d contrôle(s) rendu(s) illisible(s) pendant l'inventaire des "
                "types : l'histogramme serait amputé, il n'est pas rendu."
                % int(result["errors"]))
        if "__no_container" in result:
            raise AssertionError(
                "Conteneur '%s' absent du DOM : aucun périmètre à compter, "
                "jamais un périmètre élargi à toute la page."
                % result["__no_container"])
        types = result.get("types") or {}
        return {k: int(types[k]) for k in sorted(types)}

    def get_flp_spaces_mode(self, ignored_keys: OptionalNameListInput = None):
        """Le mode *Espaces et Pages* du launchpad, établi par TROIS lectures
        de natures différentes : la configuration déclarée
        (``ushell.spaces``), l'état effectif du service *Menu* et les types
        pleins de l'accueil rendu. Rend un verdict JSON-safe ``{state,
        declared, effective, rendered, reasons}`` où ``state`` vaut
        ``active``, ``inactive``, ``unreadable`` (une lecture impossible,
        jamais « inactif » faute d'avoir pu lire) ou ``inconsistent`` (deux
        lectures lisibles qui divergent). Ne fait jamais échouer : c'est
        `Flp Spaces Mode Should Be` qui juge.

        Le piège qui justifie trois lectures, mesuré sur ABAP Platform
        2023 : ``ushell.spaces.myHome.enabled`` vaut vrai alors que le mode
        est inactif. Seule ``enabled`` décide côté configuration ; toute
        autre clé sous ``ushell.spaces`` rend la lecture illisible en la
        nommant, sauf celles de l'argument ``ignored_keys`` (défaut
        ``myHome``, liste ou chaîne à virgules), mesurées sans effet.
        L'accueil se lit après la construction du shell, et SUR l'accueil :
        appelé trop tôt, ou depuis l'App Finder ou une application (fragment
        autre que l'intent racine de la configuration, ``Shell-home`` à
        défaut), ``rendered`` est illisible et le verdict aussi, jamais
        « inactif ». Une rubrique ``ushell.spaces`` absente vaut « inactif »
        côté déclaré : ce n'est concluant qu'avec les deux autres lectures.

        Exemple :
        | ${mode}=    `Get Flp Spaces Mode`
        | Should Be Equal    ${mode}[state]    inactive
        | Should Be Equal    ${mode}[declared][state]    inactive
        """
        ignored = (as_name_list(ignored_keys, argument="ignored_keys")
                   if ignored_keys else list(flp_spaces.DEFAULT_IGNORED_KEYS))
        declared = self._read_declared_spaces(ignored)
        try:
            menu = self.get_flp_menu_state()
        except AssertionError as error:
            menu = {"available": False, "errors": [str(error)]}
        try:
            types = self.get_ui5_control_types()
        except AssertionError:
            types = {}
        location, on_home = self._read_home_location()
        return flp_spaces.classify_spaces_mode(
            declared, flp_spaces.classify_effective(menu),
            flp_spaces.classify_rendered(types, on_home=on_home, location=location))

    def flp_spaces_mode_should_be(self, expected, ignored_keys: OptionalNameListInput = None):
        """Assertion : le mode *Espaces et Pages* établi par `Get Flp Spaces
        Mode` vaut ``expected`` (``active`` ou ``inactive``), les trois
        lectures concordant. Une lecture illisible ou une divergence échoue
        en nommant les trois lectures, jamais un succès vide. Rend le
        verdict.

        Exemple :
        | ${mode}=    `Flp Spaces Mode Should Be`    inactive
        | Should Be Equal As Integers    ${mode}[rendered][sections]    0
        """
        wanted = str(expected).strip().lower()
        if wanted not in (flp_spaces.ACTIVE, flp_spaces.INACTIVE):
            raise ValueError("expected vaut 'active' ou 'inactive', pas '%s'." % expected)
        verdict = self.get_flp_spaces_mode(ignored_keys=ignored_keys)
        if verdict["state"] != wanted:
            raise AssertionError("Attendu %s, constaté %s." % (
                wanted, flp_spaces.describe_spaces_mode(verdict)))
        return verdict

    def _read_home_location(self):
        """Fragment courant et réponse à « est-ce l'accueil ? », l'intent
        racine étant lu dans la configuration (``Shell-home`` à défaut)."""
        try:
            location = str(self._evaluate(PAGE_HASH_PROBE_JS) or "")
        except Exception:      # noqa: BLE001 (lecture : jamais d'échec ici)
            return "?", False
        root = None
        try:
            root = self._evaluate(USHELL_CONFIG_PROBE_JS,
                                  arg="renderers.fiori2.componentData.config.rootIntent")
        except Exception:      # noqa: BLE001
            root = None
        if not isinstance(root, str) or not root:
            root = flp_spaces.DEFAULT_ROOT_INTENT
        return location, flp_spaces.is_home_hash(location, root)

    def _read_declared_spaces(self, ignored):
        """Lit ``ushell.spaces`` sans échouer et le classe."""
        try:
            raw = self._evaluate(USHELL_CONFIG_PROBE_JS, arg="ushell.spaces")
        except Exception as error:      # noqa: BLE001 (lecture : jamais d'échec ici)
            return {"state": flp_spaces.UNREADABLE,
                    "reason": "configuration illisible : %s" % error}
        if isinstance(raw, dict) and raw.get("__no_config"):
            return flp_spaces.classify_declared(None, config_present=False)
        if isinstance(raw, dict) and "__missing_path" in raw:
            return flp_spaces.classify_declared(None, ignored_keys=ignored)
        return flp_spaces.classify_declared(raw, ignored_keys=ignored)
