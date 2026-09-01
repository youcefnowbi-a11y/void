Write-Host "===============================================================================" -ForegroundColor Red
Write-Host "                   [ VOIDFORGE :: FIELD OPS - POSTE DE COMMANDE ]" -ForegroundColor DarkRed
Write-Host "===============================================================================" -ForegroundColor Red
Write-Host ""
Write-Host "[*] Demarrage des composants..." -ForegroundColor Yellow

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Start Backend
$backendJob = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootDir'; python -m uvicorn web.backend.server:app --host 127.0.0.1 --port 8000" -PassThru -WindowStyle Minimized
Write-Host "[+] Backend FastAPI demarre (Port 8000)" -ForegroundColor Green

Start-Sleep -Seconds 2

# Start Frontend
$frontendDir = Join-Path $RootDir "web\frontend"
$frontendJob = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendDir'; npm run dev" -PassThru -WindowStyle Minimized
Write-Host "[+] Frontend Vite demarre (Port 5173)" -ForegroundColor Green

Start-Sleep -Seconds 3

# Launch Browser
Write-Host "[*] Ouverture de l'interface..." -ForegroundColor Cyan
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "[+] VOIDFORGE OPERATIONNEL : http://localhost:5173" -ForegroundColor Green
