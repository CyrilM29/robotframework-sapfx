---
name: a4h-se16-write-delete
description: A4H, SE16 permet Create/Change/Delete en place (DEVELOPER) ; pièges de navigation relevés live
type: projet
date: 2026-07-17
---

Découvert live le 2026-07-17 sur l'A4H (SAP GUI 8.00, client 001, DEVELOPER)
pendant une campagne d'écriture sur SCARR.

**SE16 n'est PAS en lecture seule sur cet A4H.** Avec DEVELOPER (autorisations
complètes), l'écran RÉSULTAT SE16 expose un menu « Table Entry » avec
**Create / Change / Delete / Delete all** : cycle CRUD complet sans SE16N
(absent) ni SM30.

Chemins relevés live (grille ALV activée au préalable) :
- **Créer** : depuis l'écran **INITIAL** de SE16 (table saisie, PAS d'Entrée),
  `Table > Create Entries` = `wnd[0]/mbar/menu[0]/menu[1]` → écran
  mono-enregistrement (`ctxtSCARR-CARRID`…) → `Send Vkey 11` (Save) → statut S
  « Database record successfully created ». ⚠️ Sur l'écran de **sélection**
  (après Entrée), `menu[0]/menu[1]` = « Execute and Print » → ouvre le dialogue
  d'impression `SAPLSPRI/PRI_PARAMS` (bug attrapé en run live).
- **Supprimer** : depuis la grille de résultats filtrée sur la clé,
  `Edit > Select All` (`menu[1]/menu[0]`) puis `Table Entry > Delete`
  (`menu[0]/menu[6]` ; ⚠️ `menu[5]` = « Delete all ») → écran « Table … Delete »
  (`/SE16/101`) → bouton **Delete Entry** `wnd[0]/tbar[1]/btn[14]` → statut S
  « Database record deleted » (commit immédiat, pas de Vkey 11).

**SM30 pour SCARR échoue** : « The maintenance dialog for SCARR is incomplete
or not defined » (pas de dialogue de maintenance généré).

Compte via « Number of Entries » (`tbar[1]/btn[31]`, popup
`wnd[1]/usr/txtG_DBCOUNT`) : valeurs avec **séparateur de milliers `.`**
(ex. `28.782`) → filtrer `isdigit`.

Exemple ré-exécutable complet (create→verify→delete) :
`tests/robot/exploratory_campaign_a4h.robot`. Voir aussi les field notes A4H
de CLAUDE.md.
