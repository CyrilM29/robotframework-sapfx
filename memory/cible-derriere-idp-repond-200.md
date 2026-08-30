# Une cible derrière un fournisseur d'identité répond 200, jamais 401

Relevé le 2026-08-26 en sondant le canal API (OData/HTTP) d'un site SAP Build
Work Zone hébergé sur un compte BTP de démonstration, protégé par un tenant
SAP Cloud Identity Services.

## Le fait

**Aucune route déclarée de ce site ne renvoie de défi d'authentification.**
Toute route existante répond `200` avec une page HTML d'amorçage de connexion
(qui pose des cookies de retour et un `nonce` variable). Zéro `302`, zéro
`401`, zéro `403` sur les deux hôtes du site. Seules les routes INEXISTANTES
répondent `404`, ce qui reste discriminant.

Le tenant d'identité, lui, parle correctement HTTP (`401` sur son API SCIM) :
le contraste entre les deux hôtes de la même chaîne est un critère de test
utilisable.

## Pourquoi c'est un piège de premier ordre

Un client HTTP voit un **succès** là où il n'a reçu aucune donnée. Un
préflight qui classe « 2xx = joignable » déclare le canal opérationnel sur
une cible qui n'a rien servi : c'est le « vert et faux » type, et il survit à
tous les tests qui ne regardent que le statut.

Le critère de discrimination doit être STRUCTUREL et non textuel : un
catalogue OData répond du JSON (`{`) ou du XML (`<?xml`), jamais un document
ouvert par `<!doctype`/`<html>`. Chercher un mot comme « login » dépendrait
de la langue du serveur (convention 3), et une page d'amorçage n'en contient
pas forcément.

## Deuxième piège, symétrique

Un garde qui refuse aux redirections de transporter l'authentification vers
un autre hôte lève une erreur de CONNEXION. Sans marqueur distinctif, ce cas
se classe « système injoignable », avec une remédiation du genre « le serveur
est-il démarré ? » : l'inverse exact de la vérité, puisque le serveur a
parfaitement répondu et a demandé une authentification ailleurs.

## Ce qu'il fallait pour aller plus loin : obtenu, et le fait tient toujours

La frontière a été franchie le **2026-08-26** avec une **clé de service** d'une
instance de service du sous-compte (`url`, `clientid`, `clientsecret`) : le
jeton `client_credentials` s'obtient, la bibliothèque l'obtient, et il ouvre le
backend du service.

**Et c'est là que le fait ci-dessus devient une preuve plutôt qu'une
hypothèse.** Présenté à l'hôte d'ADMINISTRATION du site avec un
`Authorization: Bearer` parfaitement valide, l'approuter répond **toujours
`200` avec sa page de connexion**. Il n'ignore pas un jeton invalide : il
ignore le mécanisme entier, parce qu'il attend une session du fournisseur
d'identité, pas un jeton porteur. Aucun identifiant supplémentaire ne changera
cela ; il faudrait un flux d'authentification d'un autre type.

La conséquence pratique est nette et se transpose à toute cible de cette
famille : **une clé de service ouvre le backend d'un service, pas l'interface
d'administration qui vit devant lui.** Confondre les deux fait chercher un
défaut d'autorisation là où il y a une différence de nature.

Le périmètre (scope) reste la deuxième condition, distincte : le jeton obtenu
ici porte un scope d'administration de launchpad, et pourtant une seule route
du backend l'accepte, les autres refusant en `403`. Jeton valide et route
autorisée sont deux questions séparées, et il faut savoir les diagnostiquer
séparément.

Voir [[gardes-qui-ne-peuvent-pas-echouer]] pour la même famille d'erreurs, et
[[angle-mort-canal-teste-en-indirect]] pour la raison pour laquelle ces
défauts avaient survécu.
