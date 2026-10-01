# Guía de revisión — Variance de agosto 2026

**Para qué sirve:** revisar la pantalla de Variance con las cifras reales de agosto y decirnos si
coincide con lo que Contraloría usa hoy en su Excel. Dura unos 60 minutos y **no hace falta saber de
sistemas**.

**Qué tienes que hacer, en resumen:**
1. Hacer las 10 tareas de la Parte 2 y comprobar que se ve lo que dice la columna "Qué debe verse".
2. Contestar las preguntas de la Parte 4.
3. Anotar cualquier cosa rara o confusa en `docs/HALLAZGOS_CONTRALORIA.md`.

---

## Parte 1 — Antes de empezar

*(Lo hace TI o quien prepara la sesión.)*
1. Abrir `iniciar_servidores.bat` y esperar a que se abra el navegador.
2. Cargar agosto, una sola vez (repetirlo no cambia nada):
   `cd backend` → `set FPA_ENTORNO=desarrollo` →
   `.venv\Scripts\python -m fpa.demo_agosto --datos "C:\...\PLATAFORMA FP&A E INTELIGENCIA HOTELERA"`
3. Entrar a `http://localhost:5180`, elegir **Contralor** en "Usuario (desarrollo)" y abrir la
   pestaña **Variance**. Debe abrir en el mes **2026-08**.

> El usuario se elige a mano porque es una versión de prueba. Después se entrará con el usuario de
> la empresa.

### Cómo leer la pantalla
- Hay **tres bloques**: *Mes*, *Acumulado del año fiscal* (julio y agosto) y *Presupuesto anual*.
  Cada uno muestra **Actual, Presupuesto, Variación y % var.**
- **Variación positiva = favorable.** En ingresos y utilidades es real menos presupuesto; en gastos
  es presupuesto menos real. Si es **desfavorable** lleva **▼** y va **entre paréntesis**.
- **—** quiere decir "no hay dato". No es un cero.
- Los números de la columna **Actual** son enlaces: al hacer clic muestran de dónde salen.

---

## Parte 2 — Las 10 tareas

Haz cada tarea y compara con la última columna. Si en tu pantalla sale otra cosa, anótalo.

| # | Qué hacer | Qué debe verse |
|---|---|---|
| 1 | Abrir **Variance**, mes 2026-08 | La tabla con sus secciones, en el mismo orden que la hoja `Ago`. Arriba, un aviso amarillo que dice que dos cuentas (`4002013` y `4003003`) quedan fuera a propósito |
| 2 | Buscar **Salaries** en la sección *Mgmt & Check In* | Mes: Actual **321,190.84**, Presupuesto 332,935.91, Variación 11,745.07 (3.5 %). Igual que tu Excel |
| 3 | Mirar los totales **Total Mgmt & Check In** y **Total Maid & Linen** | **483,198.48** y **442,235.81** en el mes. Igual que tu Excel |
| 4 | Plegar y desplegar una sección (los títulos azules) | Al plegar, quedan visibles sus totales y subtotales |
| 5 | Elegir una **Sección**, escribir `insurance` en **Buscar línea** y marcar **Solo totales y subtotales** | La tabla se reduce a lo que pediste |
| 6 | Hacer clic en el **Actual de Salaries (mes)** | Una pantalla con la cuenta `6009001.001`, el importe 321,190.84 y la marca verde **Cuadra** |
| 7 | Hacer clic en la cuenta y luego en **Cargar más** hasta que ya no aparezca | Los movimientos suman el total de la cuenta. Al final dice **Cuadra con el neto de la cuenta** |
| 8 | Hacer clic en el número de un **asiento** | Se ven todas sus líneas. Puede decir "Solo cuentas de resultados": es normal, el reporte solo trae esas |
| 9 | Hacer clic en un **total** (por ejemplo *Total Other Income*) y bajar por sus partes | Cada nivel suma lo del nivel de arriba |
| 10 | Pulsar **Exportar a Excel** | Se descarga un `.xlsx` con el mismo formato que la hoja `Ago` y las mismas cifras que la pantalla |

**Si te sobra tiempo:** entra como **Dirección** (ve el reporte, pero no el detalle de movimientos) y
como **Responsable de área** (no ve Variance). Es para confirmar que cada persona ve lo que le toca.

---

## Parte 3 — Diferencias que ya conocemos

Al comparar las 5,822 cifras con tu Excel, **19 líneas no coinciden** y ya sabemos por qué: el
sistema solo recibe la hoja *Base de Datos*, y tu Excel usa además otras fuentes. De las 263 líneas
que tienen cuentas, 256 coinciden en todo.

**No las anotes como problema nuevo. Lo que necesitamos es que nos digas la respuesta** (Parte 4).

| Línea (fila en `Ago`) | Tu Excel | El sistema | Por qué |
|---|---|---|---|
| Other Income (12) | 31,098.32 | 36,098.32 | Tu Excel deja fuera 5,000.00 de los movimientos |
| Total Other Income (25) | 60,422.32 | 65,422.33 | Arrastra la línea anterior |
| IVA Taxes (272) | 284,293.59 | 0.00 | Sus cuentas son de balance y la *Base de Datos* no las trae |
| Lodging Tax (277) | 160,991.42 | 0.00 | Igual: cuenta de balance |
| Bank Commissions (285) | 3,046.52 | 2,695.62 | Una de sus cuentas (`504-0001-000`) no viene en la *Base de Datos* |
| Audit Fees (289) | 54,075.01 | 32,958.34 | Dos de sus cuentas (`602-0038-000`, `504-0003-000`) no vienen |
| Income Taxes (292) | 95,421.00 | 73,801.00 | Su cuenta (`611-0001-000`) no viene |
| Total Other Taxes (294) y los totales que lo arrastran (336, 533, 535, 573) | 935,337.52 · 3,711,624.81… | 446,964.94 · 3,223,252.23… | Por las cinco líneas de arriba |
| Administration Fee (273) y dos "Allocated" (576, 577) | números escritos a mano | — | No tienen cuenta ni fórmula en tu Excel |
| Exchange Rate (8) | 17.1337 | — | Es un tipo de cambio, no dinero: el sistema no lo calcula |
| Employee Dining (14) | 0.00 | 0.01 | Un centavo de diferencia |
| Telephone Profit (344) | variación −25.86 | +25.86 | Tu Excel la calcula como gasto aunque es una utilidad |
| Net Profit Commercial Services (530) | % −598.5 % | +598.5 % | Su porcentaje se calcula distinto al del resto del reporte |

**Además,** dos cuentas con mucho dinero (`4002013`, unos −20,000 al mes, y `4003003`, unos −3.2
millones al mes) tienen movimientos y **ninguna línea de tu reporte las suma**. Para poder revisar,
las dejamos fuera de forma provisional.

---

## Parte 4 — Las preguntas para Contraloría

Contéstalas en `docs/HALLAZGOS_CONTRALORIA.md`, en la columna "Respuesta de Contraloría". Están en
orden de importancia.

| # | La pregunta, en simple |
|---|---|
| **P1** | `4002013` y `4003003` tienen movimientos pero ninguna línea las suma (`4003003` mueve unos 3 millones al mes). ¿Las dejas fuera a propósito o es un olvido? |
| **P2** | En *Other Income* tu Excel deja fuera 5,000.00. ¿Es a propósito? |
| **P3** | IVA, Lodging Tax, comisiones bancarias, honorarios de auditoría e impuestos: ¿de qué reporte sacas esos números cada mes? |
| **P4** | *Telephone Profit* se calcula como si fuera un gasto, aunque es utilidad. ¿Está bien así? |
| **P5** | El porcentaje de *Net Profit Commercial Services* se calcula distinto al del resto. ¿Cuál es la regla correcta? |
| **P6** | *Administration Fee* y las dos líneas *Allocated* son números escritos a mano. ¿De dónde salen? |
| **P7** | ¿El año fiscal empieza en julio? ¿Leer "positivo = favorable" es correcto en todas las líneas? |
| **P8** | ¿Cómo identificas una línea del reporte de forma única? ¿De dónde sale el presupuesto? |
| **P9** | ¿Quién debe poder ver el detalle de los movimientos? Hoy lo ven Contralor, Analista y Auditoría; Dirección no |
| **P10** | ¿Puedes darnos el Variance y el presupuesto de septiembre? |

---

## Parte 5 — De dónde salen las cifras (para entender las diferencias)

Hoy el reporte se arma a mano con el documento `docs/adr/Prompt_Integracion_Variance.docx`. El
sistema reproduce ese proceso:

1. Se parte de la hoja *Base de Datos*: los movimientos de las cuentas de resultados.
2. Se arma una hoja por cada cuenta, con su total por mes y el acumulado de julio y agosto.
3. La hoja `Ago` se liga a esos totales con fórmulas: la columna **S** trae el total del mes y la
   **T** el acumulado. Los números de cuenta de cada línea están en las columnas **X a AC**.
4. A las cuentas que empiezan con **4** (ingresos) se les pone signo negativo.
5. El presupuesto está **escrito a mano** en `Ago` (columnas E, J y O). Por eso solo hay presupuesto
   de agosto.

Lo que esto explica:
- Una cuenta con movimientos que **no está en las columnas X a AC no entra a ninguna línea**. Es el
  caso de `4002013` y `4003003`. Parece un olvido al armar el reporte, pero eso solo lo confirmas tú.
- **IVA, Lodging Tax, comisiones, auditoría e impuestos** vienen de cuentas que la *Base de Datos* no
  trae; hoy las tomas de otras hojas.
- **El proceso se repite cada mes con una base nueva.** Por eso el mapeo de agosto no sirve tal cual
  para septiembre: hay 154 cuentas nuevas.
- **El sistema lee las fórmulas de S y T para saber qué cuentas suma cada línea.** Si una fórmula del
  Excel cambia, cambia lo que el sistema suma.

---

## Parte 6 — Qué todavía no se puede revisar
- **Septiembre:** falta el Variance y el presupuesto de septiembre, y el mapeo no conoce 154 cuentas
  que tienen movimientos ese mes.
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
