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

Lire une VALEUR : `Get Ui5 Property` / `Get Ui5 Properties` (la propriété au
registre), pas `Get Ui5 Text` (le rendu, qui exige la visibilité et ajoute ce
que le contrôle dessine). `Get Ui5 Ids` répond LESQUELS ont matché (l'ancre
d'un shell est un suffixe d'id ; `containedIn=` restreint au contenu DOM d'un
autre contrôle, là où `viewId` suit la propriété). Dialogues :
`Get Ui5 Open Popups` (le pendant Fiori de `Get Open Windows` : un dialogue
fermé reste RENDU, seul `sap.m.InstanceManager` tranche) et
`Click Ui5 Dialog Button` (acquitter par POSITION : les boutons d'une
MessageBox portent un id généré et un texte traduit, et la bonne position
varie par release, la relever avant de graver).

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
5. **Une lacune de capacité trouvée sur une cible réelle se comble DANS la
   bibliothèque.** Un keyword de bibliothèque qui se comporte mal se CORRIGE
   dans `src/` ; un keyword manquant se CRÉE dans `src/Sap*Library` (logique
   pure dans `sapfx_common`), jamais en JS inline dans un page object, en
   `Evaluate` dans une suite, ou en aide locale que seule cette campagne verra ;
   un contournement déjà écrit dans une couche intermédiaire se REMONTE dans la
   bibliothèque. La frontière : les bibliothèques portent les CAPACITÉS
   (perception, résolution, attente, moteurs, état, protocoles), `resources/`
   porte le VOCABULAIRE MÉTIER d'un site. Ce sont les bibliothèques qui partent
   sur PyPI : un correctif resté dans une resource ne profite à personne
   d'autre. C'est le seul endroit où « constater, ne pas corriger » ne
   s'applique pas : la cible se constate, notre bibliothèque se répare. Chaque
   keyword ainsi ajouté garde son dû : test unitaire hors SAP (règle 5 des
   conventions du dépôt), carte d'intention rf-mcp, page Libdoc, CHANGELOG.

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

## La mémoire QA partagée (RAG `qa-brain`), si elle est montée

Quand le serveur MCP `qa-brain` est disponible (RAG sur la mémoire QA de
l'équipe : keywords, specs, docs, leçons écrites après incident réel),
l'interroger AVANT les décisions de jugement, pour ne pas repayer une leçon
déjà payée : quelle ancre tient sur cet écran, dans quelle couche va un
keyword, de quelle classe relève un échec, quel piège porte cette famille de
transactions. `qa_search` (question en langage naturel, filtres
`vertical=sap`, `type=robot|markdown|libdoc|lesson`) rend les passages avec
leur source ; `qa_ask` rédige une réponse à citations obligatoires ;
`qa_status` donne la santé de l'index (hors `green` = corpus daté, réponses à
traiter comme des pistes).

Trois garde-fous : l'observation LIVE tranche (un passage n'est jamais une
perception, ni une étape vérifiée, ni une preuve de réparation, et quand les
deux divergent c'est le système qui a raison) ; la source se cite quand un
passage a guidé un choix ; et c'est **jamais bloquant** (serveur absent ou en
erreur : une ligne au rapport, le déroulé normal continue). Un pack déployé
n'embarque pas `qa-brain` : traiter sa présence comme optionnelle, toujours.

## Le cycle agents

`/sap-plan` (exploration live → plan `specs/`) → `/sap-generate` (plan →
suite `.robot`, chaque étape vérifiée live) → `/sap-heal` (échec reproduit,
patch de `resources/`, jamais des tests) ; `/sap-maintain` = sentinelle +
télémétrie + réparations en un rapport ; `/sap-istqb` = plans du planner +
sorties recorder → plan de test + cas de test ISTQB sous `specs/istqb/`
(bloc replay normalisé, rejouable par une IA quel que soit le framework).

Repères : `llms.txt` (index du projet), `docs/test-agents.md`,
`docs/architecture.md`.
