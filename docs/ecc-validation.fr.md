> [🇬🇧 English](ecc-validation.md) · **🇫🇷 Français**

# Validation ECC « live » — système ABAP (CAL ou Docker) + SAP GUI

Procédure de bout en bout pour exécuter `tests/robot/ecc_smoke.robot` contre un vrai
système SAP (système A4H), avec le client **SAP GUI for Windows**.

> 🚧 **Disponibilité de l'image Docker (2026)** : à ce jour, l'image
> `sapse/abap-cloud-developer-trial` est **introuvable / 404 sur Docker Hub**
> d'après plusieurs retours communautaires — SAP semble l'avoir retirée (au moins
> temporairement). L'ancienne `sapse/abap-platform-trial` est également retirée et
> *AS ABAP 7.xx Developer Edition* est **EOL (mai 2026)**.
>
> ➡️ **Chemin recommandé aujourd'hui : SAP Cloud Appliance Library (CAL)** — voir
> **§ A**. Le **§ B (Docker)** reste valable *si/quand* l'image redevient
> disponible sur Docker Hub. Une fois un système joignable (CAL ou Docker), les
> **§ 5 → § 10** (connexion SAP GUI, scripting, exécution) sont communs.

> La validation au niveau code est déjà couverte hors-ligne par `tests/unit`
> (notamment `test_ecc_flow.py`, session COM simulée). Ce document couvre la
> navigation réelle, qui nécessite un système.

## 0. Prérequis (état sur cette machine)

| Élément | Requis | Cette machine |
|---|---|---|
| RAM | 16 Go min (32+ conseillé) | **128 Go ✓** |
| Disque libre | ~170 Go conseillé (image >53 Go décompressée) | **C: 241 Go ✓** |
| Docker (conteneurs Linux) | oui | **27.5.1 ✓** (Docker Desktop) |
| SAP GUI for Windows | oui | **8.00 64-bit ✓** (`C:\Program Files\SAP\FrontEnd\SAPgui\saplogon.exe`) |
| `pywin32` | oui | **✓** |

> ✅ **Vérification client + scripting (sans serveur)** — déjà validée en live sur
> cette machine. Reproductible à tout moment :
> `python tests/manual/check_sap_gui_connection.py`. Ce script lance SAP Logon,
> s'attache au moteur de scripting (COM) et lit le `GuiApplication` (ici SAP GUI
> 8.00, scripting actif). La **manipulation d'écrans** exige en plus une session
> connectée (option A ou B).

> Les lignes **Docker / RAM / disque** du tableau §0 ne concernent que l'**option B**
> (conteneur local). Pour l'**option A (CAL)**, le système tourne dans le cloud ; il
> te faut surtout le **client SAP GUI** local + `pywin32` (déjà ✓).

## A. Option recommandée — SAP Cloud Appliance Library (CAL)

Même produit (ABAP/ECC Developer Edition), mais en **appliance hébergée** : le
logiciel SAP est gratuit, tu paies uniquement l'**hébergement cloud** (AWS/Azure/GCP)
pendant que l'instance tourne (et tu peux la *suspendre* pour réduire les coûts).

1. Compte **SAP Universal ID** (gratuit) + un compte **hyperscaler** (AWS/Azure/GCP)
   avec accès facturation.
2. Aller sur **<https://cal.sap.com/catalog>**, chercher une solution **« ABAP
   Platform Developer Edition »** / **« ABAP Cloud Developer Trial »**, accepter les
   conditions, et **créer une instance** (choisir région + type de VM).
3. CAL provisionne la VM et affiche les **détails de connexion** : nom d'hôte public,
   SID, numéro d'instance, et les mots de passe (souvent `DEVELOPER` / mot de passe
   défini à la création, master password de l'instance).
4. Ouvrir les ports SAP GUI (3200 + 33xx) dans le pare-feu / security group de la VM,
   ou utiliser l'accès fourni par CAL.
5. Continuer directement au **§ 5** (connexion SAP GUI) — en remplaçant l'hôte
   `vhcala4hci` par le **nom d'hôte public de la VM CAL** et les identifiants par ceux
   affichés dans CAL.

> Astuce coût : **suspendre** l'instance dans CAL dès que tu ne l'utilises pas — tu
> ne paies alors quasiment que le stockage.

## B. Option Docker — prérequis manuels (si l'image est disponible)

> Ne s'applique que si `sapse/abap-cloud-developer-trial` est de nouveau **présente
> sur Docker Hub** (cf. note de disponibilité en haut). Sinon, utiliser l'**option A**.

L'image SAP est **protégée** : un `docker pull` direct renvoie
`denied: requested access to the resource is denied`. Avant tout :

1. **Se connecter à Docker Hub** (compte gratuit) :

   ```powershell
   docker login
   ```

2. **Accepter les conditions SAP** sur la page de l'image (connecté avec le même
   compte) : <https://hub.docker.com/r/sapse/abap-cloud-developer-trial> → bouton
   *Accept / Proceed* des termes du fournisseur. Sans cette acceptation web, le pull
   reste refusé (`denied: requested access to the resource is denied`).

## 2. Récupérer l'image

Choisir le tag dans l'onglet *Tags* de
<https://hub.docker.com/r/sapse/abap-cloud-developer-trial> (⚠️ la page *Overview*
indique explicitement de **ne pas** y faire le pull). Remplacer `<TAG>` ci-dessous
par le tag disponible le plus récent (p.ex. `2022`, `2025`) :

```powershell
docker pull sapse/abap-cloud-developer-trial:<TAG>
```

(Image ~23 Go compressée, >53 Go décompressée ; long selon la bande passante.)

## 3. Lancer le conteneur

> Le flag `-agree-to-sap-license` vaut **acceptation de la licence développeur SAP**.
> Contrairement à l'ancienne image, l'ABAP Cloud Developer Trial a un **mot de passe
> par défaut fixe selon la version** (pas de `-master-password`) — voir §5.

```powershell
docker run --stop-timeout 3600 -i --name a4h -h vhcala4hci `
  -p 3200:3200 -p 3300:3300 -p 8443:8443 -p 30213:30213 -p 50000:50000 -p 50001:50001 `
  sapse/abap-cloud-developer-trial:<TAG> `
  -agree-to-sap-license -skip-limits-check
```

> Vérifier la commande exacte (flags, ports) dans l'onglet *Tags* / la doc de la
> version choisie, car elle peut évoluer d'une release à l'autre.

Le premier démarrage (HANA + ABAP) prend **10–30 min**. Suivre les logs :

```powershell
docker logs -f a4h
```

Attendre le message indiquant que le système est démarré (« Instance on host
vhcala4hci started » / invite de fin). `Ctrl+C` détache l'affichage des logs (ne tue
pas le conteneur, lancé avec `-i`).

## 4. Résolution de nom (hosts)

Ajouter dans `C:\Windows\System32\drivers\etc\hosts` (éditeur en administrateur) :

```text
127.0.0.1   vhcala4hci
```

## 5. Connexion SAP GUI

Ouvrir **SAP Logon** → *Nouveau* → *Connexion à un serveur d'applications personnalisé* :

| Champ | Valeur |
|---|---|
| Description | `A4H` (doit correspondre à `SAP_CONNECTION`, voir §8) |
| Serveur d'application | **option B (Docker)** : `vhcala4hci` (ou `localhost`) — **option A (CAL)** : nom d'hôte public de la VM |
| Numéro d'instance | `00` |
| ID système (SID) | `A4H` |

Identifiants du système trial :

| Client | Utilisateur | Mot de passe (selon la version) | Usage |
|---|---|---|---|
| `001` | `DEVELOPER` | p.ex. `ABAPtr2022#01` (2022), `ABAPtr2023#00` (2023) | développement |
| `000` | `SAP*` / `DDIC` | même mot de passe par défaut de la version | admin |

Le mot de passe par défaut **dépend du tag** : le récupérer dans la doc / l'onglet
*Tags* de la version choisie. Au premier login, SAP peut demander de le changer.

## 6. Licence ABAP (si expirée)

Le système trial inclut une licence temporaire. Si elle est expirée
(message au login) : transaction **`SLICENSE`** → relever la *clé matériel* →
demander une licence gratuite 90 jours (« minisap ») pour le produit ABAP Platform
sur le portail SAP, puis l'installer dans `SLICENSE`.

## 7. Activer le SAP GUI Scripting

**Côté serveur** (transaction **`RZ11`**) :

- Paramètre `sapgui/user_scripting` → valeur **`TRUE`** (modification dynamique).
- Pour rendre persistant après redémarrage : le fixer dans le profil via `RZ10`.
- Optionnel : `sapgui/user_scripting_disable_recording = FALSE`,
  `sapgui/user_scripting_per_user` selon besoin.

**Côté client** (SAP Logon → *Options* → *Accessibility & Scripting* → *Scripting*) :

- Cocher **Enable scripting**.
- **Décocher** *Notify when a script attaches to SAP GUI* et *Notify when a script
  opens a connection* (sinon des popups bloquent l'automatisation).

Vérification rapide : la commande `connect to session` de la bibliothèque doit
trouver le moteur (`GetScriptingEngine`). Si elle échoue avec « is Sap Logon Pad
open? », le scripting n'est pas actif des deux côtés.

## 8. Exécuter `ecc_smoke.robot`

La suite utilise `resources/ecc_keywords.resource` :
`Open Sap Logon` (lance `saplogon.exe`) → `Connect To Session With Retry` →
`Open Connection ${SAP_CONNECTION}` → saisie login → transactions.

`SAP_CONNECTION` doit être **exactement** la *Description* de l'entrée SAP Logon (§5).

```powershell
robot --pythonpath src `
  -v SAP_CONNECTION:"A4H" `
  -v SAP_USER:DEVELOPER `
  -v "SAP_PASSWORD: Secret:ABAPtr2022#01" `
  -v SAP_CLIENT:001 `
  -v SAP_LANGUAGE:EN `
  tests/robot/ecc_smoke.robot
```

(Adapter `SAP_PASSWORD` au mot de passe par défaut de la version choisie — cf. §5.
La forme `: Secret:` est la syntaxe de variable typée de Robot Framework 7.4 :
la valeur est masquée partout, même dans les logs TRACE.)

Résultats dans `output.xml` / `log.html` / `report.html`.

## 9. Dépannage

| Symptôme | Cause / correctif |
|---|---|
| `denied` au pull | §B non fait : `docker login` + accepter les termes sur la page Docker Hub. |
| `not found` / 404 au pull | L'image Docker est actuellement retirée de Docker Hub → utiliser l'**option A (CAL)**. |
| Popup « A script is opening a connection… » | Décocher les notifications côté client (§7). |
| `Could not connect to Session, is Sap Logon Pad open?` | `sapgui/user_scripting` non `TRUE` (RZ11) ou scripting client désactivé. |
| `Cannot open connection 'A4H'` | La *Description* SAP Logon ≠ `SAP_CONNECTION`. |
| Login refusé / mot de passe expiré | Changer le mot de passe au login ; vérifier client `001` / user `DEVELOPER`. |
| Message licence au login | Installer une licence minisap via `SLICENSE` (§6). |
| `Logon not possible (error in license check)` (client 001 — GUI *et* OData) | Licence expirée/invalide (§6). En attendant, `SAP*` / client `000` se connecte pour les tâches d'admin (§11.7). |
| `SAP Gateway has been deactivated` (OData HTTP 500, `/IWFND/CM_COS/003`) | Conteneur re-créé : exécuter l'activité IMG `/IWFND/IWF_ACTIVATE` en `SAP*`/000 → *Activate* (§11.7). |
| Démarrage très long / HANA pas prête | Attendre la fin dans `docker logs -f a4h` avant de tester. |

## 10. Cycle de vie du conteneur

```powershell
docker stop a4h      # arrêt propre (peut prendre du temps : --stop-timeout 3600)
docker start a4h     # redémarrage (plus rapide que le 1er boot)
docker rm a4h        # suppression (perte des données du système)
```

## 11. Validé en live — points durs rencontrés (✅ ecc_smoke 5/5)

Validation réelle effectuée avec une **image 1909** (l'officielle étant retirée :
re-upload tiers `toberic/abap-platform-trial:1909`, ⚠️ non-officiel — cf. réserves
licence/sécurité). Ces points sont **génériques** à l'ABAP Platform Trial sous Docker
Desktop/Windows :

1. **sysctl HANA (sinon HANA ne démarre pas).** Docker Desktop/WSL2 a des limites trop
   basses ; `-skip-limits-check` contourne le *contrôle* mais pas la *limite*. Régler
   sur le kernel de la VM via un conteneur privilégié :

   ```powershell
   docker run --rm --privileged --entrypoint /bin/sh toberic/abap-platform-trial:1909 `
     -c "sysctl -w vm.max_map_count=2147483647 fs.aio-max-nr=18446744073709551615 kernel.shmmni=32768"
   ```

   Puis lancer a4h avec `--sysctl kernel.shmmni=32768`.

2. **Deux licences expirées → minisap (§6/§7), avec une subtilité clé : les clés
   matériel sont propres au conteneur** (dérivées de la MAC). Lire la clé **sur le
   conteneur a4h lui-même** :
   - ABAP : `docker exec a4h su - a4hadm -c "saplikey pf=/usr/sap/A4H/SYS/profile/A4H_D00_vhcala4hci -get"`
   - HANA : `M_LICENSE.HARDWARE_KEY` via `hdbsql -i 02 -d SYSTEMDB -u SYSTEM -p <pw>`

   Obtenir sur <https://go.support.sap.com/minisap> (système **A4H** ; HANA =
   *SAP HANA Platform Edition (64GB)*), puis installer :

   ```powershell
   docker cp ASABAP_license a4h:/opt/sap/ASABAP_license
   docker cp HDB_license    a4h:/opt/sap/HDB_license
   docker exec a4h /usr/local/bin/hdb_license_update
   docker exec a4h /usr/local/bin/asabap_license_update
   docker restart a4h        # boot propre : disp+work GREEN, "Have fun!"
   ```

3. **Scripting côté serveur (sinon le scripting voit la connexion mais 0 session).**
   Ajouter au profil d'instance puis redémarrer l'instance :

   ```powershell
   docker exec a4h bash -lc "echo 'sapgui/user_scripting = TRUE' >> /usr/sap/A4H/SYS/profile/A4H_D00_vhcala4hci"
   docker exec a4h su - a4hadm -c "sapcontrol -nr 00 -function RestartInstance"
   ```

4. **Résolution de nom :** `127.0.0.1 vhcala4hci` dans le fichier hosts (admin).

5. **Connexion sans entrée SAP Logon :** chaîne `/H/vhcala4hci/S/3200` via le keyword
   **`Open Connection By String`** (le `Open Connection` standard exige une entrée
   enregistrée). Login **`DEVELOPER` / client `001` / `Htods70334`** — le mot de
   passe par défaut publié par SAP lui-même pour cette image trial, pas un vrai
   secret ; néanmoins, préférez le passer via `-v "SAP_PASSWORD: Secret:..."`
   (la variable typée RF 7.4, masquée même dans les logs TRACE) ou une variable
   d'env plutôt que de le coder en dur, pour éviter tout faux positif de
   scanner de secrets.

6. **Exécution validée :**

   ```powershell
   robot --pythonpath src -v SAP_CONNECTION:/H/vhcala4hci/S/3200 `
     -v SAP_USER:DEVELOPER -v "SAP_PASSWORD: Secret:Htods70334" -v SAP_CLIENT:001 `
     tests/robot/ecc_smoke.robot
   ```

   → **5/5 PASS** (login, navigation SE16, parcours T000, lecture **grille ALV**
   SM50, transaction inconnue).

7. **Un conteneur re-créé repart nu — et ses licences meurent avec l'ancienne
   MAC.** `docker rm` + `docker run` remet à zéro tout ce qui a été fait depuis
   le premier provisionnement : la clé matérielle ABAP dérive de l'adresse MAC
   de eth0 (la figer avec `--mac-address` au `docker run`, sinon la clé — et la
   licence — change ; sous Docker 29 un conteneur créé *sans* `--mac-address`
   change même de MAC à chaque `docker start`), et la ligne de profil scripting
   (point 3), le service ICF `webgui` (SICF) et l'**activation de la SAP
   Gateway** sont perdus. Tout se répare **sans licence valide**, car `SAP*`
   en client `000` se connecte quand même — seul le client `001` est bloqué
   par le contrôle de licence, en GUI *et* en OData (même « error in license
   check ») :
   - OData répond HTTP 500 `/IWFND/CM_COS/003` *« SAP Gateway has been
     deactivated »* → exécuter l'activité IMG **`/IWFND/IWF_ACTIVATE`**
     (« Activate or Deactivate SAP Gateway », SPRO → SAP Gateway → OData
     Channel → Configuration) et cliquer *Activate*. Son tcode généré se lit
     dans la table `CUS_IMGACH` (`/IWFND/50000003` sur l'image 1909) ; le
     réglage est **inter-mandants** — un seul passage suffit (vérifié live le
     2026-08-02 : catalogue du client 000 = 38 services aussitôt après).
   - Piège au passage : `Run Transaction` sur un tcode IMG généré échoue en
     **faux négatif** — la transaction a bien démarré, mais sous son nom
     interne (`active='/IWFND/IWF_ACTIVATE'`). Percevoir l'écran avant de
     conclure (voir `memory/run-transaction-tcodes-parametres.md`).

> Note réelle : sur ce système, une transaction inexistante renvoie un statut de type
> **`S`** (pas `E`) — `Run Transaction` a donc été corrigé pour comparer la
> **transaction active** (`session.Info.Transaction`), seul critère vraiment
> indépendant de la langue.

---

- **Option A (CAL)** : une fois l'instance créée et joignable, donne-moi le nom
  d'hôte public + les identifiants, et je t'accompagne sur §5→§8 (connexion SAP GUI,
  scripting, exécution de `ecc_smoke`).
- **Option B (Docker)** : si l'image redevient disponible, après `docker login` +
  acceptation des termes, je pilote §2→§3 (pull + run) puis §4→§8.

## Sources

- SAP Cloud Appliance Library (option A) : <https://cal.sap.com/catalog>
- Doc officielle de l'image : <https://github.com/SAP-docs/abap-platform-trial-image>
- Image Docker Hub (option B, actuellement 404) : <https://hub.docker.com/r/sapse/abap-cloud-developer-trial>
- SAP Community — ABAP Cloud Developer Trial 2023 :
  <https://community.sap.com/t5/technology-blog-posts-by-sap/abap-cloud-developer-trial-2023-available-now/ba-p/14057183>
