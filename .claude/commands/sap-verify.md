---
description: Independent read-only review of SAP tests and recorded evidence
argument-hint: <spec, handoff, original/final artifacts and replay evidence>
---

Use `sap-verifier` to review $ARGUMENTS against the original business invariant.
Read `.claude/agent-contract.md`. Verify release/client and channel population
from evidence. Do not open a live session, repair, execute tests or write files.
Missing proof produces `not_verified`. Return findings and a separate verifier
verdict in the conversation.