$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {

Write-Host "Building eiga-cli binary..."

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Error: uv is not installed." -ForegroundColor Red
    exit 1
}

uv sync
uv run pyinstaller --onefile --name eiga-cli main.py

$installDir = "$env:LOCALAPPDATA\Programs\eiga-cli"

New-Item -ItemType Directory -Force -Path $installDir | Out-Null

Copy-Item "dist\eiga-cli.exe" "$installDir\eiga-cli.exe" -Force

Write-Host "Installed to $installDir" -ForegroundColor Green
Write-Host ""
Write-Host "Add this directory to your PATH:"
Write-Host $installDir
} finally {
    Pop-Location
}
