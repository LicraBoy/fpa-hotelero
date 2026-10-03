# Fórmulas y reglas del Variance (sub-fase 4.12)

Registro de **cómo se calcula cada cifra** y de dónde sale cada regla, para tenerlo en cuenta en
cambios futuros. Fuente: decisiones de Contraloría (sesión de septiembre 2026) y los Excel de referencia
`02. MZT August 2026 Variance.xlsx`, `02. MZT August 2026 Variance (Envio).xlsx` y `Budget MZT 26-27.xlsx`.

## 1. Año fiscal
Julio a junio (`2026/27` = jul-2026 a jun-2027). El acumulado (YTD) suma desde julio.

## 2. Variación (columnas G = Mes, L = Acumulado, Q = Anual del Excel)
- El **sentido se lee línea por línea y por bloque** de la fórmula del Excel:
  - `F−E` → **Presupuesto − Actual** (gastos; ~580 líneas de detalle).
  - `E−F` o `−F+E` → **Actual − Presupuesto** (ingresos, ~35 de detalle, 10 informativas, subtotales).
- Se guarda en la tabla `convencion_linea` (migración 0013) vía `POST /hoteles/{id}/reporte/convenciones`
  (permiso `mapeo:editar`, auditado). Código: `ingesta/variance_convenciones.py`, `servicios/convenciones_linea.py`.
- **Variación compuesta:** 5 totales de utilidad = suma de las Variaciones de sus partes (no Actual−Presupuesto).
- Sin convención guardada, el motor deduce el sentido por la sección (gasto: Presupuesto−Actual).
- La importación de convenciones es **independiente** del cálculo: el sistema calcula con sus cifras, solo toma el sentido.

## 3. Porcentaje (columna H)
Una sola fórmula para todas las filas:

    SI(Var = 0, 0,
       SI(Actual = 0, Var / Presupuesto,
          SI(Presupuesto = 0, Var / Actual,
             Var / Presupuesto)))

Código: `calculo/variance.py::variance_pct`.

## 4. Actual
- Sale de los **movimientos del CON130** sumados por cuenta, con el signo de la fórmula de `Jul-Ago`.
- **Líneas mixtas** (cuentas + otras líneas, con coeficiente): p. ej. *IVA Taxes 16 %* =
  `'2007001' + '2-1-70-20' − J756 − J807 − J363`; detalle `J754*0.16` (coeficiente 0.16).
  Los coeficientes ±1 se guardan como entero; otros como `Medida` (6 decimales).
  Código: `calculo/totales.py`, `ingesta/variance_mzt.py::referencias_a_lineas`.
- Totales y subtotales = suma de sus componentes (reglas de suma).
- **Captura manual** para líneas sin cuentas (p. ej. Exchange Rate, asignaciones corporativas):
  tabla `valor_capturado`, origen `excel` | `manual`, auditado (`PUT /budget/capturados`).
- **Excepciones documentadas** (julio/agosto): 16 Actuales cuyas fuentes corporativas no están en la
  Base de Datos (filas 19, 70, 304, 308, 317, 318, 313, 314, 32, 76, 78, 319) y el IVA de julio
  (756, 757, 807, 808), cuya fórmula difiere de la de agosto. Ver `tests/test_variance_dorada_mzt.py`.

## 5. Budget
- **Mes y año completo** salen de `Budget MZT 26-27.xlsx` (hoja `Budget 26-27 MZT`, columnas D–O = JUL…JUN,
  P = total; fila 8 = tipo de cambio, 18 cada mes). Código: `ingesta/budget_anual_mzt.py`, formato `budget_mzt`.
- Se alinea con el reporte por **número de fila + parecido de nombre** (≥ 0.6); avisa las ortografías
  distintas («Holydays»/«Holidays») y las filas sin línea.
- En el Excel **una celda en blanco de una línea de detalle vale 0**: se rellena con 0 para que la Variación no salga «—».
- Edición en pantalla = **versión nueva** inmutable (la anterior queda en el historial).

## 6. Tipo de cambio (Exchange Rate)
- Actual del mes: captura manual (jul 17.2175, ago 17.1337; septiembre se captura a mano).
- Presupuesto: 18.
- **Mes:** Variación = Presupuesto − Actual.
- **Acumulado:** Actual = **promedio de los meses capturados**; Presupuesto = 18; Variación = **Actual − Presupuesto** (al revés del mes).
- **Anual:** Actual = ese promedio; Presupuesto = 18; Variación = Presupuesto − Actual.

## 7. Cuentas omitidas a propósito
`4002020`, `4003001.010`, `4003001.020`, `6009020`, `6009001.004`, `6006012.001`:
«todavía no se ocupan» (Contraloría). Se excluyen del mapeo con ese motivo (`python -m fpa.mapeo_omitir`,
solo desarrollo, auditado). Si un día se ocupan: nueva versión del mapeo que las vincule a una línea.

## 8. Límites conocidos
- Acumulado de septiembre corto en líneas con cuentas de balance (IVA, Income Tax) hasta tener el CON130 de julio y agosto (P19).
- ~150 líneas sin cuentas requieren captura manual (P21).
- Fórmula del IVA de julio ≠ agosto (P20).

## 9. Dónde se prueba
`tests/test_variance_dorada_mzt.py`, `test_variance_convenciones.py`, `test_budget_anual_mzt.py`,
`test_valores_capturados.py`, `test_totales.py`, `test_omitir_cuentas.py`.

## 10. Cómo cambiar una fórmula o regla en el futuro
Nada de esto está fijo en el código: casi todo se vuelve a leer del Excel de Contraloría y se guarda en versiones.

| Qué cambia | Qué se hace | Dónde queda |
|---|---|---|
| Sentido de la Variación de una línea (Presupuesto−Actual o al revés) | Subir el Excel de Variance actualizado a `POST /hoteles/{id}/reporte/convenciones` | Tabla `convencion_linea` (se reemplaza; auditado) |
| Qué cuentas o líneas suma una línea, o un coeficiente (p. ej. 16 %) | Importar de nuevo el Excel con las fórmulas (`reporte/importar`): se leen las referencias de `Jul-Ago` | Nueva versión de la estructura y de las reglas de suma |
| Vincular una cuenta a otra línea, o dejar de omitir una de las 6 | Nueva versión del mapeo y su aprobación; el motivo de omisión se cambia con `fpa.mapeo_omitir` | Mapeo versionado (la anterior se conserva) |
| Fórmula del % | Editar `calculo/variance.py::variance_pct` y actualizar `test_variance.py` (único lugar con código) | Código + pruebas |
| Budget de un año fiscal nuevo | Pestaña Budget → importar el Excel (el título `FY 27/28` define los 12 meses) | Versión nueva de Budget |
| Una cifra de Actual sin cuentas | Capturarla en la pestaña Budget (o importar el Excel del Envio) | `valor_capturado`, auditado |
| Tipo de cambio de un mes | Pestaña Budget, fila Exchange Rate | `valor_capturado` |

Reglas al cambiar algo:
1. Correr `pytest`: `test_variance_dorada_mzt.py` compara con julio y agosto del Excel y avisa si algo se movió.
2. Si el cambio es intencional, actualizar la lista de excepciones de esa prueba y este documento.
3. Registrar la decisión de Contraloría (quién, cuándo) en `docs/adr/` o en `PREGUNTAS_PARA_CONTRALORIA.md`.
