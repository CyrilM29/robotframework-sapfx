---
name: registre-de-capacites-sapgui
description: 2026-09-07, une campagne de reconnaissance mesure ce que SapEccLibrary ne sait pas faire sur un écran SAP GUI réel et le consigne dans un REGISTRE de capacités (gap/covered/poste/hors_api) dont chaque scénario est une reproduction qui rougit le jour où le manque est comblé ; dix-huit manques relevés avec leur chemin API correct (arbres, combo par clé, dates et locale, calendrier F4, double-clic et menu contextuel de grille, sous-types de shell, cases par libellé, menus, carte @N noyée par les menus, préflight de liste qui alerte sur une grille), le dernier trouvé par la revue indépendante
metadata:
  type: project
---

Le 2026-09-07, un tour de dix transactions Basis d'A4H (SESSION_MANAGER, SU01,
SM37, SE16, SE38, SPRO, SICF, SM59, SE93, SE11) a confronté chaque famille de
contrôles SAP GUI aux keywords de `SapEccLibrary`, en lisant d'abord ce que
l'API Scripting EXPOSE sur le contrôle vivant, puis ce que la bibliothèque en
fait. Plan `specs/reconnaissance-couverture-sapgui-a4h.md`, preuves
`specs/evidence/`, suite `tests/robot/ui/ecc/reconnaissance_couverture_sapgui.robot`,
page object `resources/page_objects/sapgui_capability_probes.resource`.

Ce que la campagne a établi, avec le chemin API vérifié qui rend chaque manque
comblable : la perception rend `GuiShell` sans son `SubType` (Tree, GridView,
AbapEditor, Calendar, Picture, HTMLViewer, Toolbar), avec le ProgID en guise
de texte ; aucun keyword ne lit un arbre (`GetAllNodeKeys`, `GetNodeTextByKey`,
`SelectNode`, `ExpandNode` passent, `GetItemText(clé, "TEXT")` pour un arbre à
colonnes de type 2 dont les clés sont complétées à gauche), et `Select Node`
hérité échoue sur certains nœuds ; un combo box ne se sélectionne que par
libellé localisé (`.Key` se pose, `Entries` se lit, rien n'est exposé) ;
une date se saisit dans le format de l'utilisateur (DEVELOPER : `DD.MM.YYYY`
et notation décimale `1.234.567,89`, lisibles dans SU01 Defaults, ISO refusé
en type E 00/065) ; le F4 d'une date ouvre un shell `Calendar` que `Pick F4
Value` casse en `com_error` brut alors que `SelectionInterval` sélectionne et
referme ; `Doubleclick Element` appelle `doubleClickItem` (arbres) là où une
grille veut `SetCurrentCell` + `DoubleClickCurrentCell` ; `Select Context Menu
Item` refuse une grille par son type là où `ContextMenu()` puis
`SelectContextMenuItem(&FILTER)` marchent ; `Get Value` sur un shell rend son
ProgID en PASS ; le moteur sémantique n'indexe pas le texte propre d'une case
ou d'un radio ; aucun keyword de menu ; la carte `@N` commence par les
entrées de menu ; et `Get List Rendering Status` déclare « mode accessibilité
nécessaire » sur une grille ALV comme sur un éditeur (« shell ET zéro label »,
sans lire le sous-type). Ce dernier a été trouvé par la revue indépendante
`sap-verifier`, qui a refusé un scénario « limite de poste » parce que sur une
grille il ne mesurait rien du poste : le registre avait failli enregistrer un
verdict `poste` qui était en réalité un manque de perception.

**Pourquoi :** une bibliothèque validée par des campagnes MÉTIER couvre les
contrôles que ces campagnes traversent (champs, boutons, ALV, table controls,
SE16) et ignore en silence les autres, et les keywords hérités du fork amont
n'avaient jamais été confrontés aux contrôles réels. Mesurer la couverture par
famille de contrôles, et non par scénario métier, est ce qui fait sortir ces
manques d'un coup ; les consigner dans un registre dont chaque ligne est une
REPRODUCTION exécutable empêche de les oublier ET empêche de les contourner
dans une resource (convention 12 : le scénario asserte le manque tel quel).

**Comment appliquer :** avant de coder un keyword de cette liste, rejouer le
scénario correspondant (il DOIT rougir une fois le keyword livré, avec le
message « capacité désormais couverte : mettre à jour le plan et le
registre »), puis passer son verdict à `covered` dans le plan et régénérer.
C'est exactement ce qui s'est passé le soir du 2026-09-07 : le lot livré
(cinq mixins, quatre modules purs, 31 keywords) a fait rougir 18 scénarios
sur 19, et la forme couverte du registre exerce depuis chaque capacité live
(19/19). Deux faits de plus, trouvés en fermant le lot : une combo peut porter
deux clés distinctes `""` et `" "` (la clé ne se normalise jamais à
l'écriture), et le modal « Details » d'une grille SE16 refuse `sendVKey` et
n'offre qu'un bouton « Close window » (d'où `Dismiss Modal Window`, qui
essaie les voies et vérifie la disparition). La revue indépendante de la
forme couverte a ensuite refusé trois assertions qui mesuraient moins
qu'elles n'affirmaient, et la leçon vaut pour tout registre : une lecture
qui NORMALISE (la clé de combo rendue sans ses blancs) rend une restauration
invérifiable ; une action vers l'état DÉJÀ acquis (cocher une case cochée)
ne mesure rien, viser l'état opposé à l'initial ; et un attendu PRODUIT par
le keyword voisin (`Input Date` pour juger `Pick Calendar Date`) n'est pas
une mesure, l'attendu se relève et vit dans le page object. Le registre porte
aussi l'identité de la cible (système, mandant, utilisateur), hors empreinte :
deux cibles aux mêmes verdicts donnent la même empreinte, et c'est
l'identité qui dit laquelle a été mesurée. Plus tard le même soir, deux clés
de plus (registre à 20) : l'identité lue à l'écran par `Get System Identity`
(le menu System est l'AVANT-DERNIER de la barre et « Status... » son entrée
11 sur six écrans, d'où une ouverture par position vérifiée par la présence
de `txtSYST-MANDT` ; la release ABAP ne vit ni dans le modal principal ni
dans le popup du kernel, mais dans la grille « Installed Software », ligne
`SAP_BASIS`), et la liste SE16 STANDARD, qui est rendue en labels et se lit
par `Read Abap List` sans mode accessibilité : le cas « shell opaque sans
label » qui a fondé le préflight n'a jamais été observé sur ce poste, la note
historique de RSPARAM visait une GridView. Le registre est désormais écrit et
relu par `sapfx_common.artifacts` (périmètre d'empreinte déclaré, empreinte
recalculée à la relecture).

**Seconde release (2026-09-08)** : le même registre rejoué tel quel contre le
conteneur 2023 (release 758) a d'abord rougi 21/21 sur son Suite Setup (voir
[[indice-de-menu-dependant-de-la-release]]), puis, une fois le lot de la
seconde release livré, il porte à **19/21**, et les deux rouges tiennent à UNE
constante de page object (la position de menu relevée sur la 754). C'est la
mesure de portabilité de la bibliothèque : `src/` porte, `resources/` est le
vocabulaire d'une installation (convention #1). Le registre propre à la 758
(`reconnaissance_couverture_sapgui_2023.robot`, 9 clés) a pris le relais pour
les familles que la 754 n'avait pas traversées, et il a attrapé un défaut du
lot lui-même (un durcissement qui refusait le `Splitter` de la grille SE16) :
une campagne de capacités protège aussi de ses propres corrections.
Un contrôle nouveau se sonde par ses propriétés avant d'écrire quoi que ce
soit ; ce qui est hors API (source d'un `AbapEditor`, contenu d'un
`HTMLViewer`) reste `hors_api` et ne devient jamais un keyword qui rend une
valeur plausible. Pour le tour lui-même, jouer les sondes par `robot` sur le
thread principal plutôt que par rf-mcp : voir
[[perception-vide-en-pass-sous-rf-mcp-cross-thread]].
