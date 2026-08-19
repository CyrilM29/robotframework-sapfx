# Arrêter un recorder de l'extérieur : sentinelle, jamais `terminate()`

**2026-08-19, revue de code de `tools/`.** Le lanceur visuel du recorder bureau
lance le recorder dans une console SÉPARÉE. Il n'a donc aucune console à qui
envoyer un Ctrl+C, et son bouton « Arrêter » appelait `terminate()` :
`TerminateProcess` sous Windows, donc le bloc `finally` de la boucle ne tourne
jamais.

Ce que ce teardown fait, et que l'arrêt brutal perdait :

- l'OK-code resté en attente est écrit (`flush_native_state` : une transaction
  saisie dont l'Entrée n'a pas encore été observée) ;
- `Session.Record` est remis à `False` **côté SAP GUI**. Le mode record est un
  état du client SAP, pas du processus qui l'a armé : laissé actif, il rend le
  F4 modal et désactive le drag & drop pour l'utilisateur ;
- les événements COM sont désabonnés, le fichier refermé.

Correctif retenu : une **sentinelle fichier** (`--stop-file`), sondée par les
boucles interactives au rythme où elles tournent déjà. Le processus sort de sa
boucle par son propre chemin, teardown compris, et le lanceur ne tue le
processus que si la sentinelle reste sans réponse (cinq secondes).

Pourquoi pas un signal : `GenerateConsoleCtrlEvent` n'atteint que les processus
de la console de l'appelant, et le lanceur (lancé par `pythonw`) n'en a pas ;
un enfant créé avec `CREATE_NEW_CONSOLE` a de toute façon la sienne. La
sentinelle marche quels que soient le lanceur, la console et le poste.

**Règle à retenir** : dès qu'un processus détient un état EXTERNE à lui
(mode record d'un client, verrou, session ouverte), l'arrêter revient à lui
demander de s'arrêter, jamais à le tuer. Voisine de la field note « fermer
toute session ouverte, même sur échec » et de
[[replay-recorder-vert-et-faux]].
