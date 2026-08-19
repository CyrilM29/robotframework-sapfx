# Consultation du détail d'un voyage (Travel processor)

- **Canal** : Fiori (web)
- **Système / URL** : cible locale **cap-sflight** (`npx cds watch`, port 4004),
  `http://localhost:4004/sap.fe.cap.travel/index.html`. Application Fiori Elements
  **v4** `sap.fe.cap.travel` : List Report `TravelList` et Object Page
  `TravelObjectPage`. Runtime SAPUI5 **1.139.0** (CDN `ui5.sap.com`). Aucune
  authentification.
- **Préconditions** :
  - `cds watch` démarré et le service OData v4 servi. Au premier chargement live,
    le bootstrap a échoué sur `Component.js` (`net::ERR_CONNECTION_REFUSED`) alors
    que `index.html` avait déjà été servi : l'application restait à 1 seul contrôle
    UI5 (`ComponentContainer` seul dans l'arbre). Un rechargement a suffi, voir
    « Points de vigilance ». Ce plan suppose une application saine, chargée avec
    ses données.
  - Jeu de démonstration cap-sflight standard chargé (4 133 voyages observés, le
    voyage d'ID 4 133 en tête de liste comporte 2 réservations).
  - Aucun réglage persistant requis : vue standard livrée, sans filtre
    pré-positionné.
- **Périmètre** : **consultation stricte**. Aucun scénario ne déclenche les
  actions métier `acceptTravel`, `rejectTravel`, `deductDiscount`, ni la création,
  l'édition ou la suppression. Seules la navigation et la lecture sont exercées.

Ce plan est le pendant « détail » du plan de consultation de la liste
(`travel-processor-consultation-liste.md`) : il part de la liste, ouvre la page
objet d'un voyage, puis lit son en-tête et ses postes de réservation.

## Données observées

Relevé live le 2026-08-15, exploration pilotée par rf-mcp (Browser +
SapFioriLibrary), locale du navigateur en français.

### Navigation liste vers page objet

- Un clic sur la première ligne de la table de la liste (contrôle
  `sap.m.ColumnListItem`) ouvre l'Object Page. L'URL passe de
  `.../index.html` à `.../index.html#/Travel(4133)` : le hash de route porte
  la **clé technique** du voyage (`Travel(<ID>)`), locale-indépendante.
- L'application est une SPA à colonne flexible : après ouverture, le List Report
  reste instancié en arrière-plan (préfixe `sap.fe.cap.travel::TravelList--`) et
  l'Object Page ajoute ses propres contrôles (préfixe
  `sap.fe.cap.travel::TravelObjectPage--`). Le retour navigateur (`Go Back`)
  ramène à l'URL de la liste sans hash et la liste reste fonctionnelle
  (compteur `Voyages (4 133)` relu après retour).
- La page objet du voyage 4 133 (première ligne) a rendu un
  `sap.uxap.ObjectPageLayout` (1 occurrence) et l'ancre FE `fe::ObjectPage`
  (1 occurrence).

### En-tête de l'Object Page (voyage 4 133 observé)

Vue sémantique (ARIA) et lecture par ancre FE :

- Titre de l'en-tête (heading niveau 2) : « Sightseeing in New York City,
  New York » ; l'ID 4 133 est rendu à côté.
- Barre d'onglets de l'Object Page : « Informations générales » (sélectionné) et
  « My Itinerary » (libellés localisés).
- Section « Informations générales » : formulaire groupé en conteneurs (les noms
  de conteneurs et de champs sont **techniques**, indépendants de la locale) :
  - `TravelData` : `TravelID`, `to_Agency_AgencyID`, `to_Customer_CustomerID`,
    `Description`, `TravelStatus_code`.
  - `PriceData` : `BookingFee`, `TotalPrice`, `CurrencyCode_code`.
  - `DateData` : `BeginDate`, `EndDate`.
  - `i18nSustainability` : `GoGreen`, `GreenFee`, `TreesPlanted`.
- Valeurs lues live (voyage 4 133) : agence « Aussie Travel (070028) », client
  « Benz (000115) », prix total « 7 375,00 USD », frais de réservation
  « 20,00 USD », devise « USD », dates « 11 déc. 2025 », statut « Acceptée ».
- Ces valeurs correspondent exactement à la ligne de tête de la liste (même
  agence, même client, mêmes dates) : la cohérence liste vers page objet est
  une assertion locale-indépendante utile (comparaison de deux lectures du même
  run, jamais une constante en dur).

### Postes de réservation (bookings) sur l'Object Page

- Les bookings sont rendus dans une **sous-section personnalisée** (onglet
  « My Itinerary »), pas une table de macro FE standard : ancre
  `fe::CustomSubSection::CustomSection--bookingTable`. C'est une annotation
  `CustomSection` propre à cette application cap-sflight ; l'ancre n'est donc pas
  `fe::table::_Booking::LineItem` (testé live : 0 occurrence).
- Compteur d'en-tête de la table des bookings (contrôle titre) : texte
  « Réservations (2) » sur le voyage 4 133.
- Table interne des bookings : `sap.m.Table`, 2 lignes lues. Colonnes rendues
  (libellés localisés) : ID réservation, Date d'inscription, Client, Airline,
  Nº vol, Date vol, Flight Price, Booking Status. Données :
  - booking 1 : ID « 1 », client « Benz (000115) », compagnie
    « Green Albatros (GA) », vol « 0018 ».
  - booking 2 : ID « 2 », client « Detemple (000096) », compagnie
    « Fly Africa (FA) », vol « 0018 ».

### Ids stables Fiori Elements réellement observés

Préfixe applicatif à ne jamais coder en dur (`sap.fe.cap.travel::TravelList--`
pour la liste, `sap.fe.cap.travel::TravelObjectPage--` pour la page objet) :
c'est le **suffixe** `fe::…` qui est déterministe.

| Rôle fonctionnel | idSuffix (ancre primaire) | controlType observé |
|---|---|---|
| Ligne de la liste (ouvre la page objet) | ligne = `sap.m.ColumnListItem` (index) sous `fe::table::Travel::LineItem-innerTable` | `sap.m.ColumnListItem` |
| Table interne de la liste | `fe::table::Travel::LineItem-innerTable` | `sap.m.Table` |
| Object Page (layout) | `fe::ObjectPage` | `sap.uxap.ObjectPageLayout` |
| Titre dynamique d'en-tête | `fe::ObjectPageDynamicHeaderTitle` | (DynamicPageTitle FE) |
| Champ en-tête : ID/titre du voyage | `fe::FormContainer::TravelData::FormElement::DataField::TravelID` | DataField FE |
| Champ en-tête : agence | `fe::FormContainer::TravelData::FormElement::DataField::to_Agency_AgencyID` | DataField FE |
| Champ en-tête : client | `fe::FormContainer::TravelData::FormElement::DataField::to_Customer_CustomerID` | DataField FE |
| Champ en-tête : statut | `fe::FormContainer::TravelData::FormElement::DataField::TravelStatus_code` | DataField FE |
| Champ en-tête : prix total | `fe::FormContainer::PriceData::FormElement::DataField::TotalPrice` | DataField FE |
| Champ en-tête : frais de réservation | `fe::FormContainer::PriceData::FormElement::DataField::BookingFee` | DataField FE |
| Champ en-tête : date de début | `fe::FormContainer::DateData::FormElement::DataField::BeginDate` | DataField FE |
| Compteur d'en-tête des bookings | `fe::CustomSubSection::CustomSection--bookingTable-content-title` | `sap.m.Title` |
| Table interne des bookings | `fe::CustomSubSection::CustomSection--bookingTable-content-innerTable` | `sap.m.Table` |

- **Lecture d'une valeur de champ d'en-tête** : `Get Ui5 Text` sur le suffixe du
  DataField retourne `libellé localisé` + saut de ligne + valeur (ex.
  « Prix total\n7 375,00 USD »). Le suffixe enfant `…::Field-display` retourne la
  **valeur seule** (ex. « 7 375,00 USD », « Sightseeing in New York City,
  New York (4 133) ») : c'est l'ancre à privilégier pour une assertion sur la
  valeur, sans le libellé localisé qui la précède.
- `Get Page Composition` : `ui5_runtime=True`, `ui5_version=1.139.0`,
  `wc_hosts=0`, `webgui_elements=0`, `frames=[]`. Page mono-technologie, moteur
  `role` (résolution par idSuffix) suffisant, aucune frame à empiler.

## Scénarios

### 1. Ouvrir la page objet d'un voyage depuis la liste
- **Étapes** :
  1. Ouvrir l'application et attendre que la liste porte des données (Suite Setup :
     ouverture + attente d'au moins une ligne instanciée).
  2. Relever l'ID technique du voyage de la première ligne (extrait du hash de
     route après ouverture, ou lu dans la ligne).
  3. Ouvrir la page objet en activant la première ligne de la liste.
  4. Attendre le repos réel du runtime UI5.
  5. Vérifier que l'Object Page est rendue.
- **Résultat attendu** : après activation de la ligne, l'URL contient le hash
  `#/Travel(<ID>)` (assertion sur la présence du motif `Travel(` et d'un ID
  numérique, jamais sur un libellé), et l'ancre `fe::ObjectPage` est présente
  (1 occurrence). Aucune boîte de dialogue ni message d'erreur.
- **Keywords métier manquants** :
  - `Open First Travel Object Page` : active la première ligne de la table de la
    liste et attend le rendu de l'Object Page (arme la promesse sur la réponse
    OData `$batch` avant le clic, voir points de vigilance, puis `Wait For UI5
    Ready`). Retourne l'ID de voyage extrait du hash de route.
  - `Travel Object Page Should Be Displayed` : vérifie la présence de l'ancre
    `idSuffix=fe::ObjectPage` (attend le rendu, jamais une attente fixe).

### 2. Lire les données d'en-tête du voyage sur la page objet
- **Étapes** :
  1. Depuis la page objet ouverte au scénario 1, lire les champs d'en-tête :
     agence, client, statut, prix total, frais de réservation, dates.
- **Résultat attendu** :
  - chaque champ d'en-tête lu (via son ancre `…::Field-display`) est non vide ;
  - les valeurs d'agence, de client et de dates coïncident avec celles de la
    ligne d'origine dans la liste (comparaison de deux lectures du **même run**,
    l'assertion ne code aucune valeur en dur) ;
  - l'assertion ne porte jamais sur les libellés localisés (« Agence »,
    « Prix total »…) ni sur le format des nombres (séparateur de milliers U+202F
    en locale FR, virgule décimale).
- **Keywords métier manquants** :
  - `Read Travel Header Field` (`${field}`) : lit la valeur seule d'un champ
    d'en-tête de l'Object Page à partir de son nom technique de DataField
    (`to_Agency_AgencyID`, `to_Customer_CustomerID`, `TotalPrice`, `BookingFee`,
    `BeginDate`, `EndDate`, `TravelStatus_code`…), via l'ancre
    `fe::FormContainer::…::FormElement::DataField::<field>::Field-display`.
    Retourne le texte de la valeur, sans le libellé qui précède.

### 3. Lire les postes de réservation du voyage sur la page objet
- **Étapes** :
  1. Depuis la page objet, lire le compteur d'en-tête de la table des bookings.
  2. Lire les lignes de la table des bookings.
- **Résultat attendu** :
  - le compteur des bookings retourne un entier (2 observé sur le voyage 4 133) ;
  - le nombre de lignes lues dans la table des bookings est égal à la valeur du
    compteur (cohérence interne, assertion locale-indépendante) ;
  - chaque ligne porte un ID de réservation non vide et une compagnie renseignée
    (assertion sur la présence de données, pas sur un libellé de colonne, les
    en-têtes étant localisés : « ID réservation », « Airline »…).
- **Keywords métier manquants** :
  - `Get Travel Bookings Count` : lit le titre de la table des bookings
    (ancre `fe::CustomSubSection::CustomSection--bookingTable-content-title`),
    ne conserve que les chiffres et retourne un entier ; retourne `0` si aucun
    nombre n'est présent (même contrat que `Get Travel Count` côté liste, cas
    « aucune réservation »).
  - `Read Travel Bookings` : lit la table interne des bookings
    (ancre `fe::CustomSubSection::CustomSection--bookingTable-content-innerTable`)
    et retourne la liste des lignes instanciées (miroir de `Read Ui5 Table`).

## Points de vigilance

- **La table des bookings est une sous-section personnalisée, pas une macro FE
  standard.** Son ancre est `fe::CustomSubSection::CustomSection--bookingTable`
  (annotation `CustomSection` de cette app), et non
  `fe::table::_Booking::LineItem` : ce dernier n'existe pas ici (0 occurrence
  live). Le suffixe a été relevé dans le registre live, jamais déduit d'une
  convention de nommage (leçon du heal-journal du 2026-07-25 : un suffixe FE se
  constate sur l'écran réel).
- **Le préfixe applicatif diffère entre liste et page objet.**
  `sap.fe.cap.travel::TravelList--` pour la List Report,
  `sap.fe.cap.travel::TravelObjectPage--` pour l'Object Page. Ne jamais coder ces
  préfixes en dur : seul le suffixe `fe::…` est stable et c'est lui que résolvent
  les keywords (`idSuffix=`).
- **Lire la valeur d'un champ, pas son libellé.** `Get Ui5 Text` sur un DataField
  d'en-tête renvoie « libellé localisé\nvaleur ». Pour une assertion
  locale-indépendante, viser le suffixe enfant `…::Field-display` (valeur seule)
  ou couper sur le saut de ligne. Ne jamais asserter le libellé (« Agence »,
  « Prix total »…) ni le format numérique (U+202F, virgule décimale FR).
- **Course de chargement des données après navigation.** Le service OData v4
  groupe ses requêtes en `POST …/$batch`. Comme pour la recherche côté liste
  (écarts du plan liste), « attendre le retour du runtime UI5 » ne suffit pas
  toujours après le clic d'ouverture : armer une promesse sur la réponse `$batch`
  **avant** le clic, puis `Wait For UI5 Ready` pour le rendu. Ne jamais employer
  d'attente fixe (convention #2).
- **Le bootstrap peut échouer si `cds watch` redémarre à chaud.** Symptôme
  observé live : `Component.js` en `net::ERR_CONNECTION_REFUSED`, application à
  1 seul contrôle UI5, table absente. `Get Fiori Diagnostics` nomme la cause en
  une lecture (« 5 erreur(s) console, première : Failed to load resource:
  net::ERR_CONNECTION_REFUSED ») ; un rechargement de la page a suffi. Prévoir ce
  diagnostic en teardown d'échec et ne pas confondre ce symptôme avec une dérive
  de localisateur.
- **Le nombre de lignes rendues dans la liste (30) est le seuil de croissance**,
  pas une volumétrie : la navigation part de la première ligne rendue, ce qui est
  toujours suffisant. Pour les bookings, la table est courte (2 lignes) et
  entièrement instanciée : `Read Ui5 Table` les lit toutes.
- **Périmètre volontairement non destructif.** L'en-tête de l'Object Page expose
  les boutons « Modifier », « Supprimer », « Accepter le voyage »,
  « Refuser le voyage », « Déduire remise » et « Partager » (les deux premiers
  d'action métier étant partiellement désactivés selon le statut du voyage) ;
  aucun scénario de ce plan ne les active. La consultation se limite à la
  navigation et à la lecture.
