@echo off
REM Levanta el backend (puerto 8100) y el frontend (puerto 5180) en dos ventanas.
REM No cierra procesos de otros sistemas. Requiere backend\.venv y frontend\node_modules.
setlocal
set RAIZ=%~dp0

if not exist "%RAIZ%backend\.venv\Scripts\python.exe" (
  echo Falta el entorno del backend. Ejecuta primero:
  echo   cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)
if not exist "%RAIZ%frontend\node_modules" (
  echo Falta instalar el frontend. Ejecuta primero:
  echo   cd frontend ^&^& npm install
  pause
  exit /b 1
)

start "FPA backend (8100)" cmd /k "cd /d %RAIZ%backend && .venv\Scripts\python.exe -m uvicorn fpa.main:app --reload --port 8100"
start "FPA frontend (5180)" cmd /k "cd /d %RAIZ%frontend && npm run dev"

timeout /t 6 /nobreak >nul
start "" http://localhost:5180
endlocal
