---
name: canal-api-odata-v4-pieges
description: 2026-08-19, quatre comportements d'une cible OData v4 qu'aucune Gateway SAP v2 ne montre (auth mock sur le service, entité draft-enabled, Location non adressable, espace encodé en « + » refusé) ; une cible v4 n'est pas un confort de test, c'est ce qui révèle les défauts qu'une Gateway indulgente absorbe
type: projet
date: 2026-08-19
---

Une cible OData **v4** (le serveur applicatif local qui sert d'exemple Fiori
Elements au dépôt) se comporte différemment d'une Gateway SAP **v2** sur quatre
points, tous relevés en une session en montant la suite du canal API.

1. **L'authentification simulée protège aussi le service OData**, pas seulement
   l'application : sans identifiants, toute lecture part en HTTP 401
   (`WWW-Authenticate: Basic realm="Users"`). L'utilisateur simulé a un **mot de
   passe VIDE**, cas limite réel que la couche d'authentification doit accepter
   (elle décide sur « un utilisateur est fourni », pas sur « un mot de passe est
   non vide »).
2. **Une entité *draft-enabled* se dédouble.** Une création produit un
   BROUILLON, que ni le comptage ni une lecture ordinaire ne rendent (les deux
   ne voient que les entités actives), et dont la clé est **composite**
   (identifiant plus état actif/brouillon). Conséquence à retenir : sur un tel
   service, **un compte inchangé ne prouve aucun nettoyage**. Vérifier la
   disparition sur l'entité elle-même, jamais sur le total.
3. **L'URI annoncée à la création n'est pas forcément adressable.** Le serveur
   renvoie un `Location` pointant son entité de stockage interne des brouillons,
   qui répond 404 quand on la relit. Une fabrique de données suit ce que le
   serveur annonce : quand cette URI ne répond pas, il faut lui donner le chemin
   réel explicitement.
4. **L'espace encodé « à la formulaire HTML » (`+`) est REFUSÉ** (HTTP 400,
   « Expected "(", "/", or a whitespace but "+" found ») là où une Gateway SAP
   le tolère sans broncher. Or un filtre contient toujours des espaces.

**Pourquoi :** les points 2, 3 et 4 produisent chacun un « vert et faux »
possible. Le 4 était un vrai défaut du dépôt, invisible tant que le canal
n'était éprouvé que contre une Gateway v2 indulgente. Le 2 fait passer un test
de réversibilité alors qu'une donnée survit. Le 1 déguise un refus
d'authentification en « pas de données » quand l'erreur n'est pas remontée
telle quelle.

**Comment appliquer :** garder une cible v4 dans la validation du canal API,
pas seulement une Gateway v2 : c'est elle qui attrape ce que l'autre absorbe.
Sur un service draft-enabled, vérifier une suppression sur l'entité et jamais
sur le compte. Voir [[angle-mort-canal-teste-en-indirect]] pour la raison pour
laquelle ces défauts avaient survécu si longtemps.
