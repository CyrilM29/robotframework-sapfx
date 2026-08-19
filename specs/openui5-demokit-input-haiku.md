# Consultation de la documentation sap.m.Input dans le Demo Kit

- **Canal** : Fiori (web)
- **Système / URL** : https://sdk.openui5.org/ (application UI5 v1.151.0 publique)
- **Préconditions** : aucune ; c'est une documentation publique consultable directement.

## Données observées

Lors de l'exploration en direct via rf-mcp, les faits suivants ont été relevés :

- Application UI5 version 1.151.0
- Total de 551 contrôles UI5 rendus sur l'écran principal
- Titre de la page : « Demo Kit - OPENUI5 SDK »
- Langues détectées : français et anglais (selon contexte navigateur)
- Banneau de consentement TrustArc en overlay, bouton de fermeture ID `truste-consent-button`
- Architecture de l'interface : onglets principaux (TabFilter), champs SearchField, liens pour la navigation

### Structure observée de l'écran principal

- **Onglets (IconTabFilter)** :
  - @8 : Home (accueil)
  - @9 : Documentation
  - @10 : API Reference (Référence de l'API)
  - @11 : Samples (Échantillons)
  - @12 : Demo Apps (Applications de démo)
  - @13 : Resources (Ressources)
  - @14 : Plus (menu supplémentaire)

- **Barre d'outils supérieure** :
  - Champ de recherche global (@1) : SearchField `sdk---app--searchControl-searchField`
  - Bouton Feedback (@2) : OverflowToolbarButton
  - Bouton News (@5) : OverflowToolbarButton

### Page de Référence de l'API (API Reference)

Après clic sur l'onglet @10 (API Reference), la page suivante s'affiche :

- Nouveau contrôle SearchField (@16) : « Filter » (champ de filtrage) avec ID `sdk---apiMaster--searchField`
- Boutons d'action (@17, @18) : « Expand All », « Collapse All »
- Panneau de liste latéral gauche : contient la hiérarchie des contrôles et espaces de noms UI5 (sap.m, sap.ui, etc.)
- Panneau de contenu principal (droite) : affiche la documentation détaillée du contrôle sélectionné

### Comportements dynamiques observés

- **Banneau TrustArc** : Intercepte les clics jusqu'à fermeture. Fermeture via le bouton CSS `#truste-consent-button`
- **Champ de filtre** : Accepte la saisie de texte et filtre la liste des contrôles en temps réel
- **Attente UI5** : Keyword `Wait For Ui5 Idle` confirme le repos après navigation (réseau + DOM + busy indicators)

## Scénarios

### 1. Naviguer jusqu'à la page d'accueil du Demo Kit

- **Étapes** :
  1. Ouvrir l'URL `https://sdk.openui5.org/` via Browser keyword `New Page`
  2. Percevoir la page avec `Get Page Composition` pour vérifier que c'est une application UI5 (résultat attendu : `ui5_runtime=true`, `ui5_version` présente)
  3. Fermer la banneau de consentement TrustArc en cliquant sur le bouton CSS `#truste-consent-button`
  4. Valider que les onglets principaux sont visibles avec `Get Ui5 Page Map`

- **Résultat attendu** :
  - Le site charge sans erreur (HTTP 200)
  - La page affiche le titre « Demo Kit - OPENUI5 SDK »
  - La page contient une application UI5 avec 551+ contrôles rendus
  - Après fermeture de la banneau, l'onglet « API Reference » (@10) est cliquable

- **Keywords métier manquants** : aucun

### 2. Naviguer vers la Référence de l'API (API Reference)

- **Étapes** :
  1. À partir de la page d'accueil, cliquer sur l'onglet « API Reference » (ref @10 de la carte `Get Ui5 Page Map`)
  2. Attendre l'inactivité UI5 avec `Wait For Ui5 Idle`
  3. Percevoir la page avec `Get Ui5 Page Map` pour valider que le champ de filtrage est présent

- **Résultat attendu** :
  - Le contenu principal change pour afficher la page de l'API Reference
  - Un nouveau champ SearchField « Filter » (id `sdk---apiMaster--searchField`) s'affiche
  - La page contient toujours 33 éléments actionnables (selon observation live)
  - URL change vers `https://sdk.openui5.org/#/api` ou équivalent

- **Keywords métier manquants** : aucun

### 3. Rechercher et afficher la documentation de sap.m.Input

- **Étapes** :
  1. Accéder à la page API Reference (étape précédente)
  2. Saisir le texte « sap.m.Input » dans le champ de filtrage (ref @16) avec `Fill Ui5 Ref`
  3. Attendre l'inactivité UI5 pour que la liste des résultats se mette à jour
  4. Localiser et cliquer sur l'élément « sap.m.Input » dans la liste filtrée
  5. Attendre le chargement de la page de documentation

- **Résultat attendu** :
  - Le champ de filtrage contient « sap.m.Input »
  - La liste latérale se filtre pour afficher uniquement les entrées contenant « Input »
  - Le clic sur sap.m.Input charge la page de spécification du contrôle
  - La page de documentation affiche les sections : Overview, Properties, Events, Methods, Aggregations, etc.

- **Points d'attention** : La requête de clic sur le lien exact peut nécessiter d'ajuster le sélecteur de contrôle si le texte du lien inclut du formatage ou des espaces supplémentaires. Une approche alternative est d'utiliser l'URL directe si le pattern de routing est connu.

### 4. Lire les spécifications détaillées du contrôle sap.m.Input

- **Étapes** :
  1. Une fois la page de documentation sap.m.Input chargée, percevoir la structure avec `Get Ui5 Page Tree`
  2. Localiser les sections suivantes :
     - Onglets de contenu (Overview, Properties, Events, Methods, Aggregations, etc.)
     - Tableau des propriétés avec colonnes : Name, Type, Default Value, Description
     - Exemples de code (optionnel)
  3. Extraire les propriétés principales (voir observation ci-dessous)
  4. Valider les propriétés observables via des assertions sur le texte visible

- **Résultat attendu** :
  - La page affiche une section « Overview » décrivant le contrôle sap.m.Input
  - Une liste de propriétés visibles incluant :
    - `value` : propriété clé de saisie de texte
    - `placeholder` : texte d'indication
    - `enabled` : état activé/désactivé
    - `maxLength` : longueur maximale
    - `type` : type de champ (text, password, email, etc.)
  - Chaque propriété est accompagnée de sa description et de son type de données
  - Des événements (events) tels que `change`, `liveChange`, `submit` sont listés

- **Keywords métier manquants** : aucun

## Points de vigilance

### 1. Banneau de consentement TrustArc

La page contient un overlay de consentement TrustArc qui peut intercepter les clics. Il DOIT être fermé en premier via le bouton CSS `#truste-consent-button` avant toute interaction avec les onglets.

### 2. Structure dynamique de la liste de l'API Reference

Après la saisie dans le champ de filtre, la liste des contrôles s'actualise dynamiquement. Le filtrage peut prendre quelques millisecondes. Utiliser `Wait For Ui5 Idle` pour s'assurer que la page est stable avant de cliquer sur un élément.

### 3. Liens potentiellement cachés ou décalés

Le moteur d'accès UI5 pour un lien peut nécessiter un ajustement si le texte du lien inclut des espaces insécables, des accents ou du formatage spécial (gras, italique). Une exploration de `Get Ui5 Page Tree` peut être nécessaire pour identifier l'ID exact du contrôle à cliquer.

### 4. Pluralité de contrôles Link

L'observation a montré 11 contrôles `sap.m.Link` sur la page. Une recherche par propriété `text` doit être suffisamment précise pour cibler le bon lien. En cas d'ambiguïté, utiliser un xpath ou une propriété `bindingPath` si disponible.

### 5. Reconnaissance de l'URL de navigation

Le Demo Kit utilise un système de routing basé sur le hash (ex. `#/api/sap.m.Input`). Une navigation directe via l'URL complète peut être possible si le pattern est identifié, mais cela nécessite une analyse approfondie de la structure des routes.

### 6. Localisation de la page

Selon la langue du navigateur système, l'interface affiche du français ou de l'anglais. Les libellés des onglets et boutons peuvent varier. Les assertions doivent utiliser les IDs de contrôles plutôt que des textes localisés pour garantir une fiabilité cross-locale.
