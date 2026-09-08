*** Settings ***
Documentation       **EXEMPLE À PERSONNALISER** : ce fichier porte le vocabulaire
...                 métier du LABORATOIRE de ce dépôt (identifiants d'écran, chemins
...                 de contrôles et noms d'objets relevés live sur SES cibles).
...                 Beaucoup s'y réutilise tel quel sur un autre système (les écrans
...                 sondés sont des transactions Basis standard), mais rien n'y fait
...                 autorité : à VÉRIFIER sur votre cible et à adapter à votre
...                 métier. Ce qui fait foi partout, c'est `src/`, les bibliothèques,
...                 qui portent les capacités : voir `resources/README.md`.
...
...                 Page object des **sondes de capacité SAP GUI** : les écrans sur
...                 lesquels la campagne `specs/reconnaissance-couverture-sapgui-a4h.md`
...                 exerce, capacité par capacité, ce que SapEccLibrary sait faire
...                 (SESSION_MANAGER et son arbre de menu, SU01 en affichage, SM37,
...                 SE16 sur T000 en grille, SE38 en affichage, l'IMG de SPRO), et
...                 le **registre des capacités** (verdicts `gap` / `covered` /
...                 `poste` / `hors_api`, JSON trié et déterministe, identité de la
...                 cible mesurée en Suite Setup).
...
...                 Contrat, et c'est l'invariant de la campagne : aucun manque n'est
...                 contourné ici. Chaque mot-clé appelle les keywords de bibliothèque
...                 TELS QU'ILS SONT (aucun JS, aucun `Evaluate` sur un objet COM,
...                 aucun helper Python local). Le verdict est DÉRIVÉ de ce qui est
...                 observé (`Verdict De Capacite`, `Verdict De Manque`) et confronté
...                 au plan par la suite : une capacité qui cesse de tenir rougit la
...                 suite en nommant la mise à jour du registre, ce fichier ne
...                 s'adapte pas. Pour un FUTUR manque, l'absence d'un keyword se
...                 prouve par `Un Keyword Devrait Etre Absent` (`Keyword Should
...                 Exist` inversé) : ce vocabulaire est conservé à cette fin.
...
...                 Relevé live le 2026-09-07 sur A4H 1909 (SAP GUI 8.00, session
...                 EN), forme COUVERTE depuis le lot de correction du même soir
...                 (les mots-clés du matin qui reproduisaient les keywords hérités
...                 cassés ont été retirés). Les textes localisés (libellés, chemin
...                 du menu System, texte propre de la case, forme locale de la
...                 date de sonde) vivent ICI, jamais dans la suite (convention 3) ;
...                 les ids SAP GUI aussi (convention 1). LECTURE SEULE : les seules
...                 valeurs posées le sont dans l'écran de sélection SM37, jamais
...                 exécuté, et remises à leur valeur initiale relue.

Library             OperatingSystem
Library             String
Resource            ../ecc_keywords.resource
Resource            capability_register.resource


*** Variables ***
# Le registre de capacités (verdicts, artefact) vit dans
# `capability_register.resource`, partagé avec les autres campagnes.

# --- SESSION_MANAGER (SAPLSMTR_NAVIGATION/SESSION_MANAGER/100) ---------------
# Le menu utilisateur est un GuiShell de SubType Tree (GetTreeType = 1).
${SM_USER_MENU_TREE}            wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell
${SM_TREE_PLAIN_ABAP_TEXT}       Plain ABAP    # texte du dossier (menu utilisateur de DEVELOPER, EN)
# « System > Status » : POSITION relevée sur A4H 1909 en EN ; le menu System est
# en règle générale l'avant-dernier, et sa position varie par transaction. Le
# CHEMIN de textes est localisé : il vit ici, jamais dans la suite.
${SM_MENU_SYSTEM_STATUS}        wnd[0]/mbar/menu[4]/menu[11]
${SM_MENU_SYSTEM_STATUS_PATH}    System > Status
${SM_STATUS_TRANSACTION_LABEL}    Transaction

# --- SU01 en affichage (SAPLSUID_MAINTENANCE/SU01/1100) ----------------------
${SU01_USER_FIELD}              wnd[0]/usr/ctxtSUID_ST_BNAME-BNAME
${SU01_TABSTRIP}                wnd[0]/usr/tabsTABSTRIP1
&{SU01_TABS}
...    Logon Data=wnd[0]/usr/tabsTABSTRIP1/tabpLOGO
...    Defaults=wnd[0]/usr/tabsTABSTRIP1/tabpDEFA
...    Parameters=wnd[0]/usr/tabsTABSTRIP1/tabpPARAM
${SU01_USER_TYPE_COMBO}         wnd[0]/usr/tabsTABSTRIP1/tabpLOGO/ssubMAINAREA:SAPLSUID_MAINTENANCE:1101/cmbSUID_ST_NODE_LOGONDATA-USTYP
${SU01_USER_TYPE_DIALOG_CODE}    A    # la CLÉ technique du type « Dialog », que rien ne rend
${SU01_USER_TYPE_SYSTEM_LABEL}    System    # libellé localisé d'une autre entrée (tentative de sélection)
${SU01_PARAMETERS_GRID}         wnd[0]/usr/tabsTABSTRIP1/tabpPARAM/ssubMAINAREA:SAPLSUID_MAINTENANCE:1104/cntlG_PARAMETER_CONTAINER/shellcont/shell

# --- SM37, Simple Job Selection ----------------------------------------------
${SM37_FROM_DATE}               wnd[0]/usr/ctxtBTCH2170-FROM_DATE
${SM37_EVENT_COMBO}             wnd[0]/usr/cmbBTCH2170-EVENTID
${SM37_EVENT_ANY}               *
# La clé de l'entrée initiale de « Or after event » est un BLANC, distinct de
# la clé VIDE que la combo porte aussi (relevé live : deux entrées) ; c'est la
# valeur que la restauration du scénario 6 doit retrouver telle quelle.
${SM37_EVENT_NONE_CODE}          ${SPACE}
# La case « Sched. » est chkBTCH2170-PRELIM (texte propre abrégé, relevé
# live) ; chkBTCH2170-SCHEDUL porte « Released » : nom technique et texte
# affiché ne se correspondent pas, d'où la résolution par texte propre.
${SM37_SCHEDULED_LABEL}         Sched.
# Le format de date de l'utilisateur DEVELOPER de ce trial est DD.MM.YYYY (SU01,
# onglet Defaults) : la forme ISO est refusée, la forme locale acceptée.
${SM37_PROBE_DATE_ISO}          2026-09-01
${SM37_PROBE_DATE_LOCAL}        01.09.2026

# --- SE16 sur T000 en grille ALV (SAPLSLVC_FULLSCREEN/SE16/500) --------------
# ${SE16_GRID} vient de ecc_keywords.resource.
${SE16_PROBE_TABLE}             T000
${SE16_GRID_FIRST_COLUMN}       MANDT
${SE16_GRID_FIRST_ROW}          0
# Le mandant de référence, présent dans T000 de TOUT système ABAP : l'ancre
# locale-safe d'une ligne de la liste SE16 standard (relevé live 2026-09-07 :
# la liste classique, dynpro SAPMSSY0/120, est rendue en 42 GuiLabel).
${SE16_REFERENCE_CLIENT}        000
${GRID_SORT_DESC_BUTTON}        &SORT_DSC    # code fonction ALV stable, barre de grille VIDE ici
${GRID_FILTER_MENU_CODE}        &FILTER      # code fonction du menu contextuel « Set Filter... »

# --- SE38 en affichage --------------------------------------------------------
${SE38_PROGRAM_FIELD}           wnd[0]/usr/ctxtRS38M-PROGRAMM
${SE38_EDITOR}                  wnd[0]/usr/cntlEDITOR/shellcont/shell
${SE38_PROBE_PROGRAM}           RSPARAM

# --- SPRO, Reference IMG ------------------------------------------------------
${SPRO_REFERENCE_IMG_LABEL}     SAP Reference IMG
# Arbre à colonnes (GetTreeType = 2) : même ProgID que le menu utilisateur.
${SPRO_IMG_TREE}                wnd[0]/usr/cntlTREE_CONTROL_CONTAINER/shellcont/shell


*** Keywords ***

# ---------------------------------------------------------------------------
# Cycle de la campagne
# ---------------------------------------------------------------------------

Ouvrir La Campagne De Reconnaissance
    [Documentation]    Suite Setup : session unique, préflight scripting, identité
    ...                de la cible relevée (système, mandant, utilisateur), sortie
    ...                SE16 en grille ALV (réglage persistant idempotent), formats
    ...                de l'utilisateur mémorisés (SU3, pour `Input Date`), et un
    ...                registre de capacités VIDE en variable de suite.
    Open SAP And Log In
    Scripting Should Be Fully Enabled
    ${cible}=    Identite De La Cible
    Set Suite Variable    ${CAPABILITY_TARGET}    ${cible}
    Use ALV Grid In Data Browser
    Get User Formats
    ${registre}=    Create Dictionary
    Set Suite Variable    ${CAPABILITY_REGISTER}    ${registre}

Identite De La Cible
    [Documentation]    L'identité de la cible mesurée par `Get System Identity`
    ...                (System > Status, ouvert par position et vérifié) : dict
    ...                ``{system_id, client, user, basis_release, basis_sp_level,
    ...                kernel_release, kernel_patch_level, server_name,
    ...                product_version_text, database_system}`` (jamais de mot
    ...                de passe, jamais d'objet COM). Le SID lu à l'écran doit
    ...                être celui de la session active (`List Sap Sessions`) :
    ...                un registre qui nommerait une autre cible que celle qu'il
    ...                a mesurée ne décrirait rien.
    ${identite}=    Get System Identity
    Le Systeme Lu Devrait Etre Celui De La Session    ${identite}
    ${cible}=    Create Dictionary
    ...    system_id=${identite}[system_id]    client=${identite}[client]    user=${identite}[user]
    ...    basis_release=${identite}[basis_release]    basis_sp_level=${identite}[basis_sp_level]
    ...    kernel_release=${identite}[kernel_release]    kernel_patch_level=${identite}[kernel_patch_level]
    ...    server_name=${identite}[server_name]    product_version_text=${identite}[product_version_text]
    ...    database_system=${identite}[database_system]
    RETURN    ${cible}

Le Systeme Lu Devrait Etre Celui De La Session
    [Documentation]    Échoue si le SID lu dans « System: Status » n'est pas
    ...                celui de la session SAP active et connectée
    ...                (`List Sap Sessions`), ou si aucune session ne l'est.
    [Arguments]    ${identite}
    ${sessions}=    List Sap Sessions
    ${actives}=    Evaluate    [s for s in $sessions if s.get('active') and s.get('connected')]
    Length Should Be    ${actives}    1
    ...    msg=Aucune session SAP active et connectée pour nommer la cible (sessions : ${sessions}).
    Should Be Equal    ${identite}[system_id]    ${actives}[0][system]
    ...    msg=Le statut système lit le SID '${identite}[system_id]' mais la session active porte '${actives}[0][system]'.

Identite Du Systeme
    [Documentation]    `Get System Identity`, relu à l'écran (statut, kernel,
    ...                composants), pour le scénario qui l'exerce.
    ${identite}=    Get System Identity
    RETURN    ${identite}

L Identite Devrait Prouver La Release
    [Documentation]    Échoue si l'identité ne porte pas une release SAP_BASIS
    ...                (trois caractères, celle de la ligne ``SAP_BASIS`` de
    ...                « Installed Software ») ET une release de kernel, ou si
    ...                une section n'a pas pu être lue (``unread`` non vide) :
    ...                un SID partagé par deux systèmes ne prouve rien.
    [Arguments]    ${identite}
    Length Should Be    ${identite}[basis_release]    3
    ...    msg=Release SAP_BASIS illisible ('${identite}[basis_release]') : ${identite}[unread]
    Should Not Be Empty    ${identite}[kernel_release]
    ...    msg=Release du kernel illisible : ${identite}[unread]
    Should Be Empty    ${identite}[unread]
    ...    msg=Sections du statut système non lues : ${identite}[unread]

Clore La Campagne De Reconnaissance
    [Documentation]    Suite Teardown : écrit le registre PUIS ferme la session,
    ...                les deux même si l'un échoue (sémantique de teardown Robot).
    Ecrire Le Registre Des Capacites    ${REGISTER_PATH}
    Close SAP

Revenir Au Menu
    [Documentation]    Test Teardown : referme jusqu'à deux popups, puis revient
    ...                au menu SAP Easy Access par l'OK-code `/n`.
    Cancel Popup
    Cancel Popup
    Run Transaction    /n
    Wait Until Busy Done

Ouvrir L Accueil
    [Documentation]    Revient à l'accueil SAP Easy Access et attend que l'arbre du
    ...                menu utilisateur soit rendu. Relevé live : `/n` depuis une
    ...                transaction rend l'accueil, mais `/n` depuis l'accueil
    ...                LUI-MÊME laisse l'écran vide ``SAPMSYST/S000/40`` (aucun
    ...                arbre) ; de là, `Run Transaction SESSION_MANAGER` rouvre
    ...                l'accueil sans modal. Le tcode n'est lancé que si l'arbre
    ...                manque (le lancer DEPUIS l'accueil ouvre le modal « Cannot
    ...                start transaction », piège documenté).
    Revenir Au Menu
    ${present}=    Run Keyword And Return Status    Element Should Be Present    ${SM_USER_MENU_TREE}
    IF    not ${present}
        Run Transaction    SESSION_MANAGER
        Wait Until Busy Done
    END
    Wait Until Element Present    ${SM_USER_MENU_TREE}

# ---------------------------------------------------------------------------
# Assertions de forme propres à cette campagne (le registre lui-même vit
# dans capability_register.resource, partagé avec la campagne 758)
# ---------------------------------------------------------------------------

Les Noeuds Devraient Porter Cle Et Texte
    [Documentation]    Échoue si la liste de nœuds (`Read Tree Nodes`) est vide ou
    ...                si un nœud n'a pas de clé, ou si AUCUN nœud n'a de texte.
    [Arguments]    ${noeuds}
    Should Not Be Empty    ${noeuds}
    FOR    ${noeud}    IN    @{noeuds}
        Should Not Be Empty    ${noeud}[key]
    END
    ${textes}=    Evaluate    [n['text'] for n in $noeuds if n['text']]
    Should Not Be Empty    ${textes}    msg=Aucun nœud ne porte de texte.

L Entree De Cle Devrait Figurer
    [Documentation]    Échoue si aucune entrée de la liste (`Get Combo Box
    ...                Entries`) ne porte la clé donnée.
    [Arguments]    ${entrees}    ${cle}
    ${cles}=    Evaluate    [e['key'] for e in $entrees]
    List Should Contain Value    ${cles}    ${cle}

Les Formats Devraient Etre Des Cles
    [Documentation]    Échoue si les formats (`Get User Formats`) ne sont pas des
    ...                CLÉS techniques : DATFM grégorien (1 à 6), DCPFM vide/X/Y.
    [Arguments]    ${formats}
    Should Be True    $formats['date_format'] in ('1', '2', '3', '4', '5', '6')
    Should Be True    $formats['gregorian']
    Should Be True    $formats['decimal_notation'] in ('', 'X', 'Y')
    Should Not Be Empty    ${formats}[date_pattern]

Ligne De Signature Du Menu Utilisateur
    [Documentation]    La ligne de `Get Screen Signature` portant l'id de l'arbre du
    ...                menu utilisateur (accueil SAP Easy Access). Échoue si aucune
    ...                ligne ne le porte.
    ${signature}=    Get Screen Signature
    ${ligne}=    Get Lines Containing String    ${signature}    ${SM_USER_MENU_TREE}\t
    Should Not Be Empty    ${ligne}
    ...    msg=La signature de l'accueil ne porte pas l'arbre du menu utilisateur.
    RETURN    ${ligne}

Colonnes De La Ligne De Signature
    [Documentation]    Les colonnes (tabulations) d'une ligne de signature, marque
    ...                d'éditabilité retirée du premier élément : ``[id, type, texte,
    ...                ...]``.
    [Arguments]    ${ligne}
    @{colonnes}=    Split String    ${ligne}    \t
    ${id}=    Strip String    ${colonnes}[0]    characters=*${SPACE}
    Set List Value    ${colonnes}    0    ${id}
    RETURN    ${colonnes}

La Signature Affiche Le Sous Type
    [Documentation]    Vrai quand la ligne de signature de l'arbre porte le
    ...                sous-type en colonne type (``GuiShell/Tree``), trois colonnes.
    [Arguments]    ${colonnes}
    ${affiche}=    Run Keyword And Return Status    Run Keywords
    ...    Length Should Be    ${colonnes}    3
    ...    AND    Should Be Equal    ${colonnes}[1]    GuiShell/Tree
    RETURN    ${affiche}

Lire La Valeur Du Menu Utilisateur
    [Documentation]    `Get Value` sur le contrôle-arbre du menu utilisateur.
    ${valeur}=    Get Value    ${SM_USER_MENU_TREE}
    RETURN    ${valeur}

Lire Les Noeuds Du Menu Utilisateur
    [Documentation]    `Read Tree Nodes` sur l'arbre du menu utilisateur (liste de
    ...                dicts ``{key, text, level, folder, children, columns}``).
    ${noeuds}=    Read Tree Nodes    ${SM_USER_MENU_TREE}
    RETURN    ${noeuds}

Selectionner Le Dossier Plain ABAP Par Texte
    [Documentation]    `Select Tree Node By Text` sur le texte du dossier « Plain
    ...                ABAP » ; retourne la clé sélectionnée.
    ${cle}=    Select Tree Node By Text    ${SM_USER_MENU_TREE}    ${SM_TREE_PLAIN_ABAP_TEXT}    exact=True
    RETURN    ${cle}

Noeud Selectionne Du Menu Utilisateur
    [Documentation]    `Get Selected Tree Node` sur l'arbre du menu utilisateur.
    ${cle}=    Get Selected Tree Node    ${SM_USER_MENU_TREE}
    RETURN    ${cle}

Ouvrir Le Statut Systeme Par Chemin
    [Documentation]    `Select Menu Item` par le CHEMIN de textes du page object
    ...                (« System > Status ») ; attend le modal ; retourne l'id
    ...                sélectionné (à comparer à la position relevée).
    ${id}=    Select Menu Item    ${SM_MENU_SYSTEM_STATUS_PATH}
    Wait Until Element Present    wnd[1]
    RETURN    ${id}

Lire La Transaction Du Statut Systeme
    [Documentation]    Lit le champ « Transaction » du modal « System: Status » par
    ...                son libellé.
    ${tcode}=    Read Field By Label    ${SM_STATUS_TRANSACTION_LABEL}
    RETURN    ${tcode}

Fermer Le Statut Systeme
    [Documentation]    Referme le modal « System: Status » par F12 sur la fenêtre 1.
    Send Vkey    12    window=1
    Wait Until Busy Done

# ---------------------------------------------------------------------------
# SU01 en affichage
# ---------------------------------------------------------------------------

Afficher L Utilisateur
    [Documentation]    SU01, utilisateur ``${user}``, F7 (affichage) ; attend le
    ...                tabstrip de la fiche utilisateur.
    [Arguments]    ${user}
    Go To Transaction    SU01
    Input Text    ${SU01_USER_FIELD}    ${user}
    Send Vkey    7
    Wait Until Busy Done
    Wait Until Element Present    ${SU01_TABSTRIP}

Ouvrir L Onglet
    [Documentation]    Active un onglet de la fiche utilisateur : ``Logon Data``,
    ...                ``Defaults`` ou ``Parameters`` (carte `&{SU01_TABS}`).
    [Arguments]    ${onglet}
    ${tab}=    Get From Dictionary    ${SU01_TABS}    ${onglet}
    Click Element    ${tab}
    Wait Until Busy Done

Tenter De Changer Le Type D Utilisateur
    [Documentation]    `Select From List By Label` sur la combo « User Type » en
    ...                mode affichage (entrée « System »).
    Select From List By Label    ${SU01_USER_TYPE_COMBO}    ${SU01_USER_TYPE_SYSTEM_LABEL}

Lire La Cle Du Type D Utilisateur
    [Documentation]    `Get Combo Box Key` sur la combo « User Type » : la CLÉ
    ...                technique (``A`` = Dialog), locale-safe.
    ${cle}=    Get Combo Box Key    ${SU01_USER_TYPE_COMBO}
    RETURN    ${cle}

Lire Les Entrees Du Type D Utilisateur
    [Documentation]    `Get Combo Box Entries` sur la combo « User Type ».
    ${entrees}=    Get Combo Box Entries    ${SU01_USER_TYPE_COMBO}
    RETURN    ${entrees}

Lire Les Parametres De L Utilisateur
    [Documentation]    Onglet Parameters : `Read Grid` sur la grille ALV du
    ...                sous-écran (liste de dicts par titre de colonne).
    [Arguments]    ${max_rows}=5
    ${lignes}=    Read Grid    ${SU01_PARAMETERS_GRID}    max_rows=${max_rows}
    RETURN    ${lignes}

Colonnes De La Grille Des Parametres
    [Documentation]    Ids TECHNIQUES des colonnes de la grille Parameters
    ...                (`Get Grid Column Ids`), l'ancre locale-safe du témoin.
    ${ids}=    Get Grid Column Ids    ${SU01_PARAMETERS_GRID}
    RETURN    ${ids}

# ---------------------------------------------------------------------------
# SM37, Simple Job Selection (écran de sélection JAMAIS exécuté)
# ---------------------------------------------------------------------------

Ouvrir La Selection Simple Des Jobs
    [Documentation]    SM37 ; attend le champ date « From ».
    Go To Transaction    SM37
    Wait Until Element Present    ${SM37_FROM_DATE}

Lire La Date De Debut
    [Documentation]    Valeur courante du champ date « From » (id visé : le libellé
    ...                « From » est ambigu, date ET heure).
    ${date}=    Get Value    ${SM37_FROM_DATE}
    RETURN    ${date}

Saisir La Date De Debut
    [Documentation]    Saisit ``${date}`` dans le champ date « From », valide par
    ...                Entrée et retourne le TYPE du message de statut (``E`` = date
    ...                refusée, vide = acceptée).
    [Arguments]    ${date}
    Input Text    ${SM37_FROM_DATE}    ${date}
    Send Vkey    0
    Wait Until Busy Done
    ${type}    ${texte}=    Get Status Message
    Log    Statut après '${date}' : type='${type}' texte='${texte}'
    RETURN    ${type}

Restaurer La Date De Debut
    [Documentation]    Remet la date « From » à sa valeur ``${initiale}`` (relue en
    ...                début de scénario) et VÉRIFIE la restauration : aucun message
    ...                de type ``E`` et valeur relue égale à l'initiale. Une
    ...                restauration qui ne se relit pas n'est qu'une intention.
    [Arguments]    ${initiale}
    ${type}=    Saisir La Date De Debut    ${initiale}
    Should Be Equal    ${type}    ${EMPTY}
    ...    msg=La restauration de la date « From » à '${initiale}' a rendu un message de type '${type}'.
    ${relue}=    Lire La Date De Debut
    Should Be Equal    ${relue}    ${initiale}
    ...    msg=Date « From » relue '${relue}' après restauration, attendu '${initiale}'.

Restaurer La Date De Debut Si Relevee
    [Documentation]    Le teardown des scénarios qui touchent la date « From » :
    ...                restaure et VÉRIFIE la date initiale relevée par le test
    ...                dans ``${initiale}`` (variable de test), MÊME SUR ÉCHEC ;
    ...                ne fait rien si le test a échoué avant de la relever
    ...                (rien n'a alors été modifié).
    ${initiale}=    Get Variable Value    \${initiale}    ${None}
    IF    $initiale is not None
        Restaurer La Date De Debut    ${initiale}
    ELSE
        Log    Date « From » non relevée par le test : rien à restaurer.
    END

Forme Locale De La Date De Sonde
    [Documentation]    La forme LOCALE relevée de la date de sonde (``01.09.2026``
    ...                pour l'utilisateur DEVELOPER de ce trial, en ``DD.MM.YYYY``) :
    ...                la valeur MESURÉE à laquelle une conversion se confronte.
    RETURN    ${SM37_PROBE_DATE_LOCAL}

La Date Saisie Devrait Etre La Forme Locale
    [Documentation]    Échoue si ``${saisie}`` (la chaîne rendue par `Input Date` ou
    ...                par `Pick Calendar Date`) n'est pas la forme locale relevée.
    [Arguments]    ${saisie}
    Should Be Equal    ${saisie}    ${SM37_PROBE_DATE_LOCAL}
    ...    msg=La date saisie '${saisie}' n'est pas la forme locale relevée '${SM37_PROBE_DATE_LOCAL}' (format DATFM de l'utilisateur changé ?).

Tenter De Choisir Une Date Par L Aide F4
    [Documentation]    `Pick F4 Value` sur le champ date « From » (ouvre l'aide F4
    ...                lui-même : le calendrier doit être FERMÉ avant l'appel).
    [Arguments]    ${date}
    ${valeur}=    Pick F4 Value    ${SM37_FROM_DATE}    ${date}
    RETURN    ${valeur}

La Cle Initiale De L Evenement Devrait Etre Un Blanc
    [Documentation]    Échoue si la clé initiale relue de « Or after event » n'est
    ...                pas le BLANC relevé live (``" "``, distinct de la clé vide) :
    ...                c'est ce qui rend la restauration du scénario 6 vérifiable.
    [Arguments]    ${cle}
    Should Be Equal    ${cle}    ${SM37_EVENT_NONE_CODE}
    ...    msg=Clé initiale de l'événement '${cle}' (attendu : un blanc, la clé relevée live) : Get Combo Box Key normalise-t-il la clé, ou l'écran a-t-il changé ?

Choisir L Evenement Par Cle
    [Documentation]    `Select Combo Box Entry By Key` sur « Or after event » : la
    ...                voie locale-safe (``*`` = tout événement ; la clé initiale
    ...                est un BLANC, distinct de la clé vide : relevé live).
    [Arguments]    ${cle}
    Select Combo Box Entry By Key    ${SM37_EVENT_COMBO}    ${cle}

Lire La Cle De L Evenement
    [Documentation]    `Get Combo Box Key` sur « Or after event » (clé technique).
    ${cle}=    Get Combo Box Key    ${SM37_EVENT_COMBO}
    RETURN    ${cle}

Saisir La Date De Debut En ISO
    [Documentation]    `Input Date` (ISO -> format de l'utilisateur mémorisé par
    ...                `Get User Formats`) dans « From », Entrée, puis le TYPE du
    ...                message. Retourne la chaîne saisie ET le type.
    [Arguments]    ${iso}
    ${saisie}=    Input Date    ${SM37_FROM_DATE}    ${iso}
    Send Vkey    0
    Wait Until Busy Done
    ${type}    ${texte}=    Get Status Message
    RETURN    ${saisie}    ${type}

Choisir La Date De Debut Au Calendrier
    [Documentation]    `Pick Calendar Date` sur « From » (date ISO) : F4, jour
    ...                sélectionné, popup refermé ; retourne la valeur du champ.
    [Arguments]    ${iso}
    ${valeur}=    Pick Calendar Date    ${SM37_FROM_DATE}    ${iso}
    RETURN    ${valeur}

Trouver La Case Planifie
    [Documentation]    `Find Element By Label` sur le texte propre de la case
    ...                « Sched. » (« Scheduled » à l'écran, abrégé).
    ${id}=    Find Element By Label    ${SM37_SCHEDULED_LABEL}
    RETURN    ${id}

Etat De La Case Planifie
    [Documentation]    L'état (``checked``/``unchecked``) de la case « Sched. »,
    ...                lu par son texte propre.
    ${id}=    Trouver La Case Planifie
    ${etat}=    Get Value    ${id}
    RETURN    ${etat}

Basculer La Case Planifie
    [Documentation]    Bascule la case « Sched. » vers l'état OPPOSÉ à
    ...                ``${initial}`` (``checked``/``unchecked``) par son texte
    ...                propre : `Unselect Checkbox By Label` si elle est cochée,
    ...                `Select Checkbox By Label` sinon. Cocher une case déjà
    ...                cochée ne mesurerait rien. Retourne l'id résolu ET l'état
    ...                attendu après bascule.
    [Arguments]    ${initial}
    IF    '${initial}' == 'checked'
        ${id}=    Unselect Checkbox By Label    ${SM37_SCHEDULED_LABEL}
        ${attendu}=    Set Variable    unchecked
    ELSE
        ${id}=    Select Checkbox By Label    ${SM37_SCHEDULED_LABEL}
        ${attendu}=    Set Variable    checked
    END
    RETURN    ${id}    ${attendu}

La Case Planifie Devrait Etre
    [Documentation]    `Checkbox By Label Should Be` sur « Sched. ».
    [Arguments]    ${attendu}
    Checkbox By Label Should Be    ${SM37_SCHEDULED_LABEL}    ${attendu}

Restaurer La Case Planifie
    [Documentation]    Remet la case « Sched. » dans l'état ``${initial}``
    ...                (``checked``/``unchecked``) par son texte propre.
    [Arguments]    ${initial}
    IF    '${initial}' == 'checked'
        Select Checkbox By Label    ${SM37_SCHEDULED_LABEL}
    ELSE
        Unselect Checkbox By Label    ${SM37_SCHEDULED_LABEL}
    END

# ---------------------------------------------------------------------------
# SE16 sur T000 en grille ALV
# ---------------------------------------------------------------------------

Afficher T000 En Grille
    [Documentation]    SE16 sur T000, exécution (F8), grille ALV attendue.
    Display Table Contents    ${SE16_PROBE_TABLE}

Mode De Sortie Du Data Browser
    [Documentation]    `Get Data Browser Output` : ``alv_grid`` / ``alv_list`` /
    ...                ``standard_list``, lu sans rien changer.
    ${mode}=    Get Data Browser Output
    RETURN    ${mode}

Afficher T000 En Liste Standard
    [Documentation]    Bascule la sortie SE16 en liste standard (`Use Standard
    ...                List In Data Browser`, réglage persistant par utilisateur :
    ...                à RESTAURER par `Restaurer La Grille ALV Du Data Browser`),
    ...                atteint l'écran de sélection de T000 et exécute (F8) : la
    ...                liste ABAP classique ``SAPMSSY0/120``.
    Use Standard List In Data Browser
    ${verdict}=    Reach Se16 Selection Screen    ${SE16_PROBE_TABLE}
    Should Be True    ${verdict}[reached]
    ...    msg=L'écran de sélection de ${SE16_PROBE_TABLE} n'est pas atteint : ${verdict}
    Send Vkey    8
    Wait Until Busy Done

Statut De Rendu De L Ecran
    [Documentation]    `Get List Rendering Status` sur l'écran courant.
    ${statut}=    Get List Rendering Status
    RETURN    ${statut}

Lire La Liste Standard
    [Documentation]    `Read Abap List` sur la liste SE16 standard affichée
    ...                (lignes de cellules texte).
    ${lignes}=    Read Abap List
    RETURN    ${lignes}

La Liste Devrait Porter Le Mandant De Reference
    [Documentation]    Échoue si aucune ligne de la liste lue ne commence par le
    ...                mandant de référence (``000``, présent dans T000 de tout
    ...                système ABAP) : l'ancre locale-safe d'une ligne de DONNÉES,
    ...                là où les en-têtes dépendent d'un réglage utilisateur
    ...                (noms ou libellés de champs).
    [Arguments]    ${lignes}
    ${trouvees}=    Evaluate    [r for r in $lignes if r and str(r[0]).strip() == $SE16_REFERENCE_CLIENT]
    Should Not Be Empty    ${trouvees}
    ...    msg=Aucune ligne de la liste ne commence par le mandant ${SE16_REFERENCE_CLIENT} (${lignes.__len__()} ligne(s) lue(s)).

Restaurer La Grille ALV Du Data Browser
    [Documentation]    Remet la sortie SE16 en grille ALV (`Use ALV Grid In Data
    ...                Browser`) et VÉRIFIE la restauration en relisant le mode :
    ...                une restauration qui ne se relit pas n'est qu'une intention.
    ...                À appeler en teardown du scénario qui a basculé la liste.
    Use ALV Grid In Data Browser
    ${mode}=    Get Data Browser Output
    Should Be Equal    ${mode}    alv_grid
    ...    msg=La sortie SE16 relue est '${mode}' après restauration, attendu 'alv_grid'.

Cliquer Un Bouton De Grille
    [Documentation]    `Click Toolbar Button` sur la grille de résultats.
    [Arguments]    ${id}
    Click Toolbar Button    ${SE16_GRID}    ${id}

Ouvrir Le Detail De La Premiere Ligne
    [Documentation]    `Double Click Grid Cell` sur la ligne 0, colonne MANDT de
    ...                la grille de résultats (ouvre le modal de détail SE16).
    Double Click Grid Cell    ${SE16_GRID}    ${SE16_GRID_FIRST_ROW}    ${SE16_GRID_FIRST_COLUMN}

Codes Du Menu Contextuel De La Grille
    [Documentation]    Les codes fonction du menu contextuel de la grille
    ...                (`List Grid Context Menu`), sans les séparateurs.
    ${items}=    List Grid Context Menu    ${SE16_GRID}
    ${codes}=    Evaluate    [i['code'] for i in $items if i['code']]
    RETURN    ${codes}

Ouvrir Le Filtre De La Grille
    [Documentation]    `Select Grid Context Menu Item` avec le code ``&FILTER`` :
    ...                ouvre le dialogue de filtre (modal).
    Select Grid Context Menu Item    ${SE16_GRID}    ${GRID_FILTER_MENU_CODE}
    Wait Until Element Present    wnd[1]

Boutons De La Barre De La Grille
    [Documentation]    `List Grid Toolbar Buttons` sur la grille de résultats
    ...                (vide sur SE16 : les fonctions vivent dans la barre
    ...                d'application).
    ${boutons}=    List Grid Toolbar Buttons    ${SE16_GRID}
    RETURN    ${boutons}

Trier La Grille Par Client
    [Documentation]    `Sort Grid By Column` sur MANDT : sur SE16, échoue en
    ...                nommant la barre d'application (aucune barre de grille, pas
    ...                de tri dans le menu contextuel).
    Sort Grid By Column    ${SE16_GRID}    ${SE16_GRID_FIRST_COLUMN}

Premiere Reference De La Carte
    [Documentation]    `Get Screen Map` sur l'écran courant ; retourne les colonnes
    ...                de la référence ``@1`` : ``[ref, libellé, id, type, valeur]``.
    ${carte}=    Get Screen Map
    ${ligne}=    Get Line    ${carte}    1
    @{colonnes}=    Split String    ${ligne}    \t
    Should Be Equal    ${colonnes}[0]    @1
    ...    msg=La carte numérotée ne commence pas par @1 (ligne : ${ligne}).
    RETURN    ${colonnes}

Entrees De Menu De La Carte
    [Documentation]    Le nombre de lignes de `Get Screen Map` dont le type est
    ...                ``GuiMenu`` (0 attendu depuis le lot de correction).
    ${carte}=    Get Screen Map
    ${lignes}=    Get Lines Containing String    ${carte}    \tGuiMenu
    ${nombre}=    Get Line Count    ${lignes}
    RETURN    ${nombre}

# ---------------------------------------------------------------------------
# SE38 en affichage
# ---------------------------------------------------------------------------

Afficher Le Programme
    [Documentation]    SE38, programme ``${nom}``, F7 (affichage) ; attend le
    ...                contrôle éditeur.
    [Arguments]    ${nom}
    Go To Transaction    SE38
    Input Text    ${SE38_PROGRAM_FIELD}    ${nom}
    Send Vkey    7
    Wait Until Busy Done
    Wait Until Element Present    ${SE38_EDITOR}

Lire Le Controle Editeur
    [Documentation]    `Get Value` sur le contrôle éditeur ABAP.
    ${valeur}=    Get Value    ${SE38_EDITOR}
    RETURN    ${valeur}

# ---------------------------------------------------------------------------
# SPRO, Reference IMG
# ---------------------------------------------------------------------------

Ouvrir L IMG De Reference
    [Documentation]    SPRO, bouton « SAP Reference IMG » par libellé ; attend
    ...                l'arbre à colonnes de l'IMG.
    Go To Transaction    SPRO
    Click Button By Label    ${SPRO_REFERENCE_IMG_LABEL}
    Wait Until Busy Done
    Wait Until Element Present    ${SPRO_IMG_TREE}

Lire Les Noeuds De L IMG
    [Documentation]    `Read Tree Nodes` sur l'arbre à colonnes de l'IMG (texte lu
    ...                dans la colonne TEXT, clés complétées à gauche telles quelles).
    ${noeuds}=    Read Tree Nodes    ${SPRO_IMG_TREE}
    RETURN    ${noeuds}
