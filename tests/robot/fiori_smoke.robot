*** Settings ***
Documentation       Smoke test for the Fiori/web side against the public OpenUI5
...                 Demo Kit — no SAP access or login required. Exercises the ported
...                 playwright-sap locator engine: role/property resolution, the
...                 hierarchical UI5 *XPath* engine over the control tree, drilling
...                 to the interactable inner element, and clear failure on no match.
...
...                 Locators are *locale-independent* (control type / @controlType),
...                 since the Demo Kit renders in the browser language.
...
...                 Run (after `pip install -r requirements.txt` and `rfbrowser init`):
...                   robot -v HEADLESS:True tests/robot/fiori_smoke.robot
...
...                 FR — Test smoke du côté Fiori/web sur l'OpenUI5 Demo Kit public —
...                 aucun accès SAP ni login requis. Exerce le moteur de locators porté
...                 de playwright-sap : résolution par rôle/propriété, moteur XPath UI5
...                 hiérarchique sur l'arbre des contrôles, descente vers l'élément
...                 interactif, et échec explicite si aucune correspondance. Les
...                 locators sont indépendants de la langue (type de contrôle /
...                 @controlType), car le Demo Kit s'affiche dans la langue du navigateur.

Library             Browser
Library             SapFioriLibrary    ui5_timeout=20s

Suite Setup         Open Demo Kit
Suite Teardown      Close Browser


*** Variables ***
${FIORI_BASE_URL}       https://sdk.openui5.org/
${HEADLESS}             ${True}


*** Test Cases ***
Role Resolves By Short Or Full Control Type
    [Documentation]    Type-only resolution (no text -> any UI language), accepting
    ...                both the short (`SearchField`) and full (`sap.m.SearchField`) name.
    ${short}=    Resolve Ui5 Control    controlType=SearchField
    ${full}=     Resolve Ui5 Control    controlType=sap.m.SearchField
    Should Be Equal    ${short}    ${full}
    Should Contain     ${short}    searchField
    Wait For Elements State    ${short}    visible

XPath Engine Resolves Over The Control Tree
    [Documentation]    The ported UI5 XML tree + XPath engine: address controls by
    ...                tree position and attribute predicate. `@controlType` is always
    ...                present, so this is locale-independent.
    ${byType}=    Resolve Ui5 By Xpath    //SearchField
    ${byAttr}=    Resolve Ui5 By Xpath    //*[@controlType='sap.m.SearchField']
    Should Contain    ${byType}    searchField
    Should Be Equal   ${byType}    ${byAttr}

Fill Drills To The Inner Input
    [Documentation]    End-to-end: the convenience keyword reaches the inner <input>
    ...                of a composite control, not the root <div>.
    Fill Ui5 Input    UI5 rocks    controlType=SearchField
    ${selector}=    Resolve Ui5 Control    controlType=SearchField
    Get Property    ${selector} input    value    ==    UI5 rocks

Match Count Is Reported
    [Documentation]    Registry role matching returns a cardinality (>=1 buttons).
    ${count}=    Get Ui5 Match Count    controlType=Button
    Should Be True    ${count} >= 1

Shortest Unique XPath Round-Trips
    [Documentation]    Get Ui5 Xpath returns the shortest unique tree path; feeding it
    ...                back into the XPath engine must resolve the same control.
    ${xpath}=    Get Ui5 Xpath    controlType=SearchField
    Should Start With    ${xpath}    //
    ${viaShort}=    Resolve Ui5 By Xpath    ${xpath}
    Should Contain    ${viaShort}    searchField

Missing Control Fails Clearly
    [Documentation]    Both engines must fail loudly on no match, never silently.
    Run Keyword And Expect Error    *No UI5 control matched*
    ...    Resolve Ui5 Control    controlType=sap.m.Button    properties={'text': 'ZZZ_DOES_NOT_EXIST'}
    Run Keyword And Expect Error    *No UI5 control matched*
    ...    Resolve Ui5 By Xpath    //ZzzNoSuchControl

Page Tree Serializes The Control Hierarchy
    [Documentation]    Perception keyword consumed by the rf-mcp agent plugin: returns
    ...                the UI5 control tree as XML so an agent can *see* the screen.
    ...                Must be a well-formed UI5Tree carrying @controlType (locale-independent).
    ${tree}=    Get Ui5 Page Tree
    Should Start With    ${tree}    <UI5Tree
    Should Contain       ${tree}    controlType="sap.m.SearchField"


*** Keywords ***
Open Demo Kit
    New Browser    chromium    headless=${HEADLESS}
    New Page       ${FIORI_BASE_URL}
    Wait For Function    () => !!(window.sap && sap.ui && sap.ui.require)    timeout=30s
