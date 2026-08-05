> [🇬🇧 English](sap-test-data.md) · **🇫🇷 Français**

# Données de test & cibles de test SAP

Inventaire vérifié (veille web : 06/07/2026) des jeux de données SAP et des cibles
de test publiques sur lesquels ce projet peut s'appuyer, et de ceux qu'il ne doit
**pas** utiliser. Complète [testing-without-sap.fr.md](testing-without-sap.fr.md)
(comment obtenir un système) en répondant à *quoi tester une fois le système obtenu*.

## 1. Données de démo dans l'ABAP Platform Trial (A4H 1909)

Le trial n'a **aucune transaction métier ERP** (FB01, MM03, VA01… sont absentes par
conception : [FAQ officielle](https://github.com/SAP-docs/abap-platform-trial-image/blob/main/faq-v7.md)).
Il embarque en revanche trois modèles de données de démo, tous utilisables comme
cibles stables de tests smoke :

| Modèle | Tables | Générer / réinitialiser |
|--------|--------|-------------------------|
| **Flight Reference Scenario (RAP)** | `/DMO/*` | Pré-généré dans le trial ; régénération via la classe `/DMO/CL_FLIGHT_DATA_GENERATOR` (SE24 / console ADT) |
| **SFLIGHT classique** | `SPFLI`, `SFLIGHT`, `SBOOK`, `SCARR`… | SE38 → rapport `SAPBC_DATA_GENERATOR` (supprime puis régénère, taille paramétrable) |
| **EPM (Enterprise Procurement Model)** | `SNWD_*` (ex. `SNWD_PO`) | Transaction `SEPM_DG` (rapport `SEPM_DG_EPM_STD_CHANNEL`) |

Transactions sûres pour les smokes : `SE16`, `SE38`/`SA38`, `SE80`, `SE11`,
`SE24`, `SM50`, `SU01`, `SLICENSE`. Motif recommandé : un mot-clé de setup de suite
qui lance le générateur de données, puis des lectures `SE16` sur `SFLIGHT`/`SNWD_PO`
(des grilles garanties non vides).

**Validé en live sur A4H (07/2026)**, implémenté dans
`resources/a4h_demo_data.resource` + `tests/robot/ecc_data_smoke.robot` (4/4) :

- **`SE16N` n'existe pas sur A4H** (« Transaction SE16N does not exist »).
- **La sortie par défaut de SE16 est la liste ABAP classique** (aucun objet grille
  scriptable). Basculer une fois le mode de sortie de l'utilisateur (Réglages →
  Paramètres utilisateur → *ALV Grid Display*, mot-clé
  `Use ALV Grid In Data Browser`) et `wnd[0]/usr/cntlGRID1/shellcont/shell`
  apparaît.
- Faire les assertions sur les **ids techniques de colonnes** (`CARRID`, `PO_ID`)
  via `Get Grid Column Ids`, jamais sur les titres affichés (dépendants de la locale).

**La Gateway embarquée de l'A4H est vivante elle aussi** (vérifié live le
13/07/2026) : le catalogue OData répond sur le port HTTP du conteneur, à
`http://vhcala4hci:50000/sap/opu/odata/iwfnd/CATALOGSERVICE;v=2/ServiceCollection`
(auth basic DEVELOPER, `sap-client=001`), avec les **services de référence
EPM déjà activés** : `SEPMRA_SHOP`, `SEPMRA_PROD_MAN`, `SEPMRA_SO_MAN`,
`SEPMRA_PO_MAN`… `SEPMRA_SHOP/Products/$count` retourne le nombre de lignes de
`SNWD_PD` (205 avec les données `SEPM_DG` standard). L'A4H devient ainsi une
cible **GUI + API** sur un même système, le socle de
`tests/robot/flagship_cross_paradigm.robot` (compte SE16 == `$count` OData,
validé live) via `SapApiLibrary`.

## 2. Cibles de test Fiori / UI5 publiques

- **OpenUI5 Demo Kit, vivant** (notre cible smoke actuelle) : <https://sdk.openui5.org/> ;
  l'exemple Shopping Cart répond sur
  `test-resources/sap/m/demokit/cart/webapp/index.html` (aussi sur <https://ui5.sap.com/> ;
  nota : `sapui5.hana.ondemand.com` redirige désormais en 301 vers ce dernier).
- **SAP Gateway Demo ES5 (`sapes5.sapdevcenter.com`) : MORT.** Décommissionné fin
  octobre 2025 ([annonce SAP](https://community.sap.com/t5/technology-blog-posts-by-sap/sap-gateway-demo-system-will-be-de-commissioned/ba-p/13353480)).
  Ne rien construire sur ES5 / `GWSAMPLE_BASIC`.
- **OData public pour fixtures** : Northwind V4 / TripPin sur
  <https://services.odata.org/> (vérifié vivant) : flux en lecture seule pour des
  fixtures UI5 locales ; le `MockServer` intégré d'UI5
  (`sap.ui.core.util.MockServer`) simule un service OData V2 depuis `metadata.xml`
  et des fichiers JSON, de façon déterministe et hors ligne.

## 3. Cible Fiori Elements locale : cap-sflight

[SAP-samples/cap-sflight](https://github.com/SAP-samples/cap-sflight) (activement
maintenu) livre deux vraies apps **Fiori Elements** (Travel processor, Analytical
List Page) sur un backend CAP : le meilleur moyen d'exercer `SapFioriLibrary` sur
des tables/filtres/object pages FE **sans backend SAP et sans réseau** :

```bash
npm i -g @sap/cds-dk
git clone https://github.com/SAP-samples/cap-sflight && cd cap-sflight
npm ci && cds watch          # → http://localhost:4004/
```

Le service OData **v4** du même process (`/processor/Travel`, `$count`
disponible) se recoupe avec l'UI pour des vérifications croisées Fiori↔API
(le volet `capsflight` de la suite flagship). **Blocage connu (constaté le
13/07/2026)** : avec `@sap/cds-dk` 9.9 + `cds-plugin-ui5` 0.17, le clone local
se fige au montage des apps UI5 au démarrage, et sans le plugin le serveur CAP
accepte le TCP mais ne répond jamais. Rafraîchir le clone (`git pull &&
npm ci`) avant de s'y fier ; `fiori_sflight_smoke.robot` est touché de la
même façon d'ici là.

## 4. Veille plateforme (au 07/2026)

- **L'image A4H 1909 est aujourd'hui irremplaçable** : `sapse/abap-cloud-developer-trial`
  a disparu de Docker Hub (trial 2023 retiré ; un trial 2025 est annoncé mais pas
  encore publié). **Sauvegarder l'image locale** (`docker save`) et continuer à
  renouveler la licence minisap de 3 mois via
  <https://go.support.sap.com/minisap/#/minisap> (import dans `SLICENSE`).
  Détails dans [ecc-validation.fr.md](ecc-validation.fr.md).
- **SAP GUI for Windows 8.10** sort le 16/07/2026 : **API COM de scripting
  inchangée** (seul ajout : JScript comme langage d'enregistrement), migration donc
  sans risque attendue pour `SapEccLibrary` ; repasser `ecc_smoke.robot` après mise
  à jour du poste. Fin de support restreint de SAP GUI 8.00 : 31/07/2027. Référence
  API : [SAP GUI Scripting API sur le Help Portal](https://help.sap.com/docs/r/b47d018c3b9b45e897faf66a6c0885a8/latest/en-US).
- **Écosystème** : l'upstream `robotframework-sapguilibrary` est dormant (dernière
  release en 2022 : notre fork vendorisé est de facto la ligne de maintenance) ;
  [playwright-sap](https://github.com/ArpitSureka/playwright-sap) est maintenu
  (v1.1.4, 10/2025), re-diff périodique de notre port `_ui5_js.py` conseillé ;
  [rf-mcp](https://pypi.org/project/rf-mcp/) est en 0.35.0 (les séries
  0.32/0.33 n'existent pas) : notre intégration est re-validée contre elle
  (contrats de plugins inchangés depuis la 0.31.2 ; fenêtre du garde de la
  surcouche 0.31–0.35 dans `sap_robotmcp/_compat.py`) ; surveiller les séries
  suivantes pour les contrats de plugins.

## 5. Compatibilité des bibliothèques selon les versions SAP (validé 07/2026)

| Cible | État |
|-------|------|
| ECC 6.0 / R/3 (SAP GUI 7.x/8.x) | ✅ Même API COM Scripting côté client (stable depuis ~6.20/2002) ; exige `sapgui/user_scripting=TRUE`. Réserve : la couche grille « par titre » ne couvre que l'ALV **GridView** ; les écrans à `GuiTableControl` classique retombent sur les keywords upstream. Non testé physiquement sur ECC 6.0. |
| S/4HANA on-premise (GUI) | ✅ Prouvé live (A4H 1909, `ecc_smoke` + `ecc_data_smoke`). |
| SAP GUI for Windows 8.10 (16/07/2026) | ✅ API COM inchangée : migration sans risque attendue. |
| UI5 ≥ 1.67 + Fiori Elements v4 | ✅ Prouvé live (OpenUI5 Demo Kit, cap-sflight). |
| UI5 < 1.67 (launchpads pré-2019 : S/4 1610/1709, UI5 1.44/1.52/1.60) | ✅ Repli DOM `registryForEach`, **prouvé live contre un vrai OpenUI5 1.60.14** (`fiori_legacy_smoke.robot`, miroir npm jsDelivr). |
| UI5 2.x (**abandonné** depuis la keynote UI5con de juillet 2026 : aucune release 2.0 prévue ; la voie officielle SAP est la ligne 1.x legacy-free) | ✅ **Prouvé live contre le CDN nightly 2.0** (`fiori_ui5v2_smoke.robot`, `sdk.openui5.org/nightly/2`) : branche module `ElementRegistry`, zéro dépendance aux APIs supprimées en 2.x (`sap.ui.getCore()`, `Element.registry`, `sap.ui.version`). Également verrouillé par `tests/unit/test_ui5_compat.py`. Le smoke reste une **sentinelle non bloquante** tant que le CDN nightly/2 est servi (il peut être gelé ou retiré) ; le smoke 1.136-legacy-free ci-dessous est la cible d'avenir. |
| Iframes de launchpad (SAP Build Work Zone / cFLP) | ✅ `Set Ui5 Frame` : bundle évalué dans la frame, sélecteurs à perçage de frame `>>>` ; prouvé contre une fixture réellement cross-origin (`fiori_frame_smoke.robot`). |
| S/4HANA Cloud (édition publique) | ✅ Fiori + moteur WebGUI `sid` (pas de SAP GUI desktop) ; noter que la page de login IAS/SAML n'est **pas** du UI5 → la piloter avec des keywords Browser purs. |
