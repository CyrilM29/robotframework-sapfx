---
name: declare-n-est-pas-atteignable
description: 2026-09-14, trois lectures de sécurité exactes et trompeuses sur la même cible (zéro compte verrouillé mais deux expirés, 3410 services web déclarés pour 219 actifs, journal armé sans aucune entrée sur quatre ans) : ce qu'un système DÉCLARE et ce qui est ATTEIGNABLE sont deux mesures distinctes, et la première se lit plus facilement
type: projet
date: 2026-09-14
---

En montant la campagne de surface d'attaque contre la release 758, trois
lectures pourtant exactes se sont révélées trompeuses, et toujours dans le même
sens : elles décrivent ce que le système DÉCLARE, et on les lit comme si elles
décrivaient ce qui est ATTEIGNABLE.

1. **Un compte non verrouillé n'est pas un compte utilisable.** Le masque de
   verrouillage annonce zéro compte verrouillé sur les six du mandant, ce qui
   est vrai. Deux d'entre eux portent une date de fin de validité échue depuis
   vingt mois et ne peuvent plus servir : la surface d'entrée réelle est de
   quatre comptes. Les deux lectures répondent à deux questions et ne sont pas
   interchangeables.
2. **Un service web déclaré n'est pas un service servi.** Le dictionnaire porte
   3410 noeuds de services, dont **219** sont actifs. Rapporter le premier
   chiffre donne une surface seize fois trop grande, que personne ne peut
   auditer ; le second est ce qui répond sur le réseau.
3. **Un journal d'audit armé ne prouve aucun enregistrement.** Le paramètre du
   noyau vaut 1, dix emplacements de filtrage sont déclarés, **aucun n'est
   actif**, et la lecture du journal sur quatre ans rend zéro entrée et zéro
   fichier. Un lecteur du seul paramètre conclut « audit actif » et aucun
   incident de ces quatre années n'est reconstituable.

**Pourquoi :** la valeur déclarée est toujours la plus facile à lire. Elle tient
dans un paramètre ou une colonne, elle répond vite, et elle a l'air d'être la
réponse. La valeur atteignable demande de croiser deux sources (le drapeau
d'activation et la fiche du service, la configuration du journal et son
contenu, le verrouillage et la validité), donc on ne la lit que si on a d'abord
compris qu'elle diffère. Et comme les deux se ressemblent dans un rapport,
personne ne vient vérifier.

**Comment appliquer :** devant toute mesure de sécurité, se demander ce que la
source NE dit pas, et chercher la seconde lecture qui le dit. Trois formes
rencontrées : une seconde table (activation contre description), une seconde
propriété du même enregistrement (verrouillage contre validité), et le CONTENU
de ce dont on vient de lire la configuration. La troisième est la plus payante :
c'est elle qui transforme « armé sans filtre, donc il n'enregistre rien » d'une
déduction en un constat.

Corollaire de sûreté, hérité de
[[parametre-de-profil-inconnu-rend-une-valeur-vide]] : une lecture qui échoue ne
vaut JAMAIS zéro. Confondre « le journal est vide » et « je n'ai pas su le
lire » redonne exactement la conclusion recherchée, et c'est d'autant plus
facile à commettre que le module de lecture rend zéro entrée sans erreur quand
on l'appelle mal.

Voir [[une-garde-qui-compare-deux-lectures-de-la-meme-source]] pour le défaut de
méthode que la même campagne a produit en croyant vérifier l'une de ces
jointures.
