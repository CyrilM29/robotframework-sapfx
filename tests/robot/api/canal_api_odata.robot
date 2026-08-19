*** Settings ***
Documentation       Suite du **canal API**, le troisième canal, celui qui n'a pas
...                 d'écran. Elle exerce le canal pour lui-même : jusqu'ici il
...                 n'était éprouvé qu'indirectement, par les deux suites
...                 cross-paradigme, et sur un seul keyword de lecture chacune.
...                 Les défauts que cet angle mort abritait sont rappelés dans les
...                 scénarios qui les verrouillent.
...
...                 Deux protocoles, deux systèmes, les MÊMES mots-clés métier : la
...                 Gateway OData **v2** embarquée d'un ABAP Platform (tag ``a4h``) et
...                 un service OData **v4** CAP (tag ``capsflight``). C'est cette
...                 symétrie qui vaut d'être testée : une bibliothèque qui ne
...                 parlerait bien qu'à l'un des deux ne serait utile qu'à moitié.
...
...                 Prérequis lane ``a4h`` : système joignable, Gateway active
...                 (sinon le préflight le dit et nomme la remédiation).
...                 Prérequis lane ``capsflight`` : ``npx cds watch`` dans
...                 ``_cap-sflight`` (:4004).
...
...                 Exemples :
...                 | robot --pythonpath src --include a4h
...                 | ...   -v API_USER:DEVELOPER -v "API_PASSWORD: Secret:***"
...                 | ...   tests/robot/api/canal_api_odata.robot
...                 | robot --pythonpath src --include capsflight
...                 | ...   tests/robot/api/canal_api_odata.robot

Resource            ../../../resources/api_keywords.resource

Suite Teardown      Close Api Channel


*** Variables ***
# Lane a4h : Gateway OData v2 embarquée (HTTP mappé par le conteneur).
${A4H_API_URL}          http://vhcala4hci:50000
${API_USER}             DEVELOPER
${API_PASSWORD}         ${EMPTY}    # OBLIGATOIRE : -v "API_PASSWORD: Secret:<motdepasse>"
${API_CLIENT}           001
${EPM_PRODUCTS_ENTITY}    Products
${EPM_PRICE_LABEL}      Price

# Lane capsflight : service OData v4 du process cds. Le mocked-auth protège
# aussi le service : `alice` est l'utilisateur mock, son mot de passe est vide,
# ce n'est donc pas un secret.
${CAP_API_URL}          http://localhost:4004
${CAP_USER}             alice
${TRAVEL_ENTITY}        Travel
${TRAVEL_KEY_FIELD}     TravelUUID


*** Test Cases ***
Le Canal Repond Avant Toute Lecture
    [Documentation]    Le préflight passe AVANT le premier scénario métier : une
    ...    Gateway inactive doit être diagnostiquée ici, avec sa remédiation,
    ...    pas déguisée plus loin en « entité introuvable ».
    [Tags]    a4h
    Ouvrir Le Canal A4H
    Api Channel Should Be Available    alias=a4h
    Wait Until Api Channel Is Available    alias=a4h    timeout=30s

Le Catalogue Publie Le Service Metier Attendu
    [Documentation]    Perception : ce que le système expose réellement. Un
    ...    service absent du catalogue est un prérequis manquant, pas un test
    ...    en échec sur une entité.
    [Tags]    a4h
    ${services}=    List Available Business Services    alias=a4h
    Should Not Be Empty    ${services}    msg=Catalogue vide : la Gateway publie-t-elle un catalogue ?
    ${noms}=    Evaluate    [t for t in [str(s) for s in $services] if 'SEPMRA_SHOP' in t]
    Should Not Be Empty    ${noms}    msg=Le service EPM attendu n'est pas au catalogue.

Le Contrat Du Service Publie Ses Entites Et Ses Cles
    [Documentation]    Contrat vérifié à la source (`$metadata`) : l'ensemble
    ...    d'entités existe, et il annonce au moins une clé. Une entité sans clé
    ...    déclarée ne serait adressable par aucun test.
    [Tags]    a4h
    ${entite}=    Business Service Should Expose Entity Set
    ...    ${EPM_SHOP_SERVICE}    ${EPM_PRODUCTS_ENTITY}    alias=a4h
    Should Not Be Empty    ${entite}[keys]    msg=Ensemble d'entités sans clé déclarée.
    Should Not Be Empty    ${entite}[properties]

Un Champ Se Retrouve Par Son Libelle Metier
    [Documentation]    Le localisateur « libellé humain » du canal sans écran,
    ...    pendant de `Find Element By Label`. Un libellé inconnu doit échouer
    ...    en nommant ce qui existe, jamais rendre un premier match arbitraire.
    [Tags]    a4h
    ${candidats}=    Find Business Field By Label
    ...    ${EPM_SHOP_SERVICE}    ${EPM_PRICE_LABEL}    alias=a4h
    Should Not Be Empty    ${candidats}
    ...    msg=Le libellé ${EPM_PRICE_LABEL} n'est porté par aucune propriété du service.
    Run Keyword And Expect Error    *
    ...    Find Business Field By Label    ${EPM_SHOP_SERVICE}    libelle-absent-du-service    alias=a4h

Le Comptage Et La Lecture Bornee Restent Coherents
    [Documentation]    Le coeur du canal en lecture. La borne demandée est
    ...    respectée, et la projection rend bien les champs demandés : sans quoi
    ...    une suite croirait lire ce qu'elle n'a pas demandé.
    [Tags]    a4h
    ${total}=    Count Business Entities    ${EPM_PRODUCTS}    alias=a4h
    Should Be True    ${total} > 0    msg=Aucun produit : jeu de données de démonstration absent ?
    Set Suite Variable    ${TOTAL_PRODUITS}    ${total}
    ${lignes}=    Read Business Entities    ${EPM_PRODUCTS}    Id,Name,Price    limit=5    alias=a4h
    Should Not Be Empty    ${lignes}
    Should Be True    ${lignes.__len__()} <= 5    msg=La borne de lecture n'est pas respectée.
    Dictionary Should Contain Key    ${lignes}[0]    Id

La Lecture Complete Suit La Pagination Sans Depasser Le Total
    [Documentation]    Une lecture paginée rend au moins autant qu'une page
    ...    bornée et jamais plus que le total annoncé. L'encadrement est ce qui
    ...    distingue une pagination qui marche d'une boucle qui relit la même
    ...    page.
    [Tags]    a4h
    ${une_page}=    Read Business Entities    ${EPM_PRODUCTS}    Id    limit=10    alias=a4h
    ${tout}=    Read All Business Entities    ${EPM_PRODUCTS}    Id    max_pages=5    alias=a4h
    Should Be True    ${tout.__len__()} >= ${une_page.__len__()}
    Should Be True    ${tout.__len__()} <= ${TOTAL_PRODUITS}
    ...    msg=La pagination rend plus de lignes que le total annoncé : lecture en boucle ?

Plusieurs Lectures Tiennent En Un Seul Aller Retour
    [Documentation]    Regroupement `$batch` : deux lectures indépendantes, deux
    ...    réponses, dans l'ordre. Chaque statut est vérifié séparément, sinon
    ...    une opération en erreur passerait inaperçue au milieu d'un lot vert.
    [Tags]    a4h
    ${reponses}=    Read Business Entities In One Roundtrip    ${EPM_SHOP_SERVICE}
    ...    Products?$top=2    Products/$count    alias=a4h
    Length Should Be    ${reponses}    2
    FOR    ${reponse}    IN    @{reponses}
        Should Be True    ${reponse}[status] < 300    msg=Opération du lot en erreur : ${reponse}
    END

L Etat Du Canal Ne Transporte Aucun Identifiant
    [Documentation]    Cet état est servi aux agents à chaque tour de boucle.
    ...    Il doit rester lisible sans jamais devenir un vecteur de fuite.
    [Tags]    a4h
    Api Channel Should Show Activity    alias=a4h
    Api Channel State Should Not Leak Credentials

Un Canal Sans Identifiants Est Refuse Et Non Vide
    [Documentation]    Un service protégé doit répondre 401, et l'échec doit le
    ...    dire. Le piège est le silence : une lecture qui rendrait une liste
    ...    vide ferait conclure « pas de données » là où il fallait lire
    ...    « pas authentifié ».
    [Tags]    capsflight
    Open Api Channel    ${CAP_API_URL}    user=${EMPTY}    password=${EMPTY}
    ...    client=${EMPTY}    alias=cap_anonyme
    ${erreur}=    Run Keyword And Expect Error    *
    ...    Count Business Entities    ${TRAVEL_ENTITIES}    alias=cap_anonyme
    Should Contain    ${erreur}    401
    ...    msg=L'échec ne nomme pas le refus d'authentification : diagnostic impossible.

Le Contrat De Perception Vaut Aussi Pour Odata V4
    [Documentation]    Les mêmes mots-clés métier, l'autre protocole : c'est la
    ...    propriété qui rend le canal utilisable sur un paysage mixte.
    [Tags]    capsflight
    Ouvrir Le Canal Cap
    ${entite}=    Business Service Should Expose Entity Set
    ...    ${TRAVEL_SERVICE}    ${TRAVEL_ENTITY}    alias=cap
    Should Not Be Empty    ${entite}[keys]
    ${total}=    Count Business Entities    ${TRAVEL_ENTITIES}    alias=cap
    Should Be True    ${total} > 0    msg=Aucune entité : le service de démonstration tourne-t-il ?
    Set Suite Variable    ${TOTAL_AVANT}    ${total}

Un Filtre Contenant Des Espaces Interroge Bien Un Service V4
    [Documentation]    Non-régression. Un `$filter` contient toujours des
    ...    espaces (`TravelID eq 1`). Encodés comme ceux d'un formulaire HTML
    ...    (`+`), ils passaient sur une Gateway v2 et faisaient échouer tout
    ...    service v4 en HTTP 400 : le défaut vivait dans cet angle mort, et un
    ...    test unitaire gravait même l'encodage fautif.
    [Tags]    capsflight
    ${lignes}=    Read Business Entities    ${TRAVEL_ENTITIES}    TravelID    limit=1    alias=cap
    Should Not Be Empty    ${lignes}
    ${identifiant}=    Set Variable    ${lignes}[0][TravelID]
    ${filtrees}=    Get Odata Entities    ${TRAVEL_ENTITIES}    alias=cap
    ...    filter=TravelID eq ${identifiant}    select=TravelID
    Should Not Be Empty    ${filtrees}
    ...    msg=Le filtre ne retrouve pas un identifiant pourtant lu juste avant.

Les Donnees De Test Creees Sont Retirees A La Fin
    [Documentation]    Cycle réversible complet par le canal API : créer,
    ...    modifier, relire, tout retirer. Deux pièges y sont verrouillés. Le
    ...    suivi automatique repose sur l'URI que le serveur annonce, or un
    ...    service draft-enabled en annonce une qui ne répond pas : le chemin
    ...    réel est donc déclaré explicitement. Et un brouillon n'entrant pas
    ...    dans le `$count`, un compte inchangé ne prouverait aucun nettoyage :
    ...    la disparition est vérifiée sur l'entité elle-même.
    [Tags]    capsflight
    ${entite}=    Create Test Entity    ${TRAVEL_ENTITIES}    ${{ {'Description': 'Recette du canal API'} }}
    ...    alias=cap    track=${False}
    ${chemin}=    Draft Entity Path    ${TRAVEL_ENTITIES}    ${TRAVEL_KEY_FIELD}    ${entite}[${TRAVEL_KEY_FIELD}]
    Track Created Entity    ${chemin}    alias=cap
    Patch Odata    ${chemin}    ${{ {'Description': 'Recette du canal API, modifiee'} }}    alias=cap
    ${relue}=    Get Odata    ${chemin}    alias=cap
    Should Be Equal    ${relue}[Description]    Recette du canal API, modifiee
    ...    msg=La modification n'est pas relue : l'écriture n'est pas confirmée.
    Remove Created Test Data    alias=cap
    ${apres}=    Run Keyword And Ignore Error    Get Odata    ${chemin}    alias=cap
    Should Be Equal    ${apres}[0]    FAIL
    ...    msg=L'entité de test répond encore après le nettoyage : donnée laissée derrière.
    ${total}=    Count Business Entities    ${TRAVEL_ENTITIES}    alias=cap
    Should Be Equal As Integers    ${total}    ${TOTAL_AVANT}
    ...    msg=Le compte a bougé : ${total} au lieu de ${TOTAL_AVANT}.


*** Keywords ***
Ouvrir Le Canal A4H
    [Documentation]    Ouverture de la lane Gateway v2, identifiants fournis en
    ...    ligne de commande (`Secret:`), jamais écrits dans la suite.
    Api Credentials Should Be Provided    ${API_PASSWORD}
    Open Api Channel    ${A4H_API_URL}    user=${API_USER}    password=${API_PASSWORD}
    ...    client=${API_CLIENT}    alias=a4h

Ouvrir Le Canal Cap
    [Documentation]    Ouverture de la lane OData v4. Mot de passe vide : cas
    ...    limite réel du mocked-auth, que la couche doit accepter.
    Open Api Channel    ${CAP_API_URL}    user=${CAP_USER}    password=${EMPTY}
    ...    client=${EMPTY}    alias=cap
