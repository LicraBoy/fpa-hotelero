# Especificación de rediseño — Budget Studio para FPA Hotelero

**Estado:** propuesta de diseño e implementación futura/inmediata  
**Módulo:** Budget / Ciclo de Presupuesto  
**Frontend actual:** `frontend/src/pantallas/budget/PanelBudget.tsx`, `estilos/budget.css`  
**Backend relevante:** `VersionPlan`, `LineaPlan`, `LineaPlanMensual`, `CicloPresupuesto`, `CicloTransicion`, `LineaPresupuestoCaptura`, `LineaPresupuestoMensual`, `PerfilDistribucion`  
**Objetivo:** transformar Budget de una vista dominada por una tabla extensa en un espacio de trabajo financiero visual, accionable, claro y fácil de usar, sin cambiar las reglas financieras ni duplicar la lógica del backend.


> **Corrección visual obligatoria:** antes de implementar o continuar el rediseño, leer también `docs/Correccion_Visual_Budget_Studio.md`. Ese documento detalla la composición exacta por filas/columnas, los tamaños responsive y la comparación visual obligatoria con las capturas. Si hay instrucciones visuales generales en conflicto, prevalece la corrección detallada, siempre que no contradiga las reglas de negocio y arquitectura de este documento.

---

## 1. Decisión de producto

Construir una experiencia llamada **Budget Studio** con tres espacios conectados:

1. **Resumen:** dashboard del ciclo, KPIs, análisis interactivo, alertas y pendientes.
2. **Captura:** espacio de trabajo enfocado para consultar y editar las líneas autorizadas, con objetivo, propuesta anual, distribución mensual y notas.
3. **Versiones y auditoría:** historial de `VersionPlan`, ciclos y transiciones; las versiones históricas se consultan en modo de solo lectura.

La tabla financiera no se elimina: se conserva donde sea útil para edición precisa, comparación y accesibilidad. Lo que cambia es que deja de ser la única interfaz y ya no obliga al usuario a navegar horizontalmente por toda la información para comprender el presupuesto.

## 2. Principios obligatorios

- **Preservar el backend y las reglas vigentes.** No reimplementar en React permisos, aprobaciones, cálculos oficiales, transiciones de ciclo ni creación de versiones.
- **No inventar endpoints.** Revisar las rutas existentes en `fpa/api/v1/budget.py` y `fpa/api/v1/presupuesto.py`. Si una visualización requiere datos no expuestos, documentar la brecha antes de proponer una API.
- **El servidor manda.** El frontend refleja los permisos recibidos, pero el backend continúa siendo la autoridad para leer, capturar, aprobar, bloquear y reabrir.
- **Mantener el versionado inmutable.** Una versión histórica nunca se edita desde la pantalla. Restaurar o basarse en una versión antigua debe producir una versión nueva mediante el flujo ya existente.
- **Separar la visualización de la aritmética.** Reutilizar las funciones puras actuales de `calculo.ts`; cualquier nueva regla monetaria debe centralizarse y probarse, no implementarse dentro de componentes o callbacks de Plotly.
- **Precisión financiera.** Importes con formato de moneda y precisión decimal consistente. Los gráficos no deben ser la fuente de verdad de los totales ni introducir cálculos financieros con `float` en la UI.
- **Simple primero.** Mostrar el resumen relevante y revelar el detalle al interactuar. Evitar mostrar simultáneamente todos los filtros, gráficos, campos y estados.
- **Accesibilidad y teclado.** Controles con etiquetas, foco visible, navegación por teclado, contraste suficiente y tablas disponibles para usuarios que no puedan interpretar los gráficos.
- **Responsive.** Escritorio como espacio principal de planificación; en tablet/móvil, cambiar el split view por navegación secuencial o panel lateral a pantalla completa.

## 3. Arquitectura de información

### Encabezado persistente

Mostrar:

- Título `Budget` y ejercicio fiscal seleccionado (p. ej. `2026/27`).
- Nombre y número de la versión oficial vigente.
- Estado del ciclo de presupuesto: `Borrador`, `Enviado`, `Revisión`, `Aprobado` o `Bloqueado`, utilizando los estados reales del backend.
- Responsable o departamento seleccionado, cuando proceda.
- Acciones primarias permitidas por rol: `Abrir ciclo`, `Enviar a revisión`, `Aprobar`, `Bloquear`, `Guardar`, etc. Nunca mostrar como ejecutable una acción no autorizada.
- Un acceso visible al historial de transiciones y las versiones.

El encabezado debe distinguir visualmente el estado del ciclo en preparación del estado de la versión oficial vigente. No asumir que ambos son el mismo objeto.

### Navegación secundaria

Usar pestañas o navegación equivalente:

- **Resumen**
- **Captura**
- **Versiones y auditoría**

No crear una página nueva para cada gráfico. El cambio de pestaña debe preservar en lo posible el ejercicio, los filtros y la línea seleccionada.

## 4. Pantalla Resumen: dashboard accionable

### 4.1 Tarjetas KPI

Mostrar cuatro o cinco indicadores, no una pared de tarjetas:

1. **Cobertura de captura:** líneas capturadas / líneas requeridas, porcentaje y cantidad pendiente.
2. **Propuesta anual:** suma de las propuestas capturadas para el contexto actual.
3. **Diferencia contra objetivo:** propuesta menos objetivo, importe absoluto y porcentaje definido de forma consistente.
4. **Líneas por revisar:** conteo pendiente de revisión/aprobación, de acuerdo con los estados disponibles.
5. **Departamentos pendientes:** número de departamentos que aún deben completar o enviar su captura, solo si existe ese dato confiable en el modelo actual.

Cada KPI debe indicar su alcance: ejercicio, ciclo, filtro o departamento. No mostrar cifras ficticias ni sustituir datos faltantes por cero sin señalarlo. Si un KPI no puede calcularse con los endpoints existentes, mostrarlo como brecha de datos documentada, no inventarlo en el frontend.

### 4.2 Visualizaciones Plotly

Implementar inicialmente **tres visualizaciones**, con una cuarta opcional si los datos lo justifican.

#### A. Objetivo vs. propuesta por departamento/sección

- Gráfico de barras horizontales agrupadas.
- Comparar el objetivo aprobado/asignado con la propuesta actual en la misma unidad monetaria.
- Ordenar por diferencia absoluta o por mayor brecha, con selector claro.
- Tooltip con objetivo, propuesta, diferencia y porcentaje.
- Al seleccionar una barra, aplicar el filtro equivalente en Captura o abrir la lista de líneas relacionadas.
- Si no hay dimensión de departamento asociada, usar sección/línea del reporte según los datos disponibles; no inferir departamentos inexistentes.

#### B. Distribución mensual

- Línea o área por los 12 periodos del ejercicio fiscal julio–junio.
- Mostrar la suma mensual de la propuesta y, cuando proceda, la distribución mensual del objetivo.
- Permitir seleccionar propuesta/objetivo y una sección.
- Tooltip por periodo con importe, participación del total anual y diferencia disponible.
- No asumir que una curva estacional debe ser uniforme. La visualización representa los importes guardados, no una predicción inventada.

#### C. Cobertura y estado de captura

- Barra horizontal apilada o gráfico de progreso segmentado que muestre líneas capturadas, pendientes y revisadas usando únicamente estados que existan en el backend.
- Evitar un gráfico de dona sin utilidad operacional.
- Clic en un segmento aplica el filtro de estado correspondiente.

#### D. Opcional: mapa de calor mensual

Solo incorporar si el número de departamentos/líneas y los datos agregados hacen útil el análisis. Mostrar intensidad del importe o desvío por sección y mes. Debe tener leyenda, tooltip y alternativa tabular. No codificar la interpretación favorable/desfavorable solo por el color del importe.

### 4.3 Panel de alertas y acciones pendientes

Mostrar una lista compacta y priorizada de excepciones verificables, por ejemplo:

- Líneas sin capturar.
- Distribuciones mensuales cuya suma no coincide con el anual.
- Propuestas fuera del objetivo, si la regla existe y el objetivo está definido.
- Ciclo enviado pendiente de revisión.
- Errores de validación devueltos por backend.

Cada alerta debe explicar el problema y ofrecer una acción contextual: `Ver líneas`, `Revisar distribución`, `Abrir captura` o equivalente.

No marcar una propuesta como desfavorable automáticamente sin considerar la naturaleza de la cuenta o la regla financiera configurada. En ausencia de una regla de favorable/desfavorable, usar términos neutrales como `Sobre objetivo` o `Bajo objetivo`.

### 4.4 Principio de diseño del dashboard

Cada gráfico debe responder una pregunta y permitir tomar una acción. Evitar visualizaciones decorativas, gráficos repetidos, efectos 3D, gauges que ocupen demasiado espacio y animaciones innecesarias. Priorizar jerarquía visual, cifras legibles, espacio en blanco moderado y navegación evidente.

## 5. Pantalla Captura: espacio de trabajo enfocado

### 5.1 Split view en escritorio

**Panel izquierdo — Árbol de líneas**

- Navegación jerárquica por sección y línea del reporte según el catálogo real.
- Búsqueda por nombre/código y expandir/contraer secciones.
- Indicadores compactos: anual propuesto, estado de captura y diferencia contra objetivo cuando exista.
- Filtros: sección, estado y solo editables.
- No cargar el árbol con columnas pequeñas ni convertirlo en una segunda tabla compleja.

**Panel principal — Detalle de línea**

Al seleccionar una línea, mostrar:

- Nombre y código de la línea.
- Objetivo anual.
- Propuesta anual.
- Diferencia absoluta y porcentaje.
- Estado de captura y permisos efectivos.
- Distribución de los doce meses fiscales (julio a junio).
- Perfil de distribución aplicado, si existe.
- Nota/justificación.
- Historial contextual o acceso al historial, si existe información en los endpoints actuales.

### 5.2 Entrada de importes mensuales

- Presentar los 12 meses como una cuadrícula compacta de 3×4 o 4×3 en escritorio, con orden julio–junio explícitamente indicado.
- Cada mes utiliza un campo numérico editable, con etiqueta accesible, formato moneda y foco claro.
- Mostrar suma mensual, importe anual esperado y diferencia de conciliación en tiempo real.
- No usar un slider para introducir importes monetarios exactos. Puede utilizarse una barra visual para comparar objetivo y propuesta, pero la captura precisa debe realizarse mediante campos numéricos.
- Evitar scroll horizontal de página. Si la tabla comparativa de 12 meses se conserva, que el scroll se limite a su contenedor y exista una alternativa de vista por línea.
- Utilizar estados de edición explícitos: `Sin cambios`, `Cambios sin guardar`, `Guardando`, `Guardado` y `Error`, conforme al comportamiento real de las llamadas al backend.

### 5.3 Perfiles de distribución

Al pulsar `Aplicar perfil…`, abrir un modal o panel con perfiles existentes de `PerfilDistribucion`.

Para cada perfil mostrar:

- Nombre del perfil.
- Descripción breve.
- Vista previa de distribución mensual con una mini línea o barras.
- Porcentajes por mes y total del 100%, cuando el modelo disponga de estos datos.
- Resultado estimado en moneda para la línea seleccionada.

Acciones: `Vista previa`, `Aplicar`, `Cancelar`. Aplicar un perfil no debe modificar la versión oficial ni el presupuesto de otras líneas. Debe respetar el mecanismo de captura vigente y las validaciones del backend/`calculo.ts`.

El sistema debe conciliar al centavo el total mensual con el importe anual, mediante la regla de redondeo ya definida. Añadir pruebas para el último mes o el mes de ajuste de residuo y para importes con decimales.

### 5.4 Objetivo frente a propuesta

Mostrar el objetivo como referencia estable y la propuesta como valor de trabajo. Añadir una representación simple —por ejemplo, barra de progreso o bullet chart— para entender rápidamente la diferencia.

- El gráfico nunca sustituye los valores numéricos.
- Mostrar `Sobre objetivo`, `Bajo objetivo` o `Dentro del rango` según el criterio aplicable.
- Si el negocio exige comentario obligatorio al rebasar una tolerancia, usar una regla configurable definida en backend y validarla también en servidor. No imponer una regla únicamente en React ni tratar cualquier exceso como desfavorable por defecto.
- Si no existe todavía un endpoint o regla de tolerancia, implementar el contraste visual neutral y documentar la regla pendiente para decisión de producto.

### 5.5 Guardado y confirmación

- Diferenciar claramente `Guardar en el ciclo de presupuesto` de `Guardar como versión nueva`.
- Antes de confirmar, presentar un resumen comprensible de las líneas afectadas y los cambios principales.
- Evitar bloquear al usuario con una confirmación en cada campo; guardar por línea o lote según el mecanismo ya existente.
- Gestionar errores de concurrencia, permisos expirados y fallos de red sin descartar silenciosamente cambios.
- `Descartar cambios` debe restaurar la última versión cargada/guardada para esa sesión de edición y pedir confirmación si existen cambios pendientes.

## 6. Centro de control del ciclo

Rediseñar el estado del ciclo como un stepper accesible y legible:

`Borrador → Enviado → Revisión → Aprobado → Bloqueado`

El stepper debe:

- Reflejar exactamente el estado entregado por el backend.
- Mostrar la transición permitida siguiente, no todas las acciones indiscriminadamente.
- Mostrar actor, fecha y comentario de cada transición disponible.
- Permitir abrir la bitácora de `CicloTransicion` sin salir del contexto.
- Mostrar la cobertura de captura y permitir abrir un panel con líneas pendientes, solo si esos datos se pueden obtener de la API actual.
- Diferenciar los casos de reapertura `Aprobado → Borrador` o cualquier otra transición que admita el backend. No asumir que el flujo siempre es estrictamente lineal.

Los botones ejecutan las rutas existentes. Ante respuesta de error del servidor, mostrar el mensaje útil, conservar el estado anterior y actualizar el ciclo tras una transición exitosa.

## 7. Versiones y auditoría — “Time Machine”

Crear una vista cronológica de `VersionPlan` con:

- Número y nombre de la versión.
- Fecha/hora de creación.
- Usuario responsable.
- Archivo/origen o descripción disponible.
- Estado vigente/reemplazada, según el modelo actual.
- Acción de abrir/consultar.

Al abrir una versión antigua:

- Activar un indicador persistente `MODO HISTÓRICO · SOLO LECTURA`.
- Mostrar el número de versión seleccionado y la versión vigente en el contexto.
- Desactivar captura y acciones de aprobación que no correspondan a esa versión.
- Permitir comparar versiones solo si hay datos y servicios disponibles para hacerlo de forma fiable.
- Para reutilizar una versión antigua, usar el flujo existente que crea una nueva versión basada en esa referencia; nunca actualizar directamente la fila antigua.

## 8. Plotly y arquitectura frontend

### Uso recomendado

Utilizar Plotly para los gráficos analíticos interactivos del Resumen y, de forma limitada, para la vista previa estacional de los perfiles de distribución. Mantener los formularios de importes, los estados del ciclo y la tabla de líneas en componentes React normales.

Antes de instalar dependencias, revisar `package.json`, las versiones actuales de React/Next.js y si ya existe otra biblioteca de gráficos. No duplicar librerías sin necesidad.

Si el proyecto usa Next.js:

- Aislar las visualizaciones en componentes cliente.
- Cargar Plotly de forma diferida y evitar SSR del componente de gráfico si el wrapper requiere APIs del navegador.
- Mostrar un skeleton/loading compacto y una alternativa de error si falla la carga.
- Preferir un bundle de Plotly reducido a los tipos realmente utilizados, si es compatible con la instalación existente.
- Activar `responsive`, limitar los redibujados y evitar renderizados innecesarios.

Referencias técnicas oficiales:

- Plotly con React: https://plotly.com/javascript/react/
- Componente `react-plotly.js`: https://github.com/plotly/react-plotly.js
- Bundles completos y parciales de Plotly.js: https://github.com/plotly/plotly.js/blob/main/dist/README.md
- Carga dinámica en Next.js: https://nextjs.org/docs/app/guides/lazy-loading

### Organización de componentes propuesta

Adaptar los nombres a las convenciones existentes del repositorio, sin crear abstracciones innecesarias:

```text
frontend/src/pantallas/budget/
  PanelBudget.tsx                 # composición, filtros compartidos y estado de página
  componentes/
    BudgetHeader.tsx              # ejercicio, versión vigente y acciones principales
    CicloBudgetStepper.tsx        # estado, transiciones y acceso a bitácora
    BudgetKpiStrip.tsx             # indicadores del resumen
    BudgetResumen.tsx              # dashboard y alertas
    BudgetCharts.tsx               # contenedor de visualizaciones Plotly
    ObjetivoVsPropuestaChart.tsx   # barras comparativas
    DistribucionMensualChart.tsx   # evolución julio-junio
    CoberturaCapturaChart.tsx      # avance/estados de captura
    ArbolLineas.tsx                # navegación de secciones y líneas
    DetalleCapturaLinea.tsx        # objetivo, propuesta, diferencia y nota
    ImportesMensualesGrid.tsx      # captura de doce meses
    SelectorPerfilDistribucion.tsx # perfil y vista previa
    TimelineVersiones.tsx          # historial de VersionPlan
    PanelCobertura.tsx             # líneas/departamentos pendientes, si hay datos
  hooks/
    # reutilizar hooks existentes de datos; no duplicar fetching/cache
  estilos/
    budget.css                     # o modularizar según la arquitectura del repo
```

No es obligatorio adoptar exactamente esta estructura. El objetivo es dividir responsabilidades y reducir el archivo `PanelBudget.tsx`, manteniendo los patrones y dependencias que ya existen en el proyecto.

### Estado y carga de datos

- Reutilizar los hooks/servicios y cliente HTTP existentes.
- Mantener los datos de origen y los filtros sincronizados entre dashboard, árbol y detalle.
- No calcular totales oficiales desde datos parciales del gráfico.
- El backend o la capa de dominio existente debe ser la fuente de cifras autoritativas; las transformaciones para los charts deben ser funciones puras y probables.
- No ejecutar una solicitud HTTP por cada punto de un gráfico.
- Cancelar o ignorar resultados obsoletos al cambiar rápidamente de ejercicio, ciclo o filtro, utilizando los mecanismos disponibles en el stack actual.

## 9. Lenguaje visual

Dirección: **SaaS financiero hotelero premium, moderno, claro y muy visual**, orientado a Contraloría, Dirección y jefes de departamento.

- Fondo principal gris azulado muy claro; superficies blancas, bordes finos, esquinas redondeadas y sombras discretas.
- Sidebar vertical azul marino oscuro con iconos lineales, etiquetas legibles y una opción activa azul ligeramente más clara.
- Paleta analítica de azul y turquesa para series principales; verde para estados favorables confirmados; rojo/naranja solo para alertas o desviaciones cuya interpretación esté definida.
- Tarjetas KPI compactas con etiqueta, cifra destacada, variación y, cuando aporte valor, una mini tendencia.
- Tipografía moderna, jerarquía inequívoca, espacios generosos y cifras alineadas tabularmente.
- Evitar sombras exageradas, gradientes decorativos, emojis como iconografía principal, exceso de pills, animaciones y gráficos 3D.
- En tablas, diferenciar jerarquía de secciones, líneas editables, totales y errores de validación.
- Estados vacíos con una explicación y una acción concreta; errores accionables, no solo “Ocurrió un error”.
- Tooltips para explicar fórmulas o siglas, sin obligar al usuario a conocer terminología de ciencia de datos.

### 9.1 Referencia visual obligatoria: reproducir el lenguaje de la imagen

**La imagen de referencia es parte del requisito de diseño, no una sugerencia opcional.** En el repositorio debe estar disponible en:

`docs/referencias/budget-studio-referencia.png`

Antes de implementar, abre e inspecciona esa imagen. Replica de manera cercana su composición, jerarquía, proporciones, densidad, paleta y estilo visual, adaptándola a los componentes y datos reales del proyecto. El objetivo es que, al comparar ambas pantallas lado a lado, se perciba claramente que son el mismo concepto visual.

La referencia establece estas características que se deben respetar:

1. **Estructura general de aplicación:** sidebar fijo azul marino oscuro a la izquierda; área de trabajo clara a la derecha; barra superior con búsqueda global, notificaciones y usuario.
2. **Cabecera del Budget:** título prominente `Presupuesto 2026/27`, rango fiscal julio-junio, selector de versión, acceso al historial y acción principal del ciclo.
3. **Stepper horizontal del ciclo:** `Borrador → Enviado → Revisión → Aprobado → Bloqueado`, con el estado actual destacado, cobertura visible y pasos no activos en tonos suaves. Representar únicamente los estados y transiciones reales del backend.
4. **Fila de KPI:** cinco tarjetas compactas en escritorio, similares a la imagen, con iconos discretos, valor principal, comparación breve y sparkline opcional. Utilizar datos reales del presupuesto, como propuesta anual, cobertura, diferencia contra objetivo y líneas pendientes; no inventar métricas que el backend no permita calcular.
5. **Zona analítica principal:** gráfico de barras agrupadas `Objetivo vs. Propuesta` por departamento/sección a la izquierda; panel de principales diferencias respecto al objetivo en el centro; tarjeta de resumen y tareas pendientes del ciclo a la derecha.
6. **Segunda zona analítica:** gráfico ancho con la distribución mensual julio-junio y, en el panel lateral, vista previa del perfil de estacionalidad aplicado a la línea seleccionada.
7. **Zona inferior:** composición del presupuesto por sección, tarjeta breve de ayuda/contexto y acciones rápidas alineadas en una cuadrícula limpia.
8. **Acabado visual:** tarjetas blancas con bordes finos, fondo gris azulado, azul/turquesa como colores dominantes, tipografía legible, iconos lineales coherentes, radios consistentes y alineaciones precisas. No convertirlo en una pantalla plana de tablas ni en un dashboard genérico.

**Adaptación a la realidad del proyecto:** la imagen es una referencia visual; no es una fuente de datos ni una especificación de cálculos. No copies sus importes de ejemplo, nombres de hoteles, departamentos, usuarios ni porcentajes. Todo texto, KPI, gráfica, alerta, versión y estado debe provenir del backend o quedar claramente oculto cuando no haya datos. En particular, el gráfico que parece flujo de caja en la imagen debe representarse como `Distribución mensual del presupuesto` hasta que la Fase 10 Cash Flow exista y exponga datos reales. No simules un flujo de caja futuro para que la pantalla “se vea llena”.

**No insertar la imagen en la interfaz.** Está prohibido usar la imagen como fondo, mostrarla como una captura dentro de la aplicación o sustituir controles reales por una imagen estática. Construir cada región con componentes React funcionales y gráficos Plotly reales, conectados a datos disponibles. Usar la imagen solamente durante el desarrollo como referencia visual.

**Adaptación responsive:** igualar la composición de escritorio en pantallas amplias. En resoluciones menores, la barra lateral puede contraerse y las tarjetas/gráficas deben reordenarse verticalmente sin desbordamiento; no sacrificar legibilidad por forzar una copia exacta de las dimensiones de la imagen.

## 10. Reglas de negocio que no deben inventarse durante el rediseño

Antes de implementar, verificar en código/modelos cuáles de estas reglas ya existen:

- Qué significa exactamente `objetivo` y quién puede cambiarlo.
- Cuándo se exige una nota/justificación por desviación.
- Si se captura por departamento, sección, línea u otra unidad.
- Qué estados están permitidos para `LineaPresupuestoCaptura` y para `CicloPresupuesto`.
- Si el reparto automático ajusta el residuo en el último mes u otro mes definido.
- Qué sucede con líneas sin objetivo, líneas no editables y líneas sin cifras.
- Qué acciones crean `VersionPlan` y cuáles solo actualizan el ciclo en preparación.
- Qué datos permiten medir la cobertura por departamento.

Si una regla no existe, documentarla como decisión pendiente. No sustituirla por una suposición de frontend.

## 11. Plan de implementación

### Etapa 0 — Inspección y contrato funcional

1. Revisar modelos, esquemas, servicios, permisos y rutas reales.
2. Revisar `PanelBudget.tsx`, `CicloPresupuesto.tsx`, `estilos/budget.css`, `calculo.ts`, hooks y tests.
3. Preparar un mapa de las fuentes de datos por KPI y visualización.
4. Identificar dependencias gráficas instaladas y estrategia de carga en Next.js.
5. Registrar gaps sin modificar el backend por anticipado.

**Salida:** lista de componentes reutilizables, datos disponibles, endpoints existentes y brechas confirmadas.

### Etapa 1 — Shell de Budget Studio

1. Crear encabezado claro y navegación Resumen/Captura/Versiones.
2. Añadir stepper de ciclo conectado con las transiciones reales.
3. Implementar tarjetas KPI únicamente con datos fiables.
4. Preservar importación Excel, filtros existentes y todas las rutas funcionales actuales.

### Etapa 2 — Dashboard Plotly

1. Incorporar objetivo vs. propuesta por dimensión disponible.
2. Incorporar distribución mensual julio–junio.
3. Incorporar cobertura de captura y lista de alertas.
4. Implementar interacción de clic para filtrar/abrir líneas.
5. Medir rendimiento y tamaño del bundle.

### Etapa 3 — Captura enfocada

1. Implementar árbol de líneas y detalle seleccionado.
2. Desarrollar cuadrícula mensual con validación y estado de cambios.
3. Incorporar selector de perfil con vista previa y conciliación exacta.
4. Conectar guardado, descarte y confirmación a los servicios existentes.
5. Preservar permisos y workflow en backend.

### Etapa 4 — Versiones, auditoría y pulido

1. Añadir timeline en solo lectura.
2. Comparación entre versiones solo cuando el backend lo soporte correctamente.
3. Revisar responsive, accesibilidad, estados de error y loading.
4. Ejecutar pruebas de regresión de todas las funciones que ya existen.

## 12. Criterios de aceptación

### Funcionalidad

- El usuario puede entender cobertura, propuestas vs. objetivo y pendientes sin leer primero la tabla completa.
- Los filtros del dashboard se corresponden con los del espacio de captura.
- Al seleccionar un segmento de gráfico, se abre el contexto de datos correcto; no solo cambia un color.
- Se pueden capturar importes exactos de los doce meses fiscales en orden julio–junio.
- La suma mensual se concilia con el anual al centavo según la regla de cálculo existente.
- Los perfiles muestran la distribución real y no alteran otras líneas.
- Guardar en un ciclo no crea una `VersionPlan` oficial prematuramente; aprobar genera la versión oficial a través del flujo existente.
- Las versiones históricas son de solo lectura.
- Las transiciones del ciclo generan la bitácora existente y los permisos se validan en backend.
- Importar Excel, copiar Actual, filtros, búsqueda, guardar, descartar y exportar —si ya existe— siguen funcionando.

### Calidad y seguridad

- No existe una vía frontend para saltarse permisos o estados del backend.
- No se duplican versiones ni importes por reintentos comunes.
- Los errores de API son visibles y no hacen desaparecer cambios sin explicación.
- No hay cifras de demo ni KPIs ficticios en producción.
- La pantalla se puede usar con teclado y tiene alternativa tabular para los gráficos.
- Los charts se cargan de forma diferida cuando corresponda y no bloquean la captura si fallan.
- Las pruebas existentes pasan; se añaden pruebas para cálculos, estados, permisos e interacciones nuevas.
- Se documentan las rutas/componentes modificados y las brechas pendientes.

## 13. Prompt de ejecución para Claude Code

> Actúa como ingeniero senior frontend especializado en React/Next.js, diseñador de producto SaaS y analista de FP&A hotelero.
>
> Implementa el rediseño descrito en este documento y en `docs/Correccion_Visual_Budget_Studio.md` en el repositorio existente. La corrección visual contiene la cuadrícula exacta de referencia y prevalece para la distribución visual. Antes de escribir código, inspecciona el backend, el frontend, los modelos, los permisos, los endpoints, los hooks y las pruebas. Respeta la arquitectura y las reglas de negocio ya programadas. No reemplaces código funcional por mocks ni datos ficticios. No inventes endpoints, permisos, estados ni reglas financieras. Si detectas una brecha de datos, documéntala claramente y resuelve únicamente lo que pueda implementarse con seguridad usando el contrato actual.
>
> **Referencia visual obligatoria:** abre `docs/referencias/budget-studio-referencia.png` y úsala como guía principal de diseño. El resultado debe parecerse visualmente a esa imagen: sidebar azul marino, barra superior, cabecera de Budget, stepper horizontal, tarjetas KPI compactas, panel de barras Objetivo vs. Propuesta, lista de desviaciones, resumen del ciclo, gráfico mensual ancho, panel estacional y zona inferior con composición del presupuesto y acciones rápidas. Reproduce el mismo lenguaje visual, jerarquía y distribución con componentes reales. No muestres la imagen dentro de la aplicación ni la uses como fondo. No copies sus cifras, nombres ni datos de demostración.
>
> El resultado debe ser un Budget Studio profesional, visual e intuitivo, con dashboard accionable, gráficos Plotly interactivos, captura mensual precisa, perfiles de distribución con vista previa, workflow de ciclo claro e historial inmutable de versiones. Mantén una alternativa tabular y accesible; no sacrifiques exactitud financiera por estética. Los gráficos son herramientas de análisis, no el origen de las cifras ni el lugar donde se ejecuta la lógica financiera. Si no existen datos reales de Cash Flow, presenta distribución mensual de Budget en esa región del dashboard; no inventes un módulo futuro para imitar la imagen.
>
> Conserva los permisos y validaciones del backend como autoridad. Reutiliza `calculo.ts` para la aritmética existente. Separa los componentes por responsabilidad sin sobrearquitectura. Carga Plotly de manera eficiente y compatible con la versión actual de Next.js. No uses sliders para introducir importes exactos. No cambies el significado de Budget, objetivo, Actual, ciclo ni `VersionPlan`.
>
> Trabaja por etapas: (1) inspección y mapa de datos, (2) shell/navegación, (3) dashboard, (4) captura enfocada, (5) historial y pruebas. Ejecuta los tests disponibles después de cada etapa relevante. Al final, entrega un resumen de los archivos modificados, comportamiento implementado, pruebas ejecutadas, dependencias agregadas y brechas que sigan pendientes.

---

## Resultado esperado

Budget deja de ser únicamente una tabla horizontal. Se convierte en un entorno donde el usuario puede **ver el estado del ciclo, identificar dónde falta trabajo, comparar objetivo con propuesta, entender la distribución mensual, actuar sobre las excepciones y capturar cifras con precisión**; todo esto conservando el backend financiero y la trazabilidad ya construidos.
