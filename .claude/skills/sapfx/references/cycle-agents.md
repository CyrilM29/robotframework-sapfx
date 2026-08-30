# Le cycle agentique : plan → generate → heal

Quatre agents, chacun avec UN livrable et une couche d'écriture qui lui est
propre. La discipline tient à cela : personne n'écrit dans la couche d'un autre.

| Agent | Commande | Lit | Écrit | N'écrit JAMAIS |
| --- | --- | --- | --- | --- |
| `sap-planner` | `/sap-plan` | le système LIVE | `specs/<slug>.md` | ni `.robot`, ni `resources/` |
| `sap-generator` | `/sap-generate` | un plan `specs/` | `tests/robot/<canal>/<slug>.robot`, page objects, `src/` si capacité manquante | pas de keyword inventé |
| `sap-healer` | `/sap-heal` | un échec reproduit | `resources/`, `src/` si défaut de bibliothèque, `docs/heal-journal.md` | **jamais les tests** |
| `sap-istqb` | `/sap-istqb` | plans et sorties recorder | `specs/istqb/*.istqb.md` | rien d'exécutable |

Deux orchestrateurs : `/sap-maintain` (sentinelle → télémétrie → réparations, un
rapport unique) et `/sap-eval-healer` (éval EN AVEUGLE du healer sur une dérive
simulée, injectée puis restaurée par un harnais ; filet de régression du studio,
absent d'un pack déployé).

**Où vit quoi.** Les quatre agents sont définis ICI, dans
`.claude/agents/sap-*.md` : c'est là que se lisent leur workflow, leurs règles
de base et leur raisonnement, et les chat modes VS Code en sont GÉNÉRÉS
(`scripts/regen_agent_definitions.py`, jamais édités à la main). Ce que ce dépôt
ne possède pas, c'est le PATRON de méthode dont ces quatre-là sont la
déclinaison SAP : il vit dans le dépôt frère `rf-test-agents` (`rf-planner`,
`rf-generator`, `rf-healer`, `rf-istqb`, avec son propre `CLAUDE.md`), sans
AUCUNE dépendance de code, seulement un alignement conceptuel. Conséquence
pratique : consulter le dépôt frère avant d'improviser une réponse locale sur le
workflow ou la division du travail d'un agent, et rétroporter là-bas toute
amélioration de méthode trouvée ici, pour que les quatre agents raisonnent
pareil sur toutes les verticales.

## Ce qui rend le cycle vérifiable

Chaque étape produit une preuve, sinon elle n'est pas faite.

- **Le planner n'écrit que ce qu'il a OBSERVÉ.** Pas de « l'écran ressemble
  probablement à ». Chaque scénario porte ses données réelles, ses ids relevés
  et ses points de vigilance.
- **Le generator EXÉCUTE chaque étape live avant de l'écrire** (`execute_step`,
  keywords métier d'abord). Un keyword non défini dans une resource ou une
  bibliothèque n'existe pas : jamais de nom inventé.
- **Le healer VÉRIFIE la réparation live avant de toucher un fichier**, et une
  réparation n'est jamais silencieuse (WARNING journalisé, télémétrie
  `SAPFX_HEALING_LOG`, entrée de journal avec la classe d'échec).
- **Les gates du generator, dans l'ordre** : `--dryrun`, puis
  `python scripts/check_conventions.py`, puis le run live. Un garde rouge sur
  SA propre suite est un défaut de sa sortie, jamais un garde à contourner.
  Ne jamais présenter une suite non exécutée comme faite.

## Les boucles de rétroaction, fermées mécaniquement

C'est ce qui distingue ce cycle d'un enchaînement de prompts.

1. **Le plan est la source de vérité.** Une suite générée porte un marqueur de
   provenance (hash du plan plus date), posé par
   `python scripts/check_spec_sync.py --stamp <suite> <spec>`. Si le plan
   change sans régénération, la CI échoue : on ne rattrape JAMAIS une suite à
   la main pour la remettre en phase avec son plan.
2. **Les écarts constatés retournent dans le plan.** Quand la réalité live
   contredit le plan, le generator écrit une section
   `## Écarts constatés à la génération` (date, ce que dit le plan, ce qui a
   été observé, ce que fait la suite) AVANT de tamponner, donc le hash couvre
   le plan annoté et le planner voit les manques au passage suivant. Un écart
   qui change le SENS MÉTIER d'un scénario est un arrêt et un rapport, pas une
   annotation : ce flux repasse par `/sap-plan`.
3. **Un flux métier réellement changé périme son plan.** Le healer ne force pas
   le vert : il pose `robot:skip` avec la raison, et marque le plan
   `> **Statut : PÉRIMÉE (<date>)** : <ce qui a changé> ; re-explorer via
   /sap-plan.` `check_spec_sync.py` échoue tant que le marqueur est là, donc la
   dérive vit dans la CI et non dans un rapport de conversation. Le planner le
   retire en ré-explorant.
4. **Chaque session de healing écrit dans `docs/heal-journal.md`** : diagnostic,
   classe d'échec, preuve, leçon d'ancrage. Complémentaire de la télémétrie
   runtime, que `scripts/healing_drift_report.py` relit pour proposer des
   patchs `resources/` sur les dérives STABLES.

## Les cinq classes d'échec du healer

Le diagnostic précède la réparation, et la classe décide de la couche.

| Classe | Réparation |
| --- | --- |
| Dérive de localisateur | `resources/` : ancre plus stable (libellé, suffixe d'id, chaîne de repli) |
| Timing | la bonne attente conditionnelle ou un `timeout=` explicite, JAMAIS un sleep |
| Dérive de données | pointer les garanties de données, ou corriger les préconditions du plan |
| **Défaut de bibliothèque** | `src/` (convention #12) : le keyword ment, ignore un cas réel, ou manque. Contournement dans une resource = défaut laissé en place pour tous les autres utilisateurs |
| Changement fonctionnel réel | `robot:skip` plus plan marqué périmé ; retour au planner |

## Hygiène de session, valable pour les quatre

Préflight des connexions, une session ECC live à la fois par process rf-mcp, et
fermeture de TOUT ce qu'on a ouvert **même sur échec ou abandon**. Une connexion
orpheline décale les indices, et le prochain `Attach To Open Session` ou replay
saisit silencieusement la mauvaise session (leçon live). Fermer avant de rejouer
une suite : elle ouvre la sienne en Suite Setup.

Sur un **pack déployé** (pas de `src/`) : écrire dans
`resources/site_keywords.resource`, jamais dans les fichiers livrés, ET signaler
le défaut en amont. Un correctif local dont personne n'entend parler se paie
deux fois.

Détails du pont MCP : [rf-mcp.md](rf-mcp.md). Contrat complet des agents :
`.claude/agents/*.md` et `docs/test-agents.md`.
