---
name: parametre-de-profil-inconnu-rend-une-valeur-vide
description: 2026-08-29, TH_GET_PARAMETER ne refuse pas un paramètre inconnu, il rend RC=4 et une chaîne VIDE, donc un audit de sécurité écrit sur un nom mal orthographié est vert et affirme une absence de durcissement qu'il n'a jamais mesurée
type: projet
date: 2026-08-29
---

En montant les campagnes de configuration de sécurité contre les deux releases
ABAP du banc, la lecture d'un paramètre de profil s'est révélée être un piège de
mesure, pas une simple lecture.

`TH_GET_PARAMETER` (RFC-enabled, vérifié sur release 754 ET 758) rend deux
valeurs de sortie : `PARAMETER_VALUE` et `RC`. Pour un paramètre qu'il ne
connaît pas, il **ne lève aucune exception** : il répond `RC = 4` et une chaîne
**VIDE**. Or une chaîne vide est indiscernable d'un paramètre légitimement vide,
et la plupart des paramètres de sécurité intéressants valent justement `0`,
`OFF` ou rien.

Conséquence directe, et elle est silencieuse : un contrôle écrit sur un nom mal
orthographié, ou sur un paramètre qui n'existe pas sur la release visée, passe
au VERT en affirmant une absence de durcissement qu'il n'a jamais mesurée. Le
cas le plus traître est le contrôle « ce paramètre doit être désactivé » : la
valeur vide le satisfait, donc le rapport annonce une conformité là où il n'y a
eu aucune lecture.

**Pourquoi :** un audit de sécurité produit un document qu'on croit sur parole.
Un écart y est examiné, une conformité ne l'est jamais, donc l'erreur ne remonte
pas. C'est la forme « vert et faux » la plus coûteuse : elle ne se manifeste pas
au moment où elle est commise, mais le jour où quelqu'un s'appuie sur le rapport.

**Comment appliquer :** juger sur le code de retour AVANT la valeur, et ne
jamais laisser une mesure absente prendre la forme d'une valeur. Trois règles
encodées dans la bibliothèque et éprouvées par la contre-épreuve :

1. un code de retour non nul rend `unknown` avec une valeur `None`, jamais une
   chaîne vide ;
2. « non mesuré » reste distinct de « non conforme » : les deux se signalent,
   mais ils ne se corrigent pas au même endroit (corriger le contrôle contre
   corriger le système), et un contrôle non mesurable n'est JAMAIS compté comme
   un succès, sur le patron du repli sûr déjà appliqué aux statuts IDoc et aux
   verdicts d'attente de job ;
3. une campagne pose en tête une garde qui exige que TOUS les paramètres
   contrôlés soient reconnus par la cible, ce qui sépare une différence de
   vocabulaire entre releases d'une différence de posture.

Deux constats de la même passe, utiles à qui reprendra le sujet. Un comparateur
numérique appliqué à une valeur qui n'en est pas (`system/secure_communication`
vaut `OFF`) est un défaut du CONTRÔLE et non une non-conformité du système : il
doit lever une erreur qui nomme le contrôle, pas fabriquer un verdict. Et un
masque de verrouillage d'utilisateur se lit en BITS et non en énumération : un
compte verrouillé à la fois par l'administration et par des échecs de connexion
porte une valeur qu'une table de correspondance plate déclarerait inconnue.

Voir [[rfc-champ-inexistant-accuse-la-table]] pour le piège voisin sur la
lecture de tables, où c'est le code d'erreur qui désigne la mauvaise cause.
