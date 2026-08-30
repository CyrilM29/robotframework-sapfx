---
name: sapfx
description: >-
  Boîte à outils SAPFX pour piloter et tester SAP depuis Robot Framework, sur
  les quatre canaux : SAP GUI desktop (SapEccLibrary), Fiori/UI5 web et WebGUI
  (SapFioriLibrary), OData v2/v4 et RFC/BAPI (SapApiLibrary), plus la posture de
  sécurité d'un système ABAP. Charger cette skill avant tout travail de test SAP
  (SE16, ALV, dynpro, launchpad FLP, Work Zone, Gateway, pyrfc, healing,
  recorders) : boucle perception → action (carte numérotée @N, diff, screenshot
  annoté), keywords phares par canal, conventions non négociables, pièges
  relevés live, cycle agents plan → generate → heal.
---

# SAPFX : piloter et tester SAP depuis Robot Framework

## Ce qui fait foi, et ce qui est un exemple

- **`src/` fait foi** : `SapEccLibrary`, `SapFioriLibrary`, `SapApiLibrary` et
  `sapfx_common` portent les CAPACITÉS (perception, résolution, attente,
  moteurs, lecture d'état, protocoles, auto-réparation). Indépendantes de la
  cible, testées hors SAP, publiées sur PyPI.
- **`resources/` est une trousse d'EXEMPLES** : le vocabulaire métier d'UNE
  installation, relevé live sur les cibles du laboratoire du dépôt. Beaucoup
  s'y réutilise (écrans et services standard, nomenclature en miroir, patrons
  de page object), rien n'y fait autorité : à vérifier sur la cible et à
  adapter au métier du testeur (`resources/README.md`). Ne jamais présenter une
  valeur de `resources/` comme un fait SAP.

**Quatre canaux, un vocabulaire en miroir** (`Open …`, `Count …`, `Read …`,
`Close …`) : ECC (SAP GUI via COM), Fiori/UI5 web (au-dessus de la bibliothèque
Browser, une suite doit importer `Library    Browser` à côté), OData v2/v4, et
RFC/BAPI (optionnel : `pyrfc`, interpréteur 3.10 à 3.12). Un canal sans écran
prépare et recoupe les données ; l'écran ne pilote que ce qu'on teste.

## Par où continuer selon la tâche

| Tâche du moment | Lire |
| --- | --- |
| Écrire ou lancer une suite, ranger les fichiers, passer un secret | [references/demarrage.md](references/demarrage.md) |
| Piloter SAP GUI : SE16, ALV, table control, sessions, visuel, DDIC | [references/canal-ecc.md](references/canal-ecc.md) |
| Piloter Fiori/UI5, un launchpad, une page hybride, le WebGUI | [references/canal-fiori.md](references/canal-fiori.md) |
| Canal OData, canal RFC/BAPI, posture de sécurité ABAP | [references/canal-api-rfc.md](references/canal-api-rfc.md) |
| Vérifier une règle du dépôt avant d'écrire ou de committer | [references/conventions.md](references/conventions.md) |
| Un comportement bizarre sur une cible réelle | [references/pieges-terrain.md](references/pieges-terrain.md) |
| Travailler en agent via le serveur MCP (rf-mcp, `sapfx-mcp`) | [references/rf-mcp.md](references/rf-mcp.md) |
| Dérouler le cycle plan → generate → heal | [references/cycle-agents.md](references/cycle-agents.md) |

## La boucle perception → action

Ne jamais deviner un écran. Le percevoir, agir, re-percevoir.

**ECC** :

1. `Get Screen Map`, carte **numérotée** des cibles actionnables :
   `@1  * Table Name  wnd[0]/usr/ctxtDATABROWSE-TABLENAME  GuiCTextField  = T000`.
2. `Click Screen Ref    @2` / `Fill Screen Ref    @1    T000` : action par
   numéro, sans recopier l'id ; la résolution re-vérifie l'écran et échoue
   proprement si les références sont périmées (re-percevoir alors).
3. Après une action : `Get Screen Signature    mode=diff`, seul ce qui a changé
   revient (fraction des tokens) ; `mode=semantic` = vue formulaire.
4. `Get Open Windows` : détecter un modal résiduel (piège SESSION_MANAGER :
   `Run Transaction` peut rapporter un succès avec un popup d'erreur ouvert).
5. Canal visuel : `Get/Log Annotated Screenshot` (Set-of-Mark : boîtes
   numérotées + légende `numéro -> id`, même table `@N` que la carte).

**Fiori** : même boucle courte avec `Get Ui5 Page Tree` (`mode=diff` ensuite) et
`Get Ui5 Page Map` (`Click Ui5 Ref` / `Fill Ui5 Ref` par `@N`, fraîcheur
re-vérifiée au registre rendu). `Get Ui5 Application State` donne le « où en
suis-je » en un appel (portée de frame, runtime, messages) ;
`Get Page Composition` dit quels moteurs valent par région sur une page
hybride ; `Get Fiori Diagnostics` quand un écran se comporte mal (lire `issues`
d'abord). Détails et pièges : [references/canal-fiori.md](references/canal-fiori.md).

Les références `@N` sont **éphémères** : pilotage interactif seulement, jamais
dans une suite.

## Les règles non négociables

1. **Aucun id SAP brut ni CSS/XPath dans les tests.** Les localisateurs vivent
   dans `resources/` (page objects), les tests parlent métier. Sur un pack
   déployé : `resources/site_keywords.resource`, jamais les fichiers livrés.
2. **Jamais `time.sleep`** : `Wait Until Busy Done`, `Wait Until Element
   Present`, `Wait For UI5 Ready`, `Wait For Ui5 Idle`.
3. **Assertions indépendantes de la locale** : le TYPE d'un message (`E`/`S`/…),
   les ids techniques de colonnes (`CARRID`), un CODE de refus RFC, jamais un
   texte traduit.
4. **Aucun identifiant en dur** : mots de passe, clés d'API et jetons entrent
   par la ligne de commande (`-v "SAP_PASSWORD: Secret:…"`) ou l'environnement ;
   dans `resources/` et `variables/`, la valeur par défaut reste `${EMPTY}`.
5. **Refermer les sessions ouvertes, même sur échec** (`Close SAP`,
   `Close All Sap Sessions`, `Close Api Channel`, `Close Rfc Channel`) : une
   connexion orpheline décale les indices du prochain attach et laisse une
   session ouverte côté serveur.
6. **Une lacune de capacité trouvée sur une cible réelle se comble DANS la
   bibliothèque** : un keyword fautif se corrige dans `src/`, un keyword
   manquant s'y crée (logique pure dans `sapfx_common`), jamais en JS inline
   dans un page object ni en `Evaluate` dans une suite ; un contournement écrit
   dans une couche intermédiaire se REMONTE. C'est le seul endroit où
   « constater, ne pas corriger » ne s'applique pas : la cible se constate,
   notre bibliothèque se répare.
7. **Constater, ne pas corriger** : un test rouge, une violation
   d'accessibilité, une dérive de baseline se RAPPORTENT (fichier, écran,
   règle, impact, sortie utile). Ni correction de l'application testée, ni
   `--update-snapshots` de confort, sans demande explicite.

Le contrat complet (13 conventions, ventilation des fichiers, gardes
mécaniques) : [references/conventions.md](references/conventions.md).

## La mémoire QA partagée (RAG `qa-brain`), si elle est montée

Quand le serveur MCP `qa-brain` est disponible (RAG sur la mémoire QA de
l'équipe : keywords, specs, docs, leçons écrites après incident réel),
l'interroger AVANT les décisions de jugement, pour ne pas repayer une leçon déjà
payée : quelle ancre tient sur cet écran, dans quelle couche va un keyword, de
quelle classe relève un échec, quel piège porte cette famille de transactions.
`qa_search` (question en langage naturel, filtres `vertical=sap`,
`type=robot|markdown|libdoc|lesson`) rend les passages avec leur source ;
`qa_ask` rédige une réponse à citations obligatoires ; `qa_status` donne la
santé de l'index (hors `green` = corpus daté, réponses à traiter comme des
pistes).

Trois garde-fous : l'observation LIVE tranche (un passage n'est jamais une
perception, ni une étape vérifiée, ni une preuve de réparation, et quand les
deux divergent c'est le système qui a raison) ; la source se cite quand un
passage a guidé un choix ; et c'est **jamais bloquant** (serveur absent ou en
erreur : une ligne au rapport, le déroulé normal continue). Un pack déployé
n'embarque pas `qa-brain` : traiter sa présence comme optionnelle, toujours.

## Le cycle agents

`/sap-plan` (exploration live → plan `specs/`) → `/sap-generate` (plan → suite
`.robot`, chaque étape EXÉCUTÉE live avant d'être écrite) → `/sap-heal` (échec
reproduit, réparation vérifiée live, patch de `resources/`, jamais des tests) ;
`/sap-maintain` = sentinelle + télémétrie + réparations en un rapport ;
`/sap-istqb` = plans et sorties recorder → cas de test ISTQB sous
`specs/istqb/` ; `/sap-eval-healer` = éval en aveugle du healer.

Trois règles qui tiennent le cycle : **le plan est la source de vérité** (une
suite générée porte le hash de son plan, `check_spec_sync.py` échoue si l'un
bouge sans l'autre, on ne rattrape jamais une suite à la main), **rien n'est
écrit qui n'ait été observé ou exécuté live**, et **chaque agent n'écrit que
dans SA couche**. Le détail, les boucles de rétroaction et les cinq classes
d'échec du healer : [references/cycle-agents.md](references/cycle-agents.md).

Les quatre agents vivent ICI (`.claude/agents/sap-*.md`) : définition, workflow
et règles de base. Ce que ce dépôt ne possède pas, c'est le PATRON de méthode
dont ils sont la déclinaison SAP : il vit dans le dépôt frère `rf-test-agents`
(`rf-planner`, `rf-generator`, `rf-healer`, `rf-istqb`), sans aucune dépendance
de code. Le consulter avant de modifier le workflow d'un agent d'ici, et y
rétroporter toute amélioration de méthode.

Repères : `llms.txt` (index du projet), `docs/test-agents.md`,
`docs/architecture.md`, `resources/README.md`.
