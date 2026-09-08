---
name: perception-vide-en-pass-sous-rf-mcp-cross-thread
description: 2026-09-07, sous rf-mcp les keywords de bibliothèque, `execute_batch` et `Evaluate` peuvent s'exécuter sur des threads différents du thread COM propriétaire ; la bibliothèque rend alors des perceptions VIDES en PASS (`# screen ?`, `[]`), « still busy » sur un écran au repos, et une AttributeError COM verrouille le chemin GetObjectTree ; remède de session `use_context=true`, remède de bibliothèque à écrire
metadata:
  type: project
---

Pendant une exploration ECC pilotée par rf-mcp (A4H, SAP GUI 8.00), une session
ouverte par `execute_step` a cessé de répondre après un `execute_batch` : la
suite `Click Element` puis `Wait Until Busy Done` a rendu « SAP session was
still busy after 30 seconds » alors que la capture d'écran montrait un écran
au repos ; `Get Screen Signature` a rendu `# screen ?` sans une seule ligne
d'élément, en PASS ; `Get Open Windows` a rendu `[]`, en PASS ; `Element
Should Be Present    wnd[0]` a échoué ; et `Read Field By Label` a perdu la
géométrie en accusant un `GetObjectTree` « absent ». La cause, mesurée par
`threading.get_ident()` : les steps de batch et les `Evaluate` s'exécutaient
sur un autre thread que celui qui avait lié la session COM (STA), et l'accès
sortait en `com_error` RPC_E_WRONG_THREAD (hresult -2147417842) ou en
`AttributeError: <unknown>.Info`.

**Pourquoi :** quatre couches défensives de la bibliothèque transforment cette
panne de transport en résultats plausibles. `wait_until_busy_done` avale toute
exception de la sonde `session.Busy` et la lit comme « occupé » ;
`_screen_elements` rend une liste vide et `_screen_header` un `# screen ?`
quand la session est illisible (documenté comme « défensif ») ;
`get_open_windows` rend une liste vide ; et `_screen_elements` interprète une
`AttributeError` comme « API GetObjectTree absente de cette version » et la
mémorise sur l'instance, alors qu'un proxy COM sur le mauvais thread lève
exactement cette exception. Le rail STA de `_touch_com_thread` ne fait qu'un
`CoInitialize` défensif : il n'effectue aucun marshaling et ne ré-attache pas
la session, donc il ne protège de rien dans ce cas. C'est la famille
[[lecture-vide-ou-illisible-indiscernables]] appliquée à la perception elle-même,
la pire place possible : un agent qui reçoit `[]` conclut « aucune fenêtre
ouverte » et agit sur cette base.

**Comment appliquer :** en session rf-mcp, passer `use_context=true` sur
chaque `execute_step` de keyword SapEccLibrary (vérifié : la pile de fenêtres
revient), ne jamais utiliser `execute_batch` pour du COM, ne jamais toucher
un objet COM depuis `Evaluate`, et devant un `# screen ?` ré-attacher par
`Attach To Open Session    0    0`. Côté bibliothèque, la correction (à faire,
tests unitaires avec une session factice levant RPC_E_WRONG_THREAD) tient en
quatre gestes : une perception qui ne peut pas lire ÉCHOUE en nommant la
cause ; le message de `Wait Until Busy Done` porte la dernière exception de
sonde ; la latche `GetObjectTree` ne se ferme que sur une vraie absence d'API
(jamais depuis un thread étranger) ; et le rail STA ré-attache la session par
index de connexion et de session quand un thread étranger l'accède. Le
registre de capacités `tests/robot/ui/ecc/reconnaissance_couverture_sapgui.robot`
ne peut pas reproduire ce cas (un run `robot` est mono-thread) : c'est un test
unitaire qui doit le verrouiller.

**Corrigé le soir même (2026-09-07)** : les quatre gestes sont dans `src/`
(`ScreenUnreadableError` nommant la cause et le remède, message de
`Wait Until Busy Done` porteur de l'exception, latche protégée par
`is_wrong_thread_error`, rail STA qui ré-attache par thread via la ROT et
`FindById` de l'id de session, verrouillés par `tests/unit/test_perception_unreadable.py`,
`test_wait_busy_cause.py`, `test_sta_reattach.py`). Le ré-attachement a été
mesuré par une sonde en thread étranger jouée par `robot`, PUIS à travers
rf-mcp lui-même le même soir, sans redémarrer le serveur (bibliothèque
rechargée par `importlib`, instance hot-swappée, `Attach To Open Session 0 0`
en contexte pour que le setter mémorise l'id de session) : `Get Open Windows`
hors contexte et un `execute_batch` sur un thread étranger ont rendu la pile
réelle et une signature de 165 lignes, là où le matin ils rendaient `[]` et
`# screen ?`. `use_context=true` reste la consigne de session : sans coût, et
seule protection d'un serveur qui n'a pas encore rechargé la bibliothèque.
