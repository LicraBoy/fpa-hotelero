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

REM Migraciones + datos de desarrollo primero (una sola vez; el vigilante solo arranca uvicorn).
REM FPA_ENTORNO=desarrollo habilita la identidad de desarrollo (cabecera X-Usuario-Dev); NUNCA
REM usarlo fuera de local.
set FPA_ENTORNO=desarrollo
pushd "%RAIZ%backend"
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m fpa.semilla
popd

REM Cada servidor corre bajo un "vigilante": si se cuelga al arrancar, se topa con el puerto
REM ocupado, o se cae, se reinicia solo. El registro queda en la carpeta logs\.
set "VIG=powershell -NoProfile -ExecutionPolicy Bypass -File "%RAIZ%scripts\vigilante.ps1""
start "Vigilante - backend" %VIG% -Nombre backend -Directorio backend -Archivo ".venv\Scripts\python.exe" -Argumentos "-m uvicorn fpa.main:app --reload --port 8100" -Url http://127.0.0.1:8100/api/health
start "Vigilante - frontend" %VIG% -Nombre frontend -Directorio frontend -Archivo "cmd.exe" -Argumentos "/c npm run dev" -Url http://127.0.0.1:5180/

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
