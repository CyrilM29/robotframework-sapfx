*** Settings ***
Documentation       **EXEMPLE À PERSONNALISER** : ce fichier porte le vocabulaire
...                 métier du LABORATOIRE de ce dépôt (identifiants, clés
...                 techniques et familles d'anomalies relevés live sur SES
...                 cibles). Beaucoup s'y réutilise tel quel sur une autre
...                 instance du Demo Kit, mais rien n'y fait autorité : à
...                 VÉRIFIER sur votre cible et à adapter. Ce qui fait foi
...                 partout, c'est `src/`, les bibliothèques, qui portent les
...                 capacités : voir `resources/README.md`.
...
...                 Page object du **Demo Kit OpenUI5** (`sdk.openui5.org`) :
...                 barre de navigation, recherche globale, arbre de la
...                 Référence de l'API, tables de documentation, menu Options,
...                 thème, iframe d'échantillon et classement des anomalies.
...
...                 Relevé live le 2026-08-30 (rf-mcp : Browser +
...                 SapFioriLibrary), runtime SAPUI5 1.151.0, navigateur
...                 VISIBLE. Spec source :
...                 `specs/openui5-demokit-navigation-interaction.md`.
...
...                 Contrat de localisation, appris sur la cible réelle :
...
...                 1. **Aucun libellé visible n'est une ancre.** La langue
...                 servie a changé en cours de run chez l'explorateur
...                 (`fr-FR` puis `en-US`, libellés suivis, un même popover
...                 mélangeant les deux). Les seules chaînes exploitables sont
...                 techniques : `key` d'un onglet ou d'une entrée de menu,
...                 `icon`, `target` d'un nœud d'arbre, nom qualifié d'un
...                 contrôle, titre du document. La langue se JOURNALISE, elle
...                 ne s'asserte pas.
...                 2. **La pile de popups est le seul témoin d'ouverture.**
...                 Le `sap.m.Popover` de cette version n'a pas de propriété
...                 `open`, et une entrée de menu fermé compte encore une
...                 correspondance (rectangle nul). Toute ouverture et toute
...                 fermeture se constatent sur `Get Ui5 Open Popups`, et se
...                 SONDENT : mesuré, un dialogue annulé est encore dans la
...                 pile à l'instant qui suit le clic.
...                 3. **L'appariement des propriétés se fait par sous-chaîne**,
...                 donc tout nom préfixe d'un autre est ambigu (mesuré :
...                 `sap.uxap.ObjectPageLayout` compte 2 correspondances à
...                 cause de `ObjectPageLayoutMediaRange`, 1 seule sous la
...                 forme ancrée). Les noms qualifiés passent par
...                 `Motif Exact`, jamais en clair. Le point y reste un
...                 métacaractère assumé : il matche le point littéral, et
...                 aucune entité du catalogue ne se distingue d'une autre par
...                 ce seul caractère.
...                 4. **L'arbre de l'API se compte DANS son conteneur.** Le
...                 Demo Kit garde le maître de la Documentation rendu à côté
...                 de celui de l'API, et ses nœuds sont du même type : le
...                 comptage global rendait 380 nœuds dont 9 dont le `target`
...                 est un identifiant de rubrique (une empreinte, pas un nom
...                 qualifié). Toute lecture d'arbre est donc portée par
...                 `containedIn`.
...                 5. **Le repos réseau ne témoigne pas des actions locales.**
...                 Le filtre de l'arbre, la bascule d'affichage, l'ouverture
...                 des suggestions et le retour arrière n'émettent aucune
...                 requête : `Wait For Ui5 Idle` rend la main instantanément
...                 et ne prouve rien. Chaque geste local est suivi d'une
...                 attente ACTIVE de son propre témoin (comptage, propriété,
...                 couple URL plus titre), jamais d'une attente fixe
...                 (convention 2).
...                 6. **Tout identifiant généré est interdit d'ancrage**
...                 (`__item*`, `__table*`, `__popover*`, `__status*`) : ils ne
...                 traversent ni les pages ni les frames. Restent les ids
...                 stables adressés par leur SUFFIXE (`sdk---app--*`,
...                 `sdk---apiMaster--*`, `GlobalSettingsDialog`,
...                 `LanguageSelect`, `sampleFrame`) et les propriétés
...                 techniques. Les identifiants générés qui servent de portée
...                 (popover courant, table de rubrique) sont DÉCOUVERTS à
...                 l'exécution et jamais écrits ici.
...
...                 Portée : **LECTURE SEULE**. Aucune écriture, aucun
...                 formulaire soumis. Les deux seuls réglages touchés (thème,
...                 case d'affichage) sont relevés au setup et remis en état
...                 par un teardown qui s'exécute même sur échec.
...
...                 **Deux écarts de capacité relevés ici (convention 12) ont
...                 été corrigés DANS la bibliothèque le 2026-08-30, cette
...                 couche appelle donc `src/` et ne contourne plus rien :**
...
...                 * `Read Ui5 Table` rendait une liste VIDE sans échouer sur
...                 une `sap.ui.documentation.LightTable`, alors que le
...                 sélecteur résout exactement 1 contrôle porteur de ses
...                 lignes : le profil « vert et faux » type. Le keyword échoue
...                 désormais en nommant le type et la voie de repli ; la
...                 lecture au registre reste la bonne voie pour cette table
...                 (voir `Lire Les Noms Techniques De Table De Doc`).
...                 * Le **thème DEMANDÉ** du runtime n'était lisible par aucun
...                 keyword, et l'obtenir d'ici aurait imposé du JS inline que
...                 la convention 12 interdit. `Get Ui5 Theme` rend maintenant
...                 les deux valeurs, `requested` et `applied`, et remplace la
...                 lecture de classe que ce fichier faisait lui-même.

Library             Collections
Library             String
Library             Browser
Library             SapFioriLibrary


*** Variables ***
# --- Cible et ouverture -------------------------------------------------------
${DEMOKIT_URL}                      https://sdk.openui5.org/
${DEMOKIT_BROWSER}                  chromium
# Navigateur VISIBLE par défaut : exigence de la campagne, pas un confort.
# Surchargeable en ligne de commande (`-v DEMOKIT_HEADLESS:True`) pour la CI.
${DEMOKIT_HEADLESS}                 False
${DEMOKIT_VIEWPORT}                 {'width': 1600, 'height': 950}
${DEMOKIT_TIMEOUT}                  60s
${DEMOKIT_POLL}                     0.3s
${DEMOKIT_MIN_CONTROLS}             ${100}    # plancher raisonné (551 mesurés)

# --- Bannière de consentement : le SEUL endroit où le moteur dom est requis ---
# Elle vit hors du runtime UI5, donc absente de l'arbre UI5 comme de la carte
# des cibles, et son script tiers est la source de l'unique erreur JS non
# interceptée de la session.
# La valeur porte le seul sélecteur CSS de ce fichier, sans son préfixe de
# stratégie : celui-ci doit rester ÉCRIT dans l'appel (`css=${...}`), la forme
# nommée d'un argument n'étant pas reconnue quand elle arrive dans la valeur
# d'une variable. L'identifiant est visé par son ATTRIBUT et non par la forme
# à dièse : dans un tableau de variables, un dièse précédé d'un séparateur
# ouvre un commentaire, et la variable partait vide (attrapé au premier run
# live : la bannière n'était plus trouvée et le sélecteur vide finissait par
# viser la racine du document).
${DEMOKIT_CONSENT_BUTTON}           [id="truste-consent-button"]
# La bannière est servie par un tiers et arrive APRÈS le runtime : un comptage
# immédiat rend 0 alors qu'elle s'affichera juste après, et elle intercepterait
# alors les clics de toute la campagne. Son apparition s'attend donc, avec un
# budget court et une absence tolérée (contexte où le consentement est déjà
# donné).
${DEMOKIT_CONSENT_TIMEOUT}          15s
${DEMOKIT_CONSENT_SHORT}            2s

# --- Barre de navigation : la clé technique VAUT la route ----------------------
${DEMOKIT_NAV_HEADER}               demoKitSubHeader
${DEMOKIT_TAB_TYPE}                 sap.m.IconTabFilter
# Route attendue par clé d'onglet. Le cas général est `/<clé>` ; l'accueil est
# la seule exception mesurée (fragment `/` et non `/home`).
&{DEMOKIT_ROUTE_BY_KEY}             home=/
@{DEMOKIT_EXPECTED_KEYS}            home    topic    api    controls

# --- En-tête : recherche globale et menu Options ------------------------------
${DEMOKIT_SEARCH_FIELD}             searchControl-searchField
${DEMOKIT_SUGGESTION_TYPE}          sap.m.StandardListItem
${DEMOKIT_SUGGESTION_GROUP_TYPE}    sap.m.GroupHeaderListItem
# Les entrées de résultat portent un identifiant technique suivi de sa
# catégorie entre parenthèses : `sap.m.Button (class): ...`. Le mot de la
# catégorie n'est PAS traduit (mesuré interface en français).
${DEMOKIT_SUGGESTION_CLASS_SUFFIX}    ${SPACE}(class)
${DEMOKIT_MENU_BUTTON}              aboutMenuButton
${DEMOKIT_MENU_BUTTON_ICON}         sap-icon://action-settings
${DEMOKIT_MENU_ITEM_TYPE}           sap.m.MenuItem
@{DEMOKIT_MENU_KEYS}                about    appearance    sitemap    settings
@{DEMOKIT_APPEARANCE_KEYS}          light    dark

# --- Dialogue des paramètres : le seul id stable de la couche popup -----------
${DEMOKIT_SETTINGS_DIALOG}          GlobalSettingsDialog
${DEMOKIT_LANGUAGE_SELECT}          LanguageSelect
${DEMOKIT_MENU_SETTINGS_KEY}        settings
${DEMOKIT_MENU_APPEARANCE_KEY}      appearance
# Les boutons du dialogue ont des ids générés : leur ROLE les distingue, et la
# position les atteint. Position 1 = annuler, la seule que cette campagne
# actionne (lecture seule).
@{DEMOKIT_DIALOG_BUTTON_TYPES}      Emphasized    Default
${DEMOKIT_DIALOG_CANCEL_POSITION}    ${1}

# --- Panneau maître de la Référence de l'API ----------------------------------
${DEMOKIT_API_TREE}                 apiMaster--tree
${DEMOKIT_API_FILTER}               apiMaster--searchField
${DEMOKIT_API_DEPRECATED}           apiMaster--includeDeprecated
${DEMOKIT_API_EXPERIMENTAL}         apiMaster--includeExperimental
${DEMOKIT_TREE_ITEM_TYPE}           sap.ui.documentation.DemokitTreeItem
@{DEMOKIT_DISPLAY_TOGGLES}          apiMaster--includeDeprecated    apiMaster--includeExperimental

# --- Fiche d'API : rubriques et tables de documentation -----------------------
${DEMOKIT_SECTION_TYPE}             sap.uxap.ObjectPageSection
${DEMOKIT_SECTION_PROPERTIES}       controlproperties
${DEMOKIT_DOC_TABLE_TYPE}           sap.ui.documentation.LightTable
${DEMOKIT_DOC_ROW_AGGREGATION}      rows
${DEMOKIT_DOC_HEADERS_PROPERTY}     columnTitles
${DEMOKIT_DOC_NAME_KEY}             name

# --- Thème : lu sur le runtime, jamais sur le menu ----------------------------
# Aucune entrée de thème ne porte `selected=True`, pas même celle du thème
# appliqué : le menu ne dit pas le thème courant. Le thème se lit donc par
# `Get Ui5 Theme` (clé technique, locale-safe), la classe `sapUiTheme-*` du
# document étant devenue une affaire de bibliothèque.
&{DEMOKIT_THEME_KEYS}               sap_horizon=light    sap_horizon_dark=dark
...                                 sap_horizon_hcb=hcb    sap_horizon_hcw=hcw
${DEMOKIT_ALTERNATE_THEME_KEY}      dark

# --- Échantillon exécuté : une iframe de même origine, à id STABLE ------------
${DEMOKIT_SAMPLE_FRAME}             iframe[id="sampleFrame"]
${DEMOKIT_SAMPLE_FRAME_ID}          sampleFrame
# L'ancre du shell qui prouve l'étanchéité de portée : présente dehors,
# absente dedans.
${DEMOKIT_SHELL_ANCHOR}             apiMasterTab

# --- Familles d'anomalies connues de la cible ---------------------------------
# Classer, jamais compter : le nombre croît avec la navigation. Les marqueurs
# sont des ORIGINES techniques, pas des textes de message (ceux du navigateur
# suivent sa propre langue).
@{DEMOKIT_THIRD_PARTY_HOSTS}        consent.trustarc.com    people.wdf.sap.corp
...                                 secure.adnxs.com    doubleclick.net
# INVENTAIRE des ressources statiques que le SDK demande et ne sert pas, en
# minuscules (l'appariement se fait sur la forme abaissée du texte et de
# l'origine). C'est un inventaire déclaré et non un motif attrape-tout : une
# ressource manquante de plus sort en anomalie NON CLASSÉE et fait échouer le
# scénario de diagnostic, ce qui est exactement l'effet voulu.
@{DEMOKIT_MISSING_SDK_RESOURCES}    jquery.ui.button.css    jquery.ui.theme.css
...                                 sdk/samples/component-preload.js
${DEMOKIT_RUNTIME_WARNING_MARKER}    [FUTURE FATAL]
${DEMOKIT_MAX_LOG}                  ${300}
@{DEMOKIT_ANOMALY_TYPES}            error    warning    assert

# --- État relevé au setup, restauré au teardown -------------------------------
${DEMOKIT_INITIAL_THEME}            ${EMPTY}
&{DEMOKIT_INITIAL_TOGGLES}          # rempli par `Memoriser L Etat Initial Du Demo Kit`


*** Keywords ***
# =============================================================================
# Ouverture, état initial, restauration
# =============================================================================

Ouvrir Le Demo Kit
    [Documentation]    Ouvre un navigateur VISIBLE par défaut, une page sur le
    ...    Demo Kit, attend le runtime, accepte le consentement puis attend le
    ...    repos. Le mode visible est une exigence de la campagne : elle est
    ...    faite pour être regardée pendant qu'elle s'exécute. La variable
    ...    `${DEMOKIT_HEADLESS}` reste surchargeable en ligne de commande pour
    ...    une exécution non surveillée.
    New Browser    ${DEMOKIT_BROWSER}    headless=${DEMOKIT_HEADLESS}
    New Context    viewport=${DEMOKIT_VIEWPORT}
    New Page    ${DEMOKIT_URL}
    Attendre Le Runtime Du Demo Kit
    Accepter Le Consentement Cookies
    Attendre Le Repos Du Demo Kit

Accepter Le Consentement Cookies
    [Documentation]    ATTEND la bannière tierce pendant `${budget}`, l'accepte
    ...    si elle paraît, et n'échoue pas si elle ne paraît jamais :
    ...    IDEMPOTENT, donc appelable sur toute page.
    ...
    ...    L'attente n'est pas un excès de prudence : la bannière est servie par
    ...    un tiers et arrive APRÈS le runtime UI5, donc un comptage immédiat
    ...    rend 0 et le test croit n'avoir rien à accepter, juste avant qu'un
    ...    overlay ne se pose au centre de la fenêtre et n'intercepte tous les
    ...    clics suivants. Son absence est légitime dans un contexte où le
    ...    consentement a déjà été donné, d'où le budget court et la tolérance.
    ...
    ...    La bannière vit hors du runtime UI5 (absente de l'arbre UI5 comme de
    ...    la carte des cibles) : c'est le seul geste de cette campagne qui
    ...    passe par le moteur `dom`.
    [Arguments]    ${budget}=${DEMOKIT_CONSENT_TIMEOUT}
    ${apparue}=    Run Keyword And Return Status    Wait Until Keyword Succeeds
    ...    ${budget}    ${DEMOKIT_POLL}    La Banniere De Consentement Doit Etre Presente
    IF    not ${apparue}
        Log    Aucune bannière de consentement dans le budget ${budget} : rien à accepter.
        RETURN
    END
    Click Dom Element    css=${DEMOKIT_CONSENT_BUTTON}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Banniere De Consentement Doit Avoir Disparu

La Banniere De Consentement Doit Etre Presente
    [Documentation]    Assertion sondable d'APPARITION de la bannière tierce.
    ${present}=    Get Dom Match Count    css=${DEMOKIT_CONSENT_BUTTON}
    Should Be True    ${present} > 0
    ...    msg=La bannière de consentement n'est pas (encore) rendue.

La Banniere De Consentement Doit Avoir Disparu
    [Documentation]    Assertion : plus aucun bouton de consentement dans la
    ...    page. Sondée, la bannière se retirant avec une animation.
    ${present}=    Get Dom Match Count    css=${DEMOKIT_CONSENT_BUTTON}
    Should Be Equal As Integers    ${present}    0
    ...    msg=La bannière de consentement est toujours présente : elle intercepte les clics de toute la campagne.

Attendre Le Runtime Du Demo Kit
    [Documentation]    Attend que le moteur UI5 soit chargé ET inactif, en
    ...    sondant le prédicat de la bibliothèque. Le budget est celui de la
    ...    campagne, pas une attente fixe (convention 2).
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Ui5 Runtime Should Be Ready

Attendre Le Repos Du Demo Kit
    [Documentation]    Attend le repos RÉSEAU de la page. Utile après une
    ...    navigation qui charge des données, INUTILE après un geste purement
    ...    local (filtre, bascule, suggestions, retour arrière) : mesuré, la
    ...    main revient instantanément et le témoin n'est alors pas le réseau
    ...    mais le contrôle attendu.
    Wait For Ui5 Idle    ${DEMOKIT_TIMEOUT}

Memoriser L Etat Initial Du Demo Kit
    [Documentation]    Suite Setup : relève le thème appliqué et l'état de
    ...    chaque bascule d'affichage, publiés en variables de suite. C'est ce
    ...    relevé, et lui seul, qui rend la restauration possible sur toutes les
    ...    branches, échec compris.
    ${theme}=    Lire Le Theme Applique
    Set Suite Variable    ${DEMOKIT_INITIAL_THEME}    ${theme}
    Memoriser Les Bascules D Affichage
    Log    État initial du Demo Kit : thème appliqué ${theme}, bascules ${DEMOKIT_INITIAL_TOGGLES}

Memoriser Les Bascules D Affichage
    [Documentation]    Relève l'état des bascules d'affichage RENDUES et le
    ...    publie en variable de suite, sans écraser un relevé précédent.
    ...
    ...    Le relevé est fait ici et pas seulement au Suite Setup parce que ces
    ...    cases n'existent QUE dans le panneau maître de la Référence de l'API
    ...    (mesuré : zéro correspondance sur l'accueil, où le setup ouvre la
    ...    campagne). Un état jamais relevé rendrait le teardown incapable de
    ...    restaurer quoi que ce soit, et il le ferait en silence : le scénario
    ...    qui touche ces cases appelle donc ce keyword avant d'y toucher.
    ${etats}=    Create Dictionary    &{DEMOKIT_INITIAL_TOGGLES}
    FOR    ${bascule}    IN    @{DEMOKIT_DISPLAY_TOGGLES}
        ${connue}=    Evaluate    $bascule in $etats
        IF    ${connue}    CONTINUE
        ${present}=    Get Ui5 Match Count    idSuffix=${bascule}
        IF    ${present} > 0
            ${valeur}=    Lire La Bascule D Affichage    ${bascule}
            Set To Dictionary    ${etats}    ${bascule}=${valeur}
        END
    END
    Set Suite Variable    &{DEMOKIT_INITIAL_TOGGLES}    &{etats}
    RETURN    ${etats}

Ramener Le Demo Kit A Son Etat De Reference
    [Documentation]    Test Teardown : referme ce qui a été ouvert et remet en
    ...    état ce qui a été touché, sans jamais faire échouer le teardown
    ...    lui-même. Chaque geste est indépendant des autres, un test ayant pu
    ...    s'arrêter n'importe où.
    Run Keyword And Ignore Error    Sortir De Toute Iframe
    Run Keyword And Ignore Error    Fermer Les Pages Supplementaires
    Run Keyword And Ignore Error    Fermer Les Popups Ouverts
    Run Keyword And Ignore Error    Vider Le Champ    ${DEMOKIT_SEARCH_FIELD}
    Run Keyword And Ignore Error    Vider Le Champ    ${DEMOKIT_API_FILTER}
    Run Keyword And Ignore Error    Restaurer Les Bascules D Affichage
    Run Keyword And Ignore Error    Restaurer Le Theme Initial

Clore La Campagne Demo Kit
    [Documentation]    Suite Teardown : remet la cible en état puis ferme le
    ...    navigateur, MÊME sur échec. Une cible publique ne garde rien d'un
    ...    run à l'autre, mais le navigateur, lui, resterait ouvert.
    Run Keyword And Ignore Error    Ramener Le Demo Kit A Son Etat De Reference
    Close Browser    ALL

# =============================================================================
# Perception
# =============================================================================

Le Demo Kit Doit Etre Percu
    [Documentation]    Verdict de perception d'ouverture : runtime présent,
    ...    page mono-technologie UI5 (aucun hôte Web Component, aucun élément
    ...    WebGUI, aucune frame), moteur `role` recommandé, et un plancher de
    ...    contrôles rendus. La VERSION et la LANGUE sont journalisées, jamais
    ...    assertées : la première bouge avec le SDK, la seconde a changé en
    ...    cours de run sur cette cible.
    ${compo}=    Get Page Composition
    Should Be True    ${compo}[ui5_runtime]
    ...    msg=Aucun runtime UI5 sur la page du Demo Kit : la cible n'est pas celle attendue.
    Should Not Be Empty    ${compo}[ui5_version]
    ...    msg=Le runtime UI5 ne déclare aucune version.
    Should Be Equal As Integers    ${compo}[wc_hosts]    0
    ...    msg=Des hôtes Web Components sont apparus sur cette page : la composition a changé.
    Should Be Equal As Integers    ${compo}[webgui_elements]    0
    ...    msg=Des éléments WebGUI sont apparus sur cette page : la composition a changé.
    Should Be Empty    ${compo}[frames]
    ...    msg=L'accueil du Demo Kit ne doit porter aucune iframe.
    List Should Contain Value    ${compo}[engines]    role
    ...    msg=Le moteur role n'est plus recommandé sur cette page : ${compo}[engines]
    Should Be True    ${compo}[ui5_controls] >= ${DEMOKIT_MIN_CONTROLS}
    ...    msg=Seulement ${compo}[ui5_controls] contrôles rendus, sous le plancher ${DEMOKIT_MIN_CONTROLS} : la page n'est pas complètement construite.
    ${langues}=    Get Page Languages
    Log    Demo Kit perçu : SAPUI5 ${compo}[ui5_version], ${compo}[ui5_controls] contrôles, moteurs ${compo}[engines], langue servie ${langues} (journalisée, jamais assertée).
    RETURN    ${compo}

Percevoir La Composition Courante
    [Documentation]    Composition technologique de la portée COURANTE (page ou
    ...    frame empilée) : runtime, version, nombre de contrôles, hôtes de
    ...    composants web, éléments WebGUI, frames et moteurs recommandés.
    ${compo}=    Get Page Composition
    RETURN    ${compo}

Journaliser La Langue Servie
    [Documentation]    Écrit la langue du document et celle du navigateur dans
    ...    le log. Explique un log, ne fait jamais foi : la langue de cette
    ...    cible a changé entre deux pages du même run.
    ${langues}=    Get Page Languages
    Log    Langue servie : ${langues}
    RETURN    ${langues}

# =============================================================================
# Navigation par clés techniques
# =============================================================================

Lister Les Cles De Navigation
    [Documentation]    Clés techniques des onglets de la barre de navigation,
    ...    lues dans l'agrégation du conteneur d'onglets (donc DÉCOUVERTES, pas
    ...    énumérées ici). Chaque clé est exactement la route de hash de sa
    ...    section : c'est l'ancre locale-indépendante de toute la navigation.
    ${onglets}=    Get Ui5 Aggregation Info    items    idSuffix=${DEMOKIT_NAV_HEADER}
    Should Not Be Empty    ${onglets}
    ...    msg=Le conteneur d'onglets ne porte aucun onglet : la barre de navigation n'est pas rendue.
    ${cles}=    Evaluate    [o['properties'].get('key', '') for o in $onglets]
    RETURN    ${cles}

Ouvrir La Section
    [Documentation]    Clique l'onglet portant la clé technique `${cle}` puis
    ...    attend que les DEUX témoins concordent. Attention : cliquer l'onglet
    ...    déjà sélectionné n'est pas neutre, cela ramène à la racine de la
    ...    section (exploitable pour revenir à un état connu).
    [Arguments]    ${cle}
    ${motif}=    Motif Exact    ${cle}
    Click Ui5 Control    controlType=${DEMOKIT_TAB_TYPE}    properties={'key': '${motif}'}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Section Active Doit Etre    ${cle}

La Section Active Doit Etre
    [Documentation]    Les DEUX témoins de la section active, et ils ne se
    ...    remplacent pas : le fragment d'URL (ce que le routeur a fait) et la
    ...    clé sélectionnée du conteneur d'onglets (ce que le shell affiche).
    [Arguments]    ${cle}
    ${route}=    Get From Dictionary    ${DEMOKIT_ROUTE_BY_KEY}    ${cle}    default=/${cle}
    ${emplacement}=    Get Page Location
    Should Start With    ${emplacement}[fragment]    ${route}
    ...    msg=Le fragment d'URL est ${emplacement}[fragment], attendu commençant par ${route}.
    ${selection}=    Get Ui5 Property    selectedKey    idSuffix=${DEMOKIT_NAV_HEADER}
    Should Be Equal    ${selection}    ${cle}
    ...    msg=Le conteneur d'onglets déclare la section ${selection}, attendue ${cle} : les deux témoins se contredisent.

# =============================================================================
# Recherche globale
# =============================================================================

Rechercher Dans Le Demo Kit
    [Documentation]    Saisit `${terme}` dans le champ de recherche global et
    ...    constate l'ouverture du popover de suggestions SUR LA PILE DE
    ...    POPUPS. Retourne l'identifiant de ce popover, qui sert de PORTÉE aux
    ...    lectures suivantes : il est généré, donc découvert ici et jamais
    ...    écrit dans un fichier. La saisie passe par de vraies frappes : poser
    ...    la valeur ne déclenche pas les suggestions.
    [Arguments]    ${terme}
    Saisir Dans Le Champ    ${DEMOKIT_SEARCH_FIELD}    ${terme}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Pile De Popups Doit Avoir    ${1}
    ${pile}=    Get Ui5 Open Popups
    RETURN    ${pile}[-1][id]

Lire Les Suggestions
    [Documentation]    Titres des entrées de résultat rendues dans la portée du
    ...    popover, dans l'ordre du registre. Les libellés de catégorie sont
    ...    traduits ; les titres de résultat, eux, portent des identifiants
    ...    techniques non traduits.
    [Arguments]    ${popover}
    ${titres}=    Get Ui5 Properties    title    controlType=${DEMOKIT_SUGGESTION_TYPE}
    ...    containedIn=${popover}
    RETURN    ${titres}

Compter Les En Tetes De Groupe
    [Documentation]    Nombre de lignes de catégorie du popover de suggestions.
    [Arguments]    ${popover}
    ${nb}=    Get Ui5 Match Count    controlType=${DEMOKIT_SUGGESTION_GROUP_TYPE}
    ...    containedIn=${popover}
    RETURN    ${nb}

Les Suggestions Doivent Proposer
    [Documentation]    Assertion locale-indépendante : au moins une entrée dont
    ...    le titre porte l'identifiant technique cherché. Aucun libellé
    ...    traduit n'entre dans le verdict.
    [Arguments]    ${popover}    ${nom_qualifie}
    ${titres}=    Lire Les Suggestions    ${popover}
    # Le filtre passe par `filter` et non par une compréhension : une variable
    # Robot référencée par `$nom` n'est pas visible depuis la portée d'une
    # compréhension (attrapé au premier run live).
    ${porteurs}=    Evaluate    list(filter(lambda t, n=$nom_qualifie: n in t, $titres))
    Should Not Be Empty    ${porteurs}
    ...    msg=Aucune suggestion ne porte l'identifiant technique ${nom_qualifie} ; titres proposés : ${titres}

Ouvrir La Suggestion De Classe
    [Documentation]    Ouvre l'entrée de suggestion qui est la FICHE DE CLASSE
    ...    de `${nom_qualifie}`, désignée par le préfixe technique de son titre
    ...    (`<nom qualifié> (class)`), puis constate l'arrivée sur la fiche.
    ...
    ...    L'entrée est atteinte par son identifiant relevé À L'INSTANT dans la
    ...    même portée et dans le même ordre que les titres : un identifiant
    ...    généré ne s'écrit pas, il se découvre.
    [Arguments]    ${popover}    ${nom_qualifie}
    ${titres}=    Lire Les Suggestions    ${popover}
    ${identifiants}=    Get Ui5 Ids    controlType=${DEMOKIT_SUGGESTION_TYPE}    containedIn=${popover}
    ${prefixe}=    Set Variable    ${nom_qualifie}${DEMOKIT_SUGGESTION_CLASS_SUFFIX}
    ${rang}=    Set Variable    ${-1}
    FOR    ${indice}    ${titre}    IN ENUMERATE    @{titres}
        ${debute}=    Evaluate    $titre.startswith($prefixe)
        IF    ${debute}
            ${rang}=    Set Variable    ${indice}
            BREAK
        END
    END
    Should Not Be Equal As Integers    ${rang}    -1
    ...    msg=Aucune suggestion de fiche de classe pour ${nom_qualifie} ; titres proposés : ${titres}
    Click Ui5 Control    id=${identifiants}[${rang}]
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Fiche Affichee Doit Etre    ${nom_qualifie}

# =============================================================================
# Fiches d'API : liens profonds, historique, rubriques
# =============================================================================

Ouvrir La Fiche D Api
    [Documentation]    Navigue vers la fiche d'API de `${nom_qualifie}` dans la
    ...    page courante, puis constate l'arrivée.
    ...
    ...    **Naviguer vers la fiche DÉJÀ affichée n'est pas un geste neutre**
    ...    (mesuré live le 2026-08-30, et c'est ce qui a fait échouer le premier
    ...    run) : demander l'URL courante à l'identique est une navigation de
    ...    fragment sans changement, donc le routeur ne re-résout rien, mais le
    ...    titre du document est RÉINITIALISÉ au titre générique de la section
    ...    et n'en revient jamais. Le rechargement, lui, reconstruit
    ...    l'application et rétablit le titre. Ce keyword choisit donc son geste
    ...    selon l'état courant, ce qui le rend indépendant du test qui l'a
    ...    précédé : c'est la condition de la rejouabilité.
    [Arguments]    ${nom_qualifie}
    ${emplacement}=    Get Page Location
    ${deja}=    Evaluate    $emplacement['fragment'] == '/api/' + $nom_qualifie
    IF    ${deja}
        Reload
        Attendre Le Runtime Du Demo Kit
    ELSE
        Go To    ${DEMOKIT_URL}#/api/${nom_qualifie}
    END
    Attendre Le Repos Du Demo Kit
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Fiche Affichee Doit Etre    ${nom_qualifie}

Ouvrir Directement La Fiche D Api
    [Documentation]    Ouvre une page NEUVE directement sur l'URL profonde de la
    ...    fiche, sans jamais afficher l'accueil : c'est ce qui donne son sens
    ...    au scénario de lien profond. Le consentement est réaccepté si la
    ...    bannière reparaît (le keyword est idempotent).
    [Arguments]    ${nom_qualifie}
    New Page    ${DEMOKIT_URL}#/api/${nom_qualifie}
    Attendre Le Runtime Du Demo Kit
    Accepter Le Consentement Cookies    ${DEMOKIT_CONSENT_SHORT}
    Attendre Le Repos Du Demo Kit

Fermer Les Pages Supplementaires
    [Documentation]    Referme toute page ouverte EN PLUS de celle du setup, et
    ...    rend la main à cette dernière. Appelé par le test de lien profond et
    ...    par le teardown : un test interrompu après `Ouvrir Directement La
    ...    Fiche D Api` laisserait sinon les tests suivants travailler sur sa
    ...    page, dont l'état n'a rien de celui du setup.
    ${pages}=    Get Page Ids
    ${nombre}=    Get Length    ${pages}
    IF    ${nombre} <= 1    RETURN
    ${supplementaires}=    Evaluate    $pages[1:]
    FOR    ${page}    IN    @{supplementaires}
        Close Page    ${page}
    END
    Switch Page    ${pages}[0]

La Fiche Affichee Doit Etre
    [Documentation]    Le couple URL plus titre de document, le seul témoin
    ...    d'arrivée fiable ici. Le fragment est vérifié par APPARTENANCE :
    ...    l'application réécrit certaines routes, et comparer mot pour mot avec
    ...    l'URL demandée produirait un échec sur une navigation réussie. Le
    ...    titre, lui, est mis à jour APRÈS le fragment : les deux se sondent.
    [Arguments]    ${nom_qualifie}
    ${emplacement}=    Get Page Location
    Should Contain    ${emplacement}[fragment]    ${nom_qualifie}
    ...    msg=Le fragment d'URL est ${emplacement}[fragment], attendu portant ${nom_qualifie}.
    ${titre}=    Get Title
    Should Start With    ${titre}    ${nom_qualifie}
    ...    msg=Le titre du document est « ${titre} », attendu commençant par ${nom_qualifie}.

Revenir En Arriere Dans Le Demo Kit
    [Documentation]    Retour arrière du navigateur, suivi de l'attente d'un
    ...    témoin de RENDU et jamais d'un repos réseau : mesuré, le retour
    ...    arrière n'émet aucune requête (les données sont déjà en cache), donc
    ...    l'attente de repos rend la main immédiatement et ne prouve rien.
    [Arguments]    ${nom_qualifie}
    Go Back
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Fiche Affichee Doit Etre    ${nom_qualifie}

Compter Les Rubriques De La Fiche
    [Documentation]    Nombre de rubriques de documentation de la fiche
    ...    affichée (vue d'objet). Sert de témoin de fiche construite.
    ${nb}=    Get Ui5 Match Count    controlType=${DEMOKIT_SECTION_TYPE}
    RETURN    ${nb}

L Etat Doit Etre Restitue Depuis Le Lien Profond
    [Documentation]    Verdict du lien profond : le titre du document nomme
    ...    l'entité, la section active est la Référence de l'API bien que
    ...    l'accueil n'ait jamais été affiché (le cœur du scénario), l'arbre
    ...    latéral est peuplé et déplié jusqu'à l'entité, et la fiche porte au
    ...    moins une rubrique.
    [Arguments]    ${nom_qualifie}    ${cle_section}
    La Fiche Affichee Doit Etre    ${nom_qualifie}
    La Section Active Doit Etre    ${cle_section}
    ${noeuds}=    Compter Les Noeuds De L Arbre D Api
    Should Be True    ${noeuds} > 0
    ...    msg=L'arbre latéral de la Référence de l'API est vide après un accès par lien profond.
    ${vise}=    Compter Les Noeuds D Api Nommes    ${nom_qualifie}
    Should Be Equal As Integers    ${vise}    1
    ...    msg=L'arbre ne porte pas exactement un nœud de nom qualifié ${nom_qualifie} (${vise}) : il n'est pas déplié jusqu'à l'entité visée.
    ${rubriques}=    Compter Les Rubriques De La Fiche
    Should Be True    ${rubriques} > 0
    ...    msg=La fiche de ${nom_qualifie} ne porte aucune rubrique de documentation.

# =============================================================================
# Arbre de la Référence de l'API
# =============================================================================

Compter Les Noeuds De L Arbre D Api
    [Documentation]    Nombre de nœuds rendus DANS l'arbre de la Référence de
    ...    l'API. La portée n'est pas un détail : le maître de la Documentation
    ...    reste rendu à côté et ses nœuds sont du même type, un comptage global
    ...    les ajoute (mesuré 380 contre 371) et leurs `target` sont des
    ...    empreintes de rubrique, pas des noms qualifiés.
    ${nb}=    Get Ui5 Match Count    controlType=${DEMOKIT_TREE_ITEM_TYPE}
    ...    containedIn=${DEMOKIT_API_TREE}
    RETURN    ${nb}

Lister Les Cibles De L Arbre D Api
    [Documentation]    Noms pleinement qualifiés portés par les nœuds de
    ...    l'arbre de l'API : la meilleure ancre métier de cet arbre, et une
    ...    donnée technique donc indépendante de la langue.
    ${cibles}=    Get Ui5 Properties    target    controlType=${DEMOKIT_TREE_ITEM_TYPE}
    ...    containedIn=${DEMOKIT_API_TREE}
    RETURN    ${cibles}

Compter Les Noeuds D Api Nommes
    [Documentation]    Nombre de nœuds dont le nom qualifié est EXACTEMENT
    ...    `${nom_qualifie}`. L'ancrage exact est obligatoire : l'appariement
    ...    de propriétés se fait par sous-chaîne, et les préfixes communs sont
    ...    la règle dans ce catalogue.
    [Arguments]    ${nom_qualifie}
    ${motif}=    Motif Exact    ${nom_qualifie}
    ${nb}=    Get Ui5 Match Count    controlType=${DEMOKIT_TREE_ITEM_TYPE}
    ...    containedIn=${DEMOKIT_API_TREE}    properties={'target': '${motif}'}
    RETURN    ${nb}

Filtrer L Arbre D Api
    [Documentation]    Saisit `${terme}` dans le champ de filtre du panneau
    ...    maître et attend ACTIVEMENT la réduction de l'arbre. Le filtre est
    ...    différé : mesuré, le comptage lu juste après la frappe valait encore
    ...    371 et la réduction à 4 est arrivée ensuite. Retourne le comptage
    ...    filtré.
    [Arguments]    ${terme}
    ${avant}=    Compter Les Noeuds De L Arbre D Api
    Saisir Dans Le Champ    ${DEMOKIT_API_FILTER}    ${terme}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    L Arbre D Api Doit Compter Moins De    ${avant}
    ${apres}=    Compter Les Noeuds De L Arbre D Api
    Log    Filtre « ${terme} » : ${avant} nœuds avant, ${apres} après.
    RETURN    ${apres}

Vider Le Filtre D Arbre
    [Documentation]    Remet le filtre à vide et attend l'élargissement de
    ...    l'arbre. L'assertion porte sur la relation, jamais sur le retour à la
    ...    mesure initiale : la navigation faite entre-temps a changé l'état de
    ...    dépliage.
    ${avant}=    Compter Les Noeuds De L Arbre D Api
    Vider Le Champ    ${DEMOKIT_API_FILTER}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    L Arbre D Api Doit Compter Plus De    ${avant}
    ${apres}=    Compter Les Noeuds De L Arbre D Api
    RETURN    ${apres}

L Arbre D Api Doit Compter Moins De
    [Documentation]    Assertion sondable : l'arbre porte strictement moins de
    ...    `${reference}` nœuds.
    [Arguments]    ${reference}
    ${nb}=    Compter Les Noeuds De L Arbre D Api
    Should Be True    ${nb} < ${reference}
    ...    msg=L'arbre porte ${nb} nœuds, attendu strictement moins de ${reference}.

L Arbre D Api Doit Compter Plus De
    [Documentation]    Assertion sondable : l'arbre porte strictement plus de
    ...    `${reference}` nœuds.
    [Arguments]    ${reference}
    ${nb}=    Compter Les Noeuds De L Arbre D Api
    Should Be True    ${nb} > ${reference}
    ...    msg=L'arbre porte ${nb} nœuds, attendu strictement plus de ${reference}.

Ouvrir Le Noeud D Api
    [Documentation]    Clique le nœud d'arbre dont le nom qualifié est
    ...    EXACTEMENT `${nom_qualifie}`, puis constate l'arrivée sur sa fiche.
    [Arguments]    ${nom_qualifie}
    ${vise}=    Compter Les Noeuds D Api Nommes    ${nom_qualifie}
    Should Be Equal As Integers    ${vise}    1
    ...    msg=L'ancrage exact sur ${nom_qualifie} rend ${vise} correspondance(s) : le nœud visé n'est pas identifiable sans ambiguïté.
    ${motif}=    Motif Exact    ${nom_qualifie}
    Click Ui5 Control    controlType=${DEMOKIT_TREE_ITEM_TYPE}
    ...    containedIn=${DEMOKIT_API_TREE}    properties={'target': '${motif}'}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Fiche Affichee Doit Etre    ${nom_qualifie}

Les Noeuds Restants Doivent Porter Le Terme
    [Documentation]    Verdict de filtrage : tout nœud restant est soit un
    ...    ancêtre de namespace (un préfixe du nom d'un autre nœud restant),
    ...    soit porteur du terme filtré dans son nom qualifié.
    [Arguments]    ${cibles}    ${terme}
    ${intrus}=    Create List
    FOR    ${cible}    IN    @{cibles}
        ${porte}=    Evaluate    $terme.lower() in $cible.lower()
        IF    ${porte}    CONTINUE
        ${ancetre}=    Evaluate
        ...    any(map(lambda o, c=$cible: o != c and o.startswith(c + '.'), $cibles))
        IF    not ${ancetre}    Append To List    ${intrus}    ${cible}
    END
    Should Be Empty    ${intrus}
    ...    msg=Des nœuds restent alors qu'ils ne portent ni le terme « ${terme} » ni de descendant dans l'arbre filtré : ${intrus}

# =============================================================================
# Bascules d'affichage du panneau maître
# =============================================================================

Lire La Bascule D Affichage
    [Documentation]    État booléen de la case d'affichage désignée par son
    ...    suffixe d'identifiant.
    [Arguments]    ${bascule}
    ${etat}=    Get Ui5 Property    selected    idSuffix=${bascule}
    RETURN    ${etat}

Basculer L Affichage
    [Documentation]    Clique la case et constate l'INVERSION de sa propriété.
    ...    La propriété du contrôle est le seul témoin de la bascule : le
    ...    comptage de l'arbre en est une conséquence, pas une preuve.
    [Arguments]    ${bascule}
    ${avant}=    Lire La Bascule D Affichage    ${bascule}
    ${attendu}=    Evaluate    not $avant
    Click Ui5 Control    idSuffix=${bascule}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Bascule D Affichage Doit Valoir    ${bascule}    ${attendu}
    RETURN    ${attendu}

La Bascule D Affichage Doit Valoir
    [Documentation]    Assertion sondable sur la propriété de la case.
    [Arguments]    ${bascule}    ${attendu}
    ${etat}=    Lire La Bascule D Affichage    ${bascule}
    Should Be Equal    ${etat}    ${attendu}
    ...    msg=La bascule ${bascule} vaut ${etat}, attendue ${attendu}.

Restaurer Les Bascules D Affichage
    [Documentation]    Teardown : remet chaque case dans l'état relevé au setup.
    ...    La remise en état se constate sur la PROPRIÉTÉ, jamais sur le retour
    ...    du comptage de l'arbre à sa valeur initiale : mesuré, ce comptage ne
    ...    revient pas exactement à sa valeur d'origine sur un système pourtant
    ...    parfaitement restauré (l'état de dépliage a bougé).
    FOR    ${bascule}    ${attendu}    IN    &{DEMOKIT_INITIAL_TOGGLES}
        ${present}=    Get Ui5 Match Count    idSuffix=${bascule}
        IF    ${present} > 0
            ${etat}=    Lire La Bascule D Affichage    ${bascule}
            IF    $etat != $attendu
                Basculer L Affichage    ${bascule}
            END
        END
    END

# =============================================================================
# Tables de documentation d'une fiche d'API
# =============================================================================

Compter Les Tables De Doc De La Rubrique
    [Documentation]    Nombre de tables de documentation rendues dans la
    ...    rubrique `${rubrique}`. Ces tables ont des ids GÉNÉRÉS : elles
    ...    s'adressent par leur rubrique conteneuse, jamais par leur id.
    [Arguments]    ${rubrique}
    ${nb}=    Get Ui5 Match Count    controlType=${DEMOKIT_DOC_TABLE_TYPE}    containedIn=${rubrique}
    RETURN    ${nb}

Lire Les En Tetes De Table De Doc
    [Documentation]    En-têtes de colonnes de la table de la rubrique
    ...    `${rubrique}`. C'est une PROPRIÉTÉ du contrôle (une liste de
    ...    chaînes), pas une agrégation : les deux voies de lecture de ce
    ...    contrôle ne sont pas interchangeables.
    [Arguments]    ${rubrique}
    ${entetes}=    Get Ui5 Property    ${DEMOKIT_DOC_HEADERS_PROPERTY}
    ...    controlType=${DEMOKIT_DOC_TABLE_TYPE}    containedIn=${rubrique}
    RETURN    ${entetes}

Lire Les Noms Techniques De Table De Doc
    [Documentation]    Noms techniques documentés par la table de la rubrique
    ...    `${rubrique}`, extraits du CONTEXTE DE LIAISON de chaque ligne et
    ...    non de son rendu : c'est ce qui les rend indépendants de la langue
    ...    et de l'affichage.
    ...
    ...    POURQUOI PAS `Read Ui5 Table` (convention 12, relevé live le
    ...    2026-08-30, corrigé dans `src/` le même jour) : la lecture générique
    ...    rendait une liste VIDE sans échouer sur ce contrôle, alors que le
    ...    sélecteur résout exactement 1 correspondance et que le contrôle
    ...    porte bien ses lignes. C'était le profil « vert et faux » type, un
    ...    test qui croit avoir lu la table. Le keyword échoue désormais en
    ...    nommant le type et en renvoyant ici ; la voie du registre reste la
    ...    voie CORRECTE pour cette table, qui ne suit pas le contrat
    ...    `sap.m.Table` / `sap.ui.table.Table`.
    [Arguments]    ${rubrique}
    ${lignes}=    Get Ui5 Aggregation Info    ${DEMOKIT_DOC_ROW_AGGREGATION}
    ...    controlType=${DEMOKIT_DOC_TABLE_TYPE}    containedIn=${rubrique}
    ${noms}=    Evaluate
    ...    [l['binding']['object'].get('${DEMOKIT_DOC_NAME_KEY}', '') for l in $lignes if l.get('binding')]
    RETURN    ${noms}

Lire Les Proprietes Du Controle Vivant
    [Documentation]    Clés de propriétés d'une instance RÉELLEMENT rendue de
    ...    `${controlType}` dans la page, lues au registre. Le contrôle vivant
    ...    porte aussi les propriétés héritées, que la table des propriétés
    ...    propres ne documente pas : l'inclusion ne vaut donc que dans un sens.
    [Arguments]    ${controlType}
    ${fiches}=    Get Ui5 Control Info    controlType=${controlType}
    Should Not Be Empty    ${fiches}
    ...    msg=Aucune instance rendue de ${controlType} dans la page : l'invariant ne peut pas être confronté au contrôle vivant.
    ${cles}=    Evaluate    sorted($fiches[0]['properties'].keys())
    RETURN    ${cles}

La Doc Doit Etre Incluse Dans Le Controle Vivant
    [Documentation]    Invariant central du scénario de documentation : toute
    ...    propriété documentée existe sur le contrôle vivant. L'échec NOMME les
    ...    propriétés documentées absentes.
    [Arguments]    ${documentees}    ${vivantes}
    ${absentes}=    Evaluate    sorted(set($documentees) - set($vivantes))
    Should Be Empty    ${absentes}
    ...    msg=Des propriétés documentées n'existent pas sur le contrôle vivant : ${absentes}

# =============================================================================
# Menu Options, cascade de popovers, dialogue
# =============================================================================

Ouvrir Le Menu Options
    [Documentation]    Ouvre le menu Options par son bouton d'en-tête et
    ...    constate l'ouverture sur la PILE DE POPUPS. La présence des entrées
    ...    ne prouverait rien : menu refermé, une entrée compte encore une
    ...    correspondance, avec un rectangle nul.
    ${profondeur}=    Lire La Profondeur De La Pile De Popups
    ${attendue}=    Evaluate    $profondeur + 1
    Click Ui5 Control    idSuffix=${DEMOKIT_MENU_BUTTON}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Pile De Popups Doit Avoir    ${attendue}

Ouvrir L Entree De Menu
    [Documentation]    Clique l'entrée de menu portant la clé technique
    ...    `${cle}`, dans la portée du popup ouvert le plus récent. La clé et
    ...    l'icône sont les seules ancres : les libellés sont traduits et les
    ...    identifiants sont générés (mesurés `__item10` à `__item18` sur une
    ...    page, `__item16` à `__item24` sur une autre).
    [Arguments]    ${cle}
    ${motif}=    Motif Exact    ${cle}
    ${pile}=    Get Ui5 Open Popups
    Should Not Be Empty    ${pile}
    ...    msg=Aucun popup ouvert : l'entrée de menu ${cle} n'est pas atteignable.
    Click Ui5 Control    controlType=${DEMOKIT_MENU_ITEM_TYPE}
    ...    containedIn=${pile}[-1][id]    properties={'key': '${motif}'}

Lister Les Cles Du Menu Ouvert
    [Documentation]    Clés techniques des entrées rendues dans le popup ouvert
    ...    le plus récent. La portée est indispensable : ouvert, un sous-menu
    ...    fait cohabiter ses clés avec celles du menu racine dans un comptage
    ...    global (mesuré 9 clés pour 4 plus 5).
    ${pile}=    Get Ui5 Open Popups
    Should Not Be Empty    ${pile}
    ...    msg=Aucun popup ouvert : il n'y a pas de menu dont lire les clés.
    ${cles}=    Get Ui5 Properties    key    controlType=${DEMOKIT_MENU_ITEM_TYPE}
    ...    containedIn=${pile}[-1][id]
    RETURN    ${cles}

Lire La Profondeur De La Pile De Popups
    [Documentation]    Nombre de popups actuellement ouverts (dialogues et
    ...    popovers). Le témoin d'ouverture de toute cette campagne.
    ${pile}=    Get Ui5 Open Popups
    ${profondeur}=    Get Length    ${pile}
    RETURN    ${profondeur}

La Pile De Popups Doit Avoir
    [Documentation]    Assertion de profondeur de la pile de popups. Sondée par
    ...    ses appelants : mesuré, un dialogue annulé est encore dans la pile à
    ...    l'instant qui suit le clic, et le menu du thème se referme lui aussi
    ...    avec un temps de retard.
    [Arguments]    ${profondeur}
    ${pile}=    Get Ui5 Open Popups
    Length Should Be    ${pile}    ${profondeur}
    ...    msg=La pile de popups porte ${{ len($pile) }} entrée(s), attendu ${profondeur} : ${pile}

La Pile De Popups Doit Etre Vide
    [Documentation]    Assertion sondable : plus aucun popup ouvert.
    La Pile De Popups Doit Avoir    ${0}

Attendre La Profondeur De Pile
    [Documentation]    Attente ACTIVE d'une profondeur de pile de popups.
    [Arguments]    ${profondeur}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Pile De Popups Doit Avoir    ${profondeur}

Lire Le Dialogue Ouvert
    [Documentation]    Fiche du dialogue ouvert le plus récent
    ...    (`{id, controlType, kind, buttons, ...}`), ou échec si aucun n'est
    ...    ouvert.
    ${pile}=    Get Ui5 Open Popups
    ${dialogues}=    Evaluate    [p for p in $pile if p.get('kind') == 'dialog']
    Should Not Be Empty    ${dialogues}
    ...    msg=Aucun dialogue ouvert ; pile de popups : ${pile}
    RETURN    ${dialogues}[-1]

Lire Les Roles Des Boutons Du Dialogue
    [Documentation]    Types (rôles) des boutons du dialogue des paramètres,
    ...    dans l'ordre du registre. Leurs identifiants sont générés et leurs
    ...    libellés traduits : le rôle est ce qui les distingue, la position ce
    ...    qui les atteint.
    ${roles}=    Get Ui5 Properties    type    controlType=sap.m.Button
    ...    containedIn=${DEMOKIT_SETTINGS_DIALOG}
    RETURN    ${roles}

Compter Le Selecteur De Langue
    [Documentation]    Nombre de sélecteurs de langue rendus dans le dialogue
    ...    des paramètres. Ce contrôle est LU, jamais actionné : mesuré, sa clé
    ...    sélectionnée est la première entrée de la liste et ne dit pas la
    ...    langue effective de l'interface.
    ${nb}=    Get Ui5 Match Count    idSuffix=${DEMOKIT_LANGUAGE_SELECT}
    RETURN    ${nb}

Annuler Le Dialogue Des Parametres
    [Documentation]    Annule le dialogue par POSITION (le rôle du bouton ne
    ...    l'atteint pas, son libellé est traduit) et constate la fermeture sur
    ...    la pile de popups. Aucun bouton de validation n'est jamais actionné :
    ...    la campagne est en lecture seule.
    Click Ui5 Dialog Button    ${DEMOKIT_DIALOG_CANCEL_POSITION}
    Attendre La Profondeur De Pile    ${0}

Fermer Les Popups Ouverts
    [Documentation]    Teardown : referme la cascade de popups éventuellement
    ...    laissée ouverte par un test interrompu. La touche d'échappement
    ...    ferme un niveau à la fois (vérifié live sur la cascade menu plus
    ...    sous-menu), et le nombre de tentatives est borné pour ne jamais
    ...    transformer un teardown en boucle.
    FOR    ${tentative}    IN RANGE    4
        ${profondeur}=    Lire La Profondeur De La Pile De Popups
        IF    ${profondeur} == 0    BREAK
        Keyboard Key    press    Escape
        Wait Until Keyword Succeeds    5s    ${DEMOKIT_POLL}
        ...    La Pile De Popups Doit Avoir Moins De    ${profondeur}
    END

La Pile De Popups Doit Avoir Moins De
    [Documentation]    Assertion sondable de décroissance de la pile de popups.
    [Arguments]    ${reference}
    ${profondeur}=    Lire La Profondeur De La Pile De Popups
    Should Be True    ${profondeur} < ${reference}
    ...    msg=La pile de popups porte encore ${profondeur} entrée(s), attendu moins de ${reference}.

# =============================================================================
# Thème
# =============================================================================

Lire Le Theme Applique
    [Documentation]    Thème réellement APPLIQUÉ, tel que le document le porte.
    ...    Chaîne vide quand aucun thème ne l'est : mesuré, il existe une
    ...    fenêtre, juste après un changement, où le document ne porte AUCUNE
    ...    classe de thème. C'est pourquoi le thème s'attend et ne se lit pas
    ...    une fois.
    ...
    ...    Depuis la correction du 2026-08-30, la lecture est celle de la
    ...    bibliothèque (`Get Ui5 Theme`), qui rend AUSSI le thème demandé :
    ...    voir `Lire Le Theme Demande`.
    ${theme}=    Get Ui5 Theme
    RETURN    ${theme}[applied]

Lire Le Theme Demande
    [Documentation]    Thème que le runtime a reçu ordre d'appliquer. Il porte
    ...    déjà la cible pendant que le thème appliqué est encore vide : c'est
    ...    la valeur qui distingue « le changement n'a pas été demandé » de
    ...    « le changement est en cours d'application ».
    ${theme}=    Get Ui5 Theme
    RETURN    ${theme}[requested]

Choisir Le Theme
    [Documentation]    Ouvre le menu Options, ouvre le sous-menu d'aspect, puis
    ...    clique l'entrée de clé technique `${cle}`. Le choix referme toute la
    ...    cascade (constaté), et l'entrée du thème courant ne se distingue par
    ...    aucune propriété : le menu ne dit pas le thème appliqué.
    [Arguments]    ${cle}
    Ouvrir Le Menu Options
    Ouvrir L Entree De Menu    ${DEMOKIT_MENU_APPEARANCE_KEY}
    Attendre La Profondeur De Pile    ${2}
    Ouvrir L Entree De Menu    ${cle}
    Attendre La Profondeur De Pile    ${0}

Le Theme Applique Doit Devenir
    [Documentation]    Attente ACTIVE du thème appliqué. Lire la classe une
    ...    seule fois juste après le clic est une course perdue : le thème
    ...    demandé porte déjà la nouvelle valeur alors que le document n'a
    ...    encore aucune classe de thème.
    [Arguments]    ${theme}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Le Theme Applique Doit Valoir    ${theme}

Le Theme Applique Doit Valoir
    [Documentation]    Assertion sondable sur le thème appliqué.
    [Arguments]    ${theme}
    ${courant}=    Lire Le Theme Applique
    Should Be Equal    ${courant}    ${theme}
    ...    msg=Le thème appliqué est « ${courant} », attendu « ${theme} ».

Le Theme Applique Ne Doit Plus Valoir
    [Documentation]    Assertion sondable de CHANGEMENT de thème, sans graver le
    ...    nom du thème d'arrivée : le scénario compare un avant et un après,
    ...    les noms de thèmes du SDK pouvant changer d'une version à l'autre.
    [Arguments]    ${theme}
    ${courant}=    Lire Le Theme Applique
    Should Not Be Empty    ${courant}
    ...    msg=Le document ne porte aucun thème appliqué : le changement est encore en cours.
    Should Not Be Equal    ${courant}    ${theme}
    ...    msg=Le thème appliqué vaut toujours « ${theme} » : le changement n'a pas eu lieu.

Cle De Theme
    [Documentation]    Clé de menu correspondant à un nom de thème appliqué.
    ...    Échec explicite sur un thème inconnu de la carte : mieux vaut nommer
    ...    la lacune que cliquer une entrée au hasard.
    [Arguments]    ${theme}
    ${cle}=    Get From Dictionary    ${DEMOKIT_THEME_KEYS}    ${theme}    default=${EMPTY}
    Should Not Be Empty    ${cle}
    ...    msg=Le thème « ${theme} » n'a pas de clé de menu connue dans ce page object : ${DEMOKIT_THEME_KEYS}
    RETURN    ${cle}

Restaurer Le Theme Initial
    [Documentation]    Teardown : ramène le thème appliqué à celui relevé au
    ...    setup, et ne fait rien s'il n'a pas bougé. S'exécute même après un
    ...    échec en plein cycle de changement.
    ${courant}=    Lire Le Theme Applique
    IF    "${courant}" != "${DEMOKIT_INITIAL_THEME}"
        ${cle}=    Cle De Theme    ${DEMOKIT_INITIAL_THEME}
        Fermer Les Popups Ouverts
        Choisir Le Theme    ${cle}
        Le Theme Applique Doit Devenir    ${DEMOKIT_INITIAL_THEME}
    END

# =============================================================================
# Échantillon exécuté dans une iframe
# =============================================================================

Ouvrir L Echantillon
    [Documentation]    Navigue vers l'exécution de l'échantillon
    ...    `${id_echantillon}` et tolère la RÉÉCRITURE de la route :
    ...    l'application transforme `#/sample/<id>/preview` en
    ...    `#/entity/<contrôle>/sample/<id>`. Le témoin d'arrivée est
    ...    l'appartenance de l'identifiant au fragment, jamais l'égalité avec
    ...    l'URL demandée.
    [Arguments]    ${id_echantillon}
    Go To    ${DEMOKIT_URL}#/sample/${id_echantillon}/preview
    Attendre Le Repos Du Demo Kit
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Le Fragment Doit Porter    ${id_echantillon}

Le Fragment Doit Porter
    [Documentation]    Assertion sondable d'appartenance au fragment d'URL.
    [Arguments]    ${marqueur}
    ${emplacement}=    Get Page Location
    Should Contain    ${emplacement}[fragment]    ${marqueur}
    ...    msg=Le fragment d'URL est ${emplacement}[fragment], attendu portant ${marqueur}.

Lister Les Iframes De La Page
    [Documentation]    Inventaire brut des iframes de la portée courante.
    ${frames}=    List Page Iframes
    RETURN    ${frames}

Entrer Dans L Iframe D Echantillon
    [Documentation]    Empile la portée de l'iframe de l'échantillon. Son id est
    ...    STABLE, contrairement aux conteneurs générés d'un launchpad : il est
    ...    donc la bonne ancre ici.
    Push Ui5 Frame    ${DEMOKIT_SAMPLE_FRAME}
    Attendre Le Runtime Du Demo Kit

Sortir De L Iframe D Echantillon
    [Documentation]    Dépile la portée de l'iframe.
    Pop Ui5 Frame

Sortir De Toute Iframe
    [Documentation]    Teardown : dépile toutes les portées de frame restantes.
    ...    Un test arrêté dans une frame laisserait la portée à l'intérieur, et
    ...    tous les tests suivants chercheraient le shell au mauvais endroit.
    ${pile}=    Get Ui5 Frame Stack
    ${profondeur}=    Get Length    ${pile}
    FOR    ${niveau}    IN RANGE    ${profondeur}
        Pop Ui5 Frame
    END

Compter L Ancre Du Shell
    [Documentation]    Nombre de correspondances de l'ancre du shell dans la
    ...    portée COURANTE : le témoin d'étanchéité, qui vaut 0 dans l'iframe de
    ...    l'échantillon et 1 dans le document hôte.
    ${nb}=    Get Ui5 Match Count    idSuffix=${DEMOKIT_SHELL_ANCHOR}
    RETURN    ${nb}

Compter Les Controles Actionnables
    [Documentation]    Nombre de contrôles d'un type actionnable rendus dans la
    ...    portée courante. Aucun identifiant généré de l'échantillon n'est
    ...    asserté : ils se recouvrent avec ceux du document hôte, seule la
    ...    portée les distingue.
    [Arguments]    ${controlType}=sap.m.Button
    ${nb}=    Get Ui5 Match Count    controlType=${controlType}
    RETURN    ${nb}

# =============================================================================
# Diagnostic : classer les anomalies, jamais les compter
# =============================================================================

Classer Les Anomalies De La Page
    [Documentation]    Trie les entrées de console significatives et les erreurs
    ...    de page non interceptées dans les familles connues de la cible.
    ...    Retourne `{familles, non_classees}`, où `familles` est un
    ...    dictionnaire nom de famille vers liste d'entrées.
    ...
    ...    Le comptage n'est pas un verdict exploitable ici : le nombre croît
    ...    avec la navigation, chaque fiche ouverte en ajoutant. Le verdict est
    ...    l'appartenance aux familles déclarées.
    ${diag}=    Get Fiori Diagnostics    sections=console,errors    full_logs=True
    ...    max_log_entries=${DEMOKIT_MAX_LOG}
    ${significatives}=    Evaluate
    ...    list(filter(lambda e, t=tuple($DEMOKIT_ANOMALY_TYPES): e.get('type') in t, $diag.get('console', [])))
    ${entrees}=    Evaluate
    ...    [{'source': 'console', 'type': e.get('type', ''), 'texte': e.get('text', ''), 'origine': e.get('location', '')} for e in $significatives]
    ${erreurs}=    Evaluate
    ...    [{'source': 'page', 'type': 'uncaught', 'texte': (e.get('name', '') + ': ' + e.get('message', '')), 'origine': e.get('stack', '')} for e in $diag.get('page_errors', [])]
    ${toutes}=    Combine Lists    ${entrees}    ${erreurs}
    ${familles}=    Create Dictionary
    ${non_classees}=    Create List
    FOR    ${entree}    IN    @{toutes}
        ${famille}=    Famille De L Anomalie    ${entree}
        IF    "${famille}" == "${EMPTY}"
            Append To List    ${non_classees}    ${entree}
        ELSE
            ${connues}=    Get From Dictionary    ${familles}    ${famille}    default=${None}
            IF    $connues is None
                ${connues}=    Create List
                Set To Dictionary    ${familles}    ${famille}=${connues}
            END
            Append To List    ${connues}    ${entree}
        END
    END
    ${classement}=    Create Dictionary    familles=${familles}    non_classees=${non_classees}
    RETURN    ${classement}

Famille De L Anomalie
    [Documentation]    Famille d'une entrée d'anomalie, ou chaîne vide si aucune
    ...    ne la couvre. Les critères sont des ORIGINES techniques (hôte tiers,
    ...    nom de ressource, marqueur du runtime) et jamais un texte de message
    ...    localisable : ceux du navigateur suivent sa propre langue.
    ...
    ...    La famille des ressources statiques se reconnaît au NOM du fichier
    ...    demandé, et le même manque se présente sous deux formes qu'il faut
    ...    couvrir toutes deux : l'échec de chargement, dont l'ORIGINE est
    ...    l'adresse de la ressource, et le refus du système de modules UI5,
    ...    dont l'origine est le noyau et qui NOMME la ressource dans son texte.
    ...    L'appariement porte donc sur les deux champs réunis.
    [Arguments]    ${entree}
    ${blob}=    Evaluate    ($entree['texte'] + ' ' + $entree['origine']).lower()
    ${est_tiers}=    Evaluate    any(map($blob.__contains__, $DEMOKIT_THIRD_PARTY_HOSTS))
    IF    ${est_tiers}    RETURN    tiers_hors_application
    ${est_statique}=    Evaluate    any(map($blob.__contains__, $DEMOKIT_MISSING_SDK_RESOURCES))
    IF    ${est_statique}    RETURN    ressource_statique_du_sdk
    ${est_runtime}=    Evaluate
    ...    $entree['type'] == 'assert' or $DEMOKIT_RUNTIME_WARNING_MARKER in $entree['texte']
    IF    ${est_runtime}    RETURN    avertissement_du_runtime_ui5
    RETURN    ${EMPTY}

Aucune Anomalie Hors Familles Connues
    [Documentation]    Verdict de diagnostic : toute anomalie relevée appartient
    ...    à l'une des familles déclarées. Une entrée hors familles fait
    ...    échouer en la NOMMANT, ce qui est le seul verdict utile ici.
    [Arguments]    ${classement}
    Should Be Empty    ${classement}[non_classees]
    ...    msg=Des anomalies n'appartiennent à aucune famille connue de cette cible : ${classement}[non_classees]

Journaliser Le Diagnostic Du Demo Kit
    [Documentation]    Écrit dans le log le classement des anomalies, famille
    ...    par famille, avec un exemple par famille. Pour le lecteur du log,
    ...    jamais pour une assertion.
    [Arguments]    ${classement}
    FOR    ${famille}    ${entrees}    IN    &{classement}[familles]
        ${exemple}=    Evaluate    $entrees[0]['texte'][:160]
        Log    Famille « ${famille} » : ${{ len($entrees) }} entrée(s), exemple : ${exemple}
    END
    Log    Anomalies hors familles connues : ${classement}[non_classees]

Les Messages Ui5 Doivent Etre Vides
    [Documentation]    Cette application ne passe pas par le gestionnaire de
    ...    messages UI5 : ni message ni toast, du début à la fin de la campagne.
    ...    L'assertion porte sur le TYPE et jamais sur un texte (convention 3).
    ${messages}=    Get Ui5 Messages
    Should Be Empty    ${messages}[messages]
    ...    msg=Le gestionnaire de messages UI5 porte des messages sur une cible qui ne l'utilise pas : ${messages}[messages]
    RETURN    ${messages}

# =============================================================================
# Primitives de saisie et d'ancrage
# =============================================================================

Motif Exact
    [Documentation]    Forme d'ancrage EXACT d'une valeur de propriété.
    ...    L'appariement de propriétés se fait par sous-chaîne : sans cette
    ...    forme, tout nom qui est le préfixe d'un autre est ambigu (mesuré,
    ...    `sap.uxap.ObjectPageLayout` rend 2 correspondances, la forme ancrée
    ...    en rend 1). Le point reste un métacaractère, assumé : il matche le
    ...    point littéral qu'il représente.
    [Arguments]    ${valeur}
    RETURN    /^${valeur}$/

Saisir Dans Le Champ
    [Documentation]    Frappe `${texte}` dans le champ de saisie désigné par son
    ...    suffixe d'identifiant, comme le ferait un utilisateur : poser la
    ...    valeur ne déclenche ni les suggestions ni le filtrage, qui sont
    ...    branchés sur les événements de frappe.
    [Arguments]    ${champ}    ${texte}
    ${selecteur}=    Resolve Ui5 Control    idSuffix=${champ}
    Click    ${selecteur}
    Fill Text    ${selecteur} >> input    ${EMPTY}
    Type Text    ${selecteur} >> input    ${texte}    delay=20ms

Vider Le Champ
    [Documentation]    Vide le champ de saisie désigné par son suffixe
    ...    d'identifiant, sans rien asserter : appelé en teardown, il ne doit
    ...    pas transformer un champ déjà vide en échec.
    [Arguments]    ${champ}
    ${present}=    Get Ui5 Match Count    idSuffix=${champ}
    IF    ${present} > 0
        ${selecteur}=    Resolve Ui5 Control    idSuffix=${champ}
        Fill Text    ${selecteur} >> input    ${EMPTY}
    END
