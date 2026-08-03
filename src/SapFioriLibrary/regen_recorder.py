"""Régénère le programme Recorder à partir du bundle JS (source unique de vérité).

Exécution :  python -m SapFioriLibrary.regen_recorder
Écrit le Recorder généré identique dans LES DEUX cibles :
  * tools/recorder_web/recorder_snippet.js     (collage dans la console DevTools)
  * tools/recorder_web/extension/recorder.js   (script de contenu pour extension navigateur)
depuis `_ui5_js.spy_snippet()`. `tests/unit/test_sid_and_spy.py` échoue si l'un ou
l'autre fichier archivé diverge de cette source.
"""
import os

from ._ui5_js import spy_snippet

_RECORDER_WEB = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "tools", "recorder_web"))

# Les deux artefacts générés partagent exactement le même contenu.
TARGETS = [
    os.path.join(_RECORDER_WEB, "recorder_snippet.js"),
    os.path.join(_RECORDER_WEB, "extension", "recorder.js"),
]


def main():
    content = spy_snippet()
    for target in TARGETS:
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        print("Wrote %s (%d bytes)" % (target, len(content)))


if __name__ == "__main__":
    main()
