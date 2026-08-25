# Le texte rendu d'un contrôle n'est pas sa valeur

**2026-08-24, campagnes live sur un launchpad Work Zone.** Lire les noms d'une
liste par le texte visible a produit deux échecs de nature différente, dans la
même après-midi, et les deux ressemblaient à une dérive de localisateur.

**Premier cas, le rendu ajoute ce que le contrôle dessine.** Un
`sap.m.StandardListItem` de catalogue affiche son compteur de produits sous le
titre. Le texte visible vaut donc :

```
Accessories\n34        alors que la propriété title vaut "Accessories"
```

Réinjecté dans un localisateur, ce nom échoue deux fois : aucun titre ne lui
correspond, et le saut de ligne casse le littéral de dictionnaire passé en
`properties=`.

**Second cas, un contrôle rendu n'est pas forcément visible.** Quand un
`sap.f.FlexibleColumnLayout` replie une colonne, ses contrôles restent dans le
registre UI5, donc parfaitement RÉSOLUS, mais la lecture de leur texte attend
une visibilité qui ne viendra pas et expire au bout de dix secondes. Le message
parle d'un élément introuvable ou d'une expiration : il ne dit pas que la
colonne est repliée.

**Pourquoi :** lire le rendu, c'est interroger le navigateur sur ce qu'il
AFFICHE. La question posée est donc plus large que la question voulue, et elle
impose une condition (l'affichage) dont l'assertion n'a pas besoin.

**Comment appliquer :** lire la PROPRIÉTÉ du contrôle. `Get Ui5 Property` et
`Get Ui5 Properties` (ajoutés à `SapFioriLibrary` ce jour-là) lisent au
registre : valeur exacte, indépendante de la visibilité, et une liste entière de
titres en un seul appel. Une propriété inexistante échoue en listant les
propriétés disponibles, plutôt que de rendre une liste de `None` dont l'échec
tomberait deux étapes plus loin. `Get Ui5 Text` reste le bon outil quand la
question EST « qu'est-ce que l'utilisateur voit », par exemple pour un total
formaté. Voir aussi [[assertion-fiori-ni-trop-tot-ni-localisee]].
