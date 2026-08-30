# Campagne de reconnaissance du canal RFC (cible ABAP Platform trial)

- **Canal** : RFC / BAPI (`SapApiLibrary`, `pyrfc`), le canal sans écran ET
  sans HTTP. Croisement ponctuel avec le canal OData du même système.
- **Système observé** : ABAP Platform trial en conteneur Docker, `sysId` A4H,
  release 754, kernel 777, base HDB, hôte applicatif `vhcala4h` (172.17.0.2),
  joint en `ashost=localhost`, `sysnr=00`, mandant `001`, utilisateur
  `DEVELOPER`, langue `EN`.
- **Exploration live** : 2026-08-27, cinq passes de sonde contre le système
  réel. Tous les faits ci-dessous sont mesurés, aucun n'est supposé.
- **Posture** : LECTURE SEULE. Aucun scénario n'écrit dans le système. La LUW
  n'est ouverte que pour prouver qu'on sait la refermer.

## Préconditions

1. **Interpréteur Python 3.10 à 3.12.** `pyrfc` n'a aucune roue précompilée
   au-delà de 3.12, et toutes ses versions PyPI sont `yanked` depuis
   l'archivage du projet par SAP : la version s'épingle (`pyrfc==3.3.1`) et le
   choix d'interpréteur se fait à la création du venv, jamais après. Le poste
   d'exploration utilise un venv dédié en 3.12.10.
2. **Runtime NW RFC présent.** Mesuré sur ce poste : le composant
   « SAP NWRFC x64 Shared » de SAP GUI for Windows 8.00 dépose `sapnwrfc.dll`
   et les `icu*50` dans `System32`, donc le SDK sous licence n'a pas été
   nécessaire. Sur un poste ou un runner sans SAP GUI, le SDK redevient le
   prérequis (`packaging/install-rfc.ps1`).
3. **Identifiants par la ligne de commande** (convention #11) : aucun mot de
   passe committé, `-v "RFC_PASSWORD: Secret:…"`.
4. **Suite neutre par défaut.** Sur un poste sans `pyrfc`, la suite se saute
   au lieu de rougir : le canal RFC est optionnel dans ce dépôt, et une suite
   qui rougit là où rien n'est cassé finit désactivée.

## Données observées

### Identité du système, telle que le canal la rend

| Source | Champ | Valeur relevée |
|---|---|---|
| attributs de connexion | `sysId` / `client` / `user` | `A4H` / `001` / `DEVELOPER` |
| attributs de connexion | `partnerRel` / `kernelRel` | `754` / `777` |
| attributs de connexion | `rfcRole` / `type` | `C` / `E` |
| `RFC_SYSTEM_INFO` | `RFCPROTO` / `RFCSAPRL` / `RFCKERNRL` | `011` / `754` / `777` |
| `RFC_SYSTEM_INFO` | `RFCHOST` / `RFCIPADDR` | `vhcala4h` / `172.17.0.2` |
| `RFC_SYSTEM_INFO` | `RFCDBSYS` / `RFCOPSYS` | `HDB` / `Linux` |
| `STFC_CONNECTION` | `RESPTEXT` | contient `Sysid: A4H` et `Logon_Data: 001/DEVELOPER/E` |

`RFC_PING` répond par un **dictionnaire vide**. C'est un succès : il n'y a
rien à y lire, seule l'absence d'exception fait foi.

### Volumétries et lectures relevées par `RFC_READ_TABLE`

| Table | Critère | Résultat mesuré |
|---|---|---|
| `T000` | aucun | 2 mandants : `000` et `001`, tous deux « SAP SE / Walldorf » |
| `SCARR` | aucun | 18 compagnies |
| `SCARR` | `CARRID EQ 'LH'` | `Lufthansa`, devise `EUR` |
| `SPFLI` | `CARRID EQ 'LH'`, `rowcount=3` | `0400` FRANKFURT vers NEW YORK, `0401` retour, `0402` |
| `SNWD_PD` | aucun | 205 produits |
| `DD02L` | `TABNAME EQ 'SCARR'` | `TABCLASS = TRANSP` |
| `DD03L` | `TABNAME EQ 'DD03L'` | 31 champs réels, largeurs cumulées 310 caractères |
| `TBTCO` | aucun | 4719 runs de job : `F`=4597, `Z`=105, `A`=10, `S`=7 |
| `SCARR` | `CARRID EQ 'ZZ'` | liste vide, sans erreur |
| `SFLIGHT` | `CARRID EQ 'LH' AND CONNID EQ '0400'` | `PRICE` rendu `"666.00"`, devise `EUR` |

### Le même fait par deux canaux

`SNWD_PD` comptée par RFC vaut **205**, et `$count` de l'entity set
`Products` du service OData `SEPMRA_SHOP` du même système vaut **205** aussi.
C'est le croisement que la campagne verrouille : deux protocoles
indépendants, une seule réalité.

### BAPI

| Appel | Observation |
|---|---|
| `BAPI_USER_GET_DETAIL` sur `DEVELOPER` | succès, `LOGONDATA` renseigné |
| `BAPI_USER_GET_DETAIL` sur un utilisateur inconnu | `RETURN` porte un message de type `E`, id `01`, numéro `124` |
| `BAPI_FLIGHT_GETLIST` sur `LH` | `RETURN` de type `S`, `FLIGHT_LIST` peuplée, `PRICE` en `Decimal` |
| `BAPI_MONITOR_GETLIST` | rend `BAPILIST`, l'inventaire des BAPIs du système |
| `BAPI_TRANSACTION_COMMIT` / `_ROLLBACK` | `RETURN` vide, donc succès |

Différence de typage à retenir : le **même prix** revient en chaîne
`"666.00"` par `RFC_READ_TABLE` (qui rend du texte délimité) et en
`Decimal('666.0000')` par la BAPI (qui rend le type ABAP). Une assertion
numérique doit convertir, jamais comparer les deux représentations.

### Jobs de fond

`TBTCO` porte **4719 runs** répartis sur quatre statuts. Correction d'une
mesure antérieure : une première lecture plafonnée à 200 lignes les avait tous
vus `F` et laissait croire que la cible ne portait que des jobs terminés. Elle
porte en réalité de quoi éprouver **toutes** les issues de l'attente, sans rien
écrire :

| Issue attendue | Cible relevée | Statuts du job |
|---|---|---|
| `done` | `RSUPG_RUN_TASK_ONCE` | `F`=21 |
| `aborted` | `EU_PUT`, `EU_REORG`, `OCS_QUEUE_IMPORT`, `RSBKCHECKBUFFER`, `SAP_IWFND_METERING_AGG` | au moins un `A`, mêlé à des `F` |
| `waiting` (pipeline) | `RDDIMPDP` | `F`=300, `S`=1 |
| `waiting` (statut non cartographié) | `SAP_COLLECTOR_FOR_PERFMONITOR` | `Z`=69 |
| `missing` | n'importe quel nom absent | aucune ligne |

Trois observations qui font la valeur du scénario 9 :

- **`A` prime sur `F`.** Les cinq jobs annulés portent aussi des dizaines de
  runs terminés, et l'attente échoue quand même : c'est le bon comportement,
  un run annulé est un fait à remonter, pas une statistique à moyenner.
- **Le statut `Z` n'est pas cartographié par la bibliothèque** : elle l'affiche
  `Z=69 (?)`. Son élément de données est `BTCSTATUS` sur un domaine `CHAR1`,
  donc le dictionnaire ne porte aucune liste de valeurs à consulter, et la
  signification de `Z` n'est PAS établie ici : elle ne sera pas devinée.
- **Le repli est sûr**, et c'est ce que le scénario verrouille : devant des
  statuts qu'elle ne connaît pas, la logique continue d'attendre au lieu de
  conclure au succès. Un statut inconnu pris pour un `done` serait exactement
  le « vert et faux » que ce dépôt traque.

Un nom de job absent produit un échec qui nomme la cause (« aucun job trouvé
sous ce nom ») et rappelle `jobcount=` et SM37.

### Refus, classés par code technique

Aucun de ces cas ne se reconnaît à son texte, qui est localisé ou verbeux.
Le code technique, lui, est stable (convention #3).

| Cas provoqué | Classe | Code technique |
|---|---|---|
| Mot de passe faux | `LogonError` | `RFC_LOGON_FAILURE` |
| Mandant inexistant | `LogonError` | `RFC_LOGON_FAILURE` |
| Hôte ou `sysnr` injoignable | `CommunicationError` | `RFC_COMMUNICATION_FAILURE` |
| Table inexistante | `ABAPApplicationError` | `TABLE_NOT_AVAILABLE` |
| Champ inexistant | `ABAPApplicationError` | `TABLE_WITHOUT_DATA` |
| Module fonction inexistant | `ABAPApplicationError` | `FU_NOT_FOUND` |
| Paramètre inconnu du module | `ExternalRuntimeError` | `RFC_INVALID_PARAMETER` |
| Alias jamais ouvert, ou déjà fermé | `RuntimeError` de la bibliothèque | message nommant `Open Rfc Connection` |

Deux enseignements portés par ce tableau, et c'est pour eux qu'il existe :

- **Mot de passe faux et mandant inexistant partagent le code**
  `RFC_LOGON_FAILURE`. Seul le texte les sépare, donc un test ne peut pas
  prétendre distinguer ces deux causes : il constate un refus d'ouverture de
  session, et c'est tout ce qu'il peut affirmer honnêtement.
- **Un champ inexistant sort en `TABLE_WITHOUT_DATA`**, c'est-à-dire un code
  qui accuse la **table** d'être vide alors qu'elle est pleine et que le
  fautif est un **nom de champ**. Vérifié trois fois : un champ inventé sur
  `SCARR` (18 lignes), le seul `AUTHCLASS` sur `DD03L`, et une liste de 19
  champs dont 2 n'existent pas sur cette release. Contre-épreuve faite : les
  31 champs réels de `DD03L` passent tous. C'est le piège de diagnostic du
  canal, celui qui envoie chercher un problème de données là où il y a une
  faute de frappe.

### Garde de la bibliothèque, avant tout appel réseau

Une clause `OPTIONS` de plus de 72 caractères est refusée **côté client** par
`sapfx_common.rfc_tables`, avec le remède nommé (découper en clauses `AND`).
Mesuré : une clause de 104 caractères ne part jamais sur le réseau. C'est la
limite propre de `RFC_READ_TABLE`, dont le dépassement produirait sinon un
comportement silencieusement tronqué.

## Scénarios

### 1. Le canal s'ouvre et prouve à quel système il parle

- **Étapes** : ouvrir le canal RFC sur la cible ; lire les attributs de
  connexion ; appeler `RFC_SYSTEM_INFO`.
- **Résultat attendu** : les deux sources s'accordent sur `sysId`, la release
  et le kernel. Le mandant servi est celui demandé. Aucune assertion sur un
  texte localisé.
- **Pourquoi** : un canal ouvert ne dit pas encore vers quoi. Une campagne
  qui ne prouve pas l'identité de sa cible peut être verte contre le mauvais
  système, ce que ce dépôt a déjà vécu côté web avec un nom d'hôte partagé.

### 2. Les sondes de vie répondent

- **Étapes** : `RFC_PING` ; `STFC_CONNECTION` avec un texte choisi ;
  `STFC_STRUCTURE` avec une structure remplie.
- **Résultat attendu** : `RFC_PING` ne lève pas (et sa réponse vide n'est pas
  assertée comme un contenu) ; l'écho de `STFC_CONNECTION` rend exactement le
  texte envoyé ; `RESPTEXT` porte le `sysId` de la cible ; `STFC_STRUCTURE`
  renvoie la structure et une table non vide.

### 3. La lecture générique de table est bornée et filtrée

- **Étapes** : lire `T000` ; lire `SCARR` filtrée sur une compagnie ; lire
  `SPFLI` avec un plafond de lignes ; lire une table avec un filtre qui ne
  ramène rien.
- **Résultat attendu** : les mandants attendus sont présents ; le filtre rend
  la seule compagnie visée avec sa devise ; le plafond est respecté ; un
  filtre sans correspondance rend une liste vide et **pas** une erreur.
- **Keywords métier manquants** : lecture de table par RFC, comptage par RFC.

### 4. Le même fait, deux canaux, un seul verdict

- **Étapes** : compter `SNWD_PD` par RFC ; compter l'entity set `Products` du
  service marchand par OData sur le même système et le même mandant ;
  confronter.
- **Résultat attendu** : égalité stricte des deux comptes.
- **Points de vigilance** : les deux canaux doivent viser le même mandant,
  sans quoi on compare deux populations et l'on fabrique un écart inexistant.
  Le premier appel OData d'un service jamais sollicité sur un système froid
  peut dépasser le délai par défaut : ce n'est pas une panne de réseau.

### 5. Les refus se classent par code, jamais par texte

- **Étapes** : provoquer, sur la connexion ouverte, une table inexistante, un
  champ inexistant, un module inexistant et un paramètre inconnu.
- **Résultat attendu** : chaque échec porte son code technique attendu
  (`TABLE_NOT_AVAILABLE`, `TABLE_WITHOUT_DATA`, `FU_NOT_FOUND`,
  `RFC_INVALID_PARAMETER`). Le cas du champ inexistant est asserté **avec sa
  bizarrerie assumée** : le code désigne la table, la faute est dans le champ.
- **Keywords métier manquants** : une assertion « cet appel RFC échoue avec
  le code technique X », qui capture l'échec et compare le code, jamais le
  message.

### 6. La garde de clause protège avant le réseau

- **Étapes** : demander une lecture dont la clause de sélection dépasse la
  limite du module.
- **Résultat attendu** : refus immédiat de la bibliothèque, message nommant
  la limite, la longueur constatée et le remède. Aucun appel n'atteint le
  serveur.

### 7. Une BAPI est jugée sur le type de ses messages

- **Étapes** : appeler une BAPI de lecture sur un objet existant ; appeler la
  même sur un objet inexistant ; refermer la LUW.
- **Résultat attendu** : le premier appel rend ses données ; le second
  **échoue** en listant le message bloquant par son type et son identifiant,
  jamais par son libellé ; le rollback rend un `RETURN` vide.
- **Points de vigilance** : la décision se prend sur le TYPE (`E`/`A`/`X`),
  conformément à la convention #3. Le texte n'est joint que pour le lecteur.

### 8. L'inventaire des BAPIs est la perception du canal

- **Étapes** : demander au système la liste de ses BAPIs.
- **Résultat attendu** : une liste non vide, dont les entrées portent type
  d'objet, nom métier et nom ABAP. Le scénario constate la forme et le volume,
  il ne fige aucun catalogue (il varie d'un système à l'autre).

### 9. L'attente d'un job de fond distingue ses quatre issues

- **Étapes**, toutes en lecture seule, avec un délai court sur les branches
  qui ne peuvent pas aboutir : attendre un job dont tous les runs sont
  terminés ; attendre un job dont au moins un run est annulé ; attendre un job
  dont un run est encore dans le pipeline ; attendre un job dont les statuts
  ne sont pas cartographiés ; attendre un nom de job qui n'existe pas.
- **Résultat attendu** :
  1. `done`, avec le décompte par statut ;
  2. **échec nommant l'annulation** et renvoyant au journal des jobs, MÊME si
     le job porte par ailleurs des dizaines de runs terminés (un run annulé
     est un fait à remonter, jamais une statistique à moyenner) ;
  3. échec de délai nommant le pipeline ;
  4. échec de délai disant que les statuts sont inattendus et qu'on continue
     d'attendre, ce qui est le point de qualité verrouillé ici : un statut
     inconnu ne devient JAMAIS un succès ;
  5. échec nommant l'absence, avec la piste `jobcount=`.
- Les quatre échecs sont assertés comme ATTENDUS, jamais contournés.
- **Points de vigilance** : les cibles de chaque branche se DÉCOUVRENT sur le
  système (lire les statuts, choisir un job qui porte le cas voulu) plutôt que
  de graver des noms de jobs d'infrastructure, qui n'existeront pas sur une
  autre cible. La signification du statut `Z` n'est pas établie : ne pas
  l'inventer, et n'asserter que le comportement de repli.

### 10. Les refus d'ouverture de session se distinguent des refus applicatifs

- **Étapes** : tenter une ouverture avec un mot de passe faux ; avec un
  mandant inexistant ; vers un numéro de système injoignable.
- **Résultat attendu** : les deux premiers échouent en `RFC_LOGON_FAILURE`,
  le troisième en `RFC_COMMUNICATION_FAILURE`. Aucun mot de passe n'apparaît
  dans le journal.
- **Points de vigilance** : ne pas prétendre séparer « mot de passe faux » de
  « mandant inexistant », le code est le même.

### 11. Plusieurs connexions coexistent, et la fermeture les emporte toutes

- **Étapes** : ouvrir un second alias sur la même cible ; appeler sur chacun ;
  lister les alias ouverts ; fermer le canal en une fois ; vérifier qu'un
  appel sur un alias fermé échoue proprement.
- **Résultat attendu** : les deux alias répondent indépendamment ; la
  fermeture globale ne laisse aucune connexion ; un appel après fermeture
  échoue en nommant `Open Rfc Connection`.
- **Pourquoi** : une connexion RFC orpheline est une session utilisateur
  restée ouverte côté serveur. Le teardown n'est pas de la politesse.

## Points de vigilance pour la génération

- **Opt-in par tag `rfc`** et **saut propre** si `pyrfc` n'est pas importable :
  la suite doit être neutre dans un run complet de `tests/robot/` sur un poste
  sans canal RFC, y compris en CI.
- **Convention #1** : aucun nom de module fonction ni paramètre technique
  brut dans les scénarios. Les modules (`STFC_CONNECTION`, `RFC_READ_TABLE`,
  les BAPIs) et les noms de table vivent dans la couche resource, sous des
  noms métier. Recommandation : un fichier `resources/rfc_keywords.resource`
  dédié, quatrième miroir du vocabulaire métier, plutôt qu'un gonflement de
  `api_keywords.resource` (le RFC a son propre cycle de vie de connexion).
- **Convention #11** : le mot de passe arrive en `Secret:` par la ligne de
  commande, avec une garde qui ne le MESURE jamais (un `Secret` refuse
  `Should Not Be Empty`).
- **Convention #3** : toute assertion d'échec porte sur un code technique ou
  un type de message, jamais sur un texte.
- **Convention #12** : si un scénario révèle une capacité manquante, elle est
  ajoutée dans `SapApiLibrary` (logique pure dans `sapfx_common`), pas
  contournée par un `Evaluate` dans la suite.
- Le scénario 4 a besoin des deux canaux dans le même mandant ; le scénario
  10 ouvre des connexions qui **doivent** échouer, donc rien à fermer, mais
  le teardown reste posé.

## Écarts constatés à la génération

Génération du 2026-08-27, contre la même cible (A4H, `localhost` / `00` /
`001` / `DEVELOPER`). Suite produite : `tests/robot/api/canal_rfc_a4h.robot`,
vocabulaire : `resources/rfc_keywords.resource`. Tous les faits mesurés du
plan ont été re-vérifiés live et confirmés, y compris les deux enseignements
du tableau des refus. Ce qui suit est ce que le plan ne pouvait pas dire.

### Deux défauts de la frontière Robot vers pyrfc, corrigés dans la bibliothèque

Le plan avait exploré le canal en Python direct ; une suite Robot n'y accède
pas par le même chemin, et cela a fait tomber deux scénarios au premier run
live (9/11), tous deux sur des conversions de type, tous deux traités selon la
convention 12.

1. **Une structure construite par une suite n'atteignait pas le serveur.**
   `pyrfc` contrôle le type EXACT d'un paramètre de structure et refuse une
   sous-classe de `dict`, or tout dictionnaire construit dans une suite est un
   `DotDict`. Le scénario 2 était donc impossible à écrire, et le message
   (`dictionary required for structure parameter, received DotDict`) désigne
   le paramètre sans nommer la cause. Corrigé dans `Call Rfc` : les paramètres
   sont ramenés à des types nus, récursivement (`plain_rfc_value` dans
   `sapfx_common.rfc_channel`), avant l'appel.
2. **Un paramètre numérique de BAPI exige un vrai nombre** (`MAX_ROWS`, refusé
   en `'3'`). Ce cas n'a **pas** été corrigé dans la bibliothèque, et c'est
   délibéré : convertir les chaînes qui ressemblent à des nombres corromprait
   les champs caractère numériques du dictionnaire ABAP, où `'0400'` est un
   numéro de liaison et non l'entier 400. La conversion vit donc dans le
   mot-clé métier qui appelle cette BAPI, et la règle est écrite dans la
   documentation de `Call Rfc`.

### Le canal n'avait aucun mot-clé de lecture ni de perception

Le plan annonçait des « keywords métier manquants » (scénarios 3 et 5) en
supposant qu'ils se composeraient au-dessus de l'existant. Ils ne le
pouvaient pas : la bibliothèque n'exposait que `Open Rfc Connection`,
`Call Rfc`, `Call Bapi`, les deux bornes de LUW et `Wait For Background Job`.
Une suite aurait dû construire elle-même les structures `FIELDS`/`OPTIONS` de
`RFC_READ_TABLE`, ou atteindre la logique pure par un `Evaluate`. Cinq
mot-clés ont donc été ajoutés à `SapApiLibrary` (avec leurs tests hors SAP) :
`Get Rfc Channel Status` et `Rfc Channel Should Be Available` (préflight, qui
distingue binding absent et runtime natif absent, deux remèdes distincts),
`Get Rfc Connection Attributes` (l'identité du scénario 1),
`Read Rfc Table` (le scénario 3) et `Rfc Should Fail With Code` (le
scénario 5, la convention 3 appliquée au canal RFC : `Run Keyword And Expect
Error` ne voit que le texte, jamais le code).

### Précisions sur les données du plan

- **L'hôte des attributs de connexion n'est pas l'hôte SAP.** `host` vaut le
  nom du poste CLIENT, pas `vhcala4h` : l'hôte applicatif se lit dans
  `RFC_SYSTEM_INFO` (`RFCHOST`). Une assertion d'identité posée sur `host`
  serait vraie pour de mauvaises raisons, et le resterait en visant un autre
  système depuis le même poste.
- **Aucune volumétrie relevée n'est gravée dans la suite.** Le plan cite 18
  compagnies, 205 produits, 200 runs de job, 2 mandants, 31 champs. La suite
  asserte des RELATIONS (le mandant de connexion figure dans l'annuaire, le
  filtre isole une ligne unique, le plafond de lignes est respecté, les deux
  canaux comptent le même nombre), pour rester vraie sur un autre système
  portant le même modèle de démonstration. La seule égalité chiffrée est celle
  du scénario 4, et elle est calculée des deux côtés dans le même run.
- **La contre-épreuve du champ inexistant est jouée dans le test**, pas
  seulement citée : les noms de champs sont lus SUR la table elle-même puis
  réinjectés en lecture. La bizarrerie `TABLE_WITHOUT_DATA` est donc prouvée
  au lieu d'être crue.
- **`Read Field Names Of The Field Catalog` rend bien 31 champs** et la
  relecture complète passe, comme annoncé.

### Reprise du 2026-08-27 : le scénario 9 passe de deux à cinq branches

Le plan corrigé porte la mesure juste (4719 runs, `F`=4597, `Z`=105, `A`=10,
`S`=7), donc la cible permet d'éprouver TOUTES les issues de l'attente en
lecture seule. La suite a été régénérée sur ce seul scénario ; les dix autres
sont inchangés. Ce que la reprise a appris ou décidé :

- **Les cibles sont découvertes, aucune n'est gravée.** La suite ne cite plus
  aucun nom de job (le `${FINISHED_JOB}` de la première génération a disparu).
  Le journal est lu en entier, classé par job, et chaque branche choisit un
  job qui porte son cas. Vérifié live : les cinq branches retombent sur les
  jobs relevés au plan (`EU_PUT` pour l'annulation, `RDDIMPDP` pour le
  pipeline, `SAP_COLLECTOR_FOR_PERFMONITOR` pour l'inconnu), sans qu'aucun de
  ces noms figure dans un fichier.
- **Branche sans cible : saut, pas silence.** Une branche dont la cible
  n'existe pas sur le système est SAUTÉE avec un message qui nomme le cas
  manquant. Elle ne rougit pas (rien n'est cassé) et n'est pas comptée verte.
  C'est aussi la raison pour laquelle le scénario 9 est rendu par **six tests**
  et non par un seul : Robot ne sait sauter qu'un test entier, donc une seule
  enveloppe aurait obligé à choisir entre perdre les branches déjà éprouvées et
  taire celle qui manque.
- **Le sixième test est la fondation, et il verrouille la mesure fausse.** Il
  lit le journal SANS plafond, vérifie qu'aucun run lu n'échappe au classement,
  puis rejoue la lecture plafonnée à 200 lignes qui avait trompé la première
  exploration. Mesuré live pendant le run : `{'F': 200}` contre
  `{'F': 4597, 'Z': 105, 'S': 7, 'A': 10}`. Le plafond ne tronque pas seulement,
  il fausse la classification, et sans bruit.
- **Trois capacités ajoutées à la bibliothèque** (convention 12, avec leurs
  tests hors SAP) plutôt qu'un `Evaluate` dans une suite :
  `Find Background Job Cases` (le journal rendu comme un catalogue de cas
  d'attente), `Get Background Job Status Model` (ce que la bibliothèque
  cartographie, et donc ce qu'elle ne cartographie pas), et les deux fonctions
  pures qui les portent (`group_job_statuses`, `job_wait_cases` dans
  `sapfx_common.rfc_tables`). Le catalogue distingue `pipeline` et `unmapped`
  là où le verdict range les deux en `waiting` : ce ne sont pas les mêmes
  preuves.
- **`aborted_with_finished` existe pour une seule raison** : la branche
  annulée n'a de valeur que jouée sur un job qui porte AUSSI des runs
  terminés. Le test le vérifie sur les statuts avant d'attendre, sinon il
  constaterait qu'un `A` seul échoue, ce qui ne prouve aucune priorité.
- **Le statut `Z` n'est toujours pas interprété**, et le test l'écrit. Seul le
  comportement de repli est asserté : devant un statut hors carte, l'attente
  continue au lieu de conclure au succès, et son message le signale par `(?)`.
- **Les délais sont des budgets.** Cinq secondes sur les trois branches dont on
  sait qu'elles ne peuvent pas aboutir (pipeline, statut inconnu, job absent),
  soit environ six secondes chacune en pratique. Les deux autres ne patientent
  pas du tout : mesuré 0,02 s pour la conclusion sur un job terminé et 0,03 s
  pour l'échec sur annulation, ce qui prouve au passage qu'un `A` court-circuite
  l'attente au lieu d'épuiser le budget.
- **Une variable de vocabulaire est morte et a été retirée** : le nom de la
  table du journal des jobs ne figure plus dans la couche resource, la
  bibliothèque étant seule à l'adresser désormais.

### Contrainte d'outillage de cette génération

La vérification live n'est **pas** passée par rf-mcp : le serveur de la
session tourne sous Python 3.14, qui n'a pas `pyrfc` (aucune roue précompilée
au-delà de 3.12). Chaque étape a été exercée contre la cible réelle par un
venv dédié en 3.12.10 (`pyrfc==3.3.1`, SAPFX en editable), d'abord en sondes
Python, puis par la suite elle-même. Les deux branches du saut ont été
éprouvées : 11 réussis en 3.12, 11 sautés et code de sortie 0 en 3.14, avec un
message qui nomme la cause et le remède.
