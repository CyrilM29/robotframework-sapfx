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
...                 Mots-clés du canal **RFC / BAPI** lisibles métier. Quatrième
...                 miroir de `ecc_keywords.resource`, `fiori_keywords.resource` et
...                 `api_keywords.resource` : un test se lit de la même façon
...                 (`Open ...`, `Count ...`, `Read ...`, `Close ...`) qu'il pilote
...                 le client lourd SAP GUI, l'interface web Fiori, le canal OData
...                 ou le canal RFC.
...
...                 Table de correspondance des quatre canaux :
...                 | =ECC=               | =Fiori=        | =API (OData)=           | =RFC=                  |
...                 | Open SAP And Log In | Open SAP And Log In | Open Api Channel   | Open Rfc Channel       |
...                 | Go To Transaction   | Open App       | (sans objet : pas d'écran) | (sans objet)    |
...                 | Count Table Entries | (sans objet)   | Count Business Entities | Count Business Records |
...                 | Read Grid           | Read Ui5 Table | Read Business Entities  | Read Business Records  |
...                 | Close SAP           | Close SAP      | Close Api Channel       | Close Rfc Channel      |
...
...                 Pourquoi un fichier à lui plutôt qu'un gonflement de
...                 `api_keywords.resource` : le RFC a son propre cycle de vie de
...                 connexion (pas de cookie, pas de CSRF, pas d'URL, mais un
...                 système applicatif, un mandant et une LUW), et il est
...                 **optionnel** (`pyrfc` n'a aucune roue précompilée au-delà de
...                 Python 3.12). Une suite RFC doit pouvoir se sauter là où le
...                 canal n'existe pas : c'est `Skip Unless Rfc Channel Is Available`.
...
...                 Convention 1 : aucune suite ne cite un nom de module fonction,
...                 de BAPI ni de table. Ils vivent ici, sous des noms métier
...                 (`${AIRLINE_TABLE}`, `${BAPI_USER_DETAIL}`), comme les ids SAP
...                 vivent dans `ecc_keywords.resource`. Convention 3 : les refus
...                 sont jugés sur leur **code technique** (`TABLE_NOT_AVAILABLE`,
...                 `RFC_LOGON_FAILURE`) ou sur le **type** d'un message BAPIRET2,
...                 jamais sur un texte localisé. Convention 11 : le mot de passe
...                 arrive en `Secret:` par la ligne de commande, et la garde ne le
...                 MESURE jamais.

Library             SapApiLibrary
Library             Collections
# Primitive pure atteinte par un KEYWORD (décision DDIC 2026-08-17) :
# `Secret Is Provided` teste la PRÉSENCE d'un identifiant sans jamais le lire.
Library             sapfx_common.secrets


*** Variables ***
# --- Connexion (renseignée par la suite ou en ligne de commande) ---
${RFC_ASHOST}                   ${EMPTY}
${RFC_SYSNR}                    00
${RFC_CLIENT}                   ${EMPTY}
${RFC_USER}                     ${EMPTY}
${RFC_PASSWORD}                 ${EMPTY}    # `Secret:` en ligne de commande : jamais en clair
${RFC_LANG}                     EN
${RFC_ALIAS}                    default

# --- Modules fonction : les sondes de vie et la perception du canal ---
# Tous remote-enabled et livrés partout : ce sont les seuls appels qu'une
# campagne peut faire sans rien supposer du paramétrage de la cible.
${SYSTEM_INFO_MODULE}           RFC_SYSTEM_INFO
${PING_MODULE}                  RFC_PING
${ECHO_MODULE}                  STFC_CONNECTION
${STRUCTURE_MODULE}             STFC_STRUCTURE

# --- BAPIs ---
${BAPI_USER_DETAIL}             BAPI_USER_GET_DETAIL
${BAPI_FLIGHT_LIST}             BAPI_FLIGHT_GETLIST
${BAPI_INVENTORY}               BAPI_MONITOR_GETLIST

# --- Tables métier et leurs champs techniques (jamais de titre affiché) ---
${CLIENT_TABLE}                 T000
${CLIENT_FIELDS}                MANDT,MTEXT,ORT01
${CLIENT_KEY_FIELD}             MANDT
${AIRLINE_TABLE}                SCARR
${AIRLINE_FIELDS}               CARRID,CARRNAME,CURRCODE
${AIRLINE_KEY_FIELD}            CARRID
${CONNECTION_TABLE}             SPFLI
${CONNECTION_FIELDS}            CARRID,CONNID,CITYFROM,CITYTO
${FLIGHT_TABLE}                 SFLIGHT
${FLIGHT_FIELDS}                CARRID,CONNID,PRICE,CURRENCY
${PRODUCT_TABLE}                SNWD_PD
${PRODUCT_KEY_FIELD}            PRODUCT_ID
${TABLE_CATALOG}                DD02L
${TABLE_CATALOG_FIELDS}         TABNAME,TABCLASS
${FIELD_CATALOG}                DD03L
${FIELD_CATALOG_KEY_FIELD}      FIELDNAME

# --- Modèle de voyage MODERNE (le second jeu de démonstration) ---
# Il porte SON PROPRE catalogue de compagnies, de population différente de
# celle du catalogue classique : ce sont deux catalogues, jamais deux vues du
# même. Les nommer distinctement ici est ce qui empêche un croisement de les
# confondre (mesuré live 2026-08-28 : 18 contre 16, inclusion stricte).
${MODERN_AIRLINE_TABLE}         /DMO/CARRIER
${MODERN_AIRLINE_KEY_FIELD}     CARRIER_ID
${MODERN_TRAVEL_TABLE}          /DMO/TRAVEL
${MODERN_TRAVEL_KEY_FIELD}      TRAVEL_ID
${MODERN_MODEL_PREFIX}          /DMO/%
${TRANSPARENT_TABLE_CLASS}      TRANSP

# --- Surface du canal : ce que la cible publie, et avec quoi elle est bâtie ---
${COMPONENT_TABLE}              CVERS
${COMPONENT_FIELDS}             COMPONENT,RELEASE,EXTRELEASE
${FUNCTION_DIRECTORY}           TFDIR
${FUNCTION_NAME_FIELD}          FUNCNAME
${REMOTE_ENABLED_FILTER}        FMODE EQ 'R'
${REPOSITORY_DIRECTORY}         TADIR
${REPOSITORY_NAME_FIELD}        OBJ_NAME
# Définitions de service, liaisons de service et définitions de comportement :
# les objets du modèle de programmation moderne. La clause tient sous les 72
# caractères que le module ABAP accepte (mesuré : 54).
${MODERN_MODEL_FILTER}          OBJECT EQ 'SRVD' OR OBJECT EQ 'SRVB' OR OBJECT EQ 'BDEF'

# --- Jobs de fond : des BUDGETS d'attente, jamais des temporisations ---
# Le délai court sert les branches dont on SAIT qu'elles ne peuvent pas
# aboutir : il borne le budget d'un échec attendu, il ne fait patienter
# personne (convention 2 : aucun `Sleep` nulle part).
${JOB_POLL}                     2s
${SHORT_JOB_WAIT}               5s
${JOB_WAIT_BUDGET}              30s

# --- Sondes de refus : ce qui n'existe volontairement PAS sur la cible ---
${MISSING_TABLE}                ZZ_TABLE_QUI_NEXISTE_PAS
${MISSING_FIELD}                ZZ_CHAMP_INEXISTANT
${MISSING_FUNCTION}             Z_MODULE_FONCTION_INEXISTANT
${UNKNOWN_USER}                 ZZ_UTILISATEUR_INCONNU
# Un code compagnie qui n'existe pas : le filtre qui ne ramène rien SANS être
# une erreur (la distinction que le canal doit tenir).
${MISSING_AIRLINE}              ZZ
${UNKNOWN_JOB}                  ZZ_JOB_QUI_NEXISTE_PAS
${UNKNOWN_CLIENT}               999
${UNREACHABLE_SYSNR}            42
# Le port du répartiteur est DÉRIVÉ du numéro d'instance (base + numéro) :
# c'est la mécanique qui explique pourquoi une cible dont le port publié ne
# correspond pas à son numéro d'instance interne exige un relais local. Mesuré
# live : une ouverture sur le numéro 42 est refusée en nommant le port 3342.
${DISPATCHER_PORT_BASE}         3300
# Le composant logiciel qui porte la release de base du système : l'ancre
# d'identité d'une campagne, là où l'identifiant système ne discrimine rien.
${BASE_SOFTWARE_COMPONENT}      SAP_BASIS
${WRONG_PASSWORD}               mot-de-passe-volontairement-faux
# Une clause de sélection au-delà des 72 caractères que le module ABAP accepte :
# la garde est côté client, donc cet appel ne part jamais sur le réseau.
${OVERSIZED_CLAUSE}             CARRID EQ 'LH' AND CARRNAME EQ 'Lufthansa' AND CURRCODE EQ 'EUR' AND MANDT EQ '001'


*** Keywords ***
Skip Unless Rfc Channel Is Available
    [Documentation]    Saute la suite (au lieu de la faire rougir) là où le canal
    ...    RFC n'existe pas sur le poste. Le RFC est optionnel dans cet
    ...    écosystème : `pyrfc` n'a aucune roue précompilée au-delà de Python
    ...    3.12 et exige un runtime natif NW RFC. Une suite qui rougit là où rien
    ...    n'est cassé finit désactivée, et c'est une suite désactivée qui ne
    ...    protège plus rien.
    ...
    ...    Le message du saut nomme la cause ET son remède, les deux absences
    ...    possibles n'ayant pas le même : binding absent, ou runtime absent.
    ${statut}=    Get Rfc Channel Status
    Skip If    not ${statut}[available]
    ...    Canal RFC indisponible sur ce poste (${statut}[reason]) : ${statut}[detail] ${statut}[remediation]
    RETURN    ${statut}

Rfc Credentials Should Be Provided
    [Documentation]    Vérifie qu'un mot de passe a bien été fourni, SANS jamais
    ...    en lire la valeur. Même garde que côté OData, et pour la même raison :
    ...    un mot de passe passé en type `Secret` refuse d'être mesuré
    ...    (`Should Not Be Empty` échoue dessus par « Could not get length of
    ...    '<secret>' »), et l'erreur de garde masquerait la vraie cause.
    [Arguments]    ${password}
    ${fourni}=    Secret Is Provided    ${password}
    Should Be True    ${fourni}
    ...    msg=Aucun mot de passe fourni : passer -v "RFC_PASSWORD: Secret:<motdepasse>".

Open Rfc Channel
    [Documentation]    Ouvre le canal RFC vers un système applicatif. Miroir de
    ...    `Open SAP And Log In` et d'`Open Api Channel` : un test n'a pas à
    ...    savoir qu'une connexion RFC porte un hôte applicatif, un numéro de
    ...    système, un mandant et une langue.
    [Arguments]    ${alias}=${RFC_ALIAS}    ${ashost}=${RFC_ASHOST}
    ...    ${sysnr}=${RFC_SYSNR}    ${client}=${RFC_CLIENT}    ${user}=${RFC_USER}
    ...    ${password}=${RFC_PASSWORD}    ${lang}=${RFC_LANG}
    Should Not Be Empty    ${ashost}
    ...    msg=Aucune cible fournie pour le canal RFC : passer -v RFC_ASHOST:<hôte applicatif>.
    Rfc Credentials Should Be Provided    ${password}
    Open Rfc Connection    alias=${alias}    ashost=${ashost}    sysnr=${sysnr}
    ...    client=${client}    user=${user}    passwd=${password}    lang=${lang}
    RETURN    ${alias}

Close Rfc Channel
    [Documentation]    Ferme TOUTES les connexions RFC du canal. Miroir de
    ...    `Close SAP`, et même exigence d'hygiène : une connexion RFC orpheline
    ...    est une session utilisateur restée ouverte côté serveur. À appeler en
    ...    Suite Teardown, donc même sur échec.
    Close All Rfc Connections

List Open Rfc Channels
    [Documentation]    Les alias RFC actuellement ouverts, lus dans l'état RÉEL
    ...    du canal (jamais dans l'intention de la suite). C'est aussi ce qui
    ...    prouve qu'un teardown a bien tout refermé.
    ${etat}=    List Api Sessions
    RETURN    ${etat}[rfc_connections]

# ----------------------------------------------------- Perception du canal

Read System Identity
    [Documentation]    L'identité du système joint, telle que le canal la rend :
    ...    système, mandant, utilisateur, release et kernel. Un canal ouvert ne
    ...    dit pas encore vers QUOI : sans cette lecture, une campagne peut être
    ...    verte contre le mauvais système.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${attributs}=    Get Rfc Connection Attributes    alias=${alias}
    RETURN    ${attributs}

Read System Information
    [Documentation]    La fiche que le système publie sur lui-même
    ...    (`RFC_SYSTEM_INFO`) : identifiant, release, kernel, hôte, adresse IP,
    ...    base de données, système d'exploitation. Seconde source d'identité,
    ...    indépendante des attributs de la connexion : les faire coïncider est
    ...    ce qui prouve la cible.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${brut}=    Call Rfc    ${SYSTEM_INFO_MODULE}    alias=${alias}
    RETURN    ${brut}[RFCSI_EXPORT]

Rfc Channel Should Answer Ping
    [Documentation]    La sonde de vie la plus élémentaire du canal. Sa réponse
    ...    est un dictionnaire VIDE : il n'y a rien à y lire, et seule l'absence
    ...    d'exception fait foi. Asserter un contenu ici serait asserter du vide.
    [Arguments]    ${alias}=${RFC_ALIAS}
    Call Rfc    ${PING_MODULE}    alias=${alias}

Echo Through Rfc Channel
    [Documentation]    Aller-retour applicatif complet : le texte envoyé revient
    ...    tel quel dans `ECHOTEXT`, et `RESPTEXT` porte l'identité du serveur qui
    ...    a répondu. La sonde qui prouve que le canal traverse vraiment jusqu'à
    ...    l'application, pas seulement jusqu'au port.
    [Arguments]    ${texte}    ${alias}=${RFC_ALIAS}
    ${reponse}=    Call Rfc    ${ECHO_MODULE}    alias=${alias}    REQUTEXT=${texte}
    RETURN    ${reponse}

Exchange Structure Through Rfc Channel
    [Documentation]    Aller-retour d'une STRUCTURE et d'une TABLE, là où l'écho
    ...    simple ne prouve qu'une chaîne : c'est le typage ABAP qui est éprouvé.
    ...    Seuls des champs caractère sont remplis, pour rester pilotable depuis
    ...    une suite (les champs numériques de cette structure exigent de vrais
    ...    entiers, pas la chaîne « 42 »).
    [Arguments]    ${texte}    ${alias}=${RFC_ALIAS}
    ${structure}=    Create Dictionary    RFCCHAR4=ABCD    RFCDATA1=${texte}
    ...    RFCDATA2=${texte}
    ${reponse}=    Call Rfc    ${STRUCTURE_MODULE}    alias=${alias}
    ...    IMPORTSTRUCT=${structure}
    RETURN    ${reponse}

List System Bapis
    [Documentation]    L'inventaire des BAPIs que le système publie : la
    ...    perception du canal sans écran, l'équivalent RFC de
    ...    `List Available Business Services` côté OData. Chaque entrée porte un
    ...    type d'objet métier, un nom métier et le nom du module ABAP.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${brut}=    Call Rfc    ${BAPI_INVENTORY}    alias=${alias}
    RETURN    ${brut}[BAPILIST]

Read Software Components
    [Documentation]    L'inventaire des composants logiciels installés, avec
    ...    leur release et leur niveau de support. C'est la source d'identité
    ...    la plus RICHE du canal, et la seule qui distingue vraiment deux
    ...    cibles : mesuré live le 2026-08-28, deux conteneurs du même poste
    ...    portent le même identifiant système ET le même nom d'hôte
    ...    applicatif, donc ni l'un ni l'autre ne prouve quoi que ce soit.
    ...
    ...    Les clés rendues sont MÉTIER (`name`, `release`, `support_level`) :
    ...    les noms techniques de la table restent dans cette couche, et
    ...    l'artefact de surface les consomme tels quels.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${lignes}=    Read Business Records    ${COMPONENT_TABLE}    ${COMPONENT_FIELDS}
    ...    alias=${alias}
    @{composants}=    Create List
    FOR    ${ligne}    IN    @{lignes}
        ${entree}=    Create Dictionary    name=${ligne}[COMPONENT]
        ...    release=${ligne}[RELEASE]    support_level=${ligne}[EXTRELEASE]
        Append To List    ${composants}    ${entree}
    END
    RETURN    ${composants}

Read Release Of Software Component
    [Documentation]    La release d'UN composant logiciel nommé, ou un échec qui
    ...    liste les composants présents. C'est l'ancre d'identité d'une
    ...    campagne : le composant de base doit porter exactement la release que
    ...    la fiche système annonce, sinon les deux sources se contredisent.
    [Arguments]    ${composant}    ${alias}=${RFC_ALIAS}
    ${composants}=    Read Software Components    alias=${alias}
    ${noms}=    Get Values From Dicts    ${composants}    name
    Should Contain    ${noms}    ${composant}
    ...    msg=Le composant ${composant} n'est pas installé sur cette cible ; présents : ${noms}.
    ${index}=    Get Index From List    ${noms}    ${composant}
    RETURN    ${composants}[${index}][release]

# ----------------------------------------------------- Lectures de données

Read Business Records
    [Documentation]    Lecture générique d'une table par RFC (miroir de
    ...    `Read Grid` et de `Read Business Entities`) : projetée sur les champs
    ...    utiles, bornée, éventuellement filtrée.
    [Arguments]    ${table}    ${fields}    ${filter}=${EMPTY}    ${limit}=0
    ...    ${alias}=${RFC_ALIAS}
    ${lignes}=    Read Rfc Table    ${table}    ${fields}    alias=${alias}
    ...    options=${filter}    rowcount=${limit}
    RETURN    ${lignes}

Count Business Records
    [Documentation]    Le nombre de lignes d'une table, compté par RFC. Miroir du
    ...    `Count Table Entries` de l'ECC et du `Count Business Entities` du
    ...    canal OData : c'est cette symétrie qui permet de recouper un même fait
    ...    métier par deux canaux indépendants.
    ...
    ...    `RFC_READ_TABLE` n'a pas de mode « compter » : la lecture est donc
    ...    restreinte à UNE colonne clé, et les lignes sont comptées ici. Le
    ...    comptage est exact, jamais estimé.
    [Arguments]    ${table}    ${key_field}    ${filter}=${EMPTY}    ${alias}=${RFC_ALIAS}
    ${lignes}=    Read Rfc Table    ${table}    ${key_field}    alias=${alias}
    ...    options=${filter}
    ${nombre}=    Get Length    ${lignes}
    RETURN    ${nombre}

Read Client Directory
    [Documentation]    Les mandants installés sur le système (nom et ville de
    ...    l'entité). La lecture qui dit sur quelle population le canal travaille.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${lignes}=    Read Business Records    ${CLIENT_TABLE}    ${CLIENT_FIELDS}
    ...    alias=${alias}
    RETURN    ${lignes}

Read Airlines
    [Documentation]    Les compagnies aériennes du modèle de démonstration, avec
    ...    leur devise. `airline` filtre sur le code compagnie ; sans lui, tout
    ...    le catalogue.
    [Arguments]    ${airline}=${EMPTY}    ${alias}=${RFC_ALIAS}
    ${filtre}=    Airline Filter    ${airline}
    ${lignes}=    Read Business Records    ${AIRLINE_TABLE}    ${AIRLINE_FIELDS}
    ...    filter=${filtre}    alias=${alias}
    RETURN    ${lignes}

Count Airlines
    [Documentation]    Le nombre de compagnies aériennes du catalogue.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${nombre}=    Count Business Records    ${AIRLINE_TABLE}    ${AIRLINE_KEY_FIELD}
    ...    alias=${alias}
    RETURN    ${nombre}

Read Flight Connections
    [Documentation]    Les liaisons d'une compagnie (villes de départ et
    ...    d'arrivée), bornées par `limit` : la lecture qui éprouve le plafond de
    ...    lignes du canal.
    [Arguments]    ${airline}    ${limit}=0    ${alias}=${RFC_ALIAS}
    ${filtre}=    Airline Filter    ${airline}
    ${lignes}=    Read Business Records    ${CONNECTION_TABLE}    ${CONNECTION_FIELDS}
    ...    filter=${filtre}    limit=${limit}    alias=${alias}
    RETURN    ${lignes}

Count Flight Connections
    [Documentation]    Le nombre de liaisons aériennes du modèle de
    ...    démonstration classique, toutes compagnies confondues.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${nombre}=    Count Business Records    ${CONNECTION_TABLE}    ${AIRLINE_KEY_FIELD}
    ...    alias=${alias}
    RETURN    ${nombre}

Read Flight Price
    [Documentation]    Le prix d'un vol, lu par la table (donc du TEXTE délimité :
    ...    « 666.00 »). La même donnée revient en type ABAP décimal par la BAPI :
    ...    une assertion numérique doit convertir, jamais comparer les deux
    ...    représentations.
    [Arguments]    ${airline}    ${connection}    ${alias}=${RFC_ALIAS}
    ${filtre}=    Set Variable    ${AIRLINE_KEY_FIELD} EQ '${airline}' AND CONNID EQ '${connection}'
    ${lignes}=    Read Business Records    ${FLIGHT_TABLE}    ${FLIGHT_FIELDS}
    ...    filter=${filtre}    limit=1    alias=${alias}
    Should Not Be Empty    ${lignes}
    ...    msg=Aucun vol ${airline}/${connection} : jeu de données de démonstration absent ?
    RETURN    ${lignes}[0]

Count Products
    [Documentation]    Le nombre de produits du modèle marchand, compté par RFC.
    ...    C'est le fait que le scénario cross-canal confronte au `$count` du
    ...    service OData qui projette la même table.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${nombre}=    Count Business Records    ${PRODUCT_TABLE}    ${PRODUCT_KEY_FIELD}
    ...    alias=${alias}
    RETURN    ${nombre}

Read Airline Codes
    [Documentation]    Les codes du catalogue de compagnies CLASSIQUE. À ne pas
    ...    confondre avec `Read Modern Airline Codes` : ce sont deux catalogues
    ...    distincts, et le nom du keyword est ce qui empêche la confusion.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${lignes}=    Read Business Records    ${AIRLINE_TABLE}    ${AIRLINE_KEY_FIELD}
    ...    alias=${alias}
    ${codes}=    Get Values From Dicts    ${lignes}    ${AIRLINE_KEY_FIELD}
    RETURN    ${codes}

Read Modern Airline Codes
    [Documentation]    Les codes du catalogue de compagnies du modèle de voyage
    ...    MODERNE. Le second catalogue de la cible, de population différente du
    ...    classique (mesuré 16 contre 18 le 2026-08-28) : un croisement qui
    ...    pointerait un canal sur l'un et l'autre canal sur l'autre produirait
    ...    un écart parfaitement reproductible, attribué à un défaut qui
    ...    n'existe pas.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${lignes}=    Read Business Records    ${MODERN_AIRLINE_TABLE}
    ...    ${MODERN_AIRLINE_KEY_FIELD}    alias=${alias}
    ${codes}=    Get Values From Dicts    ${lignes}    ${MODERN_AIRLINE_KEY_FIELD}
    RETURN    ${codes}

Count Modern Airlines
    [Documentation]    Le nombre de compagnies du modèle de voyage moderne,
    ...    compté par RFC. C'est ce compte, et jamais celui du catalogue
    ...    classique, qui se confronte au comptage OData du service moderne.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${nombre}=    Count Business Records    ${MODERN_AIRLINE_TABLE}
    ...    ${MODERN_AIRLINE_KEY_FIELD}    alias=${alias}
    RETURN    ${nombre}

Count Travels
    [Documentation]    Le nombre de voyages du modèle moderne, compté par RFC :
    ...    le second fait métier que la campagne recoupe par les deux canaux.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${nombre}=    Count Business Records    ${MODERN_TRAVEL_TABLE}
    ...    ${MODERN_TRAVEL_KEY_FIELD}    alias=${alias}
    RETURN    ${nombre}

Count Modern Model Tables
    [Documentation]    Le nombre de tables transparentes du modèle de voyage
    ...    moderne, lu dans le catalogue du dictionnaire. Une mesure de
    ...    DÉPLOIEMENT du modèle sur la cible, pas une volumétrie de données.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${filtre}=    Set Variable
    ...    TABNAME LIKE '${MODERN_MODEL_PREFIX}' AND TABCLASS EQ '${TRANSPARENT_TABLE_CLASS}'
    ${nombre}=    Count Business Records    ${TABLE_CATALOG}    TABNAME
    ...    filter=${filtre}    alias=${alias}
    RETURN    ${nombre}

Read Dictionary Class Of Airlines
    [Documentation]    La classe de table que le DICTIONNAIRE attribue à la table
    ...    des compagnies (`TRANSP` pour une table transparente) : la lecture
    ...    locale-indépendante qui distingue une table réelle d'une structure.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${filtre}=    Set Variable    TABNAME EQ '${AIRLINE_TABLE}'
    ${lignes}=    Read Business Records    ${TABLE_CATALOG}    ${TABLE_CATALOG_FIELDS}
    ...    filter=${filtre}    alias=${alias}
    Should Not Be Empty    ${lignes}    msg=La table ${AIRLINE_TABLE} est absente du dictionnaire.
    RETURN    ${lignes}[0][TABCLASS]

Read Field Names Of The Field Catalog
    [Documentation]    Les noms de champs du catalogue de champs lu SUR LUI-MÊME :
    ...    la table se décrit, ce qui donne une liste de champs certifiée exacte
    ...    par la cible, sans rien supposer de la release. Elle sert de
    ...    contre-épreuve au piège du champ inexistant.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${filtre}=    Set Variable    TABNAME EQ '${FIELD_CATALOG}'
    ${lignes}=    Read Business Records    ${FIELD_CATALOG}    ${FIELD_CATALOG_KEY_FIELD}
    ...    filter=${filtre}    alias=${alias}
    ${noms}=    Get Values From Dicts    ${lignes}    ${FIELD_CATALOG_KEY_FIELD}
    RETURN    ${noms}

Read The Field Catalog With Every Real Field
    [Documentation]    Relit le catalogue de champs en demandant TOUS ses champs
    ...    réels : la contre-épreuve du piège `TABLE_WITHOUT_DATA`. Si une liste
    ...    de champs exacte passe là où un seul nom inventé fait échouer la
    ...    lecture entière, alors le code accuse bien la table pour une faute qui
    ...    est dans le champ.
    [Arguments]    ${fields}    ${alias}=${RFC_ALIAS}
    ${filtre}=    Set Variable    TABNAME EQ '${FIELD_CATALOG}'
    ${lignes}=    Read Business Records    ${FIELD_CATALOG}    ${fields}
    ...    filter=${filtre}    limit=1    alias=${alias}
    RETURN    ${lignes}

Airline Filter
    [Documentation]    Clause de sélection sur le code compagnie, ou aucune clause
    ...    quand aucun code n'est donné. Le littéral ABAP est composé ici : une
    ...    suite ne doit pas manipuler de syntaxe de sélection.
    [Arguments]    ${airline}
    IF    '${airline}' == ''    RETURN    ${EMPTY}
    RETURN    ${AIRLINE_KEY_FIELD} EQ '${airline}'

Get Values From Dicts
    [Documentation]    Les valeurs d'une colonne dans une liste de lignes lues.
    ...    Petit utilitaire de lecture, sans rapport avec SAP, gardé ici pour que
    ...    les suites n'aient pas à faire de boucle de collecte.
    [Arguments]    ${rows}    ${key}
    @{valeurs}=    Create List
    FOR    ${ligne}    IN    @{rows}
        Append To List    ${valeurs}    ${ligne}[${key}]
    END
    RETURN    ${valeurs}

# ----------------------------------------------------------- BAPI et LUW

Read User Details
    [Documentation]    Fiche d'un utilisateur par BAPI. L'appel est jugé sur le
    ...    TYPE de ses messages `BAPIRET2` (`E`/`A`/`X` = échec), jamais sur leur
    ...    texte : c'est la convention 3 appliquée au canal RFC.
    [Arguments]    ${user}    ${alias}=${RFC_ALIAS}
    ${detail}=    Call Bapi    ${BAPI_USER_DETAIL}    alias=${alias}    USERNAME=${user}
    RETURN    ${detail}

Reading Details Of An Unknown User Should Be Refused
    [Documentation]    Le même appel sur un utilisateur qui n'existe pas DOIT
    ...    échouer. Retourne le message d'échec pour que la suite vérifie qu'il
    ...    identifie le message bloquant (type et identifiant), et non son
    ...    libellé traduit.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${erreur}=    Run Keyword And Expect Error    *
    ...    Read User Details    ${UNKNOWN_USER}    alias=${alias}
    RETURN    ${erreur}

Read Messages Of An Unknown User Lookup
    [Documentation]    Les messages `BAPIRET2` bruts du même appel, obtenus sans
    ...    passer par le jugement de `Call Bapi` : c'est la source qui permet
    ...    d'asserter le TYPE du message, plutôt que de croire le message
    ...    d'échec sur parole.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${brut}=    Call Rfc    ${BAPI_USER_DETAIL}    alias=${alias}    USERNAME=${UNKNOWN_USER}
    RETURN    ${brut}[RETURN]

Read Flights Of Airline By Bapi
    [Documentation]    Les vols d'une compagnie par BAPI : la même donnée que la
    ...    lecture de table, mais rendue avec son TYPE ABAP (le prix arrive en
    ...    décimal, pas en texte).
    ...
    ...    Le plafond est converti en ENTIER avant l'appel : un paramètre
    ...    numérique ABAP exige un vrai nombre, et Robot rend des chaînes. La
    ...    conversion se fait ICI, jamais dans la bibliothèque, parce que deviner
    ...    le type d'après la forme de la valeur corromprait les champs caractère
    ...    numériques (le numéro de liaison « 0400 » n'est pas l'entier 400).
    [Arguments]    ${airline}    ${limit}=3    ${alias}=${RFC_ALIAS}
    ${plafond}=    Convert To Integer    ${limit}
    ${resultat}=    Call Bapi    ${BAPI_FLIGHT_LIST}    alias=${alias}
    ...    AIRLINE=${airline}    MAX_ROWS=${plafond}
    RETURN    ${resultat}

Close The Open Luw
    [Documentation]    Referme la LUW en cours par un rollback. La campagne
    ...    n'écrit rien : la LUW n'est ouverte que pour prouver qu'on sait la
    ...    refermer, et c'est aussi le réflexe après une BAPI en échec.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${resultat}=    Rollback Bapi Transaction    alias=${alias}
    RETURN    ${resultat}

# ------------------------------------------------------------ Jobs de fond

Wait For Business Job
    [Documentation]    Attend la fin des runs d'un job de fond, en lisant le
    ...    journal des jobs. Jamais de `Sleep` : l'attente est bornée et sondée,
    ...    et le délai est un BUDGET, jamais une temporisation.
    [Arguments]    ${jobname}    ${timeout}=2m    ${alias}=${RFC_ALIAS}
    ${etat}=    Wait For Background Job    ${jobname}    alias=${alias}
    ...    timeout=${timeout}    poll=${JOB_POLL}
    RETURN    ${etat}

Waiting For Job Should Fail
    [Documentation]    Attendre un job dont l'issue ne peut PAS être « terminé »
    ...    DOIT échouer, et le message d'échec est ce qui se lit ensuite. Le
    ...    délai est court parce qu'il borne un budget qu'on sait dépassé
    ...    d'avance : il ne fait patienter personne, et ce n'est donc pas une
    ...    temporisation déguisée.
    [Arguments]    ${jobname}    ${timeout}=${SHORT_JOB_WAIT}    ${alias}=${RFC_ALIAS}
    ${erreur}=    Run Keyword And Expect Error    *
    ...    Wait For Background Job    ${jobname}    alias=${alias}
    ...    timeout=${timeout}    poll=${JOB_POLL}
    RETURN    ${erreur}

Waiting For An Unknown Job Should Fail
    [Documentation]    Attendre un job qui n'existe pas DOIT échouer, et le
    ...    message doit nommer la cause et la piste (préciser le numéro de run,
    ...    journal SM37). Le cas est asserté comme un échec attendu, jamais
    ...    contourné : une attente qui rendrait « terminé » sur un job absent
    ...    serait le vert le plus dangereux du canal.
    [Arguments]    ${timeout}=${SHORT_JOB_WAIT}    ${alias}=${RFC_ALIAS}
    ${erreur}=    Waiting For Job Should Fail    ${UNKNOWN_JOB}    timeout=${timeout}
    ...    alias=${alias}
    RETURN    ${erreur}

Read Job Log Catalogue
    [Documentation]    Le journal des jobs de la cible, lu en ENTIER et rendu
    ...    comme un catalogue de cas d'attente : combien de runs, quels statuts,
    ...    quels statuts par job, et quels jobs porteraient chacune des issues
    ...    de l'attente.
    ...
    ...    Le plafond de lecture vaut 0 (tout le journal) à dessein : un plafond
    ...    ne tronque pas seulement le résultat, il FAUSSE la classification.
    ...    Mesuré sur cette cible, les 200 premières lignes d'un journal qui en
    ...    porte 4719 sont toutes terminées et font conclure que le système ne
    ...    porte que des jobs terminés.
    [Arguments]    ${limit}=0    ${alias}=${RFC_ALIAS}
    ${catalogue}=    Find Background Job Cases    alias=${alias}    rowcount=${limit}
    RETURN    ${catalogue}

Job Log Catalogue
    [Documentation]    Le même catalogue, lu UNE fois par suite puis mémorisé :
    ...    chaque branche de l'attente s'y sert sans relire les milliers de runs
    ...    du journal.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${cache}=    Get Variable Value    ${JOB_LOG_CATALOGUE}    ${NONE}
    IF    $cache is not None    RETURN    ${cache}
    ${catalogue}=    Read Job Log Catalogue    alias=${alias}
    Set Suite Variable    ${JOB_LOG_CATALOGUE}    ${catalogue}
    RETURN    ${catalogue}

Job Carrying Case Or Skip
    [Documentation]    Un job de la cible qui porte le cas d'attente demandé
    ...    (`done`, `aborted_with_finished`, `pipeline`, `unmapped`), CHOISI sur
    ...    le système plutôt que gravé : les jobs d'exploitation d'une image ne
    ...    sont pas ceux d'une autre.
    ...
    ...    Quand aucun job ne porte le cas, la branche est SAUTÉE avec un
    ...    message qui le dit. Elle ne rougit pas (rien n'est cassé) et elle ne
    ...    passe pas en silence (rien n'a été éprouvé).
    [Arguments]    ${case}    ${explication}
    ${catalogue}=    Job Log Catalogue
    ${noms}=    Get From Dictionary    ${catalogue}[cases]    ${case}
    ${message}=    Catenate    Cas « ${case} » non éprouvable sur cette cible :
    ...    ${explication}. La branche est sautée, elle n'est pas déclarée verte.
    Skip If    not $noms    ${message}
    RETURN    ${noms}[0]

Statuses Of Job
    [Documentation]    Les statuts comptés des runs d'un job, tels que le
    ...    journal les porte. C'est la source qui permet de juger le message
    ...    d'échec de l'attente sur des STATUTS, et non sur sa prose.
    [Arguments]    ${jobname}
    ${catalogue}=    Job Log Catalogue
    ${statuts}=    Get From Dictionary    ${catalogue}[jobs]    ${jobname}
    RETURN    ${statuts}

Pending Statuses Of Job
    [Documentation]    Ceux des statuts d'un job que la bibliothèque range dans
    ...    le pipeline (pas encore fini). La liste vient de la bibliothèque,
    ...    jamais d'une copie tenue ici : une carte recopiée dérive.
    [Arguments]    ${jobname}
    ${statuts}=    Statuses Of Job    ${jobname}
    ${modele}=    Get Background Job Status Model
    ${attente}=    Create List
    FOR    ${statut}    IN    @{statuts}
        IF    $statut in $modele['pending']    Append To List    ${attente}    ${statut}
    END
    RETURN    ${attente}

Uncharted Statuses Of Job
    [Documentation]    Ceux des statuts d'un job que la bibliothèque ne
    ...    cartographie PAS. Leur signification n'est pas établie et ne sera pas
    ...    devinée : le domaine `BTCSTATUS` est un `CHAR1` sans liste de valeurs
    ...    dans le dictionnaire. Seul le COMPORTEMENT devant eux s'asserte.
    [Arguments]    ${jobname}
    ${statuts}=    Statuses Of Job    ${jobname}
    ${modele}=    Get Background Job Status Model
    ${inconnus}=    Create List
    FOR    ${statut}    IN    @{statuts}
        IF    $statut not in $modele['labels']    Append To List    ${inconnus}    ${statut}
    END
    RETURN    ${inconnus}

Failure Should Report Every Counted Status
    [Documentation]    Le message d'échec d'une attente doit rendre compte de
    ...    TOUS les statuts comptés pour ce job : c'est ce qui rend le refus
    ...    lisible sans ouvrir SM37, et c'est une assertion portée par des
    ...    lettres de statut, jamais par la prose qui les entoure.
    [Arguments]    ${erreur}    ${jobname}
    ${statuts}=    Statuses Of Job    ${jobname}
    FOR    ${statut}    IN    @{statuts}
        Should Contain    ${erreur}    ${statut}=${statuts}[${statut}]
        ...    msg=L'échec ne rend pas compte du statut ${statut} du job observé.
    END

# ---------------------------------------------- Refus, classés par leur code

Reading A Missing Table Should Be Refused With Code
    [Documentation]    Une table absente du dictionnaire : le refus le plus
    ...    franc du canal, celui dont le code accuse la bonne chose.
    [Arguments]    ${code}    ${alias}=${RFC_ALIAS}
    ${refus}=    Rfc Should Fail With Code    ${code}    Read Rfc Table
    ...    ${MISSING_TABLE}    ${CLIENT_KEY_FIELD}    alias=${alias}
    RETURN    ${refus}

Reading A Missing Field Should Be Refused With Code
    [Documentation]    Un NOM DE CHAMP inexistant sur une table pleine. Le code
    ...    rendu accuse la TABLE d'être sans données alors que la faute est dans
    ...    le champ : c'est le piège de diagnostic du canal, celui qui envoie
    ...    chercher un problème de données là où il y a une faute de frappe. Le
    ...    scénario l'asserte tel quel, bizarrerie assumée, parce que c'est ce
    ...    que la cible fait vraiment.
    [Arguments]    ${code}    ${alias}=${RFC_ALIAS}
    ${refus}=    Rfc Should Fail With Code    ${code}    Read Rfc Table
    ...    ${AIRLINE_TABLE}    ${MISSING_FIELD}    alias=${alias}
    RETURN    ${refus}

Calling A Missing Function Module Should Be Refused With Code
    [Documentation]    Un module fonction qui n'existe pas sur la cible.
    [Arguments]    ${code}    ${alias}=${RFC_ALIAS}
    ${refus}=    Rfc Should Fail With Code    ${code}    Call Rfc
    ...    ${MISSING_FUNCTION}    alias=${alias}
    RETURN    ${refus}

Refusal Should Carry Message Id
    [Documentation]    Vérifie qu'une fiche de refus déjà obtenue porte
    ...    l'identifiant de message attendu (classe, type, numéro). C'est le
    ...    critère FIN qui complète le code technique, et il reste conforme à
    ...    la convention 3 : rien de localisé n'y entre.
    ...
    ...    Pourquoi asserter les deux sur la MÊME fiche plutôt que de provoquer
    ...    deux fois le refus : un second appel prouverait un second refus, pas
    ...    que celui qu'on a observé porte bien les deux caractéristiques.
    [Arguments]    ${refus}    ${identifiant}
    Should Be Equal    ${refus}[message_id]    ${identifiant}
    ...    msg=Le refus porte l'identifiant de message ${refus}[message_id] et non ${identifiant} : le message ABAP rendu n'est pas celui attendu.

Refusal Should Carry No Message Id
    [Documentation]    Vérifie qu'une fiche de refus ne porte AUCUN identifiant
    ...    de message. Ce n'est pas un manque, c'est une preuve : le refus vient
    ...    du runtime client et n'a jamais atteint l'application, donc aucun
    ...    message ABAP n'a pu être émis. Lui en prêter un serait inventer.
    [Arguments]    ${refus}
    Should Be Empty    ${refus}[message_id]
    ...    msg=Un refus du runtime client porte un identifiant de message (${refus}[message_id]) : il aurait donc atteint l'application.

Calling A Missing Function Module Should Be Refused With Message Id
    [Documentation]    Le même refus que `Calling A Missing Function Module
    ...    Should Be Refused With Code`, mais jugé directement sur son
    ...    identifiant de message. Éprouve l'oracle lui-même contre la cible :
    ...    sans cela, l'assertion fine ne serait vérifiée que sur une fiche déjà
    ...    lue, jamais comme critère d'échec.
    [Arguments]    ${identifiant}    ${alias}=${RFC_ALIAS}
    ${refus}=    Rfc Should Fail With Message Id    ${identifiant}    Call Rfc
    ...    ${MISSING_FUNCTION}    alias=${alias}
    RETURN    ${refus}

Calling With An Unknown Parameter Should Be Refused With Code
    [Documentation]    Un paramètre que le module ne déclare pas. Refus du
    ...    runtime RFC, et non de l'application : c'est une autre classe
    ...    d'exception, donc un autre code.
    [Arguments]    ${code}    ${alias}=${RFC_ALIAS}
    # Le nom du paramètre est écrit en clair ICI, et pas porté par une variable :
    # un nom d'argument nommé se lit avant toute substitution, donc une variable
    # à cette place partirait comme un argument positionnel.
    ${refus}=    Rfc Should Fail With Code    ${code}    Call Rfc    ${PING_MODULE}
    ...    alias=${alias}    ZZ_PARAMETRE_INCONNU=x
    RETURN    ${refus}

Reading With An Oversized Selection Clause Should Be Refused
    [Documentation]    Une clause de sélection au-delà de la limite du module :
    ...    la bibliothèque refuse AVANT tout appel réseau. Sans cette garde, le
    ...    dépassement produirait une sélection silencieusement tronquée, donc un
    ...    résultat faux et vert. Retourne le message pour que la suite vérifie
    ...    qu'il nomme la limite et le remède.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${erreur}=    Run Keyword And Expect Error    ValueError:*
    ...    Read Rfc Table    ${AIRLINE_TABLE}    ${AIRLINE_KEY_FIELD}
    ...    alias=${alias}    options=${OVERSIZED_CLAUSE}
    RETURN    ${erreur}

Opening With A Wrong Password Should Be Refused With Code
    [Documentation]    Ouverture refusée pour cause d'identification. Aucun mot
    ...    de passe n'est journalisé, et aucune connexion n'est laissée ouverte.
    [Arguments]    ${code}    ${alias}=refus
    ${refus}=    Rfc Should Fail With Code    ${code}    Open Rfc Connection
    ...    alias=${alias}    ashost=${RFC_ASHOST}    sysnr=${RFC_SYSNR}
    ...    client=${RFC_CLIENT}    user=${RFC_USER}    passwd=${WRONG_PASSWORD}
    ...    lang=${RFC_LANG}
    RETURN    ${refus}

Opening On An Unknown Client Should Be Refused With Code
    [Documentation]    Ouverture refusée pour cause de mandant inexistant. Le mot
    ...    de passe transmis est le VRAI (type `Secret`, jamais déballé dans le
    ...    journal) : sans cela le refus porterait aussi sur l'identification, et
    ...    le test serait vert pour la mauvaise raison.
    [Arguments]    ${code}    ${alias}=refus
    ${refus}=    Rfc Should Fail With Code    ${code}    Open Rfc Connection
    ...    alias=${alias}    ashost=${RFC_ASHOST}    sysnr=${RFC_SYSNR}
    ...    client=${UNKNOWN_CLIENT}    user=${RFC_USER}    passwd=${RFC_PASSWORD}
    ...    lang=${RFC_LANG}
    RETURN    ${refus}

Opening On An Unreachable System Should Be Refused With Code
    [Documentation]    Ouverture refusée avant toute question d'identité : le
    ...    numéro de système ne répond pas. C'est la classe « communication »,
    ...    celle qui distingue un problème de réseau d'un problème de compte.
    [Arguments]    ${code}    ${alias}=refus
    ${refus}=    Rfc Should Fail With Code    ${code}    Open Rfc Connection
    ...    alias=${alias}    ashost=${RFC_ASHOST}    sysnr=${UNREACHABLE_SYSNR}
    ...    client=${RFC_CLIENT}    user=${RFC_USER}    passwd=${RFC_PASSWORD}
    ...    lang=${RFC_LANG}
    RETURN    ${refus}

Count Remote Enabled Function Modules
    [Documentation]    Le nombre de modules fonction ouverts à distance : la
    ...    mesure la plus directe de ce que le canal RFC peut atteindre sur une
    ...    cible. Le critère est technique (mode d'appel du module), donc
    ...    indépendant de la langue et du paramétrage.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${nombre}=    Count Business Records    ${FUNCTION_DIRECTORY}
    ...    ${FUNCTION_NAME_FIELD}    filter=${REMOTE_ENABLED_FILTER}    alias=${alias}
    RETURN    ${nombre}

Count Published Business Interfaces
    [Documentation]    Le nombre d'interfaces métier publiées à l'inventaire,
    ...    c'est-à-dire la taille du catalogue que `List System Bapis` rend.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${inventaire}=    List System Bapis    alias=${alias}
    ${nombre}=    Get Length    ${inventaire}
    RETURN    ${nombre}

Count Modern Programming Model Objects
    [Documentation]    Le nombre d'objets du modèle de programmation moderne
    ...    (définitions et liaisons de service, définitions de comportement),
    ...    lus dans l'annuaire du référentiel. La mesure qui dit à quel point
    ...    une release a basculé vers ce modèle.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${nombre}=    Count Business Records    ${REPOSITORY_DIRECTORY}
    ...    ${REPOSITORY_NAME_FIELD}    filter=${MODERN_MODEL_FILTER}    alias=${alias}
    RETURN    ${nombre}

Read Target Identity For Artifact
    [Documentation]    L'identité de la cible sous la forme qu'un artefact de
    ...    surface conserve, assemblée depuis les DEUX sources indépendantes du
    ...    canal : les attributs de la connexion et la fiche que le système
    ...    publie sur lui-même.
    ...
    ...    L'adresse IP en est volontairement absente : mesurée volatile (elle
    ...    change au redémarrage d'un conteneur), elle distingue deux systèmes à
    ...    un instant donné et ne prouve plus rien le lendemain. Le nom d'hôte
    ...    retenu est celui que le SYSTÈME publie, jamais celui des attributs de
    ...    connexion, qui est le poste client.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${connexion}=    Read System Identity    alias=${alias}
    ${systeme}=    Read System Information    alias=${alias}
    ${identite}=    Create Dictionary    system_id=${systeme}[RFCSYSID]
    ...    client=${connexion}[client]    release=${systeme}[RFCSAPRL]
    ...    kernel=${systeme}[RFCKERNRL]    database=${systeme}[RFCDBSYS]
    ...    operating_system=${systeme}[RFCOPSYS]    host=${systeme}[RFCHOST]
    RETURN    ${identite}

Measure Rfc Channel Surface
    [Documentation]    Les décomptes qui composent la surface du canal sur une
    ...    cible : ce qu'elle expose (modules ouverts à distance, interfaces
    ...    métier, objets du modèle moderne) et ce qu'elle porte comme données
    ...    de démonstration. Rendu comme une carte nom métier vers entier, prête
    ...    pour `Write Rfc Surface Artifact`.
    ...
    ...    Le périmètre de l'artefact est DÉRIVÉ de cette carte : ajouter une
    ...    mesure ici change le périmètre, et deux artefacts de périmètres
    ...    différents sont alors déclarés non comparables plutôt que comparés à
    ...    tort. C'est voulu : une mesure absente d'un côté ne vaut pas zéro.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${modules}=    Count Remote Enabled Function Modules    alias=${alias}
    ${interfaces}=    Count Published Business Interfaces    alias=${alias}
    ${modernes}=    Count Modern Programming Model Objects    alias=${alias}
    ${tables_modernes}=    Count Modern Model Tables    alias=${alias}
    ${compagnies}=    Count Airlines    alias=${alias}
    ${compagnies_modernes}=    Count Modern Airlines    alias=${alias}
    ${voyages}=    Count Travels    alias=${alias}
    ${produits}=    Count Products    alias=${alias}
    ${mesures}=    Create Dictionary
    ...    remote_enabled_function_modules=${modules}
    ...    published_business_interfaces=${interfaces}
    ...    modern_programming_model_objects=${modernes}
    ...    modern_model_tables=${tables_modernes}
    ...    classic_airlines=${compagnies}
    ...    modern_airlines=${compagnies_modernes}
    ...    travels=${voyages}
    ...    products=${produits}
    RETURN    ${mesures}

Write Channel Surface Of Target
    [Documentation]    Mesure la surface de la cible ouverte et l'écrit dans un
    ...    artefact déterministe, identité comprise. Retourne la preuve
    ...    (`path`, `sha256`, `summary`) : deux exécutions sur la même cible
    ...    lisant les mêmes chiffres rendent le MÊME hash, l'horodatage étant
    ...    exclu du calcul.
    [Arguments]    ${chemin}    ${cible}    ${alias}=${RFC_ALIAS}
    ${identite}=    Read Target Identity For Artifact    alias=${alias}
    ${mesures}=    Measure Rfc Channel Surface    alias=${alias}
    ${composants}=    Read Software Components    alias=${alias}
    ${preuve}=    Write Rfc Surface Artifact    ${chemin}    ${cible}
    ...    ${identite}    ${mesures}    components=${composants}
    RETURN    ${preuve}

Compare Channel Surfaces
    [Documentation]    Compare deux artefacts de surface, hors système : c'est
    ...    la comparaison entre releases que le canal n'avait pas, et elle ne
    ...    demande aucune connexion.
    [Arguments]    ${chemin_a}    ${chemin_b}
    ${comparaison}=    Compare Rfc Surface Artifacts    ${chemin_a}    ${chemin_b}
    RETURN    ${comparaison}

Calling A Closed Rfc Channel Should Name The Opening Keyword
    [Documentation]    Un alias jamais ouvert, ou déjà fermé par un teardown, est
    ...    le refus le plus fréquent du canal. Il n'a PAS de code technique (il
    ...    vient de la bibliothèque, pas du serveur) : le contrat est donc que le
    ...    message nomme le keyword d'ouverture, pour que la correction soit
    ...    évidente au lieu d'être cherchée côté SAP.
    [Arguments]    ${alias}
    ${erreur}=    Run Keyword And Expect Error    *
    ...    Call Rfc    ${PING_MODULE}    alias=${alias}
    Should Contain    ${erreur}    Open Rfc Connection
    ...    msg=Le refus d'un alias fermé ne nomme pas le keyword d'ouverture.
    RETURN    ${erreur}
