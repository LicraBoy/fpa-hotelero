# Corrección visual obligatoria — Budget Studio

**Objetivo:** corregir la implementación actual para que se parezca de manera clara a `docs/referencias/budget-studio-referencia.png`. Este documento es una instrucción prioritaria para la implementación visual. Complementa `docs/Especificacion_Redisenio_Budget_Studio.md`; no sustituye ni modifica el contrato del backend.

## 1. Diagnóstico de las capturas actuales

Las capturas `budget-actual-resumen.png` y `budget-actual-graficos.png` muestran problemas de composición, no solamente falta de datos:

1. **Falta la estructura de aplicación de la referencia.** No se aprecia un sidebar estable ni una cabecera global. La pantalla parece una colección de controles del módulo, no un producto SaaS cohesionado. Reutiliza el shell global existente si lo hay; si no existe, implementa el shell mostrado en la referencia. No dupliques navegación si el shell ya existe.
2. **El encabezado del ciclo es demasiado alto y está fragmentado.** El título, la versión, el stepper, el texto de cobertura, el presupuesto generado y el historial aparecen en líneas sueltas. Agrúpalos en una cabecera compacta y un único panel de ciclo.
3. **La jerarquía tipográfica es demasiado pequeña.** Etiquetas, subtítulos, valores y leyendas apenas se distinguen. Las cifras KPI deben ser el segundo elemento más visible después del título de página.
4. **Los KPI están comprimidos en una sola fila aunque no quepan.** No permitas que cinco tarjetas estrechas se desborden o que sus textos queden cortados. Deben usar una cuadrícula responsive.
5. **Las tarjetas analíticas no forman una cuadrícula intencional.** `Principales diferencias` queda como un rectángulo vacío, el resumen aparece parcialmente cortado y el gráfico de objetivo/propuesta tiene etiquetas pequeñas. Las tres tarjetas deben ocupar columnas definidas y compartir alineación y altura.
6. **La distribución mensual y la composición quedan apiladas a ancho completo y con títulos cortados.** Eso no reproduce la referencia. En escritorio, la distribución mensual y el perfil estacional deben estar en una misma fila; la composición, ayuda y acciones rápidas van en otra fila.
7. **Los gráficos Plotly no están ajustando sus márgenes al contenedor.** Hay etiquetas cortadas y textos del donut que se enciman. Los gráficos deben recalcular su tamaño y reservar espacio para ticks, leyendas y títulos.
8. **La página tiene overflow y contenido recortado.** No debe existir desplazamiento horizontal del documento ni títulos cortados por el borde. Cada celda del grid necesita `min-width: 0`; los charts nunca deben forzarse a un ancho fijo mayor que su tarjeta.
9. **Hay demasiados espacios vacíos sin explicación.** Cuando una lista solo tenga una diferencia real, no inventes más filas. Muestra la diferencia existente y un estado neutral del tipo “No hay otras diferencias disponibles”. Ajusta el contenido al número real de registros y mantén la alineación con la tarjeta vecina.
10. **Hay ambigüedad entre el ciclo en edición y la versión oficial.** No mostrar mensajes inconexos como “Versión 8 restaurada” y “Budget generado versión 7” sin contexto. Separar explícitamente `Ciclo en edición` y `Versión oficial vigente`; el historial de restauración va en Versiones/auditoría.

## 2. Referencias de trabajo

Antes de modificar código, abre y compara visualmente estos archivos:

- **Referencia objetivo (obligatoria):** `docs/referencias/budget-studio-referencia.png`
- Captura actual del encabezado, ciclo, KPIs y primer bloque analítico: `docs/referencias/budget-actual-resumen.png`
- Captura actual de la distribución mensual y composición: `docs/referencias/budget-actual-graficos.png`

No pongas las capturas actuales dentro de la aplicación. Son material de diagnóstico para comparar el antes y después. La referencia objetivo orienta la composición, no los datos.

## 3. Composición exacta para escritorio

La referencia está diseñada como una aplicación de escritorio ancha. A partir de 1280 px de ancho de viewport, reproduce esta distribución. No apiles todos los módulos verticalmente mientras exista espacio suficiente.

### 3.1 Shell de la aplicación

- Sidebar vertical a la izquierda, ancho aproximado **196 px**, ocupando toda la altura visible. Fondo azul marino oscuro. Logotipo/nombre arriba, navegación con iconos lineales y texto, opción `Budget` claramente activa. Selector o identificación del hotel en la parte inferior si ya existe en el shell.
- El área de contenido empieza después del sidebar; no la superpongas ni le des un margen negativo.
- Barra superior blanca de aproximadamente **56–60 px** de alto, sobre el área de contenido. Búsqueda global al lado izquierdo y notificaciones/usuario al derecho solo si son parte del shell real. No inventes datos del usuario ni del hotel.
- Fondo de aplicación gris azulado muy claro (`#F3F6FB` aproximado). Superficies de cards blancas.
- Padding del área principal: **22–24 px** en escritorio. Gap entre cards: **12–14 px**.
- El contenido debe ocupar el ancho disponible. Usa `width: 100%`, `max-width` razonable si el proyecto lo requiere y `min-width: 0` en hijos de grid/flex. Prohibido fijar el contenido a un ancho que cause overflow.

### 3.2 Cabecera de Budget

Crear una cabecera de dos niveles, compacta; altura objetivo aproximada **76–96 px**, sin contar la navegación interna si se presenta en una fila independiente.

**Fila principal:**

- Izquierda: título grande `Presupuesto 2026/27` (24–28 px, peso semibold/bold).
- Debajo: rango fiscal `Jul 2026 – Jun 2027` y una línea secundaria discreta.
- Derecha: selector de versión oficial vigente, acceso al historial de versiones y acción primaria del ciclo (`Abrir ciclo de presupuesto` o la acción permitida por backend). Orden de importancia: acción primaria más visible; historial como acción secundaria.
- Presenta la versión del plan y el ciclo como conceptos separados. Ejemplo de estructura, usando valores reales: `Versión oficial vigente: v7` y `Ciclo actual: Borrador`. El texto “Restaurado desde v6” pertenece al detalle/historial de versiones y no debe competir con el título.

**Navegación interna:** conserva `Resumen`, `Captura` y `Versiones`, porque ya existen funcionalmente. Hazla compacta, con pestaña activa claramente marcada, sin una barra enorme ni una segunda cabecera repetida. Puede ir debajo del encabezado principal; no eliminarla para imitar la imagen.

### 3.3 Panel del ciclo presupuestario

Una sola tarjeta horizontal a todo lo ancho, de aproximadamente **76–88 px** de alto en escritorio:

- Izquierda/centro: stepper horizontal `Borrador → Enviado → Revisión → Aprobado → Bloqueado`.
- Cada etapa tiene círculo pequeño con número/estado, etiqueta corta y conexión sutil. Estado actual con fondo azul/teal y contraste suficiente; etapas completadas pueden usar color sobrio, no activas en gris.
- A la derecha: anillo/progreso de cobertura y el texto `617 de 617 líneas` o el dato real disponible.
- Acción principal de ciclo alineada en el lado derecho o en la cabecera; no repetir botones equivalentes en varias partes.
- Debajo del stepper no debe existir una lista de mensajes sueltos que duplique los mismos datos. La bitácora se abre desde `Historial del ciclo` en una línea compacta o un drawer/modal.
- Las transiciones y los estados se derivan del backend. El diseño no habilita acciones que el usuario no tenga permitidas.

### 3.4 Fila de KPI: exactamente cinco espacios iguales cuando el ancho lo permita

Ubicarla **inmediatamente debajo del panel del ciclo**. En escritorio amplio usar:

```css
.budget-kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}
```

Cada tarjeta debe tener altura visual similar (aprox. **120–136 px**), padding de 14–16 px, borde fino, radio consistente (10–14 px) y sin sombras fuertes.

KPI recomendados con datos que existen en la pantalla/backend actual:

1. `Cobertura de captura`: numerador/denominador, porcentaje y barra o anillo pequeño.
2. `Propuesta anual`: total anual capturado en moneda del reporte.
3. `Diferencia vs. objetivo`: diferencia calculada según las reglas del dominio y su etiqueta neutral (`Sobre objetivo`/`Bajo objetivo`) si corresponde.
4. `Líneas sin capturar`: cantidad de líneas que faltan, con subtítulo.
5. `Secciones incompletas`: total de secciones con líneas pendientes, solo si esta métrica se puede derivar correctamente.

Diseño interior de tarjeta: etiqueta discreta arriba; icono pequeño en contenedor de tono suave; cifra grande (24–28 px, usando `font-variant-numeric: tabular-nums`); contexto abajo (12–13 px). Sparklines solo si existen series temporales reales y aportan valor. No inventar series para llenar la tarjeta.

### 3.5 Primera fila de análisis: tres columnas, como la referencia

Esta fila va inmediatamente después de KPI y ocupa tres columnas. Es la región clave para que el dashboard deje de parecer una lista de cards apiladas.

```css
.budget-analysis-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(250px, 1fr) minmax(220px, 0.84fr);
  gap: 12px;
  align-items: stretch;
}
```

Altura visual objetivo de las tres tarjetas: **285–310 px** en escritorio, con contenido alineado arriba. No uses una altura fija para toda la página; solo una altura mínima/objetivo coherente para esa fila.

**Columna izquierda — `Objetivo vs. propuesta por sección`**

- Aproximadamente 48–50% del ancho de la fila.
- Título y subtítulo arriba a la izquierda. Control `Ver como tabla` o menú de opciones alineado arriba a la derecha, sin tapar el título.
- Gráfico Plotly de **barras horizontales agrupadas** o agrupadas comparables para `Objetivo` y `Propuesta`; la decisión final debe maximizar legibilidad con los datos disponibles.
- Etiquetas de sección legibles. Para nombres largos, usar salto de línea controlado o truncar con tooltip; nunca cortar la mitad de la tarjeta ni montar las etiquetas sobre las barras.
- Leyenda pequeña arriba o debajo del subtítulo. No desperdiciar 25% del área en una leyenda grande.
- Área del gráfico: llena el ancho/alto interno restante sin invadir el header/card. Deja margen izquierdo suficiente para los nombres de sección.

**Columna central — `Principales diferencias`**

- Aproximadamente 27–29% del ancho de la fila.
- Mostrar máximo cinco diferencias **reales**, ordenadas por magnitud según el criterio acordado y con importe, línea y contexto de la diferencia.
- Cada elemento usa una fila compacta; la etiqueta puede truncarse con tooltip, el importe se alinea a la derecha.
- Utiliza rojo/naranja únicamente cuando se pueda determinar que la desviación es adversa; de lo contrario, un indicador neutral y el texto `Sobre objetivo`/`Bajo objetivo`.
- No dejar una tarjeta casi vacía con una sola línea perdida en medio. Si solo hay una diferencia, colócala arriba y debajo añade un empty state discreto explicando que no hay más diferencias disponibles. No crear ejemplos falsos.
- Encabezado con título, subtítulo breve y enlace `Ver todas` solo si existe destino funcional.

**Columna derecha — `Resumen del ciclo`**

- Aproximadamente 22–24% del ancho de la fila.
- Estado actual en badge pequeño; cobertura como `617 de 617 líneas capturadas (100%)`; próxima acción real según estado y permisos.
- Mostrar como máximo tres acciones/pendientes cortos. Si no existe un dato, ocultar ese renglón en vez de usar un cero artificial.
- Botón secundario `Ver historial de transiciones` en la parte inferior si la ruta/modal existe.

### 3.6 Segunda fila de análisis: distribución mensual y perfil estacional

Va debajo de la primera fila con un gap vertical de 12 px. La distribución mensual debe ser una tarjeta horizontal ancha y el perfil estacional una tarjeta angosta lateral, **en la misma fila** en escritorio.

```css
.budget-trend-grid {
  display: grid;
  grid-template-columns: minmax(0, 2.9fr) minmax(240px, 0.9fr);
  gap: 12px;
  align-items: stretch;
}
```

Altura sugerida de ambas tarjetas: **220–250 px**.

**Izquierda — `Distribución mensual`**

- Aproximadamente 75–78% del ancho.
- Barra del header: título/subtítulo a la izquierda y botón `Ver como tabla` alineado a la derecha.
- Gráfico Plotly de los 12 meses fiscales en orden julio–junio; barras azules consistentes con la imagen de referencia.
- Etiquetas x legibles (`Jul 26`, `Ago 26`, …, `Jun 27`) y eje Y con formato monetario abreviado. Tooltip con el importe completo del mes.
- Renderizar solo las series reales disponibles. Si solo está la propuesta mensual, una única serie azul está bien; no inventar objetivo/actual para imitar la referencia.
- Evitar que el título del gráfico, el eje Y o el botón invadan otros elementos.

**Derecha — `Perfil de temporada` / `Distribución aplicada`**

- Aproximadamente 22–25% del ancho.
- Selector del `PerfilDistribucion` solo cuando el usuario tenga permiso y la línea/ciclo permitan editar; de lo contrario, presentar un resumen de lectura.
- Mini gráfico de 12 meses con una línea o barras del porcentaje/distribución del perfil seleccionado, con un tooltip y meses abreviados.
- Mostrar nombre del perfil y un enlace `Ver distribución` si abre una vista funcional.
- No confundir una distribución configurada con datos reales ni con una predicción.

### 3.7 Tercera fila: composición, ayuda y acciones rápidas

Debajo de la segunda fila, misma alineación izquierda/derecha, gap 12 px:

```css
.budget-bottom-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1.25fr) minmax(220px, 1fr);
  gap: 12px;
  align-items: stretch;
}
```

Altura sugerida: **205–235 px**, con posibilidad de crecer por contenido sin romper la cuadrícula.

**Izquierda — `Composición del presupuesto`**

- Mostrar distribución del importe por sección.
- Donut Plotly solo si hay pocas secciones (idealmente seis o menos) y se pueden leer las etiquetas.
- Si existen más de seis secciones, no mostrar 20 etiquetas alrededor del donut. Mostrar top 5 + `Otras secciones` agregadas **solo para visualización**, con leyenda legible y total reconciliado; dejar botón `Ver detalle por sección` para consultar el desglose completo. Explicar que el gráfico agrupa categorías menores cuando corresponda.
- Alternativamente, usar barras horizontales si representan mejor muchas categorías. Legibilidad tiene prioridad sobre imitar el donut exactamente.
- No permitir etiquetas que se encimen, salgan del canvas o se corten al borde.

**Centro — `Cómo funciona el Budget` / guía contextual**

- Tarjeta informativa ligera con icono, título corto y dos o tres líneas de ayuda que cambien según haya ciclo abierto o no.
- Un único enlace `Ver guía rápida` si existe contenido de destino.
- No insertar una imagen de hotel decorativa si no existe un activo de marca real. La tarjeta debe equilibrar el layout mediante texto útil, no imágenes genéricas.

**Derecha — `Acciones rápidas`**

- Cuatro botones de ancho completo, icono a la izquierda y etiqueta breve:
  1. `Copiar Actual a Budget`
  2. `Aplicar perfil de distribución`
  3. `Importar desde Excel`
  4. `Exportar reporte`
- Mostrar cada acción únicamente si existe y el usuario tiene permiso. Si no tiene permiso, ocultar o deshabilitar con explicación coherente con los patrones de la aplicación.
- Botones de acción secundaria; reservar el color sólido principal para la acción primaria del ciclo.

## 4. Sistema de diseño y proporciones

- Fuente sans-serif ya instalada en el proyecto; no introducir una nueva solo por preferencia. Usar escalas consistentes: página 24–28 px, título de card 14–16 px, KPI 24–28 px, cuerpo 12–14 px, caption mínimo recomendable 11–12 px en escritorio.
- Colores aproximados: sidebar `#10213D`/`#122541`, fondo `#F3F6FB`, card `#FFFFFF`, borde `#E1E8F0`, texto principal `#152B4D`, secundario `#63748B`, azul primario `#2F67E8`, teal `#27B7A6`. Adaptar a tokens de tema existentes si el proyecto ya tiene design system.
- Radio de cards 10–14 px. Bordes 1 px. Sombras muy suaves o ninguna. No usar una sombra grande distinta en cada card.
- Mantener alineación de encabezados, padding y botones entre todas las cards. Los botones `Ver como tabla` siempre en la parte superior derecha y con idéntico estilo.
- Utilizar números tabulares para importes. No dejar que los valores largos rompan cards: formato abreviado en dashboard (`$216.8 M`) y monto exacto en tooltip/detalle; mantener el valor completo accesible.
- Evitar que todos los textos estén en el mismo tamaño; la jerarquía tipográfica debe ser clara.
- No usar más de un color de acento saturado en la misma tarjeta salvo que el gráfico requiera diferenciar series.

## 5. Reglas Plotly obligatorias para no volver a cortar gráficos

1. El contenedor React que aloja el gráfico debe tener ancho real calculable (`width: 100%`, `min-width: 0`, altura definida por la tarjeta). El gráfico no debe usar un ancho fijo grande.
2. Configurar autosize/responsive mediante el patrón compatible con la versión instalada de `react-plotly.js`.
3. Reservar márgenes para ejes y títulos: ajustar `margin.l`, `.r`, `.t`, `.b`; activar `automargin` en ticks/ejes cuando corresponda.
4. Desactivar la barra Plotly completa si no es necesaria (`displayModeBar: false`) o usar una barra compacta; las acciones de tarjeta pertenecen al header React.
5. No colocar el título principal en el interior de la figura si ya existe un header de card React. Así se evita duplicar títulos y se aprovecha área útil.
6. Los gráficos no deben cortar labels, leyenda, títulos ni tooltips al cambiar de tamaño. No resolverlo con un `overflow: hidden` global que esconda ejes.
7. Para barras horizontales con nombres largos, reservar un margen izquierdo apropiado y permitir truncamiento consciente. Para la distribución mensual, mantener los 12 labels cortos.
8. Para donut, externalizar la leyenda y limitar las etiquetas que se dibujan dentro/alrededor del anillo. No dibujar cada etiqueta pequeña si se amontonan.
9. Definir colores de series de forma consistente: azul = objetivo o propuesta según la leyenda; teal = segunda serie; el mismo significado/color en los gráficos donde aplique. No codificar favorito/desfavorable por color salvo que la lógica de negocio lo determine.
10. Añadir estados de carga, error y sin datos con la misma altura/estilo de la tarjeta. Un fallo de Plotly no debe romper las demás secciones.
11. Antes de añadir o actualizar dependencias, comprobar `package.json` y respetar la versión instalada de Next.js/React.

## 6. Comportamiento responsive — no comprimir la versión desktop

**Escritorio ≥1280 px:** Shell completo, cinco KPI en una fila y grids de 3 columnas / 2 columnas / 3 columnas tal como se describe arriba.

**Laptop/tablet 900–1279 px:** Sidebar contraído si ya existe patrón. KPI en 3 columnas. Primera fila de análisis en 2 columnas; tarjeta Resumen del ciclo ocupa toda la fila siguiente o una columna de ancho mínimo legible. Distribución y perfil se pueden apilar si no caben cómodamente.

**Tablet estrecha 600–899 px:** KPI en 2 o 3 columnas, según ancho real. Gráficas a una columna o dos solo si cada una conserva leyendas y etiquetas legibles. Nunca reducir cada card a 100–150 px para mantener una fila de cinco.

**Móvil <600 px:** navegación lateral como drawer/menú móvil existente, KPI a dos columnas (una cuando el texto no quepa), todas las gráficas apiladas y formulario de captura adaptado a scroll vertical. Botones con área táctil adecuada.

En todos los breakpoints:

- No debe existir scroll horizontal en `body`.
- No cortar el borde izquierdo/derecho de títulos, card, leyenda ni botones.
- Evitar `min-width` en cards que exceda el espacio de su grid; solo usar `min-width` a nivel del breakpoint que soporte esa columna.
- Si el chart no tiene espacio suficiente, cambiar el layout, no reducir la tipografía hasta volverla ilegible.

## 7. Mantener datos reales y reglas de negocio

- No copiar los importes de la imagen objetivo.
- No inventar nuevas métricas. Usar los valores reales disponibles en los endpoints/modelos existentes.
- Si no existe cash flow todavía, la gráfica principal de la segunda fila es `Distribución mensual del presupuesto`, no `Flujo de caja`.
- Si no hay datos para una tarjeta, presentar estado vacío explícito o no mostrar esa tarjeta; no rellenarla con cero falso ni con datos de demo.
- Si una visualización necesita un endpoint que no existe, documentar la brecha y no simular la respuesta.
- Reutilizar el backend como autoridad para permisos/transiciones/versiones y `calculo.ts` para aritmética exacta.
- No cambiar el flujo `CicloPresupuesto → aprobación → _generar_version_plan → importar_budget_mensual/VersionPlan`.
- Mantener la tabla disponible en Captura y en las acciones `Ver como tabla`; el dashboard no sustituye la edición exacta.

## 8. Componentización visual sugerida

Se puede adaptar esta estructura a las convenciones reales del repo, evitando refactor masivo si no hace falta:

```text
BudgetStudioPage
├── AppShell existente / Sidebar
├── TopBar existente
└── BudgetPage
    ├── BudgetHeader
    ├── BudgetSubnav (Resumen / Captura / Versiones)
    ├── CicloPresupuestoCard
    ├── ResumenTab
    │   ├── BudgetKpiGrid
    │   ├── BudgetAnalyticsGrid
    │   │   ├── ObjetivoVsPropuestaCard
    │   │   ├── PrincipalesDiferenciasCard
    │   │   └── ResumenCicloCard
    │   ├── BudgetTrendGrid
    │   │   ├── DistribucionMensualCard
    │   │   └── PerfilTemporadaCard
    │   └── BudgetBottomGrid
    │       ├── ComposicionPresupuestoCard
    │       ├── AyudaBudgetCard
    │       └── AccionesRapidasCard
    ├── CapturaTab (reutiliza servicios y formularios existentes)
    └── VersionesTab (solo lectura para históricos)
```

Antes de crear componentes nuevos, inspecciona si existen componentes compartidos equivalentes. Reutiliza shell, botones, cards, tooltips, modals, hooks y tokens de estilo del proyecto cuando estén disponibles.

## 9. Verificación visual obligatoria

No dar el trabajo por terminado solo porque compila.

1. Ejecutar la aplicación y abrir Budget con datos reales disponibles en el entorno.
2. Capturar screenshot del dashboard a **1440×1000** y **1280×900**.
3. Capturar también **768×1024** y **390×844** para verificar responsive.
4. Comparar el screenshot de escritorio con `budget-studio-referencia.png` lado a lado. Deben coincidir claramente la composición de shell, cabecera, stepper, fila KPI, las tres columnas de análisis, fila de distribución mensual/perfil y fila inferior.
5. Revisar específicamente: títulos cortados; overflow horizontal; cards que no se alinean; KPI comprimidos; barras Plotly sin eje o etiquetas; donut con labels superpuestos; cards sin datos que parezcan errores; acciones fuera de su card.
6. Corregir CSS/layout e iterar al menos hasta que no queden defectos de recorte, alineación o distribución. Si existe Playwright u otra herramienta de pruebas visuales en el repo, reutilizarla; no añadir tooling pesado sin necesidad.
7. Ejecutar los tests existentes y revisar la consola del navegador; corregir warnings/errores provocados por la implementación.

## 10. Prompt corregido para Claude Code

> Necesito que corrijas el rediseño de Budget porque la implementación actual no se parece a la referencia y no tiene calidad visual presentable. Lee `docs/Especificacion_Redisenio_Budget_Studio.md` y este documento completo antes de modificar nada. Abre `docs/referencias/budget-studio-referencia.png` y compárala con `docs/referencias/budget-actual-resumen.png` y `docs/referencias/budget-actual-graficos.png`.
>
> **La referencia visual es un requisito obligatorio, no inspiración genérica.** Reproduce su composición: sidebar azul marino y topbar; cabecera compacta `Presupuesto 2026/27`; stepper del ciclo en una sola tarjeta horizontal; cinco KPI alineados en desktop; primera fila con tres columnas (Objetivo vs. propuesta / Principales diferencias / Resumen del ciclo); segunda fila con distribución mensual ancha y perfil estacional lateral; tercera fila con composición del presupuesto, ayuda contextual y acciones rápidas. Aplica los tamaños, proporciones, colores, gaps, tamaños tipográficos y comportamiento responsive definidos en este documento.
>
> La implementación actual muestra tarjetas KPI comprimidas, texto demasiado pequeño, el stepper fragmentado, espacios vacíos enormes, cards apiladas, títulos/ejes recortados, etiquetas del donut superpuestas y contenido fuera del viewport. Debes corregir estos defectos en el layout y los contenedores Plotly; no intentes resolverlo únicamente cambiando colores o radios.
>
> En escritorio ancho, utiliza los grids CSS explícitos de este documento. No mantengas cinco KPI en una fila en pantallas pequeñas: hazlos pasar a 3 o 2 columnas según el breakpoint. Todos los hijos de grid/flex deben poder encogerse (`min-width: 0`) y los charts deben responder al tamaño real del card sin ancho fijo ni recorte de ejes. En desktop debe verse una composición ordenada como la imagen objetivo, no una lista vertical de cards.
>
> Usa Plotly para los gráficos reales de análisis, con márgenes y redimensionamiento correctos. En el donut, no intentes etiquetar veinte categorías alrededor del anillo; limita etiquetas, utiliza leyenda o agrupa visualmente las categorías menores sin alterar el total ni esconder el acceso al desglose completo. Si faltan datos, usa estados vacíos elegantes, no datos ficticios ni tarjetas visualmente rotas.
>
> Mantén `Resumen`, `Captura` y `Versiones`; conserva los endpoints, modelos, permisos, estados y cálculos existentes. Distingue ciclo de presupuesto de versión oficial. No alteres el backend ni inventes datos para parecerte a la imagen. El rediseño debe construir elementos React reales; la imagen sirve solo como guía.
>
> Primero inspecciona el layout global, componentes existentes, CSS, versión de Next/React, Plotly instalado y datos disponibles. Después implementa la corrección por etapas. Al finalizar, ejecuta pruebas, verifica consola y captura screenshots a 1440×1000, 1280×900, 768×1024 y 390×844. Compara visualmente el escritorio contra la referencia y corrige las diferencias de composición, recorte, tipografía, espaciado y alineación antes de darlo por terminado. Devuelve un resumen de archivos modificados, pruebas realizadas y cualquier métrica que no pudo mostrarse porque el backend no la expone.
