# Extraire un tableau SAP vers cinq formats, sur les cinq cibles du banc

- **Canaux** : l'**ÉCRAN** (SAP GUI Scripting, `SapEccLibrary`), le **WebGUI**
  (SAP GUI for HTML via ITS, moteur `sid` de `SapFioriLibrary`) et l'**UI5**
  (Fiori Elements, moteurs de contrôle de `SapFioriLibrary`). Trois canaux,
  cinq cibles, un seul geste d'écriture.
- **Cibles observées** : A4H (ABAP Platform 1909, release **754**, kernel
  **777**, mandant `001`), ABAP Platform 2023 (release **758**, kernel **793**,
  mandant `001`), les services WebGUI de ces deux mêmes systèmes, et
  l'application `cap-sflight` servie en local sur le port 4004.
- **Exploration live** : le canal écran et les deux cibles WebGUI ont été
  mesurés par une exécution `robot` du 2026-09-15 (6/6, 535 s), et non par une
  exploration MCP : piloter le COM depuis un thread étranger rend des
  perceptions vides en PASS, donc l'écran ne se sonde pas depuis le serveur
  MCP. Les cibles WEB ont été re-mesurées le 2026-09-15 par le serveur MCP,
  en lecture seule et sans jamais s'authentifier (voir « Ce qui a été vérifié
  et comment »).
- **État de ce plan** : écrit **APRÈS** la suite, ce qui est un écart assumé au
  cycle plan puis génération. La campagne
  `tests/robot/cross/extraction_multi_cibles.robot` existait et était validée
  avant ce document ; celui-ci formalise ce qui a été mesuré pour que le plan
  redevienne la source de vérité et que `scripts/check_spec_sync.py` puisse
  ancrer la suite dessus. Aucune ligne de ce plan n'anticipe un comportement :
  tout y est soit mesuré, soit nommé « à vérifier ».
- **Posture** : LECTURE SEULE de bout en bout. Aucune donnée écrite dans aucun
  système, aucune transaction de modification ouverte. Les seuls effets de bord
  sont des fichiers dans le répertoire de sortie du run et des sessions
  ouvertes puis refermées.

## Pourquoi cette campagne plutôt qu'une de plus

Le dépôt porte déjà une extraction par canal. Chacune prouve que la capacité
marche là où elle a été écrite, et aucune ne pose la question qui compte
vraiment pour une capacité transverse : **tient-elle quand on change de canal
ET de système sans rien changer d'autre que des variables ?**

Trois choses ne peuvent se voir qu'en séquence :

| Question | Invisible d'un run isolé | Tranchée ici par |
|---|---|---|
| La règle de refus d'un relevé amputé vaut-elle pour les trois canaux ? | chaque suite ne connaît que son canal | les cinq cibles passent par la MÊME garde |
| Une cible qui tombe emporte-t-elle les suivantes ? | un run mono-cible n'a pas de suivante | chaque cible possède son canal, ouverture et fermeture comprises |
| Un dossier de sortie plein prouve-t-il une campagne complète ? | jamais posé | le scénario de bilan, qui refuse un bilan incomplet |

## Perception métier

- **Personas** : `@basis` (le domaine : paramètres de profil, table de messages,
  dictionnaire), croisé avec les trois personas de canal `@ecc`, `@fiori`
  (le WebGUI et l'UI5 relèvent tous deux d'elle) et, par contraste,
  aucune persona applicative : il n'y a ici ni commande, ni pièce, ni document.
  C'est une campagne de **restitution**, pas de processus.
- **Où se lit la vérité** : pas dans le fichier produit, et c'est tout le
  sujet. Elle se lit dans ce que la SOURCE déclare contenir, et chaque canal
  le déclare ailleurs : le compte de lignes de la grille ALV côté écran
  (vérifié live), le total publié par la grille dans son attribut de données
  côté WebGUI (vérifié live), la longueur du binding côté UI5 (vérifié live,
  4133 pour 30 lignes rendues). Un fichier ne prouve jamais sa propre
  complétude : il se confronte au total déclaré par la source, puis il se
  RELIT et se confronte au relevé.
- **Risques métier priorisés**, dans cet ordre :
  1. **l'extrait présenté comme un inventaire.** Le risque dominant, et le
     seul qui produise un livrable parfaitement crédible et faux. Deux canaux
     sur trois ne laissent aucune trace de l'amputation ;
  2. **l'extraction du mauvais système.** Les deux conteneurs du poste
     partagent nom d'hôte ET identifiant système : seul le port les distingue,
     et un rapport de paramètres du mauvais système est parfaitement lisible ;
  3. **le fichier qui existe sans porter la donnée** : cellule coupée au
     rendu, valeur retypée par le tableur, accents détruits par le codage,
     type gravé par inférence ;
  4. **la campagne partielle qui ressemble à un succès** : trois cibles
     tombées laissent quand même derrière elles des fichiers valides ;
  5. **la session laissée ouverte**, qui décale les indices de connexion et
     fait rattacher la cible suivante au mauvais système.
- **Assertion reine** : la chaîne fermée aux deux bouts, pour chaque cible.
  `lignes lues = lignes DÉCLARÉES par la source` d'un côté, `fichier RELU =
  relevé lu sur la cible`, ligne à ligne, de l'autre. Ni l'un ni l'autre ne
  suffit : la première seule laisse passer un fichier mal écrit, la seconde
  seule compare une lecture partielle à elle-même et ne rougit jamais. Les
  cinq premiers scénarios la portent chacun pour leur cible ; le sixième
  prouve que les cinq ont bien eu lieu.
- **Réversibilité** : rien à défaire. Aucune écriture métier, donc aucune
  contre-écriture. Ce qui doit être rendu à son état initial est d'un autre
  ordre et l'est explicitement : chaque cible referme SON canal dans son
  teardown, et la clôture de campagne rattrape ce qui aurait survécu à un
  échec. Le seul reliquat mesuré est une session GUI serveur laissée à
  expirer sur la cible 4 (voir « Données observées », point 6).

## Préconditions

1. **Aucun identifiant n'a de valeur par défaut** (convention 11). Les quatre
   mots de passe entrent par la ligne de commande en variable typée `Secret` ;
   une cible dont le mot de passe manque est **sautée en le disant**, jamais
   rouge. Un banc partiel doit pouvoir jouer la campagne sur ce qu'il a.
2. **Cibles 1 et 2 (écran)** : SAP GUI pour Windows installé, scripting activé
   côté serveur, et surtout **les deux ports distincts** (3200 et 3201 pour les
   deux conteneurs du poste). La chaîne de connexion et le mandant sont des
   variables ; la release attendue en est une aussi, et c'est elle qui sert de
   preuve de cible.
3. **Cibles 3 et 4 (WebGUI)** : le service ICF `webgui` doit être **actif** (il
   ne l'est pas par défaut, il s'active une fois par SICF). Le Data Browser de
   l'utilisateur doit être en **mode grille ALV** : en mode liste classique la
   sortie n'a aucun objet grille et la lecture échoue en nommant le réglage
   (source : message d'échec de la bibliothèque, et leçon de la mémoire QA
   partagée `lecons/erreur-diagnostic.jsonl#sap-diagnostic-0ac00079`, 2026-08-23,
   qui décrit exactement ce piège côté écran). Le certificat du conteneur 2023
   est auto-signé, donc les erreurs HTTPS doivent être ignorées sur cette
   cible, et la **stratégie de connexion est une variable de cible** (voir
   point 5 des données observées).
4. **Cible 5 (UI5)** : `npx cds watch` lancé dans le clone local de
   `cap-sflight`. Aucun identifiant. Le budget d'attente est élargi à 150 s et
   c'est une propriété de la cible, pas une pause déguisée : le serveur compile
   à la volée, donc le tout premier accès après un démarrage est lent (constaté
   au run : la table n'avait pas chargé au bout d'une minute, et chargeait en
   quelques secondes au passage suivant ; re-mesuré ce jour sur un serveur déjà
   chaud, la page répond en 1,5 s et la liste est rendue immédiatement).
5. **Le canal Parquet est optionnel** : absent, la campagne attend quatre
   formats par cible au lieu de cinq, l'annonce en journal et ne rougit pas.

## Données observées

### 1. Ce que la séquence a produit (run du 2026-09-15, 6/6, 535 s)

| Cible | Canal | Système, mandant | Tableau | Lues / déclarées | Colonnes | Durée |
|---|---|---|---|---|---|---|
| 1 | écran | A4H, `001`, release 754 kernel 777 | rapport des paramètres de profil | **1639 / 1639** | 5 | 75 s |
| 2 | écran | A4H, `001`, release 758 kernel 793 | le même rapport | **1635 / 1635** | 5 | 73 s |
| 3 | WebGUI | A4H, `001`, connexion par formulaire | table des messages, 150 hits | **150 / 150** | 4 | 10 s |
| 4 | WebGUI | A4H, `001`, connexion d'en-tête | la même table | **150 / 150** | 4 | 369 s |
| 5 | UI5 | cap-sflight, hôte local | réservations d'un voyage | **2 / 2** | 8 | 7 s |

Les cinq cibles ont produit les **cinq** formats, donc vingt-cinq fichiers, et
l'artefact de campagne porte l'empreinte `d9d15b48…` sur le seul périmètre
déclaré (les cibles), l'horodatage en étant exclu.

Deux valeurs méritent d'être lues ensemble : le rapport ne porte pas le même
nombre de paramètres sur les deux releases (1639 contre 1635), et les deux
relevés sont complets. C'est le genre d'écart qu'une extraction doit rendre
visible et qu'un extrait tronqué masquerait.

### 2. Les trois façons de s'amputer, et pourquoi elles ne se valent pas

| Canal | Ce qui est rendu | Ce qui est déclaré | Ce qui trahit l'amputation |
|---|---|---|---|
| écran (ALV) | toutes les lignes, mais les cellules non défilées sont VIDES | le compte de lignes de la grille | des lignes vides |
| WebGUI (ITS) | une PAGE de lignes (200 mesurées pour 2000 déclarées), renumérotées à partir de 1 | le total publié par la grille | **rien** |
| UI5 (`sap.m.Table`) | le seuil de croissance (**30 rendues pour 4133 déclarées**, re-mesuré live ce jour) | la longueur du binding | **rien** |

Deux canaux sur trois rendent des lignes propres, complètes et correctement
numérotées. Le fichier produit ressemble alors trait pour trait à un
inventaire. **Seule la confrontation au total déclaré** distingue « le tableau
tient en N lignes » de « la lecture s'est arrêtée à N lignes », et c'est
pourquoi la règle de refus est commune aux trois canaux au lieu de vivre dans
chaque suite.

Le cas de l'écran mérite sa nuance : le compte de lignes y est JUSTE même sur
un relevé creux, donc aucune garde fondée sur lui ne peut le voir. Le témoin
est le nombre de lignes entièrement vides, mesuré à zéro sur les deux releases
après correction (voir point 7).

### 3. Les en-têtes ne sont pas de même nature selon le canal

| Canal | Clés du relevé | En-tête du fichier produit |
|---|---|---|
| écran | identifiants techniques (`NAME`, `USER_VALUE`, `DEFAULT_VALUE`, `DEFAULT_USUBS_VALUE`, `DESCR`) | titres AFFICHÉS (`Parameter Name`, `User-Defined Value`, `System Default Value`, sa forme non substituée, `Comment`) |
| WebGUI | identifiants techniques (`SPRSL`, `ARBGB`, `MSGNR`, `TEXT`) | les mêmes identifiants dans le fichier du run |
| UI5 | **aucun identifiant technique**, seulement des libellés | les libellés, LOCALISÉS |

Trois conséquences pratiques. D'abord, les deux canaux SAP gardent des clés
indépendantes de la langue (convention 3) et n'empruntent les titres que pour
l'en-tête livré, ce qui rend le fichier ressemblant à l'écran dont il vient.
Ensuite, le canal UI5 n'a pas ce luxe : une table UI5 n'expose que le libellé
de ses colonnes, donc une assertion portée sur un nom de colonne y est une
assertion sur une traduction. Le relevé du jour le montre crûment, les libellés
étant **mélangés français et anglais** dans la même table (`ID réservation`,
`Date d'inscription`, `Client`, `Airline`, `Nº vol`, `Date vol`,
`Flight Price`, `Booking Status`), ce que je confirme live aujourd'hui.
Enfin, cette même table porte une neuvième colonne SANS NOM (deux espaces),
l'indicateur de brouillon de Fiori Elements : elle est laissée de côté à
l'assemblage, et le journal le DIT au lieu de la faire disparaître en silence.

Reste un point **à vérifier** : sur le canal WebGUI, l'en-tête du fichier porte
les identifiants techniques, ce qui peut vouloir dire que la grille affiche ces
noms-là ou que le balayage des titres n'a rien trouvé et s'est rabattu sur les
identifiants. Le compte de titres trouvés voyage avec le relevé mais n'a pas
été journalisé par ce run, donc la question n'est pas tranchée.

### 4. La cible ne se prouve pas de la même façon sur les deux canaux SAP

| Canal | Ce que l'identité rend | Discrimine les deux conteneurs ? |
|---|---|---|
| écran | identifiant système, mandant, **release**, **kernel** | **oui** (754 kernel 777 contre 758 kernel 793) |
| WebGUI | identifiant système, mandant, utilisateur, transaction, programme, écran | **non** |

Les deux conteneurs annoncent le même identifiant système et le même mandant.
L'artefact du run le montre noir sur blanc : les DEUX cibles WebGUI y sont
consignées sous le même système et le même mandant, et rien dans leur identité
lue ne dit laquelle est laquelle. Sur ce canal, **seule l'adresse visée (le
port) distingue les systèmes**, et c'est une garde d'un autre genre : elle
dépend de ce qu'on a tapé, pas de ce qu'on a mesuré. Le canal écran, lui,
prouve sa cible par la release avant d'écrire quoi que ce soit, et le nom des
fichiers en est dérivé.

### 5. La page de connexion WebGUI n'est pas la même des deux côtés

Mesuré **live ce jour** par le serveur MCP, sans jamais s'authentifier : la
page de connexion s'ouvre sans identifiant, donc son rendu se mesure sans
risque. Les trois pages portent exactement les **14 mêmes champs**.

| Page | Champs rendus avec une taille non nulle |
|---|---|
| A4H, HTTP, port 50000 | **5** : système `54x20`, mandant `54x20`, utilisateur `124x20`, mot de passe `124x20`, langue `144x20` |
| ABAP 2023, HTTPS, port 50101 | **0** |
| ABAP 2023, HTTP, port 50100 | **0** |

Sur la cible 2023, les quatorze champs mesurent `0x0` ET n'ont aucun parent de
mise en page, en HTTP comme en HTTPS : ils sont hors d'atteinte de n'importe
quel moteur, quel que soit le localisateur. Un test qui ne connaîtrait que la
voie du formulaire conclurait « cible injoignable » sur un système
parfaitement disponible, puisque la même adresse répond très bien à une
authentification portée par un en-tête (prouvé par la cible 4 du run).

**Deux précisions que la mesure du jour apporte, et qui corrigent une lecture
trop rapide.** D'abord, le message « No switch to HTTPS occurred, so it is not
secure to send a password » n'est PAS propre à la cible 2023 : il s'affiche
aussi sur la page A4H en HTTP, dont le formulaire fonctionne parfaitement. Il
accompagne donc toute page de connexion servie en clair et n'explique rien.
Ensuite, la page 2023 rend dans son texte le fragment de repli sans script
(`<iframe ... src=?sap-system-login-oninputprocessing=onNoScript>`) comme du
TEXTE au lieu de le laisser jouer son rôle, ce que la page A4H ne fait pas.
C'est un indice sérieux, ce n'est pas une cause établie : la cause du rendu à
`0x0` reste **à vérifier**, et la stratégie de connexion reste une variable de
cible en attendant.

### 6. La déconnexion propre n'a pas eu lieu sur la cible 4

| Cible | Chemin de déconnexion | Durée | État de la session à la fermeture |
|---|---|---|---|
| 3 (formulaire) | bouton du bandeau, menu système, confirmation | 1,2 s | terminée, plus aucun élément rendu |
| 4 (en-tête) | **aucun** : le bouton du bandeau n'est jamais devenu visible | **361 s** de tentatives | **1451 éléments encore rendus** |

Le teardown de la cible 4 a épuisé dix tentatives en cascade, toutes en échec,
avant de fermer le navigateur. L'échec est avalé par le caractère
« au mieux » du teardown, donc la campagne reste verte, ce qui est le bon
comportement : une cible ne doit pas rougir parce que sa déconnexion n'a pas
abouti. Mais deux faits en découlent, et ils appartiennent au plan. Un : la
session GUI côté serveur a été laissée à EXPIRER au lieu d'être fermée. Deux :
ces 361 s représentent **les deux tiers de la durée totale de la campagne**
(361 s sur 535 s), pour une cible dont l'extraction elle-même prend quelques
secondes. Le lien avec l'anomalie de rendu du point 5 est plausible et **non
établi**.

> **Corrigé depuis, et c'est ce qui rend cette mesure utile.** `Log Off WebGui`
> et `Close WebGui` prennent désormais un BUDGET, court en teardown, et ce
> budget borne aussi les deux étapes qui ne répondaient qu'au délai du
> navigateur : la première d'entre elles était précisément celle qui
> n'aboutit pas ici. Quand la déconnexion échoue, le journal DIT que la
> session serveur est laissée à expirer, au lieu de l'abandonner en silence.
> Les 361 s ci-dessus sont donc la mesure qui a motivé le correctif, pas une
> propriété actuelle de la campagne : les passages suivants tiennent en 445 s.

### 7. Quatre défauts trouvés en montant la campagne

Tous deux dans le code venant d'être écrit, tous deux corrigés avant la
validation, tous deux instructifs :

1. **L'écrivain SVG coupait les cellules à 80 caractères par défaut**, ce qui
   convient à un aperçu et jamais à une extraction : 19 et 28 cellules perdues
   selon la release, la valeur entière ne survivant que dans l'infobulle du
   document. L'invariant d'une extraction est l'intégralité, donc la coupe est
   désormais explicitement désactivée et le nombre de cellules coupées est
   ASSERTÉ à zéro.
2. **Fermer la session d'une cible par son seul alias ne suffisait pas.** La
   cible suivante s'ouvrait derrière une connexion survivante, donc sur un
   autre indice de connexion. C'est exactement la situation où l'on se rattache
   au mauvais système, puisque la campagne enchaîne délibérément deux systèmes
   qui partagent leur nom d'hôte. Chaque cible possédant son canal seule, tout
   fermer est ici le geste juste et non un excès.

**Troisième défaut, trouvé par le REJEU** : le sous-titre des documents
portait le chemin de sortie, donc deux passages dans deux dossiers rendaient
des SVG différents pendant que CSV et JSON Lines restaient identiques à
l'octet près. Le déterminisme revendiqué par la capacité était faux sur le
seul format qui porte un sous-titre. Corrigé : le sous-titre porte l'identité
de la CIBLE, et les deux passages suivants rendent **25 fichiers sur 25
identiques à l'octet près**, même empreinte d'artefact.

**Quatrième défaut, trouvé par la revue indépendante** : la déconnexion de la
cible 4 (section 6), dont la borne ne bornait en réalité que la moitié des
attentes.

### 8. Le résolveur de grille a travaillé sur la cible 2

Six avertissements pendant le seul scénario 2 : le localisateur de la grille
désigne un CONTENEUR, et la bibliothèque descend jusqu'à la grille réelle en le
disant. C'est le comportement attendu sur cette release, qui enveloppe ses ALV
dans un séparateur à une profondeur variable selon la transaction. Aucun
avertissement de ce genre sur la release 754. Rien à corriger : c'est un fait
de release, et il est journalisé plutôt que subi. Le journal de réparation du
dépôt ne porte par ailleurs aucune dérive sur ces ancres.

## Scénarios

Six scénarios, joués dans l'ordre. Les cinq premiers sont indépendants entre
eux (une cible qui tombe n'emporte pas les autres) ; le sixième dépend de tous.

### 1. Le rapport des paramètres d'un premier système, extrait vers cinq fichiers

- **Étapes** :
  1. Ouvrir une session sur le premier système avec les identifiants fournis,
     sous un alias qui lui est propre.
  2. Lire l'identité du système et la confronter à la release ATTENDUE.
  3. Ouvrir le rapport des paramètres de profil, paramètres non substitués
     inclus, et s'arrêter sur sa grille.
  4. Extraire le tableau affiché en entier, toutes colonnes, avec son contrat.
  5. Refuser le relevé s'il est incomplet, AVANT toute écriture.
  6. Écrire les cinq formats sous une marque DÉRIVÉE de l'identité mesurée,
     relire ce qui se relit, confronter.
  7. Consigner au registre ce que la cible a réellement produit.
  8. Fermer le canal, même en cas d'échec.
- **Résultat attendu** : la release lue égale la release attendue, sinon la
  cible est REFUSÉE et aucun fichier n'est écrit ; le relevé porte au moins
  1000 lignes et 5 colonnes, autant de lignes lues que déclarées, aucune ligne
  vide, aucune ligne sans nom de paramètre ; les cinq fichiers existent, aucun
  n'est tronqué, aucune cellule n'est coupée au rendu, et les quatre formats
  relisibles portent EXACTEMENT le relevé lu sur la cible.
- **Assertions locale-indépendantes** : la release et le kernel, le compte de
  lignes, les identifiants techniques de colonnes. Aucun libellé.

### 2. Le même rapport sur l'autre release, sans rien changer d'autre

- **Étapes** : les mêmes que le scénario 1, avec les variables de l'autre
  système (chaîne de connexion, mandant, release attendue).
- **Résultat attendu** : identique, sur des valeurs propres à cette cible. Le
  nombre de paramètres DIFFÈRE légitimement d'une release à l'autre : ce n'est
  pas un critère de réussite, c'est une donnée extraite.
- **Pourquoi ce scénario n'est pas une redite** : c'est lui qui prouve que le
  changement de système ne demande que des variables. Et c'est lui qui rend la
  preuve de cible indispensable : les deux conteneurs partagent nom d'hôte et
  identifiant système, seul le port les distingue, donc une extraction menée
  sur le mauvais serait parfaitement lisible et fausse.

### 3. La même capacité vue du WebGUI, premier système

- **Étapes** :
  1. Ouvrir une session WebGUI par la stratégie de connexion DE CETTE CIBLE.
  2. Lire l'identité de la session et la confronter au système et au mandant
     attendus.
  3. Naviguer vers le Data Browser, vérifier qu'on y est.
  4. Afficher le contenu de la table de messages sous un plafond de hits qui
     reste sous la page que le serveur envoie.
  5. Extraire la grille affichée avec son contrat, colonne clé nommée.
  6. Refuser un relevé incomplet, écrire les cinq formats, relire, confronter,
     consigner.
  7. Fermer le canal, même en cas d'échec.
- **Résultat attendu** : au moins 100 lignes et 4 colonnes, autant de lignes
  lues que déclarées, aucune ligne sans valeur dans la colonne clé, et les cinq
  fichiers conformes au relevé.
- **Le plafond de hits n'est pas un détail d'ergonomie** : c'est lui qui décide
  de la complétude sur ce canal, puisque le serveur n'envoie qu'une page de
  lignes et les renumérote à partir de 1.

### 4. Le même canal sur l'autre système, par l'autre stratégie de connexion

- **Étapes** : les mêmes, avec l'adresse, les identifiants et la stratégie de
  cette cible, plus la tolérance au certificat auto-signé.
- **Résultat attendu** : le même, par une voie de connexion différente. C'est
  le seul écart entre les scénarios 3 et 4, et il est PORTÉ PAR UNE VARIABLE :
  une stratégie nommée, jamais un test sur le nom du système.
- **Pourquoi il compte plus que sa jumelle** : il fige un fait de banc qui
  ferait conclure à tort qu'une cible est injoignable (voir « Données
  observées », point 5). Un plan qui ne le dirait pas laisserait quelqu'un
  reprendre la voie du formulaire et chercher un défaut de localisateur là où
  il n'y en a pas.

### 5. Une table UI5 entièrement matérialisée, extraite vers les mêmes formats

- **Étapes** :
  1. Ouvrir l'application de voyages et attendre que sa liste ait RÉELLEMENT
     chargé ses données, pas seulement que le moteur soit prêt.
  2. Ouvrir la première fiche et attendre que sa table de réservations ait
     chargé.
  3. Extraire cette table avec son contrat, relever l'adresse de la page.
  4. Refuser un relevé incomplet, écrire les cinq formats, relire, confronter,
     consigner.
  5. Fermer le navigateur, même en cas d'échec.
- **Résultat attendu** : au moins 1 ligne et 5 colonnes, autant de lignes
  rendues que déclarées par le binding, et un total qui a fini d'être compté.
  Un total encore PROVISOIRE est refusé comme un total absent : il ne borne
  rien, et l'égalité avec les lignes lues peut y être vraie un instant et
  fausse le suivant.
- **Le contraste est délibéré** : c'est la même application qui porte la liste
  de 4133 voyages rendue à 30 lignes. La campagne extrait la table qui se
  matérialise entièrement, et le contrat refuserait l'autre. Extraire un
  tableau et lire un tableau ne demandent pas la même garantie.

### 6. Le bilan de campagne est complet et déterministe

- **Étapes** :
  1. Confronter le nombre de cibles qui ont produit un relevé au nombre de
     cibles que cette exécution avait PRÉVUES.
  2. Vérifier, cible par cible, que son relevé était complet, qu'il portait des
     lignes, et qu'il a produit tous les formats attendus.
  3. Écrire l'artefact déterministe de la campagne, le RELIRE, et confronter ce
     qu'il porte au registre écrit.
- **Résultat attendu** : autant de cibles jouées que prévues, sinon la campagne
  est déclarée incomplète en nommant l'écart ; l'artefact relu porte le
  registre et son empreinte se recalcule sur le périmètre déclaré, donc un
  fichier retouché après coup est refusé au lieu d'être comparé.
- **Le détail qui fait toute la valeur du scénario** : le nombre de cibles
  prévues est calculé **avant la première cible**, d'après les identifiants
  fournis. Calculé après coup, il vaudrait toujours le nombre de cibles qui ont
  réussi, et le bilan se vérifierait lui-même.

**Keywords métier** : aucun ne manque, la suite existe et les utilise tous. Ils
vivent dans la couche vocabulaire : l'ouverture et la lecture par canal
(rapport d'écran, session et grille WebGUI, parcours et table UI5), la règle de
refus commune aux trois canaux, l'écriture des cinq formats avec sa relecture,
et l'artefact déterministe. La campagne elle-même ne contient **aucun** code
d'écriture propre à un canal : c'est le rendu concret du contrat commun.

## Points de vigilance pour la génération

1. **La garde de complétude s'appelle AVANT toute écriture**, jamais après.
   Un refus qui constate après coup n'empêche rien, et sur un relevé amputé les
   cinq écritures passent au vert : comparer une lecture partielle à elle-même
   ne rougit jamais.
2. **Un total non déclaré est refusé lui aussi.** Accepter le silence est
   exactement le défaut que la règle existe pour empêcher, puisque le canal qui
   se tait est celui qui ne laisse aucune autre trace.
3. **Le nom des fichiers est DÉRIVÉ de l'identité mesurée**, jamais d'une
   constante : un fichier ne peut pas annoncer un système qu'il ne porte pas.
4. **La stratégie de connexion WebGUI est une variable de cible**, avec des
   stratégies NOMMÉES, jamais un test sur le nom du système (même règle que les
   page objects multi-release).
5. **Le plafond de hits WebGUI décide de la complétude.** Le monter au-delà de
   la page servie rend la lecture partielle, et rien dans les lignes rendues ne
   le montre.
6. **Sur le canal UI5, un nom de colonne est une traduction** (convention 3) :
   il sert d'en-tête au fichier, jamais d'assertion. Et une colonne sans nom
   est écartée du relevé, mais le retrait est annoncé.
7. **Tout fermer après chaque cible**, pas seulement l'alias : une connexion
   orpheline décale les indices et la campagne enchaîne deux systèmes qui
   partagent leur nom d'hôte.
8. **Ne jamais piloter le canal écran depuis le serveur MCP** : le COM sur un
   thread étranger rend des perceptions vides en PASS. Cette campagne se joue
   par `robot`.
9. Conventions tenues : 1 (aucun nom de rapport, de table, de colonne ni de
   localisateur dans la suite : tout vit dans la couche vocabulaire), 2 (aucune
   attente fixe, les budgets élargis sont des propriétés de cible), 3, 11
   (aucun mot de passe par défaut, saut propre sans identifiant), 12 (le
   contrat d'extraction et les cinq écrivains sont dans `src/` avec leurs tests
   hors SAP).

## Ce qui a été vérifié et comment

| Fait | Source |
|---|---|
| lignes lues et déclarées, colonnes, formats, identités, empreinte de l'artefact | **run `robot` du 2026-09-15** (6/6, 535 s) et son artefact de campagne |
| durées par cible, avertissements de résolution de grille, échec de déconnexion de la cible 4 | **journal du même run** |
| liste UI5 rendue à 30 lignes pour 4133 déclarées, seuil de croissance, total arrêté | **re-mesuré live le 2026-09-15 par le serveur MCP** |
| table des réservations : 2 lignes sur 2, 9 colonnes dont une sans nom, libellés mélangés français et anglais | **re-mesuré live** le même jour |
| rendu des trois pages de connexion WebGUI (14 champs, 5 visibles sur A4H, 0 sur la 2023 en HTTP comme en HTTPS) | **mesuré live** le même jour, sans aucune authentification |
| message d'avertissement HTTPS présent AUSSI sur la page A4H | **mesuré live**, et il corrige une lecture trop rapide |
| réglage du Data Browser en mode grille ALV | message d'échec de la bibliothèque, plus une leçon de la mémoire QA partagée (2026-08-23) |

Le canal écran n'a **pas** été re-sondé par le serveur MCP, délibérément :
aucune session SAP GUI n'était ouverte, et le contrat du dépôt déconseille de
piloter le COM depuis un thread étranger. Ses chiffres viennent du run.

### Provenance de ce plan

Deux faits de traçabilité, rapatriés ici le 2026-09-16 depuis une clé
`notes` que portait le sidecar de mission. Le schéma du handoff est **fermé à
dessein** : une clé libre est exactement l'endroit où une affirmation non
vérifiée se glisse dans un artefact censé l'être, donc ce qui relève du récit
vit dans le plan, où il est relu.

- **Ce plan a été écrit APRÈS la suite**, écart assumé au cycle habituel
  (plan puis génération). Le marqueur de provenance a été apposé ensuite.
- **La campagne a été jouée six fois.** Les deux derniers passages rendent 25
  fichiers sur 25 identiques à l'octet près et la même empreinte d'artefact :
  c'est ce qui fait du déterminisme une mesure et non une intention.

## Ce qui n'est PAS couvert

**La campagne démontre le chemin NOMINAL de la règle commune sur cinq cibles,
et son mordant sur aucune.** C'est délibéré, et il faut le dire parce que le
contraire serait facile à croire. Sur les cibles 3 et 4 le plafond de hits est
choisi SOUS la page que le serveur envoie, donc l'égalité entre lignes lues et
lignes déclarées tient par construction de la sélection ; sur la cible 5 le
tableau visé est celui qui se matérialise entièrement, le contraste avec la
liste de 4133 lignes étant précisément le sujet de la suite voisine. Seules
les cibles 1 et 2 approchent une frontière, et encore par le canal des lignes
vides.

La preuve que la garde REFUSE, elle, vit dans les trois suites par canal, qui
portent chacune leur contre-épreuve sur la cible réelle : la grille WebGUI
redemandée avec un plafond au-delà de la page, la table UI5 au-delà de son
seuil de croissance, l'ALV non défilée. Les branches de refus sont par
ailleurs couvertes hors SAP (`tests/unit/test_table_extract.py`). Ce que
personne ne prouve aujourd'hui, c'est que `declared_rows` soit mesuré
indépendamment des lignes lues SUR CHAQUE CANAL dans le cadre de cette
campagne-ci : ajouter un scénario opt-in par canal qui provoque l'écart et
asserte le refus reste à faire.


1. **La discrimination des deux systèmes sur le canal WebGUI.** L'identité lue
   ne porte ni release ni kernel, et les deux conteneurs annoncent le même
   identifiant système et le même mandant. Seule l'adresse visée les distingue,
   ce qui est une garde plus faible que celle du canal écran.
2. **La cause du rendu à `0x0` de la page de connexion 2023.** Constatée, y
   compris dans les deux schémas, jamais expliquée. Le fragment sans script
   rendu comme du texte est un indice, pas une preuve.
3. **La cause de l'échec de déconnexion de la cible 4**, et son lien éventuel
   avec le point précédent. La session serveur y est laissée à expirer.
4. **La provenance des en-têtes du fichier WebGUI** : identifiants techniques
   affichés par la grille, ou repli faute de titres trouvés. Le témoin existe,
   il n'a pas été journalisé par ce run.
5. **Le défilement d'une grille WebGUI ou d'une table UI5.** La campagne borne
   sa sélection pour rester sous ce que la source matérialise ; elle ne force
   pas le chargement du reste. Extraire un tableau plus grand que la page
   servie demanderait une capacité que le dépôt n'a pas encore sur ces deux
   canaux.
6. **Les cibles absentes du banc.** Aucun système applicatif réel, donc aucun
   tableau métier (postes de commande, flux de documents) n'a été extrait : ce
   qui est prouvé porte sur des tableaux techniques et un jeu de démonstration.
7. **La fidélité des fichiers au-delà de leur relecture par nos propres
   lecteurs.** Le classeur a été relu par un lecteur du dépôt et par un tableur
   lors des campagnes voisines ; la relecture du SVG, elle, se fait sur le
   document et non par un lecteur, faute d'en avoir un.

## Ancrage de la suite sur ce plan

La suite porte son marqueur de provenance
(`Spec: specs/extraction-multi-cibles.md`), apposé après coup puisque le plan
est postérieur à la suite. Il se rafraîchit, une fois ce document relu :

```
python scripts/check_spec_sync.py --stamp tests/robot/cross/extraction_multi_cibles.robot specs/extraction-multi-cibles.md
```

Ensuite, la règle ordinaire s'applique : toute évolution passe par le plan,
puis par une régénération ou un re-stampage assumé, jamais par une édition
silencieuse de la suite.
