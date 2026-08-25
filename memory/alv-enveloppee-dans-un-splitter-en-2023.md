# Sur ABAP 2023, la grille ALV n'est plus au bout du chemin de shell habituel

**2026-08-23, première exécution des suites du dépôt contre un second système**
(ABAP Platform 2023, à côté de l'A4H 1909 qui sert de référence depuis des mois).
Le smoke ECC passe 4/5 : login, navigation, SE16 sur T000 et transaction
inconnue sont verts. Le seul échec est une lecture de grille :

```
AttributeError: <unknown>.rowCount
ValueError: Element 'wnd[0]/usr/cntlGRID1/shellcont/shell' is not an ALV
            GridView (no ColumnOrder).
```

Ce chemin, `wnd[0]/usr/cntlGRID1/shellcont/shell`, désigne bien la grille ALV
sur le 1909. Sur le 2023 il désigne un **`GuiSplitterShell`**, et la grille est
plus bas. La perception des deux écrans le montre :

```
SE16                                                       type
  cntlGRID1/shellcont/shell                                GuiSplitterShell
  cntlGRID1/shellcont/shell/shellcont[1]/shell             GridViewCtrl.1   <- grille

SM50
  cntlGRID1/shellcont/shell                                GuiSplitterShell
  cntlGRID1/shellcont/shell/shellcont[0]/shell             SAP.HTMLControl.1
  cntlGRID1/shellcont/shell/shellcont[1]/shell             GuiSplitterShell
  cntlGRID1/shellcont/shell/shellcont[1]/shell/shellcont[1]/shell   GridViewCtrl.1
```

**La profondeur varie selon la transaction** : un niveau de splitter pour SE16,
deux pour SM50, qui ajoute un panneau HTML d'en-tête. Il n'existe donc pas de
suffixe fixe à concaténer au chemin historique.

**Pourquoi :** un chemin de shell écrit en dur encode la MISE EN PAGE d'un
écran, pas l'identité du contrôle qu'on veut atteindre. Tant qu'on ne teste que
sur une release, l'hypothèse tient et reste invisible. Elle casse à la première
release qui enveloppe l'ALV autrement, et elle casse pour TOUTES les lectures de
grille à la fois, puisque la couche resource partage ce chemin : `Read Grid`,
`Display Table Contents`, les campagnes DDIC et de croisement en dépendent
toutes. À noter, l'échec n'est pas seulement bruyant : la vérification
« les données de démonstration existent-elles » a échoué alors que les données
étaient bel et bien présentes (comptées directement dans HANA : SFLIGHT 107,
SNWD_PD 205), parce que son contrôle passe par une lecture de grille. Un
localisateur faux se déguise en diagnostic métier faux.

**Comment appliquer :** ne pas rustiner en ajoutant un suffixe, la profondeur
n'étant pas constante.

**CORRIGÉ le 2026-08-23**, sur demande explicite, en adressant l'IDENTITÉ du
contrôle plutôt que la mise en page : `_grid()` descend jusqu'au premier
descendant portant `ColumnOrder` (parcours en largeur borné à 6 niveaux), et la
descente est journalisée en WARNING, jamais silencieuse, comme l'auto-réparation
de localisateurs. Un détail a coûté un aller-retour : les primitives de grille
héritées du code VENDORISÉ (`Get Row Count`, `Get Cell Value`, `Set Cell Value`,
`Click Toolbar Button`, `Select Table Row`) appellent `findById` en direct et ne
passent donc pas par `_grid()` : la première correction laissait `Get Row Count`
en échec. Elles sont surchargées dans le mixin (convention 4 : le fichier amont
reste intact), chacune en une ligne qui résout l'identifiant puis délègue.

Le résolveur rend l'identifiant INCHANGÉ quand le chemin porte déjà la grille,
ou quand rien de grillé n'existe en dessous (un GuiTableControl) : mesuré, aucun
WARNING de descente sur le 1909, donc zéro changement de comportement là où le
localisateur est juste. Validation : `ecc_smoke` et `ecc_data_smoke` verts sur
les DEUX releases (5/5 et 4/4 de chaque côté).
Voir aussi [[se16-ecran-selection-genere-premier-acces]].
