*** Settings ***
Documentation       **EXEMPLE À PERSONNALISER** : ce fichier porte le vocabulaire
...                 de VERDICT des campagnes de reconnaissance de ce dépôt. Il ne
...                 nomme aucun écran, donc il se réutilise tel quel, mais son
...                 vocabulaire (`gap` / `covered` / `poste` / `hors_api`) et la
...                 forme de son registre sont un choix de ce laboratoire, à
...                 adapter à votre propre façon de consigner ce qu'une bibliothèque
...                 sait faire. Ce qui fait foi partout, c'est `src/` : voir
...                 `resources/README.md`.
...
...                 Le **registre de capacités**, transverse aux campagnes de
...                 reconnaissance : le vocabulaire de verdict, l'artefact
...                 déterministe et les assertions de forme partagées.
...
...                 Il vit à part parce qu'il ne parle d'AUCUN écran : une campagne
...                 de reconnaissance mesure ce que la bibliothèque sait faire sur
...                 UNE cible (une release, un poste), et le contrat de verdict, lui,
...                 doit être le même partout, sans quoi deux campagnes deviennent
...                 incomparables. Les page objects qui l'importent apportent les
...                 écrans ; celui-ci apporte la règle.
...
...                 Contrat : un verdict est DÉRIVÉ d'une observation
...                 (`Verdict De Capacite` / `Verdict De Manque`), jamais posé ; il
...                 est confronté à celui du plan (`Le Verdict Devrait Etre`), qui
...                 échoue dans les DEUX sens (manque comblé ou capacité perdue) ;
...                 et l'absence d'une capacité se prouve par `Keyword Should Exist`
...                 inversé (`Un Keyword Devrait Etre Absent`), jamais par un
...                 contournement. Le registre est écrit et relu par
...                 `sapfx_common.artifacts` : périmètre d'empreinte DÉCLARÉ, et
...                 empreinte RECALCULÉE à la relecture, donc un registre édité
...                 après coup est refusé au lieu d'être comparé.

Library             Collections
Library             OperatingSystem
Library             String
Library             sapfx_common.artifacts


*** Variables ***
${REGISTER_PATH}                ${OUTPUT DIR}/ecc_capability_register.json
@{CAPABILITY_VERDICTS}          gap    covered    poste    hors_api
# Le registre de suite (capacité -> {verdict, preuve}), vidé par le Suite Setup
# de la campagne et rempli par `Consigner Le Verdict`.
&{CAPABILITY_REGISTER}
# L'identité de la CIBLE mesurée, posée par le Suite Setup de la campagne : elle
# dit QUELLE cible le registre décrit. Le SID seul ne suffit pas : deux
# conteneurs du laboratoire annoncent le même, seules release et kernel les
# séparent.
&{CAPABILITY_TARGET}


*** Keywords ***
Consigner Le Verdict
    [Documentation]    Ajoute (ou remplace) l'entrée ``${capacite}`` du registre de
    ...                suite avec son ``${verdict}`` (`gap` | `covered` | `poste` |
    ...                `hors_api`) et sa ``${preuve}`` (texte court : ce qui a été
    ...                observé). Un verdict hors vocabulaire est refusé.
    [Arguments]    ${capacite}    ${verdict}    ${preuve}
    List Should Contain Value    ${CAPABILITY_VERDICTS}    ${verdict}
    ...    msg=Verdict '${verdict}' hors vocabulaire pour '${capacite}' (attendu : ${CAPABILITY_VERDICTS}).
    ${entree}=    Create Dictionary    verdict=${verdict}    preuve=${preuve}
    Set To Dictionary    ${CAPABILITY_REGISTER}    ${capacite}    ${entree}
    RETURN    ${entree}

Le Verdict Devrait Etre
    [Documentation]    Échoue si le verdict consigné pour ``${capacite}`` diverge de
    ...                ``${attendu}`` (le verdict du plan), dans les deux sens, en
    ...                nommant la mise à jour du plan et du registre.
    [Arguments]    ${capacite}    ${attendu}
    Dictionary Should Contain Key    ${CAPABILITY_REGISTER}    ${capacite}
    ...    msg=Aucun verdict consigné pour '${capacite}' : appeler Consigner Le Verdict d'abord.
    ${observe}=    Set Variable    ${CAPABILITY_REGISTER}[${capacite}][verdict]
    IF    '${observe}' != '${attendu}'
        Fail    Capacité '${capacite}' : verdict observé '${observe}', attendu par le plan '${attendu}' : capacité désormais couverte (ou perdue) : mettre à jour le plan et le registre.
    END

Verdict De Manque
    [Documentation]    ``gap`` quand le manque est OBSERVÉ (booléen vrai), ``covered``
    ...                sinon : le verdict est dérivé de l'observation, jamais posé.
    [Arguments]    ${manque_observe}
    IF    ${manque_observe}
        RETURN    gap
    END
    RETURN    covered

Verdict De Capacite
    [Documentation]    Le miroir de `Verdict De Manque` : ``covered`` quand la
    ...                capacité est OBSERVÉE (booléen vrai), ``gap`` sinon. C'est
    ...                la forme des scénarios depuis le lot de correction : un
    ...                keyword livré qui cesserait de tenir rend ``gap`` et le
    ...                scénario rougit en nommant le registre.
    [Arguments]    ${capacite_observee}
    IF    ${capacite_observee}
        RETURN    covered
    END
    RETURN    gap

L Echec Devrait Etre Reproduit
    [Documentation]    Vérifie qu'une tentative (``${status}``/``${message}`` de
    ...                `Run Keyword And Ignore Error`) a bien ÉCHOUÉ avec un message
    ...                correspondant au motif glob ``${motif}``. Un PASS, ou un autre
    ...                message, signifie que la bibliothèque a changé : l'échec nomme
    ...                la mise à jour du plan et du registre. Retourne vrai.
    [Arguments]    ${capacite}    ${status}    ${message}    ${motif}
    IF    '${status}' != 'FAIL'
        Fail    Capacité '${capacite}' : le keyword a PASSÉ (retour : ${message}) là où le plan attend l'échec '${motif}' : capacité modifiée (couverte ou perdue) : mettre à jour le plan et le registre.
    END
    ${reproduit}=    Run Keyword And Return Status    Should Match    ${message}    ${motif}
    IF    not ${reproduit}
        Fail    Capacité '${capacite}' : échec observé '${message}' au lieu du motif '${motif}' : capacité modifiée (couverte ou perdue) : mettre à jour le plan et le registre.
    END
    RETURN    ${True}

Un Keyword Devrait Etre Absent
    [Documentation]    La preuve d'absence d'une capacité : `Keyword Should Exist`
    ...                inversé. Échoue si ``${nom}`` existe dans l'espace de noms de
    ...                la suite (bibliothèques ET resources importées). Retourne le
    ...                message d'absence.
    [Arguments]    ${nom}
    ${message}=    Run Keyword And Expect Error    *    Keyword Should Exist    ${nom}
    RETURN    ${message}

Une Fenetre Modale Devrait Etre Ouverte
    [Documentation]    Échoue si la pile de fenêtres (`Get Open Windows`) ne porte
    ...                aucune fenêtre ``modal``. Retourne les ids des modales.
    [Arguments]    ${fenetres}
    ${modales}=    Evaluate    [w['id'] for w in $fenetres if w.get('modal')]
    Should Not Be Empty    ${modales}
    ...    msg=Aucune fenêtre modale ouverte (pile : ${fenetres}).
    RETURN    ${modales}

Aucune Fenetre Modale Ne Devrait Etre Ouverte
    [Documentation]    Échoue si la pile de fenêtres porte une fenêtre ``modal``.
    [Arguments]    ${fenetres}
    ${modales}=    Evaluate    [w['id'] for w in $fenetres if w.get('modal')]
    Should Be Empty    ${modales}
    ...    msg=Une fenêtre modale est ouverte : ${modales}.

Les Keywords Devraient Etre Absents
    [Documentation]    Vrai si TOUS les keywords nommés sont absents, faux dès que
    ...                l'un existe (le nom du présent est journalisé).
    [Arguments]    @{noms}
    ${tous_absents}=    Set Variable    ${True}
    FOR    ${nom}    IN    @{noms}
        ${absent}=    Run Keyword And Return Status    Un Keyword Devrait Etre Absent    ${nom}
        IF    not ${absent}
            Log    Le keyword '${nom}' EXISTE désormais.    WARN
            ${tous_absents}=    Set Variable    ${False}
        END
    END
    RETURN    ${tous_absents}

Ecrire Le Registre Des Capacites
    [Documentation]    Écrit le registre par `Write Deterministic Artifact`
    ...                (``sapfx_common.artifacts`` : JSON trié, LF, UTF-8) dans
    ...                ``${chemin}`` : ``capabilities``, ``target`` (l'identité
    ...                de la cible relevée en Suite Setup), ``hash_scope``,
    ...                ``sha256`` et ``generated_at``. L'empreinte porte sur la
    ...                seule partie ``capabilities`` (deux runs aux mêmes
    ...                verdicts donnent la même empreinte, et ``target`` dit sur
    ...                QUELLE cible chacun a été mesuré ; l'artefact DIT ce que
    ...                son empreinte couvre). Journalise le tableau Markdown du
    ...                registre. Retourne le chemin absolu.
    [Arguments]    ${chemin}=${REGISTER_PATH}
    ${artefact}=    Create Dictionary    capabilities=${CAPABILITY_REGISTER}    target=${CAPABILITY_TARGET}
    ${ecrit}=    Write Deterministic Artifact    ${chemin}    ${artefact}    hashed_keys=capabilities
    ${empreinte}=    Artifact Hash    ${artefact}    hashed_keys=capabilities
    ${tableau}=    Tableau Markdown Du Registre
    Log    Registre des capacités (${empreinte}) :\n${tableau}
    RETURN    ${ecrit}

Relire Le Registre Des Capacites
    [Documentation]    Relit le registre par `Read Deterministic Artifact`, qui
    ...                RECALCULE l'empreinte sur le périmètre déclaré : un
    ...                registre édité après coup est refusé, jamais comparé.
    ...                Retourne le dict (``capabilities``, ``target``,
    ...                ``hash_scope``, ``sha256``, ``generated_at``).
    [Arguments]    ${chemin}=${REGISTER_PATH}
    ${registre}=    Read Deterministic Artifact    ${chemin}
    RETURN    ${registre}

Tableau Markdown Du Registre
    [Documentation]    Le registre de suite en tableau Markdown (capacité, verdict,
    ...                preuve), lignes triées par capacité.
    ${cles}=    Get Dictionary Keys    ${CAPABILITY_REGISTER}
    @{lignes}=    Create List    | Capacité | Verdict | Preuve |    | --- | --- | --- |
    FOR    ${cle}    IN    @{cles}
        ${entree}=    Get From Dictionary    ${CAPABILITY_REGISTER}    ${cle}
        Append To List    ${lignes}    | ${cle} | ${entree}[verdict] | ${entree}[preuve] |
    END
    ${tableau}=    Catenate    SEPARATOR=\n    @{lignes}
    RETURN    ${tableau}

Le Registre Devrait Etre Conforme Au Plan
    [Documentation]    Vérifie qu'un registre relu porte EXACTEMENT les capacités de
    ...                ``${attendus}`` (dict capacité -> verdict attendu ; plusieurs
    ...                verdicts admis séparés par ``|``, cas d'une limite de poste),
    ...                chacune avec un verdict admis, et aucune capacité en plus.
    [Arguments]    ${registre}    ${attendus}
    ${capacites}=    Get From Dictionary    ${registre}    capabilities
    ${nb_attendus}=    Get Length    ${attendus}
    Length Should Be    ${capacites}    ${nb_attendus}
    ...    msg=Le registre porte ${nb_attendus} capacités attendues, mais un autre nombre d'entrées : mettre à jour le plan et le registre.
    FOR    ${capacite}    ${admis}    IN    &{attendus}
        Dictionary Should Contain Key    ${capacites}    ${capacite}
        ...    msg=Capacité '${capacite}' absente du registre : mettre à jour le plan et le registre.
        ${observe}=    Set Variable    ${capacites}[${capacite}][verdict]
        @{verdicts_admis}=    Split String    ${admis}    |
        List Should Contain Value    ${verdicts_admis}    ${observe}
        ...    msg=Capacité '${capacite}' : verdict '${observe}' hors des verdicts du plan (${admis}) : capacité désormais couverte (ou perdue) : mettre à jour le plan et le registre.
    END

L Identite De La Cible Devrait Etre Renseignee
    [Documentation]    Échoue si le registre relu ne nomme pas sa cible : la
    ...                section ``target`` doit porter un SID, un mandant, un
    ...                utilisateur, une release SAP_BASIS et une release de
    ...                kernel NON vides (le SID seul ne distingue pas deux
    ...                systèmes du laboratoire). Retourne la section.
    [Arguments]    ${registre}
    ${cible}=    Get From Dictionary    ${registre}    target
    FOR    ${champ}    IN    system_id    client    user    basis_release    kernel_release
        Dictionary Should Contain Key    ${cible}    ${champ}
        ...    msg=Le registre ne nomme pas le champ '${champ}' de sa cible (target : ${cible}).
        Should Not Be Empty    ${cible}[${champ}]
        ...    msg=Le champ '${champ}' de la cible est vide (target : ${cible}).
    END
    RETURN    ${cible}

# ---------------------------------------------------------------------------
# SESSION_MANAGER : perception, arbre du menu, menu System
# ---------------------------------------------------------------------------
