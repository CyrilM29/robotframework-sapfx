> **🇬🇧 English** · [🇫🇷 Français](deployment-pack.fr.md)

# Deployment pack: end-to-end walkthrough

How to take the libraries, recorders and rf-mcp plugins from this repo to a
Windows test PC that has no clone of the repo. Five steps, ~10 minutes plus
downloads.

The pack is the **full-install distribution channel**, the only one that
carries everything: libraries, recorders (desktop GUI + web MV3 extension),
rf-mcp plugins with the `sapfx-mcp` launcher, business resources, sample
suites, maintenance scripts and the test agents, in one auditable ZIP
(SHA-256 + SBOM + provenance). PyPI (`pip install robotframework-sapfx`)
carries the **libraries only**: right for adding the keywords to an existing
Robot Framework project, not for provisioning a complete test workstation.
That is what makes the pack the recommended route for target test machines
(the installer still needs PyPI or an internal mirror for the pinned
dependencies; see step 3).

```
Dev PC (this repo)                      Target Windows PC
──────────────────                      ─────────────────
build_release_pack.py ──► sapfx-pack-<v>-win.zip ──► unzip
                                                      │ install.cmd [-WithMcp] [-WithBrowsers]
                                                      │ robot tests\robot\fiori_smoke.robot
                                                      ▼
                                        .venv + recorders + mcp.generated.json
```

## 1. Build the pack (dev PC)

```bash
python scripts/build_release_pack.py
```

Output: `dist/sapfx-pack-<version>-win.zip` (and the unzipped staging next to it).
The script builds both wheels (`pip wheel --no-deps`), assembles the manifest
(recorders, `resources/`, six sample suites including the offline Browser smoke, the maintenance scripts
`healing_drift_report.py`/`check_spec_sync.py`, the test agents, installer,
LICENSE/NOTICE) and zips.
`--skip-wheels` re-assembles without rebuilding the wheels; the version comes
from `pyproject.toml`. Sources of everything the pack adds (installer, READMEs,
MCP template) live in [`packaging/`](../packaging/): fix there and rebuild,
never edit `dist/` in place.

## 2. Transfer

Copy the zip to the target PC (share, USB…) and unzip it anywhere the user can
write, e.g. `C:\sapfx\`. All paths inside the pack are relative to its root.

The pack is also **publicly downloadable** (no GitHub account needed) from
[CyrilM29/robotframework-sapfx](https://github.com/CyrilM29/robotframework-sapfx/releases):
each release is published there with public-safe notes, alongside the
public source tree (open since 0.6.4) and the PyPI libraries-only
distribution.

## 3. Install (target PC)

Prerequisites: Windows 10/11, Python 3.10+ on the `PATH`, Internet access
**during this step only** (pip pulls Robot Framework, pywin32,
robotframework-browser…; the wheels of *this* repo are already in the pack).

```bat
cd C:\sapfx\sapfx-pack-<version>-win
install.cmd                 REM libraries only
install.cmd -WithMcp        REM + rf-mcp plugins (AI agent use)
install.cmd -WithBrowsers   REM + Playwright Chromium (else: system Chrome, channel=chrome)
```

The installer creates `.venv\` in the pack folder, applies the qualified
`constraints-deploy.txt` versions, runs an
import smoke check, and, with `-WithMcp`, renders `mcp.generated.json` with
the absolute path of the venv's `robotmcp.exe`. Nothing global is touched (no
`PATH` change, no system site-packages).

## 4. Validate

```bat
.venv\Scripts\robot.exe tests\robot\fiori_wc_smoke.robot REM offline, no SAP
.venv\Scripts\robot.exe tests\robot\fiori_smoke.robot     REM web side: needs network, no SAP
.venv\Scripts\robot.exe -v SAP_CONNECTION:"..." -v SAP_USER:... -v "SAP_PASSWORD: Secret:..." tests\robot\ecc_smoke.robot
```

The `: Secret:` form is Robot Framework 7.4's typed-variable syntax: the
password never appears in logs, even at TRACE level.

For the ECC side, SAP GUI for Windows must be installed with scripting enabled
(client option + server profile `sapgui/user_scripting`), and `SAP_CONNECTION`
must match an entry of the local SAP Logon. The recorders are ready too:
double-click `recorder.cmd` (desktop, uses the venv's Python) or load
`tools\recorder_web\extension` unpacked via `chrome://extensions` (web).

## 5. Hook up the AI agent (optional, `-WithMcp`)

Copy `mcp.generated.json` as `.mcp.json` at the root of the project where the
agent runs (Claude Code), or merge it into `.vscode/mcp.json` (VS Code / Copilot
agent mode). No `PYTHONPATH` is needed: the plugins are installed in the venv
and register via entry points.

## Updating an existing installation

Rebuild the zip on the dev PC (step 1), unzip **over** the existing pack folder
on the target, and re-run `install.cmd` with the same switches: the venv is
reused and pip upgrades the wheels in place. To start clean, delete `.venv\`
first.

## Limits

- The install step needs PyPI (or an internal mirror). For air-gapped targets,
  ask for the offline variant (dependency wheels bundled in `wheels/`), not
  built by default because pywin32 wheels are Python-version specific.
- The pack ships six sample suites (the ECC/Fiori smokes, the offline WC smoke, the autonomous
  exploration campaign, the drift sentinel and the cross-paradigm flagship);
  the other campaign suites (data-driven, SCARR/SPFLI…) stay in the repo
  because they need a live A4H or local fixtures.

## Integrity and provenance

The ZIP is accompanied by a `.zip.sha256` sidecar and a CycloneDX SBOM of the
clean installed environment. `SHA256SUMS.txt` verifies every file inside the
pack. The CI `release-pack` job also issues a GitHub build-provenance attestation
for ZIPs built from pushes (mandatory for public repositories, best-effort for
private repositories whose plan may not expose attestations).
