# Une ALV non défilée se lit VIDE, sans jamais lever

**Date** : 2026-09-15. **Cibles** : rapport RSPARAM lu sur deux releases ABAP
(754 et 758) par la même suite d'extraction.

## Le fait

La même lecture de grille a rendu :

- **1635 lignes, toutes remplies** sur la 758 ;
- **1639 lignes, dont 137 remplies** sur la 754.

Aucune erreur, aucun avertissement. Une ALV ne matérialise ses lignes qu'au fil
du **défilement**, et une lecture portant sur des lignes non chargées rend des
cellules **vides** au lieu d'échouer.

## Pourquoi aucune garde ne l'a vu

L'extraction était contrôlée, et chaque contrôle passait :

- le nombre de lignes lues égalait celui que la grille DÉCLARE (1639 = 1639) ;
- le fichier écrit, relu, correspondait exactement au relevé ;
- les colonnes attendues étaient toutes présentes.

Tout était cohérent parce que tout raisonnait sur des **lignes**, jamais sur
leur **contenu**. Un relevé creux est cohérent avec lui-même : il se relit, se
compare et se sérialise parfaitement.

C'est le cas d'école du résultat vert et faux, et il n'était visible qu'en
changeant de cible : sur la release où la grille charge tout, la lecture était
réellement complète.

## Ce qu'on en a fait

- `Read Full Grid` (qui défile avant de lire) remplace `Read Grid` partout où
  l'objet est d'extraire.
- Un keyword de bibliothèque compte les lignes **entièrement vides** d'un
  relevé, et la suite refuse d'écrire quand il y en a. Les deux sont
  complémentaires : le premier agit, le second constate que l'action a suffi.
- Après correction : 1639/1639 sur la 754, 1635/1635 sur la 758.

## La leçon de méthode

Une garde de complétude qui compte des lignes ne mesure pas la complétude. La
question à poser est « qu'est-ce qui serait encore vrai si la lecture avait
échoué à moitié », et ici la réponse était : tout.

Corollaire sur le même run : une garde de CIBLE qui rougit dans un scénario
n'empêche rien, les scénarios suivants écrivant leurs fichiers quand même
(quatre fichiers du mauvais système, nommés d'après le bon). Une garde doit
vivre là où elle bloque, donc dans le Suite Setup, et les noms de fichiers
doivent dériver de l'identité MESURÉE.

Voir aussi [[extraire-un-tableau-sap-n-est-pas-l-asserter]].
