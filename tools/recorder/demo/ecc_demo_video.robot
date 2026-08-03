*** Settings ***
Documentation       Démo scénarisée du **recorder ECC (SAP GUI)** contre un vrai système
...                 A4H, ENREGISTRÉE EN VIDÉO. Contrairement au canal web, il n'y a pas
...                 de panneau dans la page : on capture LA FENÊTRE SAP GUI (et elle
...                 seule — aucune fuite de bureau) avec ffmpeg `gdigrab`, et les
...                 sous-titres incrustés portent les steps RÉELLEMENT émis par le
...                 moteur record, horodatés à l'exécution.
...
...                 Prérequis : système SAP joignable + scripting activé + ffmpeg.
...                 Lancer :
...                   robot --pythonpath src ^
...                     -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER ^
...                     -v "SAP_PASSWORD: Secret:<motdepasse>" -v SAP_CLIENT:001 ^
...                     tools/recorder/demo/ecc_demo_video.robot
...                 Sortie : dist/video/sapfx-ecc-recorder-demo.mp4
...
...                 NB : la prise filme une application de BUREAU — contrairement au
...                 canal web, elle ne peut pas être headless. Ne pas toucher
...                 souris/clavier pendant l'enregistrement, et ne rien poser
...                 par-dessus la fenêtre SAP.

Library             ${EXECDIR}/tools/recorder/sapgui_recorder.py    WITH NAME    Recorder
Library             OperatingSystem
Library             Collections
Library             Process
Library             String
Resource            ${EXECDIR}/resources/ecc_keywords.resource

Suite Setup         Open SAP And Log In
Suite Teardown      Close SAP


*** Variables ***
${OUT}          ${EXECDIR}/dist/video
${RAW}          ${OUT}/ecc_capture.mkv
${SRT}          ${OUT}/ecc_capture.srt
${FINAL}        sapfx-ecc-recorder-demo.mp4
# posées à l'exécution — déclarées ici pour l'analyse statique
${T0}           ${0}
${OFFSET}       ${0}
${FFMPEG}       ${EMPTY}
${WIN_TITLE}    ${EMPTY}


*** Test Cases ***
Record The ECC Demo Video
    Create Directory    ${OUT}
    ${cues}=    Create List
    Set Suite Variable    ${CUES}    ${cues}
    ${engine}=     Recorder.Get Scripting Engine
    ${session}=    Recorder.First Session    ${engine}
    Set Suite Variable    ${SESSION}    ${session}

    Prepare Sap Window
    ${proc}=    Start Capture
    ${state}=    Create Dictionary
    ${state}    ${ignored}=    Poll Recorder    ${state}    # référence : écran d'accueil

    Beat    SAP GUI (ECC) — enregistreur de tests    Robot Framework · système SAP réel    3.5

    Beat    1. Le recorder observe la session    Par l'API de scripting SAP GUI — aucun clic intercepté    3

    # --- geste 1 : lancer une transaction, comme un utilisateur ---
    Beat    2. On pilote SAP normalement    L'OK-code est saisi, puis validé    1
    Type Okcode    /nSE16
    Sleep    1.4s
    ${state}    ${ignored}=    Poll Recorder    ${state}          # capte l'OK-code AVANT l'Entrée
    Send Vkey    0
    Wait Until Busy Done
    ${state}    ${steps}=    Poll Recorder    ${state}            # frontière -> émission
    Beat    3. Chaque geste devient un keyword    ${{chr(10).join($steps)}}    3.5

    # --- geste 2 : saisir la table, valider ---
    Input Text    ${SE16_TABLE_FIELD}    T000
    Sleep    1.2s
    ${state}    ${ignored}=    Poll Recorder    ${state}
    Send Vkey    0
    Wait Until Busy Done
    ${state}    ${steps}=    Poll Recorder    ${state}
    Beat    4. L'id technique est relevé, pas deviné    ${{chr(10).join($steps)}}    4
    ${snapshot}=    Copy List    ${RECORDED}
    Set Suite Variable    @{ALL_STEPS}    @{snapshot}

    # --- effet métier observable : le comptage ---
    Beat    5. Un vrai parcours métier    « Number of Entries » sur la table T000    1.5
    Click Element    wnd[0]/tbar[1]/btn[31]
    Wait Until Busy Done
    ${count}=    Get Value    wnd[1]/usr/txtG_DBCOUNT
    Beat    5. Le système répond    T000 contient ${count} entrées    3
    Send Vkey    12    window=1
    Wait Until Busy Done

    # --- exports ---
    Write Recording And Exports
    ${suite}=    Get File    ${OUT}/ecc_recorded_resource_first.robot
    ${res}=      Get File    ${OUT}/ecc_recorded_keywords.resource
    # On n'incruste QUE les lignes qui portent le message : un fichier entier
    # déborde du bandeau et recouvre l'écran SAP (constaté à l'image).
    ${suite_body}=    Extract Section    ${suite}    *** Test Cases ***    4
    ${res_body}=      Extract Section    ${res}      *** Keywords ***      4
    Beat    6. Export resource-first    Les localisateurs quittent le test…    4.5    ${suite_body}
    Beat    6. …et vivent dans la couche resources    C'est la couche que sap-healer répare    4.5    ${res_body}

    # --- replay : SAP rebouge tout seul ---
    Run Transaction    /n
    Wait Until Busy Done
    Beat    7. Replay contre la session ouverte    Le déroulé est rejoué — SAP repart de zéro    2.5
    ${lib}=    Get Library Instance    SapEccLibrary
    ${executed}    ${skipped}    ${failed}    ${msg}=
    ...    Recorder.Replay Recorded Steps    ${ALL_STEPS}    ${lib}
    Should Be Equal    ${failed}    ${None}    le replay doit passer : ${msg}
    ${title}=    Get Value    wnd[0]/titl
    Beat    7. Replay OK    ${executed} steps rejoués — écran d'arrivée : ${title}    4

    Beat    ECC · Fiori · WebGUI · API    Un enregistrement, un test qui parle métier    4

    Stop Capture    ${proc}
    Write Srt
    Burn Subtitles


*** Keywords ***
Prepare Sap Window
    [Documentation]    Fenêtre SAP GUI au premier plan et à taille maîtrisée : gdigrab
    ...                lie le HWND une fois, mais capture le contenu — une fenêtre
    ...                recouverte donnerait une image polluée.
    ${title}=    Evaluate    __import__("win32gui").GetWindowText(__import__("win32gui").GetForegroundWindow())
    Set Suite Variable    ${WIN_TITLE}    ${title}
    ${hwnd}=    Evaluate    __import__("win32gui").FindWindow(None, r"${title}")
    Evaluate    __import__("win32gui").MoveWindow($hwnd, 40, 40, 1280, 800, True)
    Evaluate    __import__("win32gui").SetForegroundWindow($hwnd)
    Sleep    1s

Start Capture
    ${ffmpeg}=    Resolve Ffmpeg
    Should Not Be Empty    ${ffmpeg}    ffmpeg est requis pour la prise
    Set Suite Variable    ${FFMPEG}    ${ffmpeg}
    Remove File    ${RAW}
    # Matroska : conteneur tolérant à un arrêt brutal (on coupe la capture à la fin
    # du scénario, dont on ne connaît pas la durée d'avance).
    # `title\=` échappé : sinon Robot le lit comme un argument NOMMÉ.
    ${proc}=    Start Process    ${FFMPEG}    -y    -hide_banner    -loglevel    error
    ...    -f    gdigrab    -framerate    15    -i    title\=${WIN_TITLE}
    ...    -c:v    libx264    -preset    ultrafast    -crf    18    -pix_fmt    yuv420p
    ...    ${RAW}
    Sleep    2s                     # laisse la capture s'amorcer
    ${t0}=    Evaluate    __import__("time").time()
    Set Suite Variable    ${T0}    ${t0}
    ${rec}=    Create List
    Set Suite Variable    ${RECORDED}    ${rec}
    RETURN    ${proc}

Stop Capture
    [Documentation]    Coupe la capture ET mesure le décalage entre la piste de
    ...                sous-titres et le film.
    ...
    ...                La capture démarre AVANT l'origine des répliques (amorçage de
    ...                gdigrab + temporisation), si bien que le film est plus long que
    ...                le scénario : sans correction les sous-titres devancent l'image
    ...                d'environ 3 s (constaté en relevant les titres d'écran image par
    ...                image). On mesure l'écart au lieu de le supposer.
    [Arguments]    ${proc}
    Sleep    1s
    ${elapsed}=    Evaluate    __import__("time").time() - ${T0}
    Terminate Process    ${proc}
    Sleep    2s
    File Should Exist    ${RAW}
    ${size}=    Get File Size    ${RAW}
    ${ffprobe}=    Evaluate    r"${FFMPEG}".replace("ffmpeg", "ffprobe")
    ${probe}=    Run Process    ${ffprobe}    -v    error
    ...    -show_entries    format\=duration    -of    csv\=p\=0    ${RAW}
    ${duration}=    Convert To Number    ${probe.stdout.strip()}
    ${offset}=    Evaluate    max(0.0, ${duration} - ${elapsed})
    Set Suite Variable    ${OFFSET}    ${offset}
    # une seule cellule : la 2e serait lue comme l'argument `stream` de Log To Console
    ${line}=    Catenate    capture ${size} o — film ${duration}s / scénario ${elapsed}s
    ...    — décalage sous-titres ${offset}s
    Log To Console    \n>>> ${line}

Beat
    [Documentation]    Un temps du scénario : horodate la réplique (titre + détail, plus
    ...                un bloc optionnel) et laisse le spectateur lire.
    [Arguments]    ${title}    ${detail}    ${seconds}    ${block}=${EMPTY}
    ${t}=    Evaluate    __import__("time").time() - ${T0}
    ${cue}=    Create Dictionary    t=${t}    title=${title}    detail=${detail}    block=${block}
    Append To List    ${CUES}    ${cue}
    Log To Console    \n>>> [${t}] ${title} — ${detail}
    Sleep    ${seconds}

Poll Recorder
    [Arguments]    ${state}
    ${sig}=     Recorder.Screen Signature    ${SESSION}
    ${snap}=    Recorder.Snapshot Fields    ${SESSION}
    ${okcd}=    Recorder.Okcode Value    ${SESSION}
    ${new}    ${steps}=    Recorder.Process Poll    ${state}    ${sig}    ${snap}    ${okcd}
    FOR    ${s}    IN    @{steps}
        Append To List    ${RECORDED}    ${s}
    END
    RETURN    ${new}    ${steps}

Type Okcode
    [Documentation]    `Input Text` refuse un GuiOkCodeField : on pose le champ comme
    ...                le fait `Run Transaction` en interne.
    [Arguments]    ${code}
    Evaluate    setattr($SESSION.findById("wnd[0]/tbar[0]/okcd"), "text", "${code}")

Write Recording And Exports
    ${header}=    Recorder.Build Record Header    ${OUT}/ecc_recorded.robot    suite=${True}
    ${body}=    Set Variable    ${EMPTY}
    FOR    ${s}    IN    @{RECORDED}
        ${body}=    Catenate    SEPARATOR=    ${body}    ${SPACE*4}${s}\n
    END
    Create File    ${OUT}/ecc_recorded.robot    ${header}${body}
    Recorder.Run Record Exports    ${OUT}/ecc_recorded.robot
    ...    export_resources=${True}    export_spec=${True}

Write Srt
    [Documentation]    Construit le SRT depuis les répliques horodatées : chaque
    ...                réplique dure jusqu'à la suivante.
    ${n}=    Get Length    ${CUES}
    # `${srt_text}` et non `${srt}` : les noms de variables Robot sont insensibles à
    # la casse, donc `${srt}` ÉCRASERAIT `${SRT}` (le chemin du fichier).
    ${srt_text}=    Set Variable    ${EMPTY}
    FOR    ${i}    IN RANGE    ${n}
        ${cue}=    Get From List    ${CUES}    ${i}
        # + ${OFFSET} : recale la piste sur le film (mesuré par Stop Capture).
        ${start}=    Evaluate    ${cue}[t] + ${OFFSET}
        ${next}=    Evaluate    ${i} + 1
        IF    ${next} < ${n}
            ${nc}=    Get From List    ${CUES}    ${next}
            ${end}=    Evaluate    ${nc}[t] + ${OFFSET}
        ELSE
            ${end}=    Evaluate    ${start} + 4
        END
        ${a}=    Format Timestamp    ${start}
        ${b}=    Format Timestamp    ${end}
        ${idx}=    Evaluate    ${i} + 1
        ${text}=    Catenate    SEPARATOR=    ${cue}[title]\n${cue}[detail]
        # test sur la VALEUR (pas sur une chaîne interpolée) : un bloc contenant des
        # guillemets casserait la comparaison textuelle.
        IF    $cue['block']
            ${text}=    Catenate    SEPARATOR=\n    ${text}    ${cue}[block]
        END
        ${srt_text}=    Catenate    SEPARATOR=    ${srt_text}    ${idx}\n${a} --> ${b}\n${text}\n\n
    END
    Create File    ${SRT}    ${srt_text}
    Log To Console    \n>>> SRT : ${SRT}

Extract Section
    [Documentation]    Les ``${max}`` premières lignes non vides qui SUIVENT un marqueur
    ...                de section — de quoi incruster l'essentiel d'un artefact sans
    ...                déborder du bandeau.
    [Arguments]    ${text}    ${marker}    ${max}
    ${lines}=    Evaluate    [l.rstrip() for l in $text.splitlines()]
    # Recherche du marqueur en Robot : une variable `$marker` placée dans la CONDITION
    # d'une compréhension Python n'est pas visible (portée imbriquée).
    ${idx}=    Set Variable    ${-1}
    FOR    ${i}    ${l}    IN ENUMERATE    @{lines}
        IF    $marker in $l
            ${idx}=    Set Variable    ${i}
            BREAK
        END
    END
    # int($max) : l'argument arrive en CHAÎNE depuis l'appel Robot, et une tranche
    # n'accepte pas une chaîne comme borne.
    ${sel}=      Evaluate    [l for l in $lines[$idx+1:] if l.strip()][:int($max)]
    ${out}=      Evaluate    chr(10).join($sel)
    RETURN    ${out}

Format Timestamp
    [Arguments]    ${secs}
    ${t}=    Evaluate
    ...    "%02d:%02d:%02d,%03d" % (int(${secs})//3600, (int(${secs})//60)%60, int(${secs})%60, int((${secs}-int(${secs}))*1000))
    RETURN    ${t}

Burn Subtitles
    [Documentation]    Bandeau ajouté SOUS l'image (la fenêtre SAP n'est jamais
    ...                recouverte), puis sous-titres incrustés par libass.
    # ffmpeg est lancé DANS le dossier de sortie et le SRT désigné par son nom nu :
    # un chemin Windows dans un filtre exige d'échapper « \ » ET « : », source
    # d'erreurs inutiles.
    # FontSize est exprimé dans la résolution du script ASS (libass suppose 288 de
    # haut par défaut) : 8 donne ~25 px réels sur une image de 944. À 17, le texte
    # débordait largement sur l'écran SAP.
    # Alignment=1 (bas-gauche) : les lignes de code se lisent mal centrées.
    ${style}=    Set Variable    FontName=Consolas,FontSize=8,PrimaryColour=&H00FFFFFF&,Outline=0,Shadow=0,Alignment=1,MarginL=36,MarginV=14
    ${vf}=    Catenate    SEPARATOR=
    ...    pad=iw:ih+200:0:0:color=0x0a3d62,
    ...    subtitles=ecc_capture.srt:force_style='${style}'
    ${res}=    Run Process    ${FFMPEG}    -y    -hide_banner    -loglevel    error
    ...    -i    ecc_capture.mkv    -vf    ${vf}
    ...    -c:v    libx264    -preset    slow    -crf    22
    ...    -pix_fmt    yuv420p    -movflags    +faststart    -r    30
    ...    ${FINAL}    cwd=${OUT}
    Should Be Equal As Integers    ${res.rc}    0    ${res.stdout}${res.stderr}
    ${size}=    Get File Size    ${OUT}/${FINAL}
    Log To Console    \n>>> MP4 : ${OUT}/${FINAL} (${size} octets)

Resolve Ffmpeg
    ${path}=    Evaluate
    ...    __import__("shutil").which("ffmpeg") or next((p for p in __import__("glob").glob(__import__("os").path.expanduser("~") + "/AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe")), "")
    RETURN    ${path}
