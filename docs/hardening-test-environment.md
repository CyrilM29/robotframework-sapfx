> **🇬🇧 English** · [🇫🇷 Français](hardening-test-environment.fr.md)

# Hardening the SAP Test Environment

Test automation concentrates risk in one place: a workstation that holds **real
SAP credentials**, types **real data into real screens**, records screens and
keystrokes, and exposes an automation API that any local process can drive.
This guide is the security checklist for that setup — server side, workstation
side, web side, and the AI-agent (MCP) side — and maps each point to the
**preflight keywords** that verify it automatically.

Sources: SAP GUI Scripting Security Guide (help.sap.com), SAP Security Note
3472837 / CVE-2025-0055 (January 2025), SAP GUI for Windows 8.10 GA
announcement (SAP Community, July 2026), SAP Security Note 3747367
(July 2026 Patch Day, SAP GUI for HTML).

## 1. Server side (RZ11 profile parameters)

SAP GUI Scripting is **disabled by default** (`sapgui/user_scripting = FALSE`).
A script has **exactly the rights of the user who runs it** — the server does
not distinguish scripted from human traffic. The consequence works both ways:

- scripting does not escalate privileges, but
- an unattended script can mass-create bad data at the speed of the test user's
  authorizations.

Recommended posture:

| Parameter | Recommended value | Why |
|---|---|---|
| `sapgui/user_scripting` | `TRUE` (uppercase!) on **test systems only** | required for any scripting |
| `sapgui/user_scripting_per_user` | `TRUE` | scripting restricted to users holding **S_SCR Execute(16)** (class BC_A) — grant it to the dedicated test account only. This is SAP's official mechanism to confine scripting without a dedicated app server |
| `sapgui/user_scripting_set_readonly` | `FALSE` on test systems | when `TRUE` the API can read but not act — tests fail strangely |
| `sapgui/user_scripting_disable_recording` | `FALSE` if you use the native-event recorder | when `TRUE` all scripting **events** are cut (the desktop recorder's `--engine native` falls back to polling automatically) |

Never enable scripting broadly on production; give the test user the minimal
business roles the scenarios need, nothing more.

**Preflight:** `Scripting Should Be Fully Enabled` (Suite Setup) fails early
with the exact RZ11 parameter to fix, and now names the `per_user`/S_SCR path
when the server refuses scripting despite `user_scripting = TRUE`.

### WebGUI (SAP GUI for HTML) — activate with your eyes open

The WebGUI `sid` engine needs the ICF service
`/default_host/sap/bc/gui/sap/its/webgui`, **inactive by default**. Before
activating it, know **SAP Security Note 3747367** (July 2026 Patch Day): a
memory corruption in SAP GUI for HTML rated **CVSS 9.9** (authenticated
attacker → data read/modification, availability), affecting every ICF node
with the interactive-GUI setting active. The fix is an ABAP **kernel patch**
(downtime); the only workaround — deactivating the ICF nodes — removes the
WebGUI entirely. Trial systems such as the A4H Docker image typically run an
unpatched kernel: keep them on an isolated network, activate the `webgui`
service on test systems only, and never expose it beyond the test segment.

### Patch level — input-history encryption (CVE-2025-0055)

Until January 2025, SAP GUI for Windows stored the **input history** (every
value typed into fields, including by your test runs) in local SQLite files
(`SAPHistory<WINUSER>.db`) protected by a **static-key XOR** — trivially
reversible (CVE-2025-0055, SAP Note 3472837; the SAP GUI for Java variant is
CVE-2025-0056). Fixed from **SAP GUI for Windows 8.00 PL9**; 8.10 (GA
2026-07-16, supported until 2029-06-30) ships fixed. Note that 8.00 leaves
full support on **2027-01-12** — plan the 8.10 migration of test workstations.

### Disable the input history on test workstations

Even patched, the history is a copy of everything your suites type, sitting in
the Windows profile. On a test workstation: **Options → Local Data → History →
disable**, and purge existing `SAPHistory*.db` files.

**Preflight:** `Client Security Should Be Hardened` fails if the client is
CVE-vulnerable or if history databases are present
(`allow_input_history=True` to tolerate knowingly);
`Get Client Security Status` returns the full read-only posture (also through
rf-mcp).

### Other workstation points

- Dedicated Windows account for test execution; captures/screenshots
  directories (`tools/recorder/captures/`, Robot `results/`) stay out of VCS —
  screenshots can contain personal data (GDPR): treat run artifacts as data.
- The healing telemetry (`SAPFX_HEALING_LOG`) **never logs typed values** — by
  design; keep it that way when extending it.
- Accessibility mode (client setting) is required to read classic ABAP lists —
  see `Abap List Should Be Readable` (functional preflight, same philosophy).

## 3. Credentials

- Never hardcode credentials in `.robot` files or resources — inject them per
  run from CI secrets or a local vault, as a **typed `Secret` variable**
  (Robot Framework 7.4): `-v "SAP_PASSWORD: Secret:…"`. A `Secret` is masked
  everywhere — even a TRACE log only shows `<secret>` — and every
  password-accepting keyword of the three libraries takes it (`Input
  Password`, `Open Sap Session`, `Open Api Session`, `Open Rfc Connection`,
  `Log In Via Identity Provider`), unwrapping it only at the COM/HTTP
  boundary.
- A plain `-v SAP_PASSWORD:…` string still works everywhere, but its raw
  value surfaces in TRACE logs when keywords echo their arguments — the typed
  `Secret` form is the recommended default. Either way, keep `Input
  Password`-style keywords (which never log the value) for password fields.
- Prefer SNC/SSO where the landscape offers it (no password in the loop).

## 4. Web side (Fiori / Browser library)

- **MV3 recorder extension**: injection is `activeTab`-scoped (user gesture
  required), no broad host permissions — keep it that way; the store zip is
  built from source (`package.py`), never add remotely-hosted code (MV3 policy).
- **Embedded-browser debugging** (`Enable Embedded Browser Debugging`) opens a
  **CDP debug port** on the WebView2 runtime: any local process can attach to
  it. Test workstations only, never on shared machines; unset for normal use.
- **CSP**: the `__SAPFX` bundle is injected through Playwright's evaluate
  (CDP), which page CSP does not block — no CSP relaxation is needed on the
  system under test (verified by the strict-CSP fixture smoke,
  `fiori_csp_smoke.robot`).

## 5. AI agents / MCP side

- rf-mcp runs in **stdio** (no network listener); keep it that way — do not
  wrap it in a TCP bridge on shared machines.
- API and Fiori state is partitioned by rf-mcp session. Keep one live ECC
  session per rf-mcp process because nested resource calls are not reliably
  attributed by rf-mcp 0.31 (see `integrations/robotmcp/README.md`).
- Perception output (screen signatures, screenshots) can contain real business
  data: MCP transcripts and agent logs are **data**, subject to the same
  retention rules as run artifacts.
- Prompt-injection containment: an agent acts with the test user's rights —
  the least-privilege test account of §1 is also your blast-radius limiter.

## 6. Supply chain

- `pywin32` is pinned exactly (`==`, convention 6) in `requirements.txt` /
  `requirements-deploy.txt`; review before bumping.
- Keep `constraints-deploy.txt`, the ZIP SHA-256 sidecar, CycloneDX SBOM and
  build-provenance attestation together with each qualified release.
- The deployment pack is distributed via the releases-only public repo —
  verify you install wheels from a release you trust, not a fork.

## 7. Suite Setup pattern

```robotframework
*** Settings ***
Library     SapEccLibrary
Suite Setup    Preflight

*** Keywords ***
Preflight
    Open Sap Logon    ${SAP_CONNECTION}
    Connect To Session
    Scripting Should Be Fully Enabled
    Client Security Should Be Hardened
```

Both preflights are read-only, locale-independent, and fail with the exact
parameter or client action to fix.
