*** Settings ***
Documentation       **EXEMPLE À PERSONNALISER** : ce fichier porte le vocabulaire
...                 métier du LABORATOIRE de ce dépôt (identifiants, chemins, noms
...                 de tables et de services relevés live sur SES cibles). Beaucoup
...                 s'y réutilise tel quel sur un autre système (écrans et services
...                 standard), mais rien n'y fait autorité : à VÉRIFIER sur votre
...                 cible et à adapter à votre métier. Ce qui fait foi partout,
...                 c'est `src/`, les bibliothèques, qui portent les capacités :
...                 voir `resources/README.md`.
...
...                 Vocabulaire métier du **produit EPM vu par trois canaux
...                 indépendants** (plan `specs/cycle-vie-produit-epm-api-webgui-rfc.md`) :
...                 le service OData v2 `SEPMRA_PROD_MAN` côté API, l'écran SE16
...                 côté WebGUI, `RFC_READ_TABLE` côté RFC. Les trois lisent la
...                 MÊME table (`SNWD_PD`), et c'est ce que ce fichier rend
...                 visible : la table est déclarée UNE fois et passée
...                 explicitement aux trois lectures, pour qu'on ne puisse pas
...                 croiser sans s'en apercevoir deux populations différentes
...                 (le piège mesuré le 2026-08-28 sur les deux catalogues de
...                 compagnies aériennes, où l'écart de deux lignes était
...                 parfaitement reproductible et n'avait aucune cause).
...
...                 **LECTURE SEULE de bout en bout.** Aucun keyword d'écriture
...                 ici, et ce n'est pas une précaution de confort : mesuré le
...                 2026-09-21, ce service refuse l'activation ET la suppression
...                 d'un brouillon sur les DEUX systèmes du banc
...                 (`CM_EPM_REF_APPS/002`, « Object node type DemoObject does
...                 not exist »), constat qui a survécu à un redémarrage du
...                 conteneur puis à une restauration d'image antérieure. Un
...                 cycle d'écriture y serait donc IRRÉVERSIBLE, et chaque
...                 passage laisserait une entité définitive dans un système
...                 partagé. La table n'est pas davantage écrivable par écran
...                 (`MAINFLAG` vide dans `DD02L`) : c'est une restriction du
...                 dictionnaire, valable quel que soit le canal.
...
...                 Compose les trois vocabulaires de canal existants
...                 (`api_keywords`, `rfc_keywords`, `fiori_keywords` pour le
...                 WebGUI) : convention 1, aucun chemin de service, nom de
...                 table ni SID ne doit fuir dans une suite.

Library             Collections
Library             String
# Primitives pures atteintes par un KEYWORD (décision DDIC 2026-08-17) : la
# notation décimale de l'utilisateur, qui décode le prix TEL QU'UN ÉCRAN
# L'AFFICHE. Voir `Technical Price From Screen Text` pour le piège qu'elle
# ferme, et surtout pour celui qu'elle ouvrirait si on l'appliquait partout.
Library             sapfx_common.user_formats
Resource            ../api_keywords.resource
Resource            ../rfc_keywords.resource
Resource            ../fiori_keywords.resource


*** Variables ***
# --- Canal API : le service et son entity set (convention 1) ---------------
${EPM_PROD_MAN_SERVICE}         /sap/opu/odata/sap/SEPMRA_PROD_MAN
${EPM_PRODUCT_ENTITY_SET}       SEPMRA_C_PD_Product
# L'entity set est DRAFT-ENABLED : une lecture non filtrée agrège les
# brouillons, et ce banc en porte plusieurs, orphelins et non supprimables
# (relevés live le 2026-09-21). Toute lecture passe donc par ce filtre, sans
# exception : c'est lui qui fait la différence entre le catalogue et un état
# transitoire abandonné par quelqu'un d'autre.
${EPM_ACTIVE_ONLY}              IsActiveEntity eq true
# Les champs du canal API. Nommés `..._FIELD` et jamais `..._KEY` : un nom en
# `KEY` dans un artefact committé est refusé par la garde d'identifiants
# (convention 11), et elle a raison de ne pas faire la différence, puisqu'un
# lecteur ne la fait pas non plus entre « champ clé » et « clé d'API ».
${EPM_PRODUCT_API_ID_FIELD}         Product
${EPM_PRODUCT_API_PRICE_FIELD}      Price
${EPM_PRODUCT_API_CURRENCY_FIELD}   Currency

# --- La table que les TROIS canaux lisent (déclarée une seule fois) --------
${EPM_PRODUCT_TABLE}            SNWD_PD
${EPM_PRODUCT_KEY_COLUMN}       PRODUCT_ID
${EPM_PRICE_COLUMN}             PRICE
${EPM_CURRENCY_COLUMN}          CURRENCY_CODE
${EPM_PRODUCT_COLUMNS}          PRODUCT_ID,PRICE,CURRENCY_CODE

# --- Formats de l'utilisateur : lus sur le système, jamais supposés --------
# La notation décimale vit dans les valeurs par défaut de l'utilisateur. La
# lire est ce qui rend la comparaison de prix indépendante du poste ET de la
# locale : sur ce banc `DEVELOPER` porte une notation vide (donc `1.234,50`),
# et un autre utilisateur du même système rendrait `1,234.50` pour le même
# prix, sans qu'aucune donnée n'ait bougé.
${USER_DEFAULTS_TABLE}          USR01
${USER_DEFAULTS_KEY_FIELD}      BNAME
${USER_DECIMAL_FIELD}           DCPFM

# --- Documents de modification : le catalogue et les postes ----------------
${CHANGE_OBJECT_CATALOGUE}      TCDOB
# Le champ qui porte la classe d'objet s'appelle `OBJECT`, et non `OBJECTCLAS`
# comme son nom le suggérerait (confirmé via `DD03L` le 2026-09-21).
${CHANGE_OBJECT_FIELDS}         OBJECT,TABNAME
${CHANGE_ITEM_TABLE}            CDPOS
${CHANGE_ITEM_FIELDS}           OBJECTCLAS,TABNAME,FNAME

# --- Composant qui porte la release : l'ancre d'identité de la cible -------
# Ni l'identifiant système ni le nom d'hôte ne discriminent les deux systèmes
# du banc (les deux annoncent `A4H` / `vhcala4hci`) : seule la release le
# fait, avec le volume du catalogue Gateway.
${EPM_BASE_COMPONENT}           SAP_BASIS


*** Keywords ***
# ------------------------------------------------------- Ouverture / clôture

Open Epm Product Api Channel
    [Documentation]    Ouvre le canal API sur la cible et vérifie que la
    ...    Gateway répond AVANT toute lecture métier : un service inactif
    ...    répond par une page d'erreur que rien ne distingue d'une donnée
    ...    absente.
    [Arguments]    ${base_url}    ${user}    ${password}    ${client}
    ...    ${alias}=${API_ALIAS}
    Open Api Channel    base_url=${base_url}    user=${user}
    ...    password=${password}    client=${client}    alias=${alias}
    Api Channel Should Be Available    alias=${alias}

Open Epm Product Rfc Channel
    [Documentation]    Ouvre le canal RFC, après le saut propre qui rend la
    ...    campagne neutre là où le canal n'existe pas (`pyrfc` absent, ou
    ...    binding natif absent : deux causes, deux remèdes).
    [Arguments]    ${ashost}    ${sysnr}    ${client}    ${user}    ${password}
    ...    ${alias}=${RFC_ALIAS}
    Skip Unless Rfc Channel Is Available
    Open Rfc Channel    alias=${alias}    ashost=${ashost}    sysnr=${sysnr}
    ...    client=${client}    user=${user}    password=${password}

Open Epm Product Webgui Session
    [Documentation]    Ouvre la session WebGUI et rend l'identité lue dans le
    ...    bandeau (attendue, pas lue à la volée : le bandeau se rend APRÈS
    ...    les premiers éléments de la page).
    [Arguments]    ${url}    ${user}    ${password}    ${strategy}=form
    ${identite}=    Open WebGui Session    ${url}    ${user}    ${password}
    ...    strategy=${strategy}
    RETURN    ${identite}

Read Epm Webgui Address
    [Documentation]    L'adresse RÉELLEMENT atteinte par le navigateur, seul
    ...    discriminant de cible disponible sur ce canal.
    ...
    ...    L'identité du bandeau ne discrimine rien : les deux systèmes du banc
    ...    annoncent le même identifiant système (`A4H`) et le même nom d'hôte
    ...    interne (`vhcala4hci`), et la zone info ne porte ni release ni
    ...    kernel. Or l'ICF sait REDIRIGER vers ce nom d'hôte partagé, donc
    ...    viser le mauvais port peut ouvrir une session parfaitement
    ...    fonctionnelle sur l'AUTRE système (mesuré le 2026-08-24). L'adresse
    ...    atteinte est ce qui reste pour le constater.
    ${ou}=    Get Page Location
    RETURN    ${ou}

Close Epm Product Channels
    [Documentation]    Ferme les trois canaux, sur TOUS les chemins, y compris
    ...    après un échec en cours de campagne. Chaque fermeture est tentée
    ...    même si la précédente a échoué : un teardown qui s'arrête à la
    ...    première erreur laisse derrière lui exactement ce qu'il devait
    ...    nettoyer.
    ...
    ...    Le budget WebGUI est COURT et c'est délibéré : un déroulé de
    ...    déconnexion qui ne peut pas aboutir sur une cible donnée a déjà
    ...    coûté 361 s d'acharnement, soit les deux tiers d'une campagne
    ...    entière (mesuré le 2026-09-15). Un teardown doit rendre la main.
    [Arguments]    ${webgui_budget}=10s
    Run Keyword And Ignore Error    Close WebGui    logoff_budget=${webgui_budget}
    Run Keyword And Ignore Error    Close Rfc Channel
    Run Keyword And Ignore Error    Close Api Channel

# -------------------------------------------------------- Preuve de la cible

Read Epm Target Release
    [Documentation]    La release du composant de base, lue par le canal RFC.
    ...    Le discriminant des deux systèmes du banc, là où l'identifiant
    ...    système et le nom d'hôte sont IDENTIQUES sur les deux (mesuré le
    ...    2026-08-28) : viser le mauvais port ouvre une session parfaitement
    ...    fonctionnelle sur l'autre système, et tout ce qu'on en lit est
    ...    lisible et faux.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${release}=    Read Release Of Software Component    ${EPM_BASE_COMPONENT}
    ...    alias=${alias}
    RETURN    ${release}

Count Epm Published Services
    [Documentation]    Le nombre de services publiés au catalogue Gateway : le
    ...    second discriminant de cible, lu par le canal API (38 contre 58 sur
    ...    les deux systèmes du banc, mesuré le 2026-09-21).
    [Arguments]    ${alias}=${API_ALIAS}
    ${services}=    List Available Business Services    alias=${alias}
    ${nombre}=    Get Length    ${services}
    RETURN    ${nombre}

# ---------------------------------------------------- Canal API : le produit

Read Epm Products By Api
    [Documentation]    Les produits ACTIFS du catalogue, éventuellement
    ...    restreints par `filter` et bornés par `top`, projetés sur la clé,
    ...    le prix et la devise.
    ...
    ...    Le filtre d'activité est TOUJOURS appliqué, et il n'est pas
    ...    optionnel : sans lui, la lecture rend aussi les brouillons
    ...    orphelins dont ce banc est plein.
    [Arguments]    ${filter}=${EMPTY}    ${top}=${EMPTY}    ${alias}=${API_ALIAS}
    # La condition lit la VARIABLE (`$filter`) au lieu de l'interpoler : un
    # filtre OData porte des apostrophes autour de la valeur, et la forme
    # interpolée les injecte dans l'expression Python, qui casse en
    # `SyntaxError` sur un filtre parfaitement valide (mesuré au premier run
    # live, le 2026-09-21 : « 'Product eq 'AR-FB-1000'' == '' »).
    IF    not $filter
        ${critere}=    Set Variable    ${EPM_ACTIVE_ONLY}
    ELSE
        ${critere}=    Set Variable    ${EPM_ACTIVE_ONLY} and ${filter}
    END
    ${projection}=    Set Variable
    ...    ${EPM_PRODUCT_API_ID_FIELD},${EPM_PRODUCT_API_PRICE_FIELD},${EPM_PRODUCT_API_CURRENCY_FIELD}
    ${chemin}=    Set Variable    ${EPM_PROD_MAN_SERVICE}/${EPM_PRODUCT_ENTITY_SET}
    IF    '${top}' == '${EMPTY}'
        ${entites}=    Get Odata Entities    ${chemin}    alias=${alias}
        ...    $filter=${critere}    $select=${projection}    $orderby=${EPM_PRODUCT_API_ID_FIELD}
    ELSE
        ${entites}=    Get Odata Entities    ${chemin}    alias=${alias}
        ...    $filter=${critere}    $select=${projection}    $orderby=${EPM_PRODUCT_API_ID_FIELD}
        ...    $top=${top}
    END
    RETURN    ${entites}

Establish Epm Reference Product
    [Documentation]    Le produit de référence de la campagne, DÉCOUVERT sur
    ...    la cible et jamais gravé : le premier produit actif dans l'ordre
    ...    des clés, donc le même à chaque passage sur une cible donnée (la
    ...    campagne reste déterministe) mais valable sur n'importe laquelle.
    ...
    ...    Pourquoi découvrir : `HT-1000`, relevé de mémoire comme présent
    ...    « sur les deux systèmes », est ABSENT de ce catalogue (vérifié le
    ...    2026-09-21 par l'API ET par la table : zéro produit en `HT-*`).
    ...    Une constante gravée aurait fait échouer la campagne entière sur
    ...    une donnée de cible, en désignant le canal comme coupable.
    ...
    ...    Retourne `{product, price, currency}`.
    [Arguments]    ${alias}=${API_ALIAS}
    ${entites}=    Read Epm Products By Api    top=1    alias=${alias}
    Should Not Be Empty    ${entites}
    ...    msg=Le catalogue de produits EPM actifs est VIDE sur cette cible : jeu de données de démonstration absent, ou service ${EPM_PROD_MAN_SERVICE} non publié.
    ${fiche}=    Epm Product Record From Api Entity    ${entites}[0]
    RETURN    ${fiche}

Read Epm Product By Api
    [Documentation]    La fiche d'UN produit actif, lu par sa clé technique
    ...    sur le canal API. Échoue si la clé ne désigne pas exactement une
    ...    entité : deux lignes pour une clé signifieraient que le filtre
    ...    d'activité n'a pas joué.
    [Arguments]    ${product}    ${alias}=${API_ALIAS}
    ${entites}=    Read Epm Products By Api
    ...    filter=${EPM_PRODUCT_API_ID_FIELD} eq '${product}'    alias=${alias}
    Length Should Be    ${entites}    1
    ...    msg=Le canal API ne rend pas exactement une entité ACTIVE pour le produit ${product}.
    ${fiche}=    Epm Product Record From Api Entity    ${entites}[0]
    RETURN    ${fiche}

Epm Product Record From Api Entity
    [Documentation]    Normalise une entité OData en fiche `{product, price,
    ...    currency}`, la forme COMMUNE aux trois canaux : c'est elle qui
    ...    rend les trois lectures confrontables sans que la suite ait à
    ...    connaître le nom des champs de chaque canal.
    [Arguments]    ${entite}
    ${fiche}=    Create Dictionary
    ...    product=${entite}[${EPM_PRODUCT_API_ID_FIELD}]
    ...    price=${entite}[${EPM_PRODUCT_API_PRICE_FIELD}]
    ...    currency=${entite}[${EPM_PRODUCT_API_CURRENCY_FIELD}]
    RETURN    ${fiche}

# ------------------------------------------------- Canal WebGUI : le produit

Read Epm Product By Webgui
    [Documentation]    La même ligne, lue à l'écran : SE16 sur la table des
    ...    produits, filtré sur la clé TECHNIQUE, puis relevé de la grille
    ...    AVEC son contrat d'extraction.
    ...
    ...    La complétude est vérifiée ici et pas ailleurs : une grille WebGUI
    ...    n'envoie qu'une PAGE de lignes et les RENUMÉROTE à partir de 1,
    ...    donc un relevé tronqué est propre, ordonné et indiscernable d'un
    ...    relevé complet. Seule la confrontation au total DÉCLARÉ tranche.
    ...
    ...    Retourne `{product, price, currency, extract}` : la fiche commune
    ...    aux trois canaux, plus le relevé complet pour qui veut l'asserter.
    [Arguments]    ${product}    ${url}
    Open WebGui Data Browser    ${url}
    Display WebGui Table Contents With Filter    ${EPM_PRODUCT_TABLE}
    ...    ${EPM_PRODUCT_KEY_COLUMN}=${product}
    ${extrait}=    Extract Displayed WebGui Grid
    ...    key=${EPM_PRODUCT_KEY_COLUMN}
    ...    source=produits EPM (${EPM_PRODUCT_TABLE}) filtrés sur ${product}
    Table Extract Should Be Complete    ${extrait}
    Length Should Be    ${extrait}[rows]    1
    ...    msg=La grille SE16 ne rend pas exactement une ligne pour le produit ${product} : le critère de sélection n'a peut-être pas été appliqué.
    ${ligne}=    Set Variable    ${extrait}[rows][0]
    ${fiche}=    Create Dictionary
    ...    product=${ligne}[${EPM_PRODUCT_KEY_COLUMN}]
    ...    price=${ligne}[${EPM_PRICE_COLUMN}]
    ...    currency=${ligne}[${EPM_CURRENCY_COLUMN}]
    ...    extract=${extrait}
    RETURN    ${fiche}

# ---------------------------------------------------- Canal RFC : le produit

Read Epm Product By Rfc
    [Documentation]    La même ligne, lue par `RFC_READ_TABLE` : le troisième
    ...    canal, celui qui n'a ni écran ni HTTP. La table visée est la MÊME
    ...    variable que celle des deux autres lectures, passée explicitement.
    [Arguments]    ${product}    ${alias}=${RFC_ALIAS}
    ${lignes}=    Read Business Records    ${EPM_PRODUCT_TABLE}
    ...    ${EPM_PRODUCT_COLUMNS}
    ...    filter=${EPM_PRODUCT_KEY_COLUMN} EQ '${product}'    alias=${alias}
    Length Should Be    ${lignes}    1
    ...    msg=Le canal RFC ne rend pas exactement une ligne de ${EPM_PRODUCT_TABLE} pour le produit ${product}.
    ${fiche}=    Create Dictionary
    ...    product=${lignes}[0][${EPM_PRODUCT_KEY_COLUMN}]
    ...    price=${lignes}[0][${EPM_PRICE_COLUMN}]
    ...    currency=${lignes}[0][${EPM_CURRENCY_COLUMN}]
    RETURN    ${fiche}

# ------------------------------------------- Normalisation et assertion reine

Read User Decimal Notation
    [Documentation]    La notation décimale de l'utilisateur, LUE dans ses
    ...    valeurs par défaut sur le système (canal RFC). Une notation vide
    ...    est une valeur LÉGITIME (elle désigne `1.234.567,89`), pas une
    ...    lecture manquée : on vérifie donc que la LIGNE existe, jamais que
    ...    la valeur est non vide.
    [Arguments]    ${user}    ${alias}=${RFC_ALIAS}
    ${lignes}=    Read Business Records    ${USER_DEFAULTS_TABLE}
    ...    ${USER_DEFAULTS_KEY_FIELD},${USER_DECIMAL_FIELD}
    ...    filter=${USER_DEFAULTS_KEY_FIELD} EQ '${user}'    alias=${alias}
    Length Should Be    ${lignes}    1
    ...    msg=Les valeurs par défaut de l'utilisateur ${user} sont introuvables dans ${USER_DEFAULTS_TABLE} : la notation décimale ne peut pas être établie, donc un prix affiché ne peut pas être décodé de façon sûre.
    RETURN    ${lignes}[0][${USER_DECIMAL_FIELD}]

Technical Price From Screen Text
    [Documentation]    Un prix TEL QU'UN ÉCRAN L'AFFICHE, ramené à la notation
    ...    technique, en appliquant la notation décimale de l'utilisateur.
    ...
    ...    À n'employer QUE sur un texte d'écran. Le même décodage appliqué à
    ...    une valeur de protocole la détruirait en silence : avec la notation
    ...    par défaut de ce banc, le point est le séparateur de MILLIERS, donc
    ...    le `3.25` que rendent l'API et le RFC deviendrait `325`. C'est la
    ...    raison d'être des deux keywords distincts, et le commentaire
    ...    existe parce qu'un seul keyword « normaliser un prix » aurait
    ...    fini par être appelé sur les trois canaux.
    [Arguments]    ${texte}    ${notation}
    Should Not Be Empty    ${texte}
    ...    msg=L'écran ne rend aucun prix : la cellule est vide, ce qui sur une grille ALV signifie le plus souvent une ligne non matérialisée plutôt qu'un prix absent.
    ${valeur}=    Parse Number    ${texte}    ${notation}
    RETURN    ${valeur}

Technical Price From Protocol Value
    [Documentation]    Un prix rendu par un PROTOCOLE (OData, RFC), déjà en
    ...    notation technique (point décimal), validé comme nombre.
    ...
    ...    Les deux canaux le sérialisent différemment (une décimale OData en
    ...    chaîne JSON, un texte délimité côté RFC) mais aucun des deux
    ...    n'applique les formats de l'utilisateur : ce sont des valeurs de
    ...    machine, pas d'affichage.
    [Arguments]    ${valeur}
    Should Not Be Empty    ${valeur}    msg=Le canal ne rend aucun prix.
    Should Match Regexp    ${valeur}    ^-?\\d+([.]\\d+)?$
    ...    msg=Le prix « ${valeur} » n'est pas en notation technique : ce canal appliquerait-il les formats de l'utilisateur ?
    RETURN    ${valeur}

The Three Channels Should Agree On The Price
    [Documentation]    L'assertion reine : les trois canaux rendent le MÊME
    ...    prix pour le même produit.
    ...
    ...    Les trois valeurs sont comparées ENTRE ELLES, et pas seulement
    ...    chacune à une valeur attendue : c'est ce qui prouve que les trois
    ...    canaux regardent la même vérité et non trois copies divergentes.
    ...    Une valeur attendue commune, elle, passerait tout aussi bien si
    ...    deux canaux lisaient la même copie périmée.
    ...
    ...    La comparaison porte sur la valeur NUMÉRIQUE normalisée, jamais sur
    ...    la chaîne brute : les représentations diffèrent d'un canal à
    ...    l'autre (mesuré le 2026-09-21 : `3.25` par l'API et le RFC, `3,25`
    ...    à l'écran), et une égalité de chaînes échouerait sur une donnée
    ...    pourtant parfaitement cohérente.
    [Arguments]    ${api}    ${webgui}    ${rfc}    ${notation}
    Should Be Equal    ${api}[product]    ${webgui}[product]
    ...    msg=Les canaux API et WebGUI ne parlent pas du même produit.
    Should Be Equal    ${api}[product]    ${rfc}[product]
    ...    msg=Les canaux API et RFC ne parlent pas du même produit.
    ${prix_api}=    Technical Price From Protocol Value    ${api}[price]
    ${prix_rfc}=    Technical Price From Protocol Value    ${rfc}[price]
    ${prix_web}=    Technical Price From Screen Text    ${webgui}[price]
    ...    ${notation}
    # ALLER-RETOUR de notation, et c'est la garde qui manquait : la valeur
    # d'écran normalisée, RE-FORMATÉE dans la notation lue, doit reproduire le
    # texte d'origine. Sans elle, `parse_number` CONVERTIT au lieu de refuser
    # un texte non conforme à la notation : un écran qui rendrait `3.25` sous
    # une notation à virgule décimale donnerait `325`, et il suffirait que le
    # protocole rende lui aussi `325` pour que les deux « coïncident » sur une
    # donnée pourtant divergente (réserve de la revue indépendante du
    # 2026-09-21). L'aller-retour asserte donc la NOTATION elle-même, pas
    # seulement la valeur.
    #
    # `thousands=True` suit la mise en forme de SAP, qui groupe les milliers
    # d'un montant. Une cible qui les rendrait sans séparateur ferait échouer
    # cette garde en la nommant, ce qui reste préférable à un trou silencieux.
    ${texte_ecran}=    Strip String    ${webgui}[price]
    ${retour}=    Format Number    ${prix_web}    ${notation}    thousands=${True}
    Should Be Equal    ${retour}    ${texte_ecran}
    ...    msg=La notation décimale « ${notation} » ne rend PAS compte du texte d'écran « ${texte_ecran} » : re-formaté, il donnerait « ${retour} ». La valeur normalisée ${prix_web} est donc issue d'une conversion silencieuse, et la comparer aux autres canaux ne prouverait rien. Vérifier la notation lue sur le système (champ ${USER_DECIMAL_FIELD}) plutôt que la donnée.
    Should Be Equal As Numbers    ${prix_api}    ${prix_web}
    ...    msg=Prix divergent entre le canal API (${api}[price]) et le canal WebGUI (${webgui}[price], normalisé en ${prix_web} avec la notation décimale « ${notation} » de l'utilisateur) pour le produit ${api}[product]. La comparaison porte sur la valeur NUMÉRIQUE normalisée, pas sur le texte.
    Should Be Equal As Numbers    ${prix_api}    ${prix_rfc}
    ...    msg=Prix divergent entre le canal API (${api}[price]) et le canal RFC (${rfc}[price]) pour le produit ${api}[product]. Les deux sont pourtant en notation technique : c'est la donnée qui diverge, pas sa représentation.
    RETURN    ${prix_api}

The Three Channels Should Agree On The Currency
    [Documentation]    La devise, comparée entre les trois canaux. Elle est un
    ...    code technique sur les trois (jamais un libellé traduit), donc la
    ...    comparaison est directe : c'est le contre-exemple utile du prix,
    ...    et il montre que la normalisation n'est pas un réflexe mais une
    ...    réponse à une représentation qui diffère.
    [Arguments]    ${api}    ${webgui}    ${rfc}
    Should Be Equal    ${api}[currency]    ${webgui}[currency]
    ...    msg=Devise divergente entre les canaux API (${api}[currency]) et WebGUI (${webgui}[currency]).
    Should Be Equal    ${api}[currency]    ${rfc}[currency]
    ...    msg=Devise divergente entre les canaux API (${api}[currency]) et RFC (${rfc}[currency]).
    RETURN    ${api}[currency]

# -------------------------------------------- Documents de modification (RFC)

Read Change Document Objects For Epm Products
    [Documentation]    Les classes d'objet de documents de modification
    ...    enregistrées pour la table des produits. Zéro ligne = ce mécanisme
    ...    n'est pas configuré pour cette table.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${lignes}=    Read Business Records    ${CHANGE_OBJECT_CATALOGUE}
    ...    ${CHANGE_OBJECT_FIELDS}
    ...    filter=TABNAME EQ '${EPM_PRODUCT_TABLE}'    alias=${alias}
    RETURN    ${lignes}

Read Change Document Objects Witness
    [Documentation]    Le TÉMOIN POSITIF de la lecture du catalogue des
    ...    documents de modification : quelques lignes NON filtrées.
    ...
    ...    Il existe parce qu'un résultat vide ne prouve une absence que si la
    ...    lecture qui l'a produit sait rendre des lignes. Sans témoin, « aucun
    ...    document de modification n'est configuré pour cette table » et « ce
    ...    filtre ne matche rien pour une raison de forme » rendent le même
    ...    zéro et le même test vert, ce qui est exactement la confusion que le
    ...    scénario prétend écarter. Même patron que la sonde canari de
    ...    l'inventaire DDIC, qui distingue un lot réellement absent d'un
    ...    critère déplacé.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${lignes}=    Read Business Records    ${CHANGE_OBJECT_CATALOGUE}
    ...    ${CHANGE_OBJECT_FIELDS}    limit=5    alias=${alias}
    RETURN    ${lignes}

Read Change Document Items For Epm Products
    [Documentation]    Les postes de documents de modification journalisés
    ...    pour la table des produits. Zéro ligne = aucun changement n'y a
    ...    jamais été tracé par ce mécanisme.
    [Arguments]    ${alias}=${RFC_ALIAS}
    ${lignes}=    Read Business Records    ${CHANGE_ITEM_TABLE}
    ...    ${CHANGE_ITEM_FIELDS}
    ...    filter=TABNAME EQ '${EPM_PRODUCT_TABLE}'    alias=${alias}
    RETURN    ${lignes}
