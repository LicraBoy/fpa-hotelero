# Diseño de la Fase 7 — Budget en la plataforma

Preparación/diseño (22-oct-2026), antes de programar. No se escribe código todavía — esto se
revisa primero. Fase 6 formalmente no está cerrada (6.2 pentest y 6.7 aceptación de Contraloría
pendientes); se diseña en paralelo sin bloquear, como se decidió.

## 1. Idea central: no tocar cómo se consume el Budget, solo cómo se produce

Hoy `VersionPlan`/`LineaPlan` (`fpa/modelos/plan.py`) representan una foto del Budget **ya
armada**, importada de un Excel. Variance las consume sin saber si vinieron de un Excel o de una
captura. **La Fase 7 no cambia esto**: agrega una capa de captura/flujo que, al aprobarse, produce
una `VersionPlan` normal — exactamente la misma estructura que hoy llega por Excel. Variance,
`fpa/servicios/variance.py` y todo lo que ya lee `VersionPlan` **no se tocan**.

Esto reduce el riesgo: lo nuevo es "cómo se llena la tabla", no "qué hace el sistema con la tabla".

## 2. Qué se reutiliza (no se inventa de nuevo)

| Necesidad | Ya existe en |
|---|---|
| Versionado inmutable con borrador editable → aprobado | Patrón de `fpa/servicios/versionado_mapeo.py` (`crear_borrador_desde`, `aprobar`, `AprobacionBloqueada`) — mismo patrón, nueva entidad |
| Permisos por departamento | `AsignacionDepartamento` (`fpa/modelos/identidad.py`) — usuario+hotel+sección, **ya existe**, hoy solo lo usa Comentarios (5.2/5.3) |
| Rol "responsable de departamento" | `RolCodigo.RESPONSABLE_AREA` (`fpa/identidad/permisos.py`) |
| Convención de permisos | `Permiso` como `StrEnum` `recurso:accion` (`budget:leer`, `budget:importar` ya existen) |
| Estado con transiciones auditadas y "reabrir" | `CierrePeriodo`/`CierreTransicion` (`fpa/modelos/cierre.py`, `fpa/servicios/cierre.py`) — mismo patrón, nueva entidad (no la misma tabla: el ciclo de Budget y el cierre de Variance son objetos distintos) |
| Bitácora de cambios | `fpa/servicios/auditoria.py` (`auditar(...)`), usado en todos los servicios de versionado |
| Dinero exacto | `Medida`/`Dinero` (`fpa/modelos/tipos.py`) |

## 3. Modelo de datos nuevo

### 3.1 `AnoFiscal` / `PeriodoFiscal` (calendario fiscal — requisito transversal 4)

Falta un concepto formal de año fiscal y periodo, reusable por Budget (7) y Forecast (8):

```
AnoFiscal: id, hotel_id, etiqueta ("2026/27"), mes_inicio (ej. 7=julio), mes_fin, estado
PeriodoFiscal: id, ano_fiscal_id, periodo (AAAA-MM), estado (abierto|revisado|cerrado),
               fecha_limite, cerrado_en, cerrado_por_id
```

Regla: un `PeriodoFiscal` pasa a `cerrado` cuando su `CierrePeriodo` de Variance llega a
`aprobado`/`bloqueado` (enlace lógico, no FK dura, para no acoplar los dos módulos). La reapertura
de un periodo `cerrado` exige el mismo tipo de transición auditada que `CierrePeriodo` ya usa.

### 3.2 `CicloPresupuesto` (el "borrador editable" del Budget)

```
CicloPresupuesto: id, hotel_id, ano_fiscal_id, numero (consecutivo), estado
                  (borrador|enviado|revision|aprobado|bloqueado), version_estructura_id,
                  creado_por_id, creado_en, aprobado_en, version_plan_resultante_id (nullable;
                  se llena SOLO al aprobar, apuntando a la VersionPlan que se crea)
CicloTransicion: id, ciclo_id, desde, hacia, usuario_id, nota, creado_en  (solo inserta, igual
                 que CierreTransicion)
```

### 3.3 `LineaPresupuestoCaptura` (una fila por línea de detalle del reporte)

```
LineaPresupuestoCaptura: id, ciclo_id, linea_id, responsable_id (quién la captura — deriva de
                          AsignacionDepartamento), objetivo (Medida, nullable — lo fija Dirección),
                          propuesta_anual (Medida, nullable — lo captura el responsable),
                          perfil_distribucion_id (nullable), estado (pendiente|capturada|
                          revisada), nota
LineaPresupuestoMensual: id, linea_captura_id, periodo (AAAA-MM), importe (Medida)
                         -- 12 filas por LineaPresupuestoCaptura cuando se expande el perfil;
                         -- UniqueConstraint(linea_captura_id, periodo)
```

**Reconciliación del spreading** (criterio de aceptación 1 de la Fase 7): al expandir un perfil, la
suma de los 12 `LineaPresupuestoMensual.importe` debe ser exactamente `propuesta_anual` — el
redondeo sobrante/faltante se ajusta en el **último** mes con importe (regla simple, documentada),
nunca se deja una diferencia silenciosa.

### 3.4 `PerfilDistribucion` (catálogo reusable de perfiles estacionales)

```
PerfilDistribucion: id, hotel_id (nullable = disponible para todos los hoteles), nombre,
                    pesos (JSON: 12 decimales que suman 1.000000), es_sistema (los "de fábrica":
                    uniforme, y los que se definan con Contraloría)
```

## 4. Flujo y estados del `CicloPresupuesto`

Mismo espíritu que `CierrePeriodo`, con una transición más (Enviado/Revisión) porque aquí sí hay
captura distribuida por muchos responsables, no solo lectura:

```
Borrador --(enviar, responsable)--> Enviado
Enviado --(devolver, revisor)--> Borrador      [nota obligatoria]
Enviado --(marcar revisado, revisor)--> Revisión
Revisión --(devolver, revisor)--> Borrador      [nota obligatoria]
Revisión --(aprobar, Contralor/Dirección)--> Aprobado   [[aquí se crea la VersionPlan]]
Aprobado --(bloquear)--> Bloqueado
Aprobado --(reabrir, Contralor)--> Borrador     [nota obligatoria; SOLO desde Aprobado, igual
                                                  límite que ya tiene CierrePeriodo desde Bloqueado]
```

Al llegar a **Aprobado**: se recorren todas las `LineaPresupuestoCaptura` con `propuesta_anual` no
nula, se crea una `VersionPlan` nueva (como si fuera un Excel importado) con sus `LineaPlan`
(anual) y `LineaPlanMensual` (los 12 meses expandidos) — reusa exactamente los modelos de
`fpa/modelos/plan.py`, cero cambios ahí. Las líneas sin `propuesta_anual` (cobertura incompleta) se
reportan como advertencia, no bloquean la aprobación salvo que Contraloría decida lo contrario
(`[POR VALIDAR con Contraloría]`).

## 5. Permisos nuevos (mismo patrón que `Permiso`/`CIERRE_*`)

```
BUDGET_CAPTURAR   -- responsable_area: solo sus líneas asignadas (AsignacionDepartamento)
BUDGET_OBJETIVO   -- fijar el objetivo de Dirección (rol direccion)
BUDGET_REVISAR    -- marcar enviado/revisión, devolver
BUDGET_APROBAR    -- aprobar (crea la VersionPlan), reabrir
BUDGET_BLOQUEAR   -- bloquear la versión aprobada
```

`AsignacionDepartamento` ya resuelve "qué secciones ve/edita cada responsable" — se reusa sin
cambios; solo se agrega la verificación en los endpoints nuevos de captura.

## 6. Objetivo contra propuesta (7.5) y cobertura presupuestaria

- **Objetivo**: lo fija Dirección por línea (o por sección, si se decide que no sea por línea —
  `[POR VALIDAR]`), antes o durante el ciclo. Es una referencia, no se "aprueba" por separado.
- **Propuesta**: lo captura el responsable de departamento.
- La pantalla de revisión muestra objetivo, propuesta y la diferencia, línea por línea.
- **Cobertura presupuestaria**: % de `LineaPresupuestoCaptura` con `propuesta_anual` no nula sobre
  el total de líneas de detalle de esa sección — visible para el revisor antes de aprobar.

## 7. Orden sugerido para programar (sub-fases ya en `FASES_FUTURAS.md`)

1. **7.1** — Modelos nuevos (§3) + migraciones + `CicloTransicion`/estados (sin UI todavía),
   reusando el patrón de `fpa/servicios/versionado_mapeo.py` para un servicio
   `fpa/servicios/presupuesto_ciclo.py`.
2. **7.3** — Perfiles de distribución + reconciliación del spreading (es la pieza con la regla
   matemática más delicada — conviene tenerla probada con casos de redondeo antes de construir la
   captura por pantalla).
3. **7.2** — Captura por área (API + permisos `BUDGET_CAPTURAR`, reusando `AsignacionDepartamento`).
4. **7.5** — Objetivo contra propuesta (API + pantalla de comparación).
5. **7.4** — Aprobación y bloqueo (al aprobar, generar la `VersionPlan` — aquí se cierra el
   círculo con el Budget que Variance ya sabe leer).
6. Calendario fiscal (§3.1) puede ir en paralelo desde el principio, lo necesitan 7 y 8 por igual.

## 8. Preguntas para Contraloría antes de programar

- Año fiscal: confirmar julio-junio (ya preguntado para Forecast, Fase 8 — misma respuesta aplica
  aquí).
- El objetivo de Dirección, ¿es por línea de detalle o por sección/departamento agregado?
- Si una línea de detalle no tiene responsable asignado hoy en `AsignacionDepartamento`, ¿quién la
  captura? (¿Contraloría por default?)
- ¿La aprobación final la da el Contralor, Dirección, o ambos en secuencia?

## 9. Verificación (criterios de aceptación ya en `FASES_FUTURAS.md`, Fase 7)

No se repiten aquí — son los 7 que ya quedaron documentados la semana pasada (suma mensual = anual,
versión aprobada inmutable, etc.). Este diseño debe poder probarlos todos sin ajustes adicionales.
