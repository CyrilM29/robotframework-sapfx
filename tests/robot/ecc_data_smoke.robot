*** Settings ***
Documentation       Smoke ECC **data-driven** contre l'ABAP Platform Trial (A4H) :
...                 garantit d'abord des données de démo (SFLIGHT via
...                 SAPBC_DATA_GENERATOR : génération uniquement si la table est
...                 vide), puis lit des grilles garanties non vides. Assertions
...                 indépendantes de la locale : identifiants techniques de colonnes
...                 (``CARRID``), jamais les titres affichés. Voir
...                 docs/sap-test-data.fr.md. Exécution :
...
...                   robot --pythonpath src ^
...                     -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER ^
...                     -v "SAP_PASSWORD: Secret:***" -v SAP_CLIENT:001 ^
...                     tests/robot/ecc_data_smoke.robot
...
...                 (syntaxe de variable typée `Secret` de Robot Framework 7.4 : le mot
...                 de passe n'apparaît jamais dans les logs, même en TRACE)

Resource            ../../resources/ecc_keywords.resource
Resource            ../../resources/a4h_demo_data.resource

Suite Setup         Run Keywords    Open SAP And Log In
...                 AND             Use ALV Grid In Data Browser
...                 AND             Ensure Flight Demo Data Exists
...                 AND             Ensure EPM Demo Data Exists
Suite Teardown      Close SAP


*** Test Cases ***
SFLIGHT Grid Has Flight Data
    [Documentation]    La table SFLIGHT affiche une grille avec la colonne CARRID
    ...                (id technique, indépendant de la langue) et des lignes.
    Display Table Contents    SFLIGHT
    ${ids}=    Get Grid Column Ids    ${SE16_GRID}
    Should Contain    ${ids}    CARRID
    ${rows}=    Read Displayed Grid    max_rows=5
    Should Not Be Empty    ${rows}

SPFLI Connections Are Readable
    [Documentation]    Le même générateur alimente SPFLI (liaisons) : lecture de la
    ...                première cellule de la colonne technique CONNID par titre résolu.
    Display Table Contents    SPFLI
    ${ids}=    Get Grid Column Ids    ${SE16_GRID}
    Should Contain    ${ids}    CONNID
    ${rows}=    Read Displayed Grid    max_rows=3
    Should Not Be Empty    ${rows}

EPM Purchase Orders Are Readable
    [Documentation]    Les commandes d'achat EPM (SNWD_PO, générées par SEPM_DG)
    ...                sont lisibles : colonne technique PO_ID présente et lignes non vides.
    Display Table Contents    SNWD_PO
    ${ids}=    Get Grid Column Ids    ${SE16_GRID}
    Should Contain    ${ids}    PO_ID
    ${rows}=    Read Displayed Grid    max_rows=3
    Should Not Be Empty    ${rows}

Flight Data Survives A Reread
    [Documentation]    Relire SFLIGHT donne un résultat stable (mêmes colonnes) :
    ...                garde-fou contre un état de session résiduel entre lectures.
    Display Table Contents    SFLIGHT
    ${first}=    Get Grid Column Ids    ${SE16_GRID}
    Display Table Contents    SFLIGHT
    ${second}=    Get Grid Column Ids    ${SE16_GRID}
    Should Be Equal    ${first}    ${second}
