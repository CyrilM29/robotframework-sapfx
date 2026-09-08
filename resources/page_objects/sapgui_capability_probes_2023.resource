*** Settings ***
Documentation       **EXEMPLE À PERSONNALISER** : ce fichier porte le vocabulaire
...                 métier du LABORATOIRE de ce dépôt (identifiants d'écran, chemins
...                 de contrôles et textes relevés live sur SA cible ABAP Platform
...                 2023). Beaucoup s'y réutilise tel quel ailleurs (les écrans
...                 sondés sont des transactions Basis standard), mais rien n'y fait
...                 autorité : à VÉRIFIER sur votre cible et à adapter à votre
...                 métier. Ce qui fait foi partout, c'est `src/`, les bibliothèques,
...                 qui portent les capacités : voir `resources/README.md`.
...
...                 Page object des **sondes de capacité SAP GUI d'une SECONDE
...                 release** : les écrans sur lesquels la campagne
...                 `specs/reconnaissance-couverture-sapgui-abap2023.md` mesure ce que
...                 SapEccLibrary sait (et ne sait pas) faire sur ABAP Platform 2023,
...                 release SAP_BASIS 758, kernel 793. Il n'apporte QUE des écrans et
...                 des sondes : le vocabulaire de VERDICT (registre, artefact
...                 déterministe, assertions de forme) vit dans
...                 `capability_register.resource`, partagé avec la campagne 754, sans
...                 quoi deux campagnes deviendraient incomparables.
...
...                 Contrat, et c'est l'invariant de la campagne : aucun manque n'est
...                 contourné ici. Chaque mot-clé appelle les keywords de bibliothèque
...                 TELS QU'ILS SONT (aucun JS, aucun `Evaluate` sur un objet COM,
...                 aucun helper Python local) ; un keyword absent se prouve par
...                 `Un Keyword Devrait Etre Absent`, un keyword cassé s'appelle sous
...                 filet et son échec s'asserte. Le verdict est DÉRIVÉ de ce qui est
...                 observé et confronté au plan par la suite : une capacité qui
...                 change rougit la suite en nommant la mise à jour du registre, ce
...                 fichier ne s'adapte pas.
...
...                 Relevé live le 2026-09-08 (SAP GUI 8.00, session EN, mandant 001).
...                 Les textes localisés (chemin du menu System, libellé du bouton
...                 SPRO, nom des entrées de menu) vivent ICI, jamais dans la suite
...                 (convention 3) ; les ids SAP GUI aussi (convention 1). LECTURE
...                 SEULE : aucune exécution qui écrit, aucune donnée créée ; les
...                 seules valeurs posées le sont dans le champ « Table Name » de
...                 l'écran initial SE16, jamais persistant. Le seul réglage
...                 persistant touché est la sortie du Data Browser, posée en Suite
...                 Setup comme dans toutes les suites SE16.

Library             Collections
Library             OperatingSystem
Library             String
Library             sapfx_common.robot_args
Resource            ../ecc_keywords.resource
Resource            capability_register.resource


*** Variables ***
# Le registre porte son propre nom de fichier : deux campagnes, deux cibles, deux
# registres, même dans un dossier de sortie partagé.
${REGISTER_2023_PATH}           ${OUTPUT DIR}/ecc_capability_register_2023.json

# --- Identité de la cible, relevée à l'écran (System > Status) ----------------
# Le chemin de TEXTES est localisé : il vit ici. C'est aussi la voie que l'échec
# de `Get System Identity` prescrit sur cette release.
${MENU_SYSTEM_STATUS_PATH}      System > Status
${MENU_SYSTEM_TEXT}             System
${MENU_STATUS_TEXT}             Status...
# Le dialogue « System: Status » (SAPLSHSY/<tcode>/700) et ses deux popups.
${STATUS_CLIENT_FIELD}          wnd[1]/usr/txtSYST-MANDT
${STATUS_USER_FIELD}            wnd[1]/usr/txtSYST-UNAME
${STATUS_SERVER_FIELD}          wnd[1]/usr/txtSERVERNAME
${STATUS_DETAILS_BUTTON}        wnd[1]/usr/btnPRELINFO
${STATUS_KERNEL_BUTTON}         wnd[1]/tbar[0]/btn[17]
${KERNEL_RELEASE_FIELD}         wnd[2]/usr/txtKINFOSTRUC-KERNEL_RELEASE
${KERNEL_PATCH_FIELD}           wnd[2]/usr/txtKINFOSTRUC-KERNEL_PATCH_LEVEL
${COMPONENTS_GRID}              wnd[2]/usr/tabsVERSDETAILS/tabpCOMP_VERS/ssubDETAIL_SUBSCREEN:SAPLOCS_UI_CONTROLS:0301/cntlSCV_CU_CONTROL/shellcont/shell
${COMPONENTS_COLUMNS}           COMPONENT,RELEASE,EXTRELEASE
${COMPONENTS_MAX_ROWS}          30
${BASIS_COMPONENT}              SAP_BASIS
# Ce que la CIBLE doit annoncer : les deux conteneurs du laboratoire partagent
# SID et hôte, seules ces deux valeurs les séparent.
${EXPECTED_BASIS_RELEASE}       758
${EXPECTED_KERNEL_RELEASE}      793
# La position MESURÉE de « Status... » sur cette release (10 ; 11 sur la 754,
# l'indice que la bibliothèque gravait avant le lot du 2026-09-08 : elle
# RÉSOUT désormais l'avant-dernière entrée et ne grave plus rien).
${MEASURED_STATUS_ENTRY_INDEX}    10

# --- Écrans sondés pour la disposition de la barre de menus -------------------
@{PROBED_SCREENS}               SESSION_MANAGER    SE16    SU01    SM37    SE38    SE11
${HOME_TRANSACTION}             SESSION_MANAGER
${HOME_USER_MENU_TREE}          wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell

# --- SE16 : refus applicatifs et barre de statut ------------------------------
${SE16_ABSENT_TABLE}            ZZ_TABLE_INEXISTANTE
${STATUS_BAR_ID}                wnd[0]/sbar
# Identité EXACTE des deux refus, relevée sur l'API au matin du 2026-09-08 (à
# l'époque exposée par AUCUN keyword ; `Get Status Message Identity` la rend
# depuis le lot du soir) : la classe est `MO` (complétée à droite sur 20
# caractères côté API, ce padding n'est pas une donnée) et les numéros sont
# ceux-ci. Des CONSTANTES DE CIBLE, que le scénario 3 confronte à la lecture.
${MESSAGE_CLASS_SE16}           MO
${MESSAGE_NUMBER_ABSENT_TABLE}    402
${MESSAGE_NUMBER_EMPTY_NAME}    410
# Le type d'un refus SE16 (locale-safe), pour la forme couverte du scénario 3.
${MESSAGE_TYPE_ERROR}           E
# Le popup « Number of Entries » du scénario 5 couvert : bouton par SEGMENT
# d'id (stable depuis des décennies) et compteur du popup (chiffres seuls).
${SE16_COUNT_BUTTON_SEGMENT}    btn[31]
${SE16_COUNT_RESULT}            wnd[1]/usr/txtG_DBCOUNT
# Onglets SU01 par CLÉ technique (forme couverte du scénario 4) ; le libellé
# est localisé et ne sert qu'à exercer `Select Tab By Label`.
${SU01_DEFAULTS_TAB_ID}        DEFA
${SU01_DEFAULTS_TAB_LABEL}      Defaults
${SU01_NEW_TAB_ID}             USAT

# --- SU01 en affichage : le tabstrip ------------------------------------------
${SU01_USER_FIELD}              wnd[0]/usr/ctxtSUID_ST_BNAME-BNAME
${SU01_TABSTRIP}                wnd[0]/usr/tabsTABSTRIP1
${TABSTRIP_TYPE}                GuiTabStrip
${TAB_TYPE}                     GuiTab
# Douze onglets sur la 758 contre onze sur la 754 : `USAT` est nouveau. Un
# FAIT DE CIBLE, asserté HORS verdict par le scénario 4.
${SU01_TAB_COUNT}               12
# Un onglet INACTIF ne rend aucun sous-écran : c'est l'ancre structurelle de
# « l'onglet est actif », et le numéro de sous-écran (1105 ici) dépend de la
# release, donc il n'est pas gravé.
${SU01_DEFAULTS_MARKER}         tabpDEFA/

# --- Barre d'application (SE16, écran de sélection) ---------------------------
${APPLICATION_TOOLBAR}          wnd[0]/tbar[1]
${APPLICATION_TOOLBAR_MARKER}    /tbar[1]/btn[
# Cinq boutons sur l'écran de sélection SE16 de cette release : un FAIT DE
# CIBLE, asserté HORS verdict par le scénario 5.
${APPLICATION_TOOLBAR_BUTTONS}    5

# --- SPRO : l'arbre de l'IMG et son conteneur ---------------------------------
${SPRO_REFERENCE_IMG_LABEL}     SAP Reference IMG
${SPRO_IMG_TREE}                wnd[0]/usr/cntlTREE_CONTROL_CONTAINER/shellcont/shell
${SPRO_IMG_TREE_CONTAINER}      wnd[0]/usr/cntlTREE_CONTROL_CONTAINER/shellcont

# --- SE16 sur T000 : la grille enveloppée dans un splitter --------------------
${SE16_PROBE_TABLE}             T000
# ${SE16_GRID} vient de ecc_keywords.resource : sur la 758 ce chemin porte le
# SPLITTER, la grille vivant un niveau plus bas.
${SE16_GRID_SPLITTER_TYPE}      GuiSplitterShell/Splitter
${SE16_GRID_INNER}              wnd[0]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell
${SE16_GRID_INNER_TYPE}         GuiShell/GridView
${SE16_FIRST_COLUMN}            MANDT
${SE16_REFERENCE_CLIENT}        000

# --- SE38 : l'éditeur ABAP ----------------------------------------------------
${SE38_EDITOR}                  wnd[0]/usr/cntlEDITOR/shellcont/shell
${SE38_PROBE_PROGRAM}           RSPARAM
${SE38_EDITOR_SUBTYPE}          AbapEditor

# --- La session ne dit ni la release ni le kernel -----------------------------
@{SESSION_RELEASE_FIELDS}       release    basis_release    kernel_release    kernel
@{SESSION_IDENTITY_FIELDS}      system    client    user
# La sonde COM de `session.Info` (vingt et une propriétés lisibles, aucune
# release ni kernel) est CONSERVÉE dans les preuves du plan, clé
# `hors_api_measure` : c'est là que le fait d'API se vérifie, pas ici.
${SESSION_INFO_EVIDENCE}        specs/evidence/reconnaissance-couverture-sapgui-abap2023.2026-09-08.json


*** Keywords ***

# ---------------------------------------------------------------------------
# Vocabulaire de verdict propre à cette campagne
# ---------------------------------------------------------------------------

Verdict Hors Api
    [Documentation]    Le troisième dérivateur de verdict, aux côtés de
    ...                `Verdict De Manque` et `Verdict De Capacite` (qui vivent dans
    ...                `capability_register.resource`) : ``hors_api`` quand l'API SAP
    ...                GUI n'expose PAS la donnée (observation vraie), ``covered``
    ...                sinon. Il vit ici parce que la campagne 754 n'avait aucun
    ...                témoin de ce genre ; le contrat est le même, le verdict est
    ...                DÉRIVÉ d'une observation et jamais posé, et le jour où l'API
    ...                exposerait la donnée le scénario rougirait en nommant le
    ...                registre.
    [Arguments]    ${hors_api_observe}
    IF    ${hors_api_observe}
        RETURN    hors_api
    END
    RETURN    covered

# ---------------------------------------------------------------------------
# Cycle de la campagne
# ---------------------------------------------------------------------------

Ouvrir La Campagne De Reconnaissance 758
    [Documentation]    Suite Setup : session unique, préflight scripting, sortie SE16
    ...                en grille ALV (réglage persistant idempotent), puis l'identité
    ...                de la cible MESURÉE À LA MAIN par le chemin de textes du menu
    ...                (et non par `Get System Identity`, pour que le scénario 1
    ...                confronte le keyword à une mesure INDÉPENDANTE de lui ; au
    ...                matin du 2026-09-08 c'était aussi le manque n°1 de cette
    ...                release), et un registre de capacités VIDE en variable de suite.
    Open SAP And Log In
    Scripting Should Be Fully Enabled
    Use ALV Grid In Data Browser
    ${cible}=    Identite Mesuree A L Ecran
    Le Systeme Lu Devrait Etre Celui De La Session    ${cible}
    # La PORTE de release : les deux conteneurs du laboratoire annoncent le
    # même SID, un run contre l'autre s'arrête ici, avant le premier scénario.
    La Cible Devrait Etre La Release Attendue    ${cible}
    Set Suite Variable    ${CAPABILITY_TARGET}    ${cible}
    ${registre}=    Create Dictionary
    Set Suite Variable    ${CAPABILITY_REGISTER}    ${registre}

Clore La Campagne De Reconnaissance 758
    [Documentation]    Suite Teardown : écrit le registre PUIS ferme la session, les
    ...                deux même si l'un échoue (sémantique de teardown Robot).
    Ecrire Le Registre Des Capacites    ${REGISTER_2023_PATH}
    Close SAP

Revenir Au Menu
    [Documentation]    Test Teardown : referme jusqu'à deux popups, puis revient au
    ...                menu SAP Easy Access par l'OK-code `/n`.
    Cancel Popup
    Cancel Popup
    Run Transaction    /n
    Wait Until Busy Done

Ouvrir L Accueil
    [Documentation]    Revient à l'accueil SAP Easy Access et attend l'arbre du menu
    ...                utilisateur. `/n` DEPUIS l'accueil laisse un écran vide sans
    ...                arbre, et lancer le tcode DEPUIS l'accueil ouvre le modal
    ...                « Cannot start transaction » : le tcode n'est donc lancé que
    ...                si l'arbre manque.
    Revenir Au Menu
    ${present}=    Run Keyword And Return Status    Element Should Be Present    ${HOME_USER_MENU_TREE}
    IF    not ${present}
        Run Transaction    ${HOME_TRANSACTION}
        Wait Until Busy Done
    END
    Wait Until Element Present    ${HOME_USER_MENU_TREE}

Ouvrir L Ecran
    [Documentation]    Atteint l'écran d'entrée de ``${tcode}`` : l'accueil passe par
    ...                `Ouvrir L Accueil` (piège du modal « Cannot start transaction »),
    ...                les autres transactions par `Go To Transaction`.
    [Arguments]    ${tcode}
    IF    '${tcode}' == '${HOME_TRANSACTION}'
        Ouvrir L Accueil
    ELSE
        Go To Transaction    ${tcode}
    END

# ---------------------------------------------------------------------------
# Scénario 1 : l'identité du système
# ---------------------------------------------------------------------------

Identite Mesuree A L Ecran
    [Documentation]    L'identité de la cible relevée À LA MAIN : le dialogue
    ...                « System: Status » ouvert par le CHEMIN DE TEXTES, l'ancre
    ...                structurelle vérifiée, la release SAP_BASIS lue dans la grille
    ...                des composants (colonnes techniques) et le kernel dans son
    ...                popup, tout refermé. Retourne le dict de cible du registre
    ...                (``system_id``, ``client``, ``user``, ``basis_release``,
    ...                ``basis_sp_level``, ``kernel_release``, ``kernel_patch_level``,
    ...                ``server_name``, ``status_menu_id``), jamais d'objet COM.
    ${menu_id}=    Select Menu Item    ${MENU_SYSTEM_STATUS_PATH}
    Wait Until Element Present    ${STATUS_CLIENT_FIELD}
    ${client}=    Get Value    ${STATUS_CLIENT_FIELD}
    ${user}=    Get Value    ${STATUS_USER_FIELD}
    ${serveur}=    Get Value    ${STATUS_SERVER_FIELD}
    ${sid}=    Identifiant Systeme Du Serveur    ${serveur}
    Click Element    ${STATUS_DETAILS_BUTTON}
    Wait Until Element Present    ${COMPONENTS_GRID}
    ${composants}=    Read Grid    ${COMPONENTS_GRID}
    ...    columns=${COMPONENTS_COLUMNS}    max_rows=${COMPONENTS_MAX_ROWS}
    Dismiss Modal Window    2
    ${basis}=    Ligne Du Composant    ${composants}    ${BASIS_COMPONENT}
    Click Element    ${STATUS_KERNEL_BUTTON}
    Wait Until Element Present    ${KERNEL_RELEASE_FIELD}
    ${kernel}=    Get Value    ${KERNEL_RELEASE_FIELD}
    ${kernel_pl}=    Get Value    ${KERNEL_PATCH_FIELD}
    Dismiss Modal Window    2
    Dismiss Modal Window    1
    ${cible}=    Create Dictionary
    ...    system_id=${sid}    client=${client}    user=${user}
    ...    basis_release=${basis}[RELEASE]    basis_sp_level=${basis}[EXTRELEASE]
    ...    kernel_release=${kernel}    kernel_patch_level=${kernel_pl}
    ...    server_name=${serveur}    status_menu_id=${menu_id}
    RETURN    ${cible}

Identifiant Systeme Du Serveur
    [Documentation]    Le SID extrait du nom de serveur d'applications
    ...                (``hôte_SID_instance``) ; échoue si le nom ne suit pas cette
    ...                forme plutôt que de rendre un identifiant plausible.
    [Arguments]    ${serveur}
    @{parties}=    Split String    ${serveur}    _
    Length Should Be    ${parties}    3
    ...    msg=Nom de serveur '${serveur}' hors de la forme hôte_SID_instance : le SID n'est pas déductible.
    RETURN    ${parties}[1]

Ligne Du Composant
    [Documentation]    La ligne du composant ``${nom}`` dans les lignes lues de
    ...                « Installed Software » ; échoue en nommant le plafond de
    ...                lecture si le composant n'y figure pas (une troncature
    ...                muette rendrait une release vide).
    [Arguments]    ${lignes}    ${nom}
    ${trouvees}=    Evaluate    [r for r in $lignes if r.get('COMPONENT') == $nom]
    Should Not Be Empty    ${trouvees}
    ...    msg=Composant ${nom} absent des ${COMPONENTS_MAX_ROWS} première(s) ligne(s) lue(s) de « Installed Software » : relever le plafond ou vérifier l'écran.
    RETURN    ${trouvees}[0]

Le Systeme Lu Devrait Etre Celui De La Session
    [Documentation]    Échoue si le SID lu dans « System: Status » n'est pas celui de
    ...                la session SAP active et connectée : un registre qui nommerait
    ...                une autre cible que celle qu'il a mesurée ne décrirait rien.
    [Arguments]    ${cible}
    ${entree}=    Entree De Session Active
    Should Be Equal    ${cible}[system_id]    ${entree}[system]
    ...    msg=Le statut système lit le SID '${cible}[system_id]' mais la session active porte '${entree}[system]'.

La Cible Devrait Etre La Release Attendue
    [Documentation]    Échoue si la cible mesurée ne porte pas la release SAP_BASIS et
    ...                la release de kernel attendues : les deux conteneurs du
    ...                laboratoire annoncent le même SID et le même hôte, seules ces
    ...                deux valeurs les séparent.
    [Arguments]    ${cible}
    Should Be Equal    ${cible}[basis_release]    ${EXPECTED_BASIS_RELEASE}
    ...    msg=Release SAP_BASIS '${cible}[basis_release]', attendu '${EXPECTED_BASIS_RELEASE}' : campagne jouée contre un autre système ?
    Should Be Equal    ${cible}[kernel_release]    ${EXPECTED_KERNEL_RELEASE}
    ...    msg=Release du kernel '${cible}[kernel_release]', attendu '${EXPECTED_KERNEL_RELEASE}' : campagne jouée contre un autre système ?

# ---------------------------------------------------------------------------
# Scénario 2 : la disposition de la barre de menus
# ---------------------------------------------------------------------------

Positions Du Menu System
    [Documentation]    Relevé de la barre de menus de l'écran ``${ecran}`` :
    ...                ``menus`` (menus de tête), ``index_system`` (position de
    ...                l'avant-dernier), ``texte_system``, ``entrees`` (entrées de ce
    ...                menu) et ``position_status`` (position de « Status... », -1 si
    ...                absent). Tout est DÉRIVÉ de `List Menu Items`, rien n'est gravé.
    [Arguments]    ${ecran}
    ${items}=    List Menu Items
    ${tops}=    Evaluate    [i for i in $items if len(i['positions']) == 1]
    Should Be True    len($tops) >= 2
    ...    msg=La barre de menus de ${ecran} porte moins de deux menus de tête : ${tops}
    ${systeme}=    Set Variable    ${tops}[-2]
    ${index}=    Set Variable    ${systeme}[positions][0]
    ${entrees}=    Evaluate
    ...    [i for i in $items if len(i['positions']) == 2 and i['positions'][0] == $index]
    ${positions}=    Evaluate
    ...    [i['positions'][1] for i in $entrees if i['text'] == $MENU_STATUS_TEXT]
    ${releve}=    Create Dictionary
    ...    ecran=${ecran}    menus=${{ len($tops) }}    index_system=${index}
    ...    texte_system=${systeme}[text]    entrees=${{ len($entrees) }}
    ...    position_status=${{ $positions[0] if $positions else -1 }}
    RETURN    ${releve}

Le Releve De Menu Devrait Etre Coherent
    [Documentation]    Échoue si, sur l'écran relevé, l'avant-dernier menu de tête
    ...                n'est pas le menu System, si « Status... » n'y figure pas, ou
    ...                si ce n'est pas l'AVANT-DERNIÈRE entrée du menu (l'ancre qui
    ...                tient sur les deux releases, contrairement à la position).
    [Arguments]    ${releve}
    Should Be Equal    ${releve}[texte_system]    ${MENU_SYSTEM_TEXT}
    ...    msg=Sur ${releve}[ecran], l'avant-dernier menu de tête est '${releve}[texte_system]' et non le menu System.
    Should Be Equal As Integers    ${releve}[index_system]    ${{ $releve['menus'] - 2 }}
    ...    msg=Sur ${releve}[ecran], le menu System est en position ${releve}[index_system] pour ${releve}[menus] menus de tête.
    Should Be True    ${releve}[position_status] >= 0
    ...    msg=Sur ${releve}[ecran], aucune entrée « ${MENU_STATUS_TEXT} » dans le menu System.
    Should Be Equal As Integers    ${releve}[position_status]    ${{ $releve['entrees'] - 2 }}
    ...    msg=Sur ${releve}[ecran], « ${MENU_STATUS_TEXT} » est en position ${releve}[position_status] pour ${releve}[entrees] entrées : ce n'est pas l'avant-dernière.

La Position Mesuree Devrait Etre Celle De Cette Release
    [Documentation]    Échoue si la position MESURÉE de « Status... » n'est pas celle
    ...                relevée sur cette release (10 ; la 754 avait 11) : le fait de
    ...                cible qui a fondé la résolution par « avant-dernière entrée ».
    [Arguments]    ${releve}
    Should Be Equal As Integers    ${releve}[position_status]    ${MEASURED_STATUS_ENTRY_INDEX}
    ...    msg=Sur ${releve}[ecran], « ${MENU_STATUS_TEXT} » est en position ${releve}[position_status], attendu ${MEASURED_STATUS_ENTRY_INDEX} sur cette release.

# ---------------------------------------------------------------------------
# Scénario 3 : l'identité d'un refus applicatif
# ---------------------------------------------------------------------------

Provoquer Un Refus SE16
    [Documentation]    Pose ``${valeur}`` dans « Table Name » de l'écran initial SE16,
    ...                valide par Entrée, et retourne le TYPE et le TEXTE du message
    ...                de statut. Lecture seule : rien n'est exécuté.
    [Arguments]    ${valeur}
    Go To Transaction    SE16
    Input Text    ${SE16_TABLE_FIELD}    ${valeur}
    Send Vkey    0
    Wait Until Busy Done
    ${type}    ${texte}=    Get Status Message
    Log    Refus SE16 pour '${valeur}' : type='${type}' texte='${texte}'
    RETURN    ${type}    ${texte}

# ---------------------------------------------------------------------------
# Scénario 4 : les onglets (SU01 en affichage)
# ---------------------------------------------------------------------------

Afficher L Utilisateur
    [Documentation]    SU01, utilisateur ``${user}``, F7 (affichage) ; attend le
    ...                tabstrip de la fiche utilisateur. LECTURE SEULE.
    [Arguments]    ${user}
    Go To Transaction    SU01
    Input Text    ${SU01_USER_FIELD}    ${user}
    Send Vkey    7
    Wait Until Busy Done
    Wait Until Element Present    ${SU01_TABSTRIP}

Sous Ecran De L Onglet Defaults
    [Documentation]    Les lignes de signature du sous-écran de l'onglet « Defaults » :
    ...                VIDES tant que l'onglet n'est pas actif (un onglet inactif ne
    ...                rend rien), non vides ensuite. L'ancre structurelle de
    ...                « l'onglet est actif », le numéro de sous-écran variant par
    ...                release.
    ${signature}=    Get Screen Signature
    ${lignes}=    Get Lines Containing String    ${signature}    ${SU01_DEFAULTS_MARKER}
    RETURN    ${lignes}

# ---------------------------------------------------------------------------
# Scénario 5 : la barre d'application
# ---------------------------------------------------------------------------

Ouvrir L Ecran De Selection SE16
    [Documentation]    Atteint l'écran de sélection SE16 de ``${table}`` par
    ...                `Reach Se16 Selection Screen` (statut, popup de choix de
    ...                champs, dialogue de génération) ; échoue si l'écran n'est pas
    ...                atteint, en rendant le verdict.
    [Arguments]    ${table}=${SE16_PROBE_TABLE}
    ${verdict}=    Reach Se16 Selection Screen    ${table}
    Should Be True    ${verdict}[reached]
    ...    msg=L'écran de sélection de ${table} n'est pas atteint : ${verdict}
    RETURN    ${verdict}

# ---------------------------------------------------------------------------
# Scénario 6 : deux lecteurs de contrôle visés sur un conteneur
# ---------------------------------------------------------------------------

Ouvrir L IMG De Reference
    [Documentation]    SPRO, bouton « SAP Reference IMG » par libellé ; attend l'arbre
    ...                à colonnes de l'IMG. LECTURE SEULE.
    Go To Transaction    SPRO
    Click Button By Label    ${SPRO_REFERENCE_IMG_LABEL}
    Wait Until Busy Done
    Wait Until Element Present    ${SPRO_IMG_TREE}

Lire Les Noeuds De L IMG
    [Documentation]    `Read Tree Nodes` sur l'ARBRE lui-même (le contre-exemple du
    ...                scénario : visé juste, le lecteur fonctionne).
    ${noeuds}=    Read Tree Nodes    ${SPRO_IMG_TREE}
    RETURN    ${noeuds}

Tenter Read Tree Nodes Sur Le Conteneur
    [Documentation]    `Read Tree Nodes` visé sur le CONTENEUR de l'arbre.
    ${noeuds}=    Read Tree Nodes    ${SPRO_IMG_TREE_CONTAINER}
    RETURN    ${noeuds}

Tenter Read Grid Sur Le Conteneur
    [Documentation]    `Read Grid` visé sur le CONTENEUR de l'arbre.
    ${lignes}=    Read Grid    ${SPRO_IMG_TREE_CONTAINER}    max_rows=3
    RETURN    ${lignes}

Colonnes Vues Par Le Resolveur De Grille
    [Documentation]    `Get Grid Column Ids` visé sur le CONTENEUR de l'arbre. Au
    ...                matin du 2026-09-08 il PASSAIT en rendant ``HierarchyHeader``,
    ...                la colonne d'un arbre de type 2 (le résolveur s'arrêtait au
    ...                premier descendant portant ``ColumnOrder``) ; depuis le lot du
    ...                soir le SOUS-TYPE décide et il REFUSE en nommant le contrôle.
    ${colonnes}=    Get Grid Column Ids    ${SPRO_IMG_TREE_CONTAINER}
    RETURN    ${colonnes}

# ---------------------------------------------------------------------------
# Scénario 7 : la grille enveloppée dans un splitter
# ---------------------------------------------------------------------------

Afficher T000 En Grille
    [Documentation]    SE16 sur T000, exécution (F8), grille ALV attendue au
    ...                localisateur historique (qui porte le splitter sur cette
    ...                release). LECTURE SEULE.
    Display Table Contents    ${SE16_PROBE_TABLE}

Localisateur De Grille SE16
    [Documentation]    Le localisateur de grille SE16 de la couche resources, celui
    ...                que la 758 fait pointer sur un splitter.
    RETURN    ${SE16_GRID}

Sous Type Percu
    [Documentation]    Le TYPE (sous-type compris, ``GuiShell/GridView``,
    ...                ``GuiSplitterShell/Splitter``) que la perception rend pour
    ...                ``${id}`` : la colonne TYPE de sa ligne de signature.
    [Arguments]    ${id}
    ${signature}=    Get Screen Signature
    ${ligne}=    Get Lines Containing String    ${signature}    ${id}\t
    Should Not Be Empty    ${ligne}
    ...    msg=La signature de l'écran ne porte pas de ligne pour '${id}'.
    @{colonnes}=    Split String    ${ligne}    \t
    RETURN    ${colonnes}[1]

Colonnes De La Grille SE16
    [Documentation]    `Get Grid Column Ids` sur le localisateur de grille SE16 : les
    ...                ids TECHNIQUES, malgré le conteneur intermédiaire.
    ${colonnes}=    Get Grid Column Ids    ${SE16_GRID}
    RETURN    ${colonnes}

Lire La Grille SE16
    [Documentation]    `Read Grid` sur le localisateur de grille SE16, restreint à la
    ...                colonne clé (locale-safe).
    [Arguments]    ${max_rows}=5
    ${lignes}=    Read Grid    ${SE16_GRID}    columns=${SE16_FIRST_COLUMN}    max_rows=${max_rows}
    RETURN    ${lignes}

La Grille Devrait Porter Le Mandant De Reference
    [Documentation]    Échoue si aucune ligne lue ne porte le mandant de référence
    ...                (``000``, présent dans T000 de tout système ABAP) : l'ancre
    ...                locale-safe d'une ligne de données.
    [Arguments]    ${lignes}
    ${trouvees}=    Evaluate
    ...    [r for r in $lignes if str(r.get($SE16_FIRST_COLUMN, '')).strip() == $SE16_REFERENCE_CLIENT]
    Should Not Be Empty    ${trouvees}
    ...    msg=Aucune ligne au mandant ${SE16_REFERENCE_CLIENT} dans les ${lignes.__len__()} ligne(s) lue(s).

# ---------------------------------------------------------------------------
# Scénario 8 : l'éditeur ABAP
# ---------------------------------------------------------------------------

Afficher Le Programme
    [Documentation]    SE38, programme ``${nom}``, F7 (affichage) ; attend le contrôle
    ...                éditeur. LECTURE SEULE : aucune exécution.
    [Arguments]    ${nom}
    Go To Transaction    SE38
    Input Text    ${SE38_PROGRAM_FIELD}    ${nom}
    Send Vkey    7
    Wait Until Busy Done
    Wait Until Element Present    ${SE38_EDITOR}

Tenter De Lire Le Controle Editeur
    [Documentation]    `Get Value` sur le contrôle éditeur ABAP : le refus EST la
    ...                capacité (le source est hors API Scripting).
    ${valeur}=    Get Value    ${SE38_EDITOR}
    RETURN    ${valeur}

Statut De Rendu De L Ecran
    [Documentation]    `Get List Rendering Status` sur l'écran courant.
    ${statut}=    Get List Rendering Status
    RETURN    ${statut}

Le Prefight De Liste Devrait Reconnaitre Le Sous Type
    [Documentation]    Échoue si le préflight de rendu ne relève pas le sous-type
    ...                attendu, ou s'il réclame le mode accessibilité du poste là où
    ...                le sous-type est lisible.
    [Arguments]    ${statut}    ${sous_type}
    List Should Contain Value    ${statut}[shell_subtypes]    ${sous_type}
    ...    msg=Sous-types relevés ${statut}[shell_subtypes], attendu ${sous_type}.
    Should Not Be True    ${statut}[accessibility_mode_needed]
    ...    msg=Le préflight réclame le mode accessibilité sur un shell de sous-type connu : ${statut}

# ---------------------------------------------------------------------------
# Scénario 9 : ce que la session ne dit pas
# ---------------------------------------------------------------------------

Entree De Session Active
    [Documentation]    L'entrée de la session SAP active et connectée dans
    ...                `List Sap Sessions` : la seule vue de ``session.Info`` qu'un
    ...                keyword rende (avec `Get Session Telemetry`), JSON-safe et
    ...                sans aucun identifiant.
    ${sessions}=    List Sap Sessions
    ${actives}=    Evaluate    [s for s in $sessions if s.get('active') and s.get('connected')]
    Length Should Be    ${actives}    1
    ...    msg=Aucune session SAP active et connectée (sessions : ${sessions}).
    RETURN    ${actives}[0]

Telemetrie De Session
    [Documentation]    `Get Session Telemetry` : l'autre lecture de ``session.Info``
    ...                exposée par un keyword (compteurs de performance).
    ${telemetrie}=    Get Session Telemetry
    RETURN    ${telemetrie}

Champs Absents De
    [Documentation]    Les noms de ``@{noms}`` ABSENTS des clés de ``${carte}``.
    [Arguments]    ${carte}    @{noms}
    ${absents}=    Evaluate    [n for n in $noms if n not in $carte]
    RETURN    ${absents}

Cles Triees De
    [Documentation]    Les CLÉS triées de ``${carte}``, c'est-à-dire ce que la vue
    ...                expose, sans ses valeurs. C'est la forme qui entre dans le
    ...                registre : les compteurs de `Get Session Telemetry` sont des
    ...                mesures de RUN (temps de réponse, temps d'interprétation), donc
    ...                les consigner ferait diverger l'empreinte de deux runs aux mêmes
    ...                verdicts, et l'artefact ne serait plus déterministe (mesuré à la
    ...                génération, 2026-09-08). L'observation du scénario porte sur les
    ...                champs PRÉSENTS et ABSENTS, jamais sur leur valeur.
    [Arguments]    ${carte}
    ${cles}=    Evaluate    sorted($carte)
    RETURN    ${cles}

La Session Devrait Nommer Son Identite Sans Sa Release
    [Documentation]    Échoue si la vue de session perd les champs d'identité
    ...                (système, mandant, utilisateur) OU si elle porte une release ou
    ...                un kernel : le manque est que la release n'y est pas, et le
    ...                jour où elle y sera, ce scénario doit rougir.
    [Arguments]    ${entree}    ${telemetrie}
    FOR    ${champ}    IN    @{SESSION_IDENTITY_FIELDS}
        Dictionary Should Contain Key    ${entree}    ${champ}
        ...    msg=La vue de session ne porte plus le champ d'identité '${champ}' : ${entree}
    END
    ${absents_session}=    Champs Absents De    ${entree}    @{SESSION_RELEASE_FIELDS}
    Length Should Be    ${absents_session}    ${{ len($SESSION_RELEASE_FIELDS) }}
    ...    msg=La vue de session expose désormais une release ou un kernel : ${entree}
    ${absents_telemetrie}=    Champs Absents De    ${telemetrie}    @{SESSION_RELEASE_FIELDS}
    Length Should Be    ${absents_telemetrie}    ${{ len($SESSION_RELEASE_FIELDS) }}
    ...    msg=La télémétrie de session expose désormais une release ou un kernel : ${telemetrie}

# ---------------------------------------------------------------------------
# Scénario 10 : le registre
# ---------------------------------------------------------------------------

Ecrire Le Registre De La Cible
    [Documentation]    Écrit le registre de CETTE campagne (son propre fichier : deux
    ...                cibles, deux registres) par l'artefact déterministe générique.
    ${chemin}=    Ecrire Le Registre Des Capacites    ${REGISTER_2023_PATH}
    RETURN    ${chemin}

Relire Le Registre De La Cible
    [Documentation]    Relit le registre de cette campagne, empreinte RECALCULÉE sur
    ...                le périmètre déclaré.
    ${registre}=    Relire Le Registre Des Capacites    ${REGISTER_2023_PATH}
    RETURN    ${registre}

La Cible Du Registre Devrait Porter La Release
    [Documentation]    Échoue si la section ``target`` du registre relu ne porte pas la
    ...                release SAP_BASIS et la release de kernel MESURÉES : un registre
    ...                qui ne nomme que le SID ne distingue pas les deux systèmes du
    ...                laboratoire.
    [Arguments]    ${registre}
    ${cible}=    L Identite De La Cible Devrait Etre Renseignee    ${registre}
    La Cible Devrait Etre La Release Attendue    ${cible}
    RETURN    ${cible}

# ---------------------------------------------------------------------------
# Forme COUVERTE (lot de correction du 2026-09-08) : les keywords livrés,
# exercés là où les scénarios du matin prouvaient leur absence
# ---------------------------------------------------------------------------

Identite Par Keyword
    [Documentation]    `Get System Identity` : le dialogue « System: Status »
    ...                ouvert par POSITION RÉSOLUE (avant-dernière entrée de
    ...                l'avant-dernier menu, dialogue exigé), lu, refermé.
    ${identite}=    Get System Identity
    RETURN    ${identite}

L Identite Par Keyword Devrait Egaler La Mesure Manuelle
    [Documentation]    Échoue si l'identité rendue par le keyword diffère de celle
    ...                relevée À LA MAIN (chemin de textes) sur une des sept clés
    ...                d'identité, ou si une section n'a pas été lue.
    [Arguments]    ${identite}    ${cible}
    FOR    ${champ}    IN    system_id    client    user    basis_release    basis_sp_level
    ...    kernel_release    kernel_patch_level
        Should Be Equal    ${identite}[${champ}]    ${cible}[${champ}]
        ...    msg=Le keyword lit ${champ}='${identite}[${champ}]', la mesure manuelle '${cible}[${champ}]'.
    END
    Should Be Empty    ${identite}[unread]
    ...    msg=Sections non lues par Get System Identity : ${identite}[unread]

L Identite Devrait Etre Celle De Cette Release
    [Documentation]    `System Identity Should Be` sur la release et le kernel
    ...                attendus de CETTE cible : la garde de tête d'une campagne.
    [Arguments]    ${identite}
    System Identity Should Be    identity=${identite}
    ...    basis_release=${EXPECTED_BASIS_RELEASE}    kernel_release=${EXPECTED_KERNEL_RELEASE}

Ouvrir Puis Refermer Le Statut Par Keyword
    [Documentation]    `Open System Status` (résolution de l'entrée par la
    ...                bibliothèque, dialogue vérifié) puis `Dismiss Modal Window`
    ...                sur le dialogue ; retourne l'id de l'entrée de menu que la
    ...                bibliothèque a CLIQUÉE, sa trace de résolution.
    ${entree}=    Open System Status
    Dismiss Modal Window    1
    RETURN    ${entree}

L Entree Resolue Devrait Etre Celle Du Texte
    [Documentation]    Échoue si l'entrée que `Open System Status` a cliquée n'est
    ...                pas, par sa position, celle que le relevé par TEXTE
    ...                (« Status... ») désigne dans le menu System de l'écran : la
    ...                résolution de la bibliothèque (points de suspension,
    ...                avant-dernière entrée) est confrontée à une lecture qui ne
    ...                dépend pas d'elle.
    [Arguments]    ${entree}    ${releve}
    ${positions}=    Evaluate    [int(seg[5:-1]) for seg in $entree.split('/') if seg.startswith('menu[')]
    Length Should Be    ${positions}    2
    ...    msg=L'entrée cliquée '${entree}' n'est pas une entrée de second niveau de la barre de menus.
    Should Be Equal As Integers    ${positions}[0]    ${releve}[index_system]
    ...    msg=Sur ${releve}[ecran], la bibliothèque a cliqué dans le menu ${positions}[0] ; le relevé place le menu System en ${releve}[index_system].
    Should Be Equal As Integers    ${positions}[1]    ${releve}[position_status]
    ...    msg=Sur ${releve}[ecran], la bibliothèque a cliqué l'entrée ${positions}[1] ; le relevé par texte place « ${MENU_STATUS_TEXT} » en ${releve}[position_status].

Identite Du Refus SE16
    [Documentation]    Provoque un refus SE16 avec ``${valeur}`` puis lit son identité
    ...                par `Get Status Message Identity` (classe/type/numéro).
    [Arguments]    ${valeur}
    ${type}    ${texte}=    Provoquer Un Refus SE16    ${valeur}
    ${identite}=    Get Status Message Identity
    RETURN    ${identite}

Le Refus Devrait Avoir L Identite
    [Documentation]    Échoue si l'identité lue n'est pas ``MO``/``E``/``${numero}``,
    ...                ou si `Status Message Should Be` ne la reconnaît pas.
    [Arguments]    ${identite}    ${numero}
    Should Be Equal    ${identite}[class]    ${MESSAGE_CLASS_SE16}
    Should Be Equal    ${identite}[number]    ${numero}
    Should Be Equal    ${identite}[type]    ${MESSAGE_TYPE_ERROR}
    Should Be Equal    ${identite}[identity]    ${MESSAGE_CLASS_SE16}/${MESSAGE_TYPE_ERROR}/${numero}
    Status Message Should Be    ${MESSAGE_CLASS_SE16}    ${numero}    ${MESSAGE_TYPE_ERROR}

L Autre Identite Devrait Etre Refusee
    [Documentation]    `Status Message Should Be` avec le numéro de l'AUTRE refus
    ...                doit ÉCHOUER en nommant l'attendu et le lu : c'est la
    ...                discernabilité. Retourne le message d'échec.
    [Arguments]    ${numero_autre}
    ${message}=    Run Keyword And Expect Error
    ...    *attendu ${MESSAGE_CLASS_SE16}/*/${numero_autre}, lu ${MESSAGE_CLASS_SE16}/${MESSAGE_TYPE_ERROR}/*
    ...    Status Message Should Be    ${MESSAGE_CLASS_SE16}    ${numero_autre}
    RETURN    ${message}

Les Onglets Par Keyword
    [Documentation]    `List Tabs` sur le tabstrip de SU01 (clé technique, libellé,
    ...                actif).
    ${onglets}=    List Tabs    ${SU01_TABSTRIP}
    RETURN    ${onglets}

Onglet Actif
    [Documentation]    `Get Selected Tab` sur le tabstrip de SU01 : rend la CLÉ.
    ${onglet}=    Get Selected Tab    ${SU01_TABSTRIP}
    RETURN    ${onglet}[key]

Activer L Onglet Par Cle
    [Documentation]    `Select Tab` par clé technique ; rend la clé de l'onglet
    ...                devenu actif (vérifiée par le keyword).
    [Arguments]    ${cle}
    ${onglet}=    Select Tab    ${SU01_TABSTRIP}    ${cle}
    RETURN    ${onglet}[key]

Activer L Onglet Par Libelle
    [Documentation]    `Select Tab By Label` (libellé LOCALISÉ, porté ici) ; rend la
    ...                clé de l'onglet devenu actif.
    [Arguments]    ${libelle}
    ${onglet}=    Select Tab By Label    ${SU01_TABSTRIP}    ${libelle}    exact=True
    RETURN    ${onglet}[key]

Les Onglets Devraient Etre Lisibles
    [Documentation]    Échoue si la liste rendue par `List Tabs` est vide, si un
    ...                onglet n'y porte pas ``id``/``key``/``text``/``selected``, ou si
    ...                ce n'est pas EXACTEMENT un onglet qui est actif : la forme que
    ...                la bibliothèque doit rendre sur tout tabstrip, sans rien
    ...                supposer de cette release. C'est ce qui entre dans le verdict.
    [Arguments]    ${onglets}
    Should Not Be Empty    ${onglets}    msg=List Tabs rend une liste vide.
    ${incomplets}=    Evaluate    [o for o in $onglets if not all(k in o for k in ('id', 'key', 'text', 'selected'))]
    Should Be Empty    ${incomplets}    msg=Onglets sans id/key/text/selected : ${incomplets}
    ${actifs}=    Evaluate    [o['key'] for o in $onglets if o['selected']]
    Length Should Be    ${actifs}    1    msg=Onglets marqués actifs : ${actifs} (exactement un attendu).

Les Onglets Devraient Etre Ceux De Cette Release
    [Documentation]    Échoue si la liste n'a pas ${SU01_TAB_COUNT} onglets ou si la
    ...                clé apparue sur cette release (``USAT``) n'y est pas : un FAIT
    ...                DE CIBLE relevé le 2026-09-08, asserté HORS verdict (la 754 en
    ...                a onze sans qu'aucune capacité manque).
    [Arguments]    ${onglets}
    Length Should Be    ${onglets}    ${SU01_TAB_COUNT}
    ${cles}=    Evaluate    [o['key'] for o in $onglets]
    List Should Contain Value    ${cles}    ${SU01_NEW_TAB_ID}
    ...    msg=L'onglet ${SU01_NEW_TAB_ID} n'est pas listé : écran ou release différents de la mesure (${cles}).

Inventaire De La Barre D Application
    [Documentation]    `List Toolbar Buttons` sur la barre d'application (id, texte,
    ...                tooltip, icône).
    ${boutons}=    List Toolbar Buttons
    RETURN    ${boutons}

L Inventaire Devrait Etre Lisible
    [Documentation]    Échoue si l'inventaire de `List Toolbar Buttons` est vide ou si
    ...                un bouton n'y porte pas ``id``/``text``/``tooltip``/``icon`` : la
    ...                forme attendue sur toute barre d'application. C'est ce qui
    ...                entre dans le verdict.
    [Arguments]    ${boutons}
    Should Not Be Empty    ${boutons}    msg=List Toolbar Buttons rend une liste vide.
    ${incomplets}=    Evaluate    [b for b in $boutons if not all(k in b for k in ('id', 'text', 'tooltip', 'icon'))]
    Should Be Empty    ${incomplets}    msg=Boutons sans id/text/tooltip/icon : ${incomplets}

L Inventaire Devrait Porter Le Compteur
    [Documentation]    Échoue si l'inventaire ne porte pas le bouton de comptage
    ...                (segment ``btn[31]``, stable depuis des décennies sur l'écran
    ...                de sélection SE16) : la PRÉCONDITION du clic du scénario 5, un
    ...                fait d'écran et non une capacité.
    [Arguments]    ${boutons}
    ${segments}=    Evaluate    [b['id'].rsplit('/', 1)[-1] for b in $boutons]
    List Should Contain Value    ${segments}    ${SE16_COUNT_BUTTON_SEGMENT}
    ...    msg=Le bouton de comptage ${SE16_COUNT_BUTTON_SEGMENT} n'est pas dans l'inventaire : ${segments}

La Barre Devrait Avoir Les Boutons De Cette Release
    [Documentation]    Échoue si l'inventaire n'a pas ${APPLICATION_TOOLBAR_BUTTONS}
    ...                boutons : un FAIT DE CIBLE relevé le 2026-09-08, asserté HORS
    ...                verdict (une autre release peut en porter six sans qu'aucune
    ...                capacité manque).
    [Arguments]    ${boutons}
    Length Should Be    ${boutons}    ${APPLICATION_TOOLBAR_BUTTONS}

Compter Par La Barre D Application
    [Documentation]    `Click Application Toolbar Button` sur le segment du bouton de
    ...                comptage : le popup « Number of Entries » s'ouvre, son
    ...                compteur est lu (chiffres seuls) et le popup refermé. Rend
    ...                l'entier lu.
    ${id}=    Click Application Toolbar Button    ${SE16_COUNT_BUTTON_SEGMENT}
    Wait Until Element Present    ${SE16_COUNT_RESULT}
    ${affiche}=    Get Value    ${SE16_COUNT_RESULT}
    ${nombre}=    Displayed Count    ${affiche}
    Dismiss Modal Window    1
    RETURN    ${nombre}

Tenter Read Grid Sur L Arbre
    [Documentation]    `Read Grid` visé sur l'ARBRE lui-même : doit refuser en nommant
    ...                `GuiShell/Tree` et le lecteur d'arbre.
    ${lignes}=    Read Grid    ${SPRO_IMG_TREE}    max_rows=1
    RETURN    ${lignes}
