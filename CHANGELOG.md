# Changelog

Notable changes to this project. Format inspired by [Keep a Changelog](https://keepachangelog.com/);
versions refer to the `robotframework-sapfx` distribution (`pyproject.toml`;
named `robotframework-sapecclibrary` up to 0.6.3: entries below keep the
name that was current at the time).

## [Unreleased]

### Fixed
- **Demo Kit target drift absorbed: the public OpenUI5 Demo Kit shell moved
  to UI5 Web Components** between 2026-08-25 (last green ui5-compat CI run)
  and 2026-09-01, with SDK 1.151.0 -> 1.152.0 and no repository commit in
  between. Measured live via rf-mcp: 68 WC hosts where the plan recorded 0,
  the global search replaced by a `ShellBarSearch` wrapper (the classic
  `sap.m.SearchField` child is gone), Options-menu entries now WC `MenuItem`
  wrappers without a `key` property (the technical key moved into the stable
  `menuItem-<key>` id suffix), and the popup stack now counting WC
  implementation layers (open menu = 2 entries, cascade = 3). Repairs, all
  role/xpath-engine based (nothing re-routed through CSS):
  - `tests/robot/fiori_smoke.robot` now opens the API Reference (`#/api`),
    where the classic `sap.m.SearchField` still lives, UNIQUE; not one
    locator changed. Re-validated live 7/7.
  - `specs/openui5-demokit-navigation-interaction.md` re-explored (PERIMEE
    marker lifted the same day it was set), observed-data sections and
    scenarios 1/3/9 rewritten on the day's measurements.
  - `resources/page_objects/openui5_demokit.resource`: search scoped to the
    stable `searchControl` id (suggestions are registry `SearchItem` controls
    read by their `text` property, contained in the SEARCH CONTROL, not in
    the shadow-rooted WC popover), menu entries clicked by `menuItem-<key>`
    id suffix, keys derived from id suffixes with subset assertions (the WC
    menu keeps every nested entry in the DOM, closed submenu included), menu
    stack cost carried by an explicit variable. Campaign re-validated live
    12/12 headless. The composition sentinel that caught the drift
    (`68 != 0`) now asserts the hybrid shell in the other direction
    (`wc_hosts > 0`).

## [0.8.0] - 2026-08-30

### Added
- **Security configuration posture, and a campaign per target.** New
  `sapfx_common/security_baseline.py` (pure: reading classification, control
  verdicts, drift comparison, deterministic artifact hashed excluding the
  timestamp, Markdown report) plus the `_rfc_security.py` mixin on
  `SapApiLibrary`: `Read Profile Parameters`, `Profile Parameters Should Be
  Defined`, `Read Standard Users Status`, `Build/Write/Read Security Posture`
  and `Security Posture Should Not Have Drifted`. Business vocabulary in
  `resources/security_keywords.resource` (parameter lots by theme, admin
  table names, control factory), and two live-validated read-only suites,
  `tests/robot/api/secu_configuration_a4h.robot` (15/15) and
  `secu_configuration_abap2023.robot` (16/16), replayed green.
  The reason there are two suites rather than one parameterized: the releases
  are not hardened alike (measured 2026-08-29: minimum password length 6 vs
  10, the four composition requirements 0 vs 1, automatic logout off vs one
  hour), so a single suite would have had to assert either the weaker posture
  (blind on the better target) or the stronger one (red forever on the other).
  What the suites ASSERT is limited to controls whose deviation is an incident
  under any policy (audit log active, gateway under ACL, RFC authority check
  armed, hard-coded SAP\* neutralized, reference client write-protected); the
  rest is measured, reported, and watched by the sentinel rather than turned
  into a permanent red.
  Trap encoded, paid live: `TH_GET_PARAMETER` does NOT refuse an unknown
  parameter, it returns `RC=4` and an EMPTY string, so a control written on a
  misspelled name is green and claims a lack of hardening it never measured.
  The reading judges the return code before the value, `not_measurable` stays
  distinct from `deviation` and is never a success, and a numeric comparator
  fed a non-numeric value raises naming the control instead of inventing a
  verdict. Second trap, found while proving the sentinel can fail: a committed
  reference edited on Windows carries a UTF-8 BOM, so the artifact is read as
  `utf-8-sig` and the sentinel no longer reds out on `Unexpected UTF-8 BOM`
  instead of comparing.
  Two further inventories whose raw reading misleads, each closed by its own
  keyword (`sapfx_common/security_inventory.py`): `Get Audit Configuration`,
  because `rsau/enable` answers « armed » and that is true and insufficient
  (measured on both releases: ten filtering slots DECLARED, none active, so
  the log records nothing an auditor believes it records, hence the
  `armed_without_filter` verdict kept distinct from `filtering`); and
  `Read Rfc Destination Inventory`, because a destination storing a logon to
  another system is an elevation path and that fact lives in an aggregate of
  single-letter markers rather than in a column. The latter never reads a
  secret, it observes that one exists, and it ignores markers whose meaning is
  not established rather than guessing them.
  `sapfx_common/rfc_tables.in_list_clauses` was added along the way: the
  default standard-account list already fills 69 of the 72 characters an
  OPTIONS line allows, so a single extra account made the keyword fail on a
  clause its caller never wrote.
- **A third Libdoc guard, on the `typedocs`.** The existing guard compares
  keyword NAMES, so it stays green while a spec's `usages` lists rot: adding a
  keyword enriches those lists in the library without changing any documented
  name, and the published pages silently lose their « used by » cross-links
  for a whole cycle. Measured while adding the guard: six types listed only a
  subset of their keywords. The checked contract is structural (names, type
  category, accepted types, usages) and deliberately excludes `doc`, which a
  project-specific type could one day carry in French for translation.
- **Convention #12 swept through the business keyword layer, then locked
  mechanically.** An audit of `resources/` found library-grade CAPABILITIES
  living as inline JS and `Evaluate __import__` in page objects: ushell
  service reads duplicated across the two launchpad page objects, a
  re-implementation of the bundle's registry fallback chain, binding-context
  reads (three copies), WebGUI menu/presence probes, and a cookie lambda
  carrying the paid epoch-1969 lesson. Promoted into `SapFioriLibrary` as
  **19 keywords**: launchpad services (`Get Flp User`, `List Flp Apps`,
  `List Flp Catalogs`, `List Flp Groups`, `Get Flp Intent Support`,
  `Flp Service Is Available`, `Flp Container Is Present` /
  `... Should Be Present`; new mixin `_flp_services.py`, pure reads without
  bundle injection like `Get Ushell Config`), the control record
  (`Get Ui5 Control Info`: FULL metadata type + binding context of rendered
  matches; `Get Ui5 Aggregation Info`: aggregation children rendered OR NOT,
  the items of a closed `Select` popover that no role engine can see; new
  bundle chapter `_ui5_bundle_info.js.tpl`), WebGUI perception
  (`Webgui Is Present`, `Get Webgui Element Count` global or per `window=`,
  `List Webgui Menus`, `List Webgui Menu Items`), and session state
  (`Get Session Cookie Summary`: names/domains only, `future_expiration`
  predicate encoding the Browser epoch-minus-one session-cookie trap, pure
  logic in `sapfx_common/web_cookies.py`; `Get Page Languages`;
  `List Page Iframes`; `Ui5 Runtime Is Ready` / `... Should Be Ready`, the
  promoted predicate of the resource-layer `Wait For UI5 Ready`).
  `Get Page Location` gained `url=`/`base=` (decompose a GIVEN address, no
  browser touched), and `sapfx_common.robot_args.displayed_count` merges the
  two copies of the displayed-count parser (ECC + WebGUI, anti-backslash
  lesson kept). rf-mcp Fiori intent map and the translated Libdoc spec/pages
  follow (81 keywords documented).
- **`check_conventions.py` now enforces the detectable motif of
  convention #12**, alongside #1/#2: `Evaluate JavaScript`,
  `Wait For Function` and `__import__` are blocking in `resources/` (with the
  exact-count `ALLOWED_12` allowlist on the em-dash-guard model: 4 assumed
  probes, each documented in place: the release-specific 1.71 tile walk, the
  malformed-fragment gesture, and the deliberately volatile tab marker) and
  in generated suites; `modules=` is blocked in suites (the DDIC 2026-08-17
  decision, previously prose-only); validation suites stay informative. The
  two generated suites carrying `__import__('json')` and the three carrying
  `modules=urllib.parse` were brought into line (Evaluate auto-import,
  `Get Page Location url=`).
- **Second convention #12 lot: the capabilities a linter cannot see.** The
  guard only detects the JS/`__import__` motif, never a capability written in
  plain Robot, so a judgement pass over the ECC, API and RFC layers found six
  more, now promoted. `SapEccLibrary` gains the two SE16 SCREEN primitives
  (`Use ALV Grid In Data Browser`, the remedy three of this library's own
  failure messages already prescribe to a PyPI user who has no `resources/`;
  and `Count Entries On Current Selection Screen`, which was already
  duplicated across three self-contained suites and stays reliable on an
  empty table where F8 returns nothing). `SapApiLibrary` gains
  `Build Draft Entity Path` (the COMPOSITE key of a draft-enabled v4 service:
  protocol knowledge, not one site's vocabulary) and `Classify Http Response`
  (the structural verdict on a raw response: three families of 404 hide under
  one status, and a 2xx with an HTML body is not data; pure logic added to
  `sapfx_common.gateway_status` beside `looks_like_html`).
  `sapfx_common.secrets` gains `secret_is_provided`, the predicate behind the
  four channels' credential guards, which answers WITHOUT ever measuring the
  value (a `Secret` refuses `len()`, and a naive guard hides the real missing
  prerequisite behind its own error): five copies of that test lived in the
  Robot layer. Finally `Fill Ui5 Input` / `Fill Dom Input` / `Fill Wc Input`
  now accept a `Secret` and unwrap it at the browser boundary, so the two
  inline `getattr(pwd, 'value', pwd)` disappear from the page objects, where
  the cleartext value entered the suite's variable space.
- **The family of operational-evidence reads that `Read Rfc Table` unlocks**
  (backlog 2.2), four `SapApiLibrary` keywords live-validated against A4H the
  day they were written: `Read Change Documents` (CDHDR headers with their
  CDPOS items: the audit assertion "the change was properly journaled" no
  OSS SAP tool offers), `Get Idoc Status` (EDIDC judged by CODE with an
  explicit scale where an unmapped status is NEVER a success; optional EDIDS
  history), `Read Application Log` (BALHDR with per-severity message COUNTS
  converted from zero-padded NUMC: locale-safe by construction, since the
  texts live compressed in BALDAT anyway) and `Get Job Log` (the complement
  of `Wait For Background Job`, through the official XBP chain with
  `BAPI_XMI_LOGOFF` guaranteed even on failure). Pure logic in
  `sapfx_common/rfc_reads.py`; new mixin `_rfc_reads.py` (convention #13,
  `_rfc.py` was already at 463 lines). Two traps were paid live and are
  encoded in the keywords rather than rediscovered: a CDPOS projection
  carrying both `VALUE_NEW` and `VALUE_OLD` exceeds `RFC_READ_TABLE`'s
  512-byte row buffer (`DATA_BUFFER_EXCEEDED`, AD/E/559, a code that does
  not name the cause), hence TWO projections merged on the item key; and
  `BP_JOBLOG_READ` is not remote-enabled (`CALL_FUNCTION_NOT_REMOTE`),
  hence XBP.
- **`packaging/install-rfc.ps1`, provisioning for the optional RFC channel.**
  The pack documented `pyrfc` in a single parenthesis, and the reason it is not
  installed lived in a comment inside `requirements-deploy.txt`, a file nobody
  opens. The script now does everything the licence allows a script to do:
  unpack the SAP NW RFC SDK archive (tolerating both zip shapes), set
  `SAPNWRFC_HOME` and `PATH` (User scope, or `-Machine` with an elevation
  check), install the pinned `pyrfc` into the pack venv and run a REAL import
  check. `-CheckOnly` diagnoses an existing setup without touching anything.
  What stays manual is the download itself, and deliberately so: the SDK is
  licensed by SAP, tied to an S-user, and not redistributable, so the entry
  point is either a local archive (`-SdkZip`) or the company's internal mirror
  (`-SdkUrl`, whose token is never logged). Three upstream facts, observed
  2026-08-26, are encoded in the failure messages rather than left to be
  rediscovered: SAP archived PyRFC on 2026-05-28, every PyPI release is yanked
  (hence the exact pin, since pip no longer selects them on its own), and the
  prebuilt Windows wheels stop at Python 3.12, so a workstation that needs RFC
  creates its venv on 3.10 to 3.12, a choice made at install time and not
  after. CI exercises the REFUSAL branches on a runner that has no SDK (the
  diagnosis exits 1, the no-archive refusal names SAP Note 2573790 and
  `-SdkUrl`, a non-SDK archive is rejected leaving nothing behind); real
  provisioning is an optional non-blocking step, skipped until an internal
  mirror is declared in the `NWRFC_SDK_URL` secret.
  **Measured on 2026-08-27, after that script was written: the download is
  often unnecessary.** On a workstation carrying SAP GUI for Windows 8.00, the
  client's « SAP NWRFC x64 Shared » component has already put `sapnwrfc.dll`
  and the `icu*50` libraries into `C:\Windows\System32`, so the prebuilt wheel
  loads and a REAL call goes through (`STFC_CONNECTION` echoed its text,
  `RFC_READ_TABLE` read T000, both through `Open Rfc Connection` / `Call Rfc`)
  with no `SAPNWRFC_HOME` and no `PATH` entry. The pack README now has people
  check that first, along with the three reasons the SDK keeps its place
  (licence and support, since that DLL ships for the client and no CI runner
  without SAP GUI has it; a patch level you did not choose; and source builds
  on 3.13+, which need the very headers the client omits) and the one
  constraint the shortcut does NOT lift, the 3.10 to 3.12 interpreter.
  The script was reworked accordingly rather than merely documented around it.
  It gained **`-UseSapGuiRuntime`**, the archive-free mode: it leans on the
  runtime already in `System32`, touches no environment variable (there is
  nothing to point at), installs the pinned binding and runs the real import
  check. `-CheckOnly` no longer calls the SDK missing when a runtime is there,
  it says which one answers and why the SDK still matters, so it stops exiting 1
  on a workstation where the channel works. The refusals were rewritten in the
  same spirit: with no archive and no `-SdkZip`, the message now offers the
  short way out FIRST when this machine can take it, before naming SAP Note
  2573790; `-UseSapGuiRuntime` on a machine without SAP GUI refuses and names
  both exits; combining it with `-SdkZip`, `-SdkUrl` or `-SkipPyrfc` is refused
  up front rather than half-honoured; and the import-failure message lists the
  missing runtime as a third cause instead of assuming the SDK. « SDK trouve »
  became « runtime NW RFC trouve », since that is what was actually verified.
  All five branches were exercised for real on a workstation with SAP GUI
  (diagnosis, both refusals, the nominal path twice for idempotence, and the
  no-runtime refusal with a diverted `SystemRoot`); CI gained the fourth refusal
  branch, which a runner without SAP GUI can genuinely prove.
- **A campaign for the RFC/BAPI channel**
  (`tests/robot/api/canal_rfc_a4h.robot` plus `resources/rfc_keywords.resource`,
  the fourth mirror of the business vocabulary; generated from
  `specs/canal-rfc-a4h.md`, validated live **11/11** against an ABAP Platform
  trial). The RFC was the only one of the four channels with no suite of its
  own, so it was exercised by nobody, and the gaps below had nowhere to show.
  READ ONLY: the LUW is opened only to prove it can be closed. The suite SKIPS
  cleanly (not red) where `pyrfc` or the native NW RFC runtime is missing, so
  it stays neutral in a full `tests/robot/` run; both branches were exercised
  (11 passed on 3.12, 11 skipped and exit 0 on 3.14).
  Five keywords were added to `SapApiLibrary` because the channel had no way to
  read or perceive anything: `Get Rfc Channel Status` and
  `Rfc Channel Should Be Available` (preflight telling apart a missing binding
  from a missing native runtime, two different remedies), `Get Rfc Connection
  Attributes` (an open channel does not yet say WHAT it talks to),
  `Read Rfc Table` (the screenless mirror of `Read Grid`, with the 72-character
  clause guard biting before the network) and `Rfc Should Fail With Code`
  (convention 3 applied to RFC: `Run Keyword And Expect Error` only ever sees
  the localized text, never the stable code). Pure logic in
  `sapfx_common.rfc_channel`.
  **Reworked the same day, when a corrected measurement widened the scenario
  on background jobs from two branches to five** (suite now **16/16** live).
  The first exploration had read `TBTCO` capped at 200 rows and concluded the
  target only carried finished jobs; it carries 4719 runs over four statuses,
  so every outcome of `Wait For Background Job` can be exercised READ ONLY, on
  the housekeeping jobs already there, without creating or cancelling a single
  one. Two keywords make that possible without an `Evaluate` in a suite
  (convention 12): **`Find Background Job Cases`** reads the job log whole and
  returns it as a catalogue of wait cases (which jobs of THIS target would
  produce `done`, `aborted`, `aborted_with_finished`, `pipeline`, `unmapped`),
  and **`Get Background Job Status Model`** states what the library maps, hence
  what it does not. Pure logic in `sapfx_common.rfc_tables`
  (`group_job_statuses`, `job_wait_cases`). Three properties are deliberate.
  The read cap defaults to 0, because a cap does not merely truncate, it
  falsifies the classification, silently: the suite replays the 200-row read
  next to the full one and the live run logged `{'F': 200}` against
  `{'F': 4597, 'Z': 105, 'S': 7, 'A': 10}`. `aborted_with_finished` exists
  because the cancelled branch only proves that `A` outranks `F` when played on
  a job carrying both. And `pipeline` is kept apart from `unmapped`, which the
  verdict merges into `waiting`: an uncharted status is the case where the
  library keeps waiting instead of concluding success, and it is the one worth
  locking. The meaning of the `Z` seen live is NOT asserted: its data element
  sits on a `CHAR1` domain with no value list, so the library prints `(?)` and
  the test only judges the fallback behaviour.
- **Fixed: a structure built by a Robot suite never reached the server.**
  `pyrfc` checks the EXACT type of a structure parameter and rejects a `dict`
  subclass, while every dictionary a suite builds is a `DotDict`: passing a
  structure to a function module was therefore impossible, with an error naming
  the parameter but not the cause. `Call Rfc` now normalizes parameters to bare
  types, recursively. Scalars are deliberately left untouched: converting
  number-looking strings would corrupt the numeric character fields of the ABAP
  dictionary, where `'0400'` is a connection number and not the integer 400, so
  a numeric parameter still has to be passed as a real number (the rule is in
  the keyword's documentation).
- **A reconnaissance campaign for the API channel of a BTP target**
  (`tests/robot/api/reconnaissance_canal_btp.robot` plus
  `resources/page_objects/workzone_api.resource`, validated live 9/9 twice).
  It is explicitly a reconnaissance, not an acceptance suite: the target
  exposes no business data through that channel, and the plan forbids
  inventing one. What it locks down is a map. A service key opens the channel
  in OAuth2; the backend's refusals separate into families on structural
  criteria (the GraphQL route DIALOGUES, navigation refuses on authorization,
  the OData prefix exposes nothing); the dialoguing refusal is about the
  request BODY, not the caller's identity, so reading it as an auth failure
  sends you hunting for credentials that are fine; and the site's admin host
  ignores a perfectly valid bearer token, because it wants an identity-provider
  session. That last point is the transposable one: **a service key opens a
  service's backend, not the administration interface sitting in front of it**,
  which the first pass could only suspect. The `404` classification anchors on
  the `x-cf-routererror` header rather than the body text (convention 3), and
  every probe is paired with a deliberately absent path: without that witness
  you cannot tell whether a 404 qualifies the resource or the whole host.
- **`Get Page Location`** (SapFioriLibrary): breaks down the address the
  browser actually reached into `{url, scheme, host, path, query, fragment,
  intent, intent_params}`, the inverse of `Open Fiori App` (pure logic in
  `_ui5_runtime.parse_location`). `intent` is filled only when the fragment
  really carries the `SemanticObject-action` shape, never an invented FLP
  navigation. `host` is what tells an identity provider apart from the site
  itself: without that check, a login page served by the site would turn
  green a test meant to prove the redirect. Promoted from a campaign page
  object where it lived as an `Evaluate __import__` (convention 12 proscribes
  exactly that), and the page object now only translates it into its own
  vocabulary.
- **`Get Ushell Config`** (SapFioriLibrary): reads `window['sap-ushell-config']`
  as a JSON-safe dict, with a dotted `path` argument (missing path = failure
  listing the available keys, never a silent None). The most
  locale-independent source a launchpad has: it DECLARES what the shell
  offers before rendering it. Observed live (2026-08-26, SAP Build Work Zone
  site): it is what says the `searchCEPNew` search is disabled, that 24
  services are declared, and that the session expires after 19 minutes,
  none of which any rendered control carries. Pure read, like
  `Ui5 Runtime Is Present`: it does NOT inject the `__SAPFX` bundle, so
  observing instruments nothing.
- **The wc and dom engines see through open shadow roots** (deep traversal,
  shared `deepQueryAll`): a Work Zone shell nests Web Components INSIDE the
  shadow roots of other Web Components (measured live 2026-08-26: 6 `ui5-*`
  hosts in light DOM, 16 in depth, three `ui5-button` invisible to the wc
  engine; the same CSS selector returned 0 through `Get Dom Match Count` and
  1 through Browser's `Get Element Count`). Returned paths now cross shadow
  boundaries with a DESCENDANT join (the form Playwright's CSS pierces), the
  recorder's upward walks (`closestWcElement`, `interactiveDomTarget`) hop
  boundaries too, and `Get Page Composition` counts hosts in depth
  (`wc_hosts`) while keeping the surface measure (`wc_hosts_light`). Proven
  offline by clicking an id-less button nested in a shadow root
  (`fiori_wc_smoke.robot`, 12/12).
- **`Get Ui5 Open Popups` sees Web Components popups** (`technology` field,
  `ui5`|`wc`): the user menu of a Work Zone shell is a WC popover, and the
  keyword returned `[]` with the menu open (measured live), while the menu's
  entries stay rendered with it closed, exactly the trap the keyword exists
  to lift. Open WC popups (`ui5-popover`/`ui5-dialog`/`ui5-menu`/`ui5-toast`,
  scoped tags included, witness = their `open` property) are now listed, with
  the host's resolvable `css` path; on a wc/hybrid page without a UI5
  runtime they are returned instead of the former hard failure.
- **`Get Http Response`** (SapApiLibrary): raw, tolerant HTTP read of a
  session path (`{"status", "headers", "body", "truncated", "error", "url"}`,
  never raises, truncation always flagged, per-request headers). Born from a
  live API reconnaissance of a SAP Build Work Zone site (2026-08-26), where
  reading the HTML body a BTP approuter serves required hijacking it from
  `Get Odata`'s failure message: a workaround, not a method (convention 12).
- **`headers` on `Open Api Session`**: session-level default headers, applied
  last so they can override the built-in `Accept: application/json`. A BTP
  approuter arbitrates between an HTML page and a JSON challenge on that very
  header, and the session gave no way to set it. Values are never logged.
- **Two identity-provider states in the Gateway preflight**
  (`sapfx_common.gateway_status`, so `Get Gateway Status` /
  `Gateway Should Be Active` / `Wait Until Api Available`):
  `identity_provider_redirect` (3xx, or the same-origin guard's refusal to
  carry authentication to another host, which previously came back as
  `unreachable` with a "docker start" remediation, the exact opposite of the
  truth on BTP) and `login_page` (HTTP 2xx whose body is an HTML document,
  detected structurally, never by localized text). The founding case, measured
  live: a Work Zone site answers **200 with a login bootstrap page on every
  declared route** and never issues an authentication challenge, so
  `Gateway Should Be Active` passed green on a target that had served no data
  at all.
- **The RFC channel gets a second campaign, and this one is about what two ABAP
  releases show that one hides** (`tests/robot/api/canal_rfc_abap2023.robot`,
  generated from `specs/canal-rfc-abap2023.md`, live **10/10** against ABAP
  Platform 2023 on 2026-08-28). The existing campaign already passes on that
  target by overriding variables, so portability was not the subject: what is
  new is the DIVERGENCE, the measured EQUIVALENCE (one is worth the other, and
  together they say where to put an assertion), and one trap that only a second
  target reveals. The trap is the campaign's centre: **the system carries TWO
  airline catalogues of different populations** (18 in the classic demo model,
  16 in the modern travel model, the smaller strictly included in the larger).
  A crossing that points one channel at the first and the other channel at the
  second produces a perfectly reproducible two-row gap, blamed on a defect that
  does not exist; the scenario is written backwards so that a silent trap
  becomes a loud assertion. Also locked: identity proved by RELEASE, kernel and
  software components rather than by the system id or the application host name
  (identical on both containers of this workstation, so a campaign trusting
  them would be green against the wrong system) and never by the published IP
  address (measured volatile, it changed between two readings of the SAME
  system one day apart); the field contract read ON the target with its
  counter-proof played, not quoted; two crossings the previous campaign did not
  make (travels and modern airlines, RFC against OData, 4136 = 4136 and
  16 = 16, both computed in the same run and never engraved); two logon
  refusals that, on this release, return the same code AND the same text word
  for word, so the test asserts the INDISTINCTION instead of pretending to
  separate them; and a communication refusal that names the port actually
  contacted, which is how the local relay documented in the preconditions
  stops being a story and becomes a measurement (base plus instance number,
  3342 for instance 42).
- **`Rfc Should Fail With Message Id`, and the message identifier in every RFC
  refusal description** (`sapfx_common.rfc_channel.rfc_message_identity`, so
  `Rfc Should Fail With Code` now returns it too). The technical code is stable
  but coarse, and two very different causes share one: the classic case is a
  misspelled field name on a full table, refused as `TABLE_WITHOUT_DATA`. The
  ABAP message identifier (class, type, number) designates the exact refusal
  and is just as language independent, so convention #3 gains a finer criterion
  rather than a looser one. Measured live: `DA/E/131` for a missing table,
  `AD/E/718` for a missing field, `FL/E/046` for a missing function module, and
  **no identifier at all** for `RFC_INVALID_PARAMETER`, which is not a gap but
  a proof: that refusal is raised client side and never reached the
  application. A refusal carrying no identifier fails saying so, rather than
  comparing itself to emptiness.
- **The RFC channel surface becomes a deterministic, comparable artifact**
  (`sapfx_common.rfc_surface`, keywords `Write Rfc Surface Artifact` /
  `Read Rfc Surface Artifact` / `Compare Rfc Surface Artifacts`). The question
  "which function modules here and not there" is not answered by a note in a
  document: it is answered by an artifact produced on each target and compared
  off-system, the pattern this repo already had for the DDIC inventory and for
  the cross-channel campaign, and which the RFC channel lacked. Two properties
  are deliberate and make a later comparison honest. An artifact carries the
  IDENTITY of the target that produced it (release, kernel, components), since
  without it comparing two artifacts means comparing two unknowns, and here the
  system id would not save you: both containers share it. And an artifact
  carries its SCOPE, so comparing two targets whose measure sets differ is
  refused as inconclusive rather than averaged, because a measure missing on
  one side is not worth zero. The hash excludes the timestamp, so two runs on
  the same target reading the same figures produce the same hash.
- **A navigation and deep UI5 interaction campaign on the OpenUI5 Demo Kit**
  (`tests/robot/ui/fiori/navigation_interaction_demokit.robot`, generated from
  `specs/openui5-demokit-navigation-interaction.md`, 12 scenarios, live
  **12/12 on four runs**, 2026-08-30). It is the only campaign in the repo that
  needs neither credentials nor a system to provision, so it is the one anybody
  can replay: the target is public and the browser is **visible by default**
  (`-v DEMOKIT_HEADLESS:True` for CI, also validated). Hash routing, tab keys
  equal to routes, search suggestions that navigate, a deep link restoring
  state without passing through the home page, browser back, a filtered API
  tree walked by qualified name, a reversible display toggle, a documentation
  table cross-checked against the LIVE control, a cascade of popovers then a
  dialog cancelled by position, theme changed and restored, and a sample
  iframe whose scope tightness is proven both ways. Read-only, with a teardown
  that restores state even on failure. Page object shipped in
  `resources/page_objects/openui5_demokit.resource`, and both files travel in
  the Windows pack, which gains its first complete plan-to-suite example.
  The campaign is also what surfaced the two library defects fixed below and
  above: a live target pays for itself.
- **`Get Ui5 Theme`**: the UI5 runtime theme as a JSON-safe
  `{requested, applied}`. Two values, because they diverge and the difference
  is what a test needs: `requested` is what the runtime was told to apply (the
  `sap/ui/core/Theming` module, falling back to the legacy Core configuration
  that UI5 2.x removes), `applied` is what the document actually carries
  (technical `sapUiTheme-<key>` class). Measured live on the OpenUI5 Demo Kit
  (2026-08-30): right after the click there is a window where `applied` is
  EMPTY while the runtime swaps its stylesheets and `requested` already carries
  the target, so a theme is waited for, never read once. It is the locale-safe
  witness of a theme change (convention #3: the menu entry that selects it
  carries a translated label, `sap_horizon_dark` does not). Pure read, no
  bundle injection, frame scope respected; the campaign layer no longer parses
  the class attribute itself (convention #12).

### Fixed
- **`Read Ui5 Table` returned an empty list on a table it could not read**,
  which is the same answer as a genuinely empty table and therefore a green
  test asserting nothing. Found live on the OpenUI5 Demo Kit (2026-08-30):
  against the `sap.ui.documentation.LightTable` of a control's property table,
  the selector resolves exactly one control, that control carries its rows, and
  the read returned `[]` without a word. The bundle now returns a VERDICT (the
  control type, the aggregation it read from, how many rows were candidates and
  how many were skipped) and the keyword fails naming the type, the row count
  and the fallback (`Get Ui5 Control Info`, `Get Ui5 Aggregation Info`,
  `Get Ui5 Properties`) in the two cases that were silent: no `items` and no
  `rows` aggregation at all, or rows that expose no cells. A genuinely empty
  table still returns `[]`, and group-header rows are still skipped without
  complaint, because both are legitimate results. Pure verdict in
  `SapFioriLibrary._ui5_runtime.table_read_verdict`, unit-tested off-browser.
- **Two page objects were relying on something untrue, both surfaced by a full
  live replay of every suite against the four channels (2026-08-29).** Neither
  was a library gap: in both cases the hardened library check was right and the
  caller was wrong, which is why the fixes live in `resources/page_objects/`
  and not in `src/`.
  - *Work Zone*: `Lire Les Identifiants D Iframe` inherited the accidental
    PAGE scope of the inline probe it replaced. `Evaluate JavaScript` with a
    `${None}` selector evaluates on the page whatever the frame stack, while
    `List Page Iframes` honours the stack like every other library keyword and
    exactly as its own documentation states. Called after entering the
    application iframe, which nests none, it returned an EMPTY list rather than
    an error, and an empty list is a perfectly plausible result here (the same
    campaign asserts that the home page carries no iframe), so the failure read
    as "no iframe in the shell" and sent the diagnosis towards the launchpad.
    The keyword now forces shell scope and restores the stack on every path.
  - *ABAP launchpad 1.71*: `Ouvrir La Recherche Du Shell` assumed one click
    opens the shell search. Measured at the DOM: the first click creates the
    control WITHOUT rendering it (field absent from the DOM, button still
    `visible=True`, control already in the registry declaring itself visible),
    and only the second opens it (560x36, inner input 528x26, button flipped to
    `visible=False`). Under the single click the scenario then typed into a
    field that did not exist: the value read back stayed empty and Enter went
    to whichever tile held the focus, opening an application instead of running
    the search. Opening is now idempotent and retried, and the witness is the
    field's SURFACE, never its presence in the registry. The scenario had
    passed 19/19 on 2026-08-24, five days before the non-null-rectangle
    hardening of `Ui5 Control Should Be Visible` (2026-08-26) that exposed it:
    a campaign validated BEFORE a hardening has to be replayed AFTER it, or the
    false green outlives the very fix aimed at it.
- **`Get Rfc Channel Status` declared the channel available on a machine
  without the native runtime**, caught by the `runtime_absent` CI preflight on
  its FIRST real execution (2026-08-29). The measured premise everyone had
  wrong: pyrfc 3.3.1's `__init__` swallows the native load failure
  (`except Exception as ex: print(ex)`), so on a machine without
  `sapnwrfc.dll` the import SUCCEEDS and yields a module without
  `Connection`. Trusting the import meant the RFC suite would go red instead
  of skipping, and `Open Rfc Connection` died with a bare `AttributeError`.
  The verdict now reads the module's CONTENT (`rfc_channel.binding_status`,
  classified `runtime_absent` with the same remediation), `Open Rfc
  Connection` fails naming cause and remedy, and the CI step asserts the
  real premise (importable but incomplete binding) instead of a failing
  import. `install-rfc.ps1` was already safe: it imports `Connection` by
  name.
- **Three agent-facing ambiguities closed at the Robot/MCP boundary** (all
  three from real agent incidents, 2026-08-27: through `execute_step` every
  argument arrives as a string, and an agent only reads the message).
  `Read Grid` / `Read Full Grid` now accept `columns` as a comma-separated
  string and as a serialized list literal (`"['A', 'B']"`), both previously
  treated as ONE unknown column name while every column sat in "Available";
  a list passed in `max_rows`' positional slot now fails naming the argument,
  the likely positional shift and the `columns=` remedy instead of a bare
  `TypeError: int()`; the string-to-list normalization is shared pure logic
  (`sapfx_common/robot_args.py`). `Wait For Ui5 Idle`'s failure now prints
  the COMPUTED required settle in ms (a bare `settle=2000` is 2000 Robot
  SECONDS, and the final state shown could look like it contradicted the
  failure), and an "unreadable last state" now names its cause: the probe's
  error, the current frame scope, and the two remedies (`Set/Push Ui5
  Frame`, `Get Page Composition`), the BTP shape where two minutes of
  failure carried no clue.
- **`Ui5 Control Should Be Visible` no longer passes on a zero-rectangle
  control**: rendered-registry presence was the only check, while the wc/dom
  mirrors already required a non-zero rect. Measured live (2026-08-26, Work
  Zone shell): a RENDERED search field keeps a 0x0 rectangle permanently
  (implementation disabled by configuration) and the assertion passed on it.
  The failure now distinguishes "no match" from "matches, all zero-rect"
  (naming the ids).
- **The dom engine now pierces shadow boundaries like Browser does**: the
  first deep-traversal fix filtered candidates with `matches()`, which
  evaluates ancestors in the element's own TREE, so a path CROSSING a shadow
  boundary (exactly the form `wcCssPath` returns) could never match. Measured
  live on the Work Zone shell: the same CSS string returned 1 through
  Browser's `Get Element Count` and 0 through `Get Dom Match Count`. A
  segment-by-segment piercing resolution now runs as a FALLBACK when the
  normal path finds nothing, so a selector that already resolved keeps its
  exact result. Counter-proof run with the fallback disabled: `0 != 1`, the
  field symptom. The shadow-boundary primitives moved to their own bundle
  chapter (`_ui5_bundle_shadow.js.tpl`, convention 13).
- **`docs/fiori-architecture.md` and its French pair no longer describe the
  wc engine as a light-DOM-only scan**: the claim "application content stays
  in the light DOM via slots, only component internals live in shadow roots"
  was disproved by the same shell, and the docs said so while the code had
  already changed.
- **Short wc tags now reach the MIXED spellings of UI5 Web Components**
  (`ui5-shellbar-item`: glued family, dashed component): the 2026-08-24 fix
  covered the two extreme forms (`ui5-shellbaritem`, `ui5-shell-bar-item`)
  and `tag=ShellBarItem` still matched nothing on a real Work Zone shell
  bar. All glue/dash combinations between words are now tried (bounded).
  Web recorder artifacts regenerated; extension 0.10.0 → 0.10.1.
- **Preflight probes now feed the channel telemetry** (SapApiLibrary
  `_probe`): a probe traverses the network like any read, but bypassed the
  `requests` counter, so `Api Channel Should Show Activity`, whose whole
  point is proving the network was traversed, failed on a legitimate
  reconnaissance made of probes. Measured live before the fix: ~15 network
  probes, `requests: 2`. Probe refusals stay results, not channel errors.
- **`Api Channel State Should Not Leak Credentials` no longer passes on an
  empty state** (`resources/api_keywords.resource`): observed live validating
  `{'api_sessions': []}`, where there is nothing to leak and therefore
  nothing proven. An empty state now fails naming the most frequent cause
  (under rf-mcp, resource and library can serve two namespace-partitioned
  session registries).

### Changed
- **The `sapfx` skill becomes an orientation map plus seven references.** It had
  drifted: it announced "three channels" where the repo has four (the RFC
  channel owns a resource and two live suites), said nothing of the security
  vocabulary, of the industrial layout (`tests/robot/{api,ui,cross}`,
  `page_objects/`, `variables/`), of conventions 11 and 13, carried no command
  line, no suite skeleton, no field trap, and no word on the rf-mcp pitfalls it
  exists to drive. `SKILL.md` now holds only what is needed on every load (what
  makes truth, the four channels, the perception loop, seven rules, the agent
  cycle, a routing table), and `references/` carries `demarrage`, `canal-ecc`,
  `canal-fiori`, `canal-api-rfc`, `conventions`, `pieges-terrain` and `rf-mcp`.
  An eighth reference, `cycle-agents`, makes the agentic cycle checkable rather
  than merely named: who writes where (and who never writes tests), the proof
  each step owes (the planner writes only what it observed, the generator
  EXECUTES every step live before writing it, the healer verifies the repair
  live, the gates run in order), the four feedback loops closed mechanically
  (provenance stamp, « Écarts constatés », the `PÉRIMÉE` marker, the heal
  journal), and the healer's five failure classes with the layer each one
  repairs. `tests/unit/test_skill_sapfx.py` keeps it honest: every keyword cited must
  exist in `src/` or `resources/`, references and links must match both ways,
  and the map stays a map. The guard bit on its first run (three condensed
  keyword forms that named nothing), and the pack's leak scan caught a private
  path mentioned in the conventions reference.
- **`resources/` now says what it is: examples to customize, never a universal
  SAP truth.** The layer carries the business vocabulary of ONE installation
  (every id, service path, table and profile parameter in it measured live on
  this repo's lab targets), while `src/`, the libraries and their capabilities,
  is what holds on every SAP system. Nothing said so until now: the README, the
  pack README, `llms.txt`, `docs/architecture` and the files themselves all
  presented the layer as the one "tests should call", and these files ship as
  is to the public repository and inside the Windows pack, where a reader
  without the lab context reads them as a contract and writes tests against
  another system's screens. Added `resources/README.md` (+ `.fr.md`): what was
  measured and where, the three degrees of portability (often reusable as is /
  to verify and adjust / lab specific), what stays reusable (the mirrored
  four-channel vocabulary, convention 1, one page object per screen, the safety
  properties, release divergences as variables never as a version `IF`), how to
  adopt it on a real system, and where a fix goes (capability to `src/`, target
  specifics here). Every `.resource` now opens with the
  « EXEMPLE À PERSONNALISER » banner inside its Robot `Documentation` (so Libdoc
  shows it), enforced by `tests/unit/test_resources_are_examples.py`, and the
  point is restated in convention #1 of `CLAUDE.md`, its two mirrors, and the
  `sapfx` skill.
- **The business keyword layer consumes the promoted capabilities instead of
  its inline JS** (convention #12 sweep): `fiori_keywords.resource` (WebGUI
  log-off/popup/rendered probes, count parsing), `abap_flp.resource`
  (identity, catalogs, groups, intent resolvability, SearchableContent,
  settings-by-binding-context, ICF language select via Browser's
  `Get Select Options`), the `workzone_launchpad/user_area/session/
  shell_search` page objects and `fiori_travel_list.resource`. Return shapes
  and the French vocabulary are preserved; the page objects keep only site
  anchors and translations, plus the four probes assumed in `ALLOWED_12`.
- **The healer's blind-eval scenario moved with the code it targeted**
  (`scripts/agent_eval_harness.py`): `se16-count-button` drifted an id that
  now lives in the library, where the healer never patches. The canonical
  scenario is `se16-table-field` (`ctxtDATABROWSE-TABLENAME` ->
  `ctxtDATABROWSE-TABNAME`), which stays in `resources/`, sits on the eval
  suite's path and is closer to what really drifts. The guard that caught
  this (`test_the_default_scenario_matches_the_real_repo_resource`, which
  checks the target still exists exactly once in the real resource) did its
  job: it is why the harness did not die silently.
- **`comms/proofs.json` now carries the live CAMPAIGNS, not just one live
  ratio**, and `scripts/check_comms_sync.py` accepts a `N/M scénarios`
  citation that matches any declared campaign. A single live proof held as
  long as there was a single target system. Since the launchpad campaign is
  replayed on two SAP releases, requiring one ratio meant the second
  validation could not be published at all, which pushes the figure to be
  written where no guard watches it: exactly the hole this guard exists to
  close. Each campaign still owes its target and its validation date, and a
  ratio nothing in the repo backs is still refused. The two campaigns
  declared: 22/22 on an ABAP Platform 2023 serving SAPUI5 1.120.15, and
  20/20 on an ABAP Platform 1909 serving 1.71.47.

## [0.7.0] - 2026-08-25

### Added
- **`containedIn`, the DOM-containment selector part** of the Fiori role engine
  (`Resolve Ui5 Control`, `Get Ui5 Ids`, `Get Ui5 Properties`, `Get Ui5 Match
  Count`…): restricts the match to controls whose DOM node descends from the DOM
  node of the designated control (exact id, then id suffix, then the DOM node
  carrying that id, which is what `Get Ui5 Ids` returns). It is **not** a
  duplicate of `viewId`: that one follows the property (owning view, factory
  ids), this one follows the rendering, and the second reaches what the first
  cannot see. It exists because a launchpad tile on SAPUI5 1.120 is rendered by
  a **separate component**: its title and counter are neither in its view, nor
  in its aggregations, nor in its binding context, and reading them had been
  improvised as page-object JavaScript. The capability now lives in the library
  (convention 12), the page object carries only vocabulary, and the live run
  returns exactly the same values as the JavaScript it replaces.
- **A reversible write scenario on both ABAP launchpad campaigns**: pin an
  application from the App Finder, then unpin it, proving the home page is
  returned to the state it was measured in. **Opt-in with two turns**, the
  pattern of `tests/robot/cross/simulation_ecriture_lecture.robot`: the `write`
  tag says what the test does, `-v ABAP_FLP_WRITE_OPT_IN:yes` says it was
  intended, and without the variable the test is SKIPPED even in a full
  `tests/robot/` run (a tag alone depends on the memory of whoever types the
  command). The restoration is **observed**, never assumed: it is the
  disappearance of the pinned intent that settles it, not a tile count back to
  its starting value, which would only prove arithmetic. The teardown logs the
  diagnostics BEFORE cleaning up (cleaning navigates away and destroys the
  failing screen) and unpins even after a failure. Validated live on both
  targets: 1.120 **22/22** and 1.71 **20/20** with the opt-in, 21/22 and 19/20
  with one skip without it.
- **An offline smoke for the versioned `__SAPFX` bundle**
  (`tests/robot/fiori_bundle_version_smoke.robot`, no SAP, no network): it
  plants a stale bundle in the page exactly as an rf-mcp hot swap does, then
  measures in a real browser that a keyword call replaces it, that the `fetch`
  and `XMLHttpRequest` wrappers are the SAME functions as before (so not
  stacked), that the state carrier is the same object, that a witness dropped in
  the toast capture survives, and that one request is still counted exactly
  once. Counter-proof run with the old guard restored: the replacement test then
  fails with the very field symptom, `window.__SAPFX.resolveByDom is not a
  function`.
- **A replayable campaign against the Fiori launchpad served by an ABAP server**
  (the classic ushell of the `/sap/bc/ui2/flp` ICF service), generated from
  `specs/exploration-flp-abap-a4h.md` and validated **live 19/19** against an
  ABAP Platform 1909 serving SAPUI5 1.71:
  `tests/robot/ui/fiori/exploration_flp_abap_a4h.robot`, with its page object
  `resources/page_objects/abap_flp.resource`. The page object is deliberately
  **parameterised by target** (URL, credentials, intents, classification
  markers) rather than specialised on one system: a second campaign on another
  ABAP release reuses it as is, and the values measured on this target live in
  the suite. What this launchpad establishes, point by point against the Work
  Zone cFLP already covered: there is **no iframe at all** (the application
  lives in the shell's own document and is recognised by the container whose id
  is derived from its intent), the catalogue is read through `LaunchPage`
  because `SearchableContent` does not exist on this ushell (404), and the 1.71
  runtime emits no deprecation, which makes the console triage readable (three
  errors on a clean load, all traced to components that are not deployed).
  Read-only: the home edit mode is entered only to be left without moving
  anything, and the test **proves** it by comparing the groups before and after.
- **The same launchpad campaign on a second ABAP release**, generated from
  `specs/exploration-flp-abap-2023.md` and validated **live 21/21** against an
  ABAP Platform 2023 serving SAPUI5 1.120.15, with the 1.71 suite replayed
  **19/19** right after to prove the shared page object did not regress. It
  exists because one release makes mono-release assumptions invisible, and it
  proved the point on its first run: the user actions menu changes both its id
  and its control type (`meAreaHeaderButton`/`ShellHeadItem` becomes
  `userActionsMenuHeaderButton`/`sap.m.Avatar`), the navigation refusal dialog
  gains a second button so acknowledging at position 0 **copies the message and
  leaves the dialog open** while the logoff confirmation still answers at
  position 0, the 1.71 tile probe returns empty titles and intents **without
  failing** on 1.120 (five scenarios would have gone green on nothing, now a
  named failure), the home control floor drops from 184 to 134, and the browser
  back navigation needs 55 s to settle where 15 s was enough. What is confirmed
  IDENTICAL is a result too: no iframe, the same catalogue (2 catalogues, 67
  tiles, 62 intents, 61 resolvable), 54 App Finder tiles, the same user action
  suffixes. Everything that differs is a **variable** or a **named strategy**
  (the name of the keyword that knows how to read or close), never an `IF` on
  the version: adding a release adds a keyword, not a branch.
- **Three Fiori keywords that close capability gaps found on that live target**
  (convention 12), each with its off-browser unit tests: `Get Ui5 Ids` (which
  controls matched, the reading that completes the count and the properties
  when the documented anchor is an id SUFFIX), `Get Ui5 Open Popups` (the Fiori
  counterpart of ECC's `Get Open Windows`: a closed dialog stays **rendered**,
  so no count and no resolution tells open from closed, only
  `sap.m.InstanceManager` does) and `Click Ui5 Dialog Button` (acknowledge a
  dialog by the POSITION of its button: MessageBox buttons carry a generated id
  and translated text, which two live campaigns paid for in two languages).
- **Two replayable campaigns against a live SAP BTP launchpad** (SAP Build Work
  Zone behind a real SAP Cloud Identity Services tenant), generated from plans
  and driven end to end through rf-mcp before being written:
  `specs/workzone-launchpad-btp-perception.md` ->
  `tests/robot/ui/fiori/exploration_launchpad_workzone.robot` (**live 9/9**),
  and `specs/workzone-panier-parcours-applicatif.md` ->
  `tests/robot/ui/fiori/parcours_panier_workzone.robot`. The first campaign
  perceives the shell and is read-only; the second plays a **reversible**
  business journey inside the application's cross-origin iframe and returns the
  cart to the state it measured at the start. Both are **discovery-driven**:
  the applications visited are the ones the shell's own catalogue service
  declares on the day of the run (read through `SearchableContent`, which
  answers what the signed-in user may open, not what the page happens to show),
  and no category, product or volume is hard-coded. Locators live in two page
  objects (`resources/page_objects/workzone_launchpad.resource`,
  `workzone_shopping_cart.resource`); the site URL, user and password never get
  a committed value (convention 11).
  What the real target taught, and no fixture could: the Work Zone shell is a
  **hybrid** page (UI5 runtime plus a shell bar built from scoped UI5 Web
  Components, `ui5-shellbar-6bfd01e3`), the application iframe is created
  **after** the navigation keyword returns and its generated id moves between
  runs (`__container4` then `__container5` in one session, after three other
  values the day before), entering that iframe does **not** mean the
  application has started (its first perception can legitimately report zero
  controls), and counting a launchpad's console errors is meaningless: 17 of
  the 20 seen are `[FUTURE FATAL]` deprecations that SAP's own shell code
  emits. The campaign therefore asserts the only property that holds, zero
  uncaught page exception, and **classifies** the rest instead of failing on
  code this repository does not maintain.
- **Convention #12: a capability gap found on a live target is closed IN the
  shipped library.** A library keyword that misbehaves gets fixed in `src/`; a
  missing one gets created there (pure logic in `sapfx_common`), never as
  inline JS in a page object, an `Evaluate` in a suite, or a helper only one
  campaign will ever see; a workaround already sitting in an intermediate layer
  gets promoted. The boundary is what makes the rule usable: libraries carry
  CAPABILITIES (perception, resolution, waiting, engines, state, protocols),
  `resources/` carries one site's BUSINESS VOCABULARY. It matters because the
  libraries are what ships to PyPI: a fix left in a resource helps nobody else,
  gets re-improvised in the next project, and leaves the defect in place for
  every other user while the campaign that found it looks green. It is also the
  one place where this repo's « Observe, do not fix » posture explicitly does
  not apply: the system under test is observed, our own library is repaired.
  Stated in CLAUDE.md and both mirrors, in the `sapfx` skill, and in the two
  agents that write code (sap-generator, sap-healer, the latter gaining a
  « library defect » failure class next to locator drift and timing).
  `check_guidance_sync.py` now keeps that rule in those two definitions only
  (a scoped marker map: the planner explores and the ISTQB agent writes
  offline), with counter-proofs in both directions.
- **Two engine defects the live launchpad exposed, fixed rather than
  worked around.** (1) The `wc` engine's **short type never matched a two-word
  component**: `ShellBar` became `shell-bar`, which contains a hyphen, so it was
  taken for a FULL tag name and never prefixed with `ui5-`. Measured on a real
  Work Zone shell bar, `tag=ShellBar` returned **0** while the page carried a
  `<ui5-shellbar-6bfd01e3>`. UI5 Web Components uses both spellings, glued
  (`ui5-shellbar`) and hyphenated (`ui5-side-navigation`), so the engine now
  tries both; the two cases are locked offline in `fiori_wc_smoke.robot`.
  (2) **`viewId` did not scope by view**, it compared the given id to the
  CONTROL's id as a substring: that works for a factory-built control (whose id
  contains its list's id) but not for a control with a fully generated id, and
  `controlType=Button viewId=<view>` therefore returned 0 on a view that carried
  three buttons. It now walks up to the owning view, keeping the substring form
  as a second chance, so nothing that worked stops working and the parameter
  finally does what its name promises.
- **`Get Ui5 Property` / `Get Ui5 Properties`** (SapFioriLibrary): read a
  control PROPERTY from the UI5 registry, for one control or for every match at
  once. The complement of `Get Ui5 Text`, not its duplicate, and it exists
  because the live campaign hit both of its limits in one afternoon. `Get Text`
  returns what the browser DISPLAYS, so it requires the control to be VISIBLE
  and it returns everything the control draws: a `sap.m.StandardListItem` with
  a counter reads `"Accessories\n34"` where its `title` property is
  `"Accessories"` (re-injected into a locator, that name matches nothing), and
  a control rendered inside a collapsed `sap.f.FlexibleColumnLayout` column has
  no readable text at all, so the read waits ten seconds for a visibility that
  will never come and the failure looks like locator drift. Reading the
  property is exact, needs no visibility, and lists an entire list of titles in
  one call. An unknown property name fails naming the available ones, rather
  than quietly returning a list of `None`.
- **API-key authentication, and with it a third live target for the API
  channel** (`Open Api Session    api_key=...    api_key_header=APIKey`): the
  SAP Business Accelerator Hub sandbox (api.sap.com) authenticates by a header
  key, not Basic, not OAuth2, not mTLS, so until now the channel simply could
  not reach it. That target matters beyond the auth mode: it is the only one of
  the three that serves the REAL shape of SAP S/4HANA Cloud APIs (the A4H
  Gateway is a demo repository and cap-sflight is a Node app), it needs no
  install, and it costs nothing. An empty key is refused **at open time**: sent
  as an empty header it would authenticate nothing and surface much later as an
  HTTP 401 that names neither cause nor remedy. The key never reaches a log,
  and `List Api Sessions` reports `authenticated` without exposing the header.
  Business layer in `resources/api_keywords.resource` (`Open Api Sandbox
  Channel`, `Api Key Should Be Provided`, service paths per convention 1) and a
  third `sandbox` lane in `tests/robot/api/canal_api_odata.robot`, so the same
  business keywords are now exercised over three authentication protocols. That
  lane is also the only one to serve **both OData protocols from one system**,
  v2 (`API_BUSINESS_PARTNER`) and v4 (`api_purchaseorder_2`, 210 454 purchase
  orders). The v4 service path was read off the live system rather than
  deduced: the `odata4/sap/<api>/srvd_a2x/sap/<definition>/0001` shape varies
  per API, and perfectly plausible candidates answer 404, or 403 `Unified
  Connectivity: Forbidden` for an API the key does not cover.
- **Three library keywords rejoin the rf-mcp intent maps** (`Read Ddic Table
  Fields`, `Get Se16 Selection Criteria`, `Probe Odata Entity Sets`): added by
  the cross-channel campaign without being routed, which the map-freshness
  guard caught. Outside the map an agent re-improvises them, which is exactly
  the divergent-copy problem those keywords were written to end.
- **Cross-channel write/read simulation** (`specs/simulation-ecriture-lecture-cross-canal.md`
  -> `tests/robot/cross/simulation_ecriture_lecture.robot`, live 8/8): a row is
  written through the SCREEN and observed through the API, then deleted and its
  disappearance verified on both channels. It exists because the cross-channel
  campaign's write-candidate guard returns zero candidates, and that is not a
  guard being too strict: a `sap:` annotation says what the SERVICE permits and
  says nothing about whether a write is **reversible** or **cleanable**, the
  two conditions that actually decide a write simulation. This suite produces
  the dated observation that `reversibility_observed` was missing.
  Reversibility is asserted on the ENTITY, never on a count alone: two writes
  and one delete would leave the same count as no write at all.
  Safety is mechanical rather than declared: the campaign **skips in Suite
  Setup without opening a channel** unless an explicit opt-in variable is
  passed (a tag alone depends on whoever types the command), every writing
  keyword goes through an allowlist whose empty value refuses everything,
  deletion re-reads the filtered grid and stops without deleting if the
  selection is not exactly the intended row, and SE16's mass-delete menu index
  appears nowhere in the page object, which a unit test enforces.
- **The SE16 data-entry screen becomes a reusable page object**
  (`resources/page_objects/se16_table_entry.resource`): create, search and
  targeted delete of a table row. Those locators previously existed only raw
  inside a self-contained demonstration suite, which deliberately departs from
  convention 1, so nothing reusable could be built on them.
- **Four more proven entity set to table couples** in the cross-channel
  mapping, from the `Z_BIND_FLIGHT_R` service the campaign did not cover:
  `Airline`/`/DMO/CARRIER` (16), `Connection`/`/DMO/CONNECTION` (20),
  `Flight`/`/DMO/FLIGHT` (40), `Airport`/`/DMO/AIRPORT` (47), each established
  by cross-counting and not by name. The campaign now runs 9/9 with 14 couples.
- **Cross-channel acceptance campaign, ECC screen against the live API**
  (`specs/croisement-ddic-odata-ecc-s4hana.md` ->
  `tests/robot/cross/croisement_ddic_odata.robot`, 9 scenarios, validated live
  9/9). The flagship suite already proved **one** hardcoded pair
  (`SNWD_PD` = `SEPMRA_SHOP/Products`). This generalises it into a
  discovery-driven, bounded and replayable campaign that answers the real
  question: which tables and which entity sets a target actually exposes, and
  whether the two channels agree. Three levels, each switchable: **existence**
  (every declared entity set is really addressable), **volume** (the OData
  `$count` equals the SE16 count of the mapped table), and **field contract**
  (`$metadata` properties against the DDIC fields read from DD03L, the level
  that catches a schema drift between ECC and S/4HANA). It consumes the DDIC
  inventory as an upstream brick rather than restating it, produces a
  deterministic artifact, and compares two targets offline. Read-only: the
  write-simulation scenario identifies candidates without writing.
- **Entity-set annotations in the `$metadata` contract**
  (`sapfx_common.odata_metadata`): each entity set now carries `label`,
  `capabilities` (the `sap:` annotations of the entity set itself, Gateway
  default applied when the attribute is absent) and `declared_capabilities`
  (only those actually written in the document), plus
  `write_simulation_candidates` on top. This is what lets a suite tell a
  **legitimate refusal from an anomaly** before making any call: measured
  live, the single entity set of a 29-set service that answers HTTP 403 is
  also the single one annotated `sap:addressable="false"`.
- **New business keywords for the cross-channel layer**: `Read Ddic Table
  Fields` and `Get Se16 Selection Criteria` (`SapEccLibrary`, DD03L read
  through the shared SE16 result reader), `Probe Odata Entity Sets`
  (`SapApiLibrary`, the **tolerant** probe that records HTTP status and OData
  code per entity set instead of stopping at the first refusal; the
  all-or-nothing behaviour of `Read Business Entities In One Roundtrip` is
  untouched, it remains the right one for data preparation), and the business
  vocabulary in `resources/cross_channel_keywords.resource`, which carries the
  entity set to table mapping.
- **`Api Base Url Should Be Provided`** (`resources/api_keywords.resource`),
  the symmetric guard of `Api Credentials Should Be Provided`. A missing base
  URL did not fail on open: it failed much later, on the first call, as
  `ValueError: unknown url type: '/sap/opu/odata/...'`. That message names
  neither the cause nor the remedy, and it points at a perfectly correct path,
  which sends the reader looking in the wrong place.

- **The IDP login is now proven against a real SAP IAS tenant**
  (`tests/robot/ui/fiori/authentification_ias_live.robot`, live 5/5). The
  fixture suite stays as the CI one: it needs no credentials and will outlive
  the 90 days of a trial. The live suite proves what no fixture can: the real
  redirect to the tenant's `/oauth2/authorize`, the `sap-ias` preset's
  selectors matching an authentic form (which serves one page where the fixture
  imitates two steps), and landing on a real cFLP shell.
  Two failure paths are told apart on purpose, because they are two different
  steps of the same form and nothing guarantees they look alike: an **unknown
  identity** is refused at identification, a **wrong password** at
  authentication. The second one runs against a **dedicated test account**,
  never the working one: an IAS locks a user after a few failed attempts, and
  the working account is the one that owns the trial, the site and the admin
  console. Proving an error path must not damage the environment. Result: the
  library was right, it reports "still on the IDP form" for both, and we now
  know it instead of assuming it.
  Also measured, and it cost two iterations: on a cFLP, `Wait For UI5 Ready`
  can be satisfied while the shell has built **zero** controls. The runtime is
  loaded, nothing is busy, and the page is empty. A fixture renders in one go
  and never shows that intermediate state.
- **The launchpad's application frame is found without knowing its generated
  id** (`Get Ui5 App Frame`, `Push Ui5 App Frame`). First time the project ever
  drove a **real cFLP**: a SAP Build Work Zone site on a BTP trial, with the new
  shell bar. The whole chain worked on the first attempt, including login
  through a genuine SAP IAS tenant with the `sap-ias` preset, which had only
  ever seen a two-step fixture while the real tenant serves a single page. What
  did not work was our own documentation: `Set Ui5 Frame` offered
  `iframe[id*="application"]` as its example, and no iframe of that launchpad
  carries such an id. The application frame gets a **generated** UI5 id whose
  counter moves between runs, measured on three consecutive runs of the same
  app: `__container1`, then `__container4`, then `__container3`. The new
  keyword designates the frame by what it IS (visible, loading a document,
  occupying the shell's content area) and returns a positional
  `iframe >> nth=N`; the selection logic is pure and unit-tested off-browser.
  Two findings kept alongside: the new Work Zone shell bar is built on **Web
  Components** (the `wc` engine, written for SuccessFactors pages with no UI5
  runtime, turns out to serve SAP's future launchpad), and the app iframe is
  created **after** `Open App By Intent` returns, so an immediate perception
  sees the shell alone and reports no frames.
- **A credential can no longer get a committed default value** (convention 11,
  `tests/unit/test_no_hardcoded_credentials.py`). In `resources/`,
  `tests/robot/` and `variables/`, any variable whose name carries
  `PASSWORD`/`PWD`/`SECRET`/`TOKEN`/`KEY` must keep `${EMPTY}`; exceptions are
  declared with their reason, and a test removes dead ones. It exists because
  the leak scanner of `export_public_tree.py` is a **blocklist of known
  strings**: it stops what it was taught to recognise and would not see an
  unknown API key crossing to the public repository. The realistic failure is
  convenience, not malice: pasting a key into a resource for one run and
  forgetting it. Two counter-proofs show the guard bites, on the lesson that
  a guard whose failure was never witnessed is not a guard.

### Fixed
- **The injected `__SAPFX` bundle is replaceable within the life of a page.**
  Its guard used to read « already present », so the first bundle a page
  received was kept **for ever** and every later version was ignored in silence.
  Field symptom, paid live on 2026-08-24: after hot swapping the library inside
  a running rf-mcp server (module reload, `__class__` swap, `Reload Library`),
  the new keywords are visible on the Robot side but the call comes out as
  `window.__SAPFX.<x> is not a function`, a message that accuses the keyword
  when the culprit is the injection cache, and only a page reload repaired it.
  The bundle now carries a **version derived from its own content** (a short
  fingerprint computed in Python), and the guard reads « present AND of the same
  version »: the ordinary case, at every keyword call, still installs nothing.
  The real risk of that change is what a reinstall does to the hooks placed at
  injection time (the `fetch`/`XMLHttpRequest` instrumentation of
  `Wait For Ui5 Idle`, the `MessageToast` capture): reinstalling them would
  DOUBLE them (every request counted twice, so a page never « idle »), dropping
  them would LOSE them (a page always idle, which is worse: the wait returns too
  early and the failure lands elsewhere). The mutable state therefore lives on
  the window and each wrapper carries its mark, so a reinstall neither stacks
  nor forgets; the toast hook is marked by its RECEPTACLE rather than a boolean,
  so a hook left by an older bundle cannot go on filling an orphan list.
  `Ui5 Runtime Is Present` still injects nothing (an observation must not modify
  the page).
- **A grid locator now addresses the control, not the screen layout**
  (`_grid.py`). On a modern ABAP release the ALV output is wrapped in one or
  more `GuiSplitterShell`, so the historical path
  `cntlGRID1/shellcont/shell` lands on a container and every grid read fails
  with `no ColumnOrder` or `<unknown>.rowCount`. The wrapping depth **varies by
  transaction** (one level in SE16, two in SM50, which adds an HTML header
  pane), so no fixed suffix could be appended: the library now descends to the
  first descendant carrying `ColumnOrder`, breadth-first and depth-bounded. The
  descent is logged as a WARNING, never silent, on the same principle as
  locator healing.
  The vendored upstream primitives (`Get Row Count`, `Get Cell Value`, `Set
  Cell Value`, `Click Toolbar Button`, `Select Table Row`) call `findById`
  directly and therefore bypassed that choke point, which a first pass missed:
  they are overridden in the mixin, one line each, leaving the vendored file
  untouched (convention 4). Resolution is a no-op when the locator already
  carries the grid, measured: not one descent warning on the reference 1909
  system. Found by running the repo's own suites against a **second live
  system**, which is exactly what a single target could never reveal:
  `ecc_smoke` and `ecc_data_smoke` are now green on both releases.
  A locator failure had been masquerading as a business diagnosis: the
  "does demo data exist" guard reported missing data on a system where the
  data was present, because its check goes through a grid read.
- **A response compressed by the server is now decompressed** (`gzip` and
  `deflate`, on every body the API channel reads: payloads, error excerpts,
  preflight probes, token endpoint). Found live on the SAP Business
  Accelerator Hub sandbox, which serves its `$metadata` with
  `Content-Encoding: gzip` although the client sends **no** `Accept-Encoding`
  at all. The failure blamed the wrong layer: the compressed bytes reached the
  XML parser, which reported `not well-formed (invalid token): line 1,
  column 0`, an error that accuses the document while the transport is at
  fault, and that sends you reading a perfectly valid `$metadata`. JSON reads
  passed throughout, because that server compresses only the XML path, so the
  gap stayed invisible on two live targets out of three. An encoding we cannot
  undo leaves the body untouched rather than raising: the layer above still
  names status, URL and excerpt.
- **The Libdoc freshness guard now watches content, not only the version
  number** (`tests/unit/test_libdoc_pages_fresh.py`). It compared the version
  embedded in each page against `pyproject.toml`, so it only bit on a bump:
  between two releases, an added or removed keyword left the published pages
  incomplete with nothing to announce it. Found by looking rather than by the
  guard: three keywords were missing and four signatures had changed (the
  `per_resolution` option) since the previous release, every guard green. The
  new check compares the keyword NAMES of each committed spec against what the
  library actually exposes, and it was counter-proved against the stale spec
  before being kept. The pages and specs are regenerated accordingly (121 / 53
  / 33 keywords).
- **A write capability declared is not a write capability permitted**
  (`write_simulation_candidates`). The guard counted the **presence** of a
  `sap:` annotation, not its **value**, so an entity set declaring
  `sap:creatable="false"` and `sap:deletable="false"` while staying silent on
  `updatable` was reported as backed by the service, when the only verb it
  allowed came from that silence. `evidence` is now derived from
  `declared_allowed` (allowed **and** declared), so a verb only counts when it
  is explicitly permitted. On the measured target this leaves zero candidates
  instead of two that nothing supported. Same failure class, caught twice in
  the same pass: an earlier version placed the guard at **service** level,
  which a service declaring a restriction on one entity set while staying
  silent on four others would have passed, green and wrong.
- **Per-geometry visual baselines (`per_resolution=True`)** on the three
  snapshot assertions, `Screen Should Match Baseline` and `Element Should
  Match Baseline` (ECC) and `Ui5 Screen Should Match Baseline` (Fiori). A
  perceptual hash encodes the **capture geometry** as much as the content, so
  the same unchanged screen rendered at 1920x1032 and then at 4676x2454 drifts
  by several bits: a baseline was implicitly tied to one machine, and the only
  answers on offer were "pick a reference workstation" or "stop asserting".
  With the option on, each geometry keeps its own committed reference,
  `<name>@1920x1032.png`, created on that machine's first pass exactly like any
  first pass. Drift detection is unchanged at constant geometry, which the unit
  tests pin: a variant is a separate reference, never an amnesty. An already
  committed `<name>.png` stays in use as long as its geometry matches, so
  nothing has to be regenerated or renamed. Masking gains from it too: a mask
  is a pixel rectangle, and it only means anything at constant geometry.

- **The drift sentinel follows, split along the honest line**
  (`Check Screen Against Watch`, `per_resolution=True`, on by default in
  `tests/robot/ecc_drift_sentinel.robot`): a screen signature does not depend
  on the display resolution and a perceptual fingerprint does, so the
  structural reference stays shared while the visual ones (`.dhash.txt`,
  `.tiles.txt`) become per geometry. A workstation whose geometry has no
  visual reference yet registers one and compares the structural channel that
  pass, instead of reporting a drift that is only a change of scale. The
  `.dhash.txt` now carries its own geometry, older references without it stay
  readable and keep working, and the `.tiles.txt` header already recorded it,
  which is what lets an already committed reference be recognized as valid
  here. Live against A4H: the committed references were reused, no variant
  created, SE16 and SE38 unchanged.

### Changed
- **Convention #13 (no code file beyond 500 lines) enforced, and the initial
  debt settled in one remaster pass** (23 files, 2026-08-25). Every split
  follows a seam the repo already used, never a cut at line 500; every facade
  keeps the historic import surface, so nothing changes for consumers:
  - ECC mixins: `_grid.py` hands the classic dynpro **table controls** to
    `_table_control.py`; `_perception.py` hands screenshots, visual assertions
    and the drift sentinel to `_screenshots.py` / `_visual.py` / `_watch.py`;
    `_ddic.py` hands the SE16 SCREEN primitives (`Reach Se16 Selection
    Screen`, `Fill Multiple Selection`, criteria map, result reader) to
    `_se16.py`. The `SapEccLibrary` MRO grows accordingly, keyword set
    unchanged (`robot --dryrun` 221/221).
  - `SapFioriLibrary` becomes a mixin package (`keywords/`: `_base`,
    `_frames`, `_locators`, `_engines`, `_composition`, `_actions`, `_state`,
    `_perception`, `_flp`), mirroring the ECC layout; a dead module constant
    (`_INTERACTABLE`, unused since the fill logic moved into the JS bundle)
    was removed on the way.
  - `SapApiLibrary` splits into `_http.py` (session state, same-origin
    redirect guard, body decompression), `_core.py` (`_ApiCore`:
    URL/errors/CSRF/OAuth2 plumbing shared by all mixins), `_odata_read.py`,
    `_odata_write.py`, `_discovery.py` and `_rfc.py`.
  - The injected JS templates split into chapters (`_ui5_bundle_*.js.tpl`,
    `_ui5_spy_*.js.tpl`) concatenated byte-identically by `_ui5_js.py`: same
    assembled content, same bundle version, generated recorder files
    untouched.
  - The desktop recorder splits into `recorder_com/_capture/_poll/_native/`
    `_native_loop/_replay.py` behind the `sapgui_recorder.py` facade (still
    loadable by path as a Robot library); `recorder_exports.py` becomes a
    facade over `recorder_exports_core/_robot/_docs/_report.py`; the GUI's
    pure logic moves to `recorder_gui_logic.py`.
  - `sapfx_common.semantic` keeps its public API and moves the geometric
    building blocks to `_semantic_match.py`; `sapfx_common.cross_channel`
    keeps its `__all__` (the Robot keyword surface) and moves the halves to
    `_cross_channel_contract.py` / `_cross_channel_artifact.py`;
    `export_public_tree.py` moves its declarative rules (scope, transforms,
    leak patterns) to `scripts/_export_rules.py`, excluded from the public
    export like the engine itself.
  - The ten oversized test files split by theme, shared fakes extracted into
    `_*_fixtures.py` modules; same collected count (1544), coverage
    unchanged (94% src, 74% recorders).
  The rule is now held mechanically by **`scripts/check_file_length.py`**
  (CI + `PostToolUse` hook on every edited code file + a unit test scanning
  the real tree): exact-count allowlist as the only escape hatch, empty.
  Two downstream effects of a layout change, both caught by running the whole
  publication chain rather than the tests alone: a leftover `build/` directory
  made setuptools ship the two DELETED templates inside the wheel (purge it
  before building, and diff the wheel against `src/`), and stating the rule
  meant naming the private communication directory in its exemptions, which
  the public export's leak scan refuses. `scripts/_export_rules.py` now
  handles both mirrors the way it already handled their em-dash sentences (a
  transform: the public tree must not describe a directory it does not have)
  and allowlists the three guard files the way `check_bilingual_docs.py`
  already was (an exemption prefix left without an object is harmless).
- **A visual failure whose two geometries differ now says so**, with or
  without the option: the message names the baseline geometry, the capture
  geometry, the fact that the drift may be scale alone (the structural channel
  would not have moved), the `per_resolution=True` remedy and the geometries
  already known for that name. This is the diagnosis that cost time during the
  0.6.7 test pass, spent in the failure message rather than in a memory entry.
  The Robot log also names the geometry a baseline was created at or matched
  on, so a reference says which workstation it is worth for.

## [0.6.7] - 2026-08-19

### Added
- **`Get Ui5 Application State` (SapFioriLibrary)**: the web channel's "where
  am I" in a single call, frame scope plus UI5 runtime plus messages, probing
  before it reads. It is assembled in the library because through rf-mcp the
  cost is the Robot Framework context crossing, not the JavaScript: the MCP
  state provider, which serves this section on every agent turn, now pays one
  round trip instead of three.
- **`Ui5 Runtime Is Present` (SapFioriLibrary)**: the probe to run before any
  keyword that requires a UI5 runtime. It answers True/False and never fails,
  and it is the only web expression in the repo that does **not** inject the
  `__SAPFX` bundle, so it does not instrument the application's `fetch` /
  `XMLHttpRequest` just to look at it. Pages driven by the `wc`, `sid` and
  `dom` engines are supported targets, not failures, and this is how a caller
  tells them apart cheaply.
- **`resources/api_keywords.resource`**: the business-readable layer of the API
  channel, third mirror of the ECC and Fiori resources (`Open Api Channel`,
  `Count Business Entities`, `Read Business Entities`, `Create Test Entity`,
  `Remove Created Test Data`, plus the preflight and perception keywords). It
  carries the OData service paths under business names, so a suite never spells
  one out, exactly as SAP ids live in `ecc_keywords.resource`.
- **`tests/robot/api/canal_api_odata.robot`**: the API channel finally has a
  suite of its own. It was only ever exercised indirectly, by the two
  cross-paradigm suites and through a single read keyword each, while the
  library exposes 32 public keywords: the two defects fixed below lived in
  precisely that blind spot. The suite runs the same business keywords against
  two protocols and two systems, OData v2 (tag `a4h`) and OData v4 (tag
  `capsflight`), which is the property worth testing. Live: 12/12. It also
  ships in the Windows pack, which now carries seven sample suites instead of
  six: `resources/api_keywords.resource` was being delivered without a single
  suite exercising it, so the pack held a business layer that nothing
  demonstrated and that its own dry run never resolved. The pack dry run goes
  from 27 to 39.

### Fixed
- **A `$filter` containing spaces no longer fails against an OData v4
  service.** Query parameters were encoded the HTML-form way
  (`application/x-www-form-urlencoded`), so a space became `+`. A SAP Gateway
  tolerates it, a CAP v4 service rejects it outright with
  `400 Expected "(", "/", or a whitespace but "+" found`, and a `$filter`
  always contains spaces (`TravelID eq 1`), so all v4 filtering was inoperative.
  Spaces are now percent-encoded; the fix is deliberately limited to that one
  character, so everything already served to Gateways in production is
  unchanged, and a unit test pins that exact equivalence. The old behaviour was
  itself pinned by a unit test asserting `%24filter=Price+gt+1`, which is why
  CI could not see it.
- **The data factory now deletes what it tracked on an OData v4 service.** The
  URI a server announces (`Location`, `@odata.id`, `__metadata.uri`) may be
  relative to the **service**: CAP answers `Location: Travel.drafts('...')`.
  Resolved against the session base URL it lost its service prefix, so the
  delete hit the root, returned 404 and left the data behind, while the
  `$count` of active entities looked restored. A relative URI is now resolved
  against the request URL, as RFC 3986 requires and as the pagination path
  already did. When a server announces a URI that is not addressable at all,
  the warning names `Register Created Entity` as the way out instead of leaving
  the caller to guess.
- **The flagship suite's `capsflight` lane runs again.** It opened its OData
  session with no credentials while the cds mocked-auth also guards the
  service, so the lane died on HTTP 401 before reaching its assertion, which in
  turn hid the two defects above. It also read the Travel ID as "the first
  entirely numeric cell", an assumption the rendered page breaks twice over:
  the identification column concatenates label and identifier, and the
  identifier is formatted with a locale-dependent thousands separator. The
  identifier is now read as the digits following the label, which is the same
  in every language (convention 3).
- **A missing state section no longer reaches the agent as a plain "OK".**
  rf-mcp substitutes the literal string `"OK"` for a keyword that returns
  `None`, so the "empty output" guard in the RF bridge was unreachable and the
  section was served as if it held a value. The bridge now reads `result` as
  authoritative and neutralises that sentinel; the unit test that covered it
  asserted a response shape rf-mcp never emits.
- **The Fiori application state stopped reporting supported pages as broken.**
  It called `Get Ui5 Messages` unconditionally, and that keyword fails hard
  outside a UI5 runtime, so every `sapfx_state` turn on a Web Components,
  WebGUI or hybrid page carried a permanent collection error, plus a wasted
  round trip. The runtime is probed first; the section is then reported as
  `not_applicable`, a key kept distinct from `collection_errors` so the error
  signal stays worth reading. As a side effect, a pure state read no longer
  installs the network instrumentation into the application under test.
- **One state contract across the three channels.** ECC, Fiori and API each
  reported failure in their own vocabulary, so a consumer had to special-case
  the payload per library to learn whether a section was missing or the channel
  was down. All three now serve `connected`, plus `state_error` when the
  channel does not answer, and share one epilogue (`finalize_state`) instead of
  seven hand-copied ones, one of which was already forgotten on an early-return
  path.
- **The API channel really uses the shared best-effort helper.** The extraction
  that was supposed to unify the three providers had left its copy inline, and
  the guard could not see it: it grepped for the name of the removed helper
  rather than checking the behaviour. The guard now drives each provider
  through a failing RF context and checks the contract it claims to protect.
- **The capability declaration is honoured, not decorative.** `sapfx_state`
  called both provider methods regardless of `supports_page_source` /
  `supports_application_state`, so the flags could be wrong for a whole release
  without a symptom. A section a library declares it does not serve is now
  refused explicitly, with that provider's own reason.
- **`SAPFX_MCP_FORCE=0` no longer activates the escape hatch.** It was a bare
  truthiness test, so the values an operator writes to mean "never bypass the
  compatibility guard" started the server in degraded mode.
- **The entry-point path is no longer unguarded.** The compatibility refusal
  only runs under the `sapfx-mcp` overlay, while the plugins also load into a
  stock `robotmcp` server (the pack installer falls back to it). That path now
  emits a non-blocking version warning; it cannot probe the anchors, since
  importing `robotmcp.server` from a plugin that server is loading would be
  circular.
- **The ECC intent map covers the DDIC keywords it advertises.** Six of ten
  were routed, without `Reach Se16 Selection Screen`, the one that opens an
  SE16 selection screen in a single place (status type E, wide-table field
  popup, generation dialog). Unrouted, an agent re-improvises exactly the
  divergent copies that keyword removed. A new guard checks the map in the
  direction that was missing, library towards map, which is where omissions
  live: the previous one could only catch a typo.
- **`CoInitialize` is no longer called on the channels that have no COM.** The
  shared helper applied the ECC guard to Fiori (CDP) and API (HTTP), entering
  every fresh thread-pool worker into an STA apartment, never balanced by a
  `CoUninitialize`.
- **`integrations/robotmcp/NOTICE` no longer breaks the public export.** The
  committed licence copy carries the author's name, which the leak scan allows
  by exact path only, so the release-day export would have aborted on a leak
  that is not one. Duplicating a licence file duplicates its allowlist
  obligation: the copies are now declared in one place and a unit guard runs
  the real scanner over them.
- **The Windows pack no longer ships the studio's private comms skill.**
  `build_release_pack.py` copied `.claude/skills` wholesale, so a skill that
  `export_public_tree.py` had always excluded by name travelled inside the
  released `sapfx-pack-0.6.6-win.zip`. Two distribution channels existed and
  the private boundary was held by only one. Skills now enter the pack by
  **whitelist** (`.claude/skills/sapfx`), and a unit guard makes the boundary
  symmetric: no path in the pack manifest may sit in the public export's
  `EXCLUDE_PREFIXES`. That skill's links point at `comms/`, which the pack does
  not carry, so it was dead weight there as well.
- **The pack's CONTENT is scanned for leaks too, in CI.** The guard above
  reasons about paths and would miss a secret written INSIDE an otherwise
  legitimate file. The public export does scan bytes, but only by hand, once per
  release, over `git archive HEAD`: the ZIP could be built, tested and published
  before the project's only content scan had ever run. It now runs over the pack
  manifest on every push. Measured: 5 forbidden hits on the shipped 0.6.6 ZIP,
  none on the fixed pack, so it would have stopped the leak at build time.
- **Shipped agent definitions no longer invoke scripts the pack does not
  carry.** sap-generator's definition runs `scripts/check_conventions.py` as its
  convention #1 gate and `/sap-eval-healer` runs `scripts/agent_eval_harness.py`;
  neither was in the manifest, so a deployed pack silently lost the gate and
  offered a dead command. `check_conventions.py` (plus its `_common.py` base) is
  now shipped and verified to run from the pack root; `/sap-eval-healer` is
  excluded instead, being a studio regression net aimed at a resource and a
  suite that the pack does not contain. A guard now checks both directions.
- **The `sap_robotmcp` wheel ships its licence.** It declared Apache-2.0 while
  carrying no licence text at all (verified on the wheel inside the 0.6.6 pack):
  setuptools looks for licence files in the **project** directory, and
  `integrations/robotmcp/` had none. It now holds committed copies of `LICENSE`
  and `NOTICE`, kept byte-identical to the root ones by a unit guard, which is
  what article 4 of the licence requires when redistributing.
- **`install.ps1` fails with its own diagnosis again** when `wheels\` is
  missing: under `$ErrorActionPreference = "Stop"`, `Get-ChildItem` aborted
  before the explicit `Fail` message underneath it. The `robotmcp.exe` fallback
  also stopped rendering an MCP config pointing at a non-existent executable.

### Added
- **The deployment pack verifies its own integrity and the host Python.**
  `SHA256SUMS.txt` was shipped and checked by nobody: `install.ps1` now verifies
  every listed file, treats a missing or altered `wheels/*.whl` as blocking and
  a locally adapted example suite as informational (all three paths exercised
  against a really extracted pack). It also refuses a host interpreter below
  Python 3.10, the floor both pack READMEs promise and the one the pinned Pillow
  and robotframework-browser require, instead of failing later inside pip. A
  leftover `.mcp.json` from a previous `-WithMcp` run is now reported.
- **CI qualifies the pack on the Python floor** (`pack-floor`: the real ZIP,
  installed by the real installer on 3.10, without Chromium or MCP, then a
  keyword-resolution dry run). The claim existed since the first pack and was
  only ever exercised on 3.12. `release-pack` is now gated on `dryrun` too, so
  no ZIP is built, published and attested over a red real-pywin32 suite.
- **`tests/unit/test_dependency_pins.py`**, the dependency-side counterpart of
  the version guard: the `pywin32` pin stays identical across its three
  environment files and above the package floor (convention #6 was stated, not
  enforced), the `robotframework-browser` bound stays identical across its three
  declarations, and the `robotframework-sapfx` floor of the plugin wheel must
  track the current version, since the plugins' keyword maps are versioned in
  lock-step and pip must never pair a newer plugin with an older library.

### Changed
- **Both distributions declare their licence the PEP 639 way**
  (`license = "Apache-2.0"` plus `license-files`, `setuptools>=77`), dropping
  `license = { text = ... }` and the `License :: OSI Approved` classifier: both
  are deprecated, mutually exclusive with an expression, and left the project
  waiting on whichever setuptools release removes them. Wheels now carry
  `Metadata-Version: 2.4` and `License-Expression: Apache-2.0`.
- **`packaging/constraints-deploy.txt` names its pack the guarded way.** Its
  header carried a hand-written `0.6.6`; the file is scanned by
  `check_published_versions.py`, but no pattern matches free prose. Written as
  the pack filename, the version can no longer go stale unnoticed.
- **The upper-bound policy is written down** in `pyproject.toml`: a bound is
  added only where a major would break SILENTLY (the `web` extra), which is why
  `robotframework` keeps an open range while the qualified version lives in the
  pack constraints.
- **Every wait now measures its deadline on the monotonic clock.**
  `sapfx_common.polling` (the shared primitive behind every `Wait Until ...`
  of both channels) computed its deadlines with `time.time()`: an NTP
  resynchronization or a clock change during a wait stretched or shortened the
  real budget. `retry_call`'s optional `deadline` argument therefore moves from
  an epoch reference to a `time.monotonic()` one (no caller in the repo passed
  it).
- **`robotframework-browser` is now bounded to `<21`** in the `web` extra and
  both requirement files. `SapFioriLibrary` imports INTERNAL Browser paths
  (`Browser.utils.data_types`: `ScreenshotReturnType`, `ElementState`) because
  a direct Python call through `get_library_instance` bypasses Robot's argument
  conversion; on `ImportError` the fallback passes the state back as a string,
  exactly the case that produced the `KeyError` caught live on the hybrid
  smoke. A major bump would therefore not break at import, it would silently
  reintroduce the bug: it has to be qualified.
- **`sap-robotmcp` declares its dependency on `robotframework-sapfx`.** The
  plugins and the RF context import `sapfx_common` at module level, so the
  dependency was real but only written in a comment; the Windows pack installs
  both wheels, which hid the gap from every other installation route.
- **mypy now covers everything that ships** (`files = ["src", ...]`, only
  `_vendor/` excluded, convention 4) instead of a hand-picked list. The
  progressive typing had in fact reached the whole tree, and the four packages
  ship a `py.typed` marker: what is published as typed is now verified. The
  scope was extended again on 2026-08-19 to `tools/recorder` and
  `tools/recorder_web`: they ship in the Windows pack, and they passed as they
  were (zero error). The recorders also get their own coverage floor in CI
  (`--cov=tools/recorder --cov-fail-under=70`, measured 74 %), kept separate
  from the product gate so the published coverage figure keeps its meaning.
- **`requirements.txt` carries the documented toolchain** (`mypy`,
  `pytest-cov`, `pre-commit`, `Pillow`), so the commands in CLAUDE.md all run
  after a plain `pip install -r requirements.txt`.
- **`Fill Multiple Selection` handles a scrollbar that caps.** Like every
  GuiTableControl, the SAPLALDB dialog's scrollbar tops out
  (`sapfx_common.table_control.window_plan`, learned live on SE11): the last
  window then OVERLAPS the previous one. The reached position is read back and
  the remaining values are written from the shifted local index instead of
  failing, which is what the pure helper already knew how to compute. A scroll
  that still leaves those values outside the visible window remains an
  actionable failure: replaying the same visible rows would corrupt the
  selection silently.
- **ECC: a missing-element error now names the screen you are actually on.**
  `Cannot find element with id 'wnd[0]/tbar[1]/btn[31]'` cannot tell a stale
  locator from an element not yet materialized from the screen simply not
  being the one you think, and that third cause is the frequent one in ECC (a
  transaction refusing an entry stays on the previous screen). `Element Should
  Be Present` and `Get Element Type` (the path `Click Element` takes to resolve
  a type before acting) now append a `# screen <Program>/<Transaction>/<Number>`
  line to the failure, **and so does the wait layer** (`Wait Until Element
  Present`'s timeout, `_find`'s lookup error): waiting is the dominant absence
  path in suites (convention 2 says wait, never sleep), so leaving it out kept
  the founding case (a modal open, the selection screen never displayed)
  reporting a bare timeout. Upstream behaviour is otherwise unchanged, an
  explicit caller-supplied `message` is left untouched, and the enrichment is
  best-effort: it never masks the original error.
- **Fiori engine `role`: substring matching now normalizes whitespace on both
  sides.** The `wc` and `dom` engines already collapsed whitespace in their
  haystack; `matchProps` compared the RAW UI5 property value. Since a Robot
  cell can carry neither a newline nor a run of 2+ spaces, every recorded
  selector is normalized, so a control whose `text` is `Total:\n  42` could
  never be matched by the selector the recorder had just emitted for it. The
  regex form (`/…/`) still sees the raw value, so patterns over `\s` and `\n`
  keep working.

### Added
- **DDIC inventory channel (ECC): classify a batch of dictionary objects in
  one call.** New `DdicKeywords` mixin (`SapEccLibrary/keywords/_ddic.py`):
  `Classify Ddic Objects` reads DD02L through SE16 with the multiple-selection
  dialog batched to its visible window (`TABCLASS` is read from the OUTPUT
  grid, it is not a selection criterion; an object unknown to DD02L is flagged,
  never mistaken for an empty table), `Fill Multiple Selection` loads a list of
  values into any selection-screen criterion (standard SAPLALDB dialog,
  SCROLLED window by window beyond the visible rows, with the reached scroll
  position read back: a capped scroll writes at the shifted local index, a
  scroll that leaves values outside the window fails actionably, and no row is
  ever silently rewritten),
  `Get Ddic Classification Map` builds the normalization map from the TABCLASS
  domain values read live on the target (APPEND stays `unknown` until a target
  proves otherwise), `Validate Ddic Scope` refuses an unbounded campaign,
  `Record Ddic Probe` stores locale-independent SE16 probe results and
  `Write Ddic Inventory Artifact` emits a deterministic sorted JSON artifact
  whose SHA-256 excludes the timestamp. Pure logic (scope validation, bounded
  union, classification, artifact assembly, hash, two-target comparison with
  scope-compatibility gate, Markdown report) lives in
  `sapfx_common/ddic_inventory.py`, fully unit-tested off SAP, and reachable
  from Robot through keyword wrappers rather than `Evaluate __import__(...)`
  incantations (`Sample Ddic Objects For Probe`, `Merge Ddic Name Lists`,
  `Compare Ddic Inventory Artifacts`).
  Three safeguards keep a campaign from being green and wrong: the DD02L
  result read distinguishes "no matching row" (selection screen kept) from
  "no grid at all" (the Data Browser left in classic list mode, an error
  naming `Use ALV Grid In Data Browser`) instead of reporting every object as
  absent; a read that reaches its row cap fails rather than truncating
  silently; and a batch that comes back EMPTY triggers a canary probe
  (`TABNAME=DD02L`, the table describing itself) that tells a genuine absence
  from positional criteria displaced by the per-user selection-field choice.
  The grid read is also restricted to the four technical columns actually
  consumed, which keys the rows by field name (independent of the user's ALV
  heading preference, where displayed titles are not the technical ids) and
  cuts roughly 90% of the COM calls per batch.
  `List Repository Tables` (resource layer) gains an `object_type` parameter
  (default `TABL`; `VIEW` makes views discoverable, they were silently
  invisible before) and `Discover DDIC Objects By Scope` composes the bounded,
  deduplicated union of a validated scope. Generated campaign suite
  `tests/robot/ui/ecc/inventaire_tables_ddic.robot` (spec
  `specs/inventaire-tables-ecc-s4hana.md`), validated live twice vs A4H
  (7/7, identical summaries: 99 objects, 68 tables, 16 views, 15 structures,
  0 unknown). Live finding recorded in the spec: projection views
  (`EPM_V_BP_CUST`) are rejected by SE16 with a type `E` message exactly like
  structures, so a type `E` rejection alone never classifies an object.

### Fixed
- **The post-edit hook no longer crashes on its own message.** Reported by a
  code review of `scripts/` and its dependencies (2026-08-19). On Windows,
  Python opens the standard streams in the machine's code page: the arrow in
  `hook_guards.py`'s informational message (spec/suite drift) raised
  `UnicodeEncodeError` on `stdout`, so the ONE branch designed to inform
  without blocking was the one that died, and a relayed guard report reached
  the assistant as mojibake on `stderr` (whose errors default to
  `backslashreplace`, hence no crash but `→` in place of the character to
  fix). Both streams are now switched to UTF-8, through the new shared
  `scripts/_common.py`. Guards used to disagree on this: four forced their
  `stdout`, ten did not, so CI logs and any programmatic consumer got a mix of
  two encodings. `hook_guards.py`, the only script in `scripts/` without a
  unit test, now has one: its decision moved to a `decide()` function
  separated from I/O, which makes its four branches testable without a
  throwaway repo or a genuinely red guard.
- **`check_no_em_dash.py <directory>` no longer reports a false green.** A
  directory passed as an argument was accepted, then silently ignored:
  `read_text` raises on it and that error is swallowed like a binary's. The
  guard answered `OK (ciblé)` without having read anything. Directories are
  now expanded recursively, exemptions and out-of-repo paths included.
- **`agent_eval_harness.py verify` now catches ADDED files.** It only re-read
  the manifest recorded at injection time, so a modification or a deletion was
  seen but a creation was not: a healer writing
  `resources/site_keywords.resource`, which is exactly what the agent
  definitions ask for on a deployed pack, would have scored PASS. Run
  artifacts (`__pycache__`, `*.pyc`, `*.actual.png`) are excluded from the
  manifest, since the healer reproduces the failure and therefore runs pytest
  and robot between inject and verify.
- **`build_release_pack.py` refuses wheels from another version.** The check
  was a plain count, and `--skip-wheels` reuses `wheels/` as it stands: a wheel
  from the previous release shipped inside a ZIP named after the current
  version, silently. That is precisely what `check_published_versions.py`
  forbids in the TEXT of published instructions.
- **`export_public_tree.py check_top` is now symmetrical.** It only refused an
  unknown top-level entry; a directory gone from HEAD produced an amputated
  public tree, published without a word, in a script fail-closed everywhere
  else. A unit test also pins `EXPECTED_TOP` against the real HEAD, so the
  divergence surfaces in pytest rather than on release day. `git status` is
  checked for its return code (without it, "clean" was an assumption, not a
  fact), and an old interpreter without `tarfile`'s `filter` argument is
  refused instead of extracting unfiltered.
- **`check_published_versions.py` walks its folders recursively.** The scan
  stopped at the first level, so an instruction filed in a subdirectory
  (`docs/` is flat today, but the public export already creates `docs/libdoc/`)
  left the guard's scope unnoticed.
- Three readings of the project version cohabited, two of which took the first
  `version = "…"` line regardless of section: they now share the section-aware
  one in `_common.py`. `check_bilingual_docs.py` and `check_comms_sync.py` pass
  an explicit `encoding` to their subprocesses like the other guards,
  `check_spec_sync.py` indexes linked specs by relative path rather than by
  file name, and `healing_drift_report.py` attributes a patch to its drift by
  identity instead of by substring.
- **mypy covers the two scripts the pack ships** (`healing_drift_report.py`,
  `check_spec_sync.py`): shipped code is verified code, the very rule that
  brought `tools/recorder*` into scope. They stay self-contained (no import
  from `scripts/`), a property a unit test now enforces, since they must run
  alone from the pack root.
- **`check_comms_sync.py` treats the published test count as a FLOOR.** The
  manifest carries the figure published at release time while the suite keeps
  growing between releases, so requiring equality turned CI red on the first
  test added (caught during the same review: 1254 collected against 1175
  published, an underclaim). Collecting more than the published figure is now
  an informational line, in line with the anti-overclaim rule; collecting less
  still fails, since the comms base would then assert tests that do not exist.
  Coverage stays a strict equality: it is measured on a fixed scope by the CI
  Linux job, so a gap there is a real drift.
- **Recorder: `--replay` no longer exits green after replaying nothing.** A step
  whose keyword does not exist in `SapEccLibrary` was counted as "skipped" and
  the run still ended with `Replay OK`, exit code 0. That is exactly what a
  **resource-first** export produces (all of its steps are business keywords
  living in the imported `.resource`): a green run that proved nothing. Such a
  step now fails the replay, with a message naming the resource-first case and
  pointing at `robot`. A file holding several tests is announced too, since
  only the first one is replayed (`count_test_cases`). Found by code review of
  `tools/`, 2026-08-19.
- **Recorder: steps are split on the REAL Robot separator** (a tab, or two
  spaces and more) instead of exactly four spaces. A hand-edited recording (the
  GUI steps panel invites editing) separated by two spaces or a tab collapsed
  into a single cell, so the replay called nothing; separated by five spaces it
  produced arguments with a leading space, so the replay silently sent a wrong
  value. Intentional spaces inside a value stay protected by their own
  backslash escaping.
- **Recorder GUI: « Arrêter » stops the recorder instead of killing it.** The
  launcher runs the recorder in a SEPARATE console, so it has no Ctrl+C to
  send and used `terminate()`, which skips the loop's `finally`: the pending
  OK-code (`flush_native_state`) was lost, `Session.Record` stayed armed on the
  SAP GUI side (modal F4, drag and drop disabled) and the events stayed
  subscribed. New `--stop-file` sentinel, polled by every interactive loop:
  the loop leaves through its teardown, and the process is only killed if it
  does not answer within five seconds.
- **Recorder GUI: the status line is readable again.** It shared row 5 of the
  grid with the button frame, which Tk stacked on top of it: every message the
  window has to give ("En cours…", "Arrêté.", "Étapes enregistrées dans …")
  was hidden behind the buttons.
- **Recorder: COM events that cannot be transcribed are counted and reported.**
  The event sink swallows everything a handler raises (the bridge must not
  break), but the handler also writes the step file: a lost event vanished
  without a trace. Both native loops now report `N événement(s) NON transcrits`
  with the last error when they stop.
- **Recorder: the pywin32 import fallback defines `com_error`.** The
  `except ImportError` branch reset the five `win32*` modules but left
  `pythoncom` and `com_error` undefined, while dozens of
  `except (AttributeError, com_error)` clauses name them: an exception clause
  is evaluated when the error occurs, so the real error would have been
  replaced by an opaque `NameError`.
- **Recorder: a drive-relative output path is refused for what it is.** On
  Windows `E:file` carries a drive without being absolute; `commonpath` then
  raised a `ValueError` that the CLI displayed as a path-traversal message.
- **Pack: development-only helpers stay out of the Windows pack.** The build
  copied the recorder trees whole, so `gen_icons.py` (which needs Pillow AND
  `assets/logo.png`, absent from the pack), `package.py` (the Chrome Web Store
  zip), the extension's `PUBLISHING.md` store-submission guide (which documents
  only those two) and both scripted video demos (ffmpeg, cap-sflight clone)
  shipped to test machines that cannot run any of them. `PRIVACY.md` still
  ships: it is owed to whoever installs the extension.
- **API: the CSRF token is read case-insensitively.** `_send_with_csrf` looked
  the fetch response header up with two hard-coded spellings
  (`x-csrf-token`, `X-CSRF-Token`) while the module's own `_header()` helper,
  used by the replay judge, is case-insensitive. HTTP headers are
  case-insensitive and `dict(response.headers)` keeps the case the server
  SENT: a relay answering `X-Csrf-Token` silently dropped the token to empty,
  the write went out without it, and the 403 that followed read like a
  permission problem. Found by review, not by a run: the thirteen CSRF tests
  all used the lowercase spelling.
- **API: `sap-client` is no longer appended twice when following pagination.**
  Server-driven next links (`__next` v2, `@odata.nextLink` v4) are built by the
  server and usually carry the original query options, `sap-client` included;
  `_build_url` added it unconditionally, producing
  `sap-client=001&sap-client=001` on every followed page.
- **Fiori: `_page_png` no longer takes a second screenshot on the file
  fallback.** The `except (ImportError, TypeError)` also covered the final
  `bytes(raw)`, so a Browser version returning a PATH despite
  `return_as=bytes` triggered a fresh capture: a different instant of the page
  than the one being described, paid for twice. The returned path is now read
  directly.
- **`ensure_com_initialized` keeps its "never raises" promise.** `except`
  clauses are evaluated when the exception happens, so reading
  `pythoncom.com_error` inside the tuple raised an `AttributeError` from the
  clause itself on a stub that has neither `CoInitialize` nor `com_error`.
- **`SapApiLibrary` exposes `__version__` at package level** like the three
  other packages (`import SapApiLibrary; SapApiLibrary.__version__` raised
  `AttributeError`); the version guard now tracks that file too.
- **Exploratory campaign (A4H): the table sweep survives selection screens
  generated at first access.** After a container re-creation, SE16 GENERATES
  each table's selection screen on first access (`/1BCDWB/DB<table>`, the
  Enter takes ~1 s): "busy done" does not mean the screen is there, and on
  SGEOCITY (FLTP fields) the generation pops a modal info dialog (SAPMSDYP,
  "ABAP Dictionary type FLTP is not allowed for dynpro element") instead of a
  status-bar message. Reaching a SE16 selection screen (status type `E`, the
  wide-table "choose selection fields" popup, the generation message dialog,
  waiting for the generated screen) now lives in ONE library keyword,
  `Reach Se16 Selection Screen`, returning a structured verdict (`reached` /
  `rejected` / `dialog` / `modal`) with the dialog text kept for the log only.
  The resource layer (`Try Open Table Selection Screen`, plus the new
  `Reach Table Selection Screen` for callers that need the full verdict) and
  the autonomous campaign both delegate to it, replacing three divergent
  copies. The sweep now also BOUNDS the `dialog` verdict
  (`${MAX_DIALOG_REJECTS}`, 0 by the live reference): a regression showing up
  as a blocking dialog used to slide from the "real tables" count into the
  `dialog` bucket and leave the sweep green. Robot `IF` conditions on the
  dialog use the expression form (`IF $state["verdict"] == …`) rather than
  interpolating the localized text between quotes, where a single apostrophe
  ("n'est pas autorisé") turned the condition into a SyntaxError. Live: 2/4 to
  4/4; heal session in `docs/heal-journal.md`; lessons in the A4H field notes
  and `memory/se16-ecran-selection-genere-premier-acces.md`.
- **rf-mcp: the Fiori plugin declares the application state it actually
  serves.** Its provider returns the active frame scope and recent UI5
  messages, but `supports_application_state` still said `False` (the `sapfx`
  overlay calls providers directly and never reads the flag, so nothing
  surfaced it). Any consumer honouring the declared capability would have
  skipped that state silently. The best-effort section helper
  (`asyncio.to_thread` + error trace) moves to the shared `_rf_context`
  module, where it was previously copied verbatim into each plugin.
- **Web recorder: selector texts are sanitized before entering a Robot
  Framework cell, without losing their discriminating power.** A page text
  carrying an apostrophe, a backslash, a `${` sequence or a run of 2+ spaces
  used to break the generated line (the `properties={'k': 'v'}` Python
  literal, the `text=`/`name=` cells) or wake up an RF variable at replay.
  Whitespace is now normalized (the engines normalize their target the same
  way), `${` is escaped so it stays literal, and the properties literal picks
  its quote character instead of cutting the text: `Editor's Choice` is
  emitted whole as `properties={'text': "Editor's Choice"}` where truncating
  it to `s Choice` could silently match a DIFFERENT control (role resolution
  takes the first match). The backslash remains the only truncating character
  (Robot consumes it when reading the cell back), and `rfSafeCell` now rejects
  it in xpath cells too. When a selector must still degrade (both quote kinds
  present) or an xpath fallback cannot be carried, the emitted step SAYS SO
  instead of looking discriminating or self-healing: a wrong-target replay in
  silence is worse than a step visibly marked to complete. Locked end to end
  by a unit test that replays the real chain (Robot cell → RF unescape →
  `ast.literal_eval`), the double unescaping that neither a JS grep nor a
  `--dryrun` can see. Recorded VALUES were already escaped (`rfEscape`).
- **API channel: the one-shot CSRF replay is now judged on the response
  header.** Three cases, in order: a header starting with `Required` (a relay
  may decorate it, `Required; expired`) is the SAP protocol's positive signal
  and replays once; a header carrying a real token means the server issued
  one, so the 403 is a genuine denial and is never replayed even when the body
  mentions CSRF; a header that is absent OR blanked by a relay leaves no
  reliable signal and falls back to the response text, because refusing there
  would permanently break a write that used to recover by itself past the
  Gateway CSRF timeout (~30 min). `_RequestError` carries status + headers
  through the internal error path.
- **Recorder documentation exports: secret masking extended.** The
  `password=`/`passwd=` masking that protected the HTML report now also
  covers the raw fall-through lines of the spec and ISTQB exports
  (hand-added `Open Api Session` lines in a mixed recording). Executable
  exports (.robot/.resource) stay faithful: the recorders never emit a real
  password (placeholder by construction).

### Changed
- **`sapfx_state`: the Fiori `application_state` is no longer minimal.** It
  now mirrors the ECC enrichment pattern: the active iframe scope
  (`frame_stack`, the context to know before resolving anything) and the
  recent UI5 messages (type-based, convention #3), each section best-effort
  with `collection_errors`, plus the stale-code warning.
- **`healing_drift_report.propose_patches` documents its whole-line
  behavior**: every occurrence of a drifted locator on the resource line is
  replaced, including an end-of-line comment echo (leaving echoes diverging
  would be worse), locked by a unit test.

### Added
- **Keyword documentation pages (Libdoc), in the public tree.** One reference
  page per published library (`SapEccLibrary`, `SapFioriLibrary`,
  `SapApiLibrary`) plus a home page linking them, in **English** while the
  docstrings stay French: the translation lives in an intermediate Libdoc JSON
  spec, and the pages are rebuilt from it, so `src/` is never touched for the
  published documentation. The four pages and the two images they embed ship
  in the public repository under `docs/libdoc/` and feed the rendered
  GitHub Pages site. Two guards: the pages must match the project version (a
  release cannot ship documentation that lies about the product), and they
  must carry **no machine path** (Libdoc engraves an absolute `source` per
  keyword; it is relativized to `src/…` in the spec before the rebuild, which
  the public export's leak scan would otherwise refuse).
- **`pages` workflow**: the documentation pages are served on GitHub Pages from
  `docs/libdoc/`, deployed as an artifact rather than through a `gh-pages`
  branch. Nothing to copy by hand at each release, and the fresh `main` history
  an export-per-release produces cannot carry the site away. A missing page
  fails the run instead of publishing an amputated site. Both READMEs link the
  site, and `[project.urls]` gained a `Documentation` entry, which PyPI shows
  in the project sidebar (effective at the next release, like all PyPI
  metadata).
- **`check_published_versions.py`**: no published instruction may cite a stale
  SAPFX version. It scans the files a user reads to ACT (READMEs, `docs/`,
  `packaging/`) for artifacts they will look for or type (pack filename,
  `robotframework-sapfx==X.Y.Z`, wheel names) and refuses a **static** version
  badge where the dynamic shields.io badge updates itself. Third-party
  versions (rf-mcp, fastmcp, Docker, UI5) and history files (CHANGELOG,
  CLAUDE.md, `memory/`, heal-journal) are out of scope on purpose: a guard
  that cries wolf gets disabled. Wired into CI and the `PostToolUse` hook,
  20 unit tests.
- **`pypi-publish` accepts a `post` input** on manual dispatch: a published
  PyPI version's files are immutable, so correcting the page means
  republishing the same code as `X.Y.Z.postN`. The suffix is applied to
  `pyproject.toml` for the build only, so the repository never carries a
  divergent version (module `__version__` stays `X.Y.Z`).

### Changed
- **Discovery metadata.** The PyPI distribution carried six keywords from the
  SAP GUI era (`robotframework, sap, sapgui, ecc, s4hana, test-automation`),
  naming neither the Fiori channel nor the API one nor the AI agents: 22
  keywords now cover the three channels (fiori, sapui5, ui5, playwright,
  odata, rfc, bapi, api-testing, self-healing, mcp, ai-agents), and the
  classifiers gained the audience, the testing topics and the Python versions
  the CI actually verifies (3.10 to 3.14). The OS classifier deliberately
  stays Windows: that is the SAP GUI channel's real constraint, and only what
  is validated gets declared. **PyPI metadata is frozen per release**, like
  the README, so these appear on the page at the next release.
- **The READMEs now say what ships where.** `pip install robotframework-sapfx`
  delivers the libraries and their keywords; the recorders, the rf-mcp
  integration, the test agents and the business resources carry a **(pack)**
  tag because they ship with the repository and the Windows deployment pack.
  Previously the feature sections listed everything undifferentiated and the
  Install section clarified it a hundred lines below, which was misleading on
  the PyPI page. Published as `0.6.6.post1` (page only, identical code).

## [0.6.6] - 2026-08-10

### Added
- **API channel completed into a data platform** (`SapApiLibrary`, still
  stdlib-pure, 2026-08-10):
  - Full OData CRUD: `Patch Odata` / `Delete Odata` (the CSRF protocol is
    generalized to every write, with the one-shot replay on an expired-token
    403; `If-Match` handled, `*` by default), `Call Odata Function` (v2
    function imports, v4 actions) and `Post Odata Batch` (multipart `$batch`
    for v2 AND v4, writes grouped in ONE atomic changeset by default,
    responses flattened in order, partial failures fail loudly; pure core
    `sapfx_common.odata_batch`).
  - **Test-data factory**: `Post Odata track=True` registers each created
    entity (v2 `__metadata.uri`, v4 `@odata.id` or `Location`, foreign
    origins relativized), `Register Created Entity` / `Get Created Entities`,
    `Delete Created Entities` (LIFO, best-effort, JSON-safe report,
    `strict=` option) and `Ensure Odata Entity` (idempotent create); closing
    a session with uncleaned tracked entities warns, never silently.
  - Server-driven **pagination**: `Get Odata Entities follow_next=True`
    follows `__next` / `@odata.nextLink`, `max_pages` cap with an announced
    truncation warning (a silent partial read is a false-positive factory).
  - **Channel perception and discovery**: `Get Odata Metadata` (v2+v4
    `$metadata` parsed and cached per session: entity sets, keys, properties,
    `sap:label` labels; pure core `sapfx_common.odata_metadata`),
    `Find Odata Property By Label` (the API twin of the human locators, all
    candidates surfaced) and `List Odata Services` (Gateway catalog).
  - **Gateway preflight**: `Get Gateway Status` / `Gateway Should Be Active`
    (classified probe, each state names its remediation; the recreated-A4H
    HTTP 500 `/IWFND/CM_COS/003` case points to IMG `/IWFND/IWF_ACTIVATE`)
    and `Wait Until Api Available` (boot polling, never `time.sleep`); pure
    core `sapfx_common.gateway_status`.
  - **Auth beyond Basic**: OAuth2 client credentials (`token_url` +
    `client_id` + `client_secret`, Bearer cached and refreshed, one replay
    on 401, secrets never logged) and mTLS client certificates
    (`client_cert` / `client_key`) on `Open Api Session`.
  - **Per-alias telemetry**: request/error counters, cumulated network time,
    last status/URL/error (`Get Api Telemetry`; `List Api Sessions` rows
    enriched, which feeds the rf-mcp state provider for free).
  - **BAPI pattern** over the optional RFC: `Call Bapi` (BAPIRET2 checked by
    TYPE `E`/`A`/`X`, locale-safe by construction, failure lists the blocking
    messages and reminds the rollback; pure core `sapfx_common.bapi_return`),
    `Commit Bapi Transaction` (`WAIT='X'`) / `Rollback Bapi Transaction`, and
    `Wait For Background Job` (TBTCO polled through `RFC_READ_TABLE`, no
    screen occupied, aborted job fails immediately; pure core
    `sapfx_common.rfc_tables`). `Lookup Business Term` is now exposed on the
    API channel too (third channel of the shared vocabulary).
- **ECC classic-dynpro comfort** (`SapEccLibrary`):
  - **GuiTableControl by column title**: `Read Table Control`,
    `Get Table Control Cell` / `Set Table Control Cell` (absolute row,
    automatic windowed scrolling, COM object re-acquired after each scroll)
    and `Find Table Control Row`; untitled columns become `COL<n>`,
    duplicated titles get a `(2)` suffix (nothing silently lost); pure core
    `sapfx_common.table_control`; ALV objects are redirected to `Read Grid`
    and vice versa.
  - `Pick F4 Value`: opens the field's search help, picks the entry (result
    grid double-clicked, or label list via F2) and closes the popup; value
    not found = popup closed (F12) + failure listing a sample of visible
    values; a multi-step F4 dialog fails naming `Get Screen Signature`.
- **Fiori flakiness killers** (`SapFioriLibrary`):
  - `Wait For Ui5 Idle`: waits for the REAL quiet point (in-flight XHR/fetch
    counted by bundle instrumentation + visible busy indicators + a
    continuous `settle` window); network-level, so it also works on WC and
    hybrid pages ("rendered" does not mean "data arrived").
  - `Get Ui5 Messages` / `Ui5 Should Have No Messages Of Type`: reads the
    MessageManager (legacy core and the modern `Messaging` module) plus the
    recent `MessageToast`s (hook installed at bundle injection); assertions
    by message TYPE, never localized text (convention #3 on the web channel).
  - `Upload File Via Ui5`: targets the control's inner `input[type=file]`
    through open shadow roots and delegates to Browser's
    `Upload File By Selector`.
- **Live validation against A4H and cap-sflight (2026-08-10)**, which drove
  three real fixes the unit tests could not have found:
  - API channel **8/8 + 8/8 live** on A4H: Gateway preflight (`ok` on the live
    catalog, `unreachable` on a closed port, `Wait Until Api Available`),
    discovery (38 services listed, `SEPMRA_SHOP` `$metadata` parsed to 9 entity
    sets, `$metadata` cache proven by zero extra request, `Find Odata Property
    By Label` resolving the real label « Availability » to
    `Products.StockQuantity`), then the full data cycle: `Post Odata
    track=True` (server count 3 -> 4), re-read, `Patch Odata` (rating re-read
    as 2 server-side), `Delete Created Entities` (count back to 3, zero
    residue), idempotent `Ensure Odata Entity` and a real multipart `$batch`.
  - **Table-control semantics corrected from the live system**: the scrollbar
    caps at `total - visible` (the old plan asked for an out-of-range position
    and raised), and `RowCount` counts RESERVED rows (47 announced, 26 filled)
    whose cells are not materialized. `window_plan` replaces `scroll_positions`
    (each row covered exactly once, last window shifted), `Read Table Control`
    stops at the truly filled rows instead of returning phantom ones, and
    `Get Table Control Cell` on a reserved row fails naming the trap. Live
    result: 47-row screen read as its 26 real rows, row 25 reached through
    automatic scrolling, `Find Table Control Row` returning 25.
  - `Pick F4 Value` **validated on a real match code** (SE16/SCARR `CARRID`):
    « LH » picked from the live result grid and landed in the field; an absent
    value closes the popup and fails listing the real values (AA, AB, AC…).
  - `Wait For Ui5 Idle` **validated on the live cap-sflight List Report**
    (search + Go, then the filtered rows read after the wait are all the
    filtered ones), and its exact scope documented: it waits for requests
    ALREADY in flight, so a first render is still awaited through an
    application condition. New offline-capable suite
    `tests/robot/fiori_idle_messages_smoke.robot` (3/3) also covers
    `Get Ui5 Messages` / `Ui5 Should Have No Messages Of Type`.
- **Agent/rf-mcp consumability, kept in lockstep**: every new keyword returns
  JSON-safe data; the three plugin intent cards route the new surface; the
  guidance hints teach it (CRUD+factory, pagination, discovery, preflight,
  BAPI, idle wait, messages by type, table controls, F4); the freshness guard
  `check_guidance_sync.py` now enforces the new flagship keywords; the
  planner/generator/healer definitions and the `sapfx` skill gained the
  API-perception, idle-wait and data-factory guidance (VS Code chat modes
  regenerated).

### Security
- **Code & security review pass (2026-08-10)**, every finding fixed and
  unit-locked (1020 -> 1027 tests):
  - `Close All Api Sessions` now also closes the namespace's **RFC
    connections** (an orphaned RFC connection is a user session left open
    server-side, the API-channel mirror of the "close every session you
    opened" GUI lesson); new `Close All Rfc Connections` keyword,
    best-effort (a dead connection does not block the others).
  - `Open Api Session` **warns when Basic credentials travel over plain
    `http://`** (mirror of the existing `verify_tls=False` warning); aliases
    are validated non-empty like the GUI channel's.
  - `Get Odata Count` requires the `$count` body to be **fully numeric**
    instead of extracting digits from any response: an HTML login or error
    page containing digits could fabricate a plausible count (silent false
    positive).
  - The WebGUI **sid engine decodes `lsdata` HTML entities with a pure
    decoder** instead of the detached-`textarea.innerHTML` trick (theoretical
    RCDATA breakout via `</textarea>`; no privilege gain, the bundle already
    runs in page context, but the pattern is gone). Recorder artifacts
    regenerated; offline smokes re-run green (hybrid 6/6, wc 7/7, web
    recorder 4/4).
  - `export_public_tree.py` extracts the HEAD archive with `tarfile`'s
    `filter="data"` (belt-and-braces; also pins the Python 3.14 default).

### Changed
- **`Post Odata` retries once on an expired CSRF token (2026-08-10)**: a 403
  whose body names the CSRF (Gateway security timeout, ~30 min) invalidates
  the cached token, re-fetches and replays the POST once; any other error
  still surfaces unchanged, and there is no blind retry. **Validated live vs
  the real A4H Gateway** (instrumented transport, 7/7): nominal handshake
  `GET Fetch -> POST token` accepted (the write-less probe POST reaches the
  service layer: 405 business refusal, nothing written), then a corrupted
  cached token draws the real Gateway CSRF 403 and the retry replays exactly
  once with a fresh token, converging on the same business outcome.
- **The injected JS becomes real JS files (2026-08-10)**: the `__SAPFX`
  bundle and the Spy listener move out of `_ui5_js.py`'s Python strings into
  `src/SapFioriLibrary/_ui5_bundle.js.tpl` /
  `_ui5_spy_listener.js.tpl` (shipped in the wheel via package-data), loaded
  and assembled by the module. Proven **byte-identical**: `BUNDLE`,
  `spy_snippet()` and the regenerated recorder artifacts are unchanged;
  `_ui5_js.py` drops from 2 707 to ~220 lines and the JS gets highlighting,
  readable diffs and JS tooling.
- **Desktop recorder split (2026-08-10)**: the pure text-to-text export
  layer (suite, resource-first, spec, ISTQB, HTML report: 923 lines with
  zero dependency on the COM half) moves to
  `tools/recorder/recorder_exports.py`; `sapgui_recorder.py` re-exports
  every name (explicit aliases), so path-loading consumers (Tkinter GUI,
  unit tests, Robot suites importing the file as a Library) are untouched.
  The deployment pack copies the whole `tools/recorder` directory, so the
  new module ships automatically. **Re-validated live vs A4H the same day**:
  `ecc_record_smoke` 1/1, then a full record -> exports -> dryrun -> replay
  cycle 6/6 (poll engine transcribes a real SE16 flow, the four artifacts are
  produced from the raw recording, the resource-first suite carries no raw id
  and dry-runs green, and the replay against the open session lands on the
  T000 selection screen; clean logoff in finally).
- Stale `integrations/robotmcp/build/` output removed from the working tree
  (regenerated by any build; it polluted greps with outdated copies).
- **Two medallion variants, one per scope (2026-08-07)**: the project logo
  splits in two engravings of the same medal. **ECC UI5 API TEST SUITE**
  (robot face) speaks for the **whole project** (libraries + recorders + MCP
  integration + test agents) and stays `assets/logo.png`: GitHub READMEs,
  deck cover, web pages, extension icons 16/48/128, desktop recorder window
  icon, and the 28 px data-URI embedded in the web recorder panel. **ECC UI5
  API LIBRARY** (triskelion) speaks for the **three libraries alone**, which
  is exactly what `pip install robotframework-sapfx` ships: it becomes
  `assets/logo-library.png` and is used on the PyPI page only. The README is
  a single file for both destinations, so the swap happens where the PyPI
  variant is rendered: `pypi_readme()` in `scripts/export_public_tree.py` and
  the `pypi-publish.yml` step, both **fail-closed** (pattern not found =
  abort), unit-tested including a guard on the real `README.md`. Both
  artworks are committed detoured (white background removed) as 1024 masters
  `assets/logo_rf-sapfx_{suite,library}.png`, superseding the previous
  `assets/logo_rf-sapfx.png` (LIBRARY RECORDER engraving, removed).
  `gen_icons.py` now also rewrites the `_AICABRA_ICON` data-URI in place, so
  one command regenerates every derivative.

### Fixed
- **Desktop recorder: a produced `.robot` now runs as-is (2026-08-05)** :
  recordings (and VBS transpilations) are written as a COMPLETE suite by
  default (Settings + `Library    SapEccLibrary` + `Suite Setup    Attach To
  Open Session`); the historic body-only fragment lacked the Library import
  and failed with "keyword not found" when launched directly (caught by the
  ISTQB live test: user report). `--body-only` restores the fragment for
  pasting into an existing suite; `--suite` stays accepted (now redundant);
  the GUI "Suite .robot complète" checkbox is ticked by default and unticking
  it emits `--body-only`. CLI default locked by a no-SAP unit test via the
  transpile path; the repaired live recording was re-run AS-IS by robot
  against A4H: 1/1 PASS (attach, SE16 flow, value assertion `2` re-verified
  live, visual baseline created on first pass, clean logoff).

### Added
- **ISTQB export on both recorders + `sap-istqb` agent (2026-08-05)** : one
  shared document template covering both ISTQB levels (test plan: objective
  and scope, preconditions, entry/exit criteria, traceability, risks; test
  cases: Action / Données / Résultat attendu table), each test case carrying
  a normalized `replay` YAML block (framework-neutral actions
  `run_transaction`/`fill`/`click`/`press_key`/`assert_*`…, human target
  wording, recorded locator relegated to a `hint` with engine name and, on
  the web, the recorded xpath as `fallback`): human-readable AND replayable
  by an AI with any test framework. Desktop: `steps_to_istqb` +
  `--export-istqb` + a GUI checkbox (passwords never carried, hot assertions
  become real expected results, table cells pipe-escaped, YAML single-quote
  safe); web: `buildIstqb` mirrors the template with one `TC-nn` per
  scenario (`+test` markers), new « plan ISTQB (.istqb.md) » export-menu
  entry, extension 0.9.2 → **0.10.0**, artifacts regenerated. New offline
  agent **sap-istqb** (`/sap-istqb` command, chat mode regenerated,
  `check_guidance_sync` markers carried): writes the judgment fields from
  `specs/` plans and recorder outputs into `specs/istqb/<slug>.istqb.md`
  (directory contract in `specs/istqb/README.md`), never inventing what no
  source supports, never touching `tests/robot/` or `resources/`.
  **Live-validated the same day against A4H Docker** (visible SAP GUI,
  native record engine, scripted actions): SE16 → T000 → « Number of
  Entries », hot value assertion reading the real count (2 clients) plus a
  visual baseline, F12, clean logoff; 8 steps transcribed (merged
  `Run Transaction`, exact `btn[31]` click) and the `.istqb.md` exported
  from the raw recording. The live run caught a slug bug (accented test
  names lost their letters: `TP-sc-nario-enregistr`), fixed by NFKD
  transliteration on both channels and unit-locked. The **agent itself was
  then exercised the same day** on both live recordings: it wrote the two
  fully-redacted documents under `specs/istqb/` (T000/SE16 and
  cap-sflight search), keeping the live-recorded replay blocks intact,
  grounding every claim in real repo sources (verified: the spec, the
  generated suite and its exact `Spec:` hash it cites all exist), justifying
  priorities, naming real traceability gaps (T000 has no planner spec or
  generated suite; the recording asserts no filtered count) and leaving
  honest « à compléter » questions instead of inventing answers.
- **Web recorder: multi-format export checkboxes (2026-08-05)** : every row
  of the export menu now carries a checkbox (tick several formats, selection
  persisted across navigation via sessionStorage) plus an « exporter la
  sélection » entry that downloads them all with staggered downloads
  (resource-first counts for its 2 files), so Chrome shows its
  multiple-downloads prompt instead of silently blocking; an empty selection
  reports honestly instead of no-oping. Clicking a row's label keeps the
  historic immediate single-format export (offline smoke re-run 4/4 against
  real Chromium). The desktop GUI already allowed combining its export
  checkboxes freely. **Live-validated the same day against local cap-sflight**
  (visible Chromium, real Fiori Elements List Report): recorder injected,
  real gestures recorded (search « Aussie » + Go + Alt+click assertion,
  `Travels (4,133)` → `(91)`), `.robot` + ISTQB checkboxes ticked then
  « exporter la sélection » delivering both files (staggered downloads,
  « Export de 2 formats » hint); the exported `.istqb.md` carries the stable
  Fiori Elements ids as `ui5-role` hints with their recorded xpath as
  `fallback`, and the transliterated identifier
  (`TP-recherche-de-voyages-filtree`).

## [0.6.5] - 2026-08-05

### Added
- **Source opening (2026-08-03)**: the full source tree is now public on
  [CyrilM29/robotframework-sapfx](https://github.com/CyrilM29/robotframework-sapfx),
  published as a fresh history (founding commit « SAPFX 0.6.4 - source
  opening »); historic release tags and ZIP assets survive. The private repo
  stays the studio (communication base, settings, full history).
- **PyPI publication**: `pip install robotframework-sapfx`
  ([pypi.org/project/robotframework-sapfx](https://pypi.org/project/robotframework-sapfx/)),
  sdist + wheel with LICENSE and NOTICE embedded, `twine check` clean;
  install-from-PyPI smoke-validated in a throwaway venv (all four packages
  import).
- **`scripts/export_public_tree.py`**: the export-per-release tool behind the
  posture: `git archive HEAD` + explicit exclusions + fail-closed transforms
  (every pattern must match an exact count) + a blocking byte-level leak scan
  (binaries included, per-file justified tolerances) + a PyPI README variant
  (no relative EN/FR banner). The script is itself excluded from the export;
  its unit tests ship and skip cleanly on the public tree.
- **PyPI Trusted Publishing workflow**: `.github/workflows/pypi-publish.yml`
  (OIDC, `pypi` environment, no stored token): triggered by a GitHub Release
  on the public repo (or manually), guards tag == pyproject version, strips
  the EN/FR banner from the README (relative link, broken on PyPI), builds
  and publishes sdist + wheel.
- **Project presentation video published**: `docs/media/
  sapfx-project-presentation.mp4` (3 min 20) ships in the public repo and is
  the video linked from the READMEs (GitHub and PyPI), replacing the 30-second
  healing screencast link (the healing GIF stays inline).

- **Web recorder: payment/OTP fields masked at capture time (2026-08-05)** :
  ported back from the sibling rf-web-recorder project (its 0.4.1 hardening
  pass, itself born from the SAPFX dom engine): `sensitiveMask` extends the
  password-only masking to payment and OTP fields (autocomplete tokens
  `cc-number`/`cc-csc`/`cc-exp*`/`one-time-code`/`current-password`/
  `new-password`, plus deliberately narrow name/id/aria-label patterns) →
  `<SECRET>` placeholder; real values never reach the recorded flow,
  sessionStorage or the exports, and every masked field (not only passwords)
  keeps its fallback xpath line. Locked by an offline E2E test
  (`Recorder Masks Sensitive Fields At Capture Time`, new
  `sensitive_fixture.html`) plus unit locks. Extension 0.8.0 → **0.9.0**,
  artifacts regenerated.

- **Recorder identity and movable windows (2026-08-05)** : the web recorder
  panel now carries the aicabra medallion (28 px data-URI baked into the
  bundle: no network request, silent hide under a strict `img-src` CSP) and
  advertises its drag affordance (header tooltip + move cursor on the icon;
  the header was already draggable); the desktop recorder GUI gains an
  aicabra banner that doubles as a second drag handle for the window (pure
  `banner_drag_position` logic, unit-tested), useful when the native title
  bar sits off-screen above a full-screen SAP GUI. Extension 0.9.1 →
  **0.9.2**, artifacts regenerated.

### Fixed
- **Web recorder: honest clipboard fallback (2026-08-05)** : same
  back-porting pass: `copy()` now falls back to a temporary-textarea
  `document.execCommand('copy')` when `navigator.clipboard` is missing
  (non-secure http origins, the typical intranet WebGUI host) or when
  `writeText` rejects; the button reports the fallback's REAL result instead
  of claiming « copied » when nothing was copied (the old code did exactly
  that whenever the async clipboard was absent).
- **Web recorder: storage and download failures surfaced** : a failing
  sessionStorage write (quota, storage blocked by site policy) now warns once
  in the console instead of silently losing the recording across a reload; a
  failing export download surfaces in the panel hint (clipboard copy as the
  fallback) instead of an export silently missing.
- **Web recorder: exports bootstrap on the recording START url (2026-08-05)** :
  caught by a live probe against a public non-SAP site (OrangeHRM: record
  login -> dashboard, then export from the dashboard): `New Page` used the
  URL at EXPORT time, so the exported suite replayed from the wrong page.
  Ported the rf-web-recorder mechanism back: the start URL is remembered at
  the first `rec` (never overwritten by the post-navigation resume), consumed
  by both suite bootstraps and both documents (spec, HTML report), cleared by
  `clear`, and restored when importing a `.robot` (round-trip). Live-validated
  end-to-end on OrangeHRM (real login, masked password, both exports).
  Extension 0.9.0 → **0.9.1**, artifacts regenerated.

### Changed
- READMEs: PyPI/Python/license badges, `pip install robotframework-sapfx`
  quick start, logo and demo media served from absolute URLs so the PyPI page
  renders them; `pyproject` project URLs now point to the public repository.

## [0.6.4] - 2026-08-02

### Changed
- **Project renamed to SAPFX (2026-08-02)**: the internal codename becomes
  the one project name everywhere. Distribution `robotframework-sapecclibrary`
  → **`robotframework-sapfx`** (wheel filename follows; `install.ps1` glob,
  pack READMEs and NOTICE updated; library/module names `SapEccLibrary`,
  `SapFioriLibrary`, `SapApiLibrary`, `sapfx_common` unchanged). Private
  GitHub repo renamed `SAP_library_custom` → `sapfx` (GitHub redirects the
  old URL; `Homepage`/`Documentation` URLs updated in both pyprojects).
  New medallion logo (ROBOTFRAMEWORK-SAPFX): white background removed,
  `assets/logo.png` (512 master) replaced, `assets/logo_rf-sapfx.png` kept as
  the 1024 detoured master, extension icons 16/48/128 + recorder GUI icon
  regenerated via `gen_icons.py`.

### Added
- **HTML documentation report, 4th recorder export, both channels
  (2026-08-02)**: born from the 2026-08 RoboSAPiens watch (their
  `saveHtmlReport`, concept re-implemented, NOTICE extended). Desktop:
  `--export-report` (CLI + GUI checkbox) writes `<out>_report.html`, a
  self-contained page (inline minimal CSS, no JS, no external resource) that
  documents the recording: French business phrase per step (the spec-export
  phrasing, extended to **Fiori/UI5 and API keywords** so mixed cross-channel
  transcripts render too) with the exact RF line alongside (the report never
  invents), `# screenshot:` boundaries inlined as per-step data-URI images
  (missing capture = named honest mention), `password=` named arguments always
  masked. Improves on the original: per-STEP screenshots (theirs: one per
  window), pure text→text builder with injectable screenshot loader
  (convention #5). Web recorder: `rapport HTML (.html)` entry in the export
  menu (same self-contained page, one chapter per scenario, no screenshots:
  a page cannot photograph itself; extension 0.7.0 → **0.8.0**, artifacts
  regenerated). The raw recording is still never modified.
- **Dynamic vkey names in the desktop recorder (2026-08-02)**: also learned
  from RoboSAPiens: the native record engine now resolves virtual-key names
  beyond the static table through `GuiSession.GetVKeyDescription`
  (`set_vkey_resolver`, wired while recording, restored on teardown,
  COM-failure-safe): `Send Vkey 17` gains its `# Shift+F5` comment; the
  static table keeps priority so outputs stay stable off-SAP.
- **Project presentation video (2026-08-02)**:
  `comms/visuels/sapfx-project-presentation.mp4` (3 min 20, English overlays,
  aicabra-branded): title/problem cards, VS Code walkthrough
  (test → resources layer → flagship), live SAP GUI vs A4H, live Fiori vs
  cap-sflight, real OData probe (v2+v4), an MCP agent session driving the
  live system (perception `@N` → act-by-reference) plus the rf-mcp
  `build_test_suite` output, proof cards (974 tests · 17/17 live · 3
  channels). Reproducible production kit under `comms/visuels/presentation/`
  (deterministic frame-by-frame card entrances (no `zoompan`, no screencast
  cadence), desktop-region capture harness, ffmpeg edit pipeline); notes in
  `comms/video-presentation.md`; filming lessons in
  `memory/tournage-video-demos.md`.

### Pending
- **SAP GUI 8.10 validation** (GA was 2026-07-16): re-run the ECC smokes and the
  native-event record engine against 8.10 as soon as it is installed on the
  test workstation (the known-sensitive point is the COM event connection).

## [0.6.3] - 2026-07-27

### Added
- **Numbered screen map + act-by-reference (2026-07-25)**: Vibium-inspired
  (`map`/`@e1` pattern from Jason Huggins' agent-first browser tool, applied
  to SAP GUI): `Get Screen Map` numbers the actionable targets of the active
  screen (`@N` + verified human label + id + type + value, same affordance
  engine as `mode=semantic`), and `Resolve/Click/Fill Screen Ref` act by
  number: no id to copy, references are ephemeral (last numbered perception)
  and re-verified before every action (screen changed or element gone =
  actionable failure naming `Get Screen Map`). The Set-of-Mark annotated
  screenshot legend now feeds the same `@N` table, closing the
  vision → deterministic-action loop. Surfaced to agents via the ECC plugin
  keyword map + a dedicated rf-mcp hint (interactive piloting only: suites
  keep using `resources/` locators, convention #1). 8 new unit tests.
  **Fiori mirror**: `Get Ui5 Page Map` reduces the UI5 control tree to the
  numbered actionable targets (editable types marked `*` with current value,
  clickable types, human label from text/title/placeholder/tooltip; pure
  logic `ui5_page_map` in `_ui5_runtime.py`, `include_types=` override for
  list rows), and `Resolve/Click/Fill Ui5 Ref` act by number: liveness
  re-checked against the rendered UI5 registry before every action, frame
  scope respected, composite-control fill targets the inner `<input>` like
  `Fill Ui5 Input`, `mode=diff` memory untouched. Fiori plugin keyword map
  (exhaustiveness-tested), rf-mcp hint and guidance guard extended. 7 more
  unit tests.
- **`sapfx` toolkit skill** (`.claude/skills/sapfx/SKILL.md`), the
  install-as-a-skill idea: one skill call teaches an assistant the three
  channels, the perception → action loop, the non-negotiable conventions and
  the agent cycle. Shipped in the Windows deployment pack
  (`.claude/skills/` added to the pack manifest; pack READMEs updated).
- **Vibium watch entry** in `comms/comparatif.md` (family 3, honest-nuance
  section, sources): complementary generalist, zero SAP coverage. Its
  agent-first vocabulary is a de-facto standard SAPFX already speaks.
- **Agent feedback loops closed mechanically (2026-07-24)**: back-port from the
  sibling project `rf-test-agents` (same author, universal core of the
  plan → generate → heal cycle), where these mechanisms were designed and
  validated end-to-end on a live application. Three loops that existed only as
  prose in the agent definitions are now machine-visible:
  (1) **stale-plan marker**: sap-healer writes a normalized
  `> **Statut : PÉRIMÉE (date)**` blockquote when the business flow itself
  changed, and `check_spec_sync.py` now **fails while it is present**, until
  sap-planner re-explores and removes it (previously the healer "flagged the
  spec as stale" in a conversation report, i.e. nowhere);
  (2) **generation divergences**: sap-generator records where live SAP
  contradicted the plan under `## Écarts constatés à la génération`, *before*
  re-stamping, so the provenance hash covers the annotated plan and the planner
  sees the gaps on its next pass;
  (3) **`docs/heal-journal.md`**: the agent's own diagnosis per heal session
  (failure class, live evidence, anchoring lesson). Complementary to, not a
  duplicate of, the runtime `SAPFX_HEALING_LOG` telemetry: the telemetry says
  *what keeps drifting*, the journal says *why and what to do about it*.
  sap-planner reads it before writing locator notes.
- **`scripts/check_conventions.py`**: conventions #1/#2 were *stated*
  (CLAUDE.md, `_guidance.py` hints, agent definitions, all checked by
  `check_guidance_sync.py`) but nothing verified they were *held* by the
  artifacts. This guard does: raw locators (SAP GUI ids like
  `wnd[0]/usr/ctxt…`, UI5 control addresses, CSS/XPath) in a test body, and
  `Sleep` anywhere. Convention #1 is **blocking on generated suites only**,
  recognised by their provenance marker; the hand-written library-validation
  suites (`business_data_exploration`, `exploratory_campaign_a4h`, …) are
  reported for information, since driving SAP by raw ids is precisely their
  purpose (`--strict` blocks them too). Auto-maintained: no exemption list.
  Unit tests in `tests/unit/test_check_conventions.py` (22 cases).
- **`scripts/hook_guards.py` + `PostToolUse` hook**: both guards run after
  every Write/Edit of `specs/`, `tests/robot/`, `resources/`, `variables/`:
  a conventions violation blocks (exit 2), spec-sync drift is reported
  non-blocking (it can be transient mid-generation).
- **CI**: `check_spec_sync.py` and `check_conventions.py` now run in the
  guards job. The provenance guard existed but was never wired into CI.

### Changed
- **rf-mcp 0.35.0 compatibility (2026-07-24)**: the overlay's startup guard
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
  then serves a desktop stub instead of the SAP page source. Agent
  definitions now instruct to say "SAP GUI"/"ECC" instead; the `sapfx_state`
  overlay tool is immune (calls the SAP providers directly). Full unit suite
  (946) green against the real 0.35.0; live A4H agent cycle not re-run.

### Fixed
- **Pack `.cmd` launchers shipped with LF-only line endings (2026-07-27)**:
  the repo-wide `.gitattributes` rule (`* text=auto eol=lf`) also applied to
  `install.cmd` / `recorder.cmd`, and cmd.exe's parser trips on LF-only files:
  double-clicking the 0.6.2 pack's `install.cmd` echoed two
  «'M' n'est pas reconnu…» errors on the `REM` header lines (the install
  itself still completed: cosmetic but alarming, and parser behaviour on
  LF-only batch files is version-dependent). Fixed in depth: `.gitattributes`
  exception (`*.cmd`/`*.bat` → `eol=crlf`), working-tree launchers converted,
  and `build_release_pack.py` now normalizes every staged `.cmd` to CRLF so
  the ZIP is correct regardless of the builder's checkout (unit-locked).
- **`check_spec_sync.py` was blind to ventilated suites**: it globbed
  `tests/robot/*.robot` non-recursively while sap-generator's contract places
  new suites under `tests/robot/{api, ui/ecc, ui/fiori, cross}`. Latent today
  (all 25 suites are still flat), it would have silently skipped every
  generated suite as soon as the ventilation started. Now `rglob`.
- The provenance marker also carries the **generation date**
  (`sha256:…, AAAA-MM-JJ`); markers stamped before this change stay valid.

## [0.6.2] - 2026-07-23

### Added
- **Agentic-layer upgrade pass (2026-07-23)**: the rf-mcp/agents system
  catches up with three releases of library features and closes its
  operational loops. (1) **Guidance + intent maps refreshed**: the ECC/Fiori
  keyword maps and hints now cover multi-session aliases, `Attach To Open
  Session`, `mode=semantic`, Set-of-Mark annotated screenshots, visual
  baselines/`Check Screen Against Watch`, the pointer effector, dynamic
  timeouts, FLP intent navigation, IDP login, business vocabulary;
  `check_guidance_sync.py` grew a **keyword-map freshness guard** (flagship
  keywords per mixin, textual: this drift class cannot recur). (2) **State
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
  inject/verify/restore + `/sap-eval-healer`, the 0.3.0 blind exercise made
  replayable). Instructed tracks documented in `docs/test-agents.md` (MCP
  vision channel: no image support in the rf-mcp 0.31 plugin contract,
  fastmcp could carry it (upstream proposal); planner read-only guard:
  design + why not built). +39 unit tests (884 collected).
- **Industrial project layout encoded in the generator/healer (2026-07-23)**:
  generated artifacts now follow the classic ventilation, rooted on the
  existing `tests/robot/` and `resources/`: new suites under
  `tests/robot/{api, ui/ecc, ui/fiori, cross}`; **page objects** under
  `resources/page_objects/` (one `.resource` per ECC screen/transaction or
  Fiori page/app: locator variables on top, business keywords below);
  cross-screen vocabulary in `resources/common.resource` or the shipped
  global resources; environment data under `variables/` (`env_<env>.yaml`,
  shared `locators.py`: credentials never in a file, `Secret:` variables
  only); outputs under `results/`. Legacy flat suites stay untouched; the
  healer's repair surface is that layer (page objects / common / variables /
  shipped resources: `site_keywords.resource` override on a deployed pack),
  never test bodies, and a locator found hardcoded in a test body is itself
  a finding to move into a page object. `agent_eval_harness.py` now also
  protects `variables/` in its verdict manifest.
- **`sapfx-mcp` overlay v1 (2026-07-23)**, NOT a fork: a console entry point
  (`sap_robotmcp/server.py`, `[project.scripts]` of the plugins wheel) that
  mounts the rf-mcp server unchanged and adds the three tools the 0.31
  plugin contract cannot express (every gap established live the same day,
  CLAUDE.md field notes): `sapfx_state` (SAPFX state providers called
  directly: real diff-by-default `page_source` semantics, enriched
  `application_state` with `modal_open`/status/telemetry that rf-mcp never
  routes), `sapfx_screenshot` (real MCP image content, plain or Set-of-Mark
  annotated + `number -> id` legend; `run_keyword_in_context` gained keyword
  `arguments` passthrough for `include_types`), and `sapfx_reload` (the
  live-validated plugin-layer hot-reload protocol, encoded). A startup
  **compatibility guard** (`_compat.py`) pins the tested rf-mcp window
  ([0.31, 0.32)) and probes every internal anchor, refusing to start on
  mismatch (`SAPFX_MCP_FORCE=1` overrides loudly): the vendor-drift-guard
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
  RF native context) for Fiori/web sessions: `annotated` stays ECC-only
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
  `{"1": "wnd[1]/tbar[0]/btn[0]"}`), the vision loop closed end-to-end;
  clean `Close SAP` teardown in the client's finally. **Same-day UI5
  validation, 12/12**, against the public OpenUI5 Demo Kit (headless
  Chromium, no SAP): `sapfx_state` auto-picks `SapFioriLibrary` (Browser
  ignored), full UI5 tree as baseline (26,528 bytes) then the XML diff BY
  DEFAULT after a real SearchField interaction (4,547 bytes, typed text
  visible in the diff), Fiori `application_state` served, and
  `sapfx_screenshot` returning the real page image via the Browser
  fallback (325 KB, search suggestions visibly triggered by the typed
  text); `annotated=true` fails honestly (ECC channel). The 788-byte
  premature-tree run re-confirmed the 2026-07-17 lesson (wait for a
  RENDERED control after `Wait For UI5 Ready` before perceiving).
- **The API channel joins the MCP layer (2026-07-23)**: the third channel
  had NO rf-mcp presence at all (no hints, no keyword map, no state
  provider). Now: `SapApiPlugin` (entry point `sap_api`) with API-channel
  guidance (cross-channel pattern, aliases + `Secret` passwords, v2/v4
  envelope, prefer `$count`, automatic CSRF, optional pyrfc), the full
  keyword map, and a state provider: `get_page_source` answers honestly
  that the channel has no screen (perception IS the keywords' return
  values), `get_application_state` serves the REAL channel state via the
  new `SapApiLibrary` keyword **`List Api Sessions`** (open aliases,
  base_url, sap-client, authenticated/CSRF flags; never credentials).
  The `sapfx-mcp` overlay serves it (`SapApiLibrary` added to
  `SAPFX_LIBRARIES` and to the reload order); `check_guidance_sync` guards
  the new map. **Live-validated 9/9** through the real MCP stdio client
  against the A4H Gateway: `$count` SEPMRA_SHOP/Products = 205 (the
  flagship business fact), entity read (`top`/`select`), `sapfx_state`
  auto-picking `SapApiLibrary` with the live channel state (zero
  credential in the whole response), honest no-screen page_source, and the
  emptied state re-verified after `Close All Api Sessions`. +11 unit tests
  (921 collected).

## [0.6.1] - 2026-07-22

### Added
- **`Set Default Timeout` / `Set Poll Interval` (review feedback)**: the two
  library-level wait settings, previously frozen at import time
  (`__init__` arguments), are now adjustable mid-suite, following the
  established RF idiom (`Set Browser Timeout`, `Set Selenium Timeout`): both
  keywords return the previous value as a Robot time string, ready to be
  restored in a teardown (widen the timeout around one slow transaction,
  demo-data generation, without imposing it on the whole suite). Scope is
  the library instance (`SUITE`), so a change never leaks into the next
  suite. +4 unit tests (841 collected). Live-validated vs A4H (2026-07-22,
  4/4): return-value round-trip, the shortened timeout is the *actual* wait
  fallback (failure measured at ~5s, not the 30s import value), real
  navigation at the new poll step, restore from the returned value.
- **`Set Ui5 Timeout` / `Set Poll Interval` on the Fiori side (review
  feedback)**: the ECC↔Fiori mirror of the pair above, same contract
  (previous value returned as a Robot time string, restorable in a teardown,
  `SUITE`-scoped instance). `ui5_timeout` keeps its as-a-string storage
  convention (every use site converts), and the new value is validated
  BEFORE being adopted: an invalid time string can never corrupt the
  library-wide polling budget. Same-name `Set Poll Interval` in both
  libraries follows the mirror-alias philosophy (qualify or use
  `Set Library Search Order` in cross-channel suites). +4 unit tests
  (845 collected). Live-validated (2026-07-22, 4/4): round-trip, the reduced
  `ui5_timeout` really bounds the tree probe (~2s measured, not 15s), and
  nominal resolution works at the new poll step on a real UI5 runtime.

### Changed
- **The two most generic Fiori failures now name the diagnostics layer
  (review feedback)**: the exhausted fallback chain (`Resolve Ui5 With
  Fallback`) points to `Log Fiori Diagnostics`, and the no-UI5-tree failure
  (`Get Ui5 Page Tree`) points to `Get Page Composition`. The *targeted*
  failures already carried self-correcting hints (`_relaxed_hint` type
  probe, dom→composition, wc→role); these two generic dead-ends did not
  name any next step. Locked by extending the existing failure-path tests,
  and both enriched messages observed live on a non-UI5 page (2026-07-22).

### Removed
- **Dead `_ERROR_MESSAGE_TYPE` constant (review feedback)**: a leftover from
  the pre-fork `run_transaction`, which detected failures by status-message
  *type*; the override has compared `session.Info.Transaction` since the live
  A4H validation proved the "type `E`" hypothesis wrong (an unknown
  transaction reports type `S`). The constant was referenced nowhere.

### Fixed
- **`Run Transaction` namespace tcodes, second pass (review feedback)**: two
  flaws in the expected-vs-`Info.Transaction` comparison introduced with the
  0.1.x namespace fix: (1) the comparison stripped leading `/` from the
  *expected* side only, so it broke whenever the Scripting API returns a
  namespaced tcode WITH its leading slash (sy-tcode form `/BEV1/RCA01`): both
  sides are now normalized identically, making the check independent of which
  form the API returns; (2) a namespace starting with N, O or I
  (`/IWFND/MAINT_SERVICE`, `/IWBEP/…`) was mistaken for an already-prefixed
  entry by the `transaction[:2]` check, so no `/n` was prepended and SAP read
  the raw OK-code as the `/i` system command: the new `_has_nav_prefix`
  disambiguates by the shape of the remainder (after a real prefix comes either
  a slash-free tcode or a `/`-leading namespace, never `WFND/…`). Unit-locked
  (+4 tests), verified live vs A4H: `Info.Transaction` returns the sy-tcode
  form WITH the leading slash (`'/IWFND/MAINT_SERVICE'` observed on SAP GUI
  8.00), and the raw-namespace, plain-tcode and explicit-prefix paths all pass
  through the fixed keyword.
- **`--transpile-vbs` no longer assumes UTF-8 sources (review feedback)**:
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
  feedback)**: both recorders' spec export wrapped recorded values in French
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
  feedback)**: `_field_step` gated every emission on a truthy value, so
  unchecking a `GuiCheckBox` (and clearing a text field) between two polls
  was silently dropped, while the native event engine records `Unselect
  Checkbox` / `Input Text … ${EMPTY}`. The 0.6.0 escaping pass added
  `${EMPTY}` precisely so a clear stays replayable, but the poll-side gate
  was forgotten. Safe by construction: `diff_to_steps` already discards
  new-and-empty fields, so a falsy value reaching `_field_step` is always a
  deliberate user change. Radio buttons keep the emit-if-True rule (their
  `False` is induced by the newly selected sibling). +2 tests (836
  collected); live record smoke re-run 1/1 vs A4H.
- **`--replay` CLI no longer masks the real step error**: the default replay
  library was built with `screenshots_on_error=True`; outside a Robot run the
  failure handler's `take_screenshot` needs the RF context and replaced the
  actual error with `Cannot access execution context` (caught during the
  2026-07-21 live validation pass, where it hid a wrong-session attach). The
  CLI factory now passes `screenshots_on_error=False`: there is no Robot log
  to embed a capture into anyway. Unit-locked (+1 test, 837 collected).

## [0.6.0] - 2026-07-20

### Fixed: peer-review pass on the recorder work (2026-07-20)
A full review of the 07-19/07-20 recorder passes before commit; every finding
fixed and unit-locked (810→823 tests).
- **`name=`/`text=` matching now collapses whitespace on the DOM side** (dom
  AND wc engines, `wsCollapse`): the recorded accessible name is
  space-normalized (an RF cell cannot carry 2+ spaces), but the live accname of
  a multi-node target (`<button>Add\n  item</button>`, typical React, the dom
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
  respected: overwriting is then an explicit choice). `resolve_record_out`
  pure helper, unit-tested.
- **Spec exports honour the specs/ contract on unknown steps** (both channels):
  an untranslated step CARRYING a locator/id no longer leaks it into the steps
  list: the exact line moves to « Points de vigilance »; id-free raw steps
  stay verbatim.
- **Web resource-first export wraps text-assertion pairs**: `${texte} =    Get
  Wc/Dom Text` + `Should Be Equal` become ONE business keyword with the locator
  in the resource (convention #1 had a leak there).
- **Deliberate double-Enter is kept**: the 500 ms dedup exemption now covers
  `Keyboard Key` like clicks. **`--suite` CLI help** named the wrong Suite
  Setup keyword (`Connect To Session`, the very keyword the 07-19 live replay
  proved insufficient). **`Attach To Open Session`** wraps its remaining COM
  accesses (connection closed mid-attach → actionable error). **`.gitignore`**
  now whitelists the committed demo key-frame PNGs (`comms/visuels/*-poster-*`)
  and ignores the raw `.webm` intermediates (the deliverable is the MP4).
- **cap-sflight demo authenticates against cds v9 mocked auth**: anonymous
  OData requests now take a 401 and the List Report stays empty (caught by the
  live recorder test re-run, 2026-07-20): `fiori_demo_video.robot` passes the
  mocked `alice` user via `httpCredentials` (overridable with `-v CDS_USER:`).

Both recorders re-validated LIVE after the fixes, end-to-end: ECC vs A4H
(record with OK-code merge, escaped-value round-trip read from the real screen
and replayed, the three exports, `robot --dryrun` of the pair, `--replay` via
`Attach To Open Session`, 3/3) and web vs the real cap-sflight Fiori Elements
app (real gestures measured `Travels (4,133)` → `(91)`, recording resumes after
reload, in-page replay re-filters the app, exported resource-first pair re-run
green by real `robot`, 1/1).

### Added: Selenium-IDE-spirit pass on both recorders (2026-07-19)
The good half of the record-and-playback spirit (instant feedback, editability,
fallback locators, native SAP ALT+F12 lineage), grafted onto our semantic
locators and resource-first outputs.
- **Web, in-page replay (`play`)**: the recording replays inside the page,
  each step resolved by the same engines the library uses, highlighted,
  executed (~3 steps/s); UI5 steps retry their recorded xpath fallback; first
  failure stops and marks the row. Synthetic replay events are never
  re-recorded. Live-validated: the replayed click really drives the fixture
  (counter increments), the replayed fill lands in the field.
- **Web, steps born self-healing**: every recorded UI5 click/fill carries its
  shortest-xpath fallback as an RF end-of-line comment (`# xpath: …`); the
  resource-first export converts it into `Resolve Ui5 With Fallback    xpath=…`
  followed by the Browser action: the exported keyword repairs itself
  (logged, never silent) from day one.
- **Web, multi-scenario sessions (`+test`)**: marker steps split every export
  (.robot / resource-first / spec) into several test cases, browser bootstrap
  only in the first. **`.robot` re-import**: an exported suite loads back into
  the panel (bootstrap lines skipped, markers restored): byte-identical
  round-trip, live-validated. **Double-click in-place step editing.**
- **Web, recording no longer blocks the app**: the old record-mode
  `preventDefault` froze the application under recording (you could not drive
  a real flow); clicks now pass through, only Alt+click assertion gestures are
  swallowed. Caught live by the replay validation (the fixture counter stayed
  at 0). Extension 0.5.0 → 0.6.0.
- **ECC, `--replay FILE` + GUI «Rejouer»**: replays a recording against the
  already-open SAP GUI session (`Attach To Open Session`), stop on first
  failure with the offending step named; unknown keywords reported, comments
  skipped. Live-validated 4/4 vs A4H.
- **ECC, `--transpile-vbs FILE`**: converts SAP GUI's built-in ALT+F12 VBS
  recordings into SapEccLibrary keywords through the SAME state machine as the
  native engine (OK-code merge, context-menu pairing, cell tracking; unmapped
  calls kept as comments). No SAP session needed; `--suite`/exports apply.
  Validated end-to-end live: VBS → transpile → `--replay` vs A4H 4/4, and the
  generated resource-first pair passes `robot --dryrun`.
- **ECC, self-healing resource-first export**: `--semantic` lines (label +
  technical id) generate keywords resolving through `Resolve Element With
  Healing    ${LOC_…}    label=…`: nominal id path first, scored repair +
  label anchor otherwise. **GUI**: double-click step editing in the panel.
  790→808 unit tests.

### Added: scripted demo takes for both recorders (2026-07-20)
Two committed, reproducible video generators: the recording is a *script*, so a
retake is a one-line edit and a re-run, and every figure shown is measured live.
- **`tools/recorder_web/demo/fiori_demo_video.robot`**: Playwright `recordVideo`
  against the local cap-sflight app, captions injected into the page, **headless
  by default** (a visible window stays interactive, so a stray mouse move ruins
  the take). Output: `dist/video/sapfx-fiori-recorder-demo.mp4`.
- **`tools/recorder/demo/ecc_demo_video.robot`**: the ECC channel is a *desktop*
  app with a console recorder, so nothing in-page can be injected: the take
  captures the **SAP GUI window only** (`ffmpeg gdigrab title=…`, no desktop
  leakage), adds a band under the image and burns subtitles carrying the steps
  the record engine **actually emitted**, timestamped at runtime. The subtitle
  track is re-aligned by a **measured** offset (capture starts before the
  scenario clock; without it the subtitles ran ~2 s ahead of the picture, caught
  by reading screen titles frame by frame). Output:
  `dist/video/sapfx-ecc-recorder-demo.mp4`. Cannot be headless: do not touch the
  machine during a take.

### Fixed: web recorder, caught by a LIVE run against real Fiori Elements (2026-07-20)
Validation of the web recorder against a real Fiori Elements List Report
(cap-sflight, UI5 1.139, 591 rendered controls), not a fixture. Two genuine
defects the fixture smokes and the dryrun could not surface:
- **resource-first export: fills targeted the control root.** A composite UI5
  field (`sap.m.Input`, `SearchField`) roots on a `<div>`; the generated keyword
  emitted `Fill Text    ${cible}` on it, so the exported pair failed at runtime
  (*"Element is not an `<input>`"*) even though `robot --dryrun` was green. The
  generated keyword now descends into the inner element
  (`Fill Text    ${cible} >> css=input, textarea`), exactly as `Fill Ui5 Input`
  already did. Exported pair re-run live: green.
- **panel header clipped its own buttons.** At 380 px the 7-button header
  overflowed and `overflow:hidden` cut `stop` off, genuinely unreachable by
  mouse. Panel widened to 470 px, title ellipsises instead of pushing buttons
  out, buttons never shrink. Seen on a video frame, unit-locked since.

808→810 unit tests. Also live-proven in the same pass: injection into a real FE
app, recorded steps addressing UI5 controls via stable `fe::…` ids (never the
generated `__clone…` DOM ids), step survival across a full page reload, in-page
replay measurably driving the app (`Travels (4,133)` → `Travels (91)`), the three
export formats, and the exported suite re-run green by real `robot`.

### Added: web recorder robustness for real-world sessions (2026-07-20)
Hardening born from the same live Fiori Elements pass. **Extension 0.6.0 → 0.7.0.**
- **Recording state survives navigation**: the recording flag is persisted
  (sessionStorage) next to the steps: after a full-page reload + re-injection
  (snippet re-pasted or extension shortcut), recording RESUMES by itself instead
  of silently dropping every interaction; an explicit `stop` never auto-resumes.
- **Explicit record state across frames (`setRec`)**: the popup and the
  Alt+Shift+R shortcut now read the aggregate state first, then push ONE
  explicit on/off to every frame: per-frame toggles could drift into
  anti-phase (one frame starting while another stopped). The shortcut also
  re-injects idempotently in allFrames (iframes that appeared since the last
  injection are covered) and restricted pages (chrome://, Web Store) show a
  transient `n/a` badge instead of dying in an unhandled rejection.
- **Robot Framework escaping of recorded values** (`rfEscape`/`rfUnescape`):
  typed values and asserted texts are escaped on the way into a `.robot` line
  (`${…}` stays a literal, 2+ space runs, leading `#`/space, trailing space,
  `word=` named-arg ambiguity) and unescaped by the in-page replay: a value
  like `${TAX} 10  %` no longer breaks the exported suite.
- **Deferred Enter is never lost on full-page navigation**: `beforeunload`
  flushes the one-tick-deferred `Keyboard Key    press    Enter` and marks the
  replayable wait before the page dies. Deliberate repeat clicks (stepper `+`,
  pagination) are kept: only a double dispatch of the SAME click within
  500 ms is deduplicated. Clipboard failures now flash `copy failed` instead
  of lying `copied`. `minimum_chrome_version` 111 declared (scripting MAIN
  world floor).

### Added: Recorder upgrade pass, both channels (2026-07-19)
- **`Attach To Open Session` (SapEccLibrary)**: binds the library to an
  ALREADY-open SAP GUI session by connection/session index, with actionable
  errors. `Connect To Session` alone only acquires the scripting engine: the
  session itself was only ever set by `Connect To Existing Connection`, which
  needs the exact connection description. Discovered by live-replaying a
  recorder export on A4H (the generated Suite Setup could not work); the
  generated suites now use the new keyword.
- **Resource-first + spec exports (both recorders)**: the raw transcript is now
  a *draft*, not the end product. Desktop: `--suite` (complete replayable
  `.robot` with `Suite Setup    Attach To Open Session`), `--export-resources`
  (`<out>_keywords.resource`, each id becomes a `${LOC_…}` variable wrapped in
  a business keyword, plus `<out>_resource_first.robot` calling only those
  keywords: **no raw id left in the test**, project convention #1, and the layer
  sap-healer repairs), `--export-spec` (`<out>.spec.md`, a `specs/`-format plan:
  business-language steps, ids relegated to factual notes: the recording
  becomes the input of the plan→generate→heal cycle). Web: the `export`
  button opens a 3-format menu (.robot / resource-first pair / specs plan); the
  generated pair was validated with a real `robot --dryrun`.
- **Live assertions while recording (desktop)**: global hotkeys during
  `--record` (both engines): Ctrl+Alt+A inserts `Element Value Should Be` on the
  focused element (presence check if no readable text, never a password value);
  Ctrl+Alt+V inserts `Screen Should Match Baseline    <out>_etape_NN` (visual
  snapshot). Rising-edge detection via GetAsyncKeyState, pure logic unit-tested.
- **dom-engine capture in the web recorder**: the recorder now covers the
  non-SAP zones of hybrid pages: new `captureDom` in the bundle (computed ARIA
  role + accessible name, CSS light-DOM path fallback, **interactive targets
  only**: a click on a bare div records nothing), hover label `DOM <role>`,
  `Click/Fill Dom …` steps, `dom` copy button, `Resolve Dom Element` capture
  lines. Right-click **assertion menu** while recording (visible / text per
  engine: text via `Get Wc/Dom Text` + `Should Be Equal` pairs where no direct
  keyword exists); Alt+click shortcuts kept. **Enter** captured as
  `Keyboard Key    press    Enter` (deferred one tick so the field's `change`
  lands first; textarea excluded). Navigation now emits **`Wait For UI5 Ready`**
  when the UI5 runtime is present (keyword definition embedded in exports: the
  downloaded file stays self-contained), `Wait For Load State` otherwise.
  Fill/wait **compaction** (re-typing a field replaces the previous fill,
  consecutive waits collapse) and a **cross-origin iframe warning** in the panel
  (the extension's allFrames injection is the answer). Extension 0.4.1 → 0.5.0.
- **Extended native mappings (desktop record)**: grid context menus
  (`pressToolbarContextButton`+`selectContextMenuItem` → one
  `Select Context Menu Item`), tree nodes (`selectNode`/`expandNode` →
  `Select Node`), single selected grid row → `Select Table Row`, grid cell
  clicks keep their row/column (tracked from `currentCell*` events) in an
  enriched comment. Opaque zones (`GuiShell`/`GuiChart`): capture (native
  hit-test) and hover now also suggest `Click Element At Offset` with the
  cursor's relative position, the pointer fallback for what the Scripting API
  cannot script.
- **Tkinter GUI parity**: record options exposed (suite / resource-first /
  spec checkboxes) and a live **steps panel**: follows the output file as steps
  are emitted, reorder/delete, save the corrected file (same
  `parse_recorded_body`/`replace_recorded_steps` helpers as the CLI, pure and
  unit-tested). 751→790 unit tests.

### Fixed: sid engine now matches the REAL WebGUI's lsdata encoding (2026-07-18)
- **Live-discovered by the agent cycle** (sap-planner exploration of the A4H
  SAP GUI for HTML): the real WebGUI emits `lsdata` as a JS literal
  (`SID:'wnd[0]/…'`, unquoted keys, single quotes) while `sid_xpath` and the
  bundle's `captureSid` only matched the JSON form (`"SID":"…"`) our fixtures
  use: 0 match on a live system. `sid_xpath` now emits a dual XPath predicate
  (one per encoding, quote-injection guard unchanged) and the capture regex
  tolerates both; web recorder regenerated. Locked by
  `tests/unit/test_sid_and_spy.py`; JSON-fixture non-regression:
  `fiori_hybrid_smoke.robot` re-run green. 750→751 unit tests.

### Added: WebGUI smoke suite driven by the sid engine (2026-07-18)
- `tests/robot/webgui_smoke_sid.robot`: generated by the plan→generate agent
  cycle from `specs/webgui-smoke-sid.md` and validated live **4/4** vs A4H:
  ITS login through the dom engine's accessibility locators, transaction
  launch via the `~transaction` URL parameter (the OK-code field is hidden by
  default and the setting does not persist), the SE16 T000 entry count read
  end-to-end through sid locators (`wnd[1]/usr/txtG_DBCOUNT`), clean
  System-menu logoff. New WebGUI business keywords in
  `resources/fiori_keywords.resource` (`Open WebGui`, `Log In To WebGui`,
  `Go To WebGui Transaction`, `Count WebGui Table Entries`, `Log Off WebGui`…),
  pure Browser + SapFioriLibrary composition, no new Python. Prerequisite:
  the `webgui` ICF service must be active (activated once via SICF, itself
  driven live through rf-mcp perception→action).

## [0.5.8] - 2026-07-18

### Added: Accessibility locators for the dom and wc engines (2026-07-18)
- **`role=` on the dom engine is now the COMPUTED ARIA role**: the explicit
  `role` attribute still wins, but plain HTML semantics resolve too: a bare
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
  (`Resolve/Click/Fill Dom…`, user-intent locators, like Playwright's
  `getByRole(name=…)`: `role=button name=Fermer la notification`) and the
  **wc** engine (`Resolve/Click/Fill Wc…`, an icon-only `ui5-button` or an
  unlabelled `ui5-input` is addressed by what a screen reader would announce).
  Flows through `Resolve Ui5 With Fallback`'s `wc=`/`dom=` forms unchanged.
- Proven live offline: `fiori_wc_smoke.robot` 7/7 (accessible-name attribute
  AND non-reflected `accessibleName` property) and `fiori_hybrid_smoke.robot`
  6/6 (implicit `role=button` via `aria-label`, `role=textbox` named by its
  `label[for]`); web recorder regenerated (bundle embedded). 743→747 unit
  tests.

### Fixed: alignment pass (agents, MCP hints, recorder GUI) (2026-07-18)
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

### Added: Fiori diagnostics layer (2026-07-18)
- **`Get Fiori Diagnostics`** (SapFioriLibrary): ONE JSON-safe dict aggregating
  the diagnostic bricks Browser 20 exposes separately, plus the project's own
  perception: the hybrid `composition` probe, the UI5 control tree
  (`ui5_tree`, probed for a short `tree_timeout` only, `None` when absent,
  never touching `Get Ui5 Page Tree`'s `mode=diff` state), normalized
  `console` / `page_errors` entries (Browser `Get Console Log` / `Get Page
  Errors`, incremental by default, matching the diff philosophy;
  `full_logs=True` re-reads everything; truncation to the `max_log_entries`
  most recent is always announced via `*_dropped`), and the ARIA snapshot of
  the non-SAP regions (`Get Aria Snapshot`, frame-scoped). Every section is
  best-effort (failures land in `collection_errors`, never abort the
  diagnostic), and the `issues` summary is actionable: first JS/console error
  quoted, missing UI5 tree names the recommended fallback engines and the
  iframes to scope into. Respects `Set Ui5 Frame` / `Push Ui5 Frame`.
- **`Log Fiori Diagnostics`** (SapFioriLibrary): same collection, rendered as
  a Markdown report into the Robot log (issues first), teardown-friendly
  (`Run Keyword If Test Failed`). Returns the dict for follow-up assertions.
- **`sapfx_common/fiori_diagnostics.py`**: the pure, typed core (section
  validation, console/page-error normalization to stable JSON-safe shapes,
  announced truncation, issue synthesis, Markdown report): Browser I/O stays
  in the keyword. rf-mcp Fiori guidance now points agents at the aggregate
  first when a screen misbehaves. 722→743 unit tests.

### Changed: RF 7.4 modernisation pass (2026-07-18)
- **`Input Password` accepts Robot Framework 7.4 `Secret` values**
  (SapEccLibrary override; the vendored keyword stays untouched, convention
  #4): the secret is unwrapped only at the COM boundary, plain strings behave
  exactly as before. Every password-accepting keyword of the three libraries
  now takes a `Secret`.
- **Launch examples document the typed-`Secret` syntax**
  (`-v "SAP_PASSWORD: Secret:..."`) across READMEs, docs (hardening §3,
  ecc-validation, deployment-pack) and every suite header: the value is
  masked everywhere, even at TRACE log level. The self-contained demo suites'
  password guards switched from `Should Not Be Empty` to `Should Not Be Equal
  ... ${EMPTY}` (a `Secret` has no measurable length).
- **Last deprecated `Force Tags` replaced by `Test Tags`**
  (`business_data_exploration.robot`): RF 7.4 deprecation, RF 8 readiness.

## [0.5.7] - 2026-07-17

Hybrid-sessions release: both improvement axes land together, **Fiori hybrid
pages** (composition probe, generic DOM engine, nested-frame stack) and the
**ECC multi-session registry** (named aliases with STA/Secret/teardown safety
rails). Every new keyword was driven live step-by-step through rf-mcp on both
channels, then locked by a self-contained reproducible smoke replayed by the
real robot runner (`fiori_hybrid_smoke.robot` 5/5 offline,
`ecc_multisession_smoke.robot` 4/4 vs live A4H). 677→720 unit tests at 93%
coverage (CI ubuntu measurement, the canonical one; 94% locally on Windows
against the real pywin32).

### Added: Fiori hybrid sessions (2026-07-17)
- **`Get Page Composition`** (SapFioriLibrary): hybrid-page perception probe.
  Reports which addressable technologies coexist in the current document
  (classic UI5 runtime / UI5 Web Components hosts / WebGUI `lsdata` elements /
  React-Angular-Vue hints), the recommended resolution engines per region (same
  order as the fallback chain), and every iframe with a reusable Browser
  selector plus its own probed composition (one level deep, best-effort: an
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
  exact semantics (replaces the whole stack), full backward compatibility.
- **`tests/robot/fiori_hybrid_smoke.robot`** + `fixtures/hybrid_fixture.html`
  (offline, 5/5): four technologies in one page, two REAL nested frame levels,
  composition probe, dom engine click/fill, stack push/pop, `dom=` fallback.

### Added: ECC multi-session registry (2026-07-17)
- **`keywords/_sessions.py`** (SapEccLibrary): named-session registry,
  `Open Sap Session` (second connection by string or Logon entry; optional
  standard `RSYST-*` login with a Robot `Secret` password never logged; alias
  rollback on failure), `Create Gui Session` (second window on the ACTIVE
  connection, scripted `/o`, no re-login hence no multi-logon popup: the
  recommended path for "write in one session, verify in the other"),
  `Switch Sap Session`, `List Sap Sessions` (JSON-safe, never a COM object),
  `Get Active Sap Session`, `Close Sap Session` (isolated teardown, never
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
- Windows deployment pack rebuilt as `dist/sapfx-pack-0.5.7-win.zip`: the new
  keywords travel in the library wheel, pack manifest unchanged. Field note
  learned while validating through MCP (documented in CLAUDE.md): the rf-mcp
  server process freezes both the library class and instance: restart the
  server after changing library code under `src/`.

## [0.5.6] - 2026-07-17

Cross-channel release: the productization-hardening pass below is cut as 0.5.6,
together with three self-contained **demonstration campaigns** driven end-to-end
through rf-mcp then replayed by the real `robot` runner, one per channel. Unit
tests unchanged (677 at 93% coverage: the campaigns are `.robot` example suites,
outside the pytest scope).

### Added: cross-channel demonstration campaigns (2026-07-17)
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

### Changed: productization hardening (2026-07-17)
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

## [0.5.5] - 2026-07-16

Packaging & distribution release: the Windows pack catches up with the July
security-hardening pass and the playwright-praman concept ports below, all
carried by the library wheel (pack rebuilt as `sapfx-pack-0.5.5-win.zip`,
manifest unchanged; the pack READMEs gain an « Environment preflights »
section). Unit tests 617 → 669.

### Added: release tooling (2026-07-16)
- **Comms version-sync guard** (`scripts/check_comms_sync.py`): any version
  cited in `comms/` (docs or deck sources) must equal `pyproject.toml`,
  otherwise exit 1. Deliberately version-only: the version acts as the
  tripwire that forces re-reading the proof numbers and regenerating the
  deck on every release. Born from a real incident (the comms base lived two
  releases behind with a stale test count and nothing flagged it).

### Added: security hardening pass (2026-07-15, from the July tech-watch)
- **Client-side security preflight** (`Get Client Security Status`,
  `Client Security Should Be Hardened`, pure logic in
  `sapfx_common.client_security`): classifies the SAP GUI client against the
  input-history weak-encryption vulnerability (CVE-2025-0055, SAP Note
  3472837: fixed from 8.00 PL9, 8.10+ ships fixed) and detects leftover
  `SAPHistory*.db` input-history databases on the workstation (test runs type
  real data into real fields: that history must be disabled and purged on a
  test workstation). Read-only, locale-independent, MCP-safe dict.
- `Scripting Should Be Fully Enabled` now names the
  `sapgui/user_scripting_per_user` + S_SCR Execute(16) path (SAP's official
  mechanism to confine scripting to dedicated test accounts) when the server
  refuses scripting despite `user_scripting = TRUE`.
- **Hardening guide** `docs/hardening-test-environment.md` (+ `.fr.md`):
  the security checklist of a SAP test setup (RZ11 server posture, client
  patch level & input history, credentials in CI, MV3/CDP/WebView2 surface,
  MCP/agent containment, supply chain), each point mapped to the preflight
  keyword that verifies it.
- **UI5 1.136 legacy-free compat smoke** (`fiori_legacyfree_smoke.robot`,
  4/4 live): exercises the role/xpath engines against the official
  `1.136-legacy-free` CDN build, the LTS with ALL deprecated APIs removed,
  SAP's recommended 2.x-readiness vehicle while 2.0 has no GA date. Unlike
  the nightly smoke this target is stable: a failure is a real regression.
  Completes the compat triptych 1.60 ← 1.136-legacy-free → 2.0-nightly.
- **Strict-CSP injection smoke** (`fiori_csp_smoke.robot`, 3/3 live): a
  fixture whose CSP only allows the UI5 CDN + its own nonce (no
  unsafe-inline, no unsafe-eval) first proves the policy blocks a non-nonce
  `<script>`, then proves the `__SAPFX` bundle (Playwright evaluate → CDP,
  outside page-CSP reach) and the role/xpath engines still work: no CSP
  relaxation ever needs to be requested on a system under test.
- **Work Zone iframe fragility scenarios** (`fiori_frame_smoke.robot` 3→6
  tests, 6/6 live, new `shell_multi_iframe_fixture.html`): two apps in two
  frames (per-frame scoping never leaks), full frame reload (no stale
  context retained), frame navigation to another app (resolution follows
  the new content), the exact bug class wdi5 had to fix twice in
  2025-11/2026-01. Harness lesson encoded in the suite: navigate the
  suite-level page (`Go To`), never `New Page` inside a test (Browser's
  TEST auto-closing reverts the active page between tests).

### Added: playwright-praman concept port (2026-07-15, Apache-2.0, NOTICE)
Four concepts identified by the competitive analysis, re-implemented from
scratch on this project's engines (never ported verbatim):
- **Business vocabulary** (`sapfx_common.vocabulary`, keyword
  `Lookup Business Term` on BOTH libraries): business terms (French and
  English, synonyms included) resolve to {canonical, ABAP field, table,
  domain} with tiered scoring (exact > synonym/field > prefix > fuzzy) and
  an ambiguity-refusal threshold: below-threshold or confusable candidates
  fail WITH the candidate list, never a silent first match. Ships MM/SD/FI +
  the Flight demo model; site terms extend via `extra`.
- **FLP intent navigation** (`Open Fiori App` + resource
  `Open App By Intent`, pure `build_intent_hash` helper): navigate the
  launchpad by `SemanticObject-action` hash, stable across catalog
  reorganizations, theme and language, unlike tile-title clicks (which
  remain as `Open App`, the "as the user does" path).
- **Enterprise IDP login** (`Log In Via Identity Provider`, presets in
  `sapfx_common.auth_flows`): drives SAP IAS / Azure AD / custom login forms,
  detecting single-page vs two-step flows dynamically; counts VISIBLE
  elements only (`>> visible=true`, a two-step form keeps its hidden
  password field in the DOM, presence-counting takes the wrong branch:
  caught live on the fixture); fails naming the blocking step; never logs
  the password. Live-validated 3/3 vs a two-step fake-IDP fixture
  (`fiori_auth_smoke.robot`).
- **LLM/DX surface**: root `llms.txt` (llmstxt.org format) and two bilingual
  migration guides: `docs/migrating-from-sapguilibrary.md` (drop-in rename
  from upstream) and `docs/migrating-from-cbta.md` (concept mapping +
  migration path before Solution Manager maintenance ends 2027-12-31).

### Pending
- **SAP GUI 8.10 validation** (GA is 2026-07-16, the day of this entry):
  re-run the ECC smokes and the native-recorder `ISapSessionEvents` manual
  connection against 8.10 as soon as it is installed on the test workstation
  (the known-sensitive point). 8.00 leaves full support 2027-01-12
  (restricted until 2027-07-31); 8.10 is supported until 2029-06-30.

## [0.5.2] - 2026-07-14

The perception upgrade ships: every improvement below is carried by the
library wheel of the Windows deployment pack (rebuilt as
`sapfx-pack-0.5.2-win.zip`, same manifest as 0.5.0, refreshed content).
The drift sentinel's committable references now include the per-tile
fingerprint (`*.tiles.txt`) next to the signature and global hash;
pre-upgrade references stay readable (the tile channel is simply skipped).

### Added: perception upgrade (2026-07-14, live-validated vs A4H 5/5 + Demo Kit)
- **Element-scoped visual assertion** (`Get Element Perceptual Hash`,
  `Element Should Match Baseline`): the baseline is the PNG *cropped* to one
  element's screen region (the same reading as the coordinate effector), so
  the 64 hash bits cover the opaque GuiShell/chart alone instead of the whole
  screen: the direct answer to the dHash coarse-mesh limitation, and the
  assertion is immune to everything changing elsewhere on the screen.
- **Volatile-zone masking** (`mask_elements=auto|<ids>` on
  `Get Screen Perceptual Hash` / `Screen Should Match Baseline`): status and
  title bars (clock, localized title: the classic snapshot flakiness) are
  filled with neutral gray before hashing, identically on baseline and
  capture. Live-proven: the status-bar bit of the SE16 hash drops out.
- **Tiled fingerprints + drift localization** (`Get Screen Tile Hashes`;
  `sapfx_common.visual_hash` gains pure `crop_pixels`/`mask_regions`/
  `tiled_dhash`/`tiled_hamming`/`tile_rect`): the sentinel
  (`Check Screen Against Watch`) now records a per-tile grid next to the
  global hash and, on later passes, names WHICH tile drifted: position,
  pixel rectangle, and the elements covering it (smallest first). A local
  drift too diluted for the global hash is caught by its own tile; a baseline
  without tiles (pre-upgrade references) simply skips the channel.
- **Smart perception diff** (`pair_renames` on `diff_lines`/`diff_perception`
  and `Get Screen Signature mode=diff`; always on in the sentinel): within a
  changed block, removed/added lines whose ids score ≥ 0.6 on the healing
  similarity are paired into one `~ old -> new  (similarity N%)` line: a
  renumbered subscreen reads as a rename, same-id text changes read as value
  changes (`texte : 'a' -> 'b'`). Live: SE16→SE38 pairs
  `ctxtDATABROWSE-TABLENAME -> ctxtRS38M-PROGRAMM (62%)`.
- **Semantic perception** (`Get Screen Signature mode=semantic`,
  `sapfx_common.semantic.screen_affordances`): the *form view* of a screen,
  one line per actionable target carrying its **verified** human label
  (emitted only when it re-resolves to that single element, `?` otherwise),
  technical id, type and current value. Each line replays directly as
  `Fill Field By Label`/`Click Button By Label`. Live lesson locked in: the
  real SAP GUI marks `Changeable=True` on GuiUserArea and toolbar buttons:
  `is_editable_field` (type-aware) now guards affordances, annotations and
  `describe_element` alike.
- **Annotated screenshot, Set-of-Mark** (`Get Annotated Screenshot`,
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
- **SAP GUI 8.10 validation** (GA is 2026-07-16, after this entry): re-run the
  ECC smokes and the native-recorder `ISapSessionEvents` manual connection
  against 8.10 as soon as it ships (the known-sensitive point).

## [0.5.0] - 2026-07-13

The API channel and the maintenance loop: a third, screen-free channel
(`SapApiLibrary`, OData v2/v4 + optional RFC) next to the two GUI ones, drift
detection without scripted tests (sentinel + visual assertions), and the
telemetry-to-patch bot that turns healing logs into reviewed `resources/`
fixes. The Windows deployment pack ships all of it (see *Deployment pack*
below). Also repairs a version drift the 0.3.0 guard missed:
`SapFioriLibrary.__version__` (class attribute) had stayed at 0.2.5: the
guard now tracks every library class attribute, `SapApiLibrary` included.

### Added
- **Deployment pack refreshed for the new channels**
  (`scripts/build_release_pack.py` + `packaging/`): the library wheel now also
  carries `SapApiLibrary` (and the installer's import smoke check verifies it);
  two new sample suites join the pack: `ecc_drift_sentinel.robot` (the watch
  harness: perceive → compare → Markdown drift report, no test to write) and
  `flagship_cross_paradigm.robot` (the same business fact asserted through the
  screen AND the API); the maintenance tooling ships under `scripts/`
  (`healing_drift_report.py`, `check_spec_sync.py`: both stdlib-only, run
  from the pack root); `requirements-deploy.txt` adds Pillow (visual
  fingerprints of the sentinel and `Screen Should Match Baseline`) and
  documents the optional `pyrfc` prerequisite.
- **Drift sentinel, change detection WITHOUT tests**
  (`sapfx_common.screen_watch` + `Check Screen Against Watch` +
  `tests/robot/ecc_drift_sentinel.robot`): watched screens are remembered
  (structured perception + optional visual fingerprint) and every later pass
  reports ONLY what moved, line by line: a nightly watch surfaces a support
  pack's drift screen by screen before any scripted test fails. Report-only by
  default (`FAIL_ON_DRIFT` opt-in), baselines are committable, extending the
  watch = adding a tcode to a list. Live-validated on A4H: full
  baseline→unchanged→drifted cycle, the simulated drift named (`txtI1-LOW`
  block appearing under the SE16 watch key).
- **The spec is the source of truth** (`scripts/check_spec_sync.py`):
  generated suites carry a provenance marker
  (`Spec: specs/<plan>.md (sha256:<12hex>)`, stamped via `--stamp`, now a
  step of sap-generator's contract); the guard fails when a spec changed
  since generation (stale suite → re-run `/sap-generate`, never hand-edit),
  or when a marker points to a vanished spec; plans without a suite are
  informational. `ecc_scarr_spfli_liaisons.robot` stamped against its spec.
- **Coordinate effector, act where the API is blind**
  (`PointerKeywords`): `Get Element Screen Region` (real screen geometry,
  the perception half an agent crosses with `Get Screenshot As Base64`) and
  `Click Element At Offset` (hardware win32 click at a RELATIVE position
  inside an element: left/right/double, best-effort foreground, logged
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
- **`SapApiLibrary`, the API channel** (third channel next to the GUI desktop
  and web ones, stdlib-only): OData v2 (embedded Gateway) and v4 (CAP/S4) with
  one keyword set (`Open Api Session`, `Get Odata Entities`, `Get Odata
  Count`, `Post Odata` with the SAP CSRF protocol), optional RFC through
  `pyrfc` (`Open Rfc Connection`/`Call Rfc`, helpful error when absent).
  Auto-correctable HTTP errors (status, URL, body excerpt). Rationale: robust
  SAP tests prepare/cross-check data through the API and drive the screen only
  for what they actually test.
- **Cross-paradigm flagship suite** (`tests/robot/flagship_cross_paradigm.robot`),
  the architecture demo: the same business fact asserted through two
  independent channels. The `a4h` leg is **live-validated**: the SE16 "Number
  of Entries" of `SNWD_PD` equals the `$count` of the Gateway
  `SEPMRA_SHOP/Products` service of the same system. The `capsflight` leg
  (first rendered Travel row exists through an OData v4 point query) is
  dryrun-validated only for now: the local `_cap-sflight` clone currently
  wedges on startup (cds-dk 9.9 + cds-plugin-ui5 0.17 hang at UI5 app mount;
  without the plugin the CAP server accepts TCP but never answers), an
  environment regression of the sample clone, to re-validate after refreshing
  it (`fiori_sflight_smoke.robot` is equally affected today).
- **Visual assertions** (`sapfx_common.visual_hash` + perception keywords):
  `Get Screen Perceptual Hash` (dHash over `HardCopyToMemory`, Pillow at the
  decode boundary only, new optional extra `visual`) and `Screen Should Match
  Baseline` (snapshot semantics: first run creates the baseline, then Hamming
  distance vs threshold, `.actual.png` saved next to the baseline on drift,
  auto-correctable failure). Covers exactly what the Scripting API cannot see
  (opaque GuiShell lists, record-only charts). Live-validated on A4H (real
  PNG round-trip; SE16 vs SM50 hashes measurably distant).
- **Healing-drift maintenance bot** (`scripts/healing_drift_report.py`): reads
  the cumulative `SAPFX_HEALING_LOG` JSONL, separates *stable* drifts (same
  locator healed N times to one target: patch in `resources/` located and
  proposed, `--apply` executes) from *unstable* ones (human/sap-healer
  review), exit code 1 as a CI alert signal. Never touches tests, never
  silent. First CLI run on the real repo located `${SE16_COUNT_BUTTON}` and
  proposed the exact 0.3.0 blind-healer scenario patch.
- **Coverage-discovery mode for sap-planner** (agent definitions + regenerated
  chat modes): usage-driven scoping through ST03N's transaction profile
  (perceive→act, grid keywords), honest fallback for fresh trials without
  collector history, ranked `specs/couverture-proposee.md` roadmap.

- **Embedded-browser-control bridge (ECC)**: new `EmbeddedBrowserKeywords`
  mixin: `Enable Embedded Browser Debugging` (sets
  `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` before `Open Sap Logon`/the SAP
  client starts), `Get Embedded Browser Page Id` and `Switch To Embedded
  Browser Page` (locate/activate, via the Browser library over CDP, the page
  hosted by a WebView2 control embedded in a SAP GUI/Business Client window).
  Workflow documented by RoboSAPiens (imbus, Apache-2.0, see `NOTICE`); reuses
  the same `BuiltIn().get_library_instance("Browser")` access pattern as
  `SapFioriLibrary`.
- **Enriched human-locator grammar (ECC)**: `sapfx_common.semantic` gains
  grid/position addressing (`N @ Label` / `Label @ N`: the Nth field of a
  vertical/horizontal grid below/right of a label) and the scoped-anchor
  operator (`Anchor >> Rest`: narrows resolution to the neighborhood of a
  unique label, recursively resolving `Rest` with any grammar form, including
  a nested `>>`). Covers RoboSAPiens' "non-unique label near a unique anchor"
  and "unlabelled field identified by its tooltip near a unique anchor" cases,
  reimplemented as neighborhood scoping rather than ported verbatim (see
  `NOTICE`). `Find Element By Label` and friends document the extended
  grammar. 519 unit tests (was 483).
- **Scope reach is an intent, not a tolerance**: the `>>` neighborhood radius
  (default 100 px, unchanged) is now a parameter: `scope_radius` on
  `resolve_semantic` and on all four `… By Label` keywords (alignment
  tolerances stay deliberately unexposed: they are rendering noise, the scope
  radius is what the author *means* by "near"). Nested `>>` inherits the
  radius; scopes intersect. When a `>>` locator fails, the error now embeds a
  scope diagnosis (`scope_hint`, pure and unit-tested): anchor unknown,
  anchor ambiguous, anchor without geometry, or target beyond the radius,
  naming the radius used and the remedy. Validated live on A4H:
  `MTEXT >> = 200` fails at 100 px with the diagnosis, resolves
  `txtMAX_SEL` at `scope_radius=500` across the real SE16 screen.

### Changed
- **`Read Field By Label` resolves changeable fields first** (cascade, same
  "first step that matches wins" principle as the grammar): grid positions now
  count the same fields as `Find`/`Fill` (`MTEXT @ 2` = the HIGH bound for all
  three, live-validated round-trip Fill→Read with one locator), while
  read-only fields remain readable as the fallback, the way display dynpros
  render their values. Ambiguity within the winning pass is still raised,
  never resolved silently.

### Fixed
- **`SapFioriLibrary.__version__` (class attribute) had drifted to 0.2.5**,
  the exact 0.3.0 scenario again, on the other library: the version guard
  (`tests/unit/test_version_consistency.py`) only tracked `SapEccLibrary`'s
  class attribute. It now tracks the class attribute of every library
  (`SapEccLibrary`, `SapFioriLibrary`, `SapApiLibrary`) alongside the
  `__init__` and the two `pyproject.toml`.
- **`Fill Field By Label` could target a read-only field** (found while
  validating the grid grammar live on a real SE16/T000 selection screen): the
  explicit input-type filter re-admitted non-changeable text fields (the
  screen's "to" separators) as grid positions, so `MTEXT @ 2` resolved to the
  separator for Fill (raw COM `AttributeError`) while resolving to the HIGH
  bound for Find. `resolve_semantic` gains `changeable_only` (targets only,
  never anchors); `Fill Field By Label` enables it, making Find and Fill count
  the same grid positions. Read follows through the changeable-first cascade
  (see *Changed*), keeping read-only fields readable as the fallback.

## [0.4.0] - 2026-07-13

Human locators, perception fast path and the semantic recorder: the outcome of
the comparative review of [RoboSAPiens](https://github.com/imbus/robotframework-robosapiens)
(imbus, Apache-2.0; techniques ported with attribution, see `NOTICE`) and
sapient-mcp (ideas only, no license). Both distributions and all package
`__version__` attributes move to 0.4.0.

### Added
- **Human locators (ECC)**, new `SemanticKeywords` mixin: `Find Element By
  Label`, `Fill Field By Label`, `Read Field By Label`, `Click Button By Label`
  target controls by **visible label + geometric proximity** (grammar:
  `Label`, `@ Label` = below, `Left @ Top` = intersection, `= content`;
  `exact=False` = case-insensitive prefix, tooltip-shortcut friendly). Pure
  resolution engine in `sapfx_common.semantic`. Deliberate difference from
  RoboSAPiens: **ambiguity is reported with the candidate list, never resolved
  silently to the first match**; zero-match errors list the labels actually on
  screen (self-correcting errors). Ids remain the nominal path in `resources/`.
- **`GetObjectTree` perception fast path**: `sapfx_common.object_tree`
  flattens the Scripting API's JSON subtree (one COM round-trip instead of one
  per control, geometry included); `Get Screen Signature`, healing candidates
  and the semantic engine all ride it, with automatic fallback to the
  historical COM walk (AttributeError = API absent, remembered; com_error =
  transient, retried). `Get Screen Signature` gains `include_geometry=True`
  (optional 4th column, 3-column default contract unchanged).
- **Label-anchored healing**: `Resolve Element With Healing` accepts
  `label=<visible label>`: when id-similarity stays below the threshold, a
  label that uniquely re-resolves repairs the locator (WARNING + telemetry
  `engine=label`). A visible label survives the subscreen renumbering that
  kills ids.
- **In-memory screenshots (ECC)**: `Get Screenshot As Base64`
  (`HardCopyToMemory`, MIME re-checked by magic bytes, MCP-safe string) and
  `Log Screenshot` (data-URI inline in the Robot log, self-contained
  log.html). rf-mcp guidance updated; `get_application_state` now reports the
  **live** transaction and connection state (read from the real session, never
  an optimistic state machine).
- **Semantic recorder (`--semantic`, native engine)**: each recorded step is
  rewritten as a human keyword (`Fill Field By Label    Table Name    T000`)
  when the label computed at event time **provably re-resolves** to the same
  element (`sapfx_common.semantic.describe_element`; a changeable field's text
  is its volatile value and is never used as a locator); the technical id
  stays as a trailing comment. Known vkeys get readable comments (`# F8`);
  `--screenshots` prefers `HardCopyToMemory` (faithful window image, extension
  from magic bytes) over the GDI fallback.
- **ALV row addressing by content**: `Get Cell Value By Row Content` (the
  `content @ column` idea applied to grids: no row index in tests) and
  **`Read Abap List`**, classic list output read by geometric row
  reconstruction (`sapfx_common.abap_list`).
- **Client-side preflight**: `Get List Rendering Status` and `Abap List
  Should Be Readable` (`_diagnostics.py`): the client-side counterpart of the
  server-side scripting preflight. Live-checked on A4H / SAP GUI 8.00: modern
  list screens (RSPARAM output) render inside an opaque `GuiShell` exposing
  **zero labels** unless SAP GUI **accessibility mode** is on, so
  `Read Abap List` cannot reconstruct anything. That mode **cannot be flipped
  from a test** (verified: `SAP_ACCESSIBILITY=1` has no effect; it is a
  per-Windows-user client option requiring a GUI restart), so, exactly like
  RZ11 server-side, it is **provisioned** and merely **observed**: the
  preflight reports `accessibility_mode_needed` and names the option to enable.
  A shell *with* labels (a legitimate ALV screen) is correctly reported as
  needing nothing.
- **Agents updated**: planner records visible labels next to fields,
  generator probes locators with `Find Element By Label`, healer uses label
  anchors; VS Code chat modes regenerated. `docs/architecture.md` documents
  the new layers plus an exploration note: driving SAP GUI's embedded
  **WebView2** panes via Browser/CDP (bridge between both channels; revisit
  after SAP GUI 8.10 GA).

### Fixed
- **`SapEccLibrary.__version__` class attribute** had silently stayed at 0.2.5
  through the 0.3.0 release: the version-consistency guard only covered the
  package `__init__` files. The class attribute is now tracked by
  `tests/unit/test_version_consistency.py` too.
- rf-mcp ECC signature filtering now tolerates the optional geometry column
  (4-column lines) instead of skipping filtering on them.

## [0.3.0] - 2026-07-12

Both distributions (`robotframework-sapecclibrary`, `sap-robotmcp`) move to
0.3.0, and (for the first time actually enforced) so do ALL three package
`__version__` attributes (`SapEccLibrary`, `SapFioriLibrary`, `sapfx_common`);
see the version-drift fix below. The MV3 extension stays at 0.4.1 (unchanged).

### Added
- **SAP test agents (plan → generate → heal)**: transposition of the
  [Playwright Test Agents](https://playwright.dev/docs/test-agents) principle
  to this ecosystem, on top of rf-mcp: `sap-planner` (explores the live system
  through the perception→action loop and writes a business-readable plan under
  `specs/`), `sap-generator` (turns a plan into a suite under `tests/robot/`,
  executing every step live before writing it; missing business keywords land
  in the resources layer, never raw ids in tests) and `sap-healer` (reproduces
  a failure, reads the scored closest-match suggestions and the
  `SAPFX_HEALING_LOG` telemetry, verifies the fix live, then patches
  `resources/`, not the tests, never silently). Canonical definitions in
  `.claude/agents/` + `/sap-plan`, `/sap-generate`, `/sap-heal` commands for
  Claude Code; VS Code / Copilot **chat modes generated** from that single
  source by `scripts/regen_agent_definitions.py` (`--check` drift guard wired
  into pytest). `specs/` holds the plans (French, deliberately
  single-language: `check_bilingual_docs.py` gains prefix exemptions) with a
  reference example matching the live-validated SFLIGHT/SE16 flow. Bilingual
  walkthrough: `docs/test-agents.md`.
- **Deployment pack: the agents ship with the pack**, `.claude/agents`,
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
  produced `specs/scarr-spfli-liaisons-se16.md`: 18 carriers / 14 connections
  observed, selection screens surveyed field by field; sap-generator turned it
  into `tests/robot/ecc_scarr_spfli_liaisons.robot` (7 scenarios, relational
  assertions, **7/7 live**, independently re-run), probing every locator live
  before writing it; sap-healer, blind-tested against a simulated screen drift
  (`btn[31]` → `btn[13]` in the resource), reproduced the 4 failures, diagnosed
  through live perception (toolbar signature naming « Number of Entries ») plus
  the scored closest matches (`Get Closest Element Ids`), patched the single
  resource line (zero test edits) and re-ran to **7/7**.
- **ECC filtered-selection keywords** (`resources/ecc_keywords.resource`,
  written by the generator, locators verified live first): `Display Table
  Contents With Filter` (named criteria resolved through per-table
  `&{<TABLE>_SELECTION_FIELDS}` dictionaries, SCARR I1–I4 and SPFLI I1–I15
  mapped with their exact `ctxt`/`txt` element types), `Count Flight
  Connections For Airline`, `Displayed Grid Should Contain Columns`
  (technical column ids, never localized titles) and `Read Column Values From
  Displayed Grid` (ordered list or sorted unique set).
- **Version-consistency guard** (`tests/unit/test_version_consistency.py`):
  both `pyproject.toml` files and the three package `__version__` attributes
  must carry one identical version, and `CHANGELOG.md` must have a dated
  section for it: the suite now fails on any future release drift.

### Fixed
- **`install.ps1`: latent em-dash parse bomb.** The installer is UTF-8 without
  BOM but Windows PowerShell 5.1 reads it as ANSI; the em dash in the import
  smoke-check string mojibakes to `â€”`, whose `”` is treated by PowerShell as
  a closing quote, silently unbalancing every string literal after it. All
  typographic characters are now banned from the file (rule documented in its
  header) and the string uses an ASCII dash.
- **Library version drift**: the 0.2.0 and 0.2.5 entries below claimed
  `__version__` bumps that never actually landed: `SapEccLibrary` and
  `sapfx_common` were still at 0.1.0 while `SapFioriLibrary` had run ahead to
  0.3.0. All normalized to 0.3.0; the new version-consistency guard turns any
  recurrence into a red unit suite.

## [0.2.5] - 2026-07-12

Both distributions (`robotframework-sapecclibrary`, `sap-robotmcp`) and both
library `__version__` attributes move to 0.2.5; the MV3 extension moves to
0.4.1 (regenerated recorder embedding the Web Components capture).

### Added
- **Web Components engine, third Fiori resolution engine** (`Resolve Wc
  Control`, `Click Wc Control`, `Fill Wc Input`, `Get Wc Text`, `Wc Control
  Should Be Visible`, `Get Wc Match Count`). Pages built on **UI5 Web
  Components** (SuccessFactors home, ui5-webcomponents apps) have NO classic
  UI5 runtime: the element registry is empty and the role/xpath engines are
  blind there. The new engine scans light-DOM custom elements (`ui5-*`
  prefix), matches short types (`tag=Button`) against plain AND **scoped**
  tags (`ui5-button-<suffix>`), attributes/properties (same case-insensitive
  substring + bounded `/regex/` matcher as the role engine, now shared as
  `valueMatches`), `text`, `id`/`idSuffix`, and returns CSS light-DOM paths
  anchored at the closest id (WC hosts often have no id of their own).
  Playwright's shadow-piercing CSS handles the click/fill through the open
  shadow roots. `Resolve Ui5 With Fallback` gains `wc=` as the last link of
  the chain (role → xpath → sid → wc); the web recorder captures/records WC
  hosts (`Click Wc Control`, Alt+click assertions, fill) on registry-less
  pages, with matching hover highlight. Validated live against a local
  offline fixture (`fiori_wc_smoke.robot`, 6/6, includes a genuine scoped
  tag and shadow-DOM piercing), no SAP, no network.
- **Healing telemetry** (`sapfx_common.healing_telemetry`, typed): opt-in
  cumulative JSONL journal of locator repairs (`SAPFX_HEALING_LOG=<path>`),
  fed by BOTH channels: ECC `Resolve Element With Healing` (with score) and
  Fiori `Resolve Ui5 With Fallback` (with the healing engine). Reading it
  across runs shows which locators drift recurrently, turning healing into a
  preventive-maintenance tool for `resources/`. Best-effort by contract:
  never fails a test, never records typed values.
- **Strict rf-mcp session isolation (opt-in)**: with
  `SAPFX_MCP_STRICT_SESSION=1`, the ECC state provider now REFUSES to serve
  perception for a second concurrent rf-mcp session (first-come,
  first-served, explicit error naming both sessions and the variable)
  instead of only logging the cross-session sharing warning: the documented
  "one live ECC session per rf-mcp process" rule becomes enforceable.
- **Deployment pack: self-contained data-exploration sample**
  (`tests/robot/business_data_exploration.robot`): the SE16 exploration
  campaign (domain catalogs, dynamic TADIR inventory, per-table "Number of
  Entries" verification) as a single standalone suite with zero dependency
  on `resources/`, deliberately deviating from convention #1 so the pack
  ships a real-data example runnable without the repo. Included as the third
  sample suite by `build_release_pack.py`.
- **Project logo** (`assets/logo.png`, 512 px master with transparent circular
  cutout) applied across every user-facing surface: README banners (EN/FR), the
  desktop recorder's Tkinter window icon (`tools/recorder/assets/icon.png`,
  best-effort `iconphoto`), and the MV3 extension (toolbar icons 16/48/128 +
  popup header: the 16 px icon crops to the robot face for legibility).
  `gen_icons.py` now derives all icon sizes from the committed master (Pillow,
  dev-only dependency) instead of drawing a generic magnifier.

### Changed
- **CI**: the Windows job now also runs the unit suite against the REAL
  pywin32 before the Robot dry run: `tests/unit/conftest.py`'s stubs only
  install when the authentic modules are missing, so this catches any drift
  between the COM fakes and reality (the ubuntu job keeps the coverage gate).
- rf-mcp guidance: fallback hint extended to the wc engine; new hint routing
  agents to `Resolve/Click/Fill Wc …` on registry-less Web Components pages;
  `SapFioriPlugin` keyword map and capabilities updated accordingly.

## [0.2.0] - 2026-07-12

First tagged release. Both distributions (`robotframework-sapecclibrary`,
`sap-robotmcp`) and both library `__version__` attributes move to 0.2.0; the
MV3 extension moves to 0.4.0 (its store versioning was already ahead).

### Added
- **Desktop recorder: native event engine** (`--engine auto|native|poll`).
  `--record` now uses the Scripting API's own Record mode (`GuiSession.Record`
  plus `Change` events, the mechanism behind ALT+F12): SAP GUI itself emits the
  exact command (`SP` set-property / `M` method call) before each server
  roundtrip, so button presses, ALV grid/tree/tab/context-menu interactions
  and the exact submit action are captured (the polling engine inferred
  `Send Vkey 0`). OK-code + Enter collapses into a single `Run Transaction`;
  passwords are never recorded; unmapped calls are kept as exact-call comments
  (never lost). `--capture` gains the API's hit-test mode
  (`elementVisualizationMode` + `Hit` events, plus `FocusChanged`), true
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
  T000`, and the exact `Click Element wnd[0]/tbar[1]/btn[8]` (F8), the case
  the polling engine could never capture.
- **Scripting preflight (ECC)**: `Get Scripting Status` and `Scripting Should
  Be Fully Enabled` read the API's real state (`GuiConnection.DisabledByServer`,
  `ScriptingModeReadOnly`, `ScriptingModeRecordingDisabled`, `UI_GUIDELINE`,
  GUI version) and fail EARLY with the exact RZ11 parameter to fix: these
  server profile modes otherwise degrade automation silently. Plus
  `Enable Test Tool Mode` (suppresses I/A message popups at replay, immediate
  update mode, designed by SAP for test tools) and `Get Session Telemetry`
  (ResponseTime/InterpretationTime/RoundTrips/Flushes per roundtrip).
- **Locator self-healing (unified ECC ↔ Fiori)**: new `sapfx_common.healing`
  (typed, pure) scores SAP GUI ids by terminal-field-name (heavy weight) +
  character-level path LCS + control type: a renumbered subscreen
  (`SAPLMEGUI:0013` → `:0015`) stays above the healing threshold. ECC:
  `Resolve Element With Healing` (repairs with a logged WARNING, never
  silently; returns a plain string, MCP-safe) and `Get Closest Element Ids`;
  `Wait Until Element Present` failures now list the closest ids on screen
  (self-correcting errors, UiPath "closest matches" / MCP SEP-1303 pattern).
  Fiori: `Resolve Ui5 With Fallback` (role → xpath → sid chain, per-engine
  timeout, healed engine logged) and no-match errors now say whether the
  controlType is rendered at all (properties drift vs. wrong screen).
- **Diff-mode perception**: `Get Screen Signature` and `Get Ui5 Page Tree`
  accept `mode=diff` and then return only what changed since the
  previous perception (`-`/`+` lines, unchanged summarized) via the shared
  `sapfx_common.perception_diff`: the screen is always re-read (never a state
  cache); only the rendering differs. Guidance hints updated so rf-mcp agents
  prefer diff after an action.
- **Work Zone / cFLP iframe support (Fiori)**: `Set Ui5 Frame <selector>`
  scopes all resolution to the app iframe: the JS bundle now runs inside the
  frame's context (two-arg `build_call` form: Browser's `Evaluate JavaScript`
  with a selector executes in the element's frame) and every returned selector
  is prefixed with `<frame> >>>` (Playwright frame piercing, crosses origins).
  Validated live by the new `tests/robot/fiori_frame_smoke.robot` (3/3) against
  `fixtures/shell_iframe_fixture.html`, a UI5-less shell embedding the app in
  a genuinely cross-origin iframe (file:// origin "null"), the Work Zone
  structure. The MV3 extension now injects the recorder into **all frames**
  (`allFrames: true`; panel titles get an `[iframe]` tag).
- **Fiori Elements V4 stable-id support**: new `idSuffix` selector key.
  Matches the END of the control id, the documented FE pattern
  (`fe::table::<Entity>::LineItem::Table`; the app/route prefix varies, the
  suffix doesn't). The web recorder's capture now recognizes FE ids and emits
  `idSuffix=fe::…` selectors instead of the "dynamic id, likely fragile"
  fallback.
- **UI5 2.x readiness, proven live**: new `tests/robot/fiori_ui5v2_smoke.robot`
  (4/4 live) runs SapFioriLibrary against the **OpenUI5 2.0 nightly** CDN build
  (`fixtures/ui5_v2_fixture.html`). Proves the `ElementRegistry`-module branch
  of `registryForEach` and that no library path depends on a removed legacy API
  (`sap.ui.getCore()` façade, `Element.registry`, `sap.ui.version` global).
  Symmetric counterpart of `fiori_legacy_smoke.robot` (1.60): the library now
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
  call: page-level or frame-scoped). Regenerate custom snippets with
  `python -m SapFioriLibrary.regen_recorder`.
- `SapEccLibrary.__version__`/`SapFioriLibrary.__version__` aligned to the
  distribution version (0.2.0).
- Documentation refreshed for 0.2.0 across the bilingual set (root README,
  `docs/architecture`, `docs/fiori-architecture`, `docs/mcp-integration`,
  `docs/sap-test-data` §5, both recorder READMEs, extension, packaging,
  rf-mcp plugin READMEs), including the previously stale `tools/spy*` paths and
  the pre-0.2.0 ECC mixin list. Deployment pack rebuilt as
  `dist/sapfx-pack-0.2.0-win.zip`.

### Live validation (A4H Docker, 2026-07-12)
- ECC smokes re-run: `ecc_smoke.robot` 5/5, `ecc_data_smoke.robot` 4/4,
  `ecc_record_smoke.robot` 1/1, plus the native-events end-to-end `--record`
  session described above.

### Known gaps (tracked)
- SAP GUI **8.10** (GA 2026-07-16) validation pending: the stack is currently
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
  hints vs. CLAUDE.md conventions), consistency guards, not generators.
- Progressive `mypy` typing (`sapfx_common`, `SapFioriLibrary/_ui5_runtime.py`,
  the rf-mcp perception modules), scope in `[tool.mypy]` (`pyproject.toml`).
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
- rf-mcp state providers: perception **compaction** (`_last_seen.py`:
  byte-identical consecutive `get_page_source` calls return a compact marker
  instead of the full text) and a real **`filtered`/`filtering_level`**
  implementation (`_filtering.py`, minimal/standard/aggressive, mirroring the
  real Browser provider's progression; ancestor-preserving prune for the UI5
  tree): both were part of rf-mcp's `LibraryStateProvider` contract but
  previously accepted and silently ignored.
- **SE16 exploration keywords + campaign suite, validated live** (agent-driven
  discovery through rf-mcp on the A4H): `Count Table Entries` (« Number of
  Entries », btn 31 / `G_DBCOUNT`, reliable on empty tables), `Read Domain
  Values` (DD07L), `List Repository Tables` (TADIR), `Try/Open Table Selection
  Screen` (handles the > 40-fields field-choice dialog dynamically; classifies
  structures via status type `E`). New `tests/robot/ecc_exploration.robot`
  (6/6 live vs A4H Docker): locks the delivery-class catalog (A/C/E/G/L/S/W)
  and table-class catalog (TRANSP/INTTAB/VIEW/APPEND, POOL/CLUSTER gone on
  S/4), inventories the flight (27) and EPM (114) TADIR objects and
  deep-verifies each one through SE16; sweeps tagged `deep`.
- `sapfx_common` package: shared `poll_until` / `retry_call` / `retry_until`
  synchronisation primitives used by both `SapEccLibrary` and `SapFioriLibrary`
  (previously three near-identical inline implementations).
- **Data-driven smokes, validated live**: `tests/robot/ecc_data_smoke.robot`
  (4/4 vs A4H Docker, SFLIGHT/SPFLI/EPM through SE16 ALV grid, technical column
  ids only) and `tests/robot/fiori_sflight_smoke.robot` (2/2 vs local cap-sflight).
- SE16/SE38 business keywords: `Display Table Contents`, `Read Displayed Grid`,
  `Run Report`, `Use ALV Grid In Data Browser` (A4H's SE16 default output is a
  classic list with no scriptable grid; SE16N does not exist on A4H).
- `resources/a4h_demo_data.resource`: `Ensure Flight/EPM Demo Data Exists`
  conditional generators (SAPBC_DATA_GENERATOR, SEPM_DG).
- `robot.toml` (`python-path`): RobotCode IDE and CLI resolve libraries identically.
- **MCP server config committed**: `.vscode/mcp.json` (VS Code/Copilot agent mode)
  and `.mcp.json` (Claude Code) both launch `robotmcp --transport stdio
  --without-frontend` with the project PYTHONPATH, stdio handshake verified.
  Plus `.vscode/settings.json` (Pylance paths, pytest) and `extensions.json`;
  `.gitignore` now whitelists these three `.vscode` files.
- **rf-mcp plugins hardened**: routing maps now cover the full public keyword
  surface of both libraries (the historical `Fill Sid` typo, real keyword is
  `Fill Sid Input`, is fixed and now caught by an anti-drift test that checks
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
  `Close SAP`, `Popup Is Present`, `Confirm Popup`, `Cancel Popup`, plus an
  ECC ↔ Fiori keyword mapping table in the resource documentation.
- Unit tests for previously uncovered keywords: `Open Sap Logon`, `Close Sap Logon`,
  `Open Connection By String`, `Get Cell Value By Column Title`, the WebGUI `sid`
  wrappers, `regen_recorder`, and the new `sapfx_common.polling` module.
- Tooling: ruff configuration (`pyproject.toml`), `.pre-commit-config.yaml`,
  `.editorconfig`, `[tool.pytest.ini_options]` (no more manual `PYTHONPATH=src`).
- AI-assistant supports: `AGENTS.md`, `.github/copilot-instructions.md`
  (kept in sync with `CLAUDE.md`, convention 7).
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
  (`\D`) was silently defanged by Robot Framework's own backslash escaping:
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

## [0.1.0] - initial development line
- Phase 1 `SapEccLibrary` (vendored upstream + mixins) and phase 2 `SapFioriLibrary`
  (UI5 role/XPath engines, WebGUI sid), business resources, recorders (desktop +
  web/MV3 extension), rf-mcp plugins, bilingual docs. See `CLAUDE.md` status list.
