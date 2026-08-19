# Inventaire dynamique des tables ECC et S/4HANA

> **Statut : EXPLORATION LIVE COMPLÉTÉE, PRÊT POUR GÉNÉRATION (2026-08-17,
> passe 2)** : la passe 1 avait validé la sélection TADIR, le mode ALV et des
> sondes SE16 représentatives, en laissant ouverte la porte DD02L. La passe 2 a
> relevé live le mapping de sélection et les colonnes de sortie de DD02L, la
> technique de classification d'une liste de noms arbitraires, le catalogue réel
> des valeurs `TABCLASS`, et elle a corrigé deux observations de la passe 1 (voir
> « Écarts constatés à l'exploration »). Aucune cible ECC distincte n'a été
> fournie, donc aucune comparaison ECC/S/4HANA n'est encore revendiquée.

- **Canal** : ECC (SAP GUI), réutilisable sur SAP ECC et SAP S/4HANA
- **Système / URL** : première cible validée, A4H via
  `/H/vhcala4hci/S/3200`, système `A4H`, client `001`, langue `EN`
- **Périmètre** : consultation du référentiel DDIC et sondes SE16/SE11, sans
  modification des données métier. Le setup peut activer le mode ALV du Data
  Browser, réglage utilisateur persistant et idempotent, si le préflight le
  déclare nécessaire.
- **Objectif** : découvrir les objets disponibles à partir de packages et de
  préfixes configurables, les classer sans liste métier figée, puis comparer
  deux cibles à partir d'artefacts structurés
- **Préconditions** :
  - bibliothèque `SapEccLibrary` chargée et
    `resources/ecc_keywords.resource` importée ;
  - authentification injectée par un canal externe au plan et aux logs ;
  - `Scripting Should Be Fully Enabled` passé avant toute exploration ;
  - autorisations de consultation de SE16, SE11, `TADIR` et `DD02L` ;
  - aucune session SAP GUI résiduelle avant l'ouverture, contrôle par
    `List Sap Sessions` ;
  - fermeture garantie par `Close SAP` ou `Close All Sap Sessions`, y compris
    après une erreur.

## Paramètres de campagne

Chaque exécution reçoit une configuration explicite :

- `target_id` : identifiant stable et non secret de la cible ;
- `packages` : zéro ou plusieurs packages exacts ;
- `prefixes` : zéro ou plusieurs préfixes de noms d'objets ;
- `max_objects` : limite positive obligatoire, aucun mode illimité implicite ;
- `batch_size` : nombre configurable d'objets traités avant un point de reprise ;
- `probe_se16` : sonde de consultabilité activée par défaut ;
- `inspect_ambiguous_in_se11` : inspection SE11 des classifications inconnues ;
- `measure_entry_count` : désactivé par défaut, car un comptage intégral peut
  être coûteux sur une table volumineuse ;
- `max_counted_objects` : limite distincte quand le comptage est activé ;
- `artifact_path` : chemin de sortie propre à la cible.

Au moins un package ou un préfixe est requis. La campagne refuse une sélection
sans borne. Les packages et préfixes font partie de l'artefact afin d'empêcher
une comparaison trompeuse entre périmètres différents.

## Données observées

La passe live du 2026-08-17 a établi les faits suivants :

- système `A4H`, client `001`, langue `EN`, transaction initiale
  `SESSION_MANAGER` ;
- `Scripting Should Be Fully Enabled` : succès ;
- sortie SE16 initialement en liste classique, puis mode ALV activé avec
  `Use ALV Grid In Data Browser` ;
- package `SAPBC_DATAMODEL` : 27 objets `R3TR TABL` dans TADIR, non tronqués
  avec `max_hits=500` ; exemples : `SAIRPORT`, `SAPLANE`, `SBOOK`, `SCARR`,
  `SFLIGHT`, `SFL_AUX`, `SPFLI` ;
- package `S_NWDEMO_MODEL_DDIC` : 56 objets `R3TR TABL` dans TADIR, non
  tronqués avec `max_hits=500` ; exemples : `INCL_EEW_SNWD_BPA`,
  `INCL_EEW_SNWD_PD`, `INCL_TRF_SNWD_BPA`, `INCL_TRF_SNWD_PD`, `SNWD_AD`,
  `SNWD_ADMIN_DATA`, `SNWD_ATTACHMENTS`, `SNWD_BPA`, `SNWD_PD` ;
- sondes SE16 ciblées : `SAIRPORT` et `SNWD_PD` consultables ; `SFL_AUX` et
  `INCL_EEW_SNWD_BPA` rejetés avec un message de type `E`, cohérent avec une
  structure ;
- le balayage historique par comptage a traité `SAIRPORT` (53 entrées), puis
  `SAPLANE` a affiché un dialogue indiquant que le type DDIC `FLTP` ne pouvait
  pas être rendu dans un élément dynpro. Le bouton de comptage était absent et
  la session a ensuite été fermée par le système. Cette preuve interdit une
  classification exhaustive fondée sur l'ouverture SE16 de chaque objet ;
- les appels rf-mcp composites ont rencontré `RPC_E_WRONG_THREAD`. Les
  observations déterminantes ont été reproduites dans RobotCode REPL 2.7.0,
  Robot Framework 7.4.2, sur un seul thread COM ;
- toutes les sessions ouvertes pendant l'exploration ont été fermées.

qa-brain était sain (591 passages) et confirme l'abstraction par resources et
les assertions techniques ; il n'apporte pas de classification DD02L
supplémentaire.

### Passe 2 du 2026-08-17 : la porte DD02L est franchie

Tous les faits ci-dessous ont été relevés live sur A4H (client `001`, langue
`EN`), par rf-mcp en appels unitaires, session ouverte et refermée dans la même
passe.

- **Écran de sélection SE16 de DD02L : trois critères, ses seuls champs clés.**
  `TABNAME` en `wnd[0]/usr/ctxtI1-LOW`, `AS4LOCAL` en `ctxtI2-LOW`, `AS4VERS` en
  `txtI3-LOW`. `TABCLASS` **n'est pas** un critère de sélection : il ne peut pas
  servir de filtre.
- **Sortie ALV de DD02L : 50 colonnes** aux ids techniques, dont `TABNAME`,
  `AS4LOCAL`, `AS4VERS`, `TABCLASS`, `CLIDEP`, `APPLCLASS`, `CONTFLAG`,
  `VIEWCLASS`, `VIEWGRANT`, `PROXYTYPE`. La classification se lit donc **en
  sortie**, et l'objet se sélectionne par son nom.
- **Motif de nom accepté** dans `TABNAME` : `SNWD*` avec `AS4LOCAL=A` retourne
  114 lignes actives, dont 100 `TRANSP` et 14 `INTTAB`. Les 14 `INTTAB` sont
  `SNWD_ADMIN_DATA`, `SNWD_ADMIN_DATA_AIS`, `SNWD_AU_LOCK`,
  `SNWD_DG_MODEL_TREE_ITEM`, `SNWD_EPM_SESSION_LOCK`,
  `SNWD_ITEM_AVAILABILITIES1`, `SNWD_ITEM_AVAILABILITY`,
  `SNWD_ITEM_AVAILABILITY1`, `SNWD_LOCK`, `SNWD_PD_EI`, `SNWD_SOI_INCL_EEW_PS`,
  `SNWD_SOI_INCL_EEW_TR`, `SNWD_SO_INCL_EEW_PS`, `SNWD_SO_INCL_EEW_TR`.
- **Liste de noms arbitraires : la sélection multiple répond au cas du package
  sans préfixe commun.** Bouton `wnd[0]/usr/btn%_I1_%_APP_%-VALU_PUSH`, modale
  « Multiple Selection for TABNAME », GuiTableControl
  `wnd[1]/usr/tabsTAB_STRIP/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE`,
  cellules `ctxtRSCSEL_255-SLOW_I[1,N]` (N = ligne visible, base 0), reprise par
  `wnd[1]/tbar[0]/btn[8]`. Sept objets du package Flight classés en un seul
  passage : `SAIRPORT`, `SAPLANE`, `SBOOK`, `SCARR`, `SFLIGHT`, `SPFLI` en
  `TRANSP`, `SFL_AUX` en `INTTAB`.
- **La sélection multiple n'est pas rémanente** : après un retour dans SE16, une
  sélection sur `SCUS_BOOK` seul retourne exactement une ligne. Aucune
  contamination entre deux sondes successives.
- **Catalogue live des valeurs** (DD07L) : domaine `TABCLASS` = `APPEND`,
  `INTTAB`, `TRANSP`, `VIEW` ; domaine `AS4LOCAL` = `A`, `L`, `N`, `S`, `T`. La
  correspondance de classification se construit donc depuis le système, pas de
  mémoire.
- **DD02L classe aussi les vues** : `SCUS_BOOK` retourne `TABCLASS` = `VIEW`,
  avec `VIEWCLASS` = `D` et `VIEWGRANT` = `R`. La source de classification
  couvre les quatre classes ; c'est la découverte qui ne les atteint pas toutes
  (voir les écarts).
- **Convergence DDIC et sonde SE16** : `SFL_AUX` est `INTTAB` dans DD02L et
  rejeté par SE16 avec un message de type `E`. Les deux canaux se confirment sur
  le cas de référence.
- **Champs omis de l'écran de sélection SE16, mesuré sur SAPLANE.** DD03L donne
  18 champs, l'écran n'en expose que 14. Sont omis le champ client (`MANDT`,
  `DATATYPE` = `CLNT`) et les trois champs `FLTP` (`CONSUM` position 4, `SPAN`
  position 10, `LENG` position 12), **sans aucun message de statut**. Règle
  constatée, à re-vérifier avant de s'en servir sur une autre table : `I<n>` est
  le n-ième champ de la table triée par `POSITION`, une fois retirés le champ
  client et les champs `FLTP`. DD03L est donc la source locale-indépendante d'un
  mapping de sélection, là où les dictionnaires `<TABLE>_SELECTION_FIELDS` de la
  resource sont aujourd'hui relevés à la main.

## Écarts constatés à l'exploration (passe 2, 2026-08-17)

Deux observations de la passe 1 ne survivent pas à la re-vérification. Elles
sont corrigées ici plutôt que laissées en place, parce que le plan s'appuyait
dessus.

1. **SAPLANE n'est pas un objet bloquant.** La passe 1 rapportait un dialogue
   annonçant qu'un type `FLTP` ne pouvait pas être rendu dans un élément dynpro,
   un bouton de comptage absent, puis une session fermée par le système, et elle
   en tirait l'interdiction de toute classification fondée sur l'ouverture SE16.
   Passe 2 : `Try Open Table Selection Screen SAPLANE` retourne `True`,
   `Get Open Windows` ne montre aucune fenêtre modale (vérifié aussi en pilotage
   direct, sans le filet du keyword, qui referme les popups),
   `Get Status Message` est vide, et
   `Count Entries On Current Selection Screen` retourne **34**. Ce qui subsiste
   du constat : les champs `FLTP` sont silencieusement absents de l'écran de
   sélection. Conséquence : la raison de ne pas balayer SE16 objet par objet
   reste valable, mais elle change de nature. Ce n'est plus « un objet peut tuer
   la campagne », c'est « DD02L classe mieux, en un appel, et sans effet de bord
   de fenêtres ». Le plan ne doit plus citer SAPLANE comme preuve d'un blocage.
2. **La découverte est aveugle aux vues.** `List Repository Tables` filtre
   `OBJECT=TABL` en dur. TADIR contient 9 objets `R3TR VIEW` dans le seul
   package `SAPBC_DATAMODEL` : `H_S_UNIT`, `SACY_BOOK`, `SBC_CLIENT`,
   `SBC_CONTRY`, `SBC_LANG`, `SCUS_BOOK`, `S_DESVIEW`, `S_MACVIEW`, `S_SVIEW`.
   Le modèle de classification prévoit une classe `view` que la découverte ne
   peut donc jamais produire. À la génération, il faut soit paramétrer les types
   d'objets TADIR interrogés, soit retirer la classe `view` du modèle. Le
   silence actuel est le pire des trois.

## Écarts constatés à la génération (2026-08-17)

La suite MVP a été générée et validée live (7/7 vs A4H, deux exécutions dont
les résumés sont identiques : 99 objets découverts, 68 tables, 16 vues,
15 structures, 0 unknown, aucune troncature). Trois constats de génération :

1. **Une vue peut être rejetée par SE16 exactement comme une structure.** Les
   vues de projection `EPM_V_BP_CUST` et `EPM_V_BP_SUPP` (classées `VIEW` par
   DD02L) sont refusées par SE16 avec un message de type `E`. Le plan
   anticipait qu'une vue d'aide puisse refuser le Data Browser : c'est
   confirmé et plus large. Ce que fait la suite : l'assertion de convergence
   DDIC/SE16 ne porte que sur les classes `table` (écran atteint) et
   `non_consultable_ddic` (rejet type `E`) ; le résultat des vues est
   consigné dans l'artefact sans assertion. Conséquence durable : un rejet
   type `E` ne discrimine pas structure et vue non affichable, seule DD02L
   classe.
2. **Les types d'objets TADIR font partie du périmètre comparé.** Le premier
   artefact produit ne consignait pas les types interrogés
   (`selection.object_types` vide) : corrigé, `validate_scope` les normalise
   et les consigne (`TABL` et `VIEW` par défaut), la comparaison de deux
   artefacts les confronte comme le reste de la sélection.
3. **Répartition des keywords retenue** (décision d'architecture, 2026-08-17) :
   les capacités DDIC sont des keywords de la BIBLIOTHÈQUE (`SapEccLibrary`,
   mixin `_ddic.py` : `Fill Multiple Selection`, `Classify Ddic Objects`,
   `Get Ddic Classification Map`, `Validate Ddic Scope`, `Record Ddic Probe`,
   `Write Ddic Inventory Artifact`), la logique pure vit dans
   `sapfx_common/ddic_inventory.py` (barème, artefact, hash, comparaison,
   toutes testées hors SAP), et la composition de découverte reste dans la
   couche resources (`Discover DDIC Objects By Scope`,
   `List Repository Tables` paramétré par type d'objet). Les scénarios 6
   (SE11) et 7 (volumétrie) restent hors MVP ; le scénario 9 (comparaison)
   est couvert hors SAP par `tests/unit/test_ddic_inventory.py`.

## Modèle de classification

TADIR sélectionne les objets par package ou préfixe. DD02L est la source
primaire de leur classe active (`TABCLASS`, `AS4LOCAL`, `AS4VERS`). SE16 ne sert
qu'à produire des preuves ciblées après classification : une valeur DDIC ne
suffit pas à prouver la consultabilité, et un message de type `E` ne suffit pas
à lui seul à prouver qu'un objet est une structure.

Pour chaque objet, conserver :

- identité : `object_name`, `package`, type de dépôt observé dans `TADIR` ;
- description DDIC : `DD02L-TABCLASS`, état actif et version observés ;
- classe normalisée : `table`, `view`, `non_consultable_ddic` ou `unknown` ;
- résultat SE16 : `selection_screen_reached`, `rejected`,
  `authorization_blocked`, `runtime_error` ou `not_probed` ;
- diagnostic indépendant de la locale : type, identifiant et numéro techniques
  du message quand ils sont disponibles ;
- volumétrie optionnelle : `entry_count` ou motif technique expliquant son
  absence ;
- preuve : horodatage UTC, cible, configuration et statut de la sonde.

Les valeurs brutes de `DD02L-TABCLASS` restent dans l'artefact. Sur A4H, le
domaine en expose quatre (`TRANSP`, `INTTAB`, `VIEW`, `APPEND`). Trois sont
appuyées par une observation : `TRANSP` vers `table` (SCARR, SFLIGHT, SAIRPORT
consultables), `VIEW` vers `view` (SCUS_BOOK), `INTTAB` vers
`non_consultable_ddic` (SFL_AUX, rejet de type `E`). `APPEND` reste **à
vérifier** : aucun objet de cette classe n'a été rencontré dans les deux
packages explorés, donc rien ne permet encore de le classer autrement que
`unknown`. Cette correspondance n'est pas une
constante du produit : chaque cible relit son propre domaine `TABCLASS` avant
de classer, et toute valeur absente du barème reste `unknown`, jamais supprimée
ni forcée dans une classe connue.

## Artefact structuré

Chaque cible produit un document JSON indépendant, trié par `object_name`, avec
le contrat minimal suivant :

```json
{
  "schema_version": 1,
  "target_id": "<cible>",
  "observed_at_utc": "<horodatage>",
  "selection": {
    "packages": [],
    "prefixes": [],
    "max_objects": 0,
    "batch_size": 0
  },
  "summary": {
    "discovered": 0,
    "probed": 0,
    "truncated": false,
    "table": 0,
    "view": 0,
    "non_consultable_ddic": 0,
    "authorization_blocked": 0,
    "unknown": 0
  },
  "objects": []
}
```

L'artefact ne contient ni identifiant utilisateur, ni mot de passe, ni cookie,
ni texte localisé utilisé comme oracle. Un hash SHA-256 du fichier final est
conservé avec les preuves de campagne.

## Scénarios

### 1. Initialiser une campagne en lecture seule

- **Étapes** :
  1. Initialiser une session rf-mcp avec `SapEccLibrary` et `BuiltIn`, en
     décrivant le scénario comme une exploration SAP GUI ou ECC.
  2. Importer `resources/ecc_keywords.resource`.
  3. Ouvrir SAP par le canal d'authentification externe prévu.
  4. Vérifier le scripting et recenser les sessions SAP ouvertes.
  5. Percevoir l'écran initial puis vérifier l'absence de fenêtre modale.
- **Résultat attendu** : une seule session ouverte par la campagne, scripting
  disponible, aucun modal résiduel et aucune donnée modifiée.
- **Critère d'arrêt** : échec du scripting ou présence d'une session non
  attribuable à la campagne. Produire une preuve de blocage puis fermer ce qui
  a été ouvert.
- **Keywords métier manquants** : aucun attendu pour l'initialisation.

### 2. Valider le périmètre configurable

- **Étapes** :
  1. Charger les packages, préfixes et limites de la campagne.
  2. Vérifier qu'au moins un package ou un préfixe est renseigné.
  3. Normaliser les entrées, supprimer les doublons et ordonner les filtres.
- **Résultat attendu** : configuration bornée, déterministe et inscrite dans
  l'artefact avant la première requête DDIC.
- **Critère d'arrêt** : sélection vide, limite absente ou non positive.
- **Keywords métier manquants** : `Validate DDIC Inventory Scope`, pour
  valider et normaliser la configuration sans connaissance métier figée.

### 3. Découvrir les objets DDIC par package et préfixe

- **Étapes** :
  1. Interroger le référentiel des objets à partir des packages configurés.
  2. Ajouter les objets correspondant aux préfixes configurés.
  3. Dédupliquer les résultats et les trier par nom technique.
  4. Appliquer `max_objects` et consigner toute troncature.
- **Résultat attendu** : chaque objet découvert possède un nom technique et sa
  provenance de sélection. Aucun objet hors périmètre n'est ajouté.
- **Critères d'acceptation** :
  - l'union package/préfixe est déterministe ;
  - un objet présent dans plusieurs sélections apparaît une seule fois ;
  - `summary.discovered` correspond au nombre de lignes de l'artefact avant
    sondage ;
  - une limite atteinte produit `truncated=true`, jamais un succès silencieux.
- **Keywords métier manquants** : `Discover DDIC Objects By Scope`, qui doit
  généraliser la découverte existante sans liste de tables métier. Il doit aussi
  rendre le **type d'objet TADIR paramétrable** : la découverte actuelle fige
  `TABL` et ne voit donc aucune vue (écart 2).

### 4. Enrichir et classer les objets avec le DDIC

- **Étapes** :
  1. Lire les attributs actifs des objets découverts dans le DDIC.
  2. Conserver la valeur brute de `DD02L-TABCLASS` et les indicateurs de version.
  3. Appliquer la correspondance de classification validée sur la cible live.
  4. Marquer toute valeur non reconnue comme `unknown`.
- **Résultat attendu** : chaque objet reçoit exactement une classe normalisée,
  tout en conservant les attributs techniques à l'origine de la décision.
- **Critères d'acceptation** :
  - les tables, les vues et les structures/includes non consultables sont des
    classes distinctes ;
  - aucune valeur DDIC nouvelle n'est ignorée ;
  - un objet absent du DDIC est signalé, pas assimilé à une table vide.
- **Keywords métier manquants** : `Classify DDIC Object`, qui retourne un
  dictionnaire JSON-safe et ne dépend d'aucun libellé affiché. Il lit DD02L en
  **sortie de grille** (`TABCLASS` n'est pas un critère de sélection) et
  sélectionne par nom : motif quand le périmètre en a un, sinon sélection
  multiple. Un objet demandé mais absent de la réponse DD02L est signalé comme
  tel, jamais assimilé à une table vide.

### 5. Échantillonner la consultabilité réelle dans SE16

- **Étapes** :
  1. Construire un échantillon déterministe et borné par classe DD02L, sans
    inclure tous les objets découverts.
  2. Pour chaque objet de l'échantillon, tenter d'ouvrir son écran de sélection
    SE16 avec un keyword métier.
  3. Percevoir l'écran et la pile de fenêtres après chaque tentative.
  4. Refermer tout popup avant de poursuivre.
  5. Revenir à un état SE16 connu entre deux objets.
  6. Enregistrer le résultat technique de la sonde.
- **Résultat attendu** :
  - une table ou une vue réellement consultable atteint un écran de sélection ;
  - une structure ou un include peut être classé non consultable seulement si
    la description DDIC et la sonde convergent ;
  - une erreur d'autorisation reste distincte d'un objet non consultable ;
  - un incident technique reste distinct d'un résultat fonctionnel.
- **Critères d'acceptation** : `summary.probed` égale le nombre de sondes
  planifiées et terminées, chaque objet échantillonné possède un résultat, et
  aucune fenêtre modale ne fuit vers la sonde suivante. Aucun comptage ou
  sondage exhaustif n'est lancé sur les objets TADIR.
- **Keywords métier manquants** : `Probe DDIC Object In SE16`, généralisation
  structurée de `Try Open Table Selection Screen`, avec résultat JSON-safe et
  diagnostic technique indépendant de la locale.

### 6. Inspecter les classifications ambiguës dans SE11

- **Étapes** :
  1. Sélectionner uniquement les objets `unknown` ou en désaccord DDIC/SE16.
  2. Ouvrir chaque objet dans SE11 en lecture seule.
  3. Percevoir le type d'objet et les attributs techniques disponibles.
  4. Conserver la preuve sans sauvegarder ni activer l'objet.
- **Résultat attendu** : l'inspection enrichit la preuve, mais ne force pas une
  classe si le constat reste ambigu.
- **Critère d'acceptation** : tout objet encore `unknown` porte un motif et une
  preuve exploitable, jamais une valeur vide.
- **Keywords métier manquants** : `Inspect DDIC Object In SE11`, lecture seule,
  retour JSON-safe.

### 7. Mesurer une volumétrie optionnelle sans rendre la campagne dangereuse

- **Étapes** :
  1. Ne lancer aucun comptage si `measure_entry_count` est désactivé.
  2. Si activé, limiter le comptage à `max_counted_objects` et uniquement aux
     objets déjà déclarés consultables.
  3. Utiliser le comptage SE16 sans ouvrir une extraction complète.
  4. Enregistrer le compte ou le motif technique d'absence.
- **Résultat attendu** : aucun comptage non borné, aucune extraction massive et
  aucune confusion entre zéro ligne, absence d'autorisation et comptage non
  exécuté.
- **Critère d'acceptation** : le nombre de comptages ne dépasse jamais la limite
  configurée. Une troncature est visible dans le résumé.
- **Keywords métier manquants** : `Count Consultable DDIC Objects Within Limit`,
  orchestration bornée autour de `Count Table Entries`.

### 8. Produire l'artefact d'inventaire d'une cible

- **Étapes** :
  1. Vérifier l'unicité des objets et la cohérence des totaux.
  2. Écrire le JSON trié selon le schéma versionné.
  3. Calculer son hash SHA-256.
  4. Conserver le résumé et les preuves de blocage partielles, même si certains
     objets n'ont pas pu être sondés.
- **Résultat attendu** : artefact déterministe, lisible hors SAP et ne contenant
  aucun secret.
- **Critères d'acceptation** : la somme des classes et statuts couvre tous les
  objets, le schéma est valide et deux écritures des mêmes données donnent le
  même contenu hors horodatage explicitement exclu du hash de comparaison.
- **Keywords métier manquants** : `Write DDIC Inventory Artifact`.

### 9. Comparer deux cibles à périmètre équivalent

- **Étapes** :
  1. Charger deux artefacts du même `schema_version`.
  2. Vérifier la compatibilité des packages, préfixes et options de sondage.
  3. Comparer les objets par `object_name`, indépendamment de l'ordre.
  4. Produire les ensembles présents seulement sur A, seulement sur B et
     communs aux deux cibles.
  5. Pour les objets communs, comparer classe DDIC, consultabilité SE16,
     autorisation et volumétrie quand elle existe des deux côtés.
- **Résultat attendu** : rapport structuré distinguant disponibilité,
  reclassement, changement de consultabilité, blocage d'autorisation et écart
  de volumétrie.
- **Critères d'acceptation** :
  - une différence de langue, d'ordre ou d'horodatage ne crée aucun écart ;
  - des périmètres incompatibles bloquent la comparaison ou la marquent
    explicitement non équivalente ;
  - aucune égalité stricte des catalogues n'est exigée entre ECC et S/4HANA ;
  - tous les écarts sont rattachés à un nom technique et aux deux preuves.
- **Keywords métier manquants** : `Compare DDIC Inventory Artifacts`, logique
  pure hors SAP, avec retour JSON-safe et rapport Markdown.

### 10. Fermer la campagne sur tous les chemins

- **Étapes** :
  1. Annuler tout popup inattendu.
  2. Fermer toutes les sessions ouvertes par la campagne.
  3. Vérifier qu'aucun alias créé par la campagne ne reste actif.
- **Résultat attendu** : aucune session SAP GUI orpheline, même après un échec
  d'autorisation, une limite atteinte ou une erreur de sérialisation.
- **Keywords métier manquants** : aucun, utiliser `Close SAP` ou
  `Close All Sap Sessions` dans le teardown.

## Gestion des autorisations et erreurs

- Un échec d'accès à `TADIR` ou `DD02L` bloque l'inventaire global. Produire un
  artefact partiel avec `campaign_status=blocked`, la phase et le diagnostic
  technique, puis fermer la session.
- Un échec d'autorisation sur un objet individuel ne bloque pas les suivants.
  Classer l'issue `authorization_blocked`, sans conclure que l'objet est absent
  ou non consultable.
- Un message de type `E` est une preuve d'échec, pas une cause suffisante. La
  cause s'appuie sur les attributs DDIC et, si disponible, l'identifiant et le
  numéro techniques du message.
- Un popup inattendu est perçu, consigné et annulé avant toute nouvelle action.
- Aucun texte localisé n'est une assertion. Les noms d'objets, champs DDIC,
  types de messages et statuts structurés sont les ancres stables.

## Limites et volumétrie

- `max_objects` est obligatoire et s'applique après déduplication et tri.
- `batch_size` crée des points de reprise déterministes et limite la perte en
  cas de coupure.
- La découverte et le sondage ont des compteurs séparés.
- Les objets non sondés à cause d'une limite restent dans le résumé avec
  `not_probed`, ils ne disparaissent pas.
- Le comptage de lignes est optionnel, borné séparément et désactivé par défaut.
- Les durées et seuils numériques définitifs doivent être calibrés pendant la
  prochaine exploration live. Aucun SLA n'est inventé dans ce plan bloqué.

## Preuves à conserver

Pour chaque cible :

- configuration normalisée de campagne ;
- résultat du préflight scripting et inventaire initial des sessions ;
- première perception complète, puis diffs après les changements d'écran ;
- pile de fenêtres pour chaque catégorie d'échec rencontrée ;
- valeurs DDIC brutes ayant déterminé chaque classe ;
- statuts techniques des sondes SE16 et inspections SE11 ;
- artefact JSON, résumé Markdown et hash SHA-256 ;
- journal des objets tronqués, non sondés, ambigus ou bloqués par autorisation ;
- confirmation de fermeture des sessions ouvertes par la campagne.

Les captures peuvent documenter un exemple de chaque comportement, mais elles
ne remplacent ni l'artefact structuré ni les assertions techniques.

## Keywords candidats à vérifier live

Les keywords suivants sont connus du projet mais n'ont pas été appelés dans la
campagne bloquée :

| Keyword | Usage prévu | Statut de cette campagne |
|---|---|---|
| `Open SAP And Log In` | ouverture de la cible | exécuté, A4H/001/EN |
| `Scripting Should Be Fully Enabled` | préflight | succès |
| `List Sap Sessions` | détection des sessions résiduelles | exécuté |
| `Get Screen Map` | perception initiale et pilotage interactif | exécuté via rf-mcp |
| `Get Screen Signature` | perception différentielle | exécuté via rf-mcp |
| `Get Open Windows` | détection des modaux | exécuté via rf-mcp |
| `List Repository Tables` | point de départ de la découverte | 27 + 56 objets observés |
| `Try Open Table Selection Screen` | sonde SE16 ciblée | 2 succès, 2 rejets de type E |
| `Count Table Entries` | volumétrie optionnelle | succès sur `SAIRPORT` (53) et `SAPLANE` (34) |
| `Display Table Contents With Filter` | lecture DD02L | inutilisable tel quel, voir ci-dessous |
| `Read Domain Values` | catalogue des valeurs de classification | `TABCLASS` et `AS4LOCAL` relevés |
| `Count Entries On Current Selection Screen` | comptage sur écran déjà ouvert | exécuté, y compris sur TADIR filtré |
| `Read Column Values From Displayed Grid` | lecture ciblée d'une colonne | exécuté sur `OBJ_NAME` |
| `Close SAP` | fermeture garantie | exécuté, aucun processus résiduel |

Deux limites relevées sur la couche resource existante, à traiter par
sap-generator :

- `Display Table Contents With Filter` exige un dictionnaire
  `<TABLE>_SELECTION_FIELDS`. Aucun n'existe pour DD02L, et un dictionnaire ne
  suffirait pas : la classification a besoin d'une **liste** de noms, que seule
  la sélection multiple exprime. Le keyword métier manquant doit donc piloter la
  modale de sélection multiple, pas se contenter d'un critère par champ.
- `List Repository Tables` fige `OBJECT=TABL` : voir l'écart 2.

## Points de vigilance

- La campagne n'utilise aucune liste métier fixe. `TADIR` et `DD02L` sont les
  sources techniques de découverte et de classification, pas une liste de
  tables à tester.
- Les références `@N` de `Get Screen Map` sont réservées au pilotage live. Elles
  ne figurent jamais dans une suite générée ni dans l'artefact.
- Un écran de sélection atteint prouve la consultabilité du chemin SE16, pas la
  présence de données.
- Une table vide reste consultable. Elle ne doit pas être confondue avec une
  structure, une absence d'objet ou une autorisation manquante.
- Une vue reste distincte d'une table même si les deux sont consultables dans
  SE16.
- Le balayage SE16 objet par objet n'est pas le moteur de classification, mais
  la raison n'est pas qu'un objet ferait tomber la campagne : `SAPLANE`, cité
  comme tel en passe 1, s'ouvre et se compte normalement (écart 1). La raison
  est que DD02L classe une liste entière en un appel, sans ouvrir ni refermer
  une fenêtre par objet.
- Un écran de sélection SE16 n'expose pas tous les champs de la table : le champ
  client et les champs `FLTP` en sont retirés en silence. Ne jamais déduire la
  structure d'une table de son écran de sélection ; DD03L est la source.
- Les objets historiques propres à ECC doivent rester classables sans supposer
  qu'ils existent sur S/4HANA. Les valeurs DDIC inconnues restent visibles.
- `Run Transaction` doit toujours être suivi d'une perception réelle et d'un
  contrôle des fenêtres ouvertes.
- Aucun `Sleep` ni attente fixe. Utiliser les waits de SapEccLibrary.
- Un seul processus rf-mcp pilote la session ECC live.

## Handoff sap-generator

La porte n°1 de la passe 1 (relever live le mapping de sélection et les colonnes
de sortie de DD02L) est **franchie** : les ids et les colonnes sont dans
« Passe 2 » ci-dessus, et le generator les reprend sans re-sonder, à charge pour
lui de les re-vérifier sur toute cible qui ne serait pas A4H.

La génération du MVP est autorisée avec les portes suivantes :

1. trancher les deux écarts avant d'écrire : soit la découverte devient
  paramétrable en types d'objets TADIR et la classe `view` est couverte, soit
  la classe `view` sort du modèle. Ne pas laisser une classe que le code ne
  peut jamais produire ;
2. conserver TADIR pour la sélection bornée, puis joindre DD02L pour la
  classification active. Le join se fait par motif de nom quand le périmètre en
  a un (`SNWD*`), et par **sélection multiple** sinon : c'est ce second chemin
  qui rend la campagne indépendante d'un préfixe commun, et c'est lui qui doit
  exister en keyword métier ;
3. produire un artefact JSON déterministe par cible, sans secret, et tester sa
  comparaison hors SAP ;
4. ne lancer aucun comptage de lignes par défaut et ne jamais sonder tous les
  objets dans SE16 ;
5. limiter la preuve SE16 à un échantillon configurable de classes sûres, avec
  nettoyage des fenêtres après chaque objet ;
6. créer les keywords métier manquants dans `resources/page_objects/`, leurs
  tests unitaires hors SAP, puis la suite sous `tests/robot/ui/ecc/` ;
7. exécuter chaque étape live avant écriture et fermer toutes les sessions,
  même en cas d'échec ;
8. stampiller la suite avec ce plan après génération.

**Décision ouverte, à trancher à la génération** : où vit la logique pure
(assemblage de l'artefact, hash, comparaison, rapport Markdown). Deux options
assumées, aucune n'est neutre. `src/sapfx_common/ddic_inventory.py` la met sur
le pythonpath des suites du dépôt comme du pack, aux côtés de `screen_watch` et
`visual_baseline`, mais en fait une surface produit publiée (wheel, CHANGELOG,
docs, engagement de compatibilité). Un module rangé avec la campagne évite cet
engagement, au prix de la réutilisabilité. Le critère de choix : la comparaison
de deux cibles est-elle réellement exercée, ou reste-t-elle théorique faute d'un
second système. Aujourd'hui, aucune cible ECC distincte n'est disponible.

L'inspection SE11 des objets `unknown` reste une extension. Elle ne bloque pas
le MVP si l'artefact conserve la valeur brute DD02L et un motif explicite.
