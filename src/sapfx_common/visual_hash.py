"""Hash perceptuel d'écran (dHash) : le cœur PUR de l'assertion visuelle.

Complète la perception *structurée* (``Get Screen Signature``) d'un canal
*pixels* : certains rendus SAP GUI sont opaques à l'API Scripting (GuiShell
des listes modernes, GuiChart/GuiMap officiellement record-only) : la seule
« vérité » disponible y est l'image. Un hash perceptuel condense l'écran en
une empreinte comparable : deux captures visuellement identiques ont des
empreintes identiques, un petit changement local (bouton disparu, colonne
déplacée) produit une distance de Hamming faible mais non nulle, un écran
différent une distance élevée.

Algorithme : **dHash** (difference hash), moyenne par blocs vers une grille
``(hash_size+1) × hash_size``, puis un bit par comparaison de voisins
horizontaux. Choisi pour sa tolérance au bruit d'anticrénelage/thème et sa
simplicité auditables ; volontairement PAS de SSIM/deep-features (dépendances
lourdes, non déterministes entre versions).

Ce module ne décode PAS d'image : il travaille sur une matrice de gris
(lignes de valeurs 0..255) : le décodage PNG (Pillow) reste à la frontière,
dans le keyword appelant. Pur, typé, testé hors SAP et sans Pillow.
"""
from __future__ import annotations

from typing import Sequence

# Taille par défaut de la grille dHash : 8 → 64 bits, le standard de facto
# (assez discriminant pour un écran, assez court pour être journalisé).
HASH_SIZE = 8

# Une région rectangulaire en pixels : (left, top, width, height).
Region = tuple[int, int, int, int]

# Découpage en tuiles par défaut : 4×4 = 16 empreintes par écran. Sur un
# 1936×1048, chaque tuile fait ~484×262 px et son dHash 8×8 des blocs de
# ~60×33 px : la finesse que le hash global n'a pas, tout en restant assez
# large pour tolérer l'anticrénelage.
TILES = 4

# Valeur de remplissage d'une région masquée : gris moyen, neutre pour les
# comparaisons de voisins du dHash (déterministe des deux côtés : baseline et
# capture reçoivent le même masque, la zone ne contribue plus au hash).
MASK_FILL = 128

# Nombre maximal d'échantillons par axe et par bloc lors de la réduction :
# borne le coût de la moyenne (écran 1936×1048 → quelques milliers de
# lectures) tout en restant déterministe.
_MAX_SAMPLES_PER_AXIS = 8


def _block_mean(pixels: Sequence[Sequence[int]], top: int, bottom: int,
                left: int, right: int) -> float:
    """Moyenne (échantillonnée, déterministe) du bloc [top:bottom, left:right)."""
    height = max(bottom - top, 1)
    width = max(right - left, 1)
    step_y = max(height // _MAX_SAMPLES_PER_AXIS, 1)
    step_x = max(width // _MAX_SAMPLES_PER_AXIS, 1)
    total = 0
    count = 0
    for y in range(top, bottom, step_y):
        row = pixels[y]
        for x in range(left, right, step_x):
            total += row[x]
            count += 1
    return total / count if count else 0.0


def dhash_hex(pixels: Sequence[Sequence[int]], hash_size: int = HASH_SIZE) -> str:
    """dHash hexadécimal d'une matrice de gris (lignes de 0..255).

    Réduit l'image en grille ``(hash_size+1) × hash_size`` par moyennes de
    blocs, puis émet un bit par paire de voisins horizontaux
    (``gauche > droite``). Retourne ``hash_size²`` bits en hexadécimal
    (16 caractères pour la taille 8). Lève ``ValueError`` sur une matrice
    vide ou trop petite pour la grille demandée."""
    if hash_size < 2:
        raise ValueError("hash_size doit être >= 2 (reçu %d)" % hash_size)
    height = len(pixels)
    width = len(pixels[0]) if height else 0
    if height < hash_size or width < hash_size + 1:
        raise ValueError(
            "matrice %dx%d trop petite pour une grille dHash %dx%d"
            % (width, height, hash_size + 1, hash_size))
    cols = hash_size + 1
    grid = []
    for gy in range(hash_size):
        top = gy * height // hash_size
        bottom = (gy + 1) * height // hash_size
        grid_row = []
        for gx in range(cols):
            left = gx * width // cols
            right = (gx + 1) * width // cols
            grid_row.append(_block_mean(pixels, top, bottom, left, right))
        grid.append(grid_row)
    bits = 0
    for gy in range(hash_size):
        for gx in range(hash_size):
            bits = (bits << 1) | (1 if grid[gy][gx] > grid[gy][gx + 1] else 0)
    return "%0*x" % (hash_size * hash_size // 4, bits)


def hamming_distance(hash_a: str, hash_b: str) -> int:
    """Distance de Hamming entre deux hashes hexadécimaux de même longueur
    (nombre de bits qui diffèrent). Lève ``ValueError`` si les longueurs
    diffèrent : comparer des grilles de tailles différentes n'a pas de sens."""
    a = (hash_a or "").strip().lower()
    b = (hash_b or "").strip().lower()
    if len(a) != len(b):
        raise ValueError(
            "hashes de longueurs différentes (%d vs %d), même hash_size requis"
            % (len(a), len(b)))
    return bin(int(a, 16) ^ int(b, 16)).count("1")


# -- régions : crop, masque, tuiles -------------------------------------------
#
# Le hash GLOBAL d'un écran est un filet à grosses mailles (un bloc dHash 8×8
# couvre ~1/8 de l'écran) : c'est voulu pour l'assertion plein-écran, mais la
# perception gagne trois raffinements, tous purs :
#   * crop_pixels    : hasher LA région d'un élément (GuiShell, chart), les 64
#                      bits couvrent la zone opaque seule, sensibilité ×64 ;
#   * mask_regions   : neutraliser les zones volatiles connues (barre de statut
#                      avec l'heure, barre de titre) avant hachage ;
#   * tiled_dhash    : une empreinte PAR tuile d'une grille, la dérive est
#                      localisée (« tuile (2,1) »), attribuable à un élément.


def _clamp_region(region: Region, image_width: int,
                  image_height: int) -> tuple[int, int, int, int]:
    """Borne ``region`` aux dimensions de l'image ; retourne (x0, y0, x1, y1)
    (x1/y1 exclusifs, vides si la région est entièrement hors image)."""
    left, top, width, height = (int(v) for v in region)
    x0 = max(left, 0)
    y0 = max(top, 0)
    x1 = min(left + width, image_width)
    y1 = min(top + height, image_height)
    return x0, y0, x1, y1


def crop_pixels(pixels: Sequence[Sequence[int]],
                region: Region) -> list[list[int]]:
    """Découpe la région ``(left, top, width, height)`` d'une matrice de gris,
    bornée aux dimensions de l'image. Lève ``ValueError`` si l'intersection est
    vide (élément hors capture : l'appelant doit le savoir, pas hasher du vide)."""
    height = len(pixels)
    width = len(pixels[0]) if height else 0
    x0, y0, x1, y1 = _clamp_region(region, width, height)
    if x1 <= x0 or y1 <= y0:
        raise ValueError(
            "région (%s, %s, %sx%s) hors de l'image %dx%d : rien à découper"
            % (region[0], region[1], region[2], region[3], width, height))
    return [list(row[x0:x1]) for row in pixels[y0:y1]]


def mask_regions(pixels: Sequence[Sequence[int]],
                 regions: Sequence[Region],
                 fill: int = MASK_FILL) -> list[list[int]]:
    """Copie de la matrice avec chaque région remplie à ``fill`` (gris neutre) :
    la zone masquée ne contribue plus au hash. À appliquer AVANT ``dhash_hex``,
    identiquement à la baseline et à la capture (même liste de régions) : c'est
    ce qui neutralise les zones légitimement volatiles (horloge de la barre de
    statut) sans élargir le seuil global. Régions hors image simplement bornées."""
    out = [list(row) for row in pixels]
    height = len(out)
    width = len(out[0]) if height else 0
    for region in regions:
        x0, y0, x1, y1 = _clamp_region(region, width, height)
        for y in range(y0, y1):
            row = out[y]
            for x in range(x0, x1):
                row[x] = fill
    return out


def tile_rect(index: int, image_width: int, image_height: int,
              tiles_x: int = TILES, tiles_y: int = TILES) -> Region:
    """Rectangle ``(left, top, width, height)`` de la tuile ``index`` (ordre
    ligne par ligne) d'une grille ``tiles_x × tiles_y`` couvrant exactement
    l'image (mêmes frontières entières que ``tiled_dhash``)."""
    ty, tx = divmod(int(index), int(tiles_x))
    left = tx * image_width // tiles_x
    right = (tx + 1) * image_width // tiles_x
    top = ty * image_height // tiles_y
    bottom = (ty + 1) * image_height // tiles_y
    return (left, top, right - left, bottom - top)


def tiled_dhash(pixels: Sequence[Sequence[int]], tiles_x: int = TILES,
                tiles_y: int = TILES, hash_size: int = HASH_SIZE) -> list[str]:
    """Une empreinte dHash PAR tuile d'une grille ``tiles_x × tiles_y`` (ordre
    ligne par ligne, ``tiles_x * tiles_y`` hashes). Là où le hash global dilue
    un changement local dans tout l'écran, la grille de tuiles le **localise** :
    seule la tuile touchée dérive : c'est le canal fin de la sentinelle.
    Lève ``ValueError`` si une tuile devient trop petite pour la grille dHash."""
    tiles_x = int(tiles_x)
    tiles_y = int(tiles_y)
    if tiles_x < 1 or tiles_y < 1:
        raise ValueError("grille de tuiles invalide : %dx%d" % (tiles_x, tiles_y))
    height = len(pixels)
    width = len(pixels[0]) if height else 0
    return [
        dhash_hex(crop_pixels(pixels, tile_rect(index, width, height,
                                                tiles_x, tiles_y)), hash_size)
        for index in range(tiles_x * tiles_y)
    ]


def tiled_hamming(tiles_a: Sequence[str], tiles_b: Sequence[str]) -> list[int]:
    """Distances de Hamming tuile à tuile entre deux grilles d'empreintes.
    Lève ``ValueError`` si les grilles n'ont pas le même nombre de tuiles."""
    if len(tiles_a) != len(tiles_b):
        raise ValueError(
            "grilles de tailles différentes (%d vs %d tuiles), même découpage requis"
            % (len(tiles_a), len(tiles_b)))
    return [hamming_distance(a, b) for a, b in zip(tiles_a, tiles_b, strict=True)]
