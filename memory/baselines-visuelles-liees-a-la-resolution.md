---
name: baselines-visuelles-liees-a-la-resolution
description: 2026-08-19, une empreinte perceptuelle encode la géométrie de capture autant que le contenu (1920x1032 contre 4676x2454 = 8 bits d'écart à contenu identique) ; mis à jour le 2026-08-20, l'outil répond désormais par `per_resolution=True` (une baseline par géométrie)
type: projet
date: 2026-08-19
---

Une empreinte perceptuelle encode la **géométrie de capture** autant que le
contenu. Les baselines committées sous `tests/robot/visual_baselines/` et les
références de la sentinelle (`screen_watch/`) ont été prises sur un poste dont
la fenêtre SAP GUI faisait 1920x1032. Rejouées sur un poste qui la rend en
4676x2454, elles échouent : distance de Hamming 8 pour un seuil de 5 sur
`snwd_pd_selection_screen`, et la sentinelle signale SE16, SE38 et SM50.

Or les écrans sont **fonctionnellement identiques** : mêmes champs, mêmes
valeurs, même titre, vérifié image contre image. Le diagnostic tient en une
observation : la dérive est **visuelle seule**, aucune dérive **structurelle**
n'est remontée (les ids sont inchangés).

**Décision du 2026-08-19 : ne pas régénérer.** Une baseline refaite sur le
second poste ferait échouer le premier ; la régénération déplace le problème,
elle ne le résout pas. C'est aussi ce qu'interdit la règle « pas de mise à jour
de baseline de confort », dont le vrai risque est de masquer une dérive future.

**Mise à jour du 2026-08-20 : le problème a une réponse dans l'outil.** Les
trois assertions snapshot (`Screen Should Match Baseline`,
`Element Should Match Baseline`, `Ui5 Screen Should Match Baseline`) acceptent
`per_resolution=True` : une baseline **par géométrie**
(`<nom>@1920x1032.png`), créée au premier passage du poste comme n'importe
quel premier passage, committée à côté des autres. À géométrie constante, la
détection de dérive est inchangée : une variante est une référence de plus,
jamais une amnistie. Une baseline `<nom>.png` déjà committée reste utilisée
tant que sa géométrie coïncide, donc rien à régénérer ni à renommer. Et sans
l'option, l'échec dont les deux géométries diffèrent le **dit** maintenant dans
son message (dérive peut-être d'échelle seule, remède nommé). Le poste de
travail est par ailleurs revenu à la géométrie de référence, donc la baseline
committée redevient valable telle quelle.

**La sentinelle de dérive suit, coupée là où c'est honnête :** une signature
d'écran ne dépend pas de la résolution, une empreinte perceptuelle si. Sous
`per_resolution=True` (activé par défaut dans le harnais de veille), le canal
structurel reste partagé et seules les références VISUELLES se déclinent par
géométrie ; un poste dont la géométrie est inconnue enregistre sa référence
visuelle et ne compare que le structurel ce passage-là. Le `.tiles.txt` portait
déjà sa géométrie dans son en-tête : c'est ce témoin qui permet de reconnaître
une référence committée comme valable ici, sans rien régénérer.

**Comment appliquer :** devant un `Screen Should Match Baseline` rouge ou une
dérive de sentinelle, comparer d'abord les DIMENSIONS du `.actual.png` à celles
de la baseline (le message d'échec le fait désormais pour les baselines). Si
elles diffèrent, c'est le poste qui a changé, pas SAP : ne rien régénérer, et
passer la suite en `per_resolution=True` si elle doit tourner sur plusieurs
postes. Si elles sont identiques, la dérive est réelle et mérite d'être lue. Le
canal structurel (signature d'écran) reste dans tous les cas le juge de la
non-régression fonctionnelle. Voir [[assertions-visuelles-masquage]] si le
sujet est une zone volatile plutôt qu'une échelle.
