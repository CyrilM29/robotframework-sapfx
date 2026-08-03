> **🇬🇧 English** · [🇫🇷 Français](PRIVACY.fr.md)

# Privacy Policy — SAP UI5 / WebGUI Locator Recorder

_Last updated: 2026-06-26_

This extension is a developer tool that helps you capture stable UI5/WebGUI test
locators and record action flows on the page you are looking at.

## What data the extension handles

- **Page content you point at.** When you start the recorder and hover/click controls,
  the extension reads control metadata (control type, properties, ids) and the values
  you type, to build Robot Framework keyword lines. This happens **entirely in your
  browser**.
- **Password fields are never captured in clear text.** Recorded `Fill Ui5 Input` /
  `Fill Sid Input` steps for a `type="password"` field record `<REDACTED>` as the
  value (the field's locator — id/xpath/sid — is still recorded, so the step stays
  usable once you substitute a real value by hand).

## The recording indicator is advisory only

- The toolbar badge and the in-page recording dot reflect a state signal sent by the
  page-injected recorder script. Because that signal travels through a DOM event the
  hosting page's own scripts can also see and dispatch, a compromised or malicious
  page script could in principle spoof it (show "not recording" while it's actually
  on, or vice versa). This has no impact on what data is captured or where it goes
  (still nowhere but your machine), but don't treat the badge as a tamper-proof
  guarantee — it's a convenience indicator, not a security boundary.

## What it does with that data

- The generated locator/step lines are **copied to your clipboard**, shown in an
  in-page panel, **saved to the page's `sessionStorage`** (so a recording survives a
  page reload), and — on **Export** — **downloaded as a `.robot` file** to your
  computer.
- **Nothing is sent anywhere.** The extension has **no servers, no analytics, no
  telemetry, and no network requests of its own.** No data leaves your machine.

## Permissions

- `activeTab` + `scripting`: inject the recorder into the tab **only when you click the
  toolbar icon or press the shortcut**. There are **no host permissions** — the
  extension cannot access sites you don't explicitly act on.

## Data retention

- The extension stores nothing persistently of its own. `sessionStorage` is cleared by
  the browser when the tab/session ends, or by the panel's **clear** button. Downloaded
  `.robot` files live on your computer, under your control.

## Contact

Questions: open an issue on the project repository.
