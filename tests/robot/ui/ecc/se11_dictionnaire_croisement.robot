*** Settings ***
Documentation       SE11 : l'affichage du dictionnaire ABAP croisé avec les tables
...                 Spec: specs/se11-dictionnaire-affichage-croisement-se16.md (sha256:e4ed4f84aa56, 2026-09-05)
...                 DD* lues par SE16. Campagne LECTURE SEULE, 7 scénarios.
...                 Spec: specs/se11-dictionnaire-affichage-croisement-se16.md
...                 Generated from specs/se11-dictionnaire-affichage-croisement-se16.md
...                 by sap-generator (re-run the generator rather than hand-editing
...                 locators here). Un test par scénario du plan, dans son ordre.
...
...                 L'écran SE11 est la DOCUMENTATION d'une vérité qui vit dans les
...                 tables du dictionnaire (DD02L, DD03L, DD07L) : chaque scénario
...                 confronte ce que SE11 AFFICHE à ce que SE16 LIT dans ces tables.
...                 Les assertions portent sur des valeurs TECHNIQUES (ids de champs,
...                 classes `TRANSP`/`CONTFLAG=L`/`AS4LOCAL=A`, types de message,
...                 numéros de dynpro) et sur des entiers, jamais sur un texte
...                 localisé (« Transparent Table », « Active », descriptions de
...                 valeurs fixes, format de date : convention 3). Aucun localisateur
...                 ici (convention 1) : ils vivent dans le page object
...                 `resources/page_objects/se11_dictionary_display.resource` et dans
...                 la bibliothèque (écrans SE16 standard).
...
...                 LECTURE SEULE de bout en bout : mode Display seulement, F3 pour
...                 revenir, teardown `Close SAP` même sur échec. Le seul réglage
...                 persistant touché est `Use ALV Grid In Data Browser`, que toutes
...                 les suites SE16 posent déjà.
...
...                 Exécution (A4H ou tout système de test) :
...
...                 robot --pythonpath src --outputdir results/se11_campagne ^
...                 -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER ^
...                 -v "SAP_PASSWORD: Secret:..." -v SAP_CLIENT:001 ^
...                 tests/robot/ui/ecc/se11_dictionnaire_croisement.robot

Resource            ../../../../resources/page_objects/se11_dictionary_display.resource

Suite Setup         Open Campaign
Suite Teardown      Close SAP

Test Tags           ecc    ddic    se11    a4h


*** Variables ***
${TABLE}            SNWD_PD
${DOMAIN}           CONTFLAG
${DATA_ELEMENT}     SNWD_PRODUCT_ID
${KEY_FIELD_A}      CLIENT
${KEY_FIELD_B}      NODE_KEY
${NON_KEY_FIELD}    PRODUCT_ID
${STRUCTURE}        SNWD_ADMIN_DATA
${MISSING_OBJECT}    ZZNOPE_404


*** Test Cases ***
L'en-tête SE11 d'une table dit ce que DD02L enregistre
    [Documentation]    Scénario 1 : l'écran table SE11 est atteint (programme
    ...                SAPLSD41, dynpro 2200), l'en-tête relit le nom demandé, et
    ...                DD02L confirme la classe technique (TRANSP) et la version
    ...                active (A). Aucune assertion sur les textes localisés.
    ${name}=    Display Se11 Table    ${TABLE}
    Should Be Equal    ${name}    ${TABLE}
    ${domain}=    Read Domain Values    TABCLASS
    ${class_map}=    Get Ddic Classification Map    ${domain}
    ${names}=    Create List    ${TABLE}
    ${classified}=    Classify Ddic Objects    ${names}    ${class_map}
    ${entry}=    Set Variable    ${classified}[${TABLE}]
    Should Be True    ${entry}[ddic][present]
    ...    msg=${TABLE} est absente de DD02L.
    Should Be Equal    ${entry}[ddic][tabclass]    TRANSP
    Should Be Equal    ${entry}[ddic][as4local]    A

Assertion reine : l'onglet Fields = DD03L, champ à champ
    [Documentation]    Scénario 2 : l'onglet Fields de SE11 égale le contrat de
    ...                champs DD03L : même séquence de noms (26 = 26, ordre
    ...                compris), mêmes éléments de données et mêmes longueurs
    ...                (entiers) pour tout champ qui n'est pas un `.INCLUDE`.
    Display Se11 Table    ${TABLE}
    ${se11_fields}=    Read Se11 Table Fields
    ${dd03l_fields}=    Read Ddic Table Fields    ${TABLE}
    Length Should Be    ${se11_fields}    26
    Length Should Be    ${dd03l_fields}    26
    Se11 Fields Should Match Dd03l    ${se11_fields}    ${dd03l_fields}

Les clés cochées dans SE11 sont les clés de DD03L
    [Documentation]    Scénario 3 : les cases Key cochées côté SE11 sont
    ...                exactement les lignes KEYFLAG='X' de DD03L. La colonne Key
    ...                est lue en drapeau ABAP par `Read Table Control` (aucun
    ...                contournement `Get Value`), directement croisable avec
    ...                KEYFLAG. Contre-épreuve : PRODUCT_ID décoché des deux côtés.
    Display Se11 Table    ${TABLE}
    ${se11_fields}=    Read Se11 Table Fields
    ${se11_keys}=    Read Se11 Key Fields    ${se11_fields}
    ${dd03l_fields}=    Read Ddic Table Fields    ${TABLE}
    ${dd03l_keys}=    Evaluate    sorted(r['FIELDNAME'] for r in $dd03l_fields if r.get('KEYFLAG') == 'X')
    ${expected}=    Create List    ${KEY_FIELD_A}    ${KEY_FIELD_B}
    Should Be Equal    ${se11_keys}    ${expected}
    Should Be Equal    ${dd03l_keys}    ${expected}
    Should Not Contain    ${se11_keys}    ${NON_KEY_FIELD}
    ...    msg=${NON_KEY_FIELD} ne doit pas être une clé (contre-épreuve).

La classe de livraison affichée = DD02L.CONTFLAG lu en sortie de grille
    [Documentation]    Scénario 4 : la valeur technique de la classe de livraison
    ...                lue sur l'onglet Delivery and Maintenance de SE11 égale la
    ...                colonne CONTFLAG de DD02L (lue par SE16, filtre par NOM), et
    ...                cette valeur appartient au catalogue du domaine CONTFLAG
    ...                (DD07L). Aucune assertion sur le texte descriptif (localisé).
    Display Se11 Table    ${TABLE}
    ${se11_contflag}=    Read Se11 Delivery Class
    Should Not Be Empty    ${se11_contflag}
    ${header}=    Read Ddic Table Header    ${TABLE}
    Should Be Equal    ${se11_contflag}    ${header}[CONTFLAG]
    ${domain_values}=    Read Domain Values    ${DOMAIN}
    Should Contain    ${domain_values}    ${se11_contflag}
    ...    msg=La classe ${se11_contflag} n'est pas dans le catalogue du domaine ${DOMAIN}.

Le domaine : valeurs fixes SE11 = DD07L, définition technique relevée
    [Documentation]    Scénario 5 : l'écran domaine SE11 est atteint (programme
    ...                SAPLSD11, dynpro 1200) ; la définition technique est relevée
    ...                (CHAR/1/0) ; l'ensemble des valeurs fixes de l'onglet Value
    ...                Range, TRIÉ, égale la liste DD07L (l'ordre SE11 est l'ordre
    ...                de maintenance, pas l'ordre trié).
    ${name}=    Display Se11 Domain    ${DOMAIN}
    Should Be Equal    ${name}    ${DOMAIN}
    ${definition}=    Read Se11 Domain Definition
    Should Be Equal    ${definition}[DATATYPE]    CHAR
    Should Be Equal As Integers    ${definition}[LENG]    1
    Should Be Equal As Integers    ${definition}[DECIMALS]    0
    ${fixed}=    Read Se11 Domain Fixed Values
    Length Should Be    ${fixed}    7
    ${fixed_sorted}=    Evaluate    sorted($fixed)
    ${dd07l}=    Read Domain Values    ${DOMAIN}
    Should Be Equal    ${fixed_sorted}    ${dd07l}
    ...    msg=Les valeurs fixes SE11 (triées) ne correspondent pas à DD07L.

Navigation interne : du champ à son élément de données, et retour
    [Documentation]    Scénario 6 : depuis l'onglet Fields, F2 sur la cellule Data
    ...                element de PRODUCT_ID atteint l'écran élément de données
    ...                (SAPLSD51, dynpro 1000) ; nom, type, longueur et ABSENCE de
    ...                domaine concordent avec la ligne DD03L de PRODUCT_ID (un
    ...                domaine vide des deux côtés est une assertion) ; F3 restaure
    ...                l'écran table avec le bon nom.
    Display Se11 Table    ${TABLE}
    Open Data Element From Se11 Field    ${NON_KEY_FIELD}
    ${de_type}=    Read Se11 Data Element Type
    Should Be Equal    ${de_type}[ROLLNAME]    ${DATA_ELEMENT}
    Should Be Empty    ${de_type}[DOMNAME]
    ...    msg=${DATA_ELEMENT} est un type prédéfini : son domaine doit être vide.
    Should Be Equal    ${de_type}[DATATYPE]    CHAR
    Return To Previous Ddic Object
    ${kind}=    Get Se11 Current Object Kind
    Should Be Equal    ${kind}    table
    ...    msg=F3 n'a pas restauré l'écran table.
    ${back_name}=    Get Value    ${SE11_TABLE_HEADER_NAME}
    Should Be Equal    ${back_name}    ${TABLE}
    # Croisement DD03L de la ligne PRODUCT_ID (la lecture SE16 quitte l'écran table).
    ${dd03l_fields}=    Read Ddic Table Fields    ${TABLE}
    ${pid}=    Evaluate    next(r for r in $dd03l_fields if r['FIELDNAME'] == '${NON_KEY_FIELD}')
    Should Be Equal    ${pid}[ROLLNAME]    ${DATA_ELEMENT}
    Should Be Empty    ${pid}[DOMNAME]
    Should Be Equal    ${pid}[DATATYPE]    CHAR
    Should Be Equal As Integers    ${de_type}[LENG]    ${pid}[LENG]

Branches d'erreur : l'objet inexistant et la structure déguisée
    [Documentation]    Scénario 7 : un objet inexistant laisse l'écran initial
    ...                (SAPLSD_ENTRY, dynpro 1000) inchangé avec un message de type
    ...                S (le refus SE11 EST un S : jamais asserter « pas de E ») ;
    ...                une structure demandée comme table est REDIRIGÉE vers le
    ...                dynpro 2100 (Display Structure) sans message, là où SE16 la
    ...                refuse en type E (contre-épreuve).
    Open Se11 Object Display    table    ${MISSING_OBJECT}
    ${type}=    Se11 Display Should Stay On Initial Screen
    Should Be Equal    ${type}    S
    ...    msg=Le refus d'un objet inexistant devrait être un message de type S.
    Open Se11 Object Display    table    ${STRUCTURE}
    ${kind}=    Get Se11 Current Object Kind
    Should Be Equal    ${kind}    structure
    ...    msg=Une structure demandée comme table devrait être redirigée vers l'écran structure.
    ${se16_state}=    Reach Table Selection Screen    ${STRUCTURE}
    Should Not Be True    ${se16_state}[reached]
    Should Be Equal    ${se16_state}[message_type]    E
    ...    msg=SE16 devrait rejeter la structure ${STRUCTURE} par un message de type E.


*** Keywords ***
Open Campaign
    [Documentation]    Suite Setup : session unique, préflight scripting, sortie
    ...                SE16 en grille ALV (les lectures DD02L/DD03L/DD07L en
    ...                dépendent). Réglage persistant idempotent, aucune donnée
    ...                modifiée.
    Open SAP And Log In
    Scripting Should Be Fully Enabled
    Use ALV Grid In Data Browser
