# specs/ — plans de test (agents SAP)

Plans de test **lisibles métier**, au format Markdown, produits par l'agent
**sap-planner** (exploration live du système via rf-mcp) et consommés par
l'agent **sap-generator** (génération de suites Robot Framework vérifiées
live). Voir `docs/test-agents.md` pour le cycle complet
plan → génération → réparation.

Règles du répertoire :

- **Un fichier par domaine métier**, nom en kebab-case (`sflight-consultation-se16.md`).
- Rédigé **en français** ; noms de keywords, codes transaction, ids techniques
  restent en anglais.
- Un plan décrit des **scénarios en langage métier** — jamais d'id d'élément SAP
  ni de CSS/XPath dans les étapes (convention #1) ; les identifiants observés
  vont dans « Données observées » / « Points de vigilance », comme notes
  factuelles pour le générateur.
- Un plan est **ancré dans l'observé** : données réelles relevées pendant
  l'exploration, pas de valeurs supposées.
- La suite générée référence son plan d'origine ; quand le flux métier change,
  on met à jour le plan (re-passage du planner) puis on régénère — on n'édite
  pas les localisateurs à la main dans les tests.

Gabarit d'un plan :

```markdown
# <Titre métier>

- **Canal** : ECC (SAP GUI) | Fiori (web)
- **Système / URL** : <observé>
- **Préconditions** : données requises, réglages persistants.

## Données observées

## Scénarios

### 1. <Nom du scénario>
- **Étapes** : numérotées, une étape = de préférence un keyword métier existant.
- **Résultat attendu** : assertions indépendantes de la locale.
- **Keywords métier manquants** : à créer par le sap-generator.

## Points de vigilance
```

`sflight-consultation-se16.md` est l'exemple de référence : il correspond au
flux validé live par `tests/robot/ecc_data_smoke.robot`.
