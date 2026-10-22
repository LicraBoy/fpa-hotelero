# Anexo futuro: Capa de Datos Operativos Hoteleros para el FPA

**Estado:** Propuesta futura — no implementar en las fases actuales  
**Tipo:** Anexo de arquitectura y roadmap  
**Ámbito:** Integración futura de datos operativos hoteleros con el sistema de planificación y análisis financiero (FPA)  
**Proveedor de referencia:** Cloudbeds, como posible fuente de datos; la arquitectura no debe depender de un proveedor específico

---

## 1. Propósito

Preparar la arquitectura del FPA para incorporar en el futuro información operativa del hotel —por ejemplo, ocupación, habitaciones disponibles, reservas, tarifa media, ingresos por habitaciones y datos de cobros— y utilizarla como insumo para el presupuesto, el rolling forecast, los drivers, los escenarios, el flujo de caja y el análisis multi-hotel.

La finalidad no es convertir el FPA en un PMS ni replicar las funcionalidades operativas de Cloudbeds. El FPA continuará siendo el sistema para analizar resultados financieros, planificar, comparar escenarios, controlar versiones y documentar decisiones. Los sistemas hoteleros operativos seguirán siendo las fuentes de los datos que les correspondan.

Esta propuesta documenta una capacidad futura. **No implica que se vaya a contratar Cloudbeds, que exista una cuenta disponible ni que todas las métricas aquí descritas estén accesibles por API.** Antes de desarrollar un conector se deberán confirmar el proveedor utilizado, los permisos, las condiciones contractuales, la disponibilidad de campos, los límites técnicos y la calidad real de los datos.

## 2. Relación con el roadmap existente

La capacidad se plantea como una capa transversal del Data Hub, activable después de que el presupuesto y el forecast centrales funcionen de forma fiable.

| Fase actual | Posible aprovechamiento de datos operativos |
|---|---|
| Fase 1 — Data Hub / Actuals | Incorporar fuentes operativas mediante adaptadores independientes, manteniendo separado el origen y la naturaleza de cada dato. |
| Fase 7 — Budget | Utilizar drivers operativos para elaborar o justificar partes del presupuesto. No sustituye la captura, revisión y aprobación presupuestaria. |
| Fase 8 — Rolling Forecast | Añadir reservas, ocupación y supuestos comerciales validados como insumos para proyectar periodos futuros. |
| Fase 9 — Drivers y escenarios | Modelar ocupación, ADR, habitaciones disponibles, segmentos o canales, cuando la fuente proporcione datos aptos para ello. |
| Fase 10 — Cash Flow | Usar datos elegibles sobre cobros, depósitos y saldos como parte de una proyección de caja; conciliarlos con la fuente contable correspondiente. |
| Fase 11 — Multi-hotel | Homologar dimensiones y definiciones para comparar hoteles sin agregar incorrectamente porcentajes o promedios. |
| Fase 12 — IA gobernada | Permitir análisis apoyados en indicadores operativos solo después de validar su trazabilidad, permisos y calidad. |
| Fase 14 — Daily Operational Planning | Evaluar si los datos disponibles mejoran la planificación diaria departamental. |

La integración se implementará únicamente cuando las fases existentes y sus controles estén estables. Este anexo no cambia el orden ni el alcance comprometido de las fases actuales.

## 3. Principios de diseño

1. **Independencia del proveedor.** La lógica financiera no debe depender directamente del formato de Cloudbeds ni de un PMS concreto.
2. **Fuente identificable.** Cada registro importado conservará su sistema de origen, identificador externo disponible, propiedad, fecha de extracción y fecha o periodo de negocio.
3. **Separación entre operación y contabilidad.** Una reserva, una estancia, un cobro, un depósito y un ingreso contable son conceptos diferentes y no deben tratarse como equivalentes.
4. **No sobrescritura silenciosa.** Las cargas posteriores deben poder identificar altas, cambios, cancelaciones y correcciones sin destruir el historial necesario para auditoría y análisis.
5. **Cálculos financieros en el backend.** Las fórmulas materialmente financieras no deben depender exclusivamente del frontend.
6. **Permisos heredados y mínimos privilegios.** El acceso a datos operativos y financieros debe respetar permisos por rol, hotel y función.
7. **Validación antes del uso financiero.** Los datos no validados no se incorporarán automáticamente a un Budget o Forecast oficial.
8. **Degradación controlada.** Si una fuente falla o queda desactualizada, el sistema lo indicará y no presentará datos antiguos como si fueran actuales.
9. **Métricas versionadas.** Cada KPI tendrá una definición aprobada, una unidad, una fuente y reglas documentadas.
10. **Importación manual compatible.** Excel seguirá siendo un mecanismo de entrada posible. Los datos manuales y los recibidos por integración deben pasar por reglas de validación comparables.

## 4. Alcance funcional previsto

### 4.1 Datos operativos candidatos

La lista siguiente es candidata; debe confirmarse para el PMS, los módulos, las propiedades y los permisos que se utilicen realmente.

- Identificador de la propiedad u hotel.
- Fecha de estancia, fecha de reserva y fecha de actualización de la reserva, cuando estén disponibles.
- Noches de habitación vendidas y habitaciones disponibles, conforme a la definición operativa acordada.
- Estado de reservas y cambios relevantes, como cancelaciones o modificaciones, si la fuente los expone.
- Ingresos de habitaciones y otros ingresos operativos, con detalle de conceptos cuando esté disponible.
- Tarifa media diaria (ADR), ocupación y RevPAR, ya sea recibidos de la fuente o calculados internamente a partir de componentes validados.
- Segmento de mercado, canal de origen u otras dimensiones comerciales, siempre que estén disponibles y tengan definiciones estables.
- Llegadas, salidas y otras señales operativas que puedan ser útiles para la planificación diaria.
- Transacciones, pagos, depósitos y saldos pendientes cuando la fuente permita consultarlos y exista una definición clara de su significado.

No se debe asumir que todos estos datos están disponibles en una única API, que se actualizan con la misma frecuencia o que su definición coincide con la de Contabilidad.

### 4.2 Casos de uso iniciales

**Primer caso de uso recomendado:** enriquecer el rolling forecast de ingresos de habitaciones con datos operativos validados.

Casos posteriores posibles:

- Comparar ingresos, ocupación y ADR reales contra los supuestos presupuestados.
- Explicar cambios del forecast por volumen, tarifa o mezcla comercial, solo si el modelo permite separar esos efectos correctamente.
- Crear escenarios comerciales sin modificar el Budget aprobado ni el Forecast oficial.
- Incorporar señales de operación a la previsión de caja, después de conciliar qué transacciones representan dinero cobrado o por cobrar.
- Comparar hoteles con indicadores calculados bajo definiciones homogéneas.
- Apoyar la planificación diaria mediante llegadas, salidas y ocupación prevista.

## 5. Fuera de alcance

Esta capa de datos no pretende:

- Sustituir Novohit ni ningún PMS, ERP, sistema de reservas o contabilidad.
- Crear o modificar reservas, tarifas, disponibilidad, pagos o expedientes de huéspedes en el sistema de origen.
- Replicar un Channel Manager, motor de reservas, CRM, mensajería o herramientas de marketing.
- Tratar las reservas como ingresos contables reconocidos sin aplicar la política contable que corresponda.
- Tratar un depósito como ingreso o como efectivo disponible sin revisar su naturaleza, situación y conciliación.
- Sustituir el cierre contable ni la fuente oficial de los Actuals financieros.
- Desarrollar un motor de precios dinámicos o un modelo predictivo avanzado en la primera iteración.
- Implementar consolidación legal, eliminación de operaciones intercompañía o conversión multidivisa salvo que se apruebe un alcance específico para ello.

## 6. Arquitectura lógica propuesta

La arquitectura deberá separar la adquisición de datos, la normalización, la validación y su utilización en modelos financieros.

```text
PMS / Cloudbeds u otra fuente / archivos autorizados
                         |
                         v
              Adaptador de adquisición
       (API, exportación programada o Excel validado)
                         |
                         v
                Área de datos brutos
       (origen, extracción, versión y metadatos)
                         |
                         v
          Validación y normalización canónica
   (identificadores, fechas, monedas, dimensiones, estados)
                         |
                         v
             Datos operativos homologados
                         |
              +----------+----------+
              |                     |
              v                     v
      Capa de indicadores      Conciliación / calidad
      y métricas versionadas    y excepciones documentadas
              |
              v
     Budget / Rolling Forecast / Drivers / Cash Flow
              |
              v
       Reporting, auditoría y análisis gobernado
```

### 6.1 Adaptadores de fuente

Cada fuente se conectará mediante un adaptador separado. El adaptador se encargará de autenticación, consulta o recepción de datos, paginación, límites de uso, reintentos, manejo de errores y transformación al contrato de entrada acordado.

La lógica de Budget, Forecast, escenarios y Cash Flow no debe contener reglas específicas de una API externa. Si en el futuro se cambia de PMS, solo debería ser necesario crear o sustituir el adaptador y revisar el mapeo de datos.

### 6.2 Área de datos brutos

Cuando sea viable y esté autorizado, conservar una representación controlada de los datos recibidos, con metadatos suficientes para reproducir una carga y diagnosticar diferencias. Definir políticas de retención y minimización de datos antes de almacenar información de reservas o huéspedes.

Evitar almacenar información personal de huéspedes si no es necesaria para el FPA. El caso financiero normalmente requiere datos agregados o pseudonimizados, no nombres, correos, teléfonos ni datos de identidad.

### 6.3 Modelo canónico

La información de cada proveedor debe transformarse a un contrato interno estable. El contrato podría incluir campos como:

- `source_system`: sistema que originó el registro.
- `source_record_id`: identificador externo, cuando exista.
- `property_id`: identificador interno del hotel.
- `business_date` o `period_start` / `period_end`: fecha o periodo de negocio.
- `extracted_at`: fecha y hora de extracción.
- `record_updated_at`: fecha de actualización en origen, si está disponible.
- `metric_or_event_type`: métrica o tipo de evento.
- `value` y `unit`: valor y unidad normalizada.
- `currency`: moneda cuando el dato sea monetario.
- `dimensions`: dimensiones aprobadas, como canal o segmento cuando existan.
- `validation_status`: estado de validación.
- `load_id`: identificador de la ejecución de importación.

El esquema definitivo se diseñará a partir de los campos realmente accesibles y no deberá forzar que una fuente incompleta finja disponer de información que no ofrece.

## 7. Catálogo de indicadores

Antes de consumir cualquier indicador en un cálculo oficial, definirlo en un catálogo versionado.

| Indicador | Definición base candidata | Precaución |
|---|---|---|
| Habitaciones disponibles | Habitaciones vendibles disponibles durante el periodo, según la política del hotel | Documentar el tratamiento de cierres, bloqueos y habitaciones fuera de servicio. |
| Noches vendidas | Noches de habitación correspondientes a estancias elegibles | Definir tratamiento de cortesías, cancelaciones, no-shows y ajustes. |
| Ocupación | Noches o habitaciones ocupadas / base de disponibilidad definida | Numerador y denominador deben usar la misma unidad y regla temporal. |
| ADR | Ingresos de habitaciones elegibles / habitaciones vendidas elegibles | Definir qué componentes de ingreso se incluyen y cómo se tratan impuestos y ajustes. |
| RevPAR | Ingresos de habitaciones elegibles / habitaciones disponibles elegibles | No promediar directamente el RevPAR de distintos hoteles para obtener el consolidado. |
| Ingresos de habitaciones | Importe definido por la política de reporting para el periodo | No asumir que coincide automáticamente con las ventas, cobros o ingresos reconocidos en el libro contable. |
| Ritmo de reservas (booking pace) | Comparación de reservas conocidas a una fecha de corte frente a otra referencia o fecha de corte | Requiere conservar snapshots históricos comparables; los datos actuales por sí solos no reconstruyen el pasado. |
| Cobros y depósitos | Importes recibidos o registrados como pagos/depósitos según la fuente | Conciliar con pasarela, banco o contabilidad cuando sea pertinente; no sumar dos veces el mismo movimiento. |

Cada KPI debe incluir al menos: nombre, descripción, fórmula exacta, unidad, moneda si aplica, fuente, dimensiones permitidas, frecuencia, propietario funcional, tratamiento de nulos, reglas de agregación, versión y fecha de vigencia.

## 8. Integridad, conciliación y calidad de datos

La integración deberá generar resultados de validación visibles para el usuario responsable. Los controles mínimos incluyen:

- Rechazar o marcar registros sin propiedad, periodo, unidad o identificador obligatorio.
- Detectar duplicados mediante claves de negocio definidas, no solo por coincidencia de importes.
- Identificar cambios de reservas y cancelaciones sin duplicar ni borrar silenciosamente el historial.
- Distinguir entre dato ausente, cero real, no aplicable y dato rechazado.
- Detectar periodos incompletos, retrasos de actualización y variaciones atípicas.
- Verificar rangos y relaciones lógicas, como ocupación calculada fuera de los límites esperados, sin asumir que todo caso extremo sea necesariamente inválido.
- Conciliar los totales operativos con los informes oficiales de la fuente cuando ambos sean comparables.
- Documentar las diferencias entre cifras operativas y contables en lugar de forzar que coincidan.
- Permitir reintentar una carga fallida sin duplicar registros ya procesados.
- Conservar un resumen de filas recibidas, aceptadas, rechazadas, actualizadas y no modificadas.

Una carga operativamente correcta no demuestra por sí misma que un ingreso cumple las reglas de reconocimiento contable. Esa validación pertenece al proceso financiero y contable correspondiente.

## 9. Seguridad y auditoría

Requisitos obligatorios:

- Gestionar credenciales y secretos únicamente en infraestructura segura del servidor; nunca exponerlos en el frontend.
- Usar permisos mínimos y credenciales separadas por entorno.
- Aplicar permisos por usuario, rol, hotel y dimensión en las consultas, exportaciones y procesos automatizados.
- Registrar quién configuró, ejecutó, reintentó o canceló una carga.
- Mantener fecha, fuente, versión de esquema y resultado de cada ejecución.
- Registrar cambios de mapeo y de definiciones de KPIs.
- Definir política de retención, eliminación y minimización de datos, especialmente si la fuente contiene información personal.
- No permitir que la integración cambie silenciosamente Budget, Actuals cerrados o Forecast publicado.
- Exigir aprobación explícita antes de utilizar datos externos en una versión financiera oficial.

## 10. Comportamiento cuando los datos no están disponibles

La interfaz debe mostrar la fuente, la última actualización satisfactoria y el estado de la carga. Si el origen está desactualizado, la carga falla o faltan campos necesarios, el usuario debe verlo de forma explícita.

La ausencia de datos no debe convertirse automáticamente en cero. Deben distinguirse, según corresponda, los estados `valid`, `stale`, `incomplete`, `rejected`, `unavailable` y `not_applicable` (los nombres finales pueden adaptarse a las convenciones del proyecto).

Si falla el PMS, el usuario debe poder consultar la última carga válida cuando la política lo permita, con su fecha visible. No se debe marcar el forecast como actualizado sin advertir que utiliza datos operativos desactualizados.

## 11. Proceso de implementación futuro

### Etapa 0 — Confirmación de viabilidad

- Confirmar qué PMS o fuente operativa utiliza realmente cada hotel.
- Confirmar disponibilidad contractual y técnica de acceso.
- Revisar documentación de API, autenticación, permisos, límites, versionado y condiciones de uso.
- Obtener un conjunto de datos de prueba representativo y autorizado.
- Comparar campos disponibles con las necesidades del caso de uso.
- Definir frecuencia necesaria y acordar qué fuente prevalece para cada indicador.

**Salida:** decisión documentada de continuar, posponer o descartar la integración.

### Etapa 1 — Contrato de datos y modelo canónico

- Definir dimensiones internas de hotel y periodo.
- Diseñar el contrato de datos operativo mínimo.
- Aprobar las definiciones de ocupación, ADR, RevPAR e ingresos utilizados.
- Definir mapeos, validaciones, política de nulos y manejo de cambios.
- Preparar fixtures o archivos de prueba representativos sin datos personales innecesarios.

**Salida:** contrato versionado y pruebas de normalización automatizadas.

### Etapa 2 — Primer adaptador de solo lectura

- Desarrollar el conector en backend, separado de la lógica financiera.
- Implementar autenticación segura, paginación, límites, reintentos y registro de ejecución.
- Importar un conjunto pequeño de datos operativos no sensibles o minimizados.
- No modificar reservas, pagos ni información del sistema de origen.

**Salida:** importación repetible, trazable e idempotente en un entorno de pruebas.

### Etapa 3 — Validación y conciliación

- Comparar los resultados importados con informes de referencia del PMS.
- Documentar diferencias, campos ausentes y reglas de conversión.
- Validar tratamiento de duplicados, actualizaciones, cancelaciones y correcciones.
- Confirmar indicadores de frescura, calidad y completitud.

**Salida:** conciliación aprobada por un responsable de negocio y otro técnico.

### Etapa 4 — Integración controlada con Forecast

- Utilizar los datos operativos inicialmente como fuente informativa.
- Permitir que responsables autorizados revisen los supuestos derivados.
- Ejecutar el cálculo en un escenario de prueba sin afectar el Forecast oficial.
- Comparar el pronóstico generado con el método existente y medir su desempeño.
- Activar su uso en forecasts oficiales únicamente después de aprobar los controles.

**Salida:** caso de uso aprobado, trazabilidad a fuente y plan de reversión.

### Etapa 5 — Expansión a otros casos de uso

Solo tras validar el primer caso, evaluar escenarios avanzados, caja, comparaciones multi-hotel y planificación diaria. Cada extensión deberá definir su propio contrato de datos, métricas, pruebas y propietario funcional.

## 12. Criterios de aceptación

La integración inicial no se considera terminada hasta que cumpla, como mínimo, los siguientes criterios:

1. La fuente, la propiedad, el periodo y la fecha de extracción pueden identificarse para cada conjunto de datos utilizado.
2. El mismo lote puede procesarse dos veces sin duplicar importes ni eventos.
3. Los registros cambiados, cancelados o rechazados se manejan de forma explícita y auditable.
4. Los errores de autenticación, límites de API, respuestas incompletas y errores de red generan estados y mensajes accionables.
5. Los datos obsoletos se identifican y nunca se presentan sin advertencia como datos recientes.
6. Los totales clave se comparan con una fuente de referencia y las diferencias quedan documentadas.
7. Los campos que no existen en la fuente no se completan con valores ficticios.
8. El mapeo y las definiciones de métricas están versionados.
9. La integración no puede alterar un Budget aprobado ni los Actuals cerrados.
10. Los datos solo afectan un Forecast oficial cuando existe una acción explícita, autorizada y registrada.
11. Los permisos por hotel y rol se prueban también en backend y en exportaciones.
12. Existen pruebas automatizadas para normalización, idempotencia, duplicados, fechas, unidades, moneda y tratamiento de nulos.
13. Existe un procedimiento para desactivar el conector sin dejar el FPA bloqueado ni alterar los datos previamente aprobados.
14. La documentación explica limitaciones, frecuencia de actualización y datos que no se pudieron conciliar.

## 13. Métricas para medir el valor de la integración

Evaluar el éxito con indicadores observables, no solo con el hecho de que el conector esté funcionando:

- Porcentaje de cargas completadas satisfactoriamente.
- Porcentaje de registros aceptados y rechazados, con motivos.
- Tiempo transcurrido desde la actualización en origen hasta la disponibilidad en el FPA.
- Diferencias entre los informes operativos de referencia y los datos normalizados.
- Tiempo manual que se reduce en la preparación del forecast.
- Porcentaje de ingresos proyectados respaldados por drivers documentados.
- Error de forecast frente a los resultados reales, por horizonte y tipo de indicador.
- Número de errores por definiciones incompatibles entre hoteles.

El forecast basado en datos operativos no debe considerarse mejor solo por estar automatizado. Su precisión debe medirse frente a una referencia y compararse con el método anterior.

## 14. Riesgos y decisiones pendientes

Antes de la implementación deberán resolverse y documentarse las siguientes cuestiones:

- ¿Qué PMS utiliza realmente cada hotel y qué acceso está autorizado?
- ¿Qué entidades y campos expone la fuente, y con qué frecuencia se actualizan?
- ¿Las cifras operativas incluyen impuestos, descuentos, cancelaciones, cargos adicionales o ajustes?
- ¿Qué sistema prevalece para ingresos reconocidos: contabilidad, PMS u otra fuente financiera?
- ¿Cómo se concilian los pagos y depósitos del PMS con bancos, procesadores de pago y Contabilidad?
- ¿Se necesita información diaria, horaria o únicamente mensual?
- ¿Qué reglas deben homologarse entre hoteles?
- ¿Qué datos personales no deben almacenarse?
- ¿Qué sucede cuando una reserva o un cobro se modifica después de una carga anterior?
- ¿Qué coste de mantenimiento implica cada API o integración?

No se deberá comenzar el desarrollo productivo sin resolver las decisiones que afecten a permisos, integridad financiera, acceso contractual y definición de los indicadores oficiales.

## 15. Referencias técnicas para evaluación futura

Estas referencias sirven para iniciar la evaluación técnica; la documentación, los endpoints y las condiciones de acceso deben verificarse en el momento de implementación:

- Cloudbeds — portal de desarrolladores: <https://developers.cloudbeds.com/>
- Cloudbeds — sitio oficial en español: <https://www.cloudbeds.com/es/>
- Documentación y disponibilidad de Cloudbeds Insights, APIs y módulos relacionados: confirmar en el portal oficial y con el proveedor para el producto, cuenta, propiedad y permisos concretos.

Cloudbeds es únicamente un proveedor candidato. El modelo canónico, los adaptadores y las reglas del FPA deberán seguir siendo independientes de la marca.

---

## Decisión propuesta

**Mantener esta capacidad en el roadmap futuro como una extensión transversal del Data Hub.** No priorizarla por encima de la finalización y validación de Budget y Rolling Forecast. Cuando las fases centrales estén estables, iniciar la Etapa 0 de evaluación y seleccionar un único caso de uso inicial: datos operativos validados para enriquecer el forecast de ingresos de habitaciones.

La implementación deberá ser incremental, de solo lectura al principio y sin alterar presupuestos aprobados, cierres ni datos contables oficiales.
