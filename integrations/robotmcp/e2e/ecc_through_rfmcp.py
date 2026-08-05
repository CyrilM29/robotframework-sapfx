"""Smoke END-TO-END ECC *à travers* rf-mcp (validation rejouable, SAP live requis).

Pilote les vrais handlers de tools rf-mcp (manage_session / execute_step) en
process, comme un agent via MCP, contre un SAP GUI desktop **live** (ABAP Platform
A4H en Docker). Valide dans le pipeline réel :

  * la découverte du plugin SapEccPlugin ;
  * une session qui importe SapEccLibrary + la resource métier ecc_keywords ;
  * le login complet (Open SAP And Log In) via COM ;
  * le routing des keywords (Run Transaction, Get Current Transaction) ;
  * le keyword de perception **Get Screen Signature** exécuté à travers rf-mcp ;
  * **le state provider** : appel direct de EccStateProvider.get_page_source sur la
    session live, ce que rf-mcp fait pour donner l'écran à l'agent. Le provider
    exécute "Get Screen Signature" dans le contexte RF natif (run_keyword_in_context).

Prérequis : A4H Docker démarré + scripting activé. Connexion par variables (les
mêmes que ecc_smoke.robot). Lancer depuis la racine du dépôt :

    python integrations/robotmcp/e2e/ecc_through_rfmcp.py
"""
import asyncio
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "src"))

import robotmcp.server as srv  # noqa: E402
from robotmcp.plugins import get_library_plugin_manager  # noqa: E402

from _common import Checks, out as _out, show, step as _step  # noqa: E402

SID = "ecc_e2e"
RESOURCE = os.path.join(_ROOT, "resources", "ecc_keywords.resource")
CONN = os.environ.get("SAP_CONNECTION", "/H/vhcala4hci/S/3200")
# Défauts = identifiants publics du trial ABAP Platform A4H (documentés par SAP,
# pas un secret) : voir docs/ecc-validation.md. Surchargeables par env pour ne
# jamais coder en dur de vrais identifiants d'un système non-trial.
USER = os.environ.get("SAP_USER", "DEVELOPER")
PWD = os.environ.get("SAP_PASSWORD", "Htods70334")
CLIENT = os.environ.get("SAP_CLIENT", "001")
LANG = os.environ.get("SAP_LANGUAGE", "EN")

checks = Checks()
check = checks.check


async def step(kw, args=None, **kw2):
    return await _step(srv, SID, kw, args, **kw2)


async def main():
    print("== init session : SapEccLibrary + resource métier ==")
    init = show("init", await srv.manage_session(
        action="init", session_id=SID, libraries=["SapEccLibrary"]))
    check("session initialisée", init.get("success"))
    show("import_resource", await srv.manage_session(
        action="import_resource", session_id=SID, resource_path=RESOURCE))

    print("\n== login complet via le keyword métier (COM) ==")
    login = await step("Open SAP And Log In", [CONN, USER, PWD, CLIENT, LANG])
    check("login exécuté via rf-mcp", login.get("success"))
    tx = _out(await step("Get Current Transaction"))
    check("atterri sur SESSION_MANAGER", "SESSION_MANAGER" in tx)

    print("\n== perception : Get Screen Signature (routé -> SapEccLibrary) ==")
    sig = _out(await step("Get Screen Signature"))
    check("signature d'écran (# screen …)", sig.startswith("# screen"))
    check("signature non triviale (>3 lignes)", sig.count("\n") >= 3)

    print("\n== routing : Run Transaction SE16 ==")
    await step("Run Transaction", ["SE16"])
    tx2 = _out(await step("Get Current Transaction"))
    check("transaction active = SE16", tx2.strip() == "SE16")

    print("\n== STATE PROVIDER : EccStateProvider.get_page_source(session live) ==")
    session = srv.execution_engine.session_manager.get_session(SID)
    provider = get_library_plugin_manager().get_state_provider("SapEccLibrary")
    check("provider SapEccLibrary trouvé", provider is not None)
    ps = await provider.get_page_source(session)
    print("   provider ->", {k: (str(v)[:60] + "…" if isinstance(v, str) and len(v) > 60 else v)
                              for k, v in (ps or {}).items()})
    check("provider success", isinstance(ps, dict) and ps.get("success"))
    check("provider page_source = signature SE16",
          isinstance(ps, dict) and "# screen" in str(ps.get("page_source", "")))

    print("\n== cleanup ==")
    await step("Close SAP")

    return checks.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
