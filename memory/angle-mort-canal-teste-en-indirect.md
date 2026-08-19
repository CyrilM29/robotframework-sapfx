---
name: angle-mort-canal-teste-en-indirect
description: 2026-08-19, un canal éprouvé seulement À TRAVERS d'autres suites cache ses défauts (33 keywords couverts par un seul keyword de lecture) ; et un test unitaire peut GRAVER le bug, ce qui rend la CI structurellement aveugle
type: projet
date: 2026-08-19
---

Deux défauts réels du canal API ont survécu à plusieurs versions, protégés par
trois couches de masquage superposées.

1. **Le canal n'avait pas de suite à lui.** Il exposait 33 keywords publics et
   n'était exercé en live qu'INDIRECTEMENT, par deux suites cross-paradigme, sur
   un seul keyword de lecture chacune. Tout le reste (filtrage, écriture,
   fabrique de données) n'avait jamais rencontré de système réel.
2. **Un test unitaire GRAVAIT le comportement fautif.** L'encodage à corriger
   était asserté tel quel dans un test vert. La CI ne pouvait donc pas le voir :
   elle confirmait le défaut au lieu de le signaler.
3. **Le seul usage live qui aurait pu l'attraper échouait plus tôt**, pour une
   raison sans rapport (identifiants manquants). Son échec, connu et classé
   « prérequis d'environnement », masquait ce qui venait après.

**Pourquoi :** aucune de ces trois couches n'est une négligence isolée, et
c'est bien le problème. Une couverture mesurée en pourcentage de lignes reste
excellente pendant ce temps : ce qui manquait n'était pas du volume de test,
c'était une confrontation à un système réel sur le périmètre entier du canal.
Un test qui fige un comportement observé, sans se demander s'il est CORRECT,
transforme la CI en gardien du bug.

**Comment appliquer :** quand un canal, une bibliothèque ou un moteur n'est
testé qu'à travers un autre, l'inscrire au dos de la main comme un risque, pas
comme une économie. Deux questions valent le détour avant d'écrire une
assertion sur une valeur observée : est-ce que je verrouille un contrat, ou
seulement ce que le code fait aujourd'hui ? Et si c'était faux, quel test
échouerait ? Voir [[canal-api-odata-v4-pieges]] pour les défauts eux-mêmes.
