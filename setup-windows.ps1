[CmdletBinding()]
param(
    [string]$Vault,
    [switch]$SkipCodex,
    [switch]$SkipZotero
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section([string]$Name) {
    Write-Host ""
    Write-Host $Name -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-WarningMessage([string]$Message) {
    Write-Host "  [!] $Message" -ForegroundColor Yellow
}

function Write-Failure([string]$Message) {
    Write-Host "  [X] $Message" -ForegroundColor Red
}

function Test-ExitCode([string]$Action) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Action failed with exit code $LASTEXITCODE. Review the message above and run setup again."
    }
}

function Add-UserPathEntry([string]$Entry) {
    $normalized = [System.IO.Path]::GetFullPath($Entry).TrimEnd("\")
    $processEntries = @($env:Path -split ";" | Where-Object { $_ })
    if (-not ($processEntries | Where-Object { $_.TrimEnd("\") -ieq $normalized })) {
        $env:Path = "$normalized;$env:Path"
    }

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $userEntries = @($userPath -split ";" | Where-Object { $_ })
    if ($userEntries | Where-Object { $_.TrimEnd("\") -ieq $normalized }) {
        return $false
    }

    $newUserPath = if ([string]::IsNullOrWhiteSpace($userPath)) {
        $normalized
    } else {
        "$userPath;$normalized"
    }
    [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
    return $true
}

function Add-VaultCandidate([System.Collections.Generic.List[string]]$Candidates, [string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }
    try {
        $resolved = [System.IO.Path]::GetFullPath(
            [Environment]::ExpandEnvironmentVariables($Path)
        )
    } catch {
        return
    }
    if (-not (Test-Path -LiteralPath $resolved -PathType Container)) {
        return
    }
    if (-not (Test-Path -LiteralPath (Join-Path $resolved ".obsidian") -PathType Container) -and
        -not (Test-Path -LiteralPath (Join-Path $resolved ".paperflow\config.toml") -PathType Leaf)) {
        return
    }
    if (-not ($Candidates | Where-Object { $_ -ieq $resolved })) {
        $Candidates.Add($resolved)
    }
}

function Find-Vaults {
    $candidates = [System.Collections.Generic.List[string]]::new()
    $activePointer = Join-Path $env:APPDATA "PaperFlow\active-vault"
    if (Test-Path -LiteralPath $activePointer -PathType Leaf) {
        Add-VaultCandidate $candidates (Get-Content -LiteralPath $activePointer -Raw).Trim()
    }

    $obsidianConfig = Join-Path $env:APPDATA "obsidian\obsidian.json"
    if (Test-Path -LiteralPath $obsidianConfig -PathType Leaf) {
        try {
            $obsidian = Get-Content -LiteralPath $obsidianConfig -Raw | ConvertFrom-Json
            foreach ($property in $obsidian.vaults.PSObject.Properties) {
                Add-VaultCandidate $candidates ([string]$property.Value.path)
            }
        } catch {
            Write-WarningMessage "Obsidian's vault list could not be read; continuing with common locations."
        }
    }

    foreach ($base in @("E:\Obsidian", [Environment]::GetFolderPath("MyDocuments"))) {
        if (-not [string]::IsNullOrWhiteSpace($base) -and
            (Test-Path -LiteralPath $base -PathType Container)) {
            Add-VaultCandidate $candidates $base
            Get-ChildItem -LiteralPath $base -Directory -ErrorAction SilentlyContinue | ForEach-Object {
                Add-VaultCandidate $candidates $_.FullName
            }
        }
    }
    return @($candidates)
}

function Request-Vault {
    $candidates = @(Find-Vaults)
    if ($candidates.Count -eq 1) {
        $answer = Read-Host "Use Obsidian Vault '$($candidates[0])'? [Y/n]"
        if ([string]::IsNullOrWhiteSpace($answer) -or $answer -match "^[Yy]") {
            return $candidates[0]
        }
    } elseif ($candidates.Count -gt 1) {
        for ($index = 0; $index -lt $candidates.Count; $index++) {
            Write-Host "  $($index + 1). $($candidates[$index])"
        }
        $selection = Read-Host "Choose a Vault number"
        $number = 0
        if ([int]::TryParse($selection, [ref]$number) -and
            $number -ge 1 -and $number -le $candidates.Count) {
            return $candidates[$number - 1]
        }
        Write-WarningMessage "That selection was not valid."
    }

    $entered = Read-Host "Obsidian Vault path"
    if ([string]::IsNullOrWhiteSpace($entered)) {
        throw "A Vault path is required. Run setup again with -Vault <path>."
    }
    return $entered.Trim().Trim('"')
}

trap {
    Write-Host ""
    Write-Failure $_.Exception.Message
    Write-Host ""
    Write-Host "Setup stopped. Fix the item above, then run setup-windows.ps1 again."
    exit 1
}

Write-Host "PaperFlow setup" -ForegroundColor Cyan

$repoRoot = (Get-Location).Path
$pyprojectPath = Join-Path $repoRoot "pyproject.toml"
$packagePath = Join-Path $repoRoot "src\paperflow\__init__.py"
if (-not (Test-Path -LiteralPath $pyprojectPath -PathType Leaf) -or
    -not (Test-Path -LiteralPath $packagePath -PathType Leaf)) {
    throw "This is not the PaperFlow repository. Open PowerShell in the PaperFlow repo and run the script again."
}
$pyproject = Get-Content -LiteralPath $pyprojectPath -Raw
$nameMatch = [regex]::Match($pyproject, '(?m)^name\s*=\s*"paperflow"')
$requiresMatch = [regex]::Match(
    $pyproject,
    '(?m)^requires-python\s*=\s*">=\s*([0-9.]+)"'
)
if (-not $nameMatch.Success -or -not $requiresMatch.Success) {
    throw "pyproject.toml does not look like a supported PaperFlow project."
}
$requiredPython = [version]$requiresMatch.Groups[1].Value
$venvPath = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

Write-Section "Python"
$pythonExe = $null
$pythonPrefix = @()
$pythonVersionText = $null
$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($null -ne $pyLauncher) {
    try {
        $candidateVersion = & $pyLauncher.Source -3.12 -c "import platform; print(platform.python_version())" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $pythonExe = $pyLauncher.Source
            $pythonPrefix = @("-3.12")
            $pythonVersionText = [string]$candidateVersion
        }
    } catch {}
}
if ($null -eq $pythonExe) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $pythonCommand) {
        try {
            $candidateVersion = & $pythonCommand.Source -c "import platform; print(platform.python_version())" 2>$null
            if ($LASTEXITCODE -eq 0) {
                $pythonExe = $pythonCommand.Source
                $pythonVersionText = [string]$candidateVersion
            }
        } catch {}
    }
}
if ($null -eq $pythonExe -and (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    $candidateVersion = & $venvPython -c "import platform; print(platform.python_version())" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $pythonExe = $venvPython
        $pythonVersionText = [string]$candidateVersion
    }
}
if ($null -eq $pythonExe) {
    throw "Python was not found. Install Python $requiredPython or newer from https://www.python.org/downloads/windows/, then run setup again."
}
$pythonVersion = [version]$pythonVersionText.Trim()
if ($pythonVersion -lt $requiredPython) {
    throw "Python $pythonVersion is too old. Install Python $requiredPython or newer, then run setup again."
}
Write-Ok "Python $pythonVersion"

Write-Section "PaperFlow"
if (-not (Test-Path -LiteralPath $venvPath -PathType Container)) {
    Write-Host "  Creating virtual environment..."
    & $pythonExe @pythonPrefix -m venv $venvPath
    Test-ExitCode "Creating .venv"
} elseif (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw ".venv exists but is incomplete. Move it aside or remove it, then run setup again."
}
$venvVersionText = & $venvPython -c "import platform; print(platform.python_version())"
Test-ExitCode "Checking .venv Python"
if ([version]$venvVersionText.Trim() -lt $requiredPython) {
    throw ".venv uses Python $venvVersionText. Recreate it with Python $requiredPython or newer."
}
Write-Ok "virtual environment"

Write-Host "  Installing PaperFlow..."
& $venvPython -m pip install --upgrade pip --disable-pip-version-check --quiet
Test-ExitCode "Upgrading pip"
& $venvPython -m pip install --editable $repoRoot --disable-pip-version-check --quiet
Test-ExitCode "Installing PaperFlow"
$paperflowVersion = (& $venvPython -c "import paperflow; print(paperflow.__version__)").Trim()
Test-ExitCode "Checking PaperFlow"
Write-Ok "installed $paperflowVersion"

$scriptsPath = Join-Path $venvPath "Scripts"
$pathAdded = Add-UserPathEntry $scriptsPath
if ($pathAdded) {
    Write-Ok "paperflow command added to your user PATH"
} else {
    Write-Ok "paperflow command already on your user PATH"
}

$paperflowExe = Join-Path $scriptsPath "paperflow.exe"
$zotExe = Join-Path $scriptsPath "zot.exe"
$zoteroExe = $null
$zoteroReady = $false
if ($SkipZotero) {
    Write-Section "Zotero"
    Write-WarningMessage "skipped by request"
} else {
    Write-Section "Zotero"
    $zoteroCandidates = @(
        "C:\Program Files\Zotero\zotero.exe",
        "C:\Program Files (x86)\Zotero\zotero.exe",
        (Join-Path $env:LOCALAPPDATA "Zotero\zotero.exe")
    )
    foreach ($candidate in $zoteroCandidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $zoteroExe = $candidate
            break
        }
    }
    if ($null -eq $zoteroExe) {
        $runningZotero = Get-Process zotero -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -ne $runningZotero -and $runningZotero.Path) {
            $zoteroExe = $runningZotero.Path
        }
    }

    if ($null -eq $zoteroExe) {
        Write-WarningMessage "Zotero was not found. Install it from https://www.zotero.org/download/, then run setup again."
    } else {
        Write-Ok $zoteroExe
        if ($null -eq (Get-Process zotero -ErrorAction SilentlyContinue)) {
            Write-Host "  Opening Zotero..."
            Start-Process -FilePath $zoteroExe
            Start-Sleep -Seconds 5
        } else {
            Write-Ok "running"
        }

        if (-not (Test-Path -LiteralPath $zotExe -PathType Leaf)) {
            Write-WarningMessage "zot.exe was not installed. Re-run setup after checking the pip error output."
        } else {
            & $zotExe init
            if ($LASTEXITCODE -ne 0) {
                Write-WarningMessage "zot init needs attention. Follow its instructions, then run setup again."
            }
            $pingOutput = & $zotExe ping 2>&1
            if ($LASTEXITCODE -eq 0) {
                $zoteroReady = $true
                Write-Ok "bridge ready"
            } else {
                Write-WarningMessage "Zotero ping was not fully ready. PaperFlow doctor will perform the final check."
                if ($pingOutput) {
                    $pingOutput | Select-Object -Last 3 | ForEach-Object { Write-Host "    $_" }
                }
            }
        }
    }
}

Write-Section "Codex"
$codexReady = $false
if ($SkipCodex) {
    Write-WarningMessage "skipped by request"
} else {
    $codexCommand = Get-Command codex -ErrorAction SilentlyContinue
    if ($null -eq $codexCommand) {
        Write-WarningMessage "Codex CLI was not found."
        $installCodex = Read-Host "Install Codex CLI now? [Y/n]"
        if ([string]::IsNullOrWhiteSpace($installCodex) -or $installCodex -match "^[Yy]") {
            Write-Host "  Running the official OpenAI Windows installer..."
            Invoke-RestMethod "https://chatgpt.com/codex/install.ps1" | Invoke-Expression
            $codexBin = Join-Path $env:LOCALAPPDATA "Programs\OpenAI\Codex\bin"
            if (Test-Path -LiteralPath $codexBin -PathType Container) {
                if (-not (($env:Path -split ";") | Where-Object { $_.TrimEnd("\") -ieq $codexBin.TrimEnd("\") })) {
                    $env:Path = "$codexBin;$env:Path"
                }
            }
            $codexCommand = Get-Command codex -ErrorAction SilentlyContinue
        }
    }
    if ($null -ne $codexCommand) {
        $codexVersion = (& $codexCommand.Source --version 2>&1 | Select-Object -First 1)
        Write-Ok $codexVersion
        $codexReady = $true
    } else {
        Write-WarningMessage "Codex CLI is not available in this terminal. Open a new PowerShell window and run 'codex --version'."
    }
}

Write-Section "Obsidian"
$vaultInput = if ([string]::IsNullOrWhiteSpace($Vault)) { Request-Vault } else { $Vault }
$vaultPath = [System.IO.Path]::GetFullPath(
    [Environment]::ExpandEnvironmentVariables($vaultInput.Trim().Trim('"'))
)
Write-Host "  Initializing $vaultPath..."
& $paperflowExe init $vaultPath
Test-ExitCode "Initializing PaperFlow"
Write-Ok $vaultPath

Write-Section "Doctor"
& $paperflowExe doctor --vault $vaultPath
$doctorReady = $LASTEXITCODE -eq 0
if ($doctorReady) {
    Write-Ok "all checks passed"
} else {
    Write-WarningMessage "Some optional checks need attention; use the guidance above and run 'paperflow doctor' again."
}

Write-Host ""
Write-Host "PaperFlow Windows setup complete" -ForegroundColor Green
Write-Host ""
Write-Ok "Python $pythonVersion"
Write-Ok "PaperFlow $paperflowVersion"
if ($SkipZotero) {
    Write-WarningMessage "Zotero skipped"
} elseif ($zoteroReady) {
    Write-Ok "Zotero bridge"
} else {
    Write-WarningMessage "Zotero needs attention"
}
Write-Ok "Vault: $vaultPath"
if ($SkipCodex) {
    Write-WarningMessage "Codex CLI skipped"
} elseif ($codexReady) {
    Write-Ok "Codex CLI"
} else {
    Write-WarningMessage "Codex CLI needs a new terminal or manual follow-up"
}

Write-Host ""
Write-Host "Ready." -ForegroundColor Green
if ($pathAdded) {
    Write-WarningMessage "Open a new PowerShell window once so the 'paperflow' command is available there."
}
Write-Host ""
Write-Host "Use:"
Write-Host ""
Write-Host "  paperflow sync" -ForegroundColor Cyan
Write-Host ""
Write-Host "Research:"
Write-Host ""
Write-Host "  cd `"$vaultPath`""
Write-Host "  codex" -ForegroundColor Cyan
