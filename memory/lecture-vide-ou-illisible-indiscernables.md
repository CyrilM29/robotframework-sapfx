---
name: lecture-vide-ou-illisible-indiscernables
description: 2026-08-30, une lecture qui rend une collection VIDE quand elle ne sait pas lire donne la même réponse qu'une source légitimement vide, donc un test vert qui n'affirme rien ; relevé sur une table de documentation UI5 que le sélecteur résolvait pourtant à un contrôle unique porteur de ses lignes
metadata:
  type: project
---

Sur le Demo Kit OpenUI5, la lecture générique de table rendait une **liste
vide** pour la table des propriétés d'un contrôle : le sélecteur résolvait
exactement 1 correspondance, ce contrôle portait bien ses lignes, et rien ne
signalait que le lecteur ne savait pas les atteindre. La table de documentation
(`sap.ui.documentation.LightTable`) ne suit pas le contrat des tables courantes
(ni l'agrégation `items`, ni des lignes exposant leurs cellules), et ses
en-têtes vivent dans une PROPRIÉTÉ, non dans des colonnes.

Le défaut n'est pas de ne pas savoir lire ce contrôle : c'est de rendre la même
réponse que pour une table légitimement vide. Un test qui itère sur le résultat
ne boucle pas, n'échoue pas, et passe. C'est le « vert et faux » dans sa forme
la plus économique : aucune erreur à diagnostiquer, aucune trace, une assertion
qui s'évapore.

**Pourquoi :** une valeur d'absence sert deux significations opposées, « il n'y
a rien » et « je n'ai pas su regarder ». Tant que l'appelant ne peut pas les
séparer, la seconde se déguise en première, et c'est toujours dans ce sens-là
que ça tombe (la lecture qui échoue produit du vide, jamais du bruit). La
famille est large : un comptage à zéro, un dictionnaire sans la clé, une liste
de candidats vide, une carte de correspondances muette.

**Comment appliquer :** faire rendre à la sonde un CONSTAT plutôt qu'une
collection nue (ce qui a été reconnu, par quelle voie, combien de candidats,
combien d'écartés), et décider en Python. Trois issues à garder distinctes :
rien à lire (succès, collection vide), lignes présentes mais illisibles
(échec nommant le type et la voie de repli), source absente (échec nommant la
portée). Le cas légitime d'écart partiel (des en-têtes de groupe sans cellules,
à côté de lignes lisibles) ne doit PAS devenir rouge, sans quoi le garde se
fait désactiver. Même patron que le repli sûr de [[parametre-de-profil-inconnu-rend-une-valeur-vide]]
(juger le code de retour avant la valeur) et des barèmes de classification qui
gardent un état `unmapped` plutôt que de conclure au succès.

Corollaire de couche : la correction va dans la bibliothèque, jamais dans le
page object qui l'a rencontrée ([[resources-est-un-exemple-src-fait-foi]]), et
la voie correcte pour ce contrôle (lire la propriété d'en-têtes et l'agrégation
de lignes au registre) reste ce qu'elle était, elle n'était pas le
contournement.
