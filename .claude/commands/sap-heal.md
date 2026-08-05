---
description: >-
  Réparer un test SAP en échec : diagnostic, vérification live via rf-mcp,
  patch de la couche resources (agent sap-healer)
---

Use the **sap-healer** agent to repair the failing SAP test(s): $ARGUMENTS

If the arguments do not identify the failure, ask the user (in French) for the
failing suite/test name (or the `robot` output / `output.xml` path), plus the
connection variables needed to reproduce; never invent credentials. Remind the
user that `SAPFX_HEALING_LOG=<path>` (optional) gives the agent the cumulative
healing telemetry to spot recurring drifters.

Then launch the agent, wait for its result, and relay its French report (root
causes, each repair as before → after with its live evidence, final robot run
status, tests skipped with reasons) to the user.
