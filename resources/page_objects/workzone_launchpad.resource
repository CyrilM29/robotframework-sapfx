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
...                 Page object du **shell d'un launchpad SAP Build Work Zone**
...                 (cFLP hébergé sur SAP BTP, derrière un tenant SAP Cloud
...                 Identity Services). Le shell seulement : ce qui vit dans
...                 l'iframe de l'application appartient au page object de
...                 cette application.
...
...                 Relevé live le 2026-08-24 (rf-mcp : Browser +
...                 SapFioriLibrary) sur un site Work Zone de trial BTP,
...                 runtime SAPUI5 1.151.0.
...
...                 Contrat de localisation, trois règles apprises sur la
...                 cible réelle :
...
...                 1. **Aucun identifiant de conteneur UI5 en dur.** L'iframe
...                 de l'application porte un id GÉNÉRÉ dont le compteur bouge
...                 d'une exécution à l'autre (`__container1`, `__container4`,
...                 `__container3` relevés sur trois runs de la même
...                 application, `__container4` de nouveau le 2026-08-24) :
...                 `Get Ui5 App Frame` la désigne par ce qu'elle EST.
...                 2. **Le préfixe de composant du shell est généré lui
...                 aussi** (`__component0---ShellBarView--…`) : l'ancre est le
...                 SUFFIXE d'id (`idSuffix`), jamais l'id complet.
...                 3. **La barre shell n'est plus du UI5 classique** : c'est
...                 un jeu d'UI5 Web Components à tags SCOPÉS
...                 (`ui5-shellbar-6bfd01e3`, `ui5-button-6bfd01e3`), donc du
...                 ressort du moteur `wc`.
...
...                 Contrat d'assertion : tout ce que ces mots-clés retournent
...                 est locale-indépendant (nombres, ids techniques, intents,
...                 types de contrôles). Le shell rend ses libellés dans la
...                 langue du navigateur.

# `fiori_keywords.resource` porte déjà les imports `Browser` et
# `SapFioriLibrary` : les redéclarer ici les ferait diverger en arguments, et
# Robot ignorerait le second import avec un avertissement.
Resource            ../fiori_keywords.resource
Library             Collections
Library             String
# Primitive pure atteinte par un KEYWORD (décision DDIC 2026-08-17) :
# `Secret Is Provided` teste la PRÉSENCE d'un identifiant sans jamais le lire.
Library             sapfx_common.secrets


*** Variables ***
# --- Cible et identité : jamais de valeur committée (convention 11) ----------
# Le site est une URL privée, l'utilisateur une identité réelle et le mot de
# passe un secret : les trois entrent par la ligne de commande.
${WORKZONE_SITE}                    ${EMPTY}
${WORKZONE_USER}                    ${EMPTY}
${WORKZONE_PASSWORD}                ${EMPTY}
${WORKZONE_IDP_PRESET}              sap-ias
${WORKZONE_HEADLESS}                ${True}
# Relevée par `Ouvrir La Session Work Zone`, avant toute frappe : elle n'existe
# qu'à cet instant de la session.
${WORKZONE_URL_AVANT_AUTHENTIFICATION}    ${EMPTY}

# --- Localisateurs du shell, relevés live (2026-08-24) ----------------------
${WORKZONE_HOME_INTENT}             Shell-home    # l'accueil du launchpad est un intent comme un autre
${WORKZONE_SEARCH_FIELD}            ShellBarView--shellBarSearchInput    # idSuffix : le préfixe __component0 est généré
${WORKZONE_TILE_CONTROL}            sap.m.GenericTile    # la tuile d'une application sur l'accueil
${WORKZONE_SHELLBAR_WC_TAG}         ShellBar    # type court du moteur wc, voir la note ci-dessous
${WORKZONE_IDP_URL_MARKER}          /oauth2/authorize    # point d'autorisation du tenant IAS
${WORKZONE_APP_FRAME_PATTERN}       iframe >> nth=    # forme POSITIONNELLE rendue par `Get Ui5 App Frame`
${WORKZONE_NO_APP_ERROR}            *Aucune iframe d'application*    # échec attendu quand rien n'est ouvert

# Le tag réel de la barre shell est `ui5-shellbar`, en UN mot, avec en plus le
# suffixe de scoping de l'application. Le type court `ShellBar` ne matchait rien
# avant le correctif du 2026-08-24 (il devenait `shell-bar`, donc un tag jugé
# COMPLET, jamais préfixé par `ui5-`) : c'est cette campagne qui l'a révélé, et
# le moteur essaie désormais les deux orthographes qu'emploie UI5 Web Components.
# Reste vrai après correctif : la correspondance se fait par PRÉFIXE, donc ce
# comptage inclut les sous-composants (`ui5-shellbar-branding`,
# `ui5-shellbar-item`). Il vaut comme preuve de PRÉSENCE, jamais comme
# cardinalité d'un composant précis.

# --- Perception du catalogue : services du shell, pas DOM --------------------
# `SearchableContent` est le service ushell qui rend les applications RÉELLEMENT
# accessibles à l'utilisateur connecté, avec leur intent de navigation. Lire le
# catalogue par ce service plutôt que par les tuiles rendues distingue « ce que
# l'utilisateur a le droit d'ouvrir » de « ce que cette page affiche ». La
# lecture vit dans la bibliothèque (`List Flp Apps`, convention #12) : ce
# fichier n'en garde que la traduction en vocabulaire français.

# Signature d'une dépréciation émise par le shell lui-même : UI5 les journalise
# en niveau `error`, ce qui rend tout comptage brut d'erreurs console inutile.
${WORKZONE_DEPRECATION_MARKER}      [FUTURE FATAL]


*** Keywords ***
La Cible Et Les Identifiants Sont Fournis
    [Documentation]    Garde de prérequis, à appeler avant d'ouvrir quoi que ce
    ...    soit : sans elle, l'absence de cible se manifeste bien plus loin,
    ...    par un échec de navigation qui accuse le réseau.
    ...
    ...    Le mot de passe n'est JAMAIS mesuré : un type `Secret` refuse d'être
    ...    lu (« Could not get length of '<secret>' ») et l'erreur de garde
    ...    masquerait le vrai prérequis manquant.
    Should Not Be Empty    ${WORKZONE_SITE}
    ...    msg=Cible absente : passer -v WORKZONE_SITE:<url du site Work Zone>.
    Should Not Be Empty    ${WORKZONE_USER}
    ...    msg=Utilisateur absent : passer -v WORKZONE_USER:<utilisateur du tenant>.
    ${fourni}=    Secret Is Provided    ${WORKZONE_PASSWORD}
    Should Be True    ${fourni}
    ...    msg=Mot de passe absent : passer -v "WORKZONE_PASSWORD: Secret:<motdepasse>".

Ouvrir La Session Work Zone
    [Documentation]    Suite Setup : ouvre le navigateur sur le site, laisse la
    ...    redirection vers le fournisseur d'identité se produire, RELÈVE l'URL
    ...    atteinte avant toute frappe, s'authentifie, puis rend la main
    ...    seulement quand le shell a réellement construit des contrôles.
    ...
    ...    L'URL d'avant authentification est relevée ici parce qu'elle n'existe
    ...    qu'à cet instant : une fois connecté, plus aucun test ne peut
    ...    l'observer sans se déconnecter. Elle est publiée en variable de suite
    ...    `${WORKZONE_URL_AVANT_AUTHENTIFICATION}`.
    ...
    ...    La page est ouverte au niveau SUITE : l'auto-fermeture de la
    ...    bibliothèque Browser est au niveau TEST, une page ouverte pendant un
    ...    test disparaît à sa fin et les suivants échouent sur « No page open ».
    La Cible Et Les Identifiants Sont Fournis
    New Browser    ${BROWSER}    headless=${WORKZONE_HEADLESS}
    New Page    ${WORKZONE_SITE}
    ${url_idp}=    Get Url
    Set Suite Variable    ${WORKZONE_URL_AVANT_AUTHENTIFICATION}    ${url_idp}
    Log In Via Identity Provider    ${WORKZONE_USER}    ${WORKZONE_PASSWORD}
    ...    preset=${WORKZONE_IDP_PRESET}
    Le Shell Work Zone Est Rendu

Fermer La Session Work Zone
    [Documentation]    Suite Teardown : ferme le navigateur, donc la session
    ...    applicative avec lui.
    Close Fiori

Le Shell Work Zone Est Rendu
    [Documentation]    Sonde jusqu'à ce que le shell ait construit des
    ...    contrôles, et pas seulement chargé son runtime.
    ...
    ...    Mesuré live : sur un cFLP, `Wait For UI5 Ready` peut être satisfait
    ...    alors que le shell n'a construit AUCUN contrôle (runtime chargé, rien
    ...    de busy, page vide). Une fixture rend tout d'un coup et ne montre
    ...    jamais cet état intermédiaire, d'où l'attente explicite ici.
    Wait For UI5 Ready
    Wait For Ui5 Idle
    Wait Until Keyword Succeeds    60s    2s    Le Shell Porte Des Controles

Le Shell Porte Des Controles
    [Documentation]    Prédicat de `Le Shell Work Zone Est Rendu` : la
    ...    composition perçue annonce au moins un contrôle UI5 construit.
    ${composition}=    Get Page Composition
    Should Be True    ${composition}[ui5_controls] > 0
    ...    msg=Aucun contrôle UI5 rendu : le shell du launchpad n'est pas là.

Lire La Composition De La Portee Courante
    [Documentation]    Composition perçue de la portée courante : la page du
    ...    shell, ou l'intérieur de l'iframe applicative si elle est empilée.
    ...    Retourne le dict JSON-safe de `Get Page Composition`.
    ${composition}=    Get Page Composition
    RETURN    ${composition}

Compter Les Hotes Web Components De La Barre Shell
    [Documentation]    Nombre d'hôtes Web Components de la barre shell vus par
    ...    le moteur `wc`. Voir le piège du type court documenté en tête de
    ...    fichier : le comptage prouve la PRÉSENCE de la barre en Web
    ...    Components, il ne compte pas un composant précis.
    ${nb}=    Get Wc Match Count    tag=${WORKZONE_SHELLBAR_WC_TAG}
    RETURN    ${nb}

Compter Les Hotes Web Components En Surface
    [Documentation]    Nombre d'hôtes Web Components du light DOM de la portée
    ...    courante, lu à la composition perçue. Relevé live (2026-08-26) : 6
    ...    sur l'accueil du shell, là où le comptage PROFOND en voit 16 : la
    ...    différence mesure ce que le shell imbrique dans des shadow roots.
    ${composition}=    Get Page Composition
    RETURN    ${composition}[wc_hosts_light]

Compter Les Hotes Web Components En Profondeur
    [Documentation]    Nombre d'hôtes Web Components de la portée courante en
    ...    TRAVERSANT les shadow roots ouverts (le champ `wc_hosts` de la
    ...    composition). Strictement supérieur au comptage de surface sur un
    ...    shell Work Zone : le bouton de recherche, entre autres, vit dans le
    ...    shadow root du `ui5-shellbar`.
    ${composition}=    Get Page Composition
    RETURN    ${composition}[wc_hosts]

Compter Le Champ De Recherche Du Shell
    [Documentation]    Nombre de champs de recherche du shell résolus dans la
    ...    portée COURANTE. Sert de témoin d'étanchéité de la portée de frame :
    ...    1 sur le shell, 0 depuis l'intérieur d'une application.
    ${nb}=    Get Ui5 Match Count    idSuffix=${WORKZONE_SEARCH_FIELD}
    RETURN    ${nb}

Compter Les Tuiles De L Accueil
    [Documentation]    Nombre de tuiles d'application rendues sur l'accueil.
    ${nb}=    Get Ui5 Match Count    controlType=${WORKZONE_TILE_CONTROL}
    RETURN    ${nb}

Inventorier Les Applications Du Catalogue
    [Documentation]    Inventaire des applications réellement accessibles à
    ...    l'utilisateur connecté, lu au service `SearchableContent` du shell :
    ...    une liste de dicts `{titre, intent, cible}`, l'`intent` étant la
    ...    forme `SemanticObject-action` sans ses paramètres.
    ...
    ...    Source de vérité choisie à dessein : le service dit ce que
    ...    l'utilisateur a le DROIT d'ouvrir, là où un balayage des tuiles ne
    ...    dirait que ce que cette page affiche aujourd'hui. Lecture par le
    ...    keyword de bibliothèque `List Flp Apps` (convention #12).
    ${bruts}=    List Flp Apps
    ${apps}=    Create List
    FOR    ${app}    IN    @{bruts}
        ${entree}=    Create Dictionary    titre=${app}[title]
        ...    intent=${app}[intent]    cible=${app}[target_url]
        Append To List    ${apps}    ${entree}
    END
    RETURN    ${apps}

Ouvrir L Application Par Intent
    [Documentation]    Navigue vers une application par son intent (le hash
    ...    stable, indépendant du catalogue, du thème et de la langue) et rend
    ...    la main quand son iframe est là.
    [Arguments]    ${intent}
    Open App By Intent    ${intent}
    Attendre L Iframe De L Application

Ouvrir L Application Par Sa Tuile
    [Documentation]    Ouvre une application comme le ferait l'utilisateur, en
    ...    cliquant sa tuile par son titre. La voie « intent » reste la voie
    ...    stable ; celle-ci vérifie que les deux mènent au même endroit.
    [Arguments]    ${titre}
    Open App    ${titre}
    Attendre L Iframe De L Application

Attendre L Iframe De L Application
    [Documentation]    Sonde jusqu'à ce que l'iframe applicative existe.
    ...    Nécessaire : mesuré live, l'iframe est créée APRÈS le retour du
    ...    keyword de navigation, donc une perception immédiate ne voit que le
    ...    shell et rapporte `frames: []`.
    Wait Until Keyword Succeeds    60s    1s    Get Ui5 App Frame

Entrer Dans L Application
    [Documentation]    Empile l'iframe de l'application, attend qu'elle ait
    ...    DÉMARRÉ, et retourne le sélecteur empilé. À partir de là, toute
    ...    résolution UI5 se fait DANS l'application.
    ...
    ...    L'attente n'est pas une précaution : mesuré live le 2026-08-24,
    ...    l'iframe existe et sa portée est déjà utilisable alors que
    ...    l'application n'a construit AUCUN contrôle. Une perception immédiate
    ...    rapporte donc `ui5_controls: 0`, ce qui se lit comme « application
    ...    vide » alors qu'il s'agit d'un démarrage encore en cours. Le pilotage
    ...    interactif ne voyait jamais le problème : chaque tour d'agent laisse
    ...    passer des secondes.
    ...
    ...    Suppose une application UI5 : pour une application embarquée qui n'en
    ...    est pas une (moteurs wc, sid ou dom), empiler la frame avec
    ...    `Push Ui5 App Frame` et attendre son propre témoin de rendu.
    Attendre L Iframe De L Application
    ${selecteur}=    Push Ui5 App Frame
    Wait Until Keyword Succeeds    60s    2s    L Application A Construit Ses Controles
    Wait For Ui5 Idle
    RETURN    ${selecteur}

L Application A Construit Ses Controles
    [Documentation]    Prédicat de démarrage de l'application embarquée : son
    ...    runtime UI5 a construit au moins un contrôle dans la frame.
    ${composition}=    Get Page Composition
    Should Be True    ${composition}[ui5_controls] > 0
    ...    msg=L'application ouverte n'a encore construit aucun contrôle.

Sortir De L Application
    [Documentation]    Dépile la frame applicative et revient au shell.
    ${selecteur}=    Pop Ui5 Frame
    RETURN    ${selecteur}

Sortir De L Application Si Necessaire
    [Documentation]    Teardown de test : ramène la portée au shell quel que
    ...    soit l'endroit où un échec a laissé la pile de frames. Sans cela, un
    ...    test qui échoue à l'intérieur de l'application laisse la portée
    ...    empilée et fait échouer les suivants pour une raison qui n'est pas
    ...    la leur.
    ${pile}=    Get Ui5 Frame Stack
    WHILE    len($pile) > 0    limit=5
        Pop Ui5 Frame
        ${pile}=    Get Ui5 Frame Stack
    END

Revenir A L Accueil Du Launchpad
    [Documentation]    Retour à l'accueil du shell par son intent, puis attente
    ...    du repos réel : l'iframe applicative est détruite au passage.
    Sortir De L Application Si Necessaire
    Open App By Intent    ${WORKZONE_HOME_INTENT}
    Wait For Ui5 Idle
    Wait Until Keyword Succeeds    30s    1s    Aucune Iframe D Application N Est Presente

Aucune Iframe D Application N Est Presente
    [Documentation]    Vérifie qu'aucune application n'est ouverte, en
    ...    s'appuyant sur l'échec ACTIONNABLE de `Get Ui5 App Frame` : il nomme
    ...    ce qu'il a trouvé et le remède, là où un « sélecteur introuvable »
    ...    n'apprendrait rien.
    Run Keyword And Expect Error    ${WORKZONE_NO_APP_ERROR}    Get Ui5 App Frame

Lire Les Identifiants D Iframe
    [Documentation]    Identifiants DOM des iframes actuellement présentes dans
    ...    le shell. Sert à CONSTATER que l'identifiant est généré, jamais à
    ...    s'en servir comme localisateur.
    ...
    ...    La lecture est FORCÉE à la portée du shell, puis la pile de frames
    ...    est restaurée sur tous les chemins. `List Page Iframes` respecte la
    ...    pile, comme tout keyword de la bibliothèque : appelé depuis
    ...    l'intérieur de l'application, il inventorierait les iframes de
    ...    CELLE-CI, qui n'en imbrique aucune, et rendrait une liste vide.
    ...
    ...    Le piège est que la sonde inline d'avant (`Evaluate JavaScript` au
    ...    sélecteur `${None}`) s'évaluait sur la page quelle que soit la
    ...    portée, sans le dire : les appelants en dépendaient sans le savoir.
    ...    Relevé live le 2026-08-29, scénario 5 de la campagne Work Zone.
    ${pile}=    Get Ui5 Frame Stack
    TRY
        Set Ui5 Frame    ${EMPTY}
        ${iframes}=    List Page Iframes
    FINALLY
        Restaurer La Portee De Frame    ${pile}
    END
    ${ids}=    Evaluate    [f['id'] for f in $iframes]
    RETURN    ${ids}

Restaurer La Portee De Frame
    [Documentation]    Remet la pile de frames dans l'état relevé. Une portée
    ...    laissée sur le shell ferait échouer la suite du scénario sur des
    ...    contrôles pourtant présents, et le diagnostic porterait alors sur le
    ...    mauvais symptôme.
    [Arguments]    ${pile}
    Set Ui5 Frame    ${EMPTY}
    FOR    ${frame}    IN    @{pile}
        Push Ui5 Frame    ${frame}
    END

Classer Les Erreurs De La Page Du Shell
    [Documentation]    Trie ce que la console du shell a émis, parce qu'un
    ...    comptage brut ne veut rien dire ici : UI5 journalise ses propres
    ...    dépréciations en niveau `error`, et le shell d'un Work Zone à jour en
    ...    émet des dizaines (`[FUTURE FATAL] … is deprecated`) sans qu'aucune
    ...    application soit en cause.
    ...
    ...    Retourne `{erreurs_console, depreciations, autres, erreurs_de_page,
    ...    premiere_autre}`. La seule propriété qui vaut assertion est
    ...    `erreurs_de_page` : une exception JS non rattrapée.
    ${diagnostic}=    Get Fiori Diagnostics
    ${console}=    Evaluate    $diagnostic.get('console') or []
    ${erreurs}=    Evaluate    [e for e in $console if e.get('type') == 'error']
    ${depreciations}=    Evaluate
    ...    [e for e in $erreurs if $WORKZONE_DEPRECATION_MARKER in e.get('text', '')]
    ${autres}=    Evaluate
    ...    [e for e in $erreurs if $WORKZONE_DEPRECATION_MARKER not in e.get('text', '')]
    ${page}=    Evaluate    $diagnostic.get('page_errors') or []
    ${premiere}=    Evaluate    ($autres[0].get('text', '') if $autres else '')
    ${bilan}=    Create Dictionary
    ...    erreurs_console=${{len($erreurs)}}
    ...    depreciations=${{len($depreciations)}}
    ...    autres=${{len($autres)}}
    ...    erreurs_de_page=${{len($page)}}
    ...    premiere_autre=${premiere}
    RETURN    ${bilan}

Journaliser Le Diagnostic Fiori En Cas D Echec
    [Documentation]    Teardown de test : en cas d'échec seulement, journalise
    ...    le diagnostic agrégé (composition, arbre UI5, erreurs console,
    ...    snapshot ARIA). Sur un launchpad, il distingue en une lecture une
    ...    dérive de localisateur d'une application qui n'a pas chargé.
    Run Keyword If Test Failed    Log Fiori Diagnostics
