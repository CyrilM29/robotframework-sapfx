# Canal API d'un site SAP Build Work Zone (BTP) : reconnaissance et frontière d'atteignabilité

- **Canal** : API (HTTP / OData), `SapApiLibrary` seule. Aucun navigateur, aucune
  bibliothèque web n'intervient dans ce plan.
- **Système observé** : site **SAP Build Work Zone, standard edition** hébergé sur
  un compte **SAP BTP** de trial (région `us10`, Cloud Foundry), protégé par un
  tenant **SAP Cloud Identity Services** (IAS). Quatre hôtes distincts sont
  concernés, tous **fournis en ligne de commande**, aucun n'est écrit dans le
  dépôt (convention 11, et une URL de tenant reste une donnée privée) :
  - `${WORKZONE_RUNTIME}` : le runtime du site (celui qui sert `/site`) ;
  - `${WORKZONE_SITE_MANAGER}` : l'administration, même sous-domaine avec `.dt.` ;
  - `${IAS_TENANT}` : le fournisseur d'identité ;
  - `${XSUAA_TOKEN_URL}` : le serveur d'autorisation du sous-compte.
- **Nature** : campagne de **reconnaissance en lecture seule**. Elle établit ce
  que le canal API peut atteindre, ce qu'il ne peut pas, et pourquoi. Elle ne
  prépare aucune donnée et n'en recoupe aucune.
- **Objectif** : documenter la frontière du 3e canal sur une cible BTP, de façon
  rejouable, et nommer précisément ce qu'il faudrait provisionner pour la
  franchir.
- **Préconditions** :
  - `SapApiLibrary` chargée et `resources/api_keywords.resource` importée ;
  - aucun identifiant dans le dépôt : le mot de passe de l'utilisateur du tenant
    arrive par variable d'environnement ou en type `Secret` sur la ligne de
    commande ;
  - fermeture garantie du canal (`Close Api Channel`), y compris après un échec.
- **Portée** : **lecture seule stricte**, runtime comme administration. Aucune
  écriture, aucune modification de configuration, aucun appel au Site Manager
  autre qu'une sonde de lecture.

> **Statut : exploration live complétée le 2026-08-26.** Tous les statuts HTTP
> ci-dessous ont été réellement obtenus ce jour-là, par appels rf-mcp unitaires,
> les sessions ouvertes puis refermées dans la même passe (registre final vérifié
> vide). Ce sont des **observations datées de cette cible**, jamais des
> constantes du produit.
>
> **Mise à jour du 2026-08-26, seconde passe : la frontière a été franchie.**
> Une clé de service a été provisionnée sur la cible, et tout ce qui suit reste
> vrai, mais le point de bascule a bougé. Lire la section « Après la clé de
> service » avant les scénarios : elle remplace le point 1 de « Ce qu'il
> faudrait provisionner » et transforme le scénario 7.

## Verdict (première passe, avant la clé de service)

**Le canal API ne franchit pas l'authentification de ce site, et il ne peut pas
la franchir sans un élément qui n'existe pas aujourd'hui sur la cible : une clé
de service (service key) d'une instance de service du sous-compte.**

Ce n'est pas un verrou d'architecture. La bibliothèque implémente déjà le mode
qu'il faudrait (OAuth2 client credentials), le serveur d'autorisation du
sous-compte a été atteint, et l'échec constaté se produit exactement à l'endroit
attendu : le refus du client, pas le transport. Il manque un identifiant de
client, pas une capacité.

Deux résultats secondaires valent autant que le verdict principal :

1. **Le site ne renvoie jamais de défi d'authentification.** Une route déclarée
   répond `HTTP 200` avec une page HTML d'amorçage de connexion. Un client HTTP
   voit donc un succès là où il n'a reçu aucune donnée. C'est le « vert et
   faux » type, et c'est le premier piège que toute suite visant BTP doit
   neutraliser explicitement.
2. **Le fournisseur d'identité, lui, parle correctement HTTP.** Son API SCIM
   répond `401`. Le contraste entre les deux hôtes est exploitable comme
   critère de test.

## Données observées

Relevé live le 2026-08-26. Sondes émises par `Get Gateway Status`, qui est
aujourd'hui la seule sonde **tolérante** de la bibliothèque (elle ne lève pas et
retourne le statut réel) ; corps lus, quand ils l'ont été, via l'extrait joint à
l'échec de décodage JSON de `Get Odata`. Les deux limites que cela impose sont
consignées plus bas.

### Runtime du site (`${WORKZONE_RUNTIME}`)

| Chemin sondé | Statut | Corps observé | Lecture |
|---|---|---|---|
| `/` | 200 | HTML d'amorçage de connexion | route déclarée, contenu inaccessible |
| `/site` (avec l'identifiant de site fourni) | 200 | non lu | route déclarée |
| `/site/<chemin volontairement inexistant>` | 200 | non lu | **route préfixe** : voir points de vigilance |
| `/sites` | 200 | HTML d'amorçage de connexion | route déclarée |
| `/login/callback` | 200 | non lu | route de rappel OAuth de l'approuter |
| `/ushell` | 404 | vide | route non déclarée |
| `/favicon.ico` | 404 | vide | aucun contenu statique anonyme |
| `/sap/opu/odata/iwfnd/catalogservice;v=2/ServiceCollection` | 404 | vide | **aucune Gateway ABAP ici** |
| `/sap/bc/ui2/start_up` | 404 | vide | aucun ushell ABAP ici |
| `/ceci-nexiste-absolument-pas-2026` | 404 | vide | témoin de contrôle |

### Administration, Site Manager (`${WORKZONE_SITE_MANAGER}`)

| Chemin sondé | Statut | Corps observé | Lecture |
|---|---|---|---|
| `/sites` | 200 | HTML d'amorçage de connexion | route déclarée |
| `/api` | 404 | vide | route non déclarée |
| `/api/v1` | 404 | vide | route non déclarée |
| `/ceci-nexiste-absolument-pas-2026` | 404 | vide | témoin de contrôle |

### Fournisseur d'identité (`${IAS_TENANT}`)

| Chemin sondé | Statut | Corps observé | Lecture |
|---|---|---|---|
| `/.well-known/openid-configuration` | 200 | JSON OIDC complet | découverte **anonyme**, exploitable |
| `/scim/Users` | 401 | vide | l'endpoint existe et exige une authentification |

### Serveur d'autorisation du sous-compte (`${XSUAA_TOKEN_URL}`)

| Chemin sondé | Statut | Corps observé | Lecture |
|---|---|---|---|
| `/.well-known/openid-configuration` | 200 | JSON OIDC complet | découverte anonyme |
| `/oauth/token` (client volontairement inexistant) | 401 | `{"error":"invalid_client","error_description":"Bad credentials"}` | transport correct, client absent |

### La page servie en 200 est une page de connexion, pas une donnée

Le corps renvoyé par `/` et par `/sites`, sur les deux hôtes, commence par le
même document HTML : une icône en `data:`, puis un script qui pose les cookies
`fragmentAfterLogin` et `locationAfterLogin` avant de poursuivre la chaîne de
connexion. Le `nonce` du script change à chaque appel, le reste est identique.
Sur l'hôte d'administration la variante diffère par ses attributs de cookie et
par un cookie `signature` supplémentaire.

Autrement dit : le site répond `200 OK`, avec un `Content-Type` HTML, à un client
qui a envoyé `Accept: application/json` et qui n'est pas authentifié. Aucun `302`,
aucun `401`, aucun `403` n'a été observé sur les deux hôtes du site.

### L'authentification Basic ne franchit rien

Une session ouverte avec l'utilisateur du tenant et son mot de passe, en Basic,
obtient exactement la même réponse : `200` et la même page d'amorçage.
L'en-tête `Authorization: Basic` est ignoré par l'approuter. **Une seule
tentative a été émise**, délibérément : un tenant IAS verrouille un compte après
quelques échecs, et un compte de travail ne se dépense pas en sondes.

### Ce que le fournisseur d'identité déclare

Document de découverte OIDC du tenant, lu anonymement :

- `authorization_endpoint` : `<tenant>/oauth2/authorize` ;
- `token_endpoint` : `<tenant>/oauth2/token` ;
- `grant_types_supported` : `authorization_code`, `client_credentials`,
  `password`, `refresh_token`, `urn:ietf:params:oauth:grant-type:jwt-bearer`,
  `urn:ietf:params:oauth:grant-type:saml2-bearer` ;
- `token_endpoint_auth_methods_supported` : `tls_client_auth`,
  `client_secret_basic`, `client_secret_post`, `private_key_jwt` ;
- `code_challenge_methods_supported` : `plain`, `S256` ;
- `scopes_supported` : `openid`, `email`, `profile`, `groups`, `offline_access`.

Document de découverte du serveur d'autorisation du sous-compte :

- `token_endpoint` : `<sous-compte>/oauth/token` ;
- `token_endpoint_auth_methods_supported` : `client_secret_basic`,
  `client_secret_post`, `tls_client_auth` ;
- un alias mTLS existe, sur un hôte `...authentication.cert...` distinct.

Ces deux documents disent la même chose du point de vue du canal API : les modes
d'authentification que `SapApiLibrary` sait déjà parler (OAuth2 client
credentials, mTLS) sont **déclarés supportés** par la cible. Le mode Basic, lui,
n'est proposé nulle part comme moyen d'accéder au site.

### Le mode OAuth2 de la bibliothèque atteint réellement la cible

Session ouverte sur le runtime avec `token_url` pointant le serveur
d'autorisation du sous-compte et un couple client volontairement inexistant. Le
premier appel échoue en nommant précisément l'étape et la cause :

> Le token endpoint `<sous-compte>/oauth/token` a refusé le client (HTTP 401) :
> `{"error":"invalid_client","error_description":"Bad credentials"}`
> (vérifier client_id/client_secret/oauth_scope).

C'est le résultat qui localise la frontière : la chaîne complète (résolution DNS,
TLS, requête de token, lecture de l'erreur OAuth) fonctionne. Seul l'identifiant
de client manque.

### Ce qu'il faudrait provisionner pour aller plus loin

Rien de tout cela ne peut être fabriqué depuis un test, et rien n'a été tenté :

1. **Une clé de service d'une instance de service du sous-compte** (par exemple
   une instance du service de launchpad, ou une instance de `xsuaa` liée à
   l'application). Elle fournit le triplet que la bibliothèque consomme déjà :
   `url` (donc `token_url` en lui ajoutant `/oauth/token`), `clientid` et
   `clientsecret`. C'est le seul élément bloquant.
2. **Le périmètre (scope) associé**, faute de quoi un token obtenu sera refusé
   par la route visée, ce qui est un échec différent et doit être diagnostiqué
   comme tel.
3. **Le chemin exact de l'API de contenu**, s'il en existe une sur cette
   édition : les deux familles plausibles sondées côté administration (`/api` et
   `/api/v1`) répondent `404`, donc l'API de contenu, si elle est disponible, ne
   vit pas sur l'hôte d'administration du site aux chemins essayés.

Tant que le point 1 n'est pas fourni, tout scénario de lecture de contenu par
HTTP reste **invérifiable**, et ce plan n'en propose aucun.

## Après la clé de service (seconde passe, 2026-08-26)

Le point 1 a été provisionné le jour même : une instance de service a été créée
sur le **plan de SERVICE** de l'édition (celui dont la description parle
d'intégration par API), distinct du plan d'APPLICATION qui porte l'abonnement au
site et ne s'instancie pas. Sa clé fournit le triplet attendu. Les valeurs
n'entrent nulle part dans le dépôt : elles vivent dans quatre variables
d'environnement du poste (convention 11), l'identifiant de client autant que le
secret, parce qu'un identifiant de client XSUAA désigne un tenant précis.

**Le point 1 est levé, le point 2 se précise, le point 3 tombe.**

### Le canal s'ouvre, et c'est la bibliothèque qui l'ouvre

Vérifié live, 3 tests sur 3, par une suite de contrôle jouée avec `robot` :
`Open Api Session` en OAuth2 client credentials obtient le jeton (`List Api
Sessions` rapporte bien `oauth`), et un appel atteint le service. Le scénario 7
de ce plan, dont l'objet était de constater `invalid_client`, n'est donc plus un
test d'échec permanent : c'est le point d'entrée du canal.

Le jeton obtenu vaut **8 heures** et porte un scope d'administration de
launchpad. C'est la réponse au point 2, et elle est plus intéressante que prévu :
**un scope large ne rend pas les routes accessibles pour autant** (voir
ci-dessous). Jeton valide et route autorisée restent deux questions séparées, à
diagnostiquer séparément.

### Ce que la clé ouvre : le backend du service, pas l'administration du site

C'est le fait de conception à retenir, et il **confirme** le verdict de la
première passe au lieu de l'annuler.

L'hôte d'administration du site, présenté avec un `Authorization: Bearer`
parfaitement valide, répond **toujours `200` avec sa page de connexion HTML**.
Il n'ignore pas un jeton invalide : il ignore le mécanisme entier, parce qu'il
attend une session du fournisseur d'identité et non un jeton porteur. Le
préflight le classe correctement en `login_page`, et cette classification est
donc désormais **prouvée jeton en main**, ce qui n'était pas possible avant.

Le point 3 tombe pour cette raison : il n'existe pas d'API de contenu à trouver
sur l'hôte d'administration, parce que cet hôte n'est pas une API. Un montage
qui voudrait l'administrer par HTTP relèverait d'un flux d'authentification
d'un autre type (`authorization_code` contre le fournisseur d'identité), qui
n'a pas été tenté et sort du périmètre de ce plan.

### La clé déclare elle-même les routes du backend

La clé de service contient une section d'URLs listant un préfixe par composant
du service. C'est la source à utiliser, bien plus fiable qu'un balayage de noms
plausibles, et elle arrive au moment même où l'on obtient les identifiants.

Balayage de ces préfixes avec le jeton, relevé live :

| Préfixe | Réponse | Lecture |
|---|---|---|
| `<service>/cep-runtime/graphql` | `400` avec un message de validation GraphQL | **la seule route qui accepte le jeton et traite la requête** |
| `<service>/navigation/*` | `403` corps vide | route existante, autorisation refusée |
| `<service>/interest_card_service` | `403` corps vide | idem |
| `<service>/cpss*` | `400 {"error":"Unsupported scenario"}` | l'application dialogue, le paramètre attendu n'a pas été trouvé |
| `<service>/odata`, `/bff`, `/roleMapping` | `404` d'application | préfixe routé, aucune route publique à ce niveau |
| tout autre préfixe | `404` du routeur de plateforme | préfixe non routé du tout |

La route GraphQL est un serveur Apollo dont **l'introspection est désactivée par
politique de production** : son refus le dit explicitement, et ce n'est donc pas
un refus d'authentification. Sans introspection, le schéma n'est pas
découvrable, ce qui interdit d'écrire une requête utile sans documentation
externe. C'est la limite honnête à consigner.

### Ce que cela change pour une campagne

Peu, et il faut le dire. Le canal est ouvert mais n'atteint aucune **donnée
métier** du site : la conclusion de la section « Y a-t-il matière à un
croisement écran / API » reste entière. Ce qui a changé est la nature du
livrable : ce plan documentait une frontière infranchissable, il documente
maintenant une frontière **cartographiée**, avec un point d'entrée réel et trois
familles de refus distinctes. Les scénarios 1 à 6 et 8 restent valides tels
quels ; le 7 doit être réécrit dans son cas nominal le jour où la campagne est
générée.

## Y a-t-il matière à un croisement écran / API sur cette cible ?

**Non, et il ne faut pas en fabriquer un.** Trois raisons, toutes constatées :

1. Le canal API n'atteint aucune donnée du site (verdict ci-dessus).
2. Le site ne repose sur aucun système SAP de données : il n'y a ni Gateway ABAP
   (`404` sur le catalogue standard) ni service OData propre observable.
3. L'unique application du catalogue est servie par une **URL externe** (fait
   relevé par le plan `specs/workzone-launchpad-btp-perception.md`, section
   « Iframe applicative » : le contenu réel est la démonstration Shopping Cart
   d'OpenUI5). Son contenu n'est donc pas une source de données SAP, et le
   recouper par une API produirait un test qui a l'air d'un croisement sans en
   être un.

Le pendant BTP de `tests/robot/cross/croisement_ddic_odata.robot` n'a donc pas
d'objet ici. Il en aurait un sur un site dont les applications consomment un
service OData d'un backend SAP, ce qui n'est pas le cas de cette cible.

## Scénarios

Seuls figurent ici les scénarios dont chaque étape a été constatée live le
2026-08-26. Ils forment une campagne courte, dont la valeur est de **documenter
et surveiller une frontière**, pas de vérifier une fonction métier.

### 1. Le canal atteint la cible, et la cible n'est pas une Gateway ABAP

- **Étapes** :
  1. Ouvrir le canal API sur le runtime du site.
  2. Sonder le chemin standard du catalogue de services de la Gateway ABAP.
  3. Sonder le chemin standard de démarrage de l'ushell ABAP.
- **Résultat attendu** : les deux chemins répondent `404`. La cible est
  joignable (le réseau, le TLS et le nom d'hôte répondent) et ne porte aucun des
  deux points d'entrée ABAP. L'assertion porte sur le **statut**, jamais sur un
  texte.
- **Critère d'acceptation** : un `404` ici est le résultat NORMAL et attendu ;
  c'est un statut différent qui devrait alerter (une cible qui se mettrait à
  répondre `200` sur le catalogue Gateway ne serait plus la même cible).
- **Keywords métier manquants** : `Probe Api Endpoint`, sonde tolérante d'un
  chemin quelconque, qui retourne le statut réel sans le traduire en vocabulaire
  Gateway (voir « Lacunes de bibliothèque », point 2).

### 2. Le préflight standard du canal échoue, et son diagnostic ne convient pas à BTP

- **Étapes** :
  1. Sur le canal ouvert, exécuter le préflight de disponibilité du canal.
  2. Recueillir l'état classé et sa remédiation.
- **Résultat attendu** : le préflight échoue avec l'état `catalog_not_found`. Ce
  n'est pas une anomalie de la cible : c'est le préflight qui est écrit pour une
  Gateway ABAP. La campagne le consigne comme tel et ne s'en sert pas comme
  porte d'entrée.
- **Critère d'acceptation** : la campagne **ne doit pas** conditionner ses autres
  scénarios à ce préflight, sous peine de ne jamais s'exécuter sur BTP.
- **Keywords métier manquants** : `Api Target Should Not Be An Abap Gateway`,
  qui transforme ce constat en assertion positive et lisible, au lieu d'un
  préflight détourné.

### 3. Une route déclarée répond 200 sans donner accès à quoi que ce soit

- **Étapes** :
  1. Sonder la racine du runtime.
  2. Sonder la route du site.
  3. Lire le corps de la réponse et déterminer sa nature.
- **Résultat attendu** : statut `200`, et le corps est une page HTML d'amorçage
  de connexion, reconnue **structurellement** (document HTML là où le canal a
  demandé du JSON, présence des cookies de reprise après connexion), jamais par
  un texte localisé. Le scénario **échoue** si l'on se contente du statut : c'est
  précisément ce qu'il démontre.
- **Critères d'acceptation** :
  - aucune assertion de la campagne ne se satisfait d'un `200` seul ;
  - la nature du corps est établie avant toute conclusion sur l'accès ;
  - le `nonce` du script change d'un appel à l'autre : il n'entre dans aucune
    assertion.
- **Keywords métier manquants** : `Api Response Should Not Be A Login Page`, la
  garde qui transforme le piège en échec explicite, et
  `Api Endpoint Should Require Authentication`, qui exige un défi réel (`401` ou
  `403`) et **refuse** le `200` porteur d'une page de connexion.

### 4. L'authentification Basic ne franchit pas l'approuter

- **Étapes** :
  1. Ouvrir un second canal sur le même runtime, avec l'utilisateur du tenant et
     son mot de passe en Basic.
  2. Rejouer la sonde de la racine.
  3. Comparer la nature de la réponse à celle du canal anonyme.
- **Résultat attendu** : réponse identique en statut et en nature. Le Basic est
  ignoré.
- **Critères d'acceptation** :
  - **une seule tentative par exécution**, jamais de boucle ni de nouvel essai :
    un tenant IAS verrouille un compte après quelques échecs ;
  - le mot de passe ne traverse qu'en type `Secret` et n'apparaît dans aucun
    journal ;
  - le scénario est **désactivable** par variable, pour qu'une exécution
    répétée en intégration continue ne consomme pas de tentatives.
- **Keywords métier manquants** : `Api Basic Authentication Should Not Grant
  Access`, qui encapsule la tentative unique et son verdict.

### 5. Le fournisseur d'identité, lui, répond par un vrai défi d'authentification

- **Étapes** :
  1. Ouvrir un canal sur le tenant du fournisseur d'identité.
  2. Sonder son API SCIM sans aucune authentification.
- **Résultat attendu** : `401`. L'endpoint existe et exige une identité. C'est le
  **contraste** avec le scénario 3 qui fait la valeur du test : sur la même
  campagne, deux hôtes de la même chaîne se comportent de deux façons
  incompatibles face à un client HTTP.
- **Critère d'acceptation** : aucun identifiant n'est envoyé sur ce scénario. Une
  sonde anonyme ne peut pas verrouiller un compte.
- **Keywords métier manquants** : aucun au-delà de `Probe Api Endpoint` et de
  `Api Endpoint Should Require Authentication` déjà proposés.

### 6. La chaîne d'authentification déclare les modes que la bibliothèque sait parler

- **Étapes** :
  1. Lire le document de découverte OIDC du tenant du fournisseur d'identité.
  2. Lire celui du serveur d'autorisation du sous-compte.
  3. Vérifier que les deux publient un `token_endpoint` et que les modes
     `client_credentials` et l'authentification du client par secret y sont
     déclarés.
- **Résultat attendu** : les deux documents répondent `200` et déclarent les
  modes attendus. La campagne consigne le `token_endpoint` réel, qui est la
  valeur à reporter dans une configuration le jour où une clé de service
  existera.
- **Critères d'acceptation** :
  - la lecture est **anonyme** et ne consomme aucune tentative de connexion ;
  - aucune URL d'hôte n'est écrite dans la suite : elles sont toutes des
    paramètres ;
  - l'assertion porte sur la présence des modes dans la liste déclarée, jamais
    sur l'ordre ni sur la liste entière (un fournisseur peut en ajouter).
- **Keywords métier manquants** : `Read Identity Provider Configuration` (lecture
  du document de découverte, retour JSON-safe) et
  `Identity Provider Should Support Grant` (assertion sur un mode déclaré).

### 7. Le mode OAuth2 atteint le serveur d'autorisation et échoue sur le client, pas sur le transport

- **Étapes** :
  1. Ouvrir un canal sur le runtime, configuré en OAuth2 client credentials
     contre le serveur d'autorisation du sous-compte, avec un couple client
     **volontairement inexistant**.
  2. Émettre une lecture quelconque.
  3. Recueillir l'échec.
- **Résultat attendu** : l'échec nomme le `token_endpoint` réellement contacté,
  le statut `401` et le code d'erreur OAuth `invalid_client`. Il ne mentionne ni
  problème de réseau ni URL introuvable.
- **Critères d'acceptation** :
  - le diagnostic porte sur le **code d'erreur OAuth**, jamais sur le texte
    `Bad credentials`, qui est un libellé du serveur ;
  - le couple client utilisé est manifestement fictif et n'est pas un secret ;
  - le jour où une clé de service est fournie, ce même scénario devient le point
    de bascule : il doit alors être remplacé par une lecture réelle, pas
    conservé comme un test d'échec permanent.
- **Keywords métier manquants** : `Open Api Channel With Service Key`,
  l'ouverture d'un canal à partir des champs d'une clé de service BTP
  (`url`, `clientid`, `clientsecret`), qui reste aujourd'hui la seule porte
  d'entrée envisageable et n'a donc pas pu être exercée dans son cas nominal.

### 8. Fermer le canal sur tous les chemins

- **Étapes** :
  1. Fermer toutes les sessions du canal.
  2. Vérifier que le registre du canal est vide.
- **Résultat attendu** : aucune session ni connexion résiduelle, y compris après
  l'échec attendu du scénario 7. Vérifié live : registre vide après fermeture.
- **Keywords métier manquants** : aucun. `Close Api Channel` existe et vit dans
  le teardown de suite. En revanche, voir la lacune 6 : la garde de non-fuite
  d'identifiants doit être durcie avant d'être utilisée comme oracle.

## Lacunes de bibliothèque relevées (convention 12)

Toutes constatées pendant cette exploration, aucune contournée en silence.

1. **Aucune lecture HTTP brute.** Le canal n'expose aucun mot-clé rendant
   `(statut, en-têtes, corps)` pour un endpoint qui n'est pas OData. Pour lire le
   corps d'une page il a fallu passer par le **message d'échec** de
   `Get Odata` (« Réponse illisible en JSON », qui joint 400 caractères du
   corps). C'est un détournement, pas une méthode. Sur une cible BTP, la
   réponse la plus fréquente est justement du HTML : la bibliothèque ne sait pas
   la lire proprement. **Remède proposé** : un mot-clé `Get Http Response` dans
   `SapApiLibrary`, retour JSON-safe `{status, headers, content_type, body}`,
   avec extrait borné et annoncé.

2. **La sonde tolérante est habillée en Gateway ABAP.** `Get Gateway Status` est
   aujourd'hui la seule sonde qui ne lève pas, et c'est donc l'outil de toute
   reconnaissance. Or elle traduit ses résultats dans un vocabulaire qui n'a
   aucun sens ici : un `200` devient « Catalogue Gateway joignable », un `404`
   devient « Catalogue introuvable » avec une remédiation citant le composant
   Gateway, et un `401` propose de « vérifier le mandant licencié, sur A4H sans
   licence seul SAP*/000 passe ». Sur BTP ces trois messages envoient chercher au
   mauvais endroit. Il manque en outre deux états à `classify_gateway_probe` :
   « redirection vers un fournisseur d'identité » et « 200 porteur d'une page de
   connexion ». **Remède proposé** : séparer la sonde (générique, sans
   vocabulaire de produit) de sa classification Gateway, qui reste ce qu'elle
   est pour une cible ABAP.

3. **La sonde tolérante est invisible à la télémétrie.** `_probe` court-circuite
   `_request`, donc les compteurs de session ne la voient pas. Mesuré : après une
   quinzaine de sondes réseau, la session `runtime` déclarait `requests: 2`, les
   deux seuls appels passés par `Get Odata`. Conséquence directe : le garde-fou
   `Api Channel Should Show Activity`, dont tout l'objet est de prouver que le
   réseau a bien été traversé, **échouerait** sur une campagne de reconnaissance
   entièrement légitime. **Remède proposé** : compter les sondes dans la
   télémétrie, en les distinguant au besoin des appels ordinaires.

4. **Aucun contrôle des en-têtes de requête.** L'en-tête `Accept` est figé à
   `application/json` à l'ouverture de session, et aucun mot-clé public ne permet
   de le surcharger pour une lecture. Sur un approuter BTP, c'est précisément
   l'en-tête `Accept` qui arbitre entre une page HTML et un défi JSON : la
   bibliothèque ne peut donc même pas poser la question. Cette hypothèse est
   restée **non vérifiée** faute de moyen, et elle est consignée comme telle.
   **Remède proposé** : un argument `headers` sur les lectures, ou au minimum
   sur le mot-clé de lecture brute du point 1.

5. **Le garde de non-fuite d'identifiants passe sur un état vide.**
   `Api Channel State Should Not Leak Credentials` vérifie qu'aucun mot de passe
   ni en-tête d'autorisation n'apparaît dans l'état du canal. Constaté live : il
   **passe** sur `{'api_sessions': [], 'rfc_connections': []}`. Un oracle qui se
   satisfait de l'absence de matière ne prouve rien le jour où la matière
   disparaît pour une autre raison. **Remède proposé** : échouer quand le
   registre inspecté est vide, ou exiger explicitement le nombre de sessions
   attendu.

6. **Note de conception, non constatée sur cette cible.** Le transport refuse les
   redirections qui changent d'origine (garde délibérée : une redirection ne doit
   pas emporter l'authentification vers un autre hôte). Le refus remonte en
   `URLError`, que la classification range dans `unreachable`, avec une
   remédiation du genre « système démarré ? vérifier le port ». Sur une cible qui
   redirigerait réellement vers son fournisseur d'identité, ce diagnostic
   désignerait une panne réseau au lieu d'une exigence d'authentification. **Ce
   cas n'a pas été rencontré ici** : le site ne renvoie jamais de redirection, il
   répond `200`. La note est consignée pour ne pas être redécouverte sur une
   autre cible, et elle ne doit pas être présentée comme une observation live.

## Points de vigilance

**Un `200` ne prouve rien sur cette famille de cibles.** C'est le point unique le
plus important de ce plan. Le site répond `200` avec une page de connexion à tout
client non authentifié. Une suite qui asserte un statut `200`, ou qui se contente
de « la requête n'a pas levé », est verte et fausse. La nature du corps doit être
établie.

**Le `404` discrimine les préfixes de route, pas les ressources.** Un chemin
inconnu répond `404`, ce qui rend la sonde informative. Mais `/site/<n'importe
quoi>` répond `200` : `/site` est une route **préfixe**, et sous un préfixe
déclaré, l'existence d'une ressource ne peut pas être établie anonymement. Un
inventaire de routes bâti sur ce constat ne doit donc revendiquer que la
**surface de routage déclarée**, jamais l'existence d'une ressource précise.

**Le témoin de contrôle est obligatoire.** Chaque hôte sondé doit recevoir un
chemin volontairement absurde. Sans lui, on ne sait pas si les `404` observés
signifient quelque chose ou si l'hôte répond `404` à tout. Les deux hôtes du site
ont été qualifiés ainsi.

**Ne jamais dépenser un compte de travail en sondes.** Un tenant IAS verrouille
un compte après quelques tentatives. Les scénarios anonymes (découverte OIDC,
SCIM) ne consomment rien ; le seul scénario qui présente des identifiants n'en
présente qu'une fois, et doit rester désactivable.

**Un client OAuth n'est pas un compte utilisateur.** La tentative du scénario 7
utilise un identifiant de client fictif contre le serveur d'autorisation : elle
ne met aucun compte en danger. Ne pas confondre les deux, et ne pas transposer la
prudence du scénario 4 en interdiction du scénario 7.

**Une session par origine.** Le canal refuse une URL absolue qui change
d'origine. Les quatre hôtes de la chaîne exigent donc quatre alias distincts,
ouverts et fermés ensemble. Ce n'est pas une contrainte gênante, c'est ce qui
rend le tableau des observations lisible.

**Sous rf-mcp, les mots-clés de resource et ceux de bibliothèque ne voient pas le
même registre de sessions.** Constaté live, deux appels consécutifs dans la même
session rf-mcp : `List Api Sessions` appelé directement retourne les six sessions
ouvertes, le même mot-clé appelé à travers un mot-clé de
`resources/api_keywords.resource` retourne une liste vide, et
`Api Channel Should Be Available` échoue sur « Aucune session API : appeler Open
Api Session d'abord ». Le mécanisme documenté est la partition de l'état par
espace de noms d'exécution (`sapfx_common.session_context`, que rf-mcp segmente
par test synthétique). Conséquence pratique pour la génération : une vérification
live pas à pas via rf-mcp qui ouvre le canal par un mot-clé de bibliothèque puis
l'utilise par un mot-clé métier verra un canal fermé, ce qui ressemble
exactement à un défaut de la resource. **Ouvrir et utiliser le canal par le même
niveau d'appel** pendant la vérification live, et se fier au run `robot` réel
pour trancher.

**Piège d'écriture rf-mcp.** Un argument positionnel contenant un `=` (par
exemple un chemin portant une query, `/site?siteId=...`) est interprété comme un
argument nommé et produit « missing value for argument 'path' ». Passer la query
en argument nommé, ou éviter la query dans le chemin pendant la vérification
live.

**Le nonce change à chaque appel.** La page de connexion porte un `nonce` de
script différent à chaque réponse. Il n'entre dans aucune assertion, ni comme
ancre ni comme témoin de stabilité.

**Lecture seule.** La campagne ne modifie rien, ni sur le runtime ni sur
l'administration. Le Site Manager n'est qu'une source d'observation : aucune
route d'écriture n'y a été appelée, et aucune ne doit l'être.

## Handoff sap-generator

Portes à franchir avant d'écrire quoi que ce soit :

1. **Décider si la campagne vaut d'être générée maintenant.** Elle documente une
   frontière et ne vérifie aucune fonction métier. Sa valeur est réelle mais
   étroite : elle empêche une suite BTP d'être écrite sur un `200` trompeur, et
   elle surveille la chaîne d'authentification. Si la réponse est non, ce plan
   reste le livrable et rien n'est généré.
2. **Ne pas générer les scénarios manquants.** Aucun scénario de lecture de
   contenu, de volumétrie ou de croisement ne figure ici, parce qu'aucun n'a pu
   être constaté. Ne pas en ajouter par symétrie avec les campagnes ABAP.
3. **Traiter les lacunes 1 à 5 avant, ou assumer le détournement.** Les scénarios
   3 et 5 ont besoin d'une lecture brute (lacune 1) et d'une sonde au vocabulaire
   neutre (lacune 2). Écrits sur `Get Gateway Status` et sur le message d'erreur
   de `Get Odata`, ils seraient fragiles et illisibles. La lacune 5 doit être
   corrigée avant que la garde concernée serve d'oracle.
4. **Placer les nouveaux mots-clés métier dans `resources/api_keywords.resource`**,
   en gardant le vocabulaire du fichier, et y faire vivre les quatre hôtes sous
   des noms métier paramétrés, jamais en dur (convention 1 et convention 11).
5. **Ventiler la suite sous `tests/robot/api/`**, et la marquer explicitement
   comme campagne de reconnaissance, non comme recette fonctionnelle.
6. **Exécuter chaque étape live avant écriture**, et fermer le canal sur tous les
   chemins, y compris après l'échec attendu du scénario 7.
7. **Stampiller la suite avec ce plan** après génération.

## Écarts constatés à la génération (2026-08-26)

La campagne a été générée le jour même de la seconde passe, contre la cible
réelle, et validée **9/9 en deux exécutions consécutives** (plus une exécution
sans les hôtes optionnels : 6 réussis, 3 sautés, dégradation propre). Six
écarts entre ce plan et ce que la génération a constaté.

1. **Les mots-clés ne vivent PAS dans `resources/api_keywords.resource`**,
   contrairement au point 4 du handoff, mais dans un fichier dédié,
   `resources/page_objects/workzone_api.resource`. La raison est la frontière
   du dépôt : `api_keywords.resource` porte le vocabulaire GÉNÉRIQUE du canal
   (ouvrir un canal, compter des entités), partagé par toutes les cibles, alors
   que ces mots-clés nomment les hôtes et les familles de refus d'UNE cible.
   Les y verser aurait mélangé les deux couches, et les campagnes Work Zone
   voisines ont déjà chacune leur fichier sous `page_objects/`.
2. **Le préflight ne voit pas la page de connexion sur son chemin par défaut.**
   `Get Gateway Status` sonde le chemin du CATALOGUE Gateway, absent de cet
   hôte, et répond donc `catalog_not_found` : correct, mais ce n'est pas le
   classement que le plan attendait. Éprouver `login_page` demande de sonder la
   RACINE (`catalog_path=/`). Le scénario garde les deux constats, qui
   enseignent deux choses différentes.
3. **Le discriminant d'un 404 de plateforme est un EN-TÊTE, pas un corps.**
   La réponse du routeur porte `x-cf-routererror`, technique et indépendant de
   la locale, là où la première passe s'appuyait sur le texte « Requested route
   does not exist ». C'est l'ancre retenue (convention 3) ; le corps reste au
   journal pour le lecteur.
4. **La racine du backend elle-même répond en 404 de routeur**, et pas
   seulement les chemins inventés : aucun composant n'est monté à la racine.
   Le témoin absurde reste donc indispensable, mais il confirme ici ce que la
   racine dit déjà.
5. **Quatre des cinq lacunes du plan étaient déjà comblées** avant la
   génération, par la passe de bibliothèque du matin même : lecture HTTP brute
   (`Get Http Response`), télémétrie des sondes, en-têtes surchargeables, et
   l'oracle anti-fuite qui refuse un état vide. La lacune 2 (le vocabulaire
   Gateway du préflight) n'a PAS été corrigée et n'avait pas à l'être : la
   lecture brute donne une sonde neutre, et le préflight garde son nom parce
   qu'il garde son sujet.
6. **Le piège des expressions génératrices a été re-payé** dans ce fichier même
   (`any(... for ...)` dans un `Evaluate` ne voit pas les variables Robot sous
   Python 3.12+). Il était pourtant consigné par les campagnes sœurs le jour
   d'avant. La correction est en place et commentée sur place, pour que la
   prochaine lecture du fichier porte l'avertissement.
