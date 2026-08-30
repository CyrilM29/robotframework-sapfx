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
...                 Page object de la **résilience de session et des deep-links
...                 du shell d'un launchpad SAP Build Work Zone** (cFLP sur
...                 BTP, derrière un tenant SAP Cloud Identity Services) :
...                 trajet d'authentification, accès direct par intent,
...                 rechargement, historique du navigateur, second onglet,
...                 contextes de navigateur dédiés, cookies de session, délais
...                 déclarés et refus de navigation. Le shell lui-même
...                 (session, catalogue, iframes, retour à l'accueil) vit dans
...                 `workzone_launchpad.resource`, et l'écran porteur d'état
...                 dont l'historique se sert dans
...                 `workzone_shell_search.resource` : ce fichier importe le
...                 second, qui importe le premier.
...
...                 Relevé live le 2026-08-26 (rf-mcp : Browser +
...                 SapFioriLibrary) sur un site Work Zone de trial BTP,
...                 runtime SAPUI5 1.151.0. Spec source :
...                 `specs/workzone-resilience-deeplinks.md`.
...
...                 Contrat de localisation, appris sur la cible réelle :
...
...                 1. **Aucun identifiant de conteneur d'iframe, jamais.**
...                 Cinq valeurs relevées pour la MÊME application dans la même
...                 session (`__container4`, `__container1`, `__container8`,
...                 `__container12`, plus `__container1` dans un onglet neuf) :
...                 le compteur repart de 1 à chaque chargement de document et
...                 grimpe avec les navigations. `Get Ui5 App Frame` désigne
...                 l'iframe par ce qu'elle EST et rend un sélecteur
...                 POSITIONNEL. Les identifiants ne sont lus que pour être
...                 CONSTATÉS variables.
...                 2. **L'hôte tranche, jamais le titre.** La page du
...                 fournisseur d'identité porte le nom du produit du SITE dans
...                 son titre : une page de connexion applicative rendrait un
...                 test « nous sommes bien passés par l'IdP » parfaitement
...                 vert. Le couple hôte plus chemin d'autorisation est la
...                 seule ancre.
...                 3. **Une navigation refusée se referme en deux temps.**
...                 Juste après le clic d'acquittement, le dialogue est encore
...                 listé ouvert ET le fragment porte encore l'intent refusé :
...                 les deux constatations ATTENDENT. Le bouton d'acquittement
...                 est désigné par son TYPE (mis en avant), jamais par sa
...                 position : la position 0 est une action de copie qui laisse
...                 le dialogue ouvert.
...                 4. **Les valeurs de cookies ne sortent jamais d'ici.** Ce
...                 page object ne rend que noms, domaines et caractère
...                 permanent ou non de l'expiration. La bibliothèque Browser
...                 encode une expiration de session en date de 1969 (epoch
...                 moins un) : le prédicat qui a un sens est « expiration
...                 FUTURE », pas « expiration absente ».
...                 5. **Aucun plancher de contrôles n'est gravé.** Relevés du
...                 seul 2026-08-26 : 139 sur un accueil neuf, 84 et 52 sur un
...                 accès direct, 427 sur une page de résultats fraîche, 485
...                 sur la même restaurée par un retour arrière, 844 dans
...                 l'application. Un comptage ne vaut qu'en COMPARAISON de
...                 deux relevés du même test.
...
...                 Portée : LECTURE SEULE côté métier. Deux mots-clés touchent
...                 l'état de session du NAVIGATEUR (vidage de cookies,
...                 contexte supplémentaire) : ils opèrent dans un contexte
...                 DÉDIÉ, jamais dans celui de la suite, et ce contexte est
...                 refermé par le teardown.

Resource            workzone_shell_search.resource


*** Variables ***
# --- Ce que la configuration DÉCLARE de la session ---------------------------
# Chemins RELEVÉS live : ils ne sont pas sous une racine `ushell`, contrairement
# à ce qu'un nom de clé laisse croire. Les trois délais vivent dans la
# configuration du RENDERER, le point de maintien de session dans les propriétés
# système de l'adaptateur de conteneur.
${WORKZONE_SESSION_INTERVAL_PATH}
...                                 renderers.fiori2.componentData.config.sessionTimeoutIntervalInMinutes
${WORKZONE_SESSION_REMINDER_PATH}
...                                 renderers.fiori2.componentData.config.sessionTimeoutReminderInMinutes
${WORKZONE_SESSION_KEEPALIVE_PATH}
...                                 services.Container.adapter.config.systemProperties.sessionKeepAlive

# --- Trajet d'authentification -----------------------------------------------
# Le chemin du point d'autorisation vit déjà dans le page object du shell
# (`${WORKZONE_IDP_URL_MARKER}`) : réutilisé tel quel pour que les deux
# campagnes parlent du MÊME trajet.
${WORKZONE_PASSWORD_FIELD}          input[type="password"]    # sélecteur navigateur : compté, jamais rempli ici

# --- Ancre de la page d'accueil du launchpad ---------------------------------
# Le contrôle décisif du deep-link : son ABSENCE prouve que le shell n'est pas
# passé par l'accueil avant d'ouvrir l'application.
${WORKZONE_DASHBOARD_PAGE}          sapUshellDashboardPage

# --- Navigation refusée -------------------------------------------------------
# Intent FABRIQUÉ, de forme correcte et inconnu du catalogue : la contre-preuve
# sans laquelle un shell qui accepterait tout resterait vert.
${WORKZONE_UNKNOWN_INTENT}          ZzResilienceUnknown-display
${WORKZONE_REFUSAL_STATE}           Error    # état du dialogue de refus, valeur technique
${WORKZONE_DIALOG_BUTTON_TYPE}      sap.m.Button
${WORKZONE_ACKNOWLEDGE_TYPE}        Emphasized    # TYPE du bouton d'acquittement, jamais sa position
${WORKZONE_REFUSAL_BUTTONS}         ${2}    # structure attendue : une copie, un acquittement

# --- Variante longue : accord EXPLICITE, à deux tours ------------------------
# Vide par défaut : sans lui, le scénario d'expiration réelle est SAUTÉ, y
# compris dans un run complet de `tests/robot/`. Un tag seul dépendrait de la
# mémoire de celui qui lance la commande.
${WORKZONE_LONG_OPT_IN}             ${EMPTY}
${WORKZONE_LONG_MARGIN_MINUTES}     ${2}    # marge au-delà de l'intervalle déclaré
${WORKZONE_LONG_POLL}               30s    # sondage par lecture DOM : n'émet aucun événement utilisateur

# --- Budgets d'attente --------------------------------------------------------
# Le retour arrière reconstruit l'écran précédent : la campagne ABAP 2023 a
# mesuré jusqu'à 55 secondes sur un autre couple d'écrans, d'où un budget de
# cible et non une constante enfouie.
${WORKZONE_HISTORY_TIMEOUT}         90s
${WORKZONE_HISTORY_RETRY}           1s
${WORKZONE_JOURNEY_TIMEOUT}         60s
${WORKZONE_JOURNEY_RETRY}           0.5s

# --- Repères de la suite, posés par le Suite Setup ---------------------------
${WORKZONE_SUITE_CONTEXT}           ${EMPTY}
${WORKZONE_SUITE_PAGE}              ${EMPTY}

# L'inventaire des iframes vit dans la bibliothèque (`List Page Iframes`,
# convention #12) ; la seule sonde JS restée ici est le MARQUEUR d'onglet
# (volatile par contrat : un stockage persistant violerait sa documentation),
# assumé dans l'allowlist de check_conventions.py.


*** Keywords ***
# --- Suite Setup / Teardown de la campagne -----------------------------------

Preparer La Campagne Resilience
    [Documentation]    Suite Setup : ouvre la session Work Zone, relève au
    ...    catalogue l'application témoin et le terme qui en dérive, puis
    ...    MÉMORISE le contexte et l'onglet de la suite.
    ...
    ...    Ces deux repères sont la condition de sûreté de toute la campagne :
    ...    deux scénarios ouvrent un contexte supplémentaire et un troisième un
    ...    second onglet ; sans une référence explicite du contexte et de
    ...    l'onglet de la suite, le nettoyage fermerait au hasard et un vidage
    ...    de cookies pourrait atteindre la session de la suite, faisant
    ...    échouer tous les tests suivants pour une raison qui n'est pas la
    ...    leur.
    Ouvrir La Session Work Zone
    Memoriser Une Application Temoin
    Memoriser Le Contexte Et L Onglet De La Suite

Memoriser Le Contexte Et L Onglet De La Suite
    [Documentation]    Publie en variables de suite le contexte de navigateur
    ...    et l'onglet ouverts par le Suite Setup. Exige qu'il n'y en ait
    ...    qu'un de chaque : au-delà, un reliquat d'exécution précédente rendrait
    ...    la référence ambiguë.
    ${contextes}=    Get Context Ids
    Length Should Be    ${contextes}    1
    ...    msg=La session ouverte porte ${{len($contextes)}} contextes de navigateur au lieu d'un : impossible de désigner celui de la suite sans ambiguïté.
    ${pages}=    Get Page Ids
    Length Should Be    ${pages}    1
    ...    msg=Le contexte de la suite porte ${{len($pages)}} onglets au lieu d'un : impossible de désigner celui de la suite sans ambiguïté.
    Set Suite Variable    ${WORKZONE_SUITE_CONTEXT}    ${contextes}[0]
    Set Suite Variable    ${WORKZONE_SUITE_PAGE}    ${pages}[0]

Clore La Campagne Resilience
    [Documentation]    Suite Teardown : referme contextes et onglets
    ...    supplémentaires, ramène le shell à son accueil, puis ferme la
    ...    session. S'exécute MÊME sur échec, c'est ce qui autorise à rejouer
    ...    la campagne sur un site partagé.
    Run Keyword And Ignore Error    Nettoyer Les Contextes Et Onglets Supplementaires
    Run Keyword And Ignore Error    Revenir A L Accueil Du Launchpad
    Fermer La Session Work Zone

Nettoyer Les Contextes Et Onglets Supplementaires
    [Documentation]    Teardown de test : ferme tout contexte de navigateur et
    ...    tout onglet qui ne sont pas ceux mémorisés par le Suite Setup, puis
    ...    ramène la portée active sur eux. Best effort de bout en bout : un
    ...    contexte déjà mort ne doit pas masquer l'échec du test.
    ...
    ...    Le retour explicite sur l'onglet de la suite n'est pas une
    ...    précaution : la fermeture d'un onglet ne réactive pas
    ...    nécessairement celui d'où l'on venait, et le test suivant
    ...    piloterait alors un onglet qu'il n'a pas choisi.
    ${etat}    ${contextes}=    Run Keyword And Ignore Error    Get Context Ids
    IF    '${etat}' == 'PASS'
        FOR    ${contexte}    IN    @{contextes}
            IF    '${contexte}' != '${WORKZONE_SUITE_CONTEXT}'
                Run Keyword And Ignore Error    Close Context    ${contexte}
            END
        END
    END
    Run Keyword And Ignore Error    Switch Context    ${WORKZONE_SUITE_CONTEXT}
    ${etat}    ${pages}=    Run Keyword And Ignore Error    Get Page Ids
    IF    '${etat}' == 'FAIL'    RETURN
    FOR    ${page}    IN    @{pages}
        IF    '${page}' != '${WORKZONE_SUITE_PAGE}'
            Run Keyword And Ignore Error    Close Page    ${page}
        END
    END
    Run Keyword And Ignore Error    Switch Page    ${WORKZONE_SUITE_PAGE}

# --- Le trajet : où suis-je, et suis-je authentifié --------------------------

Lire L Adresse Atteinte
    [Documentation]    Adresse réellement atteinte par le navigateur, décomposée
    ...    en `{hote, chemin, fragment}`. C'est la lecture qui fait foi : mesuré
    ...    live, l'URL rapportée par l'état de session du serveur rf-mcp est en
    ...    retard sur le fragment réel après une navigation par hash.
    ...
    ...    La DÉCOMPOSITION est une capacité de la bibliothèque
    ...    (`Get Page Location`, promue le 2026-08-26 au titre de la
    ...    convention 12 : elle vivait ici en `Evaluate __import__`, que la
    ...    convention proscrit). Ce keyword n'en garde que la traduction vers
    ...    le vocabulaire français de la campagne.
    ${ou}=    Get Page Location
    ${adresse}=    Create Dictionary
    ...    hote=${ou}[host]    chemin=${ou}[path]    fragment=${ou}[fragment]
    RETURN    ${adresse}

Lire L Hote Du Site
    [Documentation]    Hôte du site Work Zone, DÉRIVÉ de la cible passée en
    ...    ligne de commande : aucun nom d'hôte n'est écrit dans le dépôt, et
    ...    la comparaison qui distingue le fournisseur d'identité du site reste
    ...    valable sur n'importe quel tenant.
    ${ou}=    Get Page Location    url=${WORKZONE_SITE}
    RETURN    ${ou}[host]

Compter Les Champs De Mot De Passe
    [Documentation]    Nombre de champs de saisie de mot de passe rendus dans
    ...    la page. Le témoin locale-indépendant de « une authentification est
    ...    demandée » : aucun texte n'est lu, et le titre de la page du
    ...    fournisseur d'identité porte le nom du produit du SITE, donc ne
    ...    distingue rien.
    ${nb}=    Get Element Count    css=${WORKZONE_PASSWORD_FIELD}
    RETURN    ${nb}

Aucun Runtime UI5 N Est Present
    [Documentation]    Assertion : la page atteinte ne porte AUCUN runtime UI5.
    ...    Utilise la sonde pure de la bibliothèque, la seule expression web qui
    ...    n'injecte pas le bundle d'instrumentation : observer une page de
    ...    connexion ne doit rien y modifier.
    ${present}=    Ui5 Runtime Is Present
    Should Not Be True    ${present}
    ...    msg=Un runtime UI5 est chargé alors que la page atteinte devrait être celle du fournisseur d'identité.

Le Trajet De Reauthentification Est Atteint
    [Documentation]    Assertion complète du trajet « session absente » :
    ...    l'hôte atteint DIFFÈRE de celui du site, le chemin est celui du point
    ...    d'autorisation, aucun runtime UI5 n'est chargé et au moins un champ
    ...    de mot de passe est présent.
    ...
    ...    Le contrôle de l'hôte est le seul qui empêche une page de connexion
    ...    servie par le site lui-même de rendre ce test parfaitement vert :
    ...    c'est la leçon du scénario 1 de la campagne de perception, reprise
    ...    ici parce que les trois autres constats sont vrais des deux côtés.
    ${adresse}=    Lire L Adresse Atteinte
    ${site}=    Lire L Hote Du Site
    Should Not Be Equal    ${adresse}[hote]    ${site}
    ...    msg=Le navigateur est resté sur l'hôte du site (${adresse}[hote]) : aucune redirection vers un fournisseur d'identité distinct n'a eu lieu.
    Should Be Equal    ${adresse}[chemin]    ${WORKZONE_IDP_URL_MARKER}
    ...    msg=Le chemin atteint (${adresse}[chemin]) n'est pas le point d'autorisation attendu (${WORKZONE_IDP_URL_MARKER}).
    Aucun Runtime UI5 N Est Present
    ${champs}=    Compter Les Champs De Mot De Passe
    Should Be True    ${champs} > 0
    ...    msg=La page du fournisseur d'identité ne rend aucun champ de mot de passe : le formulaire attendu n'est pas là.
    RETURN    ${adresse}

Attendre Le Trajet De Reauthentification
    [Documentation]    Attend que le trajet « session absente » soit atteint.
    ...    L'attente existe parce qu'une redirection en chaîne rend la main
    ...    avant sa dernière étape : lire l'adresse dans l'instant, c'est
    ...    parfois lire une étape intermédiaire.
    ${adresse}=    Wait Until Keyword Succeeds    ${WORKZONE_JOURNEY_TIMEOUT}    ${WORKZONE_JOURNEY_RETRY}
    ...    Le Trajet De Reauthentification Est Atteint
    RETURN    ${adresse}

# --- Contextes de navigateur dédiés ------------------------------------------

Ouvrir Un Contexte Neuf
    [Documentation]    Ouvre un contexte de navigateur ISOLÉ, sans aucun cookie,
    ...    et retourne son identifiant. Le contexte de la suite n'est pas
    ...    touché : c'est ce cloisonnement qui autorise un scénario à observer
    ...    une session absente pendant qu'une session vivante existe à côté.
    ${contexte}=    New Context
    RETURN    ${contexte}

Ouvrir Le Site Sur Un Intent
    [Documentation]    Ouvre un onglet directement sur le site AVEC un fragment
    ...    d'intent, sans authentification préalable et sans attendre quoi que
    ...    ce soit : le scénario qui appelle ce mot-clé mesure justement ce qui
    ...    se passe AVANT toute frappe. Retourne l'identifiant de l'onglet.
    ...
    ...    L'intent nu suffit : mesuré live, le paramètre d'identification de
    ...    contenu que le catalogue ajoute à sa cible est facultatif.
    [Arguments]    ${intent}
    ${infos}=    New Page    ${WORKZONE_SITE}#${intent}
    ${identifiant}=    Evaluate
    ...    $infos['page_id'] if isinstance($infos, dict) else str($infos)
    RETURN    ${identifiant}

S Authentifier Sur Le Trajet Courant
    [Documentation]    S'authentifie sur le formulaire du fournisseur d'identité
    ...    actuellement affiché, puis rend la main quand le shell a réellement
    ...    construit des contrôles. Le mot de passe n'est jamais journalisé, y
    ...    compris au niveau TRACE.
    Log In Via Identity Provider    ${WORKZONE_USER}    ${WORKZONE_PASSWORD}
    ...    preset=${WORKZONE_IDP_PRESET}
    Le Shell Work Zone Est Rendu

Fermer Le Contexte Dedie
    [Documentation]    Ferme un contexte dédié et ramène la portée active sur
    ...    celui de la suite. Refuse de fermer le contexte de la suite : ce
    ...    garde-fou est la raison d'être du repère posé au Suite Setup.
    [Arguments]    ${contexte}
    Should Not Be Equal    ${contexte}    ${WORKZONE_SUITE_CONTEXT}
    ...    msg=Refus de fermer le contexte de la suite (${contexte}) : un scénario ne ferme que le contexte qu'il a lui-même ouvert.
    Close Context    ${contexte}
    Switch Context    ${WORKZONE_SUITE_CONTEXT}

# --- Cookies : noms, domaines et durées SEULEMENT ----------------------------

Lire Les Cookies De Session
    [Documentation]    Cookies du contexte COURANT, réduits à ce qui peut
    ...    entrer dans un test : une liste triée de `{nom, domaine,
    ...    expiration_future}`. Aucune valeur de cookie n'est retournée ni
    ...    journalisée, ici ni ailleurs.
    ...
    ...    `expiration_future` est le prédicat qui a un sens, et pas
    ...    « expiration absente » : la bibliothèque Browser encode un cookie de
    ...    SESSION par une date de 1969 (epoch moins un), qu'un test naïf
    ...    lirait comme une expiration renseignée donc permanente.
    ${bruts}=    Get Session Cookie Summary
    ${cookies}=    Evaluate
    ...    [{'nom': c['name'], 'domaine': c['domain'], 'expiration_future': c['future_expiration']} for c in $bruts]
    RETURN    ${cookies}

Vider Les Cookies Du Contexte
    [Documentation]    Supprime tous les cookies d'un contexte DÉDIÉ, désigné
    ...    nommément. Appliqué au contexte de la suite, ce geste ferait échouer
    ...    tous les tests suivants pour une raison qui n'est pas la leur : le
    ...    garde-fou est donc explicite plutôt que documentaire, et le contexte
    ...    visé est un argument plutôt que « celui qui se trouve actif ».
    [Arguments]    ${contexte}
    Should Not Be Equal    ${contexte}    ${WORKZONE_SUITE_CONTEXT}
    ...    msg=Refus de vider les cookies du contexte de la suite (${contexte}) : la simulation de perte de session se joue dans un contexte dédié.
    Switch Context    ${contexte}
    Delete All Cookies
    ${restants}=    Get Cookies    dictionary
    Should Be Empty    ${restants}
    ...    msg=${{len($restants)}} cookie(s) survivent au vidage du contexte : la simulation de perte de session ne prouverait rien.

# --- Page d'accueil, iframes et adresses -------------------------------------

La Page D Accueil Est Rendue
    [Documentation]    Vrai quand la page d'accueil du launchpad est construite.
    ...    Prédicat, jamais une assertion : c'est son ABSENCE qui prouve qu'un
    ...    accès direct n'est pas passé par l'accueil, et sans ce contrôle un
    ...    shell qui atterrirait sur l'accueil puis ouvrirait l'application
    ...    produirait exactement le même fragment final.
    ${nb}=    Get Ui5 Match Count    idSuffix=${WORKZONE_DASHBOARD_PAGE}
    RETURN    ${{ $nb > 0 }}

Compter Les Iframes Applicatives
    [Documentation]    Nombre d'iframes rendues dans la portée courante. Sur ce
    ...    shell, une application du site est toujours embarquée : zéro veut
    ...    dire « aucune application ouverte », un veut dire « exactement une ».
    ${iframes}=    Lire Les Iframes Applicatives
    RETURN    ${{ len($iframes) }}

Lire Les Iframes Applicatives
    [Documentation]    Une ligne par iframe rendue : `{id, adresse}`, l'adresse
    ...    amputée de sa query. Sert à CONSTATER la variabilité des
    ...    identifiants et l'identité des adresses, jamais à localiser.
    ${bruts}=    List Page Iframes
    ${iframes}=    Evaluate
    ...    [{'id': f['id'], 'adresse': f['src'].split('?')[0]} for f in $bruts]
    RETURN    ${iframes}

Lire L Identifiant De L Iframe Applicative
    [Documentation]    Identifiant DOM de l'unique iframe applicative. C'est un
    ...    CONSTAT, jamais un localisateur : cinq valeurs ont été relevées pour
    ...    la même application dans la même session. Échoue si le nombre
    ...    d'iframes n'est pas exactement un, plutôt que de rendre la première
    ...    venue.
    ${iframes}=    Lire Les Iframes Applicatives
    Length Should Be    ${iframes}    1
    ...    msg=La portée courante porte ${{len($iframes)}} iframe(s) au lieu d'une : ${iframes}
    RETURN    ${iframes}[0][id]

Lire L Adresse Chargee Dans L Iframe
    [Documentation]    Adresse réellement chargée dans l'unique iframe
    ...    applicative, sans ses paramètres de requête. La comparaison de deux
    ...    ouvertures porte sur CETTE adresse : la query porte des identifiants
    ...    de contenu du site, qui varient d'une voie d'ouverture à l'autre sans
    ...    que l'application change.
    ${iframes}=    Lire Les Iframes Applicatives
    Length Should Be    ${iframes}    1
    ...    msg=La portée courante porte ${{len($iframes)}} iframe(s) au lieu d'une : ${iframes}
    RETURN    ${iframes}[0][adresse]

Le Selecteur De L Iframe Est Positionnel
    [Documentation]    Assertion : le sélecteur que la bibliothèque retient pour
    ...    désigner l'iframe applicative ne contient AUCUN des identifiants
    ...    passés en argument. C'est la propriété à protéger, et c'est
    ...    exactement ce qu'un localisateur écrit à la main perdrait.
    [Arguments]    ${identifiants}
    ${selecteur}=    Get Ui5 App Frame
    FOR    ${identifiant}    IN    @{identifiants}
        Should Not Contain    ${selecteur}    ${identifiant}
        ...    msg=Le sélecteur de l'iframe applicative (${selecteur}) contient l'identifiant généré ${identifiant} : il deviendrait périmé au prochain chargement.
    END
    RETURN    ${selecteur}

# --- Rechargement --------------------------------------------------------------

Recharger Le Launchpad
    [Documentation]    Recharge le document du shell, portée de frame DÉPILÉE au
    ...    préalable : un rechargement effectué portée empilée laisserait la
    ...    portée pointer vers une frame détruite, et l'échec suivant
    ...    accuserait un localisateur.
    ...
    ...    Ne rend la main que sur le document rechargé, sans rien attendre de
    ...    l'application : le scénario qui appelle ce mot-clé mesure justement
    ...    ce qui est vrai AVANT que le shell ait reconstruit quoi que ce soit.
    Sortir De L Application Si Necessaire
    Reload

Attendre La Reconstruction De L Application
    [Documentation]    Après un rechargement ou une navigation, attend dans
    ...    l'ORDRE : le shell rendu, puis l'iframe applicative, puis le
    ...    DÉMARRAGE réel de l'application. Retourne le nombre de contrôles
    ...    qu'elle a construits, portée redescendue sur le shell.
    ...
    ...    Les trois attentes sont distinctes et l'ordre est porteur : le
    ...    rechargement rend la main avant que le shell existe, l'iframe naît
    ...    après le retour du keyword de navigation, et l'application démarre
    ...    après la naissance de l'iframe. Le témoin final est le premier
    ...    contrôle construit DANS la frame, jamais la seule présence de
    ...    l'iframe.
    Le Shell Work Zone Est Rendu
    Entrer Dans L Application
    ${composition}=    Get Page Composition
    Sortir De L Application
    RETURN    ${composition}[ui5_controls]

# --- Historique du navigateur --------------------------------------------------

Lire Le Fragment Courant
    [Documentation]    Fragment complet de l'URL courante, tel quel : c'est le
    ...    seul porteur d'état de navigation de ce shell, donc l'ancre de toute
    ...    assertion d'historique.
    ${adresse}=    Lire L Adresse Atteinte
    RETURN    ${adresse}[fragment]

Lire L Etat Porte Par Le Fragment
    [Documentation]    État applicatif transporté par le fragment de l'écran
    ...    porteur, décodé en valeurs TECHNIQUES : `{source, type_source,
    ...    terme}`. Vérifier seulement l'égalité des fragments laisserait passer
    ...    un écran reconstruit vide, d'où cette lecture de l'état lui-même.
    ${filtre}=    Lire Le Filtre De Recherche
    RETURN    ${filtre}

Preparer L Ecran Porteur D Etat
    [Documentation]    Amène le shell sur un écran qui porte un ÉTAT dans son
    ...    fragment (la page de résultats de recherche), en soumettant le terme
    ...    dérivé de l'application témoin du catalogue. Aucun terme n'est écrit
    ...    dans le test.
    Revenir A L Accueil Du Launchpad
    Lancer La Recherche    ${WORKZONE_TERME_TROUVE}
    Attendre L Etat Avec Resultats

Revenir En Arriere Dans Le Navigateur
    [Documentation]    Navigation arrière du navigateur, suivie du retour au
    ...    repos réel puis de l'attente que l'application ait bien été DÉTRUITE.
    ...    Le budget est un argument parce qu'il dépend de la cible : la
    ...    campagne ABAP 2023 a mesuré jusqu'à 55 secondes de retour au repos
    ...    sur un autre couple d'écrans.
    [Arguments]    ${budget}=${WORKZONE_HISTORY_TIMEOUT}
    Sortir De L Application Si Necessaire
    Go Back
    Wait For Ui5 Idle
    Wait Until Keyword Succeeds    ${budget}    ${WORKZONE_HISTORY_RETRY}
    ...    Aucune Iframe D Application N Est Presente

Avancer Dans Le Navigateur
    [Documentation]    Navigation avant du navigateur, suivie du retour au repos
    ...    réel puis de l'attente de l'iframe applicative. Retourne son
    ...    identifiant, à CONSTATER différent de celui d'avant le retour
    ...    arrière : l'application est reconstruite, pas remise en cache.
    [Arguments]    ${budget}=${WORKZONE_HISTORY_TIMEOUT}
    Go Forward
    Wait For Ui5 Idle
    Wait Until Keyword Succeeds    ${budget}    ${WORKZONE_HISTORY_RETRY}
    ...    Get Ui5 App Frame
    ${identifiant}=    Lire L Identifiant De L Iframe Applicative
    RETURN    ${identifiant}

# --- Second onglet du même contexte ------------------------------------------

Ouvrir Un Second Onglet Sur Le Site
    [Documentation]    Ouvre un SECOND onglet du contexte de la suite, sur le
    ...    site et avec un fragment d'intent. Le contexte étant partagé, ses
    ...    cookies le sont aussi : c'est précisément ce que le scénario
    ...    mesure. Retourne l'identifiant du nouvel onglet.
    [Arguments]    ${intent}
    ${identifiant}=    Ouvrir Le Site Sur Un Intent    ${intent}
    Should Not Be Equal    ${identifiant}    ${WORKZONE_SUITE_PAGE}
    ...    msg=Le second onglet porte l'identifiant de l'onglet de la suite : aucun onglet n'a réellement été ouvert.
    RETURN    ${identifiant}

Revenir Au Premier Onglet
    [Documentation]    Réactive l'onglet mémorisé par le Suite Setup et CONSTATE
    ...    la bascule sur un témoin déposé dans la page, l'URL des deux onglets
    ...    pouvant être identique. Sans cette constatation, un test « le premier
    ...    onglet reste utilisable » pourrait interroger le second.
    Marquer L Onglet Courant    second
    Switch Page    ${WORKZONE_SUITE_PAGE}
    ${marque}=    Lire La Marque De L Onglet Courant
    Should Not Be Equal    ${marque}    second
    ...    msg=La bascule d'onglet n'a pas eu lieu : l'onglet actif porte encore la marque du second.

Marquer L Onglet Courant
    [Documentation]    Dépose dans la page une marque volatile qui distingue les
    ...    onglets. Nécessaire : deux onglets ouverts sur le même deep-link ont
    ...    la même URL, le même fragment et la même structure, donc rien de
    ...    lisible ne les sépare.
    [Arguments]    ${marque}
    Evaluate JavaScript    ${None}    (m) => { window.__marqueOnglet = m; return m; }    arg=${marque}

Lire La Marque De L Onglet Courant
    [Documentation]    Marque déposée dans l'onglet courant, chaîne vide si
    ...    aucune. Lecture seule, volatile, jamais persistée.
    ${marque}=    Evaluate JavaScript    ${None}    () => String(window.__marqueOnglet || '')
    RETURN    ${marque}

Fermer L Onglet
    [Documentation]    Ferme un onglet nommément, puis réactive celui de la
    ...    suite. Refuse de fermer l'onglet de la suite, même garde-fou que
    ...    pour les contextes.
    [Arguments]    ${onglet}
    Should Not Be Equal    ${onglet}    ${WORKZONE_SUITE_PAGE}
    ...    msg=Refus de fermer l'onglet de la suite (${onglet}) : un scénario ne ferme que l'onglet qu'il a lui-même ouvert.
    Close Page    ${onglet}
    Switch Page    ${WORKZONE_SUITE_PAGE}

# --- Délais de session déclarés ----------------------------------------------

Lire Les Delais De Session Declares
    [Documentation]    Ce que la configuration du shell DÉCLARE de sa session :
    ...    `{intervalle, rappel, maintien}`, où l'intervalle est la durée
    ...    d'inactivité avant expiration, le rappel le délai d'avertissement qui
    ...    la précède, et le maintien le point de service qui prolonge la
    ...    session. Trois valeurs techniques, disponibles avant qu'un seul
    ...    contrôle soit construit.
    ...
    ...    Ce sont des réglages de SITE : ils sont journalisés par les
    ...    scénarios, jamais gravés dans une assertion. Seule leur cohérence
    ...    mutuelle est vérifiable partout.
    ${intervalle}=    Get Ushell Config    path=${WORKZONE_SESSION_INTERVAL_PATH}
    ${rappel}=    Get Ushell Config    path=${WORKZONE_SESSION_REMINDER_PATH}
    ${maintien}=    Get Ushell Config    path=${WORKZONE_SESSION_KEEPALIVE_PATH}
    ${delais}=    Create Dictionary    intervalle=${intervalle}    rappel=${rappel}    maintien=${maintien}
    RETURN    ${delais}

Le Point De Maintien Est Sur L Hote Du Site
    [Documentation]    Assertion : le point de service qui prolonge la session
    ...    est servi par l'hôte du SITE. Le contrôle est fait sur l'adresse
    ...    RÉSOLUE contre la cible, donc il vaut aussi bien pour un chemin
    ...    relatif (la forme relevée) que pour une adresse absolue : un shell
    ...    qui déléguerait son maintien de session à un tiers serait une
    ...    information, pas un détail de configuration.
    [Arguments]    ${maintien}
    ${adresse}=    Evaluate    str(($maintien or {}).get('url') or '')
    Should Not Be Empty    ${adresse}
    ...    msg=La configuration ne déclare aucun point de maintien de session : ${maintien}
    ${ou}=    Get Page Location    url=${adresse}    base=${WORKZONE_SITE}
    ${hote_maintien}=    Set Variable    ${ou}[host]
    ${site}=    Lire L Hote Du Site
    Should Be Equal    ${hote_maintien}    ${site}
    ...    msg=Le point de maintien de session est servi par ${hote_maintien} et non par l'hôte du site (${site}).

Calculer L Inactivite Avant Le Premier Signe
    [Documentation]    Durée d'inactivité stricte, en minutes, avant le premier
    ...    signe visible d'expiration : l'intervalle déclaré moins son rappel.
    ...    DÉRIVÉE de la configuration lue sur la cible, jamais écrite : ce sont
    ...    des réglages de site.
    [Arguments]    ${delais}
    ${minutes}=    Evaluate    int($delais['intervalle']) - int($delais['rappel'])
    RETURN    ${minutes}

L Accord Pour Un Scenario Long Est Donne
    [Documentation]    Prédicat d'accord explicite (`yes`/`true`/`1`/`on`).
    ${accorde}=    Evaluate
    ...    str($WORKZONE_LONG_OPT_IN).strip().lower() in ("yes", "true", "1", "on")
    RETURN    ${accorde}

Exiger L Accord Pour Un Scenario Long
    [Documentation]    SAUTE le test tant que l'accord n'a pas été donné en
    ...    ligne de commande. Deux tours, et c'est délibéré : le tag `slow` dit
    ...    ce que le test coûte, la variable dit qu'on l'a voulu. Un tag seul
    ...    dépend de la mémoire de celui qui lance la commande, et une campagne
    ...    qui immobilise la cible un quart d'heure ne doit jamais démarrer par
    ...    surprise.
    ${accorde}=    L Accord Pour Un Scenario Long Est Donne
    IF    not ${accorde}
        Skip    Expiration RÉELLE de session (inactivité stricte de plusieurs minutes) : accord explicite requis (-v WORKZONE_LONG_OPT_IN:yes).
    END

Reinitialiser Le Compte A Rebours D Inactivite
    [Documentation]    Émet une frappe RÉELLE et neutre pour que le compte à
    ...    rebours d'inactivité du shell reparte de zéro à un instant connu.
    ...
    ...    Sans ce geste, la mesure de durée de la variante longue serait
    ...    fausse par construction : le shell raccroche son compte à rebours aux
    ...    événements de souris et de clavier, or les navigations et les
    ...    perceptions de la campagne n'en émettent aucun. Le repère de départ
    ...    serait alors postérieur de plusieurs minutes au vrai départ, et
    ...    l'assertion « le signe n'arrive pas avant l'inactivité déclarée »
    ...    deviendrait un faux rouge.
    Keyboard Key    press    Escape

Le Shell A Signale L Expiration
    [Documentation]    Prédicat de fin d'attente de la variante longue : le shell
    ...    a réagi à l'inactivité, soit en ouvrant un popup (le rappel
    ...    d'expiration), soit en cessant de servir le launchpad (plus aucun
    ...    runtime UI5 sur la page atteinte). Retourne `{signe, adresse,
    ...    popups}`.
    ...
    ...    Les deux branches sont acceptées à dessein : ce qui est éprouvé, c'est
    ...    que le shell RÉAGIT à l'inactivité déclarée, pas la forme de sa
    ...    réaction, qui dépend du site.
    ...
    ...    La seconde branche est délibérément formulée sur l'ABSENCE de runtime
    ...    et non sur un trajet précis. Mesuré live le 2026-08-26 : l'expiration
    ...    réelle ne repasse PAS par le fournisseur d'identité comme le fait la
    ...    perte de session simulée, elle navigue vers une page de déconnexion
    ...    servie par l'hôte du SITE. Un prédicat écrit sur le trajet de
    ...    réauthentification aurait donc attendu en vain devant une session
    ...    parfaitement expirée.
    ${etat}    ${popups}=    Run Keyword And Ignore Error    Get Ui5 Open Popups
    IF    '${etat}' == 'PASS' and len($popups) > 0
        ${verdict}=    Create Dictionary    signe=rappel    adresse=${{ {} }}    popups=${popups}
        RETURN    ${verdict}
    END
    ${runtime}=    Ui5 Runtime Is Present
    Should Not Be True    ${runtime}
    ...    msg=Aucun signe d'expiration : le launchpad est toujours servi (runtime UI5 présent) et aucun popup n'est ouvert.
    ${adresse}=    Lire L Adresse Atteinte
    ${verdict}=    Create Dictionary    signe=session_perdue    adresse=${adresse}    popups=${{ [] }}
    RETURN    ${verdict}

Attendre Le Signe D Expiration De Session
    [Documentation]    Attend, en INACTIVITÉ STRICTE, que le shell signale
    ...    l'expiration. Le budget dérive de l'intervalle déclaré par la cible,
    ...    augmenté d'une marge.
    ...
    ...    Le sondage ne relance pas le compte à rebours : il lit le registre de
    ...    contrôles et l'URL par évaluation de script, sans jamais émettre de
    ...    mouvement de souris ni de frappe, seuls événements auxquels le shell
    ...    raccroche son maintien de session. C'est ce qui rend l'attente
    ...    observable sans `Sleep` (convention 2).
    [Arguments]    ${delais}
    ${budget}=    Evaluate    int($delais['intervalle']) + int($WORKZONE_LONG_MARGIN_MINUTES)
    ${verdict}=    Wait Until Keyword Succeeds    ${budget} minutes    ${WORKZONE_LONG_POLL}
    ...    Le Shell A Signale L Expiration
    RETURN    ${verdict}

# --- Navigation refusée --------------------------------------------------------

Demander Un Intent Inconnu
    [Documentation]    Demande au shell la navigation vers un intent FABRIQUÉ,
    ...    de forme correcte et absent du catalogue, puis attend que le shell
    ...    ait rendu son verdict. Ne présume rien de ce verdict : c'est le
    ...    scénario qui le lit.
    Open Fiori App    ${WORKZONE_UNKNOWN_INTENT}
    Wait Until Keyword Succeeds    ${WORKZONE_JOURNEY_TIMEOUT}    ${WORKZONE_JOURNEY_RETRY}
    ...    Un Dialogue De Refus Est Ouvert

Un Dialogue De Refus Est Ouvert
    [Documentation]    Prédicat : un dialogue en état d'erreur figure parmi les
    ...    popups OUVERTS. Retourne son entrée de popup. Filtré par `kind` et
    ...    `state`, jamais par identifiant : celui du dialogue est GÉNÉRÉ, et il
    ...    est réutilisé d'un refus à l'autre.
    ${popups}=    Get Ui5 Open Popups
    ${cibles}=    Evaluate
    ...    [p for p in $popups if p['kind'] == 'dialog' and p['state'] == $WORKZONE_REFUSAL_STATE]
    Should Not Be Empty    ${cibles}
    ...    msg=Aucun dialogue en état ${WORKZONE_REFUSAL_STATE} n'est ouvert. Popups réellement ouverts : ${popups}
    RETURN    ${cibles}[0]

Le Shell Refuse La Navigation
    [Documentation]    Constate la structure du refus : un dialogue en état
    ...    d'erreur, portant exactement deux boutons, dont le DERNIER est de
    ...    type mis en avant. Retourne `{dialogue, types}`.
    ...
    ...    La structure est vérifiée avant d'agir parce que l'acquittement se
    ...    fait par type : sur un shell qui changerait l'ordre ou le nombre des
    ...    actions, mieux vaut un échec qui nomme la structure qu'un clic sur la
    ...    mauvaise.
    ${dialogue}=    Un Dialogue De Refus Est Ouvert
    ${types}=    Get Ui5 Properties    type    controlType=${WORKZONE_DIALOG_BUTTON_TYPE}
    ...    containedIn=${dialogue}[id]
    Length Should Be    ${types}    ${WORKZONE_REFUSAL_BUTTONS}
    ...    msg=Le dialogue de refus porte ${{len($types)}} bouton(s) au lieu de ${WORKZONE_REFUSAL_BUTTONS} : ${types}
    Should Be Equal    ${types}[-1]    ${WORKZONE_ACKNOWLEDGE_TYPE}
    ...    msg=Le dernier bouton du dialogue de refus n'est pas celui mis en avant (${types}) : acquitter par position copierait le message technique et laisserait le dialogue ouvert.
    ${refus}=    Create Dictionary    dialogue=${dialogue}    types=${types}
    RETURN    ${refus}

Acquitter Le Refus De Navigation
    [Documentation]    Acquitte le dialogue de refus par le bouton de type mis
    ...    en avant, puis attend que la fermeture soit RÉELLE : le fragment
    ...    restauré et plus aucun popup ouvert.
    ...
    ...    Les deux attentes ne sont pas des précautions. Mesuré live, juste
    ...    après le clic le dialogue est encore listé ouvert ET le fragment
    ...    porte encore l'intent refusé : lire dans l'instant, c'est conclure
    ...    que la navigation a eu lieu sur un shell parfaitement sain.
    [Arguments]    ${dialogue}    ${fragment_attendu}
    Click Ui5 Control    controlType=${WORKZONE_DIALOG_BUTTON_TYPE}
    ...    properties={'type': '${WORKZONE_ACKNOWLEDGE_TYPE}'}    containedIn=${dialogue}[id]
    Wait Until Keyword Succeeds    ${WORKZONE_JOURNEY_TIMEOUT}    ${WORKZONE_JOURNEY_RETRY}
    ...    Le Fragment Courant Est    ${fragment_attendu}
    Attendre Qu Aucun Popup Ne Soit Ouvert

Le Fragment Courant Est
    [Documentation]    Prédicat d'égalité du fragment courant, pour les attentes.
    [Arguments]    ${attendu}
    ${fragment}=    Lire Le Fragment Courant
    Should Be Equal    ${fragment}    ${attendu}
    ...    msg=Le fragment courant est « ${fragment} » au lieu de « ${attendu} ».

Aucun Popup N Est Ouvert
    [Documentation]    Prédicat : plus aucun popup OUVERT (dialogues UI5 et
    ...    popovers Web Components confondus). Un dialogue fermé peut rester
    ...    RENDU : seule la liste des popups ouverts tranche.
    ${popups}=    Get Ui5 Open Popups
    Should Be Empty    ${popups}
    ...    msg=Des popups sont encore ouverts : ${popups}

Attendre Qu Aucun Popup Ne Soit Ouvert
    [Documentation]    Attend la fermeture réelle des popups : les fermetures
    ...    sont animées, une lecture immédiate échouerait sur un dialogue en
    ...    train de se fermer proprement.
    [Arguments]    ${budget}=${WORKZONE_JOURNEY_TIMEOUT}
    Wait Until Keyword Succeeds    ${budget}    ${WORKZONE_JOURNEY_RETRY}
    ...    Aucun Popup N Est Ouvert

Fermer Tout Popup Restant
    [Documentation]    Teardown de test best effort : referme par échappement
    ...    les popups qu'un échec aurait laissés ouverts, pour que le test
    ...    suivant ne paie pas l'état du précédent. Journalise ce qui résiste,
    ...    ne fait jamais échouer le teardown (la page peut être morte).
    ${etat}    ${popups}=    Run Keyword And Ignore Error    Get Ui5 Open Popups
    IF    '${etat}' == 'FAIL'    RETURN
    WHILE    len($popups) > 0    limit=5    on_limit=pass
        Keyboard Key    press    Escape
        ${referme}=    Run Keyword And Return Status
        ...    Attendre Qu Aucun Popup Ne Soit Ouvert    budget=10s
        IF    ${referme}    RETURN
        ${etat}    ${popups}=    Run Keyword And Ignore Error    Get Ui5 Open Popups
        IF    '${etat}' == 'FAIL'    RETURN
    END
    IF    len($popups) > 0
        Log    Des popups résistent au nettoyage par échappement : ${popups}    WARN
    END
