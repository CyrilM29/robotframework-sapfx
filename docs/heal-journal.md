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
