"""Vérification de connectivité SAP GUI — sans serveur (test manuel, hors CI).

Valide en live le « pont » de SapEccLibrary contre le client **SAP GUI for Windows**
installé localement, *avant même* de disposer d'un système : lancement de
`saplogon.exe`, présence de l'objet COM `SAPGUI` dans la Running Object Table, et
`GetScriptingEngine` (qui échoue si le scripting client est désactivé).

Ce script n'est PAS collecté par `pytest` (il est hors de `tests/unit`, exige
Windows + SAP GUI + pywin32, et ouvre une fenêtre). Lancement manuel :

    python tests/manual/check_sap_gui_connection.py

Sortie attendue si tout est bon : « OK : ... validees en live ». S'il affiche
« scripting probablement desactive », activer le scripting côté client
(SAP Logon → Options → Accessibility & Scripting → Scripting → Enable) — cf.
docs/ecc-validation.fr.md §7.
"""
import os
import subprocess
import sys
import time

try:
    import pythoncom
    import win32com.client
    from pythoncom import com_error
except ImportError:
    print("pywin32 requis (Windows uniquement) : pip install pywin32")
    sys.exit(1)

# Chemins standards (SAP GUI 8.x 64-bit puis 7.x 32-bit).
_SAPLOGON_PATHS = (
    r"C:\Program Files\SAP\FrontEnd\SAPgui\saplogon.exe",
    r"C:\Program Files (x86)\SAP\FrontEnd\SAPGUI\saplogon.exe",
)


def _saplogon_path():
    for p in (os.environ.get("SAPLOGON_PATH"),) + _SAPLOGON_PATHS:
        if p and os.path.isfile(p):
            return p
    return None


def _find_sapgui():
    """Cherche l'objet COM 'SAPGUI' dans la Running Object Table."""
    rot = pythoncom.GetRunningObjectTable()
    rotenum = rot.EnumRunning()
    while True:
        monikers = rotenum.Next()
        if not monikers:
            break
        ctx = pythoncom.CreateBindCtx(0)
        name = monikers[0].GetDisplayName(ctx, None)
        if name.endswith("SAPGUI"):
            obj = rot.GetObject(monikers[0])
            return win32com.client.Dispatch(obj.QueryInterface(pythoncom.IID_IDispatch))
    return None


def main():
    exe = _saplogon_path()
    print("[1] saplogon.exe :", exe or "INTROUVABLE")
    if not exe:
        print("ECHEC : SAP GUI for Windows ne semble pas installe.")
        return 1

    sapgui = _find_sapgui()
    if sapgui is None:
        print("[2] SAPGUI absent de la ROT -> lancement de SAP Logon...")
        subprocess.Popen([exe], close_fds=True)
        for i in range(40):
            time.sleep(1.5)
            sapgui = _find_sapgui()
            if sapgui is not None:
                print("[2] objet SAPGUI trouve apres %.0fs" % ((i + 1) * 1.5))
                break
    else:
        print("[2] objet SAPGUI deja present dans la ROT")

    if sapgui is None:
        print("ECHEC : SAP Logon n'a pas enregistre l'objet SAPGUI dans la ROT.")
        return 2

    print("[3] GetScriptingEngine...")
    try:
        engine = sapgui.GetScriptingEngine
    except com_error as err:
        print("ECHEC : scripting probablement desactive cote client.")
        print("   ", err)
        print("   -> activer : SAP Logon > Options > Accessibility & Scripting > Scripting")
        return 3

    print("[4] Moteur attache. GuiApplication :")
    print("    - a OpenConnection  :", hasattr(engine, "OpenConnection"))
    try:
        print("    - Connections.Count :", engine.Connections.Count)
    except Exception:
        pass
    for attr in ("MajorVersion", "MinorVersion", "Revision", "Patchlevel"):
        try:
            print("    - %-14s:" % attr, getattr(engine, attr))
        except Exception:
            pass
    print("OK : ouverture SAP GUI + attache COM au moteur de scripting validees en live.")
    print("    (La manipulation d'ecrans necessite en plus une session connectee a un systeme.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
