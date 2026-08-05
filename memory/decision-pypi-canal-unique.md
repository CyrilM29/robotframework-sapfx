---
name: decision-pypi-canal-unique
description: Décision 2026-08-03 (révisée le jour même) : le pack ZIP GitHub RESTE le canal d'installation complète ; PyPI = bibliothèques seules ; le « full PyPI » (2 distributions, extras [all], sapfx init) est un plan noté POUR PLUS TARD
type: projet
date: 2026-08-03
---

Décision (2026-08-03, révisée dans la même journée) : la distribution reste
**à deux canaux assumés**, et il faut le dire clairement dans les README et
docs :

- **PyPI (`robotframework-sapfx`)** = les 4 bibliothèques Python seules
  (+ extras `web`/`visual`). C'est le canal `pip install` nominal pour
  utiliser les keywords dans Robot Framework.
- **Pack ZIP des GitHub Releases** (`sapfx-pack-<version>-win.zip`) = **la
  seule option d'installation complète** : les deux wheels (bibliothèques +
  plugins rf-mcp/`sapfx-mcp`), `resources/`, les deux recorders + extension
  MV3, suites d'exemple, scripts de maintenance, agents + skill,
  `install.cmd`/`.ps1`. C'est le canal recommandé pour toute installation
  « tout embarqué » (provisionnement d'un poste de test cible). NE PAS le
  vendre comme solution « milieu fermé » : `install.ps1` tire les dépendances
  épinglées (`requirements-deploy.txt`) depuis PyPI ou un miroir interne
  pendant l'installation : seul le code SAPFX est embarqué dans le ZIP
  (leçon anti-overclaim du 2026-08-03).

Le plan « PyPI canal unique tout embarqué » (2 distributions PyPI dont
`robotframework-sapfx-mcp`, recorders déplacés dans un paquet
`src/sapfx_tools/` avec console_scripts, extras `[mcp]`/`[all]`, commande de
scaffolding `sapfx init` + `sapfx doctor`, pack converti en wheelhouse
hors-ligne) a été étudié et phasé le 2026-08-03 mais est **reporté, à
ressortir plus tard** si le besoin se confirme. Ses grandes lignes restent
valables : renommage de dist sans toucher au paquet d'import ni aux entry
points ; scaffold en package data gardé en phase par un garde de synchro ;
prérequis mainteneur = créer le projet PyPI + Trusted Publisher de la
2e distribution.
