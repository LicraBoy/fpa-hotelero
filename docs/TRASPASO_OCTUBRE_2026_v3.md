# Traspaso para continuar en otro chat (24-oct-2026)

Pega esto (o dile al asistente que lo lea) al empezar el chat nuevo. Repositorio:
`C:\Users\mzamora\Desktop\fpa-hotelero`, rama **`feat/budget-studio-redesign`** (ya subida a GitHub,
`origin/feat/budget-studio-redesign`, sin Pull Request abierto todavía), último commit `03d567a`,
árbol limpio. **Este documento reemplaza a `docs/TRASPASO_OCTUBRE_2026_v2.md` (ya desactualizado —
Budget Studio, que ahí estaba solo "diseñado", ya está programado y commiteado).**

**Decisión explícita del usuario (24-oct-2026): no abrir la Fase 8 todavía.** Antes necesita (1) la
revisión y aprobación del Contralor sobre lo ya construido (Budget Studio y el mapeo pendiente de
Fase 2/6.7) y (2) su propia revisión. Esta condición es una decisión de esta sesión, **no está
escrita en `FASES_FUTURAS.md` ni en ningún ADR** — queda documentada aquí para que el siguiente chat
no proponga saltar a Fase 8 sin pedir primero esas dos revisiones.

## 1. Qué pasó desde el traspaso anterior (v2, 22-oct-2026)

- **Budget Studio (Fase 7) se programó por completo**, en la rama `feat/budget-studio-redesign`
  (nunca se tocó `main`, que sigue en `3350057`). Dos tandas de trabajo:
  - Ciclo de presupuesto (captura por sección, objetivo, prorrateo con perfiles, aprobación →
    `VersionPlan`), shell con pestañas Resumen/Captura/Versiones, KPIs, gráficas Plotly reales
    (Objetivo vs. Propuesta, Distribución mensual, Composición por sección), árbol de líneas +
    detalle, perfiles con vista previa exacta (mismo algoritmo de redondeo que el backend,
    verificado byte a byte), timeline de versiones de solo lectura.
  - Una auditoría correctiva propia encontró y corrigió 2 defectos reales: el comparador de
    versiones no avisaba si las dos versiones comparadas eran de **ejercicios fiscales distintos**
    (corregido: aviso visible + año fiscal en los selectores) y 3 chips de estado no cumplían
    contraste WCAG 2.1 AA en tema claro (corregido: 3 colores de texto, de 3.37-4.37:1 a
    4.90-5.67:1, verificado con la fórmula de luminancia relativa, no a ojo).
- **86/86 pruebas unitarias de frontend, build y lint limpios.** Backend: **862 passed, 2 skipped**
  (suite completa, no solo lo de Budget), `mypy` limpio. **Un hallazgo menor sin corregir**: `ruff
  check` marca una línea de 103 caracteres (límite 100) en
  `backend/fpa/servicios/presupuesto_captura.py:326` — cosmético, no afecta funcionalidad, queda
  pendiente de un arreglo de una línea.
- Commit y push ya hechos (`03d567a`), con autorización explícita del usuario. No se abrió Pull
  Request (no se pidió).

## 2. Auditoría de roadmap hecha en esta sesión (24-oct-2026)

Se le pidió a dos sub-agentes en paralelo: uno leyó completos los documentos maestros
(`docs/Arquitectura_Tecnica_FPA_Hotelero.md`, `docs/ESTADO_DEL_PROYECTO.md`,
`docs/FASES_FUTURAS.md`, este traspaso), el otro buscó evidencia real de código para Rolling
Forecast, Drivers/Escenarios y Cash Flow, y corrió toda la suite de pruebas. Hallazgos:

**`docs/ESTADO_DEL_PROYECTO.md` está obsoleto** — todavía dice "Fases 6 a 14: Pendientes", pero la
Fase 6 (salvo 6.2 pentest y 6.7 acta de Contraloría) y la Fase 7 completa ya existen en código. El
documento confiable es **`docs/FASES_FUTURAS.md` (22-oct-2026)**, y ni siquiera ese sabe todavía que
Budget ya se programó (lo marca `[PENDIENTE]`). **Recomendación para el próximo chat: actualizar
`docs/ESTADO_DEL_PROYECTO.md` y la entrada de Fase 7 en `FASES_FUTURAS.md` antes de seguir, para que
dejen de contradecir el estado real del repo.**

### Matriz de fases (numeración confirmada igual en los 3 documentos, sin contradicción entre ellos)

| Fase | Objetivo | Estado real | Evidencia | Depende de |
|---|---|---|---|---|
| 1 | Data Hub: Actuals | **Completa** | `backend/fpa/ingesta/` — 8 lectores reales (CON130, CON020, Variance en sus formatos); `backend/fpa/calculo/` — motor, actual, totales, YTD, variance | — |
| 2 | Catálogo corporativo y mapeo | **Casi completa** | Mapeo v7 (715 vínculos) ya aplicado; **falta que el Contralor lo revise y confirme** | 1 |
| 3 | Motor de Variance | Completa | — | 2 |
| 4 | Reporting y frontend | Completa | Pantalla Variance | 3 |
| 5 | Comentarios, workflow, roles, auditoría | Completa | Módulo de seguridad/permisos ya en uso | 4 |
| 6 | Endurecimiento y piloto | **Casi cerrada** | Todo hecho salvo 6.2 (pentest, externo) y 6.7 (acta de aceptación del Contralor — **mismo prerrequisito que la Fase 2**) | 5 |
| **7** | **Budget en la plataforma** | **Completa, programada y commiteada** (esta sesión) — **ningún documento de roadmap lo sabe todavía** | `backend/fpa/servicios/{budget,budget_edicion,presupuesto_captura,presupuesto_ciclo,presupuesto_distribucion}.py`; `frontend/src/pantallas/budget/`; 862+86 pruebas | 6 (abierta en paralelo por decisión previa del usuario, sin esperar 6.2/6.7) |
| **8** | **Forecast y rolling forecast** | **0% — sin código, sin pruebas, sin pantallas** | Búsqueda exhaustiva de "forecast"/"rolling" en todo el repo: cero coincidencias reales | **7** (lista) + Contraloría debe confirmar año fiscal y horizonte del forecast (decisión pendiente, documentada en `FASES_FUTURAS.md`) |
| 9 | Drivers y escenarios | **0% — sin código, sin pruebas, sin pantallas** | Búsqueda exhaustiva: cero coincidencias reales | 8 + fuentes operativas (PMS/Cloudbeds, condicional — ver `docs/Anexo_Futuro_Capa_Datos_Operativos_Hoteleros.md`) |
| 10 | Cash Flow | **0% — sin código, sin pruebas, sin pantallas** | Búsqueda exhaustiva: cero coincidencias reales | 8 + datos de cuentas por cobrar/pagar |
| 11 a 15 | (detalle en `FASES_FUTURAS.md`) | Pendientes | — | — |

**Fase 8, qué es exactamente** (texto de `FASES_FUTURAS.md`): "una visión actualizada del cierre del
año, cada mes". Sub-fases 8.1 (versión de forecast), 8.2 (cierre mensual sustituye forecast por
actual), 8.3 (comparativos). Debe ser rolling de 12 meses **continuos**, distinguiendo **cuatro**
conceptos a la vez: Budget, Forecast vigente, Forecast anterior (se conserva, nunca se sobrescribe)
y Actual — mismo principio de versionado inmutable que ya se implementó para Budget (`VersionPlan`),
pero **extendido**, no reusado literalmente (el modelo de Forecast todavía no existe).

### Riesgos de abrir la Fase 8 antes de tiempo

1. **Depende de que el Contralor confirme el año fiscal y el horizonte del forecast** — sin eso,
   cualquier modelo de `PeriodoForecast` que se diseñe hoy es una suposición, exactamente el tipo de
   invención que las reglas del proyecto prohíben ("No inventar procesos de Torres").
2. **Fase 2/6.7 (revisión del mapeo por Contraloría) sigue sin cerrar.** Si el mapeo cambia después
   de empezar Forecast, los `Actual` que usa el comparativo rolling quedarían calculados con cuentas
   mal mapeadas — mismo riesgo que ya se documentó para Fase 7 en el traspaso anterior, y la razón
   por la que esta vez el usuario sí quiere esperar antes de abrir una fase nueva.
3. **Budget Studio (Fase 7) todavía no tiene su propia revisión de Contraloría/Dirección** — es la
   fuente de uno de los 4 conceptos que Forecast necesita mostrar lado a lado; si algo cambia en
   Budget tras su revisión (p. ej. el significado de "objetivo" o el flujo de aprobación), Forecast
   heredaría ese cambio a medio construir.

## 3. Qué sigue, en el orden que pidió el usuario

**No se abre ninguna fase todavía.** Lo que falta antes, en orden:

1. **Revisión del Contralor** sobre Budget Studio (Fase 7, recién terminada) y sobre el mapeo v7
   pendiente desde la Fase 2/6.7 — ambas revisiones ya estaban bloqueadas desde el traspaso anterior
   por la misma persona, tiene sentido pedirlas juntas.
2. **Revisión propia del usuario** sobre el resultado de Budget Studio (probarlo en el navegador,
   confirmar que el flujo de captura por departamento y el ciclo de aprobación son los que Torres
   necesita).
3. Solo después de (1) y (2): decidir si se abre la Fase 8, y si es así, pedir primero a
   Contraloría que confirme año fiscal y horizonte del forecast (la decisión pendiente ya
   documentada), para no repetir el patrón de "Fase 7 diseñada antes de tener las respuestas".

**Mientras tanto, limpieza de bajo riesgo que se puede hacer sin abrir fase nueva** (opcional, no
pedida explícitamente):
- Arreglar la línea de 103 caracteres en `presupuesto_captura.py:326` (un solo ajuste de formato).
- Actualizar `docs/ESTADO_DEL_PROYECTO.md` y la entrada de Fase 7 en `docs/FASES_FUTURAS.md` para
  que reflejen que Budget ya está programado (hoy ambos documentos siguen desactualizados sobre
  esto, como se explica en §2).
- Decidir si abrir un Pull Request de `feat/budget-studio-redesign` hacia `main` (no se hizo en esta
  sesión porque no se pidió).

## 4. Qué es el proyecto (sin cambios respecto a v2)

Plataforma SaaS de FP&A hotelero, independiente de PMS/ERP/POS. Primer hotel: Torres Mazatlán.
Backend FastAPI + SQLAlchemy 2 + SQLite (Postgres ya soportado en pruebas) + Alembic (puerto 8100);
frontend React 19 + TS + Vite (puerto 5180), sin librería de UI. Ver `docs/contexto.md` y
`docs/Blueprint_Funcional_FPA_Hotelero_Torres_Mazatlan.docx` para el detalle funcional aprobado por
Contraloría, y `docs/adr/` para las decisiones técnicas.
