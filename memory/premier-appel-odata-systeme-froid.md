# Le premier appel OData d'un système froid ressemble à une panne de réseau

**2026-08-23, provisionnement d'un second système ABAP.** Deux diagnostics faux
d'affilée, la même cause :

1. Le préflight du canal API a rendu `status: unreachable`, `detail:
   "Connexion impossible : timed out"`, avec la remédiation « Système démarré ?
   vérifier base_url, port et verify_tls ». Or le port servait déjà le service
   webgui en HTTP 200 sur la même URL de base. Interrogé à la main avec un délai
   large, le catalogue Gateway répondait **200 avec 74 Ko de JSON** : la Gateway
   était active depuis le début.
2. Puis la suite du canal API a échoué sur le premier `$count` d'un service
   (`TimeoutError: timed out`), l'échec suivant n'étant que la cascade d'une
   variable de suite non posée.

Dans les deux cas, le rejeu immédiat passe au vert. Mesuré sur le catalogue :
**2,2 s au premier appel, 0,1 s au deuxième, 0 s au troisième.**

**Pourquoi :** sur un système jamais sollicité, le premier appel à CHAQUE
service OData en déclenche le chargement côté serveur, et ce coût est payé une
fois par service, pas une fois par système. Un client qui abandonne au bout de
son délai par défaut ne peut pas distinguer cela d'un serveur injoignable :
côté socket, les deux se ressemblent exactement. La remédiation affichée, elle,
oriente vers la connectivité, c'est-à-dire vers le seul endroit où il n'y a rien
à trouver. C'est le même schéma que le corps gzip pris pour un XML mal formé :
un message juste du point de vue de la couche qui le rédige, et trompeur pour
qui le lit. Voir [[reponse-compressee-sans-l-avoir-demandee]].

**Comment appliquer :** sur un système fraîchement démarré ou fraîchement
provisionné, un timeout au PREMIER appel n'est pas un verdict. Rejouer avant de
conclure, ou passer un `timeout=` large à `Open Api Session` pour la première
campagne. Et avant de partir réparer une Gateway prétendument inactive,
l'interroger une fois à la main avec un délai généreux : c'est une requête, pas
une session de débogage. À noter pour l'image ABAP 2023 : sa **Gateway est
active d'origine**, aucune activité IMG n'est nécessaire, contrairement à un
conteneur A4H re-créé (voir docs/ecc-validation.md §11.7).
