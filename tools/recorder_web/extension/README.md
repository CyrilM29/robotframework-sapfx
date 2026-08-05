> **🇬🇧 English** · [🇫🇷 Français](README.fr.md)

# UI5 / WebGUI Locator Recorder: browser extension

One-click version of the Recorder: no console paste. **Hover** highlights the control
under the cursor; **click** captures it into an **in-app panel** (a floating list
with per-row `role` / `xpath` / `sid` / `all` **copy** buttons) and copies the latest
to the clipboard. **`rec`** records a whole flow (clicks → `Click Ui5 Control`,
typed fields → `Fill Ui5 Input`, Alt+click → visibility assertion, Shift+Alt+click
→ `Ui5 Text Should Be` value assertion); **`export`** downloads a complete
`recorded.robot` file (and copies it). `clear` empties the list; `stop` (or `Esc`)
ends the session.

The panel is **draggable** (grab its header) and **collapsible** (▾), and shows a red
**recording indicator**. You can drive it from the **toolbar popup** too (Start, Rec/Pause,
Export, Stop, with live status), and the keyboard shortcut **`Alt+Shift+R`** toggles
recording without opening the popup; the icon shows a **`REC` badge** while recording.

## Load it (unpacked, Chrome / Edge)

1. Generate the content script and icons (once, and after any bundle change):

   ```bash
   python -m SapFioriLibrary.regen_recorder            # writes extension/recorder.js from the bundle
   python tools/recorder_web/extension/gen_icons.py    # writes icon16/48/128.png
   ```

2. Open `chrome://extensions` (or `edge://extensions`), enable **Developer mode**.
3. **Load unpacked** → select this `extension/` folder.
4. Open a Fiori / UI5 page (or a SAP WebGUI page), click the extension icon, **Start**.
   Hover to highlight, click to capture, `rec` to record. **Stop** (or `Esc`) ends it.

## How it works

- `popup.js` / `background.js` inject `recorder.js` into the page's **MAIN world** via
  `chrome.scripting.executeScript`, required so the script can read the page's
  `window.sap` (UI5 runtime). Injection targets **all frames** (`allFrames: true`),
  so apps embedded in a launchpad **iframe** (Work Zone / cFLP, even cross-origin)
  are covered, and the panel title shows `[iframe]` in that case. They use the
  `activeTab` permission, granted when you click the icon or press the shortcut,
  so the extension needs **no broad host permissions**.
- The recorder (MAIN world) can't call `chrome.*`, so a tiny **`bridge.js`** (ISOLATED
  world) relays the recording state to `background.js`, which sets the **toolbar badge**.
- `recorder.js` is **generated from `src/SapFioriLibrary/_ui5_js.py`** (identical to
  the console snippet `../recorder_snippet.js`) so capture never drifts from the
  library's resolver. Don't edit it by hand: re-run `regen_recorder`.

## Files

| File | Role |
|------|------|
| `manifest.json` | MV3 manifest (popup + icons; `scripting` + `activeTab`; `background`; `commands`). |
| `popup.html` / `popup.js` | Start / Rec / Export / Stop UI with live status; drives the recorder. |
| `background.js` | Service worker: toolbar badge + `Alt+Shift+R` shortcut (inject + toggle record). |
| `bridge.js` | ISOLATED-world relay: forwards the recorder's state to the badge. |
| `recorder.js` | **Generated** Recorder program (bundle + hover/panel/click/record listener). |
| `icon16/48/128.png` | Toolbar icons (**generated** by `gen_icons.py` from the project logo; 16 px crops to the robot face). |
| `gen_icons.py` | Derives all icon sizes from `assets/logo.png` (repo root; needs Pillow). Dev-only. |
| `package.py` | Builds `dist/<name>-<version>.zip` for store upload. Dev-only. |
| `PRIVACY.md` / `PUBLISHING.md` | Privacy policy + step-by-step store-submission guide. |

To publish, see [PUBLISHING.md](PUBLISHING.md) (`python package.py` → upload the zip).

> Locator techniques ported from [playwright-sap](https://github.com/ArpitSureka/playwright-sap)
> (Apache-2.0); see the project `NOTICE`.
