*** Settings ***
Documentation       **EXEMPLE À PERSONNALISER** : ce fichier porte le vocabulaire
...                 métier du LABORATOIRE de ce dépôt (identifiants d'écran, chemins
...                 de contrôles et noms d'objets relevés live sur SES cibles).
...                 Beaucoup s'y réutilise tel quel sur un autre système (SE11 est un
...                 écran standard), mais rien n'y fait autorité : à VÉRIFIER sur
...                 votre cible et à adapter à votre métier. Ce qui fait foi partout,
...                 c'est `src/`, les bibliothèques, qui portent les capacités : voir
...                 `resources/README.md`.
...
...                 Page object de l'**affichage du dictionnaire ABAP (SE11)** en
...                 mode Display (lecture seule stricte) : écran initial, affichage
...                 d'une table (en-tête, onglet Fields, onglet Delivery and
...                 Maintenance), affichage d'un domaine (Definition, Value Range),
...                 affichage d'un élément de données, navigation interne du champ
...                 vers son élément de données, et le verdict structurel des
...                 branches d'erreur (objet inexistant, structure déguisée en
...                 table). Ses localisateurs `RSRD1-*`, `DD02D-*`, `DD01D-*`,
...                 `DD04D-*` et les chemins de table controls vivent ICI
...                 (convention 1) ; la suite parle métier.
...
...                 Contrat d'assertion : les verdicts portent sur le PROGRAMME et le
...                 NUMÉRO de dynpro (carte `Get Se11 Current Object Kind`), sur le
...                 TYPE du message de statut (`S`, `E`), sur des ids TECHNIQUES de
...                 champs et sur des entiers, jamais sur un texte localisé
...                 (« Transparent Table », « Active », descriptions de valeurs
...                 fixes, format de date : convention 3). LECTURE SEULE de bout en
...                 bout : mode Display seulement, F3 pour revenir, aucune écriture.

Resource            ../ecc_keywords.resource


*** Variables ***
# --- Écran initial SE11 (SAPLSD_ENTRY/SE11/1000) : radios et champs appariés ---
${SE11_RADIO_TABLE}             wnd[0]/usr/radRSRD1-TBMA
${SE11_TABLE_NAME_FIELD}        wnd[0]/usr/ctxtRSRD1-TBMA_VAL
${SE11_RADIO_DOMAIN}            wnd[0]/usr/radRSRD1-DOMA
${SE11_DOMAIN_NAME_FIELD}       wnd[0]/usr/ctxtRSRD1-DOMA_VAL
${SE11_DISPLAY_BUTTON}          wnd[0]/usr/btnPUSHSHOW    # « Display » : la voie lecture seule

# --- Affichage d'une TABLE (SAPLSD41/SE11/2200) ------------------------------
${SE11_TABLE_HEADER_NAME}       wnd[0]/usr/ctxtDD02D-DBTABNAME
${SE11_TAB_FIELDS}              wnd[0]/usr/tabsTAB_STRIP/tabpDEF
${SE11_TABLE_FIELDS_TC}         wnd[0]/usr/tabsTAB_STRIP/tabpDEF/ssubTS_SCREEN:SAPLSD41:2201/tblSAPLSD41TC0
# Colonne « Data element » (ROLLNAME) dans la cellule du table control Fields :
# indice de COLONNE 0-based (Field=0, Key=1, Initial Values=2, Data element=3).
${SE11_FIELDS_ROLLNAME_COL}     3
${SE11_TAB_DELIVERY}            wnd[0]/usr/tabsTAB_STRIP/tabpMAIN
${SE11_DELIVERY_CLASS_FIELD}    wnd[0]/usr/tabsTAB_STRIP/tabpMAIN/ssubTS_SCREEN:SAPLSD41:2202/ctxtDD02D-CONTFLAG

# --- Affichage d'un DOMAINE (SAPLSD11/SE11/1200) -----------------------------
${SE11_DOMAIN_HEADER_NAME}      wnd[0]/usr/txtDD01D-DOMNAME
${SE11_TAB_DOMAIN_DEF}          wnd[0]/usr/tabsTAB_STRIP/tabpTAB1
${SE11_DOMAIN_DATATYPE}         wnd[0]/usr/tabsTAB_STRIP/tabpTAB1/ssubTS_SCREEN:SAPLSD11:1201/ctxtDD01D-DATATYPE
${SE11_DOMAIN_LENG}             wnd[0]/usr/tabsTAB_STRIP/tabpTAB1/ssubTS_SCREEN:SAPLSD11:1201/txtDD01D-LENG
${SE11_DOMAIN_DECIMALS}         wnd[0]/usr/tabsTAB_STRIP/tabpTAB1/ssubTS_SCREEN:SAPLSD11:1201/txtDD01D-DECIMALS
${SE11_TAB_DOMAIN_VALUES}       wnd[0]/usr/tabsTAB_STRIP/tabpTAB2
${SE11_DOMAIN_FIXED_VALUES_TC}    wnd[0]/usr/tabsTAB_STRIP/tabpTAB2/ssubTS_SCREEN:SAPLSD11:1202/tblSAPLSD11TC0

# --- Affichage d'un ÉLÉMENT DE DONNÉES (SAPLSD51/SE11/1000) -------------------
${SE11_DE_HEADER_NAME}          wnd[0]/usr/txtDD04D-ROLLNAME
${SE11_DE_DOMNAME}              wnd[0]/usr/tabsTS/tabpTYPE/ssubSUB_DATA:SAPLSD51:1002/ctxtDD04D-DOMNAME
${SE11_DE_DATATYPE}             wnd[0]/usr/tabsTS/tabpTYPE/ssubSUB_DATA:SAPLSD51:1002/ctxtDD04D-DATATYPE
${SE11_DE_LENG}                 wnd[0]/usr/tabsTS/tabpTYPE/ssubSUB_DATA:SAPLSD51:1002/txtDD04D-LENG

# --- Carte programme/dynpro -> nature d'objet (ancre locale-safe) ------------
# Clé « PROGRAMME/DYNPRO » ; la nature est indépendante des titres localisés.
&{SE11_OBJECT_KIND_MAP}
...    SAPLSD_ENTRY/1000=initial
...    SAPLSD41/2200=table
...    SAPLSD41/2100=structure
...    SAPLSD11/1200=domain
...    SAPLSD51/1000=data_element


*** Keywords ***
Get Se11 Current Object Kind
    [Documentation]    Nature de l'écran SE11 courant, dérivée du PROGRAMME et du
    ...                NUMÉRO de dynpro (jamais du titre localisé) : ``initial`` |
    ...                ``table`` | ``structure`` | ``domain`` | ``data_element``,
    ...                ou ``unknown/<programme>/<dynpro>`` pour un écran hors carte.
    ...                La première ligne de `Get Screen Signature` porte
    ...                ``# screen <Programme>/<Transaction>/<Dynpro>``.
    ${sig}=    Get Screen Signature
    ${header}=    Evaluate    $sig.splitlines()[0]
    ${parts}=    Evaluate    $header.replace('# screen', '').strip().split('/')
    ${program}=    Set Variable    ${parts}[0]
    ${dynpro}=    Set Variable    ${parts}[-1]
    ${key}=    Set Variable    ${program}/${dynpro}
    ${kind}=    Get From Dictionary    ${SE11_OBJECT_KIND_MAP}    ${key}
    ...    default=unknown/${key}
    RETURN    ${kind}

Open Se11 Object Display
    [Documentation]    Ouvre SE11, sélectionne la catégorie d'objet
    ...                (``table`` ou ``domain``), saisit le nom et clique
    ...                « Display » (mode lecture seule). Repart toujours de
    ...                l'écran initial. Ne présume PAS de l'écran atteint : le
    ...                verdict est laissé aux keywords de lecture / à
    ...                `Get Se11 Current Object Kind` (une structure demandée
    ...                comme table est redirigée sans refus).
    [Arguments]    ${object_kind}    ${name}
    Go To Transaction    SE11
    IF    '${object_kind}' == 'table'
        Select Radio Button    ${SE11_RADIO_TABLE}
        Input Text    ${SE11_TABLE_NAME_FIELD}    ${name}
    ELSE IF    '${object_kind}' == 'domain'
        Select Radio Button    ${SE11_RADIO_DOMAIN}
        Input Text    ${SE11_DOMAIN_NAME_FIELD}    ${name}
    ELSE
        Fail    Catégorie d'objet SE11 non gérée : ${object_kind} (table|domain)
    END
    Click Element    ${SE11_DISPLAY_BUTTON}
    Wait Until Busy Done

Display Se11 Table
    [Documentation]    Affiche une table du dictionnaire en SE11 et vérifie que
    ...                l'écran table est bien atteint (programme ``SAPLSD41``,
    ...                dynpro ``2200``). Le nom relu dans l'en-tête est retourné.
    [Arguments]    ${table}
    Open Se11 Object Display    table    ${table}
    Wait Until Element Present    ${SE11_TABLE_HEADER_NAME}
    ${kind}=    Get Se11 Current Object Kind
    Should Be Equal    ${kind}    table
    ...    msg=Écran table SE11 non atteint pour ${table} (nature : ${kind}).
    ${name}=    Get Value    ${SE11_TABLE_HEADER_NAME}
    RETURN    ${name}

Read Se11 Table Fields
    [Documentation]    Liste des champs de l'onglet Fields d'une table SE11
    ...                (lecture du GuiTableControl : une ligne par champ, colonnes
    ...                ``Field``, ``Key``, ``Data element``, ``Data Type``,
    ...                ``Length``…). La colonne ``Key`` est une checkbox rendue en
    ...                drapeau ABAP (``X``/vide) par `Read Table Control`,
    ...                directement croisable avec ``KEYFLAG`` de DD03L.
    Click Element    ${SE11_TAB_FIELDS}
    Wait Until Busy Done
    ${rows}=    Read Table Control    ${SE11_TABLE_FIELDS_TC}
    RETURN    ${rows}

Read Se11 Key Fields
    [Documentation]    Ensemble TRIÉ des noms de champs dont la case ``Key`` est
    ...                cochée, dérivé des lignes déjà lues par
    ...                `Read Se11 Table Fields` (aucune relecture d'écran, aucun
    ...                contournement `Get Value` : le drapeau ``X`` de la colonne
    ...                Key suffit depuis la lecture des checkbox par
    ...                `Read Table Control`).
    [Arguments]    ${se11_fields}
    ${keys}=    Evaluate    sorted(r['Field'] for r in $se11_fields if r.get('Key') == 'X')
    RETURN    ${keys}

Se11 Fields Should Match Dd03l
    [Documentation]    Confronte l'onglet Fields SE11 au contrat de champs DD03L
    ...                (lu par `Read Ddic Table Fields`) : même séquence de noms
    ...                (ordre compris), et pour chaque champ qui n'est pas un
    ...                ``.INCLUDE``, même élément de données (SE11 ``Data element``
    ...                = DD03L ``ROLLNAME``) et même longueur (comparée en ENTIERS,
    ...                DD03L étant zéro-paddé). Les lignes ``.INCLUDE`` divergent
    ...                par construction (SE11 affiche le nom de l'include, DD03L
    ...                rend ``ROLLNAME`` vide) : elles ne sont confrontées que sur
    ...                le NOM.
    [Arguments]    ${se11_fields}    ${dd03l_fields}
    ${se11_names}=    Evaluate    [r['Field'] for r in $se11_fields]
    ${dd03l_names}=    Evaluate    [r['FIELDNAME'] for r in $dd03l_fields]
    Should Be Equal    ${se11_names}    ${dd03l_names}
    ...    msg=Les séquences de champs SE11 et DD03L diffèrent (nom ou ordre).
    FOR    ${se11_row}    ${dd03l_row}    IN ZIP    ${se11_fields}    ${dd03l_fields}
        IF    '${se11_row}[Field]' == '.INCLUDE'    CONTINUE
        Should Be Equal    ${se11_row}[Data element]    ${dd03l_row}[ROLLNAME]
        ...    msg=Élément de données divergent pour ${se11_row}[Field].
        ${se11_len}=    Convert To Integer    ${se11_row}[Length]
        ${dd03l_len}=    Convert To Integer    ${dd03l_row}[LENG]
        Should Be Equal As Integers    ${se11_len}    ${dd03l_len}
        ...    msg=Longueur divergente pour ${se11_row}[Field].
    END

Read Se11 Delivery Class
    [Documentation]    Valeur TECHNIQUE de la classe de livraison (``CONTFLAG``,
    ...                p.ex. ``L``) lue sur l'onglet Delivery and Maintenance d'une
    ...                table SE11. Jamais le texte descriptif (localisé).
    Click Element    ${SE11_TAB_DELIVERY}
    Wait Until Busy Done
    ${value}=    Get Value    ${SE11_DELIVERY_CLASS_FIELD}
    RETURN    ${value}

Read Ddic Table Header
    [Documentation]    En-tête DDIC d'une table lu par SE16 sur ``DD02L``, filtré
    ...                par NOM (``TABNAME``, jamais par position : le critère est
    ...                résolu par `Get Se16 Selection Criteria`, insensible au choix
    ...                des champs de sélection persistant par utilisateur).
    ...                Retourne ``{TABCLASS, CONTFLAG, AS4LOCAL}`` lus en SORTIE de
    ...                grille (l'écran de sélection DD02L n'expose PAS ces champs en
    ...                critère). ``CONTFLAG`` et ``TABCLASS`` sont les vérités
    ...                techniques derrière les textes localisés de l'en-tête SE11.
    [Arguments]    ${table}
    ${state}=    Reach Table Selection Screen    DD02L
    Should Be True    ${state}[reached]
    ...    msg=Écran de sélection SE16 de DD02L non atteint (verdict : ${state}[verdict]).
    ${criteria}=    Get Se16 Selection Criteria
    Input Text    ${criteria}[TABNAME]    ${table}
    Send Vkey    8
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_GRID}
    ${tabclass}=    Read Column Values From Displayed Grid    TABCLASS
    ${contflag}=    Read Column Values From Displayed Grid    CONTFLAG
    ${as4local}=    Read Column Values From Displayed Grid    AS4LOCAL
    ${header}=    Create Dictionary
    ...    TABCLASS=${tabclass}[0]    CONTFLAG=${contflag}[0]    AS4LOCAL=${as4local}[0]
    RETURN    ${header}

Display Se11 Domain
    [Documentation]    Affiche un domaine du dictionnaire en SE11 et vérifie que
    ...                l'écran domaine est atteint (programme ``SAPLSD11``, dynpro
    ...                ``1200``). Le nom relu dans l'en-tête est retourné.
    [Arguments]    ${domain}
    Open Se11 Object Display    domain    ${domain}
    Wait Until Element Present    ${SE11_DOMAIN_HEADER_NAME}
    ${kind}=    Get Se11 Current Object Kind
    Should Be Equal    ${kind}    domain
    ...    msg=Écran domaine SE11 non atteint pour ${domain} (nature : ${kind}).
    ${name}=    Get Value    ${SE11_DOMAIN_HEADER_NAME}
    RETURN    ${name}

Read Se11 Domain Definition
    [Documentation]    Définition technique d'un domaine lue sur l'onglet
    ...                Definition : ``{DATATYPE, LENG, DECIMALS}`` (valeurs
    ...                ``DD01D-*``). L'onglet est actif à l'arrivée sur l'écran
    ...                domaine ; le clic le garantit sans effet de bord.
    Click Element    ${SE11_TAB_DOMAIN_DEF}
    Wait Until Busy Done
    ${datatype}=    Get Value    ${SE11_DOMAIN_DATATYPE}
    ${leng}=    Get Value    ${SE11_DOMAIN_LENG}
    ${decimals}=    Get Value    ${SE11_DOMAIN_DECIMALS}
    ${definition}=    Create Dictionary
    ...    DATATYPE=${datatype}    LENG=${leng}    DECIMALS=${decimals}
    RETURN    ${definition}

Read Se11 Domain Fixed Values
    [Documentation]    Valeurs fixes d'un domaine lues sur l'onglet Value Range
    ...                (table control « Single Vals ») : liste des valeurs de la
    ...                colonne ``Fixed`` dans l'ORDRE DE MAINTENANCE (PAS trié).
    ...                Les descriptions (localisées) ne sont pas retournées comme
    ...                ancre.
    Click Element    ${SE11_TAB_DOMAIN_VALUES}
    Wait Until Busy Done
    ${rows}=    Read Table Control    ${SE11_DOMAIN_FIXED_VALUES_TC}
    ${values}=    Evaluate    [r['Fixed'] for r in $rows if r.get('Fixed')]
    RETURN    ${values}

Open Data Element From Se11 Field
    [Documentation]    Depuis l'onglet Fields d'une table SE11, navigue vers
    ...                l'élément de données du champ ``${field_name}`` par
    ...                double-clic scripté (focus sur la cellule ``Data element``
    ...                puis F2). La ligne est repérée par CONTENU
    ...                (`Find Table Control Row`), jamais par index en dur ; le
    ...                champ visé doit être dans la première fenêtre visible du
    ...                table control (cas des champs de tête, PRODUCT_ID compris).
    ...                Vérifie l'arrivée sur l'écran élément de données
    ...                (``SAPLSD51``/``1000``).
    [Arguments]    ${field_name}
    ${row}=    Find Table Control Row    ${SE11_TABLE_FIELDS_TC}    Field    ${field_name}
    Should Be True    ${row} >= 0    msg=Champ ${field_name} introuvable dans l'onglet Fields.
    Set Focus    ${SE11_TABLE_FIELDS_TC}/ctxtDD03D-ROLLNAME[${SE11_FIELDS_ROLLNAME_COL},${row}]
    Send Vkey    2
    Wait Until Busy Done
    Wait Until Element Present    ${SE11_DE_HEADER_NAME}
    ${kind}=    Get Se11 Current Object Kind
    Should Be Equal    ${kind}    data_element
    ...    msg=Écran élément de données non atteint depuis ${field_name} (nature : ${kind}).

Read Se11 Data Element Type
    [Documentation]    Type d'un élément de données lu sur l'onglet Data Type :
    ...                ``{ROLLNAME, DOMNAME, DATATYPE, LENG}`` (valeurs
    ...                ``DD04D-*``). Un ``DOMNAME`` VIDE signifie un type prédéfini
    ...                (built-in), sans domaine : l'absence est une donnée, jamais
    ...                un trou.
    ${rollname}=    Get Value    ${SE11_DE_HEADER_NAME}
    ${domname}=    Get Value    ${SE11_DE_DOMNAME}
    ${datatype}=    Get Value    ${SE11_DE_DATATYPE}
    ${leng}=    Get Value    ${SE11_DE_LENG}
    ${type}=    Create Dictionary
    ...    ROLLNAME=${rollname}    DOMNAME=${domname}    DATATYPE=${datatype}    LENG=${leng}
    RETURN    ${type}

Return To Previous Ddic Object
    [Documentation]    Dépile UN niveau de navigation SE11 (F3) et attend la
    ...                stabilisation : élément de données -> table -> écran
    ...                initial. Le verdict d'écran est laissé à l'appelant
    ...                (`Get Se11 Current Object Kind` / lecture d'en-tête).
    Send Vkey    3
    Wait Until Busy Done

Se11 Display Should Stay On Initial Screen
    [Documentation]    Verdict STRUCTUREL d'un refus SE11 : l'écran est resté
    ...                l'écran initial (``SAPLSD_ENTRY``/``1000``) et le message de
    ...                statut est relevé. Sur SE11, l'objet inexistant produit un
    ...                message de type ``S`` (JAMAIS ``E``) : on n'asserte donc pas
    ...                « pas de E », on asserte que l'écran n'a pas changé et on
    ...                RETOURNE le type de message pour l'appelant.
    ${kind}=    Get Se11 Current Object Kind
    Should Be Equal    ${kind}    initial
    ...    msg=SE11 n'est pas resté sur l'écran initial (nature : ${kind}).
    ${type}    ${text}=    Get Status Message
    RETURN    ${type}
