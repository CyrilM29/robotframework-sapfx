# La correspondance entity set / table ne se déduit ni du nom, ni du compte

**2026-08-22, campagne de croisement ECC ↔ API.** Croiser un comptage SE16
avec un `$count` OData suppose de savoir quelle table porte quel entity set.
Deux tentations existent pour l'établir sans travail : le nom, et l'égalité des
comptes. Les deux fabriquent des faux.

## Le `$metadata` ne nomme jamais la table source

Inventaire des attributs `sap:` de deux services réels : aucun ne désigne un
objet du dictionnaire. La correspondance n'est donc pas une donnée observable
du canal API. Elle est une **donnée de configuration**, nommée métier, et
chaque couple doit être prouvé par le test (les deux comptages exécutés et
confrontés), jamais supposé. Un entity set sans couple déclaré se rapporte, il
ne s'apparie pas en silence.

## Le contre-exemple qui tranche

Sur la cible mesurée, une table au nom apparemment évident (« …_CONTACT »)
existe bel et bien, est transparente, s'ouvre normalement dans le Data Browser
et contient **0 entrée**. L'entity set homonyme en compte 41 et repose en
réalité sur une **autre** table, au nom plus long. Une correspondance déduite
du nom aurait produit un échec de test sur une table parfaitement saine, et
envoyé chercher une régression inexistante.

## Trois inégalités LÉGITIMES, à ne pas prendre pour des écarts

Relevées live, chacune avec sa cause établie plutôt que supposée :

1. **Entity set draft-enabled** : le `$count` nu agrège entités actives ET
   brouillons. Mesuré 214 nu, 205 sous filtre d'activité vraie, 9 sous
   activité fausse : l'arithmétique boucle. L'égalité avec une table n'a de
   sens que sous le filtre d'activité.
2. **Projection filtrée du service** : une vue de consommation ne projette
   qu'un sous-ensemble métier de sa table (ici un rôle de partenaire). Le
   filtre a été établi en LISANT les valeurs réellement présentes dans la
   colonne, puis en rejouant le comptage filtré, pas en le devinant.
3. **Périmètre lié à l'utilisateur ou à la session** (paniers, éléments de
   panier) : aucune égalité stable n'est attendue, le couple se déclare non
   comparable.

## Deux prérequis structurels du croisement

- **Le même mandant des deux côtés.** Le comptage écran se fait dans le
  mandant de connexion GUI, le `$count` dans celui du canal API. Les faire
  diverger compare deux populations et fabrique un écart qui n'existe pas :
  le préflight doit refuser, pas avertir.
- **La carte des critères d'écran de sélection se dérive, jamais ne s'écrit.**
  Mesuré sur une table du dictionnaire : 31 critères réels là où une carte de
  mémoire en supposait 17. Voir [[se16-ecran-selection-champs-omis]].

Fait voisin, même campagne : [[annotation-odata-declaree-non-permissive]].
