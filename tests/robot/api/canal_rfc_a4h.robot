*** Settings ***
Documentation       Reconnaissance du canal **RFC / BAPI** : sans écran ET sans HTTP.
...                 Spec: specs/canal-rfc-a4h.md (sha256:e9ef80f24c6a, 2026-08-27)
...                 Générée depuis `specs/canal-rfc-a4h.md` par sap-generator :
...                 relancer le générateur plutôt que de corriger un nom
...                 technique ici.
...
...                 Elle existe parce que le RFC était le seul des quatre canaux
...                 sans suite à lui : il n'était éprouvé que par des keywords
...                 isolés, donc par personne. Ce qu'elle verrouille est une
...                 cartographie, pas une recette métier : à quel système le canal
...                 parle, ce qu'il lit, comment il classe ses refus, et ce qu'il
...                 referme derrière lui.
...
...                 **LECTURE SEULE.** Aucun scénario n'écrit dans le système. La
...                 LUW n'est ouverte que pour prouver qu'on sait la refermer, et
...                 les cinq issues de l'attente d'un job de fond sont éprouvées
...                 sur les jobs d'exploitation que la cible porte DÉJÀ : aucun
...                 job n'est créé, aucun n'est annulé, aucun nom n'est gravé.
...                 Une branche dont la cible n'existe pas sur le système se
...                 SAUTE en le disant, plutôt que de rougir ou de passer.
...
...                 Le canal est **optionnel** : sur un poste sans `pyrfc` (aucune
...                 roue précompilée au-delà de Python 3.12) ou sans runtime natif
...                 NW RFC, la suite se SAUTE au lieu de rougir, y compris dans un
...                 run complet de ``tests/robot/``. Le tag ``rfc`` permet en plus
...                 de l'inclure ou de l'exclure explicitement.
...
...                 Prérequis : un interpréteur 3.10 à 3.12 portant
...                 ``pyrfc==3.3.1``, un runtime NW RFC (souvent déjà déposé par le
...                 composant « SAP NWRFC x64 Shared » de SAP GUI for Windows
...                 8.00 : ``packaging/install-rfc.ps1 -CheckOnly`` le dit), et le
...                 système applicatif joignable.
...
...                 Exemple :
...                 | robot --pythonpath src --include rfc
...                 | ...   -v "RFC_PASSWORD: Secret:***"
...                 | ...   --outputdir results/rfc tests/robot/api/canal_rfc_a4h.robot

Resource            ../../../resources/rfc_keywords.resource
Resource            ../../../resources/api_keywords.resource

Suite Setup         Run Keywords    Skip Unless Rfc Channel Is Available
...                     AND    Open Rfc Channel
Suite Teardown      Run Keywords    Close Rfc Channel    AND    Close Api Channel

Test Tags           rfc


*** Variables ***
# Cible : le système applicatif joint par RFC. Aucun mot de passe ici
# (convention 11) : -v "RFC_PASSWORD: Secret:<motdepasse>".
${RFC_ASHOST}                   localhost
${RFC_SYSNR}                    00
${RFC_CLIENT}                   001
${RFC_USER}                     DEVELOPER
${RFC_PASSWORD}                 ${EMPTY}    # OBLIGATOIRE : -v "RFC_PASSWORD: Secret:<motdepasse>"
${RFC_LANG}                     EN
${EXPECTED_SYSTEM_ID}           A4H

# Le même système, vu par son canal OData : c'est le croisement du scénario 4.
${A4H_API_URL}                  http://localhost:50000

# Données métier du modèle de démonstration (jamais de volumétrie gravée : les
# scénarios asserttent des relations, pas des chiffres relevés un jour donné).
${AIRLINE}                      LH
${FLIGHT_CONNECTION}            0400
${CONNECTION_LIMIT}             3

# Aucun nom de job n'est gravé ici : les cibles des cinq branches de l'attente
# sont DÉCOUVERTES sur le système (le journal est lu, les statuts classés, un
# job qui porte le cas voulu est choisi). Les jobs d'exploitation d'une image
# n'existent pas sur une autre.
#
# Le plafond de lecture volontairement bas du premier test : celui par lequel
# une première exploration s'est trompée, rejoué ici pour montrer qu'il ne
# rend PAS la même image du journal.
${TRUNCATED_JOB_LOG}            200

# Codes techniques attendus des refus (convention 3 : c'est ce qui se compare,
# jamais le texte du serveur, qui est localisé ou verbeux).
${CODE_TABLE_ABSENTE}           TABLE_NOT_AVAILABLE
${CODE_TABLE_SANS_DONNEES}      TABLE_WITHOUT_DATA
${CODE_MODULE_ABSENT}           FU_NOT_FOUND
${CODE_PARAMETRE_INVALIDE}      RFC_INVALID_PARAMETER
${CODE_OUVERTURE_REFUSEE}       RFC_LOGON_FAILURE
${CODE_COMMUNICATION}           RFC_COMMUNICATION_FAILURE


*** Test Cases ***
Le Canal S Ouvre Et Prouve A Quel Systeme Il Parle
    [Documentation]    Un canal ouvert ne dit pas encore vers QUOI. Deux sources
    ...    d'identité indépendantes sont lues, puis confrontées : les attributs
    ...    de la connexion et la fiche que le système publie sur lui-même. Sans
    ...    ce scénario, toute la campagne peut être verte contre le mauvais
    ...    système, ce que ce dépôt a déjà vécu côté web avec un nom d'hôte
    ...    partagé entre deux conteneurs.
    ${identite}=    Read System Identity
    Should Be Equal    ${identite}[sysId]    ${EXPECTED_SYSTEM_ID}
    ...    msg=Le canal parle à ${identite}[sysId], pas à ${EXPECTED_SYSTEM_ID}.
    Should Be Equal    ${identite}[client]    ${RFC_CLIENT}
    ...    msg=Mandant servi différent du mandant demandé : la population lue ne serait pas celle attendue.
    Should Be Equal    ${identite}[user]    ${RFC_USER}
    ${systeme}=    Read System Information
    Should Be Equal    ${systeme}[RFCSYSID]    ${identite}[sysId]
    ...    msg=Les deux sources d'identité ne s'accordent pas sur le système.
    Should Be Equal    ${systeme}[RFCSAPRL]    ${identite}[partnerRel]
    Should Be Equal    ${systeme}[RFCKERNRL]    ${identite}[kernelRel]
    Should Not Be Empty    ${systeme}[RFCHOST]
    Should Not Be Empty    ${systeme}[RFCDBSYS]

Les Sondes De Vie Repondent
    [Documentation]    Les trois sondes livrées partout, du plus élémentaire au
    ...    plus typé. La réponse du ping est un dictionnaire VIDE : seule
    ...    l'absence d'exception fait foi, asserter un contenu ici serait
    ...    asserter du vide.
    Rfc Channel Should Answer Ping
    ${echo}=    Echo Through Rfc Channel    sonde-sapfx
    Should Be Equal    ${echo}[ECHOTEXT]    sonde-sapfx
    ...    msg=L'écho ne rend pas le texte envoyé : l'aller-retour applicatif est rompu.
    Should Contain    ${echo}[RESPTEXT]    ${EXPECTED_SYSTEM_ID}
    ...    msg=Le serveur qui répond ne s'annonce pas comme ${EXPECTED_SYSTEM_ID}.
    ${structure}=    Exchange Structure Through Rfc Channel    sonde-structure
    Should Contain    ${structure}[ECHOSTRUCT][RFCDATA1]    sonde-structure
    ...    msg=La structure n'est pas revenue telle qu'envoyée.
    Should Not Be Empty    ${structure}[RFCTABLE]
    ...    msg=La table de retour est vide : le typage table du canal n'est pas éprouvé.

La Lecture Generique De Table Est Bornee Et Filtree
    [Documentation]    Le coeur du canal en lecture. Aucune volumétrie n'est
    ...    gravée : ce sont des RELATIONS qui sont assertées (le mandant courant
    ...    figure dans l'annuaire, le filtre isole une seule compagnie, le
    ...    plafond est respecté), pour que la suite reste vraie sur un autre
    ...    système du même modèle.
    ${mandants}=    Read Client Directory
    ${codes}=    Get Values From Dicts    ${mandants}    MANDT
    Should Contain    ${codes}    ${RFC_CLIENT}
    ...    msg=Le mandant de connexion ne figure pas dans l'annuaire des mandants.
    ${total}=    Count Airlines
    Should Be True    ${total} > 0    msg=Aucune compagnie : jeu de données de démonstration absent ?
    ${une}=    Read Airlines    airline=${AIRLINE}
    Length Should Be    ${une}    1    msg=Le filtre sur le code compagnie n'isole pas une ligne unique.
    Should Be Equal    ${une}[0][CARRID]    ${AIRLINE}
    Should Not Be Empty    ${une}[0][CURRCODE]
    ${liaisons}=    Read Flight Connections    ${AIRLINE}    limit=${CONNECTION_LIMIT}
    Length Should Be    ${liaisons}    ${CONNECTION_LIMIT}
    ...    msg=Le plafond de lignes demandé n'est pas respecté par la lecture.
    Should Not Be Empty    ${liaisons}[0][CITYFROM]
    ${aucune}=    Read Airlines    airline=${MISSING_AIRLINE}
    Should Be Empty    ${aucune}
    ...    msg=Un filtre sans correspondance doit rendre une liste vide, jamais une erreur.
    ${classe}=    Read Dictionary Class Of Airlines
    Should Be Equal    ${classe}    TRANSP
    ...    msg=La table lue n'est pas une table transparente : la lecture porterait sur autre chose.

Le Meme Fait Par Deux Canaux Rend Un Seul Verdict
    [Documentation]    Le croisement qui donne son prix à la campagne : le même
    ...    fait métier compté par RFC et par OData, deux protocoles
    ...    indépendants, une seule réalité. Les deux canaux visent le MÊME
    ...    mandant : les faire diverger comparerait deux populations et
    ...    fabriquerait un écart qui n'existe pas.
    ...
    ...    Le premier appel OData d'un service jamais sollicité sur un système
    ...    froid peut être lent : ce n'est pas une panne de réseau, d'où le
    ...    préflight patient avant le comptage.
    Open Api Channel    base_url=${A4H_API_URL}    user=${RFC_USER}
    ...    password=${RFC_PASSWORD}    client=${RFC_CLIENT}    alias=odata
    Wait Until Api Channel Is Available    alias=odata    timeout=60s
    ${mandant_api}=    Api Channel Client    alias=odata
    Should Be Equal    ${mandant_api}    ${RFC_CLIENT}
    ...    msg=Les deux canaux ne visent pas le même mandant : la comparaison serait truquée.
    ${par_rfc}=    Count Products
    ${par_odata}=    Count Business Entities    ${EPM_PRODUCTS}    alias=odata
    Should Be True    ${par_rfc} > 0    msg=Aucun produit côté RFC : rien à croiser.
    Should Be Equal As Integers    ${par_rfc}    ${par_odata}
    ...    msg=Les deux canaux ne comptent pas la même population : ${par_rfc} par RFC contre ${par_odata} par OData.

Les Refus Se Classent Par Code Jamais Par Texte
    [Documentation]    Quatre refus provoqués sur la connexion ouverte, chacun
    ...    jugé sur son CODE technique : le texte du serveur est localisé ou
    ...    verbeux, le code ne l'est pas (convention 3).
    ...
    ...    Le cas du champ inexistant est asserté avec sa bizarrerie ASSUMÉE :
    ...    le code rendu accuse la table d'être sans données alors qu'elle est
    ...    pleine et que la faute est dans le nom du champ. La contre-épreuve le
    ...    prouve dans le même test : relus avec leurs vrais noms, tous les
    ...    champs de la même table passent.
    Reading A Missing Table Should Be Refused With Code    ${CODE_TABLE_ABSENTE}
    Reading A Missing Field Should Be Refused With Code    ${CODE_TABLE_SANS_DONNEES}
    Calling A Missing Function Module Should Be Refused With Code    ${CODE_MODULE_ABSENT}
    Calling With An Unknown Parameter Should Be Refused With Code    ${CODE_PARAMETRE_INVALIDE}
    ${champs}=    Read Field Names Of The Field Catalog
    Should Not Be Empty    ${champs}    msg=Le catalogue de champs ne se décrit pas lui-même.
    ${relu}=    Read The Field Catalog With Every Real Field    ${champs}
    Should Not Be Empty    ${relu}
    ...    msg=Contre-épreuve en échec : la table refuse aussi ses PROPRES champs, le code accuserait alors autre chose.

La Garde De Clause Protege Avant Le Reseau
    [Documentation]    Une clause de sélection au-delà de la limite du module est
    ...    refusée par la bibliothèque elle-même, avant tout appel. Sans cette
    ...    garde, le dépassement produirait une sélection silencieusement
    ...    tronquée : un résultat faux et vert, la pire des sorties.
    ${erreur}=    Reading With An Oversized Selection Clause Should Be Refused
    Should Contain    ${erreur}    72
    ...    msg=Le refus ne nomme pas la limite du module.
    Should Contain    ${erreur}    AND
    ...    msg=Le refus ne nomme pas le remède (découper en clauses AND).

Une Bapi Est Jugee Sur Le Type De Ses Messages
    [Documentation]    Une BAPI peut réussir techniquement et porter un message
    ...    d'erreur métier : la décision se prend donc sur le TYPE des messages
    ...    `BAPIRET2` (`E`/`A`/`X`), jamais sur leur libellé. Le message d'échec
    ...    est confronté aux messages BRUTS du même appel, pour qu'aucune des
    ...    deux sources ne soit crue sur parole.
    ...
    ...    Le prix d'un vol sert de leçon de typage : le même montant revient en
    ...    TEXTE par la lecture de table et en décimal ABAP par la BAPI. Une
    ...    assertion numérique convertit, elle ne compare jamais les deux
    ...    représentations.
    ${detail}=    Read User Details    ${RFC_USER}
    Should Not Be Empty    ${detail}[LOGONDATA]    msg=La fiche utilisateur revient sans données de connexion.
    ${erreur}=    Reading Details Of An Unknown User Should Be Refused
    ${messages}=    Read Messages Of An Unknown User Lookup
    Should Be Equal    ${messages}[0][TYPE]    E
    ...    msg=Le refus métier n'est pas de type E : la BAPI ne serait pas jugée sur le bon critère.
    Should Contain    ${erreur}    ${messages}[0][ID]
    ...    msg=Le message d'échec n'identifie pas le message bloquant (type et identifiant).
    ${vols}=    Read Flights Of Airline By Bapi    ${AIRLINE}
    Should Be Equal    ${vols}[RETURN][0][TYPE]    S
    Should Not Be Empty    ${vols}[FLIGHT_LIST]
    ${par_table}=    Read Flight Price    ${AIRLINE}    ${FLIGHT_CONNECTION}
    ${par_bapi}=    Set Variable    ${vols}[FLIGHT_LIST][0][PRICE]
    Should Be Equal As Numbers    ${par_table}[PRICE]    ${par_bapi}
    ...    msg=Le même prix diffère selon la représentation : la conversion numérique est le seul rapprochement valide.
    ${rollback}=    Close The Open Luw
    Should Be Empty    ${rollback}[RETURN][TYPE]
    ...    msg=La fermeture de la LUW rapporte un message : le rollback n'est pas propre.

L Inventaire Des Bapis Est La Perception Du Canal
    [Documentation]    Ce que le système publie de lui-même, côté RFC :
    ...    l'équivalent du catalogue Gateway pour le canal OData. Le scénario
    ...    constate la FORME et le volume, il ne fige aucun catalogue, qui varie
    ...    d'un système à l'autre.
    ${bapis}=    List System Bapis
    Should Not Be Empty    ${bapis}    msg=Le système ne publie aucune BAPI : inventaire vide, perception nulle.
    Dictionary Should Contain Key    ${bapis}[0]    OBJECTTYPE
    Dictionary Should Contain Key    ${bapis}[0]    OBJECTNAME
    Dictionary Should Contain Key    ${bapis}[0]    ABAPNAME
    Should Not Be Empty    ${bapis}[0][ABAPNAME]
    ...    msg=Une entrée d'inventaire sans nom de module ABAP n'est pas exploitable.

Le Journal Des Jobs Est Lu Sans Plafond Et Classe Par Cas
    [Documentation]    Les cinq branches qui suivent choisissent leur cible SUR
    ...    le système : les jobs d'exploitation d'une image ne sont pas ceux
    ...    d'une autre, et un nom gravé rendrait la campagne intransportable.
    ...    Ce test est la fondation de ce choix, et il verrouille d'abord ce qui
    ...    a réellement trompé une première exploration : un PLAFOND de lecture.
    ...
    ...    Une lecture plafonnée ne tronque pas seulement le résultat, elle
    ...    fausse la classification, et sans bruit : les premières lignes d'un
    ...    journal peuvent être toutes terminées et faire conclure que le
    ...    système ne porte que des jobs terminés. C'est une mesure fausse et
    ...    verte, exactement ce que ce dépôt traque.
    ${complet}=    Job Log Catalogue
    Should Be True    ${complet}[rows] > 0
    ...    msg=Journal des jobs vide : aucune branche de l'attente n'est éprouvable ici.
    ${comptes}=    Get Dictionary Values    ${complet}[statuses]
    ${total}=    Evaluate    sum($comptes)
    Should Be Equal As Integers    ${total}    ${complet}[rows]
    ...    msg=Des runs lus ne sont pas classés : le décompte par statut perd des lignes.
    ${cas}=    Set Variable    ${complet}[cases]
    Dictionary Should Contain Key    ${cas}    done
    Dictionary Should Contain Key    ${cas}    aborted_with_finished
    Dictionary Should Contain Key    ${cas}    pipeline
    Dictionary Should Contain Key    ${cas}    unmapped
    ${tronque}=    Read Job Log Catalogue    limit=${TRUNCATED_JOB_LOG}
    Should Be True    ${tronque}[rows] <= ${TRUNCATED_JOB_LOG}
    ...    msg=Le plafond de lecture n'est pas respecté par le journal.
    IF    ${complet}[rows] > ${TRUNCATED_JOB_LOG}
        Should Be True    ${tronque}[rows] < ${complet}[rows]
        ...    msg=La lecture plafonnée voit autant de runs que la complète : la démonstration ne porte pas.
        Log    Journal plafonné : ${tronque}[statuses] contre ${complet}[statuses] en entier.
        ...    level=WARN
    END

L Attente D Un Job De Fond Conclut Sur Un Job Termine
    [Documentation]    Première des cinq issues : tous les runs sont terminés,
    ...    l'attente conclut, et elle le prouve par son décompte de statuts. Une
    ...    attente qui conclurait sans compter conclurait sur rien.
    ${job}=    Job Carrying Case Or Skip    done
    ...    aucun job dont les runs sont tous terminés
    ${etat}=    Wait For Business Job    ${job}    timeout=${JOB_WAIT_BUDGET}
    Should Be Equal    ${etat}[state]    done
    ...    msg=L'attente ne conclut pas sur un job dont tous les runs sont terminés.
    Dictionary Should Contain Key    ${etat}[statuses]    F
    ...    msg=Aucun run terminé compté : l'attente conclut sans preuve.
    ${attente}=    Pending Statuses Of Job    ${job}
    Should Be Empty    ${attente}
    ...    msg=Le job choisi a un run dans le pipeline : ce n'est pas le cas « terminé ».

L Attente D Un Job De Fond Echoue Sur Un Run Annule Malgre Des Runs Termines
    [Documentation]    Deuxième issue, et le point de jugement de tout le
    ...    scénario : un run annulé PRIME sur des dizaines de runs terminés. Le
    ...    job choisi porte volontairement les deux, sinon la priorité ne serait
    ...    pas prouvée mais seulement supposée.
    ...
    ...    Un run annulé est un fait à remonter, jamais une statistique à
    ...    moyenner : une attente qui rendrait « terminé » parce que les `F`
    ...    sont majoritaires cacherait la seule chose qui mérite un regard.
    ${job}=    Job Carrying Case Or Skip    aborted_with_finished
    ...    aucun job portant à la fois un run annulé et des runs terminés
    ${statuts}=    Statuses Of Job    ${job}
    Should Be True    ${statuts}[A] > 0    msg=Le job choisi ne porte aucun run annulé.
    Should Be True    ${statuts}[F] > 0
    ...    msg=Le job choisi ne porte aucun run terminé : la priorité de l'annulation ne serait pas éprouvée.
    ${erreur}=    Waiting For Job Should Fail    ${job}
    Should Contain    ${erreur}    (statut A)
    ...    msg=L'échec ne se prononce pas sur le statut d'annulation : il serait jugé sur autre chose que le statut.
    Should Contain    ${erreur}    SM37
    ...    msg=L'échec ne nomme pas le journal où regarder.
    Failure Should Report Every Counted Status    ${erreur}    ${job}

L Attente D Un Job De Fond Signale Un Run Encore Dans Le Pipeline
    [Documentation]    Troisième issue : un run n'est ni terminé ni annulé, il
    ...    attend son tour. L'attente ne peut donc pas aboutir, et le budget est
    ...    court à dessein : il borne un échec attendu, il ne fait patienter
    ...    personne.
    ${job}=    Job Carrying Case Or Skip    pipeline
    ...    aucun job dont un run est encore dans le pipeline
    ${attente}=    Pending Statuses Of Job    ${job}
    Should Not Be Empty    ${attente}
    ...    msg=Le job choisi n'a aucun statut de pipeline : ce n'est pas le cas visé.
    ${erreur}=    Waiting For Job Should Fail    ${job}
    Should Contain    ${erreur}    ${SHORT_JOB_WAIT}
    ...    msg=L'échec ne dit pas quel budget d'attente a été dépassé.
    Failure Should Report Every Counted Status    ${erreur}    ${job}

L Attente D Un Job De Fond Continue Devant Un Statut Non Cartographie
    [Documentation]    Quatrième issue, et le point de QUALITÉ du scénario :
    ...    devant un statut que la bibliothèque ne cartographie pas, l'attente
    ...    continue au lieu de conclure au succès. Un statut inconnu pris pour
    ...    un « terminé » serait le vert le plus dangereux du canal.
    ...
    ...    Ce que ce test n'asserte PAS, et ne le fera pas : la signification du
    ...    statut rencontré. Son élément de données porte un domaine `CHAR1`
    ...    sans liste de valeurs, donc le dictionnaire n'en dit rien, et la
    ...    bibliothèque l'affiche « (?) » plutôt que de l'inventer. Seul le
    ...    comportement de repli est éprouvé ici.
    ${job}=    Job Carrying Case Or Skip    unmapped
    ...    aucun job dont les statuts sont tous hors de la carte
    ${inconnus}=    Uncharted Statuses Of Job    ${job}
    Should Not Be Empty    ${inconnus}
    ...    msg=Le job choisi ne porte que des statuts cartographiés : le repli ne serait pas éprouvé.
    ${attente}=    Pending Statuses Of Job    ${job}
    Should Be Empty    ${attente}
    ...    msg=Le job choisi a un run dans le pipeline : l'attente continuerait pour une raison connue.
    ${erreur}=    Waiting For Job Should Fail    ${job}
    Should Contain    ${erreur}    (?)
    ...    msg=L'échec ne signale pas qu'un statut lui est inconnu : il aurait donc prêté un sens à ce statut.
    Failure Should Report Every Counted Status    ${erreur}    ${job}

L Attente D Un Job De Fond Nomme L Absence D Un Job Inconnu
    [Documentation]    Cinquième issue : aucun run ne porte ce nom. Un job absent
    ...    qui rendrait « terminé » serait un vert construit sur du vide, d'où
    ...    l'assertion de ce cas comme un échec ATTENDU, jamais contourné.
    ${erreur}=    Waiting For An Unknown Job Should Fail
    # Le « = » est échappé : sans cela, il se lirait comme le début d'un
    # argument nommé au lieu du texte à chercher.
    Should Contain    ${erreur}    jobcount\=
    ...    msg=L'échec ne nomme pas la piste (préciser le run par son numéro).
    Should Contain    ${erreur}    SM37
    ...    msg=L'échec ne nomme pas le journal où regarder.
    Should Contain    ${erreur}    Aucun job
    ...    msg=L'échec ne nomme pas l'absence : la cause resterait à deviner.

Les Refus D Ouverture Se Distinguent Des Refus Applicatifs
    [Documentation]    Trois ouvertures qui DOIVENT échouer, donc rien à fermer,
    ...    mais le teardown reste posé. Le point de vigilance du plan est tenu
    ...    tel quel : mot de passe faux et mandant inexistant rendent le MÊME
    ...    code, seul le texte les sépare. Ce test ne prétend donc pas les
    ...    distinguer, il constate un refus d'ouverture de session, et c'est tout
    ...    ce qu'il peut affirmer honnêtement.
    ...
    ...    Le troisième cas, lui, est d'une autre classe : le système ne répond
    ...    pas du tout, donc la question de l'identité ne se pose même pas.
    ...    C'est ce qui sépare un problème de réseau d'un problème de compte.
    Opening With A Wrong Password Should Be Refused With Code    ${CODE_OUVERTURE_REFUSEE}
    Opening On An Unknown Client Should Be Refused With Code    ${CODE_OUVERTURE_REFUSEE}
    Opening On An Unreachable System Should Be Refused With Code    ${CODE_COMMUNICATION}
    ${ouverts}=    List Open Rfc Channels
    Length Should Be    ${ouverts}    1
    ...    msg=Un refus d'ouverture a laissé une connexion derrière lui.

Plusieurs Connexions Coexistent Et La Fermeture Les Emporte Toutes
    [Documentation]    Le canal multiplexe plusieurs connexions par alias, et le
    ...    teardown doit toutes les emporter : une connexion RFC orpheline est
    ...    une session utilisateur restée ouverte côté serveur. Le teardown de ce
    ...    test rouvre le canal principal, pour que l'ordre des tests ne soit pas
    ...    un prérequis caché.
    [Teardown]    Open Rfc Channel
    Open Rfc Channel    alias=secondaire
    ${principal}=    Echo Through Rfc Channel    canal-principal
    ${second}=    Echo Through Rfc Channel    canal-secondaire    alias=secondaire
    Should Be Equal    ${principal}[ECHOTEXT]    canal-principal
    Should Be Equal    ${second}[ECHOTEXT]    canal-secondaire
    ...    msg=Les deux alias ne répondent pas indépendamment.
    ${ouverts}=    List Open Rfc Channels
    Should Contain    ${ouverts}    secondaire
    Length Should Be    ${ouverts}    2
    Close Rfc Channel
    ${restants}=    List Open Rfc Channels
    Should Be Empty    ${restants}
    ...    msg=La fermeture globale a laissé une connexion ouverte côté serveur.
    Calling A Closed Rfc Channel Should Name The Opening Keyword    secondaire
