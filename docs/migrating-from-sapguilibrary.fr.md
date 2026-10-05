> [🇬🇧 English](migrating-from-sapguilibrary.md) · **🇫🇷 Français**

# Migrer depuis robotframework-sapguilibrary

`SapEccLibrary` est un fork durci de
[robotframework-sapguilibrary](https://github.com/frankvanderkuur/robotframework-sapguilibrary)
(Apache 2.0, voir `NOTICE`). Le code upstream est vendorisé **à l'identique**
(`src/SapEccLibrary/_vendor/sapgui_base.py`, seule la classe est renommée) et
`SapEccLibrary` en hérite ; la migration est donc un simple renommage :

```robotframework
# avant
Library    SapGuiLibrary
# après
Library    SapEccLibrary
```

**Tous les keywords upstream gardent leur nom et leur signature.** Les
suites écrites pour SapGuiLibrary tournent telles quelles ; les apports
s'adoptent ensuite au rythme de l'équipe. Quelques keywords échouent
désormais franchement là où l'amont rendait une valeur trompeuse : `Get Value`
sur un shell d'arbre, de grille ou d'éditeur (l'amont rendait le ProgID du
contrôle), et `Select From List By Label` sur une combo en affichage ou avec un
libellé inconnu.

## Étapes

1. Installer la bibliothèque depuis PyPI (`pip install robotframework-sapfx`)
   et épingler `pywin32` exactement dans votre fichier d'environnement : c'est
   la source n°1 de casse COM.
2. Remplacer l'import `Library` dans les suites/resources.
3. `robot --dryrun` pour confirmer la résolution des keywords.
4. Lancer les suites : le comportement est celui d'upstream, plus les
   surcharges ci-dessous.

## Ce qui change immédiatement (surcharges sûres)

| Comportement upstream | Comportement SapEccLibrary |
|---|---|
| `Run Transaction` vérifie le texte localisé de la barre d'état | indépendant de la locale : vérifie le **type** de message (`E`/`S`/…), gère les tcodes à namespace (`/BEV1/RCA01`) |
| `Connect To Session` suppose l'appartement COM initialisé | `CoInitialize` défensif : fonctionne hors du thread principal (rf-mcp, runners threadés) |
| `Select From List By Label` affecte l'entrée et s'y fie | refuse une combo en affichage ou un libellé inconnu (entrées listées), et relit la sélection sur l'élément ré-acquis par son id : une combo à code fonction reconstruit l'écran pendant la sélection |

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
