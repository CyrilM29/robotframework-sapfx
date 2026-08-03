---
name: run-transaction-tcodes-parametres
description: Run Transaction — faux négatif sur les tcodes paramétrés (IMG, alias) dont sy-tcode diffère du code saisi
type: projet
date: 2026-08-02
---

Constaté live le 2026-08-02 (SAP GUI 8.00, A4H, client 000) en exécutant
l'activité IMG « Activate or Deactivate SAP Gateway ».

**`Run Transaction` peut échouer en FAUX NÉGATIF alors que la transaction a
bien démarré** : son contrôle locale-safe compare `Info.Transaction`
(sy-tcode) au code saisi. Or certains tcodes sont des **transactions
paramétrées** dont le sy-tcode effectif est un autre code — cas typique : les
tcodes IMG générés (`SAPLS_CUS_IMG_ACTIVITY`). Exemple vécu :
`Run Transaction    /n/IWFND/50000003` → erreur
`Transaction '/n/IWFND/50000003' did not start (active='/IWFND/IWF_ACTIVATE')`
alors que le dialogue d'activation était ouvert et fonctionnel.

Réflexe : quand `Run Transaction` échoue avec `active='<autre tcode>'` NON
vide et différent de l'ancien écran, la transaction a probablement démarré
sous son nom interne — **percevoir l'écran** (`Get Screen Map`,
`Get Open Windows`) avant de conclure à un échec, ou lancer via
`Send Command` sans assertion puis vérifier par perception.

Au passage, la correspondance activité IMG → tcode généré se retrouve par
SE16 sur **`CUS_IMGACH`** (champ de sélection `ACTIVITY`, colonne `TCODE`).

Voir aussi [[a4h-se16-write-delete]] pour d'autres pièges SE16 relevés live.
