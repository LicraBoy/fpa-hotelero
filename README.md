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
.venv\Scripts\python -m pytest      # API, reglas de negocio y seguridad

cd ..\frontend
npm run e2e                              # navegador real (Playwright)
```
La primera vez, `npx playwright install chromium` descarga el navegador de pruebas. Las pruebas de navegador usan sus propios puertos (8101 y 5181) y una base temporal.
Una de las pruebas lee el Excel real de Torres si lo encuentra en la carpeta de documentos (o en la ruta de `FPA_DATOS_REALES`); si no, se salta.

## API principal (`/api/v1`, con `X-Usuario-Dev` solo en desarrollo)
| Método y ruta | Para qué |
|---|---|
| `GET /yo`, `GET /hoteles`, `GET /hoteles/{id}` | Quién soy y a qué hoteles tengo acceso |
| `POST /hoteles/{id}/cargas` | Subir un CON130 o el Excel del Variance (`fuente`, `confirmar_reemplazo`, `periodos`) |
| `GET /hoteles/{id}/cargas`, `GET /hoteles/{id}/cargas/{carga}` | Cargas y su reporte de calidad |
| `GET /hoteles/{id}/reporte/estructura` | Estructura vigente del reporte Variance (secciones, líneas, orden, tipo) |
| `POST /hoteles/{id}/reporte/importar` | Importar el Excel del Variance: estructura, reglas de suma y un borrador de mapeo (`periodo_referencia`, `confirmar_reemplazo`) |
| `GET /hoteles/{id}/mapeo/versiones`, `…/{version}`, `…/{version}/validacion?periodo=` | Versiones del mapeo, sus vínculos y exclusiones, y el reporte de validación |
| `POST /hoteles/{id}/mapeo/versiones` | Crear un borrador copiando la versión aprobada |
| `PUT`/`DELETE …/mapeo/versiones/{version}/vinculos` y `/exclusiones` | Editar el borrador (cuenta ↔ línea con signo; cuentas excluidas con motivo) |
| `POST …/mapeo/versiones/{version}/aprobar` · `/descartar` | Aprobar (solo contralor; 409 si quedan cuentas con movimiento sin mapear) o descartar un borrador |
| `POST /hoteles/{id}/budget/importar` | Cargar el Budget del Excel del Variance como versión inmutable (`periodo_corte`, `ano_fiscal`, `confirmar_reemplazo`) |
| `GET /hoteles/{id}/budget/versiones`, `…/{version}` | Versiones del Budget y sus cifras por línea (mes, YTD, anual) |
| `GET /hoteles/{id}/variance?periodo=AAAA-MM` | Variance del periodo (mes, YTD y anual: Actual, Budget, Variance y %), con el mapeo aprobado y el Budget vigente (`version_mapeo_id`, `version_plan_id` opcionales; filtros `seccion_id`, `tipo`, `q`) |
| _(demostración)_ `python -m fpa.demo_agosto --datos <carpeta>` | Carga el agosto real en la base de **desarrollo** para revisarlo con Contraloría (ver `docs/GUIA_PRUEBA_CONTRALORIA.md`) |
| `GET /hoteles/{id}/variance/exportar?periodo=` | Descarga el Variance en Excel (mismo formato que el reporte; acepta los filtros de la pantalla) |
| `GET /hoteles/{id}/variance/lineas/{linea}/desglose?periodo&bloque=mes\|ytd` | Qué hay detrás de una cifra: las cuentas de una línea o los componentes de un total (permiso `drilldown:leer`) |
| `GET /hoteles/{id}/variance/cuentas/{codigo}/movimientos?periodo&bloque&cursor&limite` | Movimientos de una cuenta, paginados por cursor |
| `GET /hoteles/{id}/asientos/{asiento}?periodo` | Las líneas de un asiento |
| `POST /hoteles/{id}/catalogo/importar` | Importar el catálogo oficial de Novohit (CON020, `.xls`) |
| `GET /hoteles/{id}/catalogo/arbol` | Árbol de cuentas con nombres, Deudor/Acreedor, departamento y SAT |
| `GET /hoteles/{id}/saldos?periodo=AAAA-MM` | Saldo por cuenta del periodo |
| `GET /hoteles/{id}/auditoria` | Bitácora (contralor y auditoría) |

Documentación interactiva en http://localhost:8100/docs

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
