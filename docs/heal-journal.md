# Journal de guérison (heal journal)

Mémoire des dérives réparées par l'agent **sap-healer** : une entrée par
session de réparation ayant modifié au moins un fichier.

**Ce journal n'est pas un doublon de `SAPFX_HEALING_LOG`.** La télémétrie
(JSONL cumulatif, alimenté par le *runtime* via `sapfx_common.healing_telemetry`,
exploité par `scripts/healing_drift_report.py`) enregistre mécaniquement *ce
que la bibliothèque a réparé toute seule*, run après run : elle répond à la
question « **quel localisateur dérive, et à quelle fréquence ?** ». Ce journal
enregistre ce que l'**agent** a conclu : la classe de panne, la preuve live qui
a tranché, et la leçon d'ancrage à transmettre ; il répond à « **pourquoi, et
qu'est-ce qu'on en fait ?** ».

Les deux se complètent : `healing_drift_report.py` détecte les dérives stables
et propose le patch ; le journal explique le diagnostic et oriente les
prochaines passes de **sap-planner**, qui le lit avant d'écrire ses notes de
localisation. Des entrées récurrentes sur le même écran ou la même famille
d'ancres (ids renumérotés à chaque transport, id non unique, contrôle UI5
mouvant) signalent qu'une ancre plus stable s'impose à cet endroit : sur ECC,
typiquement une ancre par **libellé visible** (`Find Element By Label`,
`Resolve Element With Healing … label=…`), qui survit à la renumérotation des
sous-écrans.

Format d'une entrée (append-only, la plus récente en haut) :

```markdown
## AAAA-MM-JJ : <suite>.robot
- **Classe** : locator drift | timing | data drift | changement fonctionnel
- **Réparation** : `<fichier>` : `avant` → `après` (une ligne par changement)
- **Preuve** : <l'observation live qui a justifié la réparation>
```

---

## 2026-08-17 : exploratory_campaign_a4h.robot

- **Classe** : data drift (dérive d'ENVIRONNEMENT : depuis la re-création du
  conteneur A4H du 2026-08-01, SE16 régénère chaque écran de sélection au
  premier accès ; sur SGEOCITY cette régénération émet un DIALOGUE modal
  d'information au lieu d'un message de barre de statut). Ni localisateur ni
  flux métier n'ont changé.
- **Réparation** (suite AUTONOME : sa couche keywords locale est la couche
  réparée, dérogation documentée dans son en-tête, `resources/` intouché) :
  - `tests/robot/exploratory_campaign_a4h.robot` : nouveau keyword
    `Dismiss Message Dialog If Present` (détection STRUCTURELLE : fenêtre
    modale + champs `txtMESSTXT<n>`, texte relevé pour le journal, refermé par
    Entrée) + variable `${SE16_DIALOG_TEXT_PREFIX}` = `wnd[1]/usr/txtMESSTXT`.
  - `Open Table In SE16` : `contrôle type E seul` → `contrôle type E, puis
    dialogue refermé et journalisé, puis attente de l'écran de sélection
    (txtMAX_SEL)` ; écran jamais atteint après dialogue = échec explicite
    citant le texte relevé.
  - `Classify And Count Table` : `verdicts table | structure` → `verdicts
    table | structure | dialog` (3e verdict : écran de sélection jamais
    atteint après dialogue refermé, jamais mis en échec) ; la garde du jour
    (attente txtMAX_SEL, cas SAPLANE) conservée telle quelle dans la branche
    sans dialogue.
  - `Deep Verify Package Catalog` : compteur `dialogs` + liste des rejets dans
    le récap et le dictionnaire de stats.
  - Test « Flight Data Tables Are Accessible And Populated » : SGEOCITY
    CONSERVÉE dans la liste attendue (le dialogue est informatif, la table
    reste consultable et peuplée : la retirer aurait réduit la couverture,
    tolérer un verdict « rejeté » aurait affaibli l'assertion).
- **Preuve** : perception rf-mcp live vs A4H (2026-08-17) : SE16 → SGEOCITY →
  Entrée ouvre `wnd[1]` GuiModalWindow « Information » (écran SAPMSDYP/SE16/10)
  au texte « ABAP Dictionary type FLTP is not allowed for dynpro element »
  (SGEOCITY porte des champs FLTP, latitude/longitude) ; Entrée sur wnd[1]
  referme le dialogue et « Data Browser: Table SGEOCITY: Selection Screen »
  s'ouvre derrière ; « Number of Entries » répond 62. Re-run complet après
  patch : 4/4, SGEOCITY comptée 62 (deux tests), 0 rejet par dialogue.

**Leçon d'ancrage (pour sap-planner)** : après une re-création du conteneur,
TOUS les écrans de sélection SE16 sont régénérés au premier accès. La plupart
des tables l'annoncent dans la barre de statut (`Program /1BCDWB/DB<table>
does not exist yet in library`, type non bloquant) ; une table à champs FLTP
l'annonce par un dialogue MODAL que le contrôle du type de statut ne voit pas
(type vide) et qui bloque le chargement de l'écran tant qu'il n'est pas
refermé. Ancrage : après l'Entrée sur un nom de table, contrôler la PILE DE
FENÊTRES (`Get Open Windows`, `modal=True`), pas seulement la barre de statut ;
un dialogue de message se reconnaît structurellement (champs `MESSTXT`), jamais
par son texte localisé. Corollaire : le dialogue disparaît une fois le dynpro
généré ; un run qui ne le referme jamais le rencontre en boucle, un run sain ne
le voit qu'une fois par génération (d'où une re-validation verte SANS dialogue
juste après la session de perception qui l'a refermé).

## 2026-07-25 : travel_processor_consultation_liste.robot

> **Provenance : dérive SIMULÉE**, injectée volontairement dans le page object
> pour évaluer le sap-healer **en aveugle** (validation de la version 0.6.2, le
> harnais `scripts/agent_eval_harness.py` exigeant un A4H alors indisponible).
> Ce n'est PAS un incident réel : le sap-generator avait relevé le bon suffixe.
> L'entrée est conservée parce que le diagnostic et la leçon d'ancrage, eux,
> ont été produits en live et restent valables.

- **Classe** : locator drift (localisateur inexistant sur l'écran : le page
  object divergeait de la spec, pas une évolution de l'app)
- **Réparation** : `resources/page_objects/fiori_travel_list.resource` :
  `${TRAVEL_HEADER_TITLE}` = `fe::table::Travel::LineItem-titleInfo` →
  `fe::table::Travel::LineItem-title`
- **Preuve** : balayage live du registre UI5 de l'app (cap-sflight, rf-mcp
  Browser + SapFioriLibrary) ; un seul contrôle porte le compteur :
  `sap.fe.cap.travel::TravelList--fe::table::Travel::LineItem-title`
  (`sap.m.Title`, texte « Voyages (4 133) », visible) ; `…-titleInfo` → **0
  match**. Après patch, `Get Ui5 Text` lit « Voyages (4 133) » puis
  « Voyages (91) » après recherche « Aussie » : le cycle du plan.

**Leçon d'ancrage (pour sap-planner)** : sur cette List Report Fiori Elements,
le compteur d'en-tête de la table MDC s'ancre sur le suffixe `…LineItem-title`
(unique sur la page : c'est le seul id qui se termine par `-title`). Ne pas
confondre avec l'agrégat `-titleInfo`, qui **n'est pas instancié** dans cette
variante. Corollaire de méthode : un suffixe d'id FE doit être **relevé dans le
registre live**, jamais déduit d'une convention de nommage ; ici les trois
sources (spec, page object, écran) divergeaient, et seule la spec était juste.
Aucune entrée `SAPFX_HEALING_LOG` n'a été produite : ce localisateur est
consommé par un `Resolve Ui5 Control` nu, hors chaîne de fallback : le runtime
n'avait donc rien à réparer ni à journaliser (dérive invisible à
`healing_drift_report.py` jusqu'à l'échec).
