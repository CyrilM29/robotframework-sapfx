# Procure-to-Pay EPM cross-canal : reception de marchandise et stock (SNWD_STOCK)

- **Canaux** : API (OData v2, service `SEPMRA_PO_MAN`) pour l'action metier
  d'achat, SAP GUI (SE16) pour la verification physique du stock. Suite
  **cross-paradigme** au sens du depot : un canal ECRIT, un canal DIFFERENT
  RELIT et prouve l'effet.
- **Systeme / URL** : ABAP Platform Trial A4H (S/4HANA 1909, Docker),
  Gateway `http://localhost:50000`, launchpad `https://localhost:50001/sap/bc/ui2/flp?sap-client=001`,
  connexion SAP GUI `/H/vhcala4hci/S/3200`, client `001`, utilisateur `DEVELOPER`.
- **Preconditions** : donnees de demonstration EPM presentes (`SNWD_PD`,
  `SNWD_STOCK`, `SEPMRA_PO_MAN` peuples par le generateur standard) ; sortie
  SE16 en grille ALV (`Use ALV Grid In Data Browser`, persistant par
  utilisateur).
- **Nature** : campagne **d'ecriture non reversible et idempotente par
  construction** : chaque execution consomme une commande d'achat CONFIRMEE
  differente (statut `F`), jamais la meme deux fois (la reception fait
  passer son statut a `D`, ce qui l'exclut naturellement des executions
  suivantes). Aucune donnee n'est creee ni supprimee ; le test lit un stock
  AVANT, agit, relit APRES, et n'affirme que l'ecart mesure.

> **Statut : faits live releves le 2026-09-18 (A4H, client 001, session
> rf-mcp).** Les identifiants observes (numero de commande, produit, GUID
> technique) sont des observations **datees** de cette cible : la commande
> `300001960` a ete recue pendant le releve et ne sera plus jamais
> selectionnable (statut passe a `D`). Aucune de ces valeurs n'est une
> constante du produit ; la suite generee les redecouvre a chaque run.

## Pourquoi ce plan diverge de la demande initiale

La demande d'origine visait l'ouverture d'une application Fiori **« Manage
Purchase Orders »** pour creer une commande d'achat, puis un geste
**« Goods Receipt »** dans cette meme application. Deux faits, verifies EN
DIRECT et INDEPENDAMMENT l'un de l'autre, empechent de le faire tel quel sur
cette cible precise :

1. **Aucune tuile ni intent de gestion des commandes d'achat n'existe au
   launchpad de ce systeme.** Le catalogue complet assigne a `DEVELOPER`
   compte 62 intents uniques ; le seul portant sur les commandes d'achat est
   `EPMPurchaseOrder-approve` (« Approve Purchase Orders », consultation +
   approbation, **non reversible**, deja documente ailleurs dans ce depot).
   Quatorze intents plausibles (`EPMPurchaseOrder-manage`,
   `EPMPurchaseOrder-create`, `PurchaseOrder-manage`, `GoodsReceipt-post`...)
   ont ete soumis au service de resolution du shell
   (`Get Flp Intent Support`) : **aucun ne resout**, y compris pris
   individuellement hors catalogue assigne. Il n'existe donc pas
   d'application Fiori deployee sur cette cible pour creer une commande
   d'achat ni pour poster une reception de marchandise par l'interface.
2. **Le service OData qui porte cette logique metier existe et repond**
   (`/sap/opu/odata/sap/SEPMRA_PO_MAN`, entity sets `SEPMRA_C_PO_PurOrd` /
   `_PurOrdItem`, function imports `Activation`, `Approve`, `Copy`, `Edit`,
   **`Goodsreceipt`**, `Preparation`, `Quickapprove`, `Quickreject`,
   `Reject`, `Validation`), mais la creation d'un POSTE (produit + quantite)
   sur une commande brouillon fraichement creee echoue au niveau du serveur,
   sur **trois protocoles distincts** essayes en direct :
   - POST direct sur `SEPMRA_C_PO_PurOrdItem` (cle de la commande brouillon en
     corps) : `HTTP 500 ASSERTION_FAILED` (erreur runtime ABAP) ;
   - function import `SEPMRA_C_PO_PurOrdItemPreparation` (le mecanisme SADL
     cense preparer un nouveau poste) : `HTTP 400 /BOBF/FRW_COMMON/004
     "Action PREPARATION not possible; reference object does not exist"`,
     alors que la commande brouillon EST relisible (`GET` reussi juste avant) ;
   - `$batch` avec creation profonde (en-tete + poste dans le meme
     changeset, reference `$1/SEPMRA_C_PO_PurOrdItem`) : `HTTP 500 "unknown
     internal server error"`.
   Les trois echecs sont **cote serveur** (pas une erreur de validation
   client corrigible) : c'est une limitation demontree de ce service de
   demonstration quand il est pilote hors de son client SAPUI5 d'origine,
   pas un manque de la bibliotheque de ce depot. La creation de l'EN-TETE
   seule (`SEPMRA_C_PO_PurOrd`, sans poste) reussit sans probleme ; c'est
   uniquement l'ajout d'un POSTE (produit + quantite) sur une commande neuve
   qui bute.

**Consequence retenue** : la commande d'achat n'est pas creee par le test,
elle est **decouverte** parmi les commandes deja CONFIRMEES (statut `F`,
« Awaiting Approval » deja franchi) et non encore receptionnees
(`Goodsreceipt_ac=true`), exactement comme le ferait un utilisateur ouvrant
« Manage Purchase Orders » pour y traiter une commande existante. Le geste
metier reellement demande, « poster la reception de marchandise pour
declencher l'entree en stock », est integralement joue, sur le MEME objet
metier (`SEPMRA_C_PO_PurOrd` / fonction `Goodsreceipt`) qu'une application
Fiori appellerait si elle existait ici. Seule l'etape de CREATION change de
canal (decouverte au lieu de saisie), ce qui est documente et non dissimule.

## Donnees observees

### Catalogue Fiori (launchpad ABAP, DEVELOPER, client 001)

| Fait | Valeur observee |
|---|---|
| Intents catalogue uniques | 62 |
| Intents lies aux achats/stocks | `EPMPurchaseOrder-approve` (seul) |
| Intents candidats testes et non resolvables | `EPMPurchaseOrder-manage`, `-manage_st`, `-create`, `-track`, `-display`, `-postGR`, `-goodsreceipt`, `-receiveGoods`, `-post`, `PurchaseOrder-manage`, `PurchaseOrder-create`, `GoodsReceipt-post`, `GoodsReceipt-create`, `GoodsReceipt-manage` |

### Service OData `SEPMRA_PO_MAN` (v2, Gateway embarquee)

| Entity set | Cle | Champs utiles |
|---|---|---|
| `SEPMRA_C_PO_PurOrd` | `PurchaseOrder, DraftUUID, IsActiveEntity` | `Supplier`, `PurchaseOrderOverallStatus`, `Goodsreceipt_ac` |
| `SEPMRA_C_PO_PurOrdItem` | `PurchaseOrder, PurchaseOrderItem, DraftUUID, IsActiveEntity` | `Product`, `Quantity`, `QuantityUnit` |
| `SEPMRA_I_PurOrdOverallStatus` | `PurchaseOrderOverallStatus` | libelle (valeurs : `E` Draft, `P` Awaiting Approval, `F` Confirmed, `S` Sent, `A` Approved, `D` Delivered, `C` Completed, `I` Invoiced, `R`/`J` rejetee, `X` Cancelled) |

Statut retenu pour la decouverte : `F` (Confirmed, prete a recevoir). Sur les
50 premieres commandes actives echantillonnees, toutes etaient deja `C`
(Completed, `Goodsreceipt_ac=false`) : filtrer sur `F` est necessaire, un
echantillon non filtre ne suffit pas.

**Fonction `SEPMRA_C_PO_PurOrdGoodsreceipt`** : function import **NON liee**
(non navigable depuis l'entite, l'essai en chemin `.../PurOrd(cle)/Goodsreceipt`
echoue en 404 "Resource not found for the segment") : elle s'appelle en
service ROOT avec la cle de la commande en parametres nommes, cle active
(`DraftUUID=guid'00000000-0000-0000-0000-000000000000'`, `IsActiveEntity=true`
: le GUID nul est la convention SADL pour designer l'entite ACTIVE d'un
service a brouillons). Verifie live : `PurchaseOrderOverallStatus` passe de
`F` a `D` (Delivered).

### Tables SE16

| Table | Colonnes utiles | Piege |
|---|---|---|
| `SNWD_PD` (produits, 205 lignes) | `PRODUCT_ID` (cle metier), `NODE_KEY` (GUID technique) | `Get Se16 Selection Criteria` echoue sur cet ecran (voir Points de vigilance) : lecture par grille complete + filtre par contenu, jamais par critere de selection derive |
| `SNWD_STOCK` (2665 lignes) | `PRODUCT_GUID` (= `SNWD_PD.NODE_KEY`), `ORG_UNIT_GUID`, `BIN_NUMBER`, `QUANTITY`, `QUANTITY_UNIT` | **PAS de colonne produit lisible** : jointure obligatoire par `SNWD_PD.NODE_KEY` ; **plusieurs lignes par produit** (un magasin/bac par `ORG_UNIT_GUID`), le stock d'un produit est la SOMME de ses lignes, jamais une seule cellule |

## Preuve live du cycle complet (2026-09-18)

| Etape | Mesure |
|---|---|
| Commande confirmee trouvee | `300001960`, fournisseur `100000012`, statut `F` |
| Poste choisi | `10`, produit `EP-E-1003`, quantite `14 EA` |
| GUID produit (`SNWD_PD.NODE_KEY`) | `0A71E5D7E6551EEAA8AD4173D2FA3E5E` |
| Stock total AVANT (13 lignes `SNWD_STOCK`) | **1132 EA** |
| Reception postee (`SEPMRA_C_PO_PurOrdGoodsreceipt`) | statut commande `F` -> `D` |
| Stock total APRES (13 lignes, meme jeu) | **1146 EA** = 1132 + 14 |
| Ligne modifiee | bin `0200001589` : 85 -> 99 EA (+14, exactement la quantite du poste) |

L'egalite `1146 = 1132 + 14` est exacte : l'invariant metier est prouve, sur
le canal API pour l'ecriture et sur SE16 pour la lecture independante.

## Scenarios

### 1. Trouver une commande d'achat confirmee et lire le stock initial

- **Etapes** :
  1. `Get Odata Entities SEPMRA_C_PO_PurOrd filter=IsActiveEntity eq true and
     PurchaseOrderOverallStatus eq 'F'` (top borne, ex. 20) ; sans resultat,
     le scenario est **saute proprement** (jamais d'echec, jamais de commande
     fabriquee : voir Invariant).
  2. Lire le PREMIER poste actif de cette commande
     (`SEPMRA_C_PO_PurOrdItem filter=PurchaseOrder eq '<numero>' and
     IsActiveEntity eq true`) : produit et quantite.
  3. Resoudre le GUID du produit dans `SNWD_PD` (lecture complete filtree par
     contenu, `PRODUCT_ID` -> `NODE_KEY`).
  4. Lire le stock total actuel du produit dans `SNWD_STOCK` (somme de toutes
     les lignes dont `PRODUCT_GUID` correspond, comparaison insensible a la
     casse et aux tirets du GUID).
- **Resultat attendu** : une commande, un poste (produit + quantite non
  vides), un stock initial mesure (entier >= 0).

### 2. Poster la reception de marchandise

- **Etapes** : appeler `SEPMRA_C_PO_PurOrdGoodsreceipt` (fonction non liee,
  cle active de la commande trouvee au scenario 1).
- **Resultat attendu** : la commande passe au statut `D` (Delivered).
  Jugement par CODE (convention 3), jamais par un texte localise.

### 3. Verifier l'incrementation exacte du stock physique

- **Etapes** : relire le stock total du meme produit dans `SNWD_STOCK`.
- **Resultat attendu** : `stock_apres == stock_avant + quantite_du_poste`,
  une egalite EXACTE (pas seulement une augmentation). C'est l'assertion
  dynamique demandee : jamais une valeur absolue supposee, toujours l'ecart
  mesure sur SA PROPRE execution.

## Invariant metier et idempotence

**Invariant** : la reception de marchandise d'un poste de commande d'achat
EPM incremente le stock physique du produit concerne EXACTEMENT de la
quantite du poste, verifiee par un canal independant de celui qui a ecrit.

**Pourquoi la suite est rejouable sans etat partage** : chaque execution
DECOUVRE sa propre commande (jamais un numero fige), et la reception rend
cette commande INELIGIBLE aux executions suivantes (statut `F` -> `D`) : deux
executions, meme simultanees, ne peuvent pas cibler la meme commande deux
fois. Aucune ecriture n'a lieu sur `SNWD_PD` ni sur le catalogue de
commandes : seul le stock du produit traite change, de facon monotone et
mesuree.

**Limite assumee, non reversible** : contrairement aux campagnes
d'ecriture-lecture de ce depot qui prouvent un retour a l'etat initial
(suppression, extourne), la reception de marchandise n'a pas de geste
inverse dans ce modele de demonstration (comme `Approve`/`Reject`, deja
documentes non reversibles ailleurs dans ce depot). Le stock EPM croit donc
d'une execution a l'autre ; ce qui reste vrai a chaque fois est l'ECART
mesure, jamais un total absolu. Le nombre de commandes confirmees
disponibles est fini : une fois epuise, le scenario 1 saute proprement
plutot que d'echouer ou d'en fabriquer une (voir la section precedente sur
la creation bloquee).

**Accord d'ecriture explicite** : une reception de marchandise consomme une
ressource reelle et FINIE (une commande confirmee) de facon non reversible,
sur un systeme partage. Suivant la convention deja etablie par les autres
campagnes d'ecriture de ce depot (`WRITE_SIMULATION_OPT_IN`,
`ABAP_FLP_WRITE_OPT_IN`), le tag `write` seul ne suffit pas : la suite exige
`-v PROCURE_TO_PAY_WRITE_OPT_IN:yes`, sans quoi tous ses tests sont SAUTES
avant meme l'ouverture d'un canal.

## Points de vigilance

- **`Get Se16 Selection Criteria` et `Read Ddic Table Fields` echouent sur les
  ecrans de selection de `SNWD_PD` et `SNWD_STOCK`** (erreur "no technical
  selection criterion found on the current screen" alors que
  `Get Screen Signature` confirme le bon ecran atteint). Cause non
  investiguee ici (hors perimetre de cette mission) : contournement retenu,
  lecture de la grille COMPLETE (compteur de hits releve haut,
  `Read Full Grid`) puis filtrage par CONTENU, jamais par un critere de
  selection derive. A signaler separement comme piste d'amelioration de la
  bibliotheque.
  **Cause isolee le 2026-09-21** : le releve du 18 tournait par RDP depuis
  un autre poste, dont l'ecran dense rendait SAP GUI a l'echelle du client
  (captures 4676x2550 pour un bureau 1920x1080) ; l'API Scripting rend la
  geometrie en pixels physiques et le moteur de localisateurs humains
  raisonnait en pixels fixes (ecart libelle -> critere de 25 px pour un
  plafond de 30), donc plus aucun libelle ne se rattachait. Corrige dans la
  bibliotheque (`sapfx_common.semantic`, tolerances portees a l'echelle
  mesuree sur l'ecran). Rejouee sur le poste, la suite passe 3/3 telle
  quelle (36 s) : le contournement par grille complete est conserve, valide
  live, et n'est plus une necessite.
- **`SNWD_STOCK` n'a pas de colonne produit lisible directement** : toute
  lecture doit joindre `SNWD_PD.NODE_KEY` prealablement, sous peine de ne
  filtrer sur rien.
- **Un produit a PLUSIEURS lignes de stock** (un magasin/bac par ligne) :
  sommer, jamais lire une seule ligne.
- **Les fonctions `SEPMRA_C_PO_Pur...` ne sont PAS liées à l'entité** :
  toujours les appeler en chemin de service ROOT avec les champs de cle en
  parametres nommes, jamais en navigation `.../PurOrd(cle)/Fonction`.
- **`DraftUUID` d'une entite ACTIVE est le GUID nul**
  (`00000000-0000-0000-0000-000000000000`), convention SADL a connaitre pour
  toute cle composite d'un service a brouillons de ce type.
- **Un GET nu pour obtenir le jeton CSRF peut echouer sur une fonction non
  liee dont les parametres sont obligatoires**, mesure live en assemblant la
  suite : `Call Odata Function` sondait le jeton par un GET sans parametre
  sur `SEPMRA_C_PO_PurOrdGoodsreceipt` elle-meme (faute de jeton deja en
  cache), et le serveur refusait ce GET (`Invalid Function Import
  Parameter 'PurchaseOrder'`) avant meme de tenter le POST reel. Capacite
  desormais promue dans la bibliotheque (`Call Odata Function` accepte
  `csrf_fetch_path`, le meme mecanisme que `Post Odata Batch` utilise deja
  en interne pour `$batch`) : la commande de reception passe
  `csrf_fetch_path=<service>/` (un GET nu sur la racine du service reussit
  toujours).
- **Un produit reference par une commande d'achat n'a pas forcement de
  ligne dans `SNWD_STOCK`** : mesure live (produit `PP-SN-1002`, un des
  runs de la suite), une absence de ligne est un stock de zero, jamais un
  echec de lecture.
