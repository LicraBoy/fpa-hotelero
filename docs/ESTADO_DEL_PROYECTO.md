# Estado del proyecto

Última actualización: 30-sep-2026

## Fase actual
**Fase 1 — Data Hub: Actuals (en curso).** Sub-fase terminada: **1.0 Cimientos de datos**. Siguiente: **1.1 (ampliación del lector del CON130: contrato común y títulos de jerarquía)**.

## Avance por fase
| Fase | Estado |
|---|---|
| Blueprint funcional v1.1 | Hecho, aprobado por Contraloría |
| Arquitectura técnica v1.0 | Hecha (`docs/Arquitectura_Tecnica_FPA_Hotelero.md`) |
| 0 Repositorio full stack (alcance básico) | **Hecha** |
| **1 Data Hub: Actuals** | **En curso** |
| 2 a 14 | Pendientes |

### Sub-fases de la Fase 1
| Sub-fase | Estado |
|---|---|
| 1.0 Cimientos de datos (Alembic, organización/hotel/usuario/rol, identidad de desarrollo, aislamiento, `Dinero`) | **Hecha** |
| 1.1 Lector CON130 (base hecha; falta contrato común y títulos de jerarquía) | En curso |
| 1.2 Lector del Excel de Variance | Pendiente |
| 1.3 Persistencia de cargas | Pendiente |
| 1.4 Idempotencia, reemplazo y auditoría | Pendiente |
| 1.5 Calidad de datos | Pendiente |
| 1.6 Catálogo local | Pendiente |
| 1.7 Saldos mensuales | Pendiente |
| 1.8 API de carga segura | Pendiente |

## Cómo verificar
- **Pruebas:** `cd backend` y `.venv\Scripts\python -m pytest` → **54 pasan y 1 se salta** (la migración en PostgreSQL, hasta definir `FPA_TEST_POSTGRES_URL`).
- **Calidad:** `.venv\Scripts\ruff check .`, `.venv\Scripts\ruff format --check .`, `.venv\Scripts\mypy fpa` → sin errores.
- **Migraciones:** `.venv\Scripts\alembic upgrade head` y `downgrade base` (la prueba automática también verifica que modelos y migraciones no se desvíen).
- **Datos de desarrollo:** `.venv\Scripts\python -m fpa.semilla` crea la organización Torres, el hotel y 5 usuarios `@torres.local`. `iniciar_servidores.bat` hace migrar + sembrar + arrancar con `FPA_ENTORNO=desarrollo`.
- **Identidad de desarrollo:** cabecera `X-Usuario-Dev: analista@torres.local` (solo con `FPA_ENTORNO=desarrollo`).
- **Verificado en vivo (puerto libre):** sin cabecera 401; analista `/yo` 200; `/hoteles` solo su hotel; hotel inexistente 404; usuario falso 401.
- **CON130 de septiembre 2026 (BASE DATOS):** 7,242 movimientos, 366 cuentas, Débito = Crédito = 57,835,193.08, las 366 cuentas cuadran con su fila "Total".

## Decisiones tomadas
- Stack mínimo: Python + FastAPI + SQLite (pruebas); React + TypeScript + Vite (ADR 0001).
- Dinero exacto también en SQLite con el tipo `Dinero`; sumas en Python con `Decimal` (ADR 0002).
- Una carga vigente por (hotel, periodo); idempotencia por hash; 401/403/404 por reglas de aislamiento; identidad de desarrollo cerrada por defecto (ADR 0003).
- `ruff` + `mypy` estricto desde la Fase 1; **un commit de git por sub-fase** (decidido por el usuario).
- Puertos propios 8100 (API) y 5180 (web). Ningún Excel real vive en el repositorio.
- Playwright se usará, diferido hasta tener pantallas reales (Fase 4, o antes si se prefiere).
- El Saldo anterior del CON130 no entra al cálculo (confirmado por Contraloría).
- Caso de prueba del MVP: Variance de agosto 2026; septiembre es la segunda prueba.
- La hoja "Base de Datos" del Variance se arma igual que el CON130 (confirmado); contiene **julio y agosto** (3,583 + 3,277 = 6,860 movimientos) solo de cuentas de resultados, por lo que **Débito ≠ Crédito** en esa fuente.
- Las filas repetidas exactas son legítimas (5 en el Variance, 14 en el CON130): generan aviso, no rechazo.
- Mapeo de cuentas: el que está en el Excel (columnas X a AJ de la hoja `Ago`).
- Budget: se carga tal como viene en el Excel de agosto como una versión; el origen real sigue pendiente.

## Pendientes y avisos
- No hay servidor remoto de código; lo define TI.
- La prueba de migración en PostgreSQL existe pero se salta: no hay PostgreSQL disponible en esta máquina.
- Advertencia conocida de Starlette sobre `httpx` en las pruebas (no afecta).
- El Blueprint en `docs/` contiene cifras agregadas de Torres; si el repositorio se comparte fuera de la empresa, revisar antes.
- Si `iniciar_servidores.bat` ya estaba abierto antes de la 1.0, hay que cerrarlo y volver a abrirlo para que aplique `FPA_ENTORNO=desarrollo`; sin eso la API responde 401.

## Preguntas abiertas
Ver sección 11 de la arquitectura (TI: alojamiento, identidad, PostgreSQL/Oracle, respaldos, antivirus; Contraloría: origen del Budget, convención de signo y año fiscal, árbol de departamentos y centros de costo, quién exporta el CON130, si Puerto Vallarta usa el mismo Novohit).

## Siguiente paso
**1.1:** mover `Movimiento`/`Cuenta` a `fpa/ingesta/contrato.py` (con `cantidad` y `costo` opcionales) y hacer que el lector del CON130 devuelva también los títulos de jerarquía. Después 1.2 a 1.8 en orden.
