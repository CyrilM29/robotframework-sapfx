"""Tests du hash perceptuel pur (sapfx_common.visual_hash) et des keywords
d'assertion visuelle, sans Pillow : la frontière image est stubbée, seul le
cœur algorithmique (matrices de gris) est exercé, comme il tournera en CI."""
import base64

import pytest

from sapfx_common.visual_hash import dhash_hex, hamming_distance
from SapEccLibrary import SapEccLibrary


def _flat(width, height, value=128):
    return [[value] * width for _ in range(height)]


def _gradient(width, height):
    """Dégradé horizontal DESCENDANT (gauche claire, droite sombre) : chaque
    voisin de gauche est plus clair -> dHash déterministe, tous bits à 1."""
    return [[(width - 1 - x) * 255 // max(width - 1, 1) for x in range(width)]
            for _ in range(height)]


# --- cœur pur -------------------------------------------------------------------

def test_dhash_est_deterministe_et_de_la_bonne_longueur():
    image = _gradient(64, 64)
    h1 = dhash_hex(image)
    h2 = dhash_hex(image)
    assert h1 == h2
    assert len(h1) == 16   # 64 bits en hexadécimal


def test_dhash_image_plate_et_degrade_sont_opposes():
    plat = dhash_hex(_flat(64, 64))
    degrade = dhash_hex(_gradient(64, 64))
    assert plat == "0" * 16       # aucun voisin plus clair
    assert degrade == "f" * 16    # tous les voisins de gauche plus clairs
    assert hamming_distance(plat, degrade) == 64


def test_petit_changement_local_petite_distance():
    image = _gradient(64, 64)
    modifie = [row[:] for row in image]
    for y in range(8):                      # un pâté SOMBRE dans le coin clair
        for x in range(8):
            modifie[y][x] = 0
    distance = hamming_distance(dhash_hex(image), dhash_hex(modifie))
    assert 0 < distance <= 8   # local : quelques bits, pas la moitié du hash


def test_dhash_matrice_trop_petite_ou_taille_invalide():
    with pytest.raises(ValueError):
        dhash_hex(_flat(4, 4))             # < grille 9x8
    with pytest.raises(ValueError):
        dhash_hex(_flat(64, 64), hash_size=1)


def test_hamming_exige_des_longueurs_identiques():
    with pytest.raises(ValueError):
        hamming_distance("ff", "ffff")
    assert hamming_distance("ff", "ff") == 0
    assert hamming_distance("00", "ff") == 8


# --- keywords (frontière image stubbée) ------------------------------------------

_PNG_STUB = base64.b64encode(b"\x89PNG-fake").decode("ascii")

# Décodage stubbé par CONTENU : la baseline relue depuis le disque et la
# capture courante passent par le même décodeur, comme avec un vrai Pillow.
_FAKE_IMAGES = {
    b"\x89PNG-gradient": _gradient(64, 64),
    b"\x89PNG-flat": _flat(64, 64),
    # Le MÊME écran rendu par un poste qui n'affiche pas pareil : autre
    # géométrie de capture, contenu de la même famille.
    b"\x89PNG-gradient-hd": _gradient(96, 72),
    b"\x89PNG-flat-hd": _flat(96, 72),
}


def _visual_lib(marker):
    lib = SapEccLibrary(screenshots_on_error=False)
    png = b"\x89PNG-" + marker.encode("ascii")
    lib.get_screenshot_as_base64 = (
        lambda image_format="png": base64.b64encode(png).decode("ascii"))
    lib._decode_image_to_gray = lambda image_bytes: _FAKE_IMAGES[bytes(image_bytes)]
    return lib


def test_get_screen_perceptual_hash_via_keyword():
    lib = _visual_lib("gradient")
    assert lib.get_screen_perceptual_hash() == dhash_hex(_gradient(64, 64))


def test_baseline_creee_au_premier_passage_puis_conforme(tmp_path):
    lib = _visual_lib("gradient")
    base_dir = str(tmp_path / "baselines")
    assert lib.screen_should_match_baseline("se16", baseline_directory=base_dir) == 0
    assert (tmp_path / "baselines" / "se16.png").exists()
    # 2e passage : écran inchangé -> distance 0, pas de .actual.png
    assert lib.screen_should_match_baseline("se16", baseline_directory=base_dir) == 0
    assert not (tmp_path / "baselines" / "se16.actual.png").exists()


def test_derive_visuelle_echoue_avec_distance_et_remede(tmp_path):
    base_dir = str(tmp_path / "baselines")
    _visual_lib("gradient").screen_should_match_baseline(
        "ecran", baseline_directory=base_dir)
    with pytest.raises(AssertionError) as err:
        _visual_lib("flat").screen_should_match_baseline(
            "ecran", baseline_directory=base_dir)
    message = str(err.value)
    assert "distance" in message and "supprimer la baseline" in message
    assert (tmp_path / "baselines" / "ecran.actual.png").exists()


# --- baselines par géométrie (multi-résolution) ------------------------------------

def test_geometries_et_nom_de_variante():
    from sapfx_common.visual_baseline import (format_geometry, geometry_of,
                                              variant_path)
    assert geometry_of(_flat(96, 72)) == (96, 72)
    assert geometry_of([]) == (0, 0)
    assert format_geometry((1920, 1032)) == "1920x1032"
    assert variant_path("/base", "se16", (1920, 1032)).endswith(
        "se16@1920x1032.png")


def test_existing_geometries_liste_trie_et_ignore_les_captures(tmp_path):
    from sapfx_common.visual_baseline import existing_geometries
    for nom in ("se16@1920x1032.png", "se16@800x600.png",
                "se16@1920x1032.actual.png", "se16.png", "se38@640x480.png"):
        (tmp_path / nom).write_bytes(b"x")
    assert existing_geometries(str(tmp_path), "se16") == ["1920x1032", "800x600"]
    assert existing_geometries(str(tmp_path / "absent"), "se16") == []


def test_per_resolution_donne_une_baseline_par_geometrie(tmp_path):
    """Deux postes, deux géométries : le second ENREGISTRE sa référence au lieu
    d'échouer sur une dérive qui n'est que d'échelle."""
    base_dir = str(tmp_path / "baselines")
    assert _visual_lib("gradient").screen_should_match_baseline(
        "ecran", baseline_directory=base_dir, per_resolution=True) == 0
    assert _visual_lib("flat-hd").screen_should_match_baseline(
        "ecran", baseline_directory=base_dir, per_resolution=True) == 0
    assert (tmp_path / "baselines" / "ecran@64x64.png").exists()
    assert (tmp_path / "baselines" / "ecran@96x72.png").exists()
    assert not (tmp_path / "baselines" / "ecran.png").exists()
    # chaque poste rejoue contre SA référence : conforme, aucune capture sauvée
    assert _visual_lib("gradient").screen_should_match_baseline(
        "ecran", baseline_directory=base_dir, per_resolution=True) == 0
    assert not list((tmp_path / "baselines").glob("*.actual.png"))


def test_per_resolution_detecte_toujours_une_vraie_derive(tmp_path):
    """Une baseline par géométrie ne doit rien anesthésier : à géométrie
    constante, un autre rendu échoue comme avant, et la capture est sauvée à
    côté de LA variante concernée."""
    base_dir = str(tmp_path / "baselines")
    _visual_lib("flat-hd").screen_should_match_baseline(
        "ecran", baseline_directory=base_dir, per_resolution=True)
    with pytest.raises(AssertionError) as err:
        _visual_lib("gradient-hd").screen_should_match_baseline(
            "ecran", baseline_directory=base_dir, per_resolution=True)
    assert "distance" in str(err.value)
    assert (tmp_path / "baselines" / "ecran@96x72.actual.png").exists()


def test_per_resolution_reutilise_une_baseline_committee_de_meme_geometrie(tmp_path):
    """Compat : la baseline historique `<name>.png` reste la référence tant que
    sa géométrie coïncide, aucune variante n'est créée en double."""
    base_dir = str(tmp_path / "baselines")
    _visual_lib("gradient").screen_should_match_baseline(
        "ecran", baseline_directory=base_dir)             # baseline historique
    assert _visual_lib("gradient").screen_should_match_baseline(
        "ecran", baseline_directory=base_dir, per_resolution=True) == 0
    assert not (tmp_path / "baselines" / "ecran@64x64.png").exists()


def test_per_resolution_arrive_en_chaine_depuis_robot(tmp_path):
    """« False » est truthy en Python : la coercition doit être Robot-friendly,
    sinon l'option s'activerait toute seule depuis une suite."""
    base_dir = str(tmp_path / "baselines")
    _visual_lib("gradient").screen_should_match_baseline(
        "ecran", baseline_directory=base_dir, per_resolution="False")
    assert (tmp_path / "baselines" / "ecran.png").exists()
    _visual_lib("gradient").screen_should_match_baseline(
        "autre", baseline_directory=base_dir, per_resolution="True")
    assert (tmp_path / "baselines" / "autre@64x64.png").exists()


def test_echec_de_geometries_differentes_nomme_les_deux_et_le_remede(tmp_path):
    """Le cas vécu : baseline prise sur un poste, capture sur un autre. Le
    message doit dire que la dérive peut n'être que d'échelle."""
    base_dir = str(tmp_path / "baselines")
    _visual_lib("gradient").screen_should_match_baseline(
        "ecran", baseline_directory=base_dir)
    with pytest.raises(AssertionError) as err:
        _visual_lib("flat-hd").screen_should_match_baseline(
            "ecran", baseline_directory=base_dir)
    message = str(err.value)
    assert "baseline 64x64" in message and "capture 96x72" in message
    assert "per_resolution=True" in message


def test_nom_de_baseline_filtre_contre_le_path_traversal(tmp_path):
    lib = _visual_lib("gradient")
    with pytest.raises(ValueError):
        lib.screen_should_match_baseline("../evil",
                                         baseline_directory=str(tmp_path))


def test_erreur_pillow_absent_est_actionnable():
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.get_screenshot_as_base64 = lambda image_format="png": _PNG_STUB
    # _decode_image_to_gray réel : si Pillow manque, le message doit guider ;
    # s'il est présent, le PNG factice doit échouer proprement à l'ouverture.
    try:
        import PIL  # noqa: F401
        from PIL import UnidentifiedImageError
        with pytest.raises(UnidentifiedImageError):
            lib.get_screen_perceptual_hash()
    except ImportError:
        with pytest.raises(RuntimeError) as err:
            lib.get_screen_perceptual_hash()
        assert "Pillow" in str(err.value)


# --- régions pures : crop, masque, tuiles -----------------------------------------

def test_crop_pixels_decoupe_et_borne_a_l_image():
    from sapfx_common.visual_hash import crop_pixels
    image = [[x + 10 * y for x in range(8)] for y in range(4)]
    crop = crop_pixels(image, (2, 1, 3, 2))
    assert crop == [[12, 13, 14], [22, 23, 24]]
    # région débordante : bornée aux dimensions, jamais d'IndexError
    assert crop_pixels(image, (6, 3, 10, 10)) == [[36, 37]]


def test_crop_pixels_region_hors_image_est_une_erreur():
    from sapfx_common.visual_hash import crop_pixels
    with pytest.raises(ValueError):
        crop_pixels([[0, 0], [0, 0]], (5, 5, 3, 3))


def test_mask_regions_neutralise_sans_toucher_l_original():
    from sapfx_common.visual_hash import mask_regions
    image = _gradient(64, 64)
    masque = mask_regions(image, [(32, 0, 32, 64)])
    assert image[0][40] != 128          # l'original n'est PAS modifié
    assert masque[0][40] == 128         # la moitié droite est neutralisée
    assert masque[0][10] == image[0][10]   # la gauche est intacte
    assert dhash_hex(masque) != dhash_hex(image)


def test_mask_regions_identique_des_deux_cotes_stabilise_le_hash():
    from sapfx_common.visual_hash import mask_regions
    # deux "écrans" qui ne diffèrent QUE dans la zone volatile (ex. l'horloge)
    a = _gradient(64, 64)
    b = [row[:] for row in a]
    for x in range(32, 64):
        b[63][x] = 255
    region = [(32, 56, 32, 8)]
    assert dhash_hex(mask_regions(a, region)) == dhash_hex(mask_regions(b, region))


def test_tile_rect_partitionne_exactement_l_image():
    from sapfx_common.visual_hash import tile_rect
    rects = [tile_rect(i, 65, 33, 4, 4) for i in range(16)]
    assert sum(w * h for _, _, w, h in rects) == 65 * 33
    left, top, width, height = tile_rect(5, 64, 64, 4, 4)   # ligne 2, colonne 2
    assert (left, top, width, height) == (16, 16, 16, 16)


def test_tiled_dhash_localise_un_changement_dans_sa_tuile():
    from sapfx_common.visual_hash import tiled_dhash
    base = _gradient(128, 128)
    modifie = [row[:] for row in base]
    for y in range(4, 24):              # pâté sombre confiné à la tuile (1,1)
        for x in range(4, 24):
            modifie[y][x] = 0
    tuiles_a = tiled_dhash(base, 4, 4)
    tuiles_b = tiled_dhash(modifie, 4, 4)
    assert len(tuiles_a) == 16
    differentes = [
        i for i, (a, b) in enumerate(zip(tuiles_a, tuiles_b, strict=True))
        if a != b]
    assert differentes == [0]           # seule la première tuile a bougé


def test_tiled_hamming_exige_le_meme_decoupage():
    from sapfx_common.visual_hash import tiled_hamming
    with pytest.raises(ValueError):
        tiled_hamming(["ff" * 8], ["ff" * 8, "00" * 8])
    assert tiled_hamming(["00" * 8], ["ff" * 8]) == [64]


# --- keywords ECC : hash d'élément, masque, tuiles ---------------------------------

def _region_stub(lib, left=16, top=8, width=32, height=24):
    lib.get_element_screen_region = lambda eid: {
        "left": left, "top": top, "width": width, "height": height}
    return lib


def test_get_element_perceptual_hash_est_le_hash_du_crop():
    from sapfx_common.visual_hash import crop_pixels
    lib = _region_stub(_visual_lib("gradient"))
    attendu = dhash_hex(crop_pixels(_gradient(64, 64), (16, 8, 32, 24)))
    assert lib.get_element_perceptual_hash("wnd[0]/usr/cntlGRID1") == attendu


def test_get_screen_perceptual_hash_avec_masque_d_elements():
    from sapfx_common.visual_hash import mask_regions
    lib = _region_stub(_visual_lib("gradient"), 32, 0, 32, 64)
    attendu = dhash_hex(mask_regions(_gradient(64, 64), [(32, 0, 32, 64)]))
    assert lib.get_screen_perceptual_hash(mask_elements="wnd[0]/sbar") == attendu
    assert lib.get_screen_perceptual_hash() != attendu


def test_masque_auto_ignore_les_elements_absents():
    lib = _visual_lib("gradient")

    def region(eid):
        if eid != "wnd[0]/sbar":
            raise AssertionError("absent")
        return {"left": 0, "top": 56, "width": 64, "height": 8}

    lib.get_element_screen_region = region
    # titl absent -> ignoré (journalisé), sbar masqué : pas d'exception
    h = lib.get_screen_perceptual_hash(mask_elements="auto")
    assert h != dhash_hex(_gradient(64, 64))


def test_get_screen_tile_hashes_retourne_la_grille():
    lib = _visual_lib("gradient")
    tuiles = lib.get_screen_tile_hashes(tiles_x=2, tiles_y=2)
    assert len(tuiles) == 4
    assert all(len(t) == 16 for t in tuiles)


def test_element_baseline_cree_conforme_puis_derive(tmp_path):
    from sapfx_common.visual_hash import crop_pixels
    base_dir = str(tmp_path / "baselines")
    _FAKE_IMAGES[b"\x89PNG-gradient-crop"] = crop_pixels(
        _gradient(64, 64), (16, 8, 32, 24))
    _FAKE_IMAGES[b"\x89PNG-flat-crop"] = crop_pixels(
        _flat(64, 64), (16, 8, 32, 24))

    def crop_stub(png, region):
        return bytes(png) + b"-crop"

    lib = _region_stub(_visual_lib("gradient"))
    lib._crop_image = crop_stub
    assert lib.element_should_match_baseline(
        "grille", "wnd[0]/usr/cntlGRID1", baseline_directory=base_dir) == 0
    assert (tmp_path / "baselines" / "grille.png").exists()
    assert lib.element_should_match_baseline(
        "grille", "wnd[0]/usr/cntlGRID1", baseline_directory=base_dir) == 0
    # un AUTRE rendu de la même région -> échec nommant l'élément
    lib2 = _region_stub(_visual_lib("flat"))
    lib2._crop_image = crop_stub
    with pytest.raises(AssertionError) as err:
        lib2.element_should_match_baseline(
            "grille", "wnd[0]/usr/cntlGRID1", baseline_directory=base_dir)
    assert "L'élément wnd[0]/usr/cntlGRID1" in str(err.value)
    assert (tmp_path / "baselines" / "grille.actual.png").exists()


# --- keywords Fiori : parité du canal visuel ---------------------------------------

def _fiori_visual(marker):
    from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary
    lib = SapFioriLibrary(ui5_timeout="1s")
    png = b"\x89PNG-" + marker.encode("ascii")
    lib._page_png = lambda: png
    lib._decode_image_to_gray = lambda image_bytes: _FAKE_IMAGES[bytes(image_bytes)]
    return lib


def test_fiori_hash_perceptuel_via_browser():
    assert _fiori_visual("gradient").get_ui5_perceptual_hash() \
        == dhash_hex(_gradient(64, 64))


def test_fiori_baseline_meme_semantique_snapshot(tmp_path):
    base_dir = str(tmp_path / "baselines")
    assert _fiori_visual("gradient").ui5_screen_should_match_baseline(
        "shop", baseline_directory=base_dir) == 0
    assert _fiori_visual("gradient").ui5_screen_should_match_baseline(
        "shop", baseline_directory=base_dir) == 0
    with pytest.raises(AssertionError) as err:
        _fiori_visual("flat").ui5_screen_should_match_baseline(
            "shop", baseline_directory=base_dir)
    assert "La page" in str(err.value)
    assert (tmp_path / "baselines" / "shop.actual.png").exists()


def test_fiori_per_resolution_miroir_de_l_option_ecc(tmp_path):
    """Parité ECC ↔ Fiori : la taille de viewport fait partie de l'empreinte,
    donc le canal web a la même baseline par géométrie."""
    base_dir = str(tmp_path / "baselines")
    assert _fiori_visual("gradient").ui5_screen_should_match_baseline(
        "shop", baseline_directory=base_dir, per_resolution=True) == 0
    assert (tmp_path / "baselines" / "shop@64x64.png").exists()
    assert _fiori_visual("flat-hd").ui5_screen_should_match_baseline(
        "shop", baseline_directory=base_dir, per_resolution=True) == 0
    assert (tmp_path / "baselines" / "shop@96x72.png").exists()


# --- frontières Pillow réelles (sautées si Pillow absent) ---------------------------

def _real_png(width=40, height=30, color=(200, 60, 60)):
    PIL = pytest.importorskip("PIL")
    import io
    image = PIL.Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_crop_image_reel_recadre_en_png():
    pytest.importorskip("PIL")
    from PIL import Image
    import io
    lib = SapEccLibrary(screenshots_on_error=False)
    cropped = lib._crop_image(_real_png(40, 30), (10, 5, 20, 10))
    assert cropped[:4] == b"\x89PNG"
    assert Image.open(io.BytesIO(cropped)).size == (20, 10)
    with pytest.raises(ValueError):
        lib._crop_image(_real_png(40, 30), (100, 100, 10, 10))


def test_draw_annotations_reel_produit_un_png_annote():
    pytest.importorskip("PIL")
    from PIL import Image
    import io
    lib = SapEccLibrary(screenshots_on_error=False)
    annotated = lib._draw_annotations(
        _real_png(60, 40), [("1", 5, 5, 20, 10), ("2", 30, 20, 20, 10)])
    assert annotated[:4] == b"\x89PNG"
    image = Image.open(io.BytesIO(annotated)).convert("RGB")
    assert image.size == (60, 40)
    assert image.getpixel((5, 10)) == (220, 30, 30)   # bord de la boîte 1


def test_decode_image_to_gray_partage_est_le_meme_des_deux_cotes():
    pytest.importorskip("PIL")
    from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary
    png = _real_png(12, 9)
    ecc = SapEccLibrary(screenshots_on_error=False)._decode_image_to_gray(png)
    fiori = SapFioriLibrary._decode_image_to_gray(png)
    assert ecc == fiori
    assert len(ecc) == 9 and len(ecc[0]) == 12


def test_geometrie_lue_sur_de_VRAIES_images_pas_transposee(tmp_path):
    """La géométrie qui nomme une variante vient de la matrice décodée : sur de
    vraies images non carrées, largeur et hauteur ne doivent pas s'inverser
    (une variante mal nommée passerait inaperçue, les deux fichiers existant)."""
    pytest.importorskip("PIL")
    from sapfx_common.visual_baseline import (decode_image_to_gray,
                                              match_baseline)
    base_dir = str(tmp_path / "baselines")
    for width, height in ((40, 30), (80, 60)):
        outcome = match_baseline("ecran", _real_png(width, height),
                                 decode_image_to_gray, base_dir,
                                 per_resolution=True)
        assert outcome.created and outcome.geometry == (width, height)
    assert (tmp_path / "baselines" / "ecran@40x30.png").exists()
    assert (tmp_path / "baselines" / "ecran@80x60.png").exists()
    # rejoué sur la 1re géométrie : la variante existante est RELUE, pas récrite
    again = match_baseline("ecran", _real_png(40, 30), decode_image_to_gray,
                           base_dir, per_resolution=True)
    assert not again.created and again.distance == 0
