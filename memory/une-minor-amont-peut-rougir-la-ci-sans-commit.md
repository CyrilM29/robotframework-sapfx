# Une minor amont rougit la CI sans qu'aucun commit ne touche le code

**Relevé le 2026-09-16**, sur une branche dont la CI était verte la veille et
dont le dernier commit ne touchait ni le code concerné ni ses tests.

## Le fait

`pyproject.toml` déclare `robotframework>=7.4` sans borne haute, et c'est
délibéré (une borne sur un socle aussi central interdirait à nos consommateurs
de migrer avant nous). Conséquence mécanique : le jour où Robot Framework 7.5
est publié, le prochain runner l'installe. Ici, le poste de développement
restait en 7.4.2, donc le test échouait en CI et passait en local, ce qui est
la pire forme du problème : on cherche d'abord dans le diff, puis dans le
merge, avant de penser à l'environnement.

La cause exacte, une fois isolée : **7.5 fait entrer le type de RETOUR d'un
keyword dans les `usages` d'un typedoc**, là où 7.4 ne comptait que les
paramètres. Le typedoc `None` d'une des bibliothèques est ainsi passé de 23 à
29 usages, et les six entrants sont exactement les keywords annotés `-> None`
(`__init__` compris). Les deux autres bibliothèques n'ont pas bougé, leurs
keywords ne portant pas cette annotation : l'écart avait donc l'air ciblé, ce
qui oriente vers un défaut local alors qu'il s'agit d'une règle générale.

## Pourquoi c'est coûteux

Le message d'échec était pourtant excellent (il nommait les keywords manquants
et la procédure de régénération) et il désignait quand même la mauvaise cause :
il invitait à régénérer une spec qui n'avait pas dérivé. Régénérer sans
comprendre aurait « réparé » la CI tout en cassant le test sur tout poste resté
en 7.4, sans que personne sache pourquoi.

Le signal qui a tranché est la MATRICE : le même test passait en 3.10 et
échouait en 3.14, alors que la version de Python n'a rien à voir. La 3.10 le
saute déjà pour une raison analogue (l'Optional implicite de PEP 484), et c'est
ce précédent, lu dans le code du test, qui a donné la réponse.

## Ce qu'on en fait

- Devant une CI rouge sans commit explicatif, **comparer les versions
  installées avant de lire le diff**. Le journal d'installation du runner porte
  la réponse (`Successfully installed ...`), et un plancher sans borne haute
  est le premier suspect.
- Un artefact de documentation dépend de la version de l'OUTIL, pas seulement
  du code : il se régénère avec l'interpréteur ET le Robot Framework du pin de
  `packaging/constraints-deploy.txt`, jamais avec ce que le poste a sous la
  main.
- Quand aucune spec committée ne peut satisfaire deux versions, la réponse du
  dépôt est un **skip documenté** portant la mesure et sa date, pas une
  comparaison affaiblie : le contrat reste entier sur la version qualifiée, et
  les NOMS de keywords, eux, restent comparés partout.
- Le plancher runtime ne monte pas pour autant : il dit ce dont le code a
  besoin (ici 7.4, pour le type `Secret`), et la version réellement qualifiée
  ensemble vit dans les fichiers d'environnement.

Même famille que [[demokit-shell-passe-aux-web-components]] : une cible ou un
socle amont bouge tout seul, et ce qui était vert la veille devient faux sans
qu'on ait rien fait. La différence est qu'ici la dérive entre par le
gestionnaire de paquets, donc elle est datable et reproductible.
