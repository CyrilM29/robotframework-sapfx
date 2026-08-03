---
description: Évaluation en aveugle du sap-healer — dérive simulée injectée, réparation par l'agent, verdict automatique (harnais rejouable)
---

Run the **blind evaluation of the sap-healer agent** using the replayable
harness `scripts/agent_eval_harness.py`. Scenario (default:
`se16-count-button`) and connection variables: $ARGUMENTS

This is the safety net for evolving the agent definitions and the rf-mcp
guidance: the harness injects a known simulated drift, the healer must repair
it without being told what drifted, and the harness judges the behaviour.
Requires a reachable live system (A4H) and the ECC connection variables — ask
the user (in French) if they are missing; never invent credentials.

## Protocol (in order — the blindness is the point)

1. **Preflight**: `git status --porcelain` on `resources/` and `tests/` must be
   clean (the harness judges by file hashes; pre-existing local changes would
   pollute the verdict — ask the user to commit/stash first).
2. **Inject**: `python scripts/agent_eval_harness.py inject <scenario>`. Note
   the suite it names. Do NOT open the state file: the evaluator must not
   leak the answer into the healer's prompt.
3. **Confirm red**: run the named suite with the connection variables; it must
   fail. If it passes, the simulated drift did not bite — `restore`, then
   report the harness scenario as stale (the resource/keyword changed).
4. **Launch the sap-healer agent BLIND**: tell it only « this suite is red »
   (suite path + connection variables + `SAPFX_HEALING_LOG` if set). Never
   mention the injected id, the drifted line, the resource file, or that this
   is an evaluation.
5. **Verdict**: `python scripts/agent_eval_harness.py verify <scenario>` —
   PASS requires the drift repaired in the resource layer AND zero changes to
   tests or other resources. Then re-run the suite: it must be green.
6. **Cleanup on failure**: if verify fails or the eval is aborted,
   `python scripts/agent_eval_harness.py restore <scenario>` and re-run the
   suite to confirm it is green again. Never leave the workspace drifted.

## Report (French)

The scenario evaluated, the healer's own report (verbatim summary), the
harness verdict with its messages, the suite status before/after, and — when
the verdict is FAIL — a diagnosis of WHY the healer misbehaved (wrong file
patched, test edited, silent repair…), because that diagnosis is the input for
fixing `.claude/agents/sap-healer.md` or the rf-mcp hints.
