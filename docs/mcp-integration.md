> **🇬🇧 English** · [🇫🇷 Français](mcp-integration.fr.md)

# MCP integration (rf-mcp plugins)

How this project exposes its SAP libraries to an AI agent over the **Model Context
Protocol**, so an LLM (e.g. Claude) can author and run SAP tests — and a human gets
the same assistance in an IDE.

## Positioning: the SAP MCP

A window is open on the market: SAP's own test tool (CBTA) dies with Solution
Manager 7.2 (2027-12-31) **with no announced successor**, and the only other
public "SAP over MCP" attempt is an unlicensed prototype without tests. This
project's `sap-robotmcp` package aims to be **the** reference way any MCP
client (Claude Code, Copilot agent mode, or a generic MCP host) touches SAP —
on guarantees none of the alternatives make:

- **Real perception, never optimistic** — every screen/state answer re-queries
  the live system (`Get Screen Signature`, `Get Ui5 Page Tree`,
  `get_application_state` reads the LIVE transaction); no state machine that
  *assumes* where the GUI is.
- **Never silent** — ambiguity fails with the candidate list; healing logs a
  WARNING plus a telemetry record; errors are auto-correctable (closest
  matches, scope diagnosis, HTTP body excerpts).
- **MCP-safe by construction** — keywords return strings/dicts, never COM
  objects across the boundary; screenshots as verified-MIME base64;
  API and Fiori mutable state is partitioned by rf-mcp session namespace.
- **Tested like a product** — the plugins ship with off-SAP unit tests, CI on
  two OSes, and end-to-end validations against a live A4H and live UI5 pages.
- **Apache-2.0**, with clean attribution of every ported technique.

Any MCP client can use the server with a declaration equivalent to
[`.mcp.json`](../.mcp.json) — launch `sapfx-mcp --transport stdio
--without-frontend` with `PYTHONPATH` covering `src` and
`integrations/robotmcp`; the SAP plugins register via entry points and the
`sapfx-mcp` console script is installed by the same
`pip install -e integrations/robotmcp`. The
package metadata is publication-ready (PyPI name `sap-robotmcp`); today's
distribution channels are this repo and the Windows deployment pack —
publishing to an index is a deliberate, separate decision.

## The `sapfx-mcp` overlay (not a fork)

`sapfx-mcp` mounts the rf-mcp server **unchanged** (every rf-mcp tool keeps
working as before) and adds the three tools the 0.31 plugin contract cannot
express — each gap was established live on 2026-07-23 (see the field notes in
`CLAUDE.md`):

- **`sapfx_state`** — session state served *directly* by the SAPFX state
  providers: `page_source` with the real differential semantics (an
  already-seen screen that changed returns a compact smart diff by default —
  through rf-mcp's own `get_session_state` the diff only triggers with
  `page_source_filtered=true`), and `application_state` enriched with the
  live window stack (`modal_open` — the leftover-error-modal trap), the
  status-message type and session telemetry, which rf-mcp never routes to
  plugin providers.
- **`sapfx_screenshot`** — the vision channel: a real MCP image (the plugin
  contract has no image channel; fastmcp does), plain or Set-of-Mark
  annotated with its `number -> id` legend as a companion text block.
- **`sapfx_reload`** — the live-validated plugin-layer hot-reload protocol
  (module reloads → plugin-manager reset → entry-point re-registration);
  the builtin `manage_library_plugins reload` alone serves cached instances.

A **compatibility guard** runs at startup: tested rf-mcp version window plus
a probe of every internal anchor the overlay touches; any mismatch refuses to
start with the exact list (`SAPFX_MCP_FORCE=1` overrides, loudly). The health
rule: every wiring accepted upstream must *shrink* this overlay — it must
never grow into a de-facto fork.

## Decision: compose above rf-mcp, don't build a new MCP

There is already a mature, generic MCP server for Robot Framework —
[**rf-mcp / RobotMCP**](https://github.com/manykarim/rf-mcp) (Apache-2.0). It covers
the whole generic surface: keyword discovery, live keyword execution, test-suite
generation (BDD / data-driven), semantic memory, and an HTTP *Debug Attach Bridge*
for IDE assistance. Rebuilding any of that would be wasted effort.

The **only** gap for us is SAP: rf-mcp's selector guidance only knows
Browser/Selenium/Appium, and it has no notion of UI5 controls, the WebGUI `sid`, or
the SAP GUI desktop screen. That gap is exactly this project's strength.

So instead of a standalone MCP — or merging the libraries into rf-mcp — we **compose
above it** with three plugins — one per channel. This mirrors the project's own architecture principle:
*don't merge paradigms at the technical layer, unify above* (see
[architecture.md](architecture.md)).

```text
  agent / IDE
      │  (MCP tools: manage_session, execute_step, get_session_state, …)
      ▼
  rf-mcp  ── generic RF engine: discovery, execution, suite gen, memory ──┐
      │                                                                    │
      │  loads plugins (entry-point: robotmcp.library_plugins)            │
      ▼                                                                    ▼
  SapEccPlugin / SapFioriPlugin / SapApiPlugin  ──▶  SapEcc / SapFiori / SapApi Library  ──▶  SAP
   (routing · perception · guidance)        (the actual keywords)
```

## What the plugins add

`integrations/robotmcp/sap_robotmcp/` — built on rf-mcp's real plugin contracts
(`StaticLibraryPlugin`, `LibraryMetadata/Capabilities/Hints`, `PromptBundle`,
`LibraryStateProvider`), verified against rf-mcp **0.31.2** and re-validated
against **0.35.0** (2026-07-24: `plugins/contracts.py` and `plugins/manager.py`
are byte-identical between the two; the overlay's startup guard covers the
0.31–0.35 window).

| rf-mcp hook | SAP contribution |
|-------------|------------------|
| `get_keyword_library_map()` | Routes the SAP keywords (`Click Ui5 Control`, `Run Transaction`, …) to their library for discovery. |
| `get_hints()` / `get_prompt_bundle()` | SAP **selector guidance** — the missing SAP equivalent of rf-mcp's `get_locator_guidance`: address UI5 controls not DOM ids; check status-bar message *type* (E/S/W/I) not localized text; never `time.sleep`; speak the business vocabulary in `resources/`. |
| `get_state_provider()` | **Screen perception** — exposes the live SAP screen as session "page source" so the agent can *see* before acting. |

No new MCP tool is created (the plugin system can't, and it isn't needed): the agent
reads state via `get_session_state` / a perception keyword, then calls the SAP
keywords directly.

### Perception keywords

Two read-only keywords surface the current screen; both also have off-SAP unit tests
(`tests/unit/test_perception.py`):

- **ECC** — `Get Screen Signature` (mixin `keywords/_perception.py`): a text view of
  the active SAP GUI screen — header `# screen <Program>/<Transaction>/<Dynpro>` then
  one line per control (session-relative id, type, text), editable fields marked `*`.
- **Fiori** — `Get Ui5 Page Tree`: the UI5 control hierarchy serialized to XML (tag =
  short control type, attributes = `id`, full `controlType`, allowed properties). It
  polls until controls are actually mounted, so it never returns an empty tree.

Both accept **`mode=diff`**: only the lines that changed since the previous
perception (`-`/`+` prefixed lines, unchanged runs summarized) — far cheaper on the
agent's context in a perceive → act → re-perceive loop.

### Agent-oriented keywords (0.2.0)

The plugins also route keywords designed for the perception → action loop:

- **Preflight** (ECC) — `Scripting Should Be Fully Enabled` fails *early* with the
  exact RZ11 parameter to fix (DisabledByServer / readonly / recording disabled),
  instead of letting the agent discover a half-enabled server keyword by keyword;
  `Get Session Telemetry` surfaces response time / round-trips.
- **Self-correcting errors** — ECC lookup failures append the closest ids on the
  current screen (scored); Fiori role failures say whether controls of that *type*
  are rendered at all. The error text itself tells the agent what to try next.
- **Healing** — `Resolve Element With Healing` (ECC) and `Resolve Ui5 With
  Fallback` (Fiori, role→xpath→sid chain): both repair a stale locator with a
  logged WARNING — never silently — and return plain strings (MCP-safe: no COM
  object ever crosses the boundary).
- **Launchpad iframes** — `Set Ui5 Frame` for Work Zone/cFLP apps embedded in a
  (possibly cross-origin) iframe.

The guidance hints (`get_hints()`) steer the agent to these: preflight in Suite
Setup, `mode=diff` on repeated perception, healing keywords on locator failures.

### The Fiori ⇄ Browser subtlety

`SapFioriLibrary` does **not** drive the page; it reuses the **Browser** library's
live page via `BuiltIn().get_library_instance('Browser')`. rf-mcp only invokes a
state provider for the *active web automation library*, which resolves to **Browser**
— so the Browser provider wins and the Fiori provider is bypassed for page source.
That's fine: Fiori perception goes through the `Get Ui5 Page Tree` **keyword** plus
the hints, not the provider. The ECC provider, by contrast, *is* used (SapEccLibrary
is the active library on a desktop session).

This works because rf-mcp executes every keyword in **one shared Robot Framework
context** per session: when a session imports both `Browser` and `SapFioriLibrary`,
they live in the same `Namespace`, so `get_library_instance('Browser')` resolves the
live page — exactly like a normal `.robot` suite. **A Fiori session must import both
libraries and open a page before any UI5 keyword.**

### COM on rf-mcp's thread (ECC)

rf-mcp executes keywords off the main thread. The SAP GUI Scripting API is COM (STA),
so that thread must `CoInitialize` before any COM access — otherwise the scripting
engine raises *"CoInitialize has not been called"*. `connect_to_session` is overridden
in `keywords/_connection.py` to do this (idempotent; a no-op under a normal Robot run).

### Session isolation

The three stateful libraries use `ROBOT_LIBRARY_SCOPE = SUITE`, which isolates
normal Robot suites. rf-mcp 0.31 currently reuses the same Python library
instance across its synthetic tests, so `sapfx_common.session_context` further
partitions API cookie/CSRF/RFC stores and Fiori frame/perception state using the
live `MCP_Test_<session_id>` context. This is unit-tested and live-proven with two
API/Fiori namespaces. Nested ECC resource calls can be attributed to the wrong
synthetic test by rf-mcp; use one live ECC session per rf-mcp process.

## Install & verify

```bash
pip install rf-mcp                      # the host MCP server
pip install -e .                        # makes SapEcc/SapFioriLibrary importable
pip install -e integrations/robotmcp    # registers the plugins (entry-points)

# verify rf-mcp discovers them:
python -c "from robotmcp.config import library_registry as r; print([l for l in r.get_all_libraries() if 'Sap' in str(l)])"
```

Alternatively, drop a manifest under `.robotmcp/plugins/` pointing at the class
(`{"module": "sap_robotmcp.fiori_plugin", "class": "SapFioriPlugin"}`) — no install.

Point your MCP client (Claude Code, an IDE, …) at the rf-mcp server as usual; the SAP
libraries and guidance are then available in any session that imports them.

## How an agent uses it

**Fiori** (import both libs, open a page, then perceive → act):

```text
manage_session  init   libraries=[Browser, SapFioriLibrary]
execute_step    New Browser      chromium
execute_step    New Page         <Fiori URL>
execute_step    Get Ui5 Page Tree            # perceive the control tree
execute_step    Click Ui5 Control   controlType=Button  properties={'text': 'Save'}
```

**ECC** (desktop; the state provider also surfaces the screen via `get_session_state`):

```text
manage_session  init             libraries=[SapEccLibrary]
manage_session  import_resource  resources/ecc_keywords.resource
execute_step    Open SAP And Log In   <conn> <user> <pwd> <client> <lang>
execute_step    Run Transaction       SE16
execute_step    Get Screen Signature              # perceive the screen
```

## Validation (end-to-end, through rf-mcp)

Replayable drivers in `integrations/robotmcp/e2e/` call the real rf-mcp tools
(`manage_session` / `execute_step` / `get_session_state`) in-process, as an agent
would, and assert the full pipeline:

- `fiori_through_rfmcp.py` — **8/8** vs the project's local UI5 fixture: plugin
  discovery, two-library session, routing, populated UI5 tree, click opens a dialog.
- `ecc_through_rfmcp.py` — **9/9** vs a live ABAP Platform A4H (Docker): COM login,
  routing, `Get Screen Signature`, and the **state provider** returning the real live
  SE16 screen signature.

See also [fiori-architecture.md](fiori-architecture.md), [architecture.md](architecture.md),
and `integrations/robotmcp/README.md` for the quick-start.
