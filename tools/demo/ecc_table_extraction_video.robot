*** Settings ***
Documentation       **Démo scénarisée, ENREGISTRÉE EN VIDÉO, de l'extraction
...                 d'une très grande table SAP par le canal SAP GUI**, avec
...                 commentaire anglais en voix off et sous-titres incrustés.
...
...                 Ce que le film montre, dans l'ordre : le Data Browser ouvert
...                 sur `DD03L` (le catalogue de champs du dictionnaire ABAP,
...                 1,8 million de lignes sur la cible), le total DEMANDÉ à la
...                 base avant toute lecture, la sélection bornée par le plafond
...                 de hits de SAP, la grille ALV défilée pour matérialiser ses
...                 lignes, le relevé confronté à ce que la grille DÉCLARE, puis
...                 l'écriture dans les cinq formats, le dossier de destination
...                 et trois des fichiers réellement ouverts.
...
...                 **Trois partis pris de prise de vue**, chacun documenté dans
...                 `tools/demo/narration.py` : une seule capture continue d'une
...                 RÉGION fixe de l'écran (et non une capture par fenêtre, qui
...                 obligerait à recoller cinq segments), un fond opaque derrière
...                 tout (une région montre ce qui s'y trouve, donc le bureau du
...                 poste dès qu'une fenêtre ne la couvre pas entièrement), et
...                 une voix SYNTHÉTISÉE AVANT la prise, mixée en post depuis les
...                 mêmes horodatages que les sous-titres.
...
...                 **Les chiffres dits par la voix sont ASSERTÉS ici.** Le
...                 commentaire est écrit à l'avance, donc il annonce des
...                 résultats ; la suite refuse de filmer si la cible ne les
...                 produit pas. Un commentaire ne doit pas pouvoir décrire une
...                 mesure qui n'a pas eu lieu.
...
...                 Prérequis : système SAP joignable, scripting activé, ffmpeg,
...                 et une voix anglaise installée (Windows en livre une).
...                 Lancer, depuis la racine du dépôt :
...                 | robot --pythonpath src -v SAP_CONNECTION:/H/vhcala4hci/S/3200
...                 | ...   -v SAP_USER:DEVELOPER -v "SAP_PASSWORD: Secret:<mdp>"
...                 | ...   -v SAP_CLIENT:001 tools/demo/ecc_table_extraction_video.robot
...
...                 NB : la prise filme des applications de BUREAU, elle ne peut
...                 donc pas être headless. Ne rien toucher pendant les quelques
...                 minutes d'enregistrement.

Library             ${EXECDIR}/tools/demo/narration.py    WITH NAME    Shot
Library             Collections
Library             OperatingSystem
Library             Process
Library             sapfx_common.robot_args
Library             sapfx_common.table_extract
Variables           ${EXECDIR}/tools/demo/extraction_script.py
Resource            ${EXECDIR}/resources/ecc_keywords.resource
Resource            ${EXECDIR}/resources/table_export_keywords.resource

Suite Setup         Preparer La Prise
Suite Teardown      Lever Le Plateau


*** Variables ***
# --- La cible et ce qu'on en attend. Les valeurs attendues sont celles que la
# VOIX annonce : les asserter est la seule façon d'empêcher un commentaire de
# décrire une mesure qui n'a pas eu lieu.
${TABLE}                DD03L
${HITS}                 5000
${EXPECTED_TOTAL}       ${1819533}
${EXPECTED_ROWS}        ${5000}
${EXPECTED_COLUMNS}     ${31}
${EXPECTED_RELEASE}     754

# --- Les localisateurs bruts du Data Browser. Ils vivent ici et non dans
# `resources/` parce que ceci est une DÉMO, pas un test : le fichier est
# autonome, et la convention 1 vise les suites de test.
${SE16_COUNT_BUTTON}    wnd[0]/tbar[1]/btn[31]
${SE16_COUNT_FIELD}     wnd[1]/usr/txtG_DBCOUNT

# --- La prise. La région filmée est un rectangle FIXE : chaque application est
# posée dedans à son tour.
${REGION_X}             ${160}
${REGION_Y}             ${90}
${REGION_W}             ${1600}
${REGION_H}             ${900}
${FFMPEG}               ffmpeg

${OUT}                  ${EXECDIR}/dist/demo-extraction
${VIDEO}                ${EXECDIR}/dist/video
${RAW}                  ${VIDEO}/extraction_capture.mkv
${SRT}                  ${VIDEO}/extraction_capture.srt
${FINAL}                ${VIDEO}/sapfx-ecc-table-extraction.mp4
${WAVS}                 ${VIDEO}/narration

# Posées à l'exécution ; déclarées pour l'analyse statique.
${T0}                   ${0}
${OFFSET}               ${0}
${CAPTURE}              ${NONE}
${BACKDROP}             ${NONE}
# Le profil jetable du navigateur. Il porte sa valeur DÈS LE DÉPART et jamais
# une chaîne vide, et c'est une précaution SÉRIEUSE, pas une élégance.
#
# Mesuré le 2026-09-17 dans un arbre jetable : `Remove Directory` résout un
# chemin vide par `_absnorm("")`, c'est-à-dire le RÉPERTOIRE COURANT, et avec
# `recursive=True` il en supprime TOUT le contenu, ne butant qu'à la fin sur le
# dossier courant lui-même, qu'un processus ne peut pas retirer sous ses pieds.
# Un scénario qui échoue avant d'ouvrir le navigateur visait donc la racine du
# dépôt depuis lequel la démo est lancée.
#
# Le même jour, dans ce dépôt, la perte s'est limitée à `.claude/` parce que le
# parcours a buté aussitôt après sur un fichier verrouillé par un éditeur
# ouvert : shutil.rmtree lève à la PREMIÈRE erreur et abandonne le reste. Rien
# dans le code ne garantissait cet arrêt, et il ne faut pas compter dessus.
${CHROME_PROFILE}       ${EXECDIR}/dist/video/chrome-profile
${SYSTEME}              ${EMPTY}
${MANDANT}              ${EMPTY}
@{CUES}                 @{EMPTY}
&{DUREES}               &{EMPTY}
&{TEXTES}               &{EMPTY}


*** Test Cases ***
Filmer L Extraction D Une Tres Grande Table
    [Documentation]    Le scénario, de bout en bout. Un seul cas de test : c'est
    ...    une prise de vue continue, elle ne se découpe pas.

    # --- 1. Le système, et ce qu'on vient y faire ------------------------
    Speak    c01
    Speak    c02

    # --- 2. Le Data Browser sur la table -------------------------------
    ${fin}=    Cue    c03
    Taper Le Code Transaction    /nSE16
    Sleep    1.2s
    Send Vkey    0
    Wait Until Busy Done
    Sleep    1s
    Open Table Selection Screen    ${TABLE}
    Wait Until Element Present    ${SE16_MAX_HITS_FIELD}    timeout=60s
    Sleep Until    ${fin}

    # --- 3. Le total DEMANDÉ à la base, avant toute lecture -------------
    Click Element    ${SE16_COUNT_BUTTON}
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_COUNT_FIELD}    timeout=60s
    ${brut}=     Get Value    ${SE16_COUNT_FIELD}
    ${total}=    Displayed Count    ${brut}
    Should Be Equal As Integers    ${total}    ${EXPECTED_TOTAL}
    ...    msg=La voix annonce ${EXPECTED_TOTAL} lignes et la cible en compte ${total}. La prise est arrêtée : un commentaire ne doit pas annoncer une mesure que le système n'a pas produite.
    Speak    c04
    Send Vkey    12    window=1
    Wait Until Busy Done

    # --- 4. La sélection bornée par le plafond de hits ------------------
    ${fin}=    Cue    c05
    Input Text    ${SE16_MAX_HITS_FIELD}    ${HITS}
    Sleep Until    ${fin}
    Send Vkey    8
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_GRID}    timeout=180s

    ${colonnes}=    Get Grid Column Ids       ${SE16_GRID}
    ${titres}=      Get Grid Column Titles    ${SE16_GRID}
    ${declarees}=   Get Row Count             ${SE16_GRID}
    ${nb_col}=      Get Length                ${colonnes}
    Should Be Equal As Integers    ${declarees}      ${EXPECTED_ROWS}
    Should Be Equal As Integers    ${nb_col}         ${EXPECTED_COLUMNS}
    ...    msg=La voix annonce ${EXPECTED_COLUMNS} colonnes et la grille en porte ${nb_col}.

    # --- 5. Le piège du rendu différé, dit pendant qu'on le voit --------
    Speak    c06
    Speak    c07
    Speak    c08

    # --- 6. La lecture : défilement forcé puis 155 000 appels -----------
    # Les répliques sont POSÉES dans la fenêtre de temps de la lecture, et non
    # dites en la bloquant : la voix est mixée en post depuis ses horodatages,
    # donc elle n'a pas à être prononcée pendant que le keyword travaille.
    ${debut}=    Shot.Clock
    ${debut}=    Evaluate    ${debut} - ${T0}
    ${lignes}=    Read Full Grid    ${SE16_GRID}    columns=${colonnes}
    ...    max_rows=${declarees}
    ${fin_lecture}=    Shot.Clock
    ${fin_lecture}=    Evaluate    ${fin_lecture} - ${T0}
    ${duree}=    Evaluate    round(${fin_lecture} - ${debut}, 1)
    Log To Console    \n>>> lecture : ${duree}s
    ${fin}=    Poser La Replique    c09    ${{ $debut + 2 }}
    ${fin}=    Poser La Replique    c10    ${{ $fin + 1 }}
    ${fin}=    Poser La Replique    c11    ${{ $fin + 1 }}
    Sleep Until    ${fin}

    # --- 7. Le relevé confronté à son contrat --------------------------
    ${extrait}=    Build Table Extract    ${lignes}    columns=${colonnes}
    ...    headers=${titres}    declared_rows=${declarees}    source=${TABLE}
    ...    key=${colonnes}[0]
    ${resume}=    Describe Table Extract    ${extrait}
    Log To Console    >>> ${resume}
    Table Extract Should Be Complete    ${extrait}    min_rows=${1000}
    ...    min_columns=${10}
    Should Be Equal As Integers    ${extrait}[blank_rows]    ${0}
    Should Be Equal As Integers    ${extrait}[row_count]     ${EXPECTED_ROWS}
    Speak    c12
    Speak    c13

    # --- 8. Les cinq formats -------------------------------------------
    ${fin}=    Cue    c14
    ${marque}=    Set Variable    ${OUT}/${TABLE}_${SYSTEME}_${MANDANT}
    ${bilan}=    Exporter Le Releve Vers Les Cinq Formats    ${extrait}
    ...    ${marque}    sheet_name=${TABLE}
    ...    subtitle=${SYSTEME} client ${MANDANT} SAP_BASIS ${EXPECTED_RELEASE} (SE16, first ${HITS} rows)
    Length Should Be    ${bilan}[formats]    ${5}
    ...    msg=Les cinq formats sont annoncés par la voix : ${bilan}[formats] ont été écrits.
    Sleep Until    ${fin}
    Speak    c15

    # --- 9. Le dossier de destination ----------------------------------
    # `Normalize Path` et non une substitution maison : l'explorateur n'ouvre
    # pas un chemin à séparateurs mixtes, il ouvre alors le dossier Documents.
    ${dossier}=    Normalize Path    ${OUT}
    Start Process    explorer.exe    ${dossier}
    Shot.Place Window    demo-extraction    ${REGION_X}    ${REGION_Y}
    ...    ${REGION_W}    ${REGION_H}
    # Affichage détaillé : c'est lui qui montre la TAILLE de chaque fichier,
    # et c'est tout l'intérêt du plan.
    Shot.Send Keys    ^+{6}
    Sleep    1s
    Speak    c16
    Speak    c17

    # --- 10. Le CSV brut ------------------------------------------------
    Start Process    notepad.exe    ${bilan}[fichiers][csv]
    Shot.Place Window    ${TABLE}_${SYSTEME}_${MANDANT}.csv    ${REGION_X}
    ...    ${REGION_Y}    ${REGION_W}    ${REGION_H}
    Speak    c18

    # --- 11. Le classeur, jusqu'à sa dernière cellule --------------------
    ${excel}=    Shot.Resolve App    excel.exe
    Start Process    ${excel}    ${bilan}[fichiers][xlsx]
    Shot.Place Window    ${TABLE}_${SYSTEME}_${MANDANT}.xlsx    ${REGION_X}
    ...    ${REGION_Y}    ${REGION_W}    ${REGION_H}    timeout=90
    Sleep    3s
    ${fin}=    Cue    c19
    Shot.Send Keys    ^{END}
    Sleep Until    ${fin}

    # --- 12. Le document vectoriel dans un navigateur -------------------
    Ouvrir Le Svg Dans Un Navigateur Neutre    ${bilan}[fichiers][svg]
    Speak    c20

    # --- 13. La morale --------------------------------------------------
    Speak    c21

    Arreter La Capture
    Monter Le Film


*** Keywords ***
Preparer La Prise
    [Documentation]    Tout ce qui doit être fait AVANT que la caméra tourne :
    ...    la voix, le fond, la session SAP et le cadrage.
    Create Directory    ${OUT}
    Create Directory    ${VIDEO}
    Empty Directory     ${OUT}
    ${durees}=    Shot.Synthesize Narration    ${SCRIPT}    ${WAVS}
    Set Suite Variable    ${DUREES}    ${durees}
    ${cues}=    Create List
    Set Suite Variable    ${CUES}    ${cues}
    ${textes}=    Create Dictionary
    FOR    ${replique}    IN    @{SCRIPT}
        Set To Dictionary    ${textes}    ${replique}[id]    ${replique}[text]
    END
    Set Suite Variable    ${TEXTES}    ${textes}

    # Le fond d'abord : il doit être en place avant la première fenêtre filmée.
    ${backdrop}=    Start Process    pythonw    ${EXECDIR}/tools/demo/backdrop.py
    Set Suite Variable    ${BACKDROP}    ${backdrop}
    Sleep    1.5s

    Open SAP And Log In
    ${identite}=    Get System Identity
    Should Be Equal    ${identite}[anchor][basis_release]    ${EXPECTED_RELEASE}
    ...    msg=Cible REFUSÉE : la session vise la release ${identite}[anchor][basis_release] et le commentaire annonce ${EXPECTED_RELEASE}. Les deux conteneurs du poste partagent nom d'hôte et identifiant système, donc filmer sans cette garde donnerait une vidéo nette du mauvais système.
    Set Suite Variable    ${SYSTEME}    ${identite}[system_id]
    Set Suite Variable    ${MANDANT}    ${identite}[client]
    # La sortie SE16 en grille ALV est un PRÉREQUIS de lecture, pas une étape du
    # récit : on la pose hors caméra.
    Use ALV Grid In Data Browser
    Run Transaction    /n
    Wait Until Busy Done

    Cadrer La Fenetre Sap
    Demarrer La Capture

Cadrer La Fenetre Sap
    [Documentation]    Pose la fenêtre SAP dans le rectangle filmé.
    ...
    ...    Le titre de l'écran d'accueil dépend de la langue de connexion, donc
    ...    il ne peut pas être la SEULE ancre : le repli vise le numéro de
    ...    session, que SAP GUI met dans le titre de toute fenêtre de session
    ...    quelle que soit la langue. Échouer ici filmerait le fond.
    ${cadre}=    Run Keyword And Ignore Error    Shot.Place Window
    ...    SAP Easy Access    ${REGION_X}    ${REGION_Y}    ${REGION_W}    ${REGION_H}
    ...    timeout=8
    IF    '${cadre}[0]' != 'PASS'
        Shot.Place Window    (1)    ${REGION_X}    ${REGION_Y}
        ...    ${REGION_W}    ${REGION_H}
    END

Demarrer La Capture
    [Documentation]    Une seule prise, d'une région fixe. Matroska : conteneur
    ...    tolérant à un arrêt brutal, la durée du scénario n'étant pas connue
    ...    d'avance.
    Remove File    ${RAW}
    ${proc}=    Start Process    ${FFMPEG}    -y    -hide_banner    -loglevel    error
    ...    -f    gdigrab    -framerate    15
    ...    -offset_x    ${REGION_X}    -offset_y    ${REGION_Y}
    ...    -video_size    ${REGION_W}x${REGION_H}    -i    desktop
    ...    -c:v    libx264    -preset    ultrafast    -crf    18    -pix_fmt    yuv420p
    ...    ${RAW}
    Set Suite Variable    ${CAPTURE}    ${proc}
    Sleep    2.5s          # laisse gdigrab s'amorcer
    ${t0}=    Shot.Clock
    Set Suite Variable    ${T0}    ${t0}

Arreter La Capture
    [Documentation]    Coupe la prise et MESURE le décalage entre la piste de
    ...    répliques et le film : la capture démarre avant l'origine du
    ...    scénario, donc sans recalage la voix devance l'image.
    Sleep    1.5s
    ${ecoule}=    Shot.Clock
    ${ecoule}=    Evaluate    ${ecoule} - ${T0}
    Terminate Process    ${CAPTURE}
    Set Suite Variable    ${CAPTURE}    ${NONE}
    Sleep    2s
    File Should Exist    ${RAW}
    ${duree}=    Shot.Probe Duration    ${FFMPEG}    ${RAW}
    ${offset}=    Evaluate    max(0.0, ${duree} - ${ecoule})
    Set Suite Variable    ${OFFSET}    ${offset}
    ${ligne}=    Catenate    film ${duree}s / scénario ${ecoule}s
    ...    (décalage ${offset}s)
    Log To Console    \n>>> ${ligne}

Sauver La Prise
    [Documentation]    Coupe et monte, si la prise tourne encore. Sans effet
    ...    quand le scénario est allé au bout : il a déjà fait les deux.
    IF    $CAPTURE is not None
        Arreter La Capture
        Monter Le Film
    END

Monter Le Film
    ${recalees}=    Shot.Shift Cues    ${CUES}    ${OFFSET}
    Shot.Build Srt    ${recalees}    ${SRT}
    ${octets}=    Shot.Assemble Video    ${FFMPEG}    ${RAW}    ${SRT}
    ...    ${recalees}    ${WAVS}    ${FINAL}
    ${mo}=    Evaluate    round(${octets} / 1048576, 2)
    Log To Console    \n>>> MP4 : ${FINAL} (${mo} Mo)

Lever Le Plateau
    [Documentation]    Referme tout, même après un échec : une prise
    ...    interrompue ne doit pas laisser une capture en cours, un fond plein
    ...    écran sans décoration ni une session SAP ouverte.
    ...
    ...    Le film est monté ICI quand le scénario a échoué APRÈS le début de
    ...    la prise : une capture de plusieurs minutes contre un système réel
    ...    est trop coûteuse pour être jetée à cause de la dernière étape, et
    ...    ce qui a été filmé avant l'échec reste exploitable.
    Run Keyword And Ignore Error    Sauver La Prise
    # Les motifs sont VOLONTAIREMENT étroits : « Google Chrome » seul
    # fermerait aussi les fenêtres de navigation de la personne qui utilise le
    # poste. On ne ferme que ce que la démo a ouvert.
    Run Keyword And Ignore Error    Shot.Close Windows    ${TABLE}_
    ...    demo-extraction    ${TABLE} - Google Chrome
    Run Keyword And Ignore Error    Close SAP
    Run Keyword And Ignore Error    Terminate Process    ${BACKDROP}
    # La garde est DÉLIBÉRÉE et redondante avec le défaut non vide déclaré plus
    # haut : une suppression récursive ne doit jamais dépendre d'une seule
    # précaution, et celle-ci nomme ce qu'elle refuse.
    IF    '${CHROME_PROFILE}' == '${EMPTY}'
        Fail    Suppression REFUSÉE : le profil jetable n'a pas de chemin, et un chemin vide désigne le répertoire courant.
    ELSE
        Run Keyword And Ignore Error    Remove Directory    ${CHROME_PROFILE}
        ...    recursive=True
    END

# --- Le moteur de répliques ---------------------------------------------
# Une réplique est enregistrée avec son horodatage, jamais prononcée pendant la
# prise : la voix est mixée en post depuis ces mêmes horodatages, donc le son et
# les sous-titres ne peuvent pas diverger.

Ecoule
    ${maintenant}=    Shot.Clock
    ${t}=    Evaluate    ${maintenant} - ${T0}
    RETURN    ${t}

Cue
    [Documentation]    Enregistre une réplique à l'instant courant et rend
    ...    l'instant où elle finit de se dire.
    [Arguments]    ${id}
    ${t}=    Ecoule
    ${fin}=    Poser La Replique    ${id}    ${t}
    RETURN    ${fin}

Poser La Replique
    [Documentation]    Enregistre une réplique à un instant DONNÉ, pour couvrir
    ...    de la voix une opération longue sans avoir à l'interrompre.
    [Arguments]    ${id}    ${t}
    ${duree}=    Get From Dictionary    ${DUREES}    ${id}
    ${texte}=    Get From Dictionary    ${TEXTES}    ${id}
    ${replique}=    Create Dictionary    id=${id}    t=${t}    duration=${duree}
    ...    text=${texte}
    Append To List    ${CUES}    ${replique}
    Log To Console    >>> [${{ round($t, 1) }}] ${texte}
    RETURN    ${{ $t + $duree }}

Speak
    [Documentation]    Dit une réplique et laisse le spectateur l'entendre.
    [Arguments]    ${id}    ${pad}=${0.7}
    ${fin}=    Cue    ${id}
    Sleep Until    ${{ $fin + $pad }}

Sleep Until
    [Arguments]    ${cible}
    ${maintenant}=    Ecoule
    ${attente}=    Evaluate    max(0.0, ${cible} - ${maintenant})
    Sleep    ${attente}

# --- Gestes de plateau ---------------------------------------------------

Taper Le Code Transaction
    [Documentation]    `Input Text` refuse un GuiOkCodeField : on pose le champ
    ...    comme `Run Transaction` le fait en interne, pour que le spectateur
    ...    VOIE le code s'inscrire avant la validation.
    [Arguments]    ${code}
    ${lib}=    Get Library Instance    SapEccLibrary
    Evaluate    setattr($lib.session.findById("wnd[0]/tbar[0]/okcd"), "text", "${code}")

Ouvrir Le Svg Dans Un Navigateur Neutre
    [Documentation]    Ouvre le document dans un profil de navigateur JETABLE.
    ...
    ...    Le profil par défaut porte les favoris, l'avatar et les bandeaux
    ...    promotionnels de la personne qui utilise le poste : autant de choses
    ...    qui n'ont rien à faire dans une vidéo, et qu'un profil neuf ne
    ...    contient pas. Le titre de la fenêtre vient du `<title>` du SVG, donc
    ...    du nom de la table.
    [Arguments]    ${chemin}
    ${profil}=    Set Variable    ${VIDEO}/chrome-profile
    Set Suite Variable    ${CHROME_PROFILE}    ${profil}
    ${url}=      Shot.File Url    ${chemin}
    ${chrome}=   Shot.Resolve App    chrome.exe
    Start Process    ${chrome}    --new-window    --no-first-run
    ...    --no-default-browser-check    --disable-features\=Translate
    ...    --user-data-dir\=${profil}    ${url}
    Shot.Place Window    ${TABLE} - Google Chrome    ${REGION_X}    ${REGION_Y}
    ...    ${REGION_W}    ${REGION_H}    timeout=60
    Sleep    3s
