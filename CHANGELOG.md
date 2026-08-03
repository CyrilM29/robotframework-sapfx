# Changelog

Notable changes to this project. Format inspired by [Keep a Changelog](https://keepachangelog.com/);
versions refer to the `robotframework-sapfx` distribution (`pyproject.toml`;
named `robotframework-sapecclibrary` up to 0.6.3 — entries below keep the
name that was current at the time).

## [0.6.4] — 2026-08-02

### Changed
- **Project renamed to SAPFX (2026-08-02)** — the internal codename becomes
  the one project name everywhere. Distribution `robotframework-sapecclibrary`
  → **`robotframework-sapfx`** (wheel filename follows; `install.ps1` glob,
  pack READMEs and NOTICE updated — library/module names `SapEccLibrary`,
  `SapFioriLibrary`, `SapApiLibrary`, `sapfx_common` unchanged). Private
  GitHub repo renamed `SAP_library_custom` → `sapfx` (GitHub redirects the
  old URL; `Homepage`/`Documentation` URLs updated in both pyprojects).
  New medallion logo (ROBOTFRAMEWORK-SAPFX): white background removed,
  `assets/logo.png` (512 master) replaced, `assets/logo_rf-sapfx.png` kept as
  the 1024 detoured master, extension icons 16/48/128 + recorder GUI icon
  regenerated via `gen_icons.py`.

### Added
- **HTML documentation report — 4th recorder export, both channels
  (2026-08-02)** — born from the 2026-08 RoboSAPiens watch (their
  `saveHtmlReport`, concept re-implemented, NOTICE extended). Desktop:
  `--export-report` (CLI + GUI checkbox) writes `<out>_report.html`, a
  self-contained page (inline minimal CSS, no JS, no external resource) that
  documents the recording — French business phrase per step (the spec-export
  phrasing, extended to **Fiori/UI5 and API keywords** so mixed cross-channel
  transcripts render too) with the exact RF line alongside (the report never
  invents), `# screenshot:` boundaries inlined as per-step data-URI images
  (missing capture = named honest mention), `password=` named arguments always
  masked. Improves on the original: per-STEP screenshots (theirs: one per
  window), pure text→text builder with injectable screenshot loader
  (convention #5). Web recorder: `rapport HTML (.html)` entry in the export
  menu (same self-contained page, one chapter per scenario, no screenshots —
  a page cannot photograph itself; extension 0.7.0 → **0.8.0**, artifacts
  regenerated). The raw recording is still never modified.
- **Dynamic vkey names in the desktop recorder (2026-08-02)** — also learned
  from RoboSAPiens: the native record engine now resolves virtual-key names
  beyond the static table through `GuiSession.GetVKeyDescription`
  (`set_vkey_resolver`, wired while recording, restored on teardown,
  COM-failure-safe) — `Send Vkey 17` gains its `# Shift+F5` comment; the
  static table keeps priority so outputs stay stable off-SAP.
- **Project presentation video (2026-08-02)** —
  `comms/visuels/sapfx-project-presentation.mp4` (3 min 20, English overlays,
  aicabra-branded): title/problem cards, VS Code walkthrough
  (test → resources layer → flagship), live SAP GUI vs A4H, live Fiori vs
  cap-sflight, real OData probe (v2+v4), an MCP agent session driving the
  live system (perception `@N` → act-by-reference) plus the rf-mcp
  `build_test_suite` output, proof cards (974 tests · 17/17 live · 3
  channels). Reproducible production kit under `comms/visuels/presentation/`
  (deterministic frame-by-frame card entrances — no `zoompan`, no screencast
  cadence —, desktop-region capture harness, ffmpeg edit pipeline); notes in
  `comms/video-presentation.md`; filming lessons in
  `memory/tournage-video-demos.md`.

### Pending
- **SAP GUI 8.10 validation** — GA was 2026-07-16: re-run the ECC smokes and the
  native-event record engine against 8.10 as soon as it is installed on the
  test workstation (the known-sensitive point is the COM event connection).

## [0.6.3] — 2026-07-27

### Added
- **Numbered screen map + act-by-reference (2026-07-25)** — Vibium-inspired
  (`map`/`@e1` pattern from Jason Huggins' agent-first browser tool, applied
  to SAP GUI): `Get Screen Map` numbers the actionable targets of the active
  screen (`@N` + verified human label + id + type + value, same affordance
  engine as `mode=semantic`), and `Resolve/Click/Fill Screen Ref` act by
  number — no id to copy, references are ephemeral (last numbered perception)
  and re-verified before every action (screen changed or element gone =
  actionable failure naming `Get Screen Map`). The Set-of-Mark annotated
  screenshot legend now feeds the same `@N` table, closing the
  vision → deterministic-action loop. Surfaced to agents via the ECC plugin
  keyword map + a dedicated rf-mcp hint (interactive piloting only — suites
  keep using `resources/` locators, convention #1). 8 new unit tests.
  **Fiori mirror**: `Get Ui5 Page Map` reduces the UI5 control tree to the
  numbered actionable targets (editable types marked `*` with current value,
  clickable types, human label from text/title/placeholder/tooltip; pure
  logic `ui5_page_map` in `_ui5_runtime.py`, `include_types=` override for
  list rows), and `Resolve/Click/Fill Ui5 Ref` act by number — liveness
  re-checked against the rendered UI5 registry before every action, frame
  scope respected, composite-control fill targets the inner `<input>` like
  `Fill Ui5 Input`, `mode=diff` memory untouched. Fiori plugin keyword map
  (exhaustiveness-tested), rf-mcp hint and guidance guard extended. 7 more
  unit tests.
- **`sapfx` toolkit skill** (`.claude/skills/sapfx/SKILL.md`) — the
  install-as-a-skill idea: one skill call teaches an assistant the three
  channels, the perception → action loop, the non-negotiable conventions and
  the agent cycle. Shipped in the Windows deployment pack
  (`.claude/skills/` added to the pack manifest; pack READMEs updated).
- **Vibium watch entry** in `comms/comparatif.md` (family 3, honest-nuance
  section, sources): complementary generalist, zero SAP coverage — its
  agent-first vocabulary is a de-facto standard SAPFX already speaks.
- **Agent feedback loops closed mechanically (2026-07-24)** — back-port from the
  sibling project `rf-test-agents` (same author, universal core of the
  plan → generate → heal cycle), where these mechanisms were designed and
  validated end-to-end on a live application. Three loops that existed only as
  prose in the agent definitions are now machine-visible:
  (1) **stale-plan marker** — sap-healer writes a normalized
  `> **Statut : PÉRIMÉE (date)**` blockquote when the business flow itself
  changed, and `check_spec_sync.py` now **fails while it is present**, until
  sap-planner re-explores and removes it (previously the healer "flagged the
  spec as stale" in a conversation report, i.e. nowhere);
  (2) **generation divergences** — sap-generator records where live SAP
  contradicted the plan under `## Écarts constatés à la génération`, *before*
  re-stamping, so the provenance hash covers the annotated plan and the planner
  sees the gaps on its next pass;
  (3) **`docs/heal-journal.md`** — the agent's own diagnosis per heal session
  (failure class, live evidence, anchoring lesson). Complementary to, not a
  duplicate of, the runtime `SAPFX_HEALING_LOG` telemetry: the telemetry says
  *what keeps drifting*, the journal says *why and what to do about it*.
  sap-planner reads it before writing locator notes.
- **`scripts/check_conventions.py`** — conventions #1/#2 were *stated*
  (CLAUDE.md, `_guidance.py` hints, agent definitions — all checked by
  `check_guidance_sync.py`) but nothing verified they were *held* by the
  artifacts. This guard does: raw locators (SAP GUI ids like
  `wnd[0]/usr/ctxt…`, UI5 control addresses, CSS/XPath) in a test body, and
  `Sleep` anywhere. Convention #1 is **blocking on generated suites only** —
  recognised by their provenance marker; the hand-written library-validation
  suites (`business_data_exploration`, `exploratory_campaign_a4h`, …) are
  reported for information, since driving SAP by raw ids is precisely their
  purpose (`--strict` blocks them too). Auto-maintained: no exemption list.
  Unit tests in `tests/unit/test_check_conventions.py` (22 cases).
- **`scripts/hook_guards.py` + `PostToolUse` hook** — both guards run after
  every Write/Edit of `specs/`, `tests/robot/`, `resources/`, `variables/`:
  a conventions violation blocks (exit 2), spec-sync drift is reported
  non-blocking (it can be transient mid-generation).
- **CI**: `check_spec_sync.py` and `check_conventions.py` now run in the
  guards job — the provenance guard existed but was never wired into CI.

### Changed
- **rf-mcp 0.35.0 compatibility (2026-07-24)** — the overlay's startup guard
  window (`sap_robotmcp/_compat.py`) widens from [0.31, 0.32) to [0.31, 0.36)
  after a wheel-level re-validation of every anchor: `plugins/contracts.py`
  and `plugins/manager.py` are byte-identical between 0.31.2 and 0.35.0,
  `plugins/base.py` only gains a backwards-compatible `keyword_library_map`
  attribute, `robotmcp.server.{mcp, execution_engine, main}` and the
  RF-native-context executor keep their shapes (0.32/0.33 were never
  published). The `get_session` probe now inspects the **`ExecutionCoordinator`
  class** instead of `server.execution_engine`: since 0.34 that attribute is a
  lazy proxy and any attribute access would materialize the whole execution
  engine during the compat check, re-slowing the MCP handshake upstream just
  sped up (locked by 3 new unit tests). Deployment pin
  `packaging/constraints-deploy.txt` bumped to `rf-mcp==0.35.0` (new
  transitive dependency: `tomlkit`). Field notes: rf-mcp ≥ 0.34 classifies a
  session as native-desktop (PlatynUI) when the `manage_session` scenario
  text contains desktop signals ("desktop", "win32", an `.exe` name…) and
  then serves a desktop stub instead of the SAP page source — agent
  definitions now instruct to say "SAP GUI"/"ECC" instead; the `sapfx_state`
  overlay tool is immune (calls the SAP providers directly). Full unit suite
  (946) green against the real 0.35.0; live A4H agent cycle not re-run.

### Fixed
- **Pack `.cmd` launchers shipped with LF-only line endings (2026-07-27)** —
  the repo-wide `.gitattributes` rule (`* text=auto eol=lf`) also applied to
  `install.cmd` / `recorder.cmd`, and cmd.exe's parser trips on LF-only files:
  double-clicking the 0.6.2 pack's `install.cmd` echoed two
  «'M' n'est pas reconnu…» errors on the `REM` header lines (the install
  itself still completed — cosmetic but alarming, and parser behaviour on
  LF-only batch files is version-dependent). Fixed in depth: `.gitattributes`
  exception (`*.cmd`/`*.bat` → `eol=crlf`), working-tree launchers converted,
  and `build_release_pack.py` now normalizes every staged `.cmd` to CRLF so
  the ZIP is correct regardless of the builder's checkout (unit-locked).
- **`check_spec_sync.py` was blind to ventilated suites** — it globbed
  `tests/robot/*.robot` non-recursively while sap-generator's contract places
  new suites under `tests/robot/{api, ui/ecc, ui/fiori, cross}`. Latent today
  (all 25 suites are still flat), it would have silently skipped every
  generated suite as soon as the ventilation started. Now `rglob`.
- The provenance marker also carries the **generation date**
  (`sha256:…, AAAA-MM-JJ`); markers stamped before this change stay valid.

## [0.6.2] — 2026-07-23

### Added
- **Agentic-layer upgrade pass (2026-07-23)** — the rf-mcp/agents system
  catches up with three releases of library features and closes its
  operational loops. (1) **Guidance + intent maps refreshed**: the ECC/Fiori
  keyword maps and hints now cover multi-session aliases, `Attach To Open
  Session`, `mode=semantic`, Set-of-Mark annotated screenshots, visual
  baselines/`Check Screen Against Watch`, the pointer effector, dynamic
  timeouts, FLP intent navigation, IDP login, business vocabulary;
  `check_guidance_sync.py` grew a **keyword-map freshness guard** (flagship
  keywords per mixin, textual — this drift class cannot recur). (2) **State
  providers serve smart diffs**: a changed already-seen screen returns the
  `perception_diff` differential (paired renames on ECC, self-describing
  header, `full_source=true` opt-out, arbitration never serves a diff longer
  than the screen). (3) **Live application state**: new ECC keyword
  `Get Open Windows` (JSON-safe window stack, `modal=True` on
  GuiModalWindow); `get_application_state` adds `modal_open`/`modal_titles`
  (the SESSION_MANAGER leftover-modal trap), status-message type and session
  telemetry, each section best-effort (`collection_errors`);
  `run_keyword_in_context` gained an `allow_structured` channel. (4)
  **Stale-code warning** (`sap_robotmcp/_staleness.py`): providers announce
  when SAPFX code changed on disk after the rf-mcp server started (the
  frozen-class trap becomes actionable). (5) **Session hygiene encoded in
  the three agent definitions** (preflight + close-even-on-failure, field
  note 2026-07-21; chat modes regenerated). (6) **`/sap-maintain`**
  orchestrator (sentinel → healing telemetry → sap-healer → one report) and
  (7) **blind healer evaluation harness** (`scripts/agent_eval_harness.py`
  inject/verify/restore + `/sap-eval-healer` — the 0.3.0 blind exercise made
  replayable). Instructed tracks documented in `docs/test-agents.md` (MCP
  vision channel: no image support in the rf-mcp 0.31 plugin contract,
  fastmcp could carry it — upstream proposal; planner read-only guard:
  design + why not built). +39 unit tests (884 collected).
- **Industrial project layout encoded in the generator/healer (2026-07-23)**
  — generated artifacts now follow the classic ventilation, rooted on the
  existing `tests/robot/` and `resources/`: new suites under
  `tests/robot/{api, ui/ecc, ui/fiori, cross}`; **page objects** under
  `resources/page_objects/` (one `.resource` per ECC screen/transaction or
  Fiori page/app — locator variables on top, business keywords below);
  cross-screen vocabulary in `resources/common.resource` or the shipped
  global resources; environment data under `variables/` (`env_<env>.yaml`,
  shared `locators.py` — credentials never in a file, `Secret:` variables
  only); outputs under `results/`. Legacy flat suites stay untouched; the
  healer's repair surface is that layer (page objects / common / variables /
  shipped resources — `site_keywords.resource` override on a deployed pack),
  never test bodies, and a locator found hardcoded in a test body is itself
  a finding to move into a page object. `agent_eval_harness.py` now also
  protects `variables/` in its verdict manifest.
- **`sapfx-mcp` overlay v1 (2026-07-23)** — NOT a fork: a console entry point
  (`sap_robotmcp/server.py`, `[project.scripts]` of the plugins wheel) that
  mounts the rf-mcp server unchanged and adds the three tools the 0.31
  plugin contract cannot express (every gap established live the same day —
  CLAUDE.md field notes): `sapfx_state` (SAPFX state providers called
  directly — real diff-by-default `page_source` semantics, enriched
  `application_state` with `modal_open`/status/telemetry that rf-mcp never
  routes), `sapfx_screenshot` (real MCP image content, plain or Set-of-Mark
  annotated + `number -> id` legend; `run_keyword_in_context` gained keyword
  `arguments` passthrough for `include_types`), and `sapfx_reload` (the
  live-validated plugin-layer hot-reload protocol, encoded). A startup
  **compatibility guard** (`_compat.py`) pins the tested rf-mcp window
  ([0.31, 0.32)) and probes every internal anchor, refusing to start on
  mismatch (`SAPFX_MCP_FORCE=1` overrides loudly) — the vendor-drift-guard
  spirit applied to the host server. Logic isolated in `_overlay.py`
  (typed, mypy scope extended) and covered off-SAP, including two living
  tests against the installed rf-mcp (anchors + real mount + real reload
  round-trip). Templates switched to the new launcher: `.mcp.json`,
  `.vscode/mcp.json`, and the pack's `install.ps1` (resolves
  `sapfx-mcp.exe`, falls back to `robotmcp.exe` on older wheels). Health
  rule documented in docs/mcp-integration.md: every wiring accepted
  upstream must shrink the overlay. `sapfx_screenshot` covers BOTH channels:
  ECC in-memory capture, and a Browser-library fallback
  (`Take Screenshot ... return_as=base64`, named argument converted by the
  RF native context) for Fiori/web sessions — `annotated` stays ECC-only
  and fails honestly elsewhere. +26 unit tests (910 collected).
  **Live-validated the same day, 16/16**, through a real MCP stdio client
  driving `sapfx-mcp.exe` against A4H (SE16/T000): the 3 overlay tools
  served alongside the 21 rf-mcp tools; `sapfx_reload` re-registering fresh
  plugins; `sapfx_state` picking `SapEccLibrary` with no `active_library`
  set, serving the live `application_state` (transaction, `modal_open`
  False→True on the count popup, status type, telemetry) and the smart
  diff BY DEFAULT (290 bytes vs 12,025 full; `full_source=true` forces the
  complete view); `sapfx_screenshot annotated=true` returning a real MCP
  `ImageContent` (Set-of-Mark box on the popup's Close button, legend
  `{"1": "wnd[1]/tbar[0]/btn[0]"}`) — the vision loop closed end-to-end;
  clean `Close SAP` teardown in the client's finally. **Same-day UI5
  validation, 12/12**, against the public OpenUI5 Demo Kit (headless
  Chromium, no SAP): `sapfx_state` auto-picks `SapFioriLibrary` (Browser
  ignored), full UI5 tree as baseline (26,528 bytes) then the XML diff BY
  DEFAULT after a real SearchField interaction (4,547 bytes, typed text
  visible in the diff), Fiori `application_state` served, and
  `sapfx_screenshot` returning the real page image via the Browser
  fallback (325 KB — search suggestions visibly triggered by the typed
  text); `annotated=true` fails honestly (ECC channel). The 788-byte
  premature-tree run re-confirmed the 2026-07-17 lesson (wait for a
  RENDERED control after `Wait For UI5 Ready` before perceiving).
- **The API channel joins the MCP layer (2026-07-23)** — the third channel
  had NO rf-mcp presence at all (no hints, no keyword map, no state
  provider). Now: `SapApiPlugin` (entry point `sap_api`) with API-channel
  guidance (cross-channel pattern, aliases + `Secret` passwords, v2/v4
  envelope, prefer `$count`, automatic CSRF, optional pyrfc), the full
  keyword map, and a state provider — `get_page_source` answers honestly
  that the channel has no screen (perception IS the keywords' return
  values), `get_application_state` serves the REAL channel state via the
  new `SapApiLibrary` keyword **`List Api Sessions`** (open aliases,
  base_url, sap-client, authenticated/CSRF flags — never credentials).
  The `sapfx-mcp` overlay serves it (`SapApiLibrary` added to
  `SAPFX_LIBRARIES` and to the reload order); `check_guidance_sync` guards
  the new map. **Live-validated 9/9** through the real MCP stdio client
  against the A4H Gateway: `$count` SEPMRA_SHOP/Products = 205 (the
  flagship business fact), entity read (`top`/`select`), `sapfx_state`
  auto-picking `SapApiLibrary` with the live channel state (zero
  credential in the whole response), honest no-screen page_source, and the
  emptied state re-verified after `Close All Api Sessions`. +11 unit tests
  (921 collected).

## [0.6.1] — 2026-07-22

### Added
- **`Set Default Timeout` / `Set Poll Interval` (review feedback)** — the two
  library-level wait settings, previously frozen at import time
  (`__init__` arguments), are now adjustable mid-suite, following the
  established RF idiom (`Set Browser Timeout`, `Set Selenium Timeout`): both
  keywords return the previous value as a Robot time string, ready to be
  restored in a teardown (widen the timeout around one slow transaction —
  demo-data generation — without imposing it on the whole suite). Scope is
  the library instance (`SUITE`), so a change never leaks into the next
  suite. +4 unit tests (841 collected). Live-validated vs A4H (2026-07-22,
  4/4): return-value round-trip, the shortened timeout is the *actual* wait
  fallback (failure measured at ~5s, not the 30s import value), real
  navigation at the new poll step, restore from the returned value.
- **`Set Ui5 Timeout` / `Set Poll Interval` on the Fiori side (review
  feedback)** — the ECC↔Fiori mirror of the pair above, same contract
  (previous value returned as a Robot time string, restorable in a teardown,
  `SUITE`-scoped instance). `ui5_timeout` keeps its as-a-string storage
  convention (every use site converts), and the new value is validated
  BEFORE being adopted — an invalid time string can never corrupt the
  library-wide polling budget. Same-name `Set Poll Interval` in both
  libraries follows the mirror-alias philosophy (qualify or use
  `Set Library Search Order` in cross-channel suites). +4 unit tests
  (845 collected). Live-validated (2026-07-22, 4/4): round-trip, the reduced
  `ui5_timeout` really bounds the tree probe (~2s measured, not 15s), and
  nominal resolution works at the new poll step on a real UI5 runtime.

### Changed
- **The two most generic Fiori failures now name the diagnostics layer
  (review feedback)** — the exhausted fallback chain (`Resolve Ui5 With
  Fallback`) points to `Log Fiori Diagnostics`, and the no-UI5-tree failure
  (`Get Ui5 Page Tree`) points to `Get Page Composition`. The *targeted*
  failures already carried self-correcting hints (`_relaxed_hint` type
  probe, dom→composition, wc→role); these two generic dead-ends did not
  name any next step. Locked by extending the existing failure-path tests,
  and both enriched messages observed live on a non-UI5 page (2026-07-22).

### Removed
- **Dead `_ERROR_MESSAGE_TYPE` constant (review feedback)** — a leftover from
  the pre-fork `run_transaction`, which detected failures by status-message
  *type*; the override has compared `session.Info.Transaction` since the live
  A4H validation proved the "type `E`" hypothesis wrong (an unknown
  transaction reports type `S`). The constant was referenced nowhere.

### Fixed
- **`Run Transaction` namespace tcodes, second pass (review feedback)** — two
  flaws in the expected-vs-`Info.Transaction` comparison introduced with the
  0.1.x namespace fix: (1) the comparison stripped leading `/` from the
  *expected* side only, so it broke whenever the Scripting API returns a
  namespaced tcode WITH its leading slash (sy-tcode form `/BEV1/RCA01`) — both
  sides are now normalized identically, making the check independent of which
  form the API returns; (2) a namespace starting with N, O or I
  (`/IWFND/MAINT_SERVICE`, `/IWBEP/…`) was mistaken for an already-prefixed
  entry by the `transaction[:2]` check, so no `/n` was prepended and SAP read
  the raw OK-code as the `/i` system command — the new `_has_nav_prefix`
  disambiguates by the shape of the remainder (after a real prefix comes either
  a slash-free tcode or a `/`-leading namespace, never `WFND/…`). Unit-locked
  (+4 tests), verified live vs A4H: `Info.Transaction` returns the sy-tcode
  form WITH the leading slash (`'/IWFND/MAINT_SERVICE'` observed on SAP GUI
  8.00), and the raw-namespace, plain-tcode and explicit-prefix paths all pass
  through the fixed keyword.
- **`--transpile-vbs` no longer assumes UTF-8 sources (review feedback)** —
  real-world ALT+F12 recordings are often ANSI (system codepage, cp1252 in
  Western Europe) or UTF-16 (Notepad "Unicode", PowerShell 5.1 `Out-File`),
  and the forced-UTF-8 read corrupted both *silently*: UTF-16's NUL bytes are
  *valid* UTF-8, so the transpile yielded 0 steps with no exception, and ANSI
  accents in recorded literals became U+FFFD. New `decode_vbs_source` decides
  by explicit BOM (UTF-8/UTF-16 LE/BE) > NUL-byte heuristic (BOM-less UTF-16,
  endianness from NUL positions) > strict UTF-8 attempt > ANSI fallback
  (`mbcs` on Windows), replace-mode on fallbacks so it never raises.
  Unit-locked (+7 tests, 833 collected) and verified through the real CLI:
  the same recording in cp1252, UTF-16+BOM and BOM-less UTF-16 transpiles to
  identical steps with `Société Générale` intact.
- **Spec exports render interpolated data as Markdown code spans (review
  feedback)** — both recorders' spec export wrapped recorded values in French
  quotes (« »), letting Markdown metacharacters in the data alter the rendered
  plan: a SAP selection wildcard `*LH*` displayed as an italic "LH". Every
  interpolated datum (values, slugs, tcodes, labels) now goes through
  `md_code`/`mdCode`, a CommonMark-correct code span whose fence outgrows any
  backtick run inside the value (a bare backtick pair would just move the
  injection); the raw-line sections that already used single backticks get the
  same treatment. This also aligns the generated drafts with the `specs/`
  reference example's own style (technical tokens in code spans). Desktop +
  web (`_ui5_js.py`, recorder artifacts regenerated); web record smoke re-run
  3/3 after regen (+2 tests, 835 collected).
- **Polling record engine records uncheck and field-clear actions (review
  feedback)** — `_field_step` gated every emission on a truthy value, so
  unchecking a `GuiCheckBox` (and clearing a text field) between two polls
  was silently dropped, while the native event engine records `Unselect
  Checkbox` / `Input Text … ${EMPTY}` — the 0.6.0 escaping pass added
  `${EMPTY}` precisely so a clear stays replayable, but the poll-side gate
  was forgotten. Safe by construction: `diff_to_steps` already discards
  new-and-empty fields, so a falsy value reaching `_field_step` is always a
  deliberate user change. Radio buttons keep the emit-if-True rule (their
  `False` is induced by the newly selected sibling). +2 tests (836
  collected); live record smoke re-run 1/1 vs A4H.
- **`--replay` CLI no longer masks the real step error** — the default replay
  library was built with `screenshots_on_error=True`; outside a Robot run the
  failure handler's `take_screenshot` needs the RF context and replaced the
  actual error with `Cannot access execution context` (caught during the
  2026-07-21 live validation pass, where it hid a wrong-session attach). The
  CLI factory now passes `screenshots_on_error=False` — there is no Robot log
  to embed a capture into anyway. Unit-locked (+1 test, 837 collected).

## [0.6.0] — 2026-07-20

### Fixed — peer-review pass on the recorder work (2026-07-20)
A full review of the 07-19/07-20 recorder passes before commit; every finding
fixed and unit-locked (810→823 tests).
- **`name=`/`text=` matching now collapses whitespace on the DOM side** (dom
  AND wc engines, `wsCollapse`): the recorded accessible name is
  space-normalized (an RF cell cannot carry 2+ spaces), but the live accname of
  a multi-node target (`<button>Add\n  item</button>` — typical React, the dom
  engine's very audience) kept its indentation newlines, so a recorded `name=`
  could never re-resolve. `captureWc` also normalizes its recorded text (a
  newline in an RF cell is invalid).
- **Desktop recorder now RF-escapes recorded values** (`rf_escape_value` /
  `rf_unescape_value`, exact mirror of the web recorder's 0.7.0 escaping):
  typed values, combo labels and hot-assertion texts survive `${…}`, 2+ space
  runs, leading `#` and `word=`; clearing a field records `${EMPTY}` instead of
  a broken line. `--replay` applies the exact inverse before invoking keywords;
  the spec export displays values unescaped.
- **GUI record no longer overwrites the previous take**: the auto-generated
  output name is regenerated on every record launch (a user-typed name is
  respected — overwriting is then an explicit choice). `resolve_record_out`
  pure helper, unit-tested.
- **Spec exports honour the specs/ contract on unknown steps** (both channels):
  an untranslated step CARRYING a locator/id no longer leaks it into the steps
  list — the exact line moves to « Points de vigilance »; id-free raw steps
  stay verbatim.
- **Web resource-first export wraps text-assertion pairs**: `${texte} =    Get
  Wc/Dom Text` + `Should Be Equal` become ONE business keyword with the locator
  in the resource (convention #1 had a leak there).
- **Deliberate double-Enter is kept**: the 500 ms dedup exemption now covers
  `Keyboard Key` like clicks. **`--suite` CLI help** named the wrong Suite
  Setup keyword (`Connect To Session` — the very keyword the 07-19 live replay
  proved insufficient). **`Attach To Open Session`** wraps its remaining COM
  accesses (connection closed mid-attach → actionable error). **`.gitignore`**
  now whitelists the committed demo key-frame PNGs (`comms/visuels/*-poster-*`)
  and ignores the raw `.webm` intermediates (the deliverable is the MP4).
- **cap-sflight demo authenticates against cds v9 mocked auth**: anonymous
  OData requests now take a 401 and the List Report stays empty (caught by the
  live recorder test re-run, 2026-07-20) — `fiori_demo_video.robot` passes the
  mocked `alice` user via `httpCredentials` (overridable with `-v CDS_USER:`).

Both recorders re-validated LIVE after the fixes, end-to-end: ECC vs A4H
(record with OK-code merge, escaped-value round-trip read from the real screen
and replayed, the three exports, `robot --dryrun` of the pair, `--replay` via
`Attach To Open Session` — 3/3) and web vs the real cap-sflight Fiori Elements
app (real gestures measured `Travels (4,133)` → `(91)`, recording resumes after
reload, in-page replay re-filters the app, exported resource-first pair re-run
green by real `robot` — 1/1).

### Added — Selenium-IDE-spirit pass on both recorders (2026-07-19)
The good half of the record-and-playback spirit (instant feedback, editability,
fallback locators, native SAP ALT+F12 lineage), grafted onto our semantic
locators and resource-first outputs.
- **Web — in-page replay (`play`)**: the recording replays inside the page,
  each step resolved by the same engines the library uses, highlighted,
  executed (~3 steps/s); UI5 steps retry their recorded xpath fallback; first
  failure stops and marks the row. Synthetic replay events are never
  re-recorded. Live-validated: the replayed click really drives the fixture
  (counter increments), the replayed fill lands in the field.
- **Web — steps born self-healing**: every recorded UI5 click/fill carries its
  shortest-xpath fallback as an RF end-of-line comment (`# xpath: …`); the
  resource-first export converts it into `Resolve Ui5 With Fallback    xpath=…`
  followed by the Browser action — the exported keyword repairs itself
  (logged, never silent) from day one.
- **Web — multi-scenario sessions (`+test`)**: marker steps split every export
  (.robot / resource-first / spec) into several test cases, browser bootstrap
  only in the first. **`.robot` re-import**: an exported suite loads back into
  the panel (bootstrap lines skipped, markers restored) — byte-identical
  round-trip, live-validated. **Double-click in-place step editing.**
- **Web — recording no longer blocks the app**: the old record-mode
  `preventDefault` froze the application under recording (you could not drive
  a real flow); clicks now pass through, only Alt+click assertion gestures are
  swallowed. Caught live by the replay validation (the fixture counter stayed
  at 0). Extension 0.5.0 → 0.6.0.
- **ECC — `--replay FILE` + GUI «Rejouer»**: replays a recording against the
  already-open SAP GUI session (`Attach To Open Session`), stop on first
  failure with the offending step named; unknown keywords reported, comments
  skipped. Live-validated 4/4 vs A4H.
- **ECC — `--transpile-vbs FILE`**: converts SAP GUI's built-in ALT+F12 VBS
  recordings into SapEccLibrary keywords through the SAME state machine as the
  native engine (OK-code merge, context-menu pairing, cell tracking; unmapped
  calls kept as comments). No SAP session needed; `--suite`/exports apply.
  Validated end-to-end live: VBS → transpile → `--replay` vs A4H 4/4, and the
  generated resource-first pair passes `robot --dryrun`.
- **ECC — self-healing resource-first export**: `--semantic` lines (label +
  technical id) generate keywords resolving through `Resolve Element With
  Healing    ${LOC_…}    label=…` — nominal id path first, scored repair +
  label anchor otherwise. **GUI**: double-click step editing in the panel.
  790→808 unit tests.

### Added — scripted demo takes for both recorders (2026-07-20)
Two committed, reproducible video generators — the recording is a *script*, so a
retake is a one-line edit and a re-run, and every figure shown is measured live.
- **`tools/recorder_web/demo/fiori_demo_video.robot`** — Playwright `recordVideo`
  against the local cap-sflight app, captions injected into the page, **headless
  by default** (a visible window stays interactive, so a stray mouse move ruins
  the take). Output: `dist/video/sapfx-fiori-recorder-demo.mp4`.
- **`tools/recorder/demo/ecc_demo_video.robot`** — the ECC channel is a *desktop*
  app with a console recorder, so nothing in-page can be injected: the take
  captures the **SAP GUI window only** (`ffmpeg gdigrab title=…`, no desktop
  leakage), adds a band under the image and burns subtitles carrying the steps
  the record engine **actually emitted**, timestamped at runtime. The subtitle
  track is re-aligned by a **measured** offset (capture starts before the
  scenario clock; without it the subtitles ran ~2 s ahead of the picture — caught
  by reading screen titles frame by frame). Output:
  `dist/video/sapfx-ecc-recorder-demo.mp4`. Cannot be headless: do not touch the
  machine during a take.

### Fixed — web recorder, caught by a LIVE run against real Fiori Elements (2026-07-20)
Validation of the web recorder against a real Fiori Elements List Report
(cap-sflight, UI5 1.139, 591 rendered controls) — not a fixture. Two genuine
defects the fixture smokes and the dryrun could not surface:
- **resource-first export — fills targeted the control root.** A composite UI5
  field (`sap.m.Input`, `SearchField`) roots on a `<div>`; the generated keyword
  emitted `Fill Text    ${cible}` on it, so the exported pair failed at runtime
  (*"Element is not an `<input>`"*) even though `robot --dryrun` was green. The
  generated keyword now descends into the inner element —
  `Fill Text    ${cible} >> css=input, textarea` — exactly as `Fill Ui5 Input`
  already did. Exported pair re-run live: green.
- **panel header clipped its own buttons.** At 380 px the 7-button header
  overflowed and `overflow:hidden` cut `stop` off — genuinely unreachable by
  mouse. Panel widened to 470 px, title ellipsises instead of pushing buttons
  out, buttons never shrink. Seen on a video frame, unit-locked since.

808→810 unit tests. Also live-proven in the same pass: injection into a real FE
app, recorded steps addressing UI5 controls via stable `fe::…` ids (never the
generated `__clone…` DOM ids), step survival across a full page reload, in-page
replay measurably driving the app (`Travels (4,133)` → `Travels (91)`), the three
export formats, and the exported suite re-run green by real `robot`.

### Added — web recorder robustness for real-world sessions (2026-07-20)
Hardening born from the same live Fiori Elements pass. **Extension 0.6.0 → 0.7.0.**
- **Recording state survives navigation**: the recording flag is persisted
  (sessionStorage) next to the steps — after a full-page reload + re-injection
  (snippet re-pasted or extension shortcut), recording RESUMES by itself instead
  of silently dropping every interaction; an explicit `stop` never auto-resumes.
- **Explicit record state across frames (`setRec`)**: the popup and the
  Alt+Shift+R shortcut now read the aggregate state first, then push ONE
  explicit on/off to every frame — per-frame toggles could drift into
  anti-phase (one frame starting while another stopped). The shortcut also
  re-injects idempotently in allFrames (iframes that appeared since the last
  injection are covered) and restricted pages (chrome://, Web Store) show a
  transient `n/a` badge instead of dying in an unhandled rejection.
- **Robot Framework escaping of recorded values** (`rfEscape`/`rfUnescape`):
  typed values and asserted texts are escaped on the way into a `.robot` line
  (`${…}` stays a literal, 2+ space runs, leading `#`/space, trailing space,
  `word=` named-arg ambiguity) and unescaped by the in-page replay — a value
  like `${TAX} 10  %` no longer breaks the exported suite.
- **Deferred Enter is never lost on full-page navigation**: `beforeunload`
  flushes the one-tick-deferred `Keyboard Key    press    Enter` and marks the
  replayable wait before the page dies. Deliberate repeat clicks (stepper `+`,
  pagination) are kept — only a double dispatch of the SAME click within
  500 ms is deduplicated. Clipboard failures now flash `copy failed` instead
  of lying `copied`. `minimum_chrome_version` 111 declared (scripting MAIN
  world floor).

### Added — Recorder upgrade pass, both channels (2026-07-19)
- **`Attach To Open Session` (SapEccLibrary)** — binds the library to an
  ALREADY-open SAP GUI session by connection/session index, with actionable
  errors. `Connect To Session` alone only acquires the scripting engine — the
  session itself was only ever set by `Connect To Existing Connection`, which
  needs the exact connection description. Discovered by live-replaying a
  recorder export on A4H (the generated Suite Setup could not work); the
  generated suites now use the new keyword.
- **Resource-first + spec exports (both recorders)** — the raw transcript is now
  a *draft*, not the end product. Desktop: `--suite` (complete replayable
  `.robot` with `Suite Setup    Attach To Open Session`), `--export-resources`
  (`<out>_keywords.resource` — each id becomes a `${LOC_…}` variable wrapped in
  a business keyword — plus `<out>_resource_first.robot` calling only those
  keywords: **no raw id left in the test**, project convention #1, and the layer
  sap-healer repairs), `--export-spec` (`<out>.spec.md`, a `specs/`-format plan:
  business-language steps, ids relegated to factual notes — the recording
  becomes the input of the plan→generate→heal cycle). Web: the `export`
  button opens a 3-format menu (.robot / resource-first pair / specs plan); the
  generated pair was validated with a real `robot --dryrun`.
- **Live assertions while recording (desktop)** — global hotkeys during
  `--record` (both engines): Ctrl+Alt+A inserts `Element Value Should Be` on the
  focused element (presence check if no readable text, never a password value);
  Ctrl+Alt+V inserts `Screen Should Match Baseline    <out>_etape_NN` (visual
  snapshot). Rising-edge detection via GetAsyncKeyState, pure logic unit-tested.
- **dom-engine capture in the web recorder** — the recorder now covers the
  non-SAP zones of hybrid pages: new `captureDom` in the bundle (computed ARIA
  role + accessible name, CSS light-DOM path fallback, **interactive targets
  only** — a click on a bare div records nothing), hover label `DOM <role>`,
  `Click/Fill Dom …` steps, `dom` copy button, `Resolve Dom Element` capture
  lines. Right-click **assertion menu** while recording (visible / text per
  engine — text via `Get Wc/Dom Text` + `Should Be Equal` pairs where no direct
  keyword exists); Alt+click shortcuts kept. **Enter** captured as
  `Keyboard Key    press    Enter` (deferred one tick so the field's `change`
  lands first; textarea excluded). Navigation now emits **`Wait For UI5 Ready`**
  when the UI5 runtime is present (keyword definition embedded in exports — the
  downloaded file stays self-contained), `Wait For Load State` otherwise.
  Fill/wait **compaction** (re-typing a field replaces the previous fill,
  consecutive waits collapse) and a **cross-origin iframe warning** in the panel
  (the extension's allFrames injection is the answer). Extension 0.4.1 → 0.5.0.
- **Extended native mappings (desktop record)** — grid context menus
  (`pressToolbarContextButton`+`selectContextMenuItem` → one
  `Select Context Menu Item`), tree nodes (`selectNode`/`expandNode` →
  `Select Node`), single selected grid row → `Select Table Row`, grid cell
  clicks keep their row/column (tracked from `currentCell*` events) in an
  enriched comment. Opaque zones (`GuiShell`/`GuiChart`): capture (native
  hit-test) and hover now also suggest `Click Element At Offset` with the
  cursor's relative position — the pointer fallback for what the Scripting API
  cannot script.
- **Tkinter GUI parity** — record options exposed (suite / resource-first /
  spec checkboxes) and a live **steps panel**: follows the output file as steps
  are emitted, reorder/delete, save the corrected file (same
  `parse_recorded_body`/`replace_recorded_steps` helpers as the CLI, pure and
  unit-tested). 751→790 unit tests.

### Fixed — sid engine now matches the REAL WebGUI's lsdata encoding (2026-07-18)
- **Live-discovered by the agent cycle** (sap-planner exploration of the A4H
  SAP GUI for HTML): the real WebGUI emits `lsdata` as a JS literal
  (`SID:'wnd[0]/…'`, unquoted keys, single quotes) while `sid_xpath` and the
  bundle's `captureSid` only matched the JSON form (`"SID":"…"`) our fixtures
  use — 0 match on a live system. `sid_xpath` now emits a dual XPath predicate
  (one per encoding, quote-injection guard unchanged) and the capture regex
  tolerates both; web recorder regenerated. Locked by
  `tests/unit/test_sid_and_spy.py`; JSON-fixture non-regression:
  `fiori_hybrid_smoke.robot` re-run green. 750→751 unit tests.

### Added — WebGUI smoke suite driven by the sid engine (2026-07-18)
- `tests/robot/webgui_smoke_sid.robot` — generated by the plan→generate agent
  cycle from `specs/webgui-smoke-sid.md` and validated live **4/4** vs A4H:
  ITS login through the dom engine's accessibility locators, transaction
  launch via the `~transaction` URL parameter (the OK-code field is hidden by
  default and the setting does not persist), the SE16 T000 entry count read
  end-to-end through sid locators (`wnd[1]/usr/txtG_DBCOUNT`), clean
  System-menu logoff. New WebGUI business keywords in
  `resources/fiori_keywords.resource` (`Open WebGui`, `Log In To WebGui`,
  `Go To WebGui Transaction`, `Count WebGui Table Entries`, `Log Off WebGui`…),
  pure Browser + SapFioriLibrary composition — no new Python. Prerequisite:
  the `webgui` ICF service must be active (activated once via SICF, itself
  driven live through rf-mcp perception→action).

## [0.5.8] — 2026-07-18

### Added — Accessibility locators for the dom and wc engines (2026-07-18)
- **`role=` on the dom engine is now the COMPUTED ARIA role**: the explicit
  `role` attribute still wins, but plain HTML semantics resolve too — a bare
  `<button>`, `a[href]` → `link`, `input[type=checkbox]` → `checkbox`,
  `h1`-`h6` → `heading`… (pragmatic HTML-AAM subset, case-insensitive). A
  React/Angular/vanilla widget no longer needs `role` attributes sprinkled in
  its markup to be addressable.
- **New `name=` selector key = the accessible name** (simplified accname in
  W3C precedence order: `aria-labelledby`, `aria-label`, the UI5 Web
  Components `accessible-name` attribute / `accessibleName` property,
  `label[for]`/wrapping label, `alt`, button `value`, visible text, `title`,
  `placeholder`), with the engines' usual matching rules (case-insensitive
  substring or `/regex/`). Available on BOTH the **dom** engine
  (`Resolve/Click/Fill Dom…` — user-intent locators, like Playwright's
  `getByRole(name=…)`: `role=button name=Fermer la notification`) and the
  **wc** engine (`Resolve/Click/Fill Wc…` — an icon-only `ui5-button` or an
  unlabelled `ui5-input` is addressed by what a screen reader would announce).
  Flows through `Resolve Ui5 With Fallback`'s `wc=`/`dom=` forms unchanged.
- Proven live offline: `fiori_wc_smoke.robot` 7/7 (accessible-name attribute
  AND non-reflected `accessibleName` property) and `fiori_hybrid_smoke.robot`
  6/6 (implicit `role=button` via `aria-label`, `role=textbox` named by its
  `label[for]`); web recorder regenerated (bundle embedded). 743→747 unit
  tests.

### Fixed — alignment pass: agents, MCP hints, recorder GUI (2026-07-18)
- The rf-mcp Fiori hints and the sap-healer agent now cite the FULL fallback
  chain (role → xpath → sid → wc → **dom**); the hints also cover the dom
  engine (computed `role=`, accessible `name=`), `Get Page Composition` and
  the nested-frame stack (`Push/Pop Ui5 Frame`). The planner/generator/healer
  agents mention `Get Page Composition` / `Get Fiori Diagnostics` at their
  perception steps; VS Code chat modes regenerated.
- The desktop recorder GUI (`tools/recorder/recorder_gui.py`) exposes the
  CLI's `--engine auto|native|poll` (capture/record) and `--semantic` (native
  record → human keywords) options, which had been CLI-only since 0.2.0/0.4.0.
  747→750 unit tests.

### Added — Fiori diagnostics layer (2026-07-18)
- **`Get Fiori Diagnostics`** (SapFioriLibrary): ONE JSON-safe dict aggregating
  the diagnostic bricks Browser 20 exposes separately, plus the project's own
  perception — the hybrid `composition` probe, the UI5 control tree
  (`ui5_tree`, probed for a short `tree_timeout` only, `None` when absent,
  never touching `Get Ui5 Page Tree`'s `mode=diff` state), normalized
  `console` / `page_errors` entries (Browser `Get Console Log` / `Get Page
  Errors` — incremental by default, matching the diff philosophy;
  `full_logs=True` re-reads everything; truncation to the `max_log_entries`
  most recent is always announced via `*_dropped`), and the ARIA snapshot of
  the non-SAP regions (`Get Aria Snapshot`, frame-scoped). Every section is
  best-effort (failures land in `collection_errors`, never abort the
  diagnostic), and the `issues` summary is actionable: first JS/console error
  quoted, missing UI5 tree names the recommended fallback engines and the
  iframes to scope into. Respects `Set Ui5 Frame` / `Push Ui5 Frame`.
- **`Log Fiori Diagnostics`** (SapFioriLibrary): same collection, rendered as
  a Markdown report into the Robot log (issues first) — teardown-friendly
  (`Run Keyword If Test Failed`). Returns the dict for follow-up assertions.
- **`sapfx_common/fiori_diagnostics.py`**: the pure, typed core (section
  validation, console/page-error normalization to stable JSON-safe shapes,
  announced truncation, issue synthesis, Markdown report) — Browser I/O stays
  in the keyword. rf-mcp Fiori guidance now points agents at the aggregate
  first when a screen misbehaves. 722→743 unit tests.

### Changed — RF 7.4 modernisation pass (2026-07-18)
- **`Input Password` accepts Robot Framework 7.4 `Secret` values**
  (SapEccLibrary override; the vendored keyword stays untouched — convention
  #4): the secret is unwrapped only at the COM boundary, plain strings behave
  exactly as before. Every password-accepting keyword of the three libraries
  now takes a `Secret`.
- **Launch examples document the typed-`Secret` syntax**
  (`-v "SAP_PASSWORD: Secret:..."`) across READMEs, docs (hardening §3,
  ecc-validation, deployment-pack) and every suite header — the value is
  masked everywhere, even at TRACE log level. The self-contained demo suites'
  password guards switched from `Should Not Be Empty` to `Should Not Be Equal
  ... ${EMPTY}` (a `Secret` has no measurable length).
- **Last deprecated `Force Tags` replaced by `Test Tags`**
  (`business_data_exploration.robot`) — RF 7.4 deprecation, RF 8 readiness.

## [0.5.7] — 2026-07-17

Hybrid-sessions release: both improvement axes land together — **Fiori hybrid
pages** (composition probe, generic DOM engine, nested-frame stack) and the
**ECC multi-session registry** (named aliases with STA/Secret/teardown safety
rails). Every new keyword was driven live step-by-step through rf-mcp on both
channels, then locked by a self-contained reproducible smoke replayed by the
real robot runner (`fiori_hybrid_smoke.robot` 5/5 offline,
`ecc_multisession_smoke.robot` 4/4 vs live A4H). 677→720 unit tests at 93%
coverage (CI ubuntu measurement — the canonical one; 94% locally on Windows
against the real pywin32).

### Added — Fiori hybrid sessions (2026-07-17)
- **`Get Page Composition`** (SapFioriLibrary): hybrid-page perception probe —
  reports which addressable technologies coexist in the current document
  (classic UI5 runtime / UI5 Web Components hosts / WebGUI `lsdata` elements /
  React-Angular-Vue hints), the recommended resolution engines per region (same
  order as the fallback chain), and every iframe with a reusable Browser
  selector plus its own probed composition (one level deep, best-effort — an
  unprobeable frame carries an `error` field instead of failing perception).
- **Generic DOM engine** (`Resolve/Click/Fill Dom …`, `Get Dom Text`,
  `Get Dom Match Count`, `Dom Element Should Be Visible`): the 5th resolution
  engine, for the NON-SAP regions of a hybrid page (React/Angular/vanilla
  widgets no SAP engine can see). CSS + text + ARIA role + attributes with the
  same matching rules as the role/wc engines; returns light-DOM CSS paths;
  new `dom=` last-resort form in `Resolve Ui5 With Fallback` (healing telemetry
  included, engine `dom`).
- **Frame stack** (`Push Ui5 Frame` / `Pop Ui5 Frame` / `Get Ui5 Frame Stack`):
  nested-iframe scoping for composite launchpads (Work Zone shell → app frame →
  embedded WebGUI frame), Browser `a >>> b` chaining. `Set Ui5 Frame` keeps its
  exact semantics (replaces the whole stack) — full backward compatibility.
- **`tests/robot/fiori_hybrid_smoke.robot`** + `fixtures/hybrid_fixture.html`
  (offline, 5/5): four technologies in one page, two REAL nested frame levels,
  composition probe, dom engine click/fill, stack push/pop, `dom=` fallback.

### Added — ECC multi-session registry (2026-07-17)
- **`keywords/_sessions.py`** (SapEccLibrary): named-session registry —
  `Open Sap Session` (second connection by string or Logon entry; optional
  standard `RSYST-*` login with a Robot `Secret` password never logged; alias
  rollback on failure), `Create Gui Session` (second window on the ACTIVE
  connection — scripted `/o`, no re-login hence no multi-logon popup: the
  recommended path for "write in one session, verify in the other"),
  `Switch Sap Session`, `List Sap Sessions` (JSON-safe, never a COM object),
  `Get Active Sap Session`, `Close Sap Session` (isolated teardown — never
  closes a connection still referenced by another alias) and
  `Close All Sap Sessions` (suite teardown).
- `session`/`connection` state is now routed per active alias (the historic
  single-session usage lives untouched under the `default` alias) with the
  **STA safety rail**: the owning COM thread is remembered per alias;
  cross-thread access gets a defensive `CoInitialize` (the marshalled mode the
  rf-mcp state providers rely on, live-validated) and
  `SAPFX_STRICT_COM_THREAD=1` upgrades it to an actionable error instead of
  COM's cryptic `RPC_E_WRONG_THREAD`.
- **Live-validated vs A4H (2026-07-17)**: the full cycle driven step-by-step
  through rf-mcp (`Open Sap Session` with integrated login, second window via
  `Create Gui Session` with no re-login, independent transactions per alias,
  JSON-safe `List Sap Sessions` across the MCP boundary, isolated
  `Close Sap Session` leaving the surviving session drivable), then replayed
  end-to-end by the real robot runner:
  **`tests/robot/ecc_multisession_smoke.robot` 4/4** (self-contained live
  smoke, shipped in the repo).

### Fixed
- `Sid Should Be Visible` (and the `sid=` form of `Resolve Ui5 With Fallback`)
  passed the element state as a *string* to Browser's internal Python API,
  which rejects it (`KeyError: 'visible'`) because Robot's argument conversion
  does not apply through `get_library_instance`. Both now go through
  `_wait_visible` (real `ElementState` enum + `timedelta` timeout). Caught live
  by the new hybrid smoke.

### Packaging
- Windows deployment pack rebuilt as `dist/sapfx-pack-0.5.7-win.zip` — the new
  keywords travel in the library wheel, pack manifest unchanged. Field note
  learned while validating through MCP (documented in CLAUDE.md): the rf-mcp
  server process freezes both the library class and instance — restart the
  server after changing library code under `src/`.

## [0.5.6] — 2026-07-17

Cross-channel release: the productization-hardening pass below is cut as 0.5.6,
together with three self-contained **demonstration campaigns** driven end-to-end
through rf-mcp then replayed by the real `robot` runner — one per channel. Unit
tests unchanged (677 at 93% coverage — the campaigns are `.robot` example suites,
outside the pytest scope).

### Added — cross-channel demonstration campaigns (2026-07-17)
- **`tests/robot/exploratory_campaign_a4h.robot`** (ECC, live A4H 4/4): delivery
  classes from DD07L/`CONTFLAG` (A/C/E/G/L/S/W), a reversible CRUD write cycle on
  SCARR (SE16 « Create Entries » from the INITIAL screen → read-back → Delete via
  Select All → Table Entry > Delete → « Delete Entry » → back to 0, no trace
  left), and a **dynamic TADIR catalog sweep** classifying every `TABL` object of
  the Flight (`SAPBC_DATAMODEL`) and EPM (`S_NWDEMO_MODEL_DDIC`) packages as a
  real table (counted) or a type-E structure.
- **`tests/robot/exploratory_campaign_fiori.robot`** (Fiori, visible browser,
  live 6/6): TrustArc cookie banner accepted by a stable DOM id
  (`truste-consent-button`), control-tree inventory, a reversible SearchField
  interaction, a **dynamic control-type sweep** (every discovered type converges
  role↔xpath), and the xpath locator grammar (hierarchy + `@controlType`
  predicate).
- **`tests/robot/cross_paradigm_api_visual.robot`** (API + GUI + visual, live
  3/3): the EPM product count agrees across OData `$count`
  (`SEPMRA_SHOP/Products`) and SE16 (`SNWD_PD`), product entity fields are read,
  and the SE16 screen is sealed by a perceptual-hash baseline
  (`Screen Should Match Baseline`, committed under `tests/robot/visual_baselines/`).
  `.gitignore` gains `!tests/robot/visual_baselines/*.png` (the `*.actual.png`
  drift diffs stay ignored).

### Changed — productization hardening (2026-07-17)
- All stateful libraries use Robot `SUITE` scope. Because rf-mcp 0.31 reuses one
  instance across synthetic tests, API stores and Fiori frame/perception state
  are additionally partitioned by `MCP_Test_<session_id>`. Live testing exposed
  the remaining ECC nested-resource limitation: one ECC session per process.
- Python support is aligned on 3.10+ for both distributions and CI now tests
  3.10/3.12; mypy also covers the ECC and Fiori public façades.
- Robot Framework 7.4 `Secret` values are accepted by IDP, OData Basic auth and
  RFC boundaries; cross-origin API URLs and redirects are blocked before an
  Authorization header can escape, and disabled TLS verification is warned.
- CI runs a real offline Browser/WC smoke and qualifies the downloadable ZIP by
  installing it outside the checkout with MCP + Chromium, generating Libdoc,
  dry-running packaged suites and replaying the smoke.
- The pack ships six examples plus qualified dependency constraints,
  `SHA256SUMS.txt` and a ZIP sidecar; CI emits a CycloneDX SBOM and GitHub build
  provenance.
- `comms/proofs.json` is checked against pytest collection and `coverage.xml`;
  current proof is 677 tests at 93% coverage. A weekly UI5 matrix keeps current
  and 1.136 LTS blocking while 2.x nightly remains informative.

## [0.5.5] — 2026-07-16

Packaging & distribution release: the Windows pack catches up with the July
security-hardening pass and the playwright-praman concept ports below — all
carried by the library wheel (pack rebuilt as `sapfx-pack-0.5.5-win.zip`,
manifest unchanged; the pack READMEs gain an « Environment preflights »
section). Unit tests 617 → 669.

### Added — release tooling (2026-07-16)
- **Comms version-sync guard** (`scripts/check_comms_sync.py`): any version
  cited in `comms/` (docs or deck sources) must equal `pyproject.toml`,
  otherwise exit 1. Deliberately version-only — the version acts as the
  tripwire that forces re-reading the proof numbers and regenerating the
  deck on every release. Born from a real incident (the comms base lived two
  releases behind with a stale test count and nothing flagged it).

### Added — security hardening pass (2026-07-15, from the July tech-watch)
- **Client-side security preflight** (`Get Client Security Status`,
  `Client Security Should Be Hardened`, pure logic in
  `sapfx_common.client_security`): classifies the SAP GUI client against the
  input-history weak-encryption vulnerability (CVE-2025-0055, SAP Note
  3472837 — fixed from 8.00 PL9, 8.10+ ships fixed) and detects leftover
  `SAPHistory*.db` input-history databases on the workstation (test runs type
  real data into real fields — that history must be disabled and purged on a
  test workstation). Read-only, locale-independent, MCP-safe dict.
- `Scripting Should Be Fully Enabled` now names the
  `sapgui/user_scripting_per_user` + S_SCR Execute(16) path (SAP's official
  mechanism to confine scripting to dedicated test accounts) when the server
  refuses scripting despite `user_scripting = TRUE`.
- **Hardening guide** `docs/hardening-test-environment.md` (+ `.fr.md`):
  the security checklist of a SAP test setup — RZ11 server posture, client
  patch level & input history, credentials in CI, MV3/CDP/WebView2 surface,
  MCP/agent containment, supply chain — each point mapped to the preflight
  keyword that verifies it.
- **UI5 1.136 legacy-free compat smoke** (`fiori_legacyfree_smoke.robot`,
  4/4 live): exercises the role/xpath engines against the official
  `1.136-legacy-free` CDN build — the LTS with ALL deprecated APIs removed,
  SAP's recommended 2.x-readiness vehicle while 2.0 has no GA date. Unlike
  the nightly smoke this target is stable: a failure is a real regression.
  Completes the compat triptych 1.60 ← 1.136-legacy-free → 2.0-nightly.
- **Strict-CSP injection smoke** (`fiori_csp_smoke.robot`, 3/3 live): a
  fixture whose CSP only allows the UI5 CDN + its own nonce (no
  unsafe-inline, no unsafe-eval) first proves the policy blocks a non-nonce
  `<script>`, then proves the `__SAPFX` bundle (Playwright evaluate → CDP,
  outside page-CSP reach) and the role/xpath engines still work — no CSP
  relaxation ever needs to be requested on a system under test.
- **Work Zone iframe fragility scenarios** (`fiori_frame_smoke.robot` 3→6
  tests, 6/6 live, new `shell_multi_iframe_fixture.html`): two apps in two
  frames (per-frame scoping never leaks), full frame reload (no stale
  context retained), frame navigation to another app (resolution follows
  the new content) — the exact bug class wdi5 had to fix twice in
  2025-11/2026-01. Harness lesson encoded in the suite: navigate the
  suite-level page (`Go To`), never `New Page` inside a test (Browser's
  TEST auto-closing reverts the active page between tests).

### Added — playwright-praman concept port (2026-07-15, Apache-2.0, NOTICE)
Four concepts identified by the competitive analysis, re-implemented from
scratch on this project's engines (never ported verbatim):
- **Business vocabulary** (`sapfx_common.vocabulary`, keyword
  `Lookup Business Term` on BOTH libraries): business terms — French and
  English, synonyms included — resolve to {canonical, ABAP field, table,
  domain} with tiered scoring (exact > synonym/field > prefix > fuzzy) and
  an ambiguity-refusal threshold: below-threshold or confusable candidates
  fail WITH the candidate list, never a silent first match. Ships MM/SD/FI +
  the Flight demo model; site terms extend via `extra`.
- **FLP intent navigation** (`Open Fiori App` + resource
  `Open App By Intent`, pure `build_intent_hash` helper): navigate the
  launchpad by `SemanticObject-action` hash — stable across catalog
  reorganizations, theme and language, unlike tile-title clicks (which
  remain as `Open App`, the "as the user does" path).
- **Enterprise IDP login** (`Log In Via Identity Provider`, presets in
  `sapfx_common.auth_flows`): drives SAP IAS / Azure AD / custom login forms,
  detecting single-page vs two-step flows dynamically; counts VISIBLE
  elements only (`>> visible=true` — a two-step form keeps its hidden
  password field in the DOM, presence-counting takes the wrong branch:
  caught live on the fixture); fails naming the blocking step; never logs
  the password. Live-validated 3/3 vs a two-step fake-IDP fixture
  (`fiori_auth_smoke.robot`).
- **LLM/DX surface**: root `llms.txt` (llmstxt.org format) and two bilingual
  migration guides — `docs/migrating-from-sapguilibrary.md` (drop-in rename
  from upstream) and `docs/migrating-from-cbta.md` (concept mapping +
  migration path before Solution Manager maintenance ends 2027-12-31).

### Pending
- **SAP GUI 8.10 validation** — GA is 2026-07-16 (the day of this entry):
  re-run the ECC smokes and the native-recorder `ISapSessionEvents` manual
  connection against 8.10 as soon as it is installed on the test workstation
  (the known-sensitive point). 8.00 leaves full support 2027-01-12
  (restricted until 2027-07-31); 8.10 is supported until 2029-06-30.

## [0.5.2] — 2026-07-14

The perception upgrade ships: every improvement below is carried by the
library wheel of the Windows deployment pack (rebuilt as
`sapfx-pack-0.5.2-win.zip` — same manifest as 0.5.0, refreshed content).
The drift sentinel's committable references now include the per-tile
fingerprint (`*.tiles.txt`) next to the signature and global hash;
pre-upgrade references stay readable (the tile channel is simply skipped).

### Added — perception upgrade (2026-07-14, live-validated vs A4H 5/5 + Demo Kit)
- **Element-scoped visual assertion** (`Get Element Perceptual Hash`,
  `Element Should Match Baseline`): the baseline is the PNG *cropped* to one
  element's screen region (the same reading as the coordinate effector), so
  the 64 hash bits cover the opaque GuiShell/chart alone instead of the whole
  screen — the direct answer to the dHash coarse-mesh limitation, and the
  assertion is immune to everything changing elsewhere on the screen.
- **Volatile-zone masking** (`mask_elements=auto|<ids>` on
  `Get Screen Perceptual Hash` / `Screen Should Match Baseline`): status and
  title bars (clock, localized title — the classic snapshot flakiness) are
  filled with neutral gray before hashing, identically on baseline and
  capture. Live-proven: the status-bar bit of the SE16 hash drops out.
- **Tiled fingerprints + drift localization** (`Get Screen Tile Hashes`;
  `sapfx_common.visual_hash` gains pure `crop_pixels`/`mask_regions`/
  `tiled_dhash`/`tiled_hamming`/`tile_rect`): the sentinel
  (`Check Screen Against Watch`) now records a per-tile grid next to the
  global hash and, on later passes, names WHICH tile drifted — position,
  pixel rectangle, and the elements covering it (smallest first). A local
  drift too diluted for the global hash is caught by its own tile; a baseline
  without tiles (pre-upgrade references) simply skips the channel.
- **Smart perception diff** (`pair_renames` on `diff_lines`/`diff_perception`
  and `Get Screen Signature mode=diff`; always on in the sentinel): within a
  changed block, removed/added lines whose ids score ≥ 0.6 on the healing
  similarity are paired into one `~ old -> new  (similarity N%)` line — a
  renumbered subscreen reads as a rename, same-id text changes read as value
  changes (`texte : 'a' -> 'b'`). Live: SE16→SE38 pairs
  `ctxtDATABROWSE-TABLENAME -> ctxtRS38M-PROGRAMM (62%)`.
- **Semantic perception** (`Get Screen Signature mode=semantic`,
  `sapfx_common.semantic.screen_affordances`): the *form view* of a screen —
  one line per actionable target carrying its **verified** human label
  (emitted only when it re-resolves to that single element, `?` otherwise),
  technical id, type and current value. Each line replays directly as
  `Fill Field By Label`/`Click Button By Label`. Live lesson locked in: the
  real SAP GUI marks `Changeable=True` on GuiUserArea and toolbar buttons —
  `is_editable_field` (type-aware) now guards affordances, annotations and
  `describe_element` alike.
- **Annotated screenshot — Set-of-Mark** (`Get Annotated Screenshot`,
  `Log Annotated Screenshot`): numbered boxes drawn on the window capture
  over every actionable target + a `number -> id` legend (dict, MCP-safe;
  HTML table inline in the Robot log). The missing link of the vision loop:
  an agent reads the number on the image and feeds the id to a deterministic
  keyword (`Click Element`, `Click Element At Offset`) instead of guessing
  coordinates. Negative widths reported by real SAP GUI are skipped.
- **Fiori visual-channel parity** (`Get Ui5 Perceptual Hash`,
  `Ui5 Screen Should Match Baseline`): same snapshot-baseline cycle as ECC
  over a Browser-library capture (`return_as=bytes` with file fallback), via
  the new shared `sapfx_common.visual_baseline` (baseline semantics + the
  Pillow decode boundary, one implementation for both channels). Live vs the
  OpenUI5 Demo Kit: create → re-verify distance 0.

### Pending
- **SAP GUI 8.10 validation** — GA is 2026-07-16 (after this entry): re-run the
  ECC smokes and the native-recorder `ISapSessionEvents` manual connection
  against 8.10 as soon as it ships (the known-sensitive point).

## [0.5.0] — 2026-07-13

The API channel and the maintenance loop: a third, screen-free channel
(`SapApiLibrary`, OData v2/v4 + optional RFC) next to the two GUI ones, drift
detection without scripted tests (sentinel + visual assertions), and the
telemetry-to-patch bot that turns healing logs into reviewed `resources/`
fixes. The Windows deployment pack ships all of it (see *Deployment pack*
below). Also repairs a version drift the 0.3.0 guard missed:
`SapFioriLibrary.__version__` (class attribute) had stayed at 0.2.5 — the
guard now tracks every library class attribute, `SapApiLibrary` included.

### Added
- **Deployment pack refreshed for the new channels**
  (`scripts/build_release_pack.py` + `packaging/`): the library wheel now also
  carries `SapApiLibrary` (and the installer's import smoke check verifies it);
  two new sample suites join the pack — `ecc_drift_sentinel.robot` (the watch
  harness: perceive → compare → Markdown drift report, no test to write) and
  `flagship_cross_paradigm.robot` (the same business fact asserted through the
  screen AND the API); the maintenance tooling ships under `scripts/`
  (`healing_drift_report.py`, `check_spec_sync.py` — both stdlib-only, run
  from the pack root); `requirements-deploy.txt` adds Pillow (visual
  fingerprints of the sentinel and `Screen Should Match Baseline`) and
  documents the optional `pyrfc` prerequisite.
- **Drift sentinel — change detection WITHOUT tests**
  (`sapfx_common.screen_watch` + `Check Screen Against Watch` +
  `tests/robot/ecc_drift_sentinel.robot`): watched screens are remembered
  (structured perception + optional visual fingerprint) and every later pass
  reports ONLY what moved, line by line — a nightly watch surfaces a support
  pack's drift screen by screen before any scripted test fails. Report-only by
  default (`FAIL_ON_DRIFT` opt-in), baselines are committable, extending the
  watch = adding a tcode to a list. Live-validated on A4H: full
  baseline→unchanged→drifted cycle, the simulated drift named (`txtI1-LOW`
  block appearing under the SE16 watch key).
- **The spec is the source of truth** (`scripts/check_spec_sync.py`):
  generated suites carry a provenance marker
  (`Spec: specs/<plan>.md (sha256:<12hex>)`, stamped via `--stamp` — now a
  step of sap-generator's contract); the guard fails when a spec changed
  since generation (stale suite → re-run `/sap-generate`, never hand-edit),
  or when a marker points to a vanished spec; plans without a suite are
  informational. `ecc_scarr_spfli_liaisons.robot` stamped against its spec.
- **Coordinate effector — act where the API is blind**
  (`PointerKeywords`): `Get Element Screen Region` (real screen geometry —
  the perception half an agent crosses with `Get Screenshot As Base64`) and
  `Click Element At Offset` (hardware win32 click at a RELATIVE position
  inside an element — left/right/double, best-effort foreground, logged
  point). The deterministic-first/hardware-last-resort hybrid for opaque
  GuiShell interiors, record-only charts and drag & drop targets.
  Live-validated on A4H: a coordinate click on the count button opened the
  real "Number of Entries" popup.
- **"The SAP MCP" positioning** (docs/mcp-integration + publication-ready
  metadata for `sap-robotmcp`): the guarantees no public alternative makes
  (real perception never optimistic, never silent, MCP-safe returns, tested
  like a product), a generic-MCP-client quickstart, and the market window
  named (CBTA EOL 2027 without successor). Publishing to an index stays a
  deliberate, separate decision.
- **`SapApiLibrary` — the API channel** (third channel next to the GUI desktop
  and web ones, stdlib-only): OData v2 (embedded Gateway) and v4 (CAP/S4) with
  one keyword set (`Open Api Session`, `Get Odata Entities`, `Get Odata
  Count`, `Post Odata` with the SAP CSRF protocol), optional RFC through
  `pyrfc` (`Open Rfc Connection`/`Call Rfc` — helpful error when absent).
  Auto-correctable HTTP errors (status, URL, body excerpt). Rationale: robust
  SAP tests prepare/cross-check data through the API and drive the screen only
  for what they actually test.
- **Cross-paradigm flagship suite** (`tests/robot/flagship_cross_paradigm.robot`)
  — the architecture demo: the same business fact asserted through two
  independent channels. The `a4h` leg is **live-validated**: the SE16 "Number
  of Entries" of `SNWD_PD` equals the `$count` of the Gateway
  `SEPMRA_SHOP/Products` service of the same system. The `capsflight` leg
  (first rendered Travel row exists through an OData v4 point query) is
  dryrun-validated only for now: the local `_cap-sflight` clone currently
  wedges on startup (cds-dk 9.9 + cds-plugin-ui5 0.17 hang at UI5 app mount;
  without the plugin the CAP server accepts TCP but never answers) — an
  environment regression of the sample clone, to re-validate after refreshing
  it (`fiori_sflight_smoke.robot` is equally affected today).
- **Visual assertions** (`sapfx_common.visual_hash` + perception keywords):
  `Get Screen Perceptual Hash` (dHash over `HardCopyToMemory`, Pillow at the
  decode boundary only — new optional extra `visual`) and `Screen Should Match
  Baseline` (snapshot semantics: first run creates the baseline, then Hamming
  distance vs threshold, `.actual.png` saved next to the baseline on drift,
  auto-correctable failure). Covers exactly what the Scripting API cannot see
  (opaque GuiShell lists, record-only charts). Live-validated on A4H (real
  PNG round-trip; SE16 vs SM50 hashes measurably distant).
- **Healing-drift maintenance bot** (`scripts/healing_drift_report.py`): reads
  the cumulative `SAPFX_HEALING_LOG` JSONL, separates *stable* drifts (same
  locator healed N times to one target — patch in `resources/` located and
  proposed, `--apply` executes) from *unstable* ones (human/sap-healer
  review), exit code 1 as a CI alert signal. Never touches tests, never
  silent. First CLI run on the real repo located `${SE16_COUNT_BUTTON}` and
  proposed the exact 0.3.0 blind-healer scenario patch.
- **Coverage-discovery mode for sap-planner** (agent definitions + regenerated
  chat modes): usage-driven scoping through ST03N's transaction profile
  (perceive→act, grid keywords), honest fallback for fresh trials without
  collector history, ranked `specs/couverture-proposee.md` roadmap.

- **Embedded-browser-control bridge (ECC)** — new `EmbeddedBrowserKeywords`
  mixin: `Enable Embedded Browser Debugging` (sets
  `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` before `Open Sap Logon`/the SAP
  client starts), `Get Embedded Browser Page Id` and `Switch To Embedded
  Browser Page` (locate/activate, via the Browser library over CDP, the page
  hosted by a WebView2 control embedded in a SAP GUI/Business Client window).
  Workflow documented by RoboSAPiens (imbus, Apache-2.0 — see `NOTICE`); reuses
  the same `BuiltIn().get_library_instance("Browser")` access pattern as
  `SapFioriLibrary`.
- **Enriched human-locator grammar (ECC)** — `sapfx_common.semantic` gains
  grid/position addressing (`N @ Label` / `Label @ N`: the Nth field of a
  vertical/horizontal grid below/right of a label) and the scoped-anchor
  operator (`Anchor >> Rest`: narrows resolution to the neighborhood of a
  unique label, recursively resolving `Rest` with any grammar form — including
  a nested `>>`). Covers RoboSAPiens' "non-unique label near a unique anchor"
  and "unlabelled field identified by its tooltip near a unique anchor" cases,
  reimplemented as neighborhood scoping rather than ported verbatim (see
  `NOTICE`). `Find Element By Label` and friends document the extended
  grammar. 519 unit tests (was 483).
- **Scope reach is an intent, not a tolerance** — the `>>` neighborhood radius
  (default 100 px, unchanged) is now a parameter: `scope_radius` on
  `resolve_semantic` and on all four `… By Label` keywords (alignment
  tolerances stay deliberately unexposed — they are rendering noise, the scope
  radius is what the author *means* by "near"). Nested `>>` inherits the
  radius; scopes intersect. When a `>>` locator fails, the error now embeds a
  scope diagnosis (`scope_hint`, pure and unit-tested): anchor unknown,
  anchor ambiguous, anchor without geometry, or target beyond the radius —
  naming the radius used and the remedy. Validated live on A4H:
  `MTEXT >> = 200` fails at 100 px with the diagnosis, resolves
  `txtMAX_SEL` at `scope_radius=500` across the real SE16 screen.

### Changed
- **`Read Field By Label` resolves changeable fields first** (cascade, same
  "first step that matches wins" principle as the grammar): grid positions now
  count the same fields as `Find`/`Fill` (`MTEXT @ 2` = the HIGH bound for all
  three — live-validated round-trip Fill→Read with one locator), while
  read-only fields remain readable as the fallback — the way display dynpros
  render their values. Ambiguity within the winning pass is still raised,
  never resolved silently.

### Fixed
- **`SapFioriLibrary.__version__` (class attribute) had drifted to 0.2.5** —
  the exact 0.3.0 scenario again, on the other library: the version guard
  (`tests/unit/test_version_consistency.py`) only tracked `SapEccLibrary`'s
  class attribute. It now tracks the class attribute of every library
  (`SapEccLibrary`, `SapFioriLibrary`, `SapApiLibrary`) alongside the
  `__init__` and the two `pyproject.toml`.
- **`Fill Field By Label` could target a read-only field** (found while
  validating the grid grammar live on a real SE16/T000 selection screen): the
  explicit input-type filter re-admitted non-changeable text fields — the
  screen's "to" separators — as grid positions, so `MTEXT @ 2` resolved to the
  separator for Fill (raw COM `AttributeError`) while resolving to the HIGH
  bound for Find. `resolve_semantic` gains `changeable_only` (targets only,
  never anchors); `Fill Field By Label` enables it, making Find and Fill count
  the same grid positions. Read follows through the changeable-first cascade
  (see *Changed*), keeping read-only fields readable as the fallback.

## [0.4.0] — 2026-07-13

Human locators, perception fast path and the semantic recorder — the outcome of
the comparative review of [RoboSAPiens](https://github.com/imbus/robotframework-robosapiens)
(imbus, Apache-2.0; techniques ported with attribution, see `NOTICE`) and
sapient-mcp (ideas only — no license). Both distributions and all package
`__version__` attributes move to 0.4.0.

### Added
- **Human locators (ECC)** — new `SemanticKeywords` mixin: `Find Element By
  Label`, `Fill Field By Label`, `Read Field By Label`, `Click Button By Label`
  target controls by **visible label + geometric proximity** (grammar:
  `Label`, `@ Label` = below, `Left @ Top` = intersection, `= content`;
  `exact=False` = case-insensitive prefix, tooltip-shortcut friendly). Pure
  resolution engine in `sapfx_common.semantic`. Deliberate difference from
  RoboSAPiens: **ambiguity is reported with the candidate list, never resolved
  silently to the first match**; zero-match errors list the labels actually on
  screen (self-correcting errors). Ids remain the nominal path in `resources/`.
- **`GetObjectTree` perception fast path** — `sapfx_common.object_tree`
  flattens the Scripting API's JSON subtree (one COM round-trip instead of one
  per control, geometry included); `Get Screen Signature`, healing candidates
  and the semantic engine all ride it, with automatic fallback to the
  historical COM walk (AttributeError = API absent, remembered; com_error =
  transient, retried). `Get Screen Signature` gains `include_geometry=True`
  (optional 4th column, 3-column default contract unchanged).
- **Label-anchored healing** — `Resolve Element With Healing` accepts
  `label=<visible label>`: when id-similarity stays below the threshold, a
  label that uniquely re-resolves repairs the locator (WARNING + telemetry
  `engine=label`). A visible label survives the subscreen renumbering that
  kills ids.
- **In-memory screenshots (ECC)** — `Get Screenshot As Base64`
  (`HardCopyToMemory`, MIME re-checked by magic bytes, MCP-safe string) and
  `Log Screenshot` (data-URI inline in the Robot log — self-contained
  log.html). rf-mcp guidance updated; `get_application_state` now reports the
  **live** transaction and connection state (read from the real session, never
  an optimistic state machine).
- **Semantic recorder (`--semantic`, native engine)** — each recorded step is
  rewritten as a human keyword (`Fill Field By Label    Table Name    T000`)
  when the label computed at event time **provably re-resolves** to the same
  element (`sapfx_common.semantic.describe_element`; a changeable field's text
  is its volatile value and is never used as a locator); the technical id
  stays as a trailing comment. Known vkeys get readable comments (`# F8`);
  `--screenshots` prefers `HardCopyToMemory` (faithful window image, extension
  from magic bytes) over the GDI fallback.
- **ALV row addressing by content** — `Get Cell Value By Row Content` (the
  `content @ column` idea applied to grids: no row index in tests) and
  **`Read Abap List`** — classic list output read by geometric row
  reconstruction (`sapfx_common.abap_list`).
- **Client-side preflight** — `Get List Rendering Status` and `Abap List
  Should Be Readable` (`_diagnostics.py`): the client-side counterpart of the
  server-side scripting preflight. Live-checked on A4H / SAP GUI 8.00: modern
  list screens (RSPARAM output) render inside an opaque `GuiShell` exposing
  **zero labels** unless SAP GUI **accessibility mode** is on, so
  `Read Abap List` cannot reconstruct anything. That mode **cannot be flipped
  from a test** (verified: `SAP_ACCESSIBILITY=1` has no effect; it is a
  per-Windows-user client option requiring a GUI restart) — so, exactly like
  RZ11 server-side, it is **provisioned** and merely **observed**: the
  preflight reports `accessibility_mode_needed` and names the option to enable.
  A shell *with* labels (a legitimate ALV screen) is correctly reported as
  needing nothing.
- **Agents updated** — planner records visible labels next to fields,
  generator probes locators with `Find Element By Label`, healer uses label
  anchors; VS Code chat modes regenerated. `docs/architecture.md` documents
  the new layers plus an exploration note: driving SAP GUI's embedded
  **WebView2** panes via Browser/CDP (bridge between both channels; revisit
  after SAP GUI 8.10 GA).

### Fixed
- **`SapEccLibrary.__version__` class attribute** had silently stayed at 0.2.5
  through the 0.3.0 release — the version-consistency guard only covered the
  package `__init__` files. The class attribute is now tracked by
  `tests/unit/test_version_consistency.py` too.
- rf-mcp ECC signature filtering now tolerates the optional geometry column
  (4-column lines) instead of skipping filtering on them.

## [0.3.0] — 2026-07-12

Both distributions (`robotframework-sapecclibrary`, `sap-robotmcp`) move to
0.3.0, and — for the first time actually enforced — so do ALL three package
`__version__` attributes (`SapEccLibrary`, `SapFioriLibrary`, `sapfx_common`);
see the version-drift fix below. The MV3 extension stays at 0.4.1 (unchanged).

### Added
- **SAP test agents (plan → generate → heal)** — transposition of the
  [Playwright Test Agents](https://playwright.dev/docs/test-agents) principle
  to this ecosystem, on top of rf-mcp: `sap-planner` (explores the live system
  through the perception→action loop and writes a business-readable plan under
  `specs/`), `sap-generator` (turns a plan into a suite under `tests/robot/`,
  executing every step live before writing it; missing business keywords land
  in the resources layer, never raw ids in tests) and `sap-healer` (reproduces
  a failure, reads the scored closest-match suggestions and the
  `SAPFX_HEALING_LOG` telemetry, verifies the fix live, then patches
  `resources/` — not the tests — never silently). Canonical definitions in
  `.claude/agents/` + `/sap-plan`, `/sap-generate`, `/sap-heal` commands for
  Claude Code; VS Code / Copilot **chat modes generated** from that single
  source by `scripts/regen_agent_definitions.py` (`--check` drift guard wired
  into pytest). `specs/` holds the plans (French, deliberately
  single-language — `check_bilingual_docs.py` gains prefix exemptions) with a
  reference example matching the live-validated SFLIGHT/SE16 flow. Bilingual
  walkthrough: `docs/test-agents.md`.
- **Deployment pack: the agents ship with the pack** — `.claude/agents`,
  `.claude/commands`, `.github/chatmodes` and `specs/` (contract + example)
  join the manifest; a second MCP template (`vscode-mcp.json.template`) and
  `install.ps1 -WithMcp` now render the IDE configs **in place** (`.mcp.json`
  for Claude Code, `.vscode/mcp.json` for Copilot agent mode,
  `mcp.generated.json` for external projects), making the unzipped pack an
  agent-ready VS Code workspace. Pack-specific rule encoded in the agent
  definitions: new keywords / locator overrides go to
  `resources/site_keywords.resource` only, so a pack update never overwrites
  local work.
- `check_guidance_sync.py` now also guards the agent definitions: every
  `.claude/agents/sap-*.md` must keep carrying the convention markers
  (locators in the resources layer, no fixed waits, message-*type* assertions).
- **Full agent cycle validated live against A4H (3/3)**: sap-planner explored
  SE16 through a real rf-mcp session (perceive→act, scripting preflight) and
  produced `specs/scarr-spfli-liaisons-se16.md` — 18 carriers / 14 connections
  observed, selection screens surveyed field by field; sap-generator turned it
  into `tests/robot/ecc_scarr_spfli_liaisons.robot` (7 scenarios, relational
  assertions, **7/7 live** — independently re-run), probing every locator live
  before writing it; sap-healer, blind-tested against a simulated screen drift
  (`btn[31]` → `btn[13]` in the resource), reproduced the 4 failures, diagnosed
  through live perception (toolbar signature naming « Number of Entries ») plus
  the scored closest matches (`Get Closest Element Ids`), patched the single
  resource line — zero test edits — and re-ran to **7/7**.
- **ECC filtered-selection keywords** (`resources/ecc_keywords.resource`,
  written by the generator, locators verified live first): `Display Table
  Contents With Filter` (named criteria resolved through per-table
  `&{<TABLE>_SELECTION_FIELDS}` dictionaries — SCARR I1–I4 and SPFLI I1–I15
  mapped with their exact `ctxt`/`txt` element types), `Count Flight
  Connections For Airline`, `Displayed Grid Should Contain Columns`
  (technical column ids, never localized titles) and `Read Column Values From
  Displayed Grid` (ordered list or sorted unique set).
- **Version-consistency guard** (`tests/unit/test_version_consistency.py`):
  both `pyproject.toml` files and the three package `__version__` attributes
  must carry one identical version, and `CHANGELOG.md` must have a dated
  section for it — the suite now fails on any future release drift.

### Fixed
- **`install.ps1`: latent em-dash parse bomb.** The installer is UTF-8 without
  BOM but Windows PowerShell 5.1 reads it as ANSI; the em dash in the import
  smoke-check string mojibakes to `â€”`, whose `”` is treated by PowerShell as
  a closing quote — silently unbalancing every string literal after it. All
  typographic characters are now banned from the file (rule documented in its
  header) and the string uses an ASCII dash.
- **Library version drift**: the 0.2.0 and 0.2.5 entries below claimed
  `__version__` bumps that never actually landed — `SapEccLibrary` and
  `sapfx_common` were still at 0.1.0 while `SapFioriLibrary` had run ahead to
  0.3.0. All normalized to 0.3.0; the new version-consistency guard turns any
  recurrence into a red unit suite.

## [0.2.5] — 2026-07-12

Both distributions (`robotframework-sapecclibrary`, `sap-robotmcp`) and both
library `__version__` attributes move to 0.2.5; the MV3 extension moves to
0.4.1 (regenerated recorder embedding the Web Components capture).

### Added
- **Web Components engine — third Fiori resolution engine** (`Resolve Wc
  Control`, `Click Wc Control`, `Fill Wc Input`, `Get Wc Text`, `Wc Control
  Should Be Visible`, `Get Wc Match Count`). Pages built on **UI5 Web
  Components** (SuccessFactors home, ui5-webcomponents apps) have NO classic
  UI5 runtime: the element registry is empty and the role/xpath engines are
  blind there. The new engine scans light-DOM custom elements (`ui5-*`
  prefix), matches short types (`tag=Button`) against plain AND **scoped**
  tags (`ui5-button-<suffix>`), attributes/properties (same case-insensitive
  substring + bounded `/regex/` matcher as the role engine — now shared as
  `valueMatches`), `text`, `id`/`idSuffix`, and returns CSS light-DOM paths
  anchored at the closest id (WC hosts often have no id of their own).
  Playwright's shadow-piercing CSS handles the click/fill through the open
  shadow roots. `Resolve Ui5 With Fallback` gains `wc=` as the last link of
  the chain (role → xpath → sid → wc); the web recorder captures/records WC
  hosts (`Click Wc Control`, Alt+click assertions, fill) on registry-less
  pages, with matching hover highlight. Validated live against a local
  offline fixture (`fiori_wc_smoke.robot`, 6/6, includes a genuine scoped
  tag and shadow-DOM piercing) — no SAP, no network.
- **Healing telemetry** (`sapfx_common.healing_telemetry`, typed): opt-in
  cumulative JSONL journal of locator repairs (`SAPFX_HEALING_LOG=<path>`),
  fed by BOTH channels — ECC `Resolve Element With Healing` (with score) and
  Fiori `Resolve Ui5 With Fallback` (with the healing engine). Reading it
  across runs shows which locators drift recurrently, turning healing into a
  preventive-maintenance tool for `resources/`. Best-effort by contract:
  never fails a test, never records typed values.
- **Strict rf-mcp session isolation (opt-in)**: with
  `SAPFX_MCP_STRICT_SESSION=1`, the ECC state provider now REFUSES to serve
  perception for a second concurrent rf-mcp session (first-come,
  first-served, explicit error naming both sessions and the variable)
  instead of only logging the cross-session sharing warning — the documented
  "one live ECC session per rf-mcp process" rule becomes enforceable.
- **Deployment pack: self-contained data-exploration sample**
  (`tests/robot/business_data_exploration.robot`): the SE16 exploration
  campaign (domain catalogs, dynamic TADIR inventory, per-table "Number of
  Entries" verification) as a single standalone suite with zero dependency
  on `resources/` — deliberately deviating from convention #1 so the pack
  ships a real-data example runnable without the repo. Included as the third
  sample suite by `build_release_pack.py`.
- **Project logo** (`assets/logo.png`, 512 px master with transparent circular
  cutout) applied across every user-facing surface: README banners (EN/FR), the
  desktop recorder's Tkinter window icon (`tools/recorder/assets/icon.png`,
  best-effort `iconphoto`), and the MV3 extension (toolbar icons 16/48/128 +
  popup header — the 16 px icon crops to the robot face for legibility).
  `gen_icons.py` now derives all icon sizes from the committed master (Pillow,
  dev-only dependency) instead of drawing a generic magnifier.

### Changed
- **CI**: the Windows job now also runs the unit suite against the REAL
  pywin32 before the Robot dry run — `tests/unit/conftest.py`'s stubs only
  install when the authentic modules are missing, so this catches any drift
  between the COM fakes and reality (the ubuntu job keeps the coverage gate).
- rf-mcp guidance: fallback hint extended to the wc engine; new hint routing
  agents to `Resolve/Click/Fill Wc …` on registry-less Web Components pages;
  `SapFioriPlugin` keyword map and capabilities updated accordingly.

## [0.2.0] — 2026-07-12

First tagged release. Both distributions (`robotframework-sapecclibrary`,
`sap-robotmcp`) and both library `__version__` attributes move to 0.2.0; the
MV3 extension moves to 0.4.0 (its store versioning was already ahead).

### Added
- **Desktop recorder: native event engine** (`--engine auto|native|poll`).
  `--record` now uses the Scripting API's own Record mode (`GuiSession.Record`
  plus `Change` events — the mechanism behind ALT+F12): SAP GUI itself emits the
  exact command (`SP` set-property / `M` method call) before each server
  roundtrip, so button presses, ALV grid/tree/tab/context-menu interactions
  and the exact submit action are captured (the polling engine inferred
  `Send Vkey 0`). OK-code + Enter collapses into a single `Run Transaction`;
  passwords are never recorded; unmapped calls are kept as exact-call comments
  (never lost). `--capture` gains the API's hit-test mode
  (`elementVisualizationMode` + `Hit` events, plus `FocusChanged`) — true
  click-to-capture including non-focusable elements. Automatic fallback to the
  polling engine when the server profile disables recording events
  (`ScriptingModeRecordingDisabled`) or COM event binding fails; `--screenshots`
  keeps preferring the polling engine (roundtrip-boundary concept).
  **Event binding does NOT use `DispatchWithEvents`**: makepy generation
  crashes on the sapfewse typelib (pywin32 issue #2433, reproduced on
  pywin32 311 / SAP GUI 8.00). `advise_session_events()` connects to the
  `ISapSessionEvents` connection point manually, with the canonical
  `_query_interface_` hack from pywin32's own `win32com/demos/connect.py`.
  **Validated live against the A4H**: scripted AND manual interactions both
  emit `Change` events; an end-to-end `--record --engine native` session
  transcribed `Run Transaction /nse16` (OK-code+Enter fused), `Input Text …
  T000`, and the exact `Click Element wnd[0]/tbar[1]/btn[8]` (F8) — the case
  the polling engine could never capture.
- **Scripting preflight (ECC)**: `Get Scripting Status` and `Scripting Should
  Be Fully Enabled` read the API's real state (`GuiConnection.DisabledByServer`,
  `ScriptingModeReadOnly`, `ScriptingModeRecordingDisabled`, `UI_GUIDELINE`,
  GUI version) and fail EARLY with the exact RZ11 parameter to fix — these
  server profile modes otherwise degrade automation silently. Plus
  `Enable Test Tool Mode` (suppresses I/A message popups at replay, immediate
  update mode — designed by SAP for test tools) and `Get Session Telemetry`
  (ResponseTime/InterpretationTime/RoundTrips/Flushes per roundtrip).
- **Locator self-healing (unified ECC ↔ Fiori)**: new `sapfx_common.healing`
  (typed, pure) scores SAP GUI ids by terminal-field-name (heavy weight) +
  character-level path LCS + control type — a renumbered subscreen
  (`SAPLMEGUI:0013` → `:0015`) stays above the healing threshold. ECC:
  `Resolve Element With Healing` (repairs with a logged WARNING, never
  silently; returns a plain string — MCP-safe) and `Get Closest Element Ids`;
  `Wait Until Element Present` failures now list the closest ids on screen
  (self-correcting errors, UiPath "closest matches" / MCP SEP-1303 pattern).
  Fiori: `Resolve Ui5 With Fallback` (role → xpath → sid chain, per-engine
  timeout, healed engine logged) and no-match errors now say whether the
  controlType is rendered at all (properties drift vs. wrong screen).
- **Diff-mode perception**: `Get Screen Signature` and `Get Ui5 Page Tree`
  accept `mode=diff` and then return only what changed since the
  previous perception (`-`/`+` lines, unchanged summarized) via the shared
  `sapfx_common.perception_diff` — the screen is always re-read (never a state
  cache); only the rendering differs. Guidance hints updated so rf-mcp agents
  prefer diff after an action.
- **Work Zone / cFLP iframe support (Fiori)**: `Set Ui5 Frame <selector>`
  scopes all resolution to the app iframe — the JS bundle now runs inside the
  frame's context (two-arg `build_call` form: Browser's `Evaluate JavaScript`
  with a selector executes in the element's frame) and every returned selector
  is prefixed with `<frame> >>>` (Playwright frame piercing, crosses origins).
  Validated live by the new `tests/robot/fiori_frame_smoke.robot` (3/3) against
  `fixtures/shell_iframe_fixture.html` — a UI5-less shell embedding the app in
  a genuinely cross-origin iframe (file:// origin "null"), the Work Zone
  structure. The MV3 extension now injects the recorder into **all frames**
  (`allFrames: true`; panel titles get an `[iframe]` tag).
- **Fiori Elements V4 stable-id support**: new `idSuffix` selector key —
  matches the END of the control id, the documented FE pattern
  (`fe::table::<Entity>::LineItem::Table`; the app/route prefix varies, the
  suffix doesn't). The web recorder's capture now recognizes FE ids and emits
  `idSuffix=fe::…` selectors instead of the "dynamic id, likely fragile"
  fallback.
- **UI5 2.x readiness, proven live**: new `tests/robot/fiori_ui5v2_smoke.robot`
  (4/4 live) runs SapFioriLibrary against the **OpenUI5 2.0 nightly** CDN build
  (`fixtures/ui5_v2_fixture.html`) — proves the `ElementRegistry`-module branch
  of `registryForEach` and that no library path depends on a removed legacy API
  (`sap.ui.getCore()` façade, `Element.registry`, `sap.ui.version` global).
  Symmetric counterpart of `fiori_legacy_smoke.robot` (1.60) — the library now
  has live coverage at both ends of the UI5 spectrum.
- **Web recorder value assertions**: Shift+Alt+click records a
  `Ui5 Text Should Be` step with the control's current text (new library
  keyword, exact compare after trim); Alt+click stays the visibility assertion.
- rf-mcp plugins: keyword routing maps + guidance updated for all of the above
  (preflight in Suite Setup, diff-mode perception, healing keywords,
  `Set Ui5 Frame` for launchpads, `idSuffix` for FE apps).
- 276→362 tests (native record engine state machine, healing scoring,
  preflight, diff perception, frame scoping, fallback chain, FE idSuffix).

### Changed
- The injected JS bundle's entry form is now `(first, second) =>` (dual-form
  call: page-level or frame-scoped) — regenerate custom snippets with
  `python -m SapFioriLibrary.regen_recorder`.
- `SapEccLibrary.__version__`/`SapFioriLibrary.__version__` aligned to the
  distribution version (0.2.0).
- Documentation refreshed for 0.2.0 across the bilingual set (root README,
  `docs/architecture`, `docs/fiori-architecture`, `docs/mcp-integration`,
  `docs/sap-test-data` §5, both recorder READMEs, extension, packaging,
  rf-mcp plugin READMEs) — including the previously stale `tools/spy*` paths and
  the pre-0.2.0 ECC mixin list. Deployment pack rebuilt as
  `dist/sapfx-pack-0.2.0-win.zip`.

### Live validation (A4H Docker, 2026-07-12)
- ECC smokes re-run: `ecc_smoke.robot` 5/5, `ecc_data_smoke.robot` 4/4,
  `ecc_record_smoke.robot` 1/1, plus the native-events end-to-end `--record`
  session described above.

### Known gaps (tracked)
- SAP GUI **8.10** (GA 2026-07-16) validation pending — the stack is currently
  validated on 8.00; the Scripting API is unchanged per SAP's announcements,
  re-run the ECC smokes once 8.10 is installed.

### Added (2026-07 hardening line, previously unreleased)

- **Windows deployment pack**: `scripts/build_release_pack.py` + `packaging/`
  produce `dist/sapfx-pack-<version>-win.zip`, a self-contained pack for a target
  Windows PC (no repo clone): the two wheels (`robotframework-sapecclibrary` =
  `SapEccLibrary`/`SapFioriLibrary`/`sapfx_common`; `sap-robotmcp` = the rf-mcp
  plugins, entry points intact), `resources/`, both recorders (desktop + web
  snippet + MV3 extension), two sample smoke suites, bilingual pack README, and
  `install.cmd`/`install.ps1` (local `.venv`, pinned `pywin32==311`, `-WithMcp`
  renders `mcp.generated.json`, `-WithBrowsers` runs `rfbrowser init chromium`).
  Assembler logic unit-tested off-SAP (`tests/unit/test_build_release_pack.py`).
  End-to-end walkthrough (build → transfer → install → validate → MCP) in
  `docs/deployment-pack.md` / `.fr.md`.
- **CI**: `.github/workflows/ci.yml` (ruff + mypy + `pytest --cov`, 85% gate, on
  ubuntu using the off-SAP `conftest.py` stubs, plus `robot --dryrun` over all of
  `tests/robot/` on a Windows runner) and `.github/workflows/vendor-drift.yml`
  (weekly, clones the real upstream and checks it against the vendored file).
- `scripts/`: `check_bilingual_docs.py` (EN/FR doc pairing + drift-since-ref),
  `check_vendor_drift.py` (vendored file vs. upstream, tolerating only the
  documented class-rename diff), `check_guidance_sync.py` (rf-mcp guidance
  hints vs. CLAUDE.md conventions) — consistency guards, not generators.
- Progressive `mypy` typing (`sapfx_common`, `SapFioriLibrary/_ui5_runtime.py`,
  the rf-mcp perception modules) — scope in `[tool.mypy]` (`pyproject.toml`).
- `sapfx_common.com_safety.ensure_com_initialized()`: the defensive
  `CoInitialize` call previously duplicated in `ConnectionKeywords
  .connect_to_session` and the rf-mcp `run_keyword_in_context`, now shared.
- `poll_interval` constructor argument on both `SapEccLibrary` and
  `SapFioriLibrary` (was hard-coded 0.1s / 0.25s in several places).
- Desktop recorder: `--screenshots` (best-effort GDI bitmap capture of the
  arrival screen at each `--record` boundary, referenced by a `# screenshot:`
  comment in the output); `--hover`'s `element_at` now restricted to each
  session's *active* window instead of every residual window in the session
  tree; `record_loop` now does a single merged COM walk per poll cycle
  (`scan_active_window`) instead of two.
- rf-mcp state providers: perception **compaction** (`_last_seen.py` —
  byte-identical consecutive `get_page_source` calls return a compact marker
  instead of the full text) and a real **`filtered`/`filtering_level`**
  implementation (`_filtering.py`, minimal/standard/aggressive, mirroring the
  real Browser provider's progression; ancestor-preserving prune for the UI5
  tree) — both were part of rf-mcp's `LibraryStateProvider` contract but
  previously accepted and silently ignored.
- **SE16 exploration keywords + campaign suite, validated live** (agent-driven
  discovery through rf-mcp on the A4H): `Count Table Entries` (« Number of
  Entries », btn 31 / `G_DBCOUNT` — reliable on empty tables), `Read Domain
  Values` (DD07L), `List Repository Tables` (TADIR), `Try/Open Table Selection
  Screen` (handles the > 40-fields field-choice dialog dynamically; classifies
  structures via status type `E`). New `tests/robot/ecc_exploration.robot`
  (6/6 live vs A4H Docker): locks the delivery-class catalog (A/C/E/G/L/S/W)
  and table-class catalog (TRANSP/INTTAB/VIEW/APPEND — POOL/CLUSTER gone on
  S/4), inventories the flight (27) and EPM (114) TADIR objects and
  deep-verifies each one through SE16; sweeps tagged `deep`.
- `sapfx_common` package: shared `poll_until` / `retry_call` / `retry_until`
  synchronisation primitives used by both `SapEccLibrary` and `SapFioriLibrary`
  (previously three near-identical inline implementations).
- **Data-driven smokes, validated live**: `tests/robot/ecc_data_smoke.robot`
  (4/4 vs A4H Docker — SFLIGHT/SPFLI/EPM through SE16 ALV grid, technical column
  ids only) and `tests/robot/fiori_sflight_smoke.robot` (2/2 vs local cap-sflight).
- SE16/SE38 business keywords: `Display Table Contents`, `Read Displayed Grid`,
  `Run Report`, `Use ALV Grid In Data Browser` (A4H's SE16 default output is a
  classic list with no scriptable grid; SE16N does not exist on A4H).
- `resources/a4h_demo_data.resource`: `Ensure Flight/EPM Demo Data Exists`
  conditional generators (SAPBC_DATA_GENERATOR, SEPM_DG).
- `robot.toml` (`python-path`) — RobotCode IDE and CLI resolve libraries identically.
- **MCP server config committed**: `.vscode/mcp.json` (VS Code/Copilot agent mode)
  and `.mcp.json` (Claude Code) both launch `robotmcp --transport stdio
  --without-frontend` with the project PYTHONPATH — stdio handshake verified.
  Plus `.vscode/settings.json` (Pylance paths, pytest) and `extensions.json`;
  `.gitignore` now whitelists these three `.vscode` files.
- **rf-mcp plugins hardened**: routing maps now cover the full public keyword
  surface of both libraries (the historical `Fill Sid` typo — real keyword is
  `Fill Sid Input` — is fixed and now caught by an anti-drift test that checks
  every routed keyword against the real library class); guidance enriched with
  the SE16 classic-list/ALV pitfall, technical-column-id assertions, perception
  workflow and A4H demo-data guards; stale "À AJOUTER" docstrings removed.
  Re-validated e2e live: Fiori 8/8, ECC 9/9 (A4H Docker).
- Chrome extension **0.3.0**: rebuilt with the multi-version recorder
  (registryForEach fallback); `PUBLISHING` docs updated.
- **UI5 multi-version support**: `registryForEach` fallback chain in the injected
  bundle (`ElementRegistry` module for UI5 2.x → `Element.registry` for 1.67+ →
  `[data-sap-ui]` DOM scan for < 1.67) and `Wait For UI5 Ready` no longer requires
  `sap.ui.getCore()`. Validated live against a real OpenUI5 1.60.14 runtime
  (`tests/robot/fiori_legacy_smoke.robot`, jsDelivr npm mirror) with zero regression
  on current UI5; locked by `tests/unit/test_ui5_compat.py`. Compatibility matrix
  in `docs/sap-test-data.md` §5.
- Fiori mirror aliases in `resources/fiori_keywords.resource`: `Open SAP And Log In`,
  `Close SAP`, `Popup Is Present`, `Confirm Popup`, `Cancel Popup` — plus an
  ECC ↔ Fiori keyword mapping table in the resource documentation.
- Unit tests for previously uncovered keywords: `Open Sap Logon`, `Close Sap Logon`,
  `Open Connection By String`, `Get Cell Value By Column Title`, the WebGUI `sid`
  wrappers, `regen_recorder`, and the new `sapfx_common.polling` module.
- Tooling: ruff configuration (`pyproject.toml`), `.pre-commit-config.yaml`,
  `.editorconfig`, `[tool.pytest.ini_options]` (no more manual `PYTHONPATH=src`).
- AI-assistant supports: `AGENTS.md`, `.github/copilot-instructions.md`
  (kept in sync with `CLAUDE.md` — convention 7).
- `docs/sap-test-data.md` (+ `.fr.md`): verified SAP demo data sets (SFLIGHT, EPM,
  `/DMO/FLIGHT`), public Fiori test targets, cap-sflight local target, platform watch.
- `py.typed` markers for both libraries; `SapFioriLibrary` also declared in
  `package-data`.
- French twin for `integrations/robotmcp/README` (bilingual convention).

### Fixed (hardening line)
- rf-mcp state providers: a COM thread-affinity gap (`run_keyword_in_context`
  now calls `ensure_com_initialized()` too, not just `connect_to_session`),
  and failures surfaced a generic "keyword absent?" instead of the real cause.
- `Get Screen Signature`'s tree walk (`_perception.py`) could raise on a stale
  COM node instead of skipping it.
- The Fiori resolution/page-tree polling loops could be aborted by a single
  transient JS exception; `_act_with_retry` was effectively count-bounded
  (~0.75s) rather than actually bounded by `ui5_timeout` as documented.
- `captureSid`'s BFS used `break` instead of `continue` for the help-button
  skip, aborting SID discovery early instead of skipping one branch.
- `run_transaction` mishandled namespaced tcodes (e.g. `/BEV1/RCA01`): the
  `/n` navigation prefix wasn't added because the tcode itself starts with `/`.
- Desktop recorder: the GUI launcher spawned its child via `pythonw.exe` (no
  stdio at all, even in a new console) instead of `python.exe`; a path-traversal
  gap in `resolve_save_path`; `get_scripting_engine` let a raw `com_error`
  escape instead of the friendly CLI error path.
- `Count Entries On Current Selection Screen`'s thousands-separator regex
  (`\D`) was silently defanged by Robot Framework's own backslash escaping —
  replaced with a backslash-free digit filter, found and locked in by a test
  that executes the real Robot-parsed expression rather than a hand-copy.
- `List Repository Tables` now fails loudly instead of silently returning a
  possibly-truncated inventory when the result count hits `max_hits` exactly.
- Raw SAP ids remaining in `ecc_smoke.robot`/`ecc_record_smoke.robot` moved to
  `resources/ecc_keywords.resource` (convention 1).

### Changed (hardening line)
- `run_transaction` failure message is now English (error-message language is
  English across all keywords; docstrings/comments stay French).
- `pywin32` exactly pinned in `requirements.txt` (`==311`); floor kept in
  `pyproject.toml` (convention 6 clarified).
- `pyproject.toml` `Homepage` now points to this repository (was upstream).
- `SapFioriLibrary.__init__.__version__` aligned to `0.3.0` (was `0.1.0`).
- READMEs (EN/FR) refreshed: recorders, MV3 extension, WebGUI `sid` engine,
  screen perception, rf-mcp integration; quick-start example now respects
  convention 1 (no raw SAP ids in test cases).

## [0.1.0] — initial development line
- Phase 1 `SapEccLibrary` (vendored upstream + mixins) and phase 2 `SapFioriLibrary`
  (UI5 role/XPath engines, WebGUI sid), business resources, recorders (desktop +
  web/MV3 extension), rf-mcp plugins, bilingual docs. See `CLAUDE.md` status list.
