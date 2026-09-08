# SE11 : l'affichage du dictionnaire ABAP croisé avec les tables DD* lues par SE16

- **Canal** : ECC (SAP GUI)
- **Système / URL** : A4H (ABAP Platform 1909 trial, Docker), connexion
  `/H/vhcala4hci/S/3200`, mandant 001, utilisateur DEVELOPER (exploré live le
  2026-09-05, SAP GUI 8.00).
- **Préconditions** :
  - scripting serveur actif (`Scripting Should Be Fully Enabled` en setup) ;
  - SE16 en grille ALV (`Use ALV Grid In Data Browser`, une fois par
    utilisateur, persistant) : les lectures DD02L/DD03L/DD07L en dépendent ;
  - aucune donnée applicative requise : la campagne lit le DICTIONNAIRE, qui
    existe même sur tables vides. `SNWD_PD`, `CONTFLAG` et `SNWD_PRODUCT_ID`
    sont livrés avec le trial (packages `S_NWDEMO_MODEL_DDIC` / SAP standard).

## Perception métier

- **Personas** : `@ecc` + `@basis` (fiches PERSONAS.md présentes et relues).
- **Où se lit la vérité** : dans les tables du dictionnaire lues par SE16,
  jamais dans les textes de l'écran SE11 : `DD02L` (classe technique
  `TABCLASS`, classe de livraison `CONTFLAG`, version active `AS4LOCAL`),
  `DD03L` (contrat de champs : nom, position, clé, élément de données, type,
  longueur), `DD07L` (valeurs fixes d'un domaine). Tout est **(vérifié live)**
  le 2026-09-05. L'écran SE11 est la DOC de cette vérité : le test confronte
  la doc au dictionnaire, le miroir ECC de la campagne Demo Kit « la table de
  documentation croisée avec le contrôle vivant ».
- **Risques métier priorisés** :
  1. la dérive de schéma silencieuse (un transport ou une montée de version
     change un champ, une clé, une longueur : le croisement SE11 = DD03L la
     nomme champ par champ) ;
  2. le « vert et faux » sur objet inexistant : SE11 refuse un objet inconnu
     par un message de type **S**, pas E (vérifié live) : toute assertion
     « pas de type E » serait verte sur un objet qui n'existe pas ;
  3. la confusion table/structure : SE11 REDIRIGE une structure demandée comme
     table (aucun refus), là où SE16 la rejette en type E : les deux canaux ne
     racontent pas la même histoire et le test doit le savoir.
  - **Hors périmètre (dit)** : le croisement des libellés `DD04T` (onglet
    Field Label de l'élément de données) : observé côté SE11, mais la lecture
    SE16 de DD04T n'a pas été explorée live, donc pas de scénario ; les vues,
    groupes de types, aides à la recherche et objets de verrouillage de
    l'écran initial SE11 : mêmes radios relevées, flux non explorés ; toute
    volumétrie de données applicatives (déjà couverte par
    `inventaire_tables_ddic.robot` et les suites SE16 existantes).
- **Assertion reine** : l'écran SE11 « Fields » d'une table = `DD03L` pour la
  même table : mêmes champs, même ordre, mêmes clés, mêmes longueurs. Portée
  par le scénario 2, et PROUVÉE pendant l'exploration : 26 lignes = 26 lignes,
  ordre identique, clés {CLIENT, NODE_KEY} des deux côtés.
- **Réversibilité** : lecture seule stricte de bout en bout : mode Display
  uniquement (bouton « Display » de l'écran initial, jamais Change/Create),
  navigation refermée par F3, session refermée même sur échec. Le seul réglage
  persistant touché est celui que toutes les suites SE16 posent déjà
  (`Use ALV Grid In Data Browser`). Rien à défaire.

## Données observées

Relevées live le 2026-09-05 sur A4H (SAP GUI 8.00, langue de session EN).

### Écran initial SE11 (`SAPLSD_ENTRY/SE11/1000`)

- Radios et champs appariés : `radRSRD1-TBMA`/`ctxtRSRD1-TBMA_VAL` (Database
  table), `radRSRD1-VIMA`/`ctxtRSRD1-VIMA_VAL` (View),
  `radRSRD1-DDTYPE`/`ctxtRSRD1-DDTYPE_VAL` (Data type),
  `radRSRD1-TYMA`/`ctxtRSRD1-TYMA_VAL` (Type Group),
  `radRSRD1-DOMA`/`ctxtRSRD1-DOMA_VAL` (Domain),
  `radRSRD1-SHMA`/`ctxtRSRD1-SHMA_VAL` (Search help),
  `radRSRD1-ENQU`/`ctxtRSRD1-ENQU_VAL` (Lock object) ; tous sous `wnd[0]/usr/`.
- Boutons : `btnPUSHSHOW` (Display, la voie lecture seule), `btnPUSHEDIT`,
  `btnPUSHADD`. Libellés visibles « Display »/« Change »/« Create » (ancres de
  libellé pour le healing).

### Affichage d'une table : SNWD_PD (`SAPLSD41/SE11/2200`, titre « Dictionary: Display Table »)

- En-tête : `ctxtDD02D-DBTABNAME` = `SNWD_PD`, `txtDD02D-DDTEXT` =
  « EPM: Product Data Table », `txtDD02D-TABCLTEXT` = « Transparent Table »
  (texte LOCALISÉ), `txtRSDXX-TXTSAVSTAT` = « Active » (localisé aussi).
- Six onglets dans `tabsTAB_STRIP` : `tabpHEAD` (Attributes), `tabpMAIN`
  (Delivery and Maintenance), `tabpDEF` (Fields, actif à l'arrivée),
  `tabpF4V` (Input Help/Check), `tabpREFF` (Currency/Quantity Fields),
  `tabpINDX` (Indexes).
- Onglet Fields : GuiTableControl
  `wnd[0]/usr/tabsTAB_STRIP/tabpDEF/ssubTS_SCREEN:SAPLSD41:2201/tblSAPLSD41TC0`.
  `Read Table Control` rend **26 lignes réellement remplies** (piège RowCount
  lignes réservées confirmé une fois de plus). Titres de colonnes : `Field`,
  `Key`, `Initial Values`, `Data element`, `Data Type`, `Length`,
  `Decimal Places`, `Coordinate`, `Short Description`, `Group`.
- Cellules du table control : `txtDD03D-FIELDNAME`, `chkDD03P-KEYFLAG`
  (GuiCheckBox), `chkDD03P-NOTNULL` (GuiCheckBox), `ctxtDD03D-ROLLNAME`,
  `txtDD03D-DATATYPE`, `txtDD03P-LENG`, `txtDD03P-DECIMALS`,
  `txtDD03P-DDTEXT`, `txtDD03P-GROUPNAME`, `txtDD03P-SRS_ID`.
  Les colonnes checkbox se lisent VIDES par le texte ; l'état est lisible par
  `Get Value` sur la cellule : `chkDD03P-KEYFLAG[1,0]` (CLIENT) = `checked`,
  `chkDD03P-KEYFLAG[1,2]` (PRODUCT_ID) = `unchecked`.
- Les 26 champs, dans l'ordre : CLIENT, NODE_KEY, PRODUCT_ID, TYPE_CODE,
  CATEGORY, .INCLUDE (SNWD_ADMIN_DATA), CREATED_BY, CREATED_AT, CHANGED_BY,
  CHANGED_AT, NAME_GUID, DESC_GUID, SUPPLIER_GUID, TAX_TARIF_CODE,
  MEASURE_UNIT, WEIGHT_MEASURE, WEIGHT_UNIT, CURRENCY_CODE, PRICE,
  PRODUCT_PIC_URL, WIDTH, DEPTH, HEIGHT, DIM_UNIT, .INCLUDE
  (INCL_EEW_SNWD_PD), DUMMY_FIELD_PD.
- Onglet Delivery and Maintenance (`ssubTS_SCREEN:SAPLSD41:2202`) :
  `ctxtDD02D-CONTFLAG` = **`L`** (la valeur TECHNIQUE, ancre locale-safe,
  libellé visible « Delivery Class ») ; `cmbDD02D-MAINFLAG` (GuiComboBox, le
  texte affiché est localisé).
- Onglet Attributes (`ssubTS_SCREEN:SAPLSD41:2104/subSUB_STATE:SAPLSED5:0100`) :
  `txtRSDXX-AS4USER` = `SAP`, `ctxtRSDXX-AS4DATE` = `23.02.2016` (format de
  date LOCALISÉ), `ctxtRSDXX-DEVCLASS` = `S_NWDEMO_MODEL_DDIC` (croisable
  TADIR), `RSDXX-MALANGU` (langue d'origine).

### Croisement DD03L (SE16, `Read Ddic Table Fields SNWD_PD`)

- 26 lignes, positions `0001` à `0026`, mêmes noms dans le même ordre que le
  table control SE11 (égalité vérifiée en session : True).
- `KEYFLAG='X'` pour CLIENT et NODE_KEY exactement : concorde avec les deux
  seules checkbox cochées côté SE11.
- `LENG` zéro-paddé (`000010`) là où SE11 affiche `10` : égalité après
  conversion entière (vérifiée : True).
- PRODUCT_ID : `ROLLNAME=SNWD_PRODUCT_ID`, `DOMNAME` VIDE (élément de données
  sans domaine, cohérent avec l'écran élément de données, voir plus bas).
- CLIENT : `DOMNAME=MANDT`, `CHECKTABLE=T000` ; CATEGORY :
  `CHECKTABLE=SNWD_PD_CATGOS`.
- Seule divergence SE11 vs DD03L : les deux lignes `.INCLUDE`. SE11 affiche le
  NOM de l'include dans la colonne « Data element » (`SNWD_ADMIN_DATA`,
  `INCL_EEW_SNWD_PD`) ; DD03L rend `ROLLNAME` vide pour ces lignes (le nom de
  l'include vit dans `PRECFIELD`, non projeté par `Read Ddic Table Fields`).

### Croisement DD02L (SE16, `Classify Ddic Objects`)

- SNWD_PD : `present=True`, `tabclass=TRANSP`, `as4local=A`, `as4vers=0000`.
  C'est la vérité technique derrière les textes localisés « Transparent
  Table » et « Active » de l'en-tête SE11.
- L'écran de sélection SE16 de DD02L n'expose que `AS4LOCAL`, `AS4VERS`,
  `TABNAME` comme critères (relevé par l'échec actionnable de
  `Count Table Entries With Criteria ... CONTFLAG=L`) : `CONTFLAG` et
  `TABCLASS` se lisent en SORTIE de grille, jamais en critère (la leçon DDIC
  du dépôt, confirmée).

### Affichage d'un domaine : CONTFLAG (`SAPLSD11/SE11/1200`, titre « Dictionary: Display Domain »)

- En-tête : `txtDD01D-DOMNAME` = `CONTFLAG`, `txtDD01D-DDTEXT` (localisé),
  `txtRSDXX-TXTSAVSTAT`.
- Trois onglets : `tabpTAB3` (Properties), `tabpTAB1` (Definition),
  `tabpTAB2` (Value Range).
- Onglet Definition (`ssubTS_SCREEN:SAPLSD11:1201`) : `ctxtDD01D-DATATYPE` =
  `CHAR`, `txtDD01D-LENG` = `1`, `txtDD01D-DECIMALS` = `0`,
  `txtDD01D-OUTPUTLEN` = `1`, `txtDD01D-CONVEXIT` vide, checkbox
  `chkDD01D-SIGNFLAG` / `chkDD01D-LOWERCASE`.
- Onglet Value Range (`ssubTS_SCREEN:SAPLSD11:1202`) : DEUX GuiTableControl,
  `tblSAPLSD11TC0` (« Single Vals » : colonnes `I`, `Fixed`
  (`txtDD07D-DOMVALUE`), `Short Descript.` (`txtDD07D-DDTEXT`)) et
  `tblSAPLSD11TC1` (« Intervals »).
- 7 valeurs fixes lues dans l'ORDRE DE MAINTENANCE : A, C, L, G, E, S, W
  (PAS trié). Triées, elles égalent exactement `Read Domain Values CONTFLAG`
  (DD07L) : A/C/E/G/L/S/W (égalité vérifiée en session : True), le catalogue
  déjà verrouillé par `ecc_exploration.robot`.

### Affichage d'un élément de données : SNWD_PRODUCT_ID (`SAPLSD51/SE11/1000`, titre « Dictionary: Display Data Element »)

- Atteint par NAVIGATION INTERNE : focus (`Set Focus`) sur la cellule
  `ctxtDD03D-ROLLNAME[3,2]` du table control Fields, puis F2 (`Send Vkey 2`).
  F3 (`Send Vkey 3`) revient à l'écran table (pile de navigation vérifiée :
  `ctxtDD02D-DBTABNAME` relit `SNWD_PD` au retour), un second F3 revient à
  l'écran initial.
- En-tête : `txtDD04D-ROLLNAME` = `SNWD_PRODUCT_ID`, `txtDD04D-DDTEXT` =
  « EPM: Product ID ».
- Quatre onglets : `tabpATTR` (Attributes), `tabpTYPE` (Data Type, actif),
  `tabpADDA` (Further Characteristics), `tabpTEXT` (Field Label).
- Onglet Data Type (`ssubSUB_DATA:SAPLSD51:1002`) : `ctxtDD04D-DOMNAME`
  **VIDE** (type prédéfini, PAS de domaine), `ctxtDD04D-DATATYPE` = `CHAR`,
  `txtDD04D-LENG` = `10` : concorde avec DD03L (`DOMNAME` vide,
  `DATATYPE=CHAR`, `LENG=000010`).
- Onglet Field Label (`ssubSUB_DATA:SAPLSD51:1003`) : `txtDD04D-SCRTEXT_S` =
  « Prod. ID » (`SCRLEN1=10`), `txtDD04D-SCRTEXT_M` = « Product ID »
  (`SCRLEN2=20`), `SCRTEXT_L` (`SCRLEN3=40`) : textes dépendants de la langue
  de session (DD04T), relevés à titre factuel, pas comme ancre.

### Branches d'erreur (vérifiées live)

- **Objet inexistant** (`ZZNOPE_404` en Database table + Display) : AUCUNE
  fenêtre modale (`Get Open Windows` = wnd[0] seul), l'écran RESTE
  `SAPLSD_ENTRY/SE11/1000`, et la barre de statut porte un message de type
  **`S`** (« ZZNOPE_404 does not exist; check the name »). Le type S est un
  PIÈGE : le verdict structurel est « écran initial inchangé », le type de
  message seul ne suffit pas.
- **Structure demandée comme table** (`SNWD_ADMIN_DATA` en Database table +
  Display) : PAS de refus, AUCUN message : SE11 redirige vers
  `SAPLSD41/SE11/2100`, titre « Dictionary: Display Structure » (même
  programme SAPLSD41, dynpro **2100** au lieu de **2200**). Contraste assumé
  avec SE16, qui rejette la même structure en type `E`
  (`sflight-consultation-se16.md`, scénario 3). L'ancre locale-safe est le
  NUMÉRO de dynpro, pas le titre.

## Scénarios

### 1. L'en-tête SE11 d'une table dit ce que DD02L enregistre

- **Étapes** :
  1. Ouvrir SE11 et afficher la table `SNWD_PD` en mode Display (keyword
     métier à créer : ouverture d'un objet du dictionnaire en affichage).
  2. Lire l'en-tête de l'écran table : nom affiché, statut, classe technique.
  3. Par SE16, classer `SNWD_PD` via DD02L (`Classify Ddic Objects` avec le
     barème relevé par `Read Domain Values TABCLASS` +
     `Get Ddic Classification Map`).
  4. Confronter : le nom relu = `SNWD_PD` ; DD02L rend `tabclass=TRANSP` et
     `as4local=A`.
- **Résultat attendu** : l'écran atteint est le dynpro table (programme
  `SAPLSD41`, dynpro `2200`) ; `DD02D-DBTABNAME` relit exactement le nom
  demandé ; DD02L confirme `TRANSP` + `A`. Aucune assertion sur les textes
  « Transparent Table » / « Active » (localisés).
- **Keywords métier manquants** : `Open Se11 Object Display` (radio + champ +
  bouton Display, catégorie d'objet paramétrée, verdict = programme/dynpro
  atteint), `Read Se11 Table Header` (nom, texte court, ids `DD02D-*` /
  `RSDXX-*`).

### 2. Assertion reine : l'onglet Fields = DD03L, champ à champ

- **Étapes** :
  1. Afficher `SNWD_PD` dans SE11, onglet Fields.
  2. Lire le GuiTableControl des champs (`Read Table Control` sur
     `tblSAPLSD41TC0` : 26 lignes réelles).
  3. Par SE16, lire le contrat de champs de la même table
     (`Read Ddic Table Fields SNWD_PD` : DD03L trié par position).
  4. Confronter liste à liste : mêmes noms, même ordre, mêmes types, mêmes
     longueurs (converties en entiers), mêmes éléments de données pour toutes
     les lignes qui ne sont pas `.INCLUDE`.
- **Résultat attendu** : égalité stricte des séquences de noms (26 = 26,
  ordre compris) ; pour chaque champ hors `.INCLUDE`, `Data element` SE11 =
  `ROLLNAME` DD03L et `int(Length)` = `int(LENG)` ; les deux lignes
  `.INCLUDE` sont confrontées sur le NOM seul côté SE11 (DD03L rend
  `ROLLNAME` vide pour elles, divergence structurelle documentée).
- **Keywords métier manquants** : `Read Se11 Table Fields` (onglet Fields +
  lecture du table control, id du contrôle confiné au page object),
  `Se11 Fields Should Match Dd03l` (la confrontation avec ses normalisations :
  entiers pour les longueurs, tolérance `.INCLUDE`).

### 3. Les clés cochées dans SE11 sont les clés de DD03L

- **Étapes** :
  1. Sur l'onglet Fields de `SNWD_PD`, lire l'état des checkbox de la colonne
     Key pour chaque ligne (état `Selected` lu cellule par cellule, le texte
     de la colonne étant vide par nature).
  2. Confronter avec les lignes `KEYFLAG='X'` de DD03L.
- **Résultat attendu** : exactement {CLIENT, NODE_KEY} cochés côté SE11 et
  marqués `X` côté DD03L ; PRODUCT_ID décoché des deux côtés (contre-épreuve).
- **Keywords métier manquants** : `Read Se11 Key Fields` (liste des champs
  dont la checkbox Key est cochée ; s'appuie sur `Get Value` par cellule tant
  que la bibliothèque ne lit pas l'état des checkbox dans
  `Read Table Control`, voir Points de vigilance).

### 4. La classe de livraison affichée = DD02L.CONTFLAG lu en sortie de grille

- **Étapes** :
  1. Sur `SNWD_PD` dans SE11, ouvrir l'onglet Delivery and Maintenance et lire
     la valeur technique du champ classe de livraison (`L` observé).
  2. Par SE16, afficher DD02L filtré sur `TABNAME=SNWD_PD` (critère par NOM,
     jamais par position) et lire la colonne `CONTFLAG` en sortie de grille.
  3. Vérifier au passage que `L` appartient aux valeurs du domaine `CONTFLAG`
     (`Read Domain Values CONTFLAG`).
- **Résultat attendu** : `DD02D-CONTFLAG` (SE11) = `CONTFLAG` (DD02L) = `L`,
  et `L` est dans le catalogue DD07L. Aucune assertion sur le texte descriptif
  de la classe (localisé).
- **Keywords métier manquants** : `Read Se11 Delivery Class` (onglet MAIN,
  valeur de `ctxtDD02D-CONTFLAG`), `Read Ddic Table Header` (DD02L filtré
  `TABNAME`, colonnes `TABCLASS`/`CONTFLAG`/`AS4LOCAL` lues en sortie :
  l'écran de sélection DD02L n'expose PAS ces champs en critère, vérifié).

### 5. Le domaine : valeurs fixes SE11 = DD07L, définition technique relevée

- **Étapes** :
  1. Depuis l'écran initial SE11, afficher le domaine `CONTFLAG` (radio
     Domain).
  2. Onglet Definition : lire type (`CHAR`), longueur (`1`), décimales (`0`).
  3. Onglet Value Range : lire le table control « Single Vals » (7 lignes,
     colonnes `Fixed` + description) et vérifier que « Intervals » est vide.
  4. Par SE16, lire `Read Domain Values CONTFLAG` (DD07L).
  5. Confronter : l'ensemble des valeurs fixes SE11 (TRIÉ) = la liste DD07L.
- **Résultat attendu** : écran domaine atteint (programme `SAPLSD11`, dynpro
  `1200`) ; 7 valeurs fixes ; ensembles égaux après tri (l'ordre SE11 est
  l'ordre de maintenance A, C, L, G, E, S, W, PAS l'ordre trié). Assertions
  sur les valeurs et les compteurs, jamais sur les descriptions.
- **Keywords métier manquants** : `Read Se11 Domain Definition` (onglet
  Definition, valeurs `DD01D-*`), `Read Se11 Domain Fixed Values` (onglet
  Value Range, lecture du table control TC0).

### 6. Navigation interne : du champ à son élément de données, et retour

- **Étapes** :
  1. Afficher `SNWD_PD`, onglet Fields.
  2. Poser le focus sur la cellule Data element de la ligne PRODUCT_ID et
     naviguer par F2 (équivalent scripté du double-clic).
  3. Sur l'écran élément de données : lire le nom (`SNWD_PRODUCT_ID`), le
     domaine (VIDE : type prédéfini), le type (`CHAR`) et la longueur (`10`).
  4. Confronter avec la ligne DD03L de PRODUCT_ID (`ROLLNAME`, `DOMNAME`
     vide, `DATATYPE`, `LENG`).
  5. Revenir par F3 et vérifier le retour à l'écran table (`SNWD_PD` relu).
- **Résultat attendu** : écran élément de données atteint (programme
  `SAPLSD51`, dynpro `1000`) ; nom, type, longueur et ABSENCE de domaine
  concordent avec DD03L (un domaine vide des deux côtés est une assertion, pas
  un trou) ; F3 restaure l'écran table avec le bon nom.
- **Keywords métier manquants** : `Open Data Element From Se11 Field` (focus
  cellule + F2, ligne repérée par `Find Table Control Row` sur le nom de
  champ, jamais par index en dur), `Read Se11 Data Element Type` (onglet Data
  Type, valeurs `DD04D-*`), `Return To Previous Ddic Object` (F3 + verdict
  d'écran).

### 7. Branches d'erreur : l'objet inexistant et la structure déguisée

- **Étapes** :
  1. Depuis l'écran initial SE11, demander l'affichage d'une table au nom
     inexistant (préfixe Z hors norme, p.ex. `ZZNOPE_404`).
  2. Constater le verdict : fenêtres ouvertes, écran courant, type de message.
  3. Demander ensuite l'affichage de `SNWD_ADMIN_DATA` (structure connue,
     classée `INTTAB` par DD02L) via le MÊME radio Database table.
  4. Constater le verdict : écran atteint, absence de message.
  5. Contre-épreuve SE16 : `Reach Table Selection Screen SNWD_ADMIN_DATA`
     rend `rejected` avec `message_type=E` (le comportement déjà verrouillé
     par les suites existantes).
- **Résultat attendu** : l'objet inexistant laisse l'écran initial
  `SAPLSD_ENTRY/SE11/1000` inchangé, aucune modale, message de type `S`
  (JAMAIS asserter « pas de E » : ici le refus EST un S) ; la structure est
  REDIRIGÉE vers le dynpro `2100` de `SAPLSD41` (affichage structure) sans
  aucun message, là où SE16 la refuse en type `E`. Les assertions portent sur
  programme/numéro de dynpro et type de message, jamais sur les textes.
- **Keywords métier manquants** : `Se11 Display Should Stay On Initial Screen`
  (le verdict structurel du refus : écran inchangé + type de message relevé),
  `Get Se11 Current Object Kind` (programme + dynpro → table | structure |
  domaine | élément de données : la carte observée est dans ce plan).

## Points de vigilance

- **Le refus SE11 est un message de type `S`** (objet inexistant, vérifié
  live) : le type seul ne discrimine rien, le verdict fiable est « l'écran
  n'a pas changé ». Ne jamais reproduire ici le patron SE16 (type `E`).
- **Une structure n'est PAS refusée par SE11** : redirection silencieuse vers
  le dynpro `2100` (« Display Structure »). Un test qui attend le dynpro table
  `2200` sur un nom de structure échouerait en accusant un localisateur ; le
  page object doit rendre la NATURE de l'écran atteint (programme + dynpro).
- **Colonnes checkbox d'un GuiTableControl** : `Read Table Control` lit le
  TEXTE des cellules, donc `Key` et `Initial Values` reviennent vides ; l'état
  se lit par `Get Value` sur la cellule (`checked`/`unchecked`). Écart de
  capacité signalé (convention #12) : candidat à une extension de
  `Read Table Control` (lire `Selected` pour les cellules GuiCheckBox) ; en
  attendant, le keyword métier passe cellule par cellule.
- **Normalisations au croisement** : `LENG`/`DECIMALS` DD03L sont zéro-paddés
  (`000010`), SE11 affiche `10` : comparer en entiers (chiffres seuls,
  locale-safe). Les lignes `.INCLUDE` divergent par construction (nom
  d'include côté SE11 colonne Data element, `ROLLNAME` vide côté DD03L).
- **Ordre des valeurs fixes d'un domaine** : ordre de MAINTENANCE côté SE11
  (A, C, L, G, E, S, W observé), ordre trié côté `Read Domain Values` :
  comparer des ensembles ou trier avant.
- **Textes localisés partout dans les en-têtes SE11** : `TABCLTEXT`,
  `TXTSAVSTAT`, le combo `MAINFLAG`, les descriptions de valeurs fixes, le
  format de `AS4DATE` (23.02.2016 observé en EN) : jamais en assertion ; les
  ancres sont les valeurs techniques (`CONTFLAG=L`, `TABCLASS=TRANSP`,
  `AS4LOCAL=A`) et les ids de programme/dynpro.
- **DD02L en SE16** : seuls `AS4LOCAL`, `AS4VERS`, `TABNAME` sont des critères
  de sélection (vérifié par échec actionnable) ; `TABCLASS` et `CONTFLAG` se
  lisent en SORTIE de grille. Et DD02L est une table large : le popup « choix
  des champs de sélection » persistant par utilisateur reste possible au
  premier accès (`Reach Se16 Selection Screen` le gère).
- **RowCount d'un GuiTableControl compte les lignes réservées** : sur SE11 le
  piège est déjà encodé dans `Read Table Control` (26 lignes rendues), ne
  jamais dimensionner une boucle dessus.
- **Élément de données sans domaine** : `SNWD_PRODUCT_ID` est un type
  prédéfini (`DOMNAME` vide des deux côtés). Ne jamais supposer qu'un élément
  de données porte un domaine ; l'absence concordante est une assertion utile.
- **Navigation interne** : F2 = double-clic scripté (focus posé d'abord),
  F3 dépile UN niveau (élément de données → table → écran initial). La ligne
  visée dans le table control se repère par contenu
  (`Find Table Control Row`), jamais par index en dur.
- **Session rf-mcp de l'exploration** (note d'outillage, pas un fait produit) :
  des erreurs COM `RPC_E_WRONG_THREAD` intermittentes ont frappé environ un
  appel sur deux (retry immédiat systématiquement vert), `Get Screen Map` et
  `mode=semantic` ont rendu `# screen ?` en continu dans cette session, et un
  `Get Open Windows` a rendu UNE fois une liste vide au lieu d'échouer. À
  investiguer côté intégration rf-mcp (rail STA) ; une suite Robot classique
  n'est pas concernée (thread unique). Signalé comme écart dans le rapport.

## Artefacts prévus

- Page object : `resources/page_objects/se11_dictionary_display.resource`
  (ids `RSRD1-*`, `DD02D-*`, `DD01D-*`, `DD04D-*`, chemins des table controls,
  carte programme/dynpro → nature d'objet ; libellés visibles « Display »,
  « Delivery Class » comme ancres de secours pour le healing).
- Suite : `tests/robot/ui/ecc/se11_dictionnaire_croisement.robot` (7
  scénarios, LECTURE SEULE, teardown `Close SAP` même sur échec).
- Réutilisés tels quels : `Read Ddic Table Fields`, `Classify Ddic Objects`,
  `Get Ddic Classification Map`, `Read Domain Values`, `Read Table Control`,
  `Find Table Control Row`, `Reach Table Selection Screen`,
  `Use ALV Grid In Data Browser`.

## Écarts constatés à la génération

Génération le 2026-09-05 (sap-generator, exploration live A4H, chaque étape
exécutée via rf-mcp avant écriture, puis run complet par le vrai `robot`).

1. **Écart de capacité comblé, le scénario 3 s'écrit sans contournement.**
   Le plan (scénario 3 et Points de vigilance) prévoyait de lire l'état des
   cases de la colonne Key par `Get Value` cellule par cellule, « tant que la
   bibliothèque ne lit pas l'état des checkbox dans `Read Table Control` ».
   Cette lecture est désormais dans la bibliothèque : `Read Table Control`
   rend une cellule GuiCheckBox en drapeau ABAP (`X` cochée, vide sinon).
   Vérifié live sur SNWD_PD : colonne `Key` = `X` pour CLIENT et NODE_KEY,
   vide pour PRODUCT_ID, exactement les lignes `KEYFLAG='X'` de DD03L. Le
   keyword `Read Se11 Key Fields` dérive donc les clés des lignes déjà lues,
   aucun `Get Value` dans le page object. Observation factuelle du même lot :
   la colonne « Initial Values » (case `chkDD03P-NOTNULL`) est rendue de la
   même façon (`X` sur CLIENT et NODE_KEY), non exploitée en assertion.

2. **Précisions de localisateurs relevées live (complètent les données du
   plan, sans les contredire).** Le conteneur d'onglets de l'écran domaine est
   `tabsTAB_STRIP` (onglets `tabpTAB1` Definition, `tabpTAB2` Value Range,
   `tabpTAB3` Properties) ; celui de l'écran élément de données est `tabsTS`
   (onglet `tabpTYPE` Data Type). Les champs de longueur sont `txtDD01D-LENG`
   (domaine) et `txtDD04D-LENG` (élément de données). L'élément de données
   PRODUCT_ID est un type prédéfini : radio `radRADIO-DIRECT` sélectionné et
   `ctxtDD04D-DOMNAME` vide, cohérent avec `DOMNAME` vide dans DD03L.

3. **Note d'outillage (pas un fait produit), confirmant celle du planner.**
   La session rf-mcp a subi des erreurs COM `RPC_E_WRONG_THREAD` intermittentes
   (environ un appel sur deux, un retry immédiat toujours vert) et
   `Get Screen Signature` a rendu `# screen ?` au premier appel puis la vraie
   valeur au second (rail STA du serveur rf-mcp). De plus, la lecture des
   checkbox par `Read Table Control` a exigé un hot-reload de la classe figée
   par le serveur rf-mcp (démarré avant le correctif de `src/`) avant de rendre
   le drapeau : après hot-swap, CLIENT et NODE_KEY portent bien `X`. Une suite
   Robot classique (thread unique, process neuf) n'est concernée par aucun de
   ces deux points ; le run par le vrai `robot` fait foi.
