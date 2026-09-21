# Piloter les recorders depuis un test : quatre pièges qui ressemblent à des pannes

Date : 2026-08-25, en validant les deux recorders EN LIVE (bureau contre un
système ECC réel, web contre une application Fiori Elements réelle). Les deux
fonctionnent ; les quatre échecs rencontrés venaient tous du HARNAIS, et chacun
ressemblait à s'y méprendre à un défaut produit. À relire avant d'écrire un test
qui automatise un outil interactif.

1. **Un recorder lancé en sous-processus écrit dans un TUBE, donc en mode bloc.**
   Attendre sa ligne « prêt » sur sa sortie standard bloque indéfiniment : le
   texte est dans son tampon, pas sur le tube. Le lancer avec l'option
   d'exécution non tamponnée de Python (`-u`). Symptôme trompeur : le fichier de
   sortie existe, vide, et rien ne bouge, ce qui fait croire à un blocage COM.

2. **Côté web, une saisie n'est transcrite qu'à la PERTE DE FOCUS.** C'est
   l'événement `change` qui la porte, comme pour un utilisateur qui tabule ou
   clique le bouton de recherche. Un remplissage scripté suivi d'une simple
   validation clavier n'enregistre donc que la touche, et l'on conclut à tort
   que la saisie n'est pas captée. Piloter comme un humain : frappe, puis
   tabulation ou clic sur le bouton suivant. Le step correct porte alors le
   localisateur de CONTRÔLE (`idSuffix=fe::…`) et son indice `# xpath:`, pas un
   identifiant de DOM généré.

3. **Après un export, le bouton du panneau porte quelques secondes le libellé du
   retour visuel** (« copied ») au lieu de son libellé normal. Un test qui
   cherche le libellé exact conclut que le panneau est cassé. Attendre le retour
   du libellé avant l'export suivant.

4. **La paire resource-first espace ses DEUX téléchargements de 350 ms**
   (contournement de la protection « téléchargements multiples » du navigateur).
   Deux attentes armées avant le clic captent toutes les deux le PREMIER
   fichier, et l'on croit à un export dupliqué : armer la seconde APRÈS
   l'arrivée du premier.

**Complété le 2026-09-12**, en refaisant l'exercice de bout en bout (bureau
contre A4H, web contre la même application Fiori Elements). Deux pièges de
plus, propres au recorder BUREAU, et tous deux invisibles hors usage réel :

- **Cinquième piège : `--screenshots` bascule le moteur `auto` en polling.**
  La capture d'écran est un concept du diff de signature, donc le drapeau
  privilégie ce moteur, ce que l'aide de l'option ne dit pas. On croit
  enregistrer avec les événements de l'API et on obtient le repli, avec sa
  qualité de transcription. Pour un enregistrement scripté, exiger
  `--engine native`.

- **Sixième piège : le polling ne transcrit presque rien d'un parcours joué à
  VITESSE MACHINE.** Il sonde toutes les 0,4 s : la saisie et sa validation
  tombent entre deux sondages, et il n'émet qu'une soumission nue là où le
  natif rend les cinq étapes exactes (transaction, saisie, Entrée, bouton,
  F12). Ce n'est pas un défaut, c'est sa conception : il vise un rythme
  humain et sert de repli quand les événements de l'API manquent. Un test qui
  juge la qualité de transcription doit donc nommer le moteur qu'il mesure.

Les points 2 et 4 ci-dessus ont été repayés ce jour-là faute d'avoir relu
cette fiche avant de construire le harnais : l'attente d'un seul
téléchargement pour l'export resource-first a décalé les fichiers suivants
d'un cran, et le diagnostic a coûté un run entier.

Rappel connexe, payé une fois de plus ici : la bibliothèque Browser referme les
pages ouvertes DANS un test, donc la page d'un tel harnais s'ouvre en
`Suite Setup` (voir [[une-seule-release-ne-montre-pas-ses-hypotheses]] pour la
même discipline appliquée aux campagnes) ; et un jeton commençant par un dièse
reste un commentaire dans une assertion, ce que
[[diese-en-tete-de-cellule-robot-est-un-commentaire]] documente déjà.
