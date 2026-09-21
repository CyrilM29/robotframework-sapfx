# Extraire un tableau SAP par le canal RFC, et à l'échelle

- **Canal** : **RFC** (`SapApiLibrary`, `pyrfc`). Le quatrième canal d'extraction
  du dépôt, après l'écran SAP GUI, le WebGUI et l'UI5. Aucun écran, aucune URL,
  aucun cookie : un système applicatif, un mandant et une LUW.
- **Système observé** : A4H (ABAP Platform 1909), `ashost=localhost`,
  `sysnr=00`, mandant `001`, utilisateur `DEVELOPER`. Release SAP_BASIS **754**,
  kernel **777** (mesurés live ce jour).
- **Exploration live** : 2026-09-16, par le serveur rf-mcp, en lecture seule.
  Contrairement au canal écran, le canal RFC se sonde sans risque depuis un
  thread étranger : il ne porte aucun objet COM.
- **Posture** : LECTURE SEULE de bout en bout. Aucune écriture métier, aucune
  LUW ouverte, aucune donnée de démonstration régénérée. Les seuls effets de
  bord sont des fichiers dans le répertoire de sortie du run, et une connexion
  RFC ouverte puis refermée.

## Pourquoi ce plan plutôt qu'une extraction de plus

Le dépôt sait extraire un tableau vers cinq formats depuis trois canaux, sous
une règle de refus commune. Ce plan ajoute le quatrième, et il n'est pas une
redite pour deux raisons que rien d'autre ne couvre.

**La première est une propriété du canal.** Les trois autres canaux DÉCLARENT
leur total (le compte de lignes d'une ALV, le `totalRows` d'une grille WebGUI,
la longueur du binding d'une table UI5). `RFC_READ_TABLE` ne déclare rien du
tout : il rend des lignes et se tait. Le total doit donc être mesuré ailleurs,
et le choix de cet ailleurs est la seule décision qui compte ici. Le mesurer
par une seconde lecture `RFC_READ_TABLE` reviendrait à comparer deux nombres
que le même module produit de la même façon, c'est-à-dire à écrire une garde
vraie quoi qu'il arrive : c'est exactement le défaut qu'une revue indépendante
a relevé sur ce dépôt le 2026-09-14, sur une jointure qui comparait deux
mesures de la même table.

**La seconde est une question d'échelle.** Le plus gros relevé jamais extrait
par ce dépôt porte 1639 lignes. Ce plan en extrait **28 782**, soit dix-sept
fois plus. Une capacité qui tient sur un rapport de paramètres et qu'on n'a
jamais poussée ne prouve rien de son comportement sur un vrai volume
transactionnel.

## Perception métier

- **Personas** : `@api` (le canal sans écran : RFC, BAPI, LUW, et ses codes de
  refus) croisée avec `@basis` (le domaine : dictionnaire, modules ouverts à
  distance, autorisation `S_RFC`). Aucune persona applicative n'est endossée,
  et c'est délibéré : il n'y a ici ni commande, ni pièce, ni document. La table
  visée porte des réservations de vol, mais elle est lue comme un **tableau à
  restituer**, jamais comme un flux métier à valider. C'est une campagne de
  restitution, pas de processus.
- **Où se lit la vérité** : pas dans le fichier produit, et pas non plus dans
  ce que la lecture a rendu. Elle se lit dans un **total mesuré par une source
  indépendante du lecteur**, et ce canal en offre deux, de forces inégales :
  1. le module de comptage `EM_GET_NUMBER_OF_ENTRIES`, qui compte côté serveur
     sans rapatrier une ligne (vérifié live : 0,021 s pour 28 782 lignes contre
     0,885 s pour les lire) ;
  2. le `$count` du service OData qui projette la même table, c'est-à-dire un
     **troisième canal** où ni le module de lecture ni celui de comptage
     n'interviennent (vérifié live : 205 des deux côtés).
  La seconde est la preuve la plus forte que ce dépôt sache produire sur une
  complétude, et le scénario 6 existe pour elle.
- **Risques métier priorisés**, dans cet ordre :
  1. **l'extrait présenté comme un inventaire.** Le risque dominant. Sur ce
     canal, une lecture bornée rend N lignes propres, ordonnées, complètes,
     sans le moindre témoin : ni ligne vide, ni clé manquante, ni renumérotation
     suspecte. Le dépôt a déjà payé ce piège une fois, hors extraction, quand un
     plafond de 200 lignes sur un journal de 4719 avait fait conclure que tous
     les jobs du système étaient terminés ;
  2. **le total qui décrit une AUTRE population que la lecture.** Propre à ce
     canal : le module de comptage ignore les clauses de sélection, donc
     apparier son total à une lecture filtrée fabrique des lignes manquantes
     qui n'ont jamais existé ;
  3. **le relevé vide déclaré complet.** Un total de zéro confronté à zéro
     ligne satisfait toutes les égalités de la garde. Seul un plancher de
     lignes le rattrape (voir « Points de vigilance », point 3) ;
  4. **l'extraction du mauvais système.** Les deux conteneurs du poste
     annoncent le même identifiant système `A4H` et le même nom d'hôte
     applicatif : seuls la release et le kernel les distinguent ;
  5. **le fichier qui existe sans porter la donnée** : zéros de tête mangés par
     un tableur, date ABAP relue comme un nombre, type gravé par inférence ;
  6. **la connexion RFC orpheline**, qui est une session utilisateur restée
     ouverte côté serveur.
- **Assertion reine** : la chaîne fermée aux deux bouts.
  `lignes lues = total mesuré par une source qui n'est pas le lecteur` d'un
  côté, `fichier RELU = relevé lu sur la cible`, ligne à ligne, de l'autre.
  Ni l'un ni l'autre ne suffit : le premier seul laisse passer un fichier mal
  écrit, le second seul compare une lecture partielle à elle-même et ne rougit
  jamais. Les scénarios 2 et 3 la portent pour la grosse table ; le scénario 6
  la porte dans sa forme la plus forte, où le total vient d'un canal tiers.
- **Réversibilité** : rien à défaire, aucune écriture métier n'ayant lieu. Ce
  qui doit être rendu à son état initial est d'un autre ordre et l'est
  explicitement : la connexion RFC est refermée par un teardown qui s'exécute
  même sur échec, et l'état réel du canal est RELU pour le prouver (vérifié
  live ce jour : `{'api_sessions': [], 'rfc_connections': []}` après fermeture).

## Préconditions

1. **Le canal RFC est optionnel** et doit pouvoir manquer sans faire rougir :
   `pyrfc` n'a aucune roue précompilée au-delà de Python 3.12 et exige un
   runtime natif NW RFC. La campagne se SAUTE en nommant la cause et son
   remède, les deux absences possibles (binding absent, runtime absent) n'ayant
   pas le même.
2. **Aucun identifiant n'a de valeur par défaut** (convention 11). Le mot de
   passe entre en variable typée `Secret` par la ligne de commande, et la garde
   ne le MESURE jamais.
3. **Le module de comptage doit être appelable à distance.**
   `EM_GET_NUMBER_OF_ENTRIES` répond sur cette cible (vérifié live), mais rien
   ne le garantit ailleurs : une cible durcie restreint `S_RFC` module par
   module. Son absence n'est pas une panne de connexion, et le message de repli
   le dit en nommant les deux sources de total de remplacement.
4. **Le jeu de données de démonstration doit être présent.** Les volumes
   ci-dessous sont ceux d'A4H après génération ; une image fraîche porterait des
   tables vides. La campagne ne les régénère pas (l'opération prend plusieurs
   minutes et n'est pas en lecture seule) : elle exige un plancher et échoue en
   le nommant.
5. **Budget disque.** L'extraction complète produit cinq fichiers pour 28 782
   lignes sur 13 colonnes, soit de l'ordre de quelques dizaines de mégaoctets
   par passage, et le scénario 7 en écrit un second jeu. Prévoir le répertoire
   de sortie en conséquence.
6. **Le canal Parquet est optionnel** : absent, la campagne attend quatre
   formats au lieu de cinq, l'annonce en journal et ne rougit pas.

## Données observées

Sauf mention contraire, tout ce qui suit a été mesuré live le 2026-09-16 par le
serveur rf-mcp, connexion RFC ouverte sur A4H mandant `001`.

### 1. L'identité de la cible, et ce qui la prouve vraiment

| Fait | Valeur lue | Sert d'ancre ? |
|---|---|---|
| identifiant système (`RFCSYSID`) | `A4H` | **non** : les deux conteneurs du poste le partagent |
| nom d'hôte applicatif (`RFCHOST`) | `vhcala4h` | **non** : partagé lui aussi |
| release (`RFCSAPRL`) | **`754`** | **oui** |
| kernel (`RFCKERNRL`) | **`777`** | **oui** |
| destination (`RFCDEST`) | `vhcala4hci_A4H_00` | indicatif |
| base de données, système (`RFCDBSYS`, `RFCOPSYS`) | `HDB`, `Linux` | indicatif |
| adresse IP (`RFCIPADDR`) | `172.17.0.3` | **jamais** : mesurée volatile, elle change au redémarrage d'un conteneur |

La cible annonce aussi `S4_HANA = 'X'`. La release voisine du banc (**758**,
kernel **793**) sert de contre-épreuve : elle n'est joignable en RFC que par un
relais TCP local, le port du répartiteur étant dérivé du numéro d'instance et
non du port publié.

### 2. Volumes de la cible, mesurés par le module de comptage

| Tableau | Lignes | Rôle dans la campagne |
|---|---|---|
| réservations de vol | **28 782** | le relevé à l'échelle (scénarios 2, 3, 4, 7) |
| annuaire des transactions | 12 166 | non utilisé, cité comme second gros volume disponible |
| catalogue des produits | **205** | le croisement à trois canaux (scénario 6) |
| vols | 94 | non utilisé |
| compagnies aériennes | 18 | non utilisé |
| liaisons aériennes | 14 | non utilisé |
| mandants | 2 | non utilisé |

Les deux valeurs en gras ont été recomptées live ce jour ; les autres
proviennent de la mesure du même jour qui a précédé ce plan.

### 3. Le piège du canal, reproduit sur la cible

Lecture bornée à 3 lignes du catalogue des produits, qui en compte 205 :

| Témoin | Valeur | Ce qu'il dit |
|---|---|---|
| lignes rendues | 3 | `AR-FB-1000`, `AR-FB-1001`, `AR-FB-1002` : consécutives, ordonnées, toutes colonnes remplies |
| `blank_rows` | **0** | aucune ligne vide |
| `keyless_rows` | **0** | aucune clé manquante |
| `declared_rows` | 205 | **venu de l'autre module** |
| `missing_rows` | 202 | déduit du seul total |
| `complete` | **`False`** | uniquement grâce au total |

Rien dans les lignes rendues ne trahit l'amputation. C'est la signature du
canal WebGUI, sur un canal de plus, et cette fois sans même une renumérotation
à interpréter. Le même relevé bornée à 2 lignes sur la table des réservations
donne exactement la même forme (2 lues, 28 782 déclarées, 28 780 manquantes,
zéro témoin).

Le libellé de provenance porte le plafond demandé, et c'est ce qui manque le
plus au lecteur d'un relevé court : `la table SNWD_PD (RFC), 3 colonne(s)
projetée(s), PLAFOND demandé 3`. Sans plafond, la mention disparaît.

### 4. L'échelle tient, et elle est rapide

| Geste | Durée mesurée |
|---|---|
| compter 28 782 lignes sans en rapatrier aucune | **0,021 s** |
| lire ces 28 782 lignes sur 13 colonnes, puis les compter | **0,885 s** |
| compter le catalogue par le `$count` OData | 0,074 s |
| refuser une lecture filtrée sans total | 0,005 s (aucun appel réseau) |

L'extraction non bornée de la table des réservations a été jouée en entier
aujourd'hui et a réussi : la projection de 13 colonnes reste sous le tampon de
512 octets par ligne du module (environ 89 octets mesurés), sur les 28 782
lignes et pas seulement sur l'échantillon.

### 5. La forme des données, et ce qu'elle impose aux fichiers

Première ligne réellement lue de la table des réservations :

| Champ | Valeur | Ce qu'elle apprend |
|---|---|---|
| `CARRID` | `LH` | |
| `CONNID` | `0400` | **zéros de tête** |
| `FLDATE` | `20161118` | date ABAP BRUTE, jamais formatée |
| `BOOKID` | `00000066` | **zéros de tête** |
| `CUSTOMID` | `00003372` | **zéros de tête** |
| `CUSTTYPE`, `CLASS` | `P`, `Y` | codes mono-lettre |
| `ORDER_DATE` | `20160717` | date ABAP brute |
| `FORCURAM` | `566.10` | **du TEXTE**, point décimal, jamais un décimal typé |
| `FORCURKEY`, `WUNIT` | `EUR`, `KG` | |
| `LUGGWEIGHT` | `0.0000` | |
| `CANCELLED` | *(chaîne vide)* | une colonne peut être vide sur toute la table |

Trois conséquences directes. Les valeurs sont **toutes du texte** et doivent le
rester : trois colonnes portent des zéros de tête qu'un tableur mangerait, et
deux portent des dates que le même tableur relirait comme des nombres. La
colonne d'annulation est vide pour une réservation non annulée, donc une
colonne vide n'est pas un défaut de lecture : c'est bien pourquoi la garde
compte les lignes **entièrement** vides, et pourquoi la colonne clé se déclare.
Enfin le montant arrive en texte par la table alors que la même donnée revient
en décimal typé par une BAPI : une assertion numérique convertit, elle ne
compare pas les deux représentations.

### 6. Ce canal n'a AUCUN libellé affiché, et c'est l'inverse exact de l'UI5

Les en-têtes rendus par le relevé retombent sur les noms de champs ABAP
(`PRODUCT_ID` donne `PRODUCT_ID`). Le canal ne connaît pas de titre traduit, et
il n'a pas à en connaître.

| Canal | Clés du relevé | En-tête livrable |
|---|---|---|
| RFC | noms de champs ABAP, stables et indépendants de la langue | **aucun**, sauf à en fournir un |
| écran (ALV) | identifiants techniques | titres affichés par SAP |
| UI5 | **aucun identifiant technique**, seulement des libellés traduits | les mêmes libellés |

C'est une bonne nouvelle pour la convention 3 (rien de localisé ne peut entrer
dans une assertion) et une contrainte pour le livrable : des en-têtes humains
doivent être FOURNIS par la couche métier, et ils sont alors **notre** choix de
vocabulaire, jamais une lecture de SAP. Le plan l'assume et le dit (voir « Ce
qui n'est PAS couvert », point 5).

### 7. Le refus du couple filtre et total, tel qu'il tombe

Une lecture filtrée sans total fourni est refusée **avant tout aller-retour
réseau**, et le message nomme les deux sorties honnêtes :

> Lecture FILTRÉE de SNWD_PD sans total fourni : EM_GET_NUMBER_OF_ENTRIES
> compte la table ENTIÈRE et n'accepte aucune clause de sélection, donc son
> total décrirait une autre population que la clause [...]. Les confronter
> annoncerait des lignes manquantes qui n'existent pas. Deux sorties honnêtes :
> retirer le filtre pour extraire la table entière, ou passer declared_rows=
> mesuré autrement (le $count du service OData qui projette la même table, un
> comptage d'écran SE16).

Le refus est à l'ENTRÉE et non après coup, parce qu'un refus qui constate
n'empêche rien : c'est la leçon de la garde de cible qui rougissait dans un
scénario pendant que les suivants écrivaient les fichiers du mauvais système.

### 8. Le croisement à trois canaux, mesuré

| Source | Ce qui est mesuré | Valeur |
|---|---|---|
| module de LECTURE (`RFC_READ_TABLE`) | lignes réellement rapatriées | **205** |
| module de COMPTAGE (`EM_GET_NUMBER_OF_ENTRIES`) | total serveur, sans rapatriement | **205** |
| service OData qui projette la table | `$count` | **205** |

Relevé complet obtenu en passant le total OData au lieu du module de comptage :
205 lues, 205 déclarées, 0 manquante, 0 vide, 0 sans clé, `complete = True`. La
complétude est alors prouvée **sans que le module de comptage RFC y
participe** : deux systèmes de mesure indépendants du lecteur s'accordent.

### 9. Un fait d'outillage, qui décide de la façon de jouer la campagne

Le relevé complet de la table des réservations pèse plusieurs mégaoctets une
fois sérialisé, et la frontière MCP tronque une sortie de keyword aux environs
de 1 300 caractères. **Un relevé de cette taille ne peut donc pas être inspecté
depuis une boucle d'agent** : l'extraction elle-même passe très bien par le
serveur MCP (elle a été jouée ainsi aujourd'hui, enveloppée de façon à ne pas
rendre le relevé), mais sa VÉRIFICATION ne traverse pas. La campagne se joue
par `robot`, comme les campagnes d'écran, mais pour une raison différente et
qu'il faut nommer : ici ce n'est pas le COM sur un thread étranger, c'est la
taille du relevé.

### 10. La largeur d'une ligne, et pourquoi le tampon n'était pas éprouvé

Mesuré le 2026-09-16. Le module borne la **ligne PROJETÉE** à 512 octets, pas la
table ni le nombre de lignes. La largeur cumulée d'une table se lit dans DD03L
(somme des longueurs de ses champs, entrées de structure incluse écartées) :

| Tableau | Champs | Octets par ligne | Projection complète |
|---|---|---|---|
| réservations de vol | 24 | **163** | passe, et ne PEUT pas déborder |
| catalogue des produits | 24 | **533** | **refusée** |
| partenaires commerciaux | 18 | 534 | dépasserait |
| postes de documents de modification | 16 | 782 | dépasserait |
| textes du modèle marchand | 6 | 299 | passe |
| adresses d'utilisateurs | 14 | 226 | passe |
| textes de messages | 4 | 97 | passe |

**C'est l'explication du trou.** La campagne restait sous le tampon SANS LE
VOULOIR : le tableau des réservations, celui du relevé à l'échelle, tient entier
en 163 octets, donc aucune projection de lui, même complète, ne peut déborder.
Extraire 28 782 lignes ne prouvait rien de ce refus, et le croire éprouvé aurait
été une lecture de travers. La seule table du laboratoire qui déborde est le
catalogue des produits, que la campagne connaissait déjà par le croisement à
trois canaux : aucune cible nouvelle n'a été déclarée pour la couvrir.

Refus mesuré sur la projection complète du catalogue (24 champs, 533 octets) :

| Témoin | Valeur |
|---|---|
| classe d'exception | `ABAPApplicationError` |
| code technique | **`DATA_BUFFER_EXCEEDED`** |
| identifiant de message | **`AD/E/559`** |
| paramètres du message | le nom de la table et `512` |

Le refus traverse la bibliothèque **intact**, ce qui est ce qui le rend
assertable par code : l'envelopper aurait amélioré le message au prix de
l'attribut que l'oracle lit, donc au prix de l'assertion elle-même.

### 11. L'ordre des lignes, mesuré parce qu'il n'est pas garanti

Ajouté le 2026-09-16 sur la réserve d'une revue indépendante. Le scénario 4
confronte un relevé borné au DÉBUT du relevé complet, ce qui suppose que deux
lectures indépendantes rendent les lignes dans le même ordre. Le canal n'offre
aucune clause de tri et ne garantit donc rien. Mesuré sur la table des
réservations (28 782 lignes) :

| Mesure | Résultat |
|---|---|
| trois lectures bornées à 25 lignes, jouées à la suite | identiques entre elles |
| lecture bornée à 25 contre les 25 premières de la lecture complète | identiques |
| deux lectures complètes successives | identiques |

La prémisse TIENT sur cette cible, et c'est une observation, pas une garantie du
protocole. Le scénario 4 la nomme et l'accompagne d'une assertion INDÉPENDANTE
de l'ordre (les identifiants bornés sont inclus dans ceux du relevé complet) :
le jour où l'ordre dérive, c'est l'égalité de préfixe qui tombe, l'inclusion
tient, et le message distingue une dérive d'ordre d'un défaut de troncature.

## Scénarios

Huit scénarios, le dernier ajouté le 2026-09-16 pour combler le manque du
tampon de ligne. Le relevé de la grosse table est produit UNE fois, dans le
Suite Setup, pour trois raisons : chaque scénario reste jouable seul, aucun ne
rougit en cascade sur une variable qu'un autre n'a pas posée, et surtout le
refus d'un relevé incomplet doit tomber **avant** qu'un seul fichier soit
écrit.

### 1. La cible est bien le système attendu

- **Étapes** :
  1. Sauter la campagne si le canal RFC n'existe pas sur le poste, en nommant
     laquelle des deux absences s'applique.
  2. Ouvrir le canal vers le système applicatif, sous un alias qui lui est
     propre.
  3. Lire l'identité que le système publie sur lui-même, et la confronter à la
     release ET au kernel ATTENDUS.
  4. Corroborer la release par une SECONDE source indépendante : l'inventaire
     des composants logiciels installés, à la ligne du composant de base.
- **Résultat attendu** : la release lue égale la release attendue et diffère de
  celle de la release voisine du banc ; le kernel est lu et non vide ; les deux
  sources de release concordent. Toute divergence REFUSE la cible, et aucune
  lecture n'a lieu.
- **Assertions locale-indépendantes** : des numéros de release et de kernel, un
  nom de composant logiciel. Aucun libellé, aucun texte.
- **Pourquoi la garde vit dans le Suite Setup et pas seulement ici** : rejouée
  contre l'autre conteneur, une campagne dont la garde n'est qu'un scénario
  rougit sur un test et écrit quand même les fichiers du mauvais système, sous
  des noms qui annoncent le bon. Ce scénario CONFRONTE ce que le Setup a déjà
  refusé le cas échéant.

### 2. Le tableau des réservations est lu en entier, et sa complétude est établie par une autre source que le lecteur

- **Étapes** :
  1. Mesurer le nombre de lignes que la table DÉCLARE contenir, sans en
     rapatrier aucune.
  2. Extraire le tableau des réservations en entier, sur ses treize colonnes,
     avec son contrat et sa colonne clé.
  3. Refuser le relevé s'il est incomplet, sous un plancher de lignes ET de
     colonnes, AVANT toute écriture.
  4. Journaliser le résumé du relevé, total déclaré compris.
- **Résultat attendu** : autant de lignes lues que déclarées, aucune ligne
  entièrement vide, aucune ligne sans identifiant de réservation, au moins
  treize colonnes, et un plancher de lignes largement franchi. Le total déclaré
  figure au journal **même quand il coïncide** : c'est ce qui distingue un
  journal qui prouve d'un journal qui rassure.
- **Le plancher n'est pas décoratif** : sans lui, un relevé vide confronté à un
  total de zéro satisfait toutes les égalités de la garde et passe pour complet
  (voir « Points de vigilance », point 3).
- **Ce que ce scénario ne prouve pas** : que le module de comptage dise vrai.
  Il dit seulement que deux modules DIFFÉRENTS s'accordent. Le scénario 6 va
  chercher la preuve plus loin.

### 3. Le tableau est écrit dans les cinq formats, relu et confronté

- **Étapes** :
  1. Écrire le relevé dans les cinq formats sous une marque DÉRIVÉE de
     l'identité mesurée, le sous-titre des documents portant cette identité et
     jamais le chemin de sortie.
  2. Relire les quatre formats qui se relisent, et confronter chacun ligne à
     ligne au relevé lu sur la cible.
  3. Prouver le cinquième, le seul sans lecteur, sur le document lui-même.
  4. Consigner ce que chaque format a réellement écrit.
- **Résultat attendu** : les cinq fichiers existent (quatre si le canal
  optionnel manque, annoncé et non rouge) ; aucun n'est tronqué puisque rien ne
  l'a demandé ; aucune cellule n'est coupée au rendu ; le codage du format
  texte porte sa marque d'ordre d'octets ; aucune valeur n'est altérée par
  défaut ; et les quatre formats relus portent EXACTEMENT le relevé, ligne à
  ligne.
- **Ce que la confrontation attrape ici et qui n'est pas théorique** : trois
  colonnes portent des zéros de tête et deux portent des dates brutes. Un
  retypage à l'écriture les détruirait sans que ni le nombre de lignes, ni le
  poids du fichier, ni sa relecture par un humain pressé ne bronchent.
- **Le document vectoriel à cette échelle est un test de charge, pas un
  livrable à lire** : vingt-huit mille lignes en font un document que personne
  n'ouvre. Il est produit parce que l'invariant de la campagne est
  l'intégralité ; la vue courte et lisible s'obtient en bornant le rendu, la
  troncature étant alors DEMANDÉE, annoncée dans le pied du document et portée
  par le verdict d'écriture.

### 4. Contre-épreuve sur la cible réelle : le plafond silencieux est refusé

- **Étapes** :
  1. Relire le même tableau des réservations en bornant délibérément la lecture
     à quelques lignes.
  2. CONSTATER que les lignes rendues ne portent aucun témoin : aucune ligne
     vide, aucune clé manquante, des identifiants consécutifs.
  3. Constater que le relevé se déclare pourtant incomplet, et que le nombre de
     lignes manquantes est cohérent avec le total.
  4. Vérifier que la garde partagée REFUSE ce relevé, et que son refus nomme la
     cause.
- **Résultat attendu** : les trois faits dans cet ordre. L'écart existe ; les
  lignes ne le trahissent en rien ; la garde refuse quand même. Aucun fichier
  n'est écrit à partir de ce relevé.
- **Pourquoi l'ordre des trois assertions est le scénario lui-même** : prouver
  seulement que la garde refuse laisserait croire qu'un contrôle de contenu
  aurait pu faire l'affaire. C'est l'assertion du milieu, celle qui constate
  qu'AUCUN témoin n'existe, qui justifie tout le dispositif.

### 5. Une lecture filtrée sans total mesuré est refusée avant tout appel réseau

- **Étapes** :
  1. Demander une extraction FILTRÉE du catalogue des produits sans fournir de
     total.
  2. Vérifier que l'appel est refusé, et que le refus nomme la cause (le
     compteur ignore les clauses de sélection) et les deux sorties honnêtes
     (retirer le filtre, ou fournir un total mesuré autrement).
  3. Vérifier que la seconde sortie FONCTIONNE : la même lecture filtrée, avec
     un total fourni, est acceptée.
- **Résultat attendu** : un refus immédiat, sans aller-retour réseau, dont le
  message est actionnable ; puis une acceptation dès qu'un total est fourni.
  Le refus est jugé sur sa classe d'erreur et sur la présence des remèdes,
  jamais sur sa prose complète.
- **Pourquoi ce scénario compte autant que le 4** : c'est le seul endroit où le
  canal RFC diffère vraiment des trois autres. Les autres canaux déclarent un
  total qui décrit exactement ce qu'ils ont rendu ; celui-ci offre un total qui
  décrit parfois une AUTRE population. Un plan qui ne le dirait pas laisserait
  quelqu'un apparier les deux et chercher un défaut de données là où il n'y en
  a pas.

### 6. La complétude prouvée par un TROISIÈME canal

- **Étapes** :
  1. Ouvrir le canal OData vers le MÊME système et le MÊME mandant.
  2. Compter les entités de l'ensemble qui projette le catalogue des produits.
  3. Extraire ce catalogue par le canal RFC en lui passant ce total-là, et non
     celui du module de comptage.
  4. Refuser le relevé s'il est incomplet, puis constater qu'il ne l'est pas.
  5. Recouper accessoirement le total du module de comptage avec celui d'OData.
  6. Fermer le canal OData, même sur échec.
- **Résultat attendu** : autant de lignes lues par RFC que d'entités comptées
  par OData, zéro manquante, zéro vide, zéro sans clé, relevé déclaré complet.
  Et les deux compteurs, indépendants l'un de l'autre, s'accordent.
- **Pourquoi c'est la preuve la plus forte du plan** : ni le module qui lit, ni
  le module qui compte ne participent à l'établissement du total. Trois chemins
  techniques distincts, dont un qui ne passe même pas par le protocole RFC,
  disent le même nombre.
- **Le mandant doit être le même des deux côtés** : les faire diverger
  comparerait deux populations et fabriquerait un écart qui n'existe pas. Le
  module de comptage suit le mandant de la connexion, ce qui a été vérifié.

### 7. Deux écritures de la même mesure sont identiques à l'octet près

- **Étapes** :
  1. Écrire une seconde fois, sous une autre marque, le relevé déjà écrit.
  2. Confronter les fichiers des deux passages, format par format, sur leur
     contenu et non sur leur seule taille.
- **Résultat attendu** : chaque format rend deux fichiers identiques à l'octet
  près. Aucune date, aucun chemin, aucun identifiant de run n'entre dans un
  fichier produit.
- **Ce que le déterminisme achète, et pourquoi il vaut un scénario** : il fait
  d'une différence entre deux extractions une information sur le SYSTÈME.
  Sans lui, comparer l'extraction d'aujourd'hui à celle du mois dernier ne
  distingue pas un paramètre qui a bougé d'un horodatage qui a changé. Ce
  contrôle a déjà mordu sur ce dépôt : le sous-titre d'un document y portait le
  répertoire de sortie, et deux passages dans deux dossiers rendaient des
  documents différents pendant que les autres formats restaient identiques.

### 8. Une projection plus large que le tampon de ligne est refusée par son code

Ajouté le 2026-09-16, après que le lot bibliothèque a rendu ce refus assertable
(voir « Données observées », point 10). Il comble le manque n°2 de la liste
« Ce qui n'est PAS couvert ».

- **Étapes** :
  1. Dériver du dictionnaire la projection COMPLÈTE de la table large et la
     largeur de sa ligne, plutôt que de les graver.
  2. Vérifier que cette largeur dépasse bien le tampon : sans dépassement, le
     scénario ne prouverait rien, et il se SAUTE en le disant.
  3. Constater au passage que le tableau du relevé à l'échelle tient, lui, sous
     le tampon : c'est l'explication du trou, rendue exécutable.
  4. Extraire la table large en projection complète, et juger le refus sur son
     CODE puis sur son IDENTIFIANT DE MESSAGE.
  5. Contre-épreuve : la MÊME table, lue en projection ÉTROITE, passe et rend un
     relevé complet.
- **Résultat attendu** : un refus porté par un code technique et un identifiant
  de message ABAP, aucun texte de serveur dans une assertion ; puis une lecture
  étroite acceptée sur la même table. Aucun fichier n'est écrit depuis ce chemin.
- **Pourquoi la contre-épreuve n'est pas décorative** : sans elle, le scénario
  ne distingue pas « la largeur mord » de « cette table est illisible ». Le refus
  seul est compatible avec les deux, et c'est l'acceptation de la projection
  étroite qui tranche.
- **Pourquoi la projection est dérivée et non gravée** : une release qui ajoute
  un champ doit rester couverte, et surtout la largeur devient une MESURE au lieu
  d'une supposition. Une liste gravée aurait porté la réponse dans l'énoncé.

## Keywords métier manquants

La suite ne doit citer **aucun nom de table, de champ ni de module fonction**
(convention 1). Tout ce qui suit est à ajouter par le sap-generator à
`resources/rfc_keywords.resource`, qui porte déjà le vocabulaire du canal.

**Variables à ajouter** (le vocabulaire de la cible, jamais dans la suite) :

| Nom proposé | Contenu | Pourquoi |
|---|---|---|
| `${BOOKING_TABLE}` | la table des réservations de vol | la cible du relevé à l'échelle |
| `${BOOKING_FIELDS}` | les treize champs mesurés valides | projection sous le tampon de 512 octets |
| `${BOOKING_KEY_FIELD}` | l'identifiant de réservation | la colonne qui ne peut pas être vide |
| `&{BOOKING_HEADERS}` | en-têtes humains des treize colonnes | le canal n'en fournit AUCUN (données observées, point 6) |
| `${PRODUCT_FIELDS}` | les champs du catalogue des produits | la table et sa clé existent déjà |
| `${PRODUCT_CATEGORY_FILTER}` | une clause de sélection sur la catégorie | le scénario 5 a besoin d'un filtre réel |
| `${MIN_BOOKINGS}`, `${MIN_BOOKING_COLUMNS}` | planchers | jamais le compte exact, qui est une donnée |

**Keywords à créer** :

1. `Count Declared Business Records` : le total d'une table mesuré SANS en
   rapatrier une ligne. Miroir de `Count Business Records`, et son opposé de
   méthode : celui-ci lit et compte, celui-là fait compter le serveur. Le nom
   doit porter la différence, faute de quoi les deux seront confondus à l'usage.
2. `Extract Business Records` : l'extraction générique avec son contrat, miroir
   sans écran d'`Extract Displayed Report`. Porte `declared_rows` en argument
   facultatif, c'est ce qui rend le scénario 6 possible.
3. `Extract Flight Bookings` : l'extraction NOMMÉE du tableau à l'échelle
   (table, champs, clé et en-têtes humains pris dans la couche vocabulaire).
4. `Extract Flight Bookings With Ceiling` : la même, bornée. Elle existe pour la
   contre-épreuve du scénario 4 et son nom dit qu'elle est dangereuse.
5. `Extract Product Catalogue` : l'extraction du catalogue, avec un total
   facultatif venu d'ailleurs (scénario 6).
6. `Extracting A Filtered Table Without A Total Should Be Refused` : le refus du
   scénario 5, rendu à la suite pour qu'elle en juge le contenu. Même patron
   que `Reading With An Oversized Selection Clause Should Be Refused`, déjà
   présent.
7. `Rfc Target Should Be Release` : la garde de cible (release, kernel, et
   corroboration par le composant logiciel de base). Les lectures existent
   séparément, la garde n'existe pas.

**Rien à créer ailleurs** : l'écriture des cinq formats et leur relecture
vivent déjà dans `resources/table_export_keywords.resource`, la règle de refus
dans `sapfx_common.table_extract`, et le vocabulaire OData du croisement dans
`resources/api_keywords.resource`. La campagne ne doit contenir **aucun** code
d'écriture propre à un canal : c'est le rendu concret du contrat commun, et
c'est ce qui se vérifie en la relisant.

## Points de vigilance

1. **La garde de complétude s'appelle AVANT toute écriture**, dans le Suite
   Setup, jamais dans un scénario. Un refus qui constate après coup n'empêche
   rien : sur un relevé amputé, les cinq écritures passent au vert, puisque
   comparer une lecture partielle à elle-même ne rougit jamais.
2. **La garde de cible vit au même endroit et pour la même raison.** Les deux
   conteneurs du poste partagent identifiant système et nom d'hôte.
3. **Un plancher de lignes est OBLIGATOIRE sur ce canal.** Le module de
   comptage annonce une table INEXISTANTE à zéro au lieu de la refuser. Un
   relevé vide confronté à un total de zéro franchit toutes les égalités de la
   garde et se déclare complet : seul le plancher l'arrête. C'est le seul
   endroit de la chaîne où une faute de frappe sur un nom de table produit un
   résultat vert.
4. **Ne jamais apparier un filtre et le total du module de comptage.** Le refus
   est automatique, mais un `declared_rows` fourni le contourne légitimement :
   il faut alors que le total fourni décrive bien la population FILTRÉE, et non
   la table entière.
5. **Le total et la lecture doivent décrire le même instant.** Un relevé plus
   long que le total déclaré est refusé comme un relevé plus court, et c'est
   voulu : les deux mesures ne se recouvrent pas, donc aucune ne prouve l'autre.
6. **Toutes les valeurs restent du TEXTE.** Zéros de tête, dates ABAP brutes et
   montants en texte délimité : c'est mesuré sur cette table, ce n'est pas une
   précaution de principe.
7. **Les en-têtes livrés sont un choix de la couche métier**, le canal n'en
   ayant aucun. Ils n'entrent dans aucune assertion (convention 3) ; les noms de
   champs ABAP restent les clés de lecture.
8. **Le nom des fichiers est DÉRIVÉ de l'identité mesurée**, jamais d'une
   constante : un fichier ne peut pas annoncer un système qu'il ne porte pas.
9. **Fermer le canal même sur échec, et RELIRE l'état pour le prouver.** Une
   connexion RFC orpheline est une session utilisateur restée ouverte côté
   serveur.
10. **Jouer la campagne par `robot`.** Un relevé de 28 782 lignes ne traverse
    pas la frontière MCP (données observées, point 9).
11. Conventions tenues : 1 (aucun nom de table, de champ ni de module dans la
    suite), 2 (aucune attente fixe : le canal RFC est synchrone, il n'y a rien
    à attendre), 3 (release, kernel, comptes et codes techniques ; aucun texte
    localisé), 11 (aucun mot de passe par défaut, garde qui ne mesure jamais le
    secret), 12 (le contrat et les deux keywords neufs vivent dans `src/` avec
    leurs tests hors SAP).

## Ce qui a été vérifié et comment

| Fait | Source |
|---|---|
| release 754, kernel 777, identifiant système, hôte, base, IP | **mesuré live 2026-09-16** (`RFC_SYSTEM_INFO`) |
| total de la table des réservations (28 782) et du catalogue (205) | **mesuré live**, module de comptage |
| lecture non bornée des 28 782 lignes sur 13 colonnes, en 0,885 s | **mesuré live**, extraction jouée en entier |
| signature de la troncature silencieuse (3/205 et 2/28 782, zéro témoin) | **mesuré live**, deux tables |
| forme des données (zéros de tête, dates brutes, montant en texte, colonne vide) | **mesuré live**, première ligne réellement lue |
| absence totale de libellé affiché (en-têtes retombant sur les noms ABAP) | **mesuré live** |
| refus du filtre sans total, avant tout appel réseau, et son message | **mesuré live** |
| `$count` OData du catalogue (205) et relevé complet prouvé par lui | **mesuré live**, canal OData sur le même système et le même mandant |
| fermeture effective des deux canaux | **mesuré live**, état du canal relu après fermeture |
| volumes des cinq autres tables citées | mesure du même jour, antérieure à ce plan |
| projection à 89 octets par ligne | mesure du même jour ; confirmée indirectement, la lecture complète n'ayant pas dépassé le tampon |

Deux remarques d'outillage, parce qu'elles ont coûté des appels et qu'elles
resserviront. La bibliothèque ayant été rechargée à chaud dans le serveur MCP,
le **catalogue statique de keywords est resté périmé** : une recherche par
catalogue déclare les deux keywords neufs introuvables alors qu'ils sont bien
là. C'est l'espace de noms VIVANT de la session qu'il faut interroger, et il
les rend avec leur documentation complète. Et l'extraction complète a pu être
jouée à travers MCP en l'enveloppant de façon à ne rendre qu'un statut : c'est
la seule manière d'éprouver un gros relevé sans le faire traverser.

## Ce qui n'est PAS couvert

1. **La seconde release du banc (758).** Ce plan ne vise qu'A4H. La 758 n'est
   joignable en RFC que par un relais TCP local, et rien n'a été mesuré dessus
   pour cette capacité. Elle sert ici de contre-épreuve d'identité, pas de
   cible.
2. ~~**Le dépassement du tampon de 512 octets par ligne.**~~ **Couvert le
   2026-09-16** par le scénario 8, qui provoque le refus sur la cible réelle et
   le juge par code (`DATA_BUFFER_EXCEEDED`) et par identifiant de message
   (`AD/E/559`), avec la contre-épreuve de la projection étroite. Ce qui reste
   hors périmètre est plus étroit : le refus n'est éprouvé que sur le chemin
   d'EXTRACTION, pas sur les autres lecteurs du canal, et la sortie de secours
   que le remède nomme (lire en deux projections partageant la colonne clé,
   puis recoller côté client) n'est exercée par aucun scénario d'extraction.
3. **Le module de comptage indisponible.** Sur une cible durcie, `S_RFC` peut
   le restreindre. Le message de repli existe et nomme ses remèdes ; il n'est
   pas éprouvé, le module répondant sur cette cible. Le provoquer demanderait
   de modifier des autorisations, ce qui sort de la lecture seule.
4. ~~**Une table inexistante annoncée à zéro.**~~ **Corrigé le 2026-09-16** :
   ce point était trop sévère. Le cas est couvert HORS SAP par
   `test_une_table_inexistante_passe_toutes_les_egalites_et_seul_le_plancher_mord`
   (`tests/unit/test_rfc_extract.py`), en deux temps : le relevé vide confronté
   à un total de zéro franchit d'abord TOUTES les égalités de la garde, puis
   c'est le plancher seul qui le refuse. Ce qui reste non couvert est plus
   étroit : aucun scénario ne le provoque sur la CIBLE, faute de pouvoir
   demander une table inexistante sans écrire un nom de table dans une suite.
5. **La justesse des en-têtes humains livrés.** Le canal n'en fournit aucun,
   donc ceux du fichier viennent de notre couche vocabulaire. Personne ne les
   confronte à ce que SAP affiche pour ces mêmes champs, et aucun canal ne
   permet de le faire sans ouvrir un écran.
6. **Le risque de formule dans le format texte.** L'écrivain compte les
   cellules qu'un tableur interpréterait comme une formule et la campagne les
   RAPPORTE sans rien neutraliser. Sur ce tableau précis, leur nombre n'a pas
   été mesuré avant ce plan.
7. **Un tableau métier d'un système applicatif réel.** Ce qui est prouvé porte
   sur un jeu de démonstration, à un volume réaliste mais sur une table dont
   les colonnes sont simples. Un tableau de postes de commande, avec ses champs
   longs et ses zones de texte, poserait la question du tampon autrement.
8. **La relecture des fichiers par autre chose que nos propres lecteurs**, sauf
   pour le classeur, relu par un tableur lors des campagnes voisines.

## Écarts constatés à la génération

Relevés le 2026-09-16 par sap-generator, chaque étape rejouée live sur A4H
(release 754, kernel 777, mandant 001) avant d'entrer dans la suite. Rien de ce
qui suit ne change le sens métier d'un scénario : ce sont des précisions et des
ajouts de vocabulaire, pas un flux à replanifier.

### 1. Les identifiants d'un relevé borné ne sont PAS consécutifs sur cette table

**Ce que le plan dit** : scénario 4, étape 2, « CONSTATER que les lignes rendues
ne portent aucun témoin : aucune ligne vide, aucune clé manquante, des
identifiants consécutifs ».

**Ce qui a été observé** : les identifiants de réservation des premières lignes
sont `00000066`, `00000079`, `00000093`, `00000098`. Ils sont ordonnés, mais
pas consécutifs : la table ne numérote pas ses lignes sans trou, contrairement
au catalogue des produits sur lequel la consécutivité avait été relevée. Une
assertion de consécutivité aurait échoué, et elle aurait échoué pour une raison
sans rapport avec la troncature.

**Ce que la suite fait** : elle asserte une propriété plus forte et,
surtout, indépendante de la façon dont la cible numérote ses lignes. Les lignes
bornées sont confrontées au relevé complet et doivent en être EXACTEMENT les
premières, dans le même ordre, en plus des quatre témoins habituels (zéro ligne
vide, zéro clé manquante, aucune clé vide, aucun doublon d'identifiant). La
démonstration du scénario est intacte, et même renforcée : ce n'est plus « les
lignes ressemblent à un inventaire », c'est « les lignes SONT le début exact de
l'inventaire », donc aucune inspection de contenu ne pourrait les distinguer.

### 2. Cinq keywords de plus que les sept annoncés, dont un hors du canal RFC

**Ce que le plan dit** : sept keywords à créer dans `resources/rfc_keywords.resource`,
et « Rien à créer ailleurs ».

**Ce qui a été observé** : la convention 1 (aucun nom de table dans une suite)
impose des noms métier là où le plan ne proposait que la primitive générique, et
le scénario 7 demande une comparaison de fichiers qui n'existait nulle part.

**Ce que la suite fait** : les sept keywords annoncés existent tels quels, plus
cinq (le quatrième est venu de la revue indépendante, voir l'écart 4).

| Ajouté | Où | Pourquoi |
|---|---|---|
| `Count Declared Flight Bookings` | `rfc_keywords.resource` | `Count Declared Business Records` prend une table en argument : la suite ne peut pas la citer (convention 1) |
| `Count Declared Products` | `rfc_keywords.resource` | même raison, pour le recoupement des deux compteurs du scénario 6 |
| `Count Filtered Products` | `rfc_keywords.resource` | le scénario 5 doit fournir un total à sa lecture filtrée, et le compteur serveur ne sait pas filtrer |
| `Read Installed Client Codes` | `rfc_keywords.resource` | le scénario 1 doit retrouver le mandant servi dans l'annuaire du SERVEUR, et une suite ne cite pas un nom de champ |
| `Measure Table Row Width` et ses deux noms métier | `rfc_keywords.resource` | le scénario 8 dérive du dictionnaire la projection complète ET la largeur, au lieu de les graver |
| `Extracting Beyond The Row Buffer Should Be Refused With Code` / `... With Message Id` | `rfc_keywords.resource` | le refus du tampon se provoque depuis la couche métier, la suite n'ayant à citer ni table ni champ |
| `Les Deux Ecritures Devraient Etre Identiques A L Octet Pres` | `table_export_keywords.resource` | le scénario 7 compare deux passages d'écriture, et la couche de restitution n'avait aucun keyword de confrontation de FICHIERS |

Le quatrième est délibérément placé hors du vocabulaire RFC : il ne parle
d'aucun canal, exactement comme le reste de cette couche, et il servira aux
trois autres campagnes d'extraction le jour où elles voudront la même preuve.
Deux planchers ont été ajoutés au vocabulaire pour la même raison que les deux
que le plan prévoyait (`${MIN_PRODUCTS}`, `${MIN_PRODUCT_COLUMNS}`) : la garde
du scénario 6 en réclame un aussi.

### 3. La seconde moitié du scénario 5 prouve la sortie de secours, pas une complétude

**Ce que le plan dit** : scénario 5, étape 3, « Vérifier que la seconde sortie
FONCTIONNE : la même lecture filtrée, avec un total fourni, est acceptée ».

**Ce qui a été observé** : sur ce canal, le seul total disponible pour une
population FILTRÉE vient du module qui lit, puisque le compteur serveur
n'accepte aucune clause de sélection. Asserter la complétude du relevé qui en
résulte reviendrait à comparer une lecture avec elle-même, c'est-à-dire à écrire
la garde vraie quoi qu'il arrive que tout ce plan existe pour éviter.

**Ce que la suite fait** : elle asserte que l'appel est ACCEPTÉ et que le relevé
porte bien la clause dans son libellé de provenance, et elle dit explicitement,
dans sa documentation et dans celle de `Count Filtered Products`, que cette
moitié ne prouve rien de la complétude. C'est le scénario 6 qui va chercher un
total réellement indépendant.

### 4. Trois assertions qui ne pouvaient pas échouer, relevées par la revue

Ajouté le 2026-09-16 après la revue indépendante `sap-verifier` (verdict
`needs_human`). Trois contrôles avaient la forme d'une assertion sans en avoir
la force, et une assertion qui ne peut pas échouer occupe une place tout en ne
protégeant rien.

**Le scénario 1 ne mesurait rien de neuf.** Ses quatre assertions étaient déjà
imposées mot pour mot par la garde de cible du Suite Setup, qui aurait avorté la
campagne avant elles, et l'égalité sur le mandant comparait le paramètre
d'ouverture à lui-même. Il porte désormais trois vérifications que le Setup
n'impose pas, toutes falsifiables : l'accord des DEUX sources d'identité du
canal (les attributs de la poignée de main RFC contre la fiche que le serveur
d'applications publie, deux couches différentes dont le Setup ne lit que la
seconde), la présence du mandant servi dans l'annuaire des mandants (une réponse
du serveur, là où l'égalité précédente était un miroir), et un kernel ATTENDU
optionnel. Les deux assertions de release restent, assumées en toutes lettres
comme une confrontation de ce que le Setup a refusé.

**Le mandant du scénario 6 était tautologique.** Le mandant relu est celui que
l'ouverture du canal OData a mémorisé, ouverture qui avait reçu celui de la
connexion RFC : l'égalité ne pouvait pas échouer, alors que sa documentation
prétendait empêcher une comparaison truquée. Elle dit maintenant ce qu'elle
vérifie vraiment (que les deux canaux ont été CONFIGURÉS sur le même mandant,
ce qui attrape une surcharge de variable incohérente et rien de plus), et la
preuve du scénario est nommée pour ce qu'elle est : l'accord des trois nombres,
trois chemins techniques distincts n'ayant aucune raison de tomber sur le même
total en lisant des populations différentes.

**La prémisse d'ordre du scénario 4 n'était pas mesurée.** Elle l'est
désormais, et consignée en « Données observées », point 10. L'égalité de préfixe
est conservée et doublée d'une assertion indépendante de l'ordre.

### 5. Un huitième scénario, et la raison pour laquelle le trou existait

Ajouté le 2026-09-16. Le plan livré ne portait que sept scénarios et rangeait le
dépassement du tampon de ligne dans « Ce qui n'est PAS couvert », en le
qualifiant de manque le plus sérieux de la liste. Il l'était, et sa cause valait
d'être nommée : la campagne restait sous le tampon **sans le vouloir**, parce
que le tableau qu'elle extrait tient entier en 163 octets par ligne et ne peut
donc pas déborder, quelle que soit la projection. Ce n'était pas une prudence,
c'était une impossibilité, et la prendre pour une couverture aurait été une
lecture de travers.

Le scénario 8 le provoque sur la seule table du laboratoire qui déborde, le
catalogue des produits (533 octets), que la campagne connaissait déjà : aucune
cible nouvelle n'a été déclarée. La projection complète et la largeur sont
dérivées du dictionnaire, la prémisse de dépassement est mesurée (et fait SAUTER
la branche là où elle ne tient pas), le refus est jugé par code et par
identifiant de message, et la contre-épreuve de la projection étroite distingue
« la largeur mord » de « cette table est illisible ». Le point 2 de « Ce qui
n'est PAS couvert » a été réduit à ce qui reste vraiment hors périmètre.

### 6. Ce qui a été confirmé sans écart

Tout le reste du plan s'est vérifié à l'identique : 28 782 lignes déclarées et
lues sur treize colonnes, 205 des trois côtés du croisement, release 754 et
kernel 777, la forme de la première ligne (zéros de tête, dates ABAP brutes,
montant en texte, colonne d'annulation vide), l'absence totale de libellé
affiché, le message de refus du couple filtre et total, et la fermeture
effective des deux canaux relue après coup. Les cinq formats ont été écrits (le
canal optionnel répondait), pour 36 249 495 octets par passage, et les deux
passages sont identiques à l'octet près.

## Ancrage de la suite sur ce plan

Le plan est la source de vérité. Une fois la suite générée, elle porte son
marqueur de provenance :

```
python scripts/check_spec_sync.py --stamp tests/robot/api/extraction_tableau_rfc_a4h.robot specs/extraction-tableau-canal-rfc-a4h.md
```

Ensuite la règle ordinaire s'applique : toute évolution passe par le plan, puis
par une régénération ou un re-stampage assumé, jamais par une édition
silencieuse de la suite.
