*** Settings ***
Documentation       **Configuration de sécurité de la cible A4H** (ABAP Platform
...                 Spec: specs/secu-configuration-a4h.md (sha256:869164c6b61f, 2026-08-30)
...                 1909, release 754), lue par le canal RFC, en LECTURE SEULE.
...
...                 Elle a une jumelle, `secu_configuration_abap2023.robot`, et
...                 les deux ne sont pas une suite dupliquée : elles partagent
...                 le vocabulaire (`resources/security_keywords.resource`) et
...                 divergent par leur BASELINE, parce que les deux releases ne
...                 sont pas durcies pareil. Mesuré le 2026-08-29 : la politique
...                 de mot de passe passe de 6 à 10 caractères, les quatre
...                 exigences de composition de 0 à 1, et la déconnexion
...                 automatique de désactivée à une heure. Une suite unique
...                 paramétrée aurait dû choisir entre asserter la posture la
...                 plus faible (aveugle sur la meilleure cible) ou la plus
...                 forte (rouge à vie sur l'autre).
...
...                 **Ce que la suite juge, et ce qu'elle se contente de
...                 rapporter.** Elle n'ASSERTE que les contrôles dont l'écart
...                 serait un incident quelle que soit la politique de
...                 l'entreprise : journal d'audit actif, passerelle sous liste
...                 de contrôle, contrôle d'autorisation RFC armé, compte SAP*
...                 codé en dur neutralisé, mandant de référence protégé contre
...                 l'écrasement. Tout le reste (longueur de mot de passe,
...                 chiffrement du transport, expiration) est MESURÉ, rapporté
...                 et surveillé par la sentinelle, jamais transformé en échec :
...                 un bac à sable de démonstration n'a pas à respecter la
...                 politique d'un système de production, et une suite rouge en
...                 permanence finit désactivée.
...
...                 **La sentinelle est le cœur de la rejouabilité.** Le dernier
...                 scénario compare le relevé complet à une référence committée
...                 sous `tests/robot/security_baselines/`. Premier passage : la
...                 référence est écrite avec un WARNING, à relire et à
...                 committer. Ensuite, tout changement de configuration non
...                 annoncé est nommé paramètre par paramètre.
...
...                 **Prérequis.** Un interpréteur 3.10 à 3.12 portant
...                 ``pyrfc`` et un runtime NW RFC (souvent déjà déposé par SAP
...                 GUI for Windows 8.00). Le canal est optionnel : sans lui la
...                 suite se SAUTE au lieu de rougir. Aucun relais réseau n'est
...                 nécessaire pour cette cible, contrairement à sa jumelle.
...
...                 Exemple :
...                 | robot --pythonpath src --include secu
...                 | ...   -v "RFC_PASSWORD: Secret:***"
...                 | ...   --outputdir results/secu-a4h
...                 | ...   tests/robot/api/secu_configuration_a4h.robot

Resource            ../../../resources/security_keywords.resource

Suite Setup         Run Keywords    Skip Unless Rfc Channel Is Available
...                     AND    Open Security Audit Channel
Suite Teardown      Close Security Audit Channel

Test Tags           secu    rfc


*** Variables ***
# --- La cible, et rien qu'elle.
${RFC_ASHOST}                   localhost
${RFC_SYSNR}                    00
${RFC_CLIENT}                   001
${RFC_USER}                     DEVELOPER
${RFC_PASSWORD}                 ${EMPTY}    # OBLIGATOIRE : -v "RFC_PASSWORD: Secret:<motdepasse>"
${RFC_LANG}                     EN

# Ce qui PROUVE la cible. Ni l'identifiant système ni le nom d'hôte applicatif
# ne le font : les deux conteneurs du poste annoncent A4H et vhcala4h, et
# l'adresse IP change d'un redémarrage à l'autre. Les ancres sont la release et
# le kernel, et ${PEER_RELEASE} est la contre-épreuve.
${EXPECTED_RELEASE}             754
${EXPECTED_KERNEL}              777
${PEER_RELEASE}                 758

# Le mandant de référence livré par SAP, celui dont l'écrasement se protège.
${REFERENCE_CLIENT}             000

# La référence de dérive de CETTE cible.
${POSTURE_REFERENCE}            posture-a4h-754

# Un paramètre qui n'existe nulle part : la contre-épreuve du piège central.
${UNKNOWN_PARAMETER}            login/parametre_qui_nexiste_pas

# Baseline des inventaires, MESURÉE sur cette cible le 2026-08-29.
${EXPECTED_AUDIT_VERDICT}       armed_without_filter
${EXPECTED_STORED_LOGONS}       ${3}
${EXPECTED_BASIS_PATCH}         0007


*** Test Cases ***
La cible est bien celle que la suite croit auditer
    [Documentation]    Sans ce scénario, toute la campagne peut être verte
    ...    contre le mauvais système. Le poste héberge deux conteneurs ABAP qui
    ...    annoncent le MÊME identifiant système et le MÊME nom d'hôte
    ...    applicatif : la release et le kernel sont les seules ancres, et la
    ...    contre-épreuve vérifie qu'on ne mesure pas la release voisine.
    ${info}=    Current System Identity
    Should Be Equal    ${info}[RFCSAPRL]    ${EXPECTED_RELEASE}
    ...    msg=Release inattendue : la suite audite un autre système que celui qu'elle décrit.
    Should Be Equal    ${info}[RFCKERNRL]    ${EXPECTED_KERNEL}
    ...    msg=Kernel inattendu sur une release pourtant conforme : cible douteuse.
    Should Not Be Equal    ${info}[RFCSAPRL]    ${PEER_RELEASE}
    ...    msg=La suite mesure la release de l'AUTRE conteneur du poste.

Un paramètre inconnu est rendu non mesurable, jamais vide
    [Documentation]    Le piège central de tout audit de configuration SAP, et
    ...    la raison d'être de la couche de lecture. Le module ABAP ne refuse
    ...    PAS un paramètre qu'il ne connaît pas : il rend un code de retour non
    ...    nul et une chaîne VIDE. Un contrôle qui lit la valeur sans regarder
    ...    le code est donc vert sur un nom mal orthographié, et conclut à une
    ...    absence de durcissement qu'il n'a jamais mesurée.
    ...
    ...    Le scénario joue les deux sens : le paramètre inventé sort en
    ...    ``unknown`` avec une valeur nulle, et un paramètre réel du même
    ...    préfixe sort bien en ``defined``.
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
    ...    paramètre absent de cette release ». Les deux se ressemblent dans un
    ...    rapport et ne se corrigent pas au même endroit. Elle protège aussi
    ...    la sentinelle : un paramètre qui deviendrait inconnu après une mise à
    ...    jour serait sinon lu comme une valeur vide, donc comme une dérive.
    ${mesures}=    Current Security Posture
    ${inconnus}=    Evaluate    [m["name"] for m in $mesures if m["status"] != "defined"]
    Should Be Empty    ${inconnus}
    ...    msg=Paramètres non reconnus par la release ${EXPECTED_RELEASE} : ${inconnus}

Le journal d'audit de sécurité est actif
    [Documentation]    Contrôle BLOQUANT : sans journal d'audit, aucun incident
    ...    de sécurité n'est reconstituable après coup, et l'écart est un
    ...    incident quelle que soit la politique de l'entreprise. Mesuré actif
    ...    sur les deux releases du poste, donc un échec ici signale un vrai
    ...    changement.
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
    ...    chemin d'entrée le plus classique sur un système ABAP, et il ne
    ...    dépend d'aucune politique interne.
    ${mesures}=    Read Security Parameters    ${PARAMS_GATEWAY}
    ${c1}=    Security Control    gateway.acl    gw/acl_mode    enabled    1
    ...    severity=high    rationale=Sans liste de contrôle, un serveur RFC arbitraire s'enregistre.
    ${c2}=    Security Control    gateway.conn_info    gw/reg_no_conn_info    enabled    1
    ...    severity=medium    rationale=Durcit le traitement des informations de connexion.
    @{controles}=    Create List    ${c1}    ${c2}
    ${verdicts}=    Judge Security Posture    ${controles}    ${mesures}
    ${resume}=    Summarize Verdicts    ${verdicts}
    Should Be Equal As Integers    ${resume}[deviation]    0
    ...    msg=Passerelle non conforme : ${resume}[deviating_keys]
    ${identite}=    Current System Identity
    Log Security Posture Report    ${identite}    ${mesures}    ${controles}

Le compte SAP* codé en dur est neutralisé et l'autorisation RFC est armée
    [Documentation]    Contrôle BLOQUANT sur deux protections que rien ne
    ...    justifie de désactiver. Le compte SAP* codé en dur du noyau ignore
    ...    la table des utilisateurs et porte tous les droits ; le contrôle
    ...    d'autorisation RFC, désarmé, laisse appeler n'importe quel module à
    ...    distance.
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

La politique de mot de passe est mesurée et rapportée
    [Documentation]    Scénario de RAPPORT, pas d'assertion de conformité : la
    ...    politique attendue dépend de l'entreprise, et ce système est un bac
    ...    à sable. La baseline déclarée ici est celle MESURÉE sur la cible le
    ...    2026-08-29, donc le scénario documente la posture réelle et laisse la
    ...    sentinelle détecter tout changement.
    ...
    ...    L'écart avec la jumelle 2023 est délibérément visible : 6 caractères
    ...    sans exigence de composition ici, 10 avec quatre exigences là-bas.
    ${mesures}=    Read Security Parameters    ${PARAMS_PASSWORD_POLICY}
    ${c1}=    Security Control    password.length    login/min_password_lng
    ...    at_least    6    severity=high
    ...    rationale=Longueur minimale mesurée sur cette release.
    ${c2}=    Security Control    password.expiration    login/password_expiration_time
    ...    at_least    0    severity=medium
    ...    rationale=Zéro signifie aucune expiration : posture connue du bac à sable.
    @{controles}=    Create List    ${c1}    ${c2}
    ${verdicts}=    Judge Security Posture    ${controles}    ${mesures}
    ${resume}=    Summarize Verdicts    ${verdicts}
    Should Be Equal As Integers    ${resume}[not_measurable]    0
    ...    msg=Politique de mot de passe non mesurable : ${resume}[not_measurable_keys]
    ${identite}=    Current System Identity
    Log Security Posture Report    ${identite}    ${mesures}    ${controles}

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
    ...    base de comparaison du système disparaît. Le scénario lit AUSSI le
    ...    mandant de travail et rapporte sa catégorie, qui diverge entre les
    ...    deux cibles du poste.
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
    [Documentation]    L'inventaire que tout audit réclame en premier, et un cas
    ...    d'école du repli sûr : un compte ABSENT du mandant est rendu comme
    ...    tel plutôt qu'omis, parce que « ce compte n'existe pas ici » est une
    ...    réponse au contrôle, alors qu'une omission ressemble à une absence de
    ...    mesure.
    ...
    ...    La suite RAPPORTE l'état sans le juger : sur ce bac à sable les deux
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
    ...    ne demande pas si le système est durci (jugement discutable, faux sur
    ...    un bac à sable) mais si sa configuration a BOUGÉ depuis la référence
    ...    committée, qui a une réponse binaire.
    ...
    ...    Premier passage : la référence est écrite avec un WARNING, à relire
    ...    et à committer. Ensuite, chaque écart est nommé. Une dérive voulue se
    ...    solde en re-committant la référence ; une dérive non voulue est
    ...    exactement l'incident que la campagne existe pour attraper.
    ${mesures}=    Current Security Posture
    ${identite}=    Current System Identity
    ${verdict}=    Security Posture Should Match Reference    ${POSTURE_REFERENCE}
    ...    ${mesures}    identite=${identite}
    IF    $verdict["first_visit"]
        Log    Référence créée : ${verdict}[reference] (à relire et à committer).    level=WARN
    ELSE
        Log    Aucune dérive : ${verdict}[unchanged] paramètres inchangés.
    END
