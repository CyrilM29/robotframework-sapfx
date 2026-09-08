---
name: indice-de-menu-dependant-de-la-release
description: 2026-09-08, un indice de position de menu relevé sur une release (System > Status en entrée 11 sur la 754) est faux sur une autre (entrée 10 sur la 758, l'entrée « List » ayant disparu) ; l'ancre qui tient sur les deux est « avant-dernière entrée », et rien dans l'API des menus n'est technique, `GuiMenu.Name` valant le texte localisé
metadata:
  type: project
---

`Get System Identity` ouvrait « System : Status » par POSITION, le menu System
étant l'avant-dernier de la barre et « Status... » son entrée **11**, relevé
sur six écrans de la release 754. Rejoué tel quel contre la release 758, le
keyword refuse : l'entrée 11 y est « Log Off », et il la CLIQUE avant de
constater que le dialogue atteint n'est pas le bon (SAP ouvre sa confirmation
de déconnexion, que `Dismiss Modal Window` décline ; mesuré deux fois à la
génération de la suite). La 758 a perdu l'entrée « List » du menu System (12
entrées au lieu de 13), et « Status... » y est en position **10**. Le dialogue atteint, lui, est structurellement IDENTIQUE sur
les deux releases (même dynpro `SAPLSHSY/<tcode>/700`, même ancre
`txtSYST-MANDT`, même popup kernel `btn[17]`, même grille de composants
`btnPRELINFO`) : le manque tenait exactement et seulement à l'indice gravé.

**Pourquoi :** une campagne mono-release ne peut pas distinguer un FAIT d'une
COÏNCIDENCE. Six écrans concordants sur une seule release donnent toutes les
apparences d'une règle, et deux moitiés de la même heuristique n'ont pas eu le
même sort : « le menu System est l'avant-dernier menu de tête » PORTE sur les
deux releases, « Status est l'entrée 11 » non. Ce qui a sauvé la mesure, c'est
que le keyword VÉRIFIE structurellement le dialogue atteint : il a refusé en
nommant la cause et en renvoyant vers la voie manuelle, au lieu de lire les
champs d'un autre dialogue et de rendre une identité plausible. Un keyword qui
aurait fait confiance à sa position aurait rendu du vide, ou pire, les valeurs
du dialogue voisin.

**Comment appliquer :** l'ancre qui tient sur les deux releases est
« **avant-dernière entrée** du menu System », « Log Off » fermant toujours la
liste (754 : 13 entrées, Status en 11 ; 758 : 12 entrées, Status en 10) : la
dériver comme le menu l'est déjà, jamais la graver, et RÉSOUDRE une entrée de
menu avant de la cliquer, puisqu'une position fausse ne tombe pas forcément
dans le vide : elle peut tomber sur « Log Off ». Et ne pas chercher
d'ancre technique du côté de l'API : `GuiMenu.Name` vaut exactement `Text`,
donc localisé (mesuré sur les douze entrées), si bien que les deux seules
voies sont la position (dépendante de la release) et le texte (dépendant de la
langue) ; c'est la raison pour laquelle le page object porte le chemin de
textes ET la position attendue. Règle générale : tout indice positionnel
relevé sur une cible est une hypothèse tant qu'une seconde cible ne l'a pas
confirmé, et le lot de correction se mesure sur les deux.

**Corrigé le soir même (2026-09-08)** : `Open System Status` résout
l'avant-dernière entrée de l'avant-dernier menu (`dialog_entry_before_last`
dans `sapfx_common.menu_path`), exige les points de suspension avant de
cliquer, et garde la vérification structurelle ; un test unitaire par
disposition (754, 758, sans dialogue, vide). Le registre 758 rejoué a rougi sur
le scénario correspondant en nommant « capacité désormais couverte », puis la
forme couverte l'exerce sur les six écrans.
Voir [[registre-de-capacites-sapgui]].
