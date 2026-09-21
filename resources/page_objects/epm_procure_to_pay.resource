*** Settings ***
Documentation       **EXEMPLE À PERSONNALISER** : ce fichier porte le vocabulaire
...                 métier du LABORATOIRE de ce dépôt (identifiants, chemins, noms
...                 de tables et de services relevés live sur SES cibles). Beaucoup
...                 s'y réutilise tel quel sur un autre système (écrans et services
...                 standard), mais rien n'y fait autorité : à VÉRIFIER sur votre
...                 cible et à adapter à votre métier. Ce qui fait foi partout,
...                 c'est `src/`, les bibliothèques, qui portent les capacités :
...                 voir `resources/README.md`.
...
...                 Vocabulaire métier du scénario **Procure-to-Pay EPM
...                 cross-canal** (plan `specs/commande-achat-epm-procure-to-pay.md`) :
...                 la réception de marchandise d'une commande d'achat EPM
...                 (service OData v2 `SEPMRA_PO_MAN`) incrémente le stock
...                 physique du produit concerné (table `SNWD_STOCK`, lue par
...                 SE16), vérifié par un canal indépendant de celui qui écrit.
...
...                 Aucune application Fiori de gestion des commandes d'achat
...                 n'existe sur la cible de ce dépôt (catalogue du launchpad
...                 vérifié live, voir le plan) : la commande n'est jamais
...                 créée par ce vocabulaire, elle est DÉCOUVERTE parmi les
...                 commandes déjà confirmées (statut ``F``), sur le MÊME objet
...                 métier qu'une telle application piloterait si elle existait
...                 ici (``SEPMRA_C_PO_PurOrd`` / fonction ``Goodsreceipt``).
...
...                 Compose les deux vocabulaires existants (``ecc_keywords``
...                 pour SE16, ``api_keywords`` pour l'ouverture du canal API) :
...                 convention 1, aucun chemin de service ni nom de table ne
...                 doit fuir dans une suite.

Library             Collections
Resource            ../ecc_keywords.resource
Resource            ../api_keywords.resource


*** Variables ***
# --- Service du périmètre (convention 1 : les chemins vivent ici) ---
${EPM_PO_MAN_SERVICE}          /sap/opu/odata/sap/SEPMRA_PO_MAN
# Convention SADL : le GUID nul désigne l'entité ACTIVE (non brouillon) d'un
# service à brouillons, quelle que soit la commande visée.
${EPM_PO_MAN_ACTIVE_DRAFT_UUID}    00000000-0000-0000-0000-000000000000
# Statut « Confirmed » (cf. SEPMRA_I_PurOrdOverallStatus) : la commande est
# passée l'approbation et n'a pas encore reçu sa marchandise.
${EPM_PO_STATUS_CONFIRMED}     F
${EPM_PO_STATUS_DELIVERED}     D
# Plafonds de lecture SE16 : les deux tables dépassent le défaut (205 et 2665
# lignes mesurées live), et aucune des deux ne se filtre de façon fiable par
# critère de sélection sur cette cible (voir le plan, section Points de
# vigilance) : la lecture se fait donc en grille COMPLÈTE puis filtre par
# contenu, jamais par un critère dérivé.
${SNWD_PD_MAX_HITS}            10000
${SNWD_STOCK_MAX_HITS}         50000
# Accord EXPLICITE d'écriture. Vide par défaut : sans lui, la campagne est
# SAUTÉE avant même l'ouverture d'un canal, y compris dans un run complet de
# `tests/robot/`. La réception de marchandise n'a pas de geste inverse dans ce
# modèle de démonstration (voir le plan) et consomme une ressource RÉELLE et
# FINIE (une commande confirmée), donc un tag seul ne suffit pas (même
# convention que `WRITE_SIMULATION_OPT_IN` / `ABAP_FLP_WRITE_OPT_IN`).
${PROCURE_TO_PAY_WRITE_OPT_IN}    ${EMPTY}


*** Keywords ***
Open Procure To Pay Channels
    [Documentation]    Suite Setup : derrière l'accord explicite d'écriture,
    ...    ouvre les deux canaux du scénario (API pour l'écriture métier, SAP
    ...    GUI pour la vérification physique indépendante) et bascule SE16 en
    ...    grille ALV. Sans l'accord, TOUS les tests sont sautés et AUCUN
    ...    canal n'est ouvert : ce qui rend la suite inoffensive dans un run
    ...    complet, là où un tag seul dépend de la mémoire de celui qui lance
    ...    la commande.
    ${opte}=    Evaluate
    ...    str($PROCURE_TO_PAY_WRITE_OPT_IN).strip().lower() in ('yes', 'true', '1', 'on')
    IF    not ${opte}
        Skip    Campagne d'ECRITURE (réception de marchandise, non reversible) sur un système reel : accord explicite requis (-v PROCURE_TO_PAY_WRITE_OPT_IN:yes).
    END
    Open Api Channel
    ecc_keywords.Open SAP And Log In
    Use ALV Grid In Data Browser

Close Procure To Pay Channels
    [Documentation]    Suite Teardown : ferme les deux canaux, même si un
    ...    scénario a échoué.
    Run Keyword And Ignore Error    Close Api Channel
    Run Keyword And Ignore Error    Close SAP

Find Confirmed Purchase Order Eligible For Goods Receipt
    [Documentation]    Découvre une commande d'achat EPM **déjà confirmée**
    ...    (statut ``F``) et son premier poste actif, sans jamais en créer
    ...    une : la création de poste sur une commande brouillon échoue côté
    ...    serveur sur ce système (voir le plan). Essaie CHAQUE commande du
    ...    lot (dans l'ordre reçu) jusqu'à en trouver une qui porte au moins
    ...    un poste actif : une commande confirmée sans poste actif ne fait
    ...    pas conclure à une absence de candidat. Retourne un dictionnaire
    ...    ``{purchase_order, item, product, quantity, quantity_unit}``, ou
    ...    ``${NONE}`` si aucune commande éligible n'a été trouvée (jamais un
    ...    échec : un système sans commande confirmée n'est pas une panne du
    ...    test).
    [Arguments]    ${top}=20
    ${entetes}=    Get Odata Entities    ${EPM_PO_MAN_SERVICE}/SEPMRA_C_PO_PurOrd
    ...    top=${top}
    ...    filter=IsActiveEntity eq true and PurchaseOrderOverallStatus eq '${EPM_PO_STATUS_CONFIRMED}'
    FOR    ${entete}    IN    @{entetes}
        ${numero}=    Evaluate    $entete['PurchaseOrder']
        ${postes}=    Get Odata Entities    ${EPM_PO_MAN_SERVICE}/SEPMRA_C_PO_PurOrdItem
        ...    filter=PurchaseOrder eq '${numero}' and IsActiveEntity eq true
        IF    $postes
            ${poste}=    Evaluate    $postes[0]
            ${commande}=    Create Dictionary
            ...    purchase_order=${numero}
            ...    item=${poste}[PurchaseOrderItem]
            ...    product=${poste}[Product]
            ...    quantity=${poste}[Quantity]
            ...    quantity_unit=${poste}[QuantityUnit]
            RETURN    ${commande}
        END
    END
    RETURN    ${NONE}

Post Goods Receipt For Purchase Order
    [Documentation]    Poste la réception de marchandise d'une commande
    ...    ACTIVE (jamais un brouillon) via la fonction
    ...    ``SEPMRA_C_PO_PurOrdGoodsreceipt``. Cette fonction n'est PAS liée à
    ...    l'entité (naviguer depuis la commande échoue en 404) : elle
    ...    s'appelle en service racine avec la clé complète en paramètres
    ...    nommés. ``csrf_fetch_path`` détourne la sonde du jeton CSRF vers la
    ...    racine du service : un GET nu sur cette fonction (le défaut,
    ...    faute de jeton déjà en cache) échoue côté serveur, ses paramètres
    ...    étant obligatoires (mesuré live, capacité promue dans la
    ...    bibliothèque, convention 12). Retourne le nouveau statut global de
    ...    la commande (code, jamais un texte localisé : convention 3).
    [Arguments]    ${purchase_order}
    &{parametres}=    Create Dictionary
    ...    PurchaseOrder='${purchase_order}'
    ...    DraftUUID=guid'${EPM_PO_MAN_ACTIVE_DRAFT_UUID}'
    ...    IsActiveEntity=true
    ${reponse}=    Call Odata Function    ${EPM_PO_MAN_SERVICE}/SEPMRA_C_PO_PurOrdGoodsreceipt
    ...    method=POST    csrf_fetch_path=${EPM_PO_MAN_SERVICE}/    &{parametres}
    ${statut}=    Evaluate    $reponse['d']['PurchaseOrderOverallStatus']
    RETURN    ${statut}

Resolve Epm Product Guid
    [Documentation]    Résout le GUID technique (``NODE_KEY``) d'un produit
    ...    EPM depuis son identifiant métier (``PRODUCT_ID``), en lisant
    ...    ``SNWD_PD`` en grille complète puis en filtrant par CONTENU : lors
    ...    du relevé, la dérivation de critère de sélection (`Get Se16
    ...    Selection Criteria`) échouait sur l'écran de cette table, rendu
    ...    par RDP à une échelle que le moteur de libellés ne suivait pas
    ...    encore (corrigé dans la bibliothèque le 2026-09-21, voir le plan) ;
    ...    la lecture complète reste valide live et est conservée.
    ...    Échoue si le produit est introuvable.
    [Arguments]    ${product_id}
    Open Table Selection Screen    SNWD_PD
    Input Text    ${SE16_MAX_HITS_FIELD}    ${SNWD_PD_MAX_HITS}
    Send Vkey    8
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_GRID}
    ${lignes}=    Read Full Grid    ${SE16_GRID}    columns=PRODUCT_ID,NODE_KEY
    ...    max_rows=${SNWD_PD_MAX_HITS}
    ${correspondances}=    Evaluate    [r for r in $lignes if r['PRODUCT_ID'].strip() == $product_id.strip()]
    Should Not Be Empty    ${correspondances}
    ...    msg=Product '${product_id}' not found in SNWD_PD (${{ len($lignes) }} rows read).
    ${guid}=    Evaluate    $correspondances[0]['NODE_KEY']
    RETURN    ${guid}

Read Total Stock Quantity For Product
    [Documentation]    Lit le stock PHYSIQUE total d'un produit EPM dans
    ...    ``SNWD_STOCK`` : la table n'a pas de colonne produit lisible
    ...    directement (jointure par ``PRODUCT_GUID`` == le ``NODE_KEY`` de
    ...    SNWD_PD, résolu par `Resolve Epm Product Guid`) et porte
    ...    PLUSIEURS lignes par produit (un magasin/bac par ligne) : la
    ...    valeur retournée est la SOMME, jamais une seule cellule. Un
    ...    produit sans AUCUNE ligne de stock retourne ``0`` (mesuré live :
    ...    un produit référencé par une commande d'achat n'a pas forcément
    ...    déjà été approvisionné nulle part), jamais un échec : l'absence de
    ...    ligne n'est pas une anomalie de lecture, c'est un stock nul.
    ...    Comparaison de GUID insensible à la casse et aux tirets (les deux
    ...    canaux ne les rendent pas dans la même forme).
    [Arguments]    ${product_guid}
    Open Table Selection Screen    SNWD_STOCK
    Input Text    ${SE16_MAX_HITS_FIELD}    ${SNWD_STOCK_MAX_HITS}
    Send Vkey    8
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_GRID}
    ${lignes}=    Read Full Grid    ${SE16_GRID}    columns=PRODUCT_GUID,QUANTITY
    ...    max_rows=${SNWD_STOCK_MAX_HITS}
    ${correspondances}=    Evaluate
    ...    [r for r in $lignes if r['PRODUCT_GUID'].upper().replace('-', '') == $product_guid.upper().replace('-', '')]
    ${total}=    Evaluate    sum(int(r['QUANTITY']) for r in $correspondances)
    RETURN    ${total}
