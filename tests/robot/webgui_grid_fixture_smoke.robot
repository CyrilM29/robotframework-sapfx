*** Settings ***
Documentation       Smoke **hors ligne** du lecteur de grille WebGUI, contre
...                 `fixtures/webgui_grid_fixture.html` : ni SAP, ni réseau.
...
...                 Il existe parce que ce qui rend l'invariant d'extraction
...                 vrai sur ce canal vit en JavaScript (lecture du `lsdata`,
...                 découpage des `ColumnIDs`, adressage `row[N]/cell[M]`,
...                 tranchage du préfixe des `th`, ré-unification des deux
...                 tables HTML d'une grille à colonnes figées). Les tests
...                 Python couvrent le CONTRAT du keyword avec une doublure de
...                 navigateur ; ils ne peuvent rien dire du balayage lui-même,
...                 et la suite live ne l'exerce que contre un conteneur, sur
...                 une seule disposition d'écran.
...
...                 Chacun des scénarios ci-dessous vise un mode de panne
...                 SILENCIEUX, c'est-à-dire un cas où une lecture fausse
...                 produirait un relevé plausible plutôt qu'une erreur.
...
...                 Exécution :
...                 | robot --pythonpath src tests/robot/webgui_grid_fixture_smoke.robot

Library             Browser
Library             Collections
Library             OperatingSystem
Library             SapFioriLibrary
Library             sapfx_common.table_extract

Suite Setup         Ouvrir La Fixture
Suite Teardown      Close Browser

Test Tags           webgui    offline


*** Variables ***
${GRILLE_A}         wnd[0]/usr/cntlGRID1/shellcont/shell
${GRILLE_B}         wnd[0]/usr/cntlGRID2/shellcont/shell


*** Test Cases ***
Deux grilles sur un ecran et aucune designee est un REFUS
    [Documentation]    Le mode de panne le plus grave du lecteur : prendre la
    ...    première grille du DOM produirait cinq fichiers parfaitement
    ...    complets d'un AUTRE tableau que celui annoncé dans leur nom. Le
    ...    dépôt remonte partout ailleurs une ambiguïté avec ses candidats.
    ${erreur}=    Run Keyword And Expect Error    *    Read Webgui Grid
    Should Contain    ${erreur}    2 grilles
    Should Contain    ${erreur}    ${GRILLE_A}
    Should Contain    ${erreur}    ${GRILLE_B}

Une grille designee est lue malgre la presence de l autre
    ${grille}=    Read Webgui Grid    ${GRILLE_A}
    Should Be Equal    ${grille}[sid]    ${GRILLE_A}
    Should Be Equal    ${grille}[container]    GRID1
    Length Should Be    ${grille}[candidates]    2

Les deux dialectes de lsdata sont lus
    [Documentation]    Un WebGUI réel écrit un littéral JS aux clés non citées
    ...    (`totalRows:200`) ; les anciens ITS et les fixtures écrivent du JSON.
    ...    Ne lire que le premier ferait d'une grille RECONNUE une grille au
    ...    contrat vide, donc refusée pour la mauvaise raison.
    ${a}=    Read Webgui Grid    ${GRILLE_A}
    Should Be Equal As Integers    ${a}[declared_rows]    ${7}
    Should Be Equal    ${a}[scrolling]    server
    ${b}=    Read Webgui Grid    ${GRILLE_B}
    Should Be Equal As Integers    ${b}[declared_rows]    ${1}
    Should Be Equal    ${b}[scrolling]    client
    Should Be Equal    ${b}[columns]    ${{ ['CARRID'] }}
    Should Be Equal    ${b}[rows][0][CARRID]    LH

Le DOM eclate la grille et les SID la re unifient
    [Documentation]    Une ALV à colonne figée est rendue en DEUX tables HTML.
    ...    Lire la structure du DOM obligerait à deviner comment les recoller ;
    ...    l'adressage par SID traverse la découpe sans la connaître.
    ${grille}=    Read Webgui Grid    ${GRILLE_A}
    ${premiere}=    Set Variable    ${grille}[rows][0]
    # MANDT vient de la table GELÉE, MTEXT de la table DÉFILANTE.
    Should Be Equal    ${premiere}[MANDT]    000
    Should Be Equal    ${premiere}[MTEXT]    SAP SE Walldorf
    Should Be Equal    ${grille}[rows][1][MANDT]    001

Une cellule au dela des colonnes declarees n est pas perdue
    [Documentation]    Le témoin d'un DÉCALAGE de colonnes, et le plus
    ...    dangereux des défauts de ce lecteur : si une release insère une
    ...    colonne que `ColumnIDs` ne porte pas au même rang, toutes les
    ...    valeurs glissent d'un cran et l'extraction reste complète, propre et
    ...    verte de bout en bout, la relecture du fichier comprise (le fichier
    ...    est fidèle au relevé, c'est le relevé qui est faux). La rendre sous
    ...    `COL<n>` au lieu de la jeter fait apparaître une colonne inattendue
    ...    dans le relevé, donc dans le fichier, donc à l'oeil.
    ${grille}=    Read Webgui Grid    ${GRILLE_A}
    Dictionary Should Contain Key    ${grille}[rows][0]    COL3
    Should Be Equal    ${grille}[rows][0][COL3]    hors-carte
    # Et la colonne surnuméraire n'est PAS annoncée dans les colonnes
    # déclarées : l'écart entre les deux est justement le signal.
    List Should Not Contain Value    ${grille}[columns]    COL3

Les titres affiches sont lus et leur nombre est rendu
    [Documentation]    La carte des titres rebouche chaque trou par
    ...    l'identifiant de colonne : elle a donc la même forme qu'on ait tout
    ...    trouvé ou rien, et aucune assertion portée sur elle ne peut détecter
    ...    un balayage qui a échoué. Seul le compteur le peut.
    ${grille}=    Read Webgui Grid    ${GRILLE_A}
    Should Be Equal As Integers    ${grille}[headers_found]    ${3}
    Should Be Equal    ${grille}[headers][MANDT]    Client
    Should Be Equal    ${grille}[headers][MTEXT]    Nom
    # La colonne de SÉLECTION porte un SID `.../col` sans nom de champ : ce
    # n'est pas une colonne de donnée et elle ne doit pas gonfler le compte.
    Dictionary Should Not Contain Key    ${grille}[headers]    ${EMPTY}

Une cellule composite n est pas collee et le texte masque reste dehors
    [Documentation]    Deux arbitrages de lecture, consignés ici pour qu'ils ne
    ...    soient pas des effets de bord.
    ...
    ...    Une cellule qui rend deux valeurs sur deux lignes est lue en
    ...    `innerText` et non en `textContent` : le second les COLLE, produisant
    ...    une valeur qui n'existe nulle part à l'écran (mesuré côté UI5 :
    ...    « New York4 133 »). Et `innerText` rend ce qui est AFFICHÉ, donc un
    ...    texte masqué reste dehors : c'est le comportement voulu pour une
    ...    extraction, qui doit rendre l'écran tel qu'il se montre.
    ${grille}=    Read Webgui Grid    ${GRILLE_A}
    ${premiere}=    Set Variable    ${grille}[rows][0]
    Should Be Equal    ${premiere}[MTEXT]    SAP SE Walldorf
    Should Not Contain    ${premiere}[MTEXT]    SEWalldorf
    ...    msg=Les deux valeurs de la cellule composite ont été collées : la lecture est repassée en textContent.
    Should Be Equal    ${premiere}[EXTRA]    visible
    Should Not Contain    ${premiere}[EXTRA]    MASQUE

Un releve amputé est REFUSE par la garde commune
    [Documentation]    Le bout en bout hors ligne : la grille déclare 7 lignes
    ...    et n'en rend que 2, propres et numérotées à partir de 1. C'est le
    ...    cas que rien dans les lignes ne trahit, et la garde partagée doit le
    ...    refuser AVANT toute écriture.
    ${grille}=    Read Webgui Grid    ${GRILLE_A}
    Should Be Equal As Integers    ${grille}[rendered_rows]    ${2}
    Should Be Equal As Integers    ${grille}[first_row_index]    ${1}
    ...    msg=La renumérotation à partir de 1 est le fait qui rend l'amputation invisible.
    Should Be Equal    ${grille}[complete]    ${False}
    ${extrait}=    Build Table Extract    ${grille}[rows]    columns=${grille}[columns]
    ...    headers=${grille}[headers]    declared_rows=${grille}[declared_rows]
    ...    source=fixture hors ligne
    Should Be Equal As Integers    ${extrait}[blank_rows]    ${0}
    ...    msg=Ces lignes doivent être PROPRES : c'est ce qui rend le cas indétectable autrement que par le total déclaré.
    ${erreur}=    Run Keyword And Expect Error    RELEVÉ REFUSÉ*
    ...    Table Extract Should Be Complete    ${extrait}
    Should Contain    ${erreur}    2 ligne(s) lues pour 7 DÉCLARÉES

Une grille absente de la portee courante echoue en nommant son remede
    [Documentation]    L'autre extrémité : sans session WebGUI rendue, le
    ...    keyword doit dire ce qu'il faut sonder plutôt que de rendre un
    ...    relevé vide.
    New Page    about:blank
    ${erreur}=    Run Keyword And Expect Error    *    Read Webgui Grid
    Should Contain    ${erreur}    Webgui Is Present
    [Teardown]    Ouvrir La Fixture Dans La Page Courante


*** Keywords ***
Ouvrir La Fixture
    [Documentation]    Ouvre la fixture locale. Aucun réseau : le fichier est
    ...    dans le dépôt, donc la suite est déterministe et jouable en CI.
    New Browser    chromium    headless=${True}
    New Context
    Ouvrir La Fixture Dans La Page Courante

Ouvrir La Fixture Dans La Page Courante
    ${chemin}=    Normalize Path    ${CURDIR}/fixtures/webgui_grid_fixture.html
    New Page    file://${chemin}
    # Une grille NOMMÉE : la fixture en porte deux à dessein, et un sélecteur
    # qui en matche plusieurs est refusé par la bibliothèque Browser.
    Wait For Elements State    css=table#C102[lsdata]    attached
