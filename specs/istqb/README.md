# specs/istqb/ : plans de test et cas de test ISTQB

Documents de **conception de test** au gabarit ISTQB / ISO 29119-3, un fichier
par domaine métier (`<slug>.istqb.md`, kebab-case), produits par l'agent
**sap-istqb** (`/sap-istqb`) depuis les plans `specs/` du planner et les
sorties des recorders ; les deux recorders émettent le même gabarit en
brouillon (`--export-istqb` côté desktop, entrée « plan ISTQB » du menu export
côté web).

Chaque document couvre les deux niveaux :

- **plan de test** : identifiant `TP-<slug>`, objectif et périmètre,
  préconditions et données, critères d'entrée/sortie, risques ;
- **cas de test** : un `TC-nn` par scénario, tableau
  `# | Action | Données | Résultat attendu`, postconditions, et un bloc
  `replay` YAML **normalisé** : actions neutres vis-à-vis du framework
  (`run_transaction`, `fill`, `click`, `press_key`, `assert_value`…), cible en
  langage humain, localisateur technique relevé relégué en `hint`
  (moteur + localisateur, repli éventuel). C'est ce bloc qui rend le cas
  rejouable par une IA avec n'importe quel framework de test.

Règles du répertoire :

- **Ancré dans l'observé** : toute valeur, tout localisateur, tout résultat
  attendu vient d'une source (plan, enregistrement, suite) ; ce qu'aucune
  source n'appuie reste « à compléter ».
- **Résultats attendus indépendants de la locale** : type de message (`E`/`S`),
  comptages, ids techniques ; jamais un texte localisé.
- **Aucune attente fixe** dans les blocs replay : une attente est toujours une
  condition (fin de chargement, élément présent), jamais une durée.
- Ces documents sont de la documentation : ils ne remplacent jamais les suites
  exécutables de `tests/robot/` et restent hors du périmètre de
  `check_spec_sync.py` (qui ne balaie que `specs/*.md`).
