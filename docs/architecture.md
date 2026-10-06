> **🇬🇧 English** · [🇫🇷 Français](architecture.fr.md)

# Architecture

## Two SAP paradigms, one test vocabulary

SAP exposes two automation worlds that share almost nothing at the technical level:

- **Desktop GUI (ECC, and the SAP GUI front-end of S/4HANA)**: driven through the
  **SAP GUI Scripting API**, a COM automation interface reached from Python via
  `win32com`. Synchronous, id-addressed (`wnd[0]/usr/txtRSYST-BNAME`).
- **Web (Fiori / S/4HANA / SAPUI5)**: a browser app driven through Playwright
  (Robot Framework Browser library). Async DOM, dynamic ids.

We do **not** try to unify these underneath. We unify them **above**, in Robot
Framework, where a keyword is the abstraction:

```
          ┌───────────────────────────────────────────────────────────────┐
          │   Tests  (tests/robot/**/*.robot)                              │
          │   speak business language only                                 │
          └────────────────────────────┬──────────────────────────────────┘
          ┌────────────────────────────┴──────────────────────────────────┐
          │  Business keywords (resources/*.resource)                      │
          │  ecc_keywords  +  fiori_keywords  +  api_keywords              │  ← one vocabulary
          └───────┬─────────────────┬─────────────────────┬───────────────┘
      ┌───────────▼────────┐ ┌──────▼─────────────┐ ┌─────▼──────────────┐
      │  SapEccLibrary     │ │  SapFioriLibrary   │ │  SapApiLibrary     │
      │  COM / win32com    │ │  + Browser library │ │  stdlib HTTP       │
      └───────────┬────────┘ └──────┬─────────────┘ └─────┬──────────────┘
   SAP GUI Scripting API      SAPUI5 runtime (sap.ui.*)   OData v2/v4, RFC
```

The three channels are peers, and they share no locator. Each library keeps the
locator of its technology: a SAP GUI scripting id
(`wnd[0]/usr/ctxtDATABROWSE-TABLENAME`), a UI5 control selector
(`controlType=sap.m.SearchField`), an OData entity set. That is deliberate. The
API channel has no screen at all, which is exactly why it is worth having,
since the cheapest way to set up or cross-check data is not to drive a screen;
and a lowest-common-denominator locator, the displayed label, would change with
the logon language. What is shared below are contracts, in `sapfx_common`: one
completeness rule for extracting a table whatever the channel, one message
identity (`MO/E/402`) on the screen and over RFC, and, for the two screen
channels, the same perception → action loop and one locator-repair log.

The channel then becomes a choice of business keyword. In this cross-channel
test, each keyword is written in a resource file on top of one library (SE16
through SAP GUI scripting for the first, an OData `$count` for the second), and
the test only names the fact it checks:

```robotframework
Product Count Is The Same On Screen And Through The API
    ${on_screen}=    Count Table Entries        ${EPM_PRODUCTS_TABLE}    # SAP GUI, SE16
    ${via_api}=      Count Business Entities    ${EPM_PRODUCTS}          # OData $count
    Should Be Equal As Integers    ${via_api}    ${on_screen}
```

## ECC library internals (`src/SapEccLibrary`)

Composition by mixins, without a base class (abridged):

```
SapEccLibrary(ConnectionKeywords, WaitKeywords, GridKeywords,
              PerceptionKeywords, DiagnosticsKeywords, HealingKeywords,
              SemanticKeywords, EmbeddedBrowserKeywords, ...,
              GridCellKeywords, ElementKeywords, InputKeywords,
              ValueCheckKeywords)
```

- **The 37 keywords of robotframework-sapguilibrary** (Apache 2.0, see
  `NOTICE`) live in our own mixins since 6 October 2026: `_elements`,
  `_inputs`, `_value_checks`, `_grid_cells`, plus connection, waits and the
  on-error screenshot. Their code, first vendored verbatim, was absorbed and
  rewritten (writes read back, no focus moved by a check, the SAP window
  captured instead of the whole screen); their names and signatures are
  pinned by a unit test, so suites written for the upstream library run
  unchanged. See [audit-upstream.md](audit-upstream.md).
- **Mixins** (`keywords/_*.py`) each carry one capability and call each other
  through `self`; the four mixins of the absorbed keywords sit last in the MRO:
  - `_connection`: autonomous bootstrap (Logon Pad, retry connect, `CoInitialize`
    for off-main-thread execution such as rf-mcp).
  - `_waits`: real synchronisation (`session.Busy` + element polling); failures
    append **closest-match suggestions** (scored by `sapfx_common.healing`) so an
    agent (or a human) can self-correct a near-miss id.
  - `_grid`: ALV ergonomics (by column *title*, `Read Grid` → list of dicts,
    row addressing by **content**: `Get Cell Value By Row Content`), plus
    `Read Abap List` for classic list output (no scriptable grid object:
    rows reconstructed geometrically from the positioned labels).
  - `_perception`: `Get Screen Signature` (read-only text view of the live screen;
    `mode=diff` returns only what changed since the previous perception;
    `pair_renames=True` upgrades it to the **smart diff**: removed/added lines
    whose ids score close on the healing similarity are paired into a single
    `~ old -> new` rename line, so a renumbered subscreen reads as a rename,
    not forty changes; `mode=semantic` returns the **form view**: one line
    per actionable target with its *verified* human label next to the
    technical id, the perception an agent can replay directly as
    `Fill Field By Label`; optional geometry column). Uses the `GetObjectTree`
    **fast path** (one COM call for the whole subtree) with automatic fallback
    to the node-by-node COM walk. Also the in-memory screenshots
    (`Get Screenshot As Base64`, `Log Screenshot`: data-URI inline in the
    Robot log), the **annotated screenshot** (`Get/Log Annotated Screenshot`,
    Set-of-Mark: numbered boxes over every actionable target + a
    `number -> id` legend; a vision agent reads the number and feeds the id to
    a deterministic keyword instead of guessing coordinates) and the **visual
    assertions** (`Get Screen Perceptual Hash`, `Screen Should Match Baseline`:
    snapshot semantics over a pure dHash, `sapfx_common.visual_hash` +
    shared `sapfx_common.visual_baseline`; Pillow only at the image boundary,
    optional extra `visual`; `mask_elements=auto` neutralizes the legitimately
    volatile status/title bars before hashing). The pixel channel gains three
    precision tools: `Get Element Perceptual Hash` /
    `Element Should Match Baseline` (the hash grid covers ONE element's
    cropped region: a change inside an opaque GuiShell weighs on all 64 bits
    instead of being diluted into the whole screen) and
    `Get Screen Tile Hashes` (one fingerprint per tile of a 4×4 grid: drift
    gets **localized**, not just detected). A perceptual hash encodes the
    **capture geometry** as much as the content, so `per_resolution=True`
    keeps one committed baseline per geometry (`<name>@1920x1032.png`) and a
    suite stays comparable across workstations that do not render the same
    size; without the option, a failure whose two geometries differ says so
    rather than reading as a functional regression. The pixel channel covers
    exactly what the Scripting API cannot see: opaque GuiShell list rendering,
    record-only charts.
  - `_diagnostics`: scripting **preflight** (`Get Scripting Status`,
    `Scripting Should Be Fully Enabled`, which fails early with the exact RZ11
    parameter to fix), `Enable Test Tool Mode`, `Get Session Telemetry`.
  - `_healing`: locator **auto-healing** (`Resolve Element With Healing`: repairs
    above a similarity threshold with a logged WARNING, never silently; a
    `label=` anchor adds a label-based repair path: a visible label survives
    the subscreen renumbering that kills ids; `Get Closest Element Ids`). Pure
    scoring lives in `sapfx_common.healing`.
  - `_semantic`: **human locators** (ported from RoboSAPiens, Apache 2.0, see
    `NOTICE`): `Find/Fill/Read Field By Label`, `Click Button By Label` target
    controls the way a business user describes them (visible label + geometric
    proximity; grammar `Label`, `@ Label`, `Left @ Top`, `= content`,
    grid positions `N @ Label` / `Label @ N`, and the scoped anchor
    `Anchor >> Rest`: resolution narrowed to a unique label's neighborhood,
    radius exposed as the `scope_radius` intent parameter, failures diagnosed
    by `scope_hint`). Deliberate difference from RoboSAPiens: ambiguity is
    **detected and reported with the candidate list**, never resolved silently
    to the first match. Fill targets only changeable fields (a read-only "to"
    separator is never a grid position); Read prefers changeable fields, then
    falls back to read-only ones (display dynpros). Ids stay the nominal path
    in `resources/`.
  - `_embedded_browser`: the **embedded-browser-control bridge** (WebView2/CDP
    workflow documented by RoboSAPiens, see `NOTICE`): `Enable Embedded
    Browser Debugging` before the SAP client starts, then `Switch To Embedded
    Browser Page` hands the page hosted by a WebView2 control inside a SAP
    GUI/Business Client window to the **Browser library over CDP**: the two
    channels of this project bridged through one suite.
  - `_pointer`: the **coordinate effector**, the deterministic-first /
    hardware-last-resort hybrid for what the Scripting API officially cannot
    script (opaque GuiShell interiors, record-only charts, drag & drop):
    `Get Element Screen Region` gives the real screen geometry (the
    perception half: an agent crosses it with `Get Screenshot As Base64` to
    decide *where*), `Click Element At Offset` performs a hardware win32
    click at a position **relative to the element** (survives window moves;
    logged, never silent). Ids and labels stay the nominal path.
  - `_trees`, `_combobox`, `_menus`, `_grid_actions`, `_windows` (2026-09-07,
    the lot that closed the SAP GUI capability register): **trees**
    (`Read Tree Nodes`, `Select Tree Node By Text`/`By Path`, opaque keys kept
    as is, column trees read through their `TEXT` column), **combo boxes by
    technical key** (`Select Combo Box Entry By Key`, `Get Combo Box Entries`)
    plus the **user's formats** (`Get User Formats` from SU3, `Input Date`
    and `Input Number` converting ISO/technical input to what the dynpro
    accepts), the **menu bar by path** (`Select Menu Item`), **grid actions**
    beyond reading (`Double Click Grid Cell`, context menu by function code,
    toolbar inventory, `Sort Grid By Column`) and **modal windows**
    (`Dismiss Modal Window`: several SAP dialogs refuse `sendVKey`, the
    fallbacks press the right button and the disappearance is verified).
    The perception itself shows `GuiShell/<SubType>`, refuses to serve a
    ProgID as a value, and FAILS naming the cause when the session is
    unreadable instead of returning an empty view; the STA rail re-attaches
    the session per thread. Pure logic in `sapfx_common.tree_nodes`,
    `menu_path`, `combo_box`, `user_formats`.
  - `_identity` (same evening): **the system identity read on screen**
    (`Get System Identity`, `System Identity Should Be`), the SAP GUI mirror
    of the RFC channel's `Read System Identity`: "System: Status" opened BY
    POSITION (the System menu is the second-to-last one, "Status..." its
    entry 11 on the six screens measured) and verified structurally, then
    the kernel popup and the "Installed Software" grid whose `SAP_BASIS` row
    carries THE ABAP release. Two lab systems share a SID and a host; only
    release and kernel tell them apart. Sections that could not be read are
    NAMED (`unread`), never replaced by a plausible value. Pure logic in
    `sapfx_common.system_identity`. The SE16 mixin gained the inverse of the
    ALV setting (`Use Standard List In Data Browser`, a classic list rendered
    as labels and read by `Read Abap List`) and `Get Data Browser Output`.
  - `_statusbar`, `_tabstrip`, `_toolbar` (2026-09-08, the lot that closed the
    capability register of a SECOND release, ABAP Platform 2023): the
    **message identity** (`Get Status Message Identity`: class/type/number,
    `MO/E/402`, empty when nothing is displayed; `Status Message Should Be`,
    two type-E refusals of the same screen told apart without a localized
    word), **tab strips by technical key** (`List Tabs`, `Get Selected Tab`,
    `Select Tab`, `Select Tab By Label`, the selection read back; the tab set
    differs between releases) and the **application toolbar inventory**
    (`List Toolbar Buttons`, `Click Application Toolbar Button`, icon names as
    locale-safe anchors). The same lot made `Open System Status` RESOLVE the
    "Status..." entry (second-to-last of the second-to-last menu, a dialog
    opener required: the hard-coded index 11 clicked "Log Off" on 758) and
    made both control resolvers read the shell SubType: a column tree is no
    longer taken for an ALV grid, a leaf shell is refused naming its reader, a
    splitter is traversed, and neither reader leaks a raw COM error. Pure
    logic in `sapfx_common.status_message`, `tab_strip`, `menu_path`.
  - `sapfx_common.artifacts` (same evening, importable as a Robot library):
    the **generic deterministic artifact**, sorted JSON with a DECLARED hash
    scope, hash recomputed on read (an artifact edited afterwards is refused),
    path-named differences on comparison; first consumer: the capability
    register.
  - The Business Partner role campaign (2026-09-26 to 28, transaction BP on
    A4H) closed seven gaps in the library itself: combo selection read back
    on the element RE-ACQUIRED by its id (a combo with a function code
    rebuilds the screen while selecting, and the old proxy raises);
    `Element Is Changeable` and its two assertions (a screen's MODE read from
    a field, since the title is translated and F6 is a toggle);
    `Element Is Present` (a presence probe that never takes a screenshot);
    a CLOSED session recognised by `Wait Until Busy Done`, which fails at once
    with `SessionDisconnectedError`, and taken by `Run Transaction    /nex` as
    its success; `field:<NAME>` for table control columns; the human-locator
    row fallback (nearest field on the same row when a short label leaves a
    gap, nothing in between, 100 px scaled); and `Open Sap Logon` without a
    screenshot per premature probe. On the RFC side, the BAPI pattern moved to
    its own mixin `_bapi.py` (`accept=` to tolerate a refusal named by message
    id, `Bapi Should Fail With Message Id` to assert one), `Read Rfc Table`
    refuses a RAW field (returned truncated to half), and `Filter Change
    Documents` / `Latest Change Number` state an audit claim offline.
  - The perception mixin also hosts the **drift sentinel**
    (`Check Screen Against Watch` over the pure
    `sapfx_common.screen_watch`): watched screens are remembered (structured
    signature + optional visual fingerprint + per-tile fingerprints) and later
    passes report ONLY what moved: change detection **without a single
    scripted test** (`tests/robot/ecc_drift_sentinel.robot` is the
    nightly-watch harness). Three channels per screen: the structural smart
    diff (renames paired, value changes named), the global visual hash, and
    the **tile grid**. A local drift too diluted for the global hash is
    caught by its own tile and reported with its position, pixel rectangle
    and the elements covering it. `per_resolution=True` gives every capture
    geometry its own VISUAL references while the structural signature stays
    shared, because a screen signature does not depend on the display
    resolution and a perceptual fingerprint does; without it, a visual drift
    between two different geometries is annotated as possibly being scale
    alone.
- **`SapEccLibrary.py`** wires them together and overrides `run_transaction` for
  locale-independent error detection. `ROBOT_LIBRARY_SCOPE = SUITE`: tests in
  one suite share their COM connection, while distinct normal Robot suites
  receive isolated instances. rf-mcp concurrency limits are documented separately.

Why mixins and not a subclass with everything in one file: each concern (connect,
wait, grid, perceive, diagnose, heal) is independently testable, and a file never
grows past the repository's size limit by accumulating unrelated keywords.

**`src/sapfx_common/`** is the shared layer used by *both* channels: `polling`
(all wait/retry loops), `com_safety` (`ensure_com_initialized`), `healing` (the
ECC↔Fiori locator-similarity scoring), `perception_diff` (the line diff behind
both `mode=diff` perceptions, incl. the `pair_renames` smart diff that reuses
the healing scoring), `object_tree` (the `GetObjectTree` JSON
flattening, the structured perception model), `semantic` (label-based
geometric resolution + the verified inverse `describe_element` used by the
recorder and the `mode=semantic` affordances view), `abap_list` (geometric row
reconstruction for classic ABAP lists), `visual_hash` (the pure perceptual
dHash behind the visual assertions, plus crop/mask/tile primitives) and
`visual_baseline` (the shared snapshot-baseline semantics and the Pillow
decode boundary, used by the ECC *and* Fiori visual keywords:
`Ui5 Screen Should Match Baseline` is the same cycle on a Browser capture).
New cross-channel primitives go there, never inline.

## The API channel (`src/SapApiLibrary`)

The third channel, next to the desktop GUI and the web: a robust SAP test
**prepares and cross-checks its data through the API** and drives the screen
only for what it actually tests: GUI setup/teardown is slow and fragile, the
API is fast and deterministic. `SapApiLibrary` is deliberately **stdlib-only**
(no new dependency to pin): OData **v2** (the embedded Gateway of ECC/S4) and
**v4** (CAP, modern S/4) behind one keyword set (`Open Api Session` per alias,
`Get Odata Entities`, `Get Odata Count`, `Post Odata` with the SAP **CSRF**
token protocol), plus optional RFC through `pyrfc` when installed. HTTP
failures are auto-correctable (status, effective URL, body excerpt).

The canonical pattern is the **cross-paradigm flagship suite**
(`tests/robot/flagship_cross_paradigm.robot`): the same business fact asserted
through two independent channels: live-validated on A4H, the SE16 « Number of
Entries » of `SNWD_PD` equals the `$count` of the Gateway
`SEPMRA_SHOP/Products` service of the same system. A divergence means a
filtering service or phantom data, something neither channel can detect alone.

Maintenance loop on top of the healing telemetry: `scripts/
healing_drift_report.py` re-reads the cumulative `SAPFX_HEALING_LOG` journal,
separates **stable** drifts (same locator healed repeatedly to one target:
the `resources/` patch is located and proposed, `--apply` executes it) from
**unstable** ones (human or sap-healer review), and exits non-zero as a CI
alert signal. Healing becomes preventive maintenance, and it never touches
tests.

## The Recorders (`tools/recorder`, `tools/recorder_web`)

`tools/recorder/sapgui_recorder.py` works over the **same** COM connection the
library uses, so any id it surfaces resolves identically at runtime. Modes: dump,
`--highlight`, click-to-capture (`--capture`), hover inspector (`--hover`) and a
flow **recorder** (`--record`) that transcribes manipulations into a replayable
keyword sequence. `--engine auto|native|poll` selects the record engine: **native**
subscribes to the Scripting API's own events (`Session.Record` + `Change`, the
mechanism behind ALT+F12) and transcribes the *exact* command, including button
clicks, grid and tree actions the polling engine cannot see; it falls back to
**polling** (screen-signature round-trip diff) automatically when the server
profile disables recording. With `--semantic` (native engine), each step is
rewritten as a **human keyword** (`Fill Field By Label    Table Name    T000`)
whenever the label computed at event time provably re-resolves to that same
element: the technical id is kept as a trailing comment, so the recording
speaks the `resources/` language (design rule 1) instead of shipping ids to
rework. Known vkeys get a readable comment (`# F8`), and `--screenshots` now
prefers the Scripting API's `HardCopyToMemory` (faithful window image even when
covered) over the GDI fallback. See `tools/recorder/README.md`.

The web counterpart (`tools/recorder_web/`: DevTools snippet + MV3 extension) is
generated from the `SapFioriLibrary` resolution bundle: capture never drifts from
resolution. See [fiori-architecture.md](fiori-architecture.md).

## WebView2 embedded in SAP GUI (implemented)

Recent SAP GUI builds embed more and more **WebView2** (Edge) controls inside
the desktop client, screens the COM Scripting API only sees as an opaque
shell. Those embedded pages are ordinary Chromium targets: the
`EmbeddedBrowserKeywords` mixin enables their remote debugging
(`Enable Embedded Browser Debugging`, which must run **before** the SAP client
starts: WebView2 reads the environment variable at control creation) and then
`Switch To Embedded Browser Page` locates the hosted page by title in the
Browser library's catalog over **CDP** and makes it the active page: every
subsequent Browser keyword (`Click`, `Fill Text`, `Get Text`…) drives the
embedded content without ever leaving the ECC suite. The CDP path (connect,
catalog polling, page switch, round-trip click) is live-validated against a
real Edge DevTools endpoint; the remaining prerequisite on a real SAP GUI is
the workstation option *Browser Control = Edge*. RoboSAPiens documents the
same route (see `NOTICE`).

## Design rules

1. Tests never contain raw SAP ids: those live in a business resource layer
   (`resources/`). That layer is the business vocabulary of **one**
   installation, written for your target and your business domain; the
   universal half is `src/`, the libraries, which carry the capabilities.
2. Never `time.sleep` to wait for SAP; use the `Wait Until ...` keywords.
3. Locale-independent assertions only (message *type*, not message *text*).
4. Keep the robotframework-sapguilibrary surface: its 37 keywords keep their
   names and signatures.

## Trademarks

SAP, SAP ECC, SAP S/4HANA, SAP Fiori, SAP BTP, SAP HANA, SAP NetWeaver, SAP
GUI, SAPUI5, ABAP and the other SAP products and services mentioned are
trademarks or registered trademarks of SAP SE or its affiliates in Germany and
in other countries. SAPFX is an independent open-source project, not affiliated
with, sponsored or endorsed by SAP SE.
