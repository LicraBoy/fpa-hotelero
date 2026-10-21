# Traspaso para continuar en otro chat (21-oct-2026)

Pega esto (o dile al asistente que lo lea) al empezar el chat nuevo. Repositorio:
`C:\Users\mzamora\Desktop\fpa-hotelero`, rama `main`, último commit `e7e540c`, árbol limpio.

## 1. Decisión del usuario sobre cómo seguir
- **NO se inicia la Fase 6 hasta que Contraloría entregue el mapeo completo de cuentas.**
- Mientras tanto el usuario **trabaja en el frontend final** (lo va a cambiar). El backend no debe
  cambiar por eso: el contrato es el OpenAPI.
- Lo que sí puede avanzar sin Contraloría: documentación, el frontend, y las listas de cuentas que
  hay que completar (ver §5).

## 2. Qué es el proyecto
Plataforma FP&A para Torres Mazatlán (VI Resorts by Westgate), parte de una plataforma de
inteligencia integral para hoteles. **Independiente**: no sustituye PMS, ERP ni contabilidad; recibe
archivos (hoy el CON130 de Novohit, el catálogo CON020 y el Excel del Variance de Contraloría).
Visión completa y reglas (no inventar capacidades, la navegación no muestra módulos futuros):
`docs/VISION_DEL_PRODUCTO.md`. Contexto original: `docs/contexto.md`.

**Pila:** backend FastAPI + SQLAlchemy 2 + SQLite + Alembic (puerto 8100); frontend React 19 +
TypeScript + Vite (puerto 5180); pruebas de navegador con Playwright (API 8101, web 5181 por
omisión). Python con `backend\.venv`.

**Reglas del repositorio (se cumplen siempre):** dinero en `Decimal`/BigInt, nunca `float`; cálculo
puro (los servicios no tocan la base, el router consulta y los llama); un commit por sub-fase en
español terminando con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; `ruff check`,
`ruff format`, `mypy fpa`, `pytest`, `npm run lint`, `npm run build`, `npm run test:unit` y las e2e
limpios antes de commitear; docs actualizados en cada sub-fase; lo no confirmado se marca
`[POR VALIDAR]`; sin Excel reales en el repo; repositorios siempre por `hotel_id`; permisos con
`hotel_autorizado(Permiso.X)` y `auditar` en toda escritura (una prueba lo exige); `get_db` no hace
commit: cada endpoint que escribe hace `db.commit()` y lo que deba sobrevivir a un error se
confirma antes de lanzar la excepción.
El otro repositorio `sistema-analisis-contable` es independiente: **no usarlo como evidencia**.

## 3. Estado de las fases
| Fase | Estado |
|---|---|
| 0 a 4 | Hechas (Data Hub, catálogo y mapeo, motor de Variance, reporting y frontend) |
| **5** | **Código listo** (5.1 a 5.5); 5.6 notificaciones diferida (requiere correo de TI) |
| 6 a 14 | Pendientes (`docs/FASES_FUTURAS.md`) |

Fase 5 en una línea cada una (detalle en `docs/ESTADO_DEL_PROYECTO.md`):
- **5.1 Identidad:** usuarios locales con `argon2id`, TOTP opcional y sesión en cookie `HttpOnly`
  (ADR 0005). Bloqueo a los 5 intentos. CSRF por `Origin`. Migración `0016`.
- **5.2 Roles:** permisos nuevos, secciones del Variance asignadas al Responsable de departamento
  (guardadas por nombre), pantalla Usuarios. Migración `0017`.
- **5.3 Comentarios:** por línea+periodo+bloque, hilo, estatus, responsable, evidencia (PDF, PNG, JPG,
  .xlsx), columnas COMMENTS del Excel. Migración `0018`.
- **5.4 Cierre:** Borrador → Comentado → Revisado → Aprobado → Bloqueado; al aprobar se congelan
  mapeo, Budget, estructura, cargas (con hash) y huella de cifras; candado de recargas. Migración
  `0019`.
- **5.5 Auditoría:** bitácora con hash encadenado por organización, `GET /auditoria/verificar`,
  historial de la cifra (ADR 0006). Migración `0020`.
- **Después de la Fase 5:** vista **«Por departamento»** (importes por `depto_ef` y `grupo_ef` del
  catálogo Novohit) y **rediseño de navegación** (catálogo único `frontend/src/ruta/navegacion.ts`,
  una ruta por pantalla, menú de usuario, CSS dividido en `frontend/src/estilos/`).

**Verificación al cierre:** `pytest` 778 pasaron y 2 se omiten; e2e 95; unitarias 63; ruff, mypy, lint y
build limpios. Migraciones hasta `0020` (base de desarrollo en `0020`).
**Ramas:** todas fusionadas en `main` (avance rápido); quedan sin borrar `fase-5-workflow`,
`fase-departamentos`, `mapeo-mgmt-checkin`, `ui/rediseno-frontend`, `ui/rediseno-navegacion`. No hay
remoto configurado: nada se ha subido a ningún lado.

## 4. Documentos que leer primero (en este orden)
1. `docs/TRASPASO_OCTUBRE_2026.md` (este)
2. `docs/ESTADO_DEL_PROYECTO.md` (estado por fase y decisiones)
3. `docs/RESUMEN_DEL_FRONTEND.md` (todo lo que hace la interfaz hoy y sus límites)
4. `docs/VISION_DEL_PRODUCTO.md` y `docs/FASES_FUTURAS.md`
5. Según la tarea: `docs/FORMULAS_Y_REGLAS_DEL_VARIANCE.md`, `docs/PREGUNTAS_PARA_CONTRALORIA.md`,
   `docs/adr/0001` a `0007`, `docs/CAMBIOS_FUTUROS_DE_TECNOLOGIA.md`.

## 5. Pendiente (lo que bloquea o falta; no es código)
**De Contraloría (bloquea la Fase 6):**
- **Mapeo completo de cuentas** (sub-fase 4.13d). Contraloría ya lo está trabajando. Hoy la versión 4
  del mapeo de Mgmt & Check In está aprobada en la base de desarrollo; faltan las demás secciones.
- Observaciones sobre **septiembre** (4.13b).
- **Preguntas abiertas P19 a P26** (`docs/PREGUNTAS_PARA_CONTRALORIA.md`): CON130 de julio y agosto,
  fórmula del IVA de julio, captura de ~150 líneas sin cuentas, mapeo v4, **roles y secciones (P23)**,
  **comentarios (P24)**, **cierre (P25)**, **departamentos de las cuentas (P26)**.
- Los 5 roles, los estados del cierre y los umbrales deben validarse antes de dar la Fase 5 por
  completa.

**Hallazgo de datos (P26):** en septiembre, 354 de 574 cuentas vinculadas no traen departamento ni
tipo en el catálogo de Novohit (incluye el ingreso principal, 4xxx); varios departamentos muestran
gasto de operación negativo (HOUSEKEEPING, ACCOUNTING, PURCH-WHAREHOU) y los nombres vienen
abreviados. Idea pendiente: Excel descargable con esas cuentas (código, nombre, importe) para que las
completen en Novohit.

**De TI:** avisar que el login usa dos dependencias nuevas, `argon2-cffi` y `pyotp` (ADR 0005); sin
HTTPS en la red interna hay que poner `FPA_COOKIE_SEGURA=false` (menos seguro).

**Del usuario:** abrir el Excel exportado del Variance en Excel real (nunca se ha abierto fuera de
las pruebas); decidir si se borran las ramas ya fusionadas.

## 6. Frontend final (lo que el usuario hará ahora)
- **Qué existe hoy:** `docs/RESUMEN_DEL_FRONTEND.md` (React 19 + TS + Vite, sin librería de UI, ~7 600
  líneas, 9 pantallas, tema claro/oscuro).
- **Se puede cambiar sin tocar el backend:** todo el frontend. El contrato es el OpenAPI; los tipos
  se regeneran con `npm run api:tipos` (en `frontend/`) y una prueba del backend falla si
  `frontend/src/api/openapi.json` se desvía de la API.
- **Debe conservarse:**
  - **CSP estricta** sin estilos ni scripts en línea (`scripts/verificar_seguridad.mjs`, dentro de
    `npm run lint`); sin `dangerouslySetInnerHTML`, `innerHTML` ni `eval`.
  - **Ninguna credencial en el navegador:** la sesión es cookie `HttpOnly`; solo preferencias en
    `sessionStorage` (`src/util/preferencias.ts`).
  - **Todo texto de archivos o personas se muestra como texto.**
  - **Permisos:** el servidor decide siempre; `src/permisos.ts` solo decide qué mostrar.
  - **Nombres accesibles que usan las e2e** (si se renombran hay que actualizar las pruebas):
    `navigation` «Secciones» y «Ubicación», grupos «Finanzas», «Datos», «Administración»,
    regiones «Variance», «Cargas», «Subir archivo», «Cierre del periodo», «Tabla de Variance»,
    botones «Menú de usuario», «Mi cuenta», «Cerrar sesión», «Probar inicio de sesión real»,
    encabezados «Bitácora de auditoría», «Usuarios», «Por departamento», etc.
- **Dirección visual propuesta** (no implementada): lienzo en
  https://claude.ai/artifact/DztMYBqn44FXJ1eWRQ6ide (privado). Sobrio, fondo gris claro, superficies
  blancas con bordes de 1 px, un acento verde azulado `#0B6E5F`, favorable `#067647` y desfavorable
  `#B42318` siempre con flecha y signo, Inter con cifras tabulares.
- **Tecnología recomendada** (a decidir por el usuario): Tailwind CSS v4 + shadcn/ui (Radix) +
  TanStack Table para el Variance + ECharts; Lucide para iconos. **Evitar** CSS-in-JS en tiempo de
  ejecución (MUI/Emotion, Mantine) por la CSP.
- **Plotly:** el usuario quiere `plotly.js` (MIT) para análisis, **más adelante**. Antes de adoptarlo
  hay que probar que funciona con la CSP estricta (inyecta estilos); alternativa: ECharts. El usuario
  mostró como referencia visual https://financial-dashboard-example.plotly.app/ (no se pudo ver: carga
  con JavaScript; pedirle una captura).
- **Plan de migración sugerido:** primero una prueba pequeña de la tecnología, luego Variance, luego
  el resto pantalla por pantalla; las e2e y la comparación de estilos protegen contra roturas.

## 7. Librerías de datos para después (ADR 0007, propuesta)
Dinero oficial siempre en `Decimal`. Fase 7 (Budget): Python estándar. Fase 8 (Forecast): pandas 3 +
statsmodels y/o statsforecast, elegido con validación de origen móvil sobre datos reales. Fase 9:
NumPy, SciPy. Fase 12: scikit-learn (LightGBM solo con datos suficientes). Sin deep learning por
ahora. Nada se instala hasta la Fase 8.

## 8. Cómo operar
- **Arrancar:** `iniciar_servidores.bat` (en la raíz; abre dos ventanas y la app). Pedir al usuario que
  lo ejecute: **no abrir procesos ocultos** desde la herramienta ni matar todos los `python`/`node`.
  El backend corre con `--reload` (recarga solo al guardar), pero una migración nueva exige reiniciarlo.
- **Problema del entorno:** `backend\.venv` está basado en el Python de Microsoft Store, que a veces
  se cuelga. Solución recomendada: instalar Python de python.org (solo para el usuario) y recrear el
  venv. Puertos: 8100/5180 desarrollo; las e2e levantan su propia API en 8101 con base temporal.
  Si el puerto 5181 está ocupado: `FPA_E2E_WEB=5191 npx playwright test`.
- **Comandos** (desde `backend/`): `.venv\Scripts\pytest`, `.venv\Scripts\ruff check fpa tests`,
  `.venv\Scripts\ruff format fpa tests`, `.venv\Scripts\mypy fpa`, `.venv\Scripts\alembic upgrade head`.
  Desde `frontend/`: `npm run build`, `npm run lint`, `npm run test:unit`, `npm run api:tipos`,
  `npx playwright test`.
- **Antes de migrar la base de desarrollo** (`backend/fpa_dev.db`) copiarla con otro nombre
  (`fpa_dev_antes_00NN.db`; fuera de git por el patrón `*.db`).
- **Crear o restablecer un usuario real:** `backend\.venv\Scripts\python scripts\crear_contralor.py
  --email a@b.com --nombre "Nombre"` (imprime una contraseña temporal una sola vez); `--restablecer`
  para una existente.
- **Usuarios de desarrollo:** `contralor@`, `analista@`, `responsable@`, `direccion@`, `auditoria@`
  `torres.local` (selector del frontend en desarrollo).
- Flujo de trabajo de cada cambio grande: plan breve → implementar → pruebas → documentación →
  commit en español.

## 9. Preferencias del usuario
Respuestas **cortas y claras, en español**, sin saturar de detalle; mostrar resultados y decidir por
defecto lo razonable, pero **preguntar antes de lo que no se puede deshacer o sale del equipo** (subir a
un remoto, borrar ramas o datos). No inventar datos ni capacidades. Siente que la interfaz actual no
se ve profesional y quiere un diseño más moderno, con análisis profundo para decisiones (más
adelante).

## 10. Primer mensaje sugerido para el chat nuevo
«Lee `docs/TRASPASO_OCTUBRE_2026.md`, `docs/ESTADO_DEL_PROYECTO.md` y `docs/RESUMEN_DEL_FRONTEND.md`.
Estoy trabajando en el frontend final; no se inicia la Fase 6 hasta tener el mapeo completo de
Contraloría. Dime qué entendiste y ayúdame con: …»
