*** Settings ***
Documentation       Le canal **RFC / BAPI** regardé sur DEUX releases ABAP.
...                 Spec: specs/canal-rfc-abap2023.md (sha256:bb8d9ea4a85e, 2026-08-28)
...                 Generated from specs/canal-rfc-abap2023.md by sap-generator:
...                 re-run the generator rather than hand-editing locators here.
...
...                 Elle ne remplace pas `canal_rfc_a4h.robot` et ne la répète
...                 pas : cette suite-là passe déjà sur cette cible par simple
...                 surcharge de variables, donc la **portabilité est acquise et
...                 n'est pas le sujet**. Ce qui est éprouvé ici est ce qu'une
...                 campagne mono-release ne peut pas voir : ce qui DIVERGE
...                 d'une release à l'autre, ce qui s'y révèle ÉQUIVALENT (une
...                 équivalence mesurée vaut une divergence mesurée), et le
...                 piège que deux jeux de données concurrents installent sur la
...                 cible.
...
...                 **LECTURE SEULE.** Aucun scénario n'écrit, ne crée ni
...                 n'annule quoi que ce soit. Aucun job n'est planifié, aucune
...                 LUW n'est validée, et les noms de jobs ne sont jamais gravés :
...                 ils sont DÉCOUVERTS sur le système, parce que les porteurs de
...                 cas mesurés diffèrent d'une cible à l'autre.
...
...                 Le canal est **optionnel** : sur un poste sans `pyrfc`
...                 (aucune roue précompilée au-delà de Python 3.12) ou sans
...                 runtime natif NW RFC, la suite se SAUTE au lieu de rougir, y
...                 compris dans un run complet de ``tests/robot/``. Le tag
...                 ``rfc`` permet en plus de l'inclure ou de l'exclure.
...
...                 **Prérequis d'environnement, et ce n'en est pas un détail :**
...                 la cible est jointe à travers un **relais TCP local**
...                 (``${RFC_ASHOST}`` par défaut), qui réaligne le port et le
...                 numéro d'instance. Ce n'est pas un contournement : le
...                 protocole DÉRIVE le port du numéro d'instance (base + numéro,
...                 ce que le scénario 7 prouve en lisant le port refusé), or le
...                 conteneur publie ses ports décalés. Viser directement l'hôte
...                 publié obligerait à annoncer un numéro d'instance que
...                 l'instance interne ne porte pas, et la connexion échouerait
...                 en réclamant une passerelle qui n'existe pas. Le relais doit
...                 donc être levé AVANT toute exécution, et l'adresse reste une
...                 variable surchargeable. Son absence se lit comme un refus de
...                 communication, jamais comme un problème de compte.
...
...                 Autres prérequis : un interpréteur 3.10 à 3.12 portant
...                 ``pyrfc==3.3.1``, un runtime NW RFC (souvent déjà déposé par
...                 le composant « SAP NWRFC x64 Shared » de SAP GUI for Windows
...                 8.00 : ``packaging/install-rfc.ps1 -CheckOnly`` le dit), et
...                 les deux canaux visant le MÊME mandant.
...
...                 Exemple :
...                 | robot --pythonpath src --include rfc
...                 | ...   -v "RFC_PASSWORD: Secret:***"
...                 | ...   --outputdir results/rfc2023
...                 | ...   tests/robot/api/canal_rfc_abap2023.robot

Resource            ../../../resources/rfc_keywords.resource
Resource            ../../../resources/api_keywords.resource

Suite Setup         Run Keywords    Skip Unless Rfc Channel Is Available
...                     AND    Open Rfc Channel
Suite Teardown      Run Keywords    Close Rfc Channel    AND    Close Api Channel

Test Tags           rfc


*** Variables ***
# --- La cible, et RIEN qu'elle : ajouter une release ajoute un jeu de
# variables, jamais une branche conditionnelle dans un test.
${RFC_ASHOST}                   127.0.0.2
${RFC_SYSNR}                    00
${RFC_CLIENT}                   001
${RFC_USER}                     DEVELOPER
${RFC_PASSWORD}                 ${EMPTY}    # OBLIGATOIRE : -v "RFC_PASSWORD: Secret:<motdepasse>"
${RFC_LANG}                     EN
${API_URL}                      http://localhost:50100
${TARGET_ID}                    abap-platform-2023

# Ce qui PROUVE la cible : sa release et son kernel. Ce qui ne prouve rien, et
# le scénario 1 le dit explicitement : l'identifiant système et le nom d'hôte
# applicatif, identiques sur les deux conteneurs du poste, et l'adresse IP,
# volatile d'un redémarrage à l'autre.
${EXPECTED_RELEASE}             758
${EXPECTED_KERNEL}              793
# La release de l'AUTRE conteneur du poste. Elle sert de contre-épreuve : une
# campagne verte contre le mauvais système est le risque que ce scénario ferme.
${PEER_RELEASE}                 754

# Données métier du modèle de démonstration (jamais de volumétrie gravée : les
# scénarios asserttent des relations, les chiffres du plan servent de calage).
${AIRLINE}                      LH
${FLIGHT_CONNECTION}            0400

# Codes techniques attendus des refus (convention 3 : jamais un texte).
${CODE_TABLE_ABSENTE}           TABLE_NOT_AVAILABLE
${CODE_TABLE_SANS_DONNEES}      TABLE_WITHOUT_DATA
${CODE_MODULE_ABSENT}           FU_NOT_FOUND
${CODE_PARAMETRE_INVALIDE}      RFC_INVALID_PARAMETER
${CODE_OUVERTURE_REFUSEE}       RFC_LOGON_FAILURE
${CODE_COMMUNICATION}           RFC_COMMUNICATION_FAILURE

# Identifiants de message attendus (classe, type, numéro) : le critère FIN qui
# complète le code, et tout aussi indépendant de la langue.
${MSG_TABLE_ABSENTE}            DA/E/131
${MSG_CHAMP_ABSENT}             AD/E/718
${MSG_MODULE_ABSENT}            FL/E/046


*** Test Cases ***
La Cible Se Prouve Par Sa Release Et Ses Composants Jamais Par Son Identifiant
    [Documentation]    Trois sources d'identité lues et confrontées : les
    ...    attributs de la connexion, la fiche que le système publie sur
    ...    lui-même, et l'inventaire de ses composants logiciels.
    ...
    ...    Ce que ce scénario refuse d'utiliser, et c'est son objet même :
    ...    l'identifiant système et le nom d'hôte applicatif sont IDENTIQUES sur
    ...    les deux conteneurs de ce poste, donc une campagne qui s'y fierait
    ...    serait verte contre le mauvais système. L'adresse IP publiée est
    ...    écartée elle aussi : elle a changé entre deux relevés du même système
    ...    à un jour d'intervalle, un conteneur redémarré reprenant l'adresse
    ...    libre suivante. Et le nom d'hôte porté par les attributs de connexion
    ...    est celui du poste CLIENT, pas celui du serveur.
    ...
    ...    Restent la release, le kernel et les composants : ce sont les ancres.
    ${identite}=    Read System Identity
    Should Be Equal    ${identite}[client]    ${RFC_CLIENT}
    ...    msg=Mandant servi différent du mandant demandé : la population lue ne serait pas celle attendue.
    Should Be Equal    ${identite}[user]    ${RFC_USER}
    ${systeme}=    Read System Information
    Should Be Equal    ${systeme}[RFCSAPRL]    ${identite}[partnerRel]
    ...    msg=Les deux sources d'identité ne s'accordent pas sur la release.
    Should Be Equal    ${systeme}[RFCKERNRL]    ${identite}[kernelRel]
    ...    msg=Les deux sources d'identité ne s'accordent pas sur le kernel.
    Should Be Equal    ${systeme}[RFCSAPRL]    ${EXPECTED_RELEASE}
    ...    msg=La cible jointe est en release ${systeme}[RFCSAPRL], pas ${EXPECTED_RELEASE}.
    Should Be Equal    ${systeme}[RFCKERNRL]    ${EXPECTED_KERNEL}
    Should Not Be Equal    ${systeme}[RFCSAPRL]    ${PEER_RELEASE}
    ...    msg=La release jointe est celle de l'AUTRE conteneur du poste : la campagne viserait le mauvais système.
    ${base}=    Read Release Of Software Component    ${BASE_SOFTWARE_COMPONENT}
    Should Be Equal    ${base}    ${EXPECTED_RELEASE}
    ...    msg=Le composant de base porte la release ${base} là où le système annonce ${EXPECTED_RELEASE} : les deux sources se contredisent.

Le Contrat De Champs Se Lit Sur La Cible Jamais De Memoire
    [Documentation]    Le piège de diagnostic du canal, et la seule façon de s'en
    ...    immuniser. Une liste de champs valable sur une release peut ne pas
    ...    l'être sur l'autre, et le refus accuse alors la TABLE d'être sans
    ...    données alors qu'elle est pleine et que la faute est dans un nom de
    ...    champ.
    ...
    ...    La contre-épreuve est JOUÉE, pas citée : la liste obtenue de la cible
    ...    passe intégralement en relecture, un seul nom inventé fait échouer la
    ...    lecture entière. C'est ce couple qui prouve que le code désigne la
    ...    mauvaise chose. Le refus est en outre caractérisé par son identifiant
    ...    de message, plus fin que le code et tout aussi non localisé.
    ${champs}=    Read Field Names Of The Field Catalog
    Should Not Be Empty    ${champs}    msg=Le catalogue de champs ne se décrit pas lui-même.
    ${relu}=    Read The Field Catalog With Every Real Field    ${champs}
    Should Not Be Empty    ${relu}
    ...    msg=Contre-épreuve en échec : la table refuse aussi ses PROPRES champs, le code accuserait alors autre chose.
    ${refus}=    Reading A Missing Field Should Be Refused With Code
    ...    ${CODE_TABLE_SANS_DONNEES}
    Refusal Should Carry Message Id    ${refus}    ${MSG_CHAMP_ABSENT}

Le Jeu De Demonstration Classique Se Compte Et Type Ses Montants
    [Documentation]    L'équivalence mesurée entre les deux releases, et elle a
    ...    de la valeur : c'est elle qui autorise UNE suite paramétrée par la
    ...    cible plutôt qu'une suite par release.
    ...
    ...    Les comptes relevés au plan ne sont pas gravés ici : ce sont des
    ...    RELATIONS qui s'assertent, pour que la campagne reste vraie sur un
    ...    système dont le jeu de démonstration aurait été régénéré. La leçon de
    ...    typage, elle, est identique des deux côtés : le même montant revient
    ...    en TEXTE par la lecture de table et en décimal ABAP par l'interface
    ...    métier. Une assertion numérique convertit, elle ne compare jamais les
    ...    deux représentations.
    ${mandants}=    Read Client Directory
    ${codes}=    Get Values From Dicts    ${mandants}    MANDT
    Should Contain    ${codes}    ${RFC_CLIENT}
    ...    msg=Le mandant de connexion ne figure pas dans l'annuaire des mandants.
    ${compagnies}=    Count Airlines
    ${liaisons}=    Count Flight Connections
    ${produits}=    Count Products
    Should Be True    ${compagnies} > 0    msg=Aucune compagnie : jeu de démonstration absent ?
    Should Be True    ${liaisons} > 0    msg=Aucune liaison aérienne : jeu de démonstration absent ?
    Should Be True    ${produits} > 0    msg=Aucun produit : jeu de démonstration marchand absent ?
    ${par_table}=    Read Flight Price    ${AIRLINE}    ${FLIGHT_CONNECTION}
    ${vols}=    Read Flights Of Airline By Bapi    ${AIRLINE}
    Should Be Equal As Numbers    ${par_table}[PRICE]    ${vols}[FLIGHT_LIST][0][PRICE]
    ...    msg=Le même prix diffère selon la représentation : la conversion numérique est le seul rapprochement valide.

Deux Catalogues De Compagnies Coexistent Et Il Faut Nommer Celui Qu On Lit
    [Documentation]    Le constat le plus exploitable de l'exploration, et il est
    ...    formulé À L'ENVERS pour qu'un piège silencieux devienne une assertion
    ...    bruyante.
    ...
    ...    La cible porte DEUX catalogues de compagnies aériennes, de populations
    ...    différentes : le modèle de démonstration classique et le modèle de
    ...    voyage moderne. Un croisement qui rapproche le comptage d'un canal sur
    ...    l'un et le comptage de l'autre canal sur l'autre produit un écart
    ...    parfaitement reproductible, attribué à un défaut qui n'existe pas.
    ...    Inversement, une égalité obtenue en les confondant serait un vert
    ...    construit sur une coïncidence.
    ...
    ...    Ce test échoue donc si quelqu'un « corrige » un jour l'un des deux
    ...    comptages pour les faire coïncider.
    ${classiques}=    Read Airline Codes
    ${modernes}=    Read Modern Airline Codes
    ${total_classique}=    Get Length    ${classiques}
    ${total_moderne}=    Get Length    ${modernes}
    Should Be True    ${total_classique} > 0 and ${total_moderne} > 0
    ...    msg=Un des deux catalogues de compagnies est vide : la comparaison ne porterait sur rien.
    Should Not Be Equal As Integers    ${total_classique}    ${total_moderne}
    ...    msg=Les deux catalogues comptent le même nombre de compagnies : ils seraient devenus confondables, et le piège que ce test protège n'aurait plus de garde-fou.
    ${propres_au_moderne}=    Evaluate    sorted(set($modernes) - set($classiques))
    Should Be Empty    ${propres_au_moderne}
    ...    msg=Le catalogue moderne porte des codes absents du classique (${propres_au_moderne}) : l'inclusion mesurée ne tient plus.
    ${ecart}=    Evaluate    sorted(set($classiques) - set($modernes))
    ${taille_ecart}=    Get Length    ${ecart}
    ${ecart_attendu}=    Evaluate    ${total_classique} - ${total_moderne}
    Should Be Equal As Integers    ${taille_ecart}    ${ecart_attendu}
    ...    msg=L'écart entre les deux comptes n'est pas entièrement expliqué par les codes présents dans l'un et absents de l'autre.
    Log    Codes portés par le seul catalogue classique : ${ecart}.

Le Meme Fait Metier Par Deux Canaux Sur Le Modele Moderne
    [Documentation]    Deux croisements que la campagne de la release précédente
    ...    ne faisait pas : ils portent sur le modèle de voyage moderne, et ils
    ...    passent par un service que le catalogue de cette cible publie.
    ...
    ...    Les deux canaux visent le MÊME mandant : les faire diverger
    ...    comparerait deux populations et fabriquerait un écart qui n'existe
    ...    pas. Le premier appel d'un service jamais sollicité sur un système
    ...    froid peut être lent, ce n'est pas une panne, d'où un préflight
    ...    patient. Et l'ensemble choisi n'est pas une projection à brouillons,
    ...    sinon le comptage agrégerait des états que la table ne porte pas.
    ...
    ...    Le dernier pas est celui qui donne son prix au scénario précédent : le
    ...    comptage OData des compagnies suit le catalogue MODERNE, et il diffère
    ...    du catalogue classique. Nommer le mauvais côté produirait un écart
    ...    stable et faux.
    Open Api Channel    base_url=${API_URL}    user=${RFC_USER}
    ...    password=${RFC_PASSWORD}    client=${RFC_CLIENT}    alias=odata
    Wait Until Api Channel Is Available    alias=odata    timeout=60s
    ${mandant_api}=    Api Channel Client    alias=odata
    Should Be Equal    ${mandant_api}    ${RFC_CLIENT}
    ...    msg=Les deux canaux ne visent pas le même mandant : la comparaison serait truquée.
    ${voyages_rfc}=    Count Travels
    ${voyages_odata}=    Count Business Entities    ${MODERN_TRAVELS}    alias=odata
    Should Be True    ${voyages_rfc} > 0    msg=Aucun voyage côté RFC : rien à croiser.
    Should Be Equal As Integers    ${voyages_rfc}    ${voyages_odata}
    ...    msg=Les deux canaux ne comptent pas les mêmes voyages : ${voyages_rfc} par RFC contre ${voyages_odata} par OData.
    ${compagnies_rfc}=    Count Modern Airlines
    ${compagnies_odata}=    Count Business Entities    ${MODERN_AIRLINES}    alias=odata
    Should Be Equal As Integers    ${compagnies_rfc}    ${compagnies_odata}
    ...    msg=Les deux canaux ne comptent pas les mêmes compagnies modernes : ${compagnies_rfc} par RFC contre ${compagnies_odata} par OData.
    ${classiques}=    Count Airlines
    Should Not Be Equal As Integers    ${compagnies_odata}    ${classiques}
    ...    msg=Le service moderne compte autant de compagnies que le catalogue classique : le croisement pourrait alors être vert en visant le mauvais catalogue.

Les Refus Applicatifs Se Classent Par Code Et Par Identifiant De Message
    [Documentation]    Quatre refus provoqués sur la connexion ouverte. Chacun est
    ...    jugé sur son CODE technique, et les trois refus APPLICATIFS le sont en
    ...    outre sur leur identifiant de message (classe, type, numéro).
    ...
    ...    Pourquoi asserter les deux : le code est stable mais grossier, deux
    ...    causes très différentes pouvant le partager, ainsi le champ inexistant
    ...    dont le refus accuse la table d'être sans données. L'identifiant de
    ...    message désigne le message ABAP exact et reste indépendant de la
    ...    langue. Les asserter ensemble caractérise un refus sans jamais toucher
    ...    à son libellé.
    ...
    ...    Le quatrième refus est d'une autre nature, et c'est une preuve et non
    ...    un manque : levé par le runtime CLIENT, il n'a jamais atteint
    ...    l'application, donc il ne porte AUCUN identifiant de message. Lui en
    ...    prêter un serait inventer.
    ${table}=    Reading A Missing Table Should Be Refused With Code
    ...    ${CODE_TABLE_ABSENTE}
    Refusal Should Carry Message Id    ${table}    ${MSG_TABLE_ABSENTE}
    ${champ}=    Reading A Missing Field Should Be Refused With Code
    ...    ${CODE_TABLE_SANS_DONNEES}
    Refusal Should Carry Message Id    ${champ}    ${MSG_CHAMP_ABSENT}
    ${module}=    Calling A Missing Function Module Should Be Refused With Code
    ...    ${CODE_MODULE_ABSENT}
    Refusal Should Carry Message Id    ${module}    ${MSG_MODULE_ABSENT}
    ${parametre}=    Calling With An Unknown Parameter Should Be Refused With Code
    ...    ${CODE_PARAMETRE_INVALIDE}
    Refusal Should Carry No Message Id    ${parametre}
    # L'oracle par identifiant éprouvé COMME critère d'échec, et pas seulement
    # relu sur une fiche : sans ce pas, l'assertion fine ne serait jamais ce qui
    # décide du verdict.
    ${direct}=    Calling A Missing Function Module Should Be Refused With Message Id
    ...    ${MSG_MODULE_ABSENT}
    Should Be Equal    ${direct}[code]    ${CODE_MODULE_ABSENT}
    ...    msg=Le refus jugé par son identifiant de message ne porte pas le code technique attendu.

Deux Refus D Ouverture Que Rien Ne Distingue Et Un Troisieme D Une Autre Nature
    [Documentation]    Trois ouvertures qui DOIVENT échouer, donc rien à fermer.
    ...
    ...    La divergence de refus mesurée entre les deux releases est ici : sur
    ...    la release précédente, mot de passe faux et mandant inexistant
    ...    partageaient le code et « seul le texte les séparait ». Sur celle-ci,
    ...    les deux rendent le même code ET le même texte, mot pour mot. Le
    ...    scénario constate donc un refus d'ouverture de session et
    ...    **n'affirme rien sur sa cause** : il asserte l'INDISTINCTION, ce qui
    ...    est une observation, alors qu'asserter le texte serait une faute.
    ...
    ...    Le troisième refus est d'une autre classe, et il documente dans le
    ...    test lui-même la raison d'être du relais décrit en préconditions : son
    ...    message nomme le port RÉELLEMENT contacté, et ce port est la base plus
    ...    le numéro d'instance. Le jour où quelqu'un voudra « simplifier » la
    ...    configuration en visant directement le port publié, ce scénario
    ...    nommera la mécanique en cause.
    ...
    ...    Chaque refus d'identification n'est provoqué qu'UNE fois par
    ...    exécution : les tentatives infructueuses se cumulent côté serveur, et
    ...    un compte verrouillé rendrait toute la campagne rouge pour une raison
    ...    sans rapport avec le canal.
    ${mot_de_passe}=    Opening With A Wrong Password Should Be Refused With Code
    ...    ${CODE_OUVERTURE_REFUSEE}
    ${mandant}=    Opening On An Unknown Client Should Be Refused With Code
    ...    ${CODE_OUVERTURE_REFUSEE}
    Should Be Equal    ${mot_de_passe}[message]    ${mandant}[message]
    ...    msg=Les deux refus d'ouverture se distinguent par leur texte sur cette release : le constat d'indistinction ne tient plus, et il faudrait le remesurer avant d'en tirer quoi que ce soit.
    ${communication}=    Opening On An Unreachable System Should Be Refused With Code
    ...    ${CODE_COMMUNICATION}
    Refusal Should Carry No Message Id    ${communication}
    ${port_attendu}=    Evaluate
    ...    ${DISPATCHER_PORT_BASE} + int("${UNREACHABLE_SYSNR}")
    Should Contain    ${communication}[message]    ${RFC_ASHOST}:${port_attendu}
    ...    msg=Le refus de communication ne nomme pas le port ${port_attendu} : la dérivation du port depuis le numéro d'instance n'est plus démontrée, et la précondition du relais devient une histoire au lieu d'une mesure.
    ${ouverts}=    List Open Rfc Channels
    Length Should Be    ${ouverts}    1
    ...    msg=Un refus d'ouverture a laissé une connexion derrière lui : ce serait une session utilisateur restée ouverte côté serveur.

Le Journal Des Jobs Est Lu Sans Plafond Et Sa Classification Est Re Derivable
    [Documentation]    Les cinq issues de l'attente d'un job de fond existent sur
    ...    les deux cibles : c'est l'équivalence utile. Ce qui DIVERGE, ce sont
    ...    les jobs qui les portent, mesuré des deux côtés. C'est la preuve de la
    ...    décision prise à la génération de la suite précédente : ne graver
    ...    aucun nom de job et découvrir les cibles sur le système. Un nom
    ...    d'infrastructure gravé aurait tenu sur une release et sauté sur
    ...    l'autre, en donnant l'impression que l'attente est cassée.
    ...
    ...    Ce test garde le mécanisme de découverte HONNÊTE : il re-dérive
    ...    lui-même la classification depuis les décomptes bruts par job et la
    ...    confronte à celle que la perception propose. Si quelqu'un remplaçait
    ...    un jour la découverte par une liste de noms, la liste ne coïnciderait
    ...    plus avec une re-dérivation faite sur le journal du moment, et ce test
    ...    le dirait. C'est la seule façon de vérifier qu'une découverte découvre.
    ...
    ...    Le journal est lu SANS plafond : un plafond ne tronque pas seulement
    ...    le résultat, il fausse la classification en silence, et c'est
    ...    exactement l'erreur qui avait faussé la première exploration de
    ...    l'autre release.
    ...
    ...    Les attentes elles-mêmes ne sont pas rejouées ici : la suite soeur les
    ...    éprouve déjà sur cette cible, branche par branche. Ce test ne garde
    ...    que ce qui est nouveau.
    ${catalogue}=    Job Log Catalogue
    Should Be True    ${catalogue}[rows] > 0
    ...    msg=Journal des jobs vide : aucune issue de l'attente ne serait éprouvable ici.
    ${comptes}=    Get Dictionary Values    ${catalogue}[statuses]
    ${total}=    Evaluate    sum($comptes)
    Should Be Equal As Integers    ${total}    ${catalogue}[rows]
    ...    msg=Des runs lus ne sont pas classés : le décompte par statut perd des lignes.
    ${modele}=    Get Background Job Status Model
    FOR    ${cas}    IN    done    aborted_with_finished    pipeline    unmapped
        Dictionary Should Contain Key    ${catalogue}[cases]    ${cas}
        ...    msg=Le cas d'attente « ${cas} » n'est pas proposé par la perception du journal.
        ${porteurs}=    Get From Dictionary    ${catalogue}[cases]    ${cas}
        Log    Cas « ${cas} » porté sur cette cible par ${porteurs}.
        Every Discovered Job Should Really Carry Its Case    ${cas}    ${porteurs}
        ...    ${catalogue}    ${modele}
    END
    ${porteurs_termines}=    Get From Dictionary    ${catalogue}[cases]    done
    Should Not Be Empty    ${porteurs_termines}
    ...    msg=Aucun job dont tous les runs sont terminés : le journal ne porterait aucune issue conclusive.

La Surface Du Canal Devient Un Artefact Comparable Entre Deux Releases
    [Documentation]    La question du plan (« quels modules ici et pas là-bas »)
    ...    ne se répond pas par une note dans un document : elle se répond par un
    ...    artefact produit sur chaque cible et comparé hors système. Le dépôt
    ...    possédait ce patron pour l'inventaire du dictionnaire et pour le
    ...    croisement entre canaux ; le canal RFC ne l'avait pas.
    ...
    ...    Deux propriétés sont éprouvées ici, et ce sont elles qui rendent une
    ...    comparaison future honnête. D'abord le DÉTERMINISME : deux relevés de
    ...    la même cible produisent le même hash, l'horodatage étant exclu du
    ...    calcul, donc une différence de hash signifiera une différence réelle.
    ...    Ensuite l'IDENTITÉ : un artefact porte la release, le kernel et les
    ...    composants de la cible qui l'a produit, sans quoi comparer deux
    ...    artefacts reviendrait à comparer deux inconnues, ce que l'identifiant
    ...    système ne rattraperait pas puisqu'il est le même des deux côtés.
    ...
    ...    Ce que ce test ne prouve PAS, et il vaut mieux le dire que le laisser
    ...    croire : la détection d'écarts entre deux cibles RÉELLES, faute d'une
    ...    seconde cible joignable pendant la génération. Cette moitié-là est
    ...    verrouillée hors SAP, où la comparaison est éprouvée sur ses trois
    ...    catégories, ses changements de release et son refus de comparer deux
    ...    périmètres différents.
    ${premier}=    Write Channel Surface Of Target
    ...    ${OUTPUT DIR}/surface-${TARGET_ID}-1.json    ${TARGET_ID}
    ${second}=    Write Channel Surface Of Target
    ...    ${OUTPUT DIR}/surface-${TARGET_ID}-2.json    ${TARGET_ID}
    Should Be Equal    ${premier}[sha256]    ${second}[sha256]
    ...    msg=Deux relevés de la même cible rendent des hash différents : l'artefact n'est pas déterministe, et toute comparaison ultérieure serait du bruit.
    Should Be True    ${premier}[summary][measures] > 0
    ...    msg=Artefact sans aucune mesure : il ne comparerait rien.
    Should Be True    ${premier}[summary][components] > 0
    ...    msg=Artefact sans inventaire de composants : la source d'identité la plus riche de la cible manquerait.
    ${comparaison}=    Compare Channel Surfaces    ${premier}[path]    ${second}[path]
    Should Be True    ${comparaison}[compatible]
    ...    msg=Deux relevés du même périmètre sont déclarés non comparables : la porte de périmètre se referme sur des artefacts identiques.
    Should Be Empty    ${comparaison}[measure_differences]
    ...    msg=La comparaison invente un écart entre deux relevés identiques de la même cible.
    Should Be Empty    ${comparaison}[identity_differences]
    Should Be Empty    ${comparaison}[components_only_in_a]
    Should Be Empty    ${comparaison}[components_only_in_b]
    Artefact Should Carry The Identity Of Its Target    ${premier}[path]

Le Canal Se Referme Entierement Y Compris Apres Un Refus
    [Documentation]    Une connexion RFC orpheline est une session utilisateur
    ...    restée ouverte côté serveur : le teardown doit toutes les emporter. Le
    ...    teardown de ce test rouvre le canal principal, pour que l'ordre des
    ...    tests ne soit pas un prérequis caché.
    [Teardown]    Open Rfc Channel
    Open Rfc Channel    alias=secondaire
    ${principal}=    Echo Through Rfc Channel    canal-principal
    ${second}=    Echo Through Rfc Channel    canal-secondaire    alias=secondaire
    Should Be Equal    ${principal}[ECHOTEXT]    canal-principal
    Should Be Equal    ${second}[ECHOTEXT]    canal-secondaire
    ...    msg=Les deux alias ne répondent pas indépendamment.
    ${ouverts}=    List Open Rfc Channels
    Length Should Be    ${ouverts}    2
    Close Rfc Channel
    ${restants}=    List Open Rfc Channels
    Should Be Empty    ${restants}
    ...    msg=La fermeture globale a laissé une connexion ouverte côté serveur.
    Calling A Closed Rfc Channel Should Name The Opening Keyword    secondaire


*** Keywords ***
Every Discovered Job Should Really Carry Its Case
    [Documentation]    Re-dérive, depuis les décomptes BRUTS de statuts du
    ...    journal, le fait qu'un job porte bien le cas d'attente sous lequel la
    ...    perception l'a rangé. C'est le contrôle qui rend la découverte
    ...    vérifiable : une liste de noms gravée ne survivrait pas à cette
    ...    confrontation avec le journal du moment.
    ...
    ...    Les statuts d'attente et la carte des statuts connus viennent de la
    ...    bibliothèque, jamais d'une copie tenue ici : une carte recopiée
    ...    dérive.
    [Arguments]    ${cas}    ${porteurs}    ${catalogue}    ${modele}
    FOR    ${job}    IN    @{porteurs}
        ${statuts}=    Get From Dictionary    ${catalogue}[jobs]    ${job}
        ${en_attente}=    Evaluate
        ...    [s for s in $statuts if s in $modele['pending']]
        ${hors_carte}=    Evaluate
        ...    [s for s in $statuts if s not in $modele['labels']]
        IF    '${cas}' == 'done'
            Should Be Empty    ${en_attente}
            ...    msg=Le job ${job} est rangé en « terminé » alors qu'un de ses runs est encore dans le pipeline.
            Should Not Be Empty    ${statuts}
        ELSE IF    '${cas}' == 'aborted_with_finished'
            Should Be True    $statuts.get('A', 0) > 0
            ...    msg=Le job ${job} est rangé en « annulé » sans porter aucun run annulé.
            Should Be True    $statuts.get('F', 0) > 0
            ...    msg=Le job ${job} ne porte aucun run terminé : la priorité de l'annulation ne serait pas éprouvable sur lui.
        ELSE IF    '${cas}' == 'pipeline'
            Should Not Be Empty    ${en_attente}
            ...    msg=Le job ${job} est rangé dans le pipeline sans porter aucun statut d'attente.
        ELSE IF    '${cas}' == 'unmapped'
            Should Not Be Empty    ${hors_carte}
            ...    msg=Le job ${job} est rangé « hors carte » alors que tous ses statuts sont cartographiés.
        END
    END

Artefact Should Carry The Identity Of Its Target
    [Documentation]    Vérifie qu'un artefact de surface porte l'identité de la
    ...    cible qui l'a produit. Un artefact anonyme se comparerait à n'importe
    ...    quoi, et sur ce poste l'identifiant système ne rattraperait rien : les
    ...    deux conteneurs le partagent.
    [Arguments]    ${chemin}
    ${artefact}=    Read Rfc Surface Artifact    ${chemin}
    Should Be Equal    ${artefact}[identity][release]    ${EXPECTED_RELEASE}
    ...    msg=L'artefact ne porte pas la release de la cible : le comparer à un autre reviendrait à comparer deux inconnues.
    Should Be Equal    ${artefact}[identity][kernel]    ${EXPECTED_KERNEL}
    Should Be Equal    ${artefact}[identity][client]    ${RFC_CLIENT}
    ${composants}=    Evaluate    [c["name"] for c in $artefact["components"]]
    Should Contain    ${composants}    ${BASE_SOFTWARE_COMPONENT}
    ...    msg=L'artefact ne porte pas le composant de base : sa source d'identité la plus riche manquerait.
