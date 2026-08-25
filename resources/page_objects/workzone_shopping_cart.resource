*** Settings ***
Documentation       Page object de l'**application embarquée dans le launchpad
...                 Work Zone** : le Shopping Cart (`sap.ui.demo.cart`), servi
...                 en application de type URL et donc ouvert dans une iframe
...                 CROSS-ORIGIN par le shell.
...
...                 Tous les mots-clés d'ici supposent que la portée de frame
...                 est déjà celle de l'application (`Entrer Dans L
...                 Application` du page object du launchpad) : c'est
...                 exactement ce qui rend le couple shell + application
...                 intéressant à tester, le registre UI5 du shell ne contient
...                 AUCUN contrôle de l'application.
...
...                 Relevé live le 2026-08-24 (rf-mcp : Browser +
...                 SapFioriLibrary), runtime SAPUI5 1.151.0, 844 contrôles
...                 construits dans la frame contre 139 pour le shell.
...
...                 Contrat de localisation, tel que la cible l'impose :
...
...                 * les ids de VUE sont stables et forment l'ancre primaire
...                 (`container-cart---cartView--entryList`,
...                 `container-cart---product--productImage`) ;
...                 * les contrôles créés par une FABRIQUE portent un préfixe
...                 généré (`__item7-container-cart---cartView--entryList-0`,
...                 `__button10`) : on les adresse par `idSuffix`, par
...                 propriété, ou par un xpath UI5 ancré sur une vue ;
...                 * la position sert de dernier recours ASSUMÉ dans un seul
...                 cas, documenté plus bas : les boutons d'une MessageBox.
...
...                 Contrat d'assertion : les libellés de l'interface suivent
...                 la locale du navigateur (relevé en français : boutons
...                 « Supprimer » et « Annuler » de la MessageBox, textes
...                 d'accessibilité UI5) tandis que les données de démonstration
...                 restent en anglais et que les prix sont formatés par la
...                 locale (`45,00`). Aucun mot-clé d'ici ne juge un libellé
...                 d'interface : on compte des contrôles, on lit des noms de
...                 produits (donnée), on compare des mesures prises dans le
...                 même run.

# L'application n'existe qu'ouverte PAR le launchpad : ce page object dépend
# donc de celui du shell, qui porte l'ouverture de session et l'entrée dans la
# frame applicative.
Resource            workzone_launchpad.resource
Library             String


*** Variables ***
# Intent de l'application dans le catalogue du site. Paramétrable : un autre
# site publiera le même Shopping Cart sous un autre intent.
${WORKZONE_CART_INTENT}         ShoppingCart-display

# --- Vues et listes : ids stables, relevés live (2026-08-24) ----------------
${CART_CATEGORY_ITEM}           sap.m.StandardListItem    # une catégorie du volet gauche
${CART_CATEGORY_LIST}           container-cart---homeView--categoryList
${CART_PRODUCT_ITEM}            sap.m.ObjectListItem    # une ligne produit, et une ligne de panier
${CART_CATEGORY_VIEW}           container-cart---category    # portée de la liste de produits
${CART_PRODUCT_LIST}            container-cart---category--productList
${CART_CATEGORY_PAGE}           container-cart---category--page    # sa propriété `title` porte le nom de la catégorie affichée
${CART_CATEGORY_BACK}           container-cart---category--page-navButton
${CART_PRODUCT_PAGE}            container-cart---product--page
${CART_PRODUCT_IMAGE}           container-cart---product--productImage
${CART_PAGE}                    container-cart---cartView--page
${CART_ENTRY_LIST}              container-cart---cartView--entryList
${CART_EDIT_BUTTON}             container-cart---cartView--editButton
${CART_DONE_BUTTON}             container-cart---cartView--doneButton
${CART_TOTAL_TEXT}              container-cart---cartView--totalPriceText

# --- Xpath UI5 : ancrés sur une vue, jamais positionnels ---------------------
# Les boutons de l'application n'ont pas d'id propre (`__button10`) : on les
# désigne par leur PLACE FONCTIONNELLE dans une vue identifiée.
${CART_ADD_XPATH}               //Page[@id='container-cart---product--page']//Toolbar//Button
${CART_TOGGLE_XPATH}            //Page[@id='container-cart---product--page']//Bar//ToggleButton
${CART_PRODUCT_TITLE_XPATH}     //Page[@id='container-cart---product--page']//Bar//Title
${CART_DELETE_XPATH}            //List[@id='container-cart---cartView--entryList']//ObjectListItem//Button[@icon='sap-icon://decline']
${CART_DELETE_ICON}             sap-icon://decline    # l'icône de suppression d'une ligne, en mode édition

# --- MessageBox de confirmation : le seul localisateur POSITIONNEL assumé ----
# Mesuré live : les boutons d'une MessageBox portent un libellé LOCALISÉ
# (« Supprimer » / « Annuler » sur un navigateur en français) et un id généré
# (`__mbox-btn-0`). Les adresser par leur texte reviendrait à écrire une
# assertion de langue dans un localisateur (convention 3) ; l'ordre des actions,
# lui, est celui que l'application déclare. La position 0 est donc l'action de
# confirmation, la position 1 l'annulation.
${CART_DIALOG_BUTTON_XPATH}     //Dialog[@type='Message']//Button
${CART_DIALOG_CONFIRM_INDEX}    ${0}
${CART_DIALOG_CANCEL_INDEX}     ${1}

# --- Propriétés lues sur le contrôle, jamais sur le rendu --------------------
# Deux pièges mesurés live le 2026-08-24, tous deux résolus par
# `Get Ui5 Properties` (ajouté à SapFioriLibrary pour cette campagne) :
# le texte RENDU d'un élément de catégorie vaut « Accessories\n34 » (le contrôle
# dessine son compteur de produits) là où la propriété `title` vaut
# « Accessories », et un contrôle rendu mais MASQUÉ par une colonne repliée du
# FlexibleColumnLayout n'a pas de texte lisible du tout (la lecture expire au
# bout de 10 s, ce qui ressemble à une dérive de localisateur).
${CART_TITLE_PROPERTY}          title
${CART_SELECTED_PROPERTY}       selected
# Disponibilité d'un produit : chaque ligne porte un `sap.m.ObjectStatus` dont
# l'ÉTAT est sémantique (`Success`/`Warning`/`Error`) là où son texte est
# localisable. Un produit hors stock ou arrêté déclenche un dialogue de
# confirmation à l'ajout, donc une campagne qui veut ajouter sans détour vise un
# produit commandable, et le fait sur l'état, pas sur le mot « Available ».
${CART_STATUS_CONTROL}          sap.m.ObjectStatus
${CART_STATE_PROPERTY}          state
${CART_ORDERABLE_STATE}         Success
${CART_DIALOG_CONTROL}          sap.m.Dialog
${CART_PRODUCT_HEADER}          sap.m.ObjectHeader    # en-tête de la fiche produit : porte le nom du produit


*** Keywords ***
Ouvrir Le Parcours Du Panier
    [Documentation]    Suite Setup du parcours : ouvre la session sur le
    ...    launchpad, navigue vers l'application par son intent, entre dans son
    ...    iframe et attend qu'elle ait rendu ses contrôles. À la sortie de ce
    ...    mot-clé, toute résolution UI5 se fait DANS l'application.
    Ouvrir La Session Work Zone
    Ouvrir L Application Par Intent    ${WORKZONE_CART_INTENT}
    Entrer Dans L Application
    L Application Du Panier Est Rendue

Fermer Le Parcours Du Panier
    [Documentation]    Suite Teardown du parcours : rend le panier à son état
    ...    vide, dépile la portée de frame, puis ferme le navigateur.
    ...
    ...    Le vidage est en avertissement plutôt qu'en échec : un teardown ne
    ...    doit pas masquer la cause d'un échec de test, mais un panier laissé
    ...    plein n'a pas non plus à disparaître en silence, car il fausserait
    ...    le run suivant.
    Run Keyword And Warn On Failure    Vider Le Panier
    Sortir De L Application Si Necessaire
    Fermer La Session Work Zone

L Application Du Panier Est Rendue
    [Documentation]    Vérifie que la portée courante est bien l'application et
    ...    qu'elle a construit ses contrôles. Retourne sa composition perçue.
    Wait For Ui5 Idle
    Wait Until Keyword Succeeds    60s    2s    La Liste Des Categories Est Rendue
    ${composition}=    Get Page Composition
    RETURN    ${composition}

La Liste Des Categories Est Rendue
    [Documentation]    Prédicat de premier rendu : au moins une catégorie est
    ...    construite. `Wait For Ui5 Idle` seul ne suffit pas au tout premier
    ...    chargement : il attend le repos des requêtes DÉJÀ parties, pas celles
    ...    que la vue va lancer.
    ${nb}=    Compter Les Categories
    Should Be True    ${nb} > 0
    ...    msg=Aucune catégorie rendue : l'application n'a pas fini de charger.

Compter Les Categories
    [Documentation]    Nombre de catégories rendues dans le volet de gauche.
    ${nb}=    Get Ui5 Match Count    controlType=${CART_CATEGORY_ITEM}
    ...    viewId=${CART_CATEGORY_LIST}
    RETURN    ${nb}

Lister Les Categories
    [Documentation]    Noms des catégories, dans l'ordre d'affichage, lus sur la
    ...    PROPRIÉTÉ des contrôles et non sur leur rendu (voir la note en tête de
    ...    la section des variables). Ce sont des DONNÉES du jeu de
    ...    démonstration, pas des libellés d'interface : les comparer reste
    ...    indépendant de la locale.
    ${noms}=    Get Ui5 Properties    ${CART_TITLE_PROPERTY}
    ...    controlType=${CART_CATEGORY_ITEM}    viewId=${CART_CATEGORY_LIST}
    RETURN    ${noms}

Afficher La Liste Des Categories
    [Documentation]    Ramène l'application à un état où une catégorie peut être
    ...    choisie.
    ...
    ...    Nécessaire, et c'est un piège que seule la cible réelle montre :
    ...    l'application est bâtie sur un `FlexibleColumnLayout`, et dès qu'une
    ...    colonne de détail est ouverte, les catégories restent RÉSOLVABLES
    ...    (elles sont dans le registre UI5) mais deviennent INVISIBLES, donc
    ...    non cliquables. Le clic échoue alors sur « element is not visible »
    ...    après avoir pourtant résolu son élément, ce qui ressemble à tort à
    ...    une dérive de localisateur.
    ${retour}=    Get Ui5 Match Count    id=${CART_CATEGORY_BACK}
    IF    ${retour} > 0
        ${selecteur}=    Resolve Ui5 Control    id=${CART_CATEGORY_BACK}
        ${visible}=    Run Keyword And Return Status
        ...    Get Element States    ${selecteur}    contains    visible
        IF    ${visible}
            Click Ui5 Control    id=${CART_CATEGORY_BACK}
            Wait For Ui5 Idle
        END
    END

Revenir Au Catalogue
    [Documentation]    Ramène l'application à un état où une catégorie peut être
    ...    choisie, quel que soit l'endroit où le test précédent l'a laissée, et
    ...    le VÉRIFIE.
    ...
    ...    Le repli n'est pas de la précaution : les colonnes affichées par un
    ...    `FlexibleColumnLayout` dépendent de la route ET de la largeur, et une
    ...    combinaison malheureuse laisse la liste des catégories hors écran, où
    ...    aucun clic ne porte. Plutôt que d'empiler des cas particuliers, on
    ...    repart alors de l'application telle que le launchpad l'ouvre : c'est
    ...    l'état de référence, et il est atteignable depuis n'importe quel état.
    Run Keyword And Ignore Error    Fermer Le Panier
    Run Keyword And Ignore Error    Afficher La Liste Des Categories
    ${pret}=    Run Keyword And Return Status    Le Catalogue Est Utilisable
    IF    not ${pret}    Reinitialiser L Application Du Panier

Le Catalogue Est Utilisable
    [Documentation]    Prédicat : la première catégorie est réellement cliquable
    ...    (rendue ET visible à l'écran).
    ${selecteur}=    Resolve Ui5 Control    controlType=${CART_CATEGORY_ITEM}
    ...    viewId=${CART_CATEGORY_LIST}
    Get Element States    ${selecteur}    contains    visible
    ...    message=La liste des catégories est rendue mais hors écran.

Reinitialiser L Application Du Panier
    [Documentation]    Rouvre l'application depuis le launchpad : la façon la
    ...    plus sûre de retrouver l'état initial de sa navigation, et elle
    ...    n'invente rien, c'est le chemin de l'utilisateur.
    Sortir De L Application Si Necessaire
    Ouvrir L Application Par Intent    ${WORKZONE_CART_INTENT}
    Entrer Dans L Application
    L Application Du Panier Est Rendue

Ouvrir Un Produit Disponible
    [Documentation]    Ouvre la fiche du premier produit trouvé en parcourant
    ...    les catégories, et retourne son nom.
    ...
    ...    Piloté par la découverte, à dessein : aucun nom de produit ni de
    ...    catégorie n'est codé en dur, la campagne reste valable si le jeu de
    ...    démonstration change. Échec explicite si AUCUNE catégorie ne contient
    ...    de produit : c'est alors la cible qui est anormale, pas le test.
    Revenir Au Catalogue
    ${categories}=    Lister Les Categories
    FOR    ${nom}    IN    @{categories}
        ${ouverte}=    Run Keyword And Return Status    Ouvrir La Categorie    ${nom}
        IF    not ${ouverte}    CONTINUE
        ${produits}=    Lister Les Produits Ouvrables
        IF    len($produits) > 0
            Ouvrir Le Produit    ${produits}[0]
            RETURN    ${produits}[0]
        END
    END
    Fail    Aucune des ${{len($categories)}} catégories du catalogue n'offre de produit ouvrable.

Compter Toutes Les Lignes Produit De L Application
    [Documentation]    Nombre de lignes produit rendues dans TOUTE
    ...    l'application, portée de catégorie comprise. Mis en regard de
    ...    `Compter Les Produits De La Categorie`, il montre ce que la portée
    ...    change : l'accueil garde ses propres listes (mis en avant, consultés,
    ...    favoris) dans le registre UI5.
    ${nb}=    Get Ui5 Match Count    controlType=${CART_PRODUCT_ITEM}
    RETURN    ${nb}

Ouvrir La Categorie
    [Documentation]    Ouvre une catégorie par son nom et ne rend la main que
    ...    lorsque LA page de CETTE catégorie est à l'écran. Même raison que
    ...    pour `Ouvrir Le Produit` : une catégorie déjà sélectionnée ne
    ...    renavigue pas, et l'échec doit tomber ici, pas trois étapes plus loin.
    [Arguments]    ${nom}
    Afficher La Liste Des Categories
    Click Ui5 Control    controlType=${CART_CATEGORY_ITEM}    properties={'title': '${nom}'}
    ...    viewId=${CART_CATEGORY_LIST}
    Wait For Ui5 Idle
    Wait Until Keyword Succeeds    15s    1s    La Categorie Est A L Ecran    ${nom}

La Categorie Est A L Ecran
    [Documentation]    Prédicat d'ouverture d'une catégorie : sa page est visible
    ...    à l'écran et son titre est bien celui demandé. Le titre est lu sur la
    ...    propriété de la page, donc exact et indépendant du rendu.
    [Arguments]    ${nom}
    ${selecteur}=    Resolve Ui5 Control    id=${CART_CATEGORY_PAGE}
    Get Element States    ${selecteur}    contains    visible
    ...    message=La page de catégorie est rendue mais masquée : la navigation n'a pas eu lieu.
    ${affichee}=    Get Ui5 Property    ${CART_TITLE_PROPERTY}    id=${CART_CATEGORY_PAGE}
    Should Be Equal    ${affichee}    ${nom}
    ...    msg=La catégorie affichée est « ${affichee} » et non « ${nom} » : la sélection n'a pas navigué.

Compter Les Produits De La Categorie
    [Documentation]    Nombre de produits rendus dans la catégorie ouverte.
    ...
    ...    La portée est essentielle : la page d'accueil garde ses propres
    ...    listes de produits (mis en avant, consultés, favoris) dans le
    ...    registre. Un comptage global des lignes produit en verrait 13 là où
    ...    la catégorie en contient 3 : c'est `viewId` qui fait la différence
    ...    entre « les produits de cette catégorie » et « toutes les lignes
    ...    produit de l'application ».
    ${nb}=    Get Ui5 Match Count    controlType=${CART_PRODUCT_ITEM}
    ...    viewId=${CART_CATEGORY_VIEW}
    RETURN    ${nb}

Lister Les Produits De La Categorie
    [Documentation]    Noms des produits de la catégorie ouverte, dans l'ordre
    ...    d'affichage, lus sur la propriété `title` des lignes.
    ${noms}=    Get Ui5 Properties    ${CART_TITLE_PROPERTY}
    ...    controlType=${CART_PRODUCT_ITEM}    viewId=${CART_CATEGORY_VIEW}
    RETURN    ${noms}

Lister Les Produits Commandables
    [Documentation]    Produits de la catégorie ouverte qui s'ajoutent au panier
    ...    SANS détour, c'est-à-dire disponibles.
    ...
    ...    Relevé live : ajouter un produit en rupture ouvre un dialogue de
    ...    confirmation (« currently out of stock, but you can order it »), et un
    ...    produit arrêté un dialogue d'information. Une campagne qui ignore ce
    ...    dialogue le laisse OUVERT, donc modal, et tout ce qui suit échoue sur
    ...    des éléments « non cliquables » qui n'ont rien à se reprocher. Le tri
    ...    se fait sur l'ÉTAT du statut (`Success`), jamais sur son texte, qui
    ...    suit la locale.
    ${noms}=    Lister Les Produits De La Categorie
    ${etats}=    Get Ui5 Properties    ${CART_STATE_PROPERTY}
    ...    controlType=${CART_STATUS_CONTROL}    viewId=${CART_CATEGORY_VIEW}
    ${commandables}=    Evaluate
    ...    [n for n, e in zip($noms, $etats) if e == $CART_ORDERABLE_STATE]
    RETURN    ${commandables}

Lister Les Produits Non Selectionnes
    [Documentation]    Produits de la catégorie ouverte qui ne sont PAS déjà
    ...    sélectionnés dans la liste.
    ...
    ...    Ce mot-clé existe à cause d'un comportement bien réel de
    ...    `sap.m.List` en mode sélection : cliquer une ligne DÉJÀ sélectionnée
    ...    n'émet pas d'événement de sélection, donc ne navigue pas. Mesuré live
    ...    le 2026-08-24 : le deuxième test qui rouvrait « le premier produit de
    ...    la première catégorie » cliquait sans effet, la fiche produit restait
    ...    absente de l'écran, et l'échec tombait plus loin sur un bouton
    ...    « invisible » qui n'avait rien à se reprocher.
    ${noms}=    Lister Les Produits De La Categorie
    ${etats}=    Get Ui5 Properties    ${CART_SELECTED_PROPERTY}
    ...    controlType=${CART_PRODUCT_ITEM}    viewId=${CART_CATEGORY_VIEW}
    ${libres}=    Evaluate    [n for n, s in zip($noms, $etats) if not s]
    RETURN    ${libres}

Lister Les Produits Ouvrables
    [Documentation]    Produits de la catégorie ouverte qu'un scénario peut
    ...    réellement ouvrir puis ajouter : commandables (pas de dialogue à
    ...    l'ajout) ET pas déjà sélectionnés (une ligne déjà sélectionnée ne
    ...    renavigue pas). L'intersection des deux contraintes relevées live.
    ${commandables}=    Lister Les Produits Commandables
    ${libres}=    Lister Les Produits Non Selectionnes
    ${ouvrables}=    Evaluate    [n for n in $commandables if n in $libres]
    RETURN    ${ouvrables}

Ouvrir Le Produit
    [Documentation]    Ouvre la fiche d'un produit de la catégorie affichée, et
    ...    ne rend la main que lorsque cette fiche est RÉELLEMENT à l'écran avec
    ...    le bon produit.
    ...
    ...    La vérification n'est pas décorative : un clic sur une ligne déjà
    ...    sélectionnée ne navigue pas, et sans elle l'échec se produit deux
    ...    étapes plus loin, sur un bouton de la fiche qualifié d'« invisible »,
    ...    ce qui envoie chercher une dérive de localisateur là où il n'y en a
    ...    pas.
    [Arguments]    ${nom}
    Click Ui5 Control    controlType=${CART_PRODUCT_ITEM}    properties={'title': '${nom}'}
    ...    viewId=${CART_CATEGORY_VIEW}
    Wait For Ui5 Idle
    Wait Until Keyword Succeeds    15s    1s    La Fiche Du Produit Est A L Ecran    ${nom}

La Fiche Du Produit Est A L Ecran
    [Documentation]    Prédicat d'ouverture : la fiche produit est visible À
    ...    L'ÉCRAN (et pas seulement rendue dans une colonne repliée) et elle
    ...    porte le produit demandé.
    [Arguments]    ${nom}
    ${selecteur}=    Resolve Ui5 Control    id=${CART_PRODUCT_PAGE}
    Get Element States    ${selecteur}    contains    visible
    ...    message=La fiche produit est rendue mais masquée : la navigation n'a pas eu lieu.
    ${affiche}=    Lire Le Nom Du Produit Affiche
    Should Be Equal    ${affiche}    ${nom}
    ...    msg=La fiche affichée porte « ${affiche} » et non « ${nom} » : la sélection n'a pas navigué.

Lire Le Nom Du Produit Affiche
    [Documentation]    Nom du produit porté par l'en-tête de la fiche produit,
    ...    lu sur la propriété du contrôle. C'est une donnée (le nom du
    ...    produit), pas un libellé d'interface.
    ${nom}=    Get Ui5 Property    ${CART_TITLE_PROPERTY}    controlType=${CART_PRODUCT_HEADER}
    RETURN    ${nom}

La Fiche Produit Est Affichee
    [Documentation]    Assertion d'écran, 100 % locale-indépendante : l'image du
    ...    produit porte un id de vue stable, elle est rendue.
    Ui5 Control Should Be Visible    id=${CART_PRODUCT_IMAGE}

Ajouter Le Produit Au Panier
    [Documentation]    Déclenche l'ajout au panier depuis la fiche produit, puis
    ...    attend le repos réel.
    Click Ui5 By Xpath    ${CART_ADD_XPATH}
    Wait For Ui5 Idle
    Aucun Dialogue N Est Ouvert

Aucun Dialogue N Est Ouvert
    [Documentation]    Vérifie qu'aucune boîte de dialogue n'est restée ouverte.
    ...
    ...    Posé après l'ajout au panier parce qu'un dialogue non traité est
    ...    MODAL : il ne fait pas échouer l'action qui l'a ouvert, il fait
    ...    échouer tout ce qui suit, sur des contrôles « non cliquables » qui
    ...    n'ont rien à se reprocher. Mieux vaut échouer ici, où la cause est
    ...    lisible (le diagnostic de teardown journalise le texte du dialogue).
    ${nb}=    Get Ui5 Match Count    controlType=${CART_DIALOG_CONTROL}
    Should Be Equal As Integers    ${nb}    0
    ...    msg=Un dialogue est resté ouvert : l'action demande une confirmation non prévue par ce scénario.

Lire Les Messages De L Application
    [Documentation]    Messages UI5 de l'application : `{messages, toasts}`. Le
    ...    hook de captation des `MessageToast` est posé à l'injection du
    ...    bundle : un toast disparu de l'écran reste dans cette liste.
    ${messages}=    Get Ui5 Messages
    RETURN    ${messages}

Aucun Message D Erreur N A Ete Emis
    [Documentation]    Assertion locale-indépendante : on juge le TYPE du
    ...    message, jamais son texte (convention 3).
    Ui5 Should Have No Messages Of Type    Error

Basculer L Affichage Du Panier
    [Documentation]    Actionne le bouton BASCULE du panier, dans l'en-tête de la
    ...    fiche produit. Interne : les scénarios expriment une intention
    ...    (`Ouvrir Le Panier`, `Fermer Le Panier`), pas un geste.
    Click Ui5 By Xpath    ${CART_TOGGLE_XPATH}
    Wait For Ui5 Idle

Le Panier Est A L Ecran
    [Documentation]    Le panier est-il affiché ? Répond True/False sans jamais
    ...    échouer : c'est une observation, pas une assertion.
    ${nb}=    Get Ui5 Match Count    id=${CART_PAGE}
    IF    ${nb} == 0    RETURN    ${False}
    ${selecteur}=    Resolve Ui5 Control    id=${CART_PAGE}
    ${visible}=    Run Keyword And Return Status
    ...    Get Element States    ${selecteur}    contains    visible
    RETURN    ${visible}

Ouvrir Le Panier
    [Documentation]    Rend le panier VISIBLE, quel que soit son état de départ.
    ...
    ...    Idempotent à dessein : le contrôle est une bascule, donc le cliquer
    ...    revient à parier sur l'état courant. Le pari se perd dès qu'une
    ...    navigation a refermé la colonne entre-temps, et le scénario continue
    ...    en croyant le panier ouvert : l'échec tombe alors sur le bouton
    ...    suivant, jamais sur la cause.
    ${ouvert}=    Le Panier Est A L Ecran
    IF    ${ouvert}    RETURN
    Basculer L Affichage Du Panier
    Wait Until Keyword Succeeds    15s    1s    Le Panier Doit Etre A L Ecran

Fermer Le Panier
    [Documentation]    Rend le panier ABSENT de l'écran, quel que soit son état
    ...    de départ. Même raison d'être idempotent que `Ouvrir Le Panier`.
    ${ouvert}=    Le Panier Est A L Ecran
    IF    not ${ouvert}    RETURN
    Basculer L Affichage Du Panier
    Wait Until Keyword Succeeds    15s    1s    Le Panier Ne Doit Plus Etre A L Ecran

Le Panier Doit Etre A L Ecran
    [Documentation]    Prédicat d'attente : le panier est affiché.
    ${ouvert}=    Le Panier Est A L Ecran
    Should Be True    ${ouvert}    msg=Le panier n'est pas affiché.

Le Panier Ne Doit Plus Etre A L Ecran
    [Documentation]    Prédicat d'attente : le panier n'est plus affiché.
    ${ouvert}=    Le Panier Est A L Ecran
    Should Not Be True    ${ouvert}    msg=Le panier est toujours affiché.

Compter Les Lignes Du Panier
    [Documentation]    Nombre de lignes que la VUE du panier porte actuellement.
    ...
    ...    Attention à la portée de cette mesure, une hypothèse fausse a coûté un
    ...    run : tant que le panier n'a jamais été OUVERT, sa vue n'existe pas et
    ...    ce comptage rend 0, alors que le modèle peut déjà contenir des
    ...    articles ajoutés depuis une fiche produit. Mesurer un « avant » sans
    ...    avoir ouvert le panier compare donc une vue absente à une vue remplie.
    ...    Ouvrir le panier avant de compter (`Ouvrir Le Panier`, ou
    ...    `Ouvrir Le Panier`, qui est idempotent).
    ${nb}=    Get Ui5 Match Count    controlType=${CART_PRODUCT_ITEM}    viewId=${CART_ENTRY_LIST}
    RETURN    ${nb}

Lister Les Produits Du Panier
    [Documentation]    Noms des produits présents dans le panier, lus sur la
    ...    propriété des lignes. Rend une liste vide tant que la vue du panier
    ...    n'a jamais été ouverte (même réserve que `Compter Les Lignes Du
    ...    Panier`).
    ${noms}=    Get Ui5 Properties    ${CART_TITLE_PROPERTY}
    ...    controlType=${CART_PRODUCT_ITEM}    viewId=${CART_ENTRY_LIST}
    RETURN    ${noms}

Preparer Un Produit Absent Du Panier
    [Documentation]    Ouvre la fiche d'un produit qui n'est PAS déjà dans le
    ...    panier, et retourne son nom. Le panier est laissé fermé, la fiche à
    ...    l'écran.
    ...
    ...    Ce détour existe pour une raison de métier, pas de technique :
    ...    ajouter un produit DÉJÀ présent n'ajoute pas de ligne, il incrémente
    ...    la quantité de la ligne existante (`intro` passe à « 2 x »). Un
    ...    scénario qui veut prouver « une ligne de plus » doit donc partir d'un
    ...    produit absent, sans quoi il mesure autre chose que ce qu'il annonce.
    ...
    ...    Le panier est ouvert une première fois à dessein : tant que sa vue
    ...    n'a jamais été rendue, elle ne porte aucune ligne, et son contenu
    ...    serait lu comme vide alors que le modèle, lui, est déjà rempli.
    Ouvrir Un Produit Disponible
    Ouvrir Le Panier
    ${dans_le_panier}=    Lister Les Produits Du Panier
    Fermer Le Panier
    ${categories}=    Lister Les Categories
    FOR    ${categorie}    IN    @{categories}
        ${ouverte}=    Run Keyword And Return Status    Ouvrir La Categorie    ${categorie}
        IF    not ${ouverte}    CONTINUE
        ${produits}=    Lister Les Produits Ouvrables
        FOR    ${produit}    IN    @{produits}
            IF    $produit in $dans_le_panier    CONTINUE
            Ouvrir Le Produit    ${produit}
            RETURN    ${produit}
        END
    END
    Fail    Tous les produits ouvrables sont déjà dans le panier : impossible de prouver un ajout.

Le Panier Contient Le Produit
    [Documentation]    Vérifie qu'une ligne du panier porte ce produit.
    [Arguments]    ${nom}
    ${nb}=    Get Ui5 Match Count    controlType=${CART_PRODUCT_ITEM}    viewId=${CART_ENTRY_LIST}
    ...    properties={'title': '${nom}'}
    Should Be True    ${nb} > 0
    ...    msg=Le produit « ${nom} » n'est pas dans le panier.

Lire Le Total Du Panier
    [Documentation]    Texte du total du panier, tel qu'il est rendu (« Total:
    ...    45,00 EUR » en locale française). Retourné BRUT et journalisé : il
    ...    sert à comparer deux mesures du même run, jamais à asserter un
    ...    format.
    ${total}=    Get Ui5 Text    id=${CART_TOTAL_TEXT}
    RETURN    ${total}

Passer Le Panier En Edition
    [Documentation]    Bascule le panier en mode édition : c'est ce mode qui
    ...    fait apparaître le bouton de suppression de chaque ligne.
    Click Ui5 Control    id=${CART_EDIT_BUTTON}
    Wait For Ui5 Idle

Quitter L Edition Du Panier
    [Documentation]    Sort du mode édition si l'application y est encore.
    ...    Idempotent : ne fait rien quand le panier est déjà en lecture.
    ${nb}=    Get Ui5 Match Count    id=${CART_DONE_BUTTON}
    IF    ${nb} > 0
        Click Ui5 Control    id=${CART_DONE_BUTTON}
        Wait For Ui5 Idle
    END

Le Dialogue De Confirmation Propose Deux Actions
    [Documentation]    Vérifie la STRUCTURE du dialogue de confirmation avant de
    ...    l'actionner par position : deux boutons d'action, confirmer puis
    ...    annuler. C'est ce qui rend la confirmation positionnelle légitime
    ...    plutôt que fragile, sur un dialogue dont les libellés sont traduits.
    Ui5 Dialog Should Be Visible
    Resolve Ui5 By Xpath    ${CART_DIALOG_BUTTON_XPATH}    ${CART_DIALOG_CONFIRM_INDEX}
    Resolve Ui5 By Xpath    ${CART_DIALOG_BUTTON_XPATH}    ${CART_DIALOG_CANCEL_INDEX}

Confirmer Le Dialogue
    [Documentation]    Actionne la confirmation du dialogue par sa position.
    Click Ui5 By Xpath    ${CART_DIALOG_BUTTON_XPATH}    ${CART_DIALOG_CONFIRM_INDEX}
    Wait For Ui5 Idle

Supprimer La Premiere Ligne Du Panier
    [Documentation]    Supprime la première ligne du panier, dialogue de
    ...    confirmation compris. Le panier doit être en mode édition. Prévu pour
    ...    le vidage en teardown : un scénario qui défait SON ajout doit viser
    ...    le produit qu'il a ajouté (`Supprimer La Ligne Du Panier`), sans quoi
    ...    il rend le bon compte en supprimant la mauvaise ligne.
    Click Ui5 By Xpath    ${CART_DELETE_XPATH}    ${0}
    Le Dialogue De Confirmation Propose Deux Actions
    Confirmer Le Dialogue

Supprimer La Ligne Du Panier
    [Documentation]    Supprime la ligne du produit demandé, dialogue de
    ...    confirmation compris. Le panier doit être en mode édition.
    [Arguments]    ${nom}
    Click Ui5 By Xpath
    ...    //List[@id='${CART_ENTRY_LIST}']//ObjectListItem[@title='${nom}']//Button[@icon='${CART_DELETE_ICON}']
    Le Dialogue De Confirmation Propose Deux Actions
    Confirmer Le Dialogue

Vider Le Panier
    [Documentation]    Ramène le panier à zéro ligne et le laisse en lecture :
    ...    le mot-clé de réversibilité, prévu pour un teardown.
    ...
    ...    Ne suppose aucun état : il ne fait rien si le panier est vide (ou
    ...    n'a jamais été ouvert), passe en édition seulement si nécessaire, et
    ...    ressort du mode édition à la fin. La borne de boucle est un
    ...    garde-fou : une suppression qui n'aboutit pas doit s'arrêter, pas
    ...    tourner.
    Run Keyword And Return Status    Ouvrir Le Panier
    ${lignes}=    Compter Les Lignes Du Panier
    IF    ${lignes} == 0
        Quitter L Edition Du Panier
        RETURN
    END
    ${edition}=    Get Ui5 Match Count    id=${CART_EDIT_BUTTON}
    IF    ${edition} > 0    Passer Le Panier En Edition
    WHILE    ${lignes} > 0    limit=20
        ${supprimee}=    Run Keyword And Return Status    Supprimer La Premiere Ligne Du Panier
        IF    not ${supprimee}    BREAK
        ${restantes}=    Compter Les Lignes Du Panier
        # Une suppression qui ne réduit pas le compte ne se réparera pas en
        # recommençant : insister ferait tourner la boucle jusqu'à sa borne, à
        # une quinzaine de secondes l'itération, pour un teardown qui n'aurait
        # toujours rien nettoyé.
        IF    ${restantes} >= ${lignes}    BREAK
        ${lignes}=    Set Variable    ${restantes}
    END
    Quitter L Edition Du Panier
    ${restes}=    Compter Les Lignes Du Panier
    Should Be Equal As Integers    ${restes}    0
    ...    msg=Le panier n'a pas pu être vidé : ${restes} ligne(s) restante(s).
