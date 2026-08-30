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
...                 Page object d'un **launchpad Fiori hébergé par un serveur
...                 ABAP** (FLP « ushell classique », service ICF
...                 `/sap/bc/ui2/flp`), par opposition au cFLP SAP Build Work
...                 Zone dont le page object voisin
...                 (`workzone_launchpad.resource`) ne s'applique PAS ici.
...
...                 Volontairement **paramétré par la cible** et non spécialisé
...                 sur un système : URL, identifiants, intents et marqueurs de
...                 classification sont des variables, pour qu'une seconde
...                 campagne sur une autre release ABAP réutilise ce fichier
...                 tel quel et éprouve précisément ce qui diffère.
...
...                 Relevé live le 2026-08-24 (rf-mcp : Browser +
...                 SapFioriLibrary) sur DEUX systèmes : un ABAP Platform 1909
...                 servant SAPUI5 1.71.47 (thème `sap_belize`) et un ABAP
...                 Platform 2023 servant SAPUI5 1.120.15 (thème
...                 `sap_horizon`), tous deux en anglais.
...
...                 **Les valeurs par défaut de ce fichier sont celles de la
...                 release 1.71** : c'est la première cible éprouvée, et une
...                 suite qui ne surcharge rien continue de la viser. Une
...                 campagne sur une autre release surcharge, dans sa propre
...                 section `*** Variables ***`, ce que la release a déplacé
...                 (voir le tableau « Ce qui diverge d'une release à l'autre »
...                 ci-dessous). Aucun mot-clé ne teste de numéro de version :
...                 la release entre par les variables, jamais par une
...                 condition.
...
...                 Ce qui diverge d'une release à l'autre, mesuré :
...
...                 | Rôle | 1.71 (défaut) | 1.120 |
...                 | Zone utilisateur | `meAreaHeaderButton` | `userActionsMenuHeaderButton` |
...                 | Son popover | `sapUshellMeAreaPopover` | `sapUshellUserActionsMenuPopover` |
...                 | Dialogue « à propos » | `aboutContainerDialogID` | `aboutDialogFragment--aboutDialog` |
...                 | Acquittement d'un REFUS | position 0 | **position 1** |
...                 | Clé d'une rubrique de paramètres | dans l'identifiant | dans le contexte de liaison |
...                 | Titre, intent et compteur d'une tuile | agrégations et contexte de liaison | **nœud DOM de la tuile** |
...                 | Service de contenu recherchable | absent | présent |
...
...
...                 Contrat de localisation, cinq règles apprises sur la cible
...                 réelle :
...
...                 1. **Aucune iframe.** L'application s'ouvre dans le
...                 document du shell : ni pile de frames, ni portée à empiler.
...                 Le témoin de « quelle application est ouverte » est le
...                 conteneur d'application dont l'id est DÉRIVÉ de l'intent
...                 (`application-<SemanticObject>-<action>`), donc ni généré
...                 ni traduit.
...                 2. **L'ancre est le SUFFIXE d'identifiant.** Les préfixes
...                 de vue sont générés et incrémentés à chaque ré-entrée, et
...                 l'identifiant d'une entrée de la zone utilisateur contient
...                 sa POSITION, qui change selon l'endroit.
...                 3. **Le catalogue se lit au service, pas à l'écran.** Le
...                 rendu de l'App Finder est paresseux (54 vignettes pour 67
...                 tuiles déclarées) et le service `SearchableContent` des
...                 cFLP n'existe pas sur ce ushell : la source est
...                 `LaunchPage`.
...                 4. **`visible` peut valoir vrai sur un contrôle jamais
...                 construit**, et un contrôle FERMÉ reste RENDU : ni un
...                 comptage ni une résolution ne disent qu'un dialogue est
...                 ouvert. C'est `Get Ui5 Open Popups` qui le dit.
...                 5. **Tout libellé visible est traduit.** Ce que ces
...                 mots-clés retournent est locale-indépendant : intents,
...                 identifiants techniques, propriétés d'état, comptages.
...
...                 Convention 11 : ni identifiant ni mot de passe committés,
...                 tout entre par la ligne de commande.

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
# --- Cible et identité ------------------------------------------------------
# L'URL est celle du service ICF du launchpad, en **HTTPS direct**. Ce n'est pas
# une préférence : la voie HTTP du même serveur redirige vers un nom d'hôte
# virtuel que plusieurs conteneurs ABAP d'un même poste peuvent annoncer, et on
# atterrit alors sur le launchpad d'un AUTRE système, avec une perception
# parfaitement cohérente et la mauvaise cible.
${ABAP_FLP_URL}                     ${EMPTY}
${ABAP_FLP_USER}                    ${EMPTY}
${ABAP_FLP_PASSWORD}                ${EMPTY}
${ABAP_FLP_HEADLESS}                ${True}
# Certificat auto-signé des images ABAP de démonstration. L'orthographe est
# exacte : `ignoreHttpsErrors` est refusée par la bibliothèque Browser.
${ABAP_FLP_IGNORE_HTTPS}            ${True}
${ABAP_FLP_VIEWPORT}                {'width': 1600, 'height': 1000}
# Budget d'attente du PREMIER chargement : sur un système froid, la compilation
# côté serveur des ressources ICF peut dépasser la minute. Un échec d'attente au
# tout premier appel n'est pas une panne, c'est ce budget.
${ABAP_FLP_BOOT_TIMEOUT}            180s
# Budget des opérations d'élément, distinct du précédent : le budget de boot
# appliqué à tout ferait durer chaque échec de localisateur trois minutes, ce
# qui rend une campagne rouge illisible.
${ABAP_FLP_TIMEOUT}                 30s
${ABAP_FLP_SETTLE}                  2 s
# Budget de retour au REPOS de la page (requêtes en vol + indicateurs busy).
# Distinct des deux précédents parce qu'il ne mesure pas la même chose : une
# application peut être rendue depuis longtemps et charger encore ses données.
# Mesuré 55 s sur une navigation arrière d'un système 2023 : le défaut de 15 s
# de la bibliothèque échoue alors en annonçant une requête en vol, ce qui se lit
# à tort comme une anomalie applicative. Se surcharge par cible, jamais en
# ajoutant un `Sleep` (convention 2).
${ABAP_FLP_IDLE_TIMEOUT}            60s
# URL réellement atteinte AVANT toute frappe, relevée par l'ouverture de session
# parce qu'elle n'existe qu'à cet instant.
${ABAP_FLP_URL_AVANT_CONNEXION}     ${EMPTY}

# --- Page de connexion ICF : aucun runtime UI5, moteur `dom` -----------------
# Sélecteurs CSS NUS, sans le préfixe `css=` : le moteur dom les reçoit en
# argument NOMMÉ (`css=<valeur>`) et la bibliothèque Browser en sélecteur
# préfixé. Les stocker préfixés interdirait le premier usage.
#
# Les identifiants sont écrits en sélecteur d'ATTRIBUT et non avec un dièse :
# une valeur de cellule qui commence par `#` est un COMMENTAIRE Robot, donc
# `#LOGIN_LINK` rendait une variable VIDE. Le dry run ne peut pas voir ce piège
# (une chaîne vide reste une chaîne) : il s'est payé au premier run live, par un
# clic sur un sélecteur vide qui a expiré au bout du budget du navigateur.
${ABAP_FLP_LOGIN_FORM}              [id="LOGIN_FORM"]
${ABAP_FLP_LOGIN_USER}              input[name="sap-user"]
${ABAP_FLP_LOGIN_PASSWORD}          input[name="sap-password"]
${ABAP_FLP_LOGIN_SUBMIT}            [id="LOGIN_LINK"]
${ABAP_FLP_LOGIN_LANGUAGES}         [id="LANGUAGE_SELECT"]
# La CLASSE est l'ancre de TYPE du refus ; le texte du message est traduit.
${ABAP_FLP_LOGIN_ERROR}             .loginMessage.sapUiError

# --- Shell : identifiants STABLES, ancrés par suffixe ------------------------
${ABAP_FLP_SHELL_HEAD_ITEM}         sap.ushell.ui.shell.ShellHeadItem
# Zone utilisateur : l'ancre ET le type ont bougé d'une release à l'autre (en
# 1.120 ce n'est plus un `ShellHeadItem` mais un `sap.m.Avatar`), d'où la
# variable. Le mot-clé qui l'ouvre ne vise qu'un SUFFIXE d'identifiant, donc le
# changement de type ne le concerne pas : seul le comptage des éléments de barre
# shell le voit, et c'est la suite qui porte ce nombre.
${ABAP_FLP_ME_AREA_BUTTON}          meAreaHeaderButton
${ABAP_FLP_ME_AREA_POPOVER}         sapUshellMeAreaPopover
# Suffixe commun aux entrées de la zone utilisateur : leur id se termine par
# l'action (`-aboutBtn`), après un index qui, lui, bouge.
${ABAP_FLP_ME_AREA_ACTION}          Btn
${ABAP_FLP_ME_AREA_ITEM}            sap.m.StandardListItem
# Moyen de REFERMER le popover de la zone utilisateur, sous forme du nom du
# mot-clé qui sait le faire. Une stratégie nommée plutôt qu'un enchaînement
# « essayer ceci puis cela », qui masquerait laquelle des deux voies a réellement
# fermé le popover.
#
# Le défaut est la BASCULE (un second clic sur le bouton d'ouverture), et il l'est
# devenu après mesure : l'échappement ne referme rien sur la release 1.120 (le
# clic d'ouverture n'y déplace pas le focus dans le popover), et sur la 1.71 il
# dépend de l'endroit où se trouve le focus, ce qui l'a rendu vert un run et
# rouge le suivant sur le même écran. La bascule, elle, referme sur les DEUX
# releases, vérifié live sur chacune.
${ABAP_FLP_ME_AREA_FERMETURE}       Fermer La Zone Utilisateur Par Bascule
${ABAP_FLP_ABOUT_ENTRY}             -aboutBtn
${ABAP_FLP_SETTINGS_ENTRY}          -userSettingsBtn
${ABAP_FLP_APPFINDER_ENTRY}         -openCatalogBtn
${ABAP_FLP_EDIT_ENTRY}              -ActionModeBtn
${ABAP_FLP_LOGOUT_ENTRY}            -logoutBtn
${ABAP_FLP_ACTIVITIES_ENTRY}        -recentActivitiesBtn
# Panneau des activités : identifiants stables, relevés sur la release 1.120.
# Le popup qui PORTE le panneau n'est pas nommé ici à dessein : sa nature
# dépend de la release (panneau replié dans le popover, ou boîte de dialogue),
# et le témoin d'ouverture retenu est la liste elle-même.
${ABAP_FLP_ACTIVITIES_LIST}         sapUshellActivityListrecentActivities
${ABAP_FLP_ACTIVITIES_RECENT_TAB}    recentActivityFilter
${ABAP_FLP_ACTIVITIES_FREQUENT_TAB}    frequentlyUsedFilter
${ABAP_FLP_BACK_BUTTON}             backBtn
${ABAP_FLP_APP_TITLE}               shellAppTitle
${ABAP_FLP_SEARCH_BUTTON}           sf
${ABAP_FLP_SEARCH_INPUT}            searchFieldInShell-input
# Ouverture de la recherche : le premier clic ne rend pas le champ (mesuré live
# le 2026-08-29 sur la 1.71), donc l'ouverture se retente jusqu'à ce que le
# champ occupe une surface. Trois passages suffisent largement, le second
# ouvrant en pratique.
${ABAP_FLP_SEARCH_ESSAIS}           3x
${ABAP_FLP_SEARCH_PAUSE}            1s
${ABAP_FLP_ALL_APPS_LIST}           sapUshellAllMyAppsDataSourcesList
${ABAP_FLP_ALL_APPS_ENTRY}          sap.m.CustomListItem
# Le mode édition de l'accueil se CONSTATE par son bouton de validation : la
# barre de pied de page, elle, n'est pas rendue comme telle (relevé live).
${ABAP_FLP_EDIT_DONE}               sapUshellDashboardFooterDoneBtn

# --- Dialogues ---------------------------------------------------------------
${ABAP_FLP_ABOUT_DIALOG}            aboutContainerDialogID
${ABAP_FLP_SETTINGS_DIALOG}         userSettingsDialog
${ABAP_FLP_SETTINGS_CANCEL}         userSettingCancelButton
${ABAP_FLP_SETTINGS_ENTRY_SUFFIX}    -UserSettingsEntry
${ABAP_FLP_SETTINGS_LIST}           userSettingEntryList
# SOURCE de la clé technique d'une rubrique de paramètres, sous forme du nom du
# mot-clé qui sait la lire. En 1.71 la clé vit dans l'identifiant
# (`themes-UserSettingsEntry`) ; en 1.120 l'identifiant est entièrement généré
# (`__item3-settingsView--userSettingEntryList-2`) et la clé n'existe plus que
# dans le contexte de liaison. Une stratégie nommée plutôt qu'une condition :
# ajouter une release, c'est ajouter un mot-clé de lecture, pas une branche.
${ABAP_FLP_RUBRIQUES_STRATEGIE}     Lire Les Rubriques Par Suffixe D Identifiant
# STRATÉGIE de lecture des tuiles de l'accueil, sous forme du nom du mot-clé qui
# sait le faire. En 1.71 le titre vit dans les agrégations et l'intent dans le
# contexte de liaison ; en 1.120 la tuile est rendue par un composant séparé,
# ni l'un ni l'autre ne répond, et seule la relation de CONTAINMENT DOM atteint
# les contrôles qui portent réellement ces valeurs. Une stratégie nommée, encore,
# plutôt qu'une condition de version.
${ABAP_FLP_TUILES_STRATEGIE}        Lire Les Tuiles Par Agregation
${ABAP_FLP_ERROR_STATE}             Error
# Position d'acquittement dans un dialogue : les boutons portent un id généré et
# un texte traduit, la position est leur seule adresse stable.
#
# DEUX positions, et pas une constante unique : c'est l'écart le plus piégeux
# entre les deux releases, parce qu'il rend un test vert ici et rouge là sans
# changer une ligne de code. En 1.120 le dialogue de REFUS de navigation offre
# `[0] Copy` et `[1] Close` : acquitter en position 0 copie le message technique
# et laisse le dialogue ouvert (vécu live, échec après 20 s d'attente d'une
# fermeture qui ne venait pas). La confirmation, elle, garde son OK en tête sur
# les deux releases.
${ABAP_FLP_CONFIRM_POSITION}        ${0}
${ABAP_FLP_ERROR_CONFIRM_POSITION}    ${0}

# --- App Finder et tuiles ----------------------------------------------------
${ABAP_FLP_APPFINDER_SEARCH}        appFinderSearch
${ABAP_FLP_CATALOG_SELECT}          catalogSelect
${ABAP_FLP_APPBOX}                  sap.ushell.ui.appfinder.AppBox
${ABAP_FLP_TILE}                    sap.m.GenericTile
# Contrôle de tuile de l'accueil (le porteur, pas son rendu) : c'est LUI dont le
# nœud DOM sert de portée à la lecture par containment.
${ABAP_FLP_HOME_TILE}               sap.ushell.ui.launchpad.Tile
# Bouton d'épinglage d'une vignette de l'App Finder : le SEUL contrôle
# d'écriture de ces campagnes, réservé au scénario réversible sous accord
# explicite (voir `Epingler L Application` / `Depingler L Application`).
${ABAP_FLP_PIN_BUTTON}              sap.ushell.ui.appfinder.PinButton
# Popover « ajouter à un groupe » ouvert par ce bouton, sa liste de cases à
# cocher (une par groupe, dans l'ORDRE des groupes du service) et son bouton de
# fermeture. Identifiants stables relevés live.
${ABAP_FLP_PIN_POPOVER}             groupsPopover-popover
${ABAP_FLP_PIN_GROUP_BOX}           sap.m.CheckBox
${ABAP_FLP_PIN_CLOSE}               closeButton
# Groupe visé par le cycle d'épinglage, par POSITION dans la liste du popover :
# le titre des groupes est traduit, l'ordre suit celui du service. 0 = le groupe
# d'accueil, présent sur les deux releases.
${ABAP_FLP_GROUPE_EPINGLAGE}        ${0}
# Accord EXPLICITE d'écriture. Vide par défaut : sans lui, le scénario
# d'épinglage est SAUTÉ, y compris dans un run complet de `tests/robot/`. Un tag
# seul dépendrait de la mémoire de celui qui lance la commande.
${ABAP_FLP_WRITE_OPT_IN}            ${EMPTY}
# Le conteneur d'application est nommé d'après l'intent : c'est l'ancre centrale
# de ce launchpad, celle qui remplace le test d'iframe des cFLP.
${ABAP_FLP_APP_CONTAINER_PREFIX}    application-

# --- Intents du shell --------------------------------------------------------
${ABAP_FLP_HOME_INTENT}             Shell-home
${ABAP_FLP_APPFINDER_INTENT}        Shell-appfinder
${ABAP_FLP_SEARCH_INTENT}           Action-search
# Catégorie de source de données de la recherche du shell : identifiant
# technique, contrairement au libellé « Apps » qui est traduit.
${ABAP_FLP_SEARCH_APPS_SOURCE}      $$APPS$$
# Intent FABRIQUÉ, de forme correcte et inconnu du système : la contre-preuve
# sans laquelle un service qui répondrait « oui » à tout resterait vert.
${ABAP_FLP_INTENT_INCONNU}          Foo-bar
${ABAP_FLP_FRAGMENT_MALFORME}       FragmentSansAction

# --- Classification des erreurs console --------------------------------------
# On CLASSE, on ne compte pas : une erreur attendue et tracée à un composant non
# déployé n'est pas un défaut, et un test qui compte devient rouge à la première
# ressource optionnelle absente. Chaque marqueur est cherché dans le texte ET
# dans l'origine de l'entrée.
@{ABAP_FLP_MARQUEURS_TUILE}         cts_abapvcs    Failed to update data via service
@{ABAP_FLP_MARQUEURS_RECHERCHE}     ESH_SEARCH_SRV    /sap/es/ina/
# Deux familles VIDES par défaut, à remplir par la cible qui les observe : le
# runtime 1.71 n'émet aucune dépréciation, celui de 1.120 en émet depuis le
# shell de SAP lui-même. Une famille vide ne classe rien, donc ce qu'elle
# couvrirait retomberait dans « autres » et ferait échouer l'exhaustivité :
# c'est voulu, on ne masque jamais ce qu'on n'a pas observé.
@{ABAP_FLP_MARQUEURS_DEPRECATION}    @{EMPTY}
@{ABAP_FLP_MARQUEURS_SESSION}       @{EMPTY}

# --- Perception du shell : keywords de bibliothèque (convention #12) ---------
# Les sondes ushell qui vivaient ici en JS inline (conteneur, identité,
# catalogues LaunchPage, groupes, résolvabilité d'intents, SearchableContent)
# sont devenues des keywords de SapFioriLibrary : `Flp Container Is Present`,
# `Get Flp User`, `List Flp Catalogs`, `List Flp Groups`,
# `Get Flp Intent Support`, `Flp Service Is Available`, `List Flp Apps`.
# Ce fichier n'en garde que la traduction en vocabulaire français, plus les
# DEUX sondes assumées ci-dessous (spécifiques à la release ou au geste).
# Tuiles RENDUES de l'accueil : titre lu sur la PROPRIÉTÉ d'en-tête (le rendu
# d'une tuile y ajoute sous-titre, compteur et libellé de compteur), intent lu
# dans le contexte de liaison (`getTileTarget` retourne null sur cet adaptateur)
# et valeur du compteur lue sur le contenu numérique.
#
# Sonde SPÉCIFIQUE À LA RELEASE, et c'est la divergence la plus coûteuse des
# deux cibles : en 1.120 le contexte de liaison rend un `target` VIDE et
# l'agrégation `content` ne porte plus qu'un `ComponentContainer`, si bien que
# cette version-ci retourne des titres et des intents vides SANS échouer. Le
# mot-clé qui l'exploite refuse désormais ce silence (voir
# `Lire Les Tuiles De L Accueil`), et la cible 1.120 déclare une autre STRATÉGIE
# de lecture (`${ABAP_FLP_TUILES_STRATEGIE}`), par containment DOM.
${ABAP_FLP_TUILES_JS}               () => { const E = sap.ui.require('sap/ui/core/Element'); const out = []; E.registry.forEach(c => { if (c.getMetadata().getName() !== 'sap.ushell.ui.launchpad.Tile' || !c.getDomRef()) return; const ctx = c.getBindingContext(); const o = (ctx && ctx.getObject()) || {}; const titres = [], valeurs = []; const walk = k => { if (!k || typeof k.getMetadata !== 'function') return; const n = k.getMetadata().getName(); if (n === 'sap.m.GenericTile' && k.getHeader) titres.push(k.getHeader() || ''); if (n === 'sap.m.NumericContent' && k.getValue) valeurs.push(k.getValue()); const agg = k.mAggregations || {}; Object.keys(agg).forEach(a => { const v = agg[a]; (Array.isArray(v) ? v : [v]).forEach(walk); }); }; (o.content || []).forEach(walk); out.push({titre: titres[0] || '', intent: String(o.target || '').replace(/^#/, '').split('?')[0], compteur: valeurs.length ? String(valeurs[0]) : '', dynamique: valeurs.length > 0}); }); return out; }
# Écriture directe d'un fragment dans l'URL : la seule façon de soumettre au
# shell une chaîne qui n'a PAS la forme d'un intent (`Open Fiori App` valide la
# forme). Sonde ASSUMÉE dans l'allowlist de check_conventions.py.
${ABAP_FLP_FRAGMENT_JS}             () => { window.location.hash = '__FRAGMENT__'; return window.location.hash; }
# Contrôles porteurs du titre et du compteur DANS le nœud d'une tuile, pour la
# lecture par containment (voir `Lire Les Tuiles Par Containment`).
${ABAP_FLP_TILE_HEADER}             sap.m.GenericTile
${ABAP_FLP_TILE_COUNTER}            sap.m.NumericContent
# Ancre HTML d'une tuile : c'est là que vit son intent sur les releases où le
# contexte de liaison ne le porte plus. Sélecteur CSS NU (le moteur le reçoit
# préfixé), `__ID__` remplacé par l'identifiant de la tuile relevé au même run.
${ABAP_FLP_TILE_ANCHOR}             [id="__ID__"] a[href]


*** Keywords ***
La Cible Et Les Identifiants Sont Fournis
    [Documentation]    Garde de prérequis, à appeler avant d'ouvrir quoi que ce
    ...    soit : sans elle, l'absence de cible se manifeste bien plus loin, par
    ...    un échec de navigation qui accuse le réseau.
    ...
    ...    Le mot de passe n'est JAMAIS mesuré : un type `Secret` refuse d'être
    ...    lu (« Could not get length of '<secret>' ») et l'erreur de garde
    ...    masquerait le vrai prérequis manquant.
    Should Not Be Empty    ${ABAP_FLP_URL}
    ...    msg=Cible absente : passer -v ABAP_FLP_URL:<url https du launchpad ABAP>.
    Should Start With    ${ABAP_FLP_URL}    https://
    ...    msg=La cible doit être attaquée en HTTPS direct : la voie HTTP redirige vers un nom d'hôte virtuel partagé et mène possiblement à un AUTRE système.
    Should Not Be Empty    ${ABAP_FLP_USER}
    ...    msg=Utilisateur absent : passer -v ABAP_FLP_USER:<utilisateur ABAP>.
    ${fourni}=    Secret Is Provided    ${ABAP_FLP_PASSWORD}
    Should Be True    ${fourni}
    ...    msg=Mot de passe absent : passer -v "ABAP_FLP_PASSWORD: Secret:<motdepasse>".

Ouvrir Le Launchpad ABAP
    [Documentation]    Suite Setup : ouvre le navigateur sur la page de connexion
    ...    du launchpad et RELÈVE l'URL réellement atteinte avant toute frappe.
    ...
    ...    Ce relevé est le cœur du premier scénario : sans lui, une page de
    ...    connexion servie par un autre serveur ABAP du même poste rendrait
    ...    toute la campagne verte sur la mauvaise cible. Il est publié en
    ...    variable de suite `${ABAP_FLP_URL_AVANT_CONNEXION}`.
    ...
    ...    La page est ouverte au niveau SUITE : l'auto-fermeture de la
    ...    bibliothèque Browser est au niveau TEST, une page ouverte pendant un
    ...    test disparaît à sa fin et les suivants échouent sur « No page open ».
    La Cible Et Les Identifiants Sont Fournis
    New Browser    ${BROWSER}    headless=${ABAP_FLP_HEADLESS}
    New Context    ignoreHTTPSErrors=${ABAP_FLP_IGNORE_HTTPS}    viewport=${ABAP_FLP_VIEWPORT}
    Set Browser Timeout    ${ABAP_FLP_TIMEOUT}
    New Page    ${ABAP_FLP_URL}
    ${url}=    Get Url
    Set Suite Variable    ${ABAP_FLP_URL_AVANT_CONNEXION}    ${url}

Fermer Le Launchpad ABAP
    [Documentation]    Suite Teardown : ferme le navigateur, donc la session
    ...    applicative avec lui, que la campagne se soit terminée ou non par une
    ...    déconnexion propre.
    Run Keyword And Ignore Error    Close Fiori

La Page De Connexion Est Rendue
    [Documentation]    Vérifie que la page atteinte est bien le formulaire de
    ...    connexion ICF : formulaire présent, et AUCUN runtime UI5 (cette page
    ...    n'en est pas une, elle relève du moteur `dom`).
    Wait For Elements State    css=${ABAP_FLP_LOGIN_FORM}    attached
    ${runtime}=    Ui5 Runtime Is Present
    Should Not Be True    ${runtime}
    ...    msg=Un runtime UI5 est présent sur ce qui devrait être la page de connexion ICF.
    ${champs}=    Compter Les Champs De Connexion
    RETURN    ${champs}

Compter Les Champs De Connexion
    [Documentation]    Compte les éléments du formulaire de connexion, un dict
    ...    `{utilisateur, mot_de_passe, langues, soumission}`. Comptages, jamais
    ...    de libellé : la page est traduite comme le reste.
    ${utilisateur}=    Get Dom Match Count    css=${ABAP_FLP_LOGIN_USER}
    ${mot_de_passe}=    Get Dom Match Count    css=${ABAP_FLP_LOGIN_PASSWORD}
    ${langues}=    Get Dom Match Count    css=${ABAP_FLP_LOGIN_LANGUAGES}
    ${soumission}=    Get Dom Match Count    css=${ABAP_FLP_LOGIN_SUBMIT}
    ${champs}=    Create Dictionary    utilisateur=${utilisateur}    mot_de_passe=${mot_de_passe}
    ...    langues=${langues}    soumission=${soumission}
    RETURN    ${champs}

Lire Les Langues De Connexion
    [Documentation]    Codes de langue proposés par le sélecteur de la page de
    ...    connexion, entrée vide exclue (le sélecteur porte une option vide en
    ...    tête, qui n'est pas une langue). Les CODES sont techniques, les
    ...    libellés qui les accompagnent ne le sont pas.
    ${nb}=    Get Dom Match Count    css=${ABAP_FLP_LOGIN_LANGUAGES}
    IF    ${nb} == 0    RETURN    ${{ [] }}
    ${options}=    Get Select Options    css=${ABAP_FLP_LOGIN_LANGUAGES}
    ${langues}=    Evaluate    [str(o['value']) for o in $options if o['value']]
    RETURN    ${langues}

Tenter Une Connexion
    [Documentation]    Remplit le formulaire ICF et le soumet, sans rien
    ...    présumer du résultat : sert aussi bien la branche nominale que la
    ...    branche de refus. Le mot de passe n'est jamais journalisé.
    [Arguments]    ${utilisateur}    ${mot_de_passe}
    Fill Dom Input    ${utilisateur}    css=${ABAP_FLP_LOGIN_USER}
    # Le type `Secret` traverse INTACT jusqu'au moteur, qui le déballe à la
    # frontière du navigateur : plus aucun déballage dans la couche Robot,
    # où la valeur claire entrait dans l'espace des variables (convention #12).
    ${niveau}=    Set Log Level    NONE
    Fill Dom Input    ${mot_de_passe}    css=${ABAP_FLP_LOGIN_PASSWORD}
    Set Log Level    ${niveau}
    Click Dom Element    css=${ABAP_FLP_LOGIN_SUBMIT}

La Connexion Est Refusee
    [Documentation]    Constate un refus d'authentification : le formulaire est
    ...    toujours là, un message portant la classe d'erreur du logon ICF est
    ...    rendu, et aucun runtime UI5 n'a été chargé. L'ancre est la CLASSE,
    ...    jamais le texte du message, qui est traduit.
    Wait For Elements State    css=${ABAP_FLP_LOGIN_ERROR}    visible
    ${erreurs}=    Get Dom Match Count    css=${ABAP_FLP_LOGIN_ERROR}
    Should Be True    ${erreurs} > 0
    ...    msg=Aucun message portant la classe d'erreur du logon ICF après une tentative refusée.
    ${formulaire}=    Get Dom Match Count    css=${ABAP_FLP_LOGIN_FORM}
    Should Be True    ${formulaire} > 0
    ...    msg=Le formulaire de connexion a disparu : la tentative refusée a pourtant laissé entrer.
    ${runtime}=    Ui5 Runtime Is Present
    Should Not Be True    ${runtime}
    ...    msg=Un runtime UI5 s'est chargé malgré une authentification refusée.

Se Connecter Au Launchpad
    [Documentation]    Connexion nominale, puis attente du shell RÉELLEMENT
    ...    rendu (pas seulement du runtime chargé).
    [Arguments]    ${utilisateur}=${ABAP_FLP_USER}    ${mot_de_passe}=${ABAP_FLP_PASSWORD}
    Tenter Une Connexion    ${utilisateur}    ${mot_de_passe}
    Le Shell Du Launchpad Est Rendu

Le Shell Du Launchpad Est Rendu
    [Documentation]    Sonde en trois marches, chacune nécessaire : le conteneur
    ...    ushell existe, la page revient au repos réseau, et le shell a
    ...    construit des contrôles. Un runtime chargé ne prouve aucun rendu.
    Wait Until Keyword Succeeds    ${ABAP_FLP_BOOT_TIMEOUT}    1s
    ...    Flp Container Should Be Present
    Wait For Ui5 Idle    settle=${ABAP_FLP_SETTLE}    timeout=${ABAP_FLP_IDLE_TIMEOUT}
    Wait Until Keyword Succeeds    60s    2s    Le Shell Porte Des Controles

Le Shell Porte Des Controles
    [Documentation]    Prédicat de rendu : la composition perçue annonce au
    ...    moins un contrôle UI5 construit.
    ${composition}=    Get Page Composition
    Should Be True    ${composition}[ui5_controls] > 0
    ...    msg=Aucun contrôle UI5 rendu : le shell du launchpad n'est pas là.

Attendre Que Le Shell Soit Construit
    [Documentation]    Attend que le shell ait construit au moins ce nombre de
    ...    contrôles, puis retourne sa composition.
    ...
    ...    Une ATTENTE et non une assertion instantanée, et la nuance a été payée
    ...    live : le shell se construit progressivement, et une mesure prise une
    ...    seule fois juste après le retour au repos a relevé 84 contrôles là où
    ...    le même écran en porte de 134 à 169 une seconde plus tard. Le message
    ...    d'échec disait « le shell n'a pas fini de se construire » : il avait
    ...    raison, et c'est bien pour cela qu'il fallait attendre plutôt que
    ...    conclure. Le plancher reste un plancher : jamais atteint, l'attente
    ...    échoue en le disant.
    [Arguments]    ${plancher}    ${budget}=60s
    Wait Until Keyword Succeeds    ${budget}    1s    Le Shell Porte Au Moins N Controles    ${plancher}
    ${composition}=    Lire La Composition De La Portee Courante
    RETURN    ${composition}

Le Shell Porte Au Moins N Controles
    [Documentation]    Prédicat de construction complète du shell.
    [Arguments]    ${plancher}
    ${composition}=    Get Page Composition
    Should Be True    ${composition}[ui5_controls] > ${plancher}
    ...    msg=Seulement ${composition}[ui5_controls] contrôles rendus : le shell n'a pas fini de se construire (plancher ${plancher}).

Lire La Composition De La Portee Courante
    [Documentation]    Composition perçue de la page : runtime, version, nombre
    ...    de contrôles, hôtes Web Components, iframes et moteurs recommandés.
    ${composition}=    Get Page Composition
    RETURN    ${composition}

Lire L Identite De Session
    [Documentation]    Utilisateur connecté, sa langue et son thème, lus au
    ...    conteneur ushell : la seule source qui dise ce que le SERVEUR a
    ...    ouvert, plutôt que ce que le test croit avoir demandé.
    ${brut}=    Get Flp User
    ${identite}=    Create Dictionary    utilisateur=${brut}[id]
    ...    langue=${brut}[language]    theme=${brut}[theme]
    RETURN    ${identite}

Compter Les Elements De La Barre Shell
    [Documentation]    Nombre d'éléments de la barre shell RENDUS. Assertion
    ...    structurelle et locale-indépendante : ce nombre diffère entre
    ...    l'accueil et une application, le shell y remplaçant un bouton par un
    ...    autre.
    ${nb}=    Get Ui5 Match Count    controlType=${ABAP_FLP_SHELL_HEAD_ITEM}
    RETURN    ${nb}

# --- Catalogue et résolvabilité ----------------------------------------------

Inventorier Les Catalogues
    [Documentation]    Catalogues assignés à l'utilisateur et leurs tuiles, lus
    ...    au service du shell : une liste de dicts `{id, tuiles}` où chaque
    ...    tuile porte `{intent, cible}`.
    ...
    ...    Source choisie à dessein : le service dit ce que l'utilisateur a le
    ...    DROIT d'ouvrir, là où l'App Finder ne rend que ce qui est filtré et
    ...    visible (mesuré : 54 vignettes rendues pour 67 tuiles déclarées).
    ${bruts}=    List Flp Catalogs
    ${catalogues}=    Create List
    FOR    ${cat}    IN    @{bruts}
        ${tuiles}=    Evaluate
        ...    [{'intent': t['intent'], 'cible': t['target_url']} for t in $cat['tiles']]
        ${entree}=    Create Dictionary    id=${cat}[id]    tuiles=${tuiles}
        Append To List    ${catalogues}    ${entree}
    END
    RETURN    ${catalogues}

Lire Les Intents Du Catalogue
    [Documentation]    Intents UNIQUES d'un inventaire de catalogues, triés.
    ...    Plusieurs tuiles peuvent viser le même intent : le dédoublonnage est
    ...    ce qui rend le nombre comparable d'un passage à l'autre.
    [Arguments]    ${catalogues}
    ${intents}=    Evaluate    sorted({t['intent'] for c in $catalogues for t in c['tuiles'] if t['intent']})
    RETURN    ${intents}

Compter Les Tuiles Du Catalogue
    [Documentation]    Volume total de tuiles déclarées par les catalogues.
    [Arguments]    ${catalogues}
    ${total}=    Evaluate    sum(len(c['tuiles']) for c in $catalogues)
    RETURN    ${total}

Le Service De Contenu Recherchable Est Disponible
    [Documentation]    Prédicat de branchement : le service de contenu
    ...    recherchable répond-il sur cette cible ? Vrai ou faux, jamais un
    ...    échec, parce que son absence n'est pas un défaut : c'est une
    ...    caractéristique de la release, et la campagne doit pouvoir se réduire
    ...    à la voie universelle en le disant plutôt qu'en échouant.
    ${disponible}=    Flp Service Is Available    SearchableContent
    RETURN    ${disponible}

Inventorier Les Applications Recherchables
    [Documentation]    Applications déclarées par le service de contenu
    ...    recherchable : une liste de dicts `{intent, titre}`.
    ...
    ...    La seconde voie d'inventaire, celle qui permet de RECOUPER le
    ...    catalogue au lieu de le croire sur parole. Sa granularité n'est pas
    ...    celle du service historique (il fusionne des visualisations qui
    ...    partagent une cible), donc ce sont les INTENTS qui se comparent, pas
    ...    les cardinalités.
    ${bruts}=    List Flp Apps
    # Priorité de titre conservée de la sonde historique : le titre de la
    # visualisation d'abord, le libellé de l'application à défaut.
    ${applications}=    Evaluate
    ...    [{'intent': a['intent'], 'titre': a['viz_title'] or a['title']} for a in $bruts]
    RETURN    ${applications}

Lire Les Intents Des Applications Recherchables
    [Documentation]    Intents UNIQUES d'un inventaire d'applications
    ...    recherchables, triés : la forme directement comparable aux intents du
    ...    catalogue.
    [Arguments]    ${applications}
    ${intents}=    Evaluate    sorted({a['intent'] for a in $applications if a['intent']})
    RETURN    ${intents}

Les Intents Sont Ils Resolvables
    [Documentation]    Soumet une liste d'intents au service de résolution de
    ...    navigation et retourne une liste de dicts `{intent, resolvable}`.
    ...
    ...    Un seul aller-retour pour toute la liste, et surtout une réponse par
    ...    intent : c'est ce qui permet de NOMMER l'écart plutôt que de conclure
    ...    globalement.
    [Arguments]    ${intents}
    ${verdicts}=    Get Flp Intent Support    ${intents}
    ${resolutions}=    Evaluate
    ...    [{'intent': v['intent'], 'resolvable': v['supported']} for v in $verdicts]
    RETURN    ${resolutions}

Separer Les Intents Non Resolvables
    [Documentation]    Sépare le verdict de résolvabilité en deux listes
    ...    `{resolvables, non_resolvables}`.
    [Arguments]    ${resolutions}
    ${oui}=    Evaluate    [r['intent'] for r in $resolutions if r['resolvable']]
    ${non}=    Evaluate    [r['intent'] for r in $resolutions if not r['resolvable']]
    ${bilan}=    Create Dictionary    resolvables=${oui}    non_resolvables=${non}
    RETURN    ${bilan}

# --- Accueil : groupes et tuiles ---------------------------------------------

Inventorier Les Groupes De L Accueil
    [Documentation]    Groupes de l'accueil et volume de chacun, lus au service :
    ...    une liste de dicts `{id, tuiles}`. L'ancre est l'identifiant TECHNIQUE
    ...    du groupe, jamais son titre : celui rendu à l'écran diffère de celui
    ...    que retourne le service, et les deux sont traduits.
    ${bruts}=    List Flp Groups
    ${groupes}=    Evaluate    [{'id': g['id'], 'tuiles': g['tile_count']} for g in $bruts]
    RETURN    ${groupes}

Lire Les Tuiles De L Accueil
    [Documentation]    Tuiles RENDUES de l'accueil : une liste de dicts
    ...    `{titre, intent, compteur, dynamique}`, lues par la STRATÉGIE de la
    ...    cible (`${ABAP_FLP_TUILES_STRATEGIE}`), qui n'est pas la même d'une
    ...    release à l'autre : ce que l'une trouve dans les agrégations et le
    ...    contexte de liaison, l'autre ne le trouve qu'en descendant dans le
    ...    nœud DOM de la tuile.
    ...
    ...    **Une tuile rendue sans titre ou sans intent fait ÉCHOUER la
    ...    lecture**, et cette garde est le cœur du mot-clé : appliquée à la
    ...    mauvaise release, la lecture retourne des tuiles aux champs vides sans
    ...    rien signaler, et toute la campagne devient verte sur du vide. Le
    ...    silence est ici le pire résultat possible, plus dangereux qu'un
    ...    échec.
    ${tuiles}=    Run Keyword    ${ABAP_FLP_TUILES_STRATEGIE}
    ${muettes}=    Evaluate    [t for t in ($tuiles or []) if not t['titre'] or not t['intent']]
    Should Be Empty    ${muettes}
    ...    msg=${{len($muettes)}} tuile(s) rendue(s) sans titre ni intent lisibles : la stratégie « ${ABAP_FLP_TUILES_STRATEGIE} » ne convient pas à cette release, elle rend des champs vides au lieu d'échouer. Tuiles concernées : ${muettes}
    RETURN    ${tuiles}

Lire Les Tuiles Par Agregation
    [Documentation]    Stratégie de lecture des tuiles quand le titre vit dans
    ...    les agrégations de la tuile et l'intent dans son contexte de liaison.
    ${tuiles}=    Evaluate JavaScript    ${None}    ${ABAP_FLP_TUILES_JS}
    RETURN    ${tuiles}

Lire Les Tuiles Par Containment
    [Documentation]    Stratégie de lecture des tuiles quand la tuile est rendue
    ...    par un COMPOSANT séparé : ni son agrégation ni son contexte de liaison
    ...    ne portent plus titre, cible ni compteur, et les contrôles qui les
    ...    portent ne sont atteignables que par la relation de containment DOM.
    ...
    ...    Aucun JavaScript ici : la capacité de perception (« quels contrôles
    ...    sont rendus À L'INTÉRIEUR de celui-ci ») vit dans la bibliothèque, sous
    ...    l'argument `containedIn`, parce qu'elle vaut pour toute cible Fiori et
    ...    pas seulement pour un launchpad (convention 12). Ce qui reste ici est
    ...    du vocabulaire : ce qu'est une tuile, où se lit son intent.
    ${ids}=    Get Ui5 Ids    controlType=${ABAP_FLP_HOME_TILE}
    ${tuiles}=    Create List
    FOR    ${id}    IN    @{ids}
        ${titres}=    Get Ui5 Properties    header
        ...    controlType=${ABAP_FLP_TILE_HEADER}    containedIn=${id}
        ${valeurs}=    Get Ui5 Properties    value
        ...    controlType=${ABAP_FLP_TILE_COUNTER}    containedIn=${id}
        ${intent}=    Lire L Intent D Une Tuile    ${id}
        ${titre}=    Set Variable If    ${titres}    ${titres}[0]    ${EMPTY}
        ${compteur}=    Set Variable If    ${valeurs}    ${valeurs}[0]    ${EMPTY}
        ${tuile}=    Create Dictionary    titre=${{str($titre or '')}}    intent=${intent}
        ...    compteur=${{str($compteur or '')}}    dynamique=${{bool($valeurs)}}
        Append To List    ${tuiles}    ${tuile}
    END
    RETURN    ${tuiles}

Lire L Intent D Une Tuile
    [Documentation]    Intent d'une tuile lu dans le `href` de son ancre HTML :
    ...    la seule source qui réponde sur les releases où le contexte de liaison
    ...    rend une cible vide. Retourne une chaîne vide quand la tuile n'a pas
    ...    d'ancre, ce que la garde de `Lire Les Tuiles De L Accueil` transforme
    ...    en échec parlant plutôt qu'en silence.
    [Arguments]    ${id}
    ${selecteur}=    Replace String    ${ABAP_FLP_TILE_ANCHOR}    __ID__    ${id}
    ${nb}=    Get Element Count    css=${selecteur}
    IF    ${nb} == 0    RETURN    ${EMPTY}
    ${href}=    Get Attribute    css=${selecteur}    href
    ${intent}=    Evaluate    ($href or '').split('#', 1)[-1].split('?')[0] if '#' in ($href or '') else ''
    RETURN    ${intent}

Separer Les Compteurs Non Resolus
    [Documentation]    Sépare les tuiles dynamiques dont le compteur est
    ...    numérique de celles dont le fournisseur de données n'a pas répondu :
    ...    `{numeriques, non_resolus}`. Un compteur non résolu se RAPPORTE, il
    ...    ne met pas la campagne en échec : c'est l'état d'un composant du
    ...    système, pas un défaut du test.
    [Arguments]    ${tuiles}
    ${numeriques}=    Evaluate
    ...    [t for t in $tuiles if t['dynamique'] and t['compteur'].replace(',', '').replace('.', '').isdigit()]
    ${non_resolus}=    Evaluate
    ...    [t for t in $tuiles if t['dynamique'] and not t['compteur'].replace(',', '').replace('.', '').isdigit()]
    ${bilan}=    Create Dictionary    numeriques=${numeriques}    non_resolus=${non_resolus}
    RETURN    ${bilan}

Compter Les Tuiles Rendues
    [Documentation]    Nombre de tuiles génériques rendues dans la page. Sert de
    ...    mesure RELATIVE (accueil contre résultats de recherche), jamais de
    ...    volumétrie absolue.
    ${nb}=    Get Ui5 Match Count    controlType=${ABAP_FLP_TILE}
    RETURN    ${nb}

# --- Navigation ---------------------------------------------------------------

Lire Le Fragment Courant
    [Documentation]    Fragment de l'URL courante, sans son dièse. C'est l'ancre
    ...    de navigation locale-indépendante de ce launchpad : le titre de page,
    ...    lui, est traduit.
    ${url}=    Get Url
    ${fragment}=    Evaluate    $url.split('#', 1)[1] if '#' in $url else ''
    RETURN    ${fragment}

Le Fragment Courant Commence Par
    [Documentation]    Prédicat de navigation : le fragment courant commence par
    ...    l'intent attendu. La forme « commence par » est nécessaire, la
    ...    recherche du shell ajoutant ses paramètres derrière son intent.
    [Arguments]    ${attendu}
    ${fragment}=    Lire Le Fragment Courant
    Should Start With    ${fragment}    ${attendu}
    ...    msg=Fragment courant « ${fragment} », attendu commençant par « ${attendu} ».

Attendre Le Fragment
    [Documentation]    Sonde jusqu'à ce que le fragment courant porte l'intent
    ...    attendu. Nécessaire : la navigation du shell est asynchrone, et une
    ...    lecture d'URL immédiate après un clic rend encore l'ancien fragment.
    [Arguments]    ${attendu}    ${budget}=60s
    Wait Until Keyword Succeeds    ${budget}    1s    Le Fragment Courant Commence Par    ${attendu}

Compter Le Conteneur D Application
    [Documentation]    Nombre de conteneurs d'application correspondant à un
    ...    intent (0 ou 1). L'identifiant du conteneur est DÉRIVÉ de l'intent,
    ...    donc ni généré ni traduit : c'est le témoin de « quelle application
    ...    est ouverte », et il remplace ici le test d'iframe des launchpads
    ...    hébergés dans le cloud.
    [Arguments]    ${intent}
    ${nb}=    Get Ui5 Match Count    idSuffix=${ABAP_FLP_APP_CONTAINER_PREFIX}${intent}
    RETURN    ${nb}

L Application Ouverte Est
    [Documentation]    Vérifie que l'application de cet intent est ouverte
    ...    exactement une fois.
    [Arguments]    ${intent}
    ${nb}=    Compter Le Conteneur D Application    ${intent}
    Should Be Equal As Integers    ${nb}    1
    ...    msg=Le conteneur de l'application « ${intent} » est présent ${nb} fois, attendu 1.

Aucune Application N Est Ouverte
    [Documentation]    Vérifie qu'aucun conteneur ne subsiste pour cet intent :
    ...    le pendant négatif, celui qui prouve la destruction au retour.
    [Arguments]    ${intent}
    ${nb}=    Compter Le Conteneur D Application    ${intent}
    Should Be Equal As Integers    ${nb}    0
    ...    msg=Le conteneur de l'application « ${intent} » survit alors qu'elle devrait être fermée.

Ouvrir L Application Par Intent
    [Documentation]    Ouvre une application par son intent, la voie STABLE : le
    ...    hash survit aux réorganisations de catalogue, au thème et à la
    ...    langue. Rend la main quand l'application est réellement ouverte.
    [Arguments]    ${intent}
    Open Fiori App    ${intent}
    Attendre Le Fragment    ${intent}
    Wait For Ui5 Idle    settle=${ABAP_FLP_SETTLE}    timeout=${ABAP_FLP_IDLE_TIMEOUT}
    Wait Until Keyword Succeeds    60s    2s    L Application Ouverte Est    ${intent}

Ouvrir L Application Par Sa Tuile
    [Documentation]    Ouvre une application comme le ferait l'utilisateur, en
    ...    cliquant sa tuile. Le titre vient de la découverte du même run, jamais
    ...    d'une constante : il est traduit.
    [Arguments]    ${titre}    ${intent}
    Click Ui5 Control    controlType=${ABAP_FLP_TILE}    properties={'header': '${titre}'}
    Attendre Le Fragment    ${intent}
    Wait For Ui5 Idle    settle=${ABAP_FLP_SETTLE}    timeout=${ABAP_FLP_IDLE_TIMEOUT}
    Wait Until Keyword Succeeds    60s    2s    L Application Ouverte Est    ${intent}

Revenir A L Accueil
    [Documentation]    Retour à l'accueil par son intent.
    ...
    ...    Pourquoi pas le bouton d'accueil de la barre shell : dans une
    ...    application, il se déclare `visible` sans avoir le moindre nœud DOM,
    ...    le shell rendant le bouton de retour à sa place. Le viser produirait
    ...    un échec de localisateur qui ressemble à une dérive alors que c'en
    ...    est une autre.
    Open Fiori App    ${ABAP_FLP_HOME_INTENT}
    Attendre Le Fragment    ${ABAP_FLP_HOME_INTENT}
    Wait For Ui5 Idle    settle=${ABAP_FLP_SETTLE}    timeout=${ABAP_FLP_IDLE_TIMEOUT}

Revenir En Arriere Dans Le Shell
    [Documentation]    Navigation arrière du NAVIGATEUR, puis attente du
    ...    fragment attendu : c'est le shell qui reconstruit l'écran précédent.
    ...
    ...    Le budget de retour au repos est un ARGUMENT, parce que la reprise
    ...    relance le chargement de données de l'application reconstruite : là
    ...    où une release met deux secondes, une autre en met près de soixante,
    ...    et le budget par défaut échoue alors en annonçant une requête en vol,
    ...    ce qui se lit à tort comme une anomalie applicative.
    [Arguments]    ${fragment_attendu}    ${budget}=${ABAP_FLP_IDLE_TIMEOUT}
    Go Back
    Attendre Le Fragment    ${fragment_attendu}
    Wait For Ui5 Idle    settle=${ABAP_FLP_SETTLE}    timeout=${budget}

# --- Zone utilisateur ---------------------------------------------------------

Ouvrir La Zone Utilisateur
    [Documentation]    Ouvre le popover de la zone utilisateur et attend qu'il
    ...    soit réellement OUVERT (et pas seulement rendu : un popover fermé
    ...    garde son nœud DOM).
    Click Ui5 Control    idSuffix=${ABAP_FLP_ME_AREA_BUTTON}
    Wait Until Keyword Succeeds    20s    0.5s    La Zone Utilisateur Est Ouverte

La Zone Utilisateur Est Ouverte
    [Documentation]    Prédicat d'ouverture, appuyé sur la liste des popups
    ...    réellement ouverts.
    ${popups}=    Get Ui5 Open Popups
    ${ouverts}=    Evaluate
    ...    [p for p in $popups if p['id'].endswith($ABAP_FLP_ME_AREA_POPOVER)]
    Should Not Be Empty    ${ouverts}
    ...    msg=Le popover de la zone utilisateur n'est pas ouvert.

Lire Les Entrees De La Zone Utilisateur
    [Documentation]    Suffixes d'action des entrées RENDUES de la zone
    ...    utilisateur, triés (`aboutBtn`, `logoutBtn`, ...).
    ...
    ...    L'ancre est le suffixe d'action seul : l'identifiant complet contient
    ...    la POSITION de l'entrée dans la liste, et cette position change entre
    ...    l'accueil et une application. Et seules les entrées RENDUES sont
    ...    retournées : une entrée déclarée mais jamais construite par le shell
    ...    ne doit pas être comptée comme offerte à l'utilisateur.
    ${ids}=    Get Ui5 Ids    controlType=${ABAP_FLP_ME_AREA_ITEM}
    ...    idSuffix=${ABAP_FLP_ME_AREA_ACTION}
    ${actions}=    Evaluate    sorted({i.rsplit('-', 1)[-1] for i in $ids})
    RETURN    ${actions}

Fermer La Zone Utilisateur
    [Documentation]    Referme le popover de la zone utilisateur par le moyen que
    ...    la cible a déclaré (`${ABAP_FLP_ME_AREA_FERMETURE}`), puis CONSTATE
    ...    qu'aucun popover n'est plus ouvert.
    ...
    ...    Le constat compte autant que le geste : un popover resté ouvert
    ...    intercepte les clics suivants, et l'échec se produit alors deux
    ...    mots-clés plus loin, sur un localisateur parfaitement valide.
    Run Keyword    ${ABAP_FLP_ME_AREA_FERMETURE}
    Wait Until Keyword Succeeds    20s    0.5s    Aucun Popover N Est Ouvert

Fermer Le Popover Par Echappement
    [Documentation]    Fermeture d'un popover par la touche d'échappement.
    Keyboard Key    press    Escape

Fermer La Zone Utilisateur Par Bascule
    [Documentation]    Fermeture du popover de la zone utilisateur en rappuyant
    ...    sur le bouton qui l'a ouvert. Le moyen des releases où
    ...    l'échappement reste sans effet, le clic d'ouverture n'ayant pas
    ...    déplacé le focus dans le popover.
    Click Ui5 Control    idSuffix=${ABAP_FLP_ME_AREA_BUTTON}

Aucun Popover N Est Ouvert
    [Documentation]    Prédicat de fermeture : plus aucun popover ouvert.
    ${popups}=    Get Ui5 Open Popups
    ${popovers}=    Evaluate    [p for p in $popups if p['kind'] == 'popover']
    Should Be Empty    ${popovers}
    ...    msg=Un popover est encore ouvert : ${popovers}

Ouvrir L Entree De La Zone Utilisateur
    [Documentation]    Ouvre la zone utilisateur puis actionne l'une de ses
    ...    entrées, désignée par son suffixe d'action.
    [Arguments]    ${suffixe}
    Ouvrir La Zone Utilisateur
    Click Ui5 Control    idSuffix=${suffixe}

Ouvrir Les Activites Recentes
    [Documentation]    Ouvre le panneau des activités récentes depuis la zone
    ...    utilisateur et attend qu'il soit réellement ouvert.
    ...
    ...    Le panneau ne NAVIGUE pas : il s'ouvre par-dessus l'écran courant,
    ...    dans un popup dont la nature dépend de la release (un panneau replié
    ...    dans le popover ici, une boîte de dialogue là). Le témoin d'ouverture
    ...    est donc la liste d'activités elle-même, sous son identifiant stable,
    ...    et non le type du popup qui la porte.
    Ouvrir L Entree De La Zone Utilisateur    ${ABAP_FLP_ACTIVITIES_ENTRY}
    Wait Until Keyword Succeeds    30s    0.5s    Le Panneau Des Activites Est Ouvert

Le Panneau Des Activites Est Ouvert
    [Documentation]    Prédicat d'ouverture du panneau des activités : sa liste
    ...    et ses deux onglets (récentes, fréquentes) sont rendus.
    ${liste}=    Get Ui5 Match Count    idSuffix=${ABAP_FLP_ACTIVITIES_LIST}
    Should Be True    ${liste} > 0
    ...    msg=La liste des activités récentes n'est pas rendue.
    ${recentes}=    Get Ui5 Match Count    idSuffix=${ABAP_FLP_ACTIVITIES_RECENT_TAB}
    ${frequentes}=    Get Ui5 Match Count    idSuffix=${ABAP_FLP_ACTIVITIES_FREQUENT_TAB}
    Should Be True    ${recentes} > 0 and ${frequentes} > 0
    ...    msg=Le panneau des activités ne rend pas ses deux onglets (récentes : ${recentes}, fréquentes : ${frequentes}).

Compter Les Activites Recentes
    [Documentation]    Nombre d'entrées RENDUES dans la liste des activités
    ...    récentes.
    ...
    ...    Ne compte que les identifiants terminés par un indice de ligne : la
    ...    liste rend aussi son propre conteneur et une icône par entrée, et les
    ...    additionner tripleraient le compte. Le contenu de cette liste, lui,
    ...    ne s'asserte pas : il dépend de l'historique de l'utilisateur.
    ${ids}=    Get Ui5 Ids    viewId=${ABAP_FLP_ACTIVITIES_LIST}
    ${entrees}=    Evaluate    [i for i in $ids if i.rsplit('-', 1)[-1].isdigit()]
    RETURN    ${{len($entrees)}}

Fermer Les Activites Recentes
    [Documentation]    Referme le panneau des activités par la touche
    ...    d'échappement, puis constate qu'aucun popup ne subsiste.
    Keyboard Key    press    Escape
    Wait Until Keyword Succeeds    20s    0.5s    Aucun Popup N Est Ouvert

Aucun Popup N Est Ouvert
    [Documentation]    Prédicat de fermeture le plus large : ni popover ni
    ...    dialogue ouvert. Nécessaire là où la release décide seule de la forme
    ...    du popup, et où ne regarder que les popovers laisserait passer une
    ...    boîte de dialogue restée ouverte.
    ${popups}=    Get Ui5 Open Popups
    Should Be Empty    ${popups}
    ...    msg=Un popup est encore ouvert : ${popups}

# --- Dialogues du shell -------------------------------------------------------

Lire Les Dialogues Ouverts
    [Documentation]    Dialogues actuellement ouverts, avec leur propriété
    ...    d'état. Un dialogue fermé restant rendu, c'est la seule lecture qui
    ...    distingue ouvert de fermé.
    ${popups}=    Get Ui5 Open Popups
    ${dialogues}=    Evaluate    [p for p in $popups if p['kind'] == 'dialog']
    RETURN    ${dialogues}

Aucun Dialogue N Est Ouvert
    [Documentation]    Prédicat de fermeture d'un dialogue.
    ${dialogues}=    Lire Les Dialogues Ouverts
    Should Be Empty    ${dialogues}
    ...    msg=Un dialogue est encore ouvert : ${dialogues}

Attendre La Fermeture Des Dialogues
    [Documentation]    Sonde jusqu'à ce que plus aucun dialogue ne soit ouvert :
    ...    la fermeture est animée, donc asynchrone.
    Wait Until Keyword Succeeds    20s    0.5s    Aucun Dialogue N Est Ouvert

Acquitter Le Dialogue Ouvert
    [Documentation]    Acquitte le dialogue ouvert le plus récent par la
    ...    POSITION de son bouton, jamais par son texte, qui est traduit, ni par
    ...    son identifiant, qui est généré.
    [Arguments]    ${position}=${ABAP_FLP_CONFIRM_POSITION}
    Click Ui5 Dialog Button    ${position}
    Attendre La Fermeture Des Dialogues

Acquitter Le Dialogue D Erreur
    [Documentation]    Acquitte un dialogue de REFUS, dont la position
    ...    d'acquittement n'est pas nécessairement celle d'une confirmation :
    ...    sur certaines releases, la première position copie le message
    ...    technique et laisse le dialogue ouvert. D'où une variable de cible
    ...    distincte, et non la constante d'acquittement générale.
    Acquitter Le Dialogue Ouvert    ${ABAP_FLP_ERROR_CONFIRM_POSITION}

Ouvrir Le Dialogue A Propos
    [Documentation]    Ouvre le dialogue « à propos » depuis la zone utilisateur
    ...    et attend son ouverture réelle.
    Ouvrir L Entree De La Zone Utilisateur    ${ABAP_FLP_ABOUT_ENTRY}
    Wait Until Keyword Succeeds    20s    0.5s    Le Dialogue A Propos Est Ouvert

Le Dialogue A Propos Est Ouvert
    [Documentation]    Prédicat d'ouverture du dialogue « à propos », par son
    ...    identifiant STABLE.
    ${dialogues}=    Lire Les Dialogues Ouverts
    ${cible}=    Evaluate    [d for d in $dialogues if d['id'].endswith($ABAP_FLP_ABOUT_DIALOG)]
    Should Not Be Empty    ${cible}
    ...    msg=Le dialogue « à propos » n'est pas ouvert (ouverts : ${dialogues}).

Lire L Empreinte Systeme
    [Documentation]    Contenu technique du dialogue « à propos », en un seul
    ...    texte : c'est le seul endroit de l'interface qui nomme la version du
    ...    produit ABAP, donc l'empreinte qui distingue deux systèmes de release
    ...    différente. Les LIBELLÉS y sont traduits, les VALEURS non.
    ${empreinte}=    Get Ui5 Text    idSuffix=${ABAP_FLP_ABOUT_DIALOG}
    RETURN    ${empreinte}

Ouvrir Les Parametres Utilisateur
    [Documentation]    Ouvre le dialogue des paramètres depuis la zone
    ...    utilisateur et attend son ouverture réelle.
    Ouvrir L Entree De La Zone Utilisateur    ${ABAP_FLP_SETTINGS_ENTRY}
    Wait Until Keyword Succeeds    20s    0.5s    Le Dialogue Des Parametres Est Ouvert

Le Dialogue Des Parametres Est Ouvert
    [Documentation]    Prédicat d'ouverture du dialogue des paramètres.
    ${dialogues}=    Lire Les Dialogues Ouverts
    ${cible}=    Evaluate    [d for d in $dialogues if d['id'].endswith($ABAP_FLP_SETTINGS_DIALOG)]
    Should Not Be Empty    ${cible}
    ...    msg=Le dialogue des paramètres n'est pas ouvert (ouverts : ${dialogues}).

Lire Les Rubriques De Parametres
    [Documentation]    Clés techniques des rubriques RENDUES de la liste maître
    ...    des paramètres, triées (`language`, `themes`, ...). Les libellés
    ...    affichés sont traduits ; ces clés ne le sont pas.
    ...
    ...    La SOURCE de ces clés est une variable de cible
    ...    (`${ABAP_FLP_RUBRIQUES_STRATEGIE}`) et non une condition : selon la
    ...    release, la clé vit dans l'identifiant de la rubrique ou dans son
    ...    contexte de liaison.
    ${cles}=    Run Keyword    ${ABAP_FLP_RUBRIQUES_STRATEGIE}
    RETURN    ${cles}

Lire Les Rubriques Par Suffixe D Identifiant
    [Documentation]    Stratégie de lecture des rubriques quand la clé technique
    ...    est PORTÉE PAR L'IDENTIFIANT (`themes-UserSettingsEntry`).
    ${ids}=    Get Ui5 Ids    idSuffix=${ABAP_FLP_SETTINGS_ENTRY_SUFFIX}
    ${cles}=    Evaluate
    ...    sorted({i.split('--')[-1][:-len($ABAP_FLP_SETTINGS_ENTRY_SUFFIX)] for i in $ids})
    RETURN    ${cles}

Lire Les Rubriques Par Contexte De Liaison
    [Documentation]    Stratégie de lecture des rubriques quand l'identifiant est
    ...    entièrement GÉNÉRÉ (`__item3-settingsView--userSettingEntryList-2`) :
    ...    la clé n'existe plus que dans le contexte de liaison de l'entrée.
    ...
    ...    La sonde ne rend que les rubriques réellement RENDUES : une rubrique
    ...    déclarée par le modèle mais jamais construite n'est pas offerte à
    ...    l'utilisateur, donc pas relevée.
    ${items}=    Get Ui5 Aggregation Info    items
    ...    idSuffix=${ABAP_FLP_SETTINGS_LIST}
    ${cles}=    Evaluate
    ...    [str((i['binding'] or {}).get('object', {}).get('id') or '') for i in $items if i['rendered']]
    ${triees}=    Evaluate    sorted({c for c in $cles if c})
    RETURN    ${triees}

Annuler Les Parametres Utilisateur
    [Documentation]    Referme le dialogue des paramètres par ANNULER, jamais par
    ...    enregistrer : le bouton d'enregistrement écrit une personnalisation
    ...    utilisateur côté serveur, et cette campagne est en lecture seule.
    Click Ui5 Control    idSuffix=${ABAP_FLP_SETTINGS_CANCEL}
    Attendre La Fermeture Des Dialogues

# --- Refus de navigation ------------------------------------------------------

Demander Un Intent Inconnu
    [Documentation]    Demande au shell la navigation vers un intent de forme
    ...    correcte mais inconnu du système.
    [Arguments]    ${intent}=${ABAP_FLP_INTENT_INCONNU}
    Open Fiori App    ${intent}

Forcer Un Fragment Malforme
    [Documentation]    Écrit dans l'URL un fragment qui n'a PAS la forme d'un
    ...    intent (aucune partie action) : le seul moyen de soumettre au shell
    ...    autre chose qu'un intent bien formé.
    [Arguments]    ${fragment}=${ABAP_FLP_FRAGMENT_MALFORME}
    ${js}=    Replace String    ${ABAP_FLP_FRAGMENT_JS}    __FRAGMENT__    ${fragment}
    Evaluate JavaScript    ${None}    ${js}

Le Shell Refuse La Navigation
    [Documentation]    Constate un refus de navigation : un dialogue en état
    ...    d'ERREUR est ouvert. L'ancre est la propriété d'état, jamais le titre
    ...    ni le texte, qui sont traduits. Retourne le dialogue constaté.
    Wait Until Keyword Succeeds    30s    0.5s    Un Dialogue D Erreur Est Ouvert
    ${dialogues}=    Lire Les Dialogues Ouverts
    ${erreurs}=    Evaluate    [d for d in $dialogues if d['state'] == $ABAP_FLP_ERROR_STATE]
    RETURN    ${erreurs}[0]

Un Dialogue D Erreur Est Ouvert
    [Documentation]    Prédicat de refus.
    ${dialogues}=    Lire Les Dialogues Ouverts
    ${erreurs}=    Evaluate    [d for d in $dialogues if d['state'] == $ABAP_FLP_ERROR_STATE]
    Should Not Be Empty    ${erreurs}
    ...    msg=Aucun dialogue en état d'erreur (ouverts : ${dialogues}).

# --- App Finder ---------------------------------------------------------------

Ouvrir L App Finder
    [Documentation]    Ouvre l'App Finder depuis la zone utilisateur et attend
    ...    son fragment ET son champ de recherche : l'App Finder est une page du
    ...    SHELL, pas une application.
    Ouvrir L Entree De La Zone Utilisateur    ${ABAP_FLP_APPFINDER_ENTRY}
    Attendre Le Fragment    ${ABAP_FLP_APPFINDER_INTENT}
    Wait For Ui5 Idle    settle=${ABAP_FLP_SETTLE}    timeout=${ABAP_FLP_IDLE_TIMEOUT}
    Ui5 Control Should Be Visible    idSuffix=${ABAP_FLP_APPFINDER_SEARCH}

Lire Les Sources De Catalogue
    [Documentation]    Identifiants des sources proposées par l'App Finder : une
    ...    entrée « toutes » plus une entrée par catalogue assigné.
    ${ids}=    Get Ui5 Ids    controlType=${ABAP_FLP_ME_AREA_ITEM}
    ...    viewId=${ABAP_FLP_CATALOG_SELECT}
    RETURN    ${ids}

Filtrer L App Finder
    [Documentation]    Saisit un terme de recherche dans l'App Finder, le valide,
    ...    et attend que le filtre ait PRIS.
    ...
    ...    L'attente porte sur le changement du nombre de vignettes rendues, et
    ...    non sur le repos réseau : le filtrage de l'App Finder est LOCAL, donc
    ...    aucune requête ne part et le repos réseau est atteint instantanément
    ...    pendant que le rendu, lui, est différé. Mesuré au premier run : un
    ...    comptage pris juste après la validation retrouve les 54 vignettes
    ...    d'avant filtrage et conclut que le filtre ne filtre pas.
    [Arguments]    ${terme}
    ${avant}=    Compter Les Applications Rendues
    Fill Ui5 Input    ${terme}    idSuffix=${ABAP_FLP_APPFINDER_SEARCH}
    Keyboard Key    press    Enter
    Wait For Ui5 Idle    settle=${ABAP_FLP_SETTLE}    timeout=${ABAP_FLP_IDLE_TIMEOUT}
    Wait Until Keyword Succeeds    20s    0.5s    Le Rendu De L App Finder A Change    ${avant}

Le Rendu De L App Finder A Change
    [Documentation]    Prédicat de prise en compte d'un filtre : le nombre de
    ...    vignettes rendues n'est plus celui d'avant.
    [Arguments]    ${avant}
    ${apres}=    Compter Les Applications Rendues
    Should Not Be Equal As Integers    ${apres}    ${avant}
    ...    msg=L'App Finder rend toujours ${apres} vignette(s) : le filtre n'a pas encore été appliqué.

Compter Les Applications Rendues
    [Documentation]    Nombre de vignettes d'application RENDUES par l'App
    ...    Finder. À ne jamais confondre avec le volume du catalogue : le rendu
    ...    est paresseux et ne montre que ce qui est filtré et visible.
    ${nb}=    Get Ui5 Match Count    controlType=${ABAP_FLP_APPBOX}
    RETURN    ${nb}

Lire L Unique Application De L App Finder
    [Documentation]    Application rendue par l'App Finder quand le filtre en
    ...    laisse EXACTEMENT une : un dict `{intent, titre}`.
    ...
    ...    L'intent se lit sur la propriété `url` de la vignette (`#Objet-action`,
    ...    technique) ; le titre est traduit et n'est retourné que pour le
    ...    journal. Exiger l'unicité plutôt que prendre la première : le cycle
    ...    d'épinglage agit sur LE bouton rendu, et agir sur « celui d'en haut »
    ...    ferait dépendre une écriture du hasard de rendu.
    ${vignettes}=    Compter Les Applications Rendues
    Should Be Equal As Integers    ${vignettes}    1
    ...    msg=Le filtre laisse ${vignettes} application(s) : le cycle d'épinglage exige un filtre qui n'en laisse qu'une (choisir un terme plus précis).
    ${urls}=    Get Ui5 Properties    url    controlType=${ABAP_FLP_APPBOX}
    ${titres}=    Get Ui5 Properties    title    controlType=${ABAP_FLP_APPBOX}
    ${intent}=    Evaluate    str($urls[0] or '').lstrip('#').split('?')[0]
    Should Not Be Empty    ${intent}
    ...    msg=La vignette filtrée ne déclare aucune cible : ${urls}
    ${appli}=    Create Dictionary    intent=${intent}    titre=${titres}[0]
    RETURN    ${appli}

# --- Épinglage : le SEUL cycle d'écriture de ces campagnes --------------------

L Accord D Ecriture Est Donne
    [Documentation]    Prédicat d'accord explicite d'écriture (`yes`/`true`/`1`/`on`).
    ${accorde}=    Evaluate
    ...    str($ABAP_FLP_WRITE_OPT_IN).strip().lower() in ("yes", "true", "1", "on")
    RETURN    ${accorde}

Exiger L Accord D Ecriture
    [Documentation]    SAUTE le test tant que l'accord d'écriture n'a pas été
    ...    donné en ligne de commande. Deux tours, et c'est délibéré : le tag
    ...    `write` dit ce que le test fait, la variable dit qu'on l'a voulu.
    ${accorde}=    L Accord D Ecriture Est Donne
    IF    not ${accorde}
        Skip    Personnalisation de l'accueil (ÉCRITURE réversible) : accord explicite requis (-v ABAP_FLP_WRITE_OPT_IN:yes).
    END

Ouvrir Le Choix Des Groupes
    [Documentation]    Ouvre, depuis la vignette filtrée, le popover qui choisit
    ...    les groupes d'accueil où l'application est épinglée, et attend son
    ...    ouverture RÉELLE.
    Click Ui5 Control    controlType=${ABAP_FLP_PIN_BUTTON}
    Wait Until Keyword Succeeds    30s    0.5s    Le Choix Des Groupes Est Ouvert

Le Choix Des Groupes Est Ouvert
    [Documentation]    Prédicat d'ouverture du popover de choix des groupes.
    ${popups}=    Get Ui5 Open Popups
    ${cibles}=    Evaluate    [p for p in $popups if p['id'].endswith($ABAP_FLP_PIN_POPOVER)]
    Should Not Be Empty    ${cibles}
    ...    msg=Le popover de choix des groupes n'est pas ouvert (ouverts : ${popups}).

Lire L Etat D Epinglage Par Groupe
    [Documentation]    État de la case de chaque groupe dans le popover ouvert,
    ...    une liste de booléens dans l'ORDRE des groupes du service.
    ...
    ...    C'est l'état qui fait foi pendant le cycle : la propriété du bouton
    ...    d'épinglage, elle, ne se rafraîchit pas à la fermeture du popover
    ...    (mesuré live : encore `False` juste après un épinglage, encore `True`
    ...    juste après un retrait). S'y fier ferait conclure l'inverse de ce qui
    ...    vient de se passer.
    ${etats}=    Get Ui5 Properties    selected
    ...    controlType=${ABAP_FLP_PIN_GROUP_BOX}    containedIn=${ABAP_FLP_PIN_POPOVER}
    RETURN    ${etats}

Basculer L Epinglage Dans Le Groupe
    [Documentation]    Coche ou décoche la case du groupe de rang ${index} dans
    ...    le popover ouvert, en EXIGEANT l'état de départ : une bascule aveugle
    ...    ferait exactement l'inverse de ce qu'on croit quand l'état a dérivé.
    [Arguments]    ${index}    ${etat_attendu}
    ${cases}=    Get Ui5 Ids    controlType=${ABAP_FLP_PIN_GROUP_BOX}
    ...    containedIn=${ABAP_FLP_PIN_POPOVER}
    Should Be True    ${{len($cases)}} > ${index}
    ...    msg=Le popover propose ${{len($cases)}} groupe(s), le rang ${index} n'existe pas.
    ${avant}=    Lire L Etat D Epinglage Par Groupe
    Should Be Equal    ${avant}[${index}]    ${etat_attendu}
    ...    msg=Le groupe de rang ${index} est dans l'état ${avant}[${index}], attendu ${etat_attendu} avant bascule.
    Click Ui5 Control    id=${cases}[${index}]
    Wait For Ui5 Idle    settle=${ABAP_FLP_SETTLE}    timeout=${ABAP_FLP_IDLE_TIMEOUT}
    ${apres}=    Lire L Etat D Epinglage Par Groupe
    Should Not Be Equal    ${apres}[${index}]    ${etat_attendu}
    ...    msg=La case du groupe de rang ${index} n'a pas basculé : toujours ${apres}[${index}].

Fermer Le Choix Des Groupes
    [Documentation]    Referme le popover de choix des groupes par son bouton, et
    ...    CONSTATE la fermeture : la personnalisation est écrite à ce moment-là,
    ...    et un popover resté ouvert intercepterait les clics suivants.
    Click Ui5 Control    idSuffix=${ABAP_FLP_PIN_CLOSE}
    Wait Until Keyword Succeeds    20s    0.5s    Aucun Popover N Est Ouvert
    Wait For Ui5 Idle    settle=${ABAP_FLP_SETTLE}    timeout=${ABAP_FLP_IDLE_TIMEOUT}

Epingler L Application
    [Documentation]    Épingle la vignette filtrée dans le groupe de ce rang.
    ...    Écriture : n'est appelée que sous accord explicite.
    [Arguments]    ${index}=${ABAP_FLP_GROUPE_EPINGLAGE}
    Ouvrir Le Choix Des Groupes
    Basculer L Epinglage Dans Le Groupe    ${index}    ${False}
    Fermer Le Choix Des Groupes

Depingler L Application
    [Documentation]    Retire la vignette filtrée du groupe de ce rang.
    [Arguments]    ${index}=${ABAP_FLP_GROUPE_EPINGLAGE}
    Ouvrir Le Choix Des Groupes
    Basculer L Epinglage Dans Le Groupe    ${index}    ${True}
    Fermer Le Choix Des Groupes

Retirer L Epinglage Si Present
    [Documentation]    Filet de sécurité de teardown : rouvre l'App Finder,
    ...    refiltre, et ne retire l'épinglage QUE s'il est encore là.
    ...
    ...    Conditionnel à dessein : ce mot-clé s'exécute aussi après un échec
    ...    survenu AVANT tout épinglage, et il ne doit alors rien faire ni rien
    ...    casser. Il ne s'exécute pas du tout sans accord d'écriture : il n'y a
    ...    alors rien à nettoyer.
    [Arguments]    ${terme}    ${index}=${ABAP_FLP_GROUPE_EPINGLAGE}
    ${accorde}=    L Accord D Ecriture Est Donne
    IF    not ${accorde}    RETURN
    Ouvrir L App Finder
    Filtrer L App Finder    ${terme}
    Ouvrir Le Choix Des Groupes
    ${etats}=    Lire L Etat D Epinglage Par Groupe
    IF    ${etats}[${index}]
        Basculer L Epinglage Dans Le Groupe    ${index}    ${True}
    END
    Fermer Le Choix Des Groupes
    Revenir A L Accueil

Lire Les Intents Des Tuiles De L Accueil
    [Documentation]    Intents des tuiles RENDUES de l'accueil, la forme
    ...    directement comparable d'un relevé à l'autre : c'est la DISPARITION
    ...    d'un intent qui prouve un retrait, là où un volume revenu à sa valeur
    ...    initiale ne prouverait qu'une arithmétique.
    ${tuiles}=    Lire Les Tuiles De L Accueil
    ${intents}=    Evaluate    sorted(t['intent'] for t in $tuiles)
    RETURN    ${intents}

# --- Mode édition de l'accueil ------------------------------------------------

Entrer En Mode Edition De L Accueil
    [Documentation]    Entre en mode édition de l'accueil depuis la zone
    ...    utilisateur. Entrer et sortir sans rien déplacer ne modifie aucune
    ...    personnalisation, ce que le scénario vérifie par comparaison.
    Ouvrir L Entree De La Zone Utilisateur    ${ABAP_FLP_EDIT_ENTRY}
    Wait For Ui5 Idle    settle=${ABAP_FLP_SETTLE}    timeout=${ABAP_FLP_IDLE_TIMEOUT}
    Wait Until Keyword Succeeds    30s    1s    Le Mode Edition Est Actif

Le Mode Edition Est Actif
    [Documentation]    Prédicat du mode édition : son bouton de validation est
    ...    rendu. Le témoin est ce bouton et non la barre de pied de page, qui
    ...    n'est pas rendue comme telle sur cette cible.
    ${nb}=    Compter Le Bouton De Fin D Edition
    Should Be Equal As Integers    ${nb}    1
    ...    msg=Le mode édition de l'accueil n'est pas actif.

Compter Le Bouton De Fin D Edition
    [Documentation]    Nombre de boutons de fin d'édition rendus (0 hors mode
    ...    édition, 1 dedans).
    ${nb}=    Get Ui5 Match Count    idSuffix=${ABAP_FLP_EDIT_DONE}
    RETURN    ${nb}

Quitter Le Mode Edition De L Accueil
    [Documentation]    Quitte le mode édition par son bouton de validation, sans
    ...    avoir rien déplacé, et attend que le mode soit réellement sorti.
    Click Ui5 Control    idSuffix=${ABAP_FLP_EDIT_DONE}
    Wait For Ui5 Idle    settle=${ABAP_FLP_SETTLE}    timeout=${ABAP_FLP_IDLE_TIMEOUT}
    Wait Until Keyword Succeeds    30s    1s    Le Mode Edition Est Quitte

Le Mode Edition Est Quitte
    [Documentation]    Prédicat inverse du mode édition.
    ${nb}=    Compter Le Bouton De Fin D Edition
    Should Be Equal As Integers    ${nb}    0
    ...    msg=Le mode édition de l'accueil est toujours actif.

# --- Menu « toutes mes applications » -----------------------------------------

Ouvrir Le Menu Toutes Mes Applications
    [Documentation]    Ouvre le popover du titre de shell et attend son
    ...    ouverture réelle.
    Click Ui5 Control    idSuffix=${ABAP_FLP_APP_TITLE}
    Wait Until Keyword Succeeds    30s    0.5s    Un Popover Est Ouvert

Un Popover Est Ouvert
    [Documentation]    Prédicat générique d'ouverture de popover.
    ${popups}=    Get Ui5 Open Popups
    ${popovers}=    Evaluate    [p for p in $popups if p['kind'] == 'popover']
    Should Not Be Empty    ${popovers}
    ...    msg=Aucun popover ouvert.

Lire Les Sources Du Menu Toutes Mes Applications
    [Documentation]    Identifiants des sources listées par le menu : les
    ...    applications de l'accueil plus une entrée par catalogue assigné.
    ${ids}=    Get Ui5 Ids    controlType=${ABAP_FLP_ME_AREA_ITEM}
    ...    viewId=${ABAP_FLP_ALL_APPS_LIST}
    RETURN    ${ids}

Attendre Les Sources Du Menu Toutes Mes Applications
    [Documentation]    Attend que le menu ait fini de lister ses sources, puis
    ...    les retourne.
    ...
    ...    Nécessaire parce que cette liste se remplit PROGRESSIVEMENT : mesuré
    ...    live, une lecture immédiate après l'ouverture du popover rend deux
    ...    sources là où la seconde en rend trois, et le repos réseau ne tranche
    ...    pas (les catalogues sont déjà chargés, l'ajout est purement un rendu
    ...    différé). Un test qui lit trop tôt échoue sur un menu parfaitement
    ...    sain, et c'est ce qui s'est produit à la première génération.
    [Arguments]    ${attendues}
    Wait Until Keyword Succeeds    20s    0.5s    Le Menu Propose N Sources    ${attendues}
    ${ids}=    Lire Les Sources Du Menu Toutes Mes Applications
    RETURN    ${ids}

Le Menu Propose N Sources
    [Documentation]    Prédicat de rendu complet de la liste des sources.
    [Arguments]    ${attendues}
    ${ids}=    Lire Les Sources Du Menu Toutes Mes Applications
    Length Should Be    ${ids}    ${attendues}
    ...    msg=Le menu rend ${{len($ids)}} source(s), ${attendues} attendue(s).

Compter Les Entrees Du Menu Toutes Mes Applications
    [Documentation]    Nombre d'entrées d'application RENDUES dans le menu. Le
    ...    menu rend les entrées de la source SÉLECTIONNÉE, pas la totalité du
    ...    catalogue : ce nombre se compare au volume d'une source, jamais au
    ...    total.
    ${nb}=    Get Ui5 Match Count    controlType=${ABAP_FLP_ALL_APPS_ENTRY}
    RETURN    ${nb}

Fermer Le Popover Courant
    [Documentation]    Referme le popover ouvert par la touche d'échappement.
    Keyboard Key    press    Escape
    Wait Until Keyword Succeeds    20s    0.5s    Aucun Popover N Est Ouvert

# --- Recherche du shell -------------------------------------------------------

Ouvrir La Recherche Du Shell
    [Documentation]    Déplie la recherche depuis la barre shell et attend que
    ...    son champ occupe RÉELLEMENT une surface.
    ...
    ...    L'ouverture est IDEMPOTENTE et se retente, parce qu'un seul clic ne
    ...    suffit pas : mesuré live le 2026-08-29 sur la 1.71, le premier clic
    ...    crée le contrôle sans le rendre (champ ABSENT du DOM, bouton
    ...    toujours `visible=True`), et c'est le second qui l'ouvre vraiment
    ...    (560x36, input 528x26, bouton passé à `visible=False`).
    ...
    ...    Ce que coûtait le clic unique, et pourquoi le témoin est la surface
    ...    et non la présence au registre : le contrôle EXISTE après le premier
    ...    clic et se déclare `visible=True`, si bien qu'une assertion de
    ...    présence passait. La suite du scénario saisissait alors dans un
    ...    champ inexistant, `Fill Ui5 Input` relisait une valeur vide, et la
    ...    touche Entrée partait à la tuile qui avait le focus, ouvrant une
    ...    application au lieu de lancer la recherche.
    Wait Until Keyword Succeeds    ${ABAP_FLP_SEARCH_ESSAIS}    ${ABAP_FLP_SEARCH_PAUSE}
    ...    Deplier La Recherche Du Shell

Deplier La Recherche Du Shell
    [Documentation]    Un passage d'ouverture : ne clique que si la recherche
    ...    n'est pas déjà ouverte (le bouton disparaît quand elle l'est, donc
    ...    recliquer échouerait), puis CONSTATE la surface du champ.
    ${ouverte}=    Run Keyword And Return Status
    ...    Ui5 Control Should Be Visible    idSuffix=${ABAP_FLP_SEARCH_INPUT}
    IF    not ${ouverte}
        Click Ui5 Control    idSuffix=${ABAP_FLP_SEARCH_BUTTON}
        Wait For Ui5 Idle    settle=${ABAP_FLP_SETTLE}    timeout=${ABAP_FLP_IDLE_TIMEOUT}
    END
    Ui5 Control Should Be Visible    idSuffix=${ABAP_FLP_SEARCH_INPUT}

Rechercher Dans Le Shell
    [Documentation]    Saisit un terme dans la recherche du shell et la
    ...    déclenche, puis attend l'atterrissage sur l'intent de recherche.
    ...
    ...    Le terme doit être PARTIEL : soumettre le titre exact d'une
    ...    application fait naviguer le shell directement vers cette
    ...    application, ce qui est un autre comportement (relevé live).
    ...
    ...    L'attente porte sur TROIS marches, et les trois ont été payées : le
    ...    fragment (l'URL change avant tout le reste), le conteneur de
    ...    l'application de recherche (le shell rend ses résultats dans une
    ...    application comme une autre, sous le même identifiant dérivé de
    ...    l'intent, vérifié sur les deux releases), puis le repos réseau. Sans
    ...    la deuxième, un comptage de tuiles pris juste après le changement
    ...    d'URL compte encore celles de l'ACCUEIL et conclut à une recherche
    ...    sans résultat.
    [Arguments]    ${terme}
    Fill Ui5 Input    ${terme}    idSuffix=${ABAP_FLP_SEARCH_INPUT}
    Keyboard Key    press    Enter
    Attendre Le Fragment    ${ABAP_FLP_SEARCH_INTENT}
    Wait Until Keyword Succeeds    60s    1s    L Application Ouverte Est    ${ABAP_FLP_SEARCH_INTENT}
    Wait For Ui5 Idle    settle=${ABAP_FLP_SETTLE}    timeout=${ABAP_FLP_IDLE_TIMEOUT}

Lire Le Filtre De Recherche
    [Documentation]    Fragment de recherche DÉCODÉ : il porte la source de
    ...    données interrogée et le terme soumis, deux informations techniques
    ...    (le libellé de la source, lui, est traduit).
    ${fragment}=    Lire Le Fragment Courant
    ${decode}=    Evaluate    urllib.parse.unquote($fragment)    modules=urllib.parse
    RETURN    ${decode}

# --- Déconnexion --------------------------------------------------------------

Se Deconnecter Du Launchpad
    [Documentation]    Déclenche la déconnexion depuis la zone utilisateur et
    ...    retourne le dialogue de confirmation SANS le confirmer : c'est le
    ...    scénario qui vérifie sa structure avant de trancher.
    Ouvrir L Entree De La Zone Utilisateur    ${ABAP_FLP_LOGOUT_ENTRY}
    Wait Until Keyword Succeeds    30s    0.5s    Un Dialogue Est Ouvert
    ${dialogues}=    Lire Les Dialogues Ouverts
    RETURN    ${dialogues}[0]

Un Dialogue Est Ouvert
    [Documentation]    Prédicat générique d'ouverture de dialogue.
    ${dialogues}=    Lire Les Dialogues Ouverts
    Should Not Be Empty    ${dialogues}
    ...    msg=Aucun dialogue ouvert.

Confirmer La Deconnexion
    [Documentation]    Confirme la déconnexion par la POSITION du bouton de
    ...    validation, puis attend l'atterrissage sur la page de sortie du
    ...    serveur.
    Click Ui5 Dialog Button    ${ABAP_FLP_CONFIRM_POSITION}
    Wait Until Keyword Succeeds    60s    1s    La Session Est Fermee

La Session Est Fermee
    [Documentation]    Constate la fin de session : l'URL atteinte est celle de
    ...    la page de déconnexion du serveur et plus aucun runtime UI5 n'est
    ...    chargé. L'ancre est le CHEMIN de l'URL, jamais le texte d'adieu.
    ${url}=    Get Url
    Should Contain    ${url}    /logoff
    ...    msg=L'URL atteinte après déconnexion n'est pas la page de sortie du serveur : ${url}
    ${runtime}=    Ui5 Runtime Is Present
    Should Not Be True    ${runtime}
    ...    msg=Un runtime UI5 subsiste après déconnexion.

# --- Erreurs console ----------------------------------------------------------

Purger Le Journal De Console
    [Documentation]    Vide le journal de console en le LISANT : la collecte est
    ...    incrémentale, chaque appel ne rend que les entrées nouvelles depuis
    ...    le précédent.
    ${vide}=    Get Fiori Diagnostics    sections=console,errors
    Log    Journal purgé : ${vide}[issues]

Recharger L Accueil Proprement
    [Documentation]    Recharge le launchpad après avoir purgé le journal, de
    ...    façon à mesurer un CHARGEMENT PROPRE.
    ...
    ...    La précaution n'est pas cosmétique : l'exploration pollue sa propre
    ...    mesure (sonder un service absent ajoute un 404, une tentative de
    ...    connexion refusée laisse son message), donc une mesure prise en cours
    ...    de campagne décrirait la campagne, pas le launchpad.
    Purger Le Journal De Console
    Go To    ${ABAP_FLP_URL}
    Le Shell Du Launchpad Est Rendu

Classer Les Erreurs Du Shell
    [Documentation]    Trie ce que la console a émis depuis la dernière lecture,
    ...    parce qu'un comptage brut ne veut rien dire : une erreur tracée à un
    ...    composant non déployé du système n'est pas un défaut.
    ...
    ...    Retourne `{erreurs_console, tuile, recherche, deprecation, session,
    ...    autres, classees, erreurs_de_page, premiere_autre}`. La seule
    ...    propriété qui vaut assertion dure est `erreurs_de_page` : une
    ...    exception JavaScript non rattrapée. La seconde assertion tenable est
    ...    l'EXHAUSTIVITÉ du tri (`classees` contre `erreurs_console`), qui
    ...    interdit à la classification de masquer ce qu'elle ne connaît pas.
    ...
    ...    Les familles `deprecation` (dépréciations émises par le shell de SAP
    ...    lui-même) et `session` (réglage de session du shell) sont vides tant
    ...    qu'une cible ne les renseigne pas : un runtime ancien n'en émet
    ...    aucune, un runtime récent en émet à chaque chargement.
    ${diagnostic}=    Get Fiori Diagnostics    sections=console,errors
    ${console}=    Evaluate    $diagnostic.get('console') or []
    ${erreurs}=    Evaluate    [e for e in $console if e.get('type') == 'error']
    ${tuile}=    Classer Par Marqueurs    ${erreurs}    ${ABAP_FLP_MARQUEURS_TUILE}
    ${recherche}=    Classer Par Marqueurs    ${erreurs}    ${ABAP_FLP_MARQUEURS_RECHERCHE}
    ${deprecation}=    Classer Par Marqueurs    ${erreurs}    ${ABAP_FLP_MARQUEURS_DEPRECATION}
    ${session}=    Classer Par Marqueurs    ${erreurs}    ${ABAP_FLP_MARQUEURS_SESSION}
    ${connus}=    Evaluate
    ...    $ABAP_FLP_MARQUEURS_TUILE + $ABAP_FLP_MARQUEURS_RECHERCHE + $ABAP_FLP_MARQUEURS_DEPRECATION + $ABAP_FLP_MARQUEURS_SESSION
    ${autres}=    Evaluate
    ...    [e for e in $erreurs if not any(m in (e.get('text') or '') + ' ' + (e.get('location') or '') for m in $connus)]
    ${page}=    Evaluate    $diagnostic.get('page_errors') or []
    ${premiere}=    Evaluate    ($autres[0].get('text', '') if $autres else '')
    ${classees}=    Evaluate
    ...    len({id(e) for e in $tuile + $recherche + $deprecation + $session}) + len($autres)
    ${bilan}=    Create Dictionary
    ...    erreurs_console=${{len($erreurs)}}
    ...    tuile=${{len($tuile)}}
    ...    recherche=${{len($recherche)}}
    ...    deprecation=${{len($deprecation)}}
    ...    session=${{len($session)}}
    ...    autres=${{len($autres)}}
    ...    classees=${classees}
    ...    erreurs_de_page=${{len($page)}}
    ...    premiere_autre=${premiere}
    RETURN    ${bilan}

Classer Par Marqueurs
    [Documentation]    Entrées de console dont le texte OU l'origine porte l'un
    ...    des marqueurs. L'origine compte autant que le texte : un échec de
    ...    ressource ne cite pas son URL dans son message.
    [Arguments]    ${entrees}    ${marqueurs}
    ${classees}=    Evaluate
    ...    [e for e in $entrees if any(m in (e.get('text') or '') + ' ' + (e.get('location') or '') for m in $marqueurs)]
    RETURN    ${classees}

Nettoyer L Epinglage Et Diagnostiquer
    [Documentation]    Teardown du scénario d'épinglage : diagnostic D'ABORD,
    ...    nettoyage ENSUITE.
    ...
    ...    L'ordre n'est pas cosmétique : le nettoyage rouvre l'App Finder et
    ...    revient à l'accueil, donc il DÉTRUIT l'écran sur lequel le test vient
    ...    d'échouer. Diagnostiquer après reviendrait à photographier la salle
    ...    une fois rangée.
    ...
    ...    Le nettoyage lui-même n'échoue jamais le test : il avertit. Ce qu'on
    ...    veut lire dans un rapport rouge est la cause, pas un teardown qui
    ...    trébuche derrière elle.
    [Arguments]    ${terme}
    Journaliser Le Diagnostic Fiori En Cas D Echec
    Run Keyword And Warn On Failure    Retirer L Epinglage Si Present    ${terme}

Journaliser Le Diagnostic Fiori En Cas D Echec
    [Documentation]    Teardown de test : en cas d'échec seulement, journalise le
    ...    diagnostic agrégé (composition, arbre UI5, erreurs console, snapshot
    ...    ARIA). Sur un launchpad, il distingue en une lecture une dérive de
    ...    localisateur d'un écran qui n'a pas chargé.
    Run Keyword If Test Failed    Log Fiori Diagnostics
