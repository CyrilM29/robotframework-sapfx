*** Settings ***
Documentation       Campagne exploratoire Fiori / UI5, pendant WEB de
...                 ``exploratory_campaign_a4h.robot`` (côté ECC/SAP GUI). Cette fois le
...                 **navigateur est visible** (Playwright, ``headless=False``).
...
...                 Pilotée par ``SapFioriLibrary``, qui ne conduit PAS la page elle-même :
...                 elle réutilise la page active de la librairie ``Browser`` (Playwright) et
...                 y injecte le bundle ``__SAPFX`` (moteurs de résolution portés de
...                 playwright-sap). Suite AUTO-SUFFISANTE : aucune resource ni suite
...                 existante du projet n'est importée.
...
...                 Cible par défaut : l'**OpenUI5 Demo Kit** public (``sdk.openui5.org``),
...                 aucun SAP, aucun login, aucun serveur local requis (donc pleinement
...                 ré-exécutable). ``${FIORI_URL}`` est surchargeable pour viser une autre
...                 app UI5 (p. ex. cap-sflight ``http://localhost:4004/…`` après
...                 ``npx cds watch``, ou un vrai Fiori Launchpad).
...
...                 Le Suite Setup accepte d'abord la bannière de consentement cookies du
...                 Demo Kit (widget TrustArc DOM, bouton d'id stable ``truste-consent-button``).
...
...                 Cinq scénarios en miroir de la campagne ECC, chacun relevé PUIS validé
...                 live (Chromium, 2026-07-17) :
...
...                 1. Inventaire des contrôles UI5 (arbre + cardinalité par type)
...                    ↔ inventaire des classes / tables côté ECC.
...                 2. Interaction vérifiée et RÉVERSIBLE (remplir un champ, relire, vider)
...                    ↔ cycle d'écriture CRUD réversible sur SCARR.
...                 3. Vérification EN PROFONDEUR sur un noyau de types : convergence des DEUX
...                    moteurs de localisation (role registre / xpath arbre + plus-court-xpath)
...                    ↔ tables curées via SE16.
...                 4. Vérification EN PROFONDEUR **dynamique** : découverte de TOUS les types
...                    de contrôles de l'arbre live, convergence des deux moteurs pour chacun,
...                    plus la grammaire de localisateurs (ancestralité + prédicat @controlType)
...                    ↔ balayage dynamique du catalogue TADIR.
...                 5. Échec explicite sur contrôle absent ↔ rejet SE16 de type E.
...
...                 Bonnes pratiques : adressage 100 % **locale-indépendant** par
...                 ``controlType`` (jamais par texte : le Demo Kit s'affiche dans la langue
...                 du navigateur) ; pas d'attente fixe (les moteurs de résolution *pollent*
...                 jusqu'au rendu) ; aucun sélecteur DOM brut dans les cas de test.
...
...                 Exécution (navigateur visible) :
...                 | robot --pythonpath src tests/robot/exploratory_campaign_fiori.robot
...                 Pour une CI sans affichage : | ... -v HEADLESS:True ...
...                 Prérequis : ``pip install -r requirements.txt`` puis ``rfbrowser init``.

Library             Browser
Library             SapFioriLibrary    ui5_timeout=15s
Library             Collections

Suite Setup         Open UI5 App In Browser
Suite Teardown      Close Browser


*** Variables ***
${FIORI_URL}        https://sdk.openui5.org/
${BROWSER}          chromium
${HEADLESS}         ${False}      # navigateur VISIBLE par défaut (demande explicite) ; -v HEADLESS:True en CI
${SEARCH_TEXT}      SapFioriLibrary rocks
# Bouton « Tout accepter » de la bannière de consentement TrustArc du Demo Kit : c'est un
# élément DOM (hors registre UI5), à l'id stable et locale-indépendant.
${COOKIE_ACCEPT_BUTTON}    css=#truste-consent-button

# Types de contrôles UI5 attendus sur la page cible (adressage locale-indépendant par
# controlType) relevés live dans l'arbre du Demo Kit. Sert d'inventaire de référence et
# de jeu de données pour la vérification en profondeur multi-moteurs.
@{EXPECTED_CONTROL_TYPES}
...    sap.m.SearchField    sap.m.Button    sap.m.Text
...    sap.ui.core.Icon     sap.m.Page      sap.m.Image


*** Test Cases ***
UI5 Runtime And Control Tree Are Available
    [Documentation]    Analyse de l'existant (pendant web de « Delivery Classes »). Le
    ...                runtime SAPUI5 est chargé et ``Get Ui5 Page Tree`` sérialise la
    ...                hiérarchie des contrôles en XML (la perception que consomme un agent).
    ...                L'arbre porte ``@controlType``, indépendant de la langue. On vérifie
    ...                qu'au moins une occurrence de chaque type attendu est rendue.
    [Tags]    exploration    ui5
    ${tree}=    Get Ui5 Page Tree
    Should Start With    ${tree}    <UI5Tree
    Should Contain       ${tree}    controlType="sap.m.SearchField"
    FOR    ${type}    IN    @{EXPECTED_CONTROL_TYPES}
        ${count}=    Get Ui5 Match Count    controlType=${type}
        Should Be True    ${count} >= 1
        ...    msg=Aucun contrôle de type ${type} rendu sur la page.
        Log    ${type} : ${count} contrôle(s)
    END

Search Field Accepts And Reflects Input
    [Documentation]    Interaction vérifiée et RÉVERSIBLE (pendant web du cycle d'écriture
    ...                ECC). On remplit le SearchField (le convenience keyword descend
    ...                jusqu'au ``<input>`` interne du contrôle composite), on relit la
    ...                valeur, puis on remet le champ à vide : aucun état laissé, test
    ...                ré-exécutable. La cible est adressée par type (locale-indépendant).
    [Tags]    interaction    ui5
    ${selector}=    Resolve Ui5 Control    controlType=SearchField
    Fill Ui5 Input    ${SEARCH_TEXT}    controlType=SearchField
    Get Property    ${selector} input    value    ==    ${SEARCH_TEXT}
    # Remise à zéro : le champ repart vide (aucun effet de bord entre deux exécutions).
    Fill Ui5 Input    ${EMPTY}    controlType=SearchField
    Get Property    ${selector} input    value    ==    ${EMPTY}

Core Controls Resolve Consistently Across Engines
    [Documentation]    Vérification EN PROFONDEUR (pendant web de « Flight Data Tables »).
    ...                Data-driven : pour chaque type de contrôle, les DEUX moteurs de
    ...                localisation portés de playwright-sap CONVERGENT : le moteur ``role``
    ...                (scan du registre) et le moteur ``xpath`` (arbre hiérarchique)
    ...                désignent le même élément, et le *plus court xpath unique* re-résout
    ...                vers ce même contrôle. Un verdict par type dans le rapport.
    [Tags]    verification    ui5    deep
    [Template]    Control Should Resolve Consistently
    sap.m.SearchField
    sap.m.Button
    sap.m.Text
    sap.ui.core.Icon
    sap.m.Page
    sap.m.Image

Missing Control Fails Clearly
    [Documentation]    Les deux moteurs échouent bruyamment sur l'absence de correspondance,
    ...                jamais en silence (pendant web du rejet SE16 de type E). On combine un
    ...                type existant avec une propriété impossible (moteur role) et un tag
    ...                inexistant (moteur xpath).
    [Tags]    verification    ui5
    Run Keyword And Expect Error    *No UI5 control matched*
    ...    Resolve Ui5 Control    controlType=sap.m.Button    properties={'text': 'ZZZ_DOES_NOT_EXIST_QA'}
    Run Keyword And Expect Error    *No UI5 control matched*
    ...    Resolve Ui5 By Xpath    //ZzzNoSuchControl_QA

Full Control Type Catalog Resolves Consistently
    [Documentation]    Vérification EN PROFONDEUR **dynamique** (pendant web du balayage TADIR
    ...                côté ECC). Plutôt qu'une liste figée, on DÉCOUVRE à l'exécution tous les
    ...                types de contrôles présents dans l'arbre UI5 live, puis on vérifie que
    ...                CHACUN converge entre les deux moteurs (``role`` registre == ``xpath``
    ...                arbre, via le plus-court-xpath). Un récapitulatif est journalisé ; le
    ...                test échoue en nommant tout type qui divergerait.
    [Tags]    verification    ui5    deep
    ${tree}=    Get Ui5 Page Tree
    ${types}=    Evaluate    sorted(set(re.findall('controlType="([^"]+)"', $tree)))    modules=re
    ${discovered}=    Get Length    ${types}
    Should Be True    ${discovered} >= 10
    ...    msg=Trop peu de types de contrôles découverts (${discovered}) : l'app a-t-elle rendu ?
    ${convergent}=    Set Variable    ${0}
    @{divergent}=    Create List
    FOR    ${type}    IN    @{types}
        ${ok}=    Control Converges Across Engines    ${type}
        IF    ${ok}
            ${convergent}=    Evaluate    ${convergent} + 1
        ELSE
            Append To List    ${divergent}    ${type}
        END
    END
    Log    Balayage dynamique : ${convergent}/${discovered} types convergent (role == xpath). Divergents : ${divergent}
    Should Be Empty    ${divergent}
    ...    msg=Types NON convergents entre moteurs (sur ${discovered} découverts) : ${divergent}

Locator Grammar Supports Hierarchy And Attribute Predicates
    [Documentation]    Vérification EN PROFONDEUR de la **grammaire de localisateurs** du
    ...                moteur xpath (porté de playwright-sap) : au-delà du type seul, on
    ...                exprime l'ancestralité (``//Parent//Enfant``) et un prédicat d'attribut
    ...                (``@controlType``, toujours présent donc locale-indépendant). Les deux
    ...                formes doivent converger vers EXACTEMENT le contrôle rendu par le
    ...                moteur ``role``.
    [Tags]    verification    ui5    deep
    ${by_role}=    Resolve Ui5 Control    controlType=sap.m.SearchField
    ${by_hierarchy}=    Resolve Ui5 By Xpath    //Page//SearchField
    Should Be Equal    ${by_role}    ${by_hierarchy}
    ...    msg=L'xpath hiérarchique //Page//SearchField ne cible pas le même contrôle que le moteur role.
    ${by_predicate}=    Resolve Ui5 By Xpath    //*[@controlType='sap.m.SearchField']
    Should Be Equal    ${by_role}    ${by_predicate}
    ...    msg=Le prédicat @controlType ne cible pas le même contrôle que le moteur role.


*** Keywords ***
Open UI5 App In Browser
    [Documentation]    Suite Setup. Ouvre un navigateur (VISIBLE par défaut, ``${HEADLESS}``
    ...                = False) sur l'app UI5 cible et attend que le runtime SAPUI5 soit
    ...                chargé (``window.sap.ui.require`` présent). Pendant web de
    ...                ``Open SAP And Log In``.
    New Browser    ${BROWSER}    headless=${HEADLESS}
    New Page       ${FIORI_URL}
    Wait For Function    () => !!(window.sap && sap.ui && sap.ui.require)    timeout=30s
    Accept Cookies
    # Le runtime chargé ne signifie pas l'app rendue : la SDK monte son composant de
    # façon asynchrone. On attend qu'un contrôle stable soit réellement rendu (le moteur
    # role polle jusqu'au rendu) avant de rendre la main aux tests, sinon la première
    # perception (`Get Ui5 Page Tree`) capterait un arbre encore incomplet.
    Ui5 Control Should Be Visible    controlType=SearchField

Control Should Resolve Consistently
    [Documentation]    Verdict data-driven pour un type de contrôle : (1) au moins une
    ...                occurrence rendue, (2) le moteur ``role`` renvoie un sélecteur CSS,
    ...                (3) le *plus court xpath unique* est bien un xpath, (4) le moteur
    ...                ``xpath`` re-résout ce plus court xpath vers EXACTEMENT le même
    ...                sélecteur que le moteur ``role`` : les deux moteurs convergent.
    [Arguments]    ${control_type}
    ${count}=    Get Ui5 Match Count    controlType=${control_type}
    Should Be True    ${count} >= 1
    ...    msg=Aucun contrôle de type ${control_type} rendu.
    ${by_role}=    Resolve Ui5 Control    controlType=${control_type}
    Should Start With    ${by_role}    css=
    ${shortest}=    Get Ui5 Xpath    controlType=${control_type}
    Should Start With    ${shortest}    //
    ${by_xpath}=    Resolve Ui5 By Xpath    ${shortest}
    Should Be Equal    ${by_role}    ${by_xpath}
    ...    msg=Les moteurs role et xpath divergent pour ${control_type} : ${by_role} vs ${by_xpath}
    Log    ${control_type} : ${count} rendu(s), sélecteur ${by_role}, xpath ${shortest}

Accept Cookies
    [Documentation]    La bannière de consentement du Demo Kit est un widget TrustArc **DOM**
    ...                (hors registre UI5), au bouton « Tout accepter » d'id stable
    ...                ``truste-consent-button`` (locale-indépendant). On l'accepte si elle
    ...                apparaît dans le délai imparti ; sinon on ne fait rien (consentement
    ...                déjà mémorisé, ou bannière absente) : le keyword reste sûr en
    ...                ré-exécution et hors ligne.
    ${shown}=    Run Keyword And Return Status
    ...    Wait For Elements State    ${COOKIE_ACCEPT_BUTTON}    visible    timeout=8s
    IF    ${shown}
        Click    ${COOKIE_ACCEPT_BUTTON}
        # Le bouton est retiré du DOM après acceptation ; attente best-effort, jamais bloquante.
        Run Keyword And Ignore Error
        ...    Wait For Elements State    ${COOKIE_ACCEPT_BUTTON}    detached    timeout=5s
    END

Control Converges Across Engines
    [Documentation]    Renvoie un booléen : le type ``${control_type}`` converge-t-il entre les
    ...                deux moteurs ? Garde-fou par ``Get Ui5 Match Count`` (qui n'attend pas) :
    ...                un type disparu depuis le snapshot de l'arbre (0 correspondance) renvoie
    ...                ``False`` sans déclencher de résolution lente. Utilisé par le balayage
    ...                dynamique du catalogue de contrôles.
    [Arguments]    ${control_type}
    ${count}=    Get Ui5 Match Count    controlType=${control_type}
    IF    ${count} == 0    RETURN    ${False}
    ${by_role}=    Resolve Ui5 Control    controlType=${control_type}
    ${shortest}=    Get Ui5 Xpath    controlType=${control_type}
    ${by_xpath}=    Resolve Ui5 By Xpath    ${shortest}
    ${converges}=    Evaluate    $by_role == $by_xpath
    RETURN    ${converges}
