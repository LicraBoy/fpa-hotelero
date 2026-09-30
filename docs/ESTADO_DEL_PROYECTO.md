# Estado del proyecto

Última actualización: 30-sep-2026

## Fase actual
**Fase 0 — Crear el repositorio del proyecto full stack: HECHA.** Siguiente: **Fase 1.0 — Cimientos de datos** (migraciones, organización/hotel/usuario/rol, prueba de aislamiento).

## Avance por fase
| Fase | Estado |
|---|---|
| Blueprint funcional v1.1 | Hecho, aprobado por Contraloría |
| Arquitectura técnica v1.0 | Hecha (`docs/Arquitectura_Tecnica_FPA_Hotelero.md`) |
| **0 Repositorio full stack (alcance básico)** | **Hecha** |
| 1 Data Hub: Actuals | En parte: 1.1 lector del CON130 hecho |
| 2 a 14 | Pendientes |

### Sub-fases de la Fase 0
| Sub-fase | Estado |
|---|---|
| 0.1 Crear el repositorio (`git init`, `.gitignore`) | Hecho (sin commits todavía) |
| 0.2 Estructura backend / frontend / docs / datos_prueba | Hecho |
| 0.3 Traer el lector del CON130 con sus pruebas | Hecho |
| 0.4 Backend básico (FastAPI, SQLite, `/api/health`, `/api/ready`) | Hecho |
| 0.5 Frontend básico (React + TypeScript + Vite, proxy a la API) | Hecho |
| 0.6 Script para levantar todo (`iniciar_servidores.bat`) | Hecho |
| 0.7 Documentación viva (CLAUDE.md, estado, ADR, cambios futuros, README, CHANGELOG) | Hecho |
| Docker, CI, pre-commit/ruff/mypy, Playwright, PostgreSQL | **Diferidos a propósito** a `docs/CAMBIOS_FUTUROS_DE_TECNOLOGIA.md` |

## Cómo verificar
- **Pruebas:** `cd backend` y `.venv\Scripts\python -m pytest` → **17 pasan** (13 del lector del CON130, incluida la del archivo real; 4 de salud y CORS).
- **Servidores:** se levantaron ambos; `GET http://localhost:8100/api/health` y `/api/ready` responden OK, y el frontend en `http://localhost:5180` llega a la API por el proxy. `npm run build` compila sin errores.
- **Septiembre 2026 (BASE DATOS):** 7,242 movimientos, 366 cuentas, Débito = Crédito = 57,835,193.08, las 366 cuentas cuadran con su fila "Total".

## Decisiones tomadas
- Stack mínimo: Python + FastAPI + SQLite (pruebas); React + TypeScript + Vite (ADR 0001).
- Puertos propios 8100 (API) y 5180 (web), para no chocar con otros sistemas.
- Repositorio separado de la carpeta de documentos de Torres; ningún Excel real vive en el repositorio.
- Playwright se usará, pero se difiere hasta tener pantallas reales (o antes si se prefiere).
- El Saldo anterior del CON130 no entra al cálculo (confirmado por Contraloría).
- Caso de prueba del MVP: Variance de agosto 2026; septiembre es la segunda prueba.
- La hoja "Base de Datos" del Variance se arma igual que el CON130 (confirmado).
- Mapeo de cuentas: el que está en el Excel (columnas X a AJ de la hoja `Ago`), armado por el contralor.
- Budget: se carga tal como viene en el Excel de agosto como una versión; el origen real sigue pendiente.

## Pendientes y avisos
- El repositorio no tiene commits todavía (se hacen cuando el usuario lo pida).
- No hay servidor remoto de código; lo define TI.
- Advertencia conocida de Starlette sobre `httpx` en las pruebas (no afecta).
- El Blueprint en `docs/` contiene cifras agregadas de Torres; si el repositorio se comparte fuera de la empresa, revisar antes.

## Preguntas abiertas
Ver sección 11 de la arquitectura (TI: alojamiento, identidad, PostgreSQL/Oracle, respaldos, antivirus; Contraloría: origen del Budget, convención de signo y año fiscal, árbol de departamentos y centros de costo, quién exporta el CON130, si Puerto Vallarta usa el mismo Novohit).

## Siguiente paso
**Fase 1.0 — Cimientos de datos:** Alembic con primera migración; modelos `organizacion`, `hotel`, `usuario`, `rol`; dependencia que exige contexto de tenant; prueba de aislamiento. Antes: acordar con el usuario si se agregan `ruff`/`mypy`/`pre-commit` (sugerido al inicio de la Fase 1).
