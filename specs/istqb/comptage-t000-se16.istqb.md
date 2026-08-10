# Plan de test ISTQB : Comptage des mandants de la table T000 via SE16

> Sources : enregistrement live du recorder desktop (moteur natif) du
> 2026-08-05 (`tools/recorder/captures/record_a4h_istqb_20260805.robot` et son
> brouillon `record_a4h_istqb_20260805.istqb.md`, valeurs et localisateurs
> relevés en session réelle) ; conventions SE16 du plan
> `specs/sflight-consultation-se16.md` (2026-07) ; notes de terrain A4H du
> dépôt (« Number of Entries », rendu des listes SE16).
> Document de conception de test (ISTQB / ISO 29119-3) : lisible par un
> humain, rejouable par une IA via le bloc `replay` de chaque cas de test,
> indépendant du framework d'exécution.

- **Identifiant** : TP-comptage-t000-se16
- **Canal** : ECC (SAP GUI)
- **Système / URL** : ABAP Platform Trial A4H (Docker), connexion
  `/H/vhcala4hci/S/3200`, utilisateur `DEVELOPER`, mandant `001`
  (session live du 2026-08-05).
- **Références** : `tools/recorder/captures/record_a4h_istqb_20260805.robot`
  (enregistrement brut, jamais modifié),
  `tools/recorder/captures/record_a4h_istqb_20260805.istqb.md` (brouillon
  recorder), `specs/sflight-consultation-se16.md` (conventions SE16),
  `resources/ecc_keywords.resource` (keyword métier `Count Table Entries`,
  même mécanique de comptage), `tests/robot/ecc_data_smoke.robot` (contexte
  SE16 sur le même système).

## 1. Objectif et périmètre

- **Objectif** : vérifier que le comptage SE16 « Number of Entries » sur la
  table des mandants `T000` retourne la valeur attendue de l'instance
  (2 mandants observés le 2026-08-05) sans ouvrir la grille de résultats, et
  que l'écran de comptage reste visuellement conforme à sa baseline. Ce
  parcours exerce la mécanique de comptage (`btn[31]` → popup `G_DBCOUNT` →
  fermeture F12) qui sous-tend le keyword métier `Count Table Entries` utilisé
  par plusieurs suites du dépôt.
- **Éléments à tester** : lancement de transaction par OK-code (`/nSE16`),
  saisie du nom de table sur l'écran initial du Data Browser, déclenchement du
  comptage « Number of Entries », valeur du compteur dans le popup, empreinte
  visuelle de l'écran de comptage, fermeture du popup.
- **Hors périmètre** : affichage de la grille de résultats (F8 / ALV), toute
  écriture ou modification de données (parcours en lecture seule), filtres de
  l'écran de sélection, log off (l'enregistrement rattache une session déjà
  ouverte et la laisse ouverte). L'étape non mappée `maximize()` de
  l'enregistrement brut (fenêtre agrandie) est du confort d'affichage, exclue
  du replay.

## 2. Préconditions et données de test

- Session SAP GUI ouverte et connectée à l'A4H (l'enregistrement a été fait
  contre une session existante : le rejeu se rattache à une session ouverte,
  il n'inclut pas le login).
- Scripting SAP GUI pleinement actif côté serveur (RZ11
  `sapgui/user_scripting`, constat possible via
  `Scripting Should Be Fully Enabled`).
- Table de test : `T000` (table système des mandants, toujours présente :
  aucune garde de données de démonstration n'est nécessaire, contrairement aux
  parcours SFLIGHT/EPM).
- Valeur attendue observée : **2** entrées dans `T000` sur cette instance A4H
  le 2026-08-05. Cette valeur est un invariant d'instance, pas une constante
  universelle (voir risques).
- Baseline visuelle : `record_a4h_istqb_20260805_etape_01`, capturée à chaud
  pendant l'enregistrement (Ctrl+Alt+V). Sémantique snapshot : un premier
  passage sans baseline la créerait avec un WARNING au lieu de comparer.
- Aucun réglage persistant requis : « Number of Entries » fonctionne sans le
  réglage ALV du Data Browser (il compte sans ouvrir de liste, et retourne 0
  sur table vide, contrairement à F8).

## 3. Critères d'entrée / de sortie

- **Entrée** :
  - conteneur A4H démarré et licencié, connexion `/H/vhcala4hci/S/3200`
    joignable ;
  - session SAP GUI connectée en mandant `001` avec un utilisateur autorisé
    sur SE16 (`DEVELOPER` observé) ;
  - préflight scripting vert (serveur non `DisabledByServer`, ni readonly) ;
  - baseline visuelle versionnée disponible (ou premier passage assumé comme
    passage de création).
- **Sortie** :
  - TC-01 exécuté de bout en bout, assertion de valeur (2) et assertion
    visuelle conformes ;
  - popup de comptage refermé, écran de sélection SE16 de nouveau actif ;
  - aucune anomalie ouverte, ou chaque écart documenté (dérive de
    localisateur, dérive visuelle avec `.actual.png`, changement de
    volumétrie de `T000`).

## 4. Cas de test

### TC-01 : Comptage des entrées de T000 via SE16 « Number of Entries »

- **Priorité** : Haute. Le parcours valide la mécanique de comptage SE16
  (bouton « Number of Entries », popup compteur, fermeture F12) sur laquelle
  repose `Count Table Entries`, utilisée par les suites de données et
  d'exploration du dépôt ; il porte de plus la seule assertion visuelle
  enregistrée de ce domaine.

| # | Action | Données | Résultat attendu |
|---|--------|---------|------------------|
| 1 | Lancer la transaction Data Browser par OK-code | `/nSE16` | L'écran initial de SE16 s'affiche, aucun message d'erreur (type `E`) |
| 2 | Saisir le nom de la table dans le champ « Table Name » | `T000` | La valeur est acceptée dans le champ |
| 3 | Valider par Entrée | | L'écran de sélection de la table `T000` s'affiche |
| 4 | Déclencher « Number of Entries » (barre d'outils applicative) | | Le popup de comptage (fenêtre modale `wnd[1]`) s'ouvre, sans message de type `E` |
| 5 | Lire le compteur du popup | `2` | Le champ compteur vaut `2` (assertion numérique, indépendante de la locale ; le champ peut contenir des séparateurs de milliers sur de plus grosses tables) |
| 6 | Comparer l'écran à la baseline visuelle | `record_a4h_istqb_20260805_etape_01` | L'empreinte perceptuelle de l'écran correspond à la baseline enregistrée le 2026-08-05 |
| 7 | Fermer le popup (F12) | | Le popup se referme, l'écran de sélection SE16 de `T000` redevient actif |

- **Postconditions** : aucune donnée modifiée (parcours en lecture seule) ;
  popup refermé ; la session reste ouverte sur l'écran de sélection SE16 de
  `T000` (prévoir un retour au menu ou un teardown de session dans la suite
  qui industrialisera ce cas).

Bloc rejouable (actions normalisées ; les `hint` sont les localisateurs
relevés au moment de l'enregistrement, susceptibles de dériver) :

```yaml
test_case: TC-01
title: 'Scénario enregistré'
channel: sap-gui
steps:
  - action: run_transaction
    value: '/nSE16'
  - action: fill
    target: 'champ databrowse_tablename'
    value: 'T000'
    hint: {engine: 'sapgui-id', locator: 'wnd[0]/usr/ctxtDATABROWSE-TABLENAME'}
  - action: press_key
    value: 'Enter'
  - action: click
    target: '31'
    hint: {engine: 'sapgui-id', locator: 'wnd[0]/tbar[1]/btn[31]'}
  - action: assert_value
    target: 'champ g_dbcount'
    expected: '2'
    hint: {engine: 'sapgui-id', locator: 'wnd[1]/usr/txtG_DBCOUNT'}
  - action: assert_visual
    value: 'record_a4h_istqb_20260805_etape_01'
  - action: press_key
    value: 'F12'
```

## 5. Traçabilité

| Cas de test | Source | Exigence / spec | Suite exécutable |
|---|---|---|---|
| TC-01 | `record_a4h_istqb_20260805.robot`, étapes 1 à 7 (enregistrement live 2026-08-05) | Conventions SE16 : `specs/sflight-consultation-se16.md` (« Number of Entries » compte sans ouvrir la grille, 0 admis sur table vide ; `SE16N` n'existe pas sur A4H). Aucune spec sap-planner dédiée à `T000`. | Aucune suite `tests/robot/` ne rejoue ce scénario. Mécanique équivalente encapsulée dans `Count Table Entries` (`resources/ecc_keywords.resource`), exercée par `tests/robot/ecc_exploration.robot` et `ecc_scarr_spfli_liaisons.robot` sur d'autres tables. |

Écarts de traçabilité : scénario enregistré sans spec planner ni suite
générée (candidat au cycle plan → generate si le comptage `T000` doit devenir
un test de régression) ; à l'inverse, les scénarios SE16 des specs existantes
(SFLIGHT, SCARR/SPFLI) ne couvrent pas `T000`.

## 6. Risques et points de vigilance

- **La valeur attendue `2` est un invariant d'instance**, pas une règle
  métier : une copie de mandant sur le système testé la ferait dériver. Pour
  l'industrialisation, préférer une assertion relative (`Count Table Entries
  T000` strictement positif, ou comparaison entre deux mesures du même run).
- **Compteur avec séparateurs de milliers possibles** dans `G_DBCOUNT` selon
  le profil utilisateur (sans effet ici sur `2`, mais réel sur de plus
  grosses tables) : `Count Table Entries` normalise déjà en ne gardant que
  les chiffres.
- **Baseline visuelle sensible aux zones volatiles** (barre de statut,
  titre) : en cas de dérive récurrente au rejeu, re-capturer avec masquage
  des zones volatiles (`mask_elements=auto`) ; une dérive dépose un
  `.actual.png` à examiner avant de re-valider la baseline.
- **`SE16N` n'existe pas sur A4H** : toujours `/nSE16`.
- **Les localisateurs des `hint` datent du 2026-08-05** : les re-vérifier en
  cas de dérive d'écran (healing `Resolve Element With Healing`, sentinelle
  `ecc_drift_sentinel.robot`).
- Ne jamais rejouer avec des attentes fixes (`time.sleep`) : attendre les
  conditions d'écran (fin du sablier, élément présent).

## À compléter (questions ouvertes)

- L'assertion de valeur doit-elle rester la constante d'instance `2` ou
  devenir relative (`> 0`) pour survivre à une copie de mandant ?
- La baseline visuelle a-t-elle été capturée avec masquage des zones
  volatiles (`mask_elements=auto`), ou faut-il la re-capturer masquée avant
  usage en régression ?
