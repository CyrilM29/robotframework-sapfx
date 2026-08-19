*** Settings ***
Documentation       Mots-clés du canal **API** (OData v2 et v4) lisibles métier.
...                 Troisième miroir de `ecc_keywords.resource` et de
...                 `fiori_keywords.resource` : un test se lit de la même façon
...                 (`Open ...`, `Count ...`, `Close ...`) qu'il pilote le client
...                 lourd SAP GUI, l'interface web Fiori ou le canal sans écran.
...
...                 Table de correspondance des trois canaux (mêmes noms quand la
...                 sémantique coïncide) :
...                 | =ECC=                    | =Fiori=                | =API=                        |
...                 | Open SAP And Log In      | Open SAP And Log In    | Open Api Channel             |
...                 | Go To Transaction        | Open App               | (sans objet : pas d'écran)   |
...                 | Count Table Entries      | (sans objet)           | Count Business Entities      |
...                 | Read Grid                | Read Ui5 Table         | Read Business Entities       |
...                 | Close SAP                | Close SAP              | Close Api Channel            |
...                 Divergences assumées : le canal API n'a **pas d'écran**, donc rien
...                 n'y correspond à la navigation par transaction ou par tuile ; en
...                 revanche il est le seul des trois à offrir une **fabrique de
...                 données** réversible (`Create Test Entity` /
...                 `Remove Created Test Data`), le patron recommandé pour préparer un
...                 jeu de test sans piloter un écran.
...
...                 Convention 1 : aucune suite ne cite un chemin de service OData.
...                 Les chemins vivent ici, sous des noms métier (`${EPM_PRODUCTS}`,
...                 `${TRAVEL_ENTITIES}`), comme les ids SAP vivent dans
...                 `ecc_keywords.resource`. Convention 3 : les assertions portent sur
...                 des comptes et des statuts, jamais sur un message localisé.

Library             SapApiLibrary
Library             Collections


*** Variables ***
# --- Connexion (renseignée par la suite ou en ligne de commande) ---
${API_BASE_URL}             ${EMPTY}
${API_USER}                 ${EMPTY}
${API_PASSWORD}             ${EMPTY}    # `Secret:` en ligne de commande : jamais en clair
${API_CLIENT}               ${EMPTY}
${API_ALIAS}                default

# --- Cibles métier : Gateway OData v2 embarquée (modèle EPM du référentiel A4H) ---
# Le service « Shop » projette les mêmes tables que SE16 côté GUI : c'est ce qui
# rend le recoupement cross-canal possible.
${EPM_SHOP_SERVICE}         /sap/opu/odata/sap/SEPMRA_SHOP
${EPM_PRODUCTS}             /sap/opu/odata/sap/SEPMRA_SHOP/Products

# --- Cibles métier : service OData v4 (modèle Travel de cap-sflight) ---
${TRAVEL_SERVICE}           /processor
${TRAVEL_ENTITIES}          /processor/Travel


*** Keywords ***
Open Api Channel
    [Documentation]    Ouvre le canal API et le déclare utilisable. Miroir de
    ...    `Open SAP And Log In` : un test n'a pas à savoir qu'une session porte
    ...    des cookies, un client SAP et un alias. Le mot de passe traverse en
    ...    type `Secret` quand l'appelant en fournit un, donc n'apparaît nulle
    ...    part, pas même en TRACE.
    [Arguments]    ${base_url}=${API_BASE_URL}    ${user}=${API_USER}
    ...    ${password}=${API_PASSWORD}    ${client}=${API_CLIENT}
    ...    ${alias}=${API_ALIAS}
    Open Api Session    ${base_url}    user=${user}    password=${password}
    ...    sap_client=${client}    alias=${alias}

Api Credentials Should Be Provided
    [Documentation]    Vérifie qu'un mot de passe a bien été fourni, SANS jamais
    ...    en lire la valeur. Un mot de passe passé en type `Secret` (la forme
    ...    recommandée) refuse d'être mesuré : `Should Not Be Empty` échoue
    ...    dessus par « Could not get length of '<secret>' », ce qui masquerait
    ...    la vraie cause derrière une erreur de garde. On teste donc la seule
    ...    chose observable sans le déballer : une valeur non fournie est restée
    ...    la chaîne vide du défaut.
    [Arguments]    ${password}
    ${fourni}=    Evaluate    not isinstance($password, str) or bool($password)
    Should Be True    ${fourni}
    ...    msg=Aucun mot de passe fourni : passer -v "API_PASSWORD: Secret:<motdepasse>".

Close Api Channel
    [Documentation]    Ferme TOUTES les sessions du canal, connexions RFC
    ...    comprises. Miroir de `Close SAP`, et même exigence d'hygiène : une
    ...    connexion RFC orpheline est une session utilisateur restée ouverte
    ...    côté serveur. À appeler en Suite Teardown, donc même sur échec.
    Close All Api Sessions

Api Channel Should Be Available
    [Documentation]    Préflight du canal, à poser AVANT la première lecture :
    ...    une Gateway inactive est diagnostiquée ici, avec sa remédiation
    ...    nommée, au lieu de faire échouer un scénario métier plus loin sur une
    ...    erreur incompréhensible.
    [Arguments]    ${alias}=${API_ALIAS}
    Gateway Should Be Active    alias=${alias}

Wait Until Api Channel Is Available
    [Documentation]    Même préflight, mais patient : pour un système qui
    ...    redémarre (conteneur relancé, Gateway en cours d'activation). Jamais
    ...    de `Sleep` dans une suite : c'est ce keyword qui attend.
    [Arguments]    ${alias}=${API_ALIAS}    ${timeout}=2m
    Wait Until Api Available    alias=${alias}    timeout=${timeout}

List Available Business Services
    [Documentation]    Perception du canal : ce que le système expose vraiment,
    ...    au lieu de le supposer. L'équivalent API du `Get Screen Signature`
    ...    de l'ECC.
    [Arguments]    ${alias}=${API_ALIAS}
    ${services}=    List Odata Services    alias=${alias}
    RETURN    ${services}

Business Service Should Expose Entity Set
    [Documentation]    Vérifie au `$metadata` qu'un service publie bien
    ...    l'ensemble d'entités attendu, et retourne sa description (clés et
    ...    propriétés). Contrat de service vérifié à la source, pas deviné.
    [Arguments]    ${service}    ${entity_set}    ${alias}=${API_ALIAS}
    ${meta}=    Get Odata Metadata    ${service}    alias=${alias}
    Dictionary Should Contain Key    ${meta}[entity_sets]    ${entity_set}
    ...    msg=Le service ${service} ne publie pas l'ensemble d'entités ${entity_set}.
    RETURN    ${meta}[entity_sets][${entity_set}]

Find Business Field By Label
    [Documentation]    Localisateur « libellé humain » du canal API : le pendant
    ...    sans écran de `Find Element By Label`. Tous les candidats sont
    ...    retournés, l'ambiguïté n'est jamais tranchée en silence.
    [Arguments]    ${service}    ${label}    ${alias}=${API_ALIAS}
    ${hits}=    Find Odata Property By Label    ${service}    ${label}    alias=${alias}
    RETURN    ${hits}

Count Business Entities
    [Documentation]    Le nombre d'entités d'un ensemble. Miroir exact du
    ...    `Count Table Entries` de l'ECC, et c'est cette symétrie qui permet de
    ...    recouper un même fait métier par deux canaux indépendants.
    [Arguments]    ${entity_set}    ${alias}=${API_ALIAS}
    ${count}=    Get Odata Count    ${entity_set}    alias=${alias}
    RETURN    ${count}

Read Business Entities
    [Documentation]    Lecture bornée et projetée (miroir de `Read Grid`) : on
    ...    ne rapatrie que les champs utiles au scénario, jamais l'entité
    ...    entière par confort.
    [Arguments]    ${entity_set}    ${fields}    ${limit}=5    ${alias}=${API_ALIAS}
    ${rows}=    Get Odata Entities    ${entity_set}    alias=${alias}
    ...    top=${limit}    select=${fields}
    RETURN    ${rows}

Read All Business Entities
    [Documentation]    Lecture complète en suivant la pagination servie par le
    ...    serveur. `max_pages` borne délibérément la moisson : une troncature
    ...    silencieuse serait un « vert et faux ».
    [Arguments]    ${entity_set}    ${fields}    ${max_pages}=10    ${alias}=${API_ALIAS}
    ${rows}=    Get Odata Entities    ${entity_set}    alias=${alias}
    ...    select=${fields}    follow_next=${True}    max_pages=${max_pages}
    RETURN    ${rows}

Read Business Entities In One Roundtrip
    [Documentation]    Plusieurs lectures indépendantes en UN aller-retour
    ...    (`$batch`). Utile quand un scénario recoupe plusieurs ensembles :
    ...    autant de latence réseau économisée, et un seul point de défaillance.
    ...    `paths` : liste de chemins RELATIFS au service.
    [Arguments]    ${service}    @{paths}    ${alias}=${API_ALIAS}
    @{operations}=    Create List
    FOR    ${path}    IN    @{paths}
        ${operation}=    Create Dictionary    method=GET    path=${path}
        Append To List    ${operations}    ${operation}
    END
    ${responses}=    Post Odata Batch    ${service}    ${operations}    alias=${alias}
    RETURN    ${responses}

Create Test Entity
    [Documentation]    Fabrique de données : crée une entité et la fait suivre
    ...    pour le nettoyage. C'est le patron recommandé (préparer les données
    ...    par l'API, ne piloter l'écran que pour ce qu'on teste vraiment).
    ...
    ...    Le suivi automatique s'appuie sur l'URI que le SERVEUR annonce. Quand
    ...    cette URI n'est pas adressable (un service v4 draft-enabled répond
    ...    par son entité de stockage interne), passer le chemin réel à
    ...    `Track Created Entity` : le nettoyage reste garanti.
    [Arguments]    ${entity_set}    ${payload}    ${alias}=${API_ALIAS}
    ...    ${track}=${True}
    ${entity}=    Post Odata    ${entity_set}    ${payload}    alias=${alias}    track=${track}
    RETURN    ${entity}

Draft Entity Path
    [Documentation]    Chemin adressable d'un brouillon sur un service OData v4
    ...    draft-enabled. La clé y est COMPOSITE : l'identifiant seul ne
    ...    désigne rien, il faut lui adjoindre l'état actif ou brouillon. Un
    ...    brouillon n'apparaît d'ailleurs ni dans le `$count` ni dans une
    ...    lecture ordinaire, qui ne rendent que les entités actives : c'est
    ...    pourquoi un compte inchangé ne prouve à lui seul aucun nettoyage.
    [Arguments]    ${entity_set}    ${key_field}    ${key_value}    ${active}=false
    RETURN    ${entity_set}(${key_field}=${key_value},IsActiveEntity=${active})

Track Created Entity
    [Documentation]    Déclare le chemin réel d'une entité à supprimer en
    ...    teardown, quand le serveur n'en a pas annoncé un qui réponde.
    [Arguments]    ${entity_path}    ${alias}=${API_ALIAS}
    Register Created Entity    ${entity_path}    alias=${alias}

Remove Created Test Data
    [Documentation]    Teardown de la fabrique : supprime tout ce que la suite a
    ...    créé, en ordre inverse. `strict=True` par défaut ICI (le contrat de
    ...    la bibliothèque est best-effort) : une donnée de test laissée dans un
    ...    système partagé pollue les runs suivants, donc le silence n'est pas
    ...    une option.
    [Arguments]    ${alias}=${API_ALIAS}    ${strict}=${True}
    ${report}=    Delete Created Entities    alias=${alias}    strict=${strict}
    RETURN    ${report}

Api Channel Should Show Activity
    [Documentation]    Garde-fou de recette : la télémétrie prouve que les
    ...    lectures ont bien traversé le réseau. Sans elle, une suite dont
    ...    toutes les réponses viendraient d'un cache passerait au vert sans
    ...    avoir rien vérifié.
    [Arguments]    ${alias}=${API_ALIAS}
    ${telemetry}=    Get Api Telemetry    alias=${alias}
    Should Be True    ${telemetry}[requests] > 0
    ...    msg=Aucune requête comptée sur le canal : rien n'a été vérifié réellement.
    RETURN    ${telemetry}

Api Channel State Should Not Leak Credentials
    [Documentation]    L'état du canal est servi aux agents (rf-mcp) à chaque
    ...    tour : il ne doit JAMAIS transporter d'identifiants. Ce keyword le
    ...    vérifie sur l'état réellement exposé, pas sur l'intention.
    ${state}=    List Api Sessions
    ${dump}=    Evaluate    str($state).lower()
    Should Not Contain    ${dump}    authorization
    ...    msg=Fuite : un en-tête d'authentification apparaît dans l'état du canal.
    Should Not Contain    ${dump}    password
    ...    msg=Fuite : un mot de passe apparaît dans l'état du canal.
    RETURN    ${state}
