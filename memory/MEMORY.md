# Index mémoire du projet

Une ligne par fiche ; n'ouvrir une fiche que si sa description est pertinente.
Règles : [README.md](README.md).

- [Distribution, deux canaux](decision-pypi-canal-unique.md) : 2026-08-03, PyPI = libs seules, pack ZIP GitHub = SEULE install complète (mais PAS « milieu fermé » : l'installateur tire les dépendances de PyPI/miroir) ; le « full PyPI » (sapfx init, extras [all]) est phasé mais REPORTÉ
- [Hot-reload plugins rf-mcp](rfmcp-plugin-hot-reload.md) : reload de la couche plugin sans redémarrer le serveur ; routage page_source/application_state ; le diff des providers exige page_source_filtered=true
- [A4H, écriture/suppression SE16](a4h-se16-write-delete.md) : SE16 fait Create/Change/Delete en place (DEVELOPER) ; Create depuis l'écran INITIAL ; SM30 KO sur SCARR ; séparateur de milliers dans les comptes
- [Run Transaction, tcodes paramétrés](run-transaction-tcodes-parametres.md) : faux négatif quand sy-tcode ≠ code saisi (tcodes IMG générés) : percevoir avant de conclure ; correspondance via CUS_IMGACH
- [Deux médaillons, suite et library](deux-medaillons-suite-library.md) : 2026-08-07, `logo.png` (projet complet) partout / `logo-library.png` (bibliothèques seules) sur PyPI ; bascule fail-closed dans export_public_tree.py ET pypi-publish.yml ; gen_icons.py puis regen_recorder ; détourage à tolérance 60, pas 90
- [Tournage des vidéos de démo](tournage-video-demos.md) : gdigrab, fenêtres GPU noires (capturer une région), arrêt ffmpeg par « q » sinon tampon perdu, bornage AVANT -i quand setpts accélère, couper la fin de prise (bureau visible)
