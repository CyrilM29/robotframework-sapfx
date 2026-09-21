"""Lecture tabulaire des canaux WEB, hors navigateur (convention #5).

Les keywords éprouvés ici existent pour une seule raison, mesurée le
2026-09-15 : une table UI5 et une grille WebGUI rendent toutes deux une PARTIE
de leur contenu sans rien laisser paraître. Les lignes rendues sont propres,
ordonnées, numérotées sans trou. Ces tests verrouillent donc surtout ce qui
distingue le cas dangereux du cas sain, c'est-à-dire le total DÉCLARÉ.

Le JS réel est exercé par les deux suites live ; ici, le contrat Python.
"""
from __future__ import annotations

import pytest

from SapFioriLibrary._ui5_js import (
    TABLE_INFO_JS,
    WEBGUI_GRID_PROBE_JS,
    WEBGUI_IDENTITY_PROBE_JS,
)
from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary
from sapfx_common.system_identity import webgui_identity


class FakeBrowser:
    def __init__(self, reponses=None):
        self.reponses = reponses or {}
        self.appels = []

    def evaluate_javascript(self, selector, js, arg=None):
        self.appels.append((js, arg))
        valeur = self.reponses.get(js)
        if isinstance(valeur, Exception):
            raise valeur
        return valeur


def _lib(browser, ids=None):
    lib = SapFioriLibrary(ui5_timeout="2s")
    lib._browser = lambda: browser
    if ids is not None:
        lib._resolve = lambda js, arg, description, timeout=None: ids
    return lib


# --- la sonde WebGUI doit COMMENCER par sa fonction -------------------------

def test_le_gabarit_de_sonde_commence_par_la_fonction():
    """Un commentaire posé AVANT la fonction fait évaluer la source comme une
    expression : la fonction n'est alors jamais appelée, le résultat revient
    vide et l'appel RÉUSSIT. Mesuré le 2026-09-15, et c'est exactement le genre
    de panne qu'aucun test d'intégration ne montre, puisque rien n'échoue."""
    assert WEBGUI_GRID_PROBE_JS.startswith("(first, second) =>")


# --- tables UI5 --------------------------------------------------------------

class TestContratDeTableUi5:
    def _info(self, **surcharges):
        base = {"type": "sap.m.Table", "source": "items", "binding": "items",
                "headers": ["Voyage", "Agence"], "rendered_rows": 30,
                "declared_rows": 4133, "contexts": 30, "length_final": True,
                "growing": True, "growing_threshold": 30, "columns": 2}
        base.update(surcharges)
        return base

    def test_le_total_declare_est_rendu_et_l_ecart_devient_visible(self):
        lib = _lib(FakeBrowser({TABLE_INFO_JS: self._info()}), ids=["t"])
        info = lib.get_ui5_table_info(id="t")
        assert info["rendered_rows"] == 30
        assert info["declared_rows"] == 4133
        assert info["complete"] is False
        assert info["growing_threshold"] == 30

    def test_une_table_entierement_rendue_est_complete(self):
        lib = _lib(FakeBrowser({TABLE_INFO_JS: self._info(
            rendered_rows=2, declared_rows=2, growing_threshold=30)}), ids=["t"])
        assert lib.get_ui5_table_info(id="t")["complete"] is True

    def test_un_total_provisoire_ne_vaut_pas_complet(self):
        # `isLengthFinal` à False : le modèle n'a pas fini de compter, donc le
        # total ne borne rien. Ni True ni False : non mesurable.
        lib = _lib(FakeBrowser({TABLE_INFO_JS: self._info(
            rendered_rows=30, declared_rows=30, length_final=False)}), ids=["t"])
        assert lib.get_ui5_table_info(id="t")["complete"] is None

    def test_une_table_sans_binding_ne_declare_rien(self):
        lib = _lib(FakeBrowser({TABLE_INFO_JS: self._info(
            declared_rows=None, binding="")}), ids=["t"])
        info = lib.get_ui5_table_info(id="t")
        assert info["declared_rows"] is None
        assert info["complete"] is None

    def test_les_colonnes_rendues_sont_celles_que_le_bundle_a_lues(self):
        # Propriété du CANAL : une table UI5 n'expose pas d'identifiant
        # technique de colonne, donc les colonnes SONT les libellés lus par
        # `getColumns()`. Ce qui est vérifié ici est le report fidèle de ce que
        # le bundle a rendu, doublons et repli `col<i>` compris : une colonne
        # sans en-tête ne doit pas disparaître de la liste, sans quoi le
        # relevé et le contrat cesseraient de compter le même nombre de
        # colonnes.
        lib = _lib(FakeBrowser({TABLE_INFO_JS: self._info(
            headers=["Voyage", "col1", "Voyage"], columns=3)}), ids=["t"])
        info = lib.get_ui5_table_info(id="t")
        assert info["columns"] == ["Voyage", "col1", "Voyage"]

    def test_l_absence_de_runtime_echoue_en_nommant_le_remede(self):
        lib = _lib(FakeBrowser({TABLE_INFO_JS: None}), ids=["t"])
        with pytest.raises(AssertionError, match="Ui5 Runtime Is Present"):
            lib.get_ui5_table_info(id="t")


# --- grilles WebGUI ----------------------------------------------------------

class TestGrilleWebgui:
    def _grille(self, **surcharges):
        base = {"found": True, "sid": "wnd[0]/usr/cntlGRID1/shellcont/shell",
                "container": "GRID1", "columns": ["SPRSL", "ARBGB"],
                "headers": {"SPRSL": "Langue", "ARBGB": "Classe"},
                "rows": [{"SPRSL": "E", "ARBGB": "MD_LOG"}],
                "rendered_rows": 1, "declared_rows": 1, "visible_rows": 19,
                "first_visible_row": 0, "declared_columns": 2,
                "scrolling": "client", "scrolling_on_demand": 1,
                "client_cell_threshold": 4000, "first_row_index": 1,
                "last_row_index": 1, "headers_found": 2,
                "candidates": ["wnd[0]/usr/cntlGRID1/shellcont/shell"]}
        base.update(surcharges)
        return base

    def test_deux_grilles_sans_designation_sont_un_REFUS(self):
        # Prendre la première du DOM produirait cinq fichiers complets d'un
        # AUTRE tableau que celui annoncé dans leur nom : la faute même que
        # cette capacité existe pour empêcher.
        lib = _lib(FakeBrowser({WEBGUI_GRID_PROBE_JS: self._grille(
            candidates=["wnd[0]/usr/cntlGRID1/shellcont/shell",
                        "wnd[0]/usr/cntlGRID2/shellcont/shell"])}))
        with pytest.raises(AssertionError) as echec:
            lib.read_webgui_grid()
        assert "2 grilles" in str(echec.value)
        assert "cntlGRID2" in str(echec.value)

    def test_une_grille_designee_est_lue_malgre_l_ambiguite(self):
        lib = _lib(FakeBrowser({WEBGUI_GRID_PROBE_JS: self._grille(
            candidates=["wnd[0]/usr/cntlGRID1/shellcont/shell",
                        "wnd[0]/usr/cntlGRID2/shellcont/shell"])}))
        grille = lib.read_webgui_grid("wnd[0]/usr/cntlGRID1/shellcont/shell")
        assert len(grille["candidates"]) == 2

    def test_le_balayage_des_titres_est_COMPTE(self):
        # La carte des titres rebouche chaque trou par l'identifiant de
        # colonne : elle a donc la même forme qu'on ait tout trouvé ou rien.
        # Seul ce compteur distingue des titres identiques aux identifiants
        # (le cas de SE16) d'un balayage qui a échoué.
        lib = _lib(FakeBrowser({WEBGUI_GRID_PROBE_JS: self._grille(
            headers={}, headers_found=0)}))
        grille = lib.read_webgui_grid()
        assert grille["headers"] == {"SPRSL": "SPRSL", "ARBGB": "ARBGB"}, \
            "le repli est silencieux, et c'est pourquoi le compteur existe"
        assert grille["headers_found"] == 0

    def test_les_lignes_sont_clees_par_identifiant_technique(self):
        # Contrairement au canal UI5, le WebGUI publie les noms de champs ABAP
        # dans son `lsdata` : ce sont des clés indépendantes de la langue.
        lib = _lib(FakeBrowser({WEBGUI_GRID_PROBE_JS: self._grille()}))
        grille = lib.read_webgui_grid()
        assert grille["columns"] == ["SPRSL", "ARBGB"]
        assert grille["rows"] == [{"SPRSL": "E", "ARBGB": "MD_LOG"}]
        assert grille["headers"]["SPRSL"] == "Langue"
        assert grille["complete"] is True

    def test_une_page_de_lignes_pour_un_total_bien_plus_grand(self):
        # Le cas mesuré : 200 lignes rendues, 2000 déclarées, renumérotées à
        # partir de 1. Rien dans les lignes ne le montre.
        lib = _lib(FakeBrowser({WEBGUI_GRID_PROBE_JS: self._grille(
            rendered_rows=200, declared_rows=2000, first_row_index=1,
            last_row_index=200)}))
        grille = lib.read_webgui_grid()
        assert grille["complete"] is False
        assert grille["first_row_index"] == 1, \
            "la renumérotation est le fait qui rend l'amputation invisible"

    def test_le_contrat_se_lit_sans_trainer_le_releve(self):
        lib = _lib(FakeBrowser({WEBGUI_GRID_PROBE_JS: self._grille()}))
        info = lib.get_webgui_grid_info()
        assert "rows" not in info
        assert info["declared_rows"] == 1

    def test_un_sid_inconnu_echoue_en_listant_les_grilles_reelles(self):
        lib = _lib(FakeBrowser({WEBGUI_GRID_PROBE_JS: {
            "found": False, "wanted": "wnd[0]/usr/cntlX/shellcont/shell",
            "candidates": ["wnd[0]/usr/cntlGRID1/shellcont/shell"],
            "lsdata_elements": 190}}))
        with pytest.raises(AssertionError) as echec:
            lib.read_webgui_grid("wnd[0]/usr/cntlX/shellcont/shell")
        assert "cntlGRID1" in str(echec.value)

    def test_un_ecran_sans_grille_renvoie_au_mode_d_affichage(self):
        # Le cas réel : SE16 rend une liste ABAP classique tant que le mode
        # ALV n'est pas choisi, et l'écran est alors plein d'éléments lsdata.
        lib = _lib(FakeBrowser({WEBGUI_GRID_PROBE_JS: {
            "found": False, "wanted": "", "candidates": [],
            "lsdata_elements": 190}}))
        with pytest.raises(AssertionError, match="Use ALV Grid In Data Browser"):
            lib.read_webgui_grid()

    def test_une_session_absente_est_dite_comme_telle(self):
        lib = _lib(FakeBrowser({WEBGUI_GRID_PROBE_JS: {
            "found": False, "wanted": "", "candidates": [],
            "lsdata_elements": 0}}))
        with pytest.raises(AssertionError, match="Webgui Is Present"):
            lib.read_webgui_grid()


# --- identité d'une session WebGUI ------------------------------------------

class TestIdentiteWebgui:
    def test_le_systeme_et_le_mandant_se_lisent_par_la_FORME(self):
        # Le libellé est traduit, la forme ne l'est pas : trois caractères
        # alphanumériques, puis trois chiffres entre parenthèses.
        for texte in ("System A4H (001)", "Système A4H (001)",
                      "システム A4H (001)"):
            identite = webgui_identity({"system": texte})
            assert identite["system_id"] == "A4H"
            assert identite["client"] == "001"

    def test_le_mandant_a_sa_propre_source_de_repli(self):
        identite = webgui_identity({"system": "System A4H", "client": "Client 001"})
        assert identite["system_id"] == ""
        assert identite["client"] == "001"

    def test_le_dynpro_se_decompose(self):
        identite = webgui_identity({"dynpro": "Screen SAPLSLVC_FULLSCREEN/0500"})
        assert identite["program"] == "SAPLSLVC_FULLSCREEN"
        assert identite["screen"] == "0500"

    def test_une_zone_absente_laisse_les_cles_VIDES(self):
        # Jamais une valeur plausible à la place d'une valeur non lue : ce
        # keyword sert aussi à constater qu'aucune session n'est ouverte.
        identite = webgui_identity({})
        assert set(identite) == {"system_id", "client", "user", "transaction",
                                 "program", "screen"}
        assert not any(identite.values())

    def test_le_keyword_ne_leve_pas_sur_une_page_muette(self):
        lib = _lib(FakeBrowser({WEBGUI_IDENTITY_PROBE_JS: None}))
        assert lib.get_webgui_session_identity()["system_id"] == ""
