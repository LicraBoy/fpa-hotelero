# Arquitectura Técnica — Plataforma FP&A e Inteligencia Hotelera (Torres Mazatlán)

Versión 1.0 · 30-sep-2026 · Base: *Blueprint Funcional FP&A Hotelero v1.1* (aprobado por Contraloría)

**Cómo leer los estados**

| Etiqueta | Significado |
|---|---|
| `[DECIDIDO]` | Ya definido por el equipo o por Contraloría |
| `[PROPUESTA]` | Recomendación técnica con justificación; requiere visto bueno |
| `[POR VALIDAR]` | Depende de TI, Contraloría u otra área; se debe confirmar antes de construir |
| `[HECHO]` | Ya construido y probado |

---

## 1. Resumen ejecutivo

La plataforma es una aplicación web **full stack** (Python + React/TypeScript) sobre una base relacional, construida como **monolito modular**. Recibe movimientos contables de Novohit, los normaliza, aplica el mapeo de cuentas, calcula **Actual vs Budget, Variance, YTD y Annual Budget**, permite comentar y aprobar, y navega hasta el asiento (drill-down). Crece por fases hacia Budget en plataforma, Forecast, drivers, escenarios, cash flow, multi-hotel y, al final, IA gobernada.

Principios que gobiernan todas las decisiones:

1. **El dinero nunca es `float`.** Todo monto usa `Decimal` en Python y `NUMERIC(18,2)` en base de datos.
2. **El cálculo es determinístico y puro.** El motor financiero no toca la red, la base ni la interfaz: recibe datos y devuelve cifras. La IA jamás calcula cifras.
3. **Toda cifra es trazable**: fuente, versión de mapeo, versión de plan, fórmula, usuario y fecha.
4. **Aislamiento por organización y hotel desde el día uno**, aunque hoy solo exista Torres.
5. **Seguridad por defecto** (deny by default), no como capa final.
6. **Se prueba contra datos reales**: agosto 2026 (Variance) y septiembre 2026 (CON130) son pruebas doradas del MVP.

### Estado actual
| Pieza | Estado |
|---|---|
| Lector del reporte CON130 de Novohit (`plataforma_fpa/fpa/ingesta/novohit_con130.py`) | `[HECHO]` 13 pruebas pasan. Con septiembre 2026: 7,242 movimientos, 366 cuentas, Débito = Crédito = 57,835,193.08, las 366 cuentas cuadran con su fila "Total" |
| Todo lo demás | No iniciado |

---

## 2. Requisitos que condicionan la arquitectura

Tomados del blueprint (etiqueta original entre paréntesis).

| # | Requisito | Impacto técnico |
|---|---|---|
| R1 | Actuals salen del reporte CON130 de Novohit, cargado como Excel (PROCESO ACTUAL) | Ingesta por archivo con validaciones; conexión directa es futuro |
| R2 | El reporte no es tabular: intercala títulos, saldos anteriores, movimientos y totales | Lector con máquina de estados (ya construido) |
| R3 | El Actual de una línea del Variance = suma de N cuentas locales con signo; una cuenta local puede aparecer en más de una línea; una cuenta corporativa se repite en varias líneas | Tabla de mapeo N a N versionada; la clave de línea no es solo la cuenta corporativa |
| R4 | Año fiscal julio–junio, YTD = meses del año fiscal hasta el corte (HP: por confirmar) | Dimensión tiempo con año fiscal configurable por organización |
| R5 | Budget hoy viene como valor pegado en el Excel; origen por validar | Budget como **versión inmutable** cargada desde Excel; luego captura en plataforma |
| R6 | Comentarios por línea (mes y YTD), hoy vacíos | Modelo de comentarios con responsable, estatus y evidencia |
| R7 | Cada cifra debe responder de dónde salió, qué fórmula, quién y cuándo | Auditoría append-only + lineage |
| R8 | Torres primero, Puerto Vallarta después; datos aislados | Multi-tenant con `organizacion_id` y `hotel_id` en todo |
| R9 | Drill-down desde el reporte hasta el asiento | Consultas paginadas por cuenta, periodo y línea |
| R10 | Casos futuros: compras, Recepción, opiniones, limpieza | El modelo identifica transacciones por hotel, departamento, producto/habitación y fecha sin rehacerse |
| R11 | La IA no sustituye el cálculo y hereda permisos | Capa de IA separada, de solo lectura, con auditoría |
| R12 | Stack: Python; SQLite para probar (`[DECIDIDO]`) | Código agnóstico de dialecto; ver riesgo en sección 6.2 |

---

## 3. Stack tecnológico completo

Cada tecnología lleva justificación y alternativa. Contexto.md pide no decidir sin justificar.

### 3.1 Backend
| Componente | Elección | Por qué | Alternativa descartada |
|---|---|---|---|
| Lenguaje | **Python 3.12 o 3.13** `[DECIDIDO]` | Decisión del equipo; ecosistema de datos y Excel | Java/Spring (TI lo mencionó; se mantiene como opción solo si TI lo exige) |
| Framework API | **FastAPI** + Uvicorn/Gunicorn `[PROPUESTA]` | OpenAPI automático, validación con tipos, buen rendimiento | Django (más pesado para una API con motor propio), Flask |
| Validación | **Pydantic v2** | Contratos estrictos de entrada y salida | — |
| ORM y migraciones | **SQLAlchemy 2.x** + **Alembic** | Portable entre SQLite y PostgreSQL; migraciones versionadas | Django ORM, SQL a mano |
| Acceso a BD | Síncrono (`psycopg 3`) al inicio `[PROPUESTA]` | Carga pequeña (≈7–8 mil movimientos por mes y hotel), más simple de probar y depurar | `asyncpg` (se evalúa si medimos cuello de botella) |
| Montos | `decimal.Decimal` | Exactitud contable | `float`, y **pandas para cálculo contable** (se evita: float) |
| Lectura de Excel | `openpyxl` en modo solo lectura, sin evaluar fórmulas | Ya probado con el CON130 real | `pandas.read_excel` (pierde control de tipos de monto) |
| Exportación a Excel | `openpyxl` o `XlsxWriter` | Reproducir el formato del reporte actual | — |
| Tareas en segundo plano | **Procrastinate** (cola sobre PostgreSQL) `[PROPUESTA]` | Sin Redis ni broker extra; transaccional con los datos | Celery + Redis (se adopta si el volumen lo exige) |
| Autenticación | **OIDC** contra el proveedor de identidad de la empresa (`Authlib`/`PyJWT`) `[POR VALIDAR con TI]` | Usuarios y MFA centralizados; no guardamos contraseñas | Usuarios locales con `argon2id` + TOTP, solo como respaldo |
| Configuración | `pydantic-settings` + variables de entorno | Sin secretos en el repositorio | — |
| Logs | `structlog` (JSON) + `request_id` | Correlación y auditoría | — |
| Fórmulas seguras (Fase drivers) | Parser propio de expresiones (AST restringido) | **Nunca `eval`** | `eval`/`exec` (prohibido) |

### 3.2 Base de datos
| Entorno | Motor | Uso |
|---|---|---|
| Pruebas locales rápidas | **SQLite** `[DECIDIDO]` | Pruebas unitarias e integración ligera |
| CI, staging y producción | **PostgreSQL 16+** `[PROPUESTA]` | Tipos `NUMERIC`, **Row Level Security**, particionado, `pgAudit`, réplicas |
| Oracle | `[POR VALIDAR con TI]` | SQLAlchemy lo soporta, pero RLS equivale a VPD (licencia y esfuerzo). Solo si la política corporativa lo exige |

### 3.3 Frontend
| Componente | Elección | Por qué |
|---|---|---|
| Lenguaje | **TypeScript** en modo estricto | Menos errores; tipos generados desde OpenAPI |
| Framework | **React 18+** con **Vite** | Estándar, rápido, buen ecosistema |
| Datos del servidor | **TanStack Query** | Caché, reintentos, invalidación |
| Enrutamiento | React Router o TanStack Router | Rutas protegidas por rol |
| Tablas del reporte | **TanStack Table** + virtualización | El Variance es una tabla con secciones, subtotales y columnas fijas; se controla el formato contable |
| Componentes | Una librería MIT madura (Mantine o MUI) `[POR VALIDAR]` | Formularios, modales, accesibilidad |
| Gráficas | ECharts o Recharts | KPIs y tendencias |
| Cliente API | Generado desde OpenAPI (`openapi-typescript`) | Un solo contrato entre backend y frontend |
| Formularios y validación | React Hook Form + Zod | Validación en cliente (la del servidor es la que manda) |

### 3.4 Infraestructura y operación
| Componente | Elección | Nota |
|---|---|---|
| Contenedores | **Docker**, imágenes mínimas, usuario no root | Portable a nube o servidores propios |
| Desarrollo | Docker Compose (API + PostgreSQL + frontend) | Un comando levanta todo |
| Orquestación y hosting | `[POR VALIDAR con TI]` | Nube, servidores propios o híbrido |
| Proxy y TLS | Nginx o Traefik con TLS 1.2+ | HSTS, cabeceras de seguridad |
| Infra como código | Terraform u homólogo (Fase 6) | Entornos reproducibles |
| CI/CD | GitHub Actions o el CI que use TI | Ver sección 9 |
| Observabilidad | OpenTelemetry + Prometheus + Grafana; Sentry opcional | Métricas, trazas y alertas |
| Respaldos | `pgBackRest` o WAL-G, cifrados, con restauración probada | Ver sección 8.9 |
| Secretos | Gestor de secretos (Vault, del proveedor de nube o de TI) | Nunca en el repositorio |

---

## 4. Arquitectura

### 4.1 Estilo: monolito modular con arquitectura hexagonal `[PROPUESTA]`

Un solo despliegue, con módulos de límites claros. Se justifica por el tamaño del equipo, la necesidad de transacciones consistentes (cargas, versiones, aprobaciones) y porque se puede separar un módulo en servicio más adelante sin reescribir. Se descartan los microservicios por costo operativo sin beneficio hoy.

```
                      ┌────────────────────────── Frontend (React + TS) ──────────────────────────┐
                      └───────────────────────────────┬────────────────────────────────────────────┘
                                                      │ HTTPS · OpenAPI · JWT corto (OIDC)
┌─────────────────────────────────────────────────────▼──────────────────────────────────────────┐
│ API (FastAPI)  ·  autenticación · autorización (rol + hotel) · validación · límites de tasa     │
├──────────────┬───────────────┬─────────────┬─────────────┬──────────────┬──────────────────────┤
│ ingesta      │ catalogo      │ plan        │ variance    │ workflow     │ auditoria · identidad │
│ (CON130,     │ (cuentas,     │ (Budget,    │ (motor      │ (comentarios,│ (usuarios, roles,     │
│  Excel)      │  mapeo)       │  versiones) │  puro)      │  aprobación) │  bitácora)            │
├──────────────┴───────────────┴─────────────┴─────────────┴──────────────┴──────────────────────┤
│ DOMINIO PURO (Decimal, sin E/S) ← núcleo testeable     │  PUERTOS → ADAPTADORES (DB, archivos…) │
└────────────────────────────────────┬────────────────────────────────────────────────────────────┘
                                     │
                     PostgreSQL (SQLite en pruebas) · almacenamiento de archivos · cola de trabajos
```

**Regla de dependencia:** el dominio no importa FastAPI, SQLAlchemy ni `openpyxl`. Los adaptadores sí importan el dominio.

### 4.2 Estructura del repositorio `[PROPUESTA]`
```
plataforma_fpa/
  backend/
    fpa/
      dominio/        # montos, periodos, motor de variance, reglas (puro)
      ingesta/        # lectores (novohit_con130.py ya existe)
      catalogo/ plan/ variance/ workflow/ auditoria/ identidad/
      api/            # routers, esquemas, dependencias de seguridad
      infra/          # repositorios SQL, almacenamiento, cola, configuración
    migraciones/      # Alembic
    tests/            # unit/ integracion/ contrato/ seguridad/ dorados/
  frontend/
  infra/              # Docker, compose, IaC
  docs/               # ESTADO_DEL_PROYECTO.md, ADR (decisiones), runbooks, blueprint y este documento
  datos_prueba/       # solo datos sintéticos; nunca Excel reales de Torres
  CLAUDE.md           # puerta de entrada para cualquier sesión nueva (ver sección 13)
  CHANGELOG.md
```

### 4.3 Modelo de datos (nivel de entidades, no DDL)

Toda tabla de negocio lleva `organizacion_id` y `hotel_id`. Los montos son `NUMERIC(18,2)`.

| Entidad | Contenido clave |
|---|---|
| `organizacion`, `hotel` | Jerarquía multi-tenant; moneda; inicio del año fiscal |
| `departamento`, `centro_costo` | Estructura operativa `[POR VALIDAR]` (hoy el Excel solo muestra secciones del reporte) |
| `cuenta_local` | Código (ej. `1000001.001`), descripción, nivel, clase, cuenta padre, `con_movimientos`, `es_titulo`; del catálogo oficial CON020: **TIPO (Deudor/Acreedor)**, grupo del estado financiero, departamento, DPTO. TI, cuenta de terceros, código SAT, auxiliar, activa |
| `linea_reporte` | Sección, orden, cuenta corporativa, descripción, tipo (detalle, subtotal, total), regla de suma |
| `mapeo_cuenta` | `linea_reporte` ↔ `cuenta_local`, **signo** (+1/−1), vigencia y versión |
| `periodo` | Año fiscal, mes, fechas de inicio y fin |
| `carga_archivo` | Una por (archivo, periodo): fuente, nombre, hash SHA-256, periodo, estado (vigente o reemplazada), totales de control, usuario, fecha |
| `movimiento` (hecho) | Hotel, cuenta local, fecha, asiento, tipo de asiento, operación, número, concepto, débito, crédito, `carga_id` |
| `saldo_mensual_cuenta` (derivado) | Hotel, cuenta local, periodo, suma débito, suma crédito (recalculable desde `movimiento`) |
| `version_plan` | Tipo (Budget, Forecast, Escenario), nombre, estado de workflow, bloqueada, origen |
| `valor_plan` | `version_plan`, `linea_reporte`, periodo, monto |
| `comentario` | Línea, periodo, tipo (mes/YTD), texto, responsable, estatus, adjuntos |
| `cierre_periodo` | Estado del workflow (Borrador → Comentado → Revisado → Aprobado → Bloqueado) |
| `usuario`, `rol`, `asignacion` | Rol por hotel |
| `evento_auditoria` | Quién, qué, cuándo, antes/después, versión, `request_id` (solo inserción) |

**Cómo se calcula (reglas observadas en el Excel de agosto):**
- `Actual(línea, mes) = Σ signo × (débito − crédito)` de las cuentas locales mapeadas a la línea. El Excel usa signo negativo en líneas de ingreso, de modo que el ingreso aparezca positivo.
- `YTD` = suma de los meses del año fiscal hasta el mes de corte. `Annual Budget` = Budget de los 12 meses.
- `Variance` y `Variance %`: en las dos líneas revisadas, el signo favorable es positivo (ingresos: Actual − Budget; gastos: Budget − Actual). `[POR VALIDAR]` la convención oficial.
- Los totales por sección y los totales generales se recalculan por reglas de suma de la `linea_reporte`, no se pegan.

### 4.4 Multi-tenant y aislamiento `[PROPUESTA]`

- Esquema compartido con `organizacion_id` + `hotel_id` en cada tabla.
- **Defensa en profundidad**: (1) el repositorio aplica el filtro de tenant siempre; (2) en PostgreSQL, **Row Level Security** con `SET LOCAL app.organizacion_id`; (3) pruebas automáticas que intentan leer datos de otro hotel y deben fallar.
- SQLite no tiene RLS: por eso las pruebas de aislamiento corren también contra PostgreSQL en CI.
- Configuración por hotel (catálogo, mapeo, departamentos, año fiscal) sobre una estructura común. Puerto Vallarta se incorpora como **configuración**, no como código nuevo.

### 4.5 Escalabilidad

Dato honesto: el volumen de un hotel es pequeño (≈7,000 movimientos al mes). La escala relevante es **más hoteles, más años y más usuarios**, no más filas por segundo.

| Palanca | Cómo |
|---|---|
| API sin estado | Se replica horizontalmente tras el proxy |
| Precálculo | `saldo_mensual_cuenta` se recalcula al cargar; los reportes leen agregados, no movimientos |
| Caché de reportes | Clave `(organización, hotel, versión de mapeo, versión de plan, periodo)`; se invalida al cargar o aprobar |
| Índices | `(organizacion_id, hotel_id, periodo, cuenta_local)` y `(carga_id)` |
| Particionado | Por periodo en `movimiento` cuando pase de unos millones de filas |
| Drill-down | Paginación por cursor (keyset), nunca `OFFSET` grande |
| Trabajos en segundo plano | Cargas grandes y exportaciones fuera del ciclo de la petición |
| Lectura | Réplica de solo lectura para reportes si hace falta |

**Objetivos de rendimiento** `[PROPUESTA]` (se miden en Fase 6): Variance mensual (≈400 líneas) con p95 < 500 ms con caché y < 2 s sin caché; carga de un CON130 de 10 mil filas < 10 s; 50 usuarios concurrentes sin degradar.

---

### 4.6 Departamentos y estructura organizacional

**Hallazgo del catálogo oficial (CON020):** los grupos de 4 dígitos de la clase 6 **son los departamentos** del Variance (6005 Bar, 6006 Área Común, 6008 Cambio de Moneda, 6009 Gerencia y Recepción, 6010 Ama de Llaves, 6011 Contabilidad, 6012 Interior Apartamentos, 6013 Compras, 6014 Restaurante, 6015 Agencia de Viajes, 6016 Tienda, 6018 Cafetería, 6021 Sistemas), y la columna `DEPTO EdoFro` coincide con las secciones del reporte donde viene llena. El departamento de una cuenta se puede derivar de su código y validar contra esa columna. **El signo del Variance es la naturaleza de la cuenta (TIPO):** Acreedor se resta y Deudor se suma (validado con el Excel de Contraloría).

**Lo que sabemos de Torres (PROCESO ACTUAL, del Variance de agosto):** el reporte agrupa las cuentas en secciones que hoy cumplen el papel de departamentos:

| Bloque | Secciones |
|---|---|
| Ingresos | Other Income |
| Gastos de operación (se suman en *Total Operation Expenses*) | Mgmt & Check In · Accounting · Maid & Linen · Apartment Interior · Common Area · Utilities · Owner Activities · Other Taxes, Fees & Insurance · Purchasing |
| Servicios comerciales (con su propio resumen: Net Income, Expenses, Profit, Allocations, Net Profit) | Money Exchange · Telephones · Travel Agency · Bar · Restaurant |
| Otros | IT Systems |

**Departamentos operativos del modelo futuro (referencia del blueprint):** Rooms / Front Office, Revenue, Ama de Llaves, F&B (Restaurante, Bar, Cafetería, Banquetes), Mantenimiento, Compras / Almacenes, Lavandería, Seguridad, RRHH / Nómina, Contraloría / Finanzas, TI y Dirección.

**Cómo lo modela la plataforma `[PROPUESTA]`:**
- `departamento` es una **dimensión por hotel**. En el MVP se siembra con las secciones del reporte de Torres, sin inventar más.
- Cada `linea_reporte` pertenece a una sección y, a través de ella, a un departamento. Eso permite el Variance por departamento y los permisos por departamento.
- `centro_costo` queda definido en el modelo pero **vacío** hasta que Contraloría entregue su estructura `[POR VALIDAR]`.
- Un departamento operativo futuro (por ejemplo Ama de Llaves) se relaciona con las secciones contables existentes mediante una tabla de equivalencias, sin rehacer el modelo.
- El Inventory Engine futuro es único; los almacenes por departamento son datos, no módulos distintos.
- Permisos: el rol *responsable de área* ve y comenta solo las líneas de su departamento.

## 5. Correspondencia con las capacidades de Board

Board es solo referencia funcional (no se copia su tecnología).

| Capacidad (referencia funcional) | Fase |
|---|---|
| Data & Actuals | 1 |
| Management Reporting con drill-down | 3–4 |
| Variance Analysis | 3 |
| Comentarios y colaboración | 5 |
| Workflow y aprobaciones | 5 |
| Budget con ciclo y versiones | 7 |
| Rolling Forecast | 8 |
| Driver-Based Planning, Scenarios | 9 |
| Cash Flow | 10 |
| Multi-hotel / Consolidación gerencial | 11 |
| AI FP&A | 12 |
| Strategic Planning y Capital Planning (CAPEX) | 13 |
| Daily Operational Planning (planeación diaria, caso Scandic) | 14 |

**Alcance frente a Board y Scandic (honesto):** el sistema cubre las mismas *capacidades funcionales* que el blueprint tomó de Board y del caso Scandic (planeación anual, rolling forecast, reporting con drill-down, consolidación, planeación operativa diaria, horizonte multianual), pero **por fases y no al mismo tiempo**. El MVP es solo Actual, Budget, Variance, YTD, Annual Budget, comentarios y drill-down. Board es una plataforma empresarial madura de muchos años; no se pretende igualarla en todo, y **no se copia su tecnología, interfaz ni modelos**. La consolidación legal (eliminaciones intercompany, multi-moneda) queda fuera hasta que exista necesidad real.

---

## 6. Decisiones y riesgos técnicos clave

### 6.1 Registro de decisiones (ADR)
| ID | Decisión | Estado |
|---|---|---|
| ADR-01 | Monolito modular hexagonal | `[PROPUESTA]` |
| ADR-02 | Python + FastAPI + SQLAlchemy 2 + Alembic | `[DECIDIDO]` Python; resto `[PROPUESTA]` |
| ADR-03 | `Decimal` y `NUMERIC(18,2)` para todo monto | `[PROPUESTA]` (no negociable) |
| ADR-04 | SQLite en pruebas locales; PostgreSQL en CI/staging/producción | `[DECIDIDO]` SQLite; `[PROPUESTA]` PostgreSQL |
| ADR-05 | Multi-tenant con RLS + filtro en aplicación | `[PROPUESTA]` |
| ADR-06 | OIDC con el proveedor de identidad de la empresa | `[POR VALIDAR con TI]` |
| ADR-07 | Auditoría de solo inserción con cadena de hash | `[PROPUESTA]` |
| ADR-08 | Cola de trabajos sobre PostgreSQL (Procrastinate) | `[PROPUESTA]` |
| ADR-09 | Nunca `eval`; fórmulas de drivers con parser restringido | `[PROPUESTA]` |
| ADR-10 | La IA solo lee, hereda permisos y cita fuente | `[PROPUESTA]` |

### 6.2 Riesgos
| Riesgo | Mitigación |
|---|---|
| SQLite oculta errores que aparecen en PostgreSQL (tipos, RLS, bloqueos, `ON CONFLICT`) | CI corre la integración en PostgreSQL desde la Fase 1; no usar sintaxis exclusiva de SQLite; probar en ambos motores |
| El formato del CON130 cambia con una versión de Novohit | Lector por reglas y validaciones; pruebas con archivos reales de cada mes; aviso claro si falla |
| Mapeo incorrecto altera todo el Actual | Mapeo versionado, reporte de cuentas sin mapear o dobles, aprobación de cambios, prueba dorada |
| Origen del Budget incierto | Se carga como versión desde el Excel; la carga se ajusta cuando el contralor confirme el origen |
| Alcance excesivo | Fases con criterio de salida; no se abre la siguiente sin cerrar la anterior |
| Decisión de TI distinta (Java/Oracle) | Dominio puro y puertos hacen costoso pero acotado el cambio de adaptadores; el dominio en Python se conserva como referencia de cálculo |
| Datos personales en casos futuros (huéspedes, empleados) | Permisos por rol y política de privacidad antes de construirlo |

---

## 7. Plan de desarrollo por fases

Tamaños relativos: **S** (días), **M** (1–2 semanas), **L** (más de 2 semanas). No son fechas comprometidas.
Cada fase termina con **criterio de salida** y **puerta de seguridad**. Ninguna fase se abre sin cerrar la anterior.

### Fase 0 — Crear el repositorio del proyecto full stack `[HECHA]` (30-sep-2026)

Objetivo: dejar un repositorio **con lo mínimo para levantar el servidor**, donde cualquier persona (o un chat nuevo) pueda levantarlo y entender el estado del proyecto leyendo su documentación. Por decisión del equipo, el alcance es **básico**: las tecnologías adicionales (Docker, CI, PostgreSQL, Playwright, autenticación, etc.) se hablan con TI y están listadas como cambios futuros en `CAMBIOS_FUTUROS_DE_TECNOLOGIA.md`.

Repositorio: `C:\Users\mzamora\Desktop\fpa-hotelero`, separado de la carpeta de documentos de Torres.

| Sub-fase | Qué se hizo | Cómo se verificó |
|---|---|---|
| 0.1 Crear el repositorio | `git init`, `.gitignore` (excluye Excel, `.env`, `.db`, `.venv`, `node_modules`). Sin commits todavía; el remoto lo define TI `[POR VALIDAR]` | `git status` no lista ningún Excel, `.env` ni `.db` |
| 0.2 Estructura | `backend/`, `frontend/`, `docs/`, `datos_prueba/` | La estructura coincide con la sección 4.2 (sin `infra/` hasta que haya Docker) |
| 0.3 Lector del CON130 | Movido a `backend/fpa/ingesta/` con sus pruebas; la prueba del archivo real lee la carpeta de documentos (`FPA_DATOS_REALES`) | Las 13 pruebas pasan desde el nuevo lugar |
| 0.4 Backend básico | Python 3.13, entorno propio `backend/.venv`, versiones fijas en `requirements.txt`, FastAPI con `GET /api/health` y `/api/ready`, SQLite por `FPA_DATABASE_URL`, CORS solo al frontend local | 4 pruebas nuevas (salud, base de datos, error sin filtrar detalle, CORS) |
| 0.5 Frontend básico | React + TypeScript + Vite, pantalla que consulta la API, proxy `/api` | `npm run build` sin errores; el proxy llega a la API |
| 0.6 Arranque | `iniciar_servidores.bat`, puertos propios **8100** (API) y **5180** (web) | Ambos servidores levantaron y respondieron |
| 0.7 Documentación viva | `CLAUDE.md`, `docs/ESTADO_DEL_PROYECTO.md`, ADR 0001, `CAMBIOS_FUTUROS_DE_TECNOLOGIA.md`, `README.md`, `CHANGELOG.md` | Un chat nuevo que lea `CLAUDE.md` sabe en qué fase va y qué sigue |

**Diferido a propósito** (antes en esta fase): Docker Compose, calidad local (`ruff`, `mypy`, `pre-commit`), integración continua y Playwright. Se reincorporan según `CAMBIOS_FUTUROS_DE_TECNOLOGIA.md`.

**Resultado:** 17 pruebas pasan; ningún secreto ni dato real en el repositorio.

### Fase 1 — Data Hub: Actuals `[HECHA]` (30-sep-2026)
| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 1.0 Cimientos de datos `[HECHO]` | Alembic con primera migración; modelos `organizacion`, `hotel`, `usuario`, `rol`, `asignacion`; tipo `Dinero`; dependencia que exige contexto de hotel; proveedor de identidad de desarrollo detrás de una interfaz (cerrado por defecto); `ruff` y `mypy` estricto | Migración sube y baja en SQLite (PostgreSQL con prueba lista, se salta hasta tener instancia) y no se desvía de los modelos. **Prueba de aislamiento**: un usuario del hotel A no lee datos del hotel B (404) y sin permiso recibe 403 |
| 1.1 Lector CON130 `[HECHO]` | Contrato común de lectura (`contrato.py`) y captura de los títulos de jerarquía | 13 pruebas del lector + pruebas del contrato; septiembre real: 7,242 movimientos / 366 cuentas / 145 títulos / 57,835,193.08 |
| 1.2 Lector del Excel de Variance `[HECHO]` | Leer la hoja "Base de Datos" (**julio y agosto**) con el mismo contrato de salida que el CON130. Es un subconjunto de cuentas de resultados (clases 4, 5 y 6), por eso **Débito ≠ Crédito** en esta fuente | Mismos totales que el libro: 6,860 movimientos (Julio 3,583 + Agosto 3,277), 296 cuentas, Débito 12,650,614.04 y Crédito 12,037,735.88 |
| 1.3 Persistencia de cargas `[HECHO]` | `carga_archivo` + `movimiento` en una sola transacción; hash SHA-256 | Carga atómica: si falla a la mitad no queda nada; `Decimal` ida y vuelta exacto |
| 1.4 Idempotencia y reemplazo `[HECHO]` | Mismo archivo no duplica (hash); una **carga vigente por hotel y periodo**; recargar un periodo con otro archivo exige confirmación y conserva historial (la anterior pasa a `reemplazada`) | Cargar dos veces = mismo resultado; el reemplazo queda en la auditoría |
| 1.5 Calidad de datos `[HECHO]` | Reporte con controles por fuente. CON130: Débito = Crédito y total por cuenta. Variance: mes en texto = mes de la fecha. Ambas: fechas dentro del periodo, cuentas nuevas (aviso) y filas repetidas exactas (**aviso, no rechazo**: existen 5 en el Variance y 14 en el CON130) | Un archivo alterado a propósito es rechazado con mensaje claro |
| 1.6 Catálogo local `[HECHO]` | Construir el árbol de cuentas desde el reporte (nivel 1 > 10 > 1000 > 1000001 > 1000001.001) | Todas las cuentas con movimiento existen en el árbol |
| 1.7 Saldos mensuales `[HECHO]` | `saldo_mensual_cuenta` derivado y recalculable | Suma de saldos = suma de movimientos, propiedad verificada con `hypothesis` |
| 1.8 API de carga segura `[HECHO]` | `POST` de archivo con validaciones (ver 8.5) | Archivos maliciosos rechazados; pruebas de tamaño, tipo y zip-bomb |
| 1.9 Catálogo oficial de cuentas `[HECHO]` | Importar el reporte CON020 de Novohit (`.xls`): nombres de la jerarquía, TIPO, departamento, grupo del estado financiero y código SAT; nuevos controles de calidad | Catálogo real: 1,238 cuentas y 68 títulos; 366 de 366 cuentas de septiembre; el signo del Variance coincide con TIPO en todos los casos del Excel |

**Salida:** septiembre y julio–agosto cargan y cuadran con sus controles. **Seguridad:** subida endurecida, auditoría de cada carga.

### Fase 2 — Catálogo corporativo y mapeo (M)
| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 2.1 Estructura del reporte `[HECHO]` | Importar de la hoja `Ago`: secciones, líneas, orden, tipo (detalle, subtotal, total) | 409 líneas de detalle importadas; orden igual al Excel |
| 2.2 Reglas de suma `[HECHO]` | Modelar cómo se construye cada total (p. ej. Total Operation Expenses = suma de 9 secciones) | Reglas reproducen 3,711,624.81 |
| 2.3 Mapeo `[HECHO]` | Importar de las columnas X a AJ: línea ↔ cuentas locales, con signo | 253 líneas vinculadas; signos iguales a las fórmulas del Excel |
| 2.4 Validación del mapeo `[HECHO]` | Reporte de cuentas con movimiento sin mapear y de cuentas mapeadas a más de una línea | Cero cuentas con Actual ≠ 0 sin vínculo (como en agosto) |
| 2.5 Versionado `[HECHO]` | Cada cambio crea nueva versión; vigencia; auditoría | No se puede editar una versión aprobada |
| 2.6 API de mapeo `[HECHO]` | Consulta y cambio con permiso de analista | Solo el rol autorizado cambia el mapeo; queda bitácora |

**Salida:** mapeo completo y aprobado por Contraloría.

### Fase 3 — Motor de Variance (L)
| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 3.1 Budget como versión `[HECHO]` | Cargar Budget del Excel de agosto (mes, YTD, anual) como `version_plan` inmutable | El Budget cargado es idéntico al del Excel, línea por línea |
| 3.2 Motor de Actual `[HECHO]` | `Actual(línea, mes)` desde movimientos + mapeo (función pura) | Pruebas unitarias con casos pequeños y propiedades (signo, suma) |
| 3.3 YTD y año fiscal `[HECHO]` | Acumulado julio–junio | Fronteras: primer mes, cierre de año, mes sin datos |
| 3.4 Totales y subtotales `[HECHO]` | Reglas de suma; Commercial Services (Net Income, Expenses, Profit, Allocations) | Totales iguales a los del reporte |
| 3.5 Variance y Variance % `[HECHO]` | Convención de signo configurable | División entre cero y presupuesto cero devuelven un valor definido, no error |
| 3.6 `[HECHO]` **Prueba dorada: agosto 2026** | Reproducir columnas D a Q de la hoja `Ago` | **Diferencia cero** en las 253 líneas vinculadas y en los totales |
| 3.7 `[HECHO el arnés; falta el Excel de septiembre]` Segunda prueba: septiembre 2026 | Mismo proceso con el CON130 y el Variance de septiembre | Diferencia cero |

**Salida:** el motor reproduce agosto cifra por cifra sin ninguno de los 14 pasos manuales. **Seguridad:** el motor no realiza E/S; entradas validadas.

### Fase 4 — API de reporting y frontend (L)
| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 4.1 Endpoints de reporte | Variance por periodo y sección; filtros | Contrato OpenAPI; pruebas con Schemathesis |
| 4.2 Drill-down | Línea → cuentas locales → movimientos, paginado por cursor | La suma de los movimientos mostrados = cifra de origen |
| 4.3 Base del frontend | React + TS, rutas protegidas, cliente generado de OpenAPI | Sin acceso a pantallas sin rol; tipos sin `any` |
| 4.4 Pantalla de Variance | Tabla por secciones con subtotales, formato contable, columnas fijas | Comparación visual y de valores contra el Excel de agosto |
| 4.5 Pantalla de drill-down | Navegación desde la cifra hasta el asiento | Prueba end-to-end con Playwright |
| 4.6 Exportación a Excel | Mismo formato del reporte actual | El Excel exportado abre y sus cifras coinciden con la pantalla |
| 4.7 Rendimiento | Caché de reportes y agregados | Objetivos de la sección 4.5 |
| 4.8 Pruebas con usuarios | Sesión con Contraloría usando agosto | Lista de hallazgos cerrada |

**Seguridad:** CSP estricta, sin `dangerouslySetInnerHTML`, tokens fuera de `localStorage`.

### Fase 5 — Comentarios, workflow, roles y auditoría (L)
| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 5.1 Identidad real | Integración OIDC con el proveedor de la empresa `[POR VALIDAR con TI]`; MFA | Sesión caduca; token revocado deja de funcionar |
| 5.2 Roles y permisos | Matriz: contralor, analista, responsable de área, dirección, auditoría | **Prueba de matriz completa**: cada rol × cada endpoint |
| 5.3 Comentarios | Por línea y periodo (mes/YTD), responsable, estatus, evidencia | Texto con HTML/script se escapa; adjuntos pasan por la validación de 8.5 |
| 5.4 Workflow de cierre | Borrador → Comentado → Revisado → Aprobado → Bloqueado | Estados inválidos rechazados; un periodo bloqueado no acepta recargas |
| 5.5 Auditoría | Cada cambio genera evento de solo inserción con hash encadenado | Intentar modificar o borrar un evento falla; la cadena detecta alteraciones |
| 5.6 Notificaciones | Aviso por correo a responsables (opcional) | No incluye datos sensibles en el cuerpo |

**Salida:** se puede reconstruir quién cambió qué cifra y cuándo.

### Fase 6 — Endurecimiento y piloto en Torres (L)
| Sub-fase | Qué se hace | Qué se prueba |
|---|---|---|
| 6.1 Revisión de seguridad | Checklist OWASP ASVS nivel 2, DAST (OWASP ZAP) en staging, revisión de dependencias | Cero hallazgos críticos o altos abiertos |
| 6.2 Prueba de penetración | Interna o externa antes de producción | Informe con remediaciones verificadas |
| 6.3 Rendimiento y carga | `Locust` o `k6`: 50 usuarios, cargas de 10 mil filas | Objetivos de la sección 4.5 |
| 6.4 Respaldos y recuperación | Respaldo cifrado y **restauración probada** | Restaurar en un entorno limpio y repetir agosto con diferencia cero |
| 6.5 Observabilidad | Métricas, trazas, alertas (errores, latencia, cargas fallidas) | Una falla simulada dispara alerta |
| 6.6 UAT | Contraloría ejecuta el cierre de agosto y septiembre en la plataforma | Acta de aceptación firmada |
| 6.7 Puesta en producción | Runbooks, plan de reversa, capacitación | Ensayo de despliegue y reversa |

**Salida:** Contraloría cierra un mes real en la plataforma sin Excel paralelo.

### Fases siguientes (detalle menor; se profundiza al llegar)
| Fase | Alcance | Sub-fases principales | Qué se prueba |
|---|---|---|---|
| 7 Budget en plataforma (L) | Ciclo top-down/bottom-up, spreading, versiones | 7.1 ciclo y estados; 7.2 captura por área; 7.3 spreading (estacionalidad, %); 7.4 aprobación y bloqueo; 7.5 comparación objetivo vs propuesta | La suma de los meses = total anual (propiedad); versión aprobada inmutable |
| 8 Forecast y rolling (L) | Actual cerrado + futuro; horizonte de 12 meses | 8.1 versión forecast; 8.2 cierre mensual que sustituye forecast por actual; 8.3 comparativo contra forecast anterior y Budget | El cierre no altera versiones anteriores |
| 9 Drivers y escenarios (L) | Ocupación, ADR, covers, headcount, OT; what-if | 9.1 modelo de drivers; 9.2 parser de fórmulas seguro; 9.3 fuentes operativas (PMS, POS, nómina); 9.4 escenarios aislados del plan oficial | Fórmula maliciosa rechazada; un escenario nunca modifica el Budget aprobado |
| 10 Cash Flow (L) | Liquidez, cobranza, pagos, nómina, impuestos, CAPEX | 10.1 fuentes de AR/AP y banco; 10.2 calendario; 10.3 escenarios de caja | Saldo final = inicial + entradas − salidas |
| 11 Multi-hotel (M) | Puerto Vallarta | 11.1 checklist de incorporación; 11.2 catálogo y mapeo por hotel; 11.3 validar si usa el mismo Novohit; 11.4 reportes comparativos entre hoteles | Aislamiento entre hoteles; el lector del CON130 funciona sin cambios si el formato es el mismo |
| 12 IA gobernada (M) | Resumen de variaciones, detección de anomalías, preguntas sobre KPIs | 12.1 capa de herramientas de solo lectura; 12.2 permisos heredados; 12.3 citas de fuente; 12.4 defensas contra inyección de prompts | La IA no puede leer fuera del alcance del usuario; toda cifra citada coincide con el motor |
| 13 Strategic y Capital Planning (L) | Plan de 3 a 5 años, proyectos CAPEX, evaluación de inversiones | 13.1 modelo de proyecto CAPEX (monto, calendario, aprobador); 13.2 impacto en P&L, depreciación y cash; 13.3 ROI/NPV/IRR con `Decimal`; 13.4 escenarios de largo plazo | Cálculos financieros contra casos de libro de texto; CAPEX y OPEX no se mezclan |
| 14 Daily Operational Planning (M) | Planeación diaria por departamento (referencia: caso Scandic) | 14.1 granularidad diaria en el modelo de tiempo; 14.2 fuentes operativas diarias (PMS, POS); 14.3 captura y alertas | Totales diarios = mensuales; rendimiento con granularidad diaria |

**Orden sugerido de las fases 7 a 14:** 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14. Puerto Vallarta (11) puede adelantarse si Dirección lo prioriza, porque el modelo ya es multi-hotel desde la sub-fase 1.0. La IA (12) siempre va después de tener datos y cálculos validados.

Casos futuros de Dirección (compras, Recepción, opiniones de huéspedes, quién limpió qué habitación) entran después de la Fase 9, cuando existan las fuentes operativas y la política de privacidad.

---

## 8. Seguridad

Objetivo: **OWASP ASVS nivel 2** y cobertura del OWASP Top 10. Ninguna plataforma es "a prueba de hackeos"; el objetivo es reducir la superficie, detectar rápido y poder reconstruir cualquier incidente.

### 8.1 Modelo de amenazas (resumen)
| Activo | Amenaza | Control principal |
|---|---|---|
| Datos financieros del hotel | Acceso no autorizado; fuga entre hoteles | Autenticación fuerte, RBAC, RLS, cifrado |
| Cifras del Variance | Alteración para ocultar desviaciones | Versiones inmutables, auditoría de solo inserción, aprobaciones |
| Archivos subidos | Malware, macros, zip-bomb, fórmulas maliciosas | Validación y aislamiento (8.5) |
| Cuentas de usuario | Robo de credenciales, fuerza bruta | OIDC + MFA, límite de intentos |
| Cadena de suministro | Dependencia comprometida | Bloqueo de versiones, auditoría continua, SBOM |
| IA (futuro) | Inyección de prompts, exfiltración | Solo lectura, permisos heredados, salida validada |

### 8.2 Autenticación y sesión
- OIDC con MFA; sin contraseñas propias si TI lo permite. Respaldo: `argon2id` + TOTP.
- Tokens de acceso cortos (≈15 min) y refresh con rotación; revocación al cerrar sesión.
- Cookies `HttpOnly`, `Secure`, `SameSite=Strict` si la sesión va en cookie; en ese caso, protección CSRF.
- Bloqueo progresivo por intentos fallidos y alertas de inicio de sesión inusual.

### 8.3 Autorización
- **Deny by default**: todo endpoint exige permiso explícito.
- RBAC por rol + **alcance por hotel**. Las verificaciones ocurren en el servidor, nunca solo en la interfaz.
- Se protege contra IDOR: cada objeto se busca siempre con su `organizacion_id` y `hotel_id`.
- Prueba automatizada de la **matriz rol × endpoint** en cada cambio.

### 8.4 Datos
- TLS 1.2+ en tránsito; cifrado en reposo (disco y respaldos).
- Montos y cuentas no se escriben en logs; los logs no incluyen tokens ni contraseñas.
- Minimización: no se guardan datos personales de huéspedes hasta que exista política.

### 8.5 Subida de archivos (el punto de entrada más expuesto)
1. Solo `.xlsx`/`.csv`; se **rechazan `.xlsm`/macros** y extensiones dobles.
2. Se verifica el tipo real por contenido (firma del archivo), no solo la extensión.
3. Tamaño máximo; límite de **tamaño descomprimido y de número de entradas** del ZIP (anti zip-bomb).
4. `openpyxl` en solo lectura y **sin evaluar fórmulas**; nunca se ejecuta contenido del archivo.
5. Nombre interno aleatorio; almacenamiento fuera de la raíz web; hash SHA-256 registrado.
6. Escaneo antivirus opcional (ClamAV) `[POR VALIDAR con TI]`.
7. Las celdas que empiezan con `=`, `+`, `-`, `@` se neutralizan al **exportar** (evita inyección de fórmulas en Excel).

### 8.6 Aplicación web
- **Inyección SQL:** solo consultas parametrizadas del ORM; prohibido concatenar SQL. `bandit` y `semgrep` lo vigilan.
- **XSS:** React escapa por defecto; CSP estricta; sin `dangerouslySetInnerHTML`; los comentarios se tratan como texto.
- **CSRF, CORS:** lista blanca de orígenes; `SameSite`; tokens anti-CSRF si hay cookies.
- **Cabeceras:** HSTS, `X-Content-Type-Options`, `frame-ancestors 'none'`, `Referrer-Policy`, `Permissions-Policy`.
- **Límite de tasa** por usuario y por IP; tamaño máximo de petición; tiempos de espera.
- **Errores:** respuestas genéricas al cliente, detalle solo en logs.
- **SSRF:** el backend no hace peticiones a URL proporcionadas por usuarios.

### 8.7 Cadena de suministro y contenedores
- Dependencias con versiones bloqueadas (lockfiles); `pip-audit`, `npm audit` y Dependabot/Renovate en CI; SBOM por versión.
- `gitleaks` en hooks y CI; secretos solo en el gestor de secretos.
- Imágenes mínimas, usuario no root, sistema de archivos de solo lectura donde se pueda; escaneo con Trivy.
- Revisión obligatoria de PR y ramas protegidas; firmas de commits `[PROPUESTA]`.

### 8.8 Auditoría
- `evento_auditoria` de **solo inserción**: el usuario de la aplicación no tiene `UPDATE` ni `DELETE` sobre esa tabla.
- Cada evento guarda el hash del anterior (cadena); una verificación periódica detecta alteraciones.
- Se registran: cargas, cambios de mapeo, versiones de plan, comentarios, aprobaciones, cambios de roles, accesos denegados.

### 8.9 Continuidad y respuesta a incidentes
- Respaldos cifrados diarios + WAL continuo; **restauración probada** en cada trimestre.
- Objetivos propuestos `[POR VALIDAR con Contraloría y TI]`: RPO ≤ 15 min, RTO ≤ 4 h.
- Runbook de incidentes: contención, revocación de credenciales, análisis con la bitácora, comunicación.

### 8.10 IA (Fase 12)
- La IA solo consume herramientas de **lectura** del motor; no escribe ni calcula.
- Hereda los permisos del usuario que pregunta; cada consulta y respuesta queda en auditoría con sus fuentes.
- Contenido de archivos y comentarios se trata como **no confiable** (defensa contra inyección de prompts); se valida la salida.

### 8.11 Correspondencia con OWASP Top 10 (2021)
| Riesgo | Control |
|---|---|
| A01 Control de acceso roto | Deny by default, RBAC + hotel, RLS, pruebas de matriz |
| A02 Fallas criptográficas | TLS, cifrado en reposo, gestor de secretos, `argon2id` |
| A03 Inyección | ORM parametrizado, CSP, escape de salida, neutralización en exportación |
| A04 Diseño inseguro | Modelo de amenazas, ADR, revisión de diseño por fase |
| A05 Configuración incorrecta | Contenedores mínimos, cabeceras, entornos separados, IaC |
| A06 Componentes vulnerables | Auditoría continua de dependencias, SBOM |
| A07 Fallas de autenticación | OIDC + MFA, límites de intentos, sesiones cortas |
| A08 Integridad de software y datos | CI con firmas, aprobaciones, auditoría encadenada, versiones inmutables |
| A09 Fallas de registro y monitoreo | Logs estructurados, alertas, bitácora de auditoría |
| A10 SSRF | Sin peticiones a URL de usuario |

---

## 9. Estrategia de pruebas y calidad

### 9.1 Pirámide
| Nivel | Herramientas | Qué cubre |
|---|---|---|
| Unitarias | `pytest`, `hypothesis` | Dominio puro: montos, periodos, signos, YTD, variance, spreading. **Propiedades:** suma de meses = total; Débito = Crédito; idempotencia de cargas |
| Integración | `pytest` con SQLite **y PostgreSQL** (servicio en CI o `testcontainers`) | Repositorios, migraciones, transacciones, RLS |
| Contrato de API | `Schemathesis` sobre el OpenAPI | Entradas inválidas, códigos de estado, esquemas |
| **Pruebas doradas** | Archivos reales (`BASE DATOS.xlsx`, Variance de agosto) | El sistema reproduce cifra por cifra. Son la prueba de aceptación del MVP |
| Seguridad | Pruebas de aislamiento de tenant, matriz rol × endpoint, fuzz de subida de archivos, `bandit`, `semgrep`, `pip-audit`, ZAP | Sección 8 |
| End-to-end | `Playwright` | Flujos: cargar, ver Variance, drill-down, comentar, aprobar |
| Rendimiento | `Locust` o `k6` | Objetivos de la sección 4.5 |
| Accesibilidad | `axe` | Pantallas clave |

### 9.1.1 Pruebas end-to-end con Playwright `[DECIDIDO: se usará Playwright]`

**Herramienta:** `@playwright/test` (TypeScript), dentro del repo del frontend. Corre en Chromium, Firefox y WebKit; en CI se ejecuta en paralelo con reintentos limitados, y guarda *trace*, captura y video solo cuando falla.

**Cómo se corre:** contra el entorno de Docker Compose o staging, con datos sembrados por API (no por la interfaz) y un usuario de prueba por rol. Cada prueba es independiente y limpia sus datos.

**Buenas prácticas:** selectores por rol y texto accesible (`getByRole`), sin esperas fijas, *page objects* para pantallas repetidas, y ninguna prueba depende del orden.

| Fase | Flujos e2e que se agregan |
|---|---|
| 1 | Subir el CON130 de septiembre: muestra 7,242 movimientos y los controles en verde; subir un archivo alterado: se rechaza con mensaje claro; subir un `.xlsm` o un archivo falso: se rechaza |
| 3–4 | **Variance de agosto en pantalla = Excel de agosto** (cifras de las 253 líneas vinculadas y los totales); colapsar y expandir secciones; drill-down de una línea hasta el asiento con suma que cuadra; exportar a Excel y comparar cifras |
| 5 | Comentar una variación; flujo Borrador → Comentado → Revisado → Aprobado → Bloqueado; un periodo bloqueado no acepta recarga |
| 5–6 | **Seguridad:** cada rol ve solo lo suyo; un usuario del hotel A no abre URLs del hotel B; un comentario con `<script>` se muestra como texto; sesión caducada redirige al inicio de sesión |
| 6 | Accesibilidad con `axe` en pantallas clave; comparación visual de la pantalla de Variance; recorrido completo del cierre de septiembre |
| 7+ | Ciclo de Budget, forecast y escenarios según se construyan |

Las pruebas e2e **no sustituyen** a las doradas del backend: verifican que lo que ve el usuario coincide con lo que calcula el motor.

### 9.2 Metas de calidad `[PROPUESTA]`
- Cobertura de líneas: dominio ≥ 90 %, resto ≥ 80 %; los umbrales bloquean el PR.
- Tipado estricto sin `Any` en el dominio.
- Toda corrección de error lleva una prueba que lo reproduce.
- Las pruebas doradas no se modifican para "hacerlas pasar": si cambian, se documenta el motivo.

### 9.3 Definición de hecho (por tarea)
1. Código revisado por otra persona.
2. Pruebas nuevas y existentes pasan en SQLite y PostgreSQL.
3. Sin hallazgos nuevos de seguridad ni dependencias vulnerables.
4. Migración reversible probada.
5. Documentación y ADR actualizados si hubo decisión.
6. Cifras verificadas contra la prueba dorada aplicable.

---

## 10. Entornos y despliegue

| Entorno | Base de datos | Datos | Propósito |
|---|---|---|---|
| Local | SQLite o PostgreSQL en contenedor | Sintéticos y archivos de prueba | Desarrollo |
| CI | PostgreSQL efímero | Sintéticos + dorados | Pruebas automáticas |
| Staging | PostgreSQL | Copia anonimizada o de prueba | UAT, DAST, rendimiento |
| Producción | PostgreSQL con respaldos | Reales | Operación |

- Separación estricta: producción no se accede desde desarrollo; credenciales distintas por entorno.
- Despliegue con migraciones automáticas y **plan de reversa** probado.
- Datos reales de Torres no se copian a entornos de desarrollo sin anonimizar.

---

## 11. Decisiones pendientes con TI y Contraloría

| # | Pregunta | Quién |
|---|---|---|
| 1 | ¿Dónde se aloja (nube, servidores propios, híbrido)? | TI |
| 2 | ¿Qué proveedor de identidad usa la empresa (Microsoft Entra ID, otro)? ¿MFA obligatorio? | TI |
| 3 | ¿PostgreSQL es aceptable o la política exige Oracle? | TI |
| 4 | ¿Hay política de respaldos, RPO y RTO? | TI |
| 5 | ¿Antivirus corporativo para archivos subidos? | TI |
| 6 | Origen, versión y responsable del Budget | Contraloría |
| 7 | Convención oficial del signo del Variance y del año fiscal | Contraloría |
| 8 | Árbol oficial de departamentos y centros de costo | Contraloría |
| 9 | ¿Quién exporta el CON130 y con qué fecha límite mensual? | Contraloría |
| 10 | ¿Puerto Vallarta usa el mismo Novohit y un catálogo parecido? | Contraloría |

---

## 12. Siguiente paso inmediato

Empezar la **Fase 0: crear el repositorio del proyecto full stack** (sección 7). El lector del CON130 ya está hecho y se traslada al repositorio en la sub-fase 0.3. La Fase 1 arranca solo cuando la Fase 0 cierre.

---

## 13. Continuidad entre chats y documentación viva

El proyecto se desarrollará en muchas sesiones de chat. Ninguna sesión recuerda a la anterior, así que **el conocimiento vive en el repositorio, no en la conversación**.

### 13.1 Qué archivos sostienen la continuidad
| Archivo | Para qué sirve | Quién lo actualiza |
|---|---|---|
| `CLAUDE.md` (raíz) | Puerta de entrada: qué es el proyecto, reglas de trabajo, cómo correrlo y probarlo, y a qué documentos ir | Al cambiar reglas o comandos |
| `docs/ESTADO_DEL_PROYECTO.md` | Fase actual, sub-fases hechas y pendientes, pruebas que pasan, decisiones recientes, bloqueos | **Al cerrar cada sub-fase** |
| `docs/adr/NNN-titulo.md` | Una decisión técnica por archivo, con contexto, alternativas y consecuencia | Cuando se toma una decisión |
| `docs/Arquitectura_Tecnica_FPA_Hotelero.md` | Este documento: el plan | Al cambiar el plan |
| `docs/Blueprint_Funcional_FPA_Hotelero_Torres_Mazatlan.docx` | Requisitos funcionales aprobados | Solo con aprobación de Contraloría |
| `CHANGELOG.md` | Qué cambió en cada versión | En cada entrega |

### 13.2 Regla de inicio y de cierre de sesión
- **Al empezar un chat:** leer `CLAUDE.md`, luego `docs/ESTADO_DEL_PROYECTO.md`, y revisar la fase en curso en este documento. No rehacer lo que ya está marcado `[HECHO]`.
- **Al terminar un chat o una sub-fase:** actualizar `ESTADO_DEL_PROYECTO.md` (qué se hizo, qué pruebas pasan, qué sigue, qué quedó pendiente) y marcar la sub-fase en este documento. Las cifras de referencia (por ejemplo 7,242 movimientos, 366 cuentas, 57,835,193.08) se anotan con su fuente.
- **Una sub-fase no está terminada** hasta que su documentación esté actualizada.

### 13.3 Contenido mínimo de `ESTADO_DEL_PROYECTO.md`
1. Fase y sub-fase actual.
2. Tabla de sub-fases con estado: pendiente, en curso, hecho.
3. Comandos para levantar el entorno y correr las pruebas.
4. Resultado de la última corrida de pruebas (incluidas las doradas).
5. Decisiones tomadas desde la última actualización (con enlace al ADR).
6. Preguntas abiertas para TI y Contraloría.
7. Siguiente paso concreto.

---

## 14. Trazabilidad: del Blueprint a esta arquitectura

Para verificar que no quedó nada fuera. **Bloque** = sección del Blueprint.

| Bloque del Blueprint | Dónde se atiende aquí | Estado |
|---|---|---|
| Contexto, problema, objetivo, alcance, qué es / qué no es | Secciones 1 y 2 | Cubierto |
| Modelo conceptual y tres capas (datos, análisis, IA) | 1, 4.1 | Cubierto |
| Fuentes de datos (CON130, Variance) | 2 (R1, R2), Fase 1 | Cubierto |
| Departamentos | 4.6 | Cubierto; centros de costo `[POR VALIDAR]` |
| Dimensiones y jerarquías | 4.3, 4.6 | Cubierto |
| Catálogo financiero y mapeo | 4.3, Fase 2 | Cubierto |
| Actuals | Fase 1 | Cubierto |
| Budget | Fase 3 (carga), Fase 7 (ciclo) | Cubierto |
| Variance, YTD, Annual Budget | Fase 3 | Cubierto |
| Comentarios | Fase 5 | Cubierto |
| Drill-down | Fase 4 | Cubierto |
| Forecast y rolling forecast | Fase 8 | Cubierto |
| Driver-based planning, spreading | Fases 7 y 9 | Cubierto |
| Escenarios | Fase 9 | Cubierto |
| Cash Flow | Fase 10 | Cubierto |
| Management Reporting | Fases 3 y 4 | Cubierto |
| Capital y estrategia | Fase 13 | Cubierto |
| Consolidación | Fase 11 (gerencial); legal fuera de alcance | Parcial, a propósito |
| Workflow, roles y permisos | Fase 5, sección 8 | Cubierto |
| Calidad de datos, trazabilidad | Fase 1.5, sección 8.8 | Cubierto |
| Integraciones | Sección 3, Fase 1 (archivo); conexión directa futura | Cubierto; API directa `[POR VALIDAR]` |
| Arquitectura, requerimientos tecnológicos | Secciones 3 y 4 | Cubierto |
| MVP y fases futuras | Sección 7 | Cubierto |
| Criterios de aceptación, riesgos, preguntas | 6.2, 9, 11 | Cubierto |
| Multi-hotel (Torres → Puerto Vallarta) | 4.4, Fase 11 | Cubierto |
| Casos futuros (compras, Recepción, opiniones, limpieza) | Después de la Fase 9, sección 7 | Cubierto como futuro |
| Planeación operativa diaria (Scandic) | Fase 14 | Cubierto |
| IA gobernada | Fase 12, 8.10 | Cubierto |
| Pruebas con Playwright | 9.1.1, Fase 0.5 | Cubierto |
