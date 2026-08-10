> [🇬🇧 English](README.md) · **🇫🇷 Français**

# Web Recorder : Fiori / UI5 (+ WebGUI) capture de localisateurs & enregistrement de déroulés (phase 2)

Capture des **sélecteurs stables** depuis une page Fiori / SAPUI5 / OpenUI5 en cours d'exécution (ainsi que le **WebGUI** classique de SAP) afin de ne plus se battre contre les identifiants DOM dynamiques, et **enregistre des déroulés entiers** en une séquence de keywords rejouable. Il émet exactement ce que `SapFioriLibrary` résout à l'exécution.

> **Fichier généré.** `recorder_snippet.js` est généré à partir du bundle de la bibliothèque
> (`src/SapFioriLibrary/_ui5_js.py`) afin que la capture ne diverge jamais de la résolution. Ne
> l'éditez pas manuellement ; exécutez `python -m SapFioriLibrary.regen_recorder`. Un test unitaire
> garantit la synchronisation.

## Deux façons de l'exécuter

**A. Extension de navigateur (un seul clic)** : voir [`extension/`](extension/README.fr.md). Chargez
le dossier non empaqueté, cliquez sur l'icône, **Start**. Idéal pour une utilisation répétée.

**B. Console DevTools (sans installation) :**

1. Ouvrez une application Fiori, le [OpenUI5 Demo Kit](https://sdk.openui5.org/), ou une page SAP
   WebGUI.
2. DevTools → Console, collez le contenu de `recorder_snippet.js`, Entrée.

Dans les deux cas : **survoler** met en évidence le contrôle sous le curseur (cadre bleu + puce
d'étiquette) ; **cliquer** le capture dans un **panneau flottant** (en bas à droite) listant chaque
capture avec des boutons **copy** par ligne (`role`, `xpath`, `sid`, `wc`, `dom`, `all`) et copie
le dernier dans le presse-papiers. Les zones non-SAP d'une page hybride (widget React/Angular/
vanilla) sont capturées aussi, via le **moteur dom générique** (rôle ARIA calculé + nom accessible,
chemin CSS en repli). Les lignes copiées ressemblent à :

```robotframework
Resolve Ui5 Control    controlType=sap.m.Button    properties={'text': 'Get Started'}
Resolve Ui5 By Xpath    //Page//Button[2]
Resolve Sid    wnd[0]/usr/ctxtVBAK-VBELN        # only on classic WebGUI pages
Resolve Dom Element    role=button    name=Submit    # zone non-SAP d'une page hybride
```

Si la page contient des **iframes cross-origin** hors de portée de ce panneau, une ligne
d'avertissement apparaît ; utilisez l'extension (injection allFrames : un panneau séparé
apparaît dans chaque frame accessible).

### Mode record

Cliquez sur **`rec`** dans le panneau pour démarrer l'enregistrement. Ensuite, **utilisez
l'application** : chaque clic devient un step `Click Ui5 Control` (ou `Click Sid` /
`Click Wc Control` / `Click Dom Element`), chaque champ saisi puis quitté un step `Fill … Input`,
la touche **Entrée** dans un champ est capturée en `Keyboard Key    press    Enter` (ordonnée
*après* la saisie du champ), et un changement de route ajoute **`Wait For UI5 Ready`** quand le
runtime UI5 est présent (la définition du keyword est embarquée dans l'export : le fichier reste
autonome), sinon `Wait For Load State`.

**Assertions** : le **clic droit** sur un élément pendant l'enregistrement ouvre le **menu
d'assertions** (visible / texte, selon le moteur) ; **Alt+clic** (visible) et
**Shift+Alt+clic** (`Ui5 Text Should Be`) restent des raccourcis.

Les steps sont **dédupliqués et compactés** (une re-saisie du même champ remplace la précédente ;
les attentes consécutives fusionnent), **éditables** (↑ ↓ ✕ par ligne, et **double-clic pour
éditer un step en place**), **nommables** (champ `Test:`) et **persistés** : ils **survivent à un
rechargement de page** (sessionStorage), donc un flux Fiori multi-pages n'est pas perdu. Pendant
l'enregistrement, **les clics ne sont jamais bloqués** : l'application continue de réagir pour
dérouler un vrai parcours (seuls les gestes méta, les assertions Alt+clic, sont avalés).

**`play`** **rejoue l'enregistrement dans la page** : chaque step est résolu par les mêmes
moteurs que la bibliothèque, surligné et exécuté (~3 steps/s) ; les steps UI5 réessaient leur
**repli xpath** enregistré quand le sélecteur primaire ne résout plus ; le premier échec arrête
le replay et marque la ligne. Validation instantanée avant export, sans lancer robot.

**`+test`** démarre un **nouveau scénario** (step marqueur) : chaque export produit alors
plusieurs `*** Test Cases ***`, le bootstrap `New Browser`/`New Page` ne vivant que dans le
premier.

**`export`** ouvre un menu : un `recorded.robot` complet et rejouable (Settings +
`New Browser`/`New Page` + steps), une **paire resource-first**
(`recorded_keywords.resource` avec keywords métier + un `recorded.robot` **sans localisateur
dans le test**, convention n°1 du projet ; les steps UI5 deviennent des keywords
**auto-réparables** via `Resolve Ui5 With Fallback` et leur xpath enregistré), un **plan
Markdown au format `specs/`** (`recorded.spec.md`, l'entrée du cycle agents
plan → generate → heal), un **plan de test + cas de test ISTQB**
(`recorded.istqb.md` : sections ISTQB / ISO 29119-3, un cas de test par
scénario avec tableau Action / Données / Résultat attendu et bloc `replay`
YAML normalisé, actions neutres vis-à-vis du framework avec le localisateur
relevé en `hint` : lisible par un humain ET rejouable par une IA avec
n'importe quel framework de test ; l'agent `sap-istqb` rédige les rubriques
de jugement), un **rapport HTML de documentation auto-contenu**
(`recorded_report.html` : une phrase métier par step avec la ligne RF exacte en
regard, un chapitre par scénario ; de la documentation pour humains, jamais un
test ; concept observé chez le recorder de RoboSAPiens, voir `NOTICE`), ou
l'**import d'un `.robot` exporté** dans le panneau (lignes de
bootstrap ignorées, multi-tests restaurés en marqueurs : le cycle d'édition se referme).
Chaque ligne de format porte aussi une **case à cocher** : cocher plusieurs
formats (le choix survit à la navigation), puis « exporter la sélection » les
télécharge tous, téléchargements espacés (Chrome affiche son invite
multi-téléchargements au lieu de bloquer en silence) ; cliquer le libellé
d'une ligne exporte toujours ce seul format immédiatement.
**`pause`** arrête l'ajout ; **`clear`** vide la liste. Exemple de sortie :

```robotframework
*** Settings ***
Library    Browser
Library    SapFioriLibrary

*** Test Cases ***
Scénario enregistré
    New Browser    chromium    headless=False
    New Page    <URL courante>
    Click Ui5 Control    controlType=sap.m.Button    properties={'text': 'Open Dialog'}
    Fill Ui5 Input    abc    controlType=sap.m.Input    properties={'value': 'hello world'}
```

> **Où atterrit le téléchargement.** Une page web ne peut pas choisir le dossier de sauvegarde
> (sécurité navigateur) ; `export` télécharge `recorded.robot` dans **le dossier *Téléchargements*
> de votre navigateur**, seul le *nom* est imposé. Le dossier de convention du projet pour ces
> artefacts est **`tools/recorder_web/captures/`** (gitignoré, le pendant web du
> `tools/recorder/captures/` bureau) ; déplacez/enregistrez-y le fichier. Le test smoke écrit
> directement le téléchargement capturé dans ce dossier via le `saveAs` de Playwright.

Le bouton `stop` du panneau ou `Esc` (ou `window.__ui5SpyStop()`) termine la session et supprime le
calque/panneau.

> `recorder_snippet.js` et `extension/recorder.js` sont tous deux **générés** à partir de
> `src/SapFioriLibrary/_ui5_js.py` ; exécutez `python -m SapFioriLibrary.regen_recorder` après
> avoir modifié le bundle (un test unitaire garantit la synchronisation).

### Iframes de launchpad (Work Zone / cFLP)

Les launchpads Fiori embarquent souvent l'application dans une **iframe**
(cross-origin) : le runtime UI5 vit dans la frame. L'**extension** injecte le
recorder dans **toutes les frames** : capture et record fonctionnent directement
dans l'application embarquée ; le titre du panneau affiche **`[iframe]`** pour
indiquer le contexte de capture. Rejouez ces steps avec `Set Ui5 Frame
<sélecteur de frame>` avant les keywords UI5 (voir `SapFioriLibrary`). La variante
snippet console doit être collée *dans le contexte de la frame* (sélecteur de
contexte des DevTools).

## Ce qu'il émet

- **role** : type de contrôle + la meilleure propriété issue d'une liste d'autorisation ordonnée par
  priorité (`text`, `title`, `value`, …), comparée au registre des contrôles. Sur les
  applications **Fiori Elements**, les contrôles dont l'id porte un suffixe stable
  `fe::` sont capturés avec `idSuffix=`, le localisateur FE le plus robuste.
- **xpath** : le chemin **le plus court et unique** dans l'arborescence des contrôles UI5.
- **sid** : sur les pages WebGUI, le `SID` stable extrait du `lsdata` de l'élément.
- **wc** : sur les pages UI5 Web Components sans runtime classique, l'hôte `ui5-*`
  (`tag=` + `text=`).
- **dom** : sur les zones non-SAP, le rôle ARIA calculé + nom accessible `name=`
  (`role=button    name=Submit`), chemin CSS light-DOM en repli ; cibles interactives
  seulement (un clic sur un `div` nu n'enregistre rien).
- **record** : steps `Click …` / `Fill …` ordonnés sur les cinq moteurs, avec les mêmes
  sélecteurs ci-dessus.

Tous résistent à la rotation des identifiants qui brise le CSS/XPath brut. Le **UI5 Test
Recorder** intégré de SAP (**Ctrl+Shift+Alt+T**) est une alternative complémentaire plus lourde.

> Nous n'utilisons intentionnellement *pas* `RecordReplay.findControlSelectorByDOMElement` : sur
> les versions actuelles de UI5, cette API est peu fiable en dehors du pipeline OPA5 complet (voir
> `../../docs/fiori-architecture.md`).

## Feuille de route

- [x] **Mise en évidence au survol** : contour + puce d'étiquette pour le contrôle sous le curseur.
- [x] **Empaquetage en extension de navigateur** : Start/Stop en un clic (voir `extension/`).
- [x] **Panneau intégré à l'application** : liste flottante des sélecteurs capturés avec boutons de copie.
- [x] **Icône de barre d'outils personnalisée** + package prêt pour le store (voir `extension/PUBLISHING.md`).
- [x] **Mode record** : `rec`/`pause`/`export` transcrivent un déroulé en un corps `*** Test Cases ***`
      rejouable. Validé en live sur le Chrome système.
- [x] **Upgrade 2026-07** : capture du moteur dom (pages hybrides), menu d'assertions au
      clic droit, capture d'Entrée, `Wait For UI5 Ready` à la navigation, compaction
      saisies/attentes, alerte frames cross-origin, et le menu d'export à 3 formats
      (.robot / resource-first / plan specs).
- [x] **Passe « esprit Selenium IDE » (2026-07-19)** : replay `play` dans la page
      (mêmes moteurs, repli xpath réessayé, arrêt au premier échec), marqueurs
      multi-scénarios `+test`, ré-import d'un `.robot`, édition au double-clic,
      steps UI5 nés auto-réparables (indice `# xpath:` → `Resolve Ui5 With
      Fallback` à l'export resource-first), et l'enregistrement ne bloque plus
      les clics de l'application.
- [ ] **Publication** sur le Chrome Web Store / Edge Add-ons (soumission manuelle).

## Relation avec le Recorder bureau

[`../recorder/`](../recorder/) effectue le même travail pour le client lourd SAP GUI (via COM), y
compris son propre enregistreur de déroulé `--record`. Ensemble, ils offrent un flux de capture +
enregistrement par canal, alimentant tous deux le même vocabulaire de mots-clés unifié
(`resources/*.resource`). Voir `../../docs/architecture.fr.md`.
