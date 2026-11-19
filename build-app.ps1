# Gera o app nativo: app\target\release\PainelF1.exe (um arquivo so, portatil).
# 1) compila o nucleo Python com o PyInstaller (build.ps1 -> dist\PainelF1.exe)
# 2) compila o app Rust/Tauri com o nucleo embutido
# Uso:  powershell -ExecutionPolicy Bypass -File build-app.ps1
# Precisa do Rust (rustup) e do Visual Studio Build Tools com C++.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

& "$PSScriptRoot\build.ps1"
if ($LASTEXITCODE -ne 0) { throw "falhou o nucleo" }

$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
$env:PAINELF1_NUCLEO = Join-Path $PSScriptRoot "dist\PainelF1.exe"
Push-Location app
try {
    cargo build --release
    if ($LASTEXITCODE -ne 0) { throw "falhou o app" }
} finally {
    Pop-Location
    Remove-Item Env:\PAINELF1_NUCLEO
}

$exe = Join-Path $PSScriptRoot "app\target\release\PainelF1.exe"
$mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "Pronto: $exe ($mb MB)"
