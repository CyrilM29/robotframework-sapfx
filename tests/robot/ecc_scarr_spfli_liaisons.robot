*** Settings ***
Documentation       Compagnies aériennes et liaisons de vol (SCARR / SPFLI) via
...                 Spec: specs/scarr-spfli-liaisons-se16.md (sha256:131c929e92cf, 2026-08-04)
...                 SE16: generated from specs/scarr-spfli-liaisons-se16.md by
...                 sap-generator (re-run the generator rather than hand-editing
...                 locators here). Un test par scénario de la spec, dans son
...                 ordre. Périmètre strictement consultation (SE16 display /
...                 « Number of Entries »), assertions indépendantes de la locale
...                 (ids techniques de colonnes, comptes, inclusions ; convention
...                 3) et relationnelles plutôt que calées sur le jeu de démo
...                 (LH > AA > 0, somme des comptes par compagnie = total,
...                 porteurs ⊂ catalogue) partout où la spec le permet. Exécution :
...
...                   robot --pythonpath src ^
...                     -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER ^
...                     -v "SAP_PASSWORD: Secret:***" -v SAP_CLIENT:001 ^
...                     --outputdir results/generate tests/robot/ecc_scarr_spfli_liaisons.robot

Resource            ../../resources/ecc_keywords.resource
Resource            ../../resources/a4h_demo_data.resource

Suite Setup         Run Keywords    Open SAP And Log In
...                 AND             Scripting Should Be Fully Enabled
...                 AND             Use ALV Grid In Data Browser
...                 AND             Ensure Flight Demo Data Exists
Suite Teardown      Close SAP

Test Tags           se16    flight-connections


*** Variables ***
# Données métier du jeu de démo vol (valeurs de données, pas des ids SAP ;
# convention 1 respectée : aucun localisateur ici, tout vit dans resources/).
@{WELL_KNOWN_CARRIERS}      AA    LH    SQ    # codes attendus au catalogue SCARR
${BUSY_CARRIER}             LH                # compagnie la plus desservie du jeu de démo
${QUIET_CARRIER}            AA                # compagnie avec peu de liaisons (> 0)
${UNKNOWN_CARRIER}          XX                # code hors catalogue : compte 0 attendu
${DETAIL_CARRIER}           LH                # liaison connue pour la lecture ciblée…
${DETAIL_CONNECTION}        0400              # …CONNID comparé en chaîne (zéros de tête)
${DETAIL_AIRPORT_FROM}      FRA
${DETAIL_AIRPORT_TO}        JFK
${DETAIL_DISTANCE_UNIT}     KM
${GRID_READ_CAP}            200               # ≥ MAX_SEL par défaut, couvre tout le jeu de démo


*** Test Cases ***
Le catalogue des compagnies contient des données
    [Documentation]    Scénario 1 : SCARR compte un nombre d'entrées strictement
    ...    positif (18 observé sur le jeu standard ; assertion relationnelle,
    ...    pas d'égalité dure).
    ${count}=    Count Table Entries    SCARR
    Should Be True    ${count} > 0    msg=SCARR is empty: flight demo data missing despite the suite-setup guard

Le catalogue des compagnies s'affiche avec ses colonnes techniques
    [Documentation]    Scénario 2 : la grille SCARR expose les ids techniques
    ...    CARRID/CARRNAME/CURRCODE (jamais les titres affichés), contient au
    ...    moins une ligne, et les codes bien connus figurent parmi les CARRID.
    Display Table Contents    SCARR
    Displayed Grid Should Contain Columns    CARRID    CARRNAME    CURRCODE
    ${rows}=    Read Displayed Grid    max_rows=${GRID_READ_CAP}
    Should Not Be Empty    ${rows}
    ${codes}=    Read Column Values From Displayed Grid    CARRID    max_rows=${GRID_READ_CAP}    unique=True
    FOR    ${code}    IN    @{WELL_KNOWN_CARRIERS}
        Should Contain    ${codes}    ${code}    values=False
        ...    msg=Carrier '${code}' missing from the SCARR catalog (read: ${codes})
    END

La table des liaisons contient des données
    [Documentation]    Scénario 3 : SPFLI compte un nombre d'entrées strictement
    ...    positif (14 observé sur le jeu standard).
    ${count}=    Count Table Entries    SPFLI
    Should Be True    ${count} > 0    msg=SPFLI is empty: flight demo data missing despite the suite-setup guard

Compter les liaisons d'une compagnie donnée
    [Documentation]    Scénario 4 : comptage filtré par CARRID via « Number of
    ...    Entries » : compte(LH) > compte(AA) > 0 (4 et 1 observés), puis
    ...    recoupement : la somme des comptes par compagnie porteuse égale le
    ...    compte total de SPFLI.
    ${lh}=    Count Flight Connections For Airline    ${BUSY_CARRIER}
    ${aa}=    Count Flight Connections For Airline    ${QUIET_CARRIER}
    Should Be True    ${lh} > ${aa}    msg=Expected ${BUSY_CARRIER} (${lh}) to serve more connections than ${QUIET_CARRIER} (${aa})
    Should Be True    ${aa} > 0    msg=Expected ${QUIET_CARRIER} to serve at least one connection
    ${total}=    Count Table Entries    SPFLI
    Display Table Contents    SPFLI
    ${carriers}=    Read Column Values From Displayed Grid    CARRID    max_rows=${GRID_READ_CAP}    unique=True
    ${sum}=    Set Variable    ${0}
    FOR    ${carrid}    IN    @{carriers}
        ${n}=    Count Flight Connections For Airline    ${carrid}
        ${sum}=    Evaluate    ${sum} + ${n}
    END
    Should Be Equal As Integers    ${sum}    ${total}
    ...    msg=Per-carrier counts (${sum}) do not add up to the SPFLI total (${total})

Une compagnie sans liaison donne un compte zéro, sans erreur
    [Documentation]    Scénario 5 : un CARRID hors catalogue compte 0 sans message
    ...    d'erreur ni popup résiduel, et l'écran de sélection reste utilisable.
    ...    Variante métier : un code du catalogue sans liaison (dérivé
    ...    dynamiquement : catalogue − porteurs) compte aussi 0.
    ${none}=    Count Flight Connections For Airline    ${UNKNOWN_CARRIER}
    Should Be Equal As Integers    ${none}    0
    ...    msg=Unknown carrier '${UNKNOWN_CARRIER}' should count zero connections
    ${residual}=    Popup Is Present
    Should Not Be True    ${residual}    msg=The count popup was not closed cleanly
    ${again}=    Count Entries On Current Selection Screen
    Should Be Equal As Integers    ${again}    0
    ...    msg=The selection screen should stay usable after a zero count
    Display Table Contents    SCARR
    ${catalog}=    Read Column Values From Displayed Grid    CARRID    max_rows=${GRID_READ_CAP}    unique=True
    Display Table Contents    SPFLI
    ${connected}=    Read Column Values From Displayed Grid    CARRID    max_rows=${GRID_READ_CAP}    unique=True
    ${without}=    Evaluate    sorted(set($catalog) - set($connected))
    IF    $without
        ${zero}=    Count Flight Connections For Airline    ${without}[0]
        Should Be Equal As Integers    ${zero}    0
        ...    msg=Carrier '${without}[0]' is in the catalog with no connection: its count must be zero
    END

Toute liaison référence une compagnie du catalogue
    [Documentation]    Scénario 6, intégrité référentielle : l'ensemble des
    ...    CARRID porteurs de liaisons (SPFLI) est inclus dans le catalogue
    ...    (SCARR). Assertion ensembliste sur ids techniques, indépendante de la
    ...    locale et du tri d'affichage.
    Display Table Contents    SCARR
    ${catalog}=    Read Column Values From Displayed Grid    CARRID    max_rows=${GRID_READ_CAP}    unique=True
    Display Table Contents    SPFLI
    ${connected}=    Read Column Values From Displayed Grid    CARRID    max_rows=${GRID_READ_CAP}    unique=True
    Should Not Be Empty    ${connected}
    ${orphans}=    Evaluate    sorted(set($connected) - set($catalog))
    Should Be Empty    ${orphans}
    ...    msg=SPFLI references carriers missing from the SCARR catalog: ${orphans}

Détail d'une liaison connue (lecture ciblée)
    [Documentation]    Scénario 7 : filtre CARRID+CONNID sur l'écran de sélection
    ...    puis lecture de la grille : exactement une ligne, aéroports et unité
    ...    de distance attendus (valeurs de données stables quelle que soit la
    ...    langue) ; CONNID comparé en chaîne (zéros de tête).
    Display Table Contents With Filter    SPFLI
    ...    CARRID=${DETAIL_CARRIER}    CONNID=${DETAIL_CONNECTION}
    ${rows}=    Read Displayed Grid    max_rows=5
    Length Should Be    ${rows}    1
    ...    msg=Expected exactly one connection for ${DETAIL_CARRIER} ${DETAIL_CONNECTION}
    Should Be Equal As Strings    ${rows}[0][CONNID]    ${DETAIL_CONNECTION}
    Should Be Equal As Strings    ${rows}[0][AIRPFROM]    ${DETAIL_AIRPORT_FROM}
    Should Be Equal As Strings    ${rows}[0][AIRPTO]    ${DETAIL_AIRPORT_TO}
    Should Be Equal As Strings    ${rows}[0][DISTID]    ${DETAIL_DISTANCE_UNIT}
