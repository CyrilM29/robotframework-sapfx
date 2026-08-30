*** Settings ***
Documentation       **Configuration de sécurité de la cible ABAP Platform 2023**
...                 Spec: specs/secu-configuration-abap2023.md (sha256:d74df48a394a, 2026-08-30)
...                 (release 758), lue par le canal RFC, en LECTURE SEULE.
...
...                 Jumelle de `secu_configuration_a4h.robot`. Les deux
...                 partagent le vocabulaire (`resources/security_keywords.resource`)
...                 et divergent par leur BASELINE, parce que les deux releases
...                 ne sont pas durcies pareil. Ce que la comparaison des deux
...                 suites établit, mesuré le 2026-08-29 : cette release exige
...                 **10 caractères** de mot de passe contre 6, impose les
...                 **quatre exigences de composition** (chiffre, lettre,
...                 minuscule, majuscule) que la 1909 laisse toutes à zéro, et
...                 arme une **déconnexion automatique** à une heure là où la
...                 1909 n'en a aucune. Six paramètres qui diffèrent, et
...                 c'est la raison d'être de deux suites : une suite unique
...                 aurait dû asserter la posture la plus faible (aveugle sur
...                 cette cible) ou la plus forte (rouge à vie sur l'autre).
...
...                 Ce qui se CONFIRME identique est un résultat aussi : journal
...                 d'audit actif et protégé, passerelle sous liste de contrôle,
...                 contrôle d'autorisation RFC armé, compte SAP* codé en dur
...                 neutralisé, mandant de référence verrouillé, transport en
...                 clair. Ces contrôles-là sont donc BLOQUANTS des deux côtés.
...
...                 **Prérequis d'environnement, et ce n'en est pas un détail.**
...                 La cible est jointe à travers un **relais TCP local**
...                 (``${RFC_ASHOST}`` par défaut), qui réaligne le port et le
...                 numéro d'instance : le protocole DÉRIVE le port du numéro
...                 d'instance, or ce conteneur publie ses ports décalés. Le
...                 relais doit être levé AVANT toute exécution. Piège majeur :
...                 sans lui, l'adresse répond quand même (la boucle locale
...                 couvre toute sa plage et l'autre conteneur écoute partout),
...                 donc la suite parlerait à la release 754 en croyant auditer
...                 la 758. Le premier scénario existe pour attraper exactement
...                 cela.
...
...                 Autres prérequis : un interpréteur 3.10 à 3.12 portant
...                 ``pyrfc`` et un runtime NW RFC. Le canal est optionnel : sans
...                 lui la suite se SAUTE au lieu de rougir.
...
...                 Exemple :
...                 | robot --pythonpath src --include secu
...                 | ...   -v "RFC_PASSWORD: Secret:***"
...                 | ...   --outputdir results/secu-2023
...                 | ...   tests/robot/api/secu_configuration_abap2023.robot

Resource            ../../../resources/security_keywords.resource

Suite Setup         Run Keywords    Skip Unless Rfc Channel Is Available
...                     AND    Open Security Audit Channel
Suite Teardown      Close Security Audit Channel

Test Tags           secu    rfc


*** Variables ***
# --- La cible, et rien qu'elle. L'adresse est celle du relais, pas celle du
# conteneur : viser directement le port publié obligerait à annoncer un numéro
# d'instance que l'instance interne ne porte pas.
${RFC_ASHOST}                   127.0.0.2
${RFC_SYSNR}                    00
${RFC_CLIENT}                   001
${RFC_USER}                     DEVELOPER
${RFC_PASSWORD}                 ${EMPTY}    # OBLIGATOIRE : -v "RFC_PASSWORD: Secret:<motdepasse>"
${RFC_LANG}                     EN

# Ce qui PROUVE la cible. Ni l'identifiant système ni le nom d'hôte applicatif
# ne le font : les deux conteneurs du poste annoncent A4H et vhcala4h, et
# l'adresse IP change d'un redémarrage à l'autre. ${PEER_RELEASE} est la
# contre-épreuve, et elle est ici la garde du relais : sans relais, c'est
# exactement cette release-là que la suite mesurerait.
${EXPECTED_RELEASE}             758
${EXPECTED_KERNEL}              793
${PEER_RELEASE}                 754

${REFERENCE_CLIENT}             000
${POSTURE_REFERENCE}            posture-abap2023-758
${UNKNOWN_PARAMETER}            login/parametre_qui_nexiste_pas

# Baseline des inventaires, MESURÉE sur cette cible le 2026-08-29.
${EXPECTED_AUDIT_VERDICT}       armed_without_filter
${EXPECTED_STORED_LOGONS}       ${3}
${EXPECTED_BASIS_PATCH}         0002

# La baseline de mot de passe MESURÉE sur cette release, celle qui la distingue
# de sa jumelle. Déclarée en variables pour que l'écart entre les deux suites
# se lise d'un coup d'oeil.
${MIN_PASSWORD_LENGTH}          10
${MIN_COMPOSITION_CLASSES}      1


*** Test Cases ***
La cible est bien celle que la suite croit auditer
    [Documentation]    Sans ce scénario, toute la campagne peut être verte
    ...    contre le mauvais système, et ici le risque est CONCRET : si le
    ...    relais TCP n'est pas posé, l'adresse visée répond quand même et c'est
    ...    l'autre conteneur qui parle. Comme les deux annoncent le même
    ...    identifiant système et le même nom d'hôte applicatif, rien dans la
    ...    réponse ne le trahit : seules la release et le kernel le font.
    ${info}=    Current System Identity
    Should Be Equal    ${info}[RFCSAPRL]    ${EXPECTED_RELEASE}
    ...    msg=Release inattendue. Cause la plus probable : le relais TCP n'est pas posé et la suite parle à l'autre conteneur.
    Should Be Equal    ${info}[RFCKERNRL]    ${EXPECTED_KERNEL}
    ...    msg=Kernel inattendu sur une release pourtant conforme : cible douteuse.
    Should Not Be Equal    ${info}[RFCSAPRL]    ${PEER_RELEASE}
    ...    msg=La suite mesure la release de l'AUTRE conteneur du poste : relais absent ou mal orienté.

Un paramètre inconnu est rendu non mesurable, jamais vide
    [Documentation]    Le piège central de tout audit de configuration SAP, et
    ...    la raison d'être de la couche de lecture. Le module ABAP ne refuse
    ...    PAS un paramètre qu'il ne connaît pas : il rend un code de retour non
    ...    nul et une chaîne VIDE. Un contrôle qui lit la valeur sans regarder
    ...    le code est donc vert sur un nom mal orthographié, et conclut à une
    ...    absence de durcissement qu'il n'a jamais mesurée.
    ...
    ...    Vérifié sur CETTE release aussi : le comportement est une propriété
    ...    du module, pas de la version, mais une campagne qui l'affirme sans
    ...    l'avoir mesuré des deux côtés ne fait que le supposer.
    ${inconnu}=    Read Security Parameters    ${UNKNOWN_PARAMETER}
    Should Be Equal    ${inconnu}[0][status]    unknown
    Should Be Equal    ${inconnu}[0][value]    ${None}
    ...    msg=Un paramètre inconnu a rendu une valeur : la garde sur le code de retour ne joue plus.
    ${connu}=    Read Security Parameters    login/min_password_lng
    Should Be Equal    ${connu}[0][status]    defined
    Should Not Be Equal    ${connu}[0][value]    ${None}

Le nom d'un paramètre est sensible à la casse, et c'est un piège muet
    [Documentation]    Le piège le plus dangereux de ce canal, et celui qu'aucun
    ...    message ne signale. Le module est SENSIBLE À LA CASSE : le même
    ...    paramètre demandé en majuscules rend un code de retour non nul et une
    ...    chaîne vide, exactement comme un paramètre inexistant.
    ...
    ...    Le risque n'est pas théorique : normaliser un identifiant ABAP en
    ...    majuscules est un réflexe, et ce dépôt contient déjà un normaliseur
    ...    qui capitalise, destiné aux noms de CHAMPS. L'employer ici ferait
    ...    remonter TOUS les paramètres comme non positionnés, et le rapport
    ...    conclurait à un système sans aucun durcissement.
    ...
    ...    Le scénario fige donc la propriété dans les deux sens : la forme
    ...    exacte mesure, la forme en majuscules ne mesure pas.
    ${exact}=    Read Security Parameters    login/min_password_lng
    Should Be Equal    ${exact}[0][status]    defined
    ${majuscules}=    Read Security Parameters    LOGIN/MIN_PASSWORD_LNG
    Should Be Equal    ${majuscules}[0][status]    unknown
    ...    msg=La casse ne compte plus : soit le canal a changé, soit un normaliseur s'est glissé dans la lecture.
    Should Be Equal    ${majuscules}[0][value]    ${None}

Tous les paramètres audités sont reconnus par cette release
    [Documentation]    La garde à passer avant tout jugement de conformité :
    ...    elle sépare « le système n'est pas durci » de « le contrôle vise un
    ...    paramètre absent de cette release ». Sur une campagne multi-release,
    ...    c'est elle qui empêche de prendre une différence de VOCABULAIRE entre
    ...    deux versions pour une différence de POSTURE.
    ${mesures}=    Current Security Posture
    ${inconnus}=    Evaluate    [m["name"] for m in $mesures if m["status"] != "defined"]
    Should Be Empty    ${inconnus}
    ...    msg=Paramètres non reconnus par la release ${EXPECTED_RELEASE} : ${inconnus}

Le journal d'audit de sécurité est actif
    [Documentation]    Contrôle BLOQUANT, identique à celui de la jumelle : sans
    ...    journal d'audit, aucun incident n'est reconstituable après coup, et
    ...    l'écart est un incident quelle que soit la politique de l'entreprise.
    ${mesures}=    Read Security Parameters    ${PARAMS_AUDIT}
    ${c1}=    Security Control    audit.enabled    rsau/enable    enabled    1
    ...    severity=high    rationale=Sans journal d'audit, aucun incident n'est reconstituable.
    ${c2}=    Security Control    audit.integrity    rsau/integrity    enabled    1
    ...    severity=medium    rationale=Le journal doit être protégé contre la modification.
    @{controles}=    Create List    ${c1}    ${c2}
    ${verdicts}=    Judge Security Posture    ${controles}    ${mesures}
    ${resume}=    Summarize Verdicts    ${verdicts}
    Should Be Equal As Integers    ${resume}[deviation]    0
    ...    msg=Journal d'audit non conforme : ${resume}[deviating_keys]
    Should Be Equal As Integers    ${resume}[not_measurable]    0
    ...    msg=Contrôle d'audit non mesurable : ${resume}[not_measurable_keys]

La passerelle RFC est sous liste de contrôle
    [Documentation]    Contrôle BLOQUANT. Une passerelle sans liste de contrôle
    ...    accepte l'enregistrement de serveurs RFC arbitraires : c'est le
    ...    chemin d'entrée le plus classique sur un système ABAP.
    ${mesures}=    Read Security Parameters    ${PARAMS_GATEWAY}
    ${c1}=    Security Control    gateway.acl    gw/acl_mode    enabled    1
    ...    severity=high    rationale=Sans liste de contrôle, un serveur RFC arbitraire s'enregistre.
    ${c2}=    Security Control    gateway.conn_info    gw/reg_no_conn_info    enabled    1
    ...    severity=medium    rationale=Durcit le traitement des informations de connexion.
    ${c3}=    Security Control    gateway.remote_start    gw/rem_start    equals    DISABLED
    ...    severity=high
    ...    rationale=Le démarrage distant de programmes est désactivé sur cette release, la 1909 le laisse à REMOTE_SHELL.
    @{controles}=    Create List    ${c1}    ${c2}    ${c3}
    ${verdicts}=    Judge Security Posture    ${controles}    ${mesures}
    ${resume}=    Summarize Verdicts    ${verdicts}
    Should Be Equal As Integers    ${resume}[deviation]    0
    ...    msg=Passerelle non conforme : ${resume}[deviating_keys]
    ${identite}=    Current System Identity
    Log Security Posture Report    ${identite}    ${mesures}    ${controles}

Le compte SAP* codé en dur est neutralisé et l'autorisation RFC est armée
    [Documentation]    Contrôle BLOQUANT sur deux protections que rien ne
    ...    justifie de désactiver, et qui se confirment identiques d'une release
    ...    à l'autre.
    @{lot}=    Create List    login/no_automatic_user_sapstar    auth/rfc_authority_check
    ${mesures}=    Read Security Parameters    ${lot}
    ${c1}=    Security Control    logon.no_sapstar    login/no_automatic_user_sapstar
    ...    enabled    1    severity=high
    ...    rationale=Le SAP* du noyau ignore la table des utilisateurs.
    ${c2}=    Security Control    rfc.authority_check    auth/rfc_authority_check
    ...    enabled    1    severity=high
    ...    rationale=Désarmé, tout module est appelable à distance.
    @{controles}=    Create List    ${c1}    ${c2}
    ${verdicts}=    Judge Security Posture    ${controles}    ${mesures}
    ${resume}=    Summarize Verdicts    ${verdicts}
    Should Be Equal As Integers    ${resume}[deviation]    0
    ...    msg=Protection de connexion non conforme : ${resume}[deviating_keys]

La politique de mot de passe de cette release est plus stricte que celle de la 1909
    [Documentation]    Le scénario qui porte l'écart entre les deux cibles, et
    ...    la raison pour laquelle deux suites valent mieux qu'une paramétrée.
    ...    Ici les seuils sont ASSERTÉS, parce qu'ils ont été mesurés sur cette
    ...    release et qu'un retour en arrière serait un affaiblissement réel de
    ...    la cible : dix caractères, et les quatre exigences de composition
    ...    armées, là où la jumelle 1909 est à six sans aucune exigence.
    ${mesures}=    Read Security Parameters    ${PARAMS_PASSWORD_POLICY}
    ${c1}=    Security Control    password.length    login/min_password_lng
    ...    at_least    ${MIN_PASSWORD_LENGTH}    severity=high
    ...    rationale=Cette release impose dix caractères, la 1909 six.
    ${c2}=    Security Control    password.digits    login/min_password_digits
    ...    at_least    ${MIN_COMPOSITION_CLASSES}    severity=medium
    ...    rationale=Exigence de composition absente de la 1909.
    ${c3}=    Security Control    password.letters    login/min_password_letters
    ...    at_least    ${MIN_COMPOSITION_CLASSES}    severity=medium
    ...    rationale=Exigence de composition absente de la 1909.
    ${c4}=    Security Control    password.lowercase    login/min_password_lowercase
    ...    at_least    ${MIN_COMPOSITION_CLASSES}    severity=medium
    ...    rationale=Exigence de composition absente de la 1909.
    ${c5}=    Security Control    password.uppercase    login/min_password_uppercase
    ...    at_least    ${MIN_COMPOSITION_CLASSES}    severity=medium
    ...    rationale=Exigence de composition absente de la 1909.
    @{controles}=    Create List    ${c1}    ${c2}    ${c3}    ${c4}    ${c5}
    ${verdicts}=    Judge Security Posture    ${controles}    ${mesures}
    ${resume}=    Summarize Verdicts    ${verdicts}
    Should Be Equal As Integers    ${resume}[not_measurable]    0
    ...    msg=Politique de mot de passe non mesurable : ${resume}[not_measurable_keys]
    Should Be Equal As Integers    ${resume}[deviation]    0
    ...    msg=Politique de mot de passe affaiblie sur cette release : ${resume}[deviating_keys]
    ${identite}=    Current System Identity
    Log Security Posture Report    ${identite}    ${mesures}    ${controles}

La déconnexion automatique des sessions inactives est armée
    [Documentation]    Le second écart mesuré avec la 1909, et le plus visible à
    ...    l'usage : cette release ferme les sessions inactives, l'autre les
    ...    laisse ouvertes indéfiniment. Une session de dialogue abandonnée sur
    ...    un poste non verrouillé est un accès complet, donc le contrôle est
    ...    asserté ici alors que la jumelle ne peut que le rapporter.
    ${mesures}=    Read Security Parameters    rdisp/gui_auto_logout
    ${controle}=    Security Control    session.auto_logout    rdisp/gui_auto_logout
    ...    enabled    1    severity=medium
    ...    rationale=Une session de dialogue abandonnée est un accès complet.
    @{controles}=    Create List    ${controle}
    ${verdicts}=    Judge Security Posture    ${controles}    ${mesures}
    ${resume}=    Summarize Verdicts    ${verdicts}
    Should Be Equal As Integers    ${resume}[deviation]    0
    ...    msg=La déconnexion automatique n'est plus armée sur cette release : ${resume}[deviating_keys]

Le journal d'audit est armé, mais il faut savoir s'il FILTRE
    [Documentation]    Le complément indispensable du scénario précédent, et un
    ...    faux positif de conformité classique. `rsau/enable` répond « armé »,
    ...    ce qui est vrai et insuffisant : le journal peut être armé au niveau
    ...    du noyau avec ZÉRO slot de filtrage actif, auquel cas il
    ...    n'enregistre pas ce qu'un auditeur croit qu'il enregistre. Mesuré
    ...    sur les deux cibles du banc : dix slots déclarés, aucun actif.
    ...
    ...    Trois choses distinctes, et le scénario les traite différemment.
    ...    Il ASSERTE l'armement, dont l'écart serait un incident quelle que
    ...    soit la politique. Il n'exige PAS de slots actifs : ce serait rouge
    ...    à vie sur ce banc, et le jour où quelqu'un en configurerait,
    ...    l'amélioration ferait échouer un test écrit à l'envers. Il asserte
    ...    en revanche la NON-DÉRIVE du régime (`${EXPECTED_AUDIT_VERDICT}`),
    ...    au même titre que la sentinelle asserte la non-dérive des
    ...    paramètres : un passage de « armé sans filtre » à « filtrant » est
    ...    un vrai changement de configuration, qui doit se voir et se solder
    ...    en mettant la baseline à jour, exactement comme on re-committe une
    ...    référence. Est asserté enfin la COHÉRENCE interne du verdict, seule
    ...    chose qui trahirait une lecture cassée.
    ${audit}=    Read Audit Filtering
    Should Be True    ${audit}[enabled]
    ...    msg=Le journal d'audit n'est plus armé : aucun incident ne sera reconstituable.
    IF    $audit["filtering"]
        Should Be True    ${audit}[slots_active] > 0
        Log    Audit filtrant : ${audit}[slots_active] slot(s) actif(s) sur ${audit}[slots_declared].
    ELSE
        Should Be Equal As Integers    ${audit}[slots_active]    0
        Log    Journal ARMÉ SANS FILTRE : ${audit}[slots_declared] slots déclarés, aucun actif.
        ...    level=WARN
    END
    Should Be Equal    ${audit}[verdict]    ${EXPECTED_AUDIT_VERDICT}
    ...    msg=Le régime du journal d'audit a changé sur cette cible.

Les destinations qui conservent un logon sont inventoriées
    [Documentation]    Une destination RFC qui stocke un logon vers un autre
    ...    système est un chemin d'élévation : qui atteint ce système atteint
    ...    l'autre, sans présenter d'identifiant. L'information n'est pas dans
    ...    une colonne, elle est enfouie dans un agrégat de marqueurs, donc une
    ...    simple liste de destinations ne la donne pas.
    ...
    ...    La campagne INVENTORIE et ne lit JAMAIS un secret : elle constate
    ...    qu'il en existe un. Le nombre est asserté contre la valeur mesurée,
    ...    parce qu'une destination à logon qui APPARAÎT est exactement
    ...    l'événement que ce contrôle existe pour voir.
    ${resume}=    Read Destinations Carrying A Logon
    Log    Destinations porteuses : ${resume}
    Length Should Be    ${resume}[with_stored_logon]    ${EXPECTED_STORED_LOGONS}
    ...    msg=Le nombre de destinations à logon stocké a changé : ${resume}[with_stored_logon]
    Should Be True    len(${resume}[with_stored_password]) <= len(${resume}[with_stored_logon])
    ...    msg=Une destination conserve un mot de passe sans porter de logon : lecture douteuse.

Le niveau de correctifs des composants n'a pas reculé
    [Documentation]    Un système qui recule de niveau de correctifs perd des
    ...    corrections de sécurité, et c'est un incident indépendant de toute
    ...    politique d'entreprise. Le contrôle porte sur le composant de base,
    ...    celui dont dépendent tous les autres.
    ...
    ...    L'inventaire des composants est aussi la seule ancre d'identité
    ...    RICHE de la cible : ni l'identifiant système ni le nom d'hôte ne
    ...    distinguent les deux conteneurs du banc.
    ${composants}=    Read Installed Components
    Should Not Be Empty    ${composants}
    ${base}=    Evaluate    [c for c in $composants if c["name"] == "SAP_BASIS"]
    Should Not Be Empty    ${base}    msg=Composant de base absent de l'inventaire : lecture douteuse.
    Should Be Equal    ${base}[0][release]    ${EXPECTED_RELEASE}
    ...    msg=La release du composant de base contredit celle du système.
    Should Be True    int("${base}[0][support_level]") >= int("${EXPECTED_BASIS_PATCH}")
    ...    msg=Le niveau de correctifs du composant de base a RECULÉ (${base}[0][support_level] < ${EXPECTED_BASIS_PATCH}).
    Log    ${composants.__len__()} composants installés, base ${base}[0][release] niveau ${base}[0][support_level].

Le mandant de référence est protégé contre l'écrasement
    [Documentation]    Contrôle BLOQUANT. Le mandant livré par SAP sert de
    ...    référence à tous les autres : s'il est copiable ou modifiable, la
    ...    base de comparaison du système disparaît. Le mandant de travail, lui,
    ...    est seulement rapporté : sa catégorie diverge entre les deux cibles
    ...    du poste, et cette divergence est une propriété de l'image, pas un
    ...    défaut.
    ${mandants}=    Read Client Protection
    Should Not Be Empty    ${mandants}
    ${reference}=    Evaluate
    ...    [c for c in $mandants if c["MANDT"] == "${REFERENCE_CLIENT}"]
    Should Not Be Empty    ${reference}
    ...    msg=Le mandant de référence ${REFERENCE_CLIENT} est absent de la table des mandants.
    Should Be Equal    ${reference}[0][CCCOPYLOCK]    X
    ...    msg=Le mandant de référence n'est PAS protégé contre la copie et l'écrasement.
    Log    Mandants relevés : ${mandants}

Les comptes standards livrés par SAP sont inventoriés avec leur état
    [Documentation]    L'inventaire que tout audit réclame en premier. Un compte
    ...    ABSENT du mandant est rendu comme tel plutôt qu'omis : « ce compte
    ...    n'existe pas ici » est une réponse au contrôle, alors qu'une omission
    ...    ressemble à une absence de mesure.
    ...
    ...    La suite RAPPORTE l'état sans le juger : sur ce bac à sable les
    ...    comptes livrés sont déverrouillés, ce qui serait un écart majeur en
    ...    production et n'a pas de sens ici. C'est la sentinelle qui rendra
    ...    visible un changement.
    ${comptes}=    Read Standard Accounts
    Should Not Be Empty    ${comptes}
    ${presents}=    Evaluate    [c["user"] for c in $comptes if c["present"]]
    Should Contain    ${presents}    SAP*
    Should Contain    ${presents}    DDIC
    FOR    ${compte}    IN    @{comptes}
        IF    $compte["present"]
            Log    ${compte}[user] : verrouillé=${compte}[locked] causes=${compte}[reasons] groupe=${compte}[user_group]
        ELSE
            Log    ${compte}[user] : absent du mandant ${RFC_CLIENT}
        END
    END

Les porteurs de profil critique et les destinations RFC sont inventoriés
    [Documentation]    Les deux chemins d'élévation classiques d'un paysage SAP :
    ...    un profil tout-puissant attribué trop largement, et une destination
    ...    RFC qui stocke un logon vers un autre système. La campagne les
    ...    INVENTORIE et ne lit jamais un secret de destination.
    ${porteurs}=    Read Critical Profile Assignments
    Should Not Be Empty    ${porteurs}
    ...    msg=Aucun porteur de profil critique : lecture douteuse plutôt que système exemplaire.
    Log    Porteurs de profil critique : ${porteurs}
    ${destinations}=    Read Rfc Destinations
    ${abap}=    Count Destinations Of Type    ${destinations}    3
    Log    ${destinations.__len__()} destinations déclarées, dont ${abap} de type ABAP.
    Should Be True    ${abap} >= 0

La configuration de sécurité n'a pas dérivé depuis la référence
    [Documentation]    La sentinelle, et ce qui rend la campagne rejouable. Elle
    ...    ne demande pas si le système est durci mais si sa configuration a
    ...    BOUGÉ depuis la référence committée de CETTE cible, qui a une réponse
    ...    binaire. Chaque cible a sa référence : les mélanger ferait passer la
    ...    différence de durcissement entre deux releases pour une dérive.
    ${mesures}=    Current Security Posture
    ${identite}=    Current System Identity
    ${verdict}=    Security Posture Should Match Reference    ${POSTURE_REFERENCE}
    ...    ${mesures}    identite=${identite}
    IF    $verdict["first_visit"]
        Log    Référence créée : ${verdict}[reference] (à relire et à committer).    level=WARN
    ELSE
        Log    Aucune dérive : ${verdict}[unchanged] paramètres inchangés.
    END
