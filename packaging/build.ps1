# Build the Windows app (G207 / G138).
#
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
#
# Output: dist\ScholarPathAI\ScholarPathAI.exe (with its _internal folder).
# The build is verified afterwards: the bundle audit must pass.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$spec = Join-Path $PSScriptRoot "scholarpath.spec"
$audit = Join-Path $PSScriptRoot "verify_bundle.py"

if (-not (Test-Path $python)) {
    throw "No project venv found. Create it first: python -m venv .venv"
}

Write-Host "Installing the build tool..."
& $python -m pip install --quiet --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Could not install pyinstaller." }

Write-Host "Building ScholarPathAI (this takes a few minutes)..."
& $python -m PyInstaller $spec --noconfirm --clean --log-level WARN
if ($LASTEXITCODE -ne 0) { throw "The build failed." }

Write-Host "Auditing the bundle..."
& $python $audit
if ($LASTEXITCODE -ne 0) { throw "The bundle audit failed - do not ship this build." }

$exe = Join-Path $root "dist\ScholarPathAI\ScholarPathAI.exe"
Write-Host ""
Write-Host "Done: $exe"
Write-Host "User data, config and logs stay in %APPDATA%\ScholarPath - never in the build."
