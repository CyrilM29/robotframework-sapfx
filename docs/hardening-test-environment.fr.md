> [🇬🇧 English](hardening-test-environment.md) · **🇫🇷 Français**

# Durcir l'environnement de test SAP

L'automatisation de tests concentre le risque en un seul endroit : un poste qui
détient de **vrais identifiants SAP**, tape de **vraies données dans de vrais
écrans**, enregistre écrans et frappes, et expose une API d'automatisation que
n'importe quel processus local peut piloter. Ce guide est la checklist de
sécurité de cet environnement — versant serveur, poste, web et agents IA
(MCP) — et relie chaque point aux **keywords de préflight** qui le vérifient
automatiquement.

Sources : SAP GUI Scripting Security Guide (help.sap.com), note de sécurité
SAP 3472837 / CVE-2025-0055 (janvier 2025), annonce GA de SAP GUI for Windows
8.10 (SAP Community, juillet 2026), note de sécurité SAP 3747367
(Patch Day de juillet 2026, SAP GUI for HTML).

## 1. Versant serveur (paramètres de profil RZ11)

Le SAP GUI Scripting est **désactivé par défaut** (`sapgui/user_scripting =
FALSE`). Un script a **exactement les droits de l'utilisateur qui le lance** —
le serveur ne distingue pas le trafic scripté du trafic humain. La conséquence
joue dans les deux sens :

- le scripting n'élève aucun privilège, mais
- un script sans surveillance peut créer de la mauvaise donnée en masse, à la
  vitesse des autorisations de l'utilisateur de test.

Posture recommandée :

| Paramètre | Valeur recommandée | Pourquoi |
|---|---|---|
| `sapgui/user_scripting` | `TRUE` (en MAJUSCULES !) sur les **systèmes de test uniquement** | prérequis de tout scripting |
| `sapgui/user_scripting_per_user` | `TRUE` | scripting réservé aux utilisateurs détenant **S_SCR Execute(16)** (classe BC_A) — à n'accorder qu'au compte de test dédié. C'est le mécanisme SAP officiel pour cantonner le scripting sans serveur d'application dédié |
| `sapgui/user_scripting_set_readonly` | `FALSE` sur les systèmes de test | à `TRUE`, l'API lit mais ne peut plus agir — les tests échouent bizarrement |
| `sapgui/user_scripting_disable_recording` | `FALSE` si vous utilisez le recorder à événements natifs | à `TRUE`, tous les **événements** de scripting sont coupés (le mode `--engine native` du recorder desktop replie automatiquement sur le polling) |

Ne jamais activer le scripting largement en production ; donner à l'utilisateur
de test les rôles métier minimaux qu'exigent les scénarios, rien de plus.

**Préflight :** `Scripting Should Be Fully Enabled` (Suite Setup) échoue tôt
avec le paramètre RZ11 exact à corriger, et nomme désormais la piste
`per_user`/S_SCR quand le serveur refuse le scripting alors que
`user_scripting = TRUE`.

### WebGUI (SAP GUI for HTML) — activer en connaissance de cause

Le moteur WebGUI `sid` a besoin du service ICF
`/default_host/sap/bc/gui/sap/its/webgui`, **inactif par défaut**. Avant de
l'activer, connaître la **note de sécurité SAP 3747367** (Patch Day de
juillet 2026) : une corruption mémoire dans SAP GUI for HTML notée
**CVSS 9.9** (attaquant authentifié → lecture/modification de données,
indisponibilité), qui concerne tout nœud ICF dont le réglage GUI interactif
est actif. Le correctif est un **patch kernel** ABAP (avec arrêt) ; l'unique
contournement — désactiver les nœuds ICF — supprime le WebGUI. Les systèmes
d'essai comme l'image Docker A4H tournent généralement sur un kernel non
patché : les garder sur un réseau isolé, n'activer le service `webgui` que
sur des systèmes de test, et ne jamais l'exposer au-delà du segment de test.

### Niveau de patch — chiffrement de l'historique de saisie (CVE-2025-0055)

Jusqu'en janvier 2025, SAP GUI for Windows stockait l'**historique de saisie**
(chaque valeur tapée dans les champs, y compris par vos runs de test) dans des
fichiers SQLite locaux (`SAPHistory<WINUSER>.db`) protégés par un **XOR à clé
statique** — trivialement réversible (CVE-2025-0055, note SAP 3472837 ; la
variante SAP GUI for Java est la CVE-2025-0056). Corrigé à partir de **SAP GUI
for Windows 8.00 PL9** ; la 8.10 (GA 16/07/2026, supportée jusqu'au
30/06/2029) embarque le correctif. Attention : la 8.00 sort du support complet
le **12/01/2027** — planifier la migration 8.10 des postes de test.

### Désactiver l'historique de saisie sur les postes de test

Même patché, l'historique reste une copie de tout ce que vos suites tapent,
posée dans le profil Windows. Sur un poste de test : **Options → Local Data →
History → désactiver**, et purger les fichiers `SAPHistory*.db` existants.

**Préflight :** `Client Security Should Be Hardened` échoue si le client est
vulnérable à la CVE ou si des bases d'historique sont présentes
(`allow_input_history=True` pour tolérer en connaissance de cause) ;
`Get Client Security Status` retourne la posture complète en lecture seule
(y compris à travers rf-mcp).

### Autres points du poste

- Compte Windows dédié à l'exécution des tests ; les répertoires de captures
  (`tools/recorder/captures/`, `results/` Robot) restent hors VCS — les
  captures d'écran peuvent contenir des données personnelles (RGPD) : traiter
  les artefacts de run comme de la donnée.
- La télémétrie de healing (`SAPFX_HEALING_LOG`) **ne journalise jamais les
  valeurs saisies** — c'est voulu ; le préserver en cas d'extension.
- Le mode accessibilité (réglage du poste) est requis pour lire les listes
  ABAP classiques — voir `Abap List Should Be Readable` (préflight
  fonctionnel, même philosophie).

## 3. Identifiants

- Ne jamais coder en dur des identifiants dans les `.robot` ou les
  resources — les injecter à chaque run depuis les secrets CI ou un coffre
  local, sous forme de **variable typée `Secret`** (Robot Framework 7.4) :
  `-v "SAP_PASSWORD: Secret:…"`. Un `Secret` est masqué partout — même un log
  TRACE n'affiche que `<secret>` — et tous les keywords des trois
  bibliothèques qui acceptent un mot de passe le prennent (`Input Password`,
  `Open Sap Session`, `Open Api Session`, `Open Rfc Connection`,
  `Log In Via Identity Provider`), en ne le déballant qu'à la frontière
  COM/HTTP.
- Une chaîne ordinaire `-v SAP_PASSWORD:…` fonctionne toujours partout, mais
  sa valeur brute affleure dans les logs TRACE quand les keywords répètent
  leurs arguments — la forme typée `Secret` est le réglage recommandé. Dans
  les deux cas, garder les keywords type `Input Password` (qui ne
  journalisent jamais la valeur) pour les champs mot de passe.
- Préférer SNC/SSO quand le paysage le permet (plus de mot de passe en jeu).

## 4. Versant web (Fiori / bibliothèque Browser)

- **Extension recorder MV3** : l'injection est bornée à `activeTab` (geste
  utilisateur requis), pas de permissions d'hôte larges — à préserver ; le zip
  du store est construit depuis les sources (`package.py`), ne jamais ajouter
  de code hébergé à distance (politique MV3).
- **Débogage du navigateur embarqué** (`Enable Embedded Browser Debugging`)
  ouvre un **port de debug CDP** sur le runtime WebView2 : n'importe quel
  processus local peut s'y attacher. Postes de test uniquement, jamais sur une
  machine partagée ; retirer la variable pour l'usage normal.
- **CSP** : le bundle `__SAPFX` est injecté via l'evaluate de Playwright
  (CDP), que la CSP de la page ne bloque pas — aucun assouplissement CSP n'est
  requis sur le système testé (prouvé par le smoke à CSP stricte,
  `fiori_csp_smoke.robot`).

## 5. Versant agents IA / MCP

- rf-mcp tourne en **stdio** (aucune écoute réseau) ; le garder ainsi — ne pas
  l'exposer via un pont TCP sur une machine partagée.
- Les états API et Fiori sont partitionnés par session rf-mcp. Conserver une
  seule session ECC live par process, car rf-mcp 0.31 n'attribue pas fiablement
  les appels de resources imbriquées (voir `integrations/robotmcp/README.fr.md`).
- La perception (signatures d'écran, screenshots) peut contenir de vraies
  données métier : les transcripts MCP et logs d'agents sont de la **donnée**,
  soumise aux mêmes règles de rétention que les artefacts de run.
- Contenir l'injection de prompt : un agent agit avec les droits de
  l'utilisateur de test — le compte de test à moindre privilège du §1 est
  aussi votre limiteur de rayon d'explosion.

## 6. Chaîne d'approvisionnement

- `pywin32` est épinglé exactement (`==`, convention 6) dans
  `requirements.txt` / `requirements-deploy.txt` ; relire avant toute montée.
- Conserver `constraints-deploy.txt`, le sidecar SHA-256 du ZIP, le SBOM
  CycloneDX et l'attestation de provenance avec chaque release qualifiée.
- Le pack de déploiement est distribué via le dépôt public releases-only —
  vérifier qu'on installe les wheels d'une release de confiance, pas d'un
  fork.

## 7. Patron de Suite Setup

```robotframework
*** Settings ***
Library     SapEccLibrary
Suite Setup    Preflight

*** Keywords ***
Preflight
    Open Sap Logon    ${SAP_CONNECTION}
    Connect To Session
    Scripting Should Be Fully Enabled
    Client Security Should Be Hardened
```

Les deux préflights sont en lecture seule, indépendants de la locale, et
échouent en nommant le paramètre ou l'action poste exacts à corriger.
