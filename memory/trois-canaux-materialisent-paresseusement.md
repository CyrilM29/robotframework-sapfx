# Les quatre canaux matérialisent leur tableau paresseusement, et trois ne laissent aucune trace

**Relevé le 2026-09-15**, en portant l'extraction d'un tableau vers cinq
formats du canal écran vers les deux canaux web. **Étendu au canal RFC le
2026-09-16**, qui s'est révélé le cas limite.

## Le fait

| Canal | Lignes rendues | Lignes déclarées | Ce qui trahit l'amputation |
|---|---|---|---|
| SAP GUI (ALV) | toutes, mais cellules VIDES tant qu'on n'a pas défilé | `RowCount` | les lignes vides |
| WebGUI (ITS) | une PAGE de 200, renumérotées `row[1]`..`row[200]` | `totalRows` du `lsdata` de la grille | **rien** |
| UI5 (`sap.m.Table`) | le seuil de croissance, 30 mesurées | `getLength()` du binding, 4133 mesurées | **rien** |
| RFC (`RFC_READ_TABLE`) | exactement `ROWCOUNT` lignes, 3 mesurées sur 205 | **rien du tout** | **rien** |

Mesures : une sélection SE16 de 2000 lignes rend `totalRows:2000` dans le
`lsdata` et 200 lignes dans le DOM ; une List Report Fiori Elements rend 30
lignes sur 4133. Dans les deux cas les lignes rendues sont **propres,
ordonnées, complètes et correctement numérotées**. Un fichier écrit à partir
de là est fidèle à ce qui a été lu, se relit sans écart, se compare à sa
source sans écart, et présente un extrait comme un inventaire.

Le canal écran est le moins dangereux des trois : une ALV creuse laisse au
moins des cellules vides à compter. Les deux canaux web ne laissent rien.

## Pourquoi c'est coûteux

Aucune garde fondée sur le CONTENU ne peut voir le cas sur les canaux web :
il n'y a rien d'anormal dans le contenu. Aucune garde fondée sur le NOMBRE
non plus, si ce nombre vient de la lecture elle-même. La seule chose qui
tranche est le total que la SOURCE déclare, et il faut aller le chercher :
dans un attribut `lsdata` côté WebGUI, dans le binding côté UI5.

## Ce qu'on en fait

- Confronter TOUJOURS un relevé au total déclaré, **avant** d'écrire quoi que
  ce soit à partir de lui. Un refus qui constate après coup n'empêche rien.
- Une seule règle de refus pour tous les canaux, jamais une par canal : une
  règle par canal est une règle que le canal suivant fait oublier. Ici
  `sapfx_common.table_extract`.
- « Non mesuré » n'est jamais « complet » : un total non déclaré rend un
  verdict `None`, et le refus porte aussi sur ce silence, parce que le canal
  qui se tait est précisément celui qui ne laisse aucune autre trace.
- Ne jamais dimensionner une boucle sur ce qu'un lecteur de table a rendu.

Corollaires de lecture relevés au passage : le DOM éclate une grille WebGUI à
colonnes figées en deux tables HTML alors que les SID des cellules la
ré-unifient (`.../row[N]/cell[M]`, M étant l'index dans `ColumnIDs`), et faire
GRANDIR une table UI5 n'est pas une voie (le chargement se fait au
défilement ; ni le déclencheur ni le seuil ne la remplissent, et 138
allers-retours pour matérialiser un écran est un contournement, pas une
capacité). Sur ce dernier point, la réponse honnête est de DÉCLARER l'extrait.

Voir [[une-alv-non-defilee-se-lit-vide-sans-lever]] (le premier tiers de ce
constat, sur le canal écran) et
[[extraire-un-tableau-sap-n-est-pas-l-asserter]].

## Complément du même jour : le décalage de colonnes

Une revue indépendante a fait sortir un cinquième cas, de la même famille et
plus difficile encore. Les deux lectures d'une même table peuvent ne pas voir
les mêmes colonnes : sur une table Fiori Elements, la liste des colonnes porte
un en-tête VIDE (l'indicateur de brouillon) que les lignes rendent aussi.
Retirer une colonne sans nom est juste ; le faire en SILENCE ne l'est pas,
parce que le symptôme est identique à celui d'un **décalage** de colonnes, où
les valeurs ont glissé d'un cran.

C'est le seul défaut de ces canaux qu'aucune relecture de fichier ne peut
démasquer : la relecture confronte le fichier au RELEVÉ, jamais le relevé à
l'ÉCRAN. Le fichier serait complet, propre, fidèle, et faux.

Remède : ce qu'un assemblage laisse de côté est NOMMÉ (`ignored_columns`), une
clé nommée mise de côté devient l'alarme, et côté WebGUI une cellule dont
l'index dépasse les colonnes déclarées sort sous un nom de repli au lieu
d'être jetée.

## Le quatrième canal : celui qui ne déclare RIEN (2026-09-16)

Le RFC reproduit le piège du WebGUI (lecture bornée, lignes propres, aucun
témoin) et ajoute la difficulté que les trois autres n'ont pas : il n'expose
aucun total. Les trois premiers publiaient chacun le leur quelque part ; ici
le lecteur rend des lignes et se tait.

**La question devient donc « d'où vient le total », et c'est la seule décision
qui compte.** La réponse tentante est de compter par une seconde lecture avec
le même module : elle est fausse, et d'une façon connue du dépôt, puisqu'une
revue indépendante avait relevé la veille une garde qui comparait deux
nombres issus de la même source, donc vraie quoi qu'il arrive. Le total doit
venir d'un module DIFFÉRENT, qui compte côté serveur sans rapatrier de ligne.
Bénéfice secondaire mesuré : le comptage est deux ordres de grandeur moins
cher que la lecture (de l'ordre de 0,02 s contre 0,8 s pour 28 782 lignes).

Deux propriétés de ce compteur ont été MESURÉES et non supposées, parce
qu'elles décident de la validité de la garde. Il compte la table ENTIÈRE et
n'accepte aucune clause de sélection : une lecture filtrée ne peut donc pas
être bornée par lui, et les apparier annoncerait des lignes manquantes qui
n'ont jamais existé, sur un relevé pourtant intègre. Il suit en revanche le
mandant de la connexion, donc les deux mesures portent bien sur la même
population : établi en remarquant qu'une table d'utilisateurs est annoncée au
même nombre que ce que rend la lecture du mandant courant, alors qu'un second
mandant existe et porte au moins un compte.

D'où la règle : le couple « filtre + total de table entière » est refusé **à
l'entrée**, avant tout aller-retour réseau, et l'appelant a deux sorties
honnêtes, retirer le filtre ou fournir un total mesuré autrement.

Cas particulier à connaître de ce compteur : une table INEXISTANTE est
annoncée à zéro au lieu d'être refusée. Un zéro est donc soit une table vide,
soit une faute de frappe, et un relevé vide confronté à un total de zéro se
déclarerait « complet ».

**La preuve la plus forte reste le canal tiers.** Quand une table est projetée
par un service OData, son `$count` borne la lecture sans qu'aucun des deux
modules RFC n'y participe : ni celui qui lit, ni celui qui compte. C'est le
seul cas où la garde ne repose sur aucune partie de la chaîne qu'elle
vérifie.
