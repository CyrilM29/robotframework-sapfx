# Sécurité croisée sur trois canaux (cible ABAP Platform 2023)

- **Canaux** : l'**ÉCRAN** (SAP GUI Scripting, `SapEccLibrary`), le **RFC**
  (`SapApiLibrary`, `pyrfc`) et l'**HTTP/OData** (`SapApiLibrary`). Trois
  protocoles, une seule cible, la même vérité regardée de trois côtés.
- **Système observé** : ABAP Platform 2023 en conteneur, release **758**,
  kernel **793**, mandant `001`, utilisateur `DEVELOPER`, langue `EN`.
- **Exploration live** : 2026-09-14, pilotée par le serveur MCP pour l'écran
  (session ouverte en ligne de commande puis rattachée, pour qu'aucun secret
  ne transite par le serveur) et par des sondes directes pour les deux autres
  canaux.
- **État de ce plan** : écrit APRÈS l'exploration. Il formalise ce qui a été
  mesuré.
- **Posture** : LECTURE SEULE de bout en bout. Aucun paramètre écrit, aucun
  compte touché, aucune transaction de modification ouverte.

## Pourquoi trois canaux plutôt qu'un de plus

Le dépôt porte déjà deux campagnes de sécurité sur cette cible, toutes deux
par le canal RFC : la **configuration** (ce que le système déclare) et la
**surface** (ce qui est atteignable). Chacune se termine par une liste de ce
qu'elle ne peut pas voir, et ces listes ont un point commun : ce ne sont pas
des oublis, ce sont des limites de CANAL.

Cette campagne existe parce qu'un autre canal les lève. Trois questions
restées ouvertes y trouvent une réponse, et une quatrième, que personne
n'avait posée, en sort.

| Question | Laissée ouverte par | Tranchée par |
|---|---|---|
| Le durcissement de la 758 est-il un réglage ou un défaut du noyau ? | les deux campagnes RFC, explicitement | l'**écran** (le rapport porte les deux colonnes) |
| Quel est l'état des comptes standards du mandant de référence ? | la campagne de surface (connexion RFC refusée) | l'**écran** (un rapport lit tous les mandants) |
| Le paramètre qui protège les cookies produit-il son effet ? | jamais posée | l'**HTTP** (la réponse porte les drapeaux, ou non) |

## Le parti pris de jugement

Le même que ses deux voisines : sont ASSERTÉS les contrôles dont l'écart
serait un incident quelle que soit la politique, et les **assertions de
non-dérive** ; tout le reste est RAPPORTÉ. S'y ajoute ici un troisième
régime, propre au croisement : une **assertion de méthode**, qui ne juge pas
le système mais vérifie que la lecture est valide (la jointure a eu lieu, le
pictogramme a été interprété, l'observation a eu lieu). Sans elles, plusieurs
scénarios seraient verts sur du vide.

## Préconditions

1. **Le port distingue les deux conteneurs du poste** (3201 pour cette cible,
   3200 pour la 1909) et le **nom d'hôte est PARTAGÉ** (`vhcala4hci` résout
   vers la boucle locale pour les deux). Le piège du canal RFC se reproduit
   donc à l'identique sur l'écran : viser le mauvais port atteint l'autre
   système sans la moindre erreur. Le scénario 1 prouve la cible **sur les
   trois canaux**.
2. **Le scripting SAP GUI doit être activé côté serveur** (mesuré `TRUE` sur
   la cible, sans restriction de lecture ni d'enregistrement). C'est un
   réglage de SERVEUR : il se provisionne, il ne se force pas depuis un test.
3. **Une session SAP GUI ouverte**, à laquelle la suite se rattache. Le mot de
   passe entre par la ligne de commande ; la suite ne l'écrit nulle part.
4. **Interpréteur 3.10 à 3.12** portant `pyrfc` pour le canal RFC, et la
   Gateway active pour le canal HTTP (elle l'est d'origine sur cette image).

## Données observées

### 1. L'origine des paramètres, ce que seul l'écran donne

Le rapport de paramètres porte trois colonnes utiles : le nom, la valeur du
**profil d'instance** et la valeur par **défaut du noyau**. Le canal RFC, lui,
ne rend que la valeur EFFECTIVE, sans dire d'où elle vient.

| Mesure | Valeur |
|---|---|
| paramètres rendus par le rapport | 1635 |
| dont **substitués par le profil** | 325 |
| paramètres de sécurité audités par les campagnes du dépôt | 42 |
| dont hérités du **noyau** | **39** |
| dont **déclarés dans le profil** | 3 |
| dont **modifiés par le profil** | **0** |

**Le durcissement supérieur de cette release n'est donc pas un réglage
d'exploitant : c'est le défaut livré par le noyau 793.** Les onze écarts
mesurés entre la 754 et la 758 par la campagne de configuration s'expliquent
par la version du noyau, et rien d'autre.

**La nuance des trois exceptions vient du run, pas de l'analyse**, et elle
compte. Une première lecture manuelle portait sur un sous-ensemble choisi de
25 paramètres et concluait « aucun n'est dans le profil ». La suite, qui lit
le périmètre COMPLET des deux campagnes, en a trouvé trois : les chemins des
deux fichiers de contrôle d'accès de la passerelle et un indicateur de
compatibilité de mot de passe. Les deux premiers ne PEUVENT pas venir d'un
défaut, ils désignent cette installation.

Or les trois y portent **exactement la valeur du défaut**. « Posé dans le
profil » et « modifié par le profil » ne sont donc pas la même chose, et c'est
la seconde notion qui a du sens pour un audit : aucun réglage de profil ne
durcit ni n'affaiblit la posture de cette cible. La campagne assertait d'abord
la première, le run l'a démentie, et la distinction a été ajoutée à la
bibliothèque plutôt que l'attente relâchée.

La conséquence pratique dépasse la curiosité. La sentinelle de dérive de la
campagne de configuration surveille ces 25 valeurs : elle surveille en réalité
le NOYAU. Un écart y apparaîtra lors d'une montée de version, pas parce que
quelqu'un a modifié le système, et le remède n'est pas le même. Inversement,
un paramètre de sécurité qui APPARAÎTRAIT dans le profil serait une décision
humaine, donc exactement ce qu'un audit veut voir.

**Contre-épreuve jouée** : sur les 129 paramètres substitués dont profil et
défaut diffèrent, 116 ont une valeur effective qui suit le PROFIL, 5 qui suit
le défaut, et 8 qui ne suit ni l'un ni l'autre. Ces 8 derniers ne sont pas une
troisième source : ce sont des valeurs longues dont la colonne de profil est
**tronquée** (voir plus bas). La mécanique « le profil l'emporte quand il
existe » est donc établie par la mesure, pas supposée.

### 2. La troncature silencieuse, et pourquoi elle compte

| Colonne | Largeur mesurée | Paramètres exactement à cette longueur |
|---|---|---|
| valeur de profil | **60** | 13 |
| valeur par défaut | 128 | 4 |

La colonne de profil coupe à 60 caractères **sans aucun marqueur**. Comparer
cette valeur à celle du canal RFC, qui est complète, fabrique un écart sur
toute valeur longue, et c'est exactement ce qui produisait les 8 « divergents »
de la contre-épreuve.

Le seul paramètre de sécurité à valeur longue (l'algorithme de hachage des
mots de passe, 67 caractères) **passe**, parce qu'il vit dans la colonne de
défaut, qui tient 128. C'est une chance structurelle et non une garantie : le
jour où ce paramètre serait posé dans le profil, l'écran le tronquerait et le
croisement crierait au loup. La garde ne dépend pas de cette chance, elle
ÉCARTE toute comparaison dont la valeur de profil atteint la largeur de
colonne, plutôt que de la trancher.

**Précision de lecture relevée au passage** : cet algorithme est `iSSHA-1`,
avec 15000 itérations et un sel de 128 bits. Les six comptes portent la
version d'empreinte `H`, que la campagne précédente qualifiait de « format
moderne ». C'est exact relativement aux versions antérieures, et cela ne veut
pas dire SHA-256 : le fond est SHA-1, étiré. La nuance est rapportée, elle
n'est pas transformée en échec.

### 3. Le mandant que seul l'écran atteint

Le rapport des comptes standards lit **tous les mandants** depuis une seule
session, là où le canal RFC lit celui de sa connexion et se voyait refuser
l'ouverture sur le mandant de référence.

| Mandant | Compte | Pictogramme de verrouillage | Statut du mot de passe |
|---|---|---|---|
| `000` | `DDIC` | `@07@` | existe, non trivial |
| `000` | `SAP*` | `@07@` | existe, non trivial |
| `000` | `TMSADM` | `@07@` | existe, non trivial |
| `000` | `SAPCPIC` | (vide) | n'existe pas |
| `001` | `DDIC` | `@07@` | existe, non trivial |
| `001` | `SAP*` | `@07@` | existe, non trivial |
| `001` | `TMSADM` | (vide) | n'existe pas |
| `001` | `SAPCPIC` | (vide) | n'existe pas |

Deux constats que la campagne RFC ne pouvait pas produire : le mandant de
référence porte **quatre** comptes standards dont trois existants, et
`TMSADM` existe en `000` alors qu'il est absent en `001`. Aucun mot de passe
n'est trivial, sur aucun des deux mandants.

### 4. Deux colonnes qui ne se lisent pas comme des données

- La colonne de verrouillage rend `@07@`, un **identifiant d'icône**. Ce n'est
  ni un booléen ni un libellé : c'est ce que le client résout en image. Elle a
  une qualité, elle ne dépend pas de la langue, et un défaut, elle ne se lit
  pas seule. Tous les comptes existants portent le MÊME code, donc cette
  colonne ne discrimine rien à elle seule.
- La colonne de statut du mot de passe rend `Exists; Password not trivial.`,
  un **texte traduit**. La convention 3 du dépôt interdit d'asserter dessus :
  elle se rapporte.

Le pictogramme s'interprète en le CROISANT : sur le mandant `001`, le canal
RFC a mesuré que les comptes sont déverrouillés (masque à zéro). Le code
`@07@` y correspond donc à « non verrouillé », et cette interprétation, une
fois ÉTABLIE sur le périmètre commun, s'applique au mandant `000` où aucune
vérité de référence n'est disponible. C'est la méthode que la campagne encode,
et elle vaut au-delà de ce rapport.

### 5. L'effet observable, ce que seul le canal HTTP donne

| Contrôle | Déclaré (RFC) | Origine (écran) | Observé (HTTP) |
|---|---|---|---|
| drapeau `HttpOnly` des cookies | `3` | noyau | **aucun des 3 cookies** |
| transport chiffré | `snc/enable` à `0`, communication sécurisée `OFF` | noyau | **aucun cookie `Secure`**, même en HTTPS |
| en-têtes de sécurité de réponse | sans objet | sans objet | **aucun des 5** |

Les trois cookies posés à l'ouverture de session sont `sap-usercontext`,
`MYSAPSSO2` (le ticket d'authentification) et `SAP_SESSIONID_A4H_001`. Aucun
ne porte `HttpOnly`, donc aucun n'est hors de portée d'un script exécuté dans
la page.

**C'est le faux positif de conformité le plus net de toute la série, et il
n'est visible d'aucun autre canal.** Un audit qui lit le paramètre conclut que
les cookies sont protégés ; ils ne le sont pas.

Il en découle un enseignement qui dépasse ce paramètre : **la valeur d'un
paramètre de sécurité n'est pas un curseur**. On lit volontiers `3` comme
« plus durci que `0` », et l'observation le dément. Un contrôle écrit
« au moins 3 » serait vert et faux. Quelle que soit la sémantique officielle de
cette échelle, la campagne ne la suppose pas : elle constate que sur cette
cible, cette valeur ne produit pas ce drapeau.

### 6. Le maillon ICF du canal HTTP

| Mesure | Valeur |
|---|---|
| services OData publiés au catalogue | **58** |
| noeuds de services web actifs | 219 lignes, **193 noms distincts** |
| noeud portant le canal OData | actif |
| noeuds `webgui`, `its`, `bsp`, `ui2`, `public` | actifs |

Un service OData ne répond que si le noeud du dictionnaire de services qui le
porte est actif : la condition d'existence du troisième canal se mesure par le
deuxième, et elle est vérifiée.

**Défaut trouvé dans la campagne précédente par ce croisement** : la clé de ces
tables est COMPOSITE (noeud plus parent), et la jointure de la bibliothèque
indexait sur le seul nom. 324 noms sont portés par plusieurs noeuds, dont 18
aux propriétés différentes. Mesuré : **aucun noeud actif n'est concerné sur
cette cible**, et les écarts ne portent que sur la casse, donc les chiffres de
la campagne précédente tiennent. La jointure a néanmoins été corrigée, parce
que la propriété qui diverge ailleurs est justement celle qui compte ici, le
compte de service, et qu'elle dépend du parent.

### 7. Ce que l'écran ne donne pas non plus

La transaction d'affichage d'un paramètre rend ses détails dans des
**conteneurs HTML opaques** : le champ d'un paramètre y est illisible par
l'API de scripting, dont la perception ne voit qu'une zone utilisateur vide et
deux visionneuses. La question de l'origine d'un paramètre n'y trouve donc PAS
de réponse, et c'est le rapport (une grille ordinaire) qui la donne. Un canal
supplémentaire n'est pas une capacité supplémentaire partout : il l'est là où
il l'est, et le scénario 2 fige ce constat pour qu'il ne soit pas retenté.

## Scénarios

Treize scénarios (les douze ci-dessous plus l'inventaire des en-têtes de
sécurité, purement rapporteur). Chacun indique ce qu'il **ASSERTE** et ce
qu'il **RAPPORTE**.

### 1. La cible est la même sur les trois canaux

- **ASSERTE** : la release et le kernel lus par l'écran, par le RFC et par
  l'HTTP désignent la même cible, et ce n'est pas la release voisine.
- **Pourquoi d'abord** : le nom d'hôte est partagé par les deux conteneurs du
  poste et seul le port les distingue, sur l'écran comme sur le RFC. Un
  croisement entre deux systèmes différents produirait des écarts partout,
  tous faux.

### 2. La transaction d'affichage d'un paramètre est hors de portée de l'API

- **ASSERTE** : l'écran de détail ne porte aucun champ de valeur, et son
  contenu vit dans des conteneurs opaques.
- **RAPPORTE** : le chemin des conteneurs.
- **Pourquoi figer un manque** : sans ce scénario, la question « pourquoi ne
  pas lire l'origine directement sur l'écran du paramètre » se repose à chaque
  reprise du sujet. Il échoue le jour où la release rendrait ces champs
  lisibles, ce qui serait une bonne nouvelle à consigner.

### 3. Le rapport de paramètres porte les deux colonnes que le RFC n'a pas

- **ASSERTE** : le rapport rend les colonnes de profil ET de défaut, et son
  relevé n'est pas vide.
- **RAPPORTE** : le nombre de paramètres et la part substituée par le profil.
- **Pourquoi** : c'est l'assertion de méthode qui rend le scénario 4
  probant. Sans elle, un rapport vide ou amputé d'une colonne donnerait « zéro
  paramètre posé dans le profil », c'est-à-dire exactement la conclusion
  recherchée, obtenue sans rien mesurer.

### 4. Le durcissement de cette release vient du noyau, pas d'un réglage

- **ASSERTE** : aucun des paramètres de sécurité audités n'est posé dans le
  profil d'instance, et tous ont une valeur effective qui suit le défaut du
  noyau.
- **RAPPORTE** : le détail par paramètre.
- **Pourquoi c'est le coeur de la campagne** : les deux campagnes voisines
  constatent le durcissement sans pouvoir l'expliquer, et l'inscrivent
  explicitement dans ce qu'elles ne couvrent pas. La réponse change la lecture
  d'une dérive future.
- **Régime** : assertion de non-dérive. Le jour où un paramètre de sécurité
  apparaîtra dans le profil, ce scénario échouera, et ce sera le bon
  comportement : une décision humaine aura été prise.

### 5. Le profil l'emporte quand il existe

- **ASSERTE** : sur les témoins COMPARABLES (valeurs tronquées écartées), la
  part dont l'effectif suit le profil atteint le seuil de prépondérance
  déclaré dans la suite.
- **RAPPORTE** : les décomptes et les témoins écartés.
- **Pourquoi** : c'est la contre-épreuve du scénario 4. Sans elle,
  « aucun paramètre de sécurité modifié par le profil » pourrait vouloir dire
  que la colonne de profil n'est pas ce qu'on croit.
- **Ce que le seuil corrige** : la première écriture se contentait d'exiger
  qu'AU MOINS un témoin suive le profil, ce qui passait avec un seul cas sur
  vingt-cinq et ne prouvait donc aucune règle. La revue indépendante l'a
  relevé. Le seuil est une part, pas un nombre absolu, parce que le nombre de
  témoins comparables dépend de la cible.

### 6. La colonne de profil est tronquée, et la campagne le sait

- **ASSERTE** : des paramètres atteignent la largeur de colonne ; la
  troncature est **PROUVÉE** pour au moins l'un d'eux par le canal RFC (la
  valeur complète commence par la valeur coupée et est strictement plus
  longue) ; et aucun de ceux dont la troncature est prouvée n'est classé
  divergent.
- **RAPPORTE** : leur nombre et leurs noms.
- **Pourquoi** : une valeur coupée comparée à une valeur complète fabrique un
  écart qui n'existe pas. Le scénario fige le piège pour que personne ne
  « corrige » la garde en la trouvant trop prudente.
- **Ce que la preuve corrige** : la première écriture se contentait de
  vérifier que la bibliothèque déclarait « non comparables » les paramètres
  que la suite venait elle-même de sélectionner sur le même critère de
  longueur. C'était une tautologie, relevée par la revue indépendante : le
  canal RFC était interrogé mais son résultat n'entrait dans aucune
  assertion. La preuve par préfixe le fait entrer.

### 7. Le mandant de référence est mesuré par l'écran

- **ASSERTE** : le relevé porte plusieurs mandants dont celui de référence, et
  les comptes livrés attendus y sont présents.
- **RAPPORTE** : la fiche de chaque compte, mandant par mandant.
- **Pourquoi** : la campagne de surface consigne ce mandant comme hors de
  portée, connexion refusée. L'écran l'atteint depuis la session courante.

### 8. Le pictogramme de verrouillage s'interprète par croisement

- **ASSERTE** : le code d'icône est reconnu comme tel (donc jamais lu comme
  une donnée) ; le recoupement avec le masque mesuré par le RFC a bien lieu ;
  et il est **NON DISCRIMINANT** sur cette cible, donc aucun sens n'est
  traduit.
- **RAPPORTE** : les codes vus, le nombre de lignes recoupées, et les lignes
  que seul l'écran atteint, laissées ININTERPRÉTÉES.
- **Pourquoi la méthode vaut plus que le résultat** : un pictogramme ne se
  devine pas ; il se recoupe là où c'est possible, puis s'applique là où ça ne
  l'est pas. Encore faut-il que le recoupement DISCRIMINE.
- **Et sur cette cible, il ne discrimine pas.** Les lignes recoupées portent
  toutes le même code et le même état, donc « ce code signifie non
  verrouillé » y est indiscernable de « ce code signifie que la ligne
  existe », hypothèse d'autant plus soutenue que les cellules vides sont
  exactement les comptes inexistants. La première écriture de ce scénario
  concluait pourtant que le sens était « établi sans ambiguïté » et
  l'appliquait au mandant de référence : c'était une extrapolation habillée en
  croisement, relevée par la revue indépendante. La bibliothèque a gagné un
  état sûr `not_discriminating` (il faut deux codes distincts ou les deux
  états observés), et le scénario asserte désormais l'honnête : le sens n'est
  PAS établi ici.
- **Ce que le scénario garde de sa valeur** : il fige la méthode et il
  échouera le jour où un second code ou un compte verrouillé apparaîtra,
  c'est-à-dire le jour où le sens DEVIENDRA établissable.

### 9. Le statut des mots de passe est rapporté, jamais asserté

- **ASSERTE** : rien sur le texte. Seulement que la colonne est renseignée
  pour les comptes existants.
- **RAPPORTE** : le statut de chaque compte des deux mandants.
- **Pourquoi** : ce libellé est traduit (convention 3). L'asserter rendrait la
  suite dépendante de la langue de la session, et le premier passage sur un
  système en allemand la ferait rougir pour une raison sans rapport avec la
  sécurité.

### 10. Le paramètre qui protège les cookies ne produit pas son effet

- **ASSERTE** : l'observation a EU LIEU (des cookies ont été posés), et le
  verdict de confrontation est celui mesuré.
- **RAPPORTE** : les cookies sans drapeau, sans `Secure`, et les en-têtes de
  sécurité absents.
- **Pourquoi c'est le second résultat de la campagne** : le paramètre est
  positionné, son origine est connue, et l'effet n'est pas là. Aucun des deux
  autres canaux ne peut le voir. La première assertion est la plus importante :
  sans cookie observé, le résumé serait vide et se lirait comme « aucun cookie
  non protégé ».
- **Ce que le scénario n'asserte PAS** : il n'exige ni `Secure` ni en-têtes de
  sécurité. Les exiger d'un banc servi en clair rendrait la suite rouge à vie,
  donc désactivée.

### 11. Le canal HTTP repose sur un noeud que le canal RFC mesure

- **ASSERTE** : le noeud de services qui porte le canal OData est actif, et le
  catalogue publie des services.
- **RAPPORTE** : le nombre de services publiés, le nombre de noeuds actifs, et
  l'écart entre lignes et noms distincts.
- **Pourquoi** : c'est la seule dépendance de canal à canal de la campagne, et
  elle est vérifiée plutôt que supposée.

### 12. Le croisement tient dans un artefact rejouable

- **ASSERTE** : l'empreinte se recalcule à la relecture, le périmètre haché
  est celui déclaré, et changer une valeur volatile ne change pas l'empreinte.
- **RAPPORTE** : le chemin de l'artefact.
- **Pourquoi** : la leçon de la campagne précédente, dont l'artefact portait la
  date de lecture dans son périmètre haché et n'était donc pas déterministe
  d'un jour à l'autre. La contre-épreuve est JOUÉE, pas affirmée.

## Points de vigilance pour la génération

1. **Le port distingue les cibles, le nom d'hôte non.** Sur les trois canaux.
2. **La colonne de profil du rapport est tronquée à 60 caractères** sans
   marqueur.
3. **Un code d'icône n'est pas une donnée**, et une colonne qui ne porte qu'un
   seul code ne discrimine rien.
4. **Un libellé d'état est une traduction** (convention 3).
5. **Une observation absente ne vaut jamais une conformité** : un relevé de
   cookies vide n'est pas un système protégé.
6. **La valeur d'un paramètre de sécurité n'est pas un curseur.** Aucun
   contrôle de la campagne ne compare une valeur déclarée à un seuil.
7. **Le mot de passe ne transite pas par le serveur MCP** : la session est
   ouverte en ligne de commande et la suite s'y rattache.

Conventions : 1 (aucun nom de rapport, de colonne ni de localisateur dans la
suite), 3, 11, 12 (les cinq capacités de cette campagne sont dans `src/` avec
leurs tests hors SAP), opt-in par tag et saut propre, lecture seule stricte.

## Revue indépendante

Relue par `sap-verifier` après une première validation live (13/13). Verdict
initial : **`needs_human`**, huit réserves. Toutes traitées, la suite rejouée
13/13 après correction. Quatre étaient hors d'atteinte de l'exécution,
puisqu'elle passait.

| Réserve | Nature | Traitement |
|---|---|---|
| Le lecteur de cookies n'était couvert par aucun test, et un lecteur aveugle produirait EXACTEMENT la conclusion publiée | défaut de méthode, le plus grave | onze tests hors SAP sur le chemin réellement emprunté, dont la contre-épreuve POSITIVE (un cookie protégé doit être vu comme tel) ; le test a immédiatement trouvé un vrai défaut, la lecture ratait trois orthographes du drapeau sur cinq |
| Le verdict cookie ignorait le statut du paramètre : un nom inconnu rendait le même verdict vert | défaut réel | garde `Security Parameters Should Be Known` ajoutée, et observation propre au scénario au lieu de relire celle du scénario 1 |
| Le scénario de troncature relisait son propre critère de sélection | tautologie | preuve par préfixe via le canal RFC, promue en `proven_truncations` |
| Le pictogramme était déclaré « établi » sans aucun contraste | extrapolation | état sûr `not_discriminating` dans la bibliothèque, scénario retourné pour asserter l'honnête |
| La contre-épreuve passait avec un seul témoin sur vingt-cinq | assertion trop faible | seuil de prépondérance sur les témoins comparables |
| Deux sélecteurs et une largeur codés en dur dans la suite | convention 12 | promus en `truncated_profile_names` et `discriminating_parameter_names` |
| Colonnes techniques et chemin de service dans la suite | convention 1 | promus dans la resource |
| Session HTTP jamais fermée | hygiène | teardown qui ferme les deux canaux ouverts, chacun tenté même si l'autre échoue |

Trois remarques sont des **arbitrages assumés** : le couplage entre scénarios
par variables de suite (patron déjà en usage dans le dépôt, au prix qu'un
scénario ne se rejoue pas seul), le scénario 11 qui recoupe partiellement sa
campagne voisine, et l'assertion d'en-têtes qui reste purement rapporteuse.

## Ce qui n'est PAS couvert

1. **La sémantique officielle de l'échelle du paramètre de cookies.** La
   campagne constate que la valeur mesurée ne produit pas le drapeau ; elle ne
   prétend pas dire ce que chaque valeur de l'échelle signifie, faute de
   source lisible par un canal (la documentation vit dans le conteneur opaque
   du scénario 2).
2. **Les autres mandants que `000` et `001`.** La cible n'en porte pas
   d'autres.
3. **Le contenu des services OData publiés.** La campagne compte le catalogue
   et vérifie le noeud qui le porte ; elle n'appelle aucun service métier.
4. **Le statut des mots de passe hors comptes livrés par SAP.** Le rapport
   utilisé ne couvre que ceux-là.
5. **L'effet des en-têtes absents.** La campagne constate qu'ils ne sont pas
   posés ; elle ne mesure pas ce qu'un navigateur en ferait.
6. **Les 5 paramètres dont l'effectif suit le défaut alors que le profil porte
   une autre valeur.** Mesurés, rapportés, non expliqués : ce sont peut-être
   des paramètres non dynamiques dont le profil a changé depuis le dernier
   démarrage, mais rien dans les mesures ne le prouve. C'est pourquoi le
   scénario 5 asserte une PRÉPONDÉRANCE et non une unanimité.
7. **L'équivalence « colonne de défaut = défaut du NOYAU ».** Elle est
   supposée, pas mesurée, et la revue indépendante l'a relevé. Un système ABAP
   a une hiérarchie de profils, et le rapport ne dit pas si la valeur par
   défaut est compilée dans le noyau ou héritée d'un profil par défaut. La
   transaction qui trancherait est justement celle que le scénario 2 déclare
   illisible. Ce qui est ÉTABLI est donc : aucun réglage du profil d'instance
   ne modifie la posture de sécurité de cette cible. L'attribution au kernel
   793 en particulier, plutôt qu'à la release 758, n'est pas séparée non plus.
8. **L'explication des onze écarts entre la 754 et la 758.** Elle exigerait la
   même mesure d'origine sur la 754, et cette campagne est mono-cible. Ce que
   la mesure autorise à dire s'arrête à cette cible.
