*** Settings ***
Documentation       **EXEMPLE À PERSONNALISER** : ce fichier porte le vocabulaire
...                 métier du LABORATOIRE de ce dépôt (identifiants d'écran relevés
...                 live sur SA cible). Beaucoup s'y réutilise tel quel sur un autre
...                 système EPM (SEPM_SO est une transaction de démonstration
...                 standard SAP), mais rien n'y fait autorité : à VÉRIFIER sur votre
...                 cible et à adapter à votre métier. Ce qui fait foi partout, c'est
...                 `src/`, les bibliothèques, qui portent les capacités : voir
...                 `resources/README.md`.
...
...                 Page object de la transaction **SEPM_SO** (EPM Sales Order,
...                 Order-to-Cash) : écran initial (Create/Display/Delete par
...                 numéro de commande), écran de saisie (onglets Header Data et
...                 Items), et la fenêtre modale de confirmation de suppression.
...                 Ses localisateurs (`GV_SO_ID`, `SEPM_SO_HEADER_300-BP_ID`, le
...                 table control des postes, `BUTTON_1`/`BUTTON_2`) vivent ICI
...                 (convention 1) ; la suite parle métier.
...
...                 Contrat d'assertion : les verdicts portent sur l'IDENTITÉ du
...                 message de statut (classe/numéro/type SEPM_BOR_MESSAGES, jamais
...                 son texte localisé, convention 3) et sur le numéro de commande
...                 ISOLÉ DU PARAMÈTRE du message, jamais de son texte. L'adressage
...                 de cellule du table control des postes est 0-INDEXÉ (vérifié
...                 live : `row=1` échoue sur une table à une seule ligne).

Resource            ../ecc_keywords.resource


*** Variables ***
# --- Écran initial (RS_EPM_SO_CLASSIC_DYNPRO/SEPM_SO/100) ---
${SEPM_SO_CREATE_BUTTON}                wnd[0]/usr/btnCREATE
${SEPM_SO_DELETE_BUTTON}                wnd[0]/usr/btnDELETE
# --- Écran de saisie (.../SEPM_SO/300), onglet Items ---
${SEPM_SO_ITEMS_TABSTRIP}               wnd[0]/usr/tabsEPM_SO_TAB
# Clé technique de l'onglet Items (suffixe `tabp<CLÉ>`, locale-safe). Nommée
# sans le suffixe « _KEY » : le garde anti-identifiants en dur le lit comme un
# secret, et une clé d'onglet n'en est pas un.
${SEPM_SO_ITEMS_TAB}                     EPM_SO_TAB_FC2
${SEPM_SO_ITEMS_SUBSCREEN}               wnd[0]/usr/tabsEPM_SO_TAB/tabpEPM_SO_TAB_FC2/ssubEPM_SO_TAB_SCA:RS_EPM_SO_CLASSIC_DYNPRO:0302
${SEPM_SO_ITEMS_TABLE}                   ${SEPM_SO_ITEMS_SUBSCREEN}/tblRS_EPM_SO_CLASSIC_DYNPROSO_ITEMS
${SEPM_SO_ITEMS_INSERT_ROW_BUTTON}       ${SEPM_SO_ITEMS_SUBSCREEN}/btnINSERT_ROW
# --- Fenêtre modale de confirmation de suppression (module de confirmation
# générique : les noms techniques des boutons sont stables, leur TEXTE dépend
# de la langue de connexion, épinglée EN par défaut dans ecc_keywords.resource) ---
${SEPM_SO_DELETE_CONFIRM_YES_BUTTON}    wnd[1]/usr/btnBUTTON_1
# --- Identité des messages de statut (classe SEPM_BOR_MESSAGES), convention 3 ---
${SEPM_SO_MESSAGE_CLASS}                SEPM_BOR_MESSAGES
${SEPM_SO_SAVED_MESSAGE_NUMBER}          044
${SEPM_SO_DELETED_MESSAGE_NUMBER}        061


*** Keywords ***
Read A Test Business Partner
    [Documentation]    Relit (jamais n'invente) l'identifiant d'un client EPM
    ...                existant : premier partenaire de rôle ``01`` (client)
    ...                dans SNWD_BPA. ``BP_ROLE=02`` désigne un fournisseur ;
    ...                confondre les deux fausse le sens métier de la commande.
    Display Table Contents With Filter    SNWD_BPA    BP_ROLE=01
    ${rows}=    Read Displayed Grid    max_rows=1
    Should Not Be Empty    ${rows}
    ...    msg=Aucun partenaire de rôle 01 (client) trouvé dans SNWD_BPA.
    RETURN    ${rows}[0][BP_ID]

Read A Test Product
    [Documentation]    Relit le premier produit EPM existant dans SNWD_PD
    ...                (sans filtre : n'importe quel produit convient à la
    ...                commande de test).
    Display Table Contents    SNWD_PD
    ${rows}=    Read Displayed Grid    max_rows=1
    Should Not Be Empty    ${rows}    msg=SNWD_PD est vide : aucun produit EPM disponible.
    RETURN    ${rows}[0][PRODUCT_ID]

Create Epm Sales Order
    [Documentation]    Crée une commande de vente EPM par SEPM_SO : Create,
    ...                en-tête (partenaire commercial), un poste (produit +
    ...                quantité), sauvegarde. Confronte le message de statut à
    ...                l'identité attendue et rend le numéro de commande ISOLÉ
    ...                DU PARAMÈTRE du message (jamais de son texte).
    [Arguments]    ${business_partner_id}    ${product_id}    ${quantity}
    Go To Transaction    SEPM_SO
    Click Element    ${SEPM_SO_CREATE_BUTTON}
    Fill Field By Label    Business Partner ID    ${business_partner_id}
    Send Vkey    0
    Select Tab    ${SEPM_SO_ITEMS_TABSTRIP}    ${SEPM_SO_ITEMS_TAB}
    Click Element    ${SEPM_SO_ITEMS_INSERT_ROW_BUTTON}
    Set Table Control Cell    ${SEPM_SO_ITEMS_TABLE}    0    PRODUCT ID    ${product_id}
    Set Table Control Cell    ${SEPM_SO_ITEMS_TABLE}    0    QUANTITY    ${quantity}
    Send Vkey    0
    Send Vkey    11
    Wait Until Busy Done
    ${identity}=    Status Message Should Be
    ...    ${SEPM_SO_MESSAGE_CLASS}    ${SEPM_SO_SAVED_MESSAGE_NUMBER}    S
    RETURN    ${identity}[parameters][0]

Delete Epm Sales Order
    [Documentation]    Supprime la commande de vente EPM ``${so_id}`` par
    ...                SEPM_SO (Delete puis confirmation « Yes ») et confronte
    ...                le message de statut à l'identité attendue.
    [Arguments]    ${so_id}
    Go To Transaction    SEPM_SO
    Fill Field By Label    Sales Order ID    ${so_id}
    Click Element    ${SEPM_SO_DELETE_BUTTON}
    Click Element    ${SEPM_SO_DELETE_CONFIRM_YES_BUTTON}
    Wait Until Busy Done
    Status Message Should Be
    ...    ${SEPM_SO_MESSAGE_CLASS}    ${SEPM_SO_DELETED_MESSAGE_NUMBER}    S
