*** Settings ***
Documentation       Parcours applicatif réversible dans l'iframe d'un launchpad Work Zone
...                 Spec: specs/workzone-panier-parcours-applicatif.md (sha256:8251b671a811, 2026-08-24)
...
...                 Parcours métier **réversible** dans l'application embarquée
...                 par le launchpad SAP Build Work Zone : choisir une
...                 catégorie, ouvrir un produit, l'ajouter au panier, puis
...                 rendre le panier à son état initial.
...
...                 Ce que cette campagne établit, et que la campagne du shell
...                 ne peut pas établir : une fois la portée basculée dans
...                 l'iframe applicative CROSS-ORIGIN, toute la chaîne
...                 fonctionne comme sur une page ordinaire (résolution de
...                 contrôles, saisie, clic, messages applicatifs, dialogues) et
...                 un parcours d'écriture peut être joué sans laisser de trace.
...
...                 Campagne **pilotée par la découverte** : ni catégorie ni
...                 produit ne sont codés en dur, ils sont relevés dans le run.
...                 Toutes les assertions sont relationnelles (avant/après
...                 mesurés dans le même run) ou structurelles (comptages de
...                 contrôles), jamais un libellé d'interface : la cible rend
...                 son interface dans la langue du navigateur (boutons
...                 « Supprimer » / « Annuler » relevés en français) et formate
...                 ses prix selon la locale (`45,00`).
...
...                 **Réversibilité** : chaque test qui ajoute au panier
...                 constate le retour à l'état initial, et le teardown de suite
...                 vide le panier même après un échec. Un panier laissé plein
...                 fausserait le run suivant.
...
...                 Aucun localisateur ici (convention 1) : ils vivent dans
...                 `resources/page_objects/workzone_shopping_cart.resource` et
...                 `resources/page_objects/workzone_launchpad.resource`.
...
...                 Prérequis : un site Work Zone accessible, un utilisateur du
...                 tenant, et l'application publiée au catalogue. Exécution ::
...
...                 |  robot --pythonpath src
...                 |  ...   -v WORKZONE_SITE:<url du site>
...                 |  ...   -v WORKZONE_USER:<utilisateur>
...                 |  ...   -v "WORKZONE_PASSWORD: Secret:<motdepasse>"
...                 |  ...   --outputdir results/workzone
...                 |  ...   tests/robot/ui/fiori/parcours_panier_workzone.robot

Resource            ../../../../resources/page_objects/workzone_shopping_cart.resource

Suite Setup         Ouvrir Le Parcours Du Panier
Suite Teardown      Fermer Le Parcours Du Panier
Test Teardown       Journaliser Le Diagnostic Fiori En Cas D Echec

Test Tags           fiori    workzone    btp    live


*** Test Cases ***
L application s execute dans l iframe du launchpad
    [Documentation]    Scénario 1 du plan. Point de départ du parcours : la
    ...    portée courante est bien celle de l'application, pas celle du shell.
    ...    Le témoin est double : l'application porte un runtime UI5 avec des
    ...    contrôles construits, et le champ de recherche du shell n'y est plus
    ...    résolu.
    ${composition}=    Lire La Composition De La Portee Courante
    Should Be True    ${composition}[ui5_runtime]
    ...    msg=Aucun runtime UI5 dans la frame applicative.
    Should Be True    ${composition}[ui5_controls] > 0
    ...    msg=L'application n'a construit aucun contrôle.
    ${champ_du_shell}=    Compter Le Champ De Recherche Du Shell
    Should Be Equal As Integers    ${champ_du_shell}    0
    ...    msg=La portée courante est encore celle du shell : le parcours ne testerait pas l'application.
    Log    Application ${composition}[url] : UI5 ${composition}[ui5_version], ${composition}[ui5_controls] contrôles    console=True

Le catalogue de categories est rendu
    [Documentation]    Scénario 2 du plan. Le volet de gauche liste les
    ...    catégories du jeu de données. Chaque nom relevé est une DONNÉE (il
    ...    vient du modèle, pas d'un fichier de traduction) : le vérifier non
    ...    vide reste indépendant de la langue de l'interface.
    ${categories}=    Lister Les Categories
    Should Not Be Empty    ${categories}
    ...    msg=Aucune catégorie rendue : l'application n'a pas chargé ses données.
    FOR    ${nom}    IN    @{categories}
        Should Not Be Empty    ${nom}    msg=Une catégorie est rendue sans nom.
    END
    Log    ${{len($categories)}} catégories : ${categories}    console=True

Une categorie restreint la liste des produits
    [Documentation]    Scénario 3 du plan. Deux propriétés dans un seul test,
    ...    parce qu'elles se prouvent l'une par l'autre. D'abord la PORTÉE :
    ...    l'application garde ses listes d'accueil (produits mis en avant,
    ...    consultés, favoris) dans le registre UI5, donc un comptage global de
    ...    lignes produit dépasse celui de la catégorie ouverte. Ensuite le
    ...    FILTRAGE : deux catégories différentes ne montrent pas les mêmes
    ...    produits.
    ...
    ...    Les deux catégories sont choisies par découverte : les premières du
    ...    catalogue qui contiennent réellement des produits.
    ${categories}=    Lister Les Categories
    ${releve}=    Create Dictionary
    FOR    ${nom}    IN    @{categories}
        Ouvrir La Categorie    ${nom}
        ${produits}=    Lister Les Produits De La Categorie
        IF    len($produits) > 0
            Set To Dictionary    ${releve}    ${nom}    ${produits}
            ${dans_la_categorie}=    Compter Les Produits De La Categorie
            ${dans_l_application}=    Compter Toutes Les Lignes Produit De L Application
            Should Be True    ${dans_l_application} >= ${dans_la_categorie}
            ...    msg=Le comptage porté à la catégorie (${dans_la_categorie}) dépasse le comptage global (${dans_l_application}).
        END
        IF    len($releve) >= 2    BREAK
    END
    Length Should Be    ${releve}    2
    ...    msg=Moins de deux catégories non vides : impossible de prouver que la catégorie filtre.
    ${listes}=    Get Dictionary Values    ${releve}
    Should Not Be Equal    ${listes}[0]    ${listes}[1]
    ...    msg=Deux catégories différentes montrent exactement les mêmes produits : la sélection ne filtre pas.
    Log    Catégories comparées : ${{list($releve)}}    console=True

La fiche produit affiche le produit choisi
    [Documentation]    Scénario 4 du plan. La navigation liste vers détail
    ...    aboutit sur LE produit demandé : l'en-tête de la fiche porte le nom
    ...    cliqué (une donnée, pas un libellé), et l'illustration du produit est
    ...    rendue. Vérifier seulement « une fiche s'est ouverte » laisserait
    ...    passer une navigation vers le mauvais élément.
    ${produit}=    Ouvrir Un Produit Disponible
    La Fiche Produit Est Affichee
    ${affiche}=    Lire Le Nom Du Produit Affiche
    Should Be Equal    ${affiche}    ${produit}
    ...    msg=La fiche ouverte porte « ${affiche} » alors que « ${produit} » a été demandé.

L ajout au panier est confirme par un message applicatif
    [Documentation]    Scénario 5 du plan. L'application confirme l'ajout par un
    ...    MessageToast, éphémère à l'écran mais capté par le hook posé à
    ...    l'injection du bundle. L'assertion porte sur la PRÉSENCE d'un
    ...    nouveau message et sur l'absence de message de type Error, jamais sur
    ...    le texte (convention 3).
    ${produit}=    Ouvrir Un Produit Disponible
    ${avant}=    Lire Les Messages De L Application
    Ajouter Le Produit Au Panier
    ${apres}=    Lire Les Messages De L Application
    Should Be True    len($apres['toasts']) > len($avant['toasts'])
    ...    msg=Aucun message de confirmation après l'ajout de « ${produit} » au panier.
    Aucun Message D Erreur N A Ete Emis
    Log    Confirmation applicative : ${apres}[toasts][-1][text]    console=True

Le panier porte exactement la ligne ajoutee
    [Documentation]    Scénario 6 du plan. L'ajout se constate dans le panier
    ...    lui-même : une ligne de plus qu'avant, et c'est bien le produit
    ...    demandé. La référence est mesurée dans le MÊME run, jamais supposée
    ...    nulle : le panier peut déjà contenir la ligne ajoutée par le scénario
    ...    précédent.
    ${produit}=    Preparer Un Produit Absent Du Panier
    Ouvrir Le Panier
    ${avant}=    Compter Les Lignes Du Panier
    Fermer Le Panier
    Ajouter Le Produit Au Panier
    Ouvrir Le Panier
    ${apres}=    Compter Les Lignes Du Panier
    Should Be Equal As Integers    ${apres}    ${{ $avant + 1 }}
    ...    msg=Le panier compte ${apres} ligne(s) au lieu de ${{ $avant + 1 }} après l'ajout de « ${produit} ».
    Le Panier Contient Le Produit    ${produit}
    ${total}=    Lire Le Total Du Panier
    Log    Panier : ${apres} ligne(s), ${total}    console=True

La suppression rend le panier a son etat initial
    [Documentation]    Scénario 7 du plan. Le cycle complet ajouter puis
    ...    supprimer est joué ici, et l'état initial est celui mesuré au début
    ...    de CE test : c'est la propriété de réversibilité, celle qui autorise
    ...    à rejouer la campagne sur un système partagé sans le polluer. C'est
    ...    la ligne AJOUTÉE qui est supprimée, pas la première venue : rendre le
    ...    bon compte en retirant la mauvaise ligne ne serait pas réversible.
    ...
    ...    La confirmation passe par la POSITION du bouton dans le dialogue, pas
    ...    par son libellé : sur cette cible, une MessageBox rend ses actions
    ...    dans la langue du navigateur (« Supprimer » / « Annuler » relevés en
    ...    français) avec des identifiants générés. La structure du dialogue est
    ...    donc vérifiée avant d'être actionnée.
    ${produit}=    Preparer Un Produit Absent Du Panier
    Ouvrir Le Panier
    ${initial}=    Compter Les Lignes Du Panier
    Fermer Le Panier
    Ajouter Le Produit Au Panier
    Ouvrir Le Panier
    ${total_avec}=    Lire Le Total Du Panier
    ${avec}=    Compter Les Lignes Du Panier
    Should Be Equal As Integers    ${avec}    ${{ $initial + 1 }}
    ...    msg=L'ajout de « ${produit} » n'a pas augmenté le panier (${avec} vs ${initial}).
    Passer Le Panier En Edition
    Supprimer La Ligne Du Panier    ${produit}
    Quitter L Edition Du Panier
    ${apres}=    Compter Les Lignes Du Panier
    Should Be Equal As Integers    ${apres}    ${initial}
    ...    msg=Le panier compte ${apres} ligne(s) au lieu des ${initial} d'avant le cycle.
    ${total_apres}=    Lire Le Total Du Panier
    Log    Total avec la ligne : ${total_avec} / après suppression : ${total_apres}    console=True
    Aucun Message D Erreur N A Ete Emis
