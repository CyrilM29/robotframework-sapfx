# AGENTS.md

Condensed guide for AI coding assistants. **`CLAUDE.md` is the canonical, detailed
version**: read it if present in your context; this file mirrors its key rules and
must be kept in sync with it (same commit when conventions or layout change).

## Language

Respond to the user in **French**; write user-facing documents in French. Docs are
bilingual: English original + `*.fr.md` French twin with cross-link banners. Keep
both in sync. Never translate code, identifiers, Robot Framework keyword names, CLI
commands, JSON, or proper nouns. Commit messages may stay in English.
Never use the em dash (« — ») **anywhere in this repo**: docs, READMEs,
`llms.txt`, `specs/`, `memory/`, NOTICE, CHANGELOG, docstrings and
code comments, emitted strings, agent/skill definitions, CI workflows, config.
Use a colon, a comma, parentheses, or split the sentence (French puts a space
before the colon, English does not). Enforced by `scripts/check_no_em_dash.py`
(CI + `PostToolUse` hook + unit test); its `ALLOWED` map pins an exact count per
file allowed to quote the character, and only `_vendor/` is out of scope.

## Agent methodology is owned by rf-test-agents

This repo owns SAP CAPABILITIES, not the agent method. The reference for
agentic testing, for agents plus MCP on Robot Framework, and for the reasoning
mindset of the four test agents (`sap-planner`, `sap-generator`, `sap-healer`,
`sap-istqb` here; `rf-*` there) is the sibling repo `rf-test-agents`. Consult
it before improvising a local answer about an agent's workflow, ground rules
or division of labour; a methodology improvement found here is back-ported
there, then propagated to the other verticals.

## Observe, do not fix

When a test run fails (red test, accessibility violation, baseline or snapshot
drift, regression): report the finding (file, screen or page, rule, impact,
useful output) and stop there. Do not fix the application under test, and do
not fix the test itself either, without an explicit request.

- No convenience baseline update, no `--update-snapshots` to turn a suite green.
- Healer agents run only on request.
- When unsure whether to observe or fix: observe, then ask.
- Exception: a fix that was explicitly asked for, or the development work in
  progress on this repo, is delivered in full, as usual.

## Memory

Durable project facts live in `memory/` at the repo root (index
`memory/MEMORY.md`, rules in `memory/README.md`; French, single-language by
design): costly debugging lessons, decisions with their context, written
**anonymized**: no personal data, no machine paths, no private URLs. Entries
are dated observations, not live state; verify before asserting. One fact
per file, update the index in the same operation, never secrets anywhere.

## What this is

SAP test automation for Robot Framework, one business vocabulary across two channels:

- **`SapEccLibrary`** (`src/SapEccLibrary/`): SAP GUI desktop client (ECC/S4
  backend) over COM (`win32com`). Hardened fork of robotframework-sapguilibrary:
  the upstream file is **vendored verbatim** in `_vendor/sapgui_base.py` (class
  renamed only) and extended by mixins in `keywords/` (connection (incl.
  `Attach To Open Session`, attaching engine + connection + session by INDEX
  to an already-open session, the replay prerequisite of recorded suites),
  waits (incl. the dynamic `Set Default Timeout`/`Set Poll Interval`,
  returning the previous value for a teardown restore), ALV
  grid (by column title, row addressing by content, `Read Abap List` for
  classic list output, plus classic dynpro **table controls** by column
  title (`Read Table Control`, `Get/Set Table Control Cell`,
  `Find Table Control Row`: automatic windowed scrolling; `RowCount`
  counts RESERVED rows, so only the truly filled ones are returned) and
  `Pick F4 Value` for search helps), DDIC inventory (`Classify Ddic Objects`:
  DD02L read through SE16, `TABCLASS` is an OUTPUT column, never a selection
  criterion; `Fill Multiple Selection` for arbitrary name lists, SCROLLING the
  standard dialog window by window with the reached position READ BACK (a
  capped scrollbar writes at the shifted local index, values left outside the
  window fail actionably, no row is ever silently rewritten);
  a batch coming back EMPTY triggers a canary probe that tells a genuine
  absence from positional criteria displaced by the per-user field choice,
  and a missing grid outside a selection screen names
  `Use ALV Grid In Data Browser` instead of flagging every object absent;
  reaching any SE16 selection screen goes through the single library keyword
  `Reach Se16 Selection Screen` (verdict `reached`/`rejected`/`dialog`/`modal`),
  which the resource layer and the campaigns delegate to;
  classification map read live from the TABCLASS domain, `APPEND` stays
  `unknown` without proof; deterministic JSON artifact whose SHA-256 excludes
  the timestamp; pure logic in `sapfx_common/ddic_inventory.py`; a projection
  view can be rejected by SE16 with a type `E` message exactly like a
  structure, only DD02L classifies), perception (`Get Screen Signature` with `mode=diff`
  (`pair_renames=True` pairs lookalike ids into `~ old -> new` rename lines
  via the healing scoring) and `mode=semantic` (the form view: one line per
  actionable target with its VERIFIED human label), `GetObjectTree` fast path
  with automatic COM-walk fallback, in-memory screenshots
  `Get Screenshot As Base64`/`Log Screenshot`, the Set-of-Mark annotated
  screenshot `Get/Log Annotated Screenshot` (numbered boxes + `number -> id`
  legend), the numbered screen map `Get Screen Map` (`@N` per actionable
  target) acted on by `Resolve/Click/Fill Screen Ref` (ephemeral references,
  re-verified before every action, interactive piloting only, never in a
  suite), `Get Open Windows` (JSON-safe window stack, `modal=True` on modal
  windows, the SESSION_MANAGER leftover-modal trap), the visual assertions `Get Screen Perceptual Hash`/`Screen Should
  Match Baseline` (with `mask_elements=auto` for the volatile status/title
  bars) plus their element-scoped variants `Get Element Perceptual Hash`/
  `Element Should Match Baseline` (baseline = the element's cropped PNG) and
  `Get Screen Tile Hashes` (per-tile grid, drift localized)), diagnostics
  (scripting preflight `Scripting Should Be Fully Enabled`, client-security
  preflight `Client Security Should Be Hardened` (input-history CVE-2025-0055,
  see docs/hardening-test-environment.md), `Enable Test Tool
  Mode`, telemetry), healing (`Resolve Element With Healing` incl. the
  `label=` anchor path, scored closest-match errors; a missing-element error
  also names the screen you are REALLY on, `# screen <Program>/<Transaction>/
  <Number>` appended by `Element Should Be Present` and `Get Element Type`,
  best-effort and never at the expense of the original error: an id alone
  cannot tell a stale locator from a screen that is not the one you think),
  **human locators**
  (`Find/Fill/Read Field By Label`, `Click Button By Label`: visible label +
  geometric proximity, grid/position addressing (`N @ Label`/`Label @ N`) and
  the scoped-anchor operator (`Anchor >> Rest`, narrows to a unique label's
  neighborhood), ambiguity always reported with candidates, never a silent
  first match; ids stay the nominal path in `resources/`) and an
  **embedded-browser-control bridge** (`Enable Embedded Browser Debugging`,
  `Get/Switch (To) Embedded Browser Page`: pilots a WebView2 control embedded
  in a SAP GUI/Business Client window through the Browser library over CDP),
  a **coordinate effector** (`Get Element Screen Region`,
  `Click Element At Offset`: hardware win32 click at an element-relative
  position, the last resort for officially unscriptable zones (opaque
  GuiShell, charts, drag & drop)), a **drift sentinel**
  (`Check Screen Against Watch` + `tests/robot/ecc_drift_sentinel.robot`:
  watched screens remembered (structured + visual + per-tile fingerprints),
  later passes report only what moved: smart diff (renames paired), global
  hash, and tile localization naming WHERE the visual drift is, change
  detection without scripted tests), and a **multi-session registry**,
  `Open Sap Session` (second connection, optional `RSYST-*` login with a
  never-logged `Secret` password), `Create Gui Session` (second window on
  the active connection, no re-login so no multi-logon popup),
  `Switch/List/Close/Close All Sap Sessions`: session/connection state is
  routed per active alias (historic usage = the `default` alias), with the
  STA safety rail (owning COM thread remembered per alias; cross-thread
  access gets a defensive CoInitialize, the marshalled mode rf-mcp state
  providers rely on, and `SAPFX_STRICT_COM_THREAD=1` turns it into an
  actionable error). Multi-session is cooperative MULTIPLEXING (one active
  session, explicit switch), never thread parallelism; closing an alias
  never closes a connection another alias still uses.
- **`SapFioriLibrary`** (`src/SapFioriLibrary/`): SAP Fiori/UI5 web automation on
  top of the Browser library (Playwright). Injects a JS bundle (`_ui5_js.py`,
  `window.__SAPFX`) with a **role** engine (incl. `idSuffix` for stable Fiori
  Elements ids `fe::…`), a **UI5 XPath** engine
  (`//Table//Button[@text='Edit']`), and a **wc** engine (`Resolve/Click/Fill
  Wc…`) scanning light-DOM `ui5-*` custom elements for UI5 Web Components pages
  WITHOUT a classic UI5 runtime (short types match scoped tags
  `ui5-button-<suffix>`; open shadow roots pierced by Playwright CSS), plus a
  WebGUI `sid` engine for classic SAP GUI for HTML and a generic **dom** engine
  (`Resolve/Click/Fill Dom…`: CSS + text + COMPUTED ARIA role (explicit or
  implicit HTML semantics) + accessible name `name=` (simplified accname:
  aria-labelledby/aria-label/label[for]/alt/text, user-intent locators, like
  Playwright's `getByRole(name=…)`) + attributes) so the
  NON-SAP regions of a hybrid page (React/Angular/vanilla widgets) enter the
  same grammar; `name=` also exists on the **wc** engine, where it reads the
  UI5 Web Components `accessible-name`/`accessibleName` convention. **Hybrid pages**: `Get Page Composition` probes which
  technologies coexist where (per region + per iframe, one level deep,
  best-effort) and recommends the engines to use; `Push/Pop Ui5 Frame` stack
  nested-iframe scopes (`a >>> b` chaining) on top of `Set Ui5 Frame`, which
  scopes resolution to a launchpad iframe (Work Zone/cFLP) and replaces the
  whole stack; `Resolve Ui5 With Fallback`
  is the logged role→xpath→sid→wc→dom healing chain (also feeds the
  `SAPFX_HEALING_LOG` telemetry journal); `Get Ui5 Page Tree` supports
  `mode=diff`; `Get Ui5 Page Map` numbers the actionable UI5 targets (`@N`)
  for `Resolve/Click/Fill Ui5 Ref` (ephemeral, liveness re-checked against
  the rendered registry, interactive piloting only); `Set Ui5 Timeout`/
  `Set Poll Interval` mirror the ECC dynamic wait settings (previous value
  returned, teardown-restorable); `Get Fiori Diagnostics` aggregates composition + UI5 tree +
  Browser 20 console/page errors + the ARIA snapshot of non-SAP regions into
  one JSON-safe dict with an actionable `issues` summary, each section
  best-effort (`Log Fiori Diagnostics` renders the Markdown report, pure core
  in `sapfx_common/fiori_diagnostics.py`); `Open Fiori App` navigates the launchpad by stable
  `SemanticObject-action` intent hash, `Log In Via Identity Provider` drives
  enterprise IDP login forms (SAP IAS / Azure AD presets, single-page and
  two-step), `Lookup Business Term` resolves FR/EN business terms to ABAP
  fields (shared vocabulary, ambiguity always surfaced, playwright-praman
  concepts, Apache-2.0, NOTICE); `Wait For Ui5 Idle` waits for the page's REAL quiet point (in-flight
  XHR/fetch instrumented at bundle injection + visible busy indicators +
  a continuous settle window): a rendered view is not yet its data, and
  this is what removes flakiness after a Go, a sort or a navigation (it
  waits for requests ALREADY in flight, so a FIRST render is still awaited
  through an application condition); `Get Ui5 Messages` /
  `Ui5 Should Have No Messages Of Type` read the MessageManager plus
  recent MessageToasts and assert by message TYPE, never localized text
  (convention #3 on the web); `Upload File Via Ui5` targets the control's
  inner file input through open shadow roots; `Get Ui5 Perceptual Hash` + `Ui5 Screen Should Match Baseline`
  give the web side the same visual snapshot cycle as ECC (shared
  `sapfx_common.visual_baseline`). It does not drive the page itself: it
  reuses the Browser library's active page, so suites must import `Browser`
  alongside it. Live-proven from UI5 1.60 to the 2.0 nightly.
- **`SapApiLibrary`** (`src/SapApiLibrary/`): the **API channel** (stdlib-only,
  no new dependency): OData v2 (embedded Gateway) and v4 (CAP/S4) with one
  keyword set: full CRUD (`Post/Patch/Delete Odata`, SAP CSRF protocol with
  one-shot 403 replay, `If-Match` handled), `Call Odata Function`,
  `Post Odata Batch` (multipart, atomic changeset), server-driven pagination
  (`Get Odata Entities follow_next=True`), a **test-data factory**
  (`track=True` + `Delete Created Entities` teardown, `Ensure Odata Entity`),
  channel perception (`Get Odata Metadata` with `sap:label` labels,
  `Find Odata Property By Label`, `List Odata Services`), Gateway preflight
  (`Gateway Should Be Active` names the `/IWFND/IWF_ACTIVATE` remediation,
  `Wait Until Api Available`), OAuth2 client-credentials + mTLS auth,
  per-alias telemetry (`Get Api Telemetry`), and optional RFC via pyrfc with
  the BAPI pattern (`Call Bapi` checked by RETURN type,
  `Commit/Rollback Bapi Transaction`) plus `Wait For Background Job` (TBTCO
  via RFC_READ_TABLE).
  Recommended pattern: prepare/cross-check data through the API, drive the
  screen only for what is actually under test, demonstrated by
  `tests/robot/flagship_cross_paradigm.robot` (SE16 count == OData `$count` on
  A4H; Fiori row ↔ OData v4 point query on cap-sflight).
  `cross_paradigm_api_visual.robot` extends it with a perceptual-hash screen
  baseline; `exploratory_campaign_{a4h,fiori}.robot` are the self-contained
  ECC/Fiori exploration campaigns (delivery-class/control inventory, reversible
  writes/interaction, dynamic table/control-type sweeps).
- **`sapfx_common`** (`src/sapfx_common/`): shared `poll_until`/`retry_call`/
  `retry_until` primitives, `com_safety.ensure_com_initialized()` (defensive
  `CoInitialize`, shared by ECC connection bootstrap and the rf-mcp state
  providers), `healing` (locator-similarity scoring shared ECC↔Fiori),
  `healing_telemetry` (opt-in cumulative JSONL journal of repairs,
  `SAPFX_HEALING_LOG=<path>`, fed by both channels), `perception_diff`
  (diff-mode perception, incl. the `pair_renames` smart diff reusing the
  healing scoring), `object_tree` (`GetObjectTree` JSON flattening, the
  structured perception model), `semantic` (label-based geometric resolution +
  the verified inverse `describe_element` used by the recorder, plus
  `is_editable_field`/`actionable_targets`/`screen_affordances` behind
  `mode=semantic` and the annotated screenshot; ported from
  RoboSAPiens, Apache-2.0, see `NOTICE`), `abap_list` (geometric row
  reconstruction for classic ABAP lists), `visual_hash` (pure perceptual
  dHash + crop/mask/tile primitives behind the visual assertions) and
  `visual_baseline` (the shared snapshot-baseline semantics + Pillow decode
  boundary used by BOTH channels' visual keywords, optional extra `visual`).
  New wait/retry loops go here, never inline; their deadlines run on
  `time.monotonic()`, never on the wall clock. Typed (`mypy`).
- **Business keywords** live in `resources/` (`ecc_keywords.resource`,
  `fiori_keywords.resource`, `api_keywords.resource`: one mirrored vocabulary
  across the three channels, same-name aliases, and the OData service paths
  carried under business names so no suite spells one out;
  `a4h_demo_data.resource` for demo-data guards). The API channel has its own
  suite, `tests/robot/api/canal_api_odata.robot`, running the same business
  keywords against OData v2 (tag `a4h`) and OData v4 (tag `capsflight`): it
  was previously exercised only through the two cross-paradigm suites, and
  that blind spot is where two real defects had been sitting. **Recorders** in `tools/recorder`
  (desktop, COM, `--engine auto|native|poll`: native uses the API's own
  `Session.Record`+`Change` events, with automatic polling fallback;
  `--semantic` rewrites steps as human keywords when the label provably
  re-resolves, technical id kept as a comment; assertion hotkeys during record;
  post-recording exports: `--suite` (complete runnable suite with the Library
  import: the DEFAULT since 2026-08-05; `--body-only` keeps the historic
  fragment), `--export-resources` (resource-first
  pair, no raw id left in the test, self-healing keywords for semantic lines),
  `--export-spec` (a specs/-format plan), `--export-istqb` (an ISTQB test
  plan + test cases document: Action/Données/Résultat attendu table plus a
  normalized `replay` YAML block per test case, framework-neutral actions
  with recorded locators as hints, human-readable AND replayable by an AI
  with any framework) and `--export-report` (a
  self-contained HTML documentation report (business phrase + exact RF line
  per step, ECC/Fiori/API keywords phrased, per-step data-URI screenshots,
  `password=` args masked; never a test)); `--replay` plays a recording
  against the open session (a step whose keyword is NOT in the library now
  FAILS the replay: a resource-first suite used to exit 0 with 0 step run);
  `--stop-file` stops an interactive loop from outside through its teardown
  (what killing the process skipped); `--transpile-vbs` converts SAP GUI's
  built-in ALT+F12 VBS recordings) and
  `tools/recorder_web` (snippet + Chrome MV3 extension, injected in all frames;
  records across all five engines incl. the generic dom engine, right-click
  assertion menu, in-page replay, multi-scenario markers, .robot re-import,
  exports: .robot / resource-first with self-healing UI5 keywords / specs
  plan / ISTQB plan (same template as desktop, one test case per scenario) /
  self-contained HTML documentation report).
  **rf-mcp plugins** in `integrations/robotmcp/`: perception is never a
  time-based cache, but consecutive identical calls get compacted
  (`_last_seen.py`) and `filtered`/`filtering_level` is really implemented
   (`_filtering.py`); state providers serve the smart perception diff on an
   already-seen screen and a stale-code warning when SAPFX code changed on
   disk after server start (`_staleness.py`), plus an **enriched application
   state** under one contract shared by the three channels (`connected` /
   `state_error`, `collection_errors` for a section that failed and
   `not_applicable` for one that has no meaning here): window stack with the
   modal trap, status type and telemetry on ECC; iframe scope, `ui5_runtime`
   (probed before reading UI5 messages, so a Web Components/WebGUI/hybrid page
   is a supported target rather than a permanent error) and the messages on
   Fiori, in ONE context crossing (`Get Ui5 Application State`); the API
   channel has its `SapApiPlugin` (honest no-screen page source; real channel
   state via `List Api Sessions`, never credentials); the **`sapfx-mcp` overlay**
   (console entry point, NOT a fork) mounts the rf-mcp server unchanged and
   adds `sapfx_state`/`sapfx_screenshot`/`sapfx_reload` behind a startup
   compatibility guard (rf-mcp window [0.31, 0.36), deployment pin 0.35.0;
   the entry-point path, where the plugins load in a stock `robotmcp`, gets a
   non-blocking version warning instead), and it honours the declared
   capabilities: a section a library does not serve is refused with that
   provider's own reason, never faked;
   API/Fiori state is partitioned by rf-mcp synthetic-test
   namespace; ECC supports one live session per rf-mcp process.
  **Repo-wide scripts** (doc pairing, vendor drift, guidance
  sync, consistency guards, not generators, plus the deployment-pack assembler
  `build_release_pack.py`, `regen_agent_definitions.py`,
  `healing_drift_report.py`, the preventive-maintenance bot: reads the
  `SAPFX_HEALING_LOG` journal, proposes/applies `resources/` patches for stable
  locator drifts, exit 1 as a CI alert, never touches tests, and
  `check_spec_sync.py`, the spec-is-the-source-of-truth guard: generated
  suites carry a `Spec: specs/<plan>.md (sha256:…, <date>)` provenance marker
  (`--stamp` after generation, part of sap-generator's contract); a spec that
  changed since generation fails the guard, as does a spec sap-healer marked
  `> **Statut : PÉRIMÉE (…)**` after a genuine functional change) and
  `check_conventions.py`, the mechanical guard for conventions #1/#2: raw
  locators (SAP GUI ids, UI5 addresses, CSS/XPath) in a **generated** suite
  and `Sleep` anywhere; hand-written library-validation suites are reported
  but not blocking, since driving SAP by raw ids is their very purpose
  (`--strict` blocks those too), and `export_public_tree.py`, the
  export-per-release tool for the public `robotframework-sapfx` repo:
  filtered `git archive HEAD` tree, fail-closed transforms, blocking
  byte-level leak scan, PyPI README variant; the script is itself excluded
  from the export, and `check_no_em_dash.py`, the mechanical guard for the
  em-dash rule: the character is refused in every tracked text file, with an
  `ALLOWED` map pinning an exact count for the few files that must quote it
  (`_vendor/` out of scope). Also `check_published_versions.py`: no published
  instruction may cite a stale SAPFX version (pack filename, pip pin, wheel
  names in READMEs / `docs/` / `packaging/`), and a STATIC version badge is
  refused where the dynamic shields.io badge updates itself (what you see
  right after a release is cache, not an error); third-party versions and
  history files are out of scope on purpose. All in `scripts/`, over the shared
  `_common.py`: it forces UTF-8 on **stdout AND stderr** (on Windows the
  standard streams open in the machine's code page, where an arrow killed the
  process on stdout and produced mojibake on stderr) and reads the project
  version **section-aware** (three copies used to disagree). The two
  first-generation packed scripts (`healing_drift_report.py`,
  `check_spec_sync.py`) keep a deliberate copy of that switch, so they stay
  usable even lifted out of the pack alone; the pack also ships
  `check_conventions.py` (sap-generator's own gate, previously invoked by a path
  ABSENT from the pack) and therefore `_common.py`. Two unit guards hold the
  pack honest: the internal import closure must be entirely inside the pack, and
  every `scripts/<x>.py` a shipped file invokes must itself be shipped or
  justified in the test's allowlist. That second guard is what moved
  `/sap-eval-healer` out of the pack (a studio regression net, aimed at a
  resource and a suite the pack does not carry). A third one enforces the
  distribution boundary in both channels: no path in the pack manifest may sit
  in `export_public_tree.py`'s `EXCLUDE_PREFIXES`, after `PACK_TREES` copied
  `.claude/skills` wholesale and shipped the studio's PRIVATE comms skill inside
  the released 0.6.6 ZIP. Skills now enter the pack by whitelist. That guard
  reasons about PATHS, so a fourth one runs the export's byte-level **content**
  scan over the pack manifest, in CI on every push: it reports 5 forbidden hits
  on the shipped 0.6.6 ZIP and none on the fixed pack, whereas the export itself
  runs by hand once per release, on `git archive HEAD`. When writing such a
  note, keep it unnamed: the leak scan forbids that skill's very name in files
  that go public, this one included. A `PostToolUse` hook
  (`scripts/hook_guards.py`, its decision in a testable `decide()`) runs the
  em-dash guard on every edited file, and the others after every edit of
  specs/tests/resources/variables.
  **SAP test agents** (plan → generate → heal, Playwright-Test-Agents style,
  plus the offline `sap-istqb` test designer: planner specs + recorder
  outputs → ISTQB test plan + test cases under `specs/istqb/`, normalized
  replay blocks an AI can re-execute with any framework, never inventing
  what no source supports):
  canonical definitions in `.claude/agents/` + `/sap-*` commands in
  `.claude/commands/` + the `sapfx` toolkit skill in `.claude/skills/`
  (shipped in the deployment pack), including the orchestrators `/sap-maintain`
  (sentinel → healing telemetry → healer, one report) and `/sap-eval-healer`
  (blind healer evaluation via `scripts/agent_eval_harness.py`); every heal
  session appends the agent's diagnosis to `docs/heal-journal.md`
  (complementary to the runtime `SAPFX_HEALING_LOG` telemetry);
  `.github/chatmodes/` holds their VS Code / Copilot
  declination, **generated** by `python scripts/regen_agent_definitions.py`
  (never edit chat modes by hand; `--check` guards drift in CI/pytest);
  business test plans in `specs/` (French, single-language by design).
  Generated artifacts follow the industrial layout encoded in the
  generator/healer definitions: new suites under
  `tests/robot/{api, ui/ecc, ui/fiori, cross}`, page objects (one `.resource`
  per screen/app: locator variables + business keywords) under
  `resources/page_objects/`, cross-screen keywords in
  `resources/common.resource`, environment data under `variables/`
  (never credentials); legacy flat suites stay put; the healer patches that
  layer, never test bodies. On a
  deployed pack the agents write only to `resources/site_keywords.resource`,
  never to shipped files. **Deployment pack sources** in
  `packaging/` (installer, pack READMEs, two MCP templates, `-WithMcp` renders
   `.mcp.json` and `.vscode/mcp.json` in place; ships 6 sample suites: smokes
   (including the offline Browser/WC product check),
  the self-contained `business_data_exploration.robot`, the drift sentinel,
  the cross-paradigm flagship, the maintenance scripts
  (`healing_drift_report.py`, `check_spec_sync.py`), plus the agents
  and `specs/`): the built pack
   under `dist/` is a generated artifact: fix `packaging/` and rebuild. CI
   installs the extracted ZIP and publishes SHA-256 checksums, a CycloneDX SBOM
   and build provenance.

## Commands

```bash
python -m pytest -q                 # all logic tests: no SAP, no browser needed
python -m ruff check src tools tests integrations scripts   # lint (_vendor excluded)
python -m mypy                      # type check: all shipped code (the 2 packed scripts included), only `_vendor/` excluded
pip install -r requirements.txt     # robotframework + pywin32 (pinned) + browser
robot --pythonpath src --dryrun --outputdir results/dry tests/robot/   # keyword check, no SAP
robot tests/robot/fiori_smoke.robot # live vs public OpenUI5 Demo Kit
robot -v SAP_CONNECTION:"..." -v SAP_USER:... -v "SAP_PASSWORD: Secret:..." tests/robot/ecc_smoke.robot   # RF 7.4 typed Secret: masked even at TRACE
python scripts/check_bilingual_docs.py --since origin/main   # EN/FR doc pairing + drift
python scripts/check_vendor_drift.py       # vendor file drift (no-op without a local _upstream/ clone)
python scripts/check_guidance_sync.py      # rf-mcp hints + agent definitions vs. CLAUDE.md conventions
python scripts/regen_agent_definitions.py --check   # VS Code chat modes in sync with .claude/agents/
python scripts/build_release_pack.py       # Windows deployment pack -> dist/sapfx-pack-<v>-win.zip
```

The dev machine already has SAP GUI 8.00, Playwright browsers (`rfbrowser init`
done) and a live A4H trial (Docker): do not ask the user to install these.

CI (`.github/workflows/ci.yml`) runs ruff + mypy + the two fast consistency scripts +
`pytest --cov` (85% gate) on ubuntu, and `pytest tests/unit` against the real pywin32
followed by `robot --dryrun` on windows, on every push/PR to `main`.
`vendor-drift.yml` runs weekly against a fresh upstream clone.

## Hard rules (from CLAUDE.md, do not break)

1. **Tests contain no raw SAP element ids and no CSS/XPath.** Locators live in
   `resources/`; tests speak business language. On Fiori, address UI5 controls
   (`controlType`/`properties`/`bindingPath`…), never DOM ids.
2. **Never `time.sleep` to wait for SAP.** Use `Wait Until Busy Done` /
   `Wait Until Element Present` (ECC) or `Wait For UI5 Ready` (Fiori).
3. **Locale-independent assertions.** Check the status-bar message *type*
   (`E`/`S`/…), never localized text.
4. **Never edit `src/SapEccLibrary/_vendor/sapgui_base.py`.** It is upstream +
   a one-line class rename. New behaviour goes in a mixin or `SapEccLibrary.py`.
5. **Every new keyword gets an off-SAP unit test** in `tests/unit/` (fake COM
   objects pattern, see `tests/unit/conftest.py`).
6. **`pywin32` stays exactly pinned** in `requirements.txt` (floor only in
   `pyproject.toml`).
7. **Keep AI supports in sync**: CLAUDE.md (canonical) ↔ this file ↔
   `.github/copilot-instructions.md`.
8. **Reuse `sapfx_common.polling`** for any wait/retry logic: no new inline loops.
9. **Check the remotes before starting work and before commit/merge/push**:
   `git fetch origin` then `git status` (private repo movement), and the public
   repo's PRs/issues (`gh pr list -R CyrilM29/robotframework-sapfx`,
   `gh issue list -R CyrilM29/robotframework-sapfx`): the public repo has no
   technical link to this one, nothing else surfaces them. Report any open
   PR/issue to the user before pushing.
10. **Docs and both memory layers are updated BEFORE the commit, in the same
   lot.** Never "commit now, document later". Before every commit (and a
   fortiori before a push or a release): `CLAUDE.md` + its mirrors (`AGENTS.md`,
   `.github/copilot-instructions.md`), `llms.txt`, the bilingual `docs/*.md`
   pair when the described behaviour moved, and the `CHANGELOG` entry; then
   **project memory** (`memory/`, public-safe French, one file per durable
   fact, index in the same operation: what cost something to learn, not what
   the code or `git log` already says); then the **shared cross-project
   memory** (private base: personal, machine-bound or beyond this repo), index
   line included. A memory entry is a DATED observation: when your work proves
   one wrong, fix it in the same lot instead of leaving a trap for the next
   session. The existing guards only cover figures, published versions and
   agent guidance: the rest is discipline, hence this rule.

## License

Apache 2.0. Preserve the attributions in `NOTICE` (upstream sapguilibrary,
playwright-sap ports in `_ui5_js.py`, RoboSAPiens human-locator techniques in
`sapfx_common/semantic.py`).
