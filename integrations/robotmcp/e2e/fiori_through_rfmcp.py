"""Smoke END-TO-END Fiori *à travers* rf-mcp (validation rejouable).

On pilote les VRAIS handlers de tools de rf-mcp (manage_session / execute_step /
get_session_state) en process — exactement ce qu'un agent ferait via MCP. Cela
valide, dans le pipeline réel :

  * la découverte du plugin SapFioriPlugin par rf-mcp ;
  * une session qui importe Browser ET SapFioriLibrary dans un SEUL contexte RF ;
  * le routing des keywords SAP (Get Ui5 Page Tree, Click Ui5 Control) ;
  * la perception (arbre de contrôles UI5) ;
  * l'action (clic) ;
  * et surtout la dépendance Browser satisfaite : SapFioriLibrary réutilise
    l'instance Browser vivante du même contexte (get_library_instance).

Cible : le fixture UI5 local du projet (déterministe, pas de bandeau cookies).

Prérequis (déjà provisionnés sur la machine de dev, cf. CLAUDE.md) : rf-mcp,
robotframework-browser + `rfbrowser init`, et `pip install -e integrations/robotmcp`
(ou un manifeste .robotmcp/plugins/) pour que rf-mcp découvre le plugin.

Lancer depuis la racine du dépôt :
    python integrations/robotmcp/e2e/fiori_through_rfmcp.py
Sortie : "N/8 checks OK" + code retour 0 si tout passe.

NB côté ECC : l'équivalent (Run Transaction / Get Screen Signature via le state
provider) nécessite l'ABAP Platform A4H en Docker — non couvert ici.
"""
import asyncio
import os
import sys

# Racine du dépôt = parents de integrations/robotmcp/e2e/
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "src"))  # rendre SapFioriLibrary importable

import robotmcp.server as srv  # noqa: E402

from _common import Checks, num as _num, out as _out, show, step as _step  # noqa: E402

SID = "fiori_e2e"
FIXTURE = os.path.join(_ROOT, "tests", "robot", "fixtures", "ui5_fixture.html")
URL = "file:///" + FIXTURE.replace("\\", "/")

checks = Checks()
check = checks.check


async def step(kw, args=None, **kw2):
    return await _step(srv, SID, kw, args, **kw2)


async def main():
    print("== init session : Browser + SapFioriLibrary ==")
    init = show("init", await srv.manage_session(
        action="init", session_id=SID, libraries=["Browser", "SapFioriLibrary"]))
    check("session initialisée", init.get("success"))

    print("\n== page Fiori (fixture local) ==")
    await step("New Browser", ["chromium", "headless=True"])
    await step("New Page", [URL])
    wf = await step("Wait For Function", ["() => window.__fixtureReady === true", "timeout=30s"])
    check("fixture UI5 prête", wf.get("success"))

    print("\n== perception : Get Ui5 Page Tree (routé -> SapFioriLibrary) ==")
    tree = _out(await step("Get Ui5 Page Tree", []))
    check("tree non vide <UI5Tree…>", tree.lstrip().startswith("<UI5Tree") and len(tree) > 30)
    check("tree contient une Table", "Table" in tree)
    n_btn = _num(await step("Get Ui5 Match Count",
                            ["controlType=Button", "properties={'text': 'Open Dialog'}"]))
    check("bouton 'Open Dialog' perçu (match count >= 1)", bool(n_btn) and n_btn >= 1)

    print("\n== action : Click Ui5 Control (Button 'Open Dialog') ==")
    clk = await step("Click Ui5 Control",
                     ["controlType=Button", "properties={'text': 'Open Dialog'}"])
    check("click routé + exécuté via Browser", clk.get("success"))

    print("\n== effet : le dialogue est apparu (résolution du Dialog) ==")
    n_dlg = _num(await step("Get Ui5 Match Count", ["controlType=sap.m.Dialog"]))
    check("le clic a ouvert le Dialog (match count >= 1)", bool(n_dlg) and n_dlg >= 1)

    print("\n== get_session_state ==")
    st = await srv.get_session_state(session_id=SID)
    check("session_state renvoyé", isinstance(st, dict) and bool(st))

    await step("Close Browser")

    return checks.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
