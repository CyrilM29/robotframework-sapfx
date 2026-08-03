> **🇬🇧 English** · [🇫🇷 Français](README.fr.md)

# Web Recorder — Fiori / UI5 (+ WebGUI) locator capture & flow recording (phase 2)

Captures **stable selectors** from a live Fiori / SAPUI5 / OpenUI5 page — and the
classic SAP **WebGUI** — so you don't fight dynamic DOM ids, and **records whole
flows** into a replayable keyword sequence. It emits exactly what `SapFioriLibrary`
resolves at runtime.

> **Generated file.** `recorder_snippet.js` is generated from the library bundle
> (`src/SapFioriLibrary/_ui5_js.py`) so capture never drifts from resolution. Don't
> edit it by hand — run `python -m SapFioriLibrary.regen_recorder`. A unit test
> enforces the sync.

## Two ways to run it

**A. Browser extension (one click)** — see [`extension/`](extension/README.md). Load
the unpacked folder, click the icon, **Start**. Best for repeated use.

**B. DevTools console (zero install):**

1. Open a Fiori app, the [OpenUI5 Demo Kit](https://sdk.openui5.org/), or a SAP
   WebGUI page.
2. DevTools → Console, paste the contents of `recorder_snippet.js`, Enter.

Either way: **hover** highlights the control under the cursor (blue box + label
chip); **click** captures it into a **floating panel** (bottom-right) listing every
capture with per-row **copy** buttons — `role`, `xpath`, `sid`, `wc`, `dom`, `all` —
and copies the latest to the clipboard. Non-SAP zones of a hybrid page (a React/
Angular/vanilla widget) are captured too, through the **generic dom engine**
(computed ARIA role + accessible name, CSS path fallback). The copied lines look
like:

```robotframework
Resolve Ui5 Control    controlType=sap.m.Button    properties={'text': 'Get Started'}
Resolve Ui5 By Xpath    //Page//Button[2]
Resolve Sid    wnd[0]/usr/ctxtVBAK-VBELN        # only on classic WebGUI pages
Resolve Dom Element    role=button    name=Submit    # non-SAP zone of a hybrid page
```

If the page contains **cross-origin iframes** this panel cannot reach, a warning
line appears in the panel — use the extension (allFrames injection: a separate
panel appears inside each accessible frame).

### Record mode

Click **`rec`** in the panel to start recording. Now just **use the app**: every
click becomes a `Click Ui5 Control` (or `Click Sid` / `Click Wc Control` /
`Click Dom Element`) step, every typed-and-blurred field a `Fill … Input` step,
pressing **Enter** in a field is captured as `Keyboard Key    press    Enter`
(ordered *after* the field's fill), and a route change adds **`Wait For UI5
Ready`** when the UI5 runtime is present (the keyword definition is embedded in
the export, so the file stays self-contained) or `Wait For Load State` otherwise.

**Assertions**: **right-click** an element while recording to open the
**assertion menu** (visible / text — per engine); **Alt+click** (visible) and
**Shift+Alt+click** (`Ui5 Text Should Be`) still work as shortcuts.

Steps are **deduplicated and compacted** (re-typing the same field replaces the
previous fill; consecutive waits collapse), **editable** (↑ ↓ ✕ per row, and
**double-click to edit a step in place**), **nameable** (the `Test:` field), and
**persisted** — they **survive a page reload** (sessionStorage), so multi-page
Fiori flows aren't lost. While recording, **clicks are never blocked** — the
app keeps reacting so you can drive a real flow (only the meta gestures,
Alt+click assertions, are swallowed).

**`play`** **replays the recording in the page**: each step is resolved by the
same engines the library uses, highlighted and executed (~3 steps/s); UI5 steps
retry their recorded **xpath fallback** when the primary selector no longer
resolves; the first failure stops the replay and marks the row. Instant
validation before export — no robot run needed.

**`+test`** starts a **new scenario** (a marker step): every export then
produces several `*** Test Cases ***`, with the `New Browser`/`New Page`
bootstrap only in the first one.

**`export`** opens a menu: a complete runnable `recorded.robot` (Settings +
`New Browser`/`New Page` + steps), a **resource-first pair**
(`recorded_keywords.resource` with business keywords + a `recorded.robot` with
**no locator in the test** — project convention #1; UI5 steps become
**self-healing** keywords via `Resolve Ui5 With Fallback` and their recorded
xpath), a **`specs/`-format Markdown plan** (`recorded.spec.md`, the input of
the plan → generate → heal agent cycle), a **self-contained HTML documentation
report** (`recorded_report.html`: one business phrase per step with the exact
RF line alongside, one chapter per scenario — documentation for humans, never
a test; concept observed in RoboSAPiens' recorder, see `NOTICE`), or **import
a previously exported `.robot`** back into the panel (bootstrap lines skipped,
multi-tests restored as markers — the editing cycle closes). **`pause`** stops appending;
**`clear`** empties it. Example output:

```robotframework
*** Settings ***
Library    Browser
Library    SapFioriLibrary

*** Test Cases ***
Scenario enregistre
    New Browser    chromium    headless=False
    New Page    <current URL>
    Click Ui5 Control    controlType=sap.m.Button    properties={'text': 'Open Dialog'}
    Fill Ui5 Input    abc    controlType=sap.m.Input    properties={'value': 'hello world'}
```

> **Where the download lands.** A web page can't choose the save folder (browser
> security) — `export` downloads `recorded.robot` to **your browser's Downloads
> folder**, with only the *filename* set. The project's convention dir for these
> artifacts is **`tools/recorder_web/captures/`** (gitignored, the web counterpart of
> the desktop `tools/recorder/captures/`) — move/save the file there. The smoke test
> writes its captured download straight to that folder via Playwright's `saveAs`.

Panel `stop` or `Esc` (or `window.__ui5SpyStop()`) ends the session and removes the
overlay/panel.

> Both `recorder_snippet.js` and `extension/recorder.js` are **generated** from
> `src/SapFioriLibrary/_ui5_js.py` — run `python -m SapFioriLibrary.regen_recorder`
> after changing the bundle (a unit test enforces the sync).

### Launchpad iframes (Work Zone / cFLP)

Fiori launchpads often embed the app in a (cross-origin) **iframe** — the UI5
runtime lives inside the frame. The **extension** injects the recorder into **all
frames**, so capture and record work directly in the embedded app; the panel
title shows **`[iframe]`** so you know which context you're capturing in. Replay
those steps with `Set Ui5 Frame    <frame selector>` before the UI5 keywords (see
`SapFioriLibrary`). The console-snippet variant must be pasted *in the frame's
context* (DevTools context picker).

## What it emits

- **role** — control type + the best property from a priority-ordered allowlist
  (`text`, `title`, `value`, …), matched against the control registry. On **Fiori
  Elements** apps, controls whose id carries a stable `fe::` suffix are captured
  with `idSuffix=` — the most robust FE locator.
- **xpath** — the **shortest unique** path over the UI5 control tree.
- **sid** — on WebGUI pages, the stable `SID` parsed from the element's `lsdata`.
- **wc** — on UI5 Web Components pages without a classic runtime, the `ui5-*`
  host (`tag=` + `text=`).
- **dom** — on non-SAP zones, the computed ARIA role + accessible `name=`
  (`role=button    name=Submit`), CSS light-DOM path as fallback — interactive
  targets only (a click on a bare `div` records nothing).
- **record** — ordered `Click …` / `Fill …` steps across all five engines,
  using the same selectors above.

All survive the id churn that breaks raw CSS/XPath. SAP's built-in **UI5 Test
Recorder** (**Ctrl+Shift+Alt+T**) is a complementary heavier alternative.

> We intentionally do *not* use `RecordReplay.findControlSelectorByDOMElement`: on
> current UI5 that API is unreliable outside the full OPA5 pipeline (see
> `../../docs/fiori-architecture.md`).

## Roadmap

- [x] **Hover highlight** — outline + label chip for the control under the cursor.
- [x] **Browser-extension packaging** — one-click Start/Stop (see `extension/`).
- [x] **In-app panel** — floating list of captured selectors with copy buttons.
- [x] **Custom toolbar icon** + store-ready package (see `extension/PUBLISHING.md`).
- [x] **Record mode** — `rec`/`pause`/`export` transcribe a flow into a replayable
      `*** Test Cases ***` body. Live-validated on system Chrome.
- [x] **2026-07 upgrade** — dom-engine capture (hybrid pages), right-click
      assertion menu, Enter capture, `Wait For UI5 Ready` on navigation,
      fill/wait compaction, cross-origin frame warning, and the 3-format export
      menu (.robot / resource-first / specs plan).
- [x] **Selenium-IDE-spirit pass (2026-07-19)** — in-page `play` replay (same
      engines, xpath fallback retried, stop on first failure), `+test`
      multi-scenario markers, `.robot` re-import, double-click step editing,
      UI5 steps born self-healing (`# xpath:` hint → `Resolve Ui5 With
      Fallback` in the resource-first export), and recording no longer blocks
      the app's own clicks.
- [ ] **Publish** to the Chrome Web Store / Edge Add-ons (manual submission).

## Relationship to the desktop Recorder

[`../recorder/`](../recorder/) does the same job for the SAP GUI thick client (over
COM), including its own `--record` flow recorder. Together they give one capture +
record workflow per channel, both feeding the same unified keyword vocabulary
(`resources/*.resource`). See `../../docs/architecture.md`.
