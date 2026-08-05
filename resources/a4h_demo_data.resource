*** Settings ***
Documentation       Préparation des jeux de données de démo de l'ABAP Platform Trial
...                 (A4H) : voir docs/sap-test-data.fr.md. Rend les smokes ECC
...                 data-driven déterministes : on garantit que SFLIGHT (modèle vol
...                 classique) et EPM (SNWD_*) contiennent des données avant de lire.
...                 Les générateurs standard SAP utilisés :
...                 - SFLIGHT : rapport ``SAPBC_DATA_GENERATOR`` (SE38) ;
...                 - EPM     : transaction ``SEPM_DG`` (génération canal standard).
...                 La génération est **conditionnelle** (uniquement si la table est
...                 vide) car elle prend plusieurs minutes.

Resource            ecc_keywords.resource


*** Keywords ***
Table Is Populated
    [Documentation]    Vrai si ``${table}`` affiche une grille de résultats non vide
    ...                dans SE16 (au moins une ligne matérialisée). Sonde courte :
    ...                une table vide reste sur l'écran de sélection.
    [Arguments]    ${table}    ${timeout}=15s
    ${shown}=    Run Keyword And Return Status    Display Table Contents    ${table}    timeout=${timeout}
    IF    not ${shown}    RETURN    ${False}
    ${rows}=    Read Displayed Grid    max_rows=1
    ${count}=    Get Length    ${rows}
    RETURN    ${{ ${count} > 0 }}

Generate Flight Demo Data
    [Documentation]    Lance ``SAPBC_DATA_GENERATOR`` (SE38) avec ses paramètres par
    ...                défaut (jeu minimal) : supprime puis régénère les tables du
    ...                modèle vol (SPFLI, SFLIGHT, SBOOK…). Long : jusqu'à quelques
    ...                minutes sur le trial.
    Run Report    SAPBC_DATA_GENERATOR
    # Écran de sélection du générateur -> exécuter tel quel (F8).
    Send Vkey    8
    Wait Until Busy Done    timeout=600s
    Confirm Popup
    Wait Until Busy Done    timeout=600s

Ensure Flight Demo Data Exists
    [Documentation]    Garantit des données dans SFLIGHT : vérifie via SE16, sinon
    ...                lance le générateur puis revérifie. Prévu pour Suite Setup.
    ${populated}=    Table Is Populated    SFLIGHT
    IF    not ${populated}
        Generate Flight Demo Data
        ${populated}=    Table Is Populated    SFLIGHT    timeout=30s
        Should Be True    ${populated}    msg=SFLIGHT is still empty after SAPBC_DATA_GENERATOR
    END

Generate EPM Demo Data
    [Documentation]    Lance la génération EPM standard (transaction ``SEPM_DG``,
    ...                rapport SEPM_DG_EPM_STD_CHANNEL) avec ses paramètres par
    ...                défaut. Long : plusieurs minutes possibles.
    Go To Transaction    SEPM_DG
    Send Vkey    8
    Wait Until Busy Done    timeout=900s
    Confirm Popup
    Wait Until Busy Done    timeout=900s

Ensure EPM Demo Data Exists
    [Documentation]    Garantit des données dans SNWD_PO (commandes d'achat EPM) :
    ...                vérifie via SE16, sinon lance ``SEPM_DG`` puis revérifie.
    ${populated}=    Table Is Populated    SNWD_PO
    IF    not ${populated}
        Generate EPM Demo Data
        ${populated}=    Table Is Populated    SNWD_PO    timeout=30s
        Should Be True    ${populated}    msg=SNWD_PO is still empty after SEPM_DG
    END
