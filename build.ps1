# Gera o nucleo Python num executavel: dist\PainelF1.exe (um arquivo so). O build-app.ps1 embute ele no app.
# Uso:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

uv sync --group build
uv run --group build pyinstaller --noconfirm --clean --onefile --windowed `
    --name PainelF1 `
    --icon app\icons\icon.ico `
    --add-data "web;web" `
    --distpath dist --workpath build `
    nucleo\server.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }

$exe = Join-Path $PSScriptRoot "dist\PainelF1.exe"
$mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "Pronto: $exe ($mb MB)"
