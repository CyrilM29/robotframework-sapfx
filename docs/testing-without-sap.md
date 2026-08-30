> **🇬🇧 English** · [🇫🇷 Français](testing-without-sap.fr.md)

# Testing without a SAP system

You can make real progress on this project with **zero SAP access**. Three tiers,
from "works right now" to "full fidelity".

## Tier 1: Pure logic, no SAP, no Windows COM (today)

The fork's added logic (waits, retry, grid-by-title, transaction error detection)
is unit-tested against **fake COM objects**:

```bash
pip install pytest
python -m pytest tests/unit -q
```

`tests/unit/conftest.py` stubs the `robot.*` and pywin32 modules when they are
absent, so these run on a bare interpreter (even non-Windows). Install the real
deps (`pip install -r requirements.txt`) and the same tests run against the real
libraries. This validates **code structure and logic**, not live navigation.

## Tier 2: Real SAP GUI navigation, fully local (recommended)

**ABAP Platform Trial Docker image** (free developer licence, renew ~quarterly).
A real SAP backend on your machine; connect a local SAP GUI to it and the Scripting
API drives a genuine system. **Full step-by-step procedure: [ecc-validation.md](ecc-validation.md).**

- **Availability, checked 2026-08-23**: SAP has **discontinued** this trial.
  `sapse/abap-cloud-developer-trial` is absent from the 23 public repositories
  of the `sapse` namespace and the Docker Hub API answers 404; SAP had a
  community mirror unpublished in May 2026 (the image is licensed for personal
  use, not redistribution); and the older AS ABAP developer editions are
  **withdrawn from Docker Hub AND from SAP CAL on 30 September 2026**, so the
  CAL fallback this page used to recommend is going away too. If you already
  hold an image, keep it: a `docker save` to an external disk is the only
  guaranteed continuity. What remains freely available, with an ordinary SAP
  account: the **SAP BTP trial** (90 days, ABAP environment with RAP and Fiori
  Elements, Build Work Zone, a real IAS) and the **SAP Business Accelerator Hub
  sandbox** (api.sap.com, OData v2 and v4 of S/4HANA Cloud, API key in a
  header). Neither offers a SAP GUI, so neither can exercise `SapEccLibrary`.
- Requirements: **~16 GB RAM minimum** (32 GB comfortable), ~150 GB disk.
- **Pin the MAC address at creation** (`docker run --mac-address …`). The SAP
  hardware key derives from it, and since Docker 29 an unpinned container draws
  a new MAC at **every start**: the licence you requested yesterday is void this
  morning. Measured on a second system: key `Y1778494144` unpinned,
  `H0425704182` once pinned, then stable across a full stop/start cycle.
- Enable scripting once the system is up:
  - Server: write the parameters into the **instance profile**
    (`/sapmnt/<SID>/profile/<SID>_D00_<host>`), not through `RZ11`. An `RZ11`
    change is lost at the next instance stop, which matters if you shut the
    container down daily:
    `sapgui/user_scripting = TRUE`,
    `sapgui/user_scripting_disable_recording = FALSE`,
    `sapgui/user_scripting_set_readonly = FALSE`. Keep a `.bak` of the profile
    and restart the instance to load it.
  - Client: SAP GUI Options → Accessibility & Scripting → Scripting → enable, and
    untick the two "notify when a script…" boxes so dialogs don't block automation.
- **First calls are slow, and a timeout is not a verdict.** On a freshly booted
  system the first OData call to each service loads it server-side and can
  exceed the client's default timeout, which surfaces as `unreachable` or
  `TimeoutError` and points you at connectivity, where there is nothing to find.
  Measured: 2.2 s on the first catalogue call, 0.1 s on the second. Replay
  before diagnosing.
- **Installing SAP GUI also provisions the RFC runtime** (observed 2026-08-27,
  SAP GUI 8.00). Its « SAP NWRFC x64 Shared » component puts `sapnwrfc.dll` and
  the `icu*50` libraries into `C:\Windows\System32`, so the prebuilt `pyrfc`
  wheel loads and a real RFC call reaches the trial (`STFC_CONNECTION`,
  `RFC_READ_TABLE` on T000) without the licensed SAP NW RFC SDK, without
  `SAPNWRFC_HOME` and without a `PATH` entry. What this does NOT remove is the
  interpreter constraint: no prebuilt `pyrfc` wheel exists beyond Python 3.12,
  and building from source needs the very SDK headers the client omits. The
  reasons the SDK still matters are in the pack README, « RFC channel ».
- Then point `Open Sap Logon` / `Connect To Session` at it and run
  `tests/robot/ecc_smoke.robot`.

This is the **best fidelity-per-cost option** for the ECC library: real navigation,
no recurring hosting bill.

## Tier 3: Full S/4HANA scenarios (occasional)

**SAP Cloud Appliance Library (CAL)**: free 30-day appliances of complete systems
(S/4HANA, ABAP Platform). The software is free; you pay the **cloud hosting**
(AWS/Azure/GCP) while the VM runs. Use for end-to-end business scenarios you can't
reproduce on the trial image. **SAP BTP Trial / Free Tier** gives a hosted Fiori
Launchpad for the web side.

## Web / Fiori side (phase 2)

No SAP access needed at all: the **OpenUI5 Demo Kit** (`sdk.openui5.org`) and its
sample apps (Shopping Cart, Worklist) render the *same* SAPUI5 controls as a real
S/4HANA, so the web locator strategy and the UI5 recorder integration can be built
and tested entirely against public demo pages.

## Summary

| Need | Use | Cost |
|------|-----|------|
| Validate fork logic now | `pytest tests/unit` (fake COM) | free, instant |
| Real ECC GUI navigation | ABAP Platform Trial Docker (**discontinued by SAP, see above**) | free + your hardware |
| Full S/4HANA scenarios | SAP CAL (30-day; the older ABAP editions leave CAL on 2026-09-30) | cloud hosting only |
| Real Fiori launchpad, real IAS login | SAP BTP trial (90 days, **no SAP GUI**) | free, account required |
| Real S/4HANA Cloud OData v2 and v4 | api.sap.com sandbox (API key in a header) | free, account required |
| Fiori / web locators | OpenUI5 Demo Kit | free |
