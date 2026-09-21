*** Settings ***
Documentation       **EXEMPLE À PERSONNALISER** : ce fichier porte le vocabulaire
...                 métier du LABORATOIRE de ce dépôt (noms de rapports, colonnes
...                 et identifiants relevés live sur SES cibles). Beaucoup s'y
...                 réutilise tel quel (ce sont des rapports SAP standard), mais
...                 rien n'y fait autorité : à VÉRIFIER sur votre cible. Ce qui
...                 fait foi partout, c'est `src/` : voir `resources/README.md`.
...
...                 Vocabulaire de la sécurité vue par l'**ÉCRAN** (SAP GUI),
...                 pendant de `security_keywords.resource` qui la lit par le
...                 canal RFC. Les deux ne sont pas redondants : ils ne voient
...                 pas la même chose, et c'est la raison d'être de ce fichier.
...
...                 **Ce que l'écran voit et que le canal sans écran ne voit
...                 pas**, mesuré le 2026-09-14 sur ABAP Platform 2023 :
...
...                 1. l'**ORIGINE** d'un paramètre. Le canal RFC rend la valeur
...                 effective sans dire si elle vient du profil d'instance ou
...                 d'un défaut ; le rapport de paramètres porte les deux
...                 colonnes. Sur la cible, 39 des 42 paramètres de sécurité
...                 audités portent leur valeur par défaut, 3 sont déclarés
...                 dans le profil et AUCUN n'y est modifié : le durcissement
...                 n'est donc pas un réglage d'exploitant. « Posé dans le
...                 profil » n'est pas « modifié par le profil », et seule la
...                 seconde notion désigne une décision humaine ;
...                 2. les **autres mandants**. Le rapport des comptes standards
...                 lit tous les mandants depuis une seule session, là où le
...                 canal RFC exige une connexion par mandant et se voyait
...                 refuser l'ouverture sur le mandant de référence ;
...                 3. le **statut des mots de passe** livrés par SAP, que
...                 aucune table ne rend.
...
...                 LECTURE SEULE de bout en bout.

Library             SapEccLibrary
Library             Collections
Library             sapfx_common.parameter_origin
Library             sapfx_common.alv_cells
# Le contrat d'extraction d'un tableau, COMMUN aux trois canaux (écran, WebGUI,
# UI5) : la règle de refus d'un relevé amputé vit à un seul endroit, sans quoi
# chaque canal la réécrit et finit par l'oublier.
Library             sapfx_common.table_extract


*** Variables ***
# --- Les rapports lus. Convention 1 : leurs noms vivent ICI, jamais dans une
# suite. Ce sont des rapports SAP standard, donc portables, mais leur présence
# se vérifie sur la cible.
${TCODE_REPORT_RUNNER}          SA38
${REPORT_PROFILE_PARAMETERS}    RSPARAM
${REPORT_STANDARD_USERS}        RSUSR003
${TCODE_PARAMETER_DETAIL}       RZ11

# L'écran de détail d'un paramètre et ses deux témoins. Le premier est le type
# de conteneur OPAQUE dans lequel cette release rend ses valeurs ; le second le
# préfixe d'un champ de valeur lisible, qui n'existe PAS ici. Les deux vivent
# dans la resource parce qu'ils sont des faits d'écran, pas des faits de test.
${FIELD_PARAMETER_NAME}         wnd[0]/usr/ctxtTPFYSTRUCT-NAME
${BUTTON_DISPLAY_PARAMETER}     wnd[0]/usr/btnPANZEIGEN_1000
${MARKER_OPAQUE_CONTAINER}      HTMLViewer
${MARKER_PARAMETER_VALUE_FIELD}    usr/txtTPFYPROPTY

# --- Les localisateurs d'écran. Le résolveur de grille de la bibliothèque
# traverse les conteneurs (les releases récentes enveloppent l'ALV dans un
# splitter, à une profondeur qui varie par transaction) et le signale.
${FIELD_REPORT_NAME}            wnd[0]/usr/ctxtRS38M-PROGRAMM
${BUTTON_EXECUTE}               wnd[0]/tbar[1]/btn[8]
${CHECKBOX_ALSO_UNSUBSTITUTED}    wnd[0]/usr/chkALSOUSUB
${GRID_FULLSCREEN}              wnd[0]/usr/cntlGRID1/shellcont/shell

# --- Les colonnes TECHNIQUES lues. Indépendantes de la langue ET du profil
# d'affichage, contrairement aux titres affichés (convention 3).
${COL_PARAM_NAME}               NAME
${COL_PARAM_PROFILE}            USER_VALUE
${COL_PARAM_DEFAULT}            DEFAULT_VALUE
@{COLUMNS_PARAMETERS}           NAME    USER_VALUE    DEFAULT_VALUE
@{COLUMNS_STANDARD_USERS}       MANDT    USERNAME    LOCKED    PWSTATUS    VALIDTO

# Les colonnes de clé du rapport des comptes, pour croiser ligne à ligne avec
# un autre canal.
@{KEY_COLUMNS_STANDARD_USERS}    MANDT    USERNAME
${COL_USER_LOCK_ICON}           LOCKED
${COL_USER_CLIENT}              MANDT
${COL_USER_NAME}                USERNAME
${COL_USER_PASSWORD_STATUS}     PWSTATUS

# Le chemin du catalogue de services web. Convention 1 : un chemin de service
# vit dans la couche vocabulaire, jamais dans une suite.
${ODATA_CATALOG_SERVICES}       /sap/opu/odata/iwfnd/catalogservice;v=2/ServiceCollection


*** Keywords ***
Open Report
    [Documentation]    Ouvre un rapport par le lanceur de rapports et s'arrête
    ...    sur son écran de sélection. Les rapports de sécurité n'ont pas tous
    ...    de code de transaction propre.
    [Arguments]    ${rapport}
    Run Transaction    /n${TCODE_REPORT_RUNNER}
    Input Text    ${FIELD_REPORT_NAME}    ${rapport}
    Click Element    ${BUTTON_EXECUTE}

Open Parameter Detail Screen
    [Documentation]    Ouvre l'écran de détail d'UN paramètre et rend la
    ...    perception de cet écran.
    ...
    ...    Sur cette release, les valeurs y sont rendues dans des conteneurs
    ...    HTML opaques : l'API de scripting ne voit qu'une zone utilisateur
    ...    vide. Le keyword existe pour que ce constat soit reproductible, pas
    ...    parce qu'il permet de lire quoi que ce soit.
    [Arguments]    ${parametre}
    Run Transaction    /n${TCODE_PARAMETER_DETAIL}
    Input Text    ${FIELD_PARAMETER_NAME}    ${parametre}
    Click Element    ${BUTTON_DISPLAY_PARAMETER}
    ${perception}=    Get Screen Signature
    RETURN    ${perception}

Run Profile Parameter Report
    [Documentation]    Exécute le rapport des paramètres de profil en incluant
    ...    les paramètres NON substitués, et rend son relevé.
    ...
    ...    L'option compte : sans elle, le rapport ne montrerait que les
    ...    paramètres posés dans le profil, et c'est justement l'ABSENCE d'un
    ...    paramètre de sécurité dans le profil qui est le résultat.
    ...
    ...    Le relevé est RESTREINT aux trois colonnes qu'un contrôle de posture
    ...    consomme : moins d'appels COM sur 1600 lignes. Pour EXTRAIRE le
    ...    tableau, enchaîner plutôt `Open Profile Parameter Report` et
    ...    `Extract Displayed Report`, qui rend les cinq colonnes du rapport.
    Open Profile Parameter Report
    ${total}=    Count Rows In Displayed Report
    @{voulues}=    Create List    ${COL_PARAM_NAME}    ${COL_PARAM_PROFILE}
    ...    ${COL_PARAM_DEFAULT}
    # `Read Full Grid`, comme l'extraction voisine : une ALV ne matérialise ses
    # lignes qu'au DÉFILEMENT et rend les autres en cellules vides. Le contrôle
    # de posture qui consomme ce relevé y est même PLUS exposé qu'une
    # extraction : il cherche 42 paramètres nommés, et ne rougirait que si
    # aucun d'eux n'entrait dans la fenêtre chargée. Une lecture partielle lui
    # ferait conclure « paramètre absent du rapport » sur un système où il est
    # présent.
    ${lignes}=    Read Full Grid    ${GRID_FULLSCREEN}    columns=${voulues}
    ...    max_rows=${total}
    ${vides}=    Count Blank Grid Rows    ${lignes}    ${voulues}
    Should Be Equal As Integers    ${vides}    ${0}
    ...    msg=Lecture REFUSÉE : ${vides} ligne(s) du rapport sont entièrement vides, la grille n'a pas chargé toutes ses lignes. Un contrôle de posture bâti sur ce relevé conclurait à l'absence de paramètres qui y sont.
    RETURN    ${lignes}

Open Profile Parameter Report
    [Documentation]    Exécute le rapport des paramètres de profil, paramètres
    ...    NON substitués inclus, et s'arrête sur sa grille.
    ...
    ...    Séparé de la lecture parce que deux usages en dépendent et ne
    ...    veulent pas les mêmes colonnes : un contrôle de posture en lit
    ...    trois, une extraction les rend toutes.
    Open Report    ${REPORT_PROFILE_PARAMETERS}
    Select Checkbox    ${CHECKBOX_ALSO_UNSUBSTITUTED}
    Click Element    ${BUTTON_EXECUTE}

Extract Displayed Report
    [Documentation]    Lit la grille du rapport AFFICHÉ en ENTIER, toutes ses
    ...    colonnes, et rend le relevé AVEC son contrat, sous la forme COMMUNE
    ...    aux trois canaux (`Build Table Extract` : `rows`, `columns`,
    ...    `headers`, `declared_rows`, `blank_rows`, `complete`).
    ...
    ...    À ne pas confondre avec les lectures voisines, qui restreignent le
    ...    relevé aux colonnes qu'un contrôle consomme : ici l'objet est
    ...    d'EXTRAIRE le tableau, donc en amputer une colonne serait le
    ...    dénaturer. Mesuré sur RSPARAM (release 758) : cinq colonnes, dont
    ...    la forme non substituée et le commentaire, qu'un audit de posture
    ...    n'utilise pas mais qu'une extraction doit rendre.
    ...
    ...    `titres` est la carte `{id technique: titre affiché}` : les clés du
    ...    relevé restent techniques (locale-safe, convention 3) et les titres
    ...    servent d'en-tête aux fichiers livrés, qui ressemblent alors à
    ...    l'écran dont ils viennent.
    ${titres}=    Get Grid Column Titles    ${GRID_FULLSCREEN}
    ${colonnes}=    Get Grid Column Ids    ${GRID_FULLSCREEN}
    ${total}=    Get Row Count    ${GRID_FULLSCREEN}
    # `Read Full Grid` et non `Read Grid` : une ALV ne matérialise ses lignes
    # qu'au fil du DÉFILEMENT, et les lignes non chargées se lisent en cellules
    # VIDES au lieu de lever. Mesuré le 2026-09-15 : la même lecture rendait
    # 1635 lignes pleines sur la 758 et 1639 lignes dont 137 remplies sur la
    # 754. Le compte de lignes était juste des deux côtés, donc aucune garde
    # de complétude fondée sur lui ne pouvait le voir. `vides` est le témoin
    # qui manquait : c'est à l'appelant de refuser un relevé creux.
    ${lignes}=    Read Full Grid    ${GRID_FULLSCREEN}    columns=${colonnes}
    ...    max_rows=${total}
    # Le total est RELU après la lecture, et c'est lui qui part dans le contrat.
    # Repris de `${total}`, il aurait été le plafond DONNÉ à cette lecture :
    # confronter une lecture au plafond qu'on lui a fixé compare deux valeurs
    # de la même source et ne peut pas échouer. Relu, il vient d'un second
    # appel indépendant, et le bras « lues contre déclarées » de la garde
    # commune devient vivant sur ce canal comme sur les deux autres.
    ${declarees}=    Get Row Count    ${GRID_FULLSCREEN}
    # Le relevé prend ici la forme que les trois canaux partagent : le jugement
    # (`Table Extract Should Be Complete`) est le MÊME pour une ALV, une grille
    # WebGUI et une table UI5, alors que chacun s'ampute d'une façon
    # différente. C'est ce qui évite qu'un canal de plus oblige à réécrire la
    # règle de refus, et à l'oublier.
    ${releve}=    Build Table Extract    ${lignes}    columns=${colonnes}
    ...    headers=${titres}    declared_rows=${declarees}    key=${COL_PARAM_NAME}
    ...    source=RSPARAM (canal écran)
    RETURN    ${releve}

Count Rows In Displayed Report
    [Documentation]    Le nombre de lignes que la grille du rapport AFFICHÉ
    ...    déclare, indépendamment de ce qui en a été lu.
    ...
    ...    C'est le témoin qui permet à un appelant de prouver qu'il a tout
    ...    lu : comparer le relevé à ce compte est la seule façon de
    ...    distinguer « le rapport tient en N lignes » de « la lecture s'est
    ...    arrêtée à N lignes ». Les deux produisent le même relevé, et le
    ...    second est un extrait présenté comme un inventaire.
    ${total}=    Get Row Count    ${GRID_FULLSCREEN}
    RETURN    ${total}

Run Standard User Report
    [Documentation]    Exécute le rapport des comptes standards livrés par SAP
    ...    et rend son relevé, TOUS MANDANTS confondus.
    ...
    ...    C'est ce que le canal sans écran ne peut pas faire : il lit le
    ...    mandant de sa connexion, et l'ouverture d'une session sur le mandant
    ...    de référence est refusée avec les identifiants de la campagne.
    Open Report    ${REPORT_STANDARD_USERS}
    Click Element    ${BUTTON_EXECUTE}
    ${total}=    Get Row Count    ${GRID_FULLSCREEN}
    ${lignes}=    Read Grid    ${GRID_FULLSCREEN}
    ...    columns=MANDT,USERNAME,LOCKED,PWSTATUS,VALIDTO    max_rows=${total}
    RETURN    ${lignes}

Cross Check Parameter Origins
    [Documentation]    Croise le relevé d'écran et les valeurs effectives d'un
    ...    autre canal, et rend l'origine de chaque paramètre : posé dans le
    ...    PROFIL (une décision humaine) ou hérité du NOYAU.
    ...
    ...    C'est la question à laquelle aucun des deux canaux ne répond seul,
    ...    et elle change la lecture d'une dérive : un écart sur une valeur de
    ...    noyau viendra d'une montée de version, pas d'une modification du
    ...    système, et le remède n'est pas le même.
    [Arguments]    ${releve_ecran}    ${valeurs_effectives}    ${parametres}=${None}
    ${verdict}=    Compare Channels    ${releve_ecran}    ${valeurs_effectives}
    ...    names=${parametres}
    RETURN    ${verdict}

Establish Lock Icon Meaning
    [Documentation]    Établit ce que veut dire le pictogramme de verrouillage
    ...    du rapport, en le confrontant à la vérité mesurée par l'autre canal
    ...    sur le périmètre où les deux se recouvrent.
    ...
    ...    Une colonne d'icônes n'est ni un booléen ni un libellé : c'est un
    ...    identifiant que le client résout en image. Il a une qualité (il ne
    ...    dépend pas de la langue) et un défaut (il ne se lit pas seul).
    ...    L'interprétation ainsi établie s'applique ensuite au mandant que
    ...    seul l'écran atteint.
    [Arguments]    ${releve_ecran}    ${verrouillages_connus}
    ${sens}=    Establish Icon Meaning    ${releve_ecran}    ${COL_USER_LOCK_ICON}
    ...    ${KEY_COLUMNS_STANDARD_USERS}    ${verrouillages_connus}
    RETURN    ${sens}
