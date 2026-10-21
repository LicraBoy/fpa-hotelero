# ADR 0007 — Librerías de datos y ciencia de datos

Estado: propuesta (a confirmar al empezar la Fase 8) · Fecha: 2026-10-21 · **No se instala nada todavía**

## Contexto
Para las fases con análisis (Forecast, escenarios, anomalías) se evaluaron las librerías que se
consideran «las mejores actuales»: pandas, Polars, NumPy, SciPy, statsmodels, scikit-learn,
XGBoost/LightGBM, PyTorch, TensorFlow/Keras, Matplotlib, Seaborn y Plotly. Hoy el backend no usa
ninguna: solo `Decimal`, `openpyxl` y `xlrd`.

Condiciones del producto que pesan más que el «ranking» general:
- **Datos chicos:** un hotel, series **mensuales cortas** y miles de filas por mes. La velocidad
  de procesamiento no es el cuello de botella.
- **El dinero debe cuadrar al centavo** y ser reproducible: lo oficial (Budget, Actual, Variance)
  no puede pasar por decimales binarios (`float`).
- **Auditabilidad:** cada cifra debe poder explicarse y repetirse.
- **PC de la empresa sin permisos de administrador:** se prefieren paquetes con ruedas
  precompiladas y pocas dependencias.

## Hallazgos (investigación de octubre 2026)
- **pandas 3.0** (21-ene-2026): tipo de texto propio por omisión, Copy-on-Write y fechas en
  microsegundos; lo oficial es migrar primero a 2.3 y limpiar advertencias. Sigue siendo el estándar
  y el que mejor se integra con scikit-learn y statsmodels.
  Fuentes: [novedades 3.0](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html),
  [anuncio](https://pandas.pydata.org/community/blog/pandas-3.0.html).
- **Polars:** motor de streaming rediseñado y mucho más rápido en uniones y agrupaciones grandes;
  las cifras exactas varían entre blogs y las versiones citadas se contradicen, así que no se
  usan como argumento. Fuente: [comparativa](https://vrlatech.com/polars-vs-pandas-in-2026-which-python-dataframe-library-should-you-use/).
- **Pronóstico estadístico:** `statsforecast` (Nixtla) dice ser mucho más rápido que statsmodels y
  Prophet, pero son cifras del propio proveedor y sus pruebas son de series diarias y semanales,
  no mensuales. No hay una comparación independiente en series mensuales.
  Fuente: [paquete](https://pypi.org/project/statsforecast/1.2.1).
- **Aprendizaje automático vs. profundo:** en la competencia M4 ganaron métodos estadísticos o
  híbridos; en M5 ganó gradient boosting (LightGBM), pero con series de ventas grandes. Con pocas
  observaciones las redes neuronales se sobreajustan.
  Fuentes: [revisión de modelos de series de tiempo](https://arxiv.org/pdf/2401.13912),
  [¿necesitamos deep learning?](https://www.paperswithcode.com/paper/do-we-really-need-deep-learning-models-for).
- **Visualización:** `plotly.js` (MIT) para gráficas interactivas en el frontend; Matplotlib y
  Seaborn sirven para figuras estáticas de informes, no para la interfaz.

## Decisión propuesta

| Necesidad | Librería | Cuándo | Nota |
|---|---|---|---|
| Dinero oficial (Budget, Actual, Variance) | `Decimal` (estándar) | Siempre | Nunca pasa por pandas ni `float` |
| Ciclo del Budget y mensualización | Python estándar | Fase 7 | Sin dependencias nuevas |
| Tablas de análisis y cargas operativas | **pandas 3** (+ `pyarrow`) | Fase 8 | Polars solo si una carga operativa grande lo exige |
| Cálculo numérico y escenarios | **NumPy**, **SciPy** | Fase 9 | Resultados a `Decimal` al guardarse |
| Pronóstico | **statsmodels** y/o **statsforecast** | Fase 8 | Se elige con una validación de origen móvil (abajo) |
| Anomalías y explicación de variaciones | **scikit-learn**; **LightGBM** solo con datos suficientes | Fase 12 | No antes |
| Gráficas interactivas | **plotly.js** (frontend) | Tras el rediseño | Probar contra la CSP estricta; alternativa: ECharts |
| Figuras estáticas de informes | Matplotlib (Seaborn opcional) | Cuando haya informes en PDF o Excel | |
| PyTorch, TensorFlow, Keras | **No por ahora** | — | Pocas observaciones; difícil de auditar y reproducir. Se reevalúa con más datos (Fase 11, multihotel) |
| XGBoost | Solo si LightGBM no sirve | Fase 12 | Equivalentes; no se instalan los dos |

## Cómo se elige entre alternativas (criterio de aceptación)
Ninguna fuente compara estas librerías en **series mensuales de un hotel**, así que no se decide por
reputación: se corre una **validación con origen móvil** sobre los datos reales de Torres (histórico
disponible), con las métricas MASE y sMAPE, y gana el modelo más simple que no pierda frente a los
demás. Se guarda el informe de la comparación junto al ADR definitivo.

## Reglas transversales
1. **El dinero oficial siempre en `Decimal`.** Las proyecciones estadísticas usan decimales binarios,
   se marcan como **proyección** y se convierten a `Decimal` al guardarse.
2. **Reproducible:** cada pronóstico guarda la versión de los datos, del modelo y la semilla; el
   mismo insumo da el mismo resultado.
3. **Cálculo puro:** los modelos viven en `servicios/` sin acceso a la base de datos (el router
   consulta y los llama), como el resto del motor.
4. **Dependencias nuevas:** se avisan a TI antes de usarlas, se fijan en `requirements.txt` y se
   prueban en SQLite y PostgreSQL.
5. **Sin caja negra para decisiones oficiales:** un resultado de aprendizaje automático solo se
   muestra con su explicación y nunca reemplaza una cifra del cierre.

## Consecuencias
- Hasta la Fase 8 no se agrega ninguna librería de ciencia de datos al backend.
- Esta decisión se reconfirma al empezar la Fase 8 con la validación descrita; hasta entonces es
  una propuesta `[POR VALIDAR con TI]`.
