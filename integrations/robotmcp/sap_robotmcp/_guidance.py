"""Guidance SAP injectée dans rf-mcp via ``LibraryHints`` / ``PromptBundle``.

C'est l'équivalent SAP de ``get_locator_guidance`` de rf-mcp (qui ne connaît que
Browser/Selenium/Appium). On encode ici les conventions du projet (cf. CLAUDE.md)
pour que l'agent (autonome **ou** assistant IDE) adresse les bons sélecteurs et
écrive des assertions stables.
"""

# Règles communes (reprises des "Conventions" du CLAUDE.md), formulées comme
# error_hints : ce que l'agent doit corriger s'il s'écarte.
COMMON_HINTS = [
    "Parler le vocabulaire métier de resources/*.resource ; ne jamais mettre d'id "
    "SAP brut ni de CSS/XPath dans un test.",
    "Ne jamais time.sleep pour attendre SAP : utiliser Wait Until Busy Done / "
    "Wait Until Element Present (ECC) ou laisser la résolution sonder le rendu (Fiori).",
]

FIORI_HINTS = [
    "PRÉREQUIS : la session doit importer Browser ET SapFioriLibrary, puis "
    "New Browser + New Page AVANT tout keyword UI5. SapFioriLibrary ne pilote pas "
    "la page : elle réutilise l'instance Browser vivante du même contexte RF.",
    "Adresser des CONTRÔLES UI5 (controlType + properties / bindingPath / viewId), "
    "jamais des ids DOM : ceux-ci changent à chaque rendu.",
    "controlType accepte la forme courte (Button) ou pleine (sap.m.Button) ; "
    "properties : sous-chaîne insensible à la casse, ou /regex/flags.",
    "Pour voir l'écran avant d'agir, appeler d'abord le keyword de perception "
    "(arbre de contrôles UI5), puis en déduire le sélecteur. Après une action, "
    "préférer Get Ui5 Page Tree mode=diff : seul CE QUI A CHANGÉ est retourné "
    "(fraction des tokens).",
    "Type ambigu -> UI5 XPath hiérarchique (//Table//Button[@text='Edit']) ; "
    "Get Ui5 Xpath renvoie le plus court unique.",
    "Boucle courte perception -> action : Get Ui5 Page Map numérote les cibles "
    "actionnables (@1, @2…) puis Click Ui5 Ref / Fill Ui5 Ref agissent par "
    "NUMÉRO : pas d'id à recopier, la résolution re-vérifie que le contrôle "
    "est toujours rendu et échoue proprement sinon (re-percevoir). Dans une "
    "SUITE, rester sur les localisateurs de contrôles/resources (les @N sont "
    "éphémères, réservés au pilotage interactif).",
    "Écran qui ne répond pas comme attendu ? Get Fiori Diagnostics agrège en "
    "UN dict JSON-safe : composition hybride, arbre UI5 (absent = anomalie "
    "nommant les moteurs/frames de repli), erreurs console et erreurs de page "
    "(Browser 20), snapshot ARIA des zones non-SAP ; lire d'abord sa synthèse "
    "`issues`. Log Fiori Diagnostics écrit le rapport Markdown dans le log.",
    "Apps Fiori Elements V4 : préférer idSuffix=fe::table::<Entity>::LineItem::"
    "Table (ids stables documentés : le préfixe app/route varie, le suffixe non).",
    "Launchpad Work Zone / cFLP : l'app tourne dans une IFRAME ; appeler "
    "Set Ui5 Frame <sélecteur iframe> avant de résoudre, sinon le shell (vide) "
    "est interrogé. Set Ui5 Frame sans argument revient à la page principale ; "
    "frames IMBRIQUÉES (Work Zone -> app -> WebGUI) : Push Ui5 Frame / "
    "Pop Ui5 Frame empilent la portée (sélecteurs chaînés a >>> b).",
    "Localisateur fragile ou en dérive ? Resolve Ui5 With Fallback (role -> "
    "xpath -> sid -> wc -> dom) répare avec un warning journalisé, jamais en "
    "silence.",
    "Pages SAP GUI for HTML (non-UI5) : moteur sid (Resolve Sid / Click Sid / "
    "Fill Sid Input), qui matche le SID stable de l'attribut lsdata.",
    "Pages « pur UI5 Web Components » (home SuccessFactors, apps "
    "ui5-webcomponents) : PAS de registre UI5, Get Ui5 Page Tree échoue ; "
    "utiliser le moteur wc (Resolve/Click/Fill Wc …) qui scanne les custom "
    "elements ui5-* du light DOM (tag=Button matche aussi les tags scopés "
    "ui5-button-<suffixe>).",
    "Zones NON-SAP d'une page hybride (widget React/Angular/vanilla) : moteur "
    "dom (Resolve/Click/Fill Dom …) : CSS + texte + rôle ARIA CALCULÉ (explicite "
    "ou implicite : un <button> nu matche role=button) + nom accessible name= "
    "(le localisateur « intention utilisateur », façon getByRole(name=…) ; "
    "name= existe aussi côté wc). Page inconnue ? Get Page Composition dit "
    "quelles technologies cohabitent où, avec les moteurs recommandés par région.",
    "Compatibilité : la résolution fonctionne d'UI5 1.4x (launchpads pré-2019, "
    "repli DOM automatique) jusqu'à UI5 2.x, aucun réglage à faire côté agent.",
    "Navigation launchpad STABLE : Open Fiori App <SemanticObject-action> ; le "
    "hash d'intent survit aux changements de catalogue/thème/langue (la "
    "resource Open App By Intent enchaîne le Wait For UI5 Ready).",
    "Login d'entreprise : Log In Via Identity Provider (presets sap-ias / "
    "azure-ad / generic ; déroulés une-page ET deux-étapes détectés "
    "dynamiquement ; mot de passe jamais journalisé).",
    "Exploration : Set Ui5 Timeout (p.ex. 5s) fait échouer vite les sondes de "
    "localisateurs (l'ancienne valeur est retournée, la restaurer en teardown) ; "
    "Set Poll Interval règle la fréquence de sondage.",
    "Assertion visuelle : Get Ui5 Perceptual Hash / Ui5 Screen Should Match "
    "Baseline : même cycle snapshot que l'ECC (baseline créée au 1er passage, "
    ".actual.png sauvé en cas de dérive).",
    "Après une action qui déclenche un aller-retour OData (Go de FilterBar, "
    "tri, navigation) : Wait For Ui5 Idle attend le VRAI repos (requêtes "
    "XHR/fetch en vol + indicateurs busy + calme continu) : « rendu » ne "
    "veut pas dire « données arrivées », asserter trop tôt lit l'écran "
    "d'avant. Fonctionne aussi sur les pages WC/hybrides (compteurs "
    "réseau/DOM, pas le runtime UI5).",
    "Messages applicatifs : Get Ui5 Messages lit le MessageManager + les "
    "MessageToast récents (hook posé à l'injection) ; asserter par TYPE "
    "(Ui5 Should Have No Messages Of Type Error), jamais sur le texte "
    "localisé : le miroir web du type de message de barre d'état ECC.",
    "Tables : Read Ui5 Table lit une sap.m.Table / sap.ui.table.Table en "
    "liste de dicts par en-têtes (le miroir de Read Grid ECC) ; Upload File "
    "Via Ui5 téléverse dans un contrôle d'upload (l'input interne est visé à "
    "travers les shadow roots ouverts).",
    "Terme métier FR/EN -> champ ABAP/table : Lookup Business Term (exposé par "
    "les DEUX bibliothèques ; ambiguïté toujours remontée avec les candidats, "
    "jamais de premier-match silencieux).",
]

ECC_HINTS = [
    "Assertions indépendantes de la locale : vérifier le TYPE du message de barre "
    "d'état (E/S/W/I), jamais le texte localisé. C'est pourquoi Run Transaction est surchargé.",
    "Adresser les champs par leur id relatif exposé dans resources/, pas par l'id "
    "absolu de session.",
    "Grilles ALV : adresser par titre de colonne (cf. Read Grid), pas par index. "
    "Pour des assertions locale-indépendantes, comparer les ids TECHNIQUES de "
    "colonnes (Get Grid Column Ids), pas les titres affichés.",
    "Tables de dynpro CLASSIQUES (GuiTableControl : FB60, VA01 ancienne "
    "génération…) : Read Table Control / Get Table Control Cell / Set Table "
    "Control Cell / Find Table Control Row adressent par TITRE de colonne et "
    "défilent automatiquement (seules les lignes visibles existent côté COM ; "
    "l'objet est ré-acquis après chaque scroll). L'ALV, elle, reste sur "
    "Read Grid (l'erreur redirige dans les deux sens).",
    "Aide à la recherche d'un champ : Pick F4 Value ouvre le matchcode, "
    "choisit l'entrée (grille de résultats double-cliquée, ou liste par F2) "
    "et referme ; valeur introuvable = popup refermé + échec listant un "
    "échantillon des valeurs visibles.",
    "SE16 : la sortie par défaut est la liste ABAP classique, SANS objet grille "
    "scriptable : appeler d'abord `Use ALV Grid In Data Browser` (resource ECC, "
    "persistant par utilisateur) ; SE16N n'existe pas sur l'ABAP Platform Trial.",
    "Écran inconnu ? Appeler Get Screen Signature pour voir les ids/types réels "
    "avant de deviner un localisateur. Après une action, préférer mode=diff : "
    "seul ce qui a changé est retourné (fraction des tokens).",
    "En Suite Setup, appeler Scripting Should Be Fully Enabled : les modes "
    "readonly/per_user/disable_recording du serveur dégradent le scripting SANS "
    "erreur franche ; ce préflight échoue tôt avec le paramètre RZ11 à corriger.",
    "Id périmé (sous-écran renuméroté) ? Resolve Element With Healing score les "
    "contrôles réels et répare au-dessus d'un seuil, avec warning journalisé ; "
    "avec label=<libellé visible> il tente aussi l'ancre de libellé (un libellé "
    "survit aux renumérotations d'écran) ; les erreurs de Wait Until Element "
    "Present listent déjà les ids les plus proches.",
    "Pas d'id sous la main ? Localisateurs HUMAINS : Find Element By Label / "
    "Fill Field By Label / Read Field By Label / Click Button By Label ciblent "
    "par libellé visible (grammaire : `Libellé`, `@ Libellé` = dessous, "
    "`Gauche @ Haut` = intersection, `= contenu`) : résolution géométrique sur "
    "l'écran réel, ambiguïté remontée avec la liste des candidats, jamais de "
    "premier-match silencieux. Les ids restent le chemin nominal dans resources/.",
    "Écran illisible en texte ou preuve visuelle requise ? Get Screenshot As "
    "Base64 (PNG base64 en mémoire, MCP-safe) ; Log Screenshot l'incruste dans "
    "le log Robot en data-URI.",
    "Sortie de report en LISTE ABAP classique (SE38/SA38, pas d'ALV) : lire avec "
    "Read Abap List (reconstruction géométrique). Prérequis POSTE : sans le mode "
    "accessibilité SAP GUI, ces listes sont rendues dans un shell opaque sans "
    "aucun label ; appeler Get List Rendering Status / Abap List Should Be "
    "Readable pour le constater et le NOMMER (c'est un réglage à provisionner, "
    "jamais à basculer depuis un test : il exige un redémarrage du client).",
    "Données de démo A4H : garanties par resources/a4h_demo_data.resource "
    "(Ensure Flight/EPM Demo Data Exists) ; SE16 sur SFLIGHT/SNWD_PO jamais vide.",
    "Perception en un appel : Get Screen Signature mode=semantic = vue FORMULAIRE "
    "(une ligne par cible actionnable, libellé humain vérifié + id + valeur) ; "
    "souvent le meilleur point de départ sur un écran inconnu. Get/Log Annotated "
    "Screenshot = screenshot Set-of-Mark (boîtes numérotées + légende "
    "numéro -> id) pour croiser vision et action déterministe.",
    "Boucle courte perception -> action : Get Screen Map numérote les cibles "
    "actionnables (@1, @2…) puis Click Screen Ref / Fill Screen Ref agissent "
    "par NUMÉRO : pas d'id à recopier, la résolution re-vérifie l'écran et "
    "échoue proprement si les références sont périmées (re-percevoir). La "
    "légende du screenshot annoté alimente la même table @N. Dans une SUITE, "
    "rester sur les ids/resources (les @N sont éphémères, réservés au pilotage "
    "interactif).",
    "Après Run Transaction, vérifier l'atterrissage RÉEL : Get Current "
    "Transaction peut déjà porter le tcode alors qu'un MODAL d'erreur est resté "
    "ouvert et neutralise l'OK-code (vu live sur SESSION_MANAGER). Get Open "
    "Windows liste les fenêtres ouvertes (modal_open dans l'état applicatif) ; "
    "refermer via Cancel Popup.",
    "Multi-session par ALIAS : Open Sap Session (nouvelle connexion) / "
    "Create Gui Session (2e fenêtre de la MÊME connexion : zéro re-login, la "
    "voie recommandée pour « écrire dans une session, vérifier dans l'autre ») / "
    "Switch Sap Session / List Sap Sessions / Close Sap Session. C'est du "
    "MULTIPLEXAGE (une session active à la fois, bascule explicite), jamais du "
    "parallélisme de threads.",
    "Session SAP GUI déjà ouverte (replay, reprise) ? Attach To Open Session "
    "rattache moteur + connexion + session par INDEX ; Connect To Session seul "
    "n'obtient que le moteur. TOUJOURS refermer les sessions ouvertes en fin de "
    "mission, MÊME SUR ÉCHEC (Close SAP / Close All Sap Sessions) : une "
    "connexion orpheline décale les indices du prochain attach.",
    "Zones officiellement HORS API (intérieur d'un GuiShell opaque, GuiChart, "
    "drag & drop) : Get Element Screen Region (la moitié perception) + Click "
    "Element At Offset (clic matériel à une position RELATIVE dans l'élément) ; "
    "le repli hybride : déterministe d'abord, geste matériel en dernier recours.",
    "Exploration : Set Default Timeout (p.ex. 5s) fait échouer vite les sondes "
    "de localisateurs (l'ancienne valeur est retournée, la restaurer en "
    "teardown) ; Set Poll Interval règle la fréquence de sondage.",
    "Assertion visuelle (ce que l'API Scripting ne voit pas) : Screen Should "
    "Match Baseline (mask_elements=auto neutralise sbar/titl), Element Should "
    "Match Baseline (zone d'UN élément), Get Screen Tile Hashes (dérive "
    "localisée à la tuile) ; Check Screen Against Watch = sentinelle de dérive "
    "(référence créée au 1er passage, chaque écart nommé ensuite).",
    "Terme métier FR/EN -> champ ABAP/table : Lookup Business Term (vocabulaire "
    "MM/SD/FI + Flight ; ambiguïté toujours remontée avec les candidats, jamais "
    "de premier-match silencieux).",
]

API_HINTS = [
    "Le canal API n'a PAS d'écran : la perception EST la valeur de retour des "
    "keywords (listes/dicts JSON). List Api Sessions donne l'état du canal "
    "(alias ouverts, base_url, sap-client, authentifié, compteurs de "
    "télémétrie, entités suivies ; jamais de credentials).",
    "Patron recommandé (suite flagship) : préparer et RECOUPER les données par "
    "l'API, ne piloter l'écran que pour ce qu'on teste : le même fait métier "
    "vérifié par deux canaux indépendants vaut plus que deux fois le même canal.",
    "Sessions par ALIAS : Open Api Session <base_url> user=... password=... "
    "sap_client=... (password de type Secret RF, jamais en clair dans une "
    "suite ni un fichier de variables) ; plusieurs systèmes simultanés ; "
    "Close All Api Sessions en teardown.",
    "OData v2 ET v4 avec les MÊMES keywords : Get Odata Entities aplatit "
    "l'enveloppe (d.results v2, value v4) ; préférer Get Odata Count "
    "($count serveur) à un chargement d'entités pour compter ; les options "
    "système passent en arguments nommés (top=5 -> $top=5).",
    "Post Odata applique le protocole CSRF SAP automatiquement (fetch du "
    "token + rejeu) ; ne jamais le réimplémenter à la main.",
    "CRUD complet + fabrique de données : Post Odata track=True enregistre "
    "l'entité créée, Patch Odata / Delete Odata (CSRF + If-Match gérés), "
    "Delete Created Entities nettoie en teardown (ordre inverse, best-effort, "
    "rapport JSON-safe), Ensure Odata Entity crée seulement si absent : le "
    "cycle de données RÉVERSIBLE par l'API, sans passer par l'écran.",
    "Listes paginées côté serveur (S/4 plafonne souvent à 100) : "
    "Get Odata Entities follow_next=True suit __next/@odata.nextLink ; sans "
    "lui la lecture peut être PARTIELLE en silence (faux positifs).",
    "N opérations en UN aller-retour : Post Odata Batch (multipart, v2 ET "
    "v4 ; écritures regroupées dans UN changeset atomique par défaut) ; "
    "Call Odata Function pour les function imports (v2) et actions (v4).",
    "PERCEPTION du canal : Get Odata Metadata parse le $metadata (entity "
    "sets, clés, propriétés, libellés sap:label ; mis en cache par session) ; "
    "Find Odata Property By Label = le localisateur « libellé humain » côté "
    "API (ambiguïté remontée avec les candidats) ; List Odata Services "
    "découvre les services actifs via le catalogue Gateway.",
    "PRÉFLIGHT : Gateway Should Be Active échoue tôt en nommant la "
    "remédiation (conteneur A4H re-créé -> HTTP 500 /IWFND/CM_COS/003 -> "
    "activité IMG /IWFND/IWF_ACTIVATE) ; Wait Until Api Available attend un "
    "système qui (re)démarre, jamais de time.sleep ; Get Api Telemetry "
    "expose compteurs/latences par alias.",
    "Auth au-delà du Basic : OAuth2 client credentials (token_url + "
    "client_id + client_secret, S/4 Cloud / BTP) et certificat client mTLS "
    "(client_cert/client_key) sur Open Api Session ; token demandé et "
    "rafraîchi automatiquement, jamais journalisé.",
    "RFC optionnel via pyrfc (SAP NW RFC SDK requis) : Open Rfc Connection / "
    "Call Rfc ; l'erreur donne la marche à suivre si pyrfc manque. Au-dessus, "
    "le pattern BAPI : Call Bapi vérifie la table RETURN par TYPE (E/A/X = "
    "échec listant les messages, jamais le texte localisé), puis Commit Bapi "
    "Transaction (WAIT) ; Rollback Bapi Transaction après un échec. "
    "Wait For Background Job suit un job de fond via RFC_READ_TABLE sur "
    "TBTCO (statut A = échec immédiat), sans occuper aucun écran.",
]

API_RECOMMENDATION = (
    "Canal API SAP (OData v2/v4, RFC) : SapApiLibrary, stdlib pure. Ouvrir "
    "une session par alias (Open Api Session, password Secret ; OAuth2/mTLS "
    "possibles), vérifier la Gateway (Gateway Should Be Active), lire par "
    "Get Odata Entities (follow_next=True pour tout lire) / Get Odata Count, "
    "écrire par Post Odata / Patch Odata / Delete Odata (CSRF automatique, "
    "track=True + Delete Created Entities = teardown garanti), explorer par "
    "Get Odata Metadata / List Odata Services. Le canal de PRÉPARATION et de "
    "RECOUPEMENT des données : l'écran ne sert qu'à tester l'écran."
)

FIORI_RECOMMENDATION = (
    "SAP Fiori / SAPUI5 : Browser (Playwright) pilote la page ; SapFioriLibrary "
    "convertit un sélecteur de CONTRÔLE UI5 stable en cible DOM, en réutilisant "
    "l'instance Browser vivante du même contexte RF (get_library_instance). "
    "Mise en place OBLIGATOIRE : importer Browser ET SapFioriLibrary dans la session, "
    "puis New Browser + New Page sur l'URL Fiori. Ensuite, boucle conseillée : "
    "(1) Get Ui5 Page Tree pour voir l'arbre de contrôles, (2) choisir un "
    "controlType/properties ou un UI5 XPath, (3) agir via Click Ui5 Control / "
    "Fill Ui5 Input. Ne jamais coder d'id DOM en dur."
)

ECC_RECOMMENDATION = (
    "SAP GUI desktop (ECC/S4) via COM : SapEccLibrary pilote le client lourd. "
    "Naviguer par Run Transaction, attendre via Wait Until Busy Done, lire les "
    "grilles ALV par titre de colonne, et vérifier le TYPE du message de barre "
    "d'état (E/S/W/I), jamais le texte localisé."
)
