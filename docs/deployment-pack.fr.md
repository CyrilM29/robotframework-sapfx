> [🇬🇧 English](deployment-pack.md) · **🇫🇷 Français**

# Pack de déploiement : déroulé de bout en bout

Comment amener les bibliothèques, les recorders et les plugins rf-mcp de ce
dépôt jusqu'à un PC de test Windows qui n'a pas de clone du dépôt. Cinq étapes,
~10 minutes hors téléchargements.

Le pack est le **canal de distribution « installation complète »**, le seul
qui embarque tout : bibliothèques, recorders (GUI desktop + extension web
MV3), plugins rf-mcp avec le lanceur `sapfx-mcp`, resources métier, suites
d'exemple, scripts de maintenance et agents de test, dans UN zip auditable
(SHA-256 + SBOM + provenance). PyPI (`pip install robotframework-sapfx`)
livre les **bibliothèques seules** : le bon choix pour ajouter les keywords à
un projet Robot Framework existant, pas pour provisionner un poste de test
complet. C'est ce qui fait du pack la voie recommandée pour les postes de
test cibles (l'installateur a toujours besoin de PyPI ou d'un miroir interne
pour les dépendances épinglées, voir l'étape 3).

```
PC dev (ce dépôt)                       PC Windows cible
─────────────────                       ────────────────
build_release_pack.py ──► sapfx-pack-<v>-win.zip ──► dézipper
                                                      │ install.cmd [-WithMcp] [-WithBrowsers]
                                                      │ robot tests\robot\fiori_smoke.robot
                                                      ▼
                                        .venv + recorders + mcp.generated.json
```

## 1. Construire le pack (PC dev)

```bash
python scripts/build_release_pack.py
```

Sortie : `dist/sapfx-pack-<version>-win.zip` (et le staging dézippé à côté).
Le script construit les deux wheels (`pip wheel --no-deps`), assemble le
manifeste (recorders, `resources/`, six suites d'exemple dont le smoke Browser hors ligne, les scripts de
maintenance `healing_drift_report.py`/`check_spec_sync.py`, les agents de
test, installateur, LICENSE/NOTICE) et zippe. `--skip-wheels` ré-assemble sans reconstruire les
wheels ; la version vient de `pyproject.toml`. Les sources de tout ce que le
pack ajoute (installateur, READMEs, gabarit MCP) vivent dans
[`packaging/`](../packaging/) : corrigez là et regénérez, ne modifiez jamais
`dist/` sur place.

## 2. Transférer

Copiez le zip sur le PC cible (partage, USB…) et dézippez-le n'importe où en
écriture pour l'utilisateur, ex. `C:\sapfx\`. Tous les chemins du pack sont
relatifs à sa racine.

Le pack est aussi **téléchargeable publiquement** (aucun compte GitHub requis)
depuis
[CyrilM29/robotframework-sapfx](https://github.com/CyrilM29/robotframework-sapfx/releases).
Chaque release y est publiée avec des notes adaptées au public, aux côtés
de l'arbre source public (ouvert depuis la 0.6.4) et de la distribution PyPI
« bibliothèques seules ».

## 3. Installer (PC cible)

Prérequis : Windows 10/11, Python 3.10+ dans le `PATH`, accès Internet
**pendant cette étape seulement** (pip télécharge Robot Framework, pywin32,
robotframework-browser… ; les wheels de *ce* dépôt sont déjà dans le pack).

```bat
cd C:\sapfx\sapfx-pack-<version>-win
install.cmd                 REM bibliothèques seules
install.cmd -WithMcp        REM + plugins rf-mcp (usage agent IA)
install.cmd -WithBrowsers   REM + Chromium Playwright (sinon : Chrome système, channel=chrome)
```

L'installateur crée `.venv\` dans le dossier du pack, applique les versions
qualifiées de `constraints-deploy.txt`,
exécute un smoke check d'import, et, avec `-WithMcp`, rend
`mcp.generated.json` avec le chemin absolu du `robotmcp.exe` du venv. Rien de
global n'est modifié (pas de changement de `PATH`, pas de site-packages
système).

## 4. Valider

```bat
.venv\Scripts\robot.exe tests\robot\fiori_wc_smoke.robot REM hors ligne, sans SAP
.venv\Scripts\robot.exe tests\robot\fiori_smoke.robot     REM côté web : réseau requis, pas de SAP
.venv\Scripts\robot.exe -v SAP_CONNECTION:"..." -v SAP_USER:... -v "SAP_PASSWORD: Secret:..." tests\robot\ecc_smoke.robot
```

La forme `: Secret:` est la syntaxe de variable typée de Robot Framework 7.4 :
le mot de passe n'apparaît jamais dans les logs, même en niveau TRACE.

Côté ECC, SAP GUI for Windows doit être installé avec le scripting activé
(option client + paramètre profil serveur `sapgui/user_scripting`), et
`SAP_CONNECTION` doit correspondre à une entrée du SAP Logon local. Les
recorders sont prêts aussi : double-clic sur `recorder.cmd` (desktop, utilise
le Python du venv) ou charger `tools\recorder_web\extension` non empaquetée via
`chrome://extensions` (web).

## 5. Brancher l'agent IA (optionnel, `-WithMcp`)

Copiez `mcp.generated.json` en `.mcp.json` à la racine du projet où tourne
l'agent (Claude Code), ou fusionnez-le dans `.vscode/mcp.json` (VS Code / mode
agent Copilot). Aucun `PYTHONPATH` n'est nécessaire : les plugins sont
installés dans le venv et s'enregistrent par entry points.

## Mettre à jour une installation existante

Regénérez le zip sur le PC dev (étape 1), dézippez **par-dessus** le dossier du
pack existant sur la cible, et relancez `install.cmd` avec les mêmes options :
le venv est réutilisé et pip met à niveau les wheels en place. Pour repartir
propre, supprimez d'abord `.venv\`.

## Limites

- L'étape d'installation a besoin de PyPI (ou d'un miroir interne). Pour des
  cibles isolées du réseau, demandez la variante offline (wheels de dépendances
  embarqués dans `wheels/`), non construite par défaut car les wheels pywin32
  sont spécifiques à la version de Python.
- Le pack embarque six suites d'exemple (les smokes ECC/Fiori, le smoke WC hors ligne, la campagne
  d'exploration autonome, la sentinelle de dérive et le flagship
  cross-paradigme) ; les autres suites de campagne (data-driven, SCARR/SPFLI…)
  restent dans le dépôt car elles exigent un A4H live ou des fixtures locales.

## Intégrité et provenance

Le ZIP est accompagné d'un sidecar `.zip.sha256` et d'un SBOM CycloneDX de
l'environnement installé proprement. `SHA256SUMS.txt` vérifie chaque fichier à
l'intérieur du pack. Le job CI `release-pack` émet aussi une attestation GitHub
de provenance pour les ZIP construits depuis un push (obligatoire en dépôt
public, best-effort en privé si le plan GitHub ne l'expose pas).
