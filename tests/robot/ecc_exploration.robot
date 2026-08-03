*** Settings ***
Documentation       Campagne de vérification exploratoire de la base SAP cible
...                 (ABAP Platform Trial A4H, S/4HANA 1909, SAP GUI 8.00) — les
...                 découvertes de la campagne robotmcp du 2026-07-09 encodées en
...                 tests rejouables. Trois volets :
...
...                 1. *Catalogues* — la liste exhaustive des classes de données de
...                 cette version, lue dans le dictionnaire (domaines ``CONTFLAG``
...                 et ``TABCLASS`` de ``DD07L``) et verrouillée par assertion :
...                 - classes de livraison : A, C, E, G, L, S, W ;
...                 - classes techniques : APPEND, INTTAB, TRANSP, VIEW
...                 (POOL/CLUSTER n'existent plus sur S/4HANA).
...
...                 2. *Inventaires* — les tables métier recensées par le
...                 référentiel (``TADIR``) : 27 objets TABL du modèle de vol
...                 (package ``SAPBC_DATAMODEL``, dont la structure ``SFL_AUX``)
...                 et 114 objets EPM (``SNWD_*``, dont 14 structures/includes
...                 non consultables).
...
...                 3. *Vérification en profondeur* — chaque table inventoriée est
...                 sondée via SE16 : ouverture de l'écran de sélection puis
...                 comptage « Number of Entries » (fiable même sur table vide) ;
...                 les structures doivent être rejetées avec un message de type
...                 ``E`` (assertion indépendante de la locale, jamais sur le texte).
...
...                 Ré-exécutable : aucune donnée modifiée (lecture seule, hors
...                 génération conditionnelle des données de démo au setup) ; aucun
...                 id SAP dans les tests (tout vit dans resources/). Exécution :
...
...                   robot --pythonpath src ^
...                     -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER ^
...                     -v "SAP_PASSWORD: Secret:***" -v SAP_CLIENT:001 -v SAP_LANGUAGE:EN ^
...                     --outputdir results/exploration tests/robot/ecc_exploration.robot
...
...                 Les balayages complets sont tagués ``deep`` :
...                 ``--exclude deep`` donne une passe rapide (catalogues + SFLIGHT).

Library             Collections
Resource            ../../resources/ecc_keywords.resource
Resource            ../../resources/a4h_demo_data.resource

Suite Setup         Run Keywords    Open SAP And Log In
...                 AND             Use ALV Grid In Data Browser
...                 AND             Ensure Flight Demo Data Exists
Suite Teardown      Close SAP

Test Tags           exploration


*** Variables ***
# Catalogues attendus — relevés live sur cette version (voir Documentation) ; un
# écart signale une dérive du dictionnaire (patch, autre release) et doit se voir.
@{EXPECTED_DELIVERY_CLASSES}    A    C    E    G    L    S    W
@{EXPECTED_TABLE_CLASSES}       APPEND    INTTAB    TRANSP    VIEW
# Noyau du modèle de vol : ces tables doivent exister dans tout inventaire sain.
@{CORE_FLIGHT_TABLES}           SBOOK    SCARR    SCUSTOM    SFLIGHT    SPFLI
${FLIGHT_PACKAGE}               SAPBC_DATAMODEL
${EPM_TABLE_PATTERN}            SNWD_*


*** Test Cases ***
Delivery Classes Catalog Is Exhaustive
    [Documentation]    Verrouille la liste exhaustive des classes de livraison
    ...    (« classes métier » des tables : A = données applicatives,
    ...    C = customizing, L = temporaire, G/E/S/W = système) telle que déclarée
    ...    par le dictionnaire de cette version.
    ${classes}=    Read Domain Values    CONTFLAG
    Lists Should Be Equal    ${classes}    ${EXPECTED_DELIVERY_CLASSES}
    ...    msg=Delivery-class catalog drifted on this SAP version

Table Classes Catalog Is Exhaustive
    [Documentation]    Verrouille les classes techniques de tables. Spécificité
    ...    S/4HANA : les classes POOL et CLUSTER ont disparu du catalogue.
    ${classes}=    Read Domain Values    TABCLASS
    Lists Should Be Equal    ${classes}    ${EXPECTED_TABLE_CLASSES}
    ...    msg=Table-class catalog drifted on this SAP version

Flight Model Inventory Contains The Core Tables
    [Documentation]    L'inventaire du référentiel (TADIR) pour le package du
    ...    modèle de vol recense bien les tables cœur du jeu de démo.
    ${tables}=    List Repository Tables    package=${FLIGHT_PACKAGE}
    Should Not Be Empty    ${tables}    msg=No table found in package ${FLIGHT_PACKAGE}
    FOR    ${core}    IN    @{CORE_FLIGHT_TABLES}
        Should Contain    ${tables}    ${core}
    END
    Log    ${{ len($tables) }} tables dans ${FLIGHT_PACKAGE} : ${tables}

Every Flight Model Table Is Countable Through SE16
    [Documentation]    Vérification en profondeur : chaque objet TABL du modèle
    ...    de vol est soit une table consultable répondant au comptage
    ...    « Number of Entries » (0 admis — une table vide reste consultable),
    ...    soit une structure proprement rejetée (message type ``E``, p.ex.
    ...    ``SFL_AUX``). Les tables cœur du jeu de démo doivent toutes être
    ...    dans le camp des consultables.
    [Tags]    deep
    ${objects}=    List Repository Tables    package=${FLIGHT_PACKAGE}
    Should Not Be Empty    ${objects}
    ${countable}=    Create List
    ${structures}=    Create List
    FOR    ${table}    IN    @{objects}
        ${ok}=    Try Open Table Selection Screen    ${table}
        IF    ${ok}
            ${count}=    Count Entries On Current Selection Screen
            Should Be True    ${count} >= 0
            Append To List    ${countable}    ${table}
            Log    ${table} -> ${count} entrées
        ELSE
            Append To List    ${structures}    ${table}
        END
    END
    Log    ${{ len($countable) }} tables comptées : ${countable}
    Log    ${{ len($structures) }} structures écartées : ${structures}
    FOR    ${core}    IN    @{CORE_FLIGHT_TABLES}
        Should Contain    ${countable}    ${core}
    END

SFLIGHT Demo Data Is Present And Readable
    [Documentation]    Cohérence compteur/grille sur la table garantie non vide par
    ...    le setup : comptage > 0, grille ALV lisible, colonne technique CARRID
    ...    présente (id technique, jamais le titre localisé).
    ${count}=    Count Table Entries    SFLIGHT
    Should Be True    ${count} > 0    msg=SFLIGHT is empty despite the demo-data guard
    Display Table Contents    SFLIGHT
    ${ids}=    Get Grid Column Ids    ${SE16_GRID}
    Should Contain    ${ids}    CARRID
    ${rows}=    Read Displayed Grid    max_rows=5
    Should Not Be Empty    ${rows}

Every EPM Object Is Accessible Or A Declared Structure
    [Documentation]    Balayage des objets TABL ``SNWD_*`` du référentiel : chacun
    ...    est soit une table consultable (écran de sélection + comptage >= 0),
    ...    soit rejeté proprement comme structure — message de statut de type
    ...    ``E``, seule assertion indépendante de la locale. Toute autre issue
    ...    (blocage, popup inattendu) fait échouer le test.
    [Tags]    deep
    ${names}=    List Repository Tables    name_pattern=${EPM_TABLE_PATTERN}
    Should Not Be Empty    ${names}    msg=No SNWD_* object found in TADIR
    ${tables}=    Create List
    ${structures}=    Create List
    FOR    ${name}    IN    @{names}
        ${ok}=    Try Open Table Selection Screen    ${name}
        IF    ${ok}
            ${count}=    Count Entries On Current Selection Screen
            Should Be True    ${count} >= 0
            Append To List    ${tables}    ${name}
        ELSE
            Append To List    ${structures}    ${name}
        END
    END
    Log    ${{ len($tables) }} tables consultables : ${tables}
    Log    ${{ len($structures) }} structures/includes écartées : ${structures}
    # Le cœur transactionnel EPM doit être consultable, et la structure connue rester écartée.
    Should Contain    ${tables}    SNWD_PO
    Should Not Be Empty    ${structures}
    Should Not Contain    ${tables}    SNWD_ADMIN_DATA
