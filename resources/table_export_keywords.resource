*** Settings ***
Documentation       **EXEMPLE À PERSONNALISER.** Vocabulaire métier de la
...                 RESTITUTION d'un relevé tabulaire : écrire un relevé dans
...                 les cinq formats de fichier, puis le RELIRE et le
...                 confronter à sa source.
...
...                 Il vit à part des trois resources de canal parce qu'il ne
...                 parle d'AUCUN canal. C'est tout l'intérêt du contrat commun
...                 (`sapfx_common.table_extract`) : une fois qu'une ALV du
...                 client lourd, une grille WebGUI et une table UI5 rendent la
...                 même forme, l'écriture et sa vérification sont le MÊME
...                 geste, écrit une fois.
...
...                 Ce qui est vérifié à chaque format, et pourquoi :
...
...                 - le verdict d'écriture dit ce qui a RÉELLEMENT été écrit
...                   (lignes, colonnes, troncature) ;
...                 - quatre des cinq formats sont RELUS et confrontés ligne à
...                   ligne au relevé d'origine : un fichier qui existe et pèse
...                   le bon nombre d'octets n'est pas un fichier juste ;
...                 - le SVG, seul format sans lecteur, se prouve sur le
...                   document (un élément de texte par cellule non vide, donc
...                   au moins un par ligne rendue) ;
...                 - Parquet est OPTIONNEL et se saute en nommant son remède,
...                   au lieu de rougir pour un binding absent.

Library             Collections
Library             OperatingSystem
Library             XML
Library             sapfx_common.table_svg
Library             sapfx_common.table_xlsx
Library             sapfx_common.table_csv
Library             sapfx_common.table_json
Library             sapfx_common.table_parquet
Library             sapfx_common.table_extract


*** Keywords ***
Exporter Le Releve Vers Les Cinq Formats
    [Documentation]    Écrit le relevé dans les cinq formats sous le préfixe
    ...                `${marque}`, relit ce qui se relit, confronte, et rend
    ...                le bilan `{formats, fichiers, lignes, colonnes, octets}`.
    ...
    ...                `${marque}` doit porter la cible MESURÉE : un fichier ne
    ...                peut pas annoncer un système qu'il ne porte pas.
    ...
    ...                `max_cell_chars` vaut ZÉRO par défaut, c'est-à-dire
    ...                aucune coupe. L'écrivain SVG, lui, coupe à 80
    ...                caractères par défaut, ce qui convient à un aperçu et
    ...                jamais à une EXTRACTION : l'invariant de ce keyword est
    ...                l'intégralité, et une valeur coupée ne survivrait que
    ...                dans l'infobulle du document. Mesuré le 2026-09-15 : le
    ...                rapport des paramètres de profil y perdait 19 et 28
    ...                cellules selon la release.
    ...
    ...                `subtitle` porte l'identité de la CIBLE, jamais le
    ...                chemin de sortie : un document dont le sous-titre
    ...                contient son propre dossier n'est plus déterministe, et
    ...                deux extractions de la même configuration cessent d'être
    ...                comparables (le rejeu de la campagne l'a attrapé le
    ...                2026-09-15, les SVG différant d'un run à l'autre pendant
    ...                que CSV et JSON Lines restaient identiques à l'octet
    ...                près). Tout ce qui varie avec l'endroit d'où l'on joue
    ...                doit rester HORS des fichiers produits.
    [Arguments]    ${extrait}    ${marque}    ${sheet_name}=Extraction
    ...    ${csv_delimiter}=,    ${max_rows}=${None}    ${max_cell_chars}=${0}
    ...    ${subtitle}=${EMPTY}
    ${lignes}=    Set Variable    ${extrait}[rows]
    ${colonnes}=    Set Variable    ${extrait}[columns]
    ${titres}=    Set Variable    ${extrait}[headers]
    ${attendue}=    Evaluate    $max_rows is not None and int($max_rows) < ${extrait}[row_count]
    # Combien de lignes CHAQUE fichier doit porter. Sans ce nombre, la
    # confrontation ci-dessous se mordrait la queue : elle rétrécit le relevé
    # attendu au compte que l'écrivain DIT avoir écrit, donc un écrivain qui
    # plafonnerait à N lignes sur 28 782 et le rapporterait honnêtement
    # passerait, l'attendu étant ramené à N lui aussi (reproduit hors SAP le
    # 2026-09-16, sur la remarque d'une revue indépendante : le cas est
    # d'autant plus plausible que le volume est grand, et c'est la première
    # campagne à cette échelle). La borne reste celle DEMANDÉE, jamais celle
    # constatée.
    ${lignes_attendues}=    Evaluate
    ...    $extrait["row_count"] if $max_rows is None else min(int($max_rows), $extrait["row_count"])
    ${fichiers}=    Create Dictionary
    ${octets}=    Set Variable    ${0}

    # --- SVG : le seul format sans lecteur, prouvé sur le document ---------
    ${svg}=    Write Table Svg    ${marque}.svg    ${lignes}    columns=${colonnes}
    ...    title=${extrait}[source]    subtitle=${subtitle}    headers=${titres}
    ...    max_rows=${max_rows}    max_cell_chars=${max_cell_chars}
    Should Be Equal    ${svg}[columns]    ${colonnes}
    Should Be Equal    ${svg}[truncated_rows]    ${attendue}
    ...    msg=Le document SVG est tronqué alors que rien ne le demandait (ou l'inverse).
    Le Fichier Devrait Porter Toutes Les Lignes Attendues    ${svg}[rows]
    ...    ${lignes_attendues}    document SVG
    Should Be Equal As Integers    ${svg}[truncated_cells]    ${0}
    ...    msg=${svg}[truncated_cells] cellule(s) coupées au rendu SVG : le document ne porte pas le tableau intégralement, et la valeur entière ne survit que dans l'infobulle (voir max_cell_chars).
    ${document}=    Parse Xml    ${marque}.svg    keep_clark_notation=True
    Should Be Equal    ${document.tag}    {http://www.w3.org/2000/svg}svg
    ...    msg=Le fichier produit n'est pas du SVG. Sans `keep_clark_notation`, Robot dépouille l'espace de noms et cette assertion ne vérifierait plus que c'est du XML.
    ${contenu}=    Get File    ${marque}.svg
    ${textes}=    Get Count    ${contenu}    <text
    Should Be True    ${textes} >= ${svg}[rows]
    ...    msg=Le document ne porte que ${textes} élément(s) de texte pour ${svg}[rows] ligne(s) rendues : il est incomplet.
    Set To Dictionary    ${fichiers}    svg=${svg}[path]
    ${octets}=    Evaluate    ${octets} + ${svg}[bytes]

    # --- XLSX, CSV, JSON Lines : écrits PUIS relus et confrontés -----------
    ${xlsx}=    Write Table Xlsx    ${marque}.xlsx    ${lignes}    columns=${colonnes}
    ...    sheet_name=${sheet_name}    headers=${titres}    max_rows=${max_rows}
    Should Be Equal As Integers    ${xlsx}[oversized_cells]    ${0}
    Le Fichier Devrait Porter Toutes Les Lignes Attendues    ${xlsx}[rows]
    ...    ${lignes_attendues}    classeur Excel
    ${relu}=    Read Table Xlsx    ${marque}.xlsx
    Le Fichier Relu Devrait Porter Le Releve    ${relu}    ${extrait}
    ...    ${xlsx}[headers]    ${xlsx}[rows]    classeur Excel
    Set To Dictionary    ${fichiers}    xlsx=${xlsx}[path]
    ${octets}=    Evaluate    ${octets} + ${xlsx}[bytes]

    ${csv}=    Write Table Csv    ${marque}.csv    ${lignes}    columns=${colonnes}
    ...    delimiter=${csv_delimiter}    headers=${titres}    max_rows=${max_rows}
    Should Be Equal    ${csv}[encoding]    utf-8-sig
    ...    msg=Sans la marque d'ordre d'octets, Excel ouvrirait le fichier en codage local et détruirait les accents.
    Should Be Equal As Integers    ${csv}[neutralized_cells]    ${0}
    ...    msg=Une extraction ne doit RIEN altérer par défaut.
    Le Fichier Devrait Porter Toutes Les Lignes Attendues    ${csv}[rows]
    ...    ${lignes_attendues}    CSV
    ${relu}=    Read Table Csv    ${marque}.csv
    Le Fichier Relu Devrait Porter Le Releve    ${relu}    ${extrait}
    ...    ${csv}[headers]    ${csv}[rows]    CSV
    Set To Dictionary    ${fichiers}    csv=${csv}[path]
    ${octets}=    Evaluate    ${octets} + ${csv}[bytes]

    ${jsonl}=    Write Table Json    ${marque}.jsonl    ${lignes}    columns=${colonnes}
    ...    headers=${titres}    max_rows=${max_rows}    lines=${True}
    Should Be Equal    ${jsonl}[format]    jsonl
    Le Fichier Devrait Porter Toutes Les Lignes Attendues    ${jsonl}[rows]
    ...    ${lignes_attendues}    JSON Lines
    ${relu}=    Read Table Json    ${marque}.jsonl
    Le Fichier Relu Devrait Porter Le Releve    ${relu}    ${extrait}
    ...    ${jsonl}[headers]    ${jsonl}[rows]    JSON Lines
    Set To Dictionary    ${fichiers}    jsonl=${jsonl}[path]
    ${octets}=    Evaluate    ${octets} + ${jsonl}[bytes]

    # --- Parquet : canal OPTIONNEL, sauté en nommant son remède ------------
    ${statut}=    Parquet Channel Status
    IF    ${statut}[available]
        ${parquet}=    Write Table Parquet    ${marque}.parquet    ${lignes}
        ...    columns=${colonnes}    headers=${titres}    max_rows=${max_rows}
        Le Fichier Devrait Porter Toutes Les Lignes Attendues    ${parquet}[rows]
        ...    ${lignes_attendues}    Parquet
        ${relu}=    Read Table Parquet    ${marque}.parquet
        Le Fichier Relu Devrait Porter Le Releve    ${relu}    ${extrait}
        ...    ${parquet}[headers]    ${parquet}[rows]    Parquet
        Set To Dictionary    ${fichiers}    parquet=${parquet}[path]
        ${octets}=    Evaluate    ${octets} + ${parquet}[bytes]
    ELSE
        Log    Canal Parquet indisponible (${statut}[reason]). ${statut}[remedy]    WARN
    END

    ${formats}=    Get Dictionary Keys    ${fichiers}
    ${bilan}=    Create Dictionary    formats=${formats}    fichiers=${fichiers}
    ...    lignes=${svg}[rows]    colonnes=${colonnes}    octets=${octets}
    ...    tronque=${attendue}
    RETURN    ${bilan}

Les Deux Ecritures Devraient Etre Identiques A L Octet Pres
    [Documentation]    Confronte deux passages d'écriture du MÊME relevé,
    ...                format par format, sur leur CONTENU et pas sur leur
    ...                seule taille.
    ...
    ...                Ce que le déterminisme achète : il fait d'une différence
    ...                entre deux extractions une information sur le SYSTÈME.
    ...                Sans lui, comparer l'extraction d'aujourd'hui à celle du
    ...                mois dernier ne distingue pas un paramètre qui a bougé
    ...                d'un horodatage qui a changé.
    ...
    ...                Le contrôle a déjà mordu sur ce dépôt : le sous-titre
    ...                d'un document y portait le répertoire de sortie, et deux
    ...                passages dans deux dossiers rendaient des documents
    ...                différents pendant que les autres formats restaient
    ...                identiques à l'octet près. La taille, elle, n'aurait
    ...                rien vu : deux chemins de même longueur donnent deux
    ...                fichiers de même poids.
    ...
    ...                La comparaison passe par `Should Be True` et non par
    ...                `Should Be Equal` : sur plusieurs mégaoctets, l'échec du
    ...                second déverserait les deux contenus dans le journal.
    [Arguments]    ${bilan_a}    ${bilan_b}
    ${formats_a}=    Get Dictionary Keys    ${bilan_a}[fichiers]
    ${formats_b}=    Get Dictionary Keys    ${bilan_b}[fichiers]
    Should Not Be Empty    ${formats_a}
    ...    msg=Le premier passage n'a écrit aucun fichier : il n'y a rien à confronter.
    Lists Should Be Equal    ${formats_a}    ${formats_b}
    ...    msg=Les deux passages n'ont pas écrit les mêmes formats : la comparaison porterait sur des jeux différents.
    FOR    ${format}    IN    @{formats_a}
        ${chemin_a}=    Get From Dictionary    ${bilan_a}[fichiers]    ${format}
        ${chemin_b}=    Get From Dictionary    ${bilan_b}[fichiers]    ${format}
        Should Not Be Equal    ${chemin_a}    ${chemin_b}
        ...    msg=Les deux passages ont écrit le MÊME fichier (${chemin_a}) : comparer un fichier à lui-même ne prouve rien.
        ${a}=    Get Binary File    ${chemin_a}
        ${b}=    Get Binary File    ${chemin_b}
        ${taille_a}=    Get Length    ${a}
        ${taille_b}=    Get Length    ${b}
        Should Be Equal As Integers    ${taille_a}    ${taille_b}
        ...    msg=Le format ${format} n'est pas déterministe : ${taille_a} octets au premier passage, ${taille_b} au second. Quelque chose qui varie avec le moment ou l'endroit du run est entré dans le fichier.
        Should Be True    $a == $b
        ...    msg=Le format ${format} rend deux fichiers de MÊME taille mais de contenu différent : une valeur variable (date, chemin, identifiant de run) y est entrée sans en changer la longueur, ce qu'une comparaison de tailles n'aurait pas vu.
    END
    RETURN    ${formats_a}

Le Fichier Devrait Porter Toutes Les Lignes Attendues
    [Documentation]    Le fichier porte-t-il le nombre de lignes qu'on attend
    ...                de lui, ou seulement celles que l'écrivain a bien voulu
    ...                écrire ?
    ...
    ...                Cette assertion existe parce que la confrontation
    ...                ci-dessous ne peut PAS la faire : elle ramène le relevé
    ...                attendu au compte que l'écrivain DÉCLARE avoir écrit,
    ...                ce qu'elle doit faire pour qu'une troncature demandée ne
    ...                soit pas prise pour un défaut. Conséquence, reproduite
    ...                hors SAP le 2026-09-16 sur la remarque d'une revue
    ...                indépendante : un écrivain qui plafonnerait à N lignes
    ...                et le rapporterait honnêtement passerait, l'attendu
    ...                étant rétréci à N lui aussi. Le fichier serait alors
    ...                propre, relu sans écart, et amputé.
    ...
    ...                Le nombre attendu vient donc du RELEVÉ et de la borne
    ...                DEMANDÉE, jamais du verdict d'écriture. Les deux
    ...                assertions sont complémentaires : celle-ci compte, celle
    ...                d'en dessous compare le contenu.
    [Arguments]    ${ecrites}    ${attendues}    ${format}
    Should Be Equal As Integers    ${ecrites}    ${attendues}
    ...    msg=Le fichier ${format} porte ${ecrites} ligne(s) là où ${attendues} étaient attendues. La relecture ne l'aurait PAS vu : elle confronte le fichier à un relevé rétréci au compte que l'écrivain rapporte.

Le Fichier Relu Devrait Porter Le Releve
    [Documentation]    L'assertion reine : le fichier RELU, confronté ligne à
    ...                ligne au relevé d'origine.
    ...
    ...                Le relevé est d'abord mis dans la forme que le fichier
    ...                porte, et les deux réductions sont nécessaires pour des
    ...                raisons différentes. Sans la première (les lignes
    ...                réellement écrites), une extraction bornée comparerait
    ...                un extrait à un relevé complet et échouerait sur une
    ...                troncature pourtant demandée. Sans la seconde (les
    ...                en-têtes du fichier), la confrontation opposerait des
    ...                identifiants techniques à des titres affichés et
    ...                déclarerait un écart là où les deux portent la même
    ...                donnée sous deux noms.
    ...
    ...                La projection elle-même est de la LOGIQUE PURE et vit
    ...                dans la bibliothèque (`Project Extract Rows`), à côté du
    ...                contrat qu'elle sert : écrite en Robot, elle existait en
    ...                quatre exemplaires, et quatre corps qui prétendent
    ...                vérifier les mêmes fichiers finissent par ne plus
    ...                vérifier la même chose.
    [Arguments]    ${relu}    ${extrait}    ${entetes}    ${nb_ecrites}    ${format}
    ${attendu}=    Project Extract Rows    ${extrait}    ${entetes}    ${nb_ecrites}
    Lists Should Be Equal    ${relu}    ${attendu}
    ...    msg=Le fichier ${format} ne porte pas exactement le relevé lu sur la cible.
