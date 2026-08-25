# Une clé de nœud d'arbre SAP GUI est complétée à gauche

**2026-08-23, activation du service ICF `webgui` par SICF.** L'arbre des
services est un `SAP.TableTreeControl.1`. `GetAllNodeKeys()` rend onze clés,
qui s'affichent comme des numéros. Trois tentatives de sélection ont échoué de
suite :

```
Select Node   <arbre>  11              -> Property '<unknown>.selectedNode' can not be set
SelectItem("11", "&Hierarchy")         -> com_error (-2147352567) sans message utile
SelectedNode = "11"                    -> idem
```

En affichant les clés avec `repr()` plutôt qu'en les journalisant telles
quelles, la cause apparaît : ce ne sont pas des nombres mais des **chaînes
complétées à gauche sur onze caractères**.

```
'          1' -> 'default_host'
'         11' -> 'webgui'
```

Avec la clé exacte, `SelectedNode = '         11'` fonctionne du premier coup.
Le keyword amont `Select Node` marche donc parfaitement : il faut simplement lui
passer la clé telle que l'arbre la rend, sans la « nettoyer ».

**Le second piège du même écran :** trois nœuds portent le texte `webgui`
(`/sap/bc/echo/webgui`, `/sap/bc/error/webgui`, et
`/sap/bc/gui/sap/its/webgui`). Activer le mauvais aurait été parfaitement
silencieux, avec un message de succès. L'identification passe donc par le
CHEMIN reconstruit en remontant les sous-nœuds (`GetSubNodesCol`), jamais par le
numéro ni par le texte. À noter, `GetParent` n'existe pas sur ce type d'arbre :
la filiation se reconstruit en sens inverse.

**Pourquoi :** un identifiant lu puis réécrit à la main perd sa forme exacte, et
COM ne dit pas « clé inconnue », il lève une exception générique. On croit alors
à un problème d'API ou de type de contrôle, et on part chercher une autre
méthode de sélection, ce qui coûte plusieurs allers-retours contre un système
lent.

**Comment appliquer :** journaliser les identifiants opaques avec `repr()` avant
de s'en servir, et les repasser tels quels. Devant un `com_error` sans message
sur un appel dont la syntaxe semble juste, suspecter la VALEUR passée avant de
suspecter la méthode. Voir aussi
[[alv-enveloppee-dans-un-splitter-en-2023]].
