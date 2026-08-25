# Une campagne validée sur une seule release ne peut pas voir ses hypothèses

Relevé le 2026-08-24, en portant sur une seconde release (SAPUI5 1.120) une
campagne d'exploration de launchpad Fiori ABAP validée 19/19 sur la première
(SAPUI5 1.71), avec le même page object partagé.

La suite d'origine était juste, complète et verte. Elle portait pourtant six
hypothèses invisibles, qui ne se sont manifestées qu'au contact de l'autre
release :

- **L'ancre de la zone utilisateur change de nom ET de type de contrôle** :
  d'un `ShellHeadItem` à un `sap.m.Avatar`, avec son popover renommé. Un
  localisateur qui ne cible que le nom rate déjà ; un keyword qui suppose le
  type rate encore après correction du nom.
- **La position d'acquittement d'un dialogue n'est pas une constante.** Le
  dialogue de refus de navigation gagne un bouton en tête sur la release
  récente : acquitter en position 0 **copie le message et laisse le dialogue
  ouvert**, alors que la confirmation de déconnexion répond toujours en
  position 0. L'échec arrive au bout du délai d'attente, sur un dialogue qu'on
  croit fermé, donc loin de sa cause.
- **Une sonde de lecture appliquée à la mauvaise release rend du vide sans
  échouer** : le contexte de liaison d'une tuile ne porte plus la cible, et la
  sonde retournait titre et intent vides. Cinq scénarios seraient passés au
  vert sur du vide. C'est le pire des cas, et le seul qui ne se signale pas
  tout seul.
- **Un seuil numérique gravé rend la suite rouge sur l'autre système** :
  plancher de contrôles de l'accueil, nombre d'éléments de barre shell, nombre
  de tuiles. Tous mesurés, tous différents, aucun anormal.
- **Un budget d'attente par défaut est une hypothèse comme une autre** : la
  même navigation arrière demande près de quatre fois le budget qui suffisait
  ailleurs.
- **Un contrôle peut disparaître entre deux releases**, ce qui fait disparaître
  aussi le piège qu'il portait : inutile de coder la parade des deux côtés.

**Ce qui se confirme identique est un résultat, pas un non-événement** :
l'architecture, la volumétrie du catalogue, les suffixes d'action. C'est ce qui
autorise à graver, et cette autorisation-là ne s'obtient qu'en mesurant deux
fois.

**Comment on l'encode** : ce qui diverge devient une **variable** de la couche
partagée, ou une **stratégie nommée** (le nom du mot-clé qui sait lire ou
fermer), jamais un `IF` sur la version. Ajouter une release ajoute alors un
mot-clé, pas une branche, et la couche ne se met pas à raisonner sur des
numéros de version. Et une sonde qui ne trouve rien **échoue en nommant la
sonde en cause** : c'est ce qui transforme la panne silencieuse en diagnostic.

**Comment on le vérifie** : la porte de sortie n'est pas le run de la nouvelle
suite, c'est le **rejeu live de l'ancienne** derrière lui. Le page object est
partagé, donc la campagne d'origine est ce que la nouvelle risque de casser.

Voir [[lire-la-propriete-plutot-que-le-rendu]] (même famille : ce qu'on croit
lire n'est pas ce que le contrôle porte) et
[[diese-en-tete-de-cellule-robot-est-un-commentaire]] (même signature
d'échec : une valeur vide qui ressemble à une dérive de localisateur).
