*** Settings ***
Documentation       Page object de la **List Report « Travel processor »** (application
...                 Fiori Elements v4 `sap.fe.cap.travel`, vue `TravelList` — cible
...                 locale cap-sflight). Un seul écran, donc un seul fichier :
...                 ses localisateurs en tête, ses mots-clés métier ensuite.
...
...                 Contrat de localisation : l'ancre primaire est le **suffixe d'id
...                 Fiori Elements** (`fe::…`), jamais le préfixe applicatif
...                 `sap.fe.cap.travel::TravelList--` (il porte le nom du composant et
...                 de la route) ni un id DOM généré (`__clone…`). Les xpath UI5 les
...                 plus courts de cet écran sont tous positionnels
...                 (`//ActionToolbar[1]/Title[1]`…) : ils ne valent que comme repli.
...
...                 Contrat d'assertion : tout ce que ces mots-clés retournent est
...                 **locale-indépendant** — des nombres extraits ou des comptages de
...                 contrôles. Les libellés de l'application suivent la locale du
...                 navigateur (relevé live en français : « Voyages (4 133) », avec un
...                 séparateur de milliers U+202F), et `Read Ui5 Table` retourne des
...                 dictionnaires dont les CLÉS sont ces libellés localisés : aucun
...                 mot-clé d'ici n'indexe dessus.
...
...                 Synchronisation : le service OData v4 de l'application groupe ses
...                 requêtes en `$batch`. Relevé live le 2026-07-25 : `Wait For UI5
...                 Ready` seul rend la main AVANT l'arrivée des données (le compteur
...                 lisait encore 4 133 juste après un « Go » filtrant à 91), et
...                 `Wait For Load State networkidle` rend la main immédiatement (l'état
...                 réseau était déjà idle avant le clic). L'attente déterministe est
...                 donc l'**armement d'une promesse sur la réponse `$batch` avant le
...                 clic** — jamais une attente fixe (convention 2).

# `fiori_keywords.resource` porte déjà les imports `Browser` et `SapFioriLibrary`
# (avec son `ui5_timeout`) : les redéclarer ici les ferait diverger en arguments —
# Robot ignorerait alors le second import avec un avertissement.
Resource            ../fiori_keywords.resource


*** Variables ***
# --- Localisateurs : suffixes d'id Fiori Elements, relevés live (2026-07-25) --
${TRAVEL_LIST_PAGE}                 fe::ListReport    # sap.f.DynamicPage
${TRAVEL_FILTER_BAR}                fe::FilterBar::Travel    # sap.fe.macros.controls.FilterBar
${TRAVEL_SEARCH_FIELD}              fe::FilterBar::Travel::BasicSearchField    # sap.ui.mdc.FilterField (composite)
${TRAVEL_GO_BUTTON}                 fe::FilterBar::Travel-btnSearch    # sap.m.Button « Go »
${TRAVEL_TABLE}                     fe::table::Travel::LineItem    # sap.ui.mdc.Table (macro FE)
${TRAVEL_INNER_TABLE}               fe::table::Travel::LineItem-innerTable    # sap.m.Table — porte les lignes
${TRAVEL_HEADER_TITLE}              fe::table::Travel::LineItem-title    # sap.m.Title — porte la volumétrie
${TRAVEL_ROW_CONTROL}               sap.m.ColumnListItem    # une ligne rendue
${TRAVEL_DIALOG_CONTROL}            sap.m.Dialog    # boîte de dialogue / MessageBox

# --- Synchronisation des données (OData v4 groupé en $batch) ------------------
${TRAVEL_DATA_MATCHER}              response => response.url().endsWith('$batch')
${TRAVEL_DATA_TIMEOUT}              30s


*** Keywords ***
Open Travel Processor
    [Documentation]    Ouvre l'application « Travel processor » et rend la main
    ...                seulement quand sa liste porte réellement des données.
    ...                Prévu pour Suite Setup. `Open Fiori Launchpad` seul ne suffit
    ...                pas : son `Wait For UI5 Ready` final rend la main alors que le
    ...                premier chargement OData est encore en vol (relevé live
    ...                2026-07-25 : table rendue, **0 ligne** instanciée).
    [Arguments]    ${url}
    Open Fiori Launchpad    ${url}
    Wait For Travel List Data

Wait For Travel List Data
    [Documentation]    Sonde jusqu'à ce que la liste ait matérialisé au moins une
    ...                ligne — l'attente qui manque après un chargement ou un
    ...                rechargement de page, quand aucune promesse n'a pu être armée
    ...                avant la requête (contrairement à `Search Travels`).
    ...                Le prédicat est lu au niveau **UI5** (`getItems()` de la table
    ...                interne), pas sur une classe CSS de rendu ; la table est
    ...                d'abord résolue par son id technique FE, puis passée au
    ...                prédicat par la bibliothèque Browser. Sondage, jamais
    ...                d'attente fixe (convention 2).
    Travel List Should Be Displayed
    ${table}=    Resolve Ui5 Control    idSuffix=${TRAVEL_INNER_TABLE}
    Wait For Function
    ...    (table) => { const s = window.sap; if (!(s && s.ui)) return false; let E = null; try { E = s.ui.require('sap/ui/core/Element'); } catch (e) {} const t = (E && E.getElementById) ? E.getElementById(table.id) : (s.ui.getCore ? s.ui.getCore().byId(table.id) : null); if (!t || !t.getItems) return false; return t.getItems().length > 0; }
    ...    selector=${table}
    ...    timeout=${TRAVEL_DATA_TIMEOUT}
    ...    message=La liste des voyages n'a matérialisé aucune ligne — données non chargées ?

Travel List Should Be Displayed
    [Documentation]    Vérifie que la liste des voyages est rendue : la table interne
    ...                du List Report (celle qui matérialise les lignes ; le wrapper
    ...                `sap.ui.mdc.Table` ne les expose pas) est visible. Assertion
    ...                d'écran, 100 % locale-indépendante (id technique FE).
    Ui5 Control Should Be Visible    idSuffix=${TRAVEL_INNER_TABLE}

Count Displayed Travel Rows
    [Documentation]    Nombre de lignes actuellement **instanciées** dans la liste.
    ...                Sert à distinguer « au moins une ligne » de « aucune ligne » —
    ...                jamais à déduire une volumétrie : la table est en mode
    ...                *growing*, ce nombre plafonne au seuil de croissance (30 relevé
    ...                live, aussi bien sur 4 133 que sur 91 résultats). La volumétrie
    ...                réelle se lit avec `Get Travel Count`.
    ${count}=    Get Ui5 Match Count    controlType=${TRAVEL_ROW_CONTROL}
    RETURN    ${count}

Get Travel Count
    [Documentation]    Volumétrie portée par le compteur d'en-tête de la liste,
    ...                retournée en **entier**. Ne garde que les chiffres du titre :
    ...                le libellé qui les précède est localisé (« Voyages » / « Travels »)
    ...                et le séparateur de milliers dépend de la locale (U+202F, espace
    ...                fine insécable, en français). Filtrage caractère par caractère —
    ...                un motif regex à backslash (`\\D`) serait silencieusement
    ...                défiguré par l'échappement Robot. Retourne `0` quand le titre ne
    ...                porte aucun nombre : c'est le rendu observé quand la recherche
    ...                ne ramène aucun résultat (titre « Voyages » tout court).
    ${raw}=    Get Ui5 Text    idSuffix=${TRAVEL_HEADER_TITLE}
    ${count}=    Evaluate    int(''.join(c for c in $raw if c.isdigit()) or 0)
    RETURN    ${count}

Search Travels
    [Documentation]    Saisit `${term}` dans la zone de recherche libre de la barre de
    ...                filtres, déclenche « Go » et **attend l'arrivée des données**.
    ...                Le clic sur « Go » est la voie déterministe (la validation par
    ...                Entrée dépend de l'état du champ). L'attente arme une promesse
    ...                sur la réponse `$batch` du service OData AVANT le clic : c'est
    ...                le seul point de synchronisation fiable relevé live — ni
    ...                `Wait For UI5 Ready` (rend la main avant l'arrivée des données)
    ...                ni `networkidle` (déjà atteint avant le clic) ne suffisent.
    ...                `Wait For UI5 Ready` reste en second rideau, pour le rendu.
    [Arguments]    ${term}
    Fill Ui5 Input    ${term}    idSuffix=${TRAVEL_SEARCH_FIELD}
    ${data_loaded}=    Promise To    Wait For Response
    ...    matcher=${TRAVEL_DATA_MATCHER}    timeout=${TRAVEL_DATA_TIMEOUT}
    Click Ui5 Control    idSuffix=${TRAVEL_GO_BUTTON}
    Wait For    ${data_loaded}
    Wait For UI5 Ready

Clear Travel Search
    [Documentation]    Revient à l'état non filtré : vide la zone de recherche libre
    ...                puis relance la recherche. Le bouton de réinitialisation
    ...                `fe::FilterBar::Travel-btnClear` existe mais est rendu invisible
    ...                dans cette variante — ne pas s'appuyer dessus.
    Search Travels    ${EMPTY}

Read Displayed Travel Rows
    [Documentation]    Lit les lignes actuellement instanciées de la liste, sous forme
    ...                de liste de dictionnaires. **Les clés sont les en-têtes de
    ...                colonne localisés** : ne jamais indexer dessus dans une
    ...                assertion — utiliser `Displayed Travel Rows Should All Contain`,
    ...                qui raisonne sur le contenu des cellules.
    ${rows}=    Read Ui5 Table    idSuffix=${TRAVEL_INNER_TABLE}
    RETURN    ${rows}

Displayed Travel Rows Should All Contain
    [Documentation]    Vérifie que **chaque** ligne rendue contient `${term}` dans
    ...                l'une de ses cellules — assertion sur le contenu de DONNÉES
    ...                (donc indépendante de la langue de l'interface), et non sur un
    ...                libellé de colonne. Échoue aussi si la liste est vide : un
    ...                filtre qui ne ramène rien ne prouve pas qu'il a filtré.
    [Arguments]    ${term}
    ${rows}=    Read Displayed Travel Rows
    Should Not Be Empty    ${rows}
    ...    msg=Aucune ligne rendue : le filtre « ${term} » ne ramène rien à vérifier
    FOR    ${row}    IN    @{rows}
        ${cells}=    Evaluate    ' | '.join(str(v) for v in $row.values())
        Should Contain    ${cells}    ${term}    ignore_case=True
        ...    msg=Ligne rendue sans le terme recherché « ${term} » : ${cells}
    END

No Travel Dialog Should Be Open
    [Documentation]    Vérifie qu'aucune boîte de dialogue UI5 (`sap.m.Dialog`,
    ...                MessageBox incluses) n'est ouverte — la façon locale-indépendante
    ...                de dire « aucun message d'erreur n'est apparu ».
    ${dialogs}=    Get Ui5 Match Count    controlType=${TRAVEL_DIALOG_CONTROL}
    Should Be Equal As Integers    ${dialogs}    0
    ...    msg=Une boîte de dialogue UI5 est ouverte alors qu'aucune n'était attendue

Log Travel List Diagnostics On Failure
    [Documentation]    Teardown de test : en cas d'échec seulement, journalise le
    ...                diagnostic Fiori agrégé (composition de la page, arbre UI5,
    ...                erreurs console). Relevé live : un `cds watch` redémarré en
    ...                cours de bootstrap fait échouer le chargement de `Component.js`
    ...                et laisse l'application quasi vide — ce diagnostic nomme la
    ...                cause en une lecture, au lieu de faire croire à une dérive de
    ...                localisateur.
    Run Keyword If Test Failed    Log Fiori Diagnostics
