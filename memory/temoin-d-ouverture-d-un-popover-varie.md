---
name: temoin-d-ouverture-d-un-popover-varie
description: 2026-08-30, le témoin « le popover est ouvert » n'est pas portable d'une cible à l'autre : en SAPUI5 1.151 le popover n'expose AUCUNE propriété open (le témoin est la pile de popups), une entrée de menu FERMÉ compte encore 1 correspondance au registre, et le menu se déclare non rendu pendant que son popover s'affiche
metadata:
  type: project
---

Sur le Demo Kit OpenUI5 (SAPUI5 1.151), trois mesures qui démontent chacune un
réflexe :

- `sap.m.Popover` n'a **pas** de propriété `open`. Le réflexe hérité du shell
  Work Zone, où l'ouverture du menu utilisateur se constate justement sur cette
  propriété, ne s'applique pas ici : le témoin est la **pile de popups**
  ouverts, dont la profondeur croît et décroît le long d'une cascade.
- Menu FERMÉ, l'entrée de thème compte encore **1** correspondance au registre,
  avec un rectangle nul. Compter les entrées ne prouve donc rien.
- Le `sap.m.Menu` se déclare `rendered=False` **pendant** que son popover
  s'affiche : l'objet interrogé n'est pas celui qui est à l'écran.

**Pourquoi :** « ouvert » n'est pas une propriété du modèle, c'est un état de
rendu, et chaque famille de contrôles (et chaque version) le matérialise
ailleurs : une propriété sur les uns, une entrée dans un registre de popups sur
les autres, une surface non nulle en dernier ressort. Une leçon de cible A
transposée telle quelle sur la cible B produit une assertion qui passe pour de
mauvaises raisons, ou qui interroge un objet fantôme.

**Comment appliquer :** établir le témoin d'ouverture SUR LA CIBLE avant
d'écrire le scénario, et le nommer dans le page object. Ordre de préférence :
la pile de popups (elle dit ce qui est réellement affiché), puis la surface non
nulle du contenu visé, jamais la seule présence au registre. Même famille que
[[recherche-shell-flp-171-deux-clics]] (le témoin est la SURFACE, pas la
présence) et [[lire-la-propriete-plutot-que-le-rendu]] (savoir ce qu'on lit).
Divergence notable avec la mémoire QA partagée, tranchée par la mesure du jour :
la leçon Work Zone « poser la valeur d'un champ n'ouvre pas les suggestions »
est FAUSSE sur cette cible, où elle les ouvre. Le live tranche, toujours.
