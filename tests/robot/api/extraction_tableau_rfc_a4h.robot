*** Settings ***
Documentation       **Extraire un tableau SAP par le canal RFC, et à l'échelle.**
...                 Spec: specs/extraction-tableau-canal-rfc-a4h.md (sha256:c62c49388f54, 2026-09-16)
...                 Le quatrième canal d'extraction du dépôt, après l'écran SAP
...                 GUI, le WebGUI et l'UI5, vers les CINQ formats de
...                 restitution (SVG, classeur Excel, CSV, JSON Lines, Parquet
...                 optionnel). LECTURE SEULE de bout en bout.
...
...                 Générée depuis `specs/extraction-tableau-canal-rfc-a4h.md`
...                 par sap-generator : relancer le générateur plutôt que de
...                 corriger un nom technique ici.
...
...                 **Ce que ce canal ajoute, et que les trois autres ne
...                 posaient pas.** Une ALV publie son nombre de lignes, une
...                 grille WebGUI son total, une table UI5 la longueur de son
...                 binding. La lecture RFC, elle, ne déclare RIEN : elle rend
...                 des lignes et se tait. Le total doit donc venir d'AILLEURS,
...                 et le choix de cet ailleurs est la seule décision qui
...                 compte. Le mesurer par une seconde lecture reviendrait à
...                 comparer deux nombres que le même module produit de la même
...                 façon, c'est-à-dire à écrire une garde vraie quoi qu'il
...                 arrive. Il vient donc d'un module de COMPTAGE distinct de
...                 celui qui lit (scénario 2), et le scénario 6 va le chercher
...                 encore plus loin, dans un TROISIÈME canal.
...
...                 **Et une question d'échelle.** Le plus gros relevé jamais
...                 extrait par ce dépôt portait 1639 lignes. Celui-ci en porte
...                 28 782, dix-sept fois plus : une capacité qu'on n'a jamais
...                 poussée ne prouve rien de son comportement sur un vrai
...                 volume transactionnel.
...
...                 **Trois gardes, chacune contre un résultat faux mais
...                 plausible.**
...
...                 1. *La cible.* Les deux conteneurs du banc annoncent le
...                 même identifiant système ET le même nom d'hôte applicatif,
...                 et l'adresse IP est mesurée volatile : seules la release et
...                 le kernel les distinguent. La garde vit dans le Suite Setup,
...                 donc aucun fichier n'est écrit sur refus.
...                 2. *La complétude.* Le relevé est confronté à un total
...                 mesuré par une source indépendante du lecteur, dans le Suite
...                 Setup lui aussi. Un refus qui constate après coup n'empêche
...                 rien : sur un relevé amputé, les cinq écritures passent au
...                 vert, puisque comparer une lecture partielle à elle-même ne
...                 rougit jamais.
...                 3. *La fidélité.* Chaque fichier écrit est RELU et confronté
...                 ligne à ligne au relevé lu sur la cible. Un fichier qui
...                 existe et pèse le bon nombre d'octets n'est pas un fichier
...                 juste, et ce tableau porte trois colonnes à zéros de tête et
...                 deux dates ABAP brutes qu'un retypage détruirait en silence.
...
...                 Le canal est **optionnel** : sur un poste sans `pyrfc`
...                 (aucune roue précompilée au-delà de Python 3.12) ou sans
...                 runtime natif NW RFC, la suite se SAUTE en nommant la cause
...                 et son remède, au lieu de rougir là où rien n'est cassé.
...
...                 **Prérequis.** Un interpréteur 3.10 à 3.12 portant `pyrfc`,
...                 un runtime NW RFC, le système applicatif joignable, et le
...                 jeu de données de démonstration présent (la campagne ne le
...                 régénère pas : elle exige un plancher et échoue en le
...                 nommant). Le module de comptage doit être appelable à
...                 distance ; son absence n'est pas une panne de connexion, et
...                 le message de repli le dit en nommant les deux sources de
...                 total de remplacement.
...
...                 Exemple :
...                 | robot --pythonpath src --include rfc
...                 | ...   -v "RFC_PASSWORD: Secret:***"
...                 | ...   --outputdir results/rfc-extraction
...                 | ...   tests/robot/api/extraction_tableau_rfc_a4h.robot
...
...                 Viser l'autre release du banc : `-v EXPECTED_RELEASE:758
...                 -v PEER_RELEASE:754`, et le refus du Suite Setup donne
...                 lui-même cette ligne. Pour une vue courte du document
...                 vectoriel, `-v MAX_ROWS:50` : la troncature est alors
...                 DEMANDÉE, annoncée en pied de document et portée par le
...                 verdict d'écriture.

Resource            ../../../resources/rfc_keywords.resource
Resource            ../../../resources/api_keywords.resource
Resource            ../../../resources/table_export_keywords.resource

Suite Setup         Ouvrir Le Canal Et Preparer Le Releve
Suite Teardown      Fermer Les Canaux Et Le Prouver

Test Tags           rfc    extraction


*** Variables ***
# --- La cible. Aucun mot de passe par défaut (convention 11) : il entre en
# variable typée `Secret` par la ligne de commande, et la garde ne le MESURE
# jamais (un `Secret` refuse d'être mesuré, et l'erreur de garde masquerait
# alors le prérequis manquant).
${RFC_ASHOST}               localhost
${RFC_SYSNR}                00
${RFC_CLIENT}               001
${RFC_USER}                 DEVELOPER
${RFC_PASSWORD}             ${EMPTY}    # OBLIGATOIRE : -v "RFC_PASSWORD: Secret:<motdepasse>"
${RFC_LANG}                 EN
# Un alias propre à cette campagne, distinct de celui du canal OData qu'elle
# ouvre le temps du croisement.
${RFC_ALIAS}                bookings
${ODATA_ALIAS}              odata

# Les ancres d'identité. Ni l'identifiant système ni le nom d'hôte ne
# discriminent les deux conteneurs du banc, et l'adresse IP change au
# redémarrage : la release est donc l'ancre, et la release VOISINE la
# contre-épreuve.
${EXPECTED_RELEASE}         754
${PEER_RELEASE}             758
# Facultatif : deux conteneurs de MÊME release ne se distinguent que par leur
# kernel. Vide = non vérifié, et le scénario 1 le dit plutôt que de laisser
# croire que le risque est couvert.
${EXPECTED_KERNEL}          ${EMPTY}

# Le même système, vu par son canal OData : c'est le troisième canal du
# scénario 6.
${A4H_API_URL}              http://localhost:50000

# Le plafond de la contre-épreuve du scénario 4 : délibérément dérisoire devant
# le volume réel, pour que l'écart soit énorme et qu'AUCUNE ligne rendue ne le
# trahisse malgré tout.
${CEILING}                  ${3}

# L'oracle du refus du tampon de ligne, en clés techniques (convention 3) : un
# code et un identifiant de message ABAP, ni l'un ni l'autre localisé. Le code
# est stable mais grossier, l'identifiant désigne le refus exact : les deux se
# complètent, et la suite les asserte sur le MÊME chemin.
${CODE_TAMPON_DEPASSE}      DATA_BUFFER_EXCEEDED
${MESSAGE_TAMPON_DEPASSE}   AD/E/559

# --- Les sorties. Le préfixe se surcharge (`-v OUTPUT_PREFIX:...`), jamais
# l'identité : les noms de fichiers sont DÉRIVÉS de la cible mesurée dans le
# Suite Setup, sans quoi un fichier annoncerait un système qu'il ne porte pas.
${OUTPUT_PREFIX}            ${OUTPUT DIR}/sbook
# La virgule est la norme (RFC 4180) ; `-v CSV_DELIMITER:;` pour un Excel
# configuré en français, qui rendrait sinon une colonne unique.
${CSV_DELIMITER}            ,
# ${None} = tout le tableau. Une troncature n'est légitime que si elle a été
# DEMANDÉE : sans cela, cinq fichiers partiels seraient indiscernables d'un
# inventaire (seul le document vectoriel l'écrit dans le fichier).
${MAX_ROWS}                 ${None}
# 0 = aucune coupe. L'invariant de cette campagne est l'intégralité : une
# valeur coupée ne survivrait que dans l'infobulle du document.
${MAX_CELL_CHARS}           ${0}
${SHEET_NAME}               Flight bookings


*** Test Cases ***
La cible est bien le systeme attendu
    [Documentation]    Les deux conteneurs du banc partagent identifiant système
    ...    et nom d'hôte applicatif, et l'adresse IP est mesurée volatile :
    ...    extraire le mauvais système donnerait des fichiers parfaitement
    ...    lisibles, que rien dans les fichiers ne permettrait de démasquer.
    ...
    ...    **Ce que ce scénario mesure et que le Suite Setup n'impose PAS.** Le
    ...    Setup a déjà refusé la cible sur la release, sur la release voisine,
    ...    sur un kernel vide et sur la corroboration par le composant logiciel
    ...    de base : re-asserter ces quatre faits ici ne pourrait plus échouer,
    ...    puisque le Setup aurait avorté avant. Ce scénario porte donc trois
    ...    vérifications de plus, toutes falsifiables.
    ...
    ...    1. *Les deux sources d'identité du canal s'accordent.* Les attributs
    ...    de la CONNEXION viennent de la poignée de main RFC ; la fiche système
    ...    vient d'un module fonction exécuté par le serveur d'applications. Ce
    ...    sont deux couches différentes, et le Setup ne lit que la seconde.
    ...    2. *Le mandant servi existe vraiment sur ce système.* Comparer le
    ...    mandant rapporté au paramètre d'ouverture serait comparer une valeur à
    ...    elle-même ; le retrouver dans l'annuaire des mandants est une réponse
    ...    du SERVEUR, donc une assertion qui peut échouer.
    ...    3. *Le kernel ATTENDU*, quand l'opérateur en déclare un : deux
    ...    conteneurs de même release ne se distinguent que par lui. Vide par
    ...    défaut, et le dire vaut mieux que de laisser croire le risque couvert.
    ...
    ...    Les deux assertions de release restent, assumées comme une
    ...    CONFRONTATION de ce que le Setup a refusé, pas comme une mesure neuve.
    [Tags]    cible
    ${connexion}=    Read System Identity
    ${systeme}=    Read System Information
    Should Be Equal    ${connexion}[sysId]    ${systeme}[RFCSYSID]
    ...    msg=Les deux sources d'identité du canal ne s'accordent pas sur le système : la poignée de main annonce ${connexion}[sysId], le serveur d'applications ${systeme}[RFCSYSID].
    Should Be Equal    ${connexion}[partnerRel]    ${systeme}[RFCSAPRL]
    ...    msg=Les deux sources d'identité ne s'accordent pas sur la release : ${connexion}[partnerRel] contre ${systeme}[RFCSAPRL].
    Should Be Equal    ${connexion}[kernelRel]    ${systeme}[RFCKERNRL]
    ...    msg=Les deux sources d'identité ne s'accordent pas sur le kernel : ${connexion}[kernelRel] contre ${systeme}[RFCKERNRL].
    ${mandants}=    Read Installed Client Codes
    Should Contain    ${mandants}    ${RFC_CLIENT}
    ...    msg=Le mandant servi (${RFC_CLIENT}) ne figure pas dans l'annuaire des mandants du système (${mandants}) : la population lue ne serait pas celle attendue.
    IF    '${EXPECTED_KERNEL}' != '${EMPTY}'
        Should Be Equal    ${IDENTITE}[kernel]    ${EXPECTED_KERNEL}
        ...    msg=Le kernel mesuré (${IDENTITE}[kernel]) n'est pas celui attendu (${EXPECTED_KERNEL}) : même release, autre système.
    END
    # Confrontation de ce que le Setup a refusé le cas échéant : ces deux
    # assertions ne peuvent plus échouer ici, et c'est assumé.
    Should Be Equal    ${IDENTITE}[release]    ${EXPECTED_RELEASE}
    Should Not Be Equal    ${IDENTITE}[release]    ${PEER_RELEASE}
    ...    msg=La cible et la release voisine portent le même numéro : la contre-épreuve ne distingue plus rien.
    Log    Cible : ${IDENTITE}[system_id] mandant ${IDENTITE}[client] release ${IDENTITE}[release] kernel ${IDENTITE}[kernel] sur ${IDENTITE}[host] (${IDENTITE}[database], ${IDENTITE}[operating_system])

Le tableau des reservations est lu en entier et sa completude vient d une autre source que le lecteur
    [Documentation]    JUGE le relevé que le Suite Setup a produit, il ne le
    ...    produit pas : c'est ce qui rend chaque scénario jouable seul, et ce
    ...    qui évite qu'un échec en cascade désigne le mauvais coupable.
    ...
    ...    Le total est RELU ici, après coup : ce qui est vérifié est que la
    ...    table n'a pas bougé entre la mesure et la lecture. La complétude du
    ...    CONTENU, elle, est refusée au Suite Setup, seul endroit où le refus
    ...    empêche réellement d'écrire.
    ...
    ...    Ce que ce scénario NE prouve PAS : que le compteur dise vrai. Il dit
    ...    seulement que deux modules DIFFÉRENTS s'accordent, ce qui est déjà
    ...    hors de portée d'une garde qui comparerait une lecture à elle-même.
    ...    Le scénario 6 va chercher la preuve plus loin.
    [Tags]    lecture
    ${lues}=    Set Variable    ${EXTRAIT}[row_count]
    ${declarees}=    Count Declared Flight Bookings
    Should Be Equal As Integers    ${lues}    ${declarees}
    ...    msg=La table déclare maintenant ${declarees} lignes alors que ${lues} ont été lues : les deux mesures ne décrivent pas le même instant, donc aucune ne prouve l'autre.
    Should Be Equal As Integers    ${EXTRAIT}[declared_rows]    ${declarees}
    ...    msg=Le total porté par le relevé n'est plus celui que le compteur rend : le relevé et sa preuve ont divergé.
    Should Be Equal    ${EXTRAIT}[complete]    ${True}
    ...    msg=Le relevé ne se déclare pas complet (le Suite Setup aurait dû le refuser).
    Should Be Equal As Integers    ${EXTRAIT}[blank_rows]    ${0}
    ...    msg=Relevé creux : ${EXTRAIT}[blank_rows] ligne(s) entièrement vides.
    Should Be Equal As Integers    ${EXTRAIT}[keyless_rows]    ${0}
    ...    msg=${EXTRAIT}[keyless_rows] ligne(s) sans identifiant de réservation : la lecture est partielle là où le compte ne le montre pas.
    ${nb_colonnes}=    Get Length    ${EXTRAIT}[columns]
    Should Be True    ${nb_colonnes} >= ${MIN_BOOKING_COLUMNS}
    ...    msg=${nb_colonnes} colonne(s) seulement : l'extraction serait amputée.
    Should Be True    ${lues} >= ${MIN_BOOKINGS}
    ...    msg=${lues} ligne(s) seulement : le jeu de données de démonstration est-il présent ?
    # La DERNIÈRE ligne autant que la première : c'est elle qui manque quand une
    # lecture s'arrête en chemin, et elle porte sa clé comme les autres.
    Should Not Be Empty    ${EXTRAIT}[rows][0][${EXTRAIT}[key]]
    Should Not Be Empty    ${EXTRAIT}[rows][-1][${EXTRAIT}[key]]
    ...    msg=La dernière ligne du relevé n'a pas d'identifiant : la lecture s'est arrêtée en chemin.
    # Le résumé dit TOUJOURS le total déclaré, y compris quand il coïncide :
    # c'est ce qui distingue un journal qui prouve d'un journal qui rassure.
    ${resume}=    Describe Table Extract    ${EXTRAIT}
    Log    ${resume}

Le tableau est ecrit dans les cinq formats relu et confronte
    [Documentation]    Écrit le relevé sous une marque DÉRIVÉE de l'identité
    ...    mesurée, relit les quatre formats qui se relisent, confronte chacun
    ...    ligne à ligne au relevé lu sur la cible, et prouve le cinquième (le
    ...    seul sans lecteur) sur le document lui-même.
    ...
    ...    Ce que la confrontation attrape ici n'a rien de théorique : trois
    ...    colonnes de ce tableau portent des zéros de tête et deux portent des
    ...    dates ABAP brutes. Un retypage à l'écriture les détruirait sans que
    ...    ni le nombre de lignes, ni le poids du fichier, ni une relecture
    ...    humaine pressée ne bronchent.
    ...
    ...    Le document vectoriel à cette échelle est un test de charge, pas un
    ...    livrable à lire : vingt-huit mille lignes en font un document que
    ...    personne n'ouvre. Il est produit parce que l'invariant de la campagne
    ...    est l'intégralité ; la vue courte s'obtient en bornant le rendu, la
    ...    troncature étant alors DEMANDÉE et annoncée.
    [Tags]    formats
    ${bilan}=    Ecriture De Reference
    ${attendue}=    Evaluate    $MAX_ROWS is not None and int($MAX_ROWS) < ${EXTRAIT}[row_count]
    Should Be Equal    ${bilan}[tronque]    ${attendue}
    ...    msg=Les fichiers sont tronqués alors que rien ne le demandait (ou l'inverse).
    Should Be Equal    ${bilan}[colonnes]    ${EXTRAIT}[columns]
    ...    msg=Les fichiers ne portent pas les colonnes du relevé.
    Should Be True    ${bilan}[octets] > 0
    ...    msg=Les fichiers écrits ne pèsent rien.
    # Quatre formats au minimum : le cinquième est OPTIONNEL et se saute en
    # nommant son remède, au lieu de faire rougir une campagne pour un binding
    # absent. Son absence est annoncée en WARNING dans le journal.
    ${nb_formats}=    Get Length    ${bilan}[formats]
    Should Be True    ${nb_formats} >= 4
    ...    msg=Seulement ${nb_formats} format(s) écrits : ${bilan}[formats].
    Log    Cinq formats écrits sous ${MARQUE} : ${bilan}[formats], ${bilan}[lignes] ligne(s), ${bilan}[colonnes] colonne(s), ${bilan}[octets] octets au total.
    Log Dictionary    ${bilan}[fichiers]

Le plafond silencieux est refuse alors qu aucune ligne ne le trahit
    [Documentation]    La contre-épreuve, jouée sur la cible RÉELLE et non sur
    ...    une doublure. Les trois assertions sont dans cet ordre parce que
    ...    l'ordre EST le scénario : l'écart existe, les lignes ne le trahissent
    ...    en rien, la garde refuse quand même.
    ...
    ...    Prouver seulement que la garde refuse laisserait croire qu'un
    ...    contrôle de contenu aurait pu faire l'affaire. C'est l'assertion du
    ...    milieu, celle qui constate qu'AUCUN témoin n'existe, qui justifie
    ...    tout le dispositif : les lignes rendues sont exactement les
    ...    premières du relevé complet, propres et ordonnées.
    ...
    ...    **Une prémisse, nommée pour qu'elle ne passe pas pour un acquis.**
    ...    L'égalité de préfixe suppose que deux lectures INDÉPENDANTES, dont
    ...    l'une bornée, rendent les lignes dans le même ordre. Le canal n'offre
    ...    aucune clause de tri et ne garantit donc rien : la propriété a été
    ...    MESURÉE sur cette cible (plan, « Données observées », point 11) et
    ...    elle y tient, mais elle reste une observation. C'est pourquoi une
    ...    seconde assertion, elle INDÉPENDANTE de l'ordre, l'accompagne : les
    ...    identifiants bornés sont inclus dans ceux du relevé complet. Si
    ...    l'ordre dérivait un jour, c'est l'égalité de préfixe qui tomberait,
    ...    l'inclusion tiendrait, et le diagnostic serait immédiat au lieu
    ...    d'accuser la troncature.
    ...
    ...    Aucun fichier n'est écrit depuis ce relevé.
    [Tags]    contre-epreuve
    ${borne}=    Extract Flight Bookings With Ceiling    ${CEILING}
    # 1. L'écart existe, et il est énorme.
    Should Be Equal As Integers    ${borne}[row_count]    ${CEILING}
    Should Be Equal As Integers    ${borne}[declared_rows]    ${EXTRAIT}[declared_rows]
    ...    msg=Le total déclaré a changé entre les deux lectures : la contre-épreuve ne porterait plus sur la même population.
    ${manquantes}=    Evaluate    ${borne}[declared_rows] - ${CEILING}
    Should Be Equal As Integers    ${borne}[missing_rows]    ${manquantes}
    ...    msg=Le nombre de lignes manquantes n'est pas cohérent avec le total.
    Should Be Equal    ${borne}[complete]    ${False}
    ...    msg=Un relevé amputé de ${manquantes} lignes se déclare complet.
    # 2. RIEN dans les lignes rendues ne le trahit. Ni ligne vide, ni clé
    # manquante, ni identifiant en double : ce sont EXACTEMENT les premières
    # lignes du relevé complet, dans le même ordre.
    Should Be Equal As Integers    ${borne}[blank_rows]    ${0}
    ...    msg=Le relevé borné porte des lignes vides : il se trahirait, et la démonstration n'aurait plus lieu d'être.
    Should Be Equal As Integers    ${borne}[keyless_rows]    ${0}
    ...    msg=Le relevé borné porte des lignes sans clé : il se trahirait.
    ${cles}=    Get Values From Dicts    ${borne}[rows]    ${borne}[key]
    List Should Not Contain Value    ${cles}    ${EMPTY}
    ...    msg=Un identifiant vide parmi les lignes rendues.
    ${uniques}=    Remove Duplicates    ${cles}
    Length Should Be    ${uniques}    ${CEILING}
    ...    msg=Les identifiants rendus ne sont pas tous distincts.
    # Indépendante de l'ordre, donc vraie quoi que fasse la base : les lignes
    # bornées appartiennent au relevé complet, elles n'ont pas été inventées.
    ${cles_completes}=    Get Values From Dicts    ${EXTRAIT}[rows]    ${EXTRAIT}[key]
    FOR    ${cle}    IN    @{cles}
        Should Contain    ${cles_completes}    ${cle}
        ...    msg=L'identifiant ${cle} rendu par la lecture bornée est absent du relevé complet : les deux lectures ne portent pas sur la même population.
    END
    # Dépendante de l'ordre, et c'est une PRÉMISSE mesurée sur cette cible, pas
    # une garantie du canal (aucune clause de tri n'existe ici). Elle est
    # doublée par l'inclusion ci-dessus : si l'ordre dérive, c'est cette
    # assertion-ci qui tombe, et son message le dit.
    ${prefixe}=    Get Slice From List    ${EXTRAIT}[rows]    0    ${CEILING}
    Lists Should Be Equal    ${borne}[rows]    ${prefixe}
    ...    msg=Les lignes bornées ne sont pas les PREMIÈRES du relevé complet. L'inclusion ayant tenu juste au-dessus, les deux lectures portent bien sur la même population : c'est donc l'ORDRE qui a dérivé entre elles, ce que le canal ne garantit pas (aucune clause de tri) et que le plan consigne comme une observation. Ce n'est PAS un défaut de la troncature.
    # 3. La garde partagée refuse quand même, et son refus nomme la cause.
    ${refus}=    Run Keyword And Expect Error    *
    ...    Table Extract Should Be Complete    ${borne}    min_rows=${MIN_BOOKINGS}
    ...    min_columns=${MIN_BOOKING_COLUMNS}
    Should Contain    ${refus}    REFUSÉ
    ...    msg=Le refus ne s'annonce pas comme un refus.
    Should Contain    ${refus}    il en manque
    ...    msg=Le refus ne nomme pas la cause : des lignes manquantes.
    Log    Plafond ${CEILING} sur ${borne}[declared_rows] lignes : ${borne}[blank_rows] ligne(s) vide(s), ${borne}[keyless_rows] sans clé, donc AUCUN témoin, et pourtant refusé.

Une lecture filtree sans total mesure est refusee avant tout appel reseau
    [Documentation]    Le seul endroit où le canal RFC diffère vraiment des trois
    ...    autres. Les autres canaux déclarent un total qui décrit exactement ce
    ...    qu'ils ont rendu ; celui-ci offre un total qui décrit parfois une
    ...    AUTRE population, puisque le compteur mesure la table entière et
    ...    n'accepte aucune clause de sélection. Les apparier annoncerait des
    ...    lignes manquantes qui n'ont jamais existé.
    ...
    ...    Le refus est à l'ENTRÉE, avant le moindre aller-retour : un refus qui
    ...    constate n'empêche rien. Il est jugé sur sa classe d'erreur et sur la
    ...    présence des remèdes, jamais sur sa prose complète.
    ...
    ...    La seconde moitié vérifie que la sortie de secours FONCTIONNE, et
    ...    elle ne prouve rien d'autre : le total qu'elle fournit vient du module
    ...    qui LIT, faute de pouvoir filtrer un comptage serveur, donc la
    ...    complétude qui en découle serait une comparaison d'une lecture avec
    ...    elle-même. Elle n'est délibérément pas assertée ici ; c'est le
    ...    scénario suivant qui va chercher un total vraiment indépendant.
    [Tags]    refus
    ${erreur}=    Extracting A Filtered Table Without A Total Should Be Refused
    Should Contain    ${erreur}    clause de sélection
    ...    msg=Le refus ne nomme pas la cause : le compteur ignore les clauses de sélection.
    Should Contain    ${erreur}    retirer le filtre
    ...    msg=Le refus ne nomme pas la première sortie honnête.
    Should Contain    ${erreur}    declared_rows=
    ...    msg=Le refus ne nomme pas la seconde sortie honnête.
    Should Contain    ${erreur}    $count
    ...    msg=Le refus ne nomme pas une source de total de remplacement.
    # La sortie de secours fonctionne : la même lecture filtrée est acceptée
    # dès qu'un total lui est fourni.
    ${total}=    Count Filtered Products
    Should Be True    ${total} > 0
    ...    msg=La clause de sélection ne ramène aucune ligne : la démonstration porterait sur du vide.
    ${filtre}=    Extract Product Catalogue    declared_rows=${total}
    ...    filter=${PRODUCT_CATEGORY_FILTER}
    Should Be Equal As Integers    ${filtre}[row_count]    ${total}
    Should Contain    ${filtre}[source]    filtre
    ...    msg=Le libellé de provenance ne dit pas que la lecture était filtrée : le lecteur du relevé ne saurait pas sur quelle population il porte.
    Log    Refus puis acceptation : ${filtre}[source]

La completude est prouvee par un troisieme canal
    [Documentation]    La preuve la plus forte que ce dépôt sache produire sur
    ...    une complétude : ni le module qui LIT, ni le module qui COMPTE ne
    ...    participent à l'établissement du total. Il vient d'un service OData,
    ...    c'est-à-dire d'un protocole qui ne passe même pas par le RFC.
    ...
    ...    Trois chemins techniques distincts disent alors le même nombre, et le
    ...    recoupement des deux compteurs entre eux vient par-dessus.
    ...
    ...    Le mandant doit être le MÊME des deux côtés : les faire diverger
    ...    comparerait deux populations et fabriquerait un écart qui n'existe
    ...    pas. Le compteur serveur suit le mandant de la connexion.
    ...
    ...    **Ce que le contrôle de mandant vaut vraiment.** Il relit le mandant
    ...    MÉMORISÉ à l'ouverture du canal OData, ouverture qui a reçu celui de
    ...    la connexion RFC : il vérifie donc que les deux canaux ont été
    ...    CONFIGURÉS sur le même mandant, et rien de plus. Le serveur ne le
    ...    confirme pas, et le présenter comme une garde contre une comparaison
    ...    truquée serait surestimer une égalité qui ne peut pas échouer. La
    ...    vraie preuve est ailleurs, dans l'ACCORD des trois nombres : trois
    ...    chemins techniques distincts qui liraient des populations différentes
    ...    n'auraient aucune raison de tomber sur le même total.
    ...
    ...    Le premier appel OData d'un service jamais sollicité sur un système
    ...    froid peut être lent : ce n'est pas une panne, d'où le préflight
    ...    patient avant le comptage.
    [Tags]    croisement
    [Teardown]    Close Api Session    alias=${ODATA_ALIAS}
    Open Api Channel    base_url=${A4H_API_URL}    user=${RFC_USER}
    ...    password=${RFC_PASSWORD}    client=${RFC_CLIENT}    alias=${ODATA_ALIAS}
    Wait Until Api Channel Is Available    alias=${ODATA_ALIAS}    timeout=60s
    # Contrôle de CONFIGURATION, pas de serveur : le mandant relu est celui
    # mémorisé à l'ouverture. Il attrape une surcharge de variable incohérente,
    # rien de plus, et c'est tout ce qu'il prétend faire.
    ${mandant}=    Api Channel Client    alias=${ODATA_ALIAS}
    Should Be Equal    ${mandant}    ${RFC_CLIENT}
    ...    msg=Les deux canaux ont été CONFIGURÉS sur des mandants différents (${mandant} contre ${RFC_CLIENT}) : ils liraient deux populations.
    ${par_odata}=    Count Business Entities    ${EPM_PRODUCTS}    alias=${ODATA_ALIAS}
    Should Be True    ${par_odata} > 0
    ...    msg=Le troisième canal ne compte aucune entité : rien à croiser.
    ${extrait}=    Extract Product Catalogue    declared_rows=${par_odata}
    Table Extract Should Be Complete    ${extrait}    min_rows=${MIN_PRODUCTS}
    ...    min_columns=${MIN_PRODUCT_COLUMNS}
    Should Be Equal As Integers    ${extrait}[row_count]    ${par_odata}
    ...    msg=Le canal RFC lit ${extrait}[row_count] ligne(s) là où le troisième canal en compte ${par_odata}.
    Should Be Equal    ${extrait}[complete]    ${True}
    Should Be Equal As Integers    ${extrait}[missing_rows]    ${0}
    Should Be Equal As Integers    ${extrait}[blank_rows]    ${0}
    Should Be Equal As Integers    ${extrait}[keyless_rows]    ${0}
    # Par-dessus : les deux COMPTEURS, indépendants l'un de l'autre, s'accordent.
    ${par_module}=    Count Declared Products
    Should Be Equal As Integers    ${par_module}    ${par_odata}
    ...    msg=Les deux compteurs indépendants divergent : ${par_module} par le compteur serveur contre ${par_odata} par le troisième canal.
    ${resume}=    Describe Table Extract    ${extrait}
    # La PREUVE du scénario tient en cette ligne, et pas dans le contrôle de
    # mandant : trois chemins techniques distincts, dont un qui ne passe même
    # pas par le protocole RFC, disent le même nombre. Deux d'entre eux ne
    # sauraient pas tomber d'accord en lisant des populations différentes.
    Log    Trois chemins, un seul nombre : ${extrait}[row_count] lu par le module de lecture, ${par_module} par le compteur serveur, ${par_odata} par le troisième canal. ${resume}

Deux ecritures de la meme mesure sont identiques a l octet pres
    [Documentation]    Écrit une seconde fois, sous une autre marque, le relevé
    ...    déjà écrit, puis confronte les fichiers des deux passages format par
    ...    format, sur leur CONTENU et non sur leur seule taille.
    ...
    ...    Ce que le déterminisme achète, et pourquoi il vaut un scénario : il
    ...    fait d'une différence entre deux extractions une information sur le
    ...    SYSTÈME. Sans lui, comparer l'extraction d'aujourd'hui à celle du mois
    ...    dernier ne distingue pas un paramètre qui a bougé d'un horodatage qui
    ...    a changé. Aucune date, aucun chemin, aucun identifiant de run ne doit
    ...    entrer dans un fichier produit.
    ...
    ...    Le contrôle a déjà mordu sur ce dépôt : le sous-titre d'un document y
    ...    portait le répertoire de sortie, et deux passages dans deux dossiers
    ...    rendaient des documents différents pendant que les autres formats
    ...    restaient identiques à l'octet près.
    [Tags]    determinisme
    ${premier}=    Ecriture De Reference
    ${second}=    Exporter Le Releve Vers Les Cinq Formats    ${EXTRAIT}    ${MARQUE_BIS}
    ...    sheet_name=${SHEET_NAME}    csv_delimiter=${CSV_DELIMITER}
    ...    max_rows=${MAX_ROWS}    max_cell_chars=${MAX_CELL_CHARS}
    ...    subtitle=${SOUS_TITRE}
    ${formats}=    Les Deux Ecritures Devraient Etre Identiques A L Octet Pres
    ...    ${premier}    ${second}
    Log    ${formats} : deux passages identiques à l'octet près, pour ${second}[lignes] ligne(s) et ${second}[octets] octets par passage.


Une projection plus large que le tampon de ligne est refusee par son code
    [Documentation]    Le dernier refus du canal que la campagne ne savait pas
    ...    provoquer, et l'explication du trou vaut le scénario à elle seule.
    ...
    ...    **Pourquoi la campagne restait sous le tampon sans le vouloir.** Le
    ...    module borne la LIGNE PROJETÉE, pas la table ni le nombre de lignes.
    ...    Or le tableau des réservations, celui du relevé à l'échelle, tient
    ...    ENTIER très largement sous la limite : aucune projection de lui, même
    ...    complète, ne peut déborder. Extraire 28 782 lignes ne prouvait donc
    ...    rien de ce refus, et le croire éprouvé aurait été le lire de travers.
    ...    La seule table du laboratoire qui déborde est le catalogue des
    ...    produits, que la campagne connaît déjà.
    ...
    ...    **Rien n'est gravé.** La projection complète et la largeur sont
    ...    DÉRIVÉES du dictionnaire : une release qui ajoute un champ reste
    ...    couverte, et la largeur est mesurée au lieu d'être supposée. Sur une
    ...    cible dont la table large passerait sous la limite, le scénario se
    ...    SAUTE en le disant, parce qu'il ne prouverait plus rien.
    ...
    ...    **La contre-épreuve est indispensable.** Sans elle, ce scénario ne
    ...    distinguerait pas « la largeur mord » de « cette table est
    ...    illisible » : la MÊME table, lue en projection étroite, passe et rend
    ...    un relevé complet.
    ...
    ...    Aucun fichier n'est écrit depuis ce chemin.
    [Tags]    refus    tampon
    ${large}=    Measure Wide Table Row Width
    ${reservations}=    Measure Booking Table Row Width
    # La prémisse du scénario, MESURÉE : sans dépassement, il ne prouve rien.
    Skip If    ${large}[width] <= ${ROW_BUFFER_LIMIT}
    ...    La table large de cette cible tient en ${large}[width] octets par ligne, sous le tampon de ${ROW_BUFFER_LIMIT} : sa projection complète passerait, et le refus ne serait pas éprouvé. Branche sautée, elle n'est pas déclarée verte.
    Should Be True    ${reservations}[width] < ${ROW_BUFFER_LIMIT}
    ...    msg=Le tableau du relevé à l'échelle fait ${reservations}[width] octets par ligne : il pourrait déborder, et l'explication du trou (une table trop étroite pour le provoquer) ne tient plus.
    # Le refus, jugé sur son CODE puis sur son IDENTIFIANT DE MESSAGE. Jamais
    # sur le texte du serveur, qui est localisé ou verbeux (convention 3).
    ${par_code}=    Extracting Beyond The Row Buffer Should Be Refused With Code
    ...    ${CODE_TAMPON_DEPASSE}    ${large}[fields]
    ${par_id}=    Extracting Beyond The Row Buffer Should Be Refused With Message Id
    ...    ${MESSAGE_TAMPON_DEPASSE}    ${large}[fields]
    Should Be Equal    ${par_code}[code]    ${CODE_TAMPON_DEPASSE}
    Should Be Equal    ${par_id}[message_id]    ${MESSAGE_TAMPON_DEPASSE}
    # La contre-épreuve : MÊME table, projection étroite, relevé complet.
    ${etroite}=    Extract Product Catalogue
    Should Be True    ${etroite}[row_count] > 0
    ...    msg=La projection étroite ne rend aucune ligne : la table serait illisible, et le refus précédent ne dirait rien de la largeur.
    Should Be Equal    ${etroite}[complete]    ${True}
    ...    msg=La projection étroite ne rend pas un relevé complet : le refus large ne peut alors pas être imputé à la seule largeur.
    Log    Tampon de ${ROW_BUFFER_LIMIT} octets : projection complète ${large}[field_count] champs / ${large}[width] octets REFUSÉE (${par_code}[code], ${par_id}[message_id]) ; projection étroite acceptée, ${etroite}[row_count] ligne(s). Le tableau des réservations, lui, fait ${reservations}[width] octets par ligne et ne peut pas déborder.


*** Keywords ***
Ouvrir Le Canal Et Preparer Le Releve
    [Documentation]    Saute la campagne là où le canal n'existe pas, ouvre le
    ...    canal, PROUVE la cible, puis produit le relevé une fois pour toutes.
    ...
    ...    **Pourquoi les deux gardes vivent ICI et pas seulement dans un
    ...    scénario.** Une garde qui constate après coup ne protège rien : un
    ...    scénario qui rougit n'empêche pas les suivants d'écrire. Sur une
    ...    cible refusée, les fichiers du mauvais système partiraient sous des
    ...    noms annonçant le bon ; sur un relevé amputé, les cinq écritures
    ...    passeraient au vert, puisque comparer une lecture partielle à
    ...    elle-même ne rougit jamais. Refuser doit EMPÊCHER, pas commenter.
    Skip Unless Rfc Channel Is Available
    Open Rfc Channel
    ${identite}=    Rfc Target Should Be Release    ${EXPECTED_RELEASE}
    ...    peer_release=${PEER_RELEASE}
    Set Suite Variable    ${IDENTITE}    ${identite}
    # Les noms portent la cible MESURÉE, jamais une constante d'écriture.
    ${marque}=    Set Variable
    ...    ${OUTPUT_PREFIX}_${identite}[system_id]_${identite}[client]_${identite}[release]
    Set Suite Variable    ${MARQUE}    ${marque}
    Set Suite Variable    ${MARQUE_BIS}    ${marque}_second_passage
    # Le sous-titre porte l'identité de la CIBLE et jamais le chemin de sortie :
    # un document dont le sous-titre contient son propre dossier n'est plus
    # déterministe, et deux extractions de la même donnée cessent d'être
    # comparables. Tout ce qui varie avec l'endroit d'où l'on joue reste DEHORS.
    Set Suite Variable    ${SOUS_TITRE}
    ...    ${identite}[system_id] mandant ${identite}[client] ${BASE_SOFTWARE_COMPONENT} ${identite}[release] kernel ${identite}[kernel]
    Preparer Le Releve

Preparer Le Releve
    [Documentation]    Extrait le tableau des réservations UNE fois, pour toute
    ...    la suite, et REFUSE tout relevé incomplet avant qu'un seul fichier ne
    ...    soit écrit.
    ...
    ...    Le relevé vit ici et non dans un scénario pour que chaque scénario
    ...    reste jouable seul et qu'aucun ne rougisse en cascade sur une variable
    ...    qu'un autre n'a pas posée : ce genre d'échec désigne le mauvais
    ...    coupable.
    ...
    ...    Le plancher de lignes n'est PAS décoratif sur ce canal : le compteur
    ...    annonce une table INEXISTANTE à zéro au lieu de la refuser, donc un
    ...    relevé vide confronté à un total de zéro franchit toutes les égalités
    ...    de la garde et se déclare complet. C'est le seul endroit de la chaîne
    ...    où une faute de frappe sur un nom de table produit un résultat vert.
    ${extrait}=    Extract Flight Bookings
    ${resume}=    Describe Table Extract    ${extrait}
    Log    ${resume}
    Table Extract Should Be Complete    ${extrait}    min_rows=${MIN_BOOKINGS}
    ...    min_columns=${MIN_BOOKING_COLUMNS}
    Set Suite Variable    ${EXTRAIT}    ${extrait}

Ecriture De Reference
    [Documentation]    Le PREMIER passage d'écriture, produit une seule fois et
    ...    mémorisé. Le scénario des formats le produit, celui du déterminisme
    ...    le compare : la mémorisation est ce qui laisse jouer l'un ou l'autre
    ...    SEUL sans écrire deux fois, ni dépendre de l'ordre d'exécution.
    ${cache}=    Get Variable Value    ${BILAN_REFERENCE}    ${NONE}
    IF    $cache is not None    RETURN    ${cache}
    ${bilan}=    Exporter Le Releve Vers Les Cinq Formats    ${EXTRAIT}    ${MARQUE}
    ...    sheet_name=${SHEET_NAME}    csv_delimiter=${CSV_DELIMITER}
    ...    max_rows=${MAX_ROWS}    max_cell_chars=${MAX_CELL_CHARS}
    ...    subtitle=${SOUS_TITRE}
    Set Suite Variable    ${BILAN_REFERENCE}    ${bilan}
    RETURN    ${bilan}

Fermer Les Canaux Et Le Prouver
    [Documentation]    Referme les deux canaux, même sur échec, et RELIT l'état
    ...    réel pour le prouver. Une connexion RFC orpheline est une session
    ...    utilisateur restée ouverte côté serveur : la refermer est la seule
    ...    chose que cette campagne ait à rendre à son état initial, puisqu'elle
    ...    n'écrit rien dans le système.
    ...
    ...    L'état est relu et non supposé : c'est la même exigence que partout
    ...    ailleurs ici, une intention n'est pas une mesure.
    Close Rfc Channel
    Close Api Channel
    ${ouverts}=    List Open Rfc Channels
    Should Be Empty    ${ouverts}
    ...    msg=Des connexions RFC survivent au teardown (${ouverts}) : autant de sessions utilisateur laissées ouvertes côté serveur.
