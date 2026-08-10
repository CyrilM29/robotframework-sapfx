---
description: Produire un plan de test + cas de test ISTQB (lisible humain, rejouable par une IA quel que soit le framework) depuis un plan specs/ ou une sortie recorder (agent sap-istqb)
---

Use the **sap-istqb** agent to turn existing test material into an ISTQB test
plan + test cases under `specs/istqb/`, for: $ARGUMENTS

If the arguments do not name a source, list the candidates (in French):
`specs/*.md` plans (excluding README.md), recorder outputs
(`tools/recorder/captures/*.robot`, downloaded `recorded*.robot` /
`*.spec.md` / `*.istqb.md` drafts the user points to) and ask which to use;
suggest `/sap-plan` or a recorder session when nothing exists yet.

Then launch the agent, wait for its result, and relay its French report (the
document path, the test-case list with priorities, traceability gaps, and the
« à compléter » items needing a human answer) to the user.
