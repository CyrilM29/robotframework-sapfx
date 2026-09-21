*** Settings ***
Documentation       **Sécurité croisée sur TROIS canaux** (ABAP Platform 2023,
...                 Spec: specs/secu-croisement-trois-canaux-abap2023.md (sha256:c14d304b713b, 2026-09-14)
...                 release 758) : l'ÉCRAN (SAP GUI Scripting), le RFC et
...                 l'HTTP/OData, sur la même cible. LECTURE SEULE.
...
...                 Elle ne répète pas les deux campagnes de sécurité voisines,
...                 toutes deux par le canal RFC : elle lève trois limites que
...                 celles-ci consignent explicitement comme non couvertes, et
...                 chacune est une limite de CANAL, pas un oubli.
...
...                 - **L'origine d'un paramètre.** Le RFC rend la valeur
...                 effective sans dire d'où elle vient ; le rapport d'écran
...                 porte les colonnes profil ET défaut noyau. Mesuré sur les
...                 42 paramètres de sécurité audités : 39 viennent du noyau,
...                 3 sont déclarés dans le profil et AUCUN n'y est modifié.
...                 Le durcissement de cette release n'est donc pas un réglage
...                 d'exploitant, c'est le défaut du noyau 793.
...                 - **Le mandant de référence.** La campagne de surface le
...                 consigne hors de portée (connexion RFC refusée) ; un
...                 rapport d'écran lit tous les mandants depuis la session
...                 courante.
...                 - **L'effet réellement produit.** Le paramètre qui pilote
...                 le drapeau HttpOnly des cookies est positionné, et AUCUN
...                 des trois cookies de session ne le porte, ticket
...                 d'authentification compris. Un audit qui s'arrête à la
...                 valeur conclut à une protection qui n'existe pas.
...
...                 **Prérequis, et le premier n'est pas un détail.** Le PORT
...                 distingue les deux conteneurs du poste (3201 ici, 3200 pour
...                 la 1909) et le nom d'hôte est PARTAGÉ : viser le mauvais
...                 port atteint l'autre système sans la moindre erreur, sur
...                 l'écran comme sur le RFC. Le scénario 1 prouve la cible.
...
...                 Une session SAP GUI doit être OUVERTE sur la cible : la
...                 suite s'y rattache. Le mot de passe entre par la ligne de
...                 commande et ne transite par aucun serveur intermédiaire.
...                 Le scripting doit être activé côté serveur (réglage de
...                 SERVEUR : il se provisionne, il ne se force pas d'un test).
...
...                 Exemple :
...                 | robot --pythonpath src --include secu
...                 | ...   -v "RFC_PASSWORD: Secret:***"
...                 | ...   --outputdir results/croisement-3
...                 | ...   tests/robot/cross/secu_croisement_trois_canaux_abap2023.robot

Resource            ../../../resources/security_keywords.resource
Resource            ../../../resources/security_screen_keywords.resource
Library             sapfx_common.artifacts

Suite Setup         Ouvrir Les Trois Canaux
Suite Teardown      Fermer Les Trois Canaux

Test Tags           secu    cross    trois-canaux


*** Variables ***
# --- La cible. L'adresse RFC est celle du relais local, l'adresse HTTP celle
# du port publié : dans les deux cas c'est le PORT qui distingue les deux
# conteneurs du poste, jamais le nom d'hôte, qu'ils partagent.
${RFC_ASHOST}                   127.0.0.2
${RFC_SYSNR}                    00
${RFC_CLIENT}                   001
${RFC_USER}                     DEVELOPER
${RFC_PASSWORD}                 ${EMPTY}    # OBLIGATOIRE : -v "RFC_PASSWORD: Secret:<motdepasse>"
${RFC_LANG}                     EN
${HTTP_BASE_URL}                http://localhost:50100
${HTTP_ALIAS}                   web

${EXPECTED_RELEASE}             758
${EXPECTED_KERNEL}              793
${PEER_RELEASE}                 754

# --- Les ATTENTES, propres à CETTE cible, mesurées le 2026-09-14.
# Les SEULS paramètres du périmètre de sécurité déclarés dans le profil
# d'instance, mesurés le 2026-09-14. Deux sont des chemins de fichiers de
# contrôle d'accès (ils ne PEUVENT pas venir d'un défaut, ils désignent cette
# installation) et le troisième un indicateur de compatibilité. Tous trois y
# portent EXACTEMENT la valeur du défaut, donc aucun ne modifie la posture :
# c'est ce que vérifie ${EXPECTED_PROFILE_CHANGING}.
@{EXPECTED_PROFILE_BACKED}      gw/reg_info    gw/sec_info
...                             login/password_downwards_compatibility
${EXPECTED_PROFILE_CHANGING}    ${0}
${EXPECTED_REFERENCE_CLIENT}    000
${EXPECTED_WORKING_CLIENT}      001
${MIN_PARAMETERS_IN_REPORT}     ${1000}
${LOCK_ICON_MEANS_LOCKED}       ${False}
${EXPECTED_COOKIE_VERDICT}      declared_without_effect
${COOKIE_CONTROL}               icf/set_HTTPonly_flag_on_cookies
# Taille de l'échantillon de la contre-épreuve, et part des témoins
# comparables qui doivent suivre le profil pour que la règle soit établie.
${CONTRE_EPREUVE_TAILLE}        ${25}
${SEUIL_PREPONDERANCE}          ${80}

${CROSS_ARTIFACT}               ${OUTPUT DIR}/croisement_trois_canaux_abap2023.json


*** Test Cases ***
Les trois canaux parlent bien a la meme cible
    [Documentation]    Le nom d'hôte est partagé par les deux conteneurs du
    ...    poste et seul le port les distingue, sur l'écran comme sur le RFC.
    ...    Un croisement entre deux systèmes différents produirait des écarts
    ...    partout, tous faux.
    ...
    ...    Limite assumée et RAPPORTÉE : le canal HTTP ne prouve pas une
    ...    release. Il prouve qu'il répond et que le mandant qu'il sert est
    ...    celui attendu ; son appartenance à la cible tient à son port.
    ${ecran}=    Get System Identity
    Should Be Equal    ${ecran}[anchor][basis_release]    ${EXPECTED_RELEASE}
    ...    msg=L'ÉCRAN ne regarde pas la cible attendue. Cause la plus probable : la session ouverte vise le port 3200 (release ${PEER_RELEASE}) au lieu de 3201.
    ${rfc}=    Read Target Identity For Artifact
    Should Be Equal    ${rfc}[release]    ${EXPECTED_RELEASE}
    ...    msg=Le canal RFC ne regarde pas la cible attendue : relais TCP absent ou mal orienté.
    Should Not Be Equal    ${rfc}[release]    ${PEER_RELEASE}
    Should Be Equal    ${ecran}[anchor][basis_release]    ${rfc}[release]
    ...    msg=L'écran et le RFC ne regardent pas la MÊME release : le croisement ne serait pas probant.
    Set Suite Variable    ${TARGET_IDENTITY}    ${rfc}
    ${cookies}=    Get Api Cookie Security    alias=${HTTP_ALIAS}
    ...    probe_path=${ODATA_CATALOG_SERVICES}/$count?sap-client=${RFC_CLIENT}
    Should Be True    ${cookies}[total] > 0
    ...    msg=Le canal HTTP n'a posé aucun cookie : il n'a pas répondu, et rien de ce qui suit ne serait mesuré.
    Set Suite Variable    ${COOKIE_SECURITY}    ${cookies}
    Log    Écran ${ecran}[anchor][basis_release] / RFC ${rfc}[release] / kernel ${rfc}[kernel]

L ecran de detail d un parametre est hors de portee de l API
    [Documentation]    Fige un MANQUE, pour qu'il ne soit pas retenté à chaque
    ...    reprise du sujet : la transaction d'affichage d'un paramètre rend
    ...    ses détails dans des conteneurs HTML opaques, donc l'origine d'un
    ...    paramètre ne s'y lit pas. C'est le rapport, une grille ordinaire,
    ...    qui la donne.
    ...
    ...    Ce scénario échoue le jour où la release rendrait ces champs
    ...    lisibles : ce serait une bonne nouvelle à consigner.
    ${perception}=    Open Parameter Detail Screen    ${COOKIE_CONTROL}
    Should Contain    ${perception}    ${MARKER_OPAQUE_CONTAINER}
    ...    msg=L'écran de détail ne porte plus de conteneur opaque : la capacité a peut-être changé, à re-mesurer.
    Should Not Contain    ${perception}    ${MARKER_PARAMETER_VALUE_FIELD}
    ...    msg=Un champ de valeur est apparu sur cet écran : le manque est comblé, mettre le plan à jour.
    Log    Les détails du paramètre vivent dans des conteneurs opaques, illisibles par l'API de scripting.

Le rapport de parametres porte les deux colonnes que le RFC n a pas
    [Documentation]    Assertion de MÉTHODE, et elle rend le scénario suivant
    ...    probant : sans elle, un rapport vide ou amputé d'une colonne
    ...    donnerait « zéro paramètre posé dans le profil », c'est-à-dire
    ...    exactement la conclusion recherchée, obtenue sans rien mesurer.
    ${releve}=    Run Profile Parameter Report
    Set Suite Variable    ${SCREEN_PARAMETERS}    ${releve}
    ${n}=    Get Length    ${releve}
    Should Be True    ${n} > ${MIN_PARAMETERS_IN_REPORT}
    ...    msg=Le rapport n'a rendu que ${n} paramètres : lecture partielle, le croisement ne serait pas probant.
    Dictionary Should Contain Key    ${releve}[0]    ${COL_PARAM_PROFILE}
    Dictionary Should Contain Key    ${releve}[0]    ${COL_PARAM_DEFAULT}
    ${substitues}=    Evaluate    len([r for r in $releve if r["${COL_PARAM_PROFILE}"].strip()])
    Should Be True    ${substitues} > 0
    ...    msg=Aucun paramètre substitué par le profil : la colonne de profil n'est pas lue correctement.
    Set Suite Variable    ${SCREEN_SUBSTITUTED}    ${substitues}
    Log    ${n} paramètres rendus, dont ${substitues} substitués par le profil d'instance.

Le durcissement de cette release vient du noyau et non d un reglage
    [Documentation]    Le coeur de la campagne. Les deux campagnes voisines
    ...    constatent le durcissement supérieur de cette release sans pouvoir
    ...    l'expliquer, et l'inscrivent dans ce qu'elles ne couvrent pas.
    ...
    ...    La réponse change la lecture d'une dérive : un écart sur une valeur
    ...    de noyau viendra d'une montée de version, pas d'une modification du
    ...    système, et le remède n'est pas le même.
    ...
    ...    Assertion de NON-DÉRIVE : le jour où un paramètre de sécurité
    ...    apparaîtra dans le profil, ce scénario échouera, et ce sera le bon
    ...    comportement, puisqu'une décision humaine aura été prise.
    ${lots}=    Create List
    ...    @{PARAMS_PASSWORD_POLICY}    @{PARAMS_LOGON_PROTECTION}
    ...    @{PARAMS_AUDIT}    @{PARAMS_GATEWAY}
    ...    @{PARAMS_RFC_AND_AUTH}    @{PARAMS_TRANSPORT_SECURITY}
    ${mesures}=    Read Security Parameters    ${lots}
    ${effectifs}=    Evaluate    {m["name"]: m["value"] for m in $mesures if m["status"] == "defined"}
    ${verdict}=    Cross Check Parameter Origins    ${SCREEN_PARAMETERS}
    ...    ${effectifs}
    Set Suite Variable    ${ORIGIN_VERDICT}    ${verdict}
    Should Be True    ${verdict}[total] > 0
    ...    msg=Aucun paramètre croisé : le relevé d'écran et les mesures RFC ne se recoupent pas.
    # L'assertion qui porte le résultat : le profil ne MODIFIE aucune valeur
    # de sécurité. « Posé dans le profil » et « modifié par le profil » ne
    # sont pas la même chose, et c'est le run live qui a imposé la nuance :
    # trois paramètres du périmètre y sont déclarés, tous à la valeur du
    # défaut, donc aucun ne durcit ni n'affaiblit.
    Length Should Be    ${verdict}[profile_changing]    ${EXPECTED_PROFILE_CHANGING}
    ...    msg=Le profil d'instance MODIFIE désormais un paramètre de sécurité : ${verdict}[profile_changing]. C'est une décision humaine, à acquitter.
    Lists Should Be Equal    ${verdict}[profile_backed]    ${EXPECTED_PROFILE_BACKED}
    ...    ignore_order=${True}
    ...    msg=La liste des paramètres DÉCLARÉS dans le profil a changé.
    Should Be Empty    ${verdict}[divergent]
    ...    msg=Des paramètres ne suivent ni le profil ni le défaut : ${verdict}[divergent]
    Log    Origine : ${verdict}[by_origin]
    Log    Déclarés au profil sans rien modifier : ${verdict}[profile_redundant]
    Log    Hérités du noyau : ${verdict}[kernel_backed]

Le profil l emporte quand il existe
    [Documentation]    La contre-épreuve du scénario précédent. Sans elle,
    ...    « aucun paramètre de sécurité dans le profil » pourrait vouloir dire
    ...    que la colonne de profil n'est pas ce qu'on croit.
    ...
    ...    Le croisement porte ici sur des paramètres NON liés à la sécurité,
    ...    choisis parce que leur valeur de profil diffère du défaut : eux
    ...    seuls discriminent.
    ${candidats}=    Discriminating Parameter Names    ${SCREEN_PARAMETERS}
    ...    limit=${CONTRE_EPREUVE_TAILLE}
    Should Not Be Empty    ${candidats}
    ...    msg=Aucun paramètre discriminant : la contre-épreuve ne peut pas être jouée.
    ${mesures}=    Read Security Parameters    ${candidats}
    ${effectifs}=    Evaluate    {m["name"]: m["value"] for m in $mesures if m["status"] == "defined"}
    ${verdict}=    Cross Check Parameter Origins    ${SCREEN_PARAMETERS}
    ...    ${effectifs}    ${candidats}
    # La PRÉPONDÉRANCE, et non la simple existence d'un cas : sur les témoins
    # comparables, l'effectif doit suivre le profil dans une large majorité.
    # La première écriture se contentait d'un « non vide », qui passait avec
    # UN seul appariement sur vingt-cinq et ne prouvait donc pas la règle.
    ${comparables}=    Evaluate    $verdict["total"] - len($verdict["not_comparable"])
    ${suivent}=    Get Length    ${verdict}[profile_backed]
    Should Be True    ${comparables} > 0
    ...    msg=Aucun témoin comparable : la contre-épreuve ne mesure rien.
    Should Be True    ${suivent} * 100 >= ${comparables} * ${SEUIL_PREPONDERANCE}
    ...    msg=Seuls ${suivent} témoins sur ${comparables} comparables voient leur effectif suivre le profil : la colonne de profil ne veut pas dire ce que la campagne suppose.
    Log    ${verdict}[total] paramètres croisés, ${comparables} comparables, ${suivent} suivant le profil
    Log    Écartés comme tronqués : ${verdict}[not_comparable]

La colonne de profil est tronquee et la campagne l ecarte
    [Documentation]    La colonne de profil coupe à une largeur fixe SANS
    ...    marqueur. Comparer cette valeur à celle du canal RFC, complète,
    ...    fabrique un écart qui n'existe pas.
    ...
    ...    Le scénario fige le piège pour que personne ne « corrige » la garde
    ...    en la trouvant trop prudente : les valeurs suspectes sont ÉCARTÉES
    ...    de la comparaison, jamais déclarées divergentes.
    ${suspects}=    Truncated Profile Names    ${SCREEN_PARAMETERS}
    Should Not Be Empty    ${suspects}
    ...    msg=Aucune valeur à la largeur de colonne : la troncature a peut-être disparu, à re-mesurer avant de retirer la garde.
    ${mesures}=    Read Security Parameters    ${suspects}
    ${effectifs}=    Evaluate    {m["name"]: m["value"] for m in $mesures if m["status"] == "defined"}
    Should Not Be Empty    ${effectifs}
    ...    msg=Aucun de ces paramètres n'est mesurable par le canal RFC : la troncature ne peut pas être PROUVÉE, seulement soupçonnée.
    # La PREUVE de la troncature, et non sa re-déduction : la valeur complète
    # que rend le canal RFC doit COMMENCER par la valeur coupée de l'écran, et
    # être strictement plus longue. C'est ce qu'une comparaison d'égalité
    # naïve lirait comme un écart, alors que les deux canaux disent la même
    # chose. La première écriture de ce scénario se contentait de relire son
    # propre critère de sélection, ce qui ne pouvait pas échouer.
    ${prouves}=    Proven Truncations    ${SCREEN_PARAMETERS}    ${effectifs}
    Should Not Be Empty    ${prouves}
    ...    msg=Aucune valeur d'écran n'est le PRÉFIXE de la valeur complète du canal RFC : ce n'est donc pas une troncature, et la garde repose sur une hypothèse fausse.
    ${verdict}=    Cross Check Parameter Origins    ${SCREEN_PARAMETERS}
    ...    ${effectifs}    ${suspects}
    ${faux_ecarts}=    Evaluate    sorted(set($prouves) & set($verdict["divergent"]))
    Should Be Empty    ${faux_ecarts}
    ...    msg=Des valeurs PROUVÉES tronquées sont classées divergentes : la garde ne les écarte pas, et elles produisent de faux écarts (${faux_ecarts}).
    ${n}=    Get Length    ${suspects}
    Log    ${n} paramètres à la largeur de colonne, dont ${prouves.__len__()} dont la troncature est PROUVÉE par le canal RFC.

Le mandant de reference est mesure par l ecran
    [Documentation]    La campagne de surface consigne ce mandant comme hors
    ...    de portée : l'ouverture d'une session RFC y est refusée avec les
    ...    identifiants de la campagne. Un rapport d'écran le lit depuis la
    ...    session courante.
    ${releve}=    Run Standard User Report
    Set Suite Variable    ${STANDARD_USERS}    ${releve}
    Should Not Be Empty    ${releve}
    ...    msg=Le rapport des comptes standards n'a rien rendu : lecture douteuse.
    ${mandants}=    Evaluate    sorted({r["${COL_USER_CLIENT}"].strip() for r in $releve})
    Should Contain    ${mandants}    ${EXPECTED_REFERENCE_CLIENT}
    ...    msg=Le mandant de référence est absent du relevé : l'écran n'apporte alors rien de plus que le canal RFC.
    Should Contain    ${mandants}    ${EXPECTED_WORKING_CLIENT}
    Log    Mandants couverts : ${mandants}
    Log    Relevé : ${releve}

Le pictogramme de verrouillage s interprete par croisement
    [Documentation]    La méthode que la campagne apporte, plus encore que le
    ...    résultat. La colonne de verrouillage rend un identifiant d'ICÔNE :
    ...    ni un booléen, ni un libellé, mais ce que le client résout en image.
    ...    Il ne dépend pas de la langue, et il ne se lit pas seul.
    ...
    ...    Son sens est ÉTABLI sur le mandant où les deux canaux se recouvrent,
    ...    puis appliqué au mandant que seul l'écran atteint. Un code ambigu
    ...    n'est JAMAIS traduit.
    ${icone}=    Set Variable    ${STANDARD_USERS}[0][${COL_USER_LOCK_ICON}]
    ${code}=    Icon Code    ${icone}
    Should Not Be Equal    ${code}    ${None}
    ...    msg=La colonne de verrouillage ne porte plus un code d'icône : la lire comme une donnée était justement le piège.
    ${codes}=    Distinct Icons    ${STANDARD_USERS}    ${COL_USER_LOCK_ICON}
    ${comptes}=    Read Account Surface
    # La vérité de référence vient de la RAISON brute, dérivée du masque de
    # verrouillage, et non du statut synthétique : celui-ci applique une
    # précédence (verrouillé l'emporte sur expiré) qui n'a rien à voir avec ce
    # qu'on cherche à établir ici, et une évolution de cette précédence
    # casserait le croisement en silence.
    ${connus}=    Evaluate
    ...    {"${EXPECTED_WORKING_CLIENT}/" + c["user"]: ("locked" in c["reasons"]) for c in $comptes["accounts"]}
    ${sens}=    Establish Lock Icon Meaning    ${STANDARD_USERS}    ${connus}
    Should Be True    ${sens}[coverage] > 0
    ...    msg=Aucun recoupement entre les deux canaux : le pictogramme ne peut même pas être confronté.
    Should Be Empty    ${sens}[ambiguous]
    ...    msg=Le pictogramme correspond aux DEUX états selon les lignes : il n'est pas traduit, et c'est le repli sûr.
    # Le verdict HONNÊTE sur cette cible, et il a été durci après une réserve
    # de revue : le recoupement porte sur des lignes qui portent toutes le
    # MÊME code et le MÊME état, donc il ne discrimine rien. « Ce code signifie
    # non verrouillé » y est indiscernable de « ce code signifie que la ligne
    # existe », hypothèse d'autant plus soutenue que les cellules vides sont
    # exactement les comptes inexistants. Le sens n'est donc PAS établi, et il
    # n'est surtout pas appliqué au mandant que seul l'écran atteint.
    Should Not Be True    ${sens}[discriminating]
    ...    msg=Le recoupement discrimine désormais : un second code ou un second état est apparu, et le sens PEUT être établi. Mettre le plan à jour.
    Should Be Empty    ${sens}[meanings]
    ...    msg=Un sens a été traduit sans contraste suffisant : c'est exactement ce que le repli sûr doit empêcher.
    List Should Contain Value    ${sens}[not_discriminating]    ${code}
    Log    Codes d'icône vus : ${codes} (un seul code sur les comptes existants)
    Log    Recoupement : ${sens}[coverage] lignes, non discriminant, sens NON établi
    Log    Lignes que seul l'écran atteint, laissées ININTERPRÉTÉES : ${sens}[unmatched]

Le statut des mots de passe est rapporte et jamais asserte
    [Documentation]    Ce libellé est TRADUIT (convention 3). L'asserter
    ...    rendrait la suite dépendante de la langue de la session, et le
    ...    premier passage sur un système dans une autre langue la ferait
    ...    rougir pour une raison sans rapport avec la sécurité.
    ...
    ...    Ce qui est asserté est donc seulement que la colonne est RENSEIGNÉE
    ...    pour les comptes que le rapport a trouvés.
    ${renseignes}=    Evaluate    [r for r in $STANDARD_USERS if r["${COL_USER_PASSWORD_STATUS}"].strip()]
    Should Not Be Empty    ${renseignes}
    ...    msg=Aucun statut de mot de passe renseigné : la colonne n'est pas lue.
    Length Should Be    ${renseignes}    ${STANDARD_USERS.__len__()}
    ...    msg=Des lignes sans statut : lecture partielle du rapport.
    FOR    ${ligne}    IN    @{STANDARD_USERS}
        Log    ${ligne}[${COL_USER_CLIENT}] / ${ligne}[${COL_USER_NAME}] : ${ligne}[${COL_USER_PASSWORD_STATUS}]
    END

Le parametre qui protege les cookies ne produit pas son effet
    [Documentation]    Le second résultat de la campagne, et aucun des deux
    ...    autres canaux ne peut le voir : le paramètre est positionné, son
    ...    origine est connue, et l'effet n'est pas là.
    ...
    ...    La première assertion est la plus importante : sans cookie observé,
    ...    le résumé serait vide et se lirait comme « aucun cookie non
    ...    protégé ».
    ...
    ...    Ce scénario n'exige NI `Secure` NI en-têtes de sécurité : les
    ...    exiger d'un banc servi en clair rendrait la suite rouge à vie, donc
    ...    désactivée.
    # Observation propre au scénario, et non la relecture de celle du test 1 :
    # un relevé de cookies vide se lirait comme « aucun cookie non protégé ».
    ${cookies}=    Get Api Cookie Security    alias=${HTTP_ALIAS}
    ...    probe_path=${ODATA_CATALOG_SERVICES}/$count?sap-client=${RFC_CLIENT}
    Should Be True    ${cookies}[total] > 0
    ...    msg=Aucun cookie observé : rien n'est mesuré, et surtout ce n'est pas une protection.
    # Le paramètre doit être RECONNU par la cible avant qu'on parle de son
    # effet. Sans cette garde (oubliée à la première écriture, relevée par la
    # revue), un nom mal orthographié ou retiré de la release rendrait une
    # valeur nulle, et le verdict « déclaré sans effet » serait VERT en
    # affirmant un faux positif de conformité qui n'existe plus.
    ${declare}=    Security Parameters Should Be Known    ${COOKIE_CONTROL}
    ${valeur}=    Set Variable    ${declare}[0][value]
    Should Not Be Equal    ${valeur}    ${None}
    ...    msg=Le paramètre n'a pas de valeur effective : il n'y a rien à confronter.
    ${protege}=    Evaluate    not $cookies["without_httponly"]
    ${verdict}=    Confront Security Control    cookies.httponly    ${valeur}
    ...    ${protege}
    Set Suite Variable    ${COOKIE_VERDICT}    ${verdict}
    Set Suite Variable    ${COOKIE_SECURITY}    ${cookies}
    Should Be Equal    ${verdict}[verdict]    ${EXPECTED_COOKIE_VERDICT}
    ...    msg=La confrontation entre le paramètre déclaré et l'effet observé a changé de verdict. Si l'effet est désormais produit, c'est une bonne nouvelle à acquitter.
    Log    ${verdict}[note]
    Log    Déclaré : ${valeur} | cookies sans HttpOnly : ${cookies}[without_httponly]
    Log    Cookies sans Secure : ${cookies}[without_secure] (canal HTTPS : ${cookies}[over_https])

Les en tetes de securite de la reponse sont inventories
    [Documentation]    RAPPORTÉ, jamais asserté : aucun de ces en-têtes n'est
    ...    obligatoire, ce sont des protections que le navigateur applique
    ...    quand le serveur les demande. Une cible qui n'en pose aucun les
    ...    laisse à la charge de ce qui est devant elle, et c'est un constat de
    ...    posture, pas une non-conformité.
    ${entetes}=    Get Api Security Headers
    ...    ${ODATA_CATALOG_SERVICES}/$count?sap-client=${RFC_CLIENT}    alias=${HTTP_ALIAS}
    Set Suite Variable    ${SECURITY_HEADERS_SEEN}    ${entetes}
    Should Be True    ${entetes}[count_expected] > 0
    Log    Présents : ${entetes}[present]
    Log    Absents : ${entetes}[missing]

Le canal HTTP repose sur un noeud que le canal RFC mesure
    [Documentation]    La seule dépendance de canal à canal de la campagne, et
    ...    elle est vérifiée plutôt que supposée : un service web ne répond que
    ...    si le noeud du dictionnaire de services qui le porte est actif.
    ${exposition}=    Read Web Exposure
    Set Suite Variable    ${WEB_EXPOSURE}    ${exposition}
    Should Be True    ${exposition}[active] > 0
    ...    msg=Aucun noeud de service actif, alors que le canal HTTP vient de répondre : lecture douteuse.
    Should Be Equal As Integers    ${exposition}[unmatched]    ${0}
    ...    msg=La jointure des deux tables de services est partielle : ${exposition}[unmatched] noeud(s) orphelin(s).
    ${noms}=    Evaluate    sorted({n for n in $exposition["sensitive_active"]})
    Log    Noeuds actifs : ${exposition}[active] | services sensibles : ${noms}

Le croisement tient dans un artefact rejouable
    [Documentation]    La leçon de la campagne précédente, dont l'artefact
    ...    portait la date de lecture dans son périmètre haché et n'était donc
    ...    pas déterministe d'un jour à l'autre. La contre-épreuve est JOUÉE,
    ...    pas affirmée.
    ${croisement}=    Create Dictionary
    ...    parameter_origins=${ORIGIN_VERDICT}
    ...    cookie_security=${COOKIE_SECURITY}
    ...    cookie_verdict=${COOKIE_VERDICT}
    ...    security_headers=${SECURITY_HEADERS_SEEN}
    ...    web_exposure=${WEB_EXPOSURE}
    ...    screen_parameters_total=${SCREEN_PARAMETERS.__len__()}
    ...    screen_parameters_substituted=${SCREEN_SUBSTITUTED}
    ${charge}=    Create Dictionary    target=${TARGET_IDENTITY}
    ...    crossing=${croisement}
    ${chemin}=    Write Deterministic Artifact    ${CROSS_ARTIFACT}    ${charge}
    ...    hashed_keys=crossing
    ${relu}=    Read Deterministic Artifact    ${chemin}
    Should Be Equal    ${relu}[hash_scope][hashed_keys][0]    crossing
    ...    msg=Le périmètre d'empreinte n'est pas celui déclaré : la comparaison entre deux passages ne serait pas probante.
    ${variante}=    Copy Dictionary    ${charge}    deepcopy=${True}
    Set To Dictionary    ${variante}[target]    read_on=19700101
    ${empreinte}=    Artifact Hash    ${variante}    hashed_keys=crossing
    Should Be Equal    ${relu}[sha256]    ${empreinte}
    ...    msg=L'empreinte dépend d'une valeur volatile de la cible : deux passages identiques seraient déclarés divergents.
    Log    Artefact : ${chemin}
    Log    Empreinte (hors horodatage) : ${relu}[sha256]


*** Keywords ***
Ouvrir Les Trois Canaux
    [Documentation]    Rattache la suite à la session SAP GUI déjà ouverte,
    ...    puis ouvre les canaux RFC et HTTP. Le canal RFC est optionnel : sans
    ...    lui la suite se saute au lieu de rougir.
    ...
    ...    L'écran n'est PAS ouvert ici : une session doit préexister, et la
    ...    suite s'y rattache. C'est ce qui permet au mot de passe d'entrer par
    ...    la ligne de commande sans transiter par un serveur intermédiaire.
    Skip Unless Rfc Channel Is Available
    Attach To Open Session    0    0
    Open Security Audit Channel
    Open Api Session    ${HTTP_BASE_URL}    alias=${HTTP_ALIAS}
    ...    user=${RFC_USER}    password=${RFC_PASSWORD}    sap_client=${RFC_CLIENT}

Fermer Les Trois Canaux
    [Documentation]    Referme les canaux OUVERTS par cette suite, et seulement
    ...    eux : la session SAP GUI préexistait, elle n'est pas fermée ici.
    ...
    ...    Une session HTTP laissée ouverte est une session utilisateur ouverte
    ...    côté serveur, au même titre qu'une connexion RFC orpheline : le
    ...    teardown n'est pas une politesse. Chaque fermeture est tentée même
    ...    si la précédente a échoué.
    Run Keyword And Ignore Error    Close All Api Sessions
    Run Keyword And Ignore Error    Close Security Audit Channel
