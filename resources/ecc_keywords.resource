*** Settings ***
Documentation       Mots-clés ECC lisibles métier, construits sur SapEccLibrary.
...                 Cette couche est celle que les tests doivent appeler : elle masque
...                 les identifiants d'éléments SAP derrière des noms à intention
...                 explicite. Le vocabulaire unifié correspondant pour Fiori/web se
...                 trouve dans `fiori_keywords.resource` (phase 2), afin qu'un test
...                 soit lisible de la même façon quelle que soit l'interface sous-jacente.

Library             Collections
Library             SapEccLibrary    screenshots_on_error=${True}    default_timeout=30s


*** Variables ***
${SAP_CONNECTION}       ${EMPTY}    # ex. "MY S/4HANA SYSTEM [Group]" : à définir par environnement
${SAP_USER}             ${EMPTY}
${SAP_PASSWORD}         ${EMPTY}
${SAP_CLIENT}           ${EMPTY}
${SAP_LANGUAGE}         EN
# Localisateurs des écrans standard utilisés par les mots-clés métier (convention 1 :
# les ids SAP vivent ici, jamais dans les tests).
${SE16_TABLE_FIELD}     wnd[0]/usr/ctxtDATABROWSE-TABLENAME
${SE16_GRID}            wnd[0]/usr/cntlGRID1/shellcont/shell
${SM50_GRID}            wnd[0]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell    # SM50 : vue Process Overview
${SE16_SETTINGS_USER_PARAMS_MENU}    wnd[0]/mbar/menu[3]/menu[0]    # Settings > User Parameters (écran initial SE16)
${SE16_ALV_GRID_RADIO}  wnd[1]/usr/tabsG_TABSTRIP/tabp0400/ssubTOOLAREA:SAPLWB_CUSTOMIZING:0400/radRSEUMOD-TBALV_GRID
${SE38_PROGRAM_FIELD}   wnd[0]/usr/ctxtRS38M-PROGRAMM
# Écran de sélection SE16 (généré par table ; ids relevés live sur A4H, GUI 8.00).
${SE16_MAX_HITS_FIELD}      wnd[0]/usr/txtMAX_SEL              # « Maximum No. of Hits » : présent sur tout écran de sélection SE16
${SE16_COUNT_BUTTON}        wnd[0]/tbar[1]/btn[31]             # « Number of Entries » : compte sans ouvrir la grille (fiable même table vide)
${SE16_COUNT_RESULT}        wnd[1]/usr/txtG_DBCOUNT            # compteur du popup « Number of Entries »
# Champs de sélection positionnels (I<n> suit l'ordre des champs de la table, stable par version).
${DD07L_DOMNAME_FIELD}      wnd[0]/usr/ctxtI1-LOW              # DD07L : DOMNAME est le 1er champ
${TADIR_OBJECT_FIELD}       wnd[0]/usr/ctxtI2-LOW              # TADIR : OBJECT (TABL, VIEW…)
${TADIR_OBJ_NAME_FIELD}     wnd[0]/usr/txtI3-LOW               # TADIR : OBJ_NAME (champ txt, pas ctxt)
${TADIR_DEVCLASS_FIELD}     wnd[0]/usr/ctxtI8-LOW              # TADIR : DEVCLASS (package)
# Dictionnaires de critères par table pour `Display Table Contents With Filter` :
# id technique du champ -> localisateur positionnel de l'écran de sélection SE16
# (relevés live sur A4H, GUI 8.00 ; spec specs/scarr-spfli-liaisons-se16.md).
# Le type d'élément varie par champ (ctxt vs txt) : re-sonder avec
# `Get Screen Signature` avant d'ajouter le dictionnaire d'une nouvelle table.
&{SCARR_SELECTION_FIELDS}    CARRID=wnd[0]/usr/ctxtI1-LOW    CARRNAME=wnd[0]/usr/txtI2-LOW
...                          CURRCODE=wnd[0]/usr/ctxtI3-LOW    URL=wnd[0]/usr/txtI4-LOW
&{SPFLI_SELECTION_FIELDS}    CARRID=wnd[0]/usr/ctxtI1-LOW    CONNID=wnd[0]/usr/ctxtI2-LOW
...                          COUNTRYFR=wnd[0]/usr/ctxtI3-LOW    CITYFROM=wnd[0]/usr/ctxtI4-LOW
...                          AIRPFROM=wnd[0]/usr/ctxtI5-LOW    COUNTRYTO=wnd[0]/usr/ctxtI6-LOW
...                          CITYTO=wnd[0]/usr/ctxtI7-LOW    AIRPTO=wnd[0]/usr/ctxtI8-LOW
...                          FLTIME=wnd[0]/usr/txtI9-LOW    DEPTIME=wnd[0]/usr/ctxtI10-LOW
...                          ARRTIME=wnd[0]/usr/ctxtI11-LOW    DISTANCE=wnd[0]/usr/txtI12-LOW
...                          DISTID=wnd[0]/usr/ctxtI13-LOW    FLTYPE=wnd[0]/usr/ctxtI14-LOW
...                          PERIOD=wnd[0]/usr/txtI15-LOW


*** Keywords ***
Open SAP And Log In
    [Documentation]    Amorçage complet : lance le Logon Pad, établit la connexion,
    ...                ouvre la connexion et s'authentifie. Prévu pour Suite Setup.
    [Arguments]    ${connection}=${SAP_CONNECTION}    ${user}=${SAP_USER}
    ...            ${password}=${SAP_PASSWORD}    ${client}=${SAP_CLIENT}    ${language}=${SAP_LANGUAGE}
    Open Sap Logon
    Connect To Session With Retry
    # Une chaîne de connexion (/H/hôte/S/port, ex. système Docker/local) n'a pas
    # d'entrée SAP Logon : on utilise alors Open Connection By String.
    IF    "${connection}".startswith("/")
        Open Connection By String    ${connection}
    ELSE
        Open Connection    ${connection}
    END
    Maximize Window
    Run Keyword If    '${client}' != '${EMPTY}'    Input Text    wnd[0]/usr/txtRSYST-MANDT    ${client}
    Input Text         wnd[0]/usr/txtRSYST-BNAME    ${user}
    ${previous_log_level}=    Set Log Level    NONE
    Input Password     wnd[0]/usr/pwdRSYST-BCODE    ${password}
    Set Log Level    ${previous_log_level}
    Run Keyword If    '${language}' != '${EMPTY}'    Input Text    wnd[0]/usr/txtRSYST-LANGU    ${language}
    Send Vkey    0
    Wait Until Busy Done
    Dismiss Multiple Logon Popup

Dismiss Multiple Logon Popup
    [Documentation]    SAP affiche une boîte de dialogue "licence / connexion multiple"
    ...                lorsque le même utilisateur est déjà connecté. Choisit
    ...                "continuer avec cette connexion" si la fenêtre est présente ;
    ...                ne fait rien dans le cas contraire.
    ${present}=    Run Keyword And Return Status    Element Should Be Present    wnd[1]/usr/radMULTI_LOGON_OPT1
    Run Keyword If    ${present}
    ...    Run Keywords
    ...    Select Radio Button    wnd[1]/usr/radMULTI_LOGON_OPT1
    ...    AND    Click Element    wnd[1]/tbar[0]/btn[0]

Popup Is Present
    [Documentation]    Vrai si une fenêtre modale (``wnd[1]``) est ouverte. Bloc de
    ...                construction des autres helpers de popup ; renvoie un booléen
    ...                sans jamais lever.
    ${present}=    Run Keyword And Return Status    Element Should Be Present    wnd[1]
    RETURN    ${present}

Confirm Popup
    [Documentation]    Confirme une fenêtre modale si elle est présente (Continuer/Oui),
    ...                indépendamment de la langue. Les dialogues de question SAP (SPOP)
    ...                ne répondent qu'au clic de bouton : on clique alors le 1er bouton
    ...                (``btnSPOP-OPTION1``) ; sinon on envoie Entrée à la modale
    ...                (``window=1``), ce qui couvre les dialogues applicatifs/d'avertissement.
    ...                Ne fait rien si aucun popup n'est ouvert.
    ${present}=    Popup Is Present
    IF    ${present}
        ${spop}=    Run Keyword And Return Status    Element Should Be Present    wnd[1]/usr/btnSPOP-OPTION1
        IF    ${spop}
            Click Element    wnd[1]/usr/btnSPOP-OPTION1
        ELSE
            Send Vkey    0    window=1
        END
        Wait Until Busy Done
    END

Cancel Popup
    [Documentation]    Annule une fenêtre modale si elle est présente. Dialogue de
    ...                question SAP (SPOP) : clique le 2e bouton (``btnSPOP-OPTION2``,
    ...                Non/Annuler) ; sinon envoie F12 à la modale (``window=1``). Ne fait
    ...                rien si aucun popup n'est ouvert.
    ${present}=    Popup Is Present
    IF    ${present}
        ${spop}=    Run Keyword And Return Status    Element Should Be Present    wnd[1]/usr/btnSPOP-OPTION2
        IF    ${spop}
            Click Element    wnd[1]/usr/btnSPOP-OPTION2
        ELSE
            Send Vkey    12    window=1
        END
        Wait Until Busy Done
    END

Click Popup Button
    [Documentation]    Clique le bouton de barre d'outils ``${button_index}`` de la
    ...                fenêtre modale (``wnd[1]/tbar[0]/btn[N]``) : utile quand le bouton
    ...                voulu n'est ni le défaut (Entrée) ni Annuler (F12). Lève si aucun
    ...                popup n'est ouvert.
    [Arguments]    ${button_index}=0
    Element Should Be Present    wnd[1]
    Click Element    wnd[1]/tbar[0]/btn[${button_index}]
    Wait Until Busy Done

Go To Transaction
    [Documentation]    Ouvre un code de transaction et attend que l'écran se stabilise.
    [Arguments]    ${tcode}
    Run Transaction    ${tcode}
    Wait Until Busy Done

Save And Expect Success
    [Documentation]    Appuie sur Enregistrer (Ctrl+S) et vérifie que la barre de statut indique un succès.
    Send Vkey    11
    Wait Until Busy Done
    Status Message Should Be Success

Use ALV Grid In Data Browser
    [Documentation]    Bascule la sortie du Data Browser (SE16) de l'utilisateur
    ...                courant en **grille ALV** (Settings → User Parameters →
    ...                ALV Grid Display). Persistant par utilisateur et idempotent,
    ...                indispensable avant `Display Table Contents` : la « Standard
    ...                SE16 list » (défaut) est une liste ABAP classique sans objet
    ...                grille scriptable.
    Go To Transaction    SE16
    Click Element    ${SE16_SETTINGS_USER_PARAMS_MENU}
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_ALV_GRID_RADIO}
    Select Radio Button    ${SE16_ALV_GRID_RADIO}
    Send Vkey    0    window=1
    Wait Until Busy Done

Display Table Contents
    [Documentation]    Ouvre la table ``${table}`` dans le Data Browser (SE16) et
    ...                exécute la sélection ; échoue si la grille de résultats
    ...                n'apparaît pas dans ``${timeout}`` (table vide ou inconnue).
    ...                Suppose la sortie SE16 en grille ALV : voir
    ...                `Use ALV Grid In Data Browser` (à appeler une fois en setup).
    [Arguments]    ${table}    ${timeout}=30s
    Go To Transaction    SE16
    Input Text    ${SE16_TABLE_FIELD}    ${table}
    Send Vkey    0
    Wait Until Busy Done
    Send Vkey    8
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_GRID}    timeout=${timeout}

Read Displayed Grid
    [Documentation]    Lit la grille de résultats SE16 courante (après
    ...                `Display Table Contents`) en liste de dicts.
    [Arguments]    ${max_rows}=10
    ${rows}=    Read Grid    ${SE16_GRID}    max_rows=${max_rows}
    RETURN    ${rows}

Display Table Contents With Filter
    [Documentation]    Comme `Display Table Contents` mais applique d'abord des
    ...                critères nommés (``CHAMP=valeur``, ids techniques en
    ...                majuscules) sur l'écran de sélection, puis exécute (F8).
    ...                Les localisateurs positionnels ``I<n>-LOW`` restent dans
    ...                cette resource (convention 1) : dictionnaire
    ...                ``<TABLE>_SELECTION_FIELDS`` par table, à compléter ici
    ...                pour toute nouvelle table filtrée. Échoue si la grille
    ...                n'apparaît pas dans ``${timeout}``, notamment quand aucune
    ...                ligne ne répond au filtre (pour un compte fiable, filtre
    ...                vide compris, préférer `Count Entries On Current Selection
    ...                Screen`). Sans critère, équivaut à `Display Table Contents`.
    ...                Ex. : ``Display Table Contents With Filter    SPFLI    CARRID=LH    CONNID=0400``
    [Arguments]    ${table}    ${timeout}=30s    &{filters}
    ${map}=    Get Variable Value    \${${table.upper()}_SELECTION_FIELDS}
    IF    not isinstance($map, dict)
        Fail    No selection-field map for table '${table}': define dictionary '${table.upper()}_SELECTION_FIELDS' (positional I<n>-LOW locators, verified live) in resources/ecc_keywords.resource.
    END
    Open Table Selection Screen    ${table}
    FOR    ${field}    ${value}    IN    &{filters}
        ${locator}=    Evaluate    $map.get($field.upper())
        IF    $locator is None
            Fail    Table '${table}' has no selection criterion '${field}'; known criteria: ${{ sorted($map) }}
        END
        Input Text    ${locator}    ${value}
    END
    Send Vkey    8
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_GRID}    timeout=${timeout}

Displayed Grid Should Contain Columns
    [Documentation]    Vérifie que la grille SE16 courante (après `Display Table
    ...                Contents` / `Display Table Contents With Filter`) expose
    ...                chacune des colonnes données par son **id technique**
    ...                (``CARRID``…), lu dans l'ordre des colonnes de la grille,
    ...                jamais les titres affichés, dépendants de la locale
    ...                (convention 3). L'échec liste les colonnes disponibles.
    [Arguments]    @{columns}
    ${ids}=    Get Grid Column Ids    ${SE16_GRID}
    FOR    ${column}    IN    @{columns}
        Should Contain    ${ids}    ${column}    values=False
        ...    msg=Displayed grid has no technical column '${column}'; available: ${ids}
    END

Read Column Values From Displayed Grid
    [Documentation]    Extrait les valeurs de la colonne ``${column}`` (id
    ...                technique) de la grille SE16 courante : liste dans l'ordre
    ...                d'affichage (doublons conservés) ou, avec ``unique=True``,
    ...                ensemble dédoublonné trié. Fait défiler la grille pour
    ...                matérialiser le chargement différé et plafonne la lecture
    ...                à ``max_rows`` (troncature journalisée par `Read Full
    ...                Grid`). La présence de la colonne est vérifiée d'abord
    ...                (échec explicite avec les colonnes disponibles) ; les clés
    ...                de lignes SE16 valent les ids techniques (relevé live A4H).
    [Arguments]    ${column}    ${max_rows}=200    ${unique}=False
    Displayed Grid Should Contain Columns    ${column}
    ${rows}=    Read Full Grid    ${SE16_GRID}    max_rows=${max_rows}
    IF    ${unique}
        ${values}=    Evaluate    sorted({r[$column] for r in $rows})
    ELSE
        ${values}=    Evaluate    [r[$column] for r in $rows]
    END
    RETURN    ${values}

Try Open Table Selection Screen
    [Documentation]    Ouvre SE16 sur ``${table}`` et tente d'atteindre l'écran de
    ...                sélection. Retourne ``True`` si l'écran s'ouvre, ``False``
    ...                sinon : nom rejeté par un message de statut de type ``E``
    ...                (structure, include ou table inconnue) OU par un dialogue de
    ...                message modal. L'assertion porte sur le *type* et la
    ...                STRUCTURE de l'écran, jamais sur un texte localisé.
    ...                Le pilotage (popup « choix des champs de sélection » des
    ...                tables larges, dialogue de message de génération d'écran,
    ...                attente de l'écran généré) vit dans le keyword de
    ...                bibliothèque `Reach Se16 Selection Screen` : UNE seule copie
    ...                de cette logique, partagée avec le canal DDIC. Le verdict
    ...                détaillé est journalisé et disponible via
    ...                `Reach Table Selection Screen` pour qui doit distinguer
    ...                ``rejected`` de ``dialog``.
    ...                Referme d'abord toute modale résiduelle d'une sonde
    ...                précédente : le keyword reste sûr en balayage de masse.
    [Arguments]    ${table}
    ${state}=    Reach Table Selection Screen    ${table}
    RETURN    ${state}[reached]

Reach Table Selection Screen
    [Documentation]    Comme `Try Open Table Selection Screen` mais retourne le
    ...                VERDICT complet (dict) : ``reached``, ``verdict``
    ...                (``reached`` | ``rejected`` | ``dialog`` | ``modal``),
    ...                ``message_type``, ``status_text`` et ``dialog_text``. À
    ...                utiliser quand un balayage doit distinguer « structure
    ...                rejetée en type E » d'un « rejet par dialogue de message »
    ...                (les textes ne servent qu'au journal, jamais aux assertions).
    [Arguments]    ${table}
    Cancel Popup
    ${state}=    Reach Se16 Selection Screen    ${table}
    Log    SE16 '${table}' : verdict=${state}[verdict] type=${state}[message_type]
    RETURN    ${state}

Open Table Selection Screen
    [Documentation]    Comme `Try Open Table Selection Screen` mais échoue si SE16
    ...                rejette le nom, pour les tests qui exigent une table consultable.
    [Arguments]    ${table}
    ${ok}=    Try Open Table Selection Screen    ${table}
    IF    not ${ok}
        ${type}    ${text}=    Get Status Message
        Fail    SE16 did not open '${table}' (status message type '${type}'): ${text}
    END

Count Entries On Current Selection Screen
    [Documentation]    Suppose un écran de sélection SE16 déjà ouvert : clique
    ...                « Number of Entries », lit le compteur du popup puis le
    ...                referme (F12). Compte **toutes** les entrées répondant aux
    ...                critères saisis : indépendant de « Maximum No. of Hits » et
    ...                fiable sur table vide (retourne 0), contrairement à
    ...                l'exécution F8 qui reste sur l'écran de sélection.
    Click Element    ${SE16_COUNT_BUTTON}
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_COUNT_RESULT}
    ${raw}=    Get Value    ${SE16_COUNT_RESULT}
    Send Vkey    12    window=1
    Wait Until Busy Done
    # Normalise les éventuels séparateurs de milliers (dépendants du profil
    # utilisateur). PAS de regex ici : `\d`/`\D` dans une cellule Robot passe par
    # deux couches d'échappement (fichier + Evaluate) qui rongent le backslash et
    # changent silencieusement le sens du motif (piégé par
    # tests/unit/test_se16_exploration_logic.py) ; le filtrage caractère par
    # caractère ci-dessous n'a pas ce problème.
    ${count}=    Evaluate    int(''.join(c for c in $raw if c.isdigit()) or 0)
    RETURN    ${count}

Count Table Entries
    [Documentation]    Compte les entrées de ``${table}`` via SE16 → « Number of
    ...                Entries ». Échoue si la table n'est pas consultable (voir
    ...                `Open Table Selection Screen`). Retourne un entier (0 admis).
    [Arguments]    ${table}
    Open Table Selection Screen    ${table}
    ${count}=    Count Entries On Current Selection Screen
    RETURN    ${count}

Count Flight Connections For Airline
    [Documentation]    Compte les liaisons de vol (table ``SPFLI``) de la compagnie
    ...                ``${carrid}`` : écran de sélection SE16, critère ``CARRID``
    ...                (localisateur posé dans ``SPFLI_SELECTION_FIELDS``), puis
    ...                « Number of Entries ». Retourne un entier : 0 sans erreur
    ...                pour une compagnie sans liaison ou inconnue ; l'écran de
    ...                sélection reste utilisable après l'appel (le popup de
    ...                comptage est refermé par F12).
    [Arguments]    ${carrid}
    Open Table Selection Screen    SPFLI
    Input Text    ${SPFLI_SELECTION_FIELDS}[CARRID]    ${carrid}
    ${count}=    Count Entries On Current Selection Screen
    RETURN    ${count}

Read Domain Values
    [Documentation]    Lit les valeurs autorisées d'un domaine du dictionnaire
    ...                (table ``DD07L``) et les retourne triées, p.ex. ``CONTFLAG``
    ...                (classes de livraison) ou ``TABCLASS`` (classes techniques).
    ...                Échoue si le domaine n'a aucune valeur (la grille n'apparaît pas).
    [Arguments]    ${domain}    ${max_hits}=200
    Open Table Selection Screen    DD07L
    Input Text    ${DD07L_DOMNAME_FIELD}    ${domain}
    Input Text    ${SE16_MAX_HITS_FIELD}    ${max_hits}
    Send Vkey    8
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_GRID}
    ${rows}=    Read Full Grid    ${SE16_GRID}    max_rows=${max_hits}
    ${values}=    Evaluate    sorted({r["DOMVALUE_L"] for r in $rows if r["DOMVALUE_L"]})
    RETURN    ${values}

List Repository Tables
    [Documentation]    Inventaire du référentiel (table ``TADIR``) : noms des objets
    ...                ``R3TR ${object_type}`` (``TABL`` par défaut, ``VIEW`` pour
    ...                les vues : la découverte n'est plus aveugle aux vues) filtrés
    ...                par package (``DEVCLASS``) et/ou motif de nom (joker ``*``).
    ...                Retourne une liste triée, vide si aucun objet ne répond.
    ...                NB : TADIR ne distingue pas tables transparentes et
    ...                structures : joindre DD02L (`Classify Ddic Objects`) ou
    ...                `Try Open Table Selection Screen` pour écarter ces dernières.
    ...
    ...                Lève si le nombre de lignes lues atteint exactement ``max_hits``
    ...                (troncature probable côté SE16, jamais un compte réel qui
    ...                tombe pile dessus par hasard) : un appelant qui n'inspecte que
    ...                la liste retournée ne peut sinon pas distinguer un inventaire
    ...                complet d'un inventaire tronqué en silence. Augmentez
    ...                ``max_hits``, ou passez ``allow_truncation=True`` pour accepter
    ...                explicitement un résultat potentiellement incomplet.
    [Arguments]    ${package}=${EMPTY}    ${name_pattern}=${EMPTY}    ${max_hits}=500
    ...    ${allow_truncation}=False    ${object_type}=TABL
    Open Table Selection Screen    TADIR
    Input Text    ${TADIR_OBJECT_FIELD}    ${object_type}
    IF    $name_pattern    Input Text    ${TADIR_OBJ_NAME_FIELD}    ${name_pattern}
    IF    $package    Input Text    ${TADIR_DEVCLASS_FIELD}    ${package}
    Input Text    ${SE16_MAX_HITS_FIELD}    ${max_hits}
    Send Vkey    8
    Wait Until Busy Done
    ${shown}=    Run Keyword And Return Status    Wait Until Element Present    ${SE16_GRID}    timeout=10s
    IF    not ${shown}
        ${empty}=    Create List
        RETURN    ${empty}
    END
    ${rows}=    Read Full Grid    ${SE16_GRID}    max_rows=${max_hits}
    IF    len($rows) == int($max_hits) and not ${allow_truncation}
        Fail    List Repository Tables read exactly max_hits=${max_hits} rows for
        ...    package='${package}' name_pattern='${name_pattern}': likely truncated.
        ...    Increase max_hits, or pass allow_truncation=True to accept a
        ...    possibly-incomplete inventory.
    END
    ${names}=    Evaluate    sorted({r["OBJ_NAME"] for r in $rows})
    RETURN    ${names}

Discover DDIC Objects By Scope
    [Documentation]    Découverte bornée des objets DDIC d'un périmètre validé
    ...                (voir `Validate Ddic Scope`) : pour chaque package puis
    ...                chaque préfixe, interroge TADIR pour chacun des types
    ...                d'objets du périmètre (``scope[object_types]``, ``TABL``
    ...                et ``VIEW`` par défaut : les vues sont découvertes ;
    ...                surchargables par les arguments variables), fait l'union
    ...                dédoublonnée et triée, applique ``max_objects``.
    ...                Retourne ``[noms, truncated]`` : une borne atteinte est
    ...                toujours visible, jamais un succès silencieux.
    [Arguments]    ${scope}    @{object_types}
    IF    not $object_types
        ${object_types}=    Evaluate    $scope.get("object_types") or ["TABL", "VIEW"]
    END
    ${groups}=    Create List
    FOR    ${object_type}    IN    @{object_types}
        FOR    ${package}    IN    @{scope}[packages]
            ${names}=    List Repository Tables    package=${package}    object_type=${object_type}
            Append To List    ${groups}    ${names}
        END
        FOR    ${prefix}    IN    @{scope}[prefixes]
            ${names}=    List Repository Tables    name_pattern=${prefix}*    object_type=${object_type}
            Append To List    ${groups}    ${names}
        END
    END
    ${names}    ${truncated}=    Merge Ddic Name Lists    ${groups}    ${scope}[max_objects]
    RETURN    ${names}    ${truncated}

Run Report
    [Documentation]    Ouvre SE38 et lance le programme ABAP ``${report}`` (F8) ;
    ...                rend la main sur son écran de sélection. À combiner avec
    ...                `Send Vkey    8` pour exécuter la sélection par défaut.
    [Arguments]    ${report}
    Go To Transaction    SE38
    Input Text    ${SE38_PROGRAM_FIELD}    ${report}
    Send Vkey    8
    Wait Until Busy Done

Close SAP
    [Documentation]    Déconnecte proprement et arrête le Logon Pad. Prévu pour Suite Teardown.
    Run Keyword And Ignore Error    Run Transaction    /nex
    Close Sap Logon
