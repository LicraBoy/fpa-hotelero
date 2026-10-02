# Guía de revisión — Variance de Mazatlán, agosto 2026

**Para qué sirve:** revisar la pantalla de Variance con las cifras reales de **Mazatlán** y decirnos
si coincide con el Excel que Contraloría usa hoy (`02. MZT August 2026 Variance (Envio).xlsx`).
Dura unos 60 minutos y **no hace falta saber de sistemas**.

> **Aviso:** una versión anterior de esta guía usaba por error el archivo de **Puerto Vallarta**.
> Las preguntas sobre `4002013` y `4003003` eran de ese archivo y **ya no aplican**.

**Qué tienes que hacer, en resumen:**
1. Hacer las 11 tareas de la Parte 2 y comprobar que se ve lo que dice la columna "Qué debe verse".
2. Contestar las preguntas de la Parte 4.
3. Anotar cualquier cosa rara o confusa en `docs/HALLAZGOS_CONTRALORIA.md`.

---

## Parte 1 — Antes de empezar

*(Lo hace TI o quien prepara la sesión.)*
1. Abrir `iniciar_servidores.bat` y esperar a que se abra el navegador.
2. Cargar julio y agosto, una sola vez (repetirlo no cambia nada):
   `cd backend` → `set FPA_ENTORNO=desarrollo` →
   `.venv\Scripts\python -m fpa.demo_agosto --datos "C:\...\PLATAFORMA FP&A E INTELIGENCIA HOTELERA"`
   (también encuentra el archivo en `docs\adr\`). Al terminar escribe la lista de cuentas que dejó
   fuera a propósito: son tres (ver Parte 3).
3. Entrar a `http://localhost:5180`, elegir **Contralor** en "Usuario (desarrollo)" y abrir la
   pestaña **Variance**. Debe abrir en el mes **2026-08**; también puedes ver **2026-07**.

> El usuario se elige a mano porque es una versión de prueba. Después se entrará con el usuario de
> la empresa.

### Cómo leer la pantalla
- Hay **tres bloques**: *Mes*, *Acumulado del año fiscal* y *Presupuesto anual*. Cada uno muestra
  **Actual, Presupuesto, Variación y % var.**
- **Tu Excel de Mazatlán solo trae el mes.** El **acumulado (julio + agosto) lo calcula el sistema**
  con los movimientos reales y el presupuesto de cada mes. El **presupuesto anual** sale como **—**
  porque el Excel no lo trae.
- **Variación positiva = favorable.** En ingresos y utilidades es real menos presupuesto; en gastos
  es presupuesto menos real. Si es **desfavorable** lleva **▼** y va **entre paréntesis**.
- **—** quiere decir "no hay dato". No es un cero.
- Los números de la columna **Actual** son enlaces: al hacer clic muestran de dónde salen.

---

## Parte 2 — Las 11 tareas

Haz cada tarea y compara con la última columna. Si en tu pantalla sale otra cosa, anótalo.

| # | Qué hacer | Qué debe verse |
|---|---|---|
| 1 | Abrir **Variance**, mes 2026-08 | La tabla con sus secciones, en el mismo orden que la hoja `Ago`. Arriba, un aviso amarillo que dice que **tres** cuentas quedan fuera a propósito |
| 2 | Buscar **Rental Income** (sección *Other Income*) | Mes: Actual **13,787.41**, Presupuesto 13,091.03, Variación 696.38 (5.3 %). Acumulado: Actual 67,537.98. Igual que tu Excel |
| 3 | Mirar **Total Maid & Linen** | Mes: Actual **367,344.39**, Presupuesto 364,051.79, Variación **(3,292.60)** con ▼ (−0.9 %). Igual que tu Excel |
| 4 | Buscar **Exchange Rate** (tipo de cambio) | Mes: Actual **17.13**, Presupuesto **18.00**, Variación **0.87**, **4.8 %**. En el acumulado y el anual, **—** (un tipo de cambio no se suma) |
| 5 | Plegar y desplegar una sección (los títulos azules) | Al plegar, quedan visibles sus totales y subtotales |
| 6 | Elegir una **Sección**, escribir `insurance` en **Buscar línea** y marcar **Solo totales y subtotales** | La tabla se reduce a lo que pediste |
| 7 | Hacer clic en el **Actual de Rental Income (mes)** | Una pantalla con la cuenta `4002011`, el importe 13,787.41 y la marca verde **Cuadra** |
| 8 | Hacer clic en la cuenta y luego en **Cargar más** hasta que ya no aparezca | Los movimientos suman el total de la cuenta. Al final dice **Cuadra con el neto de la cuenta** |
| 9 | Hacer clic en el número de un **asiento** | Se ven todas sus líneas. Puede decir "Solo cuentas de resultados": es normal, el reporte solo trae esas |
| 10 | Hacer clic en un **total** (por ejemplo *Total Maid & Linen*) y bajar por sus partes | Cada nivel suma lo del nivel de arriba |
| 11 | Pulsar **Exportar a Excel** | Se descarga un `.xlsx` con el mismo formato que la hoja `Ago` y las mismas cifras que la pantalla |

**Si te sobra tiempo:** cambia el mes a **2026-07** (julio se compara contra la hoja `Jul-Ago` de tu
Excel) y entra como **Dirección** (ve el reporte, pero no el detalle) y como **Responsable de área**
(no ve Variance). Es para confirmar que cada persona ve lo que le toca.

---

## Parte 2 bis — El Budget en pantalla (nuevo)

Abre la pestaña **Budget** (la ven Contralor y Analista). Muestra, para cada línea y cada mes del año
fiscal, el **Budget** (editable) y, al lado en gris, el **Actual** como referencia.

| # | Qué hacer | Qué debe verse |
|---|---|---|
| B1 | Elegir una **Sección** y mirar una línea de detalle | Una casilla de Budget por mes, con el Actual de ese mes al lado. Un mes sin movimientos cargados muestra **—** en el Actual |
| B2 | Escribir un importe en una casilla | La casilla se marca como editada y los **totales de la sección cambian al instante**. Abajo dice cuántos cambios hay sin guardar |
| B3 | Escribir letras en una casilla | Se marca en rojo y **no deja guardar** |
| B4 | Poner `10` en *Ajuste sobre el Actual (%)* y pulsar **Copiar el Actual** | Se llenan los meses **sin Budget** con el Actual + 10 %. Lo que ya escribiste no se pisa |
| B5 | Pulsar **Guardar como versión nueva** y confirmar | Mensaje con el número de versión. La anterior se conserva en el historial |
| B6 | Ir a **Variance** | Ya usa el Budget nuevo (mes y acumulado) |

### Un mes sin Budget (por ejemplo septiembre)
Tu Excel de Mazatlán solo trae el Budget de **julio y agosto**. Un mes sin Budget no se inventa en cero:
**Presupuesto, Variación y % var. salen en «—»** (el Actual sí se calcula) y la pantalla lo avisa con un
botón a la pestaña Budget. Para llenarlo: **Budget** → año 2026/27 → columna del mes → escribe el importe
o usa **Copiar el Actual** (con un ajuste en %) → **Guardar como versión nueva**. El **acumulado** del mes
solo se llena cuando hay Budget de **todos** los meses del año fiscal hasta ese mes.

**Cómo se calcula:** *Variación* = Actual − Presupuesto en ingresos y utilidades, y Presupuesto − Actual en
gastos (positivo = favorable). *% var.* = Variación ÷ Presupuesto.

**Cuidado:** si vuelves a **importar el Excel** de Contraloría, reemplaza el Budget vigente (incluido lo que
capturaste a mano). La versión anterior queda en el historial, pero deja de usarse.

**Nota:** *Importar el Budget desde el Excel de Contraloría* sirve de punto de partida; después se
corrige aquí. Un total o subtotal **no se edita**: se calcula de sus partes.

---

## Parte 3 — Diferencias que ya conocemos

Comparamos las 693 líneas con cifras de tu Excel, en **agosto y julio**. **Todas coinciden salvo 12
líneas del Actual y 27 de la Variación**, y ya sabemos la causa de cada una. En el
**presupuesto** coinciden todas.

**No las anotes como problema nuevo. Lo que necesitamos es que nos digas la respuesta** (Parte 4).

### A. Líneas donde el Actual no coincide (agosto)

| Línea (fila en `Ago`) | Tu Excel | El sistema | Por qué |
|---|---|---|---|
| Miscellaneous Taxable (19) | (406.94) | 4,593.06 | La fórmula resta celdas fijas de otras hojas (`'4002001.007'!L5`, `'6019001'!L12`…) y no solo el movimiento del mes |
| Total Other Income (32) | 86,808.83 | 91,808.83 | Arrastra la línea anterior (5,000.00) |
| Bank Commissions (70) | 561.35 | 243.85 | La fórmula suma una cuenta ajena (`6-1-01-100-050`) que la *Base de Datos* no trae |
| Audit Fees (308) | 56,500.00 | 35,500.00 | Suma cuentas ajenas (`6-0-20-35`, `6-1-01-100-500`) |
| Non-Deductible (313) | 0.97 | 0.00 | Sin fórmula en tu Excel; la cuenta `6004043` está listada pero no se suma |
| IVA Taxes 16% (317) | 215,965.33 | 0.00 | Sus cuentas son de pasivo (`2007001`, `2-1-70-20`) y la *Base de Datos* solo trae resultados |
| Income Tax (318) | 155,264.00 | 0.00 | Sus cuentas son de activo (`1005003`, `1-1-10-90`); igual que arriba |
| Total Other Taxes (319) | 1,044,051.98 | 651,821.68 | Por las tres líneas anteriores |
| Total Expenses (76) y Total Mgmt & Check In (78) | 809,787.90 · 715,207.89 | 809,470.40 · 714,890.39 | Por Bank Commissions (70): 317.50 de diferencia |

En **julio** además: *Bank Commissions* (304) y *Adm Fee 6 %* (314, tu Excel pega 102,454.51 sin fórmula).

### B. Líneas donde el Actual y el Presupuesto coinciden, pero la Variación tiene otro signo
- **Convención de signo (16 líneas):** *Less Discount* (3 líneas), *VDS Allocation Collections*,
  *Collection IVA Taxes 16%* y el resumen de ingresos por departamento (*Telephones* … *Restaurant*,
  *Total Income*, *Profit Commercial Services*). Tu Excel calcula Actual − Presupuesto; el sistema,
  como esas líneas no tienen cuentas, toma la regla de su sección (gasto: Presupuesto − Actual).
- **Sin presupuesto (9 líneas)**, como *Education Bonus*: tu Excel muestra 0 en la variación; el
  sistema muestra **—** porque no hay presupuesto, no inventa un cero.
- *Gross Profit Money Exchange* y *Net Profit Money Exchange*: la variación de tu Excel no es
  Actual − Presupuesto ni Presupuesto − Actual de sus propias columnas.

### C. Cuentas con movimiento que **ninguna línea** de tu Excel suma (agosto)

| Cuenta | Descripción | Importe del mes |
|---|---|---|
| `4003001.010` | Ingresos por venta de derechos de hospedaje | −4,142,045.24 |
| `4003001.020` | Ingresos 4 % venta derechos de hospedaje | −165,681.81 |
| `4002020` | Servicios administrativos y contables | −20,000.00 |

Para poder revisar, las dejamos fuera de forma provisional. Por eso el reporte dice que **no
incluye** esos movimientos.

---

## Parte 4 — Las preguntas para Contraloría

Contéstalas en `docs/HALLAZGOS_CONTRALORIA.md`, en la columna "Respuesta de Contraloría". Están en
orden de importancia.

| # | La pregunta, en simple |
|---|---|
| **P1** | Las cuentas `4003001.010` y `4003001.020` (más de 4 millones en agosto) y `4002020` tienen movimientos y **ninguna línea las suma**. ¿Las dejas fuera a propósito o es un olvido? |
| **P2** | *IVA Taxes*, *Income Tax*, *Bank Commissions* y *Audit Fees* suman cuentas que la *Base de Datos* no trae (pasivo, activo y cuentas ajenas `6-1-01…`). ¿De qué reporte sacas esos números cada mes? |
| **P3** | *Miscellaneous Taxable* resta celdas fijas (`L5`, `L12`) de otras hojas y por eso difiere en 5,000.00 de lo que dicen los movimientos. ¿Es a propósito? |
| **P4** | 6 líneas listan en `Ago!I:O` una cuenta que su fórmula no suma (por ejemplo `6019901` en *Miscellaneous Taxable*, `6006012` en la fila 234) y 15 líneas suman cuentas que no listan. ¿Cuál es la fuente correcta, la fórmula o la lista? |
| **P5** | **Tipo de cambio:** ¿de dónde sale el Actual (17.1337 en agosto, 17.2175 en julio)? El presupuesto es 18 fijo. ¿Está bien que Variación = Presupuesto − Actual y % = Variación / Presupuesto? |
| **P6** | **Año fiscal:** el título de la hoja dice *FY 25/26* y nosotros tomamos julio–junio (agosto 2026 = año 2026/27). ¿Cuál es el año fiscal correcto? |
| **P7** | *Less Discount*, *VDS Allocation Collections* y el resumen de ingresos por departamento: ¿se calculan Actual − Presupuesto? ¿Qué regla de signo aplica a las líneas sin cuentas? |
| **P8** | *Non-Deductible*, *Adm Fee 6 %* y las líneas del resumen son valores escritos a mano o sin fórmula. ¿De dónde salen? |
| **P9** | ¿Puedes darnos el **presupuesto anual** y el Variance de septiembre? Tu Excel de Mazatlán solo trae el mes. |
| **P10** | ¿Quién debe poder ver el detalle de los movimientos? Hoy lo ven Contralor, Analista y Auditoría; Dirección no |
| **P11** | **CON130:** nosotros leemos el mes, la fecha y la cuenta directamente del reporte de Novohit (lo que hoy hacen tus fórmulas). El CON130 trae también las cuentas de balance: ¿*IVA Taxes* e *Income Tax* salen de ahí? ¿Tu fórmula `'2007001'!L5` apunta siempre al primer mes de esa hoja? |
| **P12** | **Budget en pantalla:** ¿quién puede editarlo y quién lo aprueba? ¿Se parte siempre de tu Excel o a veces del Actual del año anterior? |
| **P13** | **Cuentas nuevas sin línea:** en septiembre, `6009020` (EQUIPO, 6,894.83), `6009001.004` (DIAS FESTIVOS, 5,850.68) y `6006012.001` (TRANSPORTACION, 3,101.98) tienen movimientos y **no están en ninguna línea**, por eso no salen en el Variance (la pantalla lo avisa). ¿A qué línea va cada una? *Holidays*, *Equipment* y *Transportation Allowance* existen en varios departamentos |

---

## Parte 5 — De dónde salen las cifras (para entender las diferencias)

Hoy el reporte se arma a mano con el documento `docs/adr/Prompt_Integracion_Variance.docx`. En
**Mazatlán** funciona así, y el sistema lo reproduce:

1. Se parte de la hoja *Base de Datos*: los movimientos de las cuentas de resultados (11,818 de
   julio y agosto, 442 cuentas).
2. Se arma una hoja por cada cuenta, con su total por mes.
3. La hoja **`Jul-Ago`** se liga a esas hojas con fórmulas (`SUMIFS` por mes): la columna **E** es
   julio y la **J** es agosto. El nombre de la hoja es el número de cuenta.
4. A las cuentas de ingreso (empiezan con **4**) se les pone signo negativo en la fórmula.
5. La hoja **`Ago`** trae el resultado **pegado como valores** (Actual, Presupuesto, Variación y %),
   y en las columnas **I a O** la lista de cuentas de cada línea. El presupuesto de cada mes está
   escrito a mano.

Lo que esto explica:
- **El sistema lee las fórmulas de `Jul-Ago`** para saber qué cuentas suma cada línea y con qué
  signo. Si una fórmula cambia, cambia lo que el sistema suma.
- Las fórmulas que **suman celdas fijas** (`'6019132'!L5`) o cuentas de **otras fuentes** no se
  pueden reproducir con la *Base de Datos*: son las diferencias de la Parte 3.
- **El proceso se repite cada mes con una base nueva**, así que el mapeo de agosto hay que revisarlo
  para septiembre.

---

## Parte 6 — Qué todavía no se puede revisar
- **Septiembre** y el **presupuesto anual** (tu Excel de Mazatlán no los trae).
- **Comentarios, cierre y aprobación del reporte** (se hacen después) y el **presupuesto dentro del
  sistema** (más adelante).

---

## Parte 7 — Cómo anotar un hallazgo

Agrega una fila en `docs/HALLAZGOS_CONTRALORIA.md` con:
- **Dónde:** la pantalla y la línea.
- **Qué esperabas ver** y **qué viste**.
- **Qué tan grave es:**
  - **Alta:** una cifra es incorrecta o puede llevar a una mala decisión.
  - **Media:** estorba, confunde o falta algo importante.
  - **Baja:** es una mejora de forma.
- Si puedes, una captura de pantalla.

**Anota también lo que no se entienda.** Si algo te confundió al leer, es un hallazgo.
