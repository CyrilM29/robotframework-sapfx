*** Settings ***
Documentation       **EXEMPLE À PERSONNALISER.** Page object de l'application
...                 « Travel processor » de **cap-sflight** (Fiori Elements v4,
...                 servie en local par `npx cds watch`), la cible UI5 du dépôt
...                 qui ne demande ni système SAP ni identifiants.
...
...                 Les identifiants de contrôle sont ceux que Fiori Elements
...                 GÉNÈRE (`fe::table::Travel::LineItem-innerTable`) : stables
...                 pour une application donnée, propres à elle. Sur une autre
...                 application, ils changent et ce fichier est à refaire ;
...                 c'est l'objet même d'un page object (convention 1).
...
...                 **Ce que ce page object encode et qui vaut pour toute table
...                 UI5** : une table rend ses lignes INSTANCIÉES et déclare son
...                 total ailleurs. Mesuré le 2026-09-15 : la List Report rend
...                 30 lignes (son seuil de croissance) quand le binding en
...                 déclare 4133, et les 30 sont parfaitement remplies. Aucune
...                 ligne vide, aucune numérotation qui saute : rien ne trahit
...                 l'amputation. Les keywords ci-dessous rendent donc TOUJOURS
...                 le relevé avec son total déclaré.

Library             Browser
Library             Collections
Resource            ../fiori_keywords.resource


*** Variables ***
${CAPSFLIGHT_URL}               http://localhost:4004/sap.fe.cap.travel/index.html
# La `sap.m.Table` INTERNE : c'est elle qui matérialise les lignes, le wrapper
# `sap.ui.mdc.Table` ne les expose pas.
${CAPSFLIGHT_LIST_TABLE}        sap.fe.cap.travel::TravelList--fe::table::Travel::LineItem-innerTable
# La table des réservations d'une fiche voyage : petite, et ENTIÈREMENT
# matérialisée, donc extractible en totalité. Le contraste avec la table
# ci-dessus est le sujet de la suite qui importe ce fichier.
${CAPSFLIGHT_BOOKING_TABLE}     sap.fe.cap.travel::TravelObjectPage--fe::CustomSubSection::CustomSection--bookingTable-content-innerTable
# Le temps que l'application compile et charge ses données au premier accès :
# `npx cds watch` compile à la volée, donc le tout premier rendu est lent.
${CAPSFLIGHT_TIMEOUT}           60s


*** Keywords ***
Ouvrir Le Parcours Voyages
    [Documentation]    Ouvre l'application et attend que la List Report ait
    ...                RÉELLEMENT chargé ses données. « Runtime prêt » ne veut
    ...                pas dire « données arrivées » : l'attente porte donc sur
    ...                la table, pas sur le moteur.
    [Arguments]    ${url}=${CAPSFLIGHT_URL}    ${headless}=${True}
    New Browser    chromium    headless=${headless}
    New Context
    Set Browser Timeout    ${CAPSFLIGHT_TIMEOUT}
    Set Ui5 Timeout    ${CAPSFLIGHT_TIMEOUT}
    New Page    ${url}
    Wait For UI5 Ready
    Wait Until Keyword Succeeds    ${CAPSFLIGHT_TIMEOUT}    1s
    ...    La Table Devrait Avoir Charge    ${CAPSFLIGHT_LIST_TABLE}

La Table Devrait Avoir Charge
    [Documentation]    Assertion instantanée : la table a rendu au moins une
    ...                ligne. La forme à sonder dans un
    ...                `Wait Until Keyword Succeeds`.
    [Arguments]    ${table_id}
    ${info}=    Get Ui5 Table Info    id=${table_id}
    Should Be True    ${info}[rendered_rows] > 0
    ...    msg=La table ${table_id} n'a encore rendu aucune ligne (déclarées : ${info}[declared_rows]).
    RETURN    ${info}

Ouvrir La Premiere Fiche Voyage
    [Documentation]    Ouvre la fiche du premier voyage de la liste et attend
    ...                que sa table de réservations ait chargé.
    Click Ui5 Control    controlType=ColumnListItem
    Wait Until Keyword Succeeds    ${CAPSFLIGHT_TIMEOUT}    1s
    ...    La Table Devrait Avoir Charge    ${CAPSFLIGHT_BOOKING_TABLE}

Extraire La Table Affichee
    [Documentation]    Lit une table UI5 et rend le relevé AVEC son contrat,
    ...                sous la forme commune aux trois canaux.
    ...
    ...                Les clés des colonnes sont les **titres affichés**, et
    ...                c'est une propriété du canal, pas un choix : contrairement
    ...                à l'ALV et au WebGUI, qui exposent tous deux des
    ...                identifiants techniques, une table UI5 n'expose que le
    ...                libellé de ses colonnes, donc LOCALISÉ. Une assertion
    ...                portée sur un nom de colonne est ici une assertion sur
    ...                une traduction (convention 3) : la suite qui importe ce
    ...                fichier le constate au lieu de le masquer.
    [Arguments]    ${table_id}    ${source}
    ${info}=    Get Ui5 Table Info    id=${table_id}
    ${lignes}=    Read Ui5 Table    id=${table_id}
    # `declared_final` part dans le contrat COMMUN, et non dans une assertion de
    # scénario : un binding qui n'a pas fini de compter rend un total qui ne
    # borne rien, et l'égalité « lu = déclaré » y est vraie un instant puis
    # fausse le suivant. Laissé au seul scénario, ce contrôle disparaissait dès
    # qu'on jouait une extraction seule, ce que la suite encourage pourtant.
    ${extrait}=    Build Table Extract    ${lignes}    columns=${info}[columns]
    ...    declared_rows=${info}[declared_rows]    declared_final=${info}[length_final]
    ...    source=${source}
    Set To Dictionary    ${extrait}    ui5_type=${info}[type]
    ...    growing_threshold=${info}[growing_threshold]    length_final=${info}[length_final]
    RETURN    ${extrait}

Fermer Le Parcours Voyages
    [Documentation]    Ferme le navigateur. Aucune donnée n'a été touchée : ce
    ...                parcours est en LECTURE SEULE.
    Close Browser
