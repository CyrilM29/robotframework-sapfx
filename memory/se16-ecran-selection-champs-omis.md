---
name: se16-ecran-selection-champs-omis
description: L'écran de sélection SE16 n'expose pas tous les champs de la table (champ client et champs FLTP retirés en silence, tables larges soumises à un choix persistant) : DD03L est la seule source du vrai ordre des champs
type: projet
date: 2026-08-17
---

L'écran de sélection généré par SE16 n'est **pas** la liste des champs de la
table. Trois retraits constatés live sur A4H (SAP GUI 8.00, client 001) :

- le **champ client** (`DATATYPE` = `CLNT`, typiquement `MANDT`) n'apparaît
  jamais ;
- les champs **`FLTP`** sont retirés **sans aucun message de statut** : sur
  `SAPLANE`, DD03L donne 18 champs et l'écran n'expose que 14 critères, les
  absents étant `MANDT` plus `CONSUM`, `SPAN` et `LENG`, tous `FLTP` ;
- au-delà d'environ 40 champs, SE16 ouvre le dialogue « choix des champs de
  sélection » et le choix **persiste par utilisateur** : sur `DD02L` (50
  champs), l'écran ne proposait plus que les trois champs clés `TABNAME`,
  `AS4LOCAL`, `AS4VERS`. Un champ non clé comme `TABCLASS` n'est alors pas
  filtrable, alors qu'il reste présent **en sortie** de grille.

La règle d'indexation qui en découle, vérifiée sur `SAPLANE` : `I<n>` est le
n-ième champ de la table triée par `DD03L-POSITION`, une fois retirés le champ
client et les champs `FLTP`.

**Pourquoi :** les dictionnaires `<TABLE>_SELECTION_FIELDS` de
`resources/ecc_keywords.resource` associent un champ technique à un
localisateur positionnel `I<n>-LOW`. Déduire ces positions de l'ordre des champs
de la table donne un mapping **faux** dès qu'un champ client ou un champ `FLTP`
existe, et le décalage est silencieux : le test saisit son critère dans le
mauvais champ et ne remonte aucune erreur. Corollaire utile : un objet dont un
champ `FLTP` déclenche parfois un dialogue d'avertissement n'est pas pour autant
non consultable. `SAPLANE`, longtemps soupçonné de bloquer une campagne,
s'ouvre normalement et se compte (34 entrées le 2026-08-17), sans modale ni
message.

**Comment appliquer :** avant d'ajouter un dictionnaire de sélection pour une
nouvelle table, relever l'écran réel avec `Get Screen Signature` en
`mode=semantic` (une ligne par critère, libellé vérifié) plutôt que raisonner
sur la structure. Pour un mapping industrialisable, lire `DD03L` filtré sur la
table (`FIELDNAME`, `POSITION`, `DATATYPE`) et retirer `CLNT` et `FLTP`. Ne
jamais déduire la structure d'une table de son écran de sélection : voir aussi
[[a4h-se16-write-delete]] et [[se16-selection-multiple-liste-noms]].
