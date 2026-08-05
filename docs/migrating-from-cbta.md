> **🇬🇧 English** · [🇫🇷 Français](migrating-from-cbta.fr.md)

# Migrating from CBTA (Solution Manager)

SAP Solution Manager 7.2 (the platform hosting CBTA and eCATT's Test Suite)
leaves mainstream maintenance on **2027-12-31**, and SAP has stated CBTA will
not be extended to its cloud products (SAP's designated successor path is
Cloud ALM + partner tooling). Every CBTA estate therefore needs a destination
before 2028. This guide maps CBTA concepts onto this project and sketches the
migration path.

## Concept mapping

| CBTA / Solution Manager | Here |
|---|---|
| Test script (Test Composition Environment) | a `.robot` suite under `tests/robot/` |
| Component (reusable step) | a business keyword in `resources/*.resource` (convention 1: tests never carry raw SAP ids) |
| Default components (screen actions) | `SapEccLibrary` / `SapFioriLibrary` keywords (waits, grids, labels, UI5 engines) |
| SUT connection (system data container) | connection string + credentials injected per run (`-v SAP_CONNECTION:… -v SAP_USER:…` from CI secrets) |
| Recording a script | desktop recorder (`tools/recorder`, native scripting events, `--semantic` for label-based keywords) and web recorder (MV3 extension) |
| Script maintenance after UI changes | `sap-healer` agent + locator healing with telemetry (`SAPFX_HEALING_LOG` → `scripts/healing_drift_report.py` proposes the resource patch) |
| Execution lists / test plans | `robot` CLI + your CI scheduler (tags select scope; `--include smoke`) |
| Evidence (screenshots, logs) | Robot `log.html`/`report.html`, inline screenshots, visual baselines |
| Coverage hints (TBOM) | suite/test tags + the spec layer (`specs/`: each generated suite carries its plan's hash, enforced by `check_spec_sync.py`) |

## Migration path

1. **Inventory** the CBTA scripts that still deliver value (many estates
   carry dead scripts; do not port those).
2. For each business flow, let **sap-planner** explore the live system through
   rf-mcp and write the plan into `specs/` (French Markdown, reviewable by
   business analysts; this replaces re-reading CBTA scripts).
3. **sap-generator** turns the plan into a suite, executing every step live
   before writing it; missing building blocks land in `resources/`, not in
   tests.
4. Wire into CI (`robot --dryrun` as a gate, then scheduled runs); adopt the
   [hardening checklist](hardening-test-environment.md) for the runner
   workstation and the RZ11 posture.
5. When the UI drifts, **sap-healer** repairs the resource layer: tests stay
   untouched, and the healing telemetry tells you which locators drift
   repeatedly.

## What this project does not replace

Test *management* (plans, approvals, requirement traceability) lived in
Solution Manager itself: that role moves to SAP Cloud ALM or your ALM of
choice, and Robot Framework results (`output.xml`) integrate with most of them.
CBTA licenses bundled with Enterprise Support also cover Tricentis tooling;
this project is the open-source, code-first, agent-ready alternative; the
two can coexist during the transition.
