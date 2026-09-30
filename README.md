# Plataforma FP&A e Inteligencia Hotelera

Plataforma de FP&A para hoteles. Primer hotel: **Torres Mazatlán**. Núcleo del MVP: Actual vs Budget, Variance, YTD, Annual Budget, comentarios y drill-down.

> Para continuar el trabajo (personas o un chat nuevo): lee primero [`CLAUDE.md`](CLAUDE.md) y luego [`docs/ESTADO_DEL_PROYECTO.md`](docs/ESTADO_DEL_PROYECTO.md).

## Levantar el proyecto (Windows)

**Primera vez**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
cd ..\frontend
npm install
```

**Cada día:** doble clic en `iniciar_servidores.bat` (abre el backend, el frontend y el navegador).

| Servicio | Dirección |
|---|---|
| Web | http://localhost:5180 |
| API | http://localhost:8100 (documentación en `/docs`) |
| Salud | http://localhost:8100/api/health y `/api/ready` |

Los puertos 8100 y 5180 son propios de este proyecto; no chocan con otros sistemas.

## Pruebas
```powershell
cd backend
.venv\Scripts\python -m pytest
```
Una de las pruebas lee el Excel real de Torres si lo encuentra en la carpeta de documentos (o en la ruta de `FPA_DATOS_REALES`); si no, se salta.

## Estructura
```
backend/    API en Python (FastAPI). fpa/ingesta/ contiene el lector del CON130 de Novohit
frontend/   Web en React + TypeScript + Vite
docs/       Estado del proyecto, arquitectura, blueprint, decisiones (adr/) y cambios futuros
datos_prueba/   Solo datos sintéticos
```

## Reglas importantes
- **Nunca** se suben al repositorio Excel con datos reales de Torres, archivos `.env` ni bases `.db` (el `.gitignore` los excluye).
- El dinero se maneja con `Decimal`, nunca con `float`.
- La lista de tecnologías que cambiarán (base de datos, Docker, autenticación, etc.) está en [`docs/CAMBIOS_FUTUROS_DE_TECNOLOGIA.md`](docs/CAMBIOS_FUTUROS_DE_TECNOLOGIA.md).
