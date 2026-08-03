> [🇬🇧 English](README.md) · **🇫🇷 Français**

# UI5 / WebGUI Locator Recorder — extension navigateur

Version en un clic du Recorder : sans copier-coller dans la console. **Survoler** met en surbrillance le contrôle sous le curseur ; **cliquer** le capture dans un **panneau intégré** (une liste flottante avec des boutons **copier** `role` / `xpath` / `sid` / `all` par ligne) et copie le dernier dans le presse-papiers. **`rec`** enregistre tout un déroulé (clics → `Click Ui5 Control`, champs saisis → `Fill Ui5 Input`, Alt+clic → assertion de visibilité, Shift+Alt+clic → assertion de valeur `Ui5 Text Should Be`) ; **`export`** télécharge un `recorded.robot` complet (et le copie). `clear` vide la liste ; `stop` (ou `Esc`) termine la session.

Le panneau est **déplaçable** (glisser son en-tête) et **repliable** (▾), et affiche un **point rouge d'enregistrement**. On peut aussi le piloter depuis le **popup** (Start, Rec/Pause, Export, Stop, avec état en direct), et le raccourci **`Alt+Shift+R`** bascule l'enregistrement sans ouvrir le popup — l'icône affiche un **badge `REC`** pendant l'enregistrement.

## Chargement (non empaqueté — Chrome / Edge)

1. Générer le script de contenu et les icônes (une fois, et après toute modification du bundle) :

   ```bash
   python -m SapFioriLibrary.regen_recorder            # écrit extension/recorder.js depuis le bundle
   python tools/recorder_web/extension/gen_icons.py    # écrit icon16/48/128.png
   ```

2. Ouvrir `chrome://extensions` (ou `edge://extensions`), activer le **Mode développeur**.
3. **Charger l'extension non empaquetée** → sélectionner ce dossier `extension/`.
4. Ouvrir une page Fiori / UI5 (ou une page SAP WebGUI), cliquer sur l'icône de l'extension, **Start**.
   Survoler pour surligner, cliquer pour capturer, `rec` pour enregistrer. **Stop** (ou `Esc`) termine.

## Fonctionnement

- `popup.js` / `background.js` injectent `recorder.js` dans le **MAIN world** de la page
  via `chrome.scripting.executeScript` — nécessaire pour lire `window.sap` (runtime UI5).
  L'injection cible **toutes les frames** (`allFrames: true`) : les applications
  embarquées dans une **iframe** de launchpad (Work Zone / cFLP, même cross-origin)
  sont couvertes — le titre du panneau affiche alors `[iframe]`.
  Ils utilisent la permission `activeTab`, accordée au clic sur l'icône ou au raccourci,
  donc l'extension n'a besoin d'**aucune permission d'hôte étendue**.
- Le recorder (MAIN world) ne peut pas appeler `chrome.*` : un petit **`bridge.js`**
  (monde ISOLATED) relaie l'état d'enregistrement à `background.js`, qui pose le **badge**.
- `recorder.js` est **généré depuis `src/SapFioriLibrary/_ui5_js.py`** (identique au
  snippet console `../recorder_snippet.js`), ce qui garantit que la capture ne
  diverge jamais du résolveur de la bibliothèque. Ne pas le modifier manuellement —
  relancer `regen_recorder`.

## Fichiers

| Fichier | Rôle |
|---------|------|
| `manifest.json` | Manifeste MV3 (popup + icônes ; `scripting` + `activeTab` ; `background` ; `commands`). |
| `popup.html` / `popup.js` | Interface Start / Rec / Export / Stop avec état ; pilote le Recorder. |
| `background.js` | Service worker : badge + raccourci `Alt+Shift+R` (injecte + bascule l'enregistrement). |
| `bridge.js` | Relais monde ISOLATED : transmet l'état du recorder au badge. |
| `recorder.js` | Programme Recorder **généré** (bundle + écouteur survol/panneau/clic/record). |
| `icon16/48/128.png` | Icônes de la barre d'outils (**générées** par `gen_icons.py` depuis le logo du projet ; le 16 px recadre sur le visage du robot). |
| `gen_icons.py` | Décline toutes les tailles d'icônes depuis `assets/logo.png` (racine du dépôt ; nécessite Pillow). Réservé au développement. |
| `package.py` | Construit `dist/<name>-<version>.zip` pour la mise en ligne. Réservé au développement. |
| `PRIVACY.md` / `PUBLISHING.md` | Politique de confidentialité + guide de soumission au store. |

Pour publier, voir [PUBLISHING.fr.md](PUBLISHING.fr.md) (`python package.py` → téléverser le zip).

> Techniques de localisation portées depuis [playwright-sap](https://github.com/ArpitSureka/playwright-sap)
> (Apache-2.0) ; voir le fichier `NOTICE` du projet.
