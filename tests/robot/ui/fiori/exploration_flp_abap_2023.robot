*** Settings ***
Documentation       Exploration du launchpad Fiori hébergé par un serveur ABAP (ABAP Platform 2023)
...                 Spec: specs/exploration-flp-abap-2023.md (sha256:65ea0409e86b, 2026-08-24)
...                 Generated from specs/exploration-flp-abap-2023.md by sap-generator: re-run the generator
...                 rather than hand-editing locators here
...
...                 Campagne jumelle de `exploration_flp_abap_a4h.robot`, sur un
...                 serveur ABAP d'une AUTRE release : ABAP Platform 2023
...                 servant SAPUI5 1.120, là où l'autre sert 1.71. Les deux
...                 suites partagent le page object
...                 `resources/page_objects/abap_flp.resource` ; **cette
...                 suite-ci ne contient que ce qui distingue sa cible**, en
...                 variables, et c'est sa raison d'être : mesurer ce qui, dans
...                 le premier plan, tenait à la RELEASE et non au produit.
...
...                 Ce que la release a déplacé, et que cette suite surcharge :
...                 l'ancre de la zone utilisateur et de son popover, celle du
...                 dialogue « à propos », la position d'acquittement d'un
...                 REFUS de navigation (première position sur 1.71, dernière
...                 ici, la première y copiant le message technique sans rien
...                 fermer), la source de la clé technique d'une rubrique de
...                 paramètres, la lecture des tuiles de l'accueil, le budget de
...                 retour au repos et les familles d'erreurs console. Aucune
...                 condition de version nulle part : la release entre par les
...                 variables.
...
...                 Campagne **pilotée par la découverte** : catalogue, groupes,
...                 tuiles et applications parcourues sont ceux que le système
...                 déclare le jour du run. Les deux intents cités en variables
...                 (navigation arrière) sont VÉRIFIÉS au catalogue avant usage,
...                 jamais présumés.
...
...                 **Lecture seule par défaut.** Aucune écriture métier nulle
...                 part. Le mode édition de l'accueil est entré pour être quitté
...                 sans rien déplacer, et le test le CONSTATE en comparant les
...                 groupes avant et après ; le dialogue des paramètres est
...                 refermé par annuler, jamais par enregistrer. Effet de bord
...                 assumé et consigné : naviguer écrit l'historique d'activité
...                 de l'utilisateur côté serveur.
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
...                 Prérequis : le serveur ABAP répond en **HTTPS sur SON port**.
...                 La voie HTTP redirige vers un nom d'hôte virtuel que
...                 plusieurs conteneurs ABAP d'un même poste annoncent, et mène
...                 alors au launchpad de l'AUTRE système, avec une perception
...                 parfaitement cohérente et la mauvaise cible.
...                 Exécution ::
...
...                 |  robot --pythonpath src
...                 |  ...   -v ABAP_FLP_URL:https://<hote>:<port>/sap/bc/ui2/flp?sap-client=001
...                 |  ...   -v ABAP_FLP_USER:<utilisateur>
...                 |  ...   -v "ABAP_FLP_PASSWORD: Secret:<motdepasse>"
...                 |  ...   --outputdir results/flp2023
...                 |  ...   tests/robot/ui/fiori/exploration_flp_abap_2023.robot

Resource            ../../../../resources/page_objects/abap_flp.resource

Suite Setup         Ouvrir Le Launchpad ABAP
Suite Teardown      Fermer Le Launchpad ABAP
Test Teardown       Journaliser Le Diagnostic Fiori En Cas D Echec

Test Tags           fiori    flp    abap    abap2023    live


*** Variables ***
# --- Ce que la release 1.120 a déplacé --------------------------------------
# Surcharges du page object, dont les valeurs par défaut sont celles de la
# release 1.71. Chacune a été relevée LIVE le 2026-08-24 sur cette cible.
${ABAP_FLP_ME_AREA_BUTTON}          userActionsMenuHeaderButton
${ABAP_FLP_ME_AREA_POPOVER}         sapUshellUserActionsMenuPopover
${ABAP_FLP_ABOUT_DIALOG}            aboutDialogFragment--aboutDialog
# Acquittement d'un REFUS de navigation : DERNIÈRE position. La première y est
# une copie du message technique, qui laisse le dialogue ouvert (payé live sur
# cette cible par un échec après 20 s d'attente d'une fermeture qui ne venait
# pas). La confirmation de déconnexion, elle, garde son OK en tête.
${ABAP_FLP_ERROR_CONFIRM_POSITION}    ${1}
# La clé technique d'une rubrique de paramètres a quitté l'identifiant, qui est
# désormais entièrement généré : elle vit dans le contexte de liaison.
${ABAP_FLP_RUBRIQUES_STRATEGIE}     Lire Les Rubriques Par Contexte De Liaison
# La tuile est rendue par un composant séparé : ni l'agrégation ni le contexte
# de liaison ne portent plus son titre ni sa cible. Lecture par containment DOM.
${ABAP_FLP_TUILES_STRATEGIE}        Lire Les Tuiles Par Containment
# Budget de retour au repos : mesuré jusqu'à 55 s sur une navigation arrière de
# ce système, quand la bibliothèque en accorde 15 par défaut.
${ABAP_FLP_IDLE_TIMEOUT}            180s
# Familles d'erreurs console propres à cette cible. Les dépréciations sont
# émises par le shell de SAP lui-même (le runtime 1.71 n'en émettait aucune,
# d'où des familles vides dans le page object) et le message de session est un
# réglage du shell journalisé au niveau erreur.
@{ABAP_FLP_MARQUEURS_DEPRECATION}    [FUTURE FATAL]    is deprecated
@{ABAP_FLP_MARQUEURS_SESSION}       SessionHandler

# --- Valeurs relevées LIVE sur CE système ------------------------------------
${FLP_VERSION_ATTENDUE}             1.120    # ligne du runtime SAPUI5 servi
${FLP_PRODUIT_ATTENDU}              ABAP PLATFORM 2023    # nommé par le dialogue « à propos »
# Plancher de contrôles de l'accueil : mesuré entre 134 et 169 sur cette cible,
# là où la campagne 1.71 en mesurait plus de 180. Un plancher gravé pour l'une
# rendrait l'autre rouge sur un système parfaitement sain.
${FLP_CONTROLES_MINIMUM}            ${100}
${FLP_LANGUES_ATTENDUES}            ${2}    # DE et EN, seules langues installées
# Éléments de barre shell RENDUS : la zone utilisateur n'en est plus un sur
# cette release (c'est un avatar), d'où un de moins qu'en 1.71 des deux côtés.
${FLP_HEAD_ITEMS_ACCUEIL}           ${1}
${FLP_HEAD_ITEMS_APPLICATION}       ${2}
# Termes de recherche PARTIELS à dessein : le titre exact d'une application fait
# naviguer le shell directement vers elle au lieu d'ouvrir les résultats.
${FLP_TERME_RECHERCHE}              Manage
${FLP_TERME_APPFINDER}              Shop
# Terme du cycle d'épinglage : il doit laisser UNE seule vignette, et viser une
# application ABSENTE de l'accueil, sinon le cycle ne prouverait rien. Sur cette
# cible l'accueil ne rend qu'une tuile, donc le terme de filtrage convient aussi
# ici ; ce n'est pas le cas de la cible 1.71, d'où deux variables.
${FLP_TERME_EPINGLAGE}              Shop
# Utilisateur volontairement valide, mot de passe volontairement faux : une
# SEULE tentative dans la campagne, pour ne pas approcher le verrouillage du
# compte (le seuil est un réglage serveur, non observé).
${FLP_MOT_DE_PASSE_FAUX}            mot_de_passe_volontairement_faux
# Les deux applications de la navigation arrière. Elles sont citées ici et non
# découvertes, parce que l'accueil de cette cible ne rend QU'UNE tuile et que
# son compteur n'est jamais résolu : la stratégie « prendre les premières tuiles
# saines » de la campagne 1.71 ne trouve rien ici. Le test les VÉRIFIE au
# catalogue et au service de résolution avant de les ouvrir : ce sont des
# candidates, pas des postulats.
${FLP_APP_PRINCIPALE}               Repository-manage
${FLP_APP_SECONDE}                  EPMProduct-shop
# Écart de périmètre PUBLIÉ par le scénario de résolvabilité et consommé par
# celui du refus d'une application assignée mais non déployée. Vide par défaut :
# sur un système où tout le catalogue est ouvrable, ce dernier est SAUTÉ, et non
# rouge, ce qui suppose que la variable existe avant d'être renseignée.
@{FLP_INTENTS_NON_OUVRABLES}        @{EMPTY}


*** Test Cases ***
La page de connexion est bien celle du serveur ABAP 2023 vise
    [Documentation]    Scénario 1 du plan. Avant d'accorder du crédit à quoi que
    ...    ce soit, constater que l'URL réellement atteinte est celle demandée,
    ...    sur l'hôte demandé : les deux conteneurs ABAP d'un même poste servent
    ...    le même chemin ICF, avec le même formulaire, dans la même langue, et
    ...    la voie HTTP de l'un redirige vers l'autre. Sans ce contrôle, toute
    ...    la campagne serait verte sur le mauvais système.
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
    ...    aucun runtime. UNE seule tentative dans toute la campagne, et la
    ...    connexion réussie du test suivant remet le compteur à zéro.
    Tenter Une Connexion    ${ABAP_FLP_USER}    ${FLP_MOT_DE_PASSE_FAUX}
    La Connexion Est Refusee
    Log    Refus constaté sur la page de connexion, aucun runtime chargé.    console=True

La connexion nominale rend un shell FLP 1120 identifiable
    [Documentation]    Scénario 3 du plan. Le shell doit s'annoncer pour ce
    ...    qu'il est : un runtime UI5 de la ligne attendue, des contrôles
    ...    réellement construits, aucun hôte Web Components et surtout **aucune
    ...    iframe**, ce qui distingue structurellement ce launchpad d'un cFLP,
    ...    exactement comme sur la cible 1.71. L'identité de session est lue au
    ...    conteneur ushell, seule source qui dise ce que le SERVEUR a ouvert.
    ...
    ...    Le thème est journalisé, jamais asserté : c'est un réglage.
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

Le dialogue a propos prouve la release du systeme
    [Documentation]    Scénario 4 du plan. Le scénario 1 prouve qu'on a parlé au
    ...    bon HÔTE ; celui-ci prouve qu'on a parlé à la bonne RELEASE. C'est le
    ...    seul endroit de l'interface qui nomme le produit ABAP, donc
    ...    l'empreinte de cible qui distingue ce système de son voisin 1909.
    ...
    ...    La version SAPUI5 annoncée par le dialogue et celle du runtime chargé
    ...    ne coïncident pas au patch près (l'une est la distribution, l'autre le
    ...    runtime) : seule la ligne majeure/mineure est une assertion tenable.
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

Le catalogue est inventorie par le service et les deux services concordent
    [Documentation]    Scénario 5 du plan. Le catalogue est lu au SERVICE, qui
    ...    répond ce que l'utilisateur a le droit d'ouvrir, et non à l'écran, où
    ...    le rendu est paresseux (54 vignettes pour 67 tuiles déclarées) et
    ...    donnerait un nombre faux.
    ...
    ...    Cette release apporte un second service d'inventaire, absent de la
    ...    cible 1.71 : quand il répond, les deux ensembles d'intents sont
    ...    comparés dans les DEUX sens. Sa présence est SONDÉE et non déduite de
    ...    la version, et son absence réduit le scénario à la voie universelle
    ...    en le disant, plutôt que d'échouer.
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
    ${recherchable}=    Le Service De Contenu Recherchable Est Disponible
    IF    ${recherchable}
        ${applications}=    Inventorier Les Applications Recherchables
        ${intents_bis}=    Lire Les Intents Des Applications Recherchables    ${applications}
        ${absents_du_second}=    Evaluate    sorted(set($intents) - set($intents_bis))
        ${absents_du_premier}=    Evaluate    sorted(set($intents_bis) - set($intents))
        Should Be Empty    ${absents_du_second}
        ...    msg=Des intents du catalogue sont inconnus du service de contenu recherchable : ${absents_du_second}
        Should Be Empty    ${absents_du_premier}
        ...    msg=Le service de contenu recherchable déclare des intents absents du catalogue : ${absents_du_premier}
        Log    Les deux services concordent : ${{len($intents)}} intents des deux côtés, pour ${tuiles} tuiles et ${{len($applications)}} applications    console=True
    ELSE
        Log    Service de contenu recherchable absent de cette cible : inventaire réduit à la voie universelle.    console=True
    END
    ${objets}=    Evaluate    len({i.split('-')[0] for i in $intents})
    Log    Catalogue : ${{len($catalogues)}} catalogues, ${tuiles} tuiles, ${{len($intents)}} intents uniques, ${objets} objets sémantiques    console=True

Toute application offerte au catalogue est ouvrable ou l ecart est nomme
    [Documentation]    Scénario 6 du plan. Les intents du catalogue sont soumis
    ...    au service de résolution de navigation, **plus un intent fabriqué**.
    ...    L'intent fabriqué doit être déclaré non résolvable : sans cette
    ...    contre-preuve, un service qui répondrait « oui » à tout rendrait le
    ...    test vert et vide.
    ...
    ...    Les intents assignés mais non résolvables sont RAPPORTÉS, pas mis en
    ...    échec : ils décrivent un système de démonstration dont tous les
    ...    composants ne sont pas déployés. L'écart relevé est publié pour le
    ...    scénario du refus d'une application assignée mais non déployée.
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
    Set Suite Variable    ${FLP_INTENTS_NON_OUVRABLES}    ${ecarts}
    Log    Résolvabilité : ${{len($bilan['resolvables'])}} intents ouvrables sur ${{len($intents)}} assignés. Assignés mais NON ouvrables : ${ecarts}    console=True

L accueil rend ses groupes et sa tuile compteur compris
    [Documentation]    Scénario 7 du plan. Les groupes sont lus au service :
    ...    leur titre rendu diffère de celui que retourne le service, et les
    ...    deux sont traduits, donc l'ancre est l'identifiant technique. Un
    ...    groupe peut être VIDE, et c'est le cas ici.
    ...
    ...    Un compteur non résolu est RAPPORTÉ nommément, jamais mis en échec :
    ...    c'est l'état d'un composant du système, pas un défaut du test. Sur
    ...    cette cible AUCUN compteur n'est résolu, et le fournisseur de données
    ...    échoue en silence, sans la moindre erreur console : un test qui
    ...    déduirait l'état des tuiles du journal serait faux.
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
    ${volumes}=    Evaluate    sum(g['tuiles'] for g in $groupes)
    Should Be True    ${volumes} >= ${{len($tuiles)}}
    ...    msg=Les groupes déclarent ${volumes} tuiles pour ${{len($tuiles)}} rendues : l'accueil rend plus que ce que le service déclare.
    ${compteurs}=    Separer Les Compteurs Non Resolus    ${tuiles}
    ${sans_compteur}=    Evaluate    [t['intent'] for t in $compteurs['non_resolus']]
    Log    Accueil : ${{len($groupes)}} groupes pour ${volumes} tuiles déclarées, ${{len($tuiles)}} rendues, ${{len($compteurs['numeriques'])}} compteurs résolus. Fournisseur de données non résolu pour : ${sans_compteur}    console=True

Ouvrir une application par sa tuile et par son intent mene au meme endroit
    [Documentation]    Scénario 8 du plan. Les deux voies d'ouverture doivent
    ...    mener au même endroit : celle de l'utilisateur (cliquer la tuile) et
    ...    celle des tests (naviguer par intent). L'application vient de la
    ...    DÉCOUVERTE : c'est la tuile que l'accueil rend ce jour-là, et son
    ...    titre est celui relevé dans le MÊME run, jamais une constante, parce
    ...    qu'il est traduit.
    ...
    ...    Le témoin d'ouverture est le conteneur d'application dérivé de
    ...    l'intent : ni généré ni traduit, il remplace ici le test d'iframe des
    ...    launchpads hébergés dans le cloud.
    [Setup]    Revenir A L Accueil
    ${tuiles}=    Lire Les Tuiles De L Accueil
    ${cible}=    Set Variable    ${tuiles}[0]
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

La navigation arriere du navigateur ramene a l application precedente
    [Documentation]    Scénario 9 du plan. Un seul conteneur d'application
    ...    existe à la fois : passer d'une application à l'autre détruit la
    ...    précédente, et la navigation arrière la reconstruit.
    ...
    ...    Les deux applications viennent du CATALOGUE et non de l'accueil, qui
    ...    ne rend qu'une tuile sur cette cible. Elles sont vérifiées assignées
    ...    ET résolvables avant d'être ouvertes : citer un intent sans le
    ...    vérifier ferait échouer le test sur un système où il n'est pas
    ...    déployé, ce qui accuserait la navigation d'un défaut de périmètre.
    ...
    ...    Le budget de retour au repos est celui de la cible : la reprise
    ...    relance le chargement de données de l'application reconstruite, et le
    ...    budget par défaut échouerait en annonçant une requête en vol.
    [Setup]    Revenir A L Accueil
    ${catalogues}=    Inventorier Les Catalogues
    ${intents}=    Lire Les Intents Du Catalogue    ${catalogues}
    ${couple}=    Create List    ${FLP_APP_PRINCIPALE}    ${FLP_APP_SECONDE}
    FOR    ${intent}    IN    @{couple}
        Should Contain    ${intents}    ${intent}
        ...    msg=L'application « ${intent} » n'est pas au catalogue de cet utilisateur : la campagne ne peut pas l'ouvrir.
    END
    ${resolutions}=    Les Intents Sont Ils Resolvables    ${couple}
    ${bilan}=    Separer Les Intents Non Resolvables    ${resolutions}
    Should Be Empty    ${bilan}[non_resolvables]
    ...    msg=Les applications choisies pour la navigation arrière ne sont pas ouvrables sur ce système : ${bilan}[non_resolvables]
    Ouvrir L Application Par Intent    ${FLP_APP_PRINCIPALE}
    Ouvrir L Application Par Intent    ${FLP_APP_SECONDE}
    Aucune Application N Est Ouverte    ${FLP_APP_PRINCIPALE}
    Revenir En Arriere Dans Le Shell    ${FLP_APP_PRINCIPALE}    ${ABAP_FLP_IDLE_TIMEOUT}
    L Application Ouverte Est    ${FLP_APP_PRINCIPALE}
    Aucune Application N Est Ouverte    ${FLP_APP_SECONDE}
    Log    Retour arrière : « ${FLP_APP_SECONDE} » détruite, « ${FLP_APP_PRINCIPALE} » reconstruite    console=True

La barre shell et la zone utilisateur dependent de l endroit
    [Documentation]    Scénario 10 du plan. Deux relevés, un sur l'accueil et un
    ...    dans une application, puis leur ÉCART.
    ...
    ...    Le nombre d'éléments de barre shell rendus est propre à la cible (la
    ...    zone utilisateur n'en est plus un sur cette release) : il vaut donc
    ...    une variable, et ce qui reste universel est qu'il AUGMENTE dans une
    ...    application, le shell y ajoutant le retour.
    ...
    ...    Les entrées de la zone utilisateur sont identifiées par le SUFFIXE
    ...    technique de leur action, jamais par leur libellé (traduit) ni par
    ...    leur identifiant complet (qui contient leur POSITION, laquelle change
    ...    d'un endroit à l'autre).
    [Setup]    Revenir A L Accueil
    ${head_accueil}=    Compter Les Elements De La Barre Shell
    Should Be Equal As Integers    ${head_accueil}    ${FLP_HEAD_ITEMS_ACCUEIL}
    ...    msg=${head_accueil} élément(s) de barre shell rendus à l'accueil, attendu ${FLP_HEAD_ITEMS_ACCUEIL} sur cette cible.
    Ouvrir La Zone Utilisateur
    ${sur_l_accueil}=    Lire Les Entrees De La Zone Utilisateur
    Fermer La Zone Utilisateur
    ${tuiles}=    Lire Les Tuiles De L Accueil
    Ouvrir L Application Par Intent    ${tuiles}[0][intent]
    ${head_application}=    Compter Les Elements De La Barre Shell
    Should Be Equal As Integers    ${head_application}    ${FLP_HEAD_ITEMS_APPLICATION}
    ...    msg=${head_application} élément(s) de barre shell rendus dans une application, attendu ${FLP_HEAD_ITEMS_APPLICATION} sur cette cible.
    Should Be True    ${head_application} > ${head_accueil}
    ...    msg=La barre shell ne gagne aucun élément dans une application (${head_application} contre ${head_accueil}).
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

Le panneau des activites recentes s ouvre et se referme
    [Documentation]    Scénario 11 du plan. Le panneau s'ouvre par-dessus
    ...    l'écran courant SANS naviguer : l'URL ne doit pas bouger, c'est ce
    ...    qui le distingue d'une page du shell.
    ...
    ...    Le CONTENU de la liste ne s'asserte pas : il dépend de l'historique
    ...    de l'utilisateur, y compris de sessions antérieures. Seule sa
    ...    présence en est une, et elle vaut constat d'un effet de bord : cette
    ...    campagne en lecture seule écrit tout de même cet historique en
    ...    naviguant.
    [Setup]    Revenir A L Accueil
    ${avant}=    Lire Le Fragment Courant
    Ouvrir Les Activites Recentes
    ${entrees}=    Compter Les Activites Recentes
    Should Be True    ${entrees} > 0
    ...    msg=Le panneau des activités récentes ne rend aucune entrée alors que la campagne a déjà ouvert des applications.
    ${pendant}=    Lire Le Fragment Courant
    Should Be Equal    ${pendant}    ${avant}
    ...    msg=L'ouverture du panneau des activités a navigué (${avant} puis ${pendant}) : ce devrait être un panneau, pas une page.
    Fermer Les Activites Recentes
    Log    Activités récentes : ${entrees} entrées, fragment inchangé (${avant})    console=True

Le dialogue des parametres s ouvre et se referme sans rien modifier
    [Documentation]    Scénario 12 du plan. Les rubriques sont relevées par leur
    ...    clé technique, jamais par leur libellé.
    ...
    ...    Sur cette release la clé a QUITTÉ l'identifiant, entièrement généré :
    ...    elle ne vit plus que dans le contexte de liaison de l'entrée. C'est
    ...    la stratégie de lecture surchargée par cette suite, et le résultat le
    ...    plus utile de la campagne pour le page object partagé.
    ...
    ...    Le dialogue est refermé par ANNULER : son bouton d'enregistrement
    ...    écrit une personnalisation utilisateur côté serveur.
    [Setup]    Revenir A L Accueil
    Ouvrir Les Parametres Utilisateur
    ${rubriques}=    Lire Les Rubriques De Parametres
    Should Not Be Empty    ${rubriques}
    ...    msg=La liste maître des paramètres ne rend aucune rubrique, ou leur clé technique n'a pas été trouvée là où cette cible la range.
    Annuler Les Parametres Utilisateur
    Aucun Dialogue N Est Ouvert
    Log    Rubriques de paramètres rendues : ${rubriques}    console=True

L App Finder ouvre le catalogue et sait le filtrer
    [Documentation]    Scénario 13 du plan. L'App Finder est une page du SHELL,
    ...    pas une application : son fragment est celui du shell. Sa liste de
    ...    sources vaut le nombre de catalogues assignés plus l'entrée
    ...    « toutes ».
    ...
    ...    Le nombre d'applications rendues n'est comparé qu'à LUI-MÊME avant et
    ...    après filtrage : le rendu est paresseux et ne montre jamais tout le
    ...    catalogue.
    ...
    ...    Candidat d'écriture NON exécuté : chaque vignette porte un bouton
    ...    d'épinglage qui ajoute l'application à un groupe de l'accueil.
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
    [Documentation]    Scénario 14 du plan. Entrer puis sortir du mode édition
    ...    sans rien déplacer ne doit modifier aucune personnalisation : le test
    ...    le CONSTATE en comparant les groupes et leur volume avant et après,
    ...    au lieu de le supposer.
    ...
    ...    Le témoin d'état est le bouton de fin d'édition, seul valable sur les
    ...    DEUX releases : la barre de pied de page, elle, est rendue ici et ne
    ...    l'était pas sur la cible 1.71.
    [Setup]    Revenir A L Accueil
    ${avant}=    Inventorier Les Groupes De L Accueil
    Entrer En Mode Edition De L Accueil
    Le Mode Edition Est Actif
    Quitter Le Mode Edition De L Accueil
    ${apres}=    Inventorier Les Groupes De L Accueil
    Should Be Equal    ${apres}    ${avant}
    ...    msg=Les groupes de l'accueil ont changé après un simple aller-retour en mode édition : ${avant} puis ${apres}.
    Log    Mode édition entré et quitté, groupes inchangés : ${apres}    console=True

Le menu toutes mes applications liste les sources et une partie du catalogue
    [Documentation]    Scénario 15 du plan. Le popover du titre de shell propose
    ...    une entrée par catalogue assigné plus une.
    ...
    ...    Le nombre d'entrées rendues se compare au volume total en INÉGALITÉ,
    ...    jamais en égalité : le menu ne rend que la source sélectionnée.
    ...
    ...    La liste des sources se remplit progressivement, d'où l'attente : une
    ...    lecture immédiate en a rendu deux au premier run, pour trois une
    ...    seconde plus tard.
    [Setup]    Revenir A L Accueil
    ${catalogues}=    Inventorier Les Catalogues
    ${total}=    Compter Les Tuiles Du Catalogue    ${catalogues}
    Ouvrir Le Menu Toutes Mes Applications
    ${sources}=    Attendre Les Sources Du Menu Toutes Mes Applications    ${{len($catalogues) + 1}}
    Length Should Be    ${sources}    ${{len($catalogues) + 1}}
    ...    msg=Le menu propose ${{len($sources)}} sources pour ${{len($catalogues)}} catalogues assignés (attendu : un de plus).
    ${entrees}=    Compter Les Entrees Du Menu Toutes Mes Applications
    Should Be True    ${entrees} > 0
    ...    msg=Le menu n'affiche aucune application.
    Should Be True    ${entrees} <= ${total}
    ...    msg=Le menu rend ${entrees} entrées pour ${total} tuiles déclarées au catalogue.
    Fermer Le Popover Courant
    Log    Menu « toutes mes applications » : ${{len($sources)}} sources, ${entrees} entrées rendues sur ${total} tuiles de catalogue    console=True

La recherche du shell trouve les applications de l utilisateur
    [Documentation]    Scénario 16 du plan. La recherche du shell fonctionne
    ...    **bien que** la recherche d'entreprise ne soit pas déployée sur cette
    ...    cible (404 en console au chargement) : elle se rabat sur le catalogue
    ...    d'applications local. Un test qui conclurait « recherche cassée »
    ...    depuis les erreurs console serait faux.
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

Un intent inexistant est refuse proprement sans quitter l ecran courant
    [Documentation]    Scénario 17 du plan. Le refus doit être propre : un
    ...    dialogue en état d'ERREUR s'ouvre, le fragment ne bouge pas et
    ...    l'application ouverte survit. Après acquittement, l'état est
    ...    exactement celui du relevé initial.
    ...
    ...    L'acquittement se fait par la POSITION du bouton, et cette position
    ...    n'est PAS celle d'une confirmation sur cette release : la première y
    ...    copie le message technique et laisse le dialogue ouvert. C'est
    ...    l'écart le plus piégeux entre les deux cibles, parce qu'il rend un
    ...    test vert ailleurs et rouge ici sans changer une ligne de code.
    [Setup]    Revenir A L Accueil
    ${tuiles}=    Lire Les Tuiles De L Accueil
    ${cible}=    Set Variable    ${tuiles}[0]
    Ouvrir L Application Par Intent    ${cible}[intent]
    ${fragment_avant}=    Lire Le Fragment Courant
    Demander Un Intent Inconnu
    ${dialogue}=    Le Shell Refuse La Navigation
    Should Be Equal    ${dialogue}[state]    ${ABAP_FLP_ERROR_STATE}
    ${fragment_pendant}=    Lire Le Fragment Courant
    Should Be Equal    ${fragment_pendant}    ${fragment_avant}
    ...    msg=Le fragment a changé sur un intent refusé : ${fragment_pendant} au lieu de ${fragment_avant}.
    L Application Ouverte Est    ${cible}[intent]
    Acquitter Le Dialogue D Erreur
    Aucun Dialogue N Est Ouvert
    Le Fragment Courant Commence Par    ${fragment_avant}
    L Application Ouverte Est    ${cible}[intent]
    Log    Refus de « ${ABAP_FLP_INTENT_INCONNU} » : dialogue en état ${dialogue}[state], ${dialogue}[buttons] boutons, écran intact    console=True

Un fragment d URL malforme est refuse de la meme facon
    [Documentation]    Scénario 18 du plan. Un fragment sans partie action est
    ...    refusé comme un intent inconnu, et le shell revient de lui-même au
    ...    fragment de l'application ouverte.
    ...
    ...    Mesuré live : les dialogues de refus sont structurellement
    ...    identiques d'un cas à l'autre. Ne pas chercher à les distinguer à
    ...    l'écran, le test ne le fait donc pas.
    [Setup]    Revenir A L Accueil
    ${tuiles}=    Lire Les Tuiles De L Accueil
    ${cible}=    Set Variable    ${tuiles}[0]
    Ouvrir L Application Par Intent    ${cible}[intent]
    ${fragment_avant}=    Lire Le Fragment Courant
    Forcer Un Fragment Malforme
    ${dialogue}=    Le Shell Refuse La Navigation
    Should Be Equal    ${dialogue}[state]    ${ABAP_FLP_ERROR_STATE}
    Should Be Equal As Integers    ${dialogue}[buttons]    2
    ...    msg=Le dialogue de refus porte ${dialogue}[buttons] bouton(s) : la position d'acquittement de cette cible suppose une structure à deux boutons.
    Acquitter Le Dialogue D Erreur
    Le Fragment Courant Commence Par    ${fragment_avant}
    L Application Ouverte Est    ${cible}[intent]
    Log    Fragment « ${ABAP_FLP_FRAGMENT_MALFORME} » refusé en état ${dialogue}[state], retour sur ${fragment_avant}    console=True

Une application assignee mais non ouvrable produit le meme refus
    [Documentation]    Scénario 19 du plan. Ce que ce test établit : c'est la
    ...    préflight de résolvabilité, sans navigation, qui distingue « assigné
    ...    mais non déployé » de « inconnu ». L'écran, lui, ne le fait pas : le
    ...    dialogue est indiscernable de celui d'un intent fabriqué.
    ...
    ...    SAUTÉ, et non rouge, sur un système où tout le catalogue est
    ...    ouvrable : l'écart vient du périmètre déployé, pas du launchpad.
    [Setup]    Revenir A L Accueil
    Skip If    not ${FLP_INTENTS_NON_OUVRABLES}
    ...    Aucun intent assigné et non résolvable sur ce système : il n'y a rien à refuser.
    ${tuiles}=    Lire Les Tuiles De L Accueil
    ${cible}=    Set Variable    ${tuiles}[0]
    Ouvrir L Application Par Intent    ${cible}[intent]
    ${fragment_avant}=    Lire Le Fragment Courant
    ${non_ouvrable}=    Set Variable    ${FLP_INTENTS_NON_OUVRABLES}[0]
    Demander Un Intent Inconnu    ${non_ouvrable}
    ${dialogue}=    Le Shell Refuse La Navigation
    Should Be Equal    ${dialogue}[state]    ${ABAP_FLP_ERROR_STATE}
    Acquitter Le Dialogue D Erreur
    Le Fragment Courant Commence Par    ${fragment_avant}
    L Application Ouverte Est    ${cible}[intent]
    Log    « ${non_ouvrable} » est assigné au catalogue et refusé à l'ouverture, comme un intent inconnu : l'écran ne distingue pas les deux cas    console=True

Aucune exception JavaScript non rattrapee sur un chargement propre
    [Documentation]    Scénario 20 du plan. Deux assertions dures et deux
    ...    seulement : zéro exception JavaScript non rattrapée, et un tri
    ...    EXHAUSTIF des erreurs console. On classe, on ne compte pas : une
    ...    erreur tracée à un composant non déployé n'est pas un défaut, et un
    ...    test qui compte devient rouge à la première ressource optionnelle
    ...    absente.
    ...
    ...    Deux familles n'existaient pas sur la cible 1.71 : les dépréciations,
    ...    émises par le shell de SAP lui-même sur cette release, et le message
    ...    de configuration de session. Elles sont déclarées ici, donc classées,
    ...    donc visibles, et non masquées.
    ...
    ...    La mesure est prise sur un CHARGEMENT PROPRE, journal purgé au
    ...    préalable : l'exploration pollue sa propre mesure.
    Recharger L Accueil Proprement
    ${bilan}=    Classer Les Erreurs Du Shell
    Should Be Equal As Integers    ${bilan}[erreurs_de_page]    0
    ...    msg=Le shell a émis ${bilan}[erreurs_de_page] exception(s) JavaScript non rattrapée(s).
    Should Be Equal As Integers    ${bilan}[classees]    ${bilan}[erreurs_console]
    ...    msg=Le tri des erreurs console n'est pas exhaustif : ${bilan}[classees] classées sur ${bilan}[erreurs_console].
    Should Be Equal As Integers    ${bilan}[autres]    0
    ...    msg=Erreur console inattendue au chargement propre : ${bilan}[premiere_autre]
    Log    Chargement propre : ${bilan}[erreurs_console] erreurs console, dont ${bilan}[deprecation] dépréciation(s) du shell SAP, ${bilan}[recherche] de recherche d'entreprise non déployée, ${bilan}[session] de configuration de session et ${bilan}[tuile] de fournisseur de tuile ; zéro exception non rattrapée    console=True

Epingler puis depingler une application rend l accueil a son etat initial
    [Documentation]    Scénario 22 du plan, et **le seul qui écrit** : le cycle
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
    ...    visée est vérifiée ABSENTE avant l'épinglage (sans quoi le scénario
    ...    ne prouverait rien), et la restauration est CONSTATÉE sur la
    ...    disparition de l'intent épinglé, pas sur un compte revenu à sa valeur
    ...    de départ, qui ne prouverait qu'une arithmétique.
    ...
    ...    Deux faits mesurés live et encodés dans le page object : le service
    ...    de l'accueil sert un modèle PÉRIMÉ tant qu'on est sur l'App Finder
    ...    (le constat se prend après retour à l'accueil), et la propriété du
    ...    bouton d'épinglage retarde d'un cycle (l'état qui fait foi est celui
    ...    des cases du popover).
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
    [Documentation]    Scénario 21 du plan, et **dernier de la campagne** : il
    ...    ferme la session.
    ...
    ...    Le dialogue de confirmation se distingue STRUCTURELLEMENT du dialogue
    ...    de refus : deux boutons et un état qui n'est pas l'erreur. Sa
    ...    confirmation se fait par la position d'acquittement générale, celle
    ...    qui n'a PAS bougé d'une release à l'autre, contrairement à celle d'un
    ...    refus.
    ...
    ...    L'atterrissage se constate sur le CHEMIN de l'URL de déconnexion plus
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
