---
name: ce-qu-un-canal-voit-et-que-les-autres-ne-voient-pas
description: 2026-09-14, trois limites que deux campagnes RFC consignaient comme non couvertes tombent en ajoutant l'écran et l'HTTP (origine profil contre défaut, mandant dont la connexion RFC est refusée, effet réellement produit) ; une limite de canal se lit dans la liste des non-couverts, et cette liste est une feuille de route
type: projet
date: 2026-09-14
---

Deux campagnes de sécurité du dépôt lisent la même cible par le seul canal
RFC, et chacune se termine par une liste de ce qu'elle ne peut pas voir. En
relisant ces listes, un constat : ce ne sont pas des oublis ni des arbitrages
de périmètre, ce sont des **limites de canal**. Trois d'entre elles tombent en
ajoutant deux protocoles.

| Limite consignée | Canal qui la lève | Ce qu'il donne |
|---|---|---|
| « rien ne dit si le durcissement vient d'un réglage ou d'un défaut » | l'ÉCRAN | le rapport de paramètres porte DEUX colonnes, profil d'instance et défaut, là où le RFC ne rend que la valeur effective |
| « l'état des comptes du mandant de référence n'est pas mesuré, l'ouverture RFC y est refusée » | l'ÉCRAN | un rapport lit TOUS les mandants depuis la session courante |
| « le paramètre est positionné » (sans savoir s'il agit) | l'HTTP | la réponse porte les drapeaux, ou non |

**Pourquoi :** un canal n'est pas seulement un moyen d'accès, c'est un point de
vue. Le RFC voit des tables et des valeurs effectives ; l'écran voit ce qu'un
programme a préparé pour un humain, donc des données dérivées que rien n'expose
autrement ; l'HTTP voit ce qui sort réellement sur le fil. Chaque point de vue
a des angles morts, et ils ne se recouvrent pas.

**Comment appliquer :** quand une campagne consigne honnêtement ses limites,
cette liste est une **feuille de route**, pas une clause de style. Avant
d'ajouter des scénarios dans un canal déjà couvert, relire ce que les
campagnes existantes déclarent hors de portée et se demander quel autre canal
le verrait.

Trois précautions apprises dans le même mouvement.

1. **Le croisement suppose la même cible, et le prouver est le premier
   scénario.** Sur ce banc, deux conteneurs partagent le nom d'hôte et seul le
   PORT les distingue, sur l'écran comme sur le RFC. Viser le mauvais port
   n'échoue pas : il répond.
2. **Un canal de plus n'est pas une capacité de plus partout.** L'écran de
   détail d'un paramètre rend ses valeurs dans des conteneurs HTML opaques,
   illisibles par l'API de scripting : c'est le RAPPORT, une grille ordinaire,
   qui donne l'origine. Figer ce manque dans un scénario évite de le
   redécouvrir à chaque reprise du sujet.
3. **Ce que l'écran rend n'est pas toujours une donnée.** Une colonne peut
   porter un code d'ICÔNE (indépendant de la langue, mais qui ne se lit pas
   seul) et une autre un LIBELLÉ TRADUIT (qu'on ne peut pas asserter). Un
   pictogramme s'interprète en le recoupant avec une vérité connue par
   ailleurs, à condition que le recoupement DISCRIMINE : un seul code et un
   seul état ne prouvent rien, et l'appliquer ailleurs serait une
   extrapolation.

Résultat obtenu par ce croisement, et qu'aucune des deux campagnes voisines ne
pouvait produire : le durcissement supérieur de cette release ne vient d'aucun
réglage d'exploitant. Voir
[[un-parametre-arme-ne-prouve-pas-son-effet]] pour le second.
