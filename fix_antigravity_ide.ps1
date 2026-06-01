# Fix Antigravity IDE - Remove conflito com v2.0
$targetDir = "$env:LOCALAPPDATA\Programs\Antigravity\resources"
$appDir = Join-Path $targetDir "app"
$appAsar = Join-Path $targetDir "app.asar"

if (Test-Path $appDir) {
    Rename-Item -Path $appDir -NewName "app.bak" -Force
    Write-Host "[+] app -> app.bak" -ForegroundColor Green
}
if (Test-Path $appAsar) {
    Rename-Item -Path $appAsar -NewName "app.asar.bak" -Force
    Write-Host "[+] app.asar -> app.asar.bak" -ForegroundColor Green
}
Write-Host "[+] Fix aplicado. Pode abrir o Antigravity IDE novamente." -ForegroundColor Cyan
