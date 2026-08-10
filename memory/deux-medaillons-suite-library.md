---
name: deux-medaillons-suite-library
description: Décision 2026-08-07 : deux gravures du médaillon, « suite » (projet complet, assets/logo.png, le défaut partout) et « library » (les bibliothèques seules, assets/logo-library.png, page PyPI uniquement) ; la bascule PyPI est fail-closed en deux endroits
type: projet
date: 2026-08-07
---

Le logo du projet existe en **deux gravures de la même médaille**, et le choix
n'est pas décoratif : il dit de quoi on parle.

- **`ECC UI5 API TEST SUITE`** (visage du robot) = le **projet complet**,
  bibliothèques + recorders + intégration MCP + agents de test. C'est
  `assets/logo.png`, et c'est le défaut partout : READMEs GitHub, couverture
  du deck, pages web, icônes de l'extension, icône de fenêtre du recorder
  bureau, picto 28 px embarqué dans le panneau du recorder web.
- **`ECC UI5 API LIBRARY`** (triskèle) = les **trois bibliothèques seules**,
  c'est-à-dire exactement ce que livre `pip install robotframework-sapfx`.
  C'est `assets/logo-library.png`, et il ne sert QUE sur la page PyPI.

Le README est un seul fichier pour GitHub et PyPI : la bascule se fait donc là
où la variante PyPI est rendue, et à **deux** endroits qu'il faut garder en
phase, tous deux **fail-closed** (motif introuvable = abandon) :
`pypi_readme()` dans `scripts/export_public_tree.py`, et l'étape de rendu du
README de `.github/workflows/pypi-publish.yml`. Un test unitaire vérifie aussi
le **vrai** `README.md` : retoucher le bandeau casse en CI, pas au build.

Toutes les déclinaisons (icônes 16/48/128, icône Tkinter, data-URI du panneau
web) descendent de `assets/logo.png` et se régénèrent en une commande,
`python tools/recorder_web/extension/gen_icons.py` : depuis 2026-08-07 il
réécrit aussi `_AICABRA_ICON` dans `_ui5_js.py`, donc **penser à relancer
`python -m SapFioriLibrary.regen_recorder`** derrière, sinon les artefacts
générés du recorder partent en échec de synchro.

**Piège de détourage** (les sources arrivent sur fond blanc) : le remplissage
par diffusion depuis les coins doit rester à une tolérance **basse** (60). À
90, il passe dans le reflet clair du liseré haut du médaillon et arrache un
morceau du bord (mesuré : 15 800 pixels). Recette complète dans
`comms/identite-visuelle.md`. Voir aussi [[decision-pypi-canal-unique]] : c'est
la même frontière (ce que PyPI livre) vue côté image.
