*** Settings ***
Documentation       Zone utilisateur et paramètres du shell d'un launchpad Work Zone (BTP)
...                 Spec: specs/workzone-zone-utilisateur-parametres.md (sha256:94fafe880f35, 2026-08-26)
...                 Generated from specs/workzone-zone-utilisateur-parametres.md by sap-generator:
...                 re-run the generator rather than hand-editing locators here.
...
...                 Campagne de la **zone utilisateur et des paramètres du
...                 shell** d'un launchpad SAP Build Work Zone (cFLP sur BTP,
...                 derrière un tenant SAP Cloud Identity Services) : avatar et
...                 menu utilisateur, dialogue « à propos », dialogue des
...                 paramètres (rubriques, apparence, langue et région), Theme
...                 Manager, et la preuve finale que le compte est rendu à son
...                 état initial.
...
...                 Ce que cette campagne établit, et qu'aucune fixture ne
...                 peut établir : la zone utilisateur d'un vrai cFLP est un
...                 Web Component dont le menu ne se constate OUVERT que sur
...                 sa propriété (ses entrées restent rendues menu fermé), ses
...                 entrées dépendent de l'endroit (l'index n'est pas une
...                 ancre), les dialogues du shell gardent leurs identifiants
...                 stables mais leurs rubriques sont générées, et un site
...                 peut servir l'anglais à un navigateur français parce que
...                 la traduction n'est pas publiée.
...
...                 **Lecture seule** : les dialogues sont ouverts, lus, puis
...                 refermés par leur action d'annulation. Aucun bouton
...                 d'enregistrement n'est actionné, et le Theme Manager
...                 (surface d'administration du site) est constaté sans
...                 qu'aucune de ses actions ne soit déclenchée.
...
...                 Aucun localisateur ici (convention 1) : ils vivent dans
...                 `resources/page_objects/workzone_user_area.resource` et
...                 `resources/page_objects/workzone_launchpad.resource`.
...
...                 Prérequis : un site Work Zone accessible et un utilisateur
...                 du tenant. Exécution ::
...
...                 |  robot --pythonpath src
...                 |  ...   -v WORKZONE_SITE:<url du site>
...                 |  ...   -v WORKZONE_USER:<utilisateur>
...                 |  ...   -v "WORKZONE_PASSWORD: Secret:<motdepasse>"
...                 |  ...   --outputdir results/workzone
...                 |  ...   tests/robot/ui/fiori/zone_utilisateur_workzone.robot

Resource            ../../../../resources/page_objects/workzone_user_area.resource

Suite Setup         Preparer La Campagne Zone Utilisateur
Suite Teardown      Clore La Campagne Zone Utilisateur
Test Teardown       Run Keywords    Journaliser Le Diagnostic Fiori En Cas D Echec
...                     AND    Fermer Tout Popup Restant

Test Tags           fiori    workzone    btp    live


*** Test Cases ***
La barre shell est en Web Components et sa zone utilisateur est un avatar
    [Documentation]    Scénario 1 du plan. La composition doit annoncer un
    ...    runtime UI5 avec des contrôles construits ET proposer le moteur
    ...    `wc` ; le comptage PROFOND des hôtes Web Components (à travers les
    ...    shadow roots) est strictement supérieur au comptage de surface, ce
    ...    qui prouve que le shell imbrique des composants ; et la zone
    ...    utilisateur est un Avatar de la distribution Web Components, rendu
    ...    sur un rectangle non nul, exactement ce que la configuration du
    ...    shell déclare.
    ${composition}=    Lire La Composition De La Portee Courante
    Should Be True    ${composition}[ui5_runtime]
    ...    msg=Aucun runtime UI5 sur le shell du launchpad.
    Should Be True    ${composition}[ui5_controls] > 0
    ...    msg=Le runtime est là mais le shell n'a construit aucun contrôle.
    Should Contain    ${composition}[engines]    wc
    ...    msg=Le moteur wc n'est pas proposé alors que la page porte des Web Components.
    ${surface}=    Compter Les Hotes Web Components En Surface
    ${profondeur}=    Compter Les Hotes Web Components En Profondeur
    Should Be True    ${profondeur} > ${surface}
    ...    msg=Le comptage profond (${profondeur}) ne dépasse pas la surface (${surface}) : aucun composant imbriqué dans un shadow root, ce n'est pas la barre shell attendue.
    ${barres}=    Compter Les Hotes Web Components De La Barre Shell
    Should Be True    ${barres} > 0
    ...    msg=La barre shell n'est pas résolue par le moteur Web Components.
    La Zone Utilisateur Est Visible
    ${type}=    Lire Le Type De La Zone Utilisateur
    Should End With    ${type}    ${WORKZONE_AVATAR_TYPE_SUFFIX}
    ...    msg=La zone utilisateur n'est pas un Avatar : ${type}
    Should Contain    ${type}    ${WORKZONE_WC_TYPE_MARKER}
    ...    msg=La zone utilisateur n'est pas rendue par la distribution Web Components : ${type}
    La Configuration Declare L Avatar De La Zone Utilisateur
    Log    Shell UI5 ${composition}[ui5_version] : ${surface} hôtes WC en surface, ${profondeur} en profondeur ; zone utilisateur ${type}    console=True

La zone utilisateur ouvre un menu dont l ouverture se constate sur une propriete
    [Documentation]    Scénario 2 du plan. Le témoin d'ouverture d'un menu en
    ...    Web Components n'est ni la présence ni le comptage de ses entrées :
    ...    le comptage est identique menu ouvert et menu refermé (et vaut même
    ...    zéro avant la toute première ouverture, le menu étant construit au
    ...    premier clic). La propriété d'ouverture, elle, bascule à chaque
    ...    geste, et le menu ouvert apparaît comme popover Web Components dans
    ...    les popups ouverts. Sans ce scénario, « j'ai cliqué l'avatar, je
    ...    vois 5 entrées » serait vert sans avoir jamais ouvert le menu.
    ${avant_premiere_ouverture}=    Compter Les Entrees De La Zone Utilisateur
    Ouvrir La Zone Utilisateur
    ${ouvertes}=    Compter Les Entrees De La Zone Utilisateur
    Should Be True    ${ouvertes} > 0
    ...    msg=Le menu est ouvert mais aucune entrée n'est rendue.
    ${popover}=    La Zone Utilisateur Apparait Dans Les Popups Ouverts
    Fermer La Zone Utilisateur Par Echappement
    ${refermees}=    Compter Les Entrees De La Zone Utilisateur
    Should Be Equal As Integers    ${ouvertes}    ${refermees}
    ...    msg=Le comptage d'entrées distingue le menu ouvert (${ouvertes}) du menu refermé (${refermees}) : le piège documenté n'existe plus, re-vérifier le plan.
    Ouvrir La Zone Utilisateur
    Fermer La Zone Utilisateur Par Bascule
    Log    Entrées rendues : ${avant_premiere_ouverture} avant la première ouverture, ${ouvertes} menu ouvert, ${refermees} menu refermé ; popover ouvert vu comme ${popover}[controlType] (${popover}[technology])    console=True

Les entrees de la zone utilisateur dependent de l endroit
    [Documentation]    Scénario 3 du plan. Les deux relevés (accueil, puis
    ...    dans une application du catalogue) contiennent les entrées
    ...    permanentes ; l'accueil porte EXACTEMENT une entrée de plus, celle
    ...    de l'édition de l'accueil ; et l'identifiant complet d'une même
    ...    entrée change d'index entre les deux endroits, la preuve que
    ...    l'index n'est pas une ancre. Assertions relationnelles : deux
    ...    relevés du même run, jamais un cardinal gravé (un compte non
    ...    administrateur n'aurait pas l'entrée d'administration).
    Ouvrir La Zone Utilisateur
    ${ids_accueil}=    Lire Les Identifiants Des Entrees De La Zone Utilisateur
    ${sur_accueil}=    Lire Les Suffixes D Action De La Zone Utilisateur
    Fermer La Zone Utilisateur Par Echappement
    ${apps}=    Inventorier Les Applications Du Catalogue
    Should Not Be Empty    ${apps}
    ...    msg=Le catalogue ne déclare aucune application : impossible de relever le menu en application.
    Ouvrir L Application Par Intent    ${apps}[0][intent]
    Ouvrir La Zone Utilisateur
    ${ids_app}=    Lire Les Identifiants Des Entrees De La Zone Utilisateur
    ${en_application}=    Lire Les Suffixes D Action De La Zone Utilisateur
    Fermer La Zone Utilisateur Par Echappement
    Revenir A L Accueil Du Launchpad
    FOR    ${permanente}    IN    @{WORKZONE_PERMANENT_ENTRIES}
        Should Contain    ${sur_accueil}    ${permanente}
        ...    msg=L'entrée permanente ${permanente} manque au relevé de l'accueil : ${sur_accueil}
        Should Contain    ${en_application}    ${permanente}
        ...    msg=L'entrée permanente ${permanente} manque au relevé en application : ${en_application}
    END
    ${ecart}=    Evaluate    sorted(set($sur_accueil) - set($en_application))
    ${attendu}=    Create List    ${WORKZONE_EDIT_ENTRY}
    Should Be Equal    ${ecart}    ${attendu}
    ...    msg=L'écart accueil moins application n'est pas exactement l'entrée d'édition : ${ecart}
    ${a_propos_accueil}=    Evaluate    [i for i in $ids_accueil if i.endswith($WORKZONE_ABOUT_ENTRY)][0]
    ${a_propos_app}=    Evaluate    [i for i in $ids_app if i.endswith($WORKZONE_ABOUT_ENTRY)][0]
    Should Not Be Equal    ${a_propos_accueil}    ${a_propos_app}
    ...    msg=La même entrée porte le même identifiant aux deux endroits : l'index serait donc une ancre, re-vérifier le plan.
    Log    Entrée « à propos » : ${a_propos_accueil} à l'accueil, ${a_propos_app} en application (l'index bouge, le suffixe tient)    console=True

Le dialogue a propos identifie le launchpad et son runtime
    [Documentation]    Scénario 4 du plan. Un unique popup ouvert, de type
    ...    dialogue, état `None`, un seul bouton ; trois rubriques adressées
    ...    par leur position (leurs identifiants sont générés : trois runs ont
    ...    rendu trois jeux d'ids différents) ; la rubrique « App » nomme le
    ...    composant applicatif du launchpad et une version de framework qui
    ...    partage la ligne majeure et mineure du runtime chargé ; la rubrique
    ...    « System » est vide sur un cFLP (constatée, jamais exigée non
    ...    vide) ; la rubrique « Environment » donne le thème sous sa forme
    ...    technique, identique à celle du conteneur ushell ; et la fermeture
    ...    passe par le bouton à identifiant STABLE.
    ${identite}=    Lire L Identite De Session
    Ouvrir Le Dialogue A Propos
    ${structure}=    Le Dialogue A Propos Est Ouvert
    Should Be Equal    ${structure}[state]    None
    ...    msg=Le dialogue « à propos » porte un état ${structure}[state] : ce n'est pas le dialogue neutre attendu.
    Should Be Equal As Integers    ${structure}[buttons]    1
    ...    msg=Le dialogue « à propos » rend ${structure}[buttons] bouton(s) au lieu d'un seul.
    ${popups}=    Get Ui5 Open Popups
    Length Should Be    ${popups}    1
    ...    msg=Autre chose que le dialogue « à propos » est ouvert : ${popups}
    ${rubriques}=    Lire Les Rubriques Du Dialogue A Propos
    Length Should Be    ${rubriques}    3
    ...    msg=Le dialogue « à propos » ne porte pas ses trois rubriques : ${rubriques}
    ${app}=    Lire Les Valeurs De La Rubrique A Propos    0
    Should Contain    ${app}    ${WORKZONE_ABOUT_COMPONENT}
    ...    msg=La rubrique « App » ne nomme pas le composant applicatif du launchpad (${WORKZONE_ABOUT_COMPONENT}) : ${app}
    ${composition}=    Lire La Composition De La Portee Courante
    ${ligne_runtime}=    Evaluate    '.'.join($composition['ui5_version'].split('.')[:2])
    ${au_niveau}=    Evaluate    [v for v in $app if v.startswith($ligne_runtime)]
    Should Not Be Empty    ${au_niveau}
    ...    msg=Aucune valeur de la rubrique « App » ne partage la ligne ${ligne_runtime} du runtime chargé : ${app}
    ${system}=    Lire Les Valeurs De La Rubrique A Propos    1
    Log    Rubrique « System » (vide sur un cFLP, constat et non anomalie) : ${system}    console=True
    ${environnement}=    Lire Les Valeurs De La Rubrique A Propos    2
    Should Contain    ${environnement}    ${identite}[theme]
    ...    msg=La rubrique « Environment » ne donne pas le thème technique du conteneur (${identite}[theme]) : ${environnement}
    Fermer Le Dialogue A Propos
    Log    Empreinte du launchpad : ${app}    console=True

Le dialogue des parametres s ouvre expose ses rubriques et se referme sans rien ecrire
    [Documentation]    Scénario 5 du plan. Le dialogue des paramètres est
    ...    ouvert (sa vue se charge en asynchrone) ; les quatre clés
    ...    techniques du socle sont présentes et les clés supplémentaires
    ...    (extensions du site, clés générées horodatées) sont journalisées
    ...    sans être assertées ; le dialogue expose zéro bouton dans son
    ...    agrégation et ses deux actions dans la barre de pied ; après
    ...    ANNULATION, plus aucun popup n'est ouvert et le couple thème plus
    ...    langue est strictement identique au relevé d'entrée. La
    ...    constatation de fermeture porte sur les popups OUVERTS : le
    ...    dialogue peut rester rendu un moment après l'annulation.
    ${avant}=    Lire L Identite De Session
    Ouvrir Les Parametres Utilisateur
    ${structure}=    Le Dialogue Des Parametres Est Ouvert
    Should Be Equal As Integers    ${structure}[buttons]    0
    ...    msg=Le dialogue des paramètres rend ${structure}[buttons] bouton(s) dans son agrégation : ses actions vivent dans la barre de pied.
    ${popups}=    Get Ui5 Open Popups
    Length Should Be    ${popups}    1
    ...    msg=Autre chose que le dialogue des paramètres est ouvert : ${popups}
    ${cles}=    Lire Les Cles Des Rubriques De Parametres
    FOR    ${socle}    IN    @{WORKZONE_SETTINGS_BASE_KEYS}
        Should Contain    ${cles}    ${socle}
        ...    msg=La clé du socle ${socle} manque aux rubriques de paramètres : ${cles}
    END
    ${extensions}=    Evaluate    [c for c in $cles if c not in $WORKZONE_SETTINGS_BASE_KEYS]
    Log    Rubriques hors socle (extensions du site, clés générées : journalisées, jamais assertées) : ${extensions}    console=True
    Les Actions Des Parametres Sont Rendues
    Annuler Les Parametres Utilisateur
    Aucun Popup N Est Ouvert
    ${apres}=    Lire L Identite De Session
    Should Be Equal    ${apres}[theme]    ${avant}[theme]
    ...    msg=Le thème a changé alors que le dialogue a été annulé (${avant}[theme] avant, ${apres}[theme] après).
    Should Be Equal    ${apres}[langue]    ${avant}[langue]
    ...    msg=La langue a changé alors que le dialogue a été annulé (${avant}[langue] avant, ${apres}[langue] après).

La rubrique d apparence propose des themes identifies techniquement
    [Documentation]    Scénario 6 du plan. La rubrique d'apparence est ouverte
    ...    par sa CLÉ technique (l'identifiant de la rubrique est généré) ; la
    ...    liste des thèmes n'est pas vide ; exactement un thème est
    ...    sélectionné et son identifiant technique égale celui que rend le
    ...    conteneur ushell ; et au moins un libellé est porté par deux
    ...    identifiants différents : la démonstration chiffrée qu'un
    ...    localisateur par nom visible est ambigu ici. Aucun thème n'est
    ...    cliqué.
    Ouvrir Les Parametres Utilisateur
    Ouvrir La Rubrique De Parametres    ${WORKZONE_APPEARANCE_SECTION}
    ${themes}=    Lire Les Themes Offerts
    Should Not Be Empty    ${themes}
    ...    msg=La rubrique d'apparence n'offre aucun thème identifié.
    ${selectionnes}=    Evaluate    [t for t in $themes if t['selectionne']]
    Length Should Be    ${selectionnes}    1
    ...    msg=La liste des thèmes ne marque pas exactement un thème sélectionné : ${selectionnes}
    ${du_compte}=    Lire Le Theme Du Compte
    Should Be Equal    ${selectionnes}[0][identifiant]    ${du_compte}
    ...    msg=Le thème marqué sélectionné (${selectionnes}[0][identifiant]) n'est pas celui du compte (${du_compte}).
    ${libelles}=    Evaluate    [t['libelle'] for t in $themes]
    ${partages}=    Evaluate    sorted({x for x in $libelles if $libelles.count(x) > 1})
    Should Not Be Empty    ${partages}
    ...    msg=Aucun libellé partagé par deux thèmes : la preuve d'ambiguïté attendue n'existe plus, re-vérifier le plan.
    Log    ${{len($themes)}} thèmes identifiés ; sélectionné : ${du_compte} ; libellé(s) porté(s) par plusieurs identifiants : ${partages}    console=True
    Annuler Les Parametres Utilisateur

La rubrique de langue explique la langue reellement servie
    [Documentation]    Scénario 7 du plan. Le sélecteur de langue offre au
    ...    moins une clé et sa clé sélectionnée en fait partie ; le fuseau est
    ...    un identifiant IANA (contrôle de forme par découpage sur la barre
    ...    oblique, jamais une expression régulière à contre-oblique) ; et la
    ...    langue du document est COHÉRENTE avec la clé : la clé elle-même,
    ...    ou, quand la clé vaut « langue du navigateur », une langue offerte
    ...    par le site. C'est la démonstration, dans le test, que les libellés
    ...    du shell ne suivent pas la locale du poste : elle justifie la
    ...    convention 3 pour toute la campagne.
    Ouvrir Les Parametres Utilisateur
    Ouvrir La Rubrique De Parametres    ${WORKZONE_LANGUAGE_SECTION}
    ${reglage}=    Lire Le Reglage De Langue Et Region
    Should Not Be Empty    ${reglage}[cles_offertes]
    ...    msg=Le sélecteur de langue n'offre aucune clé.
    Should Contain    ${reglage}[cles_offertes]    ${reglage}[cle_selectionnee]
    ...    msg=La clé sélectionnée (${reglage}[cle_selectionnee]) n'est pas parmi les clés offertes (${reglage}[cles_offertes]).
    ${morceaux}=    Evaluate    $reglage['fuseau'].split('/')
    Should Be True    len($morceaux) >= 2
    ...    msg=Le fuseau « ${reglage}[fuseau] » n'a pas la forme IANA Region/Ville.
    ${langue_document}=    Evaluate    $reglage['langue_document'].split('-')[0]
    IF    $reglage['cle_selectionnee'] == 'default'
        Should Contain    ${reglage}[cles_offertes]    ${langue_document}
        ...    msg=La clé vaut « langue du navigateur » mais le document est servi en ${langue_document}, une langue que le site n'offre pas (${reglage}[cles_offertes]).
    ELSE
        Should Be Equal    ${langue_document}    ${reglage}[cle_selectionnee]
        ...    msg=Le document est servi en ${langue_document} alors que la clé sélectionnée est ${reglage}[cle_selectionnee].
    END
    Log    Clé ${reglage}[cle_selectionnee], navigateur ${reglage}[langue_navigateur], document ${reglage}[langue_document], fuseau ${reglage}[fuseau] : le site sert ce qu'il publie, pas la locale du poste    console=True
    Annuler Les Parametres Utilisateur

Le theme manager est une surface d administration ouverte et refermee sans rien changer
    [Documentation]    Scénario 8 du plan. Exactement un élément de barre
    ...    shell correspond au couple type plus icône (son identifiant est
    ...    généré) ; le dialogue ouvert expose des actions d'écriture
    ...    identifiées nommément, dont l'enregistrement et la bascule de la
    ...    sélection utilisateur ; après ANNULATION, le thème du compte est
    ...    inchangé et plus aucun popup n'est ouvert. Ce dialogue configure
    ...    les thèmes de TOUS les utilisateurs du site : la campagne le
    ...    constate comme surface d'administration et n'actionne aucune de
    ...    ses actions.
    ${theme_avant}=    Lire Le Theme Du Compte
    ${acces}=    Compter Les Acces Au Theme Manager
    Should Be Equal As Integers    ${acces}    1
    ...    msg=Le couple type plus icône ne désigne pas exactement un accès au Theme Manager : ${acces}.
    Ouvrir Le Theme Manager
    ${actions}=    Lire Les Actions Du Theme Manager
    Should Contain    ${actions}    ${WORKZONE_THEME_MANAGER_SAVE}
    ...    msg=L'action d'enregistrement du Theme Manager n'est pas rendue : ${actions}
    Should Contain    ${actions}    ${WORKZONE_THEME_MANAGER_TOGGLE}
    ...    msg=La bascule de sélection utilisateur du Theme Manager n'est pas rendue : ${actions}
    Should Contain    ${actions}    ${WORKZONE_THEME_MANAGER_CANCEL}
    ...    msg=L'action d'annulation du Theme Manager n'est pas rendue : ${actions}
    Log    Actions offertes par le Theme Manager (constatées, jamais actionnées) : ${actions}    console=True
    Annuler Le Theme Manager
    ${theme_apres}=    Lire Le Theme Du Compte
    Should Be Equal    ${theme_apres}    ${theme_avant}
    ...    msg=Le thème du compte a changé après une simple ouverture puis annulation du Theme Manager (${theme_avant} avant, ${theme_apres} après).

Le parcours rend le compte a son etat initial
    [Documentation]    Scénario 9 du plan, dernier test de la suite. Thème et
    ...    langue identiques à ceux relevés par le Suite Setup, aucun popup
    ...    ouvert, aucune iframe applicative résiduelle, pile de frames vide :
    ...    la propriété qui autorise à rejouer la campagne sur un site
    ...    partagé.
    L Etat Du Compte Est Inchange
    Aucun Popup N Est Ouvert
    Aucune Iframe D Application N Est Presente
    ${pile}=    Get Ui5 Frame Stack
    Should Be Empty    ${pile}
    ...    msg=La pile de frames n'est pas vide en fin de campagne : ${pile}
    ${iframes}=    Lire Les Identifiants D Iframe
    Should Be Empty    ${iframes}
    ...    msg=Des iframes survivent en fin de campagne : ${iframes}
