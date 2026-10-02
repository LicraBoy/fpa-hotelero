# Hallazgos de la sesión con Contraloría — Variance de Mazatlán, agosto 2026

Sesión: _fecha_ · Participantes: _nombres y roles_ · Versión: _commit_ · Datos: Mazatlán, julio y agosto 2026

Estado de las sub-fases 4.8 y 4.9: **preparadas con el Excel de Mazatlán; la sesión y el cierre de esta lista están pendientes.**
La sub-fase se cierra cuando **todos** los hallazgos de severidad Alta y Media estén en `Cerrado` o
`Aceptado` (con una nota de por qué).

**Severidad:** **Alta** = una cifra es incorrecta o puede llevar a una mala decisión · **Media** =
estorba, confunde o falta algo importante · **Baja** = mejora de forma.
**Estado:** `Abierto` → `En trabajo` → `Corregido (por verificar)` → `Cerrado`; o `Aceptado` (se queda
así, con motivo) / `No es un defecto` (el sistema está bien; se explicó).

## Preguntas ya conocidas que Contraloría debe responder
Vienen de las pruebas con el Excel de **Mazatlán** (julio y agosto 2026) y están explicadas en
`docs/GUIA_PRUEBA_CONTRALORIA.md`. *Las preguntas P1 y P2 de la versión anterior (`4002013` y
`4003003`) eran del archivo de Puerto Vallarta y se retiraron.*

| ID | Pregunta | Respuesta de Contraloría | Estado |
|---|---|---|---|
| P1 | `4003001.010` (−4.1 M en agosto), `4003001.020` y `4002020` tienen movimientos y ninguna línea las suma: ¿se excluyen a propósito o es una omisión? | | Abierto |
| P2 | IVA Taxes, Income Tax, Bank Commissions y Audit Fees suman cuentas de pasivo, activo y ajenas (`2007001`, `1005003`, `6-1-01-100-050`…) que la Base de Datos no trae: ¿de qué reporte salen cada mes? | | Abierto |
| P3 | Miscellaneous Taxable (fila 19) resta celdas fijas de otras hojas y difiere en 5,000.00 de los movimientos: ¿es intencional? | | Abierto |
| P4 | 6 líneas listan en `Ago!I:O` cuentas que su fórmula no suma y 15 suman cuentas que no listan: ¿cuál es la fuente correcta? | | Abierto |
| P5 | Tipo de cambio: ¿de dónde sale el Actual (17.1337 / 17.2175)? ¿Variación = Presupuesto − Actual y % = Variación / Presupuesto es correcto? | | Abierto |
| P6 | Año fiscal: el título dice FY 25/26; el sistema usa julio–junio (agosto 2026 = 2026/27). ¿Cuál es el correcto? | | Abierto |
| P7 | Líneas sin cuentas (Less Discount, VDS Allocation, resumen por departamento): ¿la Variación es Actual − Presupuesto? ¿Qué regla de signo aplica? | | Abierto |
| P8 | Non-Deductible, Adm Fee 6 % y las líneas del resumen son valores a mano o sin fórmula: ¿de dónde salen? | | Abierto |
| P9 | ¿Pueden dar el presupuesto anual y el Variance/Budget de septiembre? El Excel de Mazatlán solo trae el mes | | Abierto |
| P10 | ¿Quién debe poder ver los movimientos (el desglose)? Hoy: Contralor, Analista y Auditoría; Dirección no | | Abierto |

## Hallazgos de la sesión

| ID | Pantalla / línea | Qué esperaban | Qué vieron | Severidad | Estado | Responsable | Notas / captura |
|---|---|---|---|---|---|---|---|
| H1 | | | | | Abierto | | |
| H2 | | | | | Abierto | | |
| H3 | | | | | Abierto | | |

## Cierre
- [ ] Todos los hallazgos Alta y Media están `Cerrado` o `Aceptado`.
- [ ] Contraloría confirmó por escrito las respuestas P1 a P10 (o acordó una fecha).
- [ ] `docs/ESTADO_DEL_PROYECTO.md` actualizado y la Fase 4 marcada como cerrada.

Firma de Contraloría: ______________________ Fecha: ____________
