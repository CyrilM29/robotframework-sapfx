*** Settings ***
Documentation       Smoke du **repos réel** et des **messages UI5** contre
...                 cap-sflight en local (Fiori Elements v4, List Report ;
...                 aucun backend SAP). Démarrage de la cible :
...
...                   cd _cap-sflight && npx cds watch    # -> localhost:4004
...
...                 Ce que la suite prouve, qu'un `Wait For UI5 Ready` seul ne
...                 prouve pas : après une action qui déclenche un aller-retour
...                 OData (filtre + Go, tri), la vue est déjà rendue alors que
...                 les données voyagent encore. `Wait For Ui5 Idle` attend le
...                 repos RÉEL (requêtes XHR/fetch en vol + indicateurs busy +
...                 calme continu), et la table lue APRÈS lui porte les données
...                 attendues. Les messages applicatifs sont vérifiés par TYPE
...                 (convention n°3), jamais par texte localisé.
...                 Exécution :  robot --pythonpath src tests/robot/fiori_idle_messages_smoke.robot

Library             Browser
Library             Collections
Resource            ../../resources/fiori_keywords.resource

Suite Setup         Run Keywords    Set Ui5 Timeout    30s
...                     AND    Open Fiori Launchpad    ${SFLIGHT_URL}
Suite Teardown      Close Fiori


*** Variables ***
${SFLIGHT_URL}          http://localhost:4004/sap.fe.cap.travel/index.html
${TRAVEL_TABLE_ID}      sap.fe.cap.travel::TravelList--fe::table::Travel::LineItem-innerTable
${SEARCH_FIELD_ID}      fe::FilterBar::Travel::BasicSearchField-inner
# Bouton « lancer la recherche » du FilterBar : ciblé par son id FE STABLE,
# jamais par son texte (l'app suit la locale du navigateur : « Go » en anglais,
# « Lancer » en français, constaté live). C'est la convention n°3 appliquée au
# web : on n'assied jamais un localisateur sur un texte traduit.
${SEARCH_BUTTON_ID}     fe::FilterBar::Travel-btnSearch


*** Test Cases ***
Page Reaches Real Idle After Load
    [Documentation]    Au chargement, `Wait For Ui5 Idle` retourne un état de
    ...                repos réel : plus aucune requête en vol, aucun indicateur
    ...                busy, et un calme continu supérieur au seuil demandé.
    Wait For UI5 Ready
    ${state}=    Wait For Ui5 Idle    settle=400 ms
    Should Be Equal As Integers    ${state}[pending]    0
    Should Not Be True    ${state}[busy]
    Should Be True    ${state}[quiet_ms] >= 400

Idle Wait Makes Filtered Data Readable
    [Documentation]    Le cas d'usage qui tue la flakiness : on filtre, on
    ...                attend le repos RÉSEAU, puis on lit. Le nombre de lignes
    ...                après filtre est strictement inférieur au total, ce qui
    ...                prouve que les données filtrées sont bien arrivées avant
    ...                l'assertion. NB : le PREMIER rendu s'attend par une
    ...                condition d'application (les lignes sont rendues), pas
    ...                par le repos réseau : le keyword attend les requêtes
    ...                déjà parties, il ne devine pas celles à venir.
    Wait For UI5 Ready
    Ui5 Control Should Be Visible    controlType=ColumnListItem
    ${all_rows}=    Read Ui5 Table    id=${TRAVEL_TABLE_ID}
    Should Not Be Empty    ${all_rows}

    Fill Ui5 Input    Aussie    idSuffix=${SEARCH_FIELD_ID}
    Click Ui5 Control    idSuffix=${SEARCH_BUTTON_ID}
    ${state}=    Wait For Ui5 Idle    settle=400 ms
    Should Be Equal As Integers    ${state}[pending]    0

    ${filtered}=    Read Ui5 Table    id=${TRAVEL_TABLE_ID}
    Should Not Be Empty    ${filtered}
    # La preuve porte sur le CONTENU, pas sur le nombre de lignes : la table
    # pagine (30 lignes chargées), le filtre ne réduit donc pas forcément ce
    # nombre. Les valeurs sont concaténées plutôt que lues par nom de colonne :
    # les en-têtes suivent la locale de l'app (convention n°3).
    ${matching}=    Evaluate
    ...    sum(1 for r in $filtered if 'Aussie' in ' '.join(map(str, r.values())))
    Should Be Equal As Integers    ${matching}    ${{ len($filtered) }}
    ...    msg=Des lignes hors filtre sont encore affichées : la table lue est celle d'AVANT le filtre.
    # Contre-preuve : avant le filtre, la table portait d'autres agences.
    ${before_matching}=    Evaluate
    ...    sum(1 for r in $all_rows if 'Aussie' in ' '.join(map(str, r.values())))
    Should Be True    ${before_matching} < ${{ len($all_rows) }}
    ...    msg=Le jeu initial ne contenait que des lignes Aussie : le test ne prouverait rien.

Application Reports No Error Messages
    [Documentation]    Les messages applicatifs sont lus depuis le
    ...                MessageManager UI5 et jugés par TYPE : aucune erreur ne
    ...                doit être en attente sur un parcours nominal.
    Wait For Ui5 Idle
    ${messages}=    Get Ui5 Messages
    Dictionary Should Contain Key    ${messages}    messages
    Dictionary Should Contain Key    ${messages}    toasts
    Ui5 Should Have No Messages Of Type    Error
