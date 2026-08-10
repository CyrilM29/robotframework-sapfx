> **🇬🇧 English** · [🇫🇷 Français](README.fr.md)

# SAP GUI Recorder (phase 2)

Locator + flow tooling for the SAP desktop client. `sapgui_recorder.py` works over
the same COM connection the library uses, so every id it surfaces is exactly what
you paste into a `SapEccLibrary` keyword. Five modes: **dump**, **highlight**,
interactive **click-to-capture**, **hover** inspector, and an on-demand **recorder**
that transcribes your manipulations into a replayable keyword sequence.

## Usage

Prerequisites: SAP Logon Pad open with a session running, scripting enabled
server- and client-side (see `../../docs/testing-without-sap.md`), and `pywin32`.

```bash
# Dump: the whole live object tree
python sapgui_recorder.py                  # pretty indented tree to stdout
python sapgui_recorder.py --filter txt     # only ids/types containing "txt"
python sapgui_recorder.py --json           # JSON -> captures/dump_<timestamp>.json
python sapgui_recorder.py --json tree.json # JSON -> captures/tree.json

# Highlight: frame a control in red on screen (Visualize)
python sapgui_recorder.py --highlight "wnd[0]/usr/ctxtDATABROWSE-TABLENAME"

# Click-to-capture: record every FOCUSED control + a ready-to-paste keyword line
python sapgui_recorder.py --capture                 # Ctrl+C to stop
python sapgui_recorder.py --capture --out my.txt    # custom destination
python sapgui_recorder.py --capture --no-highlight  # don't frame as you go
python sapgui_recorder.py --capture --filter btn    # only matching ids/types

# Hover: frame the control UNDER THE CURSOR live (inspector)
python sapgui_recorder.py --hover                    # Ctrl+C to stop
python sapgui_recorder.py --hover --out my.txt       # also record what you hover

# Record: transcribe a whole flow into a replayable *** Test Cases *** body
python sapgui_recorder.py --record                   # Ctrl+C to stop
python sapgui_recorder.py --record --out scenario.robot
python sapgui_recorder.py --record --engine native   # force the native event engine
python sapgui_recorder.py --record --engine poll     # force the polling engine
python sapgui_recorder.py --record --screenshots     # + a screenshot per boundary (polling)
python sapgui_recorder.py --record --body-only       # historic fragment (no Settings: not runnable as-is)
python sapgui_recorder.py --record --export-resources  # + resource-first pair (no raw id in tests)
python sapgui_recorder.py --record --export-spec       # + specs/-style Markdown plan (draft)
python sapgui_recorder.py --record --export-report     # + self-contained HTML documentation report
python sapgui_recorder.py --record --export-istqb      # + ISTQB test plan + test cases (.istqb.md)

# Replay: play a recording back against the OPEN SAP GUI session (stop on 1st failure)
python sapgui_recorder.py --replay captures/record_x.robot

# Transpile: convert a SAP GUI built-in ALT+F12 VBS recording into keywords (no SAP needed)
python sapgui_recorder.py --transpile-vbs my_recording.vbs --suite --export-resources
```

`--capture`/`--hover` capture **one locator at a time**; `--record` follows the
**whole flow** and emits an ordered, runnable keyword sequence.

### Live assertions while recording

A recording without assertions is just a navigation script. During `--record`
(both engines), two **global hotkeys** insert checks without leaving SAP GUI:

- **Ctrl+Alt+A**: value assertion on the focused element
  (`Element Value Should Be`; presence check if it has no readable text,
  never the value of a password field);
- **Ctrl+Alt+V**: visual assertion of the current screen
  (`Screen Should Match Baseline    <out>_etape_NN`; the baseline is created
  at first replay, see the perception keywords).

### Post-recording exports

The raw transcript (technical ids) is a **draft**. Five exports derive from it;
the raw recording is never modified:

- **Complete suite by default** (since 2026-08-05): the output file itself is
  a complete, replayable `.robot` (Settings + `Library SapEccLibrary` +
  `Suite Setup    Attach To Open Session`, the keyword that binds the library
  to the already-open SAP GUI session by index; `Connect To Session` alone
  only acquires the scripting engine, never the session; caught by
  live-replaying an export). A `.robot` file that lacks its Library import
  fails with "keyword not found" when launched as-is (caught live);
  `--body-only` restores the historic body-only fragment for pasting into an
  existing suite (`--suite` is kept as a redundant compatibility flag).
- `--export-resources`: writes `<out>_keywords.resource` (each id becomes a
  `${LOC_…}` variable wrapped in a business keyword: `Saisir
  DATABROWSE_TABLENAME`, `Cliquer Bouton 31`…) plus
  `<out>_resource_first.robot`, a suite calling **only those keywords**: no raw
  id left in the test (project convention #1, and the layer `sap-healer` knows
  how to repair).
- `--export-spec`: writes `<out>.spec.md`, a `specs/`-format Markdown plan
  (business-language steps, observed ids relegated to factual notes): the
  recording becomes the *input* of the plan → generate → heal agent cycle
  instead of a frozen test.
- `--export-report`: writes `<out>_report.html`, a **self-contained HTML
  documentation report** (inline CSS, no JS, no external resource): one French
  business phrase per step (ECC, Fiori/UI5 **and** API keywords are phrased,
  so mixed cross-channel transcripts render too) with the exact RF line
  alongside, and the `--screenshots` boundary captures inlined as per-step
  data-URI images (a missing capture is named, never silent; `password=`
  named arguments are always masked). Documentation for humans, never a
  test. Concept observed in RoboSAPiens' recorder (`saveHtmlReport`, see
  `NOTICE`), re-implemented per step.
- `--export-istqb`: writes `<out>.istqb.md`, an **ISTQB test plan + test
  cases** document (ISTQB / ISO 29119-3 sections: objective and scope,
  preconditions, entry/exit criteria, traceability, risks; one test case with
  an Action / Données / Résultat attendu table). Each test case carries a
  normalized `replay` YAML block (framework-neutral actions such as
  `run_transaction`/`fill`/`click`/`assert_value`, human target wording, the
  recorded locator relegated to a `hint`): human-readable AND replayable by an
  AI with any test framework. The recorder invents nothing: judgment fields
  stay marked « à compléter » (the `sap-istqb` agent writes them from
  `specs/` plans); hot assertions become real expected results.

Semantic lines from `--semantic` (a `Fill Field By Label` / `Click Button By
Label` step carrying its technical id as an end-of-line comment) get a
**self-healing** resource-first export: the generated keyword resolves through
`Resolve Element With Healing` with the recorded id *and* the label anchor:
nominal id path first, scored repair + label re-resolution otherwise, never
silent.

### Replay (`--replay FILE`)

The "play" of the Selenium-IDE spirit, thick-client side: replays a recording
(bare body or full suite) against the **already-open** SAP GUI session
(`Attach To Open Session`), step by step, stopping on the first failure with the
offending step named; comments skipped, keywords outside the library reported
but non-blocking. The GUI exposes it as the **Rejouer** button of the steps
panel (auto-saves pending edits first).

### VBS transpile (`--transpile-vbs FILE`)

Converts a recording made with SAP GUI's **built-in ALT+F12** "Script Recording
and Playback" (VBScript) into SapEccLibrary keywords, through the same state
machine as the native engine (OK-code + Enter merged into `Run Transaction`,
context menus paired, grid cells tracked; unmapped calls kept as `# non mappé`
comments). Requires **no SAP session**; `--suite` / `--export-resources` /
`--export-spec` then apply normally. Validated end-to-end: ALT+F12-shaped VBS →
transpile → `--replay` against a live A4H.

### Visual launcher (no command line)

A lightweight Tkinter window (stdlib, no extra dependency) to pick the mode and
options and launch with one click. **Double-click `recorder.cmd`** at the repo root
(Windows), or run:

```bash
python tools/recorder/recorder_gui.py
```

Choose a mode (dump / JSON / capture / hover / record / highlight), fill the optional
filter / output / id fields, **Lancer**. Interactive modes run in a separate console
(live output + Ctrl+C); **Arrêter** stops them, **Dossier captures** opens the output
folder. Record options (full suite, resource-first export, spec export, HTML
report export) are checkboxes. In record mode the **steps panel** follows the output file live
(each emitted step appears as you work) and lets you reorder (↑/↓), delete (✕),
**edit in place** (double-click a step), save (**Enregistrer**) and **replay**
(**Rejouer**: runs `--replay` against the open session in a separate console),
like the web recorder's panel.

Example dump output:

```
[GuiMainWindow] wnd[0] = 'SAP Easy Access'
  [GuiTextField] wnd[0]/usr/txtRSYST-BNAME = ''
  [GuiButton] wnd[0]/tbar[0]/btn[0]
```

In **record** mode, just drive SAP GUI normally. Between server round-trips the
recorder diffs the editable-field state and writes the actions that produced it:

```robot
*** Test Cases ***
Recorded scenario
    Run Transaction    /nSE16
    Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000
    Send Vkey    0
```

### How record mode works: two engines

`--engine auto|native|poll` (default `auto`: native first, automatic fallback).

The **native engine** subscribes to the Scripting API's own events: `Session.Record
= True` makes the session emit a `Change` event per user action with the **exact
command** (the mechanism behind SAP GUI's built-in ALT+F12 recorder). Each command
maps 1:1 to a keyword: `Input Text`, `Click Element` with the *exact button
pressed* (`wnd[0]/tbar[1]/btn[8]` for F8), grid/tree actions, `Select Checkbox`…
An OK-code + Enter pair is merged into a single `Run Transaction`; a grid context
menu (`pressToolbarContextButton` + `selectContextMenuItem`) becomes one `Select
Context Menu Item`; tree nodes map to `Select Node` (expand included); a single
selected grid row maps to `Select Table Row`; grid cell clicks keep their
row/column (tracked from the `currentCell*` events) in an enriched comment.
Commands with no keyword equivalent are kept as `# non mappé :` comments so
nothing is silently lost. Passwords are redacted. Vkey comments (`# F8`)
come from a static table for the common keys, extended live through
`GuiSession.GetVKeyDescription` for the rest (`# Shift+F5`…). Event binding does **not** use pywin32's
`DispatchWithEvents` (its makepy generation crashes on the sapfewse typelib,
pywin32 issue #2433) but a manual connection-point subscription
(`advise_session_events()`); live-validated on A4H.

**Polling engine** (fallback, and the `--screenshots` engine). SAP is a stateful
screen system: you fill fields (no round-trip), then **submit** (server
round-trip). The round-trip boundary is a change in a **screen signature** =
`(program/transaction/screen number, the full set of control ids)`, so even an
action that redisplays the *same* dynpro (e.g. SE16's *Execute*, which only adds
the result grid) is detected. At each boundary it emits the editable-field diff
(`Input Text`/`Select Checkbox`/…) then the submit action (`Run Transaction` if
you typed an OK-code, otherwise `Send Vkey 0`).

`auto` falls back to polling when the server profile disables recording
(`sapgui/user_scripting_disable_recording` → no `Change` events) or when the
event subscription fails; `--screenshots` (a screenshot per round-trip boundary)
implies the polling engine.

Honest limits (polling engine): a strictly identical redisplay of the same screen
isn't detected; the exact button pressed isn't deducible (plain submits become
`Send Vkey 0`; adjust if it was a specific button). Both engines: passwords are
unreadable by scripting (emitted as `Input Password    <id>    <password>`).

## Where things are saved

One unified policy for every artifact (`--json` dumps, `--capture` files **and**
`--record` scripts):

| You pass | It lands in |
|----------|-------------|
| nothing (`--json` / `--capture` / `--record` alone) | `tools/recorder/captures/` as a timestamped file (`dump_…json` / `capture_…txt` / `record_…robot`) |
| a **relative** path (`--json t.json`, `--out my.robot`) | under `tools/recorder/captures/` |
| an **absolute** path (`C:/tmp/t.json`) | exactly there |

A plain `python sapgui_recorder.py` with no `--json` still just prints to the
terminal; nothing is written. The `captures/` folder is gitignored: these are your
working artifacts, not committed.

## Why build on this rather than a third-party tool

The upstream library points users at the external "SAP Scripting Tracker" to find
ids. This script removes that dependency: it reuses our own connection logic, so
captured ids resolve 1:1 at runtime, and it has no install beyond pywin32.

## Roadmap

- [x] **Highlight**: frame a control in red on screen (native `Visualize`), via
      `--highlight ID`.
- [x] **Click-to-capture**: `--capture` records each focused control (polling
      `ActiveWindow.GuiFocus`) with a suggested keyword line. `--filter` applies here too.
- [x] **Hover highlight**: `--hover` boxes the control under the *cursor* (not just
      the focused one), mapping `win32api.GetCursorPos` to the smallest control whose
      `ScreenLeft/Top/Width/Height` rect contains it.
- [x] **Record mode**: `--record` follows your manipulations and emits an ordered,
      replayable `*** Test Cases ***` body (round-trip diff via the screen signature).
      Live-validated on ABAP Platform A4H.
- [x] **Native event engine**: `--engine native` transcribes the Scripting API's
      own `Change` events (exact buttons, grids, trees; merged `Run Transaction`),
      with hit-test capture (`Hit`/`FocusChanged`) and automatic polling fallback.
      Live-validated end-to-end on A4H (manual *and* scripted actions).
- [x] **Live assertions + exports (2026-07)**: Ctrl+Alt+A/V assertion hotkeys
      during record; `--suite` full replayable `.robot`; `--export-resources`
      resource-first pair (no raw id in tests); `--export-spec` specs/-format
      plan. Capture/hover also suggest `Click Element At Offset` (relative
      cursor position) when the target is an opaque `GuiShell`/`GuiChart`:
      the pointer-fallback the Scripting API cannot script.
- [ ] **Clipboard**: copy the suggested keyword line straight to the clipboard.
- [ ] **VBS transpile**: consume the SAP GUI built-in "Script Recording and
      Playback" `.vbs` output and emit `SapEccLibrary` keywords.

## Web counterpart (Fiori)

The web recorder lives in [`../recorder_web/`](../recorder_web/): a DevTools snippet
and a browser extension that hover-highlight, capture UI5/WebGUI locators, and
(record mode) transcribe clicks/inputs into `Click Ui5 Control` / `Fill Ui5 Input`
sequences, generated from the same `SapFioriLibrary` resolution bundle.
