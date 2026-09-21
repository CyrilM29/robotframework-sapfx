*** Settings ***
Documentation       Procure-to-Pay EPM cross-canal : reception de marchandise (API) et
...                 verification physique du stock SNWD_STOCK (SAP GUI SE16).
...                 Spec: specs/commande-achat-epm-procure-to-pay.md (sha256:856f01b6b302, 2026-09-21)
...                 Cible A4H (S/4HANA 1909, client 001).
...
...                 Aucune application Fiori de gestion des commandes d'achat n'existe sur
...                 cette cible (62 intents de launchpad testes live, aucun ne resout pour
...                 la creation ni la reception de marchandise), et la creation d'un poste
...                 sur une commande brouillon via le service OData sous-jacent echoue cote
...                 serveur sur trois protocoles distincts (voir le plan) : la commande n'est
...                 donc pas creee par cette suite, elle est DECOUVERTE parmi les commandes
...                 deja confirmees (statut ``F``), et la reception de marchandise est postee
...                 sur le MEME objet metier (``SEPMRA_C_PO_PurOrd`` / fonction
...                 ``Goodsreceipt``) qu'une telle application appellerait si elle existait.
...
...                 Chaque execution decouvre sa propre commande (jamais un numero fige) ;
...                 la reception rend cette commande ineligible aux executions suivantes
...                 (statut ``F`` -> ``D``), ce qui exclut toute collision entre deux
...                 executions. L'assertion est un ECART mesure (stock final == stock
...                 initial + quantite recue), jamais un total absolu : la reception de
...                 marchandise n'a pas de geste inverse dans ce modele de demonstration
...                 (comme Approve/Reject, deja documentes non reversibles ailleurs dans ce
...                 depot), donc le stock EPM croit d'une execution a l'autre par
...                 construction. Sans commande confirmee disponible, la suite se SAUTE
...                 proprement plutot que d'echouer ou d'en fabriquer une.
...
...                 **Accord d'ecriture EXPLICITE requis** (``-v PROCURE_TO_PAY_WRITE_OPT_IN:yes``) :
...                 sans lui, TOUS les tests sont SAUTES avant meme l'ouverture d'un canal (le
...                 tag ``write`` seul ne suffit pas, meme convention que les autres campagnes
...                 d'ecriture non triviale de ce depot).
...
...                 Vocabulaire dans `resources/page_objects/epm_procure_to_pay.resource`.
...
...                 Execution (A4H) :
...
...                 robot --pythonpath src --outputdir results/procure_to_pay ^
...                 -v API_BASE_URL:http://localhost:50000 -v API_USER:DEVELOPER ^
...                 -v "API_PASSWORD: Secret:***" -v API_CLIENT:001 ^
...                 -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER ^
...                 -v "SAP_PASSWORD: Secret:***" -v SAP_CLIENT:001 ^
...                 -v PROCURE_TO_PAY_WRITE_OPT_IN:yes ^
...                 tests/robot/cross/commande_achat_epm_procure_to_pay.robot

Resource            ../../../resources/page_objects/epm_procure_to_pay.resource

Suite Setup         Open Procure To Pay Channels
Suite Teardown      Close Procure To Pay Channels

Test Tags           cross    api    ecc    epm    procure-to-pay    write    a4h


*** Variables ***
${API_BASE_URL}         ${EMPTY}
${API_USER}             ${EMPTY}
${API_PASSWORD}         ${EMPTY}
${API_CLIENT}           001
${SAP_CONNECTION}       ${EMPTY}
${SAP_USER}             ${EMPTY}
${SAP_PASSWORD}         ${EMPTY}
${SAP_CLIENT}           001

${PROCURE_TO_PAY_WRITE_OPT_IN}    ${EMPTY}
${ELIGIBLE_ORDER_FOUND}    ${FALSE}


*** Test Cases ***
Trouver une commande d achat EPM confirmee et lire le stock initial
    [Documentation]    Scenario 1 : jamais une commande fabriquee, jamais un
    ...    numero fige. Sans commande confirmee eligible, ce test et les deux
    ...    suivants se SAUTENT proprement (aucune donnee a verifier).
    ${commande}=    Find Confirmed Purchase Order Eligible For Goods Receipt
    Skip If    $commande is None
    ...    Aucune commande d'achat EPM confirmee (statut F) eligible a une reception de marchandise sur cette cible : rien a receptionner, rien a verifier.
    Should Not Be Empty    ${commande}[product]
    ...    msg=Commande ${commande}[purchase_order] trouvee sans produit sur son premier poste actif.
    Set Suite Variable    ${ELIGIBLE_ORDER_FOUND}    ${TRUE}
    Set Suite Variable    ${COMMANDE}    ${commande}
    ${guid}=    Resolve Epm Product Guid    ${commande}[product]
    Set Suite Variable    ${PRODUCT_GUID}    ${guid}
    ${stock_avant}=    Read Total Stock Quantity For Product    ${guid}
    Set Suite Variable    ${STOCK_AVANT}    ${stock_avant}
    Log    Commande ${commande}[purchase_order] poste ${commande}[item] : produit ${commande}[product], quantite ${commande}[quantity] ${commande}[quantity_unit], stock initial ${stock_avant}.

Poster la reception de marchandise sur la commande trouvee
    [Documentation]    Scenario 2 : poste la reception via la fonction
    ...    ``SEPMRA_C_PO_PurOrdGoodsreceipt`` (service API), jugee par le
    ...    CODE de statut retourne, jamais un texte localise (convention 3).
    Skip If    not ${ELIGIBLE_ORDER_FOUND}
    ...    Aucune commande eligible (scenario precedent saute) : rien a receptionner.
    ${statut}=    Post Goods Receipt For Purchase Order    ${COMMANDE}[purchase_order]
    Should Be Equal As Strings    ${statut}    D
    ...    msg=Commande ${COMMANDE}[purchase_order] : statut attendu 'D' (Delivered) apres reception, obtenu '${statut}'.

Verifier l incrementation exacte du stock physique dans SNWD_STOCK
    [Documentation]    Scenario 3 : assertion dynamique demandee par la
    ...    mission (stock final == stock initial + quantite recue), jamais
    ...    une valeur absolue supposee. Verifiee par SE16, canal INDEPENDANT
    ...    de celui qui a poste la reception.
    Skip If    not ${ELIGIBLE_ORDER_FOUND}
    ...    Aucune commande eligible (scenario precedent saute) : rien a verifier.
    ${stock_apres}=    Read Total Stock Quantity For Product    ${PRODUCT_GUID}
    ${attendu}=    Evaluate    int($STOCK_AVANT) + int($COMMANDE['quantity'])
    Should Be Equal As Integers    ${stock_apres}    ${attendu}
    ...    msg=Produit ${COMMANDE}[product] : stock attendu ${attendu} (${STOCK_AVANT} + ${COMMANDE}[quantity]), lu ${stock_apres} apres reception de la commande ${COMMANDE}[purchase_order].
    Log    Stock ${COMMANDE}[product] : ${STOCK_AVANT} -> ${stock_apres} (+${COMMANDE}[quantity] ${COMMANDE}[quantity_unit]), commande ${COMMANDE}[purchase_order] livree.
