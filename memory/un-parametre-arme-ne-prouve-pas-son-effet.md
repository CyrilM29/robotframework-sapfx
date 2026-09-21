---
name: un-parametre-arme-ne-prouve-pas-son-effet
description: 2026-09-14, le paramètre qui pilote le drapeau HttpOnly des cookies est positionné sur la cible et aucun des trois cookies de session ne le porte, ticket SSO compris ; seul un troisième canal (HTTP) peut le voir, et la valeur d'un paramètre de sécurité n'est pas un curseur, un contrôle « au moins 3 » serait vert et faux
type: projet
date: 2026-09-14
---

En croisant trois canaux sur la même cible (l'écran SAP GUI, le RFC et
l'HTTP/OData), un écart s'est révélé qu'aucun des deux premiers ne peut voir.

Le paramètre `icf/set_HTTPonly_flag_on_cookies` vaut `3`. Le canal RFC le lit,
l'écran confirme que cette valeur vient d'un défaut et non d'un réglage. Un
audit de configuration s'arrête là et conclut que les cookies sont protégés.

Sur le fil, **aucun des trois cookies de session ne porte le drapeau**, y
compris le ticket d'authentification et l'identifiant de session. Aucun ne
porte `Secure`, même servi en HTTPS, et aucun des cinq en-têtes de sécurité
usuels n'est posé.

**Pourquoi :** un paramètre décrit une INTENTION de configuration. L'effet
qu'il produit dépend du reste du système, et rien dans la valeur ne le dit. Un
canal de configuration ne peut donc pas répondre à « la protection existe-t-elle
», il ne répond qu'à « est-elle demandée ». Les deux se ressemblent dans un
rapport, et c'est la confusion la plus rentable de ce domaine : un écart est
examiné, une conformité ne l'est jamais.

**Corollaire, et il est plus réutilisable que le cas :** la valeur d'un
paramètre de sécurité **n'est pas un curseur**. On lit spontanément `3` comme
« plus durci que `0` ». L'observation le dément ici, quelle que soit la
sémantique officielle de l'échelle. Un contrôle écrit « au moins 3 » serait
vert et faux, et cette forme de contrôle est très naturelle à écrire.

**Comment appliquer :** pour tout paramètre dont l'effet est OBSERVABLE,
confronter la valeur déclarée et l'effet constaté, plutôt que de juger la
valeur. Trois règles encodées dans la bibliothèque :

1. le verdict ne dépend QUE de l'effet observé, jamais de la valeur, qui est
   rapportée brute ;
2. `declared_without_effect` est un verdict distinct, nommé, qui dit ce qu'il
   dit ;
3. une observation absente rend `undetermined` et **jamais** une conformité :
   un relevé de cookies vide n'est pas un système protégé, c'est une session
   qui n'a rien observé.

Garde de mesure indispensable, apprise d'une réserve de revue : **l'instrument
qui constate l'absence doit avoir été prouvé capable de constater la
présence**. Le lecteur de drapeau n'était couvert par aucun test, et un lecteur
aveugle aurait produit exactement la conclusion publiée. Le test écrit pour
lever ce doute a immédiatement trouvé un vrai défaut (trois orthographes du
drapeau sur cinq n'étaient pas reconnues). Un résultat négatif obtenu par un
instrument dont on n'a jamais vérifié qu'il sait dire « oui » n'est pas une
mesure.

Voir [[declare-n-est-pas-atteignable]] pour la famille à laquelle appartient
cet écart, et [[une-garde-qui-compare-deux-lectures-de-la-meme-source]] pour le
défaut de méthode voisin.
