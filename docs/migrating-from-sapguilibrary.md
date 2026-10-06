> **🇬🇧 English** · [🇫🇷 Français](migrating-from-sapguilibrary.fr.md)

# Migrating from robotframework-sapguilibrary

`SapEccLibrary` is drop-in compatible with
[robotframework-sapguilibrary](https://github.com/frankvanderkuur/robotframework-sapguilibrary)
(Apache 2.0; see `NOTICE`). Its code was first included verbatim, then
absorbed and rewritten in SAPFX's own modules on 2026-10-06: upstream has been
frozen since March 2022 (1.2.1). The 37 keywords keep their names and the
order, names and default values of their parameters, so migration is a
rename:

```robotframework
# before
Library    SapGuiLibrary
# after
Library    SapEccLibrary
```

**Every upstream keyword keeps its name and signature**, pinned by a unit
test. Suites written for SapGuiLibrary run as-is; you then adopt the additions
at your own pace. What a suite can notice is listed below: each change makes a
keyword fail loudly where upstream passed on a wrong result, or removes a side
effect.

## Steps

1. Install the library from PyPI (`pip install robotframework-sapfx`) and
   pin `pywin32` exactly in your environment file: it is the #1 source of
   COM breakage.
2. Replace the `Library` import in your suites/resources.
3. `robot --dryrun` to confirm keyword resolution.
4. Run your suites, and read the table below for any new failure: it names a
   result upstream accepted without checking.

## What changes immediately

| Upstream behavior | SapEccLibrary behavior |
|---|---|
| `Input Text`, `Select Checkbox`, `Unselect Checkbox`, `Select Radio Button`, `Set Cell Value` write without reading back | the value or state is **read back**: a value truncated by the field length, a protected field or checkbox, a read-only grid cell fails, naming the value obtained |
| `Input Text` and `Input Password` log the typed value at INFO level | nothing is logged on a password field or for a `Secret` value; both accept Robot Framework 7.4's `Secret` type |
| `Get Value`, `Element Value Should Be` and `Element Value Should Contain` put the focus on the element before reading | a read moves nothing |
| `Get Value` on a tree, grid or editor shell returns the control's ProgID | refused, naming the keyword that reads that control |
| errors mix `Warning`, `ValueError` and `AssertionError` | a mismatch raises `AssertionError` with the expected AND the actual value; a usage error (unsupported element type) raises `ValueError`; a missing Logon Pad still raises `Warning` |
| a missing element reports the id only | the message also names the screen actually displayed (`# screen <program>/<transaction>/<number>`) |
| the error screenshot captures the **whole screen** (Robot's `Screenshot` library) | it captures the **SAP window** (modal included) as a PNG in `screenshot_directory` or the output directory; a failed capture never hides the original error |
| `Send Vkey` sends the number as text | sends the API's integer; a key combination (`F8`, `Ctrl+S`, `Shift+F3`) is still accepted, and an unknown one names the closest |
| `Connect To Session` keeps the last scripting engine found, even one of a closed Logon Pad | keeps only an engine that answers; COM is initialized first, so it works off the main thread (rf-mcp, threaded runners) |
| `Connect To Existing Connection` looks at the first connection only | looks at every open connection, and lists them when none matches |
| `Open Connection` returns as soon as the connection object exists | waits for its session (up to `default_timeout`) |
| `Set Explicit Wait` parses its own time format | accepts any Robot Framework time string (`1.5`, `500 ms`, `2 min`), returns the previous value |
| `Run Transaction` checks localized status-bar text | compares the active transaction (`session.Info.Transaction`) with the requested code, whatever the language; handles namespaced tcodes (`/BEV1/RCA01`) |
| `Select From List By Label` assigns the entry and trusts it | refuses a combo in display mode or an unknown label (entries listed), and reads the selection back on the element re-acquired by its id: a combo with a function code rebuilds the screen while selecting |
| `Doubleclick Element` and `Select Context Menu Item` call the tree API on an ALV grid | address the grid cell, then open its detail or its context menu |

## What you gain (adopt progressively)

- **Waits**: `Wait Until Busy Done`, `Wait Until Element Present`; retire
  every `Sleep`. A closed session (after `/nex`) fails at once instead of
  being polled until the timeout.
- **Probes without side effects**: `Element Is Present` replaces
  `Run Keyword And Return Status    Element Should Be Present`, whose failed
  check took a screenshot at every absence (one image per green run for an
  optional popup); `Element Is Changeable` reads a screen's display/change
  mode from a field instead of its translated title.
- **Preflights** (Suite Setup): `Scripting Should Be Fully Enabled` (server
  RZ11 posture, exact parameter named), `Client Security Should Be Hardened`
  (client patch level / input history, CVE-2025-0055), `Abap List Should Be
  Readable` (accessibility mode).
- **Grids**: ALV by column *title*, `Read Grid`, row addressing by content,
  `Read Abap List` for classic list output.
- **Human locators**: `Fill Field By Label`, `Click Button By Label` (visible
  label + geometry, ambiguity always surfaced).
- **Healing**: `Resolve Element With Healing` (scored suggestions, telemetry,
  never silent), plus `scripts/healing_drift_report.py` turning telemetry
  into resource-layer patches.
- **Perception**: `Get Screen Signature` (text view of the live screen,
  `mode=diff`/`semantic`), screenshots (plain, annotated Set-of-Mark), visual
  baselines (screen/element/tiles), drift sentinel.
- **Recorders and AI agents**: desktop recorder (native scripting events),
  rf-mcp plugins, sap-planner/generator/healer agents.

## Conventions worth adopting with the move

Tests speak business language: raw SAP ids live in `resources/`
(convention 1); assertions stay locale-independent (convention 3). The
[hardening guide](hardening-test-environment.md) is the recommended companion
for the test workstation and system posture.

## Trademarks

SAP, SAP ECC, SAP S/4HANA, SAP Fiori, SAP BTP, SAP HANA, SAP NetWeaver, SAP
GUI, SAPUI5, ABAP and the other SAP products and services mentioned are
trademarks or registered trademarks of SAP SE or its affiliates in Germany and
in other countries. SAPFX is an independent open-source project, not affiliated
with, sponsored or endorsed by SAP SE.
