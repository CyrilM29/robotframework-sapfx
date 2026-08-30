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
...                 Page object de la **zone utilisateur et des paramètres du
...                 shell d'un launchpad SAP Build Work Zone** (cFLP sur BTP) :
...                 menu utilisateur, dialogue « à propos », dialogue des
...                 paramètres et ses rubriques, Theme Manager. Le shell
...                 lui-même (session, catalogue, iframes) vit dans
...                 `workzone_launchpad.resource`, que ce fichier importe.
...
...                 Relevé live le 2026-08-26 (rf-mcp : Browser +
...                 SapFioriLibrary) sur un site Work Zone de trial BTP,
...                 runtime SAPUI5 1.151.0. Spec source :
...                 `specs/workzone-zone-utilisateur-parametres.md`.
...
...                 Contrat de localisation, appris sur la cible réelle :
...
...                 1. **La zone utilisateur est un Web Component** (hôte
...                 `ui5-avatar`, wrapper UI5 `…webcomponents.dist.Avatar`) et
...                 son menu un `ui5-user-menu`, pas un `sap.m.Popover`. Le
...                 témoin d'ouverture est la propriété `open` du menu : ses
...                 entrées restent RENDUES menu fermé, et sur une session
...                 neuve ni le menu ni ses entrées n'existent avant le
...                 premier clic sur l'avatar.
...                 2. **L'index d'une entrée du menu n'est pas une ancre**
...                 (`-4-aboutBtn` à l'accueil, `-3-aboutBtn` en application) :
...                 seul le suffixe d'action est stable.
...                 3. **Les fermetures de dialogues sont animées** : juste
...                 après le clic de fermeture, `Get Ui5 Open Popups` liste
...                 encore le dialogue. Toute constatation de fermeture ATTEND
...                 la disparition, jamais de lecture immédiate.
...                 4. **Aucun identifiant généré en dur** : rubriques de
...                 paramètres et rubriques « à propos » sont adressées par
...                 leur clé de contexte de liaison ou leur position dans une
...                 liste dont la structure est vérifiée, l'accès au Theme
...                 Manager par le couple type plus icône.
...
...                 Portée : LECTURE SEULE. Aucun mot-clé de ce fichier
...                 n'actionne un bouton d'enregistrement ni la
...                 réinitialisation des personnalisations.

Resource            workzone_launchpad.resource


*** Variables ***
# --- Zone utilisateur : ancres stables relevées live (2026-08-26) ------------
${WORKZONE_USER_AVATAR}             userActionsMenuHeaderButton    # idSuffix : le préfixe de composant est généré
${WORKZONE_USER_MENU}               sapUshellUserActionsMenuPopover    # le ui5-user-menu ; propriété `open` = témoin d'ouverture
${WORKZONE_USER_MENU_ITEM_TYPE}     UserMenuItem    # type court du wrapper UI5 des entrées du menu
${WORKZONE_AVATAR_TYPE_SUFFIX}      .Avatar    # fin attendue du type de la zone utilisateur
${WORKZONE_WC_TYPE_MARKER}          webcomponents    # marqueur de la distribution Web Components dans un nom de type
${WORKZONE_AVATAR_CONFIG_PATH}      ushell.userActionsMenu.displayAvatar    # la clé de configuration qui déclare l'avatar

# --- Entrées du menu : le SUFFIXE d'action est l'ancre, jamais l'index -------
${WORKZONE_SETTINGS_ENTRY}          userSettingsBtn
${WORKZONE_APP_FINDER_ENTRY}        openCatalogBtn
${WORKZONE_EDIT_ENTRY}              ActionModeBtn    # présente à l'accueil seulement
${WORKZONE_MANAGE_SITE_ENTRY}       manageSiteBtn    # propre au cFLP, jamais actionnée par cette couche
${WORKZONE_ABOUT_ENTRY}             aboutBtn
@{WORKZONE_PERMANENT_ENTRIES}       ${WORKZONE_SETTINGS_ENTRY}    ${WORKZONE_APP_FINDER_ENTRY}
...                                 ${WORKZONE_MANAGE_SITE_ENTRY}    ${WORKZONE_ABOUT_ENTRY}

# --- Dialogue des paramètres -------------------------------------------------
${WORKZONE_SETTINGS_DIALOG}         settingsView--userSettingsDialog
${WORKZONE_SETTINGS_SAVE}           settingsView--userSettingSaveButton    # rendu dans la barre de pied, JAMAIS cliqué
${WORKZONE_SETTINGS_CANCEL}         settingsView--userSettingCancelButton
${WORKZONE_SETTINGS_ENTRY_LIST}     settingsView--userSettingEntryList
@{WORKZONE_SETTINGS_BASE_KEYS}      userAccountEntry    themes    language    homepageEntry
${WORKZONE_APPEARANCE_SECTION}          themes
${WORKZONE_LANGUAGE_SECTION}            language
${WORKZONE_THEME_LIST}              userPrefThemeSelector--themeList

# --- Dialogue « à propos » ---------------------------------------------------
${WORKZONE_ABOUT_DIALOG}            aboutDialogFragment--aboutDialog
${WORKZONE_ABOUT_CLOSE}             aboutDialogFragment--aboutDialogCloseButton    # id STABLE : pas d'acquittement par position ici
${WORKZONE_ABOUT_ENTRY_LIST}        aboutDialogFragment--aboutDialogEntryList
${WORKZONE_ABOUT_ITEM_TYPE}         StandardListItem
${WORKZONE_ABOUT_TEXT_TYPE}         sap.m.Text
# Pages de détail par position de rubrique : ids relevés live (le nom réel est
# `DetailApplication`, pas `DetailApp` : vérifié après une première déduction fausse).
@{WORKZONE_ABOUT_DETAIL_PAGES}      aboutDialogFragment--aboutDialogDetailApplication
...                                 aboutDialogFragment--aboutDialogDetailSystem
...                                 aboutDialogFragment--aboutDialogDetailEnvironment
${WORKZONE_ABOUT_COMPONENT}         CA-FLP-FE-COR    # composant applicatif du launchpad SAP, identique à l'ushell ABAP 1.120

# --- Theme Manager : surface d'administration, ouverte mais jamais actionnée -
${WORKZONE_THEME_MANAGER_TYPE}      ShellBarItem    # l'id de l'élément de barre est GÉNÉRÉ : l'ancre est type + icône
${WORKZONE_THEME_MANAGER_ICON}      {'icon': 'palette'}
${WORKZONE_THEME_MANAGER_DIALOG}    themeDesignDialog
${WORKZONE_THEME_MANAGER_CANCEL}    cancelButton    # id complet relevé tel quel (sans préfixe de vue)
${WORKZONE_THEME_MANAGER_SAVE}      saveButton
${WORKZONE_THEME_MANAGER_TOGGLE}    userSelectionButton

# --- Budgets d'attente -------------------------------------------------------
${WORKZONE_POPUP_TIMEOUT}           30s    # ouverture des dialogues : la vue des paramètres se charge en asynchrone
${WORKZONE_POPUP_RETRY}             0.5s

# --- Perception par la bibliothèque (convention #12) -------------------------
# Les sondes JS inline qui vivaient ici (identité ushell, type de contrôle,
# clés de rubriques au contexte de liaison, thèmes, réglage de langue,
# rubriques « à propos ») sont devenues des keywords de SapFioriLibrary :
# `Get Flp User`, `Get Ui5 Control Info`, `Get Ui5 Aggregation Info` (qui voit
# aussi les items NON rendus, ceux d'un Select popover fermé) et
# `Get Page Languages`. Ce fichier ne garde que les ANCRES du site.
# Rubrique « Language and Region » : sélecteur de langue et fuseau horaire
# (suffixes d'identifiants stables de la vue des paramètres).
${WORKZONE_LANGUAGE_SELECT}         userLanguageAndRegion--languageSelectionSelect
${WORKZONE_TIMEZONE_TEXT}           userLanguageAndRegion--selectedTimeZone


*** Keywords ***
# --- Suite Setup / Teardown de la campagne -----------------------------------

Preparer La Campagne Zone Utilisateur
    [Documentation]    Suite Setup : ouvre la session Work Zone (page object du
    ...    shell) puis mémorise l'état initial du compte, la référence du
    ...    dernier test et du teardown.
    Ouvrir La Session Work Zone
    Memoriser L Etat Initial Du Compte

Clore La Campagne Zone Utilisateur
    [Documentation]    Suite Teardown : referme tout popup restant (best
    ...    effort) puis ferme la session. S'exécute MÊME sur échec, c'est ce
    ...    qui autorise à rejouer la campagne sur un site partagé.
    Run Keyword And Ignore Error    Fermer Tout Popup Restant
    Fermer La Session Work Zone

# --- Identité et état du compte ----------------------------------------------

Lire L Identite De Session
    [Documentation]    Identité du compte au conteneur ushell : identifiant (un
    ...    GUID, jamais un nom de connexion), langue et thème, trois valeurs
    ...    techniques locale-indépendantes.
    ${brut}=    Get Flp User
    ${identite}=    Create Dictionary    id=${brut}[id]
    ...    langue=${brut}[language]    theme=${brut}[theme]
    RETURN    ${identite}

Lire Le Theme Du Compte
    [Documentation]    Le thème du compte sous sa forme technique
    ...    (`sap_horizon`), la valeur qui recoupe la rubrique « Environment »
    ...    du dialogue « à propos » et la sélection de la rubrique d'apparence.
    ${identite}=    Lire L Identite De Session
    RETURN    ${identite}[theme]

Memoriser L Etat Initial Du Compte
    [Documentation]    Relève thème et langue du compte et les publie en
    ...    variable de suite `${WORKZONE_ETAT_INITIAL}` : la référence que le
    ...    dernier test compare pour prouver que le parcours n'a rien écrit.
    ${identite}=    Lire L Identite De Session
    Set Suite Variable    ${WORKZONE_ETAT_INITIAL}    ${identite}
    Log    État initial du compte : thème ${identite}[theme], langue ${identite}[langue].

L Etat Du Compte Est Inchange
    [Documentation]    Compare thème et langue du compte à l'état mémorisé par
    ...    le Suite Setup. C'est la propriété « lecture seule » de toute la
    ...    campagne, vérifiée et pas seulement promise.
    ${identite}=    Lire L Identite De Session
    Should Be Equal    ${identite}[theme]    ${WORKZONE_ETAT_INITIAL}[theme]
    ...    msg=Le thème du compte a changé pendant la campagne (${WORKZONE_ETAT_INITIAL}[theme] au départ, ${identite}[theme] maintenant).
    Should Be Equal    ${identite}[langue]    ${WORKZONE_ETAT_INITIAL}[langue]
    ...    msg=La langue du compte a changé pendant la campagne (${WORKZONE_ETAT_INITIAL}[langue] au départ, ${identite}[langue] maintenant).

# --- Zone utilisateur : avatar et menu ---------------------------------------

La Zone Utilisateur Est Visible
    [Documentation]    L'avatar de la zone utilisateur est rendu ET occupe un
    ...    rectangle non nul (l'échec distingue « aucune correspondance » de
    ...    « rendu mais 0x0 » en nommant les ids).
    Ui5 Control Should Be Visible    idSuffix=${WORKZONE_USER_AVATAR}

Lire Le Type De La Zone Utilisateur
    [Documentation]    Type de contrôle de la zone utilisateur, lu au registre.
    ...    Relevé live : `sap.f.gen.ui5.webcomponents.dist.Avatar`, un Web
    ...    Component là où l'ushell ABAP 1.120 rend un `sap.m.Avatar` sous le
    ...    même identifiant.
    ${fiches}=    Get Ui5 Control Info    idSuffix=${WORKZONE_USER_AVATAR}
    Should Not Be Empty    ${fiches}
    ...    msg=La zone utilisateur (${WORKZONE_USER_AVATAR}) n'est pas rendue sur le shell.
    RETURN    ${fiches}[0][type]

La Configuration Declare L Avatar De La Zone Utilisateur
    [Documentation]    La configuration ushell déclare l'affichage de la zone
    ...    utilisateur en avatar : le rendu constaté n'est pas un accident.
    ${declare}=    Get Ushell Config    path=${WORKZONE_AVATAR_CONFIG_PATH}
    Should Be True    ${declare}
    ...    msg=La configuration du shell ne déclare pas l'avatar de la zone utilisateur (${WORKZONE_AVATAR_CONFIG_PATH}).

Ouvrir La Zone Utilisateur
    [Documentation]    Clique l'avatar puis attend que le menu soit réellement
    ...    OUVERT, constaté sur sa propriété `open` : ses entrées restent
    ...    rendues menu fermé, donc ni un comptage ni une résolution ne
    ...    suffisent. À appeler menu fermé (le clic est une bascule).
    Click Ui5 Control    idSuffix=${WORKZONE_USER_AVATAR}
    Wait Until Keyword Succeeds    ${WORKZONE_POPUP_TIMEOUT}    ${WORKZONE_POPUP_RETRY}
    ...    La Zone Utilisateur Est Ouverte

La Zone Utilisateur Est Ouverte
    [Documentation]    Prédicat d'ouverture : la propriété `open` du menu vaut
    ...    vrai. Sur une session neuve où le menu n'a jamais été ouvert, le
    ...    contrôle n'existe pas encore au registre et ce prédicat échoue en
    ...    nommant l'absence, ce qui est le comportement voulu.
    ${ouvert}=    Get Ui5 Property    open    idSuffix=${WORKZONE_USER_MENU}
    Should Be True    ${ouvert}
    ...    msg=Le menu de la zone utilisateur (${WORKZONE_USER_MENU}) n'est pas ouvert.

La Zone Utilisateur Est Fermee
    [Documentation]    Prédicat de fermeture : la propriété `open` du menu vaut
    ...    faux. Ne prouve rien sur le rendu : les entrées restent rendues.
    ${ouvert}=    Get Ui5 Property    open    idSuffix=${WORKZONE_USER_MENU}
    Should Not Be True    ${ouvert}
    ...    msg=Le menu de la zone utilisateur (${WORKZONE_USER_MENU}) est encore ouvert.

La Zone Utilisateur Apparait Dans Les Popups Ouverts
    [Documentation]    Le menu ouvert est vu par `Get Ui5 Open Popups` comme un
    ...    popover Web Components (`technology=wc`) : le témoin croisé de la
    ...    propriété `open`. Retourne l'entrée de popup correspondante.
    ${popups}=    Get Ui5 Open Popups
    ${popovers_wc}=    Evaluate
    ...    [p for p in $popups if p['kind'] == 'popover' and p['technology'] == 'wc']
    Should Not Be Empty    ${popovers_wc}
    ...    msg=Le menu de la zone utilisateur est ouvert (propriété `open`) mais aucun popover Web Components ne figure dans les popups ouverts : ${popups}
    RETURN    ${popovers_wc}[0]

Fermer La Zone Utilisateur Par Echappement
    [Documentation]    Referme le menu par la touche d'échappement et CONSTATE
    ...    la fermeture sur la propriété `open`.
    Keyboard Key    press    Escape
    Wait Until Keyword Succeeds    ${WORKZONE_POPUP_TIMEOUT}    ${WORKZONE_POPUP_RETRY}
    ...    La Zone Utilisateur Est Fermee

Fermer La Zone Utilisateur Par Bascule
    [Documentation]    Referme le menu en rappuyant sur l'avatar qui l'a
    ...    ouvert, et CONSTATE la fermeture sur la propriété `open`.
    Click Ui5 Control    idSuffix=${WORKZONE_USER_AVATAR}
    Wait Until Keyword Succeeds    ${WORKZONE_POPUP_TIMEOUT}    ${WORKZONE_POPUP_RETRY}
    ...    La Zone Utilisateur Est Fermee

Compter Les Entrees De La Zone Utilisateur
    [Documentation]    Nombre d'entrées du menu RENDUES au registre. Mesuré
    ...    live : 0 avant la première ouverture (le menu est construit au
    ...    premier clic), puis identique menu ouvert et menu refermé : ce
    ...    comptage ne prouve donc jamais l'ouverture.
    ${nb}=    Get Ui5 Match Count    controlType=${WORKZONE_USER_MENU_ITEM_TYPE}
    RETURN    ${nb}

Lire Les Identifiants Des Entrees De La Zone Utilisateur
    [Documentation]    Identifiants complets des entrées rendues du menu, pour
    ...    la trace des index : l'index y change avec l'endroit (accueil ou
    ...    application), c'est pourquoi il n'est jamais une ancre.
    ${ids}=    Get Ui5 Ids    controlType=${WORKZONE_USER_MENU_ITEM_TYPE}
    RETURN    ${ids}

Lire Les Suffixes D Action De La Zone Utilisateur
    [Documentation]    Suffixes d'action des entrées rendues du menu, triés
    ...    (`aboutBtn`, `manageSiteBtn`, ...) : la seule forme stable de leurs
    ...    identifiants `<popover>-<index>-<action>`.
    ${ids}=    Lire Les Identifiants Des Entrees De La Zone Utilisateur
    ${actions}=    Evaluate    sorted({i.rsplit('-', 1)[-1] for i in $ids})
    RETURN    ${actions}

Ouvrir L Entree De La Zone Utilisateur
    [Documentation]    Ouvre la zone utilisateur puis actionne l'une de ses
    ...    entrées, désignée par son suffixe d'action.
    [Arguments]    ${suffixe}
    Ouvrir La Zone Utilisateur
    Click Ui5 Control    idSuffix=${suffixe}

# --- Popups : constats et nettoyage ------------------------------------------

Aucun Popup N Est Ouvert
    [Documentation]    Prédicat : plus aucun popup OUVERT (dialogues UI5 et
    ...    popovers Web Components confondus). C'est la lecture qui tranche :
    ...    un dialogue fermé peut rester rendu, et il l'est parfois encore
    ...    pendant l'animation de fermeture.
    ${popups}=    Get Ui5 Open Popups
    Should Be Empty    ${popups}
    ...    msg=Des popups sont encore ouverts : ${popups}

Attendre Qu Aucun Popup Ne Soit Ouvert
    [Documentation]    Attend la fermeture réelle des popups. Nécessaire :
    ...    mesuré live, un dialogue reste listé « ouvert » quelques instants
    ...    après le clic de fermeture (animation), une lecture immédiate
    ...    échouerait sur un écran en train de se fermer proprement.
    [Arguments]    ${budget}=${WORKZONE_POPUP_TIMEOUT}
    Wait Until Keyword Succeeds    ${budget}    ${WORKZONE_POPUP_RETRY}
    ...    Aucun Popup N Est Ouvert

Fermer Tout Popup Restant
    [Documentation]    Teardown best-effort : referme par échappement les
    ...    popups qu'un échec aurait laissés ouverts, pour que le test suivant
    ...    ne paie pas l'état du précédent. Journalise ce qui résiste, ne fait
    ...    jamais échouer le teardown (la page peut être morte).
    ${etat}    ${popups}=    Run Keyword And Ignore Error    Get Ui5 Open Popups
    IF    '${etat}' == 'FAIL'    RETURN
    WHILE    len($popups) > 0    limit=5    on_limit=pass
        Keyboard Key    press    Escape
        ${referme}=    Run Keyword And Return Status
        ...    Attendre Qu Aucun Popup Ne Soit Ouvert    budget=10s
        IF    ${referme}    RETURN
        ${etat}    ${popups}=    Run Keyword And Ignore Error    Get Ui5 Open Popups
        IF    '${etat}' == 'FAIL'    RETURN
    END
    IF    len($popups) > 0
        Log    Des popups résistent au nettoyage par échappement : ${popups}    WARN
    END

Lire Le Dialogue Ouvert
    [Documentation]    Retourne l'entrée de `Get Ui5 Open Popups` du dialogue
    ...    dont l'identifiant se termine par le suffixe donné, ou échoue en
    ...    listant ce qui est réellement ouvert.
    [Arguments]    ${suffixe_id}
    ${popups}=    Get Ui5 Open Popups
    ${cibles}=    Evaluate
    ...    [p for p in $popups if p['kind'] == 'dialog' and p['id'].endswith($suffixe_id)]
    Should Not Be Empty    ${cibles}
    ...    msg=Le dialogue ${suffixe_id} n'est pas ouvert. Popups réellement ouverts : ${popups}
    RETURN    ${cibles}[0]

# --- Dialogue « à propos » ---------------------------------------------------

Ouvrir Le Dialogue A Propos
    [Documentation]    Ouvre le dialogue « à propos » depuis la zone
    ...    utilisateur et attend qu'il soit réellement ouvert.
    Ouvrir L Entree De La Zone Utilisateur    ${WORKZONE_ABOUT_ENTRY}
    Wait Until Keyword Succeeds    ${WORKZONE_POPUP_TIMEOUT}    ${WORKZONE_POPUP_RETRY}
    ...    Le Dialogue A Propos Est Ouvert

Le Dialogue A Propos Est Ouvert
    [Documentation]    Prédicat d'ouverture ; retourne l'entrée de popup
    ...    (state, buttons, ...) pour les assertions structurelles.
    ${dialogue}=    Lire Le Dialogue Ouvert    ${WORKZONE_ABOUT_DIALOG}
    RETURN    ${dialogue}

Lire Les Rubriques Du Dialogue A Propos
    [Documentation]    Rubriques de la liste du dialogue « à propos » :
    ...    position, identifiant (GÉNÉRÉ : journalisé, jamais une ancre),
    ...    rendu, titre (traduit : trace seulement). L'adresse d'une rubrique
    ...    est sa POSITION, la structure de la liste étant vérifiée ici même.
    ${items}=    Get Ui5 Aggregation Info    items
    ...    idSuffix=${WORKZONE_ABOUT_ENTRY_LIST}
    ${rubriques}=    Create List
    FOR    ${index}    ${item}    IN ENUMERATE    @{items}
        ${titre}=    Evaluate    str($item['properties'].get('title') or '')
        ${entree}=    Create Dictionary    position=${index}    id=${item}[id]
        ...    rendu=${item}[rendered]    titre=${titre}
        Append To List    ${rubriques}    ${entree}
    END
    RETURN    ${rubriques}

Lire Les Valeurs De La Rubrique A Propos
    [Documentation]    Sélectionne une rubrique du dialogue « à propos » par sa
    ...    position, puis lit les valeurs textuelles de SA page de détail
    ...    (ids stables `…DetailApplication`, `…DetailSystem`,
    ...    `…DetailEnvironment`). La lecture attend le rendu : la navigation
    ...    du conteneur est animée, et lire le dialogue entier mélangerait les
    ...    pages déjà visitées, restées rendues (mesuré live).
    ...
    ...    La première valeur retournée est l'entête de la rubrique (traduite) :
    ...    une rubrique vide, comme « System » sur un cFLP, rend son seul entête.
    [Arguments]    ${position}
    Click Ui5 Control    index=${position}    controlType=${WORKZONE_ABOUT_ITEM_TYPE}
    ...    containedIn=${WORKZONE_ABOUT_ENTRY_LIST}
    ${page}=    Get From List    ${WORKZONE_ABOUT_DETAIL_PAGES}    ${position}
    ${valeurs}=    Wait Until Keyword Succeeds    ${WORKZONE_POPUP_TIMEOUT}    ${WORKZONE_POPUP_RETRY}
    ...    La Rubrique A Propos Porte Des Valeurs    ${page}
    RETURN    ${valeurs}

La Rubrique A Propos Porte Des Valeurs
    [Documentation]    Prédicat de rendu d'une page de détail du dialogue « à
    ...    propos » : au moins une valeur textuelle est rendue dedans.
    ...    Retourne les valeurs lues.
    [Arguments]    ${page}
    ${valeurs}=    Get Ui5 Properties    text    controlType=${WORKZONE_ABOUT_TEXT_TYPE}
    ...    containedIn=${page}
    Should Not Be Empty    ${valeurs}
    ...    msg=La page de détail ${page} ne rend encore aucune valeur.
    RETURN    ${valeurs}

Fermer Le Dialogue A Propos
    [Documentation]    Referme le dialogue « à propos » par son bouton de
    ...    fermeture, à son identifiant STABLE (pas d'acquittement par
    ...    position ici, contrairement à l'ushell ABAP 1.120), puis attend la
    ...    fermeture réelle.
    Click Ui5 Control    idSuffix=${WORKZONE_ABOUT_CLOSE}
    Attendre Qu Aucun Popup Ne Soit Ouvert

# --- Dialogue des paramètres -------------------------------------------------

Ouvrir Les Parametres Utilisateur
    [Documentation]    Ouvre le dialogue des paramètres depuis la zone
    ...    utilisateur et attend qu'il soit réellement ouvert : sa vue se
    ...    charge en asynchrone, le menu se referme AVANT que le dialogue
    ...    apparaisse (mesuré live).
    Ouvrir L Entree De La Zone Utilisateur    ${WORKZONE_SETTINGS_ENTRY}
    Wait Until Keyword Succeeds    ${WORKZONE_POPUP_TIMEOUT}    ${WORKZONE_POPUP_RETRY}
    ...    Le Dialogue Des Parametres Est Ouvert

Le Dialogue Des Parametres Est Ouvert
    [Documentation]    Prédicat d'ouverture ; retourne l'entrée de popup pour
    ...    les assertions structurelles (0 bouton dans l'agrégation, les
    ...    actions vivant dans la barre de pied).
    ${dialogue}=    Lire Le Dialogue Ouvert    ${WORKZONE_SETTINGS_DIALOG}
    RETURN    ${dialogue}

Lire Les Cles Des Rubriques De Parametres
    [Documentation]    Clés TECHNIQUES des rubriques du dialogue des paramètres,
    ...    lues au contexte de liaison : l'identifiant des items est généré, et
    ...    une rubrique apportée par une extension du site porte une clé
    ...    générée horodatée (d'où : vérifier le socle, journaliser le reste).
    ${items}=    Get Ui5 Aggregation Info    items
    ...    idSuffix=${WORKZONE_SETTINGS_ENTRY_LIST}
    ${cles}=    Evaluate
    ...    [str((i['binding'] or {}).get('object', {}).get('id') or '') for i in $items if i['rendered']]
    RETURN    ${cles}

Les Actions Des Parametres Sont Rendues
    [Documentation]    Les deux actions du dialogue des paramètres
    ...    (enregistrer, annuler) sont rendues dans sa barre de pied :
    ...    exactement une de chaque. Aucune n'est actionnée ici.
    ${save}=    Get Ui5 Match Count    idSuffix=${WORKZONE_SETTINGS_SAVE}
    Should Be Equal As Integers    ${save}    1
    ...    msg=L'action d'enregistrement des paramètres n'est pas rendue (ou plusieurs le sont) : ${save}.
    ${cancel}=    Get Ui5 Match Count    idSuffix=${WORKZONE_SETTINGS_CANCEL}
    Should Be Equal As Integers    ${cancel}    1
    ...    msg=L'action d'annulation des paramètres n'est pas rendue (ou plusieurs le sont) : ${cancel}.

Annuler Les Parametres Utilisateur
    [Documentation]    Referme le dialogue des paramètres par ANNULER (jamais
    ...    l'enregistrement : il écrirait une personnalisation), attend la
    ...    fermeture réelle, et journalise le nombre de dialogues encore
    ...    RENDUS sans l'asserter : mesuré live, ce nombre dépend de la
    ...    fenêtre de lecture (1 juste après l'annulation, 0 au repos), seule
    ...    la liste des popups OUVERTS fait foi.
    Click Ui5 Control    idSuffix=${WORKZONE_SETTINGS_CANCEL}
    Attendre Qu Aucun Popup Ne Soit Ouvert
    ${rendus}=    Get Ui5 Match Count    controlType=sap.m.Dialog
    Log    Dialogues encore rendus après annulation (journalisé, jamais asserté) : ${rendus}.

Ouvrir La Rubrique De Parametres
    [Documentation]    Sélectionne une rubrique du dialogue des paramètres par
    ...    sa CLÉ TECHNIQUE (contexte de liaison) : l'identifiant de l'item est
    ...    découvert à l'appel, jamais gravé. Échoue en nommant la clé si
    ...    aucune rubrique ne la porte.
    [Arguments]    ${cle}
    ${items}=    Get Ui5 Aggregation Info    items
    ...    idSuffix=${WORKZONE_SETTINGS_ENTRY_LIST}
    ${cibles}=    Evaluate
    ...    [i['id'] for i in $items if i['rendered'] and str((i['binding'] or {}).get('object', {}).get('id') or '') == $cle]
    Should Not Be Empty    ${cibles}
    ...    msg=Aucune rubrique de paramètres ne porte la clé technique '${cle}' (dialogue fermé, ou clé absente de ce site).
    Click Ui5 Control    id=${cibles}[0]
    Wait For Ui5 Idle

Lire Les Themes Offerts
    [Documentation]    Thèmes offerts par la rubrique d'apparence : liste de
    ...    dicts `{identifiant, libelle, selectionne}`, identifiant et libellé
    ...    lus au contexte de liaison. Les entêtes de groupe de la liste,
    ...    sans contexte donc sans identifiant, sont écartés ici. Attend le
    ...    rendu de la liste (la rubrique se charge en asynchrone).
    ${themes}=    Wait Until Keyword Succeeds    ${WORKZONE_POPUP_TIMEOUT}    ${WORKZONE_POPUP_RETRY}
    ...    La Liste Des Themes Est Servie
    RETURN    ${themes}

La Liste Des Themes Est Servie
    [Documentation]    Prédicat de rendu de la liste des thèmes : au moins un
    ...    thème IDENTIFIÉ est rendu. Retourne les thèmes identifiés.
    ${items}=    Get Ui5 Aggregation Info    items    idSuffix=${WORKZONE_THEME_LIST}
    ${bruts}=    Evaluate
    ...    [{'identifiant': str((i['binding'] or {}).get('object', {}).get('id') or ''), 'libelle': str((i['binding'] or {}).get('object', {}).get('name') or ''), 'selectionne': bool(i['properties'].get('selected'))} for i in $items if i['rendered']]
    ${themes}=    Evaluate    [t for t in $bruts if t['identifiant']]
    Should Not Be Empty    ${themes}
    ...    msg=La liste des thèmes est rendue mais aucun thème identifié n'y figure encore.
    RETURN    ${themes}

Lire Le Reglage De Langue Et Region
    [Documentation]    Réglage de langue et région de la rubrique dédiée : clé
    ...    sélectionnée et clés offertes par le sélecteur, fuseau horaire
    ...    (identifiant IANA), langue du document et du navigateur. Un seul
    ...    relevé pour toutes les comparaisons de cohérence. Attend le rendu
    ...    du sélecteur.
    ${reglage}=    Wait Until Keyword Succeeds    ${WORKZONE_POPUP_TIMEOUT}    ${WORKZONE_POPUP_RETRY}
    ...    Le Reglage De Langue Est Servi
    RETURN    ${reglage}

Le Reglage De Langue Est Servi
    [Documentation]    Prédicat de rendu de la rubrique de langue : le
    ...    sélecteur est rendu. Retourne le relevé complet.
    ${selects}=    Get Ui5 Control Info    idSuffix=${WORKZONE_LANGUAGE_SELECT}
    Should Not Be Empty    ${selects}
    ...    msg=Le sélecteur de langue de la rubrique « Language and Region » n'est pas encore rendu.
    ${cle}=    Evaluate    str($selects[0]['properties'].get('selectedKey') or '')
    # Les items d'un Select ne sont PAS rendus popover fermé : la lecture
    # d'agrégation de la bibliothèque les voit quand même (rendus ou non).
    ${items}=    Get Ui5 Aggregation Info    items
    ...    idSuffix=${WORKZONE_LANGUAGE_SELECT}
    ${cles_offertes}=    Evaluate    [str(i['properties'].get('key') or '') for i in $items]
    ${tzs}=    Get Ui5 Control Info    idSuffix=${WORKZONE_TIMEZONE_TEXT}
    ${fuseau}=    Evaluate    str($tzs[0]['properties'].get('text') or '') if $tzs else ''
    ${langues}=    Get Page Languages
    ${reglage}=    Create Dictionary    cle_selectionnee=${cle}
    ...    cles_offertes=${cles_offertes}    fuseau=${fuseau}
    ...    langue_document=${langues}[document]
    ...    langue_navigateur=${langues}[navigator]
    RETURN    ${reglage}

# --- Theme Manager -----------------------------------------------------------

Compter Les Acces Au Theme Manager
    [Documentation]    Nombre d'éléments de barre shell correspondant au couple
    ...    type plus icône du Theme Manager. Son identifiant est GÉNÉRÉ : ce
    ...    couple est l'ancre, et il doit désigner exactement un élément.
    ${nb}=    Get Ui5 Match Count    controlType=${WORKZONE_THEME_MANAGER_TYPE}
    ...    properties=${WORKZONE_THEME_MANAGER_ICON}
    RETURN    ${nb}

Ouvrir Le Theme Manager
    [Documentation]    Ouvre le Theme Manager depuis la barre shell (couple
    ...    type plus icône) et attend qu'il soit réellement ouvert. Surface
    ...    d'ADMINISTRATION : ce page object l'ouvre, le lit et l'annule,
    ...    jamais plus.
    Click Ui5 Control    controlType=${WORKZONE_THEME_MANAGER_TYPE}
    ...    properties=${WORKZONE_THEME_MANAGER_ICON}
    Wait Until Keyword Succeeds    ${WORKZONE_POPUP_TIMEOUT}    ${WORKZONE_POPUP_RETRY}
    ...    Le Theme Manager Est Ouvert

Le Theme Manager Est Ouvert
    [Documentation]    Prédicat d'ouverture ; retourne l'entrée de popup.
    ${dialogue}=    Lire Le Dialogue Ouvert    ${WORKZONE_THEME_MANAGER_DIALOG}
    RETURN    ${dialogue}

Lire Les Actions Du Theme Manager
    [Documentation]    Identifiants des boutons rendus dans le Theme Manager :
    ...    la preuve que la surface expose des actions d'écriture nommées
    ...    (enregistrement, bascule de la sélection utilisateur), relevées
    ...    sans jamais les actionner.
    ${ids}=    Get Ui5 Ids    controlType=sap.m.Button
    ...    containedIn=${WORKZONE_THEME_MANAGER_DIALOG}
    RETURN    ${ids}

Annuler Le Theme Manager
    [Documentation]    Referme le Theme Manager par son action d'annulation et
    ...    attend la fermeture réelle. Aucune autre action n'est actionnée.
    Click Ui5 Control    id=${WORKZONE_THEME_MANAGER_CANCEL}
    Attendre Qu Aucun Popup Ne Soit Ouvert
