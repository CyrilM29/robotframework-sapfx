*** Settings ***
Documentation       Smoke non-destructif du **moteur sid** contre le SAP GUI for
...                 Spec: specs/webgui-smoke-sid.md (sha256:e820e827928b, 2026-08-04)
...                 HTML (WebGUI classique via ITS) de l'A4H, generated from
...                 specs/webgui-smoke-sid.md by sap-generator (re-run the
...                 generator rather than hand-editing locators here). Un test
...                 par scénario de la spec, dans son ordre : login ITS par le
...                 moteur dom, navigation `~transaction` vérifiée par sid,
...                 comptage T000 de bout en bout au moteur sid, déconnexion
...                 propre par le menu System. Assertions 100 %
...                 locale-indépendantes (SIDs, le même espace d'ids que le
...                 scripting SAP GUI desktop ; ids techniques de dynpro ;
...                 comptages d'éléments `lsdata` ; jamais un libellé localisé).
...                 Périmètre strictement consultation (SE16 T000 en affichage /
...                 comptage, log off). Exécution :
...
...                   robot --pythonpath src ^
...                     -v WEBGUI_URL:"http://vhcala4hci:50000/sap/bc/gui/sap/its/webgui?sap-client=001" ^
...                     -v SAP_USER:DEVELOPER -v "SAP_PASSWORD: Secret:***" ^
...                     --outputdir results/webgui tests/robot/webgui_smoke_sid.robot

Resource            ../../resources/fiori_keywords.resource

Suite Setup         Run Keywords    Open WebGui    ${WEBGUI_URL}
...                 AND             Log In To WebGui    ${SAP_USER}    ${SAP_PASSWORD}
Suite Teardown      Close WebGui

Test Tags           webgui    sid-engine


*** Variables ***
# Données métier et de connexion (valeurs, pas des ids SAP ; convention 1 :
# tous les localisateurs vivent dans resources/fiori_keywords.resource).
${WEBGUI_URL}               ${EMPTY}    # OBLIGATOIRE : -v WEBGUI_URL:"http://.../its/webgui?sap-client=NNN"
${SAP_USER}                 ${EMPTY}    # -v SAP_USER:DEVELOPER
${SAP_PASSWORD}             ${EMPTY}    # -v "SAP_PASSWORD: Secret:<motdepasse>" : jamais en clair, masqué même en TRACE
${COUNTED_TABLE}            T000        # table présente sur tout système SAP
${MIN_EXPECTED_CLIENTS}     2           # T000 contient au minimum les clients 000 et 001


*** Test Cases ***
Login ITS par le moteur dom
    [Documentation]    Scénario 1 : l'ouverture et le login vivent en Suite Setup
    ...    (l'auto-closing de la bibliothèque Browser refermerait une page ouverte
    ...    PENDANT un test) : `Open WebGui` garde la composition (moteurs sid+dom
    ...    recommandés sur la page de login), `Log In To WebGui` déroule le trio
    ...    dom (rôle + nom accessible) et garde « > 0 éléments lsdata ». Ce test
    ...    vérifie l'état connecté : du WebGUI rendu et le champ OK-code
    ...    adressable par SID (présent dans le DOM, masqué par défaut, donc
    ...    présence, pas visibilité).
    WebGui Should Be Rendered
    WebGui Ok Code Field Should Be Present

Lancement de SE16 par URL ~transaction et vérification par sid
    [Documentation]    Scénario 2 : navigation par le paramètre d'URL
    ...    `~transaction` (la voie déterministe : le champ OK-code est masqué par
    ...    défaut et le réglage « Show OK Code field » n'est pas persistant côté
    ...    serveur), atterrissage vérifié par SID (champ nom de table visible) et
    ...    par l'id technique du dynpro (`SAPLSETB`, jamais un libellé localisé).
    Go To WebGui Transaction    SE16
    WebGui Data Browser Should Be Open

Comptage T000 de bout en bout au moteur sid
    [Documentation]    Scénario 3, le cœur du smoke : nom de table, « Table
    ...    Contents », « Number of Entries », lecture du compteur du popup (SPAN
    ...    texte, normalisé chiffres seuls) et fermeture (plus aucun `wnd[1]`
    ...    visible), chaque étape résolue par SID. Non-destructif : consultation
    ...    et comptage seulement, jamais « Create Entries ».
    ${count}=    Count WebGui Table Entries    ${COUNTED_TABLE}
    Should Be True    ${count} >= ${MIN_EXPECTED_CLIENTS}
    ...    msg=${COUNTED_TABLE} devrait contenir au moins ${MIN_EXPECTED_CLIENTS} entrées (clients 000 et 001), lu : ${count}

Déconnexion propre par le menu System
    [Documentation]    Scénario 4 : bouton « More » du bandeau, menu System repéré
    ...    par POSITION RELATIVE (avant-dernier : la barre de menus varie par
    ...    transaction), dernier item (Log Off), confirmation SPOP par SID, puis
    ...    assertion de fin de session 100 % locale-indépendante : plus AUCUN
    ...    élément `lsdata` dans le document.
    Log Off WebGui
