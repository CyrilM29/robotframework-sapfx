# Une sonde JS dont la première ligne est un commentaire ne fait RIEN, et l'appel réussit

**Relevé le 2026-09-15**, en ajoutant une sonde de lecture de grille WebGUI
dans un gabarit `.js.tpl` autonome.

## Le fait

Une source JS passée à `Evaluate JavaScript` (bibliothèque Browser, donc
Playwright) est reconnue comme une FONCTION à appeler ou comme une EXPRESSION
à évaluer. Un commentaire posé avant la fonction bascule la reconnaissance du
mauvais côté : la fonction n'est jamais appelée, et c'est l'objet fonction qui
est sérialisé, donc une valeur vide.

Vérifié isolément : `() => 42` rend `42` ; les mêmes caractères précédés d'une
ligne `// un commentaire` rendent une chaîne vide. **Aucune erreur n'est
levée**, l'appel est en PASS.

## Pourquoi c'est coûteux

Le symptôme n'est pas une panne, c'est un silence. Côté Robot, tout est vert
jusqu'à ce qu'un keyword plus haut constate un résultat vide, et son message
d'échec accuse alors la page, la portée de frame ou le contrôle visé : trois
pistes plausibles, aucune bonne. Dans notre cas le message disait « la page
n'a pas répondu » et proposait de vérifier `Webgui Is Present` et
`Set/Push Ui5 Frame`, alors que la page répondait parfaitement.

## Ce qu'on en fait

- Un gabarit JS autonome COMMENCE par sa fonction ; son explication vit dans
  le CORPS de la fonction.
- Les sondes en ligne de `_ui5_js.py` échappent au piège parce que leurs
  commentaires sont du côté Python, hors de la chaîne. C'est une propriété
  de leur forme, pas une vertu : un fichier séparé la perd.
- La propriété s'épingle par un test unitaire (la source commence par sa
  signature), pas par un commentaire d'avertissement : ce qui n'est pas
  vérifié mécaniquement se reperd.

Même famille que [[gardes-qui-ne-peuvent-pas-echouer]] : le danger n'est pas
l'erreur, c'est le succès qui n'affirme rien.
