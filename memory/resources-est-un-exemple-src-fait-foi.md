# `resources/` est un EXEMPLE, `src/` fait foi

Observation datée : 2026-08-30.

Le dépôt livre deux choses de nature opposée, et il ne le disait nulle part.

`src/` (les trois bibliothèques et `sapfx_common`) porte les CAPACITÉS :
perception, résolution, attente, moteurs, lecture d'état, protocoles,
auto-réparation. C'est indépendant du système cible, testé unitairement hors
SAP, versionné, publié sur PyPI. Ce que promet un de ses mots-clés, il le
promet sur n'importe quel système SAP.

`resources/` porte le VOCABULAIRE MÉTIER d'UNE installation : identifiants,
chemins de service, noms de tables et de modules, paramètres de profil,
enchaînements d'écrans, tous relevés live sur les cibles du laboratoire (une
1909, une 2023, un site Work Zone BTP, cap-sflight, un bac à sable public).
C'est une trousse d'exemples, à vérifier sur la cible et à adapter au métier
du testeur. Beaucoup s'y transpose (écrans et services standard, nomenclature
en miroir, patrons de page object), rien n'y fait autorité.

Ce que disaient les textes AVANT la clarification, et pourquoi c'est un piège :
« the business-readable keyword layer tests should call » (index LLM),
« Tests should import these » (README du pack), « Cette couche est celle que
les tests doivent appeler » (en-tête du fichier ECC, juste au-dessus d'ids
relevés sur une version précise du client lourd). Zéro occurrence du mot
« exemple » dans les seize `.resource`. Or ces fichiers partent TELS QUELS
dans le dépôt public et dans le pack de déploiement, c'est-à-dire chez un
lecteur qui n'a ni le contexte du laboratoire ni la conversation qui
l'expliquait : il les lit comme un contrat et écrit des tests contre les
écrans d'un autre système.

La clarification est donc posée là où le lecteur arrive, pas seulement dans un
guide : `resources/README.md` (et sa version française), un bandeau
« EXEMPLE À PERSONNALISER » en tête de la `Documentation` Robot de chaque
`.resource` (donc visible dans Libdoc, là où un utilisateur de la bibliothèque
lit le fichier), plus l'index LLM, les deux README, le README du pack, la doc
d'architecture, la convention #1 et ses deux miroirs, et la skill outillage.
Un garde unitaire vérifie le bandeau sur l'arbre RÉEL : un `.resource` ajouté
demain ne peut pas l'oublier.

C'est la convention #12 vue du côté de l'utilisateur : la même frontière
décide où va une correction (capacité manquante ou fautive dans `src/`,
spécificité de cible dans `resources/`) et ce qui fait foi hors du dépôt.

Voir [[capacite-en-couche-robot-angle-sans-garde]] et
[[promotion-ne-doit-pas-tuer-la-surface-de-healing]] pour l'autre versant de
cette frontière, celui de la maintenance.
