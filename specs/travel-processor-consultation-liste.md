# Consultation de la liste des voyages (Travel processor)

- **Canal** : Fiori (web)
- **Système / URL** : cible locale **cap-sflight** (`npx cds watch`, port 4004) —
  `http://localhost:4004/sap.fe.cap.travel/index.html`. Application Fiori Elements
  **List Report v4** `sap.fe.cap.travel`, vue `TravelList`. Runtime SAPUI5
  **1.139.0** (CDN `ui5.sap.com`). Aucune authentification.
- **Préconditions** :
  - `cds watch` démarré et le service OData v4 servi (au premier chargement live,
    un redémarrage du serveur en cours de bootstrap a fait échouer le
    chargement de `Component.js` — voir « Points de vigilance »).
  - Jeu de démonstration cap-sflight standard chargé (4 133 voyages observés).
  - Aucun réglage persistant requis : la **vue variante** utilisée est la vue
    standard livrée (`fe::PageVariantManagement`), sans filtre pré-positionné.

## Données observées

Relevé live le 2026-07-25, exploration pilotée par rf-mcp (Browser + SapFioriLibrary).

**Volumétrie et comportement du compteur d'en-tête** (titre de la table,
contrôle `sap.m.Title`) :

| État | Texte du titre observé | Lignes instanciées |
|---|---|---|
| Liste non filtrée | `Voyages (4 133)` | 30 |
| Recherche « Aussie » | `Voyages (91)` | 30 |
| Recherche « ZZQQXX » (sans résultat) | `Voyages` — **aucune parenthèse, aucun nombre** | 0 |
| Après vidage + Go | `Voyages (4 133)` | 30 |

- Le cycle **4 133 → 91 → 4 133** a été exécuté de bout en bout ; l'état
  non filtré est intégralement restauré en vidant la zone de recherche puis en
  déclenchant « Go ».
- Sur la recherche « Aussie », les **30 lignes rendues contiennent toutes** le
  terme (agence « Aussie Travel (070028) ») — filtrage effectif, pas un simple
  surlignage.
- Le nombre 30 est le **seuil de croissance (growing)** de la table, pas un
  volume métier : il vaut 30 aussi bien sur 4 133 que sur 91 résultats. Seul le
  compteur d'en-tête porte la volumétrie réelle.
- Le séparateur de milliers rendu est **U+202F** (espace fine insécable, locale
  FR) : `4 133`. Une conversion entière directe échoue — il faut ne garder
  que les chiffres (même précaution que `Count Table Entries` côté SE16).
- Colonnes rendues (libellés **localisés**, ici en français) : Voyage, Agence,
  Client, Date de début, Date de fin, Frais de réservation, Prix total, Statut
  du voyage. Exemple de première ligne non filtrée :
  `Sightseeing in New York City, New York` / `Aussie Travel (070028)` /
  `Benz (000115)` / `11 déc. 2025`.

**Ids stables Fiori Elements et types de contrôles réellement observés**
(préfixe applicatif `sap.fe.cap.travel::TravelList--`, à ne jamais coder en
dur : c'est le **suffixe** qui est déterministe) :

| Rôle fonctionnel | idSuffix (ancre primaire) | controlType observé | Moteur |
|---|---|---|---|
| Page du List Report | `fe::ListReport` | `sap.f.DynamicPage` | role |
| Barre de filtres | `fe::FilterBar::Travel` | `sap.fe.macros.controls.FilterBar` | role |
| Zone de recherche libre | `fe::FilterBar::Travel::BasicSearchField` | `sap.ui.mdc.FilterField` | role |
| Bouton « Go » (lancer la recherche) | `fe::FilterBar::Travel-btnSearch` | `sap.m.Button` | role |
| Bouton « Adapter les filtres » | `fe::FilterBar::Travel-btnAdapt` | `sap.m.Button` | role |
| Table (macro FE) | `fe::table::Travel::LineItem` | `sap.ui.mdc.Table` | role |
| Table interne (lignes) | `fe::table::Travel::LineItem-innerTable` | `sap.m.Table` | role |
| **Compteur d'en-tête** | `fe::table::Travel::LineItem-title` | `sap.m.Title` | role |
| Barre d'outils de la table | `fe::table::Travel::LineItem-toolbar` | (toolbar FE) | role |

- Un bouton `fe::FilterBar::Travel-btnClear` existe mais est rendu **invisible**
  dans cette variante (`sap-ui-invisible-…`) : le retour à l'état non filtré
  passe par « vider la zone de recherche + Go », pas par ce bouton.
- Les lignes de la table sont des `sap.m.ColumnListItem` : leur comptage
  (`Get Ui5 Match Count`) est une assertion **locale-indépendante** utile pour
  distinguer « au moins une ligne » de « aucune ligne ».
- `Get Page Composition` : `ui5_runtime=True`, `ui5_version=1.139.0`,
  `wc_hosts=0`, `webgui_elements=0`, `frames=[]`, moteurs recommandés
  `['role', 'xpath', 'dom']`. Page **mono-technologie** : le moteur `role` suffit,
  aucune frame à empiler.
- Xpath UI5 les plus courts calculés live (repli **faible**, purement
  positionnel — à ne considérer qu'en second rang d'une chaîne de fallback) :
  table interne `//Table[1]/Table[1]`, compteur `//ActionToolbar[1]/Title[1]`,
  zone de recherche `//FilterItemLayout[1]/FilterField[1]`, bouton Go
  `//VerticalLayout[1]/HorizontalLayout[1]/Button[1]`.

## Scénarios

### 1. La liste des voyages se charge et affiche des lignes
- **Étapes** :
  1. `Open Fiori Launchpad` sur l'URL de l'application (Suite Setup).
  2. `Wait For UI5 Ready`.
  3. Vérifier que la table des voyages est rendue.
  4. Compter les lignes rendues.
- **Résultat attendu** : la table des voyages est visible et le nombre de lignes
  rendues est strictement positif (30 observé — seuil de croissance, ne jamais
  asserter la valeur exacte). Aucune assertion sur un libellé de colonne
  (localisés : « Voyage », « Agence »… en français, « Travel », « Agency »… en
  anglais).
- **Keywords métier manquants** :
  - `Travel List Should Be Displayed` — attend et vérifie le rendu de la table
    du List Report Travel (ancre `idSuffix=fe::table::Travel::LineItem-innerTable`).
  - `Count Displayed Travel Rows` — retourne le nombre de lignes actuellement
    instanciées (`sap.m.ColumnListItem`), pour distinguer « au moins une ligne »
    de « aucune ligne ».

### 2. Le compteur d'en-tête reflète la volumétrie totale
- **Étapes** :
  1. Lire le compteur d'en-tête de la liste des voyages.
- **Résultat attendu** : le compteur retourne un entier strictement positif
  (4 133 sur le jeu de démonstration observé). L'assertion porte sur la **valeur
  numérique extraite**, jamais sur le libellé qui la précède (« Voyages » en FR,
  « Travels » en EN) ni sur le format du nombre (séparateur U+202F en FR).
- **Keywords métier manquants** :
  - `Get Travel Count` — lit le titre de la table, ne conserve que les chiffres
    et retourne un entier ; retourne `0` quand aucun nombre n'est présent
    (cas « aucun résultat », voir scénario 4).

### 3. La recherche libre filtre la liste
- **Étapes** :
  1. Rechercher le terme `Aussie` dans la barre de filtres, puis déclencher la
     recherche.
  2. Lire le compteur d'en-tête.
  3. Lire les lignes affichées.
- **Résultat attendu** :
  - le compteur filtré est strictement inférieur au compteur non filtré et
    strictement positif (91 observé) ;
  - toutes les lignes rendues contiennent le terme recherché (30/30 observé) ;
  - aucune boîte de dialogue ni message d'erreur n'apparaît.
- **Keywords métier manquants** :
  - `Search Travels` (`${term}`) — saisit le terme dans la zone de recherche
    libre de la barre de filtres puis déclenche « Go » et attend le retour du
    runtime UI5 (jamais d'attente fixe). Le clic sur « Go » est la voie
    déterministe ; la validation par Entrée dépend de l'état du champ.
  - `Displayed Travel Rows Should All Contain` (`${term}`) — vérifie que chaque
    ligne rendue contient le terme (assertion sur le contenu de données, pas sur
    un libellé d'interface).

### 4. Le retour à l'état non filtré restaure la liste complète
- **Étapes** :
  1. Depuis l'état filtré du scénario 3, vider la zone de recherche libre et
     relancer la recherche.
  2. Lire le compteur d'en-tête.
- **Résultat attendu** : le compteur retrouve exactement la valeur relevée avant
  filtrage (4 133 → 91 → 4 133 observé) et la table réaffiche des lignes.
  L'assertion compare **deux mesures prises dans le même run** — jamais une
  constante en dur, la volumétrie du jeu de démonstration pouvant évoluer.
- **Keywords métier manquants** :
  - `Clear Travel Search` — vide la zone de recherche libre et relance la
    recherche (le bouton de réinitialisation `btnClear` de la barre de filtres
    est invisible dans cette variante : ne pas s'appuyer dessus).

## Points de vigilance

- **Libellés et formats suivent la locale du navigateur.** Le run live a rendu
  l'application en français (compteur « Voyages (4 133) », colonnes « Agence »,
  « Client »…) parce que Chromium hérite de la locale du poste. Toute assertion
  doit porter sur des **nombres extraits** ou sur des **ids techniques**, jamais
  sur ces textes. Corollaire : `Read Ui5 Table` retourne des dictionnaires dont
  les clés sont les en-têtes **localisés** — ne pas indexer dessus dans une
  assertion, ou forcer explicitement la langue de l'application.
- **Zéro résultat = compteur sans nombre.** Le titre devient `Voyages` tout court
  (pas de `(0)`) : un keyword de lecture du compteur doit retourner `0` dans ce
  cas plutôt que d'échouer sur l'absence de chiffres.
- **Séparateur de milliers U+202F** (espace fine insécable) en locale FR :
  filtrer les non-chiffres caractère par caractère. Attention à l'échappement
  Robot : proscrire un motif regex à backslash (`\D`), défiguré silencieusement
  par le parseur — utiliser `c.isdigit()` (leçon verrouillée par
  `tests/unit/test_se16_exploration_logic.py`).
- **Le nombre de lignes rendues (30) est le seuil de croissance de la table**,
  pas une volumétrie : ne jamais asserter 30, ni déduire un total d'un comptage
  de lignes. Le compteur d'en-tête est la seule source de volumétrie.
- **`BasicSearchField` est un `sap.ui.mdc.FilterField` composite** : la saisie
  doit viser le champ interne (`Fill Ui5 Input` le fait déjà — le recorder web
  avait relevé le DOM `…BasicSearchField-inner`). Ne pas écrire dans la racine
  du contrôle.
- **Les xpath UI5 les plus courts sont ici tous positionnels**
  (`//ActionToolbar[1]/Title[1]`, `//FilterItemLayout[1]/FilterField[1]`…) :
  ils dérivent au moindre ajout de champ de filtre ou d'action de toolbar.
  L'ancre primaire est **l'idSuffix Fiori Elements**, le xpath ne vaut que comme
  repli d'une chaîne `Resolve Ui5 With Fallback`.
- **Le préfixe applicatif `sap.fe.cap.travel::TravelList--` ne doit pas être
  codé en dur** : il porte le nom du composant et de la route. Seul le suffixe
  `fe::…` est stable d'une version à l'autre.
- **`cds watch` redémarre à chaud.** Lors du premier chargement live, le
  bootstrap a échoué sur `Component.js` (`net::ERR_CONNECTION_REFUSED`) alors
  que `index.html` avait déjà été servi — l'application restait à 1 seul
  contrôle UI5. `Get Fiori Diagnostics` a nommé la cause en une lecture
  (5 erreurs console, la première citée) ; un rechargement a suffi. Prévoir ce
  diagnostic en teardown d'échec et ne pas confondre ce symptôme avec une
  dérive de localisateur.
- **Périmètre volontairement non destructif** : la liste comporte des actions
  `acceptTravel`, `rejectTravel`, `deductDiscount` et un bouton de création —
  aucun scénario de ce plan ne les déclenche.

## Écarts constatés à la génération

Relevés le 2026-07-25 par sap-generator, en rejouant chaque étape en live
(rf-mcp : Browser + SapFioriLibrary) avant de l'écrire. Suite produite :
`tests/robot/ui/fiori/travel_processor_consultation_liste.robot` ;
localisateurs et mots-clés d'écran dans
`resources/page_objects/fiori_travel_list.resource`.

1. **« Attendre le retour du runtime UI5 » ne suffit pas après « Go »** (le plan
   le prescrit pour `Search Travels`). Mesuré : juste après le clic sur « Go »
   d'une recherche filtrant à 91, le compteur lisait encore `4 133` — la course
   est reproductible, elle a fait échouer une assertion immédiate. Second essai,
   `Wait For Load State networkidle` : rend la main en 4 ms, l'état réseau étant
   *déjà* idle au moment du clic (la requête n'était pas encore partie) — donc
   inopérant lui aussi. Cause : le service OData v4 **groupe ses requêtes en
   `POST …/processor/$batch`**. La suite arme donc, **avant le clic**, une
   promesse sur cette réponse (`Promise To    Wait For Response`), puis
   `Wait For UI5 Ready` pour le rendu. Validé deux cycles consécutifs avec
   assertion immédiate (91 puis 4 133), plus un cycle « même terme recherché
   deux fois » : un « Go » redéclenche toujours une requête, la promesse ne
   reste donc jamais pendante.
2. **Même course au chargement initial, non prévue par le plan.** Après
   `Open Fiori Launchpad` (dont la dernière étape est `Wait For UI5 Ready`), la
   table est bien rendue mais **0 ligne** est instanciée : le premier run live de
   la suite a échoué sur le scénario 1 (`3/4`). Aucune promesse ne peut être
   armée ici — la requête est déjà en vol quand le test prend la main. La suite
   ouvre donc l'application par `Open Travel Processor` (Suite Setup), qui sonde
   jusqu'à ce que la table porte au moins une ligne (`Wait For Travel List
   Data`, prédicat lu au niveau UI5 `getItems()`, jamais une classe CSS de
   rendu). Run live suivant : 4/4.
3. **Scénario 4 rendu autonome.** Le plan l'enchaîne sur l'état filtré laissé
   par le scénario 3 ; le test correspondant rejoue le cycle complet
   (non filtré → filtré → non filtré) dans son propre corps, avec retour à
   l'état non filtré en `[Setup]`. Le contrat d'assertion du plan est respecté —
   la référence reste une mesure prise dans le **même run**, jamais une
   constante — et le test reste vrai exécuté seul (`--test`).
4. **Bruit console bénin à ne pas confondre avec un bootstrap cassé.** Sur
   l'application saine, `Get Fiori Diagnostics` remonte 8 erreurs console, dont
   `TypeError: i.storeInnerAppStateAsync is not a function` (gestion de
   l'app-state Fiori Elements hors launchpad). Aucun effet sur les scénarios :
   le symptôme décrit dans les points de vigilance (`Component.js` en
   `ERR_CONNECTION_REFUSED`, application quasi vide) reste, lui, bloquant.
5. **Conforme au plan, revérifié live** : compteur `4 133 → 91 → 4 133`,
   30 lignes rendues dans les deux états, 30/30 lignes filtrées contenant
   « Aussie », aucun dialogue ouvert, cas « aucun résultat » (`ZZQQXX`) rendant
   le titre `Voyages` sans nombre — d'où le contrat « `Get Travel Count`
   retourne 0 ».
