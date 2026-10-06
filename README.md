> **🇬🇧 English** · [🇫🇷 Français](README.fr.md)

<p align="center">
  <img src="https://raw.githubusercontent.com/CyrilM29/robotframework-sapfx/main/assets/logo-library.png" alt="SAPFX: ECC UI5 API Library" width="240">
</p>

# SAPFX: Robot Framework libraries for testing SAP

[![PyPI](https://img.shields.io/pypi/v/robotframework-sapfx)](https://pypi.org/project/robotframework-sapfx/)
[![Python](https://img.shields.io/pypi/pyversions/robotframework-sapfx)](https://pypi.org/project/robotframework-sapfx/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](https://github.com/CyrilM29/robotframework-sapfx/blob/main/LICENSE)

```bash
pip install robotframework-sapfx
```

SAPFX automates SAP tests in Robot Framework through **three libraries, one per
channel**: the SAP GUI desktop client, SAP Fiori and SAPUI5 apps in the browser,
and the OData/RFC API channel. Each keeps the locators of its technology (a SAP
GUI scripting id, a UI5 control selector, an OData entity set); what they share
is **the same contracts and the same method**: one completeness rule for
extracting a table, whether it comes from an ALV grid, a UI5 table or an RFC
call; one message identity (`MO/E/402`) on the screen and over RFC; and, on the
two screen channels, the same perception → action loop and one locator-repair
log. The business vocabulary is built above, in your project's Robot Framework
keywords: that is where a test stops depending on the channel. One run can
cross all three (prepare data through the API, drive
the screen for what you actually test, check the result through another
channel). Because they also write, delete and cross-check their own writes
through two channels, the same libraries are heading beyond testing, towards
test data, populated databases and controlled loads (see
"Beyond testing" below for what is proven and what is not yet).

This repository publishes the **library sources**, their **documentation** and
the **keyword reference**. The libraries are distributed on PyPI as
`robotframework-sapfx`.

| Library | Channel | Driven through |
| --- | --- | --- |
| **`SapEccLibrary`** | SAP GUI for Windows (ECC, S/4HANA backend) | SAP GUI Scripting API over COM (`pywin32`). A hardened fork of [robotframework-sapguilibrary](https://github.com/frankvanderkuur/robotframework-sapguilibrary): every upstream keyword keeps its name and signature, a few now fail loudly where upstream returned a misleading value. |
| **`SapFioriLibrary`** | SAP Fiori / SAPUI5, UI5 Web Components, SAP GUI for HTML | The [Browser library](https://github.com/MarketSquare/robotframework-browser) (Playwright), with **UI5-stable control selectors** instead of generated DOM ids. Locator engine ported from [playwright-sap](https://github.com/ArpitSureka/playwright-sap). |
| **`SapApiLibrary`** | OData v2 and v4, RFC / BAPI | Python standard library for HTTP (SAP CSRF protocol included); optional RFC through `pyrfc`. |

A fourth package, `sapfx_common`, holds the pure logic the three share
(polling, healing scores, perception diff, human-locator engine, table
extraction contract, visual hashing...). Some of its modules are Robot
libraries in their own right, documented in their docstrings rather than in
the keyword reference: `Library    sapfx_common.table_csv` (also `table_json`,
`table_xlsx`, `table_svg`, `table_parquet`) writes an extraction and reads it
back, `sapfx_common.table_extract` carries the shared
`Table Extract Should Be Complete` guard, `sapfx_common.artifacts` writes and
re-reads deterministic JSON artifacts, and `sapfx_common.rap_preview` builds
the Fiori Elements preview path of a RAP service.

📖 **[Keyword documentation](https://cyrilm29.github.io/robotframework-sapfx/)**:
one reference page per library, every keyword with its arguments and examples.

## Install

```bash
pip install robotframework-sapfx            # the three libraries
pip install "robotframework-sapfx[web]"     # + Browser library, for SapFioriLibrary
rfbrowser init                              # one-time: Playwright browsers
```

Other extras: `visual` (Pillow, for screen baselines) and `parquet` (pyarrow,
for Parquet exports). Requirements per channel:

- **All**: Python 3.10 or later, Robot Framework 7.4 or later.
- **`SapEccLibrary`**: Windows, SAP GUI for Windows, and scripting enabled on
  the server (RZ11 `sapgui/user_scripting`) and on the client.
  `Scripting Should Be Fully Enabled` checks both and names the parameter to
  fix. Pin `pywin32` exactly in your environment file: it is the first source
  of COM breakage.
- **`SapFioriLibrary`**: the `web` extra and `rfbrowser init`. No SAP system is
  needed to try it: the public OpenUI5 Demo Kit is a valid target.
- **RFC in `SapApiLibrary`** (optional): `pyrfc`, pinned
  (`pip install pyrfc==3.3.1`: SAP archived the project and every PyPI release
  is yanked, so pip no longer picks one by itself; prebuilt wheels up to
  Python 3.12 only), and the SAP NW RFC runtime, which a SAP GUI for
  Windows 8.00 installation usually provides already (component "SAP NWRFC
  x64 Shared"). Without it, the RFC keywords say so and the rest of the
  library works.

A free local SAP system to test against (ABAP Platform Trial in Docker), and
the SAP-side prerequisites, are described in
[docs/testing-without-sap.md](docs/testing-without-sap.md).

## Quick start

**SAP GUI** (credentials on the command line:
`robot -v "PASSWORD: Secret:..." suite.robot`; the Robot Framework 7.4 typed
variable keeps the password out of the logs, even at TRACE level):

```robotframework
*** Settings ***
Library    SapEccLibrary

*** Variables ***
${CONNECTION}    MY SYSTEM
${USER}          DEVELOPER
${PASSWORD}      ${EMPTY}
${GRID}          wnd[0]/usr/cntlGRID1/shellcont/shell

*** Test Cases ***
Read The Clients Table In SE16
    Open Sap Logon
    Connect To Session With Retry
    Open Connection    ${CONNECTION}
    Input Text        wnd[0]/usr/txtRSYST-BNAME    ${USER}
    Input Password    wnd[0]/usr/pwdRSYST-BCODE    ${PASSWORD}
    Send Vkey    0
    Scripting Should Be Fully Enabled
    Use ALV Grid In Data Browser
    Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000
    Send Vkey    0
    Send Vkey    8
    ${rows}=    Read Full Grid    ${GRID}
    Log    ${rows}
```

In a real project, the SAP element ids live in a resource file of business
keywords, and the test cases speak business language only.

**SAP Fiori / SAPUI5** (runs as is against the public OpenUI5 Demo Kit):

```robotframework
*** Settings ***
Library    Browser
Library    SapFioriLibrary    ui5_timeout=20s

*** Test Cases ***
Search The API Reference
    New Browser    chromium    headless=True
    New Page       https://sdk.openui5.org/#/api
    Fill Ui5 Input    Button    controlType=SearchField
    ${xpath}=    Get Ui5 Xpath    controlType=SearchField
    Log    ${xpath}
    [Teardown]    Close Browser
```

**OData** (a SAP Gateway service, here the EPM demo shop of the ABAP trial):

```robotframework
*** Settings ***
Library    SapApiLibrary

*** Variables ***
${PASSWORD}    ${EMPTY}

*** Test Cases ***
Count The Products
    Open Api Session    http://localhost:50000    user=DEVELOPER
    ...                 password=${PASSWORD}    sap_client=001
    ${count}=    Get Odata Count    /sap/opu/odata/sap/SEPMRA_SHOP/Products
    Should Be True    ${count} > 0
    ${first}=    Get Odata Entities    /sap/opu/odata/sap/SEPMRA_SHOP/Products    top=3
    Length Should Be    ${first}    3
    [Teardown]    Close All Api Sessions
```

## What the libraries bring

- **Real synchronisation**, never fixed sleeps: `Wait Until Busy Done`,
  `Wait Until Element Present` (SAP GUI), `Wait For Ui5 Idle` (network,
  busy indicators and a continuous quiet period, on UI5 and non-UI5 pages).
- **Locale-independent assertions**: `Run Transaction` judges the status-bar
  message **type**, never its translated text; `Get Status Message Identity`
  reads class, type and number; `Ui5 Should Have No Messages Of Type` does the
  same on the web. Dates and numbers are typed in the user's own format
  (`Input Date`, `Input Number`, `Fill Ui5 Date`), and a screen's display or
  change mode is read from a field (`Element Should Be Changeable`), never from
  its translated title.
- **Tables read as data**: ALV grids by column title (`Read Grid`,
  `Read Full Grid`, `Get Grid Column Titles`), table controls, trees, classic
  ABAP lists, UI5 tables and SAP GUI for HTML grids; one extraction contract for
  all channels, which refuses a partial reading instead of passing it for a
  complete one, and five export formats (CSV, JSON Lines, XLSX, SVG, Parquet).
- **Human locators** (SAP GUI): `Fill Field By Label`, `Click Button By Label`,
  `Read Field By Label`, by visible label and geometry; an ambiguity is always
  reported with its candidates, never resolved by a silent first match.
- **Five resolution engines on the web**: UI5 `role` and hierarchical `xpath`
  (`//Table//Button[@text='Edit']`), `sid` for SAP GUI for HTML, `wc` for UI5
  Web Components pages without a classic runtime, and `dom` (ARIA role and
  accessible name) for the non-SAP parts of hybrid pages; nested iframes of
  launchpads through a frame stack; `Get Page Composition` says which
  technology lives where.
- **Locator healing, never silent**: failures list the closest ids on screen,
  scored; `Resolve Element With Healing` and `Resolve Ui5 With Fallback` repair
  a stale locator with a logged warning and an optional telemetry journal.
- **Screen perception** for debugging and AI agents: `Get Screen Signature`,
  `Get Screen Map` (numbered actionable targets), `Get Ui5 Page Tree`, diff
  mode, annotated screenshots.
- **Visual assertions** where the Scripting API sees nothing (opaque shells,
  charts): perceptual-hash baselines per screen, per element or per tile.
- **Preflights** that name their remedy: scripting on server and client,
  workstation security posture, Gateway activation, RFC channel availability;
  and the ABAP server's security configuration read over RFC (profile
  parameters judged on their return code, drift against a committed
  reference).
- **The API channel as a data platform**: full OData CRUD with CSRF, `$batch`,
  server-driven paging, `$metadata` perception with human labels, a test-data
  factory that cleans up after itself, BAPIs judged by message type and
  refusals asserted by message identifier, RFC table reads, background jobs
  and their spool, outbound IDocs (create, wait on the status code, link to
  the inbound IDoc by its TID), change documents.
- **Several SAP GUI sessions** by alias in one suite, SAP Fiori launchpad
  navigation by intent and login through an identity provider, tile counters
  read as numbers (`Get Flp Tile Counter`), and identity readings (release,
  kernel, client; over HTTP alone with `Get Abap Software Components`) that
  prove which system a test is really talking to.

Teams that test UI5 apps with JavaScript tooling will know
[wdi5](https://github.com/ui5-community/wdi5), the reference outside Robot
Framework. SAPFX does not replace it: its scope is SAP test automation in Robot
Framework, where the desktop client, the API channel and Fiori share one
runner, one report and the same contracts.

## Beyond testing

The libraries were built to test SAP, and that stays their core. What makes a
test trustworthy (write a record through one channel, read it back through
another, independent one, delete it, and confirm it is gone) also works outside
a test. Three uses follow from it:

- **Test data sets**: creating complete, consistent data sets, identifiable as
  test data, to feed test campaigns.
- **Populating databases for performance testing**: filling empty or incomplete
  SAP databases before a load campaign.
- **Configuration and migration loads**: loading complex business data into a
  target environment, and cross-checking the load through a second channel, for
  instance in an ECC to S/4HANA migration.

To be precise about where this stands: writing, deleting and cross-checking
through two channels are validated live on SAP development systems, never on a
customer system. The three uses themselves are a direction, not delivered
features. There is no data-set generator in the libraries yet, no volume or load
time has been measured, and no migration has been run. The angle for migrations
is scripted loading plus cross-checking, not replacing SAP's own load and
migration tools.

## Documentation

| Document | Topic |
| --- | --- |
| [Keyword reference](https://cyrilm29.github.io/robotframework-sapfx/) | Every keyword of the three libraries |
| [docs/architecture.md](docs/architecture.md) | How the libraries are built and how they fit together |
| [docs/fiori-architecture.md](docs/fiori-architecture.md) | The web side: UI5 selectors, engines, frames, hybrid pages |
| [docs/testing-without-sap.md](docs/testing-without-sap.md) | A free local SAP system, SAP-side prerequisites |
| [docs/sap-test-data.md](docs/sap-test-data.md) | Test data and targets available without a customer system |
| [docs/ecc-validation.md](docs/ecc-validation.md) | Validation against a live ABAP system, step by step |
| [docs/hardening-test-environment.md](docs/hardening-test-environment.md) | Security checklist for the server, the workstation and the web side |
| [docs/migrating-from-sapguilibrary.md](docs/migrating-from-sapguilibrary.md) | Moving from robotframework-sapguilibrary |
| [docs/migrating-from-cbta.md](docs/migrating-from-cbta.md) | Moving from SAP CBTA |
| [docs/audit-upstream.md](docs/audit-upstream.md) | What the fork changes in the upstream library, and why |

Every document exists in English and in French (`*.fr.md`). They were written
alongside the libraries in the maintainer's workbench: when they mention a
business resource layer (`resources/`), Robot suites (`tests/robot/`),
recorders or test agents, they describe that workbench, which is not part of
this repository.

## Layout

```text
src/SapEccLibrary/      SAP GUI for Windows (COM); _vendor/ holds the upstream
                        library verbatim, keywords/ one mixin per capability
src/SapFioriLibrary/    Fiori / UI5 / Web Components / SAP GUI for HTML
                        (Browser library); injected JavaScript in *.js.tpl
src/SapApiLibrary/      OData v2/v4 and optional RFC / BAPI
src/sapfx_common/       shared pure logic
docs/                   library documentation (EN/FR), docs/libdoc/ = keyword pages
```

## Issues

Bug reports and suggestions are welcome as
[GitHub issues](https://github.com/CyrilM29/robotframework-sapfx/issues).

## License

Apache 2.0. Includes vendored code from robotframework-sapguilibrary, locator
engines ported from playwright-sap and techniques adapted from RoboSAPiens and
playwright-praman; see [LICENSE](LICENSE) and [NOTICE](NOTICE).

## Trademarks

SAP, SAP ECC, SAP S/4HANA, SAP Fiori, SAP BTP, SAP HANA, SAP NetWeaver, SAP
GUI, SAPUI5, ABAP and the other SAP products and services mentioned are
trademarks or registered trademarks of SAP SE or its affiliates in Germany and
in other countries. SAPFX is an independent open-source project, not affiliated
with, sponsored or endorsed by SAP SE.
