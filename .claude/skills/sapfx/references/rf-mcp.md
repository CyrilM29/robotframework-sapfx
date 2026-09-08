# Travailler en agent : rf-mcp et la surcouche `sapfx-mcp`

SAPFX ne fournit pas de serveur MCP autonome : il compose AU-DESSUS de rf-mcp
(RobotMCP) par trois plugins (`SapEccPlugin`, `SapFioriPlugin`, `SapApiPlugin`)
plus une surcouche `sapfx-mcp` qui monte le serveur rf-mcp INCHANGÉ et ajoute
les outils que le contrat plugin ne permet pas.

## Les outils propres à SAPFX

- `sapfx_state` : appelle les state providers en DIRECT (diff par défaut,
  `application_state` enrichi). C'est la voie fiable pour l'état.
- `sapfx_screenshot` : une vraie image MCP, brute ou Set-of-Mark avec légende.
- `sapfx_reload` : hot-reload de la couche plugin.

## Les pièges du pont MCP

- **Dire « SAP GUI » ou « ECC », jamais « desktop ».** Un `manage_session init`
  dont le texte de scénario contient un signal desktop (« desktop », « win32 »,
  `*.exe`) force la session en DESKTOP_TESTING : `get_session_state` sert alors
  un stub PlatynUI et n'appelle JAMAIS le provider SAP. L'outil `sapfx_state`
  est insensible au piège.
- **`sapfx_state` regarde les bibliothèques IMPORTÉES de la session**, pas
  celles qu'une resource embarque : après un simple `import_resource`, il
  refuse alors que tous les keywords fonctionnent. Ajouter
  `manage_session import_library SapFioriLibrary` (ou `SapEccLibrary`).
- **Ne jamais RETOURNER un objet COM à travers la frontière MCP** : la
  sérialisation a lieu sur un autre thread (`RPC_E_WRONG_THREAD`). Terminer un
  lot par `Element Should Be Present` plutôt que par
  `Wait Until Element Present`.
- **`execute_batch` et `Evaluate` tournent sur un AUTRE thread que le keyword
  qui a lié la session COM, et la bibliothèque le cache** (mesuré 2026-09-07) :
  `Get Screen Signature` rend `# screen ?` sans élément, `Get Open Windows`
  rend `[]`, `Wait Until Busy Done` rend « still busy » sur un écran au repos,
  tout en PASS. Passer `use_context=true` sur CHAQUE `execute_step` de keyword
  SapEccLibrary, ne jamais utiliser `execute_batch` pour du COM, ne jamais
  toucher un objet COM depuis `Evaluate`, et devant un `# screen ?` :
  `Attach To Open Session    0    0`. Pour des sondes COM (sous-types, arbres,
  combos), jouer une suite par `robot` sur le thread principal. Depuis le
  soir du 2026-09-07 la bibliothèque ÉCHOUE en nommant la cause
  (`ScreenUnreadableError`) au lieu de rendre une vue vide, et son rail STA
  ré-attache la session par thread (prouvé à travers rf-mcp : un batch sur
  thread étranger rend la pile et la signature réelles) ; `use_context=true`
  reste la consigne, parce qu'un serveur qui n'a pas rechargé la bibliothèque
  sert encore l'ancienne classe.
- **rf-mcp fige classe ET instance de bibliothèque** au premier import du
  process. Après modification du code de `src/`, redémarrer le serveur est la
  voie nominale ; les state providers ajoutent `stale_code_warning` quand un
  module SAPFX a changé sur disque après le démarrage. Les RESOURCES déjà
  parsées restent figées elles aussi : un `import_resource` ressert la copie en
  mémoire.
- **Côté web, le bundle `__SAPFX` est versionné par son CONTENU** : une version
  neuve remplace l'ancienne au premier appel de keyword, sans recharger la
  page. C'est ce qui a fermé le symptôme
  `window.__SAPFX.<x> is not a function` après un hot-swap.
- **Une session ECC live par process** : rf-mcp ne propage pas fiablement le
  contexte dans les resources imbriquées. Le registre par alias multiplexe
  plusieurs sessions GUI DANS ce process.
- **Le mode diff des providers ne s'exerce qu'avec `page_source_filtered=true`**
  (le serveur passe `full_source=not page_source_filtered`).
- **Sous Windows, `pip install -e` échoue EN SILENCE si un serveur MCP tourne**
  (verrou sur l'exe du script console, dist-info résiduel invalide) : arrêter
  les serveurs avant toute réinstallation.
- **Le canal RFC n'est atteignable par les agents que si le serveur est lancé
  par un Python 3.10 à 3.12** (`pyrfc` n'a pas de roue au-delà).

## Hygiène de session

Préflight des connexions au début, fermeture MÊME SUR ÉCHEC à la fin
(`Close SAP`, `Close All Sap Sessions`, `Close Api Channel`,
`Close Rfc Channel`). Une connexion orpheline décale les indices et fait
saisir la mauvaise session au rattachement suivant.

## Boucle de travail recommandée

1. Percevoir (`sapfx_state`, ou `Get Screen Map` / `Get Ui5 Page Map` par
   `execute_step`).
2. Agir par `@N` ou par keyword métier, UNE étape à la fois.
3. Re-percevoir en diff, vérifier l'effet RÉEL (pas le succès rapporté).
4. Ce qui est vérifié live seulement devient une ligne de suite.

Un plan, une étape ou une réparation ne se déduisent jamais d'un passage de
documentation : l'observation live tranche.
