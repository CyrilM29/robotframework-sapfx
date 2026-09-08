*** Settings ***
Documentation       Reconnaissance de couverture sur une SECONDE release : ce que
...                 Spec: specs/reconnaissance-couverture-sapgui-abap2023.md (sha256:5aaad4fa0f0f, 2026-09-08)
...                 SapEccLibrary ne sait pas faire sur ABAP Platform 2023
...                 (SAP_BASIS 758, kernel 793). Generated from
...                 specs/reconnaissance-couverture-sapgui-abap2023.md by
...                 sap-generator (re-run the generator rather than hand-editing
...                 locators here). Un test par scénario du plan, dans son ordre.
...
...                 Ce n'est PAS un test métier : chaque scénario exerce UNE capacité
...                 de la bibliothèque sur l'écran réel de CETTE release et consigne
...                 un verdict `gap` / `covered` / `poste` / `hors_api` dans un
...                 registre JSON déterministe. Le verdict est DÉRIVÉ de l'observation,
...                 puis confronté à celui du plan : le scénario échoue dans les deux
...                 sens (manque comblé OU capacité perdue) en nommant « mettre à jour
...                 le plan et le registre ». Elle ne répète pas la campagne 754 : elle
...                 mesure ce qu'une campagne mono-release ne PEUT pas voir, à savoir
...                 la constante de release déguisée en fait, l'assertion dépendante de
...                 la locale faute d'identifiant de message, les familles de contrôles
...                 non traversées (onglets, barre d'application) et l'équivalence
...                 MESURÉE là où la 754 et la 758 convergent.
...
...                 Invariant de la campagne : aucun manque n'est contourné, ni ici ni
...                 dans le page object (pas de JS, pas d'`Evaluate` sur un objet COM,
...                 pas de helper Python local). Un keyword manquant se prouve par
...                 `Un Keyword Devrait Etre Absent`, un keyword cassé s'appelle sous
...                 filet et son échec s'asserte.
...
...                 Assertions locale-safe : types de message (`E`), types de contrôles
...                 (`GuiTabStrip`, `GuiSplitterShell/Splitter`, `GuiShell/GridView`),
...                 ids techniques de colonnes (`MANDT`, `HierarchyHeader`), sous-types
...                 de shell (`AbapEditor`), positions de menu DÉRIVÉES et release /
...                 kernel (`758` / `793`). Les textes localisés (chemin du menu
...                 System, nom des entrées, libellé du bouton SPRO) vivent dans le
...                 page object
...                 `resources/page_objects/sapgui_capability_probes_2023.resource`
...                 (convention 1 : zéro localisateur ici ; convention 3), et le
...                 vocabulaire de verdict dans
...                 `resources/page_objects/capability_register.resource`, partagé avec
...                 la campagne 754.
...
...                 LECTURE SEULE : aucune exécution qui écrit, aucune donnée créée ;
...                 les seules valeurs posées le sont dans « Table Name » de l'écran
...                 initial SE16, jamais persistant. Le seul réglage persistant touché
...                 est la sortie du Data Browser (`Use ALV Grid In Data Browser` en
...                 Suite Setup, ce que toutes les suites SE16 posent). La session est
...                 refermée par le Suite Teardown MÊME SUR ÉCHEC, après l'écriture du
...                 registre.
...
...                 Le registre est écrit dans `${REGISTER_2023_PATH}` (défaut :
...                 `${OUTPUT DIR}/ecc_capability_register_2023.json`) par le scénario
...                 10 ET par le Suite Teardown ; il porte l'identité de la cible
...                 MESURÉE À LA MAIN en Suite Setup (SID, mandant, utilisateur,
...                 release SAP_BASIS, kernel), hors empreinte : par le chemin de
...                 textes et non par `Get System Identity`, pour que le scénario 1
...                 confronte le keyword à une mesure indépendante de lui (au matin
...                 du 2026-09-08, c'était aussi son manque).
...
...                 Trois scénarios (2, 4, 5) s'appuient AUSSI sur un fait de CIBLE
...                 (position 10 de « Status... », douze onglets SU01, cinq boutons
...                 de barre) : il est asserté HORS du verdict, après sa consignation,
...                 pour qu'une autre release rougisse en nommant le fait de cible
...                 sans qu'un verdict de bibliothèque en soit faussé.
...
...                 Exécution :
...
...                 robot --pythonpath src --outputdir results/reco_2023 ^
...                 -v SAP_CONNECTION:/H/vhcala4hci/S/3201 -v SAP_USER:DEVELOPER ^
...                 -v "SAP_PASSWORD: Secret:..." -v SAP_CLIENT:001 -v SAP_LANGUAGE:EN ^
...                 tests/robot/ui/ecc/reconnaissance_couverture_sapgui_2023.robot

Resource            ../../../../resources/page_objects/sapgui_capability_probes_2023.resource

Suite Setup         Ouvrir La Campagne De Reconnaissance 758
Suite Teardown      Clore La Campagne De Reconnaissance 758
Test Teardown       Revenir Au Menu

Test Tags           ecc    capability    abap2023


*** Variables ***
# Les verdicts ATTENDUS par le plan, capacité par capacité : la copie de la table
# « Clés de registre » du plan (scénarios 1 à 9), à differ avec elle. Plusieurs
# verdicts admis se sépareraient par `|` (aucun cas aujourd'hui).
&{PLANNED_VERDICTS}
...    identity.unavailable_on_release=covered
...    menu.status_entry_position=covered
...    statusbar.message_identity=covered
...    tabstrip.select_and_read=covered
...    toolbar.application_inventory=covered
...    tree.container_refuses_actionably=covered
...    grid.splitter_wrapped=covered
...    editor.get_value_refuses=covered
...    identity.not_in_session_info=hors_api


*** Test Cases ***
L'identité du système se lit sur cette release
    [Documentation]    Scénario 1 : `Get System Identity` RÉSOUT l'entrée « Status... »
    ...                (avant-dernière entrée de l'avant-dernier menu, dialogue exigé)
    ...                et rend la même identité que la mesure manuelle du Suite Setup :
    ...                release 758, kernel 793, rien de non lu, aucun modal résiduel.
    Ouvrir L Ecran    SE16
    ${identite}=    Identite Par Keyword
    ${fenetres}=    Get Open Windows
    ${sans_modal}=    Run Keyword And Return Status    Aucune Fenetre Modale Ne Devrait Etre Ouverte    ${fenetres}
    ${egale}=    Run Keyword And Return Status    L Identite Par Keyword Devrait Egaler La Mesure Manuelle    ${identite}    ${CAPABILITY_TARGET}
    ${release}=    Run Keyword And Return Status    L Identite Devrait Etre Celle De Cette Release    ${identite}
    ${verdict}=    Verdict De Capacite    ${egale} and ${release} and ${sans_modal}
    Consigner Le Verdict    identity.unavailable_on_release    ${verdict}
    ...    Get System Identity : ${identite}[system_id]/${identite}[client] SAP_BASIS ${identite}[basis_release] SP ${identite}[basis_sp_level], kernel ${identite}[kernel_release] PL ${identite}[kernel_patch_level], non lu : ${identite}[unread] ; égale à la mesure manuelle : ${egale} ; aucun modal résiduel : ${sans_modal}
    Le Verdict Devrait Etre    identity.unavailable_on_release    covered

L'entrée System > Status est résolue sur chaque écran
    [Documentation]    Scénario 2 : sur les six écrans sondés, le menu System est
    ...                l'avant-dernier menu de tête et « Status... » son avant-dernière
    ...                entrée ; `Open System Status` la RÉSOUT sur chacun (l'entrée
    ...                qu'il a cliquée est celle que le relevé par texte désigne),
    ...                dialogue vérifié puis refermé, sans jamais toucher « Log Off ».
    ...                La position 10 (11 sur la 754) est un fait de cible, asserté
    ...                HORS verdict.
    ${coherent}=    Set Variable    ${True}
    @{releves}=    Create List
    @{entrees}=    Create List
    FOR    ${ecran}    IN    @{PROBED_SCREENS}
        Ouvrir L Ecran    ${ecran}
        ${releve}=    Positions Du Menu System    ${ecran}
        Append To List    ${releves}    ${releve}
        ${ok}=    Run Keyword And Return Status    Le Releve De Menu Devrait Etre Coherent    ${releve}
        ${st}    ${entree}=    Run Keyword And Ignore Error    Ouvrir Puis Refermer Le Statut Par Keyword
        Append To List    ${entrees}    ${entree}
        ${resolu}=    Run Keyword And Return Status    Run Keywords
        ...    Should Be Equal    ${st}    PASS
        ...    AND    L Entree Resolue Devrait Etre Celle Du Texte    ${entree}    ${releve}
        ${coherent}=    Evaluate    ${coherent} and ${ok} and ${resolu}
    END
    ${fenetres}=    Get Open Windows
    ${sans_modal}=    Run Keyword And Return Status    Aucune Fenetre Modale Ne Devrait Etre Ouverte    ${fenetres}
    ${verdict}=    Verdict De Capacite    ${coherent} and ${sans_modal}
    Consigner Le Verdict    menu.status_entry_position    ${verdict}
    ...    ${releves} ; entrées cliquées par Open System Status : ${entrees} (résolues et refermées sur chaque écran : ${coherent}) ; aucun modal résiduel : ${sans_modal}
    Le Verdict Devrait Etre    menu.status_entry_position    covered
    FOR    ${releve}    IN    @{releves}
        La Position Mesuree Devrait Etre Celle De Cette Release    ${releve}
    END

Un refus applicatif s'identifie par sa classe et son numéro
    [Documentation]    Scénario 3 : deux refus SE16 différents, même type `E`, même
    ...                classe `MO`, numéros DIFFÉRENTS rendus par `Get Status Message
    ...                Identity` (`MO/E/402`, `MO/E/410`) ; `Status Message Should Be`
    ...                passe sur la bonne identité et ÉCHOUE sur l'autre : deux refus
    ...                du même écran sont discernables sans un mot de texte localisé.
    ${identite1}=    Identite Du Refus SE16    ${SE16_ABSENT_TABLE}
    ${ok1}=    Run Keyword And Return Status    Le Refus Devrait Avoir L Identite    ${identite1}    ${MESSAGE_NUMBER_ABSENT_TABLE}
    ${st1}    ${refus1}=    Run Keyword And Ignore Error    L Autre Identite Devrait Etre Refusee    ${MESSAGE_NUMBER_EMPTY_NAME}
    ${identite2}=    Identite Du Refus SE16    ${EMPTY}
    ${ok2}=    Run Keyword And Return Status    Le Refus Devrait Avoir L Identite    ${identite2}    ${MESSAGE_NUMBER_EMPTY_NAME}
    ${st2}    ${refus2}=    Run Keyword And Ignore Error    L Autre Identite Devrait Etre Refusee    ${MESSAGE_NUMBER_ABSENT_TABLE}
    ${discernables}=    Run Keyword And Return Status    Run Keywords
    ...    Should Be Equal    ${identite1}[type]    ${identite2}[type]
    ...    AND    Should Not Be Equal    ${identite1}[identity]    ${identite2}[identity]
    ...    AND    Should Be Equal    ${st1}    PASS
    ...    AND    Should Be Equal    ${st2}    PASS
    ${verdict}=    Verdict De Capacite    ${ok1} and ${ok2} and ${discernables}
    Consigner Le Verdict    statusbar.message_identity    ${verdict}
    ...    Refus 1 : ${identite1}[identity] ; refus 2 : ${identite2}[identity] ; même type, identités distinctes, l'autre identité refusée en nommant l'attendu et le lu : ${discernables}
    Le Verdict Devrait Etre    statusbar.message_identity    covered

Un onglet se choisit et se lit par keyword
    [Documentation]    Scénario 4 : SU01 en affichage ; `List Tabs` rend une liste
    ...                lisible (id, clé, libellé, un seul actif), `Get Selected
    ...                Tab` l'onglet actif, `Select Tab` par CLÉ et `Select Tab By
    ...                Label` par libellé changent l'onglet actif (vérifié), le
    ...                sous-écran de l'onglet choisi existe, l'onglet initial est
    ...                restauré par sa clé et relu. Les douze onglets de cette
    ...                release (dont la clé nouvelle) sont un fait de cible, asserté
    ...                HORS verdict.
    Afficher L Utilisateur    ${SAP_USER}
    ${onglets}=    Les Onglets Par Keyword
    ${forme}=    Run Keyword And Return Status    Les Onglets Devraient Etre Lisibles    ${onglets}
    ${initial}=    Onglet Actif
    ${par_cle}=    Activer L Onglet Par Cle    ${SU01_DEFAULTS_TAB_ID}
    ${sous_ecran}=    Sous Ecran De L Onglet Defaults
    ${relu}=    Onglet Actif
    ${retour}=    Activer L Onglet Par Cle    ${initial}
    ${par_libelle}=    Activer L Onglet Par Libelle    ${SU01_DEFAULTS_TAB_LABEL}
    ${restaure}=    Activer L Onglet Par Cle    ${initial}
    ${ok}=    Run Keyword And Return Status    Run Keywords
    ...    Should Be Equal    ${par_cle}    ${SU01_DEFAULTS_TAB_ID}
    ...    AND    Should Be Equal    ${relu}    ${SU01_DEFAULTS_TAB_ID}
    ...    AND    Should Not Be Empty    ${sous_ecran}
    ...    AND    Should Be Equal    ${retour}    ${initial}
    ...    AND    Should Be Equal    ${par_libelle}    ${SU01_DEFAULTS_TAB_ID}
    ...    AND    Should Be Equal    ${restaure}    ${initial}
    ...    AND    Should Not Be Equal    ${initial}    ${SU01_DEFAULTS_TAB_ID}
    ${verdict}=    Verdict De Capacite    ${forme} and ${ok}
    Consigner Le Verdict    tabstrip.select_and_read    ${verdict}
    ...    ${onglets.__len__()} onglets listés ; actif à l'arrivée '${initial}', par clé -> '${par_cle}' (relu '${relu}', sous-écran rendu), par libellé -> '${par_libelle}', restauré '${restaure}'
    Le Verdict Devrait Etre    tabstrip.select_and_read    covered
    Les Onglets Devraient Etre Ceux De Cette Release    ${onglets}

La barre d'application s'inventorie et se clique
    [Documentation]    Scénario 5 : sur l'écran de sélection SE16, `List Toolbar
    ...                Buttons` inventorie les boutons (id, icône, tooltip) dont celui
    ...                du comptage (précondition du clic), et `Click Application
    ...                Toolbar Button` par segment d'id ouvre le popup « Number of
    ...                Entries », dont le compteur est un entier positif ; popup
    ...                refermé. Les cinq boutons de cette release sont un fait de
    ...                cible, asserté HORS verdict.
    Ouvrir L Ecran De Selection SE16
    ${boutons}=    Inventaire De La Barre D Application
    ${inventaire}=    Run Keyword And Return Status    L Inventaire Devrait Etre Lisible    ${boutons}
    L Inventaire Devrait Porter Le Compteur    ${boutons}
    ${nombre}=    Compter Par La Barre D Application
    ${fenetres}=    Get Open Windows
    ${sans_modal}=    Run Keyword And Return Status    Aucune Fenetre Modale Ne Devrait Etre Ouverte    ${fenetres}
    ${compte}=    Run Keyword And Return Status    Should Be True    ${nombre} > 0
    ${verdict}=    Verdict De Capacite    ${inventaire} and ${compte} and ${sans_modal}
    Consigner Le Verdict    toolbar.application_inventory    ${verdict}
    ...    ${boutons.__len__()} bouton(s) inventorié(s) : ${boutons} ; clic sur le comptage -> ${nombre} entrée(s) ; popup refermé : ${sans_modal}
    Le Verdict Devrait Etre    toolbar.application_inventory    covered
    La Barre Devrait Avoir Les Boutons De Cette Release    ${boutons}

Deux lecteurs de contrôle, un même refus actionnable
    [Documentation]    Scénario 6 : visé sur le CONTENEUR de l'arbre de l'IMG,
    ...                `Read Tree Nodes` DESCEND et rend les MÊMES nœuds que la lecture
    ...                directe de l'arbre (en WARNING), `Read
    ...                Grid` et `Get Grid Column Ids` ÉCHOUENT en nommant le contrôle,
    ...                la profondeur explorée et le remède ; visé sur l'arbre, `Read
    ...                Grid` refuse en nommant `GuiShell/Tree` et `Read Tree Nodes`.
    Ouvrir L IMG De Reference
    ${noeuds}=    Lire Les Noeuds De L IMG
    ${lus}=    Run Keyword And Return Status    Should Not Be Empty    ${noeuds}
    ${st_arbre}    ${via_conteneur}=    Run Keyword And Ignore Error    Tenter Read Tree Nodes Sur Le Conteneur
    ${descendu}=    Run Keyword And Return Status    Run Keywords
    ...    Should Be Equal    ${st_arbre}    PASS
    ...    AND    Should Not Be Empty    ${via_conteneur}
    ...    AND    Should Be Equal    ${via_conteneur}    ${noeuds}
    ${st_grille}    ${msg_grille}=    Run Keyword And Ignore Error    Tenter Read Grid Sur Le Conteneur
    ${grille_nomme}=    L Echec Devrait Etre Reproduit    tree.container_refuses_actionably
    ...    ${st_grille}    ${msg_grille}    *n'est pas une grille ALV*niveaux explorés*Get Screen Signature*
    ${st_colonnes}    ${msg_colonnes}=    Run Keyword And Ignore Error    Colonnes Vues Par Le Resolveur De Grille
    ${colonnes_nomme}=    L Echec Devrait Etre Reproduit    tree.container_refuses_actionably
    ...    ${st_colonnes}    ${msg_colonnes}    *aucune grille n'a été trouvée en dessous*
    ${st_direct}    ${msg_direct}=    Run Keyword And Ignore Error    Tenter Read Grid Sur L Arbre
    ${direct_nomme}=    L Echec Devrait Etre Reproduit    tree.container_refuses_actionably
    ...    ${st_direct}    ${msg_direct}    *GuiShell/Tree*Read Tree Nodes*
    ${verdict}=    Verdict De Capacite    ${lus} and ${descendu} and ${grille_nomme} and ${colonnes_nomme} and ${direct_nomme}
    Consigner Le Verdict    tree.container_refuses_actionably    ${verdict}
    ...    Arbre visé juste : ${noeuds.__len__()} nœud(s) ; conteneur par Read Tree Nodes : ${st_arbre} (descente) ; par Read Grid : ${msg_grille} ; Get Grid Column Ids sur le conteneur : ${msg_colonnes} ; Read Grid sur l'arbre : ${msg_direct}
    Le Verdict Devrait Etre    tree.container_refuses_actionably    covered

La grille enveloppée dans un splitter se lit quand même
    [Documentation]    Scénario 7, témoin COUVERT : le localisateur de grille SE16 de
    ...                la couche resources porte un `GuiSplitterShell/Splitter` sur
    ...                cette release et la grille vit un niveau plus bas ; les
    ...                keywords de grille descendent jusqu'au contrôle et rendent ses
    ...                colonnes techniques et ses lignes. Équivalence MESURÉE avec la
    ...                754, pas supposée.
    Afficher T000 En Grille
    ${id}=    Localisateur De Grille SE16
    ${type_conteneur}=    Sous Type Percu    ${id}
    ${type_grille}=    Sous Type Percu    ${SE16_GRID_INNER}
    ${colonnes}=    Colonnes De La Grille SE16
    ${lignes}=    Lire La Grille SE16    5
    ${ok}=    Run Keyword And Return Status    Run Keywords
    ...    Should Be Equal    ${type_conteneur}    ${SE16_GRID_SPLITTER_TYPE}
    ...    AND    Should Be Equal    ${type_grille}    ${SE16_GRID_INNER_TYPE}
    ...    AND    List Should Contain Value    ${colonnes}    ${SE16_FIRST_COLUMN}
    ...    AND    La Grille Devrait Porter Le Mandant De Reference    ${lignes}
    ${verdict}=    Verdict De Capacite    ${ok}
    Consigner Le Verdict    grid.splitter_wrapped    ${verdict}
    ...    Localisateur historique perçu ${type_conteneur}, grille réelle ${type_grille} ; ${colonnes.__len__()} colonne(s) techniques, ${lignes.__len__()} ligne(s) lue(s)
    Le Verdict Devrait Etre    grid.splitter_wrapped    covered

L'éditeur ABAP reste hors API sur cette release
    [Documentation]    Scénario 8, témoin COUVERT : SE38 en affichage ; le préflight
    ...                de rendu relève le sous-type `AbapEditor` et ne réclame aucun
    ...                mode accessibilité, et `Get Value` REFUSE en nommant le ProgID
    ...                et le sous-type. Le refus EST la capacité : le source d'un
    ...                éditeur est hors API Scripting.
    Afficher Le Programme    ${SE38_PROBE_PROGRAM}
    ${statut}=    Statut De Rendu De L Ecran
    ${reconnu}=    Run Keyword And Return Status    Le Prefight De Liste Devrait Reconnaitre Le Sous Type
    ...    ${statut}    ${SE38_EDITOR_SUBTYPE}
    ${status}    ${message}=    Run Keyword And Ignore Error    Tenter De Lire Le Controle Editeur
    ${refuse}=    L Echec Devrait Etre Reproduit    editor.get_value_refuses    ${status}    ${message}
    ...    *ProgID*GuiShell/AbapEditor*
    ${verdict}=    Verdict De Capacite    ${reconnu} and ${refuse}
    Consigner Le Verdict    editor.get_value_refuses    ${verdict}
    ...    Sous-types ${statut}[shell_subtypes], accessibilité ${statut}[accessibility_mode_needed] ; Get Value : ${message}
    Le Verdict Devrait Etre    editor.get_value_refuses    covered

La release n'est pas dans la session
    [Documentation]    Scénario 9, témoin HORS API : les deux lectures de la session
    ...                exposées par un keyword rendent bien le système, le mandant et
    ...                l'utilisateur, et NI release NI kernel ; la sonde COM de
    ...                `session.Info` qui fonde le verdict (vingt et une propriétés
    ...                lisibles, aucune release ni kernel) est conservée dans les
    ...                preuves du plan. Le dialogue System > Status est donc la seule
    ...                voie côté SAP GUI, et le détour du scénario 1 est justifié.
    Ouvrir L Accueil
    ${entree}=    Entree De Session Active
    ${telemetrie}=    Telemetrie De Session
    ${ok}=    Run Keyword And Return Status    La Session Devrait Nommer Son Identite Sans Sa Release
    ...    ${entree}    ${telemetrie}
    ${cles_session}=    Cles Triees De    ${entree}
    ${cles_telemetrie}=    Cles Triees De    ${telemetrie}
    ${verdict}=    Verdict Hors Api    ${ok}
    Consigner Le Verdict    identity.not_in_session_info    ${verdict}
    ...    Vue de session ${entree}[system]/${entree}[client]/${entree}[user], clés ${cles_session} ; télémétrie, clés ${cles_telemetrie} (valeurs volontairement hors registre : ce sont des mesures de run) ; aucune release ni kernel ; la sonde COM de session.Info est conservée dans ${SESSION_INFO_EVIDENCE} (clé hors_api_measure)
    Le Verdict Devrait Etre    identity.not_in_session_info    hors_api

Le registre est écrit, déterministe, et conforme au plan
    [Documentation]    Scénario 10 : le registre est écrit par l'artefact déterministe
    ...                générique, relu avec son empreinte RECALCULÉE, porte exactement
    ...                les neuf capacités des scénarios 1 à 9 avec les verdicts admis
    ...                par le plan, et nomme sa cible par sa release SAP_BASIS et son
    ...                kernel : un run contre l'autre système du laboratoire ne peut
    ...                pas se faire passer pour celui-ci.
    ${chemin}=    Ecrire Le Registre De La Cible
    File Should Exist    ${chemin}
    ${registre}=    Relire Le Registre De La Cible
    Le Registre Devrait Etre Conforme Au Plan    ${registre}    ${PLANNED_VERDICTS}
    ${cible}=    La Cible Du Registre Devrait Porter La Release    ${registre}
    Log    Cible mesurée : ${cible}
    Should Be Equal    ${registre}[hash_scope][hashed_keys]    ${{ ['capabilities'] }}
    ...    msg=L'empreinte du registre ne couvre pas les seules capacités : ${registre}[hash_scope]
    ${tableau}=    Tableau Markdown Du Registre
    Log    ${tableau}
