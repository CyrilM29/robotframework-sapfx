*** Settings ***
Documentation       Smoke Fiori Elements contre **cap-sflight en local** (aucun backend
...                 SAP, aucun réseau) : voir docs/sap-test-data.fr.md §3. Démarrage de
...                 la cible :
...
...                   git clone https://github.com/SAP-samples/cap-sflight
...                   cd cap-sflight && npm ci && npx cds watch    # -> localhost:4004
...
...                 La suite pilote l'app « Travel processor » (Fiori Elements v4,
...                 List Report) via les sélecteurs de contrôles UI5 : chargement,
...                 lancement de la recherche (bouton Go du FilterBar, ciblé par id
...                 de registre FE stable), et lignes présentes dans la table.
...                 Exécution :  robot --pythonpath src tests/robot/fiori_sflight_smoke.robot

Library             Browser
Resource            ../../resources/fiori_keywords.resource

# La resource importe SapFioriLibrary (défaut 15s) ; le budget élargi de cette
# suite passe par le réglage dynamique, jamais par un second import avec
# d'autres arguments (Robot l'ignorerait avec un warning).
Suite Setup         Run Keywords    Set Ui5 Timeout    30s
...                     AND    Open Fiori Launchpad    ${SFLIGHT_URL}
Suite Teardown      Close Fiori


*** Variables ***
${SFLIGHT_URL}      http://localhost:4004/sap.fe.cap.travel/index.html
# Id de contrôle UI5 stable généré par Fiori Elements v4 (vue TravelList, table
# LineItem) : la ``sap.m.Table`` interne qui matérialise les lignes ; le wrapper
# ``sap.ui.mdc.Table`` ne les expose pas.
${TRAVEL_TABLE_ID}    sap.fe.cap.travel::TravelList--fe::table::Travel::LineItem-innerTable


*** Test Cases ***
Travel List Report Loads
    [Documentation]    L'app Fiori Elements démarre : le FilterBar de la List Report
    ...                est rendu (contrôle FE standard).
    Wait For UI5 Ready
    Ui5 Control Should Be Visible    controlType=FilterBar

Travel Table Materializes Rows
    [Documentation]    La List Report charge ses données (initialLoad actif sur cette
    ...                app : aucun clic Go nécessaire) : des ``ColumnListItem`` sont
    ...                rendus et la ``sap.m.Table`` interne se lit en liste de dicts.
    Wait For UI5 Ready
    Ui5 Control Should Be Visible    controlType=ColumnListItem
    ${rows}=    Read Ui5 Table    id=${TRAVEL_TABLE_ID}
    Should Not Be Empty    ${rows}
    ${count}=    Get Ui5 Match Count    controlType=ColumnListItem
    Should Be True    ${count} >= 1
