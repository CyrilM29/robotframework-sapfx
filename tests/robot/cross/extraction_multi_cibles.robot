*** Settings ***
Documentation       **Capturer un tableau SAP et le sauvegarder en fichier.**
...                 Spec: specs/extraction-multi-cibles.md (sha256:0fd4e26b5ab8, 2026-09-16)
...                 Sur TOUTES les cibles du banc, en SÉQUENCE. LECTURE SEULE.
...
...                 Les trois suites d'extraction du dépôt visent chacune un
...                 canal. Celle-ci les enchaîne sur cinq cibles réelles et
...                 répond à la question qu'aucune ne pose : **la capacité
...                 tient-elle quand on change de canal ET de système sans rien
...                 changer d'autre que des variables ?**
...
...                 | Cible | Canal | Système | Tableau |
...                 | 1 | écran SAP GUI | A4H, release 754 | RSPARAM |
...                 | 2 | écran SAP GUI | ABAP 2023, release 758 | RSPARAM |
...                 | 3 | WebGUI (ITS) | A4H | Data Browser, table de messages |
...                 | 4 | WebGUI (ITS) | ABAP 2023 | Data Browser, table de messages |
...                 | 5 | UI5 (Fiori Elements) | cap-sflight local | réservations d'un voyage |
...
...                 **Ce que la séquence prouve et qu'un run isolé ne prouve
...                 pas.** Chaque cible ouvre SON canal, prouve SON identité,
...                 extrait, écrit cinq fichiers, les relit, puis referme son
...                 canal même en cas d'échec. Une cible qui tombe n'emporte
...                 pas les autres : le bilan de campagne dit alors laquelle,
...                 et le scénario final REFUSE un bilan où une cible prévue
...                 n'aurait rien produit. C'est la différence entre « ça a
...                 marché chez moi sur une cible » et « ça tient sur le banc ».
...
...                 **L'écriture est le MÊME geste pour les trois canaux**
...                 (`Exporter Le Releve Vers Les Cinq Formats`), parce que les
...                 trois lectures rendent la même forme
...                 (`sapfx_common.table_extract`). C'est le rendu concret du
...                 contrat commun : la campagne ne contient aucun code
...                 d'écriture propre à un canal.
...
...                 **Aucun identifiant n'a de valeur par défaut** (convention
...                 11). Une cible dont les identifiants manquent est SAUTÉE en
...                 le disant, jamais rouge : un banc partiel doit pouvoir
...                 jouer la campagne sur ce qu'il a.
...
...                 Exécution (toutes cibles) :
...                 | robot --pythonpath src --outputdir results/campagne
...                 | ...   -v "ECC_754_PASSWORD: Secret:***"  -v "ECC_758_PASSWORD: Secret:***"
...                 | ...   -v "WEBGUI_A4H_PASSWORD: Secret:***"  -v "WEBGUI_2023_PASSWORD: Secret:***"
...                 | ...   tests/robot/cross/extraction_multi_cibles.robot

Resource            ../../../resources/security_screen_keywords.resource
Resource            ../../../resources/fiori_keywords.resource
Resource            ../../../resources/table_export_keywords.resource
Resource            ../../../resources/page_objects/capsflight_travel.resource
Library             Collections
Library             OperatingSystem
Library             sapfx_common.artifacts
Library             sapfx_common.table_extract
# Le prédicat de présence d'un identifiant, livré par la bibliothèque : il ne
# MESURE jamais le secret et ne le fait entrer dans aucune expression.
Library             sapfx_common.secrets

Suite Setup         Ouvrir La Campagne
Suite Teardown      Clore La Campagne

Test Tags           extraction    cross    multi-cibles


*** Variables ***
# --- Cible 1 et 2 : le canal ÉCRAN (SAP GUI), deux releases.
${ECC_754_CONNECTION}       /H/vhcala4hci/S/3200
${ECC_754_USER}             DEVELOPER
${ECC_754_PASSWORD}         ${EMPTY}
${ECC_754_CLIENT}           001
${ECC_754_RELEASE}          754
${ECC_758_CONNECTION}       /H/vhcala4hci/S/3201
${ECC_758_USER}             DEVELOPER
${ECC_758_PASSWORD}         ${EMPTY}
${ECC_758_CLIENT}           001
${ECC_758_RELEASE}          758
${MIN_PARAMETERS}           ${1000}

# --- Cible 3 et 4 : le canal WebGUI. La STRATÉGIE de connexion est une
# variable de cible : un des deux systèmes rend un formulaire dont les champs
# restent à 0x0 (mesuré), et n'est joignable que par authentification d'en-tête.
${WEBGUI_A4H_URL}           http://localhost:50000/sap/bc/gui/sap/its/webgui?sap-client=001
${WEBGUI_A4H_USER}          DEVELOPER
${WEBGUI_A4H_PASSWORD}      ${EMPTY}
${WEBGUI_A4H_STRATEGY}      form
${WEBGUI_2023_URL}          https://localhost:50101/sap/bc/gui/sap/its/webgui?sap-client=001
${WEBGUI_2023_USER}         DEVELOPER
${WEBGUI_2023_PASSWORD}     ${EMPTY}
${WEBGUI_2023_STRATEGY}     basic
${WEBGUI_SYSTEM}            A4H
${WEBGUI_CLIENT}            001
# Le tableau visé et sa colonne clé vivent dans la couche vocabulaire
# (convention 1) : la suite ne nomme ni table, ni colonne, ni transaction.
# Le plafond de hits, lui, est un choix de CAMPAGNE : il décide de la
# complétude, le serveur n'envoyant qu'une page de lignes. 150 reste sous la
# page mesurée.
${WEBGUI_MAX_HITS}          150

# --- Cible 5 : le canal UI5. Rien à fournir : la cible tourne en local.
${CAPSFLIGHT_OPT_IN}        ${True}
# Budget élargi, et c'est une propriété de la CIBLE et non une pause déguisée :
# `npx cds watch` compile à la volée, donc le tout premier accès après un
# démarrage du serveur est lent (constaté : la table n'avait pas chargé au bout
# d'une minute juste après un redémarrage, et chargeait en quelques secondes au
# passage suivant). La valeur surcharge celle du page object.
${CAPSFLIGHT_TIMEOUT}       150s

# --- Sorties communes.
${OUTPUT_PREFIX}            ${OUTPUT DIR}/campagne
${CAMPAIGN_ARTIFACT}        ${OUTPUT DIR}/campagne_extraction.json
${CSV_DELIMITER}            ,
${MAX_ROWS}                 ${None}


*** Test Cases ***
Cible 1 : canal ecran, release 754
    [Documentation]    Le rapport des paramètres de profil d'un premier système
    ...    ABAP, lu par l'API de scripting SAP GUI et sauvegardé en cinq
    ...    fichiers.
    [Tags]    ecran    a4h
    [Teardown]    Fermer Le Canal Ecran    754
    Extraire Un Rapport D Ecran    754    ${ECC_754_CONNECTION}    ${ECC_754_USER}
    ...    ${ECC_754_PASSWORD}    ${ECC_754_CLIENT}    ${ECC_754_RELEASE}

Cible 2 : canal ecran, release 758
    [Documentation]    Le MÊME rapport sur l'autre release, sans rien changer
    ...    d'autre que des variables. Les deux conteneurs du poste partagent
    ...    nom d'hôte ET identifiant système : seule la release les distingue,
    ...    et l'extraction du mauvais système serait parfaitement lisible.
    [Tags]    ecran    abap2023
    [Teardown]    Fermer Le Canal Ecran    758
    Extraire Un Rapport D Ecran    758    ${ECC_758_CONNECTION}    ${ECC_758_USER}
    ...    ${ECC_758_PASSWORD}    ${ECC_758_CLIENT}    ${ECC_758_RELEASE}

Cible 3 : canal WebGUI, premier systeme
    [Documentation]    La même capacité vue du WebGUI (SAP GUI for HTML) : une
    ...    ALV rendue en HTML, lue par les SID de ses cellules.
    [Tags]    webgui    a4h
    [Teardown]    Fermer Le Canal Webgui
    Extraire Une Grille Webgui    webgui-a4h    ${WEBGUI_A4H_URL}
    ...    ${WEBGUI_A4H_USER}    ${WEBGUI_A4H_PASSWORD}    ${WEBGUI_A4H_STRATEGY}
    ...    ${False}

Cible 4 : canal WebGUI, second systeme
    [Documentation]    Le même canal sur l'autre système, et c'est la cible qui
    ...    a fait apparaître un fait de banc : son formulaire de connexion rend
    ...    TOUS ses champs à 0x0, en HTTP comme en HTTPS (14 champs, 0 visible),
    ...    donc hors d'atteinte de n'importe quel moteur, là où la cible 3 en
    ...    rend 5 visibles. La stratégie de connexion est donc une variable de
    ...    cible, pas une constante du canal. La CAUSE reste non établie :
    ...    l'avertissement d'absence de bascule HTTPS avait paru l'expliquer,
    ...    une seconde mesure l'a trouvé aussi sur la cible 3, dont le
    ...    formulaire fonctionne.
    [Tags]    webgui    abap2023
    [Teardown]    Fermer Le Canal Webgui
    Extraire Une Grille Webgui    webgui-2023    ${WEBGUI_2023_URL}
    ...    ${WEBGUI_2023_USER}    ${WEBGUI_2023_PASSWORD}    ${WEBGUI_2023_STRATEGY}
    ...    ${True}

Cible 5 : canal UI5, application Fiori Elements
    [Documentation]    Le troisième canal : une table UI5 entièrement
    ...    matérialisée, extraite vers les mêmes cinq formats. La cible tourne
    ...    en local et ne demande aucun identifiant.
    [Tags]    ui5    capsflight
    [Teardown]    Fermer Le Canal Ui5
    IF    not ${UI5_DEMANDE}
        Skip    Cible UI5 désactivée (-v CAPSFLIGHT_OPT_IN:False).
    END
    Ouvrir Le Parcours Voyages
    Ouvrir La Premiere Fiche Voyage
    ${adresse}=    Get Page Location
    ${extrait}=    Extraire La Table Affichee    ${CAPSFLIGHT_BOOKING_TABLE}
    ...    reservations d un voyage (cap-sflight)
    ${resume}=    Describe Table Extract    ${extrait}
    Log    ${resume}
    Table Extract Should Be Complete    ${extrait}    min_rows=${1}    min_columns=${5}
    ${bilan}=    Exporter Le Releve Vers Les Cinq Formats    ${extrait}
    ...    ${OUTPUT_PREFIX}_ui5_capsflight    sheet_name=Reservations
    ...    csv_delimiter=${CSV_DELIMITER}    max_rows=${MAX_ROWS}
    ...    subtitle=cap-sflight, ${extrait}[row_count] reservation(s) (canal UI5)
    Consigner La Cible    ui5-capsflight    UI5    cap-sflight    ${EMPTY}
    ...    ${adresse}[host]    ${extrait}    ${bilan}

Le bilan de campagne est complet et deterministe
    [Documentation]    Le scénario qui donne son sens à la séquence. Il écrit un
    ...    artefact déterministe du passage, le RELIT (son empreinte est
    ...    recalculée sur le périmètre déclaré, donc un fichier retouché est
    ...    refusé et non comparé), et refuse un bilan où une cible PRÉVUE
    ...    n'aurait rien produit.
    ...
    ...    Sans lui, une campagne dont trois cibles sur cinq seraient tombées
    ...    laisserait quand même derrière elle des fichiers parfaitement
    ...    valides, et le dossier de sortie ressemblerait à un succès.
    [Tags]    bilan
    ${jouees}=    Get Length    ${REGISTRE}
    Should Be Equal As Integers    ${jouees}    ${CIBLES_PREVUES}
    ...    msg=${jouees} cible(s) ont produit un relevé sur les ${CIBLES_PREVUES} prévues par cette exécution : la campagne est incomplète et son dossier de sortie ne le montrerait pas.
    FOR    ${cle}    ${entree}    IN    &{REGISTRE}
        Should Be True    ${entree}[complete]
        ...    msg=La cible ${cle} a produit un relevé INCOMPLET : il ne devait pas être écrit.
        Should Be True    ${entree}[rows] > 0    msg=La cible ${cle} n'a lu aucune ligne.
        Length Should Be    ${entree}[formats]    ${FORMATS_ATTENDUS}
        ...    msg=La cible ${cle} n'a produit que ${entree}[formats] au lieu des ${FORMATS_ATTENDUS} formats attendus.
    END
    ${charge}=    Create Dictionary    cibles=${REGISTRE}
    ${chemin}=    Write Deterministic Artifact    ${CAMPAIGN_ARTIFACT}    ${charge}
    ...    hashed_keys=cibles
    ${relu}=    Read Deterministic Artifact    ${chemin}
    Should Be Equal    ${relu}[cibles]    ${REGISTRE}
    ...    msg=L'artefact relu ne porte pas le registre écrit.
    Log    Campagne : ${jouees} cible(s), empreinte ${relu}[sha256]. Artefact : ${chemin}
    Log Dictionary    ${REGISTRE}


*** Keywords ***
Ouvrir La Campagne
    [Documentation]    Prépare le registre et COMPTE les cibles que cette
    ...    exécution peut réellement jouer, d'après les identifiants fournis.
    ...
    ...    Ce compte est le dénominateur du scénario de bilan. Le calculer
    ...    ICI, avant toute cible, est ce qui empêche le bilan de se vérifier
    ...    lui-même : compté après coup, il vaudrait toujours le nombre de
    ...    cibles qui ont réussi.
    ${registre}=    Create Dictionary
    Set Suite Variable    ${REGISTRE}    ${registre}
    Set Suite Variable    ${FORMATS_ATTENDUS}    ${5}
    ${statut}=    Parquet Channel Status
    IF    not ${statut}[available]
        Set Suite Variable    ${FORMATS_ATTENDUS}    ${4}
        Log    Canal Parquet indisponible : la campagne attend 4 formats par cible. ${statut}[remedy]    WARN
    END
    # `Secret Is Provided` et non un test maison : le prédicat est livré par la
    # bibliothèque (convention 12), et surtout un `Evaluate` construit son
    # expression par SUBSTITUTION DE TEXTE. Un mot de passe passé en clair y
    # entrerait dans du source Python, et une apostrophe ou un antislash
    # dedans produirait une erreur de syntaxe dont le message porte
    # l'expression, donc le mot de passe, dans le journal. Rien n'oblige
    # l'opérateur à employer la forme `Secret:`.
    ${prevues}=    Set Variable    ${0}
    FOR    ${secret}    IN    ${ECC_754_PASSWORD}    ${ECC_758_PASSWORD}
    ...    ${WEBGUI_A4H_PASSWORD}    ${WEBGUI_2023_PASSWORD}
        ${fourni}=    Secret Is Provided    ${secret}
        IF    ${fourni}
            ${prevues}=    Evaluate    ${prevues} + 1
        END
    END
    # L'opt-in arrive en CHAÎNE depuis la ligne de commande : `IF not ${VAR}`
    # ne marcherait que pour les littéraux Python (`False` passe, `false` et
    # `no` font tomber le Setup sur une erreur opaque, alors que c'est ce
    # drapeau que le message de saut recommande à l'opérateur).
    ${ui5_demande}=    Convert To Boolean    ${CAPSFLIGHT_OPT_IN}
    Set Suite Variable    ${UI5_DEMANDE}    ${ui5_demande}
    IF    ${ui5_demande}
        ${prevues}=    Evaluate    ${prevues} + 1
    END
    Set Suite Variable    ${CIBLES_PREVUES}    ${prevues}
    Should Be True    ${prevues} > 0
    ...    msg=Aucune cible n'est jouable : toutes les cibles demandent un mot de passe (convention 11, aucune valeur par défaut) et la cible UI5 est désactivée. Voir la documentation de la suite pour la ligne de commande.
    Log    Cibles jouables par cette exécution : ${prevues}, ${FORMATS_ATTENDUS} format(s) attendus par cible.

Clore La Campagne
    [Documentation]    Ferme tout ce qui aurait survécu à un échec. Les
    ...    teardowns de scénario ferment déjà chaque canal ; ceci est le filet,
    ...    parce qu'une session laissée ouverte décale les indices de connexion
    ...    et fait rattacher la SUIVANTE au mauvais système.
    Run Keyword And Ignore Error    Close All Sap Sessions
    Run Keyword And Ignore Error    Close Browser    ALL

Extraire Un Rapport D Ecran
    [Documentation]    Une cible du canal écran, de bout en bout : ouverture de
    ...    SA session, preuve de SA release, lecture, refus d'un relevé
    ...    incomplet, écriture des cinq formats, consignation.
    [Arguments]    ${alias}    ${connexion}    ${user}    ${password}    ${client}
    ...    ${release}
    ${fourni}=    Secret Is Provided    ${password}
    IF    not ${fourni}
        Skip    Cible écran ${release} sautée : aucun mot de passe fourni (-v "ECC_${release}_PASSWORD: Secret:***").
    END
    Open Sap Logon
    Open Sap Session    ${alias}    connection_string=${connexion}    user=${user}
    ...    password=${password}    client=${client}
    ${identite}=    Get System Identity
    Should Be Equal    ${identite}[anchor][basis_release]    ${release}
    ...    msg=Cible REFUSÉE : la session ouverte sur ${connexion} vise la release ${identite}[anchor][basis_release], pas ${release}. Les deux conteneurs du poste partagent nom d'hôte ET identifiant système : seul le port les distingue. Aucun fichier n'est écrit.
    Open Profile Parameter Report
    ${extrait}=    Extract Displayed Report
    ${resume}=    Describe Table Extract    ${extrait}
    Log    ${resume}
    Table Extract Should Be Complete    ${extrait}    min_rows=${MIN_PARAMETERS}
    ...    min_columns=${5}
    ${marque}=    Set Variable
    ...    ${OUTPUT_PREFIX}_ecran_${identite}[system_id]_${identite}[client]_${release}
    ${bilan}=    Exporter Le Releve Vers Les Cinq Formats    ${extrait}    ${marque}
    ...    sheet_name=Profile parameters    csv_delimiter=${CSV_DELIMITER}
    ...    max_rows=${MAX_ROWS}
    ...    subtitle=${identite}[system_id] mandant ${identite}[client] SAP_BASIS ${identite}[anchor][basis_release] kernel ${identite}[anchor][kernel_release]
    Consigner La Cible    ecran-${release}    ecran SAP GUI    ${identite}[system_id]
    ...    ${identite}[client]    release ${identite}[anchor][basis_release] kernel ${identite}[anchor][kernel_release]
    ...    ${extrait}    ${bilan}

Fermer Le Canal Ecran
    [Documentation]    Ferme la session de CETTE cible, même après un échec.
    ...
    ...    Fermer par alias PUIS tout fermer, et le second n'est pas une
    ...    précaution de style : au premier passage de cette campagne, la cible
    ...    1 a échoué, son teardown a fermé son alias, et la cible 2 s'est
    ...    quand même ouverte sur `con[1]`, donc derrière une connexion
    ...    survivante. Une connexion orpheline décale les indices, et la
    ...    campagne enchaîne délibérément deux systèmes qui partagent leur nom
    ...    d'hôte : c'est exactement la situation où l'on se rattache au
    ...    mauvais. Chaque cible possède son canal seule, donc tout fermer est
    ...    ici le geste juste, pas un excès.
    [Arguments]    ${alias}
    Run Keyword And Ignore Error    Close Sap Session    ${alias}
    Run Keyword And Ignore Error    Close All Sap Sessions

Extraire Une Grille Webgui
    [Documentation]    Une cible du canal WebGUI, de bout en bout. La stratégie
    ...    de connexion est passée par la cible : voir `Open WebGui Session`.
    [Arguments]    ${nom}    ${url}    ${user}    ${password}    ${strategie}
    ...    ${https_errors}
    ${fourni}=    Secret Is Provided    ${password}
    IF    not ${fourni}
        Skip    Cible ${nom} sautée : aucun mot de passe fourni.
    END
    ${identite}=    Open WebGui Session    ${url}    ${user}    ${password}
    ...    strategy=${strategie}    ignore_https_errors=${https_errors}
    Should Be Equal    ${identite}[system_id]    ${WEBGUI_SYSTEM}
    ...    msg=Cible REFUSÉE : la session WebGUI ouverte sur ${url} vise le système ${identite}[system_id], pas ${WEBGUI_SYSTEM}.
    Should Be Equal    ${identite}[client]    ${WEBGUI_CLIENT}
    # Les deux gardes ci-dessus ne DISCRIMINENT PAS les deux systèmes du banc :
    # ils annoncent le même identifiant et le même mandant, et la zone info du
    # WebGUI ne porte ni release ni kernel. C'est une garde plus FAIBLE que
    # celle du canal écran, qui prouve la release. Le seul discriminant de ce
    # canal est l'ADRESSE réellement atteinte, et il faut la vérifier parce que
    # l'ICF sait rediriger vers le nom d'hôte virtuel que les deux partagent.
    ${demandee}=    Get Page Location    url=${url}
    ${atteinte}=    Get Page Location
    Should Be Equal    ${atteinte}[host]    ${demandee}[host]
    ...    msg=Cible REFUSÉE : l'adresse atteinte (${atteinte}[host]) n'est pas celle demandée (${demandee}[host]). Sur ce canal c'est le SEUL discriminant : les deux systèmes du banc annoncent le même identifiant système et le même mandant.
    Open WebGui Data Browser    ${url}
    Display WebGui Table Contents    ${WEBGUI_MESSAGE_TABLE}    ${WEBGUI_MAX_HITS}
    ${extrait}=    Extract Displayed WebGui Grid
    ...    key=${WEBGUI_MESSAGE_LANGUAGE_COLUMN}
    ...    source=${WEBGUI_MESSAGE_TABLE} via WebGUI (${nom})
    ${resume}=    Describe Table Extract    ${extrait}
    Log    ${resume}
    Table Extract Should Be Complete    ${extrait}    min_rows=${100}    min_columns=${4}
    # L'ADRESSE atteinte entre dans le nom du fichier, dans son sous-titre et
    # dans le registre, et ce n'est pas cosmétique : sur ce canal l'identité
    # ne distingue PAS les deux systèmes (même identifiant, même mandant), donc
    # une étiquette de cible mal pointée produirait un fichier nommé « 2023 »
    # portant les données de l'autre système, sous un sous-titre qui dirait la
    # même chose que lui. Le seul discriminant doit voyager AVEC la donnée.
    ${hote}=    Evaluate    "${atteinte}[host]".replace(":", "-")
    ${bilan}=    Exporter Le Releve Vers Les Cinq Formats    ${extrait}
    ...    ${OUTPUT_PREFIX}_${nom}_${hote}_${WEBGUI_MESSAGE_TABLE}    sheet_name=WebGUI grid
    ...    csv_delimiter=${CSV_DELIMITER}    max_rows=${MAX_ROWS}
    ...    subtitle=${identite}[system_id] mandant ${identite}[client] sur ${atteinte}[host], table ${WEBGUI_MESSAGE_TABLE} (WebGUI, connexion ${strategie})
    Consigner La Cible    ${nom}    WebGUI    ${identite}[system_id]
    ...    ${identite}[client]    ${atteinte}[host] (connexion ${strategie})
    ...    ${extrait}    ${bilan}

Fermer Le Canal Webgui
    [Documentation]    Ferme le navigateur de CETTE cible, même après un échec,
    ...    et déconnecte la session GUI serveur au passage : chaque navigation
    ...    `~transaction` en ouvre une nouvelle.
    Run Keyword And Ignore Error    Close WebGui

Fermer Le Canal Ui5
    Run Keyword And Ignore Error    Fermer Le Parcours Voyages

Consigner La Cible
    [Documentation]    Inscrit ce qu'une cible a RÉELLEMENT produit dans le
    ...    registre de campagne. Les valeurs consignées sont mesurées, jamais
    ...    déduites de la réussite du scénario.
    [Arguments]    ${cle}    ${canal}    ${systeme}    ${client}    ${detail}
    ...    ${extrait}    ${bilan}
    ${entree}=    Create Dictionary    channel=${canal}    system=${systeme}
    ...    client=${client}    reached=${detail}    source=${extrait}[source]
    ...    rows=${extrait}[row_count]    declared_rows=${extrait}[declared_rows]
    ...    columns=${{ len($extrait['columns']) }}    complete=${extrait}[complete]
    ...    formats=${{ sorted($bilan['formats']) }}
    Set To Dictionary    ${REGISTRE}    ${cle}=${entree}
    Log    Cible ${cle} consignée : ${entree}
