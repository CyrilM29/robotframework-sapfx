*** Settings ***
Documentation       Smoke **compatibilité UI5 ancien** : exerce SapFioriLibrary contre
...                 un vrai runtime OpenUI5 **1.60.14 (2018)** — antérieur à
...                 ``Element.registry`` (1.67) — chargé depuis le miroir npm jsDelivr
...                 par ``fixtures/ui5_legacy_fixture.html``. Prouve que le repli DOM
...                 de ``registryForEach`` (balayage ``[data-sap-ui]`` + ``byId``)
...                 résout les contrôles rendus là où le registre n'existe pas :
...                 c'est le cas des launchpads S/4 1610/1709 (UI5 1.44/1.52/1.60).
...                 Nécessite le réseau (CDN jsDelivr), aucun SAP.
...                 Exécution :  robot --pythonpath src tests/robot/fiori_legacy_smoke.robot

Library             OperatingSystem
Library             Browser
Library             SapFioriLibrary    ui5_timeout=60s

Suite Setup         Open Legacy Fixture
Suite Teardown      Close Browser


*** Variables ***
${HEADLESS}         ${True}


*** Keywords ***
Open Legacy Fixture
    ${fixture}=    Normalize Path    ${CURDIR}/fixtures/ui5_legacy_fixture.html
    ${url}=        Evaluate    pathlib.Path(r"${fixture}").as_uri()    pathlib
    New Browser    chromium    headless=${HEADLESS}
    Set Browser Timeout    150s
    # Le runtime 1.60 « src » charge des centaines de modules individuels : l'événement
    # `load` met bien plus de 10 s — on n'attend que le DOM puis le drapeau du fixture.
    New Page       ${url}    wait_until=domcontentloaded
    Wait For Function    () => window.__fixtureReady === true    timeout=150s


*** Test Cases ***
Runtime Predates The Element Registry
    [Documentation]    Garde-fou : vérifie que ce runtime n'a NI ``Element.registry``
    ...                (1.67+) NI le module ``ElementRegistry`` (2.x) — sinon le test
    ...                ne prouverait pas le chemin de repli.
    ${legacy}=    Evaluate JavaScript    ${None}
    ...    () => { const E = sap.ui.require('sap/ui/core/Element'); const R = sap.ui.require('sap/ui/core/ElementRegistry'); return !!E && !E.registry && !R; }
    Should Be True    ${legacy}    msg=Runtime exposes a registry — not a pre-1.67 target

Role Engine Resolves Controls Via The DOM Fallback
    [Documentation]    La résolution role/propriétés fonctionne sans registre.
    Ui5 Control Should Be Visible    controlType=sap.m.Button    properties={'text': 'Legacy Go'}
    Click Ui5 Control    controlType=sap.m.Button    properties={'text': 'Legacy Go'}
    ${pressed}=    Evaluate JavaScript    ${None}    () => window.__pressed === true
    Should Be True    ${pressed}

Inputs And Tables Work On The Legacy Runtime
    [Documentation]    Saisie dans un ``sap.m.Input`` et lecture de table — les deux
    ...                passent par la résolution role (repli DOM) puis Browser.
    Fill Ui5 Input    bonjour    controlType=sap.m.Input    properties={'placeholder': 'legacy input'}
    ${rows}=    Read Ui5 Table    controlType=sap.m.Table
    Length Should Be    ${rows}    2
    Should Be Equal    ${rows}[0][Name]    Acme

Xpath Engine Works On The Legacy Runtime
    [Documentation]    L'arbre XPath (balayage DOM, indépendant du registre) résout
    ...                un localisateur hiérarchique et retourne le xpath unique le plus court.
    ${sel}=    Resolve Ui5 By Xpath    //Table//Text[@text='Globex']
    Should Not Be Empty    ${sel}
    # Contrat aller-retour : le xpath « le plus court unique » retourné doit se
    # résoudre vers le même contrôle. (Sur ce vieux rendu, le type court Table
    # apparaît deux fois dans l'arbre, d'où un index — c'est correct.)
    ${xp}=    Get Ui5 Xpath    id=legacyTable
    Should Match Regexp    ${xp}    ^//Table(\\[\\d+\\])?$
    ${roundtrip}=    Resolve Ui5 By Xpath    ${xp}
    Should Be Equal    ${roundtrip}    css=[id="legacyTable"]
