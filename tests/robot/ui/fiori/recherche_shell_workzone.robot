*** Settings ***
Documentation       Recherche du shell d'un launchpad Work Zone (BTP)
...                 Spec: specs/workzone-recherche-shell.md (sha256:b26795fea80b, 2026-08-26)
...                 Generated from specs/workzone-recherche-shell.md by sap-generator:
...                 re-run the generator rather than hand-editing locators here.
...
...                 Campagne de la **recherche du shell** d'un launchpad SAP
...                 Build Work Zone (cFLP sur BTP, derrière un tenant SAP Cloud
...                 Identity Services) : quelle implémentation la configuration
...                 rend active, comment le champ est créé et où vit son bouton,
...                 suggestions issues du catalogue, page de résultats portée
...                 par le fragment, comptage porté contre comptage global,
...                 état sans résultat, ouverture d'un résultat, et persistance
...                 du terme dans l'URL.
...
...                 Ce que cette campagne établit, et qu'aucune fixture ne peut
...                 établir : deux implémentations de recherche cohabitent sur
...                 un vrai cFLP, et le champ le plus facile à trouver n'est pas
...                 celui dans lequel l'utilisateur tape ; le bouton qui ouvre
...                 la recherche n'a aucun identifiant et vit dans un shadow
...                 root ; ce bouton n'est pas une bascule mais disparaît une
...                 fois le champ ouvert ; la page de résultats est rendue DANS
...                 le document du shell, sans iframe, contrairement aux
...                 applications de type URL du site ; et un comptage naïf de
...                 tuiles y ment, la tuile de l'accueil restant rendue,
...                 invisible, sous les résultats.
...
...                 **Lecture seule** : la recherche interroge, elle n'écrit ni
...                 ne configure rien. Ce qui est ouvert est refermé et le
...                 teardown ramène le shell à son accueil.
...
...                 Aucun localisateur ici (convention 1) : ils vivent dans
...                 `resources/page_objects/workzone_shell_search.resource` et
...                 `resources/page_objects/workzone_launchpad.resource`.
...
...                 **L'ordre des deux premiers tests est porteur de sens** et
...                 ne doit pas être changé : le champ de la recherche nouvelle
...                 génération n'est observable que sur un shell dont la
...                 recherche d'entreprise n'a jamais été ouverte, et les
...                 contrôles de cette dernière ne sont créés qu'au premier
...                 clic. Les tests suivants sont autonomes et rétablissent
...                 eux-mêmes leur état de départ.
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
...                 |  ...   tests/robot/ui/fiori/recherche_shell_workzone.robot

Resource            ../../../../resources/page_objects/workzone_shell_search.resource

Suite Setup         Preparer La Campagne Recherche Shell
Suite Teardown      Clore La Campagne Recherche Shell
Test Teardown       Run Keywords    Journaliser Le Diagnostic Fiori En Cas D Echec
...                     AND    Sortir De L Application Si Necessaire

Test Tags           fiori    workzone    btp    live


*** Test Cases ***
La recherche active du shell est celle que la configuration declare
    [Documentation]    Scénario 1 du plan, et il doit rester le PREMIER test.
    ...    La configuration du shell déclare la recherche nouvelle génération
    ...    désactivée et nomme l'adaptateur du service de recherche réellement
    ...    servi ; le champ correspondant à l'implémentation désactivée est
    ...    présent au registre et pourtant sans rectangle, ce que la
    ...    bibliothèque et le navigateur constatent chacun de leur côté. Le test
    ...    n'échoue que sur une CONTRADICTION entre ce qui est déclaré et ce qui
    ...    est rendu : un champ déclaré désactivé mais réellement visible, ou
    ...    l'inverse.
    ...
    ...    Ce que ce scénario corrige : la campagne de perception compte ce
    ...    contrôle comme « le champ de recherche du shell ». Il reste un témoin
    ...    d'étanchéité de portée parfaitement valable, et ce n'est pas le champ
    ...    dans lequel l'utilisateur tape.
    ${declaration}=    Lire La Configuration De La Recherche
    Should End With    ${declaration}[adaptateur]    ${WORKZONE_SEARCH_SERVICE_MARKER}
    ...    msg=Le service de recherche du shell n'est pas servi par un adaptateur de recherche : ${declaration}[adaptateur]
    ${present}=    Compter Le Champ De Recherche Nouvelle Generation
    ${visible}=    Le Champ Est Visible A L Ecran    ${WORKZONE_SEARCH_FIELD}
    ${etats}=    Lire Les Etats Navigateur Du Champ    ${WORKZONE_SEARCH_FIELD}
    Should Be Equal    ${visible}    ${declaration}[nouvelle_generation]
    ...    msg=La configuration et le rendu se contredisent : la recherche nouvelle génération est déclarée activée=${declaration}[nouvelle_generation] et son champ est visible=${visible}.
    IF    ${present} > 0
        ${attendu}=    Set Variable If    ${visible}    visible    hidden
        Should Contain    ${etats}    ${attendu}
        ...    msg=Le navigateur (${etats}) contredit la mesure du rectangle (visible=${visible}) sur le champ de la recherche nouvelle génération.
    END
    Log    Recherche nouvelle génération déclarée activée=${declaration}[nouvelle_generation] ; son champ est rendu ${present} fois, visible=${visible}, états navigateur ${etats} ; adaptateur du service servi : ${declaration}[adaptateur]    console=True

Le champ de recherche est cree au premier clic et son bouton vit dans un shadow root
    [Documentation]    Scénario 2 du plan, et il doit rester le premier test qui
    ...    OUVRE la recherche : ses contrôles ne sont créés qu'au premier clic
    ...    et ne sont plus détruits ensuite, donc un comptage « zéro avant »
    ...    n'est vrai qu'une fois par session.
    ...
    ...    Le bouton d'ouverture n'a aucun identifiant et vit dans le shadow
    ...    root de la barre shell. Les trois canaux sont mesurés avec la MÊME
    ...    ancre technique : le moteur Web Components de la bibliothèque et la
    ...    bibliothèque Browser le voient, le moteur DOM générique ne le voit
    ...    pas, son balayage restant au light DOM. Convention 12 : cet écart EST
    ...    le défaut de bibliothèque, mesuré dans le test lui-même ; il est
    ...    journalisé et ne fait pas échouer la campagne tant qu'un canal de la
    ...    bibliothèque suffit à ouvrir la recherche.
    ${avant}=    Compter Les Controles De La Recherche
    Should Be Equal As Integers    ${avant}    0
    ...    msg=La recherche d'entreprise a déjà été ouverte dans cette session (${avant} contrôles) : ce test doit être le premier à l'ouvrir, sinon la création différée n'est pas prouvée.
    ${moteurs}=    Compter Le Bouton De Recherche Par Moteur
    Should Be Equal As Integers    ${moteurs}[navigateur]    1
    ...    msg=La bibliothèque Browser ne résout pas exactement un bouton de recherche sous la barre shell : ${moteurs}
    Should Be Equal As Integers    ${moteurs}[wc]    ${moteurs}[navigateur]
    ...    msg=Le moteur Web Components (${moteurs}[wc]) ne voit plus ce que la bibliothèque Browser voit (${moteurs}[navigateur]) : la recherche n'est plus ouvrable par un moteur de la bibliothèque.
    Ouvrir La Recherche Du Shell
    ${apres}=    Compter Les Controles De La Recherche
    Should Be True    ${apres} >= ${WORKZONE_SEARCH_MIN_CONTROLS}
    ...    msg=Après le clic, la recherche ne porte que ${apres} de ses contrôles au lieu d'au moins ${WORKZONE_SEARCH_MIN_CONTROLS} (groupe, saisie, déclenchement).
    ${saisie_visible}=    Le Champ Est Visible A L Ecran    ${WORKZONE_SEARCH_INPUT}
    Should Be True    ${saisie_visible}
    ...    msg=Le champ de saisie de la recherche est créé mais n'occupe aucun rectangle : la recherche n'est pas réellement ouverte.
    Log    Contrôles de la recherche : ${avant} avant le premier clic, ${apres} après. Bouton d'ouverture compté par moteur : wc=${moteurs}[wc], dom=${moteurs}[dom], navigateur=${moteurs}[navigateur] (l'écart du moteur dom est le défaut de bibliothèque restant)    console=True

Un terme partiel propose des suggestions issues du catalogue
    [Documentation]    Scénario 3 du plan. Le terme soumis est un PRÉFIXE dérivé
    ...    du titre d'une application découverte au catalogue, jamais le titre
    ...    exact : c'est un libellé traduit, et sur certains shells le soumettre
    ...    tel quel navigue directement vers l'application, sans page de
    ...    résultats. Le popover de suggestions doit être réellement OUVERT, et
    ...    au moins une suggestion doit porter le titre relevé au catalogue :
    ...    deux mesures du même run, aucun libellé écrit dans le test.
    Saisir Un Terme De Recherche    ${WORKZONE_TERME_TROUVE}
    ${popover}=    Les Suggestions Sont Proposees
    ${suggestions}=    Lire Les Suggestions
    Should Not Be Empty    ${suggestions}
    ...    msg=Le popover de suggestions est ouvert mais ne porte aucune ligne.
    ${portant_le_titre}=    Evaluate
    ...    [s for s in $suggestions if $WORKZONE_APP_TEMOIN['titre'] in s]
    Should Not Be Empty    ${portant_le_titre}
    ...    msg=Aucune suggestion ne porte le titre de l'application relevée au catalogue : suggestions ${suggestions}
    Fermer Les Suggestions
    Log    Terme partiel « ${WORKZONE_TERME_TROUVE} » : ${{len($suggestions)}} suggestion(s) proposée(s) par un popover ${popover}[technology], dont ${{len($portant_le_titre)}} porte(nt) le titre du catalogue    console=True

La recherche produit une page de resultats portee par le fragment
    [Documentation]    Scénario 4 du plan. Le fragment atteint porte l'intent de
    ...    recherche du shell ; le filtre qu'il transporte nomme la source de
    ...    données TECHNIQUE des applications et le terme exact soumis ; le
    ...    conteneur d'application dérivé de cet intent est rendu une fois ;
    ...    aucune iframe n'est créée, la page de résultats vivant dans le
    ...    document du shell ; et le nombre de contrôles rendus dépasse celui de
    ...    l'accueil relevé juste avant, dans le même test. Aucun plancher n'est
    ...    gravé : mesuré live, ce nombre dépend du chemin d'arrivée et grossit
    ...    au fil de la campagne.
    Revenir A L Accueil Du Launchpad
    ${a_l_accueil}=    Compter Les Controles Rendus
    Lancer La Recherche    ${WORKZONE_TERME_TROUVE}
    ${intent}=    Lire L Intent Porte Par Le Fragment
    Should Be Equal    ${intent}    ${WORKZONE_SEARCH_INTENT}
    ...    msg=Le fragment atteint ne porte pas l'intent de recherche du shell : ${intent}
    ${filtre}=    Lire Le Filtre De Recherche
    Should Be Equal    ${filtre}[source]    ${WORKZONE_SEARCH_APPS_DATASOURCE}
    ...    msg=Le filtre n'interroge pas la source de données des applications : ${filtre}
    Should Be Equal    ${filtre}[type_source]    ${WORKZONE_SEARCH_DATASOURCE_TYPE}
    ...    msg=La source de données interrogée n'est pas du type attendu : ${filtre}
    Should Be Equal    ${filtre}[terme]    ${WORKZONE_TERME_TROUVE}
    ...    msg=Le filtre ne porte pas le terme soumis (${WORKZONE_TERME_TROUVE}) : ${filtre}
    ${conteneurs}=    Compter Le Conteneur De L Application De Recherche
    Should Be Equal As Integers    ${conteneurs}    1
    ...    msg=Le conteneur de l'application de recherche est rendu ${conteneurs} fois au lieu d'une.
    ${iframes}=    Lire Les Identifiants D Iframe
    Should Be Empty    ${iframes}
    ...    msg=La page de résultats a créé une iframe (${iframes}) : elle devrait être rendue dans le document du shell.
    ${sur_les_resultats}=    Compter Les Controles Rendus
    Should Be True    ${sur_les_resultats} > ${a_l_accueil}
    ...    msg=La page de résultats ne rend pas plus de contrôles (${sur_les_resultats}) que l'accueil (${a_l_accueil}) : rien n'a été construit.
    Log    Fragment ${intent}, filtre ${filtre} ; contrôles rendus ${a_l_accueil} à l'accueil contre ${sur_les_resultats} sur les résultats, zéro iframe    console=True

Les resultats se comptent dans leur conteneur jamais globalement
    [Documentation]    Scénario 5 du plan. Le comptage global de tuiles est
    ...    strictement supérieur au comptage porté par la grille de résultats,
    ...    et l'écart s'explique ENTIÈREMENT par des tuiles de rectangle nul
    ...    qui n'appartiennent pas à la grille : la tuile de l'accueil, encore
    ...    rendue sous la page de résultats.
    ...
    ...    Sans ce scénario, un test « la recherche a trouvé quelque chose »
    ...    serait vert sur une recherche vide, la tuile de l'accueil suffisant à
    ...    faire le compte.
    Lancer La Recherche    ${WORKZONE_TERME_TROUVE}
    Attendre L Etat Avec Resultats
    ${portes}=    Compter Les Resultats De Recherche
    Should Be True    ${portes} > 0
    ...    msg=La grille de résultats ne porte aucun résultat pour un terme qui en a.
    ${globales}=    Compter Toutes Les Tuiles De La Page
    ${tuiles}=    Lire Les Tuiles De La Page
    ${dans_les_resultats}=    Evaluate    [t for t in $tuiles if t['dans_les_resultats']]
    ${hors_resultats}=    Evaluate    [t for t in $tuiles if not t['dans_les_resultats']]
    ${nb_portees}=    Get Length    ${dans_les_resultats}
    Should Be True    ${globales} > ${nb_portees}
    ...    msg=Le comptage global (${globales}) n'excède plus le comptage porté (${nb_portees}) : le piège documenté n'existe plus, re-vérifier le plan.
    Should Not Be Empty    ${hors_resultats}
    ...    msg=Aucune tuile hors de la grille de résultats alors que le comptage global est supérieur : l'écart est inexpliqué.
    ${visibles_hors_resultats}=    Evaluate    [t for t in $hors_resultats if t['visible']]
    Should Be Empty    ${visibles_hors_resultats}
    ...    msg=Des tuiles VISIBLES vivent hors de la grille de résultats : l'écart de comptage ne s'explique plus par des rectangles nuls, il cache autre chose. ${visibles_hors_resultats}
    ${resultats}=    Lire Les Resultats De Recherche
    Length Should Be    ${resultats}    ${portes}
    ...    msg=La lecture des résultats (${{len($resultats)}}) ne concorde pas avec leur comptage (${portes}).
    Log    ${globales} tuile(s) dans toute la page pour ${nb_portees} portée(s) par la grille ; l'écart est entièrement fait de tuiles à rectangle nul : ${hors_resultats}    console=True

Un terme sans correspondance produit un etat structurellement distinct
    [Documentation]    Scénario 6 du plan. Un terme fabriqué produit un état où
    ...    la grille de résultats n'est PAS rendue et où un écran dédié l'est,
    ...    avec son illustration ; un terme trouvé, soumis ensuite dans le même
    ...    chargement, inverse exactement les deux constats. L'aller-retour est
    ...    ce qui rend le scénario non trivial : constater seulement « zéro
    ...    résultat » serait vrai d'une page qui n'a rien construit du tout.
    ...
    ...    Assertions locale-indépendantes : la présence ou l'absence de deux
    ...    contrôles identifiés par leur suffixe, jamais le texte du message
    ...    d'absence ni celui du compteur, tous deux traduits.
    Lancer La Recherche    ${WORKZONE_SEARCH_ABSENT_TERM}
    ${filtre}=    Lire Le Filtre De Recherche
    Should Be Equal    ${filtre}[terme]    ${WORKZONE_SEARCH_ABSENT_TERM}
    ...    msg=Le filtre ne porte pas le terme fabriqué qui vient d'être soumis : ${filtre}
    Attendre L Etat Sans Resultat
    ${sans}=    Compter Les Resultats De Recherche
    Should Be Equal As Integers    ${sans}    0
    ...    msg=La recherche sans correspondance rapporte ${sans} résultat(s).
    Lancer La Recherche    ${WORKZONE_TERME_TROUVE}
    Attendre L Etat Avec Resultats
    ${avec}=    Compter Les Resultats De Recherche
    Should Be True    ${avec} > 0
    ...    msg=Le terme trouvé ne ramène aucun résultat après un passage sans correspondance.
    Log    Terme fabriqué : grille absente, écran dédié présent, ${sans} résultat ; terme trouvé dans le même chargement : grille revenue, écran dédié disparu, ${avec} résultat(s)    console=True

Ouvrir un resultat mene a la meme application que l intent
    [Documentation]    Scénario 7 du plan. Le résultat porte une cible dont
    ...    l'intent est celui de l'application ; l'ouvrir mène au même intent et
    ...    charge la même adresse dans l'iframe que la voie « intent » découverte
    ...    au catalogue. La comparaison porte sur l'intent et sur l'adresse
    ...    chargée, pas sur le fragment complet : la cible d'un résultat porte en
    ...    plus un paramètre d'identification du contenu du site, que l'intent
    ...    nu ne porte pas. Deux mesures du même run, aucune adresse écrite dans
    ...    le test.
    ...
    ...    Avec le scénario 8 de la campagne de perception, qui établit
    ...    l'équivalence de la tuile et de l'intent, les trois voies d'ouverture
    ...    sont alors éprouvées.
    Lancer La Recherche    ${WORKZONE_TERME_TROUVE}
    Attendre L Etat Avec Resultats
    ${resultats}=    Lire Les Resultats De Recherche
    ${intent_de_la_cible}=    Evaluate    $resultats[0]['cible'].lstrip('#').split('?')[0]
    Ouvrir Le Premier Resultat De Recherche
    ${intent_par_resultat}=    Lire L Intent Porte Par Le Fragment
    ${adresse_par_resultat}=    Lire L Adresse De L Application Ouverte
    Should Be Equal    ${intent_de_la_cible}    ${intent_par_resultat}
    ...    msg=Le fragment atteint (${intent_par_resultat}) n'est pas l'intent que le résultat annonçait (${intent_de_la_cible}).
    Revenir A L Accueil Du Launchpad
    Ouvrir L Application Par Intent    ${WORKZONE_APP_TEMOIN}[intent]
    ${intent_par_navigation}=    Lire L Intent Porte Par Le Fragment
    ${adresse_par_navigation}=    Lire L Adresse De L Application Ouverte
    Should Be Equal    ${intent_par_resultat}    ${intent_par_navigation}
    ...    msg=Les deux voies d'ouverture n'atteignent pas le même intent : ${intent_par_resultat} par le résultat, ${intent_par_navigation} par la navigation.
    Should Be Equal    ${adresse_par_resultat}    ${adresse_par_navigation}
    ...    msg=Les deux voies chargent des adresses différentes dans l'iframe : ${adresse_par_resultat} par le résultat, ${adresse_par_navigation} par la navigation.
    Revenir A L Accueil Du Launchpad
    Log    Les deux voies mènent à l'intent ${intent_par_navigation} et chargent ${adresse_par_navigation}    console=True

Rechercher depuis une application quitte l application
    [Documentation]    Scénario 8 du plan. Depuis une application ouverte, la
    ...    recherche est atteignable : son bouton est rendu là comme à
    ...    l'accueil, ce qui implique aussi que le champ y est replié (le bouton
    ...    disparaît quand le champ est ouvert). Après soumission d'un terme
    ...    trouvé, plus AUCUNE iframe ne subsiste et le conteneur de
    ...    l'application de recherche est présent : l'application précédente a
    ...    été quittée, pas superposée.
    Ouvrir L Application Par Intent    ${WORKZONE_APP_TEMOIN}[intent]
    ${iframes_avant}=    Lire Les Identifiants D Iframe
    Should Not Be Empty    ${iframes_avant}
    ...    msg=Aucune iframe alors qu'une application du catalogue vient d'être ouverte.
    ${champ_replie}=    Le Champ Est Visible A L Ecran    ${WORKZONE_SEARCH_INPUT}
    ${moteurs}=    Compter Le Bouton De Recherche Par Moteur
    Should Be Equal As Integers    ${moteurs}[navigateur]    1
    ...    msg=Le bouton de recherche n'est pas rendu depuis une application ouverte : la recherche y serait inatteignable. ${moteurs}
    Lancer La Recherche    ${WORKZONE_TERME_TROUVE}
    ${iframes_apres}=    Lire Les Identifiants D Iframe
    Should Be Empty    ${iframes_apres}
    ...    msg=Une iframe survit à la recherche lancée depuis l'application (${iframes_apres}) : la page de résultats se serait superposée au lieu de la remplacer.
    ${conteneurs}=    Compter Le Conteneur De L Application De Recherche
    Should Be Equal As Integers    ${conteneurs}    1
    ...    msg=Le conteneur de l'application de recherche est rendu ${conteneurs} fois au lieu d'une.
    Log    Depuis l'application : champ replié (visible=${champ_replie}), bouton rendu, ${{len($iframes_avant)}} iframe avant la recherche et ${{len($iframes_apres)}} après    console=True

Le terme recherche survit a la navigation arriere
    [Documentation]    Scénario 9 du plan, dernier test de la suite. Après avoir
    ...    ouvert un résultat puis déclenché la navigation arrière, le champ de
    ...    saisie porte le terme soumis, le filtre du fragment aussi, et le
    ...    compte de résultats est identique : l'état de la recherche est donc
    ...    porté par l'URL et non par la mémoire de la page.
    ...
    ...    Le critère est ce trio, jamais un comptage de contrôles : mesuré
    ...    live, une page de résultats reconstruite par un retour arrière se
    ...    stabilise à un nombre de contrôles sans rapport avec celui de sa
    ...    première construction.
    Revenir A L Accueil Du Launchpad
    Lancer La Recherche    ${WORKZONE_TERME_TROUVE}
    Attendre L Etat Avec Resultats
    ${compte_avant}=    Compter Les Resultats De Recherche
    ${terme_avant}=    Lire Le Terme Du Champ De Recherche
    Should Be Equal    ${terme_avant}    ${WORKZONE_TERME_TROUVE}
    ...    msg=Le champ ne porte pas le terme qui vient d'être soumis : ${terme_avant}
    Ouvrir Le Premier Resultat De Recherche
    Revenir En Arriere
    Attendre L Etat Avec Resultats
    ${terme_apres}=    Lire Le Terme Du Champ De Recherche
    ${filtre}=    Lire Le Filtre De Recherche
    ${compte_apres}=    Compter Les Resultats De Recherche
    Should Be Equal    ${terme_apres}    ${terme_avant}
    ...    msg=Le champ de saisie a perdu le terme après le retour arrière (${terme_avant} avant, ${terme_apres} après).
    Should Be Equal    ${filtre}[terme]    ${terme_avant}
    ...    msg=Le fragment restauré ne porte pas le terme soumis : ${filtre}
    Should Be Equal As Integers    ${compte_apres}    ${compte_avant}
    ...    msg=Le compte de résultats a changé après le retour arrière (${compte_avant} avant, ${compte_apres} après).
    Log    Après retour arrière : terme ${terme_apres}, filtre ${filtre}, ${compte_apres} résultat(s), identiques au relevé d'avant l'ouverture    console=True
