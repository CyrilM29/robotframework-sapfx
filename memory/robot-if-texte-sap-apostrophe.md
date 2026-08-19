---
name: robot-if-texte-sap-apostrophe
description: Une condition Robot qui interpole un texte SAP entre apostrophes (IF '${msg}' != '${EMPTY}') casse en SyntaxError dès que le message contient une apostrophe : utiliser la forme EXPRESSION ($msg)
type: projet
date: 2026-08-18
---

# Condition Robot : ne jamais entourer un texte SAP d'apostrophes

**Date : 2026-08-18.** Constat d'une revue de code complète, corrigé le jour
même (le défaut était en production dans `exploratory_campaign_a4h.robot`, à
deux endroits).

## Le problème

```robotframework
${dialog}=    Dismiss Message Dialog If Present
IF    '${dialog}' != '${EMPTY}'
```

Robot **substitue le texte AVANT d'évaluer** : la condition devient une
expression Python où le message SAP est un littéral entre apostrophes. Dès
que ce message en contient une (locale FR : « n'est pas autorisé »), le
littéral se ferme trop tôt et Robot échoue en
`Evaluating expression failed: SyntaxError`, à la place de la branche prévue.

Le piège est vicieux : le code marche parfaitement en locale EN et casse en
FR, et il casse **là où on venait justement d'ajouter une réparation** (le
chemin du dialogue de message), donc au pire moment.

## Pourquoi

C'est la même famille que le piège `\d` déjà documenté dans le dépôt : une
valeur traverse une couche de substitution textuelle avant d'être interprétée
par un moteur d'expressions. Toute donnée venue du système testé (message,
libellé, valeur de champ) est **hostile** à ce niveau, exactement comme une
entrée utilisateur l'est vis-à-vis d'un SQL concaténé.

## Comment appliquer

Utiliser la forme **expression** de Robot, où la variable est passée par
référence et jamais interpolée dans le texte :

```robotframework
IF    $dialog                      # non vide
IF    $state["verdict"] == "rejected"
IF    not $state["reached"]
```

Règle générale : dans une cellule `IF` / `Should Be True` / `Evaluate`, la
syntaxe `$nom` (sans accolades) est la seule sûre pour une valeur venue de
SAP. Réserver `${nom}` aux endroits où on veut vraiment du texte (messages de
log, arguments de keyword). Les mêmes suites gardent `'${type}' == 'E'` sans
risque : un TYPE de message est un caractère contrôlé (convention #3), pas un
texte libre. Voir [[se16-ecran-selection-genere-premier-acces]] pour le
contexte où le défaut a été trouvé.
