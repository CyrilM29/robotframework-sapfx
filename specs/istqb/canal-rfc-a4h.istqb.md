# Plan de test ISTQB : Canal RFC / BAPI sur ABAP Platform trial (A4H)

> Source unique : `specs/canal-rfc-a4h.md` (plan sap-planner, exploration live
> du 2026-08-27 contre une ABAP Platform trial en conteneur, cinq passes de
> sonde ; toutes les valeurs et tous les codes d'erreur cités ici sont mesurés
> sur ce système, aucun n'est supposé). Mémoire QA partagée (`qa-brain`) non
> exploitable au moment de la rédaction : index annoncé `green`, mais le
> moteur d'embeddings n'a pas répondu (voir section 6).
> Document de conception de test (ISTQB / ISO 29119-3) : lisible par un
> humain, rejouable par une IA via le bloc `replay` de chaque cas de test,
> indépendant du framework d'exécution.

- **Identifiant** : TP-canal-rfc-a4h
- **Canal** : API, dans sa variante RFC / BAPI (`SapApiLibrary` au-dessus de
  `pyrfc`) : le canal sans écran ET sans HTTP. Un seul cas de test (TC-04)
  croise ponctuellement le canal OData du même système, ce qui rend la
  campagne mixte pour ce cas précis.
- **Système / URL** : ABAP Platform trial en conteneur Docker, `sysId` A4H,
  release 754, kernel 777, base HDB, hôte applicatif `vhcala4h`
  (172.17.0.2), joint en `ashost=localhost`, `sysnr=00`, mandant `001`,
  utilisateur `DEVELOPER`, langue `EN` (observé le 2026-08-27).
- **Références** : `specs/canal-rfc-a4h.md` (plan métier, source de tous les
  chiffres) ; `packaging/install-rfc.ps1` (provisionnement du runtime NW RFC,
  cité par le plan) ; implémentation de référence en cours de génération sous
  `tests/robot/api/canal_rfc_a4h.robot`, avec sa couche métier
  `resources/rfc_keywords.resource` (le vocabulaire exact de cette couche
  n'est pas connu de ce document et n'y est donc jamais cité).

## 1. Objectif et périmètre

- **Objectif** : établir une cartographie vérifiable du canal RFC d'une cible
  ABAP, c'est-à-dire prouver que le canal s'ouvre, qu'il parle au système
  qu'on croit, qu'il lit des tables de façon bornée et filtrée, qu'il appelle
  des BAPIs en les jugeant sur le type de leurs messages, et surtout qu'il
  **classe ses refus par code technique** plutôt que par texte. C'est une
  campagne de reconnaissance et de non-régression du canal, pas une recette
  fonctionnelle d'un processus métier.
- **Éléments à tester** : ouverture et fermeture de connexion (mono et
  multi-alias), attributs de connexion, modules d'information et de sonde de
  vie, lecture générique de table (filtre, plafond de lignes, résultat vide,
  garde de longueur de clause), comptage croisé avec le canal OData, appels
  BAPI de lecture et jugement par type de message, inventaire des BAPIs,
  attente d'un job de fond, classification des refus (ouverture de session,
  communication, erreurs applicatives, erreurs de paramétrage, alias fermé).
- **Hors périmètre** :
  - **toute écriture** : la campagne est en LECTURE SEULE, la LUW n'est
    ouverte que pour prouver qu'on sait la refermer (rollback) ;
  - le provisionnement du runtime NW RFC et l'installation de `pyrfc`, qui
    sont des préconditions d'environnement, pas des cas de test ;
  - la branche « job annulé » de l'attente de job de fond : la cible observée
    ne porte que des runs terminés, et la provoquer supposerait d'écrire
    (voir « À compléter ») ;
  - la recette du canal OData lui-même, dont seul un comptage est emprunté
    au TC-04.

## 2. Préconditions et données de test

### Préconditions d'environnement

1. **Interpréteur Python 3.10 à 3.12.** `pyrfc` n'a aucune roue précompilée
   au-delà de 3.12, et toutes ses versions PyPI sont `yanked` depuis
   l'archivage du projet par SAP : la version s'épingle (`pyrfc==3.3.1`) et le
   choix d'interpréteur se fait à la création du venv, jamais après. Le poste
   d'exploration utilisait un venv dédié en 3.12.10.
2. **Runtime NW RFC présent.** Mesuré sur le poste d'exploration : le
   composant « SAP NWRFC x64 Shared » de SAP GUI for Windows 8.00 dépose
   `sapnwrfc.dll` et les `icu*50` dans `System32`, donc le SDK sous licence
   n'a pas été nécessaire. Sur un poste ou un runner de CI sans SAP GUI, le
   SDK redevient le prérequis (`packaging/install-rfc.ps1`).
3. **Identifiants par la ligne de commande** : aucun mot de passe committé,
   le secret est passé en variable typée `Secret` et n'est jamais mesuré ni
   journalisé.
4. **Exécution optionnelle et neutre par défaut.** Sur un poste sans `pyrfc`,
   la campagne se saute au lieu d'échouer : le canal RFC est optionnel dans ce
   dépôt, et une campagne qui rougit là où rien n'est cassé finit désactivée.
5. **Cible joignable** en `ashost=localhost`, `sysnr=00`, mandant `001`, avec
   un utilisateur autorisé aux modules RFC et aux BAPIs de lecture
   (`DEVELOPER` observé).
6. **Pour le seul TC-04** : le canal OData du même système doit répondre dans
   le **même mandant** `001` (le `$count` du service marchand a bien été
   relevé le 2026-08-27, donc la Gateway répondait ce jour-là).

### Identité du système, telle que le canal la rend (relevé 2026-08-27)

| Source | Champ | Valeur relevée |
|---|---|---|
| attributs de connexion | `sysId` / `client` / `user` | `A4H` / `001` / `DEVELOPER` |
| attributs de connexion | `partnerRel` / `kernelRel` | `754` / `777` |
| attributs de connexion | `rfcRole` / `type` | `C` / `E` |
| module d'information système | `RFCPROTO` / `RFCSAPRL` / `RFCKERNRL` | `011` / `754` / `777` |
| module d'information système | `RFCHOST` / `RFCIPADDR` | `vhcala4h` / `172.17.0.2` |
| module d'information système | `RFCDBSYS` / `RFCOPSYS` | `HDB` / `Linux` |
| module d'écho de connexion | `RESPTEXT` | contient `Sysid: A4H` et `Logon_Data: 001/DEVELOPER/E` |

La sonde de vie la plus simple répond par un **dictionnaire vide** : c'est un
succès, il n'y a rien à y lire, seule l'absence d'exception fait foi.

### Volumétries et lectures relevées (lecture générique de table)

| Table | Critère | Résultat mesuré |
|---|---|---|
| `T000` | aucun | 2 mandants : `000` et `001`, tous deux « SAP SE / Walldorf » |
| `SCARR` | aucun | 18 compagnies |
| `SCARR` | `CARRID EQ 'LH'` | `Lufthansa`, devise `EUR` |
| `SPFLI` | `CARRID EQ 'LH'`, plafond 3 lignes | `0400` FRANKFURT vers NEW YORK, `0401` retour, `0402` |
| `SNWD_PD` | aucun | 205 produits |
| `DD02L` | `TABNAME EQ 'SCARR'` | `TABCLASS = TRANSP` |
| `DD03L` | `TABNAME EQ 'DD03L'` | 31 champs réels, largeurs cumulées 310 caractères |
| `TBTCO` | plafond 200 lignes | 200 runs de job, statut `F` pour la totalité |
| `SCARR` | `CARRID EQ 'ZZ'` | liste vide, sans erreur |
| `SFLIGHT` | `CARRID EQ 'LH' AND CONNID EQ '0400'` | `PRICE` rendu `"666.00"`, devise `EUR` |

Croisement inter-canal : `SNWD_PD` comptée par RFC vaut **205**, et le
`$count` de l'ensemble d'entités « produits » du service marchand OData du
même système vaut **205** aussi.

### Observations BAPI

| Appel | Observation |
|---|---|
| détail d'un utilisateur existant (`DEVELOPER`) | succès, bloc de données de connexion renseigné |
| détail d'un utilisateur inconnu | message de retour de type `E`, id `01`, numéro `124` |
| liste de vols d'une compagnie (`LH`) | message de retour de type `S`, liste de vols peuplée, `PRICE` en `Decimal` |
| inventaire des BAPIs du système | rend une liste d'objets métier et de méthodes |
| validation et annulation de transaction | retour vide, donc succès |

**Différence de typage à retenir** : le même prix revient en chaîne
`"666.00"` par la lecture générique de table (qui rend du texte délimité) et
en `Decimal('666.0000')` par la BAPI (qui rend le type ABAP). Une assertion
numérique doit convertir, jamais comparer les deux représentations.

### Jobs de fond

`TBTCO` porte 200 runs, tous au statut `F`. Le job `RSUPG_RUN_TASK_ONCE`
compte 21 runs terminés : l'attente rend un état « terminé » immédiatement.
Un nom de job absent produit un échec qui nomme la cause et rappelle le
paramètre `jobcount=` ainsi que la transaction SM37.

### Refus, classés par code technique (aucun ne se reconnaît à son texte)

| Cas provoqué | Classe | Code technique |
|---|---|---|
| Mot de passe faux | `LogonError` | `RFC_LOGON_FAILURE` |
| Mandant inexistant | `LogonError` | `RFC_LOGON_FAILURE` |
| Hôte ou numéro de système injoignable | `CommunicationError` | `RFC_COMMUNICATION_FAILURE` |
| Table inexistante | `ABAPApplicationError` | `TABLE_NOT_AVAILABLE` |
| Champ inexistant | `ABAPApplicationError` | `TABLE_WITHOUT_DATA` |
| Module fonction inexistant | `ABAPApplicationError` | `FU_NOT_FOUND` |
| Paramètre inconnu du module | `ExternalRuntimeError` | `RFC_INVALID_PARAMETER` |
| Alias jamais ouvert, ou déjà fermé | `RuntimeError` de la bibliothèque | message nommant l'ouverture de connexion RFC |

**Deux faits contre-intuitifs, que la documentation doit rendre lisibles**
(ils sont la raison d'être du tableau ci-dessus) :

- **Un champ inexistant sort en `TABLE_WITHOUT_DATA`**, c'est-à-dire un code
  qui accuse la **table** d'être sans données alors qu'elle est pleine et que
  le fautif est un **nom de champ**. Autrement dit, le système répond « cette
  table n'a pas de données » là où la vraie cause est une faute de frappe dans
  la liste des colonnes demandées. Vérifié trois fois le 2026-08-27 : un champ
  inventé sur `SCARR` (18 lignes bien présentes), le seul champ `AUTHCLASS`
  demandé sur `DD03L`, et une liste de 19 champs dont 2 n'existent pas sur
  cette release. Contre-épreuve faite : les 31 champs réels de `DD03L` passent
  tous. C'est le piège de diagnostic du canal, celui qui envoie chercher un
  problème de données là où il y a une erreur de saisie.
- **Un mot de passe faux et un mandant inexistant produisent le MÊME code**,
  `RFC_LOGON_FAILURE`. Seul le texte, localisé, les sépare. Aucun test ne peut
  donc prétendre distinguer ces deux causes : il constate un refus d'ouverture
  de session, et c'est tout ce qu'il peut affirmer honnêtement. Un test qui
  prétendrait le contraire serait vert pour une mauvaise raison le jour où les
  deux cas s'échangent.

### Garde de la bibliothèque, avant tout appel réseau

Une clause de sélection de plus de 72 caractères est refusée **côté client**,
avec le remède nommé (découper en clauses `AND`). Mesuré : une clause de
104 caractères ne part jamais sur le réseau. C'est la limite propre du module
de lecture générique, dont le dépassement produirait sinon un comportement
silencieusement tronqué.

## 3. Critères d'entrée / de sortie

- **Entrée** :
  - conteneur cible démarré, licencié et joignable en `ashost=localhost`,
    `sysnr=00` ;
  - venv en Python 3.10 à 3.12 avec `pyrfc` épinglé installé, et runtime NW
    RFC chargeable (issu du client SAP GUI ou du SDK) ;
  - identifiants du mandant `001` fournis par la ligne de commande, le mot de
    passe en variable typée `Secret` ;
  - pour TC-04 seulement : canal OData joignable sur le **même** mandant ;
  - si `pyrfc` n'est pas importable, la campagne est **sautée** et non
    exécutée : c'est un critère d'entrée non rempli, pas un échec.
- **Sortie** :
  - les onze cas de test exécutés, ou explicitement sautés avec leur raison ;
  - toutes les connexions ouvertes refermées, y compris après échec, et TC-11
    ayant constaté qu'aucune connexion ne survit à la fermeture globale (une
    connexion RFC orpheline est une session utilisateur restée ouverte côté
    serveur) ;
  - aucune écriture dans le système, la LUW étant refermée par annulation ;
  - aucun mot de passe présent dans les journaux d'exécution ;
  - chaque écart entre valeur attendue et valeur observée documenté et
    qualifié : dérive de volumétrie d'instance (attendue et bénigne) ou
    changement de comportement du canal (à instruire).
  - **À compléter** : le seuil d'acceptation formel (taux de réussite exigé,
    traitement des cas sautés dans le verdict de campagne) n'est fixé par
    aucune source.

## 4. Cas de test

### TC-01 : Le canal s'ouvre et prouve à quel système il parle

- **Priorité** : Haute. Un canal ouvert ne dit pas encore vers quoi il parle.
  Une campagne qui ne prouve pas l'identité de sa cible peut être verte contre
  le mauvais système, ce que ce dépôt a déjà vécu côté web avec un nom d'hôte
  partagé entre deux conteneurs. Tous les autres cas de test s'appuient sur
  cette connexion.

| # | Action | Données | Résultat attendu |
|---|--------|---------|------------------|
| 1 | Ouvrir le canal RFC sur la cible, sous un alias principal | hôte `localhost`, numéro de système `00`, mandant `001`, utilisateur `DEVELOPER`, langue `EN`, mot de passe en variable `Secret` | La connexion s'ouvre sans exception ; le mot de passe n'apparaît nulle part dans le journal |
| 2 | Lire les attributs de connexion rendus par le canal | | `sysId` = `A4H`, `client` = `001`, `user` = `DEVELOPER`, `partnerRel` = `754`, `kernelRel` = `777`, `rfcRole` = `C`, `type` = `E` |
| 3 | Appeler le module d'information système | | `RFCPROTO` = `011`, `RFCSAPRL` = `754`, `RFCKERNRL` = `777`, `RFCHOST` = `vhcala4h`, `RFCIPADDR` = `172.17.0.2`, `RFCDBSYS` = `HDB`, `RFCOPSYS` = `Linux` |
| 4 | Confronter les deux sources d'identité | | Les deux s'accordent sur le `sysId`, la release et le kernel ; le mandant servi est celui demandé (`001`). Aucune assertion ne porte sur un texte localisé |

- **Postconditions** : connexion principale ouverte et réutilisée par les cas
  suivants ; aucune donnée modifiée.

```yaml
test_case: TC-01
title: "Le canal s'ouvre et prouve a quel systeme il parle"
channel: rfc
steps:
  - action: api_call
    target: "ouverture de la connexion RFC, alias principal"
    value: "ashost=localhost, sysnr=00, client=001, user=DEVELOPER, lang=EN"
    expected: "connexion ouverte, aucune exception"
    note: "mot de passe fourni en variable typee Secret par la ligne de commande, jamais journalise"
    hint: {engine: 'rfc', locator: 'connexion directe ashost/sysnr'}
  - action: assert_value
    target: "attribut sysId de la connexion"
    expected: 'A4H'
    hint: {engine: 'rfc', locator: 'connection attributes -> sysId'}
  - action: assert_value
    target: "attribut client de la connexion"
    expected: '001'
    hint: {engine: 'rfc', locator: 'connection attributes -> client'}
  - action: assert_value
    target: "attributs partnerRel et kernelRel de la connexion"
    expected: '754 / 777'
    hint: {engine: 'rfc', locator: 'connection attributes -> partnerRel, kernelRel'}
  - action: api_call
    target: "module d'information systeme"
    expected: "RFCSAPRL=754, RFCKERNRL=777, RFCHOST=vhcala4h, RFCIPADDR=172.17.0.2, RFCDBSYS=HDB, RFCOPSYS=Linux"
    hint: {engine: 'rfc', locator: 'RFC_SYSTEM_INFO'}
  - action: assert_value
    target: "concordance sysId entre attributs de connexion et information systeme"
    expected: 'A4H'
    note: "la release et le kernel sont compares de la meme facon, jamais un texte localise"
```

### TC-02 : Les sondes de vie répondent

- **Priorité** : Moyenne. Ces sondes ne portent aucun enjeu métier, mais elles
  sont le premier diagnostic quand un appel plus riche échoue : elles séparent
  « le canal ne répond plus » de « cet appel-là est en cause ».

| # | Action | Données | Résultat attendu |
|---|--------|---------|------------------|
| 1 | Envoyer la sonde de vie la plus simple sur la connexion ouverte | | L'appel ne lève aucune exception. La réponse est un dictionnaire **vide** : l'absence d'exception fait foi, aucun contenu n'est asserté |
| 2 | Appeler le module d'écho de connexion avec un texte choisi | texte arbitraire fixé par le test (l'attendu est l'égalité de l'écho, pas une valeur relevée) | L'écho rend **exactement** le texte envoyé |
| 3 | Lire le texte de réponse du même appel | | Il porte le `sysId` de la cible (`Sysid: A4H`) et les données de connexion `001/DEVELOPER/E`. Ce sont des jetons techniques, pas un message localisé |
| 4 | Appeler le module d'écho de structure avec une structure remplie | structure d'entrée : **à compléter** (le plan ne relève pas le détail des champs) | La structure est renvoyée et la table associée n'est pas vide |

- **Postconditions** : aucune donnée modifiée, connexion inchangée.

```yaml
test_case: TC-02
title: "Les sondes de vie repondent"
channel: rfc
steps:
  - action: api_call
    target: "sonde de vie du canal"
    expected: "aucune exception ; reponse vide, non assertee comme contenu"
    hint: {engine: 'rfc', locator: 'RFC_PING'}
  - action: api_call
    target: "module d'echo de connexion"
    value: "<texte arbitraire choisi par le test>"
    expected: "l'echo rend exactement le texte envoye"
    hint: {engine: 'rfc', locator: 'STFC_CONNECTION -> REQUTEXT / ECHOTEXT'}
  - action: assert_text
    target: "texte de reponse du module d'echo"
    expected: "contient 'Sysid: A4H' et 'Logon_Data: 001/DEVELOPER/E'"
    note: "jetons techniques stables, pas un message localise"
    hint: {engine: 'rfc', locator: 'STFC_CONNECTION -> RESPTEXT'}
  - action: api_call
    target: "module d'echo de structure"
    value: "<structure d'entree a completer>"
    expected: "structure renvoyee et table associee non vide"
    hint: {engine: 'rfc', locator: 'STFC_STRUCTURE'}
```

### TC-03 : La lecture générique de table est bornée et filtrée

- **Priorité** : Haute. C'est la capacité principale du canal et celle que la
  campagne réutilise partout (comptages, croisement inter-canal, contre-épreuve
  du piège de diagnostic). Une régression ici rend tout le reste illisible.

| # | Action | Données | Résultat attendu |
|---|--------|---------|------------------|
| 1 | Lire la table des mandants, sans critère | `T000` | 2 lignes ; les mandants `000` et `001` sont présents |
| 2 | Lire le catalogue des compagnies aériennes, sans critère | `SCARR` | 18 lignes |
| 3 | Relire le même catalogue avec un filtre sur la compagnie | `SCARR`, critère `CARRID EQ 'LH'` | Une seule compagnie rendue : `Lufthansa`, devise `EUR` |
| 4 | Lire les liaisons de cette compagnie avec un plafond de lignes | `SPFLI`, critère `CARRID EQ 'LH'`, plafond 3 | Exactement 3 lignes : `0400` FRANKFURT vers NEW YORK, `0401` le retour, `0402` |
| 5 | Lire le catalogue avec un filtre qui ne correspond à rien | `SCARR`, critère `CARRID EQ 'ZZ'` | Une liste **vide**, et **pas** une erreur : l'absence de résultat n'est pas un échec |
| 6 | Lire une table du dictionnaire avec un filtre et une projection | `DD02L`, critère `TABNAME EQ 'SCARR'` | La classe de table rendue vaut `TRANSP` |

- **Postconditions** : aucune donnée modifiée ; connexion ouverte.

```yaml
test_case: TC-03
title: "La lecture generique de table est bornee et filtree"
channel: rfc
steps:
  - action: api_call
    target: "lecture de la table des mandants"
    value: 'T000'
    expected: "2 lignes, mandants 000 et 001 presents"
    hint: {engine: 'rfc', locator: 'RFC_READ_TABLE QUERY_TABLE=T000'}
  - action: api_call
    target: "lecture du catalogue des compagnies aeriennes"
    value: 'SCARR'
    expected: '18 lignes'
    hint: {engine: 'rfc', locator: 'RFC_READ_TABLE QUERY_TABLE=SCARR'}
  - action: api_call
    target: "lecture filtree du catalogue des compagnies"
    value: "SCARR, filtre CARRID EQ 'LH'"
    expected: "une ligne : Lufthansa, devise EUR"
    hint: {engine: 'rfc', locator: "RFC_READ_TABLE OPTIONS=CARRID EQ 'LH'"}
  - action: api_call
    target: "lecture bornee des liaisons de la compagnie"
    value: "SPFLI, filtre CARRID EQ 'LH', plafond 3 lignes"
    expected: "exactement 3 lignes : 0400 FRANKFURT->NEW YORK, 0401 retour, 0402"
    hint: {engine: 'rfc', locator: 'RFC_READ_TABLE ROWCOUNT=3'}
  - action: api_call
    target: "lecture avec un filtre sans correspondance"
    value: "SCARR, filtre CARRID EQ 'ZZ'"
    expected: "liste vide, aucune exception"
    hint: {engine: 'rfc', locator: "RFC_READ_TABLE OPTIONS=CARRID EQ 'ZZ'"}
  - action: api_call
    target: "lecture d'une table du dictionnaire"
    value: "DD02L, filtre TABNAME EQ 'SCARR'"
    expected: 'TABCLASS = TRANSP'
    hint: {engine: 'rfc', locator: 'RFC_READ_TABLE QUERY_TABLE=DD02L, FIELDS=TABCLASS'}
```

### TC-04 : Le même fait, deux canaux, un seul verdict

- **Priorité** : Haute. C'est la preuve que la campagne apporte au-delà de
  « le canal répond » : deux protocoles indépendants, une seule réalité. Un
  écart ici signale soit une régression de l'un des deux canaux, soit une
  erreur de périmètre (mandants divergents).

| # | Action | Données | Résultat attendu |
|---|--------|---------|------------------|
| 1 | Compter les produits de la table produits par le canal RFC | `SNWD_PD`, mandant `001` | 205 |
| 2 | Compter l'ensemble d'entités « produits » du service marchand par le canal OData, sur le même système et le même mandant | service marchand OData, mandant `001` | 205 |
| 3 | Confronter les deux comptes | | Égalité stricte des deux valeurs |

- **Postconditions** : aucune donnée modifiée ; les deux canaux restent
  ouverts pour leur teardown respectif.
- **Vigilance d'exécution** : les deux canaux doivent viser le même mandant,
  sans quoi on compare deux populations et on fabrique un écart inexistant.
  Le premier appel OData d'un service jamais sollicité sur un système froid
  peut dépasser le délai par défaut : ce n'est pas une panne de réseau.

```yaml
test_case: TC-04
title: "Le meme fait, deux canaux, un seul verdict"
channel: mixte
steps:
  - action: api_call
    target: "comptage des produits par le canal RFC"
    value: 'SNWD_PD, mandant 001'
    expected: '205'
    hint: {engine: 'rfc', locator: 'RFC_READ_TABLE QUERY_TABLE=SNWD_PD'}
  - action: api_call
    target: "comptage des produits par le canal OData, meme systeme et meme mandant"
    value: 'service marchand, ensemble d entites produits, mandant 001'
    expected: '205'
    hint: {engine: 'odata', locator: '$count de l ensemble d entites produits du service marchand'}
  - action: assert_value
    target: "confrontation des deux comptes"
    expected: "egalite stricte (205 = 205)"
    note: "mandants identiques exiges ; un premier appel OData sur systeme froid peut etre lent sans etre en panne"
```

### TC-05 : Les refus se classent par code, jamais par texte

- **Priorité** : Haute. Ce cas porte le piège de diagnostic du canal (un
  champ inexistant accusant la table d'être sans données). Sans lui, une
  équipe part chercher un problème de données là où il y a une faute de
  frappe, et le temps perdu est réel.

| # | Action | Données | Résultat attendu |
|---|--------|---------|------------------|
| 1 | Demander la lecture d'une table qui n'existe pas | nom de table volontairement absent du dictionnaire | L'appel échoue en `ABAPApplicationError`, code technique `TABLE_NOT_AVAILABLE` |
| 2 | Demander la lecture d'un champ qui n'existe pas, sur une table pleine | `SCARR` (18 lignes réelles), un nom de champ inventé | L'appel échoue en `ABAPApplicationError`, code technique **`TABLE_WITHOUT_DATA`**. Le code accuse la table d'être sans données ; la table est pleine et le fautif est le nom de champ. L'assertion porte sur le code, avec cette bizarrerie assumée et documentée |
| 3 | Répéter avec un seul champ absent sur une table du dictionnaire | `DD03L`, champ `AUTHCLASS` | Même code `TABLE_WITHOUT_DATA` |
| 4 | Répéter avec une liste de 19 champs dont 2 n'existent pas sur cette release | `DD03L`, 19 champs demandés | Même code `TABLE_WITHOUT_DATA` : deux noms fautifs sur dix-neuf suffisent à faire déclarer la table sans données |
| 5 | Contre-épreuve : demander les 31 champs réels de la même table | `DD03L`, critère `TABNAME EQ 'DD03L'`, 31 champs | Succès : les lignes sont rendues, largeurs cumulées 310 caractères. La différence entre 4 et 5 tient au seul nom des champs |
| 6 | Appeler un module fonction qui n'existe pas | nom de module volontairement absent | L'appel échoue en `ABAPApplicationError`, code technique `FU_NOT_FOUND` |
| 7 | Appeler un module existant avec un paramètre qu'il ne connaît pas | paramètre volontairement inconnu | L'appel échoue en `ExternalRuntimeError`, code technique `RFC_INVALID_PARAMETER` |

- **Postconditions** : aucune donnée modifiée ; la connexion reste utilisable
  après chacun de ces refus (aucun n'invalide la session).

```yaml
test_case: TC-05
title: "Les refus se classent par code, jamais par texte"
channel: rfc
steps:
  - action: api_call
    target: "lecture d'une table inexistante"
    value: '<nom de table volontairement absent>'
    expected: 'echec ABAPApplicationError, code TABLE_NOT_AVAILABLE'
    hint: {engine: 'rfc', locator: 'RFC_READ_TABLE QUERY_TABLE=<inexistante>'}
  - action: api_call
    target: "lecture d'un champ inexistant sur une table pleine"
    value: 'SCARR (18 lignes reelles), champ invente'
    expected: 'echec ABAPApplicationError, code TABLE_WITHOUT_DATA'
    note: "contre-intuitif assume : le code accuse la TABLE, le fautif est le NOM DE CHAMP"
    hint: {engine: 'rfc', locator: 'RFC_READ_TABLE FIELDS=<champ invente>'}
  - action: api_call
    target: "lecture d'un champ absent sur une table du dictionnaire"
    value: 'DD03L, champ AUTHCLASS'
    expected: 'echec ABAPApplicationError, code TABLE_WITHOUT_DATA'
    hint: {engine: 'rfc', locator: 'RFC_READ_TABLE QUERY_TABLE=DD03L, FIELDS=AUTHCLASS'}
  - action: api_call
    target: "lecture d'une liste de 19 champs dont 2 absents"
    value: 'DD03L, 19 champs demandes'
    expected: 'echec ABAPApplicationError, code TABLE_WITHOUT_DATA'
    hint: {engine: 'rfc', locator: 'RFC_READ_TABLE FIELDS=<19 noms, 2 fautifs>'}
  - action: api_call
    target: "contre-epreuve : les 31 champs reels de la meme table"
    value: "DD03L, filtre TABNAME EQ 'DD03L', 31 champs"
    expected: 'succes, lignes rendues, largeurs cumulees 310 caracteres'
    hint: {engine: 'rfc', locator: 'RFC_READ_TABLE FIELDS=<31 noms reels>'}
  - action: api_call
    target: "appel d'un module fonction inexistant"
    value: '<nom de module volontairement absent>'
    expected: 'echec ABAPApplicationError, code FU_NOT_FOUND'
    hint: {engine: 'rfc', locator: 'appel de module par nom'}
  - action: api_call
    target: "appel d'un module avec un parametre inconnu"
    value: '<parametre volontairement inconnu>'
    expected: 'echec ExternalRuntimeError, code RFC_INVALID_PARAMETER'
    hint: {engine: 'rfc', locator: 'appel de module avec parametre non declare'}
```

### TC-06 : La garde de clause protège avant le réseau

- **Priorité** : Moyenne. Le dépassement de la limite produirait une lecture
  silencieusement tronquée, ce qui est grave ; mais la garde agit côté client,
  sans dépendre du système, donc le risque de régression est faible et ce cas
  vérifie surtout que le câblage est en place.

| # | Action | Données | Résultat attendu |
|---|--------|---------|------------------|
| 1 | Demander une lecture dont la clause de sélection dépasse la limite du module | clause de 104 caractères | Refus **immédiat** de la bibliothèque, côté client. Le message nomme la limite (72 caractères), la longueur constatée (104) et le remède : découper en plusieurs clauses `AND`. Aucun appel n'atteint le serveur |
| 2 | Contre-épreuve : les clauses courtes du TC-03 | `CARRID EQ 'LH'` et les autres critères du TC-03 | Elles passent la garde et atteignent le serveur normalement |

- **Postconditions** : aucun appel réseau émis à l'étape 1 ; aucune donnée
  modifiée.

```yaml
test_case: TC-06
title: "La garde de clause protege avant le reseau"
channel: rfc
steps:
  - action: api_call
    target: "lecture avec une clause de selection trop longue"
    value: 'clause de 104 caracteres'
    expected: "refus immediat cote client, message nommant la limite 72, la longueur 104 et le decoupage en clauses AND ; aucun appel reseau"
    hint: {engine: 'rfc', locator: 'garde de longueur de clause OPTIONS (cote client)'}
  - action: api_call
    target: "contre-epreuve : clause courte du TC-03"
    value: "CARRID EQ 'LH'"
    expected: "la clause passe la garde et la lecture aboutit"
    hint: {engine: 'rfc', locator: "RFC_READ_TABLE OPTIONS=CARRID EQ 'LH'"}
```

### TC-07 : Une BAPI est jugée sur le type de ses messages

- **Priorité** : Haute. C'est la règle de jugement du canal : la décision se
  prend sur le TYPE du message (`E`, `A`, `X`), jamais sur son libellé, qui
  est localisé. Une suite qui asserterait le texte serait rouge au premier
  changement de langue de connexion.

| # | Action | Données | Résultat attendu |
|---|--------|---------|------------------|
| 1 | Appeler la BAPI de détail d'utilisateur sur un utilisateur existant | `DEVELOPER` | Succès : le bloc de données de connexion est renseigné, aucun message bloquant (type `E`, `A` ou `X`) dans le retour |
| 2 | Appeler la même BAPI sur un utilisateur inconnu | identifiant volontairement absent du système (valeur arbitraire, non relevée par le plan) | L'appel **échoue**. Le message bloquant est identifié par son type `E`, son id `01` et son numéro `124`, jamais par son libellé |
| 3 | Appeler la BAPI de liste de vols d'une compagnie | `LH` | Retour de type `S` ; la liste de vols est peuplée ; le prix est rendu en `Decimal` |
| 4 | Refermer la LUW par annulation | | Le retour est vide, donc succès. Aucune donnée n'a été écrite |

- **Postconditions** : LUW refermée par annulation ; aucune donnée modifiée.
- **Vigilance** : le même prix vaut `"666.00"` en chaîne par la lecture
  générique de table et `Decimal('666.0000')` par la BAPI. Toute comparaison
  entre les deux voies convertit d'abord ; comparer les représentations
  échouerait sur une différence de format, pas sur une différence de valeur.

```yaml
test_case: TC-07
title: "Une BAPI est jugee sur le type de ses messages"
channel: rfc
steps:
  - action: api_call
    target: "BAPI de detail d'utilisateur, sur un utilisateur existant"
    value: 'DEVELOPER'
    expected: "succes, bloc de donnees de connexion renseigne, aucun message de type E/A/X"
    hint: {engine: 'rfc', locator: 'BAPI_USER_GET_DETAIL'}
  - action: api_call
    target: "BAPI de detail d'utilisateur, sur un utilisateur inconnu"
    value: '<identifiant volontairement absent>'
    expected: "echec ; message bloquant de type E, id 01, numero 124"
    note: "assertion sur type + id + numero, jamais sur le libelle localise"
    hint: {engine: 'rfc', locator: 'BAPI_USER_GET_DETAIL -> RETURN'}
  - action: api_call
    target: "BAPI de liste de vols d'une compagnie"
    value: 'LH'
    expected: "retour de type S, liste de vols peuplee, PRICE en Decimal"
    hint: {engine: 'rfc', locator: 'BAPI_FLIGHT_GETLIST'}
  - action: api_call
    target: "fermeture de la LUW par annulation"
    expected: 'retour vide, donc succes ; aucune ecriture'
    hint: {engine: 'rfc', locator: 'BAPI_TRANSACTION_ROLLBACK'}
```

### TC-08 : L'inventaire des BAPIs est la perception du canal

- **Priorité** : Basse. Le cas ne fige aucun catalogue (il varie d'un système
  à l'autre) et ne protège aucune règle métier : il constate que le canal sait
  se décrire, ce qui sert au diagnostic et à l'exploration, pas à la
  régression.

| # | Action | Données | Résultat attendu |
|---|--------|---------|------------------|
| 1 | Demander au système la liste de ses BAPIs | | Une liste **non vide** est rendue |
| 2 | Contrôler la forme des entrées | | Chaque entrée porte un type d'objet métier, un nom métier et un nom ABAP |
| 3 | Constater le volume | plancher de volume : **à compléter** (aucun nombre relevé) | Le volume est journalisé et constaté, jamais figé en constante : le catalogue varie d'un système à l'autre |

- **Postconditions** : aucune donnée modifiée.

```yaml
test_case: TC-08
title: "L'inventaire des BAPIs est la perception du canal"
channel: rfc
steps:
  - action: api_call
    target: "inventaire des BAPIs du systeme"
    expected: 'liste non vide'
    hint: {engine: 'rfc', locator: 'BAPI_MONITOR_GETLIST -> BAPILIST'}
  - action: assert_present
    target: "forme des entrees de l'inventaire"
    expected: "chaque entree porte type d'objet, nom metier et nom ABAP"
  - action: assert_value
    target: "volume de l'inventaire"
    expected: '<plancher a completer>'
    note: "le catalogue varie d un systeme a l autre : constater et journaliser, ne pas figer"
```

### TC-09 : L'attente d'un job de fond distingue le terminé de l'absent

- **Priorité** : Moyenne. La capacité est utile aux campagnes qui déclenchent
  des traitements, mais sur cette cible en lecture seule elle n'exerce que
  deux branches sur trois (voir risques) : elle ne peut pas prouver la
  détection d'un job annulé.

| # | Action | Données | Résultat attendu |
|---|--------|---------|------------------|
| 1 | Lire la table des runs de job avec un plafond de lignes | `TBTCO`, plafond 200 | 200 runs rendus, tous au statut `F` |
| 2 | Attendre un job dont des runs sont terminés | `RSUPG_RUN_TASK_ONCE` | L'attente rend immédiatement un état « terminé », avec le décompte par statut : 21 runs terminés |
| 3 | Attendre un nom de job qui n'existe pas, avec un budget d'attente court | nom de job volontairement absent ; budget d'attente : **à compléter** (non relevé) | L'appel **échoue**, et c'est le résultat attendu du cas, pas un incident : le message nomme la cause (aucun job trouvé sous ce nom) et rappelle le paramètre `jobcount=` ainsi que la transaction SM37 |

- **Postconditions** : aucune donnée modifiée ; aucun job déclenché (la
  campagne se contente d'observer des runs existants).

```yaml
test_case: TC-09
title: "L'attente d'un job de fond distingue le termine de l'absent"
channel: rfc
steps:
  - action: api_call
    target: "lecture des runs de job"
    value: 'TBTCO, plafond 200 lignes'
    expected: '200 runs, statut F pour la totalite'
    hint: {engine: 'rfc', locator: 'RFC_READ_TABLE QUERY_TABLE=TBTCO, ROWCOUNT=200'}
  - action: api_call
    target: "attente d'un job dont des runs sont termines"
    value: 'RSUPG_RUN_TASK_ONCE'
    expected: "etat termine rendu immediatement, decompte par statut : 21 runs termines"
    hint: {engine: 'rfc', locator: 'attente de job via TBTCO'}
  - action: api_call
    target: "attente d'un nom de job inexistant, budget d'attente court"
    value: '<nom de job absent>, budget a completer'
    expected: "echec ATTENDU ; le message nomme la cause et rappelle jobcount= et SM37"
    note: "echec asserte comme resultat du cas, jamais contourne ; le budget est une borne, pas une temporisation"
    hint: {engine: 'rfc', locator: 'attente de job via TBTCO'}
```

### TC-10 : Les refus d'ouverture de session se distinguent des refus applicatifs

- **Priorité** : Haute, pour deux raisons cumulées : c'est le cas où un mot de
  passe pourrait fuiter dans un journal, et c'est celui qui pose la limite
  honnête du canal (deux causes distinctes rendent le même code).

| # | Action | Données | Résultat attendu |
|---|--------|---------|------------------|
| 1 | Tenter une ouverture avec un mot de passe faux | mot de passe volontairement erroné (valeur arbitraire, jamais committée) | L'ouverture échoue en `LogonError`, code technique `RFC_LOGON_FAILURE`. Aucun mot de passe n'apparaît dans le journal |
| 2 | Tenter une ouverture avec un mandant inexistant | un mandant hors des deux relevés dans `T000` (`000` et `001`) | L'ouverture échoue en `LogonError`, **même** code `RFC_LOGON_FAILURE`. Le cas constate un refus d'ouverture de session ; il **ne prétend pas** identifier laquelle des deux causes est en jeu, puisque seul le texte, localisé, les sépare |
| 3 | Tenter une ouverture vers un numéro de système injoignable | un numéro de système où rien n'écoute (la cible sert `sysnr=00`) | L'ouverture échoue en `CommunicationError`, code technique `RFC_COMMUNICATION_FAILURE`. C'est la distinction utile : refus par le système contre absence de système |

- **Postconditions** : aucune connexion ouverte à fermer (les trois tentatives
  échouent par construction) ; le teardown reste néanmoins posé, un échec
  partiel pouvant laisser un alias derrière lui.

```yaml
test_case: TC-10
title: "Les refus d'ouverture de session se distinguent des refus applicatifs"
channel: rfc
steps:
  - action: api_call
    target: "ouverture avec un mot de passe faux"
    value: 'client=001, user=DEVELOPER, mot de passe volontairement errone'
    expected: 'echec LogonError, code RFC_LOGON_FAILURE'
    note: "aucun mot de passe journalise ; valeur jamais committee"
    hint: {engine: 'rfc', locator: 'ouverture de connexion RFC'}
  - action: api_call
    target: "ouverture avec un mandant inexistant"
    value: '<mandant hors 000 et 001>'
    expected: 'echec LogonError, code RFC_LOGON_FAILURE (le MEME code)'
    note: "le cas constate un refus d ouverture ; il ne peut pas distinguer mot de passe faux et mandant inexistant"
    hint: {engine: 'rfc', locator: 'ouverture de connexion RFC'}
  - action: api_call
    target: "ouverture vers un numero de systeme injoignable"
    value: '<sysnr ou rien n ecoute>'
    expected: 'echec CommunicationError, code RFC_COMMUNICATION_FAILURE'
    hint: {engine: 'rfc', locator: 'ouverture de connexion RFC'}
```

### TC-11 : Plusieurs connexions coexistent, et la fermeture les emporte toutes

- **Priorité** : Haute. Une connexion RFC orpheline est une session
  utilisateur restée ouverte côté serveur : le teardown n'est pas de la
  politesse, c'est une contrainte d'exploitation sur un système partagé.

| # | Action | Données | Résultat attendu |
|---|--------|---------|------------------|
| 1 | Ouvrir un second alias sur la même cible | mêmes paramètres de connexion que TC-01, alias distinct | Le second alias s'ouvre sans exception |
| 2 | Émettre un appel sur chacun des deux alias | sonde de vie ou lecture bornée | Chaque alias répond indépendamment de l'autre |
| 3 | Lister les alias ouverts | | Les deux alias sont présents dans l'inventaire ; aucun identifiant ni mot de passe n'y figure |
| 4 | Fermer le canal en une fois | | Aucune connexion ne subsiste après la fermeture globale |
| 5 | Émettre un appel sur un alias fermé | l'un des deux alias fermés à l'étape 4 | L'appel échoue proprement : `RuntimeError` de la bibliothèque, message nommant l'ouverture de connexion RFC (la remédiation, pas une trace technique) |

- **Postconditions** : plus aucune connexion RFC ouverte, donc plus aucune
  session utilisateur laissée derrière côté serveur ; aucune donnée modifiée.

```yaml
test_case: TC-11
title: "Plusieurs connexions coexistent, et la fermeture les emporte toutes"
channel: rfc
steps:
  - action: api_call
    target: "ouverture d'un second alias sur la meme cible"
    value: 'ashost=localhost, sysnr=00, client=001, user=DEVELOPER, alias distinct'
    expected: 'second alias ouvert, aucune exception'
    hint: {engine: 'rfc', locator: 'ouverture de connexion RFC'}
  - action: api_call
    target: "appel sur le premier alias"
    expected: 'reponse independante'
    hint: {engine: 'rfc', locator: 'RFC_PING sur alias 1'}
  - action: api_call
    target: "appel sur le second alias"
    expected: 'reponse independante'
    hint: {engine: 'rfc', locator: 'RFC_PING sur alias 2'}
  - action: assert_present
    target: "inventaire des alias ouverts"
    expected: 'les deux alias presents, aucun identifiant ni mot de passe expose'
  - action: api_call
    target: "fermeture globale du canal"
    expected: 'aucune connexion restante'
    hint: {engine: 'rfc', locator: 'fermeture de toutes les connexions du namespace'}
  - action: api_call
    target: "appel sur un alias ferme"
    expected: "echec RuntimeError de la bibliotheque, message nommant l'ouverture de connexion RFC"
    hint: {engine: 'rfc', locator: 'appel sur alias inexistant ou ferme'}
```

## 5. Traçabilité

| Cas de test | Scénario source (`specs/canal-rfc-a4h.md`) | Données observées mobilisées | Suite exécutable |
|---|---|---|---|
| TC-01 | 1. Le canal s'ouvre et prouve à quel système il parle | Table « Identité du système » | `tests/robot/api/canal_rfc_a4h.robot` (en cours de génération) |
| TC-02 | 2. Les sondes de vie répondent | Réponse vide de la sonde ; jetons `Sysid: A4H` et `Logon_Data: 001/DEVELOPER/E` | idem |
| TC-03 | 3. La lecture générique de table est bornée et filtrée | Table « Volumétries et lectures relevées » | idem |
| TC-04 | 4. Le même fait, deux canaux, un seul verdict | 205 = 205 (RFC et OData, mandant `001`) | idem, avec le canal OData du même système |
| TC-05 | 5. Les refus se classent par code, jamais par texte | Table « Refus, classés par code technique » ; contre-épreuve des 31 champs de `DD03L` | idem |
| TC-06 | 6. La garde de clause protège avant le réseau | Clause de 104 caractères refusée côté client, limite 72 | idem |
| TC-07 | 7. Une BAPI est jugée sur le type de ses messages | Table « Observations BAPI » ; type `E` id `01` numéro `124` ; typage `Decimal` contre chaîne | idem |
| TC-08 | 8. L'inventaire des BAPIs est la perception du canal | Inventaire des BAPIs rendu non vide | idem |
| TC-09 | 9. L'attente d'un job de fond distingue fini, absent et annulé | `TBTCO` 200 runs statut `F` ; 21 runs terminés du job de tâche unique | idem, branche « annulé » non couverte |
| TC-10 | 10. Les refus d'ouverture de session se distinguent des refus applicatifs | `RFC_LOGON_FAILURE` (deux causes) ; `RFC_COMMUNICATION_FAILURE` | idem |
| TC-11 | 11. Plusieurs connexions coexistent, et la fermeture les emporte toutes | Refus nommant l'ouverture de connexion sur alias fermé | idem |

Écarts de traçabilité connus à la rédaction :

- **Suite non encore vérifiée** : `tests/robot/api/canal_rfc_a4h.robot` et sa
  couche `resources/rfc_keywords.resource` sont générés en parallèle de ce
  document. La correspondance cas de test / test exécutable est donc annoncée,
  pas constatée ; le vocabulaire exact de la couche métier n'est pas cité ici.
- **Couverture partielle du scénario 9** : son titre annonce trois états
  (fini, absent, annulé) ; la cible observée ne permet d'en éprouver que deux.
- **Capacités signalées manquantes par le plan** : lecture et comptage de
  table par RFC (scénario 3), et une assertion « cet appel RFC échoue avec le
  code technique X » (scénario 5). Si elles sont créées, elles appartiennent à
  la bibliothèque et non à un contournement local dans la suite.
- **Aucun cas de test ne couvre l'écriture** : c'est un choix de posture
  (lecture seule), pas un oubli, mais le canal RFC en écriture reste donc non
  documenté par ce plan.

## 6. Risques et points de vigilance

- **Pérennité de la dépendance `pyrfc` (risque principal, hors de notre
  contrôle)** : SAP a archivé le projet le 2026-05-28, toutes ses versions
  PyPI sont `yanked` (pip ne les choisit donc plus seul, d'où l'épinglage
  exact) et les roues Windows s'arrêtent à Python 3.12. Conséquences directes
  sur cette campagne : le choix d'interpréteur se fait à la création du venv
  et pas après, et une montée de version de Python sur le poste ou le runner
  peut retirer le canal du jour au lendemain. C'est ce qui justifie que la
  campagne soit optionnelle et se saute proprement.
- **Dépendance d'environnement asymétrique poste / CI** : sur le poste
  d'exploration, le runtime NW RFC était déjà là, déposé par le composant
  « SAP NWRFC x64 Shared » de SAP GUI for Windows 8.00, donc aucun SDK n'a été
  nécessaire. Sur un runner de CI sans SAP GUI, le SDK NW RFC sous licence SAP
  redevient un prérequis (non redistribuable, obtention par compte S-user) :
  la même campagne n'a donc pas le même coût d'installation selon l'endroit où
  elle tourne. À consigner dans la fiche d'environnement de la campagne.
- **Une campagne qui rougit sans raison finit désactivée** : sur un poste sans
  canal RFC, l'absence d'exécution doit se traduire par un saut explicite, pas
  par un échec. C'est un risque de crédibilité de la suite, pas un risque
  technique.
- **Le piège de diagnostic `TABLE_WITHOUT_DATA`** : le code accuse la table
  d'être sans données alors que le fautif est un nom de champ. Toute analyse
  d'un échec de lecture commence donc par relire la liste des champs demandés,
  avant de soupçonner les données. Le TC-05 contient exprès sa contre-épreuve
  (31 champs réels qui passent) pour rendre la démonstration lisible.
- **Deux causes, un seul code** : mot de passe faux et mandant inexistant
  rendent tous deux `RFC_LOGON_FAILURE`. Aucun test ne doit prétendre les
  distinguer, et aucune analyse d'incident ne doit conclure « mot de passe
  faux » sur la seule foi du code.
- **Les volumétries sont des invariants d'instance, pas des règles métier** :
  2 mandants, 18 compagnies, 205 produits, 200 runs, 21 runs terminés,
  31 champs et 310 caractères sont des mesures du 2026-08-27 sur cette cible.
  Une copie de mandant, un rechargement de données de démonstration ou une
  autre release les feraient dériver sans qu'aucun défaut n'existe. Pour une
  campagne rejouée dans la durée, privilégier les assertions relatives
  (strictement positif, égalité entre deux mesures du même run) partout où la
  valeur exacte n'est pas le sujet ; le TC-04 est l'exemple type de la bonne
  forme, puisqu'il compare deux mesures entre elles.
- **Typage : chaîne contre `Decimal`** : le même prix vaut `"666.00"` par la
  lecture générique de table et `Decimal('666.0000')` par la BAPI. Convertir
  avant de comparer, toujours.
- **Limite de 72 caractères des clauses de sélection** : au-delà, le
  comportement serait silencieusement tronqué. La garde côté client existe
  pour cela et doit rester active ; découper en clauses `AND`.
- **Croisement inter-canal (TC-04)** : mandants divergents entre RFC et OData
  fabriquent un écart inexistant. Et le premier appel OData d'un service
  jamais sollicité sur un système froid peut dépasser le délai par défaut :
  rejouer avant de conclure à une panne.
- **Connexion orpheline = session serveur ouverte** : le teardown ferme les
  alias même après échec. Le TC-10 ouvre trois connexions qui doivent échouer,
  donc en principe rien à fermer, mais le teardown reste posé.
- **Secret jamais mesuré** : le mot de passe arrive en variable typée `Secret`
  par la ligne de commande. Une garde qui voudrait vérifier qu'il n'est pas
  vide échouerait sur le type lui-même : contrôler la présence de la variable,
  jamais son contenu.
- **Mémoire QA partagée indisponible à la rédaction** : le serveur `qa-brain`
  a répondu à l'appel d'état (index annoncé `green`, 930 passages), mais ses
  deux recherches ont échoué faute de moteur d'embeddings joignable. Aucun
  enseignement d'incident antérieur n'a donc pu être versé à cette section :
  elle est intégralement dérivée du plan et du contexte fourni. À reprendre
  quand le service répond.

## À compléter (questions ouvertes)

1. **TC-02, étape 2** : quel texte d'écho la campagne envoie-t-elle ? Le plan
   dit « un texte choisi » sans le relever. L'attendu (égalité de l'écho) ne
   dépend pas de la valeur, mais la suite doit en fixer une.
2. **TC-02, étape 4** : quels champs de la structure d'écho sont remplis et
   assertés ? Le plan ne relève que « structure renvoyée et table non vide ».
3. **TC-05, TC-07, TC-09, TC-10** : les valeurs volontairement fautives (nom
   de table inexistante, nom de champ inventé, nom de module inexistant,
   identifiant utilisateur inconnu, nom de job absent, mandant inexistant,
   numéro de système injoignable) ne sont pas relevées par le plan. Elles sont
   arbitraires par nature, mais doivent être fixées et stables pour que le cas
   soit rejouable à l'identique.
4. **TC-09, étape 3** : quelle valeur pour le budget d'attente court ? Le plan
   dit « avec un délai court » sans le chiffrer. Il s'agit d'une borne de
   budget, pas d'une temporisation.
5. **TC-08, étape 3** : faut-il un plancher de volume pour l'inventaire des
   BAPIs, et lequel ? Le plan constate une liste non vide sans en relever la
   taille, et refuse explicitement de figer le catalogue.
6. **Scénario 9, branche « annulé »** : comment éprouver la détection d'un job
   au statut annulé alors que la cible ne porte que des runs terminés et que
   la campagne est en lecture seule ? Une réponse possible serait un autre
   système ou un jeu de données préparé hors campagne, mais aucune source ne
   la formule.
7. **Critères de sortie chiffrés** : taux de réussite exigé, traitement des
   cas sautés dans le verdict de campagne, seuil au-delà duquel un écart de
   volumétrie devient une anomalie. Rien dans les sources ne les fixe.
8. **Cadence et lieu d'exécution** : la campagne tourne-t-elle en CI, où le
   SDK NW RFC sous licence redeviendrait un prérequis, ou seulement sur des
   postes porteurs de SAP GUI ? Le plan décrit les deux situations sans
   trancher.
