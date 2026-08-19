# Un garde qui relaie une sortie doit forcer UTF-8 sur stdout ET stderr

**2026-08-19, revue de code de `scripts/` et de ses dépendances.** Sous
Windows, Python ouvre les flux standard dans l'encodage du poste (cp1252 ici),
et les deux flux ne se comportent PAS pareil :

- `stdout` est en erreurs **strictes** : imprimer « ↔ » ou « → » lève
  `UnicodeEncodeError` et tue le processus ;
- `stderr` est en `backslashreplace` : pas de plantage, mais le message part
  en mojibake, avec `→` à la place du caractère.

Les deux cas étaient réunis dans le hook post-édition. Sa branche
INFORMATIVE (dérive plan/suite) portait une flèche dans son propre
`systemMessage` : la seule branche conçue pour ne pas bloquer était donc la
seule à mourir, en traceback. Et le rapport qu'il relaie d'un garde enfant
arrivait abîmé : le garde émettait pourtant de l'UTF-8 propre, c'est le
ré-encodage à la sortie du hook qui le cassait, y compris le caractère à
corriger.

Reproduit avant correction, octets réels : `[check_no_em_dash] \xc9CHEC` puis
`titre \x97 sous-titre fleche → fin`.

**La leçon générale** : ce n'est pas une affaire d'affichage. Un garde est lu
par des machines (CI, hook, agent) autant que par un humain, donc son
encodage de sortie fait partie de son contrat. Quatre gardes du dépôt
forçaient leur `stdout`, dix non : les logs mélangeaient deux encodages. La
bascule vit désormais dans `scripts/_common.py` et couvre les deux flux.

**Deux corollaires appris en corrigeant** :

- le script qui RELAIE la sortie d'un sous-processus doit lui imposer un
  `encoding` explicite à la lecture, sinon il redécode dans l'encodage du
  poste ce que l'enfant a écrit en UTF-8 ;
- mutualiser n'est pas toujours possible : les deux scripts EMBARQUÉS dans le
  pack Windows doivent tourner seuls depuis sa racine, sans voisin. Ils
  gardent une copie assumée de ces quatre lignes, et un test refuse tout
  import d'un module de `scripts/` dans un script embarqué : la propriété
  « autonome » est plus précieuse que l'absence de duplication.

Voisines : [[replay-recorder-vert-et-faux]] (un outil ne doit jamais être vert
sans avoir rien fait) et [[robot-if-texte-sap-apostrophe]] pour la famille des
pièges de caractères venus du système.
