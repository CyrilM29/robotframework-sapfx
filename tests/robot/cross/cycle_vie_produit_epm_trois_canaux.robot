*** Settings ***
Documentation       **Le MÊME produit EPM lu par TROIS canaux indépendants.**
...                 Spec: specs/cycle-vie-produit-epm-api-webgui-rfc.md (sha256:d2919a1cefdf, 2026-09-21)
...                 API (OData v2 `SEPMRA_PROD_MAN`), WebGUI (SE16 sur
...                 `SNWD_PD`) et RFC (`RFC_READ_TABLE`). L'assertion reine
...                 confronte les trois prix ENTRE EUX, pas chacun à une valeur
...                 attendue : c'est ce qui prouve que les trois canaux
...                 regardent la même vérité et non trois copies divergentes.
...
...                 Generated from specs/cycle-vie-produit-epm-api-webgui-rfc.md
...                 by sap-generator: re-run the generator rather than
...                 hand-editing locators here.
...
...                 **LECTURE SEULE de bout en bout, donc aucun opt-in.** Le plan
...                 visait d'abord un cycle d'écriture ; l'exploration a établi
...                 que ce service refuse l'activation ET la suppression d'un
...                 brouillon sur les DEUX systèmes du banc, ce qui rendrait
...                 toute écriture IRRÉVERSIBLE (voir « Écart n°3 » du plan). La
...                 campagne est donc rejouable à l'infini sans effet de bord.
...
...                 Quatre gardes, chacune contre un résultat faux mais plausible.
...                 (1) La CIBLE de CHACUN des trois canaux est prouvée avant
...                 toute lecture métier, par son propre discriminant : release
...                 côté RFC, volume du catalogue Gateway côté API, adresse
...                 réellement atteinte côté WebGUI. Les deux conteneurs du banc
...                 annoncent le même identifiant système ET le même nom d'hôte,
...                 donc lire le mauvais donnerait des valeurs parfaitement
...                 cohérentes, et une garde sur un SEUL canal laisserait une
...                 surcharge de variables incomplète comparer deux systèmes en
...                 restant verte. (2) Le produit de référence est DÉCOUVERT sur
...                 la cible et jamais gravé (`HT-1000`, pourtant relevé de
...                 mémoire, est absent de ce catalogue). (3) La comparaison des
...                 prix porte sur la valeur NUMÉRIQUE normalisée, la notation
...                 décimale de l'utilisateur étant LUE sur le système : l'écran
...                 rend `3,25` là où les deux protocoles rendent `3.25`.
...                 (4) Le constat d'absence de document de modification est
...                 précédé d'un TÉMOIN POSITIF : sans lui, une absence réelle
...                 et une lecture ratée rendraient le même zéro.
...
...                 Les gardes de cible et le témoin ont été vus REFUSER, par
...                 des provocations pointant l'autre conteneur du banc : elles
...                 échouent dans le Suite Setup, donc aucun scénario ne lit.
...
...                 Les relevés vivent dans le Suite Setup, pas dans les
...                 scénarios : chaque test est ainsi jouable SEUL, sans qu'un
...                 échec en cascade sur une variable qu'un autre test n'a pas
...                 posée désigne le mauvais coupable.
...
...                 Invocation (A4H, la cible principale) :
...                 | robot --pythonpath src -v "SAP_PASSWORD: Secret:<mdp>" tests/robot/cross/cycle_vie_produit_epm_trois_canaux.robot
...
...                 Le canal RFC est requis : la suite se SAUTE proprement là où
...                 il n'existe pas (`pyrfc` ou binding natif absent), plutôt que
...                 de rougir là où rien n'est cassé.

Library             Collections
Resource            ../../../resources/page_objects/sepmra_prod_man.resource

Suite Setup         Open The Three Channels And Take The Readings
Suite Teardown      Close Epm Product Channels    webgui_budget=${TEARDOWN_BUDGET}

Test Tags           cross    epm    trois-canaux    rfc


*** Variables ***
# --- Cible : données d'ENVIRONNEMENT, surchargeables par -v ----------------
# Le canal API vise le nom d'hôte interne (celui que l'ICF utilise pour ses
# redirections), le canal WebGUI le port publié sur le poste.
${API_BASE_URL}         http://vhcala4hci:50000
${WEBGUI_URL}           http://localhost:50000/sap/bc/gui/sap/its/webgui?sap-client=001
${RFC_ASHOST}           vhcala4hci
${RFC_SYSNR}            00
${SAP_CLIENT}           001
${SAP_USER}             DEVELOPER
# Convention 11 : aucun identifiant n'a de valeur par défaut committée. Le mot
# de passe entre en variable TYPÉE `Secret:` sur la ligne de commande, donc
# masquée même en TRACE.
${SAP_PASSWORD}         ${EMPTY}
${WEBGUI_STRATEGY}      form

# --- Cible : les TROIS discriminants, un par canal -------------------------
# Les deux conteneurs du banc annoncent le même identifiant système ET le même
# nom d'hôte interne : aucun des deux ne prouve quoi que ce soit. Chaque canal
# a donc son propre discriminant, et les trois sont confrontés à une valeur
# attendue dans le Suite Setup. Une garde sur un seul canal laisserait une
# surcharge de variables incomplète faire lire DEUX systèmes différents, et
# comme les deux images portent le même jeu de démonstration au même prix,
# l'assertion reine serait verte en comparant deux systèmes (réserve de la
# revue indépendante du 2026-09-21).
#
# Canal RFC : la release du composant de base (754 = A4H / ABAP Platform 1909,
# 758 = ABAP Platform 2023).
${EXPECTED_RELEASE}     754
# Canal API : le volume du catalogue Gateway, mesuré sur chaque cible
# (38 sur A4H, 58 sur la 2023, relevés le 2026-09-21). Un compte EXACT plutôt
# qu'un plancher : c'est ce qui en fait un discriminant et non une garde de
# non-vacuité. `-v EXPECTED_SERVICES:0` désactive ce seul contrôle si la cible
# publie un catalogue mouvant.
${EXPECTED_SERVICES}    38
# Canal WebGUI : l'adresse RÉELLEMENT atteinte. Le bandeau n'y porte ni
# release ni kernel, et l'ICF sait rediriger vers le nom d'hôte que les deux
# conteneurs partagent, donc l'hôte et le PORT sont le seul discriminant.
${EXPECTED_WEBGUI_HOST}    localhost:50000

# Un teardown doit rendre la main : budget COURT, parce qu'un déroulé de
# déconnexion WebGUI qui ne peut pas aboutir sur une cible donnée a déjà coûté
# 361 s d'acharnement (mesuré le 2026-09-15).
${TEARDOWN_BUDGET}      10s


*** Test Cases ***
1. Ouvrir les trois canaux et vérifier les préflights
    [Documentation]    Les trois canaux répondent, sur le même système et le
    ...    même mandant. L'état est lu dans le REGISTRE réel du canal, jamais
    ...    dans l'intention de la suite : c'est ce qui distingue « la session
    ...    est ouverte » de « on a demandé son ouverture ».
    ${sessions}=    List Api Sessions
    Length Should Be    ${sessions}[api_sessions]    1
    ...    msg=Le registre du canal API ne porte pas exactement la session de cette campagne.
    Should Be True    ${sessions}[api_sessions][0][authenticated]
    ...    msg=La session API existe mais n'est pas authentifiée.
    Should Be Equal    ${sessions}[api_sessions][0][sap_client]    ${SAP_CLIENT}
    ...    msg=Le canal API ne travaille pas sur le mandant attendu.
    ${canaux_rfc}=    List Open Rfc Channels
    Should Not Be Empty    ${canaux_rfc}
    ...    msg=Aucune connexion RFC ouverte : le canal n'a pas été établi.
    ${webgui_present}=    Webgui Is Present
    Should Be True    ${webgui_present}
    ...    msg=Aucun élément WebGUI rendu : la session d'écran n'est pas (ou plus) là.
    Should Be Equal    ${WEBGUI_IDENTITY}[client]    ${SAP_CLIENT}
    ...    msg=La session WebGUI ne travaille pas sur le mandant attendu.
    Should Be Equal    ${WEBGUI_IDENTITY}[user]    ${SAP_USER}
    ...    msg=La session WebGUI n'est pas ouverte sous l'utilisateur attendu.

2. Prouver la cible avant toute lecture
    [Documentation]    La cible atteinte est celle attendue, prouvée par un
    ...    critère qui DISCRIMINE les deux systèmes du banc.
    ...
    ...    **UN discriminant par canal**, parce que l'invariant porte sur
    ...    trois canaux : la release côté RFC, le volume du catalogue Gateway
    ...    côté API, l'adresse réellement atteinte côté WebGUI. Une garde sur
    ...    un seul canal laisserait une surcharge de variables incomplète
    ...    faire lire deux systèmes différents, et comme les deux images du
    ...    banc portent le même jeu de démonstration au même prix, les trois
    ...    canaux « s'accorderaient » en comparant deux systèmes (réserve de
    ...    la revue indépendante du 2026-09-21).
    ...
    ...    Les trois gardes MORDENT dans le Suite Setup, avant toute lecture
    ...    métier : ce test les redit pour que le rapport porte la preuve de
    ...    cible, il ne les remplace pas. Une garde qui ne vit que dans un
    ...    scénario rougit sans EMPÊCHER, et les scénarios suivants lisent
    ...    tranquillement le mauvais système (défaut mesuré le 2026-09-15).
    ...
    ...    L'identité affichée par le WebGUI n'est assertée qu'en COHÉRENCE
    ...    (mandant, utilisateur) : son identifiant système vaut `A4H` sur les
    ...    deux conteneurs, donc il ne prouve rien à lui seul.
    Should Be Equal    ${TARGET_RELEASE}    ${EXPECTED_RELEASE}
    ...    msg=Canal RFC : release ${TARGET_RELEASE} au lieu de ${EXPECTED_RELEASE}.
    IF    ${EXPECTED_SERVICES} > 0
        Should Be Equal As Integers    ${PUBLISHED_SERVICES}    ${EXPECTED_SERVICES}
        ...    msg=Canal API : ${PUBLISHED_SERVICES} services au catalogue Gateway au lieu de ${EXPECTED_SERVICES}.
    END
    Should Be Equal    ${WEBGUI_ADDRESS}[host]    ${EXPECTED_WEBGUI_HOST}
    ...    msg=Canal WebGUI : session ouverte sur « ${WEBGUI_ADDRESS}[host] » au lieu de « ${EXPECTED_WEBGUI_HOST} ».
    Should Be Equal    ${WEBGUI_IDENTITY}[system_id]    A4H
    ...    msg=Le canal WebGUI n'annonce pas le même système que les deux autres canaux.
    Log    Cible prouvée canal par canal : release ${TARGET_RELEASE} (RFC), ${PUBLISHED_SERVICES} services au catalogue Gateway (API), adresse ${WEBGUI_ADDRESS}[host] (WebGUI), identité de bandeau ${WEBGUI_IDENTITY}.

3. Lire le produit de référence par le canal API
    [Documentation]    L'entité produit ACTIVE existe et porte un prix non
    ...    vide. La lecture vise l'entité active explicitement : l'entity set
    ...    est draft-enabled et agrège sinon des brouillons, dont ce système
    ...    porte plusieurs reliquats non supprimables.
    Should Not Be Empty    ${API_RECORD}[product]
    ...    msg=Le canal API ne rend aucune clé de produit.
    Should Be Equal    ${API_RECORD}[product]    ${REFERENCE_PRODUCT}[product]
    ...    msg=La lecture par clé ne rend pas le produit de référence établi.
    # Les DEUX lectures du même canal sont confrontées : la découverte (lecture
    # de liste, bornée à une entité) et la lecture par CLÉ sont deux requêtes
    # distinctes, et rien ne les comparait. Une divergence entre deux lectures
    # du même canal serait passée inaperçue alors que l'assertion reine, qui
    # ne voit que la seconde, aurait été verte (réserve de la revue
    # indépendante du 2026-09-21).
    ${prix_decouverte}=    Technical Price From Protocol Value
    ...    ${REFERENCE_PRODUCT}[price]
    ${prix_par_cle}=    Technical Price From Protocol Value    ${API_RECORD}[price]
    Should Be Equal As Numbers    ${prix_decouverte}    ${prix_par_cle}
    ...    msg=Le MÊME canal API rend deux prix différents pour ${API_RECORD}[product] : ${REFERENCE_PRODUCT}[price] à la découverte (lecture de liste) contre ${API_RECORD}[price] à la lecture par clé. Les deux requêtes ne voient donc pas la même vérité, et l'assertion reine ne prouverait rien puisqu'elle ne lit que la seconde.
    Should Be Equal    ${REFERENCE_PRODUCT}[currency]    ${API_RECORD}[currency]
    ...    msg=Le MÊME canal API rend deux devises différentes pour ${API_RECORD}[product] : ${REFERENCE_PRODUCT}[currency] contre ${API_RECORD}[currency].
    ${prix}=    Technical Price From Protocol Value    ${API_RECORD}[price]
    Should Be True    ${prix} > 0
    ...    msg=Le produit ${API_RECORD}[product] porte un prix nul ou négatif côté API : le jeu de démonstration est-il complet ?
    Should Not Be Empty    ${API_RECORD}[currency]
    ...    msg=Le canal API ne rend aucune devise.

4. Lire la même ligne par le canal WebGUI
    [Documentation]    Une ligne et une seule, portant la clé visée, assertée
    ...    sur les ids TECHNIQUES de colonnes et jamais sur un libellé
    ...    affiché.
    ...
    ...    La complétude du relevé est confrontée au total DÉCLARÉ par la
    ...    grille (garde commune aux canaux, appliquée dans le page object) :
    ...    une grille WebGUI n'envoie qu'une PAGE de lignes qu'elle
    ...    RENUMÉROTE à partir de 1, donc un relevé tronqué est propre,
    ...    ordonné et indiscernable d'un relevé complet.
    Should Be Equal    ${WEBGUI_RECORD}[product]    ${REFERENCE_PRODUCT}[product]
    ...    msg=La grille SE16 ne porte pas la clé visée : le critère de sélection a-t-il bien été appliqué ?
    Should Be Equal As Integers    ${WEBGUI_RECORD}[extract][declared_rows]    1
    ...    msg=La grille déclare un total différent de la ligne unique attendue pour une clé technique.
    Should Be True    ${WEBGUI_RECORD}[extract][complete]
    ...    msg=Le relevé de la grille est incomplet : il ne prouve rien sur la valeur lue.
    List Should Contain Value    ${WEBGUI_RECORD}[extract][columns]    PRICE
    ...    msg=La grille ne publie pas la colonne technique du prix.
    Should Not Be Empty    ${WEBGUI_RECORD}[price]
    ...    msg=La cellule du prix est vide : sur une grille ALV cela signifie le plus souvent une ligne non matérialisée.

5. Lire la même ligne par le canal RFC
    [Documentation]    La troisième lecture, par le canal qui n'a ni écran ni
    ...    HTTP, sur la MÊME table que les deux autres.
    Should Be Equal    ${RFC_RECORD}[product]    ${REFERENCE_PRODUCT}[product]
    ...    msg=Le canal RFC ne rend pas la clé visée.
    ${prix}=    Technical Price From Protocol Value    ${RFC_RECORD}[price]
    Should Be True    ${prix} > 0
    ...    msg=Le produit ${RFC_RECORD}[product] porte un prix nul ou négatif côté RFC.
    Should Not Be Empty    ${RFC_RECORD}[currency]
    ...    msg=Le canal RFC ne rend aucune devise.

6. Assertion reine : les trois canaux rendent le même prix
    [Documentation]    Les trois valeurs sont comparées ENTRE ELLES, et pas
    ...    seulement chacune à une valeur attendue : une valeur attendue
    ...    commune passerait tout aussi bien si deux canaux lisaient la même
    ...    copie périmée.
    ...
    ...    La comparaison porte sur la valeur NUMÉRIQUE normalisée : les
    ...    représentations diffèrent d'un canal à l'autre (une décimale OData
    ...    et un texte délimité RFC en notation technique, un texte d'écran
    ...    dans la notation de l'utilisateur), et une égalité de chaînes
    ...    échouerait sur une donnée pourtant parfaitement cohérente.
    ${prix}=    The Three Channels Should Agree On The Price
    ...    ${API_RECORD}    ${WEBGUI_RECORD}    ${RFC_RECORD}
    ...    ${DECIMAL_NOTATION}
    ${devise}=    The Three Channels Should Agree On The Currency
    ...    ${API_RECORD}    ${WEBGUI_RECORD}    ${RFC_RECORD}
    Log    Les trois canaux s'accordent sur le produit ${API_RECORD}[product] : ${prix} ${devise} (API « ${API_RECORD}[price] », écran « ${WEBGUI_RECORD}[price] » en notation décimale « ${DECIMAL_NOTATION} », RFC « ${RFC_RECORD}[price] »).

7. Constater l'absence de document de modification
    [Documentation]    Résultat NÉGATIF attendu et documenté : aucune classe
    ...    d'objet de document de modification n'est enregistrée pour cette
    ...    table, et aucun poste n'y a jamais été journalisé. C'est attendu
    ...    d'une application bâtie sur BOPF, qui trace ses changements dans
    ...    ses propres tables.
    ...
    ...    Ce constat EST l'assertion, pas un contournement : si une future
    ...    release de la cible enregistrait une classe d'objet pour cette
    ...    table, ce scénario ÉCHOUERAIT en le signalant, et le plan devrait
    ...    être ré-exploré. Ignorer silencieusement le nouveau résultat
    ...    laisserait croire que la traçabilité a été vérifiée.
    ...
    ...    Le TÉMOIN POSITIF vient d'abord, et c'est lui qui donne son sens au
    ...    zéro : sans lui, « aucun document n'est configuré pour cette table »
    ...    et « cette lecture ne sait pas rendre de lignes » produisent le même
    ...    résultat vide et le même test vert (réserve de la revue
    ...    indépendante du 2026-09-21 ; même patron que la sonde canari de
    ...    l'inventaire DDIC).
    ${temoin}=    Read Change Document Objects Witness
    Should Not Be Empty    ${temoin}
    ...    msg=Le catalogue des documents de modification est ILLISIBLE : une lecture non filtrée ne rend aucune ligne, alors que toute cible en porte. Le zéro des assertions suivantes ne prouverait donc aucune absence, seulement une lecture ratée.
    ${classes}=    Read Change Document Objects For Epm Products
    Should Be Empty    ${classes}
    ...    msg=Une classe d'objet de documents de modification est désormais enregistrée pour la table des produits (${classes}) : le comportement de la cible a CHANGÉ, la traçabilité d'audit est peut-être devenue observable et le plan doit être ré-exploré (specs/cycle-vie-produit-epm-api-webgui-rfc.md, Écart n°2).
    ${postes}=    Read Change Document Items For Epm Products
    Should Be Empty    ${postes}
    ...    msg=Des postes de documents de modification existent désormais pour la table des produits (${postes}) : le plan doit être ré-exploré.


*** Keywords ***
Open The Three Channels And Take The Readings
    [Documentation]    Ouvre les trois canaux, PROUVE la cible, puis prend les
    ...    trois relevés.
    ...
    ...    La garde de cible vit ici et non dans un scénario : une garde qui
    ...    rougit dans un test laisse les suivants lire tranquillement le
    ...    mauvais système (défaut mesuré le 2026-09-15 sur une campagne
    ...    d'extraction, où quatre scénarios écrivaient des fichiers du
    ...    mauvais système sous des noms qui annonçaient le bon).
    ...
    ...    Les relevés vivent ici pour que chaque scénario soit jouable seul.
    # La garde ne MESURE jamais le mot de passe : un `Secret` refuse d'être
    # mesuré, et l'erreur de garde masquerait le prérequis manquant.
    Api Credentials Should Be Provided    ${SAP_PASSWORD}
    Open Epm Product Api Channel    ${API_BASE_URL}    ${SAP_USER}
    ...    ${SAP_PASSWORD}    ${SAP_CLIENT}
    Open Epm Product Rfc Channel    ${RFC_ASHOST}    ${RFC_SYSNR}
    ...    ${SAP_CLIENT}    ${SAP_USER}    ${SAP_PASSWORD}
    ${release}=    Read Epm Target Release
    Set Suite Variable    ${TARGET_RELEASE}    ${release}
    Should Be Equal    ${release}    ${EXPECTED_RELEASE}
    ...    msg=Cible refusée AVANT toute lecture : la release du composant de base est ${release}, or ${EXPECTED_RELEASE} est attendue. Les deux systèmes du banc annoncent le même identifiant système et le même nom d'hôte, donc rien d'autre ne les distingue. Pour viser l'autre cible : -v API_BASE_URL:<url> -v WEBGUI_URL:<url> -v RFC_ASHOST:<hôte> -v EXPECTED_RELEASE:<release>.
    # Canal API : le compte EXACT du catalogue, pas un plancher. Le plan
    # annonce ce volume comme discriminant de cible ; ne vérifier que sa
    # non-vacuité en ferait une garde vraie quoi qu'il arrive, et une
    # surcharge de variables qui oublierait `API_BASE_URL` lirait l'autre
    # système sans que rien ne l'arrête.
    ${services}=    Count Epm Published Services
    Set Suite Variable    ${PUBLISHED_SERVICES}    ${services}
    IF    ${EXPECTED_SERVICES} > 0
        Should Be Equal As Integers    ${services}    ${EXPECTED_SERVICES}
        ...    msg=Cible du canal API refusée AVANT toute lecture : le catalogue Gateway publie ${services} services, or ${EXPECTED_SERVICES} sont attendus sur la cible visée. Ce volume est le discriminant de ce canal, l'identifiant système et le nom d'hôte étant partagés par les deux conteneurs du banc. Vérifier -v API_BASE_URL, ou -v EXPECTED_SERVICES si le catalogue de la cible a légitimement bougé.
    ELSE
        Log    Contrôle du volume du catalogue Gateway désactivé (EXPECTED_SERVICES=0) : la cible du canal API n'est donc PAS prouvée.    level=WARN
    END
    ${identite}=    Open Epm Product Webgui Session    ${WEBGUI_URL}
    ...    ${SAP_USER}    ${SAP_PASSWORD}    ${WEBGUI_STRATEGY}
    Set Suite Variable    ${WEBGUI_IDENTITY}    ${identite}
    # Canal WebGUI : l'adresse atteinte, seul discriminant disponible ici.
    # L'identité du bandeau ne sert qu'à la cohérence (mandant, utilisateur) :
    # son identifiant système vaut `A4H` sur les DEUX conteneurs.
    ${adresse}=    Read Epm Webgui Address
    Set Suite Variable    ${WEBGUI_ADDRESS}    ${adresse}
    Should Be Equal    ${adresse}[host]    ${EXPECTED_WEBGUI_HOST}
    ...    msg=Cible du canal WebGUI refusée : la session est ouverte sur « ${adresse}[host] », or « ${EXPECTED_WEBGUI_HOST} » est attendu. L'ICF sait REDIRIGER vers le nom d'hôte virtuel que les deux conteneurs partagent, donc viser le mauvais port ouvre une session parfaitement fonctionnelle sur l'AUTRE système. Vérifier -v WEBGUI_URL et -v EXPECTED_WEBGUI_HOST.
    ${notation}=    Read User Decimal Notation    ${SAP_USER}
    Set Suite Variable    ${DECIMAL_NOTATION}    ${notation}
    ${reference}=    Establish Epm Reference Product
    Set Suite Variable    ${REFERENCE_PRODUCT}    ${reference}
    ${api}=    Read Epm Product By Api    ${reference}[product]
    Set Suite Variable    ${API_RECORD}    ${api}
    ${webgui}=    Read Epm Product By Webgui    ${reference}[product]
    ...    ${WEBGUI_URL}
    Set Suite Variable    ${WEBGUI_RECORD}    ${webgui}
    ${rfc}=    Read Epm Product By Rfc    ${reference}[product]
    Set Suite Variable    ${RFC_RECORD}    ${rfc}
    Log    Produit de référence découvert sur la cible : ${reference}[product] ; notation décimale de l'utilisateur : « ${notation} ».
