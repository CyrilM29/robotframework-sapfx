*** Settings ***
Documentation       Navigation et interaction poussée dans le Demo Kit OpenUI5
...                 Spec: specs/openui5-demokit-navigation-interaction.md (sha256:36e01b9bd257, 2026-09-01)
...                 Generated from specs/openui5-demokit-navigation-interaction.md
...                 by sap-generator: re-run the generator rather than
...                 hand-editing locators here.
...
...                 Campagne de **navigation** et d'**interaction avec des
...                 familles de contrôles UI5 distinctes** sur le Demo Kit
...                 public OpenUI5 (`sdk.openui5.org`, application mono-page à
...                 routage par hash, runtime SAPUI5 relevé 1.152.0, dont le
...                 shell est en Web Components depuis cette version) : barre
...                 d'onglets à clés techniques, recherche globale et son
...                 popover de suggestions, lien profond, retour arrière,
...                 arbre de la Référence de l'API filtré puis navigué,
...                 bascule d'affichage réversible, tables de documentation
...                 confrontées au contrôle vivant, cascade de popovers du
...                 menu Options, thème changé et restauré, iframe
...                 d'échantillon étanche, et classement des anomalies.
...
...                 **Navigateur VISIBLE par défaut** (`${DEMOKIT_HEADLESS}`
...                 vaut `False`) : c'est une exigence du plan, cette campagne
...                 est faite pour être regardée pendant qu'elle s'exécute.
...                 Surchargeable en ligne de commande pour une exécution non
...                 surveillée.
...
...                 **LECTURE SEULE** : aucune écriture, aucun formulaire
...                 soumis, aucun bouton de validation de dialogue actionné (le
...                 dialogue des paramètres est ouvert, lu, puis ANNULÉ). Les
...                 deux seuls réglages touchés, le thème et la case
...                 d'affichage, sont relevés au Suite Setup et remis en état
...                 par un teardown qui s'exécute sur toutes les branches,
...                 échec compris : deux exécutions consécutives rendent le
...                 même verdict.
...
...                 Trois interdits que la cible impose, et qui expliquent la
...                 forme des assertions : la LANGUE de l'interface change en
...                 cours de run (mesuré), donc aucun libellé visible n'entre
...                 dans un verdict ; la pile de popups du runtime est le seul
...                 témoin d'ouverture, le popover de cette version n'ayant pas
...                 de propriété d'état ; et les COMPTES bougent d'un passage à
...                 l'autre, donc tout ce qui est asserté est une relation ou
...                 une appartenance, jamais un nombre gravé.
...
...                 Aucun localisateur ici (convention 1) : ils vivent dans
...                 `resources/page_objects/openui5_demokit.resource`.
...
...                 Prérequis : un accès réseau à `sdk.openui5.org`. Aucune
...                 authentification, aucune donnée métier, aucun système SAP.
...                 Exécution ::
...
...                 |  robot --pythonpath src
...                 |  ...   --outputdir results/demokit
...                 |  ...   tests/robot/ui/fiori/navigation_interaction_demokit.robot
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
Le Demo Kit s ouvre en navigateur visible et se laisse percevoir
    [Documentation]    Scénario 1 du plan (réécrit à la ré-exploration du
    ...    2026-09-01). Ce que ce test établit : la cible est une page HYBRIDE
    ...    (runtime UI5 + shell en Web Components depuis le SDK 1.152.0, hôtes
    ...    WC PRÉSENTS), sans frame ni élément WebGUI, le consentement tiers a
    ...    bien été levé (sans quoi son overlay intercepterait les clics de
    ...    toute la campagne), et la page est réellement construite.
    ...
    ...    La version du runtime et la langue servie sont JOURNALISÉES et
    ...    jamais assertées : la première bouge avec le SDK, la seconde a
    ...    changé en cours de run sur cette cible.
    La Banniere De Consentement Doit Avoir Disparu
    ${composition}=    Le Demo Kit Doit Etre Percu
    Journaliser La Langue Servie

Les onglets de navigation portent des cles techniques egales aux routes
    [Documentation]    Scénario 2 du plan. La clé technique d'un onglet est
    ...    exactement la route de hash de sa section : c'est l'ancre
    ...    locale-indépendante de toute la navigation, là où le libellé de
    ...    l'onglet est traduit.
    ...
    ...    Après chaque ouverture, les DEUX témoins sont vérifiés et ils ne se
    ...    remplacent pas : le fragment d'URL dit ce que le routeur a fait, la
    ...    clé sélectionnée du conteneur dit ce que le shell affiche.
    ${cles}=    Lister Les Cles De Navigation
    Log    Clés de navigation découvertes : ${cles}
    FOR    ${attendue}    IN    @{DEMOKIT_EXPECTED_KEYS}
        List Should Contain Value    ${cles}    ${attendue}
        ...    msg=La barre de navigation ne porte plus la section de clé ${attendue} : ${cles}
    END
    Ouvrir La Section    topic
    Ouvrir La Section    api

La recherche globale propose des suggestions et l une d elles navigue
    [Documentation]    Scénario 3 du plan. L'ouverture du popover est constatée
    ...    sur la PILE DE POPUPS du runtime, jamais sur la présence des entrées.
    ...
    ...    Les lignes de catégorie du popover sont traduites, les titres des
    ...    résultats portent des identifiants techniques : c'est sur ces
    ...    derniers, et sur eux seuls, que porte le verdict. Le compte total
    ...    annoncé par le lien de repli dépend de l'index du SDK et n'est pas
    ...    asserté.
    ${popover}=    Rechercher Dans Le Demo Kit    Button
    Attendre Les Suggestions Groupees    ${popover}
    ${groupes}=    Compter Les En Tetes De Groupe    ${popover}
    Should Be True    ${groupes} >= 1
    ...    msg=Le popover de suggestions ne porte aucun en-tête de groupe.
    ${titres}=    Lire Les Suggestions    ${popover}
    Should Be True    ${{ len($titres) }} > ${groupes}
    ...    msg=Le popover ne propose pas plus d'entrées que de catégories : ${titres}
    Les Suggestions Doivent Proposer    ${popover}    sap.m.Button
    Ouvrir La Suggestion De Classe    ${popover}    sap.m.Button

Un deep-link direct restitue l etat sans passer par l accueil
    [Documentation]    Scénario 4 du plan, et son cœur est le deuxième constat :
    ...    la section active vaut la Référence de l'API alors que l'accueil n'a
    ...    JAMAIS été affiché dans cette page, ouverte neuve directement sur
    ...    l'URL profonde.
    ...
    ...    Le fragment est vérifié par appartenance et non mot pour mot :
    ...    l'application réécrit certaines routes.
    Ouvrir Directement La Fiche D Api    sap.m.Input
    L Etat Doit Etre Restitue Depuis Le Lien Profond    sap.m.Input    api
    Fermer Les Pages Supplementaires

Le retour arriere du navigateur remonte le fil de la navigation
    [Documentation]    Scénario 5 du plan. Le témoin d'arrivée est le couple URL
    ...    plus titre du document, sondé : mesuré, le retour arrière n'émet
    ...    aucune requête réseau (les données sont en cache), donc une attente
    ...    de repos rendrait la main immédiatement sans rien prouver, et le
    ...    titre du document est mis à jour APRÈS le fragment.
    Ouvrir La Fiche D Api    sap.m.Table
    Ouvrir La Fiche D Api    sap.m.Button
    Revenir En Arriere Dans Le Demo Kit    sap.m.Table

L arbre lateral se filtre s ancre sur le nom qualifie et navigue
    [Documentation]    Scénario 6 du plan. Trois choses s'y jouent : le filtre
    ...    est DIFFÉRÉ (le comptage lu juste après la frappe vaut encore
    ...    l'ancien, la réduction arrive ensuite), l'ancrage doit être EXACT
    ...    (l'appariement se fait par sous-chaîne, et le nom visé est le
    ...    préfixe d'un autre), et la réversibilité se lit en RELATION, pas en
    ...    retour à la mesure initiale.
    Ouvrir La Fiche D Api    sap.m.Button
    ${avant}=    Compter Les Noeuds De L Arbre D Api
    Should Be True    ${avant} > 0
    ...    msg=L'arbre de la Référence de l'API est vide avant tout filtrage.
    ${filtre}=    Filtrer L Arbre D Api    ObjectPageLayout
    Should Be True    ${filtre} < ${avant}
    ...    msg=Le filtrage n'a pas réduit l'arbre : ${filtre} nœuds contre ${avant}.
    ${cibles}=    Lister Les Cibles De L Arbre D Api
    Les Noeuds Restants Doivent Porter Le Terme    ${cibles}    ObjectPageLayout
    ${ambigus}=    Evaluate    [c for c in $cibles if c.endswith('ObjectPageLayout')]
    Should Be True    ${{ len($ambigus) }} >= 1
    ...    msg=Le nom qualifié visé ne figure pas dans l'arbre filtré : ${cibles}
    Ouvrir Le Noeud D Api    sap.uxap.ObjectPageLayout
    ${elargi}=    Vider Le Filtre D Arbre
    Should Be True    ${elargi} > ${filtre}
    ...    msg=Le vidage du filtre n'a pas élargi l'arbre : ${elargi} nœuds contre ${filtre}.

Une bascule d affichage change l arbre et se remet en etat
    [Documentation]    Scénario 7 du plan. La remise en état se constate sur la
    ...    PROPRIÉTÉ du contrôle et jamais sur le retour du comptage à sa
    ...    valeur initiale : mesuré, ce comptage ne revient pas exactement à
    ...    son point de départ sur un système pourtant parfaitement restauré.
    ...
    ...    Deux verdicts sur le contenu de l'arbre, et le premier vaut dans
    ...    tous les états : inclure les dépréciés n'ENLÈVE jamais un nœud (les
    ...    cibles d'avant sont incluses dans celles d'après). Le second, la
    ...    croissance stricte, dépend de la branche dépliée : le test ouvre
    ...    donc lui-même la fiche dont la branche porte des entités
    ...    dépréciées, au lieu de dépendre de l'état laissé par un test voisin.
    Ouvrir La Fiche D Api    sap.m.Button
    Memoriser Les Bascules D Affichage
    ${initial}=    Lire La Bascule D Affichage    ${DEMOKIT_API_DEPRECATED}
    Should Be Equal    ${initial}    ${False}
    ...    msg=La case des éléments dépréciés est déjà cochée au départ : l'état de référence n'est pas celui attendu.
    ${avant}=    Compter Les Noeuds De L Arbre D Api
    ${cibles_avant}=    Lister Les Cibles De L Arbre D Api
    ${bascule}=    Basculer L Affichage    ${DEMOKIT_API_DEPRECATED}
    Should Be Equal    ${bascule}    ${True}
    ...    msg=La case n'a pas basculé vers l'état coché.
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    L Arbre D Api Doit Compter Plus De    ${avant}
    ${cibles_apres}=    Lister Les Cibles De L Arbre D Api
    ${perdues}=    Evaluate    sorted(set($cibles_avant) - set($cibles_apres))
    Should Be Empty    ${perdues}
    ...    msg=Inclure les éléments dépréciés a fait DISPARAÎTRE des entités de l'arbre : ${perdues}
    Basculer L Affichage    ${DEMOKIT_API_DEPRECATED}
    La Bascule D Affichage Doit Valoir    ${DEMOKIT_API_DEPRECATED}    ${initial}

La table de proprietes se lit par ses en-tetes et s accorde avec le controle vivant
    [Documentation]    Scénario 8 du plan. La table de documentation n'est pas
    ...    une table UI5 standard : ses en-têtes sont une PROPRIÉTÉ et ses
    ...    lignes une AGRÉGATION, et le nom technique d'une ligne vit dans son
    ...    contexte de liaison, pas dans son rendu.
    ...
    ...    L'invariant central est une inclusion, et dans un seul sens : toute
    ...    propriété documentée existe sur le contrôle vivant, l'inverse étant
    ...    faux (le contrôle vivant porte en plus ses propriétés héritées, que
    ...    la documentation range dans ses listes d'éléments empruntés).
    ...
    ...    Les en-têtes sont journalisés et leur STRUCTURE seule est assertée :
    ...    ce sont des chaînes du modèle de documentation, sur lesquelles la
    ...    campagne se refuse à parier comme sur du texte stable (convention 3).
    Ouvrir La Fiche D Api    sap.m.Button
    ${tables}=    Compter Les Tables De Doc De La Rubrique    ${DEMOKIT_SECTION_PROPERTIES}
    Should Be Equal As Integers    ${tables}    1
    ...    msg=La rubrique des propriétés porte ${tables} table(s) de documentation, attendu exactement 1.
    ${entetes}=    Lire Les En Tetes De Table De Doc    ${DEMOKIT_SECTION_PROPERTIES}
    Should Be True    ${{ len($entetes) }} >= 2
    ...    msg=La table des propriétés n'expose pas au moins deux colonnes : ${entetes}
    Log    En-têtes de la table des propriétés : ${entetes}
    ${documentees}=    Lire Les Noms Techniques De Table De Doc    ${DEMOKIT_SECTION_PROPERTIES}
    Should Not Be Empty    ${documentees}
    ...    msg=La table des propriétés ne porte aucune ligne exploitable.
    ${vides}=    Evaluate    [n for n in $documentees if not n]
    Should Be Empty    ${vides}
    ...    msg=Des lignes de la table des propriétés n'exposent aucun nom technique.
    ${vivantes}=    Lire Les Proprietes Du Controle Vivant    sap.m.Button
    La Doc Doit Etre Incluse Dans Le Controle Vivant    ${documentees}    ${vivantes}
    Log    ${{ len($documentees) }} propriétés documentées, incluses dans les ${{ len($vivantes) }} du contrôle vivant.

Le menu Options ouvre une cascade de popovers puis un dialogue annulable
    [Documentation]    Scénario 9 du plan (profondeurs réécrites à la
    ...    ré-exploration du 2026-09-01 : le menu WC pousse DEUX entrées sur la
    ...    pile, la cascade en fait TROIS, voir le plan). Toute ouverture et
    ...    toute fermeture sont constatées sur la PILE DE POPUPS : la présence
    ...    des entrées ne prouve rien, une entrée de menu fermé comptant encore
    ...    une correspondance, avec un rectangle nul, et depuis le shell WC les
    ...    clés lues couvrent le menu ENTIER (les assertions sont des
    ...    inclusions).
    ...
    ...    Le dialogue est ouvert, LU, puis annulé par position : ses boutons
    ...    ont des identifiants générés et des libellés traduits, seul leur
    ...    rôle les distingue. Aucun bouton de validation n'est actionné.
    La Pile De Popups Doit Etre Vide
    ${theme_avant}=    Lire Le Theme Applique
    Ouvrir Le Menu Options
    ${cles}=    Lister Les Cles Du Menu Ouvert
    FOR    ${attendue}    IN    @{DEMOKIT_MENU_KEYS}
        List Should Contain Value    ${cles}    ${attendue}
        ...    msg=Le menu Options ne porte plus l'entrée de clé ${attendue} : ${cles}
    END
    Ouvrir L Entree De Menu    ${DEMOKIT_MENU_APPEARANCE_KEY}
    ${cascade}=    Evaluate    ${DEMOKIT_MENU_STACK_COST} + 1
    Attendre La Profondeur De Pile    ${cascade}
    ${cles_aspect}=    Lister Les Cles Du Menu Ouvert
    FOR    ${attendue}    IN    @{DEMOKIT_APPEARANCE_KEYS}
        List Should Contain Value    ${cles_aspect}    ${attendue}
        ...    msg=Le sous-menu d'aspect ne porte plus l'entrée de clé ${attendue} : ${cles_aspect}
    END
    Fermer Les Popups Ouverts
    Ouvrir Le Menu Options
    Ouvrir L Entree De Menu    ${DEMOKIT_MENU_SETTINGS_KEY}
    Attendre La Profondeur De Pile    ${1}
    ${dialogue}=    Lire Le Dialogue Ouvert
    Should Be Equal    ${dialogue}[id]    ${DEMOKIT_SETTINGS_DIALOG}
    ...    msg=Le dialogue ouvert est ${dialogue}[id], attendu celui des paramètres globaux.
    ${selecteurs}=    Compter Le Selecteur De Langue
    Should Be Equal As Integers    ${selecteurs}    1
    ...    msg=Le dialogue des paramètres ne porte pas exactement un sélecteur de langue (${selecteurs}).
    ${roles}=    Lire Les Roles Des Boutons Du Dialogue
    Should Be Equal    ${roles}    ${DEMOKIT_DIALOG_BUTTON_TYPES}
    ...    msg=Les rôles des boutons du dialogue sont ${roles}, attendus ${DEMOKIT_DIALOG_BUTTON_TYPES}.
    Annuler Le Dialogue Des Parametres
    Le Theme Applique Doit Valoir    ${theme_avant}

Le theme change et revient constate sur le theme applique
    [Documentation]    Scénario 10 du plan. Le thème se lit sur le RUNTIME et
    ...    jamais sur le menu : aucune entrée de thème ne porte la marque du
    ...    thème courant, pas même celle du thème appliqué.
    ...
    ...    Le thème appliqué arrive APRÈS le clic, et il existe une fenêtre où
    ...    le document ne porte aucun thème : d'où une attente active, jamais
    ...    une lecture unique juste après le clic. Le test compare un avant et
    ...    un après, il ne grave pas les noms de thèmes du SDK.
    ${initial}=    Lire Le Theme Applique
    Should Not Be Empty    ${initial}
    ...    msg=Le document ne porte aucun thème appliqué au départ.
    ${cle_initiale}=    Cle De Theme    ${initial}
    Should Not Be Equal    ${cle_initiale}    ${DEMOKIT_ALTERNATE_THEME_KEY}
    ...    msg=Le thème de départ est déjà celui du cycle (${initial}) : le changement ne serait pas observable.
    Choisir Le Theme    ${DEMOKIT_ALTERNATE_THEME_KEY}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Le Theme Applique Ne Doit Plus Valoir    ${initial}
    ${change}=    Lire Le Theme Applique
    Log    Thème appliqué passé de ${initial} à ${change}.
    Choisir Le Theme    ${cle_initiale}
    Le Theme Applique Doit Devenir    ${initial}

L echantillon s execute dans une iframe dont la portee est etanche
    [Documentation]    Scénario 11 du plan. L'iframe de l'échantillon a un id
    ...    STABLE, contrairement aux conteneurs générés d'un launchpad, et son
    ...    runtime UI5 est le sien.
    ...
    ...    L'étanchéité est vérifiée DANS LES DEUX SENS : l'ancre du shell est
    ...    introuvable dans la frame et retrouvée après dépilement. Aucun
    ...    identifiant généré de l'échantillon n'est asserté, les deux espaces
    ...    d'identifiants se recouvrant, seule la portée les séparant.
    Ouvrir L Echantillon    sap.m.sample.Button
    ${frames}=    Lister Les Iframes De La Page
    Length Should Be    ${frames}    1
    ...    msg=La page d'exécution d'un échantillon porte ${{ len($frames) }} iframe(s), attendu exactement 1 : ${frames}
    Should Be Equal    ${frames}[0][id]    ${DEMOKIT_SAMPLE_FRAME_ID}
    ...    msg=L'iframe de l'échantillon n'a plus son identifiant stable : ${frames}[0]
    ${dehors}=    Compter L Ancre Du Shell
    Should Be Equal As Integers    ${dehors}    1
    ...    msg=L'ancre du shell n'est pas résoluble dans le document hôte (${dehors}).
    Entrer Dans L Iframe D Echantillon
    ${composition}=    Percevoir La Composition Courante
    Should Be True    ${composition}[ui5_runtime]
    ...    msg=L'iframe de l'échantillon ne porte pas de runtime UI5 propre.
    Should Be True    ${composition}[ui5_controls] > 0
    ...    msg=L'échantillon n'a construit aucun contrôle dans son iframe.
    ${actionnables}=    Compter Les Controles Actionnables
    Should Be True    ${actionnables} > 0
    ...    msg=L'échantillon n'expose aucun contrôle actionnable dans son iframe.
    ${dedans}=    Compter L Ancre Du Shell
    Should Be Equal As Integers    ${dedans}    0
    ...    msg=L'ancre du shell est résoluble DANS l'iframe (${dedans}) : la portée n'est pas étanche.
    Sortir De L Iframe D Echantillon
    ${retour}=    Compter L Ancre Du Shell
    Should Be Equal As Integers    ${retour}    1
    ...    msg=L'ancre du shell n'est pas revenue après dépilement de la frame (${retour}).

Le diagnostic classe les anomalies au lieu de les compter
    [Documentation]    Scénario 12 du plan, et il doit rester le DERNIER : il
    ...    relit tout ce que la navigation de la campagne a produit.
    ...
    ...    Un comptage serait inexploitable, le nombre d'entrées croissant avec
    ...    chaque fiche ouverte. Le verdict est donc l'appartenance aux trois
    ...    familles déclarées de la cible (tiers hors application, ressources
    ...    statiques absentes du SDK, avertissements du runtime UI5) : une
    ...    entrée hors de ces familles fait échouer en la nommant.
    ${messages}=    Les Messages Ui5 Doivent Etre Vides
    Log    Gestionnaire de messages UI5 : ${messages}
    ${classement}=    Classer Les Anomalies De La Page
    Journaliser Le Diagnostic Du Demo Kit    ${classement}
    Aucune Anomalie Hors Familles Connues    ${classement}
