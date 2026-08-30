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
...                 Vocabulaire métier du **croisement DDIC et OData** : le même
...                 fait de données vérifié par deux canaux indépendants sur un
...                 seul système (plan `specs/croisement-ddic-odata-ecc-s4hana.md`).
...
...                 Cette resource ne pilote ni l'écran ni le réseau : elle
...                 COMPOSE les deux vocabulaires existants (`ecc_keywords` pour
...                 SE16 et le dictionnaire, `api_keywords` pour OData) et la
...                 logique pure de `sapfx_common.cross_channel`, importée comme
...                 bibliothèque Robot pour qu'une suite atteigne chaque
...                 primitive par un keyword.
...
...                 Convention 1 : aucune suite ne cite un chemin de service
...                 OData ni un nom de table. Les deux vivent ICI, et surtout le
...                 **dictionnaire de correspondance** entity set / table, qui
...                 est une donnée de configuration nommée métier. Il n'est
...                 jamais déduit d'une convention de nom : `SNWD_CONTACT`
...                 existe, s'ouvre dans SE16 et contient 0 entrée quand
...                 `ContactSet` en publie 41, et la table réelle est
...                 `SNWD_BPA_CONTACT`. Chaque couple déclaré ici est PROUVÉ par
...                 le test (les deux comptages sont exécutés et confrontés) ;
...                 un entity set sans couple déclaré est rapporté, jamais
...                 apparié en silence.
...
...                 Convention 3 : les verdicts portent sur des entiers, des
...                 noms techniques, des statuts HTTP et des codes d'erreur
...                 OData, jamais sur un message localisé.

Library             Collections
Library             DateTime
Library             OperatingSystem
Library             String
Library             sapfx_common.cross_channel
Library             sapfx_common.write_simulation
Resource            ecc_keywords.resource
Resource            api_keywords.resource


*** Variables ***
# --- Services du périmètre (convention 1 : les chemins vivent ici) ---
${SERVICE_GWSAMPLE_BASIC}       /sap/opu/odata/iwbep/GWSAMPLE_BASIC
${SERVICE_EPM_SHOP}             /sap/opu/odata/sap/SEPMRA_SHOP
${SERVICE_EPM_PROD_MAN}         /sap/opu/odata/sap/SEPMRA_PROD_MAN
# Modèle de démonstration RAP (« flight ») : ses quatre ensembles d'entités
# correspondent un pour un à des tables du dictionnaire, comptages croisés
# faits le 2026-08-22 (16, 20, 40, 47).
${SERVICE_FLIGHT_RAP}           /sap/opu/odata/sap/Z_BIND_FLIGHT_R
@{CAMPAIGN_SERVICES}            ${SERVICE_GWSAMPLE_BASIC}    ${SERVICE_EPM_SHOP}
...                             ${SERVICE_EPM_PROD_MAN}    ${SERVICE_FLIGHT_RAP}

# --- Alias de champs d'un couple : les renommages métier qu'aucun normaliseur
# ne peut trouver. `BusinessPartnerID` face à `BP_ID` ne se déduit d'aucune
# règle, et c'est pourtant la clé de l'entity type.
&{ALIASES_BUSINESS_PARTNER}     BusinessPartnerID=BP_ID    BusinessPartnerRole=BP_ROLE
&{ALIASES_NONE}

# --- Dictionnaire de correspondance entity set / table -----------------------
# Un couple = un enregistrement : ensemble d'entités, service, table DDIC,
# filtres éventuels de chaque côté, verdict attendu et motif quand il n'est pas
# `equal`. Verdicts admis : `equal`, `equal_under_filter`, `not_comparable`.
&{COUPLE_PRODUCTS_GWSAMPLE}     entity_set=ProductSet    service=${SERVICE_GWSAMPLE_BASIC}
...                             table=SNWD_PD    expected=equal    aliases=${ALIASES_NONE}
&{COUPLE_PRODUCTS_SHOP}         entity_set=Products    service=${SERVICE_EPM_SHOP}
...                             table=SNWD_PD    expected=equal    aliases=${ALIASES_NONE}
&{COUPLE_BUSINESS_PARTNERS}     entity_set=BusinessPartnerSet    service=${SERVICE_GWSAMPLE_BASIC}
...                             table=SNWD_BPA    expected=equal    aliases=${ALIASES_BUSINESS_PARTNER}
&{COUPLE_SALES_ORDERS}          entity_set=SalesOrderSet    service=${SERVICE_GWSAMPLE_BASIC}
...                             table=SNWD_SO    expected=equal    aliases=${ALIASES_NONE}
&{COUPLE_SALES_ORDER_ITEMS}     entity_set=SalesOrderLineItemSet    service=${SERVICE_GWSAMPLE_BASIC}
...                             table=SNWD_SO_I    expected=equal    aliases=${ALIASES_NONE}
&{COUPLE_CONTACTS}              entity_set=ContactSet    service=${SERVICE_GWSAMPLE_BASIC}
...                             table=SNWD_BPA_CONTACT    expected=equal    aliases=${ALIASES_NONE}
&{COUPLE_SUPPLIERS_SHOP}        entity_set=Suppliers    service=${SERVICE_EPM_SHOP}
...                             table=SNWD_BPA    ddic_filter=BP_ROLE=02
...                             expected=equal_under_filter
...                             reason=le service ne projette que les partenaires de rôle fournisseur
...                             aliases=${ALIASES_NONE}
&{COUPLE_SUPPLIERS_PROD_MAN}    entity_set=SEPMRA_C_PD_Supplier    service=${SERVICE_EPM_PROD_MAN}
...                             table=SNWD_BPA    ddic_filter=BP_ROLE=02
...                             expected=equal_under_filter
...                             reason=meme projection metier que Suppliers
...                             aliases=${ALIASES_NONE}
&{COUPLE_PRODUCTS_DRAFT}        entity_set=SEPMRA_C_PD_Product    service=${SERVICE_EPM_PROD_MAN}
...                             table=SNWD_PD    api_filter=IsActiveEntity eq true
...                             expected=equal_under_filter
...                             reason=vue draft-enabled : le compte nu agrege actives et brouillons
...                             aliases=${ALIASES_NONE}
&{COUPLE_SHOPPING_CARTS}        entity_set=ShoppingCarts    service=${SERVICE_EPM_SHOP}
...                             table=${EMPTY}    expected=not_comparable
...                             reason=perimetre lie a l utilisateur connecte
...                             aliases=${ALIASES_NONE}
# Modèle RAP « flight » : quatre couples prouvés le 2026-08-22 par comptage
# croisé (16, 20, 40, 47 des deux côtés). Seul l'alias RELEVÉ live est déclaré :
# la propriété `AirlineID` face au champ `CARRIER_ID` est un renommage métier,
# du même genre que `BusinessPartnerID` face à `BP_ID`, et aucun normaliseur ne
# le trouve. Les champs des trois autres tables n'ayant pas été relevés, leurs
# couples n'entrent ici qu'avec ce qui est prouvé : leur volumétrie.
&{ALIASES_AIRLINE}              AirlineID=CARRIER_ID
&{COUPLE_AIRLINES}              entity_set=Airline    service=${SERVICE_FLIGHT_RAP}
...                             table=/DMO/CARRIER    expected=equal
...                             aliases=${ALIASES_AIRLINE}
&{COUPLE_CONNECTIONS}           entity_set=Connection    service=${SERVICE_FLIGHT_RAP}
...                             table=/DMO/CONNECTION    expected=equal
...                             aliases=${ALIASES_NONE}
&{COUPLE_FLIGHTS}               entity_set=Flight    service=${SERVICE_FLIGHT_RAP}
...                             table=/DMO/FLIGHT    expected=equal
...                             aliases=${ALIASES_NONE}
&{COUPLE_AIRPORTS}              entity_set=Airport    service=${SERVICE_FLIGHT_RAP}
...                             table=/DMO/AIRPORT    expected=equal
...                             aliases=${ALIASES_NONE}
@{CROSS_CHANNEL_COUPLES}        ${COUPLE_PRODUCTS_GWSAMPLE}    ${COUPLE_PRODUCTS_SHOP}
...                             ${COUPLE_BUSINESS_PARTNERS}    ${COUPLE_SALES_ORDERS}
...                             ${COUPLE_SALES_ORDER_ITEMS}    ${COUPLE_CONTACTS}
...                             ${COUPLE_SUPPLIERS_SHOP}    ${COUPLE_SUPPLIERS_PROD_MAN}
...                             ${COUPLE_PRODUCTS_DRAFT}    ${COUPLE_SHOPPING_CARTS}
...                             ${COUPLE_AIRLINES}    ${COUPLE_CONNECTIONS}
...                             ${COUPLE_FLIGHTS}    ${COUPLE_AIRPORTS}

# --- Couples dont le contrat de champs est instruit (scénario 5) -------------
@{CROSS_CHANNEL_FIELD_COUPLES}    ${COUPLE_PRODUCTS_GWSAMPLE}    ${COUPLE_BUSINESS_PARTNERS}

# --- Liste blanche métier des cibles d'écriture ------------------------------
# « Déclaré modifiable » est un critère NÉCESSAIRE, jamais suffisant : le choix
# des cibles d'écriture reste une décision métier, portée ici.
@{WRITE_ALLOWLIST}              Reviews    Products    ShoppingCartItems

# --- Cible de la simulation d'écriture réversible ----------------------------
# Périmètre d'écriture par l'ÉCRAN : une seule table, déclarée ici et nulle
# part ailleurs (le mot-clé d'écriture refuse tout ce qui n'y figure pas).
# Trois conditions, toutes relevées live le 2026-08-22, et la première est celle
# que le `$metadata` ne peut pas donner :
#   1. le dictionnaire AUTORISE la maintenance (`MAINFLAG`) : les onze tables
#      `/DMO/*` du modèle RAP ne l'autorisent pas, et SE16 les refuse en type
#      `E` quelles que soient les autorisations de l'utilisateur ;
#   2. la table est OBSERVABLE par le canal API (sinon le cycle ne prouverait
#      que l'écran) : `SNWD_PD_CATGOS` est projetée par `SubCategories` du
#      service « Shop » ET par l'aide à la recherche `VH_CategorySet` de
#      `GWSAMPLE_BASIC`, deux constatations indépendantes ;
#   3. sa structure est minimale (deux champs métier), sans dépendance à un
#      autre enregistrement : la valeur de rattachement est relue dans les
#      données existantes, jamais inventée.
@{WRITE_SIMULATION_ALLOWLIST}    SNWD_PD_CATGOS
&{WRITE_SIMULATION_TARGET}      table=SNWD_PD_CATGOS    key_field=CATEGORY
...                             value_field=MAIN_CATEGORY
...                             service=${SERVICE_EPM_SHOP}    entity_set=SubCategories
...                             entity_key=Id    entity_value=MainCategoryId
...                             reference_set=MainCategories    reference_key=Id
...                             mirror_service=${SERVICE_GWSAMPLE_BASIC}
...                             mirror_entity_set=VH_CategorySet
# Identifiant de test : reconnaissable au premier coup d'oeil, sans allure
# métier, et hors de tout espace de nom livré. Surchargeable en ligne de
# commande, jamais deviné.
${WRITE_SIMULATION_KEY}         ZZ_SAPFX_TEST_CATEGORY


*** Keywords ***
Cross Channel Preflight
    [Documentation]    Préflight des DEUX canaux en un verdict unique : la
    ...    Gateway répond, la session GUI est saine (scripting activé, une
    ...    seule session, aucune modale héritée) et les deux canaux regardent
    ...    le MÊME mandant. Retourne le périmètre normalisé de la campagne,
    ...    à consigner dans l'artefact.
    ...
    ...    Le refus de mandants divergents est délibérément bloquant : le
    ...    comptage SE16 se fait dans le mandant de connexion GUI et le
    ...    `$count` dans celui du canal API. Les faire diverger comparerait
    ...    deux populations et fabriquerait un écart qui n'existe pas.
    [Arguments]    ${services}=${CAMPAIGN_SERVICES}    ${max_entity_sets}=60
    ...    ${max_couples}=20    ${max_field_contracts}=5    ${alias}=${API_ALIAS}
    Api Channel Should Be Available    alias=${alias}
    ${ecc_client}=    Ecc Session Should Be Clean
    ${api_client}=    Api Channel Client    alias=${alias}
    ${scope}=    Validate Cross Channel Scope    ${services}    ${ecc_client}
    ...    ${api_client}    ${max_entity_sets}    ${max_couples}    ${max_field_contracts}
    RETURN    ${scope}

Business Services Should Be Published
    [Documentation]    Recoupe le périmètre demandé avec le catalogue de la
    ...    cible : un service du périmètre absent du catalogue est un **écart
    ...    de portabilité rapporté** (cette cible ne le publie pas), pas une
    ...    erreur silencieuse. C'est l'information utile quand la même campagne
    ...    passe d'une cible ECC à une cible S/4HANA. Retourne la couverture
    ...    (`catalog_size`, `published`, `missing`), à consigner dans
    ...    l'artefact ; l'échec n'est levé que si ``required`` est vrai.
    [Arguments]    ${services}=${CAMPAIGN_SERVICES}    ${required}=${True}
    ...    ${alias}=${API_ALIAS}
    ${catalog}=    List Available Business Services    alias=${alias}
    ${coverage}=    Catalog Coverage    ${services}    ${catalog}
    IF    ${required}
        Should Be Empty    ${coverage}[missing]
        ...    msg=Services du périmètre absents du catalogue de la cible : ${coverage}[missing]
    END
    RETURN    ${coverage}

List Business Service Entity Sets
    [Documentation]    Fiche de contrat de chaque ensemble d'entités d'un
    ...    service : clés, adressabilité et capacités d'écriture DÉCLARÉES,
    ...    caractère draft-enabled, nombre de propriétés. Tirée du service
    ...    lui-même, jamais d'une convention. Une limite atteinte produit un
    ...    indicateur de troncature visible.
    [Arguments]    ${service}    ${max_entity_sets}=60    ${alias}=${API_ALIAS}
    ${meta}=    Read Business Service Contract    ${service}    alias=${alias}
    ${contract}=    Describe Service Contract    ${meta}    ${max_entity_sets}
    RETURN    ${contract}

Cross Channel Existence Should Be Consistent
    [Documentation]    Sonde chaque ensemble d'entités ADRESSABLE du service et
    ...    rend le verdict par ensemble. Les ensembles déclarés non adressables
    ...    sont écartés du sondage et consignés comme tels : leur refus n'est
    ...    pas une anomalie, c'est une déclaration honorée. L'anomalie, la
    ...    seule, est un ensemble déclaré adressable qui ne répond pas.
    ...    Retourne la liste des verdicts ; l'assertion porte sur l'absence de
    ...    `unexpected_refusal`.
    [Arguments]    ${contract}    ${max_entity_sets}=60    ${alias}=${API_ALIAS}
    ${addressable}=    Evaluate
    ...    [e["entity_set"] for e in $contract["entity_sets"] if e["addressable"]]
    ${probe}=    Probe Business Entity Sets    ${contract}[service_path]    ${addressable}
    ...    max_entity_sets=${max_entity_sets}    alias=${alias}
    ${verdicts}=    Classify Entity Set Probes    ${contract}    ${probe}[probed]
    ${unexpected}=    Evaluate
    ...    [v for v in $verdicts if v["verdict"] == "unexpected_refusal"]
    Should Be Empty    ${unexpected}
    ...    msg=Ensembles déclarés adressables mais refusés (statut HTTP et code technique) : ${unexpected}
    RETURN    ${verdicts}

Cross Channel Volume Should Match
    [Documentation]    Croise la volumétrie d'UN couple déclaré : comptage
    ...    OData d'un côté, comptage SE16 de l'autre, filtres déclarés
    ...    appliqués de chaque côté, puis confrontation selon le verdict
    ...    attendu du couple. Retourne un verdict JSON-safe.
    ...
    ...    Un couple `equal_under_filter` fait relever EN PLUS le compte sans
    ...    filtre : l'écart est ainsi consigné au lieu d'être masqué, et c'est
    ...    lui qui documente la projection métier ou les brouillons. Un couple
    ...    `not_comparable` n'est jamais asserté en égalité : ses comptes sont
    ...    relevés et son motif consigné.
    [Arguments]    ${couple}
    ${entity_set}=    Set Variable    ${couple}[entity_set]
    ${path}=    Set Variable    ${couple}[service]/${entity_set}
    ${api_filter}=    Evaluate    $couple.get("api_filter") or ""
    ${table}=    Evaluate    $couple.get("table") or ""
    ${ddic_filter}=    Evaluate    $couple.get("ddic_filter") or ""
    ${unfiltered}=    Set Variable    ${None}
    IF    $api_filter
        ${api_count}=    Count Business Entities With Filter    ${path}    ${api_filter}
        ${unfiltered}=    Count Business Entities    ${path}
    ELSE
        ${api_count}=    Count Business Entities    ${path}
    END
    IF    $table and $ddic_filter
        ${field}    ${value}=    Split String    ${ddic_filter}    \=    1
        ${ddic_count}=    Count Table Entries With Criteria    ${table}    ${field}=${value}
    ELSE IF    $table
        ${ddic_count}=    Count Table Entries    ${table}
    ELSE
        ${ddic_count}=    Set Variable    ${None}
    END
    ${verdict}=    Build Couple Verdict    ${couple}    ${api_count}    ${ddic_count}
    ...    ${unfiltered}
    IF    '${verdict}[expected]' != 'not_comparable'
        Should Be True    ${verdict}[match]
        ...    msg=Volumétrie divergente pour '${entity_set}' face à '${table}' : API ${verdict}[api_count] contre DDIC ${verdict}[ddic_count] (attendu ${verdict}[expected]).
    END
    RETURN    ${verdict}

Cross Channel Field Contract
    [Documentation]    Croise le contrat de champs d'UN couple : propriétés de
    ...    l'entity type d'un côté, champs DD03L de la version active de
    ...    l'autre, rapprochés en trois passes ordonnées (alias déclarés, puis
    ...    normalisation consciente des acronymes, puis rien).
    ...
    ...    Retourne les trois ensembles (appariés, propriétés orphelines,
    ...    champs DDIC orphelins) : c'est ce triplet qui rend une dérive de
    ...    schéma lisible, là où un verdict binaire ne dirait rien. Seule
    ...    assertion : les **clés** de l'entity type sont appariées, par alias
    ...    si nécessaire. Une clé non appariée est le signal fort d'une dérive
    ...    de schéma ou d'un alias manquant.
    [Arguments]    ${couple}    ${max_fields}=200
    ${info}=    Business Service Should Expose Entity Set    ${couple}[service]
    ...    ${couple}[entity_set]
    ${fields}=    Read Table Fields    ${couple}[table]    max_fields=${max_fields}
    ${aliases}=    Evaluate    $couple.get("aliases") or {}
    ${contract}=    Compare Odata Properties With Ddic Fields    ${info}[properties]
    ...    ${fields}    aliases=${aliases}    keys=${info}[keys]
    Should Be Empty    ${contract}[unmatched_keys]
    ...    msg=Clé(s) de '${couple}[entity_set]' sans champ DDIC apparié : ${contract}[unmatched_keys] (déclarer un alias dans resources/cross_channel_keywords.resource).
    ${record}=    Create Dictionary    entity_set=${couple}[entity_set]
    ...    service=${couple}[service]    table=${couple}[table]
    ...    summary=${contract}[summary]    matched=${contract}[matched]
    ...    unmatched_properties=${contract}[unmatched_properties]
    ...    unmatched_fields=${contract}[unmatched_fields]
    ...    unmatched_keys=${contract}[unmatched_keys]
    RETURN    ${record}    ${fields}

List Write Simulation Candidates
    [Documentation]    Candidats à une FUTURE simulation d'écriture, identifiés
    ...    sans rien écrire. Deux gardes, dans cet ordre : seule une capacité
    ...    réellement DÉCLARÉE par le service engage (une capacité obtenue par
    ...    défaut ne prouve rien, le service s'est tu), puis la liste blanche
    ...    métier. Un service qui ne déclare aucune restriction ne produit donc
    ...    aucun candidat par ce seul fait.
    [Arguments]    ${service}    ${allowlist}=${WRITE_ALLOWLIST}
    ...    ${alias}=${API_ALIAS}
    ${meta}=    Read Business Service Contract    ${service}    alias=${alias}
    ${qualified}=    Write Simulation Candidates    ${meta}
    ${shortlist}=    Shortlist Write Candidates    ${qualified}    ${allowlist}
    FOR    ${candidate}    IN    @{shortlist}
        Set To Dictionary    ${candidate}    service=${service}
    END
    RETURN    ${shortlist}

Write Cross Channel Artifact
    [Documentation]    Écrit l'artefact JSON déterministe de la cible et
    ...    retourne sa preuve (`path`, `sha256`, `summary`). L'empreinte exclut
    ...    l'horodatage : deux exécutions sur les mêmes données donnent la même
    ...    empreinte. Les paramètres de campagne font partie de l'artefact,
    ...    afin qu'une comparaison entre périmètres différents soit impossible
    ...    par accident.
    [Arguments]    ${path}    ${target_id}    ${scope}    ${catalog}
    ...    ${services}    ${probes}    ${couples}    ${contracts}    ${tables}
    ...    ${candidates}    ${truncated}=${False}
    ${observed}=    Get Current Date    time_zone=UTC    result_format=%Y-%m-%dT%H:%M:%S+00:00
    ${artifact}=    Build Cross Channel Artifact    ${target_id}    ${scope}
    ...    ${observed}    catalog=${catalog}    services=${services}
    ...    probes=${probes}    couples=${couples}    contracts=${contracts}
    ...    tables=${tables}    candidates=${candidates}    truncated=${truncated}
    ${content}=    Cross Channel Artifact Json    ${artifact}
    ${digest}=    Cross Channel Hash    ${artifact}
    Create File    ${path}    ${content}
    ${proof}=    Create Dictionary    path=${path}    sha256=${digest}
    ...    summary=${artifact}[summary]
    RETURN    ${proof}

Count Business Entities With Key
    [Documentation]    Nombre d'entités portant UNE clé donnée : 0 ou 1 sur un
    ...    ensemble d'entités correctement modélisé. C'est la façon
    ...    locale-indépendante ET sans exception de demander « cette entité
    ...    existe-t-elle » : une lecture par clé d'une entité absente répond
    ...    HTTP 404 et lève, ce qui obligerait à interpréter un message
    ...    d'erreur pour distinguer « absente » de « service en panne ».
    [Arguments]    ${path}    ${key_property}    ${key_value}
    ...    ${alias}=${API_ALIAS}
    ${count}=    Count Business Entities With Filter    ${path}
    ...    ${key_property} eq '${key_value}'    alias=${alias}
    RETURN    ${count}

Read Business Entity By Key
    [Documentation]    L'entité portant UNE clé donnée, projetée sur les champs
    ...    demandés : liste d'un élément quand elle existe, liste VIDE sinon.
    ...    Même raison qu'au-dessus de passer par un filtre plutôt que par le
    ...    chemin de clé : l'absence est une donnée, pas une exception.
    [Arguments]    ${path}    ${key_property}    ${key_value}    ${fields}
    ...    ${alias}=${API_ALIAS}
    ${rows}=    Get Odata Entities    ${path}    alias=${alias}
    ...    filter=${key_property} eq '${key_value}'    select=${fields}
    RETURN    ${rows}

Record Reversibility Observation
    [Documentation]    Écrit l'observation DATÉE de réversibilité d'un cycle
    ...    d'écriture et retourne son verdict complet. C'est la preuve que la
    ...    campagne de croisement ne peut pas produire : elle laisse
    ...    `reversibility_observed` à `unknown` parce qu'une annotation de
    ...    métadonnées dit ce que le SERVICE permet, jamais ce qui est
    ...    réellement réversible. Le fichier est déterministe (clés triées) et
    ...    ne porte ni identifiant d'utilisateur ni secret.
    [Arguments]    ${path}    ${observation_fields}
    ${observed}=    Get Current Date    time_zone=UTC    result_format=%Y-%m-%dT%H:%M:%S+00:00
    ${observation}=    Build Reversibility Observation    observed_at_utc=${observed}
    ...    &{observation_fields}
    ${content}=    Reversibility Observation Json    ${observation}
    Create File    ${path}    ${content}
    RETURN    ${observation}

Compare Cross Channel Artifact Files
    [Documentation]    Compare deux artefacts écrits par `Write Cross Channel
    ...    Artifact` : charge les deux fichiers, journalise le rapport Markdown
    ...    et retourne la comparaison JSON-safe. Hors ligne : ne touche ni
    ...    l'écran ni le réseau. Des périmètres différents marquent la
    ...    comparaison non équivalente au lieu de produire des écarts
    ...    trompeurs.
    [Arguments]    ${path_a}    ${path_b}
    ${raw_a}=    Get File    ${path_a}
    ${raw_b}=    Get File    ${path_b}
    ${comparison}=    Compare Cross Channel Artifacts    ${raw_a}    ${raw_b}
    ${report}=    Render Cross Channel Report    ${comparison}
    Log    ${report}
    RETURN    ${comparison}
