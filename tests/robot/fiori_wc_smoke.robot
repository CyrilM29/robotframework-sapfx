*** Settings ***
Documentation       Smoke du **moteur Web Components** (`Resolve/Click/Fill Wc …`) contre
...                 la fixture locale `fixtures/wc_fixture.html`, une page « pur UI5
...                 Web Components » SANS runtime UI5 (registre vide : les moteurs
...                 role/xpath sont aveugles, c'est précisément le cas d'usage du 3e
...                 moteur : home SuccessFactors et apps ui5-webcomponents). Prouve :
...                 le matching type court/tag complet Y COMPRIS les tags scopés
...                 (`ui5-button-x1b2`), le matching attributs/texte, le clic et la
...                 saisie à travers un shadow root ouvert, le repli `wc=` de
...                 `Resolve Ui5 With Fallback`, et la capture WC du recorder web.
...                 Hors ligne : aucun SAP, aucun réseau (fixture 100 % locale).
...
...                 Run:  robot --pythonpath src tests/robot/fiori_wc_smoke.robot

Library             Browser
Library             SapFioriLibrary    ui5_timeout=10s
Library             OperatingSystem

Suite Setup         Open Wc Fixture
Suite Teardown      Close Browser


*** Variables ***
${HEADLESS}         ${True}


*** Test Cases ***
Short Tag Matches Plain And Scoped Custom Elements
    [Documentation]    `tag=Button` doit matcher les <ui5-button> ET le tag scopé
    ...                <ui5-button-x1b2> (scoping UI5 WC) ; un tag complet aussi.
    ${count}=    Get Wc Match Count    tag=Button
    Should Be Equal As Integers    ${count}    3
    ${count}=    Get Wc Match Count    tag=ui5-button
    Should Be Equal As Integers    ${count}    3
    ${count}=    Get Wc Match Count    tag=Input
    Should Be Equal As Integers    ${count}    1
    Wc Control Should Be Visible    tag=Button    text=Scoped save

Attributes And Text Are Matchable Properties
    [Documentation]    Le matching `properties=` porte sur les attributs de l'hôte
    ...                (mêmes règles que le moteur role : sous-chaîne insensible à la casse).
    Wc Control Should Be Visible    tag=Button    properties={'design': 'Emphasized'}
    Wc Control Should Be Visible    tag=Input    properties={'placeholder': 'name'}
    ${count}=    Get Wc Match Count    tag=Button    text=save
    Should Be Equal As Integers    ${count}    2    # Save + Scoped save (insensible à la casse)

Accessible Name Addresses Hosts By User Intent
    [Documentation]    Le cran accessibilité du moteur wc : `name=` matche le NOM
    ...                ACCESSIBLE de l'hôte, la convention UI5 Web Components
    ...                `accessible-name` (attribut) puis `accessibleName`
    ...                (propriété JS non reflétée), puis le texte visible. Le
    ...                localisateur suit l'intention utilisateur, pas la structure.
    Wc Control Should Be Visible    tag=Input    name=Customer name
    ${count}=    Get Wc Match Count    tag=Button    name=Cancel order
    Should Be Equal As Integers    ${count}    1
    # sans attribut ni propriété : le texte visible reste le nom accessible
    Wc Control Should Be Visible    tag=Button    name=Scoped save

Click Wc Control Reaches The Shadow Internals
    [Documentation]    Le clic sur l'hôte résolu atteint le <button> interne au shadow
    ...                root (compteur de la fixture incrémenté).
    Click Wc Control    tag=Button    text=Save    properties={'design': 'Emphasized'}
    ${clicks}=    Evaluate JavaScript    ${None}    () => document.getElementById('clicks').textContent
    Should Be Equal As Integers    ${clicks}    1

Fill Wc Input Pierces The Open Shadow Root
    [Documentation]    La saisie descend jusqu'à l'<input> réel du shadow root ouvert.
    Fill Wc Input    Jean Dupont    tag=Input
    ${value}=    Evaluate JavaScript    ${None}
    ...    () => document.querySelector('ui5-input').shadowRoot.querySelector('input').value
    Should Be Equal    ${value}    Jean Dupont

Fallback Chain Heals Role To Wc On A Registry-Less Page
    [Documentation]    Sur une page sans runtime UI5, le sélecteur role ne résout pas ;
    ...                la chaîne `Resolve Ui5 With Fallback` doit se replier sur `wc=`
    ...                (réparation journalisée en WARNING, jamais silencieuse).
    ${sel}=    Resolve Ui5 With Fallback
    ...    controlType=Button    properties={'text': 'Save'}
    ...    wc={'tag': 'Button', 'text': 'Save'}
    ...    attempt_timeout=2s
    Should Contain    ${sel}    css=
    Click    ${sel}
    ${clicks}=    Evaluate JavaScript    ${None}    () => document.getElementById('clicks').textContent
    Should Be Equal As Integers    ${clicks}    2

Web Recorder Captures Wc Hosts On A Registry-Less Page
    [Documentation]    Le recorder web, injecté sur une page pur WC, doit transcrire un
    ...                clic en `Click Wc Control` (et Alt+clic en assertion WC) au lieu
    ...                de l'ignorer faute de contrôle UI5/SID.
    ${recjs}=    Normalize Path    ${CURDIR}/../../tools/recorder_web/extension/recorder.js
    ${src}=    Get File    ${recjs}
    Evaluate JavaScript    ${None}    (s) => { (0,eval)(s); }    arg=${src}
    Wait For Function    () => !!document.getElementById('__ui5SpyPanel')    timeout=10s
    Evaluate JavaScript    ${None}
    ...    () => { const p=document.getElementById('__ui5SpyPanel'); [...p.querySelectorAll('button')].find(x=>x.textContent==='rec').click(); }
    Evaluate JavaScript    ${None}
    ...    () => { document.querySelector('[id="saveBtn"]').dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true})); }
    Evaluate JavaScript    ${None}
    ...    () => { document.querySelector('ui5-button-x1b2').dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,altKey:true})); }
    ${panel}=    Evaluate JavaScript    ${None}    () => document.getElementById('__ui5SpyPanel').innerText
    Should Contain    ${panel}    Click Wc Control
    Should Contain    ${panel}    tag=ui5-button
    Should Contain    ${panel}    Wc Control Should Be Visible
    Evaluate JavaScript    ${None}    () => window.__ui5SpyStop()


*** Keywords ***
Open Wc Fixture
    ${fixture}=    Normalize Path    ${CURDIR}/fixtures/wc_fixture.html
    ${url}=    Evaluate    pathlib.Path(r"${fixture}").as_uri()    pathlib
    New Browser    chromium    headless=${HEADLESS}
    New Page    ${url}
    Wait For Function    () => window.__fixtureReady === true    timeout=20s
