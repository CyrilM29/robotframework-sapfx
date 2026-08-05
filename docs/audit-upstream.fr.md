> [🇬🇧 English](audit-upstream.md) · **🇫🇷 Français**

# Audit : `robotframework-sapguilibrary` (upstream)

Commit examiné : pointe de `master` (version **v1.2.1**, mars 2022). Licence **Apache 2.0**.
Source auditée : `SapGuiLibrary/SapGuiLibrary.py` (module unique d'environ 780 lignes, une seule classe).

## Verdict

Une base solide et ciblée, qu'il vaut mieux forker que réécrire. La plomberie COM et un
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
> sur la grille dans notre fork relève de l'*ergonomie* (adresser les colonnes par leur titre),
> et non du comblement d'un manque.

## Lacunes traitées dans le fork

| # | Lacune | Preuve dans le source | Notre correctif |
|---|--------|-----------------------|-----------------|
| 1 | **Pas de synchronisation réelle.** Seulement un `time.sleep(self.explicit_wait)` fixe après chaque mot-clé. Pas de polling `session.Busy`, pas de « attendre jusqu'à présence ». | `explicit_wait` défini par `set_explicit_wait` ; chaque mot-clé se termine par `time.sleep`. | `keywords/_waits.py` : `Wait Until Busy Done`, `Wait Until Element Present`, `Wait Until Element Value Is`. |
| 2 | **Vérification de transaction dépendante de la locale.** La détection d'une tcode inconnue compare par correspondance de chaîne dans la barre de statut en **néerlandais/anglais/allemand uniquement**. | `run_transaction` compare avec `"Transactie %s bestaat niet"`, `"Transaction %s does not exist"`, `"Transaktion %s existiert nicht"`. | Le remplacement lit `sbar.messageType == "E"` (indépendant de la locale). |
| 3 | **Pas de bootstrap de connexion.** Suppose que le Logon Pad est déjà en cours d'exécution ; la documentation demande de le démarrer avec la bibliothèque AutoIt/Process. | `connect_to_session` lève « is Sap Logon Pad open? » si ce n'est pas le cas. | `keywords/_connection.py` : `Open Sap Logon` (lancement de l'exe + attente du moteur), `Close Sap Logon`, `Connect To Session With Retry`. |
| 4 | **Grille adressée uniquement par identifiant de colonne technique.** Il faut connaître `"MATNR"` etc. (trouvé via le Scripting Tracker externe). | `get_cell_value(table_id, row, col_id)` prend un `col_id` brut. | `keywords/_grid.py` : résolution des colonnes par titre visible, `Read Grid` → liste de dicts. |
| 5 | **Pas d'utilitaires pour les messages de statut.** | (sans objet) | `Get Status Message`, `Status Message Should Be Success`. |

## Observations mineures (non corrigées, notées pour plus tard)

- `__version__ = '1.2'` dans le code contre le tag de version `1.2.1`.
- Dépend de `robot.libraries.Screenshot` (fonctionnel, mais ScreenCapLibrary en version
  autonome est le choix plus moderne).
- Plusieurs mots-clés appellent `findById` plusieurs fois pour un même élément (par ex.
  `element_value_should_be` → `get_element_type` + `get_value` + `findById`) ;
  sans conséquence, mais bavard sur COM.
- `select_node` avec `expand=True` avale toutes les `com_error`s (un `# TODO` est laissé
  en néerlandais). Acceptable.
- Classificateurs Python 2.7 dans `setup.py`, supprimés dans notre `pyproject.toml`.

## Stratégie de resynchronisation

Le fichier upstream est intégré tel quel à
`src/SapEccLibrary/_vendor/sapgui_base.py` avec une **seule** modification (renommage de classe
`SapGuiLibrary` → `SapGuiBase`). Pour intégrer une future version upstream : recopier le
fichier, réappliquer ce renommage, puis relancer `tests/unit` et le diff libdoc. Limiter
la modification à une seule ligne est délibéré afin que cela reste une opération de 5 minutes.
