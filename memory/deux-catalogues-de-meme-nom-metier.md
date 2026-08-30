# Deux catalogues portant le même nom métier, de populations différentes

**Date de l'observation** : 2026-08-28.
**Contexte** : génération d'une campagne du canal RFC sur une seconde release
ABAP, avec croisement vers le canal OData du même système.

## Le fait

Le système porte **deux** catalogues de compagnies aériennes. Ils décrivent la
même notion métier, ils ne décrivent pas la même population :

- le catalogue du modèle de démonstration historique compte **18** codes ;
- celui du modèle de voyage moderne en compte **16** ;
- le second est **strictement inclus** dans le premier, deux codes manquent.

Le service web qui projette le modèle moderne compte donc 16, et non 18.

## Pourquoi cela coûte

Un croisement entre deux canaux rapproche « le nombre de compagnies compté
ici » et « le nombre de compagnies compté là ». Si un côté lit le catalogue
historique et l'autre le catalogue moderne, l'écart vaut deux, il est
**parfaitement reproductible**, et rien dans le résultat ne dit qu'on compare
deux populations. Le temps passé cherche alors un défaut de synchronisation,
de filtre ou d'autorisation qui n'existe pas.

La forme symétrique est pire : une égalité obtenue en confondant les deux
serait un vert construit sur une coïncidence, et il suffirait qu'un des deux
jeux de données bouge pour que la campagne devienne rouge sans raison lisible.

## Ce qu'on en fait

1. **Nommer le catalogue dans le nom du mot-clé**, pas dans un commentaire.
   Deux mots-clés distincts dans la couche vocabulaire, dont les noms se
   lisent à voix haute sans ambiguïté, valent mieux qu'un mot-clé
   paramétré : c'est au moment d'écrire l'appel qu'il faut choisir, pas au
   moment de le relire.
2. **Écrire le scénario à l'envers.** Plutôt que d'espérer que personne ne
   confonde, asserter la DIFFÉRENCE : les deux comptes diffèrent, le plus
   petit est inclus dans le plus grand, et l'écart est entièrement expliqué
   par les codes présents dans l'un et absents de l'autre. Le piège devient
   alors une assertion bruyante, et la suite échoue si quelqu'un « corrige »
   un jour l'un des deux comptages pour les faire coïncider.
3. **Vérifier, dans le test de croisement lui-même, que le compte du canal web
   n'égale PAS celui de l'autre catalogue.** Sans ce pas, le croisement
   pourrait devenir vert en visant le mauvais côté.

## La règle générale

Un même nom métier ne garantit aucune correspondance de population. C'est la
même leçon qu'une correspondance entity set vers table déduite d'un nom, et
elle se paie de la même façon : par un écart stable qu'on attribue à un défaut
imaginaire. Le couple lu se déclare explicitement et se prouve par les deux
comptages exécutés dans le même run.
