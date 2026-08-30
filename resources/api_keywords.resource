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
...                 Mots-clés du canal **API** (OData v2 et v4) lisibles métier.
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
# Primitive pure atteinte par un KEYWORD (décision DDIC 2026-08-17) :
# `Secret Is Provided` teste la PRÉSENCE d'un identifiant sans jamais le lire.
Library             sapfx_common.secrets


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

# --- Cibles métier : modèle de voyage MODERNE servi par un serveur ABAP ---
# Relevé live (ABAP Platform 2023, 2026-08-28) sur le catalogue de la cible,
# jamais deviné : le système publie plusieurs services de voyage et ils ne
# projettent PAS la même population. Celui-ci est la variante sans brouillons,
# donc le seul dont le comptage égale celui de la table par le canal RFC ;
# les variantes à brouillons agrègent des états que la table ne porte pas.
#
# Piège mesuré à connaître avant tout croisement : l'ensemble des compagnies
# de ce service compte 16 lignes, celui du modèle de démonstration CLASSIQUE
# en compte 18. Ce sont DEUX catalogues, pas deux vues du même : les
# confondre fabrique un écart de deux lignes parfaitement reproductible.
${MODERN_TRAVEL_SERVICE}    /sap/opu/odata/dmo/UI_TRAVEL_U_V2
${MODERN_TRAVELS}           /sap/opu/odata/dmo/UI_TRAVEL_U_V2/Travel
${MODERN_AIRLINES}          /sap/opu/odata/dmo/UI_TRAVEL_U_V2/Airline

# --- Cibles métier : bac à sable SAP Business Accelerator Hub (api.sap.com) ---
# Troisième cible du canal, la seule qui expose la forme RÉELLE des APIs
# S/4HANA Cloud (ni Gateway A4H, ni CAP). Authentification par clé d'API en
# en-tête, pas de mandant : la clé se récupère sur api.sap.com, bouton
# « Show API Key », et se passe en `-v "API_KEY: Secret:<clé>"`.
${API_KEY}                  ${EMPTY}
${S4_SANDBOX_BASE}          https://sandbox.api.sap.com/s4hanacloud
# OData v2 sur le bac à sable.
${BUSINESS_PARTNER_SERVICE}    /sap/opu/odata/sap/API_BUSINESS_PARTNER
${BUSINESS_PARTNERS}        /sap/opu/odata/sap/API_BUSINESS_PARTNER/A_BusinessPartner
# OData v4 sur le bac à sable. Chemin RELEVÉ live (2026-08-23), jamais deviné :
# la forme `odata4/sap/<api>/srvd_a2x/sap/<définition>/0001` est propre à chaque
# API, et plusieurs candidats plausibles répondent 404 ou 403 « Unified
# Connectivity: Forbidden ». Celui-ci sert un edmx 4.0 de 13 entity sets.
${PURCHASE_ORDER_SERVICE}    /sap/opu/odata4/sap/api_purchaseorder_2/srvd_a2x/sap/purchaseorder/0001
${PURCHASE_ORDERS}          /sap/opu/odata4/sap/api_purchaseorder_2/srvd_a2x/sap/purchaseorder/0001/PurchaseOrder


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
    Api Base Url Should Be Provided    ${base_url}
    Open Api Session    ${base_url}    user=${user}    password=${password}
    ...    sap_client=${client}    alias=${alias}

Api Base Url Should Be Provided
    [Documentation]    Vérifie que la cible du canal API a bien été fournie.
    ...    Sans cette garde, une base vide n'échoue pas à l'ouverture : elle
    ...    échoue beaucoup plus tard, au premier appel, quand le chemin relatif
    ...    du service part comme une URL absolue et ressort en
    ...    `ValueError: unknown url type: '/sap/opu/odata/...'`. Ce message ne
    ...    nomme ni la cause ni le remède, et il désigne un chemin parfaitement
    ...    correct, ce qui envoie chercher au mauvais endroit.
    ...
    ...    Symétrique de `Api Credentials Should Be Provided` : le canal API a
    ...    deux prérequis fournis de l'extérieur, ils méritent deux refus
    ...    lisibles.
    [Arguments]    ${base_url}
    Should Not Be Empty    ${base_url}
    ...    msg=Aucune cible fournie pour le canal API : passer -v API_BASE_URL:http://<hote>:<port>.

Open Api Sandbox Channel
    [Documentation]    Ouvre le canal API sur le bac à sable SAP Business
    ...    Accelerator Hub, qui s'authentifie par une **clé d'API en en-tête**
    ...    et non en Basic. Même vocabulaire métier que `Open Api Channel` pour
    ...    la suite : seule la façon de prouver son identité change.
    ...
    ...    Aucun mandant n'est envoyé : le bac à sable est un système unique, et
    ...    un `sap-client` y serait un paramètre de query sans destinataire.
    [Arguments]    ${base_url}=${S4_SANDBOX_BASE}    ${api_key}=${API_KEY}
    ...    ${alias}=${API_ALIAS}
    Api Base Url Should Be Provided    ${base_url}
    Api Key Should Be Provided    ${api_key}
    Open Api Session    ${base_url}    api_key=${api_key}    alias=${alias}

Api Key Should Be Provided
    [Documentation]    Vérifie qu'une clé d'API a bien été fournie, SANS jamais
    ...    en lire la valeur, exactement comme `Api Credentials Should Be
    ...    Provided` le fait d'un mot de passe : une clé passée en type `Secret`
    ...    refuse d'être mesurée, et l'erreur de garde masquerait la vraie
    ...    cause. La bibliothèque refuse déjà une clé vide à l'ouverture ; cette
    ...    garde-ci nomme le remède côté ligne de commande.
    [Arguments]    ${api_key}
    ${fourni}=    Secret Is Provided    ${api_key}
    Should Be True    ${fourni}
    ...    msg=Aucune clé d'API fournie : passer -v "API_KEY: Secret:<clé>" (api.sap.com, bouton « Show API Key »).

Api Credentials Should Be Provided
    [Documentation]    Vérifie qu'un mot de passe a bien été fourni, SANS jamais
    ...    en lire la valeur. Un mot de passe passé en type `Secret` (la forme
    ...    recommandée) refuse d'être mesuré : `Should Not Be Empty` échoue
    ...    dessus par « Could not get length of '<secret>' », ce qui masquerait
    ...    la vraie cause derrière une erreur de garde. On teste donc la seule
    ...    chose observable sans le déballer : une valeur non fournie est restée
    ...    la chaîne vide du défaut.
    [Arguments]    ${password}
    ${fourni}=    Secret Is Provided    ${password}
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

Read Business Service Contract
    [Documentation]    Le contrat de métadonnées COMPLET d'un service (entity
    ...    sets, clés, propriétés, libellés, et les capacités déclarées au
    ...    niveau entity set : adressabilité, création, modification,
    ...    suppression). C'est la perception brute du canal, celle sur laquelle
    ...    une campagne construit ses fiches ; pour vérifier la seule présence
    ...    d'un ensemble d'entités, `Business Service Should Expose Entity Set`
    ...    suffit.
    [Arguments]    ${service}    ${alias}=${API_ALIAS}
    ${meta}=    Get Odata Metadata    ${service}    alias=${alias}
    RETURN    ${meta}

Api Channel Client
    [Documentation]    Le mandant SAP sur lequel le canal est ouvert, lu dans
    ...    l'état RÉEL de la session (jamais dans la configuration attendue).
    ...    Sert à prouver qu'un canal API et une session GUI regardent la même
    ...    population avant de comparer des volumétries.
    [Arguments]    ${alias}=${API_ALIAS}
    ${state}=    List Api Sessions
    # La table alias -> mandant est construite AVANT la recherche : un `$alias`
    # placé dans le corps d'une compréhension ne serait pas visible depuis
    # l'espace de noms d'`Evaluate` (portée Python), et l'erreur ne se voit
    # qu'à l'exécution réelle.
    ${clients}=    Evaluate    {s["alias"]: s["sap_client"] for s in $state["api_sessions"]}
    ${client}=    Evaluate    $clients.get($alias) or ""
    RETURN    ${client}

Count Business Entities With Filter
    [Documentation]    Le nombre d'entités d'un ensemble SOUS FILTRE OData,
    ...    variante de `Count Business Entities`. Indispensable à deux cas que
    ...    le comptage nu rend faux : un service draft-enabled, dont le
    ...    `$count` nu agrège entités actives et brouillons (filtre d'activité),
    ...    et une vue de consommation qui ne projette qu'un sous-ensemble
    ...    métier de sa table (filtre de rôle, de type…).
    [Arguments]    ${entity_set}    ${filter}    ${alias}=${API_ALIAS}
    ${count}=    Get Odata Count    ${entity_set}    alias=${alias}    filter=${filter}
    RETURN    ${count}

Probe Business Entity Sets
    [Documentation]    Sonde d'existence TOLÉRANTE : compte chaque ensemble
    ...    d'entités en un aller-retour et enregistre les refus au lieu de
    ...    s'arrêter au premier. À ne pas confondre avec `Read Business
    ...    Entities In One Roundtrip`, qui échoue en bloc : c'est le bon
    ...    comportement pour préparer un jeu de données (un échec partiel
    ...    silencieux corromprait la préparation) et le mauvais pour une sonde,
    ...    qui doit consigner et poursuivre. Chaque entrée porte le statut HTTP
    ...    et le code technique OData, jamais un message localisé.
    [Arguments]    ${service}    ${entity_sets}    ${max_entity_sets}=50
    ...    ${alias}=${API_ALIAS}
    ${probe}=    Probe Odata Entity Sets    ${service}    ${entity_sets}
    ...    alias=${alias}    max_entity_sets=${max_entity_sets}
    RETURN    ${probe}

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
    ...
    ...    Un état VIDE est refusé : constaté live (2026-08-26, reconnaissance
    ...    BTP sous rf-mcp), l'oracle validait `{'api_sessions': []}`, où il
    ...    n'y a rien à ne pas fuir. Un oracle qui se satisfait de l'absence
    ...    de matière ne prouve rien ; l'échec nomme la cause la plus
    ...    fréquente (sous rf-mcp, resource et bibliothèque peuvent servir
    ...    deux registres partitionnés par namespace).
    ${state}=    List Api Sessions
    ${sessions}=    Get From Dictionary    ${state}    api_sessions
    ${vide}=    Catenate    État du canal VIDE : rien à vérifier, donc rien
    ...    de prouvé. Ouvrir la session AVANT cet oracle (sous rf-mcp,
    ...    vérifier que resource et bibliothèque servent le même namespace :
    ...    List Api Sessions des deux côtés doit rendre les mêmes alias).
    Should Not Be Empty    ${sessions}    msg=${vide}
    ${dump}=    Evaluate    str($state).lower()
    Should Not Contain    ${dump}    authorization
    ...    msg=Fuite : un en-tête d'authentification apparaît dans l'état du canal.
    Should Not Contain    ${dump}    password
    ...    msg=Fuite : un mot de passe apparaît dans l'état du canal.
    RETURN    ${state}
