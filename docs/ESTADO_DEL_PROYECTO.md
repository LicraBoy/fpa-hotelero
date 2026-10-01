# Estado del proyecto

Última actualización: 01-oct-2026

## Fase actual
**Fase 1 — Data Hub: Actuals: HECHA** (sub-fases 1.0 a 1.9; la 1.9 es el **catálogo oficial de cuentas**, reporte CON020 de Novohit). Además tiene **frontend de la Fase 1** y **pruebas de navegador con Playwright**. **Fase 2 — Catálogo corporativo y mapeo: sub-fases 2.1 a 2.6 HECHAS; falta la aprobación de Contraloría** (ver Pendientes). **Fase 3 — Motor de Variance: sub-fases 3.1 a 3.7 hechas** (agosto reproducido con 19 excepciones documentadas; septiembre sin referencia de Contraloría todavía).

## Avance por fase
| Fase | Estado |
|---|---|
| Blueprint funcional v1.1 | Hecho, aprobado por Contraloría |
| Arquitectura técnica v1.0 | Hecha (`docs/Arquitectura_Tecnica_FPA_Hotelero.md`) |
| 0 Repositorio full stack (alcance básico) | **Hecha** |
| **1 Data Hub: Actuals** | **Hecha** |
| 2 Catálogo corporativo y mapeo | **Código listo** (2.1 a 2.6); falta aprobación de Contraloría |
| 3 Motor de Variance | **Código listo** (3.1 a 3.7); falta el Excel de septiembre de Contraloría |
| 4 a 14 | Pendientes |

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
| 2.3 Mapeo línea ↔ cuenta (`variance_mapeo.py`, `VersionMapeo` + `MapeoLineaCuenta`, migración `0009`, `importar_mapeo`, `discrepancias_de_signo`) | **Hecha** |
| 2.4 Validación del mapeo (`servicios/validacion_mapeo.py`, `validar_mapeo` → `ReporteMapeo`) | **Hecha** |
| 2.5 Versionado y aprobación (`servicios/versionado_mapeo.py`, `CuentaExcluidaMapeo`, migración `0010`) | **Hecha** |
| 2.6 API del mapeo (`api/v1/mapeo.py`, permisos `reporte:leer`, `mapeo:leer`, `mapeo:editar`, `mapeo:aprobar`) | **Hecha** |

### Sub-fases de la Fase 3
| Sub-fase | Estado |
|---|---|
| 3.1 Budget como versión inmutable (`VersionPlan` + `LineaPlan`, migración `0011`, `servicios/budget.py`, `api/v1/budget.py`) | **Hecha** |
| 3.2 Motor de Actual (`calculo/actual.py` pura, `servicios/actual.py`) | **Hecha** |
| 3.3 YTD y año fiscal (`calculo/ano_fiscal.py`, `calculo/ytd.py`, `actual_ytd_del_periodo`) | **Hecha** |
| 3.4 Totales y subtotales (`calculo/totales.py`: `evaluar_totales` movido aquí, `completar_con_totales`) | **Hecha** |
| 3.5 Variance y Variance % (`calculo/variance.py`) | **Hecha** |
| 3.6 Prueba dorada de agosto (`calculo/motor.py`, `servicios/variance.py`, `GET /hoteles/{id}/variance`, `tests/test_variance_dorada.py`) | **Hecha, con 19 excepciones documentadas** |
| 3.7 Segunda prueba: septiembre (`tests/test_variance_septiembre.py`: consistencia del YTD, Budget no inventado, validación; arnés de diferencia cero) | **Hecha el arnés; falta el Excel de septiembre** |

## Frontend (Fase 1) y pruebas de navegador
- Pantallas: **Cargas** (subir CON130 o Variance, aviso de reemplazo con confirmación, lista de cargas y su reporte de calidad), **Catálogo** (árbol con búsqueda), **Saldos** (por mes, con total exacto) y **Auditoría**. Cada rol ve solo sus secciones.
- Modo desarrollo: el usuario se elige en un selector (cabecera `X-Usuario-Dev`); se reemplazará por el inicio de sesión corporativo.
- Importes siempre como texto exacto y sumas en centavos (`BigInt`); nunca `number`.
- `cd frontend` y `npm run e2e`: **11 pruebas de Playwright pasan**. Levantan su propio backend limpio (8101, base temporal) y frontend (5181); no tocan la base ni los puertos de desarrollo.
- `npm run build` y `npm run lint` sin errores.

## Cómo verificar
- **Pruebas:** `cd backend` y `.venv\Scripts\python -m pytest` → **408 pasan y 2 se saltan y 1 se salta** (la migración en PostgreSQL, hasta definir `FPA_TEST_POSTGRES_URL`).
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

- **Mapeo (2.3):** se lee de las fórmulas S (Actual) y T (Budget) de `Ago`, no de las columnas X a AJ (Excel pierde el cero final de `4002001.010`). Real: 304 vínculos a 302 cuentas en 263 líneas = **253 con fórmula en S y T** (las que cita el plan) + **10 solo en T** (tienen Budget y Actual 0 en agosto; se importan). Signo −1 en 31 vínculos y +1 en 273. **Contra el catálogo oficial: 0 discrepancias de signo** en las 210 cuentas que sí están en él; 92 cuentas del mapeo no están en el catálogo (se avisan, se siguen vinculando). El mapeo se importa como **borrador** (`VersionMapeo`, un solo borrador por hotel; otro importe pide confirmación y descarta el anterior). Aprobación y edición: 2.5.

- **Validación (2.4):** solo mira cuentas de resultados (clases 4, 5, 6) con neto ≠ 0 y devuelve: sin mapear (**bloqueante**), cuentas en varias líneas (informativo), sin catálogo, discrepancias de signo y líneas sin cuentas. **Hallazgo real:** en julio y agosto, `4002013` (−20,000) y `4003003` (≈ −2.9 y −3.2 millones) tienen movimientos y ninguna línea de `Ago` las toma (existen como hojas de trabajo pero ningún total las cita). Todo lo demás cuadra y no hay discrepancias de signo. La prueba real fija ese resultado; **pregunta abierta a Contraloría** (ver `FASES_FUTURAS.md`). Para poder aprobar mientras tanto, la 2.5 permite registrar una cuenta como **excluida a propósito**, con motivo y auditoría.

- **Versionado (2.5):** estados `borrador` → `aprobada` → `reemplazada` (o `descartada`); un borrador y una aprobada por hotel, también por índice en la base. Solo se edita un borrador (agregar/quitar vínculo, cambiar signo, excluir cuenta); una aprobada lanza `VersionInmutable` y se cambia copiándola a un borrador nuevo (`crear_borrador_desde`). `aprobar` valida contra todos los periodos con movimientos y se bloquea si queda una cuenta con movimiento sin mapear; para dejar una fuera **a propósito** se registra como cuenta excluida (motivo, usuario, fecha; queda en la bitácora). Con los Excel reales, excluir `4002013` y `4003003` permite aprobar el mapeo de agosto; esa exclusión es provisional hasta la respuesta de Contraloría.

- **API del mapeo (2.6):** 11 rutas bajo `/api/v1/hoteles/{id}` (ver README). Permisos: analista lee y edita; **solo el contralor aprueba**; dirección y auditoría leen; el responsable de área solo ve la estructura del reporte. Hotel ajeno 404, sin permiso 403, sin sesión 401, versión aprobada 409. `POST /reporte/importar` sube el Excel del Variance (mismas defensas de archivo que las cargas: sin macros, sin zip bombs, límites de tamaño), importa estructura + reglas + un **borrador** de mapeo y no escribe nada hasta confirmar lo que reemplaza. Real por API: 409 detalle, 45 reglas, 263 líneas y 304 vínculos. Sin pantalla todavía (el frontend del mapeo no está en la Fase 2). Matriz rol × endpoint y aislamiento por hotel en `tests/test_api_mapeo.py`.

- **Budget (3.1):** `POST /hoteles/{id}/budget/importar` carga el Budget pegado en el Excel (mes = columna E, YTD = J, anual = O) como `VersionPlan` **inmutable**: no existe forma de editarla; reimportar otro archivo del mismo año fiscal pide confirmación y deja la anterior como `reemplazada`. Real: 400+ líneas, idénticas al Excel celda por celda. **Se guarda con 6 decimales** (`Medida`, no `Dinero`) porque el Budget del Excel trae decimales de más (`20639.6489456203`) y recortarlo a centavos movería los totales; los reportes redondean al mostrar. Tres filas con cifras y sin nombre (395, 520, 528) se ignoran con aviso. Permisos nuevos `budget:leer`, `budget:importar` y `variance:leer` (analista y contralor importan; dirección y auditoría leen). El año fiscal por omisión sale del corte (agosto 2026 → `2026/27`, **julio–junio por validar**).

- **Motor de Actual (3.2):** `calcular_actual(vinculos, netos)` = Σ signo × (Débito − Crédito) por línea; pura, `Decimal`, sin base de datos. Propiedades con `hypothesis`: invertir los signos invierte el resultado, la suma de las líneas = Σ de los vínculos con signo, el orden de entrada no importa y es lineal en los netos. `servicios/actual.py` lee los saldos del periodo y el mapeo **aprobado** (o la versión que se indique; sin mapeo aprobado es error, no un cero silencioso).

- **YTD y año fiscal (3.3):** `periodos_ytd(periodo, mes_inicio=7)` da los meses del año fiscal hasta el corte (julio–junio; `mes_inicio=1` = año calendario; **julio–junio por validar con Contraloría**). `acumular_ytd` suma línea por línea y devuelve `sin_datos`: un mes sin carga cuenta como 0 **y se informa**, para que el reporte avise que el acumulado está incompleto. Fronteras probadas: primer mes (julio), cierre (junio, 12 meses), cruce de año (enero) y mes sin datos.

- **Totales (3.4):** el evaluador de reglas pasó a `fpa/calculo/totales.py` (puro; `servicios/reglas_suma.py` lo re-exporta). **Corrección a la 2.1/2.2 que destapó la prueba real:** las 13 filas de Commercial Services de la forma `=S438` (Money Exchg Inc, Bar Income, Restrnt Expenses…) estaban clasificadas como "informativas" y quedaban sin regla; ahora son subtotales (vínculos) y las reglas pasaron de 45 a 58, así que Total Income, Total Expenses, Profit, Allocations y Net Profit Commercial Services ya se calculan. **Budget:** los totales calculados con las reglas coinciden con los pegados en el Excel (mes, YTD y anual, tolerancia 0.01). **Actual de agosto:** quedan 10 totales con diferencia en el mes y 5 en el YTD, todos explicados y fijados en `tests/test_totales.py` (25 ← fila 12; 294, 336, 533, 535, 573 ← cuentas fuera del Base de Datos; 451, 495, 497, 507 ← centavos). Un total que aparezca o desaparezca de esa lista hace fallar la prueba.

- **Variance y % (3.5):** `variance(actual, budget, convención)` y `variance_pct` puros. **Convención favorable-positivo** (`[POR VALIDAR]`): ingresos y utilidades `Actual − Budget`, gastos `Budget − Actual`; se **deduce** sin tabla (detalle: signo mayoritario de sus cuentas de resultados, clases 4 a 6 — una cuenta de pasivo como el IVA por pagar no vuelve ingreso a la línea; sin cuentas: mayoría de su sección; total: su primer componente positivo) y se corrige con `excepciones` por línea. **% = Var / Budget con el signo del Budget** (así lo hace el Excel en ~970 celdas; `base_absoluta=True` da Var / |Budget|, por validar); Budget 0 → +1, −1 o 0 según el Variance (nunca error); sin Budget → `None`. Contra el Excel real (más de 600 comparaciones mes y YTD) la deducción coincide en todo salvo **fila 8** (tipo de cambio, no es dinero) y **fila 344 Telephone Profit** (el Excel la trata como gasto aunque es una utilidad; **pregunta para Contraloría**).

- **Prueba dorada de agosto (3.6):** `calcular_variance` arma el reporte completo (mes, YTD y anual: Actual, Budget, Variance y %) y `GET /hoteles/{id}/variance?periodo=` lo entrega (importes a centavos, % a 6 decimales; permiso `variance:leer`). Contra la hoja `Ago` se comparan **5,822 celdas** (columnas D a Q de todas las líneas): cuadran todas salvo **19 líneas**, fijadas con su causa en `tests/test_variance_dorada.py` (una diferencia fuera de esa lista, o una excepción que deje de serlo, falla la prueba). De las 263 líneas con cuentas, **256 cuadran en las 12 columnas** (tolerancia 0.10 en importes —el Excel acumula centavos en sus columnas de control— y 1e-5 relativo en %). **Causas:** (a) el Base de Datos no trae el dato: fila 12 (el Excel deja fuera 5,000), IVA Taxes y Lodging Tax (cuentas de pasivo), Bank Commissions, Audit Fees e Income Taxes (cuentas corporativas), y los totales que arrastran (25, 294, 336, 533, 535, 573); Administration Fee y las dos "Allocated" (valores pegados sin fórmula); tipo de cambio (no es dinero); un residuo de un centavo en Employee Dining; (b) convenciones del Excel distintas de la regla general: Telephone Profit (344) se trata como gasto y el % de NET PROFIT COMMERCIAL SERVICES (530) usa |Budget|. **Hallazgo:** el Budget del mes y del YTD solo es válido para el corte del archivo; para otro periodo el motor devuelve solo el anual y avisa (nunca un cero inventado). **Corrección a lo dicho antes:** el YTD de las 10 líneas "solo en T" **sí** coincide con el Excel (incluye julio); no es una diferencia.

- **Septiembre (3.7):** no hay Variance ni Budget de septiembre de Contraloría, así que **no se puede probar la "diferencia cero" de septiembre**; el arnés (`test_septiembre_contra_el_excel_de_contraloria`) se activa solo cuando haya un `*Variance*Sep*.xlsx` en la carpeta de datos reales. Con el CON130 de septiembre cargado se prueba lo que sí se puede: el acumulado julio–septiembre es **exactamente** el de agosto más el mes de septiembre en cada línea; el Budget del mes y del YTD no se inventa (solo el anual, con aviso); agosto no cambia al cargar septiembre. **Hallazgos:** (1) el mapeo de agosto no conoce **154 cuentas con movimiento en septiembre** (cuentas nuevas como `4001006.x` y `4003001.010`, un ingreso de ≈ 4.6 millones): hay que ampliar el mapeo con Contraloría antes de dar por bueno el Variance de septiembre, y la validación ya lo bloquea; (2) el CON130 de septiembre es **parcial** (262 cuentas de resultados con movimiento, de las que 108 están en el mapeo; p. ej. Salaries sale en 0 y IVA/Lodging Tax tampoco aparecen): si es el reporte completo del mes, falta confirmar con quién lo exporta.

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
**Para cerrar la Fase 3 (Contraloría):** (1) el Variance y el Budget de septiembre para la prueba de diferencia cero; (2) ampliar el mapeo con las 154 cuentas nuevas de septiembre; (3) confirmar las causas de las 19 excepciones de agosto (ver `FASES_FUTURAS.md`). Pendientes anteriores que siguen abiertos: `4002013`/`4003003` sin línea, clave única de una línea, origen del Budget, año fiscal julio–junio y convención de signo. Con eso, **Fase 4 — Reporting y frontend definitivo** (la API del Variance ya existe: `GET /hoteles/{id}/variance`).
