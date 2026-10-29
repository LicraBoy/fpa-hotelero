# Handoff — Budget Studio: seguir con las demás secciones

Pegar al iniciar un chat nuevo (proyecto fpa-hotelero).

## Quién y qué
Proyecto **fpa-hotelero** (FP&A Torres Mazatlán). Backend FastAPI + SQLAlchemy + SQLite (`backend/fpa_dev.db`) + Alembic; frontend React 19 + TypeScript + Vite (CSS con tokens `--ref-*`). Rama de trabajo: `feat/budget-studio-redesign` (último commit `653fac6`, ya en GitHub; el repo es **público**, así que nunca se suben bases `.db`, Excel ni capturas con cifras reales). El **Contralor ya revisó y quedó enganchado con el sistema actual**: el objetivo es **replicar lo mismo, con la misma calidad y patrones**, en las siguientes secciones del Budget, sin romper lo ya aprobado.

Usuario: contralor/analista que dirige el trabajo. Respuestas **breves y en español**, explicando; sin saturar de detalle.

## Reglas permanentes
- **No hacer commit ni push** salvo que el usuario lo pida (y confirmar antes de subir; repo público).
- **Datos solo reales**: ausencia de dato nunca se convierte en cero; no inventar cifras.
- Sin `style=` en JSX, sin colores hex sueltos (usar tokens `--ref-*`), **sin dependencias nuevas**.
- No modificar la aritmética de `frontend/src/pantallas/budget/calculo.ts`; el dinero va en **micros (BigInt)**, nunca `number`.
- Antes de decir «listo»: `pytest` (backend), `npx tsc -b`, `npm run lint`, `npm run test:unit`, `npm run build` y Playwright (`FPA_CLAMAV_ACTIVO=false npx playwright test`). Reportar fallos con honestidad (hay uno intermitente ajeno: `seguridad.spec` drill-down).
- **Abrir yo mismo las capturas** y compararlas con el Excel; detener los servidores de captura (puertos 8102/5182) al terminar.
- Windows: usar scripts Python/Write en vez de heredocs con comillas mixtas; no matar todos los `python`/`node`.

## Vocabulario de pantallas (acordado con el Contralor)
**Hoja de sección** (cuentas × 12 meses + inflación + comparativos, `HojaSeccion.tsx`) → **Hoja de cuenta** (partidas × 12 meses, mismo componente con `modo='cuenta'`) → **Editor de partida** (`EditorPartida.tsx`: Cantidad, Unidad, Costo, Costo extendido = Cant. × Costo, reparto Mensual/Estacional). Las cuentas **sin** partidas van Hoja de sección → **Editor mensual** (`TablaInternaLinea.tsx`, base × factor / monto fijo). **Panel de línea** = panel lateral (propuesta, objetivo, notas). Un solo botón de regreso por pantalla.

## Qué ya está hecho (no rehacer)
- **Other Income**: sección con importador desde la hoja `Other Income` del Excel, Hoja de sección, Editor mensual, inflación **informativa** (no cambia el Budget), comparativos Est-Act / Budget previo.
- **Mgmt & Check In**: misma sección activada con `importar_seccion(..., seccion='mgmtcheckin')` leyendo `Budget 26-27 MZT` (código col B, descripción col C, meses D..O) + hojas del año previo (`EstAct 25-26 MZT`, `MZT Budget 25-26`) + **14 hojas de detalle `0111-NNNNN`** (Other Fringe, Training, Telephone, Airfare, Lodging, Mileage, Meals, Uniforms, Equipment, Materials/Supplies, Postage, Bank Commissions, T&E Local, Non-Deductible). Esas cuentas se capturan **por partidas** (tabla `Account Detail`: Item · Qty · Unit · Cost · Extended Cost · distribución Jul–Jun · inflación mensual) y **la inflación SÍ entra al Budget** (Budget del mes = distribución × (1 + inflación)). Σ extendido = `Total Expense` de cada hoja (verificado). Se quitó la columna «Distribución» (Monthly/Md Turn/Md Pts/Rm Night/Seasonal) de la tabla: **no la usan**.
- Botones: «Importar del Excel» (sección completa), «Importar partidas del Excel» (una cuenta, parámetro `linea_id`), «Detallar por partidas» (crea una partida «Importe actual»), «Quitar partidas».
- Base de datos de entrega: `Desktop\fpa_dev_ENTREGA.db` (migración 0025, 78 partidas).

## Dónde está el código (patrón a reutilizar)
Backend: `backend/fpa/ingesta/budget_seccion.py` (lee una sección de `Budget 26-27 MZT`; `DEPARTAMENTO_POR_SECCION = {"mgmtcheckin": "0111"}`), `budget_partidas.py` (lee hojas `NNNN-CCCCC Nombre`), `budget_other_income.py`; `backend/fpa/servicios/presupuesto_detalle.py` (`importar_seccion`, `ESTRICTAS`, `ALIAS_*`, `_importar_partidas`, `_linea_de_hoja` por código corporativo `-DDDD-CCCCC-`), `presupuesto_partidas.py`, `presupuesto_hoja.py`, `presupuesto_distribucion.py`; API `backend/fpa/api/v1/presupuesto.py` (`_SECCIONES_IMPORTABLES`, `/detalle/importar-other-income?seccion_id=&linea_id=`, `/lineas/{id}/hoja`, `/partidas`); modelos `modelos/presupuesto.py` (`PartidaLinea`, `PartidaMes`, `InflacionLineaMes`, `ReferenciaLineaMes`, `usa_partidas`); migraciones `0023`–`0025`.
Frontend: `frontend/src/pantallas/budget/componentes/{HojaSeccion,EditorPartida,TablaInternaLinea,TablaInflacion,AccionesInflacion}.tsx`, `partidas.ts` (+ `partidas.test.ts`), `PanelBudget.tsx`, `api/cliente.ts`, `estilos/hoja.css`.
Pruebas: `backend/tests/test_budget_seccion.py`, `test_presupuesto_partidas.py`, `test_budget_other_income.py`, `test_cadena_auditoria.py` (**toda ruta que escribe debe auditar o declararse en `DELEGAN_EN_SERVICIO`**); e2e `frontend/e2e/zz_tabla_interna.spec.ts` (corre al final), fixtures sintéticos `backend/scripts/crear_archivos_e2e.py`; capturas reales `frontend/capturas/*.spec.ts` con `playwright.captura.config.ts` (copia de la BD en 8102/5182).

## El proceso que seguimos para cada sección (repetirlo)
1. **Mapear las cuentas**: la estructura del reporte (`linea_reporte`, versión 2) ya trae las secciones y líneas con código corporativo `028-DDDD-CCCCC-000`. Para la sección nueva, comparar nombre a nombre las cuentas del Excel (`Budget 26-27 MZT`) con las líneas del reporte; las diferencias de nombre se resuelven con un **alias confirmado por el Contralor** (como `ALIAS_MGMT_CHECKIN`), nunca por parecido (Other Income usa parecido ≥0.6; las demás secciones son **estrictas**).
2. **Leer el Excel de verdad** (solo lectura, `openpyxl`, `data_only=True`) y verificar contra los totales del propio libro antes de programar; reportar `#REF!`/celdas vacías como «quedan para captura», sin inventar.
3. **Activar la sección** (añadirla a `_SECCIONES_IMPORTABLES`, `DEPARTAMENTO_POR_SECCION`, alias y `seccionAdmitePartidas`), importar y mostrar con la **misma Hoja de sección**.
4. **Detectar cuentas con hoja de detalle** (`NNNN-CCCCC …`): se importan por partidas con inflación incluida; las demás quedan con Editor mensual y botón «Detallar por partidas».
5. Pruebas (backend, unitarias, e2e), **captura real con el Excel** y comparación visual contra la hoja del Excel; luego respaldo de la BD antes de importar en la real.

## Lo que sigue (a confirmar con el usuario en el chat nuevo)
Secciones de `Budget 26-27 MZT` aún sin activar, en este orden del reporte: **Accounting, Maid & Linen, Apartment Interior, Common Area, Utilities, Owner Activities, Other Taxes/Fees/Insurance, Owner Services, VDS Allocation Collections, Purchasing**, luego Commercial Services (Telephones, Travel Agency, Store, Cafeteria, Bar, Money Exchange, Restaurant), Legal e IT Systems. Las hojas de detalle del libro están por departamento (`0101, 0103, 0106, 0108, 0109, 0114, 0115, 0118, 0120, 0122, 0124, 0128, 0130, 1136`; `0111` = Mgmt ya hecho): **hay que mapear qué departamento corresponde a cada sección**. Salaries / Seniority Premium (Mgmt) no tienen hoja de detalle (la nómina está en `05. A Staff`): pendiente aparte. Algunas hojas traen estructura distinta (p. ej. `0106-61440 Diesel` sin encabezado «Item»; `Uniforms` vacías; métodos Md Turn / Rm Night) y requerirán decisiones.

## Primer paso sugerido
## Primer paso sugerido
Preguntar al usuario **qué sección sigue** y hacer en modo solo lectura el mapeo cuenta por cuenta (Excel ↔ estructura del reporte) antes de escribir código.

