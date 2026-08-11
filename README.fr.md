> [🇬🇧 English](README.md) · **🇫🇷 Français**

<p align="center">
  <img src="https://raw.githubusercontent.com/CyrilM29/robotframework-sapfx/main/assets/logo.png" alt="SAPFX : ECC UI5 API Test Suite" width="240">
</p>

# SAPFX

[![PyPI](https://img.shields.io/pypi/v/robotframework-sapfx)](https://pypi.org/project/robotframework-sapfx/)
[![Python](https://img.shields.io/pypi/pyversions/robotframework-sapfx)](https://pypi.org/project/robotframework-sapfx/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](https://github.com/CyrilM29/robotframework-sapfx/blob/main/LICENSE)

```bash
pip install robotframework-sapfx
```

> PyPI livre les **bibliothèques** (les trois canaux ci-dessous). La **boîte à
> outils complète** (recorders, intégration rf-mcp/MCP, agents de test,
> resources métier) est livrée par le **pack de déploiement Windows** attaché
> à chaque [GitHub Release](https://github.com/CyrilM29/robotframework-sapfx/releases) ;
> voir [Installation](#installation).

SAPFX est une **solution d'automatisation de tests SAP** pour Robot Framework
(distribution `robotframework-sapfx`) : pas une simple librairie, mais un
ensemble d'outils conçus ensemble autour de toute la vie d'un test SAP :
écrire, enregistrer, générer, exécuter, réparer, surveiller. Son cœur : **un
vocabulaire métier unique pour trois canaux** :

- **`SapEccLibrary`** (phase 1) : client lourd SAP GUI (backend ECC, S/4HANA),
  un fork renforcé de
  [robotframework-sapguilibrary](https://github.com/frankvanderkuur/robotframework-sapguilibrary)
  (Apache 2.0), via COM.
- **`SapFioriLibrary`** (phase 2) : SAP Fiori / S/4HANA web (SAPUI5), via Playwright
  (bibliothèque Browser) avec des **sélecteurs de contrôles UI5 stables** (sans rotation
  d'identifiants dynamiques) : correspondance par rôle/propriété *et* un moteur
  **UI5 XPath** hiérarchique (`//Table//Button[@text='Edit']`), plus un **moteur
  WebGUI `sid`** pour les pages SAP GUI for HTML classiques et un **moteur Web
  Components** pour les pages `ui5-*` sans runtime UI5 classique. Le moteur de
  localisateurs est porté depuis
  [playwright-sap](https://github.com/ArpitSureka/playwright-sap) (Apache-2.0).
- **`SapApiLibrary`**, le canal API (stdlib pure) : OData **v2 et v4**
  derrière un seul jeu de keywords (protocole CSRF SAP compris), RFC optionnel
  via pyrfc. Préparer et recouper les données par l'API ; ne piloter l'écran
  que pour ce qu'on teste vraiment ; voir la suite flagship cross-paradigme
  (`tests/robot/flagship_cross_paradigm.robot` : compte SE16 == `$count` OData
  sur le même système vivant).

Un test se lit de la même façon quel que soit le canal utilisé. Voir
[docs/architecture.fr.md](docs/architecture.fr.md) et
[docs/fiori-architecture.fr.md](docs/fiori-architecture.fr.md).

📖 **[Documentation des keywords](https://cyrilm29.github.io/robotframework-sapfx/)**
(en anglais) : une page de référence par bibliothèque, chaque keyword avec ses
arguments et ses exemples.

![Démo live : un localisateur périmé réparé sur un vrai système SAP, jusqu'au patch resources/](https://raw.githubusercontent.com/CyrilM29/robotframework-sapfx/main/docs/media/healing-live.gif)

Tout ce qui précède est **réel** : écrans capturés sur un système live (A4H)
pendant que la bibliothèque le pilote, localisateur périmé réparé en plein run
(score 97 %), vrai comptage SE16, vrai rapport de dérive. Le point clé : le
healing n'est jamais silencieux. Un WARNING devient une télémétrie cumulée,
puis `scripts/healing_drift_report.py` **(pack)** localise le patch à faire dans
`resources/` sans modifier les tests métier.

https://github.com/user-attachments/assets/0a471849-30a9-47f5-a48c-7071b16be8fb

3 min 20 : VS Code et les keywords métier, puis SAP GUI, Fiori et le canal API
pilotés en direct, et un agent MCP qui génère une suite depuis une vraie session.

## Une solution, tout le cycle de vie du test

Les bibliothèques sont le cœur d'exécution. Autour, chaque besoin d'un projet
de test SAP a son outil dans la même boîte, avec partout le même vocabulaire
métier, les mêmes moteurs de localisation, les mêmes conventions :

> **Ce que livre chaque canal.** `pip install robotframework-sapfx` fournit les
> trois bibliothèques et tous les keywords documentés ci-dessous. Les éléments
> marqués **(pack)** ne sont pas des paquets Python : ils vivent dans ce dépôt
> et dans le pack de déploiement Windows. Voir [Installation](#installation)
> pour les deux canaux.

| Besoin | L'outil dans la boîte |
| --- | --- |
| Écrire des tests lisibles | les trois bibliothèques + la couche de keywords métier `resources/` **(pack)** : aucun id SAP brut dans les tests (convention tenue par la CI) |
| Capturer un déroulé existant | deux recorders **(pack)** : SAP GUI desktop (moteur d'événements natifs, lanceur graphique) et web Fiori/UI5 (extension Chrome MV3), avec exports resource-first, brouillons de spec et enregistrements rejouables |
| Générer et réparer les tests avec l'IA, sous contrôle | l'intégration rf-mcp (MCP) et les agents `plan → generate → heal` **(pack)** : chaque étape générée est exécutée en direct avant d'être écrite, et le healer patche `resources/`, jamais les tests |
| Surveiller des écrans sans écrire de scénario | la sentinelle de dérive : les keywords de perception et de baseline visuelle sont dans les bibliothèques, la suite de veille prête à l'emploi est **(pack)** |
| Anticiper la dérive des localisateurs | la télémétrie de healing (dans les bibliothèques) qui alimente `healing_drift_report.py` **(pack)**, lequel localise le correctif à faire dans `resources/` |
| Provisionner un poste de test | le pack de déploiement Windows : l'installation complète ([voir Installation](#installation)) |

C'est la vue d'ensemble qui compte : enregistrement, génération, exécution,
réparation et surveillance parlent les mêmes keywords métier ; ce que produit
un outil, les autres savent l'entretenir.

## Où ça se situe : wdi5 compris

[wdi5](https://github.com/ui5-community/wdi5) est la référence du test
end-to-end UI5 hors Robot Framework (projet de la communauté UI5, basé sur
WebdriverIO, activement maintenu). Ce projet n'est **pas** un remplaçant de
wdi5 et n'essaie pas de l'être. Le positionnement est autre : **le test SAP
dans Robot Framework**, où le client lourd SAP GUI, le canal API OData/RFC et
Fiori/UI5 partagent un même vocabulaire métier, un même runner et **un seul
rapport**.

- Votre stack est JS/WebdriverIO et votre périmètre une app UI5 → wdi5 est le
  choix naturel.
- Votre stack est Robot Framework, ou votre scénario traverse le client lourd,
  les API et Fiori dans le même run → c'est ce que fait ce projet.

Le détail dans [docs/fiori-architecture.fr.md](docs/fiori-architecture.fr.md)
(§ « Pourquoi pas Selenium / CSS brut / wdi5 »).

## Ce que ce fork ajoute par rapport à l'original

La bibliothèque originale constitue une base solide avec une bonne couverture de mots-clés
(y compris les grilles ALV). Ce fork conserve **tout** cela et ajoute ce dont
l'automatisation SAP en production a besoin (voir l'[audit](docs/audit-upstream.fr.md)
complet). Tout ce qui suit est un keyword fourni par
`pip install robotframework-sapfx`, sauf les éléments marqués **(pack)**, qui
sont des outils livrés avec le dépôt et le pack de déploiement Windows :

- **Synchronisation réelle** à la place des `sleep` fixes : `Wait Until Busy Done`,
  `Wait Until Element Present`, `Wait Until Element Value Is`.
- **Démarrage autonome** : `Open Sap Logon` lance le Logon Pad et attend
  le moteur de scripting ; `Connect To Session With Retry` ; `Close Sap Logon`.
- **`Run Transaction` indépendant de la locale** (lit le *type* du message de la barre
  d'état, non le texte en anglais/néerlandais/allemand) + `Status Message Should Be Success`.
- **Grilles ALV par titre de colonne** : `Get Cell Value By Column Title`, `Read Grid`
  (→ liste de dictionnaires), `Get Column Id By Title`.
- **Perception d'écran** : `Get Screen Signature` (ECC) et `Get Ui5 Page Tree`
  (Fiori) : une vue texte/XML en lecture seule de l'écran vivant, pour le débogage de
  localisateurs et l'intégration d'agents IA. Les deux supportent `mode=diff`
  (uniquement ce qui a changé depuis la perception précédente).
- **Préflight scripting & télémétrie** (ECC) : `Scripting Should Be Fully Enabled`
  échoue tôt avec le paramètre RZ11 exact à corriger ; `Enable Test Tool Mode`,
  `Get Session Telemetry`.
- **Réparation de localisateurs, jamais silencieuse** : les échecs suggèrent les
  ids les plus proches à l'écran (scorés) ; `Resolve Element With Healing` (ECC) et
  `Resolve Ui5 With Fallback` (Fiori : chaîne role→xpath→sid→wc) réparent un
  localisateur périmé avec un WARNING journalisé, en alimentant un journal de
  télémétrie opt-in (`SAPFX_HEALING_LOG`) que `scripts/healing_drift_report.py`
  transforme en maintenance préventive (dérives stables localisées dans
  `resources/`, patch proposé, `--apply` l'exécute).
- **Localisateurs humains** (ECC, portés de RoboSAPiens avec une politique plus
  stricte) : `Find/Fill/Read Field By Label`, `Click Button By Label` : libellé
  visible + géométrie, positions de grille (`N @ Libellé` / `Libellé @ N`),
  portée ancrée (`Ancre >> Reste`, rayon `scope_radius` ajustable) ;
  l'ambiguïté toujours remontée avec les candidats, jamais de premier match
  silencieux.
- **Assertions visuelles** (ECC) : `Screen Should Match Baseline` (dHash
  perceptuel sur captures en mémoire, sémantique snapshot) : la couverture
  pixels pour exactement ce que l'API Scripting ne voit pas (listes GuiShell
  opaques, graphiques record-only). Extra optionnel `visual` (Pillow).
- **Pont WebView2 embarqué** (ECC) : `Switch To Embedded Browser Page` confie
  un contrôle WebView2 embarqué dans une fenêtre SAP GUI/Business Client à la
  bibliothèque Browser via CDP : les deux canaux dans une même suite.
- **Iframes de launchpad & Fiori Elements** : `Set Ui5 Frame` pour les applications
  Work Zone/cFLP embarquées dans une iframe (cross-origin) ; sélecteurs stables
  `idSuffix=fe::…`. UI5 multi-versions : 1.60 → 2.0 nightly, prouvé en live.
- **Des enregistreurs (pack)**, pas de simples spies : bureau (`tools/recorder` :
  surbrillance, capture au clic, survol, `--record` produisant une séquence de
  mots-clés rejouable avec un **moteur natif à événements** (boutons/grilles/arbres
  exacts via les événements `Change` de l'API de scripting, repli polling
  automatique) ; lanceur Tkinter + `recorder.cmd` à la racine) et web
  (`tools/recorder_web` : snippet **et** extension Chrome MV3 qui exporte un corps
  `*** Test Cases ***`, avec assertions de valeur et support des iframes).
  Aucun traceur tiers.
- **Intégration rf-mcp (RobotMCP) (pack)** (`integrations/robotmcp/`) : `SapEccPlugin` /
  `SapFioriPlugin` se branchent sur le serveur
  [rf-mcp](https://github.com/manykarim/robotframework-mcp) : routage de mots-clés,
  guidance de sélecteurs SAP et perception d'écran en direct pour agents IA.
  Validée de bout en bout contre un système A4H vivant et une page UI5 vivante.

## Structure

```text
src/SapEccLibrary/          # phase 1 : client lourd SAP GUI (COM)
  _vendor/sapgui_base.py    #   original, vendorisé tel quel (classe renommée uniquement)
  keywords/_connection.py   #   mixin de démarrage (Logon Pad, retry, CoInitialize)
  keywords/_waits.py        #   mixin de synchronisation (+ suggestions d'ids proches)
  keywords/_grid.py         #   mixin d'ergonomie ALV
  keywords/_perception.py   #   Get Screen Signature (mode=diff) + captures
                            #   + assertions visuelles (baselines par hash perceptuel)
  keywords/_diagnostics.py  #   préflight scripting + TestToolMode + télémétrie
  keywords/_healing.py      #   Resolve Element With Healing (journalisé, jamais silencieux)
  keywords/_semantic.py     #   localisateurs humains (libellé + géométrie, grilles, portée >>)
  keywords/_embedded_browser.py  # pont WebView2/CDP vers la bibliothèque Browser
  SapEccLibrary.py          #   les compose + Run Transaction sécurisé pour la locale
src/SapFioriLibrary/        # phase 2 : Fiori / S/4HANA web (Playwright + UI5)
  _ui5_runtime.py           #   modèle de sélecteurs de contrôles UI5 (données pures)
  _ui5_js.py                #   bundle __SAPFX injecté : arbre, moteurs XPath/rôle, sid
  regen_recorder.py         #   régénère l'enregistreur web (snippet + extension)
  SapFioriLibrary.py        #   résout les sélecteurs UI5 via la page Browser
                            #   (+ Set Ui5 Frame, Resolve Ui5 With Fallback, idSuffix)
src/SapApiLibrary/          # canal API : OData v2/v4 + CSRF, RFC optionnel (stdlib pure)
src/sapfx_common/           # primitives partagées : sondage/relance, sûreté COM,
                            #   scoring + télémétrie de réparation, diff de perception,
                            #   arbre d'objets, moteur sémantique, hash visuel
resources/                  # mots-clés métier : ecc_keywords + fiori_keywords (en miroir)
                            # + a4h_demo_data (garanties de données SFLIGHT/EPM)
tests/unit/                 # tests de logique hors SAP/hors navigateur (exécutables partout)
tests/robot/                # ecc_smoke + ecc_data_smoke + ecc_exploration (nécessitent SAP),
                            # fiori_smoke (OpenUI5 Demo Kit), fiori_sflight_smoke
                            # (cap-sflight local), smokes de compat (UI5 1.60 legacy,
                            # UI5 2.0 nightly, iframes cross-origin)
                            # + smokes des enregistreurs (moteur record bureau, mode record web)
                            # + flagship_cross_paradigm (recoupements GUI ↔ API ↔ Fiori)
tools/recorder/             # enregistreur bureau (arbre d'objets SAP GUI, lanceur GUI,
                            # moteur record natif à événements avec repli polling)
tools/recorder_web/         # enregistreur web : snippet + extension Chrome MV3
integrations/robotmcp/      # plugins rf-mcp : routage de mots-clés + perception d'écran SAP
packaging/ + scripts/       # sources du pack de déploiement Windows + outillage du dépôt
                            # (build_release_pack.py -> dist/sapfx-pack-<v>-win.zip)
docs/                       # architecture, fiori-architecture, mcp-integration,
                            # audit-upstream, testing-without-sap, ecc-validation,
                            # sap-test-data, deployment-pack (tous bilingues EN/FR)
```

## Installation

Deux canaux de distribution, par choix :

**Bibliothèques seules : PyPI.** Les quatre paquets Python (`SapEccLibrary`,
`SapFioriLibrary`, `SapApiLibrary`, `sapfx_common`), pour utiliser les keywords
dans votre propre projet Robot Framework :

```bash
pip install robotframework-sapfx           # + extras : [web] Browser, [visual] Pillow
rfbrowser init                             # unique : navigateurs Playwright (côté Fiori)
```

Les recorders, les plugins rf-mcp/la surcouche `sapfx-mcp`, les resources
métier et les agents de test ne sont **pas** sur PyPI.

**Installation complète : le pack de déploiement Windows**
(`sapfx-pack-<version>-win.zip` attaché à chaque
[GitHub Release](https://github.com/CyrilM29/robotframework-sapfx/releases)).
C'est le **seul canal qui embarque tout** : les deux wheels (bibliothèques +
plugins rf-mcp avec le lanceur `sapfx-mcp`), la couche resources métier, les
deux recorders (GUI desktop + extension web MV3), les suites d'exemple, les
scripts de maintenance, les agents de test plan → generate → heal, et un
`install.cmd`/`install.ps1` qui construit un venv local et rend les configs
MCP. L'intégrité est vérifiable (sommes SHA-256 + SBOM CycloneDX + attestation
de provenance). Recommandé pour provisionner les postes de test cibles : le
code SAPFX arrive dans UN zip auditable ; à noter, l'installateur a toujours
besoin de Python et d'un accès à PyPI *ou à un miroir interne* pour les
dépendances épinglées. Guide complet :
[docs/deployment-pack.fr.md](docs/deployment-pack.fr.md).

**Depuis un clone de ce dépôt** (développement) :

```bash
pip install -r requirements.txt      # robotframework + pywin32 (épinglé, Windows) + browser
rfbrowser init                       # unique : téléchargement des navigateurs Playwright (côté Fiori)
```

Les prérequis côté SAP (scripting activé côté serveur/client) sont détaillés dans
[docs/testing-without-sap.fr.md](docs/testing-without-sap.fr.md), qui explique également
comment obtenir un **système SAP local gratuit** pour les tests (ABAP Platform Trial
sous Docker). Le côté Fiori ne nécessite aucun SAP : il effectue ses tests contre le
kit de démonstration public OpenUI5.

## Démarrage rapide

Les tests parlent le langage métier ; les identifiants d'éléments SAP restent dans la
couche resource (convention : **aucun id brut, aucun CSS/XPath dans les cas de test**) :

```robotframework
*** Settings ***
Resource    resources/ecc_keywords.resource
Suite Setup       Open SAP And Log In
Suite Teardown    Close SAP

*** Test Cases ***
Lire La Table Des Mandants Dans SE16
    Go To Transaction    SE16
    Display Table Contents    T000
    ${rows}=    Read Displayed Grid    max_rows=5
    Log    ${rows}

*** Variables ***
${SE16_TABLE_FIELD}    wnd[0]/usr/ctxtDATABROWSE-TABLENAME
${SE16_GRID}           wnd[0]/usr/cntlGRID1/shellcont/shell

*** Keywords ***
# Dans un vrai projet, ces mots-clés vivent dans resources/, à côté d'ecc_keywords.resource.
Display Table Contents
    [Arguments]    ${table}
    Input Text    ${SE16_TABLE_FIELD}    ${table}
    Send Vkey     0
    Send Vkey     8
    Wait Until Element Present    ${SE16_GRID}

Read Displayed Grid
    [Arguments]    ${max_rows}=5
    ${rows}=    Read Grid    ${SE16_GRID}    max_rows=${max_rows}
    RETURN    ${rows}
```

Exécution (contre un système, identifiants via des variables ; `Secret` est la
syntaxe de variable typée de Robot Framework 7.4 : le mot de passe n'apparaît
jamais dans les logs, même en niveau TRACE) :

```bash
robot -v SAP_CONNECTION:"MY SYSTEM" -v SAP_USER:DEVELOPER \
      -v "SAP_PASSWORD: Secret:secret" tests/robot/ecc_smoke.robot
robot tests/robot/fiori_smoke.robot   # Fiori : aucun SAP requis (OpenUI5 Demo Kit)
```

## Tests

```bash
python -m pytest tests/unit -q       # tests de logique, SAP non requis
```

## Licence

Apache 2.0. Contient du code vendorisé provenant de robotframework-sapguilibrary et des
moteurs de localisateurs portés depuis playwright-sap ; voir [LICENSE](LICENSE) et
[NOTICE](NOTICE).
