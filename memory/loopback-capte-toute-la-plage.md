---
name: loopback-capte-toute-la-plage
description: 2026-08-28, sous Windows un service publié sur 0.0.0.0 répond aussi sur 127.0.0.2, donc viser une adresse de bouclage « libre » atteint en silence l'autre système SAP du poste, que son identifiant identique ne trahit pas
type: projet
date: 2026-08-28
---

Deux systèmes SAP tournent en conteneurs sur le même poste, aux ports décalés.
Pour joindre le second en RFC, il a fallu réaligner numéro d'instance et port
en faisant écouter les ports de l'instance `00` sur une **seconde adresse de
bouclage**, `127.0.0.2`. Le montage fonctionne. Ce qui surprend, c'est ce qui
se passe quand la redirection n'est PAS posée.

Sous Windows, la boucle locale couvre **`127.0.0.0/8` en entier**. Un service
publié sur `0.0.0.0` répond donc aussi sur `127.0.0.2`. Le premier système
publiant sur toutes les interfaces, une connexion vers `127.0.0.2` en
`sysnr=00` **atteint ce premier système**, sans erreur, sans avertissement.

Le piège se referme parce que les deux conteneurs portent le **même identifiant
de système** (`A4H`) et le **même nom d'hôte interne** : la réponse à une sonde
d'identité naïve est strictement celle qu'on attendait. Seules la release
(754 contre 758), la version du kernel et la liste des composants logiciels
séparent les deux. L'adresse IP, elle, n'est pas une ancre : elle change d'un
démarrage à l'autre.

**Pourquoi :** un diagnostic réseau conclut normalement « le port répond, donc
c'est bon ». Ici, un port qui répond alors qu'aucune redirection n'est posée
est exactement le contraire d'une bonne nouvelle : c'est la preuve qu'un AUTRE
système capte l'adresse. Le premier script de diagnostic écrit pour ce montage
affichait « port repond » dans cet état, ce qui aurait envoyé lancer une
campagne contre la mauvaise cible.

**Comment appliquer :** ne jamais fonder l'identité d'une cible sur ce qui est
partagé entre systèmes d'un même parc (identifiant, nom d'hôte, adresse IP).
Une campagne prouve la release et le kernel de sa cible AVANT tout le reste, et
elle refuse explicitement la release du voisin plutôt que de simplement exiger
la sienne : le message d'échec nomme alors le vrai problème, « la campagne
viserait le mauvais système », au lieu d'un écart de version incompréhensible.
Corollaire pour les diagnostics d'environnement : distinguer « le port répond »
de « la redirection est posée », et traiter le premier sans le second comme une
alerte.

Voir aussi [[rfc-champ-inexistant-accuse-la-table]] et
[[plafond-de-lecture-pris-pour-un-total]] : trois cas où le signal disponible
désignait autre chose que la cause.
