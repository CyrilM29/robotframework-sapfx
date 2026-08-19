---
name: baselines-visuelles-liees-a-la-resolution
description: 2026-08-19, les baselines visuelles ECC committées divergent dès que la fenêtre SAP GUI est rendue à une autre résolution (1920x1032 contre 4676x2454), à contenu strictement identique ; DÉCISION prise, ne pas les régénérer
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

**Décision (Cyril, 2026-08-19) : on ne régénère pas.** Une baseline refaite ici
ferait échouer l'autre poste ; le problème n'a pas de bonne réponse par la
régénération, seulement par le choix du poste de référence.

**Pourquoi :** le réflexe naturel devant un rouge est de rafraîchir la
référence, et c'est exactement ce que la règle « pas de mise à jour de baseline
de confort » interdit. Ici ce réflexe serait doublement mauvais : il masquerait
une vraie dérive future, et il déplacerait simplement l'échec sur un autre
poste. À noter, aucune conséquence de portée : ces suites ne tournent dans
AUCUN workflow de CI, donc l'écart ne bloque ni la CI ni une release.

**Comment appliquer :** devant un `Screen Should Match Baseline` rouge ou une
dérive de sentinelle, comparer d'abord les DIMENSIONS du `.actual.png` à celles
de la baseline. Si elles diffèrent, c'est le poste qui a changé, pas SAP :
ne rien régénérer, et ne pas re-signaler le constat comme une régression. Si
elles sont identiques, alors la dérive est réelle et mérite d'être lue. Le
canal structurel (signature d'écran) reste dans tous les cas le juge de la
non-régression fonctionnelle. Voir [[assertions-visuelles-masquage]] si le
sujet est une zone volatile plutôt qu'une échelle.
