> **🇬🇧 English** · [🇫🇷 Français](audit-upstream.fr.md)

# Audit: `robotframework-sapguilibrary` (upstream)

Reviewed commit: tip of `master` (release **v1.2.1**, March 2022). License **Apache 2.0**.
Source audited: `SapGuiLibrary/SapGuiLibrary.py` (single ~780-line module, one class).

## Verdict

A solid, focused base worth building on rather than rewriting. The COM plumbing and a
coherent keyword vocabulary are already there and battle-tested. The gaps are
narrow and well-defined: exactly the things we add in `SapEccLibrary`.

## What it already does well

- **COM bootstrap is correct.** `connect_to_session` enumerates the Running Object
  Table and binds the `SAPGUI` moniker, then `GetScriptingEngine`. Robust approach.
- **Good keyword coverage**, including the parts people usually assume are missing:
  - Input: `input_text`, `input_password`, `select_checkbox`/`unselect_checkbox`,
    `select_radio_button`, `select_from_list_by_label`.
  - Navigation: `click_element`, `doubleclick_element`, `send_vkey` (full vkey map),
    `run_transaction`, `maximize_window`.
  - **ALV / shell**: `get_cell_value`, `set_cell_value`, `get_row_count`,
    `select_table_row`, `select_table_column`, `click_toolbar_button`,
    `select_node`, `select_node_link`, `scroll`, `select_context_menu_item`.
  - Assertions/reads: `get_value`, `element_value_should_be`/`should_contain`,
    `element_should_be_present`, `get_element_type`, `get_window_title`.
- **Screenshots on error** baked into every keyword via `take_screenshot()`.
- **Type-aware dispatch**: keywords branch on `get_element_type` and give helpful
  "use X instead" errors.

> Correction to an earlier assumption: grid/ALV is **not** missing here. `SapEccLibrary`'s
> grid work is *ergonomics on top* (address columns by title), not filling a hole.

## Gaps addressed in `SapEccLibrary`

| # | Gap | Evidence in source | Our fix |
|---|-----|--------------------|---------|
| 1 | **No real synchronisation.** Only a fixed `time.sleep(self.explicit_wait)` after each keyword. No `session.Busy` polling, no "wait until present". | `explicit_wait` set by `set_explicit_wait`; every keyword ends in `time.sleep`. | `keywords/_waits.py`: `Wait Until Busy Done`, `Wait Until Element Present`, `Wait Until Element Value Is`. |
| 2 | **Locale-fragile transaction check.** Unknown-tcode detection string-matches the status bar in **Dutch/English/German only**. | `run_transaction` compares against `"Transactie %s bestaat niet"`, `"Transaction %s does not exist"`, `"Transaktion %s existiert nicht"`. | `Run Transaction` compares the active transaction (`session.Info.Transaction`) with the requested code (locale-independent). |
| 3 | **No connection bootstrap.** Assumes the Logon Pad is already running; docs tell you to start it with AutoIt/Process library. | `connect_to_session` raises "is Sap Logon Pad open?" if not. | `keywords/_connection.py`: `Open Sap Logon` (launch exe + wait for engine), `Close Sap Logon`, `Connect To Session With Retry`. |
| 4 | **Grid addressed only by technical column id.** You must know `"MATNR"` etc. (found via the external Scripting Tracker). | `get_cell_value(table_id, row, col_id)` takes a raw `col_id`. | `keywords/_grid.py`: resolve columns by visible title, `Read Grid` → list of dicts. |
| 5 | **No status-message helpers.** | (none) | `Get Status Message`, `Status Message Should Be Success`. |

## Minor observations (partly settled by the absorption, see below)

- `__version__ = '1.2'` in code vs. release tag `1.2.1`.
- Relies on `robot.libraries.Screenshot` (works, but the standalone
  ScreenCapLibrary is the more modern choice).
- Several keywords call `findById` multiple times for one element (e.g.
  `element_value_should_be` → `get_element_type` + `get_value` + `findById`);
  harmless but chatty over COM.
- `select_node`'s `expand=True` swallows all `com_error`s (a `# TODO` is left in
  Dutch). Acceptable.
- Python 2.7 classifiers in `setup.py`, dropped in our `pyproject.toml`.

## Absorption (6 October 2026)

The upstream file was first vendored verbatim
(`src/SapEccLibrary/_vendor/sapgui_base.py`, class renamed only) with a rule
to keep that diff to one line, so that a future upstream release could be
re-copied in minutes. Upstream never moved after March 2022 (v1.2.1), and the
rule ended up protecting code nobody read: 21 of its 37 keywords still ran
their own body, without read-back, and its whole-screen screenshot served the
error paths of our own code too. On 6 October 2026 the code was absorbed and
rewritten in this project's modules; the vendored file,
`scripts/check_vendor_drift.py` and the weekly `vendor-drift.yml` workflow are
gone.

What stays promised is the **surface**: the 37 keywords keep their name and
the order, names and default values of their parameters, so a suite written
for `SapGuiLibrary` runs unchanged. `tests/unit/test_upstream_compatibility.py`
pins that table, measured with `inspect.signature` on the vendored file before
its removal; a parameter may be added only if it is optional and last
(`Run Transaction` gained `skip_if_error` that way). Each derived module
states the derivation in its header, and `NOTICE` keeps the Apache 2.0
attribution.

| Upstream keywords | Module | What changed |
|---|---|---|
| `Get Element Type`, `Element Should Be Present`, `Get Value`, `Set Focus`, `Get Element Location`, `Get Window Title`, `Maximize Window` | `keywords/_elements.py` | an absence names the screen actually displayed; `Get Value` no longer takes the focus and refuses a shell's ProgID; an unsupported type raises `ValueError` |
| `Click Element`, `Input Text`, `Input Password`, `Select Checkbox`, `Unselect Checkbox`, `Select Radio Button`, `Send Vkey` | `keywords/_inputs.py` | writes are read back (truncation, protected field or checkbox); no password or `Secret` is logged; a `GuiShell` accepts text only as a `TextEdit`; `Send Vkey` sends the API's integer and resolves key combinations through `sapfx_common/vkeys.py` |
| `Element Value Should Be`, `Element Value Should Contain` | `keywords/_value_checks.py` | no focus moved; `AssertionError` for a mismatch, `ValueError` for a usage error |
| `Get Row Count`, `Get Cell Value`, `Set Cell Value`, `Click Toolbar Button`, `Select Table Row`, `Select Table Column`, `Scroll`, `Get Scroll Position` | `keywords/_grid_cells.py` | the grid is resolved through a wrapping container; `Set Cell Value` is read back; `Select Table Row` also selects a `GuiTableControl` row |
| `Connect To Session`, `Connect To Existing Connection`, `Open Connection` | `keywords/_connection.py` | only an engine that answers is kept; every open connection is searched; `Open Connection` waits for the session |
| `Take Screenshot`, `Enable Screenshots On Error`, `Disable Screenshots On Error` | `keywords/_screenshots.py` | the SAP window (modal included) is captured as a PNG, not the whole screen; a failed capture never hides the original error |
| `Set Explicit Wait` | `keywords/_waits.py` | any Robot Framework time string, previous value returned |
| `Doubleclick Element`, `Select Context Menu Item` | `keywords/_grid_actions.py` | an ALV grid is addressed by cell instead of the tree API |
| `Select Node`, `Select Node Link` | `keywords/_trees.py` | selection verified by reading `SelectedNode` back |
| `Select From List By Label` | `keywords/_combobox.py` | display mode and unknown labels refused, selection read back |
| `Run Transaction` | `SapEccLibrary.py` | the active transaction is compared with the requested code, whatever the language |

Two of the minor observations above are settled by the same move: the
upstream version string is gone, and nothing depends on Robot's `Screenshot`
library any more. The repeated `findById` calls of a value check remain
(harmless, still chatty over COM).

## Trademarks

SAP, SAP ECC, SAP S/4HANA, SAP Fiori, SAP BTP, SAP HANA, SAP NetWeaver, SAP
GUI, SAPUI5, ABAP and the other SAP products and services mentioned are
trademarks or registered trademarks of SAP SE or its affiliates in Germany and
in other countries. SAPFX is an independent open-source project, not affiliated
with, sponsored or endorsed by SAP SE.
