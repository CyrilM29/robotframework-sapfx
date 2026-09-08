# Reconnaissance de couverture sur une SECONDE release : ce que SapEccLibrary ne sait pas faire sur ABAP Platform 2023

> **Statut au 2026-09-08 (soir)** : lot de correction livré dans `src/` (§ 2
> sexies du backlog). Rejoué tel quel sur la bibliothèque corrigée, le
> registre a rougi 5 fois sur 6 manques en nommant « capacité désormais
> couverte » (le sixième, la position de l'entrée, mesurait un fait de cible
> contre une constante de page object et non la bibliothèque : refait), ET le
> témoin 7 a rougi sur un durcissement excessif du résolveur de grille, qui
> refusait un `Splitter` au lieu d'y descendre : corrigé avant la forme
> couverte. Les scénarios ci-dessous sont cette forme COUVERTE. Elle ne
> répète pas
> `specs/reconnaissance-couverture-sapgui-a4h.md` : celle-là a mesuré la
> couverture sur UNE release (754) et son lot de correction a été livré ;
> celle-ci mesure ce qu'une campagne mono-release ne PEUT pas voir.

- **Canal** : ECC (SAP GUI)
- **Système / URL** : ABAP Platform 2023 (conteneur `abap2023`, release
  SAP_BASIS **758** SP 0002, kernel **793**), connexion
  `/H/vhcala4hci/S/3201`, mandant 001, utilisateur DEVELOPER, SAP GUI 8.00,
  langue de session EN. Exploré live le 2026-09-08 en trois passes de sondes
  jetables jouées par `robot` sur le thread principal.
- **Préconditions** :
  - le conteneur `abap2023` démarré (ports publiés décalés : dispatcher 3201) ;
  - scripting serveur actif (`Scripting Should Be Fully Enabled` en setup) ;
  - SE16 en grille ALV (`Use ALV Grid In Data Browser`, persistant par
    utilisateur, idempotent) ;
  - aucune donnée applicative requise : SESSION_MANAGER, SE16, SU01, SM37,
    SE38, SPRO sont présentes sur tout système ABAP. `T000` est lue en
    lecture seule.
  - **piège de cible, à connaître avant d'interpréter quoi que ce soit** :
    les deux conteneurs du laboratoire annoncent le même identifiant système
    (`A4H`) et le même hôte interne (`vhcala4hci`). Seules la release et le
    kernel les séparent. Une campagne qui ne prouve pas sa release peut être
    verte contre l'autre système.

## Perception métier

- **Personas** : `@ecc` + `@basis`, et la casquette d'**architecte de la
  bibliothèque**. Cette campagne ne teste pas un processus métier : elle teste
  la BIBLIOTHÈQUE contre l'API SAP GUI Scripting d'une SECONDE release.
- **Où se lit la vérité** : dans ce que l'API expose sur le contrôle vivant de
  CETTE release, jamais dans ce que la campagne 754 a relevé. Un fait de la
  754 est ici une HYPOTHÈSE à re-mesurer, et c'est tout l'intérêt.
- **Risques priorisés** (ceux que la campagne couvre) :
  1. la **constante de release déguisée en fait** : un indice de position
     relevé sur une release et gravé dans la bibliothèque, qui rend une
     capacité indisponible ailleurs sans que rien ne l'annonce ;
  2. l'**assertion dépendante de la locale faute de mieux** : un refus
     applicatif ne s'asserte aujourd'hui que par son TYPE, alors que l'API
     expose l'identifiant EXACT du message (le pendant GUI de ce que le canal
     RFC a déjà, convention #3) ;
  3. les **familles de contrôles sans keyword** que la campagne 754 n'a pas
     traversées : onglets d'un tabstrip, barre d'application ;
  4. la **robustesse inégale et trompeuse des lecteurs de contrôle voisins** :
     visés sur un conteneur, les deux lecteurs laissent fuir une erreur COM
     brute, et le résolveur de grille va jusqu'à prendre un arbre à colonnes
     pour une ALV (un keyword de grille qui PASSE sur un arbre, le vert et
     faux type) ;
  5. le **vert et faux de portabilité** : croire portée une capacité qu'on n'a
     mesurée que sur une release, ou l'inverse, croire divergent ce qui est
     identique. Une équivalence MESURÉE est un résultat.
  - **Hors périmètre (dit)** : les familles déjà mesurées sur la 754 et non
    reprises ici (arbres, combo par clé, formats, calendrier, actions de
    grille, cases, carte `@N`) ; le contenu d'un `HTMLViewer` ou d'un
    `AbapEditor` (hors API) ; le canal RFC de cette cible (il a sa suite, et
    il exige un relais TCP local dont le SAP GUI n'a pas besoin).
- **Assertion reine** : **le registre des capacités de la 758 est exact**.
  Chaque scénario reproduit UN manque, ou constate une capacité qui PORTE, et
  consigne un verdict `gap` / `covered` / `poste` / `hors_api` dans un
  registre JSON déterministe qui nomme SA cible (release et kernel compris) ;
  le scénario échoue dans les deux sens le jour où l'observation diverge.
- **Réversibilité** : lecture seule. Les seules valeurs posées le sont dans
  des champs d'écran de sélection jamais exécutés en écriture, et le seul
  réglage persistant est la sortie du Data Browser, posée en Suite Setup
  comme dans toutes les suites SE16. Session refermée même sur échec.

## Données observées

Relevées live le 2026-09-08 (ABAP 2023, release 758, kernel 793, SAP GUI 8.00,
session EN). Les ids sont donnés pour la couche `resources/`.

### La barre de menus, et ce qui diverge de la 754

- Le menu **System est l'avant-dernier menu de tête** sur les six écrans
  sondés (SESSION_MANAGER `menu[4]`, SE16 `menu[5]`, SU01 `menu[5]`, SM37
  `menu[3]`, SE38 `menu[5]`, SE11 `menu[5]`). **Cette moitié de l'heuristique
  PORTE** : elle tient sur les deux releases.
- Son entrée « Status... » est en position **10**, contre **11** sur la 754 :
  la 758 a perdu l'entrée « List » (12 entrées contre 13). C'est le seul
  écart, et il suffit à rendre `Get System Identity` inopérant.
- Ce qui tient sur les deux releases, et qui est la bonne ancre : « Status... »
  est l'**avant-dernière entrée** du menu System, « Log Off » fermant la
  liste (754 : 13 entrées, Status en 11 ; 758 : 12 entrées, Status en 10).
- **`GuiMenu.Name` n'est PAS un nom technique** : il vaut exactement `Text`,
  donc localisé (mesuré sur les douze entrées). Il n'existe aucune ancre
  technique de menu : les deux seules voies sont la position (dépendante de
  la release, prouvé) et le texte (dépendant de la langue).

### Le dialogue System > Status

- Atteint par `Select Menu Item    System > Status` (chemin de TEXTES), il est
  **structurellement identique à celui de la 754** : même dynpro
  `SAPLSHSY/<tcode>/700`, même ancre `wnd[1]/usr/txtSYST-MANDT`, mêmes boutons
  (`tbar[0]/btn[17]` « Other Kernel Information », `usr/btnPRELINFO`
  « Details »), même popup kernel `KINFOSTRUC-KERNEL_RELEASE` = `793`, même
  grille de composants aux colonnes techniques `COMPONENT` / `RELEASE` /
  `EXTRELEASE` / `HIGH_PATCH` / `DESC_TEXT`, ligne `SAP_BASIS` = `758` SP
  `0002`. **Le manque est donc exactement et seulement l'indice gravé.**

### La barre de statut

- `wnd[0]/sbar` expose, au-delà du type et du texte : **`MessageId`** (la
  classe de message ABAP, complétée à droite sur 20 caractères) et
  **`MessageNumber`**. Mesuré : table inexistante = `MO`/`402`, nom de table
  vide = `MO`/`410`, les deux de type `E`. Un message absent rend les trois
  champs VIDES (aucune identité inventée).
- `MessageParameter` est une MÉTHODE (les variables `&` du message), pas une
  propriété : elle se lit par index.
- Au matin du 2026-09-08, `Get Status Message` ne rendait que le type et le
  texte. Le texte est localisé, donc une suite ne pouvait asserter que le
  type : deux refus différents du même écran étaient indiscernables (`MO/402`
  contre `MO/410`). Depuis le lot du soir, `Get Status Message Identity` rend
  l'identité `MO/E/402` et `Status Message Should Be` la confronte.

### Les onglets (SU01 en affichage)

- `wnd[0]/usr/tabsTABSTRIP1` (`GuiTabStrip`) expose **`SelectedTab`**, un objet
  COM (le `GuiTab` actif). Chaque `GuiTab` porte son `Text` LOCALISÉ et un
  `Changeable` qui vaut vrai pour le seul onglet actif (mesuré : `tabpADDR`).
- **Douze onglets sur la 758 contre onze sur la 754** : `tabpUSAT`
  (« User Attributes ») est nouveau. Un page object qui grave la liste des
  onglets d'une release est faux sur l'autre.
- Au matin du 2026-09-08, aucun keyword d'onglet (`Select Tab By Label`,
  `Get Selected Tab`, `List Tabs`, `Select Tab` ABSENTS) : une suite cliquait
  un id d'onglet gravé. Livrés le soir (mixin `_tabstrip.py`).

### La barre d'application

- `wnd[0]/tbar[1]` porte les boutons de l'écran (SE16 écran de sélection :
  `btn[8]`, `btn[2]`, `btn[14]`, `btn[18]`, `btn[31]` « Number of Entries »).
- Au matin du 2026-09-08, aucun keyword d'inventaire (`List Toolbar
  Buttons`, `Click Application Toolbar Button` ABSENTS). `List Grid Toolbar
  Buttons` refuse explicitement cette barre (elle est réservée aux grilles,
  et son refus est actionnable), or c'est **la barre que trois messages
  d'échec de la bibliothèque nomment déjà comme l'endroit où chercher la
  fonction**. Livrés le soir (mixin `_toolbar.py`).

### Les conteneurs, et l'asymétrie entre deux lecteurs

- La 758 enveloppe la grille SE16 dans un `GuiSplitterShell/Splitter` :
  `cntlGRID1/shellcont/shell` est le splitter, la grille vit sous
  `shellcont[1]/shell`. **`Read Grid` et toutes les actions de grille PORTENT**
  (le résolveur descend jusqu'au premier `GuiShell/GridView` ; depuis le lot
  du soir c'est le SOUS-TYPE qui décide, au matin il s'arrêtait au premier
  descendant portant `ColumnOrder`) : équivalence mesurée, pas supposée.
- L'arbre du menu utilisateur est au même id que sur la 754
  (`cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell`), l'arbre de l'IMG
  de SPRO n'est PAS enveloppé (`cntlTREE_CONTROL_CONTAINER/shellcont/shell`).
- **Au matin du 2026-09-08, visés sur le CONTENEUR de l'arbre de l'IMG, les
  deux lecteurs laissaient fuir une erreur COM brute** (corrigé le soir : le
  scénario 6 exerce la forme couverte) : `Read Tree Nodes` un
  `AttributeError: <unknown>.GetAllNodeKeys`, `Read Grid` un
  `AttributeError: ElementAt.RowCount`. Et la cause du second est pire qu'un
  simple refus manqué : le résolveur de grille descend jusqu'au premier
  descendant portant `ColumnOrder`, or un arbre à colonnes (type 2) en porte
  une, si bien que `Get Grid Column Ids` visé sur ce conteneur PASSE en
  rendant `['HierarchyHeader']` : un keyword de grille réussit sur un arbre.
  Le refus actionnable de `Read Grid` (contrôle visé, profondeur explorée,
  remède nommé) existe, mais seulement là où AUCUN descendant ne porte
  `ColumnOrder` : mesuré sur `wnd[0]/tbar[1]`. (Relevé corrigé à la
  génération : la première lecture de la sonde avait pris ce refus-là pour le
  comportement général.)

### L'identité, et ce que la session ne dit pas

- `session.Info` n'expose **NI la release NI le kernel** : les vingt et une
  propriétés lisibles sont celles de la session (mandant, utilisateur, langue,
  programme, transaction, serveur d'application, temps de réponse). `dir()`
  rend une liste VIDE sur ce proxy COM : les propriétés se sondent par nom.
  Le dialogue System > Status est donc la SEULE voie côté SAP GUI, ce qui
  justifie le détour que fait `Get System Identity`.
- Piège relevé : `session.Info.SystemNumber` vaut `1` sur cette cible et `0`
  sur l'autre. Cela ressemble à une ancre d'identité et n'en est pas une :
  le numéro reflète le PORT publié par le conteneur, pas l'instance interne,
  qui est `00` des deux côtés.

## Scénarios

Chaque scénario consigne un verdict dans le registre : `gap` (l'API le permet,
la bibliothèque ne le fait pas), `covered` (la capacité est exercée live et
tient), `poste` (limite de poste constatée), `hors_api` (l'API ne l'expose
pas). Le verdict ATTENDU est celui de la table « Clés de registre ».

### 1. L'identité du système se lit sur cette release

- **Étapes** : sur SE16, `Get System Identity` (l'entrée « Status... » est
  désormais RÉSOLUE : avant-dernière entrée de l'avant-dernier menu, et elle
  doit ouvrir un dialogue) ; lire la pile de fenêtres ; confronter le dict
  rendu à l'identité relevée À LA MAIN en Suite Setup (chemin de textes).
- **Résultat attendu** : le keyword rend `basis_release` `758` et
  `kernel_release` `793`, `unread` VIDE, et les sept clés d'identité
  (système, mandant, utilisateur, release SAP_BASIS et SP, kernel et patch)
  ÉGALES à la mesure manuelle ; aucun modal résiduel ; `System Identity
  Should Be    basis_release=758    kernel_release=793` passe. Verdict
  `covered`. (Forme « manque » du matin : le keyword échouait en nommant la
  disposition de la barre, et cliquait « Log Off », l'entrée 11 de la 758.)

### 2. L'entrée System > Status est résolue sur chaque écran

- **Étapes** : sur les six écrans sondés, lire la barre de menus
  (`List Menu Items`) pour constater que le menu System est l'avant-dernier
  menu de tête et « Status... » son avant-dernière entrée, en position 10 ;
  puis `Open System Status` (résolution par la bibliothèque) et `Dismiss
  Modal Window`.
- **Résultat attendu** : sur les six écrans, la position mesurée est 10 (la
  754 avait 11 : le fait de cible ne bouge pas) ET `Open System Status`
  ouvre le dialogue vérifié puis le referme, sans jamais toucher « Log Off ».
  Verdict `covered`.

### 3. Un refus applicatif s'identifie par sa classe et son numéro

- **Étapes** : sur SE16, provoquer DEUX refus différents (table inexistante,
  nom de table vide) ; `Get Status Message Identity` après chacun ;
  `Status Message Should Be` avec la bonne identité, puis avec celle de
  l'AUTRE refus.
- **Résultat attendu** : les deux refus portent le même type `E`, la même
  classe `MO` et des numéros DIFFÉRENTS (`402`, `410`), rendus sous la forme
  `MO/E/402` et `MO/E/410` ; l'assertion passe sur la bonne identité et
  ÉCHOUE sur l'autre, en nommant l'attendu et le lu : deux refus du même
  écran sont discernables sans un mot de texte localisé. Les identifiants ne
  sont plus des constantes de sonde : ils sont MESURÉS par le keyword.
  Verdict `covered`.

### 4. Un onglet se choisit et se lit par keyword

- **Étapes** : SU01 en affichage ; `List Tabs` ; `Get Selected Tab` (l'onglet
  actif à l'arrivée) ; `Select Tab` par CLÉ technique (`DEFA`) ; relire ;
  `Select Tab By Label` par un libellé porté par le page object ; restaurer
  l'onglet initial par sa clé et le relire.
- **Résultat attendu** : douze onglets listés dont la clé `USAT` (un de plus
  que la 754) ; l'onglet actif relu change à chaque sélection et revient à
  l'initial ; le sous-écran de l'onglet sélectionné existe. Verdict
  `covered`.

### 5. La barre d'application s'inventorie et se clique

- **Étapes** : SE16 sur l'écran de sélection de T000 ; `List Toolbar
  Buttons` ; `Click Application Toolbar Button` sur le bouton « Number of
  Entries » désigné par son SEGMENT d'id (`btn[31]`) ; lire le compteur du
  popup ; le refermer.
- **Résultat attendu** : cinq boutons inventoriés (id, icône, tooltip), dont
  celui du comptage ; le clic ouvre le popup de comptage, dont la valeur est
  un entier positif (T000 n'est jamais vide) ; popup refermé. Verdict
  `covered`.

### 6. Deux lecteurs de contrôle, un même refus actionnable

- **Étapes** : sur SPRO, lire l'arbre de l'IMG visé JUSTE, puis viser son
  CONTENEUR avec `Read Tree Nodes`, `Read Grid` et `Get Grid Column Ids`, et
  viser l'ARBRE lui-même avec `Read Grid`.
- **Résultat attendu** : visé sur le conteneur, `Read Tree Nodes` DESCEND et
  rend les nœuds (en WARNING) ; `Read Grid` et `Get Grid Column Ids`
  ÉCHOUENT en nommant le contrôle visé, la profondeur explorée et le remède,
  sans plus jamais prendre l'arbre pour une grille ; visé sur l'arbre,
  `Read Grid` refuse en nommant `GuiShell/Tree` et `Read Tree Nodes`.
  Verdict `covered`. (Forme « manque » : `Get Grid Column Ids` PASSAIT sur
  l'arbre en rendant `HierarchyHeader`, et les deux lecteurs laissaient fuir
  une `AttributeError` COM brute.)

### 7. La grille enveloppée dans un splitter se lit quand même (témoin couvert)

- **Étapes** : SE16 sur T000 en grille ; constater que le chemin attendu est
  un `GuiSplitterShell/Splitter` et que la grille vit un niveau plus bas ;
  lire la grille et ses colonnes techniques par le localisateur du splitter.
- **Résultat attendu** : le sous-type `Splitter` est visible dans la
  perception, `Get Grid Column Ids` et `Read Grid` rendent la grille malgré
  le conteneur intermédiaire. Verdict `covered`.

### 8. L'éditeur ABAP reste hors API sur cette release (témoin)

- **Étapes** : SE38, RSPARAM en affichage ; `Get Value` sur le contrôle
  éditeur ; `Get List Rendering Status`.
- **Résultat attendu** : le sous-type est `AbapEditor` sur la 758 comme sur la
  754, `Get Value` REFUSE en nommant le ProgID et le sous-type, et le
  préflight ne réclame aucun mode accessibilité. Verdict `covered`.

### 9. La release n'est pas dans la session (témoin hors API)

- **Étapes** : sonder `session.Info` sur les noms de propriété qui
  porteraient une release ou un kernel.
- **Résultat attendu** : aucune de ces propriétés n'existe, alors que le
  mandant, l'utilisateur et le serveur d'application sont bien là : le
  dialogue est la seule voie, et le détour de `Get System Identity` est
  justifié. Verdict `hors_api`.

### 10. Le registre est écrit, déterministe, et conforme au plan

- **Étapes** : écrire le registre par `Write Deterministic Artifact`
  (empreinte sur la seule clé `capabilities`) avec l'IDENTITÉ de la cible
  MESURÉE au scénario 1 (release et kernel, pas seulement le SID) ; le relire
  par `Read Deterministic Artifact` ; confronter à la table ci-dessous.
- **Résultat attendu** : registre présent, exactement les 9 clés de la table,
  identité portant `basis_release=758` et `kernel_release=793`, périmètre
  haché `capabilities`.

## Clés de registre

La suite recopie cette table dans `&{PLANNED_VERDICTS}`. Au 2026-09-08 (lot de
correction livré), les six manques sont `covered` ; la colonne « avant » garde
le verdict du tour de reconnaissance.

| Scénario | Clé de registre | Verdict attendu | Avant le lot |
| --- | --- | --- | --- |
| 1 | `identity.unavailable_on_release` | `covered` | `gap` |
| 2 | `menu.status_entry_position` | `covered` | `gap` |
| 3 | `statusbar.message_identity` | `covered` | `gap` |
| 4 | `tabstrip.select_and_read` | `covered` | `gap` |
| 5 | `toolbar.application_inventory` | `covered` | `gap` |
| 6 | `tree.container_refuses_actionably` | `covered` | `gap` |
| 7 | `grid.splitter_wrapped` | `covered` | `covered` |
| 8 | `editor.get_value_refuses` | `covered` | `covered` |
| 9 | `identity.not_in_session_info` | `hors_api` | `hors_api` |

Les clés 2, 4 et 5 s'appuient AUSSI sur un fait de CIBLE (la position 10 de
« Status... », les douze onglets SU01, les cinq boutons de barre). Depuis la
revue indépendante du tour 2, ce fait est asserté par le scénario HORS du
verdict, après sa consignation : sur une autre release le scénario rougit en
nommant le fait de cible, et le verdict reste celui de la bibliothèque (le
mécanisme exact des deux rouges de portabilité du registre 754 sur la 758).

## Keywords métier manquants

Page object à créer : `resources/page_objects/sapgui_capability_probes_2023.resource`
(écrans et familles propres à cette campagne). Les mots-clés de REGISTRE sont
TRANSVERSES : ils sont extraits du page object de la campagne 754 vers
`resources/page_objects/capability_register.resource`, importé par les deux
(aucune duplication, et le contrat de verdict reste unique).

1. `Identite Mesuree A L Ecran` : ouvre le statut par le chemin de textes,
   lit release et kernel, referme tout, rend le dict de cible du registre.
2. `Tenter L Identite Par Keyword` : `Get System Identity` sous filet.
3. `Positions Du Menu System` : par écran, la position du menu System, celle
   de « Status... » et le nombre d'entrées.
4. `Provoquer Un Refus SE16    ${valeur}` : pose une valeur, valide, rend le
   type et le texte du message.
5. `Identifiant De Message Percu` : ce que la perception rend de la barre de
   statut (pour prouver que l'identifiant n'est PAS exposé par un keyword).
6. `Afficher L Utilisateur    ${user}`, `Onglets Percus`, `Bandeau D Onglets`.
7. `Boutons De La Barre D Application`.
8. `Conteneur De L Arbre IMG`, `Tenter Read Tree Nodes Sur`,
   `Tenter Read Grid Sur`.
9. `Localisateur De Grille SE16`, `Sous Type Percu`.
10. `Proprietes De Session Absentes    @{noms}`.

(Liste du tour de reconnaissance. La forme couverte a RETIRÉ du page object
les keywords qui ne servaient qu'à prouver un manque, voir le lot du soir,
point 6.)

## Écarts constatés à la génération

Relevés le 2026-09-08 en montant
`tests/robot/ui/ecc/reconnaissance_couverture_sapgui_2023.robot` (live, ABAP
Platform 2023, release 758, kernel 793). La suite asserte ce qui a été MESURÉ ;
les verdicts du registre, eux, sont inchangés.

1. **Scénario 6 : le plan attendait une asymétrie qui n'existe pas sur cette
   cible, et la mesure est pire que ce qu'il annonçait.** Le plan dit que
   `Read Grid` visé sur le conteneur de l'arbre de l'IMG « échoue en nommant le
   contrôle visé, la profondeur explorée et le remède ». Mesuré, il laisse fuir
   `AttributeError: ElementAt.RowCount`, exactement comme `Read Tree Nodes`
   laisse fuir `AttributeError: <unknown>.GetAllNodeKeys` : les DEUX lecteurs
   sont bruts. La cause est établie live : le résolveur de grille descend
   jusqu'au premier descendant portant `ColumnOrder`, or un arbre à colonnes
   (type 2) en porte une, et `Get Grid Column Ids` visé sur ce conteneur
   **PASSE** en rendant `['HierarchyHeader']`. Autrement dit un keyword de
   grille réussit sur un ARBRE, et le run journalise même le WARNING de
   descente (« grille trouvée à .../shellcont/shell et utilisée »). Le refus
   actionnable que le plan décrit existe bien, mais seulement là où AUCUN
   descendant ne porte `ColumnOrder` : c'est le cas de la barre d'application
   du scénario 5 (`wnd[0]/tbar[1]`), où le message nomme le contrôle, les
   6 niveaux explorés et `Get Screen Signature`. Le scénario 6 asserte donc les
   deux échecs bruts ET la cause ; le verdict reste `gap`, et le manque à
   corriger dans `src/` est double : ne pas confondre un arbre à colonnes avec
   une ALV, et refuser en nommant le contrôle des deux côtés.
2. **Scénario 1 : le keyword ne se contente pas d'échouer, il CLIQUE une autre
   entrée.** Sur la 758, l'entrée gravée (position 11) existe : c'est
   « Log Off ». `Get System Identity` la sélectionne donc, SAP ouvre son
   dialogue de confirmation, et la session ne survit que parce que
   `Dismiss Modal Window` répond « Non » avant que le keyword échoue. Vérifié
   live à deux reprises : la session reste pilotable et aucun modal ne subsiste
   (le scénario l'asserte par `Get Open Windows`). Le plan n'annonçait qu'un
   échec ; l'effet de bord aggrave le manque et vaut d'être nommé dans le lot
   de correction (l'entrée doit être RÉSOLUE, pas comptée).
3. **Scénario 9 : la sonde du plan violerait l'invariant de la campagne.** Le
   plan dit « sonder `session.Info` sur les noms de propriété qui porteraient
   une release ou un kernel ». Fait depuis la couche Robot, cela exige un
   `Evaluate` sur un objet COM, que cette campagne s'interdit précisément parce
   qu'elle mesure la couverture des keywords. La suite mesure donc le même fait
   par les DEUX seules lectures de `session.Info` qu'un keyword expose :
   `List Sap Sessions` (système, mandant, utilisateur, transaction) et
   `Get Session Telemetry` (compteurs de performance), aucune ne portant de
   release ni de kernel, et aucun keyword ne prétendant les en tirer. La sonde
   COM brute du 2026-09-08 (`Release`, `SapRelease`, `Kernel`,
   `SystemRelease` absentes, `dir()` vide) reste la source du fait, en
   « Données observées » ; elle n'a pas sa place dans une suite.
4. **Le registre porte son propre nom de fichier**
   (`${OUTPUT DIR}/ecc_capability_register_2023.json`), que le plan ne
   nommait pas : deux campagnes, deux cibles, deux registres, y compris dans un
   dossier de sortie partagé.
5. **Un troisième dérivateur de verdict a été ajouté**, `Verdict Hors Api`,
   dans le page object de cette campagne : la 754 n'avait aucun témoin
   `hors_api`, et le contrat du registre veut qu'un verdict soit DÉRIVÉ d'une
   observation, jamais posé. Il vit dans le page object 758 et non dans
   `capability_register.resource` pour ne pas toucher au fichier partagé avec
   la campagne 754.
6. **Le registre n'était pas déterministe au premier jet, et deux runs l'ont
   montré.** Le scénario 9 consignait d'abord la télémétrie de session BRUTE ;
   or ses compteurs sont des mesures de run (temps de réponse 62 ms puis 31 ms,
   temps d'interprétation 109 ms puis 125 ms), donc deux exécutions aux MÊMES
   verdicts produisaient deux empreintes différentes, ce qui ôtait tout sens à
   `Compare Deterministic Artifacts`. La preuve ne porte plus que sur les CLÉS
   exposées par les deux vues (`Cles Triees De`), puisque l'observation du
   scénario est « quels champs existent », jamais leur valeur. Vérifié : deux
   runs consécutifs rendent la même empreinte
   (`4f3a27815200752325d0135c2056a9c5a9bebce5d0ab13741b73faf4e8646447`). À
   retenir pour toute campagne de registre : une preuve ne doit contenir que ce
   que le scénario ASSERTE.
7. **Confirmé sans écart** : la position 10 de « Status... » et son rang
   d'avant-dernière entrée sur les six écrans, le menu System avant-dernier sur
   les six, les douze onglets SU01 (`tabpUSAT` compris), les cinq boutons de la
   barre d'application, les identifiants `MO`/`402` et `MO`/`410`, la grille
   SE16 enveloppée dans un `GuiSplitterShell/Splitter` et lisible quand même,
   l'éditeur ABAP en `AbapEditor` refusé par `Get Value`, la release 758 et le
   kernel 793. Le sous-écran de l'onglet « Defaults » porte le numéro 1105 sur
   cette release : il n'est pas gravé, l'ancre d'activation d'un onglet étant
   « le sous-écran existe » (un onglet inactif n'en rend aucun).
8. **Revue indépendante (sap-verifier, lecture seule) : les huit points de
   fond confirmés, `needs_human` sur un seul écart mécanique**, le registre
   partagé `capability_register.resource` né de l'extraction ne portait pas
   le bandeau « EXEMPLE À PERSONNALISER » que le garde
   `test_resources_are_examples.py` exige de toute resource : ajouté, avec
   l'en-tête orphelin du page object 754 retiré, garde et dry-runs des deux
   suites repassés. Quatre réserves non bloquantes, et ce qui en est fait :
   (a) les identifiants `MO/402` et `MO/410` de la preuve du scénario 3 sont
   des constantes issues de la sonde, jamais re-mesurées par la suite (qui ne
   le PEUT pas sans le keyword manquant) : la preuve et le scénario le disent
   désormais tels quels ; (b) le scénario 2 dérive la position de
   « Status... » d'un texte localisé, ce qui exige une session EN, sans
   alternative puisque `GuiMenu.Name` vaut le texte : documenté ; (c)
   l'empreinte du registre fige les textes de preuve (messages SAP de la
   langue de session, messages de la bibliothèque), donc un `Compare
   Deterministic Artifacts` contre une autre langue signalera des écarts de
   preuve à verdicts égaux : choix hérité de la 754, assumé ; (d) la porte de
   release est désormais posée DANS le Suite Setup (`La Cible Devrait Etre La
   Release Attendue` juste après la confrontation du SID à la session) : un
   run contre l'autre conteneur s'arrête avant le premier scénario au lieu de
   jouer les dix puis de rougir. Le tout rejoué live (run v5).

### Lot de correction du 2026-09-08 (soir) : ce que le rejeu a montré

1. **Le registre a mesuré, dans les deux sens.** Rejoué TEL QUEL sur la
   bibliothèque corrigée, il a rougi sur cinq des six manques en nommant
   « capacité désormais couverte : mettre à jour le plan et le registre »
   (scénarios 1, 3, 4, 5, 6). Le scénario 2 est resté vert : il mesurait la
   position de « Status... » contre une CONSTANTE de page object (l'indice
   11 gravé) et non contre la bibliothèque ; sa forme couverte exerce
   `Open System Status` sur les six écrans.
2. **Le témoin 7 a rougi aussi, et c'était un vrai défaut du lot** : la
   première version du résolveur de grille refusait TOUT `GuiShell` d'un
   sous-type autre que `GridView`, donc le `Splitter` qui enveloppe la grille
   SE16 sur la 758. Corrigé avant la forme couverte : un shell FEUILLE
   (`Tree`, `Calendar`, `AbapEditor`, `TextEdit`, `HTMLViewer`, `Picture`)
   est refusé en nommant son lecteur, tout autre sous-type est un conteneur
   que l'on traverse (`LEAF_SHELL_SUBTYPES` dans `sapfx_common.object_tree`,
   test unitaire dédié). Une campagne de capacités protège aussi de ses
   propres corrections.
3. **La forme couverte tient live (10/10)** : `Get System Identity` rend
   exactement l'identité relevée à la main (758 SP 0002, kernel 793 PL 101,
   rien de non lu) ; `Open System Status` résout l'entrée 10 sur les six
   écrans sans toucher « Log Off » ; `MO/E/402` et `MO/E/410` sont MESURÉS
   par `Get Status Message Identity` (plus des constantes de sonde) et
   `Status Message Should Be` refuse l'autre identité en nommant l'attendu et
   le lu ; douze onglets listés, actif `ADDR`, `DEFA` par clé puis par
   libellé, `ADDR` restauré et relu ; cinq boutons inventoriés avec leur icône
   (`B_EXEC`...), le comptage cliqué par segment rend un entier positif ;
   `Read Tree Nodes` descend le conteneur de l'IMG, `Read Grid` et `Get Grid
   Column Ids` refusent en nommant la profondeur explorée, `Read Grid` sur
   l'arbre nomme `GuiShell/Tree` et `Read Tree Nodes`.
4. **L'icône d'un bouton de barre est une ancre locale-safe que la 754
   n'avait pas révélée** : `IconName` vaut `B_EXEC` pour « Execute », lu
   best-effort par `List Toolbar Buttons` ; `Click Application Toolbar Button`
   l'accepte à la place d'un segment d'id.
5. **Le registre de la 754 porte désormais sur la 758 à 19/21**, rejoué tel
   quel après le lot : son Suite Setup passe (identité résolue), et les deux
   seuls rouges tiennent à UNE constante de page object de la 754, la
   position `menu[4]/menu[11]` que le scénario 16 attend comme id sélectionné
   (`menu[4]/menu[10]` sur la 758), le 21e étant la conformité du registre qui
   en découle. Aucun manque de bibliothèque : c'est la convention #1 vue du
   côté de l'utilisateur, `resources/` est le vocabulaire d'UNE installation.
   La 754 rejouée sur sa propre cible après le lot : 21/21.
6. **Revue indépendante du tour 2 (forme couverte) : `verified`, huit
   réserves non bloquantes, toutes traitées puis rejouées live.** (R1) Le
   page object gardait les keywords de la forme « manques » (dont un
   contournement dormant qui cliquait un id d'onglet gravé) et une variable
   définie deux fois : retirés. (R2) Trois faits de cible entraient dans un
   verdict de capacité (position 10, douze onglets, cinq boutons) : sortis du
   verdict, assertés après sa consignation. (R3) Le scénario 2 ne confrontait
   la résolution de la bibliothèque à rien : `Open System Status` rend
   désormais l'id de l'entrée qu'il a CLIQUÉE, et le scénario le confronte,
   position par position, au relevé par texte. (R4) Le glob `*attendu*lu*`
   est resserré sur l'identité attendue et l'identité lue. (R5) La descente
   de `Read Tree Nodes` est prouvée par l'ÉGALITÉ avec la lecture directe de
   l'arbre, plus seulement par « non vide ». (R6) Le verdict `hors_api` ne
   s'appuie plus sur l'absence de trois noms de keywords inventés ; la sonde
   COM de `session.Info` est conservée dans les preuves du plan (clé
   `hors_api_measure`) et la preuve du scénario y renvoie. (R7) Les manques
   comblés sont datés au passé, ici et dans le page object. (R8) Le refus du
   résolveur de grille est rédigé en français et nomme le sous-type comme
   critère, plus `ColumnOrder`.

## Points de vigilance

- **Prouver la cible avant de conclure.** Les deux conteneurs annoncent le
  même SID et le même hôte. Le scénario 1 lit la release et le kernel, et le
  registre les porte : un run contre l'autre système ne peut pas se faire
  passer pour celui-ci.
- **`GuiMenu.Name` n'est pas technique** : ne jamais l'utiliser comme ancre
  locale-safe, il vaut le texte.
- **`MessageId` est complété à droite sur 20 caractères.** Contrairement à la
  clé d'une combo box (où `""` et `" "` sont deux entrées distinctes), ce
  padding n'est pas une donnée : une classe de message est `MO`. Le futur
  keyword doit le dire dans sa documentation plutôt que de laisser croire à
  une normalisation gratuite.
- **`session.Info.SystemNumber` est un faux ami** (le port publié, pas
  l'instance).
- **La suite 754 n'était PAS rejouable telle quelle sur cette cible** au
  matin du 2026-09-08 : son Suite Setup lit l'identité, et le manque 1
  l'arrêtait là. C'est le premier constat de la campagne, et il vaut mesure ;
  après le lot du soir elle porte à 19/21 (lot, point 5).
