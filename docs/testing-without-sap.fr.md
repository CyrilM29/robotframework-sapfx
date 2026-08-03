> [🇬🇧 English](testing-without-sap.md) · **🇫🇷 Français**

# Tester sans système SAP

Vous pouvez progresser concrètement sur ce projet avec **zéro accès SAP**. Trois niveaux,
du « fonctionne immédiatement » à la « haute fidélité complète ».

## Niveau 1 — Logique pure, sans SAP, sans COM Windows (aujourd'hui)

La logique ajoutée par le fork (attentes, réessais, grille par titre, détection d'erreurs de transaction)
est testée unitairement contre des **faux objets COM** :

```bash
pip install pytest
python -m pytest tests/unit -q
```

`tests/unit/conftest.py` remplace par des bouchons les modules `robot.*` et pywin32 lorsqu'ils sont
absents, de sorte que ces tests s'exécutent sur un interpréteur nu (même hors Windows). Installez les vraies
dépendances (`pip install -r requirements.txt`) et les mêmes tests s'exécutent contre les vraies
bibliothèques. Cela valide la **structure du code et la logique** — pas la navigation en direct.

## Niveau 2 — Navigation SAP GUI réelle, entièrement locale (recommandé)

**ABAP Platform Trial — image Docker** (licence développeur gratuite, à renouveler ~trimestriellement).
Un vrai backend SAP sur votre machine ; connectez-y un SAP GUI local et l'API Scripting
pilote un système authentique. **Procédure détaillée pas-à-pas : [ecc-validation.fr.md](ecc-validation.fr.md).**

- Récupérez l'image `sapse/abap-cloud-developer-trial:<TAG>` **si disponible** — en
  2026 elle semble retirée (404) de Docker Hub ; dans ce cas, utilisez **SAP CAL**
  (`cal.sap.com`). Procédure complète : [ecc-validation.fr.md](ecc-validation.fr.md).
- Prérequis : **~16 Go de RAM minimum** (32 Go confortable), ~150 Go de disque.
- Activez le scripting une fois le système démarré :
  - Serveur : transaction `RZ11` → définir `sapgui/user_scripting = TRUE` (et
    `sapgui/user_scripting_per_user` selon les besoins).
  - Client : Options SAP GUI → Accessibilité & Scripting → Scripting → activer, et
    décocher les deux cases « notifier lorsqu'un script… » pour que les boîtes de dialogue ne bloquent pas l'automatisation.
- Pointez ensuite `Open Sap Logon` / `Connect To Session` dessus et exécutez
  `tests/robot/ecc_smoke.robot`.

C'est l'**option meilleur rapport qualité-coût** pour la bibliothèque ECC : navigation réelle,
sans frais d'hébergement récurrents.

## Niveau 3 — Scénarios S/4HANA complets (occasionnel)

**SAP Cloud Appliance Library (CAL)** — appliances gratuites de 30 jours pour des systèmes complets
(S/4HANA, ABAP Platform). Le logiciel est gratuit ; vous payez l'**hébergement cloud**
(AWS/Azure/GCP) pendant que la VM tourne. À utiliser pour les scénarios métier de bout en bout que vous ne pouvez pas
reproduire sur l'image d'essai. **SAP BTP Trial / Free Tier** fournit un Fiori
Launchpad hébergé pour la partie web.

## Côté web / Fiori (phase 2)

Aucun accès SAP requis : l'**OpenUI5 Demo Kit** (`sdk.openui5.org`) et ses
applications exemples (Shopping Cart, Worklist) rendent les *mêmes* contrôles SAPUI5 qu'un vrai
S/4HANA, de sorte que la stratégie de localisation web et l'intégration du recorder UI5 peuvent être construites
et testées entièrement sur des pages de démonstration publiques.

## Récapitulatif

| Besoin | Utiliser | Coût |
|--------|----------|------|
| Valider la logique du fork maintenant | `pytest tests/unit` (faux COM) | gratuit, instantané |
| Navigation ECC GUI réelle | ABAP Platform Trial Docker | gratuit + votre matériel |
| Scénarios S/4HANA complets | SAP CAL (30 jours) | hébergement cloud uniquement |
| Localisateurs Fiori / web | OpenUI5 Demo Kit | gratuit |
