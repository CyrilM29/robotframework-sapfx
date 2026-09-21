# Extraire un tableau SAP n'est pas l'asserter

**Date** : 2026-09-15. **Cible** : rapport RSPARAM (« Display Profile
Parameter ») d'un système ABAP Platform 2023, release 758.

## Le fait

Le premier jet d'une extraction du rapport vers un fichier a rendu **3 des 5
colonnes** de la grille, nommées par leurs **identifiants techniques**
(`NAME`, `USER_VALUE`, `DEFAULT_VALUE`). Le fichier était juste, complet sur
ce qu'il montrait, et inutilisable : il ne ressemblait pas à l'écran dont il
venait.

La cause n'est pas une étourderie, c'est une confusion de but. Les trois
colonnes retenues étaient celles qu'un **contrôle de posture de sécurité**
consomme, et la lecture avait été reprise telle quelle. Or les deux gestes
n'ont pas le même contrat :

| | Asserter (un contrôle) | Extraire (une restitution) |
|---|---|---|
| Colonnes | restreintes à ce qu'on juge, pour épargner des appels COM | **toutes celles de la grille** |
| Noms | identifiants **techniques**, seuls indépendants de la langue (convention 3) | **titres affichés**, les seuls qu'un lecteur reconnaît |
| Critère | le verdict | la fidélité à l'écran |

Mesuré sur la cible : la grille porte `NAME`, `USER_VALUE`, `DEFAULT_VALUE`,
`DEFAULT_USUBS_VALUE` (forme non substituée) et `DESCR` (commentaire). Les
deux dernières ne servent à aucun contrôle et manquaient cruellement à une
extraction.

## Ce qu'on en a fait

- Les colonnes d'une extraction sont **lues sur la grille**, jamais gravées
  dans la suite : une release qui en ajoute une la rend d'office.
- Les deux noms coexistent, chacun à sa place : les identifiants techniques
  restent les **clés de lecture**, les titres affichés deviennent
  l'**en-tête du fichier livré**. D'où le keyword de bibliothèque qui rend la
  carte `{id technique: titre affiché}`, et l'argument `headers=` des
  écrivains.
- Un libellé **dupliqué** (une grille peut en afficher) est toléré là où
  l'en-tête est décoratif et **refusé** là où il devient une clé (JSON,
  Parquet) : une colonne y disparaîtrait d'un fichier d'apparence complète.

## Pourquoi c'est à retenir

Le défaut n'était visible ni d'un test ni d'un garde : le fichier existait,
son contenu correspondait au relevé, tous les scénarios étaient verts. Seul un
lecteur humain confrontant le fichier à l'écran pouvait le voir. Quand une
lecture écrite pour JUGER est réemployée pour RESTITUER, vérifier ce qu'elle
laisse de côté fait partie du travail.

Voir aussi [[colonne-de-profil-tronquee-a-60-caracteres]] (l'autre piège de ce
rapport : une colonne coupée en silence par SAP lui-même).
