# Session d'un cFLP : trois mesures qui mentent si on les croit

Relevé le 2026-08-26 sur un launchpad SAP Build Work Zone (cFLP derrière un
tenant d'identité), en montant la campagne « résilience de session et
deep-links ». Chacun de ces trois points aurait produit un test vert et faux,
ou rouge sur un système sain.

## 1. Un cookie sans expiration est daté de 1969

La bibliothèque Browser encode l'absence d'expiration d'un cookie de session
par une date de **1969** (l'epoch moins un), pas par un champ vide ou absent.
Un prédicat « ce cookie n'a pas d'expiration » classe donc les cookies de
session en cookies PERMANENTS, et le test de perte de session passe à
l'envers. Le prédicat juste est « aucune expiration **future** ».

## 2. L'expiration réelle ne repasse pas par le fournisseur d'identité

Quand la session expire pour de bon, le shell ne renvoie pas vers le point
d'autorisation du tenant : il navigue vers une page de déconnexion servie par
l'hôte du **site**. Une assertion écrite sur le trajet de réauthentification
attend donc indéfiniment devant une session parfaitement expirée.

À ne pas confondre avec l'accès SANS session (première visite), qui lui
passe bien par un hôte distinct : ce sont deux trajets différents.

## 3. Les clés de configuration ne sont pas où leur nom les place

Les délais de session ne vivent pas sous la rubrique qui porte le nom du
shell, mais sous la configuration du RENDERER
(`renderers.<renderer>.componentData.config.sessionTimeout*`) et sous
l'adaptateur du conteneur
(`services.Container.adapter.config.systemProperties.sessionKeepAlive`).
Lire la configuration par un chemin supposé échoue ; il faut la parcourir.

## Le point tranché, qui rend la mesure possible

**Sonder la page ne réarme pas le maintien de session.** Vérifié en mesurant
d'abord sans aucune sonde entre deux relevés éloignés, puis avec sondage
continu : le rappel arrive au même moment. C'est ce qui permet d'observer une
expiration réelle sans jamais écrire d'attente fixe.

Le rappel avant expiration est un dialogue d'état **`Warning`**, à distinguer
de l'état `Error` d'un refus de navigation : l'état est l'ancre
locale-indépendante, le titre et le texte sont traduits. Mesuré à 16,5
minutes pour 16 déclarées.

## Corollaire d'écriture de campagne

Une expiration de session se teste en DEUX temps : une simulation en
quelques secondes (contexte dédié, cookies vidés) qui a sa place dans la
campagne, et l'observation réelle qui immobilise la cible pendant tout le
délai, donc **opt-in à deux tours** (un tag ET une variable) pour être sautée
par défaut même dans un run complet. Un tag seul dépend de la mémoire de
celui qui lance la commande.

Voir [[assertion-fiori-ni-trop-tot-ni-localisee]] et
[[shell-imbrique-ses-composants-web]].
