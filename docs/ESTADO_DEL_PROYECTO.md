# Estado del proyecto

Última actualización: 30-sep-2026

## Fase actual
**Fase 1 — Data Hub: Actuals: HECHA** (sub-fases 1.0 a 1.8). Siguiente: **Fase 2 — Catálogo corporativo y mapeo** (líneas del reporte Variance y mapeo de cuentas locales a líneas).

## Avance por fase
| Fase | Estado |
|---|---|
| Blueprint funcional v1.1 | Hecho, aprobado por Contraloría |
| Arquitectura técnica v1.0 | Hecha (`docs/Arquitectura_Tecnica_FPA_Hotelero.md`) |
| 0 Repositorio full stack (alcance básico) | **Hecha** |
| **1 Data Hub: Actuals** | **Hecha** |
| 2 Catálogo corporativo y mapeo | Por iniciar |
| 3 a 14 | Pendientes |

### Sub-fases de la Fase 1
| Sub-fase | Estado |
|---|---|
| 1.0 Cimientos de datos (Alembic, organización/hotel/usuario/rol, identidad de desarrollo, aislamiento, `Dinero`) | **Hecha** |
| 1.1 Lector CON130 con contrato común (`fpa/ingesta/contrato.py`) y títulos de jerarquía | **Hecha** |
| 1.2 Lector del Excel de Variance (`fpa/ingesta/variance_base_datos.py`) | **Hecha** |
| 1.3 Persistencia de cargas (`CargaArchivo`, `Movimiento`, migración `0002`, `registrar_carga`) | **Hecha** |
| 1.4 Idempotencia, reemplazo con confirmación y auditoría (`cargar_archivo`, `EventoAuditoria`, migración `0003`) | **Hecha** |
| 1.5 Calidad de datos (`fpa/calidad/evaluacion.py`; el reporte se guarda en cada carga) | **Hecha** |
| 1.6 Catálogo local (`CuentaLocal`, migración `0004`, árbol acumulado, `GET /api/v1/hoteles/{id}/catalogo/arbol`) | **Hecha** |
| 1.7 Saldos mensuales (`SaldoMensualCuenta`, migración `0005`, `recalcular_saldos`, `GET /api/v1/hoteles/{id}/saldos?periodo=`) | **Hecha** |
| 1.8 API de carga segura (`POST /cargas`, `GET /cargas`, `GET /cargas/{id}`, `GET /auditoria`; `fpa/seguridad/archivos.py`) | **Hecha** |

## Cómo verificar
- **Pruebas:** `cd backend` y `.venv\Scripts\python -m pytest` → **195 pasan y 1 se salta** (la migración en PostgreSQL, hasta definir `FPA_TEST_POSTGRES_URL`).
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
- Los importes negativos existen legítimamente (257 en el CON130 y 92 en el Variance: reversos y ajustes): aviso, no error.
- El primer número del asiento (`9.2.15`) coincide con el mes de la fecha en el 100 % de los asientos de ambos archivos: se controla como aviso.
- Un mismo código puede ser a la vez cuenta con movimientos y título de grupo (`4002007`: cuenta en julio–agosto, título en septiembre): el catálogo guarda `con_movimientos` y `es_titulo` por separado. Las subcuentas con punto (`X.NNN`) cuelgan de su código base si se conoce.
- Existe una línea sin Débito ni Crédito en el Variance (fila 4389, "INCENTIVOS CHEF", agosto): se conserva en cero con aviso; **por confirmar con Contraloría** si es un cero o un dato faltante.
- Mapeo de cuentas: el que está en el Excel (columnas X a AJ de la hoja `Ago`).
- Budget: se carga tal como viene en el Excel de agosto como una versión; el origen real sigue pendiente.

## Pendientes y avisos
- No hay servidor remoto de código; lo define TI.
- **Salida de la Fase 1 verificada por la API con los Excel reales** (también en vivo con el servidor): CON130 septiembre = 7,242 movimientos (57,835,193.08); Variance = 3,583 (julio) + 3,277 (agosto); repetir un archivo no cambia nada; 366 saldos de septiembre; catálogo con 145 títulos + 554 cuentas con movimientos; un usuario de otro hotel recibe 404 en todo.
- Riesgo residual de la subida de archivos: hoy no hay límite de tasa ni antivirus (ver `CAMBIOS_FUTUROS_DE_TECNOLOGIA.md`).
- La prueba de migración en PostgreSQL existe pero se salta: no hay PostgreSQL disponible en esta máquina.
- Advertencia conocida de Starlette sobre `httpx` en las pruebas (no afecta).
- El Blueprint en `docs/` contiene cifras agregadas de Torres; si el repositorio se comparte fuera de la empresa, revisar antes.
- Si `iniciar_servidores.bat` ya estaba abierto antes de la 1.0, hay que cerrarlo y volver a abrirlo para que aplique `FPA_ENTORNO=desarrollo`; sin eso la API responde 401.

## Preguntas abiertas
Ver sección 11 de la arquitectura (TI: alojamiento, identidad, PostgreSQL/Oracle, respaldos, antivirus; Contraloría: origen del Budget, convención de signo y año fiscal, árbol de departamentos y centros de costo, quién exporta el CON130, si Puerto Vallarta usa el mismo Novohit).

## Siguiente paso
**Fase 2.1:** importar de la hoja `Ago` del Variance la estructura del reporte (secciones, líneas, orden, tipo detalle/subtotal/total) como `linea_reporte`; 409 líneas de detalle en agosto. Después 2.2 (reglas de suma), 2.3 (mapeo desde las columnas X a AJ con su signo), 2.4 a 2.6. Antes, confirmar con Contraloría las preguntas de signo, clave única de línea y origen del Budget.
