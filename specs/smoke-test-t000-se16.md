# Smoke test système : consultation des mandants (T000) via SE16

- **Canal** : ECC (SAP GUI)
- **Système / URL** : ABAP Platform Trial A4H (S/4HANA 1909), connexion
  `/H/vhcala4hci/S/3200`, mandant 001, utilisateur DEVELOPER.
- **Préconditions** :
  - Sortie SE16 en **grille ALV** pour l'utilisateur de test : keyword
    `Use ALV Grid In Data Browser` (réglage persistant par utilisateur ; la
    liste ABAP classique par défaut n'a pas d'objet grille scriptable).
    Constaté déjà actif sur ce poste au moment de l'exploration
    (`Get Data Browser Output` = `alv_grid`), mais l'appel reste idempotent
    et sans risque pour un autre utilisateur ou un autre poste.

## Données observées

Relevé live sur A4H (2026-09-21) :

- Table `T000` (mandants) : l'écran de sélection généré
  (`/1BCDWB/DBT000/SE16/1000`) est atteint directement, sans popup de choix
  de champs de sélection (la table compte moins de 40 champs).
- L'ouverture de cet écran de sélection affiche systématiquement un message
  de statut de **type `S`** (« A maintenance view exists for table T000 ») :
  purement informatif, il n'a jamais empêché la recherche.
- **2 mandants observés sans aucun filtre** : `000` et `001`, tous deux avec
  `MTEXT = SAP SE`. Cohérent avec l'attendu d'un système SAP minimal.
- « Number of Entries » (`wnd[0]/tbar[1]/btn[31]` sur l'écran de sélection)
  confirme le compte de 2 sans même ouvrir la grille de résultats, et
  fonctionnerait aussi sur une table vide (contrairement à F8, qui reste sur
  l'écran de sélection quand rien ne répond aux critères).
- Colonnes techniques de la grille de résultats (ids indépendants de la
  langue) : `MANDT`, `MTEXT`, `ORT01`, `MWAER`, `ADRNR`, `CCCATEGORY`,
  `CCCORACTIV`, `CCNOCLIIND`, `CCCOPYLOCK`, `CCNOCASCAD`, `CCSOFTLOCK`,
  `CCORIGCONT`, `CCIMAILDIS`, `CCTEMPLOCK`, `CHANGEUSER`, `CHANGEDATE`,
  `LOGSYS`.
- Fait notable propre à cette table : l'écran de sélection généré pour
  `T000` **n'expose aucun critère sur `MANDT`** (les 16 critères disponibles
  vont de `I1` = `MTEXT` à `I16` = `LOGSYS`). Sur la table des mandants
  elle-même, il est donc structurellement impossible d'introduire par
  erreur un filtre de mandant : une recherche « sans filtre » couvre
  nativement tous les mandants existants.
- Complétude vérifiée sur le relevé complet de la grille : aucune ligne
  entièrement vide (compte de lignes vides = 0), donc les 2 lignes lues sont
  bien les 2 lignes réelles, pas un artefact de défilement incomplet.

## Scénarios

### 1. La table des mandants répond avec au moins les mandants standard
- **Étapes** :
  1. `Open SAP And Log In` (Suite Setup).
  2. `Use ALV Grid In Data Browser` (réglage idempotent, Suite Setup).
  3. Atteindre l'écran de sélection SE16 de la table `T000`.
  4. Lancer la recherche sans renseigner aucun critère de sélection.
  5. Lire le contenu de la grille de résultats obtenue.
- **Résultat attendu** :
  - Le nombre de lignes retournées est strictement positif (au moins 2
    attendues : les mandants `000` et `001`).
  - Aucune ligne de la grille n'est entièrement vide.
  - Chaque ligne porte une valeur non vide pour la colonne technique
    `MANDT`.
- **Keywords métier manquants** : aucun. Le trajet complet s'appuie sur des
  primitives déjà présentes dans `SapEccLibrary`
  (atteinte de l'écran de sélection, lecture exhaustive de la grille,
  détection de lignes vides) ; le seul geste propre à ce scénario, « lancer
  la recherche sans filtre » (Exécuter / F8), est un geste SAP standard qui
  ne demande pas de nouveau mot-clé métier.

## Points de vigilance

- Test strictement en **lecture seule** (SE16 en consultation, aucune
  écriture) : rejouable à l'infini sans aucun effet de bord, et nativement
  **idempotent** (le contenu de `T000` ne varie pas d'un passage à l'autre
  sur ce système de laboratoire).
- La session doit être fermée dans tous les cas, y compris en cas d'échec
  (fermeture en Suite Teardown) : convention d'hygiène de session du dépôt.
- Le message de statut de type `S` affiché à l'ouverture de l'écran de
  sélection est informatif ; ne pas le confondre avec un message de type
  `E`, qui signalerait un refus (table ou structure inconnue).
- Sur cette table précise, aucun critère de sélection ne porte sur `MANDT` :
  il n'y a donc rien à vérifier de ce côté pour garantir l'absence de
  filtre, contrairement à une table métier ordinaire où il faudrait
  s'assurer qu'aucun champ `I<n>-LOW` n'est resté rempli d'un run
  précédent.
- Le compte « Number of Entries » et le nombre de lignes réellement lues
  dans la grille doivent coïncider. Sur un système où plus de deux mandants
  existeraient, adapter uniquement le seuil de l'assertion (« au moins 2 »),
  jamais un nombre exact en dur.
