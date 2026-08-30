# Sur une cible Cloud Foundry, un 404 dit trois choses différentes

Relevé le 2026-08-26 en balayant les routes du backend d'un service BTP avec un
jeton `client_credentials` valide, pour trouver lesquelles servent des données.

## Le fait

Trente chemins sondés, trois corps de réponse **structurellement distincts**
sous le même statut `404`, et chacun désigne une couche différente :

| Corps de la réponse | Couche qui répond | Ce que ça veut dire |
|---|---|---|
| `text/plain` : « Requested route (`<hôte>`) does not exist. » | le **routeur** de la plateforme | le préfixe n'est routé vers AUCUNE application |
| `text/html` : « Cannot GET `<chemin>` » | une **application** (Express) | le préfixe est routé, cette route-là n'existe pas |
| JSON structuré (`{"error": ...}`, `{"message": ...}`) | l'application, qui **dialogue** | la route existe et refuse la requête telle quelle |

**Le discriminant à retenir n'est pas le corps, c'est un en-tête** (relevé en
générant la campagne le même jour) : la réponse du routeur porte
`x-cf-routererror: unknown_route`. Un en-tête technique ne dépend d'aucune
langue et ne bouge pas avec une reformulation du message, là où le texte
« Requested route does not exist » est de la prose (convention 3). Le corps
reste utile au journal, pour le lecteur humain ; l'assertion, elle, vise
l'en-tête.

Et deux voisins qui complètent la carte : un `403` à corps **vide** signale une
route qui existe et dont l'autorisation refuse, un `400` porteur d'un message
métier (ici « Unsupported scenario ») signale une route qui attend un paramètre
qu'on n'a pas deviné.

## Pourquoi cela vaut d'être écrit

Traiter les `404` comme une masse indistincte fait conclure « le service
n'expose rien » alors que la lecture correcte est « le service expose quatre
préfixes, dont deux répondent et un dialogue ». C'est la différence entre
abandonner et savoir où creuser.

Le corollaire est une méthode de reconnaissance : **inclure toujours un chemin
volontairement absurde**, sur chaque préfixe, pour établir quelle couche répond
avant d'interpréter quoi que ce soit. Sans ce témoin, on ne sait pas si un `404`
qualifie la ressource ou l'hôte entier.

## Où trouver la liste des préfixes plutôt que la deviner

Sur ce type de cible, la **clé de service elle-même déclare les routes** : sa
section d'URLs liste un préfixe par composant du service. C'est une source
autrement plus fiable qu'un balayage de noms plausibles, et elle est fournie au
moment même où l'on obtient les identifiants.

Voir [[cible-derriere-idp-repond-200]] : la couche d'authentification devant ces
préfixes obéit à des règles encore différentes.
