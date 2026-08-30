> [🇬🇧 English](README.md) · **🇫🇷 Français**

# Pack de déploiement SAPFX (Windows)

Pack de déploiement autonome pour un PC de test Windows. Il embarque tout le
nécessaire pour exécuter l'automatisation de tests SAP avec Robot Framework, sans
cloner le dépôt source :

| Contenu du pack | Rôle |
|---|---|
| `wheels/robotframework_sapfx-*.whl` | `SapEccLibrary` (SAP GUI desktop / ECC), `SapFioriLibrary` (web Fiori / UI5), `SapApiLibrary` (canal API : OData v2/v4, RFC optionnel) et `sapfx_common`, dans un seul wheel. |
| `wheels/sap_robotmcp-*.whl` | Plugins rf-mcp (RobotMCP) `SapEccPlugin` / `SapFioriPlugin` / `SapApiPlugin` (routage de keywords, perception SAP, guidance de sélecteurs), plus le **lanceur surcouche `sapfx-mcp`** (rf-mcp inchangé + outils `sapfx_state`/`sapfx_screenshot`/`sapfx_reload`, garde de compatibilité au démarrage). Optionnel (`-WithMcp`). |
| `resources/` | Keywords Robot Framework en langage métier, un vocabulaire en miroir par canal (`ecc_keywords`, `fiori_keywords`, `api_keywords`, `rfc_keywords`), plus les page objects et les garanties de données. **Des exemples à personnaliser**, relevés sur les systèmes du laboratoire du projet : réutilisables en bonne part, jamais faisant autorité, à vérifier sur votre cible et à adapter à votre métier (voir `resources/README.fr.md`). Les tests importent cette couche, jamais d'ids SAP bruts ; ce qui tient sur tout système SAP, c'est le wheel des bibliothèques, pas ce dossier. Vos propres keywords vont dans `resources\site_keywords.resource` (voir plus bas), qu'une mise à jour du pack n'écrase jamais. |
| `tools/recorder/` + `recorder.cmd` | Recorder desktop (SAP GUI via COM) : dump / capture / survol / record ; le record utilise les événements natifs de l'API de scripting (boutons exacts) avec repli polling automatique. Double-cliquez `recorder.cmd` pour ouvrir le lanceur graphique, qui expose le choix du moteur (auto/native/poll) et le mode sémantique (keywords humains par libellé visible). |
| `tools/recorder_web/` | Recorder web : `recorder_snippet.js` (à coller dans DevTools) et `extension/` (extension Chrome MV3, à charger non empaquetée via `chrome://extensions`). |
| `tests/robot/` | Sept suites d'exemple : smokes ECC/Fiori plus `fiori_wc_smoke.robot` déterministe et hors ligne, campagne d'exploration autonome, sentinelle de dérive, flagship cross-paradigme, et `api/canal_api_odata.robot` (le canal API pour lui-même, les mêmes mots-clés métier contre OData v2 avec `--include a4h` et v4 avec `--include capsflight`). |
| `scripts/` | Outillage de maintenance (stdlib pure, à lancer depuis la racine du pack) : `healing_drift_report.py` (relit la télémétrie de healing, propose, ou applique avec `--apply`, les patchs `resources/` des dérives stables de localisateurs) et `check_spec_sync.py` (échoue quand une suite générée est en retard sur son plan `specs/`). |
| `.claude/` + `.github/chatmodes/` + `specs/` | **Agents de test SAP** (sap-planner / sap-generator / sap-healer / sap-istqb) : définitions d'agents + commandes `/sap-*` pour Claude Code, chat modes générés pour VS Code / Copilot, et le répertoire des plans de test avec son exemple de référence (+ `specs/istqb/` pour les plans ISTQB). Voir « Agents de test » plus bas. |
| `install.cmd` / `install.ps1` | Installateur : crée un `.venv` local, installe les wheels + dépendances épinglées, rend les configs MCP. |
| `mcp.json.template` / `vscode-mcp.json.template` | Gabarits de déclaration du serveur rf-mcp ; `install.ps1 -WithMcp` les rend en place en `.mcp.json` (Claude Code) et `.vscode/mcp.json` (VS Code / Copilot), plus `mcp.generated.json` à copier dans un autre projet. |
| `LICENSE` / `NOTICE` | Licence Apache-2.0 et attributions upstream, à conserver à côté des binaires. |

## Ce que le pack contient, et ce qu'il ne contient pas

Le pack est un environnement d'**exécution**, pas une copie du dépôt source.
Ce qui en découle sur le poste :

- **Pas de `src/`** : les bibliothèques sont installées comme wheel dans le
  venv, donc on ne corrige pas leur code sur place. C'est la raison de la règle
  `resources\site_keywords.resource` (plus bas) : keywords ajoutés et
  surcharges de localisateurs y vont, et une mise à jour du pack ne les écrase
  pas. Un défaut de bibliothèque se signale en amont au lieu d'être contourné
  localement, sinon le même bug est payé deux fois.
- **Sept suites d'exemple**, pas la suite de validation complète du dépôt :
  elles servent de contrôle d'installation et de modèle à copier, pas de
  couverture.
- **Quatre scripts de maintenance** sur la quinzaine du dépôt : les autres sont
  des gardes de développement (appariement bilingue, dérive du vendor,
  cohérence des supports IA) sans objet hors du dépôt.
- **Aucun test unitaire** : ils s'exécutent en CI sur le dépôt source.

Ce qui est rigoureusement identique, en revanche, c'est le **code** des
bibliothèques : le wheel contient exactement `src/`, donc un keyword se
comporte ici comme sur le poste de développement.

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

## Canal RFC : optionnel, et non installé

`pip` n'installe pas `pyrfc`, et c'est délibéré : ce binding a besoin du
**runtime SAP NW RFC**, une bibliothèque C absente de PyPI. Son véhicule
officiel est le **SAP NW RFC SDK**, que SAP distribue sous licence depuis son
portail de téléchargement : aucun installateur ne peut donc le provisionner à
votre place.

Son absence ne casse rien : l'import se fait à l'intérieur du keyword, pas au
chargement du module. `SapApiLibrary` s'importe et fonctionne, et **tout le
canal OData** reste disponible (v2 et v4, `$batch`, protocole CSRF,
`$metadata`, catalogue, préflight Gateway, fabrique de données de test).

Six keywords seulement en dépendent : `Open Rfc Connection`, `Call Rfc`,
`Call Bapi`, `Commit Bapi Transaction`, `Rollback Bapi Transaction` et
`Wait For Background Job`. Les appeler sans `pyrfc` donne un échec de test
nommant la marche à suivre, jamais un `ModuleNotFoundError` au démarrage de la
suite.

### Si SAP Logon est installé, vous pouvez déjà faire des tests RFC (constaté le 2026-08-27)

À lire avant de partir en quête d'un S-user : **un poste qui fait tourner SAP
Logon porte déjà le runtime RFC.** Installer SAP GUI for Windows 8.00 installe
son composant « SAP NWRFC x64 Shared », qui dépose dans `C:\Windows\System32` un
`sapnwrfc.dll` (version 7530.1116 au relevé, variante kernel, release 750 patch
level 11) plus `icudt50.dll`, `icuin50.dll` et `icuuc50.dll`. Le loader Windows
les y trouve sans `SAPNWRFC_HOME` ni entrée de `PATH` : la roue précompilée de
`pyrfc` se charge, et un appel RFC **réel** passe. Mesuré contre une ABAP
Platform trial, `STFC_CONNECTION` a renvoyé son écho et `RFC_READ_TABLE` a lu
T000 à travers `Open Rfc Connection` / `Call Rfc`.

En pratique cela couvre le cas courant, puisqu'un poste qui teste le canal ECC a
SAP GUI par définition. Une commande vous situe, pour moins cher qu'un portail
de téléchargement :

```bat
REM aucune archive, aucun S-user : le runtime déjà installé par SAP GUI
powershell -ExecutionPolicy Bypass -File install-rfc.ps1 -UseSapGuiRuntime
```

Elle refuse proprement si le runtime n'est pas là (pas de SAP GUI sur ce poste),
installe le `pyrfc` épinglé dans le venv du pack et contrôle l'import pour de
vrai. Un import n'est toujours pas une connexion : confirmer par un appel RFC
réel avant de conclure. `install-rfc.ps1 -CheckOnly` rapporte cette
configuration pour ce qu'elle est, au lieu de déclarer le SDK manquant.

**Cela dit, le SDK reste le but à viser**, et ce raccourci est ce qui vous
débloque en attendant, pas ce qui le remplace. Trois raisons, par ordre de
rapidité à vous rattraper :

- **C'est la seule voie hors de ce poste.** Un runner de CI, un agent de build
  ou la machine d'un collègue sans SAP GUI n'ont aucun runtime. Tout ce qui doit
  s'exécuter ailleurs demande le SDK, et l'anticiper évite de le découvrir le
  jour où un pipeline doit passer au vert.
- **Licence et support.** Cette DLL est livrée avec le client SAP GUI, pour le
  client. L'artefact que SAP supporte pour le développement RFC, ses versions et
  ses correctifs, c'est le SDK : un ticket de support demandera lequel est
  installé.
- **Un patch level subi, et pas de compilation.** Vous prenez celui du client,
  et une incompatibilité avec `pyrfc` ne se verrait pas à l'import, seulement à
  l'usage. Sur un Python sans roue précompilée (3.13 et au-delà), compiler exige
  les en-têtes du SDK, que le client ne fournit pas.

Une contrainte que le raccourci ne lève **pas** : l'interpréteur. Aucune roue
`pyrfc` précompilée n'existe au-delà de Python 3.12, donc le venv se crée en
3.10 à 3.12, que vous ayez le SDK ou non.

### Procédure de provisionnement (une fois par poste)

1. **Récupérer l'archive.** SAP for Me, rubrique Software Downloads : il faut un
   S-user portant l'autorisation « Software Download », donc un contrat client
   ou partenaire. Chercher `SAP NW RFC SDK 7.50`, plateforme *Windows on x64
   64bit*. La note SAP **2573790** fait référence pour la disponibilité, les
   plateformes supportées et les patch levels.
2. **Prérequis Windows.** Installer le *Visual C++ Redistributable for Visual
   Studio 2013* (x64) : la bibliothèque C en dépend à l'exécution, et son
   absence produit une erreur de chargement de DLL, pas un message clair.
3. **Décompresser** l'archive, par exemple dans `C:\nwrfcsdk`, de sorte que
   `C:\nwrfcsdk\lib` existe.
4. **Déclarer les variables d'environnement** : `SAPNWRFC_HOME=C:\nwrfcsdk`, et
   ajouter `C:\nwrfcsdk\lib` au `PATH` (c'est par là que les DLL sont trouvées
   à l'exécution).
5. **Installer le binding** dans le venv du pack :
   `.venv\Scripts\python.exe -m pip install pyrfc==3.3.1`
6. **Vérifier** :
   `.venv\Scripts\python.exe -c "from pyrfc import Connection; print('pyrfc OK')"`

Les étapes 2 à 6 sont scriptées par `install-rfc.ps1` (voir plus bas).

### État amont, à connaître avant de s'engager (constaté le 2026-08-26)

- SAP a **archivé** le dépôt PyRFC le 2026-05-28 : le projet n'est plus
  maintenu et aucun remplaçant officiel n'est annoncé.
- **Toutes les versions publiées sur PyPI sont « yanked »** : pip ne les
  sélectionne plus tout seul, d'où la version épinglée exacte à l'étape 5.
- Les **roues précompilées Windows s'arrêtent à Python 3.12**. Sur un venv en
  3.13 ou 3.14, pip tenterait une compilation depuis les sources (Cython plus
  les Build Tools MSVC). Si le canal RFC vous est indispensable, créez le venv
  du pack avec un interpréteur **3.10 à 3.12**, choix qui se fait au moment de
  l'installation et pas après.
- La dernière version est construite contre un patch level du SDK que SAP ne
  supporte plus.

Rien de tout cela ne concerne le canal OData, qui reste le chemin nominal.

### Automatiser ce provisionnement

`install-rfc.ps1` scripte tout **sauf** l'obtention de l'archive :

```bat
REM l'archive est déjà sur le poste (ou sur un partage)
powershell -ExecutionPolicy Bypass -File install-rfc.ps1 -SdkZip C:\downloads\nwrfc750P_13-70002755.zip

REM ou tirée du miroir interne de l'entreprise
powershell -ExecutionPolicy Bypass -File install-rfc.ps1 -SdkUrl https://artefacts.interne/sap/nwrfc750.zip -SdkUrlToken $env:ARTIFACTS_TOKEN

REM ou aucune archive du tout, sur un poste qui fait tourner SAP Logon
powershell -ExecutionPolicy Bypass -File install-rfc.ps1 -UseSapGuiRuntime
```

Il décompresse dans `-SdkHome` (défaut `C:\nwrfcsdk`), pose `SAPNWRFC_HOME` et
le `PATH` de l'utilisateur, installe le `pyrfc` épinglé dans le venv du pack et
exécute un vrai contrôle d'import. `-Machine` écrit les variables pour toute la
machine (shell élevé requis), `-CheckOnly` diagnostique une installation
existante sans rien modifier.

`-UseSapGuiRuntime` est le mode sans archive décrit plus haut : il s'appuie sur
le runtime RFC installé par le client SAP GUI, donc ne touche aucune variable
d'environnement (les DLL sont dans `System32`, que le loader lit de toute
façon), installe le binding et contrôle l'import. Il refuse si aucun runtime
n'est là, et refuse d'être combiné à `-SdkZip`, `-SdkUrl` ou `-SkipPyrfc`
plutôt que d'ignorer en silence la moitié de la demande. À utiliser pour
travailler dès aujourd'hui, en gardant le SDK comme cible : ce mode n'est vrai
que de **ce** poste.

Le **téléchargement**, lui, ne peut pas être anonyme : le portail exige un S-user et
la licence interdit de redistribuer l'archive, donc elle ne sera jamais dans le
pack ni dans un dépôt public. Deux voies praticables, dans cet ordre :

1. **Miroir interne** (recommandé) : télécharger l'archive une fois à la main,
   la déposer dans le dépôt d'artefacts de l'entreprise (Artifactory, Nexus,
   Azure Artifacts, partage interne), et pointer `-SdkUrl` dessus.
2. **Téléchargement direct authentifié** : les URL `softwaredownloads.sap.com`
   acceptent une authentification basique S-user (`curl -u` / `wget`), pratique
   courante mais non contractuelle : l'outil supporté reste le SAP Download
   Manager, et les identifiants doivent vivre en secrets d'usine, jamais dans
   un script versionné (convention 11 du dépôt source).

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
resources, preuves live à l'appui ; **sap-istqb** (hors ligne, sans MCP)
transforme les plans du planner et les sorties des recorders en plan de test
+ cas de test ISTQB sous `specs\istqb\` (lisible par un humain, rejouable par
une IA quel que soit le framework via ses blocs replay normalisés ; les deux
recorders émettent le même gabarit en brouillon : `--export-istqb` côté
desktop, entrée « plan ISTQB » du menu export côté web). Côté Claude Code :
commandes `/sap-plan`, `/sap-generate`, `/sap-heal` et `/sap-istqb` ; côté
VS Code / Copilot : chat modes du même nom (`sap-planner`, `sap-generator`,
`sap-healer`, `sap-istqb`).

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
  en assertion. Les références visuelles suivent la géométrie de capture :
  `${PER_RESOLUTION}` vaut `True` dans cette suite, si bien qu'une résolution
  d'écran encore inconnue **enregistre** sa référence visuelle et ne compare
  que le structurel ce passage-là, au lieu de crier à la dérive.
- **Assertions visuelles** (Pillow, installé par `requirements-deploy.txt`) :
  `Screen Should Match Baseline` et `Element Should Match Baseline` (ECC ; la
  variante élément recadre la baseline sur UN contrôle : GuiShell opaques,
  graphiques) et `Ui5 Screen Should Match Baseline` (Fiori) partagent le même
  cycle snapshot : le premier passage enregistre la baseline PNG (à
  conserver), ensuite toute dérive fait échouer avec la distance de Hamming
  et sauve un `.actual.png` à côté ; `mask_elements=auto` neutralise les
  barres de statut et de titre volatiles avant hachage.
  **Une empreinte encode la géométrie de capture autant que le contenu** :
  des baselines venues d'un autre poste échouent donc sur une simple
  différence de résolution d'écran, sans qu'aucun écran ait bougé. Les
  enregistrer sur le poste qui les rejouera, ou passer `per_resolution=True`
  pour garder une baseline par géométrie (`<nom>@1920x1032.png`, créée au
  premier passage du poste comme n'importe quelle première baseline) ; quand
  les deux géométries diffèrent, le message d'échec le dit et liste celles
  déjà connues.
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
- `Call Rfc a besoin de pyrfc (et du SAP NW RFC SDK)` → attendu : voir
  « Canal RFC » plus haut. Les keywords OData n'en ont pas besoin.
- Un `dev_rfc.log` apparaît à côté de votre suite → normal : la bibliothèque
  NW RFC écrit sa trace dans le répertoire COURANT quand une connexion échoue.
  La lire (elle nomme le runtime RFC chargé), puis la supprimer.
- Une assertion visuelle échoue au premier run sur un poste neuf → vérifier
  d'abord la résolution d'écran : voir la note de géométrie dans « Veille et
  maintenance ».

---
Ce pack est généré depuis le dépôt source par
`python scripts/build_release_pack.py` : ne modifiez pas ses fichiers sur place ;
corrigez le dépôt et regénérez. Déroulé complet de bout en bout (build →
transfert → installation → validation → MCP) : `docs/deployment-pack.fr.md`
dans le dépôt source.
