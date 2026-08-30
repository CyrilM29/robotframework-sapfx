# Une capacité en couche Robot s'accumule exactement dans l'angle sans garde

Observation datée : 2026-08-29.

Un audit de la couche `resources/` (demande : « aucun keyword de bibliothèque
dans le vocabulaire métier ») a trouvé la dette de la convention #12 très
précisément là où AUCUN garde mécanique ne regardait : du JS inline
(`Evaluate JavaScript`, `Wait For Function`) et des `Evaluate __import__`
dans les page objects, alors que les conventions voisines (#1 localisateurs,
#2 Sleep, #13 taille de fichier, cadratin) étaient toutes tenues par un
script. Le dépôt SAVAIT faire la promotion (le même fichier documentait
celle de `Get Page Location`, 2026-08-26) : ce n'est pas la discipline qui
manquait, c'est le filet.

Trois signatures de cette dette, à reconnaître ailleurs :

- la **duplication entre page objects** (la même lecture de service ushell
  écrite deux fois, la lecture de contexte de liaison trois fois) : une
  capacité générique recopiée est le signal le plus sûr qu'elle a changé de
  couche ;
- la **réimplémentation d'un mécanisme que la bibliothèque porte déjà** (la
  chaîne de repli `ElementRegistry` → `Element.registry` recodée inline dans
  un page object, alors qu'elle est LA raison d'être du bundle versionné) ;
- la **leçon payée encodée dans une lambda** (le prédicat « expiration
  future » des cookies, sentinelle 1969) : une leçon qui vit dans un
  `Evaluate` ne protège que la campagne qui l'a payée.

Résolution : 19 keywords promus dans la bibliothèque web (services ushell,
fiche de contrôle avec agrégations NON rendues, perception WebGUI, état de
session), et le garde des conventions étendu au motif détectable de la #12,
avec une allowlist à COMPTE EXACT. Règle d'admission dans l'allowlist : une
raison de NATURE, jamais de commodité : sonde spécifique à une release
(stratégie nommée), geste que la bibliothèque refuse par contrat (fragment
malformé), ou promotion qui violerait le contrat documenté de la sonde
elle-même (le marqueur d'onglet est « volatile, jamais persisté » : un
stockage persistant le trahirait).

**Limite du garde, mesurée le jour même** : il ne voit que le MOTIF (JS
inline, `__import__`), jamais une capacité écrite en Robot pur. Une seconde
passe, de JUGEMENT cette fois, en a trouvé six de plus que rien n'aurait
signalées : deux primitives d'écran SE16, une garde de secret dupliquée cinq
fois, un déballage de secret en couche Robot, la clé composite d'un service
OData draft, et une classification de refus HTTP. Le garde couvre donc la
récidive mécanique, pas l'inventaire : celui-ci se refait à la main, et le
meilleur indice reste la duplication (voir [[promotion-ne-doit-pas-tuer-la-surface-de-healing]]
pour l'effet de bord à surveiller à chaque promotion).

Corollaire pour les suites : `modules=` et `__import__('json')` s'étaient
aussi glissés dans des suites GÉNÉRÉES malgré la décision DDIC : l'Evaluate
de Robot auto-importe les modules de premier niveau (`json.dumps(...)` nu
suffit), et une adresse se décompose par le keyword (`Get Page Location
url=… base=…`), plus jamais par `urllib` en cellule.
