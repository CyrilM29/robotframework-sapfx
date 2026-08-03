# Consultation des données de vol (SFLIGHT) via SE16

- **Canal** : ECC (SAP GUI)
- **Système / URL** : ABAP Platform Trial A4H (S/4HANA 1909) — connexion
  `/H/vhcala4hci/S/3200`, utilisateur de test avec autorisations SE16.
- **Préconditions** :
  - Données de démonstration vol présentes — garde
    `Ensure Flight Demo Data Exists` (`resources/a4h_demo_data.resource`,
    génération SAPBC_DATA_GENERATOR uniquement si les tables sont vides).
  - Sortie SE16 en **grille ALV** pour l'utilisateur de test — keyword
    `Use ALV Grid In Data Browser` (réglage persistant par utilisateur ; la
    liste ABAP classique par défaut n'a pas d'objet grille scriptable).

## Données observées

Relevé live sur A4H (2026-07) :

- `SFLIGHT` (vols), `SPFLI` (liaisons) : non vides après la garde ; colonnes
  techniques stables `CARRID`, `CONNID`, `FLDATE` (ids techniques, indépendants
  de la langue de connexion).
- SE16 « Number of Entries » compte sans ouvrir la grille et fonctionne aussi
  sur table vide (retourne 0) — contrairement à F8 qui reste sur l'écran de
  sélection quand rien ne répond aux critères.
- Le compteur du popup peut contenir des séparateurs de milliers (dépend du
  profil utilisateur) — le keyword `Count Table Entries` normalise déjà.

## Scénarios

### 1. La table des vols contient des données
- **Étapes** :
  1. `Open SAP And Log In` (Suite Setup).
  2. `Ensure Flight Demo Data Exists`.
  3. `Count Table Entries    SFLIGHT`.
- **Résultat attendu** : le compte est un entier strictement positif.
- **Keywords métier manquants** : aucun.

### 2. Affichage des vols dans la grille ALV
- **Étapes** :
  1. `Use ALV Grid In Data Browser` (une fois, idempotent).
  2. `Display Table Contents    SFLIGHT`.
  3. `Read Displayed Grid` (10 premières lignes).
- **Résultat attendu** : la grille contient les colonnes techniques `CARRID`,
  `CONNID`, `FLDATE` (assertion sur les ids techniques, jamais sur les titres
  affichés, qui dépendent de la langue) et au moins une ligne.
- **Keywords métier manquants** : aucun.

### 3. Une structure n'est pas consultable dans SE16
- **Étapes** :
  1. `Try Open Table Selection Screen    SFL_AUX` (structure du modèle de
     données vol, package SAPBC_DATAMODEL).
- **Résultat attendu** : retourne `False` — SE16 rejette les structures avec un
  message de statut de **type `E`** (l'assertion porte sur le type, pas sur le
  texte localisé du message).
- **Keywords métier manquants** : aucun.

## Points de vigilance

- `SE16N` n'existe pas sur A4H — toujours SE16.
- Les champs de l'écran de sélection SE16 sont positionnels (`I<n>-LOW` suit
  l'ordre des champs de la table) et de type variable (`ctxt` vs `txt`) :
  sonder avec `Get Screen Signature` avant d'ajouter un filtre.
- Les tables de plus de 40 champs ouvrent un dialogue « choix des champs de
  sélection » (position de la case variable, choix persistant par utilisateur) —
  `Try Open Table Selection Screen` le gère déjà dynamiquement.
