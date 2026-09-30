# CLAUDE.md — Plataforma FP&A e Inteligencia Hotelera (Torres Mazatlán)

Puerta de entrada para cualquier sesión nueva. Repositorio: `C:\Users\mzamora\Desktop\fpa-hotelero`.

## Qué es el proyecto
Plataforma SaaS de FP&A para hoteles, independiente de PMS/ERP/POS. Primer hotel: **Torres Mazatlán**; después **Puerto Vallarta**. Núcleo del MVP: **Actual vs Budget, Variance, YTD, Annual Budget, comentarios y drill-down**. Board y el caso Scandic son solo *referencia funcional*: no se copia su código, interfaz, textos ni modelos.

## Lee esto primero, en orden
1. `docs/ESTADO_DEL_PROYECTO.md` — en qué fase va el proyecto y qué sigue.
2. `docs/Arquitectura_Tecnica_FPA_Hotelero.md` — stack, arquitectura, seguridad, pruebas y fases (0 a 14).
3. `docs/CAMBIOS_FUTUROS_DE_TECNOLOGIA.md` — qué es provisional hoy y cómo cambiará (base de datos, Docker, autenticación, etc.).
4. `docs/Blueprint_Funcional_FPA_Hotelero_Torres_Mazatlan.docx` — requisitos funcionales aprobados por Contraloría.
5. `docs/contexto.md` — requerimientos originales. Decisiones técnicas en `docs/adr/`.

## Cómo correrlo
- Levantar todo: `iniciar_servidores.bat` (backend **8100**, frontend **5180**; no usar 8000/5173, son de otro sistema).
- Pruebas: `cd backend` y `.venv\Scripts\python -m pytest`. Calidad: `.venv\Scripts\ruff check .`, `.venv\Scripts\ruff format --check .` y `.venv\Scripts\mypy fpa` (deben quedar sin errores).
- Pruebas de navegador: `cd frontend` y `npm run e2e` (Playwright; backend propio en 8101, base temporal). Siempre correrlas al tocar pantallas; `npm run build` y `npm run lint` deben quedar sin errores.
- Base de datos: `.venv\Scripts\alembic upgrade head` (migraciones) y `.venv\Scripts\python -m fpa.semilla` (datos de desarrollo). Si cambias un modelo, genera la migración con `alembic revision --autogenerate`.
- Identidad de desarrollo: `FPA_ENTORNO=desarrollo` y cabecera `X-Usuario-Dev: analista@torres.local` (por defecto el entorno es `produccion` y nadie entra).
- Primera vez: ver `README.md`.

## Reglas de trabajo
- **Nada de `float` para dinero**: `Decimal` en Python y `NUMERIC(18,2)` en base de datos.
- El cálculo financiero es **puro y determinístico**; la IA nunca calcula cifras.
- Stack actual **mínimo**: Python + FastAPI + SQLite (pruebas) y React + TypeScript + Vite. Las tecnologías nuevas (PostgreSQL, Docker, CI, OIDC, Playwright…) se hablan con TI antes de adoptarlas; el plan está en `docs/CAMBIOS_FUTUROS_DE_TECNOLOGIA.md`.
- No escribir SQL propio de un solo motor: todo acceso a datos pasa por SQLAlchemy.
- Seguridad por defecto: deny by default, aislamiento por organización y hotel, sin secretos ni datos reales de Torres en el repositorio.
- **No inventar procesos de Torres.** Marcar lo no confirmado como `[POR VALIDAR]`.
- El trabajo se hace **por fases**; no se abre una fase sin cerrar la anterior.
- **Una sub-fase no termina hasta actualizar `docs/ESTADO_DEL_PROYECTO.md`** y marcarla en la arquitectura.
- Git: **un commit por sub-fase** terminada (el usuario lo autorizó para la Fase 1), con mensaje en español. No subir a ningún servidor sin pedirlo.
- Respuestas al usuario: cortas y claras, en español.
- Este proyecto es independiente de `DataContabilidad\sistema-analisis-contable`; no usarlo como evidencia ni modificarlo.

## Datos de Torres (fuera del repositorio, solo lectura)
Carpeta: `C:\Users\mzamora\Desktop\PLATAFORMA FP&A E INTELIGENCIA HOTELERA\`. No copiar nada de ahí al repositorio.
- `BASE DATOS.xlsx` — reporte CON130 de Novohit, septiembre 2026 (7,242 movimientos, 366 cuentas, Débito = Crédito = 57,835,193.08).
- `02. VT August 2026 Variance (Envio) (1).xlsx` — Variance de agosto 2026, **prueba dorada del MVP**.
- `Prompt_Integracion_Variance.docx` — los 14 pasos manuales que la plataforma reemplaza.

## Código existente
- `backend/fpa/ingesta/novohit_con130.py` — lector del CON130 (máquina de estados; valida Débito = Crédito y total por cuenta).
- `backend/fpa/main.py`, `config.py`, `db.py`, `api/health.py` — API con `/api/health` y `/api/ready`.
- `backend/fpa/modelos/` (modelos y tipos `Dinero`/`Medida`), `backend/fpa/identidad/` (proveedor, permisos, dependencias), `backend/migraciones/` (Alembic, 0001 a 0005), `backend/fpa/semilla.py`.
- `backend/fpa/ingesta/` (contrato común y lectores CON130 y Variance), `backend/fpa/calidad/` (controles), `backend/fpa/servicios/` (`cargar_archivo`, catálogo, saldos, auditoría), `backend/fpa/repositorios/` (siempre acotados por hotel), `backend/fpa/seguridad/archivos.py` (validación de subidas), `backend/fpa/api/v1/` (rutas; ver README).
- Fase 1 terminada: cargar, validar y guardar movimientos con trazabilidad. Lo siguiente es la Fase 2 (líneas del reporte y mapeo de cuentas).
- `frontend/src/` — pantallas de la Fase 1 (Cargas, Catálogo, Saldos, Auditoría) en `componentes/`, cliente de la API en `api/`, importes exactos en `util/dinero.ts` (nunca `number`), permisos de interfaz en `permisos.ts` (solo para mostrar u ocultar; el servidor autoriza). Pruebas en `frontend/e2e/`.
