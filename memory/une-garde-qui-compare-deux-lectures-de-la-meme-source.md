---
name: une-garde-qui-compare-deux-lectures-de-la-meme-source
description: 2026-09-14, une assertion censée prouver qu'une jointure a eu lieu comparait deux nombres issus de la MÊME table, donc ne mesurait rien ; le mode de panne qu'elle visait produit exactement la signature d'un système sain, et la suite passait
type: projet
date: 2026-09-14
---

La campagne de surface d'attaque lit les services web dans deux tables : l'une
porte le drapeau d'activation, l'autre le nom lisible, le chiffrement et le
compte de service éventuel. Un scénario était censé vérifier que la jointure
avait bien eu lieu, et l'assertion écrite était « les services actifs sont moins
nombreux que les services déclarés ».

Elle ne mesure rien. Les deux nombres sont tirés de la même lecture, celle de la
table d'activation : l'assertion est donc vraie dès qu'un seul noeud est
inactif, que la seconde table ait répondu ou non.

Ce qui rend le défaut coûteux est le mode de panne qu'il était censé attraper.
Si l'appariement se casse (clé de noeud qui ne correspond plus, seconde table
vide), le résumé garde exactement la même forme : des noms repliés sur
l'identifiant technique, **aucun compte de service**, **aucun service sensible**
reconnu, et un décompte d'actifs parfaitement juste. C'est la signature d'un
système sain. Le scénario voisin, qui asserte « aucun service actif ne porte de
compte de service », se serait donc vérifié tout seul sur du vide, et il était
déclaré bloquant.

Le défaut a été trouvé par la revue indépendante (`sap-verifier`), pas par
l'exécution : la suite passait 12/12, deux fois.

**Pourquoi :** quand on écrit une garde, on pense au résultat attendu et pas au
chemin par lequel il arrive. Une jointure réussie et une jointure perdue
produisent souvent le même NOMBRE de lignes, parce que l'on part de la table
pilote dans les deux cas ; ce qui diffère, c'est la richesse des lignes, et ça
ne se voit dans aucun décompte global. La même passe a produit deux variantes du
même aveuglement : un verdict d'audit qui acceptait une réponse vide comme une
lecture réussie, et une empreinte censée être déterministe que deux exécutions
du même jour ne pouvaient pas démentir.

**Comment appliquer :** quand une assertion prétend prouver qu'une étape a eu
lieu, vérifier d'abord d'OÙ viennent ses deux termes. S'ils sortent de la même
lecture, elle ne prouve rien.

Trois formes de garde qui, elles, mesurent :

1. **un témoin produit par l'étape elle-même** : ici un décompte d'appariements
   (`matched` / `unmatched`) rendu par la bibliothèque, seul champ qui distingue
   les deux situations ;
2. **une propriété que seule la seconde source peut fournir** : asserter qu'au
   moins un service sensible est reconnu par son NOM, impossible sans la table
   descriptive ;
3. **une contre-épreuve jouée dans le run** plutôt qu'affirmée : pour une
   empreinte censée ignorer une valeur, la faire varier et vérifier que
   l'empreinte ne bouge pas. C'est ce qui manquait au scénario d'artefact, dont
   le déterminisme était prouvé par deux exécutions du même jour, c'est-à-dire
   par rien.

Corollaire de méthode : une campagne verte n'est pas une campagne vérifiée. Les
trois défauts de cette passe étaient hors d'atteinte de l'exécution, puisque
c'est le sens même des assertions qui était faux.

Voir [[declare-n-est-pas-atteignable]] pour les mesures que cette campagne a
produites, et [[gardes-qui-ne-peuvent-pas-echouer]] pour la famille à laquelle
ce défaut appartient.
