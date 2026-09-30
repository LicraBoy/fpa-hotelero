# Arranque de la Fase 2 (para abrir en un chat nuevo)

Fecha de cierre de la Fase 1: 30-sep-2026. Último commit de la Fase 1: ver `git log` ("Catálogo oficial acumulativo entre meses").

## Prompt para pegar en el chat nuevo
> Lee `CLAUDE.md`, `docs/ESTADO_DEL_PROYECTO.md`, `docs/FASES_FUTURAS.md` (sección Fase 2) y `docs/ARRANQUE_FASE_2.md`. Vamos a empezar la **Fase 2 — Catálogo corporativo y mapeo**, sub-fase 2.1. Trabaja por sub-fases con pruebas, ruff + mypy limpios, un commit por sub-fase, docs actualizados al cerrar cada una, respuestas cortas en español. Antes de codificar, revisa el Excel `02. VT August 2026 Variance (Envio) (1).xlsx` (hoja `Ago`) y propón el modelo de datos.

## Estado verificado al cierre de la Fase 1
- 240 pruebas de backend pasan (1 se salta: PostgreSQL), 11 de Playwright, ruff/mypy/build/lint limpios.
- Verificado con los Excel reales: CON130 septiembre (7,242 movimientos, Débito = Crédito = 57,835,193.08), Variance julio+agosto (6,860), catálogo CON020 (1,238 cuentas, 68 títulos).
- El frontend es **provisional** (solo para probar la Fase 1); el diseño real llega en fases de reporte.

## Dónde están los archivos reales (no están en el repo)
Carpeta `C:\Users\mzamora\Desktop\PLATAFORMA FP&A E INTELIGENCIA HOTELERA`: Variance de agosto (hoja `Ago`, mapeo en columnas X a AJ), `BASE DATOS.xlsx` (CON130 sept), `Catalogo de cuentas.xls`, Blueprint y prompt del contralor. Las pruebas con archivos reales se saltan si no existen (variable `FPA_DATOS_REALES`).

## Lo que la Fase 2 debe hacer (resumen)
2.1 estructura del reporte (secciones, líneas, orden, tipo) desde la hoja `Ago` · 2.2 reglas de suma (totales) · 2.3 mapeo línea ↔ cuentas con signo · 2.4 validación del mapeo · 2.5 versionado · 2.6 API. Criterios en `docs/FASES_FUTURAS.md`.

## Decisiones ya tomadas que NO se reabren
- Signo = naturaleza de la cuenta (TIPO del catálogo): Acreedor resta, Deudor suma (validado 203/203 con el Excel; falta confirmación formal).
- Departamentos = grupos de 4 dígitos de la clase 6; `DEPTO EdoFro` los confirma.
- Catálogo por hotel y acumulativo entre meses; Puerto Vallarta copia el de Torres (Fase 11).
- El Saldo anterior del CON130 no se usa. Dinero con `Dinero` (Decimal, 2 decimales), nunca float.
- Aislamiento por hotel (404 hotel ajeno, 403 sin permiso, 401 sin sesión). Repos siempre filtran por `hotel_id`.
- Una carga vigente por (hotel, periodo); idempotencia por SHA-256; auditoría insert-only.
- Ruff + mypy estricto; un commit por sub-fase; ningún Excel real en el repo.

## Preguntas abiertas para Contraloría (no bloquean 2.1)
1. Clave única de una línea del Variance (una cuenta corporativa aparece en varias líneas).
2. Origen del Budget (hoy viene pegado como valor).
3. Confirmar signo del Variance (favorable positivo; ingresos Actual−Budget, gastos Budget−Actual).
4. Por qué 87 cuentas del Variance no están en el catálogo de septiembre (ahora se acumulan al importar otros meses).
5. Significado de `Aux = S` y `DPTO. TI`; fila 4389 "INCENTIVOS CHEF" (¿cero o dato faltante?); año fiscal (¿jul–jun?); catálogo de Puerto Vallarta.

## Cómo levantar todo
`iniciar_servidores.bat` (migra, siembra, API en 8100 y web en 5180). Pruebas: `cd backend` → `.venv\Scripts\python -m pytest`. E2E: `cd frontend` → `npm run e2e`.
