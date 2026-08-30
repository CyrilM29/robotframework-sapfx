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
...                 Vocabulaire du **canal API d'une cible SAP Build Work Zone**
...                 (BTP / Cloud Foundry, derrière un tenant SAP Cloud Identity
...                 Services). Le pendant « sans écran » des page objects
...                 `workzone_*` : mêmes conventions, même cible, mais le canal
...                 est HTTP et non un navigateur.
...
...                 Relevé live le 2026-08-26 (voir
...                 `specs/workzone-canal-api-btp.md`). Ce que la campagne
...                 au-dessus vérifie est une **cartographie**, pas une fonction
...                 métier : la cible n'expose aucune donnée métier par ce canal,
...                 et le plan interdit explicitement d'en fabriquer une.
...
...                 Contrat de localisation, quatre règles apprises sur la cible :
...
...                 1. **Quatre hôtes, quatre rôles distincts** : le backend du
...                 service (que la clé de service ouvre), le site d'exécution,
...                 l'hôte d'administration du site, et le fournisseur
...                 d'identité. Ils n'obéissent PAS aux mêmes règles
...                 d'authentification, et les confondre fait chercher un défaut
...                 d'autorisation là où il y a une différence de nature.
...                 2. **Un `404` de Cloud Foundry dit trois choses** selon la
...                 couche qui répond. Le discriminant retenu est l'en-tête
...                 technique `x-cf-routererror`, jamais le texte du corps
...                 (convention 3).
...                 3. **Toute sonde s'accompagne d'un témoin absurde** sur le
...                 même hôte : sans lui, on ne sait pas si un `404` qualifie la
...                 ressource ou l'hôte entier.
...                 4. **Aucune valeur de cible n'est écrite ici** : hôtes et
...                 identifiants entrent par la ligne de commande, ou à défaut
...                 par les variables d'environnement du poste (convention 11).
...                 Un identifiant de client XSUAA désigne un tenant précis :
...                 il est traité comme un secret, au même titre que le secret.

Library             SapApiLibrary
Library             Collections
Library             String
Library             OperatingSystem


*** Variables ***
# --- Cible et identité : jamais de valeur committée (convention 11) ----------
# Vides par défaut ; `Resoudre La Cible Du Canal` complète depuis les variables
# d'environnement du poste quand la ligne de commande ne les fournit pas.
${WZ_API_BASE}                      ${EMPTY}    # backend du service (clé de service)
${WZ_TOKEN_URL}                     ${EMPTY}    # serveur d'autorisation XSUAA du sous-compte
${WZ_CLIENT_ID}                     ${EMPTY}
${WZ_CLIENT_SECRET}                 ${EMPTY}
${WZ_SITE_URL}                      ${EMPTY}    # site d'exécution (le launchpad)
${WZ_ADMIN_URL}                     ${EMPTY}    # hôte d'administration du site
${WZ_IDP_URL}                       ${EMPTY}    # tenant du fournisseur d'identité

# --- Repli sur l'environnement du poste --------------------------------------
# UN préfixe, quatre suffixes fixes (`API_URL`, `TOKEN_URL`, `CLIENT_ID`,
# `CLIENT_SECRET`) : la clé de service arrive d'un bloc, ses quatre valeurs
# vivent sous le même préfixe. Un préfixe plutôt que quatre noms complets
# évite aussi qu'une variable de ce fichier PORTE le mot « secret » sans en
# être un, ce que le garde anti-identifiants signale à juste titre.
${WZ_ENV_PREFIXE}                   SAPFX_WZ_

# --- Alias de session, un par hôte : leurs règles d'auth diffèrent -----------
${WZ_ALIAS_BACKEND}                 wz_backend
${WZ_ALIAS_ADMIN}                   wz_admin
${WZ_ALIAS_IDP}                     wz_idp

# --- Chemins relevés live, jamais devinés (2026-08-26) ----------------------
# Les préfixes du backend sont DÉCLARÉS par la clé de service elle-même : cette
# liste en est la transcription, pas un balayage de noms plausibles.
${WZ_PATH_GRAPHQL}                  /cep-runtime/graphql
${WZ_PATH_NAVIGATION}               /navigation
${WZ_PATH_ODATA}                    /odata
${WZ_PATH_ABSURDE}                  /chemin-volontairement-absent-temoin
${WZ_PATH_IDP_SCIM}                 /scim/Users
${WZ_PATH_IDP_DISCOVERY}            /.well-known/openid-configuration

# En-tête du routeur de la plateforme : le discriminant STRUCTUREL d'un 404
# qui qualifie l'HÔTE et non la ressource. Le corps porte le même sens en
# toutes lettres, mais un texte ne s'asserte pas (convention 3).
# La bibliothèque en fait le même usage (`ROUTER_ERROR_HEADER` de
# `sapfx_common.gateway_status`, derrière `Classify Http Response`) ; le nom
# reste ici parce qu'un scénario l'ASSERTE directement dans les en-têtes reçus.
${WZ_HEADER_ROUTER_ERROR}           x-cf-routererror


*** Keywords ***
# --- Cible, identifiants, ouverture et fermeture -----------------------------

Resoudre La Cible Du Canal
    [Documentation]    Complète les variables de cible restées vides avec les
    ...    variables d'environnement du poste. La ligne de commande reste
    ...    prioritaire ; l'environnement n'est qu'un confort de poste
    ...    provisionné. Aucune valeur n'est journalisée.
    ${base}=    Resoudre Une Valeur    ${WZ_API_BASE}    ${WZ_ENV_PREFIXE}API_URL
    ${token}=    Resoudre Une Valeur    ${WZ_TOKEN_URL}    ${WZ_ENV_PREFIXE}TOKEN_URL
    ${id}=    Resoudre Une Valeur    ${WZ_CLIENT_ID}    ${WZ_ENV_PREFIXE}CLIENT_ID
    ${secret}=    Resoudre Une Valeur    ${WZ_CLIENT_SECRET}    ${WZ_ENV_PREFIXE}CLIENT_SECRET
    Set Suite Variable    ${WZ_API_BASE}    ${base}
    Set Suite Variable    ${WZ_TOKEN_URL}    ${token}
    Set Suite Variable    ${WZ_CLIENT_ID}    ${id}
    Set Suite Variable    ${WZ_CLIENT_SECRET}    ${secret}

Resoudre Une Valeur
    [Documentation]    Valeur de ligne de commande si elle est fournie, sinon
    ...    la variable d'environnement nommée, sinon vide.
    [Arguments]    ${valeur}    ${nom_env}
    IF    $valeur
        RETURN    ${valeur}
    END
    ${depuis_env}=    Get Environment Variable    ${nom_env}    ${EMPTY}
    RETURN    ${depuis_env}

Les Identifiants Du Backend Sont Fournis
    [Documentation]    Garde de préflight. Ne MESURE jamais le secret : un
    ...    `Secret` refuse `Should Not Be Empty` par « Could not get length of
    ...    '<secret>' », et l'erreur de garde masquerait la vraie cause (piège
    ...    déjà encodé dans `api_keywords.resource`). On teste donc la
    ...    présence par une condition d'expression, pas par une longueur.
    ${manquants}=    Create List
    IF    not $WZ_API_BASE    Append To List    ${manquants}    ${WZ_ENV_PREFIXE}API_URL
    IF    not $WZ_TOKEN_URL    Append To List    ${manquants}    ${WZ_ENV_PREFIXE}TOKEN_URL
    IF    not $WZ_CLIENT_ID    Append To List    ${manquants}    ${WZ_ENV_PREFIXE}CLIENT_ID
    IF    not $WZ_CLIENT_SECRET    Append To List    ${manquants}    ${WZ_ENV_PREFIXE}CLIENT_SECRET
    ${liste}=    Catenate    SEPARATOR=,${SPACE}    @{manquants}
    Should Be Empty    ${manquants}
    ...    msg=Clé de service incomplète. Manquent : ${liste}. Les fournir en ligne de commande (-v WZ_CLIENT_SECRET:"Secret:...") ou par les variables d'environnement du poste.

Ouvrir Le Canal Backend
    [Documentation]    Ouvre la session OAuth2 client credentials vers le
    ...    backend du service. C'est le point d'entrée que la clé de service
    ...    a rendu possible : avant elle, cette ouverture échouait sur
    ...    `invalid_client`.
    Les Identifiants Du Backend Sont Fournis
    Open Api Session    ${WZ_API_BASE}
    ...    alias=${WZ_ALIAS_BACKEND}
    ...    token_url=${WZ_TOKEN_URL}
    ...    client_id=${WZ_CLIENT_ID}
    ...    client_secret=${WZ_CLIENT_SECRET}
    RETURN    ${WZ_ALIAS_BACKEND}

Ouvrir Le Canal Vers Un Hote Sans Authentification
    [Documentation]    Ouvre une session NUE vers un hôte (site, administration
    ...    ou fournisseur d'identité) : aucun identifiant, puisque l'objet est
    ...    précisément d'observer ce que l'hôte répond à un anonyme.
    [Arguments]    ${url}    ${alias}
    Should Not Be Empty    ${url}
    ...    msg=Hôte non fourni pour l'alias ${alias} : le passer en ligne de commande (convention 11, aucune URL de cible n'est committée).
    Open Api Session    ${url}    alias=${alias}
    RETURN    ${alias}

Fermer Le Canal
    [Documentation]    Ferme TOUTES les sessions du namespace et vérifie que le
    ...    registre est bien vide. Une session laissée ouverte est une session
    ...    utilisateur restée ouverte côté serveur ; le constat vaut mieux que
    ...    la supposition.
    Close All Api Sessions
    ${etat}=    List Api Sessions
    Should Be Empty    ${etat}[api_sessions]
    ...    msg=Des sessions API survivent à la fermeture : ${etat}[api_sessions]

# --- Perception du canal ------------------------------------------------------

Lire L Etat Du Canal
    [Documentation]    État JSON-safe du canal (alias, base, authentifié) tel
    ...    qu'il est servi aux agents. Jamais d'identifiant dedans : c'est ce
    ...    que `Api Channel State Should Not Leak Credentials` vérifie.
    ${etat}=    List Api Sessions
    RETURN    ${etat}

La Session Porte Une Authentification Oauth2
    [Documentation]    Le témoin d'ouverture réussie : la session déclare son
    ...    mode OAuth2. C'est une propriété de l'ÉTAT, pas une supposition
    ...    tirée de l'absence d'erreur.
    [Arguments]    ${alias}=${WZ_ALIAS_BACKEND}
    ${etat}=    List Api Sessions
    ${sessions}=    Evaluate    [s for s in $etat['api_sessions'] if s['alias'] == $alias]
    Should Not Be Empty    ${sessions}    msg=Aucune session d'alias ${alias} dans l'état du canal.
    Should Be True    ${sessions}[0][oauth]
    ...    msg=La session ${alias} n'est pas en OAuth2 : ${sessions}[0]
    RETURN    ${sessions}[0]

Sonder Un Chemin
    [Documentation]    Lecture brute et tolérante d'un chemin : retourne le
    ...    dict `{status, headers, body, truncated, error, url}` sans jamais
    ...    lever. C'est la primitive de reconnaissance ; elle consigne et
    ...    poursuit là où une lecture OData s'arrêterait au premier refus.
    [Arguments]    ${chemin}    ${alias}=${WZ_ALIAS_BACKEND}    ${max_chars}=4000
    ${reponse}=    Get Http Response    ${chemin}    alias=${alias}    max_chars=${max_chars}
    RETURN    ${reponse}

# --- Classement des refus (le cœur de la campagne) ---------------------------

Classer La Reponse
    [Documentation]    Range une réponse dans l'une des familles relevées live
    ...    sur cette cible, par des critères STRUCTURELS :
    ...
    ...    - `route_inconnue` : 404 portant l'en-tête du routeur de plateforme,
    ...    le préfixe n'est routé vers AUCUNE application ;
    ...    - `route_absente` : 404 SANS cet en-tête, une application a répondu,
    ...    donc le préfixe est routé mais cette route n'existe pas ;
    ...    - `autorisation_refusee` : 403, la route existe et l'autorisation
    ...    refuse ;
    ...    - `dialogue` : 4xx porteur d'un corps JSON, l'application traite la
    ...    requête et explique ce qui lui manque ;
    ...    - `page_de_connexion` : 2xx dont le corps est du HTML, la réponse
    ...    n'est pas une donnée (le « vert et faux » de cette famille de
    ...    cibles) ;
    ...    - `donnee` : 2xx qui n'est pas du HTML ;
    ...    - `injoignable` : aucune réponse.
    ...
    ...    La classification elle-même est une CAPACITÉ (statut, en-tête
    ...    technique du routeur, forme du corps) : elle vit dans la
    ...    bibliothèque (`Classify Http Response`, convention #12). Ce
    ...    keyword n'en garde que la traduction vers le vocabulaire français
    ...    de la campagne.
    [Arguments]    ${reponse}
    ${famille}=    Classify Http Response    ${reponse}
    ${traduction}=    Create Dictionary
    ...    unreachable=injoignable    unknown_route=route_inconnue
    ...    missing_route=route_absente    forbidden=autorisation_refusee
    ...    dialog=dialogue    login_page=page_de_connexion    data=donnee
    ...    other=autre
    ${francais}=    Get From Dictionary    ${traduction}    ${famille}    autre
    RETURN    ${francais}

Le Chemin Est Classe
    [Documentation]    Sonde un chemin et exige une famille précise. L'échec
    ...    nomme la famille obtenue ET le début du corps : sans cela, un
    ...    changement de la cible produirait un « attendu X, obtenu Y » sans
    ...    matière pour comprendre.
    [Arguments]    ${chemin}    ${attendu}    ${alias}=${WZ_ALIAS_BACKEND}
    ${reponse}=    Sonder Un Chemin    ${chemin}    alias=${alias}
    ${famille}=    Classer La Reponse    ${reponse}
    Should Be Equal    ${famille}    ${attendu}
    ...    msg=${chemin} (alias ${alias}) classé « ${famille} » au lieu de « ${attendu} » : statut ${reponse}[status], début du corps « ${reponse.get('body', '')[:120]} ».
    RETURN    ${reponse}

Le Temoin Absurde Etablit La Couche Qui Repond
    [Documentation]    Sonde un chemin volontairement absent et retourne sa
    ...    famille. C'est le préalable de toute interprétation : sans ce
    ...    témoin, on ne sait pas si un 404 qualifie la ressource ou l'hôte
    ...    entier. Méthode encodée plutôt que rappelée en commentaire.
    [Arguments]    ${alias}=${WZ_ALIAS_BACKEND}
    ${reponse}=    Sonder Un Chemin    ${WZ_PATH_ABSURDE}    alias=${alias}
    ${famille}=    Classer La Reponse    ${reponse}
    RETURN    ${famille}
