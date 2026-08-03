# CLAUDE.md

Guidance for AI assistants working in this repo. Keep it accurate — update it when
structure or conventions change.

## Language / Langue

**Respond to the user in French**, and write user-facing documents in French. The
project maintainer is French-speaking and requested this. Docs are kept
bilingual: an English original plus a `*.fr.md` French version with cross-link
banners — preserve that pattern. Do **not** translate code, identifiers, Robot
Framework keyword names, CLI commands, JSON, or proper nouns (SAP, Fiori, UI5,
Playwright…). This CLAUDE.md and git commit messages may remain in English.

## Memory

Durable project facts live in `memory/` at the repo root (index
`memory/MEMORY.md`, rules in `memory/README.md`; French, single-language by
design): costly debugging lessons, decisions with their context — written
**anonymized**: no personal data, no machine paths, no private URLs. Entries
are dated observations, not live state — verify before asserting. One fact
per file, update the index in the same operation, never secrets anywhere.

## What this is

A SAP test-automation ecosystem for Robot Framework, in two phases:

- **Phase 1 (in progress): `SapEccLibrary`** — SAP GUI desktop-client (ECC, S/4HANA
  backend GUI) library. A hardened fork of
  [robotframework-sapguilibrary](https://github.com/frankvanderkuur/robotframework-sapguilibrary)
  (Apache 2.0), driven via the SAP GUI Scripting API over COM (`win32com`).
- **Phase 2 (validated): `SapFioriLibrary` + web Spy.** SAP Fiori / S/4HANA
  (SAPUI5) web automation. Sits next to the Browser library (Playwright). Injects a
  JS bundle (`_ui5_js.py`, `window.__SAPFX`) with three resolution engines, all
  polling until rendered:
  - **role**: registry scan matching controlType (short/full), properties
    (case-insensitive substring or `/regex/`), id, bindingPath, viewId. Returns
    `css=[id="<controlId>"]`.
  - **xpath**: builds an XML tree of the control hierarchy and runs XPath over it →
    hierarchical locators like `//Table//Button[@text='Edit']`. `Get Ui5 Xpath`
    returns the **shortest unique** xpath for a control.
  - **wc** (`Resolve/Click/Fill Wc…`): light-DOM scan of `ui5-*` custom elements for
    **UI5 Web Components** pages WITHOUT a classic UI5 runtime (SuccessFactors home)
    — registry empty, role/xpath blind. `tag=Button` matches plain AND scoped tags
    (`ui5-button-<suffix>`); returns CSS light-DOM paths (WC hosts often have no id);
    Playwright's CSS pierces the open shadow roots for click/fill.
  Also a **WebGUI `sid` engine** (`Resolve/Click/Fill Sid…`) for classic SAP GUI for
  HTML pages (non-UI5): matches the stable `SID` in each element's `lsdata` attribute.
  The tree/XPath/shortest-xpath/matcher/drill/allowlist/sid are **ported from playwright-sap**
  (Apache-2.0; attribution in `NOTICE` + `_ui5_js.py` header). Smoke passes end-to-end
  vs the live OpenUI5 Demo Kit (RF 7.4.2 / Browser 20). Recorders: `tools/recorder`
  (desktop, COM) and `tools/recorder_web` (emits role + xpath keyword lines).
  NB: `RecordReplay.findDOMElementByControlSelector` was tried and abandoned — it
  throws internally outside the OPA5 pipeline on current UI5.

The unifying idea: don't merge the two paradigms at the technical layer — unify
**above**, in Robot Framework business keywords (`resources/`). See
[docs/architecture.md](docs/architecture.md).

## Layout

| Path | Role |
|------|------|
| `src/SapEccLibrary/_vendor/sapgui_base.py` | Upstream code, **vendored verbatim**, class renamed `SapGuiLibrary`→`SapGuiBase`. Read-only. |
| `src/SapEccLibrary/keywords/_connection.py` | Mixin: launch Logon Pad, retry connect, `connect_to_session` override (`CoInitialize` for off-main-thread execution, e.g. rf-mcp), et `Attach To Open Session` (rattache moteur + connexion + session par INDEX à une session déjà ouverte — le prérequis de replay des suites générées par le recorder ; `Connect To Session` seul n'obtient que le moteur). |
| `src/SapEccLibrary/keywords/_waits.py` | Mixin: `session.Busy` + element polling waits, plus le réglage dynamique `Set Default Timeout`/`Set Poll Interval` (retournent l'ancienne valeur, restaurable en teardown ; portée = l'instance, scope `SUITE`). |
| `src/SapEccLibrary/keywords/_grid.py` | Mixin: ALV grid by column title, `Read Grid`, adressage de ligne par contenu (`Get Cell Value By Row Content`), et `Read Abap List` (sorties liste classiques sans objet grille — reconstruction géométrique via `sapfx_common.abap_list`, mode accessibilité SAP GUI conseillé). |
| `src/SapEccLibrary/keywords/_perception.py` | Mixin: `Get Screen Signature` (`mode=diff` → différentiel, `pair_renames=True` → **diff intelligent** appariant les ids renommés via le scoring de healing ; `mode=semantic` → **vue formulaire** : une ligne par cible actionnable avec libellé humain vérifié + id + valeur ; `include_geometry` → 4e colonne optionnelle) — read-only text view of the active screen (locator debugging + rf-mcp agent plugin). Aussi `Get Open Windows` (pile de fenêtres JSON-safe, `modal=True` sur les GuiModalWindow — le garde-fou du piège SESSION_MANAGER : `Run Transaction` peut rapporter un succès alors qu'un modal d'erreur est resté ouvert). Chemin rapide `GetObjectTree` (un appel COM pour tout le sous-arbre, repli marche COM automatique) via `_screen_elements`, le parcours structuré partagé avec healing/sémantique. Aussi `Get Screenshot As Base64` (`HardCopyToMemory`, MIME vérifié par magic bytes, MCP-safe), `Log Screenshot` (data-URI inline dans le log Robot), le **screenshot annoté Set-of-Mark** (`Get/Log Annotated Screenshot` — boîtes numérotées sur les cibles actionnables + légende `numéro -> id` : l'agent vision lit le numéro, l'id part dans un keyword déterministe), la **carte numérotée + action par référence** façon `map`/`@e1` de Vibium (`Get Screen Map` → une ligne `@N` par cible actionnable avec libellé/id/valeur ; `Resolve/Click/Fill Screen Ref` agissent par numéro — références éphémères de la dernière perception, re-vérifiées avant chaque action : écran changé ou élément disparu = échec actionnable nommant `Get Screen Map` ; la légende du screenshot annoté alimente la même table ; réservé au pilotage interactif, jamais dans une suite), et l'**assertion visuelle** `Get Screen Perceptual Hash`/`Screen Should Match Baseline` (dHash pur dans `sapfx_common.visual_hash`, sémantique snapshot partagée dans `sapfx_common.visual_baseline`, Pillow à la frontière — extra `visual` ; `mask_elements=auto` neutralise sbar/titl avant hachage) + sa déclinaison **par élément** `Get Element Perceptual Hash`/`Element Should Match Baseline` (baseline = PNG recadré sur l'élément — les 64 bits couvrent la seule zone opaque visée) et `Get Screen Tile Hashes` (grille 4×4 d'empreintes — la dérive se localise). |
| `src/SapEccLibrary/keywords/_diagnostics.py` | Mixin: préflight scripting **serveur** (`Get Scripting Status`, `Scripting Should Be Fully Enabled` — DisabledByServer / readonly / recording_disabled, avec le paramètre RZ11 à corriger et la piste `per_user`/S_SCR), préflight **poste** (`Get List Rendering Status`, `Abap List Should Be Readable` — détecte le rendu shell-sans-labels et nomme le mode accessibilité SAP GUI à provisionner ; un shell AVEC labels = ALV légitime, rien à corriger), préflight **posture de sécurité du poste** (`Get Client Security Status`, `Client Security Should Be Hardened` — client patché contre la CVE-2025-0055 de l'historique de saisie (corrigée en 8.00 PL9+, note SAP 3472837), bases `SAPHistory*.db` présentes à purger ; logique pure dans `sapfx_common.client_security` ; guide : [docs/hardening-test-environment.md](docs/hardening-test-environment.md)), `Enable Test Tool Mode`, `Get Session Telemetry`. |
| `src/SapEccLibrary/keywords/_healing.py` | Mixin: auto-réparation de localisateurs — `Resolve Element With Healing` (répare au-dessus d'un seuil avec WARNING journalisé, jamais silencieux ; `label=<libellé>` ajoute la voie **ancre de libellé**, adoptée seulement si le libellé re-résout vers UN élément, télémétrie `engine=label` ; retourne une chaîne, MCP-safe) et `Get Closest Element Ids`. Le scoring pur vit dans `sapfx_common.healing` ; chaque réparation alimente aussi le journal `SAPFX_HEALING_LOG` (`sapfx_common.healing_telemetry`). |
| `src/SapEccLibrary/keywords/_semantic.py` | Mixin: **localisateurs humains** (portés de RoboSAPiens, Apache-2.0 — NOTICE) — `Find Element By Label`, `Fill Field By Label`, `Read Field By Label`, `Click Button By Label` : libellé visible + proximité géométrique (grammaire `Libellé`, `@ Libellé` = dessous, `Gauche @ Haut` = intersection, `= contenu`, `N @ Libellé`/`Libellé @ N` = grille verticale/horizontale par position, `Ancre >> Reste` = portée réduite au voisinage d'un libellé unique ; `exact=False` = préfixe insensible à la casse, pensé pour les tooltips finissant par le raccourci). Ambiguïté toujours remontée avec la liste des candidats — jamais de premier-match silencieux ; les ids restent le chemin nominal dans `resources/`. Moteur pur dans `sapfx_common.semantic`. Aussi `Lookup Business Term` (terme métier FR/EN → champ ABAP/table — `sapfx_common.vocabulary`, même contrat d'ambiguïté). |
| `src/SapEccLibrary/keywords/_embedded_browser.py` | Mixin: pont **contrôle-navigateur-embarqué** (WebView2/CDP, workflow documenté par RoboSAPiens — NOTICE) — `Enable Embedded Browser Debugging` (positionne `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` avant `Open Sap Logon`), `Get Embedded Browser Page Id`/`Switch To Embedded Browser Page` (retrouvent puis activent, via la bibliothèque Browser sur CDP, la page hébergée par un contrôle WebView2 embarqué dans une fenêtre SAP GUI/Business Client). Même accès `BuiltIn().get_library_instance("Browser")` que `SapFioriLibrary` ; suite doit importer `Library    Browser`. |
| `src/SapEccLibrary/keywords/_pointer.py` | Mixin: **effecteur coordonnées** — le repli hybride « déterministe d'abord, geste matériel en dernier recours » pour les zones officiellement hors API (intérieur des GuiShell opaques, GuiChart, drag & drop) : `Get Element Screen Region` (ScreenLeft/ScreenTop — la moitié perception, à croiser avec `Get Screenshot As Base64` par un agent) et `Click Element At Offset` (clic win32 à une position RELATIVE dans l'élément, left/right/double, fenêtre mise au premier plan best-effort, point cliqué journalisé). Validé live : clic matériel sur `btn[31]` → popup de comptage ouvert. |
| `src/SapEccLibrary/keywords/_sessions.py` | Mixin: **registre multi-session par alias** — `Open Sap Session` (nouvelle connexion par chaîne/entrée Logon, login optionnel `RSYST-*` avec `password` de type `Secret` jamais journalisé, rollback d'alias sur échec), `Create Gui Session` (2e fenêtre sur la connexion active — l'équivalent `/o` scripté, AUCUN re-login donc jamais de popup multi-logon : la voie recommandée pour « écrire dans une session, vérifier dans l'autre »), `Switch/List/Close/Close All Sap Sessions`, `Get Active Sap Session`. Multi-session = **multiplexage** (une session active, bascule explicite), jamais du parallélisme de threads ; l'état `session`/`connection` est routé par alias dans `SapEccLibrary.py` (compat totale : l'usage historique vit dans l'alias `default`), avec le rail **STA** : thread COM propriétaire mémorisé par alias, accès cross-thread = `CoInitialize` défensif (mode marshaling dont dépendent les state providers rf-mcp), `SAPFX_STRICT_COM_THREAD=1` = erreur actionnable à la place. Teardown isolé : fermer un alias ne touche ni les autres ni une connexion encore partagée. |
| `src/SapEccLibrary/SapEccLibrary.py` | Composes mixins + base; locale-safe `Run Transaction`; routage `session`/`connection` par alias actif + garde de thread COM (`_touch_com_thread`). |
| `src/SapFioriLibrary/_ui5_runtime.py` | UI5 control-selector model (pure data, unit-tested). |
| `src/SapFioriLibrary/_ui5_js.py` | Injected `__SAPFX` JS bundle: control tree, XPath + role engines, shortest-xpath, matcher, capture, WebGUI sid (ported from playwright-sap), generic DOM engine (`resolveByDom` + `captureDom` pour le recorder), page-composition probe (`pageComposition`). Also generates the Recorder snippet. |
| `src/SapFioriLibrary/regen_recorder.py` | `python -m SapFioriLibrary.regen_recorder` → writes the generated Recorder to BOTH `tools/recorder_web/recorder_snippet.js` and `tools/recorder_web/extension/recorder.js`. |
| `tools/recorder_web/extension/` | MV3 extension: popup (Start/Rec/Export/Stop) + `background.js` (`Alt+Shift+R` shortcut, `REC` badge) inject `recorder.js` (MAIN) + `bridge.js` (ISOLATED, badge relay) via `chrome.scripting`+`activeTab`. Draggable/collapsible capture+record panel; `PRIVACY.md`; store zip (`package.py`, `PUBLISHING.md`). |
| `src/SapFioriLibrary/SapFioriLibrary.py` | Role/XPath/shortest-xpath resolution + WebGUI sid + moteur WC (`Resolve/Click/Fill Wc…`, pages UI5 Web Components hors registre) + **moteur DOM générique** (`Resolve/Click/Fill Dom…`, 5e moteur : les zones NON-SAP d'une page hybride — widget React/Angular/vanilla — entrent dans la même grammaire, CSS+texte+rôle ARIA **calculé** (explicite ou implicite via la sémantique HTML)+**nom accessible** `name=` (accname simplifié : aria-labelledby/label/label[for]/alt/texte — le localisateur « intention utilisateur », façon `getByRole(name=…)`)+attributs, chemins light-DOM ; `name=` existe aussi côté **wc**, où il lit la convention UI5 Web Components `accessible-name`/`accessibleName`) ; click/fill/get convenience. **Pages hybrides** : `Get Page Composition` (sonde de perception — quelles technologies cohabitent où : runtime UI5/WC/lsdata/frameworks + moteurs recommandés par région, descente d'un niveau dans chaque iframe, best-effort) et la **pile de frames** `Push/Pop Ui5 Frame` (frames IMBRIQUÉES, portée chaînée `a >>> b`) au-dessus de `Set Ui5 Frame` (apps en iframe Work Zone/cFLP — évaluation dans la frame + sélecteurs préfixés `>>>` ; remplace toute la pile). `Resolve Ui5 With Fallback` (chaîne role→xpath→sid→wc→dom, réparation journalisée + télémétrie), `idSuffix` (ids stables Fiori Elements `fe::…`), `Ui5 Text Should Be`, `Get Ui5 Page Tree mode=diff`, le **miroir Fiori de la carte numérotée** (`Get Ui5 Page Map` → cibles actionnables `@N` de l'arbre UI5, logique pure `ui5_page_map` dans `_ui5_runtime.py` ; `Resolve/Click/Fill Ui5 Ref` agissent par numéro — fraîcheur re-vérifiée au registre rendu, échec actionnable nommant la re-perception ; éphémère, pilotage interactif seulement), et la **parité du canal visuel** : `Get Ui5 Perceptual Hash` + `Ui5 Screen Should Match Baseline` (capture Browser `return_as=bytes` avec repli fichier, même cycle snapshot que l'ECC via `sapfx_common.visual_baseline`). **Couche diagnostic** `Get Fiori Diagnostics`/`Log Fiori Diagnostics` : UN dict JSON-safe agrégeant composition hybride + arbre UI5 (sondé `tree_timeout` court, sans toucher l'état `mode=diff`) + erreurs console/page normalisées (briques Browser 20, incrémental par défaut, troncature annoncée) + snapshot ARIA des zones non-SAP (portée frame respectée) — chaque section best-effort (`collection_errors`), synthèse `issues` actionnable (arbre absent → moteurs/frames de repli nommés), rapport Markdown pour le log (cœur pur `sapfx_common.fiori_diagnostics`). Aussi (portés de playwright-praman — NOTICE) : `Open Fiori App` (navigation FLP par **intent** `SemanticObject-action` — le hash stable, cross-catalogue/thème/langue ; la resource `Open App By Intent` enchaîne le Wait For UI5 Ready), `Log In Via Identity Provider` (formulaires IDP sap-ias/azure-ad/generic, une-page et deux-étapes) et `Lookup Business Term` (vocabulaire métier partagé). NB appel Python interne : les états Browser passent en enum via `_wait_visible` (la conversion d'arguments RF n'existe pas via `get_library_instance` — leçon live du smoke hybride). Réglage dynamique `Set Ui5 Timeout`/`Set Poll Interval` (miroirs de l'ECC — ancienne valeur retournée, restaurable en teardown) ; les échecs génériques (fallback épuisé, arbre UI5 absent) nomment `Log Fiori Diagnostics`/`Get Page Composition`. |
| `src/sapfx_common/polling.py` | Shared sync primitives (`poll_until`/`retry_call`/`retry_until`) used by BOTH libraries — add new wait/retry loops here, not inline. Typed (`mypy`-checked). |
| `src/sapfx_common/com_safety.py` | `ensure_com_initialized()` — defensive `CoInitialize` on the current thread, shared by `ConnectionKeywords.connect_to_session` (ECC) and the rf-mcp state providers' `run_keyword_in_context` (avoids `RPC_E_WRONG_THREAD` off the main thread). Typed. |
| `src/sapfx_common/healing.py` | Scoring pur d'auto-réparation (partagé ECC↔Fiori) : similarité d'ids SAP GUI — segment terminal lourdement pondéré + LCS caractère sur le chemin + type (un sous-écran renuméroté `SAPLMEGUI:0013`→`:0015` reste réparable) ; `closest_gui_ids` / `format_suggestions` (erreurs auto-corrigibles). Typed. |
| `src/sapfx_common/perception_diff.py` | Diff ligne à ligne entre deux perceptions (lignes `-`/`+`, inchangé résumé) — socle du `mode=diff` des deux keywords de perception. `pair_renames=True` = **diff intelligent** : les paires disparue/apparue dont les ids se ressemblent (scoring `sapfx_common.healing`, seuil 0.6) deviennent `~ ancien -> nouveau (similarité N%)` — ou `texte : 'a' -> 'b'` à id constant ; toujours actif dans la sentinelle. Typed. |
| `src/sapfx_common/healing_telemetry.py` | Journal JSONL **cumulatif** des réparations de localisateurs (opt-in `SAPFX_HEALING_LOG=<chemin>`), alimenté par les deux canaux (ECC avec score, Fiori avec moteur de repli) — relu sur plusieurs runs, il révèle les localisateurs qui dérivent de façon récurrente. Best-effort : ne fait jamais échouer un test, ne consigne jamais de valeur saisie. Typed. |
| `src/sapfx_common/object_tree.py` | Aplatissement du JSON de `GuiSession.GetObjectTree` en `ScreenElement` (id/type/texte/tooltip/éditabilité/géométrie) — **un appel COM** pour tout le sous-arbre au lieu d'un par nœud ; nombres-en-chaînes et `Changeable` texte normalisés. Le modèle structuré partagé perception ↔ healing ↔ sémantique ↔ recorder. Typed. |
| `src/sapfx_common/semantic.py` | Moteur de **localisateurs humains** (porté de RoboSAPiens, Apache-2.0 — NOTICE) : résolution par libellé visible + géométrie (droite/dessous/intersection/contenu, grille par position `N @ Libellé`/`Libellé @ N`, portée `Ancre >> Reste` réduite au voisinage d'un libellé unique — récursive, tolérances paramétrables), `resolve_semantic` retourne TOUS les matches (ambiguïté tranchée par l'appelant, jamais en silence) ; `describe_element` = l'inverse **vérifié** pour le recorder (un libellé n'est émis que s'il re-résout vers le même élément ; la valeur d'un champ de saisie n'est jamais un localisateur). Aussi la **perception sémantique** : `is_editable_field` (le vrai SAP GUI marque `Changeable=True` sur GuiUserArea et des boutons de toolbar — constaté live, `changeable` seul ne suffit jamais), `actionable_targets` et `screen_affordances` (la vue formulaire du `mode=semantic` — partagée avec le screenshot annoté). Typed. |
| `src/sapfx_common/abap_list.py` | Reconstruction géométrique d'une **liste ABAP classique** (labels positionnés → lignes/cellules texte) — socle de `Read Abap List` (SE38, SE16 sans ALV : aucun objet grille scriptable). Typed. |
| `src/sapfx_common/visual_hash.py` | Hash perceptuel d'écran (dHash) **pur** (matrices de gris, aucune dépendance image) — cœur des keywords `Get Screen Perceptual Hash` / `Screen Should Match Baseline` de `_perception.py`. Aussi les primitives de **précision** : `crop_pixels` (hash de LA région d'un élément), `mask_regions` (neutraliser les zones volatiles — sbar/titl — avant hachage), `tiled_dhash`/`tiled_hamming`/`tile_rect` (une empreinte par tuile d'une grille → dérive localisée). Pillow reste à la frontière (`_decode_image_to_gray`, extra `visual`). Couvre ce que l'API Scripting ne voit pas (GuiShell opaques, charts record-only). Typed. |
| `src/sapfx_common/visual_baseline.py` | Sémantique **snapshot** des baselines visuelles, partagée ECC↔Fiori : 1er passage = baseline créée (WARNING, PNG à committer), ensuite distance de Hamming vs seuil, `.actual.png` sauvé en cas de dérive, échec auto-corrigible nommant le sujet (`L'écran`/`L'élément <id>`/`La page`) ; `validate_snapshot_name` (anti path-traversal) et `decode_image_to_gray` (la frontière Pillow commune aux deux canaux). Typed. |
| `src/sapfx_common/screen_watch.py` | **Sentinelle de dérive** pure — détecter qu'un écran a changé SANS test scripté : `compare_watch` croise le diff structurel **intelligent** (renommages appariés) et la distance visuelle (empreinte optionnelle — utilisable sans Pillow) ; le canal **tuiles** s'y ajoute (`locate_tile_drift` nomme la tuile — position, rectangle, éléments recouvrants — et `apply_tile_verdict` fait foi même quand le hash global reste sous le seuil : c'est le cas dilué que les tuiles rattrapent) ; `render_watch_report` = rapport Markdown des dérives. E/S dans le keyword `Check Screen Against Watch` (`_perception.py` : 1re visite = référence à committer — signature + dhash + tiles, ensuite chaque écart nommé, `fail_on_drift` optionnel, verdict dict MCP-safe). Harnais de veille : `tests/robot/ecc_drift_sentinel.robot`. Typed. |
| `src/sapfx_common/client_security.py` | Posture de sécurité du **poste client** SAP GUI, logique pure : classification CVE-2025-0055 de la version/patch du client (`input_history_cve_status` — historique de saisie chiffré en XOR statique, corrigé 8.00 PL9+), scan best-effort des bases d'historique `SAPHistory*.db` aux emplacements connus (`find_history_databases`). Socle des keywords `Get Client Security Status` / `Client Security Should Be Hardened` (`_diagnostics.py`). Typed. |
| `src/sapfx_common/vocabulary.py` | **Vocabulaire métier** partagé ECC↔Fiori (concept porté de playwright-praman, Apache-2.0 — NOTICE) : terme métier FR/EN + synonymes → fiche {canonique, champ ABAP, table, domaine} ; barème exact > synonyme/champ > préfixe > flou, `lookup_term` refuse sous le seuil OU en ambiguïté (candidats listés, jamais de premier-match silencieux) ; vocabulaire livré MM/SD/FI + modèle Flight, extensible par `extra` (Z-champs site). Exposé par `Lookup Business Term` (les DEUX bibliothèques, dict MCP-safe). Typed. |
| `src/sapfx_common/auth_flows.py` | **Presets IDP** (concept porté de playwright-praman — NOTICE) : fiches de sélecteurs des formulaires de connexion (sap-ias, azure-ad, generic — chaque sélecteur surchargeable, preset inconnu = erreur listant les valides). Le pilotage vit dans `Log In Via Identity Provider` (SapFioriLibrary) : déroulés une-page ET deux-étapes détectés dynamiquement, comptage en VISIBILITÉ (`>> visible=true` — un formulaire deux-étapes garde son champ mot de passe caché dans le DOM), échec nommant l'étape bloquante, mot de passe jamais journalisé. Typed. |
| `src/sapfx_common/fiori_diagnostics.py` | Assemblage pur du **diagnostic Fiori agrégé** (`Get/Log Fiori Diagnostics`) : validation des sections, normalisation JSON-safe des entrées console/erreurs de page (briques Browser 20), troncature toujours annoncée, synthèse d'anomalies **actionnable** (arbre UI5 absent → moteurs/frames de repli nommés) et rapport Markdown. Les E/S Browser restent dans le keyword. Typed. |
| `src/SapApiLibrary/SapApiLibrary.py` | Le canal **API** (3e canal, stdlib pure — zéro dépendance nouvelle) : OData v2 (Gateway embarquée) ET v4 (CAP/S4) avec les mêmes keywords (`Open Api Session` par alias, `Get Odata Entities`, `Get Odata Count`, `Post Odata` avec protocole CSRF SAP), RFC optionnel via pyrfc (`Open Rfc Connection`/`Call Rfc`, erreur actionnable sinon), et `List Api Sessions` (état JSON-safe du canal : alias/base_url/sap-client/authentifié — jamais de credentials ; la « perception » du canal sans écran, consommée par `SapApiPlugin`). Patron recommandé : préparer/recouper les données par l'API, ne piloter l'écran que pour ce qu'on teste (voir la suite flagship). Typed (périmètre mypy). |
| `resources/ecc_keywords.resource` | ECC business-readable keywords tests should call. Includes SE16/SE38 helpers (`Display Table Contents`, `Run Report`, `Use ALV Grid In Data Browser`), SE16 exploration keywords (`Count Table Entries`, `Read Domain Values`, `List Repository Tables`, `Try Open Table Selection Screen`) and filtered-selection/grid-assertion keywords (`Display Table Contents With Filter` sur dictionnaires `<TABLE>_SELECTION_FIELDS` relevés live, `Count Flight Connections For Airline`, `Displayed Grid Should Contain Columns`, `Read Column Values From Displayed Grid`). |
| `resources/fiori_keywords.resource` | Fiori business keywords — **mirrors** the ECC vocabulary: same-name aliases (`Open SAP And Log In`, `Popup Is Present`, `Confirm/Cancel Popup`, `Close SAP`) + mapping table in its Documentation; only `Go To Transaction` ↔ `Open App` diverges (assumed). Aussi `Open App By Intent` (navigation FLP stable par hash d'intent + Wait For UI5 Ready). |
| `resources/a4h_demo_data.resource` | A4H demo-data guards: `Ensure Flight/EPM Demo Data Exists` (conditional SAPBC_DATA_GENERATOR / SEPM_DG). |
| `tests/unit/` | Off-SAP / off-browser logic tests (fake COM, UI5 selector logic). |
| `tests/manual/check_sap_gui_connection.py` | Manual COM sanity probe (SAP GUI reachable, scripting on). Not run by pytest. |
| `tests/robot/ecc_smoke.robot` | ECC smoke; needs a real/trial SAP system. |
| `tests/robot/fiori_smoke.robot` | Fiori smoke; runs vs the public OpenUI5 Demo Kit. |
| `tests/robot/ecc_data_smoke.robot` | **Data-driven** ECC smoke (live A4H): guarantees SFLIGHT/EPM data then reads guaranteed-non-empty grids. Locale-safe: asserts technical column ids (`CARRID`), never displayed titles. |
| `tests/robot/ecc_exploration.robot` | **Exploration campaign** (live A4H): locks the delivery/table-class catalogs (DD07L domains), inventories flight + EPM tables via TADIR, then deep-verifies every object through SE16 « Number of Entries » (structures classified by status type `E`). Sweeps tagged `deep`. |
| `tests/robot/business_data_exploration.robot` | Variante **AUTONOME** de la campagne d'exploration (zéro dépendance à `resources/` — déroge volontairement à la convention 1, voir son en-tête) : l'exemple « données réelles » embarqué dans le pack de déploiement, rejouable sans le dépôt. Le pendant conforme aux conventions est `ecc_exploration.robot`. |
| `tests/robot/ecc_scarr_spfli_liaisons.robot` | Suite SCARR/SPFLI via SE16 (live A4H), générée depuis `specs/scarr-spfli-liaisons-se16.md` par sap-generator : 7 scénarios en assertions relationnelles (comptes > 0, LH > AA > 0, somme des comptes filtrés par CARRID = total, porteurs ⊂ catalogue, lecture ciblée LH 0400). Exerce les keywords de sélection filtrée. |
| `tests/robot/ecc_multisession_smoke.robot` | Smoke **multi-session** (live A4H) auto-suffisant : `Create Gui Session` (2e fenêtre, même connexion, zéro re-login), multiplexage `Switch Sap Session` (transactions indépendantes entre alias), `List Sap Sessions` (JSON-safe), `Close Sap Session` (teardown isolé — la session survivante reste pilotable). Validé live 4/4 (2026-07-17), après le même cycle déroulé pas-à-pas via rf-mcp. |
| `tests/robot/exploratory_campaign_a4h.robot` | **Campagne exploratoire ECC** auto-suffisante (importe `SapEccLibrary` directement, aucune resource/suite du projet réutilisée) : inventaire des classes de livraison (domaine `CONTFLAG`/DD07L → A/C/E/G/L/S/W), cycle d'écriture CRUD **réversible** sur SCARR (SE16 « Create Entries » depuis l'écran INITIAL → relecture → Delete → retour à 0, aucune trace), et **balayage dynamique du catalogue** TADIR (packages Flight `SAPBC_DATAMODEL` + EPM `S_NWDEMO_MODEL_DDIC`, classification table réelle vs structure de type E + comptage). Validée live 4/4 vs A4H (2026-07-17). |
| `tests/robot/fiori_sflight_smoke.robot` | Fiori Elements smoke vs **local cap-sflight** (`_cap-sflight/`, `npx cds watch` → :4004). No SAP, no network. |
| `tests/robot/fiori_legacy_smoke.robot` | **UI5 1.60 (pre-`Element.registry`)** compat smoke — real legacy runtime from the jsDelivr npm mirror; proves the `registryForEach` DOM fallback. Network, no SAP. |
| `tests/robot/fiori_ui5v2_smoke.robot` | **UI5 2.0 nightly** compat smoke (CDN officiel `sdk.openui5.org/nightly/2`) : prouve la branche module `ElementRegistry` et l'absence de dépendance aux APIs supprimées en 2.x (`sap.ui.getCore()`, `Element.registry`, `sap.ui.version`). Pendant symétrique du smoke legacy. NB : UI5 2.0 **abandonné** (keynote UI5con 07/2026 — la voie officielle est la ligne 1.x legacy-free) : sentinelle non bloquante tant que le CDN nightly/2 répond, la cible d'avenir est le smoke 1.136-legacy-free. Réseau (nightly = instable par nature), no SAP. |
| `tests/robot/fiori_legacyfree_smoke.robot` | **UI5 1.136 legacy-free** compat smoke (CDN `sdk.openui5.org/1.136-legacy-free` — la LTS officielle SANS APIs dépréciées, le véhicule SAP de préparation 2.x tant que 2.0 n'est pas GA) : garde-fou `sap.ui.getCore` absent + branche module `ElementRegistry`. Contrairement au nightly, cible STABLE : un échec = vraie régression. Complète le triptyque 1.60 ← 1.136-legacy-free → 2.0-nightly. Réseau, no SAP. |
| `tests/robot/fiori_csp_smoke.robot` | Smoke **injection sous CSP stricte** vs `fixtures/csp_fixture.html` (script-src CDN+nonce, sans unsafe-inline/unsafe-eval) : prouve d'abord que la politique bloque un `<script>` sans nonce, puis que le bundle `__SAPFX` (evaluate Playwright → CDP, hors de portée de la CSP de page) et les moteurs role/xpath fonctionnent quand même — aucun assouplissement CSP à demander sur un système testé (cf. docs/hardening-test-environment.md §4). Réseau, no SAP. |
| `tests/robot/fiori_frame_smoke.robot` | **Iframe launchpad** smoke (`Set Ui5 Frame`) vs `fixtures/shell_iframe_fixture.html` — shell sans UI5 embarquant l'app dans une iframe réellement cross-origin (structure Work Zone/cFLP). Aussi les scénarios de fragilité observés chez wdi5 (2 correctifs iframe fin 2025/début 2026), vs `fixtures/shell_multi_iframe_fixture.html` : DEUX apps en frames (portée jamais partagée), rechargement de frame (zéro contexte périmé), navigation de frame vers une autre app (re-résolution). NB harnais : `Go To` et non `New Page` dans les tests — l'auto-closing TEST de Browser referme les pages ouvertes pendant un test. Réseau, no SAP. |
| `tests/robot/fiori_wc_smoke.robot` | Smoke du **moteur Web Components** vs `fixtures/wc_fixture.html` (page « pur WC » sans runtime UI5, tags scopés, shadow roots ouverts, capture recorder, nom accessible `name=` — attribut `accessible-name` ET propriété `accessibleName`). Hors ligne : no SAP, no network. |
| `tests/robot/fiori_hybrid_smoke.robot` | Smoke des **sessions hybrides** vs `fixtures/hybrid_fixture.html` (page composite sans runtime UI5 : hôtes WC + élément WebGUI `lsdata` + widget React + frames imbriquées level1→level2 en srcdoc) : `Get Page Composition` (technologies + moteurs par région, descente dans les frames), moteur DOM générique (résolution/clic/saisie de la zone non-SAP, localisateurs d'accessibilité `role=` implicite + `name=` aria-label/label[for]), pile `Push/Pop Ui5 Frame` sur DEUX niveaux (sid au niveau 1, dom au niveau 2), pop-de-trop = erreur nette, repli `dom=` de la chaîne de fallback. Le run live a attrapé un bug préexistant (`Sid Should Be Visible` passait l'état en chaîne à l'API Python interne de Browser — KeyError). Validé 5/5. Hors ligne : no SAP, no network. |
| `tests/robot/fiori_auth_smoke.robot` | Smoke **authentification IDP** vs `fixtures/idp_login_fixture.html` (IDP factice DEUX ÉTAPES aux ids sap-ias) : `Log In Via Identity Provider` atterrit dans l'app UI5, mauvais mot de passe = échec nommant le formulaire, preset inconnu = refus listant les presets. Réseau (CDN pour l'app cible), no SAP, no vrai IDP. |
| `tests/robot/webgui_smoke_sid.robot` | Smoke **WebGUI (SAP GUI for HTML) au moteur sid**, généré par le cycle agents plan→generate depuis `specs/webgui-smoke-sid.md` et validé live **4/4** vs A4H : login ITS au moteur dom (localisateurs `role=`/`name=`), lancement de transaction par le paramètre d'URL `~transaction` (champ OK-code masqué par défaut, réglage non persistant), comptage SE16 T000 de bout en bout par sid (`wnd[1]/usr/txtG_DBCOUNT`), log off par le menu System. Keywords métier WebGUI dans `resources/fiori_keywords.resource` (`Open WebGui`, `Go To WebGui Transaction`, `Count WebGui Table Entries`…). Prérequis : service ICF `webgui` actif (voir field notes). Réseau local (A4H Docker). |
| `tests/robot/exploratory_campaign_fiori.robot` | **Campagne exploratoire Fiori** auto-suffisante (importe `Browser` + `SapFioriLibrary` directement), **navigateur visible** (`headless=False`) sur l'OpenUI5 Demo Kit : acceptation de la bannière cookies TrustArc (élément DOM `truste-consent-button`, id stable locale-indépendant), inventaire des types de contrôles (`Get Ui5 Page Tree`), interaction **réversible** (remplir/relire/vider un SearchField), **balayage dynamique** — convergence role↔xpath sur TOUS les types découverts —, et grammaire de localisateurs (ancestralité `//Page//SearchField` + prédicat `@controlType`). Le run live a attrapé un bug de timing (arbre capté avant rendu de l'app → attente d'un contrôle rendu dans le setup). Validée live 6/6 (2026-07-17). Réseau, no SAP. |
| `tests/robot/ecc_record_smoke.robot` | Desktop recorder **record-engine** smoke (live A4H); recorder imported as a Library by path. |
| `tests/robot/recorder_web_smoke.robot` | Web recorder **record-mode** smoke vs `tests/robot/fixtures/ui5_fixture.html` (Chromium). |
| `tests/robot/flagship_cross_paradigm.robot` | Suite **flagship cross-paradigme** : le même fait métier vérifié par DEUX canaux indépendants — tag `a4h` (compte SE16 de `SNWD_PD` = `$count` OData `SEPMRA_SHOP/Products` du même système, validé live) et tag `capsflight` (la première ligne Travel rendue par la List Report existe via requête OData v4 point ; `npx cds watch` requis). Les alias miroirs ECC↔Fiori y sont départagés par `Set Library Search Order` + appels qualifiés. |
| `tests/robot/cross_paradigm_api_visual.robot` | Test **API ↔ GUI + assertion visuelle** auto-suffisant (importe `SapApiLibrary` + `SapEccLibrary`) : le nb de produits EPM recoupé par l'API (`$count` OData `SEPMRA_SHOP/Products`) ET SE16 (`SNWD_PD`) — 205=205 live —, lecture d'entités (`Id`/`Name`/`Price`), puis l'écran SE16 scellé par empreinte perceptuelle (`Screen Should Match Baseline`, `mask_elements=auto`, baseline committée sous `tests/robot/visual_baselines/`). Empreinte fresh-to-fresh distance 0. Validé live 3/3 vs A4H (2026-07-17). |
| `tests/robot/ecc_drift_sentinel.robot` | **Harnais de veille** de la sentinelle : un passage = chaque transaction de `@{WATCHED_TRANSACTIONS}` perçue et comparée à sa référence (`screen_watch/`, à committer) ; rapport Markdown agrégé dans le log ; `-v FAIL_ON_DRIFT:True` = sentinelle-assertion. Étendre la surveillance = ajouter un tcode à la liste, aucun scénario à écrire. Cycle référence→inchangé→dérive validé live vs A4H. |
| `tools/recorder/` | Desktop recorder (`sapgui_recorder.py`): dump / highlight / capture / hover / `--record`, avec `--engine auto\|native\|poll` — le mode **natif** utilise les événements de l'API (`Session.Record`+`Change` pour le record : boutons/grilles/arbres capturés avec la commande exacte ; hit-test `Hit`+`FocusChanged` pour la capture) et replie automatiquement sur le polling (profil serveur `disable_recording`, liaison COM impossible). `--semantic` (moteur natif) réécrit chaque étape en keyword **humain** (`Fill Field By Label …`, id technique en commentaire) quand le libellé calculé à l'événement re-résout de façon unique (`describe_element`) ; vkeys commentés (`# F8` — table statique + `GetVKeyDescription` de la session pour le reste) ; `--screenshots` préfère `HardCopyToMemory` au GDI. **Assertions à chaud** pendant le record (Ctrl+Alt+A = `Element Value Should Be` sur l'élément focalisé — jamais un mot de passe ; Ctrl+Alt+V = `Screen Should Match Baseline`) ; **exports post-enregistrement** : `--suite` (.robot complet, Suite Setup `Attach To Open Session`), `--export-resources` (paire **resource-first** : `${LOC_…}` + keywords métier, plus AUCUN id brut dans la suite — convention 1, validée `robot --dryrun` ET rejouée live), `--export-spec` (plan Markdown format `specs/`, brouillon pour sap-generator), `--export-report` (**rapport HTML de documentation** auto-contenu — phrase métier + ligne RF exacte par step, keywords ECC/Fiori/API phrasés pour les déroulés mixtes, captures `--screenshots` incrustées en data-URI par step, `password=` masqué ; concept RoboSAPiens `saveHtmlReport` réimplémenté par step — NOTICE ; jamais un test) — l'enregistrement brut n'est jamais modifié. Mappings natifs étendus : menus contextuels de grille appariés (`Select Context Menu Item`), arbres (`Select Node`), ligne sélectionnée (`Select Table Row`), cellule suivie via `currentCell*` ; zones opaques (GuiShell/GuiChart) → suggestion `Click Element At Offset` (position relative du curseur) en capture/hover. **Replay** : `--replay FILE` rejoue un enregistrement contre la session OUVERTE (`Attach To Open Session`, arrêt au premier échec — validé live 4/4) ; **transpile VBS** : `--transpile-vbs FILE` convertit les enregistrements ALT+F12 intégrés à SAP GUI via la même machine à états que le natif (sans session SAP ; validé live VBS→transpile→replay) ; l'export resource-first des lignes `--semantic` génère des keywords **auto-réparables** (`Resolve Element With Healing … label=…`). `recorder_gui.py` = lightweight Tkinter launcher (mode picker, pure `build_args` unit-tested) + cases suite/exports + **panneau de steps live** (suivi du fichier de sortie, réordonner/supprimer/ÉDITER au double-clic/enregistrer/REJOUER — helpers purs `parse_recorded_body`/`replace_recorded_steps`). `demo/ecc_demo_video.robot` = **démo scénarisée enregistrée en vidéo** : capture de la SEULE fenêtre SAP GUI (`ffmpeg gdigrab title=…`, aucune fuite de bureau), bandeau ajouté sous l'image, sous-titres portant les steps réellement émis et **recalés par un décalage mesuré** (la capture démarre avant l'horloge du scénario). Ne peut pas être headless — application de bureau : ne rien toucher pendant la prise. |
| `tools/recorder_web/` | Web recorder: locator dump/capture + action recording sur les **5 moteurs** (UI5 role/xpath, WebGUI sid, wc, et **dom** — `captureDom` : rôle ARIA calculé + nom accessible, cibles interactives seulement, le repli des zones non-SAP d'une page hybride). Clic droit en record = **menu d'assertions** (visible/texte par moteur ; Alt+clic conservé), Entrée capturée (`Keyboard Key`, différée après le `change`), navigation → `Wait For UI5 Ready` si runtime UI5 (keyword embarqué dans l'export) sinon `Wait For Load State`, compaction saisies/attentes, alerte iframes cross-origin. `export` = menu : .robot complet, paire resource-first (convention 1 ; steps UI5 nés **auto-réparables** — indice `# xpath:` posé à l'enregistrement → `Resolve Ui5 With Fallback` généré), plan `specs/`, **rapport HTML** de documentation auto-contenu (phrase métier + ligne exacte par step, un chapitre par scénario — jamais un test), et **import** d'un .robot exporté (round-trip). **`play`** = replay in-page (mêmes moteurs, repli xpath réessayé, arrêt au premier échec — le clic rejoué agit réellement, validé live) ; **`+test`** = multi-scénarios (bootstrap dans le seul premier test) ; édition in-place au double-clic ; l'enregistrement ne bloque JAMAIS les clics de l'app (seuls les gestes méta Alt+clic sont avalés — l'ancien preventDefault global gelait l'app en record). `demo/fiori_demo_video.robot` = **démo scénarisée enregistrée en vidéo** (Playwright `recordVideo`, sous-titres incrustés) contre le cap-sflight local — headless par défaut (une fenêtre visible reste interactive, donc parasitable) ; sortie `dist/video/`, visuels livrés dans `comms/visuels/`. |
| `integrations/robotmcp/` | rf-mcp (RobotMCP) plugins (`SapEccPlugin`/`SapFioriPlugin`/`SapApiPlugin`): route keywords, SAP screen perception (state provider), selector guidance. Le plugin API (canal sans écran) sert l'état réel du canal via `List Api Sessions` (alias/base_url/authentifié — jamais de credentials) et une explication honnête en guise de page source. Compose **above** rf-mcp — no standalone MCP. Perception is never a time-based cache; `_last_seen.py` compacts identical calls and `_filtering.py` implements the real filtering contract. Les state providers servent le **diff intelligent** quand l'écran déjà vu a changé (`perception_diff`, renommages appariés côté ECC ; en-tête auto-descriptif, `full_source=true` = vue complète, arbitrage : jamais un diff plus long que l'écran). `get_application_state` ECC lit l'état RÉEL : transaction + **pile de fenêtres/`modal_open`** (piège SESSION_MANAGER) + type de message + télémétrie, chaque section best-effort. `_staleness.py` ajoute `stale_code_warning` quand le code SAPFX a changé sur disque après le démarrage du serveur (rf-mcp fige classes et instances). **Surcouche `sapfx-mcp`** (`server.py` + `_overlay.py` + `_compat.py`, entry point console du wheel) : monte le serveur rf-mcp INCHANGÉ et ajoute les outils que le contrat plugin 0.31 ne permet pas (constaté live 2026-07-23) — `sapfx_state` (providers appelés en direct : diff par défaut, `application_state` enrichi), `sapfx_screenshot` (vraie image MCP, brute ou Set-of-Mark + légende), `sapfx_reload` (hot-reload de la couche plugin) ; garde de compatibilité au démarrage (fenêtre de versions rf-mcp validée + sonde des points d'ancrage, refus bruyant, `SAPFX_MCP_FORCE=1` pour outrepasser). PAS un fork : chaque câblage accepté upstream fait maigrir la surcouche. ECC reste limité à une session live par process : rf-mcp 0.31 ne propage pas fiablement le contexte dans les resources imbriquées. See its `README.md`. |
| `docs/` | architecture · fiori-architecture · mcp-integration · audit-upstream · testing-without-sap · ecc-validation · sap-test-data · deployment-pack (end-to-end pack walkthrough) · test-agents (cycle plan → generate → heal) · hardening-test-environment (checklist sécurité serveur/poste/web/MCP, mappée sur les préflights) · migrating-from-sapguilibrary + migrating-from-cbta (guides de migration — la fenêtre CBTA se ferme fin 2027). All bilingual (`*.md` + `*.fr.md`); pairing/drift enforced by `scripts/check_bilingual_docs.py`. |
| `llms.txt` | Index **LLM-friendly** du projet à la racine (format llmstxt.org) : résumé, conventions non négociables, liens vers les docs et points d'entrée — le pendant machine de ce CLAUDE.md pour les assistants qui découvrent le dépôt. Tenir en phase quand docs/layout bougent. |
| `assets/` | Identité visuelle : `logo.png` (master 512 px, médaillon détouré, fond transparent), affiché en tête des README. Déclinaisons régénérées par `tools/recorder_web/extension/gen_icons.py` (Pillow, dev only) : icônes 16/48/128 de l'extension (le 16 px recadre sur le visage du robot, illisible sinon) + icône 256 px de la GUI Tkinter (`tools/recorder/assets/icon.png`). `.gitignore` exclut `*.png` sauf ces assets (liste d'exceptions à étendre pour tout nouveau PNG committé). |
| `scripts/` | Repo-wide tooling scripts (not tied to one library): `check_bilingual_docs.py` (EN/FR doc pairing + drift since a ref), `check_vendor_drift.py` (vendored file vs. a local/fresh upstream clone), `check_guidance_sync.py` (rf-mcp hints **et définitions d'agents de test** vs. CLAUDE.md conventions, plus la **fraîcheur des cartes de keywords** des plugins — keywords phares par mixin, la dérive 0.5.6→0.6.1 ne peut plus se reproduire) — consistency guards, not generators — plus `build_release_pack.py`, `regen_agent_definitions.py`, `healing_drift_report.py` (**bot de maintenance préventive** : journal → propositions/patches `resources/`, jamais les tests), `check_spec_sync.py` (**le plan est la source de vérité** : marqueur sha256 + date, suite périmée refusée, plan marqué `PÉRIMÉE` par le healer refusé jusqu'à ré-exploration), `check_conventions.py` (**les conventions #1/#2 tenues, pas seulement énoncées** : localisateurs bruts dans une suite *générée*, `Sleep` partout ; les suites de validation de la bibliothèque, dont l'objet est de piloter SAP par ses ids bruts, sont informatives — `--strict` les inclut), `hook_guards.py` (hook `PostToolUse` lançant les deux après chaque édition), `check_comms_sync.py` (**la comm ne doit pas mentir sur le produit** : `comms/proofs.json` est recoupé avec `pyproject.toml`, la collecte pytest et `coverage.xml`; les citations périmées échouent), et `agent_eval_harness.py` (**éval en aveugle des agents** : inject/verify/restore d'une dérive simulée dans `resources/` — le filet de régression du comportement du healer, orchestré par `/sap-eval-healer`). Enfin `export_public_tree.py` (**export public par release**, décision 2026-08-03 : arbre `git archive HEAD` filtré vers le dépôt public `robotframework-sapfx` — exclusions comms/skill privée/settings/picto, transformations fail-closed, scan anti-fuite bloquant octets/binaires, README PyPI sans banner EN/FR ; le script est lui-même exclu de l'export, son test unitaire est livré et se saute sur l'arbre public). Tous sont couverts dans `tests/unit/`. |
| `packaging/` | Sources of the **Windows deployment pack**: `python scripts/build_release_pack.py` → `dist/sapfx-pack-<version>-win.zip` (les deux wheels, `resources/`, recorders + extension MV3, 6 suites d'exemple dont `fiori_wc_smoke.robot` hors ligne, scripts de maintenance, agents + skill `sapfx` et `specs/`, LICENSE/NOTICE). `install.ps1`/`install.cmd` créent le venv, appliquent `requirements-deploy.txt` sous `constraints-deploy.txt`, installent optionnellement MCP/Chromium et rendent les configs. Le builder écrit `SHA256SUMS.txt` et le sidecar du ZIP ; CI installe le ZIP extrait puis génère SBOM CycloneDX et attestation de provenance. Le pack sous `dist/` est généré — corriger `packaging/` et reconstruire, jamais l'éditer en place. |
| `.github/workflows/ci.yml` | Main CI (push/PR to `main`): Python 3.10/3.12/3.14 unit matrix (3.10 = floor and 3.14 = latest verified in plain pytest; the full lane — lint, guards, coverage — stays on 3.12), ruff + expanded mypy + consistency/proof guards + `pytest --cov` (85% gate); Windows real-pywin32 dry-run plus offline Browser smoke; `release-pack` builds the ZIP, installs it outside the checkout with MCP/Chromium, runs Libdoc/dry-run/smoke, then publishes SHA-256 + CycloneDX SBOM and attests push builds. |
| `.github/workflows/ui5-compat.yml` | Weekly/manual UI5 matrix: current + 1.136 LTS are blocking; UI5 2.x nightly runs as a non-blocking sentinel, with Robot results retained. |
| `.github/workflows/vendor-drift.yml` | Weekly (+ manual dispatch): clones the real upstream repo fresh and runs `check_vendor_drift.py` against it — the CI-side counterpart of convention 4, since CI has no local `_upstream/` clone. |
| `recorder.cmd` | Root double-click launcher for the desktop recorder GUI (pythonw→python→py fallback). |
| `robot.toml` | Shared RF config (`python-path = ["src", ...]`) — keeps the RobotCode IDE resolver and CLI in sync; fixes false "KeywordNotFound" in the IDE. |
| `.vscode/` | Committed team config: `settings.json` (Pylance paths, pytest), `extensions.json`, `mcp.json` (rf-mcp server for VS Code/Copilot agent mode). Everything else under `.vscode/` stays gitignored. |
| `.mcp.json` | Same rf-mcp server declaration for Claude Code (project scope). Both configs launch **`sapfx-mcp` --transport stdio --without-frontend** (la **surcouche** : le serveur rf-mcp INCHANGÉ + les outils `sapfx_*`) with `PYTHONPATH=src;integrations/robotmcp`; the SAP plugins AND the `sapfx-mcp` console script register via `pip install -e integrations/robotmcp`. |
| `.claude/agents/` + `.claude/commands/` + `.claude/skills/` | **Agents de test SAP** (source canonique, style Playwright Test Agents) et la **skill `sapfx`** (`.claude/skills/sapfx/SKILL.md` — la boîte à outils apprise en un appel, esprit « install as a skill » de Vibium : trois canaux, boucle perception→action `@N`, conventions, cycle agents ; embarquée dans le pack Windows) : `sap-planner` (exploration live perception→action via rf-mcp → plan métier dans `specs/`), `sap-generator` (plan → suite `.robot`, chaque étape exécutée live avant écriture ; keywords manquants ajoutés à la couche resources), `sap-healer` (échec reproduit, closest matches scorés + télémétrie, patch de `resources/` — jamais des tests, jamais silencieux) ; slash-commands `/sap-plan`, `/sap-generate`, `/sap-heal`, plus les orchestrateurs `/sap-maintain` (cycle sentinelle → télémétrie → healer, un rapport unique) et `/sap-eval-healer` (éval en aveugle du healer via `scripts/agent_eval_harness.py`). Hygiène de session encodée dans les trois définitions : préflight des connexions, fermeture MÊME SUR ÉCHEC (field note 2026-07-21). **Ventilation industrielle** encodée dans generator/healer : nouvelles suites sous `tests/robot/{api, ui/ecc, ui/fiori, cross}`, **page objects** sous `resources/page_objects/` (UN `.resource` par écran/app : variables de localisateurs + keywords métier), `resources/common.resource` (transverse), `variables/` (`env_<env>.yaml`, `locators.py` partagé — jamais de mot de passe : `Secret:` en ligne de commande) ; les suites legacy à plat ne bougent pas ; le healer répare cette couche, jamais les tests. Règle pack déployé encodée dedans : écrire dans `resources/site_keywords.resource`, jamais dans les fichiers livrés. Voir [docs/test-agents.md](docs/test-agents.md). |
| `.github/chatmodes/` | Déclinaison VS Code / Copilot agent mode des mêmes agents — fichiers **GÉNÉRÉS** depuis `.claude/agents/` par `scripts/regen_agent_definitions.py` (ne jamais éditer un `*.chatmode.md` à la main ; `--check` en garde CI/pytest). |
| `specs/` | Plans de test métier (Markdown, **français** — hors contrat bilingue, comme `.claude/` : exemptions par préfixe dans `check_bilingual_docs.py`) : produits par sap-planner, consommés par sap-generator. `README.md` = contrat du répertoire ; `sflight-consultation-se16.md` = exemple de référence aligné sur `ecc_data_smoke.robot`, embarqué dans le pack. |
| `_upstream/` | Local reference clone of upstream. **Not committed** (gitignored); used by `scripts/check_vendor_drift.py` when present. |
| `_cap-sflight/` | Local clone of SAP-samples/cap-sflight (local Fiori Elements target). **Not committed** (gitignored). |

Class MRO (ECC): `SapEccLibrary(ConnectionKeywords, WaitKeywords, GridKeywords,
PerceptionKeywords, DiagnosticsKeywords, HealingKeywords, SemanticKeywords,
EmbeddedBrowserKeywords, PointerKeywords, SessionKeywords, SapGuiBase)` —
mixins precede the base so they override same-named base keywords and can call
inherited ones via `self`.

Fiori: `SapFioriLibrary` does **not** drive the page itself — it reuses the
Browser library's active page via `BuiltIn().get_library_instance('Browser')` and
injects `RecordReplay` JS. A suite must `Library    Browser` alongside it.

## Commands

```bash
python -m pytest -q                       # all logic tests — no SAP/browser (paths via pyproject)
python -m pytest -q --cov=src --cov=integrations/robotmcp/sap_robotmcp \
  --cov-report=term-missing --cov-fail-under=85   # same, with the coverage gate CI enforces
python -m ruff check src tools tests integrations scripts   # lint (config in pyproject; _vendor excluded)
python -m mypy                            # progressive type check — scope is `[tool.mypy] files` in pyproject.toml
python -m py_compile src/SapEccLibrary/**/*.py   # quick syntax check
pip install -r requirements.txt           # robotframework + pywin32 (pinned) + browser
rfbrowser init                            # one-time: download Playwright browsers (web side)
robot --pythonpath src --dryrun --outputdir results/dry tests/robot/   # keyword resolution check, no SAP
robot -v SAP_CONNECTION:"..." -v SAP_USER:... -v "SAP_PASSWORD: Secret:..." tests/robot/ecc_smoke.robot   # RF 7.4 typed Secret — masked even at TRACE
robot --pythonpath src -v SAP_CONNECTION:... -v SAP_USER:... -v "SAP_PASSWORD: Secret:..." tests/robot/ecc_multisession_smoke.robot   # multi-session par alias (live)
robot tests/robot/fiori_smoke.robot       # Fiori — runs vs the public OpenUI5 Demo Kit
robot tests/robot/fiori_sflight_smoke.robot   # Fiori Elements vs local cap-sflight (cds watch first)
robot --pythonpath src tests/robot/fiori_ui5v2_smoke.robot   # compat UI5 2.0 nightly (réseau)
robot --pythonpath src tests/robot/fiori_legacyfree_smoke.robot   # compat UI5 1.136 legacy-free (réseau, cible stable)
robot --pythonpath src tests/robot/fiori_csp_smoke.robot   # injection sous CSP stricte (réseau)
robot --pythonpath src tests/robot/fiori_auth_smoke.robot   # login IDP deux-étapes (fixture, réseau)
robot --pythonpath src tests/robot/fiori_frame_smoke.robot   # iframes launchpad (Set Ui5 Frame, multi-frames/reload/navigation)
robot --pythonpath src tests/robot/fiori_wc_smoke.robot   # moteur Web Components (fixture locale, hors ligne)
robot --pythonpath src tests/robot/fiori_hybrid_smoke.robot   # sessions hybrides : composition, moteur dom, pile de frames (fixture locale, hors ligne)
robot --pythonpath src -v SAP_CONNECTION:... --include a4h tests/robot/flagship_cross_paradigm.robot   # flagship GUI↔API (A4H) ; --include capsflight = Fiori↔API (cds watch requis)
python scripts/healing_drift_report.py --log <SAPFX_HEALING_LOG>   # dérives de localisateurs ; --apply patche resources/
python scripts/check_spec_sync.py         # suites en phase avec leur spec (source de vérité) ; --stamp après génération
python scripts/check_conventions.py       # conventions #1/#2 tenues par les artefacts (--strict inclut les suites de validation de la lib)
robot --pythonpath src -v SAP_CONNECTION:... tests/robot/ecc_drift_sentinel.robot   # sentinelle de dérive (veille sans tests)
python scripts/check_bilingual_docs.py --since origin/main   # EN/FR doc pairing + drift since a ref
python scripts/check_vendor_drift.py      # vendor file vs. local _upstream/ clone (no-op if absent)
python scripts/check_guidance_sync.py     # rf-mcp hints + définitions d'agents vs. CLAUDE.md conventions
python scripts/regen_agent_definitions.py --check   # chat modes VS Code alignés sur .claude/agents/ (sans --check : régénère)
python scripts/build_release_pack.py      # Windows deployment pack -> dist/sapfx-pack-<v>-win.zip
python scripts/export_public_tree.py      # arbre public filtré -> dist/public-export/ (+ README PyPI, scan anti-fuite)
```

**Local environment already provisioned (do not ask the user to install these):**

- **Playwright browsers are already initialized** (`rfbrowser init` done; Chromium present).
  The Fiori smoke runs as-is — `robot --pythonpath src tests/robot/fiori_smoke.robot`
  passes live vs the OpenUI5 Demo Kit. The system Chrome is also usable via
  `New Browser    chromium    channel=chrome`.
- **SAP GUI for Windows 8.00 (build 800) is installed** at
  `C:\Program Files\SAP\FrontEnd\SAPgui\saplogon.exe` — the ECC desktop side can run live
  (against the ABAP Platform A4H trial in Docker). See `docs/testing-without-sap.md` for the
  exact `robot` invocation and connection string.

To provision a fresh machine from scratch instead, see
[docs/testing-without-sap.md](docs/testing-without-sap.md) — the **ABAP Platform
Trial Docker** image is the recommended free, local, full-fidelity ECC option; the
Fiori side needs no SAP at all (test against the OpenUI5 Demo Kit, or the local
cap-sflight target — see [docs/sap-test-data.md](docs/sap-test-data.md)).

**A4H field notes (learned live, save yourself the debugging):**

- **`SE16N` does not exist on A4H** ("Transaction SE16N does not exist") — use SE16.
- **SE16's default output is the classic ABAP list** (dynpro `SAPMSSY0/120`) — it has
  **no scriptable grid object**. Call `Use ALV Grid In Data Browser` once per user
  (persistent) before `Display Table Contents`; only then does
  `wnd[0]/usr/cntlGRID1/shellcont/shell` exist.
- Demo data: SFLIGHT/EPM guards live in `resources/a4h_demo_data.resource`
  (generation runs only when tables are empty; it takes minutes).
- **SE16 « Number of Entries »** = `wnd[0]/tbar[1]/btn[31]` on the selection screen;
  the popup exposes the count in `wnd[1]/usr/txtG_DBCOUNT` (thousands separators
  possible — strip non-digits) and closes with F12. Works on empty tables (0) —
  unlike F8, which stays on the selection screen when nothing matches.
- **Selection-screen fields are positional**: `I<n>-LOW/HIGH` follows the table's
  field order, and the control type varies (`ctxtI2-LOW` vs `txtI3-LOW` — probe
  with `Get Screen Signature` first). `MAX_SEL` = « Maximum No. of Hits ».
- **Tables with > 40 fields** (e.g. DD02L) pop a « choose selection fields » dialog
  on Enter; the checkbox position varies by table, and the choice **persists per
  user**. `Try Open Table Selection Screen` finds the first checkbox dynamically.
- **Les écrans de liste ABAP modernes (SAP GUI 8.00) sont rendus dans un
  GuiShell opaque** (`GuiCustomControl`→`GuiContainerShell`→`GuiShell`, zéro
  `GuiLabel` — vérifié live sur la sortie RSPARAM) tant que le **mode
  accessibilité** SAP GUI n'est pas actif : `Read Abap List` ne peut rien
  reconstruire. Le mode accessibilité **ne s'active PAS depuis un test** —
  testé live, `SAP_ACCESSIBILITY=1` transmis à saplogon n'a aucun effet, et
  c'est de toute façon un réglage du **poste** (Options SAP GUI → Interaction
  Design → Accessibility), global à l'utilisateur Windows et exigeant un
  redémarrage du client : il se **provisionne** (comme RZ11 côté serveur) et se
  **constate** (`Get List Rendering Status` / `Abap List Should Be Readable`,
  validés live : `accessibility_mode_needed: True` sur RSPARAM, `False` sur un
  écran à labels). Les menus dupliquent le texte des boutons de toolbar
  (« Number of Entries » = `btn[31]` ET `menu[1]/menu[10]`) — d'où l'exclusion
  des `GuiMenu` des cibles de `Click Button By Label`.
- **WebGUI (SAP GUI for HTML) sur A4H** : le service ICF
  `/default_host/sap/bc/gui/sap/its/webgui` est **inactif par défaut**
  (HTTP 403) — l'activer UNE fois via SICF (les parents sont déjà actifs, la
  feuille suffit ; fait live via rf-mcp le 2026-07-18). Le WebGUI réel émet
  `lsdata` en **littéral JS** (`SID:'…'`, clés non citées, guillemets simples)
  et non le JSON `"SID":"…"` des fixtures — `sid_xpath` et `captureSid`
  matchent les DEUX formats depuis le correctif 2026-07-18 (découvert par
  l'exploration agent : 0 match live avant). L'espace des SIDs est identique
  au scripting desktop (`wnd[0]/usr/ctxtDATABROWSE-TABLENAME`,
  `wnd[0]/tbar[1]/btn[31]`…). Le champ OK-code est masqué par défaut et le
  réglage « Show OK Code field » ne persiste pas : lancer les transactions par
  le paramètre d'URL `&~transaction=<TCODE>`.
- **Conteneur A4H re-créé = configuration remise à zéro** (vécu 2026-08-01/02) :
  licences liées à la MAC (figer `--mac-address` au `docker run`), profil
  scripting, ICF webgui ET **Gateway désactivée** (OData → HTTP 500
  `/IWFND/CM_COS/003`). Sans licence, **`SAP*`/000 se connecte quand même**
  (001 refusé « error in license check », en GUI ET en OData) — la voie
  d'admin pour tout réparer. Réactivation Gateway validée live 2026-08-02 :
  activité IMG `/IWFND/IWF_ACTIVATE` (tcode généré `/IWFND/50000003`,
  correspondance lue dans `CUS_IMGACH`) → bouton « Activate » ; réglage
  inter-mandants (catalogue client 000 = 38 services aussitôt après). Piège :
  `Run Transaction` sur un tcode IMG généré échoue en **faux négatif** —
  sy-tcode = le nom interne (`active='/IWFND/IWF_ACTIVATE'`) ; percevoir
  l'écran avant de conclure (fiche
  `memory/run-transaction-tcodes-parametres.md`). Procédure complète :
  [docs/ecc-validation.md](docs/ecc-validation.md) §11.7.
- **Structures/includes are rejected by SE16 with a status message of type `E`**
  (e.g. SFL_AUX in SAPBC_DATAMODEL, 14 of the 114 SNWD_* TADIR objects) — the
  locale-safe way to tell a structure from a table.
- S/4HANA 1909 catalogs (locked by `ecc_exploration.robot`): delivery classes
  A/C/E/G/L/S/W, table classes TRANSP/INTTAB/VIEW/APPEND (no more POOL/CLUSTER).
- **rf-mcp + COM**: never let a keyword *return* a COM object through the MCP
  boundary (serialization on another thread → RPC_E_WRONG_THREAD). Use
  `Element Should Be Present` instead of `Wait Until Element Present` as the last
  step of an MCP-driven batch; plain robot runs are unaffected.
- **rf-mcp session isolation**: all three libraries use `SUITE` scope, which
      isolates normal Robot suites. rf-mcp 0.31 nevertheless reuses one Python
      instance across its synthetic tests; `session_context` therefore partitions
      API cookie/CSRF/RFC stores and Fiori frame/perception state by `MCP_Test_<id>`.
      Nested ECC resource calls can be attributed to the wrong synthetic test, so
      validated usage remains one live ECC session per rf-mcp process (the
      per-alias registry — `Open Sap Session`/`Create Gui Session` — multiplexes
      several GUI sessions *within* that one process, live-validated through MCP).
- **rf-mcp fige classe ET instance de bibliothèque** : le serveur importe les
      libs à la première session et les réutilise pour tout le process — après
      une modification du code de `src/`, un simple `manage_session init` (même
      avec alias d'import) resservira l'ANCIENNE classe. Redémarrer le serveur
      rf-mcp est la voie nominale ; le dépannage sans redémarrage validé live :
      `importlib.reload` des modules (`keywords` → `SapEccLibrary.SapEccLibrary`
      → package), puis hot-swap `instance.__class__`, puis BuiltIn
      `Reload Library` pour re-découvrir les keywords. Les state providers
      détectent désormais ce cas (`sap_robotmcp/_staleness.py`) et ajoutent
      `stale_code_warning` à leurs réponses quand un module SAPFX a changé sur
      disque après le démarrage du serveur.

- **Test live agent+MCP du 2026-07-23 — quatre faits rf-mcp 0.31.2 appris en
      route** (validés contre A4H, SE16/T000) : (1) le hot-reload de la **couche
      plugin** sans redémarrer le serveur est possible : `importlib.reload` des
      modules `sap_robotmcp` puis
      `robotmcp.plugins.manager.reset_library_plugin_manager_for_tests()` puis
      ré-enregistrement (`iter_entry_point_plugins` → `register_plugin`) — le
      tool `manage_library_plugins reload` SEUL ne suffit pas (instances en
      cache) ; même chose côté bibliothèque : l'init de session réutilise le
      module déjà importé au démarrage du serveur (hot-swap field note
      ci-dessus). (2) `get_session_state(sections=["page_source"])` ne route
      vers le provider SAP que si `session.browser_state.active_library` est
      posé — l'exécution en contexte natif ne le pose PAS pour une lib desktop
      (« No page source available ») : le poser via Evaluate
      (`setattr(s.browser_state, 'active_library', 'SapEccLibrary')`), ou
      correctif upstream à proposer. (3) le chemin `application_state` de
      rf-mcp n'appelle JAMAIS `get_application_state` des plugins (seul
      `page_source` est branché sur les providers) — l'état enrichi
      (`modal_open`…) s'obtient par les keywords (`Get Open Windows`) via
      `execute_step`. (4) sur `get_session_state`, le serveur passe
      `full_source=not page_source_filtered` : le mode DIFF du provider ne
      s'exerce qu'avec `page_source_filtered=true` (validé live : 290 octets au
      lieu de 11 945, `~ txtMAX_SEL texte : '250' -> '300'`).

- **Windows + serveur MCP actif : `pip install -e integrations/robotmcp`
      échoue EN SILENCE** (vécu 2026-07-23) : un serveur `sapfx-mcp`/`robotmcp`
      en cours verrouille l'exe du script console — pip s'arrête sur
      WinError 32 en laissant un dist-info résiduel invalide (`~ap_robotmcp…`,
      `pip show` aveugle) alors que le serveur, lui, continue de marcher via
      l'egg-info local du PYTHONPATH. Réflexe : arrêter les serveurs MCP avant
      la réinstallation (ou vérifier `pip show sap-robotmcp` après), et
      supprimer le dossier `~…dist-info` résiduel avant de réessayer.

- **rf-mcp 0.35.0 — re-validation de compatibilité (2026-07-24, diff du wheel
      + suite unitaire complète contre la 0.35.0 réelle ; PAS de re-run live
      A4H)** : les séries 0.32/0.33 n'existent pas sur PyPI (saut 0.31.2 →
      0.34.0 → 0.35.0). Contrat plugin INCHANGÉ (`plugins/contracts.py` et
      `plugins/manager.py` identiques octet à octet, `plugins/base.py` = ajout
      rétro-compatible `keyword_library_map`) ; routage `page_source` inchangé
      (`full_source=not page_source_filtered`, field note 2026-07-23 toujours
      valable). Ce qui a bougé : (1) `robotmcp.server.execution_engine` est un
      **proxy LAZY** — tout `hasattr`/accès d'attribut dessus matérialise le
      moteur et re-ralentit le handshake MCP : sonder la CLASSE
      `ExecutionCoordinator` (fait dans `_compat.py`) ; (2) entry points
      console déplacés vers `robotmcp.entry:main` (+ alias `rf-mcp`,
      sous-commandes d'onboarding `init`/`doctor`… — `robotmcp.server.main`
      existe toujours, mêmes arguments : la délégation de `sapfx-mcp` tient) ;
      (3) nouvelle dépendance `tomlkit` ; (4) **piège de classification
      desktop (PlatynUI)** : un `manage_session init` dont le TEXTE de
      scénario contient un signal desktop (« desktop », « win32 »,
      « `*.exe` »…) force la session en DESKTOP_TESTING → `get_session_state`
      sert un STUB PlatynUI en guise de `page_source` et n'appelle jamais le
      provider SAP — dire « SAP GUI »/« ECC » dans les scénarios, jamais
      « desktop » ; l'outil `sapfx_state` de la surcouche est insensible au
      piège (providers appelés en direct) ; (5) gabarit d'instructions agent
      par défaut passé à `lean` (`ROBOTMCP_INSTRUCTIONS_TEMPLATE=standard`
      pour l'ancien). Fenêtre du garde élargie à [0.31, 0.36) ; pin de
      déploiement `packaging/constraints-deploy.txt` monté à 0.35.0.

- **Live ECC testing: close every session you opened, even on failure.** End
  each probe/suite with a clean logoff (`Close SAP` teardown, `/nex`, or
  `Close All Sap Sessions`), and wrap ad-hoc scripts in try/finally so a crash
  still logs off: an orphaned connection shifts the connection indices, and
  the next `Attach To Open Session` / `--replay` silently grabs the wrong
  session (bitten live 2026-07-21 — the replay attached to a leftover session
  parked on another screen, and the real error was two layers deep).

## Conventions (do not break)

1. **Tests contain no raw SAP ids / no CSS-XPath.** ECC element ids and Fiori UI5
   selectors live in `resources/`; tests speak business language. On Fiori, address
   **UI5 controls** (`controlType`/`properties`/`bindingPath`/…), never DOM ids.
2. **Never `time.sleep` to wait for SAP.** Use `Wait Until Busy Done` /
   `Wait Until Element Present`. Fixed waits are demo-only.
3. **Locale-independent assertions.** Check status-bar message *type* (`E`/`S`/…),
   never the localized message text. This is *why* `Run Transaction` is overridden.
4. **Keep the vendor diff to one line.** `_vendor/sapgui_base.py` is upstream + the
   class rename only. New behaviour goes in a mixin or `SapEccLibrary.py`, never by
   editing the vendored file. This keeps upstream re-sync a 5-minute job
   (procedure in [docs/audit-upstream.md](docs/audit-upstream.md)).
5. **Every new keyword gets an off-SAP unit test** in `tests/unit/` using the fake
   COM objects pattern (see `test_logic.py` / `conftest.py`), even when it also
   needs a live smoke test.
6. **Pin `pywin32`** in `requirements.txt` (exact `==`, currently `311`); it is the
   #1 source of COM breakage. `pyproject.toml` keeps a floor (`>=305`) because a
   *library* must not hard-pin its consumers — the pin belongs to the environment file.
7. **Keep the AI-assistant supports in sync.** This CLAUDE.md is the canonical,
   detailed guide. `AGENTS.md` (root) and `.github/copilot-instructions.md` are
   condensed mirrors for other assistants (Copilot, Codex, Cursor…): when layout or
   conventions change here, propagate the change to both files in the same commit.
8. **Spec lifecycle markers close the agent feedback loops.** sap-healer marks a
   functionally-changed plan `> **Statut : PÉRIMÉE (date)** — …` (blocks
   `check_spec_sync.py` until sap-planner re-explores and removes it);
   sap-generator records reality/plan divergences under
   `## Écarts constatés à la génération` before re-stamping; every heal session
   appends to `docs/heal-journal.md` — the agent's diagnosis (failure class,
   evidence, anchoring lesson), complementary to the runtime
   `SAPFX_HEALING_LOG` telemetry that feeds `healing_drift_report.py`.
   Conventions #1/#2 are not only stated, they are **enforced** by
   `check_conventions.py` (generator gate, post-edit hook, CI).

## License

Apache 2.0. Vendored upstream attribution is in `NOTICE`; preserve it.

## Status / next steps

- [x] Phase 1 (ECC): vendored base, mixins, business resource, unit tests, docs.
- [x] Phase 2 (Fiori): `SapFioriLibrary` (UI5 RecordReplay locators), mirrored
      `fiori_keywords.resource`, off-browser unit tests, web Spy MVP, docs.
- [x] Validate `ecc_smoke.robot` against a live ABAP Platform Trial (A4H 1909 in
      Docker, `/H/vhcala4hci/S/3200`, DEVELOPER/001 — 5/5 passing).
- [x] Validate `fiori_smoke.robot` with the Browser library's Chromium installed
      (`rfbrowser init chromium`) vs the live OpenUI5 Demo Kit — 6/6 passing.
- [x] Desktop recorder (`tools/recorder`): click-to-capture (`--capture`, focus polling)
      + hover-highlight (`--hover`, cursor → control) + `--highlight ID`. Captures land in
      `tools/recorder/captures/`. Off-SAP unit tests in `tests/unit/test_desktop_spy.py`.
- [x] On-demand **record mode** following user manipulations → ordered, replayable
      keyword sequence. Desktop (`--record`): round-trip diff via a full-control-id
      *screen signature* + editable-field diff → `Input Text`/`Run Transaction`/`Send Vkey`
      (live-validated on A4H). Web (`rec` button in the panel): click/change listeners →
      `Click Ui5 Control`/`Fill Ui5 Input`, `export` copies a `*** Test Cases ***` body
      (live-validated on system Chrome). Pure logic unit-tested (`process_poll`, `diff_to_steps`).
- [x] **rf-mcp (RobotMCP) integration** (`integrations/robotmcp/`): instead of a
      standalone MCP, compose **above** the existing rf-mcp server with two plugins
      (`SapEccPlugin`/`SapFioriPlugin`) built on its real contracts (v0.31.2). They
      route keywords, inject SAP selector guidance (hints/prompt-bundle), and surface
      screen perception via state providers calling the RF-context. Perception keywords
      added: `Get Screen Signature` (ECC) and `Get Ui5 Page Tree` (Fiori). Off-SAP
      unit-tested (`tests/unit/test_perception.py`, `integrations/robotmcp/tests/`).
- [x] **End-to-end Fiori *through* rf-mcp** validated (`integrations/robotmcp/e2e/
      fiori_through_rfmcp.py`, 8/8): drives the real MCP tools in-process —
      session with Browser + SapFioriLibrary in one RF context, keyword routing,
      `Get Ui5 Page Tree` perception + `Click Ui5 Control` action against a live page.
      Proves the Browser dependency is satisfied inside rf-mcp's shared context.
- [x] **End-to-end ECC *through* rf-mcp** validated against live A4H Docker
      (`integrations/robotmcp/e2e/ecc_through_rfmcp.py`, 9/9): session + business
      resource, COM login, keyword routing, `Get Screen Signature` perception, and the
      **state provider** returning the real live SE16 screen signature. Required a
      `CoInitialize` on rf-mcp's execution thread (`connect_to_session` override).
- [x] **Hardening pass (2026-07)**: `sapfx_common` shared polling/retry primitives
      (three duplicate loops removed); coverage gaps closed (bootstrap, SID wrappers,
      grid-by-title, regen — 154 unit tests); ECC↔Fiori mirror aliases; ruff +
      pre-commit + .editorconfig + robot.toml + CHANGELOG; AI supports (AGENTS.md,
      copilot-instructions); `docs/sap-test-data.md` (verified SAP data/test targets).
- [x] **Data-driven smokes validated live**: `ecc_data_smoke.robot` 4/4 vs A4H Docker
      (SFLIGHT/SPFLI/EPM via SE16 ALV grid, conditional generators) and
      `fiori_sflight_smoke.robot` 2/2 vs local cap-sflight (`cds watch`, FE v4
      List Report, inner `sap.m.Table` read by stable FE control id).
- [x] **Exploration campaign through rf-mcp validated live (2026-07)**: agent-driven
      SE16 exploration of the A4H (perception → action loop), findings encoded in
      `resources/ecc_keywords.resource` exploration keywords + `ecc_exploration.robot`
      (6/6 live: catalogs locked, 27 flight + 114 EPM objects deep-verified).
- [x] **UI5 multi-version readiness (2026-07)**: `registryForEach` fallback chain in
      `_ui5_js.py` — `ElementRegistry` module (UI5 2.x) → `Element.registry` (1.67+)
      → DOM scan `[data-sap-ui]` (< 1.67) — and `Wait For UI5 Ready` no longer hard-
      requires `sap.ui.getCore()`. Proven live vs **real OpenUI5 1.60.14**
      (`fiori_legacy_smoke.robot` 4/4, jsDelivr npm mirror) with zero regression on
      current UI5 (fiori + recorder smokes 10/10). Unit-locked by
      `tests/unit/test_ui5_compat.py`; compatibility matrix in
      [docs/sap-test-data.md](docs/sap-test-data.md) §5.
- [x] **Code-quality review + fix pass (2026-07-10)**: closed a COM thread-affinity
      gap in the rf-mcp state providers, an unhandled `com_error` in `Get Screen
      Signature`'s tree walk, Fiori polling loops that could be killed by a single
      transient JS exception, a `captureSid` BFS bug, `run_transaction` mishandling
      namespaced tcodes (`/BEV1/RCA01`), the desktop recorder's `pythonw`/no-stdio
      launch bug and a path-traversal gap, plus a real bug found *while writing
      tests* for the new SE16 exploration keywords (a `\D` regex silently defanged
      by Robot's own backslash escaping — replaced with a backslash-free digit
      filter, locked in by a test that executes the real Robot-parsed expression,
      `tests/unit/test_se16_exploration_logic.py`). 201→247 unit tests.
- [x] **CI + DX hardening pass (2026-07-10)**: `.github/workflows/ci.yml` (ruff +
      mypy + pytest/coverage on ubuntu using the conftest stubs, `robot --dryrun`
      on windows) and `vendor-drift.yml` (weekly, real upstream clone); progressive
      `mypy` typing (`sapfx_common`, `_ui5_runtime.py`, the rf-mcp perception
      modules); `poll_interval` made configurable on both libraries (was hard-coded
      0.1s/0.25s); `--hover`'s `element_at` now restricted to each session's
      *active* window (`iter_active_window_elements`) instead of every residual
      window; desktop recorder gained `--screenshots` (best-effort GDI capture per
      `--record` boundary) and a merged single-COM-walk `scan_active_window`
      (was two full tree walks per poll cycle); rf-mcp state providers gained
      perception compaction (`_last_seen.py`: byte-identical consecutive calls ->
      compact marker) and a real `filtered`/`filtering_level` implementation
      (`_filtering.py`, minimal/standard/aggressive, ancestor-preserving prune for
      the UI5 tree) — both were part of the contract but previously ignored.
      `scripts/check_bilingual_docs.py` / `check_vendor_drift.py` /
      `check_guidance_sync.py` are new consistency guards, not generators (see
      their docstrings for why generation was rejected). 247→276 unit tests.
- [x] **Windows deployment pack (2026-07-11)**: `scripts/build_release_pack.py` +
      `packaging/` → `dist/sapfx-pack-<version>-win.zip`, a self-contained pack for
      a target test PC (no repo clone): both wheels (libraries + rf-mcp plugins,
      entry points intact), business resources, both recorders (incl. MV3
      extension), 2 sample smokes, bilingual README, and an `install.cmd`/`.ps1`
      that builds a local `.venv`, pins pywin32, optionally installs the MCP
      plugins (`-WithMcp`, renders `mcp.generated.json`) and Playwright Chromium
      (`-WithBrowsers`). Library wheel smoke-validated in a throwaway venv
      (imports + RF 7.4.2). Assembler logic unit-tested (19 tests).
- [x] **Release 0.2.0 — pass P1/P2/P3 issue de la revue experte (2026-07-12)** :
      (P1) recorder desktop sur les **événements natifs** de l'API
      (`--engine auto|native|poll` : `Session.Record`+`Change` → commandes exactes,
      boutons/grilles/arbres capturés, OK-code+Entrée fusionnés en
      `Run Transaction` ; hit-test `Hit`+`FocusChanged` pour `--capture` ; repli
      polling automatique) ; **préflight scripting** ECC (`Scripting Should Be
      Fully Enabled` — échec tôt avec le paramètre RZ11) + `Enable Test Tool Mode`
      + `Get Session Telemetry` ; **erreurs auto-corrigibles** (closest matches
      scorés dans les échecs ECC ; hint type-rendu-ou-pas côté Fiori) et
      **perception `mode=diff`** (les deux canaux, `sapfx_common.perception_diff`).
      (P2) **healing unifié** (`sapfx_common.healing` : terminal pondéré + LCS
      chemin + type ; `Resolve Element With Healing`, `Resolve Ui5 With Fallback`
      — réparation toujours journalisée, jamais silencieuse) ; **iframes
      Work Zone/cFLP** (`Set Ui5 Frame`, bundle à double forme d'appel exécuté
      dans la frame, sélecteurs `>>>` ; extension MV3 en `allFrames` ;
      `fiori_frame_smoke.robot` 3/3 live sur iframe réellement cross-origin) ;
      **Fiori Elements** (`idSuffix=fe::…`, Spy FE-aware). (P3) assertion de
      valeur au recorder web (Shift+Alt+clic → `Ui5 Text Should Be`) ; **smoke
      UI5 2.0 nightly** (`fiori_ui5v2_smoke.robot` 4/4 live — branche
      `ElementRegistry`, zéro dépendance aux APIs supprimées). Non-régression
      live : fiori + recorder web + legacy 14/14. 276→362 unit tests.
      Versions : distributions et libs 0.2.0, extension 0.4.0.
- [x] **Smokes ECC live re-validés + événements natifs prouvés (2026-07-12)** :
      `ecc_smoke` 5/5, `ecc_data_smoke` 4/4, `ecc_record_smoke` 1/1 vs A4H
      Docker. Le mode record natif est passé de `DispatchWithEvents` (makepy
      plante sur la typelib sapfewse — pywin32 issue #2433) à une **connexion
      manuelle au point de connexion** `ISapSessionEvents`
      (`advise_session_events`, hack `_query_interface_` canonique de la démo
      pywin32 connect.py). Prouvé live : les actions scriptées ET manuelles
      émettent les `Change` ; une session `--record --engine native` de bout en
      bout a transcrit `Run Transaction /nse16` (OK-code+Entrée fusionnés),
      `Input Text … T000` et le `Click Element wnd[0]/tbar[1]/btn[8]` exact
      (F8) — le cas que le polling ne pouvait pas capter. Reste ouvert :
      validation SAP GUI 8.10 (GA 16/07/2026).
- [x] **Release 0.2.5 (2026-07-12)** : **moteur Web Components** — 3e moteur de
      résolution Fiori (`Resolve/Click/Fill Wc…`) pour les pages UI5 Web
      Components SANS runtime UI5 (registre vide — home SuccessFactors) : scan
      light-DOM des custom elements `ui5-*`, types courts matchant aussi les
      tags scopés `ui5-button-<suffixe>`, comparateur de valeurs factorisé avec
      le moteur role (`valueMatches`), chemins CSS ancrés à l'id le plus proche,
      shadow roots ouverts percés par le CSS Playwright ; repli `wc=` dans
      `Resolve Ui5 With Fallback` (chaîne role→xpath→sid→wc) ; capture/record WC
      dans le recorder web. Validé live 6/6 (`fiori_wc_smoke.robot`, fixture
      hors ligne avec tag scopé réel). **Télémétrie de healing**
      (`sapfx_common.healing_telemetry`, opt-in `SAPFX_HEALING_LOG`) : journal
      JSONL cumulatif alimenté par les deux canaux (ECC score, Fiori moteur) —
      le healing devient maintenance préventive. **Isolation rf-mcp stricte**
      (`SAPFX_MCP_STRICT_SESSION=1`) : refus explicite premier-arrivé-premier-
      servi au lieu du simple warning. **Pack** : `business_data_exploration.robot`
      (campagne SE16 autonome, dérogation documentée à la convention 1) embarqué
      comme 3e suite d'exemple. **CI Windows** : pytest contre le vrai pywin32
      avant le dryrun (détection de dérive des stubs COM). 362→390 unit tests.
      Versions : distributions et libs 0.2.5, extension 0.4.1. Pas de publication
      PyPI (distribution = pack Windows, décision 2026-07-12).
- [x] **Agents de test « plan → generate → heal » (2026-07-12)** : transposition
      du principe Playwright Test Agents au-dessus de rf-mcp. `sap-planner`
      (exploration live perception→action → plan métier `specs/`),
      `sap-generator` (plan → suite `.robot`, chaque étape exécutée live via
      `execute_step` AVANT écriture ; keywords manquants ajoutés à la couche
      resources), `sap-healer` (reproduction, closest matches scorés +
      télémétrie `SAPFX_HEALING_LOG`, vérification live, patch de `resources/`
      — jamais des tests, jamais silencieux ; `robot:skip` documenté si le flux
      métier a réellement changé). Source canonique `.claude/agents/` +
      slash-commands `/sap-*` ; chat modes VS Code/Copilot **générés**
      (`scripts/regen_agent_definitions.py`, garde `--check` en pytest) ;
      `specs/` monolingue français (exemptions par préfixe dans
      `check_bilingual_docs.py`) avec l'exemple SFLIGHT/SE16 aligné sur
      `ecc_data_smoke.robot`. Pack Windows : agents + specs embarqués au
      manifeste ; `install -WithMcp` rend `.mcp.json` ET `.vscode/mcp.json` en
      place (2e gabarit `vscode-mcp.json.template`) — le pack dézippé est un
      workspace agent prêt pour VS Code ; sur pack déployé les agents écrivent
      dans `resources/site_keywords.resource`, jamais dans les fichiers livrés.
      `check_guidance_sync.py` garde aussi les marqueurs de conventions dans
      les définitions d'agents. Dialecte des chat modes vérifié contre le
      générateur de référence de Playwright (`generateAgents.ts` : builtins
      qualifiés `search/readFile`…, outils MCP par outil `rf-mcp-sap/<tool>`,
      tri `vscodeToolsOrder`). Doc bilingue `docs/test-agents.md`.
      **Cycle validé live 3/3 vs A4H (2026-07-12)** : plan SCARR/SPFLI produit
      par le planner (18 compagnies / 14 liaisons observées, écrans de
      sélection relevés champ par champ) ; suite `ecc_scarr_spfli_liaisons.robot`
      générée **7/7 live** (re-vérifiée indépendamment), keywords de sélection
      filtrée ajoutés à la resource (dictionnaires `&{<TABLE>_SELECTION_FIELDS}`) ;
      healer testé **en aveugle** sur dérive simulée `btn[31]`→`btn[13]`
      (diagnostic par perception live + closest matches scorés, patch d'UNE
      ligne resource, zéro test modifié, re-run 7/7). Release **0.3.0** :
      distributions ET les trois `__version__` normalisés (dérive 0.2.x
      réparée — `SapEccLibrary`/`sapfx_common` étaient restés à 0.1.0 malgré
      les CHANGELOG ; verrouillé par `tests/unit/test_version_consistency.py`),
      extension 0.4.1 inchangée. 390→415 unit tests.
- [x] **Release 0.4.0 — localisateurs humains, perception rapide, recorder
      sémantique (2026-07-13)** : fruit de l'analyse comparative RoboSAPiens
      (imbus, Apache-2.0 — techniques portées avec attribution NOTICE) /
      sapient-mcp (sans licence — idées seulement). (A) **chemin rapide
      `GetObjectTree`** (`sapfx_common.object_tree` : un appel COM pour tout le
      sous-arbre, géométrie incluse, repli marche COM automatique) sous la
      perception, le healing et la sémantique ; `include_geometry` sur `Get
      Screen Signature`. (B) **localisateurs humains** (`sapfx_common.semantic`
      + mixin `_semantic.py` : `Find/Fill/Read Field By Label`, `Click Button
      By Label` — libellé visible + géométrie, grammaire `@`/`Gauche @ Haut`/
      `= contenu` ; ambiguïté TOUJOURS remontée avec candidats, contrairement
      au premier-match silencieux de RoboSAPiens) ; healing par **ancre de
      libellé** (`Resolve Element With Healing label=…`, télémétrie
      `engine=label`). (D) rf-mcp : `Get Screenshot As Base64`/`Log Screenshot`
      (HardCopyToMemory, MIME par magic bytes), `get_application_state` lit la
      transaction LIVE (jamais de machine à états optimiste — leçon inverse de
      sapient-mcp), guidance sémantique, agents planner/generator/healer mis à
      jour + chat modes régénérés. (C) recorder desktop : `--semantic` (keywords
      humains vérifiés par re-résolution `describe_element`, id en commentaire ;
      valeur d'un champ modifiable jamais utilisée comme localisateur), vkeys
      lisibles (`# F8`), `--screenshots` via HardCopyToMemory. Backlog :
      `Get Cell Value By Row Content` (ligne par contenu), `Read Abap List`
      (reconstruction géométrique, `sapfx_common.abap_list`), note WebView2/CDP
      dans docs/architecture. Fixed : l'attribut de classe
      `SapEccLibrary.__version__` (resté à 0.2.5 en 0.3.0) est désormais couvert
      par le garde de versions. **Validé live vs A4H (2026-07-13) : 17/17** —
      non-régression `ecc_smoke` 5/5, `ecc_data_smoke` 4/4, `ecc_record_smoke`
      1/1, puis suite de validation dédiée 7/7 : GetObjectTree réel (124
      éléments + géométrie en UN appel COM sur SAP GUI 8.00), `Find/Fill/Read
      Field By Label` sur le vrai écran SE16 (« Table Name » →
      `ctxtDATABROWSE-TABLENAME`), bouton par tooltip, healing `label=`
      (WARNING + `engine=label` observés), `HardCopyToMemory(2)` = PNG confirmé
      par magic bytes, `semanticize_step` transcrit live `Input Text …` en
      `Fill Field By Label    Table Name    T000    # id: …`. Deux leçons
      terrain intégrées : `GuiMenu` exclu des cibles de `Click Button By Label`
      (les menus dupliquent le texte des boutons — ambiguïté détectée par le
      moteur, comme conçu) ; listes ABAP modernes rendues en GuiShell opaque
      sans mode accessibilité (l'échec de `Read Abap List` nomme l'option —
      voir field notes). 415→483 unit tests.
- [x] **Veille écosystème RF+SAP (2026-07-13)** : comparaison web (GitHub, SAP
      Community, help.sap.com) confirmant l'absence de concurrent RF sérieux
      côté Fiori/UI5 et la maturité croissante de RoboSAPiens (imbus, v2.27.0).
      Deux pistes concrètes implémentées : (1) **pont contrôle-navigateur-
      embarqué** — mixin `EmbeddedBrowserKeywords`
      (`src/SapEccLibrary/keywords/_embedded_browser.py`) : `Enable Embedded
      Browser Debugging` (variable d'environnement WebView2/CDP, à appeler
      avant `Open Sap Logon`), `Get Embedded Browser Page Id`/`Switch To
      Embedded Browser Page` (recherche par titre + bascule via la
      bibliothèque Browser sur CDP, sondage jusqu'à rendu). (2) **grammaire de
      localisateurs humains étendue** (`sapfx_common.semantic`) : grilles par
      position `N @ Libellé`/`Libellé @ N` (N-ième champ d'une grille
      verticale/horizontale), et opérateur de portée `Ancre >> Reste`
      (réduction récursive au voisinage d'un libellé unique — désambiguïse un
      libellé répété ailleurs ou un champ sans libellé identifié par son
      tooltip). Les deux réimplémentées sur notre modèle (jamais portées
      verbatim), attribution étendue dans `NOTICE`. 483→508 unit tests.
- [x] **Release 0.5.0 — packaging & distribution (2026-07-13)** : le pack
      Windows rattrape les trois lots fusionnés depuis la 0.4.0. Wheel des
      bibliothèques = 4 paquets (`SapApiLibrary` embarquée, smoke d'import de
      l'installateur étendu) ; 5 suites d'exemple (ajout
      `ecc_drift_sentinel.robot` — veille sans tests, références
      `screen_watch/` créées au premier passage — et
      `flagship_cross_paradigm.robot` — même fait métier par l'écran ET
      l'API) ; scripts de maintenance embarqués (`healing_drift_report.py`,
      `check_spec_sync.py` — stdlib pure, exécutables depuis la racine du
      pack) ; `requirements-deploy.txt` ajoute Pillow (assertions visuelles /
      empreinte sentinelle) et documente le prérequis pyrfc (SDK SAP, hors
      PyPI). Réparé au passage : `SapFioriLibrary.__version__` (attribut de
      classe) resté à 0.2.5 — le garde de versions suit désormais l'attribut
      de classe des TROIS bibliothèques. READMEs du pack (EN/FR) : section
      « Veille et maintenance » (sentinelle, bot télémétrie→patch, garde
      spec). Versions : distributions et libs 0.5.0, extension 0.4.1
      inchangée. Pack reconstruit : `dist/sapfx-pack-0.5.0-win.zip`.
- [x] **Upgrade de perception (2026-07-14, live A4H 5/5 + Demo Kit)** — six
      améliorations issues de la démo « assertion visuelle » : (1) **hash
      visuel par élément** (`Get Element Perceptual Hash`, `Element Should
      Match Baseline` — baseline = PNG recadré, les 64 bits couvrent la zone
      opaque seule) ; (2) **masque des zones volatiles**
      (`mask_elements=auto` : sbar/titl neutralisées avant hachage — le bit
      de la barre de statut tombe, prouvé live) + **tuiles**
      (`Get Screen Tile Hashes`, sentinelle 3 canaux : la dérive locale trop
      diluée pour le hash global est rattrapée par SA tuile, nommée avec
      rectangle + éléments recouvrants) ; (3) **screenshot annoté
      Set-of-Mark** (`Get/Log Annotated Screenshot`, boîtes numérotées +
      légende `numéro -> id` — le chaînon vision→effecteur) ; (4) **diff
      intelligent** (`pair_renames` : ids appariés par le scoring de healing,
      `~ ancien -> nouveau (similarité N%)` — live : SE16→SE38 apparie
      `ctxtDATABROWSE-TABLENAME -> ctxtRS38M-PROGRAMM (62%)`) ; (5)
      **perception sémantique** (`mode=semantic` : vue formulaire à libellés
      humains VÉRIFIÉS — leçon live verrouillée : le vrai SAP GUI marque
      `Changeable=True` sur GuiUserArea/boutons de toolbar,
      `is_editable_field` type-aware partout) ; (6) **parité Fiori du canal
      visuel** (`Get Ui5 Perceptual Hash`, `Ui5 Screen Should Match
      Baseline` — module partagé `sapfx_common.visual_baseline`, validé live
      vs Demo Kit distance 0). Non-régression live : ecc_smoke 5/5,
      sentinelle (références régénérées avec `.tiles.txt`, 2e passage
      inchangé), fiori_smoke 7/7. 617 unit tests, couverture 92%.
- [x] **Release 0.5.2 — packaging & distribution (2026-07-14)** : l'upgrade de
      perception embarqué dans le pack Windows. Versions : distributions et
      les trois `__version__` à 0.5.2, extension 0.4.1 inchangée ; CHANGELOG
      daté (section Unreleased promue, `Pending` SAP GUI 8.10 conservé).
      READMEs du pack (EN/FR) : la sentinelle documente ses références
      3 canaux (`*.tiles.txt`, dérive localisée à la tuile, renommages
      appariés) + nouvelle puce « Assertions visuelles » (baselines
      écran/élément/Fiori, `mask_elements=auto`, `.actual.png`). Manifeste
      du pack inchangé (les nouveautés voyagent dans le wheel). Pack
      reconstruit : `dist/sapfx-pack-0.5.2-win.zip`.
- [x] **Release 0.5.5 — packaging & distribution (2026-07-16)** : le pack
      Windows rattrape la passe de hardening sécurité (préflights
      serveur/poste/posture client, guide `docs/hardening-test-environment.md`,
      smokes legacy-free/CSP/iframes) et les ports de concepts
      playwright-praman (vocabulaire métier, navigation FLP par intent,
      login IDP) — tout voyage dans le wheel, manifeste du pack inchangé.
      READMEs du pack (EN/FR) : nouvelle section « Préflights
      d'environnement » (les trois couples de keywords, mappés sur le guide
      de hardening). Aussi le garde `scripts/check_comms_sync.py` (la comm ne
      peut plus mentir sur la version — né d'un incident réel) et comms/
      resynchronisées (v0.5.5, 669 tests, 94 % de couverture mesurée).
      Versions : distributions et les trois `__version__` à 0.5.5, extension
      0.4.1 inchangée ; CHANGELOG daté (Unreleased promue, `Pending` SAP GUI
      8.10 conservé — GA le jour même, validation à faire dès installation).
      617→669 unit tests. Pack reconstruit : `dist/sapfx-pack-0.5.5-win.zip`.
- [x] **Release 0.5.6 — campagnes cross-canal (2026-07-17, live A4H + Demo Kit)** :
      la passe de productization hardening (section `[Unreleased]` du CHANGELOG :
      scope `SUITE` + partition rf-mcp, Python 3.10+, `Secret` RF 7.4 aux
      frontières auth, CI ZIP qualifié + SBOM/provenance, garde comms) est coupée
      en 0.5.6, avec **trois suites de démonstration auto-suffisantes** (importent
      les librairies directement, aucune resource/suite réutilisée), produites en
      direct via rf-mcp puis rejouées par le vrai `robot`. (1)
      `exploratory_campaign_a4h.robot` (ECC 4/4) : classes de livraison
      DD07L/CONTFLAG (A/C/E/G/L/S/W), cycle d'écriture CRUD **réversible** sur
      SCARR (leçon live : SE16 « Create Entries » se déclenche depuis l'écran
      INITIAL — l'écran de sélection y expose « Execute and Print » — ; suppression
      Select All → Table Entry > Delete → « Delete Entry », commit immédiat ; SM30
      KO sur SCARR), et **balayage DYNAMIQUE** du catalogue TADIR (27 objets Flight
      `SAPBC_DATAMODEL` + 56 EPM `S_NWDEMO_MODEL_DDIC` = 66 tables réelles / 17
      structures de type E). (2) `exploratory_campaign_fiori.robot` (Fiori 6/6,
      navigateur visible) : bannière cookies TrustArc acceptée (id DOM
      `truste-consent-button`), inventaire de contrôles, interaction réversible,
      balayage dynamique de 43 types tous convergents role↔xpath, grammaire xpath
      (hiérarchie + prédicat `@controlType`). (3) `cross_paradigm_api_visual.robot`
      (API+visuel 3/3) : `$count` OData `SEPMRA_SHOP/Products` = 205 = SE16
      `SNWD_PD`, lecture d'entités (Id/Name/Price), assertion visuelle
      `Screen Should Match Baseline` sur l'écran SE16 (empreinte fresh-to-fresh
      distance 0, baseline committée — `.gitignore` étendu
      `!tests/robot/visual_baselines/*.png`, les `*.actual.png` de dérive restent
      ignorés). Deux bugs de timing/assemblage attrapés par le run live (create
      depuis le mauvais écran SE16 ; arbre UI5 capté avant rendu). Versions :
      distributions et les trois `__version__` à 0.5.6 (garde
      `test_version_consistency`), extension 0.4.1 inchangée ; CHANGELOG daté ;
      comms resynchronisées (v0.5.6, 677 tests, 93 %). Suites de démonstration —
      hors périmètre pytest (zéro test unitaire ajouté, 677 inchangé).
- [x] **Sessions hybrides Fiori + multi-session ECC (2026-07-17)** :
      deux axes d'amélioration implémentés. (1) **Pages hybrides Fiori** :
      `Get Page Composition` (sonde de perception — technologies présentes par
      région + moteurs recommandés, descente d'un niveau dans chaque iframe,
      best-effort), **5e moteur `dom`** (`Resolve/Click/Fill Dom…` — les zones
      non-SAP d'une page hybride entrent dans la même grammaire : CSS + texte +
      rôle ARIA + attributs, chemins light-DOM, repli `dom=` dans la chaîne de
      fallback + télémétrie), **pile de frames** `Push/Pop Ui5 Frame`/`Get Ui5
      Frame Stack` (frames imbriquées Work Zone → app → WebGUI, portée chaînée
      `a >>> b` ; `Set Ui5 Frame` remplace la pile — compat totale). (2)
      **Multi-session ECC par alias** (`keywords/_sessions.py`) : `Open Sap
      Session` (2e connexion, login RSYST optionnel avec `Secret`, rollback sur
      échec), `Create Gui Session` (2e fenêtre même connexion, zéro re-login),
      `Switch/List/Close/Close All Sap Sessions` ; état routé par alias
      (`default` = usage historique), rail STA (thread COM propriétaire par
      alias, cross-thread = CoInitialize défensif compatible rf-mcp,
      `SAPFX_STRICT_COM_THREAD=1` = refus actionnable), teardown isolé (une
      connexion partagée n'est jamais fermée). Attrapé par le smoke live :
      `Sid Should Be Visible` cassé en appel Python interne (état chaîne vs
      enum `ElementState` — corrigé par `_wait_visible`, converti aussi dans la
      chaîne de fallback). `fiori_hybrid_smoke.robot` 5/5 (fixture hors ligne,
      frames imbriquées réelles) ; non-régression wc 6/6 + recorder web 3/3 +
      frame 6/6. 677→720 unit tests, couverture 93 % (mesure CI canonique).
      **Validé live vs A4H le
      jour même** : cycle complet piloté via rf-mcp étape par étape (`Open Sap
      Session` — connexion + login intégré —, `Create Gui Session` 2e fenêtre
      sans re-login, transactions indépendantes SE16/SESSION_MANAGER entre
      alias, `List Sap Sessions` JSON-safe à travers MCP, `Close Sap Session`
      isolé — la session survivante reste pilotable), puis la suite
      reproductible `ecc_multisession_smoke.robot` rejouée par le vrai robot :
      **4/4**. Même exercice de symétrie côté **Fiori** : cycle hybride déroulé
      pas-à-pas via rf-mcp sur la fixture (`Get Page Composition` — moteurs
      `sid/wc/dom` recommandés, frame level1 sondée déclarant sa sous-frame —,
      moteur dom count/click/fill vérifiés par relecture JS, pile
      Push→sid(niv.1)→Push→dom(niv.2)→Pop×2, pop-de-trop = erreur nette,
      fallback réparé sur `dom=`), puis `fiori_hybrid_smoke.robot` rejoué par
      le vrai robot : **5/5**. Leçon rf-mcp au passage (voir field notes) : le
      process MCP fige classe ET instance — redémarrer le serveur après
      modification du code de la bibliothèque.
- [x] **Release 0.5.7 — sessions hybrides & multi-session (2026-07-17)** : les
      deux axes ci-dessus coupés en release. Versions : distributions et les
      trois `__version__` à 0.5.7 (garde `test_version_consistency`), extension
      0.4.1 inchangée ; CHANGELOG daté (Unreleased promue — le `Pending`
      SAP GUI 8.10 reste ouvert) ; comms resynchronisées (v0.5.7, 720 tests,
      93 % — la couverture CANONIQUE est celle de la CI ubuntu, 94 % en local
      Windows contre le vrai pywin32 : arbitré par le garde
      `check_comms_sync --verify-runtime`, leçon déjà rencontrée en 0.5.6) ;
      les nouveautés
      voyagent dans le wheel, manifeste du pack inchangé. Pack reconstruit :
      `dist/sapfx-pack-0.5.7-win.zip`.
- [x] **Release 0.5.8 — localisateurs d'accessibilité, diagnostic Fiori,
      alignement des supports (2026-07-18)** : `role=` ARIA **calculé**
      (explicite ou implicite via la sémantique HTML) + nom accessible `name=`
      sur les moteurs dom ET wc (smokes hors ligne wc 7/7 / hybrid 6/6,
      recorder web régénéré) ; couche diagnostic `Get/Log Fiori Diagnostics`
      (`sapfx_common.fiori_diagnostics`) ; passe d'alignement issue du contrôle
      du 18/07 — chaîne de fallback complète (role→xpath→sid→wc→dom) dans les
      hints rf-mcp et sap-healer, moteur dom/`Get Page Composition`/`Push-Pop
      Ui5 Frame` ajoutés aux hints, `Get Page Composition`/`Get Fiori
      Diagnostics` aux étapes de perception des trois agents (chat modes
      régénérés), et GUI recorder desktop exposant enfin `--engine
      auto|native|poll` + `--semantic` (CLI-only depuis 0.2.0/0.4.0). Versions :
      distributions et les `__version__` à 0.5.8 (garde
      `test_version_consistency`), extension 0.4.1 inchangée ; CHANGELOG daté ;
      comms resynchronisées (v0.5.8, 750 tests, 93 % CI ubuntu — couverture
      canonique) ; manifeste du pack inchangé (nouveautés dans le wheel),
      READMEs du pack : options du lanceur recorder. Pack reconstruit :
      `dist/sapfx-pack-0.5.8-win.zip`.
- [x] **Passe d'upgrade des recorders (2026-07-19)** : le déroulé enregistré
      devient un BROUILLON outillé, plus un produit final. (1) **Exports
      post-enregistrement, les deux canaux** : `--suite` (.robot complet
      rejouable), `--export-resources` / menu « resource-first » web (la paire
      `.resource` keywords métier + suite SANS id brut — convention 1, la
      couche que sap-healer répare ; paire desktop validée `robot --dryrun`),
      `--export-spec` / menu « spec » (plan Markdown format `specs/` — le
      recorder devient l'entrée du cycle plan → generate → heal). (2) Desktop :
      **assertions à chaud** Ctrl+Alt+A (valeur du champ focalisé) /
      Ctrl+Alt+V (baseline visuelle) pendant le record ; mappings natifs
      étendus (menus contextuels appariés → `Select Context Menu Item`, arbres
      → `Select Node`, ligne de grille → `Select Table Row`, cellule suivie
      via `currentCell*`) ; suggestion `Click Element At Offset` (position
      relative du curseur) en capture/hover sur GuiShell/GuiChart opaques ;
      GUI Tkinter : cases suite/exports + **panneau de steps live**
      (suivi/édition/sauvegarde du fichier de sortie). (3) Web : **capture du
      moteur dom** (`captureDom` — rôle ARIA calculé + nom accessible, cibles
      interactives seulement : les zones non-SAP des pages hybrides entrent
      dans le record), menu d'assertions au clic droit, Entrée capturée
      (différée après le change), navigation → `Wait For UI5 Ready` (keyword
      embarqué dans l'export autonome), compaction saisies/attentes, alerte
      iframes cross-origin ; extension 0.4.1 → **0.5.0**, artefacts régénérés.
      **Validé LIVE le jour même** — ECC vs A4H : `ecc_record_smoke` 1/1, suite
      dédiée 2/2 (pipeline poll→exports sur steps réels ; ligne d'assertion à
      chaud construite depuis l'élément focalisé live puis REJOUÉE), moteur
      natif OK (fusion `Run Transaction`, bouton exact F8, offset calculé sur
      la vraie grille ALV), et la paire resource-first exportée REJOUÉE par le
      vrai robot contre la session — replay qui a attrapé un bug : `Connect To
      Session` n'obtient que le moteur, jamais la session → nouveau keyword
      **`Attach To Open Session`** (rattachement par index, erreurs
      actionnables, testé unitairement) utilisé par les suites générées. Web
      vs Chromium : smoke 3/3 + suite hybride 1/1 (capture dom role/name,
      compaction, Entrée différée, menu d'assertions, exports resource-first
      — dryrun OK — et spec). 790→793 unit tests ; ruff/mypy verts. Projet
      FRÈRE créé le même jour :
      `rf-web-recorder` (recorder web UNIVERSEL pour la
      bibliothèque Browser, hors périmètre de ce dépôt — le moteur dom y est
      porté et généralisé, attribution SAPFX dans son NOTICE).
- [x] **Passe « esprit Selenium IDE » des recorders (2026-07-19)** : greffer
      la bonne moitié du record-and-playback (feedback immédiat, éditabilité,
      localisateurs de repli, filiation ALT+F12 native SAP) sur nos
      localisateurs sémantiques et sorties resource-first. **Web** : replay
      in-page `play` (mêmes moteurs de résolution, repli xpath réessayé,
      arrêt au premier échec, les événements synthétiques jamais
      ré-enregistrés — validé live : le clic rejoué incrémente réellement le
      compteur de la fixture) ; steps UI5 **nés auto-réparables** (indice
      `# xpath:` à l'enregistrement → `Resolve Ui5 With Fallback` dans
      l'export resource-first) ; multi-scénarios `+test` (bootstrap dans le
      seul premier test) ; **import** d'un .robot exporté (round-trip
      identique octet à octet, validé live) ; édition in-place au
      double-clic ; et correction d'une vraie faiblesse héritée : le
      preventDefault global du mode record GELAIT l'application — les clics
      passent désormais (seuls les gestes méta Alt+clic sont avalés).
      Extension 0.5.0 → **0.6.0**. **ECC** : `--replay FILE` + bouton GUI
      « Rejouer » (rejoue contre la session ouverte via `Attach To Open
      Session`, arrêt au premier échec — validé live 4/4 vs A4H) ;
      `--transpile-vbs FILE` (enregistrements ALT+F12 → keywords via la MÊME
      machine à états que le natif, sans session SAP — validé de bout en bout
      live : VBS → transpile → `--replay` 4/4, paire resource-first en
      dryrun) ; export resource-first **auto-réparable** des lignes
      `--semantic` (`Resolve Element With Healing … label=…`) ; édition GUI
      au double-clic. 790→808 unit tests ; ruff/mypy verts ; smoke web 3/3.
      Le projet frère rf-web-recorder reçoit la même passe (replay, édition,
      fallback IF/ELSE, multi-tests, import — v0.3.0).
- [x] **Validation LIVE du recorder web contre une vraie app Fiori Elements
      (2026-07-20)** : cible = cap-sflight local (List Report v4, UI5 1.139 du
      CDN, 591 contrôles rendus, 4 133 voyages), pas un fixture. Chaîne prouvée
      4/4 : injection dans l'app réelle ; record de gestes réels (recherche
      « Aussie » + Go) donnant des localisateurs de **contrôles UI5** —
      `idSuffix=fe::FilterBar::Travel::BasicSearchField-inner`, l'id stable
      Fiori Elements, jamais les `__clone…` générés du DOM ; survie du déroulé
      à un **rechargement complet** (sessionStorage) ; **replay in-page dont
      l'effet est MESURÉ sur l'app** (`Travels (4,133)` → `Travels (91)`, et le
      rechargement défait bien le filtre entre les deux) ; les trois formats
      d'export ; la suite exportée **rejouée verte par le vrai `robot`** ; la
      paire resource-first (zéro localisateur dans la suite) rejouée verte
      aussi. Le live a attrapé DEUX défauts que ni les fixtures ni le `--dryrun`
      ne pouvaient voir : (1) l'export resource-first remplissait la **racine**
      d'un champ UI5 composite (`<div>`) au lieu de son `<input>` interne — le
      dryrun passait, le run échouait ; (2) l'en-tête du panneau débordait ses
      7 boutons à 380 px et `overflow:hidden` rendait **`stop` inatteignable**
      (vu à l'image). Les deux corrigés et verrouillés par tests unitaires
      (808→810). Livrable comm : `tools/recorder_web/demo/fiori_demo_video.robot`
      (démo scénarisée, sous-titres incrustés, headless par défaut) →
      `comms/visuels/sapfx-fiori-recorder-demo.mp4` (H.264, 1280×720, 48 s) +
      4 images clés. Prérequis : `cd _cap-sflight && npx cds watch`.
- [x] **Validation LIVE du recorder ECC + prise vidéo (2026-07-20)** : pendant
      ECC de la passe Fiori, contre A4H. Pipeline complet vert **4/4**
      (`ecc_smoke` 5/5 et `ecc_record_smoke` 1/1 en sanité préalable) :
      enregistrement d'un parcours réel par le moteur record (OK-code + Entrée
      fusionnés en `Run Transaction /nSE16`, `Input Text` sur l'id relevé,
      `Send Vkey`), les TROIS exports depuis le même enregistrement brut —
      jamais modifié —, `--dryrun` de la paire resource-first (suite SANS aucun
      `wnd[…]`, ids confinés à la resource), et **replay contre la session
      ouverte** (3 steps, écran d'arrivée `Data Browser: Table T000: Selection
      Screen`). Aucun défaut produit trouvé côté ECC ; deux pièges d'usage
      relevés, tous deux diagnostiqués par l'état live plutôt que devinés :
      (1) le moteur ne peut fusionner l'OK-code que si le sondage a lieu ENTRE
      la saisie et la validation — sonder après coup ne laisse qu'un
      `Send Vkey`, et le replay le signale honnêtement en échouant faute de
      navigation ; (2) `Run Transaction SESSION_MANAGER` **rapporte un succès
      alors qu'un modal d'erreur reste affiché** (« Cannot start transaction
      SESSION_MANAGER ») — le contrôle porte sur `Info.Transaction`, qui valait
      déjà SESSION_MANAGER ; ce modal résiduel neutralise ensuite le champ
      OK-code. Le retour au menu se fait par l'OK-code système `/n`. Aucune
      suite du dépôt n'est concernée (elles ASSERTENT SESSION_MANAGER, ne le
      lancent pas). Livrable comm :
      `tools/recorder/demo/ecc_demo_video.robot` → `comms/visuels/
      sapfx-ecc-recorder-demo.mp4` (H.264, 1248×944, 51 s) + 3 images clés.

- [x] **Release 0.6.0 — recorders coupés en release après revue par les pairs
      (2026-07-20)** : les passes recorders des 19-20/07 (exports
      resource-first/spec, replay, transpile VBS, démos vidéo) relues avant
      commit, chaque constat corrigé et verrouillé par tests : appariement
      `name=`/`text=` à blancs normalisés côté DOM (moteurs dom ET wc),
      échappement RF des valeurs enregistrées du canal desktop (miroir de
      l'échappement web ; champ vidé → `${EMPTY}`, `--replay` applique
      l'inverse exact), la GUI ne réécrase plus l'enregistrement précédent,
      les exports spec ne fuient plus de localisateur dans les étapes non
      traduites, la paire assertion-texte du web devient UN keyword métier
      (fuite convention 1), double-Entrée délibérée conservée, `Attach To
      Open Session` robuste à une connexion fermée en cours de rattachement,
      démo cap-sflight authentifiée contre le mocked-auth cds v9 (`alice`).
      Extension web 0.6.0 → **0.7.0** (état de record persistant à la
      navigation — reprise auto après rechargement —, état explicite
      inter-frames `setRec`). Les deux recorders re-validés live après
      correctifs (ECC 3/3 vs A4H, web 1/1 vs cap-sflight). 810→823 tests.
- [x] **Release 0.6.1 — passe « review feedback » (2026-07-22)** : réglages
      d'attente dynamiques `Set Default Timeout`/`Set Poll Interval` (ECC) et
      `Set Ui5 Timeout`/`Set Poll Interval` (Fiori) — ancienne valeur
      retournée en chaîne de temps Robot, restaurable en teardown, portée
      l'instance (`SUITE`), nouvelle valeur validée AVANT adoption ; validés
      live vs A4H et sur runtime UI5 réel (4/4 + 4/4, le timeout réduit est
      bien le budget d'attente effectif). Les deux échecs Fiori génériques
      nomment la couche diagnostic (`Log Fiori Diagnostics`,
      `Get Page Composition`). Correctifs : `Run Transaction` tcodes de
      namespace 2e passe (normalisation identique des deux côtés +
      `_has_nav_prefix` — `/IWFND/…` n'est plus pris pour un préfixe `/i` ;
      vérifié live, `Info.Transaction` retourne la forme sy-tcode AVEC slash) ;
      `--transpile-vbs` décode BOM UTF-8/16, UTF-16 sans BOM et ANSI
      (`decode_vbs_source` — l'UTF-16 forcé en UTF-8 donnait 0 step SANS
      exception) ; exports spec en code spans CommonMark (`md_code`/`mdCode` —
      `*LH*` ne se rend plus en italique) ; le moteur polling enregistre
      décochages et vidages de champ (le natif le faisait déjà) ; `--replay`
      CLI construit la lib avec `screenshots_on_error=False` (hors contexte RF
      le handler masquait l'erreur réelle). Constante morte
      `_ERROR_MESSAGE_TYPE` supprimée. 823→845 tests.
- [x] **Release 0.6.2 — mise à niveau de la couche agentique (2026-07-23)** :
      (1) guidance + cartes de keywords rf-mcp rattrapent trois releases
      (multi-session, `Attach To Open Session`, `mode=semantic`, Set-of-Mark,
      baselines visuelles, effecteur pointeur, timeouts dynamiques, FLP/IDP/
      vocabulaire) + garde de fraîcheur des cartes dans
      `check_guidance_sync.py` ; (2) state providers en diff intelligent ;
      (3) `Get Open Windows` + `get_application_state` enrichi
      (`modal_open` — piège SESSION_MANAGER, type de message, télémétrie) ;
      (4) `_staleness.py` (code SAPFX changé après démarrage du serveur =
      warning) ; (5) hygiène de session encodée dans les 3 agents ;
      (6) `/sap-maintain` et (7) éval en aveugle du healer
      (`agent_eval_harness.py` + `/sap-eval-healer`). Ventilation
      industrielle encodée generator/healer (suites
      `tests/robot/{api, ui/ecc, ui/fiori, cross}`, page objects,
      `variables/`). **Surcouche `sapfx-mcp`** v1 (`sapfx_state`,
      `sapfx_screenshot`, `sapfx_reload`, garde `_compat.py`) — validée live
      le jour même 16/16 vs A4H et 12/12 vs Demo Kit. **Le canal API entre
      dans MCP** : `SapApiPlugin` + keyword `List Api Sessions` (état du
      canal sans écran, jamais de credentials) — validé live 9/9 vs la
      Gateway A4H. 845→921 tests.
- [x] **Release 0.6.3 — cartes numérotées `@N`, skill sapfx, boucles agents
      fermées, compat rf-mcp 0.35.0 (2026-07-27)** : carte numérotée façon
      Vibium (`Get Screen Map` → `Resolve/Click/Fill Screen Ref` côté ECC ;
      miroir Fiori `Get Ui5 Page Map` → `… Ui5 Ref`) — références éphémères
      re-vérifiées avant chaque action, pilotage interactif seulement ;
      skill `sapfx` (la boîte à outils apprise en un appel, embarquée dans le
      pack) ; boucles de feedback agents fermées mécaniquement (marqueur
      `PÉRIMÉE` bloquant `check_spec_sync`, section « Écarts constatés à la
      génération », `docs/heal-journal.md`, `check_conventions.py` + hook
      `PostToolUse` + CI) ; compat rf-mcp 0.35.0 (fenêtre du garde élargie à
      [0.31, 0.36), sonde lazy-proxy-safe, pin de déploiement 0.35.0, piège
      de classification desktop documenté — voir field notes) ; fix pack :
      `.cmd` en CRLF (`.gitattributes` + normalisation au build) ;
      `check_spec_sync` en rglob (suites ventilées) + date dans le marqueur
      de provenance. 921→963 tests (couverture canonique CI ubuntu : 93 %).
