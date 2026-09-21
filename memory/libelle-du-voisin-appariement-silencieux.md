---
name: libelle-du-voisin-appariement-silencieux
description: En dérivant la carte des critères d'un écran de sélection, un champ sans libellé propre adoptait le libellé le plus proche à sa gauche, sans borne, et la garde de doublon ne le voyait que sur une même ligne ; règle structurelle (un libellé appartient au premier champ à sa droite) plutôt que métrique, et carte mesurée avant et après
type: projet
date: 2026-09-21
---

# Un libellé appartient au premier champ à sa droite, et à lui seul

**Relevé le 2026-09-21** sur la capacité qui dérive la carte `{CHAMP: SID}`
d'un écran de sélection SE16 rendu par le WebGUI, à la lecture de la revue
indépendante de la suite qui l'emploie.

## Le fait

L'appariement prenait, pour chaque critère, le libellé technique le plus
proche **à sa gauche sur la même ligne**, sans aucune borne de distance. Un
critère dépourvu de libellé propre adoptait donc celui d'un voisin, parfois
très loin. La garde de doublon (« un même nom revendiqué par deux critères »)
ne l'attrapait que si le propriétaire légitime était lui aussi un critère,
sur la même ligne. Quand ce propriétaire n'est pas un critère (un champ de
portée générale de l'écran), personne d'autre ne réclame le libellé : la carte
nomme un critère d'après le libellé d'un AUTRE champ, et rien ne proteste.
C'était la seule mauvaise carte qui passait sans bruit, c'est-à-dire
exactement ce que la capacité existe pour empêcher.

## Ce qu'on en fait

- Règle **structurelle** : un libellé appartient au PREMIER champ porteur
  d'un SID à sa droite, quelle que soit la nature de ce champ. Un critère dont
  le libellé appartient à un autre est traité comme un critère SANS libellé,
  donc ignoré : l'appelant reçoit la liste de ce que l'écran porte vraiment,
  jamais un nom emprunté.
- Pas de seuil en pixels : une distance gravée a déjà cessé de rattacher le
  moindre libellé dès que la densité d'affichage a changé (session RDP, le
  même jour, sur le canal écran).
- Le premier test écrit tombait sur le cas que la garde de doublon attrapait
  déjà bruyamment ; le cas SILENCIEUX exige que le propriétaire ne soit pas un
  critère, et c'est celui-là qu'il faut épingler (vérifié en désactivant la
  règle : la carte nommait le mauvais champ, sans erreur).
- Une règle qui écarte peut aussi **rétrécir** la carte en silence, ce qu'un
  scénario qui ne filtre que sur un champ ne verrait pas : mesurer la carte sur
  l'écran réel avant et après (23 critères, inchangé) et journaliser son
  compte à chaque usage.
