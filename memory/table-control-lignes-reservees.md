---
name: table-control-lignes-reservees
description: GuiTableControl, RowCount compte les lignes RÉSERVÉES et la scrollbar plafonne à total moins visible, deux pièges qui cassent une lecture naïve
type: projet
date: 2026-08-10
---

Mesuré live le 2026-08-10 (SAP GUI 8.00, A4H) sur SE11 affichant la table
`SNWD_PD` : `RowCount = 47`, `VisibleRowCount = 22`, `Columns.Count = 10`,
`VerticalScrollbar.Maximum = 25`.

**Piège 1 : `RowCount` compte les lignes RÉSERVÉES par l'écran, pas les
lignes remplies.** Ici 47 annoncées pour **26** réellement porteuses de
données. Au-delà, AUCUNE cellule n'est matérialisée : `GetCell` lève un
`com_error` « The method got an invalid argument » plutôt que de retourner
du vide. Une boucle dimensionnée sur `RowCount` produit donc soit un crash,
soit des lignes fantômes.

**Piège 2 : la scrollbar plafonne à `total - visible`** (25, pas 47).
Demander une position au-delà lève aussi un `com_error`. Conséquence non
évidente : la DERNIÈRE fenêtre chevauche la précédente et doit être lue à
partir d'un index local décalé, sinon les lignes de fin sont lues deux fois
et les vraies dernières jamais.

Ce que le code en a tiré (`sapfx_common.table_control` + `keywords/_grid.py`) :
`window_plan(total, visible)` produit un plan
`(position, index local de départ, nombre de lignes)` couvrant chaque ligne
exactement une fois et borné à la limite réelle ; `Read Table Control`
s'arrête à la première ligne dont aucune cellule n'existe et retourne les
lignes réellement remplies ; `Get Table Control Cell` sur une ligne réservée
échoue en NOMMANT le piège. Le tout verrouillé par des tests unitaires dont
le cas 47/22/26 exact.

Deux remarques d'environnement du même run : **FB60 n'existe pas sur A4H**
(« Transaction FB60 does not exist », comme SE16N : le trial n'embarque pas
les transactions FI), donc la cible de référence pour un vrai table control
est SE11 ; et un `GuiTableControl` se distingue d'une grille ALV par
l'absence de `ColumnOrder` (les keywords redirigent dans les deux sens).

Voir aussi [[a4h-se16-write-delete]] et [[run-transaction-tcodes-parametres]]
pour les autres pièges A4H relevés live.
