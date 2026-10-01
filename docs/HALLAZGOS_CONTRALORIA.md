# Hallazgos de la sesión con Contraloría — Variance de agosto 2026

Sesión: _fecha_ · Participantes: _nombres y roles_ · Versión: _commit_ · Datos: agosto 2026

Estado de la sub-fase 4.8: **preparada; la sesión y el cierre de esta lista están pendientes.**
La sub-fase se cierra cuando **todos** los hallazgos de severidad Alta y Media estén en `Cerrado` o
`Aceptado` (con una nota de por qué).

**Severidad:** **Alta** = una cifra es incorrecta o puede llevar a una mala decisión · **Media** =
estorba, confunde o falta algo importante · **Baja** = mejora de forma.
**Estado:** `Abierto` → `En trabajo` → `Corregido (por verificar)` → `Cerrado`; o `Aceptado` (se queda
así, con motivo) / `No es un defecto` (el sistema está bien; se explicó).

## Preguntas ya conocidas que Contraloría debe responder
Vienen de las pruebas con agosto y están explicadas en `docs/GUIA_PRUEBA_CONTRALORIA.md`.

| ID | Pregunta | Respuesta de Contraloría | Estado |
|---|---|---|---|
| P1 | `4002013` (−20,000/mes) y `4003003` (≈ −3.2 M/mes) tienen movimientos y ninguna línea las toma: ¿se excluyen a propósito o es una omisión? | | Abierto |
| P2 | Fila 12 Other Income: el Excel deja fuera 5,000.00 de la hoja de la cuenta: ¿es intencional? | | Abierto |
| P3 | IVA Taxes, Lodging Tax, Bank Commissions, Audit Fees e Income Taxes (filas 272, 277, 285, 289, 292) usan cuentas de balance o corporativas que el archivo de movimientos no trae: ¿de qué reporte salen cada mes? | | Abierto |
| P4 | Telephone Profit (fila 344) se calcula como gasto aunque es utilidad: ¿es intencional? | | Abierto |
| P5 | El % de Net Profit Commercial Services (530) usa el valor absoluto del presupuesto y el resto no: ¿cuál es la regla? | | Abierto |
| P6 | Administration Fee (273) y las dos "Allocated" (576, 577) son valores pegados: ¿de dónde salen? | | Abierto |
| P7 | ¿El año fiscal es julio–junio? ¿La convención "favorable = positivo" es la correcta para todas las líneas? | | Abierto |
| P8 | ¿Cuál es la clave única de una línea del reporte y de dónde sale el Budget? | | Abierto |
| P9 | ¿Quién debe poder ver los movimientos (el desglose)? Hoy: Contralor, Analista y Auditoría; Dirección no | | Abierto |
| P10 | Septiembre: ¿pueden dar el Variance y el Budget de septiembre y aclarar las 154 cuentas nuevas? | | Abierto |

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
