# ============================================================================
#  Installateur du pack de déploiement SAPFX (Windows).
#  Crée un venv local (.venv), installe les wheels du pack + les dépendances
#  épinglées, vérifie les imports, et rend la config MCP (avec -WithMcp).
#
#  Usage (depuis le dossier du pack) :
#    powershell -ExecutionPolicy Bypass -File install.ps1 [-WithMcp] [-WithBrowsers]
#  ou simplement : install.cmd [-WithMcp] [-WithBrowsers]
#
#  Compatible Windows PowerShell 5.1 (pas de `&&`, pas d'opérateur ternaire).
#  Fichier UTF-8 sans BOM, lu en ANSI par PowerShell 5.1 : PAS de tirets
#  cadratins ni guillemets typographiques dans les chaînes (leur mojibake
#  contient un guillemet " typographique " qui ferme la chaîne et casse le
#  parse) ; les lettres accentuées, elles, sont sans danger.
# ============================================================================
param(
    [switch]$WithMcp,       # installe aussi le wheel sap-robotmcp (plugins rf-mcp)
    [switch]$WithBrowsers   # télécharge le Chromium de Playwright (rfbrowser init)
)

$ErrorActionPreference = "Stop"
$PackDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Fail($msg) {
    Write-Host "[ERREUR] $msg" -ForegroundColor Red
    exit 1
}

# --- 0. Verifier l'integrite du pack -------------------------------------------
# Le pack livre SHA256SUMS.txt (ecrit par le builder avant le zip) ; personne ne
# le controlait, donc il n'etait utile qu'a qui y pensait a la main. Les wheels
# sont la charge utile executable : une alteration y est bloquante. Le reste du
# pack (suites d'exemple, resources) est fait pour etre adapte sur le poste : on
# le signale, on ne refuse pas d'installer.
$Sums = Join-Path $PackDir "SHA256SUMS.txt"
if (Test-Path $Sums) {
    Write-Host "[0/5] Verification d'integrite (SHA256SUMS.txt)"
    $Alteres = @()
    foreach ($Line in (Get-Content $Sums)) {
        if ($Line.Trim() -eq "") { continue }
        $Parts = $Line -split "  ", 2
        if ($Parts.Count -ne 2) { continue }
        $Attendu = $Parts[0].Trim()
        $Relatif = $Parts[1].Trim()
        $Cible = Join-Path $PackDir ($Relatif -replace "/", "\")
        if (-not (Test-Path $Cible)) {
            $Verdict = "absent"
        } else {
            $Obtenu = (Get-FileHash $Cible -Algorithm SHA256).Hash
            if ($Obtenu -ieq $Attendu) { continue }
            $Verdict = "modifie"
        }
        if ($Relatif -like "wheels/*") {
            Fail "$Relatif est $Verdict (empreinte SHA-256 non conforme). Le pack est incomplet ou altere : retelecharger l'archive."
        }
        $Alteres += "$Relatif ($Verdict)"
    }
    if ($Alteres.Count -gt 0) {
        Write-Host "  [info] $($Alteres.Count) fichier(s) different(s) du pack d'origine :" -ForegroundColor Yellow
        foreach ($Entree in ($Alteres | Select-Object -First 5)) {
            Write-Host "         - $Entree" -ForegroundColor Yellow
        }
        Write-Host "         (normal si vous avez adapte les suites ou les resources)" -ForegroundColor Yellow
    } else {
        Write-Host "  Empreintes conformes."
    }
} else {
    Write-Host "[0/5] SHA256SUMS.txt absent : verification d'integrite ignoree."
}

# --- 1. Trouver un Python hote -------------------------------------------------
$HostPython = $null
foreach ($candidate in @("python", "py")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($null -ne $cmd) { $HostPython = $candidate; break }
}
if ($null -eq $HostPython) { Fail "Python introuvable dans le PATH (python ou py requis)." }

# Plancher 3.10 (requires-python du paquet). Sans ce controle, un poste en 3.9
# partait jusqu'au pip install pour finir sur un message de resolveur, et les
# versions EPINGLEES du pack (Pillow, robotframework-browser) exigent elles
# aussi 3.10 : autant le dire ici, avec la marche a suivre.
$PyVersion = (& $HostPython -c "import sys; print('%d.%d' % sys.version_info[:2])")
if ($LASTEXITCODE -ne 0) { Fail "Impossible d'interroger la version de Python ($HostPython)." }
$PyParts = $PyVersion.Trim().Split(".")
$PyMajor = [int]$PyParts[0]
$PyMinor = [int]$PyParts[1]
if (($PyMajor -lt 3) -or (($PyMajor -eq 3) -and ($PyMinor -lt 10))) {
    Fail "Python $PyVersion detecte, or SAPFX exige Python 3.10 ou plus recent. Installer une version 3.10+ (python.org) et relancer, ou pointer le lanceur py sur une version compatible."
}
Write-Host "      Python $PyVersion (3.10 minimum) : OK"

# --- 2. Créer le venv ----------------------------------------------------------
$VenvDir = Join-Path $PackDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "[1/5] Création du venv : $VenvDir"
    if ($HostPython -eq "py") { & py -3 -m venv $VenvDir } else { & python -m venv $VenvDir }
    if (-not (Test-Path $VenvPython)) { Fail "La création du venv a échoué." }
} else {
    Write-Host "[1/5] venv déjà présent : $VenvDir (réutilisé)"
}

# --- 3. Installer les wheels + dépendances -------------------------------------
Write-Host "[2/5] Mise à niveau de pip"
& $VenvPython -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { Fail "Échec de la mise à niveau de pip." }

# -ErrorAction SilentlyContinue : sous $ErrorActionPreference = "Stop", un dossier
# wheels\ absent faisait avorter Get-ChildItem AVANT le Fail explicite ci-dessous,
# donc l'utilisateur voyait l'erreur PowerShell brute au lieu du diagnostic.
$LibWheels = @(Get-ChildItem (Join-Path $PackDir "wheels\robotframework_sapfx-*.whl") -ErrorAction SilentlyContinue)
if ($LibWheels.Count -eq 0) { Fail "Wheel robotframework_sapfx-*.whl introuvable dans wheels\." }
if ($LibWheels.Count -ne 1) { Fail "Plusieurs wheels robotframework_sapfx trouvés ; pack ambigu ou corrompu." }

Write-Host "[3/5] Installation des bibliothèques (SapEccLibrary / SapFioriLibrary / SapApiLibrary / sapfx_common)"
& $VenvPython -m pip install $LibWheels[0].FullName `
    -r (Join-Path $PackDir "requirements-deploy.txt") `
    -c (Join-Path $PackDir "constraints-deploy.txt")
if ($LASTEXITCODE -ne 0) { Fail "Échec de l'installation des bibliothèques." }

if ($WithMcp) {
    $McpWheels = @(Get-ChildItem (Join-Path $PackDir "wheels\sap_robotmcp-*.whl") -ErrorAction SilentlyContinue)
    if ($McpWheels.Count -eq 0) { Fail "Wheel sap_robotmcp-*.whl introuvable dans wheels\." }
    if ($McpWheels.Count -ne 1) { Fail "Plusieurs wheels sap_robotmcp trouvés ; pack ambigu ou corrompu." }
    Write-Host "[3b/5] Installation des plugins rf-mcp (sap-robotmcp + rf-mcp)"
    & $VenvPython -m pip install $McpWheels[0].FullName `
        -c (Join-Path $PackDir "constraints-deploy.txt")
    if ($LASTEXITCODE -ne 0) { Fail "Échec de l'installation des plugins rf-mcp." }
}

if ($WithBrowsers) {
    Write-Host "[3c/5] Téléchargement du Chromium Playwright (rfbrowser init)"
    & (Join-Path $VenvDir "Scripts\rfbrowser.exe") init chromium
    if ($LASTEXITCODE -ne 0) { Fail "Échec de rfbrowser init chromium." }
}

# --- 4. Rendre les configs MCP ---------------------------------------------------
if ($WithMcp) {
    Write-Host "[4/5] Génération des configs MCP (.mcp.json, .vscode\mcp.json)"
    # Lanceur : la surcouche sapfx-mcp (rf-mcp inchangé + outils sapfx_* :
    # état par providers, canal image, hot-reload) ; repli robotmcp.exe si un
    # wheel sap-robotmcp antérieur à 0.6.2 est installé.
    $RobotMcpExe = (Join-Path $VenvDir "Scripts\sapfx-mcp.exe")
    if (-not (Test-Path $RobotMcpExe)) {
        $RobotMcpExe = (Join-Path $VenvDir "Scripts\robotmcp.exe")
    }
    # Le repli ne verifiait pas l'existence de sa cible : une config MCP pouvait
    # etre rendue avec un chemin mort, et l'agent echouait plus tard, ailleurs.
    if (-not (Test-Path $RobotMcpExe)) {
        Fail "Ni sapfx-mcp.exe ni robotmcp.exe dans .venv\Scripts : l'installation des plugins rf-mcp n'a pas depose son point d'entree. Relancer install.cmd -WithMcp et lire les messages de pip."
    }
    $RobotMcpExe = $RobotMcpExe.Replace("\", "/")
    $Template = Get-Content (Join-Path $PackDir "mcp.json.template") -Raw
    $Rendered = $Template.Replace("{{ROBOTMCP_EXE}}", $RobotMcpExe)
    # mcp.generated.json : à copier si l'agent IA tourne dans un AUTRE projet.
    $Rendered | Set-Content (Join-Path $PackDir "mcp.generated.json") -Encoding utf8
    # .mcp.json : Claude Code le lit à la racine du workspace ; le pack ouvert
    # dans VS Code/Claude Code est donc immédiatement branché sur rf-mcp.
    $Rendered | Set-Content (Join-Path $PackDir ".mcp.json") -Encoding utf8
    # .vscode\mcp.json : équivalent pour VS Code / Copilot agent mode (clé "servers").
    $VsCodeDir = Join-Path $PackDir ".vscode"
    if (-not (Test-Path $VsCodeDir)) { New-Item -ItemType Directory -Path $VsCodeDir | Out-Null }
    $VsTemplate = Get-Content (Join-Path $PackDir "vscode-mcp.json.template") -Raw
    $VsTemplate.Replace("{{ROBOTMCP_EXE}}", $RobotMcpExe) |
        Set-Content (Join-Path $VsCodeDir "mcp.json") -Encoding utf8
} else {
    Write-Host "[4/5] Plugins MCP non demandés (relancer avec -WithMcp pour les ajouter)"
    # Une installation precedente a pu deposer ces configs : elles pointent un
    # serveur qui n'est plus installe. On le signale sans les supprimer (elles
    # ont pu etre adaptees a la main, effacer serait pire que prevenir).
    $Restes = @()
    foreach ($Config in @(".mcp.json", "mcp.generated.json", ".vscode\mcp.json")) {
        if (Test-Path (Join-Path $PackDir $Config)) { $Restes += $Config }
    }
    if ($Restes.Count -gt 0) {
        Write-Host "  [info] configs MCP d'une installation precedente encore presentes : $($Restes -join ', ')" -ForegroundColor Yellow
        Write-Host "         elles pointent un serveur non installe ici : relancer avec -WithMcp, ou les supprimer." -ForegroundColor Yellow
    }
}

# --- 5. Smoke check ------------------------------------------------------------
Write-Host "[5/5] Vérification des imports"
& $VenvPython -c "import SapEccLibrary, SapFioriLibrary, SapApiLibrary, sapfx_common; import robot; print('imports OK - Robot Framework', robot.version.VERSION)"
if ($LASTEXITCODE -ne 0) {
    Fail "Le smoke check d'import a échoué (voir README.fr.md, section Dépannage)."
}
if ($WithMcp) {
    & $VenvPython -c "import sap_robotmcp; print('plugins rf-mcp OK')"
    if ($LASTEXITCODE -ne 0) { Fail "Import des plugins rf-mcp en échec." }
}

Write-Host ""
Write-Host "Installation terminée." -ForegroundColor Green
Write-Host "  Valider :  .venv\Scripts\robot.exe tests\robot\fiori_smoke.robot"
Write-Host "  Recorder : recorder.cmd (SAP Logon ouvert au préalable)"
if ($WithMcp) {
    Write-Host "  MCP :      .mcp.json (Claude Code) et .vscode\mcp.json (Copilot) sont prêts dans le pack ;"
    Write-Host "             pour un agent tournant ailleurs, copier mcp.generated.json dans son projet"
    Write-Host "  Agents :   ouvrir ce dossier dans VS Code : agents de test dans .claude\agents (Claude Code)"
    Write-Host "             et .github\chatmodes (Copilot agent mode) ; plans de test dans specs\"
}
