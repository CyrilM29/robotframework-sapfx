> **🇬🇧 English** · [🇫🇷 Français](testing-without-sap.fr.md)

# Testing without a SAP system

You can make real progress on this project with **zero SAP access**. Three tiers,
from "works right now" to "full fidelity".

## Tier 1 — Pure logic, no SAP, no Windows COM (today)

The fork's added logic (waits, retry, grid-by-title, transaction error detection)
is unit-tested against **fake COM objects**:

```bash
pip install pytest
python -m pytest tests/unit -q
```

`tests/unit/conftest.py` stubs the `robot.*` and pywin32 modules when they are
absent, so these run on a bare interpreter (even non-Windows). Install the real
deps (`pip install -r requirements.txt`) and the same tests run against the real
libraries. This validates **code structure and logic** — not live navigation.

## Tier 2 — Real SAP GUI navigation, fully local (recommended)

**ABAP Platform Trial — Docker image** (free developer licence, renew ~quarterly).
A real SAP backend on your machine; connect a local SAP GUI to it and the Scripting
API drives a genuine system. **Full step-by-step procedure: [ecc-validation.md](ecc-validation.md).**

- Get the image `sapse/abap-cloud-developer-trial:<TAG>` **if available** — as of
  2026 it appears withdrawn (404) from Docker Hub; if so, use **SAP CAL**
  (`cal.sap.com`) instead. Full guidance: [ecc-validation.md](ecc-validation.md).
- Requirements: **~16 GB RAM minimum** (32 GB comfortable), ~150 GB disk.
- Enable scripting once the system is up:
  - Server: transaction `RZ11` → set `sapgui/user_scripting = TRUE` (and
    `sapgui/user_scripting_per_user` as needed).
  - Client: SAP GUI Options → Accessibility & Scripting → Scripting → enable, and
    untick the two "notify when a script…" boxes so dialogs don't block automation.
- Then point `Open Sap Logon` / `Connect To Session` at it and run
  `tests/robot/ecc_smoke.robot`.

This is the **best fidelity-per-cost option** for the ECC library: real navigation,
no recurring hosting bill.

## Tier 3 — Full S/4HANA scenarios (occasional)

**SAP Cloud Appliance Library (CAL)** — free 30-day appliances of complete systems
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
| Real ECC GUI navigation | ABAP Platform Trial Docker | free + your hardware |
| Full S/4HANA scenarios | SAP CAL (30-day) | cloud hosting only |
| Fiori / web locators | OpenUI5 Demo Kit | free |
