# Un code injecté dans une page y reste, même après avoir été corrigé

**2026-08-24, campagne de launchpad ABAP pilotée par rf-mcp.** La bibliothèque
web injecte un bundle JavaScript dans la page (`window.__SAPFX`) au premier
keyword, et chaque appel suivant réinstalle ce même bundle. La réinstallation
était gardée par un simple « déjà présent », ce qui rendait le bundle
**idempotent, donc irremplaçable** : la première version reçue par une page y
restait pour la vie de cette page.

**Le symptôme, et pourquoi il ment.** Après avoir corrigé la bibliothèque et
l'avoir échangée à chaud dans le serveur en cours (rechargement des modules,
échange de la classe de l'instance, redécouverte des mots-clés), les nouveaux
mots-clés sont bien visibles côté Robot, mais l'appel sort en :

```
window.__SAPFX.<nouvelle fonction> is not a function
```

Le message accuse le mot-clé appelé. Le fautif est le cache d'injection, deux
couches plus bas, et le seul remède connu était de recharger la page, ce qui
détruit l'état du parcours en cours.

**Le correctif, et le vrai risque qu'il porte.** Le bundle porte désormais une
version dérivée de son propre contenu et la garde lit « présent ET de la même
version ». Le coût courant ne bouge pas : à chaque appel de mot-clé, une page
déjà à jour ne réinstalle rien. Mais rendre un code réinstallable n'est pas
gratuit quand ce code pose des HOOKS au moment de son injection (ici :
l'instrumentation des requêtes réseau qui sert l'attente de repos, et la capture
des messages éphémères). Deux façons opposées de se tromper :

- les reposer les DOUBLE : chaque requête est comptée deux fois, la page n'est
  jamais « au repos », et l'attente expire sur une page parfaitement calme ;
- les abandonner les PERD : la page est toujours au repos, ce qui est pire,
  parce que l'attente rend la main trop tôt et que l'échec tombe ailleurs, sur
  une étape innocente.

**Comment on s'en sort :** l'état mutable vit sur la fenêtre et non dans la
clôture du bundle (une réinstallation le RETROUVE), et chaque enveloppe porte sa
marque (une réinstallation n'en repose aucune). Détail qui a failli passer : la
marque du hook de messages est le RÉCEPTACLE lui-même et non un booléen, sinon
un hook laissé par une version antérieure continuerait de remplir une liste
orpheline, et la capture serait silencieusement vide.

**Comment le prouver sans navigateur, et pourquoi ça ne suffit pas.** Les tests
hors navigateur verrouillent la forme (garde par version, marques, état porté
par la fenêtre). La propriété réelle se mesure dans un vrai navigateur, et elle
se mesure de façon SYNCHRONE : on remet le compteur à zéro, on émet une requête
vouée à l'échec, et on lit le compteur immédiatement, avant que les
décrémentations (asynchrones) ne passent. Lire après coup donnerait zéro que le
hook soit doublé ou non, donc ne prouverait rien.

**Ce qui reste figé, et qu'aucun versionnement ne débloque :** les fichiers de
ressources déjà analysés par le serveur. Un ré-import sert la copie en mémoire,
donc les variables et mots-clés ajoutés depuis le démarrage restent invisibles
jusqu'au redémarrage du serveur. Explorer avec les mots-clés de bibliothèque,
pas avec la resource en cours d'écriture.
