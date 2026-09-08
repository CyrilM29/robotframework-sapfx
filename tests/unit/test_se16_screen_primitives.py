"""Les deux primitives d'ÉCRAN SE16 promues de la couche resources.

`Use ALV Grid In Data Browser` et `Count Entries On Current Selection Screen`
vivaient dans `resources/ecc_keywords.resource`. La première est le REMÈDE que
trois messages d'échec de la bibliothèque prescrivent déjà, à un utilisateur
PyPI qui n'a pas `resources/` ; la seconde se dupliquait dans trois suites
autonomes. Promues dans le mixin `_se16.py` (convention #12), elles se testent
ici avec les doublures COM partagées (convention #5).
"""
from _ddic_keywords_fixtures import _Recorder  # noqa: F401

_COUNT_BUTTON = "wnd[0]/tbar[1]/btn[31]"
_COUNT_RESULT = "wnd[1]/usr/txtG_DBCOUNT"
_SETTINGS_MENU = "wnd[0]/mbar/menu[3]/menu[0]"


def _kinds(lib, kind):
    return [call for call in lib.calls if call[0] == kind]


class TestUseAlvGridInDataBrowser:
    def test_le_reglage_passe_par_l_ecran_initial_et_le_radio_alv(self):
        lib = _Recorder(screen="selection")
        lib.use_alv_grid_in_data_browser()
        assert ("run_transaction", "SE16") in lib.calls
        assert ("click", _SETTINGS_MENU) in lib.calls
        radios = _kinds(lib, "radio")
        assert len(radios) == 1
        assert radios[0][1].endswith("radRSEUMOD-TBALV_GRID")

    def test_la_modale_est_validee_par_entree(self):
        """Le réglage n'est acquis qu'une fois le dialogue confirmé : sans
        cette validation, la préférence n'est pas écrite et la sortie SE16
        reste en mode liste, ce que rien ne signalerait avant la lecture."""
        lib = _Recorder(screen="selection")
        lib.use_alv_grid_in_data_browser()
        assert ("vkey", 0, 1) in lib.calls
        assert lib.session.popup is None      # la modale est bien refermée

    def test_le_radio_est_attendu_avant_d_etre_coche(self):
        """La vue des paramètres se charge en asynchrone : cocher sans
        attendre viserait un contrôle pas encore rendu."""
        lib = _Recorder(screen="selection")
        lib.use_alv_grid_in_data_browser()
        ordre = [c[0] for c in lib.calls]
        assert ordre.index("wait_present") < ordre.index("radio")


class TestDataBrowserOutput:
    """Les trois sorties du Data Browser : la liste standard (l'inverse du
    réglage ALV, la cible du registre pour les listes classiques), le réglage
    générique, et la LECTURE du réglage courant, refermée sans rien changer."""

    def test_la_liste_standard_coche_son_radio_et_valide(self):
        lib = _Recorder(screen="selection")
        lib.use_standard_list_in_data_browser()
        radios = _kinds(lib, "radio")
        assert len(radios) == 1 and radios[0][1].endswith("radTB_DUMMY")
        assert ("vkey", 0, 1) in lib.calls
        assert lib.session.popup is None

    def test_un_mode_inconnu_est_refuse_en_listant_les_trois(self):
        import pytest
        lib = _Recorder(screen="selection")
        with pytest.raises(ValueError, match="alv_grid, alv_list, standard_list"):
            lib.set_data_browser_output("html")
        assert not _kinds(lib, "radio")           # rien n'a été touché

    def test_la_lecture_rend_le_mode_coche_et_referme_sans_valider(self):
        lib = _Recorder(screen="selection", output_radio="radTB_DUMMY")
        assert lib.get_data_browser_output() == "standard_list"
        assert not _kinds(lib, "radio")           # lecture seule
        assert ("vkey", 0, 1) not in lib.calls     # jamais validé par Entrée
        assert ("dismiss", 1) in lib.calls
        assert lib.session.popup is None

    def test_la_lecture_par_defaut_rend_la_grille_alv(self):
        lib = _Recorder(screen="selection")
        assert lib.get_data_browser_output() == "alv_grid"

    def test_aucun_radio_coche_est_un_echec_jamais_un_mode_devine(self):
        import pytest
        lib = _Recorder(screen="selection", output_radio=None)
        with pytest.raises(AssertionError, match="0 sortie\\(s\\) cochée"):
            lib.get_data_browser_output()
        assert lib.session.popup is None           # refermé même en échec


class TestCountEntriesOnCurrentSelectionScreen:
    def test_le_compte_est_lu_dans_le_popup_puis_referme(self):
        lib = _Recorder(screen="selection", count_text="205")
        assert lib.count_entries_on_current_selection_screen() == 205
        assert ("click", _COUNT_BUTTON) in lib.calls
        assert ("get_value", _COUNT_RESULT) in lib.calls
        # F12 sur la modale : l'écran de sélection reste utilisable ensuite.
        assert ("vkey", 12, 1) in lib.calls
        assert lib.session.popup is None

    def test_les_separateurs_de_milliers_sont_neutralises(self):
        """Le compteur AFFICHÉ suit le profil utilisateur : point, virgule ou
        espace. La normalisation est locale-safe par construction (chiffres
        seuls), la leçon anti-regex de 2026-07-10 étant conservée dans
        ``displayed_count``."""
        for affiche, attendu in (("4.136", 4136), ("4,136", 4136),
                                 ("4 136", 4136), ("42", 42)):
            lib = _Recorder(screen="selection", count_text=affiche)
            assert lib.count_entries_on_current_selection_screen() == attendu

    def test_une_table_vide_rend_zero_sans_echouer(self):
        """C'est la RAISON d'être de ce chemin plutôt que d'une exécution F8 :
        sur une table vide, F8 resterait sur l'écran de sélection sans grille,
        alors que « Number of Entries » répond 0."""
        lib = _Recorder(screen="selection", count_text="0")
        assert lib.count_entries_on_current_selection_screen() == 0

    def test_le_compteur_est_attendu_avant_d_etre_lu(self):
        lib = _Recorder(screen="selection", count_text="7")
        lib.count_entries_on_current_selection_screen()
        attentes = [c[1] for c in _kinds(lib, "wait_present")]
        assert _COUNT_RESULT in attentes
