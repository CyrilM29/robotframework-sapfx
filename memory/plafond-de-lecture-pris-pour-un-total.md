---
name: plafond-de-lecture-pris-pour-un-total
description: 2026-08-27, une lecture bornée à 200 lignes a fait conclure « 4 sur 4 statuts identiques » sur une table qui en portait 4719 et 4 statuts distincts ; l'erreur a traversé un plan, une suite et une documentation avant d'être vue
type: projet
date: 2026-08-27
---

En explorant le canal RFC, `TBTCO` a été lue avec un plafond de 200 lignes.
Les 200 renvoyées portaient toutes le statut `F`, et la conclusion écrite fut
« la table porte 200 runs, tous terminés ». La table en portait **4719**,
répartis sur **quatre** statuts (`F`=4597, `Z`=105, `A`=10, `S`=7).

La conséquence n'était pas une simple imprécision. Elle a fait déclarer
**non éprouvable** une branche de code qui l'était parfaitement, et en lecture
seule : cinq jobs de la même cible portaient un run annulé, un autre un run
encore dans le pipeline, un troisième 69 runs à un statut non cartographié.
L'erreur a traversé le plan de test, la suite générée, la documentation du
dépôt et un compte rendu, sans que rien ne la contredise, parce qu'un plafond
atteint ne se signale pas : il rend une liste pleine, d'apparence complète.

**Pourquoi :** un `rowcount` est une protection contre le volume, pas un
échantillon représentatif. Les lignes rendues ne sont pas tirées au hasard,
elles arrivent dans l'ordre physique de la table, donc elles sont
CORRÉLÉES entre elles (mêmes jobs, même période, même statut). Conclure une
distribution depuis ce préfixe revient à décrire une population d'après ses
premiers arrivés.

**Comment appliquer :** ne jamais tirer un fait de DISTRIBUTION (« tous »,
« aucun », « seulement N ») d'une lecture plafonnée. Deux réflexes, l'un ou
l'autre : lire sans plafond quand la table le permet et compter côté client,
ou compter par critère (une lecture filtrée par valeur, ou un `$count`
équivalent) plutôt que d'inventorier. Et quand un plafond reste nécessaire,
écrire le plafond À CÔTÉ du chiffre dans toute note qui en découle, pour que
le lecteur suivant voie qu'il lit un préfixe et non un total. C'est la même
propriété que le dépôt exige déjà de ses campagnes, où un plafond ATTEINT est
un échec et jamais une troncature muette : la règle valait aussi pour
l'exploration qui précède la campagne.

Voir aussi [[rfc-champ-inexistant-accuse-la-table]].
