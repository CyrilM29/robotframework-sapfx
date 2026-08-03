*** Settings ***
Documentation       Smoke **authentification IDP** : exerce `Log In Via Identity
...                 Provider` contre ``fixtures/idp_login_fixture.html`` — un IDP
...                 factice au déroulé DEUX ÉTAPES (utilisateur → Suivant → mot
...                 de passe → connexion, le cas Azure AD) portant les ids du
...                 preset ``sap-ias`` (#j_username / #j_password /
...                 #logOnFormSubmit) : la branche difficile du keyword ET la
...                 fiche IAS sont couvertes d'un coup. Vérifie le succès (on
...                 atterrit dans l'app UI5, la résolution role fonctionne),
...                 l'échec explicite sur mauvais mot de passe (« toujours sur
...                 le formulaire »), et le refus d'un preset inconnu (liste
...                 des presets valides). Réseau (CDN UI5 pour l'app cible),
...                 aucun SAP, aucun IDP réel.
...                 Exécution :  robot --pythonpath src tests/robot/fiori_auth_smoke.robot

Library             OperatingSystem
Library             Browser
Library             SapFioriLibrary    ui5_timeout=60s

Suite Setup         New Browser    chromium    headless=${HEADLESS}
Suite Teardown      Close Browser


*** Variables ***
${HEADLESS}         ${True}
# Identifiants du FAUX IDP embarqué dans la fixture — publics par nature.
${IDP_USER}         TESTER
${IDP_PASSWORD}     s3cret


*** Keywords ***
Open Idp Fixture
    ${fixture}=    Normalize Path    ${CURDIR}/fixtures/idp_login_fixture.html
    ${url}=        Evaluate    pathlib.Path(r"${fixture}").as_uri()    pathlib
    Set Browser Timeout    120s
    New Page       ${url}    wait_until=domcontentloaded


*** Test Cases ***
Two Step Idp Login Lands In The Application
    [Documentation]    Déroulé complet : utilisateur → Suivant → mot de passe →
    ...                connexion → redirection vers l'app UI5, où la
    ...                résolution role fonctionne (preuve d'atterrissage).
    Open Idp Fixture
    Log In Via Identity Provider    ${IDP_USER}    ${IDP_PASSWORD}    preset=sap-ias
    Ui5 Control Should Be Visible    controlType=sap.m.Button    properties={'text': 'Open Dialog'}

Wrong Password Fails Naming The Idp Form
    [Documentation]    Identifiants refusés = le formulaire reste affiché : le
    ...                keyword doit échouer TÔT en le disant (pas un timeout
    ...                muet en aval dans l'app).
    Open Idp Fixture
    Run Keyword And Expect Error    *Toujours sur le formulaire IDP*
    ...    Log In Via Identity Provider    ${IDP_USER}    mauvais-mdp    preset=sap-ias    timeout=5s

Unknown Preset Is Refused With The Valid List
    [Documentation]    Jamais de repli silencieux vers ``generic`` : un preset
    ...                inconnu échoue immédiatement en listant les presets.
    Open Idp Fixture
    Run Keyword And Expect Error    *Preset IDP inconnu*
    ...    Log In Via Identity Provider    ${IDP_USER}    ${IDP_PASSWORD}    preset=okta
