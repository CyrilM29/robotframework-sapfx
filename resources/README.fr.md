> [🇬🇧 English](README.md) · **🇫🇷 Français**

# `resources/` : des exemples à personnaliser, jamais une vérité SAP universelle

**Ce qui fait foi dans ce projet, c'est `src/`.** Les trois bibliothèques
(`SapEccLibrary`, `SapFioriLibrary`, `SapApiLibrary`) et `sapfx_common` portent
les CAPACITÉS : perception, résolution de localisateurs, attente, moteurs,
lecture d'état, protocoles, auto-réparation. Elles sont indépendantes du système
cible, testées unitairement hors SAP, versionnées, publiées sur PyPI, et ce que
promet un de leurs mots-clés, il le promet sur n'importe quel système SAP.

**`resources/` est exactement l'inverse, et c'est délibéré.** Cette couche porte
le VOCABULAIRE MÉTIER d'*une* installation : les identifiants, chemins de
service, noms de tables et de modules fonction, paramètres de profil et
enchaînements d'écrans d'une cible donnée, nommés dans la langue d'un domaine
métier donné. Chaque valeur qu'on y lit a été relevée live sur les cibles du
laboratoire de ce dépôt.

Beaucoup s'y transpose : les transactions standard, les services OData standard
et le vocabulaire en miroir des canaux sont les mêmes sur bien des systèmes, donc
une bonne part de cette couche se réutilise telle quelle. Mais **rien n'y fait
autorité**. Une release, une langue, une variante d'écran, un champ Z spécifique,
ou simplement votre domaine métier, change ce qu'un mot-clé doit adresser. À
vérifier sur votre cible, et à adapter.

Donc : **ces fichiers sont à personnaliser selon votre cible et selon votre
métier.** C'est une trousse de démarrage, pas une dépendance.

## Ce qui a été mesuré, et où

| Cible utilisée par ce dépôt | Ce qu'elle a figé dans `resources/` |
| --- | --- |
| ABAP Platform Trial 1909 (A4H, Docker) | les ids SE16/SE38/SM50, les cartes de champs des écrans de sélection SE16, les garde-fous de données de démonstration (SFLIGHT, EPM) |
| ABAP Platform 2023 | la seconde release du page object FLP partagé, les lots de contrôles de sécurité |
| OpenUI5 Demo Kit, cap-sflight local | le vocabulaire Fiori, le page object de la liste Travel, et `page_objects/openui5_demokit.resource` (routage par hash, arbre de l'API, tables de documentation, menu Options, thème, iframe d'échantillon) |
| Un site SAP Build Work Zone sur BTP (derrière un tenant IAS) | les page objects `workzone_*` (shell, recherche, zone utilisateur, session, application embarquée) |
| La Gateway d'A4H, cap-sflight, le bac à sable SAP Business Accelerator Hub | les chemins de service OData derrière des noms métier (`${EPM_PRODUCTS}`, `${TRAVEL_ENTITIES}`…) |

Trois degrés, en pratique :

- **Souvent réutilisable tel quel** : les écrans standard (SE16, SE11, SE38), les
  patrons de page object FLP et ushell, les préflights des canaux API et RFC, et
  toute la nomenclature. `${SE16_TABLE_FIELD}` est un identifiant relevé sur SAP
  GUI 8.00 contre A4H, et il tient généralement ailleurs.
- **À vérifier, et souvent à ajuster** : les identifiants positionnels des écrans
  de sélection (ils suivent l'ordre des champs de la table, donc ils bougent avec
  la release), les chemins de grille (les releases récentes enveloppent l'ALV dans
  un splitter, à une profondeur qui varie par transaction), les ancres de
  launchpad (elles diffèrent entre UI5 1.71 et 1.120, ce qui est précisément
  pourquoi `page_objects/abap_flp.resource` est partagé par les deux).
- **Propre au laboratoire, à remplacer** : les modèles de démonstration (SFLIGHT,
  EPM, `/DMO/`) et les chemins de service qui les projettent, les page objects
  `workzone_*` écrits pour un site BTP, les garde-fous de données de
  démonstration, et `@{PARAMS_PASSWORD_POLICY}`, qui est une *sélection* de
  paramètres de profil convenant à un bac à sable et doit suivre votre propre
  politique de sécurité.

## Ce qui, ici, est réellement réutilisable

Les valeurs sont locales ; le **patron** ne l'est pas. Ce qu'il faut garder en
réécrivant cette couche pour votre site :

- **Un vocabulaire en miroir sur les quatre canaux** (ECC, Fiori, OData, RFC) :
  `Open …`, `Count …`, `Read …`, `Close …`, pour qu'un test se lise de la même
  façon quel que soit le canal piloté (tables de correspondance dans la
  `Documentation` de chaque fichier).
- **La convention 1** : aucun id SAP brut, aucun CSS/XPath, aucun chemin de
  service OData, aucun nom de module fonction ni de table dans un cas de test.
  Tout cela vit dans cette couche, les tests parlent métier.
- **Un `.resource` par écran ou par application** sous `page_objects/`, variables
  de localisateurs plus mots-clés métier : c'est la couche que l'agent
  `sap-healer` répare, et celle qu'une montée de version vous fait toucher.
- **Les propriétés de sûreté encodées dans les mots-clés**, qui valent d'être
  recopiées telles quelles : chemins d'écriture passant par une liste blanche,
  suppression qui relit la grille filtrée avant d'agir, assertions jugées sur le
  TYPE d'un message et jamais sur un texte localisé, nettoyages constatés plutôt
  que supposés.
- **Les divergences de release exprimées par une variable ou une stratégie
  nommée**, jamais par un `IF` sur un numéro de version (voir
  `page_objects/abap_flp.resource`, partagé par UI5 1.71 et 1.120).

## L'utiliser sur votre système

1. Copiez le fichier qui correspond à votre canal, gardez les noms de mots-clés,
   remplacez les variables par ce que vous avez mesuré sur *votre* cible (l'agent
   `sap-planner` et les deux recorders existent pour les mesurer à votre place).
2. Mettez vos valeurs d'environnement dans `variables/env_<env>.yaml`, et **jamais
   de valeur par défaut pour un secret** : mots de passe, clés d'API et jetons
   entrent par la ligne de commande (`-v "SAP_PASSWORD: Secret:…"`) ou par
   l'environnement.
3. Sur un **pack déployé** (pas de `src/` à éditer), écrivez vos mots-clés dans
   `resources/site_keywords.resource` : les fichiers livrés sont écrasés par la
   mise à jour suivante du pack, les vôtres non.

## Où va une correction, et pourquoi cela compte

Un défaut rencontré sur une cible réelle n'appartient pas toujours à cette
couche :

- Le mot-clé de bibliothèque se comporte mal, ou la capacité manque : **corriger
  dans `src/`** (logique pure dans `sapfx_common`). C'est ce qui part sur PyPI,
  donc un correctif resté dans une resource ne profite à personne d'autre et se
  réimprovise au projet suivant.
- La cible nomme les choses autrement, l'enchaînement d'écrans a changé, un
  identifiant a dérivé : **corriger ici**, cette couche est faite pour ça.

Cette frontière est la convention 12 de `CLAUDE.md`, et c'est aussi pourquoi la
télémétrie d'auto-réparation ne propose des patches que dans `resources/` : ce
qui varie par site doit rester dans la couche prévue pour varier.

## Pourquoi les livrer quand même

Parce qu'un patron qui fonctionne vaut mieux qu'un dossier vide, et parce que ces
fichiers ne sont pas décoratifs : ce sont eux que les campagnes live de ce dépôt
exécutent contre de vrais systèmes (A4H, ABAP Platform 2023, un site Work Zone
BTP, cap-sflight). Ils éprouvent les bibliothèques contre la réalité, et ils vous
montrent la forme de la couche que vous avez à écrire. À lire comme un exemple
travaillé, pas comme un contrat.
