---
name: service-epm-produit-cassee-en-ecriture
description: Le service OData de gestion des produits EPM refuse d'activer ET de supprimer un brouillon sur les deux images trial du banc ; défaut cuit dans le contenu de démonstration, insensible au redémarrage et à la restauration ; SNWD_PD sans écran de saisie ni document de modification ; un POST expiré côté client avait réussi côté serveur
type: projet
date: 2026-09-21
---

# Le chemin d'écriture du service produit EPM est cassé, sur les deux images

**Relevé le 2026-09-21**, en traitant un prompt qui demandait un cycle de vie
complet d'un produit EPM : création par l'API, modification du prix par le
WebGUI, trace de modification lue par le RFC.

## Le fait

Sur `SEPMRA_PROD_MAN` (entity set `SEPMRA_C_PD_Product`, draft-enabled,
construit sur BOPF), la création d'un brouillon réussit, puis TOUT le reste
échoue :

| Geste | ABAP Platform 1909 (754) | ABAP Platform 2023 (758) |
| --- | --- | --- |
| Activer le brouillon | `CM_EPM_REF_APPS/002` « Object node type DemoObject does not exist » | `/BOBF/FRW_COMMON/141` « Instance with the same key already exists » |
| Supprimer un brouillon | `CM_EPM_REF_APPS/002` | `CM_EPM_REF_APPS/002` |
| Éditer un produit actif | `HTTP 500 RAISE_SHORTDUMP` | non tenté |

Trois vérifications, et c'est leur combinaison qui tranche : le refus survit à
un **redémarrage** du conteneur, à une **restauration** de l'image sauvegardée
un mois plus tôt (donc antérieure à toute manipulation de la campagne), et il
se **reproduit sur la seconde release**. Ce n'est ni un verrou en mémoire, ni
un état de session rf-mcp, ni une release : c'est le contenu applicatif de
démonstration livré avec ces images.

La collision de clé de la 2023 a une cause lisible : le compteur de numéros
produit (`ProductForEdit`) est désynchronisé des brouillons orphelins que le
système porte déjà (`EPM-000042`, `000043`, `000051` à `000054`), et il
réattribue ces numéros aux brouillons neufs. On pourrait brûler des numéros
jusqu'à en trouver un libre ; on ne pourrait pas nettoyer ensuite.

Deux faits voisins sur la même table : `SNWD_PD` n'est maintenable par AUCUN
écran, desktop ou WebGUI (`MAINFLAG` vide dans `DD02L`, SE16 refuse en type
`E` « Table maintenance not allowed »), et aucun document de modification
n'existe pour elle (`TCDOB` et `CDPOS` vides : BOPF trace ailleurs).

## Pourquoi c'est coûteux

Le cycle demandé était plausible, chaque étape existe dans la bibliothèque, et
les deux premières réussissent. Sans les trois vérifications, on aurait conclu
tour à tour à un piège de pilotage, à un état corrompu, puis à un défaut d'une
release. Il a fallu un redémarrage et une restauration de conteneur (une
heure) pour établir ce qu'aucun message d'erreur ne disait.

Corollaire mesuré en route : un `POST` qui **expire côté client** (58 s sur le
premier appel d'un service jamais sollicité depuis le démarrage) avait
**réussi côté serveur** ; le rejeu, 2,5 s, a créé le brouillon SUIVANT. Sur un
chemin d'écriture, un timeout n'est pas une preuve de non-écriture.

## Ce qu'on en fait

- Sur ce banc, on **lit** le catalogue EPM, on n'y **crée** rien : la campagne
  trois canaux porte son assertion sur un produit existant, découvert à
  l'exécution (`HT-1000`, souvent cité, est absent de ce catalogue).
- La **réversibilité** tranche avant la faisabilité : un cycle qu'on ne sait
  pas défaire ne se joue pas sur un système partagé, même s'il passait.
- Toute lecture de cet entity set filtre `IsActiveEntity eq true` : les
  brouillons orphelins, non supprimables, s'accumulent et une lecture nue les
  rend tous.
- Devant un timeout sur une écriture, constater l'état avant de rejouer.
