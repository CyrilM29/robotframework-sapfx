# Cycle de vie d'un produit EPM : API, WebGUI, RFC

- **Canaux** : API (OData v2, service `SEPMRA_PROD_MAN`), WebGUI (SAP GUI for HTML,
  SE16), RFC (`RFC_READ_TABLE`, lecture de la configuration des documents de
  modification)
- **Système** : A4H (ABAP Platform 1909), client `001`, utilisateur `DEVELOPER`
- **Préconditions** : Gateway active (`Gateway Should Be Active`), service ICF
  `webgui` actif, canal RFC disponible (`pyrfc` importable, binding natif
  présent), une valeur de catégorie produit et un fournisseur existants
  (relevés à l'exécution, jamais en dur)

> **Statut : faits live relevés le 2026-09-21 (A4H, client 001).** Les valeurs
> observées (chemins de service, noms de champs, catégories, fournisseurs,
> identifiants de brouillon) sont datées de cette exploration. Toute cible
> relit ses propres valeurs.

## Perception métier

- **Personas** : `@api` (canal principal d'écriture et de RFC) + `@basis`
  (où se lit la vérité dictionnaire : `DD02L`, `TCDOB`/`CDPOS`). Aucune fiche
  `PERSONAS.md` ne couvre nativement le modèle EPM : ce n'est pas un module
  applicatif SAP réel (FI/MM/SD/PP), c'est le jeu de démonstration livré avec
  la pile technique, construit sur BOPF (Business Object Processing
  Framework) et le protocole brouillon de Fiori Elements. Limite déjà
  consignée dans `PERSONAS.md` : A4H ne porte aucun module applicatif.
- **Où se lit la vérité** : la table `SNWD_PD` (**vérifié live** : `TABCLASS`
  `TRANSP`, `CONTFLAG` `L`, classe de livraison du modèle EPM), lue par trois
  canaux indépendants : l'entity set `SEPMRA_C_PD_Product` du service
  `SEPMRA_PROD_MAN` côté API, l'écran SE16 côté WebGUI, `RFC_READ_TABLE` côté
  RFC. Jamais un texte d'écran localisé.
- **Risques métier priorisés** :
  1. **(couvert)** trois canaux qui liraient trois valeurs différentes du même
     prix après une écriture : c'est le risque central de toute architecture
     multi-canal, et l'assertion reine du plan le porte directement.
  2. **(écarté par construction)** un produit de test qui resterait dans le
     catalogue de démonstration partagé après le passage du test : la
     réversibilité est non négociable sur ce système utilisé par d'autres
     campagnes, et c'est précisément parce qu'elle s'est révélée IMPOSSIBLE à
     garantir (voir « Écart n°3 ») que la campagne renonce à créer quoi que
     ce soit.
  3. **(hors périmètre, documenté ci-dessous)** la traçabilité d'audit du
     changement de prix par les documents de modification classiques
     (CDHDR/CDPOS) : l'exploration live a établi que ce mécanisme n'est PAS
     utilisé par cette table sur ce système. Voir « Écart n°2 ».
  4. **(hors périmètre)** les règles de validation métier de l'app Product
     Manager (prix négatif refusé, devise incohérente, catégorie inconnue) :
     ce plan vérifie la plomberie cross-canal, pas les règles métier de
     l'application.
- **Assertion reine** : la MÊME valeur de prix est relue par les trois canaux
  indépendants (lecture API de l'entité produit, lecture WebGUI de la grille
  SE16 filtrée sur la clé technique, lecture RFC via `RFC_READ_TABLE`), sur un
  produit EPM **déjà présent** dans le catalogue. Les trois valeurs sont
  comparées ENTRE ELLES, et pas seulement chacune à une valeur attendue :
  c'est ce qui prouve que les trois canaux regardent la même vérité et non
  trois copies divergentes. C'est le scénario 6.
- **Réversibilité** : sans objet, et c'est le résultat d'une mesure plutôt
  qu'un choix de confort (voir « Écart n°3 ») : la campagne est entièrement
  en LECTURE SEULE, donc rejouable à l'infini sans effet de bord, sans donnée
  à nettoyer et sans garde-fou d'opt-in.

## Données observées

### Service API `SEPMRA_PROD_MAN`

- Entity set produit : **`SEPMRA_C_PD_Product`** (et non un nom plus générique
  supposé a priori). **Draft-enabled** (protocole brouillon de Fiori
  Elements/BOPF) : clé composite `Product` + `DraftUUID` + `IsActiveEntity`.
- Champs utiles confirmés : `Name` (`Edm.String`), `Price` (`Edm.Decimal`),
  `Currency` (`Edm.String`), `ProductCategory` (`Edm.String`), `Supplier`
  (`Edm.String`), `ProductForEdit` (numéro produit réservé pour le brouillon,
  devient la clé `Product` de l'entité active à l'activation).
- `$metadata` ne déclare EXPLICITEMENT que la capacité `searchable` sur cet
  entity set (`declared_capabilities: ['searchable']`) : `creatable`,
  `updatable`, `deletable` sont muettes dans l'annotation, donc par défaut à
  `True` dans le contrat lu, ce qui n'est **pas une preuve** (la leçon déjà
  payée sur ce service, CLAUDE.md 2026-08-22 : une annotation absente devient
  un défaut, jamais une permission constatée). Seule la tentative réelle fait
  foi, et elle a été faite ci-dessous.
- **Création réelle vérifiée live** : `POST` sur `SEPMRA_C_PD_Product` avec le
  seul corps `{Name, ProductCategory, Supplier, Price, Currency}` crée un
  BROUILLON (`IsActiveEntity=False`, `Product=''`) et le serveur réserve un
  numéro de produit dans `ProductForEdit` (`EPM-000050` puis `EPM-000051`,
  deux créations successives). La réponse porte `Activation_ac: True` et une
  vingtaine de drapeaux d'action `_ac` (patron BOPF : chaque action métier a
  son drapeau d'activation contextuelle).
- **Function imports pertinents** (23 au total, tous action-oriented) :
  `SEPMRA_C_PD_ProductActivation` (active le brouillon), `SEPMRA_C_PD_ProductEdit`
  (rouvre un brouillon d'édition depuis une entité active, hypothèse la plus
  probable pour la modification du prix, **non vérifiée live**),
  `SEPMRA_C_PD_ProductDelete_ext` (action de suppression dédiée, présente et
  activée `Delete_ext_ac: True` sur le brouillon créé, **la voie de
  suppression probable, non vérifiée live** face à un `DELETE` OData nu).
- **Valeurs de référence lues live** : catégories (`SEPMRA_I_ProductCategory`,
  clé `ProductCategory`) : `Ballpoint Pens`, `Bands & Twine`, `Batteries`,
  `Bins & Baskets`, `Boxes & Box Tape` (échantillon des 5 premières). Fournisseurs
  (`SEPMRA_C_PD_Supplier`, clé `Supplier`) : `100000010` (« OffiPOR »),
  `100000011` (« bür-o-nline »), `100000012` (« Mein Ressort GmbH »),
  `100000013` (« Office Line Prag »), `100000014` (« Regular Custom Ltd »).
- **Brouillons orphelins déjà présents avant toute action de ce plan** : une
  lecture non filtrée de `SEPMRA_C_PD_Product` a montré des brouillons
  `IsActiveEntity=False` préexistants (`Name` « dfg », « dsgfdg »), preuve que
  ce système porte déjà des reliquats de tests manuels antérieurs, sans effet
  sur le catalogue actif (absents de tout `$count` ou lecture d'entité
  active).

### Canal WebGUI

- URL de session : `http://localhost:50000/sap/bc/gui/sap/its/webgui?sap-client=001`,
  identité confirmée (`system_id: A4H`, `client: 001`, `user: DEVELOPER`).
- SID du champ nom de table sur l'écran initial SE16 : `wnd[0]/usr/ctxtDATABROWSE-TABLENAME`
  (déjà couvert par `resources/fiori_keywords.resource`, `${WEBGUI_TABLE_NAME_SID}`).
- Champ de sélection généré pour `TABNAME` sur l'écran de sélection DD02L :
  `wnd[0]/usr/ctxtI1-LOW` (positionnel, comme sur le canal desktop).
- **`SNWD_PD` : `MAINFLAG` vide dans `DD02L`** (lu live via SE16 sur DD02L
  filtré `TABNAME=SNWD_PD` : `TABCLASS=TRANSP`, `CONTFLAG=L`, `MAINFLAG=''`).
  Un `MAINFLAG` vide signifie « maintenance non autorisée » côté dictionnaire,
  indépendamment du canal.

### Canal RFC

- Connexion RFC ouverte live (`ashost=vhcala4hci`, `sysnr=00`, `client=001`),
  `pyrfc 3.3.1` importable, binding natif présent.
- Table `TCDOB` (catalogue des objets de documents de modification) : le champ
  qui porte la classe d'objet est **`OBJECT`**, pas `OBJECTCLAS` comme le
  nom pourrait le suggérer (confirmé via `DD03L` filtrée sur `TABNAME=TCDOB`).
- **`TCDOB` filtrée sur `TABNAME='SNWD_PD'` rend ZÉRO ligne** : aucune classe
  d'objet de document de modification n'est enregistrée pour cette table sur
  ce système.
- **`CDPOS` filtrée sur `TABNAME='SNWD_PD'` rend ZÉRO ligne** : aucun document
  de modification n'a jamais été journalisé pour cette table.

## Écarts constatés à l'exploration (2026-09-21)

Le prompt d'origine demande de « modifier le prix via le canal WebGUI en mode
saisie SE16 » puis de « confirmer qu'un document de modification existe sur le
champ prix » via CDHDR/CDPOS. Les deux hypothèses sont contredites par
l'observation live, chacune pour une raison différente et vérifiée de deux
façons indépendantes.

### Écart n°1 : `SNWD_PD` n'est maintenable par écran sur AUCUN des deux canaux

Ce n'est pas une lacune de la bibliothèque WebGUI (qui ne couvre aujourd'hui
que la consultation SE16, `Display WebGui Table Contents`/`Extract Displayed
WebGui Grid`/`Count WebGui Table Entries`, jamais `btn[5]` « Create
Entries », par choix documenté dans `resources/fiori_keywords.resource`) :
c'est une restriction du **dictionnaire ABAP**, valable quel que soit le
canal qui l'atteint.

Deux preuves indépendantes, relevées le même jour sur la même cible :

1. **Lecture WebGUI de `DD02L`** : `MAINFLAG` vide pour `SNWD_PD`.
2. **Tentative réelle sur le canal desktop** (`Open Table Entry Creation`,
   page object `resources/page_objects/se16_table_entry.resource`, déjà
   éprouvé sur d'autres tables) : refus SAP de type `E`, texte exact
   « Table maintenance not allowed for table SNWD_PD ». Cette restriction
   confirme et généralise ce que `specs/simulation-ecriture-lecture-cross-canal.md`
   avait déjà établi le 2026-08-22 pour `/DMO/CARRIER` et les tables `SNWD_*`
   en général (§ Écart n°1 de ce plan-là) : c'est la même cible, la même
   restriction, revérifiée pour `SNWD_PD` précisément.

**Adaptation retenue** : la MODIFICATION du prix passe par le canal **API**
(protocole brouillon : rouvrir un brouillon d'édition sur l'entité active,
modifier le prix, ré-activer ; voie exacte à confirmer live par
sap-generator, voir Handoff). Le canal **WebGUI** est conservé dans le
scénario mais change de rôle : il devient un canal de **lecture de
vérification** (SE16 sur `SNWD_PD`, filtré par la clé technique du produit
de test), au même titre que le canal RFC. C'est un scénario cross-paradigme
tout aussi valable : la question posée n'est plus « WebGUI peut-il écrire »
mais « les trois canaux voient-ils la même vérité après l'écriture ».

### Écart n°2 : CDHDR/CDPOS ne portent aucune trace pour `SNWD_PD`

Le prompt suppose qu'une modification du prix laisserait un document de
modification lisible par `Read Change Documents` (CDHDR/CDPOS). Deux lectures
RFC indépendantes contredisent cette hypothèse sur ce système :

1. `TCDOB` (quelle classe d'objet suit quelle table) ne porte aucune ligne
   pour `TABNAME='SNWD_PD'` : aucun objet de document de modification n'a
   jamais été configuré pour cette table précise.
2. `CDPOS` elle-même, interrogée directement sur `TABNAME='SNWD_PD'`, ne porte
   aucune ligne : aucun changement n'y a jamais été journalisé, cohérent avec
   le point 1.

C'est attendu pour une app construite sur **BOPF** (le nommage des drapeaux
d'action `_ac` du brouillon lu ci-dessus, et le protocole brouillon
lui-même, en sont la signature) : ce framework journalise ses changements
dans ses propres tables de configuration (`/BOBF/...`), pas dans les
documents de modification classiques ABAP. Explorer cette piste serait un
plan à part entière, hors périmètre ici.

**Adaptation retenue** : la vérification RFC du plan ne porte plus sur une
TRACE de modification, mais sur une **troisième lecture indépendante** de la
valeur du prix (`RFC_READ_TABLE` sur `SNWD_PD`), qui complète l'assertion
reine (trois canaux, une seule vérité). Le scénario 7 CONSTATE l'absence de
document de modification comme un résultat attendu et documenté, plutôt que
de le supposer implicitement : c'est ce qui distingue une adaptation honnête
d'un simple contournement.

### Écart n°3 : le cycle d'écriture est cassé sur les DEUX systèmes du banc

Mesuré le 2026-09-21, après un redémarrage du conteneur `a4h`, puis une
restauration complète de ce conteneur depuis la sauvegarde du 2026-08-23, puis
une contre-épreuve sur le second système du banc (ABAP Platform 2023, cible
prouvée distincte : catalogue Gateway de 58 services contre 38 pour A4H).

| Geste | A4H 1909 (restauré) | ABAP 2023 |
| --- | --- | --- |
| Créer un brouillon | réussit | réussit |
| Activer le brouillon | `CM_EPM_REF_APPS/002` « Object node type DemoObject does not exist » | `/BOBF/FRW_COMMON/141` « Instance with the same key already exists » |
| Supprimer un brouillon | `CM_EPM_REF_APPS/002` (identique) | `CM_EPM_REF_APPS/002` (identique) |

Trois faits établis, chacun par une mesure et non par déduction :

1. **Ce n'est pas un état d'exécution.** Le refus survit à un redémarrage du
   conteneur ET à la restauration d'une image antérieure à toute manipulation
   de cette campagne. Les brouillons créés pendant l'exploration ne sont donc
   pour rien dans le défaut.
2. **Ce n'est pas propre à une release.** Le refus `DemoObject does not exist`
   frappe les deux images, au minimum sur le chemin de suppression : il vient
   du contenu applicatif EPM livré avec ces images trial, pas de la
   configuration du poste.
3. **La collision de clé du 2023 a une cause identifiée** : le compteur de
   numéros produit est désynchronisé des brouillons existants. Le système
   porte des brouillons orphelins anciens réservant `EPM-000042`, `EPM-000043`
   et `EPM-000051` à `EPM-000054`, et le serveur réattribue ces mêmes numéros
   aux brouillons neufs. La contourner reviendrait à brûler des numéros
   jusqu'à en trouver un libre.

**Adaptation retenue, et c'est la réversibilité qui tranche.** Même en
contournant la collision du 2023, le cycle resterait IRRÉVERSIBLE : aucun
chemin de suppression ne fonctionne sur aucune des deux cibles, donc chaque
passage laisserait une entité définitive dans un système partagé. Le risque
n°2 de ce plan étant non négociable, la campagne renonce à la création et
porte son assertion reine sur un produit EPM **déjà présent** (`HT-1000`,
existant sur les deux systèmes). Le scénario reste pleinement
cross-paradigme : la question posée est « les trois canaux voient-ils la même
vérité », pas « sait-on créer un produit ». Il devient en outre entièrement
en lecture seule, donc rejouable à l'infini sans opt-in.

## Scénarios

Toute la campagne est en **LECTURE SEULE** (voir « Écart n°3 ») : aucun
opt-in, aucune donnée créée, aucune donnée à nettoyer, rejouable à l'infini.

### 1. Ouvrir les trois canaux et vérifier les préflights

- **Étapes** : ouvrir le canal API (`Open Api Channel`), vérifier la Gateway
  (`Api Channel Should Be Available`) ; ouvrir le canal WebGUI (`Open WebGui
  Session`) et vérifier l'identité système lue ; ouvrir une connexion RFC et
  vérifier sa disponibilité (`Get Rfc Channel Status`, `Skip` propre si le
  canal est absent, comme `Skip Unless Rfc Channel Is Available`).
- **Résultat attendu** : les trois canaux répondent, sur le même système et le
  même mandant.
- **Critère d'arrêt** : un canal indisponible interrompt (ou saute, pour le
  RFC optionnel) avant toute écriture.

### 2. Prouver la cible avant toute lecture

- **Étapes** : établir quel système répond réellement, sur chacun des canaux
  ouverts, avant de lire la moindre donnée métier.
- **Résultat attendu** : la cible atteinte est celle attendue, prouvée par un
  critère qui DISCRIMINE les deux systèmes du banc.
- **Point de vigilance** : les deux conteneurs annoncent le même identifiant
  système (`A4H`) et le même nom d'hôte interne (`vhcala4hci`), donc ni l'un
  ni l'autre ne prouve quoi que ce soit. Deux discriminants mesurés le
  2026-09-21 : la **release** (754 contre 758, lue par le canal RFC ou par
  l'écran) et le **volume du catalogue Gateway** (38 services contre 58, lu
  par le canal API). Le port publié seul ne suffit pas comme preuve, puisque
  l'ICF sait rediriger vers le nom d'hôte virtuel partagé.

### 3. Lire le produit de référence par le canal API

- **Étapes** : lire l'entité produit ACTIVE du produit de référence du
  catalogue de démonstration, par sa clé technique ; relever son prix et sa
  devise.
- **Résultat attendu** : l'entité existe et porte un prix non vide.
- **Point de vigilance** : la lecture doit viser l'entité ACTIVE
  (`IsActiveEntity eq true`) : l'entity set est draft-enabled et agrège
  sinon des brouillons, dont ce système porte plusieurs reliquats.
- **Keywords métier manquants** : un keyword de lecture de produit par clé
  dans un page object dédié à `SEPMRA_PROD_MAN`, à créer par sap-generator
  (convention 1 : le chemin du service et les noms d'entity set n'ont pas à
  apparaître dans la suite).

### 4. Lire la même ligne par le canal WebGUI

- **Étapes** : ouvrir SE16 sur `SNWD_PD`, filtrer sur la clé technique du
  produit de référence, lire la ligne ; relever le prix.
- **Résultat attendu** : une ligne et une seule, portant la clé visée
  (assertion sur les ids techniques de colonnes, jamais un libellé affiché).
- **Point de vigilance** : lecture seule, jamais `btn[5]` (la restriction de
  l'écart n°1). La lecture doit confronter le relevé au total DÉCLARÉ par la
  grille, comme l'exige le contrat d'extraction commun aux canaux.
- **Keywords métier manquants** : une lecture WebGUI SE16 filtrée par clé
  technique (variante paramétrée de `Display WebGui Table Contents`,
  aujourd'hui non filtrée).

### 5. Lire la même ligne par le canal RFC

- **Étapes** : lire `SNWD_PD` par `RFC_READ_TABLE`, filtrée sur la clé
  technique du produit de référence, champs `PRODUCT_ID` et `PRICE`.
- **Résultat attendu** : une ligne, portant la clé visée et un prix non vide.
- **Keywords métier manquants** : un keyword métier RFC de lecture filtrée
  sur `SNWD_PD` (au-dessus de `Read Rfc Table`).

### 6. Assertion reine : les trois canaux rendent le même prix

- **Étapes** : confronter les trois valeurs relevées aux scénarios 3, 4 et 5.
- **Résultat attendu** : les trois lectures rendent EXACTEMENT le même prix.
- **Critère d'acceptation** : les trois valeurs sont comparées ENTRE ELLES,
  et pas seulement chacune à une valeur attendue : c'est ce qui prouve que
  les trois canaux regardent la même vérité et non trois copies divergentes.
- **Point de vigilance** : les représentations diffèrent d'un canal à
  l'autre (une décimale OData, un texte délimité par RFC, un texte d'écran
  côté WebGUI) : la comparaison se fait sur la valeur NUMÉRIQUE normalisée,
  jamais sur la chaîne brute, et le test doit le dire dans son message
  d'échec.

### 7. Constater l'absence de document de modification (résultat attendu et documenté)

- **Étapes** : interroger `TCDOB` par RFC sur `TABNAME='SNWD_PD'` ; si une
  classe d'objet existe, interroger `CDHDR`/`CDPOS` par `Read Change
  Documents` ; sinon, constater et journaliser l'absence.
- **Résultat attendu** : ZÉRO classe d'objet enregistrée et ZÉRO document de
  modification pour `SNWD_PD`, cohérent avec l'exploration (voir Écart n°2).
- **Critère d'acceptation** : ce résultat NÉGATIF est l'assertion, pas un
  échec du scénario. Si une future release de la cible enregistre une classe
  d'objet pour cette table, le scénario doit alors ÉCHOUER en le signalant
  (le comportement a changé et le plan doit être ré-exploré), jamais ignorer
  silencieusement le nouveau résultat.

### 8. Fermer les trois canaux sur tous les chemins

- **Étapes** : fermer le canal API, la session WebGUI et la connexion RFC, y
  compris après un échec en cours de campagne (teardown de suite).
- **Résultat attendu** : aucune session orpheline côté serveur.
- **Point de vigilance** : rien à nettoyer côté données, la campagne n'ayant
  rien écrit. La fermeture WebGUI prend un budget BORNÉ : un teardown doit
  rendre la main, et un déroulé de déconnexion a déjà coûté 361 s
  d'acharnement sur une cible de ce banc.

## Points de vigilance

**`SNWD_PD` n'est écrivable par AUCUN écran SAP GUI**, desktop ou WebGUI :
c'est une restriction du dictionnaire (`MAINFLAG` vide), pas une lacune de
bibliothèque. Ne jamais tenter d'ajouter un keyword d'écriture WebGUI SE16
pour cette table précise : il échouerait identiquement à la tentative
desktop déjà observée.

**Le service `SEPMRA_PROD_MAN` est un objet métier en brouillon (BOPF)** :
toute écriture suit le protocole créer-brouillon puis activer (et
probablement éditer-brouillon puis ré-activer pour une modification), jamais
un `POST`/`PATCH` en un seul appel sur l'entité active. La documentation
`$metadata` ne déclare presque aucune capacité explicitement : la tentative
réelle prime toujours sur l'annotation absente.

**Aucune trace CDHDR/CDPOS n'existe pour `SNWD_PD`** sur ce système : ne pas
supposer que l'audit applicatif de cette app passe par les documents de
modification classiques.

**Les deux systèmes portent des brouillons orphelins non supprimables**, et
c'est un état de banc dont toute lecture doit se protéger plutôt qu'une
anomalie à corriger : la restauration du conteneur `a4h` a effacé ceux de
l'exploration, les vérifications du 2026-09-21 en ont laissé un sur A4H et
deux sur le 2023, et le 2023 en portait déjà sept avant toute manipulation
de cette campagne. Aucun n'est activé, donc aucun n'apparaît dans un
`$count` ni dans une lecture d'entité ACTIVE ; en revanche une lecture non
filtrée de l'entity set produit les rend tous. D'où la règle du scénario 3 :
filtrer sur `IsActiveEntity eq true`, toujours.

**Un POST qui « expire » côté client peut avoir réussi côté serveur.**
Mesuré le 2026-09-21 sur le 2023 : le premier appel à ce service, jamais
sollicité depuis le démarrage, a dépassé 58 s et rendu un `TimeoutError`,
alors qu'il avait bel et bien créé un brouillon côté serveur (le rejeu a
pris 2,5 s et créé le SUIVANT). Sur un chemin d'écriture, un timeout n'est
donc pas une preuve de non-écriture, et la reprise doit constater l'état
avant de rejouer.

**Piège de pilotage rf-mcp rencontré pendant l'exploration.** Un appel de
mot-clé dont l'argument contenait littéralement une clé OData à apostrophes
et `=` (`...DraftUUID=guid'...',IsActiveEntity=false)...`) a été mal résolu
par la couche de résolution d'arguments de `execute_step` (« got positional
argument after named arguments »). Après cet échec, le registre de sessions
du canal API est resté VIDE pour le reste de l'exploration
(`List Api Sessions` rendait `{'api_sessions': []}` alors même qu'`Open Api
Channel` rapportait un succès juste avant), y compris en reconstruisant le
chemin problématique via une variable (`Evaluate` puis `${var}`) plutôt
qu'en dur. Seule une session rf-mcp neuve aurait vraisemblablement rétabli
un registre cohérent, non tentée ici faute de budget.

La **première moitié** de ce piège est confirmée et reproductible : le
2026-09-21, un `Delete Odata` dont le chemin portait la clé en dur a été
refusé par `execute_step` avec « expected 1 to 3 non-named arguments, got
0 », le `DraftUUID=guid'...'` ayant été lu comme un argument nommé. Le
remède tient : construire le chemin dans une variable (`Evaluate` puis
`${var}`) fait passer l'appel. La **seconde moitié** (registre de sessions
API vidé pour le reste de la session) ne s'est PAS reproduite ce jour-là :
plusieurs appels ont suivi le refus sans que la session soit perdue. Le
piège d'argument est donc réel, la casse de registre reste à confirmer.

## Écarts constatés à la génération (2026-09-21)

Suite produite : `tests/robot/cross/cycle_vie_produit_epm_trois_canaux.robot`,
validée live 7/7 sur A4H (client 001), deux exécutions consécutives.

### 1. Le produit de référence `HT-1000` n'existe pas sur cette cible

Le plan le donnait « relevé présent sur les deux systèmes » tout en demandant
de le vérifier plutôt que de le graver. La vérification dit non, et par deux
canaux indépendants :

- canal API : `SEPMRA_C_PD_Product` filtré `startswith(Product,'HT-') and
  IsActiveEntity eq true` rend ZÉRO entité, alors que le même filtre sur un
  témoin (`Product eq 'AR-FB-1000'`) en rend une ;
- canal RFC : `SNWD_PD` filtré `PRODUCT_ID LIKE 'HT-%'` rend ZÉRO ligne.

Ce n'est donc pas une particularité du service : la table elle-même ne porte
aucun produit de ce préfixe. Le catalogue EPM de cette image utilise les
préfixes `AR-FB-`, `AR-BK-` et voisins.

**Adaptation retenue** : le produit de référence est DÉCOUVERT à l'exécution
(`Establish Epm Reference Product` : le premier produit actif dans l'ordre des
clés), donc identique à chaque passage sur une cible donnée (la campagne reste
déterministe) mais valable sur n'importe laquelle. Relevé live sur A4H :
`AR-FB-1000`, 3.25 USD. Une constante gravée aurait fait échouer la campagne
entière sur une donnée de cible, en désignant le canal comme coupable.

### 2. Le canal WebGUI applique la notation décimale de l'UTILISATEUR

Le plan annonçait des représentations différentes ; la mesure précise la
cause, et elle est plus exigeante que « un texte d'écran ». Le prix relevé
vaut `3.25` par l'API et par le RFC, mais **`3,25` à l'écran** : le WebGUI
applique les formats de l'utilisateur, donc une valeur qui dépend du
paramétrage du compte et non de la donnée.

Deux conséquences encodées dans la suite :

1. la notation est LUE sur le système (`USR01-DCPFM` par RFC, valeur vide pour
   `DEVELOPER`, ce qui désigne la forme `1.234.567,89`) au lieu d'être
   supposée : un autre utilisateur du même système rendrait `1,234.50` pour le
   même prix, sans qu'aucune donnée n'ait bougé ;
2. la normalisation est scindée en DEUX mots-clés distincts
   (`Technical Price From Screen Text` et `Technical Price From Protocol
   Value`), parce qu'un seul mot-clé « normaliser un prix » aurait fini par
   être appelé sur les trois canaux : avec la notation par défaut de ce banc,
   le point est le séparateur de MILLIERS, donc décoder le `3.25` d'un
   protocole avec la notation de l'utilisateur le transformerait en `325`, en
   silence et sans lever.

### 3. Capacité ajoutée à la bibliothèque (convention #12)

Le plan demandait « le filtrage par clé technique aux lectures WebGUI SE16 ».
La mesure a montré que ce filtrage ne peut PAS s'écrire dans une couche
métier : sur l'écran de sélection de `SNWD_PD`, le critère `PRODUCT_ID` est
`wnd[0]/usr/ctxtI2-LOW`, alors que son voisin immédiat `NODE_KEY` est
`wnd[0]/usr/txtI1-LOW`. Le rang est positionnel (il suit le choix des champs
de sélection, réglage qui persiste par utilisateur) ET le préfixe de type
varie d'un champ à l'autre : un SID gravé est donc faux de deux façons, et il
le devient en silence, puisque l'écran répond, un AUTRE critère se remplit, et
la grille rend ensuite des lignes parfaitement lisibles qui ne sont pas celles
qu'on a demandées.

Ajouté dans `src/` : **`Get Webgui Selection Criteria`** (SapFioriLibrary), le
miroir web de `Get Se16 Selection Criteria`, qui DÉRIVE la carte
`{CHAMP: SID}` de la page. C'est possible parce que SE16 affiche en libellé le
nom TECHNIQUE du champ et non son texte court traduit, donc l'appariement
reste indépendant de la langue (convention 3). Mesuré live sur `SNWD_PD` : 23
critères dérivés, dont `PRODUCT_ID` et `PRICE`.

Le vocabulaire générique qui s'appuie dessus (`Display WebGui Table Contents
With Filter`, miroir WebGUI du mot-clé ECC du même nom) vit dans
`resources/fiori_keywords.resource`. À la différence du canal écran, il n'a
AUCUN dictionnaire de positions à maintenir par table.

### 4. Le scénario 8 est le teardown de la suite, non un huitième test

Le plan le qualifie lui-même de « teardown de suite ». La suite porte donc 7
tests et un `Suite Teardown` qui ferme les trois canaux sur tous les chemins,
avec un budget WebGUI court (10 s) et chaque fermeture tentée même si la
précédente a échoué. La propriété vérifiable, elle, est assertée par le
scénario 1, qui lit le REGISTRE réel des canaux au lieu de l'intention de la
suite.

### 5. Condition d'exécution : le canal RFC impose son interpréteur

Sous l'interpréteur par défaut du poste (3.14), la suite se SAUTE proprement
en nommant la cause et le remède (`pyrfc` n'a aucune roue précompilée
au-delà de 3.12). Le run live a donc été joué par le venv 3.12 qui porte le
canal, celui-là même qui sert le serveur rf-mcp. Ce n'est pas un défaut de la
suite (les deux branches sont éprouvées : sautée proprement, puis 7/7), mais
une condition à nommer dans toute commande d'exécution.

### 6. Le piège rf-mcp du chemin OData ne concerne pas cette suite

Le handoff signalait qu'un chemin portant une clé composite
(`DraftUUID=guid'...'`) est mal résolu par `execute_step`. Confirmé pendant
l'exploration, et sans effet ici : la suite ne construit aucun chemin à clé
composite, elle lit par `$filter`. Le contournement (construire le chemin dans
une variable) n'a donc pas eu à être employé.

### 7. Le rendu des libellés DIVERGE entre les deux releases, et la seconde a trouvé un défaut de la capacité

La contre-épreuve de portabilité n'était pas demandée ; elle a payé
immédiatement, et c'est le seul défaut de cette livraison qu'aucune exécution
sur la cible principale ne pouvait révéler.

Rejouée telle quelle sur la 2023, la suite a échoué dans son Suite Setup sur
un refus de la capacité neuve : « Le champ C est revendiqué par deux critères
(`ctxtI4-LOW` et `txtI5-LOW`) ». La garde d'ambiguïté avait donc fait
exactement son travail (refuser au lieu d'apparier au hasard), mais la carte
était inutilisable.

Cause MESURÉE sur l'écran : **la 2023 isole le caractère d'accélérateur
clavier de chaque libellé dans sa propre feuille du DOM**. `CATEGORY` s'y rend
en un parent `CATEGORY` (x 292 à 364) contenant une feuille `C` (x 292 à 302),
et la barre de menus en ajoute autant qu'elle a d'entrées (`M`, `E`, `S`,
`D`...). A4H, elle, rend le libellé d'un seul bloc. Ne lire que les feuilles du
DOM, ce que faisait la première version de la sonde, ramenait donc une poignée
de lettres seules que la couche pure prenait pour des noms de champ d'un
caractère, et `CATEGORY`, `CREATED_BY`, `CREATED_AT` et `CHANGED_BY` se
disputaient un champ nommé « C ».

**Correction** : la sonde remonte d'un niveau (les noeuds portant AU PLUS un
enfant, donc la feuille ET son parent immédiat) et la couche pure retire les
FRAGMENTS par un critère structurel, non typographique
(`drop_accelerator_fragments` : un fragment est géométriquement INCLUS dans un
libellé dont le texte contient le sien ; deux libellés distincts ne s'englobent
jamais, donc aucun vrai libellé ne peut être retiré, y compris un champ
réellement nommé d'une lettre). Le même tri écarte la duplication d'un libellé
rendu à trois niveaux du DOM, qui n'est pas une ambiguïté mais un seul libellé
vu trois fois. Sept cas de non-régression ajoutés au test hors navigateur,
aux pixels relevés sur les deux releases.

Après correction, les deux cibles rendent la MÊME carte de 23 critères
(`PRODUCT_ID` en `ctxtI2-LOW`, `PRICE` en `txtI17-LOW`), et zéro lettre seule.

**Portabilité prouvée** : la suite passe **7/7 sur les deux releases**, par
simple surcharge de variables. Deux faits de cible à connaître pour la 2023,
tous deux déjà documentés par le dépôt et confirmés ici : sa stratégie de
connexion WebGUI doit être `basic` (son formulaire ICF rend tous ses champs à
0x0, donc hors d'atteinte de tout moteur), et son déroulé de déconnexion
n'aboutit pas, ce que le teardown borne à 10 s en DISANT que la session
serveur est laissée à expirer. Mesures : A4H release 754, 38 services publiés,
11,9 s ; ABAP 2023 release 758, 58 services, 100,1 s (dont la déconnexion
bornée). Les deux annoncent le même identifiant système `A4H`, ce qui confirme
le point de vigilance du scénario 2 : seule la release discrimine.

### 8. Précondition devenue sans objet

La précondition « une valeur de catégorie produit et un fournisseur
existants » servait le chemin de création, abandonné à l'écart n°3. La
campagne ne crée rien, donc elle ne requiert plus ni catégorie ni fournisseur.

## Handoff sap-generator

1. Créer un page object dédié `resources/page_objects/sepmra_prod_man.resource`
   (chemin de service, noms d'entity sets, lecture d'un produit par sa clé) :
   convention 1, ces identifiants n'ont pas à apparaître dans la suite.
2. Choisir le produit de référence en le VÉRIFIANT live plutôt qu'en le
   gravant de mémoire : `HT-1000` a été relevé présent sur les deux systèmes
   du banc le 2026-09-21, mais c'est une donnée de cible, pas une constante.
3. Ajouter le filtrage par clé technique aux lectures WebGUI SE16 (variante
   paramétrée de `Display WebGui Table Contents`) et un keyword métier RFC de
   lecture filtrée sur `SNWD_PD` (au-dessus de `Read Rfc Table`), si ces
   capacités manquent encore à la génération. Une capacité qui manque à la
   BIBLIOTHÈQUE (et non au vocabulaire métier) se comble dans `src/`,
   convention #12.
4. Placer la suite sous `tests/robot/cross/`. Aucun opt-in : la campagne est
   en lecture seule.
5. Stampiller la suite avec ce plan.

## Revue indépendante (2026-09-21) et durcissement

Revue `sap-verifier` en lecture seule après génération, verdict initial
`needs_human`. L'assertion reine a été jugée réelle (la normalisation REFUSE
une valeur non conforme au lieu de la rattraper), les trois lectures
indépendantes, la capacité bien placée et son test unitaire au-dessus de la
moyenne du dépôt. Trois réserves portaient sur la PORTÉE des gardes, et
elles ont été traitées puis rejouées live.

1. **La garde de cible ne couvrait qu'un canal sur trois.** La release est
   lue par le RFC, mais la suite porte cinq variables de cible et une seule
   était confrontée à une mesure. Le scénario n'était pas théorique, ce plan
   décrivant la seconde release comme jouée par simple surcharge de
   variables : en oublier une fait lire DEUX systèmes, et comme les deux
   images portent le même jeu de démonstration au même prix, les trois
   canaux « s'accordent » et la suite est verte en comparant deux systèmes.
   Désormais **un discriminant par canal**, tous comparés à une valeur
   attendue dans le Suite Setup : release (RFC), volume du catalogue Gateway
   (API, 38 contre 58), adresse réellement atteinte (WebGUI, le bandeau ne
   portant ni release ni kernel).
2. **Le volume du catalogue était annoncé discriminant et seulement comparé
   à zéro.** Une garde de non-vacuité là où le plan promettait un
   discriminant : le motif exact que ce dépôt a déjà payé ailleurs.
3. **Le résultat négatif du scénario 7 n'avait pas de témoin.** Zéro ligne
   était asserté comme absence prouvée sans qu'aucune mesure n'établisse que
   cette lecture-là sait rendre des lignes. Un témoin positif (lecture non
   filtrée du catalogue, bornée) précède désormais le constat, sur le patron
   de la sonde canari de l'inventaire DDIC.

**Les deux nouvelles gardes ont été vues REFUSER**, chacune par une
provocation dédiée pointant l'autre conteneur du banc : elles échouent dans
le Suite Setup, donc aucun scénario ne lit, ce qui est la différence entre
empêcher et rougir. Preuve dérivée du run sous
`specs/evidence/cycle-vie-produit-epm-api-webgui-rfc.2026-09-21.json`,
sidecar de handoff produit et vérifié par `agent_contract.py`.

### Les trois réserves mineures, traitées à leur tour

Elles ne portaient pas sur l'invariant, mais chacune ouvrait un chemin vers un
résultat faux, donc aucune n'a été laissée en l'état.

4. **`parse_number` CONVERTIT au lieu de refuser** un texte non conforme à la
   notation lue : un écran rendant `3.25` sous une notation à virgule décimale
   donne `325`, et il suffirait que le protocole rende lui aussi `325` pour que
   les deux « coïncident » sur une donnée divergente. Fermé par un
   **aller-retour de notation** : la valeur d'écran normalisée, re-formatée
   dans la notation lue, doit reproduire le texte d'origine. La garde asserte
   donc la NOTATION elle-même et non plus la seule valeur.
5. **Les deux lectures du canal API ne se parlaient pas.** La découverte
   (lecture de liste) et la lecture par clé sont deux requêtes distinctes, et
   rien ne les comparait : une divergence entre elles serait passée inaperçue
   alors que l'assertion reine, qui ne voit que la seconde, aurait été verte.
   Les deux prix et les deux devises sont désormais confrontés.
6. **Un critère sans libellé propre adoptait celui d'un voisin.** Les candidats
   n'étant bornés par aucune distance, le « plus proche à gauche » pouvait se
   trouver très loin, et la garde de doublon ne le voyait que si le
   propriétaire légitime revendiquait AUSSI ce libellé, donc seulement quand
   les deux critères partageaient une ligne. Fermé par une règle
   **structurelle** et non métrique (donc insensible à l'échelle de rendu, la
   leçon du 2026-09-21) : un libellé appartient au PREMIER champ à sa droite,
   quelle que soit la nature de ce champ. Un critère dont le libellé
   appartient à un autre est traité comme un critère SANS libellé, donc
   ignoré, et l'appelant reçoit la liste de ce que l'écran porte vraiment
   plutôt qu'un nom emprunté.

Le cas réellement silencieux (le propriétaire du libellé n'est PAS un critère,
donc la garde de doublon reste muette) est épinglé par un test qui, sans le
correctif, voit la carte nommer un critère d'après le libellé d'un autre
champ. Les deux seuils de la sonde sont épinglés à leur tour.

**Contrôle de non-régression sur l'écran réel** : la règle d'interposition
pouvait RÉTRÉCIR la carte en silence, un scénario qui n'aurait pas rougi
puisque la suite ne filtre que sur un champ. La carte dérivée de l'écran de
sélection de `SNWD_PD` compte **23 critères**, soit exactement le relevé
d'avant correction ; le compte est désormais journalisé à chaque filtrage,
pour que l'écart soit constatable après coup.
