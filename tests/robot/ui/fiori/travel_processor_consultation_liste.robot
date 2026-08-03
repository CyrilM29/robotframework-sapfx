*** Settings ***
Documentation       Consultation de la liste des voyages — application Fiori Elements
...                 Spec: specs/travel-processor-consultation-liste.md (sha256:85cf71c662da, 2026-07-25)
...                 v4 « Travel processor » (`sap.fe.cap.travel`, List Report
...                 `TravelList`) servie par la cible locale **cap-sflight** —
...                 generated from specs/travel-processor-consultation-liste.md by
...                 sap-generator (re-run the generator rather than hand-editing
...                 locators here). Un test par scénario du plan, dans son ordre.
...
...                 Périmètre strictement **consultation** : chargement, lecture du
...                 compteur d'en-tête, recherche libre, retour à l'état non filtré.
...                 Les actions `acceptTravel` / `rejectTravel` / `deductDiscount` et
...                 la création ne sont jamais déclenchées.
...
...                 Assertions **indépendantes de la langue** : nombres extraits du
...                 compteur (le rendu live est en français, séparateur de milliers
...                 U+202F), comptages de contrôles UI5, contenu de DONNÉES des
...                 lignes — jamais un libellé d'interface ni un en-tête de colonne
...                 (convention 3). Assertions **relationnelles** plutôt que calées
...                 sur le jeu de démonstration (filtré < total, restauré = mesuré
...                 avant filtrage dans le MÊME run) : la volumétrie de cap-sflight
...                 peut évoluer.
...
...                 Aucun localisateur ici (convention 1) : ils vivent tous dans
...                 `resources/page_objects/fiori_travel_list.resource`.
...
...                 Prérequis : la cible tourne (`cd _cap-sflight && npx cds watch`
...                 → http://localhost:4004). Exécution :
...
...                   robot --pythonpath src ^
...                     --outputdir results/fiori ^
...                     tests/robot/ui/fiori/travel_processor_consultation_liste.robot

Resource            ../../../../resources/fiori_keywords.resource
Resource            ../../../../resources/page_objects/fiori_travel_list.resource
Variables           ../../../../variables/env_local.py

Suite Setup         Open Travel Processor    ${TRAVEL_APP_URL}
Suite Teardown      Close Fiori
Test Teardown       Log Travel List Diagnostics On Failure

Test Tags           fiori    fiori-elements    cap-sflight


*** Variables ***
# Donnée métier du jeu de démonstration (une valeur recherchée, pas un
# localisateur) : le terme apparaît dans le nom de l'agence « Aussie Travel ».
${TRAVEL_SEARCH_TERM}       Aussie


*** Test Cases ***
La liste des voyages se charge et affiche des lignes
    [Documentation]    Scénario 1 du plan. L'application démarre et matérialise des
    ...                lignes. Le nombre exact n'est jamais asserté : il plafonne au
    ...                seuil de croissance de la table (30 relevé live), qui n'est pas
    ...                une volumétrie métier.
    Travel List Should Be Displayed
    ${rows}=    Count Displayed Travel Rows
    Should Be True    ${rows} > 0
    ...    msg=La liste des voyages est rendue mais ne matérialise aucune ligne

Le compteur d'en-tête reflète la volumétrie totale
    [Documentation]    Scénario 2 du plan. Le compteur d'en-tête est la SEULE source
    ...                de volumétrie. L'assertion porte sur la valeur numérique
    ...                extraite — jamais sur le libellé qui la précède (« Voyages » /
    ...                « Travels ») ni sur le format du nombre.
    ${total}=    Get Travel Count
    Should Be True    ${total} > 0
    ...    msg=Le compteur d'en-tête ne porte aucune volumétrie
    ${rows}=    Count Displayed Travel Rows
    Should Be True    ${total} >= ${rows}
    ...    msg=Le compteur d'en-tête (${total}) est inférieur au nombre de lignes déjà rendues (${rows})

La recherche libre filtre la liste
    [Documentation]    Scénario 3 du plan. La recherche libre restreint réellement le
    ...                jeu de données : le compteur descend strictement sans tomber à
    ...                zéro, et toutes les lignes rendues portent le terme recherché
    ...                (filtrage effectif, pas un surlignage). Aucun dialogue ni
    ...                message d'erreur ne doit apparaître.
    ${unfiltered}=    Get Travel Count
    Search Travels    ${TRAVEL_SEARCH_TERM}
    ${filtered}=    Get Travel Count
    Should Be True    0 < ${filtered} < ${unfiltered}
    ...    msg=Le compteur filtré (${filtered}) n'est pas strictement compris entre 0 et le total (${unfiltered})
    Displayed Travel Rows Should All Contain    ${TRAVEL_SEARCH_TERM}
    No Travel Dialog Should Be Open

Le retour à l'état non filtré restaure la liste complète
    [Documentation]    Scénario 4 du plan. Le cycle complet non filtré → filtré →
    ...                non filtré est joué dans CE test : la valeur de référence est
    ...                mesurée au début du même run, jamais codée en dur (la
    ...                volumétrie du jeu de démonstration peut évoluer). Le setup
    ...                repart d'un état non filtré connu, quel que soit le test
    ...                précédent.
    [Setup]    Clear Travel Search
    ${reference}=    Get Travel Count
    Search Travels    ${TRAVEL_SEARCH_TERM}
    ${filtered}=    Get Travel Count
    Should Be True    ${filtered} < ${reference}
    ...    msg=La recherche n'a pas réduit la liste (${filtered} vs ${reference})
    Clear Travel Search
    ${restored}=    Get Travel Count
    Should Be Equal As Integers    ${restored}    ${reference}
    ...    msg=Le compteur n'est pas revenu à sa valeur d'avant filtrage (${restored} vs ${reference})
    Travel List Should Be Displayed
    ${rows}=    Count Displayed Travel Rows
    Should Be True    ${rows} > 0
    ...    msg=La liste ne réaffiche aucune ligne après le retour à l'état non filtré
