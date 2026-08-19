---
name: se16-selection-multiple-liste-noms
description: Sélectionner une LISTE de valeurs arbitraires dans SE16 passe par la modale de sélection multiple (ids relevés live) : c'est ce qui permet de traiter un lot d'objets sans préfixe commun en un seul passage
type: projet
date: 2026-08-17
---

Un critère SE16 accepte une valeur unique, un motif à joker (`SNWD*`) ou une
**liste** de valeurs. La liste passe par la modale de sélection multiple, dont
les ids ont été relevés live sur A4H (SAP GUI 8.00) pour le premier critère
`I1` :

- ouverture : `wnd[0]/usr/btn%_I1_%_APP_%-VALU_PUSH` (le bouton à droite du
  champ) ;
- modale « Multiple Selection for <CHAMP> », onglet « Select Single Values »,
  qui contient un **GuiTableControl** :
  `wnd[1]/usr/tabsTAB_STRIP/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE` ;
- une valeur par ligne visible :
  `.../tblSAPLALDBSINGLE/ctxtRSCSEL_255-SLOW_I[1,N]`, `N` étant l'index de
  ligne **visible** en base 0 (au-delà de la fenêtre visible, défiler comme
  pour tout table control) ;
- reprise dans l'écran de sélection : `wnd[1]/tbar[0]/btn[8]`.

La sélection ainsi chargée **n'est pas rémanente** : après un retour dans SE16,
une nouvelle sélection repart vide. Vérifié le 2026-08-17, une sonde suivante
sur un nom unique a bien retourné une seule ligne.

**Pourquoi :** classer ou lire un lot d'objets dont les noms n'ont aucun
préfixe commun (un package SAP livré, une liste issue de TADIR) coûte sinon un
aller-retour SE16 par objet. Avec la sélection multiple, sept tables du package
Flight (`SAIRPORT`, `SAPLANE`, `SBOOK`, `SCARR`, `SFLIGHT`, `SFL_AUX`, `SPFLI`)
ont été classées via DD02L en un seul passage. C'est aussi la limite du keyword
`Display Table Contents With Filter`, qui n'exprime qu'un critère par champ :
un besoin de liste réclame un keyword métier dédié.

**Comment appliquer :** garder les ids ci-dessus dans la couche `resources/`
(convention 1), remplir les lignes visibles puis reprendre par `btn[8]`, et
vérifier le retour à `wnd[0]` avec `Get Open Windows` avant d'exécuter (F8).
Le champ `I<n>` ciblé se relève d'abord sur l'écran réel : voir
[[se16-ecran-selection-champs-omis]].
