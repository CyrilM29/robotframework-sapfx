---
name: rfc-champ-inexistant-accuse-la-table
description: 2026-08-27, un champ inconnu demandé à RFC_READ_TABLE sort en TABLE_WITHOUT_DATA, code qui accuse la table d'être vide alors qu'elle est pleine et que le fautif est un nom de champ ; et deux causes d'échec d'ouverture de session partagent un seul code
type: projet
date: 2026-08-27
---

En sondant le canal RFC contre une ABAP Platform trial, `RFC_READ_TABLE` a
refusé une lecture avec le code technique **`TABLE_WITHOUT_DATA`** et le
message `ID:AD Type:E Number:718 DD03L`. Le code désigne la TABLE. Or la table
était pleine : le fautif était un **nom de champ** demandé dans `FIELDS` et
absent de la table sur cette release.

Vérifié trois fois, sur trois formes différentes : un champ inventé sur une
table de 18 lignes, un champ unique réellement absent du dictionnaire, et une
liste de 19 champs dont 2 n'existaient pas. Contre-épreuve faite dans l'autre
sens : les 31 champs RÉELS de la même table, lus d'un coup, passent tous. Ce
n'est donc ni le nombre de champs ni la largeur de ligne.

**Pourquoi :** le message envoie chercher un problème de DONNÉES (« table sans
données ») là où il y a une faute de frappe ou une hypothèse de release. La
piste coûteuse est de vérifier le contenu de la table, ses autorisations, son
mandant, avant de soupçonner la liste de champs. Une première hypothèse de
dépassement de la limite de largeur de ligne, plausible et classique, a été
formulée puis écartée par la mesure : la somme des largeurs déclarées ne
faisait que 310 caractères.

**Comment appliquer :** devant un `TABLE_WITHOUT_DATA`, suspecter d'abord la
liste de champs, et la valider contre le dictionnaire (`DD03L`) sur LA cible
plutôt que contre une mémoire de sa structure : les champs d'une table
standard varient d'une release à l'autre. Corollaire pour les campagnes, une
lecture RFC restreinte à des champs relevés live est portable, une liste
écrite de mémoire ne l'est pas.

Second enseignement de la même passe, de même nature : **un mot de passe faux
et un mandant inexistant rendent tous deux `RFC_LOGON_FAILURE`**, seul le
texte les sépare. Un test ne peut donc affirmer qu'un refus d'ouverture de
session, jamais sa cause. Le refus de niveau réseau, lui, se distingue
franchement (`RFC_COMMUNICATION_FAILURE`), comme les refus applicatifs
(`TABLE_NOT_AVAILABLE` pour une table absente, `FU_NOT_FOUND` pour un module
absent, `RFC_INVALID_PARAMETER` pour un paramètre inconnu, celui-ci levé côté
client sans atteindre le serveur).

Voir aussi [[sap-gui-fournit-le-runtime-rfc]] pour le provisionnement du canal.
