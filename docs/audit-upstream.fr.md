> [🇬🇧 English](audit-upstream.md) · **🇫🇷 Français**

# Audit : `robotframework-sapguilibrary` (upstream)

Commit examiné : pointe de `master` (version **v1.2.1**, mars 2022). Licence **Apache 2.0**.
Source auditée : `SapGuiLibrary/SapGuiLibrary.py` (module unique d'environ 780 lignes, une seule classe).

## Verdict

Une base solide et ciblée, sur laquelle il vaut mieux bâtir que tout réécrire. La plomberie COM et un
vocabulaire de mots-clés cohérent sont déjà en place et éprouvés. Les lacunes sont
circonscrites et bien définies : exactement ce que nous ajoutons dans `SapEccLibrary`.

## Ce qu'elle fait déjà bien

- **Le bootstrap COM est correct.** `connect_to_session` énumère la Running Object
  Table, lie le moniker `SAPGUI`, puis appelle `GetScriptingEngine`. Approche robuste.
- **Bonne couverture des mots-clés**, y compris les parties que l'on suppose généralement absentes :
  - Saisie : `input_text`, `input_password`, `select_checkbox`/`unselect_checkbox`,
    `select_radio_button`, `select_from_list_by_label`.
  - Navigation : `click_element`, `doubleclick_element`, `send_vkey` (table complète des vkeys),
    `run_transaction`, `maximize_window`.
  - **ALV / shell** : `get_cell_value`, `set_cell_value`, `get_row_count`,
    `select_table_row`, `select_table_column`, `click_toolbar_button`,
    `select_node`, `select_node_link`, `scroll`, `select_context_menu_item`.
  - Assertions/lectures : `get_value`, `element_value_should_be`/`should_contain`,
    `element_should_be_present`, `get_element_type`, `get_window_title`.
- **Captures d'écran en cas d'erreur** intégrées dans chaque mot-clé via `take_screenshot()`.
- **Dispatch par type** : les mots-clés s'appuient sur `get_element_type` et fournissent des
  erreurs explicites du type « utilisez X à la place ».

> Correction d'une hypothèse antérieure : la grille/ALV **n'est pas** absente ici. Le travail
> sur la grille dans `SapEccLibrary` relève de l'*ergonomie* (adresser les colonnes par leur titre),
> et non du comblement d'un manque.

## Lacunes traitées dans `SapEccLibrary`

| # | Lacune | Preuve dans le source | Notre correctif |
|---|--------|-----------------------|-----------------|
| 1 | **Pas de synchronisation réelle.** Seulement un `time.sleep(self.explicit_wait)` fixe après chaque mot-clé. Pas de polling `session.Busy`, pas de « attendre jusqu'à présence ». | `explicit_wait` défini par `set_explicit_wait` ; chaque mot-clé se termine par `time.sleep`. | `keywords/_waits.py` : `Wait Until Busy Done`, `Wait Until Element Present`, `Wait Until Element Value Is`. |
| 2 | **Vérification de transaction dépendante de la locale.** La détection d'une tcode inconnue compare par correspondance de chaîne dans la barre de statut en **néerlandais/anglais/allemand uniquement**. | `run_transaction` compare avec `"Transactie %s bestaat niet"`, `"Transaction %s does not exist"`, `"Transaktion %s existiert nicht"`. | `Run Transaction` compare la transaction active (`session.Info.Transaction`) au code demandé (indépendant de la locale). |
| 3 | **Pas de bootstrap de connexion.** Suppose que le Logon Pad est déjà en cours d'exécution ; la documentation demande de le démarrer avec la bibliothèque AutoIt/Process. | `connect_to_session` lève « is Sap Logon Pad open? » si ce n'est pas le cas. | `keywords/_connection.py` : `Open Sap Logon` (lancement de l'exe + attente du moteur), `Close Sap Logon`, `Connect To Session With Retry`. |
| 4 | **Grille adressée uniquement par identifiant de colonne technique.** Il faut connaître `"MATNR"` etc. (trouvé via le Scripting Tracker externe). | `get_cell_value(table_id, row, col_id)` prend un `col_id` brut. | `keywords/_grid.py` : résolution des colonnes par titre visible, `Read Grid` → liste de dicts. |
| 5 | **Pas d'utilitaires pour les messages de statut.** | (sans objet) | `Get Status Message`, `Status Message Should Be Success`. |

## Observations mineures (en partie réglées par l'absorption, voir plus bas)

- `__version__ = '1.2'` dans le code contre le tag de version `1.2.1`.
- Dépend de `robot.libraries.Screenshot` (fonctionnel, mais ScreenCapLibrary en version
  autonome est le choix plus moderne).
- Plusieurs mots-clés appellent `findById` plusieurs fois pour un même élément (par ex.
  `element_value_should_be` → `get_element_type` + `get_value` + `findById`) ;
  sans conséquence, mais bavard sur COM.
- `select_node` avec `expand=True` avale toutes les `com_error`s (un `# TODO` est laissé
  en néerlandais). Acceptable.
- Classificateurs Python 2.7 dans `setup.py`, supprimés dans notre `pyproject.toml`.

## Absorption (6 octobre 2026)

Le fichier amont a d'abord été vendorisé tel quel
(`src/SapEccLibrary/_vendor/sapgui_base.py`, seule la classe renommée) avec
une règle qui limitait ce diff à une ligne, pour qu'une future version amont
se recopie en quelques minutes. L'amont n'a plus bougé après mars 2022
(v1.2.1), et la règle a fini par protéger du code que personne ne relisait :
21 de ses 37 mots-clés tournaient encore avec leur corps d'origine, sans
relecture, et sa capture de l'écran entier servait aussi les chemins d'erreur
de notre propre code. Le 6 octobre 2026, ce code a été absorbé et réécrit dans
les modules du projet ; le fichier vendorisé, `scripts/check_vendor_drift.py`
et le workflow hebdomadaire `vendor-drift.yml` ont disparu.

Ce qui reste promis, c'est la **surface** : les 37 mots-clés gardent leur nom
ainsi que l'ordre, le nom et la valeur par défaut de leurs paramètres, donc une
suite écrite pour `SapGuiLibrary` tourne sans modification.
`tests/unit/test_upstream_compatibility.py` tient cette table, relevée par
`inspect.signature` sur le fichier vendorisé avant son retrait ; un paramètre
ne peut être ajouté que s'il est optionnel et placé en dernier (`Run
Transaction` a gagné `skip_if_error` ainsi). Chaque module dérivé le dit dans
son en-tête, et `NOTICE` garde l'attribution Apache 2.0.

| Mots-clés de l'amont | Module | Ce qui a changé |
|---|---|---|
| `Get Element Type`, `Element Should Be Present`, `Get Value`, `Set Focus`, `Get Element Location`, `Get Window Title`, `Maximize Window` | `keywords/_elements.py` | une absence nomme l'écran réellement affiché ; `Get Value` ne prend plus le focus et refuse le ProgID d'un shell ; un type non pris en charge lève `ValueError` |
| `Click Element`, `Input Text`, `Input Password`, `Select Checkbox`, `Unselect Checkbox`, `Select Radio Button`, `Send Vkey` | `keywords/_inputs.py` | les écritures sont relues (troncature, champ ou case protégés) ; aucun mot de passe ni `Secret` n'est journalisé ; un `GuiShell` n'accepte du texte qu'en `TextEdit` ; `Send Vkey` envoie l'entier de l'API et résout les combinaisons par `sapfx_common/vkeys.py` |
| `Element Value Should Be`, `Element Value Should Contain` | `keywords/_value_checks.py` | aucun focus déplacé ; `AssertionError` pour un écart, `ValueError` pour une erreur d'usage |
| `Get Row Count`, `Get Cell Value`, `Set Cell Value`, `Click Toolbar Button`, `Select Table Row`, `Select Table Column`, `Scroll`, `Get Scroll Position` | `keywords/_grid_cells.py` | la grille est résolue à travers un conteneur qui l'enveloppe ; `Set Cell Value` est relu ; `Select Table Row` sélectionne aussi une ligne de `GuiTableControl` |
| `Connect To Session`, `Connect To Existing Connection`, `Open Connection` | `keywords/_connection.py` | seul un moteur qui répond est retenu ; toutes les connexions ouvertes sont examinées ; `Open Connection` attend la session |
| `Take Screenshot`, `Enable Screenshots On Error`, `Disable Screenshots On Error` | `keywords/_screenshots.py` | la fenêtre SAP (modal compris) est capturée en PNG, pas l'écran entier ; une capture impossible ne masque jamais l'erreur d'origine |
| `Set Explicit Wait` | `keywords/_waits.py` | toute durée Robot Framework, ancienne valeur rendue |
| `Doubleclick Element`, `Select Context Menu Item` | `keywords/_grid_actions.py` | une grille ALV est visée par cellule au lieu de l'API des arbres |
| `Select Node`, `Select Node Link` | `keywords/_trees.py` | sélection vérifiée en relisant `SelectedNode` |
| `Select From List By Label` | `keywords/_combobox.py` | mode affichage et libellé inconnu refusés, sélection relue |
| `Run Transaction` | `SapEccLibrary.py` | la transaction active est comparée au code demandé, quelle que soit la langue |

Deux des observations mineures ci-dessus se règlent du même coup : la chaîne
de version de l'amont a disparu, et plus rien ne dépend de la bibliothèque
`Screenshot` de Robot. Les appels répétés à `findById` d'une vérification de
valeur demeurent (sans gravité, toujours bavards par COM).

## Marques

SAP, SAP ECC, SAP S/4HANA, SAP Fiori, SAP BTP, SAP HANA, SAP NetWeaver, SAP
GUI, SAPUI5, ABAP et les autres produits et services SAP cités sont des marques
commerciales ou des marques déposées de SAP SE ou de ses sociétés affiliées en
Allemagne et dans d'autres pays. SAPFX est un projet open source indépendant,
sans affiliation, parrainage ni approbation de SAP SE.
