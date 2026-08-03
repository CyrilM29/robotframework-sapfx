# Compagnies aériennes et liaisons de vol (SCARR / SPFLI) via SE16

- **Canal** : ECC (SAP GUI)
- **Système / URL** : ABAP Platform Trial A4H (S/4HANA 1909) — connexion
  `/H/vhcala4hci/S/3200`, client 001, langue EN, utilisateur de test avec
  autorisations SE16. Périmètre **strictement consultation** (SE16 display /
  « Number of Entries ») — aucune écriture.
- **Préconditions** :
  - Données de démonstration vol présentes — garde
    `Ensure Flight Demo Data Exists` (`resources/a4h_demo_data.resource`,
    génération `SAPBC_DATA_GENERATOR` uniquement si les tables sont vides).
    Lors du relevé, SCARR et SPFLI étaient déjà peuplées (la garde n'a rien
    déclenché).
  - Sortie SE16 en **grille ALV** pour l'utilisateur de test — keyword
    `Use ALV Grid In Data Browser` (réglage persistant par utilisateur,
    idempotent ; la liste ABAP classique par défaut n'a pas d'objet grille
    scriptable).

## Données observées

Relevé live sur A4H le 2026-07-12 (session rf-mcp, préflight
`Scripting Should Be Fully Enabled` passé).

### SCARR — catalogue des compagnies (18 entrées)

- « Number of Entries » : **18**. Colonnes techniques de la grille ALV :
  `MANDT`, `CARRID`, `CARRNAME`, `CURRCODE`, `URL`.
- Les 18 codes (`CARRID` → `CARRNAME`, `CURRCODE`) :
  AA American Airlines (USD), AB Air Berlin (EUR), AC Air Canada (CAD),
  AF Air France (EUR), AZ Alitalia (EUR), BA British Airways (GBP),
  CO Continental Airlines (USD), DL Delta Airlines (USD), FJ Air Pacific (USD),
  JL Japan Airlines (JPY), LH Lufthansa (EUR), NG Lauda Air (EUR),
  NW Northwest Airlines (USD), QF Qantas Airways (AUD),
  SA South African Air. (ZAR), SQ Singapore Airlines (SGD), SR Swiss (CHF),
  UA United Airlines (USD).
- Écran de sélection (programme généré `/1BCDWB/DBSCARR`, dynpro `SE16/1000`),
  champs positionnels relevés :

  | Champ | Critère | Locator observé | Type GUI |
  |---|---|---|---|
  | I1 | `CARRID` | `wnd[0]/usr/ctxtI1-LOW` (+ `-HIGH`) | GuiCTextField |
  | I2 | `CARRNAME` | `wnd[0]/usr/txtI2-LOW` | GuiTextField |
  | I3 | `CURRCODE` | `wnd[0]/usr/ctxtI3-LOW` | GuiCTextField |
  | I4 | `URL` | `wnd[0]/usr/txtI4-LOW` | GuiTextField |

  `MANDT` n'est **pas** proposé comme critère (mais apparaît en 1re colonne de
  la grille). Pas de dialogue « choix des champs de sélection » (table étroite).

### SPFLI — liaisons de vol (14 entrées)

- « Number of Entries » : **14**. Colonnes techniques de la grille ALV :
  `MANDT`, `CARRID`, `CONNID`, `COUNTRYFR`, `CITYFROM`, `AIRPFROM`,
  `COUNTRYTO`, `CITYTO`, `AIRPTO`, `FLTIME`, `DEPTIME`, `ARRTIME`,
  `DISTANCE`, `DISTID`, `FLTYPE`, `PERIOD`.
- Répartition par compagnie (comptes vérifiés au filtre `CARRID` +
  « Number of Entries », recoupés avec la grille complète) :
  **AA 1, AZ 2, DL 1, JL 2, LH 4, QF 1, SQ 2, UA 1** — total 14.
  Les 10 autres compagnies du catalogue (AB, AC, AF, BA, CO, FJ, NG, NW, SA,
  SR) n'ont **aucune** liaison.
- Les 14 liaisons (extrait des colonnes clés) :

  | CARRID | CONNID | De | Vers | DISTANCE (DISTID) |
  |---|---|---|---|---|
  | AA | 0017 | US NEW YORK (JFK) | US SAN FRANCISCO (SFO) | 2.572 MI |
  | AZ | 0555 | IT ROME (FCO) | DE FRANKFURT (FRA) | 845 MI |
  | AZ | 0789 | JP TOKYO (TYO) | IT ROME (FCO) | 6.130 MI |
  | DL | 0106 | US NEW YORK (JFK) | DE FRANKFURT (FRA) | 3.851 MI |
  | JL | 0407 | JP TOKYO (NRT) | DE FRANKFURT (FRA) | 9.100 KM |
  | JL | 0408 | DE FRANKFURT (FRA) | JP TOKYO (NRT) | 9.100 KM |
  | LH | 0400 | DE FRANKFURT (FRA) | US NEW YORK (JFK) | 6.162 KM |
  | LH | 0401 | US NEW YORK (JFK) | DE FRANKFURT (FRA) | 6.162 KM |
  | LH | 0402 | DE FRANKFURT (FRA) | US NEW YORK (JFK) | 6.162 KM |
  | LH | 2402 | DE FRANKFURT (FRA) | DE BERLIN (SXF) | 555 KM |
  | QF | 0005 | SG SINGAPORE (SIN) | DE FRANKFURT (FRA) | 10.000 KM |
  | SQ | 0002 | SG SINGAPORE (SIN) | US SAN FRANCISCO (SFO) | 8.452 MI |
  | SQ | 0015 | US SAN FRANCISCO (SFO) | SG SINGAPORE (SIN) | 8.452 MI |
  | UA | 0941 | DE FRANKFURT (FRA) | US SAN FRANCISCO (SFO) | 5.685 MI |

- Intégrité référentielle observée : les 8 `CARRID` porteurs de liaisons sont
  tous présents dans SCARR (⊂ du catalogue).
- Écran de sélection (programme généré `/1BCDWB/DBSPFLI`, dynpro `SE16/1000`),
  15 champs positionnels, types mixtes :

  | Champ | Critère | Locator observé | Type GUI |
  |---|---|---|---|
  | I1 | `CARRID` | `wnd[0]/usr/ctxtI1-LOW` | GuiCTextField |
  | I2 | `CONNID` | `wnd[0]/usr/ctxtI2-LOW` | GuiCTextField |
  | I3–I8 | `COUNTRYFR`, `CITYFROM`, `AIRPFROM`, `COUNTRYTO`, `CITYTO`, `AIRPTO` | `ctxtI3-LOW` … `ctxtI8-LOW` | GuiCTextField |
  | I9 | `FLTIME` | `wnd[0]/usr/txtI9-LOW` (affiche `0:00` à vide) | GuiTextField |
  | I10, I11 | `DEPTIME`, `ARRTIME` | `ctxtI10-LOW`, `ctxtI11-LOW` (affichent `00:00:00` à vide) | GuiCTextField |
  | I12 | `DISTANCE` | `txtI12-LOW` | GuiTextField |
  | I13, I14 | `DISTID`, `FLTYPE` | `ctxtI13-LOW`, `ctxtI14-LOW` | GuiCTextField |
  | I15 | `PERIOD` | `txtI15-LOW` | GuiTextField |

  `MAX_SEL` (« Maximum No. of Hits », `wnd[0]/usr/txtMAX_SEL`) vaut **200**
  par défaut — supérieur aux 14 entrées, aucune troncature à craindre ici.

### Comportements SE16 vérifiés live

- « Number of Entries » (`wnd[0]/tbar[1]/btn[31]`, popup
  `wnd[1]/usr/txtG_DBCOUNT`, fermeture F12) compte **toutes** les entrées
  répondant aux critères, indépendamment de `MAX_SEL`, et retourne **0 sans
  erreur** sur un filtre sans résultat (testé avec `CARRID = XX`).
- Les critères saisis sur l'écran de sélection **ne persistent pas** après un
  retour par `/nSE16` : `Display Table Contents SPFLI` juste après le filtre
  `XX` a bien affiché les 14 lignes (écran de sélection re-généré vierge).
- `CONNID` est restitué avec zéros de tête (`0017`) — comparer en **chaîne**,
  jamais en entier.
- `DISTANCE` est rendue avec séparateur de milliers (`2.572`, `9.100`) selon le
  profil utilisateur — même piège que le compteur du popup (déjà normalisé par
  `Count Entries On Current Selection Screen`).
- `FLTYPE` est vide sur les 14 liaisons (vol régulier ; aucune valeur charter
  dans ce jeu de démo).

## Scénarios

### 1. Le catalogue des compagnies contient des données
- **Étapes** :
  1. `Open SAP And Log In` (Suite Setup), `Scripting Should Be Fully Enabled`.
  2. `Ensure Flight Demo Data Exists` (Suite Setup, conditionnel).
  3. `Count Table Entries    SCARR`.
- **Résultat attendu** : compte entier strictement positif (18 observé sur le
  jeu de démo standard — valeur de calage, ne pas en faire une assertion dure
  si le trial a été regénéré différemment).
- **Keywords métier manquants** : aucun.

### 2. Le catalogue des compagnies s'affiche avec ses colonnes techniques
- **Étapes** :
  1. `Use ALV Grid In Data Browser` (une fois, idempotent, Suite Setup).
  2. `Display Table Contents    SCARR`.
  3. `Read Displayed Grid    max_rows=18`.
- **Résultat attendu** : chaque ligne expose les ids techniques `CARRID`,
  `CARRNAME`, `CURRCODE` (assertion sur les clés des dicts, jamais sur les
  titres affichés) ; les codes `AA`, `LH`, `SQ` figurent parmi les `CARRID`
  lus ; au moins une ligne.
- **Keywords métier manquants** : `Displayed Grid Should Contain Columns`
  (confort — assertion directe sur les ids techniques de colonnes, aujourd'hui
  à refaire en `Evaluate` dans chaque test).

### 3. La table des liaisons contient des données
- **Étapes** :
  1. `Count Table Entries    SPFLI`.
- **Résultat attendu** : compte entier strictement positif (14 observé).
- **Keywords métier manquants** : aucun.

### 4. Compter les liaisons d'une compagnie donnée
- **Étapes** :
  1. Ouvrir l'écran de sélection SPFLI (`Open Table Selection Screen    SPFLI`).
  2. Filtrer sur la compagnie `LH` (saisie du critère `CARRID`).
  3. Compter via « Number of Entries »
     (`Count Entries On Current Selection Screen`).
- **Résultat attendu** : LH → 4 ; répété avec AA → 1 (valeurs du jeu de démo
  standard ; l'assertion robuste minimale est : compte(LH) > compte(AA) > 0 et
  somme des comptes par compagnie = compte total SPFLI).
- **Keywords métier manquants** : `Count Flight Connections For Airline`
  (ouvre SPFLI, saisit le `CARRID` dans le champ de sélection dédié — locator
  `ctxtI1-LOW` à poser dans `resources/` — puis compte ; l'étape 2 n'a
  aujourd'hui aucun keyword métier et impose un `Input Text` avec id brut dans
  le test, ce qui violerait la convention 1).

### 5. Une compagnie sans liaison donne un compte zéro, sans erreur
- **Étapes** :
  1. Ouvrir l'écran de sélection SPFLI, filtrer sur un `CARRID` inexistant
     (ex. `XX`) — même mécanique que le scénario 4.
  2. Compter via « Number of Entries ».
- **Résultat attendu** : 0, sans message d'erreur ni popup résiduel (le popup
  de comptage se referme par F12 ; l'écran de sélection reste actif). Variante
  métier : un code du catalogue sans liaison (ex. `AF`, `BA`) doit aussi
  donner 0 — vérifie la cohérence catalogue/liaisons.
- **Keywords métier manquants** : le même `Count Flight Connections For
  Airline` que le scénario 4.

### 6. Toute liaison référence une compagnie du catalogue
- **Étapes** :
  1. `Display Table Contents    SCARR` puis `Read Displayed Grid` → ensemble
     des `CARRID` du catalogue.
  2. `Display Table Contents    SPFLI` puis `Read Displayed Grid` → ensemble
     des `CARRID` porteurs de liaisons.
  3. Vérifier l'inclusion du second ensemble dans le premier.
- **Résultat attendu** : inclusion vraie (observé : {AA, AZ, DL, JL, LH, QF,
  SQ, UA} ⊂ les 18 du catalogue). Assertion ensembliste sur ids techniques —
  indépendante de la locale et du tri d'affichage.
- **Keywords métier manquants** : `Read Column Values From Displayed Grid`
  (confort — extraire la liste/ensemble d'une colonne technique de la grille
  courante ; aujourd'hui un `Evaluate` par test).

### 7. Détail d'une liaison connue (lecture ciblée)
- **Étapes** :
  1. Ouvrir l'écran de sélection SPFLI, filtrer `CARRID` = `LH` et `CONNID` =
     `0400`.
  2. Exécuter la sélection (F8) et lire la grille.
- **Résultat attendu** : exactement 1 ligne ; `AIRPFROM` = `FRA`,
  `AIRPTO` = `JFK`, `DISTID` = `KM` (valeurs de données, stables quelle que
  soit la langue de connexion). `CONNID` comparé comme chaîne `0400`.
- **Keywords métier manquants** : `Display Table Contents With Filter`
  (généralisation : ouvre la table, applique des critères nommés sur l'écran
  de sélection avant F8 — les locators positionnels `I<n>-LOW` restant dans
  `resources/`).

## Points de vigilance

- `SE16N` n'existe pas sur A4H — toujours SE16.
- Champs de sélection **positionnels** (`I<n>-LOW/HIGH` suit l'ordre des champs
  de la table) et de **type variable** : sur SPFLI, `FLTIME`/`DISTANCE`/`PERIOD`
  sont des `txt<...>` alors que le reste est `ctxt<...>` — les relevés exacts
  sont dans « Données observées » ; re-sonder avec `Get Screen Signature` après
  tout changement de version/structure.
- Sur l'écran de sélection SPFLI, les champs heure/durée vides **affichent**
  `0:00` / `00:00:00` : ne jamais lire ces valeurs comme des critères saisis.
- Séparateurs de milliers possibles dans le popup de comptage **et** dans les
  colonnes numériques de la grille (`DISTANCE`) — normaliser avant toute
  comparaison numérique (filtrage caractère par caractère, pas de `\d` dans
  une cellule Robot — piège d'échappement documenté dans
  `resources/ecc_keywords.resource`).
- Les critères de sélection ne survivent pas à `/nSE16`, mais le réglage
  « ALV Grid » et le choix des champs de sélection sont **persistants par
  utilisateur** — d'où `Use ALV Grid In Data Browser` en setup, une fois.
- Ni SCARR ni SPFLI n'ouvrent le dialogue « choix des champs de sélection »
  (tables < 40 champs) — pas de garde nécessaire ici, `Try Open Table
  Selection Screen` la fournit déjà pour les tables larges.
- rf-mcp × COM : terminer tout batch MCP par `Element Should Be Present`
  (jamais `Wait Until Element Present` en dernière étape) ; une seule session
  ECC live par process rf-mcp.
- Comptes « de calage » (18 compagnies, 14 liaisons, LH=4, AA=1) : exacts pour
  le jeu `SAPBC_DATA_GENERATOR` standard du trial ; préférer les assertions
  relationnelles (somme des comptes par compagnie = total, inclusions) aux
  égalités dures quand le test doit survivre à une régénération de données.
