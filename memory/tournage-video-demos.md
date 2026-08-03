---
name: tournage-video-demos
description: Leçons de captation écran pour les vidéos de démo/présentation (gdigrab, fenêtres GPU, accélération) — payées en prises ratées le 2026-08-02
type: projet
date: 2026-08-02
---

Leçons apprises en produisant la vidéo de présentation
(`comms/video-presentation.md`, sources dans `comms/visuels/presentation/`),
chacune constatée sur une prise ratée avant d'être corrigée.

**Une fenêtre rendue par GPU (VS Code, navigateurs, Electron) sort NOIRE en
`gdigrab` par titre** (`-i title=...` fait un BitBlt du DC de la fenêtre) :
capturer une **région du bureau** à la place (`-i desktop -offset_x/-offset_y
-video_size`), la fenêtre poussée topmost pendant la prise. SAP GUI (GDI
classique) supporte les deux voies.

**Le rectangle utile d'une fenêtre n'est pas `GetWindowRect`** : bords DWM
invisibles et fenêtres d'arrière-plan qui dépassent entrent dans le cadre.
`DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS)` aide, mais des liserés
survivent — le plus robuste est un recadrage de quelques pixels au montage,
masqué par un cadre décoratif (fond navy) qui uniformise au passage.

**Arrêter ffmpeg par `terminate()` jette le tampon** : ~10 s de fin de prise
perdues sur un conteneur mkv (vécu : 26 s livrées pour 36 s tournées).
Toujours arrêter par « `q` » écrit sur stdin (`stdin=PIPE`), puis `wait()`.

**Avec un changement de vitesse (`setpts`), borner l'ENTRÉE, jamais la
sortie** : `-t` placé après `-i` (option de sortie) se mesure sur la durée
accélérée et rallonge le plan avec la suite de la prise — c'est par là qu'une
fin de capture montrant le bureau (fuite d'écran) est revenue dans un premier
montage. `-ss/-t` avant `-i`, et le fondu de sortie se calcule sur
`(fin - début) / vitesse`.

**`zoompan` crantèle les zooms lents, même suréchantillonné** : ses
recadrages avancent par pas entiers — un Ken Burns « propre » en ffmpeg pur
n'existe pas à basse vitesse. Et le screencast `recordVideo` de
Playwright ne tient pas non plus une cadence stable (frames sur changement,
pas d'horloge fixe) : un zoom lent y vacille aussi. La voie fiable, en deux
temps : animations CSS mises en PAUSE et horloge posée frame par frame
(`document.getAnimations()` + `currentTime = n/30`), un screenshot par
frame — rendu déterministe — puis ffmpeg assemble la séquence et CLONE la
dernière frame (`tpad`) pour la durée du plan. Un mouvement lent continu ne
vaut jamais le coût : préférer une entrée animée courte puis un plan
parfaitement figé, habillé par les incrustations ASS (déterministes).

**Toute prise « région du bureau » filme ce qui passe** : couper au montage
tout ce qui suit la fermeture de la fenêtre filmée (le bureau réel apparaît),
et relire les dernières secondes image par image avant livraison.

Voir aussi les deux suites de démo vidéo historiques
(`tools/recorder/demo/`, `tools/recorder_web/demo/`) : mesure du décalage
sous-titres/film et pièges Playwright `recordVideo` y sont déjà documentés.
