"""Mixin perception : arbre UI5 et fiche de controle.

`Get Ui5 Page Tree` (``mode=diff`` : differentiel depuis la derniere
perception) et la fiche d'un controle au registre (`Get Ui5 Control Info`,
`Get Ui5 Aggregation Info`, `Get Ui5 Control Metadata`).

Extrait de ``SapFioriLibrary.py`` (convention #13).
"""

import json
from typing import TYPE_CHECKING, Any, Literal

from robot.utils import timestr_to_secs

from sapfx_common.perception_diff import diff_perception
from sapfx_common.polling import poll_until

from .._ui5_js import (
    CONTROL_INFO_JS,
    CONTROL_METADATA_JS,
    DUMP_TREE_JS,
)
from .._ui5_runtime import (
    build_control_selector,
    selector_to_json,
)


class PerceptionKeywords:
    """Mixin compose dans :class:`SapFioriLibrary` (voir ce module).
    Suppose la page active de Browser accessible via ``self._browser()``
    et la plomberie de ``_base.py`` disponible par composition."""

    if TYPE_CHECKING:
        # Contrat du composite, pour mypy seulement : les
        # keywords annotés font vérifier leurs corps.
        def _act_with_retry(self, *args: Any, **kwargs: Any) -> Any: ...
        def _decode_image_to_gray(self, *args: Any, **kwargs: Any) -> Any: ...
        def _evaluate(self, *args: Any, **kwargs: Any) -> Any: ...
        def _page_png(self, *args: Any, **kwargs: Any) -> Any: ...
        def _relaxed_hint(self, *args: Any, **kwargs: Any) -> Any: ...
        def _scoped_selector(self, *args: Any, **kwargs: Any) -> Any: ...
        poll_interval: Any
        ui5_timeout: Any
        _last_page_tree: Any

    def get_ui5_page_tree(self, mode: Literal["full", "diff"] = "full"):
        """Retourne l'arbre des contrôles UI5 de la page courante, sérialisé en XML.

        Chaque nœud = un contrôle : balise = type court (``Button``), attributs =
        ``id``, ``controlType`` plein, et les propriétés primitives autorisées
        (``text``, ``value`` …). C'est le pendant Fiori de `Get Screen Signature`
        (ECC) : une vue de l'écran qu'un agent IA (plugin rf-mcp) lit pour *voir*
        les contrôles disponibles avant d'en déduire un sélecteur role/xpath stable.

        ``mode=diff`` retourne le *différentiel* depuis l'appel précédent de ce
        keyword sur cette instance (balises ``- `` disparues / ``+ `` apparues,
        inchangé résumé) : après une action, « ce qui a changé » suffit à l'agent
        pour une fraction des tokens. Premier appel en diff : arbre complet.
        La page est TOUJOURS relue (jamais de cache) ; seul le rendu diffère.

        Lecture seule. Sonde jusqu'à ``ui5_timeout`` que le noyau UI5 soit prêt.
        Respecte `Set Ui5 Frame` (arbre de l'app embarquée, pas du shell).
        Lève une exception si la page n'est pas une application UI5.

        Exemple :
        | ${tree}=    `Get Ui5 Page Tree`
        | Should Contain    ${tree}    sap.m.Table
        | ${changes}=    `Get Ui5 Page Tree`    mode=diff
        """
        def _dump_tree():
            try:
                return self._evaluate(DUMP_TREE_JS, arg=None)
            except Exception:
                # transitoire pendant un re-rendu (ex. navigation par hash) : le
                # sondage doit continuer, pas s'interrompre sur la première erreur.
                return None

        tree = poll_until(_dump_tree, timestr_to_secs(self.ui5_timeout), step=self.poll_interval)
        if not tree:
            raise AssertionError(
                "No UI5 control tree on the current page (UI5 not ready, or "
                "not a UI5 app). Call Get Page Composition to see which "
                "technologies this page hosts (and which engines/frames to "
                "use).")
        previous = self._last_page_tree
        self._last_page_tree = tree
        if str(mode).strip().lower() == "diff":
            return diff_perception(previous, tree, xml=True)
        return tree

    # -- fiche de contrôle : type, propriétés, contexte de liaison --------------

    def _control_info(self, selector_parts, aggregation=None, index=None,
                      model=None):
        """Appelle ``controlInfo`` du bundle et traduit ``null`` (pas de
        runtime UI5) en échec actionnable, commun aux deux keywords."""
        payload = {"selector": json.loads(
            selector_to_json(build_control_selector(**selector_parts)))}
        if aggregation is not None:
            payload["aggregation"] = str(aggregation)
            payload["index"] = int(index or 0)
        if model:
            payload["model"] = str(model)
        result = self._evaluate(CONTROL_INFO_JS, arg=json.dumps(payload))
        if result is None:
            raise AssertionError(
                "Aucun runtime UI5 sur la portée courante : impossible de "
                "lire la fiche des contrôles. Sonder d'abord avec `Ui5 "
                "Runtime Is Present`, et vérifier la portée de frame avec "
                "`Get Ui5 Frame Stack`.")
        return result

    def get_ui5_control_info(self, model=None, **selector_parts):
        """Fiche JSON-safe de CHAQUE contrôle *rendu* qui matche le
        sélecteur (mêmes clés que `Resolve Ui5 Control`) : liste de dicts
        ``{id, type, rendered, properties, property_keys, binding}``.

        ``type`` est le nom PLEIN de métadonnées (``sap.m.Avatar``) : la
        lecture qui prouve la TECHNOLOGIE d'un contrôle, là où l'arbre de
        `Get Ui5 Page Tree` n'en donne que la forme courte. ``binding`` porte
        le *contexte de liaison* (``{path, object, object_keys}``, ``None``
        sans contexte ; ``model=`` en vise un nommé) : la voie des items dont
        l'identifiant est GÉNÉRÉ mais dont la clé technique vit dans le
        modèle (rubriques de paramètres d'un shell, thèmes : relevés live
        2026-08-24/26 sur deux launchpads). ``object`` est réduit aux entrées
        primitives de premier niveau (les valeurs profondes portent des
        contrôles et des cycles) ; ``object_keys`` liste tout ce qui existe.
        Même contrat côté propriétés : ``properties`` ne porte que les valeurs
        primitives, et ``property_keys`` liste TOUTES les propriétés lues,
        y compris celles dont la valeur est un tableau (``fieldGroupIds``) :
        la réduction s'annonce, elle ne se devine pas. Pour l'inventaire
        DÉCLARÉ (types, défauts, provenance), voir `Get Ui5 Control Metadata`.

        Lecture, pas assertion : aucune correspondance rend une liste vide.
        N'attend pas le rendu (percevoir d'abord, cf. `Get Ui5 Page Tree`).

        Exemple :
        | ${info}=    `Get Ui5 Control Info`    idSuffix=fe::table::Travel::LineItem-innerTable
        | Should Be Equal    ${info}[0][type]    sap.m.Table
        """
        return list(self._control_info(selector_parts, model=model) or [])

    def get_ui5_aggregation_info(self, aggregation, index: int = 0, model=None,
                                 **selector_parts):
        """Fiche JSON-safe des *enfants d'une agrégation* du contrôle
        résolu (``index``, base 0) : liste de dicts ``{id, type, rendered,
        properties, binding}``, rendus OU NON.

        C'est ce que le moteur role ne peut pas voir : les items d'un
        ``Select`` n'existent pas dans le DOM tant que son popover est fermé,
        et les items réservés d'une liste restent non rendus ; ils sont
        pourtant DÉCLARÉS dans l'agrégation, avec leur clé, leur contexte de
        liaison et leur position. ``rendered`` distingue les deux
        populations.

        Agrégation inconnue du contrôle = échec la nommant ; agrégation
        déclarée mais vide = liste vide (les deux cas restent distincts).
        Sélecteur sans correspondance = échec (il faut UN contrôle hôte).

        Exemple :
        | ${columns}=    `Get Ui5 Aggregation Info`    columns    idSuffix=fe::table::Travel::LineItem-innerTable
        | Should Be Equal    ${columns}[0][type]    sap.m.Column
        """
        result = self._control_info(selector_parts, aggregation=aggregation,
                                    index=index, model=model)
        if isinstance(result, dict) and "__out_of_range" in result:
            matched = int(result["__out_of_range"] or 0)
            if matched == 0:
                raise AssertionError(
                    "No UI5 control matched %s on the current page.%s"
                    % (selector_parts, self._relaxed_hint(selector_parts)))
            raise AssertionError(
                "%s matched %d control(s); index %s is out of range."
                % (selector_parts, matched, index))
        if isinstance(result, dict) and "__no_aggregation" in result:
            raise AssertionError(
                "Le contrôle résolu ne déclare pas d'agrégation '%s' : "
                "vérifier son type avec `Get Ui5 Control Info` (les listes "
                "portent `items`, les tables `rows`/`items` selon la "
                "famille)." % result["__no_aggregation"])
        return list(result or [])

    def get_ui5_control_metadata(self, **selector_parts):
        """Inventaire de *MÉTADONNÉES* de chaque contrôle qui matche le
        sélecteur (mêmes clés que `Resolve Ui5 Control`) : le contrat DÉCLARÉ
        par la classe, indépendant des valeurs courantes. Liste de dicts
        ``{id, type, lineage, properties, aggregations, associations,
        events}``.

        Le complément de `Get Ui5 Control Info`, pas son doublon : la fiche
        porte les VALEURS (réduites aux primitives), cet inventaire porte la
        DÉCLARATION. Chaque membre est décrit par ``{borrowed, origin}``
        (provenance : ``borrowed=False`` = déclaré par la classe elle-même,
        ``origin`` = la classe qui le déclare), plus ``type`` et ``default``
        (JSON-safe, un tableau reste un tableau) pour les propriétés, ``type``
        et ``multiple`` pour agrégations et associations. ``lineage`` est la
        chaîne d'héritage complète (de la classe au socle).

        C'est la lecture qui permet de confronter une documentation d'API au
        contrôle VIVANT : relevé 2026-09-05 sur le Demo Kit, la fiche réduite
        aux primitives rendait 17 clés là où la doc de ``sap.m.Button`` en
        documente 18 (``fieldGroupIds``, valeur tableau), et la notion
        « borrowed » de la doc correspond exactement à ``borrowed`` ici.

        Lecture, pas assertion : aucune correspondance rend une liste vide.
        N'attend pas le rendu (percevoir d'abord, cf. `Get Ui5 Page Tree`).

        Exemple :
        | ${metadata}=    `Get Ui5 Control Metadata`    idSuffix=fe::table::Travel::LineItem-innerTable
        | Should Be Equal    ${metadata}[0][properties][growingThreshold][type]    int
        """
        payload = {"selector": json.loads(
            selector_to_json(build_control_selector(**selector_parts)))}
        result = self._evaluate(CONTROL_METADATA_JS, arg=json.dumps(payload))
        if result is None:
            raise AssertionError(
                "Aucun runtime UI5 sur la portée courante : impossible de "
                "lire l'inventaire de métadonnées. Sonder d'abord avec `Ui5 "
                "Runtime Is Present`, et vérifier la portée de frame avec "
                "`Get Ui5 Frame Stack`.")
        return list(result or [])

    # -- assertion visuelle (parité du canal ECC) -------------------------------


