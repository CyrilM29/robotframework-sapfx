> [🇬🇧 English](mcp-integration.md) · **🇫🇷 Français**

# Intégration MCP (plugins rf-mcp)

Comment ce projet expose ses bibliothèques SAP à un agent IA via le **Model Context
Protocol**, pour qu'un LLM (p.ex. Claude) écrive et lance des tests SAP, et qu'un
humain bénéficie de la même assistance dans un IDE.

## Positionnement : LE MCP de SAP

Une fenêtre est ouverte sur le marché : l'outil de test de SAP (CBTA) meurt
avec Solution Manager 7.2 (31/12/2027) **sans successeur annoncé**, et la
seule autre tentative publique de « SAP via MCP » est un prototype sans
licence ni tests. Le paquet `sap-robotmcp` de ce projet vise à être **la**
façon de référence dont n'importe quel client MCP (Claude Code, mode agent
Copilot, ou un hôte MCP générique) touche SAP, sur des garanties qu'aucune
alternative n'offre :

- **Perception réelle, jamais optimiste** : chaque réponse d'écran/état
  ré-interroge le système vivant (`Get Screen Signature`, `Get Ui5 Page
  Tree`, `get_application_state` lit la transaction LIVE) ; aucune machine à
  états qui *suppose* où en est la GUI.
- **Jamais silencieux** : l'ambiguïté échoue avec la liste des candidats ; le
  healing journalise un WARNING plus une entrée de télémétrie ; les erreurs
  sont auto-corrigibles (correspondances proches, diagnostic de portée,
  extraits de corps HTTP).
- **MCP-safe par construction** : les keywords retournent des chaînes/dicts,
  jamais d'objet COM à travers la frontière ; captures en base64 au MIME
  vérifié ; les états mutables API et Fiori sont partitionnés par session rf-mcp.
- **Testé comme un produit** : les plugins embarquent des tests unitaires
  hors SAP, une CI sur deux OS, et des validations de bout en bout contre un
  A4H vivant et des pages UI5 vivantes.
- **Apache-2.0**, avec l'attribution propre de chaque technique portée.

N'importe quel client MCP utilise le serveur avec une déclaration équivalente
à [`.mcp.json`](../.mcp.json) : lancer `sapfx-mcp --transport stdio
--without-frontend` avec un `PYTHONPATH` couvrant `src` et
`integrations/robotmcp` ; les plugins SAP s'enregistrent par entry points et
le script console `sapfx-mcp` est installé par le même
`pip install -e integrations/robotmcp`. Les
métadonnées du paquet sont prêtes pour la publication (nom PyPI
`sap-robotmcp`) ; les canaux de distribution du moment restent ce dépôt et le
pack de déploiement Windows : publier sur un index est une décision
délibérée, séparée.

## La surcouche `sapfx-mcp` (pas un fork)

`sapfx-mcp` monte le serveur rf-mcp **inchangé** (tous ses outils continuent
de fonctionner à l'identique) et ajoute les trois outils que le contrat
plugin 0.31 ne sait pas exprimer ; chaque manque a été établi live le
2026-07-23 (voir les field notes de `CLAUDE.md`) :

- **`sapfx_state`** : l'état de session servi *directement* par les state
  providers SAPFX : `page_source` avec la vraie sémantique différentielle
  (un écran déjà vu qui a changé retourne un diff intelligent compact par
  défaut ; via le `get_session_state` de rf-mcp, le diff ne s'exerce
  qu'avec `page_source_filtered=true`), et `application_state` enrichi de la
  pile de fenêtres live (`modal_open`, le piège du modal d'erreur
  résiduel), du type de message de statut et de la télémétrie de session,
  que rf-mcp ne route jamais vers les providers des plugins.
- **`sapfx_screenshot`** : le canal vision, une vraie image MCP (le contrat
  plugin n'a pas de canal image ; fastmcp si), brute ou annotée Set-of-Mark
  avec sa légende `numéro -> id` en bloc texte compagnon.
- **`sapfx_reload`** : le protocole de hot-reload de la couche plugin validé
  live (reload des modules → reset du manager de plugins →
  ré-enregistrement des entry points) ; le `manage_library_plugins reload`
  natif seul ressert des instances en cache.

Un **garde de compatibilité** s'exécute au démarrage : fenêtre de versions
rf-mcp validée plus une sonde de chaque point d'ancrage interne touché par la
surcouche ; tout écart refuse le démarrage avec la liste exacte
(`SAPFX_MCP_FORCE=1` outrepasse, bruyamment). La règle de santé : chaque
câblage accepté upstream doit faire *maigrir* cette surcouche ; elle ne doit
jamais grossir en fork de fait.

## Décision : composer au-dessus de rf-mcp, ne pas refaire un MCP

Il existe déjà un serveur MCP générique et mûr pour Robot Framework :
[**rf-mcp / RobotMCP**](https://github.com/manykarim/rf-mcp) (Apache-2.0). Il couvre
toute la surface générique : découverte de keywords, exécution live, génération de
suites (BDD / data-driven), mémoire sémantique, et un *Debug Attach Bridge* HTTP pour
l'assistance dans l'IDE. Réécrire tout cela serait du gâchis.

Le **seul** trou pour nous, c'est SAP : le guidage de sélecteurs de rf-mcp ne connaît
que Browser/Selenium/Appium, et il n'a aucune notion de contrôle UI5, de `sid` WebGUI,
ni d'écran SAP GUI desktop. Ce trou, c'est exactement la force de ce projet.

Donc plutôt qu'un MCP autonome (ou fusionner les libs dans rf-mcp), on **compose
au-dessus** via trois plugins, un par canal. C'est le principe d'architecture du projet :
*ne pas fusionner les paradigmes au niveau technique, unifier au-dessus* (voir
[architecture.fr.md](architecture.fr.md)).

```text
  agent / IDE
      │  (tools MCP : manage_session, execute_step, get_session_state, …)
      ▼
  rf-mcp  ── moteur RF générique : découverte, exécution, gen de suites, mémoire ──┐
      │                                                                            │
      │  charge les plugins (entry-point : robotmcp.library_plugins)              │
      ▼                                                                            ▼
  SapEccPlugin / SapFioriPlugin / SapApiPlugin  ──▶  SapEcc / SapFiori / SapApi Library  ──▶  SAP
   (routing · perception · guidance)        (les vrais keywords)
```

## Ce qu'apportent les plugins

`integrations/robotmcp/sap_robotmcp/` : bâtis sur les vrais contrats de plugin de
rf-mcp (`StaticLibraryPlugin`, `LibraryMetadata/Capabilities/Hints`, `PromptBundle`,
`LibraryStateProvider`), vérifiés contre rf-mcp **0.31.2** et re-validés contre
la **0.35.0** (2026-07-24 : `plugins/contracts.py` et `plugins/manager.py`
identiques octet à octet entre les deux ; la fenêtre du garde de démarrage de
la surcouche couvre 0.31–0.35).

| Hook rf-mcp | Apport SAP |
|-------------|------------|
| `get_keyword_library_map()` | Route les keywords SAP (`Click Ui5 Control`, `Run Transaction`, …) vers leur lib pour la découverte. |
| `get_hints()` / `get_prompt_bundle()` | **Guidage de sélecteurs SAP**, l'équivalent SAP manquant du `get_locator_guidance` de rf-mcp : adresser des contrôles UI5 pas des ids DOM ; vérifier le *type* de message de barre (E/S/W/I) pas le texte localisé ; jamais de `time.sleep` ; parler le vocabulaire métier de `resources/`. |
| `get_state_provider()` | **Perception d'écran** : expose l'écran SAP vivant comme « page source » de session, pour que l'agent *voie* avant d'agir. |

Aucun nouvel outil MCP n'est créé (le système de plugins ne le permet pas, et ce
n'est pas nécessaire) : l'agent lit l'état via `get_session_state` / un keyword de
perception, puis appelle directement les keywords SAP.

### Keywords de perception

Deux keywords en lecture seule exposent l'écran courant ; tous deux ont des
unit-tests off-SAP (`tests/unit/test_perception.py`) :

- **ECC** : `Get Screen Signature` (mixin `keywords/_perception.py`), vue texte de
  l'écran SAP GUI actif : entête `# screen <Programme>/<Transaction>/<Dynpro>` puis une
  ligne par contrôle (id relatif à la session, type, texte), champs éditables marqués `*`.
- **Fiori** : `Get Ui5 Page Tree`, la hiérarchie des contrôles UI5 sérialisée en XML
  (balise = type court, attributs = `id`, `controlType` plein, propriétés autorisées).
  Sonde jusqu'à ce que des contrôles soient montés ; ne renvoie jamais d'arbre vide.

Les deux acceptent **`mode=diff`** : seules les lignes qui ont changé depuis la
perception précédente (lignes préfixées `-`/`+`, plages inchangées résumées),
bien plus économe en contexte d'agent dans une boucle percevoir → agir → re-percevoir.

### Keywords orientés agent (0.2.0)

Les plugins routent aussi des keywords conçus pour la boucle perception → action :

- **Préflight** (ECC) : `Scripting Should Be Fully Enabled` échoue *tôt* avec le
  paramètre RZ11 exact à corriger (DisabledByServer / readonly / recording
  désactivé), au lieu de laisser l'agent découvrir un serveur à moitié activé
  keyword par keyword ; `Get Session Telemetry` expose temps de réponse /
  allers-retours.
- **Erreurs auto-corrigibles** : les échecs de résolution ECC ajoutent les ids les
  plus proches sur l'écran courant (scorés) ; les échecs role Fiori disent si des
  contrôles de ce *type* sont rendus ou non. Le texte d'erreur lui-même dit à
  l'agent quoi essayer ensuite.
- **Healing** : `Resolve Element With Healing` (ECC) et `Resolve Ui5 With
  Fallback` (Fiori, chaîne role→xpath→sid) : les deux réparent un localisateur
  périmé avec un WARNING journalisé, jamais en silence, et retournent des
  chaînes simples (MCP-safe : aucun objet COM ne traverse la frontière).
- **Iframes de launchpad** : `Set Ui5 Frame` pour les applications Work Zone/cFLP
  embarquées dans une iframe (éventuellement cross-origin).

Les hints de guidance (`get_hints()`) orientent l'agent vers ces keywords :
préflight en Suite Setup, `mode=diff` sur les perceptions répétées, keywords de
healing sur les échecs de localisation.

### La subtilité Fiori ⇄ Browser

`SapFioriLibrary` ne pilote **pas** la page ; elle réutilise la page vivante de la lib
**Browser** via `BuiltIn().get_library_instance('Browser')`. rf-mcp n'invoque un state
provider que pour la *lib d'automatisation web active*, résolue à **Browser** : le
provider Browser l'emporte donc et celui de Fiori est court-circuité pour la page source.
C'est voulu : la perception Fiori passe par le **keyword** `Get Ui5 Page Tree` + les
hints, pas par le provider. Le provider ECC, lui, *est* utilisé (SapEccLibrary est la
lib active sur une session desktop).

Ça marche parce que rf-mcp exécute chaque keyword dans **un seul contexte Robot
Framework partagé** par session : quand une session importe `Browser` et
`SapFioriLibrary`, ils vivent dans le même `Namespace`, donc
`get_library_instance('Browser')` résout la page vivante, exactement comme une suite
`.robot` classique. **Une session Fiori doit importer les deux libs et ouvrir une page
avant tout keyword UI5.**

### COM sur le thread de rf-mcp (ECC)

rf-mcp exécute les keywords hors du thread principal. L'API SAP GUI Scripting est COM
(STA) : ce thread doit appeler `CoInitialize` avant tout accès COM, sinon le moteur de
scripting lève *« CoInitialize n'a pas été appelé »*. `connect_to_session` est
surchargé dans `keywords/_connection.py` pour le faire (idempotent ; sans effet en run
Robot normal).

### Isolation des sessions

Les trois bibliothèques stateful utilisent `ROBOT_LIBRARY_SCOPE = SUITE`, ce qui
isole les suites Robot normales. rf-mcp 0.31 réutilise toutefois la même instance
Python entre ses tests synthétiques ; `sapfx_common.session_context` partitionne
donc les stores API cookies/CSRF/RFC et l'état frame/perception Fiori via le
contexte vivant `MCP_Test_<session_id>`. Des tests unitaires et live à deux
namespaces le prouvent. rf-mcp peut attribuer les appels ECC imbriqués dans une
resource au mauvais test synthétique : utiliser une session ECC live par process.

## Installation & vérification

```bash
pip install rf-mcp                      # le serveur MCP hôte
pip install -e .                        # rend SapEcc/SapFioriLibrary importables
pip install -e integrations/robotmcp    # enregistre les plugins (entry-points)

# vérifier que rf-mcp les découvre :
python -c "from robotmcp.config import library_registry as r; print([l for l in r.get_all_libraries() if 'Sap' in str(l)])"
```

Alternative sans installation : déposer un manifeste sous `.robotmcp/plugins/`
pointant la classe (`{"module": "sap_robotmcp.fiori_plugin", "class": "SapFioriPlugin"}`).

Pointez votre client MCP (Claude Code, un IDE, …) sur le serveur rf-mcp comme
d'habitude ; les libs SAP et le guidage sont alors disponibles dans toute session qui
les importe.

## Comment un agent l'utilise

**Fiori** (importer les deux libs, ouvrir une page, puis percevoir → agir) :

```text
manage_session  init   libraries=[Browser, SapFioriLibrary]
execute_step    New Browser      chromium
execute_step    New Page         <URL Fiori>
execute_step    Get Ui5 Page Tree            # percevoir l'arbre de contrôles
execute_step    Click Ui5 Control   controlType=Button  properties={'text': 'Save'}
```

**ECC** (desktop ; le state provider expose aussi l'écran via `get_session_state`) :

```text
manage_session  init             libraries=[SapEccLibrary]
manage_session  import_resource  resources/ecc_keywords.resource
execute_step    Open SAP And Log In   <conn> <user> <pwd> <client> <langue>
execute_step    Run Transaction       SE16
execute_step    Get Screen Signature              # percevoir l'écran
```

## Validation (end-to-end, à travers rf-mcp)

Des drivers rejouables dans `integrations/robotmcp/e2e/` appellent les vrais tools
rf-mcp (`manage_session` / `execute_step` / `get_session_state`) en process, comme un
agent, et vérifient tout le pipeline :

- `fiori_through_rfmcp.py` : **8/8** sur le fixture UI5 local (découverte du plugin,
  session à deux libs, routing, arbre UI5 peuplé, clic qui ouvre un dialogue).
- `ecc_through_rfmcp.py` : **9/9** sur un ABAP Platform A4H live sous Docker (login
  COM, routing, `Get Screen Signature`, et le **state provider** renvoyant la vraie
  signature d'écran SE16 live).

Voir aussi [fiori-architecture.fr.md](fiori-architecture.fr.md),
[architecture.fr.md](architecture.fr.md), et `integrations/robotmcp/README.md` pour le
démarrage rapide.
