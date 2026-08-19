---
name: uia-desktop-generique-composition
description: Décision 2026-08-12 : rien d'UIA à intégrer dans SAPFX (la SAP GUI Scripting API reste supérieure sur SAP GUI) ; appli Windows non-SAP d'un flux = composer PlatynUI/FlaUI à côté ; idée en réserve : repli UIA avant l'effecteur coordonnées sur les zones opaques, à ne creuser que sur cas réel
type: projet
date: 2026-08-12
---

Contexte : évaluation (2026-08-12) du pitch QF-Test « test des applications
Windows (Win32, WinForms/WPF, UWP, Qt) via l'API Windows Automation, détection
automatique de la technologie ». Question posée : un intérêt pour SAPFX ?

Conclusion, en trois points :

- **Rien à adopter pour piloter SAP GUI.** UIA ne voit SAP GUI qu'à travers sa
  couche d'accessibilité, partielle (cf. la field note « listes ABAP rendues en
  GuiShell opaque sans mode accessibilité »). La SAP GUI Scripting API (COM)
  reste structurellement supérieure : modèle d'objets sémantique, ids stables,
  `GetObjectTree` en un appel, record natif.
- **Ne pas réimplémenter d'effecteur UIA dans SAPFX.** L'écosystème Robot
  Framework a déjà la brique : PlatynUI (livré avec rf-mcp 0.35 ; attention au
  piège de classification desktop des field notes) et robotframework-flaui. Si
  un flux touche une appli Windows non-SAP (dialogue fichier, client tiers),
  la réponse est la composition : importer la lib UIA à côté, unifier dans
  `resources/`, exactement comme Browser côté web.
- **Idée en réserve, à ne creuser que sur cas réel** : sonder UIA/MSAA comme
  repli intermédiaire AVANT l'effecteur coordonnées (`Click Element At
  Offset`) sur les zones officiellement hors API Scripting (GuiShell opaques,
  GuiChart). Aucun cas concret ne le justifie à ce jour ; si le besoin
  survient, commencer par composer PlatynUI/FlaUI, pas par coder.

Trace comm : nuance « généralistes desktop Windows » ajoutée le même jour dans
`comms/comparatif.md` (§ Les nuances honnêtes + source QF-Test).
