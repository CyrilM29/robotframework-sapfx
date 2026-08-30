# GitHub Copilot instructions

This repo is a Robot Framework SAP test-automation ecosystem with two libraries
sharing one business vocabulary. `CLAUDE.md` at the repo root is the canonical
detailed guide; `AGENTS.md` is its condensed mirror. Keep all three files in sync
when conventions or layout change.

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

## Context you need before suggesting code

- `src/SapEccLibrary/` drives the SAP GUI **desktop client** through the SAP GUI
  Scripting API over COM (`win32com`, Windows only). `_vendor/sapgui_base.py` is
  upstream code vendored verbatim: **never modify it**; add behaviour in a mixin
  under `keywords/` or in `SapEccLibrary.py`. Mixins already cover connection
  (incl. `Attach To Open Session`, attach by index to an already-open
  session, the replay prerequisite of recorded suites), waits (incl. the
  dynamic `Set Default Timeout`/`Set Poll Interval`, previous value returned
  for a teardown restore), ALV grid (by column title, row addressing by
  content, `Read Abap List`, classic dynpro **table controls** by column
  title with automatic scrolling (`Read Table Control` and friends: note
  `RowCount` counts RESERVED rows, not filled ones) and `Pick F4 Value`
  for search helps), DDIC inventory (`Classify Ddic Objects` reads DD02L
  through SE16 by batched multiple selection (the dialog is SCROLLED past its
  visible window, scroll verified): `TABCLASS` is an OUTPUT column,
  never a criterion; classification map read live from the TABCLASS domain;
  an empty batch triggers a canary probe and a missing grid names
  `Use ALV Grid In Data Browser`, so a campaign is never green and wrong;
  every SE16 selection screen is reached through the one library keyword
  `Reach Se16 Selection Screen`, alongside the two promoted SE16 screen
  primitives `Use ALV Grid In Data Browser` and
  `Count Entries On Current Selection Screen`;
  deterministic hashed JSON artifact; pure logic in
  `sapfx_common/ddic_inventory.py`), perception (`Get Screen Signature`: `mode=diff` with the
  `pair_renames` smart diff pairing lookalike ids into `~ old -> new` lines,
  `mode=semantic` form view with verified human labels, `GetObjectTree`
  fast path with COM-walk fallback, in-memory screenshots `Get Screenshot As
  Base64`/`Log Screenshot`, the Set-of-Mark `Get/Log Annotated Screenshot`
  (numbered boxes + `number -> id` legend), the numbered screen map
  `Get Screen Map` (`@N` per actionable target) with `Resolve/Click/Fill
  Screen Ref` acting by number (ephemeral, re-verified before every action,
  interactive piloting only, never in a suite), `Get Open Windows` (JSON-safe
  window stack, `modal=True`, the SESSION_MANAGER leftover-modal trap),
  visual assertions
  `Get Screen Perceptual Hash`/`Screen Should Match Baseline` with
  `mask_elements=auto`, their element-scoped variants `Get Element Perceptual
  Hash`/`Element Should Match Baseline`, and `Get Screen Tile Hashes` for
  localized drift), scripting preflight/diagnostics
  (`Scripting Should Be Fully Enabled`, `Client Security Should Be Hardened`:
  input-history CVE-2025-0055 posture, `Enable Test Tool Mode`, telemetry),
  locator healing (`Resolve Element With Healing`, incl. the `label=` anchor
  path; missing-element errors also append `# screen <Program>/<Transaction>/
  <Number>`, the screen you are really on, which an id alone cannot reveal)
  and human locators (`Find/Fill/Read Field By Label`, `Click Button By
  Label`: visible label + geometry, grid/position addressing (`N @ Label`/
  `Label @ N`) and the scoped-anchor operator (`Anchor >> Rest`); ambiguity
  always reported with the candidate list, never a silent first match). An
  **embedded-browser-control bridge** (`Enable Embedded Browser Debugging`,
  `Get/Switch (To) Embedded Browser Page`) pilots a WebView2 control embedded
  in a SAP GUI/Business Client window through the Browser library over CDP.
  A **coordinate effector** (`Get Element Screen Region`,
  `Click Element At Offset`: hardware win32 click at an element-relative
  position) is the last resort for officially unscriptable zones; a **drift
  sentinel** (`Check Screen Against Watch` +
  `tests/robot/ecc_drift_sentinel.robot`) detects screen changes without
  scripted tests (structured smart diff + global hash + per-tile baselines
  that localize the drift; report-only by default; `per_resolution=True`
  keeps the visual references per capture geometry, the structural one being
  resolution-independent). A **multi-session
  registry** (`keywords/_sessions.py`: `Open Sap Session` (optional
  `RSYST-*` login with a never-logged `Secret` password),
  `Create Gui Session` (second window on the active connection, no
  re-login), `Switch/List/Close/Close All Sap Sessions`) routes
  session/connection state per active alias (historic usage = `default`),
  with an STA safety rail: the owning COM thread is remembered per alias,
  cross-thread access gets a defensive `CoInitialize` (rf-mcp marshalled
  mode) and `SAPFX_STRICT_COM_THREAD=1` makes it an actionable error.
  Multi-session is cooperative multiplexing: one active session, explicit
  switch, never thread parallelism; closing an alias never closes a
  connection another alias still uses.
- `src/SapFioriLibrary/` drives SAP Fiori/UI5 **web** apps via the Browser library
  (Playwright). It injects `window.__SAPFX` (generated from `_ui5_js.py`) and
  resolves UI5 controls by **role** (controlType/properties/bindingPath, plus
  `idSuffix` for stable Fiori Elements ids `fe::…`), by
  **UI5 XPath** (`//Table//Button[@text='Edit']`), or by the **wc** engine
  (`Resolve/Click/Fill Wc…`: scan of `ui5-*` custom elements in the light DOM
  AND every open shadow root, for UI5 Web Components pages without a classic
  UI5 runtime; short types match scoped tags `ui5-button-<suffix>` and every
  glue/dash spelling, `ui5-shellbar-item` included); a `sid` engine covers classic
  SAP GUI for HTML, and a generic **dom** engine (`Resolve/Click/Fill Dom…`:
  CSS + text + computed ARIA role (explicit or implicit HTML semantics) +
  accessible name `name=` (simplified accname, user-intent locators, like
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
  `Resolve/Click/Fill Ui5 Ref` (ephemeral, liveness re-checked, interactive
  piloting only); `Set Ui5 Timeout`/`Set Poll Interval` adjust the wait
  settings mid-suite (previous value returned, teardown-restorable);
  `Get Fiori Diagnostics` aggregates composition + UI5 tree + Browser 20
  console/page errors + the ARIA snapshot of non-SAP regions into one
  JSON-safe dict with an actionable `issues` summary (`Log Fiori Diagnostics`
  renders the Markdown report);
  `Wait For Ui5 Idle` waits for the real network/busy quiet point after an
  action (a rendered view is not yet its data; it covers requests already
  in flight, so a first render is still awaited by an application
  condition); `Get Ui5 Messages` / `Ui5 Should Have No Messages Of Type`
  assert by message TYPE, never localized text; `Get Ui5 Property` /
  `Get Ui5 Properties` read a control PROPERTY from the registry (exact, and
  readable even when the control is rendered but hidden), where `Get Ui5 Text`
  returns what is DISPLAYED and therefore needs visibility;
  `Upload File Via Ui5`
  reaches the inner file input through open shadow roots;
  `Get Ui5 Perceptual Hash`/`Ui5 Screen Should Match Baseline` mirror the ECC
  visual snapshot cycle (shared `sapfx_common.visual_baseline`);
  `Get Ui5 Property`/`Get Ui5 Properties` read a control PROPERTY from the
  registry (text is what the browser displays: it needs visibility and adds
  what the control draws), `Get Ui5 Control Info`/`Get Ui5 Aggregation Info`
  read the full metadata type, the binding context and aggregation children
  rendered OR NOT (a closed Select's items are in no engine's DOM), the pure
  probes cover launchpad services (`Get Flp User`, `List Flp
  Apps/Catalogs/Groups`, `Get Flp Intent Support`, `Flp Service Is
  Available`), WebGUI presence/menus, `List Page Iframes`,
  `Get Page Languages`, `Get Session Cookie Summary` (never a value),
  `Get Ui5 Theme` (`{requested, applied}`, which diverge while the runtime
  swaps its stylesheets) and
  `Ui5 Runtime Is Ready`, `Get Ui5 Ids` says WHICH controls matched
  (`containedIn=` narrows to another control's DOM content),
  `Get Ui5 Open Popups` tells open from merely rendered dialogs
  (`sap.m.InstanceManager`) and `Click Ui5 Dialog Button` acknowledges by
  POSITION (button ids are generated, texts translated, and the right
  position varies by release); `Open Fiori
  App` (stable intent-hash FLP navigation), `Log In Via Identity Provider`
  (SAP IAS / Azure AD presets) and `Lookup Business Term` (FR/EN business
  vocabulary → ABAP fields) come from the playwright-praman analysis
  (Apache-2.0, NOTICE).
  It reuses the Browser library's active page: suites import
  `Library    Browser` alongside it.
- **Security posture, one suite per target**:
  `tests/robot/api/secu_configuration_a4h.robot` (live 12/12) and
  `secu_configuration_abap2023.robot` (live 13/13), READ-ONLY, RFC channel.
  Vocabulary in `resources/security_keywords.resource`, capability in
  `SapApiLibrary._rfc_security`, pure logic in
  `sapfx_common/security_baseline.py`. Two suites because the releases are not
  hardened alike (password length 6 vs 10, composition requirements 0 vs 1,
  auto-logout off vs 3600, `gw/rem_start` REMOTE_SHELL vs DISABLED). Only
  controls whose deviation is an incident under any policy are asserted; the
  rest is reported and watched by a drift sentinel against a committed
  per-target reference. Trap: `TH_GET_PARAMETER` returns `RC=4` and an EMPTY
  string for an unknown parameter and is CASE SENSITIVE, so judge the return
  code before the value and keep `not_measurable` distinct from `deviation`.
- `src/SapApiLibrary/` is the **API channel** (stdlib-only): OData v2/v4 with
  one keyword set: full CRUD (`Post/Patch/Delete Odata`, SAP CSRF protocol,
  `If-Match`), `Post Odata Batch` (atomic changeset), pagination
  (`follow_next=True`), test-data factory (`track=True` +
  `Delete Created Entities`, `Ensure Odata Entity`), discovery
  (`Get Odata Metadata`, `List Odata Services`), Gateway preflight
  (`Gateway Should Be Active`, `Wait Until Api Available`, plus the tolerant
  `Classify Http Response`: three families of 404 under one status, a 2xx with
  an HTML body is not data), `Build Draft Entity Path`, OAuth2/mTLS auth,
  telemetry, optional RFC via pyrfc with `Call Bapi` (RETURN checked by type)
  and `Wait For Background Job`. Prefer preparing and
  cross-checking data through it; drive the screen only for what is under test
  (see `tests/robot/flagship_cross_paradigm.robot`, and
  `cross_paradigm_api_visual.robot` which adds a perceptual-hash screen baseline
  to that pattern; `exploratory_campaign_{a4h,fiori}.robot` are the matching
  self-contained ECC/Fiori exploration campaigns). The channel also has a suite
  of its own, `tests/robot/api/canal_api_odata.robot`, exercising the same
  business keywords against OData v2 (tag `a4h`) and OData v4 (tag
  `capsflight`): a v4 target is not optional, it is what catches what a
  forgiving SAP Gateway hides. The optional **RFC/BAPI** channel got its own
  suite on 2026-08-27, `tests/robot/api/canal_rfc_a4h.robot` (spec
  `specs/canal-rfc-a4h.md`, live 16/16) over
  `resources/rfc_keywords.resource`, the fourth mirror of the business
  vocabulary: read-only, cross-checking a table counted over RFC against the
  OData `$count` of the same system, classifying every refusal by its
  technical CODE, and **skipping cleanly** wherever the channel is absent
  (`pyrfc` has no wheel past Python 3.12) instead of going red. Its first live
  run felled two boundary defects, chief among them `pyrfc` rejecting a
  `DotDict`, which is every dictionary Robot builds.
  `tests/robot/api/canal_rfc_abap2023.robot` (spec `specs/canal-rfc-abap2023.md`,
  live 10/10) looks at that same channel across TWO ABAP releases, the first
  suite already passing on the newer target by variable override. What one
  release hides: the system carries **two airline catalogues of different
  populations** (18 classic, 16 modern, the smaller strictly included), so a
  crossing that mixes them fabricates a reproducible two-row gap; identity is
  proved by RELEASE, kernel and `CVERS` components, never by the system id, the
  application host name or the IP address; and two logon refusals return the
  same code AND the same text, so the test asserts the INDISTINCTION. It brings
  refusal assertions by **ABAP message identifier**
  (`Rfc Should Fail With Message Id`) and a deterministic **channel-surface
  artifact** (`sapfx_common/rfc_surface.py`) carrying its target's identity and
  scope. `tests/robot/cross/croisement_ddic_odata.robot`
  (live 9/9) is the cross-channel campaign: discovery-driven, bounded,
  read-only, reusable on ECC and S/4HANA, checking entity-set existence, volume
  (`$count` vs the SE16 count of the mapped table) and field contract
  (`$metadata` vs DD03L). Two rules it encodes, both paid live: a table's NAME
  proves no mapping, and a `sap:` annotation being PRESENT does not make it
  PERMISSIVE, so the write-candidate guard reads per entity set and verb by
  verb. `tests/robot/cross/simulation_ecriture_lecture.robot` (live 8/8) is its
  write counterpart: a row written through the SCREEN, observed through the API,
  deleted, and its disappearance asserted on the ENTITY (a count alone proves
  no cleanup). It skips in Suite Setup without opening a channel unless an
  explicit opt-in variable is passed; its SE16 locators live in
  `resources/page_objects/se16_table_entry.resource`, and SE16's mass-delete
  menu index appears nowhere in it, which a unit test enforces. A third
  criterion decides a write target and is invisible from OData: the table must
  allow maintenance (`DD02L`), which the `/DMO/*` RAP model does not.
- Business keywords live in `resources/*.resource`; recorders in `tools/`
  (shipped in the pack, so they are in the mypy scope and have their own
  coverage floor in CI; `--replay` fails on any step it could not run, and
  `--stop-file` gives an external caller a clean stop);
  rf-mcp plugins in `integrations/robotmcp/` (state providers serve a smart
  perception diff on an already-seen screen plus a stale-code warning when
  SAPFX code changed after server start, and an enriched application state
  under one contract for the three channels (`connected`/`state_error`,
  `collection_errors` for a failed section, `not_applicable` for one without
  meaning here): window stack/modal trap/telemetry on ECC, iframe scope +
  `ui5_runtime` probed before the UI5 messages on Fiori (a Web
  Components/WebGUI/hybrid page is a supported target, not an error), all
  three in one context crossing (`Get Ui5 Application State`); the
  `SapApiPlugin` serves the real
  API-channel state via `List Api Sessions`, never credentials; the
  `sapfx-mcp` overlay (not a fork) mounts the rf-mcp server unchanged and
  adds `sapfx_state`/`sapfx_screenshot`/`sapfx_reload` behind a
  version-window guard (non-blocking warning on the entry-point path) and
  honours the declared capabilities, deployment pin rf-mcp 0.35.0; API stores
  and Fiori frame state
  are partitioned by rf-mcp session; ECC remains one live session per process;
  the injected `__SAPFX` bundle is versioned by its content, so hot swapping
  the library replaces it at the next keyword call instead of leaving the
  page with the first bundle it ever received, and a reinstall neither
  doubles nor drops the fetch/XHR and MessageToast hooks; already-parsed
  resources do stay frozen for the process);
  repo-wide consistency scripts
  (doc pairing, vendor drift, guidance sync) plus the Windows deployment-pack
  assembler (`build_release_pack.py`, sources in `packaging/`, which also ship
  `install-rfc.ps1`: the OPTIONAL RFC channel provisioned end to end except the
  licensed SDK archive itself, which no script may download or redistribute,
  and which a workstation carrying SAP GUI 8.00 often does not need at all: its
  « SAP NWRFC x64 Shared » component already puts the RFC runtime in
  `System32`, so `pyrfc` loads and calls without `SAPNWRFC_HOME`, measured
  2026-08-27, which is what `-UseSapGuiRuntime` provisions; the 3.10 to 3.12
  interpreter constraint is NOT lifted by that, and the SDK stays the target
  for anything running off that one workstation),
  the healing
  drift bot (`healing_drift_report.py`: proposes/applies `resources/` patches
  from the `SAPFX_HEALING_LOG` journal, never touches tests) and the
  spec-sync guard (`check_spec_sync.py`: generated suites carry a
  `Spec: … (sha256:…, <date>)` provenance marker, stale suites fail CI, as does
  a spec sap-healer marked `> **Statut : PÉRIMÉE (…)**`; stamp after every
  regeneration) and the conventions guard (`check_conventions.py`: raw
  locators in a **generated** suite, `Sleep` anywhere, and convention #12's
  detectable motif: inline JS / `__import__` blocking in `resources/` under
  an exact-count `ALLOWED_12` allowlist, `modules=` blocked in suites;
  library-validation
  suites are informative only, `--strict` blocks them too) and the public
  export tool (`export_public_tree.py`: filtered tree for the public
  `robotframework-sapfx` repo: fail-closed transforms, blocking leak scan,
  PyPI README variant; itself excluded from the export) and the em-dash guard
  (`check_no_em_dash.py`: the character refused in every tracked text file, an
  `ALLOWED` map pinning an exact count for the few files that must quote it,
  `_vendor/` out of scope) in `scripts/`. `check_published_versions.py`
  refuses a stale SAPFX version in published instructions (pack filename,
  pip pin, wheel names) and a STATIC version badge where the dynamic
  shields.io one updates itself.
  All of them sit on the shared `scripts/_common.py`: UTF-8 forced on **stdout
  AND stderr** (Windows opens the standard streams in the machine's code page:
  an arrow killed the process on stdout, mojibake on stderr) and a
  section-aware read of the project version. The two first-generation packed
  scripts (`healing_drift_report.py`, `check_spec_sync.py`) keep a deliberate
  copy of that switch, so they stay usable even lifted out of the pack alone;
  the pack also ships `check_conventions.py` (sap-generator's gate, previously
  invoked by a path absent from the pack) and therefore `_common.py`. Unit
  guards hold this: the internal import closure stays inside the pack, every
  `scripts/<x>.py` a shipped file invokes is itself shipped or justified, and no
  pack-manifest path may sit in `export_public_tree.py`'s `EXCLUDE_PREFIXES`
  (copying `.claude/skills` wholesale had shipped the studio's PRIVATE comms
  skill in the released 0.6.6 ZIP; skills now enter by whitelist, and such notes
  stay unnamed because the leak scan forbids that name in public-bound files),
  and the export's byte-level **content** scan runs over the pack manifest in CI
  (5 hits on the shipped 0.6.6 ZIP, none on the fixed pack), since the export
  itself only runs by hand once per release.
  A `PostToolUse` hook (`scripts/hook_guards.py`, decision in a testable
  `decide()`) runs the em-dash guard on
  every edited file, the published-version guard on every edited `.md`/`.txt`,
  and the others after each edit.
  The built pack (`dist/sapfx-pack-*.zip`) is generated: never edit it in place.
- SAP test agents (plan → generate → heal, plus the offline `sap-istqb`
  designer: planner specs + recorder outputs → ISTQB test plan + test cases
  under `specs/istqb/`, replayable by an AI with any framework): canonical
  definitions in
  `.claude/agents/sap-*.md` (+ the `sapfx` toolkit skill in
  `.claude/skills/`, shipped in the pack), business test plans in `specs/`
  (French). All four query the **optional `qa-brain` MCP RAG** (shared QA
  memory: keywords, specs, lessons from real incidents) before their judgement
  calls; live observation still decides, and an absent server never blocks. The
  chat modes in `.github/chatmodes/` are **generated** from those definitions
  by `python scripts/regen_agent_definitions.py`: never edit a
  `*.chatmode.md` by hand; edit the `.claude/agents/` source and regenerate
  (`--check` fails CI/pytest on drift). Orchestrating commands:
  `/sap-maintain` (drift sentinel → healing telemetry → healer, one report)
  and `/sap-eval-healer` (blind healer evaluation via
  `scripts/agent_eval_harness.py`, inject/verify/restore a simulated drift).
  Every heal session appends the agent's diagnosis to `docs/heal-journal.md`
  (complementary to the runtime `SAPFX_HEALING_LOG` telemetry).
  Generated artifacts follow the industrial layout: suites under
  `tests/robot/{api, ui/ecc, ui/fiori, cross}`, page objects under
  `resources/page_objects/` (one `.resource` per screen/app),
  `resources/common.resource` for cross-screen keywords, environment data
  under `variables/` (never credentials); the healer patches that layer,
  never test bodies.
- `src/sapfx_common/polling.py` holds the shared `poll_until`/`retry_call`/
  `retry_until` primitives: reuse them for any wait/retry logic instead of
  writing new `while time.time() < deadline` loops (their own deadlines run on
  `time.monotonic()`, so a clock change mid-wait cannot alter the budget). `sapfx_common/com_safety.py`
  holds the shared defensive `CoInitialize` helper: reuse it for any code that
  might run off the main thread (rf-mcp) instead of a new inline try/except.
  `sapfx_common/healing.py` (locator-similarity scoring, shared ECC↔Fiori),
  `sapfx_common/healing_telemetry.py` (opt-in cumulative JSONL journal of
  locator repairs), `sapfx_common/perception_diff.py` (diff-mode perception),
  `sapfx_common/object_tree.py` (`GetObjectTree` JSON flattening, the
  structured perception model), `sapfx_common/semantic.py` (label-based
  geometric resolution + the verified inverse used by the recorder's
  `--semantic` mode, plus `is_editable_field`/`actionable_targets`/
  `screen_affordances` behind `mode=semantic` and the annotated screenshot),
  `sapfx_common/abap_list.py` (geometric row reconstruction),
  `sapfx_common/visual_hash.py` (pure perceptual dHash + crop/mask/tile
  primitives behind the visual assertions) and
  `sapfx_common/visual_baseline.py` (shared snapshot-baseline semantics +
  the Pillow decode boundary for BOTH channels, optional extra `visual`,
  plus the per-geometry baselines behind `per_resolution=True`)
  are the other shared primitives: extend them rather than
  duplicating scoring/diff/journal/geometry logic.
- CI (`.github/workflows/ci.yml`) runs a Python 3.10/3.12/3.14 matrix (3.10 =
  floor and 3.14 = latest verified, plain pytest; the full lane stays on 3.12),
  ruff + expanded
  mypy + `pytest --cov` (85% gate) + consistency/proof guards; Windows runs the
  real-pywin32 tests, dry-run, offline Browser smoke and installs the final ZIP
  with SHA-256/SBOM/provenance checks. A weekly UI5 matrix keeps current and
  1.136 LTS blocking while 2.x nightly remains informative. Generated
  code should stay green against this: run the commands above locally before
  assuming a change is done.

## Rules for generated code

1. Robot Framework **tests must not contain raw SAP element ids or CSS/XPath**:
   put locators in `resources/` keywords; tests speak business language. On the
   Fiori side, target UI5 controls, never DOM ids (they are dynamic).
   What `resources/` ships are **examples, not a universal SAP truth**: the
   business vocabulary of ONE installation, measured on this repo's lab targets,
   reusable in good part but to be verified on the target and adapted to the
   business domain (`resources/README.md`). What holds everywhere is `src/`, the
   libraries and their capabilities.
2. **Never suggest `time.sleep`/`Sleep` to wait for SAP.** Use
   `Wait Until Busy Done` / `Wait Until Element Present` (ECC) or
   `Wait For UI5 Ready` (Fiori).
3. **Assertions must be locale-independent**: check status-bar message *type*
   (`E`/`S`/…), never localized message text.
4. Every new library keyword needs an **off-SAP unit test** in `tests/unit/`
   using the fake-COM-objects pattern (`tests/unit/conftest.py`). Run with
   `python -m pytest tests/unit -q`: no SAP or browser required.
5. Dependencies: `pywin32` is **pinned exactly** in `requirements.txt`
   (loosening it breaks COM); `pyproject.toml` keeps floors only.
6. Python code comments/docstrings are in French in this repo; keep raised
   error messages in English. Do not translate keyword names or identifiers.
7. Docs are bilingual: every `docs/*.md` has a `*.fr.md` twin with cross-link
   banners: update both or neither. Never use the em dash (« — »)
   **anywhere in this repo** (docs, READMEs, `llms.txt`, specs,
   docstrings, comments, emitted strings, workflows, config): use a colon, a
   comma, parentheses, or split the sentence (French puts a space before the
   colon, English does not). Enforced by `scripts/check_no_em_dash.py` (CI +
   `PostToolUse` hook + unit test); only `_vendor/` is out of scope.
8. Before starting work and before any commit/merge/push, check the remotes:
   `git fetch origin` then `git status`, plus the public repo's PRs/issues
   (`gh pr list -R CyrilM29/robotframework-sapfx`,
   `gh issue list -R CyrilM29/robotframework-sapfx`): the public repo is
   detached from this one (export-per-release), so nothing else surfaces them.
   Surface any open PR/issue to the user before pushing.
9. Docs and both memory layers are updated BEFORE the commit, in the same lot,
   never "commit now, document later": `CLAUDE.md` + its mirrors (`AGENTS.md`,
   this file), `llms.txt`, the bilingual `docs/*.md` pair and the `CHANGELOG`;
   then `memory/` (project, public-safe, one file per durable fact + index) and
   the private cross-project base (personal/machine/cross-repo facts + index).
   Memory entries are dated observations: correct a wrong one in the same lot.
10. No credential ever gets a committed default value: passwords, API keys and
   tokens come from the command line (`-v "NAME: Secret:…"`) or the
   environment; such variables keep `${EMPTY}` in `resources/`,
   `tests/robot/` and `variables/`.
11. **A capability gap found on a live target is closed IN the shipped
   library.** A library keyword that misbehaves is FIXED in `src/`, never
   worked around in a suite/page object/resource; a missing one is CREATED in
   `src/Sap*Library` (pure logic in `sapfx_common`), never as inline JS in a
   page object nor an `Evaluate` in a suite; an existing workaround in an
   intermediate layer is PROMOTED into the library. Boundary: libraries carry
   CAPABILITIES (perception, resolution, waiting, engines, state, protocols),
   `resources/` carries one site's BUSINESS VOCABULARY. The libraries are what
   ships to PyPI, so a fix left in a resource helps nobody else. It still owes
   its off-SAP unit test, its rf-mcp intent-map entry, its Libdoc page and its
   CHANGELOG line; on a deployed pack, the workaround goes to
   `resources/site_keywords.resource` AND the defect is reported upstream.
   Promoting can also change SCOPE in silence: `Evaluate JavaScript` with a
   `${None}` selector evaluates on the page whatever the frame stack, a library
   keyword honours it, and the empty result that follows is plausible enough to
   misdirect the diagnosis. Check the promoted probe from EVERY caller.
12. **Never let a code file grow past 500 lines.** A file over the line is
   doing several jobs: split it along a seam the repo already uses (one mixin
   per capability under `keywords/`, pure logic into `sapfx_common`, one module
   per concern), never by cutting at line 500 to satisfy the number. In scope:
   everything a machine executes, whatever the language (Python, JavaScript
   including the injected `*.js.tpl` bundles, PowerShell, batch, unit tests)
   under `src/`, `integrations/`, `tools/`, `scripts/`, `packaging/`,
   `tests/unit/`. Out of scope: HTML/CSS and graphical supports, generated
   artefacts (the limit applies to
   their generator), docs, Robot suites and `.resource` files, and `_vendor/`.
   The files above the limit on 2026-08-25 were split the same day (debt
   settled); enforced by `scripts/check_file_length.py` (CI + `PostToolUse`
   hook + unit test), whose exact-count allowlist is empty.

## License

Apache 2.0 with vendored/ported Apache-2.0 code (robotframework-sapguilibrary,
playwright-sap ports, RoboSAPiens human-locator techniques). Preserve headers
and `NOTICE` attributions.
