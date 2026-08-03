---
description: Explorer un système SAP live (via rf-mcp) et produire un plan de test dans specs/ (agent sap-planner)
---

Use the **sap-planner** agent to explore the target SAP system and produce a
test plan under `specs/` for: $ARGUMENTS

If the arguments do not say so, first ask the user (in French) for:
- the channel — ECC (transaction code) or Fiori (URL / app name);
- the business goal to cover;
- the connection (ECC connection string or SAP Logon entry + user, Fiori URL) —
  never invent credentials.

Then launch the agent, wait for its result, and relay its French report
(spec path, scenarios, observed data, missing business keywords) to the user.
