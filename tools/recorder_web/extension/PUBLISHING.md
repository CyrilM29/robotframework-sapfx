> **🇬🇧 English** · [🇫🇷 Français](PUBLISHING.fr.md)

# Publishing the UI5 / WebGUI Recorder extension

The extension is store-ready. Actual submission is manual (it needs your developer
account and the stores' review) — these are the exact steps.

## 1. Build the package

Regenerate the generated assets, then zip:

```bash
python -m SapFioriLibrary.regen_recorder            # writes recorder.js from the bundle
python tools/recorder_web/extension/gen_icons.py    # writes icon16/48/128.png
python tools/recorder_web/extension/package.py      # -> dist/ui5-recorder-extension-<version>.zip
```

The zip contains only the runtime files: `manifest.json`, `popup.html`, `popup.js`,
`recorder.js`, `background.js`, `bridge.js`, `icon16/48/128.png`. Dev helpers
(`gen_icons.py`, `package.py`, the READMEs) are excluded. Bump `"version"` in
`manifest.json` before each new upload (currently `0.3.0`).

## 2. Chrome Web Store

1. Register once at the [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole)
   (one-time US$5 fee).
2. **Add new item** → upload the `.zip`.
3. Fill the listing: name, summary, description, category *Developer Tools*, language,
   at least one **1280×800** screenshot — a ready one is provided at
   `store/screenshot-1280x800.png` (regenerate with
   `robot --pythonpath src tools/recorder_web/extension/store/make_screenshot.robot`) —
   and the 128px icon (already in the package).
4. **Privacy**: declare a single purpose ("capture stable test locators and record
   action flows on SAP UI5/WebGUI pages"); justify permissions — `scripting` +
   `activeTab` are used only to inject the recorder into the tab you explicitly
   activate (icon click or `Alt+Shift+R`). **No data is collected or transmitted**
   (everything runs locally; selectors go to your clipboard / a downloaded `.robot`).
   Provide the **privacy-policy URL** — host [`PRIVACY.md`](PRIVACY.md) (e.g. as a
   GitHub Pages / raw page) and paste its URL.
5. Submit for review.

## 3. Microsoft Edge Add-ons (optional)

Same `.zip` at the [Edge Add-ons Partner Center](https://partner.microsoft.com/dashboard/microsoftedge)
(no fee). Same listing fields, privacy policy and permission justification.

## 4. Firefox (optional, experimental)

The JS uses a `browser`/`chrome` shim (`const api = typeof browser !== 'undefined' ?
browser : chrome`) so popup/background/bridge are cross-browser. Firefox MV3 differs
on the manifest `background` key (event `scripts` vs `service_worker`) and may need a
`browser_specific_settings.gecko.id`; produce a Firefox-specific manifest before
submitting to [addons.mozilla.org](https://addons.mozilla.org). Not fully validated yet.

## Permission justification (copy-paste)

> **activeTab** + **scripting**: when the user clicks the toolbar button (or presses the
> `Alt+Shift+R` command), the popup/background injects the recorder (`recorder.js`) into
> the *current* tab's page context to read the SAP UI5 control registry / WebGUI
> `lsdata` and compute stable test locators, plus a small `bridge.js` to drive the
> toolbar badge. No host permissions are requested; nothing runs until the user acts.
> The extension performs **no network requests** and **collects no user data** —
> captured locators stay on the local clipboard / a downloaded `.robot` file. See
> [PRIVACY.md](PRIVACY.md).
