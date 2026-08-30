# ============================================================================
#  Provisionnement du canal RFC (optionnel) : SAP NW RFC SDK + pyrfc.
#
#  Ce script fait tout SAUF obtenir l'archive du SDK : SAP la distribue sous
#  licence depuis SAP for Me (S-user avec l'autorisation Software Download), et
#  elle ne peut etre ni redistribuee dans le pack ni telechargee anonymement.
#  Trois entrees possibles, donc :
#    -SdkZip <chemin>     archive deja presente sur le poste ou sur un partage
#    -SdkUrl <url>        miroir interne de l'entreprise (Artifactory, Nexus...)
#    -UseSapGuiRuntime    AUCUNE archive : s'appuyer sur le runtime NW RFC que le
#                         client SAP GUI a depose dans System32 (mesure le
#                         2026-08-27 : pyrfc s'y charge et un appel RFC reel
#                         passe). Depannage assume, pas un remplacant du SDK,
#                         qui reste la voie de reference et la seule portable
#                         vers un poste ou un runner sans SAP GUI.
#
#  Usage (depuis le dossier du pack) :
#    powershell -ExecutionPolicy Bypass -File install-rfc.ps1 -SdkZip C:\dl\nwrfc.zip
#    powershell -ExecutionPolicy Bypass -File install-rfc.ps1 -SdkUrl https://... -SdkUrlToken $env:TOKEN
#    powershell -ExecutionPolicy Bypass -File install-rfc.ps1 -UseSapGuiRuntime
#    powershell -ExecutionPolicy Bypass -File install-rfc.ps1 -CheckOnly
#
#  Compatible Windows PowerShell 5.1 (pas de `&&`, pas d'operateur ternaire).
#  Fichier UTF-8 sans BOM, lu en ANSI par PowerShell 5.1 : PAS de tirets
#  cadratins ni de guillemets typographiques dans les chaines (leur mojibake
#  contient un guillemet qui ferme la chaine et casse le parse), et pas de
#  lettres accentuees dans ce fichier-ci, contrairement a install.ps1 : il
#  s'execute aussi sur des runners CI dont la page de code n'est pas la notre.
# ============================================================================
param(
    [string]$SdkZip,              # archive locale du SAP NW RFC SDK 7.50
    [string]$SdkUrl,              # ou URL d'un miroir interne
    [string]$SdkUrlToken,         # jeton porteur pour ce miroir (jamais journalise)
    [string]$SdkHome = "C:\nwrfcsdk",
    [string]$PyrfcVersion = "3.3.1",   # toutes les versions PyPI sont yanked : epingler
    [switch]$UseSapGuiRuntime,    # s'appuyer sur le runtime livre par SAP GUI (aucune archive)
    [switch]$Machine,             # variables pour la machine (shell eleve requis)
    [switch]$CheckOnly,           # diagnostique sans rien modifier
    [switch]$SkipPyrfc            # SDK seul (poste sans venv, image de base CI)
)

$ErrorActionPreference = "Stop"
$PackDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $PackDir ".venv\Scripts\python.exe"

function Fail($msg) {
    Write-Host "[ERREUR] $msg" -ForegroundColor Red
    exit 1
}

function Info($msg) { Write-Host "  $msg" }

# Le runtime NW RFC n'arrive pas forcement par le SDK. Le client SAP GUI for
# Windows installe le meme jeu de DLL (composant "SAP NWRFC x64 Shared") dans
# System32, ou le loader Windows les trouve sans SAPNWRFC_HOME ni entree de
# PATH : mesure le 2026-08-27, la roue precompilee de pyrfc s'y charge et un
# appel RFC REEL passe. Un poste qui teste le canal ECC a donc deja le
# necessaire, et c'est souvent la seule voie praticable quand le S-user manque.
# Le SDK garde sa raison d'etre (poste ou runner sans SAP GUI, patch level
# choisi, compilation depuis les sources) : voir "Canal RFC" dans le README.
function Get-SystemRfcRuntime {
    $Dll = Join-Path $env:SystemRoot "System32\sapnwrfc.dll"
    if (Test-Path $Dll) { return $Dll }
    return $null
}

# La cible des variables d'environnement : User par defaut (aucune elevation),
# Machine sur demande explicite. Ecrire dans Machine sans droits leve une
# exception peu parlante, donc on verifie avant.
# Combinaisons d'arguments : tranchees AVANT d'agir, sinon le refus arrive
# apres trois etapes deja affichees, ce qui laisse croire qu'elles ont porte.
if ($UseSapGuiRuntime -and $SkipPyrfc) {
    Fail "-SkipPyrfc et -UseSapGuiRuntime ensemble ne font rien : ce mode n'installe QUE le binding, le runtime etant deja la. Relancer sans -SkipPyrfc."
}
if ($UseSapGuiRuntime -and (($SdkZip -ne "") -or ($SdkUrl -ne ""))) {
    Fail "-UseSapGuiRuntime ignore toute archive : choisir soit ce mode, soit -SdkZip/-SdkUrl (le SDK), pas les deux."
}

$Scope = "User"
if ($Machine) {
    $Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = New-Object Security.Principal.WindowsPrincipal($Identity)
    if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Fail "-Machine ecrit les variables pour toute la machine : relancer ce script depuis un PowerShell lance en tant qu'administrateur, ou omettre -Machine (portee utilisateur)."
    }
    $Scope = "Machine"
}

# --- 0. Diagnostic d'une installation existante ---------------------------------
# Rendu utile en soi (-CheckOnly) ET reutilise en verification finale : un
# provisionnement qui se declare fait sans avoir rien verifie ne vaut rien.
function Test-Provisioning {
    param([switch]$Quiet)

    $Problemes = @()

    $Lib = Join-Path $SdkHome "lib"
    # Un SDK absent n'est un MANQUE que si rien d'autre ne fournit le runtime :
    # sur un poste porteur de SAP GUI, le canal fonctionne, et declarer un
    # manque la reviendrait a crier au loup sur une installation valide.
    if (-not (Test-Path $Lib)) {
        $Runtime = Get-SystemRfcRuntime
        if ($null -ne $Runtime) {
            if (-not $Quiet) {
                Write-Host "  SDK : absent de $SdkHome, mais le runtime NW RFC du client SAP GUI est present"
                Info "($Runtime) : pyrfc se charge et appelle sans SAPNWRFC_HOME ni PATH."
                Info "Le SDK reste la voie de reference : poste ou runner sans SAP GUI,"
                Info "patch level choisi, compilation source. Voir 'Canal RFC' dans le README."
            }
            return @()
        }
    }
    if (-not (Test-Path $Lib)) {
        $Problemes += "$Lib absent (l'archive n'est pas decompressee a cet endroit), et aucun runtime NW RFC dans System32"
    } else {
        $Dll = Join-Path $Lib "sapnwrfc.dll"
        if (-not (Test-Path $Dll)) {
            $Problemes += "$Dll absent : l'archive decompressee n'est pas celle du SDK Windows x64"
        }
    }

    $Home_ = [Environment]::GetEnvironmentVariable("SAPNWRFC_HOME", $Scope)
    if ($null -eq $Home_ -or $Home_.Trim() -eq "") {
        $Problemes += "SAPNWRFC_HOME non definie (portee $Scope)"
    } elseif ($Home_.TrimEnd("\") -ine $SdkHome.TrimEnd("\")) {
        $Problemes += "SAPNWRFC_HOME vaut '$Home_' et non '$SdkHome'"
    }

    $PathValue = [Environment]::GetEnvironmentVariable("PATH", $Scope)
    if ($null -eq $PathValue) { $PathValue = "" }
    $DejaDansPath = $false
    foreach ($Entree in ($PathValue -split ";")) {
        if ($Entree.Trim().TrimEnd("\") -ieq $Lib.TrimEnd("\")) { $DejaDansPath = $true }
    }
    if (-not $DejaDansPath) {
        $Problemes += "$Lib absent du PATH (portee $Scope) : les DLL ne seront pas trouvees a l'execution"
    }

    if (-not $Quiet) {
        if ($Problemes.Count -eq 0) {
            Write-Host "  SDK : OK ($SdkHome, SAPNWRFC_HOME et PATH poses en portee $Scope)"
        } else {
            foreach ($P in $Problemes) { Write-Host "  [manque] $P" -ForegroundColor Yellow }
        }
    }
    return $Problemes
}

if ($CheckOnly) {
    Write-Host "[check] Diagnostic du provisionnement RFC (aucune modification)"
    $Manques = Test-Provisioning
    if (-not $SkipPyrfc) {
        if (-not (Test-Path $VenvPython)) {
            Write-Host "  [manque] venv du pack absent : lancer install.cmd d'abord" -ForegroundColor Yellow
        } else {
            & $VenvPython -c "from pyrfc import Connection; import pyrfc; print('  pyrfc :', pyrfc.__version__)"
            if ($LASTEXITCODE -ne 0) {
                Write-Host "  [manque] pyrfc absent ou non chargeable dans le venv du pack" -ForegroundColor Yellow
            }
        }
    }
    if ($Manques.Count -eq 0) { exit 0 }
    exit 1
}

# --- 1. Prerequis Windows : le runtime Visual C++ 2013 --------------------------
# La bibliotheque C du SDK 7.50 en depend. Son absence ne dit pas son nom :
# elle sort en "DLL load failed" au premier import, un message qui envoie
# chercher le probleme du cote de Python. On le signale donc AVANT.
$Vc = Join-Path $env:SystemRoot "System32\msvcr120.dll"
if (-not (Test-Path $Vc)) {
    Write-Host "[1/4] Runtime Visual C++ 2013 (x64) : introuvable" -ForegroundColor Yellow
    Info "Le runtime NW RFC 7.50 en depend a l'execution. Sans lui, l'import de"
    Info "pyrfc echouera en 'DLL load failed', une erreur qui ne nomme pas sa cause."
    Info "Installer 'Visual C++ Redistributable for Visual Studio 2013' (x64)"
    Info "depuis le site Microsoft, puis relancer ce script."
    Info "Le provisionnement continue : le runtime sera en place, l'import restera KO."
} else {
    Write-Host "[1/4] Runtime Visual C++ 2013 (x64) : present"
}

# --- 2. Obtenir puis decompresser l'archive -------------------------------------
$Lib = Join-Path $SdkHome "lib"
$Telecharge = $null
$RuntimeSysteme = Get-SystemRfcRuntime

if ($UseSapGuiRuntime) {
    if ($null -eq $RuntimeSysteme) {
        Fail @"
-UseSapGuiRuntime demande de s'appuyer sur le runtime NW RFC livre par le client
SAP GUI, mais aucun 'sapnwrfc.dll' n'est present dans System32 : ce poste n'a pas
SAP GUI for Windows (ou pas son composant 'SAP NWRFC x64 Shared').

  Installer SAP GUI for Windows, ou provisionner le SDK : relancer avec
  -SdkZip <archive> ou -SdkUrl <url> [-SdkUrlToken <jeton>].
"@
    }
    Write-Host "[2/4] Runtime NW RFC du client SAP GUI (aucune archive requise)"
    Info $RuntimeSysteme
    Info "Depannage assume : le SDK reste la voie de reference (poste ou runner sans"
    Info "SAP GUI, patch level choisi, compilation source). Voir 'Canal RFC' du README."
} elseif (Test-Path $Lib) {
    Write-Host "[2/4] SDK deja decompresse dans $SdkHome (reutilise)"
} else {
    if (($SdkZip -eq "") -and ($SdkUrl -eq "")) {
        # Si le poste porte deja le runtime, le dire AVANT d'envoyer l'utilisateur
        # vers un portail qui exige un S-user : le refus doit nommer la sortie la
        # plus courte, pas seulement la plus officielle.
        $Piste = ""
        if ($null -ne $RuntimeSysteme) {
            $Piste = @"

  0. Plus court ici : ce poste porte DEJA le runtime NW RFC
     ($RuntimeSysteme), installe par le client SAP GUI. Relancer avec
     -UseSapGuiRuntime teste le canal sans aucune archive. Le SDK reste la
     voie de reference (un runner de CI, lui, n'a pas ce runtime).
"@
        }
        Fail @"
Aucune source d'archive. Le SAP NW RFC SDK est distribue par SAP sous licence :
ce script ne peut pas le telecharger a votre place.
$Piste
  1. Recuperer 'SAP NW RFC SDK 7.50' (Windows on x64 64bit) sur SAP for Me,
     rubrique Software Downloads (S-user avec l'autorisation Software Download).
     Reference : note SAP 2573790.
  2. Relancer avec  -SdkZip <chemin de l'archive>
     ou, si l'entreprise en garde un miroir interne,  -SdkUrl <url> [-SdkUrlToken <jeton>]

Deja provisionne ailleurs ? Passer -SdkHome <dossier> pour le designer.
"@
    }

    if ($SdkUrl -ne "") {
        Write-Host "[2/4] Telechargement depuis le miroir interne"
        $Telecharge = Join-Path ([IO.Path]::GetTempPath()) ("nwrfcsdk-" + [Guid]::NewGuid().ToString("N") + ".zip")
        $Entetes = @{}
        if ($SdkUrlToken -ne "") { $Entetes["Authorization"] = "Bearer $SdkUrlToken" }
        try {
            # Le jeton n'est jamais affiche : seul l'hote de l'URL est journalise.
            Info ("hote : " + ([Uri]$SdkUrl).Host)
            Invoke-WebRequest -Uri $SdkUrl -OutFile $Telecharge -Headers $Entetes -UseBasicParsing
        } catch {
            Fail "Telechargement impossible ($($_.Exception.Message)). Verifier l'URL du miroir et le jeton (-SdkUrlToken)."
        }
        $SdkZip = $Telecharge
    } else {
        Write-Host "[2/4] Archive locale"
    }

    if (-not (Test-Path $SdkZip)) { Fail "Archive introuvable : $SdkZip" }

    # Le SDK se decompresse en un dossier 'nwrfcsdk' : selon l'archive, la
    # racine du zip EST ce dossier, ou le contient. Les deux formes existent,
    # donc on extrait a cote et on deplace ce qui porte reellement 'lib'.
    $Temp = Join-Path ([IO.Path]::GetTempPath()) ("nwrfcsdk-x-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $Temp | Out-Null
    try {
        Expand-Archive -Path $SdkZip -DestinationPath $Temp -Force
        $Racine = $null
        if (Test-Path (Join-Path $Temp "lib")) {
            $Racine = $Temp
        } else {
            $Candidats = @(Get-ChildItem -Path $Temp -Directory -Recurse |
                Where-Object { Test-Path (Join-Path $_.FullName "lib") })
            if ($Candidats.Count -gt 0) { $Racine = $Candidats[0].FullName }
        }
        if ($null -eq $Racine) {
            Fail "L'archive ne contient aucun dossier 'lib' : ce n'est pas le SAP NW RFC SDK (verifier la plateforme choisie au telechargement : Windows on x64 64bit)."
        }
        $Parent = Split-Path -Parent $SdkHome
        if (-not (Test-Path $Parent)) { New-Item -ItemType Directory -Path $Parent -Force | Out-Null }
        Move-Item -Path $Racine -Destination $SdkHome
        Info "decompresse dans $SdkHome"
    } finally {
        if (Test-Path $Temp) { Remove-Item $Temp -Recurse -Force -ErrorAction SilentlyContinue }
        if (($null -ne $Telecharge) -and (Test-Path $Telecharge)) {
            Remove-Item $Telecharge -Force -ErrorAction SilentlyContinue
        }
    }
}

# --- 3. Variables d'environnement ------------------------------------------------
# Sans objet quand le runtime vient du client SAP GUI : ses DLL vivent dans
# System32, que le loader Windows consulte de toute facon. Poser SAPNWRFC_HOME
# vers un dossier inexistant serait pire qu'inutile, cela ferait mentir le
# diagnostic du prochain passage.
if ($UseSapGuiRuntime) {
    Write-Host "[3/4] Variables d'environnement : sans objet dans ce mode"
    Info "les DLL sont dans System32, ni SAPNWRFC_HOME ni PATH ne sont requis"
} else {
    Write-Host "[3/4] Variables d'environnement (portee $Scope)"
    [Environment]::SetEnvironmentVariable("SAPNWRFC_HOME", $SdkHome, $Scope)
    $env:SAPNWRFC_HOME = $SdkHome
    Info "SAPNWRFC_HOME = $SdkHome"

    $PathValue = [Environment]::GetEnvironmentVariable("PATH", $Scope)
    if ($null -eq $PathValue) { $PathValue = "" }
    $Present = $false
    foreach ($Entree in ($PathValue -split ";")) {
        if ($Entree.Trim().TrimEnd("\") -ieq $Lib.TrimEnd("\")) { $Present = $true }
    }
    if ($Present) {
        Info "PATH : $Lib deja present"
    } else {
        $Nouveau = $PathValue.TrimEnd(";")
        if ($Nouveau -eq "") { $Nouveau = $Lib } else { $Nouveau = "$Nouveau;$Lib" }
        [Environment]::SetEnvironmentVariable("PATH", $Nouveau, $Scope)
        Info "PATH : $Lib ajoute"
    }
    # Le processus courant n'herite pas de ce qu'on vient d'ecrire dans le
    # registre : sans cette ligne, la verification finale echouerait alors que
    # tout est correct.
    $env:PATH = "$env:PATH;$Lib"
}

# --- 4. Le binding Python --------------------------------------------------------
if ($SkipPyrfc) {
    Write-Host "[4/4] pyrfc non demande (-SkipPyrfc) : SDK seul."
    Write-Host ""
    Write-Host "SDK provisionne. Ouvrir un NOUVEAU terminal pour heriter des variables." -ForegroundColor Green
    exit 0
}

if (-not (Test-Path $VenvPython)) {
    Fail "venv du pack introuvable ($VenvPython) : lancer install.cmd d'abord, ou passer -SkipPyrfc pour ne provisionner que le SDK."
}

# Toutes les versions PyPI de pyrfc sont 'yanked' depuis l'archivage du projet
# par SAP (2026-05-28) : pip ne les choisit plus tout seul, une version exacte
# est donc obligatoire, ce n'est pas un exces de prudence.
Write-Host "[4/4] Installation de pyrfc==$PyrfcVersion dans le venv du pack"
& $VenvPython -m pip install "pyrfc==$PyrfcVersion"
if ($LASTEXITCODE -ne 0) {
    $PyVersion = (& $VenvPython -c "import sys; print('%d.%d' % sys.version_info[:2])")
    Fail @"
L'installation de pyrfc a echoue (venv en Python $PyVersion).

Cause la plus frequente : les roues precompilees de pyrfc s'arretent a Python
3.12, donc au-dela pip tente une compilation depuis les sources, qui exige
Cython et les Build Tools MSVC. Si le canal RFC vous est indispensable, recreer
le venv du pack avec un interpreteur 3.10 a 3.12 (supprimer .venv, puis
relancer install.cmd avec ce Python-la), et rejouer ce script.
"@
}

Write-Host "      Verification de l'import"
& $VenvPython -c "from pyrfc import Connection; import pyrfc; print('      pyrfc', pyrfc.__version__, 'charge, runtime NW RFC trouve')"
if ($LASTEXITCODE -ne 0) {
    Fail @"
pyrfc est installe mais ne se charge pas. Les trois causes usuelles :
  - le runtime Visual C++ 2013 (x64) manque : voir l'etape [1/4] ci-dessus ;
  - le PATH du processus ne porte pas encore $Lib : ouvrir un NOUVEAU terminal
    et relancer  install-rfc.ps1 -CheckOnly
  - aucun runtime NW RFC n'est atteignable : ni SDK decompresse, ni client SAP
    GUI installe (dont le composant 'SAP NWRFC x64 Shared' en depose un dans
    System32). Installer l'un ou l'autre.
"@
}

$Restant = Test-Provisioning -Quiet
if ($Restant.Count -gt 0) {
    foreach ($P in $Restant) { Write-Host "  [manque] $P" -ForegroundColor Yellow }
    Fail "Provisionnement incomplet : voir les lignes ci-dessus."
}

Write-Host ""
Write-Host "Canal RFC provisionne." -ForegroundColor Green
if ($UseSapGuiRuntime) {
    Write-Host "  Runtime fourni par le client SAP GUI : rien a ouvrir, aucune variable a heriter."
    Write-Host "  Ce mode vaut pour CE poste. Un runner de CI, un poste sans SAP GUI ou un"
    Write-Host "  patch level choisi demandent le SDK : voir 'Canal RFC' dans le README."
} else {
    Write-Host "  Ouvrir un NOUVEAU terminal pour heriter de SAPNWRFC_HOME et du PATH."
}
Write-Host "  Verifier a tout moment :  powershell -File install-rfc.ps1 -CheckOnly"
Write-Host "  Un appel REEL reste la seule preuve : un import qui passe ne dit rien du protocole."
Write-Host "  Keywords disponibles : Open Rfc Connection, Call Rfc, Call Bapi,"
Write-Host "                         Commit/Rollback Bapi Transaction, Wait For Background Job"
