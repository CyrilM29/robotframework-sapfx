---
name: urllib-redirection-conserve-authorization
description: 2026-09-06, le gestionnaire de redirection standard d'urllib CONSERVE l'en-tête Authorization en suivant une redirection vers un autre hôte ; toute frontière réseau qui porte des identifiants doit monter sa propre garde d'origine, et un test qui doublonne le transport ne peut pas voir ce défaut
type: projet
date: 2026-09-06
---

Une revue externe du canal API a reproduit hors réseau, avec des données
factices, une fuite d'identifiants par redirection : le transport du token
endpoint OAuth2 passait par l'opener standard d'urllib, dont le
`HTTPRedirectHandler` **recopie tous les en-têtes de la requête d'origine
sauf `Content-Length`/`Content-Type`** en suivant une redirection.
`Authorization` (ici le Basic `client_id:client_secret`) partait donc vers
l'hôte désigné par un token endpoint compromis ou mal configuré.

Le dépôt avait pourtant déjà une garde (`_SameOriginRedirectHandler`), mais
montée sur le seul opener de SESSION, épinglée sur `base_url` : le token
endpoint (IAS, XSUAA) vivant légitimement sur un autre hôte que l'API, il
avait été sorti de cette garde, et il était sorti de TOUTE garde. Le correctif
épingle une garde propre sur l'origine du token endpoint lui-même (schéma
compris : un repli `https` vers `http` sur le même hôte est refusé aussi).

**Pourquoi :** deux leçons distinctes. (1) « Cette frontière échappe
légitimement à la garde X » ne signifie pas « cette frontière n'a besoin
d'aucune garde » : chaque frontière qui transporte des identifiants a la
sienne, épinglée sur SA cible. (2) Les tests unitaires du canal doublonnent
le transport (`lib._token_transport = fake`), donc un défaut situé DANS le
transport leur est invisible par construction : la propriété se verrouille
contre l'opener RÉEL (retrouver le handler dans `opener.handlers` et éprouver
son `redirect_request`), voir [[gardes-qui-ne-peuvent-pas-echouer]].

**Comment l'appliquer :** avant de faire confiance à `urllib.request.urlopen`
(ou à un opener sans handler de redirection maison) pour une requête portant
`Authorization`, une clé d'API ou un cookie sensible, poser la question :
« où cette requête peut-elle être redirigée, et qu'emporte-t-elle ? ». Même
passe pour le cache d'un secret à durée de vie : l'échéance locale se calcule
en SOUSTRAYANT la marge de la durée annoncée, jamais par un plancher qui la
dépasse (`max(30, 0.9*d)` gardait 30 s un token annoncé 10 s), et une durée
de 0 annoncée par le serveur est un fait à respecter, pas un défaut à
remplacer (`or 300` confondait 0 et absent).
