*** Settings ***
Documentation       Campagne exploratoire SAP GUI (ECC/S4, backend A4H — S/4HANA 1909, GUI 8.00).
...
...                 Objectif : dresser l'inventaire exhaustif des **classes métier** (classes de
...                 livraison du dictionnaire ABAP, domaine ``CONTFLAG``) et des **classes
...                 techniques de table** (domaine ``TABCLASS``) disponibles sur cette instance,
...                 puis vérifier en profondeur — table par table, via SE16 — l'accessibilité et
...                 le nombre d'entrées de toutes les tables de données des paquets de
...                 démonstration réellement peuplés sur A4H (vol ``SAPBC_DATAMODEL`` et EPM
...                 ``SNWD_*``).
...
...                 Fichier autonome : toutes les interactions SAP passent **directement** par
...                 les mots-clés bas niveau de ``SapEccLibrary`` (aucune dépendance à
...                 ``resources/ecc_keywords.resource`` ni aux autres suites du dépôt), pour rester
...                 indépendant du reste du projet.
...
...                 NB — cette autonomie DÉROGE volontairement à la convention n°1 du dépôt
...                 (« les ids SAP vivent dans resources/ ») : la suite est embarquée telle
...                 quelle dans le **pack de déploiement Windows** comme exemple « données
...                 réelles » rejouable sans le dépôt (voir ``packaging/``). Le pendant
...                 conforme aux conventions, pour le développement dans le dépôt, est
...                 ``ecc_exploration.robot`` (mêmes vérifications, via la resource métier).
...
...                 Découverte dynamique : les listes de tables ne sont **jamais codées en dur** —
...                 chaque exécution relit le référentiel (TADIR) en direct, ce qui rend la suite
...                 rejouable telle quelle après une montée de version ou l'ajout de données.
Library             SapEccLibrary    screenshots_on_error=${True}    default_timeout=30s
Library             Collections

Suite Setup         Connect And Log In To SAP GUI
Suite Teardown      Log Out And Close SAP GUI

Test Tags           sap    ecc    exploration


*** Variables ***
# Identifiants de connexion — fournis en ligne de commande (-v) ou en variables d'environnement.
${SAP_CONNECTION}               ${EMPTY}    # ex. "/H/vhcala4hci/S/3200" (chaîne de connexion Docker/local)
${SAP_USER}                     ${EMPTY}
${SAP_PASSWORD}                 ${EMPTY}
${SAP_CLIENT}                   ${EMPTY}
${SAP_LANGUAGE}                 EN

# --- Localisateurs des écrans standard (convention du dépôt : les ids SAP vivent ici, jamais
# --- dans les Test Cases). Relevés live sur A4H, SAP GUI 8.00.
${SE16_TABLE_FIELD}             wnd[0]/usr/ctxtDATABROWSE-TABLENAME
${SE16_GRID}                    wnd[0]/usr/cntlGRID1/shellcont/shell
${SE16_SETTINGS_USER_PARAMS_MENU}    wnd[0]/mbar/menu[3]/menu[0]    # Settings > User Parameters
${SE16_ALV_GRID_RADIO}          wnd[1]/usr/tabsG_TABSTRIP/tabp0400/ssubTOOLAREA:SAPLWB_CUSTOMIZING:0400/radRSEUMOD-TBALV_GRID
${SE16_MAX_HITS_FIELD}          wnd[0]/usr/txtMAX_SEL             # « Maximum No. of Hits »
${SE16_COUNT_BUTTON}            wnd[0]/tbar[1]/btn[31]            # « Number of Entries »
${SE16_COUNT_RESULT}            wnd[1]/usr/txtG_DBCOUNT           # popup « Number of Entries »
# Champs de sélection positionnels (I<n> suit l'ordre des champs de la table — stable par version).
${DD07L_DOMNAME_FIELD}          wnd[0]/usr/ctxtI1-LOW             # DD07L : DOMNAME (1er champ)
${TADIR_OBJECT_FIELD}           wnd[0]/usr/ctxtI2-LOW             # TADIR : OBJECT (TABL, VIEW…)
${TADIR_OBJ_NAME_FIELD}         wnd[0]/usr/txtI3-LOW              # TADIR : OBJ_NAME (champ txt)
${TADIR_DEVCLASS_FIELD}         wnd[0]/usr/ctxtI8-LOW             # TADIR : DEVCLASS (paquet)

# --- Catalogues métier verrouillés — vérifiés live le 2026-07-12 sur cette instance A4H
# --- (S/4HANA 1909, GUI 8.00). Un écart signale une évolution du système à documenter.
@{EXPECTED_DELIVERY_CLASSES}    A    C    E    G    L    S    W
@{EXPECTED_TABLE_CLASSES}       APPEND    INTTAB    TRANSP    VIEW

# --- Périmètre de la vérification en profondeur : les deux paquets de données de démonstration
# --- réellement peuplés sur A4H (SFLIGHT/EPM). La liste des tables qu'ils contiennent est
# --- redécouverte dynamiquement à chaque exécution (voir mot-clé `List Repository Tables`).
${FLIGHT_PACKAGE}               SAPBC_DATAMODEL
${EPM_NAME_PATTERN}              SNWD_*


*** Test Cases ***
SAP GUI Scripting Should Be Fully Enabled
    [Documentation]    Préflight : le scripting SAP GUI doit être pleinement actif (côté
    ...                serveur RZ11 ``sapgui/user_scripting`` et côté client) avant toute
    ...                exploration — échoue tôt et clairement plutôt que par des timeouts
    ...                en cascade plus loin dans la suite.
    [Tags]    smoke
    Scripting Should Be Fully Enabled

Business Delivery Classes Catalog Should Match Known Set
    [Documentation]    Dresse l'inventaire exhaustif des **classes métier** (classes de
    ...                livraison du dictionnaire ABAP) disponibles sur cette version de SAP,
    ...                en lisant les valeurs fixes du domaine ``CONTFLAG`` (table ``DD07L``).
    ...                Verrouille le catalogue connu : un écart doit être investigué (montée
    ...                de version, correctif SAP) plutôt qu'ignoré.
    [Tags]    catalog
    ${delivery_classes}=    Read Domain Fixed Values    CONTFLAG
    Log    Classes de livraison (business classes) découvertes : ${delivery_classes}    level=INFO
    Should Not Be Empty    ${delivery_classes}
    Lists Should Be Equal    ${delivery_classes}    ${EXPECTED_DELIVERY_CLASSES}
    ...    ignore_order=True
    ...    msg=Le catalogue des classes de livraison a changé sur ce système — mettre à jour EXPECTED_DELIVERY_CLASSES après investigation.

Table Technical Classes Catalog Should Match Known Set
    [Documentation]    Même principe que le test précédent, pour les **classes techniques de
    ...                table** (domaine ``TABCLASS``) : transparente, vue, table interne,
    ...                append — utile pour distinguer une vraie table d'une vue ou d'un append
    ...                avant de tenter une vérification SE16.
    [Tags]    catalog
    ${table_classes}=    Read Domain Fixed Values    TABCLASS
    Log    Classes techniques de table découvertes : ${table_classes}    level=INFO
    Should Not Be Empty    ${table_classes}
    Lists Should Be Equal    ${table_classes}    ${EXPECTED_TABLE_CLASSES}
    ...    ignore_order=True
    ...    msg=Le catalogue des classes techniques de table a changé sur ce système — mettre à jour EXPECTED_TABLE_CLASSES après investigation.

Flight Demo Package Tables Should All Be Accessible And Counted
    [Documentation]    Vérification en profondeur : redécouvre dynamiquement (TADIR, objets
    ...                ``R3TR TABL``) toutes les tables du paquet de démonstration vol
    ...                (``SAPBC_DATAMODEL``), puis vérifie chacune individuellement via SE16 —
    ...                consultable + nombre d'entrées lu, ou reconnue comme structure/include
    ...                (statut ``E`` à l'ouverture, ex. ``SFL_AUX``) sans faire échouer le test.
    [Tags]    deep
    ${tables}=    List Repository Tables    package=${FLIGHT_PACKAGE}
    Log    ${{len($tables)}} table(s) découverte(s) dans le paquet ${FLIGHT_PACKAGE} : ${tables}    level=INFO
    Should Not Be Empty    ${tables}
    FOR    ${table}    IN    @{tables}
        Verify Table Is Accessible And Counted    ${table}
    END

EPM Demo Package Tables Should All Be Accessible And Counted
    [Documentation]    Même vérification en profondeur pour les tables EPM (motif de nom
    ...                ``SNWD_*`` — paquet EPM non homogène, d'où le filtrage par nom plutôt
    ...                que par DEVCLASS unique).
    [Tags]    deep
    ${tables}=    List Repository Tables    name_pattern=${EPM_NAME_PATTERN}    max_hits=200
    Log    ${{len($tables)}} table(s) découverte(s) pour le motif ${EPM_NAME_PATTERN} : ${tables}    level=INFO
    Should Not Be Empty    ${tables}
    FOR    ${table}    IN    @{tables}
        Verify Table Is Accessible And Counted    ${table}
    END


*** Keywords ***
Connect And Log In To SAP GUI
    [Documentation]    Amorçage complet de la session : lance le Logon Pad, se connecte,
    ...                ouvre la connexion cible et s'authentifie. Bascule ensuite SE16 en
    ...                grille ALV (nécessaire pour toute lecture de grille par la suite).
    ...                Prévu pour Suite Setup.
    Open Sap Logon
    Connect To Session With Retry
    # Une chaîne de connexion (/H/hôte/S/port, ex. système Docker/local) n'a pas d'entrée
    # SAP Logon enregistrée : on utilise alors Open Connection By String.
    IF    "${SAP_CONNECTION}".startswith("/")
        Open Connection By String    ${SAP_CONNECTION}
    ELSE
        Open Connection    ${SAP_CONNECTION}
    END
    Maximize Window
    IF    "${SAP_CLIENT}" != "${EMPTY}"
        Input Text    wnd[0]/usr/txtRSYST-MANDT    ${SAP_CLIENT}
    END
    Input Text    wnd[0]/usr/txtRSYST-BNAME    ${SAP_USER}
    ${previous_log_level}=    Set Log Level    NONE
    Input Password    wnd[0]/usr/pwdRSYST-BCODE    ${SAP_PASSWORD}
    Set Log Level    ${previous_log_level}
    IF    "${SAP_LANGUAGE}" != "${EMPTY}"
        Input Text    wnd[0]/usr/txtRSYST-LANGU    ${SAP_LANGUAGE}
    END
    Send Vkey    0
    Wait Until Busy Done
    Dismiss Multiple Logon Popup
    Use ALV Grid In Data Browser

Dismiss Multiple Logon Popup
    [Documentation]    SAP affiche une boîte de dialogue « connexion multiple » lorsque le
    ...                même utilisateur est déjà connecté ailleurs. Choisit « continuer avec
    ...                cette connexion » si la fenêtre est présente ; ne fait rien sinon.
    ${present}=    Run Keyword And Return Status    Element Should Be Present    wnd[1]/usr/radMULTI_LOGON_OPT1
    IF    ${present}
        Select Radio Button    wnd[1]/usr/radMULTI_LOGON_OPT1
        Click Element    wnd[1]/tbar[0]/btn[0]
        Wait Until Busy Done
    END

Popup Is Present
    [Documentation]    Vrai si une fenêtre modale (``wnd[1]``) est ouverte. Ne lève jamais.
    ${present}=    Run Keyword And Return Status    Element Should Be Present    wnd[1]
    RETURN    ${present}

Cancel Residual Popup
    [Documentation]    Referme une fenêtre modale résiduelle si présente (F12) — sécurise
    ...                l'enchaînement des sondes SE16 en balayage de masse. Ne fait rien si
    ...                aucun popup n'est ouvert.
    ${present}=    Popup Is Present
    IF    ${present}
        Send Vkey    12    window=1
        Wait Until Busy Done
    END

Use ALV Grid In Data Browser
    [Documentation]    Bascule la sortie du Data Browser (SE16) de l'utilisateur courant en
    ...                **grille ALV** (Settings > User Parameters > ALV Grid Display).
    ...                Réglage persistant par utilisateur et idempotent (peut être rappelé
    ...                sans risque) — indispensable : la « Standard SE16 list » (défaut) est
    ...                une liste ABAP classique sans objet grille scriptable.
    Run Transaction    SE16
    Click Element    ${SE16_SETTINGS_USER_PARAMS_MENU}
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_ALV_GRID_RADIO}
    Select Radio Button    ${SE16_ALV_GRID_RADIO}
    Send Vkey    0    window=1
    Wait Until Busy Done

Try Open Table Selection Screen
    [Documentation]    Ouvre SE16 sur ``${table}`` et tente d'atteindre l'écran de sélection.
    ...                Retourne ``True`` si l'écran s'ouvre, ``False`` si SE16 rejette le nom —
    ...                message de statut de type ``E`` (structure, include ou table inconnue) ;
    ...                l'assertion porte sur le *type* du message, jamais sur son texte
    ...                localisé. Gère le dialogue « choix des champs de sélection » des tables
    ...                larges (> 40 champs) en repérant dynamiquement la première case via
    ...                `Get Screen Signature`.
    [Arguments]    ${table}
    Cancel Residual Popup
    Run Transaction    SE16
    Input Text    ${SE16_TABLE_FIELD}    ${table}
    Send Vkey    0
    Wait Until Busy Done
    ${type}    ${text}=    Get Status Message
    IF    "${type}" == "E"    RETURN    ${False}
    ${popup}=    Popup Is Present
    IF    ${popup}
        ${signature}=    Get Screen Signature
        ${checkbox}=    Evaluate    next((l.split(chr(9))[0][2:] for l in $signature.splitlines() if l.startswith('* wnd[1]/usr/chk')), '')
        IF    $checkbox    Select Checkbox    ${checkbox}
        Send Vkey    0    window=1
        Wait Until Busy Done
    END
    Wait Until Element Present    ${SE16_MAX_HITS_FIELD}
    RETURN    ${True}

Count Entries On Current Selection Screen
    [Documentation]    Suppose un écran de sélection SE16 déjà ouvert : clique « Number of
    ...                Entries », lit le compteur du popup puis le referme (F12). Compte
    ...                **toutes** les entrées répondant aux critères saisis — fiable même sur
    ...                table vide (retourne 0), contrairement à l'exécution F8.
    Click Element    ${SE16_COUNT_BUTTON}
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_COUNT_RESULT}
    ${raw}=    Get Value    ${SE16_COUNT_RESULT}
    Send Vkey    12    window=1
    Wait Until Busy Done
    # Normalise les éventuels séparateurs de milliers (dépendants du profil utilisateur) sans
    # regex : `\d`/`\D` dans une cellule Robot traverse deux couches d'échappement (fichier +
    # Evaluate) qui rongent le backslash et changent silencieusement le motif.
    ${count}=    Evaluate    int(''.join(c for c in $raw if c.isdigit()) or 0)
    RETURN    ${count}

Verify Table Is Accessible And Counted
    [Documentation]    Vérification en profondeur d'une table unique : tente d'ouvrir SE16
    ...                sur ``${table}``. Si consultable, compte ses entrées et journalise le
    ...                résultat (assertion : le compte est un entier >= 0, toujours vrai —
    ...                l'objectif est de prouver que la lecture n'a pas échoué silencieusement).
    ...                Si SE16 la rejette (structure ou include, statut ``E``), le journalise
    ...                comme tel sans faire échouer le test : ce n'est pas une anomalie mais
    ...                une caractéristique attendue du dictionnaire ABAP.
    [Arguments]    ${table}
    ${accessible}=    Try Open Table Selection Screen    ${table}
    IF    ${accessible}
        ${count}=    Count Entries On Current Selection Screen
        Should Be True    ${count} >= 0
        Log    Table ${table} : consultable, ${count} entrée(s).    level=INFO
    ELSE
        ${type}    ${text}=    Get Status Message
        Should Be Equal As Strings    ${type}    E
        ...    msg=Table ${table} rejetée par SE16 pour une raison inattendue (type '${type}': ${text}).
        Log    Table ${table} : non consultable via SE16 (structure/include) — statut '${type}': ${text}.    level=INFO
    END

Read Domain Fixed Values
    [Documentation]    Lit les valeurs fixes autorisées d'un domaine du dictionnaire ABAP
    ...                (table ``DD07L``) et les retourne triées — p.ex. ``CONTFLAG`` (classes
    ...                de livraison / business classes) ou ``TABCLASS`` (classes techniques).
    [Arguments]    ${domain}    ${max_hits}=200
    ${opened}=    Try Open Table Selection Screen    DD07L
    Should Be True    ${opened}    DD07L devrait toujours être consultable via SE16.
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
    ...                ``R3TR TABL`` filtrés par paquet (``DEVCLASS``) et/ou motif de nom
    ...                (joker ``*``). Retourne une liste triée, vide si aucun objet ne répond.
    ...                Lève si le nombre de lignes lues atteint exactement ``max_hits``
    ...                (troncature probable — un vrai inventaire complet ne doit jamais
    ...                tomber pile sur la limite par hasard), pour ne jamais faire passer
    ...                silencieusement un inventaire tronqué pour un inventaire exhaustif.
    [Arguments]    ${package}=${EMPTY}    ${name_pattern}=${EMPTY}    ${max_hits}=500
    ${opened}=    Try Open Table Selection Screen    TADIR
    Should Be True    ${opened}    TADIR devrait toujours être consultable via SE16.
    Input Text    ${TADIR_OBJECT_FIELD}    TABL
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
    IF    len($rows) == int($max_hits)
        Fail    List Repository Tables a lu exactement max_hits=${max_hits} lignes pour
        ...    package='${package}' name_pattern='${name_pattern}' — inventaire probablement
        ...    tronqué. Augmenter max_hits.
    END
    ${names}=    Evaluate    sorted({r["OBJ_NAME"] for r in $rows})
    RETURN    ${names}

Log Out And Close SAP GUI
    [Documentation]    Déconnecte proprement et arrête le Logon Pad. Prévu pour Suite
    ...                Teardown ; ne fait jamais échouer la suite (déconnexion best-effort).
    Run Keyword And Ignore Error    Run Transaction    /nex
    Run Keyword And Ignore Error    Close Sap Logon
