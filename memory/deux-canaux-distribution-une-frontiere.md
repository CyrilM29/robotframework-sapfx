---
name: deux-canaux-distribution-une-frontiere
description: Deux canaux de distribution (dépôt public exporté, pack Windows) filtraient le privé chacun de leur côté, et un seul le faisait : copier un dossier PARENT dans le pack a livré du contenu que l'export excluait nommément, pendant une release entière
type: projet
date: 2026-08-19
---

Le projet distribue par **deux** canaux qui partent du même arbre privé :
`scripts/export_public_tree.py` (vers le dépôt public et PyPI) et
`scripts/build_release_pack.py` (le ZIP Windows). Chacun avait sa propre notion
du périmètre. L'export tenait une liste d'exclusions explicite, nominative,
doublée d'un scan anti-fuite bloquant. L'assembleur du pack, lui, copiait des
**arborescences entières** : il n'exprimait que ce qu'il fallait prendre, jamais
ce qu'il fallait laisser.

Résultat constaté à la revue du 2026-08-19 : une entrée de `.claude/skills/`
que l'export excluait par son nom depuis toujours est partie dans le ZIP livré
d'une release complète, parce que le pack copiait le dossier parent. Personne
n'avait menti nulle part, aucune règle n'avait été oubliée : elle n'était
simplement écrite qu'à un endroit sur les deux.

Trois leçons, dans l'ordre de leur valeur.

1. **Une frontière de confidentialité tenue par un seul canal n'est pas
   tenue.** Ce n'est pas un défaut de vigilance, c'est un défaut de structure :
   tant que deux scripts décident séparément, l'un des deux finit par diverger.
   La réparation n'est pas de recopier la liste, c'est de faire porter LA liste
   de l'export par les deux, avec un test qui refuse tout chemin du manifeste du
   pack figurant dans les exclusions publiques.
2. **Copier un dossier parent est une décision par défaut, et le défaut y est
   « tout ».** La liste blanche (nommer chaque sous-dossier voulu) échoue du bon
   côté : le jour où un contenu privé apparaît dans un dossier déjà copié, il ne
   part pas. Le coût est d'une ligne par ajout.
3. **Ne pas recopier le secret dans la documentation de sa fuite.** Le scan
   anti-fuite de l'export interdit jusqu'au NOM de l'entrée concernée, y compris
   dans les fichiers qui partent au public (CLAUDE.md, AGENTS.md, CHANGELOG,
   `tests/unit/`). En documentant la correction, la première rédaction nommait
   la chose partout : elle aurait fait échouer l'export à la release suivante,
   ou pire, publié ce qu'on venait de retirer. Les notes disent donc
   « la skill privée de communication », et l'assertion du test se formule en
   **liste blanche** (« rien d'autre que `sapfx` ») plutôt qu'en liste noire.

Quatrième leçon, découverte en vérifiant les trois premières : **un garde de
chemins ne remplace pas un garde de contenu**. La symétrie ci-dessus ne voit
rien d'un secret écrit À L'INTÉRIEUR d'un fichier par ailleurs légitime. Le
scan d'octets existait, côté export, mais il ne tournait qu'à la main, une fois
par release, sur `git archive HEAD` : le ZIP pouvait donc être construit, testé
et publié avant que le seul scan de contenu du projet ait jamais tourné.
Mesure faite : passé sur le ZIP réellement livré, il sort 5 occurrences
interdites et nomme le fichier ; passé sur le pack corrigé, zéro. Il est donc
branché sur le manifeste du pack, en CI, à chaque push. Un outil de contrôle
qui ne s'exécute qu'au moment de publier arrive après la décision qu'il devait
éclairer.

Corollaire, trouvé par le même garde : la symétrie vaut aussi pour la
**cohérence interne** du pack. Deux définitions d'agent livrées pilotaient des
scripts restés au dépôt (la gate de conventions de sap-generator, et l'éval en
aveugle du healer). Un fichier livré qui invoque un chemin absent est un échec
silencieux chez l'utilisateur : le garde exige maintenant que tout script cité
par un fichier du pack soit livré, ou explicitement justifié comme hors sujet.

Voir aussi [[gardes-sortie-console-utf8]] pour l'autre moitié de la question
(ce que les scripts embarqués peuvent supposer de leur voisinage).
