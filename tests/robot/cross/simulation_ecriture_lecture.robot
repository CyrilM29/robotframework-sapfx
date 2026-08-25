*** Settings ***
Documentation       Simulation écriture / lecture cross-canal.
...                 Spec: specs/simulation-ecriture-lecture-cross-canal.md (sha256:426f946fb21c, 2026-08-22)
...                 Écrire à l'écran, constater par l'API, puis prouver le
...                 retour à l'état initial.
...                 Generated from specs/simulation-ecriture-lecture-cross-canal.md
...                 by sap-generator (re-run the generator rather than
...                 hand-editing locators here). Un test par scénario du plan,
...                 dans son ordre.
...
...                 ATTENTION, cette campagne ÉCRIT dans le système. Elle est
...                 **opt-in** à deux tours : un tag dédié (`write`) et une
...                 variable d'accord explicite. Sans
...                 `-v WRITE_SIMULATION_OPT_IN:yes`, tous ses tests sont
...                 SAUTÉS, y compris dans un run complet de `tests/robot/` :
...                 une campagne qui écrit ne doit jamais démarrer par surprise,
...                 et un tag seul se perd dès qu'on oublie un `--exclude`.
...
...                 Ce qu'elle prouve, et que la campagne de croisement ne peut
...                 pas prouver : `specs/croisement-ddic-odata-ecc-s4hana.md`
...                 qualifie des cibles d'écriture sur le seul `$metadata`, donc
...                 laisse `reversibility_observed` à `unknown`. Une annotation
...                 dit ce que le SERVICE permet ; elle ne dit rien de ce qui
...                 est réversible ni nettoyable. Cette suite produit
...                 l'observation datée qui manquait.
...
...                 Rien ici ne suppose une cible précise : la table visée, sa
...                 clé, l'ensemble d'entités qui la projette et le périmètre
...                 d'écriture vivent dans
...                 `resources/cross_channel_keywords.resource` (convention 1),
...                 les localisateurs d'écran dans le page object
...                 `resources/page_objects/se16_table_entry.resource`. Les
...                 nombres ne sont jamais gravés dans une assertion : la suite
...                 CROISE deux canaux et compare des états successifs, elle ne
...                 compare pas à une constante. Les verdicts portent sur des
...                 entiers, des noms techniques et des TYPES de message, jamais
...                 sur un texte localisé (convention 3).
...
...                 Exécution (A4H ou toute cible ECC / S/4HANA) :
...
...                 robot --pythonpath src --outputdir results/write ^
...                 -v WRITE_SIMULATION_OPT_IN:yes ^
...                 -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER ^
...                 -v "SAP_PASSWORD: Secret:..." -v SAP_CLIENT:001 ^
...                 -v API_BASE_URL:http://vhcala4hci:50000 -v API_USER:DEVELOPER ^
...                 -v "API_PASSWORD: Secret:..." -v API_CLIENT:001 ^
...                 tests/robot/cross/simulation_ecriture_lecture.robot

Library             Collections
Library             OperatingSystem
Resource            ../../../resources/cross_channel_keywords.resource
Resource            ../../../resources/page_objects/se16_table_entry.resource

Suite Setup         Open Write Simulation Campaign
Suite Teardown      Close Write Simulation Campaign

Test Tags           cross    write    simulation


*** Variables ***
${WRITE_SIMULATION_OPT_IN}      ${EMPTY}    # accord explicite : yes / true / 1 / on
${TARGET_ID}                    a4h
${OBSERVATION_PATH}             ${OUTPUT DIR}${/}reversibility_${TARGET_ID}.json


*** Test Cases ***
Ouvrir les deux canaux et établir l'état initial
    [Documentation]    Scénario 1 : les deux préflights, l'accord de mandant,
    ...                puis l'invariant de départ. Les deux canaux comptent la
    ...                même population ; sans cet invariant, aucune variation
    ...                ultérieure ne serait interprétable, et une divergence
    ...                arrête la campagne AVANT toute écriture.
    ${scope}=    Cross Channel Preflight
    Set Suite Variable    ${SCOPE}    ${scope}
    Should Not Be Empty    ${scope}[client]
    ${screen}=    Count Table Entries    ${WRITE_SIMULATION_TARGET}[table]
    ${api}=    Count Business Entities    ${ENTITY_PATH}
    ${mirror}=    Count Business Entities    ${MIRROR_PATH}
    Should Be True    ${screen} > 0
    ...    msg=La table cible est vide : l'invariant de départ serait vrai sans rien prouver.
    Should Be Equal As Integers    ${screen}    ${api}
    ...    msg=Comptes divergents AVANT toute écriture (écran ${screen}, API ${api}) : la campagne s'arrête, l'écart ne viendrait pas d'elle.
    Should Be Equal As Integers    ${mirror}    ${api}
    ...    msg=Les deux projections du même contenu divergent (${mirror} et ${api}) : la constatation ne serait pas indépendante.
    Set Suite Variable    ${SCREEN_INITIAL}    ${screen}
    Set Suite Variable    ${API_INITIAL}    ${api}
    Set Suite Variable    ${MIRROR_INITIAL}    ${mirror}

Garantir un point de départ propre
    [Documentation]    Scénario 2 : le pré-nettoyage a lieu AVANT le cycle, pas
    ...                après, pour qu'une exécution interrompue ne bloque pas la
    ...                suivante. Idempotent : il passe qu'un reliquat existe ou
    ...                non, et le compte attendu après nettoyage est déduit de
    ...                ce qui a réellement été supprimé, jamais supposé.
    ${deleted}=    Ensure Table Entry Is Absent    ${WRITE_SIMULATION_TARGET}[table]
    ...    ${WRITE_SIMULATION_TARGET}[key_field]    ${WRITE_SIMULATION_KEY}
    ...    allowlist=${WRITE_SIMULATION_ALLOWLIST}
    IF    ${deleted}
        Log    Reliquat d'une exécution précédente supprimé : ${WRITE_SIMULATION_KEY}    level=WARN
        ${expected}=    Evaluate    ${SCREEN_INITIAL} - 1
    ELSE
        ${expected}=    Set Variable    ${SCREEN_INITIAL}
    END
    ${screen}=    Count Table Entries    ${WRITE_SIMULATION_TARGET}[table]
    Should Be Equal As Integers    ${screen}    ${expected}
    ...    msg=Le pré-nettoyage n'a pas laissé le compte attendu (${screen} au lieu de ${expected}) : il a touché autre chose que l'enregistrement de test.
    ${api}=    Count Business Entities    ${ENTITY_PATH}
    Should Be Equal As Integers    ${api}    ${screen}
    ...    msg=Après nettoyage, les deux canaux divergent (écran ${screen}, API ${api}).
    ${mirror}=    Count Business Entities    ${MIRROR_PATH}
    # L'état de RÉFÉRENCE du cycle est celui d'APRÈS nettoyage : c'est lui que
    # la fin de cycle doit retrouver, pas celui d'avant.
    Set Suite Variable    ${SCREEN_REFERENCE}    ${screen}
    Set Suite Variable    ${API_REFERENCE}    ${api}
    Set Suite Variable    ${MIRROR_REFERENCE}    ${mirror}

Écrire par l'écran
    [Documentation]    Scénario 3 : création déclenchée depuis l'écran INITIAL
    ...                du Data Browser, valeurs saisies par nom technique de
    ...                champ, verdict lu sur le TYPE du message de statut.
    ...                La valeur de rattachement est RELUE dans les données
    ...                existantes : une valeur inventée serait refusée par le
    ...                contrôle du dictionnaire, ou pire, acceptée et fausse.
    ${references}=    Read All Business Entities    ${REFERENCE_PATH}
    ...    ${WRITE_SIMULATION_TARGET}[reference_key]    max_pages=2
    Should Not Be Empty    ${references}
    ...    msg=Aucune valeur de rattachement lisible : impossible d'écrire sans inventer une valeur.
    @{candidates}=    Create List
    FOR    ${row}    IN    @{references}
        Append To List    ${candidates}    ${row}[${WRITE_SIMULATION_TARGET}[reference_key]]
    END
    ${reference_value}=    Evaluate    sorted($candidates)[0]
    Set Suite Variable    ${REFERENCE_VALUE}    ${reference_value}
    ${values}=    Create Dictionary
    ...    ${WRITE_SIMULATION_TARGET}[key_field]=${WRITE_SIMULATION_KEY}
    ...    ${WRITE_SIMULATION_TARGET}[value_field]=${reference_value}
    Create Table Entry    ${WRITE_SIMULATION_TARGET}[table]
    ...    ${WRITE_SIMULATION_ALLOWLIST}    &{values}
    ${popup}=    Popup Is Present
    Should Not Be True    ${popup}
    ...    msg=Une fenêtre modale est restée ouverte après l'écriture : l'écran suivant hériterait d'un contexte non voulu.
    # Relecture par le canal qui a écrit : les clés de ligne sont les ids
    # TECHNIQUES de colonnes, jamais des libellés traduits.
    ${rows}=    Display Table Entries With Key    ${WRITE_SIMULATION_TARGET}[table]
    ...    ${WRITE_SIMULATION_TARGET}[key_field]    ${WRITE_SIMULATION_KEY}
    Length Should Be    ${rows}    1
    ...    msg=L'écran ne relit pas exactement une ligne pour la clé de test.
    Dictionary Should Contain Item    ${rows}[0]
    ...    ${WRITE_SIMULATION_TARGET}[value_field]    ${reference_value}

Constater par l'autre canal
    [Documentation]    Scénario 4 : le canal qui n'a pas écrit voit-il la même
    ...                chose ? Le compte gagne exactement un, et l'entité
    ...                existe avec les VALEURS écrites. C'est cette dernière
    ...                vérification qui distingue « une ligne est apparue » de
    ...                « ma ligne est apparue ».
    ${api}=    Count Business Entities    ${ENTITY_PATH}
    ${expected}=    Evaluate    ${API_REFERENCE} + 1
    Should Be Equal As Integers    ${api}    ${expected}
    ...    msg=Le canal de constatation ne voit pas l'écriture (compte ${api}, attendu ${expected}).
    ${mirror}=    Count Business Entities    ${MIRROR_PATH}
    ${mirror_expected}=    Evaluate    ${MIRROR_REFERENCE} + 1
    Should Be Equal As Integers    ${mirror}    ${mirror_expected}
    ...    msg=La seconde projection ne voit pas l'écriture (compte ${mirror}, attendu ${mirror_expected}).
    ${fields}=    Set Variable
    ...    ${WRITE_SIMULATION_TARGET}[entity_key],${WRITE_SIMULATION_TARGET}[entity_value]
    ${rows}=    Read Business Entity By Key    ${ENTITY_PATH}
    ...    ${WRITE_SIMULATION_TARGET}[entity_key]    ${WRITE_SIMULATION_KEY}    ${fields}
    Length Should Be    ${rows}    1
    ...    msg=L'entité écrite n'est pas lisible par sa clé sur le canal de constatation.
    Dictionary Should Contain Item    ${rows}[0]
    ...    ${WRITE_SIMULATION_TARGET}[entity_key]    ${WRITE_SIMULATION_KEY}
    Dictionary Should Contain Item    ${rows}[0]
    ...    ${WRITE_SIMULATION_TARGET}[entity_value]    ${REFERENCE_VALUE}
    Set Suite Variable    ${SEEN_BY_OBSERVATION}    ${True}
    Set Suite Variable    ${API_AFTER_WRITE}    ${api}
    ${screen}=    Count Table Entries    ${WRITE_SIMULATION_TARGET}[table]
    Set Suite Variable    ${SCREEN_AFTER_WRITE}    ${screen}

Supprimer par l'écran
    [Documentation]    Scénario 5 : suppression CIBLÉE, et elle seule. La
    ...                sélection est filtrée sur la clé puis RELUE avant
    ...                d'agir : toute ambiguïté interrompt le scénario sans
    ...                rien supprimer. Le menu de suppression de masse, voisin
    ...                immédiat de celui-ci, n'est jamais emprunté.
    ${deleted}=    Delete Table Entry    ${WRITE_SIMULATION_TARGET}[table]
    ...    ${WRITE_SIMULATION_TARGET}[key_field]    ${WRITE_SIMULATION_KEY}
    ...    allowlist=${WRITE_SIMULATION_ALLOWLIST}
    Should Be True    ${deleted}
    ...    msg=Rien n'a été supprimé alors que l'enregistrement de test venait d'être constaté par les deux canaux.

Constater la disparition par les deux canaux
    [Documentation]    Scénario 6 : un compte revenu à l'initial ne suffit pas.
    ...                Deux écritures et une suppression donneraient le même
    ...                nombre. La preuve est la disparition de l'entité
    ...                IDENTIFIÉE, vérifiée des deux côtés.
    ${screen}=    Count Table Entries    ${WRITE_SIMULATION_TARGET}[table]
    Should Be Equal As Integers    ${screen}    ${SCREEN_REFERENCE}
    ...    msg=L'écran ne revient pas à son état de référence (${screen} au lieu de ${SCREEN_REFERENCE}).
    ${api}=    Count Business Entities    ${ENTITY_PATH}
    Should Be Equal As Integers    ${api}    ${API_REFERENCE}
    ...    msg=Le canal de constatation ne revient pas à son état de référence (${api} au lieu de ${API_REFERENCE}).
    ${mirror}=    Count Business Entities    ${MIRROR_PATH}
    Should Be Equal As Integers    ${mirror}    ${MIRROR_REFERENCE}
    ...    msg=La seconde projection ne revient pas à son état de référence (${mirror} au lieu de ${MIRROR_REFERENCE}).
    ${on_screen}=    Count Table Entries With Key    ${WRITE_SIMULATION_TARGET}[table]
    ...    ${WRITE_SIMULATION_TARGET}[key_field]    ${WRITE_SIMULATION_KEY}
    Should Be Equal As Integers    ${on_screen}    0
    ...    msg=L'enregistrement de test subsiste dans la table : la donnée est LAISSÉE dans le système.
    ${fields}=    Set Variable
    ...    ${WRITE_SIMULATION_TARGET}[entity_key],${WRITE_SIMULATION_TARGET}[entity_value]
    ${rows}=    Read Business Entity By Key    ${ENTITY_PATH}
    ...    ${WRITE_SIMULATION_TARGET}[entity_key]    ${WRITE_SIMULATION_KEY}    ${fields}
    Should Be Empty    ${rows}
    ...    msg=L'entité répond encore à sa clé sur le canal de constatation : le nettoyage n'est pas prouvé.
    Set Suite Variable    ${GONE_FROM_OBSERVATION}    ${True}
    Set Suite Variable    ${SCREEN_AFTER_DELETE}    ${screen}
    Set Suite Variable    ${API_AFTER_DELETE}    ${api}

Produire l'observation de réversibilité
    [Documentation]    Scénario 7 : l'observation DATÉE que la campagne de
    ...                croisement ne peut pas produire, sous une forme
    ...                JSON-safe et déterministe. C'est elle qui remplace le
    ...                `unknown` de `reversibility_observed`, et elle ne porte
    ...                ni identifiant d'utilisateur ni secret.
    ${fields}=    Create Dictionary
    ...    target=${WRITE_SIMULATION_TARGET}[table]
    ...    key_field=${WRITE_SIMULATION_TARGET}[key_field]
    ...    key_value=${WRITE_SIMULATION_KEY}
    ...    entity_set=${WRITE_SIMULATION_TARGET}[entity_set]
    ...    service=${WRITE_SIMULATION_TARGET}[service]
    ...    write_channel=ecc    observation_channel=api
    ...    screen_count_before=${SCREEN_REFERENCE}
    ...    screen_count_after_write=${SCREEN_AFTER_WRITE}
    ...    screen_count_after_delete=${SCREEN_AFTER_DELETE}
    ...    api_count_before=${API_REFERENCE}
    ...    api_count_after_write=${API_AFTER_WRITE}
    ...    api_count_after_delete=${API_AFTER_DELETE}
    ...    seen_by_observation_channel=${SEEN_BY_OBSERVATION}
    ...    values_match=${True}
    ...    gone_from_observation_channel=${GONE_FROM_OBSERVATION}
    ${observation}=    Record Reversibility Observation    ${OBSERVATION_PATH}    ${fields}
    File Should Exist    ${OBSERVATION_PATH}
    Should Be Equal    ${observation}[verdict]    reversible
    ...    msg=Le cycle n'est pas prouvé réversible : ${observation}
    Should Be True    ${observation}[initial_state_restored]
    ${content}=    Get File    ${OBSERVATION_PATH}
    Should Not Contain    ${content}    ${SAP_USER}
    ...    msg=L'observation ne doit embarquer aucun identifiant.
    Should Not Contain    ${content}    password
    Log    Réversibilité constatée le ${observation}[observed_at_utc] : ${observation}

Fermer sur tous les chemins
    [Documentation]    Scénario 8 : aucune fenêtre modale résiduelle, une seule
    ...                session GUI (celle de la campagne), aucun identifiant
    ...                dans l'état servi du canal API, et aucune donnée de test
    ...                laissée dans le système. Les fermetures elles-mêmes
    ...                vivent dans le Suite Teardown, donc s'exécutent même
    ...                après un échec en cours de cycle.
    Cancel Popup
    ${client}=    Ecc Session Should Be Clean
    Should Be Equal    ${client}    ${SCOPE}[client]
    ${state}=    Api Channel State Should Not Leak Credentials
    Should Not Be Empty    ${state}[api_sessions]
    ${remaining}=    Count Table Entries With Key    ${WRITE_SIMULATION_TARGET}[table]
    ...    ${WRITE_SIMULATION_TARGET}[key_field]    ${WRITE_SIMULATION_KEY}
    Should Be Equal As Integers    ${remaining}    0
    ...    msg=La campagne laisse ${remaining} enregistrement(s) de test dans le système.


*** Keywords ***
Open Write Simulation Campaign
    [Documentation]    Ouverture des DEUX canaux, derrière l'accord explicite
    ...    d'écriture. Sans cet accord, TOUS les tests sont sautés et aucun
    ...    canal n'est ouvert : c'est ce qui rend la suite inoffensive dans un
    ...    run complet de `tests/robot/`, là où un tag seul dépend de la
    ...    mémoire de celui qui lance la commande.
    ${opted_in}=    Evaluate
    ...    str($WRITE_SIMULATION_OPT_IN).strip().lower() in ("yes", "true", "1", "on")
    Set Suite Variable    ${OPTED_IN}    ${opted_in}
    Set Suite Variable    ${ENTITY_PATH}
    ...    ${WRITE_SIMULATION_TARGET}[service]/${WRITE_SIMULATION_TARGET}[entity_set]
    Set Suite Variable    ${MIRROR_PATH}
    ...    ${WRITE_SIMULATION_TARGET}[mirror_service]/${WRITE_SIMULATION_TARGET}[mirror_entity_set]
    Set Suite Variable    ${REFERENCE_PATH}
    ...    ${WRITE_SIMULATION_TARGET}[service]/${WRITE_SIMULATION_TARGET}[reference_set]
    Set Suite Variable    ${SEEN_BY_OBSERVATION}    ${False}
    Set Suite Variable    ${GONE_FROM_OBSERVATION}    ${False}
    IF    not ${opted_in}
        Skip    Campagne d'ÉCRITURE dans un système réel : accord explicite requis (-v WRITE_SIMULATION_OPT_IN:yes). Cible déclarée : ${WRITE_SIMULATION_TARGET}[table].
    END
    Api Credentials Should Be Provided    ${API_PASSWORD}
    Open Api Channel
    Open SAP And Log In
    Use ALV Grid In Data Browser

Close Write Simulation Campaign
    [Documentation]    Nettoyage puis fermeture, sur TOUS les chemins : le
    ...    reliquat éventuel est retiré avant de fermer (une donnée de test
    ...    laissée dans un système partagé pollue les runs suivants), et le
    ...    canal API est fermé même si la fermeture GUI échoue. Rien n'est
    ...    tenté quand la campagne n'a pas été autorisée : il n'y a alors rien
    ...    d'ouvert.
    IF    not ${OPTED_IN}    RETURN
    Remove Table Entry If Present    ${WRITE_SIMULATION_TARGET}[table]
    ...    ${WRITE_SIMULATION_TARGET}[key_field]    ${WRITE_SIMULATION_KEY}
    ...    allowlist=${WRITE_SIMULATION_ALLOWLIST}
    Run Keyword And Ignore Error    Cancel Popup
    Run Keyword And Ignore Error    Close SAP
    Close Api Channel
