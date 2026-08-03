"""Tests de la sentinelle de dérive : cœur pur (sapfx_common.screen_watch) et
keyword d'E/S `Check Screen Against Watch` (perception et hash stubbés)."""
import pytest

from sapfx_common.screen_watch import (WatchOutcome, compare_watch,
                                       render_watch_report)
from SapEccLibrary import SapEccLibrary

SIG_V1 = "\n".join([
    "# screen SAPLSETB/SE16/230",
    "  wnd[0]/usr/lblDATABROWSE-TABLENAME\tGuiLabel\tTable Name",
    "* wnd[0]/usr/ctxtDATABROWSE-TABLENAME\tGuiCTextField\t",
    "  wnd[0]/tbar[1]/btn[31]\tGuiButton\tNumber of Entries",
])
# Dérive simulée : le bouton 31 devient 13 (le scénario healer de la 0.3.0).
SIG_V2 = SIG_V1.replace("btn[31]", "btn[13]")


# --- cœur pur -------------------------------------------------------------------

def test_compare_watch_inchange():
    outcome = compare_watch("SE16", SIG_V1, SIG_V1, "ab" * 8, "ab" * 8)
    assert outcome.status == "unchanged" and not outcome.drifted
    assert outcome.visual_distance == 0


def test_compare_watch_derive_structurelle_nommee():
    # ids voisins (btn[31] -> btn[13]) : le diff INTELLIGENT les apparie en un
    # renommage « ~ ancien -> nouveau » au lieu de deux lignes -/+ brutes.
    outcome = compare_watch("SE16", SIG_V1, SIG_V2)
    assert outcome.drifted
    assert "~ " in outcome.structural_diff
    assert "btn[31]" in outcome.structural_diff
    assert "btn[13]" in outcome.structural_diff
    assert "similarité" in outcome.structural_diff


def test_compare_watch_disparition_reste_un_bloc_moins_plus():
    # un élément réellement DISPARU (aucun id proche) garde la ligne « - » —
    # l'appariement ne fabrique jamais un faux renommage.
    sig_sans_bouton = "\n".join(
        line for line in SIG_V1.splitlines() if "btn[31]" not in line)
    outcome = compare_watch("SE16", SIG_V1, sig_sans_bouton)
    assert outcome.drifted
    assert "- " in outcome.structural_diff
    assert "btn[31]" in outcome.structural_diff
    assert "~ " not in outcome.structural_diff


def test_compare_watch_derive_visuelle_seule():
    # même structure, rendu altéré : 16 bits de distance > seuil 5
    outcome = compare_watch("SM50", SIG_V1, SIG_V1, "00" * 8, "0f0f" + "00" * 6)
    assert outcome.drifted and outcome.structural_diff is None
    assert outcome.visual_distance == 8


def test_empreinte_absente_d_un_cote_jamais_une_derive():
    # Pillow optionnel : un hash manquant ne déclenche rien (canal structurel seul)
    assert not compare_watch("X", SIG_V1, SIG_V1, None, "ab" * 8).drifted
    assert not compare_watch("X", SIG_V1, SIG_V1, "ab" * 8, None).drifted


def test_render_watch_report_derives_en_tete():
    outcomes = [
        WatchOutcome("SE38", "unchanged"),
        compare_watch("SE16", SIG_V1, SIG_V2),
        WatchOutcome("SM50", "baseline-created"),
    ]
    report = render_watch_report(outcomes)
    assert "3 surveillé(s), 1 dérive(s)" in report
    assert "DÉRIVE : SE16" in report and "```diff" in report
    assert "Références créées" in report and "SM50" in report
    assert "Inchangés : SE38" in report


# --- keyword (E/S stubbée) --------------------------------------------------------

def _watch_lib(signature, visual="a1b2c3d4e5f60718"):
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.get_screen_signature = lambda **kwargs: signature
    lib.get_screen_perceptual_hash = lambda **kwargs: visual
    return lib


def test_keyword_premiere_visite_cree_la_reference(tmp_path):
    lib = _watch_lib(SIG_V1)
    verdict = lib.check_screen_against_watch("SE16", directory=str(tmp_path))
    assert verdict["status"] == "baseline-created"
    assert (tmp_path / "SE16.signature.txt").exists()
    assert (tmp_path / "SE16.dhash.txt").exists()


def test_keyword_inchange_puis_derive_rapportee(tmp_path):
    _watch_lib(SIG_V1).check_screen_against_watch("SE16", directory=str(tmp_path))
    verdict = _watch_lib(SIG_V1).check_screen_against_watch(
        "SE16", directory=str(tmp_path))
    assert verdict["status"] == "unchanged"
    # dérive : rapportée (run vert) + perception courante sauvée à côté
    verdict = _watch_lib(SIG_V2).check_screen_against_watch(
        "SE16", directory=str(tmp_path))
    assert verdict["status"] == "drifted"
    assert "btn[13]" in verdict["structural_diff"]
    assert (tmp_path / "SE16.actual.signature.txt").exists()


def test_keyword_fail_on_drift_transforme_en_assertion(tmp_path):
    _watch_lib(SIG_V1).check_screen_against_watch("SE16", directory=str(tmp_path))
    with pytest.raises(AssertionError) as err:
        _watch_lib(SIG_V2).check_screen_against_watch(
            "SE16", directory=str(tmp_path), fail_on_drift=True)
    assert "DÉRIVÉ" in str(err.value)


def test_keyword_sans_pillow_reste_utilisable(tmp_path):
    # get_screen_perceptual_hash lève (Pillow absent / vieux SAP GUI) : la
    # sentinelle continue sur le seul canal structurel.
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.get_screen_signature = lambda **kwargs: SIG_V1
    lib.get_screen_perceptual_hash = lambda **kwargs: (_ for _ in ()).throw(
        RuntimeError("Pillow manquant"))
    verdict = lib.check_screen_against_watch("SE16", directory=str(tmp_path))
    assert verdict["status"] == "baseline-created"
    assert not (tmp_path / "SE16.dhash.txt").exists()


def test_keyword_nom_filtre_contre_le_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        _watch_lib(SIG_V1).check_screen_against_watch(
            "../evil", directory=str(tmp_path))


# --- canal tuiles : localisation de la dérive visuelle -----------------------------

def test_locate_tile_drift_nomme_tuile_rectangle_et_elements():
    from sapfx_common.screen_watch import locate_tile_drift
    distances = [0] * 16
    distances[5] = 9                      # tuile ligne 2, colonne 2 (1-based)
    report = locate_tile_drift(
        distances, 4, 4, 64, 64, threshold=5,
        elements=[("wnd[0]/usr/cntlGRID1/shellcont/shell", 10, 10, 40, 40),
                  ("wnd[0]", 0, 0, 64, 64),
                  ("wnd[0]/usr/lblAilleurs", 40, 0, 10, 10)])
    assert "tuile (2,2)" in report and "9 bits" in report
    assert "[16,16 16x16]" in report
    # les recouvrants du PLUS PETIT au plus grand ; l'élément hors tuile absent
    assert "éléments : wnd[0]/usr/cntlGRID1/shellcont/shell, wnd[0]" in report
    assert "lblAilleurs" not in report


def test_locate_tile_drift_sous_le_seuil_est_vide():
    from sapfx_common.screen_watch import locate_tile_drift
    assert locate_tile_drift([5] * 16, 4, 4, 64, 64, threshold=5) == ""


def test_apply_tile_verdict_rattrape_une_derive_diluee():
    from sapfx_common.screen_watch import apply_tile_verdict
    # hash global sous le seuil (unchanged) MAIS une tuile a dérivé
    unchanged = compare_watch("SE16", SIG_V1, SIG_V1, "00" * 8, "00" * 8)
    assert not unchanged.drifted
    upgraded = apply_tile_verdict(unchanged, "tuile (1,1) [0,0 16x16] : 9 bits")
    assert upgraded.drifted and "tuile (1,1)" in upgraded.visual_tiles
    # sans rapport de tuiles : verdict inchangé
    assert apply_tile_verdict(unchanged, None) is unchanged


def test_render_watch_report_inclut_la_derive_localisee():
    from sapfx_common.screen_watch import apply_tile_verdict
    outcome = apply_tile_verdict(
        compare_watch("SE16", SIG_V1, SIG_V1),
        "tuile (2,1) [0,262 484x262] : 7 bits — éléments : usr/cntlGRID1")
    report = render_watch_report([outcome])
    assert "dérive visuelle localisée" in report
    assert "usr/cntlGRID1" in report


# --- keyword : le canal tuiles de bout en bout --------------------------------------

TUILES_A = ["00" * 8] * 4
TUILES_B = ["00" * 8] * 3 + ["ff" * 8]    # la 4e tuile a totalement changé


def _watch_lib_tuiles(signature, tuiles):
    lib = _watch_lib(signature)
    lib._try_tile_capture = lambda tx, ty, hs=8: (tuiles, 64, 64)
    return lib


def test_keyword_tuiles_ecrites_puis_derive_localisee(tmp_path):
    lib = _watch_lib_tuiles(SIG_V1, TUILES_A)
    lib.check_screen_against_watch("SE16", directory=str(tmp_path),
                                   tiles_x=2, tiles_y=2)
    tiles_file = tmp_path / "SE16.tiles.txt"
    assert tiles_file.exists()
    assert tiles_file.read_text(encoding="utf-8").startswith("2 2 8 64 64")
    # même structure, même hash global : SEULE la 4e tuile a bougé -> la
    # sentinelle rattrape la dérive localisée que le canal global ne voit pas
    verdict = _watch_lib_tuiles(SIG_V1, TUILES_B).check_screen_against_watch(
        "SE16", directory=str(tmp_path), tiles_x=2, tiles_y=2)
    assert verdict["status"] == "drifted"
    assert "tuile (2,2)" in verdict["visual_tiles"]
    assert "64 bits" in verdict["visual_tiles"]


def test_keyword_sans_tuiles_reste_utilisable(tmp_path):
    # _try_tile_capture répond None (Pillow absent...) : la sentinelle
    # fonctionne sur les deux canaux historiques, sans fichier .tiles.txt
    lib = _watch_lib(SIG_V1)
    lib._try_tile_capture = lambda tx, ty, hs=8: None
    verdict = lib.check_screen_against_watch("SE16", directory=str(tmp_path))
    assert verdict["status"] == "baseline-created"
    assert not (tmp_path / "SE16.tiles.txt").exists()
