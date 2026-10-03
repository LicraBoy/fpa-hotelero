# Preguntas para Contraloría — Torres Mazatlán (julio a septiembre 2026)

Estas preguntas salen de comparar la plataforma con **tu Excel de Mazatlán** (`02. MZT August 2026 Variance`,
julio y agosto) y de cargar el **CON130 de septiembre** (`SEPTIEMBRE 2026.xls`). *Las preguntas sobre
`4002013` y `4003003` de una versión anterior eran del archivo de Puerto Vallarta y se retiraron.*

**Cómo responder:** contesta en la columna «Tu respuesta» (o por correo, citando el número). Una frase
basta. Cada pregunta dice **qué hace hoy el sistema** y **qué pasa si no se responde**.

**Contestadas por Contraloría (ya aplicadas, no hay que revisarlas):** **P1** y **P13** (las 6 cuentas
`4002020`, `4003001.010`, `4003001.020`, `6009020`, `6009001.004`, `6006012.001` se omiten a propósito:
«todavía no se ocupan»), **P6** (año fiscal julio–junio), **P7, P14, P15** (la Variación y el % se toman de las
columnas G/H, L y Q de `02. MZT August 2026 Variance.xlsx`, línea por línea), **P9** (el Budget del año sale de
`Budget MZT 26-27.xlsx`), **P5** (el tipo de cambio se captura a mano por mes; su YTD es el promedio de los
meses capturados). Se dejan en las tablas para el historial.

**Qué está ya resuelto** (para que no lo revises): en julio y agosto, el **Presupuesto coincide en las
693 líneas**; el **Actual coincide salvo 12 líneas** y la **Variación salvo 27**, todas explicadas abajo.
El CON130 de septiembre cuadra: **Débito = Crédito = 66,323,973.22**, 8,280 movimientos, 544 cuentas.

---

## A. Cifras que hoy no cuadran o no aparecen (las más importantes)

| # | Pregunta | Qué hace hoy el sistema / qué pasa si no se responde | Tu respuesta |
|---|---|---|---|
| **P1** | Las cuentas **`4003001.010`** (≈ −4.1 millones en agosto), **`4003001.020`** (≈ −166 mil) y **`4002020`** (−20,000) tienen movimientos y **ninguna línea de tu reporte las suma**. ¿Se dejan fuera a propósito o es un olvido? ¿A qué línea irían? | Hoy están **excluidas de forma provisional**: sus importes no entran al Variance (la pantalla lo avisa). Si son un olvido, los ingresos del reporte están subestimados. | |
| **P2** | **IVA Taxes 16 %**, **Income Tax**, **Bank Commissions** y **Audit Fees** suman cuentas de pasivo, activo y cuentas ajenas (`2007001`, `1005003`, `6-1-01-100-050`, `6-0-20-35`, `6-1-01-100-500`…). ¿De qué reporte sacas esos números cada mes? | En agosto difieren de tu Excel: IVA 215,965.33 (sistema 0), Income Tax 155,264.00 (0), Audit Fees 56,500.00 (35,500.00), Bank Commissions 561.35 (243.85). Arrastran *Total Other Taxes* (1,044,051.98 vs 651,821.68), *Total Expenses* y *Total Mgmt & Check In*. | |
| **P11** | El **CON130 sí trae las cuentas de balance** (activo y pasivo), a diferencia de la hoja «Base de Datos». ¿IVA e Income Tax salen de ahí? Y tu fórmula `'2007001'!L5`: ¿apunta siempre al **primer mes** de esa hoja? | Si salen del CON130, el sistema los podrá calcular solo. Hoy no los toma porque tu fórmula apunta a una **celda fija**, no al mes. | |
| **P3** | **Miscellaneous Taxable** (fila 19) resta celdas fijas de otras hojas (`'4002001.007'!L5`, `'6019001'!L12`…) y por eso difiere en **5,000.00** de lo que dicen los movimientos (Excel −406.94; sistema 4,593.06). ¿Es a propósito? | Arrastra *Total Other Income* (86,808.83 vs 91,808.83). | |
| **P4** | **6 líneas** listan en `Ago!I:O` una cuenta que su fórmula no suma (p. ej. `6019901` en *Miscellaneous Taxable*, `6006012` en la fila 234) y **15 líneas** suman cuentas que no listan. ¿Cuál es la fuente correcta: **la fórmula o la lista**? | El sistema sigue la **fórmula**. Si la correcta es la lista, algunas líneas cambiarían. | |
| **P13** | En **septiembre** hay 3 cuentas nuevas con movimiento y sin línea: **`6009020` EQUIPO** (6,894.83), **`6009001.004` DIAS FESTIVOS** (5,850.68) y **`6006012.001` TRANSPORTACION** (3,101.98). ¿A qué línea va cada una? *Holidays*, *Equipment* y *Transportation Allowance* existen en **varios departamentos**. | **No salen en el Variance** (15,847.49 en total); la pantalla lo avisa. No las asigno sin tu respuesta. | |
| **P8** | **Non-Deductible**, **Adm Fee 6 %** y las líneas del resumen por departamento son valores escritos a mano o sin fórmula (p. ej. Non-Deductible 0.97; Adm Fee 6 % de julio 102,454.51). ¿De dónde salen? | El sistema muestra 0 en esas líneas. | |

## B. Reglas de cálculo que necesitamos confirmar

| # | Pregunta | Qué hace hoy el sistema | Tu respuesta |
|---|---|---|---|
| **P5** | **Tipo de cambio:** ¿de dónde sale el **Actual** (17.1337 agosto, 17.2175 julio)? El Budget es **18 fijo**: ¿siempre? ¿Es correcto que **Variación = Presupuesto − Actual** y **% = Variación ÷ Presupuesto** (0.87 y 4.8 % en agosto)? **Y para septiembre: ¿cuál es el Actual y el Budget?** | Septiembre **no tiene tipo de cambio**: se ve «—». Hoy el sistema no tiene dónde capturarlo (solo lo toma de tu Excel). | |
| **P6** | **Año fiscal:** el título de la hoja dice *FY 25/26* y el sistema toma **julio–junio** (agosto 2026 = 2026/27). ¿Cuál es el correcto? | Con otro año fiscal cambian el **acumulado** y los 12 meses de la pestaña Budget. | |
| **P7** | *Less Discount*, *VDS Allocation Collections* y el resumen de ingresos por departamento no tienen cuentas. En tu Excel la Variación es **Actual − Presupuesto**; el sistema toma la regla de su sección (gasto: Presupuesto − Actual). ¿Qué regla aplica a las líneas sin cuentas? | **16 líneas** salen con la Variación al revés de tu Excel (mismos Actual y Presupuesto, signo contrario). | |
| **P14** | **Gross Profit Money Exchange** y **Net Profit Money Exchange** (filas 615 y 617): la Variación de tu Excel no es ni Actual − Presupuesto ni Presupuesto − Actual de sus propias columnas (p. ej. −37,802.63 vs −34,876.69). ¿Cómo se calcula? | Mostramos lo que dan sus columnas. | |
| **P15** | Líneas **sin Presupuesto** (p. ej. *Education Bonus*, *Holidays*, *Sunday Premiums*: 9 líneas): tu Excel muestra Variación **0**; el sistema muestra **«—»** (no hay presupuesto). ¿Prefieres que muestre 0? | «—» = no hay dato; un 0 diría que se cumplió el presupuesto. | |

## C. Datos que faltan

| # | Pregunta | Qué pasa si no se responde | Tu respuesta |
|---|---|---|---|
| **P9** | ¿Puedes darnos el **Budget de septiembre** (y de los meses siguientes) y el **presupuesto anual**? Tu Excel de Mazatlán solo trae julio y agosto, sin anual. Y el **Variance de septiembre** que armaste, para compararlo. | En septiembre **Presupuesto, Variación y % salen en «—»** y el acumulado también. El bloque anual siempre sale «—». Puedes capturarlo tú en la pestaña **Budget** (escribir o *Copiar el Actual* con un % de ajuste). | |
| **P16** | El CON130 de septiembre trae **18 movimientos con Débito y Crédito en blanco** (p. ej. *LOZA DE BAJA PUB EN GRAL*, *DIF DEPURADA SALDO BANCO*, *PAGO PREST EMPL FONDO AHORRO*). El saldo no cambia: ¿son **movimientos de cero** legítimos? | Los cargamos como **0 con un aviso**. Si alguno escondiera un importe, el saldo cambiaría y el sistema **rechazaría** el archivo. | |
| **P17** | En ese mismo CON130 hay **26 filas repetidas exactamente** y **300 movimientos con importe negativo**. ¿Son **reversos y ajustes legítimos**? | Se cargan con un aviso («pueden ser legítimas»). Un duplicado real inflaría un saldo. | |

## C2. Nuevas, de la sesión del 02-oct-2026

| # | Pregunta | Qué hace hoy el sistema / qué pasa si no se responde | Tu respuesta |
|---|---|---|---|
| **P19** | ¿Puedes darnos el **CON130 completo de julio y agosto**? | Las líneas que dependen de cuentas de balance (IVA, Income Tax…) en el **acumulado de septiembre** quedan cortas: solo tienen septiembre. | |
| **P20** | En **julio** el IVA (*IVA Taxes 16 %* y sus detalles 756, 757, 807, 808) usa una fórmula distinta a la de agosto. ¿Es intencional o conviene unificarla para septiembre? | Septiembre usa la fórmula de agosto. Julio se reproduce con una excepción documentada. | |
| **P21** | Unas **150 líneas no tienen cuentas** (asignaciones corporativas, etc.). ¿Se capturan a mano cada mes en la pestaña Budget? ¿Quién? | La pantalla avisa «líneas sin Actual capturado»; su Actual y Variación quedan en «—». | |

## D. Proceso y permisos

| # | Pregunta | Tu respuesta |
|---|---|---|
| **P10** | ¿Quién debe poder **ver el detalle de los movimientos** (el desglose desde una cifra hasta el asiento)? Hoy lo ven **Contralor, Analista y Auditoría**; **Dirección no**. | |
| **P12** | **Budget en pantalla:** ¿quién puede **editarlo** (hoy: Contralor y Analista) y **quién lo aprueba**? ¿Se parte siempre de tu Excel o a veces del **Actual del año anterior**? Ojo: si se **vuelve a importar el Excel**, reemplaza el Budget vigente, incluido lo que se capturó a mano (la versión anterior queda en el historial). ¿Qué flujo prefieres? | |
| **P18** | **Puerto Vallarta:** ¿usa el mismo Novohit y un catálogo de cuentas parecido? ¿Cuándo se incorpora? | |

---

## Resumen: qué es urgente
1. **P1, P13, P2/P11:** definen si el reporte está **completo**. Hoy faltan 3 cuentas de septiembre (15,847.49), 3 excluidas (más de 4 M en agosto) y las líneas de impuestos.
2. **P9 y P5 (septiembre):** sin el Budget y el tipo de cambio de septiembre, el Variance de septiembre **no se puede comparar**.
3. **P6 (año fiscal):** cambia el acumulado.

Todo lo demás son reglas de signo y presentación que **no cambian las cifras de Actual**.
