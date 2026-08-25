# Parcours applicatif réversible dans l'iframe d'un launchpad Work Zone

- **Canal** : Fiori (web)
- **Système / URL** : la même cible que
  [workzone-launchpad-btp-perception.md](workzone-launchpad-btp-perception.md) :
  site **SAP Build Work Zone** sur un compte **SAP BTP** de trial, derrière un
  tenant **SAP Cloud Identity Services**. URL, utilisateur et mot de passe
  fournis en ligne de commande (convention 11).
  L'application parcourue est celle que le catalogue publie sous l'intent
  `ShoppingCart-display` : la démonstration **Shopping Cart** d'OpenUI5
  (`sap.ui.demo.cart`), servie en application de type URL et donc ouverte dans
  une iframe **cross-origin**. Runtime relevé : SAPUI5 **1.151.0**, **844**
  contrôles construits dans la frame.
- **Préconditions** :
  - un utilisateur du tenant, et l'application publiée au catalogue du site ;
  - la portée de frame applicative est établie par le Suite Setup ; tout ce plan
    se joue à l'intérieur.
- **Portée** : parcours d'**écriture réversible**. Le panier est modifié puis
  rendu à son état initial ; le teardown de suite le vide même après un échec.
  Aucune commande n'est passée (le bouton de validation du panier n'est jamais
  actionné).

## Données observées

Relevé live le 2026-08-24, exploration pilotée par rf-mcp (Browser +
SapFioriLibrary), à travers le launchpad et non en attaquant l'application
directement.

**Structure de l'application** : un `sap.f.FlexibleColumnLayout` à trois
colonnes (`beginColumnNav` = catégories, `midColumnNav` = produits puis fiche
produit, `endColumnNav` = panier), et cinq vues dont les ids sont **stables** :
`container-cart---homeView`, `---welcomeView`, `---category`, `---product`,
`---cartView`.

**Ids relevés, et ce qu'ils valent comme ancre** :

| Rôle fonctionnel | Ancre retenue | Type de contrôle |
|---|---|---|
| Liste des catégories | `viewId=container-cart---homeView--categoryList` | `sap.m.StandardListItem` |
| Liste des produits d'une catégorie | `viewId=container-cart---category` | `sap.m.ObjectListItem` |
| Nom d'un produit de la liste | `idSuffix=container-cart---category--productList-<i>-titleText` | `sap.m.Text` |
| Retour à la liste des catégories | `id=container-cart---category--page-navButton` | `sap.m.Button` |
| Image de la fiche produit | `id=container-cart---product--productImage` | `sap.m.Image` |
| Nom sur la fiche produit | xpath `//Page[@id='container-cart---product--page']//Bar//Title` | `sap.m.Title` |
| Ajouter au panier | xpath `//Page[@id='…product--page']//Toolbar//Button` | `sap.m.Button` |
| Ouvrir/fermer le panier | xpath `//Page[@id='…product--page']//Bar//ToggleButton` | `sap.m.ToggleButton` |
| Lignes du panier | `viewId=container-cart---cartView--entryList` | `sap.m.ObjectListItem` |
| Passer en édition | `id=container-cart---cartView--editButton` | `sap.m.Button` |
| Quitter l'édition | `id=container-cart---cartView--doneButton` | `sap.m.Button` |
| Total du panier | `id=container-cart---cartView--totalPriceText` | `sap.m.Text` |
| Supprimer une ligne | xpath `//List[@id='…cartView--entryList']//ObjectListItem//Button[@icon='sap-icon://decline']` | `sap.m.Button` |

- Les contrôles créés par une **fabrique** portent un préfixe généré
  (`__item5-…`, `__item7-…`, `__button10`) : ils s'adressent par `idSuffix`, par
  propriété, ou par un xpath **ancré sur une vue**, jamais par leur id complet.
- Le matcher `viewId` de la bibliothèque se comporte comme une correspondance
  de **sous-chaîne sur l'id du contrôle** : il fonctionne pour les contrôles de
  fabrique (dont l'id contient l'id de la liste) mais **pas** pour un contrôle à
  id entièrement généré. Mesuré : `viewId=container-cart---category` retourne 3
  lignes produit, mais `controlType=Button viewId=container-cart---product`
  retourne **0** alors que la fiche produit contient bien trois boutons. D'où
  les xpath ancrés sur la vue pour les boutons.

**Volumétrie et portée** : la catégorie `Speakers` contient **3** produits
(`Blaster Extreme`, `Sound Booster`, `Surround Sound`), tandis qu'un comptage
**global** des lignes produit de l'application en retourne **13** : l'accueil
garde ses propres listes (produits mis en avant, consultés, favoris) dans le
registre UI5. C'est la portée `viewId` qui fait la différence entre « les
produits de cette catégorie » et « toutes les lignes produit ».

**Cycle du panier, mesuré de bout en bout** : ajout depuis la fiche produit,
`MessageToast` capté (`Product "Sound Booster" added to your shopping cart`),
panier à **1** ligne, total `Total: 45,00 EUR` ; puis passage en édition
(le titre de la page devient `Edit Cart` et chaque ligne reçoit un bouton de
suppression), suppression, confirmation, panier à **0** ligne et total
`Total: 0,00 EUR`, retour en lecture.

**Langue et formats.** Le navigateur étant en français, UI5 rend ses textes de
bibliothèque en français (textes d'accessibilité, boutons de MessageBox
« Supprimer » / « Annuler ») et formate les nombres selon la locale (`45,00`),
tandis que les textes propres à l'application de démonstration restent en
anglais (`Add to Cart`, `Supplier`, `Description`). Une assertion de texte
d'interface serait donc fausse dans un sens ou dans l'autre selon le poste.

**Boîte de dialogue de confirmation** : `sap.m.Dialog` de `type="Message"`,
deux boutons d'action aux ids générés (`__mbox-btn-0` = confirmer,
`__mbox-btn-1` = annuler), plus un bouton de débordement. Le libellé étant
localisé et l'id généré, la seule adresse stable est la **position**.

## Scénarios

### 1. L'application s'exécute dans l'iframe du launchpad
- **Étapes** : lire la composition de la portée courante ; compter le champ de
  recherche du shell.
- **Résultat attendu** : runtime UI5 présent, au moins un contrôle construit, et
  **0** champ de recherche du shell résolu (sans quoi le parcours testerait le
  shell en croyant tester l'application).
- **Keywords métier manquants** : `Ouvrir Le Parcours Du Panier` (Suite Setup :
  session, navigation par intent, entrée dans la frame, attente du premier
  rendu).

### 2. Le catalogue de catégories est rendu
- **Étapes** : lister les catégories du volet gauche.
- **Résultat attendu** : liste non vide, chaque nom non vide. Les noms sont des
  DONNÉES du modèle, pas des libellés traduits : les lire reste indépendant de
  la locale.
- **Keywords métier manquants** : `Lister Les Categories`,
  `Compter Les Categories`.

### 3. Une catégorie restreint la liste des produits
- **Étapes** : parcourir les catégories jusqu'à en trouver deux qui contiennent
  des produits ; pour chacune, compter les produits de la catégorie et les
  lignes produit de toute l'application ; comparer les deux listes de noms.
- **Résultat attendu** : le comptage global est supérieur ou égal au comptage
  porté à la catégorie (13 contre 3 relevés), et deux catégories différentes ne
  montrent pas les mêmes produits. Aucun nom de catégorie n'est codé en dur.
- **Keywords métier manquants** : `Ouvrir La Categorie`,
  `Lister Les Produits De La Categorie`, `Compter Les Produits De La Categorie`,
  `Compter Toutes Les Lignes Produit De L Application`.

### 4. La fiche produit affiche le produit choisi
- **Étapes** : ouvrir le premier produit trouvé ; vérifier l'illustration et le
  nom porté par l'en-tête.
- **Résultat attendu** : l'image de la fiche est rendue et le nom affiché est
  **exactement** celui qui a été demandé. Vérifier seulement « une fiche s'est
  ouverte » laisserait passer une navigation vers le mauvais élément.
- **Keywords métier manquants** : `Ouvrir Un Produit Disponible` (découverte),
  `La Fiche Produit Est Affichee`, `Lire Le Nom Du Produit Affiche`.

### 5. L'ajout au panier est confirmé par un message applicatif
- **Étapes** : relever les messages avant l'ajout, ajouter, relever après.
- **Résultat attendu** : un `MessageToast` de plus qu'avant, et **aucun message
  de type `Error`**. L'assertion porte sur le TYPE et sur le compte, jamais sur
  le texte (convention 3).
- **Keywords métier manquants** : `Ajouter Le Produit Au Panier`,
  `Lire Les Messages De L Application`, `Aucun Message D Erreur N A Ete Emis`.

### 6. Le panier porte exactement la ligne ajoutée
- **Étapes** : mesurer le nombre de lignes du panier, ajouter un produit, ouvrir
  le panier, mesurer de nouveau et vérifier la présence du produit.
- **Résultat attendu** : une ligne de plus qu'avant, et la ligne porte le
  produit demandé. La référence est mesurée dans le MÊME test : le panier peut
  déjà contenir la ligne d'un scénario précédent, et supposer qu'il est vide
  rendrait le test dépendant de son ordre d'exécution.
- **Keywords métier manquants** : `Ouvrir Le Panier`,
  `Compter Les Lignes Du Panier`, `Le Panier Contient Le Produit`,
  `Lire Le Total Du Panier`.

### 7. La suppression rend le panier à son état initial
- **Étapes** : mesurer l'état initial, ajouter, ouvrir le panier, passer en
  édition, supprimer la première ligne, confirmer, quitter l'édition, mesurer.
- **Résultat attendu** : le panier revient au nombre de lignes mesuré au début
  du test, et aucun message d'erreur n'a été émis. C'est la propriété de
  réversibilité, celle qui autorise à rejouer la campagne sur un système partagé
  sans le polluer.
- **Keywords métier manquants** : `Passer Le Panier En Edition`,
  `Supprimer La Premiere Ligne Du Panier`, `Quitter L Edition Du Panier`,
  `Le Dialogue De Confirmation Propose Deux Actions`, `Confirmer Le Dialogue`,
  `Vider Le Panier` (teardown).
- **Adresse par position, assumée** : les boutons de la MessageBox portent un
  libellé traduit et un id généré. La structure est donc vérifiée avant d'être
  actionnée (deux actions, confirmer puis annuler), et seule la position est
  utilisée.

## Écarts constatés à la génération

Relevés le 2026-08-24 en exécutant la suite produite
(`tests/robot/ui/fiori/parcours_panier_workzone.robot`). Trois défauts, tous
invisibles en pilotage interactif, et une lacune de bibliothèque comblée.

1. **Le texte rendu d'un élément de liste n'est pas son titre.** Lire les noms
   de catégories par le texte visible donnait `Accessories\n34` : le contrôle
   dessine son compteur de produits sous le titre. Réinjecté dans un
   localisateur, ce nom échouait deux fois (aucun titre ne correspond, et le
   saut de ligne casse le littéral de dictionnaire).
2. **Un contrôle rendu mais masqué n'a pas de texte lisible.** Quand le
   `FlexibleColumnLayout` replie une colonne, ses contrôles restent dans le
   registre (donc parfaitement résolus) mais la lecture du texte attend une
   visibilité qui ne vient pas et expire au bout de 10 s. Le symptôme ressemble
   à une dérive de localisateur et n'en est pas une.
3. **Lacune de bibliothèque, comblée plutôt que contournée** : rien ne
   permettait de lire une PROPRIÉTÉ de contrôle, seulement son rendu. D'où
   `Get Ui5 Property` / `Get Ui5 Properties` dans `SapFioriLibrary` (lecture au
   registre, exacte, indépendante de la visibilité, avec échec actionnable
   listant les propriétés disponibles quand le nom demandé n'existe pas). Les
   deux points ci-dessus disparaissent avec elle, et les listes de noms se
   lisent désormais en un appel.
4. **Cliquer une ligne DÉJÀ sélectionnée ne navigue pas.** `sap.m.List` en mode
   sélection n'émet pas d'événement quand la sélection ne change pas. Le
   deuxième test qui rouvrait « le premier produit de la première catégorie »
   cliquait donc sans effet ; la fiche produit n'était pas à l'écran, et l'échec
   tombait deux étapes plus loin, sur un bouton d'ajout qualifié d'« invisible »
   qui n'avait rien à se reprocher. Corrigé en deux temps : le choix se porte
   sur un produit NON sélectionné (propriété `selected` lue au registre), et
   l'ouverture vérifie que la fiche demandée est bien à l'écran.
5. **Compter le panier sans l'avoir ouvert mesure une vue absente.** Tant que
   la vue du panier n'a jamais été rendue, le comptage donne 0 alors que le
   modèle contient déjà des articles ajoutés depuis une fiche produit. Le
   « avant » d'un test se mesurait donc à 0 face à un « après » à 2. Les
   scénarios ouvrent maintenant le panier avant de le mesurer, et le mot-clé de
   comptage porte l'avertissement.
6. **Ajouter un produit DÉJÀ présent n'ajoute pas de ligne**, il incrémente la
   quantité de la ligne existante (`intro` passe à « 2 x »). Une assertion
   « une ligne de plus » doit donc partir d'un produit absent du panier :
   `Preparer Un Produit Absent Du Panier` ouvre le panier, relève son contenu,
   et choisit ailleurs. Le rejeu enchaîné des deux campagnes est ce qui a
   révélé le cas, la deuxième exécution retombant sur un produit déjà ajouté.
   Corollaire du même scénario : c'est la ligne AJOUTÉE qui est supprimée, pas
   la première venue, sinon le compte revient juste en ayant retiré la mauvaise.
7. **Un bouton BASCULE ne se clique pas, il se pilote vers un état.** Le panier
   s'ouvre et se ferme par le même `sap.m.ToggleButton`. Cliquer « pour ouvrir »
   revient donc à parier sur l'état courant, et le pari se perd dès qu'une
   navigation a refermé la colonne entre-temps : le scénario poursuit en croyant
   le panier ouvert, et l'échec tombe sur le bouton suivant. `Ouvrir Le Panier`
   et `Fermer Le Panier` sont donc IDEMPOTENTS (observer l'état, agir seulement
   si nécessaire, puis attendre l'état voulu), et le geste brut reste un mot-clé
   interne.
8. **Tous les produits ne s'ajoutent pas de la même façon.** Un produit en
   RUPTURE ouvre un dialogue de confirmation à l'ajout (« currently out of
   stock, but you can order it »), un produit ARRÊTÉ un dialogue
   d'information. Non traité, ce dialogue reste MODAL : il ne fait pas échouer
   l'ajout, il fait échouer tout ce qui suit, sur des contrôles « non
   cliquables » parfaitement innocents. C'est le diagnostic de teardown
   (snapshot ARIA) qui a nommé la cause en une lecture. Deux conséquences : les
   scénarios choisissent un produit COMMANDABLE, trié sur l'**état** du statut
   (`Success`) et jamais sur son texte localisable ; et `Ajouter Le Produit Au
   Panier` refuse désormais de laisser un dialogue ouvert derrière lui.
   Le chemin « ajouter malgré la rupture » reste à couvrir : c'est un scénario
   à part entière, pas un accident à absorber.
9. **Un teardown qui agit sur des contrôles masqués ne rate pas, il traîne.**
   Le vidage du panier s'exécutait colonne refermée : chaque clic attendait son
   délai avant d'échouer, et le nettoyage prenait des minutes pour ne rien
   nettoyer. Le mot-clé rouvre désormais la colonne avant d'agir.

## Points de vigilance

- **« Résolvable » ne veut pas dire « cliquable ».** Dès qu'une colonne de
  détail est ouverte, le `FlexibleColumnLayout` masque les catégories : elles
  restent dans le registre UI5, donc parfaitement résolues, mais le clic échoue
  sur `element is not visible` après avoir pourtant trouvé son élément. Le
  symptôme ressemble à une dérive de localisateur et n'en est pas une. Toute
  navigation vers le catalogue commence donc par refermer le panier puis
  revenir à la liste des catégories, la visibilité étant **vérifiée**, pas
  supposée. Mesuré aussi : élargir la fenêtre ne change rien, c'est la
  navigation de l'application qui décide des colonnes affichées.
- **Le panier s'ouvre et se ferme avec le MÊME bouton bascule** de la fiche
  produit : c'est la voie utilisée par ces campagnes, et le page object le
  documente comme une hypothèse de flux.
- **Un teardown doit vider le panier sans masquer un échec** : le vidage est
  exécuté en avertissement (jamais silencieux, jamais bloquant), car un panier
  laissé plein fausserait le run suivant.
- **Ne jamais asserter le total sous sa forme rendue** (`Total: 45,00 EUR`) :
  le séparateur décimal, la place de la devise et le libellé dépendent de la
  locale. Le total est lu et journalisé ; ce sont les comptes de lignes qui
  portent l'assertion.
- **Le `MessageToast` est éphémère à l'écran mais pas dans la perception** : le
  hook est posé à l'injection du bundle, donc un toast émis AVANT l'entrée dans
  la frame est perdu. Relever les messages avant l'action et comparer.
- **La borne de la boucle de vidage** est un garde-fou : une suppression qui
  n'aboutit pas doit arrêter la boucle, pas la faire tourner.
