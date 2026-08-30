*** Settings ***
Documentation       Reconnaissance du canal API d'une cible SAP Build Work Zone (BTP).
...                 Spec: specs/workzone-canal-api-btp.md (sha256:79c29a9d95c6, 2026-08-26)
...                 Générée depuis `specs/workzone-canal-api-btp.md` : rejouer la
...                 génération plutôt que de corriger des localisateurs ici.
...
...                 Cible : un site SAP Build Work Zone sur Cloud Foundry,
...                 derrière un tenant SAP Cloud Identity Services.
...
...                 Ce n'est PAS une recette fonctionnelle, et le plan interdit
...                 d'en faire une : cette cible n'expose aucune donnée métier
...                 par ce canal. Ce que la campagne verrouille est une
...                 **cartographie** : quel hôte obéit à quelle règle
...                 d'authentification, et comment se distinguent les refus.
...
...                 Sa valeur est étroite mais réelle. Elle empêche une suite
...                 BTP d'être écrite sur un `200` trompeur (toute route
...                 déclarée du site répond 200 avec une page de connexion,
...                 jamais un défi d'authentification), elle surveille la
...                 chaîne d'authentification du sous-compte, et elle prouve
...                 jeton en main ce que la première passe ne pouvait que
...                 supposer : une clé de service ouvre le backend d'un
...                 service, pas l'interface d'administration devant lui.
...
...                 LECTURE SEULE : aucune écriture, ni sur le site ni sur son
...                 administration.
...
...                 Cible et identifiants par la ligne de commande, ou par les
...                 variables d'environnement du poste (convention 11) :
...
...                 | robot --pythonpath src -v WZ_SITE_URL:<site> |
...                 | ... -v WZ_ADMIN_URL:<administration> -v WZ_IDP_URL:<tenant> |
...                 | ... tests/robot/api/reconnaissance_canal_btp.robot |
...
...                 Relevé et validé live le 2026-08-26.

Resource            ../../../resources/page_objects/workzone_api.resource

Suite Setup         Preparer Le Canal
Suite Teardown      Fermer Le Canal

Test Tags           api    workzone    btp    live    reconnaissance


*** Test Cases ***
La cle de service ouvre le canal en OAuth2
    [Documentation]    Scénario 7 du plan, dans son cas NOMINAL. Sa première
    ...    version constatait un `invalid_client` : c'était la frontière. Une
    ...    clé de service ayant été provisionnée, ce refus n'est plus le sujet,
    ...    et l'ouverture devient le point d'entrée du canal.
    ...
    ...    Le témoin est une propriété de l'ÉTAT servi (`oauth`), pas l'absence
    ...    d'erreur à l'ouverture : une session peut exister sans avoir
    ...    négocié quoi que ce soit.
    ${session}=    La Session Porte Une Authentification Oauth2
    Should Be Equal    ${session}[alias]    ${WZ_ALIAS_BACKEND}
    Should Be True    ${session}[authenticated] or ${session}[oauth]

L etat du canal ne transporte aucun identifiant
    [Documentation]    L'état est servi aux agents à chaque tour : il ne doit
    ...    jamais porter d'identifiant. L'oracle exige de la matière (au moins
    ...    une session ouverte) : un état vide ne prouverait rien, et c'est
    ...    exactement le défaut corrigé dans la resource générique le même jour.
    ${etat}=    Lire L Etat Du Canal
    Should Not Be Empty    ${etat}[api_sessions]
    ${dump}=    Evaluate    str($etat).lower()
    Should Not Contain    ${dump}    authorization
    Should Not Contain    ${dump}    client_secret
    Should Not Contain    ${dump}    bearer

Le temoin absurde etablit la couche qui repond
    [Documentation]    Le préalable de toute interprétation, et la raison
    ...    d'être de ce test : sur cette plateforme un `404` dit trois choses
    ...    différentes selon la couche qui répond. Sans témoin, on ne sait pas
    ...    si un 404 qualifie la ressource ou l'hôte entier.
    ...
    ...    Sur le backend, un chemin absurde à la racine n'est routé vers
    ...    aucune application : c'est le routeur de la plateforme qui répond,
    ...    reconnaissable à son en-tête technique et non à son texte.
    ${famille}=    Le Temoin Absurde Etablit La Couche Qui Repond
    # Distinguer « la cible ne répond pas » de « elle répond autre chose » :
    # sans ce garde, une base_url erronée sort en « injoignable != route_inconnue »,
    # message qui ressemble à une dérive de la cible alors que rien n'a été atteint.
    Should Not Be Equal    ${famille}    injoignable
    ...    msg=Le backend n'a pas répondu du tout (base ${WZ_API_BASE}) : vérifier l'URL du service et la connectivité avant d'interpréter quoi que ce soit.
    Should Be Equal    ${famille}    route_inconnue
    ${reponse}=    Sonder Un Chemin    ${WZ_PATH_ABSURDE}
    Should Be Equal As Integers    ${reponse}[status]    404
    ${entetes}=    Evaluate    [k.lower() for k in $reponse['headers']]
    Should Contain    ${entetes}    ${WZ_HEADER_ROUTER_ERROR}

Les refus du backend se distinguent famille par famille
    [Documentation]    Le cœur de la cartographie. Trois chemins DÉCLARÉS par
    ...    la clé de service, trois comportements distincts, chacun asserté sur
    ...    un critère structurel :
    ...
    ...    - la route GraphQL accepte le jeton et DIALOGUE (elle explique ce
    ...    qui manque à la requête) : c'est la seule qui traite la demande ;
    ...    - la route de navigation existe et son autorisation refuse ;
    ...    - le préfixe OData est routé, mais n'expose aucune route publique.
    ...
    ...    Un scope large ne rend donc pas les routes accessibles : jeton
    ...    valide et route autorisée sont deux questions séparées.
    Le Chemin Est Classe    ${WZ_PATH_GRAPHQL}    dialogue
    Le Chemin Est Classe    ${WZ_PATH_NAVIGATION}    autorisation_refusee
    ${odata}=    Sonder Un Chemin    ${WZ_PATH_ODATA}
    ${famille}=    Classer La Reponse    ${odata}
    Should Be True    $famille in ('route_absente', 'route_inconnue')
    ...    msg=Le préfixe OData est classé « ${famille} » : statut ${odata}[status].

La route qui dialogue refuse pour une raison qui n est pas l authentification
    [Documentation]    La distinction qui change une conclusion. Le refus de
    ...    la route GraphQL porte sur le CONTENU de la requête, pas sur
    ...    l'identité de l'appelant : le jeton est donc bien accepté à cet
    ...    endroit. Lire ce 400 comme un échec d'authentification ferait
    ...    chercher un défaut d'identifiants là où il n'y en a pas.
    ${reponse}=    Sonder Un Chemin    ${WZ_PATH_GRAPHQL}
    Should Be Equal As Integers    ${reponse}[status]    400
    # Auto-import Robot du module `json` : ni __import__ ni modules= dans une
    # suite (décision DDIC 2026-08-17, tenue par check_conventions.py).
    ${charge}=    Evaluate    json.loads($reponse['body'])
    Should Contain    ${charge}    errors
    ${dump}=    Evaluate    str($charge).lower()
    Should Not Contain    ${dump}    unauthorized
    Should Not Contain    ${dump}    forbidden

L administration du site ignore un jeton porteur parfaitement valide
    [Documentation]    Le fait de conception que cette campagne peut enfin
    ...    PROUVER, jeton en main, là où la première passe ne pouvait que le
    ...    supposer : l'hôte d'administration répond `200` avec sa page de
    ...    connexion même présenté avec un `Authorization: Bearer` valide.
    ...
    ...    Il n'ignore pas un jeton invalide, il ignore le mécanisme entier,
    ...    parce qu'il attend une session du fournisseur d'identité et non un
    ...    jeton porteur. Conséquence transposable : une clé de service ouvre
    ...    le backend d'un service, pas l'interface d'administration qui vit
    ...    devant lui. Aucun identifiant supplémentaire ne changera cela.
    [Tags]    admin
    Skip If    not $WZ_ADMIN_URL    L'hôte d'administration n'a pas été fourni (-v WZ_ADMIN_URL:...).
    Ouvrir Le Canal Admin Avec Le Jeton Du Service
    ${reponse}=    Sonder Un Chemin    /    alias=${WZ_ALIAS_ADMIN}
    ${famille}=    Classer La Reponse    ${reponse}
    Should Be Equal    ${famille}    page_de_connexion
    ...    msg=L'administration a répondu « ${famille} » (statut ${reponse}[status]) : le comportement relevé le 2026-08-26 a changé, re-explorer avant de conclure.

Le fournisseur d identite repond par un vrai defi d authentification
    [Documentation]    Scénario 5 du plan. Le contraste est le sujet : sur la
    ...    même chaîne, l'hôte du site ne défie jamais (il sert une page) alors
    ...    que le fournisseur d'identité, lui, parle correctement HTTP. C'est
    ...    ce contraste qui rend la cartographie utilisable comme oracle.
    [Tags]    idp
    Skip If    not $WZ_IDP_URL    Le tenant d'identité n'a pas été fourni (-v WZ_IDP_URL:...).
    Ouvrir Le Canal Vers Un Hote Sans Authentification    ${WZ_IDP_URL}    ${WZ_ALIAS_IDP}
    ${scim}=    Sonder Un Chemin    ${WZ_PATH_IDP_SCIM}    alias=${WZ_ALIAS_IDP}
    Should Be Equal As Integers    ${scim}[status]    401
    ${decouverte}=    Sonder Un Chemin    ${WZ_PATH_IDP_DISCOVERY}    alias=${WZ_ALIAS_IDP}
    Should Be Equal As Integers    ${decouverte}[status]    200
    ${famille}=    Classer La Reponse    ${decouverte}
    Should Be Equal    ${famille}    donnee

Le preflight standard classe la cible sans se tromper de remede
    [Documentation]    Scénario 2 du plan, revisité. Le préflight du canal est
    ...    écrit pour une Gateway ABAP ; sur une cible BTP il ne doit pas
    ...    déclarer le canal opérationnel, ET son diagnostic doit nommer une
    ...    remédiation qui a du sens ici.
    ...
    ...    Avant le correctif du 2026-08-26, un `200` portant une page de
    ...    connexion était classé « catalogue joignable » : le vert et faux
    ...    type, sur une cible qui n'avait servi aucune donnée.
    [Tags]    admin
    Skip If    not $WZ_ADMIN_URL    L'hôte d'administration n'a pas été fourni (-v WZ_ADMIN_URL:...).
    # Sur son chemin par défaut, le préflight cherche un catalogue Gateway ABAP
    # qui n'existe évidemment pas ici : il le dit, et c'est déjà correct.
    ${catalogue}=    Get Gateway Status    alias=${WZ_ALIAS_ADMIN}
    Should Be Equal    ${catalogue}[status]    catalog_not_found
    # Sonder la RACINE est l'épreuve qui compte : c'est elle qui renvoie 200
    # avec une page de connexion, donc elle qui piégeait le classement.
    ${racine}=    Get Gateway Status    alias=${WZ_ALIAS_ADMIN}    catalog_path=/
    Should Not Be Equal    ${racine}[status]    ok
    ...    msg=Le préflight déclare la cible opérationnelle alors qu'elle ne sert aucune donnée : ${racine}
    Should Be Equal    ${racine}[status]    login_page
    Should Not Be Empty    ${racine}[remediation]

La telemetrie compte les sondes de reconnaissance
    [Documentation]    Une reconnaissance est faite de SONDES, et une sonde
    ...    traverse le réseau autant qu'une lecture. Avant le correctif du
    ...    2026-08-26, elles ne comptaient pas, donc le garde censé prouver que
    ...    le réseau avait été traversé échouait sur une reconnaissance
    ...    parfaitement légitime. Un refus consigné reste un résultat, jamais
    ...    une erreur du canal : `errors` doit rester à zéro.
    ${telemetrie}=    Get Api Telemetry    alias=${WZ_ALIAS_BACKEND}
    Should Be True    ${telemetrie}[requests] > 0
    ...    msg=Aucune requête comptée alors que la campagne a sondé le backend.
    Should Be Equal As Integers    ${telemetrie}[errors]    0
    ...    msg=Une sonde a été comptée comme erreur du canal : ${telemetrie}


*** Keywords ***
Preparer Le Canal
    [Documentation]    Résout la cible, ouvre le backend, et journalise la
    ...    cartographie de départ. Les hôtes du site, de l'administration et du
    ...    fournisseur d'identité sont optionnels : les tests qui en dépendent
    ...    se SAUTENT en le disant plutôt que d'échouer sur une cible partielle.
    Resoudre La Cible Du Canal
    Ouvrir Le Canal Backend

Ouvrir Le Canal Admin Avec Le Jeton Du Service
    [Documentation]    Ouvre vers l'hôte d'ADMINISTRATION une session portant
    ...    les mêmes identifiants de service que le backend : la bibliothèque
    ...    négocie le jeton et l'envoie en `Authorization: Bearer` d'elle-même.
    ...
    ...    C'est la façon propre de poser la question « cet hôte accepte-t-il un
    ...    jeton porteur valide ? » : aucun test n'a à extraire un jeton de
    ...    l'état interne d'une session pour le recoller à la main, et le jeton
    ...    ne traverse jamais le code de la campagne.
    Les Identifiants Du Backend Sont Fournis
    Open Api Session    ${WZ_ADMIN_URL}
    ...    alias=${WZ_ALIAS_ADMIN}
    ...    token_url=${WZ_TOKEN_URL}
    ...    client_id=${WZ_CLIENT_ID}
    ...    client_secret=${WZ_CLIENT_SECRET}
    La Session Porte Une Authentification Oauth2    ${WZ_ALIAS_ADMIN}
