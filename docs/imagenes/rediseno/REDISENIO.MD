# PROYECTO: REDISEÑO INTEGRAL DE UNA PLATAFORMA SaaS DE INTELIGENCIA FINANCIERA HOTELERA

## 1. Objetivo y responsabilidad

Actúa como un equipo senior formado por:

- Principal Product Designer especializado en software financiero empresarial.
- Staff Frontend Engineer especializado en React y TypeScript.
- Design Systems Engineer.
- Especialista en interfaces de análisis financiero, contabilidad y presupuestos.
- Especialista en visualización de datos y tablas de alta densidad.
- Especialista en accesibilidad, rendimiento y pruebas de aplicaciones web.

Tu misión consiste en transformar el frontend existente en una plataforma SaaS financiera empresarial con identidad propia, diseño sofisticado, alta densidad informativa y una experiencia de usuario excepcional.

**No quiero que te limites a dar recomendaciones, generar imágenes o construir un prototipo independiente. Quiero que trabajes directamente sobre el repositorio existente, implementes los cambios en el código real y verifiques que el producto siga funcionando.**

El resultado debe parecer un software financiero hotelero desarrollado por un equipo experimentado de producto e ingeniería, no una plantilla genérica de dashboard ni una interfaz compuesta por tarjetas decorativas generadas automáticamente.

La prioridad es construir un sistema visual duradero que permita incorporar progresivamente más áreas del hotel sin perder coherencia.

## 2. Concepto del producto

Estamos desarrollando una plataforma de inteligencia financiera que centralizará la información económica del hotel y conectará sus áreas de operación, contabilidad, presupuestos, ingresos, gastos, departamentos y auditoría.

El sistema debe transmitir cinco atributos:

1. Precisión financiera.
2. Confianza y trazabilidad.
3. Claridad para tomar decisiones.
4. Integración entre las diferentes áreas del hotel.
5. Solidez de un producto empresarial profesional.

No debe parecer una aplicación bancaria de consumo, un panel administrativo genérico ni una simple hoja de cálculo dentro de un navegador.

Debe combinar la capacidad analítica de una herramienta financiera, la claridad de una aplicación empresarial moderna y la familiaridad de una tabla contable bien diseñada.

## 3. Referencias visuales: cómo utilizarlas

Se proporcionan referencias de interfaces financieras limpias, productos SaaS profesionales y una tabla de reportes financieros.

La imagen de la tabla es especialmente importante. Utilízala para comprender la presentación y la experiencia de lectura que buscamos.

### Qué debes tomar de la referencia de la tabla

- Fondo blanco y superficies neutras.
- Tipografía limpia, legible y de jerarquía discreta.
- Encabezados agrupados por periodo.
- Separación clara entre las etiquetas y las columnas numéricas.
- Importes alineados a la derecha.
- Grupos contables jerárquicos que pueden expandirse o contraerse.
- Totales y subtotales fácilmente identificables.
- Líneas divisorias finas y discretas.
- Resaltado suave de una fila o columna seleccionada.
- Un indicador de foco preciso para la celda activa, cuando exista edición.
- Densidad suficiente para mostrar muchos datos sin perder legibilidad.
- Controles compactos y una barra de herramientas que no compita con el contenido.
- Desplazamiento horizontal natural en tablas anchas.

La tabla debe sentirse como una herramienta financiera profesional de uso diario, no como una tarjeta que contiene una tabla.

### Qué NO debes copiar de la referencia

No copies literalmente nombres, importes, años, columnas, estructuras contables, acciones de Google Sheets ni funcionalidades que pertenezcan a otro producto.

No conviertas Variance en un balance general.

La referencia determina el lenguaje visual y los principios de presentación. La estructura financiera, los campos, los cálculos y los comportamientos deben proceder del sistema existente.

Combina esta referencia con una identidad propia para nuestro producto: azul petróleo, azul ejecutivo, verde azulado discreto, fondos claros y semántica financiera rigurosa.

## 4. Antes de programar: inspección obligatoria del repositorio

El sistema actual utiliza React 19, TypeScript y Vite, sin una librería de interfaz centralizada. Tiene aproximadamente 7.600 líneas de código, temas claro y oscuro, rutas hash, tipos generados desde OpenAPI y pruebas automatizadas.

Antes de modificar archivos:

1. Inspecciona la estructura del repositorio.
2. Identifica el punto de entrada, el shell principal, las rutas y la navegación.
3. Localiza todos los componentes y estilos de Variance.
4. Identifica las dos capas de CSS de Variance y las reglas que se están pisando.
5. Revisa las tablas, filtros, paneles, formularios y componentes compartidos.
6. Comprueba cómo funcionan la autenticación, los permisos y las llamadas al backend.
7. Inspecciona el tema claro y el oscuro.
8. Examina las pruebas unitarias y las de navegador.
9. Revisa el documento funcional disponible en el repositorio.
10. Comprueba los comandos de compilación, linting, TypeScript y pruebas.

Identifica la arquitectura que conviene conservar y los puntos que deben refactorizarse.

No supongas que necesitas reescribir toda la aplicación.

**Después de esta auditoría, continúa directamente con la implementación. No te detengas en presentar un informe o un plan para que otra persona lo ejecute.**

## 5. Identidad visual definitiva

Crea un sistema visual propio para nuestra plataforma financiera hotelera.

### Paleta principal

Utiliza inicialmente estos colores como tokens del sistema de diseño:

- Azul petróleo `#142B43`: navegación principal e identidad institucional.
- Azul ejecutivo `#2563EB`: acciones primarias, selección activa e interacción.
- Verde azulado `#0F766E`: acento secundario para integración, continuidad y elementos complementarios.
- Fondo general `#F3F6FA`.
- Superficie principal `#FFFFFF`.
- Texto principal `#172B4D`.
- Texto secundario `#64748B`.
- Bordes discretos `#DCE4ED`.

La paleta debe sentirse corporativa, financiera y moderna, sin saturar la interfaz.

Utiliza rojo para las desviaciones desfavorables, verde para las favorables y ámbar para advertencias, respetando las definiciones financieras reales de la aplicación.

No conviertas cada tarjeta o sección en una combinación de colores.

### Tipografía

Define una familia tipográfica adecuada para aplicaciones empresariales, con jerarquías consistentes y una excelente legibilidad.

Utiliza cifras tabulares para facilitar la comparación de importes. Mantén coherencia en tamaños, pesos, alturas de línea y formatos numéricos.

Los números financieros deben alinearse visualmente. Las etiquetas pueden alinearse a la izquierda; los importes, porcentajes y variaciones deben seguir una regla uniforme.

### Diseño visual

Evita:

- Tarjetas grandes e innecesarias.
- Sombras fuertes y repetitivas.
- Bordes alrededor de todos los elementos.
- Exceso de iconos decorativos.
- Pastillas de colores para cada dato.
- Degradados llamativos.
- Espacios vacíos excesivos.
- Tipografía diminuta para comprimir contenido.
- El aspecto de una plantilla SaaS genérica.
- Animaciones que dificulten el trabajo.
- Paneles permanentes que reduzcan innecesariamente el área de análisis.

La calidad debe provenir de la composición, la tipografía, los alineamientos, la proporción y la consistencia, no de acumular adornos.

## 6. Prioridad máxima: la tabla de Variance

Esta es la parte más importante del rediseño.

Variance es una herramienta para analizar desviaciones entre Actual y Presupuesto. Su valor depende de que los usuarios puedan localizar problemas, entender las cifras y profundizar en sus causas rápidamente.

La tabla debe tener el protagonismo visual de la pantalla.

### Estructura financiera que debe conservarse

La tabla existente tiene 13 columnas distribuidas en tres grupos:

- Mes seleccionado.
- Acumulado del año fiscal.
- Presupuesto anual.

Cada grupo contiene Actual, Presupuesto, Variación y porcentaje de variación.

Conserva la estructura, las etiquetas reales, las cifras, los cálculos y los comportamientos existentes. No cambies las reglas contables para hacer que el diseño resulte más sencillo.

### Diseño de encabezados

Implementa encabezados multinivel claros y compactos.

Los tres grupos temporales deben diferenciarse de forma evidente. Sus cuatro subcolumnas deben mantener alineación vertical y anchuras consistentes.

Utiliza separadores verticales sutiles para dividir los grupos principales. No traces bordes fuertes alrededor de cada celda.

Los encabezados deben permanecer legibles durante el desplazamiento horizontal. Cuando resulte técnicamente viable, utiliza encabezados fijos durante el desplazamiento vertical.

### Columna de conceptos

La primera columna debe permitir identificar inmediatamente:

- Secciones financieras.
- Líneas contables.
- Totales y subtotales.
- Niveles jerárquicos.
- Elementos que pueden expandirse.
- Líneas seleccionadas.

Implementa sangrías consistentes, indicadores compactos de expansión y estilos tipográficos diferenciados.

Si resulta viable con la arquitectura existente, mantén fija la columna de conceptos durante el desplazamiento horizontal.

No utilices tarjetas dentro de la tabla ni separes visualmente cada fila como si fuera un componente independiente.

### Cifras y variaciones

Los importes deben alinearse a la derecha y presentar formatos consistentes.

Define un tratamiento claro para:

- Valores positivos y negativos.
- Variaciones favorables y desfavorables.
- Porcentajes.
- Celdas sin información.
- Totales y subtotales.
- Valores iguales a cero.

Conserva las convenciones financieras existentes para signos, paréntesis, moneda y precisión decimal.

Utiliza colores semánticos junto con un indicador textual o visual accesible. El significado nunca debe depender únicamente del color.

Destaca las filas de totales con peso tipográfico y separadores discretos. No resaltes todas las filas con fondos diferentes.

### Selección e interacción

Inspírate en el resaltado suave de fila y columna que presenta la referencia.

Implementa, según lo permita el comportamiento real del sistema:

- Resaltado de la línea seleccionada.
- Foco visible para navegación por teclado.
- Estados de hover discretos.
- Selección claramente diferenciada del error o de una variación financiera.
- Indicadores de expansión.
- Acceso al detalle de una línea sin perder el contexto.
- Navegación coherente entre cuentas y movimientos.

No confundas una celda seleccionada con una celda editable. La tabla Variance no debe parecer editable si el sistema no permite editarla.

### Densidad visual

La tabla debe ser compacta, pero nunca ilegible.

Ofrece las densidades compacta y cómoda que ya existen. Define alturas de fila, espacios internos y tamaños de texto de manera intencional.

La opción compacta debe permitir examinar más líneas. La cómoda debe facilitar sesiones de análisis prolongadas.

Evita reducir globalmente toda la interfaz para hacer caber la información.

### Rendimiento

Comprueba el comportamiento con el número de filas habitual y con las líneas que se pueden expandir.

Evita renderizados innecesarios, recalcular información repetidamente o introducir una dependencia de gran tamaño sin justificarla.

Considera una estrategia de virtualización únicamente si el volumen real de datos la hace necesaria y si puede implementarse sin romper los encabezados agrupados, las filas jerárquicas o la interacción existente.

## 7. Reorganiza Variance como una herramienta de análisis

La pantalla actual dedica demasiado espacio a la zona superior.

Quiero una composición más compacta y funcional que permita llegar rápidamente a la tabla.

### Encabezado

Presenta el nombre de la sección y una descripción breve cuando resulte útil.

Organiza las acciones de exportación a Excel e impresión en una posición consistente, sin competir con la información principal.

Conserva el periodo, el año fiscal y las versiones relevantes. Evita repetir información entre el encabezado y los filtros.

### Estado del cierre

Presenta Borrador, Comentado, Revisado, Aprobado y Bloqueado de manera compacta.

Debe resultar fácil identificar el estado actual, las acciones permitidas y las restricciones correspondientes.

No conviertas el flujo de cierre en una gran tarjeta que ocupe innecesariamente el ancho y la altura de la pantalla.

Conserva todas las reglas de permisos, confirmaciones y congelación de versiones.

### Filtros

Agrupa periodo, sección, salto a línea y búsqueda en una franja compacta.

Mantén las opciones de mostrar solo totales y ocultar líneas sin cifras.

Los filtros deben ser fáciles de localizar, operar con teclado y conservar el comportamiento actual.

Evita que cada filtro se convierta en una tarjeta o en un control sobredimensionado.

### Indicadores de resumen

Conserva las cuatro métricas actuales:

- Líneas con variación desfavorable.
- Mayor desviación desfavorable.
- Mayor desviación favorable.
- Cobertura de presupuesto.

No las elimines, pero reduce su peso visual. Deben ser útiles sin convertirse en el elemento protagonista de la página.

Prefiere una composición compacta con divisiones sutiles, etiquetas claras y cifras destacadas mediante tipografía, en vez de cuatro grandes tarjetas con iconos y bordes de colores.

No alteres sus definiciones ni introduzcas datos ficticios.

### Avisos

Conserva los avisos de mapeo y líneas sin cuentas.

Muestra su cantidad, severidad y resumen en un área compacta, con capacidad de expandir los detalles cuando se necesite.

Los usuarios deben poder entender los problemas importantes sin que los avisos ocupen permanentemente una parte desproporcionada de la pantalla.

### Herramientas de tabla

Mantén las acciones existentes para expandir, plegar, cambiar densidad e imprimir.

Ubícalas cerca de la tabla, con controles discretos, agrupados y reconocibles.

Evita duplicar botones o colocar herramientas de poca frecuencia al mismo nivel que las acciones principales.

### Distribución recomendada

En una pantalla de escritorio, la jerarquía debe ser:

1. Encabezado compacto.
2. Estado del cierre.
3. Filtros.
4. Resumen financiero compacto.
5. Avisos resumidos.
6. Controles de tabla.
7. Tabla financiera como superficie principal.

No añadas separaciones verticales innecesarias.

Como objetivo inicial, intenta reducir aproximadamente entre un 25 % y un 35 % la altura conjunta de los bloques superiores respecto de la implementación actual, verificando el resultado visual y la legibilidad antes de considerar cumplido este objetivo.

## 8. El detalle de la línea no debe quitarle protagonismo a la tabla

Actualmente existe un panel de detalle con resumen, historial, comentarios, evidencias y navegación.

Conserva sus funcionalidades, pero reconsidera su presentación.

**La tabla debe disponer de la mayor superficie útil posible cuando el usuario está analizando datos.**

Evalúa un panel lateral contextual que se abra cuando se seleccione una línea y que pueda cerrarse sin perder filtros, posición o contexto de navegación.

Cuando la anchura sea suficiente, puedes mostrar la tabla y el detalle juntos. Cuando el panel reduzca demasiado la tabla, debe poder ocultarse o superponerse sin destruir el contexto visual.

El panel debe incluir los datos y las acciones reales que ya existen:

- Actual frente a Presupuesto.
- Historial.
- Comentarios y respuestas.
- Responsable y estado.
- Evidencias adjuntas.
- Acceso a cuentas.
- Acceso a movimientos y asiento completo.

No elimines contenido ni inventes funcionalidades para simplificar la interfaz.

## 9. Un sistema de diseño para toda la plataforma

No quiero que Variance parezca profesional y que el resto del software conserve el diseño antiguo.

Construye componentes compartidos para:

- Botones y grupos de acciones.
- Inputs y selectores.
- Búsquedas y filtros.
- Tablas financieras.
- Encabezados de página.
- Breadcrumbs.
- Navegación lateral.
- Menús.
- Diálogos y confirmaciones.
- Drawers y paneles.
- Alertas y notificaciones.
- Indicadores de estado.
- Etiquetas semánticas.
- Paginación.
- Estados de carga, error, vacío y falta de permisos.
- Formularios y validaciones.

Centraliza los tokens de color, tipografía, espaciado, bordes, radios, sombras, alturas de controles y demás propiedades visuales.

Cada componente debe tener estados coherentes, propiedades tipadas y un comportamiento consistente.

Evita duplicar CSS entre pantallas o permitir que una modificación de Variance rompa Budget.

## 10. Navegación y apariencia general

Implementa una barra lateral sobria con fondo azul petróleo, iconos coherentes y una selección activa clara.

Organiza los módulos existentes en sus grupos actuales:

**Finanzas**
- Variance.
- Budget.
- Por departamento.

**Datos**
- Cargas.
- Catálogo.
- Saldos.

**Administración**
- Auditoría.
- Usuarios.

Conserva la identidad de la organización, el estado de conexión, los accesos de usuario y los elementos globales existentes.

No añadas módulos inexistentes al menú para aparentar que el producto está más completo.

El diseño debe poder extenderse en el futuro a más áreas del hotel mediante los mismos componentes, patrones y reglas visuales.

## 11. Aplicación a los demás módulos

Después de validar el diseño de Variance, adapta el sistema visual al resto de las pantallas.

### Budget

Conserva la edición mensual, la comparación con Actual, los totales, el ajuste porcentual, la importación y el versionado.

Mejora la legibilidad de la tabla, los controles de captura y la identificación de las acciones de guardado.

### Por departamento

Mantén la agrupación por departamento y tipo, los importes y la expansión de cuentas. Conserva la fila «Sin departamento».

### Cargas

Conserva el flujo de cuatro pasos, las comprobaciones de calidad, la confirmación de reemplazo y el historial.

Mejora la jerarquía de errores, advertencias, resultados y acciones principales.

### Catálogo

Conserva la importación CON020, los filtros y el árbol jerárquico.

### Saldos

Mantén débito, crédito y resultado por cuenta y mes, con una tabla consistente con la del resto de la aplicación.

### Auditoría

Conserva los filtros, la bitácora y el indicador «Cadena íntegra».

Prioriza la trazabilidad, la lectura de registros y la claridad de los estados.

### Usuarios y Mi cuenta

Mantén la administración de usuarios, roles, asignación de secciones, activación, desactivación, restablecimiento de contraseñas, desbloqueo y configuración de seguridad.

Aplica el mismo sistema de diseño a los formularios y las confirmaciones de operaciones sensibles.

## 12. Tecnologías: decide con criterio de ingeniería

La base actual es React 19, TypeScript y Vite. Mantén esa arquitectura salvo que una necesidad técnica real justifique otra decisión.

Evalúa una integración incremental de:

- Tailwind CSS para gestionar estilos y tokens, si encaja con el CSS existente.
- shadcn/ui para componentes reutilizables.
- Radix UI para primitivas de interacción accesibles.
- Lucide React para iconografía.
- TanStack Table u otra solución especializada si facilita la gestión de tablas complejas sin perder comportamientos actuales.

No instales dependencias por moda ni migres todo el frontend únicamente para utilizar una librería concreta.

Verifica compatibilidad de versiones, configuración de Vite, TypeScript, temas y estilos actuales antes de introducir cambios.

No migres a Next.js, no cambies el backend ni sustituyas el sistema de rutas existente sin una justificación técnica y un plan de compatibilidad adecuado.

Prioriza componentes mantenibles, CSS organizado, contratos tipados y código fácil de probar.

No incorpores gráficos ficticios para decorar las pantallas. Las visualizaciones futuras deberán responder a necesidades reales y utilizar datos disponibles.

## 13. Funcionalidades y seguridad que deben permanecer intactas

El rediseño es una intervención visual y de experiencia de usuario, no una redefinición de las reglas de negocio.

Conserva:

- Autenticación de producción.
- Verificación en dos pasos mediante código de seis dígitos cuando corresponda.
- Bloqueo tras cinco intentos fallidos.
- Selector de usuario de prueba en desarrollo.
- Roles de Contralor, Analista, Responsable de departamento, Dirección y Auditoría.
- Restricciones de acceso y secciones disponibles para cada rol.
- Rutas hash persistentes.
- Mensajes de «Sin acceso».
- Tipos generados desde OpenAPI.
- Contratos y llamadas del backend.
- Exportación a Excel con fórmulas vivas.
- Impresión.
- Transiciones del cierre y congelación de versiones.
- Filtros y opciones de tabla.
- Comentarios, respuestas y evidencias.
- Navegación hacia cuentas, movimientos y asientos.
- Presupuesto mensual, importaciones y versionado.
- Cargas, catálogo y saldos.
- Auditoría y administración de usuarios.
- Tema claro y tema oscuro.

No expongas credenciales, no relajes la CSP, no introduzcas HTML inyectado y no modifiques la forma segura de representar textos provenientes de archivos o usuarios.

No elimines pruebas para conseguir que el proyecto pase las verificaciones.

## 14. Accesibilidad, responsive y experiencia de uso

La interfaz debe seguir siendo funcional en distintos tamaños de pantalla.

Conserva la necesidad de adaptación alrededor de 1024 px y mejora el comportamiento en anchos inferiores cuando sea razonable.

En pantallas estrechas:

- Reorganiza filtros y acciones.
- Mantén identificables los controles principales.
- Evita que todo el documento tenga desplazamiento horizontal.
- Permite que la tabla gestione su propio desplazamiento horizontal.
- No comprimas los importes hasta volverlos ilegibles.
- Adapta el detalle de línea a un drawer o pantalla contextual.
- Evita perder filtros o posición al cambiar de vista.

Implementa foco visible, nombres accesibles, navegación por teclado, contraste adecuado y estados que no dependan únicamente del color.

El tema oscuro debe tener una paleta y una jerarquía diseñadas de forma específica; no debe ser una inversión automática de todos los colores.

## 15. Verificación visual y pruebas

Antes de finalizar, ejecuta las comprobaciones disponibles en el repositorio.

### Verificaciones técnicas

- TypeScript.
- Linting.
- Compilación de producción.
- Pruebas unitarias.
- Pruebas de navegador.
- Consola del navegador.
- Errores de red y de integración relevantes.

El proyecto tiene un conjunto existente de pruebas unitarias y de navegador. Inspecciónalo y utiliza sus escenarios como base de regresión. No debilites las pruebas para que pasen.

### Verificaciones funcionales

Comprueba al menos:

- Navegación entre módulos.
- Permisos por rol.
- Filtros de Variance.
- Expansión y contracción de grupos.
- Densidad de tabla.
- Apertura y cierre del detalle de línea.
- Comentarios y evidencias.
- Exportación e impresión.
- Flujo de cierre.
- Operaciones de Budget.
- Los flujos principales de Cargas.
- Tema claro y oscuro.

Usa los datos reales disponibles en el entorno de desarrollo. No sustituyas los datos de la API por valores ficticios para hacer una demostración visual.

### Verificaciones visuales

Captura y examina la interfaz ejecutándose en el navegador.

Comprueba, como mínimo:

- Pantalla de escritorio a 1440 × 900 px.
- Una anchura de aproximadamente 1024 px.
- Tema claro.
- Tema oscuro.
- Vista de Variance con la tabla visible.
- Estado de una línea seleccionada.
- Detalle abierto y cerrado.

Compara los resultados con la referencia. Corrige problemas de alineación, densidad, encabezados, desbordamiento y jerarquía antes de dar por terminado el trabajo.

No consideres que una pantalla está terminada únicamente porque el código compile.

## 16. Criterios finales de aceptación

El rediseño se considerará terminado cuando:

1. Variance tenga una identidad visual financiera profesional, sobria y reconocible.
2. La tabla sea el centro de la experiencia de análisis.
3. Las 13 columnas y sus agrupaciones se conserven y se lean correctamente.
4. Los importes, variaciones, totales y subtotales presenten una jerarquía precisa.
5. La pantalla superior ocupe menos espacio sin perder funcionalidades.
6. Los filtros y herramientas estén organizados de forma compacta.
7. El detalle de línea no reduzca innecesariamente el área de análisis.
8. Todos los módulos compartan los mismos fundamentos visuales.
9. La interfaz funcione correctamente en tema claro y oscuro.
10. Los permisos, las operaciones financieras y las integraciones sigan funcionando.
11. La compilación y las pruebas disponibles hayan sido ejecutadas y sus resultados estén documentados.
12. No existan regresiones conocidas sin identificar ni problemas visuales importantes pendientes.

## 17. Forma de trabajar y entrega

Ejecuta el trabajo en esta secuencia:

1. Audita el repositorio.
2. Define y centraliza los tokens visuales.
3. Refactoriza los componentes comunes y el shell.
4. Implementa el nuevo Variance.
5. Perfecciona la tabla financiera y el detalle contextual.
6. Aplica el sistema de diseño a los demás módulos.
7. Verifica el resultado visual y funcional.
8. Corrige regresiones.
9. Entrega un resumen de los cambios realizados.

Al finalizar, informa con precisión sobre:

- Archivos y componentes relevantes modificados.
- Decisiones de arquitectura y dependencias.
- Pantallas completadas.
- Pruebas ejecutadas y resultados.
- Problemas pendientes.
- Funcionalidades que no hayas podido verificar.

No afirmes que una prueba pasó si no la ejecutaste. Distingue los fallos preexistentes de los introducidos por los cambios.

### Instrucción final

Empieza inspeccionando el código real y continúa con la implementación.

No te detengas después de diseñar un plan. No generes una imagen como sustituto de la interfaz. No construyas una maqueta aislada. No elimines funcionalidades para simplificar el trabajo.

**Quiero convertir esta plataforma en un producto SaaS financiero hotelero profesional, compacto, visualmente excelente y preparado para crecer. La referencia de la tabla marca el estándar de limpieza y legibilidad; los datos, el comportamiento y las reglas de negocio del sistema existente definen lo que debes implementar.**