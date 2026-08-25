"""Mixin perception : arbre UI5, carte numerotee ``@N``, canal visuel.

`Get Ui5 Page Tree` (``mode=diff`` : differentiel depuis la derniere
perception), la carte numerotee `Get Ui5 Page Map` +
`Resolve/Click/Fill Ui5 Ref` (references ephemeres re-verifiees au registre
rendu, pilotage interactif seulement), et la parite du canal visuel :
`Get Ui5 Perceptual Hash` / `Ui5 Screen Should Match Baseline` (meme cycle
snapshot que l'ECC via ``sapfx_common.visual_baseline``).

Extrait de ``SapFioriLibrary.py`` (convention #13).
"""

from robot.api import logger
from robot.utils import timestr_to_secs

from sapfx_common.perception_diff import diff_perception
from sapfx_common.polling import poll_until

from .._ui5_js import (
    DUMP_TREE_JS,
    RESOLVE_ROLE_JS,
)
from .._ui5_runtime import (
    build_control_selector,
    selector_to_json,
    ui5_page_map,
)




class PerceptionKeywords:
    """Mixin compose dans :class:`SapFioriLibrary` (voir ce module).
    Suppose la page active de Browser accessible via ``self._browser()``
    et la plomberie de ``_base.py`` disponible par composition."""

    def get_ui5_page_tree(self, mode="full"):
        """Retourne l'arbre des contrôles UI5 de la page courante, sérialisé en XML.

        Chaque nœud = un contrôle : balise = type court (``Button``), attributs =
        ``id``, ``controlType`` plein, et les propriétés primitives autorisées
        (``text``, ``value``…). C'est le pendant Fiori de `Get Screen Signature`
        (ECC) : une vue de l'écran qu'un agent IA (plugin rf-mcp) lit pour *voir*
        les contrôles disponibles avant d'en déduire un sélecteur role/xpath stable.

        ``mode=diff`` retourne le **différentiel** depuis l'appel précédent de ce
        keyword sur cette instance (balises ``- `` disparues / ``+ `` apparues,
        inchangé résumé) : après une action, « ce qui a changé » suffit à l'agent
        pour une fraction des tokens. Premier appel en diff : arbre complet.
        La page est TOUJOURS relue (jamais de cache) ; seul le rendu diffère.

        Lecture seule. Sonde jusqu'à ``ui5_timeout`` que le noyau UI5 soit prêt.
        Respecte `Set Ui5 Frame` (arbre de l'app embarquée, pas du shell).
        Lève une exception si la page n'est pas une application UI5."""
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
                "use), or Log Fiori Diagnostics for the full report.")
        previous = self._last_page_tree
        self._last_page_tree = tree
        if str(mode).strip().lower() == "diff":
            return diff_perception(previous, tree, xml=True)
        return tree

    # -- carte numérotée + action par référence (@N) ---------------------------
    # Miroir Fiori de Get Screen Map / Click Screen Ref (ECC) : le patron
    # « map / @e1 » agent-first (cf. Vibium) : la carte numérote les cibles
    # actionnables de l'arbre UI5, l'agent agit par numéro. Références
    # éphémères (dernière carte de l'instance), re-vérifiées avant chaque
    # action contre le registre UI5 rendu.

    def get_ui5_page_map(self, include_types=None):
        """Retourne la **carte numérotée** de la page UI5 courante : une ligne
        par cible actionnable : champs saisissables (``* ``, valeur courante
        affichée) et cibles cliquables, avec libellé humain (text/title/
        placeholder/tooltip, ``?`` à défaut), id de contrôle et type court ::

            # ui5 page map : 2 actionable target(s)
            @1\t* Search\tcontainer---app--searchField\tSearchField\t=
            @2\t  Go\tcontainer---app--goBtn\tButton

        Chaque numéro devient une **référence éphémère** pour `Resolve Ui5
        Ref`, `Click Ui5 Ref` et `Fill Ui5 Ref` : l'agent lit la carte puis
        agit par ``@N`` sans recopier l'id (la résolution re-vérifie que le
        contrôle est toujours rendu). ``include_types`` (types courts séparés
        par des virgules, ex. ``ColumnListItem,StandardListItem``) remplace la
        sélection par défaut, utile pour numéroter les lignes d'une liste.
        Respecte `Set Ui5 Frame`. Lecture seule ; ne touche pas la mémoire du
        ``mode=diff`` de `Get Ui5 Page Tree`. Dans une SUITE, rester sur les
        localisateurs de ``resources/`` (convention #1) : les ``@N`` sont
        réservés au pilotage interactif."""
        def _dump_tree():
            try:
                return self._evaluate(DUMP_TREE_JS, arg=None)
            except Exception:
                return None

        tree = poll_until(_dump_tree, timestr_to_secs(self.ui5_timeout),
                          step=self.poll_interval)
        if not tree:
            raise AssertionError(
                "No UI5 control tree on the current page (UI5 not ready, or "
                "not a UI5 app). No map to number. Call Get Page Composition "
                "to see which technologies this page hosts (and which "
                "engines/frames to use).")
        lines, refs = ui5_page_map(tree, include_types)
        self._ui5_refs = refs
        header = "# ui5 page map : %d actionable target(s)" % len(refs)
        return "\n".join([header] + lines)

    def _validate_ui5_ref(self, ref):
        """Valide une référence ``@N``/``N`` contre la dernière carte :
        échec IMMÉDIAT (hors budget de retry) si aucune carte n'a été relevée
        ou si le numéro est inconnu. Retourne ``(numéro, id de contrôle)``."""
        refs = getattr(self, "_ui5_refs", None)
        if not refs:
            raise AssertionError(
                "Aucune carte numérotée mémorisée : appeler d'abord "
                "Get Ui5 Page Map pour relever les références @N de la page.")
        number = str(ref).strip().lstrip("@")
        if number not in refs:
            raise AssertionError(
                "Référence @%s inconnue : la dernière carte expose @1..@%d "
                "(relever la carte à jour avec Get Ui5 Page Map)."
                % (number, len(refs)))
        return number, refs[number]

    def resolve_ui5_ref(self, ref):
        """Résout une référence ``@N`` de la dernière `Get Ui5 Page Map` en
        **sélecteur Browser** (``css=[id="…"]``, préfixé par la frame active),
        jamais en silence : échec actionnable si aucune carte n'a été
        relevée, si le numéro est inconnu, ou si le contrôle n'est plus rendu
        (page naviguée, vue redessinée ; le remède est nommé : re-percevoir
        avec `Get Ui5 Page Map`). Accepte ``3`` ou ``@3``."""
        number, control_id = self._validate_ui5_ref(ref)
        try:
            ids = self._evaluate(
                RESOLVE_ROLE_JS,
                arg=selector_to_json(build_control_selector(id=control_id))) or []
        except Exception:
            ids = []
        if not ids:
            raise AssertionError(
                "La cible @%s (%s) n'est plus rendue sur la page : "
                "re-percevoir avec Get Ui5 Page Map avant d'agir par "
                "référence." % (number, control_id))
        return self._scoped_selector('css=[id="%s"]' % control_id)

    def click_ui5_ref(self, ref):
        """Clique la cible ``@N`` de la dernière carte : résolution
        `Resolve Ui5 Ref` (fraîcheur re-vérifiée) puis clic Browser, avec la
        même absorption des *stale elements* que `Click Ui5 Control`
        (re-résolution à chaque tentative). Retourne le sélecteur cliqué
        (journalisé : la trace reste rejouable dans une suite)."""
        number, _control_id = self._validate_ui5_ref(ref)

        def _do():
            selector = self.resolve_ui5_ref(ref)
            self._browser().click(selector)
            return selector
        selector = self._act_with_retry(_do, "click ui5 ref @%s" % number)
        logger.info("Click Ui5 Ref @%s -> %s" % (number, selector))
        return selector

    def fill_ui5_ref(self, ref, text):
        """Saisit ``text`` dans la cible ``@N`` de la dernière carte : même
        chemin composite que `Fill Ui5 Input` (l'élément interne
        ``<input>``/``<textarea>`` du contrôle, jamais son ``<div>`` racine),
        fraîcheur re-vérifiée avant chaque tentative. Retourne le sélecteur
        du contrôle rempli. La valeur saisie n'est jamais un localisateur."""
        number, _control_id = self._validate_ui5_ref(ref)

        def _do():
            self.resolve_ui5_ref(ref)
            control_id = self._ui5_refs[number]
            attr = '[id="%s"]' % control_id
            self._browser().fill_text(
                self._scoped_selector("css=%s input, %s textarea"
                                      % (attr, attr)), text)
            return self._scoped_selector('css=[id="%s"]' % control_id)
        selector = self._act_with_retry(_do, "fill ui5 ref @%s" % number)
        logger.info("Fill Ui5 Ref @%s -> %s" % (number, selector))
        return selector

    # -- assertion visuelle (parité du canal ECC) -------------------------------

    def get_ui5_perceptual_hash(self, hash_size=8):
        """Capture la page courante (bibliothèque Browser) et retourne son
        **hash perceptuel** (dHash hexadécimal, ``hash_size²`` bits) : le
        pendant Fiori de `Get Screen Perceptual Hash` (ECC), même cœur pur
        ``sapfx_common.visual_hash``.

        Couvre ce que l'arbre UI5 ne dit pas : un canvas, une image, un
        thème/rendu globalement altéré. Nécessite Pillow (extra ``visual``)."""
        pixels = self._decode_image_to_gray(self._page_png())
        from sapfx_common.visual_hash import dhash_hex
        return dhash_hex(pixels, int(hash_size))

    def ui5_screen_should_match_baseline(self, name, threshold=5,
                                         baseline_directory="visual_baselines",
                                         hash_size=8, per_resolution=False):
        """Assertion de **non-régression visuelle** de la page Fiori courante,
        même sémantique *snapshot* que `Screen Should Match Baseline` (ECC),
        même module partagé (``sapfx_common.visual_baseline``) :

        * premier passage : la capture devient la baseline ``<name>.png``
          (WARNING journalisé, à committer si le rendu fait référence) ;
        * ensuite : distance de Hamming vs le hash recalculé depuis la
          baseline ; au-delà de ``threshold`` (défaut 5 sur 64 bits), échec
          auto-corrigible avec ``<name>.actual.png`` sauvé à côté.

        ``per_resolution=True`` garde **une baseline par géométrie de capture**
        (``<name>@1440x900.png``), miroir exact de l'option ECC : la taille de
        viewport fait partie de l'empreinte, donc deux postes (ou deux réglages
        de `New Browser`) comparent chacun à leur propre référence au lieu
        d'échouer sur une dérive d'échelle. Sans l'option, un échec dont les
        deux géométries diffèrent le **dit** dans son message.

        Retourne la distance mesurée (0 pour une baseline nouvellement créée)."""
        from sapfx_common.visual_baseline import (format_geometry,
                                                  match_baseline)
        outcome = match_baseline(name, self._page_png(),
                                 self._decode_image_to_gray,
                                 str(baseline_directory), int(threshold),
                                 int(hash_size), what="La page",
                                 per_resolution=per_resolution)
        where = ("" if outcome.geometry is None
                 else " en %s" % format_geometry(outcome.geometry))
        if outcome.created:
            logger.warn("Baseline visuelle créée (%s), premier passage%s : "
                        "committer ce PNG s'il fait référence."
                        % (outcome.baseline_path, where))
        else:
            logger.info("Conforme à la baseline%s (distance %d <= %d)."
                        % (where, outcome.distance, int(threshold)))
        return outcome.distance
