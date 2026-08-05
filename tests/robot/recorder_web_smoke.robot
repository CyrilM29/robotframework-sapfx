*** Settings ***
Documentation       Smoke test for the **web Recorder's record mode** against a
...                 self-contained UI5 fixture (OpenUI5 from the CDN, no SAP). Injects
...                 the generated `recorder.js`, starts recording, simulates a click and
...                 a typed value, and asserts the transcribed flow contains the ordered
...                 action keywords (`Click Ui5 Control`, `Fill Ui5 Input`). Needs the
...                 Browser library's Chromium (`rfbrowser init chromium`) and network
...                 (the fixture loads UI5 from sdk.openui5.org).
...
...                 Run:  robot -v HEADLESS:True tests/robot/recorder_web_smoke.robot
...
...                 FR : Test smoke du **mode record du Recorder web** contre un fixture
...                 UI5 autonome (OpenUI5 depuis le CDN, sans SAP). Injecte le
...                 `recorder.js` généré, démarre l'enregistrement, simule un clic et une
...                 saisie, et vérifie que le déroulé transcrit contient les keywords
...                 d'action ordonnés.

Library             Browser
Library             OperatingSystem

Suite Teardown      Close Browser


*** Variables ***
${HEADLESS}         ${True}


*** Test Cases ***
Web Recorder Transcribes A Click And A Fill
    [Documentation]    rec -> clic sur un bouton + saisie d'un champ -> Click Ui5 Control
    ...                puis Fill Ui5 Input, dans l'ordre, lisibles dans le panneau.
    ${fixture}=    Normalize Path    ${CURDIR}/fixtures/ui5_fixture.html
    ${url}=        Evaluate    pathlib.Path(r"${fixture}").as_uri()    pathlib
    ${recjs}=      Normalize Path    ${CURDIR}/../../tools/recorder_web/extension/recorder.js
    New Browser    chromium    headless=${HEADLESS}
    New Context    acceptDownloads=${True}
    New Page       ${url}
    Wait For Function    () => window.__fixtureReady === true    timeout=40s
    # inject the generated recorder program (as the extension would)
    ${src}=    Get File    ${recjs}
    Evaluate JavaScript    ${None}    (s) => { (0,eval)(s); }    arg=${src}
    Wait For Function    () => !!document.getElementById('__ui5SpyPanel')    timeout=10s
    # start recording (panel « rec » button)
    Evaluate JavaScript    ${None}
    ...    () => { const p=document.getElementById('__ui5SpyPanel'); const b=[...p.querySelectorAll('button')].find(x=>x.textContent==='rec'); b.click(); }
    # simulate a user click on the "Open Dialog" button
    Evaluate JavaScript    ${None}
    ...    () => { document.querySelector('[id="openBtn"]').dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true})); }
    # simulate a validated input
    Evaluate JavaScript    ${None}
    ...    () => { const i=document.querySelector('[id="nameInput-inner"]'); i.value='abc'; i.dispatchEvent(new Event('change',{bubbles:true})); }
    # read the transcribed flow from the panel
    ${panel}=    Evaluate JavaScript    ${None}    () => document.getElementById('__ui5SpyPanel').innerText
    Should Contain    ${panel}    Recording
    Should Contain    ${panel}    Click Ui5 Control
    Should Contain    ${panel}    Open Dialog
    Should Contain    ${panel}    Fill Ui5 Input
    Should Contain    ${panel}    abc
    # export ouvre depuis 2026-07 un MENU à 3 formats : cliquer le bouton puis
    # l'entrée « .robot complet » : capture dans le dossier captures du projet
    ${dl_path}=    Normalize Path    ${CURDIR}/../../tools/recorder_web/captures/recorded.robot
    ${promise}=    Promise To Wait For Download    saveAs=${dl_path}
    Evaluate JavaScript    ${None}
    ...    () => { const p=document.getElementById('__ui5SpyPanel'); const b=[...p.querySelectorAll('button')].find(x=>x.textContent==='export'); b.click(); }
    Click    text=.robot complet
    Wait For    ${promise}
    ${content}=    Get File    ${dl_path}
    Should Contain    ${content}    *** Test Cases ***
    Should Contain    ${content}    Click Ui5 Control
    Should Contain    ${content}    Open Dialog
    Should Contain    ${content}    Fill Ui5 Input

Recorder Persists Across Reload Edits Steps And Exports Full Script
    [Documentation]    Enregistre (assertion Alt+clic + clic + saisie), recharge la page,
    ...                vérifie que les steps sont restaurés (sessionStorage), supprime un
    ...                step, puis exporte un .robot COMPLET (Settings + New Browser + steps).
    ${fixture}=    Normalize Path    ${CURDIR}/fixtures/ui5_fixture.html
    ${url}=        Evaluate    pathlib.Path(r"${fixture}").as_uri()    pathlib
    ${recjs}=      Normalize Path    ${CURDIR}/../../tools/recorder_web/extension/recorder.js
    ${src}=        Get File    ${recjs}
    New Browser    chromium    headless=${HEADLESS}
    New Context    acceptDownloads=${True}
    New Page       ${url}
    Wait For Function    () => window.__fixtureReady === true    timeout=40s
    Evaluate JavaScript    ${None}    (s) => { (0,eval)(s); }    arg=${src}
    Wait For Function    () => !!document.getElementById('__ui5SpyPanel')    timeout=10s
    # start recording
    Evaluate JavaScript    ${None}
    ...    () => { const p=document.getElementById('__ui5SpyPanel'); [...p.querySelectorAll('button')].find(x=>x.textContent==='rec').click(); }
    # Alt+click = assertion ; then a normal click ; then a fill
    Evaluate JavaScript    ${None}
    ...    () => { document.querySelector('[id="openBtn"]').dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,altKey:true})); }
    Evaluate JavaScript    ${None}
    ...    () => { document.querySelector('[id="openBtn"]').dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true})); }
    Evaluate JavaScript    ${None}
    ...    () => { const i=document.querySelector('[id="nameInput-inner"]'); i.value='abc'; i.dispatchEvent(new Event('change',{bubbles:true})); }
    # 3 steps recorded
    ${n}=    Evaluate JavaScript    ${None}    () => JSON.parse(sessionStorage.getItem('__ui5RecorderSteps')).length
    Should Be Equal As Integers    ${n}    3
    # reload the page -> recorder gone, steps must persist in sessionStorage
    Reload
    Wait For Function    () => window.__fixtureReady === true    timeout=40s
    Evaluate JavaScript    ${None}    (s) => { (0,eval)(s); }    arg=${src}
    Wait For Function    () => !!document.getElementById('__ui5SpyPanel')    timeout=10s
    ${panel}=    Evaluate JavaScript    ${None}    () => document.getElementById('__ui5SpyPanel').innerText
    Should Contain    ${panel}    Ui5 Control Should Be Visible
    Should Contain    ${panel}    Click Ui5 Control
    Should Contain    ${panel}    Fill Ui5 Input
    # le déchargement pendant l'enregistrement a marqué l'attente rejouable (0.7.0)
    Should Contain    ${panel}    Wait For UI5 Ready
    # ... et l'ENREGISTREMENT lui-même a repris à la ré-injection (flag persisté)
    ${rec}=    Evaluate JavaScript    ${None}    () => window.__ui5RecorderApi.isRecording()
    Should Be True    ${rec}    recording did not resume after reload
    # delete the first step (the assertion) -> 3 left (click + fill + wait)
    Evaluate JavaScript    ${None}
    ...    () => { const p=document.getElementById('__ui5SpyPanel'); [...p.querySelectorAll('button')].find(x=>x.textContent==='✕').click(); }
    ${n2}=    Evaluate JavaScript    ${None}    () => JSON.parse(sessionStorage.getItem('__ui5RecorderSteps')).length
    Should Be Equal As Integers    ${n2}    3
    # export a complete, runnable .robot (menu à 3 formats -> « .robot complet »)
    ${dl2}=    Normalize Path    ${CURDIR}/../../tools/recorder_web/captures/recorded_full.robot
    ${promise}=    Promise To Wait For Download    saveAs=${dl2}
    Evaluate JavaScript    ${None}
    ...    () => { const p=document.getElementById('__ui5SpyPanel'); [...p.querySelectorAll('button')].find(x=>x.textContent==='export').click(); }
    Click    text=.robot complet
    Wait For    ${promise}
    ${full}=    Get File    ${dl2}
    Should Contain    ${full}    *** Settings ***
    Should Contain    ${full}    SapFioriLibrary
    Should Contain    ${full}    New Browser
    Should Contain    ${full}    Click Ui5 Control
    Should Contain    ${full}    Fill Ui5 Input

Recorder Masks Sensitive Fields At Capture Time
    [Documentation]    Portage rf-web-recorder 0.4.1 : les valeurs des champs
    ...                sensibles (password, carte via token autocomplete cc-number,
    ...                OTP via motif de nom) n'atteignent JAMAIS le déroulé enregistré
    ...                (ni sessionStorage, ni export) ; un champ ordinaire est, lui,
    ...                capturé en clair. Fixture hors ligne, sans UI5 : la capture
    ...                passe par le moteur dom.
    ${fixture}=    Normalize Path    ${CURDIR}/fixtures/sensitive_fixture.html
    ${url}=        Evaluate    pathlib.Path(r"${fixture}").as_uri()    pathlib
    ${recjs}=      Normalize Path    ${CURDIR}/../../tools/recorder_web/extension/recorder.js
    ${src}=        Get File    ${recjs}
    New Browser    chromium    headless=${HEADLESS}
    New Page       ${url}
    Evaluate JavaScript    ${None}    (s) => { (0,eval)(s); }    arg=${src}
    Wait For Function    () => !!document.getElementById('__ui5SpyPanel')    timeout=10s
    Evaluate JavaScript    ${None}
    ...    () => { const p=document.getElementById('__ui5SpyPanel'); [...p.querySelectorAll('button')].find(x=>x.textContent==='rec').click(); }
    Evaluate JavaScript    ${None}
    ...    () => { const f=(id,v)=>{ const i=document.getElementById(id); i.value=v; i.dispatchEvent(new Event('change',{bubbles:true})); }; f('pwd','S3cret!'); f('card','4111111111111111'); f('otp','123456'); f('q','abc'); }
    ${steps}=    Evaluate JavaScript    ${None}    () => sessionStorage.getItem('__ui5RecorderSteps')
    Should Contain    ${steps}    <REDACTED>
    Should Contain    ${steps}    <SECRET>
    Should Contain    ${steps}    abc
    Should Not Contain    ${steps}    S3cret!
    Should Not Contain    ${steps}    4111111111111111
    Should Not Contain    ${steps}    123456

Recorder Panel Controls And Extension Api
    [Documentation]    Pièces in-page des items moyen impact : API (__ui5RecorderApi),
    ...                événement d'état (relayé au badge par bridge.js), point
    ...                d'enregistrement, repli et déplacement du panneau.
    ${fixture}=    Normalize Path    ${CURDIR}/fixtures/ui5_fixture.html
    ${url}=        Evaluate    pathlib.Path(r"${fixture}").as_uri()    pathlib
    ${recjs}=      Normalize Path    ${CURDIR}/../../tools/recorder_web/extension/recorder.js
    ${src}=        Get File    ${recjs}
    New Browser    chromium    headless=${HEADLESS}
    New Page       ${url}
    Wait For Function    () => window.__fixtureReady === true    timeout=40s
    Evaluate JavaScript    ${None}    (s) => { (0,eval)(s); }    arg=${src}
    Wait For Function    () => !!document.getElementById('__ui5SpyPanel')    timeout=10s
    ${r}=    Evaluate JavaScript    ${None}    () => { const api=window.__ui5RecorderApi; const before=api.isRecording(); let evt=null; document.addEventListener('__ui5RecorderState', e=>{evt=e.detail;}, {once:true}); api.toggleRec(); const panel=document.getElementById('__ui5SpyPanel'); const dotShown=panel.querySelector('span').style.display==='inline-block'; [...panel.querySelectorAll('button')].find(b=>b.textContent==='▾').click(); const collapsed=[...panel.querySelectorAll('button')].some(b=>b.textContent==='▸'); const head=panel.firstChild; head.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,clientX:120,clientY:120})); document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,clientX:320,clientY:300})); document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true})); const moved=panel.style.left!==''&&panel.style.left!=='auto'; return {before:before, after:api.isRecording(), evt:evt, dotShown:dotShown, collapsed:collapsed, moved:moved}; }
    # api: pas enregistrement -> puis enregistrement ; événement diffusé ; point visible ;
    # panneau replié ; panneau déplacé par glisser.
    Should Be Equal    ${r}[before]    ${False}
    Should Be Equal    ${r}[after]    ${True}
    Should Be Equal    ${r}[evt]    ${True}
    Should Be Equal    ${r}[dotShown]    ${True}
    Should Be Equal    ${r}[collapsed]    ${True}
    Should Be Equal    ${r}[moved]    ${True}
