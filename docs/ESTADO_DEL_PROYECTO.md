# Estado del proyecto

Última actualización: 01-oct-2026

## Fase actual
**Fase 1 — Data Hub: Actuals: HECHA** (sub-fases 1.0 a 1.9; la 1.9 es el **catálogo oficial de cuentas**, reporte CON020 de Novohit). Además tiene **frontend de la Fase 1** y **pruebas de navegador con Playwright**. **Fase 2 — Catálogo corporativo y mapeo: en curso** (2.1 y 2.2 hechas; sigue 2.3).

## Avance por fase
| Fase | Estado |
|---|---|
| Blueprint funcional v1.1 | Hecho, aprobado por Contraloría |
| Arquitectura técnica v1.0 | Hecha (`docs/Arquitectura_Tecnica_FPA_Hotelero.md`) |
| 0 Repositorio full stack (alcance básico) | **Hecha** |
| **1 Data Hub: Actuals** | **Hecha** |
| 2 Catálogo corporativo y mapeo | **En curso** (2.1 y 2.2 hechas) |
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
| 1.9 Catálogo oficial de cuentas (CON020 `.xls`: nombres de la jerarquía, TIPO, departamento, grupo, SAT; `POST /catalogo/importar`; migración `0006`) | **Hecha** |

### Sub-fases de la Fase 2
| Sub-fase | Estado |
|---|---|
| 2.1 Estructura del reporte (`fpa/ingesta/variance_estructura.py`, `VersionEstructuraReporte` + `LineaReporte`, migración `0007`, `importar_estructura_reporte`) | **Hecha** |
| 2.2 Reglas de suma (`variance_reglas.py`, `ReglaSumaLinea`, migración `0008`, `evaluar_totales` pura) | **Hecha** |
| 2.3 Mapeo · 2.4 Validación · 2.5 Versionado · 2.6 API | Pendientes |

## Frontend (Fase 1) y pruebas de navegador
- Pantallas: **Cargas** (subir CON130 o Variance, aviso de reemplazo con confirmación, lista de cargas y su reporte de calidad), **Catálogo** (árbol con búsqueda), **Saldos** (por mes, con total exacto) y **Auditoría**. Cada rol ve solo sus secciones.
- Modo desarrollo: el usuario se elige en un selector (cabecera `X-Usuario-Dev`); se reemplazará por el inicio de sesión corporativo.
- Importes siempre como texto exacto y sumas en centavos (`BigInt`); nunca `number`.
- `cd frontend` y `npm run e2e`: **11 pruebas de Playwright pasan**. Levantan su propio backend limpio (8101, base temporal) y frontend (5181); no tocan la base ni los puertos de desarrollo.
- `npm run build` y `npm run lint` sin errores.

## Cómo verificar
- **Pruebas:** `cd backend` y `.venv\Scripts\python -m pytest` → **265 pasan y 1 se salta** (la migración en PostgreSQL, hasta definir `FPA_TEST_POSTGRES_URL`).
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
- **Catálogo oficial (CON020, 30/09/2026):** 1,238 cuentas y 68 títulos con nombre. Cubre las 366 cuentas del CON130 de septiembre (nombres idénticos) y 209 de las 296 del Variance; **87 cuentas del Variance no están** (se avisan). Resuelve los 50 títulos que el CON130 no traía con nombre.
- **El catálogo acumula entre meses:** cada CON020 es una foto mensual; las cuentas de catálogos anteriores se conservan y solo se avisa cuáles no vienen en el nuevo.
- **El signo del Variance es la naturaleza de la cuenta (TIPO):** en las fórmulas del Excel toda cuenta Acreedor se resta (16/16) y toda Deudor se suma (187/187). Validado con una prueba; falta la confirmación de Contraloría.
- **Departamentos:** los grupos de 4 dígitos de la clase 6 del catálogo son los departamentos del Variance (6009 Gerencia y Recepción, 6010 Ama de Llaves, 6011 Contabilidad, 6014 Restaurante, 6005 Bar…) y `DEPTO EdoFro` coincide con las secciones del reporte donde viene lleno.
- **Puerto Vallarta:** catálogo propio por hotel; al llegar, se crea copiando el de Torres (~70 % coincide) y se ajusta (Fase 11).
- Novohit exporta la Ñ como `¥` en algunos nombres; se corrige al leer (`DUE¥OS` → `DUEÑOS`).
- Mapeo de cuentas: el que está en el Excel (columnas X a AJ de la hoja `Ago`).
- Budget: se carga tal como viene en el Excel de agosto como una versión; el origen real sigue pendiente.

- **Estructura del reporte (2.1):** la hoja `Ago` se lee por posición (B = código corporativo o título de sección, C = descripción/total, D = Actual solo para distinguir filas informativas). Real: 512 líneas = 409 detalle + 24 secciones + 24 totales + 17 subtotales + 38 informativas (tipo de cambio, resumen de Commercial Services, bloque de notas con importe 0). Una fila con cifras y sin nombre (395, un porcentaje) se ignora con aviso. Una estructura **vigente por hotel**; reimportar otro archivo pide confirmación y deja la anterior como `reemplazada`. La `clave` de línea es **provisional** (orden + descripción) hasta que Contraloría confirme la clave natural. Aún sin API ni pantalla (la API del mapeo es 2.6).

- **Reglas de suma (2.2):** se leen de las fórmulas de la columna S de `Ago` con un analizador propio (solo `SUM(rango)`, sumas y restas de celdas; nunca se evalúa texto). 45 reglas (totales y subtotales) que, con los importes pegados de la columna D, reproducen todos los totales del Excel (diferencia < 0.05). Sin regla: 2 filas "Allocated" (576 y 577) que no traen fórmula. La clasificación de la 2.1 se afinó: una fila con importe y fórmula en S es subtotal/total (p. ej. PUERTO VALLARTA, fila 535); ahora son 26 totales + 21 subtotales + 32 informativas.

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
**Fase 2.3:** importar el mapeo línea ↔ cuentas con su signo desde las fórmulas S/T de `Ago`. Después (mapeo desde las columnas X a AJ con su signo), 2.4 a 2.6. Antes, confirmar con Contraloría la clave única de una línea y el origen del Budget (el signo ya lo respalda el TIPO de cuenta del catálogo oficial).
