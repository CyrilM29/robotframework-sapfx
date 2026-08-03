> **🇬🇧 English** · [🇫🇷 Français](README.fr.md)

# rf-mcp plugins for the SAP ecosystem

> Quick start. For the detailed design and usage, see the canonical doc:
> [docs/mcp-integration.md](../../docs/mcp-integration.md)
> ([FR](../../docs/mcp-integration.fr.md)).

Integrates this repo with **[rf-mcp / RobotMCP](https://github.com/manykarim/rf-mcp)**
(an MCP server for Robot Framework) instead of rewriting an MCP. rf-mcp already
provides the whole generic layer: keyword discovery, live execution, suite
generation, memory, and a *Debug Attach Bridge* for in-IDE assistance.

This package only fills **the one gap**: **SAP** perception and guidance, which
rf-mcp knows nothing about (its `get_locator_guidance` only covers Browser/Selenium/Appium).
Three plugins, one per channel: `SapEccPlugin` (desktop GUI), `SapFioriPlugin`
(Fiori/UI5 web) and `SapApiPlugin` (OData/RFC — a channel with no screen: its
page source is an honest explanation, its application state the real channel
state via `List Api Sessions`, never credentials).

## What the plugins add

| rf-mcp hook | SAP contribution |
| --- | --- |
| `get_state_provider()` | Perception: the ECC **screen signature** (via the `Get Screen Signature` keyword, run in the live RF context) exposed as the session's "page source". The agent *sees* the screen before acting. |
| `get_hints()` / `get_prompt_bundle()` | SAP selector guidance: UI5 controls ≠ DOM ids, status-bar message type ≠ localized text, never `time.sleep`, business vocabulary from `resources/`; plus the 0.2.0 agent workflow (preflight in Suite Setup, `mode=diff` perception, healing keywords on locator failures, `Set Ui5 Frame` for launchpad iframes). |
| `get_keyword_library_map()` | Routes `Click Ui5 Control`, `Run Transaction`, etc. to the libs — including the 0.2.0 keywords (`Scripting Should Be Fully Enabled`, `Get Session Telemetry`, `Resolve Element With Healing`, `Resolve Ui5 With Fallback`, `Set Ui5 Frame`, `Ui5 Text Should Be`). |

The plugins themselves create no MCP tool (the plugin contract does not allow
it): the agent reads the state via `get_session_state` then calls the SAP
keywords directly. What the 0.31 contract **cannot** express is added by the
**`sapfx-mcp` overlay** — a console entry point of this same wheel that mounts
the rf-mcp server unchanged and adds `sapfx_state` (state providers called
directly: diff-by-default page source, enriched application state),
`sapfx_screenshot` (real MCP image content, plain or Set-of-Mark annotated)
and `sapfx_reload` (plugin-layer hot-reload), behind a startup compatibility
guard. See [docs/mcp-integration.md](../../docs/mcp-integration.md).

### Fiori subtlety (verified in the rf-mcp code)

rf-mcp only invokes the page-source `state_provider` for the **active web
library**, which resolves to **Browser** (SapFioriLibrary does not drive the page,
it reuses Browser's). The builtin Browser provider therefore wins. UI5 perception
goes through a **keyword** the agent calls (`Get Ui5 Page Tree`) plus the hints
that steer it there — not through the provider. On the **ECC** side, SapEccLibrary
*is* the active lib: its provider is indeed consulted.

## Security notes

- **No tcode allowlist.** `Run Transaction`/`Send Vkey`/`Input Text` are routed to
  the agent with no allow/deny-list — an agent driving SAP through this plugin has
  exactly the SAP user's own authorizations (it can invoke `SU01`, `SM49`, `SE38`,
  etc.). This is intentional (the tool's purpose is full test automation), but
  worth knowing before pointing an LLM agent at a non-trial system: don't give the
  driving SAP user broader authorizations than the tests actually need.
- **Entry-point registration has no built-in namespacing.** The plugins register
  under the `robotmcp.library_plugins` entry-point group (`pyproject.toml`); any
  other installed package declaring the same group also loads into rf-mcp — a
  generic characteristic of Python's entry-point mechanism, not something this
  repo can fix from its own `pyproject.toml`. Only matters if an untrusted package
  is ever installed in the same environment, at which point entry-point hijacking
  is a secondary concern to the supply-chain compromise that got it installed.
- API stores and Fiori frame/perception state are partitioned by rf-mcp's
  `MCP_Test_<session_id>` context. Keep one live ECC session per process: rf-mcp
  0.31 can misattribute nested resource calls, so `SUITE` alone is insufficient.

## Installation

```bash
pip install rf-mcp                 # l'hôte
pip install -e .                   # à la RACINE du dépôt : rend SapEcc/SapFioriLibrary importables
pip install -e integrations/robotmcp   # enregistre les plugins (entry-points)
```

Verify discovery:

```bash
python -c "from robotmcp.config import library_registry as r; print(r.get_all_libraries())"
```

Install-free alternative: drop a manifest in `.robotmcp/plugins/` pointing to the
class (`{"module": "sap_robotmcp.fiori_plugin", "class": "SapFioriPlugin"}`).

## Status

- [x] Plugins conform to the **actual** rf-mcp 0.31.2 contract (`StaticLibraryPlugin`,
      `LibraryMetadata/Capabilities/Hints`, `PromptBundle`, exact `get_page_source`
      signature) — re-validated against **rf-mcp 0.35.0** on 2026-07-24
      (`plugins/contracts.py` and `plugins/manager.py` byte-identical between the
      two, `plugins/base.py` backwards-compatible addition only; the overlay's
      startup guard window in `sap_robotmcp/_compat.py` covers 0.31–0.35).
      Instantiation + guidance covered by `tests/test_plugins.py`
      (10/10, off-SAP, no live session).
- [x] `state_provider`s wired to the **real** RF-context pattern for reaching the
      live instance (`get_rf_native_context_manager().execute_keyword_with_context`),
      like the builtin Browser provider (`_rf_context.run_keyword_in_context`).
- [x] **Perception keywords** added to the libs (the providers call them), with
      off-SAP unit tests (`tests/unit/test_perception.py`):
  - `SapEccLibrary.Get Screen Signature` (mixin `keywords/_perception.py`): text view
    of the active screen (`# screen Prog/Tcode/Dynpro` header + relative ids,
    editable fields marked `*`).
  - `SapFioriLibrary.Get Ui5 Page Tree`: UI5 control tree serialized as XML
    (`dumpTree` method added to the `_ui5_js.py` bundle).
- [x] **End-to-end Fiori smoke *through* rf-mcp** (`e2e/fiori_through_rfmcp.py`,
      8/8): drives the real tools (`manage_session`/`execute_step`/`get_session_state`)
      in process. Validates plugin discovery, a **Browser + SapFioriLibrary** session
      in a single RF context, routing (`Get Ui5 Page Tree`, `Click Ui5 Control`),
      perception (populated UI5 tree) and action (click → Dialog opens) — hence the
      Browser dependency is satisfied. Target: the local UI5 fixture (deterministic).
- [x] **End-to-end ECC smoke *through* rf-mcp** (`e2e/ecc_through_rfmcp.py`, 9/9,
      against live A4H Docker): SapEccLibrary session + business resource, COM login,
      routing (`Run Transaction`/`Get Current Transaction`), `Get Screen Signature`
      perception, and above all the **state provider** called directly —
      `EccStateProvider.get_page_source` returns the real live SE16 screen signature
      (the provider executes the keyword in the native RF context). Required a
      `CoInitialize` on rf-mcp's execution thread (override in `keywords/_connection.py`).
- [x] **Perception compaction**: both state providers always re-query the real
      screen/tree (never a time-based cache — a stale state right after an action
      would break the perception-before-acting loop), but if the result is
      byte-identical to the previous call for that session, `page_source` is
      replaced by a compact marker and `unchanged_since_last_call: true` is set —
      saving the agent's context on repeated look-without-acting checks. See
      `_last_seen.py` (`tests/test_last_seen.py`, off-SAP).
- [x] **Perception filtering**: `get_page_source(filtered=True, filtering_level=...)`
      (declared by rf-mcp's own `LibraryStateProvider` contract, previously accepted
      but ignored) now actually reduces the response on busy SAP screens, mirroring
      the real Browser provider's minimal/standard/aggressive progression. ECC:
      `minimal` drops pure structural noise, `standard` also drops known layout
      container types, `aggressive` keeps only editable fields. Fiori: bottom-up
      pruning of non-interactive/non-textual leaves, never breaking the ancestor
      chain of any surviving node (XPath addressing stays valid). Filtering is
      always a post-processing step on the freshly-fetched perception — never a
      shortcut that skips querying the real screen. See `_filtering.py`
      (`tests/test_filtering.py`, 20 off-SAP tests).
