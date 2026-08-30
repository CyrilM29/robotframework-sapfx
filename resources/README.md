> **🇬🇧 English** · [🇫🇷 Français](README.fr.md)

# `resources/`: examples to customize, never a universal SAP truth

**What makes truth in this project is `src/`.** The three libraries
(`SapEccLibrary`, `SapFioriLibrary`, `SapApiLibrary`) and `sapfx_common` carry
the CAPABILITIES: perception, locator resolution, waiting, engines, state
reading, protocol handling, healing. They are system independent, unit tested
off SAP, versioned, published on PyPI, and what one of their keywords promises,
it promises on any SAP system.

**`resources/` is the opposite, by design.** It carries the business VOCABULARY
of *one* installation: the ids, service paths, table and function-module names,
profile parameters and screen flows of a given target, named in the language of
a given business domain. Every value here was measured live on the lab targets
of this repository.

Much of it travels: standard transactions, standard OData services and the
mirrored channel vocabulary are the same on many systems, so a good part of this
layer is reusable as is. But **nothing here is authoritative**. A release, a
language, a screen variant, a custom Z field, or simply your own business domain
changes what a keyword has to address. Verify on your target, and expect to
adapt.

So: **these files are to be customized for your target and for your business
domain.** A starter kit, not a dependency.

## What was measured, and where

| Target used by this repo | What it fixed in `resources/` |
| --- | --- |
| ABAP Platform Trial 1909 (A4H, Docker) | SE16/SE38/SM50 element ids, the SE16 selection-screen field maps, demo-data guards (SFLIGHT, EPM) |
| ABAP Platform 2023 | the second release of the shared FLP page object, the security control lots |
| OpenUI5 Demo Kit, local cap-sflight | the Fiori vocabulary, the Travel list page object, and `page_objects/openui5_demokit.resource` (hash routing, API tree, doc tables, Options menu, theme, sample iframe) |
| A SAP Build Work Zone site on BTP (behind an IAS tenant) | the `workzone_*` page objects (shell, search, user area, session, embedded app) |
| The A4H Gateway, cap-sflight, the SAP Business Accelerator Hub sandbox | the OData service paths behind business names (`${EPM_PRODUCTS}`, `${TRAVEL_ENTITIES}`…) |

Three degrees, in practice:

- **Often reusable as is**: the standard screens (SE16, SE11, SE38), the FLP and
  ushell page-object patterns, the API and RFC preflights, and the whole naming
  scheme. `${SE16_TABLE_FIELD}` is an id read on SAP GUI 8.00 against A4H, and it
  usually still holds elsewhere.
- **To verify, and often to adjust**: the positional selection-screen ids (they
  follow the table's field order, so they move with the release), the grid paths
  (recent releases wrap the ALV in a splitter, at a depth that varies by
  transaction), the launchpad anchors (they differ between UI5 1.71 and 1.120,
  which is exactly why `page_objects/abap_flp.resource` is shared by both).
- **Lab specific, expect to replace**: the demo models (SFLIGHT, EPM, `/DMO/`)
  and the service paths that project them, the `workzone_*` page objects written
  for one BTP site, the demo-data guards, and `@{PARAMS_PASSWORD_POLICY}`, which
  is a *selection* of profile parameters that suits a sandbox and must follow
  your own security policy instead.

## What IS reusable here

The values are local; the **pattern** is not. What you should keep when you
rewrite this layer for your site:

- **One mirrored vocabulary across the four channels** (ECC, Fiori, OData, RFC):
  `Open …`, `Count …`, `Read …`, `Close …`, so a test reads the same way
  whichever channel it drives (see the mapping tables in each file's
  `Documentation`).
- **Convention 1**: no raw SAP id, no CSS/XPath, no OData service path, no
  function-module or table name inside a test case. They live in this layer, the
  tests speak business.
- **One `.resource` per screen or application** under `page_objects/`, locator
  variables plus business keywords: this is the layer the `sap-healer` agent
  repairs, and the layer a release upgrade makes you touch.
- **The safety properties encoded in the keywords**, which are worth copying
  verbatim: write paths gated by an allowlist, deletions that re-read the
  filtered grid before acting, assertions judged on a message TYPE and never on
  localized text, cleanups verified rather than assumed.
- **Release divergences expressed as a variable or a named strategy**, never as
  an `IF` on a version number (see `page_objects/abap_flp.resource`, shared by
  UI5 1.71 and 1.120).

## Using it on your own system

1. Copy the file that matches your channel, keep the keyword names, replace the
   variables with what you measured on *your* target (the `sap-planner` agent
   and both recorders exist to measure them for you).
2. Put your environment values in `variables/env_<env>.yaml`, and **never a
   credential default**: passwords, API keys and tokens come from the command
   line (`-v "SAP_PASSWORD: Secret:…"`) or from the environment.
3. On a **deployed pack** (no `src/` to edit), write your own keywords in
   `resources/site_keywords.resource`: the shipped files are overwritten by the
   next pack update, yours are not.

## Where a fix goes, and why it matters

A defect you hit on a live target does not always belong here:

- The library keyword misbehaves, or the capability is missing: **fix it in
  `src/`** (pure logic in `sapfx_common`). That is what ships to PyPI, so a fix
  left in a resource helps nobody else and gets re-improvised in the next
  project.
- The target names things differently, the screen flow changed, an id drifted:
  **fix it here**, this layer exists exactly for that.

This boundary is convention 12 of `CLAUDE.md`, and it is also why the healing
telemetry proposes patches in `resources/` only: what varies per site must stay
in the layer that is meant to vary.

## Why ship them at all

Because a working pattern beats an empty folder, and because these files are not
decorative: they are the ones the live campaigns of this repository run against
real systems (A4H, ABAP Platform 2023, a BTP Work Zone site, cap-sflight). They
prove the libraries against reality, and they show you the shape of the layer you
have to write. Read them as a worked example, not as a contract.
