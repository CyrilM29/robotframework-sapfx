> **🇬🇧 English** · [🇫🇷 Français](sap-test-data.fr.md)

# SAP test data & test targets

Curated, verified inventory (web check: 2026-07-06) of the SAP data sets and public
test targets this project can rely on — and the ones it must **not**. Complements
[testing-without-sap.md](testing-without-sap.md) (how to get a system) by answering
*what to test against once you have one*.

## 1. Demo data inside the ABAP Platform Trial (A4H 1909)

The trial has **no ERP business transactions** (FB01, MM03, VA01… are absent by
design — [official FAQ](https://github.com/SAP-docs/abap-platform-trial-image/blob/main/faq-v7.md)).
It does ship three demo data models, all usable as stable smoke-test targets:

| Model | Tables | Generate / reset |
|-------|--------|------------------|
| **Flight Reference Scenario (RAP)** | `/DMO/*` | Pre-generated in the trial; regen via class `/DMO/CL_FLIGHT_DATA_GENERATOR` (SE24 / ADT console) |
| **Classic SFLIGHT** | `SPFLI`, `SFLIGHT`, `SBOOK`, `SCARR`… | SE38 → report `SAPBC_DATA_GENERATOR` (deletes then regenerates, size selectable) |
| **EPM (Enterprise Procurement Model)** | `SNWD_*` (e.g. `SNWD_PO`) | Transaction `SEPM_DG` (report `SEPM_DG_EPM_STD_CHANNEL`) |

Safe transactions for smokes: `SE16`, `SE38`/`SA38`, `SE80`, `SE11`, `SE24`,
`SM50`, `SU01`, `SLICENSE`. Recommended pattern: a suite-setup keyword that runs the
data generator, then `SE16` reads on `SFLIGHT`/`SNWD_PO` — guaranteed-non-empty grids.

**Validated live on A4H (2026-07)** — implemented in
`resources/a4h_demo_data.resource` + `tests/robot/ecc_data_smoke.robot` (4/4):

- **`SE16N` does not exist on A4H** ("Transaction SE16N does not exist").
- **SE16's default output is the classic ABAP list** (no scriptable grid object).
  Switch the user's output mode once — Settings → User Parameters → *ALV Grid
  Display* (`Use ALV Grid In Data Browser` keyword) — and
  `wnd[0]/usr/cntlGRID1/shellcont/shell` appears.
- Assert on **technical column ids** (`CARRID`, `PO_ID`) via `Get Grid Column Ids`,
  never on displayed titles (locale-dependent).

**The A4H embedded Gateway is alive too** (verified live 2026-07-13): the
OData catalog answers on the container's HTTP port —
`http://vhcala4hci:50000/sap/opu/odata/iwfnd/CATALOGSERVICE;v=2/ServiceCollection`
(basic auth DEVELOPER, `sap-client=001`) — with the **EPM reference services
already activated**: `SEPMRA_SHOP`, `SEPMRA_PROD_MAN`, `SEPMRA_SO_MAN`,
`SEPMRA_PO_MAN`… `SEPMRA_SHOP/Products/$count` returns the `SNWD_PD` row count
(205 with standard `SEPM_DG` data). This makes A4H a **GUI + API** target on
one system — the basis of `tests/robot/flagship_cross_paradigm.robot` (SE16
count == OData `$count`, live-validated) via `SapApiLibrary`.

## 2. Public Fiori / UI5 test targets

- **OpenUI5 Demo Kit — alive** (our current smoke target): <https://sdk.openui5.org/>;
  the Shopping Cart sample responds at
  `test-resources/sap/m/demokit/cart/webapp/index.html` (also on <https://ui5.sap.com/>;
  note `sapui5.hana.ondemand.com` now 301-redirects there).
- **SAP Gateway Demo ES5 (`sapes5.sapdevcenter.com`) — DEAD.** Decommissioned end of
  October 2025 ([SAP announcement](https://community.sap.com/t5/technology-blog-posts-by-sap/sap-gateway-demo-system-will-be-de-commissioned/ba-p/13353480)).
  Do not build anything on ES5 / `GWSAMPLE_BASIC`.
- **Public OData for fixtures**: Northwind V4 / TripPin at
  <https://services.odata.org/> (verified alive) — read-only feeds for local UI5
  fixtures; UI5's built-in `MockServer` (`sap.ui.core.util.MockServer`) simulates an
  OData V2 service from `metadata.xml` + JSON, deterministic and offline.

## 3. Local Fiori Elements target: cap-sflight

[SAP-samples/cap-sflight](https://github.com/SAP-samples/cap-sflight) (actively
maintained) ships two real **Fiori Elements** apps (Travel processor, Analytical
List Page) on a CAP backend — the best way to exercise `SapFioriLibrary` against
FE tables/filters/object pages with **no SAP backend and no network**:

```bash
npm i -g @sap/cds-dk
git clone https://github.com/SAP-samples/cap-sflight && cd cap-sflight
npm ci && cds watch          # → http://localhost:4004/
```

The OData **v4** service of the same process (`/processor/Travel`,
`$count`-capable) pairs with the UI for Fiori↔API cross-checks (the
`capsflight` leg of the flagship suite). **Known wedge (observed 2026-07-13)**:
with `@sap/cds-dk` 9.9 + `cds-plugin-ui5` 0.17 the local clone hangs at the
UI5 app mount on startup, and without the plugin the CAP server accepts TCP
but never answers — refresh the clone (`git pull && npm ci`) before relying on
it; `fiori_sflight_smoke.robot` is equally affected until then.

## 4. Platform watch (as of 2026-07)

- **A4H 1909 image is irreplaceable right now** — `sapse/abap-cloud-developer-trial`
  is gone from Docker Hub (2023 trial withdrawn; a 2025 trial is announced but not
  yet published). **Back up the local image** (`docker save`) and keep renewing the
  3-month minisap license via <https://go.support.sap.com/minisap/#/minisap>
  (import in `SLICENSE`). Details in [ecc-validation.md](ecc-validation.md).
- **SAP GUI for Windows 8.10** ships 2026-07-16: scripting **COM API unchanged**
  (only adds JScript as a recording language), so `SapEccLibrary` should migrate
  risk-free; re-run `ecc_smoke.robot` after upgrading. SAP GUI 8.00 restricted
  support ends 2027-07-31. API reference: [SAP GUI Scripting API on the Help Portal](https://help.sap.com/docs/r/b47d018c3b9b45e897faf66a6c0885a8/latest/en-US).
- **Ecosystem**: upstream `robotframework-sapguilibrary` is dormant (last release
  2022 — our vendored fork is the de-facto maintenance line);
  [playwright-sap](https://github.com/ArpitSureka/playwright-sap) is maintained
  (v1.1.4, 2025-10) — periodically re-diff our `_ui5_js.py` port against it;
  [rf-mcp](https://pypi.org/project/rf-mcp/) latest is 0.35.0 (there is no
  0.32/0.33 series) — our integration is re-validated against it (plugin
  contracts unchanged since 0.31.2; overlay guard window 0.31–0.35 in
  `sap_robotmcp/_compat.py`); watch future series for plugin-contract changes.

## 5. Library compatibility across SAP versions (validated 2026-07)

| Target | Status |
|--------|--------|
| ECC 6.0 / R/3 (SAP GUI 7.x/8.x) | ✅ Same client-side COM Scripting API (stable since ~6.20/2002); needs `sapgui/user_scripting=TRUE`. Caveat: the by-title grid layer covers ALV **GridView** only — classic `GuiTableControl` screens fall back to upstream keywords. Not physically tested on ECC 6.0. |
| S/4HANA on-prem GUI | ✅ Proven live (A4H 1909, `ecc_smoke` + `ecc_data_smoke`). |
| SAP GUI for Windows 8.10 (2026-07-16) | ✅ COM API unchanged — risk-free migration expected. |
| UI5 ≥ 1.67 + Fiori Elements v4 | ✅ Proven live (OpenUI5 Demo Kit, cap-sflight). |
| UI5 < 1.67 (pre-2019 launchpads: S/4 1610/1709, UI5 1.44/1.52/1.60) | ✅ `registryForEach` DOM fallback — **proven live vs real OpenUI5 1.60.14** (`fiori_legacy_smoke.robot`, jsDelivr npm mirror). |
| UI5 2.x (**cancelled** — UI5con keynote, July 2026: no 2.0 release planned; SAP's official path is the legacy-free 1.x line) | ✅ **Proven live vs the 2.0 nightly CDN** (`fiori_ui5v2_smoke.robot`, `sdk.openui5.org/nightly/2`): `ElementRegistry` module branch, zero dependency on the APIs removed in 2.x (`sap.ui.getCore()`, `Element.registry`, `sap.ui.version`). Also locked by `tests/unit/test_ui5_compat.py`. The smoke stays a **non-blocking sentinel** for as long as the nightly/2 CDN is served (it may be frozen or withdrawn); the 1.136-legacy-free smoke below is the forward-looking target. |
| Launchpad iframes (SAP Build Work Zone / cFLP) | ✅ `Set Ui5 Frame` — bundle evaluated inside the frame, `>>>` frame-piercing selectors; proven vs a genuinely cross-origin fixture (`fiori_frame_smoke.robot`). |
| S/4HANA Cloud (public edition) | ✅ Fiori + WebGUI `sid` engine (no desktop SAP GUI there); note the IAS/SAML login page is **not** UI5 → drive it with plain Browser keywords. |
