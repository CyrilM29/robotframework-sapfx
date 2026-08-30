*** Settings ***
Documentation       Exploration du shell d'un launchpad SAP Build Work Zone (SAP BTP)
...                 Spec: specs/workzone-launchpad-btp-perception.md (sha256:62feea22b46f, 2026-08-24)
...
...                 Campagne d'exploration du **shell d'un launchpad SAP Build
...                 Work Zone** hébergé sur SAP BTP, derrière un tenant SAP
...                 Cloud Identity Services.
...
...                 Ce que cette campagne établit, et qu'aucune fixture ne peut
...                 établir : le shell d'un vrai cFLP est une page HYBRIDE (UI5
...                 classique plus Web Components à tags scopés), son catalogue
...                 se lit à un service du shell et non au DOM, chaque
...                 application vit dans une iframe dont l'identifiant est
...                 GÉNÉRÉ, et la portée de résolution bascule proprement entre
...                 le shell et l'application.
...
...                 Campagne **pilotée par la découverte** : rien n'est codé en
...                 dur sur le contenu du site. Les applications parcourues sont
...                 celles que le catalogue déclare le jour du run, et les
...                 assertions sont relationnelles (mesures prises dans le même
...                 run) plutôt que calées sur une volumétrie de trial.
...
...                 **Lecture seule** : la campagne navigue et perçoit, elle
...                 n'écrit rien. Le parcours applicatif réversible vit dans
...                 `tests/robot/ui/fiori/parcours_panier_workzone.robot`.
...
...                 Aucun localisateur ici (convention 1) : ils vivent dans
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
...                 |  ...   tests/robot/ui/fiori/exploration_launchpad_workzone.robot

Resource            ../../../../resources/page_objects/workzone_launchpad.resource

Suite Setup         Ouvrir La Session Work Zone
Suite Teardown      Fermer La Session Work Zone
Test Teardown       Run Keywords    Journaliser Le Diagnostic Fiori En Cas D Echec
...                     AND    Sortir De L Application Si Necessaire

Test Tags           fiori    workzone    btp    live


*** Test Cases ***
Le launchpad est servi derriere un fournisseur d identite distinct
    [Documentation]    Scénario 1 du plan. Avant d'accorder du crédit à un login
    ...    vert, constater qu'un fournisseur d'identité est bien intervenu :
    ...    l'URL atteinte avant toute frappe est un point d'autorisation OAuth2,
    ...    et il est servi par un HÔTE différent de celui du site. Sans ce
    ...    constat, une page de login applicative locale produirait le même test
    ...    vert.
    Should Contain    ${WORKZONE_URL_AVANT_AUTHENTIFICATION}    ${WORKZONE_IDP_URL_MARKER}
    ...    msg=La cible n'a pas redirigé vers un point d'autorisation : elle n'est pas protégée par un IDP.
    # Décomposition par le keyword de bibliothèque (convention #12) : ni
    # __import__ ni modules= dans une suite (décision DDIC 2026-08-17).
    ${idp}=    Get Page Location    url=${WORKZONE_URL_AVANT_AUTHENTIFICATION}
    ${site}=    Get Page Location    url=${WORKZONE_SITE}
    ${hote_idp}=    Set Variable    ${idp}[host]
    ${hote_site}=    Set Variable    ${site}[host]
    Should Not Be Equal    ${hote_idp}    ${hote_site}
    ...    msg=Le formulaire d'authentification est servi par le site lui-même : aucun IDP externe n'est en jeu.
    ${url_courante}=    Get Url
    Should Contain    ${url_courante}    ${hote_site}
    ...    msg=Après authentification, le navigateur n'est pas revenu sur le site.
    Log    IDP : ${hote_idp} / site : ${hote_site}    console=True

Le shell est un cFLP reel dont la barre est en Web Components
    [Documentation]    Scénario 2 du plan. Le shell d'un Work Zone à jour n'est
    ...    plus une page UI5 homogène : sa barre est un jeu d'UI5 Web
    ...    Components. La composition doit donc annoncer À LA FOIS un runtime
    ...    UI5 avec des contrôles construits ET des hôtes Web Components, et
    ...    proposer le moteur `wc` en plus des moteurs UI5.
    ${composition}=    Lire La Composition De La Portee Courante
    Should Be True    ${composition}[ui5_runtime]
    ...    msg=Aucun runtime UI5 sur le shell du launchpad.
    Should Be True    ${composition}[ui5_controls] > 0
    ...    msg=Le runtime est là mais le shell n'a construit aucun contrôle.
    Should Be True    ${composition}[wc_hosts] > 0
    ...    msg=Aucun hôte Web Components : la barre shell attendue n'est pas celle de ce launchpad.
    Should Contain    ${composition}[engines]    wc
    ...    msg=Le moteur wc n'est pas proposé alors que la page porte des Web Components.
    ${barres}=    Compter Les Hotes Web Components De La Barre Shell
    Should Be True    ${barres} > 0
    ...    msg=La barre shell n'est pas résolue par le moteur Web Components.
    Log    Shell UI5 ${composition}[ui5_version] : ${composition}[ui5_controls] contrôles, ${composition}[wc_hosts] hôtes WC, moteurs ${composition}[engines]    console=True

Le catalogue expose des applications adressables par intent
    [Documentation]    Scénario 3 du plan. Le catalogue est lu au service du
    ...    shell, qui répond ce que l'utilisateur connecté a le DROIT d'ouvrir,
    ...    et non ce que cette page affiche. Chaque entrée doit porter un titre
    ...    et un intent de la forme `SemanticObject-action` : c'est cet intent,
    ...    et non une tuile, qui rend une application adressable de façon
    ...    stable.
    ${apps}=    Inventorier Les Applications Du Catalogue
    Should Not Be Empty    ${apps}
    ...    msg=Le catalogue du launchpad ne déclare aucune application pour cet utilisateur.
    FOR    ${app}    IN    @{apps}
        Should Not Be Empty    ${app}[titre]
        ...    msg=Une application du catalogue n'a pas de titre : ${app}
        ${morceaux}=    Split String    ${app}[intent]    -
        Length Should Be    ${morceaux}    2
        ...    msg=L'intent « ${app}[intent] » n'est pas de la forme SemanticObject-action
        Should Not Be Empty    ${morceaux}[0]
        Should Not Be Empty    ${morceaux}[1]
        Log    Application : ${app}[titre] -> ${app}[intent]    console=True
    END

Chaque application du catalogue s ouvre dans son iframe
    [Documentation]    Scénario 4 du plan. Le balayage est piloté par le
    ...    catalogue relevé plus haut : toutes les applications déclarées sont
    ...    ouvertes par leur intent, et chacune doit matérialiser une iframe
    ...    dont le contenu porte réellement des contrôles. Une application
    ...    déclarée mais qui n'ouvre rien est l'anomalie que ce scénario
    ...    cherche.
    [Setup]    Revenir A L Accueil Du Launchpad
    ${apps}=    Inventorier Les Applications Du Catalogue
    FOR    ${app}    IN    @{apps}
        Ouvrir L Application Par Intent    ${app}[intent]
        Entrer Dans L Application
        ${composition}=    Lire La Composition De La Portee Courante
        Should Be True    ${composition}[ui5_controls] > 0
        ...    msg=L'application « ${app}[titre] » s'ouvre mais ne construit aucun contrôle.
        Log    ${app}[titre] : ${composition}[ui5_controls] contrôles, ${composition}[url]    console=True
        Sortir De L Application
        Revenir A L Accueil Du Launchpad
    END

L iframe de l application est designee sans son identifiant genere
    [Documentation]    Scénario 5 du plan. L'identifiant de l'iframe
    ...    applicative est un compteur UI5 : relevé `__container1`, puis
    ...    `__container4`, puis `__container3` sur trois runs de la MÊME
    ...    application. Le test constate que l'identifiant réel est bien de
    ...    cette famille générée, et que le sélecteur retenu ne s'appuie pas
    ...    dessus.
    [Setup]    Revenir A L Accueil Du Launchpad
    ${apps}=    Inventorier Les Applications Du Catalogue
    Ouvrir L Application Par Intent    ${apps}[0][intent]
    ${selecteur}=    Entrer Dans L Application
    ${ids}=    Lire Les Identifiants D Iframe
    Should Not Be Empty    ${ids}
    ...    msg=Aucune iframe dans le shell alors qu'une application est ouverte.
    Should Contain    ${selecteur}    ${WORKZONE_APP_FRAME_PATTERN}
    ...    msg=Le sélecteur de frame n'est pas positionnel : ${selecteur}
    FOR    ${id}    IN    @{ids}
        Should Not Contain    ${selecteur}    ${id}
        ...    msg=Le sélecteur de frame s'appuie sur un identifiant généré (${id}).
        Log    Identifiant d'iframe de ce run : ${id}    console=True
    END

La portee de frame est etanche entre le shell et l application
    [Documentation]    Scénario 6 du plan. La bascule de portée n'est pas
    ...    cosmétique : depuis le shell, les contrôles de l'application sont
    ...    INVISIBLES au registre, et réciproquement. Le témoin retenu est le
    ...    champ de recherche du shell, qui doit être résolu une fois sur le
    ...    shell et zéro fois depuis l'application, et la perception doit
    ...    décrire deux documents différents.
    ...
    ...    Le nombre de contrôles n'est PAS le témoin : il est journalisé pour
    ...    le lecteur, mais rien ne garantit qu'une application embarquée en
    ...    porte plus que le shell qui l'héberge, et il varie pendant le
    ...    démarrage de l'application.
    [Setup]    Revenir A L Accueil Du Launchpad
    ${apps}=    Inventorier Les Applications Du Catalogue
    Ouvrir L Application Par Intent    ${apps}[0][intent]
    Entrer Dans L Application
    ${dans_l_app}=    Compter Le Champ De Recherche Du Shell
    ${composition_app}=    Lire La Composition De La Portee Courante
    Sortir De L Application
    ${sur_le_shell}=    Compter Le Champ De Recherche Du Shell
    ${composition_shell}=    Lire La Composition De La Portee Courante
    Should Be Equal As Integers    ${dans_l_app}    0
    ...    msg=Le champ de recherche du shell est résolu depuis l'application : la portée fuit.
    Should Be Equal As Integers    ${sur_le_shell}    1
    ...    msg=Le champ de recherche du shell n'est plus résolu après le retour au shell.
    Should Not Be Equal    ${composition_app}[url]    ${composition_shell}[url]
    ...    msg=La perception décrit le même document dans les deux portées : la portée n'a pas basculé.
    Should Be True    ${composition_app}[ui5_controls] > 0
    ...    msg=La portée applicative ne perçoit aucun contrôle.
    Log    Contrôles : ${composition_app}[ui5_controls] dans l'application, ${composition_shell}[ui5_controls] sur le shell    console=True

Le retour a l accueil detruit l iframe et l absence est diagnostiquee
    [Documentation]    Scénario 7 du plan. Le chemin d'erreur, éprouvé pour
    ...    lui-même : de retour à l'accueil, plus aucune iframe n'existe et la
    ...    demande de frame applicative doit échouer en NOMMANT ce qui a été
    ...    trouvé et le remède, plutôt que par un « sélecteur introuvable » qui
    ...    enverrait chercher une dérive de localisateur.
    [Setup]    Revenir A L Accueil Du Launchpad
    ${apps}=    Inventorier Les Applications Du Catalogue
    Ouvrir L Application Par Intent    ${apps}[0][intent]
    ${ids_avec_application}=    Lire Les Identifiants D Iframe
    Should Not Be Empty    ${ids_avec_application}
    Revenir A L Accueil Du Launchpad
    ${ids_sur_l_accueil}=    Lire Les Identifiants D Iframe
    Should Be Empty    ${ids_sur_l_accueil}
    ...    msg=Une iframe survit au retour à l'accueil : ${ids_sur_l_accueil}
    Aucune Iframe D Application N Est Presente

La tuile de l accueil ouvre la meme application que l intent
    [Documentation]    Scénario 8 du plan. Les deux voies d'ouverture doivent
    ...    mener au même endroit : celle de l'utilisateur (cliquer la tuile par
    ...    son titre) et celle des tests (naviguer par intent). La comparaison
    ...    porte sur l'URL réellement chargée dans l'iframe, mesurée dans le
    ...    même run par les deux voies.
    [Setup]    Revenir A L Accueil Du Launchpad
    ${tuiles}=    Compter Les Tuiles De L Accueil
    Should Be True    ${tuiles} > 0
    ...    msg=Aucune tuile sur l'accueil du launchpad : la voie « comme l'utilisateur » n'existe pas.
    ${apps}=    Inventorier Les Applications Du Catalogue
    Ouvrir L Application Par Sa Tuile    ${apps}[0][titre]
    Entrer Dans L Application
    ${par_la_tuile}=    Lire La Composition De La Portee Courante
    Sortir De L Application
    Revenir A L Accueil Du Launchpad
    Ouvrir L Application Par Intent    ${apps}[0][intent]
    Entrer Dans L Application
    ${par_l_intent}=    Lire La Composition De La Portee Courante
    Sortir De L Application
    Should Be Equal    ${par_la_tuile}[url]    ${par_l_intent}[url]
    ...    msg=La tuile et l'intent n'ouvrent pas la même application (${par_la_tuile}[url] vs ${par_l_intent}[url])

Le shell n emet aucune erreur non rattrapee
    [Documentation]    Scénario 9 du plan. Compter les erreurs console d'un
    ...    launchpad ne veut rien dire : UI5 journalise ses PROPRES
    ...    dépréciations en niveau `error`, et le shell d'un Work Zone à jour en
    ...    émet des dizaines sans qu'aucune application soit en cause. La seule
    ...    propriété assertable est donc l'absence d'exception JS non
    ...    rattrapée ; le reste est CLASSÉ puis rapporté, sans faire échouer un
    ...    test sur du code que nous ne maintenons pas (posture « constater, ne
    ...    pas corriger »).
    [Setup]    Revenir A L Accueil Du Launchpad
    ${bilan}=    Classer Les Erreurs De La Page Du Shell
    Should Be Equal As Integers    ${bilan}[erreurs_de_page]    0
    ...    msg=Le shell a émis ${bilan}[erreurs_de_page] exception(s) JS non rattrapée(s).
    ${classees}=    Evaluate    $bilan['depreciations'] + $bilan['autres']
    Should Be Equal As Integers    ${classees}    ${bilan}[erreurs_console]
    ...    msg=Le tri des erreurs console n'est pas exhaustif : ${classees} classées sur ${bilan}[erreurs_console].
    Log    Console du shell : ${bilan}[erreurs_console] erreurs, dont ${bilan}[depreciations] dépréciations UI5 et ${bilan}[autres] autres. Première autre : ${bilan}[premiere_autre]    console=True
