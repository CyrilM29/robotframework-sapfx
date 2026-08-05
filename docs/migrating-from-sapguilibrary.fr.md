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

**Tous les keywords upstream continuent de fonctionner à l'identique.** Les
suites écrites pour SapGuiLibrary tournent telles quelles ; les apports
s'adoptent ensuite au rythme de l'équipe.

## Étapes

1. Installer la bibliothèque (wheel du pack de déploiement Windows, ou le
   dépôt avec `pip install -r requirements.txt` ; `pywin32` y est épinglé
   exactement : la source n°1 de casse COM).
2. Remplacer l'import `Library` dans les suites/resources.
3. `robot --dryrun` pour confirmer la résolution des keywords.
4. Lancer les suites : le comportement est celui d'upstream, plus les
   surcharges ci-dessous.

## Ce qui change immédiatement (surcharges sûres)

| Comportement upstream | Comportement SapEccLibrary |
|---|---|
| `Run Transaction` vérifie le texte localisé de la barre d'état | indépendant de la locale : vérifie le **type** de message (`E`/`S`/…), gère les tcodes à namespace (`/BEV1/RCA01`) |
| `Connect To Session` suppose l'appartement COM initialisé | `CoInitialize` défensif : fonctionne hors du thread principal (rf-mcp, runners threadés) |

## Ce que vous gagnez (adoption progressive)

- **Attentes** : `Wait Until Busy Done`, `Wait Until Element Present`, pour
  retirer chaque `Sleep`.
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
