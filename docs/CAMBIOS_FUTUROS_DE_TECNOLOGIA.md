# Cambios futuros de tecnología

La Fase 0 usa **lo mínimo para levantar el servidor**. Este documento dice qué cambiará después, cuándo y cómo, para hablarlo con TI y con Contraloría **antes** de hacerlo. Ningún cambio de esta lista se hace sin avisar y sin aprobación.

Estados: `[DECIDIDO]` ya definido · `[PROPUESTA]` recomendación técnica · `[POR VALIDAR]` depende de TI o Contraloría.

## 1. Base de datos (el cambio más importante)

| | Hoy (Fase 0) | Futuro |
|---|---|---|
| Motor | **SQLite** (`sqlite:///./fpa_dev.db`) `[DECIDIDO]` para desarrollo y pruebas | **PostgreSQL 16+** en staging y producción `[PROPUESTA]`. Oracle solo si la política de TI lo exige `[POR VALIDAR]` |
| Dónde se configura | Variable `FPA_DATABASE_URL` en `backend/.env` | La misma variable |
| Migraciones | No hay tablas de negocio todavía | **Alembic** desde la sub-fase 1.0 |

**Cómo se hará el cambio a PostgreSQL**
1. Instalar el driver (`psycopg[binary]`) y cambiar `FPA_DATABASE_URL` a `postgresql+psycopg://usuario:clave@servidor:5432/fpa`.
2. Agregar Alembic y crear la primera migración (sub-fase 1.0). Las tablas se crean con migraciones, no con `create_all`.
3. Correr **las mismas pruebas en SQLite y en PostgreSQL**. SQLite puede ocultar diferencias (tipos, bloqueos, `ON CONFLICT`).
4. Usar `NUMERIC(18,2)` para dinero. En Python siempre `Decimal`, nunca `float`.
5. Para el aislamiento entre hoteles, activar **Row Level Security** en PostgreSQL (SQLite no lo tiene; se prueba solo ahí).

**Qué no hay que hacer desde hoy:** escribir SQL propio de un solo motor, ni usar funciones exclusivas de SQLite. Todo acceso pasa por SQLAlchemy.

## 2. Resto de cambios previstos

| Tema | Hoy | Futuro | Cuándo `[PROPUESTA]` |
|---|---|---|---|
| Arranque | `iniciar_servidores.bat` (dos ventanas) | **Docker Compose** (API + PostgreSQL + frontend) | Cuando TI defina dónde se aloja; a más tardar en la Fase 6 |
| Servidor de la API | `uvicorn --reload` (solo desarrollo) | Gunicorn con workers de Uvicorn detrás de un proxy con TLS (Nginx o Traefik) | Staging y producción |
| Integración continua | Ninguna | CI con lint, tipos, pruebas en SQLite y PostgreSQL, `bandit`, `pip-audit`, `npm audit`, `gitleaks` | En cuanto exista el repositorio remoto que indique TI |
| Calidad de código | Solo pruebas (`pytest`) | `ruff`, `mypy` estricto, ESLint y `pre-commit` | Al inicio de la Fase 1 (es barato y conviene temprano) |
| Pruebas end-to-end | **Playwright** ya en uso (10 pruebas, Chromium) con backend propio y Excel sintéticos | Sumar Firefox/WebKit, comparación visual y `axe` (accesibilidad); correrlas en la integración continua | Al montar el CI |
| Autenticación | No hay (todo abierto, solo local) | OIDC con el proveedor de identidad de la empresa y MFA | Antes de exponer la plataforma a cualquier usuario; Fase 5 como máximo, `[POR VALIDAR con TI]` |
| Autorización | No hay | Roles por hotel, deny by default, pruebas de matriz rol × endpoint | Fase 1.0 (base) y Fase 5 (completo) |
| Separación por hotel | No hay | `organizacion_id` y `hotel_id` en cada tabla + RLS | Fase 1.0 |
| Migraciones | No hay | Alembic | Fase 1.0 |
| Tareas en segundo plano | No hay | Cola sobre PostgreSQL (Procrastinate); Celery + Redis solo si el volumen lo exige | Cuando una carga o exportación tarde demasiado |
| Caché | No hay | Caché de reportes por clave (hotel, versiones, periodo); Redis solo si hace falta | Fase 4 (rendimiento) |
| Lectura de `.xls` | `xlrd` 2.0.2 (solo lectura, solo para el catálogo CON020) | Si Novohit ofrece exportar el catálogo como `.xlsx` o `.csv`, se puede retirar `xlrd`; si TI ve riesgo en el formato binario antiguo, revisar con ellos | Al definir las políticas de seguridad con TI |
| Archivos subidos | `storage/` local, validaciones de tamaño, ZIP, macros y rutas (hecho en 1.8) | Antivirus (p. ej. ClamAV) `[POR VALIDAR con TI]`, límite de tasa por usuario, almacenamiento de objetos y cifrado en reposo, cuotas | Fase 6 / antes de producción |
| Secretos | Archivo `.env` local (no se sube) | Gestor de secretos de TI | Antes de producción |
| Auditoría | Bitácora de solo inserción, reforzada por la aplicación (`AuditoriaInmutable`) | En PostgreSQL: quitar UPDATE/DELETE al usuario de la aplicación y encadenar hashes entre eventos | Fase 5.5 / antes de producción |
| Observabilidad | Logs de consola | Logs JSON con `request_id`, métricas y alertas (OpenTelemetry, Prometheus, Grafana) | Fase 6 |
| Respaldos | No aplica | Respaldos cifrados y restauración probada | Fase 6 |
| Componentes del frontend | Solo React + CSS propio | Una librería MIT (Mantine o MUI), TanStack Query, TanStack Table, cliente API generado desde OpenAPI | Fase 4 |
| Lenguaje del backend | Python | Se mantiene; Java/Spring solo si TI lo exige `[POR VALIDAR]` | — |
| Inicio de sesión | Usuarios locales: `argon2id` + TOTP + sesión en cookie `HttpOnly` (ADR 0005, Fase 5.1) `[DECIDIDO, avisar a TI]`; dependencias nuevas `argon2-cffi` y `pyotp` | OIDC con el proveedor de la empresa si TI lo ofrece (se agrega otro `ProveedorIdentidad`); `FPA_COOKIE_SEGURA=true` detrás de HTTPS | Cuando TI lo defina |

## 3. Avisos técnicos conocidos de hoy
- Al correr las pruebas aparece una advertencia de Starlette sobre `httpx` (se sugiere `httpx2`). No afecta el funcionamiento; se revisa al actualizar dependencias.
- El frontend se creó con la plantilla actual de Vite (React 19, TypeScript 6, Vite 8). Las versiones quedan fijas en `package-lock.json`.

## 4. Regla para el equipo
Antes de cambiar cualquiera de estas piezas: (1) se habla con TI/Contraloría, (2) se registra la decisión en `docs/adr/`, (3) se actualiza este documento y `docs/ESTADO_DEL_PROYECTO.md`.

## 5. Fórmulas y reglas de negocio (no son tecnología, pero no deben perderse)
Las fórmulas de Variación, %, Actual, Budget y tipo de cambio de la sub-fase 4.12 están registradas en
`docs/FORMULAS_Y_REGLAS_DEL_VARIANCE.md`. Cualquier cambio de motor, de base de datos o de lector de Excel debe
conservar esos resultados (las pruebas doradas de Mazatlán los protegen).
