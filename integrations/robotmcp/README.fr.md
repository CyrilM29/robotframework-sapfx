> [🇬🇧 English](README.md) · **🇫🇷 Français**

# Plugins rf-mcp pour l'écosystème SAP

> Démarrage rapide. Pour la conception et l'usage détaillés, voir la doc canonique :
> [docs/mcp-integration.fr.md](../../docs/mcp-integration.fr.md)
> ([EN](../../docs/mcp-integration.md)).

Intègre ce dépôt à **[rf-mcp / RobotMCP](https://github.com/manykarim/rf-mcp)**
(serveur MCP pour Robot Framework) au lieu de réécrire un MCP. rf-mcp fournit déjà
toute la couche générique : découverte de keywords, exécution live, génération de
suites, mémoire, et un *Debug Attach Bridge* pour l'assistance dans l'IDE.

Ce paquet ne comble que **le seul trou** : la perception et la guidance **SAP**, que
rf-mcp ne connaît pas (son `get_locator_guidance` ne couvre que Browser/Selenium/Appium).
Trois plugins, un par canal : `SapEccPlugin` (GUI desktop), `SapFioriPlugin`
(web Fiori/UI5) et `SapApiPlugin` (OData/RFC — un canal sans écran : sa page
source est une explication honnête, son état applicatif l'état réel du canal
via `List Api Sessions`, jamais de credentials).

## Ce que les plugins ajoutent

| Hook rf-mcp | Apport SAP |
| --- | --- |
| `get_state_provider()` | Perception : **screen signature** ECC (via le keyword `Get Screen Signature`, exécuté dans le contexte RF vivant) exposée comme "page source" de session. L'agent *voit* l'écran avant d'agir. |
| `get_hints()` / `get_prompt_bundle()` | Guidance de sélecteurs SAP : contrôles UI5 ≠ ids DOM, type de message barre ≠ texte localisé, jamais de `time.sleep`, vocabulaire métier de `resources/` ; plus le workflow agent 0.2.0 (préflight en Suite Setup, perception `mode=diff`, keywords de healing sur échec de localisation, `Set Ui5 Frame` pour les iframes de launchpad). |
| `get_keyword_library_map()` | Route `Click Ui5 Control`, `Run Transaction`, etc. vers les libs — y compris les keywords 0.2.0 (`Scripting Should Be Fully Enabled`, `Get Session Telemetry`, `Resolve Element With Healing`, `Resolve Ui5 With Fallback`, `Set Ui5 Frame`, `Ui5 Text Should Be`). |

Les plugins eux-mêmes ne créent aucun outil MCP (le contrat de plugin ne le
permet pas) : l'agent lit l'état via `get_session_state` puis appelle
directement les keywords SAP. Ce que le contrat 0.31 ne sait **pas** exprimer
est ajouté par la **surcouche `sapfx-mcp`** — un point d'entrée console de ce
même wheel qui monte le serveur rf-mcp inchangé et ajoute `sapfx_state`
(providers appelés en direct : page source en diff par défaut, état applicatif
enrichi), `sapfx_screenshot` (vrai contenu image MCP, brut ou annoté
Set-of-Mark) et `sapfx_reload` (hot-reload de la couche plugin), derrière un
garde de compatibilité au démarrage. Voir
[docs/mcp-integration.fr.md](../../docs/mcp-integration.fr.md).

### Subtilité Fiori (vérifiée dans le code rf-mcp)

rf-mcp n'invoque le `state_provider` de page source que pour la **bibliothèque web
active**, résolue à **Browser** (SapFioriLibrary ne pilote pas la page, elle réutilise
celle de Browser). Le provider Browser builtin l'emporte donc. La perception UI5
passe par un **keyword** que l'agent appelle (`Get Ui5 Page Tree`) + les hints qui
l'y invitent — pas par le provider. Côté **ECC**, SapEccLibrary *est* la lib active :
son provider est bien sollicité.

## Notes de sécurité

- **Pas d'allowlist de tcodes.** `Run Transaction`/`Send Vkey`/`Input Text` sont
  routés vers l'agent sans liste blanche/noire — un agent qui pilote SAP via ce
  plugin dispose exactement des autorisations SAP de son utilisateur (il peut
  invoquer `SU01`, `SM49`, `SE38`, etc.). C'est voulu (l'outil vise l'automation de
  test complète), mais à garder en tête avant de brancher un agent LLM sur un
  système non-trial : ne donnez pas à l'utilisateur SAP pilotant plus
  d'autorisations que ce que les tests requièrent réellement.
- **L'enregistrement des entry-points n'a pas de namespacing intégré.** Les
  plugins s'enregistrent sous le groupe d'entry-points `robotmcp.library_plugins`
  (`pyproject.toml`) ; tout autre paquet installé déclarant le même groupe se
  charge aussi dans rf-mcp — une caractéristique générique du mécanisme
  d'entry-points Python, que ce dépôt ne peut pas corriger depuis son propre
  `pyproject.toml`. Ne compte que si un paquet non fiable est un jour installé
  dans le même environnement, auquel cas le détournement d'entry-point est un
  problème secondaire par rapport à la compromission de supply chain qui l'a
  amené là.
- Les stores API et l'état frame/perception Fiori sont partitionnés par contexte
  `MCP_Test_<session_id>`. Conserver une session ECC live par process : rf-mcp
  0.31 peut mal attribuer les appels de resources imbriquées, et `SUITE` ne suffit pas.

## Installation

```bash
pip install rf-mcp                 # l'hôte
pip install -e .                   # à la RACINE du dépôt : rend SapEcc/SapFioriLibrary importables
pip install -e integrations/robotmcp   # enregistre les plugins (entry-points)
```

Vérifier la découverte :

```bash
python -c "from robotmcp.config import library_registry as r; print(r.get_all_libraries())"
```

Alternative sans installation : déposer un manifeste dans `.robotmcp/plugins/`
pointant la classe (`{"module": "sap_robotmcp.fiori_plugin", "class": "SapFioriPlugin"}`).

## État

- [x] Plugins conformes au **contrat réel** rf-mcp 0.31.2 (`StaticLibraryPlugin`,
      `LibraryMetadata/Capabilities/Hints`, `PromptBundle`, signature exacte de
      `get_page_source`) — re-validés contre **rf-mcp 0.35.0** le 2026-07-24
      (`plugins/contracts.py` et `plugins/manager.py` identiques octet à octet
      entre les deux, `plugins/base.py` = ajout rétro-compatible seulement ; la
      fenêtre du garde de démarrage de la surcouche, dans
      `sap_robotmcp/_compat.py`, couvre 0.31–0.35). Instanciation + guidance
      couvertes par `tests/test_plugins.py` (10/10, off-SAP, sans session live).
- [x] `state_provider` câblés sur le **vrai** pattern RF-context d'accès à l'instance
      live (`get_rf_native_context_manager().execute_keyword_with_context`), comme le
      provider Browser builtin (`_rf_context.run_keyword_in_context`).
- [x] **Keywords de perception** ajoutés dans les libs (les providers les appellent),
      avec unit-tests off-SAP (`tests/unit/test_perception.py`) :
  - `SapEccLibrary.Get Screen Signature` (mixin `keywords/_perception.py`) : vue texte
    de l'écran actif (entête `# screen Prog/Tcode/Dynpro` + ids relatifs, champs
    éditables marqués `*`).
  - `SapFioriLibrary.Get Ui5 Page Tree` : arbre de contrôles UI5 sérialisé en XML
    (méthode `dumpTree` ajoutée au bundle `_ui5_js.py`).
- [x] **Smoke end-to-end Fiori *à travers* rf-mcp** (`e2e/fiori_through_rfmcp.py`,
      8/8) : pilote les vrais tools (`manage_session`/`execute_step`/`get_session_state`)
      en process. Valide la découverte du plugin, une session **Browser + SapFioriLibrary**
      dans un seul contexte RF, le routing (`Get Ui5 Page Tree`, `Click Ui5 Control`), la
      perception (arbre UI5 peuplé) et l'action (clic → ouverture du Dialog) — donc la
      dépendance Browser satisfaite. Cible : le fixture UI5 local (déterministe).
- [x] **Smoke end-to-end ECC *à travers* rf-mcp** (`e2e/ecc_through_rfmcp.py`, 9/9,
      contre A4H Docker live) : session SapEccLibrary + resource métier, login COM,
      routing (`Run Transaction`/`Get Current Transaction`), perception
      `Get Screen Signature`, et surtout le **state provider** appelé directement —
      `EccStateProvider.get_page_source` renvoie la vraie signature d'écran SE16 live
      (le provider exécute le keyword dans le contexte RF natif). A nécessité un
      `CoInitialize` sur le thread d'exécution rf-mcp (override dans `keywords/_connection.py`).
- [x] **Compaction de la perception** : les deux state providers interrogent
      TOUJOURS le vrai écran/arbre (jamais de cache temporel — un état périmé
      juste après une action casserait la boucle perception -> action), mais si
      le résultat est identique octet pour octet au précédent appel pour cette
      session, `page_source` est remplacé par un marqueur compact et
      `unchanged_since_last_call: true` est renseigné — ce qui économise le
      contexte de l'agent sur des vérifications répétées sans action entre les
      deux. Voir `_last_seen.py` (`tests/test_last_seen.py`, hors-SAP).
- [x] **Filtrage de la perception** : `get_page_source(filtered=True,
      filtering_level=...)` (déclaré par le contrat `LibraryStateProvider` réel
      de rf-mcp, accepté mais ignoré jusqu'ici) réduit désormais vraiment la
      réponse sur les écrans SAP chargés, sur le même principe de progressivité
      minimal/standard/aggressive que le vrai provider Browser. ECC : `minimal`
      retire le bruit structurel pur, `standard` retire aussi les types de
      conteneur de mise en page connus, `aggressive` ne garde que les champs
      éditables. Fiori : élagage ascendant des feuilles non interactives/sans
      texte, sans jamais casser la chaîne d'ancêtres d'un nœud survivant (le
      chemin XPath reste valide). Le filtrage est toujours un post-traitement
      sur la perception fraîchement obtenue — jamais un raccourci qui saute
      l'interrogation de l'écran réel. Voir `_filtering.py`
      (`tests/test_filtering.py`, 20 tests hors-SAP).
