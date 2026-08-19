---
name: libdoc-chemins-absolus
description: Libdoc grave le chemin ABSOLU du fichier source dans chaque champ source (bibliothèque et keywords), donc un chemin de poste dans toute page publiée
type: projet
date: 2026-08-11
---

Constaté le 2026-08-11 en préparant la publication des pages de documentation
des keywords : chaque spec Libdoc (et donc chaque page HTML reconstruite
depuis elle, qui embarque la spec en JSON) porte un champ `source` par
**keyword** en plus de celui de la bibliothèque, renseigné avec le chemin
ABSOLU du fichier au moment de la génération. Soit, pour les trois
bibliothèques, 198 occurrences du chemin du poste de génération dans des
fichiers destinés à être publiés.

Ce n'est pas cosmétique : le chemin nomme l'arborescence de travail de la
machine, et l'export public s'arrête dessus (scan anti-fuite), c'est-à-dire au
pire moment, le jour de la release.

Le traitement retenu : **relativiser à la racine du dépôt**
(`src/SapEccLibrary/keywords/_grid.py`) dans la spec traduite, AVANT de
reconstruire les pages, par remplacement de TEXTE (jamais de réindentation du
JSON : sous Windows, un `json.tool` naïf relit en ANSI et grave du mojibake).
Le champ garde ainsi sa valeur informative, sans rien dire du poste. Verrouillé
par `tests/unit/test_libdoc_pages_fresh.py`, qui refuse toute lettre de lecteur
dans une spec ou une page, et par la procédure de `comms/libdoc/README.md`.

Leçon généralisable : un générateur de documentation grave l'environnement de
génération dans son artefact. Avant de publier une sortie d'outil, la lire
comme le ferait un lecteur externe, pas seulement la regarder s'afficher.

Voir aussi [[deux-medaillons-suite-library]] (l'autre règle qui s'applique à
ces mêmes pages : le médaillon `library` quand le sujet est les bibliothèques
seules).
