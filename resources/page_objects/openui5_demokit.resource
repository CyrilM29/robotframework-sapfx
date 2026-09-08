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
...                 Étendu le 2026-09-05 (SDK 1.152.0, exploration headless)
...                 pour la campagne d'exploration profonde
...                 (`specs/openui5-demokit-exploration-profonde.md`) : arbre
...                 des sujets de la Documentation, liens croisés du contenu,
...                 fiche d'API en profondeur (membres, bascules borrowed,
...                 chaîne d'héritage), galerie d'échantillons et vue du code
...                 source, Demo Apps et Resources, sentinelle d'accumulation.
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
# Depuis le SDK 1.152.0 (relevé 2026-09-01), le shell est rendu en UI5 Web
# Components encapsulés dans des wrappers `sap.f.gen.ui5.webcomponents*` qui
# restent AU REGISTRE : les moteurs role/xpath les adressent encore. La
# recherche est un `ShellBarSearch` qui garde l'id stable `searchControl`
# (son enfant `searchControl-searchField` n'existe plus), et ses entrées de
# suggestion sont des `SearchItem`/`SearchItemGroup` dont le titre se lit sur
# la propriété `text`. Les entrées ne sont PAS DOM-contenues dans le popover
# WC (il vit dans un shadow root) : la portée de lecture est le contrôle de
# recherche lui-même.
${DEMOKIT_SEARCH_CONTROL}           searchControl
${DEMOKIT_SUGGESTION_TYPE}          SearchItem
${DEMOKIT_SUGGESTION_GROUP_TYPE}    SearchItemGroup
${DEMOKIT_SUGGESTION_TITLE_PROP}    text
# Les entrées de résultat portent un identifiant technique suivi de sa
# catégorie entre parenthèses : `sap.m.Button (class): ...`. Le mot de la
# catégorie n'est PAS traduit (mesuré interface en français).
${DEMOKIT_SUGGESTION_CLASS_SUFFIX}    ${SPACE}(class)
${DEMOKIT_MENU_BUTTON}              aboutMenuButton
${DEMOKIT_MENU_BUTTON_ICON}         sap-icon://action-settings
# Le menu Options est un `ui5-menu` WC d'id stable `aboutMenu`. Ses entrées
# (`MenuItem` WC au registre) n'ont PLUS de propriété `key` : la clé technique
# vit dans l'id, de forme `menuItem-<clé>`, et TOUTES les entrées (sous-menu
# fermé compris) sont au DOM, DOM-contenues dans le menu. La pile de popups
# compte les couches d'implémentation WC : menu ouvert = 2 entrées (le menu +
# son popover interne `ui5wc_N-menu-rp`), sous-menu = +1.
${DEMOKIT_MENU}                     aboutMenu
${DEMOKIT_MENU_ITEM_TYPE}           MenuItem
${DEMOKIT_MENU_ITEM_PREFIX}         menuItem-
${DEMOKIT_MENU_STACK_COST}          ${2}
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

# --- Section Documentation : arbre des sujets et vue de détail ----------------
# (Campagne d'exploration profonde, relevé live 2026-09-05, SDK 1.152.0.)
${DEMOKIT_TOPIC_TREE}               topicMaster--tree
${DEMOKIT_TOPIC_FILTER}             topicMaster--searchField
# DEUX vues portent le suffixe court `topicDetailPage` (l'écran d'accueil de la
# section ET le sujet réel, mesuré 2 correspondances) : l'ancre est le suffixe
# LONG incluant le nom de vue, qui rend exactement 1.
${DEMOKIT_TOPIC_DETAIL_PAGE}        topicDetail--topicDetailPage
# Le `target` d'un nœud de sujet est le « loio » stable du corpus : un GUID
# hexadécimal de 32 caractères, jamais un nom qualifié. Motif SANS backslash
# (l'échappement Robot défangerait un `\\w` en silence, leçon du dépôt).
${DEMOKIT_GUID_MOTIF}               [0-9a-f]{32}
# Deux loio relevés live, stables (identifiants de contenu, pas des ids DOM) :
# la racine « Essentials » et son enfant « Data Binding », riche en liens
# croisés vers l'API.
${DEMOKIT_SUJET_ESSENTIALS}         ec699e0817fb46a0817b0fa276a249f8
${DEMOKIT_SUJET_DATA_BINDING}       68b9644a253741e8a4b9e4279a35c247

# --- Fiche d'API en profondeur : rubriques, membres, bascules borrowed --------
${DEMOKIT_API_OBJECT_PAGE}          apiDetailObjectPage
# La rubrique sélectionnée se lit sur le `selectedKey` de la barre d'ancrage
# (IconTabHeader), par SUFFIXE : le préfixe de vue est généré (`__xmlview<N>--`).
# `selectedSectionId` n'existe pas comme propriété sur cet ObjectPageLayout.
${DEMOKIT_ANCHOR_BAR_TYPE}          sap.m.IconTabHeader
# Les cases « Show borrowed ... » ont des ids GÉNÉRÉS (`__box9`...) : elles
# s'ancrent par containment de rubrique (exactement 1 CheckBox par rubrique,
# vérifié), jamais par id ni par libellé (localisé).
${DEMOKIT_CHECKBOX_TYPE}            sap.m.CheckBox
${DEMOKIT_BORROWED_LIST_TYPE}       sap.ui.documentation.BorrowedList
${DEMOKIT_DOC_BORROWED_MARKER}         borrowedFrom
${DEMOKIT_SECTION_AGGREGATIONS}     aggregations
${DEMOKIT_SECTION_EVENTS}           events
${DEMOKIT_SECTION_METHODS}          methods
@{DEMOKIT_RUBRIQUES_ATTENDUES}      controlproperties    aggregations    events    methods
# Les trois rubriques porteuses d'une case « Show borrowed ... ». État par
# défaut RELEVÉ le 2026-09-05 : [False, True, False], la case des AGRÉGATIONS
# est cochée d'origine (la table contient donc des entrées héritées sans qu'on
# ait rien touché) : l'état se relève AVANT de lire, jamais supposé.
@{DEMOKIT_RUBRIQUES_A_BASCULE}      controlproperties    aggregations    associations
# Propriétés documentées que la fiche du contrôle vivant ne matérialise PAS :
# la fiche est réduite aux valeurs PRIMITIVES (MCP-safe), et `fieldGroupIds`
# est la seule propriété de `sap.m.Button` à valeur tableau (mesuré 2026-09-05 :
# 70 instances rendues, 0 porteuse). Inventaire déclaré à compte exact : une
# entrée devenue lisible sur le vivant fait ÉCHOUER le verdict (tolérance
# morte), une propriété manquante de plus aussi.
@{DEMOKIT_PROPS_HORS_FICHE}         fieldGroupIds

# --- Galerie d'échantillons et vue du code source -----------------------------
${DEMOKIT_ENTITY_TABLE}             entity--table
${DEMOKIT_ENTITY_ROW_TYPE}          sap.m.ColumnListItem
${DEMOKIT_SAMPLE_CODE_BUTTON}       sample--code
# Boutons de la barre d'échantillon PERÇUS mais JAMAIS actionnés (lecture
# seule) : ouverture d'onglet et mode adaptation runtime.
@{DEMOKIT_SAMPLE_TOOLBAR_INTERDITS}    sample--newTab    sample--toggleRTA
${DEMOKIT_CODE_FILE_EDITOR}         code--fileEditor
${DEMOKIT_CODE_EDITOR}              code--fileEditor-editor
# Le téléchargement écrit sur le disque : perçu, jamais cliqué.
${DEMOKIT_CODE_DOWNLOAD}            code--downloadSampleButton
${DEMOKIT_CODE_NEXT}                code--nextSample
${DEMOKIT_CODE_PREV}                code--prevSample
# Les fichiers de l'échantillon sont des onglets dont la `key` EST le nom de
# fichier ; un 4e onglet technique à clé VIDE est rendu à côté (relevé live) :
# la lecture filtre les clés vides.
${DEMOKIT_FILE_TAB_TYPE}            sap.m.IconTabFilter
${DEMOKIT_CODE_ROUTE_SUFFIX}        /code

# --- Demo Apps et Resources ---------------------------------------------------
${DEMOKIT_DEMOAPPS_MAIN}            demoApps--sapUiDemoKitDemoAppsMain
${DEMOKIT_CARD_TYPE}                sap.f.Card
# La vue Resources n'a pas de conteneur de page à id stable : la PORTÉE de
# comptage est la vue elle-même (id complet, relevé live).
${DEMOKIT_RESOURCES_VIEW}           sdk---resources
# Hôtes externes DÉCLARÉS des cartes Demo Apps : un lien absolu vers un autre
# hôte sort en intrus et fait échouer le verdict. Deux hôtes relevés live :
# les dépôts GitHub et les pages GitHub Pages des exemples SAP-samples
# (`sap-samples.github.io`, relevé au premier run complet).
@{DEMOKIT_EXTERNAL_LINK_HOSTS}      github.com    sap-samples.github.io

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
# L'entrée `component-preload.js` couvre la FAMILLE des préchargements de
# composants, que le SDK ne sert jamais : celui de l'accueil
# (`sdk/samples/component-preload.js`, entrée historique qu'elle subsume) et
# celui de CHAQUE échantillon exécuté, qui manque sous DEUX formes (404 réseau
# sur `test-resources/.../demokit/sample/<Nom>/Component-preload.js` et refus
# du ModuleSystem nommant `.../sample/<Nom>/Component-preload.js`), relevées
# live le 2026-09-05 sur Button ET ButtonWithBadge. L'entrée nomme le FICHIER :
# toute autre ressource manquante sort toujours non classée.
@{DEMOKIT_MISSING_SDK_RESOURCES}    jquery.ui.button.css    jquery.ui.theme.css
...                                 component-preload.js
# INVENTAIRE des ressources du shell Web Components (SDK 1.152.0) dont le code
# émet ses propres exceptions non rattrapées (relevé live 2026-09-01 :
# `TypeError: e._close is not a function` dans `_closeOtherSubMenus`, déclenché
# par la cascade du menu Options : un défaut du SDK, pas de la campagne). Même
# contrat que l'inventaire ci-dessus : reconnu au NOM de la ressource dans la
# pile d'origine, jamais au texte du message ; une ressource de plus sort en
# anomalie NON CLASSÉE et fait échouer le diagnostic, c'est l'effet voulu.
@{DEMOKIT_WC_SHELL_RESOURCES}       library-webcomponents-preload.js
${DEMOKIT_RUNTIME_WARNING_MARKER}    [FUTURE FATAL]
${DEMOKIT_MAX_LOG}                  ${300}
@{DEMOKIT_ANOMALY_TYPES}            error    warning    assert

# --- État relevé au setup, restauré au teardown -------------------------------
${DEMOKIT_INITIAL_THEME}            ${EMPTY}
&{DEMOKIT_INITIAL_TOGGLES}          # rempli par `Memoriser L Etat Initial Du Demo Kit`
&{DEMOKIT_INITIAL_BORROWED}         # rempli par `Memoriser Les Bascules Borrowed` (fiche d'API seulement)


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
    Run Keyword And Ignore Error    Vider Le Champ    ${DEMOKIT_SEARCH_CONTROL}
    Run Keyword And Ignore Error    Vider Le Champ    ${DEMOKIT_API_FILTER}
    Run Keyword And Ignore Error    Restaurer Les Bascules D Affichage
    Run Keyword And Ignore Error    Restaurer Les Bascules Borrowed
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
    ...    page HYBRIDE UI5 + Web Components (le shell est en WC depuis le SDK
    ...    1.152.0 : des hôtes WC ABSENTS signaleraient un nouveau changement
    ...    de composition, dans l'autre sens), aucun élément WebGUI, aucune
    ...    frame, moteurs `role` ET `wc` recommandés, et un plancher de
    ...    contrôles rendus. La VERSION et la LANGUE sont journalisées, jamais
    ...    assertées : la première bouge avec le SDK, la seconde a changé en
    ...    cours de run sur cette cible.
    ${compo}=    Get Page Composition
    Should Be True    ${compo}[ui5_runtime]
    ...    msg=Aucun runtime UI5 sur la page du Demo Kit : la cible n'est pas celle attendue.
    Should Not Be Empty    ${compo}[ui5_version]
    ...    msg=Le runtime UI5 ne déclare aucune version.
    Should Be True    ${compo}[wc_hosts] > 0
    ...    msg=Plus aucun hôte Web Component sur cette page alors que le shell 1.152.0 est en WC : la composition a changé.
    Should Be Equal As Integers    ${compo}[webgui_elements]    0
    ...    msg=Des éléments WebGUI sont apparus sur cette page : la composition a changé.
    Should Be Empty    ${compo}[frames]
    ...    msg=L'accueil du Demo Kit ne doit porter aucune iframe.
    List Should Contain Value    ${compo}[engines]    role
    ...    msg=Le moteur role n'est plus recommandé sur cette page : ${compo}[engines]
    List Should Contain Value    ${compo}[engines]    wc
    ...    msg=Le moteur wc n'est plus recommandé sur cette page : ${compo}[engines]
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
    [Documentation]    Saisit `${terme}` dans le contrôle de recherche global
    ...    (`ShellBarSearch` WC, id stable, frappe percée jusqu'à l'input du
    ...    shadow root) et constate l'ouverture du popover de suggestions SUR
    ...    LA PILE DE POPUPS. Retourne l'identifiant complet du CONTRÔLE DE
    ...    RECHERCHE, qui sert de PORTÉE aux lectures suivantes : depuis le
    ...    shell WC (1.152.0), les entrées de suggestion ne sont pas
    ...    DOM-contenues dans le popover, qui vit dans un shadow root. La
    ...    saisie passe par de vraies frappes : poser la valeur ne déclenche
    ...    pas les suggestions.
    [Arguments]    ${terme}
    Saisir Dans Le Champ    ${DEMOKIT_SEARCH_CONTROL}    ${terme}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Pile De Popups Doit Avoir    ${1}
    ${identifiants}=    Get Ui5 Ids    idSuffix=${DEMOKIT_SEARCH_CONTROL}
    RETURN    ${identifiants}[0]

Lire Les Suggestions
    [Documentation]    Titres des entrées de résultat rendues dans la portée
    ...    donnée (le contrôle de recherche depuis le shell WC), dans l'ordre
    ...    du registre. Le titre se lit sur la propriété `text` des
    ...    `SearchItem` ; il porte des identifiants techniques non traduits.
    [Arguments]    ${portee}
    ${titres}=    Get Ui5 Properties    ${DEMOKIT_SUGGESTION_TITLE_PROP}
    ...    controlType=${DEMOKIT_SUGGESTION_TYPE}    containedIn=${portee}
    RETURN    ${titres}

Compter Les En Tetes De Groupe
    [Documentation]    Nombre de lignes de catégorie des suggestions, dans la
    ...    portée donnée.
    [Arguments]    ${portee}
    ${nb}=    Get Ui5 Match Count    controlType=${DEMOKIT_SUGGESTION_GROUP_TYPE}
    ...    containedIn=${portee}
    RETURN    ${nb}

Attendre Les Suggestions Groupees
    [Documentation]    Attente ACTIVE de l'arrivée des résultats groupés dans
    ...    la portée. Le popover s'ouvre dès la première frappe, mais les
    ...    entrées et leurs en-têtes de groupe arrivent avec les RÉSULTATS, un
    ...    instant plus tard (mesuré 2026-09-01 : lu à l'instant de
    ...    l'ouverture, le compte de groupes vaut 0 ; relu après l'arrivée des
    ...    résultats, 2). « Popover ouvert » ne veut pas dire « résultats là ».
    [Arguments]    ${portee}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Les Suggestions Doivent Etre Groupees    ${portee}

Les Suggestions Doivent Etre Groupees
    [Documentation]    Assertion sondable : au moins un en-tête de groupe est
    ...    rendu dans la portée des suggestions.
    [Arguments]    ${portee}
    ${nb}=    Compter Les En Tetes De Groupe    ${portee}
    Should Be True    ${nb} >= 1
    ...    msg=Le popover de suggestions ne porte aucun en-tête de groupe.

Les Suggestions Doivent Proposer
    [Documentation]    Assertion locale-indépendante : au moins une entrée dont
    ...    le titre porte l'identifiant technique cherché. Aucun libellé
    ...    traduit n'entre dans le verdict.
    [Arguments]    ${portee}    ${nom_qualifie}
    ${titres}=    Lire Les Suggestions    ${portee}
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
    [Arguments]    ${portee}    ${nom_qualifie}
    ${titres}=    Lire Les Suggestions    ${portee}
    ${identifiants}=    Get Ui5 Ids    controlType=${DEMOKIT_SUGGESTION_TYPE}    containedIn=${portee}
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
    ...
    ...    Une SOUS-ROUTE DE MEMBRE de la même fiche compte comme « déjà
    ...    affichée » (mesuré à la génération de la campagne profonde : depuis
    ...    `/api/X%23events/press`, demander `/api/X` réinitialise le titre au
    ...    titre générique de la section et n'en revient jamais, exactement le
    ...    symptôme du cas à l'identique).
    [Arguments]    ${nom_qualifie}
    ${emplacement}=    Get Page Location
    ${deja}=    Evaluate
    ...    $emplacement['fragment'] == '/api/' + $nom_qualifie or $emplacement['fragment'].startswith('/api/' + $nom_qualifie + '%23') or $emplacement['fragment'].startswith('/api/' + $nom_qualifie + '#')
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
    ...    correspondance, avec un rectangle nul. Depuis le shell WC (1.152.0),
    ...    un menu ouvert pousse DEUX entrées sur la pile (le `ui5-menu` et son
    ...    popover interne `ui5wc_N-menu-rp`) : le coût est porté par
    ...    `${DEMOKIT_MENU_STACK_COST}`, jamais supposé égal à 1.
    ${profondeur}=    Lire La Profondeur De La Pile De Popups
    ${attendue}=    Evaluate    $profondeur + ${DEMOKIT_MENU_STACK_COST}
    Click Ui5 Control    idSuffix=${DEMOKIT_MENU_BUTTON}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Pile De Popups Doit Avoir    ${attendue}

Ouvrir L Entree De Menu
    [Documentation]    Clique l'entrée de menu portant la clé technique
    ...    `${cle}`. Depuis le shell WC, les entrées n'ont plus de propriété
    ...    `key` : la clé vit dans l'identifiant, de forme STABLE
    ...    `menuItem-<clé>`, qui devient l'ancre de clic. La garde de pile
    ...    reste : entrée présente au DOM ne veut pas dire menu ouvert.
    [Arguments]    ${cle}
    ${pile}=    Get Ui5 Open Popups
    Should Not Be Empty    ${pile}
    ...    msg=Aucun popup ouvert : l'entrée de menu ${cle} n'est pas atteignable.
    Click Ui5 Control    idSuffix=${DEMOKIT_MENU_ITEM_PREFIX}${cle}

Lister Les Cles Du Menu Ouvert
    [Documentation]    Clés techniques des entrées du menu ouvert, dérivées des
    ...    suffixes d'identifiant `menuItem-<clé>` dans la portée du menu.
    ...    Depuis le shell WC, TOUTES les entrées (sous-menu fermé compris)
    ...    sont au DOM et DOM-contenues dans le menu : la lecture rend le menu
    ...    ENTIER (9 clés mesurées), elle ne distingue plus le niveau ouvert,
    ...    et les assertions des appelants sont des INCLUSIONS.
    ${pile}=    Get Ui5 Open Popups
    Should Not Be Empty    ${pile}
    ...    msg=Aucun popup ouvert : il n'y a pas de menu dont lire les clés.
    ${menus}=    Evaluate    [p['id'] for p in $pile if p['id'].endswith('${DEMOKIT_MENU}')]
    Should Not Be Empty    ${menus}
    ...    msg=Aucun menu Options dans la pile de popups : ${pile}
    ${identifiants}=    Get Ui5 Ids    controlType=${DEMOKIT_MENU_ITEM_TYPE}
    ...    containedIn=${menus}[0]
    ${cles}=    Evaluate    [i.split('${DEMOKIT_MENU_ITEM_PREFIX}', 1)[1] for i in $identifiants if '${DEMOKIT_MENU_ITEM_PREFIX}' in i]
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
    ${cascade}=    Evaluate    ${DEMOKIT_MENU_STACK_COST} + 1
    Attendre La Profondeur De Pile    ${cascade}
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
    ${est_shell_wc}=    Evaluate    any(map($blob.__contains__, $DEMOKIT_WC_SHELL_RESOURCES))
    IF    ${est_shell_wc}    RETURN    defaut_du_shell_webcomponents
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

# =============================================================================
# Section Documentation : arbre des sujets et liens croisés du contenu
# =============================================================================

Compter Les Noeuds De L Arbre Des Sujets
    [Documentation]    Nombre de nœuds rendus DANS l'arbre des sujets de la
    ...    Documentation. La portée n'est pas un détail : cette SPA garde les
    ...    maîtres de toutes les sections visitées rendus côte à côte, et les
    ...    nœuds de l'arbre de l'API sont du même type.
    ${nb}=    Get Ui5 Match Count    controlType=${DEMOKIT_TREE_ITEM_TYPE}
    ...    containedIn=${DEMOKIT_TOPIC_TREE}
    RETURN    ${nb}

Attendre L Arbre Des Sujets
    [Documentation]    Attente ACTIVE des nœuds de l'arbre des sujets : ils
    ...    arrivent APRÈS les deux témoins de section, le champ de filtre
    ...    étant déjà rendu (mesuré live : 0 nœud à l'instant des témoins,
    ...    filtre présent, 9 nœuds un instant plus tard). Retourne le
    ...    comptage.
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    L Arbre Des Sujets Doit Rendre Des Noeuds
    ${nb}=    Compter Les Noeuds De L Arbre Des Sujets
    RETURN    ${nb}

L Arbre Des Sujets Doit Rendre Des Noeuds
    [Documentation]    Assertion sondable : au moins un nœud de sujet rendu.
    ${nb}=    Compter Les Noeuds De L Arbre Des Sujets
    Should Be True    ${nb} > 0
    ...    msg=L'arbre des sujets de la Documentation ne rend aucun nœud.

Lister Les Identifiants De Sujets
    [Documentation]    Les `target` des nœuds de sujets rendus : le « loio »
    ...    stable de chaque sujet, un GUID hexadécimal et jamais un nom
    ...    qualifié. Les titres des nœuds sont de la prose documentaire
    ...    anglaise : ils se journalisent, ils ne s'ancrent pas.
    ${cibles}=    Get Ui5 Properties    target    controlType=${DEMOKIT_TREE_ITEM_TYPE}
    ...    containedIn=${DEMOKIT_TOPIC_TREE}
    RETURN    ${cibles}

Les Identifiants De Sujets Doivent Etre Des Guid
    [Documentation]    Assertion STRUCTURELLE, indépendante de la langue et du
    ...    contenu : chaque identifiant de sujet suit le motif du GUID
    ...    hexadécimal de 32 caractères. L'échec NOMME les intrus.
    [Arguments]    ${cibles}
    Should Not Be Empty    ${cibles}
    ...    msg=Aucun identifiant de sujet à vérifier : l'arbre des sujets est vide.
    ${intrus}=    Evaluate
    ...    [c for c in $cibles if not re.fullmatch('${DEMOKIT_GUID_MOTIF}', c)]
    Should Be Empty    ${intrus}
    ...    msg=Des identifiants de sujets ne sont pas des GUID hexadécimaux de 32 caractères : ${intrus}

Le Champ De Filtre Des Sujets Doit Etre Rendu
    [Documentation]    Le panneau des sujets porte exactement un champ de
    ...    filtre.
    ${nb}=    Get Ui5 Match Count    idSuffix=${DEMOKIT_TOPIC_FILTER}
    Should Be Equal As Integers    ${nb}    1
    ...    msg=Le champ de filtre du panneau des sujets rend ${nb} correspondance(s), attendu exactement 1.

Ouvrir Le Sujet
    [Documentation]    Clique le nœud d'arbre dont l'identifiant de sujet est
    ...    EXACTEMENT `${guid}` (ancrage exact : l'appariement de propriétés se
    ...    fait par sous-chaîne), puis attend le fragment ET la vue de détail
    ...    RÉELLE. Le clic navigue ET déplie dans le même geste.
    [Arguments]    ${guid}
    ${motif}=    Motif Exact    ${guid}
    ${vise}=    Get Ui5 Match Count    controlType=${DEMOKIT_TREE_ITEM_TYPE}
    ...    containedIn=${DEMOKIT_TOPIC_TREE}    properties={'target': '${motif}'}
    Should Be Equal As Integers    ${vise}    1
    ...    msg=L'ancrage exact sur le sujet ${guid} rend ${vise} correspondance(s) : le nœud visé n'est pas identifiable sans ambiguïté.
    Click Ui5 Control    controlType=${DEMOKIT_TREE_ITEM_TYPE}
    ...    containedIn=${DEMOKIT_TOPIC_TREE}    properties={'target': '${motif}'}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Le Sujet Affiche Doit Etre    ${guid}

Ouvrir Le Sujet Par Sa Route
    [Documentation]    Navigue vers le sujet `${guid}` par sa route de hash,
    ...    sans dépendre de l'état de dépliage de l'arbre : c'est ce qui rend
    ...    le scénario indépendant du test qui l'a précédé. Même garde de
    ...    rejouabilité que `Ouvrir La Fiche D Api` : demander l'URL courante à
    ...    l'identique ne re-résout rien et réinitialise le titre, donc le
    ...    sujet DÉJÀ affiché passe par un rechargement.
    [Arguments]    ${guid}
    ${emplacement}=    Get Page Location
    ${deja}=    Evaluate    $emplacement['fragment'] == '/topic/' + $guid
    IF    ${deja}
        Reload
        Attendre Le Runtime Du Demo Kit
    ELSE
        Go To    ${DEMOKIT_URL}#/topic/${guid}
    END
    Attendre Le Repos Du Demo Kit
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Le Sujet Affiche Doit Etre    ${guid}

Le Sujet Affiche Doit Etre
    [Documentation]    Les deux témoins d'arrivée sur un sujet : le fragment
    ...    porte le GUID, et la vue de détail RÉELLE est rendue. Le suffixe
    ...    court `topicDetailPage` ne suffit pas : l'écran d'accueil de la
    ...    section le porte aussi (2 correspondances mesurées), seule l'ancre
    ...    LONGUE incluant le nom de vue rend exactement 1.
    [Arguments]    ${guid}
    Le Fragment Doit Porter    /topic/${guid}
    ${detail}=    Get Ui5 Match Count    idSuffix=${DEMOKIT_TOPIC_DETAIL_PAGE}
    Should Be Equal As Integers    ${detail}    1
    ...    msg=La vue de détail réelle du sujet n'est pas rendue (${detail} correspondance(s) sur l'ancre longue).

Compter Les Liens Croises Vers L Api
    [Documentation]    Nombre d'ancres relatives `api/...` DANS la portée du
    ...    détail du sujet affiché. Les liens croisés du contenu documentaire
    ...    sont des ancres DOM relatives SANS `#/` (mesuré : un sélecteur
    ...    `href*="#/api/"` rend 0 en croyant qu'il n'y a pas de liens), et la
    ...    portée est obligatoire : le contenu des sujets déjà lus reste au
    ...    DOM.
    ${detail}=    Resolve Ui5 Control    idSuffix=${DEMOKIT_TOPIC_DETAIL_PAGE}
    ${nb}=    Get Element Count    ${detail} a[href^='api/']
    RETURN    ${nb}

Ouvrir Le Lien Croise Vers L Api
    [Documentation]    Clique l'ancre relative `api/${nom_qualifie}` dans la
    ...    portée du détail du sujet (moteur DOM : ce contenu HTML vit hors du
    ...    registre UI5), puis attend l'arrivée sur la fiche ET le changement
    ...    de section : la navigation croisée fait passer la clé active de
    ...    `topic` à `api`, c'est le cœur du scénario.
    [Arguments]    ${nom_qualifie}
    ${detail}=    Resolve Ui5 Control    idSuffix=${DEMOKIT_TOPIC_DETAIL_PAGE}
    Click    ${detail} a[href='api/${nom_qualifie}']
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Navigation Croisee Doit Etre Arrivee    ${nom_qualifie}

La Navigation Croisee Doit Etre Arrivee
    [Documentation]    Assertion sondable du lien croisé : la fiche d'API est
    ...    affichée (couple fragment plus titre) ET la section active est la
    ...    Référence de l'API.
    [Arguments]    ${nom_qualifie}
    La Fiche Affichee Doit Etre    ${nom_qualifie}
    La Section Active Doit Etre    api

# =============================================================================
# Fiche d'API en profondeur : rubriques, membres, provenance
# =============================================================================

Lister Les Rubriques De La Fiche
    [Documentation]    Suffixes des rubriques de la fiche d'API affichée,
    ...    portés par la vue d'objet de la fiche (le préfixe de vue est GÉNÉRÉ,
    ...    `__xmlview<N>--`, seul le suffixe est stable). La portée écarte les
    ...    rubriques des autres sections que cette SPA garde rendues.
    ${ids}=    Get Ui5 Ids    controlType=${DEMOKIT_SECTION_TYPE}
    ...    containedIn=${DEMOKIT_API_OBJECT_PAGE}
    Should Not Be Empty    ${ids}
    ...    msg=La fiche d'API ne porte aucune rubrique de documentation.
    ${suffixes}=    Evaluate    [i.rsplit('--', 1)[-1] for i in $ids]
    RETURN    ${suffixes}

Ouvrir Le Membre De La Fiche
    [Documentation]    Clique le lien DOM du membre `${nom}` (rubrique
    ...    `${type_membre}`) de la fiche `${classe}`, dans la PORTÉE de sa
    ...    rubrique, puis attend le fragment et la rubrique sélectionnée. Le
    ...    lien est une ancre relative `api/<classe>#<type>/<nom>` du contenu
    ...    documentaire (hors registre UI5).
    [Arguments]    ${classe}    ${type_membre}    ${nom}
    ${section}=    Resolve Ui5 Control    controlType=${DEMOKIT_SECTION_TYPE}
    ...    idSuffix=${type_membre}    containedIn=${DEMOKIT_API_OBJECT_PAGE}
    Click    ${section} a[href='api/${classe}#${type_membre}/${nom}']
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Le Membre Doit Etre Atteint    ${classe}    ${type_membre}    ${nom}

Le Membre Doit Etre Atteint
    [Documentation]    Assertion sondable de sous-navigation : le fragment
    ...    porte le membre (le témoin FORT, celui du routeur), et la barre
    ...    d'ancrage a QUITTÉ la rubrique d'ouverture (le témoin du
    ...    défilement). La barre est un scroll spy, pas un témoin de route :
    ...    mesuré au premier run, elle peut se stabiliser sur la rubrique
    ...    VOISINE (`--associations` pour un membre d'`events`, rubrique
    ...    courte) alors que la navigation a parfaitement réussi. Sa valeur
    ...    exacte se journalise, elle ne se grave pas.
    [Arguments]    ${classe}    ${type_membre}    ${nom}
    Le Fragment Doit Porter Le Membre    ${classe}    ${type_membre}    ${nom}
    ${rubrique}=    Lire La Rubrique Selectionnee
    ${suivie}=    Evaluate    not $rubrique.endswith('--overview')
    Should Be True    ${suivie}
    ...    msg=La barre d'ancrage déclare encore ${rubrique} : le défilement n'a pas suivi la navigation vers le membre.

Le Fragment Doit Porter Le Membre
    [Documentation]    Le fragment d'une route de membre encode le second
    ...    dièse : cliquer `api/sap.m.Button#events/press` donne
    ...    `/api/sap.m.Button%23events/press` (mesuré). Une égalité sur la
    ...    forme à dièse échouerait sur une navigation réussie : l'assertion
    ...    accepte les deux formes.
    [Arguments]    ${classe}    ${type_membre}    ${nom}
    ${emplacement}=    Get Page Location
    ${porte}=    Evaluate
    ...    ($classe + '#' + $type_membre + '/' + $nom in $emplacement['fragment']) or ($classe + '%23' + $type_membre + '/' + $nom in $emplacement['fragment'])
    Should Be True    ${porte}
    ...    msg=Le fragment est ${emplacement}[fragment], attendu portant ${classe} suivi de ${type_membre}/${nom} (second dièse éventuellement encodé %23).

Lire La Rubrique Selectionnee
    [Documentation]    La rubrique sélectionnée se lit sur le `selectedKey` de
    ...    la barre d'ancrage de la fiche (le préfixe de vue est généré, seul
    ...    le suffixe est stable) ; `selectedSectionId` n'est pas une propriété
    ...    de l'ObjectPageLayout de cette version. ATTENTION à ce qu'elle
    ...    prouve : la barre est un scroll spy, et sur une navigation de
    ...    membre elle peut se stabiliser sur la rubrique VOISINE (mesuré au
    ...    premier run) : la route se prouve au FRAGMENT, jamais ici.
    ${cle}=    Get Ui5 Property    selectedKey    controlType=${DEMOKIT_ANCHOR_BAR_TYPE}
    ...    containedIn=${DEMOKIT_API_OBJECT_PAGE}
    RETURN    ${cle}

Compter Les Lignes De La Rubrique
    [Documentation]    Nombre de lignes de la table de documentation de la
    ...    rubrique `${rubrique}` (agrégation `rows`, la propriété du contrôle
    ...    étant les en-têtes).
    [Arguments]    ${rubrique}
    ${lignes}=    Get Ui5 Aggregation Info    ${DEMOKIT_DOC_ROW_AGGREGATION}
    ...    controlType=${DEMOKIT_DOC_TABLE_TYPE}    containedIn=${rubrique}
    ${nb}=    Get Length    ${lignes}
    RETURN    ${nb}

La Rubrique Doit Compter Plus De
    [Documentation]    Assertion sondable : la table de la rubrique porte
    ...    strictement plus de `${reference}` lignes.
    [Arguments]    ${rubrique}    ${reference}
    ${nb}=    Compter Les Lignes De La Rubrique    ${rubrique}
    Should Be True    ${nb} > ${reference}
    ...    msg=La table de la rubrique ${rubrique} porte ${nb} ligne(s), attendu strictement plus de ${reference}.

Les Lignes De La Rubrique Ne Portent Pas De Contexte
    [Documentation]    Assertion-DOCUMENTATION d'un fait mesuré : les lignes
    ...    des tables des méthodes et des événements ne portent AUCUN contexte
    ...    de liaison (`binding: None` sur les 44 lignes de `sap.m.Button`),
    ...    contrairement aux propriétés et agrégations. La voie du contexte y
    ...    rend des listes vides PLAUSIBLES, le profil « vert et faux » : ce
    ...    keyword grave le fait pour que la voie de lecture erronée ne
    ...    revienne pas. Les noms techniques se lisent sur les liens DOM de la
    ...    rubrique (`Lire Les Membres Propres De La Rubrique`).
    [Arguments]    ${rubrique}
    ${lignes}=    Get Ui5 Aggregation Info    ${DEMOKIT_DOC_ROW_AGGREGATION}
    ...    controlType=${DEMOKIT_DOC_TABLE_TYPE}    containedIn=${rubrique}
    Should Not Be Empty    ${lignes}
    ...    msg=La table de la rubrique ${rubrique} ne porte aucune ligne.
    ${porteuses}=    Evaluate    [l for l in $lignes if l.get('binding')]
    Should Be Empty    ${porteuses}
    ...    msg=Des lignes de la rubrique ${rubrique} portent désormais un contexte de liaison : le fait documenté a changé, la voie de lecture est à revoir.

Lire Les Membres Propres De La Rubrique
    [Documentation]    Noms techniques des membres PROPRES de `${classe}` dans
    ...    la rubrique `${type_membre}`, extraits des liens DOM relatifs
    ...    `api/<classe>#<type>/<nom>` portés par la rubrique : le préfixe de
    ...    classe filtre les membres propres des hérités (dont les liens
    ...    pointent vers l'ancêtre). Dédoublonnés : un membre est lié plusieurs
    ...    fois (nom de ligne, références du texte).
    [Arguments]    ${classe}    ${type_membre}
    ${section}=    Resolve Ui5 Control    controlType=${DEMOKIT_SECTION_TYPE}
    ...    idSuffix=${type_membre}    containedIn=${DEMOKIT_API_OBJECT_PAGE}
    ${ancres}=    Get Elements    ${section} a[href^='api/${classe}#${type_membre}/']
    ${noms}=    Create List
    FOR    ${ancre}    IN    @{ancres}
        ${href}=    Get Attribute    ${ancre}    href
        ${nom}=    Evaluate    $href.rsplit('/', 1)[-1]
        Append To List    ${noms}    ${nom}
    END
    ${uniques}=    Evaluate    sorted(set($noms))
    RETURN    ${uniques}

Les Noms Doivent Etre Des Identifiants Javascript
    [Documentation]    Assertion structurelle : chaque nom de membre est un
    ...    identifiant JavaScript, éventuellement QUALIFIÉ par des points :
    ...    les méthodes statiques sont documentées sous leur nom plein
    ...    (`sap.m.Button.extend`, `sap.m.Button.getMetadata`, relevé au
    ...    premier run). Motif SANS backslash (l'échappement Robot défangerait
    ...    un `\\w` en silence, leçon du dépôt : la classe `[.]` remplace le
    ...    point échappé).
    [Arguments]    ${noms}
    Should Not Be Empty    ${noms}
    ...    msg=Aucun nom de membre à vérifier.
    ${intrus}=    Evaluate
    ...    [n for n in $noms if not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*([.][A-Za-z_][A-Za-z0-9_]*)*', n)]
    Should Be Empty    ${intrus}
    ...    msg=Des noms de membres ne sont pas des identifiants JavaScript, même qualifiés : ${intrus}

# =============================================================================
# Bascules « borrowed » des rubriques de fiche
# =============================================================================

Lire La Bascule Borrowed De La Rubrique
    [Documentation]    État de la case « Show borrowed ... » de la rubrique
    ...    `${rubrique}`, ancrée par CONTAINMENT (exactement 1 CheckBox par
    ...    rubrique, vérifié) : ses ids sont générés et son libellé est
    ...    localisé, ni l'un ni l'autre ne s'ancrent.
    [Arguments]    ${rubrique}
    ${nb}=    Get Ui5 Match Count    controlType=${DEMOKIT_CHECKBOX_TYPE}    containedIn=${rubrique}
    Should Be Equal As Integers    ${nb}    1
    ...    msg=La rubrique ${rubrique} porte ${nb} case(s) à cocher, attendu exactement 1 : l'ancrage par containment ne tient plus.
    ${etat}=    Get Ui5 Property    selected    controlType=${DEMOKIT_CHECKBOX_TYPE}    containedIn=${rubrique}
    RETURN    ${etat}

Memoriser Les Bascules Borrowed
    [Documentation]    Relève l'état des cases « borrowed » RENDUES et le
    ...    publie en variable de suite, sans écraser un relevé précédent. Ces
    ...    cases n'existent que sur une fiche d'API : le scénario qui y touche
    ...    appelle ce keyword AVANT, sans quoi le teardown ne saurait rien
    ...    restaurer, et il le ferait en silence. L'état par défaut n'est pas
    ...    uniforme (la case des agrégations est cochée d'origine, relevé
    ...    2026-09-05) : on restaure l'état RELEVÉ, jamais un état supposé.
    ${etats}=    Create Dictionary    &{DEMOKIT_INITIAL_BORROWED}
    FOR    ${rubrique}    IN    @{DEMOKIT_RUBRIQUES_A_BASCULE}
        ${connue}=    Evaluate    $rubrique in $etats
        IF    ${connue}    CONTINUE
        ${present}=    Get Ui5 Match Count    controlType=${DEMOKIT_CHECKBOX_TYPE}    containedIn=${rubrique}
        IF    ${present} == 1
            ${valeur}=    Lire La Bascule Borrowed De La Rubrique    ${rubrique}
            Set To Dictionary    ${etats}    ${rubrique}=${valeur}
        END
    END
    Set Suite Variable    &{DEMOKIT_INITIAL_BORROWED}    &{etats}
    RETURN    ${etats}

Basculer Les Borrowed De La Rubrique
    [Documentation]    Clique la case « borrowed » de la rubrique et constate
    ...    l'INVERSION de sa propriété `selected` : la propriété est le seul
    ...    témoin de la bascule, le nombre de lignes de la table en est une
    ...    conséquence, pas une preuve.
    [Arguments]    ${rubrique}
    ${avant}=    Lire La Bascule Borrowed De La Rubrique    ${rubrique}
    ${attendu}=    Evaluate    not $avant
    Click Ui5 Control    controlType=${DEMOKIT_CHECKBOX_TYPE}    containedIn=${rubrique}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Bascule Borrowed Doit Valoir    ${rubrique}    ${attendu}
    RETURN    ${attendu}

La Bascule Borrowed Doit Valoir
    [Documentation]    Assertion sondable sur la propriété de la case.
    [Arguments]    ${rubrique}    ${attendu}
    ${etat}=    Lire La Bascule Borrowed De La Rubrique    ${rubrique}
    Should Be Equal    ${etat}    ${attendu}
    ...    msg=La bascule borrowed de la rubrique ${rubrique} vaut ${etat}, attendue ${attendu}.

Restaurer Les Bascules Borrowed
    [Documentation]    Teardown : remet chaque case « borrowed » relevée dans
    ...    son état d'origine, constaté sur la PROPRIÉTÉ. Ne fait rien pour une
    ...    rubrique absente de la page courante.
    FOR    ${rubrique}    ${attendu}    IN    &{DEMOKIT_INITIAL_BORROWED}
        ${present}=    Get Ui5 Match Count    controlType=${DEMOKIT_CHECKBOX_TYPE}    containedIn=${rubrique}
        IF    ${present} == 1
            ${etat}=    Lire La Bascule Borrowed De La Rubrique    ${rubrique}
            IF    $etat != $attendu
                Basculer Les Borrowed De La Rubrique    ${rubrique}
            END
        END
    END

Lire Les Noms Documentes Avec Provenance
    [Documentation]    Objets des contextes de liaison des lignes de la table
    ...    de la rubrique `${rubrique}` : le nom technique (`name`) et, sur les
    ...    entrées héritées, la clé `borrowedFrom`. Vérifie que CHAQUE ligne
    ...    porte son contexte (le contraire serait le « vert et faux » inverse
    ...    des tables de méthodes) et qu'aucun nom n'est vide.
    [Arguments]    ${rubrique}
    ${lignes}=    Get Ui5 Aggregation Info    ${DEMOKIT_DOC_ROW_AGGREGATION}
    ...    controlType=${DEMOKIT_DOC_TABLE_TYPE}    containedIn=${rubrique}
    Should Not Be Empty    ${lignes}
    ...    msg=La table de la rubrique ${rubrique} ne porte aucune ligne.
    ${objets}=    Evaluate    [l['binding']['object'] for l in $lignes if l.get('binding')]
    ${nb_lignes}=    Get Length    ${lignes}
    ${nb_objets}=    Get Length    ${objets}
    Should Be Equal As Integers    ${nb_objets}    ${nb_lignes}
    ...    msg=${nb_lignes} ligne(s) mais ${nb_objets} contexte(s) de liaison dans la rubrique ${rubrique} : des lignes sont illisibles par cette voie.
    ${vides}=    Evaluate    [o for o in $objets if not o.get('name')]
    Should Be Empty    ${vides}
    ...    msg=Des lignes de la rubrique ${rubrique} n'exposent aucun nom technique : ${vides}
    RETURN    ${objets}

La Provenance Des Lignes Doit Etre Coherente
    [Arguments]    ${objets_avant}    ${objets_apres}
    [Documentation]    Verdict de provenance de la bascule : aucune ligne
    ...    d'AVANT ne portait `borrowedFrom` (la case était décochée), les
    ...    lignes PROPRES d'après sont exactement celles d'avant, et chaque
    ...    ligne AJOUTÉE porte `borrowedFrom`. L'échec nomme les lignes en
    ...    cause.
    ${deja_empruntees}=    Evaluate
    ...    sorted(o.get('name', '') for o in $objets_avant if o.get('${DEMOKIT_DOC_BORROWED_MARKER}'))
    Should Be Empty    ${deja_empruntees}
    ...    msg=Des lignes portaient ${DEMOKIT_DOC_BORROWED_MARKER} avant la bascule : ${deja_empruntees}
    ${propres_apres}=    Evaluate
    ...    sorted(o.get('name', '') for o in $objets_apres if not o.get('${DEMOKIT_DOC_BORROWED_MARKER}'))
    ${noms_avant}=    Evaluate    sorted(o.get('name', '') for o in $objets_avant)
    Should Be Equal    ${propres_apres}    ${noms_avant}
    ...    msg=Les lignes propres après bascule (${propres_apres}) ne sont pas celles d'avant (${noms_avant}).
    ${ajoutees_sans_provenance}=    Evaluate
    ...    sorted(set(o.get('name', '') for o in $objets_apres) - set($noms_avant) - set(o.get('name', '') for o in $objets_apres if o.get('${DEMOKIT_DOC_BORROWED_MARKER}')))
    Should Be Empty    ${ajoutees_sans_provenance}
    ...    msg=Des lignes ajoutées par la bascule ne portent pas ${DEMOKIT_DOC_BORROWED_MARKER} : ${ajoutees_sans_provenance}

La Doc Complete Doit Egaler Le Controle Vivant
    [Documentation]    L'assertion reine : bascule « borrowed » activée,
    ...    l'ensemble des noms documentés est ÉGAL à l'ensemble des propriétés
    ...    d'une instance vivante du contrôle, MODULO l'inventaire déclaré
    ...    `@{DEMOKIT_PROPS_HORS_FICHE}` (propriétés à valeur non primitive que
    ...    la fiche du vivant, réduite aux primitives, ne matérialise pas :
    ...    relevé à la génération, voir les écarts du plan). L'inventaire est à
    ...    compte exact : une tolérance MORTE (propriété redevenue lisible sur
    ...    le vivant) fait échouer, comme un écart de plus.
    [Arguments]    ${objets}    ${vivantes}
    ${documentes}=    Evaluate    sorted({o.get('name', '') for o in $objets})
    ${tolerees}=    Evaluate    set($DEMOKIT_PROPS_HORS_FICHE)
    ${manque_vivant}=    Evaluate    sorted(set($documentes) - set($vivantes) - $tolerees)
    Should Be Empty    ${manque_vivant}
    ...    msg=Des propriétés documentées n'existent pas sur le contrôle vivant : ${manque_vivant}
    ${manque_doc}=    Evaluate    sorted(set($vivantes) - set($documentes))
    Should Be Empty    ${manque_doc}
    ...    msg=Des propriétés du contrôle vivant ne sont pas documentées, même bascule borrowed activée : ${manque_doc}
    ${tolerance_morte}=    Evaluate    sorted($tolerees & set($vivantes))
    Should Be Empty    ${tolerance_morte}
    ...    msg=Des entrées de l'inventaire DEMOKIT_PROPS_HORS_FICHE sont désormais lisibles sur le contrôle vivant, l'inventaire est à purger : ${tolerance_morte}

Lire La Chaine D Heritage Documentee
    [Documentation]    Noms d'ancêtres portés par les listes d'éléments
    ...    empruntés de la rubrique `${rubrique}` (contrôles dédiés du SDK,
    ...    contextes `/borrowed/<rubrique>/<n>`), dans l'ordre du registre :
    ...    la chaîne d'héritage complète, en clés techniques.
    [Arguments]    ${rubrique}
    ${fiches}=    Get Ui5 Control Info    controlType=${DEMOKIT_BORROWED_LIST_TYPE}
    ...    containedIn=${rubrique}
    Should Not Be Empty    ${fiches}
    ...    msg=La rubrique ${rubrique} ne porte aucune liste d'éléments empruntés.
    ${ancetres}=    Evaluate
    ...    [((f.get('binding') or {}).get('object') or {}).get('name', '') for f in $fiches]
    ${vides}=    Evaluate    [a for a in $ancetres if not a]
    Should Be Empty    ${vides}
    ...    msg=Des listes d'emprunts ne nomment aucun ancêtre dans la rubrique ${rubrique}.
    RETURN    ${ancetres}

La Chaine D Heritage Doit Porter
    [Documentation]    Inclusion d'un ancêtre dans la chaîne documentée. La
    ...    longueur et l'ordre de la chaîne suivent le SDK : ils se
    ...    journalisent, ils ne se gravent pas.
    [Arguments]    ${ancetres}    ${ancetre}
    List Should Contain Value    ${ancetres}    ${ancetre}
    ...    msg=La chaîne d'héritage documentée ne porte pas ${ancetre} : ${ancetres}

Les Ancetres Doivent Etre Des Noms Qualifies
    [Documentation]    Assertion structurelle : chaque ancêtre est un nom
    ...    qualifié technique du namespace `sap.`.
    [Arguments]    ${ancetres}
    ${intrus}=    Evaluate    [a for a in $ancetres if not a.startswith('sap.')]
    Should Be Empty    ${intrus}
    ...    msg=Des ancêtres documentés ne sont pas des noms qualifiés sap.* : ${intrus}

# =============================================================================
# Galerie d'échantillons et vue du code source
# =============================================================================

Ouvrir La Galerie D Echantillons
    [Documentation]    Navigue vers la galerie d'échantillons de l'entité
    ...    `${nom_qualifie}` et attend ses témoins. Même garde de rejouabilité
    ...    que `Ouvrir La Fiche D Api` : la galerie DÉJÀ affichée passe par un
    ...    rechargement, sans quoi le titre du document est réinitialisé sans
    ...    jamais revenir.
    [Arguments]    ${nom_qualifie}
    ${emplacement}=    Get Page Location
    ${deja}=    Evaluate    $emplacement['fragment'] == '/entity/' + $nom_qualifie
    IF    ${deja}
        Reload
        Attendre Le Runtime Du Demo Kit
    ELSE
        Go To    ${DEMOKIT_URL}#/entity/${nom_qualifie}
    END
    Attendre Le Repos Du Demo Kit
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    La Galerie Affichee Doit Etre    ${nom_qualifie}

La Galerie Affichee Doit Etre
    [Documentation]    Les témoins d'arrivée sur la galerie : fragment, titre
    ...    du document commençant par le nom qualifié, et section active
    ...    `controls` constatée sur le SEUL témoin du shell (la clé
    ...    sélectionnée) : les routes de la section des échantillons ne
    ...    portent PAS la clé (`/entity/...` sous `controls`, mesuré au
    ...    premier run), le témoin de fragment du cas général y serait faux.
    [Arguments]    ${nom_qualifie}
    Le Fragment Doit Porter    /entity/${nom_qualifie}
    ${titre}=    Get Title
    Should Start With    ${titre}    ${nom_qualifie}
    ...    msg=Le titre du document est « ${titre} », attendu commençant par ${nom_qualifie}.
    La Cle De Section Active Doit Etre    controls

La Cle De Section Active Doit Etre
    [Documentation]    Le témoin SHELL seul : la clé sélectionnée du conteneur
    ...    d'onglets. Pour les sections dont les routes portent la clé, le
    ...    couple complet reste `La Section Active Doit Etre` ; celui-ci sert
    ...    les routes qui ne la portent pas (galerie et échantillons sous
    ...    `controls`).
    [Arguments]    ${cle}
    ${selection}=    Get Ui5 Property    selectedKey    idSuffix=${DEMOKIT_NAV_HEADER}
    Should Be Equal    ${selection}    ${cle}
    ...    msg=Le conteneur d'onglets déclare la section ${selection}, attendue ${cle}.

Lire Les Echantillons De La Galerie
    [Documentation]    Les échantillons de la galerie, lus par les DEUX voies
    ...    en un seul verdict de cohérence : la table (une vraie `sap.m.Table`,
    ...    contrairement aux tables de doc des fiches d'API) et les contextes
    ...    de liaison des lignes, porteurs des clés techniques (`id` de
    ...    l'échantillon, `entityId`, `library`, `key` : la route d'exécution).
    ...    Retourne les contextes, dans l'ordre des lignes.
    ${rendues}=    Read Ui5 Table    idSuffix=${DEMOKIT_ENTITY_TABLE}
    ${fiches}=    Get Ui5 Control Info    controlType=${DEMOKIT_ENTITY_ROW_TYPE}
    ...    containedIn=${DEMOKIT_ENTITY_TABLE}
    ${contextes}=    Evaluate    [((f.get('binding') or {}).get('object') or {}) for f in $fiches]
    Should Not Be Empty    ${contextes}
    ...    msg=La galerie ne porte aucune ligne d'échantillon.
    ${nb_rendues}=    Get Length    ${rendues}
    ${nb_contextes}=    Get Length    ${contextes}
    Should Be Equal As Integers    ${nb_contextes}    ${nb_rendues}
    ...    msg=La table rend ${nb_rendues} ligne(s) mais ${nb_contextes} contexte(s) de liaison : les deux voies de lecture divergent.
    RETURN    ${contextes}

Les Echantillons Doivent Porter Leurs Cles
    [Documentation]    Verdict structurel des clés techniques d'une liste
    ...    d'échantillons : `id` préfixé par `<library>.sample.`, `entityId`
    ...    ÉGAL à l'entité de la galerie, route d'exécution non vide. L'échec
    ...    nomme les lignes en cause.
    [Arguments]    ${contextes}    ${nom_qualifie}
    ${intrus}=    Create List
    FOR    ${contexte}    IN    @{contextes}
        ${conforme}=    Evaluate
        ...    $contexte.get('id', '').startswith($contexte.get('library', '') + '.sample.') and $contexte.get('entityId', '') == $nom_qualifie and bool($contexte.get('key'))
        IF    not ${conforme}    Append To List    ${intrus}    ${contexte}
    END
    Should Be Empty    ${intrus}
    ...    msg=Des échantillons ne portent pas leurs clés techniques (id préfixé par la bibliothèque, entityId égal à l'entité, route non vide) : ${intrus}

Ouvrir L Echantillon Par Sa Ligne
    [Documentation]    Clique la ligne de rang `${rang}` de la galerie (son
    ...    identifiant est DÉCOUVERT à l'instant, jamais écrit) et attend la
    ...    route d'exécution de l'échantillon `${id_echantillon}` (lu de la
    ...    galerie, jamais en dur : la campagne survit à l'ajout d'un
    ...    échantillon).
    [Arguments]    ${rang}    ${id_echantillon}
    ${identifiants}=    Get Ui5 Ids    controlType=${DEMOKIT_ENTITY_ROW_TYPE}
    ...    containedIn=${DEMOKIT_ENTITY_TABLE}
    Click Ui5 Control    id=${identifiants}[${rang}]
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Le Fragment D Echantillon Doit Etre    ${id_echantillon}
    Attendre Le Repos Du Demo Kit

Le Fragment D Echantillon Doit Etre
    [Documentation]    Le fragment se termine par `/sample/<id>` : la borne
    ...    finale évite qu'un identifiant préfixe d'un autre (Button,
    ...    ButtonWithBadge) passe pour lui.
    [Arguments]    ${id_echantillon}
    ${emplacement}=    Get Page Location
    Should End With    ${emplacement}[fragment]    /sample/${id_echantillon}
    ...    msg=Le fragment est ${emplacement}[fragment], attendu se terminant par /sample/${id_echantillon}.

La Barre D Echantillon Doit Etre Percue
    [Documentation]    La barre d'outils de l'échantillon est rendue : le
    ...    bouton de la vue code, et les boutons INTERDITS de cette campagne
    ...    (ouverture d'onglet, mode adaptation runtime), PERÇUS pour prouver
    ...    la barre, jamais actionnés (lecture seule).
    ${nb}=    Get Ui5 Match Count    idSuffix=${DEMOKIT_SAMPLE_CODE_BUTTON}
    Should Be Equal As Integers    ${nb}    1
    ...    msg=Le bouton de la vue code n'est pas rendu (${nb} correspondance(s)).
    FOR    ${interdit}    IN    @{DEMOKIT_SAMPLE_TOOLBAR_INTERDITS}
        ${present}=    Get Ui5 Match Count    idSuffix=${interdit}
        Should Be Equal As Integers    ${present}    1
        ...    msg=Le bouton ${interdit} de la barre d'échantillon n'est pas rendu (${present} correspondance(s)).
    END

Ouvrir La Vue Du Code Source
    [Documentation]    Ouvre la vue du code source par son bouton stable et
    ...    attend la route `/code`. Le bouton de téléchargement y est PERÇU
    ...    (id stable), jamais cliqué : il écrit sur le disque. Sa perception
    ...    est une attente ACTIVE : la barre de la vue code est rendue APRÈS
    ...    la route (mesuré au premier run : 0 correspondance juste après le
    ...    fragment, 1 ensuite).
    Click Ui5 Control    idSuffix=${DEMOKIT_SAMPLE_CODE_BUTTON}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Le Fragment Doit Se Terminer Par    ${DEMOKIT_CODE_ROUTE_SUFFIX}
    Attendre Le Repos Du Demo Kit
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Le Bouton De Telechargement Doit Etre Rendu
    # Les onglets de fichier arrivent APRÈS le bouton de téléchargement
    # (mesuré live : bouton rendu, liste de clés encore vide, puis les trois
    # fichiers) : la vue code n'est prête qu'avec ses onglets.
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Des Onglets De Fichier Doivent Etre Rendus

Des Onglets De Fichier Doivent Etre Rendus
    [Documentation]    Assertion sondable : au moins un onglet de fichier à
    ...    clé NON VIDE est rendu dans la vue code (l'onglet technique à clé
    ...    vide ne compte pas).
    ${brutes}=    Get Ui5 Properties    key    controlType=${DEMOKIT_FILE_TAB_TYPE}
    ...    containedIn=${DEMOKIT_CODE_FILE_EDITOR}
    ${cles}=    Evaluate    [c for c in $brutes if c]
    Should Not Be Empty    ${cles}
    ...    msg=La vue code ne rend encore aucun onglet de fichier à clé non vide.

Le Bouton De Telechargement Doit Etre Rendu
    [Documentation]    Assertion sondable : le bouton de téléchargement de la
    ...    vue code est rendu, exactement une fois. Perçu, jamais cliqué.
    ${present}=    Get Ui5 Match Count    idSuffix=${DEMOKIT_CODE_DOWNLOAD}
    Should Be Equal As Integers    ${present}    1
    ...    msg=Le bouton de téléchargement de la vue code n'est pas rendu (${present} correspondance(s)).

Le Fragment Doit Se Terminer Par
    [Documentation]    Assertion sondable de fin de fragment d'URL.
    [Arguments]    ${suffixe}
    ${emplacement}=    Get Page Location
    Should End With    ${emplacement}[fragment]    ${suffixe}
    ...    msg=Le fragment est ${emplacement}[fragment], attendu se terminant par ${suffixe}.

Lister Les Fichiers De L Echantillon
    [Documentation]    Clés des onglets de fichier de la vue code : la `key`
    ...    d'un onglet EST le nom de fichier. Un onglet technique à clé VIDE
    ...    est rendu à côté des fichiers (relevé live) : les clés vides sont
    ...    filtrées.
    ${brutes}=    Get Ui5 Properties    key    controlType=${DEMOKIT_FILE_TAB_TYPE}
    ...    containedIn=${DEMOKIT_CODE_FILE_EDITOR}
    ${cles}=    Evaluate    [c for c in $brutes if c]
    Should Not Be Empty    ${cles}
    ...    msg=La vue code ne porte aucun onglet de fichier.
    RETURN    ${cles}

Lire Le Fichier Selectionne
    [Documentation]    Clé du fichier actuellement affiché, lue sur le
    ...    `selectedKey` du conteneur d'onglets de la vue code.
    ${cle}=    Get Ui5 Property    selectedKey    controlType=${DEMOKIT_ANCHOR_BAR_TYPE}
    ...    containedIn=${DEMOKIT_CODE_FILE_EDITOR}
    RETURN    ${cle}

Choisir Le Fichier
    [Documentation]    Bascule vers le fichier `${cle}` par son onglet, et
    ...    constate que le `selectedKey` a suivi. Geste purement local : le
    ...    témoin est la propriété, jamais le réseau.
    [Arguments]    ${cle}
    ${motif}=    Motif Exact    ${cle}
    Click Ui5 Control    controlType=${DEMOKIT_FILE_TAB_TYPE}
    ...    containedIn=${DEMOKIT_CODE_FILE_EDITOR}    properties={'key': '${motif}'}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Le Fichier Selectionne Doit Etre    ${cle}

Le Fichier Selectionne Doit Etre
    [Documentation]    Assertion sondable sur la clé du fichier affiché.
    [Arguments]    ${cle}
    ${courante}=    Lire Le Fichier Selectionne
    Should Be Equal    ${courante}    ${cle}
    ...    msg=Le fichier sélectionné est ${courante}, attendu ${cle}.

Lire Le Source De L Editeur
    [Documentation]    Contenu de l'éditeur de code (propriété `value` du
    ...    CodeEditor) : le SOURCE réel du fichier affiché.
    ${source}=    Get Ui5 Property    value    idSuffix=${DEMOKIT_CODE_EDITOR}
    RETURN    ${source}

Le Source Doit Porter L Identifiant
    [Documentation]    Le source affiché est non vide et porte l'identifiant
    ...    technique de l'échantillon : la vue code montre bien LE code de CET
    ...    échantillon.
    [Arguments]    ${source}    ${id_echantillon}
    Should Not Be Empty    ${source}
    ...    msg=L'éditeur de code est vide.
    Should Contain    ${source}    ${id_echantillon}
    ...    msg=Le source affiché ne porte pas l'identifiant technique ${id_echantillon}.

Passer A L Echantillon Suivant
    [Documentation]    Actionne « échantillon suivant » depuis la vue code et
    ...    attend le fragment de l'échantillon `${id_suivant}`, toujours
    ...    terminé par `/code` : la vue ne change pas, seul l'échantillon
    ...    change.
    [Arguments]    ${id_suivant}
    Click Ui5 Control    idSuffix=${DEMOKIT_CODE_NEXT}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Le Fragment De Code Doit Porter    ${id_suivant}
    Attendre Le Repos Du Demo Kit

Revenir A L Echantillon Precedent
    [Documentation]    Actionne « échantillon précédent » depuis la vue code
    ...    et attend le fragment de l'échantillon `${id_precedent}`, toujours
    ...    terminé par `/code`.
    [Arguments]    ${id_precedent}
    Click Ui5 Control    idSuffix=${DEMOKIT_CODE_PREV}
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Le Fragment De Code Doit Porter    ${id_precedent}
    Attendre Le Repos Du Demo Kit

Le Fragment De Code Doit Porter
    [Documentation]    Le fragment porte `/sample/<id>/` (la borne du
    ...    séparateur évite qu'un identifiant préfixe d'un autre passe pour
    ...    lui) ET se termine par `/code`.
    [Arguments]    ${id_echantillon}
    ${emplacement}=    Get Page Location
    Should Contain    ${emplacement}[fragment]    /sample/${id_echantillon}/
    ...    msg=Le fragment est ${emplacement}[fragment], attendu portant /sample/${id_echantillon}/.
    Should End With    ${emplacement}[fragment]    ${DEMOKIT_CODE_ROUTE_SUFFIX}
    ...    msg=Le fragment est ${emplacement}[fragment], attendu se terminant par ${DEMOKIT_CODE_ROUTE_SUFFIX} : la navigation a quitté la vue code.

# =============================================================================
# Demo Apps et Resources : perception seule
# =============================================================================

Compter Les Cartes Demo Apps
    [Documentation]    Nombre de cartes d'applications rendues dans la zone
    ...    PRINCIPALE de la page Demo Apps (comptage porté : cette SPA
    ...    accumule les cartes des autres sections).
    ${nb}=    Get Ui5 Match Count    controlType=${DEMOKIT_CARD_TYPE}
    ...    containedIn=${DEMOKIT_DEMOAPPS_MAIN}
    RETURN    ${nb}

Attendre Les Cartes Demo Apps
    [Documentation]    Attente ACTIVE des cartes de la zone principale : elles
    ...    arrivent APRÈS les deux témoins de section (mesuré au premier run :
    ...    comptage 0 juste après l'activation de la section, 9 ensuite).
    ...    Retourne le comptage.
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Des Cartes Doivent Etre Rendues Dans    ${DEMOKIT_DEMOAPPS_MAIN}
    ${nb}=    Compter Les Cartes Demo Apps
    RETURN    ${nb}

Attendre Les Cartes De Resources
    [Documentation]    Attente ACTIVE des cartes de la vue Resources, même
    ...    motif d'arrivée différée que la zone Demo Apps. Retourne le
    ...    comptage.
    Wait Until Keyword Succeeds    ${DEMOKIT_TIMEOUT}    ${DEMOKIT_POLL}
    ...    Des Cartes Doivent Etre Rendues Dans    ${DEMOKIT_RESOURCES_VIEW}
    ${nb}=    Compter Les Cartes De Resources
    RETURN    ${nb}

Des Cartes Doivent Etre Rendues Dans
    [Documentation]    Assertion sondable : au moins une carte rendue dans la
    ...    portée donnée.
    [Arguments]    ${portee}
    ${nb}=    Get Ui5 Match Count    controlType=${DEMOKIT_CARD_TYPE}
    ...    containedIn=${portee}
    Should Be True    ${nb} > 0
    ...    msg=Aucune carte rendue dans la portée ${portee}.

Lister Les Liens Demo Apps
    [Documentation]    Les `href` de toutes les ancres de la zone principale
    ...    de Demo Apps, valeurs d'ATTRIBUT brutes (un lien relatif reste
    ...    relatif) : la matière du verdict de localité.
    ${zone}=    Resolve Ui5 Control    idSuffix=${DEMOKIT_DEMOAPPS_MAIN}
    ${ancres}=    Get Elements    ${zone} a[href]
    ${liens}=    Create List
    FOR    ${ancre}    IN    @{ancres}
        ${href}=    Get Attribute    ${ancre}    href
        Append To List    ${liens}    ${href}
    END
    RETURN    ${liens}

Les Liens De Lancement Doivent Etre Locaux
    [Documentation]    Classe chaque lien de Demo Apps : RELATIF same-origin
    ...    (chemins `test-resources/...`, ancres sans cible) ou EXTERNE
    ...    DÉCLARÉ (hôtes de `@{DEMOKIT_EXTERNAL_LINK_HOSTS}`). Un lien absolu
    ...    vers un hôte non déclaré fait échouer en le nommant. Retourne le
    ...    classement `{locaux, externes}` pour le journal.
    [Arguments]    ${liens}
    ${locaux}=    Create List
    ${externes}=    Create List
    ${intrus}=    Create List
    FOR    ${lien}    IN    @{liens}
        ${absolu}=    Evaluate    '://' in $lien
        IF    not ${absolu}
            Append To List    ${locaux}    ${lien}
        ELSE
            ${declare}=    Evaluate    any(map(lambda h, v=$lien: h in v, $DEMOKIT_EXTERNAL_LINK_HOSTS))
            IF    ${declare}
                Append To List    ${externes}    ${lien}
            ELSE
                Append To List    ${intrus}    ${lien}
            END
        END
    END
    Should Be Empty    ${intrus}
    ...    msg=Des liens de Demo Apps ne sont ni relatifs same-origin ni externes déclarés : ${intrus}
    Should Not Be Empty    ${locaux}
    ...    msg=Aucun lien de lancement relatif same-origin dans la zone Demo Apps.
    ${classement}=    Create Dictionary    locaux=${locaux}    externes=${externes}
    RETURN    ${classement}

Compter Les Cartes De Resources
    [Documentation]    Nombre de cartes rendues DANS la vue Resources (la vue
    ...    n'a pas de conteneur de page à id stable : la portée est la vue
    ...    elle-même). Comptage porté, comme toute lecture de cette campagne.
    ${nb}=    Get Ui5 Match Count    controlType=${DEMOKIT_CARD_TYPE}
    ...    containedIn=${DEMOKIT_RESOURCES_VIEW}
    RETURN    ${nb}

# =============================================================================
# Sentinelle d'accumulation
# =============================================================================

L Iframe D Echantillon Doit Avoir Survecu
    [Documentation]    Le fait qui justifie toutes les lectures portées de
    ...    cette campagne : l'iframe d'échantillon SURVIT à la navigation,
    ...    invisible (comportement INVERSE du launchpad ABAP, qui détruit la
    ...    sienne au retour à l'accueil). L'assertion vise nommément l'iframe
    ...    d'échantillon dans la composition donnée : la vue code laisse une
    ...    seconde survivante (`sampleFrameEdit`, relevé à la génération), qui
    ...    se journalise sans se graver. Retourne la fiche de la frame.
    [Arguments]    ${composition}
    ${survivantes}=    Evaluate
    ...    [f for f in $composition.get('frames', []) if '"${DEMOKIT_SAMPLE_FRAME_ID}"' in f.get('selector', '')]
    Should Not Be Empty    ${survivantes}
    ...    msg=L'iframe d'échantillon a disparu de la composition : le comportement d'accumulation de cette cible a changé.
    ${visible}=    Evaluate    $survivantes[0].get('visible')
    Should Be Equal    ${visible}    ${False}
    ...    msg=L'iframe d'échantillon survivante est VISIBLE hors de sa page : ${survivantes}[0]
    RETURN    ${survivantes}[0]
