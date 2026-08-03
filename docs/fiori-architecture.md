> **🇬🇧 English** · [🇫🇷 Français](fiori-architecture.fr.md)

# Fiori / web side (phase 2)

The web half of the project. It automates SAP Fiori / S/4HANA (SAPUI5) apps and
plugs into the **same** Robot Framework business vocabulary as the ECC side, so
tests read identically across channels (see [architecture.md](architecture.md)).

## The core problem: dynamic UI5 ids

SAPUI5 generates DOM ids like `__xmlview0--__button12` that change between builds,
views, and even renders. CSS/XPath built on them is brittle. The fix is to stop
addressing the **DOM** and address the **UI5 control** instead.

## How it works

```text
  test  ──▶  fiori_keywords.resource  ──▶  Browser library (Playwright)  ──▶  page
                       │                              ▲
                       └──▶ SapFioriLibrary ──────────┘
                              injects the __SAPFX bundle (_ui5_js.py) which
                              resolves a control selector → stable control DOM id
```

- **Browser library** (Playwright) owns the page, the clicking and the typing.
- **`SapFioriLibrary`** turns a *UI5 control selector* into a selector Browser can
  use, via an injected JS bundle (`src/SapFioriLibrary/_ui5_js.py`) offering three
  engines:
  - **role**: scan the control registry, matching `controlType` (short *or* full
    name), `properties` (case-insensitive substring, or `/regex/`), `id`,
    `bindingPath`, `viewId`. → `Resolve Ui5 Control`. Returns
    `css=[id="<controlId>"]` (the *control* id, e.g.
    `sdk---app--searchControl-searchField` — stable, not the churny generated DOM id).
  - **xpath**: build an XML tree mirroring the **control hierarchy** (tag = control
    short type, attributes = its properties) and evaluate XPath over it — so you can
    express ancestry and predicates. → `Resolve Ui5 By Xpath`. Same return shape.
  - **wc**: light-DOM scan of `ui5-*` custom elements, for **UI5 Web Components**
    pages with no classic UI5 runtime (see below). → `Resolve Wc Control`.
  - **dom**: generic light-DOM scan (CSS + text + computed ARIA role +
    accessible name + attributes) for the **non-SAP regions** of a hybrid page
    (see below). → `Resolve Dom Element`.
- Apps render views asynchronously, so resolution **polls** until a control appears
  or `ui5_timeout` elapses — never a fixed sleep (the web twin of the ECC
  `Wait Until Element Present`).

```robotframework
Click Ui5 Control    controlType=Button    properties={'text': 'Create'}
Resolve Ui5 By Xpath    //Table//ColumnListItem//Button[@text='Edit']
Resolve Ui5 By Xpath    //*[@controlType='sap.m.SearchField']
${xpath}=    Get Ui5 Xpath    controlType=SearchField    # -> shortest unique //SearchField
```

### Shortest unique XPath (`Get Ui5 Xpath`)

Ported from playwright-sap `getShortestXPath`: given a resolved control, return the
shortest ``//suffix`` of its positional tree path that still resolves to exactly that
control. Useful for codegen and for turning a found control into a stable, readable
hierarchical locator.

### SAP WebGUI / SAP GUI for HTML — the `sid` engine

Classic ABAP WebGUI (SAP GUI for HTML) pages are **not** UI5. Their elements carry an
``lsdata`` attribute whose JSON holds a stable ``"SID"`` — the same id space as SAP
GUI scripting (``wnd[0]/usr/ctxtVBAK-VBELN``). `Resolve Sid` matches it with a
``contains()`` XPath on ``@lsdata`` and returns an ``xpath=`` selector; `Click Sid` /
`Fill Sid Input` / `Sid Should Be Visible` build on it. The Spy captures SIDs too
(parsing ``lsdata``). This complements the UI5 engines for hybrid landscapes — it is
not exercised by the OpenUI5 Demo Kit smoke (no WebGUI there); the SID-XPath builder
and capture logic are unit-tested instead.

### UI5 Web Components — the `wc` engine

Pages built on **UI5 Web Components** (the SuccessFactors home page,
ui5-webcomponents apps) have **no classic UI5 runtime at all**: no
`window.sap`, an empty element registry — the role and xpath engines are
structurally blind there. The `wc` engine scans the document's **light DOM**
for `ui5-*` custom elements (application content stays in the light DOM via
slots; only component internals live in shadow roots):

- `tag=Button` (short type) matches `ui5-button` **and scoped tags**
  `ui5-button-<suffix>` (UI5 WC scoping); a full tag (`tag=ui5-button`) works too;
- `properties=` matches host attributes/properties with the *same* matcher as
  the role engine (case-insensitive substring, bounded `/regex/` — shared
  `valueMatches` implementation); `text=` matches the trimmed `textContent`;
- `name=` matches the host's **accessible name** — what a screen reader would
  announce: `aria-labelledby`/`aria-label`, then the UI5 Web Components
  convention `accessible-name` (attribute) / `accessibleName` (non-reflected
  JS property), then label/visible text. The user-intent locator for an
  icon-only `ui5-button` or an unlabelled `ui5-input`;
- WC hosts often have no id, so matches come back as **CSS light-DOM paths**
  anchored at the closest ancestor with an id; the open shadow roots are pierced
  by Playwright's CSS for the actual click/fill (`Click Wc Control`,
  `Fill Wc Input` targets the internal `<input>`).

The web recorder captures/records WC hosts on registry-less pages too
(`Click Wc Control`, Alt+click assertions). Proven offline against a local
fixture with a genuine scoped tag (`tests/robot/fiori_wc_smoke.robot`).

### Launchpad iframes — `Set Ui5 Frame` (Work Zone / cFLP)

SAP Build Work Zone and the classic cFLP embed each app in an **iframe**, often
cross-origin — the UI5 runtime the bundle needs lives *inside* the frame, not in
the shell. `Set Ui5 Frame    iframe#application-...` switches the library: the
bundle is injected and evaluated **in the frame's context**, and every returned
selector is prefixed with the frame + Playwright's `>>>` piercing combinator
(which crosses origins). `Set Ui5 Frame` without argument switches back to the
main page. Proven against a genuinely cross-origin fixture
(`tests/robot/fiori_frame_smoke.robot`).

### Hybrid pages — composition probe, frame stack, `dom` engine

A real composite screen (Work Zone shell + a UI5 app in one iframe + a WebGUI
transaction in another + a React/vanilla widget in a portlet) mixes technologies
**per region of the same page**. Three keywords make that first-class:

- **`Get Page Composition`** — the hybrid perception probe: reports, per region,
  which technologies are present (classic UI5 runtime / `ui5-*` WC hosts /
  WebGUI `lsdata` elements / React-Angular-Vue hints), the **recommended
  engines** in fallback order, and every iframe with a reusable Browser
  selector plus its own probed composition (one level deep, best-effort — an
  unreachable frame carries an `error` field, never a failed perception).
  Call it first on an unknown screen to know *which engine to aim where*.
- **`Push Ui5 Frame` / `Pop Ui5 Frame` / `Get Ui5 Frame Stack`** — nested-frame
  scoping on top of `Set Ui5 Frame` (which replaces the whole stack): each
  level stacks, the effective scope is Browser's `level1 >>> level2` chaining.
  A surplus `Pop` fails loudly — never a silently wrong scope.
- **the `dom` engine** (`Resolve/Click/Fill Dom …`, `Get Dom Text`,
  `Get Dom Match Count`, `Dom Element Should Be Visible`) — generic matching
  on CSS, text, ARIA role and attributes (same `valueMatches` rules as role/wc,
  light-DOM CSS paths as wc) so the non-SAP regions enter the *same grammar* —
  polling, fallback chain and healing telemetry included — instead of falling
  back to raw Browser selectors outside the library. `role=` is the
  **computed** ARIA role — the explicit `role` attribute *or* the implicit
  HTML semantics (a bare `<button>`, `a[href]` → `link`,
  `input[type=checkbox]` → `checkbox`, `h1`-`h6` → `heading`…, a pragmatic
  HTML-AAM subset) — and `name=` is the **accessible name** (simplified
  accname in W3C precedence order: `aria-labelledby`, `aria-label`,
  `label[for]`/wrapping label, `alt`, button `value`, visible text, `title`,
  `placeholder`). Together they give **user-intent locators** à la
  Playwright `getByRole(name=…)`: `role=button    name=Fermer la
  notification` survives any DOM/CSS refactoring that keeps the widget
  accessible. On a SAP region, the dedicated engine always wins; `dom` is
  the last resort by design.

Proven offline against `fixtures/hybrid_fixture.html` (four technologies, two
genuinely nested frame levels — `tests/robot/fiori_hybrid_smoke.robot`).

### Selector fallback chain — `Resolve Ui5 With Fallback`

One keyword, five engines: tries **role**, then **xpath**, then **sid**, then
**wc** (`wc={'tag': 'Button', 'text': '…'}` — e.g. an app re-platformed to UI5
Web Components whose registry disappeared), then **dom**
(`dom={'role': 'button', 'text': '…'}` — the last resort, a region
re-platformed outside any SAP framework), each
with its own short timeout, and logs a WARNING whenever it succeeds on anything
but the first engine — a healed locator is never silent (the log tells you which
selector to fix, and the repair is appended to the cumulative
`SAPFX_HEALING_LOG` journal when configured — see
`sapfx_common.healing_telemetry`). Failures list what *each* engine tried; role
failures add a type-level hint (« N control(s) of that type ARE rendered » vs
« none at all ») so a wrong property is distinguishable from a wrong control type.

### Fiori Elements — stable `idSuffix`

Fiori Elements v4 generates stable, semantic control ids ending in patterns like
`fe::table::Travel::LineItem-innerTable`. The `idSuffix` selector key matches on
that suffix (role engine + capture); the recorder emits it automatically when a
control id carries an `fe::` marker — the most robust locator for FE apps.

### Ported from playwright-sap

The control-tree + XPath engine, own+inherited property extraction, the property
matcher, interactable-element drilling, and the Spy's priority property allowlist
are derived from **playwright-sap** (Apache-2.0; see the project NOTICE),
re-implemented as a single injected bundle (no Playwright fork) for Robot Framework.

> **Why not `RecordReplay.findDOMElementByControlSelector`?** An earlier design used
> SAP's `sap.ui.test.RecordReplay`. In validation against OpenUI5 1.149 that API
> threw internally (`reading 'ancestor'`) outside the full OPA5 pipeline — even with
> a hardcoded valid selector. The registry/tree approach is more robust and
> dependency-light.
>
> **Composite inputs.** `sap.m.Input` / `SearchField` render an inner
> `<input>`/`<textarea>` inside the control root `<div>`; you cannot type into the
> div. `Fill Ui5 Input` drills to the inner field automatically.

## Validation

`tests/robot/fiori_smoke.robot` passes end-to-end against the live OpenUI5 Demo Kit
(Robot Framework 7.4.2, Browser 20.0.0): resolve a control by type to its stable id,
fill its inner input, and confirm a missing control fails with a clear message.

Version coverage beyond the current runtime (all live-validated):

- **UI5 1.60** (pre-`Element.registry`) — `fiori_legacy_smoke.robot` proves the
  `registryForEach` DOM fallback against a real 1.60.14 runtime.
- **UI5 2.0 nightly** — `fiori_ui5v2_smoke.robot` proves the `ElementRegistry`
  module branch and zero dependency on APIs removed in 2.x (`sap.ui.getCore()`,
  `Element.registry`, `sap.ui.version`). NB: at UI5con (July 2026) SAP
  announced that no UI5 2.0 release is planned — the official modernization
  path is the legacy-free 1.x line. This smoke therefore remains a
  non-blocking sentinel for as long as the nightly/2 CDN is served (it may
  disappear); the 1.136-legacy-free smoke is the forward-looking target.
- **Cross-origin iframes** — `fiori_frame_smoke.robot` (see `Set Ui5 Frame` above).
- **Fiori Elements v4** — `fiori_sflight_smoke.robot` vs a local cap-sflight.

## Why not Selenium / raw CSS / wdi5

- **Raw CSS/XPath**: breaks on id churn — the exact problem we're avoiding.
- **wdi5**: excellent and UI5-native, but it is WebdriverIO-based and lives outside
  Robot Framework. Our stack is Robot, so Browser + `RecordReplay` keeps everything
  in one runner and one report alongside the ECC suites.

## Testing without SAP

Zero access needed: point `FIORI_BASE_URL` at the **OpenUI5 Demo Kit**
(`https://sdk.openui5.org/`). Its controls are the same SAPUI5 controls as a real
S/4HANA, so the locator strategy, `SapFioriLibrary`, and the web Spy can all be
built and tested against public demo pages. See
[testing-without-sap.md](testing-without-sap.md).

## Capture tooling

The web Recorder captures locators from a live page: **hover** highlights the
control under the cursor (blue box + label chip); **click** captures it into a
**floating panel** with per-row `role` / `xpath` / `sid` / `all` **copy** buttons
(and copies the latest to the clipboard). It picks the best property from the
priority allowlist and emits `Resolve Ui5 Control` + `Resolve Ui5 By Xpath`
(shortest unique) lines — with `idSuffix` for Fiori Elements controls — plus
`Resolve Sid` on classic WebGUI pages. **Record mode** (`rec`) transcribes a whole
flow: clicks → `Click Ui5 Control`, typed fields → `Fill Ui5 Input`, Alt+click →
visibility assertion, **Shift+Alt+click → `Ui5 Text Should Be` value assertion**;
`export` downloads a runnable `.robot` file. Works inside launchpad iframes too
(the panel titles show `[iframe]`; the extension injects into all frames).
Two front-ends, one program:

- `tools/recorder_web/recorder_snippet.js` — paste into the DevTools console.
- `tools/recorder_web/extension/` — MV3 browser extension; click the icon → Start.
  It injects `recorder.js` into the page's MAIN world (to reach `window.sap`) via
  `chrome.scripting` + `activeTab` (no broad host permissions). Generated icons
  (`gen_icons.py`) and a store-ready zip builder (`package.py` + `PUBLISHING.md`).

Both JS files are **generated from the bundle**
(`python -m SapFioriLibrary.regen_recorder`) so capture never drifts from
resolution; a unit test guards the sync. SAP's built-in **UI5 Test Recorder**
(Ctrl+Shift+Alt+T) is a complementary heavier option.

## Status

- [x] `SapFioriLibrary` role + **XPath** engines, interaction convenience keywords.
- [x] Ported playwright-sap locator engine (tree/XPath/matcher/drill/allowlist).
- [x] **Shortest unique XPath** generation (`Get Ui5 Xpath`).
- [x] **WebGUI `sid` engine** (`Resolve/Click/Fill Sid…`) for SAP GUI for HTML.
- [x] `fiori_keywords.resource` mirroring the ECC vocabulary.
- [x] Off-browser unit tests for the selector + bundle + sid + recorder-sync logic.
- [x] **Smoke suite passes end-to-end** vs the live OpenUI5 Demo Kit (RF 7.4.2 /
      Browser 20.0.0): role short/full, XPath tree + `@controlType` predicate, fill
      inner input, match count, shortest-xpath round-trip, both engines fail clearly.
- [x] Web Recorder: hover-highlight, in-app panel, record mode + `.robot` export,
      generated from the bundle (snippet + MV3 extension).
- [x] **Multi-version**: UI5 1.60 → 2.0 nightly proven live (registry fallback
      chain), `Get Ui5 Page Tree mode=diff`, perception for rf-mcp.
- [x] **0.2.0**: `Set Ui5 Frame` (Work Zone/cFLP iframes), `Resolve Ui5 With
      Fallback` (role→xpath→sid, logged healing), Fiori Elements `idSuffix`,
      `Ui5 Text Should Be` (+ recorder assertion capture).
- [x] **0.2.5**: **`wc` engine** for UI5 Web Components pages without a classic
      runtime (light-DOM `ui5-*` scan, scoped tags, shadow-piercing click/fill,
      recorder capture — offline fixture smoke 6/6), fallback chain extended to
      role→xpath→sid→wc, healing telemetry journal (`SAPFX_HEALING_LOG`).
- [x] **Visual channel parity with ECC**: `Get Ui5 Perceptual Hash` +
      `Ui5 Screen Should Match Baseline` — the same snapshot-baseline cycle as
      `Screen Should Match Baseline` (shared `sapfx_common.visual_baseline`),
      over a Browser-library page capture. Covers what the UI5 tree does not
      say (canvas, images, a globally altered theme/rendering).
