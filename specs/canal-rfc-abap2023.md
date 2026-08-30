# Canal RFC : ce qui diverge d'une release ABAP à l'autre (cible ABAP Platform 2023)

- **Canal** : RFC / BAPI (`SapApiLibrary`, `pyrfc`), avec croisement ponctuel
  vers le canal OData du même système.
- **Système observé** : ABAP Platform 2023 en conteneur, `sysId` A4H,
  release **758**, kernel **793**, base HDB, hôte applicatif `vhcala4h`
  (adresse `172.17.0.4` au moment de la mesure), joint en `ashost=127.0.0.2`,
  `sysnr=00`, mandant `001`, utilisateur `DEVELOPER`, langue `EN`. Canal OData
  du même système : `http://localhost:50100`, mandant `001`.
- **Exploration live** : 2026-08-28, une passe complète contre le système réel
  via le serveur rf-mcp. Tous les chiffres de ce plan sont mesurés ce jour-là,
  sauf ceux explicitement attribués à une source datée (voir plus bas).
- **Posture** : LECTURE SEULE. Aucun scénario n'écrit, ne crée ni n'annule quoi
  que ce soit. Aucun job n'est planifié, aucune LUW n'est validée.

## Pourquoi ce plan existe

`specs/canal-rfc-a4h.md` couvre déjà le canal RFC sur la release 1909, et la
suite qui en est née passe telle quelle sur la 2023, par simple surcharge de
variables. La **portabilité est donc acquise et n'est pas le sujet ici**.

Le sujet est ce que deux releases rendent visible et qu'une seule cache. Le
dépôt a déjà payé cette leçon côté web : la paire de campagnes
`exploration-flp-abap-*` a montré qu'une campagne mono-release grave des
hypothèses sans le savoir (nom de contrôle, position d'un bouton, plancher de
comptage). Ce plan applique la même méthode au canal sans écran, et il en tire
la même conclusion : **une équivalence mesurée vaut une divergence mesurée**,
et les deux ensemble disent où placer une assertion.

## Préconditions

1. **Interpréteur Python 3.10 à 3.12.** `pyrfc` n'a aucune roue précompilée
   au-delà de 3.12 et toutes ses versions PyPI sont `yanked` depuis
   l'archivage du projet par SAP. Mesuré ce jour : le serveur rf-mcp de ce
   poste sert `pyrfc` 3.3.1 et le canal est déclaré disponible, donc
   l'exploration a pu se faire par les outils MCP, ce que la campagne 1909
   n'avait pas pu faire (voir sa section « Contrainte d'outillage »).
2. **Runtime NW RFC présent.** Mesuré : la bibliothèque native cliente est en
   release **753**, celle que dépose le composant « SAP NWRFC x64 Shared » du
   client SAP GUI 8.00. Elle dialogue sans réserve avec un serveur 758 : le
   décalage client/serveur n'est pas un sujet sur cette cible.
3. **Relais TCP local, et c'est une précondition d'ENVIRONNEMENT, pas un
   contournement.** `127.0.0.2` n'est pas un hôte SAP : c'est un relais local
   qui réaligne le port et le numéro d'instance. Le conteneur publie ses ports
   décalés (`127.0.0.1:3301` vers son `3300` interne), or le protocole dérive
   le port du numéro d'instance ; viser `127.0.0.1` obligerait à annoncer
   `sysnr=01`, et l'instance interne étant `00`, la connexion échoue en
   réclamant une passerelle `sapgw01` qui n'existe pas. La dérivation est
   **prouvée par une mesure de ce plan** : une ouverture sur `sysnr=42` échoue
   en nommant `127.0.0.2:3342`, soit 3300 plus le numéro d'instance. Le relais
   doit donc être levé avant toute exécution, et son absence se lit comme un
   refus de communication, jamais comme un problème de compte.
4. **Identifiants par la ligne de commande** (convention 11). Aucun mot de
   passe n'est écrit ici ni dans une suite : `-v "RFC_PASSWORD: Secret:…"`.
5. **Les deux canaux visent le même mandant** (`001`) pour tout croisement.
6. **Suite neutre par défaut** : sur un poste sans canal RFC, elle se saute au
   lieu de rougir.

## Données observées

### Sources de ce plan

| Marque | Origine |
|---|---|
| **2023** | mesuré live le 2026-08-28 sur la cible décrite ci-dessus |
| **1909 (daté)** | relevé live le 2026-08-27, consigné dans `specs/canal-rfc-a4h.md` |
| **1909 (brief)** | relevé le 2026-08-28 par la demande à l'origine de ce plan |

Rien d'autre n'entre dans ce plan. Ce qui n'a pas été mesuré est listé en fin
de document sous « Ce qui n'a pas pu être sondé ».

### 1. Identité : ce qui distingue les deux systèmes, et ce qui ne distingue rien

Les deux conteneurs portent le **même identifiant système** et le **même nom
d'hôte applicatif**. Mesuré des deux côtés, ces deux valeurs sont donc
inutilisables comme preuve de cible.

| Attribut | 2023 | 1909 (daté) | Discrimine ? |
|---|---|---|---|
| identifiant système | `A4H` | `A4H` | **non** |
| hôte applicatif publié | `vhcala4h` | `vhcala4h` | **non** |
| base de données | `HDB` | `HDB` | non |
| système d'exploitation | `Linux` | `Linux` | non |
| release du partenaire | `758` | `754` | **oui** |
| release kernel | `793` | `777` | **oui** |
| adresse IP publiée | `172.17.0.4` | `172.17.0.2` (daté), `172.17.0.3` (brief) | **non, volatile** |

L'adresse IP mérite sa ligne : elle a changé entre deux relevés du **même**
système à un jour d'intervalle, parce qu'un conteneur redémarré reprend
l'adresse libre suivante. Elle distingue deux systèmes à un instant donné et
ne prouve rien le lendemain : ce n'est pas une ancre.

Deux autres relevés du 2023 qui ne prouvent pas ce qu'ils semblent prouver :

- l'attribut de connexion qui porte un nom d'hôte vaut le nom du **poste
  client**, pas l'hôte SAP ; l'hôte applicatif se lit dans la fiche que le
  système publie sur lui-même ;
- le champ système d'un message BAPI vaut `A4HCLNT001` sur cette cible, donc
  la même valeur que sur l'autre conteneur : même un message applicatif ne
  départage pas les deux.

**La source d'identité la plus riche mesurée sur la 2023 est l'inventaire des
composants logiciels**, qui n'apparaissait pas dans la campagne 1909 :

| Composant | Release | Niveau de support |
|---|---|---|
| `SAP_BASIS` | `758` | `0000000002` |
| `SAP_ABA` | `75I` | `0000000002` |
| `SAP_GWFND` | `758` | `0000000002` |
| `SAP_UI` | `758` | `0000000002` |
| `SAP_BW` | `758` | `0000000002` |
| `S4FND` | `108` | `0000000002` |
| `MDG_FND` | `808` | `0000000002` |
| `UIBAS001` | `758` | `0002` |
| `DMIS` | `2020` | `0000000008` |
| `ST-PI` | `740` | `0000000028` |

Quatre composants locaux complètent la liste (`HOME`, `LOCAL`, `ZLOCAL`,
`ZCUSTOM_DEVELOPMENT`, tous en release `DEV`) : ils signalent que la cible
porte du développement propre, ce qui est un fait à consigner pour toute
comparaison ultérieure.

La fiche système publie aussi un indicateur S/4HANA positionné sur cette
cible, ainsi qu'une destination `vhcala4hci_A4H_00` et un nom pleinement
qualifié `vhcala4hci`. Ces trois valeurs n'ont **pas** été relevées sur la
1909, donc aucune comparaison n'est affirmée ici.

### 2. Contrat de champs du dictionnaire : équivalence mesurée

Le brief signalait le risque : une liste de champs valable sur une release
peut ne pas l'être sur l'autre, et le refus accuse alors la table alors que la
faute est dans un nom de champ.

| Mesure | 2023 | 1909 (daté) |
|---|---|---|
| nombre de champs du catalogue de champs, lu sur lui-même | **31** | **31** |
| plus grande position de champ | `0031` | non relevée |
| le champ de classe d'autorisation existe-t-il sur ce catalogue ? | **non** | **non** |

Le champ de classe d'autorisation **existe bien dans le système** (porté par
une vingtaine d'autres objets du dictionnaire, dont les vues historiques du
dictionnaire et les tables de version), mais **pas** sur le catalogue de
champs : le piège de la 1909 se reproduit à l'identique. C'est donc une
équivalence, et une équivalence qui a de la valeur, parce qu'elle dit qu'une
suite qui lit le contrat sur la cible reste juste sur les deux releases,
là où une liste écrite de mémoire aurait pu être fausse sur l'une des deux.

### 3. Données de démonstration : le modèle classique est identique

| Jeu | 2023 | 1909 (daté) |
|---|---|---|
| compagnies aériennes du modèle classique | **18** | **18** |
| liaisons aériennes | **14** | **14** |
| produits du modèle marchand | **205** | **205** |
| mandants installés | **2** (`000`, `001`, tous deux « SAP SE / Walldorf ») | idem |
| prix du vol de référence, lu en table | `"666.00"` en `EUR` | `"666.00"` en `EUR` |
| le même prix, rendu par une interface métier | `Decimal('666.0000')` | idem |

La leçon de typage est donc identique sur les deux releases : le même montant
revient en **texte** par la lecture générique de table et en **décimal ABAP**
par l'interface métier. Une assertion numérique convertit, elle ne compare
jamais les deux représentations.

### 4. Le modèle de voyage moderne, et le piège des deux catalogues de compagnies

La 2023 porte un modèle de voyage moderne largement déployé, mesuré ici :

| Mesure | 2023 |
|---|---|
| tables transparentes du modèle moderne | **47** |
| voyages | **4136** |
| voyages dans la persistance active du variant à brouillons | **4136** |
| compagnies du modèle moderne | **16** |

**Le piège, et c'est le constat le plus exploitable de cette exploration** :
le système porte **deux** catalogues de compagnies aériennes, de populations
**différentes**. Le catalogue classique en compte 18, celui du modèle moderne
en compte 16 : deux codes compagnie présents dans l'un sont absents de
l'autre. Un croisement qui rapproche le comptage d'un canal sur un catalogue
et le comptage de l'autre canal sur le second catalogue produit un écart de
deux lignes, parfaitement reproductible, et attribué à un défaut qui n'existe
pas. Inversement, une égalité obtenue en confondant les deux serait un vert
construit sur une coïncidence.

Il n'est **pas** établi que le modèle moderne soit absent ou plus pauvre sur
la 1909 : la 1909 le porte aussi (le dépôt le sait par ailleurs), mais sa
volumétrie n'a jamais été mesurée. Ce plan n'affirme donc qu'une chose sur ce
point : les chiffres ci-dessus valent pour la 2023, à cette date.

### 5. Croisement entre les deux canaux du même système

| Fait métier | Compté par RFC | Compté par OData | Verdict |
|---|---|---|---|
| produits du modèle marchand | **205** | **205** | égalité |
| voyages du modèle moderne | **4136** | **4136** | égalité |
| compagnies du modèle moderne | **16** | **16** | égalité |

Le premier croisement est celui que la campagne 1909 verrouille déjà, et il
donne le même chiffre ici. **Les deux autres sont nouveaux** : ils portent sur
le modèle moderne, que la campagne 1909 ne croisait pas, et ils passent par
un service OData que le catalogue de la 2023 publie.

État du canal OData de la 2023 mesuré au passage : catalogue joignable en
HTTP 200 **sans aucune activation préalable**, et **58 services** publiés dans
le mandant de connexion. C'est une divergence d'exploitation nette avec un
conteneur 1909 recréé, où la passerelle est désactivée et exige une activité
de personnalisation avant de répondre.

### 6. Refus applicatifs : six codes, six équivalences

Tous mesurés sur la 2023, tous identiques à ceux relevés sur la 1909.

| Cas provoqué | Classe | Code technique | Code numérique |
|---|---|---|---|
| Table inexistante | erreur applicative | `TABLE_NOT_AVAILABLE` | 5 |
| Champ inexistant sur une table pleine | erreur applicative | `TABLE_WITHOUT_DATA` | 5 |
| Module fonction inexistant | erreur applicative | `FU_NOT_FOUND` | 5 |
| Paramètre inconnu du module | erreur du runtime client | `RFC_INVALID_PARAMETER` | 20 |
| Mot de passe faux | refus d'ouverture | `RFC_LOGON_FAILURE` | 2 |
| Mandant inexistant | refus d'ouverture | `RFC_LOGON_FAILURE` | 2 |
| Instance injoignable | refus de communication | `RFC_COMMUNICATION_FAILURE` | 1 |

**Enrichissement mesuré sur la 2023, et transposable à la 1909** : les trois
refus applicatifs portent, en plus de leur code, un **identifiant de message
stable** (classe de message, type et numéro), lisible sans traduction :

| Cas | Identifiant relevé |
|---|---|
| Table inexistante | classe `DA`, type `E`, numéro `131` |
| Champ inexistant | classe `AD`, type `E`, numéro `718` |
| Module fonction inexistant | classe `FL`, type `E`, numéro `046` |

Cet identifiant est plus fin que le code et reste conforme à la convention 3
(rien de localisé). La campagne 1909 ne l'exploitait pas.

**La seule divergence de refus mesurée** concerne les deux refus d'ouverture.
Le plan de la 1909 note que mot de passe faux et mandant inexistant partagent
le code et que « seul le texte les sépare ». Sur la 2023, les deux cas rendent
non seulement le même code mais **le même texte, mot pour mot**. Sur cette
release, rien ne les distingue : un test qui aurait tenté de les séparer par
le texte, déjà interdit par la convention 3, échouerait ici pour de bon.

Le refus de communication, lui, nomme le port réellement contacté et la
release de la bibliothèque cliente : c'est ce qui rend la précondition du
relais démontrable au lieu d'être racontée.

### 7. Journal des jobs de fond : mêmes issues, autres porteurs

| Mesure | 2023 | 1909 (daté) |
|---|---|---|
| runs consignés | **6030** | **4719** |
| terminés | **5908** | **4597** |
| statut hors carte | **107** | **105** |
| annulés | **12** | **10** |
| encore dans le pipeline | **3** | **7** |
| jobs portant le cas « tous terminés » | **232** | non relevé |

Les **cinq issues de l'attente sont éprouvables sur les deux cibles**, ce qui
est l'équivalence utile. Ce qui diverge, ce sont les **jobs qui les portent** :

| Issue | Porteurs 2023 | Porteurs 1909 (daté) |
|---|---|---|
| annulé avec des runs terminés | 6 jobs, dont **2 absents de la liste 1909** | 5 jobs, dont **1 absent de la liste 2023** |
| encore dans le pipeline | **3 jobs** (1 commun, 2 propres à la 2023) | **1 job** |
| statut hors carte | 1 job, **le même des deux côtés**, avec le même compte de 69 runs | idem |

C'est la **preuve mesurée** de la décision prise à la génération de la suite
1909 : ne graver aucun nom de job et découvrir les cibles sur le système. Un
nom d'infrastructure gravé aurait tenu sur une release et sauté sur l'autre,
et il aurait sauté en donnant l'impression que l'attente est cassée.

Le statut hors carte reste non interprété, exactement comme sur la 1909 : son
domaine ne porte aucune liste de valeurs, sa signification n'est donc pas
établie et ne sera pas devinée. Seul le comportement de repli s'asserte.

### 8. Surface du canal, mesurée sur la 2023

| Mesure | 2023 | 1909 |
|---|---|---|
| modules fonction ouverts à distance | **22047** | non relevé |
| interfaces métier publiées à l'inventaire | **735** | non relevé |
| objets du modèle de programmation moderne (définitions et liaisons de service, définitions de comportement) | **688** | non relevé |
| services publiés au catalogue OData | **58** | non comparable |

Aucune de ces quatre mesures n'a d'équivalent daté côté 1909 : elles sont
consignées ici comme **point de départ** d'une comparaison, pas comme une
comparaison. C'est précisément ce que le scénario 9 propose d'industrialiser.

## Scénarios

### 1. La cible se prouve par sa release et ses composants, jamais par son identifiant système

- **Étapes** :
  1. Ouvrir le canal RFC sur la cible.
  2. Lire les attributs de la connexion.
  3. Lire la fiche que le système publie sur lui-même.
  4. Lire l'inventaire des composants logiciels installés.
- **Résultat attendu** : les trois sources s'accordent sur la release et sur
  le kernel ; la release attendue est celle de la cible visée ; le composant
  de base porte exactement cette release. Le mandant servi est celui demandé.
  Aucune assertion ne repose sur l'identifiant système ni sur le nom d'hôte
  applicatif, **et le scénario le dit explicitement** : ces deux valeurs sont
  identiques sur les deux conteneurs du poste, donc une campagne qui s'y
  fierait serait verte contre le mauvais système.
- **Points de vigilance** : ne rien asserter sur l'adresse IP publiée, qui
  change au redémarrage d'un conteneur. Ne rien asserter sur le nom d'hôte
  porté par les attributs de connexion : c'est le poste client.
- **Keywords métier manquants** : lecture de l'inventaire des composants
  logiciels, sous un nom métier.

### 2. Le contrat de champs se lit sur la cible, jamais de mémoire

- **Étapes** :
  1. Demander à la cible la liste des champs d'une table du dictionnaire, en
     interrogeant cette table sur elle-même.
  2. Relire la même table en demandant tous les champs ainsi obtenus.
  3. Provoquer la même lecture avec un nom de champ qui n'existe pas.
- **Résultat attendu** : la liste obtenue de la cible passe intégralement en
  relecture ; le nom inventé fait échouer la lecture entière avec le code qui
  accuse la table d'être sans données, alors qu'elle est pleine. La
  contre-épreuve est **jouée**, pas citée : c'est elle qui prouve que le code
  désigne la mauvaise chose.
- **Pourquoi** : c'est le piège de diagnostic du canal, celui qui envoie
  chercher un problème de données là où il y a une faute de frappe ou un champ
  disparu entre deux releases. Une suite qui lit le contrat sur la cible y est
  immunisée ; une suite qui grave une liste de champs y est exposée.

### 3. Le jeu de démonstration classique se compte, et il est le même sur les deux releases

- **Étapes** :
  1. Compter le catalogue des compagnies aériennes classiques.
  2. Compter les liaisons aériennes.
  3. Compter les produits du modèle marchand.
  4. Lire les mandants installés.
  5. Lire le prix d'un vol de référence par la table, puis le même prix par
     l'interface métier.
- **Résultat attendu** : les comptes sont strictement positifs ; le mandant de
  connexion figure dans l'annuaire ; les deux représentations du prix sont
  **égales après conversion numérique** et jamais comparées comme des textes.
- **Points de vigilance** : les comptes relevés ne sont pas gravés dans la
  suite. Ce sont des relations qui s'assertent, pour que la campagne reste
  vraie sur un système dont le jeu de démonstration aurait été régénéré. Les
  chiffres du présent plan servent de calage, pas d'assertion.

### 4. Deux catalogues de compagnies coexistent, et il faut nommer celui qu'on lit

- **Étapes** :
  1. Compter les compagnies du catalogue classique.
  2. Compter les compagnies du modèle de voyage moderne.
  3. Confronter les deux listes de codes.
- **Résultat attendu** : les deux comptes **diffèrent**, et l'écart est
  entièrement expliqué par les codes présents dans l'un et absents de l'autre.
  Le scénario asserte l'inclusion du plus petit catalogue dans le plus grand,
  et **refuse** l'égalité des deux comptes.
- **Pourquoi** : c'est un scénario qui échoue si quelqu'un « corrige » un jour
  un croisement en pointant les deux canaux sur des catalogues différents.
  Formulé à l'envers, il transforme un piège silencieux en assertion bruyante.
- **Keywords métier manquants** : vocabulaire du modèle de voyage moderne
  (compagnies, voyages), aujourd'hui absent de la couche resource du canal.

### 5. Le même fait métier par deux canaux, sur le modèle moderne

- **Étapes** :
  1. Ouvrir le canal OData sur le même système et le même mandant, et attendre
     qu'il réponde.
  2. Vérifier que les deux canaux visent bien le même mandant.
  3. Compter les voyages par le canal RFC.
  4. Compter le même ensemble par le canal OData.
  5. Répéter pour le catalogue de compagnies du modèle moderne.
- **Résultat attendu** : égalité stricte des deux comptes, sur les deux
  ensembles. Les deux comptes sont calculés dans le même run, jamais gravés.
- **Points de vigilance** : les deux canaux doivent viser le même mandant,
  sinon la comparaison porte sur deux populations. Le premier appel d'un
  service jamais sollicité sur un système froid peut être lent : ce n'est pas
  une panne, d'où un préflight patient. Enfin l'ensemble choisi ne doit pas
  être une projection à brouillons, sinon le comptage agrège des états
  différents de ceux que la table porte ; sur cette cible, le service retenu
  rend exactement le compte de la table, ce qui a été vérifié.
- **Keywords métier manquants** : le chemin du service moderne, sous un nom
  métier, dans la couche resource du canal OData.

### 6. Les refus applicatifs se classent par leur code, et par leur identifiant de message

- **Étapes** : provoquer, sur la connexion ouverte, une table inexistante, un
  champ inexistant, un module inexistant et un paramètre inconnu.
- **Résultat attendu** : chaque échec porte son code technique attendu, et les
  trois refus applicatifs portent en outre l'identifiant de message attendu
  (classe, type, numéro). Aucun texte n'est asserté.
- **Pourquoi asserter les deux** : le code est stable mais grossier (deux
  causes très différentes peuvent le partager) ; l'identifiant de message est
  fin et reste indépendant de la langue. Les asserter ensemble donne un refus
  caractérisé sans jamais toucher au libellé.
- **Keywords métier manquants** : une assertion « cet appel échoue avec
  l'identifiant de message X », complémentaire de l'assertion par code qui
  existe déjà.

### 7. Deux refus d'ouverture que rien ne distingue, et un troisième d'une autre nature

- **Étapes** : tenter une ouverture avec un mot de passe faux ; avec un
  mandant inexistant ; vers un numéro d'instance injoignable.
- **Résultat attendu** : les deux premiers échouent avec le **même code** et,
  sur cette release, le **même message** ; le scénario constate donc un refus
  d'ouverture de session et **n'affirme rien sur sa cause**. Le troisième
  échoue en refus de communication, et son message nomme le port réellement
  contacté, ce qui prouve que le port est dérivé du numéro d'instance.
  Aucune connexion n'est laissée ouverte, et aucun mot de passe n'apparaît
  dans le journal.
- **Pourquoi le troisième cas mérite son assertion** : il documente, dans le
  test lui-même, la raison d'être du relais local décrit en préconditions. Le
  jour où quelqu'un tentera de « simplifier » la configuration en visant
  directement le port publié, ce scénario nommera la mécanique en cause.
- **Points de vigilance** : ne provoquer chaque refus d'identification
  qu'**une seule fois** par exécution. Les tentatives infructueuses se
  cumulent côté serveur et un compte verrouillé rendrait toute la campagne
  rouge pour une raison sans rapport avec le canal.

### 8. Les cinq issues de l'attente d'un job existent ici aussi, portées par d'autres jobs

- **Étapes**, toutes en lecture seule : lire le journal des jobs **sans
  plafond** ; le classer par cas ; puis, pour chacune des cinq issues,
  découvrir sur le système un job qui porte le cas et attendre ce job avec un
  budget court sur les branches qui ne peuvent pas aboutir.
- **Résultat attendu** : les cinq issues se produisent (conclusion sur un job
  terminé ; échec sur une annulation, même quand le job porte par ailleurs des
  dizaines de runs terminés ; échec de budget nommant le pipeline ; échec de
  budget signalant qu'un statut est hors carte et que l'attente continue ;
  échec nommant l'absence d'un job inconnu). Une branche dont aucune cible
  n'existe est **sautée en le disant**, jamais déclarée verte.
- **Le point que ce plan ajoute à celui de la 1909** : le scénario asserte
  aussi que **les jobs choisis ne sont pas les mêmes que sur l'autre release**.
  Concrètement, il vérifie que les cibles ont été découvertes et non lues dans
  une constante, en confrontant les jobs retenus à ceux qu'aucune suite ne
  doit connaître. C'est la seule façon de garder honnête un mécanisme de
  découverte : sinon, rien n'empêche quelqu'un de le remplacer un jour par une
  liste, et la suite resterait verte sur la cible du moment.
- **Points de vigilance** : lire le journal **sans plafond**. Un plafond ne
  tronque pas seulement le résultat, il fausse la classification en silence,
  et c'est exactement l'erreur qui avait faussé la première exploration de la
  1909. La signification du statut hors carte n'est pas établie et ne sera pas
  devinée.

### 9. La surface du canal devient un artefact comparable entre deux releases

- **Étapes** :
  1. Mesurer, sur la cible ouverte, le nombre de modules fonction ouverts à
     distance, l'inventaire des interfaces métier publiées, l'inventaire des
     objets du modèle de programmation moderne, les composants logiciels et
     les volumétries des jeux de démonstration.
  2. Écrire ces relevés dans un artefact déterministe (trié, hashé hors
     horodatage), à la manière de ce que font déjà l'inventaire du
     dictionnaire et la campagne de croisement.
  3. Hors système, comparer deux artefacts produits sur deux cibles.
- **Résultat attendu** : deux exécutions sur la même cible produisent le même
  hash ; la comparaison de deux cibles rend une liste d'écarts nommés, séparés
  en trois catégories : présent des deux côtés, propre à la première cible,
  propre à la seconde.
- **Pourquoi ce scénario est le coeur du plan** : les questions du brief
  (« quels modules ici et pas là-bas ») ne se répondent pas par une note dans
  un document, elles se répondent par un artefact qu'on produit sur chaque
  cible et qu'on compare. Le dépôt possède déjà ce patron pour le dictionnaire
  et pour le croisement entre canaux ; le canal RFC ne l'a pas.
- **Keywords métier manquants** : la mesure de surface, l'écriture de
  l'artefact et la comparaison de deux artefacts. La logique de comparaison
  est pure et n'a pas besoin de SAP : elle appartient à la bibliothèque
  (convention 12), pas à un calcul improvisé dans une suite.
- **Points de vigilance** : un artefact n'a de sens qu'accompagné de
  l'identité de la cible qui l'a produit (release, kernel, composants), sans
  quoi comparer deux artefacts revient à comparer deux inconnues. Et un
  artefact porte un périmètre : comparer deux cibles dont les périmètres
  diffèrent doit être refusé, pas moyenné.

### 10. Le canal se referme entièrement, y compris après un refus

- **Étapes** : ouvrir un second alias sur la même cible ; appeler sur chacun ;
  lister les connexions ouvertes ; refermer le canal en une fois ; vérifier
  qu'un appel sur un alias fermé échoue proprement.
- **Résultat attendu** : les deux alias répondent indépendamment ; la
  fermeture globale ne laisse aucune connexion ; un appel après fermeture
  nomme le mot-clé d'ouverture. Après les trois refus du scénario 7, l'état du
  canal ne porte **que** la connexion nominale : un refus d'ouverture ne laisse
  rien derrière lui.
- **Pourquoi** : une connexion RFC orpheline est une session utilisateur
  restée ouverte côté serveur. Vérifié pendant l'exploration : après les trois
  refus, une seule connexion subsistait, celle qui avait été ouverte
  volontairement.

## Points de vigilance pour la génération

- **Une suite paramétrée par la cible, jamais une suite par release.** Tout ce
  qui diffère (hôte, numéro d'instance, release attendue, composant de base
  attendu, chemins de services) est une **variable** ; tout ce qui diffère
  dans le comportement est une **stratégie nommée**. Aucun test conditionnel
  sur le numéro de release : ajouter une release doit ajouter un jeu de
  variables, pas une branche. C'est la règle que les deux campagnes
  `exploration-flp-abap-*` ont déjà éprouvée côté web.
- **Convention 1** : aucun nom de module fonction, d'interface métier, de
  table ni de chemin de service dans les scénarios. Ils vivent dans la couche
  resource, sous des noms métier. Les relevés techniques de ce plan sont là
  pour la génération, pas pour les étapes.
- **Convention 3** : les refus se jugent sur un code technique ou sur un
  identifiant de message (classe, type, numéro), jamais sur un texte. Ce plan
  en donne une raison de plus : sur cette release, deux causes distinctes
  rendent un texte identique.
- **Convention 11** : le mot de passe arrive en variable typée par la ligne de
  commande, et la garde qui vérifie sa présence ne le **mesure** jamais.
- **Convention 12** : les capacités manquantes du scénario 9 (mesure de
  surface, artefact, comparaison) vont dans la bibliothèque, logique pure
  isolée, avec leurs tests hors SAP. Ni un calcul dans une suite, ni un
  utilitaire local que cette seule campagne verrait.
- **Opt-in par tag et saut propre** si le canal n'existe pas sur le poste,
  comme la campagne 1909 : une suite qui rougit là où rien n'est cassé finit
  désactivée.
- **Aucune écriture, aucun job créé ni annulé.** Les cinq issues de l'attente
  s'éprouvent sur les jobs d'exploitation que la cible porte déjà.
- **La suite existante ne bouge pas.** Elle passe sur les deux cibles par
  surcharge de variables ; cette campagne s'ajoute à côté et ne la remplace
  pas.

## Ce qui n'a pas pu être sondé

Consigné ici pour qu'aucun lecteur ne prenne une absence de mesure pour une
absence de divergence.

1. **Aucune mesure live n'a été prise sur la 1909 pendant cette exploration.**
   Les identifiants de ce système n'étaient pas fournis, et tenter une
   ouverture pour « voir » aurait consommé des tentatives infructueuses sur un
   compte réel, avec un risque de verrouillage sans contrepartie. Toutes les
   valeurs 1909 de ce plan viennent donc de relevés live **datés** consignés
   dans le dépôt ou fournis avec la demande, et sont marquées comme telles.
2. **La comparaison des modules fonction et des interfaces métier entre les
   deux releases n'a pas été faite.** Elle exige deux inventaires, et il n'en
   existe qu'un : c'est exactement le manque que le scénario 9 comble.
3. **La volumétrie du modèle de voyage moderne sur la 1909 est inconnue.** Ce
   plan n'affirme donc aucune divergence sur ce modèle, seulement des chiffres
   propres à la 2023.
4. **L'indicateur S/4HANA et la destination publiée par la fiche système** ne
   sont pas comparables : ils n'ont pas été relevés sur la 1909.
5. **Le catalogue OData des deux systèmes n'est pas comparable en l'état** :
   les 58 services relevés ici le sont dans le mandant de connexion d'un
   système opérationnel, alors que le chiffre disponible pour l'autre cible
   avait été relevé dans un autre mandant, juste après une réactivation.
6. **L'échange de structures typées n'a pas été rejoué via les outils MCP** :
   la frontière refuse une structure passée en texte, ce qui est le
   comportement attendu. Cette sonde reste couverte par la suite existante,
   qui passe sur cette cible.

## Écarts constatés à la génération

Relevés le 2026-08-28 en montant `tests/robot/api/canal_rfc_abap2023.robot`,
chaque étape rejouée live avant écriture.

**Aucun chiffre du plan n'a été contredit.** Les 18 et 16 compagnies, les 4136
voyages, les 47 tables du modèle moderne, les 688 objets du modèle de
programmation, les 22047 modules ouverts à distance, les 735 interfaces
métier, les 6030 runs de jobs et leur ventilation, les trois identifiants de
message et les six codes de refus ont tous été remesurés et retrouvés à
l'identique. Ce qui suit ne corrige donc pas le plan : ce sont des choix de
réalisation qui s'en écartent, et les raisons de s'en écarter.

1. **Scénario 8 : la preuve que la découverte découvre est faite autrement que
   le plan ne le propose.** Le plan demande de « confronter les jobs retenus à
   ceux qu'aucune suite ne doit connaître », c'est-à-dire aux porteurs de
   l'autre release. Écrire ces noms dans la suite serait exactement ce que le
   plan interdit par ailleurs, et une liste de noms interdits est encore une
   liste de noms gravés. La suite fait donc mieux et sans rien graver : elle
   **re-dérive elle-même la classification** depuis les décomptes bruts de
   statuts par job et la confronte à celle que la perception propose (mot-clé
   local `Every Discovered Job Should Really Carry Its Case`). Une liste de
   noms substituée un jour à la découverte ne survivrait pas à cette
   confrontation avec le journal du moment, quelle que soit la cible.
2. **Scénario 8 : les cinq attentes elles-mêmes ne sont pas rejouées.** La
   suite de la release précédente les éprouve déjà branche par branche, et
   elle passe sur cette cible (16/16, vérifié le même jour). Les rejouer aurait
   aussi obligé à mettre cinq `Skip` conditionnels dans un test unique, or un
   saut interrompt le test entier : quatre branches auraient été perdues dès
   qu'une seule cible manque. Le scénario ne garde donc que ce qui est
   nouveau : lecture sans plafond, décompte exhaustif, re-dérivation.
3. **Scénario 9 : la comparaison de deux cibles RÉELLES n'a pas pu être
   jouée.** Une seule cible était joignable, pour la raison que le plan
   consigne déjà (les identifiants de l'autre système n'étaient pas fournis, et
   sonder « pour voir » aurait consommé des tentatives infructueuses sur un
   compte réel). Ce qui est éprouvé LIVE est donc la moitié qui ne demande
   qu'une cible, et c'est celle dont tout le reste dépend : le déterminisme du
   hash hors horodatage et la présence de l'identité dans l'artefact. La
   détection d'écarts (trois catégories de composants, changements de release,
   refus de comparer deux périmètres différents) est verrouillée hors SAP par
   `tests/unit/test_rfc_surface.py`. Le test le dit dans sa documentation
   plutôt que de laisser croire l'inverse.
4. **Scénario 3 allégé.** Le filtre sur une compagnie, le plafond de lignes et
   le filtre sans correspondance sont déjà éprouvés par la suite soeur sur
   cette cible : le scénario garde les comptages, l'annuaire des mandants et la
   leçon de typage du prix, qui sont ce que le plan pose comme équivalence
   entre les deux releases.
5. **Ajout au scénario 1 : une contre-épreuve de release.** Le plan écarte
   l'identifiant système et le nom d'hôte, sans dire comment attraper le cas où
   la campagne viserait l'autre conteneur. La suite l'asserte franchement : la
   release lue doit différer de celle de l'autre conteneur du poste, portée par
   une variable (`${PEER_RELEASE}`). C'est le garde-fou que le constat
   « ces deux valeurs ne discriminent rien » appelait.
6. **Ajout au scénario 6 : l'absence d'identifiant de message est assertée
   comme une preuve.** Mesuré à la génération, le refus du runtime client
   (`RFC_INVALID_PARAMETER`) ne porte AUCUN identifiant de message, là où les
   trois refus applicatifs en portent un. Ce n'est pas un manque : c'est ce qui
   établit que ce refus n'a jamais atteint l'application. La suite l'asserte
   dans les deux sens, et le refus de communication du scénario 7 est traité de
   même.
7. **Le service OData du modèle moderne a été RELEVÉ live, pas deviné.** Le
   catalogue de la cible publie plusieurs services de voyage et ils ne
   projettent pas la même population : le service retenu est la variante sans
   brouillons, la seule dont le comptage égale celui de la table par le canal
   RFC (4136 = 4136 et 16 = 16, vérifiés à la génération). Son chemin vit sous
   un nom métier dans `resources/api_keywords.resource`, jamais dans un
   scénario.
8. **Trois capacités ont été ajoutées à la bibliothèque (convention 12), pas
   contournées dans la suite** :
   - l'**identifiant de message** d'un refus RFC (classe, type, numéro) entre
     dans la fiche que rend la classification des refus, avec un oracle dédié
     `Rfc Should Fail With Message Id` (`sapfx_common.rfc_channel`) ;
   - la **surface du canal** devient un artefact déterministe et comparable
     (`sapfx_common.rfc_surface`, mots-clés `Write` / `Read` /
     `Compare Rfc Surface Artifacts`) : c'est ce que le scénario 9 demandait
     d'industrialiser, et la logique de comparaison est pure, donc éprouvable
     sans SAP ;
   - toutes trois arrivent avec leurs tests hors SAP, leur carte d'intention
     rf-mcp et leur page Libdoc.
9. **Le vocabulaire du canal a été ÉTENDU, jamais dupliqué.**
   `resources/rfc_keywords.resource` est partagé avec la suite de l'autre
   release : la suite soeur a été rejouée en non-régression contre les DEUX
   systèmes après extension (16/16 des deux côtés).
