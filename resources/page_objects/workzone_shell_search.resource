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
...                 Page object de la **recherche du shell d'un launchpad SAP
...                 Build Work Zone** (cFLP sur BTP) : configuration déclarée,
...                 ouverture du champ, suggestions, page de résultats,
...                 comptage porté, état sans résultat et ouverture d'un
...                 résultat. Le shell lui-même (session, catalogue, iframes,
...                 retour à l'accueil) vit dans `workzone_launchpad.resource`,
...                 que ce fichier importe.
...
...                 Relevé live le 2026-08-26 (rf-mcp : Browser +
...                 SapFioriLibrary) sur un site Work Zone de trial BTP,
...                 runtime SAPUI5 1.151.0. Spec source :
...                 `specs/workzone-recherche-shell.md`.
...
...                 Contrat de localisation, appris sur la cible réelle :
...
...                 1. **Deux implémentations de recherche cohabitent, et la
...                 configuration dit laquelle est active.** Le champ que la
...                 campagne de perception compte
...                 (`ShellBarView--shellBarSearchInput`, variable
...                 `${WORKZONE_SEARCH_FIELD}` du page object du shell)
...                 appartient à la recherche « CEP » nouvelle génération, que
...                 `ushell.searchCEPNew.enabled` déclare DÉSACTIVÉE : il est
...                 rendu et de rectangle nul. Celui qui reçoit la frappe est
...                 l'Enterprise Search classique (`searchFieldInShell-input`).
...                 Le premier ne doit jamais être rempli.
...                 2. **Le bouton d'ouverture vit dans le shadow root du
...                 `ui5-shellbar` et n'a aucun identifiant** : l'ancre est le
...                 couple type de composant plus attribut d'icône, résolu par
...                 le moteur `wc` (qui traverse les shadow roots depuis la
...                 0.7.0). Le moteur `dom`, lui, ne les traverse pas : l'écart
...                 entre les trois comptages EST le défaut de bibliothèque
...                 restant, mesuré par `Compter Le Bouton De Recherche Par
...                 Moteur`.
...                 3. **Ce bouton n'est pas une bascule** : il DISPARAÎT quand
...                 le champ est ouvert (mesuré : 0 dans les trois canaux). Tout
...                 mot-clé qui ouvre la recherche vérifie donc d'abord si elle
...                 est déjà ouverte, sinon le clic échoue sur un bouton absent.
...                 4. **Écrire la valeur ne déclenche pas les suggestions** :
...                 `Fill Ui5 Input` pose bien la valeur, et le popover reste
...                 fermé. La saisie passe par de VRAIES frappes clavier, comme
...                 celle d'un utilisateur.
...                 5. **Toutes les ancres de la page de résultats sont des
...                 SUFFIXES** relatifs au contrôle composite, dont le compteur
...                 (`eshCompGenId_<n>`) est généré.
...                 6. **Ne jamais compter les tuiles globalement** sur la page
...                 de résultats : la tuile de l'accueil y reste rendue,
...                 invisible, et fausse le compte. Le comptage qui a un sens
...                 est porté par la grille de résultats.
...
...                 Portée : LECTURE SEULE. La recherche interroge, elle
...                 n'écrit ni ne configure rien.

Resource            workzone_launchpad.resource


*** Variables ***
# --- Ce que la configuration DÉCLARE, avant tout rendu -----------------------
${WORKZONE_SEARCH_CEP_CONFIG}           ushell.searchCEPNew.enabled
${WORKZONE_SEARCH_SERVICE_CONFIG}       services.Search.adapter.module
${WORKZONE_SEARCH_SERVICE_MARKER}       SearchAdapter    # fin attendue du module d'adaptateur

# --- Les deux implémentations ------------------------------------------------
# Le champ CEP est `${WORKZONE_SEARCH_FIELD}` (page object du shell) : réutilisé
# tel quel pour que les deux campagnes parlent du MÊME contrôle.
${WORKZONE_SEARCH_ESH_INPUT_TYPE}       sap.esh.search.ui.controls.SearchInput
${WORKZONE_SEARCH_COMPOSITE_TYPE}       sap.esh.search.ui.SearchCompositeControl

# --- Ouverture : le bouton vit dans le shadow root du ui5-shellbar -----------
${WORKZONE_SHELLBAR}                    ShellBarView--shellBar
${WORKZONE_SEARCH_TOGGLE_TAG}           Button    # type court du moteur wc
${WORKZONE_SEARCH_TOGGLE_PROPS}         {'icon': 'search'}
# LA MÊME chaîne CSS est passée au moteur `dom` et à la bibliothèque Browser :
# c'est ce qui rend l'écart de comptage imputable au moteur, pas au sélecteur.
${WORKZONE_SEARCH_TOGGLE_SELECTOR}      [id$="${WORKZONE_SHELLBAR}"] [icon="search"]

# --- Contrôles de la recherche d'entreprise, créés au premier clic -----------
${WORKZONE_SEARCH_GROUP}                searchFieldInShell
${WORKZONE_SEARCH_INPUT}                searchFieldInShell-input
${WORKZONE_SEARCH_TRIGGER}              searchFieldInShell-button
@{WORKZONE_SEARCH_CONTROLS}             ${WORKZONE_SEARCH_GROUP}    ${WORKZONE_SEARCH_INPUT}
...                                     ${WORKZONE_SEARCH_TRIGGER}
${WORKZONE_SEARCH_MIN_CONTROLS}         ${3}    # groupe, saisie, déclenchement

# --- Suggestions --------------------------------------------------------------
${WORKZONE_SEARCH_SUGGEST_POPUP}        searchFieldInShell-input-popup
${WORKZONE_SEARCH_SUGGEST_TABLE}        searchFieldInShell-input-popup-table
${WORKZONE_SEARCH_SUGGEST_ITEM_TYPE}    sap.m.ColumnListItem

# --- Page de résultats : suffixes relatifs au composite généré ---------------
${WORKZONE_SEARCH_INTENT}               Action-search
${WORKZONE_SEARCH_APP_CONTAINER}        application-Action-search-content
${WORKZONE_SEARCH_RESULT_GRID}          ushell-search-result-app
${WORKZONE_SEARCH_RESULT_TYPE}          sap.ushell.ui.launchpad.VizInstanceCdm
${WORKZONE_SEARCH_NO_RESULT_SCREEN}     searchContainerResultsView-noResultScreen
${WORKZONE_SEARCH_ILLUSTRATION_TYPE}    sap.m.IllustratedMessage
# Source de données technique du filtre : les APPLICATIONS du site. Le libellé
# porté à côté (« Apps ») est traduit, l'identifiant ne l'est pas.
${WORKZONE_SEARCH_APPS_DATASOURCE}      $$APPS$$
${WORKZONE_SEARCH_DATASOURCE_TYPE}      Category

# --- Terme de recherche -------------------------------------------------------
${WORKZONE_SEARCH_PREFIX_LENGTH}        ${4}    # longueur du préfixe dérivé d'un titre découvert
${WORKZONE_SEARCH_ABSENT_TERM}          zzqxwv7788    # fabriqué : aucune correspondance possible
# Relevés au catalogue par le Suite Setup, jamais écrits : voir
# `Memoriser Une Application Temoin`.
&{WORKZONE_APP_TEMOIN}                  titre=${EMPTY}    intent=${EMPTY}    cible=${EMPTY}
${WORKZONE_TERME_TROUVE}                ${EMPTY}

# --- Budgets d'attente --------------------------------------------------------
${WORKZONE_SEARCH_TIMEOUT}              60s    # le module de recherche se charge au premier clic
${WORKZONE_SEARCH_RETRY}                0.5s

# Le fragment de la page de résultats a la forme
# `#Action-search&/top=20&filter=<json encodé>` : il est lu par le keyword de
# bibliothèque `Get Page Location` (convention #12) puis décodé en Python dans
# `Lire Le Filtre De Recherche`. Seules les trois valeurs techniques comptent :
# identifiant de la source de données, son type, et le terme soumis. Ni le
# libellé de la source ni le texte du compteur, tous deux traduits (convention 3).


*** Keywords ***
# --- Suite Setup / Teardown de la campagne -----------------------------------

Preparer La Campagne Recherche Shell
    [Documentation]    Suite Setup : ouvre la session Work Zone (page object du
    ...    shell) puis relève au catalogue l'application témoin et le terme qui
    ...    en dérive. Rien de plus, et c'est délibéré : le premier scénario doit
    ...    observer un shell dont la recherche d'entreprise n'a JAMAIS été
    ...    ouverte, ses contrôles n'étant créés qu'au premier clic. Ni la
    ...    lecture du catalogue ni celle de la configuration ne les créent.
    Ouvrir La Session Work Zone
    Memoriser Une Application Temoin

Memoriser Une Application Temoin
    [Documentation]    Relève au catalogue la première application accessible et
    ...    en dérive un terme de recherche, publiés en variables de suite
    ...    `${WORKZONE_APP_TEMOIN}` et `${WORKZONE_TERME_TROUVE}`. Un seul
    ...    relevé pour toute la campagne : aucun titre ni intent n'est écrit
    ...    dans les tests, et chaque comparaison porte sur deux mesures du MÊME
    ...    run.
    ${apps}=    Inventorier Les Applications Du Catalogue
    Should Not Be Empty    ${apps}
    ...    msg=Le catalogue ne déclare aucune application accessible : la recherche n'aurait rien à indexer, la campagne n'a pas d'objet.
    ${temoin}=    Set Variable    ${apps}[0]
    ${terme}=    Deriver Un Terme Partiel    ${temoin}[titre]
    Set Suite Variable    ${WORKZONE_APP_TEMOIN}    ${temoin}
    Set Suite Variable    ${WORKZONE_TERME_TROUVE}    ${terme}
    Log    Application témoin découverte au catalogue : intent ${temoin}[intent] ; terme partiel dérivé de son titre : ${terme}

Clore La Campagne Recherche Shell
    [Documentation]    Suite Teardown : ramène le shell à son accueil (une
    ...    suite qui s'arrête sur une page de résultats laisse un fragment
    ...    porteur d'état) puis ferme la session. S'exécute MÊME sur échec,
    ...    c'est ce qui autorise à rejouer la campagne sur un site partagé.
    Run Keyword And Ignore Error    Revenir A L Accueil Du Launchpad
    Fermer La Session Work Zone

# --- Ce que la configuration déclare ------------------------------------------

Lire La Configuration De La Recherche
    [Documentation]    Ce que la configuration du shell DÉCLARE de sa recherche,
    ...    avant tout rendu : `{nouvelle_generation, adaptateur}`, où
    ...    `nouvelle_generation` est l'indicateur d'activation de la recherche
    ...    « CEP » et `adaptateur` le module d'adaptateur du service de
    ...    recherche déclaré. Les deux sont techniques, donc
    ...    locale-indépendants, et disponibles avant qu'un seul contrôle soit
    ...    construit.
    ${cep}=    Get Ushell Config    path=${WORKZONE_SEARCH_CEP_CONFIG}
    ${adaptateur}=    Get Ushell Config    path=${WORKZONE_SEARCH_SERVICE_CONFIG}
    ${declaration}=    Create Dictionary    nouvelle_generation=${cep}    adaptateur=${adaptateur}
    RETURN    ${declaration}

# --- Visibilité RÉELLE : rendu ne veut pas dire visible ----------------------

Le Champ Est Visible A L Ecran
    [Documentation]    Vrai quand le contrôle désigné par son suffixe
    ...    d'identifiant est rendu ET occupe un rectangle non nul ; faux quand
    ...    il est absent du registre ou rendu à 0 par 0. Prédicat, jamais une
    ...    assertion : les deux issues sont des informations que l'appelant
    ...    confronte à ce que la configuration déclare.
    ...
    ...    Mesuré live le 2026-08-26, ce site rend le champ de la recherche
    ...    nouvelle génération à 0 par 0 en permanence, et replie celui de la
    ...    recherche d'entreprise dès qu'une application est ouverte : la
    ...    présence au registre ne prouve donc rien dans les deux sens.
    ...
    ...    Le contrôle absent est tranché par un COMPTAGE avant d'appeler
    ...    l'assertion : celle-ci sonde jusqu'à son budget d'attente, et un
    ...    prédicat qui met quinze secondes à répondre « non » se paie à chaque
    ...    appel.
    [Arguments]    ${suffixe}
    ${present}=    Get Ui5 Match Count    idSuffix=${suffixe}
    IF    ${present} == 0    RETURN    ${False}
    ${visible}=    Run Keyword And Return Status
    ...    Ui5 Control Should Be Visible    idSuffix=${suffixe}
    RETURN    ${visible}

Lire Les Etats Navigateur Du Champ
    [Documentation]    États que la bibliothèque Browser rapporte du contrôle
    ...    désigné (`attached`, `hidden`, `enabled`...) : le second canal, tout
    ...    aussi locale-indépendant, qui corrobore la mesure du rectangle. Liste
    ...    vide si le contrôle n'est pas au registre.
    [Arguments]    ${suffixe}
    ${present}=    Get Ui5 Match Count    idSuffix=${suffixe}
    IF    ${present} == 0
        ${vide}=    Create List
        RETURN    ${vide}
    END
    ${selecteur}=    Resolve Ui5 Control    idSuffix=${suffixe}
    ${etats}=    Get Element States    ${selecteur}
    RETURN    ${etats}

Compter Le Champ De Recherche Nouvelle Generation
    [Documentation]    Nombre de champs de la recherche « CEP » nouvelle
    ...    génération rendus dans la portée courante. C'est le contrôle que la
    ...    campagne de perception compte comme témoin d'étanchéité de portée :
    ...    il reste un témoin valable, et ce n'est pas le champ dans lequel
    ...    l'utilisateur tape.
    ${nb}=    Get Ui5 Match Count    idSuffix=${WORKZONE_SEARCH_FIELD}
    RETURN    ${nb}

# --- Ouverture de la recherche d'entreprise ----------------------------------

Compter Les Controles De La Recherche
    [Documentation]    Nombre de contrôles de la recherche d'entreprise rendus
    ...    parmi ses trois ancres stables : le groupe, la saisie et le
    ...    déclenchement. Vaut 0 tant que la recherche n'a jamais été ouverte
    ...    (ces contrôles sont créés au premier clic), puis 3.
    ${total}=    Set Variable    ${0}
    FOR    ${ancre}    IN    @{WORKZONE_SEARCH_CONTROLS}
        ${nb}=    Get Ui5 Match Count    idSuffix=${ancre}
        ${total}=    Evaluate    ${total} + ${nb}
    END
    RETURN    ${total}

Compter Le Bouton De Recherche Par Moteur
    [Documentation]    Le bouton d'ouverture de la recherche compté par TROIS
    ...    canaux, avec la même ancre technique (attribut d'icône, sous la barre
    ...    shell désignée par son suffixe d'identifiant) : le moteur `wc` de la
    ...    bibliothèque, son moteur `dom`, et la bibliothèque Browser. Retourne
    ...    `{wc, dom, navigateur}`.
    ...
    ...    C'est la MESURE, dans le test, de ce que les moteurs traversent :
    ...    relevé le 2026-08-26 sur ce shell, `wc` et Browser voient le bouton
    ...    (1), le moteur `dom` ne le voit pas (0), son balayage restant au
    ...    light DOM. À appeler recherche FERMÉE : ouverte, le bouton disparaît
    ...    et les trois canaux rendent 0.
    ${wc}=    Get Wc Match Count    tag=${WORKZONE_SEARCH_TOGGLE_TAG}
    ...    properties=${WORKZONE_SEARCH_TOGGLE_PROPS}
    ${dom}=    Get Dom Match Count    css=${WORKZONE_SEARCH_TOGGLE_SELECTOR}
    ${navigateur}=    Get Element Count    css=${WORKZONE_SEARCH_TOGGLE_SELECTOR}
    ${comptes}=    Create Dictionary    wc=${wc}    dom=${dom}    navigateur=${navigateur}
    RETURN    ${comptes}

La Recherche Du Shell Est Ouverte
    [Documentation]    Prédicat d'ouverture : le champ de saisie de la recherche
    ...    d'entreprise occupe un rectangle non nul. Le comptage ne suffirait
    ...    pas : une fois créés, ces contrôles ne sont plus détruits, et le
    ...    groupe est simplement replié dans une application.
    Ui5 Control Should Be Visible    idSuffix=${WORKZONE_SEARCH_INPUT}

Ouvrir La Recherche Du Shell
    [Documentation]    Ouvre la recherche depuis la barre shell et rend la main
    ...    quand le champ de saisie est réellement visible. IDEMPOTENT :
    ...    n'agit que si la recherche est fermée, parce que le bouton n'est pas
    ...    une bascule mais DISPARAÎT une fois le champ ouvert (mesuré live) ;
    ...    un second clic échouerait donc sur un bouton absent.
    ...
    ...    Le clic passe par le moteur `wc`, seul canal de la bibliothèque qui
    ...    traverse le shadow root du `ui5-shellbar` où vit ce bouton sans
    ...    identifiant.
    ${deja_ouverte}=    Le Champ Est Visible A L Ecran    ${WORKZONE_SEARCH_INPUT}
    IF    ${deja_ouverte}    RETURN
    Click Wc Control    tag=${WORKZONE_SEARCH_TOGGLE_TAG}
    ...    properties=${WORKZONE_SEARCH_TOGGLE_PROPS}
    Wait Until Keyword Succeeds    ${WORKZONE_SEARCH_TIMEOUT}    ${WORKZONE_SEARCH_RETRY}
    ...    La Recherche Du Shell Est Ouverte

# --- Saisie et suggestions ----------------------------------------------------

Deriver Un Terme Partiel
    [Documentation]    Dérive un terme de recherche du titre d'une application
    ...    DÉCOUVERTE au catalogue : le préfixe de son premier mot. Le titre
    ...    exact n'est jamais soumis, pour deux raisons : c'est un libellé
    ...    traduit, et sur certains shells il déclenche une navigation directe
    ...    vers l'application, sans page de résultats. Échoue quand le titre est
    ...    trop court pour qu'un préfixe STRICT en soit tiré.
    [Arguments]    ${titre}
    ${terme}=    Evaluate    ($titre.split() or [$titre])[0][:${WORKZONE_SEARCH_PREFIX_LENGTH}]
    ${strict}=    Evaluate    bool($terme) and len($terme) < len($titre)
    Should Be True    ${strict}
    ...    msg=Aucun préfixe strict ne peut être dérivé du titre '${titre}' : soumettre le titre exact risquerait une navigation directe sans page de résultats.
    RETURN    ${terme}

Saisir Un Terme De Recherche
    [Documentation]    Ouvre la recherche si besoin puis saisit le terme par de
    ...    VRAIES frappes clavier, en remplaçant ce que le champ portait, et ne
    ...    rend la main que lorsque le champ porte RÉELLEMENT ce terme. Ne
    ...    valide pas.
    ...
    ...    Les frappes ne sont pas une coquetterie : mesuré live, poser la
    ...    valeur par `Fill Ui5 Input` renseigne bien le champ et laisse le
    ...    popover de suggestions FERMÉ. La recherche d'entreprise réagit à la
    ...    frappe, pas à la valeur.
    ...
    ...    La relecture non plus : mesurée live sur la page de résultats, la
    ...    frappe peut manquer le champ, l'application de résultats reprenant le
    ...    focus après son rendu. Les touches partent alors au document, et
    ...    l'assertion suivante porterait sur une recherche que personne n'a
    ...    saisie. Le geste est donc rejoué jusqu'à ce que le champ le porte.
    [Arguments]    ${terme}
    Ouvrir La Recherche Du Shell
    Wait Until Keyword Succeeds    ${WORKZONE_SEARCH_TIMEOUT}    ${WORKZONE_SEARCH_RETRY}
    ...    Frapper Le Terme Dans Le Champ    ${terme}

Frapper Le Terme Dans Le Champ
    [Documentation]    Un geste de saisie complet, focus compris, suivi de sa
    ...    CONSTATATION : cliquer le champ, tout sélectionner, frapper le terme,
    ...    puis relire ce que le champ porte. Échoue quand la frappe n'a pas
    ...    atteint le champ, ce qui rend le geste rejouable par l'appelant.
    [Arguments]    ${terme}
    Click Ui5 Control    idSuffix=${WORKZONE_SEARCH_INPUT}
    Keyboard Key    press    Control+a
    Keyboard Input    type    ${terme}
    ${porte}=    Lire Le Terme Du Champ De Recherche
    Should Be Equal    ${porte}    ${terme}
    ...    msg=Le champ de recherche porte « ${porte} » après la frappe de « ${terme} » : les touches ne l'ont pas atteint.

Lire Le Terme Du Champ De Recherche
    [Documentation]    Terme actuellement porté par le champ de saisie, lu à sa
    ...    PROPRIÉTÉ et non à son rendu.
    ${terme}=    Get Ui5 Property    value    idSuffix=${WORKZONE_SEARCH_INPUT}
    RETURN    ${terme}

Le Popover De Suggestions Est Ouvert
    [Documentation]    Prédicat : le popover de suggestions figure parmi les
    ...    popups OUVERTS. Retourne son entrée de popup.
    ${popups}=    Get Ui5 Open Popups
    ${cibles}=    Evaluate
    ...    [p for p in $popups if p['kind'] == 'popover' and p['id'].endswith($WORKZONE_SEARCH_SUGGEST_POPUP)]
    Should Not Be Empty    ${cibles}
    ...    msg=Le popover de suggestions (${WORKZONE_SEARCH_SUGGEST_POPUP}) n'est pas ouvert. Popups réellement ouverts : ${popups}
    RETURN    ${cibles}[0]

Les Suggestions Sont Proposees
    [Documentation]    Attend que le popover de suggestions soit réellement
    ...    ouvert et retourne son entrée de popup. L'attente est indispensable :
    ...    mesuré live, les suggestions arrivent APRÈS le retour au repos
    ...    réseau, une lecture immédiate rend une liste de popups vide sur une
    ...    recherche parfaitement saine.
    ${popover}=    Wait Until Keyword Succeeds    ${WORKZONE_SEARCH_TIMEOUT}    ${WORKZONE_SEARCH_RETRY}
    ...    Le Popover De Suggestions Est Ouvert
    RETURN    ${popover}

Lire Les Suggestions
    [Documentation]    Contenu des suggestions proposées : le texte rendu de
    ...    chaque ligne de la table du popover. Ce texte est traduit, comme le
    ...    titre du catalogue auquel l'appelant le compare : les deux mesures
    ...    viennent du MÊME run, aucun libellé n'est écrit dans le test.
    ${ids}=    Get Ui5 Ids    controlType=${WORKZONE_SEARCH_SUGGEST_ITEM_TYPE}
    ...    containedIn=${WORKZONE_SEARCH_SUGGEST_TABLE}
    ${textes}=    Create List
    FOR    ${id}    IN    @{ids}
        ${texte}=    Get Ui5 Text    id=${id}
        ${propre}=    Evaluate    ' '.join($texte.split())
        Append To List    ${textes}    ${propre}
    END
    RETURN    ${textes}

Fermer Les Suggestions
    [Documentation]    Referme le popover de suggestions par la touche
    ...    d'échappement et CONSTATE la fermeture. Le champ de saisie reste
    ...    ouvert et visible : l'échappement ne referme que le popover (mesuré).
    Keyboard Key    press    Escape
    Wait Until Keyword Succeeds    ${WORKZONE_SEARCH_TIMEOUT}    ${WORKZONE_SEARCH_RETRY}
    ...    Aucune Suggestion N Est Ouverte

Aucune Suggestion N Est Ouverte
    [Documentation]    Prédicat de fermeture du popover de suggestions.
    ${popups}=    Get Ui5 Open Popups
    ${restants}=    Evaluate
    ...    [p for p in $popups if p['id'].endswith($WORKZONE_SEARCH_SUGGEST_POPUP)]
    Should Be Empty    ${restants}
    ...    msg=Le popover de suggestions est encore ouvert : ${restants}

# --- Lancement et page de résultats -------------------------------------------

Lancer La Recherche
    [Documentation]    Saisit le terme puis le soumet par le BOUTON de
    ...    déclenchement du champ, et rend la main quand l'application de
    ...    recherche est présente. Fonctionne depuis l'accueil comme depuis une
    ...    application ouverte.
    ...
    ...    La soumission passe par le bouton et non par la touche Entrée, qui
    ...    n'est pas déterministe ici : mesuré live, une frappe qui manque le
    ...    champ laisse la touche Entrée ACTIVER l'élément focalisé de la page,
    ...    et sur une page de résultats c'est la tuile du premier résultat, donc
    ...    l'application s'ouvre au lieu de la recherche. Le bouton, lui, soumet
    ...    la valeur du champ, quoi qu'il arrive au focus.
    [Arguments]    ${terme}
    Saisir Un Terme De Recherche    ${terme}
    Click Ui5 Control    idSuffix=${WORKZONE_SEARCH_TRIGGER}
    Wait For Ui5 Idle
    Attendre L Application De Recherche

Attendre L Application De Recherche
    [Documentation]    Attend que le conteneur d'application de la recherche,
    ...    dérivé de son intent, soit présent. C'est LE témoin d'attente : le
    ...    fragment change AVANT que l'application de résultats existe, donc
    ...    l'attendre sur le fragment seul laisserait lire une page qui n'a
    ...    encore rien construit.
    Wait Until Keyword Succeeds    ${WORKZONE_SEARCH_TIMEOUT}    ${WORKZONE_SEARCH_RETRY}
    ...    L Application De Recherche Est Presente

L Application De Recherche Est Presente
    [Documentation]    Prédicat : le conteneur d'application de la recherche est
    ...    rendu exactement une fois.
    ${nb}=    Compter Le Conteneur De L Application De Recherche
    Should Be Equal As Integers    ${nb}    1
    ...    msg=Le conteneur de l'application de recherche (${WORKZONE_SEARCH_APP_CONTAINER}) est rendu ${nb} fois au lieu d'une.

Compter Le Conteneur De L Application De Recherche
    [Documentation]    Nombre de conteneurs d'application dérivés de l'intent de
    ...    recherche du shell, rendus dans la portée courante.
    ${nb}=    Get Ui5 Match Count    idSuffix=${WORKZONE_SEARCH_APP_CONTAINER}
    RETURN    ${nb}

Lire Le Filtre De Recherche
    [Documentation]    Filtre porté par le fragment, décodé : `{source,
    ...    type_source, terme}`. `source` est l'identifiant TECHNIQUE de la
    ...    source de données interrogée, jamais son libellé, qui est traduit.
    ${ou}=    Get Page Location
    ${part}=    Evaluate
    ...    ([p for p in $ou['fragment'].split('&') if p.startswith('filter=')] or [''])[0]
    ${status}    ${brut}=    Run Keyword And Ignore Error    Evaluate
    ...    json.loads(urllib.parse.unquote($part[7:])) if $part else None
    ...    modules=json, urllib.parse
    IF    '${status}' != 'PASS' or $brut is None
        Fail    Le fragment courant ne porte aucun filtre de recherche décodable : la page de résultats n'a pas été atteinte.
    END
    ${filtre}=    Evaluate
    ...    {'source': str(($brut.get('dataSource') or {}).get('id') or ''), 'type_source': str(($brut.get('dataSource') or {}).get('type') or ''), 'terme': str($brut.get('searchTerm') or '')}
    RETURN    ${filtre}

Lire L Intent Porte Par Le Fragment
    [Documentation]    Partie `SemanticObject-action` du fragment courant,
    ...    isolée par DÉCOUPAGE (sur le croisillon, puis sur l'esperluette, puis
    ...    sur le point d'interrogation), jamais par une expression régulière à
    ...    contre-oblique. Rend l'intent nu : ni les paramètres de navigation,
    ...    ni les segments d'état de l'application.
    ${url}=    Get Url
    ${intent}=    Evaluate
    ...    ($url.split('#', 1)[1] if '#' in $url else '').split('&')[0].split('?')[0]
    RETURN    ${intent}

Compter Les Controles Rendus
    [Documentation]    Nombre de contrôles UI5 construits dans la portée
    ...    courante, lu à la composition perçue. Ne vaut qu'en COMPARAISON de
    ...    deux relevés du même run : mesuré live, la même page de résultats
    ...    porte des nombres très différents selon le chemin d'arrivée, et
    ...    l'accueil grossit au fil de la campagne. Aucun plancher n'est gravé.
    ${composition}=    Get Page Composition
    RETURN    ${composition}[ui5_controls]

# --- Comptage des résultats : porté, jamais global ---------------------------

Compter Les Resultats De Recherche
    [Documentation]    Nombre de résultats PORTÉS par la grille de résultats :
    ...    le seul comptage qui a un sens sur cette page. Zéro quand la grille
    ...    n'est pas rendue.
    ${nb}=    Get Ui5 Match Count    controlType=${WORKZONE_SEARCH_RESULT_TYPE}
    ...    containedIn=${WORKZONE_SEARCH_RESULT_GRID}
    RETURN    ${nb}

Compter Toutes Les Tuiles De La Page
    [Documentation]    Nombre de tuiles rendues dans TOUTE la page : le
    ...    contre-exemple, journalisé et jamais utilisé comme mesure de
    ...    résultats. Mesuré live, il rend 2 pour 1 résultat, la tuile de
    ...    l'accueil restant rendue, invisible, sous la page de résultats.
    ${nb}=    Get Ui5 Match Count    controlType=${WORKZONE_TILE_CONTROL}
    RETURN    ${nb}

Lire Les Tuiles De La Page
    [Documentation]    Une ligne par tuile rendue dans la page :
    ...    `{id, visible, dans_les_resultats}`, où `visible` mesure le rectangle
    ...    et `dans_les_resultats` l'appartenance à la grille de résultats.
    ...    C'est la lecture qui EXPLIQUE l'écart entre le comptage global et le
    ...    comptage porté, au lieu de le constater.
    ${globales}=    Get Ui5 Ids    controlType=${WORKZONE_TILE_CONTROL}
    ${portees}=    Get Ui5 Ids    controlType=${WORKZONE_TILE_CONTROL}
    ...    containedIn=${WORKZONE_SEARCH_RESULT_GRID}
    ${lignes}=    Create List
    FOR    ${id}    IN    @{globales}
        ${visible}=    Run Keyword And Return Status    Ui5 Control Should Be Visible    id=${id}
        ${dans}=    Evaluate    $id in $portees
        ${ligne}=    Create Dictionary    id=${id}    visible=${visible}    dans_les_resultats=${dans}
        Append To List    ${lignes}    ${ligne}
    END
    RETURN    ${lignes}

Lire Les Resultats De Recherche
    [Documentation]    Résultats portés par la grille : une liste de dicts
    ...    `{titre, cible}` lus aux PROPRIÉTÉS des contrôles de résultat, jamais
    ...    à leur rendu. La `cible` est le hash de navigation que le résultat
    ...    ouvrira.
    ${titres}=    Get Ui5 Properties    title    controlType=${WORKZONE_SEARCH_RESULT_TYPE}
    ...    containedIn=${WORKZONE_SEARCH_RESULT_GRID}
    ${cibles}=    Get Ui5 Properties    targetURL    controlType=${WORKZONE_SEARCH_RESULT_TYPE}
    ...    containedIn=${WORKZONE_SEARCH_RESULT_GRID}
    ${resultats}=    Create List
    FOR    ${indice}    IN RANGE    ${{len($titres)}}
        ${ligne}=    Create Dictionary    titre=${titres}[${indice}]    cible=${cibles}[${indice}]
        Append To List    ${resultats}    ${ligne}
    END
    RETURN    ${resultats}

# --- Les deux états structurellement distincts -------------------------------

La Grille De Resultats Est Affichee
    [Documentation]    Prédicat : la grille de résultats est rendue.
    ${nb}=    Get Ui5 Match Count    idSuffix=${WORKZONE_SEARCH_RESULT_GRID}
    Should Be True    ${nb} > 0
    ...    msg=La grille de résultats (${WORKZONE_SEARCH_RESULT_GRID}) n'est pas rendue.

La Grille De Resultats N Est Pas Rendue
    [Documentation]    Prédicat inverse : aucune grille de résultats au registre.
    ${nb}=    Get Ui5 Match Count    idSuffix=${WORKZONE_SEARCH_RESULT_GRID}
    Should Be Equal As Integers    ${nb}    0
    ...    msg=La grille de résultats est encore rendue (${nb}) alors que la recherche n'a rien trouvé.

L Ecran Sans Resultat Est Affiche
    [Documentation]    Prédicat : l'écran dédié « sans résultat » est rendu, et
    ...    porte son illustration. Deux constats, parce que l'état « aucune
    ...    correspondance » se reconnaît à ce qui est CONSTRUIT, pas au texte du
    ...    compteur, qui est traduit.
    ${nb}=    Get Ui5 Match Count    idSuffix=${WORKZONE_SEARCH_NO_RESULT_SCREEN}
    Should Be True    ${nb} > 0
    ...    msg=L'écran dédié « sans résultat » (${WORKZONE_SEARCH_NO_RESULT_SCREEN}) n'est pas rendu.
    ${illustrations}=    Get Ui5 Match Count    controlType=${WORKZONE_SEARCH_ILLUSTRATION_TYPE}
    Should Be True    ${illustrations} > 0
    ...    msg=L'écran « sans résultat » est rendu mais sans son illustration.

L Ecran Sans Resultat N Est Pas Rendu
    [Documentation]    Prédicat inverse : plus d'écran dédié « sans résultat ».
    ${nb}=    Get Ui5 Match Count    idSuffix=${WORKZONE_SEARCH_NO_RESULT_SCREEN}
    Should Be Equal As Integers    ${nb}    0
    ...    msg=L'écran « sans résultat » est encore rendu (${nb}) alors que la recherche a trouvé quelque chose.

Attendre L Etat Sans Resultat
    [Documentation]    Attend l'état « aucune correspondance » : grille ABSENTE
    ...    et écran dédié PRÉSENT. Les deux constats ensemble, parce que
    ...    constater seulement « zéro résultat » serait vrai d'une page qui n'a
    ...    rien construit du tout.
    Wait Until Keyword Succeeds    ${WORKZONE_SEARCH_TIMEOUT}    ${WORKZONE_SEARCH_RETRY}
    ...    La Grille De Resultats N Est Pas Rendue
    Wait Until Keyword Succeeds    ${WORKZONE_SEARCH_TIMEOUT}    ${WORKZONE_SEARCH_RETRY}
    ...    L Ecran Sans Resultat Est Affiche

Attendre L Etat Avec Resultats
    [Documentation]    Attend l'état « résultats » : grille PRÉSENTE et écran
    ...    dédié disparu, les deux constats de l'état précédent inversés.
    Wait Until Keyword Succeeds    ${WORKZONE_SEARCH_TIMEOUT}    ${WORKZONE_SEARCH_RETRY}
    ...    La Grille De Resultats Est Affichee
    Wait Until Keyword Succeeds    ${WORKZONE_SEARCH_TIMEOUT}    ${WORKZONE_SEARCH_RETRY}
    ...    L Ecran Sans Resultat N Est Pas Rendu

# --- Ouvrir un résultat --------------------------------------------------------

Ouvrir Le Premier Resultat De Recherche
    [Documentation]    Ouvre le premier résultat porté par la grille, comme le
    ...    ferait l'utilisateur, et rend la main quand l'iframe de
    ...    l'application est là. La tuile visée est celle de la GRILLE : un clic
    ...    sur la tuile de l'accueil, encore rendue et invisible sous la page de
    ...    résultats, n'ouvrirait rien.
    Click Ui5 Control    controlType=${WORKZONE_TILE_CONTROL}
    ...    containedIn=${WORKZONE_SEARCH_RESULT_GRID}
    Attendre L Iframe De L Application

Lire L Adresse De L Application Ouverte
    [Documentation]    Adresse réellement chargée dans l'iframe de
    ...    l'application ouverte, lue à la composition perçue. La comparaison de
    ...    deux voies d'ouverture porte sur CETTE adresse et sur l'intent, pas
    ...    sur le fragment complet : la cible d'un résultat de recherche porte
    ...    en plus un paramètre d'identification du contenu du site, que
    ...    l'intent nu ne porte pas.
    ${composition}=    Get Page Composition
    ${sources}=    Evaluate    [f['src'] for f in $composition['frames']]
    Should Not Be Empty    ${sources}
    ...    msg=Aucune iframe d'application dans la portée courante : aucune adresse à lire.
    RETURN    ${sources}[0]

Revenir En Arriere
    [Documentation]    Navigation arrière du navigateur, suivie du retour au
    ...    repos réel. Ne conclure d'aucun comptage de contrôles après ce
    ...    geste : mesuré live, une page de résultats reconstruite par un retour
    ...    arrière se stabilise à un nombre de contrôles sans rapport avec celui
    ...    de sa première construction.
    Go Back
    Wait For Ui5 Idle
