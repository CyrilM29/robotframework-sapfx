# Démarrer : lancer, ranger, passer un secret

## Lancer

```bash
robot --pythonpath src --dryrun --outputdir results/dry tests/robot/   # résolution des keywords, sans SAP
robot --pythonpath src -v SAP_CONNECTION:"/H/hôte/S/3200" -v SAP_USER:DEVELOPER \
      -v "SAP_PASSWORD: Secret:…" tests/robot/ecc_smoke.robot          # ECC live
robot --pythonpath src tests/robot/fiori_smoke.robot                    # Fiori, aucune cible SAP requise
robot --pythonpath src -v API_USER:… -v "API_PASSWORD: Secret:…" --include a4h \
      tests/robot/api/canal_api_odata.robot                             # canal OData
robot --pythonpath src -v "RFC_PASSWORD: Secret:…" --include rfc \
      tests/robot/api/canal_rfc_a4h.robot                               # canal RFC (se saute proprement sans pyrfc)
```

Le `--dryrun` est le premier réflexe après avoir écrit une suite : il attrape
les keywords inexistants et les arguments manquants sans toucher au système.

Prérequis par canal : ECC exige SAP GUI for Windows et le scripting activé
(serveur ET poste, voir `docs/hardening-test-environment.md`) ; Fiori exige
`rfbrowser init` une fois ; RFC exige `pyrfc` sous un interpréteur 3.10 à 3.12.

## Squelettes minimaux

ECC (SAP GUI) :

```robotframework
*** Settings ***
Resource          resources/ecc_keywords.resource     # votre copie adaptée à la cible
Suite Setup       Open SAP And Log In
Suite Teardown    Close SAP

*** Test Cases ***
Le Data Browser Compte Les Mandants
    ${total}=    Count Table Entries    T000
    Should Be True    ${total} > 0
```

Fiori (la bibliothèque Browser est obligatoire à côté) :

```robotframework
*** Settings ***
Library           Browser
Resource          resources/fiori_keywords.resource
Suite Setup       Open SAP And Log In
Suite Teardown    Close SAP

*** Test Cases ***
L Application S Ouvre Par Son Intent
    Open App By Intent    Product-manage
    Wait For Ui5 Idle
    Ui5 Should Have No Messages Of Type    Error
```

Canal OData (sans écran) :

```robotframework
*** Settings ***
Resource          resources/api_keywords.resource
Suite Setup       Open Api Channel
Suite Teardown    Close Api Channel

*** Test Cases ***
Le Service Publie Ses Produits
    Api Channel Should Be Available
    ${total}=    Count Business Entities    Products
    Should Be True    ${total} > 0
```

Canal RFC (optionnel, donc neutre là où il n'existe pas) :

```robotframework
*** Settings ***
Resource          resources/rfc_keywords.resource
Suite Setup       Skip Unless Rfc Channel Is Available
Suite Teardown    Close Rfc Channel
Force Tags        rfc

*** Test Cases ***
Le Système Annonce Son Identité
    Open Rfc Channel
    ${identite}=    Read System Identity
    Should Not Be Empty    ${identite}
```

## Où va quoi

| Ce que vous écrivez | Où |
| --- | --- |
| Suites | `tests/robot/{api, ui/ecc, ui/fiori, cross}/` (les suites historiques restent à plat) |
| Page object d'un écran ou d'une application | `resources/page_objects/<ecran>.resource` |
| Keywords transverses au site | `resources/common.resource` |
| Données d'environnement | `variables/env_<env>.yaml` |
| Localisateurs partagés en Python | `variables/locators.py` |
| Sur un **pack déployé** | `resources/site_keywords.resource` uniquement : les fichiers livrés sont écrasés à la mise à jour |

Une capacité manquante ne va dans AUCUNE de ces cases : elle va dans `src/`
(convention #12, voir [conventions.md](conventions.md)).

## Secrets

Un mot de passe, une clé d'API ou un jeton entre par la ligne de commande, avec
le type `Secret` de Robot Framework 7.4, masqué jusqu'en TRACE :

```bash
robot -v "SAP_PASSWORD: Secret:monMotDePasse" …
```

Deux pièges, tous deux payés en live :

- **Un `Secret` refuse d'être MESURÉ.** `Should Not Be Empty    ${password}`
  échoue par « Could not get length of '<secret>' », donc une garde naïve
  masque le prérequis manquant derrière sa propre erreur. Utiliser les gardes
  prévues : `Api Credentials Should Be Provided`, `Rfc Credentials Should Be
  Provided`, `Api Key Should Be Provided`, ou le keyword de bibliothèque
  `Secret Is Provided` (`Library sapfx_common.secrets`).
- **Le déballage se fait à la frontière externe seulement** (COM, HTTP, RFC),
  par `sapfx_common.secrets.reveal_secret`. `Fill Ui5 Input`, `Fill Dom Input`
  et `Fill Wc Input` acceptent directement un `Secret` : aucun
  `getattr(pwd, 'value', pwd)` ne doit apparaître dans un page object, il
  ferait entrer la valeur claire dans l'espace des variables de la suite.

Dans `resources/` et `variables/`, une variable dont le nom porte
`PASSWORD`/`PWD`/`SECRET`/`TOKEN`/`KEY` garde `${EMPTY}` comme défaut. Un garde
unitaire le vérifie sur l'arbre réel.

## Réglages d'attente

Les deux canaux à écran exposent des réglages dynamiques qui retournent
l'ancienne valeur, donc restaurables en teardown : `Set Default Timeout` /
`Set Poll Interval` (ECC), `Set Ui5 Timeout` / `Set Poll Interval` (Fiori).
Portée : l'instance de bibliothèque, scope `SUITE`.

Attention à l'unité : un `settle=2000` nu vaut 2000 SECONDES pour Robot, pas
2000 ms.
