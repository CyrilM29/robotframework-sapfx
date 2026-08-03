# GitHub Copilot instructions

This repo is a Robot Framework SAP test-automation ecosystem with two libraries
sharing one business vocabulary. `CLAUDE.md` at the repo root is the canonical
detailed guide; `AGENTS.md` is its condensed mirror. Keep all three files in sync
when conventions or layout change.

## Memory

Durable project facts live in `memory/` at the repo root (index
`memory/MEMORY.md`, rules in `memory/README.md`; French, single-language by
design): costly debugging lessons, decisions with their context — written
**anonymized**: no personal data, no machine paths, no private URLs. Entries
are dated observations, not live state — verify before asserting. One fact
per file, update the index in the same operation, never secrets anywhere.

## Context you need before suggesting code

- `src/SapEccLibrary/` drives the SAP GUI **desktop client** through the SAP GUI
  Scripting API over COM (`win32com`, Windows only). `_vendor/sapgui_base.py` is
  upstream code vendored verbatim — **never modify it**; add behaviour in a mixin
  under `keywords/` or in `SapEccLibrary.py`. Mixins already cover connection
  (incl. `Attach To Open Session` — attach by index to an already-open
  session, the replay prerequisite of recorded suites), waits (incl. the
  dynamic `Set Default Timeout`/`Set Poll Interval`, previous value returned
  for a teardown restore), ALV grid (by column title, row addressing by
  content, `Read Abap List`), perception (`Get Screen Signature` — `mode=diff` with the
  `pair_renames` smart diff pairing lookalike ids into `~ old -> new` lines,
  `mode=semantic` form view with verified human labels —, `GetObjectTree`
  fast path with COM-walk fallback, in-memory screenshots `Get Screenshot As
  Base64`/`Log Screenshot`, the Set-of-Mark `Get/Log Annotated Screenshot`
  — numbered boxes + `number -> id` legend —, the numbered screen map
  `Get Screen Map` (`@N` per actionable target) with `Resolve/Click/Fill
  Screen Ref` acting by number (ephemeral, re-verified before every action —
  interactive piloting only, never in a suite), `Get Open Windows` (JSON-safe
  window stack, `modal=True` — the SESSION_MANAGER leftover-modal trap),
  visual assertions
  `Get Screen Perceptual Hash`/`Screen Should Match Baseline` with
  `mask_elements=auto`, their element-scoped variants `Get Element Perceptual
  Hash`/`Element Should Match Baseline`, and `Get Screen Tile Hashes` for
  localized drift), scripting preflight/diagnostics
  (`Scripting Should Be Fully Enabled`, `Client Security Should Be Hardened` —
  input-history CVE-2025-0055 posture, `Enable Test Tool Mode`, telemetry),
  locator healing (`Resolve Element With Healing`, incl. the `label=` anchor
  path) and human locators (`Find/Fill/Read Field By Label`, `Click Button By
  Label` — visible label + geometry, grid/position addressing (`N @ Label`/
  `Label @ N`) and the scoped-anchor operator (`Anchor >> Rest`); ambiguity
  always reported with the candidate list, never a silent first match). An
  **embedded-browser-control bridge** (`Enable Embedded Browser Debugging`,
  `Get/Switch (To) Embedded Browser Page`) pilots a WebView2 control embedded
  in a SAP GUI/Business Client window through the Browser library over CDP.
  A **coordinate effector** (`Get Element Screen Region`,
  `Click Element At Offset` — hardware win32 click at an element-relative
  position) is the last resort for officially unscriptable zones; a **drift
  sentinel** (`Check Screen Against Watch` +
  `tests/robot/ecc_drift_sentinel.robot`) detects screen changes without
  scripted tests (structured smart diff + global hash + per-tile baselines
  that localize the drift; report-only by default). A **multi-session
  registry** (`keywords/_sessions.py`: `Open Sap Session` — optional
  `RSYST-*` login with a never-logged `Secret` password —,
  `Create Gui Session` — second window on the active connection, no
  re-login —, `Switch/List/Close/Close All Sap Sessions`) routes
  session/connection state per active alias (historic usage = `default`),
  with an STA safety rail: the owning COM thread is remembered per alias,
  cross-thread access gets a defensive `CoInitialize` (rf-mcp marshalled
  mode) and `SAPFX_STRICT_COM_THREAD=1` makes it an actionable error.
  Multi-session is cooperative multiplexing — one active session, explicit
  switch, never thread parallelism; closing an alias never closes a
  connection another alias still uses.
- `src/SapFioriLibrary/` drives SAP Fiori/UI5 **web** apps via the Browser library
  (Playwright). It injects `window.__SAPFX` (generated from `_ui5_js.py`) and
  resolves UI5 controls by **role** (controlType/properties/bindingPath, plus
  `idSuffix` for stable Fiori Elements ids `fe::…`), by
  **UI5 XPath** (`//Table//Button[@text='Edit']`), or by the **wc** engine
  (`Resolve/Click/Fill Wc…` — light-DOM scan of `ui5-*` custom elements for UI5
  Web Components pages without a classic UI5 runtime; short types match scoped
  tags `ui5-button-<suffix>`); a `sid` engine covers classic
  SAP GUI for HTML, and a generic **dom** engine (`Resolve/Click/Fill Dom…` —
  CSS + text + computed ARIA role (explicit or implicit HTML semantics) +
  accessible name `name=` (simplified accname — user-intent locators, like
  Playwright's `getByRole(name=…)`) + attributes) covers the NON-SAP regions
  of a hybrid page (React/Angular/vanilla widgets); `name=` also exists on the
  **wc** engine (UI5 Web Components `accessible-name`/`accessibleName`
  convention). For hybrid pages,
  `Get Page Composition` probes which technologies coexist where (per region
  and per iframe, one level deep) and recommends the engines; `Push/Pop Ui5
  Frame` stack nested-iframe scopes (`a >>> b` chaining). `Set Ui5 Frame`
  scopes resolution to a launchpad iframe
  (Work Zone/cFLP) and replaces the whole stack; `Resolve Ui5 With Fallback`
  is the logged healing chain
  (role→xpath→sid→wc→dom, also feeding the opt-in `SAPFX_HEALING_LOG` journal);
  `Get Ui5 Page Map` numbers the actionable UI5 targets (`@N`) for
  `Resolve/Click/Fill Ui5 Ref` (ephemeral, liveness re-checked — interactive
  piloting only); `Set Ui5 Timeout`/`Set Poll Interval` adjust the wait
  settings mid-suite (previous value returned, teardown-restorable);
  `Get Fiori Diagnostics` aggregates composition + UI5 tree + Browser 20
  console/page errors + the ARIA snapshot of non-SAP regions into one
  JSON-safe dict with an actionable `issues` summary (`Log Fiori Diagnostics`
  renders the Markdown report);
  `Get Ui5 Perceptual Hash`/`Ui5 Screen Should Match Baseline` mirror the ECC
  visual snapshot cycle (shared `sapfx_common.visual_baseline`); `Open Fiori
  App` (stable intent-hash FLP navigation), `Log In Via Identity Provider`
  (SAP IAS / Azure AD presets) and `Lookup Business Term` (FR/EN business
  vocabulary → ABAP fields) come from the playwright-praman analysis
  (Apache-2.0, NOTICE).
  It reuses the Browser library's active page — suites import
  `Library    Browser` alongside it.
- `src/SapApiLibrary/` is the **API channel** (stdlib-only): OData v2/v4 with
  one keyword set (`Open Api Session`, `Get Odata Entities/Count`, `Post Odata`
  with the SAP CSRF protocol), optional RFC via pyrfc. Prefer preparing and
  cross-checking data through it; drive the screen only for what is under test
  (see `tests/robot/flagship_cross_paradigm.robot`, and
  `cross_paradigm_api_visual.robot` which adds a perceptual-hash screen baseline
  to that pattern; `exploratory_campaign_{a4h,fiori}.robot` are the matching
  self-contained ECC/Fiori exploration campaigns).
- Business keywords live in `resources/*.resource`; recorders in `tools/`;
  rf-mcp plugins in `integrations/robotmcp/` (state providers serve a smart
  perception diff on an already-seen screen plus a stale-code warning when
  SAPFX code changed after server start; the `SapApiPlugin` serves the real
  API-channel state via `List Api Sessions` — never credentials; the
  `sapfx-mcp` overlay — not a fork — mounts the rf-mcp server unchanged and
  adds `sapfx_state`/`sapfx_screenshot`/`sapfx_reload` behind a
  version-window guard, deployment pin rf-mcp 0.35.0; API stores and Fiori
  frame state
  are partitioned by rf-mcp session; ECC remains one live session per process);
  repo-wide consistency scripts
  (doc pairing, vendor drift, guidance sync) plus the Windows deployment-pack
  assembler (`build_release_pack.py`, sources in `packaging/`), the healing
  drift bot (`healing_drift_report.py` — proposes/applies `resources/` patches
  from the `SAPFX_HEALING_LOG` journal, never touches tests) and the
  spec-sync guard (`check_spec_sync.py` — generated suites carry a
  `Spec: … (sha256:…, <date>)` provenance marker, stale suites fail CI, as does
  a spec sap-healer marked `> **Statut : PÉRIMÉE (…)**`; stamp after every
  regeneration) and the conventions guard (`check_conventions.py` — raw
  locators in a **generated** suite, `Sleep` anywhere; library-validation
  suites are informative only, `--strict` blocks them too) in `scripts/`.
  A `PostToolUse` hook (`scripts/hook_guards.py`) runs both after each edit.
  The built pack (`dist/sapfx-pack-*.zip`) is generated — never edit it in place.
- SAP test agents (plan → generate → heal): canonical definitions in
  `.claude/agents/sap-*.md` (+ the `sapfx` toolkit skill in
  `.claude/skills/`, shipped in the pack), business test plans in `specs/`
  (French). The
  chat modes in `.github/chatmodes/` are **generated** from those definitions
  by `python scripts/regen_agent_definitions.py` — never edit a
  `*.chatmode.md` by hand; edit the `.claude/agents/` source and regenerate
  (`--check` fails CI/pytest on drift). Orchestrating commands:
  `/sap-maintain` (drift sentinel → healing telemetry → healer, one report)
  and `/sap-eval-healer` (blind healer evaluation via
  `scripts/agent_eval_harness.py` — inject/verify/restore a simulated drift).
  Every heal session appends the agent's diagnosis to `docs/heal-journal.md`
  (complementary to the runtime `SAPFX_HEALING_LOG` telemetry).
  Generated artifacts follow the industrial layout: suites under
  `tests/robot/{api, ui/ecc, ui/fiori, cross}`, page objects under
  `resources/page_objects/` (one `.resource` per screen/app),
  `resources/common.resource` for cross-screen keywords, environment data
  under `variables/` (never credentials); the healer patches that layer,
  never test bodies.
- `src/sapfx_common/polling.py` holds the shared `poll_until`/`retry_call`/
  `retry_until` primitives — reuse them for any wait/retry logic instead of
  writing new `while time.time() < deadline` loops. `sapfx_common/com_safety.py`
  holds the shared defensive `CoInitialize` helper — reuse it for any code that
  might run off the main thread (rf-mcp) instead of a new inline try/except.
  `sapfx_common/healing.py` (locator-similarity scoring, shared ECC↔Fiori),
  `sapfx_common/healing_telemetry.py` (opt-in cumulative JSONL journal of
  locator repairs), `sapfx_common/perception_diff.py` (diff-mode perception),
  `sapfx_common/object_tree.py` (`GetObjectTree` JSON flattening — the
  structured perception model), `sapfx_common/semantic.py` (label-based
  geometric resolution + the verified inverse used by the recorder's
  `--semantic` mode, plus `is_editable_field`/`actionable_targets`/
  `screen_affordances` behind `mode=semantic` and the annotated screenshot),
  `sapfx_common/abap_list.py` (geometric row reconstruction),
  `sapfx_common/visual_hash.py` (pure perceptual dHash + crop/mask/tile
  primitives behind the visual assertions) and
  `sapfx_common/visual_baseline.py` (shared snapshot-baseline semantics +
  the Pillow decode boundary for BOTH channels — optional extra `visual`)
  are the other shared primitives — extend them rather than
  duplicating scoring/diff/journal/geometry logic.
- CI (`.github/workflows/ci.yml`) runs a Python 3.10/3.12/3.14 matrix (3.10 =
  floor and 3.14 = latest verified, plain pytest; the full lane stays on 3.12),
  ruff + expanded
  mypy + `pytest --cov` (85% gate) + consistency/proof guards; Windows runs the
  real-pywin32 tests, dry-run, offline Browser smoke and installs the final ZIP
  with SHA-256/SBOM/provenance checks. A weekly UI5 matrix keeps current and
  1.136 LTS blocking while 2.x nightly remains informative. Generated
  code should stay green against this — run the commands above locally before
  assuming a change is done.

## Rules for generated code

1. Robot Framework **tests must not contain raw SAP element ids or CSS/XPath** —
   put locators in `resources/` keywords; tests speak business language. On the
   Fiori side, target UI5 controls, never DOM ids (they are dynamic).
2. **Never suggest `time.sleep`/`Sleep` to wait for SAP.** Use
   `Wait Until Busy Done` / `Wait Until Element Present` (ECC) or
   `Wait For UI5 Ready` (Fiori).
3. **Assertions must be locale-independent**: check status-bar message *type*
   (`E`/`S`/…), never localized message text.
4. Every new library keyword needs an **off-SAP unit test** in `tests/unit/`
   using the fake-COM-objects pattern (`tests/unit/conftest.py`). Run with
   `python -m pytest tests/unit -q` — no SAP or browser required.
5. Dependencies: `pywin32` is **pinned exactly** in `requirements.txt`
   (loosening it breaks COM); `pyproject.toml` keeps floors only.
6. Python code comments/docstrings are in French in this repo; keep raised
   error messages in English. Do not translate keyword names or identifiers.
7. Docs are bilingual: every `docs/*.md` has a `*.fr.md` twin with cross-link
   banners — update both or neither.

## License

Apache 2.0 with vendored/ported Apache-2.0 code (robotframework-sapguilibrary,
playwright-sap ports, RoboSAPiens human-locator techniques). Preserve headers
and `NOTICE` attributions.
