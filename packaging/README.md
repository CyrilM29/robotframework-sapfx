> **🇬🇧 English** · [🇫🇷 Français](README.fr.md)

# SAPFX deployment pack (Windows)

Self-contained deployment pack for a Windows test PC. It bundles everything needed
to run SAP test automation with Robot Framework, without cloning the source repo:

| Pack content | What it is |
|---|---|
| `wheels/robotframework_sapfx-*.whl` | `SapEccLibrary` (SAP GUI desktop / ECC), `SapFioriLibrary` (Fiori / UI5 web), `SapApiLibrary` (API channel: OData v2/v4, optional RFC) and `sapfx_common`, in one wheel. |
| `wheels/sap_robotmcp-*.whl` | rf-mcp (RobotMCP) plugins `SapEccPlugin` / `SapFioriPlugin` / `SapApiPlugin` (keyword routing, SAP perception, selector guidance), plus the **`sapfx-mcp` overlay launcher** (rf-mcp unchanged + `sapfx_state`/`sapfx_screenshot`/`sapfx_reload` tools, startup compatibility guard). Optional (`-WithMcp`). |
| `resources/` | Business-readable Robot Framework keywords, one mirrored vocabulary per channel (`ecc_keywords`, `fiori_keywords`, `api_keywords`, `rfc_keywords`) plus page objects and demo-data guards. **Examples to customize**, measured on the lab systems of the project: reusable in good part, never authoritative, to be verified against your target and adapted to your business domain (see `resources/README.md`). Tests import this layer, never raw SAP ids; what holds on every SAP system is the library wheel, not this folder. Your own keywords go to `resources\site_keywords.resource` (see below), which a pack update never overwrites. |
| `tools/recorder/` + `recorder.cmd` | Desktop recorder (SAP GUI over COM): dump / capture / hover / record; record uses the Scripting API's native events (exact buttons) with automatic polling fallback. Double-click `recorder.cmd` to open the launcher GUI, which exposes the engine choice (auto/native/poll) and the semantic mode (human keywords by visible label). |
| `tools/recorder_web/` | Web recorder: `recorder_snippet.js` (paste in DevTools) and `extension/` (Chrome MV3 extension, load unpacked via `chrome://extensions`). |
| `tests/robot/` | Seven sample suites: ECC/Fiori smokes plus the deterministic offline `fiori_wc_smoke.robot`, the autonomous exploration campaign, drift sentinel, cross-paradigm flagship, and `api/canal_api_odata.robot` (the API channel on its own terms, the same business keywords against OData v2 with `--include a4h` and v4 with `--include capsflight`). |
| `scripts/` | Maintenance tooling (stdlib-only, run from the pack root): `healing_drift_report.py` (reads the healing telemetry, proposes, or applies with `--apply`, the `resources/` patches for stable locator drifts) and `check_spec_sync.py` (fails when a generated suite is stale vs its `specs/` plan). |
| `.claude/` + `.github/chatmodes/` + `specs/` | **SAP test agents** (sap-planner / sap-generator / sap-healer / sap-istqb): agent definitions + `/sap-*` commands for Claude Code, generated chat modes for VS Code / Copilot, and the test-plan directory with its reference example (+ `specs/istqb/` for ISTQB test plans). See « Test agents » below. |
| `install.cmd` / `install.ps1` | Installer: creates a local `.venv`, installs the wheels + pinned dependencies, renders the MCP configs. |
| `mcp.json.template` / `vscode-mcp.json.template` | Templates of the rf-mcp server declaration; `install.ps1 -WithMcp` renders them in place as `.mcp.json` (Claude Code) and `.vscode/mcp.json` (VS Code / Copilot), plus `mcp.generated.json` to copy into another project. |
| `LICENSE` / `NOTICE` | Apache-2.0 license and upstream attributions; keep them next to the binaries. |

## What the pack ships, and what it does not

The pack is an **execution** environment, not a copy of the source repo. On the
target PC that means:

- **No `src/`**: the libraries are installed as a wheel inside the venv, so
  their code cannot be fixed in place. That is the reason for the
  `resources\site_keywords.resource` rule (below): added keywords and locator
  overrides land there, and a pack update never overwrites them. A library
  defect gets reported upstream instead of being worked around locally,
  otherwise the same bug is paid for twice.
- **Seven sample suites**, not the repo's full validation suite: they are an
  installation check and a template to copy, not coverage.
- **Four maintenance scripts** out of the repo's fifteen or so: the others are
  development guards (bilingual pairing, vendor drift, AI-support consistency)
  that make no sense outside the repo.
- **No unit tests**: they run in CI on the source repo.

What is strictly identical is the libraries' **code**: the wheel contains
exactly `src/`, so a keyword behaves here as it does on the development
machine.

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

## RFC channel: optional, and not installed

`pip` does not install `pyrfc`, deliberately: that binding needs the **SAP NW
RFC runtime**, a C library that is not on PyPI. Its official vehicle is the
**SAP NW RFC SDK**, which SAP distributes under licence from its download
portal, so no installer can provision it for you.

Its absence breaks nothing: the import happens inside the keyword, not at
module load. `SapApiLibrary` imports and works, and the **whole OData channel**
stays available (v2 and v4, `$batch`, the CSRF protocol, `$metadata`, catalog,
Gateway preflight, test-data factory).

Only six keywords depend on it: `Open Rfc Connection`, `Call Rfc`, `Call Bapi`,
`Commit Bapi Transaction`, `Rollback Bapi Transaction` and
`Wait For Background Job`. Calling them without `pyrfc` yields a test failure
naming what to do, never a `ModuleNotFoundError` when the suite starts.

### If SAP Logon is installed, you can already run RFC tests (observed 2026-08-27)

Read this before hunting for an S-user: **a workstation that runs SAP Logon
already carries the RFC runtime.** Installing SAP GUI for Windows 8.00 installs
its « SAP NWRFC x64 Shared » component, which drops `sapnwrfc.dll` (version
7530.1116 when measured, kernel variant, release 750 patch level 11) plus
`icudt50.dll`, `icuin50.dll` and `icuuc50.dll` into `C:\Windows\System32`. The
Windows loader finds them there with no `SAPNWRFC_HOME` and no `PATH` entry, so
the prebuilt `pyrfc` wheel loads and a **real** RFC call goes through: measured
against an ABAP Platform trial, `STFC_CONNECTION` echoed its text and
`RFC_READ_TABLE` read T000 through `Open Rfc Connection` / `Call Rfc`.

In practice this covers the common case, because a workstation that tests the
ECC channel has SAP GUI on it by definition. One command tells you where you
stand, and it costs less than a download portal:

```bat
REM no archive, no S-user: use the runtime SAP GUI already installed
powershell -ExecutionPolicy Bypass -File install-rfc.ps1 -UseSapGuiRuntime
```

It refuses cleanly if the runtime is not there (no SAP GUI on this machine),
installs the pinned `pyrfc` into the pack venv, and runs a real import check.
An import is still not a connection: confirm with an actual RFC call before
concluding. `install-rfc.ps1 -CheckOnly` reports this configuration for what it
is instead of calling the SDK missing.

**That said, the SDK remains the goal to aim for**, and this shortcut is what
unblocks you meanwhile, not what replaces it. Three reasons, in decreasing order
of how soon they will catch up with you:

- **It is the only route off this workstation.** A CI runner, a build agent or a
  colleague's machine without SAP GUI has no runtime at all. Anything that must
  run somewhere else needs the SDK, and planning for it early avoids discovering
  it the day a pipeline is meant to go green.
- **Licence and support.** That DLL ships as part of the SAP GUI client, for the
  client. The artifact SAP supports for RFC development, versions and patches is
  the SDK: a support ticket will ask which one you installed.
- **A patch level you did not choose, and no source build.** You get whatever
  the client carries, and an incompatibility with `pyrfc` would not show at
  import, only in use. On a Python with no prebuilt wheel (3.13 and later),
  compiling needs the SDK headers, which the client does not ship.

One constraint the shortcut does **not** lift: the interpreter. No prebuilt
`pyrfc` wheel exists beyond Python 3.12, so the venv is created on 3.10 to 3.12
whether or not you have the SDK.

`install-rfc.ps1 -CheckOnly` does not know about this case yet: it reports the
SDK as missing and exits 1 on a workstation where the channel works. Its
`pyrfc` line, on the other hand, tells the truth.

### Provisioning procedure (once per workstation)

1. **Get the archive.** SAP for Me, Software Downloads section: you need an
   S-user carrying the « Software Download » authorization, hence a customer or
   partner contract. Search for `SAP NW RFC SDK 7.50`, platform *Windows on x64
   64bit*. SAP Note **2573790** is the reference for availability, supported
   platforms and patch levels.
2. **Windows prerequisite.** Install the *Visual C++ Redistributable for Visual
   Studio 2013* (x64): the C library needs it at run time, and its absence
   produces a DLL load error rather than a clear message.
3. **Unpack** the archive, for instance into `C:\nwrfcsdk`, so that
   `C:\nwrfcsdk\lib` exists.
4. **Declare the environment variables**: `SAPNWRFC_HOME=C:\nwrfcsdk`, and add
   `C:\nwrfcsdk\lib` to `PATH` (that is how the DLLs are found at run time).
5. **Install the binding** into the pack venv:
   `.venv\Scripts\python.exe -m pip install pyrfc==3.3.1`
6. **Verify**:
   `.venv\Scripts\python.exe -c "from pyrfc import Connection; print('pyrfc OK')"`

Steps 2 to 6 are scripted by `install-rfc.ps1` (see below).

### Upstream status, worth knowing before committing (observed 2026-08-26)

- SAP **archived** the PyRFC repository on 2026-05-28: the project is no longer
  maintained and no official replacement has been announced.
- **Every release published on PyPI is yanked**: pip no longer selects them on
  its own, hence the exact pin in step 5.
- **Prebuilt Windows wheels stop at Python 3.12.** On a 3.13 or 3.14 venv pip
  would attempt a source build (Cython plus the MSVC Build Tools). If the RFC
  channel matters to you, create the pack venv with a **3.10 to 3.12**
  interpreter, a choice made at install time and not after.
- The latest release is built against an SDK patch level SAP no longer
  supports.

None of this affects the OData channel, which remains the nominal path.

### Automating this provisioning

`install-rfc.ps1` scripts everything **except** obtaining the archive:

```bat
REM the archive is already on the machine (or on a share)
powershell -ExecutionPolicy Bypass -File install-rfc.ps1 -SdkZip C:\downloads\nwrfc750P_13-70002755.zip

REM or pulled from the company's internal mirror
powershell -ExecutionPolicy Bypass -File install-rfc.ps1 -SdkUrl https://artifacts.internal/sap/nwrfc750.zip -SdkUrlToken $env:ARTIFACTS_TOKEN

REM or no archive at all, on a machine that runs SAP Logon
powershell -ExecutionPolicy Bypass -File install-rfc.ps1 -UseSapGuiRuntime
```

It unpacks to `-SdkHome` (default `C:\nwrfcsdk`), sets `SAPNWRFC_HOME` and the
`PATH` for the user, installs the pinned `pyrfc` into the pack venv and runs a
real import check. `-Machine` writes the variables machine-wide (needs an
elevated shell), `-CheckOnly` diagnoses an existing installation without
touching anything.

`-UseSapGuiRuntime` is the archive-free mode described above: it leans on the
RFC runtime the SAP GUI client installed, so it touches no environment variable
(the DLLs live in `System32`, which the loader reads anyway), installs the
binding and checks the import. It refuses if no runtime is there, and it refuses
to be combined with `-SdkZip`, `-SdkUrl` or `-SkipPyrfc` rather than silently
ignoring half of what you asked. Use it to get working today; keep the SDK as
the target, since this mode is true of **this** machine only.

The **download** cannot be anonymous: the portal requires an S-user and the
licence forbids redistributing the archive, so it will never be in the pack nor
in a public repository. Two workable routes, in this order:

1. **Internal mirror** (recommended): download the archive once by hand, put it
   in the company artifact store (Artifactory, Nexus, Azure Artifacts, an
   internal share), and point `-SdkUrl` at it.
2. **Authenticated direct download**: `softwaredownloads.sap.com` URLs accept
   S-user basic authentication (`curl -u` / `wget`), a common practice but not
   a contractual interface: the supported tool remains the SAP Download
   Manager, and the credentials must live as factory secrets, never in a
   versioned script (convention 11 of the source repo).

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
  `-v FAIL_ON_DRIFT:True` turns the report into an assertion. Visual
  references follow the capture geometry: `${PER_RESOLUTION}` is `True` in
  this suite, so a screen resolution not seen before **records** its visual
  reference and compares only the structural channel on that pass, instead of
  crying drift.
- **Visual assertions** (Pillow, installed by `requirements-deploy.txt`):
  `Screen Should Match Baseline` and `Element Should Match Baseline` (ECC;
  the element variant crops the baseline to ONE control: opaque GuiShell,
  charts) and `Ui5 Screen Should Match Baseline` (Fiori) share one snapshot
  cycle: the first run records the baseline PNG (keep it), later runs fail
  on drift with the Hamming distance and save an `.actual.png` next to it;
  `mask_elements=auto` neutralizes the volatile status/title bars before
  hashing. **A fingerprint encodes the capture geometry as much as the
  content**: baselines brought from another workstation therefore fail on a
  mere screen-resolution difference, with nothing on screen having moved.
  Record them on the machine that will replay them, or pass
  `per_resolution=True` to keep one baseline per geometry
  (`<name>@1920x1032.png`, created on that machine's first pass like any first
  baseline); when the two geometries differ, the failure says so and lists the
  ones already known.
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
- `Call Rfc a besoin de pyrfc (et du SAP NW RFC SDK)` → expected: see « RFC
  channel » above. The OData keywords do not need it.
- A `dev_rfc.log` appears next to your suite → normal: the NW RFC library
  writes its trace into the CURRENT directory when a connection fails. Read it,
  it names the RFC runtime it loaded, then delete it.
- A visual assertion fails on the very first run on a new machine → check the
  screen resolution first: see the geometry note under « Watch & maintenance ».

---
This pack is generated from the source repo by
`python scripts/build_release_pack.py`: do not edit its files in place; fix the
repo and rebuild. Full end-to-end walkthrough (build → transfer → install →
validate → MCP): `docs/deployment-pack.md` in the source repo.
