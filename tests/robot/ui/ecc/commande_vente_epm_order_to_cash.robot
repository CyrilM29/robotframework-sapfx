*** Settings ***
Documentation       Order-to-Cash EPM de bout en bout via SEPM_SO (SAP GUI).
...                 Spec: specs/commande-vente-epm-order-to-cash.md (sha256:d60a84b0b8e6, 2026-09-18)
...                 Cible A4H (S/4HANA 1909, client 001) : voir docs/ecc-validation.md.
...                 Un test par scénario du plan, dans son ordre.
...
...                 Crée une commande de vente EPM (client + produit + quantité
...                 saisis via des localisateurs humains et un table control
...                 adressé par titre de colonne, jamais un id brut dans ce
...                 fichier, convention 1), isole son numéro depuis le
...                 PARAMÈTRE du message de confirmation (jamais son texte,
...                 convention 3), le confronte à SNWD_SO via SE16, puis la
...                 supprime par la fonction officielle de la même transaction.
...
...                 **Réjouable sans limite** : le numéro de commande est
...                 attribué par SAP à chaque sauvegarde (jamais choisi par le
...                 test), donc deux exécutions, même simultanées, ne peuvent
...                 jamais entrer en collision. Le nettoyage vit dans le Suite
...                 Teardown, s'exécute même après un échec, et ne fait rien si
...                 aucune commande n'a été créée : un nettoyage en échec est
...                 journalisé en avertissement plutôt que de faire échouer la
...                 suite (une commande orpheline ne gêne aucune exécution
...                 suivante, seul son propre numéro la désigne).
...
...                 Localisateurs d'écran dans le page object
...                 `resources/page_objects/sepm_so_order_entry.resource` ;
...                 lecture/comptage SE16 génériques dans
...                 `resources/ecc_keywords.resource` (convention 1).
...
...                 Exécution (A4H) :
...
...                 robot --pythonpath src --outputdir results/order_to_cash ^
...                 -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER ^
...                 -v "SAP_PASSWORD: Secret:***" -v SAP_CLIENT:001 ^
...                 tests/robot/ui/ecc/commande_vente_epm_order_to_cash.robot

Resource            ../../../../resources/page_objects/sepm_so_order_entry.resource
Resource            ../../../../resources/a4h_demo_data.resource

Suite Setup         Open Order To Cash Campaign
Suite Teardown      Run Keywords    Nettoyer La Commande De Vente Creee Si Necessaire    AND    Close SAP

Test Tags           ecc    epm    order-to-cash    write    a4h


*** Variables ***
${BP_ID}            ${EMPTY}
${PRODUCT_ID}        ${EMPTY}
${EPM_SO_ID}         ${EMPTY}
${ORDER_QUANTITY}    2


*** Test Cases ***
Lire un client et un produit EPM existants
    [Documentation]    Scénario 1 : jamais un identifiant inventé. Le client
    ...                (rôle 01, jamais 02 = fournisseur) et le produit sont
    ...                relus dans les données EPM déjà présentes sur la cible.
    ${bp_id}=    Read A Test Business Partner
    ${product_id}=    Read A Test Product
    Should Not Be Empty    ${bp_id}    msg=Aucun client EPM (BP_ROLE=01) disponible sur cette cible.
    Should Not Be Empty    ${product_id}    msg=Aucun produit EPM disponible sur cette cible.
    Set Suite Variable    ${BP_ID}    ${bp_id}
    Set Suite Variable    ${PRODUCT_ID}    ${product_id}

Creer une commande de vente EPM via SEPM_SO
    [Documentation]    Scénario 2 : Create, en-tête, un poste, sauvegarde. Le
    ...                numéro de commande vient du PARAMÈTRE du message de
    ...                confirmation (``SEPM_BOR_MESSAGES/S/044``), jamais de
    ...                son texte localisé.
    ${so_id}=    Create Epm Sales Order    ${BP_ID}    ${PRODUCT_ID}    ${ORDER_QUANTITY}
    Should Match Regexp    ${so_id}    ^\\d{10}$
    ...    msg=Numéro de commande de forme inattendue : ${so_id}
    Set Suite Variable    ${EPM_SO_ID}    ${so_id}

Verifier l inscription physique de la commande dans SNWD_SO
    [Documentation]    Scénario 3 : la commande créée par le canal SAP GUI
    ...                doit exister, à l'identique par son numéro, dans
    ...                SNWD_SO (canal SE16), avec le statut d'une commande
    ...                neuve. Critères dérivés live de l'écran de sélection
    ...                (`Count Table Entries With Criteria`), jamais un
    ...                dictionnaire de localisateurs à maintenir.
    ${count}=    Count Table Entries With Criteria    SNWD_SO
    ...    SO_ID=${EPM_SO_ID}    LIFECYCLE_STATUS=N
    Should Be Equal As Integers    ${count}    1
    ...    msg=SNWD_SO ne porte pas exactement une commande neuve pour ${EPM_SO_ID}.


*** Keywords ***
Open Order To Cash Campaign
    [Documentation]    Connexion, garde de données de démonstration EPM, et
    ...                réglage persistant requis par toute lecture SE16 de
    ...                cette suite (grille ALV, posé une fois par utilisateur).
    Open SAP And Log In
    Ensure EPM Demo Data Exists
    Use ALV Grid In Data Browser

Nettoyer La Commande De Vente Creee Si Necessaire
    [Documentation]    Garantie de réjouabilité : supprime la commande créée
    ...                par cette exécution, si une a été créée, et vérifie sa
    ...                disparition de SNWD_SO. Un échec ici est journalisé en
    ...                avertissement plutôt que de faire échouer la suite : la
    ...                connexion doit rester utilisable pour le `Close SAP`
    ...                qui suit, et une commande orpheline ne gêne aucune
    ...                exécution future (elle porte son propre numéro, jamais
    ...                réutilisé).
    IF    "${EPM_SO_ID}" == "${EMPTY}"
        RETURN
    END
    TRY
        Delete Epm Sales Order    ${EPM_SO_ID}
        ${count_after}=    Count Table Entries With Criteria    SNWD_SO    SO_ID=${EPM_SO_ID}
        Should Be Equal As Integers    ${count_after}    0
        ...    msg=La commande ${EPM_SO_ID} est toujours visible dans SNWD_SO après suppression.
    EXCEPT    AS    ${error}
        Log    Nettoyage de la commande ${EPM_SO_ID} en échec : ${error}    level=WARN
    END
