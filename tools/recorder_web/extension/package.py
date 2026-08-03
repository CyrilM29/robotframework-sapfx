"""Construit un .zip publiable de l'extension (Chrome Web Store / Edge Add-ons).

Run:  python tools/recorder_web/extension/package.py
Produit dist/ui5-recorder-extension-<version>.zip avec uniquement les fichiers
d'exécution (manifest, popup, recorder.js généré, icônes). Régénérer recorder.js /
les icônes au préalable :
  python -m SapFioriLibrary.regen_recorder
  python tools/recorder_web/extension/gen_icons.py
"""
import json
import os
import zipfile

_DIR = os.path.dirname(__file__)
# Fichiers d'exécution inclus dans le paquet du store (helpers réservés au développement exclus).
_INCLUDE = [
    "manifest.json", "popup.html", "popup.js", "recorder.js",
    "background.js", "bridge.js",
    "icon16.png", "icon48.png", "icon128.png",
]


def main():
    with open(os.path.join(_DIR, "manifest.json"), encoding="utf-8") as fh:
        version = json.load(fh)["version"]
    missing = [f for f in _INCLUDE if not os.path.isfile(os.path.join(_DIR, f))]
    if missing:
        raise SystemExit("Missing files (run regen_recorder / gen_icons first): %s" % missing)

    dist = os.path.join(_DIR, "dist")
    os.makedirs(dist, exist_ok=True)
    out = os.path.join(dist, "ui5-recorder-extension-%s.zip" % version)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in _INCLUDE:
            z.write(os.path.join(_DIR, name), name)
    print("Wrote %s (%d files)" % (out, len(_INCLUDE)))


if __name__ == "__main__":
    main()
