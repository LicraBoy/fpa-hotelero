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

REM Backend: aplica migraciones, siembra datos de desarrollo y arranca. FPA_ENTORNO=desarrollo
REM habilita la identidad de desarrollo (cabecera X-Usuario-Dev); NUNCA usarlo fuera de local.
start "FPA backend (8100)" cmd /k "cd /d %RAIZ%backend && set FPA_ENTORNO=desarrollo&& .venv\Scripts\alembic.exe upgrade head && .venv\Scripts\python.exe -m fpa.semilla && .venv\Scripts\python.exe -m uvicorn fpa.main:app --reload --port 8100"
start "FPA frontend (5180)" cmd /k "cd /d %RAIZ%frontend && npm run dev"

REM Espera a que la API responda (migrar + sembrar tarda unos segundos) antes de abrir el navegador.
set INTENTOS=0
:esperar
curl -s -o nul http://127.0.0.1:8100/api/health && goto listo
set /a INTENTOS+=1
if %INTENTOS% GEQ 40 goto listo
timeout /t 1 /nobreak >nul
goto esperar
:listo
start "" http://localhost:5180
endlocal
