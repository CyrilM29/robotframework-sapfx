# Croisement DDIC et OData : disponibilité et cohérence des données ECC / S/4HANA

- **Canaux** : ECC (SAP GUI) **et** API (OData), croisés sur le MÊME système
- **Système observé** : A4H, ECC via `/H/vhcala4hci/S/3200`, client `001`,
  langue `EN` ; canal API via `http://vhcala4hci:50000`, même client
- **Nature** : campagne de recette **en lecture seule**, rejouable et
  paramétrable, réutilisable sur une cible ECC comme sur une cible S/4HANA
- **Objectif** : établir quelles tables et quels entity sets sont réellement
  disponibles sur la cible, prouver leur cohérence par deux canaux
  indépendants, et produire l'artefact qui servira d'entrée aux futures suites
  de simulation écriture / lecture
- **Préconditions** :
  - `SapEccLibrary` et `SapApiLibrary` chargées, `resources/ecc_keywords.resource`
    et `resources/api_keywords.resource` importées ;
  - identifiants injectés hors du plan et hors des logs (type `Secret`) ;
  - `Scripting Should Be Fully Enabled` et `Api Channel Should Be Available`
    passés avant toute exploration ;
  - `Use ALV Grid In Data Browser` appliqué une fois (réglage utilisateur
    persistant et idempotent) ;
  - autorisations de consultation SE16 sur `TADIR`, `DD02L`, `DD03L` et sur les
    tables du périmètre, plus l'accès au catalogue Gateway ;
  - aucune session SAP GUI résiduelle avant l'ouverture (`List Sap Sessions`) ;
  - fermeture garantie des DEUX canaux (`Close SAP` et `Close Api Channel`),
    y compris après un échec.

> **Statut : exploration live complétée le 2026-08-22 (A4H, client 001).** Les
> valeurs chiffrées ci-dessous sont des **observations datées de cette cible**,
> jamais des constantes du produit. Toute cible relit ses propres nombres.

## Réutilisation de la brique amont

La découverte et la classification DDIC ne sont **pas** replanifiées ici. Elles
sont déjà spécifiées par `specs/inventaire-tables-ecc-s4hana.md` et générées
dans `tests/robot/ui/ecc/inventaire_tables_ddic.robot` (validée 7/7). Cette
campagne les consomme comme brique amont, via les keywords du mixin DDIC :
`Validate Ddic Scope`, `Discover DDIC Objects By Scope`,
`Get Ddic Classification Map`, `Classify Ddic Objects`,
`Reach Se16 Selection Screen`, `Fill Multiple Selection`,
`Write Ddic Inventory Artifact`, `Compare Ddic Inventory Artifacts`.

Vérifié live le 2026-08-22 : le barème relu sur la cible (domaine `TABCLASS` =
`APPEND`, `INTTAB`, `TRANSP`, `VIEW`) puis `Classify Ddic Objects` sur les sept
tables du croisement retournent `TRANSP` / classe `table` pour `SNWD_PD`,
`SNWD_BPA`, `SNWD_SO`, `SNWD_SO_I`, `SNWD_BPA_CONTACT`, `SNWD_CONTACT` et
`SCARR`. La brique amont est donc directement réutilisable, sans adaptation.

Ce que cette campagne ajoute, et qui manque aujourd'hui : le **croisement avec
le canal API**, aux trois niveaux ci-dessous.

## Paramètres de campagne

Rien de figé qui supposerait A4H. Chaque exécution reçoit :

- `target_id` : identifiant stable et non secret de la cible ;
- `ecc_connection`, `ecc_client`, `ecc_language` : accès du canal GUI ;
- `api_base_url`, `api_client` : accès du canal API ;
- `services` : liste bornée de services métier à instruire (à défaut, sélection
  bornée dans le catalogue Gateway, les services d'infrastructure exclus) ;
- `couples_map` : nom du dictionnaire de correspondance entity set / table à
  utiliser (voir « La correspondance ne se devine pas ») ;
- `max_entity_sets`, `max_couples`, `max_field_contracts` : limites positives
  obligatoires, aucun mode illimité implicite ;
- `probe_existence`, `probe_volume`, `probe_field_contract` : les trois niveaux
  activables séparément ;
- `artifact_path` : sortie propre à la cible.

`ecc_client` et `api_client` doivent désigner le **même mandant** : sans cela le
niveau volumétrie compare deux populations différentes (voir les points de
vigilance). La campagne refuse une exécution où les deux diffèrent.

## Données observées

Tous les faits de cette section ont été relevés live le 2026-08-22 sur A4H,
client `001`, par appels rf-mcp unitaires, les deux canaux ouverts puis refermés
dans la même passe.

### Préflights

- ECC : `Scripting Should Be Fully Enabled` en succès ; `List Sap Sessions`
  retourne exactement une session, celle de la campagne, système `A4H`,
  client `001`, utilisateur applicatif, transaction initiale `SESSION_MANAGER`.
- API : `Gateway Should Be Active` en succès. Le catalogue Gateway expose 38
  services (relevé du préflight fourni avec la mission), dont une minorité de
  services métier : les services d'infrastructure (catalogue, ADT, page builder,
  transport, LREP, extracteur d'usage) ne sont pas des cibles.

### Niveau 1 : existence des entity sets

Trois services instruits, chaque entity set sondé par un comptage en UN
aller-retour `$batch` :

| Service | Entity sets déclarés | Adressables | En échec |
|---|---|---|---|
| `GWSAMPLE_BASIC` (chemin `iwbep`) | 16 | 16 | 0 |
| `SEPMRA_SHOP` | 9 | 9 | 0 |
| `SEPMRA_PROD_MAN` | 29 | 28 | 1 |

L'unique échec est décisif : `I_DraftAdministrativeData` répond **HTTP 403**,
code OData `CX_SADL_GW_PRIVIL_VIOLATION`, motif « accessible uniquement par
navigation ou expand ». Et cet échec est **prévisible depuis le `$metadata`** :
sur les 29 entity sets du service, exactement UN porte l'annotation
`sap:addressable="false"`, et c'est précisément celui-là. Le contrat du niveau 1
en découle : un entity set déclaré non adressable n'est pas une anomalie, c'est
une déclaration à respecter ; l'anomalie est un entity set déclaré adressable
qui ne répond pas.

### Niveau 2 : volumétrie croisée

**Égalités prouvées** (`$count` OData vs comptage SE16, même client) :

| Entity set | Service | `$count` | Table DDIC | Comptage SE16 |
|---|---|---|---|---|
| `ProductSet` | `GWSAMPLE_BASIC` | 205 | `SNWD_PD` | 205 |
| `Products` | `SEPMRA_SHOP` | 205 | `SNWD_PD` | 205 |
| `BusinessPartnerSet` | `GWSAMPLE_BASIC` | 21 | `SNWD_BPA` | 21 |
| `SalesOrderSet` | `GWSAMPLE_BASIC` | 10000 | `SNWD_SO` | 10000 |
| `SalesOrderLineItemSet` | `GWSAMPLE_BASIC` | 21853 | `SNWD_SO_I` | 21853 |
| `ContactSet` | `GWSAMPLE_BASIC` | 41 | `SNWD_BPA_CONTACT` | 41 |

**Égalité prouvée sous filtre** (le service projette un sous-ensemble) :

| Entity set | Service | `$count` | Table et filtre DDIC | Comptage SE16 |
|---|---|---|---|---|
| `Suppliers` | `SEPMRA_SHOP` | 10 | `SNWD_BPA` filtré `BP_ROLE` = `02` | 10 |
| `SEPMRA_C_PD_Supplier` | `SEPMRA_PROD_MAN` | 10 | idem | 10 |

Le filtre n'est pas supposé : les valeurs réellement présentes dans la colonne
`BP_ROLE` de `SNWD_BPA` ont été lues (`01` et `02`), puis le comptage filtré a
été exécuté et donne 10, contre 21 sans filtre.

**Inégalités attendues, avec leur cause établie** :

1. **Entity set draft-enabled.** `SEPMRA_C_PD_Product` retourne **214** en
   `$count` nu, alors que `SNWD_PD` en compte 205. Avec le filtre
   `IsActiveEntity eq true` le compte tombe à **205**, et avec
   `IsActiveEntity eq false` il vaut **9**. L'arithmétique boucle
   (205 + 9 = 214) : le `$count` nu d'une vue de consommation draft-enabled
   agrège les entités actives ET les brouillons. L'égalité avec une table DDIC
   n'a de sens que sous le filtre d'activité.
2. **Projection filtrée du service.** `Suppliers` = 10 face à `SNWD_BPA` = 21
   (cas ci-dessus, résolu par le filtre `BP_ROLE`).
3. **Périmètre lié à l'utilisateur ou à la session.** `ShoppingCarts` = 1 et
   `ShoppingCartItems` = 0 dans `SEPMRA_SHOP` : ces comptes dépendent de
   l'utilisateur connecté. Aucune égalité stable avec une table n'est
   attendue ; le couple doit être déclaré non comparable.
4. **Dépendance au mandant.** Les tables croisées portent un champ client
   (`SNWD_PD` et `SNWD_BPA` : champ `CLIENT`, élément de données `MANDT`, type
   `CLNT`, position 1, champ clé). Un comptage SE16 dans un mandant et un
   `$count` dans un autre comparent deux populations distinctes.

**Le contre-exemple qui tranche le débat de la correspondance** :
`SNWD_CONTACT` existe, est classée `TRANSP`, s'ouvre normalement dans SE16, et
contient **0 entrée**. La convention de nom l'aurait appariée à `ContactSet`
(41 entités) et aurait produit un échec faux. La table réelle est
`SNWD_BPA_CONTACT` (41), trouvée par recherche dans le référentiel, pas par
déduction.

### La correspondance entity set / table ne se devine pas

Instruit live : le document `$metadata` **ne porte aucune annotation nommant la
table source**. Inventaire complet des annotations `sap:` réellement présentes :

- `GWSAMPLE_BASIC` : `action-for`, `content-version`, `creatable`, `deletable`,
  `filterable`, `label`, `pageable`, `schema-version`, `semantics`, `sortable`,
  `supported-formats`, `unicode`, `unit`, `updatable` ;
- `SEPMRA_PROD_MAN` : les précédentes moins `unicode` et `pageable`, plus
  `addressable`, `aggregation-role`, `applicable-path`, `attribute-for`,
  `deletable-path`, `display-format`, `field-control`, `heading`, `quickinfo`,
  `searchable`, `text`, `value-list`.

Aucune ne désigne un objet du dictionnaire. Conclusion tranchée pour la
génération : la correspondance est une **donnée de configuration nommée métier**
qui vit dans la couche `resources/`, au même titre que les chemins de service
et les localisateurs (convention 1). Elle n'est jamais déduite d'une convention
de nom, et chaque couple déclaré est **prouvé par le test** (les deux comptages
sont exécutés et confrontés). Un entity set sans couple déclaré est
**rapporté** dans l'artefact avec le motif `no_declared_couple`, jamais apparié
en silence.

Forme proposée du dictionnaire (un couple = un enregistrement) : entity set,
service, table DDIC, filtre API éventuel, filtre DDIC éventuel, verdict attendu
(`equal`, `equal_under_filter`, `not_comparable`) et motif quand il n'est pas
`equal`.

### Niveau 3 : contrat de champs

Source DDIC : la table `DD03L`, lue par SE16. Son écran de sélection expose 17
critères positionnels, dont `TABNAME`, `FIELDNAME`, `AS4LOCAL`, `AS4VERS`,
`POSITION`, `KEYFLAG`, `ROLLNAME`, `CHECKTABLE`, `INTTYPE`, `NOTNULL` ; sa
grille de sortie expose 31 colonnes techniques, dont `FIELDNAME`, `POSITION`,
`KEYFLAG`, `ROLLNAME`, `DATATYPE`, `LENG`, `DECIMALS`, `DOMNAME`, `CHECKTABLE`.
Le filtre `AS4LOCAL` = `A` restreint à la version active.

**Rapprochement mesuré, `ProductSet` (21 propriétés) contre `SNWD_PD`** :

- normalisation consciente des acronymes (une suite de majuscules reste un
  seul jeton) : **15 propriétés sur 21** appariées ;
- normalisation naïve (séparateur devant chaque majuscule) : **14 sur 21**,
  parce que `ProductID` devient `PRODUCT_I_D` au lieu de `PRODUCT_ID` ;
- non appariées, et qui doivent le rester : `Description`,
  `DescriptionLanguage`, `Name`, `NameLanguage` (textes déportés, la table ne
  porte que les références `DESC_GUID` et `NAME_GUID`), `SupplierID`,
  `SupplierName` (association, la table ne porte que `SUPPLIER_GUID`) ;
- champs DDIC sans propriété : `.INCLUDE` (ligne technique d'include),
  `CLIENT`, `NODE_KEY`, `CREATED_BY`, `CHANGED_BY`, `DESC_GUID`, `NAME_GUID`,
  `SUPPLIER_GUID`, `PRODUCT_PIC_URL`, `DUMMY_FIELD_PD`.

**Rapprochement mesuré, `BusinessPartnerSet` (12 propriétés) contre
`SNWD_BPA`** : **9 sur 12** appariées. Les trois restantes sont le coeur du
sujet :

- `Address` est de type complexe (`CT_Address`) : elle ne correspond à aucun
  champ plat, mais à la table d'adresses jointe par `ADDRESS_GUID`. Écart
  structurel, pas lexical ;
- `BusinessPartnerID` correspond fonctionnellement à `BP_ID` et
  `BusinessPartnerRole` à `BP_ROLE` : ce sont des **renommages métier**
  qu'aucun normaliseur mécanique ne peut trouver. Et `BusinessPartnerID` est la
  **clé** de l'entity type.
- champs DDIC sans propriété : `.INCLUDE`, `ADDRESS_GUID`, `APPROVAL_STATUS`,
  `BP_ID`, `BP_ROLE`, `CHANGED_BY`, `CLIENT`, `CREATED_BY`, `DUMMY_FIELD_BPA`,
  `NODE_KEY`.

Règle de rapprochement à retenir pour la génération, en trois passes
ordonnées : (1) alias explicite déclaré dans la couche `resources/` pour le
couple, (2) normalisation consciente des acronymes, (3) tout le reste reste
**non apparié et rapporté**, jamais forcé. La qualité du contrat se lit sur
trois nombres : appariées, propriétés orphelines, champs DDIC orphelins. Une
dérive de schéma entre ECC et S/4HANA se voit sur ces trois nombres, pas sur un
verdict binaire.

### Candidats à une future simulation écriture / lecture

Rien n'a été écrit pendant cette exploration. Les candidats sont identifiés par
ce que la cible **déclare** et par ce qui a déjà été **constaté** ailleurs.

Côté API, les annotations d'entity set de `SEPMRA_SHOP` discriminent nettement :

| Entity set | Création | Modification | Suppression |
|---|---|---|---|
| `Reviews` | oui | oui | oui |
| `Products` | non | oui | non |
| `ShoppingCartItems` | non (import de fonction dédié) | oui | oui |
| `Suppliers`, `MainCategories`, `SubCategories`, `ReviewAggregates`, `ShoppingCarts`, `Images` | non | non | non |

`Reviews` est donc le seul entity set du service à cycle complet, et le
candidat naturel d'une écriture réversible par l'API.

Le contraste avec `GWSAMPLE_BASIC` est la leçon importante : ce service ne
déclare **aucune** restriction, donc ses 16 entity sets héritent des valeurs par
défaut et apparaissent tous créables, modifiables et supprimables, y compris les
aides à la recherche (`VH_LanguageSet`, `VH_CountrySet`, `VH_CurrencySet`), qui
projettent du paramétrage. « Déclaré modifiable » signifie donc seulement « non
déclaré en lecture seule » : c'est un critère nécessaire, jamais suffisant. Le
choix des cibles d'écriture reste une **liste blanche métier** portée par la
couche `resources/`, et la réversibilité doit être **constatée**, jamais
déduite.

Côté ECC, la mémoire projet documente (observation datée du 2026-07-17) que SE16
réalise création et suppression en place sur `SCARR` de façon réversible, la
création se déclenchant depuis l'écran initial. `SCARR` est classée `TRANSP`
sur la cible d'aujourd'hui, donc la piste reste ouverte.

Attributs que l'artefact doit porter pour qu'une suite d'écriture ultérieure
sache quoi cibler, sans re-explorer :

- pour chaque table : nom, valeur brute `TABCLASS` et classe normalisée,
  dépendance au mandant (présence d'un champ de type `CLNT`), champs clés
  (`KEYFLAG`), nombre d'entrées quand il a été mesuré ;
- pour chaque entity set : service, clés, adressabilité déclarée, création /
  modification / suppression déclarées, caractère draft-enabled (présence d'une
  propriété d'état d'activité), compte observé et filtre utilisé pour l'obtenir ;
- pour chaque couple : verdict volumétrique, filtre appliqué de chaque côté,
  et le triplet du contrat de champs ;
- pour la réversibilité : un champ `reversibility_observed` qui ne vaut que ce
  qui a été **constaté** (canal, date, preuve), et `unknown` par défaut. Une
  déclaration de métadonnées ne remplit jamais ce champ.

## Scénarios

### 1. Ouvrir les deux canaux et prouver qu'ils répondent

- **Étapes** :
  1. Ouvrir le canal API sur la cible et vérifier sa disponibilité par le
     préflight Gateway.
  2. Ouvrir la session SAP GUI sur la même cible et vérifier le préflight
     scripting.
  3. Recenser les sessions SAP GUI ouvertes et signaler toute session non
     attribuable à la campagne.
  4. Vérifier que le mandant du canal API et celui de la session GUI coïncident.
  5. Basculer le Data Browser en grille ALV.
- **Résultat attendu** : les deux canaux répondent, une seule session GUI
  ouverte, aucune fenêtre modale, mandants identiques. Le préflight qui échoue
  nomme sa remédiation au lieu de laisser un scénario métier échouer plus loin.
- **Critère d'arrêt** : préflight en échec, session résiduelle, ou mandants
  divergents. Produire la preuve du blocage puis fermer ce qui a été ouvert.
- **Keywords métier manquants** : `Cross Channel Preflight`, qui enchaîne les
  deux préflights et l'accord de mandant en un verdict unique JSON-safe.

### 2. Percevoir le contrat de chaque service du périmètre

- **Étapes** :
  1. Charger la liste bornée de services de la campagne.
  2. Pour chaque service, lire son contrat de métadonnées.
  3. Consigner, par entity set : les clés, l'adressabilité déclarée, les
     capacités d'écriture déclarées, le caractère draft-enabled.
  4. Appliquer la limite `max_entity_sets` et rendre toute troncature visible.
- **Résultat attendu** : chaque entity set du périmètre possède une fiche de
  contrat, tirée du service lui-même et jamais d'une convention.
- **Critères d'acceptation** : un service illisible en métadonnées bloque ce
  service et pas la campagne ; une limite atteinte produit un indicateur de
  troncature, jamais un succès silencieux.
- **Keywords métier manquants** : `List Business Service Entity Sets`, qui
  retourne la fiche complète par entity set. **Lacune de bibliothèque à
  combler** : l'analyseur de métadonnées expose aujourd'hui, par propriété, le
  type, la nullabilité et le libellé, mais **n'expose pas les annotations de
  niveau entity set** (adressabilité, création, modification, suppression,
  pagination). Ce sont exactement celles dont les niveaux 1 et le volet
  écriture ont besoin.

### 3. Prouver l'existence réelle de chaque entity set adressable

- **Étapes** :
  1. Écarter du sondage les entity sets déclarés non adressables et les
     consigner comme tels.
  2. Sonder les autres par un comptage groupé en un aller-retour, sans
     interrompre le sondage au premier refus.
  3. Consigner par entity set : le statut HTTP et, en cas de refus, le code
     d'erreur technique OData.
  4. Borner le nombre d'entity sets sondés par exécution.
- **Résultat attendu** :
  - un entity set déclaré adressable répond ; sinon la campagne le rapporte en
    échec avec son code technique ;
  - un entity set déclaré non adressable qui refuse la lecture n'est **pas** un
    échec : c'est la déclaration honorée ;
  - le diagnostic s'appuie sur le statut HTTP et le code d'erreur, jamais sur le
    texte du message, dépendant de la langue.
- **Critères d'acceptation** : la somme des adressables, des non adressables
  déclarés et des refus couvre tous les entity sets du périmètre ; aucun refus
  n'interrompt le sondage des suivants.
- **Keywords métier manquants** : `Probe Business Entity Sets`. Le keyword
  métier existant qui groupe des lectures en un aller-retour **échoue en bloc**
  dès qu'une opération refuse : inutilisable pour une sonde, qui doit
  enregistrer et poursuivre. Le keyword de bibliothèque sous-jacent, lui, sait
  ne pas échouer sur les erreurs partielles : c'est ce mode que la sonde doit
  emprunter.

### 4. Croiser la volumétrie d'un couple déclaré

- **Étapes** :
  1. Charger le dictionnaire de correspondance de la campagne.
  2. Pour chaque couple, lire le nombre d'entités côté API, en appliquant le
     filtre déclaré (filtre d'activité pour un entity set draft-enabled, filtre
     métier pour une projection).
  3. Compter les entrées de la table côté SE16, en appliquant le filtre DDIC
     déclaré.
  4. Confronter les deux nombres selon le verdict attendu du couple.
  5. Consigner les entity sets sans couple déclaré, sans les apparier.
  6. Borner le nombre de couples traités par exécution.
- **Résultat attendu** :
  - un couple `equal` a deux comptes égaux ;
  - un couple `equal_under_filter` a deux comptes égaux **une fois les filtres
    déclarés appliqués**, et l'écart sans filtre est consigné, pas masqué ;
  - un couple `not_comparable` n'est jamais asserté en égalité : son motif est
    consigné (périmètre utilisateur, dépendance de langue, agrégat) ;
  - un entity set sans couple est rapporté, jamais assimilé.
- **Critères d'acceptation** : aucun comptage n'est extrapolé d'une lecture
  paginée ; un compte nul est distingué d'un accès refusé et d'un sondage non
  exécuté ; les assertions portent sur des entiers et des noms techniques.
- **Keywords métier manquants** : `Cross Channel Volume Should Match`, qui prend
  un enregistrement de couple et rend un verdict JSON-safe, et
  `Count Business Entities With Filter`, la variante filtrée du comptage
  d'entités (indispensable au filtre d'activité des services draft-enabled).

### 5. Croiser le contrat de champs d'un couple déclaré

- **Étapes** :
  1. Lire les propriétés de l'entity type côté API, avec leurs libellés.
  2. Lire les champs de la table côté DDIC, version active, avec leur position,
     leur indicateur de clé et leur type.
  3. Rapprocher en trois passes ordonnées : alias déclarés, puis normalisation
     consciente des acronymes, puis rien.
  4. Produire les trois ensembles : appariés, propriétés orphelines, champs DDIC
     orphelins.
  5. Vérifier séparément que les **clés** de l'entity type sont appariées, par
     alias si nécessaire.
  6. Borner le nombre de contrats produits par exécution.
- **Résultat attendu** : un rapport à trois ensembles pour chaque couple.
  Aucune propriété n'est appariée de force ; les lignes techniques de la table
  (marqueurs d'include, champ client, champs d'administration, références par
  identifiant technique) apparaissent naturellement en orphelines DDIC et ce
  n'est pas une anomalie.
- **Critères d'acceptation** :
  - le rapprochement est déterministe et indépendant de l'ordre de lecture ;
  - un alias déclaré est toujours prioritaire sur la normalisation ;
  - une clé d'entity type non appariée est signalée explicitement : c'est le
    signal fort d'une dérive de schéma ou d'un alias manquant ;
  - une propriété de type complexe est classée comme telle, pas comme un simple
    échec d'appariement.
- **Keywords métier manquants** : `Read Ddic Table Fields` (lecture DD03L d'une
  table en liste de dictionnaires par colonne technique, version active) et
  `Compare Odata Properties With Ddic Fields` (logique pure, testable hors SAP :
  normaliseur, alias, trois ensembles, jamais d'appariement forcé).

### 6. Identifier les candidats à une simulation écriture / lecture

- **Étapes** :
  1. Pour chaque entity set du périmètre, relever les capacités d'écriture
     déclarées par le service.
  2. Pour chaque table du périmètre, relever la classe DDIC, la dépendance au
     mandant et les champs clés.
  3. Croiser avec la liste blanche métier de la campagne : un objet n'est
     candidat que s'il y figure.
  4. Consigner la réversibilité **constatée** ailleurs (canal, date, preuve) et
     laisser `unknown` par défaut.
- **Résultat attendu** : une liste de candidats, chacun portant le canal
  d'écriture envisagé, sa clé, sa classe DDIC et l'état de sa réversibilité.
  Aucune écriture n'est effectuée par cette campagne.
- **Critères d'acceptation** :
  - un service qui ne déclare aucune restriction ne produit **aucun** candidat
    par ce seul fait : l'absence de déclaration n'est pas une autorisation ;
  - un objet de paramétrage ou une aide à la recherche n'est jamais candidat,
    même déclaré modifiable ;
  - un import de fonction à effet de masse est explicitement marqué interdit.
- **Keywords métier manquants** : `List Write Simulation Candidates`, qui
  applique la liste blanche et retourne les fiches de candidats.

### 7. Produire l'artefact de croisement de la cible

- **Étapes** :
  1. Vérifier la cohérence des totaux (entity sets, couples, contrats).
  2. Écrire un document JSON trié et déterministe, au schéma versionné.
  3. Calculer son empreinte, hors horodatage.
  4. Conserver les preuves partielles quand une phase a été bloquée.
- **Résultat attendu** : artefact déterministe, lisible hors SAP, sans
  identifiant ni mot de passe, sans texte localisé utilisé comme oracle.
- **Critères d'acceptation** : deux exécutions sur les mêmes données donnent la
  même empreinte ; les paramètres de campagne font partie de l'artefact, afin
  qu'une comparaison entre périmètres différents soit impossible par accident.
- **Keywords métier manquants** : `Write Cross Channel Artifact`, miroir de
  l'écriture d'artefact déjà en place pour l'inventaire DDIC.

### 8. Comparer deux cibles à périmètre équivalent

- **Étapes** :
  1. Charger deux artefacts de même version de schéma.
  2. Vérifier la compatibilité des paramètres de campagne.
  3. Comparer les entity sets, les couples et les contrats de champs par nom
     technique, indépendamment de l'ordre.
  4. Produire les écarts : entity set apparu ou disparu, adressabilité changée,
     verdict volumétrique changé, contrat de champs dégradé (propriété ou champ
     apparu, disparu, ou passé d'apparié à orphelin).
- **Résultat attendu** : un rapport structuré qui distingue disponibilité,
  volumétrie et schéma. Aucune égalité stricte n'est exigée entre ECC et
  S/4HANA : c'est l'écart qui est l'information.
- **Critères d'acceptation** : une différence de langue, d'ordre ou
  d'horodatage ne crée aucun écart ; des périmètres incompatibles bloquent la
  comparaison ou la marquent explicitement non équivalente ; chaque écart est
  rattaché à des noms techniques et aux deux preuves.
- **Keywords métier manquants** : `Compare Cross Channel Artifacts`, logique
  pure hors SAP, retour JSON-safe et rapport Markdown.

### 9. Fermer la campagne sur tous les chemins

- **Étapes** :
  1. Annuler tout popup inattendu côté GUI.
  2. Fermer la session SAP GUI ouverte par la campagne.
  3. Fermer toutes les sessions du canal API.
  4. Vérifier qu'aucun alias créé par la campagne ne reste actif.
- **Résultat attendu** : aucune session SAP GUI orpheline, aucune session API ni
  connexion RFC laissée ouverte, y compris après un échec de préflight, une
  limite atteinte ou une erreur de sérialisation.
- **Keywords métier manquants** : aucun. Les deux fermetures existent et
  vivent dans le teardown de suite.

## Points de vigilance

**Mandant.** Les tables croisées portent un champ client de type `CLNT` en
première position et en clé. Le comptage SE16 se fait dans le mandant de
connexion GUI, le `$count` dans le mandant du canal API. Les faire diverger
compare deux populations et fabrique un faux écart : la campagne refuse
l'exécution plutôt que de rapporter une incohérence.

**Format des valeurs de filtre.** Le rôle de partenaire est stocké sur trois
caractères et vaut `01` ou `02` sur la cible observée. Un filtre saisi `2`
retourne 0 entrée, sans erreur : le vert et faux type. Ne jamais inventer une
valeur de code : la lire dans les données ou dans son domaine.

**Entity sets draft-enabled.** Le comptage nu d'une vue de consommation
draft-enabled agrège actives et brouillons. Un compte inchangé après un cycle
d'écriture ne prouve donc aucun nettoyage : c'est sur l'entité elle-même qu'il
faut vérifier, et la clé y est composite.

**Le `$batch` est un POST.** Même composé exclusivement de lectures, il
déclenche le protocole de jeton CSRF. Ce n'est pas une écriture, mais cela
suppose un canal authentifié et un jeton valide.

**Sonde tolérante.** Une sonde d'existence doit enregistrer les refus et
poursuivre. Le keyword métier de lecture groupée échoue en bloc au premier
refus : c'est le bon comportement pour préparer un jeu de données, et le
mauvais pour une sonde. Le mode tolérant existe au niveau bibliothèque et c'est
lui qu'il faut exposer sous un nom métier distinct.

**Rejet OData et rejet SE16 ne se ressemblent pas.** Un refus OData porte un
statut HTTP et un code technique exploitable. Un rejet SE16 porte un type de
message. Les deux sont des ancres indépendantes de la langue, mais ils ne se
substituent pas l'un à l'autre : un entity set inaccessible ne dit rien de la
table, et une table non consultable ne dit rien du service.

**Écrans de sélection SE16.** Les critères sont positionnels. La perception
sémantique de l'écran nomme chaque critère par son champ technique, ce qui rend
la carte de sélection **dérivable live** au lieu d'être maintenue à la main dans
la couche `resources/`. C'est la piste à privilégier pour toute table nouvelle
du périmètre : les dictionnaires écrits à la main dérivent, la perception non.
Les critères simples ne persistent pas entre deux passages dans SE16 (vérifié) :
aucune contamination d'une sonde à la suivante.

**Lecture de grille projetée.** La lecture restreinte à des colonnes techniques
attend une **liste** de noms. Une chaîne à séparateurs est prise pour un unique
nom de colonne et produit une erreur qui cite la chaîne entière : piège relevé
pendant l'exploration, à ne pas reproduire dans la suite générée.

**La grille ALV est un prérequis.** Sans le réglage utilisateur du Data Browser,
la sortie SE16 est une liste classique sans objet de grille exploitable.

**Le nom ne prouve rien.** Une table qui porte le nom apparent d'un entity set
peut exister, être consultable, et contenir zéro entrée pendant que la vraie
table sous-jacente en contient plusieurs dizaines. Le journal de réparation du
projet dit exactement la même chose côté localisateurs : un identifiant se
relève dans le système, il ne se déduit pas d'une convention. Le croisement
suit la même règle.

**Bornes.** Chaque niveau a sa propre limite et son propre compteur. Une limite
atteinte produit un indicateur de troncature visible dans le résumé, jamais un
succès silencieux, et les objets non traités restent dans l'artefact avec un
motif explicite.

**Lecture seule.** La campagne ne crée, ne modifie ni ne supprime aucune donnée
métier, par aucun des deux canaux. L'import de fonction de régénération de masse
exposé par l'un des services observés ne doit jamais être appelé.

**Pilotage rf-mcp.** Un seul processus pilote la session ECC, en appels
unitaires. Aucun keyword ne doit retourner un objet COM à travers la frontière
MCP. Les références numérotées de la perception interactive ne figurent ni dans
la suite générée ni dans l'artefact.

**Aucune attente fixe.** Les attentes passent par les primitives de
synchronisation des bibliothèques, jamais par une pause.

## Handoff sap-generator

Portes à franchir avant d'écrire la suite :

1. **Combler la lacune de bibliothèque** du niveau entity set : exposer, dans
   le contrat de métadonnées, les annotations d'adressabilité et d'écriture
   déclarées par le service. Sans elles, le scénario 3 ne peut pas distinguer
   un refus légitime d'une anomalie, et le scénario 6 n'a pas de matière.
   Prévoir les tests hors SAP correspondants.
2. **Exposer un mode de sonde tolérant** sous un nom métier distinct de la
   lecture groupée existante, dont le comportement en tout ou rien reste le bon
   pour la préparation de données.
3. **Créer le dictionnaire de correspondance** dans la couche `resources/`, avec
   les couples prouvés ci-dessus et leur verdict attendu. Un couple non prouvé
   n'y entre pas ; il entre dans la liste des entity sets sans couple.
4. **Placer la logique pure hors SAP** : normaliseur et rapprochement de champs,
   assemblage de l'artefact, empreinte, comparaison de deux cibles, rapport.
   Même arbitrage que pour l'inventaire DDIC : rejoindre le socle partagé en
   fait une surface produit publiée, avec l'engagement de compatibilité qui va
   avec ; le critère de choix reste de savoir si la comparaison de deux cibles
   est réellement exercée. Aujourd'hui aucune seconde cible n'est disponible,
   donc la comparaison se teste hors SAP.
5. **Ventiler la suite** : les scénarios purement API sous `tests/robot/api/`,
   les scénarios croisés sous `tests/robot/cross/`, les keywords métier
   nouveaux dans la couche `resources/` (canal API et canal ECC dans leur
   fichier respectif, le croisement dans un fichier dédié).
6. **Exécuter chaque étape live avant écriture**, sur les deux canaux, et
   fermer tout ce qui a été ouvert, même en cas d'échec.
7. **Stampiller la suite** avec ce plan après génération.

Décision laissée ouverte : la campagne doit-elle **découvrir** les services à
instruire dans le catalogue Gateway, ou les recevoir en paramètre. La découverte
est plus fidèle à l'esprit de l'inventaire DDIC, mais le catalogue observé mêle
services d'infrastructure et services métier sans critère technique fiable pour
les séparer, et une liste d'exclusion par nom serait exactement le genre de
convention que ce plan refuse ailleurs. La liste bornée en paramètre, avec une
découverte du catalogue consignée dans l'artefact à titre de perception, est la
piste recommandée tant qu'aucun critère technique de tri n'a été trouvé.

## Arbitrages rendus avant génération (2026-08-22)

### Porte 1 : fermée, et une observation du plan corrigée au passage

La lacune de bibliothèque est comblée dans `sapfx_common.odata_metadata` :
chaque entity set porte désormais `label`, `capabilities` (les annotations
`sap:` du niveau entity set, défaut de la Gateway appliqué quand l'attribut est
absent) et `declared_capabilities` (celles réellement écrites dans le document).
`write_simulation_candidates` en dérive la qualification d'écriture. Six tests
hors SAP couvrent la forme déclarée, la forme muette, le cas v4 et la
prédiction d'adressabilité.

Vérification live du 2026-08-22, hors rf-mcp (le serveur fige les modules
chargés à son démarrage, donc il ne pouvait pas servir le code corrigé) :

- `SEPMRA_PROD_MAN` : 29 entity sets, exactement un prédit non adressable,
  `I_DraftAdministrativeData`. Contre-épreuve HTTP sur ce seul entity set :
  **403 Forbidden**. La prédiction tient sans appel réseau, ce qui est
  exactement ce que le scénario 3 demandait.
- `SEPMRA_SHOP` : 9 entity sets, aucun non adressable.
- `GWSAMPLE_BASIC` : 16 entity sets, aucun non adressable.

**Correction d'une observation du plan.** Le plan retient que `GWSAMPLE_BASIC`
ne déclare aucune restriction. La mesure live dit l'inverse : ce service
déclare `sap:updatable` sur `SalesOrderSet`. Ce qui reste vrai, et qui était le
fond du constat, c'est qu'il se tait sur **quatre** autres entity sets, lesquels
paraissent donc modifiables par simple défaut.

La conséquence est une correction de conception, pas de rédaction : une garde
posée au niveau du **service** aurait été verte sur `GWSAMPLE_BASIC` tout en
laissant passer ces quatre faux candidats. La garde est donc **par entity
set** : chaque candidat porte `evidence` valant `declared` ou `default`, et
seul `declared` engage. Le drapeau de service subsiste, avec une portée
explicitement plus faible : faux, il disqualifie tout le document ; vrai, il ne
qualifie aucun entity set en particulier.

### Porte 4 : la logique pure rejoint le socle partagé

`src/sapfx_common/cross_channel.py`, aux côtés de `ddic_inventory.py`. Le
critère de choix posé par le plan est le bon, et c'est justement lui qui tranche
autrement qu'en 0.6.x : la comparaison de deux cibles n'est plus théorique ici.
Elle est la **demande** (une cible ECC et une cible S/4HANA), donc la
réutilisabilité l'emporte sur la prudence d'engagement de compatibilité. La
campagne doit aussi être exécutable depuis le pack Windows, où seul le socle
partagé est sur le pythonpath.

### Décision ouverte : liste bornée en paramètre, recoupée au catalogue

La recommandation du plan est retenue, avec une exigence de plus qui la rend
utile à la portabilité ECC / S/4HANA : la campagne reçoit sa liste de services
en paramètre **et** lit le catalogue Gateway pour vérifier que chacun y est
réellement publié sur la cible. Un service du périmètre absent du catalogue est
un écart de portabilité rapporté, pas une erreur de configuration silencieuse.
Le catalogue complet reste consigné dans l'artefact à titre de perception.

## Écarts constatés à la génération (2026-08-22)

Relevés live sur A4H, client `001`, pendant la génération de
`tests/robot/cross/croisement_ddic_odata.robot`. Tous les couples volumétriques
du plan ont été re-mesurés et confirmés (205, 205, 21, 10000, 21853, 41, et
`SNWD_CONTACT` toujours à 0 entrée) ; l'unique entity set non adressable de
`SEPMRA_PROD_MAN` répond toujours 403 avec le code
`CX_SADL_GW_PRIVIL_VIOLATION`. Les écarts ci-dessous portent sur les points où
la réalité observée ne correspond pas à ce que le plan retient.

### 1. `GWSAMPLE_BASIC` déclare bien plus que `SalesOrderSet`

Le plan (section « Candidats à une future simulation ») affirme que ce service
ne déclare **aucune** restriction, et l'arbitrage l'a corrigé en « il déclare
`sap:updatable` sur `SalesOrderSet` ». La mesure va plus loin : **12 des 16**
entity sets portent des annotations d'écriture, dont les onze aides à la
recherche `VH_*`, qui déclarent `creatable`, `updatable` et `deletable` à
**faux**. Elles sont donc écartées des candidats par la bibliothèque
elle-même, et non par la liste blanche métier.

Le fond du constat tient : **quatre** entity sets restent muets
(`BusinessPartnerSet`, `ContactSet`, `ProductSet`, `SalesOrderLineItemSet`) et
apparaissent, par simple défaut, créables, modifiables et supprimables. Ce que
la mesure invalide, c'est la formulation « des aides à la recherche qui
apparaissent ainsi supprimables » : sur cette cible, les aides à la recherche
sont précisément celles qui se déclarent en lecture seule.

Ce que la suite en fait : la garde `evidence` par entity set est appliquée
telle qu'arbitrée, et les quatre entity sets muets ne produisent aucun
candidat.

### 2. `Reviews` n'est pas le candidat naturel de `SEPMRA_SHOP`

Le plan présente `Reviews` comme le seul entity set du service à cycle complet
(création, modification, suppression « oui ») et comme « le candidat naturel
d'une écriture réversible par l'API ». La mesure dit l'inverse : `Reviews` est
**entièrement muet**, ses trois « oui » venaient des valeurs par défaut de la
Gateway. Sous la garde arbitrée, `Reviews` n'est donc **pas** candidat, tandis
que `Products` et `ShoppingCartItems` le deviennent, eux, parce qu'ils portent
des annotations.

Ce que la suite en fait : elle applique la garde et rapporte les candidats
mesurés, sans privilégier `Reviews`.

### 3. Une garde `evidence` vraie peut reposer sur des restrictions

Corollaire du point 2, et c'est l'observation la plus utile pour la future
suite d'écriture. Les deux candidats retenus passent la garde grâce à des
annotations qui **interdisent** d'autres verbes : `Products` déclare
`creatable="false"` et `deletable="false"` et doit son unique capacité
autorisée (`updatable`) au silence du service ; `ShoppingCartItems` déclare
`creatable="false"` et doit `updatable` et `deletable` au même silence. Sur
cette cible, **aucun** candidat n'a de capacité à la fois autorisée ET
déclarée.

> **Tranché le 2026-08-22 : la garde est durcie.** `evidence` se dérive
> désormais de `declared_allowed` dans
> `sapfx_common.odata_metadata.write_simulation_candidates` : un verbe n'engage
> que s'il est explicitement PERMIS, une interdiction déclarée ne faisant plus
> office d'appui. Sur A4H, le compte de candidats tombe de deux à **zéro**.
>
> Et c'est le résultat qui apprend quelque chose : ce n'est pas la garde qui
> était trop stricte, c'est le `$metadata` qui ne peut pas répondre à la
> question posée. Une annotation dit ce que le SERVICE permet ; elle ne dit
> rien de ce qui est **réversible**, ni de ce qui est nettoyable après coup,
> qui sont les deux vraies conditions d'une simulation d'écriture. Le champ
> `reversibility_observed`, à `unknown` par construction, nommait déjà la
> preuve manquante. La conclusion est donc structurelle : la qualification
> d'une cible d'écriture demande DEUX sources, une déclaration ET une
> observation datée. La seconde ne peut pas venir de cette campagne, qui est en
> lecture seule : elle vient d'un cycle réversible exécuté à part, spécifié
> dans `specs/simulation-ecriture-lecture-cross-canal.md`.

Ce que la suite en faisait avant cet arbitrage : elle ne changeait pas la règle
(la garde restait `evidence`), mais chaque fiche de candidat portait déjà
`declared_allowed`, l'intersection des capacités autorisées et des
capacités déclarées. Vide, elle signale que la capacité visée repose sur le
silence du service. **Point à trancher avant d'écrire quoi que ce soit** :
faut-il durcir la garde en exigeant `declared_allowed` non vide, ce qui ne
laisserait aucun candidat sur cette cible.

### 4. L'écran de sélection SE16 de `DD03L` expose 31 critères, pas 17

Le plan (niveau 3) relève 17 critères positionnels. Live, il en expose **31**
(`TABNAME` à `SRS_ID`), et la grille de sortie en expose 31 également. L'écart
n'est pas une erreur du plan : le choix des champs de sélection **persiste par
utilisateur** et déplace les critères `I<n>`.

Ce que la suite en fait : elle ne maintient aucune carte de critères écrite à
la main. Le keyword `Get Se16 Selection Criteria` la **dérive** de la
perception sémantique de l'écran, où chaque critère porte son nom technique de
champ, et `Read Ddic Table Fields` résout `TABNAME` et `AS4LOCAL` par nom. Un
critère attendu et absent échoue en listant ceux réellement présents. C'est la
piste que le plan recommandait lui-même dans ses points de vigilance.

### 5. Une liste illustrative incomplète sur `BusinessPartnerSet`

Les nombres du plan sont confirmés (9 propriétés appariées sur 12 sans alias,
11 avec les deux alias déclarés). En revanche son inventaire des champs DDIC
orphelins omet `WEB_ADDRESS` : ce champ existe bien dans `SNWD_BPA` (position
0007) et il est APPARIÉ à la propriété `WebAddress`, ce qui explique le
neuvième appariement que le plan ne détaille pas. Seule la liste illustrative
était incomplète, pas le décompte.

### 6. Deux pièges d'écriture Robot, sans effet sur le plan

Consignés parce qu'ils ont coûté un run et qu'aucune porte statique ne les
attrape : un `$variable` placé dans le **corps** d'une compréhension Python
d'un `Evaluate` n'y est pas visible (portée Python), et le `--dryrun` ne le
voit pas ; un comptage DDIC **filtré** ne doit jamais alimenter la fiche de
volumétrie d'une table (sans quoi `SNWD_BPA` porterait 10 au lieu de 21). Les
deux ont été trouvés au run live et corrigés.
