> **🇬🇧 English** · [🇫🇷 Français](README.fr.md)

# SAPFX deployment pack (Windows)

Self-contained deployment pack for a Windows test PC. It bundles everything needed
to run SAP test automation with Robot Framework, without cloning the source repo:

| Pack content | What it is |
|---|---|
| `wheels/robotframework_sapfx-*.whl` | `SapEccLibrary` (SAP GUI desktop / ECC), `SapFioriLibrary` (Fiori / UI5 web), `SapApiLibrary` (API channel: OData v2/v4, optional RFC) and `sapfx_common`, in one wheel. |
| `wheels/sap_robotmcp-*.whl` | rf-mcp (RobotMCP) plugins `SapEccPlugin` / `SapFioriPlugin` / `SapApiPlugin` (keyword routing, SAP perception, selector guidance), plus the **`sapfx-mcp` overlay launcher** (rf-mcp unchanged + `sapfx_state`/`sapfx_screenshot`/`sapfx_reload` tools, startup compatibility guard). Optional (`-WithMcp`). |
| `resources/` | Business-readable Robot Framework keywords (`ecc_keywords.resource`, `fiori_keywords.resource`, `a4h_demo_data.resource`). Tests should import these, never raw SAP ids. |
| `tools/recorder/` + `recorder.cmd` | Desktop recorder (SAP GUI over COM): dump / capture / hover / record; record uses the Scripting API's native events (exact buttons) with automatic polling fallback. Double-click `recorder.cmd` to open the launcher GUI, which exposes the engine choice (auto/native/poll) and the semantic mode (human keywords by visible label). |
| `tools/recorder_web/` | Web recorder: `recorder_snippet.js` (paste in DevTools) and `extension/` (Chrome MV3 extension, load unpacked via `chrome://extensions`). |
| `tests/robot/` | Seven sample suites: ECC/Fiori smokes plus the deterministic offline `fiori_wc_smoke.robot`, the autonomous exploration campaign, drift sentinel, cross-paradigm flagship, and `api/canal_api_odata.robot` (the API channel on its own terms, the same business keywords against OData v2 with `--include a4h` and v4 with `--include capsflight`). |
| `scripts/` | Maintenance tooling (stdlib-only, run from the pack root): `healing_drift_report.py` (reads the healing telemetry, proposes, or applies with `--apply`, the `resources/` patches for stable locator drifts) and `check_spec_sync.py` (fails when a generated suite is stale vs its `specs/` plan). |
| `.claude/` + `.github/chatmodes/` + `specs/` | **SAP test agents** (sap-planner / sap-generator / sap-healer / sap-istqb): agent definitions + `/sap-*` commands for Claude Code, generated chat modes for VS Code / Copilot, and the test-plan directory with its reference example (+ `specs/istqb/` for ISTQB test plans). See « Test agents » below. |
| `install.cmd` / `install.ps1` | Installer: creates a local `.venv`, installs the wheels + pinned dependencies, renders the MCP configs. |
| `mcp.json.template` / `vscode-mcp.json.template` | Templates of the rf-mcp server declaration; `install.ps1 -WithMcp` renders them in place as `.mcp.json` (Claude Code) and `.vscode/mcp.json` (VS Code / Copilot), plus `mcp.generated.json` to copy into another project. |
| `LICENSE` / `NOTICE` | Apache-2.0 license and upstream attributions; keep them next to the binaries. |

## Prerequisites on the target PC

- **Windows 10/11**, **Python 3.10+** on the `PATH` (`python` or the `py` launcher).
- Internet access **during installation** (pip downloads Robot Framework, pywin32,
  robotframework-browser…). Execution afterwards can be offline (except suites
  targeting public sites).
- For the **ECC side**: SAP GUI for Windows installed, with scripting enabled
  (client and server side).
- For the **Fiori side**: either run `install.cmd -WithBrowsers` (downloads
  Playwright's Chromium), or use the system Chrome
  (`New Browser    chromium    channel=chrome`, no download needed).

## Install

```bat
install.cmd                 REM libraries only (ECC + Fiori)
install.cmd -WithMcp        REM + rf-mcp plugins (pulls rf-mcp)
install.cmd -WithBrowsers   REM + Playwright Chromium (rfbrowser init)
install.cmd -WithMcp -WithBrowsers
```

The installer creates `.venv\` inside the pack directory, installs the wheels and
`requirements-deploy.txt` under the qualified versions in
`constraints-deploy.txt`, runs an import smoke check, and (with `-WithMcp`)
renders the MCP configs with the absolute path of the venv's `sapfx-mcp`
launcher (falling back to `robotmcp` on older wheels):
`.mcp.json`, `.vscode\mcp.json` and `mcp.generated.json`.

## Validate

```bat
.venv\Scripts\robot.exe tests\robot\fiori_wc_smoke.robot
.venv\Scripts\robot.exe tests\robot\fiori_smoke.robot
.venv\Scripts\robot.exe -v SAP_CONNECTION:"..." -v SAP_USER:... -v "SAP_PASSWORD: Secret:..." tests\robot\ecc_smoke.robot
```

`fiori_wc_smoke.robot` is the deterministic offline installation check (real
Chromium, no SAP or network). `fiori_smoke.robot` runs against the public OpenUI5
Demo Kit. `ecc_smoke.robot` needs a reachable SAP system and a `SAP_CONNECTION` entry
present in the local SAP Logon. The `: Secret:` form is Robot Framework 7.4's
typed-variable syntax: the password never appears in logs, even at TRACE level.

## Artifact integrity

`SHA256SUMS.txt` covers every file inside the pack. The release also publishes
`sapfx-pack-<version>-win.zip.sha256`, a CycloneDX SBOM generated from the clean
installed environment, and a GitHub build-provenance attestation for the ZIP.
The attestation is mandatory on public repositories and best-effort on private
repositories whose GitHub plan may not expose attestations. Verify the sidecar
hash before installing a transferred artifact.

## Environment preflights (new in 0.5.5)

Before blaming a red suite, check the posture of the test environment: three
read-only keyword pairs (all in `SapEccLibrary`, locale-independent) verify it
and *name the exact setting to fix*:

- **Server**: `Scripting Should Be Fully Enabled` fails early when the
  system refuses or restricts scripting, naming the RZ11 parameter
  (`sapgui/user_scripting`, readonly, recording) and the per-user path
  (`user_scripting_per_user` + S_SCR) to confine scripting to test accounts.
- **Workstation rendering**: `Abap List Should Be Readable` detects classic
  ABAP lists rendered as an opaque shell (no labels) and names the SAP GUI
  accessibility mode to provision on the workstation.
- **Workstation security**: `Client Security Should Be Hardened` checks the
  SAP GUI client is patched against the input-history weak encryption
  (CVE-2025-0055, fixed from 8.00 PL9) and flags leftover `SAPHistory*.db`
  input-history databases to purge (test runs type real data into real
  fields).

The full checklist (server, workstation, web, MCP containment) is
`docs/hardening-test-environment.md` in the source repo, each point mapped to
the preflight that verifies it.

## Use the MCP plugins

With `-WithMcp` the pack folder is ready to use as an agent workspace:
`.mcp.json` (Claude Code) and `.vscode/mcp.json` (VS Code / Copilot agent mode)
are rendered in place: open the folder in VS Code and approve the `rf-mcp-sap`
server on first use. If the AI agent runs in **another** project, copy
`mcp.generated.json` there as `.mcp.json`, or merge it into that project's
`.vscode/mcp.json`. No `PYTHONPATH` is needed: libraries and plugins are
installed in the venv and the plugins register through entry points.

## Test agents (plan → generate → heal)

The pack ships the SAP test agents (requires `-WithMcp`): **sap-planner**
explores the live system through rf-mcp and writes a business-readable test
plan under `specs/`; **sap-generator** turns a plan into a Robot Framework
suite under `tests\robot\`, verifying every step live before writing it;
**sap-healer** repairs a failing suite by patching the resources layer, with
live evidence; **sap-istqb** (offline, no MCP needed) turns planner specs and
recorder outputs into an ISTQB test plan + test cases under `specs\istqb\`
(human-readable, replayable by an AI with any framework via its normalized
replay blocks; both recorders emit the same template as a draft, `--export-istqb`
on the desktop, the « plan ISTQB » export-menu entry on the web). Claude Code
users get the `/sap-plan`, `/sap-generate`, `/sap-heal` and `/sap-istqb`
commands; VS Code / Copilot users pick the matching chat modes
(`sap-planner`, `sap-generator`, `sap-healer`, `sap-istqb`).

The pack also ships the **`sapfx` skill** (`.claude\skills\sapfx\`): a Claude
Code assistant opening the pack folder learns the toolkit in one call: the
three channels, the perception → action loop (numbered map `Get Screen Map` +
`Click/Fill Screen Ref`), the non-negotiable conventions and the agent cycle.
No installation: the skill is picked up with the folder.

Local rule on a deployed pack: the agents never modify the files shipped by
the pack: new keywords and locator overrides land in
`resources\site_keywords.resource`, so a pack update never overwrites local
work. Full walkthrough: `docs/test-agents.md` in the source repo.

## Watch & maintenance

- **Drift sentinel** (screen watch without writing a single test):

  ```bat
  .venv\Scripts\robot.exe -v SAP_CONNECTION:"..." -v SAP_USER:... -v "SAP_PASSWORD: Secret:..." tests\robot\ecc_drift_sentinel.robot
  ```

  The first pass records the reference of each watched transaction under
  `screen_watch\` (keep that folder): structured signature, global visual
  fingerprint AND a per-tile grid (`*.tiles.txt`, new in 0.5.2); every later
  pass reports ONLY what moved, line by line, in the Robot log: renamed ids
  are paired (`~ old -> new  (similarity N%)`) and a local visual drift is
  localized to its tile (position, pixel rectangle, covering elements).
  Watching one more screen = adding its tcode to `@{WATCHED_TRANSACTIONS}`;
  `-v FAIL_ON_DRIFT:True` turns the report into an assertion.
- **Visual assertions** (Pillow, installed by `requirements-deploy.txt`):
  `Screen Should Match Baseline` and `Element Should Match Baseline` (ECC;
  the element variant crops the baseline to ONE control: opaque GuiShell,
  charts) and `Ui5 Screen Should Match Baseline` (Fiori) share one snapshot
  cycle: the first run records the baseline PNG (keep it), later runs fail
  on drift with the Hamming distance and save an `.actual.png` next to it;
  `mask_elements=auto` neutralizes the volatile status/title bars before
  hashing.
- **Healing telemetry → patch proposals**: run the suites with
  `SAPFX_HEALING_LOG=<path>.jsonl` set, then
  `.venv\Scripts\python.exe scripts\healing_drift_report.py --log <path>.jsonl`
  separates stable locator drifts (a `resources\` patch is located and
  proposed; `--apply` executes it) from unstable ones to review. Exit code 1
  signals drift, usable as a scheduled alert.
- **Specs stay the source of truth**: for suites generated by the agents,
  `.venv\Scripts\python.exe scripts\check_spec_sync.py` fails when a plan in
  `specs\` changed after its suite was generated: re-run `/sap-generate`
  instead of hand-editing the suite.

## Troubleshooting

- `ImportError: DLL load failed` on `win32api` → run once:
  `.venv\Scripts\python.exe .venv\Scripts\pywin32_postinstall.py -install`
- `robot` not found → always call the venv executables
  (`.venv\Scripts\robot.exe`), the installer does not touch the global `PATH`.
- SAP GUI « scripting support is disabled » → enable scripting in SAP Logon
  options and check profile parameter `sapgui/user_scripting` server side.

---
This pack is generated from the source repo by
`python scripts/build_release_pack.py`: do not edit its files in place; fix the
repo and rebuild. Full end-to-end walkthrough (build → transfer → install →
validate → MCP): `docs/deployment-pack.md` in the source repo.
