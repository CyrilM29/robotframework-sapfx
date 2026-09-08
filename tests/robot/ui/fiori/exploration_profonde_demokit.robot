*** Settings ***
Documentation       Exploration en profondeur du Demo Kit OpenUI5
...                 Spec: specs/openui5-demokit-exploration-profonde.md (sha256:4283d8e028cb, 2026-09-05)
...                 Generated from specs/openui5-demokit-exploration-profonde.md
...                 by sap-generator: re-run the generator rather than
...                 hand-editing locators here.
...
...                 Campagne **complémentaire** de
...                 `navigation_interaction_demokit.robot` : elle couvre ce que
...                 la campagne sœur ne touche pas. La section Documentation
...                 (`#/topic`) et ses liens croisés, la fiche d'API AU-DELÀ de
...                 la table des propriétés (méthodes, événements, éléments
...                 empruntés, bascules « borrowed »), la galerie
...                 d'échantillons (`#/entity/...`) avec sa vue du code source,
...                 les pages Demo Apps et Resources en perception seule, et la
...                 sentinelle d'accumulation (l'iframe d'échantillon SURVIT à
...                 la navigation, invisible).
...
...                 Le piège central de la cible, et il commande la forme de
...                 toutes les assertions : cette SPA ACCUMULE tout ce qu'elle
...                 a montré (masters rendus côte à côte, contenu des sujets
...                 déjà lus encore au DOM, 511 contrôles à froid contre 5442
...                 après un tour complet). Toute lecture est donc PORTÉE par
...                 son conteneur, et aucun plancher global n'est asserté hors
...                 d'une page fraîche.
...
...                 Les vérités techniques assertées sont locale-indépendantes
...                 (convention 3) : GUID de sujets, routes de hash, clés
...                 d'onglets et de fichiers, noms qualifiés, suffixes
...                 d'identifiants, contextes de liaison. Les titres et la
...                 langue se journalisent, jamais ne s'assertent (la langue de
...                 cette cible a changé en cours de run, et l'instantané ARIA
...                 du 2026-09-05 mêlait français et anglais sur la même page).
...
...                 **LECTURE SEULE** : le seul réglage touché (case « borrowed
...                 properties » d'une fiche d'API) est remis dans son état
...                 RELEVÉ, dans le scénario et par un teardown qui s'exécute
...                 même sur échec. Le téléchargement, l'ouverture d'onglet et
...                 le mode adaptation runtime sont PERÇUS, jamais actionnés.
...
...                 Aucun localisateur ici (convention 1) : ils vivent dans
...                 `resources/page_objects/openui5_demokit.resource`.
...
...                 Prérequis : un accès réseau à `sdk.openui5.org`. Aucune
...                 authentification, aucune donnée métier, aucun système SAP.
...                 Exécution ::
...
...                 |  robot --pythonpath src
...                 |  ...   --outputdir results/exploration_profonde_demokit
...                 |  ...   tests/robot/ui/fiori/exploration_profonde_demokit.robot
...
...                 Exécution non surveillée (CI) ::
...
...                 |  robot --pythonpath src -v DEMOKIT_HEADLESS:True ...

Resource            ../../../../resources/page_objects/openui5_demokit.resource

Suite Setup         Run Keywords    Ouvrir Le Demo Kit
...                     AND    Memoriser L Etat Initial Du Demo Kit
Suite Teardown      Clore La Campagne Demo Kit
Test Teardown       Ramener Le Demo Kit A Son Etat De Reference

Test Tags           fiori    openui5    demokit    live    readonly


*** Test Cases ***
L arbre des sujets de la Documentation porte des identifiants stables
    [Documentation]    Scénario 1 du plan. L'identifiant d'un sujet est son
    ...    « loio », un GUID hexadécimal de 32 caractères, PAS un nom
    ...    qualifié : l'assertion est structurelle (motif), indépendante de la
    ...    langue et du contenu. Les titres des nœuds sont de la prose
    ...    documentaire anglaise : journalisés, jamais assertés. Le comptage
    ...    est PORTÉ par le conteneur de l'arbre des sujets, l'arbre de l'API
    ...    partageant le même type de nœuds.
    Ouvrir La Section    topic
    Le Champ De Filtre Des Sujets Doit Etre Rendu
    ${noeuds}=    Attendre L Arbre Des Sujets
    ${cibles}=    Lister Les Identifiants De Sujets
    Les Identifiants De Sujets Doivent Etre Des Guid    ${cibles}
    Log    ${noeuds} nœud(s) racine (compte journalisé, jamais gravé) ; identifiants de sujets : ${cibles}

Un sujet s ouvre par son noeud navigation et depliage dans le meme geste
    [Documentation]    Scénario 2 du plan. Le clic sur un nœud NAVIGUE (le
    ...    fragment porte le GUID, la vue de détail RÉELLE est rendue : deux
    ...    vues partagent le suffixe court de page, l'ancre est la longue) ET
    ...    DÉPLIE (le comptage de l'arbre croît strictement : 9 vers 30
    ...    observés, la RELATION est l'assertion, jamais les nombres).
    Ouvrir La Section    topic
    ${avant}=    Attendre L Arbre Des Sujets
    Ouvrir Le Sujet    ${DEMOKIT_SUJET_ESSENTIALS}
    ${apres}=    Compter Les Noeuds De L Arbre Des Sujets
    Should Be True    ${apres} > ${avant}
    ...    msg=Le clic sur le nœud n'a pas déplié l'arbre : ${apres} nœud(s) contre ${avant}.
    ${titre}=    Get Title
    Log    Sujet ouvert : arbre passé de ${avant} à ${apres} nœuds ; titre du document (prose, jamais assertée) : ${titre}

Les liens croises d un sujet menent a la Reference de l API
    [Documentation]    Scénario 3 du plan. Les liens croisés du contenu
    ...    documentaire sont des ancres DOM RELATIVES sans `#/` (un sélecteur
    ...    qui cherche la forme à dièse rend 0 en croyant qu'il n'y a pas de
    ...    liens, mesuré) : moteur DOM obligatoire, et comptage PORTÉ par le
    ...    détail du sujet, le contenu des sujets déjà lus restant au DOM. Le
    ...    cœur du scénario : le clic change de SECTION, la clé active passe
    ...    de `topic` à `api`.
    Ouvrir Le Sujet Par Sa Route    ${DEMOKIT_SUJET_DATA_BINDING}
    La Section Active Doit Etre    topic
    ${liens}=    Compter Les Liens Croises Vers L Api
    Should Be True    ${liens} > 0
    ...    msg=Le sujet n'expose aucun lien croisé relatif vers l'API dans la portée de son détail.
    Log    ${liens} lien(s) croisé(s) vers l'API dans le sujet (compte journalisé).
    Ouvrir Le Lien Croise Vers L Api    sap.ui.model.BindingMode

La fiche d API se sous navigue par ses rubriques et ses liens de membre
    [Documentation]    Scénario 4 du plan. Les rubriques attendues sont une
    ...    INCLUSION, pas une égalité (7 observées). Le lien d'un membre donne
    ...    un fragment dont le second dièse est ENCODÉ (`%23events/press`
    ...    observé : l'assertion accepte les deux formes). La barre d'ancrage
    ...    est un SCROLL SPY, pas un témoin de route : elle peut se stabiliser
    ...    sur la rubrique voisine d'une rubrique courte (mesuré au premier
    ...    run), donc la route se prouve au fragment et la barre atteste
    ...    seulement que le défilement a quitté la rubrique d'ouverture.
    Ouvrir La Fiche D Api    sap.m.Button
    ${rubriques}=    Lister Les Rubriques De La Fiche
    Log    Rubriques de la fiche : ${rubriques}
    FOR    ${attendue}    IN    @{DEMOKIT_RUBRIQUES_ATTENDUES}
        List Should Contain Value    ${rubriques}    ${attendue}
        ...    msg=La fiche ne porte plus la rubrique ${attendue} : ${rubriques}
    END
    Ouvrir Le Membre De La Fiche    sap.m.Button    ${DEMOKIT_SECTION_EVENTS}    press

Les methodes et evenements se lisent par leurs liens techniques
    [Documentation]    Scénario 5 du plan. Deux familles de tables de doc, deux
    ...    voies de lecture : propriétés et agrégations portent des contextes
    ...    de liaison, méthodes et événements N'EN PORTENT PAS (`binding:
    ...    None` sur toutes les lignes, vérifié). Le scénario ASSERTE ce fait
    ...    pour que la voie de lecture erronée, qui rend des listes vides
    ...    plausibles, ne revienne pas. Les noms techniques se lisent sur les
    ...    liens DOM de chaque rubrique, le préfixe de classe filtrant les
    ...    membres propres des hérités.
    Ouvrir La Fiche D Api    sap.m.Button
    ${nb_methodes}=    Compter Les Lignes De La Rubrique    ${DEMOKIT_SECTION_METHODS}
    Should Be True    ${nb_methodes} > 0
    ...    msg=La table des méthodes ne porte aucune ligne.
    ${nb_evenements}=    Compter Les Lignes De La Rubrique    ${DEMOKIT_SECTION_EVENTS}
    Should Be True    ${nb_evenements} > 0
    ...    msg=La table des événements ne porte aucune ligne.
    Les Lignes De La Rubrique Ne Portent Pas De Contexte    ${DEMOKIT_SECTION_METHODS}
    Les Lignes De La Rubrique Ne Portent Pas De Contexte    ${DEMOKIT_SECTION_EVENTS}
    ${evenements}=    Lire Les Membres Propres De La Rubrique    sap.m.Button    ${DEMOKIT_SECTION_EVENTS}
    List Should Contain Value    ${evenements}    press
    ...    msg=L'événement définitoire d'un bouton (press) manque aux événements propres : ${evenements}
    ${methodes}=    Lire Les Membres Propres De La Rubrique    sap.m.Button    ${DEMOKIT_SECTION_METHODS}
    Les Noms Doivent Etre Des Identifiants Javascript    ${methodes}
    Les Noms Doivent Etre Des Identifiants Javascript    ${evenements}
    Log    ${nb_methodes} ligne(s) de méthodes, ${nb_evenements} d'événements ; membres propres : ${methodes} / ${evenements}

La documentation complete egale le controle vivant
    [Documentation]    Scénario 6 du plan, l'assertion reine : bascule
    ...    « borrowed properties » activée, l'ensemble des noms documentés est
    ...    ÉGAL à l'ensemble des propriétés d'une instance vivante du
    ...    contrôle, MODULO l'inventaire déclaré des propriétés à valeur non
    ...    primitive que la fiche du vivant ne matérialise pas (une entrée,
    ...    `fieldGroupIds`, relevée à la génération : voir les écarts du
    ...    plan ; une tolérance MORTE fait échouer). Chaque ligne ajoutée par
    ...    la bascule porte sa provenance (`borrowedFrom`), aucune ligne
    ...    propre ne la porte. L'état de la case est RELEVÉ avant d'y toucher
    ...    (la case des agrégations est cochée d'origine : rien ne se
    ...    suppose), restauré dans le scénario ET par le teardown.
    Ouvrir La Fiche D Api    sap.m.Button
    Memoriser Les Bascules Borrowed
    ${initial}=    Lire La Bascule Borrowed De La Rubrique    ${DEMOKIT_SECTION_PROPERTIES}
    Should Be Equal    ${initial}    ${False}
    ...    msg=La case borrowed des propriétés est déjà cochée au départ : l'état de référence n'est pas celui attendu.
    ${objets_avant}=    Lire Les Noms Documentes Avec Provenance    ${DEMOKIT_SECTION_PROPERTIES}
    ${nb_avant}=    Get Length    ${objets_avant}
    Basculer Les Borrowed De La Rubrique    ${DEMOKIT_SECTION_PROPERTIES}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Rubrique Doit Compter Plus De    ${DEMOKIT_SECTION_PROPERTIES}    ${nb_avant}
    ${objets}=    Lire Les Noms Documentes Avec Provenance    ${DEMOKIT_SECTION_PROPERTIES}
    ${nb_complet}=    Get Length    ${objets}
    La Provenance Des Lignes Doit Etre Coherente    ${objets_avant}    ${objets}
    ${vivantes}=    Lire Les Proprietes Du Controle Vivant    sap.m.Button
    ${nb_vivantes}=    Get Length    ${vivantes}
    La Doc Complete Doit Egaler Le Controle Vivant    ${objets}    ${vivantes}
    Log    Table passée de ${nb_avant} à ${nb_complet} lignes ; ${nb_vivantes} propriétés sur le contrôle vivant (nombres journalisés, la relation seule est assertée).
    Basculer Les Borrowed De La Rubrique    ${DEMOKIT_SECTION_PROPERTIES}
    La Bascule Borrowed Doit Valoir    ${DEMOKIT_SECTION_PROPERTIES}    ${initial}
    ${nb_retour}=    Compter Les Lignes De La Rubrique    ${DEMOKIT_SECTION_PROPERTIES}
    Should Be Equal As Integers    ${nb_retour}    ${nb_avant}
    ...    msg=La table des propriétés n'est pas revenue à son état relevé : ${nb_retour} ligne(s) contre ${nb_avant}.

Les elements empruntes reconstruisent la chaine d heritage
    [Documentation]    Scénario 7 du plan. Les listes d'éléments empruntés de
    ...    la rubrique des méthodes sont liées aux contextes
    ...    `/borrowed/methods/<n>` dont l'objet nomme l'ANCÊTRE : la chaîne
    ...    d'héritage complète en clés techniques. L'assertion est une
    ...    inclusion (`sap.ui.core.Control`, l'ancêtre définitoire d'un
    ...    contrôle) plus un motif structurel ; l'ordre et la longueur de la
    ...    chaîne suivent le SDK et se journalisent.
    Ouvrir La Fiche D Api    sap.m.Button
    ${ancetres}=    Lire La Chaine D Heritage Documentee    ${DEMOKIT_SECTION_METHODS}
    Les Ancetres Doivent Etre Des Noms Qualifies    ${ancetres}
    La Chaine D Heritage Doit Porter    ${ancetres}    sap.ui.core.Control
    Log    Chaîne d'héritage documentée : ${ancetres}

La galerie d echantillons se lit comme une table et porte ses cles
    [Documentation]    Scénario 8 du plan. La table de la galerie est une
    ...    VRAIE `sap.m.Table` (contrairement aux tables de doc des fiches
    ...    d'API) : la lecture générique et les contextes de liaison sont
    ...    confrontés en un verdict de cohérence. Chaque ligne porte ses clés
    ...    techniques : identifiant d'échantillon préfixé par la bibliothèque,
    ...    `entityId` égal à l'entité de la route, route d'exécution non
    ...    vide. Le nombre d'échantillons est journalisé, jamais gravé.
    Ouvrir La Galerie D Echantillons    sap.m.Button
    ${echantillons}=    Lire Les Echantillons De La Galerie
    Les Echantillons Doivent Porter Leurs Cles    ${echantillons}    sap.m.Button
    ${nb}=    Get Length    ${echantillons}
    Log    ${nb} échantillon(s) dans la galerie (journalisé) ; clés : ${echantillons}

Un echantillon s ouvre et sa vue code expose les fichiers et le source reel
    [Documentation]    Scénario 9 du plan. L'échantillon est ouvert par sa
    ...    LIGNE, dont l'identifiant est découvert à l'exécution, et son
    ...    identifiant technique est LU de la galerie, jamais écrit en dur :
    ...    la campagne survit à l'ajout d'un échantillon. Les fichiers de la
    ...    vue code sont des onglets dont la clé EST le nom de fichier
    ...    (assertions par MOTIFS : une vue, un contrôleur, le manifeste), et
    ...    le source de l'éditeur porte l'identifiant de CET échantillon.
    ...    Téléchargement, ouverture d'onglet et mode adaptation : perçus,
    ...    jamais actionnés.
    Ouvrir La Galerie D Echantillons    sap.m.Button
    ${echantillons}=    Lire Les Echantillons De La Galerie
    ${premier}=    Set Variable    ${echantillons}[0][id]
    Ouvrir L Echantillon Par Sa Ligne    0    ${premier}
    La Barre D Echantillon Doit Etre Percue
    Ouvrir La Vue Du Code Source
    ${fichiers}=    Lister Les Fichiers De L Echantillon
    ${vues}=    Evaluate    [f for f in $fichiers if f.endswith('.view.xml')]
    Should Not Be Empty    ${vues}
    ...    msg=Aucun fichier de vue (.view.xml) parmi les onglets : ${fichiers}
    ${controleurs}=    Evaluate    [f for f in $fichiers if f.endswith('.controller.js')]
    Should Not Be Empty    ${controleurs}
    ...    msg=Aucun fichier de contrôleur (.controller.js) parmi les onglets : ${fichiers}
    List Should Contain Value    ${fichiers}    manifest.json
    ...    msg=Le manifeste manque aux onglets de fichier : ${fichiers}
    ${selectionne}=    Lire Le Fichier Selectionne
    List Should Contain Value    ${fichiers}    ${selectionne}
    ...    msg=Le fichier sélectionné (${selectionne}) n'est pas dans la liste des onglets : ${fichiers}
    Choisir Le Fichier    ${controleurs}[0]
    ${source}=    Lire Le Source De L Editeur
    Le Source Doit Porter L Identifiant    ${source}    ${premier}
    Log    Fichiers de l'échantillon ${premier} : ${fichiers} (noms exacts journalisés).

La navigation suivant precedent traverse les echantillons sans quitter la vue
    [Documentation]    Scénario 10 du plan. Depuis la vue code, « suivant »
    ...    mène à l'échantillon SUIVANT de la galerie sans quitter la vue (le
    ...    fragment se termine toujours par `/code`), « précédent » ramène au
    ...    premier. Les deux identifiants sont LUS de la galerie ; chaque
    ...    geste s'attend sur le FRAGMENT, jamais sur le réseau, et la borne
    ...    `/sample/<id>/` évite qu'un identifiant préfixe d'un autre passe
    ...    pour lui.
    Ouvrir La Galerie D Echantillons    sap.m.Button
    ${echantillons}=    Lire Les Echantillons De La Galerie
    ${nb}=    Get Length    ${echantillons}
    Should Be True    ${nb} >= 2
    ...    msg=La galerie ne porte que ${nb} échantillon(s) : la navigation suivant/précédent n'a pas de cible.
    ${premier}=    Set Variable    ${echantillons}[0][id]
    ${second}=    Set Variable    ${echantillons}[1][id]
    Ouvrir L Echantillon Par Sa Ligne    0    ${premier}
    Ouvrir La Vue Du Code Source
    Passer A L Echantillon Suivant    ${second}
    Revenir A L Echantillon Precedent    ${premier}

Demo Apps et Resources se percoivent sans rien ouvrir
    [Documentation]    Scénario 11 du plan. Les cartes d'applications sont
    ...    comptées dans la zone PRINCIPALE (comptage porté), et chaque lien
    ...    est classé : relatif same-origin (les lancements
    ...    `test-resources/...`, les ancres sans cible) ou externe DÉCLARÉ
    ...    (GitHub) ; un lien hors des deux familles fait échouer en le
    ...    nommant. Aucune application n'est ouverte ; Resources est perçue de
    ...    la même façon.
    Ouvrir La Section    demoapps
    ${cartes}=    Attendre Les Cartes Demo Apps
    ${liens}=    Lister Les Liens Demo Apps
    ${classement}=    Les Liens De Lancement Doivent Etre Locaux    ${liens}
    ${nb_locaux}=    Get Length    ${classement}[locaux]
    ${nb_externes}=    Get Length    ${classement}[externes]
    ${titre_apps}=    Get Title
    Log    Demo Apps : ${cartes} carte(s), ${nb_locaux} lien(s) locaux, ${nb_externes} externe(s) déclaré(s) ; titre journalisé : ${titre_apps}
    Ouvrir La Section    resources
    ${cartes_res}=    Attendre Les Cartes De Resources
    ${titre_res}=    Get Title
    Log    Resources : ${cartes_res} carte(s) ; titre journalisé : ${titre_res}

L iframe d echantillon survit a la navigation
    [Documentation]    Scénario 12 du plan, la sentinelle d'accumulation, et
    ...    il reste le DERNIER : il relit ce que la campagne a produit. Le
    ...    test établit sa propre prémisse (un échantillon visité, puis une
    ...    autre section) : la composition porte ENCORE l'iframe
    ...    d'échantillon, INVISIBLE, le comportement inverse du launchpad
    ...    ABAP qui détruit la sienne : c'est le fait qui justifie toutes les
    ...    lectures portées de cette campagne. Le nombre de contrôles
    ...    accumulés est journalisé, JAMAIS asserté (511 à froid contre 5442
    ...    mesurés après un tour complet), et les anomalies console sont
    ...    CLASSÉES dans les familles déclarées de la cible, jamais comptées.
    Ouvrir La Galerie D Echantillons    sap.m.Button
    ${echantillons}=    Lire Les Echantillons De La Galerie
    Ouvrir L Echantillon Par Sa Ligne    0    ${echantillons}[0][id]
    Ouvrir La Section    resources
    ${composition}=    Percevoir La Composition Courante
    ${frame}=    L Iframe D Echantillon Doit Avoir Survecu    ${composition}
    Log    Iframe survivante : ${frame} ; ${composition}[ui5_controls] contrôle(s) rendus (accumulation journalisée, jamais assertée).
    ${classement}=    Classer Les Anomalies De La Page
    Journaliser Le Diagnostic Du Demo Kit    ${classement}
    Aucune Anomalie Hors Familles Connues    ${classement}
