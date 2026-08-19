# Replay du recorder : un step ignoré ne doit jamais sortir en 0

**2026-08-19, revue de code de `tools/`.** `--replay` comptait « ignoré » tout
step dont le keyword n'existe pas dans `SapEccLibrary`, puis affichait
`Replay OK : 0 step(s) exécuté(s), N ignoré(s)` avec le code de sortie **0**.

Le cas n'est pas théorique : c'est EXACTEMENT ce que produit la paire
**resource-first**, l'export que la convention n°1 recommande. Tous ses steps
sont des keywords métier vivant dans le `.resource` importé, donc 100 % sont
ignorés, et le replay se déclare vert après n'avoir rien rejoué. Vérifié :
2 steps, 0 exécuté, code 0.

Corrigé : un step non rejoué fait échouer le replay (code 1), et le message
nomme le cas resource-first en renvoyant vers `robot`. Un fichier portant
plusieurs tests est annoncé aussi, puisque seul le premier est rejoué
(`parse_recorded_body` s'arrête au premier, `count_test_cases` le dit).

**La leçon générale** : un outil qui « saute » ce qu'il ne comprend pas doit le
compter ET le rendre bloquant. La même règle vaut pour un lot d'objets revenu
vide, une lecture plafonnée ou une grille absente : c'est la doctrine « jamais
vert et faux » du dépôt, et un compteur affiché ne suffit pas quand le code de
sortie, lui, dit l'inverse.

Deux voisines du même lot : [[arret-externe-recorder-teardown]] (un arrêt
brutal saute le teardown) et le séparateur de cellules RF, qui n'est pas
« quatre espaces » mais « une tabulation ou deux espaces au moins » : un
déroulé édité à la main se découpait en une seule cellule, donc en steps tous
ignorés, ce qui alimentait exactement le faux vert ci-dessus.
