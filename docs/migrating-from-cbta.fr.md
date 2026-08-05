> [🇬🇧 English](migrating-from-cbta.md) · **🇫🇷 Français**

# Migrer depuis CBTA (Solution Manager)

SAP Solution Manager 7.2 (la plateforme qui héberge CBTA et la Test Suite
d'eCATT) sort de maintenance mainstream le **31/12/2027**, et SAP a indiqué
que CBTA ne serait pas étendu à ses produits cloud (la trajectoire officielle
est Cloud ALM + outillage partenaire). Tout parc CBTA doit donc avoir une
destination avant 2028. Ce guide mappe les concepts CBTA sur ce projet et
esquisse le chemin de migration.

## Correspondance des concepts

| CBTA / Solution Manager | Ici |
|---|---|
| Script de test (Test Composition Environment) | une suite `.robot` sous `tests/robot/` |
| Composant (étape réutilisable) | un keyword métier dans `resources/*.resource` (convention 1 : les tests ne portent jamais d'ids SAP bruts) |
| Composants par défaut (actions d'écran) | les keywords `SapEccLibrary` / `SapFioriLibrary` (attentes, grilles, libellés, moteurs UI5) |
| Connexion au SUT (system data container) | chaîne de connexion + identifiants injectés à chaque run (`-v SAP_CONNECTION:… -v SAP_USER:…` depuis les secrets CI) |
| Enregistrement d'un script | recorder desktop (`tools/recorder`, événements natifs de l'API, `--semantic` pour des keywords par libellé) et recorder web (extension MV3) |
| Maintenance des scripts après un changement d'UI | agent `sap-healer` + healing de localisateurs avec télémétrie (`SAPFX_HEALING_LOG` → `scripts/healing_drift_report.py` propose le patch de la resource) |
| Listes d'exécution / plans de test | CLI `robot` + votre ordonnanceur CI (les tags sélectionnent le périmètre ; `--include smoke`) |
| Preuves (captures, journaux) | `log.html`/`report.html` Robot, screenshots inline, baselines visuelles |
| Indications de couverture (TBOM) | tags de suite/test + la couche spec (`specs/` : chaque suite générée porte le hash de son plan, gardé par `check_spec_sync.py`) |

## Chemin de migration

1. **Inventorier** les scripts CBTA qui produisent encore de la valeur
   (beaucoup de parcs traînent des scripts morts : ne pas les porter).
2. Pour chaque flux métier, laisser **sap-planner** explorer le système réel à
   travers rf-mcp et écrire le plan dans `specs/` (Markdown français,
   relisible par la MOA ; cela remplace la relecture des scripts CBTA).
3. **sap-generator** transforme le plan en suite, chaque étape exécutée live
   avant d'être écrite ; les briques manquantes atterrissent dans
   `resources/`, jamais dans les tests.
4. Brancher la CI (`robot --dryrun` en garde, puis runs planifiés) ; adopter
   la [checklist de durcissement](hardening-test-environment.fr.md) pour le
   poste d'exécution et la posture RZ11.
5. Quand l'UI dérive, **sap-healer** répare la couche resources : les tests ne
   bougent pas, et la télémétrie de healing révèle les localisateurs qui
   dérivent de façon récurrente.

## Ce que ce projet ne remplace pas

La *gestion* de test (plans, validations, traçabilité des exigences) vivait
dans Solution Manager lui-même : ce rôle part vers SAP Cloud ALM ou l'ALM de
votre choix ; les résultats Robot Framework (`output.xml`) s'intègrent à la
plupart d'entre eux. Les contrats Enterprise Support incluent aussi une
licence Tricentis ; ce projet est l'alternative open-source, code-first et
prête pour les agents ; les deux peuvent coexister pendant la transition.
