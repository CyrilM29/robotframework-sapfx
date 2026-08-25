"""Sémantique *snapshot* des baselines visuelles, partagée ECC ↔ Fiori.

Le cycle est toujours le même, quel que soit le canal de capture (fenêtre SAP
GUI via ``HardCopyToMemory``, page Fiori via la bibliothèque Browser, région
d'un élément découpée) :

* premier passage (aucune baseline ``<name>.png``) : la capture devient la
  baseline : l'appelant journalise un WARNING, le test passe (PNG à committer
  s'il fait référence) ;
* passages suivants : distance de Hamming entre le hash perceptuel de la
  capture et celui **recalculé depuis le PNG** de la baseline ; au-delà du
  seuil, échec auto-corrigible : distance mesurée, chemins de la baseline et
  de la capture ``<name>.actual.png`` sauvée à côté, et le remède (supprimer
  la baseline si le changement est voulu).

Une empreinte perceptuelle encode la **géométrie de capture** autant que le
contenu : la même fenêtre SAP rendue en 1920x1032 puis en 4676x2454 dérive de
plusieurs bits à contenu strictement identique. D'où deux dispositifs ici :
le message d'échec **nomme les deux géométries** quand elles diffèrent (une
dérive d'échelle ne doit pas se lire comme une régression fonctionnelle), et
``per_resolution=True`` garde **une baseline par géométrie**
(``<name>@<largeur>x<hauteur>.png``), ce qui rend une même suite comparable
sur des postes qui n'affichent pas pareil.

Ce module porte cette sémantique UNE fois (fichiers + décision + message) ;
le décodage image reste passé en ``decode`` par l'appelant (Pillow à la
frontière, stubbable en test ; voir :func:`decode_image_to_gray`, l'impl
partagée). Aucune dépendance Robot/COM/navigateur : utilisable des deux côtés.
"""
from __future__ import annotations

import os
import re
from typing import Callable, List, NamedTuple, Optional, Tuple

from .visual_hash import HASH_SIZE, dhash_hex, hamming_distance

# Matrice de gris (lignes de valeurs 0..255) : la monnaie de visual_hash.
GrayImage = List[List[int]]

# Seuil par défaut : 5 bits sur 64, tolère l'anticrénelage/thème, signale un
# vrai changement local. Le même que la sentinelle (screen_watch).
THRESHOLD = 5

_SNAPSHOT_NAME = re.compile(r"^[A-Za-z0-9._-]+$")

_TRUTHY = ("1", "true", "yes", "on")


def _truthy(value: object) -> bool:
    """Booléen Robot-friendly : un argument non annoté arrive en chaîne, et
    « False » est truthy en Python (le piège classique). La coercition vit ici
    pour que les deux bibliothèques aient la MÊME règle sans la recopier."""
    if isinstance(value, str):
        return value.strip().lower() in _TRUTHY
    return bool(value)


class BaselineOutcome(NamedTuple):
    """Résultat d'une assertion snapshot : distance mesurée (0 si la baseline
    vient d'être créée), création éventuelle, chemins en jeu, et la géométrie
    de la capture (celle qui conditionne la comparaison)."""
    distance: int
    created: bool
    baseline_path: str
    actual_path: Optional[str] = None
    geometry: Optional[Tuple[int, int]] = None


def validate_snapshot_name(name: object, kind: str = "baseline") -> str:
    """Valide un nom de snapshot destiné à devenir un nom de fichier
    (anti path-traversal : lettres/chiffres/._- uniquement). Retourne le nom
    nettoyé ; lève ``ValueError`` sinon. ``kind`` personnalise le message
    (« baseline », « surveillance »…)."""
    safe = str(name).strip()
    if not safe or not _SNAPSHOT_NAME.match(safe):
        raise ValueError(
            "Nom de %s invalide '%s' : lettres/chiffres/._- uniquement "
            "(le nom devient un nom de fichier)." % (kind, name))
    return safe


def geometry_of(image: GrayImage) -> Tuple[int, int]:
    """Géométrie ``(largeur, hauteur)`` d'une matrice de gris décodée : ce que
    l'empreinte perceptuelle encode implicitement, à côté du contenu."""
    height = len(image)
    width = len(image[0]) if height else 0
    return width, height


def format_geometry(geometry: Tuple[int, int]) -> str:
    """``(1920, 1032)`` → ``'1920x1032'`` : la forme lisible ET la forme
    utilisée dans le nom de fichier d'une baseline par géométrie."""
    return "%dx%d" % (int(geometry[0]), int(geometry[1]))


def variant_path(directory: str, name: str, geometry: Tuple[int, int]) -> str:
    """Chemin de la baseline PROPRE à une géométrie de capture,
    ``<name>@<largeur>x<hauteur>.png``. Le séparateur ``@`` est interdit dans
    un nom de snapshot (:func:`validate_snapshot_name`) : une variante ne peut
    donc jamais entrer en collision avec une baseline nommée par l'appelant."""
    return os.path.join(directory, "%s@%s.png" % (name, format_geometry(geometry)))


def existing_geometries(directory: str, name: str) -> List[str]:
    """Géométries pour lesquelles une baseline ``<name>@LxH.png`` existe déjà,
    triées. Sert à rendre l'échec bavard : « voici les postes déjà connus »."""
    prefix, found = "%s@" % name, []
    try:
        entries = os.listdir(directory)
    except OSError:      # répertoire pas encore créé : aucune variante
        return []
    for entry in entries:
        if (entry.startswith(prefix) and entry.endswith(".png")
                and not entry.endswith(".actual.png")):
            found.append(entry[len(prefix):-len(".png")])
    return sorted(found)


def _baseline_path_for(directory: str, name: str, geometry: Tuple[int, int],
                       per_resolution: bool,
                       decode: Callable[[bytes], GrayImage]) -> str:
    """Décide CONTRE QUEL fichier la capture sera comparée.

    Sans ``per_resolution`` : la baseline historique ``<name>.png``, quelle que
    soit sa géométrie (comportement d'origine, un poste de référence).
    Avec : la variante de la géométrie courante si elle existe ; sinon la
    baseline historique **à condition qu'elle ait la même géométrie** (une
    baseline déjà committée reste donc valable et n'est pas dupliquée) ; sinon
    la variante, qui sera créée au premier passage sur ce poste."""
    plain = os.path.join(directory, "%s.png" % name)
    if not per_resolution:
        return plain
    variant = variant_path(directory, name, geometry)
    if os.path.exists(variant):
        return variant
    if os.path.exists(plain):
        with open(plain, "rb") as fh:
            if geometry_of(decode(fh.read())) == geometry:
                return plain
    return variant


def describe_geometry_mismatch(reference_geometry: Optional[Tuple[int, int]],
                               geometry: Optional[Tuple[int, int]],
                               reference: str = "baseline") -> str:
    """La phrase qui évite de lire une dérive d'ÉCHELLE comme une régression
    fonctionnelle, PARTAGÉE par les assertions snapshot et la sentinelle (leurs
    remèdes diffèrent, ce constat non). Vide si les deux géométries coïncident
    ou si l'une n'est pas connue."""
    if (reference_geometry is None or geometry is None
            or reference_geometry == geometry):
        return ""
    return ("Géométries différentes : %s %s, capture %s. Une empreinte "
            "perceptuelle encode l'échelle autant que le contenu, donc cette "
            "dérive peut n'être QUE de résolution (le canal structurel, lui, "
            "ne bougerait pas : le vérifier avant de conclure).\n"
            % (reference, format_geometry(reference_geometry),
               format_geometry(geometry)))


def _geometry_note(baseline_geometry: Tuple[int, int],
                   geometry: Tuple[int, int], name: str, directory: str,
                   per_resolution: bool) -> str:
    """Le paragraphe complet des assertions snapshot : le constat partagé, plus
    le remède et les géométries déjà connues pour ce nom."""
    note = describe_geometry_mismatch(baseline_geometry, geometry)
    if not note:
        return ""
    if not per_resolution:
        note += ("Pour comparer chaque poste à sa propre référence : "
                 "per_resolution=True (une baseline par géométrie, "
                 "'%s@%s.png').\n" % (name, format_geometry(geometry)))
    known = existing_geometries(directory, name)
    if known:
        note += ("Baselines par géométrie déjà connues pour '%s' : %s.\n"
                 % (name, ", ".join(known)))
    return note


def match_baseline(name: str, png_bytes: bytes,
                   decode: Callable[[bytes], GrayImage],
                   directory: str, threshold: int = THRESHOLD,
                   hash_size: int = HASH_SIZE,
                   what: str = "L'écran",
                   per_resolution: object = False) -> BaselineOutcome:
    """Assertion snapshot d'une capture PNG contre sa baseline sur disque.

    ``decode`` : PNG → matrice de gris (la frontière image de l'appelant).
    ``what`` : le sujet du message d'échec (« L'écran », « L'élément <id> »…).
    Première passe : écrit la baseline, retourne ``created=True`` (à
    l'appelant de journaliser le WARNING). Dérive au-delà de ``threshold`` :
    sauve ``<name>.actual.png`` et lève ``AssertionError`` auto-corrigible.
    Le hash de la baseline est recalculé depuis son PNG à chaque assertion :
    changer ``hash_size`` (ou le masque appliqué dans ``decode``) reste
    honnête : les deux côtés passent par le même pipeline.

    ``per_resolution=True`` : une baseline par **géométrie de capture**
    (``<name>@1920x1032.png``), à committer comme les autres. Un poste dont la
    géométrie n'a pas encore de référence en crée une au premier passage au
    lieu d'échouer sur une dérive d'échelle ; une baseline ``<name>.png`` déjà
    committée reste utilisée telle quelle tant que la géométrie coïncide. Le
    masquage de zones volatiles y gagne aussi : un masque est un rectangle en
    pixels, il n'a de sens qu'à géométrie constante."""
    safe = validate_snapshot_name(name)
    hash_size = int(hash_size)
    threshold = int(threshold)
    directory = os.path.abspath(str(directory))
    # Décodage AVANT toute écriture : échec tôt (Pillow absent, image
    # invalide) plutôt qu'une baseline incomparable créée sur disque.
    pixels = decode(png_bytes)
    geometry = geometry_of(pixels)
    per_geometry = _truthy(per_resolution)
    baseline_path = _baseline_path_for(directory, safe, geometry,
                                       per_geometry, decode)
    if not os.path.exists(baseline_path):
        os.makedirs(directory, exist_ok=True)
        with open(baseline_path, "wb") as fh:
            fh.write(png_bytes)
        return BaselineOutcome(distance=0, created=True,
                               baseline_path=baseline_path, geometry=geometry)
    with open(baseline_path, "rb") as fh:
        baseline_png = fh.read()
    baseline_pixels = decode(baseline_png)
    distance = hamming_distance(dhash_hex(pixels, hash_size),
                                dhash_hex(baseline_pixels, hash_size))
    if distance > threshold:
        actual_path = "%s.actual.png" % baseline_path[:-len(".png")]
        with open(actual_path, "wb") as fh:
            fh.write(png_bytes)
        raise AssertionError(
            "%s a dérivé visuellement de la baseline '%s' : distance "
            "de Hamming %d > seuil %d (%d bits).\n  baseline : %s\n  "
            "capture  : %s\n%sSi le changement est voulu, supprimer la "
            "baseline pour la régénérer au prochain passage."
            % (what, safe, distance, threshold, hash_size * hash_size,
               baseline_path, actual_path,
               _geometry_note(geometry_of(baseline_pixels), geometry, safe,
                              directory, per_geometry)))
    return BaselineOutcome(distance=distance, created=False,
                           baseline_path=baseline_path, geometry=geometry)


def decode_image_to_gray(image_bytes: bytes) -> GrayImage:
    """PNG/JPEG/BMP → matrice de gris : la frontière image PARTAGÉE des deux
    canaux (les keywords l'exposent en ``_decode_image_to_gray`` stubbable).
    Pillow est importé ICI seulement : l'assertion visuelle est opt-in (extra
    ``visual``), le reste des bibliothèques n'en dépend jamais."""
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError(
            "L'assertion visuelle a besoin de Pillow pour décoder la "
            "capture : pip install Pillow (extra 'visual' du paquet "
            "robotframework-sapfx).")
    import io
    image = Image.open(io.BytesIO(image_bytes)).convert("L")
    width, height = image.size
    data = list(image.getdata())
    return [data[y * width:(y + 1) * width] for y in range(height)]
