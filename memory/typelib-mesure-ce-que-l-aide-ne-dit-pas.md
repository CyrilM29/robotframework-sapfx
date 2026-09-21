---
name: typelib-mesure-ce-que-l-aide-ne-dit-pas
description: >-
  2026-09-08, la type library COM d'un client SAP GUI expose des membres que
  l'aide officielle ne documente pas (mesuré en 8.10 : SetFields,
  HighlightElements, RunGuidedScript, ExceptionMsgBoxActive absents du chapitre
  GuiSession) : comparer deux typelibs est la seule mesure de ce qu'une release
  apporte, l'aide n'en est que le commentaire ; et le dump doit se faire SANS
  enregistrement (REGKIND_NONE), sinon charger la typelib d'un média détourne le
  LIBID du poste vers un dossier de téléchargement
metadata:
  type: project
---

Devant un nouveau média de SAP GUI, la question « qu'est-ce que cette release
apporte à l'automatisation » se répond en **comparant les type libraries COM**
du client neuf et du client installé, pas en lisant la documentation. Mesuré le
2026-09-08 en dépouillant le média SAP Frontend Package 8.10 Compilation 1
(numéro 50167926) face au 8.00 installé : trois méthodes et deux propriétés de
`GuiSession` existent dans `sapfewse.ocx` sans figurer dans le chapitre
« GuiSession Object » de l'aide livrée sur le MÊME média, dont deux qui
changeraient nos keywords (`SetFields`, qui pose plusieurs champs en un appel,
et `HighlightElements`, qui encadre une liste d'éléments à l'écran). Les
membres documentés, eux, sont tous présents : l'aide ne ment pas, elle est
incomplète, ce qui est le pire des deux cas puisque rien ne signale le manque.

**Le geste, et son piège.** Charger une typelib avec `pythoncom.LoadTypeLib`
l'**ENREGISTRE** dans le registre Windows. Appliqué au fichier d'un média
téléchargé, cela fait pointer le LIBID `SAPFEWSELib` du poste vers un dossier
de téléchargement, pour tous les processus et toutes les sessions : le client
installé continue de fonctionner, mais toute résolution de typelib (makepy,
génération de wrappers, outils tiers) lit désormais une version que personne
n'a installée. Passer par `oleaut32.LoadTypeLibEx(path, REGKIND_NONE, byref)`
en ctypes, puis `pythoncom.ObjectFromAddress(ptr, pythoncom.IID_ITypeLib)` :
`pythoncom` n'expose pas `LoadTypeLibEx`, c'est l'unique raison du détour.
Le parcours ensuite est standard : `GetTypeInfoCount`, `GetTypeInfo`,
`GetTypeAttr`, `GetFuncDesc`, `GetVarDesc`, `GetNames`, avec
`GetRefTypeInfo` pour résoudre les types définis par l'utilisateur.

**Deux précautions de lecture du diff.** Comparer par NOM de fichier produit du
bruit de casse (le média écrit `sapguisv.ocx`, l'installation `SAPguisv.ocx`,
et un diff naïf annonce 30 fichiers ajoutés et 30 supprimés) : apparier en
minuscules, ou ne lire que les lignes de membres. Et un membre présent n'est
pas un membre utilisable : sur ce même média, `GetObjectList` et
`GetObjectTreeCompressed` sont documentés, mais l'aide les marque « not
supported for public use, restricted to SAP-internal scenarios ». La typelib
dit ce qui EXISTE, l'aide dit ce qui est SUPPORTÉ : les deux lectures sont
nécessaires, et une capacité non supportée se surveille au lieu de s'adopter.

**Pourquoi :** une release de client SAP GUI est annoncée par des notes de
version orientées utilisateur final (thèmes, ergonomie, navigateur embarqué),
où la ligne « scripting » se limite à ce que SAP juge grand public. Le
2026-09-08, cette ligne annonçait l'enregistrement en JScript, et rien
d'autre ; le diff des typelibs a rendu une douzaine de membres neufs, une
rupture de signature (`GuiTextedit.MultipleFilesDropped` prend désormais un
tableau de fichiers) et un membre disparu. Sans la mesure, la rupture se
serait découverte sur un poste client, en clientèle.

**Comment appliquer :** à chaque nouveau média ou patch majeur du client,
dumper les typelibs des deux versions et diffuser le diff avant de planifier
quoi que ce soit ; consigner les capacités neuves comme des keywords GARDÉS
(le client précédent reste maintenu des années, ici le 8.00 jusqu'au
31/07/2027, donc chaque nouveauté doit dégrader en nommant la version requise
plutôt que de tomber sur un `AttributeError` COM nu) ; et ne jamais lancer un
dump avec une fonction qui enregistre. Les scripts de mesure et le corpus
converti vivent dans la base de mémoire privée, la documentation SAP n'étant
pas redistribuable.
