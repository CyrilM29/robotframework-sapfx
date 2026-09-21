---
name: garde-de-cible-un-canal-sur-trois
description: Une campagne à trois canaux prouvait sa cible sur un seul, une garde annoncée discriminante ne vérifiait qu'une non-vacuité et un résultat négatif n'avait pas de témoin ; trois assertions vraies quoi qu'il arrive, trouvées par une revue indépendante sur une suite verte, corrigées puis vues refuser
type: projet
date: 2026-09-21
---

# La cible d'une campagne multi-canal se prouve canal par canal

**Relevé le 2026-09-21** par la revue indépendante (`sap-verifier`) d'une
suite fraîchement générée et validée 7/7 sur deux releases : rien n'était
faux, et pourtant trois gardes n'avaient pas la portée que la suite leur
prêtait.

## Les trois trous, et pourquoi ils étaient invisibles

1. **La release prouvait la cible du canal RFC, et de lui seul.** La suite
   porte cinq variables de cible et une seule était confrontée à une mesure.
   Or le plan décrivait la seconde release comme jouée « par simple
   surcharge de variables » : en oublier une (`API_BASE_URL`) fait lire DEUX
   systèmes différents, et comme les deux images du banc portent le même jeu
   de démonstration au même prix, les trois canaux « s'accordent » et la
   suite est verte en comparant deux systèmes. Une suite qui passe ne peut pas
   voir ça.
2. **Le volume du catalogue Gateway était annoncé discriminant** (38 contre
   58, mesuré) **et seulement comparé à zéro.** Une garde de non-vacuité là où
   le plan promettait un discriminant.
3. **Le résultat négatif** (aucun document de modification pour la table)
   **n'avait pas de témoin** : zéro ligne était asserté comme absence prouvée
   sans que rien n'établisse que cette lecture-là sait rendre des lignes.
   « Constaté absent » et « pas réussi à lire » rendaient le même vert.

## Ce qu'on en fait

- **Un discriminant par canal**, tous confrontés à une valeur attendue, dans
  le **Suite Setup** : release (RFC), volume exact du catalogue (API), adresse
  réellement atteinte (WebGUI, dont le bandeau ne porte ni release ni kernel).
  Une garde qui ne vit que dans un scénario rougit sans EMPÊCHER.
- Une garde annoncée « discriminante » compare à une valeur attendue, jamais à
  zéro.
- Un résultat négatif est précédé d'un témoin positif (le patron de la sonde
  canari de l'inventaire DDIC).
- Une garde ajoutée est **vue refuser** avant d'être déclarée fermée : ici
  deux provocations pointant l'autre conteneur, chacune faisant échouer le
  Suite Setup, donc aucun scénario ne lit.
- La revue indépendante vaut son coût précisément sur une suite verte : c'est
  là qu'une exécution ne trouve plus rien.
