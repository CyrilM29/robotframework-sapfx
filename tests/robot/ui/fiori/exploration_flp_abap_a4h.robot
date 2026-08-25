*** Settings ***
Documentation       Exploration du launchpad Fiori hébergé par un serveur ABAP (A4H 1909)
...                 Spec: specs/exploration-flp-abap-a4h.md (sha256:255e2b279b5c, 2026-08-24)
...                 Generated from specs/exploration-flp-abap-a4h.md by sap-generator: re-run the generator
...                 rather than hand-editing locators here
...
...                 Campagne d'exploration du **launchpad Fiori servi par un
...                 serveur ABAP** (FLP « ushell classique » du service ICF
...                 `/sap/bc/ui2/flp`), sur une ABAP Platform 1909 de
...                 démonstration servant SAPUI5 1.71.
...
...                 Ce que cette campagne établit, et qui l'oppose point par
...                 point au launchpad SAP Build Work Zone déjà couvert par
...                 `exploration_launchpad_workzone.robot` : ici il n'y a
...                 **aucune iframe**, l'application vit dans le document du
...                 shell et se reconnaît au conteneur nommé d'après son intent ;
...                 le catalogue se lit au service `LaunchPage` et non au
...                 service `SearchableContent`, absent de ce ushell ; et le
...                 runtime 1.71 n'émet aucune dépréciation, ce qui rend le tri
...                 des erreurs console lisible.
...
...                 Campagne **pilotée par la découverte** : le catalogue, les
...                 groupes, les tuiles et les applications parcourues sont ceux
...                 que le système déclare le jour du run. Les valeurs
...                 spécifiques à CETTE cible (version, produit, volumétrie
...                 minimale) sont des variables de suite, surchargeables : le
...                 page object, lui, reste valable pour tout launchpad ABAP.
...
...                 **Lecture seule par défaut.** Aucune écriture métier nulle
...                 part. Le mode édition de l'accueil est entré pour être quitté
...                 sans rien déplacer, et le test le CONSTATE en comparant les
...                 groupes avant et après ; le dialogue des paramètres est
...                 refermé par annuler, jamais par enregistrer.
...
...                 **Une seule exception, et elle est verrouillée à deux
...                 tours** : le cycle réversible « épingler puis dépingler »
...                 une application depuis l'App Finder écrit une
...                 personnalisation d'accueil. Il porte le tag `write` ET exige
...                 `-v ABAP_FLP_WRITE_OPT_IN:yes`, sans quoi il est SAUTÉ, y
...                 compris dans un run complet de `tests/robot/` : un tag seul
...                 dépendrait de la mémoire de celui qui lance la commande.
...
...                 Aucun localisateur ici (convention 1) : ils vivent dans
...                 `resources/page_objects/abap_flp.resource`.
...
...                 Prérequis : le serveur ABAP répond en **HTTPS** (la voie HTTP
...                 redirige vers un nom d'hôte virtuel que plusieurs conteneurs
...                 peuvent annoncer, et mène alors au mauvais système).
...                 Exécution ::
...
...                 |  robot --pythonpath src
...                 |  ...   -v ABAP_FLP_URL:https://<hote>:<port>/sap/bc/ui2/flp?sap-client=001
...                 |  ...   -v ABAP_FLP_USER:<utilisateur>
...                 |  ...   -v "ABAP_FLP_PASSWORD: Secret:<motdepasse>"
...                 |  ...   --outputdir results/flp
...                 |  ...   tests/robot/ui/fiori/exploration_flp_abap_a4h.robot

Resource            ../../../../resources/page_objects/abap_flp.resource

Suite Setup         Ouvrir Le Launchpad ABAP
Suite Teardown      Fermer Le Launchpad ABAP
Test Teardown       Journaliser Le Diagnostic Fiori En Cas D Echec

Test Tags           fiori    flp    abap    a4h    live


*** Variables ***
# Valeurs relevées LIVE sur cette cible le 2026-08-24. Elles vivent ici, et non
# dans le page object, parce qu'elles décrivent CE système : une seconde
# campagne sur une autre release ABAP réutilise le page object tel quel et
# surcharge ces variables.
${FLP_VERSION_ATTENDUE}         1.71    # ligne du runtime SAPUI5 servi
${FLP_PRODUIT_ATTENDU}          ABAP PLATFORM    # nommé par le dialogue « à propos »
${FLP_CONTROLES_MINIMUM}        ${150}    # accueil mesuré entre 184 et 192 contrôles
${FLP_LANGUES_ATTENDUES}        ${2}    # DE et EN, seules langues installées
# Termes de recherche : PARTIELS à dessein. Le titre exact d'une application
# fait naviguer le shell directement vers elle au lieu d'ouvrir les résultats.
${FLP_TERME_RECHERCHE}          Manage
${FLP_TERME_APPFINDER}          Shop
# Terme du cycle d'épinglage : il doit laisser UNE seule vignette ET viser une
# application ABSENTE de l'accueil, sinon le cycle ne prouverait rien. Sur cette
# cible les quatre tuiles de l'accueil couvrent déjà « Shop », d'où un terme
# distinct de celui du filtrage : « Logos » ne laisse qu'une vignette
# (`Logo-manage`), relevé live.
${FLP_TERME_EPINGLAGE}          Logos
# Utilisateur volontairement valide, mot de passe volontairement faux : une
# SEULE tentative dans la campagne, pour ne pas approcher le verrouillage du
# compte (le seuil est un réglage serveur, non observé).
${FLP_MOT_DE_PASSE_FAUX}        mot_de_passe_volontairement_faux


*** Test Cases ***
La page de connexion est bien celle du serveur ABAP vise
    [Documentation]    Scénario 1 du plan. Avant d'accorder du crédit à quoi que
    ...    ce soit, constater que l'URL réellement atteinte est celle demandée,
    ...    sur l'hôte demandé : sans ce contrôle, une page de connexion servie
    ...    par un AUTRE serveur ABAP du même poste rendrait toute la campagne
    ...    verte sur la mauvaise cible. La page de connexion ICF n'est pas du
    ...    UI5, et la composition doit le dire.
    ${champs}=    La Page De Connexion Est Rendue
    ${hote_demande}=    Evaluate    urllib.parse.urlparse($ABAP_FLP_URL).netloc    modules=urllib.parse
    ${hote_atteint}=    Evaluate
    ...    urllib.parse.urlparse($ABAP_FLP_URL_AVANT_CONNEXION).netloc    modules=urllib.parse
    Should Be Equal    ${hote_atteint}    ${hote_demande}
    ...    msg=Redirection vers un autre hôte que la cible : ${hote_atteint} au lieu de ${hote_demande}.
    ${composition}=    Lire La Composition De La Portee Courante
    Should Not Be True    ${composition}[ui5_runtime]
    ...    msg=Un runtime UI5 est présent sur la page de connexion ICF.
    Should Be Equal As Integers    ${composition}[ui5_controls]    0
    Should Be Equal    ${composition}[engines]    ${{['dom']}}
    ...    msg=La page de connexion devrait relever du seul moteur dom : ${composition}[engines]
    Should Be Equal As Integers    ${champs}[utilisateur]    1
    Should Be Equal As Integers    ${champs}[mot_de_passe]    1
    Should Be Equal As Integers    ${champs}[soumission]    1
    Should Be Equal As Integers    ${champs}[langues]    1
    ${langues}=    Lire Les Langues De Connexion
    Length Should Be    ${langues}    ${FLP_LANGUES_ATTENDUES}
    ...    msg=Langues proposées à la connexion : ${langues}
    Log    Cible atteinte : ${ABAP_FLP_URL_AVANT_CONNEXION} / langues ${langues}    console=True

Une authentification refusee le dit et ne laisse pas entrer
    [Documentation]    Scénario 2 du plan. Le chemin d'erreur éprouvé pour
    ...    lui-même : un mot de passe faux laisse la page de connexion en place,
    ...    rend un message portant la classe d'erreur du logon ICF, et ne charge
    ...    aucun runtime. UNE seule tentative dans toute la campagne.
    Tenter Une Connexion    ${ABAP_FLP_USER}    ${FLP_MOT_DE_PASSE_FAUX}
    La Connexion Est Refusee
    Log    Refus constaté sur la page de connexion, aucun runtime chargé.    console=True

La connexion nominale rend un shell FLP identifiable
    [Documentation]    Scénario 3 du plan. Le shell doit s'annoncer pour ce qu'il
    ...    est : un runtime UI5 de la ligne attendue, des contrôles réellement
    ...    construits, aucun hôte Web Components et surtout **aucune iframe**,
    ...    ce qui distingue structurellement ce launchpad d'un cFLP. L'identité
    ...    de session est lue au conteneur, seule source qui dise ce que le
    ...    SERVEUR a ouvert.
    Se Connecter Au Launchpad
    ${composition}=    Attendre Que Le Shell Soit Construit    ${FLP_CONTROLES_MINIMUM}
    Should Be True    ${composition}[ui5_runtime]
    ...    msg=Aucun runtime UI5 après authentification.
    Should Start With    ${composition}[ui5_version]    ${FLP_VERSION_ATTENDUE}
    ...    msg=Runtime servi ${composition}[ui5_version], attendu sur la ligne ${FLP_VERSION_ATTENDUE}.
    Should Be Equal As Integers    ${composition}[wc_hosts]    0
    ...    msg=Des hôtes Web Components sur un ushell classique : la cible n'est pas celle attendue.
    Should Be Empty    ${composition}[frames]
    ...    msg=Ce launchpad ne doit contenir aucune iframe : ${composition}[frames]
    Should Contain    ${composition}[engines]    role
    Should Contain    ${composition}[engines]    xpath
    ${identite}=    Lire L Identite De Session
    Should Be Equal    ${identite}[utilisateur]    ${ABAP_FLP_USER}
    ...    msg=Le conteneur ushell déclare l'utilisateur ${identite}[utilisateur] et non ${ABAP_FLP_USER}.
    Le Fragment Courant Commence Par    ${ABAP_FLP_HOME_INTENT}
    Log    Shell UI5 ${composition}[ui5_version] : ${composition}[ui5_controls] contrôles, identité ${identite}    console=True

Le catalogue de l utilisateur est inventorie par le service
    [Documentation]    Scénario 4 du plan. Le catalogue est lu au service du
    ...    shell, qui répond ce que l'utilisateur a le DROIT d'ouvrir, et non ce
    ...    que l'écran affiche : mesuré live, l'App Finder ne rend qu'une partie
    ...    des tuiles déclarées, donc compter à l'écran donnerait un nombre faux.
    ...    Chaque tuile doit porter un intent de la forme SemanticObject-action.
    [Setup]    Revenir A L Accueil
    ${catalogues}=    Inventorier Les Catalogues
    Should Not Be Empty    ${catalogues}
    ...    msg=Aucun catalogue assigné à cet utilisateur.
    ${tuiles}=    Compter Les Tuiles Du Catalogue    ${catalogues}
    Should Be True    ${tuiles} > 0
    ...    msg=Les catalogues assignés ne déclarent aucune tuile.
    FOR    ${catalogue}    IN    @{catalogues}
        Should Not Be Empty    ${catalogue}[id]
        ...    msg=Un catalogue sans identifiant technique : ${catalogue}
        FOR    ${tuile}    IN    @{catalogue}[tuiles]
            ${morceaux}=    Split String    ${tuile}[intent]    -    1
            Length Should Be    ${morceaux}    2
            ...    msg=L'intent « ${tuile}[intent] » n'est pas de la forme SemanticObject-action.
            Should Not Be Empty    ${morceaux}[0]
            Should Not Be Empty    ${morceaux}[1]
        END
        Log    Catalogue ${catalogue}[id] : ${{len($catalogue['tuiles'])}} tuiles    console=True
    END
    ${intents}=    Lire Les Intents Du Catalogue    ${catalogues}
    Should Be True    ${{len($intents)}} <= ${tuiles}
    ...    msg=Plus d'intents uniques que de tuiles : le dédoublonnage est faux.
    ${objets}=    Evaluate    len({i.split('-')[0] for i in $intents})
    Log    Catalogue : ${{len($catalogues)}} catalogues, ${tuiles} tuiles, ${{len($intents)}} intents uniques, ${objets} objets sémantiques    console=True

Toute application offerte au catalogue est ouvrable ou l ecart est nomme
    [Documentation]    Scénario 5 du plan. Les intents du catalogue sont soumis
    ...    au service de résolution de navigation, **plus un intent fabriqué**.
    ...    L'intent fabriqué doit être déclaré non résolvable : sans cette
    ...    contre-preuve, un service qui répondrait « oui » à tout rendrait le
    ...    test vert et vide.
    ...
    ...    Les intents assignés mais non résolvables sont RAPPORTÉS, pas mis en
    ...    échec : ils décrivent un système de démonstration dont tous les
    ...    composants ne sont pas déployés, et figer leur nombre ferait échouer
    ...    la campagne sur un autre système parfaitement sain.
    [Setup]    Revenir A L Accueil
    ${catalogues}=    Inventorier Les Catalogues
    ${intents}=    Lire Les Intents Du Catalogue    ${catalogues}
    ${a_sonder}=    Evaluate    list($intents) + [$ABAP_FLP_INTENT_INCONNU]
    ${resolutions}=    Les Intents Sont Ils Resolvables    ${a_sonder}
    Length Should Be    ${resolutions}    ${{len($a_sonder)}}
    ...    msg=Le service n'a pas répondu pour chaque intent soumis.
    ${bilan}=    Separer Les Intents Non Resolvables    ${resolutions}
    Should Contain    ${bilan}[non_resolvables]    ${ABAP_FLP_INTENT_INCONNU}
    ...    msg=L'intent fabriqué « ${ABAP_FLP_INTENT_INCONNU} » est déclaré résolvable : le service répond oui à tout, la préflight ne prouve rien.
    ${ecarts}=    Evaluate    [i for i in $bilan['non_resolvables'] if i != $ABAP_FLP_INTENT_INCONNU]
    Should Be True    ${{len($bilan['resolvables'])}} > 0
    ...    msg=Aucun intent du catalogue n'est résolvable : le service de navigation ne répond pas.
    Log    Résolvabilité : ${{len($bilan['resolvables'])}} intents ouvrables sur ${{len($intents)}} assignés. Assignés mais NON ouvrables : ${ecarts}    console=True

L accueil rend ses groupes et ses tuiles compteurs compris
    [Documentation]    Scénario 6 du plan. Les groupes sont lus au service (leur
    ...    titre rendu diffère de celui que retourne le service, et les deux sont
    ...    traduits : l'ancre est l'identifiant technique). Chaque tuile rendue
    ...    doit viser un intent présent au catalogue, l'accueil étant un
    ...    sous-ensemble de celui-ci. Un compteur non résolu est RAPPORTÉ
    ...    nommément, jamais mis en échec.
    [Setup]    Revenir A L Accueil
    ${groupes}=    Inventorier Les Groupes De L Accueil
    Should Not Be Empty    ${groupes}
    ...    msg=Aucun groupe sur l'accueil.
    ${tuiles}=    Lire Les Tuiles De L Accueil
    Should Not Be Empty    ${tuiles}
    ...    msg=Aucune tuile rendue sur l'accueil.
    ${catalogues}=    Inventorier Les Catalogues
    ${intents_catalogue}=    Lire Les Intents Du Catalogue    ${catalogues}
    FOR    ${tuile}    IN    @{tuiles}
        Should Not Be Empty    ${tuile}[titre]
        ...    msg=Une tuile rendue sans titre de propriété : ${tuile}
        Should Contain    ${intents_catalogue}    ${tuile}[intent]
        ...    msg=La tuile « ${tuile}[titre] » vise l'intent ${tuile}[intent], absent du catalogue de l'utilisateur.
    END
    ${compteurs}=    Separer Les Compteurs Non Resolus    ${tuiles}
    Should Be True    ${{len($compteurs['numeriques'])}} > 0
    ...    msg=Aucune tuile dynamique n'a résolu son compteur : le système ne sert plus aucune donnée.
    ${sans_compteur}=    Evaluate    [t['intent'] for t in $compteurs['non_resolus']]
    Log    Accueil : ${{len($groupes)}} groupes, ${{len($tuiles)}} tuiles rendues, ${{len($compteurs['numeriques'])}} compteurs résolus. Fournisseur de données non résolu pour : ${sans_compteur}    console=True

Ouvrir une application par sa tuile et par son intent mene au meme endroit
    [Documentation]    Scénario 7 du plan. Les deux voies d'ouverture doivent
    ...    mener au même endroit : celle de l'utilisateur (cliquer la tuile) et
    ...    celle des tests (naviguer par intent). L'application est CHOISIE par
    ...    découverte : la première tuile de l'accueil dont le compteur est
    ...    résolu, donc dont le fournisseur de données répond.
    ...
    ...    Le témoin d'ouverture est le conteneur d'application dérivé de
    ...    l'intent : ni généré ni traduit, il remplace ici le test d'iframe des
    ...    launchpads hébergés dans le cloud.
    [Setup]    Revenir A L Accueil
    ${tuiles}=    Lire Les Tuiles De L Accueil
    ${compteurs}=    Separer Les Compteurs Non Resolus    ${tuiles}
    ${cible}=    Set Variable    ${compteurs}[numeriques][0]
    ${controles_accueil}=    Lire La Composition De La Portee Courante
    Ouvrir L Application Par Intent    ${cible}[intent]
    ${par_intent}=    Lire Le Fragment Courant
    ${composition_app}=    Lire La Composition De La Portee Courante
    Should Be Empty    ${composition_app}[frames]
    ...    msg=Une iframe est apparue à l'ouverture de l'application : ${composition_app}[frames]
    Should Be True    ${composition_app}[ui5_controls] > ${controles_accueil}[ui5_controls]
    ...    msg=L'application ouverte ne rend pas plus de contrôles que l'accueil.
    Revenir A L Accueil
    Aucune Application N Est Ouverte    ${cible}[intent]
    Ouvrir L Application Par Sa Tuile    ${cible}[titre]    ${cible}[intent]
    ${par_la_tuile}=    Lire Le Fragment Courant
    Should Be Equal    ${par_la_tuile}    ${par_intent}
    ...    msg=La tuile et l'intent n'aboutissent pas au même fragment (${par_la_tuile} contre ${par_intent}).
    Log    « ${cible}[titre] » ouverte par les deux voies sur ${par_intent} : ${composition_app}[ui5_controls] contrôles contre ${controles_accueil}[ui5_controls] à l'accueil    console=True

La recherche du shell trouve les applications de l utilisateur
    [Documentation]    Scénario 8 du plan. La recherche du shell fonctionne
    ...    **bien que** la recherche d'entreprise ne soit pas déployée sur cette
    ...    cible (403 et 404 en console au chargement) : elle se rabat sur le
    ...    catalogue d'applications local. Un test qui conclurait « recherche
    ...    cassée » depuis les erreurs console serait faux.
    ...
    ...    Assertions locale-indépendantes : l'intent atteint, l'identifiant
    ...    TECHNIQUE de la source de données interrogée, et le fait que la page
    ...    de résultats rende strictement plus de tuiles que l'accueil.
    [Setup]    Revenir A L Accueil
    ${tuiles_accueil}=    Compter Les Tuiles Rendues
    Ouvrir La Recherche Du Shell
    Rechercher Dans Le Shell    ${FLP_TERME_RECHERCHE}
    ${filtre}=    Lire Le Filtre De Recherche
    Should Contain    ${filtre}    ${ABAP_FLP_SEARCH_APPS_SOURCE}
    ...    msg=La recherche n'interroge pas la source « applications » : ${filtre}
    Should Contain    ${filtre}    ${FLP_TERME_RECHERCHE}
    ...    msg=Le terme soumis ne figure pas dans le filtre de recherche : ${filtre}
    ${tuiles_resultats}=    Compter Les Tuiles Rendues
    Should Be True    ${tuiles_resultats} > ${tuiles_accueil}
    ...    msg=La recherche ne rend aucun résultat en plus des tuiles de l'accueil (${tuiles_resultats} contre ${tuiles_accueil}).
    Log    Recherche « ${FLP_TERME_RECHERCHE} » : ${tuiles_resultats} tuiles rendues contre ${tuiles_accueil} à l'accueil    console=True

La zone utilisateur expose ses entrees et elles dependent de l endroit
    [Documentation]    Scénario 9 du plan. Les entrées de la zone utilisateur
    ...    sont identifiées par le SUFFIXE technique de leur action, jamais par
    ...    leur libellé (traduit) ni par leur identifiant complet (qui contient
    ...    leur POSITION, laquelle change d'un endroit à l'autre).
    ...
    ...    Le relevé fait sur l'ACCUEIL doit contenir tout celui fait dans une
    ...    application, plus exactement l'entrée d'édition de la page d'accueil,
    ...    qui n'a pas de sens ailleurs.
    [Setup]    Revenir A L Accueil
    Ouvrir La Zone Utilisateur
    ${sur_l_accueil}=    Lire Les Entrees De La Zone Utilisateur
    Fermer La Zone Utilisateur
    ${tuiles}=    Lire Les Tuiles De L Accueil
    ${compteurs}=    Separer Les Compteurs Non Resolus    ${tuiles}
    ${cible}=    Set Variable    ${compteurs}[numeriques][0]
    Ouvrir L Application Par Intent    ${cible}[intent]
    Ouvrir La Zone Utilisateur
    ${dans_l_application}=    Lire Les Entrees De La Zone Utilisateur
    Fermer La Zone Utilisateur
    Should Not Be Empty    ${dans_l_application}
    ...    msg=La zone utilisateur ne rend aucune entrée dans une application.
    ${manquantes}=    Evaluate    sorted(set($dans_l_application) - set($sur_l_accueil))
    Should Be Empty    ${manquantes}
    ...    msg=Des entrées existent dans une application sans exister à l'accueil : ${manquantes}
    ${supplementaires}=    Evaluate    sorted(set($sur_l_accueil) - set($dans_l_application))
    ${edition}=    Evaluate    $ABAP_FLP_EDIT_ENTRY.lstrip('-')
    Should Be Equal    ${supplementaires}    ${{[$edition]}}
    ...    msg=L'écart accueil/application devrait se réduire à l'entrée d'édition : ${supplementaires}
    Log    Zone utilisateur : ${sur_l_accueil} à l'accueil, ${dans_l_application} dans une application    console=True

Le dialogue a propos identifie le systeme et le composant courant
    [Documentation]    Scénario 10 du plan. C'est le seul endroit de l'interface
    ...    qui nomme la version du produit ABAP : il donne à la campagne une
    ...    **empreinte de cible** capable de distinguer deux systèmes de release
    ...    différente. La version SAPUI5 qu'il annonce doit être cohérente avec
    ...    le runtime réellement chargé.
    ...
    ...    Le dialogue est refermé par la POSITION de son bouton, et la
    ...    fermeture est constatée sur la liste des popups OUVERTS : le contrôle,
    ...    lui, reste rendu après acquittement.
    [Setup]    Revenir A L Accueil
    ${composition}=    Lire La Composition De La Portee Courante
    Ouvrir Le Dialogue A Propos
    ${empreinte}=    Lire L Empreinte Systeme
    Should Not Be Empty    ${empreinte}
    ...    msg=Le dialogue « à propos » ne rend aucun contenu.
    ${ligne}=    Evaluate    '.'.join($composition['ui5_version'].split('.')[:2])
    Should Contain    ${empreinte}    ${ligne}
    ...    msg=La version SAPUI5 annoncée par le dialogue est incohérente avec le runtime chargé (${composition}[ui5_version]).
    Should Contain    ${empreinte}    ${FLP_PRODUIT_ATTENDU}
    ...    msg=Le dialogue ne nomme pas le produit attendu (${FLP_PRODUIT_ATTENDU}).
    Acquitter Le Dialogue Ouvert
    Aucun Dialogue N Est Ouvert
    Log    Empreinte de cible : ${empreinte}    console=True

Le dialogue des parametres s ouvre et se referme sans rien modifier
    [Documentation]    Scénario 11 du plan. Les rubriques sont relevées par leur
    ...    clé technique, jamais par leur libellé. Le dialogue est refermé par
    ...    ANNULER : son bouton d'enregistrement écrit une personnalisation
    ...    utilisateur côté serveur, et cette campagne est en lecture seule.
    [Setup]    Revenir A L Accueil
    Ouvrir Les Parametres Utilisateur
    ${rubriques}=    Lire Les Rubriques De Parametres
    Should Not Be Empty    ${rubriques}
    ...    msg=La liste maître des paramètres ne rend aucune rubrique.
    Annuler Les Parametres Utilisateur
    Aucun Dialogue N Est Ouvert
    Log    Rubriques de paramètres rendues : ${rubriques}    console=True

L App Finder ouvre le catalogue et sait le filtrer
    [Documentation]    Scénario 12 du plan. L'App Finder est une page du SHELL,
    ...    pas une application : son fragment est celui du shell et aucun
    ...    conteneur d'application n'apparaît. Sa liste de sources vaut le nombre
    ...    de catalogues assignés plus l'entrée « toutes ».
    ...
    ...    Le nombre d'applications rendues n'est comparé qu'à LUI-MÊME avant et
    ...    après filtrage : le rendu est paresseux et ne montre jamais tout le
    ...    catalogue.
    [Setup]    Revenir A L Accueil
    ${catalogues}=    Inventorier Les Catalogues
    Ouvrir L App Finder
    ${sources}=    Lire Les Sources De Catalogue
    Length Should Be    ${sources}    ${{len($catalogues) + 1}}
    ...    msg=L'App Finder propose ${{len($sources)}} sources pour ${{len($catalogues)}} catalogues assignés (attendu : un de plus).
    ${avant}=    Compter Les Applications Rendues
    Should Be True    ${avant} > 0
    ...    msg=L'App Finder ne rend aucune application.
    Filtrer L App Finder    ${FLP_TERME_APPFINDER}
    ${apres}=    Compter Les Applications Rendues
    Should Be True    ${apres} < ${avant}
    ...    msg=Le filtrage ne réduit pas le nombre d'applications rendues (${apres} contre ${avant}).
    Should Be True    ${apres} > 0
    ...    msg=Le filtre « ${FLP_TERME_APPFINDER} » ne rend aucune application alors que le terme vient du catalogue.
    ${total}=    Compter Les Tuiles Du Catalogue    ${catalogues}
    Log    App Finder : ${{len($sources)}} sources, ${avant} applications rendues sur ${total} déclarées au catalogue, ${apres} après filtrage sur « ${FLP_TERME_APPFINDER} »    console=True

Le mode edition de l accueil s ouvre et se quitte sans rien changer
    [Documentation]    Scénario 13 du plan. Entrer puis sortir du mode édition
    ...    sans rien déplacer ne doit modifier aucune personnalisation : le test
    ...    le CONSTATE en comparant les groupes et leur volume avant et après,
    ...    au lieu de le supposer.
    ...
    ...    Ajouter, déplacer ou supprimer une tuile sont des écritures et restent
    ...    hors périmètre.
    [Setup]    Revenir A L Accueil
    ${avant}=    Inventorier Les Groupes De L Accueil
    Entrer En Mode Edition De L Accueil
    Le Mode Edition Est Actif
    Quitter Le Mode Edition De L Accueil
    ${apres}=    Inventorier Les Groupes De L Accueil
    Should Be Equal    ${apres}    ${avant}
    ...    msg=Les groupes de l'accueil ont changé après un simple aller-retour en mode édition : ${avant} puis ${apres}.
    Log    Mode édition entré et quitté, groupes inchangés : ${apres}    console=True

Le menu toutes mes applications du titre de shell liste le catalogue
    [Documentation]    Scénario 14 du plan. Le popover du titre de shell propose
    ...    les applications de l'accueil et une entrée par catalogue assigné.
    ...
    ...    Le nombre d'entrées rendues est comparé au volume d'UNE source et non
    ...    au total du catalogue : mesuré live, le menu ne rend que la source
    ...    sélectionnée.
    [Setup]    Revenir A L Accueil
    ${catalogues}=    Inventorier Les Catalogues
    ${total}=    Compter Les Tuiles Du Catalogue    ${catalogues}
    Ouvrir Le Menu Toutes Mes Applications
    ${sources}=    Lire Les Sources Du Menu Toutes Mes Applications
    Length Should Be    ${sources}    ${{len($catalogues) + 1}}
    ...    msg=Le menu propose ${{len($sources)}} sources pour ${{len($catalogues)}} catalogues assignés (attendu : un de plus).
    ${entrees}=    Compter Les Entrees Du Menu Toutes Mes Applications
    Should Be True    ${entrees} > 0
    ...    msg=Le menu n'affiche aucune application.
    Should Be True    ${entrees} <= ${total}
    ...    msg=Le menu rend ${entrees} entrées pour ${total} tuiles déclarées au catalogue.
    Fermer Le Popover Courant
    Log    Menu « toutes mes applications » : ${{len($sources)}} sources, ${entrees} entrées rendues sur ${total} tuiles de catalogue    console=True

La navigation arriere du navigateur ramene a l ecran precedent
    [Documentation]    Scénario 15 du plan. Un seul conteneur d'application
    ...    existe à la fois : passer d'une application à l'autre détruit la
    ...    précédente, et la navigation arrière la reconstruit. Les deux
    ...    applications sont choisies par découverte parmi les tuiles dont le
    ...    compteur est résolu.
    [Setup]    Revenir A L Accueil
    ${tuiles}=    Lire Les Tuiles De L Accueil
    ${compteurs}=    Separer Les Compteurs Non Resolus    ${tuiles}
    ${saines}=    Set Variable    ${compteurs}[numeriques]
    Should Be True    ${{len($saines)}} >= 2
    ...    msg=Il faut deux applications ouvrables pour éprouver la navigation arrière ; l'accueil n'en propose que ${{len($saines)}}.
    ${premiere}=    Set Variable    ${saines}[0]
    ${seconde}=    Set Variable    ${saines}[1]
    Ouvrir L Application Par Intent    ${premiere}[intent]
    Ouvrir L Application Par Intent    ${seconde}[intent]
    Aucune Application N Est Ouverte    ${premiere}[intent]
    Revenir En Arriere Dans Le Shell    ${premiere}[intent]
    L Application Ouverte Est    ${premiere}[intent]
    Aucune Application N Est Ouverte    ${seconde}[intent]
    Log    Retour arrière : « ${seconde}[intent] » détruite, « ${premiere}[intent] » reconstruite    console=True

Un intent inexistant est refuse proprement sans quitter l ecran courant
    [Documentation]    Scénario 16 du plan. Le refus doit être propre : un
    ...    dialogue en état d'ERREUR s'ouvre, le fragment ne bouge pas et
    ...    l'application ouverte survit. Après acquittement, l'état est
    ...    exactement celui du relevé initial.
    ...
    ...    Assertions locale-indépendantes : la propriété d'état du dialogue,
    ...    jamais son titre ni son texte ; et l'acquittement par la POSITION du
    ...    bouton, pour la même raison.
    [Setup]    Revenir A L Accueil
    ${tuiles}=    Lire Les Tuiles De L Accueil
    ${compteurs}=    Separer Les Compteurs Non Resolus    ${tuiles}
    ${cible}=    Set Variable    ${compteurs}[numeriques][0]
    Ouvrir L Application Par Intent    ${cible}[intent]
    ${fragment_avant}=    Lire Le Fragment Courant
    Demander Un Intent Inconnu
    ${dialogue}=    Le Shell Refuse La Navigation
    Should Be Equal    ${dialogue}[state]    ${ABAP_FLP_ERROR_STATE}
    ${fragment_pendant}=    Lire Le Fragment Courant
    Should Be Equal    ${fragment_pendant}    ${fragment_avant}
    ...    msg=Le fragment a changé sur un intent refusé : ${fragment_pendant} au lieu de ${fragment_avant}.
    L Application Ouverte Est    ${cible}[intent]
    Acquitter Le Dialogue Ouvert
    Aucun Dialogue N Est Ouvert
    Le Fragment Courant Commence Par    ${fragment_avant}
    L Application Ouverte Est    ${cible}[intent]
    Log    Refus de « ${ABAP_FLP_INTENT_INCONNU} » : dialogue en état ${dialogue}[state], ${dialogue}[buttons] boutons, écran intact    console=True

Un fragment d URL malforme est refuse et l ecran survit
    [Documentation]    Scénario 17 du plan. Un fragment sans partie action est
    ...    refusé comme un intent inconnu, et le shell revient de lui-même au
    ...    fragment de l'application ouverte.
    ...
    ...    Le plan notait, comme observation à confirmer, que ce dialogue-ci
    ...    n'offrirait pas l'accès aux détails techniques. Mesuré live, les deux
    ...    dialogues sont structurellement identiques : l'assertion n'est donc
    ...    pas écrite (voir les écarts consignés dans le plan).
    [Setup]    Revenir A L Accueil
    ${tuiles}=    Lire Les Tuiles De L Accueil
    ${compteurs}=    Separer Les Compteurs Non Resolus    ${tuiles}
    ${cible}=    Set Variable    ${compteurs}[numeriques][0]
    Ouvrir L Application Par Intent    ${cible}[intent]
    ${fragment_avant}=    Lire Le Fragment Courant
    Forcer Un Fragment Malforme
    ${dialogue}=    Le Shell Refuse La Navigation
    Should Be Equal    ${dialogue}[state]    ${ABAP_FLP_ERROR_STATE}
    Acquitter Le Dialogue Ouvert
    Le Fragment Courant Commence Par    ${fragment_avant}
    L Application Ouverte Est    ${cible}[intent]
    Log    Fragment « ${ABAP_FLP_FRAGMENT_MALFORME} » refusé en état ${dialogue}[state], retour sur ${fragment_avant}    console=True

Aucune exception JavaScript non rattrapee sur un chargement propre
    [Documentation]    Scénario 18 du plan. La seule assertion dure porte sur les
    ...    exceptions JavaScript non rattrapées. Les erreurs console sont
    ...    CLASSÉES, pas comptées : une erreur tracée à un composant non déployé
    ...    du système n'est pas un défaut, et un test qui compte devient rouge à
    ...    la première ressource optionnelle absente.
    ...
    ...    La mesure est prise sur un CHARGEMENT PROPRE, journal purgé au
    ...    préalable : l'exploration pollue sa propre mesure, chaque sonde d'un
    ...    service absent ajoutant son 404. Le tri doit être exhaustif, sans quoi
    ...    la classification masquerait ce qu'elle ne connaît pas.
    Recharger L Accueil Proprement
    ${bilan}=    Classer Les Erreurs Du Shell
    Should Be Equal As Integers    ${bilan}[erreurs_de_page]    0
    ...    msg=Le shell a émis ${bilan}[erreurs_de_page] exception(s) JavaScript non rattrapée(s).
    ${classees}=    Evaluate    $bilan['tuile'] + $bilan['recherche'] + $bilan['autres']
    Should Be Equal As Integers    ${classees}    ${bilan}[erreurs_console]
    ...    msg=Le tri des erreurs console n'est pas exhaustif : ${classees} classées sur ${bilan}[erreurs_console].
    Should Be Equal As Integers    ${bilan}[autres]    0
    ...    msg=Erreur console inattendue au chargement propre : ${bilan}[premiere_autre]
    Log    Chargement propre : ${bilan}[erreurs_console] erreurs console, dont ${bilan}[tuile] de fournisseur de tuile et ${bilan}[recherche] de recherche d'entreprise non déployée ; zéro exception non rattrapée    console=True

Epingler puis depingler une application rend l accueil a son etat initial
    [Documentation]    Scénario 20 du plan, et **le seul qui écrit** : le cycle
    ...    réversible de personnalisation de l'accueil, épingler une application
    ...    depuis l'App Finder puis la retirer.
    ...
    ...    **Opt-in à deux tours** : le tag `write` dit ce que le test fait, la
    ...    variable `ABAP_FLP_WRITE_OPT_IN` dit qu'on l'a voulu. Sans elle le
    ...    test est SAUTÉ, y compris dans un run complet de `tests/robot/`, un
    ...    tag seul dépendant de la mémoire de celui qui lance la commande.
    ...
    ...    Ce que le test refuse de supposer : l'état initial de l'accueil est
    ...    MESURÉ (intents rendus et volume de chaque groupe), l'application
    ...    visée est vérifiée ABSENTE avant l'épinglage (sur cette cible les
    ...    quatre tuiles de l'accueil couvrent déjà les applications de
    ...    démonstration, d'où un terme de filtrage distinct de celui du
    ...    scénario 12), et la restauration est CONSTATÉE sur la disparition de
    ...    l'intent épinglé, jamais sur un compte revenu à sa valeur de départ,
    ...    qui ne prouverait qu'une arithmétique.
    [Tags]    write
    [Setup]    Revenir A L Accueil
    Exiger L Accord D Ecriture
    ${groupes_avant}=    Inventorier Les Groupes De L Accueil
    ${intents_avant}=    Lire Les Intents Des Tuiles De L Accueil
    Ouvrir L App Finder
    Filtrer L App Finder    ${FLP_TERME_EPINGLAGE}
    ${appli}=    Lire L Unique Application De L App Finder
    Should Not Contain    ${intents_avant}    ${appli}[intent]
    ...    msg=« ${appli}[intent] » est déjà sur l'accueil : l'épinglage ne prouverait rien, choisir une autre application.
    Epingler L Application
    Revenir A L Accueil
    ${intents_pendant}=    Lire Les Intents Des Tuiles De L Accueil
    Should Contain    ${intents_pendant}    ${appli}[intent]
    ...    msg=L'application épinglée n'apparaît pas sur l'accueil : ${intents_pendant}
    ${groupes_pendant}=    Inventorier Les Groupes De L Accueil
    ${volume_avant}=    Evaluate    sum(g['tuiles'] for g in $groupes_avant)
    ${volume_pendant}=    Evaluate    sum(g['tuiles'] for g in $groupes_pendant)
    Should Be Equal As Integers    ${volume_pendant}    ${{$volume_avant + 1}}
    ...    msg=L'épinglage a fait passer le volume de l'accueil de ${volume_avant} à ${volume_pendant}, attendu une seule tuile de plus.
    Ouvrir L App Finder
    Filtrer L App Finder    ${FLP_TERME_EPINGLAGE}
    Depingler L Application
    Revenir A L Accueil
    ${intents_apres}=    Lire Les Intents Des Tuiles De L Accueil
    Should Not Contain    ${intents_apres}    ${appli}[intent]
    ...    msg=L'application « ${appli}[intent] » est encore sur l'accueil après retrait : la personnalisation n'a pas été rendue.
    Should Be Equal    ${intents_apres}    ${intents_avant}
    ...    msg=L'accueil ne rend pas les mêmes tuiles qu'au départ : ${intents_avant} puis ${intents_apres}.
    ${groupes_apres}=    Inventorier Les Groupes De L Accueil
    Should Be Equal    ${groupes_apres}    ${groupes_avant}
    ...    msg=Les groupes de l'accueil diffèrent de l'état initial : ${groupes_avant} puis ${groupes_apres}.
    Log    Cycle réversible sur « ${appli}[titre] » (${appli}[intent]) : accueil ${volume_avant} tuiles, ${volume_pendant} après épinglage, retour à ${intents_apres}    console=True
    [Teardown]    Nettoyer L Epinglage Et Diagnostiquer    ${FLP_TERME_EPINGLAGE}

La deconnexion demande confirmation et atterrit sur la page de sortie
    [Documentation]    Scénario 19 du plan, et **dernier de la campagne** : il
    ...    ferme la session.
    ...
    ...    Le dialogue de confirmation se distingue STRUCTURELLEMENT du dialogue
    ...    de refus du scénario 16 : deux boutons et un état qui n'est pas
    ...    l'erreur. La confirmation se fait par la POSITION du bouton, et
    ...    l'atterrissage se constate sur le CHEMIN de l'URL de déconnexion plus
    ...    l'absence de runtime, jamais sur le texte d'adieu.
    [Setup]    Revenir A L Accueil
    ${dialogue}=    Se Deconnecter Du Launchpad
    Should Not Be Equal    ${dialogue}[state]    ${ABAP_FLP_ERROR_STATE}
    ...    msg=La confirmation de déconnexion se présente en état d'erreur : elle ne se distingue plus d'un refus.
    Should Be Equal As Integers    ${dialogue}[buttons]    2
    ...    msg=La confirmation de déconnexion porte ${dialogue}[buttons] bouton(s), attendu 2.
    Confirmer La Deconnexion
    La Session Est Fermee
    Log    Session fermée sur la page de déconnexion du serveur, aucun runtime UI5 restant.    console=True
