# Gera o executavel do Windows: dist\PainelF1.exe (um arquivo so, com o icone e o menu).
# Uso:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

uv sync --group build
uv run --group build pyinstaller --noconfirm --clean --onefile --windowed `
    --name PainelF1 `
    --icon icone.ico `
    --add-data "web;web" `
    --add-data "icone.ico;." `
    --distpath dist --workpath build `
    server.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }

$exe = Join-Path $PSScriptRoot "dist\PainelF1.exe"
$mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "Pronto: $exe ($mb MB)"
