---
name: sapfx
description: >-
  Boîte à outils SAPFX pour piloter et tester SAP depuis Robot Framework :
  SAP GUI desktop (SapEccLibrary), Fiori/UI5 web (SapFioriLibrary) et API
  OData/RFC (SapApiLibrary). Charger cette skill avant tout travail de test
  SAP : boucle perception → action (carte numérotée @N, diff, screenshot
  annoté), keywords phares, conventions non négociables, cycle agents
  plan → generate → heal.
---

# SAPFX : piloter et tester SAP depuis Robot Framework

Trois canaux, un vocabulaire métier commun (couche `resources/`) :

- **SapEccLibrary** : SAP GUI desktop (ECC/S/4 backend) via l'API Scripting COM.
- **SapFioriLibrary** : Fiori/UI5 web, au-dessus de la bibliothèque Browser
  (Playwright) ; une suite doit importer `Library    Browser` à côté.
- **SapApiLibrary** : OData v2/v4 + RFC optionnel. Préparer/recouper les
  données par l'API, ne piloter l'écran que pour ce qu'on teste : CRUD
  complet (`Post/Patch/Delete Odata`, `Post Odata Batch` atomique), fabrique
  de données (`track=True`, `Ensure Odata Entity`, `Delete Created Entities`
  en teardown), préflight `Gateway Should Be Active` / `Wait Until Api
  Available`, discovery `Get Odata Metadata` / `List Odata Services` /
  `Find Odata Property By Label`, pattern BAPI (`Call Bapi` + `Commit/
  Rollback Bapi Transaction`) et `Wait For Background Job` (TBTCO par RFC).

## La boucle perception → action (ECC)

Ne jamais deviner un écran. Le percevoir, puis agir, puis re-percevoir :

1. `Get Screen Map`, carte **numérotée** des cibles actionnables :
   `@1  * Table Name  wnd[0]/usr/ctxtDATABROWSE-TABLENAME  GuiCTextField  = T000`.
2. `Click Screen Ref    @2` / `Fill Screen Ref    @1    T000` : action par
   numéro, sans recopier l'id ; la résolution re-vérifie l'écran et échoue
   proprement si les références sont périmées (re-percevoir alors).
3. Après une action : `Get Screen Signature    mode=diff`, seul ce qui a
   changé revient (fraction des tokens) ; `mode=semantic` = vue formulaire.
4. `Get Open Windows` : détecter un modal résiduel (piège SESSION_MANAGER :
   `Run Transaction` peut rapporter un succès avec un popup d'erreur ouvert).
5. Canal visuel : `Get/Log Annotated Screenshot` (Set-of-Mark : boîtes
   numérotées + légende `numéro -> id`, même table `@N` que la carte).

Côté Fiori : `Get Ui5 Page Tree` (`mode=diff` ensuite), et la même boucle
courte. `Get Ui5 Page Map` numérote les contrôles actionnables,
`Click Ui5 Ref` / `Fill Ui5 Ref` agissent par `@N` (fraîcheur re-vérifiée au
registre rendu). `Get Page Composition` sur une page hybride (quels moteurs
par région : role/xpath/sid/wc/dom), `Get Fiori Diagnostics` quand un écran
se comporte mal (lire `issues` d'abord). Après une action qui déclenche de
l'OData : `Wait For Ui5 Idle` (le repos réseau réel, « rendu » ne veut pas
dire « données arrivées ») ; messages applicatifs par TYPE via
`Get Ui5 Messages` / `Ui5 Should Have No Messages Of Type`, précédés de
`Ui5 Runtime Is Present` quand la page peut ne pas être UI5 (moteurs wc/sid/dom
: des cibles légitimes, pas des pannes ; cette sonde répond sans jamais échouer
et sans rien injecter dans la page). `Get Ui5 Application State` donne les trois
d'un coup (portée de frame, runtime, messages) : le « où en suis-je » du canal
web, à joindre au diagnostic d'un échec.

## Les règles non négociables

1. **Aucun id SAP brut ni CSS/XPath dans les tests** : les localisateurs
   vivent dans `resources/` (ou `resources/site_keywords.resource` sur un
   pack déployé, jamais dans les fichiers livrés) ; les tests parlent métier.
   Les références `@N` sont éphémères : pilotage interactif seulement,
   jamais dans une suite.
2. **Jamais `time.sleep`** : `Wait Until Busy Done`, `Wait Until Element
   Present`, `Wait For UI5 Ready`.
3. **Assertions indépendantes de la locale** : le TYPE du message de barre
   d'état (`E`/`S`/…), les ids techniques de colonnes (`CARRID`), jamais un
   texte localisé.
4. **Toujours refermer les sessions ouvertes, même sur échec** (`Close SAP`,
   `Close All Sap Sessions`) : une connexion orpheline décale les indices du
   prochain attach.

## Robustesse intégrée

- Localisateurs humains : `Fill Field By Label`, `Click Button By Label`
  (grammaire `@`, `Ancre >> Reste`), ambiguïté toujours remontée.
- Auto-réparation : `Resolve Element With Healing` (ECC, `label=` en ancre),
  `Resolve Ui5 With Fallback` (chaîne role→xpath→sid→wc→dom), réparation
  journalisée, jamais silencieuse ; télémétrie `SAPFX_HEALING_LOG`.
- Assertions visuelles : `Screen Should Match Baseline`
  (`mask_elements=auto`), déclinaison par élément et côté Fiori.
- Écrans classiques ECC : `Read Table Control` et ses variantes (tables de
  dynpro adressées par TITRE de colonne, défilement automatique),
  `Pick F4 Value` (matchcode ouvert, entrée choisie, popup refermé).

## Le cycle agents

`/sap-plan` (exploration live → plan `specs/`) → `/sap-generate` (plan →
suite `.robot`, chaque étape vérifiée live) → `/sap-heal` (échec reproduit,
patch de `resources/`, jamais des tests) ; `/sap-maintain` = sentinelle +
télémétrie + réparations en un rapport ; `/sap-istqb` = plans du planner +
sorties recorder → plan de test + cas de test ISTQB sous `specs/istqb/`
(bloc replay normalisé, rejouable par une IA quel que soit le framework).

Repères : `llms.txt` (index du projet), `docs/test-agents.md`,
`docs/architecture.md`.
