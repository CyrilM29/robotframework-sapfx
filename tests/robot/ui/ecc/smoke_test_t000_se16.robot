*** Settings ***
Documentation       Smoke test système : consultation des mandants (T000) via SE16.
...                 Spec: specs/smoke-test-t000-se16.md (sha256:8e032b0823b5, 2026-09-21)
...                 Cible A4H (S/4HANA 1909, client 001) exclusivement.
...
...                 Test unique, strictement en lecture seule (SE16 en
...                 consultation, aucune écriture), rejouable à l'infini et
...                 nativement idempotent : le contenu de T000 ne varie pas
...                 d'un passage à l'autre sur ce système de laboratoire. Lit
...                 la grille de résultats SANS aucun critère de sélection
...                 (structurellement impossible d'en poser un sur MANDT :
...                 T000 n'expose aucun critère sur ce champ) et prouve sa
...                 COMPLÉTUDE (`Count Blank Grid Rows`), pas seulement son
...                 nombre de lignes : une ALV rend ses lignes non chargées en
...                 cellules vides plutôt que d'échouer, donc le compte de
...                 lignes seul ne distingue pas un relevé complet d'un
...                 relevé tronqué en silence.
...
...                 Localisateurs SE16 génériques dans
...                 `resources/ecc_keywords.resource` (convention 1).
...
...                 Exécution (A4H) :
...
...                 robot --pythonpath src --outputdir results/smoke_t000 ^
...                 -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER ^
...                 -v "SAP_PASSWORD: Secret:***" -v SAP_CLIENT:001 ^
...                 tests/robot/ui/ecc/smoke_test_t000_se16.robot

Resource            ../../../../resources/ecc_keywords.resource

Suite Setup         Open T000 Smoke Campaign
Suite Teardown      Close SAP

Test Tags           ecc    se16    smoke    read-only    a4h


*** Variables ***
${MIN_EXPECTED_CLIENTS}    2


*** Test Cases ***
La table des mandants répond avec au moins les mandants standard
    [Documentation]    Scénario 1 : la table T000 (mandants), consultée via
    ...    SE16 sans aucun filtre, rend au moins les deux mandants standard
    ...    de laboratoire (000 et 001), un relevé COMPLET (aucune ligne
    ...    entièrement vide) et une colonne technique MANDT renseignée sur
    ...    chaque ligne.
    Display Table Contents    T000
    ${rows}=    Read Full Displayed Grid
    ${row_count}=    Get Length    ${rows}
    Should Be True    ${row_count} >= ${MIN_EXPECTED_CLIENTS}
    ...    msg=T000 should list at least ${MIN_EXPECTED_CLIENTS} clients (000 and 001), got ${row_count}
    ${blank_rows}=    Count Blank Grid Rows    ${rows}
    Should Be Equal As Integers    ${blank_rows}    0
    ...    msg=T000 read is incomplete: ${blank_rows} fully blank row(s) in a grid announcing ${row_count} row(s)
    FOR    ${row}    IN    @{rows}
        Should Not Be Empty    ${row}[MANDT]
        ...    msg=A T000 row is missing its MANDT value: ${row}
    END


*** Keywords ***
Open T000 Smoke Campaign
    [Documentation]    Connexion et réglage persistant requis par toute
    ...    lecture SE16 en grille ALV (posé une fois par utilisateur,
    ...    constaté déjà actif sur ce poste, mais l'appel reste idempotent).
    Open SAP And Log In
    Use ALV Grid In Data Browser
