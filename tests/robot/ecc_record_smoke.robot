*** Settings ***
Documentation       Live smoke for the **desktop Recorder's record engine** against a
...                 real ABAP Platform A4H. Drives a genuine flow via SapEccLibrary and
...                 checks the engine (`screen_signature` / `snapshot_fields` /
...                 `process_poll`) transcribes a typed selection field into an
...                 `Input Text` step plus its submit. Needs a reachable system +
...                 scripting enabled. (The OK-code -> `Run Transaction` path is covered
...                 by the off-SAP unit tests in tests/unit/test_desktop_spy.py.)
...
...                 The recorder lives under tools/ (not a package) — imported as a
...                 Library by path. SapEccLibrary is imported by the resource. Run e.g.:
...                   robot --pythonpath src ^
...                     -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER ^
...                     -v "SAP_PASSWORD: Secret:..." -v SAP_CLIENT:001 tests/robot/ecc_record_smoke.robot
...
...                 FR — Smoke live du **moteur record du Recorder bureau** contre un vrai
...                 A4H : pilote un déroulé via SapEccLibrary et vérifie que le moteur
...                 transcrit une saisie de champ en un step `Input Text` + sa soumission.

Library             ${CURDIR}/../../tools/recorder/sapgui_recorder.py    WITH NAME    Recorder
Resource            ../../resources/ecc_keywords.resource

Suite Setup         Open SAP And Log In
Suite Teardown      Close SAP


*** Test Cases ***
Recorder Transcribes A Typed Field Live
    [Documentation]    Sur SE16, saisie du nom de table puis Entrée (qui change l'écran)
    ...                -> le moteur record émet Input Text ...T000 + Send Vkey 0, lus
    ...                depuis la session COM live.
    ${engine}=    Recorder.Get Scripting Engine
    ${session}=   Recorder.First Session    ${engine}
    Go To Transaction    SE16

    ${state}=    Create Dictionary                                       # baseline sur l'écran SE16
    ${state}    ${steps}=    Poll Recorder    ${state}    ${session}
    Input Text    ${SE16_TABLE_FIELD}    T000
    ${state}    ${steps}=    Poll Recorder    ${state}    ${session}      # même écran, capture le champ
    Should Be Empty    ${steps}
    Send Vkey    0
    Wait Until Busy Done
    ${state}    ${steps}=    Poll Recorder    ${state}    ${session}      # frontière -> émission
    ${joined}=    Catenate    @{steps}
    Should Contain    ${joined}    Input Text
    Should Contain    ${joined}    ${SE16_TABLE_FIELD}
    Should Contain    ${joined}    T000
    Should Contain    ${joined}    Send Vkey


*** Keywords ***
Poll Recorder
    [Documentation]    Un tour du moteur record sur la session live : signature + snapshot
    ...                + okcode -> process_poll. Retourne (état, lignes émises).
    [Arguments]    ${state}    ${session}
    ${sig}=     Recorder.Screen Signature    ${session}
    ${snap}=    Recorder.Snapshot Fields    ${session}
    ${okcd}=    Recorder.Okcode Value    ${session}
    ${new}    ${steps}=    Recorder.Process Poll    ${state}    ${sig}    ${snap}    ${okcd}
    RETURN    ${new}    ${steps}
