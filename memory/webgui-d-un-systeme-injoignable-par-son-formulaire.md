# Le WebGUI d'un système peut être injoignable par son formulaire et parfaitement joignable autrement

**Relevé le 2026-09-15**, en enchaînant la même extraction sur les WebGUI de
deux systèmes ABAP du banc.

## Le fait

Sur un des deux systèmes, la page de connexion du service ICF `webgui` rend
**14 champs dont 0 visible** : tous à 0x0, sans parent de mise en page, en
HTTP comme en HTTPS. L'attente de visibilité tient 60 secondes sans jamais
aboutir. Aucun moteur ne peut les atteindre, et c'est normal : ils n'occupent
aucune surface.

Le système voisin, lui, rend 5 champs visibles sur la même page et se remplit
sans histoire.

**La même adresse répond parfaitement à une authentification HTTP d'en-tête.**
Sans identifiant elle sert la page de connexion (titre « Logon ») ; avec
l'en-tête, elle sert la page de session WebGUI. Le système n'est donc pas
indisponible du tout.

## La fausse piste, et pourquoi elle était tentante

En HTTP, la page affiche « No switch to HTTPS occurred, so it is not secure to
send a password ». C'est une explication séduisante et **fausse** : une seconde
mesure a trouvé le même avertissement sur le système dont le formulaire
fonctionne. Il accompagne toute page servie en clair et n'explique rien.

Le seul écart propre au système muet est qu'il rend son fragment de repli sans
script (`<iframe ... onNoScript>`) comme du TEXTE. Indice, pas cause. **La
cause reste non établie.**

## Ce qu'on en fait

- La stratégie de connexion est une **variable de cible** (`form` contre
  `basic`), jamais une constante du canal ni un `IF` sur le système.
- On la choisit sur le CONSTAT que le formulaire est inatteignable, pas sur
  une explication : une explication fausse fait chercher au mauvais endroit
  bien plus longtemps qu'une absence d'explication.
- Un test qui ne connaîtrait que la voie formulaire conclurait « cible
  injoignable » sur un système disponible : c'est le genre de conclusion qui
  fait ouvrir un incident chez l'exploitant.

## Le corollaire, mesuré au même endroit

Sur ce même système, la **déconnexion propre n'aboutit pas** : le bouton
« More » du bandeau ne devient jamais visible, et 1451 éléments restent rendus
à la fermeture. La session serveur est laissée à expirer. Deux leçons :

1. Un teardown doit être BORNÉ. Non borné, ce déroulé consommait 361 s, soit
   les deux tiers d'une campagne de cinq cibles, pour une extraction de
   quelques secondes.
2. Borner à moitié ne borne rien : les attentes qui passent par le navigateur
   n'écoutent que SON délai, et c'était justement la première étape du
   déroulé. Corrigé, la campagne est passée de 445 s à 114 s.
3. Une session abandonnée doit être DITE. Une ressource qu'on croit rendue et
   qui ne l'est pas se paie plus tard, sur un système partagé.

Voir [[trois-canaux-materialisent-paresseusement]].
