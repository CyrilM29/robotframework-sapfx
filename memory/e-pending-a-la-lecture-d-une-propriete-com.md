---
name: e-pending-a-la-lecture-d-une-propriete-com
description: 2026-09-12, pendant un aller-retour serveur SAP GUI lève E_PENDING sur la LECTURE d'une propriété COM (node.Children), avant tout Count, donc tout code qui sonde l'arbre en continu traverse cet état ; le recorder bureau gardait Count et ElementAt mais pas la propriété elle-même et mourait en traceback brut au milieu d'un enregistrement
metadata:
  type: project
---

Un accès d'attribut sur un proxy COM SAP GUI n'est pas une lecture de champ,
c'est une opération réseau. Pendant un aller-retour serveur, la lecture de
`node.Children` lève :

```
com_error (-2147483638, 'Les données nécessaires pour terminer cette
opération ne sont pas encore disponibles.')
```

soit `E_PENDING` (0x8000000A), AVANT tout appel à `Count` ou `ElementAt`.

**Relevé le 2026-09-12** en utilisant le recorder bureau pour de vrai contre
A4H (parcours SE16 enregistré pendant qu'un script le déroulait). Les deux
parcours d'arbre de `tools/recorder/recorder_com.py` gardaient `Count` et
`ElementAt` contre `com_error` mais lisaient `Children` à nu. Le mode record
sonde en continu, donc il traverse forcément l'état transitoire d'une
transition d'écran : la boucle est morte en traceback brut, avec **zéro étape
sauvée**, sur un parcours par ailleurs sain.

**Pourquoi ça se cache :** le test unitaire existant couvrait déjà le cas
« `Count` lève », ce qui donne l'illusion d'un parcours défensif, et le smoke
live passait parce qu'il sonde à des instants CHOISIS, après une attente de
fin de busy. Seul un usage réel, où le sondage est continu et la transition
subie, met le poste dans cet état. C'est la différence entre exercer une
fonction et s'en servir.

**Comment appliquer :** sur un proxy COM SAP GUI, garder l'ACCÈS lui-même,
pas seulement ce qu'on en tire (ici un helper `_children` sur le modèle du
`_safe` voisin). Et dans une boucle de sondage, un cycle manqué se rattrape
au suivant : ne jamais laisser une exception transitoire tuer la boucle, car
ce qui est perdu n'est pas le cycle mais tout le travail accumulé. Voir aussi
[[cles-de-noeud-completees-a-gauche]], l'autre `com_error` opaque dont la
cause n'est pas celle qu'on croit, et
[[piloter-les-recorders-dans-un-test]] pour les pièges de harnais du même
exercice.
