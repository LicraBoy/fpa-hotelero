# Fases futuras

Qué sigue después de la Fase 1, en orden. Fuente: `Arquitectura_Tecnica_FPA_Hotelero.md` (sección 7) y el Blueprint funcional aprobado por Contraloría. Este documento resume cada fase para planear; el detalle técnico y las decisiones viven en la arquitectura.

Última actualización: 22-oct-2026

**Estados:** `[HECHA]` · `[SIGUIENTE]` · `[PENDIENTE]` · `[PROPUESTA]` (fase nueva que aún no está en la arquitectura).
**Tamaños relativos** (no son fechas): **S** días · **M** 1–2 semanas · **L** más de 2 semanas.
**Regla:** no se abre una fase sin cerrar la anterior. Cada sub-fase termina con pruebas, `ruff`, `mypy`, `npm run e2e` si toca pantallas, documentación al día y un commit.

---

## Vista general

| Fase | Nombre | Tamaño | Estado | Depende de |
|---|---|---|---|---|
| 0 | Repositorio full stack | M | `[HECHA]` | — |
| 1 | Data Hub: Actuals | L | `[HECHA]` | 0 |
| **2** | **Catálogo corporativo y mapeo** | M | `[CÓDIGO LISTO]` | 1 + 3 respuestas de Contraloría |
| 3 | Motor de Variance | L | `[PENDIENTE]` | 2 |
| 4 | Reporting y frontend definitivo | L | `[PENDIENTE]` | 3 |
| 5 | Comentarios, workflow, roles y auditoría | L | `[PENDIENTE]` | 4 + decisión de identidad con TI |
| 6 | Endurecimiento y piloto en Torres | L | `[PENDIENTE]` | 5 |
| 7 | Budget en la plataforma | L | `[PENDIENTE]` | 6 |
| 8 | Forecast y rolling forecast | L | `[PENDIENTE]` | 7 |
| 9 | Drivers y escenarios | L | `[PENDIENTE]` | 8 + fuentes operativas |
| 10 | Cash Flow | L | `[PENDIENTE]` | 8 + datos de cuentas por cobrar/pagar |
| 11 | Multi-hotel (Puerto Vallarta) | M | `[PENDIENTE]` | 6 (puede adelantarse) |
| 12 | IA gobernada | M | `[PENDIENTE]` | 6 (siempre después de tener cálculo validado) |
| 13 | Planeación estratégica y CAPEX | L | `[PENDIENTE]` | 8 |
| 14 | Planeación operativa diaria | M | `[PENDIENTE]` | 9 |
| 15 | Inteligencia hotelera (cruce de áreas con finanzas) | L | `[PROPUESTA]` | 9 + privacidad definida |

**Hito del MVP:** al cerrar la Fase 6, Contraloría cierra un mes real en la plataforma sin Excel paralelo. Las fases 7 en adelante son crecimiento.

**Capacidad transversal condicional (no es una fase numerada):** `docs/Anexo_Futuro_Capa_Datos_Operativos_Hoteleros.md` — conectar en el futuro un PMS (Cloudbeds es solo el proveedor candidato de referencia, no una decisión) para alimentar con datos operativos (ocupación, ADR, RevPAR, reservas, cobros) las Fases 8, 9, 10, 11, 12 y 14, y como diseño detallado de la Fase 15.2. **No se prioriza sobre Budget (7) ni Rolling Forecast (8)**; su propia "Decisión propuesta" dice empezar, cuando esas dos estén estables, por un solo caso de uso: enriquecer el forecast de ingresos de habitaciones con datos operativos validados.

---

## Requisitos transversales de gobierno, control y confiabilidad financiera

Una revisión externa del roadmap (22-oct-2026) señaló un riesgo real: si estas reglas no quedan
explícitas antes de construir Budget, Forecast, Cash Flow y las fases siguientes, habrá que
rehacerlas cuando se agregue un hotel o una fuente de datos nueva. No son una fase más — son
principios que **ya aplican desde la Fase 2** y que toda fase nueva debe respetar. Varios ya están
hechos; se listan explícitamente para no perderlos de vista.

1. **Calidad de datos, conciliación y trazabilidad de importaciones.** Cada carga (CON130, Budget,
   catálogo) necesita un identificador, un origen, una fecha, un resultado y un historial de
   errores — cuentas sin mapear, periodos inválidos, duplicados, importes rechazados, diferencias
   de conciliación. *Ya hecho (verificado 22-oct-2026):* `CargaArchivo` (`fpa/modelos/cargas.py`)
   ya trae id, origen (`fuente`, `nombre_archivo`, `sha256`), fecha y resultado; duplicados por
   hash (mismo archivo → `DUPLICADA`, no hace nada) y vista previa antes de confirmar un reemplazo
   (`REQUIERE_CONFIRMACION` con reporte de diferencias, `fpa/servicios/cargar_archivo.py` y
   `budget.py`) — esto cubre "plantillas versionadas, vista previa, prevención de duplicados" del
   punto 7 de abajo. La validación del mapeo (2.4) ya detecta cuentas con movimiento sin vínculo.
   *Falta de verdad:* no hay un historial de errores persistido por carga (hoy, si la lectura trae
   errores, se rechaza todo el archivo con un mensaje — no queda un registro para auditar después)
   ni un concepto de "importe rechazado" fila por fila.

2. **Versionado inmutable de presupuestos, forecasts, mapeos y escenarios publicados.** Regla
   general: lo aprobado no se sobrescribe, se versiona. Un cambio autorizado crea una versión
   nueva; la anterior se conserva completa (no solo el mapeo: también Budget, cada forecast
   publicado y cada escenario). *Ya hecho:* versionado del mapeo (2.5) y del Budget (3.1); falta
   extenderlo a Forecast (Fase 8) y Escenarios (Fase 9).

3. **Permisos por rol, departamento y hotel, con separación de funciones.** No basta
   administrador/usuario: quién consulta, quién captura, quién revisa y quién aprueba deben ser
   roles distintos, comprobados en el backend también al exportar (no solo al ver en pantalla).
   *Ya hecho:* matriz de roles por hotel (5.2); y **ya existe el detalle por departamento** que
   parecía faltar — el rol `responsable_area` (`fpa/identidad/permisos.py`, `ROLES_POR_SECCION`)
   ya restringe a un jefe de departamento a ver/editar solo las secciones que le asignaron. Hoy
   aplica a Comentarios (5.2/5.3); cuando se construya la captura de Budget (7.2) es extender ese
   mismo mecanismo, no inventar uno nuevo.

4. **Calendario fiscal y gestión de periodos.** Un periodo pasa por abierto → revisado → cerrado;
   la reapertura de uno cerrado debe ser un proceso autorizado y explícito, nunca una corrección
   silenciosa. *Corrección (22-oct-2026, verificado en código):* esto ya existe, mejor de lo que se
   dijo aquí antes. `CierrePeriodo` (`fpa/modelos/cierre.py`) ya tiene el estado por hotel y
   periodo (Borrador → Comentado → Revisado → Aprobado → Bloqueado), y la transición
   **Aprobado → Borrador está etiquetada "Reabrir"**, exige permiso (`CIERRE_APROBAR`) y una nota
   obligatoria — es justo la reapertura controlada que pide este punto. Lo que **sí falta**: desde
   **Bloqueado no hay ninguna transición de reapertura** (es terminal — si Contabilidad corrige un
   mes ya bloqueado, hoy no hay camino definido), y no existe un concepto formal de "año fiscal" ni
   de fecha límite. Esto se completa antes/durante la Fase 7, no como fase aparte.

5. **Catálogo formal de métricas y reglas de cálculo/agregación.** Cada KPI tiene una sola
   definición: fórmula, unidad, fuente, periodicidad, responsable, regla de agregación y versión —
   para que no se calcule de una forma en un reporte y de otra en un forecast. Ejemplos a
   documentar cuando se usen (no todos existen ya en el sistema):

   | Indicador | Definición |
   |---|---|
   | Ocupación | Habitaciones ocupadas / habitaciones disponibles |
   | ADR | Ingresos de habitaciones / habitaciones vendidas |
   | RevPAR | Ingresos de habitaciones / habitaciones disponibles |
   | Coste de nómina | Conceptos incluidos, departamentos, periodo y cargas patronales |
   | Variación financiera | Fórmula, signo, denominador, favorable/desfavorable — **ya definido**, ver `fpa/servicios/variance.py` |
   | Flujo de caja | Conceptos de cobro/pago incluidos, fecha del movimiento, saldo inicial |

   **Importante para la Fase 11 (multi-hotel):** no todo KPI se agrega sumando o promediando. La
   ocupación consolidada es habitaciones ocupadas totales / disponibles totales (no el promedio de
   los porcentajes de cada hotel); el ADR consolidado se pondera por habitaciones vendidas, no es
   un promedio simple de los ADR de cada hotel. Cada KPI necesita su propia regla de agregación
   declarada, no una genérica.

6. **Precisión decimal, pruebas financieras y recuperación ante fallos.** *Ya hecho en la Fase 6:*
   dinero con `Decimal` (ADR 0002), respaldos cifrados con restauración probada (6.4), análisis de
   dependencias y código estático sin hallazgos (6.1). Cada fase nueva agrega sus propios criterios
   de aceptación financieros (ver ejemplo en la Fase 7 de abajo) — no basta con que funcione en la
   pantalla.

7. **Capa de importación robusta** (mejora a lo que ya existe en `fpa/ingesta/`, no una fase
   nueva): plantillas versionadas, vista previa de los cambios antes de confirmar, prevención de
   duplicados, conciliación de totales contra la fuente, y trazar cada cifra hasta su archivo de
   origen. Diseñarlo de forma que, si algún día hay API con Novohit, se sustituya el adaptador sin
   reescribir la lógica financiera.

---

## Fase 2 — Catálogo corporativo y mapeo `[CÓDIGO LISTO]` (M)

**Estado (01-oct-2026):** las sub-fases 2.1 a 2.6 están hechas. La **salida** ("mapeo completo, aprobado por Contraloría") queda pendiente de dos respuestas: las cuentas sin línea (en Mazatlán `4003001.010`, `4003001.020` y `4002020`; las `4002013` y `4003003` eran del archivo de Vallarta) y la clave única de una línea. Hasta entonces el mapeo del Excel de agosto se puede aprobar solo con esas cuentas excluidas a propósito (provisional). La Fase 3 puede empezar sobre el borrador, pero la Fase 2 no se cierra hasta esa aprobación.

**Avance:** la sub-fase 2.1 (estructura del reporte desde la hoja `Ago`) está hecha. El catálogo oficial de cuentas ya está importado (sub-fase 1.9). Trae TIPO (signo), departamento y grupo de cada cuenta, lo que permite **validar el mapeo** contra el Excel del contralor en vez de aceptarlo a ciegas, y derivar la sección del reporte desde el código (los grupos de 4 dígitos de la clase 6 son los departamentos).

**Objetivo:** convertir las cuentas de Novohit en las líneas del reporte Variance, con las reglas que hoy están escondidas en las columnas X a AJ de la hoja `Ago`.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 2.1 Estructura del reporte `[HECHA]` | Importar de la hoja `Ago` las secciones, líneas, orden y tipo (detalle, subtotal, total) | 409 líneas de detalle importadas en el mismo orden que el Excel |
| 2.2 Reglas de suma `[HECHA]` | Modelar cómo se arma cada total (por ejemplo Total Operation Expenses = suma de 9 secciones) | Las reglas reproducen 3,711,624.81 |
| 2.3 Mapeo `[HECHA]` | Importar de las columnas X a AJ: línea del reporte ↔ cuentas locales, con su signo | 253 líneas vinculadas; signos iguales a las fórmulas del Excel |
| 2.4 Validación del mapeo `[HECHA]` | Reporte de cuentas con movimiento sin mapear y de cuentas mapeadas a más de una línea | Cero cuentas con Actual distinto de cero sin vínculo (como en agosto) |
| 2.5 Versionado `[HECHA]` | Cada cambio del mapeo crea una versión; vigencia y auditoría | No se puede editar una versión aprobada |
| 2.6 API del mapeo `[HECHA]` | Consultar y cambiar con permiso de analista | Solo el rol autorizado cambia el mapeo; queda bitácora |

**Antes de empezar, Contraloría debe confirmar:**
1. La convención del **signo** del Variance (hoy: favorable positivo; ingresos Actual − Budget, gastos Budget − Actual).
2. La **clave única de una línea**, porque una misma cuenta corporativa aparece en varias líneas.
3. El **origen del Budget** (hoy viene pegado como valor en el Excel).

**Salida:** mapeo completo, con todas las cuentas con movimiento mapeadas o marcadas sin mapear, y aprobado por Contraloría.

---

## Fase 3 — Motor de Variance `[PENDIENTE]` (L)

**Objetivo:** calcular el Variance con el Actual de los movimientos y el Budget cargado, y **reproducir el de agosto 2026 cifra por cifra**.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 3.1 Budget como versión `[HECHA]` | Cargar el Budget del Excel de agosto (mes, acumulado y anual) como una versión inmutable | Idéntico al Excel, línea por línea |
| 3.2 Actual por línea y mes `[HECHA]` | Suma con signo de las cuentas mapeadas (función pura) | Casos pequeños y propiedades (signo, suma) |
| 3.3 Acumulado y año fiscal `[HECHA]` | YTD desde julio hasta el mes de corte | Primer mes, cierre de año, mes sin datos |
| 3.4 Totales y subtotales `[HECHA]` | Reglas de suma; resumen de Commercial Services (Net Income, Expenses, Profit, Allocations) | Totales iguales a los del reporte |
| 3.5 Variance y Variance % `[HECHA]` | Convención de signo configurable | División entre cero y presupuesto cero devuelven un valor definido |
| **3.6 Prueba dorada: agosto** `[HECHA con excepciones documentadas]` | Reproducir las columnas D a Q de la hoja `Ago` | **Diferencia cero** en las 253 líneas vinculadas y en los totales |
| 3.7 Segunda prueba: septiembre `[ARNÉS LISTO; falta el Excel de Contraloría]` | Mismo proceso con el CON130 y el Variance de septiembre | Diferencia cero |

**Salida:** el motor reproduce agosto sin ninguno de los 14 pasos manuales.

---

## Fase 4 — Reporting y frontend definitivo `[CÓDIGO LISTO; falta la sesión con Contraloría]` (L)

**Estado (01-oct-2026):** 4.1 a 4.7 hechas y 4.8 preparada (datos de demostración, guía y plantilla de hallazgos). La Fase 4 se cierra cuando Contraloría haga la sesión y la lista de hallazgos Alta y Media quede cerrada (`docs/HALLAZGOS_CONTRALORIA.md`).

**Objetivo:** la interfaz real. El frontend actual es provisional y solo sirve para ver la Fase 1.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 4.1 Endpoints de reporte `[HECHA]` | Variance por periodo y sección, con filtros | Contrato de la API; pruebas automáticas de entradas inválidas |
| 4.2 Drill-down `[HECHA]` | Línea → cuentas → movimientos, paginado | La suma de los movimientos mostrados = la cifra de origen |
| 4.3 Base del frontend `[HECHA]` | Elegir librería de componentes; rutas protegidas; cliente tipado | Sin acceso a pantallas sin rol |
| 4.4 Pantalla de Variance `[HECHA]` | Tabla por secciones con subtotales, formato contable, columnas fijas | Cifras en pantalla = Excel de agosto |
| 4.5 Drill-down en pantalla `[HECHA]` | Del número hasta el asiento | Prueba de navegador (Playwright) |
| 4.6 Exportación a Excel `[HECHA]` | Mismo formato del reporte actual | El Excel exportado abre y coincide con la pantalla |
| 4.7 Rendimiento `[HECHA]` | Caché de reportes y agregados | Variance mensual (~400 líneas) p95 < 500 ms con caché |
| 4.8 Pruebas con usuarios `[PREPARADA]` | Sesión con Contraloría usando agosto | Lista de hallazgos cerrada |

---

## Fase 5 — Comentarios, workflow, roles y auditoría `[CÓDIGO LISTO; falta validación de Contraloría]` (L)

**Objetivo:** que las variaciones se expliquen y se aprueben dentro del sistema.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 5.1 Identidad real **[HECHA]** | Usuarios locales con `argon2id`, TOTP y sesiones del servidor (TI dio libertad de tecnología; ADR 0005). OIDC queda como proveedor futuro | Sesión caduca; token revocado deja de funcionar |
| 5.2 Roles y permisos **[HECHA]** | Matriz completa por rol y por hotel; el responsable de departamento ve y comentará solo las secciones asignadas; pantalla Usuarios | Prueba de toda la matriz rol × endpoint |
| 5.3 Comentarios **[HECHA]** | Por línea y periodo (mes y acumulado), con responsable, estatus y evidencia; el umbral para exigir comentario queda apagado `[POR VALIDAR]` | Texto con HTML o script se muestra como texto; adjuntos con la misma validación de archivos |
| 5.4 Workflow de cierre **[HECHA]** | Borrador → Comentado → Revisado → Aprobado → Bloqueado, con versiones congeladas al aprobar | Estados inválidos rechazados; un periodo bloqueado no acepta recargas |
| 5.5 Auditoría reforzada **[HECHA]** | Bitácora con hash encadenado (ADR 0006) e historial de la cifra; en PostgreSQL, sin permiso de modificar (`docs/bitacora_postgresql.sql`, al migrar) | Alterar un evento se detecta |
| 5.6 Notificaciones | Aviso por correo a responsables (opcional) | Sin datos sensibles en el cuerpo |

**Pregunta abierta:** quién comenta hoy y con qué umbral (las columnas de comentarios están vacías en agosto).

---

## Fase 6 — Endurecimiento y piloto en Torres `[PENDIENTE]` (L)

**Objetivo:** dejar el MVP listo para producción y cerrarlo con un mes real.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 6.1 Revisión de seguridad | Lista OWASP ASVS nivel 2, revisión de dependencias, análisis dinámico | Cero hallazgos críticos o altos abiertos |
| 6.2 Prueba de penetración | Interna o externa antes de producción | Informe con remediaciones verificadas |
| 6.3 Rendimiento y carga | 50 usuarios concurrentes; cargas de 10 mil filas | Objetivos de la arquitectura (sección 4.5) |
| 6.4 Respaldos | Respaldo cifrado y **restauración probada** | Restaurar y repetir agosto con diferencia cero |
| 6.5 Observabilidad | Registros, métricas y alertas | Una falla simulada dispara alerta |
| 6.6 PostgreSQL y CI | Base de producción, integración continua, pruebas en ambos motores | Migraciones y pruebas pasan en SQLite y PostgreSQL |
| 6.7 Pruebas de aceptación | Contraloría cierra agosto y septiembre en la plataforma | Acta de aceptación firmada |
| 6.8 Puesta en producción | Guías de operación, plan de reversa, capacitación | Ensayo de despliegue y reversa |

**Decisiones con TI antes de esta fase:** dónde se aloja, proveedor de identidad, PostgreSQL u Oracle, política de respaldos, antivirus para archivos subidos.

---

## Fase 7 — Budget en la plataforma `[PENDIENTE]` (L)

**Objetivo:** construir el presupuesto dentro del sistema, sin archivos paralelos.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 7.1 Ciclo y estados | Draft → Submitted → Review → Approved → Locked | Transiciones válidas e inválidas |
| 7.2 Captura por área | Cada responsable captura su departamento | Solo ve y edita lo suyo |
| 7.3 Mensualización | Repartir un total anual con estacionalidad o porcentajes | La suma de los meses = total anual (propiedad) |
| 7.4 Aprobación y bloqueo | Versión oficial inmutable | No se puede editar una versión aprobada |
| 7.5 Objetivo contra propuesta | Comparar lo que fija Dirección con lo que propone cada área | Las diferencias se calculan y se muestran |

**Requisitos que deben quedar definidos como comportamiento explícito** (revisión externa, 22-oct-2026):

| Capacidad | Comportamiento que debe quedar definido |
|---|---|
| Captura dentro de la plataforma | Cada responsable edita sus líneas directamente en el sistema, sin Excel paralelo |
| Objetivo frente a propuesta | El objetivo autorizado es la referencia; la propuesta se modifica y compara antes de aprobarse |
| Spreading mensual | Repartir el importe anual con perfiles estacionales, pesos personalizados, importes mensuales o distribución uniforme |
| Reconciliación del spreading | La suma de los meses coincide exactamente con el importe anual, incluidos los ajustes por redondeo |
| Validaciones | Importes faltantes, cuentas no permitidas, meses incompletos, líneas sin responsable |
| Flujo de aprobación | Responsables, estados, comentarios, fechas límite, rechazos y devoluciones para corrección |
| Bloqueo del presupuesto | Una versión aprobada no admite modificaciones ordinarias; una revisión autorizada publica una versión nueva |
| Historial y auditoría | Quién cambió un importe, el valor anterior, cuándo y por qué |
| Cobertura presupuestaria | Qué porcentaje de las líneas requeridas tiene presupuesto y cuáles faltan |
| Comparación de versiones | Objetivo, propuesta departamental y versión aprobada, una junto a la otra |

**Ejemplo de perfil de distribución mensual** (ilustrativo): un departamento con presupuesto anual
de mantenimiento de $1,200,000 no necesariamente gasta $100,000 cada mes —

| Periodo | Distribución | Presupuesto |
|---|---|---|
| Enero | 5% | $60,000 |
| Febrero | 5% | $60,000 |
| Marzo | 8% | $96,000 |
| Abril-diciembre | 82% | $984,000 |
| **Total** | **100%** | **$1,200,000** |

El sistema debe permitir elegir un perfil existente, personalizarlo y comprobar que el total anual
se mantiene; y distinguir entre un reparto automático y una distribución manual aprobada.

**Criterios de aceptación de la Fase 7** (no basta con que funcione en pantalla):
1. La suma de los importes mensuales distribuidos coincide exactamente con el importe anual.
2. Un presupuesto aprobado no se puede modificar sin el procedimiento autorizado.
3. Una nueva versión no altera los valores de la anterior.
4. Un usuario no puede aprobar presupuestos fuera de sus permisos.
5. Importar dos veces el mismo archivo no duplica los importes.
6. Los totales importados se concilian con la fuente, o la diferencia queda identificada.
7. Las exportaciones muestran la versión, los filtros y el periodo sobre los que se generaron.

---

## Fase 8 — Forecast y rolling forecast `[PENDIENTE]` (L)

**Objetivo:** una visión actualizada del cierre del año, cada mes.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 8.1 Versión de forecast | Actual cerrado + proyección de los meses que faltan | Comparable contra Budget |
| 8.2 Cierre mensual | Cada cierre sustituye forecast por actual y agrega un mes al horizonte de 12 meses | El cierre no altera versiones anteriores |
| 8.3 Comparativos | Contra el forecast anterior y contra el Budget | Las diferencias cuadran |

**Precisión necesaria** (revisión externa, 22-oct-2026): debe ser un rolling de 12 meses
**continuos**, no una previsión hasta el fin del ejercicio fiscal. Distinguir siempre **cuatro**
conceptos, no tres:
- **Budget**: el plan original aprobado.
- **Forecast vigente**: la expectativa actual de lo que va a ocurrir.
- **Forecast anterior**: la previsión publicada antes de la última actualización (se conserva, no
  se sobrescribe — ver requisito transversal 2).
- **Actual**: el resultado real de Contabilidad.

Así se compara no solo Budget contra Actual, sino también qué forecast se tenía antes del cierre
contra lo que finalmente ocurrió.

**Ejemplo ilustrativo — cierre de septiembre 2026** (el periodo exacto depende de la fecha de
corte y de si el mes actual ya cerró):

| Tramo | Qué pasa |
|---|---|
| Jul-sep | Actuales cerrados: el resultado real sustituye la previsión de esos meses; se conserva el forecast original para comparar |
| Oct-ago | Proyectados: siguen con sus hipótesis vigentes, actualizables mediante una previsión controlada |
| Sep 2027 | Se incorpora para mantener 12 meses de horizonte hacia adelante |

**Corrección de un periodo ya cerrado**: sigue el proceso de reapertura del calendario fiscal
(requisito transversal 4) — nunca se altera silenciosamente la fotografía del forecast que ya se
publicó.

**Criterios de aceptación de la Fase 8**: al cerrar un mes, el actual ocupa su lugar; los periodos
ya cerrados mantienen su integridad; el horizonte se extiende; la versión anterior del forecast
sigue disponible para medir qué tan acertada fue.

**Por confirmar:** año fiscal (julio–junio o calendario) y horizonte.

**Dato operativo futuro (condicional):** si se conecta un PMS, el primer caso de uso propuesto es
enriquecer este forecast con datos operativos validados (ocupación, reservas) — ver
`docs/Anexo_Futuro_Capa_Datos_Operativos_Hoteleros.md`, no antes de que esta fase esté estable.

**Librerías de pronóstico y análisis:** ver `docs/adr/0007-librerias-de-datos-y-ciencia-de-datos.md` (también aplica a las Fases 9 y 12); se elige con una validación con datos reales.

---

## Fase 9 — Drivers y escenarios `[PENDIENTE]` (L)

**Objetivo:** planear con variables del negocio (ocupación, tarifa, covers, plantilla, órdenes de trabajo) y simular decisiones.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 9.1 Modelo de drivers | Por ejemplo: ingreso de habitaciones = habitaciones disponibles × ocupación × tarifa | Cálculos contra casos de libro |
| 9.2 Fórmulas seguras | Parser propio de expresiones; **nunca `eval`** | Una fórmula maliciosa se rechaza |
| 9.3 Fuentes operativas | Conectar Recepción, puntos de venta, nómina | Datos cuadran con la fuente |
| 9.4 Escenarios | Copias aisladas del plan oficial | Un escenario nunca modifica el Budget aprobado |

**Por definir antes de construir** (revisión externa, 22-oct-2026): catálogo de drivers con
unidades, fórmulas, responsables y fuentes; dependencias entre variables; comparación del efecto
financiero de un escenario contra el oficial; y una forma explícita de volver al escenario base.

**Bloquea a las fases 14 y 15** porque trae las fuentes operativas.

**Dato operativo futuro (condicional):** la sub-fase 9.3 es exactamente donde encajaría un PMS si
se conecta algún día — arquitectura detallada en
`docs/Anexo_Futuro_Capa_Datos_Operativos_Hoteleros.md` (adaptador independiente del proveedor,
contrato canónico, validación antes de usarse en un driver oficial).

---

## Fase 10 — Cash Flow `[PENDIENTE]` (L)

**Objetivo:** proyectar la liquidez.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 10.1 Fuentes | Saldos bancarios, cuentas por cobrar y por pagar, calendario de nómina e impuestos | Datos cuadran con la fuente |
| 10.2 Calendario | Cuándo se cobra y cuándo se paga | Reglas de antigüedad y vencimiento |
| 10.3 Escenarios de caja | Menor ocupación, mayor gasto, inversiones | Saldo final = inicial + entradas − salidas |

**Precisión necesaria** (revisión externa, 22-oct-2026): modelar el *momento* en que el dinero
entra o sale, no solo el monto contable — saldos iniciales, cobros, pagos a proveedores, nómina,
impuestos, inversiones, y escenarios de liquidez con esos mismos componentes.

**Por confirmar:** quién gestiona Tesorería y si existe hoy una proyección de efectivo.

**Dato operativo futuro (condicional):** cobros y depósitos de un PMS solo se usan aquí después de
conciliarlos con banco/Contabilidad (nunca tratar un depósito como efectivo disponible sin
revisar su naturaleza) — ver `docs/Anexo_Futuro_Capa_Datos_Operativos_Hoteleros.md` §7-8.

---

## Fase 11 — Multi-hotel: Puerto Vallarta `[PENDIENTE]` (M, puede adelantarse)

**Decisión:** cada hotel tiene su catálogo propio (aislado). Como ~70 % de las cuentas coincide con Torres, se agrega la función **"crear el catálogo de un hotel copiando el de otro"** y un reporte de diferencias; después se importa el catálogo de Vallarta para ajustar.

**Objetivo:** incorporar el segundo hotel como **configuración**, no como código nuevo (el aislamiento por hotel ya existe desde la Fase 1.0).

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 11.1 Lista de incorporación | Pasos para dar de alta un hotel | Un hotel nuevo se da de alta sin programar |
| 11.2 Catálogo y mapeo propios | Cuentas, líneas del reporte y mapeo por hotel | Datos aislados entre hoteles |
| 11.3 Validar el formato | Confirmar si usa el mismo Novohit y el mismo CON130 | El lector funciona sin cambios si el formato es el mismo |
| 11.4 Comparativos | Reportes entre hoteles | Cada usuario solo ve los hoteles que le corresponden |

**Regla de agregación por KPI** (revisión externa, 22-oct-2026 — ver también el requisito
transversal 5): no todo indicador se agrega sumando o promediando. La ocupación consolidada es
habitaciones ocupadas totales / disponibles totales de todos los hoteles, nunca el promedio de los
porcentajes de cada uno; el ADR consolidado se pondera por habitaciones vendidas, no es un promedio
simple. Falta definir también: permisos por hotel, diferencias entre catálogos contables, y
comparación homogénea de periodos entre hoteles.

**Por confirmar:** si Puerto Vallarta usa el mismo Novohit y un catálogo parecido; qué significa la línea "PUERTO VALLARTA" en el reporte de Torres.

**Dato operativo futuro (condicional):** si cada hotel usa un PMS distinto, homologar sus
definiciones de ocupación/ADR antes de comparar — ver
`docs/Anexo_Futuro_Capa_Datos_Operativos_Hoteleros.md` §2 (fila Fase 11) y su catálogo de
indicadores (§7).

---

## Fase 12 — IA gobernada `[PENDIENTE]` (M)

**Objetivo:** resúmenes y alertas. **La IA nunca calcula cifras**: lee las del motor.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 12.1 Herramientas de solo lectura | La IA consulta el motor, no escribe | No puede modificar datos |
| 12.2 Permisos heredados | Ve solo lo que ve el usuario que pregunta | No lee fuera de su alcance |
| 12.3 Citas de fuente | Toda cifra citada remite a su origen | Toda cifra citada coincide con el motor |
| 12.4 Defensas | Contenido de archivos y comentarios tratado como no confiable | Resiste intentos de inyección de instrucciones |

**Agregar a los criterios de prueba** (revisión externa, 22-oct-2026): reconocer explícitamente
cuando no hay información suficiente para responder (en vez de inventar), y dejar registro de las
consultas sensibles en la bitácora.

**Condición:** solo después de tener datos y cálculos validados.

**Dato operativo futuro (condicional):** si hay indicadores de un PMS, la IA solo los usa después
de validar trazabilidad, permisos y calidad — ver
`docs/Anexo_Futuro_Capa_Datos_Operativos_Hoteleros.md` §2 (fila Fase 12).

---

## Fase 13 — Planeación estratégica y CAPEX `[PENDIENTE]` (L)

**Objetivo:** decisiones de mediano y largo plazo.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 13.1 Proyectos CAPEX | Monto, calendario, aprobador | Flujo de aprobación |
| 13.2 Impacto | Efecto en resultados, depreciación y efectivo | Coherencia entre estados |
| 13.3 Evaluación | Retorno, valor presente e IRR con aritmética exacta | Contra casos de libro de texto |
| 13.4 Escenarios a largo plazo | Plan de 3 a 5 años | CAPEX y gasto operativo no se mezclan |

**Por definir explícitamente** (revisión externa, 22-oct-2026): los flujos de caja incrementales de
cada proyecto, la inversión inicial, el calendario de desembolsos, la tasa de descuento, el
horizonte y los supuestos de ROI/NPV/IRR — validados con aritmética decimal (`Decimal`, no floats).

---

## Fase 14 — Planeación operativa diaria `[PENDIENTE]` (M)

**Objetivo:** pasar de lo mensual a lo diario por departamento (referencia: caso Scandic).

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 14.1 Tiempo diario | Granularidad de día en el modelo | Totales diarios = mensuales |
| 14.2 Fuentes diarias | Recepción y puntos de venta | Datos cuadran con la fuente |
| 14.3 Captura y alertas | Captura por departamento y avisos de desviación | Rendimiento con granularidad diaria |

**Por definir** (revisión externa, 22-oct-2026): cómo se agregan las previsiones diarias a los
meses fiscales y cómo se reconcilian con los datos reales de Contabilidad; responsables y
frecuencia de actualización por departamento.

**Dato operativo futuro (condicional):** llegadas, salidas y ocupación prevista de un PMS, solo si
mejoran de verdad la planeación diaria departamental — ver
`docs/Anexo_Futuro_Capa_Datos_Operativos_Hoteleros.md` §2 (fila Fase 14).

---

## Fase 15 — Inteligencia hotelera `[PROPUESTA]` (L)

**Objetivo:** cruzar áreas operativas con finanzas. Es la idea que planteó Dirección y todavía no tiene fase en la arquitectura; se propone crearla aquí.

**Preguntas que debe poder responder**
- ¿Cuántas escobas se han comprado y cuánto cuestan por departamento?
- ¿Cómo entra Recepción en el análisis financiero?
- ¿Qué habitaciones tienen peores opiniones?
- ¿Quién limpió esa habitación?

| Sub-fase | Qué se hace | Qué se prueba | Por qué va en este orden |
|---|---|---|---|
| 15.1 Compras e insumos | Compra → almacén → consumo por departamento → cuenta contable; un solo motor de inventario para todos los almacenes | Las cantidades y los costos cuadran con las cuentas de inventario | Es lo más cercano: el CON130 ya trae el tipo de asiento de entradas y salidas de almacén |
| 15.2 Recepción y habitaciones | Estancias y ocupación por habitación y fecha; ingresos por habitación | Ocupación y tarifas cuadran con la fuente | Necesita conectar el sistema de Recepción |
| 15.3 Política de privacidad | Permisos por rol y reglas de uso de datos de huéspedes y empleados, definidos con Contraloría y Recursos Humanos | Un usuario sin permiso no ve datos personales | **Bloquea a las dos siguientes** |
| 15.4 Opiniones de huéspedes | Calificación por aspecto (incluida la limpieza), ligada a habitación y fecha | Ranking de habitaciones correcto | Necesita las encuestas como fuente |
| 15.5 Limpieza | Tarea de limpieza de Ama de Llaves → habitación → empleado | Se puede rastrear una calificación hasta la tarea y el empleado, con permiso | Necesita el registro de quién limpia cada habitación |

**Llave común de los datos:** habitación + fecha (opiniones, estancias y limpieza); producto + almacén (compras e inventario).

**Por confirmar:** qué sistema guarda las opiniones, si Ama de Llaves registra quién limpia cada habitación, y dónde vive hoy cada fuente.

**Diseño detallado de la 15.2:** `docs/Anexo_Futuro_Capa_Datos_Operativos_Hoteleros.md` es la
especificación completa para esta sub-fase (contrato canónico de datos, catálogo de indicadores,
6 etapas de implementación, 14 criterios de aceptación) — Cloudbeds ahí es solo el proveedor de
referencia, no una decisión; sigue sin resolverse qué PMS usa Recepción hoy.

---

## Decisiones pendientes que afectan estas fases

| Quién | Pregunta | Afecta a |
|---|---|---|
| Contraloría | Confirmar que el signo es la naturaleza de la cuenta (Deudor suma, Acreedor resta; ya validado con el Excel) | 2, 3 |
| Contraloría | Clave única de una línea del reporte | 2 |
| Contraloría | **Septiembre:** el Variance y el Budget de septiembre (para la prueba de diferencia cero) y ampliar el mapeo: 154 cuentas con movimiento en septiembre no están en el mapeo de agosto (p. ej. `4003001.010`, ≈ −4.6 millones, y `4001006.x`) | 3.7 |
| Contraloría | Fuera del Base de Datos de agosto: filas 12 (5,000), 272, 277, 285, 289, 292 y Administration Fee/Allocated pegadas; `Telephone Profit` (344) como gasto y % de la fila 530 con |Budget|: ¿intencional? | 3.6 |
| Contraloría | Las cuentas `4003001.010` (≈ −4.1 M en agosto), `4003001.020` (≈ −166 mil) y `4002020` (−20,000) tienen movimientos pero **ninguna línea del Excel de Mazatlán las toma**: ¿se excluyen a propósito o es una omisión? | 2 |
| Contraloría | Origen, versión y responsable del Budget | 3, 7 |
| Contraloría | Año fiscal (julio–junio) y horizonte del forecast | 3, 8 |
| Contraloría | Árbol oficial de departamentos y centros de costo | 2, 5, 7 |
| Contraloría | Línea sin importe de agosto (fila 4389, "INCENTIVOS CHEF"): ¿cero o dato faltante? | 3 |
| Contraloría | Por qué 87 cuentas del Variance (el catálogo ahora acumula: al importar los de otros meses deberían cubrirse; las que sigan faltando se le preguntan) (ej. `4001004.004`, `4002003`, `6003001.013`) no están en el catálogo de septiembre | 2 |
| Contraloría | Significado de `Aux = S` y `DPTO. TI` del catálogo; catálogo de Puerto Vallarta para medir el ~70 % de coincidencia | 2, 11 |
| TI | Dónde se aloja, proveedor de identidad, PostgreSQL u Oracle, respaldos, antivirus | 5, 6 |
| TI | Sistema de Recepción, compras/almacén y encuestas: formatos y acceso | 9, 14, 15 |
| Contraloría y RR. HH. | Política de privacidad de datos de huéspedes y empleados | 15 |
| Contraloría | ¿Puerto Vallarta usa el mismo Novohit y catálogo? | 11 |

---

## Fuera de alcance por ahora

- Consolidación legal (eliminaciones entre empresas, varias monedas): solo si hay necesidad real.
- Cadena de suministro, S&OP y planeación de demanda del material de Board: no aplican al problema de Torres.
- Conexión directa a Novohit: hoy la carga es por archivo; la conexión directa queda por validar con TI.
