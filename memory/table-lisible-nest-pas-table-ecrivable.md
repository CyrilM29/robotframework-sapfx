# Une table lisible n'est pas une table écrivable

**2026-08-22, choix d'une cible pour une simulation d'écriture.** Une cible
d'écriture avait été retenue sur quatre critères qui semblaient suffisants :
elle est observable par l'autre canal (comptage croisé prouvé), sa structure
est minimale (quatre champs, aucun GUID), c'est une table de démonstration hors
de tout flux métier, et sa clé courte permet un identifiant de test sans
collision.

Elle refuse la création d'entrée, par un message de statut de type `E`.

## Le critère manquant

Ce n'est pas une autorisation manquante, et rien dans le canal API ne le
laissait voir. La description de la table dans le dictionnaire porte un
**indicateur de maintenance**, et il est vide sur toutes les tables
transparentes du modèle de démonstration RAP concerné, comme sur les tables
métier du modèle EPM. Une table peut donc être transparente, consultable,
comptable et exposée par un service, tout en n'étant pas maintenable.

Le cinquième critère est donc : **la table accepte la maintenance**, et il se
lit dans le dictionnaire, jamais dans un `$metadata`.

## La voie symétrique était fermée aussi

Le service qui expose ce modèle déclare `creatable`, `updatable` et `deletable`
à **faux** sur l'entity set correspondant. Ni l'écran ni l'API ne peuvent y
écrire. Les deux refus disent la même chose par deux chemins, ce qui est
rassurant sur la cohérence du système et inutile pour trouver une cible.

## Ce qui généralise

- **L'ordre des sondes compte.** Vérifier la maintenabilité AVANT de retenir
  une cible coûte une lecture du dictionnaire ; le découvrir après coûte la
  conception d'un cycle entier autour d'une table qui le refusera.
- Une correspondance prouvée entre un entity set et une table
  ([[correspondance-entity-set-table-non-deductible]]) prouve qu'ils portent la
  même population. Elle ne dit rien sur ce qu'on a le droit d'y faire.
- Le même angle mort que pour les capacités d'écriture déclarées
  ([[annotation-odata-declaree-non-permissive]]) : la source consultée
  répondait à une question voisine de celle qu'on posait.
- Une cible d'écriture doit être un **paramètre**, jamais une constante gravée
  dans un plan ou une suite : c'est la seule forme qui survit au moment où la
  cible se révèle inadaptée.
