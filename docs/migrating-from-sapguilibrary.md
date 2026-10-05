> **🇬🇧 English** · [🇫🇷 Français](migrating-from-sapguilibrary.fr.md)

# Migrating from robotframework-sapguilibrary

`SapEccLibrary` is a hardened fork of
[robotframework-sapguilibrary](https://github.com/frankvanderkuur/robotframework-sapguilibrary)
(Apache 2.0; see `NOTICE`). The upstream code is vendored **verbatim**
(`src/SapEccLibrary/_vendor/sapgui_base.py`, single change: class renamed) and
`SapEccLibrary` inherits from it, which makes migration a drop-in rename:

```robotframework
# before
Library    SapGuiLibrary
# after
Library    SapEccLibrary
```

**Every upstream keyword keeps its name and signature.** Suites written for
SapGuiLibrary run as-is; you then adopt the additions at your own pace. A few
keywords now fail loudly where upstream returned a misleading value: `Get Value`
on a tree, grid or editor shell (upstream returned the control's ProgID), and
`Select From List By Label` on a combo box in display mode or with an unknown
label.

## Steps

1. Install the library from PyPI (`pip install robotframework-sapfx`) and
   pin `pywin32` exactly in your environment file: it is the #1 source of
   COM breakage.
2. Replace the `Library` import in your suites/resources.
3. `robot --dryrun` to confirm keyword resolution.
4. Run your suites: behavior is upstream's, plus the overrides below.

## What changes immediately (safe overrides)

| Upstream behavior | SapEccLibrary behavior |
|---|---|
| `Run Transaction` checks localized status-bar text | locale-independent: checks the message **type** (`E`/`S`/…), handles namespaced tcodes (`/BEV1/RCA01`) |
| `Connect To Session` assumes the COM apartment is initialized | defensive `CoInitialize`: works off the main thread (rf-mcp, threaded runners) |
| `Select From List By Label` assigns the entry and trusts it | refuses a combo in display mode or an unknown label (entries listed), and reads the selection back on the element re-acquired by its id: a combo with a function code rebuilds the screen while selecting |

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
