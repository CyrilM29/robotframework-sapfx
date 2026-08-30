*** Settings ***
Documentation       Résilience de session et deep-links d'un launchpad Work Zone (BTP)
...                 Spec: specs/workzone-resilience-deeplinks.md (sha256:1454523a19d7, 2026-08-26)
...
...                 Campagne de la **résilience de session et des deep-links**
...                 d'un launchpad SAP Build Work Zone (cFLP sur BTP, derrière
...                 un tenant SAP Cloud Identity Services) : ce qui arrive
...                 AUTOUR d'une application ouverte. Trajet d'authentification
...                 et sort du fragment, accès direct par intent, rechargement,
...                 identifiant d'iframe, historique du navigateur, second
...                 onglet, perte de session, délais déclarés, navigation
...                 refusée.
...
...                 Ce que cette campagne établit, et qu'aucune fixture ne peut
...                 établir : le fragment d'URL est le SEUL porteur d'état de
...                 navigation de ce shell, il disparaît du document du
...                 fournisseur d'identité et réapparaît après le retour, ce qui
...                 est exactement ce qui rend un deep-link partageable ;
...                 l'identifiant de l'iframe applicative est un compteur qui
...                 repart de 1 à chaque chargement de document, donc jamais une
...                 ancre ; une navigation refusée ne détruit rien et ne restaure
...                 le fragment qu'à l'acquittement, lequel se fait par TYPE de
...                 bouton, la position 0 étant une action de copie ; et la
...                 session tient à six cookies de session, aucun jeton
...                 persistant.
...
...                 **Lecture seule** côté métier : aucune donnée n'est écrite.
...                 Deux tests manipulent l'état de session du NAVIGATEUR
...                 (contexte supplémentaire, vidage de cookies) : ils se jouent
...                 dans un contexte DÉDIÉ, jamais dans celui de la suite, et ce
...                 contexte est refermé par le teardown, y compris sur échec.
...
...                 Aucun localisateur ici (convention 1) : ils vivent dans
...                 `resources/page_objects/workzone_session.resource`,
...                 `resources/page_objects/workzone_shell_search.resource` et
...                 `resources/page_objects/workzone_launchpad.resource`.
...
...                 Aucun nombre de contrôles n'est gravé (relevés du même jour :
...                 139, 84, 52, 427, 485, 844 selon le CHEMIN d'arrivée) et
...                 aucun identifiant de conteneur non plus (cinq valeurs
...                 relevées pour la même application dans la même session) :
...                 chaque test ne compare que deux relevés qu'il a pris
...                 lui-même.
...
...                 Les tests sont AUTONOMES et rétablissent eux-mêmes leur état
...                 de départ, sauf le dernier, qui doit rester le dernier :
...                 l'expiration réelle peut tuer la session de la suite.
...
...                 Prérequis : un site Work Zone accessible, un utilisateur du
...                 tenant, et au moins une application publiée au catalogue.
...                 Exécution ::
...
...                 |  robot --pythonpath src
...                 |  ...   -v WORKZONE_SITE:<url du site>
...                 |  ...   -v WORKZONE_USER:<utilisateur>
...                 |  ...   -v "WORKZONE_PASSWORD: Secret:<motdepasse>"
...                 |  ...   --outputdir results/workzone
...                 |  ...   tests/robot/ui/fiori/resilience_deeplinks_workzone.robot
...
...                 La variante longue (expiration RÉELLE, plusieurs minutes
...                 d'inactivité stricte) est SAUTÉE tant que son accord
...                 explicite n'est pas donné : ajouter
...                 `-v WORKZONE_LONG_OPT_IN:yes`.

Resource            ../../../../resources/page_objects/workzone_session.resource

Suite Setup         Preparer La Campagne Resilience
Suite Teardown      Clore La Campagne Resilience
Test Teardown       Run Keywords    Journaliser Le Diagnostic Fiori En Cas D Echec
...                     AND    Sortir De L Application Si Necessaire
...                     AND    Nettoyer Les Contextes Et Onglets Supplementaires
...                     AND    Fermer Tout Popup Restant

Test Tags           fiori    workzone    btp    live


*** Test Cases ***
Sans session un acces direct passe par le fournisseur d identite et y perd son fragment
    [Documentation]    Scénario 1 du plan. Dans un contexte de navigateur NEUF,
    ...    sans aucun cookie, un accès direct au site avec un fragment d'intent
    ...    atterrit sur un hôte DIFFÉRENT de celui du site, au chemin
    ...    d'autorisation du fournisseur d'identité, sans aucun runtime UI5 et
    ...    avec un champ de mot de passe. Le fragment, lui, a disparu.
    ...
    ...    Le contrôle de l'hôte est le seul qui compte vraiment : sans lui, une
    ...    page de connexion servie par le site lui-même rendrait ce test
    ...    parfaitement vert. Le titre ne peut pas jouer ce rôle, il porte le
    ...    nom du produit du SITE.
    ...
    ...    Ce que ce scénario établit pour le suivant : le fragment n'est pas
    ...    transmis au serveur, donc le retrouver après authentification n'a
    ...    rien de trivial.
    ${contexte}=    Ouvrir Un Contexte Neuf
    Ouvrir Le Site Sur Un Intent    ${WORKZONE_APP_TEMOIN}[intent]
    ${adresse}=    Attendre Le Trajet De Reauthentification
    Should Be Empty    ${adresse}[fragment]
    ...    msg=Le document du fournisseur d'identité porte encore un fragment (${adresse}[fragment]) : le fragment aurait été transmis.
    ${champs}=    Compter Les Champs De Mot De Passe
    ${site}=    Lire L Hote Du Site
    Fermer Le Contexte Dedie    ${contexte}
    Log    Accès direct sans session : hôte atteint ${adresse}[hote] (le site est ${site}), chemin ${adresse}[chemin], fragment vide, aucun runtime UI5, ${champs} champ(s) de mot de passe    console=True

Apres authentification l acces direct retrouve sa cible sans passer par l accueil
    [Documentation]    Scénario 2 du plan. Le même trajet, poursuivi jusqu'à
    ...    l'authentification : le navigateur revient sur l'hôte du site, le
    ...    fragment demandé AVANT authentification est restauré, et
    ...    l'application est ouverte.
    ...
    ...    Le contrôle décisif est l'absence de la page d'accueil du launchpad :
    ...    sans lui, un shell qui atterrirait sur l'accueil puis ouvrirait
    ...    l'application produirait exactement le même fragment final. Le
    ...    scénario est rejoué depuis un contexte neuf plutôt que d'hériter de
    ...    l'état du précédent : chaque test rétablit son propre départ.
    ${contexte}=    Ouvrir Un Contexte Neuf
    Ouvrir Le Site Sur Un Intent    ${WORKZONE_APP_TEMOIN}[intent]
    Attendre Le Trajet De Reauthentification
    S Authentifier Sur Le Trajet Courant
    Attendre L Iframe De L Application
    ${adresse}=    Lire L Adresse Atteinte
    ${site}=    Lire L Hote Du Site
    Should Be Equal    ${adresse}[hote]    ${site}
    ...    msg=Le navigateur n'est pas revenu sur l'hôte du site après authentification : ${adresse}[hote]
    Should Be Equal    ${adresse}[fragment]    ${WORKZONE_APP_TEMOIN}[intent]
    ...    msg=Le fragment demandé avant authentification n'a pas été restauré : ${adresse}[fragment] au lieu de ${WORKZONE_APP_TEMOIN}[intent]
    ${accueil}=    La Page D Accueil Est Rendue
    Should Not Be True    ${accueil}
    ...    msg=La page d'accueil du launchpad a été rendue : le shell est passé par l'accueil avant d'ouvrir l'application, le deep-link n'est donc pas direct.
    ${iframes}=    Compter Les Iframes Applicatives
    Should Be Equal As Integers    ${iframes}    1
    ...    msg=L'accès direct a produit ${iframes} iframe(s) applicative(s) au lieu d'une.
    ${champs}=    Compter Les Champs De Mot De Passe
    Should Be Equal As Integers    ${champs}    0
    ...    msg=Un champ de mot de passe subsiste après authentification (${champs}) : le formulaire n'a pas été quitté.
    Fermer Le Contexte Dedie    ${contexte}
    Log    Accès direct après authentification : hôte ${adresse}[hote], fragment ${adresse}[fragment] restauré, accueil rendu=${accueil}, ${iframes} iframe applicative    console=True

Le rechargement ne redemande pas d authentification et reconstruit l application
    [Documentation]    Scénario 3 du plan. Application ouverte, le rechargement
    ...    du document conserve le fragment, ne redemande aucune
    ...    authentification, et l'application est RECONSTRUITE dans une nouvelle
    ...    iframe.
    ...
    ...    Le piège que ce test encode : le rechargement rend la main bien avant
    ...    que l'application ait démarré. Le témoin de reconstruction est le
    ...    premier contrôle construit DANS la frame, jamais la seule présence de
    ...    l'iframe, et le comptage n'est comparé à aucun plancher, seulement à
    ...    zéro.
    Revenir A L Accueil Du Launchpad
    Ouvrir L Application Par Intent    ${WORKZONE_APP_TEMOIN}[intent]
    ${fragment_avant}=    Lire Le Fragment Courant
    ${iframe_avant}=    Lire L Identifiant De L Iframe Applicative
    ${adresse_avant}=    Lire L Adresse Atteinte
    Recharger Le Launchpad
    ${champs}=    Compter Les Champs De Mot De Passe
    ${adresse_apres}=    Lire L Adresse Atteinte
    Should Be Equal As Integers    ${champs}    0
    ...    msg=Le rechargement a fait apparaître ${champs} champ(s) de mot de passe : la session n'a pas survécu.
    Should Be Equal    ${adresse_apres}[hote]    ${adresse_avant}[hote]
    ...    msg=Le rechargement a changé d'hôte (${adresse_avant}[hote] avant, ${adresse_apres}[hote] après).
    ${controles}=    Attendre La Reconstruction De L Application
    ${fragment_apres}=    Lire Le Fragment Courant
    ${iframe_apres}=    Lire L Identifiant De L Iframe Applicative
    Should Be Equal    ${fragment_apres}    ${fragment_avant}
    ...    msg=Le fragment n'a pas survécu au rechargement (${fragment_avant} avant, ${fragment_apres} après).
    Should Be True    ${controles} > 0
    ...    msg=L'application n'a reconstruit aucun contrôle après le rechargement.
    Should Not Be Equal    ${iframe_apres}    ${iframe_avant}
    ...    msg=L'iframe porte le même identifiant avant et après rechargement (${iframe_avant}) : elle n'aurait pas été reconstruite.
    Log    Rechargement : fragment ${fragment_apres} inchangé, ${champs} champ de mot de passe, ${controles} contrôles reconstruits dans la frame, identifiant d'iframe ${iframe_avant} devenu ${iframe_apres}    console=True

L identifiant de l iframe applicative est un compteur pas une ancre
    [Documentation]    Scénario 4 du plan. L'identifiant de l'iframe est
    ...    collecté à QUATRE moments d'un même run (ouverture, après
    ...    rechargement, après un aller-retour d'historique, dans un onglet
    ...    neuf), puis comparé.
    ...
    ...    Ce test n'assère AUCUNE valeur d'identifiant : il assère leur
    ...    VARIABILITÉ, et que le sélecteur retenu par la bibliothèque pour
    ...    désigner la frame n'en contient aucun. C'est précisément la propriété
    ...    qu'un localisateur écrit à la main perdrait, et elle a coûté assez
    ...    cher pour mériter son propre scénario.
    Revenir A L Accueil Du Launchpad
    Ouvrir L Application Par Intent    ${WORKZONE_APP_TEMOIN}[intent]
    ${a_l_ouverture}=    Lire L Identifiant De L Iframe Applicative
    Recharger Le Launchpad
    Attendre La Reconstruction De L Application
    ${apres_rechargement}=    Lire L Identifiant De L Iframe Applicative
    Revenir En Arriere Dans Le Navigateur
    ${apres_historique}=    Avancer Dans Le Navigateur
    ${onglet}=    Ouvrir Un Second Onglet Sur Le Site    ${WORKZONE_APP_TEMOIN}[intent]
    Le Shell Work Zone Est Rendu
    Attendre L Iframe De L Application
    ${dans_un_onglet_neuf}=    Lire L Identifiant De L Iframe Applicative
    Revenir Au Premier Onglet
    Fermer L Onglet    ${onglet}
    ${collectes}=    Create List    ${a_l_ouverture}    ${apres_rechargement}
    ...    ${apres_historique}    ${dans_un_onglet_neuf}
    ${distincts}=    Evaluate    len(set($collectes))
    Should Be True    ${distincts} >= 2
    ...    msg=Les quatre relevés portent le même identifiant (${collectes}) : la variabilité que ce scénario protège n'est plus observable, re-vérifier le plan.
    ${selecteur}=    Le Selecteur De L Iframe Est Positionnel    ${collectes}
    Log    Identifiants d'iframe relevés dans le même run : ouverture ${a_l_ouverture}, après rechargement ${apres_rechargement}, après aller-retour d'historique ${apres_historique}, dans un onglet neuf ${dans_un_onglet_neuf} (${distincts} valeurs distinctes). Sélecteur retenu par la bibliothèque : ${selecteur}    console=True

La navigation arriere detruit l application et restaure l ecran precedent avec son etat
    [Documentation]    Scénario 5 du plan. Depuis un écran de shell qui porte un
    ...    ÉTAT dans son fragment (la page de résultats de recherche), ouvrir
    ...    une application puis revenir en arrière détruit l'application et
    ...    reconstruit l'écran précédent avec son état.
    ...
    ...    Vérifier seulement le fragment laisserait passer un écran reconstruit
    ...    vide : le test confronte donc trois mesures prises avant le départ,
    ...    le fragment, l'état qu'il transporte et le nombre de résultats
    ...    portés. Aucun comptage de contrôles n'entre dans le verdict : mesuré
    ...    live, la même page restaurée par un retour arrière se stabilise à un
    ...    nombre sans rapport avec celui de sa première construction.
    Preparer L Ecran Porteur D Etat
    ${fragment_avant}=    Lire Le Fragment Courant
    ${etat_avant}=    Lire L Etat Porte Par Le Fragment
    ${resultats_avant}=    Compter Les Resultats De Recherche
    Should Be True    ${resultats_avant} > 0
    ...    msg=L'écran de départ ne porte aucun résultat : sa restauration serait vraie sans rien prouver.
    Ouvrir Le Premier Resultat De Recherche
    ${iframes_ouvertes}=    Compter Les Iframes Applicatives
    Should Be Equal As Integers    ${iframes_ouvertes}    1
    ...    msg=L'ouverture du résultat n'a pas produit exactement une iframe applicative (${iframes_ouvertes}).
    Revenir En Arriere Dans Le Navigateur
    Attendre L Etat Avec Resultats
    ${iframes_apres}=    Compter Les Iframes Applicatives
    ${fragment_apres}=    Lire Le Fragment Courant
    ${etat_apres}=    Lire L Etat Porte Par Le Fragment
    ${resultats_apres}=    Compter Les Resultats De Recherche
    Should Be Equal As Integers    ${iframes_apres}    0
    ...    msg=Une iframe survit au retour arrière (${iframes_apres}) : l'application n'a pas été détruite.
    Should Be Equal    ${fragment_apres}    ${fragment_avant}
    ...    msg=Le fragment restauré diffère de celui de l'écran de départ.
    Should Be Equal    ${etat_apres}[terme]    ${etat_avant}[terme]
    ...    msg=L'état porté par le fragment a perdu son terme (${etat_avant}[terme] avant, ${etat_apres}[terme] après).
    Should Be Equal    ${etat_apres}[source]    ${etat_avant}[source]
    ...    msg=L'état porté par le fragment a changé de source de données (${etat_avant}[source] avant, ${etat_apres}[source] après).
    Should Be Equal As Integers    ${resultats_apres}    ${resultats_avant}
    ...    msg=L'écran restauré porte ${resultats_apres} résultat(s) au lieu des ${resultats_avant} d'avant le départ.
    Log    Retour arrière : ${iframes_apres} iframe, fragment identique, état ${etat_apres} restauré, ${resultats_apres} résultat(s) comme avant le départ    console=True

La navigation avant rouvre l application dans une nouvelle iframe
    [Documentation]    Scénario 6 du plan. Depuis l'écran restauré, la
    ...    navigation avant rouvre l'application : une iframe est de nouveau
    ...    présente, son identifiant DIFFÈRE de celui d'avant le retour arrière,
    ...    et l'adresse chargée est la MÊME. L'application est donc reconstruite,
    ...    pas remise en cache.
    ...
    ...    La comparaison porte sur l'adresse amputée de sa query : celle-ci
    ...    transporte des identifiants de contenu du site, qui varient d'une voie
    ...    d'ouverture à l'autre sans que l'application change.
    Preparer L Ecran Porteur D Etat
    Ouvrir Le Premier Resultat De Recherche
    ${iframe_avant}=    Lire L Identifiant De L Iframe Applicative
    ${adresse_avant}=    Lire L Adresse Chargee Dans L Iframe
    Revenir En Arriere Dans Le Navigateur
    ${iframe_apres}=    Avancer Dans Le Navigateur
    ${adresse_apres}=    Lire L Adresse Chargee Dans L Iframe
    Should Not Be Equal    ${iframe_apres}    ${iframe_avant}
    ...    msg=L'iframe rouverte porte le même identifiant qu'avant le retour arrière (${iframe_avant}) : elle aurait été remise en cache plutôt que reconstruite.
    Should Be Equal    ${adresse_apres}    ${adresse_avant}
    ...    msg=L'iframe rouverte charge une autre adresse (${adresse_avant} avant, ${adresse_apres} après).
    Log    Navigation avant : iframe ${iframe_avant} devenue ${iframe_apres}, même adresse chargée (${adresse_apres})    console=True

Un second onglet du meme navigateur partage la session
    [Documentation]    Scénario 7 du plan. Un second onglet du MÊME contexte,
    ...    ouvert sur le site avec un fragment d'intent, n'est pas redirigé vers
    ...    le fournisseur d'identité, ne demande aucun mot de passe, et ouvre
    ...    l'application sans passer par l'accueil. La session est donc portée
    ...    par des cookies de contexte, partagés entre onglets.
    ...
    ...    Le dernier contrôle interdit la lecture « le second onglet a volé la
    ...    session » : le premier onglet doit rester utilisable, ce qui se
    ...    constate en lui faisant servir sa configuration ushell et compter ses
    ...    contrôles. Le retour au premier onglet est lui-même CONSTATÉ sur un
    ...    témoin déposé dans la page, les deux onglets ayant la même URL.
    Revenir A L Accueil Du Launchpad
    ${onglet}=    Ouvrir Un Second Onglet Sur Le Site    ${WORKZONE_APP_TEMOIN}[intent]
    ${adresse}=    Lire L Adresse Atteinte
    ${champs}=    Compter Les Champs De Mot De Passe
    ${site}=    Lire L Hote Du Site
    Should Be Equal    ${adresse}[hote]    ${site}
    ...    msg=Le second onglet a été redirigé hors du site (${adresse}[hote]) : la session n'est pas partagée entre onglets.
    Should Be Equal As Integers    ${champs}    0
    ...    msg=Le second onglet demande un mot de passe (${champs} champ(s)) : la session n'est pas partagée.
    Should Be Equal    ${adresse}[fragment]    ${WORKZONE_APP_TEMOIN}[intent]
    ...    msg=Le second onglet n'a pas conservé son fragment d'intent : ${adresse}[fragment]
    Le Shell Work Zone Est Rendu
    Attendre L Iframe De L Application
    ${accueil}=    La Page D Accueil Est Rendue
    ${iframes}=    Compter Les Iframes Applicatives
    Should Not Be True    ${accueil}
    ...    msg=Le second onglet est passé par la page d'accueil avant d'ouvrir l'application.
    Should Be Equal As Integers    ${iframes}    1
    ...    msg=Le second onglet porte ${iframes} iframe(s) applicative(s) au lieu d'une.
    Revenir Au Premier Onglet
    ${delais}=    Lire Les Delais De Session Declares
    ${controles}=    Compter Les Controles Rendus
    Should Be True    ${controles} > 0
    ...    msg=Le premier onglet ne rend plus aucun contrôle après l'ouverture du second : il aurait perdu sa session.
    Fermer L Onglet    ${onglet}
    Log    Second onglet : hôte ${adresse}[hote], fragment ${adresse}[fragment], ${champs} champ de mot de passe, accueil rendu=${accueil}, ${iframes} iframe. Premier onglet toujours vivant : ${controles} contrôles et configuration servie (intervalle ${delais}[intervalle] min)    console=True

La perte de session est observable en secondes et se constate au trajet
    [Documentation]    Scénario 8 du plan. Dans un contexte de navigateur DÉDIÉ,
    ...    authentifié et application ouverte, les cookies sont relevés (noms,
    ...    domaines et caractère permanent SEULEMENT), vidés, puis la page est
    ...    rechargée : le navigateur repart sur le trajet de réauthentification.
    ...
    ...    Ce que ce test remplace, et pourquoi : l'expiration réelle demande
    ...    plusieurs minutes d'inactivité stricte (voir le test suivant, opt-in).
    ...    Vider les cookies produit le MÊME trajet observable en quelques
    ...    secondes, et c'est un test du comportement du shell face à une session
    ...    absente, pas une mesure du délai.
    ...
    ...    Ce qu'il ne prouve PAS, et le dit : rien de ce que fait le shell quand
    ...    la session meurt SANS rechargement, au moment d'un appel de service en
    ...    cours de page.
    ...
    ...    Aucune valeur de cookie n'est lue ni journalisée, et le vidage se
    ...    refuse mécaniquement sur le contexte de la suite.
    ${contexte}=    Ouvrir Un Contexte Neuf
    Ouvrir Le Site Sur Un Intent    ${WORKZONE_APP_TEMOIN}[intent]
    Attendre Le Trajet De Reauthentification
    S Authentifier Sur Le Trajet Courant
    Attendre L Iframe De L Application
    ${cookies}=    Lire Les Cookies De Session
    Should Not Be Empty    ${cookies}
    ...    msg=Le contexte authentifié ne porte aucun cookie : la session serait portée par autre chose, le scénario n'a plus d'objet.
    ${permanents}=    Evaluate    [c for c in $cookies if c['expiration_future']]
    Should Be Empty    ${permanents}
    ...    msg=Des cookies portent une date d'expiration FUTURE : il existe un jeton persistant, contrairement à ce que le plan a relevé. ${permanents}
    ${site}=    Lire L Hote Du Site
    ${sur_le_site}=    Evaluate    [c for c in $cookies if c['domaine'].lstrip('.') == $site]
    Should Not Be Empty    ${sur_le_site}
    ...    msg=Aucun cookie n'est posé sur l'hôte du site (${site}) : la lecture ne porte pas sur la session attendue. ${cookies}
    ${domaines}=    Evaluate    sorted({c['domaine'].lstrip('.') for c in $cookies})
    Vider Les Cookies Du Contexte    ${contexte}
    ${restants}=    Lire Les Cookies De Session
    Should Be Empty    ${restants}
    ...    msg=${{len($restants)}} cookie(s) survivent au vidage : la simulation de perte de session ne prouverait rien.
    Recharger Le Launchpad
    ${adresse}=    Attendre Le Trajet De Reauthentification
    Should Be Empty    ${adresse}[fragment]
    ...    msg=Le fragment a survécu à la perte de session (${adresse}[fragment]) : le trajet n'est pas celui d'un accès sans session.
    Fermer Le Contexte Dedie    ${contexte}
    Log    Perte de session simulée : ${{len($cookies)}} cookie(s) de session sur ${{len($domaines)}} domaine(s) (${domaines}), aucun à expiration future ; après vidage et rechargement, retour sur ${adresse}[hote]${adresse}[chemin] sans runtime UI5    console=True

Le shell declare ses delais de session
    [Documentation]    Scénario 9 du plan. La configuration du shell déclare
    ...    l'intervalle d'expiration, le délai de rappel qui le précède et le
    ...    point de service qui maintient la session. Les trois sont présents et
    ...    cohérents entre eux, et le point de maintien est servi par l'hôte du
    ...    site.
    ...
    ...    Les valeurs exactes sont JOURNALISÉES, jamais gravées : ce sont des
    ...    réglages de site. Ce qui est vérifiable partout, c'est que le rappel
    ...    précède strictement l'expiration, sinon il n'aurait pas lieu d'être,
    ...    et c'est aussi ce chiffre qui rend l'expiration réelle impraticable
    ...    dans une campagne courte, donc qui justifie le scénario précédent.
    ${delais}=    Lire Les Delais De Session Declares
    Should Be True    ${{ int($delais['intervalle']) > 0 }}
    ...    msg=L'intervalle d'expiration déclaré n'est pas un délai exploitable : ${delais}[intervalle]
    Should Be True    ${{ int($delais['rappel']) > 0 }}
    ...    msg=Le délai de rappel déclaré n'est pas un délai exploitable : ${delais}[rappel]
    Should Be True    ${{ int($delais['rappel']) < int($delais['intervalle']) }}
    ...    msg=Le rappel (${delais}[rappel] min) n'est pas strictement inférieur à l'intervalle d'expiration (${delais}[intervalle] min) : il ne pourrait jamais précéder l'expiration.
    Le Point De Maintien Est Sur L Hote Du Site    ${delais}[maintien]
    ${inactivite}=    Calculer L Inactivite Avant Le Premier Signe    ${delais}
    Log    Délais déclarés par le shell : expiration à ${delais}[intervalle] min d'inactivité, rappel ${delais}[rappel] min avant, soit ${inactivite} min d'inactivité stricte avant le premier signe visible ; maintien de session par ${delais}[maintien]    console=True

Une navigation refusee laisse l ecran intact et le fragment n est restaure qu a l acquittement
    [Documentation]    Scénario 10 du plan. Application ouverte, la demande de
    ...    navigation vers un intent FABRIQUÉ produit un dialogue en état
    ...    d'erreur à deux boutons, dont le dernier est mis en avant. Pendant le
    ...    dialogue, le fragment porte l'intent REFUSÉ ; après acquittement, il
    ...    est restauré, l'identifiant de l'iframe n'a pas bougé et plus aucun
    ...    popup n'est ouvert.
    ...
    ...    Deux pièges sont encodés ici, et chacun rendrait un test rouge sur un
    ...    shell parfaitement sain. Mesurer le fragment PENDANT le dialogue et
    ...    conclure que la navigation a eu lieu : la mesure qui fait foi est
    ...    prise après acquittement, et elle attend. Acquitter par la position
    ...    0 : c'est une action de copie du message technique, qui laisse le
    ...    dialogue ouvert, d'où l'ancre par TYPE de bouton.
    Revenir A L Accueil Du Launchpad
    Ouvrir L Application Par Intent    ${WORKZONE_APP_TEMOIN}[intent]
    ${fragment_avant}=    Lire Le Fragment Courant
    ${iframe_avant}=    Lire L Identifiant De L Iframe Applicative
    Demander Un Intent Inconnu
    ${refus}=    Le Shell Refuse La Navigation
    ${fragment_pendant}=    Lire Le Fragment Courant
    ${iframe_pendant}=    Lire L Identifiant De L Iframe Applicative
    Should Be Equal    ${fragment_pendant}    ${WORKZONE_UNKNOWN_INTENT}
    ...    msg=Pendant le dialogue de refus, le fragment porte ${fragment_pendant} au lieu de l'intent refusé.
    Should Be Equal    ${iframe_pendant}    ${iframe_avant}
    ...    msg=L'iframe a changé d'identifiant pendant le refus (${iframe_avant} puis ${iframe_pendant}) : l'application aurait été détruite.
    Acquitter Le Refus De Navigation    ${refus}[dialogue]    ${fragment_avant}
    ${fragment_apres}=    Lire Le Fragment Courant
    ${iframe_apres}=    Lire L Identifiant De L Iframe Applicative
    Should Be Equal    ${fragment_apres}    ${fragment_avant}
    ...    msg=Le fragment n'a pas été restauré après acquittement (${fragment_avant} attendu, ${fragment_apres} obtenu).
    Should Be Equal    ${iframe_apres}    ${iframe_avant}
    ...    msg=L'iframe a changé d'identifiant après acquittement (${iframe_avant} puis ${iframe_apres}) : l'application aurait été reconstruite.
    Log    Refus de navigation : dialogue en état ${refus}[dialogue][state] à ${refus}[dialogue][buttons] boutons de types ${refus}[types] ; fragment ${fragment_pendant} pendant le dialogue, ${fragment_apres} après acquittement, iframe ${iframe_apres} jamais détruite    console=True

L expiration reelle survient apres l inactivite declaree
    [Documentation]    Variante LONGUE du scénario 9, opt-in à DEUX tours : le
    ...    tag `slow` dit ce que ce test coûte, la variable
    ...    `WORKZONE_LONG_OPT_IN` dit qu'on l'a voulu. Sans elle le test est
    ...    SAUTÉ, y compris dans un run complet, parce qu'un tag seul dépend de
    ...    la mémoire de celui qui lance la commande et qu'une campagne qui
    ...    immobilise la cible un quart d'heure ne doit jamais démarrer par
    ...    surprise.
    ...
    ...    Ce qu'il éprouve : après une inactivité STRICTE dérivée de la
    ...    configuration de la cible, le shell RÉAGIT, soit par un rappel
    ...    d'expiration, soit en repartant sur le trajet de réauthentification.
    ...    Les deux branches sont acceptées : c'est la réaction à l'inactivité
    ...    qui est éprouvée, pas sa forme, qui dépend du site.
    ...
    ...    La partie falsifiable est la DURÉE : le signe ne doit pas arriver
    ...    avant l'inactivité déclarée, sinon rien ne prouve qu'un compte à
    ...    rebours d'inactivité existe. Le repère de départ est donc posé juste
    ...    après une frappe RÉELLE, seul geste qui remet ce compte à rebours à
    ...    zéro à un instant connu. L'attente, elle, ne dort pas (convention 2) :
    ...    elle sonde par lecture de script, sans jamais émettre de mouvement de
    ...    souris ni de frappe, et il est mesuré que cela ne réarme pas le
    ...    maintien de session.
    ...
    ...    Ce test doit rester le DERNIER de la suite : il peut tuer la session
    ...    que les autres utilisent.
    [Tags]    slow
    Exiger L Accord Pour Un Scenario Long
    Revenir A L Accueil Du Launchpad
    ${delais}=    Lire Les Delais De Session Declares
    ${inactivite}=    Calculer L Inactivite Avant Le Premier Signe    ${delais}
    Reinitialiser Le Compte A Rebours D Inactivite
    ${debut}=    Get Time    epoch
    ${verdict}=    Attendre Le Signe D Expiration De Session    ${delais}
    ${fin}=    Get Time    epoch
    ${ecoule}=    Evaluate    round((${fin} - ${debut}) / 60.0, 1)
    Should Be True    ${ecoule} >= ${inactivite}
    ...    msg=Le shell a signalé l'expiration après ${ecoule} minutes, avant les ${inactivite} minutes d'inactivité qu'il déclare : rien ne prouve qu'un compte à rebours d'inactivité soit en cause.
    Log    Expiration réelle : signe « ${verdict}[signe] » obtenu après ${ecoule} minutes d'inactivité stricte, pour ${inactivite} minutes déclarées avant le premier signe (expiration annoncée à ${delais}[intervalle] min). Popups ouverts : ${verdict}[popups] ; adresse atteinte : ${verdict}[adresse]    console=True
