# CLAUDE.md — Plataforma FP&A e Inteligencia Hotelera (Torres Mazatlán)

Puerta de entrada para cualquier sesión nueva. Repositorio: `C:\Users\mzamora\Desktop\fpa-hotelero`.

## Qué es el proyecto
Plataforma SaaS de FP&A para hoteles, independiente de PMS/ERP/POS. Primer hotel: **Torres Mazatlán**; después **Puerto Vallarta**. Núcleo del MVP: **Actual vs Budget, Variance, YTD, Annual Budget, comentarios y drill-down**. Board y el caso Scandic son solo *referencia funcional*: no se copia su código, interfaz, textos ni modelos.

## Lee esto primero, en orden
1. `docs/ESTADO_DEL_PROYECTO.md` — en qué fase va el proyecto y qué sigue.
2. `docs/Arquitectura_Tecnica_FPA_Hotelero.md` — stack, arquitectura, seguridad, pruebas y fases (0 a 14).
3. `docs/FASES_FUTURAS.md` — resumen de las fases que faltan (2 a 15), con sub-fases, pruebas y decisiones pendientes.
   `docs/CAMBIOS_FUTUROS_DE_TECNOLOGIA.md` — qué es provisional hoy y cómo cambiará (base de datos, Docker, autenticación, etc.).
4. `docs/Blueprint_Funcional_FPA_Hotelero_Torres_Mazatlan.docx` — requisitos funcionales aprobados por Contraloría.
5. `docs/Especificacion_Redisenio_Budget_Studio.md` y `docs/Correccion_Visual_Budget_Studio.md` — especificación y corrección visual del rediseño de Budget Studio (referencia SaaS de alta fidelidad).
6. `docs/contexto.md` — requerimientos originales. Decisiones técnicas en `docs/adr/`.

## Cómo correrlo
- Levantar todo: `iniciar_servidores.bat` (backend **8100**, frontend **5180**; no usar 8000/5173, son de otro sistema).
- Pruebas backend: `cd backend` y `.venv\Scripts\python -m pytest`. Calidad: `.venv\Scripts\ruff check .`, `.venv\Scripts\ruff format --check .` y `.venv\Scripts\mypy fpa` (deben quedar sin errores).
- Pruebas frontend: `cd frontend` y `npm.cmd run test:unit` (82 pruebas unitarias). Calidad y CSP: `npm.cmd run lint` (oxlint + `node scripts/verificar_seguridad.mjs`). Compilación: `npm.cmd run build` (tsc + vite).
- Pruebas de navegador / E2E: `cd frontend` y `npm.cmd run e2e` (Playwright; corre contra el build de producción con su CSP estricta). Siempre correrlas al tocar pantallas. Si cambias la API: `npm run api:tipos` y commitea `src/api/openapi.json` y `schema.d.ts` (una prueba del backend lo exige).
- Base de datos: `.venv\Scripts\alembic upgrade head` (migraciones) y `.venv\Scripts\python -m fpa.semilla` (datos de desarrollo). Si cambias un modelo, genera la migración con `alembic revision --autogenerate`.
- Identidad de desarrollo: `FPA_ENTORNO=desarrollo` y cabecera `X-Usuario-Dev: analista@torres.local` (por defecto el entorno es `produccion` y nadie entra).
- Primera vez: ver `README.md`.

## Reglas de trabajo
- **Nada de `float` para dinero**: `Decimal` en Python y `NUMERIC(18,2)` en base de datos; en frontend `BigInt` (micros) vía `util/dinero.ts` y `calculo.ts`, nunca `number` para almacenar o calcular importes.
- El cálculo financiero es **puro y determinístico**; la IA nunca calcula cifras.
- **Cero estilos en línea**: Prohibido `style="..."` o `style={{...}}` en frontend (verificado automáticamente por `scripts/verificar_seguridad.mjs` bajo política CSP estricta).
- Stack actual **mínimo**: Python + FastAPI + SQLite (pruebas) y React + TypeScript + Vite + Plotly (lazy load). Las tecnologías nuevas (PostgreSQL, Docker, CI, OIDC, Playwright…) se hablan con TI antes de adoptarlas; el plan está en `docs/CAMBIOS_FUTUROS_DE_TECNOLOGIA.md`.
- No escribir SQL propio de un solo motor: todo acceso a datos pasa por SQLAlchemy.
- Seguridad por defecto: deny by default, aislamiento por organización y hotel, sin secretos ni datos reales de Torres en el repositorio.
- **No inventar procesos de Torres.** Marcar lo no confirmado como `[POR VALIDAR]`.
- El trabajo se hace **por fases**; no se abre una fase sin cerrar la anterior.
- **Una sub-fase no termina hasta actualizar `docs/ESTADO_DEL_PROYECTO.md`** y marcarla en la arquitectura.
- Git: **un commit por sub-fase** terminada, con mensaje en español. No subir a ningún servidor sin pedirlo.
- Respuestas al usuario: cortas y claras, en español.
- Este proyecto es independiente de `DataContabilidad\sistema-analisis-contable`; no usarlo como evidencia ni modificarlo.

## Datos de Torres (fuera del repositorio, solo lectura)
Carpeta: `C:\Users\mzamora\Desktop\PLATAFORMA FP&A E INTELIGENCIA HOTELERA\`. No copiar nada de ahí al repositorio.
- `BASE DATOS.xlsx` — reporte CON130 de Novohit, septiembre 2026 (7,242 movimientos, 366 cuentas, Débito = Crédito = 57,835,193.08).
- `02. VT August 2026 Variance (Envio) (1).xlsx` — Variance de agosto 2026 de **Puerto Vallarta** (hasta la 4.8 se creyó de Mazatlán): hoy solo **regresión del formato VT**.
- `02. MZT August 2026 Variance (Envio).xlsx` (los Excel reales viven fuera del repo, en `FPA_DATOS_REALES` o `Desktop/PLATAFORMA FP&A E INTELIGENCIA HOTELERA`; ver `fpa/datos_reales.py`) — Variance de **Mazatlán** (julio y agosto 2026): **prueba dorada del MVP** desde la 4.9 (`.xlsx` no se versiona; recomendado moverlo fuera del repositorio).
- `Prompt_Integracion_Variance.docx` — los 14 pasos manuales que la plataforma reemplaza.

## Código existente y estado de módulos
- `backend/fpa/ingesta/` — lectores de CON130, Variance y catálogo CON020 en `.xls`.
- `backend/fpa/api/v1/` — rutas de salud, cargas, catálogo, saldos, variance y presupuestos (`presupuesto.py`, `presupuesto_captura.py`).
- **Módulo Variance** (`frontend/src/pantallas/variance/`): Reporte con desglose por cursor, exportación a Excel, caché y drill-down contable.
- **Módulo Budget Studio** (`frontend/src/pantallas/budget/` en rama `feat/budget-studio-redesign`):
  - **Cabecera y Ciclo de Gobernanza**: `BudgetHeader.tsx` (año fiscal, versión oficial) y `CicloPresupuesto.tsx` (stepper Borrador → Enviado → Revisión → Aprobado, transiciones por rol, bitácora y donut de cobertura).
  - **Pestaña Resumen (Dashboard Analítico)** (`BudgetResumen.tsx`):
    - Franja de 5 KPIs con micro-sparklines vectoriales SVG y paleta cromática individualizada (`BudgetKpiStrip.tsx`).
    - Gráfico agrupado Objetivo vs. Propuesta por departamento con escala en millones y etiquetas superiores (`BudgetObjetivoVsPropuestaChart.tsx`).
    - Top 5 variaciones con píldoras de estado (`BudgetPrincipalesDiferencias.tsx`).
    - Resumen del ciclo con checklist de próximas acciones (`BudgetResumenCiclo.tsx`).
    - Distribución mensual multi-trazo en Plotly (barras por trimestre + curva spline de tendencia con marcadores y área sombreada; `BudgetDistribucionMensualChart.tsx`).
    - Perfil de temporada interactivo Plotly (`BudgetPerfilTemporada.tsx`).
    - Estructura del presupuesto (donut interactivo Plotly con pull effect, etiquetas externas y total central dinámico consolidado; `BudgetComposicionChart.tsx`).
    - Tarjeta explicativa del flujo presupuestario (`BudgetComoFunciona.tsx`) y accesos directos (`BudgetAccionesRapidas.tsx`).
    - Hook de paleta coordinada claro/oscuro (`useColoresTema.ts`).
  - **Pestaña Captura**: Edición mensual celda a celda en 12 meses fiscales, cálculo en tiempo real de subtotales, prorrateo con perfiles estacionales, copia de Actual con ajuste %, vista tabla completa y vista split árbol/detalle (`ArbolLineas.tsx`, `DetalleCapturaLinea.tsx`).
  - **Pestaña Versiones**: Historial cronológico inmutable (time machine) y comparador de versiones con diff porcentual (`BudgetVersionesTab.tsx`, `BudgetComparacionVersiones.tsx`).
  - **Estilos y Layout**: `frontend/src/estilos/budget.css` y `layout.css`, completamente desacoplados de Variance, con grid responsive (5 cols desktop, 3 laptop, 2 tablet, 1 móvil) y soporte de tema oscuro.
- **Progreso del rediseño de Budget Studio**:
  - Etapa 1 (Fundamentos y layout): **Completada**.
  - Etapa 2 (Cabecera y ciclo presupuestario): **Completada**.
  - Etapa 3 (Dashboard analítico y gráficos avanzados): **Completada y auditada** (validada en 1440px, 1280px, 768px, 390px y tema oscuro; 82/82 tests unitarios pasando, 0 errores de linter/CSP, build exitoso).
  - **Próxima etapa pendiente en el roadmap**: **Etapa 4 — Versiones, auditoría y pulido** (timeline en solo lectura, comparación entre versiones, auditoría de accesibilidad/skeletons y pruebas de regresión).
