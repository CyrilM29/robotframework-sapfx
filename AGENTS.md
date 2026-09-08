# AGENTS.md

## Agent contract v1 (2026-09-06)

Five roles include read-only `sap-verifier` (`/sap-verify`). Read
`.claude/agent-contract.md` first: common method from rf-test-agents, SAP checks
here. It supersedes historical healer skip/spec-edit/unbounded-replay guidance.
Healer outcomes: `repaired_verified`, `application_defect`, `blocked`,
`needs_human`, `not_verified`; procedural budget 2 candidates / 20 calls / 900s.
The PreToolUse hook in `.claude/settings.json` serves Claude Code and Copilot:
readers preserve base permissions, other calls ask (`RF_AGENT_READ_ONLY=1`
denies). Host loading still needs qualification. Handoff hashes/facts and
recovery milestones live in scripts/agent_contract.py and agent_journal.py;
no automatic retry or measured LLM quality follows from their offline tests.
Regenerate canonical `.claude/agents/` into four legacy chatmodes plus
`.github/agents/sap-verifier.agent.md`. The pack ships the scripts/contract
and minimal hook settings, never the workstation's permissions.

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
  `Pick F4 Value` for search helps, and since 2026-09-07 the lot that closed
  the SAP GUI capability register: trees (`Read Tree Nodes`, `Select Tree
  Node By Text`/`By Path`, opaque keys kept as is), combo boxes by technical
  key (`Select Combo Box Entry By Key`), the user's date/decimal formats
  (`Get User Formats`, `Input Date`, `Input Number`), the F4 calendar
  (`Pick Calendar Date`), grid actions (`Double Click Grid Cell`, context
  menu by function code, `Sort Grid By Column`), the menu bar by path
  (`Select Menu Item`), checkboxes/radios by their own text and modal windows
  (`Dismiss Modal Window`); the perception shows `GuiShell/<SubType>`, refuses
  to serve a ProgID as a value and FAILS naming the cause when the session is
  unreadable; the same evening added the system identity read on screen
  (`Get System Identity`: System > Status opened BY POSITION and verified,
  SAP_BASIS release and kernel, since two lab systems share a SID and a host)
  and the standard SE16 list (`Use Standard List In Data Browser`, a classic
  ABAP list rendered as labels and read by `Read Abap List`); the 2023 register
  (2026-09-08) added the message identity (`Get Status Message Identity`,
  `MO/E/402`, `Status Message Should Be`), tab strips by technical key
  (`Select Tab`, `Get Selected Tab`, `List Tabs`), the application toolbar
  inventory (`List Toolbar Buttons`, `Click Application Toolbar Button`), the
  resolved "Status..." entry (second-to-last, dialog required: the hard-coded
  index clicked "Log Off" on 758) and control resolvers that read the shell
  SubType (a column tree is no longer taken for an ALV)), DDIC inventory
  (`Classify Ddic Objects`:
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
  which the resource layer and the campaigns delegate to, plus the two SE16
  SCREEN primitives promoted from `resources/` in 2026-08-29 (convention #12):
  `Use ALV Grid In Data Browser`, the remedy this library's own failure
  messages prescribe, and `Count Entries On Current Selection Screen`, which
  is reliable on an empty table where F8 yields no grid;
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
  bars, and `per_resolution=True` for one baseline per capture geometry: a
  perceptual hash encodes the geometry as much as the content) plus their
  element-scoped variants `Get Element Perceptual Hash`/
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
  watched screens remembered (structured + visual + per-tile fingerprints,
  the visual ones per capture geometry under `per_resolution=True` while the
  structural signature stays shared),
  later passes report only what moved: smart diff (renames paired), global
  hash, and tile localization naming WHERE the visual drift is, change
  detection without scripted tests), and a **multi-session registry**,
  `Open Sap Session` (second connection, optional `RSYST-*` login with a
  never-logged `Secret` password), `Create Gui Session` (second window on
  the active connection, no re-login so no multi-logon popup),
  `Switch/List/Close/Close All Sap Sessions`: session/connection state is
  routed per active alias (historic usage = the `default` alias), with the
  STA safety rail (owning COM thread remembered per alias; since 2026-09-07 a
  cross-thread access RE-ATTACHES the session on that thread, scripting engine
  re-acquired from the ROT then `FindById` of the session id, one proxy cached
  per thread: a defensive CoInitialize never marshalled anything and rf-mcp's
  `execute_batch`/`Evaluate` were getting EMPTY perceptions in PASS; perception
  keywords now fail naming the cause when the session is unreadable, and
  `SAPFX_STRICT_COM_THREAD=1` still turns any cross-thread access into an
  actionable error). Multi-session is cooperative MULTIPLEXING (one active
  session, explicit switch), never thread parallelism; closing an alias
  never closes a connection another alias still uses.
- **`SapFioriLibrary`** (`src/SapFioriLibrary/`): SAP Fiori/UI5 web automation on
  top of the Browser library (Playwright). Injects a JS bundle (`_ui5_js.py`,
  `window.__SAPFX`) with a **role** engine (incl. `idSuffix` for stable Fiori
  Elements ids `fe::…`), a **UI5 XPath** engine
  (`//Table//Button[@text='Edit']`), and a **wc** engine (`Resolve/Click/Fill
  Wc…`) scanning `ui5-*` custom elements in the light DOM **and in every open
  shadow root** for UI5 Web Components pages WITHOUT a classic UI5 runtime
  (short types match scoped tags `ui5-button-<suffix>` and every glue/dash
  spelling of compound names, `ui5-shellbar-item` included; a shadow boundary
  becomes a DESCENDANT combinator in the returned path, the form Playwright's
  CSS pierces for click/fill), plus a
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
  (convention #3 on the web); `Get Ui5 Property` / `Get Ui5 Properties` read a
  control PROPERTY from the registry, which `Get Ui5 Text` cannot replace: text
  is what the browser DISPLAYS, so it needs visibility and returns everything
  the control draws (a list item with a counter reads `"Accessories\n34"` where
  its `title` is `"Accessories"`, and a control inside a collapsed
  FlexibleColumnLayout column has no readable text at all);
  `Get Ui5 Control Info` / `Get Ui5 Aggregation Info` read the FULL metadata
  type, the binding context (the technical key of items whose id is
  generated) and aggregation children rendered OR NOT (a closed Select's
  items exist in no engine's DOM), with `property_keys` announcing every
  property read (an array-valued one no longer vanishes silently);
  `Get Ui5 Control Metadata` reads the DECLARED contract (types, defaults,
  borrowed provenance, inheritance chain), the doc-vs-living-control read; the promoted pure probes cover launchpad
  services (`Get Flp User`, `List Flp Apps/Catalogs/Groups`,
  `Get Flp Intent Support`, `Flp Service Is Available`), WebGUI presence and
  menus (`Webgui Is Present`, `Get Webgui Element Count`,
  `List Webgui Menus/Menu Items`), `List Page Iframes`,
  `Get Page Languages`, `Get Session Cookie Summary` (never a value; the
  1969 session-cookie sentinel is not a future expiration),
  `Get Ui5 Theme` (`{requested, applied}`: they diverge while the runtime
  swaps its stylesheets, so a theme is waited for, never read once) and
  `Ui5 Runtime Is Ready`; `Get Ui5 Ids`
  returns WHICH controls matched (the reading you need when the documented
  anchor is an id SUFFIX; `containedIn=` narrows any role-engine selector to
  the DOM content of another control, where `viewId` follows the ownership
  property); `Get Ui5 Open Popups` is the Fiori counterpart of ECC's
  `Get Open Windows` (a closed dialog stays RENDERED, only
  `sap.m.InstanceManager` tells open from closed) and
  `Click Ui5 Dialog Button` acknowledges by button POSITION (MessageBox
  buttons carry generated ids and translated text, and the right position
  varies by release: measure it, do not hardcode it);
  `Upload File Via Ui5` targets the control's
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
  `Wait Until Api Available`; `Classify Http Response` is its tolerant
  counterpart, sorting a raw response structurally: three families of 404
  hide under one status, and a 2xx with an HTML body is not data; behind an
  API-management layer a 401 splits too, `backend_auth_failed` meaning the
  layer ACCEPTED the API key and the SAP system behind refused, so the key
  must not be regenerated),
  `Build Draft Entity Path` (the COMPOSITE key of a draft-enabled v4
  service), OAuth2 client-credentials + mTLS auth,
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
  boundary used by BOTH channels' visual keywords, optional extra `visual`,
  including the per-geometry baselines behind `per_resolution=True`).
  New wait/retry loops go here, never inline; their deadlines run on
  `time.monotonic()`, never on the wall clock. Typed (`mypy`).
- **Security configuration posture, one campaign per target.**
  `tests/robot/api/secu_configuration_a4h.robot` (live 12/12) and
  `secu_configuration_abap2023.robot` (live 13/13), both replayed green,
  read a system's hardening through the RFC channel, READ-ONLY. Vocabulary in
  `resources/security_keywords.resource` (parameter lots by theme, admin table
  names, control factory), capability in `SapApiLibrary._rfc_security` plus
  pure logic in `sapfx_common/security_baseline.py`. Two suites rather than
  one parameterized, because the releases are not hardened alike (measured:
  minimum password length 6 vs 10, the four composition requirements 0 vs 1,
  automatic logout off vs one hour, remote program start REMOTE_SHELL vs
  DISABLED): a single suite would have had to assert either the weaker posture
  (blind on the better target) or the stronger one (red forever on the other).
  Only controls whose deviation is an incident under ANY policy are asserted
  (audit log active, gateway under ACL, RFC authority check armed, hard-coded
  SAP* neutralized, reference client write-protected); everything else is
  measured, reported, and watched by a **drift sentinel** against a committed
  per-target reference, so the question is not « is this system hardened »
  (arguable, red forever on a sandbox) but « has its configuration moved »
  (binary). Central trap encoded: `TH_GET_PARAMETER` does NOT refuse an unknown
  parameter, it returns `RC=4` and an EMPTY string, and it is CASE SENSITIVE,
  so a control written on a misspelled or upper-cased name is green and claims
  a lack of hardening it never measured. The reading judges the return code
  before the value, and `not_measurable` stays distinct from `deviation` and is
  never a success.
- **Business keywords** live in `resources/` (`ecc_keywords.resource`,
  `fiori_keywords.resource`, `api_keywords.resource`, `rfc_keywords.resource`:
  one mirrored vocabulary
  across the four channels, same-name aliases, and the OData service paths,
  function-module names, BAPI names and table names carried under business
  names so no suite spells one out;
  `a4h_demo_data.resource` for demo-data guards). The API channel has its own
  suite, `tests/robot/api/canal_api_odata.robot`, running the same business
  keywords against OData v2 (tag `a4h`) and OData v4 (tag `capsflight`): it
  was previously exercised only through the two cross-paradigm suites, and
  that blind spot is where two real defects had been sitting. The **RFC/BAPI
  channel** got the same treatment on 2026-08-27 with
  `tests/robot/api/canal_rfc_a4h.robot` (spec `specs/canal-rfc-a4h.md`, live
  16/16), and the same blind spot paid out again: the first live run felled
  two boundary defects, chief among them `pyrfc` rejecting a `DotDict` (every
  dictionary Robot builds), which meant no suite could pass a structure to a
  function module at all. It is read-only, cross-checks `SNWD_PD` counted over
  RFC against the OData `$count` of the same system, exercises all five
  outcomes of a background-job wait on jobs the target already carries
  (targets DISCOVERED, never graven: a branch with no candidate skips saying
  so), and is **neutral by
  default**: tag `rfc` plus a clean skip wherever the optional channel is
  absent (`pyrfc` has no wheel past Python 3.12), because a suite that goes
  red where nothing is broken ends up disabled. A **second RFC campaign**,
  `tests/robot/api/canal_rfc_abap2023.robot` (spec
  `specs/canal-rfc-abap2023.md`, live 10/10 on 2026-08-28), looks at the same
  channel across TWO ABAP releases, since the first suite already passes on the
  newer target by overriding variables: portability is settled and is not the
  subject. What one release hides: the system carries **two airline catalogues
  of different populations** (18 classic, 16 in the modern travel model, the
  smaller strictly included), so a crossing that mixes them fabricates a
  reproducible two-row gap; identity is proved by RELEASE, kernel and the
  `CVERS` software components, never by the system id or the application host
  name (identical on both containers) nor by the IP address (measured
  volatile); two logon refusals return the same code AND the same text word for
  word, so the test asserts the INDISTINCTION; and the dispatcher port is
  DERIVED from the instance number, which turns the local TCP relay from a
  story into a measurement. It also adds refusal assertions by **ABAP message
  identifier** (`Rfc Should Fail With Message Id`, class/type/number, finer
  than the code and just as language independent) and a deterministic
  **channel-surface artifact** (`sapfx_common/rfc_surface.py`) that carries its
  target's identity and its scope, so two artifacts of different scopes are
  refused as inconclusive rather than averaged. The **cross-channel
  campaign** `tests/robot/cross/croisement_ddic_odata.robot` (spec
  `specs/croisement-ddic-odata-ecc-s4hana.md`, live 9/9) generalises the
  flagship's single hardcoded pair into a discovery-driven, bounded, read-only
  campaign reusable on ECC and S/4HANA: existence of every declared entity set,
  volume (`$count` against the SE16 count of the mapped table), and field
  contract (`$metadata` against DD03L). Its vocabulary and the **entity set to
  table mapping** live in `resources/cross_channel_keywords.resource`, its pure
  logic in `sapfx_common/cross_channel.py`, imported as a Robot library so a
  pure primitive is reached by a keyword, never by `Evaluate __import__(...)`.
  Two rules it encodes, both paid live: a table's NAME proves no mapping
  (`SNWD_CONTACT` is a healthy empty table that a naming convention would have
  paired with a 41-row entity set), and a `sap:` annotation being PRESENT does
  not make it PERMISSIVE (`sap:creatable="false"` is declared and forbids), so
  the write-candidate guard reads per entity set and verb by verb. Its
  read-only sibling is `tests/robot/cross/simulation_ecriture_lecture.robot`
  (spec `specs/simulation-ecriture-lecture-cross-canal.md`, live 8/8), the
  campaign that actually WRITES: write through the screen, observe through the
  API, delete, prove the initial state came back. It produces the dated
  reversibility observation the crossing campaign leaves at `unknown`, and it
  is **opt-in twice over** (tag `write` AND `-v WRITE_SIMULATION_OPT_IN:yes`,
  otherwise every test skips itself, including inside a full `tests/robot/`
  run). Its SE16 write screens live in the page object
  `resources/page_objects/se16_table_entry.resource` and its pure logic in
  `sapfx_common/write_simulation.py`, whose write-target allowlist is the
  choke point every writing keyword goes through (an EMPTY allowlist refuses
  everything, it never allows everything). Two facts it paid for live: a
  screen write is refused by the DICTIONARY, not by authorisations (the eleven
  `/DMO/*` RAP tables carry an empty `MAINFLAG`, so SE16 answers type `E` for
  any user), and safety cannot rest on a menu index, since mass delete sits
  one notch from selective delete: the filtered grid is re-read and the
  keyword stops without deleting whenever the selection is not exactly the
  targeted row.
  **Recorders** in `tools/recorder`
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
   **Hot swapping the library inside a running server also needs the PAGE to
   let go**: the injected `__SAPFX` bundle is versioned by its content and its
   guard reads « present AND same version », so a new build replaces the old
   one at the next keyword call instead of being ignored for the life of the
   page (the old guard produced `window.__SAPFX.<x> is not a function` on
   keywords that were visible on the Robot side). Reinstalling neither doubles
   nor drops the hooks placed at injection time (fetch/XHR counting,
   MessageToast capture): the state lives on the window and each wrapper is
   marked. Already-parsed RESOURCES, however, stay frozen for the process.
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
  `check_conventions.py`, the mechanical guard for conventions #1/#2/#12: raw
  locators (SAP GUI ids, UI5 addresses, CSS/XPath) in a **generated** suite,
  `Sleep` anywhere, and (since 2026-08-29) convention #12's detectable motif:
  `Evaluate JavaScript`/`Wait For Function`/`__import__` blocking in
  `resources/` (exact-count `ALLOWED_12` allowlist for the few assumed
  probes) and in generated suites, `modules=` blocked in suites; hand-written
  library-validation suites are reported
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
  the four definitions also require querying the **optional `qa-brain` MCP
  RAG** (shared QA memory: keywords, specs, lessons written after real
  incidents) BEFORE their judgement calls (which anchor holds, which layer a
  keyword belongs to, which failure class, which risk), live observation
  still deciding and an absent server never blocking;
  the planner additionally adopts a **business persona** before exploring
  (domain fiches in the private root `PERSONAS.md`: truth source, risks to
  cover first, reigning assertion, reversibility; on a deployed pack the file
  is absent and the agent derives the same grid, marked (SAP général)), and
  every plan carries a « Perception métier » section;
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
   and build provenance. `install-rfc.ps1` provisions the OPTIONAL RFC channel
   (SAP NW RFC SDK unpacked, `SAPNWRFC_HOME` + `PATH`, pinned `pyrfc`, real
   import check, `-CheckOnly` diagnosis): everything except obtaining the
   licensed archive, which no script may download or redistribute. Its refusal
   branches are exercised by CI on a runner that has no SDK. Measured
   2026-08-27: a workstation carrying **SAP GUI for Windows 8.00** often needs
   no archive at all, its « SAP NWRFC x64 Shared » component having already put
   `sapnwrfc.dll` and the `icu*50` libraries in `System32`, so `pyrfc` loads and
   a real call goes through without `SAPNWRFC_HOME` or a `PATH` entry, which is
   what `-UseSapGuiRuntime` provisions (no archive, no variable, binding plus a
   real import check) and what `-CheckOnly` now reports instead of calling the
   SDK missing. That shortcut does NOT lift the 3.10 to 3.12 interpreter
   constraint, and it is true of one workstation only: the SDK stays the target
   for anything that must run elsewhere.

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
   **What `resources/` ships are EXAMPLES, not a universal SAP truth**: the
   business vocabulary of ONE installation, measured live on this repo's lab
   targets. Much of it travels (standard screens and services, the mirrored
   naming), none of it is authoritative: it is to be verified on the target and
   adapted to the business domain (`resources/README.md`, and the
   « EXEMPLE À PERSONNALISER » banner every `.resource` opens with). What holds
   on every SAP system is `src/`, the libraries and their capabilities: the same
   boundary as convention #12, seen from the user's side.
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
11. **No credential ever gets a committed default value**: passwords, API keys
   and tokens come in through the command line (`-v "NAME: Secret:…"`) or the
   environment; in `resources/`, `tests/robot/` and `variables/` such a variable
   keeps `${EMPTY}`. Enforced by `tests/unit/test_no_hardcoded_credentials.py`.
12. **A capability gap found on a live target is closed IN the shipped
   library.** A library keyword that misbehaves gets FIXED in `src/`, never
   routed around in a suite, a page object or a resource; a missing one gets
   CREATED in `src/Sap*Library` (pure logic in `sapfx_common`), never as inline
   JS in a page object nor an `Evaluate` in a suite; a workaround already
   written in an intermediate layer is PROMOTED into the library as soon as it
   is recognised as a capability. The boundary: libraries carry CAPABILITIES
   (perception, resolution, waiting, engines, state, protocols), `resources/`
   carries the BUSINESS VOCABULARY of one site. Why: the libraries are what
   ships to PyPI, so a fix left in a resource helps nobody else and gets
   re-improvised in the next project. This is also the one place where
   « Observe, do not fix » does not apply: the system under test is observed,
   but our own library is the work in progress. Each such keyword still owes
   its off-SAP unit test (#5), its rf-mcp intent-map entry, its Libdoc page and
   its CHANGELOG line. On a deployed pack (no `src/`), the workaround goes to
   `resources/site_keywords.resource` AND the defect is reported upstream.
   Promoting also changes more than the caller in front of you: a promoted
   probe can quietly change SCOPE (`Evaluate JavaScript` with a `${None}`
   selector evaluates on the page whatever the frame stack, a library keyword
   honours it), and the empty result that follows is plausible enough to send
   the diagnosis elsewhere. Establish what the old probe evaluated ON, then
   check the new one from EVERY caller.
13. **No code file grows past 500 lines.** A file over the line is a file doing
   several jobs: split it along a seam the repo already uses (one mixin per
   capability under `keywords/`, pure logic into `sapfx_common`, one module per
   concern), never by cutting at line 500 to satisfy the number. **In scope**:
   everything a machine executes, whatever the language (Python, JavaScript
   including the injected `*.js.tpl` bundles, PowerShell, batch, and the unit
   tests) under `src/`, `integrations/`, `tools/`, `scripts/`, `packaging/`,
   `tests/unit/`. **Out of scope**: HTML/CSS pages and graphical supports,
   GENERATED artefacts (the
   limit applies to their generator: `recorder_snippet.js` and
   `extension/recorder.js` come from `regen_recorder.py`), Markdown and docs,
   Robot suites and `.resource` files (their length follows the scenarios and
   the screen they name), and `_vendor/` (convention #4 forbids splitting it).
   The 23 files above the limit on 2026-08-25 were split the same day (debt
   settled); enforced mechanically by `scripts/check_file_length.py` (CI +
   `PostToolUse` hook + unit test), whose exact-count `ALLOWED` map is the
   only escape hatch and is empty.

## License

Apache 2.0. Preserve the attributions in `NOTICE` (upstream sapguilibrary,
playwright-sap ports in `_ui5_js.py`, RoboSAPiens human-locator techniques in
`sapfx_common/semantic.py`).
