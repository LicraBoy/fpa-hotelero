# Guía de prueba con Contraloría — Variance de agosto 2026

Para revisar la pantalla de Variance con las cifras reales de agosto y decirnos qué está bien, qué
está mal y qué falta. Dura unos 60 minutos. **No hace falta saber de sistemas.**

Lo que ustedes validan es: *¿las cifras y la forma de leerlas son las que Contraloría usa hoy en el
Excel?* Todo lo que no coincida se anota en `docs/HALLAZGOS_CONTRALORIA.md`.

## Antes de empezar (lo hace TI o quien prepara la sesión)
1. Abrir `iniciar_servidores.bat` (carpeta del proyecto) y esperar a que se abra el navegador.
2. Cargar agosto en la base de desarrollo (una sola vez; repetirlo no cambia nada):
   `cd backend` → `set FPA_ENTORNO=desarrollo` →
   `.venv\Scripts\python -m fpa.demo_agosto --datos "C:\...\PLATAFORMA FP&A E INTELIGENCIA HOTELERA"`
3. Entrar a `http://localhost:5180`, elegir **Contralor** en "Usuario (desarrollo)" y abrir la
   pestaña **Variance**. Debe verse el mes **2026-08**.

> Modo desarrollo: el usuario se elige a mano. En producción se entrará con el inicio de sesión
> corporativo.

## De dónde salen las cifras (lo que hoy hace el Prompt de integración)
Hoy el reporte se arma a mano siguiendo `docs/adr/Prompt_Integracion_Variance.docx`. La plataforma
reproduce ese proceso, así que conviene tenerlo presente al comparar:

1. **Materia prima:** la hoja *Base de Datos* (movimientos de cuentas de resultados: mes, fecha,
   cuenta, asiento, concepto, débito, crédito).
2. **Una hoja por cuenta**, con su total por mes (Débito − Crédito) y el acumulado de julio y agosto.
3. **La hoja `Ago` se liga a esos totales con fórmulas:** la columna **S** trae el total del mes y la
   **T** el acumulado. Los números de cuenta de cada línea están en las columnas **X a AC**.
4. **Las cuentas que empiezan con 4 van con signo negativo** (ingresos). La plataforma lo llama signo
   −1; las demás, +1.
5. **El Budget está pegado a mano** en `Ago` (columnas E, J y O): por eso solo hay Budget de agosto.

Qué explica esto de lo que van a ver:
- **Una cuenta con movimientos que no está en X a AC no entra a ninguna línea.** Es el caso de
  `4002013` y `4003003` (el propio prompt lo dice: sin vínculo, no participa). Parece un olvido del
  armado, pero lo confirma Contraloría.
- **IVA, Lodging Tax, Bank Commissions, Audit Fees e Income Taxes** salen de cuentas de balance o
  corporativas que *Base de Datos* no trae; hoy Contraloría las toma de otras hojas.
- **El proceso se repite cada mes con una base nueva** (el prompt habla de septiembre). Por eso el
  mapeo de agosto no sirve tal cual para septiembre: hay 154 cuentas nuevas.
- **La plataforma lee las fórmulas de S y T para sacar el mapeo.** Si una fórmula del Excel cambia,
  cambia el mapeo.

## Cómo leer la pantalla
- **Tres bloques:** *Mes*, *Acumulado del año fiscal* (julio a agosto) y *Presupuesto anual*. Cada uno
  con **Actual, Presupuesto, Variación y % var.**
- **Variación favorable = positiva.** Ingresos y utilidades: real − presupuesto. Gastos:
  presupuesto − real. Una variación **desfavorable** lleva **▼** y los negativos van **entre
  paréntesis**.
- **—** significa "no hay dato" (por ejemplo, no hay presupuesto). Nunca es un cero.
- Las cifras del **Actual** son enlaces: abren el desglose (cuentas → movimientos → asiento).
- **Año fiscal julio–junio** y la convención de signo son lo que entendimos del Excel; si no son así,
  anótenlo.

## Las 10 tareas

| # | Qué hacer | Qué debe verse |
|---|---|---|
| 1 | Abrir **Variance**, mes 2026-08 | La tabla del reporte con sus secciones, en el mismo orden que la hoja `Ago`. Aviso amarillo: el mapeo deja fuera a propósito 2 cuentas (`4002013`, `4003003`) |
| 2 | Buscar **Salaries** en la sección Mgmt & Check In | Actual mes **321,190.84**, presupuesto 332,935.91, variación 11,745.07 (3.5 %). Igual que el Excel |
| 3 | Comparar los totales **Total Mgmt & Check In** y **Total Maid & Linen** | **483,198.48** y **442,235.81** en el mes. Igual que el Excel |
| 4 | Plegar y desplegar una sección con el título azul | Al plegar quedan visibles sus totales y subtotales |
| 5 | Filtrar por **Sección**, escribir `insurance` en **Buscar línea** y marcar **Solo totales y subtotales** | La tabla se acota a lo que pidieron |
| 6 | Hacer clic en el **Actual de Salaries (mes)** | Desglose: la cuenta `6009001.001` con signo **+** y 321,190.84, y la marca **Cuadra** |
| 7 | Hacer clic en la cuenta, luego en **Cargar más** hasta el final | Los movimientos suman el neto de la cuenta; al terminar dice **Cuadra con el neto de la cuenta** |
| 8 | Hacer clic en el número de un **asiento** | Todas sus líneas del mes. Puede decir "Solo cuentas de resultados": es normal, el reporte solo trae esas |
| 9 | Hacer clic en un **total** (p. ej. Total Other Income) y bajar por sus componentes | Cada nivel suma al anterior |
| 10 | **Exportar a Excel** | Un `.xlsx` con el mismo formato que la hoja `Ago`; las cifras son las de la pantalla |

Si tienen tiempo: entren como **Dirección** (ve el reporte pero **no** el desglose) y como
**Responsable de área** (no ve Variance) para confirmar que cada rol ve lo que debe.

## Cifras que **ya sabemos** que no coinciden con el Excel (19 líneas)
Se detectaron al comparar las 5,822 cifras de las columnas D a Q. De las 263 líneas con cuentas,
256 coinciden en todo. **No las anoten como hallazgo nuevo; sí díganos cuál es la respuesta.**

| Línea (fila en `Ago`) | Excel | Plataforma | Por qué |
|---|---|---|---|
| Other Income (12) | 31,098.32 | 36,098.32 | El Excel toma celdas puntuales de la hoja de la cuenta y deja fuera 5,000.00. **¿Es intencional?** |
| Total Other Income (25) | 60,422.32 | 65,422.33 | Arrastra la fila 12 |
| IVA Taxes (272) | 284,293.59 | 0.00 | Sus cuentas (`2007003`, `213-0001-000`) son de balance y el archivo de movimientos solo trae resultados |
| Lodging Tax (277) | 160,991.42 | 0.00 | Cuenta `2002014`, igual |
| Bank Commissions (285) | 3,046.52 | 2,695.62 | Cuenta corporativa `504-0001-000` fuera del archivo |
| Audit Fees (289) | 54,075.01 | 32,958.34 | Cuentas `602-0038-000` y `504-0003-000` fuera del archivo |
| Income Taxes (292) | 95,421.00 | 73,801.00 | Cuenta `611-0001-000` fuera del archivo |
| Total Other Taxes (294) y los totales que lo arrastran (336, 533, 535, 573) | 935,337.52; 3,711,624.81… | 446,964.94; 3,223,252.23… | Por las cinco líneas anteriores |
| Administration Fee (273) y dos líneas "Allocated" (576, 577) | valores pegados | — | Son valores escritos a mano en el Excel, sin cuenta ni fórmula |
| Exchange Rate (8) | 17.1337 | — | Es el tipo de cambio, no dinero; no se calcula |
| Employee Dining (14) | 0.00 | 0.01 | Un centavo de residuo |
| Telephone Profit (344) | variación −25.86 | +25.86 | El Excel la trata como gasto aunque es una utilidad. **¿Es intencional?** |
| Net Profit Commercial Services (530) | % −598.5 % | +598.5 % | Su % usa el valor absoluto del presupuesto; el resto del reporte no. **¿Es intencional?** |

También: las cuentas **`4002013`** (−20,000 al mes) y **`4003003`** (≈ −3.2 millones al mes) tienen
movimientos y **ninguna línea de la hoja `Ago` las toma**. Para poder revisar, las dejamos fuera *a
propósito y de forma provisional*. **¿Se excluyen del reporte o es una omisión?**

## Qué NO se puede revisar todavía
- **Septiembre:** falta el Variance y el Budget de septiembre de Contraloría, y hay 154 cuentas con
  movimiento en septiembre que el mapeo de agosto no conoce.
- Comentarios, cierre y aprobación del reporte (Fase 5), y presupuesto dentro del sistema (Fase 7).

## Cómo anotar un hallazgo
Una fila en `docs/HALLAZGOS_CONTRALORIA.md`: qué pantalla y qué línea, qué esperaban ver, qué vieron
y qué tan grave es (**Alta** = la cifra es incorrecta o confunde una decisión; **Media** = estorba o
no se entiende; **Baja** = mejora de forma). Si pueden, adjunten una captura.
