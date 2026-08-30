*** Settings ***
Documentation       **EXEMPLE À PERSONNALISER** : ce fichier porte le vocabulaire
...                 métier du LABORATOIRE de ce dépôt (identifiants, chemins, noms
...                 de tables et de modules relevés live sur SES cibles). Beaucoup
...                 s'y réutilise tel quel sur un autre système (écrans et services
...                 standard), mais rien n'y fait autorité : à VÉRIFIER sur votre
...                 cible et à adapter à votre métier. Ce qui fait foi partout,
...                 c'est `src/`, les bibliothèques, qui portent les capacités :
...                 voir `resources/README.md`.
...
...                 Page object des écrans de **saisie du Data Browser (SE16)** :
...                 l'écran initial d'où se déclenche la création, l'écran de
...                 saisie d'un enregistrement, et le chemin de suppression
...                 CIBLÉE depuis la grille de résultats. Un seul écran métier,
...                 donc un seul fichier : ses localisateurs en tête, ses
...                 mots-clés métier ensuite.
...
...                 Ces mots-clés existaient en BRUT dans une suite de
...                 démonstration auto-suffisante (`tests/robot/
...                 exploratory_campaign_a4h.robot`, dérogation à la convention 1
...                 assumée dans son en-tête). Ils sont ici promus en couche
...                 réutilisable et **paramétrée par table et par champs** : plus
...                 aucun identifiant SAP dans une suite, et une cible d'écriture
...                 se change sans toucher au code.
...
...                 Contrat de sûreté, parce que ces mots-clés ÉCRIVENT dans un
...                 système réel :
...
...                 1. **Liste blanche obligatoire.** Chaque mot-clé qui écrit
...                 passe par `Validate Write Target` : une table hors périmètre
...                 est refusée avant toute action, et une liste blanche vide
...                 refuse tout au lieu d'autoriser tout.
...                 2. **Suppression CIBLÉE seulement.** Le menu emprunté est
...                 « Table Entry > Delete » (les entrées sélectionnées), jamais
...                 son voisin immédiat « Delete all » (toute la table, sans
...                 égard pour la sélection). L'écart d'un cran est
...                 irréversible : la garde n'est donc pas l'indice de menu mais
...                 le CONTENU, relu juste avant, la grille étant filtrée sur la
...                 clé et devant porter exactement la ligne visée.
...                 3. **Idempotence.** `Ensure Table Entry Is Absent` ne fait
...                 rien quand rien n'existe : un pré-nettoyage ne doit pas
...                 dépendre de l'état laissé par l'exécution précédente.
...
...                 Contrat d'assertion : les verdicts portent sur le TYPE du
...                 message de statut (`S`, `E`), sur des ids TECHNIQUES de
...                 champs et sur des entiers, jamais sur un texte localisé
...                 (convention 3). Les champs de l'écran de saisie ne sont pas
...                 déclarés ici : ils sont DÉRIVÉS de la perception de l'écran
...                 (`Table Entry Fields`), parce que leur préfixe de type varie
...                 d'un champ à l'autre et que l'écran est régénéré par table.

# `ecc_keywords.resource` porte déjà l'import de `SapEccLibrary` (avec ses
# arguments) et les localisateurs SE16 communs : les redéclarer les ferait
# diverger. Ce page object n'ajoute que ce qui manque à l'ÉCRITURE.
Resource            ../ecc_keywords.resource
Library             sapfx_common.write_simulation


*** Variables ***
# --- Localisateurs de l'écran INITIAL de SE16 (relevés live A4H, GUI 8.00) ---
# « Create Entries » ne s'atteint QUE depuis l'écran initial : sur l'écran de
# sélection, le même indice de menu porte « Execute and Print ». D'où la garde
# structurelle de `Open Table Entry Creation`, qui exige la présence du champ
# de saisie du nom de table (le seul discriminant indépendant de la langue).
${SE16_MENU_CREATE_ENTRIES}         wnd[0]/mbar/menu[0]/menu[1]

# --- Localisateurs de la grille de résultats (chemin de suppression) ---------
${SE16_MENU_SELECT_ALL}             wnd[0]/mbar/menu[1]/menu[0]    # Edit > Select All
# ATTENTION : l'entrée de menu qui PRÉCÈDE immédiatement celle-ci est
# « Delete all » (toute la table, sans égard pour la sélection). Son indice
# n'est écrit nulle part dans ce fichier, à dessein : rien à copier par
# mégarde. Le mot-clé de suppression ne référence que la ligne ci-dessous, et
# seulement après avoir relu le contenu de la grille filtrée.
${SE16_MENU_DELETE_SELECTED}        wnd[0]/mbar/menu[0]/menu[6]    # Table Entry > Delete
${SE16_DELETE_ENTRY_BUTTON}        wnd[0]/tbar[1]/btn[14]         # « Delete Entry » : valide la suppression

# --- Périmètre d'écriture ----------------------------------------------------
# Liste blanche par défaut : VIDE, donc aucune écriture possible. Une campagne
# déclare son périmètre explicitement (une entrée par défaut) ; c'est une
# décision, jamais un effet de bord.
@{WRITE_TARGET_ALLOWLIST}


*** Keywords ***
Open Table Entry Creation
    [Documentation]    Ouvre l'écran de SAISIE d'un enregistrement de
    ...    ``${table}`` et retourne la carte ``{CHAMP: localisateur}`` de ses
    ...    champs, dérivée de la perception.
    ...
    ...    Trois pièges tenus ici, tous relevés live : la création se déclenche
    ...    depuis l'écran INITIAL de SE16 (garde structurelle sur le champ de
    ...    nom de table, l'entrée de menu de même indice signifiant tout autre
    ...    chose sur l'écran de sélection) ; une table que le dictionnaire
    ...    déclare non maintenable est refusée par un message de type ``E``
    ...    quelles que soient les autorisations, et l'échec le dit ; les
    ...    identifiants des champs suivent ``<type><TABLE>-<CHAMP>`` avec un
    ...    préfixe de type qui varie d'un champ à l'autre, donc ils se
    ...    perçoivent au lieu de se déclarer.
    [Arguments]    ${table}    ${allowlist}=${WRITE_TARGET_ALLOWLIST}
    ${target}=    Validate Write Target    ${table}    ${allowlist}
    Go To Transaction    /nSE16
    Element Should Be Present    ${SE16_TABLE_FIELD}
    ...    message=L'écran initial de SE16 n'est pas affiché : « Create Entries » n'y est atteignable que depuis là.
    Input Text    ${SE16_TABLE_FIELD}    ${target}
    Click Element    ${SE16_MENU_CREATE_ENTRIES}
    Wait Until Busy Done
    ${signature}=    Get Screen Signature
    ${fields}=    Table Entry Fields    ${signature}    ${target}
    IF    not ${fields}
        ${type}    ${text}=    Get Status Message
        Fail    L'écran de saisie de '${target}' ne s'est pas ouvert (message de type '${type}') : ${text}. Une table dont le dictionnaire interdit la maintenance est refusée en type 'E' quelles que soient les autorisations ; percevoir l'écran avec Get Screen Signature avant de conclure à une dérive de localisateur.
    END
    RETURN    ${fields}

Create Table Entry
    [Documentation]    Écrit UN enregistrement dans ``${table}`` par l'écran,
    ...    puis exige un message de statut de type ``S``. Les valeurs sont
    ...    données par nom TECHNIQUE de champ (``CATEGORY=...``) : un champ
    ...    inconnu de l'écran échoue en listant ceux qui y sont réellement
    ...    présents, jamais une saisie au petit bonheur dans un champ voisin.
    ...
    ...    Rend la main sur l'écran initial de SE16 : l'écran de saisie reste
    ...    sinon ouvert, prêt pour un enregistrement suivant, et le mot-clé
    ...    d'après hériterait d'un contexte qu'il n'a pas demandé.
    [Arguments]    ${table}    ${allowlist}=${WRITE_TARGET_ALLOWLIST}    &{values}
    ${fields}=    Open Table Entry Creation    ${table}    ${allowlist}
    FOR    ${field}    ${value}    IN    &{values}
        ${locator}=    Evaluate    $fields.get($field.upper())
        IF    $locator is None
            Fail    La table '${table}' n'expose pas le champ de saisie '${field}' ; champs présents à l'écran : ${{ sorted($fields) }}
        END
        Input Text    ${locator}    ${value}
    END
    Send Vkey    11
    Wait Until Busy Done
    ${type}    ${text}=    Get Status Message
    Should Be Equal    ${type}    S
    ...    msg=L'écriture dans '${table}' n'a pas confirmé un succès (message de type '${type}') : ${text}
    Go To Transaction    /nSE16

Display Table Entries With Key
    [Documentation]    Affiche les lignes de ``${table}`` dont ``${key_field}``
    ...    vaut ``${key_value}`` et les retourne en liste de dicts (clés = ids
    ...    techniques de colonnes). Retourne une liste VIDE quand la sélection
    ...    ne ramène rien : SE16 reste alors sur l'écran de sélection sans
    ...    ouvrir de grille, et c'est un état normal, pas une erreur.
    ...
    ...    Le critère est résolu par NOM (`Get Se16 Selection Criteria`), jamais
    ...    par position : le choix des champs de sélection persiste par
    ...    utilisateur et déplace les critères ``I<n>``.
    [Arguments]    ${table}    ${key_field}    ${key_value}    ${max_rows}=20
    Open Table Selection Screen    ${table}
    ${criteria}=    Get Se16 Selection Criteria
    ${locator}=    Evaluate    $criteria.get($key_field.upper())
    IF    $locator is None
        Fail    La table '${table}' n'expose pas le critère de sélection '${key_field}' ; critères présents : ${{ sorted($criteria) }}
    END
    Input Text    ${locator}    ${key_value}
    Send Vkey    8
    Wait Until Busy Done
    ${shown}=    Run Keyword And Return Status    Wait Until Element Present
    ...    ${SE16_GRID}    timeout=5s
    IF    not ${shown}
        ${empty}=    Create List
        RETURN    ${empty}
    END
    ${rows}=    Read Grid    ${SE16_GRID}    max_rows=${max_rows}
    RETURN    ${rows}

Count Table Entries With Key
    [Documentation]    Nombre d'enregistrements de ``${table}`` portant la clé
    ...    donnée, compté par « Number of Entries » (fiable à 0, contrairement
    ...    à l'exécution F8 qui reste sur l'écran de sélection sans résultat).
    ...    Retourne un entier.
    [Arguments]    ${table}    ${key_field}    ${key_value}
    ${criteria}=    Create Dictionary    ${key_field}=${key_value}
    ${count}=    Count Table Entries With Criteria    ${table}    &{criteria}
    RETURN    ${count}

Delete Table Entry
    [Documentation]    Supprime l'enregistrement de ``${table}`` portant la clé
    ...    donnée, et lui seul. Retourne ``True`` s'il y avait quelque chose à
    ...    supprimer, ``False`` sinon (donc **idempotent** : utilisable en
    ...    pré-nettoyage comme en teardown).
    ...
    ...    La sûreté ne repose PAS sur l'indice du menu, qui jouxte celui de la
    ...    suppression de masse, mais sur le contenu : la grille est filtrée sur
    ...    la clé, puis RELUE, et toute ambiguïté (plus d'une ligne, ou une
    ...    ligne dont la clé n'est pas celle visée) interrompt le mot-clé
    ...    **sans rien supprimer**. « Select All » ne peut donc porter que sur
    ...    la ligne visée.
    [Arguments]    ${table}    ${key_field}    ${key_value}
    ...    ${allowlist}=${WRITE_TARGET_ALLOWLIST}
    ${target}=    Validate Write Target    ${table}    ${allowlist}
    ${rows}=    Display Table Entries With Key    ${target}    ${key_field}    ${key_value}
    IF    not ${rows}    RETURN    ${False}
    Length Should Be    ${rows}    1
    ...    msg=Suppression interrompue AVANT toute action : la sélection de '${target}' sur ${key_field}=${key_value} porte ${{ len($rows) }} lignes au lieu d'une seule.
    ${key_seen}=    Evaluate    $rows[0].get($key_field.upper())
    Should Be Equal    ${key_seen}    ${key_value}
    ...    msg=Suppression interrompue AVANT toute action : la ligne affichée porte ${key_field}='${key_seen}' et non '${key_value}'.
    Click Element    ${SE16_MENU_SELECT_ALL}
    Wait Until Busy Done
    Click Element    ${SE16_MENU_DELETE_SELECTED}
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_DELETE_ENTRY_BUTTON}
    Click Element    ${SE16_DELETE_ENTRY_BUTTON}
    Wait Until Busy Done
    ${type}    ${text}=    Get Status Message
    Should Be Equal    ${type}    S
    ...    msg=La suppression de ${key_field}=${key_value} dans '${target}' n'a pas confirmé un succès (message de type '${type}') : ${text}
    RETURN    ${True}

Ensure Table Entry Is Absent
    [Documentation]    Garantit qu'aucun enregistrement de ``${table}`` ne porte
    ...    la clé donnée : supprime le reliquat s'il existe, ne fait rien sinon,
    ...    puis CONSTATE l'absence par un comptage. C'est le pré-nettoyage du
    ...    plan, à exécuter AVANT le cycle : une exécution interrompue ne doit
    ...    pas bloquer la suivante.
    [Arguments]    ${table}    ${key_field}    ${key_value}
    ...    ${allowlist}=${WRITE_TARGET_ALLOWLIST}
    ${deleted}=    Delete Table Entry    ${table}    ${key_field}    ${key_value}
    ...    allowlist=${allowlist}
    ${count}=    Count Table Entries With Key    ${table}    ${key_field}    ${key_value}
    Should Be Equal As Integers    ${count}    0
    ...    msg=Le point de départ n'est pas propre : ${count} enregistrement(s) '${key_value}' subsistent dans '${table}'.
    RETURN    ${deleted}

Remove Table Entry If Present
    [Documentation]    Filet de teardown : tente la suppression du reliquat et
    ...    **journalise** son propre échec au lieu de le propager, pour ne
    ...    jamais masquer l'échec réel du test. À appeler sur tous les chemins,
    ...    y compris après un échec en cours de cycle.
    [Arguments]    ${table}    ${key_field}    ${key_value}
    ...    ${allowlist}=${WRITE_TARGET_ALLOWLIST}
    ${status}    ${result}=    Run Keyword And Ignore Error
    ...    Delete Table Entry    ${table}    ${key_field}    ${key_value}
    ...    allowlist=${allowlist}
    IF    '${status}' != 'PASS'
        Log    Nettoyage de '${key_value}' dans '${table}' impossible : ${result}. Vérifier À LA MAIN que le système est revenu à son état initial.
        ...    level=WARN
    END
    RETURN    ${result}
