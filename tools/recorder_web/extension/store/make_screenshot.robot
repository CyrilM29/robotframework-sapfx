*** Settings ***
Documentation       Generates the 1280x800 store screenshot of the UI5 Recorder: the
...                 capture panel populated with a few captures and the hover overlay
...                 on a control, on the live OpenUI5 Demo Kit.
...
...                 FR. Génère la capture d'écran 1280x800 pour la fiche du store :
...                 le panneau de captures rempli et la surbrillance au survol, sur
...                 l'OpenUI5 Demo Kit en direct.
...
...                 Run:  robot --pythonpath ../../../../src \\
...                         tools/recorder_web/extension/store/make_screenshot.robot

Library             Browser
Library             OperatingSystem


*** Variables ***
${SPY_JS}           ${CURDIR}/../recorder.js
${OUT_PNG}          ${CURDIR}/screenshot-1280x800.png


*** Test Cases ***
Capture Store Screenshot
    New Browser    chromium    headless=${True}
    New Context    viewport={'width': 1280, 'height': 800}    deviceScaleFactor=1
    New Page       https://sdk.openui5.org/
    Wait For Function    () => !!(window.sap && sap.ui && sap.ui.require)    timeout=30s
    Sleep    3s
    # inject the generated Spy program
    ${spy}=    Get File    ${SPY_JS}
    Evaluate JavaScript    ${None}    (src) => { (0,eval)(src); }    arg=${spy}
    # populate the panel with a few varied captures
    Evaluate JavaScript    ${None}    ${POPULATE_JS}
    # show the hover overlay on a prominent control
    Evaluate JavaScript    ${None}    ${HOVER_JS}
    Sleep    0.4s
    Take Screenshot    ${OUT_PNG}    fullPage=${False}
    Close Browser


*** Variables ***
${POPULATE_JS}=     SEPARATOR=
...    () => {
...      const click = (el) => el && el.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));
...      click(document.querySelector('[id="sdk---app--searchControl-searchField"]'));
...      const btns = document.querySelectorAll('.sapMBtn'); if (btns[0]) click(btns[0]); if (btns[1]) click(btns[1]);
...      const title = document.querySelector('.sapMTitle'); if (title) click(title);
...    }
${HOVER_JS}=        SEPARATOR=
...    () => {
...      const el = document.querySelector('[id="sdk---app--searchControl-searchField"]');
...      if (el) el.dispatchEvent(new MouseEvent('mousemove', {bubbles:true, view:window}));
...    }
