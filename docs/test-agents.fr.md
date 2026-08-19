> [🇬🇧 English](test-agents.md) · **🇫🇷 Français**

# Agents de test SAP (plan → génération → réparation)

Un flux Robot Framework agentique pour cet écosystème, transposant le principe
des [Playwright Test Agents](https://playwright.dev/docs/test-agents)
(planner / generator / healer) à SAP : les agents pilotent le système **live**
via le [serveur rf-mcp et ses plugins SAP](mcp-integration.fr.md), parlent le
vocabulaire métier de `resources/` et respectent les conventions du dépôt
(localisateurs dans la couche resources, pas d'attente fixe, assertions
indépendantes de la locale).

## Les quatre agents

| Agent | Entrée | Sortie |
|---|---|---|
| **sap-planner** | Un objectif métier + un système accessible (tcode ECC ou URL Fiori) | Un plan de test Markdown dans `specs/`, ancré dans l'observé live (boucle perception → action) |
| **sap-generator** | Un plan de `specs/` | Une suite exécutable dans `tests/robot/`, chaque étape exécutée live via rf-mcp avant d'être écrite ; les keywords métier manquants ajoutés à la couche resources |
| **sap-healer** | Une suite/un test en échec | L'échec reproduit, classifié (dérive de localisateur / timing / données / changement fonctionnel) et réparé **dans la couche resources**, vérifié live, relancé jusqu'au vert, jamais silencieusement |
| **sap-istqb** | Des plans du planner et/ou des sorties recorder (enregistrements, brouillons `.spec.md`/`.istqb.md`) | Un document **plan de test + cas de test ISTQB** sous `specs/istqb/` (hors ligne, artefacts seulement) : sections ISO 29119-3, un cas de test par scénario avec tableau Action / Données / Résultat attendu et bloc `replay` YAML normalisé, lisible par un humain ET rejouable par une IA avec n'importe quel framework de test ; ce qu'aucune source n'appuie reste « à compléter » |

Le planner a aussi un **mode découverte de couverture**, pour la question qui
vient *avant* tout plan, « que faut-il tester en premier ? » : il lit l'usage
réel du système via le profil de transactions de **ST03N** (perception →
action, keywords de grille), classe les transactions par étapes de dialogue ×
utilisateurs, signale ce que les suites existantes couvrent déjà, et écrit une
feuille de route dans `specs/couverture-proposee.md` : une entrée par
transaction très utilisée non couverte, chacune passant ensuite par la boucle
d'exploration normale. Sur un trial neuf sans historique de collecteur, il le
dit honnêtement et replie sur la liste des transactions critiques fournie par
le métier.

Les définitions canoniques vivent dans `.claude/agents/sap-*.md`. Les
slash-commands `/sap-plan`, `/sap-generate`, `/sap-heal` et `/sap-istqb`
(`.claude/commands/`) les enrobent pour Claude Code.

Les deux recorders émettent le même gabarit ISTQB en brouillon
(`--export-istqb` côté desktop, l'entrée « plan ISTQB » du menu export côté
web) : le rôle de sap-istqb est alors de RÉDIGER les rubriques de jugement
(objectif, périmètre, priorités, risques, traçabilité vers les specs et les
suites générées), jamais de dégrader l'observé. Ces documents sont de la
documentation de conception de test : ils ne remplacent jamais les suites
exécutables, et l'agent ne touche jamais `tests/robot/` ni `resources/`.

## Le cycle

```text
/sap-plan     consultation des données de vol via SE16 sur A4H
   └─> specs/sflight-consultation-se16.md        (relu/amendé par un humain)
/sap-generate specs/sflight-consultation-se16.md
   └─> tests/robot/sflight-consultation-se16.robot   (dry run + run live rapportés)
/sap-heal     tests/robot/sflight-consultation-se16.robot
   └─> localisateur corrigé dans resources/, suite verte (rapport avant → après)
```

Différence structurelle clé avec les agents Playwright : grâce à la
convention #1, le healer répare `resources/` (une ligne corrige toutes les
suites utilisant ce localisateur), pas les tests. Le corps d'un test ne
change que si le flux métier lui-même a changé, ce qui relève d'un passage
planner/generator, pas d'une réparation. Le healer lit aussi la télémétrie de
healing cumulative (`SAPFX_HEALING_LOG`) pour repérer les localisateurs qui
dérivent de façon récurrente et méritent une correction définitive.

Cette boucle de télémétrie est aussi automatisée sans agent :
`python scripts/healing_drift_report.py --log <journal>` agrège le JSONL,
sépare les dérives **stables** (même localisateur réparé plusieurs fois vers
LA même cible : le patch de `resources/` est localisé et proposé ; `--apply`
l'exécute) des **instables** (laissées à un humain ou à sap-healer), et sort
en code non nul quand des dérives existent, prêt pour un job CI planifié qui
ouvre une issue/PR. Même règle maison que le healer : il ne patche que
`resources/`, jamais les tests, jamais en silence.

## Le cycle de maintenance (`/sap-maintain`)

Les trois briques de maintenance (sentinelle de dérive, télémétrie de
healing, sap-healer) sont enchaînées par une commande orchestratrice,
`/sap-maintain` (`.claude/commands/sap-maintain.md`) : lancer la sentinelle
(`tests/robot/ecc_drift_sentinel.robot`), lire son rapport de dérives agrégé,
appliquer les patches de dérives *stables* proposés par
`healing_drift_report.py` (après présentation du diff), déléguer chaque dérive
restante ou suite rouge à l'agent sap-healer (un échec à la fois) et
produire UN rapport en français (dérives → réparations `avant → après` → ce
qui reste ouvert). Le cycle respecte les règles maison (ne patcher que
`resources/`, jamais en silence, fermer chaque session même sur échec) et
devient une assertion planifiée en relançant la sentinelle avec
`-v FAIL_ON_DRIFT:True`. Une variante CI totalement autonome exigerait un
système SAP joignable depuis le runner : sur le montage A4H-dans-Docker,
c'est une tâche planifiée locale, pas un job hébergé GitHub.

## Évaluer les agents eux-mêmes (`/sap-eval-healer`)

Modifier une définition d'agent ou la guidance rf-mcp sans filet de
régression, c'est laisser le comportement agentique pourrir en silence.
`scripts/agent_eval_harness.py` rend rejouable l'exercice en aveugle de la
0.3.0 : `inject` applique une dérive simulée connue à la couche resources
(sauvegarde octet à octet + empreintes de la surface protégée : les tests et
les autres resources), le sap-healer est ensuite lancé **en aveugle** (« cette
suite est rouge », rien de plus), et `verify` juge le résultat : dérive
réparée dans la couche resources, zéro modification des tests, état nettoyé
sur PASS (`restore` annule une éval interrompue). La commande
`/sap-eval-healer` déroule le protocole complet, préflight git propre et runs
rouge/vert de la suite autour de la réparation compris. Un verdict FAIL
s'accompagne du diagnostic à réinjecter dans `.claude/agents/sap-healer.md`
ou les hints : c'est tout l'intérêt.

## Pistes instruites (analysées le 2026-07-23, pas encore construites)

**Canal vision MCP natif.** Verdict : le contrat plugin de rf-mcp 0.31.2
(`LibraryStateProvider`) n'a **aucun canal image** : les state providers
retournent des dicts JSON, un screenshot traverse donc MCP en *texte* base64
que le modèle ne peut pas voir. La pile sous-jacente saurait le faire :
rf-mcp tourne sur fastmcp (3.4.2 ici), dont les outils peuvent retourner du
vrai contenu image MCP (`fastmcp.utilities.types.Image`), mais c'est une
**évolution upstream de rf-mcp** (un outil `get_screenshot` ou un hook
provider image), à proposer, pas quelque chose que les plugins peuvent
ajouter de l'extérieur. Praticable **dès aujourd'hui** sans rien changer :
les agents tournent dans Claude Code, dont l'outil `Read` rend les fichiers
PNG : `Take Screenshot` (fichier) + `Read` donne au planner/healer une vraie
vision des zones opaques. La pièce manquante pour la boucle Set-of-Mark
complète est une variante fichier de `Get Annotated Screenshot` (son dict ne
retourne le PNG annoté qu'en base64) : un petit keyword (sortie `path=`) à
ajouter quand le besoin sera confirmé.

**Garde de session lecture seule pour le planner.** Le contrat
consultation-seule du planner ne vit que dans son prompt ; un
`SAPFX_READONLY_SESSION=1` runtime (refus des vkeys de sauvegarde,
11/Ctrl+S, des menus contextuels de suppression, de `Post Odata`, des RFC
d'écriture) serait de la défense en profondeur, dans l'esprit de
`SAPFX_STRICT_COM_THREAD`. Difficulté honnête, et c'est pourquoi ce n'est pas
encore construit : la frontière lecture/écriture est floue. Remplir un écran
de sélection *est* une écriture d'UI et doit rester permis, la sémantique de
la transaction décide si F8 modifie quoi que ce soit, et une denylist qui se
ferait passer pour un bac à sable serait pire que le contrat documenté. Si
elle est construite, elle devra être présentée comme « bloque les gestes de
commit connus », jamais comme une frontière d'autorisation : les droits de
l'utilisateur SAP restent la vraie (voir les notes de sécurité de
[mcp-integration.fr.md](mcp-integration.fr.md)).

**Score de confiance de release (au-delà du diagnostic déjà fait par
sap-healer).** Piste identifiée en veille concurrentielle (2026-08-18,
Testsigma : pipeline agentique qui génère, exécute, répare, diagnostique les
tests puis score la confiance de la release). Le diagnostic existe déjà en
bonne partie : sap-healer classe chaque échec (dérive de localisateur / timing
/ données / changement fonctionnel) avant de réparer. Ce qui manque est
ailleurs : un indicateur agrégé de confiance au niveau d'une release (pas d'un
test), construit à partir de l'historique de healing (`SAPFX_HEALING_LOG`), de
la télémétrie de dérive (`healing_drift_report.py`) et des suites
rouges/vertes, pour répondre à « peut-on publier ». Cyril l'appelle le
« 5ᵉ agent » (après planner, generator, healer, istqb). Pas encore instruite :
pas d'analyse de faisabilité, pas de décision agent séparé vs extension de
`/sap-maintain` ou du rapport de `healing_drift_report.py`, qui agrège déjà
une partie de la matière brute.

`specs/sflight-consultation-se16.md` est le plan d'exemple de référence ; il
correspond au flux déjà validé live par `tests/robot/ecc_data_smoke.robot`.

## Une source, deux dialectes d'IDE

Les mêmes agents sont disponibles dans les deux piles IA de VS Code :

- **Claude Code** (CLI ou extension VS Code) lit `.claude/agents/` et
  `.claude/commands/`, plus la déclaration de serveur `.mcp.json`.
- **GitHub Copilot agent mode** lit les chat modes de `.github/chatmodes/`
  plus `.vscode/mcp.json`.

Les `.github/chatmodes/*.chatmode.md` sont **générés**, ne jamais les éditer
à la main :

```bash
python scripts/regen_agent_definitions.py           # régénérer après édition de .claude/agents/
python scripts/regen_agent_definitions.py --check   # garde CI/pytest (détection de dérive)
```

Le corps (les instructions) est copié tel quel ; seul le frontmatter change de
dialecte : les noms d'outils Claude Code deviennent les formes qualifiées
VS Code (`search/readFile`, `edit/editFiles`…), et les outils MCP gardent leur
granularité par outil en `rf-mcp-sap/<outil>`. C'est exactement le dialecte
émis par le générateur de référence de Playwright
(`packages/playwright/src/agents/generateAgents.ts`, la mécanique
`init-agents`). Même patron que
`regen_recorder` : une source, des cibles générées, un garde de cohérence
(`tests/unit/test_regen_agent_definitions.py` échoue si les chat modes sont
obsolètes).

## Dans le pack de déploiement Windows

`build_release_pack.py` embarque tout le système dans le pack :
`.claude/agents` + `.claude/commands`, les `.github/chatmodes` générés,
`specs/` (contrat + exemple de référence) et les deux gabarits MCP. Sur le PC
cible :

1. `install.cmd -WithMcp` installe les plugins et rend **les deux** configs
   IDE en place : `.mcp.json` (Claude Code) et `.vscode/mcp.json` (Copilot),
   plus `mcp.generated.json` à copier si l'agent tourne dans un autre projet.
2. Ouvrir le dossier du pack dans VS Code : les agents sont découverts
   immédiatement (approuver le serveur MCP projet à la première utilisation).
3. Règle propre au pack (encodée dans les définitions d'agents) : le generator
   et le healer ne modifient jamais les fichiers livrés par le pack : nouveaux
   keywords et surcharges de localisateurs vont dans
   `resources/site_keywords.resource`, si bien qu'une mise à jour du pack
   n'écrase jamais le travail local. Dans le dépôt source, ils enrichissent
   normalement `resources/` (convention #1).

## Règles et sécurité

- **Perception avant action** : les agents ne devinent jamais un écran ; ils
  le lisent (`Get Screen Signature` / `Get Ui5 Page Tree`, `mode=diff` en
  boucle).
- **Isolation des sessions** : l'état API/Fiori est partitionné par session
  rf-mcp ; les agents ECC utilisent une session live par process à cause des
  limites de contexte des resources imbriquées de rf-mcp 0.31.
- **Les agents détiennent les autorisations de l'utilisateur SAP**, ni plus,
  ni moins (voir les notes de sécurité de
  [mcp-integration.fr.md](mcp-integration.fr.md)). Les pointer vers des
  systèmes d'essai/test ; le planner est en consultation seule par contrat.
- **Jamais silencieux** : chaque réparation du healer est rapportée
  `avant → après` avec sa preuve live, en plus du WARN + journal de télémétrie
  du runtime.
- Les définitions portent les conventions du dépôt ; `check_guidance_sync.py`
  échoue si une définition d'agent cesse de les mentionner.

Voir aussi : [deployment-pack.fr.md](deployment-pack.fr.md) (parcours pack de
bout en bout) et [mcp-integration.fr.md](mcp-integration.fr.md) (plugins
rf-mcp).
