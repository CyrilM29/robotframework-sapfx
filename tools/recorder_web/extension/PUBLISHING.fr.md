> [🇬🇧 English](PUBLISHING.md) · **🇫🇷 Français**

# Publier l'extension UI5 / WebGUI Recorder

L'extension est prête pour le store. La soumission reste manuelle (elle nécessite votre
compte développeur et la revue des stores) — voici les étapes exactes.

## 1. Construire le paquet

Régénérez les fichiers générés, puis zippez :

```bash
python -m SapFioriLibrary.regen_recorder            # écrit recorder.js depuis le bundle
python tools/recorder_web/extension/gen_icons.py    # écrit icon16/48/128.png
python tools/recorder_web/extension/package.py      # -> dist/ui5-recorder-extension-<version>.zip
```

Le zip ne contient que les fichiers d'exécution : `manifest.json`, `popup.html`,
`popup.js`, `recorder.js`, `background.js`, `bridge.js`, `icon16/48/128.png`. Les
helpers de développement (`gen_icons.py`, `package.py`, les READMEs) sont exclus.
Incrémentez `"version"` dans `manifest.json` avant chaque mise en ligne (actuellement
`0.3.0`).

## 2. Chrome Web Store

1. Inscrivez-vous une fois sur le [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole)
   (frais uniques de 5 US$).
2. **Add new item** → téléversez le `.zip`.
3. Remplissez la fiche : nom, résumé, description, catégorie *Developer Tools*, langue,
   au moins une capture **1280×800** — une prête est fournie dans
   `store/screenshot-1280x800.png` (régénérez avec
   `robot --pythonpath src tools/recorder_web/extension/store/make_screenshot.robot`) —
   et l'icône 128 px (déjà dans le paquet).
4. **Confidentialité** : déclarez un objectif unique (« capturer des localisateurs de
   test stables et enregistrer des déroulés sur les pages SAP UI5/WebGUI ») ; justifiez
   les permissions — `scripting` + `activeTab` ne servent qu'à injecter le recorder dans
   l'onglet que vous activez explicitement (clic icône ou `Alt+Shift+R`). **Aucune donnée
   collectée ni transmise** (tout est local ; les sélecteurs vont au presse-papiers / un
   `.robot` téléchargé). Fournissez l'**URL de la politique de confidentialité** —
   hébergez [`PRIVACY.fr.md`](PRIVACY.fr.md) (ex. via GitHub Pages / page brute) et collez
   son URL.
5. Soumettez à la revue.

## 3. Microsoft Edge Add-ons (optionnel)

Même `.zip` sur le [Edge Add-ons Partner Center](https://partner.microsoft.com/dashboard/microsoftedge)
(sans frais). Mêmes champs, politique de confidentialité et justification de permissions.

## 4. Firefox (optionnel, expérimental)

Le JS utilise un shim `browser`/`chrome` (`const api = typeof browser !== 'undefined' ?
browser : chrome`), donc popup/background/bridge sont multi-navigateurs. Firefox MV3
diffère sur la clé manifeste `background` (event `scripts` vs `service_worker`) et peut
exiger un `browser_specific_settings.gecko.id` ; produisez un manifeste spécifique
Firefox avant de soumettre à [addons.mozilla.org](https://addons.mozilla.org). Pas
encore entièrement validé.

## Justification des permissions (copier-coller)

> **activeTab** + **scripting** : quand l'utilisateur clique sur le bouton de la barre
> d'outils (ou utilise la commande `Alt+Shift+R`), le popup/background injecte le
> recorder (`recorder.js`) dans le contexte de page de l'onglet *courant* pour lire le
> registre de contrôles SAP UI5 / le `lsdata` WebGUI et calculer des localisateurs de
> test stables, plus un petit `bridge.js` pour piloter le badge de l'icône. Aucune
> permission d'hôte n'est demandée ; rien ne s'exécute tant que l'utilisateur n'agit pas.
> L'extension n'effectue **aucune requête réseau** et **ne collecte aucune donnée** — les
> localisateurs capturés restent dans le presse-papiers local / un `.robot` téléchargé.
> Voir [PRIVACY.fr.md](PRIVACY.fr.md).
