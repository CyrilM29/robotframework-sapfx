> [🇬🇧 English](README.md) · **🇫🇷 Français**

# SAP GUI Recorder (phase 2)

Outillage de localisateurs + déroulés pour le client lourd SAP. `sapgui_recorder.py`
opère sur la même connexion COM que la bibliothèque : chaque id qu'il expose est
exactement ce que l'on colle dans un keyword `SapEccLibrary`. Cinq modes : **dump**,
**surlignage**, **clic-à-capturer** interactif, **survol** (inspecteur), et un
**enregistreur** à la demande qui transcrit vos manipulations en une séquence de
keywords rejouable.

## Utilisation

Prérequis : SAP Logon Pad ouvert avec une session en cours, scripting activé côté
serveur et client (voir `../../docs/testing-without-sap.fr.md`), et `pywin32`.

```bash
# Dump : tout l'arbre d'objets en direct
python sapgui_recorder.py                  # arbre indenté -> stdout
python sapgui_recorder.py --filter txt     # ids/types contenant "txt"
python sapgui_recorder.py --json           # JSON -> captures/dump_<horodatage>.json
python sapgui_recorder.py --json tree.json # JSON -> captures/tree.json

# Surlignage : encadre un contrôle en rouge à l'écran (Visualize)
python sapgui_recorder.py --highlight "wnd[0]/usr/ctxtDATABROWSE-TABLENAME"

# Clic-à-capturer : enregistre chaque contrôle FOCALISÉ + une ligne de keyword
python sapgui_recorder.py --capture                 # Ctrl+C pour arrêter
python sapgui_recorder.py --capture --out mes.txt   # destination personnalisée
python sapgui_recorder.py --capture --no-highlight  # sans surligner au passage
python sapgui_recorder.py --capture --filter btn    # seulement ids/types correspondants

# Survol : encadre le contrôle SOUS LE CURSEUR en direct (inspecteur)
python sapgui_recorder.py --hover                    # Ctrl+C pour arrêter
python sapgui_recorder.py --hover --out mes.txt      # enregistre aussi le survol

# Record : transcrit tout un déroulé en un corps *** Test Cases *** rejouable
python sapgui_recorder.py --record                   # Ctrl+C pour arrêter
python sapgui_recorder.py --record --out scenario.robot
python sapgui_recorder.py --record --engine native   # force le moteur natif (événements)
python sapgui_recorder.py --record --engine poll     # force le moteur polling
python sapgui_recorder.py --record --screenshots     # + une capture d'écran par frontière (polling)
python sapgui_recorder.py --record --body-only       # fragment historique (sans Settings : ne se lance pas tel quel)
python sapgui_recorder.py --record --export-resources  # + paire resource-first (aucun id brut)
python sapgui_recorder.py --record --export-spec       # + plan Markdown format specs/ (brouillon)
python sapgui_recorder.py --record --export-report     # + rapport HTML de documentation auto-contenu
python sapgui_recorder.py --record --export-istqb      # + plan de test + cas de test ISTQB (.istqb.md)

# Replay : rejoue un enregistrement contre la session SAP GUI OUVERTE (arrêt au 1er échec)
python sapgui_recorder.py --replay captures/record_x.robot

# Transpile : convertit un enregistrement VBS ALT+F12 de SAP GUI en keywords (sans SAP)
python sapgui_recorder.py --transpile-vbs mon_enregistrement.vbs --suite --export-resources
```

`--capture`/`--hover` capturent **un localisateur à la fois** ; `--record` suit
**tout le déroulé** et émet une séquence de keywords ordonnée et exécutable.

### Assertions à chaud pendant l'enregistrement

Un enregistrement sans assertion n'est qu'un script de navigation. Pendant
`--record` (les deux moteurs), deux **raccourcis globaux** insèrent des
vérifications sans quitter SAP GUI :

- **Ctrl+Alt+A** : assertion de valeur sur l'élément focalisé
  (`Element Value Should Be` ; présence si l'élément n'a pas de texte lisible,
  jamais la valeur d'un champ mot de passe) ;
- **Ctrl+Alt+V** : assertion visuelle de l'écran courant
  (`Screen Should Match Baseline    <out>_etape_NN` ; la baseline est créée au
  premier replay, voir les keywords de perception).

### Exports post-enregistrement

Le déroulé brut (ids techniques) est un **brouillon**. Cinq exports en
dérivent ; l'enregistrement brut n'est jamais modifié :

- **Suite complète par défaut** (depuis le 2026-08-05) : le fichier de sortie
  est directement un `.robot` complet et rejouable (Settings +
  `Library SapEccLibrary` + `Suite Setup    Attach To Open Session`, le
  keyword qui rattache la bibliothèque à la session SAP GUI déjà ouverte, par
  index ; `Connect To Session` seul n'obtient que le moteur de scripting,
  jamais la session ; attrapé en rejouant un export en live). Un `.robot`
  sans son import Library échoue en « keyword introuvable » lancé tel quel
  (constaté live) ; `--body-only` restaure le fragment historique (corps nu à
  coller dans une suite existante ; `--suite` reste accepté, redondant).
- `--export-resources` : écrit `<out>_keywords.resource` (chaque id devient une
  variable `${LOC_…}` enveloppée dans un keyword métier : `Saisir
  DATABROWSE_TABLENAME`, `Cliquer Bouton 31`…) plus
  `<out>_resource_first.robot`, une suite qui n'appelle **que ces keywords** :
  plus aucun id brut dans le test (convention n°1 du projet, et la couche que
  `sap-healer` sait réparer).
- `--export-spec` : écrit `<out>.spec.md`, un plan Markdown au format `specs/`
  (étapes en langage métier, ids relevés relégués en notes factuelles) :
  l'enregistrement devient l'*entrée* du cycle plan → generate → heal des
  agents, au lieu d'un test figé.
- `--export-report` : écrit `<out>_report.html`, un **rapport HTML de
  documentation auto-contenu** (CSS minimal inline, aucun script, aucune
  ressource externe) : une phrase métier française par step (les keywords
  ECC, Fiori/UI5 **et** API sont phrasés, un déroulé mixte cross-canal se
  documente donc aussi) avec la ligne RF exacte en regard, et les captures
  de `--screenshots` incrustées en data-URI par step (capture manquante
  nommée, jamais silencieuse ; les arguments nommés `password=` sont
  toujours masqués). De la documentation pour humains, jamais un test.
  Concept observé chez le recorder de RoboSAPiens (`saveHtmlReport`, voir
  `NOTICE`), réimplémenté par step.
- `--export-istqb` : écrit `<out>.istqb.md`, un document **plan de test + cas
  de test ISTQB** (sections ISTQB / ISO 29119-3 : objectif et périmètre,
  préconditions, critères d'entrée/sortie, traçabilité, risques ; un cas de
  test avec tableau Action / Données / Résultat attendu). Chaque cas de test
  porte un bloc `replay` YAML normalisé (actions neutres vis-à-vis du
  framework : `run_transaction`/`fill`/`click`/`assert_value`…, cible en
  langage humain, localisateur relevé relégué en `hint`) : lisible par un
  humain ET rejouable par une IA avec n'importe quel framework de test. Le
  recorder n'invente rien : les rubriques de jugement restent « à compléter »
  (l'agent `sap-istqb` les rédige depuis les plans `specs/`) ; les assertions
  posées à chaud deviennent de vrais résultats attendus.

Les lignes sémantiques de `--semantic` (un step `Fill Field By Label` /
`Click Button By Label` portant son id technique en commentaire de fin de
ligne) reçoivent un export resource-first **auto-réparable** : le keyword
généré résout via `Resolve Element With Healing` avec l'id enregistré *et*
l'ancre de libellé : chemin nominal par id d'abord, réparation scorée +
re-résolution par libellé sinon, jamais en silence.

### Replay (`--replay FICHIER`)

Le « play » de l'esprit Selenium IDE, côté client lourd : rejoue un
enregistrement (corps nu ou suite complète) contre la session SAP GUI **déjà
ouverte** (`Attach To Open Session`), step par step, arrêt au premier échec
avec le step fautif nommé ; commentaires ignorés. Un step dont le keyword
n'existe **pas** dans `SapEccLibrary` est signalé ET fait échouer le replay
(code de sortie 1) : un « Replay OK : 0 step(s) exécuté(s) » serait vert et
faux. C'est exactement ce que produit une suite **resource-first**, dont tous
les steps sont des keywords métier vivant dans le `.resource` importé : le
message d'échec nomme le cas et renvoie vers `robot`. Un fichier portant
plusieurs tests est annoncé comme tel, seul le premier étant rejoué. La GUI
expose le replay par le bouton **Rejouer** du panneau de steps (sauvegarde
d'abord les éditions en attente).

### Transpile VBS (`--transpile-vbs FICHIER`)

Convertit un enregistrement du « Script Recording and Playback » **intégré à
SAP GUI (ALT+F12)** (VBScript) en keywords SapEccLibrary, via la même machine
à états que le moteur natif (OK-code + Entrée fusionnés en `Run Transaction`,
menus contextuels appariés, cellules de grille suivies ; appels sans keyword
conservés en commentaires `# non mappé`). Ne requiert **aucune session SAP** ;
`--suite` / `--export-resources` / `--export-spec` s'appliquent ensuite
normalement. Validé de bout en bout : VBS format ALT+F12 → transpile →
`--replay` contre un A4H live.

### Arrêt propre depuis l'extérieur (`--stop-file FICHIER`)

Les boucles interactives (capture / survol / record) s'arrêtent normalement par
Ctrl+C dans leur console. Quand le recorder est piloté par un autre programme
(le lanceur Tkinter ci-dessous, un script), il n'y a aucune console à qui
envoyer ce signal : `--stop-file` nomme un fichier sentinelle, et la boucle
sort dès qu'il apparaît, **par son teardown**. Tuer le processus, lui, saute ce
teardown : l'OK-code en attente est perdu et `Session.Record` reste armé côté
SAP GUI (F4 modal, drag & drop désactivé pour l'utilisateur). Le recorder
efface la sentinelle lui-même en s'arrêtant.

### Lanceur visuel (sans ligne de commande)

Une fenêtre Tkinter légère (bibliothèque standard, aucune dépendance en plus) pour
choisir le mode et les options et lancer en un clic. **Double-cliquez `recorder.cmd`**
à la racine du dépôt (Windows), ou lancez :

```bash
python tools/recorder/recorder_gui.py
```

Choisissez un mode (dump / JSON / capture / survol / record / surlignage), remplissez
les champs optionnels filtre / sortie / id, puis **Lancer**. Les modes interactifs
tournent dans une console séparée (sortie live + Ctrl+C) ; **Arrêter** les stoppe,
**Dossier captures** ouvre le dossier de sortie. **Arrêter** est un arrêt
*propre* : le lanceur pose une sentinelle (`--stop-file`, voir ci-dessus) et le
recorder quitte sa boucle par son propre teardown (`Session.Record` remis à
False, événements désabonnés, dernières étapes écrites) ; il ne tue le
processus que si cela reste sans réponse pendant cinq secondes. Les options du record (suite
complète, export resource-first, export spec, export rapport HTML) sont des
cases à cocher. En mode
record, le **panneau « Étapes »** suit le fichier de sortie en direct (chaque
step émis apparaît au fil de l'enregistrement) et permet de réordonner (↑/↓),
supprimer (✕), **éditer en place** (double-clic sur un step), **Enregistrer**
le fichier corrigé et **Rejouer** (lance `--replay` contre la session ouverte,
console séparée), comme le panneau du recorder web.

Exemple de sortie dump :

```
[GuiMainWindow] wnd[0] = 'SAP Easy Access'
  [GuiTextField] wnd[0]/usr/txtRSYST-BNAME = ''
  [GuiButton] wnd[0]/tbar[0]/btn[0]
```

En mode **record**, pilotez SAP GUI normalement. Entre deux allers-retours serveur,
l'enregistreur diffe l'état des champs éditables et écrit les actions qui l'ont produit :

```robot
*** Test Cases ***
Scénario enregistré
    Run Transaction    /nSE16
    Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000
    Send Vkey    0
```

### Fonctionnement du mode record : deux moteurs

`--engine auto|native|poll` (défaut `auto` : natif d'abord, repli automatique).

Le **moteur natif** s'abonne aux événements de l'API de scripting elle-même :
`Session.Record = True` fait émettre à la session un événement `Change` par action
utilisateur avec la **commande exacte** (le mécanisme derrière l'enregistreur
ALT+F12 intégré à SAP GUI). Chaque commande se mappe 1:1 sur un keyword :
`Input Text`, `Click Element` avec le *bouton exact pressé* (`wnd[0]/tbar[1]/btn[8]`
pour F8), actions de grilles/arbres, `Select Checkbox`… Une paire OK-code + Entrée
est fusionnée en un seul `Run Transaction` ; un menu contextuel de grille
(`pressToolbarContextButton` + `selectContextMenuItem`) devient UN `Select
Context Menu Item` ; les nœuds d'arbre se mappent en `Select Node` (dépliage
compris) ; une ligne de grille sélectionnée devient `Select Table Row` ; les
clics de cellule gardent leur ligne/colonne (suivies via les événements
`currentCell*`) dans un commentaire enrichi. Les commandes sans équivalent
keyword sont conservées en commentaires `# non mappé :` ; rien n'est perdu en
silence. Les
mots de passe sont caviardés. Les commentaires de vkeys (`# F8`) viennent d'une
table statique pour les touches courantes, étendue en live via
`GuiSession.GetVKeyDescription` pour le reste (`# Shift+F5`…). La liaison aux événements n'utilise **pas** le
`DispatchWithEvents` de pywin32 (sa génération makepy plante sur la typelib
sapfewse, issue pywin32 #2433) mais un abonnement manuel au point de connexion
(`advise_session_events()`) ; validé en live sur A4H.

**Moteur polling** (repli, et le moteur de `--screenshots`). SAP est un système
d'écrans à états : on remplit des champs (pas d'aller-retour), puis on **soumet**
(aller-retour serveur). La frontière d'aller-retour est un changement de
**signature d'écran** = `(programme/transaction/n° écran, ensemble complet des ids
de contrôles)` : ainsi une action qui réaffiche le *même* dynpro (ex. *Exécuter*
de SE16, qui ne fait qu'ajouter la grille de résultat) est détectée. À chaque
frontière il émet le diff des champs éditables (`Input Text`/`Select Checkbox`/…)
puis l'action de soumission (`Run Transaction` si un OK-code a été saisi, sinon
`Send Vkey 0`).

`auto` replie sur le polling quand le profil serveur désactive l'enregistrement
(`sapgui/user_scripting_disable_recording` → pas d'événements `Change`) ou quand
l'abonnement échoue ; `--screenshots` (une capture d'écran par frontière
d'aller-retour) implique le moteur polling.

Limites assumées (moteur polling) : un réaffichage strictement identique du même
écran n'est pas détecté ; le bouton exact pressé n'est pas déductible (les
soumissions simples deviennent `Send Vkey 0` ; à ajuster si c'était un bouton
précis). Les deux moteurs : les mots de passe sont illisibles par scripting (émis
en `Input Password    <id>    <password>`).

## Où sont sauvegardés les artefacts

Une politique unifiée pour tout (`--json`, `--capture` **et** `--record`) :

| Vous passez | Cela atterrit dans |
|-------------|--------------------|
| rien (`--json` / `--capture` / `--record` seul) | `tools/recorder/captures/`, fichier horodaté (`dump_…json` / `capture_…txt` / `record_…robot`) |
| un chemin **relatif** (`--json t.json`, `--out mes.robot`) | sous `tools/recorder/captures/` |
| un chemin **absolu** (`C:/tmp/t.json`) | exactement là |

Un simple `python sapgui_recorder.py` sans `--json` ne fait qu'afficher dans le
terminal : rien n'est écrit. Le dossier `captures/` est gitignoré : ce sont vos
artefacts de travail, non commités.

## Pourquoi cet outil plutôt qu'un tiers

La bibliothèque amont oriente vers le « SAP Scripting Tracker » externe pour trouver
les ids. Ce script supprime cette dépendance : il réutilise notre propre logique de
connexion, donc les ids capturés se résolvent à l'identique à l'exécution, et
n'installe rien d'autre que pywin32.

## Feuille de route

- [x] **Surlignage** : encadre un contrôle en rouge (`Visualize` natif), via `--highlight ID`.
- [x] **Clic-à-capturer** : `--capture` enregistre chaque contrôle focalisé (polling
      `ActiveWindow.GuiFocus`) avec une ligne de keyword. `--filter` s'y applique aussi.
- [x] **Survol** : `--hover` encadre le contrôle sous le *curseur* (pas seulement le
      focalisé), en mappant `win32api.GetCursorPos` au plus petit rect `ScreenLeft/Top/Width/Height`.
- [x] **Mode record** : `--record` suit vos manipulations et émet un corps
      `*** Test Cases ***` rejouable (diff par aller-retour via la signature d'écran).
      Validé en live sur ABAP Platform A4H.
- [x] **Moteur natif à événements** : `--engine native` transcrit les événements
      `Change` de l'API de scripting (boutons exacts, grilles, arbres ;
      `Run Transaction` fusionné), avec capture par hit-test (`Hit`/`FocusChanged`)
      et repli polling automatique. Validé en live de bout en bout sur A4H (actions
      manuelles *et* scriptées).
- [x] **Assertions à chaud + exports (2026-07)** : raccourcis Ctrl+Alt+A/V pendant
      le record ; `--suite` (.robot complet rejouable) ; `--export-resources`
      (paire resource-first, aucun id brut dans les tests) ; `--export-spec`
      (plan au format specs/). Capture/survol suggèrent aussi `Click Element At
      Offset` (position relative du curseur) quand la cible est un
      `GuiShell`/`GuiChart` opaque : le repli pointeur que l'API ne scripte pas.
- [ ] **Presse-papiers** : copier la ligne de keyword directement dans le presse-papiers.
- [ ] **Transpile VBS** : consommer la sortie `.vbs` du « Script Recording and
      Playback » intégré à SAP GUI et émettre des keywords `SapEccLibrary`.

## Pendant web (Fiori)

Le recorder web est dans [`../recorder_web/`](../recorder_web/) : un extrait DevTools
et une extension navigateur qui surlignent au survol, capturent des localisateurs
UI5/WebGUI, et (mode record) transcrivent clics/saisies en séquences
`Click Ui5 Control` / `Fill Ui5 Input`, générés depuis le même bundle de résolution
`SapFioriLibrary`.
