# Changelog

## Fase 1 (en curso)

### 1.2 — Lector del Excel de Variance (2026-09-30)
- `fpa/ingesta/variance_base_datos.py`: lee la hoja "Base de Datos" (julio + agosto) por nombre de columna, tolerando los caracteres dañados de Débito/Crédito.
- Sin control Débito = Crédito (es un subconjunto de cuentas de resultados). Cantidad y costo se conservan con todos sus decimales.
- Avisos (no errores): mes en texto distinto al de la fecha, cuenta con dos nombres, movimiento sin importe (fila 4389).
- Prueba dorada: 6,860 movimientos (3,583 julio + 3,277 agosto), 296 cuentas, Débito 12,650,614.04 y Crédito 12,037,735.88.
- Pruebas: 76 pasan y 1 se salta.

### 1.1 — Contrato común de lectura (2026-09-30)
- `fpa/ingesta/contrato.py`: `Movimiento` (con `cantidad` y `costo` opcionales), `Cuenta`, `Titulo`, `ResultadoLectura` (periodos, rango de fechas, `controla_balance`) y `Fuente`.
- `fpa/ingesta/utilidades.py`: conversiones comunes (montos con comas, fechas dd/mm/aaaa).
- El lector del CON130 devuelve también los 145 títulos de la jerarquía de cuentas.
- Pruebas: 62 pasan y 1 se salta.

### 1.0 — Cimientos de datos (2026-09-30)
- Herramientas de calidad: `ruff` (estilo) y `mypy` estricto, configurados en `backend/pyproject.toml`.
- Modelos `Organizacion`, `Hotel`, `Usuario`, `Rol`, `Asignacion` y el tipo `Dinero` (decimales exactos también en SQLite).
- Alembic con la migración `0001`; prueba de que sube, baja y no se desvía de los modelos.
- Identidad: proveedor de desarrollo (cabecera `X-Usuario-Dev`), cerrado por defecto (`FPA_ENTORNO=produccion`).
- Permisos por rol y dependencias `principal_actual` y `hotel_autorizado` (401 / 403 / 404).
- Endpoints `GET /api/v1/yo`, `GET /api/v1/hoteles`, `GET /api/v1/hoteles/{id}`.
- `python -m fpa.semilla` (idempotente) y `iniciar_servidores.bat` ahora migra, siembra y arranca.
- ADR 0002 (dinero en SQLite) y ADR 0003 (carga vigente por periodo, aislamiento e identidad de desarrollo).
- Pruebas: 54 pasan y 1 se salta (migración en PostgreSQL).

## 0.1.0 — 2026-09-30 (Fase 0)
- Repositorio creado con estructura backend / frontend / docs / datos_prueba.
- Backend: FastAPI con `GET /api/health` y `GET /api/ready`, SQLite por configuración, CORS limitado al frontend local.
- Lector del reporte CON130 de Novohit (`backend/fpa/ingesta/novohit_con130.py`) trasladado al repositorio.
- Frontend: React + TypeScript + Vite con una pantalla que consulta la API.
- `iniciar_servidores.bat` para levantar todo en local (puertos 8100 y 5180).
- Documentación viva: `CLAUDE.md`, estado del proyecto, arquitectura, blueprint, ADR 0001 y cambios futuros de tecnología.
- Pruebas: 17 pasan (13 del lector del CON130 incluida la del archivo real, 4 de salud y CORS).
