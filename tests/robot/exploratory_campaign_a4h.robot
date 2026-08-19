*** Settings ***
Documentation       Campagne de tests exploratoires SAP ECC sur l'ABAP Platform Trial « A4H ».
...
...                 Pilotée de bout en bout par la librairie Python ``SapEccLibrary``
...                 (API SAP GUI Scripting via COM). Suite AUTO-SUFFISANTE : elle n'importe
...                 aucune resource ni aucune suite existante du projet : tous les mots-clés
...                 métier sont définis localement au-dessus de ``SapEccLibrary``.
...
...                 Trois scénarios, chacun relevé PUIS validé live sur le système cible
...                 (SAP GUI 8.00 / A4H, client 001, 2026-07-17) :
...
...                 1. Analyse de l'existant : inventaire des *classes de livraison*
...                    (« classes métier »), domaine ``CONTFLAG`` de la table dictionnaire
...                    DD07L. Sur cette version : exactement A / C / E / G / L / S / W.
...                 2. Test d'écriture : cycle CRUD idempotent et RÉVERSIBLE sur SCARR
...                    (classe A, cohérent avec le modèle de données Flight) : création d'un
...                    transporteur de test via SE16 « Create Entries », relecture des
...                    valeurs, suppression, contrôle du retour à zéro. Aucune trace laissée.
...                 3. Vérification en profondeur : chaque table du modèle Flight est ouverte
...                    via SE16 puis comptée : accessible (pas de message de type E) ET non
...                    vide. Data-driven (un verdict par table).
...
...                 Bonnes pratiques respectées :
...                 - Aucun ``Sleep`` : synchronisation par ``Wait Until Busy Done`` /
...                   ``Wait Until Element Present``.
...                 - Assertions indépendantes de la langue : on teste le *type* du message
...                   de statut (``S`` / ``E``) et les *ids techniques* de colonnes
...                   (``CARRID``…), jamais un libellé traduit.
...                 - Aucun id SAP brut dans les cas de test : ils vivent en section
...                   ``*** Variables ***`` et dans la couche de mots-clés.
...
...                 Exécution (`Secret` RF 7.4 : le mot de passe typé dès la ligne de
...                 commande n'apparaît jamais dans les logs, même en TRACE) :
...                 | robot --pythonpath src
...                 |     -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER
...                 |     -v "SAP_PASSWORD: Secret:<motdepasse>" -v SAP_CLIENT:001 -v SAP_LANGUAGE:EN
...                 |     tests/robot/exploratory_campaign_a4h.robot

Library             SapEccLibrary    screenshots_on_error=${True}    default_timeout=30s
Library             Collections

Suite Setup         Open SAP And Log In
Suite Teardown      Close SAP Cleanly


*** Variables ***
# --- Paramètres de connexion (surchargables via -v en ligne de commande) --------
${SAP_CONNECTION}       /H/vhcala4hci/S/3200
${SAP_USER}             DEVELOPER
${SAP_PASSWORD}         ${EMPTY}      # OBLIGATOIRE : fournir via -v "SAP_PASSWORD: Secret:<motdepasse>"
${SAP_CLIENT}           001
${SAP_LANGUAGE}         EN

# --- Localisateurs SAP GUI (jamais dans les cas de test ; relevés live A4H, GUI 8.00) -----
# Écran initial / écran de sélection SE16
${SE16_TABLE_FIELD}         wnd[0]/usr/ctxtDATABROWSE-TABLENAME
${SE16_GRID}                wnd[0]/usr/cntlGRID1/shellcont/shell
${SE16_MAX_HITS_FIELD}      wnd[0]/usr/txtMAX_SEL
${SE16_FIRST_SEL_FIELD}     wnd[0]/usr/ctxtI1-LOW      # 1er critère positionnel (= CARRID pour SCARR, DOMNAME pour DD07L)
${SE16_COUNT_BUTTON}        wnd[0]/tbar[1]/btn[31]     # « Number of Entries » : fiable même quand le résultat est 0
${SE16_COUNT_POPUP}         wnd[1]/usr/txtG_DBCOUNT    # compteur affiché dans le popup « Number of Entries »
# Objets tolérés en rejet par DIALOGUE de message au balayage profond : la référence
# live (2026-08-17) en compte zéro. Au-delà, le balayage échoue en nommant les objets.
${MAX_DIALOG_REJECTS}       ${0}
# Bascule de sortie SE16 en grille ALV (Settings > User Parameters)
${SE16_SETTINGS_MENU}       wnd[0]/mbar/menu[3]/menu[0]
${SE16_ALV_GRID_RADIO}      wnd[1]/usr/tabsG_TABSTRIP/tabp0400/ssubTOOLAREA:SAPLWB_CUSTOMIZING:0400/radRSEUMOD-TBALV_GRID
# Chemin de suppression depuis la grille de résultats SE16
${SE16_MENU_SELECT_ALL}     wnd[0]/mbar/menu[1]/menu[0]    # Edit > Select All
${SE16_MENU_DELETE_SEL}     wnd[0]/mbar/menu[0]/menu[6]    # Table Entry > Delete  (⚠ menu[5] = « Delete all », NE JAMAIS utiliser)
${SE16_DELETE_ENTRY_BUTTON}    wnd[0]/tbar[1]/btn[14]      # « Delete Entry » sur l'écran de suppression mono-enregistrement
# Popup « connexion multiple »
${MULTI_LOGON_RADIO}        wnd[1]/usr/radMULTI_LOGON_OPT1
# Écran « Create Entries » de SCARR
${SCARR_CREATE_MENU}        wnd[0]/mbar/menu[0]/menu[1]    # Table > Create Entries
${SCARR_FIELD_CARRID}       wnd[0]/usr/ctxtSCARR-CARRID
${SCARR_FIELD_CARRNAME}     wnd[0]/usr/txtSCARR-CARRNAME
${SCARR_FIELD_CURRCODE}     wnd[0]/usr/ctxtSCARR-CURRCODE
${SCARR_FIELD_URL}          wnd[0]/usr/txtSCARR-URL
# Écran de sélection TADIR (inventaire du référentiel) : champs positionnels I<n>, types vérifiés live
${TADIR_OBJECT_FIELD}       wnd[0]/usr/ctxtI2-LOW     # OBJECT (TABL, VIEW…)
${TADIR_DEVCLASS_FIELD}     wnd[0]/usr/ctxtI8-LOW     # DEVCLASS (package)

# --- Données du transporteur de test (clé dédiée, sans collision avec les données démo) --
${TEST_CARRID}          ZZ
${TEST_CARRNAME}        QA Test Airways
${TEST_CURRCODE}        EUR
${TEST_URL}             http://qa.example.test

# Classes de livraison attendues sur cette version A4H (domaine CONTFLAG / DD07L),
# triées : l'inventaire exhaustif « classes métier » relevé live.
@{EXPECTED_DELIVERY_CLASSES}    A    C    E    G    L    S    W

# Packages des deux modèles de données démo balayés en profondeur (relevés live via TADIR) :
# SAPBC_DATAMODEL = modèle Flight (SCARR/SPFLI/SFLIGHT…) ; S_NWDEMO_MODEL_DDIC = modèle EPM (SNWD_*).
@{CATALOG_PACKAGES}     SAPBC_DATAMODEL    S_NWDEMO_MODEL_DDIC


*** Test Cases ***
Delivery Classes Available On This System
    [Documentation]    Analyse de l'existant. Le domaine ``CONTFLAG`` (table dictionnaire
    ...                DD07L) énumère les *classes de livraison*, la classification
    ...                « métier » des tables du Dictionnaire ABAP. On vérifie que cette
    ...                version A4H expose exactement les 7 classes A/C/E/G/L/S/W.
    [Tags]    exploration    dictionary
    ${classes}=    Read Delivery Classes
    Log    Classes de livraison disponibles sur le système : ${classes}
    FOR    ${class}    IN    @{EXPECTED_DELIVERY_CLASSES}
        Should Contain    ${classes}    ${class}
        ...    msg=La classe de livraison attendue '${class}' est absente : ${classes}
    END
    Length Should Be    ${classes}    7
    ...    msg=Nombre de classes de livraison inattendu (attendu 7) : ${classes}

Write Read And Delete A Carrier
    [Documentation]    Test d'écriture réversible sur SCARR. Cycle CRUD complet et
    ...                idempotent : pré-nettoyage, création via SE16 « Create Entries »,
    ...                relecture des valeurs écrites, suppression, contrôle du retour à 0.
    ...                Le test ne laisse aucune trace dans la base : il est ré-exécutable
    ...                autant de fois que voulu.
    [Tags]    write    crud
    # Départ propre : retire un éventuel reliquat d'un run précédent interrompu.
    Delete Test Carrier
    Carrier Count Should Be    0

    # Écriture
    Create Test Carrier

    # Vérification : présence (compte = 1) ET valeurs relues champ par champ.
    Carrier Count Should Be    1
    Test Carrier Should Have Expected Data

    # Suppression explicite + contrôle du retour à zéro.
    Delete Test Carrier
    Carrier Count Should Be    0

Flight Data Tables Are Accessible And Populated
    [Documentation]    Vérification en profondeur. Chaque table du modèle de données Flight
    ...                est ouverte via SE16 puis comptée. Une ligne échoue si la table est
    ...                inaccessible (nom rejeté → message de type E) ou vide (0 entrée).
    ...                Data-driven : un verdict individuel par table dans le rapport.
    [Tags]    verification    data
    [Template]    Table Should Be Accessible And Non Empty
    SCARR
    SPFLI
    SFLIGHT
    SBOOK
    SCUSTOM
    SAIRPORT
    # SGEOCITY reste attendue : son dialogue « ABAP Dictionary type FLTP is not allowed
    # for dynpro element » (1er accès depuis la re-création du conteneur) est INFORMATIF ;
    # une fois refermé par la couche keywords, la table se compte (62 entrées live
    # 2026-08-17). La retirer aurait réduit la couverture sans raison.
    SGEOCITY
    STRAVELAG
    SBUSPART
    SCOUNTER

Deep Catalog Sweep Of Flight And EPM Models
    [Documentation]    Vérification EN PROFONDEUR, dynamique. Plutôt qu'une liste figée, le
    ...                catalogue est DÉCOUVERT à l'exécution via TADIR : tous les objets
    ...                ``R3TR TABL`` des packages ``SAPBC_DATAMODEL`` (modèle Flight) et
    ...                ``S_NWDEMO_MODEL_DDIC`` (modèle EPM / SNWD). Chaque objet reçoit un
    ...                verdict : soit une table réelle consultable (comptée via SE16, 0
    ...                admis), soit une structure / include rejetée par SE16 (message de
    ...                type E ; TADIR ne distingue pas les deux), soit un rejet par
    ...                DIALOGUE de message (l'écran de sélection n'est jamais atteint :
    ...                texte relevé et journalisé, dialogue refermé). Le test échoue si un
    ...                package ne livre aucune table réelle ou aucune donnée. Les tables
    ...                vides, les structures et les rejets par dialogue sont journalisés,
    ...                jamais mis en échec : une table démo légitimement vide reste
    ...                « accessible ».
    [Tags]    verification    data    deep
    FOR    ${package}    IN    @{CATALOG_PACKAGES}
        ${stats}=    Deep Verify Package Catalog    ${package}
        Should Be True    ${stats}[tables] > 0
        ...    msg=Le package ${package} n'expose aucune table réelle consultable.
        Should Be True    ${stats}[total_rows] > 0
        ...    msg=Le package ${package} ne contient aucune donnée (0 ligne au total).
        # Un rejet par dialogue est une ANOMALIE, pas un genre d'objet : la référence
        # live (2026-08-17) en compte zéro, SGEOCITY compris (son dialogue informatif
        # se referme et la table se compte). Sans cette borne, une régression qui se
        # manifeste en dialogue bloquant glisse du compte « tables » vers le seau
        # « dialog » et le balayage reste vert. Relever ${MAX_DIALOG_REJECTS} est un
        # choix explicite, jamais un effet de bord.
        Should Be True    ${stats}[dialogs] <= ${MAX_DIALOG_REJECTS}
        ...    msg=${package} : ${stats}[dialogs] objet(s) rejeté(s) par un dialogue de message (borne ${MAX_DIALOG_REJECTS}) : ${stats}[dialog_rejects]. Percevoir l'écran (Get Screen Signature) avant de relever la borne.
    END


*** Keywords ***
Open SAP And Log In
    [Documentation]    Suite Setup. Lance le Logon Pad, ouvre la connexion, s'authentifie,
    ...                gère le popup « connexion multiple », puis bascule la sortie SE16 en
    ...                grille ALV (prérequis à toute lecture de grille). Le mot de passe
    ...                n'est jamais journalisé (log level abaissé le temps de la saisie).
    # Should Not Be Equal (et non Should Not Be Empty) : tolère un mot de passe
    # de type Secret RF 7.4, qui n'a pas de longueur mesurable.
    Should Not Be Equal    ${SAP_PASSWORD}    ${EMPTY}
    ...    msg=SAP_PASSWORD est vide : fournissez-le via -v "SAP_PASSWORD: Secret:<motdepasse>".
    Open Sap Logon
    Connect To Session With Retry
    # Une chaîne « /H/hôte/S/port » (système Docker/local) n'a pas d'entrée SAP Logon :
    # on passe alors par Open Connection By String ; sinon par le nom d'entrée enregistrée.
    IF    "${SAP_CONNECTION}".startswith("/")
        Open Connection By String    ${SAP_CONNECTION}
    ELSE
        Open Connection    ${SAP_CONNECTION}
    END
    Maximize Window
    Input Text    wnd[0]/usr/txtRSYST-MANDT    ${SAP_CLIENT}
    Input Text    wnd[0]/usr/txtRSYST-BNAME    ${SAP_USER}
    ${previous_level}=    Set Log Level    NONE
    Input Password    wnd[0]/usr/pwdRSYST-BCODE    ${SAP_PASSWORD}
    Set Log Level    ${previous_level}
    Input Text    wnd[0]/usr/txtRSYST-LANGU    ${SAP_LANGUAGE}
    Send Vkey    0
    Wait Until Busy Done
    Handle Multiple Logon Popup
    Enable ALV Grid In SE16

Close SAP Cleanly
    [Documentation]    Suite Teardown. Garde de nettoyage (retire le transporteur de test
    ...                si un échec l'a laissé en base), quitte la session (/nex) et arrête
    ...                le Logon Pad. Chaque étape est tolérante aux erreurs pour ne jamais
    ...                masquer l'échec réel d'un test.
    Run Keyword And Ignore Error    Delete Test Carrier
    Run Keyword And Ignore Error    Run Transaction    /nex
    Close Sap Logon

Handle Multiple Logon Popup
    [Documentation]    SAP affiche un dialogue « licence / connexion multiple » quand le
    ...                même utilisateur est déjà connecté ailleurs. On choisit « continuer
    ...                avec cette connexion » si le dialogue est présent ; sinon, rien.
    ${present}=    Run Keyword And Return Status    Element Should Be Present    ${MULTI_LOGON_RADIO}
    IF    ${present}
        Select Radio Button    ${MULTI_LOGON_RADIO}
        Click Element    wnd[1]/tbar[0]/btn[0]
        Wait Until Busy Done
    END

Enable ALV Grid In SE16
    [Documentation]    Bascule la sortie du Data Browser (SE16) de l'utilisateur courant en
    ...                grille ALV (Settings > User Parameters). Réglage persistant par
    ...                utilisateur et idempotent. Indispensable : la « Standard SE16 list »
    ...                (défaut) est une liste ABAP classique SANS objet grille scriptable.
    Start Transaction    SE16
    Click Element    ${SE16_SETTINGS_MENU}
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_ALV_GRID_RADIO}
    Select Radio Button    ${SE16_ALV_GRID_RADIO}
    Send Vkey    0    window=1
    Wait Until Busy Done

Start Transaction
    [Documentation]    Ouvre un code transaction et attend la stabilisation de l'écran.
    [Arguments]    ${tcode}
    Run Transaction    ${tcode}
    Wait Until Busy Done

Open Table In SE16
    [Documentation]    Ouvre SE16 sur ``${table}`` et ATTEINT son écran de sélection.
    ...                Échoue explicitement si SE16 rejette le nom (message de statut de
    ...                type ``E`` : structure, include ou table inconnue). L'assertion
    ...                porte sur le *type*, jamais sur le texte localisé. SE16 peut aussi
    ...                répondre par un DIALOGUE de message modal (vécu SGEOCITY après
    ...                re-création du conteneur : « ABAP Dictionary type FLTP is not
    ...                allowed for dynpro element », dialogue informatif émis à la
    ...                génération de l'écran de sélection) : le texte est relevé pour le
    ...                journal, le dialogue refermé, et on continue si l'écran de
    ...                sélection s'ouvre quand même derrière (cas SGEOCITY : la table se
    ...                compte normalement ensuite, 62 entrées live 2026-08-17).
    [Arguments]    ${table}
    # Tout le pilotage (statut de type E, popup « choix des champs », dialogue de
    # message de génération, attente de l'écran généré) vit dans le keyword de
    # bibliothèque : une seule implémentation, ici comme dans la couche resources.
    ${state}=    Reach Se16 Selection Screen    ${table}
    IF    not $state["reached"]
        Fail    SE16 n'ouvre pas la table '${table}' (verdict ${state}[verdict], message de type '${state}[message_type]') : ${state}[status_text] ${state}[dialog_text]
    END

Count Table Entries
    [Documentation]    Compte les entrées de ``${table}`` via SE16 > « Number of Entries »
    ...                (fiable même à 0, contrairement à F8 qui reste sur l'écran de
    ...                sélection sans résultat). Filtre optionnel sur le premier critère
    ...                positionnel (``${key}`` = CARRID pour SCARR). Renvoie un entier ;
    ...                les séparateurs de milliers du profil utilisateur sont retirés.
    [Arguments]    ${table}    ${key}=${EMPTY}
    Open Table In SE16    ${table}
    IF    '${key}' != '${EMPTY}'
        Input Text    ${SE16_FIRST_SEL_FIELD}    ${key}
    END
    Click Element    ${SE16_COUNT_BUTTON}
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_COUNT_POPUP}
    ${raw}=    Get Value    ${SE16_COUNT_POPUP}
    Send Vkey    12    window=1
    Wait Until Busy Done
    # Filtrage caractère par caractère (pas de regex : \\d dans une cellule Robot traverse
    # deux couches d'échappement et change de sens) : retire les « . » de milliers.
    ${count}=    Evaluate    int(''.join(c for c in $raw if c.isdigit()) or 0)
    RETURN    ${count}

Read Delivery Classes
    [Documentation]    Lit les valeurs autorisées du domaine ``CONTFLAG`` (classes de
    ...                livraison) dans la table dictionnaire DD07L et les renvoie triées,
    ...                sans doublon.
    Open Table In SE16    DD07L
    Input Text    ${SE16_FIRST_SEL_FIELD}    CONTFLAG
    Input Text    ${SE16_MAX_HITS_FIELD}    500
    Send Vkey    8
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_GRID}
    ${rows}=    Read Grid    ${SE16_GRID}    max_rows=50
    # Sur cet A4H, la grille ALV de SE16 titre ses colonnes par l'id technique : DOMVALUE_L.
    ${classes}=    Evaluate    sorted({r['DOMVALUE_L'] for r in $rows})
    RETURN    ${classes}

Create Test Carrier
    [Documentation]    Insère le transporteur de test dans SCARR via SE16 > Create Entries,
    ...                puis enregistre (Ctrl+S). Exige un message de statut de succès (S).
    ...                « Create Entries » se déclenche depuis l'écran INITIAL de SE16 (menu
    ...                Table) : on n'avance donc PAS jusqu'à l'écran de sélection, où
    ...                ``menu[0]/menu[1]`` serait « Execute and Print ».
    Start Transaction    SE16
    Input Text    ${SE16_TABLE_FIELD}    SCARR
    Click Element    ${SCARR_CREATE_MENU}
    Wait Until Busy Done
    Wait Until Element Present    ${SCARR_FIELD_CARRID}
    Input Text    ${SCARR_FIELD_CARRID}      ${TEST_CARRID}
    Input Text    ${SCARR_FIELD_CARRNAME}    ${TEST_CARRNAME}
    Input Text    ${SCARR_FIELD_CURRCODE}    ${TEST_CURRCODE}
    Input Text    ${SCARR_FIELD_URL}         ${TEST_URL}
    Send Vkey    11
    Wait Until Busy Done
    ${type}    ${message}=    Get Status Message
    Should Be Equal    ${type}    S
    ...    msg=La création du transporteur ${TEST_CARRID} n'a pas confirmé un succès : (${type}) ${message}

Test Carrier Should Have Expected Data
    [Documentation]    Relit le transporteur de test (filtre CARRID) et vérifie chaque champ
    ...                écrit. Les clés de ligne sont les ids techniques (CARRID, CARRNAME…),
    ...                jamais des libellés dépendants de la langue.
    Open Table In SE16    SCARR
    Input Text    ${SE16_FIRST_SEL_FIELD}    ${TEST_CARRID}
    Send Vkey    8
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_GRID}
    ${rows}=    Read Grid    ${SE16_GRID}    max_rows=10
    Length Should Be    ${rows}    1
    ...    msg=Attendu exactement 1 ligne pour CARRID=${TEST_CARRID}.
    ${row}=    Set Variable    ${rows}[0]
    Should Be Equal    ${row}[CARRID]      ${TEST_CARRID}
    Should Be Equal    ${row}[CARRNAME]    ${TEST_CARRNAME}
    Should Be Equal    ${row}[CURRCODE]    ${TEST_CURRCODE}
    Should Be Equal    ${row}[URL]         ${TEST_URL}

Carrier Count Should Be
    [Documentation]    Vérifie que SCARR contient ``${expected}`` entrée(s) pour la clé du
    ...                transporteur de test.
    [Arguments]    ${expected}
    ${count}=    Count Table Entries    SCARR    key=${TEST_CARRID}
    Should Be Equal As Integers    ${count}    ${expected}
    ...    msg=SCARR devrait contenir ${expected} entrée(s) CARRID=${TEST_CARRID}, trouvé ${count}.

Delete Test Carrier
    [Documentation]    Supprime le transporteur de test s'il existe (idempotent : ne fait
    ...                rien s'il est absent). Filtre d'abord sur CARRID pour ne JAMAIS
    ...                sélectionner d'autres lignes, puis Edit>Select All, Table Entry>Delete
    ...                et « Delete Entry » (qui commite en base). Utilisé en pré-nettoyage,
    ...                dans le test, et en garde de Suite Teardown.
    Open Table In SE16    SCARR
    Input Text    ${SE16_FIRST_SEL_FIELD}    ${TEST_CARRID}
    Send Vkey    8
    Wait Until Busy Done
    # 0 ligne -> F8 reste sur l'écran de sélection (pas de grille) : rien à supprimer.
    ${present}=    Run Keyword And Return Status    Wait Until Element Present    ${SE16_GRID}    timeout=5s
    IF    not ${present}    RETURN
    Click Element    ${SE16_MENU_SELECT_ALL}
    Wait Until Busy Done
    Click Element    ${SE16_MENU_DELETE_SEL}
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_DELETE_ENTRY_BUTTON}
    Click Element    ${SE16_DELETE_ENTRY_BUTTON}
    Wait Until Busy Done
    ${type}    ${message}=    Get Status Message
    Should Be Equal    ${type}    S
    ...    msg=La suppression de ${TEST_CARRID} n'a pas confirmé un succès : (${type}) ${message}

Table Should Be Accessible And Non Empty
    [Documentation]    Verdict data-driven : ``${table}`` s'ouvre via SE16 (sinon échec de
    ...                type E dans ``Open Table In SE16``) ET contient au moins une entrée.
    [Arguments]    ${table}
    ${count}=    Count Table Entries    ${table}
    Should Be True    ${count} > 0
    ...    msg=La table ${table} est accessible mais vide (0 entrée).
    Log    ${table} : ${count} entrées

List Tables In Package
    [Documentation]    Inventaire du référentiel (table TADIR) : tous les noms d'objets
    ...                ``R3TR TABL`` du package ``${package}``. Renvoie une liste triée sans
    ...                doublon. Lève si la lecture atteint ``${max_hits}`` (troncature
    ...                probable) : un inventaire tronqué en silence fausserait le balayage.
    [Arguments]    ${package}    ${max_hits}=1000
    Open Table In SE16    TADIR
    Input Text    ${TADIR_OBJECT_FIELD}    TABL
    Input Text    ${TADIR_DEVCLASS_FIELD}    ${package}
    Input Text    ${SE16_MAX_HITS_FIELD}    ${max_hits}
    Send Vkey    8
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_GRID}
    ${rows}=    Read Full Grid    ${SE16_GRID}    max_rows=${max_hits}
    ${names}=    Evaluate    sorted({r['OBJ_NAME'] for r in $rows})
    ${discovered}=    Get Length    ${names}
    IF    ${discovered} >= ${max_hits}
        Fail    Inventaire TADIR de ${package} probablement tronqué (${discovered} lignes = max_hits ${max_hits}). Augmentez max_hits.
    END
    RETURN    ${names}

Classify And Count Table
    [Documentation]    Donne un verdict à un objet TADIR ``TABL``. Ouvre SE16 sur
    ...                ``${table}`` : un message de statut de type ``E`` = structure /
    ...                include (non consultable) ; un DIALOGUE de message modal qui
    ...                empêche d'atteindre l'écran de sélection = rejet par dialogue
    ...                (texte relevé et journalisé, dialogue refermé, jamais mis en
    ...                échec) ; sinon c'est une table réelle, comptée via « Number of
    ...                Entries ». Renvoie DEUX valeurs : le genre (``table`` |
    ...                ``structure`` | ``dialog``) et le nombre de lignes (``-1`` hors
    ...                ``table``). L'assertion porte sur le *type* du message et la
    ...                STRUCTURE de l'écran, jamais sur un texte localisé.
    [Arguments]    ${table}
    # Même keyword de bibliothèque que `Open Table In SE16` : le verdict structuré
    # (reached | rejected | dialog | modal) remplace la détection recopiée. Les
    # comparaisons sont en forme EXPRESSION ($state[...]), jamais une interpolation
    # entre apostrophes : un texte SAP contenant une apostrophe casserait l'évaluation.
    ${state}=    Reach Se16 Selection Screen    ${table}
    IF    $state["verdict"] == "rejected"    RETURN    structure    ${-1}
    IF    not $state["reached"]
        Log    Table '${table}' rejetée par dialogue de message : ${state}[dialog_text]
        RETURN    dialog    ${-1}
    END
    Click Element    ${SE16_COUNT_BUTTON}
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_COUNT_POPUP}
    ${raw}=    Get Value    ${SE16_COUNT_POPUP}
    Send Vkey    12    window=1
    Wait Until Busy Done
    ${count}=    Evaluate    int(''.join(c for c in $raw if c.isdigit()) or 0)
    RETURN    table    ${count}

# La détection/absorption du DIALOGUE DE MESSAGE modal (programme SAPMSDYP, lignes
# ``txtMESSTXT<n>``) vivait ici en deux copies ; elle est désormais DANS la
# bibliothèque (`Reach Se16 Selection Screen`), qui la traite de façon structurelle,
# relève le texte pour le seul journal et rend un verdict. Une copie, pas trois.

Deep Verify Package Catalog
    [Documentation]    Découvre le catalogue TADIR de ``${package}`` puis balaie chaque
    ...                objet (classification + comptage). Journalise un verdict par objet et
    ...                un récapitulatif, et renvoie les statistiques agrégées (objets
    ...                découverts, tables réelles, structures, rejets par dialogue, total
    ...                de lignes).
    [Arguments]    ${package}
    ${tables}=    List Tables In Package    ${package}
    ${discovered}=    Get Length    ${tables}
    ${n_tables}=    Set Variable    ${0}
    ${n_structures}=    Set Variable    ${0}
    ${n_dialogs}=    Set Variable    ${0}
    ${total_rows}=    Set Variable    ${0}
    @{empty_tables}=    Create List
    @{dialog_rejects}=    Create List
    FOR    ${obj}    IN    @{tables}
        ${kind}    ${count}=    Classify And Count Table    ${obj}
        IF    '${kind}' == 'structure'
            ${n_structures}=    Evaluate    ${n_structures} + 1
            Log    ${package} / ${obj} : structure (rejetée par SE16, type E)
        ELSE IF    '${kind}' == 'dialog'
            ${n_dialogs}=    Evaluate    ${n_dialogs} + 1
            Append To List    ${dialog_rejects}    ${obj}
            Log    ${package} / ${obj} : rejeté par un dialogue de message SE16 (texte relevé plus haut dans le log ; journalisé, jamais mis en échec)
        ELSE
            ${n_tables}=    Evaluate    ${n_tables} + 1
            ${total_rows}=    Evaluate    ${total_rows} + ${count}
            Log    ${package} / ${obj} : ${count} entrées
            IF    ${count} == 0    Append To List    ${empty_tables}    ${obj}
        END
    END
    Log    RÉCAP ${package} : ${discovered} objets TABL = ${n_tables} tables réelles (${total_rows} lignes cumulées) + ${n_structures} structures + ${n_dialogs} rejets par dialogue. Tables vides : ${empty_tables}. Rejets par dialogue : ${dialog_rejects}
    ${stats}=    Create Dictionary    package=${package}    discovered=${discovered}
    ...    tables=${n_tables}    structures=${n_structures}    dialogs=${n_dialogs}
    ...    total_rows=${total_rows}    dialog_rejects=${dialog_rejects}
    RETURN    ${stats}
