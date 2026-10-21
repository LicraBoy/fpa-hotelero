# Resumen del frontend (octubre 2026)

Estado de `main` (commit `609bfe4`). Carpeta `frontend/`. Se describe lo que **existe hoy**; al final
están los límites.

## 1. Tecnología y estructura
- **React 19 + TypeScript + Vite.** Sin librería de interfaz: componentes y CSS propios. Única
  dependencia de ejecución, además de React: la tipografía Inter (`@fontsource-variable/inter`).
- **~7 600 líneas** de TypeScript. CSS dividido en `src/estilos/` (tokens, layout, componentes,
  variance, budget, datos, variance-v2, departamentos, pulido, cuenta, flujos, transversal).
- **API tipada:** los tipos se generan del OpenAPI del backend (`npm run api:tipos`); una prueba del
  backend falla si el `openapi.json` versionado se desvía. Todas las llamadas pasan por
  `src/api/cliente.ts` (`obtenerTipado`, `enviarJson`, subidas y descargas) y `useDatos`.
- **Sin router externo:** rutas por hash validadas con listas blancas (`src/ruta/`).
- **Tema claro y oscuro** (automático y con interruptor), tamaño de barra lateral y densidad de la
  tabla recordados solo durante la pestaña (`sessionStorage`, solo preferencias).

## 2. Entrada, sesión y roles
- **Producción:** pantalla de entrada con usuario (correo) y contraseña; pide el código de 6 dígitos
  si la cuenta tiene verificación en dos pasos. Errores genéricos (no revela si la cuenta existe);
  cuenta bloqueada tras 5 intentos. Un 401 durante el uso devuelve a la entrada.
- **Desarrollo** (`FPA_ENTORNO=desarrollo`): selector «Usuario (desarrollo)» con un usuario por rol y
  botón «Probar inicio de sesión real».
- **Menú de usuario** (pie de la barra lateral): «Mi cuenta» y «Cerrar sesión».
- **Roles** (espejo en `permisos.ts`; el servidor decide siempre): Contralor, Analista, Responsable
  de departamento (solo sus secciones del Variance), Dirección (lectura, sin detalle de movimientos),
  Auditoría/consulta.

## 3. Navegación
- **Barra lateral** con tres grupos y solo lo que el rol puede abrir:
  - **Finanzas:** Variance, Budget, Por departamento.
  - **Datos:** Cargas, Catálogo, Saldos.
  - **Administración:** Auditoría, Usuarios.
- **Barra superior:** plegar el menú, «Ubicación» (migas), selector de hotel, estado de la API
  («API conectada»), tema y usuario.
- **Una ruta por pantalla** (`#/variance`, `#/budget`, `#/departamentos`, `#/cargas`, `#/catalogo`,
  `#/saldos`, `#/auditoria`, `#/usuarios`, `#/cuenta`): se puede enlazar, sobrevive a recargar, y una
  ruta sin permiso muestra «Sin acceso» sin consultar nada. Sin ruta o con una inexistente se abre
  la primera pantalla disponible y la dirección se completa.
- Catálogo único de pantallas en `src/ruta/navegacion.ts`; solo aparece lo que existe.

## 4. Variance (pantalla principal)
- **Encabezado:** periodo, año fiscal, versión de mapeo y de Budget; botones **Exportar a Excel**
  (con fórmulas vivas; oculto para quien tiene acceso limitado) e **Imprimir**.
- **Barra «Cierre del periodo»:** estado (Borrador, Comentado, Revisado, Aprobado, Bloqueado), solo
  los pasos que el rol puede dar, nota obligatoria al devolver o reabrir, versiones congeladas al
  aprobar (mapeo, Budget, huella) e historial.
- **Filtros:** selector de periodo con anterior/siguiente, sección, «Saltar a» una sección, búsqueda
  de línea (resalta lo encontrado), «Solo totales y subtotales» y «Ocultar líneas sin cifras».
- **Tarjetas de resumen:** líneas desfavorables, mayor desviación desfavorable, mayor desviación
  favorable y cobertura de Budget.
- **Avisos** plegables (meses sin carga, líneas sin cuentas, etc.).
- **Tabla:** 13 columnas (Mes, Acumulado y Presupuesto anual × Actual, Presupuesto, Variación, %),
  secciones plegables con conteo y desfavorables, subtotales y totales distinguidos, encabezado y
  columna de línea fijos, «Expandir todo / Plegar todo», densidad cómoda/compacta, variación con
  flecha y color (favorable = positiva), cifras de Actual como enlace al desglose. Cada línea muestra
  un indicador con su número de comentarios (y cuántos pendientes).
- **Panel lateral de la línea** (se cierra con Esc): barras Actual contra Presupuesto para Mes,
  Acumulado y Anual; enlaces a «Ver cuentas»; **Historial de la cifra** (cargas con su hash, cambios
  de mapeo, capturas, comentarios y cierre, con quién y cuándo); **Comentarios**.
- **Comentarios:** hilo por línea, periodo y bloque (mes o acumulado); responsable, estatus
  (pendiente, explicado, aprobado); respuestas; edición solo del autor con marca «editado»; evidencia
  adjunta (PDF, PNG, JPG o .xlsx) que se descarga como archivo. El texto siempre se muestra como
  texto, nunca como HTML.
- **Recorrido de desglose:** Línea → cuentas con su aporte y si cuadra (con los motivos cuando el
  Actual es cero) → movimientos de la cuenta (50 por página, «Cargar más») → asiento completo con su
  Débito y Crédito. Migas y «Volver» en cada paso. El rol Dirección ve el reporte sin enlaces de
  detalle.

## 5. Por departamento
Importes del Variance agrupados por el **departamento de la cuenta** del catálogo de Novohit, del mes
o del acumulado, separados por tipo (Ingreso, Nómina, Operación, Costo, Otros, Sin tipo), con Gasto y
Resultado. Tarjetas con departamentos, cuentas sin departamento y cuentas sin tipo; fila destacada
«Sin departamento»; cada departamento se despliega con sus cuentas (enlace al desglose si el rol
puede). Aclara que el Budget y la variación no se calculan por departamento.

## 6. Budget
Edición del Budget mes a mes por línea, con el Actual al lado como referencia, totales calculados al
instante, filtros (año fiscal, sección, búsqueda, «Solo líneas editables»), «Copiar el Actual» con
ajuste en % a las líneas visibles (opción «Solo meses sin Budget»), captura del Actual de líneas sin
cuentas (p. ej. Exchange Rate), importar el Budget desde el Excel de Contraloría, barra fija
«Guardar como versión nueva» / «Descartar cambios» (cada guardado crea versión; la anterior se
conserva).

## 7. Datos
- **Cargas:** flujo de cuatro pasos (fuente CON130 o Excel del Variance; archivo .xls/.xlsx/.csv;
  meses declarados opcionales; validar y subir), resultado con reporte de calidad, confirmación
  explícita para reemplazar una carga vigente, historial con estado (vigente/reemplazada) y «Ver
  calidad». Los archivos se rechazan con mensaje claro (falsos, con macros, demasiado grandes).
- **Catálogo:** importar el catálogo oficial (CON020, .xls); árbol de cuentas con búsqueda, filtros
  (Todas, Con movimientos, Sin jerarquía, Fuera del catálogo) y detalle de la cuenta.
- **Saldos:** por mes, débito, crédito y resultado de cada cuenta, con filtro por código y totales.

## 8. Administración
- **Auditoría:** bitácora con filtro por tipo de evento (etiquetas en español), detalle del evento e
  indicador «Cadena íntegra / alterada» con el último hash y «Verificar de nuevo».
- **Usuarios** (solo Contralor): lista con rol, secciones, estado (activa, bloqueada, inactiva) y
  verificación en dos pasos; crear usuario (contraseña temporal que se muestra una sola vez), editar
  rol y secciones asignadas, activar/desactivar, restablecer contraseña, desbloquear.
- **Mi cuenta:** cambiar contraseña (política mínima, cierra las demás sesiones) y activar o
  desactivar la verificación en dos pasos (clave y dirección `otpauth://`).

## 9. Seguridad del frontend
- Política CSP estricta sin nada en línea; sin `dangerouslySetInnerHTML`, `innerHTML` ni `eval`
  (lo comprueba `scripts/verificar_seguridad.mjs` dentro de `npm run lint`).
- Ninguna credencial en el almacenamiento del navegador: la sesión es una cookie `HttpOnly`.
- Todo texto que viene de archivos o personas (conceptos de movimientos, comentarios) se muestra
  como texto.

## 10. Accesibilidad y diseño
Regiones y encabezados con nombre, botones reales, foco visible, `aria-current` en la navegación,
estados con texto además de color, cifras con signo y flecha, responsivo hasta ~1024 px (menú
plegable, tablas con desplazamiento), impresión del Variance en hoja horizontal.

## 11. Pruebas
- **63 pruebas unitarias** (rutas, formato de dinero con BigInt, porcentajes, periodos, resumen del
  Variance, tema).
- **16 archivos de pruebas de navegador** (95 pruebas): carga de archivos, Variance, desglose,
  exportación a Excel contra cifras de referencia, seguridad (CSP), navegación y permisos, usuarios,
  login, comentarios, cierre, integridad de la bitácora, departamentos.

## 12. Límites conocidos (lo que no hace)
- Sin gráficas interactivas (solo barras simples); Plotly o ECharts quedan para después.
- Sin datos operativos de otros departamentos (Recepción, Mantenimiento, Ama de Llaves) ni
  integraciones; la vista por departamento solo usa el catálogo contable.
- Sin Budget ni variación por departamento; el Budget se edita por línea del reporte.
- Sin notificaciones por correo (Fase 5.6 diferida).
- El selector de archivos usa el botón nativo del navegador («Choose File» según el idioma).
- Las dos capas de CSS de Variance (`variance.css` y `variance-v2.css`) conviven con reglas que se
  pisan; funcionan, pero no se fusionaron.
- El diseño visual no sigue todavía una librería de componentes moderna; hay una propuesta aparte
  para cuando se decida el rediseño.
