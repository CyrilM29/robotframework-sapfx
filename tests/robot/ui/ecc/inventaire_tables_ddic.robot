*** Settings ***
Documentation       Inventaire dynamique des tables ECC et S/4HANA : campagne MVP.
...                 Spec: specs/inventaire-tables-ecc-s4hana.md (sha256:a51caaa76a23, 2026-08-17)
...                 Generated from specs/inventaire-tables-ecc-s4hana.md by
...                 sap-generator (re-run the generator rather than hand-editing
...                 locators here). Un test par scénario du plan, dans son ordre.
...
...                 Périmètre MVP du handoff : scénarios 1 à 5, 8 et 10. Le
...                 scénario 6 (inspection SE11) est une extension déclarée du
...                 plan ; le scénario 7 (volumétrie) est désactivé par défaut
...                 (``measure_entry_count`` faux) ; le scénario 9 (comparaison
...                 de deux cibles) est de la logique pure, couverte hors SAP
...                 par ``tests/unit/test_ddic_inventory.py``, aucune seconde
...                 cible n'étant disponible.
...
...                 La campagne est en LECTURE SEULE : consultation du
...                 référentiel (TADIR), du dictionnaire (DD02L, DD07L) et
...                 sondes d'écran de sélection SE16, aucune donnée modifiée.
...                 Le barème de classification est relu sur la cible à chaque
...                 exécution (domaine ``TABCLASS``), jamais pris de mémoire ;
...                 les assertions portent sur des valeurs techniques, jamais
...                 un libellé localisé (convention 3). Aucun localisateur ici
...                 (convention 1) : ils vivent dans la bibliothèque (écrans
...                 standard SE16/SAPLALDB) et dans la couche resources.
...
...                 Exécution (A4H ou tout système de test) :
...
...                 robot --pythonpath src --outputdir results/ddic ^
...                 -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER ^
...                 -v "SAP_PASSWORD: Secret:..." -v SAP_CLIENT:001 ^
...                 tests/robot/ui/ecc/inventaire_tables_ddic.robot

Library             OperatingSystem
Resource            ../../../../resources/ecc_keywords.resource

Suite Setup         Open Campaign
Suite Teardown      Close Campaign

Test Tags           ecc    ddic    a4h


*** Variables ***
# Périmètre par défaut de la campagne (surchargable par -v) : les deux
# packages de démonstration présents sur tout système de test SAP.
@{CAMPAIGN_PACKAGES}        SAPBC_DATAMODEL    S_NWDEMO_MODEL_DDIC
@{CAMPAIGN_PREFIXES}        # vide par défaut : la sélection par packages suffit
${MAX_OBJECTS}              150
${BATCH_SIZE}               7
${PROBE_PER_CLASS}          2
${TARGET_ID}                a4h
${ARTIFACT_PATH}            ${OUTPUT DIR}${/}ddic_inventory_${TARGET_ID}.json


*** Test Cases ***
Initialiser une campagne en lecture seule
    [Documentation]    Scénario 1 : préflight scripting, session unique,
    ...                aucun modal résiduel avant la première requête DDIC.
    Scripting Should Be Fully Enabled
    ${sessions}=    List Sap Sessions
    Length Should Be    ${sessions}    1
    ${windows}=    Get Open Windows
    ${modals}=    Evaluate    [w for w in $windows if w["modal"]]
    Should Be Empty    ${modals}    msg=A modal window leaked into the campaign.

Valider le périmètre configurable
    [Documentation]    Scénario 2 : périmètre normalisé et borné, refus d'une
    ...                sélection vide ou d'une limite non positive.
    ${scope}=    Validate Ddic Scope    ${CAMPAIGN_PACKAGES}    ${CAMPAIGN_PREFIXES}
    ...    ${MAX_OBJECTS}    ${BATCH_SIZE}
    Set Suite Variable    ${SCOPE}    ${scope}
    Should Not Be Empty    ${scope}[packages]
    # Le refus ET sa RAISON sont assertés en une ligne : un périmètre vide et une
    # limite non positive doivent échouer chacun pour son propre motif.
    Run Keyword And Expect Error    *package ou un préfixe*
    ...    Validate Ddic Scope    ${EMPTY}    ${EMPTY}    ${MAX_OBJECTS}    ${BATCH_SIZE}
    Run Keyword And Expect Error    *strictement positif*
    ...    Validate Ddic Scope    ${CAMPAIGN_PACKAGES}    ${EMPTY}    0    ${BATCH_SIZE}

Découvrir les objets DDIC par package et préfixe
    [Documentation]    Scénario 3 : union TADIR bornée et déterministe des
    ...                packages et préfixes, tables ET vues (écart 2 du plan),
    ...                troncature toujours visible.
    ${names}    ${truncated}=    Discover DDIC Objects By Scope    ${SCOPE}
    Set Suite Variable    ${DISCOVERED}    ${names}
    Set Suite Variable    ${TRUNCATED}    ${truncated}
    Should Not Be Empty    ${names}
    ${unique_sorted}=    Evaluate    sorted(set($names))
    Should Be Equal    ${names}    ${unique_sorted}
    ...    msg=Discovery must be deduplicated and sorted.
    Should Be True    len($names) <= ${MAX_OBJECTS}

Enrichir et classer les objets avec le DDIC
    [Documentation]    Scénario 4 : barème relu sur la cible (domaine TABCLASS),
    ...                classification DD02L par lots de sélection multiple,
    ...                chaque objet reçoit exactement une classe normalisée.
    ${domain}=    Read Domain Values    TABCLASS
    ${class_map}=    Get Ddic Classification Map    ${domain}
    ${entries}=    Classify Ddic Objects    ${DISCOVERED}    ${class_map}
    ...    batch_size=${BATCH_SIZE}
    Set Suite Variable    ${ENTRIES}    ${entries}
    Length Should Be    ${entries}    ${{ len($DISCOVERED) }}
    ${classes}=    Evaluate    {e["class"] for e in $ENTRIES.values()}
    ${known}=    Evaluate
    ...    $classes <= {"table", "view", "non_consultable_ddic", "unknown"}
    Should Be True    ${known}    msg=Every object gets exactly one normalized class.
    ${tables}=    Evaluate
    ...    [n for n, e in $ENTRIES.items() if e["class"] == "table"]
    Should Not Be Empty    ${tables}
    ...    msg=The demo packages contain transparent tables; none classified.

Échantillonner la consultabilité réelle dans SE16
    [Documentation]    Scénario 5 : échantillon déterministe et borné par
    ...                classe, sonde SE16 par objet, fenêtres nettoyées entre
    ...                deux sondes, convergence DDIC/SE16 vérifiée sur les
    ...                classes sûres (table consultable, structure rejetée en
    ...                type E). Le résultat des vues est consigné sans
    ...                assertion forte : une vue d'aide peut légitimement
    ...                refuser le Data Browser.
    ${sample}=    Sample Ddic Objects For Probe    ${ENTRIES}    per_class=${PROBE_PER_CLASS}
    Should Not Be Empty    ${sample}
    FOR    ${name}    IN    @{sample}
        ${state}=    Reach Table Selection Screen    ${name}
        ${entry}=    Evaluate    $ENTRIES[$name]
        IF    $state["reached"]
            Record Ddic Probe    ${entry}    selection_screen_reached
        ELSE
            Record Ddic Probe    ${entry}    rejected    message_type=${state}[message_type]
            ...    detail=${state}[verdict]
        END
        Cancel Popup
    END
    FOR    ${name}    IN    @{sample}
        ${entry}=    Evaluate    $ENTRIES[$name]
        IF    $entry["class"] == "table"
            Should Be Equal    ${entry}[probe][status]    selection_screen_reached
            ...    msg=Transparent table '${name}' did not reach its selection screen.
        ELSE IF    $entry["class"] == "non_consultable_ddic"
            Should Be Equal    ${entry}[probe][status]    rejected
            ...    msg=Structure '${name}' unexpectedly opened in SE16.
            Should Be Equal    ${entry}[probe][message_type]    E
        END
    END
    ${probed}=    Evaluate
    ...    sum(1 for e in $ENTRIES.values() if e["probe"]["status"] != "not_probed")
    Should Be Equal As Integers    ${probed}    ${{ len($sample) }}

Produire l'artefact d'inventaire d'une cible
    [Documentation]    Scénario 8 : artefact JSON déterministe, trié, sans
    ...                secret, hash SHA-256 insensible à l'horodatage, résumé
    ...                couvrant tous les objets.
    ${proof}=    Write Ddic Inventory Artifact    ${ARTIFACT_PATH}    ${TARGET_ID}
    ...    ${SCOPE}    ${ENTRIES}    truncated=${TRUNCATED}
    File Should Exist    ${ARTIFACT_PATH}
    Should Match Regexp    ${proof}[sha256]    ^[0-9a-f]{64}$
    Should Be Equal As Integers    ${proof}[summary][discovered]
    ...    ${{ len($DISCOVERED) }}
    ${covered}=    Evaluate
    ...    $proof["summary"]["table"] + $proof["summary"]["view"] + $proof["summary"]["non_consultable_ddic"] + $proof["summary"]["unknown"]
    Should Be Equal As Integers    ${covered}    ${proof}[summary][discovered]
    ${content}=    Get File    ${ARTIFACT_PATH}
    Should Not Contain    ${content}    ${SAP_USER}
    ...    msg=The artifact must not embed any credential.

Fermer la campagne sur tous les chemins
    [Documentation]    Scénario 10 : aucune fenêtre modale résiduelle, une
    ...                seule session, celle de la campagne (la fermeture
    ...                elle-même vit dans le Suite Teardown, exécuté même
    ...                après un échec).
    Cancel Popup
    ${sessions}=    List Sap Sessions
    Length Should Be    ${sessions}    1


*** Keywords ***
Open Campaign
    [Documentation]    Ouverture de la cible + préflights + mode ALV du Data
    ...                Browser (réglage utilisateur persistant et idempotent).
    Open SAP And Log In
    Scripting Should Be Fully Enabled
    Use ALV Grid In Data Browser

Close Campaign
    [Documentation]    Fermeture garantie, y compris après un échec de test :
    ...                popups annulés puis déconnexion complète.
    Run Keyword And Ignore Error    Cancel Popup
    Close SAP
