*** Settings ***
Documentation       Démo scénarisée du **recorder web SAP** contre une VRAIE application
...                 Fiori Elements (cap-sflight), ENREGISTRÉE EN VIDÉO (Playwright
...                 recordVideo) pour la communication. Sous-titres incrustés dans la
...                 page : la vidéo se comprend sans commentaire audio.
...
...                 Prérequis :  cd _cap-sflight && npx cds watch    # -> localhost:4004
...                 Lancer    :  robot --pythonpath src tools/recorder_web/demo/fiori_demo_video.robot
...                 Sortie    :  dist/video/sapfx-fiori-recorder-demo.webm (+ .mp4)
...
...                 Headless par DÉFAUT : une fenêtre visible reste interactive, donc un
...                 simple mouvement de souris pollue la prise. `-v HEADLESS:False` pour
...                 regarder la démo se dérouler — mais alors, ne toucher à rien.

Library             Browser    auto_closing_level=SUITE
Library             OperatingSystem
Library             Collections
Library             Process

Suite Teardown      Close Browser


*** Variables ***
${APP}              http://localhost:4004/sap.fe.cap.travel/index.html
${RECJS}            ${CURDIR}${/}..${/}extension${/}recorder.js
# auth `mocked` de cds v9 : les requêtes OData anonymes prennent un 401 et la
# List Report reste vide (constaté live 2026-07-20) — utilisateur mocké de
# cap-sflight, surchargez par -v CDS_USER:... -v CDS_PWD:... si besoin.
${CDS_USER}         alice
${CDS_PWD}          ${EMPTY}
${OUT}              ${CURDIR}${/}..${/}..${/}..${/}dist${/}video
${HEADLESS}         ${True}
${BEAT}             1.8s
${SEARCH}           input[id$="BasicSearchField-inner-I"]
${GO}               button:has-text("Go") >> visible=true
# posée à l'exécution (chemin résolu en slashes) — déclarée ici pour l'analyse statique
${VIDEO_DIR}        ${EMPTY}


*** Test Cases ***
Record The Fiori Demo Video
    ${src}=    Get File    ${RECJS}
    # Chemin en SLASHES : un chemin Windows à backslashes est mangé à l'évaluation
    # du dict (\Q, \d… lus comme des échappements).
    ${video_dir}=    Evaluate    pathlib.Path(r"${OUT}").resolve().as_posix()    pathlib
    Set Suite Variable    ${VIDEO_DIR}    ${video_dir}
    Create Directory    ${video_dir}
    # Purge des captures Playwright d'anciennes prises : sans elle, la prise livrée
    # pouvait être une VIEILLE vidéo (vu en vrai — 28 s livrées pour un scénario
    # de 49 s). `Rename Video To` prend en plus la plus récente, ceinture et bretelles.
    Remove File    ${video_dir}${/}page@*.webm
    New Browser    chromium    headless=${HEADLESS}    slowMo=0:00:00.20
    New Context
    ...    viewport={'width': 1280, 'height': 720}
    ...    recordVideo={'dir': '${video_dir}', 'size': {'width': 1280, 'height': 720}}
    ...    acceptDownloads=${True}
    ...    locale=en-US
    ...    httpCredentials={'username': '$CDS_USER', 'password': '$CDS_PWD'}
    New Page    ${APP}
    Wait For Elements State    ${GO}    visible    timeout=180s
    Wait For UI5 Idle
    Install Caption Bar

    Caption    SAP Fiori — enregistreur de tests    Robot Framework · application Fiori Elements réelle
    Sleep    3s

    Caption    1. Injection    Extension Chrome ou snippet console — le panneau apparaît
    Intercept Blobs
    Evaluate JavaScript    ${None}    (s) => { (0,eval)(s); }    arg=${src}
    Wait For Function    () => !!document.getElementById('__ui5SpyPanel')    timeout=15s
    Sleep    2.5s

    Caption    2. Mode enregistrement    Un clic sur « rec », puis on utilise l'application
    Evaluate JavaScript    ${None}    () => { window.__ui5RecorderApi.toggleRec(); }
    Sleep    ${BEAT}

    Caption    3. Parcours métier réel    Rechercher une agence, puis lancer la recherche
    ${total}=    Read Table Title
    Fill Text    ${SEARCH}    Aussie
    Sleep    ${BEAT}
    Click    ${GO}
    Wait For UI5 Idle
    ${filtered}=    Read Table Title
    Set Suite Variable    ${FILTERED}    ${filtered}
    Caption    3. Le filtre s'applique    ${total} → ${filtered}
    Sleep    2.5s

    # Sous-titre EXACT : l'id DOM montré est celui du champ de recherche, préfixé par
    # le composant applicatif. Le recorder n'en garde que le suffixe stable Fiori
    # Elements — c'est ce qui survit à un changement de composant ou de thème.
    Caption    4. Des CONTRÔLES UI5, pas des ids DOM    L'id DOM porte le préfixe de l'app ; le recorder ne garde que le suffixe stable Fiori Elements
    Show Locator Card
    Sleep    5s
    Hide Overlay

    Caption    5. Le déroulé survit au rechargement    On recharge l'application : le filtre est défait
    Reload
    Wait For Elements State    ${GO}    visible    timeout=180s
    Wait For UI5 Idle
    # le rechargement emporte TOUT ce qui a été incrusté : bandeau et interception
    # de Blobs se réinstallent (le recorder, lui, se réinjecte juste après).
    Install Caption Bar
    Intercept Blobs
    Evaluate JavaScript    ${None}    (s) => { (0,eval)(s); }    arg=${src}
    Wait For Function    () => !!document.getElementById('__ui5SpyPanel')    timeout=15s
    ${reset}=    Read Table Title
    Caption    5. Application remise à zéro    ${reset} — mais les steps sont toujours là
    Sleep    3s

    Caption    6. Replay dans la page    « play » rejoue le déroulé, avec les mêmes moteurs de résolution
    Evaluate JavaScript    ${None}    () => { window.__ui5RecorderApi.play(); }
    Wait For Function    () => window.__ui5RecorderApi.isReplaying() === false    timeout=120s
    Wait For UI5 Idle
    ${after}=    Read Table Title
    Should Be Equal    ${after}    ${FILTERED}    le replay doit ramener l'app à l'état filtré
    Caption    6. L'application a réellement réagi    ${reset} → ${after} — validé avant même d'exporter
    Sleep    3s

    Caption    7. Export resource-first    Keywords métier + suite SANS localisateur — la convention du projet
    Export Resource First
    Park Mouse
    Show Exported Pair
    Sleep    6s
    Hide Overlay

    Caption    Fiori · WebGUI · UI5 Web Components · zones non-SAP    Cinq moteurs de résolution, un seul enregistreur
    Sleep    4s

    # la vidéo n'est écrite qu'à la FERMETURE du contexte
    Close Context
    Rename Video To    sapfx-fiori-recorder-demo.webm
    Convert To Mp4     sapfx-fiori-recorder-demo.webm    sapfx-fiori-recorder-demo.mp4


*** Keywords ***
Install Caption Bar
    [Documentation]    Bandeau de sous-titres incrusté EN BAS À GAUCHE : le panneau du
    ...                recorder vit en bas à droite, on ne le recouvre pas. `pointer-events
    ...                none` pour ne jamais intercepter un clic du scénario.
    ...
    ...                Ajouté à `documentElement`, PAS à `body` : le `<body>` d'une app UI5
    ...                impose son contexte de mise en page — greffé dedans, le bandeau
    ...                s'étirait sur toute la hauteur et poussait l'application de côté
    ...                (constaté à l'image). Le recorder ancre son propre menu là pour la
    ...                même raison. `height:auto` verrouille le calcul de hauteur.
    Evaluate JavaScript    ${None}
    ...    () => { const b = document.createElement('div'); b.id = '__demoCaption'; b.style.cssText = 'position:fixed;bottom:0;left:0;right:404px;height:auto;z-index:2147483000;pointer-events:none;background:linear-gradient(90deg,#0a3d62,#1d6fa5);color:#fff;padding:13px 20px;font:600 19px/1.3 -apple-system,Segoe UI,sans-serif;box-shadow:0 -2px 12px rgba(0,0,0,.3);'; const t = document.createElement('div'); const s = document.createElement('div'); s.style.cssText = 'font:400 13px/1.4 -apple-system,Segoe UI,sans-serif;opacity:.88;margin-top:3px;'; b.appendChild(t); b.appendChild(s); document.documentElement.appendChild(b); window.__caption = (a, c) => { t.textContent = a; s.textContent = c || ''; }; }

Caption
    [Arguments]    ${title}    ${subtitle}=${EMPTY}
    # Les textes passent en ARGUMENT (jamais interpolés dans une chaîne JS) :
    # une apostrophe française (« l'application ») casserait le littéral.
    Evaluate JavaScript    ${None}
    ...    (s) => { const i = s.indexOf('||'); window.__caption(s.slice(0, i), s.slice(i + 2)); }    arg=${title}||${subtitle}
    Log To Console    \n>>> ${title} — ${subtitle}

Read Table Title
    [Documentation]    Le titre de la table FE porte le compte (« Travels (4,133) ») :
    ...                c'est l'effet métier observable d'un filtre.
    ${t}=    Evaluate JavaScript    ${None}
    ...    () => { const el = [...document.querySelectorAll('.sapMTitle, .sapMText')].find(e => /^Travels?\\s*\\(/.test(e.innerText.trim())); return el ? el.innerText.trim() : ''; }
    RETURN    ${t}

Wait For UI5 Idle
    Sleep    1s
    Wait For Function
    ...    () => { try { const c = window.sap && sap.ui && sap.ui.getCore && sap.ui.getCore(); return !c || !c.getUIDirty || !c.getUIDirty(); } catch (e) { return true; } }
    ...    timeout=60s
    Sleep    1.5s

Intercept Blobs
    [Documentation]    Capte les Blobs des exports : la vidéo pourra afficher le LIVRABLE.
    Evaluate JavaScript    ${None}
    ...    () => { window.__blobs = []; const o = URL.createObjectURL.bind(URL); URL.createObjectURL = (b) => { window.__blobs.push(b); return o(b); }; }

Show Locator Card
    [Documentation]    Carte « id DOM généré » vs « localisateur enregistré » : le point
    ...                qui distingue un enregistreur SAP d'un enregistreur DOM générique.
    ${domid}=    Evaluate JavaScript    ${None}
    ...    () => { const i = document.querySelector('input[id$="BasicSearchField-inner-I"]'); return i ? i.id : ''; }
    ${step}=    Evaluate JavaScript    ${None}
    ...    () => (JSON.parse(sessionStorage.getItem('__ui5RecorderSteps') || '[]'))[0] || ''
    Show Overlay    Ce que rend Fiori Elements||${domid}||Ce qu'enregistre le recorder||${step}

Show Exported Pair
    [Documentation]    Affiche la paire exportée : la vidéo montre le livrable, pas
    ...                seulement le geste.
    ${res}=    Evaluate JavaScript    ${None}    () => window.__blobs[0].text()
    ${rob}=    Evaluate JavaScript    ${None}    () => window.__blobs[1].text()
    Log To Console    \n----- .resource -----\n${res}\n----- .robot -----\n${rob}
    Show Overlay    recorded_keywords.resource||${res}||recorded.robot (aucun localisateur)||${rob}

Show Overlay
    [Documentation]    Superposition à deux blocs (titre + contenu monospace).
    [Arguments]    ${payload}
    Evaluate JavaScript    ${None}
    ...    (s) => { const p = s.split('||'); const w = document.createElement('div'); w.id = '__demoOverlay'; w.style.cssText = 'position:fixed;left:32px;top:56px;height:auto;z-index:2147482000;display:flex;flex-direction:column;gap:12px;width:58%;'; for (let i = 0; i < p.length; i += 2) { const c = document.createElement('div'); c.style.cssText = 'background:#0d1117;color:#c9d1d9;padding:14px 18px;border-radius:8px;box-shadow:0 8px 30px rgba(0,0,0,.45);'; const h = document.createElement('div'); h.textContent = p[i]; h.style.cssText = 'font:600 12px -apple-system,Segoe UI,sans-serif;color:#7d8590;margin-bottom:7px;text-transform:uppercase;letter-spacing:.5px;'; const b = document.createElement('pre'); b.textContent = p[i + 1]; b.style.cssText = 'margin:0;font:12px/1.5 Consolas,monospace;white-space:pre-wrap;overflow-wrap:break-word;'; c.appendChild(h); c.appendChild(b); w.appendChild(c); } document.documentElement.appendChild(w); }    arg=${payload}

Hide Overlay
    Evaluate JavaScript    ${None}
    ...    () => { const o = document.getElementById('__demoOverlay'); if (o) o.remove(); }

Export Resource First
    Evaluate JavaScript    ${None}
    ...    () => { const p=document.getElementById('__ui5SpyPanel'); [...p.querySelectorAll('button')].find(b=>b.textContent==='export').click(); }
    Sleep    1s
    # Libellé EXACT (guillemets) : « resource-first » seul matche aussi le
    # sous-titre de la démo, et Playwright refuse un sélecteur ambigu.
    Click    text="resource-first (.resource + .robot)"
    Wait For Function    () => window.__blobs && window.__blobs.length >= 2    timeout=20s

Park Mouse
    [Documentation]    Gare le curseur SUR le panneau : le survol y est ignoré, donc plus
    ...                aucune pastille de surbrillance ne traîne sur les plans de fin.
    Hover    css=#__ui5SpyPanel
    Sleep    0.4s

Rename Video To
    [Arguments]    ${name}
    Sleep    2s                      # Playwright finit d'écrire le .webm après Close Context
    Wait Until Keyword Succeeds    10x    1s    Video File Exists
    # La capture de CETTE prise = le page@*.webm le plus RÉCENT. Prendre le premier
    # par ordre alphabétique livrait une prise périmée quand le dossier n'était pas
    # vierge (constaté : 28 s livrées pour un scénario de 49 s).
    ${latest}=    Evaluate
    ...    max(__import__("glob").glob("${VIDEO_DIR}/page@*.webm"), key=__import__("os").path.getmtime)
    ${target}=    Normalize Path    ${VIDEO_DIR}/${name}
    Remove File    ${target}
    Move File    ${latest}    ${target}
    ${size}=    Get File Size    ${target}
    Log To Console    \n>>> Vidéo : ${target} (${size} octets)

Video File Exists
    ${files}=    List Files In Directory    ${VIDEO_DIR}    page@*.webm
    Should Not Be Empty    ${files}    aucune capture produite par Playwright

Convert To Mp4
    [Documentation]    Convertit le .webm de Playwright en .mp4 H.264 (le format que
    ...                LinkedIn accepte). Best-effort : sans ffmpeg, on garde le .webm.
    [Arguments]    ${source}    ${target}
    ${ffmpeg}=    Resolve Ffmpeg
    # On teste une LONGUEUR : interpoler un chemin Windows dans une expression
    # le ferait lire comme des échappements Python (\U…).
    ${found}=    Get Length    ${ffmpeg}
    IF    ${found} == 0
        Log To Console    \n>>> ffmpeg absent — .webm conservé (convertir pour LinkedIn)
        RETURN
    END
    ${result}=    Run Process    ${ffmpeg}    -y    -hide_banner    -loglevel    error
    ...    -i    ${VIDEO_DIR}/${source}
    ...    -c:v    libx264    -preset    slow    -crf    22
    ...    -pix_fmt    yuv420p    -movflags    +faststart    -r    30
    ...    ${VIDEO_DIR}/${target}
    Should Be Equal As Integers    ${result.rc}    0    ${result.stderr}
    ${size}=    Get File Size    ${VIDEO_DIR}/${target}
    Log To Console    \n>>> MP4 : ${VIDEO_DIR}/${target} (${size} octets)

Resolve Ffmpeg
    [Documentation]    ffmpeg du PATH, sinon les emplacements connus (installation
    ...                winget, ou le binaire embarqué par imageio-ffmpeg).
    ${path}=    Evaluate
    ...    __import__("shutil").which("ffmpeg") or next((p for p in __import__("glob").glob(__import__("os").path.expanduser("~") + "/AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe")), "") or (__import__("imageio_ffmpeg").get_ffmpeg_exe() if __import__("importlib").util.find_spec("imageio_ffmpeg") else "")
    RETURN    ${path}
