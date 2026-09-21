*** Settings ***
Documentation       **Extraction d'une grille ALV servie par le WebGUI**
...                 (SAP GUI for HTML / ITS) vers les CINQ formats de
...                 restitution : SVG, classeur Excel, CSV, JSON Lines et
...                 Parquet. LECTURE SEULE.
...
...                 C'est la même capacité que
...                 `tests/robot/ui/ecc/extraction_parametres_profil.robot`,
...                 vue depuis un autre canal, et l'intérêt est précisément là :
...                 les cinq écrivains sont indépendants du canal, la LECTURE
...                 ne l'est pas.
...
...                 **Ce que le WebGUI change, et le piège qu'il ajoute.** Une
...                 grille ALV y est rendue en HTML, et deux faits commandent
...                 tout. Le DOM ÉCLATE la grille en deux tables (colonnes
...                 figées d'un côté, défilantes de l'autre) alors que le SID de
...                 chaque cellule la ré-unifie : `Read Webgui Grid` adresse donc
...                 par SID et ignore la découpe. Et surtout, le serveur
...                 n'envoie qu'une PAGE de lignes (200 mesurées) qu'il
...                 renumérote à partir de 1 : une sélection de 2000 lignes rend
...                 200 lignes propres, complètes, numérotées 1 à 200. **Rien
...                 dans les lignes ne signale qu'il en manque 1800.** Seul le
...                 total que la grille DÉCLARE dans son `lsdata` fait la
...                 différence, et c'est ce que le scénario 8 démontre en
...                 provoquant le cas.
...
...                 **Trois gardes, les mêmes que sur le canal écran.**
...
...                 1. *La cible.* Les deux conteneurs du poste annoncent le
...                 même identifiant système, et l'ICF de l'un REDIRIGE vers le
...                 nom d'hôte virtuel que les deux partagent (relevé le
...                 2026-08-24) : viser le mauvais port ouvre une session
...                 parfaitement fonctionnelle sur l'autre système. Le Suite
...                 Setup prouve donc l'identité ET que l'adresse atteinte est
...                 bien celle demandée, avant toute lecture.
...                 2. *La complétude.* Le relevé est confronté au total
...                 DÉCLARÉ par la grille, dans le Suite Setup, donc AVANT
...                 qu'un fichier ne soit écrit. Un refus qui ne fait que
...                 constater n'empêche rien.
...                 3. *La fidélité.* Chaque fichier écrit est RELU et
...                 confronté ligne à ligne au relevé.
...
...                 **Prérequis.** Le service ICF `webgui` doit être actif
...                 (voir docs/ecc-validation.md). Exécution :
...                 | robot --pythonpath src
...                 | ...   -v WEBGUI_URL:"http://localhost:50000/sap/bc/gui/sap/its/webgui?sap-client=001"
...                 | ...   -v SAP_USER:DEVELOPER -v "SAP_PASSWORD: Secret:***"
...                 | ...   --outputdir results/webgui
...                 | ...   tests/robot/ui/fiori/extraction_grille_webgui.robot

Resource            ../../../../resources/fiori_keywords.resource
Library             Collections
Library             OperatingSystem
Library             XML
Library             sapfx_common.table_svg
Library             sapfx_common.table_xlsx
Library             sapfx_common.table_csv
Library             sapfx_common.table_json
Library             sapfx_common.table_parquet

Suite Setup         Ouvrir Le Canal Webgui
Suite Teardown      Close WebGui

Test Tags           webgui    extraction


*** Variables ***
# --- La cible. Aucun défaut d'identifiant (convention 11).
${WEBGUI_URL}               ${EMPTY}    # OBLIGATOIRE : -v WEBGUI_URL:"http://.../its/webgui?sap-client=NNN"
${SAP_USER}                 ${EMPTY}
${SAP_PASSWORD}             ${EMPTY}    # -v "SAP_PASSWORD: Secret:<motdepasse>"
${EXPECTED_SYSTEM}          A4H
${EXPECTED_CLIENT}          001

# --- Le tableau extrait. Une table présente sur tout système SAP, dont le
# volume se règle par le plafond de hits : c'est ce plafond, et non la table,
# qui décide si la lecture peut être complète (le serveur n'envoie qu'une page
# de 200 lignes).
${EXTRACTED_TABLE}          T100
${MAX_HITS}                 150
# Le plafond du scénario 8, délibérément AU-DELÀ de ce qu'une page peut porter.
${OVERFLOW_HITS}            2000
${MIN_ROWS}                 ${100}
${MIN_COLUMNS}              ${4}
# La colonne qui ne peut pas être vide : la langue d'un texte de message.
${KEY_COLUMN}               SPRSL

# --- Les sorties. Les noms portent la cible MESURÉE, jamais une constante.
${OUTPUT_PREFIX}            ${OUTPUT DIR}/webgui
${CSV_DELIMITER}            ,
${MAX_ROWS}                 ${None}
${MAX_CELL_CHARS}           ${0}
${SHEET_NAME}               WebGUI grid


*** Test Cases ***
La cible est bien le systeme demande
    [Documentation]    Deux gardes distinctes, et la seconde est celle qui mord
    ...    réellement sur ce banc : l'identifiant système ne DISTINGUE pas les
    ...    deux conteneurs du poste (ils annoncent le même), alors que l'adresse
    ...    atteinte, elle, les sépare. L'ICF sait rediriger vers le nom d'hôte
    ...    virtuel partagé, et une session ouverte ailleurs que là où on croit
    ...    produirait une extraction lisible et fausse.
    Should Be Equal    ${IDENTITE}[system_id]    ${EXPECTED_SYSTEM}
    Should Be Equal    ${IDENTITE}[client]    ${EXPECTED_CLIENT}
    Should Not Be Empty    ${IDENTITE}[user]
    ...    msg=La zone info système ne nomme aucun utilisateur : la session n'est pas (ou plus) ouverte.
    ${demande}=    Get Page Location    url=${WEBGUI_URL}
    Should Be Equal    ${ADRESSE}[host]    ${demande}[host]
    ...    msg=L'adresse atteinte (${ADRESSE}[host]) n'est pas celle demandée (${demande}[host]) : l'ICF a redirigé, et la session porte sur un AUTRE système que celui visé.
    Log    Cible : ${IDENTITE}[system_id] mandant ${IDENTITE}[client] sur ${ADRESSE}[host] (utilisateur ${IDENTITE}[user])

La grille est lue en entier
    [Documentation]    Confronte le relevé à ce que la grille DÉCLARE, et
    ...    vérifie que les colonnes sont celles qu'elle publie.
    ...
    ...    Les identifiants de colonnes sont TECHNIQUES (`SPRSL`, `ARBGB`) :
    ...    la grille WebGUI les publie elle-même dans son `lsdata`, ce sont
    ...    donc des clés indépendantes de la langue, exactement comme sur le
    ...    canal écran. Le canal UI5, lui, n'en offre pas.
    [Tags]    lecture
    Should Be Equal As Integers    ${RELEVE}[row_count]    ${RELEVE}[declared_rows]
    Should Be True    ${RELEVE}[complete]
    Should Be Equal As Integers    ${RELEVE}[blank_rows]    ${0}
    ${nb_colonnes}=    Get Length    ${COLONNES}
    Should Be True    ${nb_colonnes} >= ${MIN_COLUMNS}
    List Should Contain Value    ${COLONNES}    ${KEY_COLUMN}
    # La DERNIÈRE ligne autant que la première : c'est elle qui manque quand
    # une grille n'a rendu que sa première page.
    ${premiere}=    Set Variable    ${LIGNES}[0]
    ${derniere}=    Set Variable    ${LIGNES}[-1]
    Should Not Be Empty    ${premiere}[${KEY_COLUMN}]
    Should Not Be Empty    ${derniere}[${KEY_COLUMN}]
    ...    msg=La dernière ligne du relevé n'a pas de valeur dans ${KEY_COLUMN} : la lecture s'est arrêtée en chemin.
    # Le balayage des titres AFFICHÉS a-t-il seulement fonctionné ? La carte des
    # titres rebouche chaque trou par l'identifiant de colonne, donc elle a
    # exactement la même forme qu'on ait tout trouvé ou rien : `Dictionary
    # Should Contain Key` dessus ne peut pas échouer. Le compteur que la sonde
    # rend, lui, peut. Sur cette cible SE16 affiche les noms de champs, donc
    # titres et identifiants COÏNCIDENT : c'est précisément le cas où seul ce
    # compteur distingue un balayage réussi d'un repli silencieux, et le jour
    # où le préfixe de SID change de forme, cinq fichiers sortiraient en-têtés
    # d'identifiants techniques sans que rien ne le dise.
    ${nb_titres}=    Set Variable    ${RELEVE}[headers_found]
    Should Be Equal As Integers    ${nb_titres}    ${nb_colonnes}
    ...    msg=Le balayage des en-têtes a trouvé ${nb_titres} titre(s) pour ${nb_colonnes} colonne(s) : la carte des titres est retombée en silence sur les identifiants techniques.
    ${resume}=    Describe Table Extract    ${RELEVE}
    Log    ${resume}
    # Le contrat que la grille publie est JOURNALISÉ et non asserté : ces
    # valeurs sont une mesure sur cette cible un jour donné, pas une règle du
    # canal. Les consigner permet à une seconde mesure de confirmer ou de
    # démentir ; les asserter graverait un fait de banc.
    Log    Contrat publié par la grille : ${RELEVE}[declared_rows] lignes déclarées, ${RELEVE}[visible_rows] visibles, première ligne rendue numérotée ${RELEVE}[first_row_index], défilement « ${RELEVE}[scrolling] », seuil ${RELEVE}[client_cell_threshold] cellules, grilles sur l'écran : ${RELEVE}[candidates]

Le tableau est extrait en SVG
    [Documentation]    Écrit puis PARSE le document : un SVG mal formé s'ouvre
    ...    sur une page blanche, jamais sur une erreur.
    [Tags]    svg
    ${verdict}=    Write Table Svg    ${SVG_PATH}    ${LIGNES}
    ...    columns=${COLONNES}    title=${EXTRACTED_TABLE} (${EXPECTED_SYSTEM})
    ...    subtitle=${SOUS_TITRE}    headers=${TITRES}    max_rows=${MAX_ROWS}
    ...    max_cell_chars=${MAX_CELL_CHARS}
    Should Be Equal    ${verdict}[columns]    ${COLONNES}
    Should Be Equal As Integers    ${verdict}[total_rows]    ${RELEVE}[row_count]
    Should Be Equal As Integers    ${verdict}[truncated_cells]    ${0}
    Should Be Equal    ${verdict}[truncated_rows]    ${EXPECTED_TRUNCATION}
    # `keep_clark_notation` garde l'espace de noms : sans lui, Robot le
    # dépouille et l'assertion ne vérifie plus que le document est du SVG.
    ${document}=    Parse Xml    ${SVG_PATH}    keep_clark_notation=True
    Should Be Equal    ${document.tag}    {http://www.w3.org/2000/svg}svg
    ${contenu}=    Get File    ${SVG_PATH}
    # Le SVG est le seul des cinq formats sans lecteur : son contenu se prouve
    # sur le document. Un élément de texte par cellule non vide, donc au moins
    # un par ligne rendue.
    ${elements}=    Get Count    ${contenu}    <text
    Should Be True    ${elements} >= ${verdict}[rows]
    ...    msg=Le document ne porte que ${elements} élément(s) de texte pour ${verdict}[rows] ligne(s) : il est incomplet.
    # Témoins vérifiés NON VIDES avant usage : `Should Contain` avec une
    # aiguille vide est toujours vrai.
    ${premier}=    Set Variable    ${LIGNES}[0][${KEY_COLUMN}]
    ${dernier}=    Set Variable    ${LIGNES}[-1][${KEY_COLUMN}]
    Should Not Be Empty    ${premier}
    Should Not Be Empty    ${dernier}
    Should Contain    ${contenu}    ${premier}
    Should Contain    ${contenu}    ${dernier}
    Log    SVG écrit : ${verdict}[path] (${verdict}[rows]/${verdict}[total_rows] lignes, ${verdict}[bytes] octets)

Le tableau est extrait en classeur Excel
    [Documentation]    Écrit le classeur, le RELIT et le confronte ligne à
    ...    ligne au relevé : l'assertion reine. Toutes les cellules sont du
    ...    texte, sans quoi Excel retyperait un mandant `000` en zéro.
    [Tags]    xlsx
    ${verdict}=    Write Table Xlsx    ${XLSX_PATH}    ${LIGNES}
    ...    columns=${COLONNES}    sheet_name=${SHEET_NAME}
    ...    headers=${TITRES}    max_rows=${MAX_ROWS}
    Should Be Equal    ${verdict}[columns]    ${COLONNES}
    Should Be Equal As Integers    ${verdict}[oversized_cells]    ${0}
    Should Be Equal    ${verdict}[truncated_rows]    ${EXPECTED_TRUNCATION}
    ${relu}=    Read Table Xlsx    ${XLSX_PATH}
    ${attendu}=    Restreindre Le Releve Aux Colonnes    ${verdict}[headers]    ${verdict}[rows]
    Lists Should Be Equal    ${relu}    ${attendu}
    ...    msg=Le classeur ne porte pas exactement la grille lue.
    Log    Classeur écrit : ${verdict}[path] (feuille « ${verdict}[sheet] », ${verdict}[rows] lignes, ${verdict}[bytes] octets)

Le tableau est extrait en CSV
    [Documentation]    Écrit, RELIT, confronte, puis RAPPORTE le risque de
    ...    formule : une valeur commençant par `=`, `+`, `-` ou `@` est
    ...    exécutée à l'ouverture dans un tableur. Rien n'est neutralisé par
    ...    défaut, altérer une valeur mesurée en silence serait pire.
    [Tags]    csv
    ${verdict}=    Write Table Csv    ${CSV_PATH}    ${LIGNES}
    ...    columns=${COLONNES}    delimiter=${CSV_DELIMITER}
    ...    headers=${TITRES}    max_rows=${MAX_ROWS}
    Should Be Equal    ${verdict}[columns]    ${COLONNES}
    Should Be Equal    ${verdict}[encoding]    utf-8-sig
    ...    msg=Sans la marque d'ordre d'octets, Excel ouvrirait le fichier en codage local et détruirait les accents.
    Should Be Equal    ${verdict}[truncated_rows]    ${EXPECTED_TRUNCATION}
    Should Be Equal As Integers    ${verdict}[neutralized_cells]    ${0}
    ...    msg=Une extraction ne doit RIEN altérer par défaut.
    ${relu}=    Read Table Csv    ${CSV_PATH}
    ${attendu}=    Restreindre Le Releve Aux Colonnes    ${verdict}[headers]    ${verdict}[rows]
    Lists Should Be Equal    ${relu}    ${attendu}
    ...    msg=Le CSV ne porte pas exactement la grille lue.
    Log    CSV écrit : ${verdict}[path] (${verdict}[rows] lignes, séparateur « ${verdict}[delimiter] », ${verdict}[formula_cells] cellule(s) qu'un tableur lirait comme une formule)

Le tableau est extrait en JSON Lines pour une chaine d outils
    [Documentation]    Un objet par ligne, donc une lecture en FLUX : la forme
    ...    que lisent nativement pandas, R, DuckDB et les outils décisionnels.
    [Tags]    json
    ${verdict}=    Write Table Json    ${JSONL_PATH}    ${LIGNES}
    ...    columns=${COLONNES}    headers=${TITRES}    max_rows=${MAX_ROWS}
    ...    lines=${True}
    Should Be Equal    ${verdict}[format]    jsonl
    Should Be Equal    ${verdict}[columns]    ${COLONNES}
    Should Be Equal    ${verdict}[truncated_rows]    ${EXPECTED_TRUNCATION}
    ${relu}=    Read Table Json    ${JSONL_PATH}
    ${attendu}=    Restreindre Le Releve Aux Colonnes    ${verdict}[headers]    ${verdict}[rows]
    Lists Should Be Equal    ${relu}    ${attendu}
    ...    msg=Le JSON Lines ne porte pas exactement la grille lue.
    Log    JSON Lines écrit : ${verdict}[path] (${verdict}[rows] lignes, ${verdict}[bytes] octets)

Le tableau est extrait en Parquet quand le canal est disponible
    [Documentation]    Canal OPTIONNEL : il délègue à `pyarrow`, qui n'est pas
    ...    une dépendance des bibliothèques. Le scénario se SAUTE en nommant le
    ...    remède là où le binding manque, sur le patron du canal RFC.
    [Tags]    parquet
    ${statut}=    Parquet Channel Status
    IF    not ${statut}[available]
        Skip    Canal Parquet indisponible (${statut}[reason]). ${statut}[remedy]
    END
    ${verdict}=    Write Table Parquet    ${PARQUET_PATH}    ${LIGNES}
    ...    columns=${COLONNES}    headers=${TITRES}    max_rows=${MAX_ROWS}
    Should Be Equal    ${verdict}[columns]    ${COLONNES}
    ${relu}=    Read Table Parquet    ${PARQUET_PATH}
    ${attendu}=    Restreindre Le Releve Aux Colonnes    ${verdict}[headers]    ${verdict}[rows]
    Lists Should Be Equal    ${relu}    ${attendu}
    ...    msg=Le Parquet ne porte pas exactement la grille lue.
    Log    Parquet écrit : ${verdict}[path] (${verdict}[rows] lignes, ${verdict}[compression], ${verdict}[bytes] octets)

Une lecture amputee est REFUSEE au lieu d etre ecrite
    [Documentation]    La contre-épreuve, et c'est elle qui donne son sens aux
    ...    six scénarios précédents : le cas dangereux est PROVOQUÉ sur la
    ...    cible réelle, puis on vérifie que la garde le refuse.
    ...
    ...    On redemande la même table avec un plafond de hits très au-delà de
    ...    ce qu'une page WebGUI peut porter. La grille déclare alors des
    ...    milliers de lignes et n'en rend que 200, propres et numérotées à
    ...    partir de 1. Sans la confrontation au total déclaré, ces 200 lignes
    ...    s'écriraient dans cinq fichiers qu'aucune relecture ne pourrait
    ...    démasquer, puisqu'ils seraient fidèles à ce qui a été lu.
    [Tags]    contre-epreuve
    Go To WebGui Transaction    SE16
    WebGui Data Browser Should Be Open
    Display WebGui Table Contents    ${EXTRACTED_TABLE}    ${OVERFLOW_HITS}
    ${partiel}=    Extract Displayed WebGui Grid    key=${KEY_COLUMN}
    ...    source=${EXTRACTED_TABLE} plafonnée à ${OVERFLOW_HITS}
    Should Be True    ${partiel}[declared_rows] > ${partiel}[row_count]
    ...    msg=Le cas dangereux n'a PAS été provoqué : la grille a rendu ses ${partiel}[row_count] lignes en entier, donc cette contre-épreuve ne prouve rien. Monter ${OVERFLOW_HITS}.
    Should Be Equal As Integers    ${partiel}[blank_rows]    ${0}
    ...    msg=Ces lignes devraient être PROPRES : c'est ce qui rend le cas indétectable autrement que par le total déclaré.
    Should Be Equal    ${partiel}[complete]    ${False}
    ${erreur}=    Run Keyword And Expect Error    RELEVÉ REFUSÉ*
    ...    Table Extract Should Be Complete    ${partiel}
    # Le message doit NOMMER les deux nombres : un refus qui ne dit pas de
    # combien il manque envoie chercher la cause ailleurs.
    Should Contain    ${erreur}    ${partiel}[row_count] ligne(s) lues
    Should Contain    ${erreur}    ${partiel}[declared_rows] DÉCLARÉES
    Log    Refus obtenu sur un relevé de ${partiel}[row_count] lignes pour ${partiel}[declared_rows] déclarées : ${erreur}


*** Keywords ***
Ouvrir Le Canal Webgui
    [Documentation]    Ouvre la session, PROUVE la cible, affiche la table, lit
    ...    la grille une fois pour toutes et REFUSE un relevé amputé.
    ...
    ...    **Pourquoi tout cela vit ICI et non dans un scénario.** Une garde qui
    ...    constate après coup n'empêche rien : rejouée contre le mauvais
    ...    système, une suite dont la garde vivait dans un scénario a rougi sur
    ...    la cible ET écrit quatre fichiers du mauvais système, sous des noms
    ...    qui annonçaient le bon (relevé le 2026-09-15 sur le canal écran). Le
    ...    scénario 1 CONFRONTE ce que le Setup a relevé, il ne le remplace pas.
    Should Not Be Empty    ${WEBGUI_URL}
    ...    msg=WEBGUI_URL est obligatoire : -v WEBGUI_URL:"http://.../sap/bc/gui/sap/its/webgui?sap-client=NNN"
    Open WebGui    ${WEBGUI_URL}
    Log In To WebGui    ${SAP_USER}    ${SAP_PASSWORD}
    # Identité ATTENDUE et non lue à la volée : le bandeau se rend APRÈS les
    # premiers éléments de la page, donc une lecture enchaînée sur le login
    # rend parfois une identité VIDE, et la garde de cible refuserait alors
    # pour la mauvaise raison.
    ${identite}=    Read WebGui Session Identity
    ${adresse}=    Get Page Location
    Should Be Equal    ${identite}[system_id]    ${EXPECTED_SYSTEM}
    ...    msg=Cible REFUSÉE : la session ouverte vise le système ${identite}[system_id], pas ${EXPECTED_SYSTEM}. Aucune extraction n'est écrite. Adresse réellement atteinte : ${adresse}[url]
    Should Be Equal    ${identite}[client]    ${EXPECTED_CLIENT}
    ...    msg=Cible REFUSÉE : mandant ${identite}[client] au lieu de ${EXPECTED_CLIENT}.
    Set Suite Variable    ${IDENTITE}    ${identite}
    Set Suite Variable    ${ADRESSE}    ${adresse}
    # Les noms de fichiers portent la cible MESURÉE : un fichier ne peut pas
    # annoncer un système qu'il ne porte pas.
    ${marque}=    Set Variable
    ...    ${OUTPUT_PREFIX}_${identite}[system_id]_${identite}[client]_${EXTRACTED_TABLE}
    Set Suite Variable    ${SVG_PATH}    ${marque}.svg
    Set Suite Variable    ${XLSX_PATH}    ${marque}.xlsx
    Set Suite Variable    ${CSV_PATH}    ${marque}.csv
    Set Suite Variable    ${JSONL_PATH}    ${marque}.jsonl
    Set Suite Variable    ${PARQUET_PATH}    ${marque}.parquet
    Preparer Le Releve

Preparer Le Releve
    [Documentation]    Affiche la table et lit la grille UNE fois, pour toute la
    ...    suite : chaque extraction reste ainsi jouable SEULE
    ...    (`robot --test "... en CSV"`), et aucun scénario ne rougit en cascade
    ...    sur une variable qu'un autre n'a pas posée.
    Go To WebGui Transaction    SE16
    WebGui Data Browser Should Be Open
    Display WebGui Table Contents    ${EXTRACTED_TABLE}    ${MAX_HITS}
    ${extrait}=    Extract Displayed WebGui Grid    key=${KEY_COLUMN}
    ...    source=${EXTRACTED_TABLE} sur ${EXPECTED_SYSTEM}/${EXPECTED_CLIENT}
    ${resume}=    Describe Table Extract    ${extrait}
    Log    ${resume}
    Table Extract Should Be Complete    ${extrait}    min_rows=${MIN_ROWS}
    ...    min_columns=${MIN_COLUMNS}
    Set Suite Variable    ${RELEVE}    ${extrait}
    Set Suite Variable    ${LIGNES}    ${extrait}[rows]
    Set Suite Variable    ${COLONNES}    ${extrait}[columns]
    Set Suite Variable    ${TITRES}    ${extrait}[headers]
    Set Suite Variable    ${SOUS_TITRE}
    ...    ${EXPECTED_SYSTEM} mandant ${EXPECTED_CLIENT}, table ${EXTRACTED_TABLE}, ${extrait}[row_count] lignes (WebGUI)
    # Une troncature n'est légitime que si elle a été DEMANDÉE.
    ${tronque}=    Evaluate    $MAX_ROWS is not None and int($MAX_ROWS) < ${extrait}[row_count]
    Set Suite Variable    ${EXPECTED_TRUNCATION}    ${tronque}

Restreindre Le Releve Aux Colonnes
    [Documentation]    Le relevé mis dans la forme que le fichier écrit doit
    ...    porter : réduit aux lignes RÉELLEMENT écrites, et re-clé sur les
    ...    en-têtes du fichier. Sans la première réduction, `-v MAX_ROWS:50`
    ...    comparerait 50 lignes écrites à un relevé complet ; sans la seconde,
    ...    la confrontation opposerait des identifiants techniques à des titres
    ...    affichés et déclarerait un écart là où les deux portent la même
    ...    donnée sous deux noms.
    ...
    ...    L'argument de compte s'appelle `${nb_ecrites}` et non `${lignes}` :
    ...    les noms de variables Robot sont INSENSIBLES à la casse, donc un
    ...    argument `${lignes}` masquerait la variable de suite `${LIGNES}` et
    ...    le relevé deviendrait un entier au milieu du keyword.
    [Arguments]    ${entetes}    ${nb_ecrites}
    ${retenues}=    Get Slice From List    ${LIGNES}    0    ${nb_ecrites}
    ${attendu}=    Create List
    FOR    ${ligne}    IN    @{retenues}
        ${reduite}=    Create Dictionary
        FOR    ${index}    ${colonne}    IN ENUMERATE    @{COLONNES}
            ${valeur}=    Get From Dictionary    ${ligne}    ${colonne}
            Set To Dictionary    ${reduite}    ${entetes}[${index}]    ${valeur}
        END
        Append To List    ${attendu}    ${reduite}
    END
    RETURN    ${attendu}
