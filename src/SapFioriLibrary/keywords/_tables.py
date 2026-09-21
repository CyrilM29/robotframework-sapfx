"""Mixin **extraction tabulaire du canal web** : ce qu'une table DÉCLARE.

Il existe parce que les deux canaux web savent rendre un tableau et ne savent
pas dire qu'ils n'en ont rendu qu'un morceau.

* `Get Ui5 Table Info` : le contrat d'une table UI5, par opposition à son
  contenu. `Read Ui5 Table`, son voisin d'`_actions.py`, rend les lignes
  INSTANCIÉES : mesuré le 2026-09-15 sur une List Report Fiori Elements, 30
  lignes pour 4133 déclarées par le binding, toutes les 30 parfaitement
  remplies. Aucune ligne vide, aucune numérotation qui saute, aucun signal :
  seul le total déclaré fait la différence entre un inventaire et un extrait.

* `Read Webgui Grid` / `Get Webgui Grid Info` : la lecture d'une ALV rendue par
  le WebGUI, que le canal ne savait pas faire du tout. Il comptait les entrées
  d'une table (par le popup SE16) sans jamais pouvoir lire la table elle-même.
  Deux faits de rendu sont encodés dans la sonde : le DOM éclate une grille à
  colonnes figées en deux tables HTML alors que les SID des cellules la
  ré-unifient, et la grille publie dans son ``lsdata`` les identifiants
  TECHNIQUES de ses colonnes (``ColumnIDs``) plus son total (``totalRows``).
  Mesuré : 2000 lignes déclarées, 200 rendues, renumérotées à partir de 1.

Ces keywords perçoivent, ils ne jugent pas : la règle de refus est commune aux
trois canaux et vit dans :mod:`sapfx_common.table_extract`
(`Table Extract Should Be Complete`), pour qu'un canal de plus n'oblige pas à
la réécrire, et l'oublier.

Extrait de ``_actions.py`` / ``_engines.py`` (convention #13).
"""

from .._ui5_js import (
    RESOLVE_ROLE_JS,
    TABLE_INFO_JS,
    WEBGUI_GRID_PROBE_JS,
)
from .._ui5_runtime import build_control_selector, selector_to_json


class TableKeywords:
    """Mixin composé dans :class:`SapFioriLibrary` (voir ce module).
    Suppose la plomberie de ``_base.py`` disponible par composition."""

    # -- tables UI5 ------------------------------------------------------------

    def get_ui5_table_info(self, index=0, **selector_parts):
        """Ce qu'une table UI5 DÉCLARE contenir, sans lire ses lignes.

        Le complément indispensable de `Read Ui5 Table` : celui-ci rend les
        lignes instanciées, celui-là le total. Retourne un dict JSON-safe
        ``{type, source, binding, columns, headers, rendered_rows,
        declared_rows, contexts, length_final, growing, growing_threshold,
        complete}``.

        ``declared_rows`` est le ``getLength()`` du binding de la table.
        ``length_final`` à ``False`` signifie que ce total est lui-même
        PROVISOIRE (le modèle n'a pas fini de compter) : il ne borne alors
        rien, et le dire vaut mieux que de le présenter comme une mesure.
        ``complete`` vaut ``True`` seulement quand les lignes rendues
        atteignent un total ARRÊTÉ ; il vaut ``None``, jamais ``False``, quand
        le total n'est pas mesurable, sur le repli sûr du dépôt (une absence de
        mesure n'est pas un verdict).

        Une table qui n'expose aucun binding rend ``declared_rows`` à ``None``
        et se refuse donc en aval : c'est voulu. Une table non bornée écrite
        dans un fichier est un extrait présenté comme un inventaire.
        """
        selector = build_control_selector(**selector_parts)
        ids = self._resolve(RESOLVE_ROLE_JS, selector_to_json(selector), str(selector))
        dom_id = self._pick_id(ids, index, selector, noun="table")
        brut = self._evaluate(TABLE_INFO_JS, arg=dom_id)
        if not isinstance(brut, dict):
            raise AssertionError(
                "Lecture du contrat de table impossible pour %s : pas de "
                "runtime UI5 sur la portée courante, ou contrôle disparu entre "
                "sa résolution et sa lecture. Sonder avec Ui5 Runtime Is "
                "Present, et vérifier la portée de frame (Set/Push Ui5 Frame)."
                % selector)
        return _ui5_table_verdict(brut, str(selector))

    # -- grilles ALV du WebGUI (SAP GUI for HTML) ------------------------------

    def read_webgui_grid(self, sid=""):
        """Lit une grille ALV rendue par le **WebGUI**, avec son contrat.

        Le miroir WebGUI de `Read Full Grid` (ECC) et de `Read Ui5 Table`
        (Fiori). Retourne un dict JSON-safe ``{sid, container, columns,
        headers, rows, rendered_rows, declared_rows, visible_rows,
        first_visible_row, scrolling, complete, ...}``.

        Les lignes sont des dicts clés par les identifiants **TECHNIQUES** des
        colonnes (``MANDT``, ``SPRSL``), que la grille publie elle-même dans
        son ``lsdata`` : ce sont les seules clés indépendantes de la langue
        (convention 3). Les titres AFFICHÉS vivent à part, dans ``headers``,
        pour l'en-tête des fichiers livrés.

        ``sid`` vise une grille précise (``wnd[0]/usr/cntlGRID1/shellcont/shell``).
        Laissé vide, il n'est accepté que si l'écran ne porte QU'UNE grille :
        au-delà, l'échec les liste plutôt que d'en choisir une en silence.
        Prendre la première du DOM produirait cinq fichiers complets d'un AUTRE
        tableau que celui annoncé dans leur nom, ce qui est la faute même que
        cette capacité existe pour empêcher, et le dépôt remonte partout
        ailleurs une ambiguïté avec ses candidats.

        **Ce que le keyword ne fait pas** : défiler. Le serveur n'envoie
        qu'une PARTIE des lignes et les renumérote à partir de 1, donc une
        lecture de grille peut être PARTIELLE sans que rien dans les lignes ne
        le montre. ``declared_rows`` est là pour ça, et
        `Table Extract Should Be Complete` refuse l'écart.

        Un relevé du 2026-09-15, sur une table et un système : une sélection
        SE16 de 2000 lignes rendait ``totalRows`` à 2000 et 200 lignes dans le
        DOM. Ce qui est ÉTABLI est donc l'existence du cas, pas la valeur 200
        ni sa cause : la sonde rend ``visible_rows``, ``scrolling`` et
        ``client_cell_threshold`` pour qu'une seconde mesure puisse confirmer
        ou démentir, et ces valeurs se journalisent plutôt qu'elles ne
        s'assertent.
        """
        brut = self._evaluate(WEBGUI_GRID_PROBE_JS, arg=str(sid or ""))
        if not isinstance(brut, dict):
            raise AssertionError(
                "Lecture de grille WebGUI impossible : la page n'a pas "
                "répondu. Vérifier qu'une session WebGUI est rendue (Webgui Is "
                "Present) et la portée de frame (Set/Push Ui5 Frame).")
        return _webgui_grid_verdict(brut, str(sid or ""))

    def get_webgui_grid_info(self, sid=""):
        """Le contrat d'une grille WebGUI, sans ses lignes.

        La même sonde que `Read Webgui Grid`, projetée sur son seul contrat :
        la forme à poser dans une assertion « suis-je devant la bonne grille,
        et combien déclare-t-elle » sans trimballer le relevé.
        """
        verdict = dict(self.read_webgui_grid(sid))
        verdict.pop("rows", None)
        return verdict


def _ui5_table_verdict(payload, description):
    """Normalise le constat du bundle en dict JSON-safe, complétude comprise."""
    declare = payload.get("declared_rows")
    declare = None if declare is None else int(declare)
    rendues = int(payload.get("rendered_rows") or 0)
    final = payload.get("length_final")
    if declare is None or final is False:
        complet = None
    else:
        complet = rendues >= declare
    entetes = [str(h) for h in (payload.get("headers") or [])]
    return {"type": str(payload.get("type") or ""),
            "source": str(payload.get("source") or ""),
            "binding": str(payload.get("binding") or ""),
            "selector": description,
            "columns": entetes,
            "headers": {h: h for h in entetes},
            "rendered_rows": rendues,
            "declared_rows": declare,
            "contexts": payload.get("contexts"),
            "length_final": final,
            "growing": payload.get("growing"),
            "growing_threshold": payload.get("growing_threshold"),
            "complete": complet}


def _webgui_grid_verdict(payload, wanted):
    """Normalise la sonde WebGUI, et refuse une grille introuvable en le disant."""
    if not payload.get("found"):
        candidats = [str(c) for c in (payload.get("candidates") or [])]
        elements = int(payload.get("lsdata_elements") or 0)
        if wanted and candidats:
            raise AssertionError(
                "Aucune grille WebGUI au SID %r. Grilles rendues sur cet "
                "écran : %s." % (wanted, ", ".join(candidats)))
        if elements:
            raise AssertionError(
                "Aucune grille ALV (GuiGridView) sur cet écran WebGUI, alors "
                "que %d élément(s) lsdata y sont rendus : la sortie est "
                "peut-être une liste ABAP classique et non une grille. Dans "
                "SE16, Use ALV Grid In Data Browser bascule le mode "
                "d'affichage." % elements)
        raise AssertionError(
            "Aucun élément WebGUI (lsdata) rendu dans la portée courante : la "
            "session WebGUI n'est pas (ou plus) affichée. Sonder avec Webgui "
            "Is Present, et vérifier la portée de frame (Set/Push Ui5 Frame).")

    candidats = [str(c) for c in (payload.get("candidates") or [])]
    if not wanted and len(candidats) > 1:
        raise AssertionError(
            "Cet écran WebGUI porte %d grilles ALV et aucune n'a été désignée : "
            "%s. Prendre la première serait un choix silencieux, et le fichier "
            "produit porterait le contenu d'un autre tableau que celui annoncé. "
            "Passer le SID voulu à Read Webgui Grid."
            % (len(candidats), ", ".join(candidats)))

    declare = payload.get("declared_rows")
    declare = None if declare is None else int(declare)
    rendues = int(payload.get("rendered_rows") or 0)
    colonnes = [str(c) for c in (payload.get("columns") or [])]
    titres = {str(k): str(v) for k, v in (payload.get("headers") or {}).items()}
    lignes = [{str(k): ("" if v is None else str(v)) for k, v in ligne.items()}
              for ligne in (payload.get("rows") or [])]
    return {"sid": str(payload.get("sid") or ""),
            "candidates": candidats,
            "container": str(payload.get("container") or ""),
            "columns": colonnes,
            "headers": {c: titres.get(c, c) for c in colonnes},
            # Ce que le balayage des en-têtes a RÉELLEMENT trouvé. La carte des
            # titres rebouche chaque trou par l'identifiant de colonne, donc
            # elle a la même forme qu'on ait tout trouvé ou rien : seul ce
            # compteur les distingue.
            "headers_found": int(payload.get("headers_found") or 0),
            "rows": lignes,
            "rendered_rows": rendues,
            "declared_rows": declare,
            "visible_rows": payload.get("visible_rows"),
            "first_visible_row": payload.get("first_visible_row"),
            "declared_columns": payload.get("declared_columns"),
            "scrolling": str(payload.get("scrolling") or ""),
            "scrolling_on_demand": bool(payload.get("scrolling_on_demand")),
            "client_cell_threshold": payload.get("client_cell_threshold"),
            "first_row_index": payload.get("first_row_index"),
            "last_row_index": payload.get("last_row_index"),
            "complete": None if declare is None else rendues >= declare}
