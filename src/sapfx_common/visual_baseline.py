"""Sémantique *snapshot* des baselines visuelles, partagée ECC ↔ Fiori.

Le cycle est toujours le même, quel que soit le canal de capture (fenêtre SAP
GUI via ``HardCopyToMemory``, page Fiori via la bibliothèque Browser, région
d'un élément découpée) :

* premier passage (aucune baseline ``<name>.png``) : la capture devient la
  baseline — l'appelant journalise un WARNING, le test passe (PNG à committer
  s'il fait référence) ;
* passages suivants : distance de Hamming entre le hash perceptuel de la
  capture et celui **recalculé depuis le PNG** de la baseline ; au-delà du
  seuil, échec auto-corrigible — distance mesurée, chemins de la baseline et
  de la capture ``<name>.actual.png`` sauvée à côté, et le remède (supprimer
  la baseline si le changement est voulu).

Ce module porte cette sémantique UNE fois (fichiers + décision + message) ;
le décodage image reste passé en ``decode`` par l'appelant (Pillow à la
frontière, stubbable en test — voir :func:`decode_image_to_gray`, l'impl
partagée). Aucune dépendance Robot/COM/navigateur : utilisable des deux côtés.
"""
from __future__ import annotations

import os
import re
from typing import Callable, List, NamedTuple, Optional

from .visual_hash import HASH_SIZE, dhash_hex, hamming_distance

# Matrice de gris (lignes de valeurs 0..255) — la monnaie de visual_hash.
GrayImage = List[List[int]]

# Seuil par défaut : 5 bits sur 64 — tolère l'anticrénelage/thème, signale un
# vrai changement local. Le même que la sentinelle (screen_watch).
THRESHOLD = 5

_SNAPSHOT_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class BaselineOutcome(NamedTuple):
    """Résultat d'une assertion snapshot : distance mesurée (0 si la baseline
    vient d'être créée), création éventuelle, chemins en jeu."""
    distance: int
    created: bool
    baseline_path: str
    actual_path: Optional[str] = None


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


def match_baseline(name: str, png_bytes: bytes,
                   decode: Callable[[bytes], GrayImage],
                   directory: str, threshold: int = THRESHOLD,
                   hash_size: int = HASH_SIZE,
                   what: str = "L'écran") -> BaselineOutcome:
    """Assertion snapshot d'une capture PNG contre sa baseline sur disque.

    ``decode`` : PNG → matrice de gris (la frontière image de l'appelant).
    ``what`` : le sujet du message d'échec (« L'écran », « L'élément <id> »…).
    Première passe : écrit la baseline, retourne ``created=True`` (à
    l'appelant de journaliser le WARNING). Dérive au-delà de ``threshold`` :
    sauve ``<name>.actual.png`` et lève ``AssertionError`` auto-corrigible.
    Le hash de la baseline est recalculé depuis son PNG à chaque assertion :
    changer ``hash_size`` (ou le masque appliqué dans ``decode``) reste
    honnête — les deux côtés passent par le même pipeline."""
    safe = validate_snapshot_name(name)
    hash_size = int(hash_size)
    threshold = int(threshold)
    directory = os.path.abspath(str(directory))
    baseline_path = os.path.join(directory, "%s.png" % safe)
    if not os.path.exists(baseline_path):
        decode(png_bytes)   # échec tôt (Pillow absent, image invalide) : ne pas
        os.makedirs(directory, exist_ok=True)   # créer une baseline incomparable
        with open(baseline_path, "wb") as fh:
            fh.write(png_bytes)
        return BaselineOutcome(distance=0, created=True,
                               baseline_path=baseline_path)
    actual_hash = dhash_hex(decode(png_bytes), hash_size)
    with open(baseline_path, "rb") as fh:
        baseline_png = fh.read()
    baseline_hash = dhash_hex(decode(baseline_png), hash_size)
    distance = hamming_distance(actual_hash, baseline_hash)
    if distance > threshold:
        actual_path = os.path.join(directory, "%s.actual.png" % safe)
        with open(actual_path, "wb") as fh:
            fh.write(png_bytes)
        raise AssertionError(
            "%s a dérivé visuellement de la baseline '%s' : distance "
            "de Hamming %d > seuil %d (%d bits).\n  baseline : %s\n  "
            "capture  : %s\nSi le changement est voulu, supprimer la "
            "baseline pour la régénérer au prochain passage."
            % (what, safe, distance, threshold, hash_size * hash_size,
               baseline_path, actual_path))
    return BaselineOutcome(distance=distance, created=False,
                           baseline_path=baseline_path)


def decode_image_to_gray(image_bytes: bytes) -> GrayImage:
    """PNG/JPEG/BMP → matrice de gris — la frontière image PARTAGÉE des deux
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
