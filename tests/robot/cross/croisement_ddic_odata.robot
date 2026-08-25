*** Settings ***
Documentation       Croisement DDIC et OData : disponibilité et cohérence des données.
...                 Spec: specs/croisement-ddic-odata-ecc-s4hana.md (sha256:a291af3a388c, 2026-08-22)
...                 Generated from specs/croisement-ddic-odata-ecc-s4hana.md by
...                 sap-generator (re-run the generator rather than hand-editing
...                 locators here). Un test par scénario du plan, dans son ordre.
...
...                 Le même fait de données vérifié par DEUX canaux indépendants
...                 sur un seul système : le Data Browser d'un côté, le canal
...                 OData de l'autre. Campagne en **lecture seule** : aucun des
...                 deux canaux ne crée, ne modifie ni ne supprime quoi que ce
...                 soit ; le scénario « candidats écriture » IDENTIFIE sans
...                 écrire.
...
...                 Rien ici ne suppose une cible précise. Les services, les
...                 tables, les couples et la liste blanche d'écriture vivent
...                 dans `resources/cross_channel_keywords.resource`
...                 (convention 1) ; les nombres ne sont jamais gravés dans une
...                 assertion : la suite CROISE deux canaux, elle ne compare pas
...                 à une constante. Les assertions portent sur des entiers, des
...                 noms techniques, des statuts HTTP et des codes d'erreur
...                 OData, jamais sur un message localisé (convention 3).
...
...                 Le scénario 8 du plan (comparer deux cibles) s'exécute ici
...                 dans sa moitié réalisable : aucune seconde cible n'étant
...                 disponible, la suite prouve la stabilité de la comparaison
...                 et son refus des périmètres incompatibles ; les cas de
...                 dérive sont couverts hors SAP par
...                 `tests/unit/test_cross_channel.py`.
...
...                 Exécution (A4H ou toute cible ECC / S/4HANA) :
...
...                 robot --pythonpath src --outputdir results/cross ^
...                 -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER ^
...                 -v "SAP_PASSWORD: Secret:..." -v SAP_CLIENT:001 ^
...                 -v API_BASE_URL:http://vhcala4hci:50000 -v API_USER:DEVELOPER ^
...                 -v "API_PASSWORD: Secret:..." -v API_CLIENT:001 ^
...                 tests/robot/cross/croisement_ddic_odata.robot

Library             OperatingSystem
Resource            ../../../resources/cross_channel_keywords.resource

Suite Setup         Open Cross Channel Campaign
Suite Teardown      Close Cross Channel Campaign

Test Tags           cross    ddic    odata


*** Variables ***
${TARGET_ID}                a4h
${MAX_ENTITY_SETS}          60
${MAX_COUPLES}              20
${MAX_FIELD_CONTRACTS}      5
${ARTIFACT_PATH}            ${OUTPUT DIR}${/}cross_channel_${TARGET_ID}.json
${ARTIFACT_REPLAY_PATH}     ${OUTPUT DIR}${/}cross_channel_${TARGET_ID}.replay.json


*** Test Cases ***
Ouvrir les deux canaux et prouver qu'ils répondent
    [Documentation]    Scénario 1 : les deux préflights et l'accord de mandant
    ...                en un verdict unique. Un préflight en échec nomme sa
    ...                remédiation ici, au lieu de laisser un scénario métier
    ...                échouer plus loin sur une erreur incompréhensible.
    ${scope}=    Cross Channel Preflight    ${CAMPAIGN_SERVICES}
    ...    ${MAX_ENTITY_SETS}    ${MAX_COUPLES}    ${MAX_FIELD_CONTRACTS}
    Set Suite Variable    ${SCOPE}    ${scope}
    Should Not Be Empty    ${scope}[services]
    Should Not Be Empty    ${scope}[client]
    # Le refus des mandants divergents est la garde qui empêche de comparer
    # deux populations : il doit échouer pour SA raison, pas par accident.
    Run Keyword And Expect Error    *Mandants divergents*
    ...    Validate Cross Channel Scope    ${CAMPAIGN_SERVICES}    001    002
    ...    ${MAX_ENTITY_SETS}    ${MAX_COUPLES}    ${MAX_FIELD_CONTRACTS}
    Run Keyword And Expect Error    *strictement positif*
    ...    Validate Cross Channel Scope    ${CAMPAIGN_SERVICES}    ${scope}[client]
    ...    ${scope}[client]    0    ${MAX_COUPLES}    ${MAX_FIELD_CONTRACTS}
    ${coverage}=    Business Services Should Be Published    ${scope}[services]
    Set Suite Variable    ${COVERAGE}    ${coverage}
    Should Be True    ${coverage}[catalog_size] > 0
    ...    msg=Le catalogue de la cible est vide : la perception du canal API n'a rien vu.

Percevoir le contrat de chaque service du périmètre
    [Documentation]    Scénario 2 : une fiche de contrat par ensemble
    ...                d'entités, tirée du service lui-même. Un service
    ...                illisible bloque CE service, pas la campagne : les
    ...                autres sont instruits avant que l'échec ne soit rendu.
    [Tags]    api
    @{contracts}=    Create List
    @{unreadable}=    Create List
    FOR    ${service}    IN    @{SCOPE}[services]
        ${status}    ${contract}=    Run Keyword And Ignore Error
        ...    List Business Service Entity Sets    ${service}    ${MAX_ENTITY_SETS}
        IF    '${status}' == 'PASS'
            Append To List    ${contracts}    ${contract}
        ELSE
            Append To List    ${unreadable}    ${service}: ${contract}
        END
    END
    Set Suite Variable    ${SERVICE_CONTRACTS}    ${contracts}
    Should Be Empty    ${unreadable}    msg=Services dont les métadonnées sont illisibles : ${unreadable}
    Should Not Be Empty    ${contracts}
    FOR    ${contract}    IN    @{contracts}
        Should Not Be Empty    ${contract}[entity_sets]
        ...    msg=Le service ${contract}[service_path] ne publie aucun ensemble d'entités.
        Should Be True    len($contract["entity_sets"]) <= ${MAX_ENTITY_SETS}
        # Une borne atteinte est un indicateur, jamais un succès silencieux.
        ${expected_truncation}=    Evaluate
        ...    len($contract["entity_sets"]) == ${MAX_ENTITY_SETS}
        Should Be True    $contract["truncated"] == $expected_truncation or not $contract["truncated"]
        FOR    ${record}    IN    @{contract}[entity_sets]
            Should Not Be Empty    ${record}[entity_set]
            Should Be True    isinstance($record["addressable"], bool)
            Should Be True    isinstance($record["draft_enabled"], bool)
        END
    END

Prouver l'existence réelle de chaque entity set adressable
    [Documentation]    Scénario 3 : sondage groupé et TOLÉRANT. Un ensemble
    ...                déclaré non adressable est écarté du sondage et consigné
    ...                comme tel : sa déclaration est honorée, ce n'est pas une
    ...                anomalie. L'anomalie, la seule, est un ensemble déclaré
    ...                adressable qui ne répond pas. Aucun refus n'interrompt
    ...                le sondage des suivants.
    [Tags]    api
    @{probes}=    Create List
    FOR    ${contract}    IN    @{SERVICE_CONTRACTS}
        ${verdicts}=    Cross Channel Existence Should Be Consistent    ${contract}
        ...    ${MAX_ENTITY_SETS}
        # La somme des verdicts couvre TOUS les ensembles de la fiche.
        Length Should Be    ${verdicts}    ${{ len($contract["entity_sets"]) }}
        FOR    ${verdict}    IN    @{verdicts}
            Set To Dictionary    ${verdict}    service=${contract}[service_path]
            Append To List    ${probes}    ${verdict}
        END
    END
    Set Suite Variable    ${PROBE_VERDICTS}    ${probes}
    Should Not Be Empty    ${probes}
    ${available}=    Evaluate    [p for p in $probes if p["verdict"] == "available"]
    Should Not Be Empty    ${available}
    ...    msg=Aucun ensemble d'entités n'a répondu : le croisement n'aurait aucune matière.
    # Un ensemble qui a répondu porte un compte entier ; un refus porte un code
    # technique, jamais un message localisé.
    FOR    ${probe}    IN    @{available}
        Should Be True    isinstance($probe["count"], int)
        ...    msg=L'ensemble ${probe}[entity_set] a répondu sans compte exploitable.
    END
    ${honored}=    Evaluate
    ...    [p for p in $probes if p["verdict"] == "declared_not_addressable"]
    Log    Ensembles non adressables déclarés, écartés du sondage : ${honored}

Croiser la volumétrie des couples déclarés
    [Documentation]    Scénario 4 : pour chaque couple du dictionnaire, le
    ...                comptage OData face au comptage SE16, filtres déclarés
    ...                appliqués de chaque côté. Un couple `equal_under_filter`
    ...                fait aussi relever le compte SANS filtre : l'écart est
    ...                consigné, jamais masqué. Un couple `not_comparable`
    ...                n'est jamais asserté en égalité. Les ensembles sans
    ...                couple déclaré sont rapportés, jamais appariés.
    Should Be True    len($CROSS_CHANNEL_COUPLES) <= ${MAX_COUPLES}
    ...    msg=Le dictionnaire de correspondance dépasse la borne max_couples de la campagne.
    @{verdicts}=    Create List
    FOR    ${couple}    IN    @{CROSS_CHANNEL_COUPLES}
        ${verdict}=    Cross Channel Volume Should Match    ${couple}
        Append To List    ${verdicts}    ${verdict}
    END
    Set Suite Variable    ${COUPLE_VERDICTS}    ${verdicts}
    ${compared}=    Evaluate    [v for v in $verdicts if v["verdict"] != "not_compared"]
    Should Not Be Empty    ${compared}
    ...    msg=Aucun couple n'a réellement été croisé.
    FOR    ${verdict}    IN    @{compared}
        Should Be True    ${verdict}[match]
        ...    msg=Couple non concordant : ${verdict}
    END
    # Un couple sous filtre doit avoir relevé l'écart sans filtre : c'est lui
    # qui documente la projection métier ou les brouillons.
    ${filtered}=    Evaluate
    ...    [v for v in $verdicts if v["expected"] == "equal_under_filter" and v["api_filter"]]
    FOR    ${verdict}    IN    @{filtered}
        Should Be True    isinstance($verdict["api_count_unfiltered"], int)
        ...    msg=Le compte sans filtre de ${verdict}[entity_set] n'a pas été relevé.
    END
    # Les ensembles sondés sans couple déclaré sont RAPPORTÉS, jamais assimilés.
    ${coupled}=    Evaluate    {v["entity_set"] for v in $verdicts}
    FOR    ${probe}    IN    @{PROBE_VERDICTS}
        ${declared}=    Evaluate    $probe["entity_set"] in $coupled
        IF    ${declared}
            Set To Dictionary    ${probe}    couple=declared
        ELSE
            Set To Dictionary    ${probe}    couple=no_declared_couple
        END
    END
    ${uncoupled}=    Evaluate
    ...    sorted({p["entity_set"] for p in $PROBE_VERDICTS if p["couple"] == "no_declared_couple"})
    Log    Ensembles d'entités sans couple déclaré (rapportés, non appariés) : ${uncoupled}

Croiser le contrat de champs des couples déclarés
    [Documentation]    Scénario 5 : propriétés de l'entity type contre champs
    ...                DD03L de la version active, rapprochés en trois passes
    ...                ordonnées. Le résultat est un rapport à trois ensembles,
    ...                pas un verdict binaire : c'est ce triplet qui rend une
    ...                dérive de schéma lisible. Les lignes techniques de la
    ...                table (marqueur d'include, champ mandant, champs
    ...                d'administration, références par identifiant technique)
    ...                sont naturellement orphelines côté DDIC, et ce n'est pas
    ...                une anomalie.
    Should Be True    len($CROSS_CHANNEL_FIELD_COUPLES) <= ${MAX_FIELD_CONTRACTS}
    ...    msg=Plus de contrats de champs demandés que la borne max_field_contracts.
    @{contracts}=    Create List
    @{tables}=    Create List
    FOR    ${couple}    IN    @{CROSS_CHANNEL_FIELD_COUPLES}
        ${record}    ${fields}=    Cross Channel Field Contract    ${couple}
        Append To List    ${contracts}    ${record}
        # Seuls les comptages SANS filtre décrivent la table : reprendre celui
        # d'un couple filtré donnerait à `SNWD_BPA` la volumétrie des seuls
        # fournisseurs, présentée comme son total.
        ${counts}=    Evaluate
        ...    {v["table"]: v["ddic_count"] for v in $COUPLE_VERDICTS if not v["ddic_filter"]}
        ${count}=    Evaluate    $counts.get($record["table"])
        ${table}=    Describe Ddic Table    ${couple}[table]    ${fields}    ${count}
        Append To List    ${tables}    ${table}
        # Les trois ensembles PARTITIONNENT les propriétés : rien ne se perd,
        # rien n'est apparié deux fois.
        ${summary}=    Set Variable    ${record}[summary]
        Should Be Equal As Integers    ${summary}[properties]
        ...    ${{ $summary["matched"] + $summary["unmatched_properties"] }}
        # Un alias déclaré est TOUJOURS prioritaire sur la normalisation.
        ${aliased}=    Evaluate    $couple.get("aliases") or {}
        ${vias}=    Evaluate    {m["property"]: m["via"] for m in $record["matched"]}
        FOR    ${property}    ${field}    IN    &{aliased}
            ${via}=    Evaluate    $vias.get($property) or ""
            Should Be Equal    ${via}    alias
            ...    msg=L'alias déclaré ${property} vers ${field} n'a pas été appliqué.
        END
        # Le rapprochement est INDÉPENDANT de l'ordre de lecture.
        ${reversed}=    Evaluate    list(reversed($fields))
        ${again}=    Compare Odata Properties With Ddic Fields
        ...    ${{ [m["property"] for m in $record["matched"]] + [p["property"] for p in $record["unmatched_properties"]] }}
        ...    ${reversed}    aliases=${aliased}
        Should Be Equal    ${again}[summary][matched]    ${summary}[matched]
        ...    msg=Le rapprochement dépend de l'ordre de lecture des champs.
        # La normalisation consciente des acronymes ne perd jamais un
        # appariement que la coupure naïve trouverait.
        ${naive}=    Compare Odata Properties With Ddic Fields
        ...    ${{ [m["property"] for m in $record["matched"]] + [p["property"] for p in $record["unmatched_properties"]] }}
        ...    ${fields}    aliases=${aliased}    acronym_aware=${False}
        Should Be True    ${summary}[matched] >= ${naive}[summary][matched]
        ...    msg=La normalisation consciente des acronymes apparie moins que la coupure naïve.
    END
    Set Suite Variable    ${FIELD_CONTRACTS}    ${contracts}
    Set Suite Variable    ${TABLE_RECORDS}    ${tables}
    ${matched}=    Evaluate    sum(c["summary"]["matched"] for c in $contracts)
    Should Be True    ${matched} > 0
    ...    msg=Aucune propriété appariée : le rapprochement n'a rien prouvé.

Identifier les candidats à une simulation écriture
    [Documentation]    Scénario 6 : identification SANS écriture. Seule une
    ...                capacité réellement DÉCLARÉE par le service engage : une
    ...                capacité obtenue par défaut ne prouve rien, puisque le
    ...                service s'est tu. La liste blanche métier tranche
    ...                ensuite. Un service qui ne déclare aucune restriction ne
    ...                produit donc aucun candidat par ce seul fait.
    [Tags]    api
    @{candidates}=    Create List
    FOR    ${service}    IN    @{SCOPE}[services]
        ${found}=    List Write Simulation Candidates    ${service}
        FOR    ${candidate}    IN    @{found}
            Append To List    ${candidates}    ${candidate}
        END
    END
    Set Suite Variable    ${WRITE_CANDIDATES}    ${candidates}
    FOR    ${candidate}    IN    @{candidates}
        Should Be Equal    ${candidate}[evidence]    declared
        ...    msg=Candidat appuyé sur une capacité par défaut : le service ne l'a jamais déclarée.
        Should Contain    ${WRITE_ALLOWLIST}    ${candidate}[entity_set]
        ...    msg=Candidat hors liste blanche métier : ${candidate}[entity_set]
        Should Be Equal    ${candidate}[reversibility_observed]    unknown
        ...    msg=La réversibilité ne se déduit pas d'une déclaration de métadonnées.
        Should Not Be Empty    ${candidate}[keys]
        ...    msg=Un candidat sans clé ne peut pas être ciblé ni nettoyé.
    END
    # Une capacité par défaut n'est jamais une autorisation : sans la garde,
    # les ensembles muets du service remonteraient comme candidats.
    ${silent}=    Evaluate
    ...    [c for c in $WRITE_CANDIDATES if c["evidence"] != "declared"]
    Should Be Empty    ${silent}
    # Nuance rendue visible plutôt que tue : un candidat peut passer la garde
    # en déclarant des RESTRICTIONS sur d'autres verbes, sa capacité autorisée
    # restant due au silence du service. À confirmer avant toute écriture.
    ${par_defaut}=    Evaluate
    ...    [c["entity_set"] for c in $WRITE_CANDIDATES if not c["declared_allowed"]]
    Log    Candidats dont la capacité autorisée repose sur le silence du service : ${par_defaut}

Produire l'artefact de croisement de la cible
    [Documentation]    Scénario 7 : document JSON trié, déterministe, sans
    ...                identifiant ni mot de passe, au schéma versionné. Son
    ...                empreinte exclut l'horodatage : deux exécutions sur les
    ...                mêmes données donnent la même empreinte.
    ${proof}=    Write Cross Channel Artifact    ${ARTIFACT_PATH}    ${TARGET_ID}
    ...    ${SCOPE}    ${COVERAGE}    ${SERVICE_CONTRACTS}    ${PROBE_VERDICTS}
    ...    ${COUPLE_VERDICTS}    ${FIELD_CONTRACTS}    ${TABLE_RECORDS}
    ...    ${WRITE_CANDIDATES}
    File Should Exist    ${ARTIFACT_PATH}
    Should Match Regexp    ${proof}[sha256]    ^[0-9a-f]{64}$
    Should Be Equal As Integers    ${proof}[summary][couples]
    ...    ${{ len($COUPLE_VERDICTS) }}
    Should Be Equal As Integers    ${proof}[summary][entity_sets]
    ...    ${{ sum(len(c["entity_sets"]) for c in $SERVICE_CONTRACTS) }}
    ${content}=    Get File    ${ARTIFACT_PATH}
    Should Not Contain    ${content}    ${SAP_USER}
    ...    msg=L'artefact ne doit embarquer aucun identifiant.
    Should Not Contain    ${content}    password
    # Empreinte insensible au moment du relevé : le même contenu, plus tard.
    ${replay}=    Write Cross Channel Artifact    ${ARTIFACT_REPLAY_PATH}    ${TARGET_ID}
    ...    ${SCOPE}    ${COVERAGE}    ${SERVICE_CONTRACTS}    ${PROBE_VERDICTS}
    ...    ${COUPLE_VERDICTS}    ${FIELD_CONTRACTS}    ${TABLE_RECORDS}
    ...    ${WRITE_CANDIDATES}
    Should Be Equal    ${replay}[sha256]    ${proof}[sha256]
    ...    msg=L'empreinte dépend de l'horodatage : deux relevés identiques doivent la partager.

Comparer deux artefacts à périmètre équivalent
    [Documentation]    Scénario 8, dans sa moitié réalisable : aucune seconde
    ...                cible n'est disponible, donc la suite prouve ce qui se
    ...                prouve ici, à savoir qu'une différence d'ordre ou
    ...                d'horodatage ne crée AUCUN écart, et qu'un périmètre
    ...                incompatible bloque la comparaison au lieu de produire
    ...                des écarts trompeurs. Les cas de dérive (entity set
    ...                apparu, adressabilité changée, contrat dégradé) sont
    ...                couverts hors SAP par tests/unit/test_cross_channel.py.
    [Tags]    offline
    ${comparison}=    Compare Cross Channel Artifact Files    ${ARTIFACT_PATH}
    ...    ${ARTIFACT_REPLAY_PATH}
    Should Be True    ${comparison}[compatible]
    Should Be Empty    ${comparison}[only_in_a]
    Should Be Empty    ${comparison}[only_in_b]
    Should Be Empty    ${comparison}[addressability_changed]
    Should Be Empty    ${comparison}[volume_verdict_changed]
    Should Be Empty    ${comparison}[field_contract_changed]
    Should Be True    ${comparison}[common] > 0
    # Périmètres différents : comparaison marquée non équivalente, pas d'écart
    # inventé.
    ${narrow}=    Evaluate    dict($SCOPE, services=$SCOPE["services"][:1])
    ${other}=    Build Cross Channel Artifact    ${TARGET_ID}    ${narrow}
    ...    2026-01-01T00:00:00+00:00    catalog=${COVERAGE}
    ...    services=${SERVICE_CONTRACTS}
    ${raw}=    Get File    ${ARTIFACT_PATH}
    ${incompatible}=    Compare Cross Channel Artifacts    ${raw}    ${other}
    Should Not Be True    ${incompatible}[compatible]
    Should Not Be Empty    ${incompatible}[incompatibility_reasons]

Fermer la campagne sur tous les chemins
    [Documentation]    Scénario 9 : aucune fenêtre modale résiduelle, une seule
    ...                session GUI, celle de la campagne, et le canal API
    ...                toujours identifié par son alias. Les deux fermetures
    ...                elles-mêmes vivent dans le Suite Teardown, donc
    ...                s'exécutent même après un échec.
    Cancel Popup
    ${client}=    Ecc Session Should Be Clean
    Should Be Equal    ${client}    ${SCOPE}[client]
    ${state}=    Api Channel State Should Not Leak Credentials
    Should Not Be Empty    ${state}[api_sessions]


*** Keywords ***
Open Cross Channel Campaign
    [Documentation]    Ouverture des DEUX canaux et réglage du Data Browser en
    ...                grille ALV (réglage utilisateur persistant et
    ...                idempotent, sans lequel la sortie SE16 est une liste
    ...                classique sans objet de grille exploitable).
    Api Credentials Should Be Provided    ${API_PASSWORD}
    Open Api Channel
    Open SAP And Log In
    Use ALV Grid In Data Browser

Close Cross Channel Campaign
    [Documentation]    Fermeture garantie des DEUX canaux, y compris après un
    ...                échec de préflight ou de scénario : une session GUI
    ...                orpheline décale les index de connexion de la prochaine
    ...                exécution, et une session API laissée ouverte est une
    ...                session utilisateur restée ouverte côté serveur. Le
    ...                canal API est fermé même si la fermeture GUI échoue.
    Run Keyword And Ignore Error    Cancel Popup
    Run Keyword And Ignore Error    Close SAP
    Close Api Channel
