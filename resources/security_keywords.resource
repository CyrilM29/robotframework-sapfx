*** Settings ***
Documentation       **EXEMPLE À PERSONNALISER** : ce fichier porte le vocabulaire
...                 métier du LABORATOIRE de ce dépôt (identifiants, chemins, noms
...                 de tables et de modules relevés live sur SES cibles). Beaucoup
...                 s'y réutilise tel quel sur un autre système (écrans et services
...                 standard), mais rien n'y fait autorité : à VÉRIFIER sur votre
...                 cible et à adapter à votre métier. Ce qui fait foi partout,
...                 c'est `src/`, les bibliothèques, qui portent les capacités :
...                 voir `resources/README.md`.
...
...                 Mots-clés métier de la **configuration de sécurité** d'un
...                 système ABAP, lus par le canal RFC. Cette resource est au
...                 vocabulaire de sécurité ce que `rfc_keywords.resource` est
...                 au canal : elle nomme les contrôles, les tables et les
...                 comptes, pour qu'aucune suite ne porte un nom de table SAP
...                 ni un nom de paramètre de profil (convention 1).
...
...                 **Deux partis pris, et ils décident de tout le reste.**
...
...                 1. Une campagne de sécurité ne juge PAS « ce système est-il
...                 durci ». Ce jugement dépend d'une politique d'entreprise,
...                 il est faux sur un bac à sable, et une suite qui rougit en
...                 permanence finit désactivée. Elle juge « la configuration
...                 a-t-elle bougé depuis la référence committée », qui a une
...                 réponse binaire, et elle RAPPORTE la posture pour le
...                 lecteur humain. Les seuls contrôles qui échouent vraiment
...                 sont ceux dont l'écart serait un incident quelle que soit
...                 la politique.
...                 2. Une mesure absente n'est jamais une valeur. Le module
...                 qui lit un paramètre de profil rend un code de retour non
...                 nul et une chaîne VIDE pour un nom qu'il ne connaît pas :
...                 sans garde, un contrôle écrit sur un nom mal orthographié
...                 est vert et affirme une absence de durcissement qu'il n'a
...                 jamais mesurée. D'où `Security Parameters Should Be Known`,
...                 posée en tête de campagne.
...
...                 LECTURE SEULE de bout en bout : aucun mot-clé d'ici n'écrit
...                 dans le système observé.

Library             SapApiLibrary
Library             Collections
Library             OperatingSystem
Library             sapfx_common.security_baseline
Library             sapfx_common.security_inventory
Resource            rfc_keywords.resource


*** Variables ***
# --- Les lots de LECTURE, par thème. Ce sont les noms de paramètres SAP, donc
# ils vivent ici et jamais dans une suite. Les ATTENTES, elles, sont propres à
# chaque cible et vivent dans sa suite : c'est ce qui permet à deux releases de
# partager ce vocabulaire sans partager leur baseline.
@{PARAMS_PASSWORD_POLICY}
...                             login/min_password_lng
...                             login/min_password_digits
...                             login/min_password_letters
...                             login/min_password_specials
...                             login/min_password_lowercase
...                             login/min_password_uppercase
...                             login/password_expiration_time
...                             login/password_hash_algorithm
...                             login/password_history_size
...                             login/min_password_diff
...                             login/password_compliance_to_current_policy
...                             login/password_downwards_compatibility
...                             login/password_max_idle_initial
...                             login/password_max_idle_productive

@{PARAMS_LOGON_PROTECTION}
...                             login/fails_to_session_end
...                             login/fails_to_user_lock
...                             login/failed_user_auto_unlock
...                             login/disable_multi_gui_login
...                             login/no_automatic_user_sapstar
...                             login/isolate_rfc_system_calls
...                             rdisp/gui_auto_logout

@{PARAMS_AUDIT}
...                             rsau/enable
...                             rsau/integrity
...                             rsau/selection_slots
...                             rsau/user_selection
...                             rec/client

@{PARAMS_GATEWAY}
...                             gw/acl_mode
...                             gw/reg_no_conn_info
...                             gw/rem_start
...                             gw/monitor
...                             gw/sec_info
...                             gw/reg_info

@{PARAMS_RFC_AND_AUTH}
...                             auth/rfc_authority_check
...                             auth/no_check_in_some_cases
...                             auth/object_disabling_active
...                             rfc/reject_expired_passwd
...                             rfc/callback_security_method

@{PARAMS_TRANSPORT_SECURITY}
...                             snc/enable
...                             system/secure_communication
...                             icf/set_HTTPonly_flag_on_cookies
...                             login/ticket_only_by_https
...                             http/security_session_timeout

# --- Les tables d'administration lues. Convention 1 : leurs noms vivent ICI.
${TABLE_CLIENTS}                T000
${TABLE_USER_PROFILES}          UST04
${TABLE_RFC_DESTINATIONS}       RFCDES
@{CRITICAL_PROFILES}            SAP_ALL    SAP_NEW
# Les types de destination qui peuvent porter un logon vers un système tiers :
# ABAP (3) et HTTP (H, G). Les autres (T, I, X, @) n'en portent pas.
@{LOGON_BEARING_TYPES}          3    H    G

# --- Où vivent les références de dérive (une par cible, committée).
${SECURITY_REFERENCE_DIR}       ${CURDIR}/../tests/robot/security_baselines


*** Keywords ***
Open Security Audit Channel
    [Documentation]    Ouvre le canal de lecture de la posture. Alias du canal
    ...    RFC : une campagne de sécurité n'a pas de canal à elle, elle emprunte
    ...    celui qui sait lire les paramètres et les tables d'administration.
    [Arguments]    ${alias}=${RFC_ALIAS}    ${ashost}=${RFC_ASHOST}
    ...    ${sysnr}=${RFC_SYSNR}    ${client}=${RFC_CLIENT}    ${user}=${RFC_USER}
    ...    ${password}=${RFC_PASSWORD}    ${lang}=${RFC_LANG}
    ${ouvert}=    Open Rfc Channel    alias=${alias}    ashost=${ashost}
    ...    sysnr=${sysnr}    client=${client}    user=${user}
    ...    password=${password}    lang=${lang}
    RETURN    ${ouvert}

Close Security Audit Channel
    [Documentation]    Referme le canal, TOUTES connexions comprises. Une
    ...    connexion RFC laissée ouverte est une session utilisateur ouverte
    ...    côté serveur : le teardown n'est pas une politesse. Sans argument, à
    ...    l'image du mot-clé de canal qu'il enveloppe.
    Close Rfc Channel

Read Security Parameters
    [Documentation]    Lit un lot de paramètres de profil et rend une fiche par
    ...    paramètre (``name``, ``status``, ``value``). ``status`` distingue
    ...    ``defined`` de ``unknown`` : c'est la garde contre la valeur vide que
    ...    le système rend pour un nom qu'il ne connaît pas.
    [Arguments]    ${parametres}    ${alias}=${RFC_ALIAS}
    ${mesures}=    Read Profile Parameters    ${parametres}    alias=${alias}
    RETURN    ${mesures}

Read Full Security Posture
    [Documentation]    Lit TOUS les thèmes en un mot-clé et rend le relevé
    ...    complet, dans un ordre stable. C'est ce relevé que la sentinelle
    ...    compare à la référence : le prendre en une fois garantit que deux
    ...    exécutions comparent le même périmètre.
    [Arguments]    ${alias}=${RFC_ALIAS}
    @{tous}=    Create List
    FOR    ${lot}    IN
    ...    ${PARAMS_PASSWORD_POLICY}    ${PARAMS_LOGON_PROTECTION}
    ...    ${PARAMS_AUDIT}    ${PARAMS_GATEWAY}
    ...    ${PARAMS_RFC_AND_AUTH}    ${PARAMS_TRANSPORT_SECURITY}
        ${mesures}=    Read Security Parameters    ${lot}    alias=${alias}
        Append To List    ${tous}    @{mesures}
    END
    RETURN    ${tous}

Current System Identity
    [Documentation]    L'identité de la cible, relevée UNE fois par suite puis
    ...    réutilisée. Mémoïsée à dessein : sans elle, chaque scénario qui a
    ...    besoin de l'identité dépendrait d'un `Set Suite Variable` posé par un
    ...    scénario précédent, donc aucun test ne pourrait être rejoué SEUL
    ...    (`--test`), ce qui est exactement ce qu'on demande à un test quand il
    ...    vient d'échouer.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${connue}=    Get Variable Value    ${SECURITY_SYSTEM_INFO}    ${None}
    IF    $connue is None
        ${connue}=    Read System Information    alias=${alias}
        Set Suite Variable    ${SECURITY_SYSTEM_INFO}    ${connue}
    END
    RETURN    ${connue}

Current Security Posture
    [Documentation]    Le relevé complet de la posture, lu UNE fois par suite
    ...    puis réutilisé. Même raison que `Current System Identity`, plus une
    ...    seconde : le relevé est une trentaine d'allers-retours RFC, et deux
    ...    scénarios qui le reliraient séparément pourraient le lire
    ...    DIFFÉREMMENT si la configuration bougeait entre les deux, ce qui
    ...    rendrait la comparaison à la référence incohérente avec ce que la
    ...    suite a rapporté juste avant.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${connue}=    Get Variable Value    ${SECURITY_POSTURE}    ${None}
    IF    $connue is None
        ${connue}=    Read Full Security Posture    alias=${alias}
        Set Suite Variable    ${SECURITY_POSTURE}    ${connue}
    END
    RETURN    ${connue}

Security Parameters Should Be Known
    [Documentation]    Vérifie que le système reconnaît tous les paramètres du
    ...    lot. À poser AVANT tout jugement de conformité : elle sépare « le
    ...    système n'est pas durci » de « mon contrôle vise un paramètre qui
    ...    n'existe pas sur cette release », deux constats qui se ressemblent
    ...    dans un rapport et ne se corrigent pas au même endroit.
    [Arguments]    ${parametres}    ${alias}=${RFC_ALIAS}
    ${mesures}=    Profile Parameters Should Be Defined    ${parametres}    alias=${alias}
    RETURN    ${mesures}

Security Control
    [Documentation]    Déclare UN contrôle : sa clé, le paramètre mesuré, le
    ...    comparateur (``equals``, ``at_least``, ``at_most``, ``one_of``,
    ...    ``enabled``, ``disabled``), l'attendu, la sévérité et la raison
    ...    d'être. La raison n'est pas décorative : c'est elle que lit celui qui
    ...    découvre l'écart dans le rapport.
    [Arguments]    ${key}    ${parameter}    ${comparison}    ${expected}
    ...    ${severity}=medium    ${rationale}=${EMPTY}
    ${controle}=    Create Dictionary    key=${key}    parameter=${parameter}
    ...    comparison=${comparison}    expected=${expected}
    ...    severity=${severity}    rationale=${rationale}
    RETURN    ${controle}

Judge Security Posture
    [Documentation]    Confronte les contrôles déclarés aux mesures et rend un
    ...    verdict par contrôle. Trois verdicts, jamais deux : ``compliant``,
    ...    ``deviation``, et ``not_measurable`` pour le paramètre que le système
    ...    ne reconnaît pas, qui n'est PAS une non-conformité et n'est jamais
    ...    compté comme un succès.
    [Arguments]    ${controles}    ${mesures}
    ${verdicts}=    Evaluate Controls    ${controles}    ${mesures}
    RETURN    ${verdicts}

Log Security Posture Report
    [Documentation]    Journalise le rapport Markdown de la posture et rend
    ...    l'artefact. Le rapport nomme les non-mesurables AVANT les écarts :
    ...    lire une liste d'écarts sans savoir combien de contrôles sont restés
    ...    muets donne l'illusion d'un système presque conforme.
    [Arguments]    ${identite}    ${mesures}    ${controles}    ${observations}=${None}
    ${artefact}=    Build Security Posture    ${identite}    ${mesures}
    ...    ${controles}    observations=${observations}
    ${rapport}=    Render Posture Report    ${artefact}
    Log    ${rapport}    formatter=str
    RETURN    ${artefact}

Security Posture Should Match Reference
    [Documentation]    Compare la posture mesurée à la référence committée de
    ...    LA cible. Premier passage : la référence est écrite avec un WARNING
    ...    et l'appel réussit (elle est à relire et à committer). Ensuite,
    ...    chaque écart est nommé.
    ...
    ...    ``fail_on_drift=False`` transforme la sentinelle en simple rapport,
    ...    utile pour un premier balayage d'un système qu'on ne maîtrise pas.
    [Arguments]    ${nom_reference}    ${mesures}    ${identite}=${None}
    ...    ${fail_on_drift}=${True}
    ${chemin}=    Set Variable    ${SECURITY_REFERENCE_DIR}/${nom_reference}.json
    ${verdict}=    Security Posture Should Not Have Drifted    ${chemin}
    ...    ${mesures}    identity=${identite}    fail_on_drift=${fail_on_drift}
    RETURN    ${verdict}

Read Standard Accounts
    [Documentation]    L'état des comptes livrés par SAP dans le mandant de
    ...    connexion : présence, verrouillage et sa CAUSE, type, groupe,
    ...    dernière connexion. Un compte absent est rendu avec
    ...    ``present=False`` plutôt qu'omis, parce que « ce compte n'existe pas
    ...    ici » est une réponse au contrôle, pas une absence de mesure.
    [Arguments]    ${alias}=${RFC_ALIAS}    ${comptes}=${None}    ${mandant}=${RFC_CLIENT}
    ${fiches}=    Read Standard Users Status    alias=${alias}    users=${comptes}
    ...    client=${mandant}
    RETURN    ${fiches}

Read Client Protection
    [Documentation]    Les mandants du système et leurs verrous : catégorie,
    ...    protection contre la copie et l'écrasement, protection contre les
    ...    modifications inter-mandants.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${lignes}=    Read Rfc Table    ${TABLE_CLIENTS}
    ...    MANDT,MTEXT,CCCATEGORY,CCCOPYLOCK,CCNOCLIIND,CCCORACTIV    alias=${alias}
    RETURN    ${lignes}

Read Critical Profile Assignments
    [Documentation]    Qui porte un profil d'autorisation critique dans le
    ...    mandant de connexion. Le contrôle d'audit le plus regardé d'un
    ...    système SAP, et celui qui se dégrade le plus vite.
    [Arguments]    ${alias}=${RFC_ALIAS}    ${profils}=${CRITICAL_PROFILES}
    ${liste}=    Catenate    SEPARATOR=,    @{profils}
    ${cite}=    Set Variable    '${liste.replace(',', "','")}'
    ${lignes}=    Read Rfc Table    ${TABLE_USER_PROFILES}    BNAME,PROFILE
    ...    alias=${alias}    options=PROFILE IN (${cite})
    RETURN    ${lignes}

Read Rfc Destinations
    [Documentation]    L'inventaire des destinations RFC déclarées, avec leur
    ...    type. Une destination de type 3 qui stocke un logon est un chemin
    ...    d'élévation classique entre systèmes : la campagne l'INVENTORIE, et
    ...    ne lit jamais son secret.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${lignes}=    Read Rfc Table    ${TABLE_RFC_DESTINATIONS}    RFCDEST,RFCTYPE
    ...    alias=${alias}
    RETURN    ${lignes}

Read Destinations Carrying A Logon
    [Documentation]    Les destinations qui CONSERVENT un logon vers un autre
    ...    système, classées : la lecture d'audit que la simple liste des
    ...    destinations ne donne pas, l'information n'étant pas dans une
    ...    colonne mais dans un agrégat de marqueurs. Ne lit jamais un secret,
    ...    constate seulement qu'il en existe un.
    [Arguments]    ${alias}=${RFC_ALIAS}    ${types}=${LOGON_BEARING_TYPES}
    ${fiches}=    Read Rfc Destination Inventory    alias=${alias}    types=${types}
    ${resume}=    Summarize Destinations    ${fiches}
    RETURN    ${resume}

Read Audit Filtering
    [Documentation]    L'état RÉEL du journal d'audit : armé ou non, et surtout
    ...    s'il FILTRE quelque chose. Le paramètre `rsau/enable` ne répond qu'à
    ...    la première question, et une campagne qui s'y arrête conclut « audit
    ...    actif » sur un journal qui n'enregistre rien.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${config}=    Get Audit Configuration    alias=${alias}
    RETURN    ${config}

Read Installed Components
    [Documentation]    Les composants logiciels installés et leur niveau de
    ...    correctifs : l'ancre d'identité de la cible, et la base d'un
    ...    contrôle « ce système a-t-il reculé de niveau ».
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${composants}=    Read Software Components    alias=${alias}
    RETURN    ${composants}

Count Destinations Of Type
    [Documentation]    Compte les destinations d'un type donné dans un
    ...    inventaire déjà lu, sans relire le système.
    [Arguments]    ${destinations}    ${type}
    ${compte}=    Set Variable    ${0}
    FOR    ${ligne}    IN    @{destinations}
        IF    $ligne.get("RFCTYPE", "").strip() == $type
            ${compte}=    Evaluate    ${compte} + 1
        END
    END
    RETURN    ${compte}
