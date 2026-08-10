# Plan de test ISTQB : Recherche de voyages filtrée (Travel processor, cap-sflight)

> Sources : enregistrement live du recorder web du 2026-08-05
> (`tools/recorder_web/captures/recorded_capsflight_20260805.robot` et son
> brouillon `recorded_capsflight_20260805.istqb.md` ; constaté en session :
> liste initiale « Travels (4,133) », recherche « Aussie » + Go →
> « Travels (91) », assertion de présence du bouton Go posée à chaud) ; plan
> planner `specs/travel-processor-consultation-liste.md` (relevé live du
> 2026-07-25 : cycle 4 133 → 91 → 4 133, ids Fiori Elements stables, écarts de
> génération) ; suite générée
> `tests/robot/ui/fiori/travel_processor_consultation_liste.robot`.
> Document de conception de test (ISTQB / ISO 29119-3) : lisible par un
> humain, rejouable par une IA via le bloc `replay` de chaque cas de test,
> indépendant du framework d'exécution.

- **Identifiant** : TP-recherche-voyages-capsflight
- **Canal** : Fiori (web)
- **Système / URL** : cible locale cap-sflight (`npx cds watch`, port 4004),
  `http://localhost:4004/sap.fe.cap.travel/index.html`, application Fiori
  Elements List Report v4 `sap.fe.cap.travel` (vue `TravelList`),
  authentification simulée cds (utilisateur `alice`). Runtime SAPUI5 1.139.0
  relevé au plan du 2026-07-25.
- **Références** :
  `tools/recorder_web/captures/recorded_capsflight_20260805.robot`
  (suite exportée de l'enregistrement),
  `tools/recorder_web/captures/recorded_capsflight_20260805.istqb.md`
  (brouillon recorder), `specs/travel-processor-consultation-liste.md`
  (plan planner, source des données observées et des vigilances),
  `tests/robot/ui/fiori/travel_processor_consultation_liste.robot` (suite
  générée du plan, marqueur `Spec:` daté 2026-08-04),
  `resources/page_objects/fiori_travel_list.resource` (localisateurs et
  keywords d'écran), `tests/robot/fiori_sflight_smoke.robot` (smoke de
  chargement sans recherche).

## 1. Objectif et périmètre

- **Objectif** : vérifier que la recherche libre de la barre de filtres de la
  List Report « Travel processor » filtre réellement la liste des voyages :
  saisie d'un terme dans la zone de recherche (`BasicSearchField`),
  déclenchement par le bouton « Go », réduction de la volumétrie affichée par
  le compteur d'en-tête (4 133 voyages avant filtrage, 91 après le terme
  « Aussie », observé le 2026-07-25 et re-constaté le 2026-08-05).
- **Éléments à tester** : ouverture de l'application, focalisation et saisie
  dans la zone de recherche libre (contrôle composite `sap.ui.mdc.FilterField`
  : la saisie vise le champ interne `-inner`), présence du bouton « Go »
  (assertion posée à chaud pendant l'enregistrement), déclenchement de la
  recherche par « Go » (voie déterministe, la validation par Entrée dépendant
  de l'état du champ).
- **Hors périmètre** : lecture détaillée du compteur d'en-tête et du contenu
  des lignes (couverts par les scénarios 2 et 3 du plan planner et la suite
  générée), retour à l'état non filtré (scénario 4 du plan), cas « aucun
  résultat », et toute action métier (`acceptTravel`, `rejectTravel`,
  `deductDiscount`, création) : périmètre volontairement non destructif,
  consultation seule.

## 2. Préconditions et données de test

- `cds watch` démarré dans `_cap-sflight/` et le service OData v4 servi sur
  le port 4004 ; bootstrap de l'application complet (un redémarrage à chaud de
  `cds watch` pendant le chargement fait échouer `Component.js`, voir
  risques).
- Authentification simulée cds : utilisateur `alice` (mocked auth, aucun IDP).
- Jeu de démonstration cap-sflight standard chargé : 4 133 voyages observés
  (2026-07-25 et 2026-08-05). Cette volumétrie peut évoluer avec le jeu de
  démonstration : les assertions industrialisées sont relationnelles
  (filtré < total), jamais des constantes.
- Vue variante standard de la List Report, sans filtre pré-positionné (aucun
  réglage persistant requis).
- Terme de recherche observé : `Aussie` (agence « Aussie Travel (070028) » du
  jeu de démonstration) ; résultat filtré observé : 91 voyages.
- Navigateur Chromium disponible (Playwright initialisé).

## 3. Critères d'entrée / de sortie

- **Entrée** :
  - l'URL de l'application répond et l'application UI5 est réellement
    rendue (barre de filtres présente ; en cas de page quasi vide, consulter
    le diagnostic Fiori avant de conclure à une dérive de localisateur) ;
  - la liste initiale porte des données (compteur d'en-tête strictement
    positif) : sans données, le filtrage n'est pas démontrable.
- **Sortie** :
  - TC-01 exécuté de bout en bout : saisie acceptée, bouton « Go » présent et
    cliqué, liste filtrée (compteur réduit et strictement positif), aucune
    boîte de dialogue ni message d'erreur ;
  - écarts documentés le cas échéant (dérive de localisateur consignée par la
    chaîne de fallback, changement de volumétrie du jeu de démonstration).

## 4. Cas de test

### TC-01 : Recherche de voyages filtrée

- **Priorité** : Haute. La recherche libre est le geste central de la List
  Report (scénario 3 du plan planner, le seul geste actif de ce parcours de
  consultation) ; le comportement a été constaté deux fois en live
  (2026-07-25 et 2026-08-05) et la suite générée du plan en dépend.

| # | Action | Données | Résultat attendu |
|---|--------|---------|------------------|
| 1 | Cliquer la zone de recherche libre de la barre de filtres (`BasicSearchField`) | | Le champ prend le focus, aucune erreur |
| 2 | Vérifier la présence du bouton « Go » de la barre de filtres | | Le bouton est présent (assertion posée à chaud pendant l'enregistrement) |
| 3 | Saisir le terme de recherche dans la zone de recherche libre | `Aussie` | La valeur est acceptée dans le champ interne du contrôle composite |
| 4 | Cliquer le bouton « Go » | | La liste se filtre : le compteur d'en-tête passe d'une valeur initiale (4 133 observé) à une valeur strictement inférieure et positive (91 observé) ; aucune boîte de dialogue ni message d'erreur. Assertion sur les nombres extraits, jamais sur le texte localisé du titre |

- **Postconditions** : la liste est laissée **filtrée** sur « Aussie »
  (l'enregistrement ne restaure pas l'état initial). Restauration : vider la
  zone de recherche puis « Go » (le bouton `btnClear` de la barre de filtres
  est invisible dans cette variante, ne pas s'appuyer dessus), ou recharger
  l'application. Aucune donnée modifiée.

Bloc rejouable (actions normalisées ; les `hint` sont les localisateurs
relevés au moment de l'enregistrement) :

```yaml
test_case: TC-01
title: 'Recherche de voyages filtrée'
channel: web
steps:
  - action: click
    target: 'fe_filterbar_travel_basicsea'
    hint: {engine: 'ui5-role', locator: 'idSuffix=fe::FilterBar::Travel::BasicSearchField-inner'}
    fallback: {engine: 'ui5-xpath', locator: '//SearchField[1]'}
  - action: assert_present
    target: 'fe_filterbar_travel_btnsearc'
    hint: {engine: 'ui5-role', locator: 'idSuffix=fe::FilterBar::Travel-btnSearch'}
  - action: fill
    target: 'champ fe_filterbar_travel_basicsea'
    value: 'Aussie'
    hint: {engine: 'ui5-role', locator: 'idSuffix=fe::FilterBar::Travel::BasicSearchField-inner'}
    fallback: {engine: 'ui5-xpath', locator: '//SearchField[1]'}
  - action: click
    target: 'fe_filterbar_travel_btnsearc'
    hint: {engine: 'ui5-role', locator: 'idSuffix=fe::FilterBar::Travel-btnSearch'}
    fallback: {engine: 'ui5-xpath', locator: '//VerticalLayout[1]/HorizontalLayout[1]/Button[1]'}
```

## 5. Traçabilité

| Cas de test | Source | Exigence / spec | Suite exécutable |
|---|---|---|---|
| TC-01 | `recorded_capsflight_20260805.robot`, étapes 1 à 4 (enregistrement live 2026-08-05) | `specs/travel-processor-consultation-liste.md`, scénario 3 « La recherche libre filtre la liste » (relevé live 2026-07-25) | `tests/robot/ui/fiori/travel_processor_consultation_liste.robot` (générée du plan, marqueur `Spec:` sha256:495673b5cbaf du 2026-08-04) ; localisateurs dans `resources/page_objects/fiori_travel_list.resource` |

Écarts de traçabilité : les scénarios 1 (chargement), 2 (compteur d'en-tête)
et 4 (retour à l'état non filtré) du plan planner ne sont pas couverts par cet
enregistrement (ils le sont par la suite générée) ; ce document ne les
duplique pas. L'enregistrement lui-même ne porte aucune assertion du résultat
filtré (voir questions ouvertes). `tests/robot/fiori_sflight_smoke.robot`
couvre le seul chargement, sans recherche.

## 6. Risques et points de vigilance

- **Libellés et formats suivent la locale du navigateur** : le même compteur a
  été rendu « Voyages (4 133) » (FR, séparateur U+202F) le 2026-07-25 et
  « Travels (4,133) » (EN, virgule) le 2026-08-05. Toute assertion doit
  porter sur les nombres extraits chiffre à chiffre (`isdigit`, jamais un
  motif regex à backslash défiguré par le parseur Robot), jamais sur le texte
  du titre ni sur les en-têtes de colonnes.
- **Course après « Go »** (écart de génération n°1 du plan) : juste après le
  clic, le compteur peut encore lire l'ancienne valeur ; le service OData v4
  groupe ses requêtes en `POST …/$batch`. Au rejeu avec assertion immédiate,
  armer l'attente de cette réponse AVANT le clic, puis attendre le retour du
  runtime UI5 ; `networkidle` seul est inopérant (constaté).
- **Course au chargement initial** (écart n°2) : la table peut être rendue
  avec 0 ligne instanciée juste après le bootstrap ; attendre qu'au moins une
  ligne soit portée par la table avant d'agir.
- **Les 30 lignes rendues sont le seuil de croissance de la table**, pas une
  volumétrie : seul le compteur d'en-tête porte le total ; ne jamais asserter
  30 ni déduire un total d'un comptage de lignes.
- **`BasicSearchField` est un contrôle composite** : écrire dans le champ
  interne (`…BasicSearchField-inner`, ce que portent les `hint` relevés),
  jamais dans la racine du contrôle (le dryrun passe, le run échoue : constaté
  live 2026-07-20).
- **Les `fallback` xpath du bloc replay sont positionnels**
  (`//SearchField[1]`, `//VerticalLayout[1]/…`) : repli faible, qui dérive au
  moindre ajout de champ de filtre ; l'ancre primaire reste l'idSuffix Fiori
  Elements. Ne jamais coder en dur le préfixe applicatif
  `sap.fe.cap.travel::TravelList--` : seul le suffixe `fe::…` est stable.
- **`cds watch` redémarre à chaud** : un bootstrap interrompu laisse
  l'application quasi vide (`Component.js` en `ERR_CONNECTION_REFUSED`) ; le
  diagnostic Fiori nomme la cause en une lecture, un rechargement suffit. Ne
  pas confondre avec une dérive de localisateur. À l'inverse, un bruit
  console bénin (~8 erreurs dont `storeInnerAppStateAsync`) existe sur
  l'application saine.
- Ne jamais rejouer avec des attentes fixes (`time.sleep`) : attendre la fin
  du chargement (runtime UI5 prêt, élément présent, réponse `$batch`).

## À compléter (questions ouvertes)

- L'enregistrement ne vérifie pas le résultat du filtrage (le compteur à 91 a
  été constaté à l'écran, pas asserté) : faut-il ré-enregistrer le parcours
  avec une assertion à chaud sur le compteur d'en-tête (ou étendre le bloc
  replay d'une étape de lecture du compteur) avant usage en régression ?
