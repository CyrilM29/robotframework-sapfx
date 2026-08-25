# Cliquer une ligne déjà sélectionnée ne navigue pas

**2026-08-24, parcours applicatif live dans une application de launchpad.** Une
suite ouvrait « le premier produit de la première catégorie » à chaque test.
Le premier test passait, les suivants échouaient, et l'échec accusait un
innocent :

```
Could not click ... //Page[@id='...product--page']//Toolbar//Button
  - element is not visible
```

Le bouton d'ajout au panier n'était pas visible parce que la FICHE PRODUIT
n'était pas ouverte. Le clic sur la ligne, lui, avait « réussi » : il n'avait
simplement rien déclenché. Une `sap.m.List` en mode sélection n'émet pas
d'événement quand la sélection ne CHANGE pas, et la ligne était restée
sélectionnée depuis le test précédent.

**Pourquoi :** un clic qui aboutit et une navigation qui a lieu sont deux
choses différentes. Un mot-clé qui rend la main après le clic laisse donc le
scénario continuer dans un état qu'il croit atteint, et l'échec surgit là où le
localisateur suivant est parfaitement correct. Le diagnostic Fiori de la suite a
tranché en une lecture : le snapshot ARIA ne montrait qu'une seule colonne, celle
de la catégorie, avec la ligne marquée « Sélectionné ».

**Même famille, relevé le même jour :** un bouton BASCULE. La colonne du panier
s'ouvrait et se fermait par le même `sap.m.ToggleButton`, et le mot-clé
« ouvrir » se contentait de cliquer. Le pari sur l'état courant se perd dès
qu'une navigation a refermé la colonne entre-temps : le scénario continue en
croyant le panier ouvert, et l'échec tombe sur le bouton suivant. Un mot-clé
métier exprime un ÉTAT VOULU (ouvrir, fermer) et reste idempotent ; le geste
brut reste interne.

**Comment appliquer :** deux gestes, complémentaires. Choisir une cible NON
sélectionnée quand c'est possible (la propriété `selected` se lit au registre,
voir [[lire-la-propriete-plutot-que-le-rendu]]). Et surtout, faire vérifier au
mot-clé d'ouverture que la destination est bien à l'écran ET porte le bon
contenu, avant de rendre la main. La règle générale : un mot-clé de navigation
constate son arrivée, il ne la suppose pas.
