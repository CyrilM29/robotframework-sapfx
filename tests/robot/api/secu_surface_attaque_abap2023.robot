*** Settings ***
Documentation       **Surface d'attaque de la cible ABAP Platform 2023**
...                 Spec: specs/secu-surface-attaque-abap2023.md (sha256:7cd814dc54a6, 2026-09-14)
...                 (release 758), lue par le canal RFC, en LECTURE SEULE.
...
...                 Complément de `secu_configuration_abap2023.robot`, et non
...                 sa répétition : la campagne de configuration lit ce que le
...                 système DÉCLARE (paramètres de profil, comptes livrés,
...                 destinations déclarées), celle-ci lit ce qui est
...                 réellement ATTEIGNABLE. Les deux ne coïncident pas, et les
...                 quatre écarts mesurés le 2026-09-14 sont sa raison d'être :
...
...                 - **zéro compte verrouillé, deux comptes inutilisables**
...                 (validité échue au 31/12/2024) : la surface d'entrée est
...                 de quatre comptes là où le masque de verrouillage en
...                 annonce six ;
...                 - **3410 services web déclarés, 219 actifs** : compter les
...                 déclarés donne une surface seize fois trop grande ;
...                 - **117 commandes système, 109 acceptant des arguments
...                 additionnels** : l'écart entre « exécuter une sauvegarde »
...                 et « exécuter ce que l'appelant voudra » ;
...                 - **journal d'audit armé, zéro entrée sur quatre ans** : ce
...                 que la campagne voisine DÉDUIT, celle-ci le CONSTATE.
...
...                 **Prérequis d'environnement, et ce n'en est pas un détail.**
...                 La cible est jointe à travers un **relais TCP local**
...                 (``${RFC_ASHOST}`` par défaut). Sans lui, l'adresse répond
...                 quand même (la boucle locale couvre toute sa plage et
...                 l'autre conteneur écoute partout), donc la suite parlerait
...                 à la release 754 en croyant auditer la 758, avec le même
...                 identifiant système et le même nom d'hôte. Le premier
...                 scénario existe pour attraper exactement cela.
...
...                 Autres prérequis : un interpréteur 3.10 à 3.12 portant
...                 ``pyrfc`` et un runtime NW RFC. Le canal est optionnel :
...                 sans lui la suite se SAUTE au lieu de rougir.
...
...                 Exemple :
...                 | robot --pythonpath src --include secu
...                 | ...   -v "RFC_PASSWORD: Secret:***"
...                 | ...   --outputdir results/surface-2023
...                 | ...   tests/robot/api/secu_surface_attaque_abap2023.robot

Resource            ../../../resources/security_keywords.resource
Library             sapfx_common.artifacts

Suite Setup         Run Keywords    Skip Unless Rfc Channel Is Available
...                     AND    Open Security Audit Channel
Suite Teardown      Close Security Audit Channel

Test Tags           secu    rfc    surface


*** Variables ***
# --- La cible, et rien qu'elle. L'adresse est celle du relais, pas celle du
# conteneur : viser directement le port publié obligerait à annoncer un numéro
# d'instance que l'instance interne ne porte pas.
${RFC_ASHOST}                       127.0.0.2
${RFC_SYSNR}                        00
${RFC_CLIENT}                       001
${RFC_USER}                         DEVELOPER
${RFC_PASSWORD}                     ${EMPTY}    # OBLIGATOIRE : -v "RFC_PASSWORD: Secret:<motdepasse>"
${RFC_LANG}                         EN

# Ce qui PROUVE la cible. Ni l'identifiant système ni le nom d'hôte ne le font
# (les deux conteneurs du poste annoncent A4H et vhcala4h) et l'adresse IP est
# volatile. ${PEER_RELEASE} est la contre-épreuve, et c'est ici la garde du
# relais : sans relais, c'est cette release-là que la suite mesurerait.
${EXPECTED_RELEASE}                 758
${EXPECTED_KERNEL}                  793
${PEER_RELEASE}                     754

# --- Les ATTENTES, propres à CETTE cible : mesurées le 2026-09-14. Elles
# vivent dans la suite et non dans la resource, ce qui permet à une autre
# release de partager le vocabulaire sans partager la baseline.
@{EXPECTED_USABLE_ACCOUNTS}         BWDEVELOPER    DDIC    DEVELOPER    SAP*
@{EXPECTED_UNUSABLE_ACCOUNTS}       DEVELOPER_5    SDMI_DLRYYAU
${EXPECTED_ACCOUNT_TOTAL}           ${6}
# La forme moderne d'empreinte de mot de passe. Une version plus ancienne
# (B, D, F) signalerait des empreintes faibles conservées.
${MODERN_HASH_VERSION}              H

${EXPECTED_ACTIVE_SERVICES}         ${219}

# NB : le total des commandes système (117 à la mesure) n'est volontairement
# PAS gravé. Il bouge avec un lot de correctifs SAP sans porter la moindre
# information de sécurité, et une suite qui rougit sur une mise à jour normale
# finit désactivée. Ce qui est asserté est l'absence de commande AJOUTÉE.

${EXPECTED_AUDIT_VERDICT}           armed_without_filter_and_silent
${AUDIT_WINDOW_DAYS}                ${365}

${EXPECTED_TRUSTED_SYSTEMS}         ${0}
${EXPECTED_TRUSTING_SYSTEMS}        ${0}
${EXPECTED_CALLBACK_ENTRIES}        ${2}

${EXPECTED_ROLE_ASSIGNMENTS}        ${9}

${SURFACE_ARTIFACT}                 ${OUTPUT DIR}/surface_attaque_abap2023.json


*** Test Cases ***
La cible est bien la release auditee et pas sa voisine
    [Documentation]    Sans le relais TCP, l'adresse visée répond quand même et
    ...    c'est l'autre conteneur qui parle. Les onze scénarios suivants
    ...    seraient alors verts et décriraient la mauvaise machine. C'est la
    ...    cause la plus probable d'un échec ici.
    # `Read Target Identity For Artifact` assemble les DEUX sources
    # indépendantes du canal (attributs de connexion et fiche publiée par le
    # système) et laisse dehors l'adresse IP, mesurée volatile : c'est ce qui
    # rend l'artefact du scénario 12 déterministe d'un passage à l'autre.
    ${identite}=    Read Target Identity For Artifact
    Should Be Equal    ${identite}[release]    ${EXPECTED_RELEASE}
    ...    msg=Release inattendue. Cause la plus probable : le relais TCP local n'est pas levé, et c'est l'autre conteneur du poste qui a répondu.
    Should Be Equal    ${identite}[kernel]    ${EXPECTED_KERNEL}
    ...    msg=Kernel inattendu sur une release pourtant conforme : cible douteuse.
    Should Not Be Equal    ${identite}[release]    ${PEER_RELEASE}
    ...    msg=La suite mesure la release de l'AUTRE conteneur du poste : relais absent ou mal orienté.
    Set Suite Variable    ${TARGET_IDENTITY}    ${identite}

Un compte non verrouille n est pas forcement utilisable
    [Documentation]    L'écart fondateur de cette campagne. Le masque de
    ...    verrouillage dit « aucun compte verrouillé », ce qui est exact, et
    ...    deux comptes portent une validité échue depuis vingt mois. La
    ...    surface d'entrée réelle est de quatre comptes, pas six.
    ${surface}=    Read Account Surface
    Set Suite Variable    ${ACCOUNT_SURFACE}    ${surface}
    Should Be Equal As Integers    ${surface}[total]    ${EXPECTED_ACCOUNT_TOTAL}
    Lists Should Be Equal    ${surface}[usable]    ${EXPECTED_USABLE_ACCOUNTS}
    ...    msg=La liste des comptes UTILISABLES a changé : un compte de plus ou de moins peut entrer dans ce mandant.
    Lists Should Be Equal    ${surface}[unusable]    ${EXPECTED_UNUSABLE_ACCOUNTS}
    ...    msg=La liste des comptes inutilisables a changé.
    # La cause est assertée, pas seulement le fait : « inutilisable » doit
    # rester « expiré » et non devenir « verrouillé », qui serait un autre
    # événement et un autre remède.
    # Lu avec un défaut : le jour où plus aucun compte n'est expiré, la clé
    # disparaît, et un accès direct lèverait une erreur technique au moment
    # précis où la campagne aurait quelque chose à dire.
    ${expires}=    Get From Dictionary    ${surface}[by_status]    expired    default=@{EMPTY}
    Lists Should Be Equal    ${expires}    ${EXPECTED_UNUSABLE_ACCOUNTS}
    ...    msg=La population des comptes EXPIRÉS a changé.
    Dictionary Should Not Contain Key    ${surface}[by_status]    locked
    ...    msg=Un compte est désormais VERROUILLÉ : constat distinct de l'expiration, à acquitter.
    Log    Comptes utilisables : ${surface}[usable]
    Log    Répartition par statut : ${surface}[by_status]

Les empreintes de mots de passe sont toutes au format moderne
    [Documentation]    Une empreinte ancienne conservée est cassable hors
    ...    ligne, et cela ne dépend d'aucune politique d'entreprise. Bloquant
    ...    des deux côtés du banc.
    ${versions}=    Set Variable    ${ACCOUNT_SURFACE}[hash_versions]
    Dictionary Should Contain Key    ${versions}    ${MODERN_HASH_VERSION}
    Should Be Equal As Integers    ${versions}[${MODERN_HASH_VERSION}]
    ...    ${EXPECTED_ACCOUNT_TOTAL}
    ...    msg=Tous les comptes ne portent pas l'empreinte moderne : des empreintes faibles sont conservées.
    Length Should Be    ${versions}    ${1}
    ...    msg=Plusieurs versions d'empreinte cohabitent : ${versions}
    Log    Versions d'empreinte : ${versions}

La liste des mots de passe interdits est mesuree et non supposee
    [Documentation]    RAPPORTÉ, pas asserté : asserter zéro graverait une
    ...    faiblesse comme une cible, et exiger un minimum rendrait la suite
    ...    rouge à vie sur ce banc. Ce qui compte est que la mesure EXISTE. Le
    ...    piège fermé ici : cette table n'a pas de colonne d'utilisateur, et
    ...    projeter la colonne plausible ferait conclure « liste vide » sans
    ...    avoir rien lu, avec ici la même réponse que la vérité.
    ${compte}=    Count Forbidden Passwords
    Should Be True    isinstance($compte, int)
    ...    msg=La lecture de la liste n'a pas abouti : un décompte est attendu.
    Set Suite Variable    ${FORBIDDEN_PASSWORDS}    ${compte}
    Log    Mots de passe interdits déclarés : ${compte}

La surface web servie n est pas la surface declaree
    [Documentation]    Le drapeau d'activation et le nom lisible vivent dans
    ...    DEUX tables jointes par l'identifiant de noeud. La seconde
    ...    assertion vérifie la jointure elle-même : si elle échouait, le
    ...    keyword rendrait autant d'actifs que de déclarés, ou zéro, et le
    ...    nombre seul ne le dirait pas.
    ${exposition}=    Read Web Exposure
    Set Suite Variable    ${WEB_EXPOSURE}    ${exposition}
    Should Be Equal As Integers    ${exposition}[active]    ${EXPECTED_ACTIVE_SERVICES}
    ...    msg=Le nombre de services web ACTIFS a changé : un service a été activé ou désactivé.
    Should Be True    ${exposition}[active] > 0
    ...    msg=Zéro service actif sur un système qui sert un launchpad : lecture douteuse.
    # La JOINTURE elle-même, et c'est le seul contrôle qui la mesure. Comparer
    # « actifs » et « déclarés » ne dirait rien : les deux viennent de la table
    # d'activation. Une jointure cassée rendrait des noms repliés sur
    # l'identifiant de noeud, aucun compte de service et aucun service
    # sensible, soit la signature exacte d'un système sain.
    Should Be Equal As Integers    ${exposition}[unmatched]    ${0}
    ...    msg=${exposition}[unmatched] service(s) actif(s) sans fiche descriptive : la jointure des deux tables est partielle, et les contrôles qui en dépendent (compte de service, chiffrement) sont alors verts pour de mauvaises raisons.
    Should Be Equal As Integers    ${exposition}[matched]    ${exposition}[active]
    Should Not Be Empty    ${exposition}[sensitive_active]
    ...    msg=Aucun service sensible reconnu alors que la cible en sert : la jointure n'a pas ramené les noms lisibles.
    Log    Déclarés ${exposition}[declared] / actifs ${exposition}[active] (ratio ${exposition}[exposure_ratio])
    Log    Services sensibles actifs : ${exposition}[sensitive_active]
    Log    Hôtes virtuels : ${exposition}[virtual_hosts]

Aucun service actif ne s execute sans authentifier son appelant
    [Documentation]    Un service qui porte un compte de service répond sans
    ...    demander d'identifiant : c'est un chemin d'entrée indépendant de
    ...    toute politique, donc bloquant. Le chiffrement, lui, est seulement
    ...    RAPPORTÉ : l'exiger sur un banc en HTTP rendrait la suite rouge à
    ...    vie, ce qui la ferait désactiver.
    # Le contrôle ne vaut que si la jointure a eu lieu : sans elle, ce champ
    # serait vide par construction. Le scénario précédent l'a établi, on le
    # rappelle ici pour que ce test ne puisse pas passer seul sur du vide.
    Should Be Equal As Integers    ${WEB_EXPOSURE}[unmatched]    ${0}
    ...    msg=La jointure est partielle : ce contrôle serait vert sans avoir rien mesuré.
    Should Be Empty    ${WEB_EXPOSURE}[with_stored_user]
    ...    msg=Un service web actif porte un compte de service : il s'exécute sans authentifier son appelant.
    Log    Services actifs sans chiffrement : ${WEB_EXPOSURE}[active_without_ssl] sur ${WEB_EXPOSURE}[active] (banc en HTTP, rapporté et non jugé)

Aucune commande du systeme d exploitation n a ete ajoutee
    [Documentation]    Les 117 commandes livrées sont un standard, les juger
    ...    n'aurait pas de sens. Une commande ajoutée sur le système, elle, ne
    ...    vient d'aucun standard : son apparition est exactement ce que ce
    ...    contrôle existe pour voir.
    ${commandes}=    Read Os Command Surface
    Set Suite Variable    ${OS_COMMANDS}    ${commandes}
    Should Be Empty    ${commandes}[customer_defined]
    ...    msg=Une commande système a été ajoutée dans l'espace de noms client : elle ne vient d'aucun standard.
    # Garde de vraisemblance, PAS de non-dérive : le total des commandes
    # livrées par SAP bouge avec un lot de correctifs, sans aucune portée de
    # sécurité. Le graver rendrait la suite rouge sur une mise à jour normale,
    # ce qui est le mécanisme exact par lequel une suite finit désactivée. On
    # vérifie donc que l'inventaire a bien été lu, pas qu'il n'a pas bougé.
    Should Be True    ${commandes}[total] > 0
    ...    msg=Inventaire de commandes système VIDE : lecture douteuse bien plus probablement qu'un système sans aucune commande.
    Log    ${commandes}[total] commandes, dont ${commandes}[accepting_additional] acceptant des arguments additionnels
    Log    Par système d'exploitation : ${commandes}[by_os]

Le journal d audit est arme et il n enregistre rien
    [Documentation]    Le complément indispensable du scénario d'audit de la
    ...    campagne de configuration : celui-là établit « armé sans filtre » et
    ...    en DÉDUIT que rien n'est enregistré, celui-ci le CONSTATE en lisant
    ...    le journal.
    ...
    ...    La deuxième assertion est la plus importante : une lecture qui
    ...    échoue ne doit JAMAIS valoir zéro, sans quoi « je n'ai pas su lire »
    ...    passerait pour « le journal est vide », qui est précisément la
    ...    conclusion recherchée. Le module de lecture rend d'ailleurs zéro
    ...    entrée sans erreur quand on l'appelle mal.
    ${couverture}=    Read Audit Coverage    fenetre_jours=${AUDIT_WINDOW_DAYS}
    Set Suite Variable    ${AUDIT_COVERAGE}    ${couverture}
    Should Not Be Equal    ${couverture}[verdict]    not_measured
    ...    msg=La lecture du journal n'a PAS abouti : aucun verdict de couverture n'est possible, et surtout ce n'est pas un journal vide.
    Should Not Be Equal    ${couverture}[entries]    ${None}
    ...    msg=Aucun décompte d'entrées : la lecture n'a pas eu lieu.
    Should Be Equal    ${couverture}[verdict]    ${EXPECTED_AUDIT_VERDICT}
    ...    msg=Le régime d'audit a changé. Si un filtrage a été configuré, c'est une bonne nouvelle à acquitter en mettant à jour l'attente.
    Should Be True    ${couverture}[consistent]
    ...    msg=Le verdict n'est pas cohérent avec ses propres décomptes : lecture douteuse.
    Log    ${couverture}[note]
    Log    Emplacements déclarés ${couverture}[configuration][slots_declared], actifs ${couverture}[configuration][slots_active]
    Log    Entrées ${couverture}[entries] sur ${couverture}[window_days] jours, fichiers de journal ${couverture}[files]

Aucune relation de confiance RFC n est configuree
    [Documentation]    Asserter un VIDE a un sens ici : une confiance qui
    ...    apparaît est un chemin d'élévation vers un autre système, et
    ...    l'apparition est l'événement à voir. Sans cet inventaire, on ne
    ...    distingue pas « aucune relation » de « personne n'a regardé ».
    ...
    ...    Le piège fermé : la table des confiances entrantes n'a pas la
    ...    colonne d'identifiant système qu'on lui suppose, et la demander fait
    ...    échouer la lecture par un code qui accuse la table d'être vide. La
    ...    conclusion se trouverait être exacte, ce qui rend l'erreur invisible.
    ${confiance}=    Read Trust Surface
    Set Suite Variable    ${TRUST_SURFACE}    ${confiance}
    Should Be Equal As Integers    ${confiance}[trusted_systems]    ${EXPECTED_TRUSTED_SYSTEMS}
    ...    msg=Une relation de confiance ENTRANTE est apparue : un autre système peut désormais entrer ici sans présenter d'identifiant.
    Should Be Equal As Integers    ${confiance}[trusting_systems]    ${EXPECTED_TRUSTING_SYSTEMS}
    ...    msg=Une relation de confiance SORTANTE est apparue.
    Should Not Be True    ${confiance}[any_trust_configured]
    Should Be Equal As Integers    ${confiance}[callback_allowlist_entries]
    ...    ${EXPECTED_CALLBACK_ENTRIES}
    ...    msg=La liste blanche des rappels RFC a changé de taille.
    Log    Rappels autorisés : ${confiance}[callback_destinations]

L empreinte des objets d autorisation critiques est mesuree
    [Documentation]    Garde de VRAISEMBLANCE, pas de conformité : zéro ligne
    ...    pour l'appel distant sur un système ABAP signale une lecture
    ...    douteuse bien plus probablement qu'un système exemplaire. Les
    ...    valeurs elles-mêmes ne sont pas gravées : elles bougent avec le
    ...    moindre rôle livré par un correctif.
    ${empreinte}=    Read Critical Authorization Footprint
    Set Suite Variable    ${AUTH_FOOTPRINT}    ${empreinte}
    FOR    ${objet}    IN    @{CRITICAL_AUTH_OBJECTS}
        Dictionary Should Contain Key    ${empreinte}    ${objet}
    END
    # Les deux objets témoins sont NOMMÉS dans la resource (convention 1) :
    # une suite ne porte pas d'identifiant d'objet SAP.
    Should Be True    ${empreinte}[${AUTH_OBJECT_REMOTE_CALL}] > 0
    ...    msg=Aucune ligne de rôle ne porte l'objet d'appel distant : lecture douteuse.
    Should Be True    ${empreinte}[${AUTH_OBJECT_TABLE_ACCESS}] > 0
    ...    msg=Aucune ligne de rôle ne porte l'objet d'accès aux tables : lecture douteuse.
    Log    Empreinte des objets critiques : ${empreinte}

Les attributions de roles effectives sont inventoriees
    [Documentation]    Complémentaire du scénario précédent : celui-là mesure
    ...    ce que les rôles DÉFINIS contiennent, celui-ci ce qui est réellement
    ...    ATTRIBUÉ. Des dizaines de milliers de lignes de rôle pour neuf
    ...    attributions : lire l'un pour l'autre surestime d'un facteur qui ne
    ...    veut plus rien dire.
    ${attributions}=    Read Effective Role Assignments
    Set Suite Variable    ${ROLE_ASSIGNMENTS}    ${attributions}
    Should Be True    ${attributions}[total] > 0
    ...    msg=Aucune attribution de rôle : lecture douteuse bien plus probablement qu'un système sans rôle.
    Should Be Equal As Integers    ${attributions}[total]    ${EXPECTED_ROLE_ASSIGNMENTS}
    ...    msg=Le nombre d'attributions de rôles a changé.
    ${sans_echeance}=    Get Length    ${attributions}[without_end_date]
    Log    ${attributions}[total] attributions, dont ${sans_echeance} sans échéance
    Log    Par utilisateur : ${attributions}[by_user]

La surface tient dans un artefact rejouable
    [Documentation]    Ce qui rend la campagne comparable entre deux passages
    ...    et entre deux cibles, sur le patron de l'inventaire DDIC et du
    ...    registre de capacités. L'empreinte est calculée hors horodatage,
    ...    donc deux campagnes aux mêmes mesures en produisent la même, et la
    ...    relecture la RECALCULE (un artefact édité après coup est refusé).
    # La date de LECTURE est sortie du périmètre haché et rattachée à la
    # cible : laissée dans les mesures, elle ferait changer l'empreinte à
    # chaque jour qui passe, donc deux passages identiques à vingt-quatre
    # heures d'écart seraient déclarés divergents. Le défaut ne se voit pas
    # en rejouant la suite le même jour.
    ${comptes}=    Copy Dictionary    ${ACCOUNT_SURFACE}    deepcopy=${True}
    ${date_lecture}=    Pop From Dictionary    ${comptes}    as_of
    ${cible}=    Copy Dictionary    ${TARGET_IDENTITY}    deepcopy=${True}
    Set To Dictionary    ${cible}    read_on=${date_lecture}
    ${surface}=    Create Dictionary
    ...    accounts=${comptes}
    ...    web=${WEB_EXPOSURE}
    ...    os_commands=${OS_COMMANDS}
    ...    audit=${AUDIT_COVERAGE}
    ...    trust=${TRUST_SURFACE}
    ...    authorizations=${AUTH_FOOTPRINT}
    ...    roles=${ROLE_ASSIGNMENTS}
    ...    forbidden_passwords=${FORBIDDEN_PASSWORDS}
    ${charge}=    Create Dictionary    target=${cible}    surface=${surface}
    ${chemin}=    Write Deterministic Artifact    ${SURFACE_ARTIFACT}    ${charge}
    ...    hashed_keys=surface
    ${relu}=    Read Deterministic Artifact    ${chemin}
    Should Be Equal    ${relu}[hash_scope][hashed_keys][0]    surface
    ...    msg=Le périmètre d'empreinte n'est pas celui déclaré : la comparaison entre deux passages ne serait pas probante.
    Dictionary Should Contain Key    ${relu}    sha256
    # Contre-épreuve du déterminisme, jouée dans le run plutôt qu'affirmée :
    # une cible dont la date de lecture change ne doit RIEN changer à
    # l'empreinte, puisque cette date n'est pas une mesure de la surface.
    ${demain}=    Copy Dictionary    ${charge}    deepcopy=${True}
    Set To Dictionary    ${demain}[target]    read_on=19700101
    ${empreinte_demain}=    Artifact Hash    ${demain}    hashed_keys=surface
    Should Be Equal    ${relu}[sha256]    ${empreinte_demain}
    ...    msg=L'empreinte dépend de la date de lecture : deux passages identiques à un jour d'écart seraient déclarés divergents.
    Log    Artefact de surface : ${chemin}
    Log    Empreinte (hors horodatage) : ${relu}[sha256]
