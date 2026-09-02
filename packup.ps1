<#
.SYNOPSIS
Packs the StoryWeaver app into a versioned zip for the updater/device.

.DESCRIPTION
Mirrors the AGENTS.md packup rules using .NET System.IO.Compression so it works
on both PowerShell 5.1 and 7 (Core). Sources from APP\StoryWeaver (app files),
APP\Imgs\StoryWeaver.png (icon), and APP\StoryWeaver.sh (launch file).

Produces: .\_packup\StoryWeaver v<version>.zip
- Adds config.json.default and config.ai.json.default (copies of the current
  dev configs) into the zip.
- Excludes res\source source folder.
- Preserves empty folders.

Optionally deploys the zip via the Cyberduck CLI (duck.exe) to the release or
debug branch: use -Deploy with a required release or debug keyword, e.g.
  .\packup.ps1 -Deploy release   # deploy to release
  .\packup.ps1 -Deploy debug     # deploy to debug
The upload DSN is taken from -DSN (highest priority) or the PACKUP_DSN entry in
the repository .env file.
#>

[CmdletBinding()]
param(
    [string]$Version = "",
    [ValidateSet("release", "debug")]
    [string]$Deploy  = "",
    [string]$DSN     = ""
)

$ErrorActionPreference = "Stop"

function Exit-WithError {
    param([string]$Message, [int]$Code = 1)
    Write-Host $Message -ForegroundColor Red
    exit $Code
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$repoRoot  = $PSScriptRoot
$appRoot   = Join-Path $repoRoot "APP"
$appDir    = Join-Path $appRoot "StoryWeaver"
$iconPath  = Join-Path $appRoot "Imgs\StoryWeaver.png"
$launchFile= Join-Path $appRoot "StoryWeaver.sh"
$outDir    = Join-Path $repoRoot "_packup"

function Assert-Path {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path)) {
        Exit-WithError "Required path missing: $Label => $Path"
    }
}

function Resolve-DeployBranch {
    param([string]$Value)
    if ($Value -ieq "release" -or $Value -ieq "r") {
        return "releases"
    }
    if ($Value -ieq "debug" -or $Value -ieq "d" -or $Value -ieq "debugs") {
        return "debugs"
    }
    Exit-WithError "Invalid -DeployBranch value '$Value'. Expected 'release' or 'debug'."
}

function Resolve-PackupDSN {
    $dsn = $DSN.Trim().TrimEnd('/')
    if ([string]::IsNullOrWhiteSpace($dsn)) {
        $envFile = Join-Path $PSScriptRoot ".env"
        if (Test-Path -LiteralPath $envFile) {
            $line = Get-Content -LiteralPath $envFile | Where-Object {
                $_ -match '^\s*PACKUP_DSN\s*=' } | Select-Object -First 1
            if ($line -and $line -match '=\s*(.+)$') {
                $dsn = $Matches[1].Trim().TrimEnd('/')
            }
        }
    }
    if ([string]::IsNullOrWhiteSpace($dsn)) {
        Exit-WithError "No upload DSN configured. Provide -DSN '<dsn>' or a PACKUP_DSN entry in the repository .env file."
    }
    return $dsn
}

function Assert-DuckCli {
    $cmd = Get-Command duck -ErrorAction SilentlyContinue
    if (-not $cmd) {
        Exit-WithError "duck.exe (Cyberduck CLI) was not found. Install it from: https://docs.duck.sh/cli/#installation (On error, see: https://github.com/iterate-ch/cyberduck/issues/18408)"
    }
    return $cmd
}

function Invoke-DuckUpload {
    param([string]$RemoteUrl, [string]$LocalPath)
    $duck = Assert-DuckCli
    Write-Host "Uploading to: $RemoteUrl"
    & $duck.Source --upload "$RemoteUrl" "$LocalPath" --nokey -e overwrite 2>&1
    if ($LASTEXITCODE -ne 0) {
        Exit-WithError "duck upload failed with exit code $LASTEXITCODE"
    }
}

Assert-Path $appDir    "app folder"
Assert-Path $iconPath  "app icon"
Assert-Path $launchFile "launch file"

if (-not $Version -or [string]::IsNullOrWhiteSpace($Version)) {
    $appPy = Join-Path $appDir "app.py"
    Assert-Path $appPy "app.py"
    $verLine = (Get-Content -LiteralPath $appPy | Where-Object { $_ -match '^\s*ver\s*=' } | Select-Object -First 1)
    if (-not $verLine -or $verLine -notmatch 'ver\s*=\s*"([^"]+)"') {
        Exit-WithError "Could not parse version from app.py (expected: ver = ""vX.Y.Z.B"")"
    }
    $Version = $Matches[1]
}
Write-Host "Packing StoryWeaver $Version"

if (-not (Test-Path -LiteralPath $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}
$zipPath = Join-Path $outDir "StoryWeaver $Version.zip"

# Staging: Compress-Archive/7z can't add one file twice with different names,
# so stage renamed .default copies + apply the res/source exclusion here.
$stageBase = Join-Path ([System.IO.Path]::GetTempPath()) ("storyweaver_packup_" + [System.Guid]::NewGuid().ToString("N"))
try {
    $stageApp   = Join-Path $stageBase "StoryWeaver"
    $stageImgs  = Join-Path $stageBase "Imgs"
    New-Item -ItemType Directory -Path $stageImgs -Force | Out-Null

    # Copy app folder (preserves empty dirs)
    Copy-Item -LiteralPath $appDir -Destination $stageBase -Recurse -Force

    # Rename-copy the config defaults into the staged app
    Copy-Item -LiteralPath (Join-Path $appDir "config.json")    -Destination (Join-Path $stageApp "config.json.default")    -Force
    Copy-Item -LiteralPath (Join-Path $appDir "config.ai.json") -Destination (Join-Path $stageApp "config.ai.json.default") -Force

    # Exclude res\source\* entirely (the whole source dir must not be in the pack)
    $sourceDir = Join-Path $stageApp "res\source"
    if (Test-Path -LiteralPath $sourceDir) {
        Remove-Item -LiteralPath $sourceDir -Recurse -Force
    }

    # Icon + launch file at top level
    Copy-Item -LiteralPath $iconPath   -Destination $stageImgs -Force
    Copy-Item -LiteralPath $launchFile -Destination $stageBase -Force

    # Build zip with explicit directory entries (matching 7z behavior) and
    # skip .gitkeep placeholders. Top-level: StoryWeaver/, Imgs/StoryWeaver.png,
    # StoryWeaver.sh — with directory entries only inside StoryWeaver/.
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    $zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        # Directory entries for the whole tree (relative to stageBase)
        $dirs = Get-ChildItem -LiteralPath $stageBase -Recurse -Directory -Force
        foreach ($d in $dirs) {
            $rel = $d.FullName.Substring($stageBase.Length).TrimStart('\', '/') + "/"
            $rel = $rel.Replace('\', '/')
            # Match reference: only directory entries under StoryWeaver/
            if ($rel -like "Imgs/*") { continue }
            [void]$zip.CreateEntry($rel)
        }

        # File entries
        $files = Get-ChildItem -LiteralPath $stageBase -Recurse -File -Force
        foreach ($f in $files) {
            if ($f.Name -eq ".gitkeep") { continue }
            $rel = $f.FullName.Substring($stageBase.Length).TrimStart('\', '/')
            $rel = $rel.Replace('\', '/')
            $entry = $zip.CreateEntry($rel, [System.IO.Compression.CompressionLevel]::Optimal)
            $es = $entry.Open()
            try {
                $bs = [System.IO.File]::OpenRead($f.FullName)
                try { $bs.CopyTo($es) }
                finally { $bs.Dispose() }
            }
            finally { $es.Dispose() }
        }
    }
    finally {
        $zip.Dispose()
    }

    $size = [math]::Round((Get-Item -LiteralPath $zipPath).Length / 1MB, 2)
    Write-Host "Created: $zipPath ($size MB)"

    if (-not [string]::IsNullOrWhiteSpace($Deploy)) {
        $branch = Resolve-DeployBranch $Deploy
        $dsn    = Resolve-PackupDSN
        $remote = "$dsn/$branch/StoryWeaver $Version.zip"
        Invoke-DuckUpload -RemoteUrl $remote -LocalPath $zipPath
        Write-Host "Deployed $Version to branch '$branch'."
    } else {
        Write-Host "Skipping upload (no -Deploy given)."
    }
}
finally {
    if (Test-Path -LiteralPath $stageBase) {
        Remove-Item -LiteralPath $stageBase -Recurse -Force
    }
}