"""Mixin perception des pages hybrides.

`Get Page Composition` (quelles technologies cohabitent ou : runtime
UI5/WC/lsdata/frameworks + moteurs recommandes par region, descente d'un
niveau dans chaque iframe, best-effort).

Extrait de ``SapFioriLibrary.py`` (convention #13).
"""

from typing import TYPE_CHECKING, Any

from .._ui5_js import (
    PAGE_COMPOSITION_JS,
)
from .._ui5_runtime import (
    recommended_engines,
)


class CompositionKeywords:
    """Mixin compose dans :class:`SapFioriLibrary` (voir ce module).
    Suppose la page active de Browser accessible via ``self._browser()``
    et la plomberie de ``_base.py`` disponible par composition."""

    if TYPE_CHECKING:
        # Contrat du composite, pour mypy seulement : les
        # keywords annotés font vérifier leurs corps.
        def _browser(self, *args: Any, **kwargs: Any) -> Any: ...
        def _evaluate(self, *args: Any, **kwargs: Any) -> Any: ...
        def _scoped_selector(self, *args: Any, **kwargs: Any) -> Any: ...
        _ui5_frame: Any
        poll_interval: Any

    # -- sonde de composition (perception des pages hybrides) ------------------

    def get_page_composition(self, include_frames: bool = True):
        """Sonde la *composition technologique* de la page courante : la
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
        moteur adresser où.

        Exemple :
        | ${composition}=    `Get Page Composition`
        | Should Be True    ${composition}[ui5_runtime]
        """
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


