# Gera o executavel do Windows e o pacote para a release:
#   dist\PainelF1\                pasta pronta para usar (PainelF1.exe + atalhos)
#   dist\PainelF1-windows.zip     o mesmo, zipado, para anexar na release
# Uso:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

uv sync --group build
uv run --group build pyinstaller --noconfirm --clean --onedir --console `
    --name PainelF1 `
    --add-data "web;web" `
    --distpath dist --workpath build `
    server.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }

# atalhos e instrucoes ao lado do .exe
Copy-Item pacote\* dist\PainelF1\ -Force

$zip = Join-Path $PSScriptRoot "dist\PainelF1-windows.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory((Join-Path $PSScriptRoot "dist\PainelF1"), $zip,
    [IO.Compression.CompressionLevel]::Optimal, $true)
$mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host "Pronto: $zip ($mb MB)"
