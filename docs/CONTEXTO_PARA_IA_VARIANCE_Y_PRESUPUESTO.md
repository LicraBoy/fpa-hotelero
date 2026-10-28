# Contexto para la IA: Variance y Presupuesto con detalle por cuenta

> Pega este documento al inicio de un chat nuevo. Rutas: `B/` = `backend/fpa`, `F/` = `frontend/src`,
> `D/` = `docs`. Fecha de corte: 26-oct-2026. Rama: `feat/budget-studio-redesign` (con cambios sin commitear).

## 1. Qué es el proyecto y qué se pide ahora

Plataforma FP&A hotelera (hotel piloto: Torres Mazatlán). Contraloría decidió **no abrir fases nuevas**
(Rolling Forecast, Drivers, Cash Flow quedan fuera) y **pulir la base**: mejorar el Budget/Presupuesto.
Mandó un Excel del presupuesto que ya no trae solo totales, sino **las tablas internas de cada cuenta**.
El trabajo se centra **solo en Variance y Presupuesto**. La estructura exacta de ese Excel se explicará
después (ver sección 9); no hay datos reales en este documento ni deben subirse al repo.

## 2. Reglas del proyecto (obligatorias)

- Dinero: `Decimal` en backend, `BigInt` en micros en frontend (`calculo.ts`, `util/dinero.ts`). Nunca `float`.
- Cálculo puro y determinístico; la IA no calcula cifras. Servicios sin acceso a BD cuando sea posible.
- **Una versión de Budget nunca se edita** (ADR 0003): se crea una nueva y la anterior pasa a `reemplazada`.
- CSP estricta (ADR 0004): **sin `style=` en línea** ni `style={{}}`; `scripts/verificar_seguridad.mjs` lo comprueba.
  Sin librerías de UI. Plotly ya está instalado.
- Lo no confirmado con Contraloría se marca `[POR VALIDAR]`. No inventar procesos de Torres.
- Sin Excel ni datos reales en el repo. Sin SQL de un solo motor (todo por SQLAlchemy).
- No tocar `F/pantallas/budget/calculo.ts` sin un defecto demostrado y pruebas específicas.
- No inventar rutas, páginas ni funciones; no hacer commit ni push sin que el usuario lo pida.
- Cuando se cambie la API: `npm run api:tipos` y versionar `openapi.json` y `schema.d.ts`
  (hay una prueba backend que lo exige: `test_openapi_versionado.py`).

## 3. Stack, puertos y comandos

- Backend: FastAPI + SQLAlchemy + SQLite + Alembic (`backend/fpa`, 22 migraciones; última `0022_ciclo_presupuesto`).
- Frontend: React 19 + TypeScript + Vite, CSS propio (`F/estilos/`), sin librería de UI.
- Puertos: desarrollo API 8100 / web 5180; e2e API 8101 / web 5181 (base temporal en `backend/.e2e/`).
- Backend (desde `backend/`): `.venv\Scripts\python -m pytest`, `ruff check .`, `ruff format --check .`, `mypy fpa`.
- Frontend (desde `frontend/`): `npm.cmd run test:unit`, `npm run lint` (oxlint + verificación de seguridad),
  `npm run build`, `npm run e2e`.
- **Para correr e2e hay que exportar `FPA_CLAMAV_ACTIVO=false`** (no hay `clamd`; si no, las subidas dan 503).
- Identidad de desarrollo: `FPA_ENTORNO=desarrollo` + cabecera `X-Usuario-Dev` (`analista@torres.local`,
  `contralor@torres.local`) o el selector "Usuario (desarrollo)" del sidebar. Por defecto el entorno es producción.
- Roles: contralor, analista, responsable_area, dirección, auditoría. Permisos clave: `variance:leer`,
  `drilldown:leer`, `budget:leer/importar/capturar/objetivo/revisar/aprobar/bloquear`, `mapeo:*`, `carga:*`.
  Espejo solo visual en `F/permisos.ts`; el servidor autoriza siempre. Todo marcado `[POR VALIDAR]`.
- Python: el `.venv` puede ser el de Microsoft Store y colgarse a veces; pedir al usuario que arranque los
  servidores con `iniciar_servidores.bat` en vez de procesos ocultos.

## 4. Variance: cómo funciona hoy

Motor en `B/servicios/variance.py` (`calcular_variance`) y `B/calculo/` (puro).

- **Actual** (mes y YTD) = `Σ signo × neto(cuenta)`, `neto = Débito − Crédito` de `SaldoMensualCuenta`
  (derivado de la carga vigente de movimientos). Los vínculos línea→cuenta salen de la `VersionMapeo`
  aprobada (`MapeoLineaCuenta`, signo ±1). Código: `B/calculo/actual.py`, `B/servicios/actual.py`.
  Líneas sin cuentas (p. ej. tipo de cambio) usan `ValorCapturado` (Actual capturado a mano).
- **Budget**: de la `VersionPlan` vigente del año fiscal. Si hay `LineaPlanMensual`, el mes es el del periodo
  y el YTD es la suma del año fiscal (si falta un mes, el YTD queda en blanco con advertencia). Si no hay
  filas mensuales y `periodo_corte == periodo`, usa `LineaPlan.mes/ytd`. Anual: `LineaPlan.anual`.
  Si el Budget y el mapeo usan estructuras de reporte distintas: `PlanIncompatible`.
- **Totales/subtotales**: `B/calculo/totales.py` con `ReglaSumaLinea` (`linea = Σ coef × componente`,
  coef ±1 o factor como 0.16). También se aplican al Budget.
- **Variación**: `B/calculo/variance.py`. Convención `REAL_MENOS_PRESUPUESTO` (ingresos) o
  `PRESUPUESTO_MENOS_REAL` (gastos). **Manda lo que diga el Excel de Contraloría** (`ConvencionLinea`, por línea
  y bloque mes/ytd/anual, incluye `suma_de_variaciones`); si no hay, se deduce por clase de cuenta. Var % =
  Var / Budget con el signo del Budget (Budget 0 → +1/−1/0; `[POR VALIDAR]`). Variación `None` si no hay Budget.
- Año fiscal julio–junio (`B/calculo/ano_fiscal.py`). Ensamblado: `B/calculo/motor.py` (`armar_variance`).
- **Cierre**: `B/servicios/cierre.py` congela mapeo y plan de un periodo; `cierre_candado.py` bloquea cargas.
  Caché en memoria de reportes (TTL 300 s, `cache_reportes.py`).
- **Drill-down**: `B/servicios/drilldown.py` (línea → cuentas → movimientos → asiento).
- **Estructura del reporte**: `B/modelos/reporte.py` (`VersionEstructuraReporte`, `LineaReporte` con `tipo`
  seccion/detalle/subtotal/total/informativa y **`fila_origen`**, `ReglaSumaLinea`, `ConvencionLinea`);
  mapeo en `B/modelos/mapeo.py`.
- **API** (`/api/v1/hoteles/{hotel_id}/...`, en `B/api/v1/`): `variance.py` (`GET /variance`,
  `GET /variance/exportar`), `drilldown.py`, `historial.py`, `cierres.py`, `comentarios.py`, `departamentos.py`;
  estructura/mapeo/convenciones en `mapeo.py`.
- **Ingesta del Excel de Variance** (`B/ingesta/`): `variance_estructura.py`, `variance_reglas.py`,
  `variance_mapeo.py`, `variance_valores.py`, `variance_convenciones.py`, `variance_base_datos.py`,
  `variance_mzt.py` (Mazatlán: reglas y mapeo desde fórmulas de la hoja `Jul-Ago`), `formato_variance.py`
  (`Formato.VT` / `Formato.MZT`). **Las fórmulas del Excel nunca se evalúan**: solo se reconocen patrones
  (`SUMIFS('cuenta'!L:L,...)`).
- **Frontend**: `F/pantallas/variance/` (`PanelVariance`, `TablaVariance`, `PanelLinea`, `Desglose`,
  `Movimientos`, `AsientoVista`, `HistorialCifra`, `ComentariosLinea`, `CierrePeriodo`, `agrupar.ts`),
  `F/util/resumenVariance.ts`, `F/api/cliente.ts`.

## 5. Presupuesto/Budget: cómo funciona hoy

- **Modelos**: `B/modelos/plan.py` — `VersionPlan` (tipo, número, `ano_fiscal` "2026/27", `periodo_corte`,
  `version_estructura_id`, `sha256`, estado; una sola `vigente` por hotel/tipo/año), `LineaPlan(mes, ytd, anual)`,
  `LineaPlanMensual(periodo, importe)`, `ValorCapturado`. `B/modelos/presupuesto.py` — `AnoFiscal`,
  `PeriodoFiscal`, `CicloPresupuesto`, `CicloTransicion` (solo inserta), `PerfilDistribucion` (12 pesos que
  suman 1), `LineaPresupuestoCaptura` (objetivo, propuesta_anual, estado, nota, perfil), `LineaPresupuestoMensual`.
- **Importador** (`POST /budget/importar`, `B/api/v1/budget.py`, permiso `budget:importar`, solo `.xlsx`):
  1. `budget_mzt`: hoja `Budget 26-27 MZT` (`B/ingesta/budget_anual_mzt.py`): encabezado JUL…JUN en columnas D–O,
     cuenta corporativa en B, descripción en C, TOTAL en P; `alinear_con_lineas` pone cada fila en la línea del
     reporte con el **mismo número de fila** si el nombre se parece (umbral 0.6); tipo de cambio por nombre.
  2. `mzt`: Variance de Mazatlán (`Jul-Ago`); Budget del mes en columnas F (julio) y K (agosto).
  3. `vt`: hoja `Ago` con tres bloques (Budget en E mes, J YTD, O anual); `periodo_corte` obligatorio.
  Requiere una estructura de reporte vigente (409 si falta). Filas con Budget que no existen en la estructura
  se ignoran con aviso; si pasan del 5 %, se rechaza.
- **Versionado (ADR 0003)**: mismo hash → `DUPLICADA` (no cambia nada); otro archivo del mismo año pide
  `confirmar_reemplazo`; todo en `begin_nested()` con auditoría (`budget.creado/reemplazado/rechazado`).
  `B/servicios/budget_edicion.py` (`crear_version_desde_cambios`) copia la base, aplica cambios y crea versión
  nueva (409 `BaseDesactualizada` si la base ya no es la vigente). Solo se editan líneas de detalle sin regla.
- **Ciclo** (`B/servicios/presupuesto_ciclo.py`, `presupuesto_captura.py`, `presupuesto_distribucion.py`;
  `B/api/v1/presupuesto.py`): `borrador → enviado → revision → aprobado → bloqueado`; devolver y reabrir piden nota.
  Al aprobar se genera una `VersionPlan` normal vía `importar_budget_mensual` (exige todas las líneas
  mensualizadas). Variance no cambia: solo lee `VersionPlan`. Captura por departamento vía `AsignacionDepartamento`.
- **Frontend** (`F/pantallas/budget/`): `PanelBudget.tsx` (Resumen / Captura / Versiones, navegación en el
  sidebar), `CicloPresupuesto.tsx`, `calculo.ts`, `componentes/` (`DetalleCapturaLinea`, `BudgetResumen`,
  `BudgetVersionesTab`, `BudgetComparacionVersiones`, `BudgetVariacionSeccionChart`, etc.).

## 6. El hueco que se va a llenar

- **No existe Budget por cuenta.** `linea_plan` y `linea_plan_mensual` están a nivel de **línea del reporte**,
  no de cuenta. Las hojas por cuenta del Excel de Variance (p. ej. `'4002011'`, con columnas B mes, G "Total",
  L importe) hoy solo se leen **por nombre desde las fórmulas**, no por contenido.
- **Tablas existentes que podrían enlazarse**: `cuenta_local` (por hotel, `codigo`, `padre_codigo`, `nivel`,
  `tipo`, `grupo_ef`, `depto_ef`), `mapeo_linea_cuenta` (qué cuentas pertenecen a cada línea), `movimiento`,
  `saldo_mensual_cuenta`, `carga_archivo`, `version_plan`, `linea_reporte`.
- **Puntos de enganche (inferencia, NO diseño aprobado)**: un registro hijo de
  `(version_plan_id, linea_id, cuenta_codigo[, periodo])`, creado junto con la `VersionPlan` y nunca editado;
  hacer que `importar_budget_mensual` lo reciba; que cuadre con `LineaPlanMensual` de la misma línea; reutilizar
  `mapeo_linea_cuenta` para validar que la cuenta pertenece a la línea; que el ciclo, al aprobar
  (`_generar_version_plan`), lo propague. Alternativa: colgarlo de `LineaPresupuestoCaptura`.
- Habrá que decidir si el Variance usa este detalle (drill-down por cuenta del Budget) y cómo se compara con el
  Actual por cuenta, que ya existe vía movimientos.

## 7. Frontend de Budget Studio: estado tras esta sesión

- Captura rediseñada según una imagen de referencia (1536×1024) y verificada con capturas reales: sidebar de
  198 px (Financiero, Budget Studio con Resumen/Captura/Versiones, "Administración"), cabecera con estado y
  cobertura, ciclo en una fila, filtros en una fila, tabla con **una cifra por celda y solo la celda activa
  como input** (el Actual va en el tooltip y en la gráfica del panel), panel "Detalle de línea" siempre visible,
  barra de cambios que solo aparece con cambios, scroll de página completo.
- Se eliminaron `ArbolLineas`, `BudgetComposicionChart` y `BudgetObjetivoVsPropuestaChart` (fusionados en
  `BudgetVariacionSeccionChart`). `BudgetTabs.ts` ahora solo exporta los tipos y `PESTANAS_BUDGET`.
- El estado de la pestaña (Resumen/Captura/Versiones) vive en `App.tsx`, no en rutas.
- Desviaciones y motivos: `docs/captura-diff.md`. Capturas: `docs/imagenes/rediseno/`.
- Pruebas: 86/86 unitarias, lint y build limpios; e2e 94 de 95 (la que falla, `seguridad.spec.ts:107`, es
  intermitente: pasa 3 de 3 sola). Se actualizaron `rediseno`, `variance_budget`, `cargas` y `variance` specs.
- **Hay muchos cambios sin commitear en `frontend/`**; no se hizo commit ni push.

## 8. Trampas conocidas

- `PUT .../ciclos/{id}/lineas/{linea}` **no es parcial**: sin `propuesta_anual` borra la existente y deja la
  línea en "pendiente". Siempre reenviar el anual vigente junto con la nota.
- El Excel pierde ceros finales en códigos de cuenta (`4002001.010` → `4002001.01`); `normalizar_codigo`
  (`B/ingesta/variance_mzt.py`) lo maneja.
- Una misma cuenta puede estar en varias líneas.
- `Medida` guarda 6 decimales (Budget); `Dinero` 2 (movimientos).
- `display:flex` directo sobre un `<td>` saca la celda del layout de tabla (las columnas se apilan).
- `.tabla-variance` ya tiene cabecera pegajosa, columna de línea fija y scroll contenido; reutilizarla.
- El total de una sección se suma solo sobre líneas `detalle` (los subtotales ya agregan esas líneas).
- El endpoint de historial por línea de Budget no existe (solo auditoría del ciclo completo).
- No hay Excel reales en el repo; las pruebas con datos reales se saltan si faltan. Fixtures sintéticos:
  `backend/scripts/crear_archivos_e2e.py`, `backend/tests/mzt_sintetico.py`.
- Seguridad de archivos (`B/seguridad/archivos.py`): rechaza `.xlsm/.xlsb/.xls` en Budget y Variance, límites
  anti zip-bomb, escaneo ClamAV (si `clamd` no responde, se rechaza).

## 9. Preguntas abiertas (a resolver con el usuario / Contraloría antes de programar)

1. ¿Cómo es el Excel nuevo? ¿Una hoja por cuenta, o una hoja con todas? ¿Qué columnas y filas tiene cada tabla
   interna? ¿Hay filas de subtotal dentro de cada cuenta?
2. ¿El detalle es Budget, Actual o ambos? ¿Mensual o anual? ¿Por producto, concepto, departamento…?
3. ¿Debe cuadrar con el total de la línea del reporte? ¿Qué pasa si no cuadra (rechazar, avisar)?
4. ¿Se importa solamente, o también se captura/edita en pantalla (ciclo de presupuesto)?
5. ¿Cómo se verá en Variance (drill-down por cuenta del Budget) y en Captura?
6. ¿Aplica a todo el hotel o solo a ciertas cuentas/secciones? ¿Sirve igual para Vallarta (formato `vt`)?
7. Pendiente con Contraloría desde antes: confirmación del mapeo de cuentas, año fiscal y roles `[POR VALIDAR]`.

## 10. Cómo arrancar el chat nuevo

Texto sugerido para pegar:

> Lee `docs/CONTEXTO_PARA_IA_VARIANCE_Y_PRESUPUESTO.md`. Vamos a extender Variance y Presupuesto para ingerir el
> Excel del contralor con las tablas internas de cada cuenta. No abras fases nuevas. Antes de programar:
> inspecciona la estructura del Excel de muestra que te daré (sin subirlo al repo), propón el modelo de datos y
> el plan, y espera mi aprobación. Respeta las reglas de la sección 2.

Orden de lectura sugerido: `CLAUDE.md` del repo, `docs/adr/0003` y `0004`, `docs/FORMULAS_Y_REGLAS_DEL_VARIANCE.md`,
`B/servicios/variance.py`, `B/servicios/budget.py`, `B/ingesta/budget_anual_mzt.py`, `B/modelos/plan.py`,
`B/servicios/presupuesto_ciclo.py`, `F/pantallas/budget/PanelBudget.tsx`.
Primer paso: pedir el Excel de muestra, mapear sus hojas/columnas, y comparar con lo que ya hace
`importar_budget_mensual` antes de crear tablas nuevas (migración Alembic `0023_...`).

Otros documentos útiles: `docs/ESTADO_DEL_PROYECTO.md` (desactualizado: dice fases 6–14 pendientes),
`docs/TRASPASO_OCTUBRE_2026_v3.md`, `docs/DISENO_FASE7_BUDGET.md`, `docs/PREGUNTAS_PARA_CONTRALORIA.md`,
`docs/Especificacion_Redisenio_Budget_Studio.md`.
