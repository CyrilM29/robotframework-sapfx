---
name: une-entree-racine-garde-ce-qu-un-sous-dossier-laisse-passer
description: 2026-09-21, un commit fourre-tout a fait entrer la collecte d'un AUTRE projet dans le dépôt ; la garde d'export a nommé les deux fichiers de RACINE et laissé passer les douze du sous-dossier, parce que son dossier parent était déjà attendu ; quatre citaient le chemin du studio, donc la release ne pouvait plus s'exporter, et c'est le scan de CONTENU qui l'a dit, pas le scan de périmètre
type: projet
date: 2026-09-21
---

Un commit fourre-tout (« sweep ») a fait entrer dans le dépôt du produit
l'instrumentation de collecte d'un autre projet : douze fichiers dans un
sous-dossier de `tools/`, plus deux fichiers à la racine (un marqueur de
verticale et une sauvegarde de la configuration MCP).

**La garde de périmètre de l'export public a mordu, mais à moitié.** Elle
vérifie que toute entrée de PREMIER NIVEAU est classée, publiée ou exclue, et
elle a donc refusé les deux fichiers de racine. Les douze autres sont passés
sans un mot : leur dossier parent, `tools/`, est une entrée attendue de longue
date, et la garde ne descend pas. Le périmètre était donc gardé à la racine et
libre en dessous, ce qui est le mode de panne d'une garde dont la granularité
ne suit pas celle du risque.

**Ce qui a rattrapé le coup est une garde d'une AUTRE nature** : le scan de
CONTENU de l'export, qui refuse certains motifs d'octets, a trouvé le chemin du
studio dans quatre des douze fichiers. Conséquence concrète, mesurée : en
l'état, la prochaine release ne pouvait plus s'exporter du tout. Deux gardes
indépendantes, l'une sur les chemins et l'autre sur les octets, et c'est la
seconde qui voyait ce que la première ne pouvait pas voir. C'est l'argument
qui avait justifié de faire tourner le scan de contenu sur le manifeste du
pack en plus de l'export (voir la revue packaging du 2026-08-19) : il vaut
aussi dans l'autre sens.

**Décision** : le code de collecte sort du dépôt (retiré de l'index, exclu
localement) et reste sur disque, où le recorder continue de tourner. C'est le
choix déjà arrêté pour le même collecteur dans un dépôt frère ; l'appliquer ici
n'invente rien, il restaure une cohérence qu'un commit fourre-tout avait
rompue.

**Ce qui n'était PAS un problème, et qu'il a fallu mesurer pour le savoir** :
rien n'avait fuité (la dernière release précède le commit fautif), le
collecteur n'écrit jamais dans son dossier d'installation (donc aucun
enregistrement ne pouvait atterrir ici), et la configuration MCP PUBLIÉE est
restée propre du début à la fin. Sur ce dernier point, la lecture naïve du
fichier de travail donnait l'inverse : tout le câblage du poste y est visible,
et c'est `skip-worktree` qui l'empêche de partir en commit, au prix que la
différence ne se voit dans aucun `git status`. Lire `git show HEAD:<fichier>`
avant d'affirmer ce qu'un dépôt publie, jamais le fichier ouvert sous les yeux.

**Comment appliquer** : après un commit fourre-tout, ne pas se fier au fait que
les gardes sont vertes, mais leur demander ce qu'elles COUVRENT. Une garde de
périmètre à la racine ne dit rien des sous-dossiers déjà admis. Et devant un
fichier de configuration versionné ET adapté localement, la version publiée est
celle de `HEAD`, pas celle du disque.
