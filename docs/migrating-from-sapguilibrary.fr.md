> [🇬🇧 English](migrating-from-sapguilibrary.md) · **🇫🇷 Français**

# Migrer depuis robotframework-sapguilibrary

`SapEccLibrary` est compatible sans changement avec
[robotframework-sapguilibrary](https://github.com/frankvanderkuur/robotframework-sapguilibrary)
(Apache 2.0, voir `NOTICE`). Son code, d'abord inclus à l'identique, a été
absorbé et réécrit dans les modules de SAPFX le 2026-10-06 : l'amont est figé
depuis mars 2022 (1.2.1). Ses 37 keywords gardent leur nom ainsi que l'ordre,
le nom et la valeur par défaut de leurs paramètres ; la migration est donc un
simple renommage :

```robotframework
# avant
Library    SapGuiLibrary
# après
Library    SapEccLibrary
```

**Tous les keywords de l'amont gardent leur nom et leur signature**, tenus
par un test unitaire. Les suites écrites pour SapGuiLibrary tournent telles
quelles ; les apports s'adoptent ensuite au rythme de l'équipe. Ce qu'une
suite peut remarquer est listé ci-dessous : chaque changement fait échouer
franchement un keyword là où l'amont acceptait un résultat faux, ou retire un
effet de bord.

## Étapes

1. Installer la bibliothèque depuis PyPI (`pip install robotframework-sapfx`)
   et épingler `pywin32` exactement dans votre fichier d'environnement : c'est
   la source n°1 de casse COM.
2. Remplacer l'import `Library` dans les suites/resources.
3. `robot --dryrun` pour confirmer la résolution des keywords.
4. Lancer les suites, et lire le tableau ci-dessous devant tout nouvel échec :
   il nomme un résultat que l'amont acceptait sans le vérifier.

## Ce qui change immédiatement

| Comportement de l'amont | Comportement SapEccLibrary |
|---|---|
| `Input Text`, `Select Checkbox`, `Unselect Checkbox`, `Select Radio Button`, `Set Cell Value` écrivent sans relire | la valeur ou l'état est **relu** : une valeur tronquée par la longueur du champ, un champ ou une case protégés, une cellule de grille en affichage échouent en nommant la valeur obtenue |
| `Input Text` et `Input Password` journalisent la valeur saisie au niveau INFO | rien n'est journalisé sur un champ mot de passe ni pour une valeur `Secret` ; les deux acceptent le type `Secret` de Robot Framework 7.4 |
| `Get Value`, `Element Value Should Be` et `Element Value Should Contain` posent le focus sur l'élément avant de lire | une lecture ne déplace rien |
| `Get Value` sur un shell d'arbre, de grille ou d'éditeur rend le ProgID du contrôle | refusé, en nommant le keyword qui sait lire ce contrôle |
| les erreurs mêlent `Warning`, `ValueError` et `AssertionError` | un écart lève `AssertionError` avec la valeur attendue ET la valeur lue ; une erreur d'usage (type d'élément non pris en charge) lève `ValueError` ; un Logon Pad absent lève toujours `Warning` |
| un élément absent ne nomme que son id | le message nomme aussi l'écran réellement affiché (`# screen <programme>/<transaction>/<numéro>`) |
| la capture sur erreur photographie **l'écran entier** (bibliothèque `Screenshot` de Robot) | elle photographie la **fenêtre SAP** (modal compris) en PNG dans `screenshot_directory` ou le dossier de sortie ; une capture impossible ne masque jamais l'erreur d'origine |
| `Send Vkey` envoie le numéro sous forme de texte | envoie l'entier de l'API ; une combinaison (`F8`, `Ctrl+S`, `Shift+F3`) reste acceptée, et une combinaison inconnue nomme les plus proches |
| `Connect To Session` garde le dernier moteur de scripting trouvé, même celui d'un Logon Pad fermé | ne garde qu'un moteur qui répond ; COM est initialisé d'abord, donc il fonctionne hors du thread principal (rf-mcp, exécuteurs multi-threads) |
| `Connect To Existing Connection` ne regarde que la première connexion | regarde toutes les connexions ouvertes, et les liste quand aucune ne correspond |
| `Open Connection` rend la main dès que l'objet connexion existe | attend sa session (jusqu'à `default_timeout`) |
| `Set Explicit Wait` lit son propre format de durée | accepte toute durée Robot Framework (`1.5`, `500 ms`, `2 min`) et rend l'ancienne valeur |
| `Run Transaction` vérifie le texte localisé de la barre d'état | compare la transaction active (`session.Info.Transaction`) au code demandé, quelle que soit la langue ; gère les tcodes à namespace (`/BEV1/RCA01`) |
| `Select From List By Label` affecte l'entrée et lui fait confiance | refuse une combo en affichage ou un libellé inconnu (entrées listées), et relit la sélection sur l'élément ré-acquis par son id : une combo à code fonction reconstruit l'écran pendant la sélection |
| `Doubleclick Element` et `Select Context Menu Item` appellent l'API des arbres sur une grille ALV | visent la cellule de la grille, puis ouvrent son détail ou son menu contextuel |

## Ce que vous gagnez (adoption progressive)

- **Attentes** : `Wait Until Busy Done`, `Wait Until Element Present`, pour
  retirer chaque `Sleep`. Une session fermée (après `/nex`) échoue tout de
  suite au lieu d'être sondée jusqu'au délai.
- **Sondes sans effet de bord** : `Element Is Present` remplace
  `Run Keyword And Return Status    Element Should Be Present`, dont la
  vérification échouée capturait l'écran à chaque absence (une image par run
  vert pour un popup facultatif) ; `Element Is Changeable` lit le mode
  affichage/modification d'un écran sur un champ plutôt que sur son titre
  traduit.
- **Préflights** (Suite Setup) : `Scripting Should Be Fully Enabled` (posture
  serveur RZ11, paramètre exact nommé), `Client Security Should Be Hardened`
  (patch client / historique de saisie, CVE-2025-0055), `Abap List Should Be
  Readable` (mode accessibilité).
- **Grilles** : ALV par *titre* de colonne, `Read Grid`, adressage de ligne
  par contenu, `Read Abap List` pour les sorties liste classiques.
- **Localisateurs humains** : `Fill Field By Label`, `Click Button By Label`
  (libellé visible + géométrie, ambiguïté toujours remontée).
- **Healing** : `Resolve Element With Healing` (suggestions scorées,
  télémétrie, jamais silencieux), plus `scripts/healing_drift_report.py` qui
  transforme la télémétrie en patchs de la couche resources.
- **Perception** : `Get Screen Signature` (vue texte de l'écran réel,
  `mode=diff`/`semantic`), screenshots (simple, annoté Set-of-Mark), baselines
  visuelles (écran/élément/tuiles), sentinelle de dérive.
- **Recorders et agents IA** : recorder desktop (événements natifs de l'API),
  plugins rf-mcp, agents sap-planner/generator/healer.

## Conventions à adopter avec la migration

Les tests parlent métier : les ids SAP bruts vivent dans `resources/`
(convention 1) ; les assertions restent indépendantes de la locale
(convention 3). Le [guide de durcissement](hardening-test-environment.fr.md)
est le compagnon recommandé pour la posture du poste et du système de test.

## Marques

SAP, SAP ECC, SAP S/4HANA, SAP Fiori, SAP BTP, SAP HANA, SAP NetWeaver, SAP
GUI, SAPUI5, ABAP et les autres produits et services SAP cités sont des marques
commerciales ou des marques déposées de SAP SE ou de ses sociétés affiliées en
Allemagne et dans d'autres pays. SAPFX est un projet open source indépendant,
sans affiliation, parrainage ni approbation de SAP SE.
