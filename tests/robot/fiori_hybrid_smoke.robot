*** Settings ***
Documentation       Smoke des **sessions hybrides** contre la fixture locale
...                 `fixtures/hybrid_fixture.html`, une page composite SANS runtime
...                 UI5 où cohabitent quatre régions technologiques : hôtes UI5 Web
...                 Components, élément WebGUI (`lsdata`), widget web générique
...                 marqué React, et frames IMBRIQUÉES (level1 -> level2). Prouve :
...                 la sonde de composition `Get Page Composition` (technologies +
...                 moteurs recommandés par région, descente dans les frames), le
...                 moteur DOM générique (`Resolve/Click/Fill Dom …` : la zone
...                 non-SAP entre dans la même grammaire), la pile de frames
...                 `Push/Pop Ui5 Frame` (portée chaînée ``a >>> b`` sur deux
...                 niveaux), et le repli ``dom=`` de `Resolve Ui5 With Fallback`.
...                 Hors ligne : aucun SAP, aucun réseau (fixture 100 % locale).
...
...                 Run:  robot --pythonpath src tests/robot/fiori_hybrid_smoke.robot

Library             Browser
Library             SapFioriLibrary    ui5_timeout=10s
Library             OperatingSystem

Suite Setup         Open Hybrid Fixture
Suite Teardown      Close Browser


*** Variables ***
${HEADLESS}         ${True}


*** Test Cases ***
Composition Probe Names The Technologies And Engines Per Region
    [Documentation]    La perception hybride : la sonde rapporte chaque technologie
    ...                présente, les moteurs recommandés, et descend dans les frames.
    ${comp}=    Get Page Composition
    Should Be Equal    ${comp}[ui5_runtime]    ${False}
    Should Be True    ${comp}[wc_hosts] >= 2
    Should Be True    ${comp}[webgui_elements] >= 1
    Should Contain    ${comp}[frameworks]    react
    Should Not Contain    ${comp}[engines]    role    # pas de runtime UI5 : role exclu
    Should Contain    ${comp}[engines]    sid
    Should Contain    ${comp}[engines]    wc
    Should Contain    ${comp}[engines]    dom
    # descente d'un niveau : la frame level1 est sondée à son tour
    ${level1}=    Set Variable    ${comp}[frames][0]
    Should Be Equal    ${level1}[selector]    iframe[id="level1"]
    Should Be True    ${level1}[composition][webgui_elements] >= 1
    # ...et rapporte elle-même SA sous-frame (level2), sondable via la pile
    ${sub_frames}=    Get Length    ${level1}[composition][frames]
    Should Be True    ${sub_frames} >= 1

Dom Engine Resolves Clicks And Fills The Non-Sap Widget
    [Documentation]    Le widget React n'est visible d'aucun moteur SAP ; le moteur
    ...                DOM générique le résout (rôle ARIA + texte), clique et saisit.
    ${count}=    Get Dom Match Count    role=button    text=Valider
    Should Be Equal As Integers    ${count}    1
    Dom Element Should Be Visible    role=button    properties={'data-testid': 'submit'}
    Click Dom Element    role=button    text=Valider
    ${clicks}=    Evaluate JavaScript    ${None}    () => document.getElementById('clicks').textContent
    Should Be Equal As Integers    ${clicks}    1
    Fill Dom Input    Jean Dupont    css=input[id="name-input"]
    ${value}=    Evaluate JavaScript    ${None}    () => document.getElementById('name-input').value
    Should Be Equal    ${value}    Jean Dupont

Accessibility Locators Address The Widget By Role And Name
    [Documentation]    Le cran accessibilité du moteur dom : rôle ARIA IMPLICITE
    ...                (sémantique HTML, aucun attribut role sur la cible) + nom
    ...                accessible (aria-label, label[for]) : le localisateur
    ...                « intention utilisateur », indépendant de la structure DOM.
    # bouton d'icône : ni attribut role, ni texte parlant, l'aria-label le nomme
    ${count}=    Get Dom Match Count    role=button    name=Fermer la notification
    Should Be Equal As Integers    ${count}    1
    Click Dom Element    role=button    name=Fermer la notification
    ${hidden}=    Evaluate JavaScript    ${None}    () => document.getElementById('note').hidden
    Should Be Equal    ${hidden}    ${True}
    # champ nommé par son <label for=…> : rôle textbox implicite (input nu)
    Fill Dom Input    Martin    role=textbox    name=Nom du client
    ${value}=    Evaluate JavaScript    ${None}    () => document.getElementById('name-input').value
    Should Be Equal    ${value}    Martin

Frame Stack Scopes Resolution Across Two Nested Levels
    [Documentation]    Push/Pop Ui5 Frame : la portée s'empile (chaînage Browser
    ...                ``level1 >>> level2``) : le moteur sid opère au niveau 1,
    ...                le moteur dom au niveau 2, puis la pile se déroule.
    Push Ui5 Frame    iframe[id="level1"]
    Sid Should Be Visible    wnd[0]/tbar[1]/btn[8]
    Push Ui5 Frame    iframe[id="level2"]
    ${stack}=    Get Ui5 Frame Stack
    Length Should Be    ${stack}    2
    Click Dom Element    role=button    text=Deep action
    ${clicked}=    Evaluate JavaScript
    ...    iframe[id="level1"] >>> iframe[id="level2"] >>> css=body
    ...    (b) => b.dataset.clicked
    Should Be Equal    ${clicked}    1
    Pop Ui5 Frame
    Sid Should Be Visible    wnd[0]/tbar[1]/btn[8]    # revenu au niveau 1
    Pop Ui5 Frame
    ${stack}=    Get Ui5 Frame Stack
    Length Should Be    ${stack}    0
    [Teardown]    Set Ui5 Frame    ${EMPTY}    # isolation : jamais de portée résiduelle

Pop On The Main Page Fails Clearly
    [Documentation]    Un Pop de trop est un bug de scénario : erreur nette, jamais
    ...                un état de portée silencieusement faux.
    Run Keyword And Expect Error    *frame stack is empty*    Pop Ui5 Frame

Fallback Chain Heals Role To Dom On A Non-Sap Widget
    [Documentation]    Sur une page sans runtime UI5, le sélecteur role ne résout
    ...                pas ; la chaîne se replie sur ``dom=`` (réparation
    ...                journalisée en WARNING + télémétrie, jamais silencieuse).
    ${sel}=    Resolve Ui5 With Fallback
    ...    controlType=Button    properties={'text': 'Valider'}
    ...    dom={'role': 'button', 'text': 'Valider'}
    ...    attempt_timeout=2s
    Should Contain    ${sel}    css=
    Click    ${sel}
    ${clicks}=    Evaluate JavaScript    ${None}    () => document.getElementById('clicks').textContent
    Should Be Equal As Integers    ${clicks}    2


*** Keywords ***
Open Hybrid Fixture
    ${fixture}=    Normalize Path    ${CURDIR}/fixtures/hybrid_fixture.html
    ${url}=    Evaluate    pathlib.Path(r"${fixture}").as_uri()    pathlib
    New Browser    chromium    headless=${HEADLESS}
    New Page    ${url}
    Wait For Function    () => window.__fixtureReady === true    timeout=20s
