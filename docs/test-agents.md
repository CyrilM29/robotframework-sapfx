> **🇬🇧 English** · [🇫🇷 Français](test-agents.fr.md)

# SAP test agents (plan → generate → heal)

An agentic Robot Framework workflow for this ecosystem, transposing the
[Playwright Test Agents](https://playwright.dev/docs/test-agents) principle
(planner / generator / healer) to SAP: the agents drive the **live** system
through the [rf-mcp server and its SAP plugins](mcp-integration.md), speak the
business vocabulary of `resources/`, and honour the repo's conventions
(locators in the resources layer, no fixed waits, locale-independent
assertions).

## The four agents

| Agent | Input | Output |
|---|---|---|
| **sap-planner** | A business goal + a reachable system (ECC tcode or Fiori URL) | A Markdown test plan in `specs/`, grounded in live observations (perceive → act loop) |
| **sap-generator** | A plan from `specs/` | A runnable suite in `tests/robot/`, every step executed live through rf-mcp before being written; missing business keywords added to the resources layer |
| **sap-healer** | A failing suite/test | The failure reproduced, classified (locator drift / timing / data / functional change) and repaired **in the resources layer**, verified live, re-run to green, never silently |
| **sap-istqb** | Planner specs and/or recorder outputs (recordings, `.spec.md`/`.istqb.md` drafts) | An **ISTQB test plan + test cases** document under `specs/istqb/` (offline, artifacts only): ISO 29119-3 sections, one test case per scenario with an Action / Données / Résultat attendu table and a normalized `replay` YAML block, human-readable AND replayable by an AI with any test framework; what no source supports stays marked « à compléter » |

The planner also has a **coverage-discovery mode** for the question that comes
*before* any plan (« what should we test first? »): it reads the real usage of
the system through **ST03N**'s transaction profile (perceive → act, grid
keywords), ranks transactions by dialog steps × users, flags what the existing
suites already cover, and writes a roadmap to `specs/couverture-proposee.md`:
one entry per uncovered high-usage transaction, each then going through the
normal exploration loop. On a fresh trial without collector history it says so
honestly and falls back to asking for the critical-transaction list.

The canonical definitions live in `.claude/agents/sap-*.md`. Slash commands
`/sap-plan`, `/sap-generate`, `/sap-heal` and `/sap-istqb`
(`.claude/commands/`) wrap them for Claude Code.

Both recorders emit the same ISTQB template as a draft (`--export-istqb` on
the desktop, the « plan ISTQB » export-menu entry on the web): sap-istqb's
job is then to WRITE the judgment fields (objective, scope, priorities,
risks, traceability to specs and generated suites), never to degrade what was
observed. These documents are test-design documentation: they never replace
the executable suites, and the agent never edits `tests/robot/` or
`resources/`.

## The cycle

```text
/sap-plan     consultation of flight data via SE16 on A4H
   └─> specs/sflight-consultation-se16.md        (reviewed/amended by a human)
/sap-generate specs/sflight-consultation-se16.md
   └─> tests/robot/sflight-consultation-se16.robot   (dry run + live run reported)
/sap-heal     tests/robot/sflight-consultation-se16.robot
   └─> locator patched in resources/, suite green again (report before → after)
```

Key structural difference with Playwright's agents: thanks to convention #1,
the healer patches `resources/` (one line fixes every suite using that
locator), not the tests; test bodies only change when the business flow
itself changed, which is a planner/generator round, not a heal. The healer
also reads the cumulative healing telemetry (`SAPFX_HEALING_LOG`) to spot
locators that drift recurrently and deserve a definitive fix.

That telemetry loop is also automated without any agent:
`python scripts/healing_drift_report.py --log <journal>` aggregates the
JSONL, separates **stable** drifts (same locator healed repeatedly to one
target: the `resources/` patch is located and proposed; `--apply` executes
it) from **unstable** ones (left to a human or to sap-healer), and exits
non-zero when drifts exist, ready for a scheduled CI job that opens an
issue/PR. Same house rule as the healer: it patches `resources/` only, never
tests, never silently.

## The maintenance cycle (`/sap-maintain`)

The three maintenance bricks (drift sentinel, healing telemetry, sap-healer)
are chained by one orchestrating command, `/sap-maintain`
(`.claude/commands/sap-maintain.md`): run the sentinel
(`tests/robot/ecc_drift_sentinel.robot`), read its aggregated drift report,
apply the *stable* drift patches proposed by `healing_drift_report.py` (after
showing the diff), delegate every remaining drift or red suite to the
sap-healer agent one failure at a time, and produce ONE French report
(drifts → repairs `before → after` → what stays open). The cycle honours the
house rules (patch `resources/` only, never silently, close every session even
on failure) and becomes a scheduled assertion by re-running the sentinel with
`-v FAIL_ON_DRIFT:True`. A fully unattended CI variant would need the SAP
system reachable from the runner: on the A4H-in-Docker setup this is a local
scheduled task, not a GitHub-hosted job.

## Evaluating the agents themselves (`/sap-eval-healer`)

Changing an agent definition or the rf-mcp guidance without a regression net
is how agent behaviour silently rots. `scripts/agent_eval_harness.py` makes
the 0.3.0 blind exercise replayable: `inject` applies a known simulated drift
to the resources layer (byte-exact backup + hashes of the protected surface:
tests and the other resources), the sap-healer is then launched **blind**
(« this suite is red », nothing more), and `verify` judges the outcome: drift
repaired in the resource layer, zero changes to tests, state cleaned on PASS
(`restore` rolls back an aborted run). The `/sap-eval-healer` command drives
the full protocol, including the git-clean preflight and the red/green suite
runs around the heal. A FAIL verdict comes with the diagnosis to feed back
into `.claude/agents/sap-healer.md` or the hints: that is the point.

## Instructed tracks (investigated 2026-07-23, not yet built)

**MCP-native vision channel.** Verdict: the rf-mcp 0.31.2 plugin contract
(`LibraryStateProvider`) has **no image channel**: state providers return
JSON dicts, so a screenshot crosses MCP as base64 *text* the model cannot see.
The underlying stack could do it: rf-mcp runs on fastmcp (3.4.2 here), whose
tools can return real MCP image content (`fastmcp.utilities.types.Image`),
but that is an **upstream rf-mcp evolution** (a `get_screenshot` tool or an
image-capable provider hook), worth proposing, not something the plugins can
add from outside. Practicable **today** without any change: the agents run
inside Claude Code, whose `Read` tool renders PNG files, so `Take Screenshot`
(file) + `Read` gives the planner/healer real vision on opaque zones. The
missing piece for the full Set-of-Mark loop is a file-writing variant of
`Get Annotated Screenshot` (its dict returns the annotated PNG only as
base64); a small keyword (`path=` output) to add when the need is confirmed.

**Read-only session guard for the planner.** The planner's display-only
contract lives in its prompt only; a runtime `SAPFX_READONLY_SESSION=1`
(refusing save-type vkeys (11/Ctrl+S), delete context menus, `Post Odata`,
write RFCs) would be defence in depth, in the same spirit as
`SAPFX_STRICT_COM_THREAD`. Honest difficulty, which is why it is not built
yet: the read/write frontier is blurry, since filling a selection screen *is* a UI
write and must stay allowed, transaction semantics decide whether F8 mutates
anything, and a denylist that pretends to be a sandbox would be worse than
the documented contract. If built, it should be sold as « blocks the known
commit gestures », never as an authorization boundary: the SAP user's
permissions remain the real one (see the security notes in
[mcp-integration.md](mcp-integration.md)).

**Release confidence score (beyond the diagnosis sap-healer already does).**
Lead identified via competitive watch (2026-08-18, Testsigma: an agentic
pipeline that generates, runs, heals and diagnoses tests, then scores release
confidence). Diagnosis already exists in good part: sap-healer classifies
every failure (locator drift / timing / data / functional change) before
repairing it. What's missing sits elsewhere: an aggregated confidence
indicator at the release level (not the test level), built from the healing
history (`SAPFX_HEALING_LOG`), the drift telemetry
(`healing_drift_report.py`) and red/green suite results, to answer "can we
ship". Cyril calls it the "5th agent" (after planner, generator, healer,
istqb). Not instructed yet: no feasibility analysis, no decision between a
separate agent vs. extending `/sap-maintain` or the `healing_drift_report.py`
report, which already aggregates part of the raw material.

`specs/sflight-consultation-se16.md` is the reference plan example; it matches
the flow already live-validated by `tests/robot/ecc_data_smoke.robot`.

## One source, two IDE dialects

The same agents are available in both VS Code AI stacks:

- **Claude Code** (CLI or VS Code extension) reads `.claude/agents/` and
  `.claude/commands/`, plus the `.mcp.json` server declaration.
- **GitHub Copilot agent mode** reads the chat modes in `.github/chatmodes/`
  plus `.vscode/mcp.json`.

`.github/chatmodes/*.chatmode.md` are **generated**; never edit them by hand:

```bash
python scripts/regen_agent_definitions.py           # regenerate after editing .claude/agents/
python scripts/regen_agent_definitions.py --check   # CI/pytest guard (drift detection)
```

The body (the instructions) is copied verbatim; only the front matter changes
dialect: Claude Code tool names become the qualified VS Code forms
(`search/readFile`, `edit/editFiles`…), and MCP tools keep their per-tool
granularity as `rf-mcp-sap/<tool>`. This is the exact dialect emitted by
Playwright's own reference generator
(`packages/playwright/src/agents/generateAgents.ts`, the `init-agents`
machinery). Same pattern as `regen_recorder`: one source,
generated targets, a consistency guard
(`tests/unit/test_regen_agent_definitions.py` fails if the chat modes are
stale).

## In the Windows deployment pack

`build_release_pack.py` ships the whole system with the pack: `.claude/agents`
and `.claude/commands`, the generated `.github/chatmodes`, `specs/` (contract
plus the reference example), and both MCP templates. On the target PC:

1. `install.cmd -WithMcp` installs the plugins and renders **both** IDE
   configs in place: `.mcp.json` (Claude Code) and `.vscode/mcp.json`
   (Copilot), plus `mcp.generated.json` to copy if the agent runs in another
   project.
2. Open the pack folder in VS Code: the agents are discovered immediately
   (approve the project MCP server on first use).
3. Pack-specific rule (encoded in the agent definitions): the generator and
   healer never modify the files shipped by the pack: new keywords and
   locator overrides go to `resources/site_keywords.resource`, so a pack
   update never overwrites local work. In the source repo they enrich
   `resources/` normally (convention #1).

## Ground rules and safety

- **Perception before action**: the agents never guess a screen; they read it
  (`Get Screen Signature` / `Get Ui5 Page Tree`, `mode=diff` in loops).
- **Session isolation**: API/Fiori state is partitioned per rf-mcp session;
  ECC agents run one live session per process due to rf-mcp 0.31 nested-resource context limits.
- **The agents hold the SAP user's authorizations**, nothing more, nothing
  less (see the security notes in [mcp-integration.md](mcp-integration.md)).
  Point them at trial/test systems; the planner is display-only by contract.
- **Never silent**: every healer repair is reported `before → after` with live
  evidence, on top of the runtime's own WARN + telemetry journal.
- The definitions carry the repo conventions; `check_guidance_sync.py` fails
  if an agent definition stops mentioning them.

See also: [deployment-pack.md](deployment-pack.md) (end-to-end pack
walkthrough) and [mcp-integration.md](mcp-integration.md) (rf-mcp plugins).
