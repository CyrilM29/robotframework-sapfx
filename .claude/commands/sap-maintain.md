---
description: Cycle de maintenance préventive — sentinelle de dérive + télémétrie de healing + réparations sap-healer, en un seul rapport
---

Run the **preventive maintenance cycle** of this SAP test workspace: chain the
three existing bricks (drift sentinel → healing telemetry → sap-healer) and
produce ONE aggregated French report. Arguments (connection variables, healing
log path, suite filter): $ARGUMENTS

If the ECC connection variables are missing (`SAP_CONNECTION`, `SAP_USER`,
`SAP_PASSWORD`), ask the user (in French) before starting; never invent
credentials. `SAPFX_HEALING_LOG` is optional — without it, step 2 is skipped
and the report says so.

## The cycle

1. **Drift sentinel** (detection without tests). Run
   `robot --pythonpath src -v SAP_CONNECTION:... -v SAP_USER:... -v
   "SAP_PASSWORD: Secret:..." --outputdir results/maintain
   tests/robot/ecc_drift_sentinel.robot` (in a deployed pack:
   `.venv\Scripts\robot.exe`, suites under the pack root). Read the aggregated
   Markdown drift report in the log. First visit of a screen = reference
   created (to commit) — say so, that is not a drift.
2. **Healing telemetry** (recurring drifters). If a healing journal exists:
   `python scripts/healing_drift_report.py --log <journal>`. **Stable** drifts
   (same locator healed to the same target run after run) come with a located
   `resources/` patch — apply them via `--apply` only after showing the user
   the proposed diff. **Unstable** drifts go to step 3.
3. **Repairs** (sap-healer). For each drifted screen from step 1 and each
   unstable drifter from step 2 — and for any suite the user reported red —
   launch the **sap-healer** agent (one failure at a time; a shared resource
   fix often clears the rest). House rules apply: patch `resources/` (or
   `resources/site_keywords.resource` in a deployed pack), never the tests,
   never silently.
4. **Aggregated report** (French): drifts detected (screen + what changed),
   telemetry insights (recurring drifters, applied patches), each repair as
   `before → after` + live evidence, suites re-run with real status, and what
   remains open (genuine functional changes to send back to sap-planner —
   `robot:skip` + stale spec, per the healer contract).

## Ground rules

- One live ECC session at a time; close every session you opened, **even on
  failure** (an orphaned connection shifts the attach indices — learned live
  2026-07-21).
- Never weaken an assertion or delete a step to get to green; never
  `time.sleep`. Locators live in `resources/`; assertions stay
  locale-independent (message type, technical column ids).
- Extending the watch = adding a tcode to `@{WATCHED_TRANSACTIONS}` in
  `tests/robot/ecc_drift_sentinel.robot` — no scenario to write.
- To make the cycle a scheduled assertion (CI/task scheduler), re-run step 1
  with `-v FAIL_ON_DRIFT:True`; the report should then mention the non-zero
  exit as the alerting signal.
