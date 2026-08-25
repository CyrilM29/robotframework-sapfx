"""Mixin perception des pages hybrides et diagnostic agrege.

`Get Page Composition` (quelles technologies cohabitent ou : runtime
UI5/WC/lsdata/frameworks + moteurs recommandes par region, descente d'un
niveau dans chaque iframe, best-effort) et `Get/Log Fiori Diagnostics`
(UN dict JSON-safe : composition + arbre UI5 sonde + erreurs console/page
normalisees + snapshot ARIA, chaque section best-effort, synthese ``issues``
actionnable ; coeur pur dans ``sapfx_common.fiori_diagnostics``).

Extrait de ``SapFioriLibrary.py`` (convention #13).
"""

from robot.api import logger
from robot.utils import timestr_to_secs

from sapfx_common.fiori_diagnostics import (
    normalize_console_entries,
    normalize_page_errors,
    parse_sections,
    render_diagnostics_report,
    summarize_issues,
    tail_entries,
)
from sapfx_common.polling import poll_until

from .._ui5_js import (
    DUMP_TREE_JS,
    PAGE_COMPOSITION_JS,
)
from .._ui5_runtime import (
    recommended_engines,
)




class CompositionKeywords:
    """Mixin compose dans :class:`SapFioriLibrary` (voir ce module).
    Suppose la page active de Browser accessible via ``self._browser()``
    et la plomberie de ``_base.py`` disponible par composition."""

    # -- sonde de composition (perception des pages hybrides) ------------------

    def get_page_composition(self, include_frames=True):
        """Sonde la **composition technologique** de la page courante : la
        perception d'une page HYBRIDE (shell UI5 + iframe WebGUI + widget web
        générique cohabitant dans le même écran).

        Retourne un dict JSON-safe (utilisable à travers rf-mcp) :

        * ``ui5_runtime`` / ``ui5_version`` / ``ui5_controls`` : runtime UI5
          classique présent (moteurs *role*/*xpath* utilisables) ;
        * ``wc_hosts`` : hôtes UI5 Web Components (moteur *wc*) ;
        * ``webgui_elements`` : éléments ``lsdata`` SAP GUI for HTML (moteur *sid*) ;
        * ``frameworks`` : indices React/Angular/Vue (moteur *dom*) ;
        * ``engines`` : les moteurs recommandés pour CETTE région, dans
          l'ordre d'essai de `Resolve Ui5 With Fallback` ;
        * ``frames`` : chaque iframe du document avec son sélecteur Browser
          réutilisable (`Set Ui5 Frame` / `Push Ui5 Frame`) et, si
          ``include_frames`` (défaut), SA composition sondée à son tour
          (champ ``composition``). C'est là que l'hybridation se voit : un
          launchpad Work Zone rapporte un shell sans contrôles et une app
          UI5 par frame. Une frame insondable porte un champ ``error`` au
          lieu de faire échouer la perception (best-effort). La descente
          fait UN niveau : pour aller plus profond, `Push Ui5 Frame` puis
          re-sonder.

        Respecte `Set Ui5 Frame` / `Push Ui5 Frame` : la sonde part de la
        portée courante. Lecture seule, le pendant hybride de `Get Ui5 Page
        Tree`, à appeler en premier sur un écran inconnu pour savoir QUEL
        moteur adresser où."""
        composition = self._evaluate(PAGE_COMPOSITION_JS, arg=None)
        if not isinstance(composition, dict):
            raise AssertionError(
                "Could not probe the page composition (no document?). "
                "Is a page open in the Browser library?")
        composition["engines"] = recommended_engines(composition)
        if include_frames:
            for frame in composition.get("frames", []):
                frame_scope = self._scoped_selector(frame["selector"])
                try:
                    sub = self._browser().evaluate_javascript(
                        "%s >>> css=body" % frame_scope,
                        PAGE_COMPOSITION_JS, arg=None)
                    if isinstance(sub, dict):
                        sub["engines"] = recommended_engines(sub)
                        frame["composition"] = sub
                    else:
                        frame["error"] = "frame document not probeable"
                except Exception as err:
                    frame["error"] = str(err)
        return composition

    # -- diagnostic agrégé (inspiré des briques Browser 20) --------------------

    def get_fiori_diagnostics(self, sections="composition,tree,console,errors,aria",
                              tree_timeout="3s", full_logs=False,
                              max_log_entries=50, aria_selector="css=body"):
        """Agrège en UN dict JSON-safe les vues de diagnostic de la page
        courante : la perception « pourquoi ça ne marche pas » d'un écran
        Fiori/hybride, pensée pour rf-mcp et le débogage de suite :

        * ``composition`` : la sonde `Get Page Composition` (technologies par
          région + moteurs recommandés + iframes) ;
        * ``ui5_tree`` : l'arbre de contrôles UI5 (XML, portée courante),
          sondé pendant ``tree_timeout`` seulement (défaut 3s : un diagnostic
          sur une page non-UI5 ne doit pas bloquer ``ui5_timeout`` entier) ;
          ``None`` si absent, ce qui devient une anomalie NOMMANT les
          moteurs/frames de repli. Ne touche PAS l'état ``mode=diff`` de
          `Get Ui5 Page Tree` ;
        * ``console`` / ``page_errors`` : `Get Console Log` / `Get Page
          Errors` de Browser 20, normalisés en dicts à forme stable
          ``{type, text, location, time}`` / ``{name, message, stack, time}``.
          Par défaut (``full_logs=False``, la sémantique Browser), chaque
          appel ne retourne que les entrées NOUVELLES depuis le précédent,
          l'esprit ``mode=diff`` ; ``full_logs=True`` relit tout. Les listes
          gardent les ``max_log_entries`` plus récentes (troncature annoncée
          dans ``console_dropped``/``page_errors_dropped``, jamais
          silencieuse) ;
        * ``aria`` : snapshot ARIA YAML (`Get Aria Snapshot`) de
          ``aria_selector`` (défaut ``css=body``, préfixé par la frame
          courante) : la vue sémantique des zones NON-SAP qu'aucun moteur ne
          modélise ;
        * ``issues`` : la synthèse actionnable, erreurs JS/console comptées
          (première citée), arbre UI5 absent avec les moteurs recommandés à
          la place, sections insondables.

        ``sections`` (chaîne ``a,b,c`` ou liste) restreint la collecte ;
        section inconnue = erreur listant les valides. Chaque section est
        best-effort : une collecte qui échoue est consignée dans
        ``collection_errors`` (et dans ``issues``) au lieu de faire échouer
        le diagnostic. Lecture seule. Respecte `Set Ui5 Frame` /
        `Push Ui5 Frame` (composition, arbre et ARIA sondent la portée
        courante ; console et erreurs de page sont PAR PAGE, toutes frames
        confondues, c'est Playwright qui les collecte). ::

            ${diag}=    Get Fiori Diagnostics
            Should Be Empty    ${diag}[issues]
        """
        wanted = parse_sections(sections)
        browser = self._browser()
        diagnostics = {"sections": wanted, "frame_scope": self._ui5_frame}
        collection_errors = {}
        for key in ("url", "title"):
            try:
                diagnostics[key] = str(getattr(browser, "get_%s" % key)())
            except Exception:
                pass    # contexte facultatif : une page absente se voit dans les sections
        if "composition" in wanted:
            try:
                diagnostics["composition"] = self.get_page_composition()
            except Exception as err:
                collection_errors["composition"] = str(err)
        if "tree" in wanted:
            def _dump_tree():
                try:
                    return self._evaluate(DUMP_TREE_JS, arg=None)
                except Exception:
                    return None
            diagnostics["ui5_tree"] = poll_until(
                _dump_tree, timestr_to_secs(tree_timeout),
                step=self.poll_interval) or None
        if "console" in wanted:
            try:
                entries = normalize_console_entries(
                    browser.get_console_log(full=bool(full_logs)))
                kept, dropped = tail_entries(entries, int(max_log_entries))
                diagnostics["console"] = kept
                if dropped:
                    diagnostics["console_dropped"] = dropped
            except Exception as err:
                collection_errors["console"] = str(err)
        if "errors" in wanted:
            try:
                entries = normalize_page_errors(
                    browser.get_page_errors(full=bool(full_logs)))
                kept, dropped = tail_entries(entries, int(max_log_entries))
                diagnostics["page_errors"] = kept
                if dropped:
                    diagnostics["page_errors_dropped"] = dropped
            except Exception as err:
                collection_errors["errors"] = str(err)
        if "aria" in wanted:
            try:
                diagnostics["aria"] = str(browser.get_aria_snapshot(
                    self._scoped_selector(str(aria_selector))))
            except Exception as err:
                collection_errors["aria"] = str(err)
        if collection_errors:
            diagnostics["collection_errors"] = collection_errors
        diagnostics["issues"] = summarize_issues(diagnostics)
        return diagnostics

    def log_fiori_diagnostics(self, sections="composition,tree,console,errors,aria",
                              tree_timeout="3s", full_logs=False,
                              max_log_entries=50, aria_selector="css=body"):
        """Collecte `Get Fiori Diagnostics` (mêmes paramètres) puis écrit le
        **rapport Markdown** dans le log Robot : anomalies d'abord, puis chaque
        section en résumé compact. Retourne le dict complet, pour enchaîner une
        assertion sur ``issues`` après coup. Le réflexe de fin de test en échec::

            [Teardown]    Run Keyword If Test Failed    Log Fiori Diagnostics
        """
        diagnostics = self.get_fiori_diagnostics(
            sections=sections, tree_timeout=tree_timeout, full_logs=full_logs,
            max_log_entries=max_log_entries, aria_selector=aria_selector)
        logger.info(render_diagnostics_report(diagnostics))
        return diagnostics
