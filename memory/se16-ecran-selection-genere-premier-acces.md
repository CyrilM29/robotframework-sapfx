---
name: se16-ecran-selection-genere-premier-acces
description: SE16 génère l'écran de sélection d'une table au premier accès (/1BCDWB/DB<table>, ~1 s) : la fin du busy ne garantit pas l'écran, et la génération peut émettre un dialogue modal d'information (FLTP) au lieu d'un statut type E
type: projet
date: 2026-08-17
---

L'écran de sélection SE16 d'une table n'existe pas d'avance : c'est un
programme **généré au premier accès** (`/1BCDWB/DB<table>`). Après une
re-création du conteneur (2026-08-01), toute la génération est à refaire, et
un balayage de catalogue rencontre le phénomène en série. Deux symptômes
constatés live le 2026-08-17 (A4H, SAP GUI 8.00, client 001) :

- **La génération est lente et asynchrone du point de vue du script** :
  l'Entrée sur le nom de table prend ~1 s au lieu de ~0,1 s, et « busy
  terminé » ne signifie pas « écran affiché ». Sur `SAPLANE`, un clic sur
  « Number of Entries » 90 ms après la fin du busy échouait en
  « Cannot find element » sur deux runs consécutifs, alors que le même
  enchaînement avec une attente de l'écran (`txtMAX_SEL` présent) passe.
- **La génération peut émettre un dialogue modal d'information** (programme
  `SAPMSDYP`, lignes `wnd[1]/usr/txtMESSTXT<n>`) au lieu d'un message de
  barre de statut : sur `SGEOCITY` (champs `FLTP`), « ABAP Dictionary type
  FLTP is not allowed for dynpro element ». Le dialogue est bénin : Entrée le
  referme, l'écran de sélection est derrière (62 entrées comptées ensuite).
  Il n'apparaît qu'à la génération : le second accès n'en émet plus, ce qui
  rend le symptôme non reproductible une fois l'écran généré.

**Pourquoi :** un scénario qui enchaîne « statut pas de type E, donc je
clique » tient tant que les écrans sont déjà générés, puis casse en boucle
sur système frais : le contrôle du type de statut ne voit rien (barre vide),
le modal masque `btn[31]` et `txtMAX_SEL`, et l'échec (« Cannot find
element ») ressemble à un localisateur périmé alors que l'écran n'est
simplement pas celui qu'on croit. C'est la 3e cause du diagnostic d'absence
(écran réel différent), la plus fréquente en ECC.

**Comment appliquer :** après l'Entrée sur un nom de table, contrôler la
**pile de fenêtres**, pas seulement la barre de statut : refermer un
dialogue de message détecté **structurellement** (fenêtre modale + champ
`txtMESSTXT1`, texte relevé pour le journal seulement, jamais en assertion),
puis **attendre l'écran de sélection** (`txtMAX_SEL`) avant toute action.
**Correction du 2026-08-18 (revue de code).** Cette fiche affirmait que la
réparation était « encodée dans `Try Open Table Selection Screen` » : c'était
FAUX au moment où elle a été écrite (ce keyword n'avait ni détection
`MESSTXT` ni journalisation), et la logique existait en TROIS copies
divergentes (resource, mixin DDIC, suite autonome). Elle vit désormais dans
UN seul keyword de bibliothèque, `Reach Se16 Selection Screen`, qui retourne
un verdict structuré (`reached` / `rejected` / `dialog` / `modal`) ; la
resource (`Try Open Table Selection Screen`, `Reach Table Selection Screen`)
et les campagnes y délèguent.

Deux corollaires appris en corrigeant :

- un verdict `dialog` doit être **borné** par le balayage, pas seulement
  journalisé : sinon une régression qui se manifeste en dialogue bloquant
  glisse du compte « tables réelles » vers le seau `dialog` et la suite reste
  verte (`${MAX_DIALOG_REJECTS}`, 0 sur la référence live) ;
- ne JAMAIS interpoler le texte d'un dialogue SAP dans une condition Robot
  entre apostrophes (`IF '${dialog}' != '${EMPTY}'`) : voir
  [[robot-if-texte-sap-apostrophe]].

Un objet qui déclenche ce dialogue n'est pas non consultable : voir le
corollaire de [[se16-ecran-selection-champs-omis]] (champs FLTP retirés en
silence) et [[a4h-se16-write-delete]] pour les autres pièges SE16.
