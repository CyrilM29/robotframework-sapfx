# La recherche du shell FLP 1.71 demande DEUX clics, et le témoin est la surface

Observation datée : 2026-08-29, launchpad Fiori servi par un serveur ABAP en
SAPUI5 1.71.

Mesuré au DOM. Après le PREMIER clic sur le bouton de recherche du shell, le
champ est ABSENT du DOM et le bouton reste `visible=True`. Après le SECOND, le
champ occupe 560x36 (son input interne 528x26) et le bouton passe à
`visible=False`. Le contrôle, lui, existe au registre dès le premier clic, et il
s'y déclare `visible=True`.

Ce que coûtait le clic unique : l'assertion de PRÉSENCE passait, le scénario
saisissait ensuite dans un champ inexistant, la valeur relue restait vide, et la
touche Entrée partait à la tuile qui avait le focus, ouvrant une application au
lieu de lancer la recherche. Le test était donc vert sur du vide, aussi
longtemps que la visibilité n'a pas exigé de surface.

Deux conséquences durables :

- le témoin d'ouverture est la SURFACE du champ, jamais sa présence au registre
  ni sa propriété `visible` (sur ce même shell, `visible=true` ment déjà sur
  `homeBtn`, qui se déclare visible sans nœud DOM) ;
- l'ouverture s'écrit idempotente et se retente : elle ne clique que si le champ
  n'est pas déjà ouvert, le bouton disparaissant une fois la recherche dépliée,
  si bien que recliquer échouerait. C'est exactement le motif déjà relevé sur le
  shell d'un launchpad Work Zone.

Leçon de méthode, plus large que ce champ : le durcissement de la visibilité
(exiger un rectangle non nul, 2026-08-26) est ce qui a fait tomber le scénario,
cinq jours après sa validation à 19/19. Une campagne validée AVANT un
durcissement doit être rejouée APRÈS, sans quoi le vert-et-faux survit
tranquillement à la correction qui le visait, et se découvre des semaines plus
tard sur une cible qu'on croyait acquise.

Voir [[une-seule-release-ne-montre-pas-ses-hypotheses]] : la campagne jumelle en
1.120 passait, ce qui isolait la cause à la release et non au produit.
