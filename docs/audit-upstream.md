> **🇬🇧 English** · [🇫🇷 Français](audit-upstream.fr.md)

# Audit — `robotframework-sapguilibrary` (upstream)

Reviewed commit: tip of `master` (release **v1.2.1**, March 2022). License **Apache 2.0**.
Source audited: `SapGuiLibrary/SapGuiLibrary.py` (single ~780-line module, one class).

## Verdict

A solid, focused base worth forking rather than rewriting. The COM plumbing and a
coherent keyword vocabulary are already there and battle-tested. The gaps are
narrow and well-defined — exactly the things we add in `SapEccLibrary`.

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

> Correction to an earlier assumption: grid/ALV is **not** missing here. Our fork's
> grid work is *ergonomics on top* (address columns by title), not filling a hole.

## Gaps we address in the fork

| # | Gap | Evidence in source | Our fix |
|---|-----|--------------------|---------|
| 1 | **No real synchronisation.** Only a fixed `time.sleep(self.explicit_wait)` after each keyword. No `session.Busy` polling, no "wait until present". | `explicit_wait` set by `set_explicit_wait`; every keyword ends in `time.sleep`. | `keywords/_waits.py`: `Wait Until Busy Done`, `Wait Until Element Present`, `Wait Until Element Value Is`. |
| 2 | **Locale-fragile transaction check.** Unknown-tcode detection string-matches the status bar in **Dutch/English/German only**. | `run_transaction` compares against `"Transactie %s bestaat niet"`, `"Transaction %s does not exist"`, `"Transaktion %s existiert nicht"`. | Override reads `sbar.messageType == "E"` (locale-independent). |
| 3 | **No connection bootstrap.** Assumes the Logon Pad is already running; docs tell you to start it with AutoIt/Process library. | `connect_to_session` raises "is Sap Logon Pad open?" if not. | `keywords/_connection.py`: `Open Sap Logon` (launch exe + wait for engine), `Close Sap Logon`, `Connect To Session With Retry`. |
| 4 | **Grid addressed only by technical column id.** You must know `"MATNR"` etc. (found via the external Scripting Tracker). | `get_cell_value(table_id, row, col_id)` takes a raw `col_id`. | `keywords/_grid.py`: resolve columns by visible title, `Read Grid` → list of dicts. |
| 5 | **No status-message helpers.** | — | `Get Status Message`, `Status Message Should Be Success`. |

## Minor observations (not fixed, noted for later)

- `__version__ = '1.2'` in code vs. release tag `1.2.1`.
- Relies on `robot.libraries.Screenshot` (works, but the standalone
  ScreenCapLibrary is the more modern choice).
- Several keywords call `findById` multiple times for one element (e.g.
  `element_value_should_be` → `get_element_type` + `get_value` + `findById`);
  harmless but chatty over COM.
- `select_node`'s `expand=True` swallows all `com_error`s (a `# TODO` is left in
  Dutch). Acceptable.
- Python 2.7 classifiers in `setup.py` — dropped in our `pyproject.toml`.

## Re-sync strategy

The upstream file is vendored verbatim at
`src/SapEccLibrary/_vendor/sapgui_base.py` with a **single** change (class rename
`SapGuiLibrary` → `SapGuiBase`). To pull a future upstream release: re-copy the
file, re-apply that rename, and re-run `tests/unit` + the libdoc diff. Keeping the
modification to one line is deliberate so this stays a 5-minute operation.
