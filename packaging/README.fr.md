> [🇬🇧 English](README.md) · **🇫🇷 Français**

# Pack de déploiement SAPFX (Windows)

Pack de déploiement autonome pour un PC de test Windows. Il embarque tout le
nécessaire pour exécuter l'automatisation de tests SAP avec Robot Framework, sans
cloner le dépôt source :

| Contenu du pack | Rôle |
|---|---|
| `wheels/robotframework_sapfx-*.whl` | `SapEccLibrary` (SAP GUI desktop / ECC), `SapFioriLibrary` (web Fiori / UI5), `SapApiLibrary` (canal API : OData v2/v4, RFC optionnel) et `sapfx_common`, dans un seul wheel. |
| `wheels/sap_robotmcp-*.whl` | Plugins rf-mcp (RobotMCP) `SapEccPlugin` / `SapFioriPlugin` / `SapApiPlugin` (routage de keywords, perception SAP, guidance de sélecteurs), plus le **lanceur surcouche `sapfx-mcp`** (rf-mcp inchangé + outils `sapfx_state`/`sapfx_screenshot`/`sapfx_reload`, garde de compatibilité au démarrage). Optionnel (`-WithMcp`). |
| `resources/` | Keywords Robot Framework en langage métier (`ecc_keywords.resource`, `fiori_keywords.resource`, `a4h_demo_data.resource`). Les tests importent ces fichiers, jamais d'ids SAP bruts. |
| `tools/recorder/` + `recorder.cmd` | Recorder desktop (SAP GUI via COM) : dump / capture / survol / record ; le record utilise les événements natifs de l'API de scripting (boutons exacts) avec repli polling automatique. Double-cliquez `recorder.cmd` pour ouvrir le lanceur graphique, qui expose le choix du moteur (auto/native/poll) et le mode sémantique (keywords humains par libellé visible). |
| `tools/recorder_web/` | Recorder web : `recorder_snippet.js` (à coller dans DevTools) et `extension/` (extension Chrome MV3, à charger non empaquetée via `chrome://extensions`). |
| `tests/robot/` | Six suites d'exemple : smokes ECC/Fiori plus `fiori_wc_smoke.robot` déterministe et hors ligne, campagne d'exploration autonome, sentinelle de dérive et flagship cross-paradigme. |
| `scripts/` | Outillage de maintenance (stdlib pure, à lancer depuis la racine du pack) : `healing_drift_report.py` (relit la télémétrie de healing, propose, ou applique avec `--apply`, les patchs `resources/` des dérives stables de localisateurs) et `check_spec_sync.py` (échoue quand une suite générée est en retard sur son plan `specs/`). |
| `.claude/` + `.github/chatmodes/` + `specs/` | **Agents de test SAP** (sap-planner / sap-generator / sap-healer) : définitions d'agents + commandes `/sap-*` pour Claude Code, chat modes générés pour VS Code / Copilot, et le répertoire des plans de test avec son exemple de référence. Voir « Agents de test » plus bas. |
| `install.cmd` / `install.ps1` | Installateur : crée un `.venv` local, installe les wheels + dépendances épinglées, rend les configs MCP. |
| `mcp.json.template` / `vscode-mcp.json.template` | Gabarits de déclaration du serveur rf-mcp ; `install.ps1 -WithMcp` les rend en place en `.mcp.json` (Claude Code) et `.vscode/mcp.json` (VS Code / Copilot), plus `mcp.generated.json` à copier dans un autre projet. |
| `LICENSE` / `NOTICE` | Licence Apache-2.0 et attributions upstream, à conserver à côté des binaires. |

## Prérequis sur le PC cible

- **Windows 10/11**, **Python 3.10+** dans le `PATH` (`python` ou le lanceur `py`).
- Accès Internet **pendant l'installation** (pip télécharge Robot Framework,
  pywin32, robotframework-browser…). L'exécution ensuite peut être hors ligne
  (sauf suites visant des sites publics).
- Côté **ECC** : SAP GUI for Windows installé, scripting activé (côté client et
  côté serveur).
- Côté **Fiori** : soit lancer `install.cmd -WithBrowsers` (télécharge le Chromium
  de Playwright), soit utiliser le Chrome système
  (`New Browser    chromium    channel=chrome`, aucun téléchargement).

## Installation

```bat
install.cmd                 REM bibliothèques seules (ECC + Fiori)
install.cmd -WithMcp        REM + plugins rf-mcp (installe rf-mcp)
install.cmd -WithBrowsers   REM + Chromium Playwright (rfbrowser init)
install.cmd -WithMcp -WithBrowsers
```

L'installateur crée `.venv\` dans le dossier du pack, installe les wheels et
`requirements-deploy.txt` sous les versions qualifiées de
`constraints-deploy.txt`, exécute un smoke check d'import, et (avec `-WithMcp`)
rend les configs MCP avec le chemin absolu du lanceur `sapfx-mcp` du venv
(repli `robotmcp` sur un wheel plus ancien) :
`.mcp.json`, `.vscode\mcp.json` et `mcp.generated.json`.

## Validation

```bat
.venv\Scripts\robot.exe tests\robot\fiori_wc_smoke.robot
.venv\Scripts\robot.exe tests\robot\fiori_smoke.robot
.venv\Scripts\robot.exe -v SAP_CONNECTION:"..." -v SAP_USER:... -v "SAP_PASSWORD: Secret:..." tests\robot\ecc_smoke.robot
```

`fiori_wc_smoke.robot` est le contrôle d'installation déterministe hors ligne
(vrai Chromium, sans SAP ni réseau). `fiori_smoke.robot` s'exécute contre le Demo
Kit OpenUI5 public. `ecc_smoke.robot` demande un système SAP joignable et une entrée
`SAP_CONNECTION` présente dans le SAP Logon local. La forme `: Secret:` est la
syntaxe de variable typée de Robot Framework 7.4 : le mot de passe n'apparaît
jamais dans les logs, même en niveau TRACE.

## Intégrité de l'artefact

`SHA256SUMS.txt` couvre chaque fichier du pack. La release publie aussi
`sapfx-pack-<version>-win.zip.sha256`, un SBOM CycloneDX généré depuis
l'environnement installé proprement et une attestation GitHub de provenance du
ZIP. L'attestation est obligatoire sur un dépôt public et best-effort sur un
dépôt privé dont le plan GitHub peut ne pas l'exposer. Vérifier le hash sidecar
avant d'installer un artefact transféré.

## Préflights d'environnement (nouveau en 0.5.5)

Avant d'incriminer une suite au rouge, vérifiez la posture de l'environnement
de test : trois couples de keywords en lecture seule (tous dans
`SapEccLibrary`, indépendants de la langue) la contrôlent et *nomment le
réglage exact à corriger* :

- **Serveur** : `Scripting Should Be Fully Enabled` échoue tôt quand le
  système refuse ou restreint le scripting, en nommant le paramètre RZ11
  (`sapgui/user_scripting`, readonly, recording) et la voie par utilisateur
  (`user_scripting_per_user` + S_SCR) pour confiner le scripting aux comptes
  de test.
- **Rendu du poste** : `Abap List Should Be Readable` détecte les listes
  ABAP classiques rendues en shell opaque (sans labels) et nomme le mode
  accessibilité SAP GUI à provisionner sur le poste.
- **Sécurité du poste** : `Client Security Should Be Hardened` vérifie que
  le client SAP GUI est corrigé contre le chiffrement faible de l'historique
  de saisie (CVE-2025-0055, corrigé à partir de 8.00 PL9) et signale les
  bases d'historique `SAPHistory*.db` résiduelles à purger (les runs de test
  saisissent de vraies données dans de vrais champs).

La checklist complète (serveur, poste, web, confinement MCP) est
`docs/hardening-test-environment.md` dans le dépôt source, chaque point mappé
sur le préflight qui le vérifie.

## Utiliser les plugins MCP

Avec `-WithMcp`, le dossier du pack est prêt à servir d'espace de travail
agent : `.mcp.json` (Claude Code) et `.vscode/mcp.json` (VS Code / mode agent
Copilot) sont rendus en place : ouvrez le dossier dans VS Code et approuvez le
serveur `rf-mcp-sap` à la première utilisation. Si l'agent IA tourne dans un
**autre** projet, copiez-y `mcp.generated.json` en `.mcp.json`, ou
fusionnez-le dans le `.vscode/mcp.json` de ce projet. Aucun `PYTHONPATH` n'est
nécessaire : bibliothèques et plugins sont installés dans le venv et les
plugins s'enregistrent par entry points.

## Agents de test (plan → génération → réparation)

Le pack embarque les agents de test SAP (nécessite `-WithMcp`) :
**sap-planner** explore le système live via rf-mcp et écrit un plan de test
lisible métier dans `specs\` ; **sap-generator** transforme un plan en suite
Robot Framework dans `tests\robot\`, chaque étape vérifiée live avant d'être
écrite ; **sap-healer** répare une suite en échec en corrigeant la couche
resources, preuves live à l'appui. Côté Claude Code : commandes `/sap-plan`,
`/sap-generate` et `/sap-heal` ; côté VS Code / Copilot : chat modes du même
nom (`sap-planner`, `sap-generator`, `sap-healer`).

Le pack embarque aussi la **skill `sapfx`** (`.claude\skills\sapfx\`) : un
assistant Claude Code qui ouvre le dossier du pack apprend l'outillage en un
appel : les trois canaux, la boucle perception → action (carte numérotée
`Get Screen Map` + `Click/Fill Screen Ref`), les conventions non négociables
et le cycle agents. Aucune installation : la skill est détectée avec le
dossier.

Règle locale sur un pack déployé : les agents ne modifient jamais les fichiers
livrés par le pack : nouveaux keywords et surcharges de localisateurs vont
dans `resources\site_keywords.resource`, si bien qu'une mise à jour du pack
n'écrase jamais le travail local. Déroulé complet : `docs/test-agents.fr.md`
dans le dépôt source.

## Veille et maintenance

- **Sentinelle de dérive** (surveiller des écrans sans écrire un seul test) :

  ```bat
  .venv\Scripts\robot.exe -v SAP_CONNECTION:"..." -v SAP_USER:... -v "SAP_PASSWORD: Secret:..." tests\robot\ecc_drift_sentinel.robot
  ```

  Le premier passage enregistre la référence de chaque transaction surveillée
  dans `screen_watch\` (conservez ce dossier) : signature structurée,
  empreinte visuelle globale ET grille par tuile (`*.tiles.txt`, nouveau en
  0.5.2) ; chaque passage suivant ne remonte QUE ce qui a bougé, ligne à
  ligne, dans le log Robot : les ids renommés sont appariés
  (`~ ancien -> nouveau  (similarité N%)`) et une dérive visuelle locale est
  localisée à sa tuile (position, rectangle en pixels, éléments recouvrants).
  Surveiller un écran de plus = ajouter son tcode à
  `@{WATCHED_TRANSACTIONS}` ; `-v FAIL_ON_DRIFT:True` transforme le rapport
  en assertion.
- **Assertions visuelles** (Pillow, installé par `requirements-deploy.txt`) :
  `Screen Should Match Baseline` et `Element Should Match Baseline` (ECC ; la
  variante élément recadre la baseline sur UN contrôle : GuiShell opaques,
  graphiques) et `Ui5 Screen Should Match Baseline` (Fiori) partagent le même
  cycle snapshot : le premier passage enregistre la baseline PNG (à
  conserver), ensuite toute dérive fait échouer avec la distance de Hamming
  et sauve un `.actual.png` à côté ; `mask_elements=auto` neutralise les
  barres de statut et de titre volatiles avant hachage.
- **Télémétrie de healing → propositions de patch** : exécutez les suites avec
  `SAPFX_HEALING_LOG=<chemin>.jsonl` positionné, puis
  `.venv\Scripts\python.exe scripts\healing_drift_report.py --log <chemin>.jsonl`
  sépare les dérives stables de localisateurs (un patch `resources\` est
  localisé et proposé ; `--apply` l'exécute) des instables à examiner. Le code
  retour 1 signale la dérive, utilisable en alerte planifiée.
- **Le plan reste la source de vérité** : pour les suites générées par les
  agents, `.venv\Scripts\python.exe scripts\check_spec_sync.py` échoue quand
  un plan de `specs\` a changé après la génération de sa suite : repassez par
  `/sap-generate` au lieu d'éditer la suite à la main.

## Dépannage

- `ImportError: DLL load failed` sur `win32api` → exécuter une fois :
  `.venv\Scripts\python.exe .venv\Scripts\pywin32_postinstall.py -install`
- `robot` introuvable → toujours appeler les exécutables du venv
  (`.venv\Scripts\robot.exe`), l'installateur ne modifie pas le `PATH` global.
- SAP GUI « scripting support is disabled » → activer le scripting dans les
  options de SAP Logon et vérifier le paramètre profil `sapgui/user_scripting`
  côté serveur.

---
Ce pack est généré depuis le dépôt source par
`python scripts/build_release_pack.py` : ne modifiez pas ses fichiers sur place ;
corrigez le dépôt et regénérez. Déroulé complet de bout en bout (build →
transfert → installation → validation → MCP) : `docs/deployment-pack.fr.md`
dans le dépôt source.
