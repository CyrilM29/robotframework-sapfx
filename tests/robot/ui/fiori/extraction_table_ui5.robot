*** Settings ***
Documentation       **Extraction d'une table UI5 (Fiori Elements) vers les CINQ
...                 formats** de restitution : SVG, classeur Excel, CSV, JSON
...                 Lines et Parquet. LECTURE SEULE, contre la cible locale
...                 cap-sflight, donc sans système SAP ni identifiants.
...
...                 Troisième canal de la même capacité, après le canal écran
...                 (`tests/robot/ui/ecc/extraction_parametres_profil.robot`) et
...                 le canal WebGUI (`extraction_grille_webgui.robot`). Les cinq
...                 écrivains sont identiques ; ce qui change, et qui fait
...                 l'objet de cette suite, c'est la LECTURE.
...
...                 **Ce que le canal UI5 change.**
...
...                 *Une table UI5 ne rend que ses lignes INSTANCIÉES.* Mesuré
...                 le 2026-09-15 : la List Report des voyages rend 30 lignes,
...                 son seuil de croissance, quand son binding en déclare 4133.
...                 Les 30 sont parfaitement remplies, correctement ordonnées,
...                 sans trou. C'est le pire des trois canaux de ce point de
...                 vue : l'ALV laisse au moins des cellules VIDES derrière
...                 elle, ici il ne reste aucune trace. Le scénario 2 provoque
...                 le cas sur la cible réelle et vérifie que la garde le
...                 refuse ; les scénarios d'écriture, eux, portent sur une
...                 table ENTIÈREMENT matérialisée.
...
...                 *Une table UI5 n'expose pas d'identifiant technique de
...                 colonne.* L'ALV et le WebGUI publient tous deux les noms de
...                 champs ABAP ; ici, la seule clé disponible est le LIBELLÉ
...                 affiché, donc traduit. Les clés du relevé sont par
...                 conséquent localisées, et le scénario 3 le CONSTATE plutôt
...                 que de le masquer : une suite qui asserterait un nom de
...                 colonne sur ce canal asserterait une traduction
...                 (convention 3).
...
...                 **Le périmètre de ce canal, et il est plus étroit que celui
...                 des deux autres.** L'extraction UI5 ne porte que les tables
...                 ENTIÈREMENT matérialisées. Une table plus grande que son
...                 seuil de croissance est REFUSÉE par conception, elle n'est
...                 pas supportée : faire grandir la table a été mesuré et
...                 écarté (`growingScrollToLoad` charge au défilement, ni le
...                 déclencheur ni le seuil ne la remplissent, et 138
...                 allers-retours pour matérialiser un écran est un
...                 contournement, pas une capacité). La parité des trois
...                 canaux porte donc sur la LECTURE et sur la garde, pas sur
...                 le volume extractible.
...
...                 **Prérequis.** La cible doit tourner :
...                 | cd _cap-sflight && npx cds watch    # -> localhost:4004
...                 Exécution :
...                 | robot --pythonpath src --outputdir results/ui5
...                 | ...   tests/robot/ui/fiori/extraction_table_ui5.robot
...                 `-v CAPSFLIGHT_HEADLESS:False` pour regarder le parcours.

Resource            ../../../../resources/page_objects/capsflight_travel.resource
Library             Collections
Library             OperatingSystem
Library             XML
Library             sapfx_common.table_svg
Library             sapfx_common.table_xlsx
Library             sapfx_common.table_csv
Library             sapfx_common.table_json
Library             sapfx_common.table_parquet

Suite Setup         Ouvrir Le Canal Ui5
Suite Teardown      Fermer Le Parcours Voyages

Test Tags           ui5    capsflight    extraction


*** Variables ***
${CAPSFLIGHT_HEADLESS}      ${True}
# Plancher volontairement bas : la fiche d'un voyage porte peu de
# réservations, et le sujet de la suite est la complétude, pas le volume.
${MIN_ROWS}                 ${1}
${MIN_COLUMNS}              ${5}
# Ce que la List Report doit déclarer AU MINIMUM pour que la contre-épreuve
# du scénario 2 prouve quelque chose : sans écart entre déclaré et rendu, elle
# ne démontrerait rien.
${MIN_DECLARED_LIST_ROWS}   ${100}

# --- Les sorties.
${OUTPUT_PREFIX}            ${OUTPUT DIR}/ui5_reservations
${CSV_DELIMITER}            ,
${MAX_ROWS}                 ${None}
${MAX_CELL_CHARS}           ${0}
${SHEET_NAME}               Reservations


*** Test Cases ***
La cible est bien l application attendue
    [Documentation]    Le risque de cible est plus faible ici que sur les deux
    ...    canaux SAP (aucun système partagé, une adresse locale explicite),
    ...    et le dire vaut mieux que de simuler une garde qui n'en est pas
    ...    une. Ce qui est vérifié est réel : l'adresse atteinte est celle
    ...    demandée, et le contrôle lu est bien une table UI5 qui porte ses
    ...    lignes, pas un conteneur qui les délègue.
    ${demandee}=    Get Page Location    url=${CAPSFLIGHT_URL}
    Should Be Equal    ${ADRESSE}[host]    ${demandee}[host]
    ...    msg=L'adresse atteinte (${ADRESSE}[url]) n'est pas celle demandée.
    Should Be Equal    ${RELEVE}[ui5_type]    sap.m.Table
    ...    msg=Le contrôle lu est un ${RELEVE}[ui5_type] : ce n'est pas la table qui matérialise les lignes.
    Log    Cible : ${ADRESSE}[url]

La table de la liste declare bien plus qu elle ne rend et son extraction est REFUSEE
    [Documentation]    Le coeur de la suite. La List Report est la table
    ...    dangereuse : son binding déclare des milliers de voyages, elle en
    ...    rend quelques dizaines, et les lignes rendues sont IRRÉPROCHABLES.
    ...
    ...    Le scénario établit les trois faits dans l'ordre : l'écart existe,
    ...    les lignes rendues ne le trahissent en rien (zéro ligne vide, donc
    ...    aucune garde de contenu ne pourrait le voir), et la garde de
    ...    complétude refuse quand même. Sans ce dernier point, cinq fichiers
    ...    parfaitement fidèles à une lecture partielle seraient écrits.
    [Tags]    contre-epreuve
    ${partiel}=    Extraire La Table Affichee    ${CAPSFLIGHT_LIST_TABLE}
    ...    liste des voyages
    Should Be True    ${partiel}[declared_rows] >= ${MIN_DECLARED_LIST_ROWS}
    ...    msg=La liste ne déclare que ${partiel}[declared_rows] lignes : l'écart est trop faible pour que cette contre-épreuve prouve quoi que ce soit.
    Should Be True    ${partiel}[row_count] < ${partiel}[declared_rows]
    ...    msg=Le cas dangereux n'a PAS été provoqué : la table a rendu ses ${partiel}[row_count] lignes en entier.
    Should Be Equal As Integers    ${partiel}[blank_rows]    ${0}
    ...    msg=Ces lignes devraient être PROPRES : c'est ce qui rend l'amputation indétectable autrement que par le total déclaré.
    Should Be Equal    ${partiel}[complete]    ${False}
    ${erreur}=    Run Keyword And Expect Error    RELEVÉ REFUSÉ*
    ...    Table Extract Should Be Complete    ${partiel}
    Should Contain    ${erreur}    ${partiel}[row_count] ligne(s) lues
    Should Contain    ${erreur}    ${partiel}[declared_rows] DÉCLARÉES
    Log    Liste : ${partiel}[row_count] lignes rendues (seuil de croissance ${partiel}[growing_threshold]) pour ${partiel}[declared_rows] déclarées. Refus : ${erreur}

Le releve de la fiche est lu en entier
    [Documentation]    La table extraite, elle, est ENTIÈREMENT matérialisée :
    ...    les lignes rendues atteignent le total déclaré.
    ...
    ...    Le second constat confronte DEUX lectures indépendantes de la même
    ...    table : `Get Ui5 Table Info` dérive les colonnes de `getColumns()`,
    ...    `Read Ui5 Table` dérive les clés de ses lignes de `getCells()`. Les
    ...    deux passent par des fonctions distinctes du bundle, donc leur
    ...    accord est une vraie propriété, que le Suite Setup fait d'ailleurs
    ...    déjà respecter (une colonne annoncée et absente de toutes les lignes
    ...    y fait échouer l'assemblage). Le scénario l'énonce pour qu'elle soit
    ...    visible, il n'en est pas le seul garant.
    ...
    ...    Ce qui n'est PAS asserté, et pourquoi : « les clés des colonnes sont
    ...    les titres affichés » est une propriété structurelle du canal, pas
    ...    une mesure. La carte des titres est construite comme l'identité,
    ...    donc toute assertion dessus serait vraie par construction. Le fait
    ...    est documenté, journalisé, et laissé hors des assertions.
    [Tags]    lecture
    Should Be Equal As Integers    ${RELEVE}[row_count]    ${RELEVE}[declared_rows]
    Should Be True    ${RELEVE}[complete]
    # Le caractère DÉFINITIF du total est désormais dans le contrat commun
    # (`declared_final`), donc refusé par le Suite Setup et non par ce seul
    # scénario : la suite est faite pour être jouée un scénario à la fois, et
    # un contrôle qui ne vit que dans le scénario 3 disparaît dès qu'on joue
    # l'extraction CSV seule.
    Should Be Equal    ${RELEVE}[declared_final]    ${True}
    Should Be Equal As Integers    ${RELEVE}[blank_rows]    ${0}
    ${nb_colonnes}=    Get Length    ${COLONNES}
    Should Be True    ${nb_colonnes} >= ${MIN_COLUMNS}
    # Toute clé présente dans les lignes et ABSENTE des colonnes extraites doit
    # être une colonne SANS NOM : une table UI5 en porte (l'indicateur de
    # brouillon de Fiori Elements est une colonne à en-tête vide, et une
    # colonne sans nom n'est pas extractible). Une clé NOMMÉE laissée de côté
    # serait tout autre chose : le témoin d'un décalage, c'est-à-dire d'un
    # relevé dont les valeurs ont glissé d'un cran. Le fichier serait alors
    # complet, propre, fidèle au relevé, et faux : c'est le seul défaut de ce
    # canal qu'aucune relecture de fichier ne pourrait démasquer.
    FOR    ${ignoree}    IN    @{RELEVE}[ignored_columns]
        Should Be Empty    ${ignoree.strip()}
        ...    msg=La colonne « ${ignoree} » est rendue par les lignes mais absente des colonnes déclarées : les deux lectures de la table divergent, et un décalage de colonnes produirait exactement ce symptôme.
    END
    ${resume}=    Describe Table Extract    ${RELEVE}
    Log    ${resume}
    Log    Propriété de canal : les clés de colonnes sont les titres AFFICHÉS (${COLONNES}), une table UI5 n'exposant aucun identifiant technique. Une assertion portée sur l'un de ces noms serait une assertion sur une traduction.

Le tableau est extrait en SVG
    [Documentation]    Écrit puis PARSE le document : un SVG mal formé s'ouvre
    ...    sur une page blanche, jamais sur une erreur.
    [Tags]    svg
    ${verdict}=    Write Table Svg    ${SVG_PATH}    ${LIGNES}
    ...    columns=${COLONNES}    title=Reservations d un voyage
    ...    subtitle=${SOUS_TITRE}    max_rows=${MAX_ROWS}
    ...    max_cell_chars=${MAX_CELL_CHARS}
    Should Be Equal    ${verdict}[columns]    ${COLONNES}
    Should Be Equal As Integers    ${verdict}[total_rows]    ${RELEVE}[row_count]
    Should Be Equal As Integers    ${verdict}[truncated_cells]    ${0}
    Should Be Equal    ${verdict}[truncated_rows]    ${EXPECTED_TRUNCATION}
    ${document}=    Parse Xml    ${SVG_PATH}    keep_clark_notation=True
    Should Be Equal    ${document.tag}    {http://www.w3.org/2000/svg}svg
    ${contenu}=    Get File    ${SVG_PATH}
    ${elements}=    Get Count    ${contenu}    <text
    Should Be True    ${elements} >= ${verdict}[rows]
    ...    msg=Le document ne porte que ${elements} élément(s) de texte pour ${verdict}[rows] ligne(s) : il est incomplet.
    Log    SVG écrit : ${verdict}[path] (${verdict}[rows] lignes, ${verdict}[bytes] octets)

Le tableau est extrait en classeur Excel
    [Documentation]    Écrit, RELIT et confronte ligne à ligne : l'assertion
    ...    reine. Tout est écrit en texte, sans quoi Excel retyperait les
    ...    identifiants à zéros de tête que portent les données SAP.
    [Tags]    xlsx
    ${verdict}=    Write Table Xlsx    ${XLSX_PATH}    ${LIGNES}
    ...    columns=${COLONNES}    sheet_name=${SHEET_NAME}    max_rows=${MAX_ROWS}
    Should Be Equal    ${verdict}[columns]    ${COLONNES}
    Should Be Equal As Integers    ${verdict}[oversized_cells]    ${0}
    ${relu}=    Read Table Xlsx    ${XLSX_PATH}
    ${attendu}=    Restreindre Le Releve Aux Colonnes    ${verdict}[headers]    ${verdict}[rows]
    Lists Should Be Equal    ${relu}    ${attendu}
    ...    msg=Le classeur ne porte pas exactement la table lue.
    Log    Classeur écrit : ${verdict}[path] (feuille « ${verdict}[sheet] », ${verdict}[rows] lignes)

Le tableau est extrait en CSV
    [Documentation]    Écrit, RELIT, confronte, puis RAPPORTE le risque de
    ...    formule (une valeur commençant par `=`, `+`, `-` ou `@` est exécutée
    ...    à l'ouverture dans un tableur). Rien n'est neutralisé par défaut.
    [Tags]    csv
    ${verdict}=    Write Table Csv    ${CSV_PATH}    ${LIGNES}
    ...    columns=${COLONNES}    delimiter=${CSV_DELIMITER}    max_rows=${MAX_ROWS}
    Should Be Equal    ${verdict}[columns]    ${COLONNES}
    Should Be Equal    ${verdict}[encoding]    utf-8-sig
    ...    msg=Sans la marque d'ordre d'octets, Excel ouvrirait le fichier en codage local et détruirait les accents, dont cette table est pleine.
    Should Be Equal As Integers    ${verdict}[neutralized_cells]    ${0}
    ${relu}=    Read Table Csv    ${CSV_PATH}
    ${attendu}=    Restreindre Le Releve Aux Colonnes    ${verdict}[headers]    ${verdict}[rows]
    Lists Should Be Equal    ${relu}    ${attendu}
    ...    msg=Le CSV ne porte pas exactement la table lue.
    Log    CSV écrit : ${verdict}[path] (${verdict}[rows] lignes, ${verdict}[formula_cells] cellule(s) qu'un tableur lirait comme une formule)

Le tableau est extrait en JSON Lines pour une chaine d outils
    [Documentation]    Un objet par ligne, donc une lecture en FLUX : la forme
    ...    que lisent nativement pandas, R, DuckDB et les outils décisionnels.
    [Tags]    json
    ${verdict}=    Write Table Json    ${JSONL_PATH}    ${LIGNES}
    ...    columns=${COLONNES}    max_rows=${MAX_ROWS}    lines=${True}
    Should Be Equal    ${verdict}[format]    jsonl
    Should Be Equal    ${verdict}[columns]    ${COLONNES}
    ${relu}=    Read Table Json    ${JSONL_PATH}
    ${attendu}=    Restreindre Le Releve Aux Colonnes    ${verdict}[headers]    ${verdict}[rows]
    Lists Should Be Equal    ${relu}    ${attendu}
    ...    msg=Le JSON Lines ne porte pas exactement la table lue.
    Log    JSON Lines écrit : ${verdict}[path] (${verdict}[rows] lignes, ${verdict}[bytes] octets)

Le tableau est extrait en Parquet quand le canal est disponible
    [Documentation]    Canal OPTIONNEL : il délègue à `pyarrow`, qui n'est pas
    ...    une dépendance des bibliothèques. Le scénario se SAUTE en nommant le
    ...    remède là où le binding manque.
    [Tags]    parquet
    ${statut}=    Parquet Channel Status
    IF    not ${statut}[available]
        Skip    Canal Parquet indisponible (${statut}[reason]). ${statut}[remedy]
    END
    ${verdict}=    Write Table Parquet    ${PARQUET_PATH}    ${LIGNES}
    ...    columns=${COLONNES}    max_rows=${MAX_ROWS}
    Should Be Equal    ${verdict}[columns]    ${COLONNES}
    ${relu}=    Read Table Parquet    ${PARQUET_PATH}
    ${attendu}=    Restreindre Le Releve Aux Colonnes    ${verdict}[headers]    ${verdict}[rows]
    Lists Should Be Equal    ${relu}    ${attendu}
    ...    msg=Le Parquet ne porte pas exactement la table lue.
    Log    Parquet écrit : ${verdict}[path] (${verdict}[rows] lignes, ${verdict}[compression], ${verdict}[bytes] octets)


*** Keywords ***
Ouvrir Le Canal Ui5
    [Documentation]    Ouvre l'application, navigue jusqu'à la table ENTIÈREMENT
    ...    matérialisée, la lit une fois pour toutes et REFUSE un relevé
    ...    amputé.
    ...
    ...    Le refus vit ICI et non dans un scénario : sur un relevé partiel,
    ...    les cinq écritures passent au vert, puisqu'un fichier fidèle à une
    ...    lecture partielle se relit sans écart. Un refus qui constate après
    ...    coup n'empêche rien (leçon payée le 2026-09-15 sur le canal écran).
    Ouvrir Le Parcours Voyages    headless=${CAPSFLIGHT_HEADLESS}
    Ouvrir La Premiere Fiche Voyage
    ${adresse}=    Get Page Location
    Set Suite Variable    ${ADRESSE}    ${adresse}
    ${extrait}=    Extraire La Table Affichee    ${CAPSFLIGHT_BOOKING_TABLE}
    ...    reservations d un voyage
    ${resume}=    Describe Table Extract    ${extrait}
    Log    ${resume}
    Table Extract Should Be Complete    ${extrait}    min_rows=${MIN_ROWS}
    ...    min_columns=${MIN_COLUMNS}
    Set Suite Variable    ${RELEVE}    ${extrait}
    Set Suite Variable    ${LIGNES}    ${extrait}[rows]
    Set Suite Variable    ${COLONNES}    ${extrait}[columns]
    Set Suite Variable    ${TITRES}    ${extrait}[headers]
    Set Suite Variable    ${SOUS_TITRE}
    ...    cap-sflight, ${extrait}[row_count] reservation(s) lues sur ${extrait}[declared_rows] declarees (canal UI5)
    Set Suite Variable    ${SVG_PATH}    ${OUTPUT_PREFIX}.svg
    Set Suite Variable    ${XLSX_PATH}    ${OUTPUT_PREFIX}.xlsx
    Set Suite Variable    ${CSV_PATH}    ${OUTPUT_PREFIX}.csv
    Set Suite Variable    ${JSONL_PATH}    ${OUTPUT_PREFIX}.jsonl
    Set Suite Variable    ${PARQUET_PATH}    ${OUTPUT_PREFIX}.parquet
    ${tronque}=    Evaluate    $MAX_ROWS is not None and int($MAX_ROWS) < ${extrait}[row_count]
    Set Suite Variable    ${EXPECTED_TRUNCATION}    ${tronque}

Restreindre Le Releve Aux Colonnes
    [Documentation]    Le relevé mis dans la forme que le fichier écrit doit
    ...    porter : réduit aux lignes RÉELLEMENT écrites, et re-clé sur les
    ...    en-têtes du fichier.
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
