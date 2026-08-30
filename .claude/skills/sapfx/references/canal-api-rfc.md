# Canaux sans écran : OData, RFC/BAPI, posture de sécurité (`SapApiLibrary`)

Patron recommandé : **préparer et recouper les données par ces canaux, ne
piloter l'écran que pour ce qu'on teste**. Un fait métier vérifié par deux
canaux indépendants vaut mieux qu'une capture d'écran.

## Canal OData (v2 Gateway et v4 CAP/S4, mêmes keywords)

- **Ouverture** : `Open Api Session` par alias, quatre modes d'authentification
  (Basic, OAuth2 client credentials, mTLS, clé d'API en en-tête). Une clé vide
  est REFUSÉE à l'ouverture, sinon l'en-tête part sans authentifier et l'échec
  arrive bien plus tard en 401 muet.
- **Préflight** : `Get Gateway Status`, `Gateway Should Be Active`,
  `Wait Until Api Available`. Chaque état porte sa remédiation NOMMÉE
  (`unreachable`, `auth_failed`, `forbidden`, `catalog_not_found`,
  `gateway_inactive`, `server_error`, plus `identity_provider_redirect` et
  `login_page` pour une cible derrière un IdP).
- **Perception** : `Get Odata Metadata` (v2 ET v4, entity sets, clés,
  propriétés, libellés `sap:label`, annotations de niveau entity set),
  `Find Odata Property By Label` (le localisateur « libellé humain » côté API),
  `List Odata Services`, `Probe Odata Entity Sets` (la sonde TOLÉRANTE, qui
  consigne statut et code par entity set au lieu de s'arrêter au premier refus).
- **Lecture** : `Get Odata Entities`, `Get Odata Count`, pagination
  server-driven (`follow_next`), `Post Odata Batch` (multipart v2 et v4,
  lectures en parties indépendantes, écritures dans UN changeset atomique).
- **Écriture** : `Post/Patch/Delete Odata` avec le protocole CSRF SAP (token
  re-fetché et rejoué UNE fois sur un 403 nommant le CSRF, le timeout Gateway
  étant d'environ 30 min), `If-Match`, fabrique de données (`track=True`,
  `Ensure Odata Entity`, `Delete Created Entities` en teardown).
- **État** : `List Api Sessions` (alias, base_url, sap-client, authentifié,
  JAMAIS de credentials), `Classify Http Response` (reconnaissance tolérante :
  `unknown_route` sur l'en-tête `x-cf-routererror` d'un routeur de plateforme,
  `missing_route`, `forbidden`, `dialog`, `login_page`, `data`, `unreachable`).

Deux règles de jugement : une annotation `sap:addressable="false"` est une
DÉCLARATION à respecter (l'anomalie est l'inverse, un entity set déclaré
adressable qui ne répond pas), et une annotation PRÉSENTE n'est pas PERMISSIVE
(`sap:creatable="false"` est déclarée et interdit), donc la garde se lit par
entity set ET verbe par verbe.

## Canal RFC / BAPI (optionnel)

Optionnel par nature : `pyrfc` n'a aucune roue précompilée au-delà de Python
3.12, et le SDK NW RFC est sous licence SAP. Une suite RFC doit pouvoir se
SAUTER là où le canal n'existe pas, sans rougir.

- **Disponibilité** : `Get Rfc Channel Status`, `Rfc Channel Should Be
  Available`. Les deux causes d'indisponibilité sont distinguées parce que leur
  remède diffère : binding `pyrfc` absent contre runtime natif `sapnwrfc.dll`
  absent. Le verdict lit le CONTENU du module, pas le seul sort de l'import
  (un `import pyrfc` peut réussir en rendant un module sans `Connection`).
- **Lecture** : `Read Rfc Table` (le lecteur générique, qui construit `FIELDS`
  et `OPTIONS` pour l'appelant), `Get Rfc Connection Attributes`,
  `Call Rfc`, `Call Bapi` (jugé par TYPE de BAPIRET2, avec
  `Commit/Rollback Bapi Transaction`), `Wait For Background Job` (TBTCO).
- **Preuves d'exploitation** : `Read Change Documents` (CDHDR plus postes
  CDPOS lus en DEUX projections fusionnées), `Get Idoc Status` (barème
  explicite : un statut hors carte n'est JAMAIS un succès),
  `Read Application Log` (BALHDR, comptes par sévérité convertis des NUMC),
  `Get Job Log` (chaîne XBP avec logoff TOUJOURS exécuté).
- **Refus** : `Rfc Should Fail With Code` et `Rfc Should Fail With Message Id`.
  Un refus RFC porte un code stable ET un identifiant de message ABAP (classe,
  type, numéro), tous deux indépendants de la langue ; le texte, lui, est
  localisé. Le code est grossier, l'identifiant est fin : les deux se
  complètent.
- **Surface** : `Write Rfc Surface Artifact`, `Read Rfc Surface Artifact`,
  `Compare Rfc Surface Artifacts`, pour répondre à
  « quels modules fonction ici et pas là-bas » par une mesure comparée hors
  système. Un artefact porte l'identité de la cible ET son périmètre ; deux
  périmètres différents sont REFUSÉS comme non probants plutôt que moyennés.

Frontière Robot vers pyrfc : `pyrfc` contrôle le type EXACT d'un paramètre de
structure et REFUSE une sous-classe de `dict`, or tout dictionnaire construit
par Robot est un `DotDict`. `Call Rfc` normalise donc en types nus,
récursivement, **sans toucher aux scalaires** (convertir « 0400 » en 400
corromprait les champs caractère numériques du dictionnaire ABAP).

## Posture de configuration de sécurité (au-dessus du canal RFC)

Lecture seule de bout en bout. Vocabulaire métier dans
`resources/security_keywords.resource`, capacités dans `_rfc_security.py` et
`sapfx_common/security_baseline.py`.

- `Read Profile Parameters`, `Profile Parameters Should Be Defined` (la garde
  de tête d'une campagne), `Read Standard Users Status`,
  `Build Security Posture`, `Write Security Posture`,
  `Read Security Posture`, `Security Posture Should Not Have Drifted`.
- **Le piège central est silencieux** : `TH_GET_PARAMETER` ne REFUSE pas un
  paramètre inconnu, il rend `RC=4` et une chaîne VIDE, indiscernable d'un
  paramètre légitimement vide. Un contrôle écrit sur un nom mal orthographié
  est donc VERT et affirme un durcissement jamais mesuré, le cas le plus
  traître étant « ce paramètre doit être désactivé », que la valeur vide
  satisfait. D'où : juger sur le code de retour AVANT la valeur, garder
  `not_measurable` DISTINCT de `deviation`, et poser la garde de tête.
- **La question posée n'est pas « ce système est-il durci »** (jugement qui
  dépend d'une politique d'entreprise, faux sur un bac à sable, et une suite
  rouge en permanence finit désactivée) **mais « sa configuration a-t-elle
  bougé »**, qui a une réponse binaire : la posture est comparée à une
  référence committée par cible, première visite = référence écrite avec
  WARNING.
- Ce qui est ASSERTÉ est borné à dessein aux contrôles dont l'écart serait un
  incident quelle que soit la politique ; le reste est mesuré, rapporté et
  surveillé par la sentinelle.

## Croisement entre canaux

`sapfx_common/cross_channel.py` (importé comme bibliothèque Robot) porte la
logique pure : périmètre validé et borné, couverture du catalogue, normaliseur
d'identifiants conscient des acronymes (`ProductID` vers `PRODUCT_ID`),
rapprochement propriétés OData contre champs DD03L, artefact déterministe hashé
hors horodatage.

Trois inégalités LÉGITIMES à traiter comme telles avant de crier au défaut : un
`$count` draft-enabled agrège actives et brouillons (filtrer sur l'activité),
un service peut ne projeter qu'un sous-ensemble (filtre lu dans la colonne, pas
supposé), et certains comptes dépendent de l'utilisateur. Et les deux mandants
doivent coïncider, sinon on compare deux populations.

Pièges relevés live sur ces canaux : voir [pieges-terrain.md](pieges-terrain.md).
