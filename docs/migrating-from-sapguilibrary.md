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

**Every upstream keyword keeps working unchanged.** Suites written for
SapGuiLibrary run as-is; you then adopt the additions at your own pace.

## Steps

1. Install the library (wheel from the Windows deployment pack, or the repo
   with `pip install -r requirements.txt`; `pywin32` is pinned exactly:
   it is the #1 source of COM breakage).
2. Replace the `Library` import in your suites/resources.
3. `robot --dryrun` to confirm keyword resolution.
4. Run your suites: behavior is upstream's, plus the overrides below.

## What changes immediately (safe overrides)

| Upstream behavior | SapEccLibrary behavior |
|---|---|
| `Run Transaction` checks localized status-bar text | locale-independent: checks the message **type** (`E`/`S`/…), handles namespaced tcodes (`/BEV1/RCA01`) |
| `Connect To Session` assumes the COM apartment is initialized | defensive `CoInitialize`: works off the main thread (rf-mcp, threaded runners) |

## What you gain (adopt progressively)

- **Waits**: `Wait Until Busy Done`, `Wait Until Element Present`; retire
  every `Sleep`.
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
