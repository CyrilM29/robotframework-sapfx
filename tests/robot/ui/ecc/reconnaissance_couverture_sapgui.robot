*** Settings ***
Documentation       Reconnaissance de couverture : ce que SapEccLibrary sait (et ne
...                 Spec: specs/reconnaissance-couverture-sapgui-a4h.md (sha256:c728eafcb423, 2026-09-08)
...                 savait pas) faire sur un écran SAP GUI : le REGISTRE de capacités.
...                 Generated from specs/reconnaissance-couverture-sapgui-a4h.md
...                 by sap-generator (re-run the generator rather than hand-editing
...                 locators here). Un test par scénario du plan, dans son ordre.
...
...                 Ce n'est PAS un test métier : chaque scénario exerce UNE capacité
...                 de la bibliothèque sur l'écran réel et consigne un verdict `gap` /
...                 `covered` / `poste` / `hors_api` dans un registre JSON déterministe.
...                 Le verdict est DÉRIVÉ de l'observation, puis confronté à celui du
...                 plan : le scénario échoue dans les deux sens (manque comblé OU
...                 capacité perdue) en nommant « mettre à jour le plan et le registre ».
...                 Le 2026-09-07, le tour de reconnaissance a relevé dix-sept manques
...                 (verdicts `gap`) ; le lot de correction livré le même jour dans
...                 `src/` les a comblés, et ce registre a rougi 18 fois sur 19 sur la
...                 bibliothèque corrigée avant de passer à l'état COUVERT ci-dessous.
...                 Invariant de la campagne : aucun manque n'est contourné, ni ici ni
...                 dans le page object (pas de JS, pas d'`Evaluate` sur un objet COM,
...                 pas de helper Python local).
...
...                 Assertions locale-safe : types de message (`E`, vide), ProgID
...                 (`SAP.TableTreeControl.1`, `SAPGUI.AbapEditor.1`), clés techniques
...                 (`A`, `*`, `DATFM`), codes fonction (`&FILTER`), types de contrôles
...                 (`GuiShell/Tree`, `GuiMenu`), code de transaction (`SESSION_MANAGER`).
...                 Les textes localisés (libellés, chemin du menu System, texte propre
...                 de la case) vivent dans le page object
...                 `resources/page_objects/sapgui_capability_probes.resource`
...                 (convention 1 : zéro localisateur ici ; convention 3).
...
...                 LECTURE SEULE : SM37 n'est jamais exécuté (aucun F8), la date
...                 « From », la combo et la case sont remises à leur valeur initiale
...                 relue en début de scénario ; l'écran de sélection n'est pas
...                 persistant. Le seul réglage persistant touché est la sortie du
...                 Data Browser : `Use ALV Grid In Data Browser` en Suite Setup
...                 (que toutes les suites SE16 posent), basculée en liste standard
...                 par le scénario 19 et RESTAURÉE en grille ALV par son teardown,
...                 restauration relue.
...                 Le registre est écrit dans `${REGISTER_PATH}` (défaut :
...                 `${OUTPUT DIR}/ecc_capability_register.json`) par le scénario 21
...                 ET par le Suite Teardown, avant `Close SAP`, même sur échec ; il
...                 porte l'identité de la cible mesurée en Suite Setup par
...                 `Get System Identity` (SID, mandant, utilisateur, release
...                 SAP_BASIS, kernel, serveur), hors empreinte.
...
...                 Exécution (A4H ou tout système de test) :
...
...                 robot --pythonpath src --outputdir results/reconnaissance ^
...                 -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER ^
...                 -v "SAP_PASSWORD: Secret:..." -v SAP_CLIENT:001 -v SAP_LANGUAGE:EN ^
...                 tests/robot/ui/ecc/reconnaissance_couverture_sapgui.robot

Resource            ../../../../resources/page_objects/sapgui_capability_probes.resource

Suite Setup         Ouvrir La Campagne De Reconnaissance
Suite Teardown      Clore La Campagne De Reconnaissance
Test Teardown       Revenir Au Menu

Test Tags           ecc    capability    a4h


*** Variables ***
# Les verdicts ATTENDUS par le plan, capacité par capacité : la copie de la
# table « Clés de registre » du plan (scénarios 1 à 20), à differ avec elle.
# Plusieurs verdicts admis se sépareraient par `|` (aucun cas aujourd'hui).
&{PLANNED_VERDICTS}
...    perception.shell_subtype=covered
...    tree.read_nodes=covered
...    tree.select_node=covered
...    tree.column_tree_read=covered
...    combobox.display_mode=covered
...    combobox.select_by_key=covered
...    date.input_user_format=covered
...    user.formats=covered
...    f4.calendar=covered
...    grid.double_click_cell=covered
...    grid.context_menu=covered
...    grid.toolbar_inventory=covered
...    grid.in_tabstrip_subscreen=covered
...    editor.get_value_refuses=covered
...    checkbox.by_own_label=covered
...    menu.select_by_path=covered
...    screen_map.menus_first=covered
...    perception.list_status_on_grid=covered
...    list.standard_se16_readable=covered
...    identity.release_and_kernel=covered


*** Test Cases ***
La perception distingue les sous-types de shell
    [Documentation]    Scénario 1 : la ligne de signature de l'arbre du menu
    ...                utilisateur porte `GuiShell/Tree` en colonne type.
    Ouvrir L Accueil
    ${ligne}=    Ligne De Signature Du Menu Utilisateur
    ${colonnes}=    Colonnes De La Ligne De Signature    ${ligne}
    ${affiche}=    La Signature Affiche Le Sous Type    ${colonnes}
    ${verdict}=    Verdict De Capacite    ${affiche}
    Consigner Le Verdict    perception.shell_subtype    ${verdict}
    ...    Ligne de signature de l'arbre : type=${colonnes}[1], ${colonnes.__len__()} colonnes
    Le Verdict Devrait Etre    perception.shell_subtype    covered

L'arbre du menu SAP se lit par keyword
    [Documentation]    Scénario 2 : `Read Tree Nodes` rend des nœuds (clé et
    ...                texte) et `Get Value` sur l'arbre REFUSE en nommant le
    ...                ProgID et le lecteur.
    Ouvrir L Accueil
    ${noeuds}=    Lire Les Noeuds Du Menu Utilisateur
    ${lus}=    Run Keyword And Return Status    Les Noeuds Devraient Porter Cle Et Texte    ${noeuds}
    ${status}    ${message}=    Run Keyword And Ignore Error    Lire La Valeur Du Menu Utilisateur
    ${refuse}=    L Echec Devrait Etre Reproduit    tree.read_nodes    ${status}    ${message}
    ...    *ProgID*Read Tree Nodes*
    ${verdict}=    Verdict De Capacite    ${lus} and ${refuse}
    Consigner Le Verdict    tree.read_nodes    ${verdict}
    ...    ${noeuds.__len__()} nœud(s) lu(s) ; Get Value sur l'arbre : ${message}
    Le Verdict Devrait Etre    tree.read_nodes    covered

Sélectionner un nœud d'arbre est vérifié
    [Documentation]    Scénario 3 : `Select Tree Node By Text` sur « Plain ABAP »
    ...                rend une clé, relue par `Get Selected Tree Node`.
    Ouvrir L Accueil
    ${cle}=    Selectionner Le Dossier Plain ABAP Par Texte
    ${relue}=    Noeud Selectionne Du Menu Utilisateur
    ${verifie}=    Run Keyword And Return Status    Should Be Equal    ${cle}    ${relue}
    ${verdict}=    Verdict De Capacite    ${verifie}
    Consigner Le Verdict    tree.select_node    ${verdict}
    ...    Sélection par texte -> clé ${cle}, relue ${relue}
    Le Verdict Devrait Etre    tree.select_node    covered

L'arbre à colonnes de l'IMG se lit
    [Documentation]    Scénario 4 : `Read Tree Nodes` sur l'IMG de SPRO rend un
    ...                texte NON vide lu dans la colonne TEXT, clé telle quelle.
    Ouvrir L IMG De Reference
    ${noeuds}=    Lire Les Noeuds De L IMG
    ${lus}=    Run Keyword And Return Status    Les Noeuds Devraient Porter Cle Et Texte    ${noeuds}
    ${verdict}=    Verdict De Capacite    ${lus}
    Consigner Le Verdict    tree.column_tree_read    ${verdict}
    ...    ${noeuds.__len__()} nœud(s) de l'IMG, premier : ${noeuds}[0]
    Le Verdict Devrait Etre    tree.column_tree_read    covered

Une combo box en affichage est refusée en le disant
    [Documentation]    Scénario 5 : SU01 en affichage, onglet Logon Data ; la clé
    ...                technique du type d'utilisateur se lit (`A`), l'entrée
    ...                figure dans la liste, et la sélection par libellé échoue en
    ...                nommant le mode AFFICHAGE.
    Afficher L Utilisateur    ${SAP_USER}
    Ouvrir L Onglet    Logon Data
    ${cle}=    Lire La Cle Du Type D Utilisateur
    ${entrees}=    Lire Les Entrees Du Type D Utilisateur
    ${cle_lue}=    Run Keyword And Return Status    Should Be Equal    ${cle}    ${SU01_USER_TYPE_DIALOG_CODE}
    ${listee}=    Run Keyword And Return Status    L Entree De Cle Devrait Figurer    ${entrees}    ${cle}
    ${status}    ${message}=    Run Keyword And Ignore Error    Tenter De Changer Le Type D Utilisateur
    ${refuse}=    L Echec Devrait Etre Reproduit    combobox.display_mode    ${status}    ${message}
    ...    *AFFICHAGE*
    ${verdict}=    Verdict De Capacite    ${cle_lue} and ${listee} and ${refuse}
    Consigner Le Verdict    combobox.display_mode    ${verdict}
    ...    Clé lue '${cle}', ${entrees.__len__()} entrées ; sélection en affichage : ${message}
    Le Verdict Devrait Etre    combobox.display_mode    covered

Une combo box modifiable se sélectionne par clé
    [Documentation]    Scénario 6 : SM37, « Or after event » : la clé initiale est
    ...                le BLANC relevé (rendu tel quel), `*` par clé, relu par clé,
    ...                puis le blanc restauré et relu : la restauration a visé la
    ...                bonne des deux entrées (clé vide et clé blanche).
    Ouvrir La Selection Simple Des Jobs
    ${initiale}=    Lire La Cle De L Evenement
    ${blanc}=    Run Keyword And Return Status    La Cle Initiale De L Evenement Devrait Etre Un Blanc    ${initiale}
    Choisir L Evenement Par Cle    ${SM37_EVENT_ANY}
    ${lue}=    Lire La Cle De L Evenement
    Choisir L Evenement Par Cle    ${initiale}
    ${restauree}=    Lire La Cle De L Evenement
    ${ok}=    Run Keyword And Return Status    Run Keywords
    ...    Should Be Equal    ${lue}    ${SM37_EVENT_ANY}
    ...    AND    Should Be Equal    ${restauree}    ${initiale}
    ...    AND    La Cle Initiale De L Evenement Devrait Etre Un Blanc    ${restauree}
    ${verdict}=    Verdict De Capacite    ${blanc} and ${ok}
    Consigner Le Verdict    combobox.select_by_key    ${verdict}
    ...    Clé initiale '${initiale}' (blanc : ${blanc}), après sélection '${lue}', après restauration '${restauree}'
    Le Verdict Devrait Etre    combobox.select_by_key    covered

La saisie d'une date se convertit au format de l'utilisateur
    [Documentation]    Scénario 7 : `Input Date` avec une date ISO : aucun type E,
    ...                la chaîne saisie est la forme LOCALE relevée (page object),
    ...                la valeur relue est cette chaîne ; date restaurée et relue
    ...                en teardown, même sur échec.
    Ouvrir La Selection Simple Des Jobs
    ${initiale}=    Lire La Date De Debut
    ${saisie}    ${type}=    Saisir La Date De Debut En ISO    ${SM37_PROBE_DATE_ISO}
    ${relue}=    Lire La Date De Debut
    ${ok}=    Run Keyword And Return Status    Run Keywords
    ...    Should Be Equal    ${type}    ${EMPTY}
    ...    AND    La Date Saisie Devrait Etre La Forme Locale    ${saisie}
    ...    AND    Should Be Equal    ${relue}    ${saisie}
    ${verdict}=    Verdict De Capacite    ${ok}
    Consigner Le Verdict    date.input_user_format    ${verdict}
    ...    ISO ${SM37_PROBE_DATE_ISO} -> saisi '${saisie}', type '${type}', relu '${relue}'
    Le Verdict Devrait Etre    date.input_user_format    covered
    [Teardown]    Run Keywords    Restaurer La Date De Debut Si Relevee    AND    Revenir Au Menu

Les formats de l'utilisateur se lisent par clé technique
    [Documentation]    Scénario 8 : `Get User Formats` rend des CLÉS (DATFM 1 à
    ...                6, DCPFM vide/X/Y), jamais un libellé localisé.
    ${formats}=    Get User Formats
    ${ok}=    Run Keyword And Return Status    Les Formats Devraient Etre Des Cles    ${formats}
    ${verdict}=    Verdict De Capacite    ${ok}
    Consigner Le Verdict    user.formats    ${verdict}
    ...    ${formats}
    Le Verdict Devrait Etre    user.formats    covered

Le calendrier F4 d'une date se pilote
    [Documentation]    Scénario 9 : `Pick Calendar Date` sélectionne la date, rend
    ...                la forme LOCALE relevée (page object, aucune saisie Input
    ...                Date ici) et referme ; `Pick F4 Value` sur le même champ
    ...                nomme le CALENDRIER. Date restaurée et relue en teardown,
    ...                même sur échec.
    Ouvrir La Selection Simple Des Jobs
    ${initiale}=    Lire La Date De Debut
    ${choisie}=    Choisir La Date De Debut Au Calendrier    ${SM37_PROBE_DATE_ISO}
    ${attendue}=    Forme Locale De La Date De Sonde
    ${fenetres}=    Get Open Windows
    ${sans_modal}=    Run Keyword And Return Status    Aucune Fenetre Modale Ne Devrait Etre Ouverte    ${fenetres}
    ${status}    ${message}=    Run Keyword And Ignore Error
    ...    Tenter De Choisir Une Date Par L Aide F4    ${attendue}
    ${nomme}=    L Echec Devrait Etre Reproduit    f4.calendar    ${status}    ${message}
    ...    *CALENDRIER*Pick Calendar Date*
    ${ok}=    Run Keyword And Return Status    La Date Saisie Devrait Etre La Forme Locale    ${choisie}
    ${verdict}=    Verdict De Capacite    ${ok} and ${sans_modal} and ${nomme}
    Consigner Le Verdict    f4.calendar    ${verdict}
    ...    Calendrier -> '${choisie}' (attendu '${attendue}') ; Pick F4 Value : ${message}
    Le Verdict Devrait Etre    f4.calendar    covered
    [Teardown]    Run Keywords    Restaurer La Date De Debut Si Relevee    AND    Revenir Au Menu

Le double-clic d'une cellule ouvre le détail
    [Documentation]    Scénario 10 : `Double Click Grid Cell` sur T000 ouvre le
    ...                modal de détail, refermé ensuite.
    Afficher T000 En Grille
    Ouvrir Le Detail De La Premiere Ligne
    ${fenetres}=    Get Open Windows
    ${modal}=    Run Keyword And Return Status    Une Fenetre Modale Devrait Etre Ouverte    ${fenetres}
    Cancel Popup
    ${apres}=    Get Open Windows
    ${referme}=    Run Keyword And Return Status    Aucune Fenetre Modale Ne Devrait Etre Ouverte    ${apres}
    ${verdict}=    Verdict De Capacite    ${modal} and ${referme}
    Consigner Le Verdict    grid.double_click_cell    ${verdict}
    ...    Modal après double-clic = ${modal}, refermé = ${referme}
    Le Verdict Devrait Etre    grid.double_click_cell    covered

Le menu contextuel d'une grille se pilote par code fonction
    [Documentation]    Scénario 11 : `List Grid Context Menu` porte `&FILTER`,
    ...                `Select Grid Context Menu Item` l'ouvre (modal), refermé.
    Afficher T000 En Grille
    ${codes}=    Codes Du Menu Contextuel De La Grille
    ${liste}=    Run Keyword And Return Status    List Should Contain Value    ${codes}    ${GRID_FILTER_MENU_CODE}
    Ouvrir Le Filtre De La Grille
    ${fenetres}=    Get Open Windows
    ${modal}=    Run Keyword And Return Status    Une Fenetre Modale Devrait Etre Ouverte    ${fenetres}
    Cancel Popup
    ${verdict}=    Verdict De Capacite    ${liste} and ${modal}
    Consigner Le Verdict    grid.context_menu    ${verdict}
    ...    Codes ${codes} ; filtre ouvert en modal = ${modal}
    Le Verdict Devrait Etre    grid.context_menu    covered

Un bouton de barre d'outils absent est refusé avec inventaire
    [Documentation]    Scénario 12 : la barre de la grille est vide, le clic et le
    ...                tri échouent en nommant la barre d'application.
    Afficher T000 En Grille
    ${boutons}=    Boutons De La Barre De La Grille
    ${status}    ${message}=    Run Keyword And Ignore Error
    ...    Cliquer Un Bouton De Grille    ${GRID_SORT_DESC_BUTTON}
    ${nomme}=    L Echec Devrait Etre Reproduit    grid.toolbar_inventory    ${status}    ${message}
    ...    *barre d'application*
    ${status_tri}    ${message_tri}=    Run Keyword And Ignore Error    Trier La Grille Par Client
    ${tri_nomme}=    L Echec Devrait Etre Reproduit    grid.toolbar_inventory    ${status_tri}    ${message_tri}
    ...    *barre d'application*
    ${vide}=    Run Keyword And Return Status    Should Be Empty    ${boutons}
    ${verdict}=    Verdict De Capacite    ${nomme} and ${tri_nomme} and ${vide}
    Consigner Le Verdict    grid.toolbar_inventory    ${verdict}
    ...    Barre de grille : ${boutons} ; clic : ${message} ; tri : ${message_tri}
    Le Verdict Devrait Etre    grid.toolbar_inventory    covered

Une grille dans un sous-écran de tabstrip se lit (témoin couvert)
    [Documentation]    Scénario 13 : SU01, onglet Parameters ; la grille ALV du
    ...                sous-écran expose des ids de colonnes TECHNIQUES et
    ...                `Read Grid` en lit au moins une ligne.
    Afficher L Utilisateur    ${SAP_USER}
    Ouvrir L Onglet    Parameters
    ${ids}=    Colonnes De La Grille Des Parametres
    ${lignes}=    Lire Les Parametres De L Utilisateur    5
    ${couvert}=    Run Keyword And Return Status    Run Keywords
    ...    Should Not Be Empty    ${ids}
    ...    AND    Should Not Be Empty    ${lignes}
    ${verdict}=    Verdict De Capacite    ${couvert}
    Consigner Le Verdict    grid.in_tabstrip_subscreen    ${verdict}
    ...    Colonnes ${ids}, ${lignes.__len__()} ligne(s) lue(s) par Read Grid
    Le Verdict Devrait Etre    grid.in_tabstrip_subscreen    covered

Get Value sur un éditeur ABAP refuse
    [Documentation]    Scénario 14 : SE38, RSPARAM en affichage ; `Get Value` sur
    ...                le contrôle éditeur ÉCHOUE en nommant le ProgID et le
    ...                sous-type (le source est hors API : le refus est la capacité).
    Afficher Le Programme    ${SE38_PROBE_PROGRAM}
    ${status}    ${message}=    Run Keyword And Ignore Error    Lire Le Controle Editeur
    ${refuse}=    L Echec Devrait Etre Reproduit    editor.get_value_refuses    ${status}    ${message}
    ...    *ProgID*GuiShell/AbapEditor*
    ${verdict}=    Verdict De Capacite    ${refuse}
    Consigner Le Verdict    editor.get_value_refuses    ${verdict}
    ...    Get Value sur l'éditeur : ${message}
    Le Verdict Devrait Etre    editor.get_value_refuses    covered

Une case à cocher se coche par son texte propre
    [Documentation]    Scénario 15 : SM37 ; la case « Sched. » est basculée par son
    ...                TEXTE PROPRE vers l'état OPPOSÉ à l'initial, son état se
    ...                relit, l'état initial est restauré.
    Ouvrir La Selection Simple Des Jobs
    ${initial}=    Etat De La Case Planifie
    ${id}    ${attendu}=    Basculer La Case Planifie    ${initial}
    ${etat}=    Run Keyword And Return Status    La Case Planifie Devrait Etre    ${attendu}
    ${type}=    Get Element Type    ${id}
    Restaurer La Case Planifie    ${initial}
    ${revenu}=    Run Keyword And Return Status    La Case Planifie Devrait Etre    ${initial}
    ${ok}=    Run Keyword And Return Status    Run Keywords
    ...    Should Be Equal    ${type}    GuiCheckBox
    ...    AND    Should Not Be Equal    ${attendu}    ${initial}
    ${verdict}=    Verdict De Capacite    ${etat} and ${ok} and ${revenu}
    Consigner Le Verdict    checkbox.by_own_label    ${verdict}
    ...    Case basculée par texte propre -> ${id} (${type}), '${initial}' -> '${attendu}', état initial restauré = ${revenu}
    Le Verdict Devrait Etre    checkbox.by_own_label    covered

Un menu se sélectionne par chemin
    [Documentation]    Scénario 16 : accueil ; `Select Menu Item` par le chemin de
    ...                textes du page object ouvre le modal « System: Status »,
    ...                dont la transaction est lue, puis F12.
    Ouvrir L Accueil
    ${id}=    Ouvrir Le Statut Systeme Par Chemin
    ${fenetres}=    Get Open Windows
    ${modal}=    Run Keyword And Return Status    Une Fenetre Modale Devrait Etre Ouverte    ${fenetres}
    ${tcode}=    Lire La Transaction Du Statut Systeme
    Fermer Le Statut Systeme
    ${ok}=    Run Keyword And Return Status    Run Keywords
    ...    Should Be Equal    ${id}    ${SM_MENU_SYSTEM_STATUS}
    ...    AND    Should Be Equal    ${tcode}    SESSION_MANAGER
    ${verdict}=    Verdict De Capacite    ${modal} and ${ok}
    Consigner Le Verdict    menu.select_by_path    ${verdict}
    ...    Chemin -> ${id}, modal ${modal}, transaction '${tcode}'
    Le Verdict Devrait Etre    menu.select_by_path    covered

La carte numérotée commence par la zone actionnable
    [Documentation]    Scénario 17 : SE16 sur T000 en grille ; `@1` n'est pas un
    ...                `GuiMenu` et la carte ne porte aucune entrée de menu.
    Afficher T000 En Grille
    ${colonnes}=    Premiere Reference De La Carte
    ${menus}=    Entrees De Menu De La Carte
    ${ok}=    Run Keyword And Return Status    Run Keywords
    ...    Should Not Be Equal    ${colonnes}[3]    GuiMenu
    ...    AND    Should Be Equal As Integers    ${menus}    0
    ${verdict}=    Verdict De Capacite    ${ok}
    Consigner Le Verdict    screen_map.menus_first    ${verdict}
    ...    @1 = type ${colonnes}[3], entrées de menu dans la carte : ${menus}
    Le Verdict Devrait Etre    screen_map.menus_first    covered

Le préflight de liste reconnaît une grille ALV
    [Documentation]    Scénario 18 : `Get List Rendering Status` sur la grille de
    ...                T000 : sous-type GridView relevé, aucune alerte accessibilité.
    Afficher T000 En Grille
    ${statut}=    Get List Rendering Status
    ${ok}=    Run Keyword And Return Status    Run Keywords
    ...    List Should Contain Value    ${statut}[shell_subtypes]    GridView
    ...    AND    Should Not Be True    ${statut}[accessibility_mode_needed]
    ${verdict}=    Verdict De Capacite    ${ok}
    Consigner Le Verdict    perception.list_status_on_grid    ${verdict}
    ...    shell_subtypes=${statut}[shell_subtypes], accessibility_mode_needed=${statut}[accessibility_mode_needed]
    Le Verdict Devrait Etre    perception.list_status_on_grid    covered

La liste SE16 standard se lit en labels
    [Documentation]    Scénario 19 : la sortie du Data Browser basculée en liste
    ...                standard ; T000 exécutée rend une liste ABAP classique en
    ...                labels : `Get List Rendering Status` ne réclame aucun mode
    ...                accessibilité et `Read Abap List` rend la ligne du mandant
    ...                de référence. La grille ALV est restaurée et relue en
    ...                teardown, même sur échec.
    Afficher T000 En Liste Standard
    ${statut}=    Statut De Rendu De L Ecran
    ${lignes}=    Lire La Liste Standard
    ${ok}=    Run Keyword And Return Status    Run Keywords
    ...    Should Be True    ${statut}[list_readable]
    ...    AND    Should Not Be True    ${statut}[accessibility_mode_needed]
    ...    AND    Should Not Be True    ${statut}[shell_rendered]
    ...    AND    La Liste Devrait Porter Le Mandant De Reference    ${lignes}
    ${verdict}=    Verdict De Capacite    ${ok}
    Consigner Le Verdict    list.standard_se16_readable    ${verdict}
    ...    Liste standard : ${statut}[readable_labels] labels, shell=${statut}[shell_rendered], accessibilité=${statut}[accessibility_mode_needed], ${lignes.__len__()} ligne(s) lue(s)
    Le Verdict Devrait Etre    list.standard_se16_readable    covered
    [Teardown]    Run Keywords    Restaurer La Grille ALV Du Data Browser    AND    Revenir Au Menu

L'identité du système prouve sa release et son kernel
    [Documentation]    Scénario 20 : `Get System Identity` ouvre System > Status
    ...                par position, lit release SAP_BASIS et kernel, referme tout ;
    ...                le SID lu est celui de la session, aucune section non lue,
    ...                aucun modal résiduel.
    Ouvrir L Accueil
    ${identite}=    Identite Du Systeme
    ${prouve}=    Run Keyword And Return Status    L Identite Devrait Prouver La Release    ${identite}
    ${meme}=    Run Keyword And Return Status    Le Systeme Lu Devrait Etre Celui De La Session    ${identite}
    ${fenetres}=    Get Open Windows
    ${sans_modal}=    Run Keyword And Return Status    Aucune Fenetre Modale Ne Devrait Etre Ouverte    ${fenetres}
    ${verdict}=    Verdict De Capacite    ${prouve} and ${meme} and ${sans_modal}
    Consigner Le Verdict    identity.release_and_kernel    ${verdict}
    ...    ${identite}[system_id]/${identite}[client] SAP_BASIS ${identite}[basis_release] SP ${identite}[basis_sp_level], kernel ${identite}[kernel_release] PL ${identite}[kernel_patch_level], non lu : ${identite}[unread], aucun modal résiduel : ${sans_modal}
    Le Verdict Devrait Etre    identity.release_and_kernel    covered

Le registre est écrit, déterministe, et conforme au plan
    [Documentation]    Scénario 21 : le registre est écrit par l'artefact
    ...                déterministe générique, relu avec son empreinte
    ...                RECALCULÉE, porte exactement les capacités des scénarios 1
    ...                à 20 avec les verdicts admis par le plan ET l'identité de la
    ...                cible mesurée (SID, mandant, utilisateur, release, kernel) ;
    ...                le tableau Markdown est journalisé.
    ${chemin}=    Ecrire Le Registre Des Capacites    ${REGISTER_PATH}
    File Should Exist    ${chemin}
    ${registre}=    Relire Le Registre Des Capacites    ${chemin}
    Le Registre Devrait Etre Conforme Au Plan    ${registre}    ${PLANNED_VERDICTS}
    ${cible}=    L Identite De La Cible Devrait Etre Renseignee    ${registre}
    Log    Cible mesurée : ${cible}
    Should Be Equal    ${registre}[hash_scope][hashed_keys]    ${{ ['capabilities'] }}
    ...    msg=L'empreinte du registre ne couvre pas les seules capacités : ${registre}[hash_scope]
    ${tableau}=    Tableau Markdown Du Registre
    Log    ${tableau}
