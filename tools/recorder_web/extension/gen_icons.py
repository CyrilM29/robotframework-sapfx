"""Régénère les icônes de l'extension à partir du logo du projet (``assets/logo.png``).

Le master committé (512×512, médaillon détouré sur fond transparent) est décliné :

- ``icon48.png`` / ``icon128.png`` — la médaille complète, simplement redimensionnée ;
- ``icon16.png`` — à cette taille la médaille est illisible : on recadre sur le
  cadran rond du visage du robot (~30 % central), masque circulaire, contraste et
  netteté légèrement renforcés ;
- ``../../recorder/assets/icon.png`` (256×256) — l'icône de fenêtre du lanceur
  Tkinter du recorder bureau, même source pour une identité visuelle unique.

Nécessite Pillow (outil de développement uniquement — les PNG générés sont
committés, rien n'en dépend à l'exécution).

Run:  python tools/recorder_web/extension/gen_icons.py
"""
import os

from PIL import Image, ImageDraw, ImageEnhance

_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_DIR, "..", "..", ".."))
LOGO = os.path.join(_REPO, "assets", "logo.png")
RECORDER_ICON = os.path.join(_REPO, "tools", "recorder", "assets", "icon.png")


def _face_icon(logo, size=16, crop_ratio=0.30):
    """Icône « visage » : crop central du cadran rond, masque circulaire anti-aliasé."""
    side = logo.size[0]
    face_side = int(side * crop_ratio)
    off = (side - face_side) // 2
    face = logo.crop((off, off, off + face_side, off + face_side))
    big = face_side * 4
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, big - 1, big - 1), fill=255)
    face.putalpha(mask.resize((face_side, face_side), Image.LANCZOS))
    face = ImageEnhance.Contrast(face).enhance(1.25)
    out = face.resize((size, size), Image.LANCZOS)
    return ImageEnhance.Sharpness(out).enhance(1.5)


def main():
    logo = Image.open(LOGO).convert("RGBA")

    for size in (48, 128):
        path = os.path.join(_DIR, "icon%d.png" % size)
        logo.resize((size, size), Image.LANCZOS).save(path, optimize=True)
        print("Wrote %s" % path)

    path16 = os.path.join(_DIR, "icon16.png")
    _face_icon(logo).save(path16, optimize=True)
    print("Wrote %s" % path16)

    os.makedirs(os.path.dirname(RECORDER_ICON), exist_ok=True)
    logo.resize((256, 256), Image.LANCZOS).save(RECORDER_ICON, optimize=True)
    print("Wrote %s" % RECORDER_ICON)


if __name__ == "__main__":
    main()
