# Simulation écriture / lecture cross-canal : écrire à l'écran, constater par l'API

- **Canaux** : ECC (SAP GUI) pour l'écriture, API (OData) pour la constatation
- **Système observé** : A4H, ECC via une chaîne de connexion paramétrée, client
  `001`, langue `EN` ; canal API sur le même système et le même mandant
- **Nature** : campagne **d'écriture**, réversible, idempotente et **opt-in**,
  réutilisable sur une cible ECC comme sur une cible S/4HANA
- **Objectif** : prouver qu'une donnée écrite par un canal est réellement vue
  par l'autre, puis qu'elle disparaît des deux, et **produire l'observation de
  réversibilité** que la campagne de croisement ne peut pas produire

> **Statut : faits live relevés le 2026-08-22 (A4H, client 001).** Les valeurs
> chiffrées sont des observations datées de cette cible, jamais des constantes
> du produit. Toute cible relit ses propres nombres.

## Pourquoi ce plan existe

`specs/croisement-ddic-odata-ecc-s4hana.md` qualifie des candidats à l'écriture
à partir du seul `$metadata`, et sa garde durcie retourne **zéro candidat** sur
A4H. Ce n'est pas un défaut de la garde : c'est la limite de la source. Une
annotation `sap:` dit ce que le SERVICE permet. Elle ne dit rien de deux
conditions qui décident vraiment d'une simulation d'écriture :

1. l'écriture est-elle **réversible** (peut-on revenir à l'état initial) ;
2. le nettoyage est-il **constatable** (peut-on prouver le retour, et pas
   seulement l'avoir demandé).

Le champ `reversibility_observed`, à `unknown` par construction dans l'artefact
de croisement, nomme cette preuve manquante. Ce plan la produit, par
observation datée, sur une cible choisie pour être sûre.

## La cible, et pourquoi elle

Établie live le 2026-08-22, par **comptage croisé** et non par convention de
nom. Le service `Z_BIND_FLIGHT_R` expose le modèle de démonstration RAP, et
quatre de ses entity sets correspondent exactement à des tables du dictionnaire :

| Entity set | `$count` OData | Table DDIC | Comptage SE16 |
|---|---|---|---|
| `Airline` | 16 | `/DMO/CARRIER` | 16 |
| `Connection` | 20 | `/DMO/CONNECTION` | 20 |
| `Flight` | 40 | `/DMO/FLIGHT` | 40 |
| `Airport` | 47 | `/DMO/AIRPORT` | 47 |

Ces quatre couples sont prouvés et doivent rejoindre le dictionnaire de
correspondance de la campagne de croisement, où ils manquent.

`/DMO/CARRIER` est retenue comme cible d'écriture, pour quatre raisons :

- **elle est observable par l'autre canal**, ce qui est tout l'intérêt : SCARR,
  la voie d'écriture historiquement éprouvée du dépôt, n'est exposée par aucun
  service. Un cycle sur SCARR ne prouverait que l'écran ;
- **sa structure est minimale** : quatre champs seulement, relevés dans DD03L
  le 2026-08-22 : `CLIENT` (`CLNT`, clé, retiré en silence de l'écran de
  sélection SE16), `CARRIER_ID` (`CHAR` 3, clé), `NAME` (`CHAR` 40),
  `CURRENCY_CODE` (`CUKY` 5). Aucun champ obligatoire exotique, aucun GUID ;
- **c'est une table de démonstration**, hors de tout flux métier réel ;
- **une clé de 3 caractères** laisse choisir un identifiant de test qui
  n'entrera jamais en collision avec une donnée livrée.

`CURRENCY_CODE` est de type `CUKY` : sa valeur doit exister dans la table des
devises. Prendre une devise déjà présente dans la table, relevée à l'exécution,
plutôt qu'une constante écrite dans le plan.

## Règles de sûreté, non négociables

Cette campagne écrit dans un système. Les règles suivantes priment sur toute
considération de couverture.

1. **Opt-in explicite.** La suite porte un tag dédié et ne s'exécute pas dans
   un run par défaut. Une campagne qui écrit ne doit jamais démarrer par
   surprise.
2. **Un identifiant de test reconnaissable**, paramétrable, jamais une valeur
   d'allure métier. La suite refuse de démarrer si l'identifiant visé existe
   déjà avec un contenu qui n'est pas le sien.
3. **Pré-nettoyage idempotent.** Un reliquat d'exécution précédente est
   supprimé AVANT le cycle, pas après : une exécution interrompue ne doit pas
   bloquer la suivante.
4. **Nettoyage garanti sur tous les chemins**, y compris après un échec de
   test, par un teardown qui ignore ses propres erreurs mais les journalise.
5. **Suppression ciblée uniquement.** L'écran de suppression de masse de SE16
   n'est jamais emprunté : la seule voie est la suppression d'un enregistrement
   sélectionné. Le menu de suppression globale est adjacent à celui de la
   suppression sélective, et la confusion est irréversible.
6. **Aucune écriture sur une table qui n'est pas la cible déclarée.** Le
   périmètre d'écriture est une liste blanche d'une seule entrée par défaut.
7. **Le verdict de nettoyage est CONSTATÉ, jamais supposé** : le retour au
   compte initial ET la disparition de l'entité sont vérifiés, par les deux
   canaux.

## Scénarios

### 1. Ouvrir les deux canaux et établir l'état initial

- **Étapes** : préflight des deux canaux (scripting, Gateway), contrôle du même
  mandant des deux côtés, comptage initial de la table par SE16 et de l'entity
  set par `$count`.
- **Résultat attendu** : les deux comptes sont égaux. C'est l'invariant de
  départ : sans lui, aucune variation ultérieure n'est interprétable.
- **Critère d'arrêt** : comptes divergents. Produire la preuve et s'arrêter
  AVANT toute écriture.

### 2. Garantir un point de départ propre

- **Étapes** : chercher l'identifiant de test dans la table ; s'il existe, le
  supprimer ; re-compter.
- **Résultat attendu** : l'identifiant de test est absent, le compte est revenu
  à l'état initial du scénario 1.
- **Critère d'acceptation** : le scénario est idempotent, il passe qu'un
  reliquat existe ou non.

### 3. Écrire par l'écran

- **Étapes** : ouvrir SE16 sur la table, déclencher la création d'entrée depuis
  l'écran INITIAL, saisir les champs, valider, contrôler le TYPE du message de
  statut.
- **Résultat attendu** : message de succès, aucun modal résiduel.
- **Critère d'acceptation** : l'assertion porte sur le type de message, jamais
  sur son texte localisé (convention 3).
- **Piège relevé** : la création se déclenche depuis l'écran initial de SE16 ;
  sur l'écran de sélection, l'entrée de menu correspondante a une autre
  signification.

### 4. Constater par l'autre canal

- **Étapes** : compter l'entity set, puis lire l'entité par sa clé.
- **Résultat attendu** : le compte vaut l'initial plus un, et l'entité existe
  avec **exactement** les valeurs écrites à l'écran.
- **Critère d'acceptation** : la comparaison porte sur les valeurs, pas
  seulement sur l'existence. C'est ce qui distingue « une ligne est apparue »
  de « ma ligne est apparue ».
- **Point de vigilance** : la lecture par l'API peut nécessiter une nouvelle
  requête plutôt qu'un cache de session. Aucune attente fixe : re-interroger.

### 5. Supprimer par l'écran

- **Étapes** : sélectionner l'enregistrement de test et lui seul, emprunter la
  suppression sélective, confirmer, contrôler le type du message.
- **Résultat attendu** : message de succès.
- **Critère d'arrêt** : toute ambiguïté sur la ligne sélectionnée interrompt le
  scénario sans supprimer.

### 6. Constater la disparition par les deux canaux

- **Étapes** : re-compter par SE16 et par `$count`, et tenter la lecture de
  l'entité par sa clé.
- **Résultat attendu** : les deux comptes sont revenus à l'état initial et
  égaux entre eux, et la lecture par clé ne retourne plus l'entité.
- **Critère d'acceptation** : un compte revenu à l'initial ne suffit pas. La
  disparition se vérifie sur **l'entité**, la leçon déjà payée sur un service
  draft-enabled où un compte inchangé ne prouvait aucun nettoyage.

### 7. Produire l'observation de réversibilité

- **Étapes** : consigner le verdict du cycle sous une forme JSON-safe : cible,
  canal d'écriture, canal de constatation, horodatage UTC, comptes avant et
  après, verdict de disparition.
- **Résultat attendu** : une observation **datée**, réutilisable pour renseigner
  `reversibility_observed` dans l'artefact de croisement, à la place du
  `unknown` par défaut.
- **Critère d'acceptation** : l'observation ne contient aucun identifiant
  d'utilisateur ni secret.

### 8. Fermer sur tous les chemins

- **Étapes** : supprimer l'enregistrement de test s'il subsiste, annuler tout
  popup, fermer la session GUI et le canal API.
- **Résultat attendu** : aucune session orpheline, aucune donnée de test
  laissée dans le système, y compris après un échec en cours de cycle.

## Points de vigilance

**Le champ client est retiré en silence de l'écran de sélection SE16** (type
`CLNT`), constat déjà consigné pour d'autres tables. Ne pas le chercher parmi
les critères, ne pas le saisir : il est renseigné par la session.

**Le type `CUKY` contraint la valeur.** Une devise inventée sera refusée. Lire
une valeur réellement présente dans la table avant d'écrire.

**Un compte égal n'est pas une preuve de nettoyage.** Deux écritures et une
suppression donneraient le même compte qu'aucune écriture. La preuve est la
disparition de l'entité identifiée.

**L'écriture est un droit, pas une capacité déclarée.** Une autorisation
manquante se manifestera par un message de statut, pas par une annotation de
métadonnées. Le diagnostic reste le TYPE du message.

**Ne jamais réutiliser cette suite comme fabrique de données.** Elle prouve un
cycle, elle ne prépare rien pour d'autres tests : la fabrique de données du
canal API existe pour cela, avec son suivi et son teardown.

## Handoff sap-generator

1. Créer les keywords métier d'écriture SE16 dans la couche `resources/`, en
   page object (un fichier pour l'écran de saisie SE16) : les localisateurs
   d'écran n'ont pas à vivre dans une suite (convention 1), et ils n'existent
   aujourd'hui qu'en brut dans une suite de démonstration auto-suffisante,
   volontairement dérogatoire.
2. Placer la suite sous `tests/robot/cross/`, tag d'opt-in explicite, et NE PAS
   l'inclure dans un run par défaut.
3. Ajouter les quatre couples `Z_BIND_FLIGHT_R` prouvés ci-dessus au
   dictionnaire de correspondance de la campagne de croisement, puis re-jouer
   cette campagne pour vérifier qu'elle reste verte avec dix-quatorze couples.
4. Exécuter chaque étape live avant écriture, et vérifier de ses propres yeux
   que la table est revenue à son état initial à la fin.
5. Stampiller la suite avec ce plan.

## Écarts constatés à la génération (2026-08-22)

Relevés live sur A4H, client `001`, pendant la génération de
`tests/robot/cross/simulation_ecriture_lecture.robot`. Le premier écart change
la cible de la campagne : il est donc rendu ici en entier, avec la mesure qui
l'établit.

### 1. La cible du plan n'est pas écrivable par l'écran

Le plan retient `/DMO/CARRIER` sur quatre critères. Un cinquième, resté
implicite parce qu'il paraissait acquis, la disqualifie : **la table doit
accepter la maintenance**. Mesuré : « Create Entries » sur `/DMO/CARRIER`
répond par un message de statut de type `E` et l'écran de saisie ne s'ouvre
pas.

Ce n'est pas une question d'autorisation, c'est une propriété du dictionnaire.
Lecture de `DD02L` (version active, motif `/DMO/*`) : les **onze** tables
transparentes du modèle de démonstration RAP portent un indicateur de
maintenance VIDE. Aucune n'est écrivable par SE16, quel que soit
l'utilisateur. La même lecture sur les tables `SNWD_*` montre que les tables
métier EPM (`SNWD_PD`, `SNWD_BPA`, `SNWD_SO`…) sont dans le même cas : sur
cette cible, les tables projetées par les services les plus intéressants sont
précisément celles que l'écran refuse d'écrire.

**Ce que la suite en fait.** Les huit scénarios sont inchangés, y compris leurs
critères d'acceptation : c'est la CIBLE qui change, et elle est devenue un
paramètre de la couche `resources/` plutôt qu'une constante du plan. La cible
retenue satisfait les quatre critères du plan ET le cinquième :

| Critère du plan | `SNWD_PD_CATGOS` (mesuré le 2026-08-22) |
|---|---|
| Maintenance autorisée par le dictionnaire | oui (le seul critère que `/DMO/CARRIER` échoue) |
| Observable par l'autre canal | `SubCategories` du service « Shop » : 32 = 32 côté écran ; et `VH_CategorySet` de `GWSAMPLE_BASIC` : 32, seconde constatation indépendante |
| Structure minimale | trois champs, dont un seul non clé : `MANDT` (`CLNT`, clé), `CATEGORY` (`CHAR` 40, clé), `MAIN_CATEGORY` (`CHAR` 40) |
| Table de démonstration hors flux métier | classe de livraison `L` |
| Clé permettant un identifiant de test sans collision | `CHAR` 40 : `ZZ_SAPFX_TEST_CATEGORY` |

La contrainte de type `CUKY` du plan disparaît avec `/DMO/CARRIER`, mais la
règle qu'elle portait est conservée telle quelle : la valeur de rattachement
(`MAIN_CATEGORY`) est **relue dans les données existantes** à l'exécution, la
première valeur de `MainCategories` par ordre alphabétique, jamais une valeur
inventée. Effet de bord surveillé : réutiliser une valeur existante laisse le
nombre de catégories principales inchangé (8 avant, 8 après), donc le cycle ne
touche qu'un seul compte.

### 2. Le plan a raison sur SCARR, et la voie API est fermée aussi

Vérifié : le catalogue Gateway de la cible publie 38 services et **aucun
n'expose SCARR** (pas de service d'exemple « flight » classique). Un cycle sur
SCARR ne prouverait donc que l'écran, exactement comme le plan l'affirme.

Constat qui va plus loin, et qui n'était pas dans le plan : la voie
symétrique est fermée elle aussi. Le service `Z_BIND_FLIGHT_R` déclare
`creatable`, `updatable` et `deletable` à **faux** sur `Airline`. Sur cette
cible, ni l'écran ni l'API ne peuvent écrire dans le modèle RAP. C'est une
confirmation de plus de l'arbitrage du plan de croisement : la qualification
d'une cible d'écriture demande une observation, pas une déclaration.

### 3. Les quatre couples sont confirmés, et le service entre au périmètre

Re-mesurés à la génération, des deux côtés : `Airline` 16, `Connection` 20,
`Flight` 40, `Airport` 47, égaux aux comptages SE16 des quatre tables. Les
quatre couples sont entrés dans le dictionnaire de correspondance, et le
service `Z_BIND_FLIGHT_R` dans le périmètre de la campagne de croisement (son
cinquième ensemble d'entités, `I_Country`, répond aussi : 250). Seul l'alias
RELEVÉ est déclaré (`AirlineID` face à `CARRIER_ID`) ; les champs des trois
autres tables n'ayant pas été lus, leurs couples n'entrent qu'avec ce qui est
prouvé, leur volumétrie.

### 4. Deux points de vigilance du plan sont confirmés tels quels

Le champ client est bien **retiré en silence** de l'écran de sélection SE16 :
`/DMO/CARRIER` n'y expose que `CARRIER_ID`, `NAME` et `CURRENCY_CODE`. Et le
menu de suppression de masse est bien **adjacent** à celui de la suppression
sélective sur la grille de résultats, à un cran d'écart.

La conséquence de conception est dans la suite : la sûreté ne repose pas sur
l'indice du menu, qui peut se décaler d'une version à l'autre, mais sur le
CONTENU. La grille est filtrée sur la clé, relue, et le mot-clé s'interrompt
**sans rien supprimer** dès que la sélection ne porte pas exactement la ligne
visée. Un test hors SAP verrouille en plus l'absence de toute référence à
l'indice voisin dans le page object.

### 5. L'observation ne rejoint pas encore l'artefact de croisement

Le plan prévoit que l'observation serve à renseigner `reversibility_observed`
dans l'artefact de croisement. Le raccordement n'est pas automatique, et sur
cette cible il ne peut pas l'être : ce champ vit sur une fiche de **candidat
d'écriture API**, or la campagne de croisement n'en produit aucun sur A4H, et
la réversibilité constatée ici porte sur le canal ÉCRAN. L'observation est donc
produite comme artefact autonome et daté (`write_channel: ecc`). Raccorder les
deux demanderait une fiche de candidat par CANAL, ce qui relève d'une
re-planification, pas d'une génération.

### 6. Un piège de pilotage, sans effet sur le plan

Consigné parce qu'il a coûté du temps : le serveur rf-mcp fige les classes de
bibliothèque à son démarrage, donc les mots-clés ajoutés depuis répondaient
« keyword not found », et une erreur COM inter-threads a fini par rendre la
session GUI illisible depuis ce processus alors qu'elle était parfaitement
saine. La fin de l'exploration et toutes les validations sont passées par des
exécutions `robot` ciblées, qui repartent d'un processus neuf.
