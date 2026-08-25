*** Settings ***
Documentation       Authentification contre un **vrai tenant SAP Cloud Identity
...                 Services**, et non contre une imitation.
...
...                 Le pendant live de `tests/robot/fiori_auth_smoke.robot`, qui
...                 reste la suite de CI : celle-ci exige un système réel et des
...                 identifiants, celle-là tourne partout et survivra aux 90
...                 jours d'un trial. Les deux se complètent, l'une ne remplace
...                 pas l'autre.
...
...                 Ce que seule une cible réelle prouve, et que la fixture ne
...                 pouvait pas :
...                 - le tenant sert son formulaire en **UNE page** (identifiant
...                   et mot de passe ensemble) là où la fixture imite le
...                   déroulé à DEUX étapes ; le keyword prétend détecter les
...                   deux, on le vérifie ici ;
...                 - la chaîne de redirection réelle (launchpad -> IAS
...                   ``/oauth2/authorize`` -> retour), qu'aucune page locale ne
...                   reproduit ;
...                 - l'atterrissage sur un shell cFLP réel, avec son runtime
...                   UI5 et ses Web Components.
...
...                 **Un test d'échec ne se fait PAS sur un compte réel.** Un IAS
...                 verrouille un utilisateur après quelques tentatives ratées :
...                 le scénario d'échec utilise donc une identité INEXISTANTE,
...                 qui échoue à l'identification sans jamais compter contre le
...                 compte de travail. C'est la différence entre éprouver un
...                 chemin d'erreur et abîmer son environnement.
...
...                 Prérequis : un site Work Zone accessible et un utilisateur du
...                 tenant IAS. Exécution ::
...
...                 |  robot --pythonpath src --include ias
...                 |  ...   -v IAS_SITE:<url du site>
...                 |  ...   -v IAS_USER:<utilisateur>
...                 |  ...   -v "IAS_PASSWORD: Secret:<mot de passe>"
...                 |  ...   tests/robot/ui/fiori/authentification_ias_live.robot

# La couche resource porte déjà Browser et SapFioriLibrary (convention 1) :
# les ré-importer ici avec d'autres arguments créerait une SECONDE instance de
# la bibliothèque, avec sa propre pile de frames, et deux états qui divergent.
Resource            ../../../../resources/fiori_keywords.resource

Suite Teardown      Run Keyword And Ignore Error    Close Browser
Test Tags           ias    live


*** Variables ***
${HEADLESS}         ${True}
# Cible et identifiants fournis en ligne de commande : convention 11, aucune
# valeur par défaut committée pour un identifiant.
${IAS_SITE}         ${EMPTY}
${IAS_USER}         ${EMPTY}
${IAS_PASSWORD}     ${EMPTY}
# Identité volontairement inexistante, pour éprouver le refus à
# l'IDENTIFICATION. Le domaine `.invalid` est réservé par la RFC 2606 : il ne
# peut jamais être enregistré, donc cette identité ne risque pas de désigner un
# jour quelqu'un.
${IAS_INCONNU}      sapfx-utilisateur-inexistant@example.invalid
# Compte DÉDIÉ au test, existant dans le tenant, sans rôle et sans usage
# ailleurs : c'est lui qu'on maltraite pour éprouver le refus à
# l'AUTHENTIFICATION, et son verrouillage éventuel n'a aucune conséquence.
# Aucun mot de passe n'est requis : le scénario en fournit un faux à dessein.
${IAS_TEST_USER}    ${EMPTY}


*** Keywords ***
Ouvrir Le Launchpad Non Authentifie
    [Documentation]    Ouvre la cible et laisse la redirection vers l'IDP se
    ...    produire. Chaque test repart d'un contexte NEUF : une session déjà
    ...    ouverte court-circuiterait le formulaire, et le test ne testerait
    ...    plus rien tout en restant vert.
    New Context
    New Page    ${IAS_SITE}

Le Shell A Rendu Ses Controles
    [Documentation]    La preuve d'atterrissage : des contrôles UI5 réellement
    ...    construits, et non le seul chargement du runtime.
    ${composition}=    Get Page Composition
    Should Be True    ${composition}[ui5_controls] > 0
    ...    msg=Aucun contrôle UI5 rendu : le shell n'est pas là.
    Log    Shell réel : ${composition}[ui5_controls] contrôles, ${composition}[wc_hosts] hôtes Web Components    console=True

La Cible Et Les Identifiants Sont Fournis
    Should Not Be Empty    ${IAS_SITE}
    ...    msg=Cible absente : passer -v IAS_SITE:<url du site Work Zone>.
    Should Not Be Empty    ${IAS_USER}
    ...    msg=Utilisateur absent : passer -v IAS_USER:<utilisateur du tenant>.
    # Le mot de passe n'est JAMAIS mesuré : un type `Secret` refuse d'être lu
    # et l'erreur de garde masquerait la vraie cause (leçon du canal API).
    ${fourni}=    Evaluate    not isinstance($IAS_PASSWORD, str) or bool($IAS_PASSWORD)
    Should Be True    ${fourni}
    ...    msg=Mot de passe absent : passer -v "IAS_PASSWORD: Secret:<motdepasse>".


*** Test Cases ***
Le Formulaire Servi Est Bien Celui D Un IAS
    [Documentation]    Avant de s'authentifier, constater où l'on a atterri :
    ...    la redirection doit mener au point d'autorisation OAuth2 du tenant.
    ...    Sans ce constat, un test de login vert ne prouverait pas qu'un IDP
    ...    est intervenu.
    La Cible Et Les Identifiants Sont Fournis
    New Browser    chromium    headless=${HEADLESS}
    Ouvrir Le Launchpad Non Authentifie
    ${url}=    Get Url
    Should Contain    ${url}    /oauth2/authorize
    ...    msg=Pas de redirection vers un point d'autorisation : la cible n'est pas protégée par un IDP.
    Get Element States    input[name="j_username"]    contains    visible
    ...    message=Le champ d'identifiant du preset sap-ias est absent du formulaire réel.

Le Login Reel Atterrit Sur Le Shell Du Launchpad
    [Documentation]    Le scénario nominal. La preuve d'atterrissage n'est pas
    ...    l'absence d'erreur mais la PRÉSENCE du shell : un runtime UI5 et des
    ...    contrôles rendus sur la page d'accueil du launchpad.
    Ouvrir Le Launchpad Non Authentifie
    Log In Via Identity Provider    ${IAS_USER}    ${IAS_PASSWORD}    preset=sap-ias
    # Le keyword rend la main dès le formulaire soumis : la destination charge
    # encore. Sa docstring le dit, et l'oublier fait échouer l'assertion
    # suivante sur un login pourtant réussi.
    Wait For UI5 Ready
    ${present}=    Ui5 Runtime Is Present
    Should Be True    ${present}
    ...    msg=Pas de runtime UI5 après login : l'atterrissage n'est pas le launchpad.
    # Constaté live : sur un cFLP, « UI5 prêt » peut être vrai alors que le
    # shell n'a encore construit AUCUN contrôle. Le runtime est chargé, rien
    # n'est busy, et pourtant la page est vide. Une fixture rend tout d'un coup
    # et ne montre jamais cet état intermédiaire. On attend donc le repos RÉEL
    # (requêtes en vol comprises), puis on vérifie la propriété elle-même.
    Wait For Ui5 Idle
    Wait Until Keyword Succeeds    60s    2s    Le Shell A Rendu Ses Controles

Une Identite Inconnue Echoue En Nommant Le Formulaire
    [Documentation]    Le chemin d'échec, éprouvé SANS risquer le verrouillage
    ...    d'un compte réel : l'identité n'existe pas, donc l'IAS la refuse à
    ...    l'identification. Le keyword doit échouer tôt en disant qu'on est
    ...    resté sur le formulaire, plutôt que de laisser un timeout muet
    ...    survenir plus loin dans l'application.
    Ouvrir Le Launchpad Non Authentifie
    Run Keyword And Expect Error    *formulaire IDP*
    ...    Log In Via Identity Provider    ${IAS_INCONNU}    mot-de-passe-sans-objet
    ...    preset=sap-ias    timeout=20s

Un Mauvais Mot De Passe Sur Un Compte Existant Echoue Aussi
    [Documentation]    Distinct du scénario précédent, et pas par excès de zèle :
    ...    l'IAS refuse ici à l'**authentification**, alors que l'identité
    ...    inconnue est refusée à l'**identification**. Ce sont deux étapes
    ...    différentes du même formulaire, et rien ne garantit qu'elles
    ...    produisent le même écran ni le même message. Notre keyword les traite
    ...    aujourd'hui de façon identique, en constatant qu'on est resté sur le
    ...    formulaire : ce test vérifie que c'est vrai des DEUX côtés sur un
    ...    tenant authentique.
    ...
    ...    Le compte utilisé est **dédié au test**, sans rôle et sans usage
    ...    ailleurs : un verrouillage éventuel n'a aucune conséquence. C'est
    ...    précisément pourquoi il existe, et pourquoi ce scénario ne vise pas
    ...    le compte de travail.
    ...
    ...    Aucun mot de passe réel n'est nécessaire ici : le test en fournit un
    ...    faux à dessein.
    [Tags]    compte_dedie
    Should Not Be Empty    ${IAS_TEST_USER}
    ...    msg=Compte de test absent : passer -v IAS_TEST_USER:<utilisateur dédié du tenant>.
    Ouvrir Le Launchpad Non Authentifie
    Run Keyword And Expect Error    *formulaire IDP*
    ...    Log In Via Identity Provider    ${IAS_TEST_USER}    mot-de-passe-volontairement-faux
    ...    preset=sap-ias    timeout=20s

Un Preset Inconnu Est Refuse Avant Toute Frappe
    [Documentation]    Jamais de repli silencieux vers ``generic``. Vérifié ici
    ...    aussi contre la cible réelle : le refus doit intervenir AVANT que
    ...    quoi que ce soit ne soit saisi dans un formulaire de production.
    Ouvrir Le Launchpad Non Authentifie
    Run Keyword And Expect Error    *Preset IDP inconnu*
    ...    Log In Via Identity Provider    ${IAS_USER}    ${IAS_PASSWORD}    preset=okta
