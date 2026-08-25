> [🇬🇧 English](testing-without-sap.md) · **🇫🇷 Français**

# Tester sans système SAP

Vous pouvez progresser concrètement sur ce projet avec **zéro accès SAP**. Trois niveaux,
du « fonctionne immédiatement » à la « haute fidélité complète ».

## Niveau 1 : logique pure, sans SAP, sans COM Windows (aujourd'hui)

La logique ajoutée par le fork (attentes, réessais, grille par titre, détection d'erreurs de transaction)
est testée unitairement contre des **faux objets COM** :

```bash
pip install pytest
python -m pytest tests/unit -q
```

`tests/unit/conftest.py` remplace par des bouchons les modules `robot.*` et pywin32 lorsqu'ils sont
absents, de sorte que ces tests s'exécutent sur un interpréteur nu (même hors Windows). Installez les vraies
dépendances (`pip install -r requirements.txt`) et les mêmes tests s'exécutent contre les vraies
bibliothèques. Cela valide la **structure du code et la logique**, pas la navigation en direct.

## Niveau 2 : navigation SAP GUI réelle, entièrement locale (recommandé)

**ABAP Platform Trial en image Docker** (licence développeur gratuite, à renouveler ~trimestriellement).
Un vrai backend SAP sur votre machine ; connectez-y un SAP GUI local et l'API Scripting
pilote un système authentique. **Procédure détaillée pas-à-pas : [ecc-validation.fr.md](ecc-validation.fr.md).**

- **Disponibilité, vérifiée le 2026-08-23** : SAP a **arrêté** ce trial.
  `sapse/abap-cloud-developer-trial` ne figure pas parmi les 23 dépôts publics
  du namespace `sapse` et l'API Docker Hub répond 404 ; SAP a fait dépublier un
  miroir communautaire en mai 2026 (l'image est sous licence d'usage personnel,
  non redistribuable) ; et les anciennes AS ABAP developer editions sont
  **retirées de Docker Hub ET de SAP CAL le 30 septembre 2026**, donc le repli
  CAL que cette page recommandait disparaît aussi. Si vous détenez déjà une
  image, gardez-la : un `docker save` vers un disque externe est la seule
  continuité garantie. Ce qui reste librement accessible avec un simple compte
  SAP : le **trial SAP BTP** (90 jours, environnement ABAP avec RAP et Fiori
  Elements, Build Work Zone, un IAS réel) et le **bac à sable SAP Business
  Accelerator Hub** (api.sap.com, OData v2 et v4 de S/4HANA Cloud, clé d'API en
  en-tête). Aucun des deux n'offre de SAP GUI, donc aucun ne peut exercer
  `SapEccLibrary`.
- Prérequis : **~16 Go de RAM minimum** (32 Go confortable), ~150 Go de disque.
- **Figez l'adresse MAC à la création** (`docker run --mac-address …`). La clé
  matérielle SAP en dérive, et depuis Docker 29 un conteneur non épinglé en tire
  une nouvelle à **chaque démarrage** : la licence demandée hier est caduque ce
  matin. Mesuré sur un second système : clé `Y1778494144` sans épinglage,
  `H0425704182` une fois épinglée, puis stable sur un cycle arrêt/démarrage
  complet.
- Activez le scripting une fois le système démarré :
  - Serveur : écrivez les paramètres dans le **profil d'instance**
    (`/sapmnt/<SID>/profile/<SID>_D00_<hôte>`), et non par `RZ11`. Un réglage
    `RZ11` est perdu au prochain arrêt de l'instance, ce qui compte si vous
    éteignez le conteneur tous les soirs :
    `sapgui/user_scripting = TRUE`,
    `sapgui/user_scripting_disable_recording = FALSE`,
    `sapgui/user_scripting_set_readonly = FALSE`. Gardez un `.bak` du profil et
    redémarrez l'instance pour qu'il soit lu.
  - Client : Options SAP GUI → Accessibilité & Scripting → Scripting → activer, et
    décocher les deux cases « notifier lorsqu'un script… » pour que les boîtes de dialogue ne bloquent pas l'automatisation.
- **Les premiers appels sont lents, et un timeout n'est pas un verdict.** Sur un
  système fraîchement démarré, le premier appel OData à chaque service en
  déclenche le chargement côté serveur et peut dépasser le délai par défaut du
  client : cela se présente en `unreachable` ou `TimeoutError` et oriente vers
  la connectivité, où il n'y a rien à trouver. Mesuré : 2,2 s au premier appel
  du catalogue, 0,1 s au deuxième. Rejouez avant de diagnostiquer.
- Pointez ensuite `Open Sap Logon` / `Connect To Session` dessus et exécutez
  `tests/robot/ecc_smoke.robot`.

C'est l'**option meilleur rapport qualité-coût** pour la bibliothèque ECC : navigation réelle,
sans frais d'hébergement récurrents.

## Niveau 3 : scénarios S/4HANA complets (occasionnel)

**SAP Cloud Appliance Library (CAL)** : appliances gratuites de 30 jours pour des systèmes complets
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
| Navigation ECC GUI réelle | ABAP Platform Trial Docker (**arrêté par SAP, voir plus haut**) | gratuit + votre matériel |
| Scénarios S/4HANA complets | SAP CAL (30 jours ; les anciennes éditions ABAP quittent CAL le 2026-09-30) | hébergement cloud uniquement |
| Launchpad Fiori réel, login IAS réel | Trial SAP BTP (90 jours, **pas de SAP GUI**) | gratuit, compte requis |
| OData v2 et v4 S/4HANA Cloud réels | Bac à sable api.sap.com (clé d'API en en-tête) | gratuit, compte requis |
| Localisateurs Fiori / web | OpenUI5 Demo Kit | gratuit |
