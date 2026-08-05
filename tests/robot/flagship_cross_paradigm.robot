*** Settings ***
Documentation       Suite **flagship cross-paradigme** : un même fait métier vérifié
...                 par DEUX canaux indépendants : l'écran (GUI desktop ou Fiori web)
...                 ET l'API (OData via ``SapApiLibrary``). C'est la démonstration du
...                 principe d'architecture du projet (unifier au-dessus, dans le
...                 vocabulaire métier) et le patron recommandé : préparer/recouper
...                 par l'API, ne passer par l'écran que pour ce qu'on teste.
...
...                 Deux scénarios indépendants (tags ``a4h`` / ``capsflight`` pour
...                 les exécuter séparément) :
...
...                 1. **A4H (GUI ↔ API)** : le compte des produits EPM lu par SE16
...                 (« Number of Entries », table ``SNWD_PD``) doit égaler le
...                 ``$count`` du service OData Gateway ``SEPMRA_SHOP`` du même
...                 système. Prérequis : A4H Docker démarré, données EPM générées
...                 (``Ensure EPM Demo Data Exists``).
...
...                 2. **cap-sflight (Fiori ↔ API)** : la première ligne rendue par
...                 la List Report « Travel » existe côté OData v4 (requête point
...                 sur son Travel ID) et le service annonce des entités.
...                 Prérequis : ``npx cds watch`` dans ``_cap-sflight`` (:4004).
...
...                 Exécution complète :
...                   robot --pythonpath src -v SAP_CONNECTION:... -v SAP_USER:...
...                   -v "SAP_PASSWORD: Secret:..." -v SAP_CLIENT:001
...                   tests/robot/flagship_cross_paradigm.robot

# Les deux resources métier importent leurs bibliothèques (SapEccLibrary,
# Browser + SapFioriLibrary) ; leurs alias miroirs portent le même nom des
# deux côtés (exprès), d'où les appels ECC qualifiés `ecc_keywords.` ci-dessous.
Library             SapApiLibrary
Resource            ../../resources/ecc_keywords.resource
Resource            ../../resources/fiori_keywords.resource
Resource            ../../resources/a4h_demo_data.resource

# Les alias miroirs (Confirm/Cancel Popup, ...) existent dans les DEUX resources :
# la priorité va au côté ECC (les popups des guards EPM sont des popups SAP GUI) ;
# les keywords propres au web (Open Fiori Launchpad, Close Fiori) restent uniques.
Suite Setup         Set Library Search Order    ecc_keywords    fiori_keywords
Suite Teardown      Close All Api Sessions


*** Variables ***
# Gateway OData v2 embarquée de l'A4H (HTTP mappé par le conteneur Docker).
${A4H_API_URL}          http://vhcala4hci:50000
# Service EPM « Shop » (relevé au catalogue Gateway le 2026-07-13) et la table
# qu'il projette : le MÊME référentiel que SE16 côté GUI.
${EPM_PRODUCTS_PATH}    /sap/opu/odata/sap/SEPMRA_SHOP/Products
${EPM_PRODUCTS_TABLE}    SNWD_PD

# cap-sflight local : app Fiori Elements + service OData v4 du même process.
${SFLIGHT_URL}          http://localhost:4004/sap.fe.cap.travel/index.html
${TRAVEL_ENTITY_PATH}    /processor/Travel
${TRAVEL_TABLE_ID}      sap.fe.cap.travel::TravelList--fe::table::Travel::LineItem-innerTable


*** Test Cases ***
Products Count Matches Between SE16 And OData
    [Documentation]    Le compte GUI (SE16 « Number of Entries » sur ``SNWD_PD``)
    ...                et le compte API (``$count`` OData) du même système doivent
    ...                coïncider : toute divergence signale un service qui filtre
    ...                ou une donnée fantôme.
    [Tags]    a4h
    [Setup]    ecc_keywords.Open SAP And Log In
    Ensure EPM Demo Data Exists
    ${gui_count}=    Count Table Entries    ${EPM_PRODUCTS_TABLE}
    Should Be True    ${gui_count} > 0    msg=Table ${EPM_PRODUCTS_TABLE} vide malgré le guard EPM.
    Open Api Session    ${A4H_API_URL}    user=${SAP_USER}    password=${SAP_PASSWORD}
    ...    sap_client=${SAP_CLIENT}    alias=a4h
    ${api_count}=    Get Odata Count    ${EPM_PRODUCTS_PATH}    alias=a4h
    Should Be Equal As Integers    ${api_count}    ${gui_count}
    ...    msg=OData ${EPM_PRODUCTS_PATH} (${api_count}) ≠ SE16 ${EPM_PRODUCTS_TABLE} (${gui_count}).
    [Teardown]    ecc_keywords.Close SAP

Travel Row Rendered By Fiori Exists Through OData
    [Documentation]    Recoupement Fiori ↔ API sur cap-sflight : le service v4
    ...                annonce des entités, et le Travel ID de la première ligne
    ...                réellement rendue par la List Report se retrouve par une
    ...                requête OData point : l'écran n'invente pas de données.
    [Tags]    capsflight
    [Setup]    Open Fiori Launchpad    ${SFLIGHT_URL}
    Open Api Session    http://localhost:4004    alias=cap
    ${api_count}=    Get Odata Count    ${TRAVEL_ENTITY_PATH}    alias=cap
    Should Be True    ${api_count} > 0    msg=Aucun Travel côté OData : cds watch démarré ?
    Wait For UI5 Ready
    Ui5 Control Should Be Visible    controlType=ColumnListItem
    ${rows}=    Read Ui5 Table    id=${TRAVEL_TABLE_ID}
    Should Not Be Empty    ${rows}
    ${travel_id}=    Extract First Travel Id    ${rows}[0]
    ${entities}=    Get Odata Entities    ${TRAVEL_ENTITY_PATH}    alias=cap
    ...    filter=TravelID eq ${travel_id}
    Length Should Be    ${entities}    1
    ...    msg=Travel ID ${travel_id} affiché par l'app mais introuvable (ou multiple) via OData.
    [Teardown]    Close Fiori


*** Keywords ***
Extract First Travel Id
    [Documentation]    Le Travel ID d'une ligne lue par ``Read Ui5 Table`` : la
    ...                première valeur entièrement numérique de la ligne (les
    ...                en-têtes affichés varient avec la locale, pas le format de
    ...                l'identifiant).
    [Arguments]    ${row}
    FOR    ${value}    IN    @{row.values()}
        ${digits}=    Evaluate    str($value).strip().isdigit()
        IF    ${digits}    RETURN    ${value.strip()}
    END
    Fail    Aucune valeur numérique (Travel ID) dans la ligne : ${row}
