*** Settings ***
Documentation       **Sentinelle de dérive** : la surveillance d'écrans SANS tests
...                 scriptés : chaque transaction surveillée est perçue (signature
...                 structurée + empreinte visuelle) et comparée à sa référence
...                 mémorisée dans ``${WATCH_DIR}`` (à committer). Première
...                 exécution = les références sont créées ; les suivantes ne
...                 remontent QUE la dérive (champ disparu, bouton déplacé, rendu
...                 altéré), nommée ligne à ligne, l'entrée idéale d'un run de
...                 veille nocturne, avant qu'un seul test n'échoue.
...
...                 Par défaut la sentinelle RAPPORTE (le run reste vert et le
...                 rapport agrégé arrive dans le log) ; ``-v FAIL_ON_DRIFT:True``
...                 la transforme en assertion. Étendre la surveillance = ajouter
...                 un tcode à ``@{WATCHED_TRANSACTIONS}``, aucun scénario à
...                 écrire.
...
...                 ``${PER_RESOLUTION}`` (True ici) donne à chaque **géométrie de
...                 capture** sa propre référence VISUELLE, le canal structurel
...                 restant partagé : la même surveillance vaut sur des postes qui
...                 n'affichent pas pareil, sans qu'un changement d'échelle se
...                 rapporte comme une dérive. ``-v PER_RESOLUTION:False`` revient
...                 au fichier unique.
...
...                   robot --pythonpath src -v SAP_CONNECTION:... -v SAP_USER:...
...                   -v "SAP_PASSWORD: Secret:..." tests/robot/ecc_drift_sentinel.robot

Library             Collections
Resource            ../../resources/ecc_keywords.resource

Suite Setup         Open SAP And Log In
Suite Teardown      Close SAP


*** Variables ***
# Les écrans surveillés : l'écran initial de chaque transaction critique.
@{WATCHED_TRANSACTIONS}    SE16    SE38    SM50
${WATCH_DIR}               screen_watch
${FAIL_ON_DRIFT}           False
${PER_RESOLUTION}          ${True}


*** Test Cases ***
Watch Critical Screens
    [Documentation]    Un passage de sentinelle sur toutes les transactions
    ...                surveillées ; le rapport Markdown agrégé est journalisé
    ...                (et le run échoue si ``FAIL_ON_DRIFT`` et au moins une
    ...                dérive).
    ${outcomes}=    Create List
    FOR    ${tcode}    IN    @{WATCHED_TRANSACTIONS}
        Go To Transaction    ${tcode}
        Wait Until Busy Done
        ${verdict}=    Check Screen Against Watch    ${tcode}
        ...    directory=${WATCH_DIR}    fail_on_drift=${FAIL_ON_DRIFT}
        ...    per_resolution=${PER_RESOLUTION}
        Append To List    ${outcomes}    ${verdict}
    END
    # Le verdict porte EXACTEMENT les champs de WatchOutcome : le reconstruire
    # champ par champ perdait la dérive localisée par tuile (et la note
    # d'échelle) dans le rapport agrégé.
    ${verdicts}=    Evaluate
    ...    [sapfx_common.screen_watch.WatchOutcome(**o) for o in $outcomes]
    ...    modules=sapfx_common.screen_watch
    ${report}=    Evaluate
    ...    sapfx_common.screen_watch.render_watch_report($verdicts)
    ...    modules=sapfx_common.screen_watch
    Log    ${report}
