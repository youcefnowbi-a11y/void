@echo off
title VOIDFORGE - Lanceur Operationnel
color 0C
echo ===============================================================================
echo                    [ VOIDFORGE :: FIELD OPS - POSTE DE COMMANDE ]
echo ===============================================================================
echo.
echo [*] Demarrage des modules backend et frontend...
echo.

:: Verifier que Python est disponible
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Erreur: Python n'est pas installe ou n'est pas dans le PATH.
    pause
    exit /b 1
)

:: Demarrage du Backend FastAPI dans une fenetre separee
echo [*] Lancement du Backend FastAPI (port 8000)...
start "VOIDFORGE Backend" /min cmd /c "python -m uvicorn web.backend.server:app --host 127.0.0.1 --port 8000"

:: Attente courte pour le demarrage du backend
timeout /t 2 /nobreak >nul

:: Demarrage du Frontend Vite dans une fenetre separee
echo [*] Lancement du Frontend React/Vite (port 5173)...
cd web\frontend
start "VOIDFORGE Frontend" /min cmd /c "npm run dev"
cd ..\..

:: Attente que Vite soit pret puis ouverture du navigateur
timeout /t 3 /nobreak >nul
echo [*] Ouverture de l'interface dans le navigateur...
start http://localhost:5173

echo.
echo ===============================================================================
echo  [+] SYSTEME ARME ET OPERATIONNEL : http://localhost:5173
echo  [+] Fermez cette fenetre ou appuyez sur une touche pour terminer.
echo ===============================================================================
pause
