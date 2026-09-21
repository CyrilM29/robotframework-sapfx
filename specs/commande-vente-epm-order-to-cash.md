# Commande de vente EPM de bout en bout (Order-to-Cash) via SEPM_SO

- **Canal** : ECC (SAP GUI)
- **Système / URL** : ABAP Platform Trial A4H (S/4HANA 1909), connexion
  `/H/vhcala4hci/S/3200`, client 001, langue EN, utilisateur `DEVELOPER`.
- **Préconditions** :
  - Données de démonstration EPM présentes : garde `Ensure EPM Demo Data
    Exists` (`resources/a4h_demo_data.resource`, génération `SEPM_DG`
    uniquement si `SNWD_PO` est vide). Lors du relevé, le modèle EPM était
    déjà peuplé (10000 commandes dans `SNWD_SO`, 87 partenaires dans
    `SNWD_BPA`, plusieurs centaines de produits dans `SNWD_PD`) ; la garde
    n'a rien déclenché.
  - Sortie SE16 en **grille ALV** pour l'utilisateur de test : keyword
    `Use ALV Grid In Data Browser` (réglage persistant par utilisateur).
- **Nature** : campagne **d'écriture réversible et idempotente**, rejouable
  sans limite : chaque exécution crée une commande à laquelle SAP attribue un
  numéro **neuf et unique** (aucune collision possible entre deux runs, y
  compris concurrents), puis la supprime par la fonction officielle de la
  transaction elle-même. Contrairement à `simulation-ecriture-lecture-cross-
  canal.md`, qui écrit directement dans le dictionnaire par SE16 et exige un
  double opt-in, cette campagne passe par la transaction métier **standard et
  livrée par SAP pour cet usage précis** (`SEPM_SO`, y compris sa fonction
  Delete) : aucun opt-in n'est requis, un tag `write` suffit à l'exclure d'un
  run strictement lecture seule.
- **Objectif** : prouver le cycle Order-to-Cash EPM de bout en bout sur
  l'interface SAP GUI (saisie d'une commande de vente, sauvegarde, numéro de
  commande isolé depuis le message de confirmation) puis **croiser** cette
  écriture avec le canal SE16 (la même commande, identifiée par son numéro,
  existe physiquement dans `SNWD_SO`), et prouver la réversibilité (la
  suppression fait disparaître la même ligne).

> **Statut : faits live relevés le 2026-09-18 (A4H, client 001, session
> rf-mcp).** Les identifiants observés (numéros de commande, partenaire,
> produit) sont des observations **datées** de cette cible : deux commandes
> ont été créées puis supprimées pendant le relevé (`0500010051`,
> `0500010052`), et le compteur repart du numéro suivant à chaque nouvelle
> exécution. Aucune de ces valeurs n'est une constante du produit.

## Pourquoi SEPM_SO existe et comment il a été vérifié

Une note de veille interne proposait ce scénario comme une **idée** de
campagne future, jamais vérifiée live. La transaction
`SEPM_SO` n'apparaissait dans aucune exploration antérieure du dépôt (seule
`SEPM_DG`, le générateur de données de masse, était connue). Avant d'écrire un
mot de test, la transaction a donc été lancée en direct via une session
rf-mcp : elle existe bel et bien (programme `RS_EPM_SO_CLASSIC_DYNPRO`,
dynpro `100` pour l'écran initial), avec trois boutons : Create, Display,
Delete. Le cycle complet (création, sauvegarde, lecture croisée, suppression)
a été rejoué **deux fois de suite** avec deux partenaires et deux produits
différents, sans jamais échouer.

## Données observées

### Écran initial SEPM_SO (dynpro `RS_EPM_SO_CLASSIC_DYNPRO/SEPM_SO/100`)

| Cible | Locator observé | Type GUI | Libellé humain vérifié |
|---|---|---|---|
| Numéro de commande | `wnd[0]/usr/ctxtGV_SO_ID` | GuiCTextField | `Sales Order ID` |
| Bouton Créer | `wnd[0]/usr/btnCREATE` | GuiButton | (pas de tooltip) |
| Bouton Afficher | `wnd[0]/usr/btnDISPLAY` | GuiButton | (pas de tooltip) |
| Bouton Supprimer | `wnd[0]/usr/btnDELETE` | GuiButton | (pas de tooltip) |

### Écran de saisie (dynpro `RS_EPM_SO_CLASSIC_DYNPRO/SEPM_SO/300`), deux onglets

Tabstrip `wnd[0]/usr/tabsEPM_SO_TAB` : `EPM_SO_TAB_FC1` = « Header Data »,
`EPM_SO_TAB_FC2` = « Items ».

| Cible | Locator observé | Type GUI | Libellé humain vérifié |
|---|---|---|---|
| Partenaire commercial | `.../tabpEPM_SO_TAB_FC1/ssubEPM_SO_TAB_SCA:RS_EPM_SO_CLASSIC_DYNPRO:0301/ctxtSEPM_SO_HEADER_300-BP_ID` | GuiCTextField | `Business Partner ID` |
| Table des postes | `.../tabpEPM_SO_TAB_FC2/ssubEPM_SO_TAB_SCA:RS_EPM_SO_CLASSIC_DYNPRO:0302/tblRS_EPM_SO_CLASSIC_DYNPROSO_ITEMS` | GuiTableControl | (colonnes ci-dessous) |
| Bouton Insérer une ligne | `.../tblRS_EPM_SO_CLASSIC_DYNPROSO_ITEMS/btnINSERT_ROW` (frère du table control) | GuiButton | (pas de tooltip) |

Colonnes du table control des postes (titres relevés par `Read Table
Control`) : `ITEM POS`, `PRODUCT ID`, `QUANTITY`, `QUA` (unité), `GROSS
AMOUNT`, `CURRE` (devise), `NOTE`. Une ligne insérée porte déjà `QUANTITY =
1,000` par défaut ; l'adressage de cellule (`Set/Get Table Control Cell`) est
0-INDEXÉ (`row=0` pour la première ligne insérée, vérifié live : `row=1`
échoue par `com_error` « invalid argument », la ligne n'existant pas).

### Messages de statut (identité, convention 3 : jamais de texte localisé)

| Action | Identité | Paramètre | Texte observé (EN, jamais asserté) |
|---|---|---|---|
| Sauvegarde réussie | `SEPM_BOR_MESSAGES/S/044` | `[so_id]` | `Sales Order <id> saved` |
| Suppression réussie | `SEPM_BOR_MESSAGES/S/061` | `[so_id]` | `Sales Order <id> deleted` |

Le numéro de commande n'est **jamais** extrait du texte du message (localisé,
donc fragile) : il vient du paramètre `parameters[0]` de l'identité, rendu
par `Get Status Message Identity` / `Status Message Should Be`.

### Confirmation de suppression (fenêtre modale)

`Click Element    wnd[0]/usr/btnDELETE` ouvre une fenêtre modale `wnd[1]`
avec deux boutons (`Get Modal Buttons` observé) : `wnd[1]/usr/btnBUTTON_1`
(texte « Yes »), `wnd[1]/usr/btnBUTTON_2` (texte « No »). Cette paire de
boutons vient d'un module de confirmation générique de la transaction (les
noms techniques `BUTTON_1`/`BUTTON_2` sont stables ; leur texte dépend de la
langue de connexion, ici EN).

### Table `SNWD_SO` (Data Browser / SE16)

Colonnes techniques (`Get Grid Column Ids`) : `CLIENT`, `NODE_KEY`, `SO_ID`,
`CREATED_BY`, `CREATED_AT`, `CHANGED_BY`, `CHANGED_AT`, `CREATED_BY_BP`,
`CHANGED_BY_BP`, `NOTE_GUID`, `BUYER_GUID`, `CURRENCY_CODE`, `GROSS_AMOUNT`,
`NET_AMOUNT`, `TAX_AMOUNT`, `LIFECYCLE_STATUS`, `BILLING_STATUS`,
`DELIVERY_STATUS`, `OP_ID`, `_DATAAGING`, `DUMMY`, `OVERALL_STATUS`,
`BUY_CONTACT_GUID`, `SHIP_TO_ADR_GUID`, `BILL_TO_ADR_GUID`,
`PAYMENT_METHOD`, `PAYMENT_TERMS`. Écran de sélection (`Get Se16 Selection
Criteria`, dérivé live, jamais gravé en dur) : `SO_ID` = `wnd[0]/usr/txtI2-
LOW`, `LIFECYCLE_STATUS` = `wnd[0]/usr/ctxtI15-LOW`.

Une commande fraîchement créée porte `LIFECYCLE_STATUS = 'N'` (nouvelle),
contre `'C'` (confirmée) pour les commandes de démonstration livrées :
c'est ce qui distingue, dans le croisement, la commande **du test** d'une
commande préexistante qui porterait le même numéro par coïncidence (numéro
que SAP garantit de toute façon unique).

Après suppression via `SEPM_SO`, `Count Entries On Current Selection Screen`
(filtré sur `SO_ID`) revient à **0** : la ligne a physiquement disparu de
`SNWD_SO`, vérifié live sur les deux commandes créées pendant l'exploration.

### Table `SNWD_BPA` (partenaires commerciaux)

Colonnes utiles : `BP_ROLE`, `BP_ID`, `COMPANY_NAME`. `BP_ROLE = '01'` =
client (celui qu'une commande de vente référence) ; les partenaires de rôle
`02` sont des fournisseurs (déjà établi par
`specs/croisement-ddic-odata-ecc-s4hana.md`, réutilisé ici plutôt que
redécouvert). Premier client relevé (`BP_ROLE=01`, tri par `NODE_KEY`) :
`0100000000` (« OffiPOR »).

### Table `SNWD_PD` (produits)

Colonnes utiles : `PRODUCT_ID`, `CATEGORY`, `PRICE`, `MEASURE_UNIT`. Premier
produit relevé (sans filtre) : `AR-FB-1000` (« Files & Binders », 3,25 USD,
unité `EA`).

## Scénarios

### 1. Lire un client et un produit EPM existants

- **Étapes** :
  1. `Display Table Contents With Filter    SNWD_BPA    BP_ROLE=01` puis lire
     la première ligne (`BP_ID`) : jamais un identifiant inventé, toujours
     relu dans les données existantes à l'exécution (même principe que
     `simulation-ecriture-lecture-cross-canal.md` pour sa catégorie EPM).
  2. `Display Table Contents    SNWD_PD` puis lire la première ligne
     (`PRODUCT_ID`).
- **Résultat attendu** : un `BP_ID` et un `PRODUCT_ID` non vides, mémorisés
  pour les scénarios suivants.
- **Keywords métier manquants** : aucun (`Display Table Contents With
  Filter`, `Read Displayed Grid` existent déjà) ; le dictionnaire
  `SNWD_BPA_SELECTION_FIELDS` (critère `BP_ROLE`) est à ajouter à
  `resources/ecc_keywords.resource`, à côté de `SCARR_SELECTION_FIELDS` /
  `SPFLI_SELECTION_FIELDS`.

### 2. Créer une commande de vente EPM via SEPM_SO

- **Étapes** :
  1. Lancer `SEPM_SO`, cliquer Create.
  2. Saisir le partenaire commercial (onglet Header Data, libellé humain
     vérifié `Business Partner ID`), valider (Entrée).
  3. Passer à l'onglet Items, insérer une ligne, y saisir le produit et la
     quantité (table control, adressage par TITRE de colonne, jamais par id
     brut dans le test), valider (Entrée).
  4. Sauvegarder (Ctrl+S / `btn[11]`).
  5. Confronter le message de statut à l'identité attendue
     (`SEPM_BOR_MESSAGES/S/044`) et isoler le numéro de commande depuis son
     paramètre.
- **Résultat attendu** : message de type `S`, identité exacte, numéro de
  commande non vide (10 chiffres).
- **Keywords métier manquants** : `Create Epm Sales Order` (page object
  `resources/page_objects/sepm_so_order_entry.resource`, composant `Fill
  Field By Label`, `Select Tab`, `Set Table Control Cell`, `Status Message
  Should Be`).

### 3. Vérifier l'inscription physique de la commande dans SNWD_SO

- **Étapes** :
  1. `Count Table Entries With Criteria    SNWD_SO    SO_ID=<numéro>
     LIFECYCLE_STATUS=N` (keyword déjà existant, critères dérivés live de
     l'écran, aucun dictionnaire à maintenir).
- **Résultat attendu** : exactement **1** entrée. Une commande dont le canal
  SAP GUI affirme la création et que SE16 ne retrouve pas serait un défaut
  (écriture non physique) ; l'inverse (SE16 en trouve plusieurs) serait une
  incohérence de clé, qui ne devrait jamais se produire (le numéro est
  attribué par SAP).
- **Keywords métier manquants** : aucun.

### 4. Nettoyer la commande créée et prouver sa disparition (teardown)

Ce n'est pas un scénario métier à part entière mais la garantie de
réjouabilité : il s'exécute **inconditionnellement** en fin de suite (même si
un scénario précédent a échoué), et ne fait rien si aucune commande n'a été
créée.

- **Étapes** :
  1. Si un numéro de commande a été capturé : lancer `SEPM_SO`, saisir ce
     numéro (libellé humain vérifié `Sales Order ID`), cliquer Delete,
     confirmer (« Yes ») la fenêtre modale.
  2. Confronter le message de statut à l'identité attendue
     (`SEPM_BOR_MESSAGES/S/061`).
  3. `Count Table Entries With Criteria    SNWD_SO    SO_ID=<numéro>` doit
     revenir à **0**.
- **Résultat attendu** : la commande a disparu des deux côtés (message de
  suppression ET SE16). Un échec de nettoyage est journalisé en
  avertissement plutôt que de faire échouer la suite : la commande restante
  ne bloque aucune exécution future (chaque run utilise un numéro neuf), mais
  l'avertissement reste visible pour un opérateur.
- **Keywords métier manquants** : `Delete Epm Sales Order` (même page
  object).

## Invariant métier et réversibilité

**Invariant** : toute commande de vente EPM créée par cette suite est
retrouvée dans `SNWD_SO`, à l'identique par son numéro, puis n'existe plus
après suppression. La suite ne suppose jamais l'état du système au départ
(aucun décompte global avant/après, contrairement à `simulation-ecriture-
lecture-cross-canal.md`) : chaque exécution raisonne sur SA PROPRE commande,
identifiée par le numéro que SAP lui a attribué, jamais sur un compte global
de `SNWD_SO` (10000 lignes et en croissance, propre à ce système).

**Pourquoi 100 exécutions consécutives ne peuvent pas se gêner l'une
l'autre** : le partenaire et le produit sont **lus**, jamais créés ni
modifiés (aucune écriture sur `SNWD_BPA`/`SNWD_PD`) ; le numéro de commande
est **attribué par SAP** à la sauvegarde, jamais choisi par le test, ce qui
exclut toute collision entre deux exécutions, y compris concurrentes ; et la
suppression est **ciblée par ce numéro exact**, jamais par un critère large.
Un teardown qui échouerait à supprimer laisserait une commande orpheline
inoffensive (une ligne de plus dans une table qui en compte déjà des
milliers), jamais un obstacle à l'exécution suivante.

## Points de vigilance

- Le partenaire doit être de rôle `01` (client) : un partenaire de rôle `02`
  (fournisseur) n'est pas nécessairement refusé par l'écran, mais fausserait
  le sens métier de la commande. Toujours filtrer `BP_ROLE=01`.
- L'adressage du table control des postes est **0-indexé** dans ce dépôt
  (`row=0` pour la première ligne), contrairement à une lecture naïve de
  « ligne absolue » qui suggérerait `row=1` : vérifié par l'échec `com_error`
  obtenu avec `row=1` sur une table à une seule ligne.
- Les boutons de la fenêtre de confirmation de suppression sont nommés
  techniquement `BUTTON_1`/`BUTTON_2`, mais leur **texte** (« Yes »/« No »)
  dépend de la langue de connexion : cette suite épingle `SAP_LANGUAGE=EN`
  (défaut de `resources/ecc_keywords.resource`) pour que le texte reste
  stable d'une exécution à l'autre.
- Ne jamais confondre ce cycle avec celui de `simulation-ecriture-lecture-
  cross-canal.md` : celui-là écrit directement par SE16 dans le dictionnaire
  (double opt-in requis, danger de suppression de masse) ; celui-ci passe
  par la transaction métier officielle et sa propre fonction Delete, jugée
  sur son message de confirmation, jamais sur un menu SE16.
