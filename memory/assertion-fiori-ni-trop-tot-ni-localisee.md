---
name: assertion-fiori-ni-trop-tot-ni-localisee
description: Une assertion Fiori ne s'appuie ni sur un écran pas encore peuplé (le rendu n'est pas la donnée) ni sur un texte localisé (l'app suit la locale du navigateur)
type: projet
date: 2026-08-10
---

Constaté live le 2026-08-10 en validant `Wait For Ui5 Idle` contre la List
Report cap-sflight (Fiori Elements v4).

**1. « Rendu » ne veut pas dire « données arrivées ».** Après un Go de
FilterBar, un tri ou une navigation, la vue existe déjà pendant que l'OData
voyage encore : asserter à ce moment lit l'écran d'AVANT.
`Wait For Ui5 Idle` attend le repos RÉEL (requêtes XHR/fetch en vol,
instrumentées à l'injection du bundle, plus les indicateurs busy, plus un
calme continu `settle`).

**Portée exacte, apprise en se trompant** : il attend les requêtes DÉJÀ
parties, il ne devine pas celles à venir. Au tout PREMIER chargement d'une
app, il peut donc rendre la main avant que la vue n'ait lancé son
`initialLoad` : un premier rendu s'attend par une condition d'application
(`Ui5 Control Should Be Visible`, ou la résolution qui sonde déjà le rendu).
C'est APRÈS une action, quand la vue est là et que seules les données
manquent, qu'il est décisif.

**2. L'app suit la locale du NAVIGATEUR.** La même List Report affiche
« Lancer » là où la documentation dit « Go », et ses en-têtes de colonnes
sont traduits (`Agence`, `Prix total`). Un localisateur ou une assertion
assis sur ce texte casse au premier changement de langue, y compris sur le
poste d'à côté. Cibler l'**id Fiori Elements stable**
(`idSuffix=fe::FilterBar::Travel-btnSearch`) et, pour lire une table,
comparer un contenu de données plutôt qu'un nom de colonne traduit. C'est la
convention n°3 appliquée au canal web ; côté messages applicatifs, son
équivalent est `Ui5 Should Have No Messages Of Type` (on juge le TYPE, le
texte n'est là que pour le lecteur humain).

Harnais qui garde ces deux leçons : `tests/robot/fiori_idle_messages_smoke.robot`.
