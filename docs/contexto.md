# CONTEXTO GENERAL DEL PROYECTO

Estoy trabajando en un nuevo proyecto junto con el área de **Contraloría de Torres Mazatlán** (VI Resorts by Westgate).

El objetivo es analizar, diseñar y posteriormente desarrollar una **plataforma Software as a Service (SaaS) de FP&A e Inteligencia Financiera/Operativa especializada en hotelería**.

IMPORTANTE:

**NO estamos desarrollando un PMS, ERP, sistema contable, POS ni otro sistema operativo para reemplazar los sistemas actuales de la empresa.**

La plataforma será **independiente** y funcionará como una capa superior que:

* recibe información de diferentes sistemas y fuentes;
* integra los datos;
* normaliza la información;
* relaciona información financiera y operativa;
* calcula métricas;
* realiza análisis;
* permite Budget;
* permite Forecast;
* permite Variance Analysis;
* permite escenarios;
* y posteriormente incorporará Inteligencia Artificial.

La plataforma deberá poder coexistir con los sistemas actuales de cada hotel.

> **Requisito permanente:** la visión integral del producto y las reglas que de ella se derivan están en `docs/VISION_DEL_PRODUCTO.md`.

---

# 1. REFERENCIA PRINCIPAL: BOARD

La empresa ha decidido tomar **Board** como principal referencia funcional para el nuevo proyecto.

Sitio principal:

https://www.board.com/

La parte que más nos interesa inicialmente es:

https://www.board.com/finance/planning-budgeting-forecasting

También nos interesa estudiar:

* Office of Finance
* Financial Planning & Analysis
* Planning, Budgeting & Forecasting
* Management Reporting & Analysis
* Cash Flow Forecasting & Analysis
* Strategic Long-term Planning
* Capital Planning
* Financial Close, Consolidation, and Reporting (FCCR)

Board será utilizada únicamente como **referencia funcional y de mercado**.

NO queremos copiar:

* código;
* interfaz;
* textos;
* diseño;
* identidad visual;
* arquitectura propietaria;
* modelos internos;
* contenido protegido.

Lo que queremos estudiar es:

> **qué problemas resuelve, qué procesos automatiza, qué conceptos financieros utiliza, qué capacidades tiene y cómo podríamos implementar conceptos equivalentes en una plataforma propia orientada específicamente a hoteles.**

---

# 2. CASO DE USO DE SCANDIC HOTELS

Existe un caso público de Board con Scandic Hotels:

https://www.board.com/customer/annual-planning-and-rolling-forecasting-at-scandic-hotel

Este caso es especialmente importante porque queremos analizarlo como referencia para comprender cómo una empresa hotelera utiliza una plataforma de FP&A para resolver problemas relacionados con:

* planificación;
* presupuesto;
* rolling forecast;
* consolidación;
* reporting;
* múltiples unidades;
* diferentes fuentes de información;
* procesos anteriormente dependientes de Excel;
* estandarización;
* workflows;
* análisis financiero.

ESTUDIAR EL CASO DE SCANDIC PARA ENTENDER:

1. cuál era el problema;
2. cómo trabajaban antes;
3. qué información utilizaban;
4. qué proceso transformaron;
5. qué elementos de Board resolvieron cada problema;
6. qué estructura funcional podemos adaptar al contexto de Torres Mazatlán.

No copiar la solución.

Extraer la **lógica funcional**.

---

# 3. PROBLEMA REAL DE TORRES MAZATLÁN

Contraloría actualmente recibe información de diferentes fuentes y realiza procesos manuales para consolidar, comparar y analizar el comportamiento financiero.

Existe una base de datos de movimientos que contiene información de múltiples departamentos/cuentas.

También existe un reporte de análisis de Variance que actualmente presenta una estructura similar a:

* Account #
* Account Description
* Actual
* Budget
* Variance
* Variance %
* Year to Date
* YTD Comments
* Annual Budget
* Comments

El proceso actual utiliza información detallada de movimientos y posteriormente realiza agrupaciones por cuenta y periodo.

Ejemplo conceptual:

```text
MOVIMIENTOS
    ↓
CUENTA CONTABLE
    ↓
MES
    ↓
DÉBITO / CRÉDITO
    ↓
TOTAL DEL MES
    ↓
ACTUAL
    ↓
COMPARACIÓN CON BUDGET
    ↓
VARIANCE
    ↓
VARIANCE %
    ↓
YTD
    ↓
ANNUAL BUDGET
    ↓
COMMENTS
```

También existen vínculos hacia cuentas detalladas para poder investigar el origen de una variación.

Actualmente parte de este trabajo se realiza mediante Excel, fórmulas, hojas separadas, vínculos y procesos manuales.

La nueva plataforma deberá convertir progresivamente este proceso manual en un sistema estructurado de FP&A.

---

# 4. EJEMPLO DE DATOS DE MOVIMIENTOS

Existe una estructura de información similar a:

| Campo                      |
| -------------------------- |
| Mes                        |
| Fecha                      |
| No Cuenta                  |
| Nombre de la Cuenta        |
| Asiento - Salida           |
| Concepto - Nombre Artículo |
| Cantidad                   |
| Costo                      |
| Débito                     |
| Crédito                    |

Ejemplo conceptual:

```text
Mes: Agosto
Fecha: 8/1/2026
Cuenta: 4001002.001
Descripción: INGRESOS DE BAR BEBIDAS
Asiento: 8.3.1
Concepto: BAR PALAPA
Débito: 59.95
Crédito: 0
```

Y existen muchos movimientos para una misma cuenta.

Esto representa principalmente la capa de:

# ACTUALS / DATOS REALES

No asumir que este Excel es la única fuente definitiva.

La plataforma debe diseñarse para que los datos puedan provenir de:

* sistemas contables;
* PMS;
* POS;
* nómina;
* compras;
* inventarios;
* mantenimiento;
* otros sistemas;
* Excel;
* CSV;
* APIs;
* bases de datos;
* otras fuentes que se determinen durante el descubrimiento.

---

# 5. CONCEPTO CENTRAL DE LA PLATAFORMA

La plataforma deberá funcionar conceptualmente así:

```text
SISTEMAS EXISTENTES
        ↓
DATA SOURCES
        ↓
INGESTA
        ↓
VALIDACIÓN
        ↓
NORMALIZACIÓN
        ↓
MODELO FINANCIERO / OPERATIVO
        ↓
MÉTRICAS
        ↓
REPORTING
        ↓
BUDGET
        ↓
FORECAST
        ↓
VARIANCE ANALYSIS
        ↓
SCENARIOS
        ↓
CASH FLOW
        ↓
AI / INSIGHTS
```

La plataforma NO reemplaza las fuentes originales.

Funciona como una capa de inteligencia encima de ellas.

---

# 6. VISIÓN: HOTEL INTELLIGENCE

Aunque el núcleo inicial será FP&A, la visión de largo plazo es una plataforma de:

# HOTEL INTELLIGENCE

Debe poder relacionar:

## Habitaciones

* Occupancy
* ADR
* RevPAR
* TRevPAR
* habitaciones disponibles
* habitaciones ocupadas
* pickup
* pace
* OTB

## Alimentos y Bebidas

* ventas
* covers
* average check
* Food Cost
* Beverage Cost
* labor
* mix
* rentabilidad de productos
* recetas
* costos

## Ama de Llaves

* habitaciones atendidas
* productividad
* labor
* amenidades
* blancos
* costo por habitación

## Mantenimiento

* órdenes de trabajo
* activos
* mantenimiento preventivo
* mantenimiento correctivo
* materiales
* mano de obra
* habitaciones fuera de servicio
* costos

## Compras

* proveedores
* compras
* precios
* variaciones
* histórico

## Almacenes

* existencias
* entradas
* salidas
* transferencias
* ajustes
* consumo
* inventarios
* mermas

## Recursos Humanos

* headcount
* labor
* horas
* costo laboral
* productividad

## Revenue

* occupancy
* ADR
* RevPAR
* pickup
* pace
* forecast de demanda

## Finanzas

* Revenue
* Costos
* Gastos
* GOP
* GOP Margin
* EBITDA
* Cash Flow
* Working Capital
* Budget
* Forecast

La plataforma debe relacionar todos estos datos.

---

# 7. IMPORTANTE: LOS DEPARTAMENTOS NO SON SISTEMAS AISLADOS

No diseñar:

```text
Sistema de Mantenimiento

Sistema de Inventarios

Sistema de F&B

Sistema Financiero
```

como sistemas independientes desconectados.

El modelo debe permitir:

```text
HOTEL
 ↓
DEPARTAMENTO
 ↓
CENTRO DE COSTO
 ↓
CUENTA / PRODUCTO / ACTIVO
 ↓
TRANSACCIÓN / EVENTO
 ↓
PERIODO
```

Ejemplo:

```text
Mantenimiento
 ↓
Orden de trabajo
 ↓
Material utilizado
 ↓
Salida de almacén
 ↓
Costo de mantenimiento
 ↓
Habitación fuera de servicio
 ↓
Menor disponibilidad
 ↓
Posible impacto en Revenue
```

Otro:

```text
Ama de Llaves
 ↓
Habitaciones limpiadas
 ↓
Amenidades consumidas
 ↓
Labor
 ↓
Costo por habitación
```

Otro:

```text
F&B
 ↓
Producto
 ↓
Receta
 ↓
Costo
 ↓
Venta
 ↓
Food Cost
 ↓
Margen
```

---

# 8. ALMACENES

Un departamento puede tener su propio almacén.

Por ejemplo:

```text
INVENTORY ENGINE

├── Almacén F&B
├── Almacén Mantenimiento
├── Almacén Housekeeping
├── Almacén Lavandería
└── Otros almacenes
```

IMPORTANTE:

No crear un motor de inventarios diferente para cada departamento.

Debe existir un:

# INVENTORY ENGINE

general.

Los departamentos tienen diferentes almacenes y permisos, pero utilizan una misma lógica de inventario.

---

# 9. NÚCLEO FP&A

El MVP inicial NO será toda la inteligencia hotelera.

El núcleo inicial debe ser:

# FINANCIAL PERFORMANCE & VARIANCE

Con:

```text
ACTUAL
BUDGET
VARIANCE
VARIANCE %
YTD
ANNUAL BUDGET
COMMENTS
DRILL-DOWN
```

Posteriormente:

```text
FORECAST
ROLLING FORECAST
DRIVERS
SCENARIOS
CASH FLOW
STRATEGIC PLANNING
CAPEX
AI
```

---

# 10. MODELO TEMPORAL

El sistema debe diferenciar claramente:

* Mes actual.
* Acumulado YTD.
* Año completo.
* Año anterior.
* Budget.
* Forecast.
* Scenario.

Ejemplo:

```text
                 ACTUAL    BUDGET    VARIANCE    %
AGOSTO             X          X          X         X
YTD                X          X          X         X
FULL YEAR          X          X          X         X
```

No mezclar estos conceptos.

---

# 11. BUDGET

Queremos estudiar cómo implementar:

## Annual Budget

Debe permitir:

* versión;
* ciclo;
* responsables;
* captura;
* revisión;
* aprobación;
* bloqueo;
* publicación.

También estudiar:

## Top-down

Dirección/Contraloría establece objetivos.

## Bottom-up

Los responsables de área construyen el detalle.

Ejemplo:

```text
Dirección
 ↓
Objetivo Revenue
 ↓
Departamentos
 ↓
Presupuesto detallado
 ↓
Revisión
 ↓
Correcciones
 ↓
Aprobación
```

---

# 12. DRIVER-BASED PLANNING

Esta es una de las funcionalidades más importantes.

No queremos planificar únicamente cantidades monetarias.

Queremos utilizar drivers operativos.

Ejemplos:

```text
Room Revenue
=
Available Rooms × Occupancy × ADR
```

```text
F&B Revenue
=
Covers × Average Check
```

```text
Housekeeping Labor
=
Rooms to Clean × Standard Hours × Labor Cost
```

```text
Maintenance Cost
=
Expected Work Orders × Average Cost
```

Los drivers deberán alimentar el presupuesto y posteriormente el forecast.

---

# 13. SPREADING / MENSUALIZACIÓN

Estudiar cómo implementar:

```text
Presupuesto anual
        ↓
Distribución mensual
```

utilizando:

* porcentajes;
* histórico;
* estacionalidad;
* drivers;
* patrones;
* ajustes manuales controlados.

---

# 14. FORECAST

Posteriormente desarrollar:

# Rolling Forecast

Conceptualmente:

```text
Actual cerrado
+
Meses futuros
=
Forecast actualizado
```

Ejemplo:

```text
Enero - Agosto
ACTUAL

Septiembre - Diciembre
FORECAST
```

Después del cierre de septiembre:

```text
Enero - Septiembre
ACTUAL

Octubre - Diciembre
FORECAST
```

---

# 15. SCENARIO PLANNING

Después del Budget y Forecast:

```text
BASE
```

Crear escenarios:

```text
Occupancy -5%

ADR +8%

Labor +10%

Food Cost +3%

Exchange Rate +5%
```

Y calcular automáticamente el impacto financiero.

---

# 16. CASH FLOW

Posteriormente:

```text
Cash Beginning
+
Inflows
-
Outflows
=
Cash Ending
```

Relacionando:

* Revenue;
* cuentas por cobrar;
* cuentas por pagar;
* proveedores;
* nómina;
* impuestos;
* CAPEX;
* financiamiento.

---

# 17. MANAGEMENT REPORTING

El sistema debe poder generar:

```text
Actual
vs Budget
vs Forecast
vs Prior Year
```

con:

* KPIs;
* tablas;
* gráficas;
* variaciones;
* comentarios;
* drill-down;
* filtros;
* departamentos;
* cuentas;
* periodos.

---

# 18. DRILL-DOWN

No queremos copiar el concepto actual de hipervínculos en Excel.

Queremos:

```text
P&L
 ↓
Departamento
 ↓
Cuenta
 ↓
Movimiento
```

Por ejemplo:

```text
Other Income
 ↓
029-0000-44060-000
 ↓
Movimientos
 ↓
Fecha
 ↓
Asiento
 ↓
Concepto
 ↓
Importe
```

El usuario debe poder llegar desde el KPI hasta el dato origen.

---

# 19. COMMENTS

Los comentarios deben formar parte del modelo.

Una variación no debe ser únicamente:

```text
Variance = +$50,000
```

También debe poder existir:

```text
Comentario
Responsable
Fecha
Estatus
Evidencia
```

Posteriormente la IA podrá ayudar a generar o resumir estos comentarios.

---

# 20. AI

La IA NO deberá ser la primera funcionalidad.

Orden correcto:

```text
Datos confiables
 ↓
Reglas
 ↓
Métricas
 ↓
Budget
 ↓
Forecast
 ↓
Escenarios
 ↓
AI
```

La IA deberá principalmente:

* explicar;
* resumir;
* detectar patrones;
* responder preguntas;
* generar insights;
* analizar escenarios;
* ayudar a interpretar desviaciones.

Los cálculos financieros importantes deberán salir del motor financiero y no de una estimación libre del LLM.

---

# 21. PRINCIPIO DE TRAZABILIDAD

Cada resultado importante debe poder responder:

```text
¿De dónde salió este número?

¿Qué fuente lo generó?

¿Qué período representa?

¿Qué cuenta lo compone?

¿Qué fórmula se utilizó?

¿Quién modificó el dato?

¿Cuándo se modificó?
```

---

# 22. MULTI-TENANT / SaaS

Aunque inicialmente el piloto será:

# Torres Mazatlán

la arquitectura debe diseñarse para eventualmente soportar:

```text
Organización
 ↓
Grupo / Corporativo
 ↓
Hotel
 ↓
Departamento
 ↓
Centro de costo
```

Ejemplo futuro:

```text
Grupo Hotelero
│
├── Hotel A
├── Hotel B
├── Hotel C
└── Hotel D
```

Cada organización debe mantener sus datos aislados.

---

# 23. TECNOLOGÍA

AÚN NO DECIDIR EL STACK DEFINITIVO.

El contralor ha mencionado Oracle y posiblemente Java.

IMPORTANTE:

Oracle y Java no son la misma cosa.

Oracle puede referirse a:

* Oracle Database;
* Oracle Cloud;
* ecosistema Oracle.

Java es:

* lenguaje/plataforma backend.

Se debe investigar y posteriormente proponer una arquitectura tecnológica adecuada.

Considerar como candidatos:

## Backend

* Java + Spring Boot
* Python + FastAPI

## Database

* Oracle Database
* PostgreSQL

## Frontend

* React
* TypeScript

## Integraciones

* REST API
* SFTP
* Excel
* CSV
* DB connections
* Web Services

NO tomar una decisión tecnológica sin justificarla.

---

# 24. OBJETIVO DE ESTA ETAPA

MUY IMPORTANTE:

## NO PROGRAMAR.

Actualmente estamos en la etapa:

# INVESTIGACIÓN + DISCOVERY + BLUEPRINT FUNCIONAL

Quiero que analices todos los documentos que voy a proporcionar.

Los documentos pueden incluir:

* investigación de Monthly;
* documentos sobre Board;
* caso Scandic;
* propuesta anterior del proyecto;
* reportes de Torres;
* ejemplos de Excel;
* procesos actuales;
* documentos de Mantenimiento;
* documentos financieros;
* otros materiales.

NO debes empezar a crear código.

NO debes crear tablas SQL.

NO debes crear API.

NO debes crear componentes React.

NO debes modificar el proyecto.

Primero necesitamos entender perfectamente el negocio.

---

# 25. LO QUE NECESITO QUE HAGAS

Analiza todos los documentos proporcionados y construye una visión consolidada del proyecto.

Debes identificar:

### A. Procesos actuales

¿Cómo trabaja actualmente Torres?

### B. Procesos manuales

¿Qué se hace actualmente en Excel?

### C. Fuentes de datos

¿Qué sistemas y archivos proporcionan información?

### D. Dimensiones

Ejemplo:

```text
Hotel
Departamento
Centro de costo
Cuenta
Producto
Periodo
Escenario
Versión
```

### E. Métricas

Identificar las métricas ya utilizadas y las que deberían existir.

### F. Drivers

Identificar las variables operativas que podrían alimentar Budget y Forecast.

### G. Reglas de negocio

Detectar todas las fórmulas, clasificaciones y convenciones existentes.

### H. Workflow

Identificar:

```text
Draft
Submitted
Review
Approved
Locked
```

o equivalentes.

### I. Reportes

Identificar cuáles son los reportes actuales y cuáles deben digitalizarse.

### J. Integraciones

Identificar qué información debería llegar por:

* API;
* Excel;
* CSV;
* DB;
* otro método.

---

# 26. ENTREGABLE QUE QUIERO

Después de analizar los documentos, genera un:

# BLUEPRINT FUNCIONAL FP&A HOTELERO — TORRES MAZATLÁN

Debe incluir como mínimo:

1. Contexto del proyecto.
2. Problema actual.
3. Objetivo.
4. Alcance.
5. Qué es y qué NO es la plataforma.
6. Modelo conceptual.
7. Fuentes de datos.
8. Mapa de departamentos.
9. Dimensiones.
10. Jerarquías.
11. Catálogo financiero.
12. Actuals.
13. Budget.
14. Variance Analysis.
15. YTD.
16. Annual Budget.
17. Comments.
18. Drill-down.
19. Forecast.
20. Rolling Forecast.
21. Driver-Based Planning.
22. Spreading.
23. Scenario Planning.
24. Cash Flow.
25. Management Reporting.
26. Capital Planning.
27. Strategic Planning.
28. Consolidation.
29. Workflow.
30. Roles y permisos.
31. Calidad de datos.
32. Trazabilidad.
33. Integraciones.
34. Arquitectura conceptual.
35. Requerimientos tecnológicos.
36. MVP.
37. Fases futuras.
38. Criterios de aceptación.
39. Riesgos.
40. Preguntas que necesitamos validar con Contraloría.

---

# 27. PRIORIZACIÓN

Clasifica cada funcionalidad en:

## MVP

Lo indispensable para empezar.

## FASE 2

Funcionalidades posteriores.

## FASE 3

Funciones avanzadas.

## FUTURO

Funciones que no deben entrar todavía.

No intentes meter todo en el MVP.

---

# 28. METODOLOGÍA DE ANÁLISIS

Para cada funcionalidad importante quiero esta estructura:

### Funcionalidad

Nombre.

### Qué problema resuelve

Explicación empresarial.

### Cómo funciona conceptualmente

Proceso paso a paso.

### Datos de entrada

Qué información necesita.

### Procesamiento

Qué reglas se aplican.

### Resultado

Qué genera.

### Usuario

Quién lo utiliza.

### Dependencias

Qué debe existir antes.

### Aplicación en Torres

Cómo podría implementarse.

### Prioridad

MVP / Fase 2 / Fase 3 / Futuro.

### Preguntas abiertas

Qué necesitamos confirmar con Contraloría.

---

# 29. REGLA FUNDAMENTAL DE DISEÑO

NO diseñar la plataforma como una colección de módulos independientes.

Debe existir un modelo común:

```text
FUENTES
 ↓
DATA HUB
 ↓
NORMALIZACIÓN
 ↓
MODELO FINANCIERO / OPERATIVO
 ↓
MÉTRICAS
 ↓
FP&A
 ↓
REPORTING
 ↓
FORECAST
 ↓
SCENARIOS
 ↓
AI
```

La información de cada departamento debe poder relacionarse con Finanzas.

---

# 30. EJEMPLOS DE RELACIONES QUE DEBEMOS BUSCAR

### Mantenimiento

```text
Orden de trabajo
 ↓
Material
 ↓
Almacén
 ↓
Costo
 ↓
Habitación fuera de servicio
 ↓
Impacto operativo
 ↓
Impacto financiero
```

### Ama de Llaves

```text
Habitaciones
 ↓
Limpieza
 ↓
Labor
 ↓
Amenidades
 ↓
Costo / habitación
```

### F&B

```text
Ventas
 ↓
Productos
 ↓
Recetas
 ↓
Costo
 ↓
Food Cost
 ↓
Margen
```

### RRHH

```text
Headcount
 ↓
Horas
 ↓
Labor
 ↓
Departamento
 ↓
Costo
 ↓
Productividad
```

### Compras

```text
Proveedor
 ↓
Compra
 ↓
Precio
 ↓
Inventario
 ↓
Consumo
 ↓
Costo
```

---

# 31. PRINCIPIO DE IMPLEMENTACIÓN

El sistema deberá desarrollarse por capas.

NO hacer:

```text
Todo el hotel
+
Budget
+
Forecast
+
Cash
+
AI
+
Mantenimiento
+
Inventarios
+
Revenue
```

al mismo tiempo.

La estrategia será:

```text
1. Descubrimiento
       ↓
2. Modelo funcional
       ↓
3. Actuals
       ↓
4. Variance
       ↓
5. Budget
       ↓
6. Forecast
       ↓
7. Drivers
       ↓
8. Scenarios
       ↓
9. Cash Flow
       ↓
10. Inteligencia avanzada
       ↓
11. AI
```

Cada etapa debe tener:

* alcance;
* entregables;
* pruebas;
* validación;
* aprobación;
* criterio de salida.

NO avanzar si la capa anterior no está validada.

---

# 32. TU PRIORIDAD ACTUAL

Quiero que pienses como:

* analista funcional;
* arquitecto de negocio;
* especialista FP&A;
* consultor de hotelería;
* analista de datos.

NO como programador todavía.

Primero debemos responder:

> **¿Qué tiene que hacer exactamente nuestra plataforma y cómo debe funcionar para Torres Mazatlán?**

Después:

> **¿Qué datos necesita?**

Después:

> **¿Cómo se relacionan?**

Después:

> **¿Qué arquitectura tecnológica necesitamos?**

Y finalmente:

> **¿Cómo la programamos?**

---

# 33. RESULTADO FINAL DE ESTA SESIÓN

NO quiero código.

Quiero un análisis profundo y ordenado que nos permita sentarnos con Contraloría y decir:

> “Este es el sistema que proponemos construir, así funcionará, estos procesos va a mejorar, estas fuentes utilizará, estas serán sus principales funcionalidades y este será el orden en que se desarrollará.”

Después de ese documento, podremos pasar a la siguiente etapa:

# ARQUITECTURA TÉCNICA

y posteriormente al desarrollo.

IMPORTANTE:

No inventes procesos de Torres que no estén documentados.

Cuando algo no esté confirmado:

**marcarlo como HIPÓTESIS / POR VALIDAR.**

Cuando algo venga de Board:

**marcarlo como REFERENCIA FUNCIONAL.**

Cuando algo venga de los documentos de Torres:

**marcarlo como PROCESO ACTUAL / REQUERIMIENTO DE TORRES.**

La separación entre:

* dato confirmado;
* referencia externa;
* interpretación;
* propuesta;

debe mantenerse durante todo el análisis.
