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
                ┌─────────────────────────────────────────────┐
                │   Tests  (tests/robot/*.robot)               │
                │   speak business language only               │
                └───────────────────┬─────────────────────────┘
                ┌───────────────────┴─────────────────────────┐
                │  Business keywords (resources/*.resource)    │
                │  ecc_keywords.resource  +  fiori_keywords*   │  ← unified vocabulary
                └─────────┬───────────────────────┬───────────┘
            ┌─────────────▼──────────┐   ┌─────────▼─────────────────┐
            │  SapEccLibrary (this)  │   │  Browser lib + UI5 helpers │
            │  COM / win32com        │   │  Playwright (phase 2)      │
            └─────────┬──────────────┘   └─────────┬─────────────────┘
       SAP GUI Scripting API                SAPUI5 runtime (sap.ui.*)

  * fiori_keywords.resource is phase 2; the ECC side is implemented now.
```

A test reads the same regardless of channel:

```robotframework
Go To Transaction    VA01          # ECC
Open App             Sales Order    # Fiori (phase 2): same intent, different lib
```

## ECC library internals (`src/SapEccLibrary`)

Composition by mixins over the vendored upstream class:

```
SapEccLibrary(ConnectionKeywords, WaitKeywords, GridKeywords,
              PerceptionKeywords, DiagnosticsKeywords, HealingKeywords,
              SemanticKeywords, EmbeddedBrowserKeywords, SapGuiBase)
```

- **`_vendor/sapgui_base.py`**: upstream `SapGuiLibrary`, renamed `SapGuiBase`,
  Apache 2.0 (see `NOTICE`). Treated as read-only; never edited except on re-sync.
- **Mixins** (`keywords/_*.py`) are listed *before* the base in the MRO, so a mixin
  method overrides a same-named base method, and mixins can call inherited keywords
  via `self`:
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
    gets **localized**, not just detected). The pixel channel covers exactly
    what the Scripting API cannot see: opaque GuiShell list rendering,
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
    and the elements covering it.
- **`SapEccLibrary.py`** wires them together and overrides `run_transaction` for
  locale-independent error detection. `ROBOT_LIBRARY_SCOPE = SUITE`: tests in
  one suite share their COM connection, while distinct normal Robot suites
  receive isolated instances. rf-mcp concurrency limits are documented separately.

Why mixins and not a subclass with everything in one file: each concern (connect,
wait, grid, perceive, diagnose, heal) is independently testable and independently
re-syncable, and the diff against upstream stays obvious.

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

1. Tests never contain raw SAP ids: those live in `resources/`.
2. Never `time.sleep` to wait for SAP; use the `Wait Until ...` keywords.
3. Locale-independent assertions only (message *type*, not message *text*).
4. Keep the upstream vendor diff to one line.
