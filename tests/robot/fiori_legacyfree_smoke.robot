*** Settings ***
Documentation       Smoke **compatibilité UI5 1.136 legacy-free** : exerce SapFioriLibrary
...                 contre la variante officielle ``1.136-legacy-free`` du CDN OpenUI5
...                 (``fixtures/ui5_legacyfree_fixture.html``) : la LTS 1.136 avec TOUT
...                 le code déprécié supprimé (façade ``sap.ui.getCore()``,
...                 ``Element.registry``, globals de bibliothèques). C'est le véhicule
...                 que SAP recommande pour tester la compatibilité 2.x tant que 2.0
...                 n'est pas GA, donc la baseline intermédiaire que rencontreront
...                 les clients. Complète le triptyque de compatibilité :
...                 ``fiori_legacy_smoke.robot`` (1.60, repli DOM) ←
...                 CE SMOKE (1.136 legacy-free, branche module ElementRegistry) →
...                 ``fiori_ui5v2_smoke.robot`` (2.0 nightly). Contrairement au
...                 nightly, cette cible est STABLE (version LTS figée) : un échec
...                 ici est une vraie régression de la bibliothèque.
...                 Nécessite le réseau (CDN OpenUI5), aucun SAP.
...                 Exécution :  robot --pythonpath src tests/robot/fiori_legacyfree_smoke.robot

Library             OperatingSystem
Library             Browser
Library             SapFioriLibrary    ui5_timeout=60s

Suite Setup         Open Legacy Free Fixture
Suite Teardown      Close Browser


*** Variables ***
${HEADLESS}         ${True}


*** Keywords ***
Open Legacy Free Fixture
    ${fixture}=    Normalize Path    ${CURDIR}/fixtures/ui5_legacyfree_fixture.html
    ${url}=        Evaluate    pathlib.Path(r"${fixture}").as_uri()    pathlib
    New Browser    chromium    headless=${HEADLESS}
    Set Browser Timeout    120s
    New Page       ${url}    wait_until=domcontentloaded
    Wait For Function    () => window.__fixtureReady === true    timeout=120s


*** Test Cases ***
Runtime Is Legacy Free
    [Documentation]    Garde-fou : ce runtime est bien une 1.136 SANS les APIs
    ...                dépréciées (ni la façade ``sap.ui.getCore`` ni
    ...                ``Element.registry``) : sinon ce smoke ne prouverait pas
    ...                la branche module ``ElementRegistry``.
    ${version}=    Evaluate JavaScript    ${None}
    ...    () => new Promise((res) => sap.ui.require(['sap/ui/VersionInfo'], (VI) => VI.load().then((i) => res(i.version)).catch(() => res('load-failed')), () => res('module-missing')))
    Should Match Regexp    ${version}    ^1\\.136\\.    msg=Runtime is not a 1.136 build (got ${version})
    ${legacy_free}=    Evaluate JavaScript    ${None}
    ...    () => { const E = sap.ui.require('sap/ui/core/Element'); const R = sap.ui.require('sap/ui/core/ElementRegistry'); return typeof sap.ui.getCore !== 'function' && !!R && typeof R.forEach === 'function' && !(E && E.registry); }
    Should Be True    ${legacy_free}    msg=Legacy APIs still present: not a legacy-free build

Role Engine Resolves Controls On The Legacy Free Runtime
    [Documentation]    La résolution role/propriétés fonctionne via le module
    ...                ``ElementRegistry`` (aucun chemin ne touche une API supprimée).
    Ui5 Control Should Be Visible    controlType=sap.m.Button    properties={'text': 'LegacyFree Go'}
    Click Ui5 Control    controlType=sap.m.Button    properties={'text': 'LegacyFree Go'}
    ${pressed}=    Evaluate JavaScript    ${None}    () => window.__pressed === true
    Should Be True    ${pressed}

Inputs And Tables Work On The Legacy Free Runtime
    Fill Ui5 Input    bonjour    controlType=sap.m.Input    properties={'placeholder': 'lf input'}
    ${rows}=    Read Ui5 Table    controlType=sap.m.Table
    Length Should Be    ${rows}    2
    Should Be Equal    ${rows}[0][Name]    Acme

Xpath Engine Works On The Legacy Free Runtime
    ${sel}=    Resolve Ui5 By Xpath    //Table//Text[@text='Globex']
    Should Not Be Empty    ${sel}
    ${xp}=    Get Ui5 Xpath    id=lfTable
    ${roundtrip}=    Resolve Ui5 By Xpath    ${xp}
    Should Be Equal    ${roundtrip}    css=[id="lfTable"]
