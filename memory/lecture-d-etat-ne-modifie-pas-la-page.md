# Une lecture d'état ne doit ni modifier la page, ni crier au loup

**2026-08-19, revue de code de `integrations/`.** L'état applicatif Fiori servi
aux agents appelait `Get Ui5 Messages` sans condition. Deux conséquences, l'une
fonctionnelle, l'autre plus insidieuse.

**1. Une cible supportée était signalée comme une panne.** Ce keyword échoue
durement hors runtime UI5, or les pages UI5 Web Components (moteur `wc`), le
WebGUI classique (`sid`) et les zones non-SAP d'une page hybride (`dom`) sont
des cibles LÉGITIMES de la bibliothèque. Chaque tour d'agent y produisait donc
une erreur de collecte permanente, dont le texte orientait en plus vers une
fausse piste. Un signal d'erreur qui se déclenche en fonctionnement normal
n'est plus lu : la correction sépare deux clés, « une section a ÉCHOUÉ » et
« une section n'a pas de sens ici ».

**2. Une simple observation instrumentait l'application testée.** Toutes les
expressions web du dépôt sont bâties par le même assembleur, qui **(ré)installe
le bundle injecté** avant d'appeler sa méthode. Le bundle enveloppe
`window.fetch` et `XMLHttpRequest.prototype.send` (l'instrumentation d'attente
réseau) et accroche les toasts. C'est voulu quand on PILOTE ; ça ne l'est pas
quand un state provider, appelé après chaque étape, se contente de REGARDER :
sur une application qui enveloppe elle-même `fetch` (intercepteur OData, agent
de supervision), l'ordre d'enveloppement diffère alors entre un run piloté par
l'agent et un run ordinaire.

D'où une sonde dédiée, `Ui5 Runtime Is Present` : elle répond `True`/`False`
sans jamais échouer et c'est la seule expression web du dépôt qui n'injecte
rien. Vérifiée en vrai navigateur le jour même : `False` sur la fixture Web
Components (et `window.__SAPFX` toujours absent après l'appel, alors qu'un
keyword ordinaire l'installe bien), `True` sur une application UI5 réelle.

**Le prix, assumé :** un aller-retour de plus sur une page UI5, un de moins
ailleurs. Une perception qui ment coûte plus cher qu'une perception qui sonde.

**Comment appliquer :** avant d'ajouter une section à un état servi
automatiquement, se demander (a) ce qu'elle vaut sur les familles de pages où
elle n'a pas de sens, et (b) ce qu'elle MODIFIE dans le système observé. Les
deux réponses appartiennent à la conception de la section, pas à son débogage.
Voir aussi [[gardes-qui-ne-peuvent-pas-echouer]].
