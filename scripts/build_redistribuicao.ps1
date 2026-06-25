<#
.SYNOPSIS
    Build + redistribuição do Spreadhunter via PyInstaller com criptografia.
    Saída no Desktop. Sem PyArmor.
#>

$ErrorActionPreference = "Stop"
$PY313 = "C:\Program Files\Python313\python.exe"
$ROOT = Split-Path -Parent $PSScriptRoot
$DESKTOP = [Environment]::GetFolderPath("Desktop")

Set-Location -LiteralPath $ROOT

Write-Host "=== Limpando ===" -ForegroundColor Cyan
Remove-Item -Recurse -Force "$DESKTOP/Spreadhunter" -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Directory "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "=== Rodando PyInstaller ===" -ForegroundColor Cyan
& $PY313 -m PyInstaller --clean `
    --distpath "$DESKTOP/dist" `
    --workpath "$DESKTOP/build_pyi" `
    spreadhunter.spec
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller falhou!" -ForegroundColor Red
    exit 1
}

Remove-Item -Recurse -Force "$DESKTOP/Spreadhunter" -ErrorAction SilentlyContinue
Move-Item "$DESKTOP/dist/Spreadhunter" "$DESKTOP/Spreadhunter"
Remove-Item -Recurse -Force "$DESKTOP/dist", "$DESKTOP/build_pyi" -ErrorAction SilentlyContinue

Write-Host "=== Pós-build ===" -ForegroundColor Cyan

@"
# Credenciais opcoes.net.br (preencha com seus dados)
OPCOESNET_CPF=SEU_CPF_AQUI
OPCOESNET_SENHA=SUA_SENHA_AQUI
"@ | Out-File -FilePath "$DESKTOP/Spreadhunter/.env.example" -Encoding utf8

@"
╔══════════════════════════════════════════════════════╗
║              SPREADHUNTER v0.1.0                     ║
║     B3 Options Trading Monitor (Desktop)             ║
╚══════════════════════════════════════════════════════╝

COMO USAR:
  1. Execute Spreadhunter.exe
  2. Na primeira execução o banco é criado automaticamente
  3. Copie .env.example → .env e preencha suas credenciais
  4. Conecte o Profit (RTD) e inicie o monitoramento

ATALHOS:
  Ctrl+Shift+F  → Pipeline (funil de filtros)
  ⚡ Importar   → Importar opções do Profit
"@ | Out-File -FilePath "$DESKTOP/Spreadhunter/INSTRUCOES.txt" -Encoding utf8

Write-Host "=== Compactando ===" -ForegroundColor Cyan
$versao = "0.1.0"
$zipName = "Spreadhunter_v${versao}.zip"
Compress-Archive -Path "$DESKTOP/Spreadhunter/*" -DestinationPath "$DESKTOP/$zipName" -Force

Write-Host "========================================" -ForegroundColor Green
Write-Host "Build concluído!" -ForegroundColor Green
Write-Host "Pasta: $DESKTOP/Spreadhunter/" -ForegroundColor Green
Write-Host "ZIP:   $DESKTOP/$zipName" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
