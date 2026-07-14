> [🇬🇧 English](README.md) · **🇫🇷 Français**

# SAPFX — releases

Point de distribution public de **SAPFX**, un écosystème d'automatisation de
tests SAP pour [Robot Framework](https://robotframework.org) :

- **SapEccLibrary** — automatisation SAP GUI desktop (ECC / backend S/4HANA)
  via l'API SAP GUI Scripting : perception structurée des écrans,
  localisateurs auto-réparants, localisateurs humains (par libellé) et
  assertions visuelles ;
- **SapFioriLibrary** — automatisation web SAP Fiori / UI5 aux côtés de la
  bibliothèque Browser (Playwright) : moteurs de résolution role / XPath /
  Web Components / WebGUI, iframes de launchpad, baselines visuelles ;
- **SapApiLibrary** — le canal API : OData v2/v4 avec un seul jeu de
  keywords, RFC optionnel ;
- des resources de keywords métier, un recorder desktop (événements natifs
  de l'API Scripting) et un recorder web (extension Chrome MV3), les plugins
  rf-mcp (RobotMCP) pour le pilotage par agents IA, les agents de test
  plan → generate → heal, et une sentinelle de dérive qui surveille des
  écrans sans tests scriptés.

Ce dépôt n'héberge **que les artefacts de release** — le **pack de
déploiement Windows** autonome. Le code source vit dans un dépôt privé ;
accès sur demande : <cyril@montiel.me>.

## Téléchargement

Récupérez `sapfx-pack-<version>-win.zip` depuis la page
[Releases](../../releases).

## Installation (résumé)

1. Dézippez sur le PC Windows cible (Python 3.10+ sur le `PATH`).
2. `install.cmd` — bibliothèques seules ; `-WithMcp` ajoute les plugins
   rf-mcp et rend les configs MCP en place ; `-WithBrowsers` télécharge le
   Chromium de Playwright.
3. Validez avec les suites d'exemple (`tests\robot\fiori_smoke.robot` ne
   nécessite aucun SAP).

Instructions complètes, prérequis et dépannage : `README.md` /
`README.fr.md` **dans le pack**.

## Licence

Apache-2.0 — voir [LICENSE](LICENSE) et [NOTICE](NOTICE) (tous deux également
livrés dans chaque pack, à côté des binaires).
