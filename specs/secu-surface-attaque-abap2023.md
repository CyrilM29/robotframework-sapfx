# Surface d'attaque par le canal RFC (cible ABAP Platform 2023)

- **Canal** : RFC (`SapApiLibrary`, `pyrfc`), le canal sans écran et sans HTTP.
  Aucun écran n'est piloté, aucune requête HTTP n'est émise.
- **Système observé** : ABAP Platform 2023 en conteneur, release **758**,
  kernel **793**, mandant `001`, utilisateur `DEVELOPER`, langue `EN`. Cible
  jointe à travers un **relais TCP local** (`127.0.0.2`), qui réaligne le port
  et le numéro d'instance.
- **Exploration live** : 2026-09-14, en cinq passes de sondes, environ cent
  lectures, zéro écriture. Les capacités manquantes ont été livrées dans
  `src/` avant l'écriture de ce plan (convention 12), puis éprouvées en direct
  contre la cible.
- **État de ce plan** : écrit APRÈS l'exploration. Il formalise ce qui a été
  mesuré, il ne décrit pas une intention.
- **Posture** : LECTURE SEULE de bout en bout. Aucun paramètre n'est écrit,
  aucun compte touché, aucune destination ouverte, aucun secret lu, aucune
  commande exécutée.

## Pourquoi une campagne de plus sur une cible déjà couverte

`specs/secu-configuration-abap2023.md` couvre la **configuration** de sécurité
de cette même cible, en seize scénarios validés. Sa section « Ce qui n'est PAS
couvert » liste dix zones, et c'est le point de départ d'ici : cette campagne
ne répète aucun de ses contrôles, elle attaque ce qu'elle laissait dehors.

La différence tient en une phrase. La campagne de configuration lit **ce que le
système déclare** : des paramètres de profil, des comptes livrés, des
destinations déclarées. Celle-ci lit **ce qui est réellement atteignable** :
quels comptes peuvent entrer, quels services répondent, quelles commandes
peuvent s'exécuter, ce que le journal d'audit a réellement enregistré.

Les deux ne coïncident pas, et les quatre écarts mesurés le 2026-09-14 sont la
matière de cette campagne. Chacun est un cas où une lecture naïve conclut
quelque chose d'exact et de trompeur.

## Le parti pris de jugement

Identique à celui de la campagne jumelle, et pour les mêmes raisons : une
campagne rejouable ne juge pas « ce système est-il durci » (jugement qui dépend
d'une politique d'entreprise, faux sur un bac à sable, et qui produit un verdict
permanent que personne ne relit). Trois régimes :

1. **ASSERTÉ** : les contrôles dont l'écart serait un incident quelle que soit
   la politique, et les **assertions de non-dérive** (une valeur mesurée dont
   le changement est l'événement à voir) ;
2. **RAPPORTÉ** : tout ce qui est mesuré sans être jugé ;
3. jamais de contrôle qui exigerait de ce banc une posture de production, parce
   qu'une suite rouge en permanence finit désactivée.

Chaque scénario dit lequel il applique.

## Préconditions

1. **Le relais TCP local doit être levé AVANT toute exécution.** Le piège est
   le même qu'en configuration, et il est majeur : sans relais, l'adresse
   visée répond quand même (la boucle locale couvre toute sa plage et l'autre
   conteneur écoute partout), donc la campagne mesurerait la release 754 en
   croyant auditer la 758. Les deux conteneurs annonçant le même identifiant
   système et le même nom d'hôte applicatif, rien dans la réponse ne le
   trahirait. Le scénario 1 existe pour attraper exactement cela.
2. **Interpréteur Python 3.10 à 3.12** portant `pyrfc`, et un runtime NW RFC.
   Le canal est **optionnel** : sur un poste sans lui, la campagne se SAUTE.
3. **Identifiants par la ligne de commande** (convention 11).
4. **La campagne lit le mandant de connexion** (`001`). Le mandant `000` a été
   sondé et n'est PAS accessible avec ces identifiants : voir « Ce qui n'est
   pas couvert ».

## Données observées

Tout ce qui suit est mesuré le 2026-09-14 sur la cible décrite plus haut.

### 1. Comptes : verrouillé et utilisable sont deux questions

| Mesure | Valeur |
|---|---|
| comptes du mandant `001` | 6 |
| comptes **verrouillés** | **0** |
| comptes **inutilisables** | **2** (`DEVELOPER_5`, `SDMI_DLRYYAU`) |
| cause | date de fin de validité au **31/12/2024**, échue depuis vingt mois |
| comptes réellement utilisables | **4** (`BWDEVELOPER`, `DDIC`, `DEVELOPER`, `SAP*`) |
| version de hachage des mots de passe | `H` pour les six |

C'est l'écart fondateur de cette campagne. La campagne de configuration lit le
masque de verrouillage et rapporte « aucun compte verrouillé » : c'est exact,
et cela laisse croire que six comptes sont ouverts quand quatre le sont. Les
deux lectures répondent à deux questions différentes et ne sont pas
interchangeables.

La version de hachage vaut `H` partout, la forme moderne. Une version plus
ancienne (`B`, `D`, `F`) signalerait des empreintes faibles conservées, ce qui
serait un incident indépendant de toute politique.

### 2. Exposition web : déclaré n'est pas servi

| Mesure | Valeur |
|---|---|
| noeuds de services déclarés | 3410 |
| services **actifs** | **219** |
| ratio d'exposition | 6,4 % |
| noeuds actifs **appariés** à leur fiche descriptive | **219** (aucun orphelin) |
| actifs **sans chiffrement** | **219**, soit tous |
| actifs portant un **compte de service** | **0** |
| hôtes virtuels | 2 (`DEFAULT_HOST` en HTTP, `SAPCONNECT` en SMTP) |
| services sensibles actifs | `bsp`, `gui`, `its`, `nwbc`, `public`, `ui2`, `webgui` |

Le drapeau d'activation et le nom lisible vivent dans **deux tables
différentes**, jointes par l'identifiant de noeud. Lire la seule table des
services donne 3410 noeuds sans savoir lesquels répondent, soit une surface
seize fois trop grande pour être auditée.

**Le décompte d'appariements n'est pas décoratif, et il a été ajouté après
coup.** Les deux premiers chiffres du tableau viennent tous deux de la table
d'activation : comparer « actifs » et « déclarés » ne dit donc RIEN de la
seconde table. Si l'appariement se casse, le résumé garde exactement la même
forme, avec des noms repliés sur l'identifiant de noeud, aucun compte de
service et aucun service sensible, soit la signature d'un système sain. Seul
`matched` distingue les deux situations, et c'est la revue indépendante qui
l'a fait remarquer : la première version de cette campagne croyait vérifier la
jointure en comparant deux nombres issus de la même lecture.

`webgui` est actif, ce qui vaut d'être noté : c'est le service visé par la note
SAP 3747367 (CVSS 9.9). La campagne le CONSTATE et ne le juge pas, l'activation
étant délibérée sur ce banc.

Aucun service actif ne porte de compte de service : c'est un résultat mesuré,
et c'est la propriété la plus intéressante de cet inventaire, puisqu'un tel
service s'exécuterait sans authentifier son appelant.

### 3. Commandes du système d'exploitation

| Mesure | Valeur |
|---|---|
| commandes déclarées | 117 |
| acceptant des **arguments additionnels** | **109** |
| figées | 8 |
| définies sur le système (espace de noms client) | **0** |
| systèmes d'exploitation déclarés | 7 formes, dont `ANYOS` (58) et `UNIX` (22) |

La distinction qui porte le sens : une commande dont l'appelant peut compléter
les arguments à l'exécution n'offre pas la même surface qu'une commande figée.
C'est l'écart entre « exécuter une sauvegarde » et « exécuter ce que l'appelant
voudra ».

Aucune commande n'est définie sur le système : les 117 sont livrées par SAP.
L'apparition d'une commande client est exactement l'événement que le scénario 7
existe pour voir.

### 4. Couverture d'audit : le constat qui remplace une déduction

| Mesure | Valeur |
|---|---|
| journal armé (`rsau/enable`) | `1` |
| journal intègre (`rsau/integrity`) | `1` |
| emplacements de filtrage déclarés | 10 |
| emplacements **actifs** | **0** |
| **entrées lues** sur 7, 365 et 1500 jours | **0** |
| **fichiers de journal vus** | **0** |
| verdict croisé | `armed_without_filter_and_silent` |

La campagne de configuration établissait « armé sans filtre » et en **déduisait**
que le journal n'enregistre rien. La lecture du journal lui-même le
**constate** : zéro entrée et zéro fichier, sur un an comme sur quatre.

C'est le faux positif de conformité le plus coûteux de ce domaine : un lecteur
du seul paramètre conclut « audit actif », et aucun incident de sécurité de ces
quatre années n'est reconstituable.

### 5. Relations de confiance RFC

| Mesure | Valeur |
|---|---|
| systèmes de confiance entrants | **0** |
| systèmes de confiance sortants | **0** |
| entrées de la liste blanche des rappels | **2** |

Aucune relation de confiance n'est configurée. Ce vide est un **résultat**, et
il n'était vu par aucune suite : sans cet inventaire, on ne distingue pas
« aucune relation n'est configurée » de « personne n'a regardé », et seule la
première situation rend visible l'apparition d'une relation.

### 6. Autorisations

| Objet | Lignes de rôle le portant |
|---|---|
| `S_TCODE` | 6336 |
| `S_RFC` | 5311 |
| `S_DEVELOP` | 4068 |
| `S_TABU_DIS` | 3374 |
| `S_ADMI_FCD` | 549 |
| `S_USER_GRP` | 351 |
| `S_LOG_COM` | 190 |
| `S_RFCACL` | 127 |

Total : 60793 lignes de rôle, pour **9 attributions effectives** seulement,
toutes sur des rôles de l'espace de noms client et **toutes sans échéance**. La
distinction compte : un rôle DÉFINI n'est pas un rôle ATTRIBUÉ, et lire l'un
pour l'autre surestime massivement.

La liste des mots de passe interdits compte **0 entrée** : aucun mot de passe
trivial n'est refusé par le système.

## Scénarios

Douze scénarios. Chacun indique ce qu'il **ASSERTE** et ce qu'il **RAPPORTE**.

### 1. La cible est bien celle que la campagne croit auditer

- **Étapes** : ouvrir le canal sur l'adresse du relais, lire l'identité publiée.
- **ASSERTE** : la release et le kernel sont ceux de cette cible, et la release
  lue **n'est pas** celle du conteneur voisin.
- **Pourquoi en premier** : sans relais, l'adresse répond quand même et c'est
  l'autre conteneur qui parle. Les onze scénarios suivants seraient alors
  verts et décriraient la mauvaise machine. L'échec doit nommer le relais en
  premier, c'est la cause la plus probable.

### 2. Un compte non verrouillé n'est pas forcément utilisable

- **Étapes** : lire la surface des comptes du mandant, puis journaliser.
- **ASSERTE** : la liste des comptes utilisables est celle mesurée, et la liste
  des inutilisables aussi, avec leur cause (`expired`). Assertion de
  non-dérive : l'apparition d'un compte utilisable de plus est l'événement à
  voir.
- **RAPPORTE** : chaque fiche avec son statut, son groupe et sa dernière
  connexion.
- **Pourquoi ce scénario est le coeur de la campagne** : c'est l'écart
  fondateur. Zéro compte verrouillé et deux comptes inutilisables cohabitent,
  et une campagne qui ne lit que le verrouillage rapporte une surface d'entrée
  de six comptes là où elle est de quatre.

### 3. Les empreintes de mots de passe sont toutes au format moderne

- **Étapes** : reprendre la surface déjà lue, en extraire les versions de
  hachage.
- **ASSERTE** : aucun compte ne porte une version d'empreinte ancienne.
- **RAPPORTE** : la répartition des versions.
- **Pourquoi bloquant** : une empreinte ancienne conservée est cassable hors
  ligne, et cela ne dépend d'aucune politique d'entreprise.

### 4. La liste des mots de passe interdits est mesurée, pas supposée

- **Étapes** : compter les entrées de la liste.
- **ASSERTE** : la lecture aboutit (un entier est rendu).
- **RAPPORTE** : le décompte, zéro sur cette cible.
- **Pourquoi RAPPORTÉ et non asserté** : asserter zéro graverait une faiblesse
  comme une cible, et exiger un minimum rendrait la suite rouge à vie sur ce
  banc. Ce qui compte est que la mesure existe.
- **Le piège fermé ici, et la preuve qu'il l'est** : cette table n'a pas de
  colonne d'utilisateur. Son contrat de champs a été RELEVÉ au dictionnaire de
  la cible le 2026-09-14, et il vaut exactement `BCODE` (clé) et
  `CASESENSITIVE` : c'est ce qui est projeté. La colonne plausible `BNAME` a
  d'ailleurs été essayée pendant l'exploration et a échoué en « table sans
  donnée ».
- **Ce qui rend la lecture auto-vérifiante**, et c'est le point que la revue
  indépendante ne pouvait pas voir sur pièces : une projection sur un champ
  inexistant ne rend PAS zéro en silence, elle fait ÉCHOUER la lecture (le
  refus remonte en exception). Le scénario ne peut donc pas passer au vert sur
  une colonne fausse. Le zéro rapporté ici est bien une mesure.

### 5. La surface web servie n'est pas la surface déclarée

- **Étapes** : lire l'exposition web, puis journaliser l'inventaire.
- **ASSERTE** : le nombre de services actifs est celui mesuré (assertion de
  non-dérive) ; **aucun noeud actif n'est orphelin** de sa fiche descriptive ;
  et au moins un service sensible est reconnu par son nom lisible.
- **RAPPORTE** : le ratio d'exposition, les hôtes virtuels, les services
  sensibles actifs.
- **Pourquoi ces trois assertions et pas une comparaison de nombres** : la
  première version de ce scénario vérifiait que les actifs étaient moins
  nombreux que les déclarés, en croyant ainsi prouver la jointure. C'était
  faux, et la revue indépendante l'a relevé : les deux nombres viennent de la
  MÊME table, donc la comparaison est vraie dès qu'un noeud est inactif,
  jointure réussie ou non. Les deux dernières assertions mesurent la jointure
  elle-même, et elles comptent parce que le scénario 6 en dépend entièrement.

### 6. Aucun service actif ne s'exécute sans authentifier son appelant

- **Étapes** : reprendre l'exposition, isoler les services à compte de service.
- **ASSERTE** : la liste est vide, **et la jointure a bien eu lieu**.
- **RAPPORTE** : le nombre d'actifs sans chiffrement (tous, sur ce banc HTTP).
- **Pourquoi bloquant dans un sens seulement** : un service qui porte un compte
  de service répond sans demander d'identifiant, ce qui est un chemin d'entrée
  indépendant de toute politique. Le chiffrement, lui, est seulement rapporté :
  l'exiger sur un banc en HTTP rendrait la suite rouge à vie.
- **Pourquoi le rappel de la jointure** : sans elle, ce champ serait vide par
  construction et le scénario se vérifierait tout seul. C'est le mode de panne
  le plus traître de cette campagne, puisqu'il produit exactement le résultat
  espéré.

### 7. Aucune commande du système d'exploitation n'a été ajoutée

- **Étapes** : lire l'inventaire des commandes externes, puis journaliser.
- **ASSERTE** : aucune commande de l'espace de noms client n'est déclarée, et
  l'inventaire n'est pas vide (vraisemblance).
- **RAPPORTE** : le total, le nombre acceptant des arguments additionnels, la
  répartition par système d'exploitation.
- **Pourquoi ce régime** : les 117 commandes livrées sont un standard, les
  juger n'aurait pas de sens. Une commande ajoutée sur le système, elle, ne
  vient d'aucun standard, et son apparition est exactement ce que ce contrôle
  existe pour voir.
- **Pourquoi le total n'est PAS gravé**, alors qu'il l'était dans la première
  version : la revue indépendante a relevé l'incohérence avec le scénario 10,
  qui refuse de graver ses décomptes pour cette raison exacte. Le total des
  commandes LIVRÉES bouge avec un lot de correctifs SAP sans porter la moindre
  information de sécurité ; le graver aurait rendu la suite rouge sur une mise
  à jour normale, mécanisme par lequel une suite finit désactivée.

### 8. Le journal d'audit est armé, et il n'enregistre rien

- **Étapes** : croiser la configuration du journal et son contenu sur une
  fenêtre d'un an, puis journaliser le constat.
- **ASSERTE** trois choses : le verdict croisé est celui mesuré
  (`armed_without_filter_and_silent`) ; la lecture a bien EU LIEU (le nombre
  d'entrées n'est pas « non mesuré ») ; et le verdict est cohérent avec ses
  décomptes.
- **RAPPORTE** : les emplacements déclarés et actifs, les entrées et fichiers
  vus, la note explicative.
- **Pourquoi ce scénario est le complément indispensable de son voisin en
  configuration** : celui-là établit que le journal est armé sans filtre et en
  déduit qu'il n'enregistre rien ; celui-ci le constate. La deuxième assertion
  est la plus importante des trois : **une lecture qui échoue ne doit jamais
  valoir zéro**, sans quoi « je n'ai pas su lire » passerait pour « le journal
  est vide », qui est précisément la conclusion recherchée. Le module de
  lecture rend d'ailleurs zéro entrée sans erreur quand on l'appelle mal.
- **Le même piège, déplacé d'un cran**, relevé par la revue indépendante : la
  première version ne reconnaissait l'échec qu'à une EXCEPTION. Une réponse
  vide ou de forme inattendue (module renommé sur une autre release, refus
  rendu sans exception) donnait donc zéro entrée et « lecture réussie », soit
  le verdict de silence recherché, obtenu sans rien lire. Le keyword vérifie
  désormais que la réponse porte bien ses tables de sortie.

### 9. Aucune relation de confiance RFC n'est configurée

- **Étapes** : inventorier les confiances entrantes, sortantes, et la liste
  blanche des rappels.
- **ASSERTE** : zéro relation entrante, zéro sortante, et le nombre d'entrées
  de la liste blanche est celui mesuré. Assertions de non-dérive.
- **RAPPORTE** : les destinations de la liste blanche.
- **Pourquoi asserter un vide** : une destination ou une confiance qui apparaît
  est un chemin d'élévation vers un autre système, et l'apparition est
  exactement l'événement à voir. **Le piège fermé ici** : la table des
  confiances entrantes n'a pas la colonne d'identifiant système qu'on lui
  suppose, et la demander fait échouer la lecture par un code qui accuse la
  table d'être vide. La conclusion « aucune relation » se trouverait être
  exacte, ce qui rend l'erreur invisible.

### 10. L'empreinte des objets d'autorisation critiques est mesurée

- **Étapes** : compter les lignes de rôle portant chaque objet critique.
- **ASSERTE** : l'appel distant et l'accès aux tables ont une empreinte **non
  nulle**. Garde de vraisemblance, pas de conformité : zéro ligne pour
  `S_RFC` sur un système ABAP signale une lecture douteuse bien plus
  probablement qu'un système exemplaire.
- **RAPPORTE** : l'empreinte de chaque objet.
- **Pourquoi pas d'assertion de valeur** : ces chiffres bougent avec le moindre
  rôle livré par un correctif, et les graver rendrait la suite rouge sur une
  évolution normale.

### 11. Les attributions de rôles effectives sont inventoriées

- **Étapes** : lire les attributions du mandant, puis journaliser.
- **ASSERTE** : l'inventaire n'est pas vide (vraisemblance), et le nombre
  d'attributions est celui mesuré (non-dérive).
- **RAPPORTE** : les attributions par utilisateur, et celles sans échéance.
- **Complémentarité avec le scénario 10** : celui-là mesure ce que les rôles
  DÉFINIS contiennent, celui-ci ce qui est réellement ATTRIBUÉ. 60793 lignes
  de rôle pour 9 attributions : lire l'un pour l'autre surestime d'un facteur
  qui ne veut plus rien dire.

### 12. La surface tient dans un artefact rejouable

- **Étapes** : assembler les mesures des scénarios précédents en un artefact
  déterministe, l'écrire, le relire et vérifier son empreinte.
- **ASSERTE** : le périmètre d'empreinte est celui déclaré ; l'artefact relu
  porte son empreinte ; et **changer la date de lecture ne change pas
  l'empreinte**, contre-épreuve JOUÉE dans le run.
- **RAPPORTE** : le chemin de l'artefact.
- **Pourquoi** : c'est ce qui rend la campagne comparable entre deux passages
  et entre deux cibles, sur le patron de l'inventaire DDIC et du registre de
  capacités.
- **Le défaut que deux exécutions le même jour ne pouvaient pas révéler**, et
  c'est la plus subtile des réserves de la revue indépendante : la date de
  lecture des comptes entrait dans le périmètre haché. Les deux premières
  validations ont donc produit la même empreinte en semblant prouver le
  déterminisme, alors que le même relevé rejoué le lendemain aurait été
  déclaré divergent. La date est désormais rattachée à la CIBLE, hors
  périmètre, et le scénario joue la contre-épreuve au lieu de l'affirmer.

## Points de vigilance pour la génération

Les cinq pièges relevés pendant l'exploration. Tous produisent un résultat
**plausible** plutôt qu'une erreur visible, ce qui est la raison pour laquelle
ils sont écrits ici plutôt que laissés à la sagacité du lecteur.

1. **Le lecteur du journal d'audit ne vérifie pas son paramètre obligatoire.**
   Appelé sans intervalle, il rend zéro entrée et zéro fichier sans rien lever.
   Ce zéro est indiscernable d'une mesure. Et la structure attend `DAT_FROM` et
   non `DATE_FROM` : l'orthographe plausible échoue côté client, sans jamais
   atteindre le système. Encodé dans le keyword, qui compose l'intervalle
   lui-même.
2. **Un champ inexistant fait accuser la table.** Trois lectures ont échoué en
   « table sans donnée » pendant l'exploration alors que les tables étaient
   pleines : c'est la colonne demandée qui n'existait pas. Une table de 3417
   lignes a ainsi été déclarée vide. Toujours établir le contrat de champs sur
   la cible avant de projeter.
3. **Une lecture qui échoue ne vaut jamais zéro.** Encodé dans le verdict de
   couverture d'audit, qui garde `not_measured` distinct de tout verdict de
   silence.
4. **Les services web demandent deux tables.** L'activation d'un côté, le nom
   de l'autre. Une seule ne donne rien d'auditable.
5. **Sans le relais TCP, la cible répond quand même**, et c'est l'autre
   conteneur qui parle. Aucune erreur, un rapport complet, cohérent et faux.

Autres exigences de génération :

- **Convention 1** : aucun nom de table, d'objet d'autorisation ni de motif de
  service dans la suite. Ils vivent dans
  `resources/security_keywords.resource` ; les ATTENTES vivent dans la suite,
  parce qu'elles sont propres à la cible.
- **Convention 3** : aucun jugement sur un texte localisé.
- **Convention 11** : mot de passe par variable typée en ligne de commande.
- **Convention 12** : les huit capacités de cette campagne sont dans `src/`
  avec leurs tests hors SAP, pas dans un calcul improvisé dans la suite.
- **Opt-in par tag et saut propre** quand le canal RFC n'existe pas.
- **Lecture seule stricte.**

## Revue indépendante

La campagne a été relue par `sap-verifier` après sa première validation live
(12/12, deux exécutions). Verdict initial : **`needs_human`**, avec huit
réserves. Cinq portaient sur des défauts réels, toutes corrigées puis rejouées
live (12/12), et les trois plus importantes n'auraient pas pu être trouvées en
exécutant la suite, puisqu'elle passait.

| Réserve | Nature | Traitement |
|---|---|---|
| La garde de jointure des services web ne mesurait rien (deux nombres issus de la même table) | défaut réel, et le scénario 6 en dépendait entièrement | décompte d'appariements ajouté dans la bibliothèque (`matched`/`unmatched`), trois assertions refaites, deux tests hors SAP dont une contre-épreuve « jointure cassée = système sain » |
| Le verdict d'audit acceptait une réponse vide ou de forme inattendue | défaut réel, même piège déplacé d'un cran | le keyword vérifie que la réponse porte ses tables de sortie, deux tests hors SAP |
| La date de lecture entrait dans le périmètre haché | défaut réel, invisible à deux exécutions du même jour | date rattachée à la cible, hors périmètre, et contre-épreuve JOUÉE dans le scénario 12 |
| Le total des commandes livrées était gravé | incohérence avec le scénario 10 | assertion retirée, remplacée par une garde de vraisemblance |
| Deux noms d'objets d'autorisation dans la suite | convention 1 | promus en variables de la resource |
| Accès direct à la clé `expired` | lèverait une erreur technique le jour où la campagne aurait quelque chose à dire | lecture avec défaut |
| Doublons d'assertions cosmétiques | gonflait l'apparence de couverture | retirés |
| Contrat de champs de `USR40` non prouvé sur pièces | affirmation non vérifiable par un relecteur | relevé de dictionnaire inscrit au scénario 4, avec l'argument qui rend la lecture auto-vérifiante |

Deux remarques de la revue sont des **arbitrages assumés** et non des défauts :
le couplage entre scénarios par variables de suite (patron déjà en usage dans
les registres de capacités du dépôt, au prix qu'un scénario ne se rejoue pas
seul), et l'absence de sidecar de preuves au moment de la revue, comblée
depuis.

## Ce qui n'est PAS couvert

Consigné pour qu'aucune absence de mesure ne passe pour une absence de
problème.

1. **Le mandant `000`.** Sondé pendant l'exploration : l'ouverture de session y
   est REFUSÉE avec les identifiants de la campagne. L'état de ses comptes
   n'est donc pas mesuré, et ce n'est pas un oubli mais une limite constatée.
   Elle demanderait des identifiants propres à ce mandant.
2. **Le contenu des listes de contrôle de la passerelle.** Les chemins des
   fichiers sont déclarés et lus (`/usr/sap/A4H/SYS/global/secinfo` et
   `/usr/sap/A4H/D00/data/reginfo`), mais aucun module de lecture de fichier
   n'est appelable à distance sur cette release : les trois candidats sondés
   sont absents. Une liste de contrôle déclarée mais permissive passerait donc
   le contrôle. C'est une limite du CANAL, pas un choix.
3. **Les droits effectifs.** La campagne mesure l'empreinte des objets
   critiques dans les rôles définis et le nombre d'attributions ; elle
   n'analyse ni les valeurs de champs d'autorisation, ni les droits réellement
   obtenus par un utilisateur donné.
4. **Le contenu des entrées du journal d'audit.** La campagne mesure combien
   il y en a (zéro) et n'en lit aucune. Sur un système qui enregistrerait
   vraiment, il faudrait décider quoi asserter, ce qui est un autre sujet.
5. **La liste noire des modules appelables à distance.** Le plan de la campagne
   de configuration annonce 9010 lignes sur cette cible contre 524 sur la
   jumelle, et la désigne comme son seul candidat d'extension restant. **Cette
   table n'a pas été retrouvée** : aucune table du dictionnaire dont le nom
   évoque une liste noire ne porte ce volume, et la recherche élargie n'a
   ramené que des tables sans rapport. Ce qui EXISTE et a été mesuré à la
   place : une liste blanche de rappels RFC (2 entrées) et l'inventaire de
   connectivité unifiée (1873 services RFC, dont 344 et 39 portent une portée
   déclarée). Le chiffre du plan voisin reste donc **non reproduit**, et il est
   signalé ici plutôt que confirmé par complaisance.
6. **Les marqueurs d'options de destination non établis** (limite déjà
   consignée par la campagne de configuration, inchangée).
7. **Le lien entre un service web actif et ce qu'il expose réellement.** La
   campagne compte les services actifs et lit leurs propriétés déclarées ; elle
   n'appelle aucune URL et ne vérifie pas ce qu'un appel anonyme obtiendrait.
   C'est le canal web qui répondrait à cette question, pas celui-ci.
