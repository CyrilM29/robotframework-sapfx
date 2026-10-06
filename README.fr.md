> [🇬🇧 English](README.md) · **🇫🇷 Français**

<p align="center">
  <img src="https://raw.githubusercontent.com/CyrilM29/robotframework-sapfx/main/assets/logo-library.png" alt="SAPFX : ECC UI5 API Library" width="240">
</p>

# SAPFX : bibliothèques Robot Framework pour tester SAP

[![PyPI](https://img.shields.io/pypi/v/robotframework-sapfx)](https://pypi.org/project/robotframework-sapfx/)
[![Python](https://img.shields.io/pypi/pyversions/robotframework-sapfx)](https://pypi.org/project/robotframework-sapfx/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](https://github.com/CyrilM29/robotframework-sapfx/blob/main/LICENSE)

```bash
pip install robotframework-sapfx
```

SAPFX automatise les tests SAP dans Robot Framework avec **trois bibliothèques,
une par canal** : le client lourd SAP GUI, les applications SAP Fiori et SAPUI5
dans le navigateur, et le canal API OData/RFC. Chacune garde les localisateurs
de sa technologie (un id de scripting SAP GUI, un sélecteur de contrôle UI5, un
entity set OData) ; elles partagent **les mêmes contrats et la même méthode** :
une seule règle de complétude pour extraire un tableau, qu'il vienne d'une
grille ALV, d'une table UI5 ou d'un appel RFC ; une même identité de message
(`MO/E/402`) à l'écran et en RFC ; et, sur les deux canaux à écran, la même
boucle perception → action et un même journal de réparation des localisateurs.
Le vocabulaire métier se construit au-dessus, dans les keywords Robot Framework
de votre projet : c'est là qu'un test cesse de dépendre du canal. Un même run
peut traverser les trois
(préparer les données par l'API, piloter l'écran pour ce qu'on teste vraiment,
vérifier le résultat par un autre canal). Comme elles savent aussi écrire,
supprimer et recouper leurs propres écritures par deux canaux, les mêmes
bibliothèques s'ouvrent au-delà du test, vers les jeux de données, les bases à
garnir et les chargements contrôlés (voir « Au-delà du test »
plus bas pour ce qui est prouvé et ce qui ne l'est pas encore).

Ce dépôt publie les **sources des bibliothèques**, leur **documentation** et la
**référence des keywords**. Les bibliothèques sont distribuées sur PyPI sous le
nom `robotframework-sapfx`.

| Bibliothèque | Canal | Pilotée par |
| --- | --- | --- |
| **`SapEccLibrary`** | SAP GUI for Windows (backend ECC, S/4HANA) | L'API SAP GUI Scripting via COM (`pywin32`). Compatible sans changement avec [robotframework-sapguilibrary](https://github.com/frankvanderkuur/robotframework-sapguilibrary) : chacun de ses keywords garde son nom et sa signature, quelques-uns échouent désormais franchement là où elle rendait une valeur trompeuse. |
| **`SapFioriLibrary`** | SAP Fiori / SAPUI5, UI5 Web Components, SAP GUI for HTML | La [bibliothèque Browser](https://github.com/MarketSquare/robotframework-browser) (Playwright), avec des **sélecteurs de contrôles UI5 stables** au lieu des ids DOM générés. Moteur de localisateurs porté de [playwright-sap](https://github.com/ArpitSureka/playwright-sap). |
| **`SapApiLibrary`** | OData v2 et v4, RFC / BAPI | La bibliothèque standard Python pour HTTP (protocole CSRF SAP compris) ; RFC optionnel via `pyrfc`. |

Un quatrième paquet, `sapfx_common`, porte la logique pure que les trois
partagent (attente, scores de réparation, diff de perception, moteur de
localisateurs humains, contrat d'extraction de tableaux, empreinte visuelle...). Certains de ses
modules sont des bibliothèques Robot à part entière, documentées dans leurs
docstrings et non dans la référence des keywords :
`Library    sapfx_common.table_csv` (aussi `table_json`, `table_xlsx`,
`table_svg`, `table_parquet`) écrit une extraction et la relit,
`sapfx_common.table_extract` porte la garde commune
`Table Extract Should Be Complete`, `sapfx_common.artifacts` écrit et relit
des artefacts JSON déterministes, et `sapfx_common.rap_preview` construit le
chemin de l'aperçu Fiori Elements d'un service RAP.

📖 **[Documentation des keywords](https://cyrilm29.github.io/robotframework-sapfx/)**
(en anglais) : une page de référence par bibliothèque, chaque keyword avec ses
arguments et ses exemples.

## Installation

```bash
pip install robotframework-sapfx            # les trois bibliothèques
pip install "robotframework-sapfx[web]"     # + bibliothèque Browser, pour SapFioriLibrary
rfbrowser init                              # une fois : navigateurs Playwright
```

Autres extras : `visual` (Pillow, pour les baselines d'écran) et `parquet`
(pyarrow, pour les exports Parquet). Prérequis par canal :

- **Tous** : Python 3.10 ou plus, Robot Framework 7.4 ou plus.
- **`SapEccLibrary`** : Windows, SAP GUI for Windows, et le scripting activé
  côté serveur (RZ11 `sapgui/user_scripting`) et côté client.
  `Scripting Should Be Fully Enabled` vérifie les deux et nomme le paramètre à
  corriger. Épinglez `pywin32` exactement dans votre fichier d'environnement :
  c'est la première source de casse COM.
- **`SapFioriLibrary`** : l'extra `web` et `rfbrowser init`. Aucun système SAP
  n'est nécessaire pour l'essayer : l'OpenUI5 Demo Kit public est une cible
  valable.
- **Le RFC de `SapApiLibrary`** (optionnel) : `pyrfc`, épinglé
  (`pip install pyrfc==3.3.1` : SAP a archivé le projet et toutes ses versions
  PyPI sont retirées, donc pip n'en choisit plus aucune seul ; roues
  précompilées jusqu'à Python 3.12 seulement), et le runtime SAP NW RFC, qu'une
  installation de SAP GUI for Windows 8.00 fournit en général déjà (composant
  « SAP NWRFC x64 Shared »). Sans lui, les keywords RFC le disent et le reste
  de la bibliothèque fonctionne.

Un système SAP local et gratuit pour s'exercer (ABAP Platform Trial sous
Docker), ainsi que les prérequis côté SAP, sont décrits dans
[docs/testing-without-sap.fr.md](docs/testing-without-sap.fr.md).

## Démarrage rapide

**SAP GUI** (identifiants en ligne de commande :
`robot -v "PASSWORD: Secret:..." suite.robot` ; la variable typée de Robot
Framework 7.4 garde le mot de passe hors des journaux, même en niveau TRACE) :

```robotframework
*** Settings ***
Library    SapEccLibrary

*** Variables ***
${CONNECTION}    MY SYSTEM
${USER}          DEVELOPER
${PASSWORD}      ${EMPTY}
${GRID}          wnd[0]/usr/cntlGRID1/shellcont/shell

*** Test Cases ***
Read The Clients Table In SE16
    Open Sap Logon
    Connect To Session With Retry
    Open Connection    ${CONNECTION}
    Input Text        wnd[0]/usr/txtRSYST-BNAME    ${USER}
    Input Password    wnd[0]/usr/pwdRSYST-BCODE    ${PASSWORD}
    Send Vkey    0
    Scripting Should Be Fully Enabled
    Use ALV Grid In Data Browser
    Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000
    Send Vkey    0
    Send Vkey    8
    ${rows}=    Read Full Grid    ${GRID}
    Log    ${rows}
```

Dans un vrai projet, les ids des éléments SAP vivent dans un fichier de
resources de keywords métier, et les cas de test ne parlent que le langage
métier.

**SAP Fiori / SAPUI5** (tourne tel quel sur l'OpenUI5 Demo Kit public) :

```robotframework
*** Settings ***
Library    Browser
Library    SapFioriLibrary    ui5_timeout=20s

*** Test Cases ***
Search The API Reference
    New Browser    chromium    headless=True
    New Page       https://sdk.openui5.org/#/api
    Fill Ui5 Input    Button    controlType=SearchField
    ${xpath}=    Get Ui5 Xpath    controlType=SearchField
    Log    ${xpath}
    [Teardown]    Close Browser
```

**OData** (un service SAP Gateway, ici la boutique de démonstration EPM de
l'image trial ABAP) :

```robotframework
*** Settings ***
Library    SapApiLibrary

*** Variables ***
${PASSWORD}    ${EMPTY}

*** Test Cases ***
Count The Products
    Open Api Session    http://localhost:50000    user=DEVELOPER
    ...                 password=${PASSWORD}    sap_client=001
    ${count}=    Get Odata Count    /sap/opu/odata/sap/SEPMRA_SHOP/Products
    Should Be True    ${count} > 0
    ${first}=    Get Odata Entities    /sap/opu/odata/sap/SEPMRA_SHOP/Products    top=3
    Length Should Be    ${first}    3
    [Teardown]    Close All Api Sessions
```

## Ce que les bibliothèques apportent

- **Une vraie synchronisation**, jamais d'attente fixe : `Wait Until Busy Done`,
  `Wait Until Element Present` (SAP GUI), `Wait For Ui5 Idle` (réseau,
  indicateurs d'occupation et période de calme continue, sur les pages UI5 et
  non UI5).
- **Des assertions indépendantes de la langue** : `Run Transaction` juge le
  **type** du message de la barre de statut, jamais son texte traduit ;
  `Get Status Message Identity` lit classe, type et numéro ;
  `Ui5 Should Have No Messages Of Type` fait de même côté web. Dates et
  nombres se saisissent au format de l'utilisateur (`Input Date`,
  `Input Number`, `Fill Ui5 Date`), et le mode affichage ou modification d'un
  écran se lit sur un champ (`Element Should Be Changeable`), jamais sur son
  titre traduit.
- **Des tableaux lus comme des données** : grilles ALV par titre de colonne
  (`Read Grid`, `Read Full Grid`, `Get Grid Column Titles`), table controls,
  arbres, listes ABAP classiques, tables UI5 et grilles SAP GUI for HTML ; un
  seul contrat d'extraction pour tous les canaux, qui refuse une lecture
  partielle au lieu de la faire passer pour complète, et cinq formats d'export
  (CSV, JSON Lines, XLSX, SVG, Parquet).
- **Des localisateurs humains** (SAP GUI) : `Fill Field By Label`,
  `Click Button By Label`, `Read Field By Label`, par libellé visible et
  géométrie ; une ambiguïté est toujours remontée avec ses candidats, jamais
  tranchée par un premier résultat silencieux.
- **Cinq moteurs de résolution côté web** : UI5 `role` et `xpath`
  hiérarchique (`//Table//Button[@text='Edit']`), `sid` pour SAP GUI for HTML,
  `wc` pour les pages UI5 Web Components sans runtime classique, et `dom` (rôle
  ARIA et nom accessible) pour les zones non SAP des pages hybrides ; les
  iframes imbriquées des launchpads par une pile de frames ;
  `Get Page Composition` dit quelle technologie vit où.
- **Une réparation de localisateurs jamais silencieuse** : les échecs listent
  les ids les plus proches à l'écran, avec leur score ;
  `Resolve Element With Healing` et `Resolve Ui5 With Fallback` réparent un
  localisateur périmé avec un avertissement journalisé et un journal de
  télémétrie optionnel.
- **La perception de l'écran**, pour le débogage et les agents IA :
  `Get Screen Signature`, `Get Screen Map` (cibles actionnables numérotées),
  `Get Ui5 Page Tree`, mode différentiel, captures annotées.
- **Des assertions visuelles** là où l'API Scripting ne voit rien (shells
  opaques, graphiques) : baselines par empreinte perceptuelle, par écran, par
  élément ou par tuile.
- **Des préflights qui nomment leur remède** : scripting côté serveur et
  client, posture de sécurité du poste, activation de la Gateway,
  disponibilité du canal RFC ; et la configuration de sécurité du serveur ABAP
  lue par RFC (paramètres de profil jugés sur leur code de retour, dérive
  confrontée à une référence committée).
- **Le canal API comme plateforme de données** : CRUD OData complet avec CSRF,
  `$batch`, pagination pilotée par le serveur, perception du `$metadata` avec
  les libellés humains, une fabrique de données de test qui nettoie derrière
  elle, BAPI jugées par type de message et refus assertés par identifiant de
  message, lectures de tables RFC, jobs de fond et leur spool, IDocs sortants
  (création, attente sur le code de statut, lien avec l'IDoc entrant par son
  TID), documents de modification.
- **Plusieurs sessions SAP GUI** par alias dans une même suite, la navigation
  dans le launchpad SAP Fiori par intent et la connexion par un fournisseur
  d'identité, les compteurs de tuiles lus comme des nombres
  (`Get Flp Tile Counter`), et des lectures d'identité (release, kernel,
  mandant ; par HTTP seul avec `Get Abap Software Components`) qui prouvent à
  quel système un test parle réellement.

Les équipes qui testent des applications UI5 avec un outillage JavaScript
connaissent [wdi5](https://github.com/ui5-community/wdi5),
la référence hors de Robot Framework. SAPFX ne le remplace pas : son périmètre
est l'automatisation de tests SAP dans Robot Framework, où le client lourd, le
canal API et Fiori partagent un exécuteur, un rapport et les mêmes contrats.

## Au-delà du test

Les bibliothèques ont été conçues pour tester SAP, et cela reste leur cœur. Ce
qui rend un test fiable (écrire une donnée par un canal, la relire par un autre
canal indépendant, la supprimer et constater qu'elle a disparu) fonctionne aussi
en dehors d'un test. Trois usages en découlent :

- **Jeux de données de test** : créer des jeux complets et cohérents,
  identifiables comme données de test, pour alimenter les campagnes.
- **Garnir des bases pour les tests de performance** : peupler des bases SAP
  vides ou incomplètes avant une campagne de charge.
- **Chargements de paramétrage et de migration** : charger des données métier
  complexes dans un environnement cible, et contrôler le chargement par un
  second canal, par exemple dans une migration d'ECC vers S/4HANA.

Pour être précis sur l'état : l'écriture, la suppression et le contrôle croisé
par deux canaux sont validés en direct sur des systèmes SAP de développement,
jamais sur un système client. Les trois usages eux-mêmes sont un cap, pas des
fonctions livrées. Il n'existe pas encore de générateur de jeux de données dans
les bibliothèques, aucun volume ni temps de chargement n'a été mesuré, et
aucune migration n'a été jouée. L'angle pour les migrations est le chargement
scripté et son contrôle croisé, pas le remplacement des outils de chargement et
de migration de SAP.

## Documentation

| Document | Sujet |
| --- | --- |
| [Référence des keywords](https://cyrilm29.github.io/robotframework-sapfx/) | Tous les keywords des trois bibliothèques (en anglais) |
| [docs/architecture.fr.md](docs/architecture.fr.md) | Comment les bibliothèques sont construites et s'articulent |
| [docs/fiori-architecture.fr.md](docs/fiori-architecture.fr.md) | Le côté web : sélecteurs UI5, moteurs, frames, pages hybrides |
| [docs/testing-without-sap.fr.md](docs/testing-without-sap.fr.md) | Un système SAP local et gratuit, les prérequis côté SAP |
| [docs/sap-test-data.fr.md](docs/sap-test-data.fr.md) | Les données et cibles de test disponibles sans système client |
| [docs/ecc-validation.fr.md](docs/ecc-validation.fr.md) | La validation sur un système ABAP réel, pas à pas |
| [docs/hardening-test-environment.fr.md](docs/hardening-test-environment.fr.md) | Liste de contrôle de sécurité : serveur, poste, côté web |
| [docs/migrating-from-sapguilibrary.fr.md](docs/migrating-from-sapguilibrary.fr.md) | Migrer depuis robotframework-sapguilibrary |
| [docs/migrating-from-cbta.fr.md](docs/migrating-from-cbta.fr.md) | Migrer depuis SAP CBTA |
| [docs/audit-upstream.fr.md](docs/audit-upstream.fr.md) | Ce que SapEccLibrary change au code amont qu'elle embarque, et pourquoi |

Chaque document existe en anglais et en français (`*.fr.md`). Ils ont été
écrits avec les bibliothèques dans l'atelier du mainteneur : quand ils
mentionnent une couche de resources métier (`resources/`), des suites Robot
(`tests/robot/`), des recorders ou des agents de test, ils décrivent cet
atelier, qui ne fait pas partie de ce dépôt.

## Organisation

```text
src/SapEccLibrary/      SAP GUI for Windows (COM) ; keywords/ un mixin par
                        capacité, y compris ceux de robotframework-sapguilibrary
src/SapFioriLibrary/    Fiori / UI5 / Web Components / SAP GUI for HTML
                        (bibliothèque Browser) ; JavaScript injecté dans *.js.tpl
src/SapApiLibrary/      OData v2/v4 et RFC / BAPI optionnels
src/sapfx_common/       logique pure partagée
docs/                   documentation des bibliothèques (EN/FR), docs/libdoc/ = pages des keywords
```

## Signalements

Les rapports d'anomalie et les suggestions sont les bienvenus en
[issues GitHub](https://github.com/CyrilM29/robotframework-sapfx/issues).

## Licence

Apache 2.0. Inclut du code absorbé de robotframework-sapguilibrary, des
moteurs de localisateurs portés de playwright-sap et des techniques adaptées de
RoboSAPiens et de playwright-praman ; voir [LICENSE](LICENSE) et
[NOTICE](NOTICE).

## Marques

SAP, SAP ECC, SAP S/4HANA, SAP Fiori, SAP BTP, SAP HANA, SAP NetWeaver, SAP
GUI, SAPUI5, ABAP et les autres produits et services SAP cités sont des marques
commerciales ou des marques déposées de SAP SE ou de ses sociétés affiliées en
Allemagne et dans d'autres pays. SAPFX est un projet open source indépendant,
sans affiliation, parrainage ni approbation de SAP SE.
