---
name: rfmcp-plugin-hot-reload
description: rf-mcp — hot-reload plugins sans redémarrage, routage page_source/application_state, où le mode diff s'exerce (validé live 2026-07-23)
type: projet
date: 2026-07-23
---

Quatre faits rf-mcp 0.31.2 validés live (A4H, SE16) le 2026-07-23, détaillés
dans les field notes de CLAUDE.md (toujours valables en 0.35.0 —
re-vérification du 2026-07-24) :

1. **Hot-reload de la couche plugin sans redémarrer le serveur** :
   `importlib.reload` des modules `sap_robotmcp` →
   `robotmcp.plugins.manager.reset_library_plugin_manager_for_tests()` →
   ré-enregistrement (`iter_entry_point_plugins` → `register_plugin`). Le tool
   `manage_library_plugins reload` seul ne suffit PAS (instances en cache).
2. `get_session_state(page_source)` ne route vers le provider SAP que si
   `session.browser_state.active_library` est posé — jamais posé par le
   contexte natif pour une lib desktop (→ « No page source available »).
3. Le chemin `application_state` de rf-mcp n'appelle jamais
   `get_application_state` des plugins — l'état enrichi (modal_open…) passe
   par les keywords (`Get Open Windows`) via `execute_step`.
4. Le serveur passe `full_source=not page_source_filtered` : le mode DIFF du
   provider ne s'exerce qu'avec `page_source_filtered=true`.

Depuis, la **surcouche `sapfx-mcp`** (outils `sapfx_state`/`sapfx_screenshot`/
`sapfx_reload`) contourne 2–4 en appelant les providers en direct.

**Pourquoi :** ces limites ne sont visibles dans aucun code du dépôt
(comportement du paquet rf-mcp installé) et coûtent une session de débogage à
redécouvrir.

**Comment appliquer :** avant tout test live agent+MCP après modification de
`src/`/`integrations/`, dérouler le hot-reload (1) OU redémarrer le serveur ;
pour exercer le diff des providers, demander `page_source_filtered=true` ;
ne pas chercher `modal_open` dans `get_session_state` (appeler le keyword).
