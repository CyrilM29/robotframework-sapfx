# Configuration de sécurité par le canal RFC (cible ABAP Platform 2023)

- **Canal** : RFC (`SapApiLibrary`, `pyrfc`), le canal sans écran et sans HTTP.
  Aucun écran n'est piloté, aucune requête HTTP n'est émise.
- **Système observé** : ABAP Platform 2023 en conteneur, release **758**, kernel
  **793**, composant de base `SAP_BASIS` en release 758 niveau de correctifs
  0002, **14 composants logiciels** inventoriés, mandant `001`, utilisateur
  `DEVELOPER`, langue `EN`. Cible jointe à travers un **relais TCP local**
  (`127.0.0.2`), qui réaligne le port et le numéro d'instance.
- **Exploration live** : 2026-08-29, **hors rf-mcp**. Le serveur MCP du poste
  tourne sous un interpréteur qui n'a pas `pyrfc` (aucune roue précompilée
  au-delà de Python 3.12), donc l'exploration est passée par des sondes RFC
  directes dans un interpréteur compatible, puis par la suite elle-même.
- **État de ce plan** : écrit APRÈS l'exploration et la génération. La suite
  `tests/robot/api/secu_configuration_abap2023.robot` existe et passe **16/16**
  en direct, sur deux exécutions consécutives. Ce document formalise ce qui a
  été mesuré, il ne décrit pas une intention.
- **Posture** : LECTURE SEULE de bout en bout. Aucun paramètre n'est écrit,
  aucun compte n'est touché, aucune destination n'est ouverte, aucun secret de
  destination n'est lu.

## Pourquoi une jumelle plutôt qu'une suite paramétrée

Cette campagne a une jumelle, `specs/secu-configuration-a4h.md`, et les deux ne
sont pas une suite dupliquée : elles partagent le vocabulaire
(`resources/security_keywords.resource`) et divergent par leur **baseline**,
parce que les deux releases du banc ne sont pas durcies pareil.

Mesuré le 2026-08-29, cette release est nettement plus durcie que la 1909 : dix
caractères de mot de passe contre six, les quatre exigences de composition
armées là où l'autre les laisse toutes à zéro, un hachage des mots de passe
quinze fois plus itéré, une déconnexion automatique des sessions inactives à
une heure là où l'autre n'en a aucune, un démarrage distant de programmes
désactivé là où l'autre le laisse ouvert.

Une suite unique paramétrée aurait dû choisir entre asserter la posture la plus
faible, donc rester aveugle sur cette cible, et asserter la plus forte, donc
rester rouge à vie sur l'autre. Une suite rouge en permanence finit désactivée :
c'est la raison de fond du découpage.

**Ce qui se CONFIRME identique est un résultat aussi.** Journal d'audit armé et
protégé, passerelle sous liste de contrôle, contrôle d'autorisation RFC armé,
compte `SAP*` codé en dur neutralisé, mandant de référence verrouillé, transport
en clair, et jusqu'aux inventaires (mêmes trois destinations à logon stocké,
même régime d'audit sans filtre) : ces contrôles-là sont donc bloquants des deux
côtés, et l'affirmer demandait de les mesurer sur deux releases, pas sur une.

## Le parti pris de jugement, et il décide de tout le reste

Une campagne de sécurité rejouable ne juge pas « ce système est-il durci ». Ce
jugement dépend d'une politique d'entreprise, il est faux sur un bac à sable, et
il produit un verdict permanent que personne ne relit.

Elle juge trois choses qui, elles, ont une réponse binaire :

1. **les contrôles dont l'écart serait un incident quelle que soit la politique
   d'entreprise** sont ASSERTÉS ;
2. **les inventaires dont l'apparition d'une entrée est l'événement à voir**
   sont assertés contre leur valeur mesurée (destinations porteuses d'un logon,
   régime du journal d'audit, niveau de correctifs) : ce sont des assertions de
   NON-DÉRIVE, pas de conformité ;
3. **tout le reste est MESURÉ et RAPPORTÉ**, jamais transformé en échec, et
   c'est la sentinelle de dérive qui rend visible un changement.

Sur cette cible, la frontière du premier régime se déplace par rapport à la
jumelle, et c'est délibéré : la politique de mot de passe, la déconnexion
automatique et le démarrage distant de programmes sont ASSERTÉS ici, alors
qu'ils ne peuvent être que rapportés sur la 1909. La raison n'est pas qu'ils
comptent davantage, c'est qu'ils sont **armés sur cette cible** et qu'un retour
en arrière y serait un affaiblissement réel et constatable, pas un désaccord de
politique.

Chaque scénario ci-dessous dit lequel des trois régimes il applique.

## Préconditions

1. **Le relais TCP local doit être levé AVANT toute exécution**, et ce n'est pas
   un détail d'environnement. Le protocole DÉRIVE le port du numéro d'instance,
   or ce conteneur publie ses ports décalés : viser directement le port publié
   obligerait à annoncer un numéro d'instance que l'instance interne ne porte
   pas. Le relais réaligne les deux.
   **Le piège, et il est majeur** : sans relais, l'adresse visée répond quand
   même (la boucle locale couvre toute sa plage et l'autre conteneur écoute
   partout), donc la campagne parlerait à la release 754 en croyant auditer la
   758. Comme les deux conteneurs annoncent le même identifiant système et le
   même nom d'hôte applicatif, rien dans la réponse ne le trahirait. Le
   scénario 1 existe pour attraper exactement cela.
2. **Interpréteur Python 3.10 à 3.12** portant `pyrfc`, et un runtime NW RFC.
   Le canal est **optionnel** : sur un poste sans lui, la campagne se SAUTE au
   lieu de rougir.
3. **Identifiants par la ligne de commande** (convention 11). Aucun mot de
   passe n'est écrit ici ni dans une suite : `-v "RFC_PASSWORD: Secret:…"`. La
   garde de présence ne MESURE jamais le secret. Les identifiants de cette
   cible ne sont pas ceux de la 1909.
4. **Une référence de dérive committée pour CETTE cible**
   (`tests/robot/security_baselines/posture-abap2023-758.json`). Au premier
   passage elle n'existe pas : elle est ÉCRITE avec un avertissement, à relire
   et à committer. Les références des deux cibles ne se mélangent jamais, sinon
   la différence de durcissement entre deux releases passerait pour une dérive.
5. **La campagne lit le mandant de connexion** (`001`). Les lectures de tables
   d'administration portent sur ce mandant : en lire un autre demande une autre
   connexion.

## Données observées

Tout ce qui suit est mesuré le 2026-08-29 sur la cible décrite plus haut.
Ce qui n'a pas été mesuré est listé en fin de document, pour qu'aucune absence
de mesure ne passe pour une absence de problème.

### 1. Identité : ce qui prouve la cible, et ce qui ne prouve rien

Le poste héberge **deux** conteneurs ABAP, et trois valeurs qu'on croirait
discriminantes ne le sont pas.

| Attribut | Valeur relevée | Discrimine la cible ? |
|---|---|---|
| release du partenaire | `758` | **oui** |
| release kernel | `793` | **oui** |
| composant de base `SAP_BASIS` | release 758, niveau de correctifs 0002 | **oui** |
| nombre de composants logiciels | 14 | **oui** |
| identifiant système | `A4H` | **non**, les deux conteneurs l'annoncent |
| nom d'hôte applicatif | `vhcala4h` | **non**, les deux l'annoncent |
| nom d'instance (`rdisp/myname`) | identique sur les deux cibles | **non** |

Sur cette cible, ce n'est pas une précaution théorique : c'est la garde du
relais. Sans lui, la campagne mesurerait la release 754 avec un identifiant
système, un nom d'hôte et un nom d'instance rigoureusement identiques à ceux
qu'elle attend. L'inventaire des composants est la seule ancre d'identité RICHE,
et il compte quatre composants de plus que sur la 1909.

### 2. Périmètre du relevé de posture

Le relevé complet compte **42 paramètres de profil**, répartis en six lots
thématiques déclarés dans la couche vocabulaire : politique de mot de passe
(14), protection de la connexion (7), journal d'audit (5), passerelle (6), RFC
et autorisations (5), sécurité du transport (5). Mesuré sur cette cible : **les
42 sont reconnus**, donc aucun ne remonte comme non mesurable, ce qui est la
condition d'un jugement honnête (voir le scénario 4). Les deux releases
reconnaissent exactement le même périmètre : aucune différence de VOCABULAIRE
entre elles, seulement des différences de POSTURE.

Ces 42 lectures sont exactement ce que la référence de dérive committée
contient : le périmètre du rapport et celui de la sentinelle sont le même, par
construction.

### 3. Ce que cette release durcit, et que la 1909 laisse ouvert

| Paramètre | Cette cible (758) | Cible A4H (754) |
|---|---|---|
| `login/min_password_lng` | `10` | `6` |
| `login/min_password_digits` | `1` | `0` |
| `login/min_password_letters` | `1` | `0` |
| `login/min_password_lowercase` | `1` | `0` |
| `login/min_password_uppercase` | `1` | `0` |
| `login/min_password_diff` | `3` | `1` |
| `login/password_history_size` | `15` | `5` |
| `login/password_hash_algorithm` | `iterations=15000, saltsize=128` | `iterations=1024, saltsize=96` |
| `rdisp/gui_auto_logout` | `3600` | `0` |
| `gw/rem_start` | `DISABLED` | `REMOTE_SHELL` |
| `login/isolate_rfc_system_calls` | `1` | `0` |

Onze paramètres, et c'est la matière du découpage en deux suites. Trois d'entre
eux deviennent des assertions sur cette cible : la politique de mot de passe
(scénario 8), la déconnexion automatique (scénario 9) et le démarrage distant
de programmes (scénario 6).

Le paramètre de hachage est une **chaîne composée** (encodage, algorithme,
itérations, taille de sel) : la sentinelle la compare en entier, et un
comparateur numérique appliqué à cette valeur serait un défaut du contrôle, pas
une non-conformité du système. C'est aussi pour cela qu'il est surveillé et non
asserté, alors qu'il porte l'un des plus gros écarts de durcissement du banc.

### 4. Ce qui est mesuré IDENTIQUE sur les deux cibles du banc

| Paramètre | Valeur mesurée |
|---|---|
| `rsau/enable` | `1` |
| `rsau/integrity` | `1` |
| `rsau/selection_slots` | `10` |
| `gw/acl_mode` | `1` |
| `gw/reg_no_conn_info` | `1` |
| `auth/rfc_authority_check` | `1` |
| `rfc/callback_security_method` | `1` |
| `login/no_automatic_user_sapstar` | `1` |
| `login/fails_to_user_lock` | `5` |
| `login/fails_to_session_end` | `3` |
| `login/password_expiration_time` | `0` |
| `snc/enable` | `0` |
| `system/secure_communication` | `OFF` |
| `rec/client` | `OFF` |
| `icf/set_HTTPonly_flag_on_cookies` | `3` |
| `http/security_session_timeout` | `1800` |

Le durcissement de cette release **ne s'étend pas au transport** : il n'est pas
chiffré (`snc/enable` à `0`, `system/secure_communication` à `OFF`), et les mots
de passe n'expirent jamais. Ces trois valeurs sont rapportées, surveillées par
la sentinelle, et jamais transformées en échec : c'est une posture de banc, et
l'écart avec une politique de production se lit dans le rapport plutôt que dans
un test rouge.

### 5. Ce qui a rejoint le périmètre, et ce qui reste dehors

Trois paramètres relevés à l'exploration ont été **ajoutés aux lots
surveillés** après une première passe qui les laissait dehors :
`login/password_hash_algorithm` (celui qui porte l'écart d'itérations),
`rfc/callback_security_method` et `http/security_session_timeout`. Le relevé
est ainsi passé de 39 à 42 paramètres, les références de dérive ont été
régénérées et les deux suites rejouées.

Deux relevés restent **délibérément hors périmètre**, et il faut savoir
pourquoi :

| Relevé | Cette cible (758) | Cible A4H (754) | Pourquoi dehors |
|---|---|---|---|
| `ms/http_logging` | `1` | `0` | aucun des six lots thématiques ne lui convient sans déformer le découpage |
| lignes de la liste noire des modules appelables à distance | `9010` | `524` | c'est une **table**, pas un paramètre de profil : hors du mécanisme de la sentinelle |

La liste noire est donc le **seul candidat d'extension restant** de cette
campagne. C'est aussi l'écart le plus spectaculaire entre les deux releases, et
il n'est aujourd'hui vu par aucun test.

### 6. Mandants

Cette cible porte deux mandants.

| Mandant | Catégorie (`CCCATEGORY`) | Verrou de copie et d'écrasement (`CCCOPYLOCK`) | Indicateur de correction (`CCCORACTIV`) |
|---|---|---|---|
| `000` | `S` | positionné (`X`) | non relevé |
| `001` | `D` (la 1909 porte `C`) | **vide** : le mandant de travail n'a pas ce verrou | `3` (la 1909 porte `1`) |

Seul le mandant de référence porte le verrou de copie, et c'est le cas sur les
deux cibles. Trois indicateurs (`CCNOCLIIND`, `CCIMAILDIS`, `CCTEMPLOCK`) sont
**vides sur les quatre mandants des deux systèmes**. Deux d'entre eux ont été
relevés à l'exploration hors de la projection que lit la campagne : elle lit le
mandant, son texte, sa catégorie, `CCCOPYLOCK`, `CCNOCLIIND` et `CCCORACTIV`.

La catégorie du mandant de travail et son indicateur de correction divergent
entre les deux cibles : c'est une propriété de l'image livrée, pas un défaut, et
c'est pour cela que le scénario 13 les rapporte au lieu de les asserter.

### 7. Comptes

| Mesure | Cette cible | Cible A4H |
|---|---|---|
| comptes du mandant `001`, tous comptes confondus | 6 | 5 |
| comptes verrouillés | **aucun** | aucun |
| rattachement de groupe dominant | `SUPER` | `SUPER` |
| `SAP*` et `DDIC` | présents et déverrouillés | idem |
| `EARLYWATCH`, `TMSADM`, `SAPCPIC`, `SAPSUPPORT` | absents du mandant `001` | idem |
| attributions du profil `SAP_ALL` | 5 | 5 |
| attributions du profil `SAP_NEW` | **aucune** | aucune |

La lecture porte bien sur les deux profils critiques : les cinq lignes rendues
par cible sont toutes `SAP_ALL`, donc l'absence d'attribution de `SAP_NEW` est
un **résultat mesuré**, pas une absence de mesure.

Le durcissement supérieur de cette release **ne se voit pas du tout sur les
comptes** : ils sont tous déverrouillés, comme sur la 1909, et presque tous
rattachés au groupe des super-utilisateurs. C'est un rappel utile de ce que
mesure un paramètre de profil : la politique, pas son application aux comptes
existants.

### 8. Destinations RFC et relations de confiance

| Mesure | Cette cible | Cible A4H |
|---|---|---|
| destinations déclarées | 45 | 43 |
| dont destinations de type `3` (ABAP) | 5 | 5 |
| destinations de type `3`, `G` ou `H` (celles qui peuvent porter un logon) | 9 | 9 |
| dont destinations à **logon stocké** | 3 | 3 |
| dont destinations à **mot de passe en stockage sécurisé** | 2 | 2 |
| tables de confiance (`RFCTRUST`, `RFCSYSACL`, ACL modernes) | **toutes vides** | toutes vides |

Les contenus d'options des destinations sont **identiques mot pour mot** entre
les deux systèmes, et le nombre de trois destinations à logon stocké est
asserté par les deux suites, qui passent : le relevé est donc confirmé deux
fois, par la mesure et par l'exécution. C'est l'un des rares domaines où les
deux images ne divergent en rien.

Aucune relation de confiance n'est configurée sur le banc : c'est un fait
mesuré, et il vaut d'être écrit, parce qu'une campagne qui ne trouve rien dans
ces tables doit pouvoir distinguer « rien n'est configuré » de « la lecture n'a
pas eu lieu ».

L'information « cette destination conserve un logon » n'est pas dans une
colonne : elle est enfouie dans un agrégat de marqueurs mono-lettres, dont
seuls ceux dont la signification est établie sont interprétés (hôte, numéro de
système, mandant, utilisateur de connexion, langue, port, plus la marque d'un
mot de passe en stockage sécurisé). Les autres sont **ignorés plutôt que
devinés** : sur un inventaire de sécurité, une interprétation approximative
vaut moins que l'absence d'interprétation, parce qu'elle serait lue comme un
fait.

### 9. Le constat d'audit, et il est inconfortable

`rsau/enable` vaut `1` sur les deux cibles, et `rsau/selection_slots` annonce
dix emplacements de filtrage. La lecture de la configuration d'audit par son
interface dédiée dit autre chose : **dix emplacements déclarés, aucun actif**,
y compris sur cette release mieux durcie. Le régime mesuré est donc « armé sans
filtre » : le journal est armé au niveau du noyau et ne filtre rien, donc il
n'enregistre pas ce qu'un lecteur du seul paramètre croit qu'il enregistre.

C'est le faux positif de conformité le plus coûteux de ce domaine, et c'est
pour cela que la campagne sépare les deux questions : le scénario 5 asserte
l'armement, le scénario 10 mesure le filtrage et rapporte le régime.

## Scénarios

Seize scénarios, dans l'ordre de la suite. Chacun indique ce qu'il **ASSERTE**
(un échec est un incident ou une dérive à acquitter) et ce qu'il se contente de
**RAPPORTER** (une mesure consignée, surveillée par la sentinelle du
scénario 16). Les scénarios 6, 8 et 9 sont ceux qui assertent davantage que sur
la cible jumelle.

### 1. La cible est bien celle que la campagne croit auditer

- **Étapes** :
  1. Ouvrir le canal de lecture de la posture sur l'adresse du relais.
  2. Lire l'identité que le système publie sur lui-même.
- **ASSERTE** : la release et le kernel sont ceux de cette cible, et la release
  lue **n'est pas** celle du conteneur voisin du poste.
- **RAPPORTE** : rien d'autre.
- **Pourquoi ce scénario est le premier, et pourquoi il compte plus ici** : le
  risque est CONCRET, pas théorique. Si le relais TCP n'est pas posé, l'adresse
  visée répond quand même et c'est l'autre conteneur qui parle. Les quinze
  scénarios suivants seraient alors verts, mesureraient la posture de la 1909 et
  la rapporteraient sous le nom de la 758. L'échec du scénario 1 doit donc
  nommer cette cause en premier : c'est la plus probable.

### 2. Un paramètre inconnu est rendu non mesurable, jamais vide

- **Étapes** :
  1. Demander la lecture d'un paramètre de profil qui n'existe nulle part.
  2. Demander la lecture d'un paramètre réel du même préfixe.
- **ASSERTE** : le paramètre inventé sort avec le statut « non mesurable » et
  une valeur nulle ; le paramètre réel sort « mesuré » avec une valeur non
  nulle. Les deux sens sont joués, pas seulement le premier.
- **RAPPORTE** : rien.
- **Pourquoi le rejouer sur cette release aussi** : le comportement est une
  propriété du module de lecture, pas de la version, mais une campagne qui
  l'affirme sans l'avoir mesuré des deux côtés ne fait que le supposer. Il a
  donc été mesuré ici également, et le scénario le fige.
- **Le piège lui-même** : le module ne refuse PAS un nom qu'il ne connaît pas,
  il rend un code de retour non nul et une **chaîne vide**, indiscernable d'un
  paramètre légitimement vide. Un contrôle qui lit la valeur sans regarder le
  code de retour est donc vert sur une faute de frappe, et affirme une absence
  de durcissement qu'il n'a jamais mesurée.

### 3. Le nom d'un paramètre est sensible à la casse, et c'est un piège muet

- **Étapes** :
  1. Lire un paramètre réel dans sa casse exacte.
  2. Lire le même paramètre en majuscules.
- **ASSERTE** : la forme exacte mesure, la forme en majuscules ne mesure pas
  (statut « non mesurable », valeur nulle).
- **RAPPORTE** : rien.
- **Pourquoi** : normaliser un identifiant ABAP en majuscules est un réflexe, et
  le dépôt contient déjà un normaliseur qui capitalise, destiné aux noms de
  champs. L'employer ici ferait remonter TOUS les paramètres comme non
  positionnés, avec un code de retour plausible et sans le moindre message : le
  rapport conclurait à un système sans aucun durcissement, ce qui serait
  particulièrement absurde sur la cible la mieux durcie du banc.

### 4. Tous les paramètres audités sont reconnus par cette release

- **Étapes** : lire le relevé complet de posture (les six lots en une fois) et
  vérifier qu'aucune lecture ne revient sans valeur effective.
- **ASSERTE** : aucun des 42 paramètres n'est non mesurable.
- **RAPPORTE** : le relevé complet, réutilisé par les scénarios suivants et par
  la sentinelle.
- **Pourquoi, et c'est le scénario clé d'une campagne multi-release** : il
  sépare « le système n'est pas durci » de « le contrôle vise un paramètre
  absent de cette release ». Sans lui, une différence de VOCABULAIRE entre deux
  versions se lirait comme une différence de POSTURE. Mesuré : les deux
  releases reconnaissent le même périmètre, donc les onze écarts de la
  section 3 sont bien des écarts de posture.

### 5. Le journal d'audit de sécurité est actif

- **Étapes** : lire le lot du journal d'audit, déclarer les deux contrôles
  (journal armé, journal protégé contre la modification), confronter.
- **ASSERTE** : zéro écart ET zéro contrôle non mesurable.
- **RAPPORTE** : les autres paramètres du lot.
- **Pourquoi bloquant** : sans journal d'audit, aucun incident de sécurité n'est
  reconstituable après coup, et cela ne dépend d'aucune politique d'entreprise.
  Identique sur les deux releases, donc bloquant des deux côtés.
- **Limite explicite, levée par le scénario 10** : ce contrôle porte sur le
  paramètre du noyau, pas sur le filtrage réel.

### 6. La passerelle RFC est sous liste de contrôle, et le démarrage distant est désactivé

- **Étapes** : lire le lot de la passerelle, déclarer les trois contrôles (liste
  de contrôle armée, durcissement des informations de connexion, démarrage
  distant de programmes désactivé), confronter, puis journaliser le rapport de
  posture.
- **ASSERTE** : zéro écart sur les **trois** contrôles. Le troisième est propre
  à cette cible : le démarrage distant y est mesuré désactivé, alors que la 1909
  le laisse à sa valeur permissive, où il ne peut qu'être rapporté.
- **RAPPORTE** : le rapport de posture complet dans le journal Robot, chemins
  des fichiers de liste de contrôle compris.
- **Pourquoi bloquant** : une passerelle sans liste de contrôle accepte
  l'enregistrement de serveurs RFC arbitraires, le chemin d'entrée le plus
  classique sur un système ABAP. Et un démarrage distant de programmes réactivé
  sur une cible qui l'avait désactivé est un affaiblissement constatable, pas un
  désaccord de politique.

### 7. Le compte SAP* codé en dur est neutralisé et l'autorisation RFC est armée

- **Étapes** : lire les deux paramètres, déclarer les deux contrôles,
  confronter.
- **ASSERTE** : zéro écart.
- **RAPPORTE** : rien de plus.
- **Pourquoi bloquant** : le compte `SAP*` codé en dur du noyau ignore la table
  des utilisateurs et porte tous les droits ; le contrôle d'autorisation RFC,
  désarmé, laisse appeler n'importe quel module à distance. Les deux protections
  se confirment identiques d'une release à l'autre.

### 8. La politique de mot de passe de cette release est plus stricte que celle de la 1909

- **Étapes** : lire le lot de politique de mot de passe, déclarer les cinq
  contrôles (longueur minimale, puis les quatre exigences de composition),
  confronter, journaliser le rapport.
- **ASSERTE** : zéro contrôle non mesurable ET zéro écart. Les seuils sont
  gravés : dix caractères, et au moins une occurrence exigée pour chacune des
  quatre classes de caractères.
- **RAPPORTE** : le reste du lot, dont l'historique de quinze mots de passe,
  l'écart minimal de trois caractères entre deux mots de passe successifs, le
  hachage à 15000 itérations et l'absence d'expiration.
- **Pourquoi ce régime ici, et pas sur la jumelle** : ces seuils ont été mesurés
  ARMÉS sur cette release. Les asserter ne grave pas une politique d'entreprise
  arbitraire, cela grave l'état constaté d'une cible : un retour en arrière
  serait un affaiblissement réel, et c'est exactement ce qu'un test doit
  attraper. Sur la 1909, où tout est à zéro, asserter les mêmes seuils rendrait
  la suite rouge à vie, et asserter la valeur mesurée reviendrait à graver la
  faiblesse comme une cible.
- **Points de vigilance** : les seuils vivent en variables de la suite, pas en
  dur dans les contrôles, pour que l'écart entre les deux campagnes se lise d'un
  coup d'oeil.

### 9. La déconnexion automatique des sessions inactives est armée

- **Étapes** : lire le paramètre de déconnexion automatique, déclarer le
  contrôle, confronter.
- **ASSERTE** : la déconnexion automatique est armée.
- **RAPPORTE** : sa valeur (une heure sur cette cible).
- **Pourquoi ce scénario existe sur cette cible seulement** : c'est le second
  écart mesuré avec la 1909, et le plus visible à l'usage. Une session de
  dialogue abandonnée sur un poste non verrouillé est un accès complet au
  système. La jumelle ne peut que rapporter ce paramètre, puisqu'il y vaut zéro.
- **Points de vigilance** : le contrôle porte sur « armé », pas sur une durée
  exacte. Graver la valeur ferait échouer la suite le jour où l'exploitant
  raccourcirait le délai, donc renforcerait la posture.

### 10. Le journal d'audit est armé, mais il faut savoir s'il FILTRE

- **Étapes** : lire la configuration réelle du journal d'audit (armement,
  emplacements déclarés, emplacements actifs, régime), puis journaliser le
  constat.
- **ASSERTE** trois choses : le journal est armé ; le verdict est **cohérent**
  avec le décompte (filtrant implique au moins un emplacement actif, non
  filtrant implique zéro), seule incohérence qui trahirait une lecture cassée ;
  et le **régime mesuré n'a pas changé** (armé sans filtre sur cette cible).
- **RAPPORTE** : le nombre d'emplacements déclarés et actifs, avec un
  avertissement explicite quand le journal est armé sans filtre.
- **Pourquoi ce scénario est le complément indispensable du scénario 5** : le
  paramètre du noyau répond « armé », ce qui est vrai et insuffisant. Dix
  emplacements sont déclarés et aucun n'est actif, y compris sur la cible la
  mieux durcie du banc, donc le journal n'enregistre pas ce qu'un auditeur croit
  qu'il enregistre.
- **Ce que le scénario n'exige PAS, et pourquoi** : il ne réclame pas
  d'emplacement actif. L'exiger rendrait la suite rouge à vie sur ce banc.
  L'assertion de régime est en revanche une assertion de non-dérive : le jour
  où un filtrage sera configuré, elle échouera, et c'est le comportement voulu,
  la baseline du scénario devant alors être mise à jour comme on re-commit une
  référence après une dérive assumée.

### 11. Les destinations qui conservent un logon sont inventoriées

- **Étapes** : lire l'inventaire des destinations susceptibles de porter un
  logon (types ABAP et HTTP), les classer, puis journaliser le résumé.
- **ASSERTE** : le nombre de destinations à logon stocké est celui mesuré
  (trois sur cette cible, comme sur la jumelle), et aucune destination ne
  conserve un mot de passe sans porter de logon, incohérence qui signalerait une
  lecture douteuse.
- **RAPPORTE** : le résumé complet (total par type, noms des destinations
  porteuses).
- **Pourquoi le nombre est asserté** : une destination qui stocke un logon vers
  un autre système est un chemin d'élévation, qui atteint ce système atteint
  l'autre sans présenter d'identifiant. L'APPARITION d'une telle destination est
  exactement l'événement que ce contrôle existe pour voir, donc c'est une
  assertion de non-dérive, pas de conformité.
- **Limite assumée** : la campagne constate qu'un secret existe, elle ne le lit
  JAMAIS, et elle n'interprète que les marqueurs d'options dont la
  signification est établie.

### 12. Le niveau de correctifs des composants n'a pas reculé

- **Étapes** : lire l'inventaire des composants logiciels installés, isoler le
  composant de base, comparer sa release et son niveau de correctifs.
- **ASSERTE** : l'inventaire n'est pas vide ; le composant de base est présent ;
  sa release confirme celle du système ; son niveau de correctifs est
  **supérieur ou égal** à celui mesuré (0002 sur cette cible).
- **RAPPORTE** : le nombre de composants installés (14 ici contre 10 sur la
  jumelle) et le niveau constaté.
- **Pourquoi bloquant, et pourquoi un plancher plutôt qu'une égalité** : un
  système qui recule de niveau de correctifs perd des corrections de sécurité,
  et c'est un incident indépendant de toute politique. Un plancher laisse
  passer l'application de correctifs, qui est l'évolution souhaitable : une
  égalité ferait échouer la suite le jour où quelqu'un fait le bon geste.
- **À noter** : cette release, plus récente, porte un niveau de correctifs plus
  BAS que la 1909 (0002 contre 0007). Les deux chiffres ne se comparent pas
  entre releases, chacun étant un plancher propre à sa cible.

### 13. Le mandant de référence est protégé contre l'écrasement

- **Étapes** : lire les mandants du système avec leurs verrous, isoler le
  mandant de référence livré par SAP, vérifier son verrou de copie.
- **ASSERTE** : la liste des mandants n'est pas vide, le mandant de référence
  est présent, et il porte la protection contre la copie et l'écrasement.
- **RAPPORTE** : la catégorie du mandant de travail et son indicateur de
  correction, qui divergent entre les deux cibles du banc (`D` et `3` ici, `C`
  et `1` sur la jumelle). Cette divergence est une propriété de l'image, pas un
  défaut. Le mandant de travail n'a pas le verrou de copie, sur les deux
  cibles : c'est mesuré, et ce n'est pas ce que le contrôle protège.
- **Pourquoi bloquant** : le mandant livré par SAP sert de référence à tous les
  autres. S'il est copiable ou modifiable, la base de comparaison du système
  disparaît.

### 14. Les comptes standards livrés par SAP sont inventoriés avec leur état

- **Étapes** : lire l'état des comptes standards dans le mandant de connexion,
  puis journaliser chaque fiche, présents et absents.
- **ASSERTE** : l'inventaire n'est pas vide et les deux comptes livrés attendus
  sont présents.
- **RAPPORTE** : pour chaque compte présent, son verrouillage et **la cause** du
  verrouillage, son groupe et sa dernière connexion ; pour chaque compte absent,
  son absence explicite.
- **Pourquoi ce régime** : sur ce banc, les comptes livrés sont déverrouillés, y
  compris sur cette release mieux durcie, ce qui serait un écart majeur en
  production et n'a pas de sens ici. Le verrouillage se lit en **bits** et non
  en énumération : un compte verrouillé à la fois par l'administration et par
  des échecs de connexion porte les deux causes, et une table de correspondance
  plate le déclarerait inconnu.

### 15. Les porteurs de profil critique et les destinations RFC sont inventoriés

- **Étapes** : lire les attributions des deux profils critiques dans le mandant
  de connexion, puis l'inventaire complet des destinations RFC déclarées avec
  leur type.
- **ASSERTE** : l'inventaire des porteurs n'est **pas vide**. Ce n'est pas un
  contrôle de conformité, c'est une garde de vraisemblance : zéro porteur de
  profil tout-puissant signale une lecture douteuse bien plus probablement qu'un
  système exemplaire.
- **RAPPORTE** : les porteurs (cinq attributions, toutes du profil le plus
  large, aucune du second profil surveillé) et le nombre de destinations
  déclarées dont la part de destinations ABAP.
- **Complémentarité avec le scénario 11** : celui-ci compte les destinations,
  celui-là dit lesquelles portent un logon. Les deux ensemble donnent la
  surface d'élévation.

### 16. La configuration de sécurité n'a pas dérivé depuis la référence

- **Étapes** : reprendre le relevé complet et l'identité déjà lus, les
  confronter à la référence committée de cette cible.
- **ASSERTE** : aucune dérive. Chaque écart est nommé paramètre par paramètre,
  avec sa valeur avant et après.
- **RAPPORTE** : au premier passage, la création de la référence, avec un
  avertissement disant qu'elle est à relire et à committer.
- **Pourquoi ce scénario est le coeur de la campagne** : il ne demande pas si le
  système est durci mais si sa configuration a BOUGÉ, qui a une réponse binaire.
  Une dérive voulue se solde en re-committant la référence ; une dérive non
  voulue est exactement l'incident que la campagne existe pour attraper.
- **Points de vigilance** : **chaque cible a sa référence**. Les mélanger ferait
  passer les onze écarts de durcissement entre les deux releases pour une dérive
  de configuration, et la sentinelle crierait au loup dès le premier passage. Et
  son périmètre suit les lots : ajouter un paramètre à un lot oblige à régénérer
  la référence, ce qui a été fait quand le relevé est passé de 39 à 42.

## Points de vigilance pour la génération

Les cinq pièges relevés pendant l'exploration. Les trois premiers sont des
propriétés du canal de lecture, les deux derniers des propriétés de
l'environnement, et tous les cinq produisent un « vert et faux » plutôt qu'une
erreur visible.

1. **Un paramètre inconnu ne lève rien** : le module de lecture rend un code de
   retour non nul et une **chaîne vide**. Juger sur le code de retour AVANT la
   valeur, et ne jamais laisser une mesure absente prendre la forme d'une
   valeur. Encodé dans la bibliothèque, éprouvé par le scénario 2.
2. **La lecture est sensible à la casse** : la forme en majuscules d'un nom
   valide rend le même code non nul et la même chaîne vide qu'un nom inexistant.
   Ne jamais faire passer un nom de paramètre par un normaliseur qui capitalise
   (celui du dépôt est destiné aux noms de champs). Éprouvé par le scénario 3.
3. **Le code de retour ne distingue pas deux causes** : « inconnu de cette
   release » et « connu du noyau et non positionné » rendent le même verdict, et
   la table dictionnaire qui trancherait (`TPFYPROPTY`) a été mesurée **vide**
   sur les deux cibles du banc. Le vocabulaire du verdict reste donc prudent :
   « pas de valeur effective », jamais « ce paramètre n'existe pas ».
4. **Une référence éditée sous Windows porte une marque d'ordre d'octets
   UTF-8**, et la sentinelle échouait alors sur son propre décodage au lieu de
   comparer, c'est-à-dire qu'elle rougissait pour une raison sans rapport avec
   la sécurité du système. La relecture tolère désormais cette marque : ne pas
   la retirer en croyant simplifier.
5. **Sans le relais TCP, la cible répond quand même, et c'est l'autre conteneur
   qui parle.** C'est le piège le plus coûteux de cette campagne, parce qu'il ne
   produit aucune erreur : il produit un rapport complet, cohérent et faux, qui
   attribue à la 758 la posture de la 754. Le scénario 1 est la seule
   protection, et son message d'échec doit nommer le relais en premier.

Un sixième piège, propre aux inventaires : **un paramètre peut dire vrai et
laisser croire faux**. `rsau/enable` répond « armé » sur un journal qui ne
filtre rien, et la liste des destinations ne dit pas lesquelles portent un
logon, l'information vivant dans un agrégat de marqueurs. Chaque fois qu'un
contrôle repose sur un paramètre unique, se demander ce que ce paramètre NE dit
pas.

Autres exigences de génération :

- **Convention 1** : aucun nom de paramètre de profil ni de table
  d'administration dans une suite. Ils vivent dans
  `resources/security_keywords.resource`, sous des lots thématiques nommés ; les
  ATTENTES, elles, sont propres à la cible et vivent dans sa suite. C'est
  exactement ce qui permet à deux releases de partager un vocabulaire sans
  partager une baseline.
- **Convention 3** : aucun jugement sur un texte localisé. Les verdicts portent
  sur des valeurs de paramètres, des codes techniques et des décomptes.
- **Convention 11** : mot de passe par variable typée en ligne de commande, et
  la garde de présence ne le mesure jamais.
- **Convention 12** : les capacités manquantes listées plus bas vont dans la
  bibliothèque avec leurs tests hors SAP, jamais dans un calcul improvisé dans
  une suite. C'est ce qui a été fait pour la configuration d'audit, l'inventaire
  des destinations et celui des composants.
- **Opt-in par tag et saut propre** quand le canal RFC n'existe pas sur le
  poste, comme les deux suites RFC existantes.
- **Lecture seule stricte** : la campagne n'écrit aucun paramètre, ne
  déverrouille ni ne verrouille aucun compte, n'ouvre aucune destination, ne
  lit aucun secret.

## Ce qui n'est PAS couvert

Consigné pour qu'aucun lecteur du rapport ne prenne une absence de mesure pour
une absence de problème.

1. **Le contenu des fichiers de liste de contrôle de la passerelle.** La
   campagne vérifie que la passerelle est sous liste de contrôle et que les
   chemins de ces fichiers sont déclarés ; elle ne lit PAS les règles qu'ils
   contiennent. Une liste de contrôle déclarée mais permissive passerait donc le
   contrôle, sur cette cible comme sur l'autre.
2. **La distinction entre valeur de profil et valeur par défaut du noyau.** Le
   canal rend la valeur **effective** d'un paramètre. Il ne dit pas si elle
   vient du profil d'instance ou du défaut livré, donc la campagne ne peut pas
   affirmer que le durcissement supérieur de cette release est un réglage
   délibéré de l'image plutôt qu'un changement de défaut entre deux versions du
   noyau. La question est ouverte pour les onze écarts de la section 3.
3. **Le contenu du journal d'audit.** La campagne mesure la configuration du
   journal, désormais y compris son filtrage réel, mais jamais ses entrées :
   elle ne dit rien de ce qui s'est réellement passé sur le système. Elle
   n'exige pas non plus qu'un filtrage soit configuré (voir le scénario 10).
4. **La journalisation du serveur de messages** (`ms/http_logging`, mesurée `1`
   ici et `0` sur la jumelle) : délibérément hors des lots, aucun des six thèmes
   ne l'accueillant sans déformer le découpage. Elle n'est donc pas surveillée
   par la sentinelle, alors même qu'elle fait partie du durcissement propre à
   cette cible.
5. **La liste noire des modules appelables à distance** (9010 lignes ici, 524
   sur la jumelle) : c'est une **table**, pas un paramètre de profil, donc elle
   est hors du mécanisme de la sentinelle. C'est le **seul candidat d'extension
   restant** de cette campagne, et le plus gros écart de durcissement non
   surveillé entre les deux releases. **Keyword métier manquant** : la lecture
   de cette liste, rendue comme un décompte et une empreinte comparable plutôt
   que comme un contenu.
6. **Les relations de confiance RFC.** Les tables de confiance ont été lues
   pendant l'exploration et sont **toutes vides**, mais aucune suite ne les lit :
   le jour où une relation de confiance est créée, rien ne le verra. **Keyword
   métier manquant** : l'inventaire des relations de confiance entrantes et
   sortantes.
7. **Les marqueurs d'options de destination non établis.** Seuls ceux dont la
   signification est sûre sont interprétés ; les autres sont ignorés à dessein.
   Une destination pourrait donc porter une propriété de sécurité que cette
   campagne ne voit pas.
8. **Les autres mandants.** Toutes les lectures de tables d'administration
   portent sur le mandant de connexion (`001`). L'état des comptes du mandant
   `000`, notamment, n'est pas mesuré : il demanderait une autre connexion.
9. **Les autorisations réelles.** La campagne compte les porteurs des deux
   profils critiques ; elle n'analyse ni les rôles, ni les objets
   d'autorisation, ni les droits effectifs.
10. **La cause du durcissement supérieur de cette cible.** Rien dans les mesures
    ne dit si elle vient de l'image livrée, d'un paramétrage du banc ou d'un
    changement de défaut du noyau. Le plan constate l'écart et ne l'explique
    pas.
