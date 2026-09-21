---
name: echelle-de-rendu-et-localisateurs-humains
description: 2026-09-21, une session RDP depuis un poste à écran dense rend SAP GUI à l'échelle du CLIENT et l'API Scripting rend cette géométrie en pixels physiques ; des tolérances fixes ne rattachaient plus aucun libellé, `Get Se16 Selection Criteria` rendait « aucun critère » sur un écran parfait, et deux campagnes EPM en ont porté la trace (un rouge, un contournement) ; corrigé dans la bibliothèque, les tolérances suivent la hauteur de champ mesurée
type: projet
date: 2026-09-21
---

Deux campagnes EPM générées le 2026-09-18 portaient la même anomalie sous
deux formes : la suite Order-to-Cash (`SEPM_SO`) était ROUGE sur son
croisement SE16 (« no technical selection criterion found on the current
screen », alors que la capture d'écran jointe montre l'écran de sélection de
`SNWD_SO` parfaitement rendu, tous ses libellés visibles), et la suite
Procure-to-Pay avait CONTOURNÉ le même échec sur `SNWD_PD` et `SNWD_STOCK`
en lisant les grilles complètes puis en filtrant par contenu, avec dans son
plan la mention « cause non investiguée ».

Rejouées le 2026-09-21 sur le poste lui-même, les deux passent 3/3 sans
qu'une ligne de la bibliothèque ait bougé. Ce qui différait le 18 : la
session tournait **par RDP depuis une autre machine**, et les captures de
cette fenêtre font 4676x2550 là où le bureau du poste fait 1920x1080. Une
session RDP rend SAP GUI à l'échelle du poste CLIENT (facteur ~2,4 ici), et
l'API Scripting rend la géométrie (`Left`/`Top`/`Width`/`Height`) en pixels
PHYSIQUES : toutes les distances de l'écran sont multipliées.

Or le moteur de localisateurs humains raisonnait en pixels FIXES
(alignement 5, écart horizontal 30, vertical 25). Mesuré sur l'écran de
sélection SE16 à 100 % : chaque libellé est un champ texte non modifiable de
231 px (bord droit à 258) et le critère `I<n>-LOW` commence à 283, soit un
écart de **25 px pour un plafond de 30**. Simulé sur cette géométrie
réelle : dès un facteur 1,25, plus AUCUN libellé ne se rattache, et la carte
des critères est vide. Le rapport de vérification manquait donc de
franchise : « aucun critère à l'écran » désignait l'écran, quand c'était le
rendu.

**Pourquoi c'est une capacité et pas une tolérance à élargir** : élargir les
constantes aurait acheté un facteur et en aurait perdu un autre (à 100 %,
un écart de 31 px doit rester hors tolérance, sinon un libellé désigne le
champ de la ligne voisine). L'échelle se mesure sur l'écran lui-même : la
médiane des hauteurs des champs et libellés, divisée par 24 (la hauteur
d'un champ rendu à 100 %, identique sur les 281 éléments de l'écran relevé),
et toutes les tolérances ET le rayon de portée `>>` suivent cette échelle,
proportionnellement, jamais en amnistie. Bornée à 1 vers le bas : un thème
plus compact n'a pas à resserrer des tolérances calibrées à 100 %.

**Comment appliquer** : devant un échec de localisateur humain ou de
dérivation de critères sur un écran que la capture montre correct, regarder
d'abord les DIMENSIONS de la capture jointe au rapport (même réflexe que
[[baselines-visuelles-liees-a-la-resolution]] pour les empreintes) : une
géométrie qui n'est pas celle du poste dit RDP, facteur d'échelle Windows
ou écran dense, et c'est le rendu, pas l'écran, qui a changé. Et quand un
plan consigne « cause non investiguée » à côté d'un contournement coûteux
(ici 2665 lignes lues au lieu d'un critère), la cause est à chercher avant
la génération suivante : un contournement de couche intermédiaire est le
signal de la convention 12, pas sa réponse.
