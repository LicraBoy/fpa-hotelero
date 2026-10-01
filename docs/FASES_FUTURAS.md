# Fases futuras

Qué sigue después de la Fase 1, en orden. Fuente: `Arquitectura_Tecnica_FPA_Hotelero.md` (sección 7) y el Blueprint funcional aprobado por Contraloría. Este documento resume cada fase para planear; el detalle técnico y las decisiones viven en la arquitectura.

Última actualización: 30-sep-2026

**Estados:** `[HECHA]` · `[SIGUIENTE]` · `[PENDIENTE]` · `[PROPUESTA]` (fase nueva que aún no está en la arquitectura).
**Tamaños relativos** (no son fechas): **S** días · **M** 1–2 semanas · **L** más de 2 semanas.
**Regla:** no se abre una fase sin cerrar la anterior. Cada sub-fase termina con pruebas, `ruff`, `mypy`, `npm run e2e` si toca pantallas, documentación al día y un commit.

---

## Vista general

| Fase | Nombre | Tamaño | Estado | Depende de |
|---|---|---|---|---|
| 0 | Repositorio full stack | M | `[HECHA]` | — |
| 1 | Data Hub: Actuals | L | `[HECHA]` | 0 |
| **2** | **Catálogo corporativo y mapeo** | M | `[SIGUIENTE]` | 1 + 3 respuestas de Contraloría |
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

---

## Fase 2 — Catálogo corporativo y mapeo `[SIGUIENTE]` (M)

**Avance:** la sub-fase 2.1 (estructura del reporte desde la hoja `Ago`) está hecha. El catálogo oficial de cuentas ya está importado (sub-fase 1.9). Trae TIPO (signo), departamento y grupo de cada cuenta, lo que permite **validar el mapeo** contra el Excel del contralor en vez de aceptarlo a ciegas, y derivar la sección del reporte desde el código (los grupos de 4 dígitos de la clase 6 son los departamentos).

**Objetivo:** convertir las cuentas de Novohit en las líneas del reporte Variance, con las reglas que hoy están escondidas en las columnas X a AJ de la hoja `Ago`.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 2.1 Estructura del reporte `[HECHA]` | Importar de la hoja `Ago` las secciones, líneas, orden y tipo (detalle, subtotal, total) | 409 líneas de detalle importadas en el mismo orden que el Excel |
| 2.2 Reglas de suma `[HECHA]` | Modelar cómo se arma cada total (por ejemplo Total Operation Expenses = suma de 9 secciones) | Las reglas reproducen 3,711,624.81 |
| 2.3 Mapeo | Importar de las columnas X a AJ: línea del reporte ↔ cuentas locales, con su signo | 253 líneas vinculadas; signos iguales a las fórmulas del Excel |
| 2.4 Validación del mapeo | Reporte de cuentas con movimiento sin mapear y de cuentas mapeadas a más de una línea | Cero cuentas con Actual distinto de cero sin vínculo (como en agosto) |
| 2.5 Versionado | Cada cambio del mapeo crea una versión; vigencia y auditoría | No se puede editar una versión aprobada |
| 2.6 API del mapeo | Consultar y cambiar con permiso de analista | Solo el rol autorizado cambia el mapeo; queda bitácora |

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
| 3.1 Budget como versión | Cargar el Budget del Excel de agosto (mes, acumulado y anual) como una versión inmutable | Idéntico al Excel, línea por línea |
| 3.2 Actual por línea y mes | Suma con signo de las cuentas mapeadas (función pura) | Casos pequeños y propiedades (signo, suma) |
| 3.3 Acumulado y año fiscal | YTD desde julio hasta el mes de corte | Primer mes, cierre de año, mes sin datos |
| 3.4 Totales y subtotales | Reglas de suma; resumen de Commercial Services (Net Income, Expenses, Profit, Allocations) | Totales iguales a los del reporte |
| 3.5 Variance y Variance % | Convención de signo configurable | División entre cero y presupuesto cero devuelven un valor definido |
| **3.6 Prueba dorada: agosto** | Reproducir las columnas D a Q de la hoja `Ago` | **Diferencia cero** en las 253 líneas vinculadas y en los totales |
| 3.7 Segunda prueba: septiembre | Mismo proceso con el CON130 y el Variance de septiembre | Diferencia cero |

**Salida:** el motor reproduce agosto sin ninguno de los 14 pasos manuales.

---

## Fase 4 — Reporting y frontend definitivo `[PENDIENTE]` (L)

**Objetivo:** la interfaz real. El frontend actual es provisional y solo sirve para ver la Fase 1.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 4.1 Endpoints de reporte | Variance por periodo y sección, con filtros | Contrato de la API; pruebas automáticas de entradas inválidas |
| 4.2 Drill-down | Línea → cuentas → movimientos, paginado | La suma de los movimientos mostrados = la cifra de origen |
| 4.3 Base del frontend | Elegir librería de componentes; rutas protegidas; cliente tipado | Sin acceso a pantallas sin rol |
| 4.4 Pantalla de Variance | Tabla por secciones con subtotales, formato contable, columnas fijas | Cifras en pantalla = Excel de agosto |
| 4.5 Drill-down en pantalla | Del número hasta el asiento | Prueba de navegador (Playwright) |
| 4.6 Exportación a Excel | Mismo formato del reporte actual | El Excel exportado abre y coincide con la pantalla |
| 4.7 Rendimiento | Caché de reportes y agregados | Variance mensual (~400 líneas) p95 < 500 ms con caché |
| 4.8 Pruebas con usuarios | Sesión con Contraloría usando agosto | Lista de hallazgos cerrada |

---

## Fase 5 — Comentarios, workflow, roles y auditoría `[PENDIENTE]` (L)

**Objetivo:** que las variaciones se expliquen y se aprueben dentro del sistema.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 5.1 Identidad real | Inicio de sesión corporativo (OIDC) con MFA, según lo que defina TI | Sesión caduca; token revocado deja de funcionar |
| 5.2 Roles y permisos | Matriz completa por rol y por hotel | Prueba de toda la matriz rol × endpoint |
| 5.3 Comentarios | Por línea y periodo (mes y acumulado), con responsable, estatus y evidencia | Texto con HTML o script se muestra como texto; adjuntos con la misma validación de archivos |
| 5.4 Workflow de cierre | Borrador → Comentado → Revisado → Aprobado → Bloqueado | Estados inválidos rechazados; un periodo bloqueado no acepta recargas |
| 5.5 Auditoría reforzada | Bitácora con hash encadenado; en PostgreSQL, sin permiso de modificar | Alterar un evento se detecta |
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

---

## Fase 8 — Forecast y rolling forecast `[PENDIENTE]` (L)

**Objetivo:** una visión actualizada del cierre del año, cada mes.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 8.1 Versión de forecast | Actual cerrado + proyección de los meses que faltan | Comparable contra Budget |
| 8.2 Cierre mensual | Cada cierre sustituye forecast por actual y agrega un mes al horizonte de 12 meses | El cierre no altera versiones anteriores |
| 8.3 Comparativos | Contra el forecast anterior y contra el Budget | Las diferencias cuadran |

**Por confirmar:** año fiscal (julio–junio o calendario) y horizonte.

---

## Fase 9 — Drivers y escenarios `[PENDIENTE]` (L)

**Objetivo:** planear con variables del negocio (ocupación, tarifa, covers, plantilla, órdenes de trabajo) y simular decisiones.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 9.1 Modelo de drivers | Por ejemplo: ingreso de habitaciones = habitaciones disponibles × ocupación × tarifa | Cálculos contra casos de libro |
| 9.2 Fórmulas seguras | Parser propio de expresiones; **nunca `eval`** | Una fórmula maliciosa se rechaza |
| 9.3 Fuentes operativas | Conectar Recepción, puntos de venta, nómina | Datos cuadran con la fuente |
| 9.4 Escenarios | Copias aisladas del plan oficial | Un escenario nunca modifica el Budget aprobado |

**Bloquea a las fases 14 y 15** porque trae las fuentes operativas.

---

## Fase 10 — Cash Flow `[PENDIENTE]` (L)

**Objetivo:** proyectar la liquidez.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 10.1 Fuentes | Saldos bancarios, cuentas por cobrar y por pagar, calendario de nómina e impuestos | Datos cuadran con la fuente |
| 10.2 Calendario | Cuándo se cobra y cuándo se paga | Reglas de antigüedad y vencimiento |
| 10.3 Escenarios de caja | Menor ocupación, mayor gasto, inversiones | Saldo final = inicial + entradas − salidas |

**Por confirmar:** quién gestiona Tesorería y si existe hoy una proyección de efectivo.

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

**Por confirmar:** si Puerto Vallarta usa el mismo Novohit y un catálogo parecido; qué significa la línea "PUERTO VALLARTA" en el reporte de Torres.

---

## Fase 12 — IA gobernada `[PENDIENTE]` (M)

**Objetivo:** resúmenes y alertas. **La IA nunca calcula cifras**: lee las del motor.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 12.1 Herramientas de solo lectura | La IA consulta el motor, no escribe | No puede modificar datos |
| 12.2 Permisos heredados | Ve solo lo que ve el usuario que pregunta | No lee fuera de su alcance |
| 12.3 Citas de fuente | Toda cifra citada remite a su origen | Toda cifra citada coincide con el motor |
| 12.4 Defensas | Contenido de archivos y comentarios tratado como no confiable | Resiste intentos de inyección de instrucciones |

**Condición:** solo después de tener datos y cálculos validados.

---

## Fase 13 — Planeación estratégica y CAPEX `[PENDIENTE]` (L)

**Objetivo:** decisiones de mediano y largo plazo.

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 13.1 Proyectos CAPEX | Monto, calendario, aprobador | Flujo de aprobación |
| 13.2 Impacto | Efecto en resultados, depreciación y efectivo | Coherencia entre estados |
| 13.3 Evaluación | Retorno, valor presente e IRR con aritmética exacta | Contra casos de libro de texto |
| 13.4 Escenarios a largo plazo | Plan de 3 a 5 años | CAPEX y gasto operativo no se mezclan |

---

## Fase 14 — Planeación operativa diaria `[PENDIENTE]` (M)

**Objetivo:** pasar de lo mensual a lo diario por departamento (referencia: caso Scandic).

| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 14.1 Tiempo diario | Granularidad de día en el modelo | Totales diarios = mensuales |
| 14.2 Fuentes diarias | Recepción y puntos de venta | Datos cuadran con la fuente |
| 14.3 Captura y alertas | Captura por departamento y avisos de desviación | Rendimiento con granularidad diaria |

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

---

## Decisiones pendientes que afectan estas fases

| Quién | Pregunta | Afecta a |
|---|---|---|
| Contraloría | Confirmar que el signo es la naturaleza de la cuenta (Deudor suma, Acreedor resta; ya validado con el Excel) | 2, 3 |
| Contraloría | Clave única de una línea del reporte | 2 |
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
