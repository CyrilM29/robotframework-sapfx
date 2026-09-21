*** Settings ***
Documentation       **Extraction du rapport « Display Profile Parameter »**
...                 (RSPARAM) d'un système ABAP vers CINQ
...                 formats de restitution : **SVG** vectoriel (une preuve à
...                 coller dans un rapport), **classeur Excel** (un relevé
...                 qu'on trie), **CSV**, **JSON Lines** (la forme que lisent
...                 pandas, R, DuckDB et les outils décisionnels) et
...                 **Parquet** (optionnel). LECTURE SEULE.
...
...                 Ce n'est pas une capture d'écran : c'est le CONTENU lu par
...                 l'API de scripting, redessiné. La différence porte tout
...                 l'intérêt de la suite. Une capture rend ce que le client a
...                 peint, avec sa langue, son profil d'affichage ALV et la
...                 résolution du poste ; l'extraction, elle, est rejouable,
...                 comparable d'un run à l'autre et exploitable par un script.
...
...                 **Le tableau est extrait tel que SAP le montre** : toutes
...                 les colonnes de la grille (cinq sur les deux releases du
...                 banc, dont la forme non substituée et le commentaire, qu'un
...                 contrôle de posture n'utilise pas), et les TITRES AFFICHÉS
...                 en en-tête
...                 des fichiers livrés. Les identifiants techniques restent
...                 les clés de lecture, parce qu'eux seuls sont indépendants
...                 de la langue (convention 3) : les deux noms coexistent,
...                 chacun là où il sert.
...
...                 **Trois gardes, chacune contre un résultat faux mais
...                 plausible.**
...
...                 1. *La cible.* Les deux conteneurs du poste partagent leur
...                 nom d'hôte et seul le PORT les distingue : une session
...                 ouverte sur 3200 au lieu de 3201 produirait une extraction
...                 parfaitement lisible, de l'autre système. Le scénario 1
...                 prouve la release avant toute lecture.
...                 2. *La complétude.* Le relevé lu est confronté au nombre de
...                 lignes que la grille DÉCLARE. Sans cette confrontation,
...                 « le rapport tient en N lignes » et « la lecture s'est
...                 arrêtée à N lignes » produisent le même fichier, et le
...                 second est un extrait présenté comme un inventaire.
...                 3. *La fidélité.* Chaque fichier écrit est RELU et
...                 confronté ligne à ligne au relevé d'écran. Un fichier qui
...                 existe et pèse le bon nombre d'octets n'est pas un fichier
...                 juste.
...
...                 **Elle n'est PAS liée à une release.** Validée live 7/7 sur
...                 les deux systèmes du banc le 2026-09-15 (ABAP Platform 2023
...                 release 758, puis A4H release 754), en surchargeant les deux
...                 seules variables de cible. Rien de ce qu'elle lit n'est
...                 gravé : ni les colonnes, ni leurs titres, ni le nombre de
...                 lignes. Viser une autre cible :
...                 | -v EXPECTED_RELEASE:754 -v PEER_RELEASE:758
...                 et le refus du Suite Setup donne lui-même cette ligne quand
...                 la session ouverte ne vise pas la release attendue.
...
...                 **Prérequis.** Une session SAP GUI doit être OUVERTE sur la
...                 cible : la suite s'y rattache et ne la ferme pas. C'est ce
...                 qui permet à cette extraction de ne demander AUCUN secret,
...                 ni en ligne de commande ni à travers un serveur
...                 intermédiaire. Le scripting doit être activé côté serveur.
...
...                 Exemple :
...                 | robot --pythonpath src --outputdir results/rsparam
...                 | ...   tests/robot/ui/ecc/extraction_parametres_profil.robot
...
...                 Le rapport complet dépasse le millier de lignes : le SVG est
...                 donc un document haut, fait pour être lu dans un navigateur
...                 ou intégré à un rapport. Pour une vue courte, passer
...                 `-v MAX_ROWS:50`, la troncature étant alors annoncée dans le
...                 pied du document et dans le verdict d'écriture.

Resource            ../../../../resources/security_screen_keywords.resource
Library             Collections
Library             OperatingSystem
Library             XML
Library             sapfx_common.table_svg
Library             sapfx_common.table_xlsx
Library             sapfx_common.table_csv
Library             sapfx_common.table_json
Library             sapfx_common.table_parquet

Suite Setup         Ouvrir Le Canal Ecran
Suite Teardown      Fermer Le Canal Ecran

Test Tags           secu    ecran    extraction


*** Variables ***
# --- La cible. Aucun identifiant ici : la suite se rattache à une session
# déjà ouverte (convention 11, et rien à masquer si rien n'est demandé).
# La release ATTENDUE est un défaut de poste, pas une propriété de la suite :
# elle se surcharge, et le refus du Setup rappelle comment. La release VOISINE
# sert de contre-épreuve, les deux conteneurs du banc partageant nom d'hôte et
# identifiant système.
${EXPECTED_RELEASE}         758
${PEER_RELEASE}             754
# Facultatif : deux conteneurs de MÊME release ne se distinguent que par leur
# noyau. Vide = non vérifié, et le scénario 1 le dit plutôt que de laisser
# croire que le risque est couvert.
${EXPECTED_KERNEL}          ${EMPTY}

# Le rapport de cette release en porte plus d'un millier ; le plancher est
# volontairement bas, il garde contre une lecture qui rendrait trois lignes.
${MIN_PARAMETERS}           ${1000}
# Les colonnes du rapport, mesurées sur la 758 : nom, valeur utilisateur,
# valeur par défaut, forme non substituée et commentaire. Le plancher garde
# contre une extraction amputée ; une release qui en ajoute une la rend quand
# même, la liste n'étant jamais gravée ici.
${MIN_COLUMNS}              ${5}

# --- Les sorties. ${None} = tout le tableau ; `-v MAX_ROWS:50` pour une vue
# courte, annoncée comme tronquée.
# Les noms de fichiers sont DÉRIVÉS de la cible mesurée (voir le Suite
# Setup) : un fichier ne peut pas annoncer une release qu'il ne porte pas.
# Le préfixe se surcharge (`-v OUTPUT_PREFIX:...`), jamais la release.
${OUTPUT_PREFIX}            ${OUTPUT DIR}/rsparam
# La virgule est la norme (RFC 4180) ; `-v CSV_DELIMITER:;` pour un Excel
# configuré en français, qui rendrait sinon une colonne unique.
${CSV_DELIMITER}            ,
${MAX_ROWS}                 ${None}
# 0 = aucune coupe. Le SVG est le seul format qui en fait une, et l'invariant
# de cette suite est l'intégralité : une valeur coupée ne survivrait que dans
# l'infobulle. Passer une valeur (80 par exemple) pour un document plus étroit,
# la coupe étant alors comptée dans le verdict et annoncée en pied de page.
${MAX_CELL_CHARS}           ${0}
${SHEET_NAME}               Profile parameters


*** Test Cases ***
La cible est bien la release ABAP 2023
    [Documentation]    Les deux conteneurs du poste annoncent le même
    ...    identifiant système et le même nom d'hôte : seuls la release et le
    ...    noyau les distinguent. Extraire le rapport du mauvais système
    ...    donnerait un fichier valide et faux, que rien dans le fichier ne
    ...    permettrait de démasquer, d'où cette garde AVANT toute lecture.
    Should Be Equal    ${IDENTITE}[anchor][basis_release]    ${EXPECTED_RELEASE}
    Should Not Be Equal    ${IDENTITE}[anchor][basis_release]    ${PEER_RELEASE}
    ...    msg=La cible et la release voisine portent le même numéro : la contre-épreuve ne distingue plus rien.
    Should Not Be Empty    ${IDENTITE}[anchor][kernel_release]
    ...    msg=Le noyau n'a pas été lu : deux conteneurs de même release resteraient indiscernables.
    # Le noyau n'est comparé que s'il est DÉCLARÉ : deux conteneurs de même
    # release s'y distinguent, mais l'imposer rendrait la suite dépendante
    # d'un fait de banc. Exiger un noyau non vide (ci-dessus) ne suffit pas à
    # couvrir le risque que le message nomme, et le dire est plus honnête que
    # de laisser croire l'inverse.
    IF    '${EXPECTED_KERNEL}' != '${EMPTY}'
        Should Be Equal    ${IDENTITE}[anchor][kernel_release]    ${EXPECTED_KERNEL}
        ...    msg=Le noyau mesuré (${IDENTITE}[anchor][kernel_release]) n'est pas celui attendu (${EXPECTED_KERNEL}) : même release, autre système.
    END
    Log    Cible : ${IDENTITE}[system_id]/${IDENTITE}[client] SAP_BASIS ${IDENTITE}[anchor][basis_release] kernel ${IDENTITE}[anchor][kernel_release]

Le rapport des parametres de profil est lu en entier
    [Documentation]    Lance RSPARAM avec les paramètres NON substitués (sans
    ...    quoi le rapport ne montrerait que ce que le profil pose, et c'est
    ...    justement l'ABSENCE d'un paramètre dans le profil qui est un
    ...    résultat), puis confronte le relevé au nombre de lignes que la
    ...    grille déclare.
    [Tags]    lecture
    ${lues}=    Get Length    ${RELEVE}
    # Le compte est RELU sur la grille APRÈS la lecture, et non repris de
    # celui qui a servi à la borner : confronter une lecture au plafond qu'on
    # lui a donné compare deux valeurs de la même source et ne peut pas
    # échouer. Ce qui est vérifié ici est que la grille n'a pas bougé pendant
    # la lecture ; la complétude du CONTENU, elle, est refusée au Suite Setup,
    # qui est le seul endroit où elle empêche d'écrire.
    ${declarees}=    Count Rows In Displayed Report
    Should Be Equal As Integers    ${lues}    ${declarees}
    ...    msg=La grille déclare maintenant ${declarees} lignes alors que ${lues} ont été lues : elle a changé pendant la lecture, le relevé n'est pas un instantané.
    Should Be Equal As Integers    ${LIGNES_VIDES}    ${0}
    ...    msg=Relevé creux : ${LIGNES_VIDES} ligne(s) entièrement vides (le Suite Setup aurait dû le refuser).
    # Les colonnes sont celles de la GRILLE, pas une liste gravée ici : une
    # release qui en ajoute une doit la voir entrer dans l'extraction, et les
    # trois colonnes d'un contrôle de posture ne sont pas le tableau.
    ${nb_colonnes}=    Get Length    ${COLONNES}
    List Should Contain Value    ${COLONNES}    ${COL_PARAM_NAME}
    List Should Contain Value    ${COLONNES}    ${COL_PARAM_PROFILE}
    List Should Contain Value    ${COLONNES}    ${COL_PARAM_DEFAULT}
    ${premiere}=    Set Variable    ${RELEVE}[0]
    ${derniere}=    Set Variable    ${RELEVE}[-1]
    Dictionary Should Contain Key    ${premiere}    ${COL_PARAM_NAME}
    # La DERNIÈRE ligne autant que la première : c'est elle qui manque quand
    # une grille n'a chargé que sa première fenêtre.
    Should Not Be Empty    ${derniere}[${COL_PARAM_NAME}]
    ...    msg=La dernière ligne du relevé n'a pas de nom de paramètre : la lecture s'est arrêtée en chemin.
    # Chaque colonne porte le titre que SAP AFFICHE : c'est lui que l'en-tête
    # des fichiers livrés doit montrer, les identifiants techniques ne parlant
    # qu'au développeur. Les deux restent disponibles, chacun à sa place.
    Dictionary Should Contain Key    ${TITRES}    ${COL_PARAM_NAME}
    Should Not Be Empty    ${TITRES}[${COL_PARAM_NAME}]
    ...    msg=La colonne ${COL_PARAM_NAME} n'a pas de titre affiché : l'en-tête livré retomberait sur l'identifiant technique.
    Log    Colonnes extraites (${nb_colonnes}) : ${TITRES}

Le tableau est extrait en SVG
    [Documentation]    Écrit le tableau en SVG, puis PARSE le fichier produit :
    ...    un SVG mal formé s'ouvre sur une page blanche, jamais sur une
    ...    erreur, donc le seul contrôle qui vaille est de le relire.
    ...
    ...    Le sous-titre porte l'identité de la cible et non la date : deux
    ...    extractions de la même configuration restent ainsi identiques à
    ...    l'octet près, et une différence entre deux fichiers signale une
    ...    différence du SYSTÈME. L'horodatage du run vit dans le log Robot.
    [Tags]    svg
    ${sous_titre}=    Set Variable
    ...    ${IDENTITE}[system_id] mandant ${IDENTITE}[client] SAP_BASIS ${IDENTITE}[basis_release] kernel ${IDENTITE}[kernel_release] (RSPARAM, paramètres non substitués inclus)
    ${verdict}=    Write Table Svg    ${SVG_PATH}    ${RELEVE}
    ...    columns=${COLONNES}    title=Display Profile Parameter
    ...    subtitle=${sous_titre}    headers=${TITRES}    max_rows=${MAX_ROWS}
    ...    max_cell_chars=${MAX_CELL_CHARS}
    ${total}=    Get Length    ${RELEVE}
    Should Be Equal    ${verdict}[columns]    ${COLONNES}
    Should Be Equal As Integers    ${verdict}[total_rows]    ${total}
    Should Be True    ${verdict}[bytes] > 0
    # `keep_clark_notation` garde l'espace de noms dans le tag : sans lui,
    # Robot le dépouille et l'assertion ne vérifierait plus que le document
    # est bien du SVG, seulement qu'il est du XML.
    Should Be Equal As Integers    ${verdict}[truncated_cells]    ${0}
    ...    msg=${verdict}[truncated_cells] cellule(s) coupées au rendu : le document ne porte pas le tableau intégralement (voir MAX_CELL_CHARS).
    Should Be Equal    ${verdict}[truncated_rows]    ${EXPECTED_TRUNCATION}
    ...    msg=Le document est tronqué alors que rien ne le demandait (ou l'inverse).
    ${document}=    Parse Xml    ${SVG_PATH}    keep_clark_notation=True
    Should Be Equal    ${document.tag}    {http://www.w3.org/2000/svg}svg
    ${contenu}=    Get File    ${SVG_PATH}
    # Le SVG est le seul des cinq formats sans lecteur : son contenu se prouve
    # donc sur le document lui-même. Un élément de texte par cellule non vide,
    # donc au MOINS un par ligne rendue : un writer qui n'écrirait qu'une ligne
    # sur mille passait les deux `Should Contain` qui tenaient lieu de preuve.
    ${elements}=    Get Count    ${contenu}    <text
    Should Be True    ${elements} >= ${verdict}[rows]
    ...    msg=Le document ne porte que ${elements} élément(s) de texte pour ${verdict}[rows] ligne(s) rendues : il est incomplet.
    Should Contain    ${contenu}    ${TITRES}[${COL_PARAM_NAME}]
    ...    msg=Le titre que SAP affiche pour ${COL_PARAM_NAME} manque de l'en-tête du document.
    # Les témoins sont vérifiés NON VIDES avant usage : `Should Contain` avec
    # une aiguille vide est toujours vrai, donc un relevé creux aurait fait
    # passer cette preuve-là aussi. Premier ET dernier, la dernière ligne étant
    # celle qui manque quand la grille n'a chargé que sa première fenêtre.
    ${premier}=    Set Variable    ${RELEVE}[0][${COL_PARAM_NAME}]
    ${dernier}=    Set Variable    ${RELEVE}[-1][${COL_PARAM_NAME}]
    Should Not Be Empty    ${premier}
    Should Not Be Empty    ${dernier}
    Should Contain    ${contenu}    ${premier}
    ...    msg=Le premier paramètre du relevé (${premier}) est absent du SVG.
    Should Contain    ${contenu}    ${dernier}
    ...    msg=Le dernier paramètre du relevé (${dernier}) est absent du SVG : le rendu s'arrête en chemin.
    Log    SVG écrit : ${verdict}[path] (${verdict}[rows]/${verdict}[total_rows] lignes, ${verdict}[truncated_cells] cellule(s) coupées au rendu, ${verdict}[bytes] octets)

Le tableau est extrait en classeur Excel
    [Documentation]    Écrit le tableau en .xlsx, puis le RELIT et le confronte
    ...    ligne à ligne au relevé d'écran : l'assertion reine de cette suite.
    ...
    ...    Toutes les cellules sont du texte, à dessein. Excel retype ce qu'il
    ...    lit, et un relevé SAP y perd ses zéros de tête (un mandant `000`
    ...    devient `0`) : la corruption se verrait à l'ouverture, pas à
    ...    l'écriture. L'aller-retour prouve que rien n'a été retypé.
    [Tags]    xlsx
    ${verdict}=    Write Table Xlsx    ${XLSX_PATH}    ${RELEVE}
    ...    columns=${COLONNES}    sheet_name=${SHEET_NAME}
    ...    headers=${TITRES}    max_rows=${MAX_ROWS}
    Should Be Equal    ${verdict}[columns]    ${COLONNES}
    Should Be Equal As Integers    ${verdict}[oversized_cells]    ${0}
    Should Be Equal    ${verdict}[truncated_rows]    ${EXPECTED_TRUNCATION}
    ...    msg=Le fichier est tronqué alors que rien ne le demandait (ou l'inverse) : aucun format sauf le SVG ne porte cette information DANS le fichier, donc elle s'asserte sur le verdict.
    ${relu}=    Read Table Xlsx    ${XLSX_PATH}
    ${attendu}=    Restreindre Le Releve Aux Colonnes    ${RELEVE}
    ...    ${verdict}[headers]    ${verdict}[rows]    ${COLONNES}
    Lists Should Be Equal    ${relu}    ${attendu}
    ...    msg=Le classeur ne porte pas exactement le relevé d'écran.
    Log    Classeur écrit : ${verdict}[path] (feuille « ${verdict}[sheet] », ${verdict}[rows]/${verdict}[total_rows] lignes, ${verdict}[bytes] octets)

Le tableau est extrait en CSV
    [Documentation]    Écrit le tableau en CSV, le RELIT et le confronte au
    ...    relevé d'écran, puis RAPPORTE le risque de formule.
    ...
    ...    Une valeur qui commence par `=`, `+`, `-` ou `@` est interprétée
    ...    comme une FORMULE à l'ouverture dans un tableur, et un relevé de
    ...    paramètres en porte réellement (une valeur négative commence par un
    ...    tiret). Rien n'est neutralisé ici : altérer une valeur mesurée en
    ...    silence serait pire que le risque. Le compte est journalisé, et
    ...    `Write Table Csv    neutralize_formulas=True` est le remède pour un
    ...    fichier destiné à être ouvert plutôt que lu par un script.
    [Tags]    csv
    ${verdict}=    Write Table Csv    ${CSV_PATH}    ${RELEVE}
    ...    columns=${COLONNES}    delimiter=${CSV_DELIMITER}
    ...    headers=${TITRES}    max_rows=${MAX_ROWS}
    Should Be Equal    ${verdict}[columns]    ${COLONNES}
    Should Be Equal    ${verdict}[encoding]    utf-8-sig
    Should Be Equal    ${verdict}[truncated_rows]    ${EXPECTED_TRUNCATION}
    ...    msg=Le fichier est tronqué alors que rien ne le demandait (ou l'inverse) : aucun format sauf le SVG ne porte cette information DANS le fichier, donc elle s'asserte sur le verdict.
    ...    msg=Sans la marque d'ordre d'octets, Excel ouvrirait le fichier en codage local et détruirait les accents.
    Should Be Equal As Integers    ${verdict}[neutralized_cells]    ${0}
    ...    msg=Une extraction ne doit RIEN altérer par défaut.
    ${relu}=    Read Table Csv    ${CSV_PATH}
    ${attendu}=    Restreindre Le Releve Aux Colonnes    ${RELEVE}
    ...    ${verdict}[headers]    ${verdict}[rows]    ${COLONNES}
    Lists Should Be Equal    ${relu}    ${attendu}
    ...    msg=Le CSV ne porte pas exactement le relevé d'écran.
    Log    CSV écrit : ${verdict}[path] (${verdict}[rows]/${verdict}[total_rows] lignes, séparateur « ${verdict}[delimiter] », ${verdict}[encoding], ${verdict}[formula_cells] cellule(s) qu'un tableur lirait comme une formule, ${verdict}[bytes] octets)


Le tableau est extrait en JSON Lines pour une chaine d outils
    [Documentation]    Écrit le tableau en JSON Lines, la forme que lisent
    ...    nativement pandas (`read_json(lines=True)`), R, DuckDB et les outils
    ...    décisionnels, puis le RELIT et le confronte au relevé d'écran.
    ...
    ...    Un objet par ligne, donc une lecture en FLUX : le fichier n'a pas à
    ...    tenir en mémoire, ce qui distingue cette forme du tableau JSON dès
    ...    que le relevé grossit. Les valeurs restent du texte, faute de quoi
    ...    un mandant `000` deviendrait un zéro à la lecture.
    [Tags]    json
    ${verdict}=    Write Table Json    ${JSONL_PATH}    ${RELEVE}
    ...    columns=${COLONNES}    headers=${TITRES}    max_rows=${MAX_ROWS}
    ...    lines=${True}
    Should Be Equal    ${verdict}[format]    jsonl
    Should Be Equal    ${verdict}[truncated_rows]    ${EXPECTED_TRUNCATION}
    ...    msg=Le fichier est tronqué alors que rien ne le demandait (ou l'inverse) : aucun format sauf le SVG ne porte cette information DANS le fichier, donc elle s'asserte sur le verdict.
    Should Be Equal    ${verdict}[columns]    ${COLONNES}
    ${relu}=    Read Table Json    ${JSONL_PATH}
    ${attendu}=    Restreindre Le Releve Aux Colonnes    ${RELEVE}
    ...    ${verdict}[headers]    ${verdict}[rows]    ${COLONNES}
    Lists Should Be Equal    ${relu}    ${attendu}
    ...    msg=Le JSON Lines ne porte pas exactement le relevé d'écran.
    Log    JSON Lines écrit : ${verdict}[path] (${verdict}[rows]/${verdict}[total_rows] lignes, ${verdict}[bytes] octets)

Le tableau est extrait en Parquet quand le canal est disponible
    [Documentation]    Parquet est un canal OPTIONNEL : il délègue à `pyarrow`,
    ...    qui n'est pas une dépendance des bibliothèques. Le scénario se SAUTE
    ...    en nommant le remède là où le binding manque, au lieu de rougir pour
    ...    un format absent, sur le patron du canal RFC.
    ...
    ...    Le typage y est IMPOSÉ en chaîne. Laissé libre, un écrivain Parquet
    ...    infère les types, un mandant `000` devient l'entier `0`, et le
    ...    fichier porte alors ce type pour toujours : la corruption est
    ...    irréversible là où celle d'un CSV se rattrape à la lecture.
    [Tags]    parquet
    ${statut}=    Parquet Channel Status
    IF    not ${statut}[available]
        Skip    Canal Parquet indisponible (${statut}[reason]). ${statut}[remedy]
    END
    ${verdict}=    Write Table Parquet    ${PARQUET_PATH}    ${RELEVE}
    ...    columns=${COLONNES}    headers=${TITRES}    max_rows=${MAX_ROWS}
    Should Be Equal    ${verdict}[columns]    ${COLONNES}
    Should Be Equal    ${verdict}[truncated_rows]    ${EXPECTED_TRUNCATION}
    ${relu}=    Read Table Parquet    ${PARQUET_PATH}
    ${attendu}=    Restreindre Le Releve Aux Colonnes    ${RELEVE}
    ...    ${verdict}[headers]    ${verdict}[rows]    ${COLONNES}
    Lists Should Be Equal    ${relu}    ${attendu}
    ...    msg=Le Parquet ne porte pas exactement le relevé d'écran.
    Log    Parquet écrit : ${verdict}[path] (${verdict}[rows]/${verdict}[total_rows] lignes, ${verdict}[compression], ${verdict}[bytes] octets, ${verdict}[writer])


*** Keywords ***
Ouvrir Le Canal Ecran
    [Documentation]    Rattache la suite à la session ouverte, PROUVE la cible,
    ...    puis extrait le rapport une fois pour toutes.
    ...
    ...    L'écran n'est PAS ouvert ici, et c'est délibéré : une session qui
    ...    préexiste rend cette extraction utilisable sans qu'aucun mot de
    ...    passe entre nulle part.
    ...
    ...    **Pourquoi la garde de cible vit ICI et non dans un scénario.**
    ...    Rejouée telle quelle contre l'autre conteneur du poste le
    ...    2026-09-15, la suite a bien rougi sur la release, et a quand même
    ...    écrit quatre fichiers du mauvais système, sous des noms qui
    ...    annonçaient la bonne. Une garde qui constate après coup ne protège
    ...    rien : refuser la cible doit empêcher l'extraction, pas la
    ...    commenter. Le scénario 1 reste, et confronte ce que le Setup a
    ...    relevé.
    Attach To Open Session    0    0
    ${identite}=    Get System Identity
    Should Be Equal    ${identite}[anchor][basis_release]    ${EXPECTED_RELEASE}
    ...    msg=Cible REFUSÉE : la session ouverte vise la release ${identite}[anchor][basis_release], pas ${EXPECTED_RELEASE}. Cause la plus probable : elle est connectée au port de l'autre conteneur (les deux partagent nom d'hôte ET identifiant système). Aucune extraction n'est écrite. Pour extraire cette cible-là : -v EXPECTED_RELEASE:${identite}[anchor][basis_release] -v PEER_RELEASE:${EXPECTED_RELEASE}
    Set Suite Variable    ${IDENTITE}    ${identite}
    # Les noms portent la cible MESURÉE, jamais une constante d'écriture.
    ${marque}=    Set Variable
    ...    ${OUTPUT_PREFIX}_${identite}[system_id]_${identite}[client]_${identite}[anchor][basis_release]
    Set Suite Variable    ${SVG_PATH}    ${marque}.svg
    Set Suite Variable    ${XLSX_PATH}    ${marque}.xlsx
    Set Suite Variable    ${CSV_PATH}    ${marque}.csv
    Set Suite Variable    ${JSONL_PATH}    ${marque}.jsonl
    Set Suite Variable    ${PARQUET_PATH}    ${marque}.parquet
    Preparer Le Releve

Preparer Le Releve
    [Documentation]    Exécute le rapport et lit la grille UNE fois, pour toute
    ...    la suite.
    ...
    ...    La lecture vit dans le Setup et non dans un scénario pour que chaque
    ...    extraction soit jouable SEULE (`robot --test "... en CSV"`), et pour
    ...    qu'aucun scénario ne rougisse en cascade sur une variable qu'un
    ...    autre n'a pas posée : ce genre d'échec désigne le mauvais coupable,
    ...    constaté en rejouant la suite contre l'autre conteneur. Le scénario
    ...    2 JUGE ce relevé, il ne le produit pas.
    Open Profile Parameter Report
    ${extrait}=    Extract Displayed Report
    ${lues}=    Set Variable    ${extrait}[row_count]
    # Le REFUS vit ici, et pas dans un scénario. La leçon de la garde de cible
    # vaut pour le CONTENU : un scénario qui rougit n'empêche pas les suivants
    # d'écrire, et sur un relevé creux les cinq extractions passent au vert
    # (comparer du vide à du vide ne rougit jamais, et `Should Contain` avec
    # une aiguille vide est toujours vrai). Rien ne doit être écrit.
    #
    # La règle de refus est COMMUNE aux trois canaux depuis le 2026-09-15 : la
    # même garde juge cette ALV, une grille WebGUI et une table UI5, alors que
    # chacune s'ampute autrement (cellules vides ici, page renumérotée là,
    # seuil de croissance ailleurs). Une règle par canal est une règle qu'un
    # canal de plus fait oublier.
    ${resume}=    Describe Table Extract    ${extrait}
    Log    ${resume}
    Table Extract Should Be Complete    ${extrait}    min_rows=${MIN_PARAMETERS}
    ...    min_columns=${MIN_COLUMNS}
    Set Suite Variable    ${RELEVE}    ${extrait}[rows]
    Set Suite Variable    ${COLONNES}    ${extrait}[columns]
    Set Suite Variable    ${TITRES}    ${extrait}[headers]
    Set Suite Variable    ${LIGNES_DECLAREES}    ${extrait}[declared_rows]
    Set Suite Variable    ${LIGNES_VIDES}    ${extrait}[blank_rows]
    # Une troncature n'est légitime que si elle a été DEMANDÉE : sans cela,
    # `-v MAX_ROWS:50` rendrait cinq fichiers partiels indiscernables d'un
    # inventaire complet (seul le SVG l'écrit dans le fichier).
    ${tronque}=    Evaluate    $MAX_ROWS is not None and int($MAX_ROWS) < ${lues}
    Set Suite Variable    ${EXPECTED_TRUNCATION}    ${tronque}

Fermer Le Canal Ecran
    [Documentation]    Ne ferme rien : la session préexistait à la suite. Le
    ...    seul état laissé à l'écran est le rapport affiché, que l'opérateur
    ...    quitte par F3.
    No Operation

Restreindre Le Releve Aux Colonnes
    [Documentation]    Le relevé d'écran mis dans la forme que le fichier
    ...    écrit doit porter : réduit aux lignes RÉELLEMENT écrites, et
    ...    re-clé sur les en-têtes du fichier.
    ...
    ...    Les deux réductions sont nécessaires et pour des raisons
    ...    différentes. Sans la première, une suite lancée avec
    ...    `-v MAX_ROWS:50` comparerait 50 lignes écrites à un relevé complet
    ...    et échouerait sur une troncature pourtant demandée. Sans la
    ...    seconde, la confrontation opposerait les identifiants techniques du
    ...    relevé aux titres SAP du fichier, et déclarerait un écart là où les
    ...    deux portent la même donnée sous deux noms.
    [Arguments]    ${releve}    ${entetes}    ${lignes}    ${colonnes}
    ${retenues}=    Get Slice From List    ${releve}    0    ${lignes}
    ${attendu}=    Create List
    FOR    ${ligne}    IN    @{retenues}
        ${reduite}=    Create Dictionary
        FOR    ${index}    ${colonne}    IN ENUMERATE    @{colonnes}
            ${valeur}=    Get From Dictionary    ${ligne}    ${colonne}
            Set To Dictionary    ${reduite}    ${entetes}[${index}]    ${valeur}
        END
        Append To List    ${attendu}    ${reduite}
    END
    RETURN    ${attendu}
