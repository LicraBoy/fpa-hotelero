# Changelog

## Fase 1 (en curso)

### 1.9 — Catálogo oficial de cuentas, CON020 (2026-09-30)
- Lector `.xls` (`xlrd`, solo lectura) del reporte "Catálogo Contable" de Novohit: ignora los encabezados que se repiten por página, normaliza títulos con letras espaciadas (`B A N C O S` → `BANCOS`) y corrige la Ñ exportada como `¥`.
- `cuenta_local` ampliada (migración `0006`): TIPO (Deudor/Acreedor), grupo del estado financiero, departamento, DPTO. TI, cuenta de terceros, código SAT, auxiliar, activa y `en_catalogo_oficial`.
- `importar_catalogo`: el catálogo oficial manda en nombre y clasificaciones; recalcula la jerarquía; idempotente; reporta cuentas con movimientos que no están en el catálogo.
- Nuevos controles de calidad (avisos): cuentas fuera del catálogo oficial y movimientos en cuentas inactivas.
- `POST /api/v1/hoteles/{id}/catalogo/importar` (permiso `catalogo:importar`: contralor y analista) con seguridad propia para `.xls` (firma OLE2, sin macros, tamaño máximo). El árbol devuelve tipo, departamento, grupo y SAT.
- Pantalla: importar el catálogo y ver nombres, Deudor/Acreedor, departamento y código SAT; búsqueda también por esos campos.
- Con el catálogo real: 1,306 nodos (1,238 cuentas + 68 títulos), 366 de 366 cuentas de septiembre, 87 cuentas del Variance fuera del catálogo; 0 nodos sin descripción.
- Validación: el signo del Variance coincide con TIPO (Acreedor resta, Deudor suma) en todos los casos del Excel.
- Pruebas: 239 del backend y 11 de navegador.

### Frontend de la Fase 1 y Playwright (2026-09-30)
- Pantallas de Cargas (con aviso y confirmación de reemplazo y reporte de calidad), Catálogo (árbol con búsqueda), Saldos (total exacto) y Auditoría; secciones según el rol.
- Importes como texto y sumas en centavos con `BigInt`.
- La pantalla y el script de arranque esperan a la API; la tabla de reemplazo compara también el Crédito.
- Playwright: 10 pruebas de navegador contra un backend limpio propio (`backend/scripts/servidor_e2e.py`) con Excel sintéticos (`backend/scripts/crear_archivos_e2e.py`).
- `vite.config.ts` toma la API y el puerto de variables (`FPA_API_URL`, `FPA_WEB_PUERTO`).

### 1.8 — API de carga segura (2026-09-30) — cierra la Fase 1
- `POST /api/v1/hoteles/{id}/cargas` (archivo `.xlsx`, `fuente`, `confirmar_reemplazo`, `periodos` opcional). Respuestas: 201 creada/reemplazada, 200 duplicada, 409 requiere confirmación, 422 rechazada por calidad o lectura, 400/413/415 archivo inválido, 401/403/404.
- `fpa/seguridad/archivos.py`: solo `.xlsx`; tamaño máximo por bloques; firma ZIP; sin macros, sin cifrado, sin rutas con `..`; límites anti zip-bomb (entradas, tamaño descomprimido real, razón de compresión) medidos con los Excel reales.
- El nombre original nunca forma parte de una ruta; el archivo se guarda como `storage/cargas/<hotel>/<sha256>.xlsx`; los temporales se borran y los huérfanos se limpian.
- Todo rechazo de archivo queda en la auditoría (`carga.archivo_rechazado`).
- `GET /cargas`, `GET /cargas/{id}` (con el reporte de calidad) y `GET /auditoria` (contralor y auditoría).
- Corregido: los lectores abren el archivo ellos mismos para que siempre se cierre (en Windows un archivo abierto no se puede borrar).
- Prueba de salida de la Fase 1 por la API con los Excel reales, y en vivo con el servidor.
- Pruebas: 195 pasan y 1 se salta.

### 1.7 — Saldos mensuales (2026-09-30)
- `SaldoMensualCuenta` (migración `0005`): Débito, Crédito y número de movimientos por cuenta, hotel y periodo; Resultado = Débito − Crédito.
- `recalcular_saldos`: desde la carga vigente, en Python con `Decimal`, idempotente; se invoca al cargar o reemplazar. Sin carga vigente no hay saldos.
- Pruebas de propiedades (`hypothesis`): suma de saldos = suma de movimientos, el orden no importa, agregar por partes = agregar todo.
- `GET /api/v1/hoteles/{id}/saldos?periodo=AAAA-MM` (permiso `saldos:leer`; importes como texto exacto).
- Con el CON130 real: los 366 saldos coinciden con la fila "Total" de cada cuenta del reporte.
- Pruebas: 164 pasan y 1 se salta.

### 1.6 — Catálogo local (2026-09-30)
- `CuentaLocal` (migración `0004`): código, descripción, clase, nivel, padre, `con_movimientos`, `es_titulo`, `sin_jerarquia`. Se acumula entre cargas y recalcula la jerarquía de todas las cuentas conocidas.
- Padre = título más largo que sea prefijo del código (o el código base de una subcuenta con punto). Con el CON130 real: 145 títulos + 366 cuentas = 511 nodos, todas las cuentas con ancestro.
- Un código puede ser cuenta con movimientos y título a la vez (`4002007`); el catálogo lo soporta.
- `cargar_archivo` actualiza el catálogo en la misma transacción y usa las cuentas conocidas para avisar de cuentas nuevas.
- `GET /api/v1/hoteles/{id}/catalogo/arbol` (permiso `catalogo:leer`, 404 para hoteles ajenos).
- Pruebas: 150 pasan y 1 se salta.

### 1.5 — Calidad de datos (2026-09-30)
- `fpa/calidad/evaluacion.py` (funciones puras): errores que rechazan la carga (errores de lectura, Débito ≠ Crédito en el CON130, total de cuenta que no coincide, fechas fuera del periodo del encabezado o del declarado) y avisos que se guardan (cuentas nuevas, filas repetidas, importes negativos, Débito y Crédito a la vez, asiento que no corresponde al mes, avisos del lector).
- El reporte completo se guarda en `CargaArchivo.controles` y los rechazos explican qué falló y con ejemplos.
- Medido con los archivos reales: filas repetidas (14 y 5) e importes negativos (257 y 92) son legítimos, por eso son avisos.
- Un CON130 real alterado a propósito (un Débito cambiado; una fecha fuera de periodo) es rechazado.
- Pruebas: 136 pasan y 1 se salta.

### 1.4 — Idempotencia, reemplazo y auditoría (2026-09-30)
- `cargar_archivo`: mismo archivo = `duplicada` (no cambia nada); otro archivo para un periodo ya cargado = `requiere_confirmacion` (sin escribir); al confirmar, la carga anterior pasa a `reemplazada` (historial conservado); lecturas inválidas = `rechazada`.
- Un archivo de varios meses reemplaza solo los periodos que chocan y omite los que ya eran idénticos.
- `EventoAuditoria` de solo inserción (modificar o borrar lanza `AuditoriaInmutable`); eventos `carga.creada`, `carga.duplicada`, `carga.rechazada`, `carga.reemplazada` con usuario, hotel y detalle. Migración `0003`.
- Si el reemplazo falla a la mitad, la carga anterior sigue vigente.
- Pruebas: 109 pasan y 1 se salta.

### 1.3 — Persistencia de cargas (2026-09-30)
- Modelos `CargaArchivo` (una por archivo y periodo; una sola vigente por hotel y periodo, garantizado por un índice parcial) y `Movimiento`. Migración `0002`.
- Tipo `Medida` (hasta 6 decimales exactos) para cantidades y costos unitarios.
- `registrar_carga`: todo o nada dentro de un SAVEPOINT; rechaza lecturas sin fuente, sin movimientos o con errores.
- `RepositorioCargas`: exige `hotel_id`; los cálculos leen solo la carga vigente de cada periodo.
- Con los Excel reales: Variance = 2 cargas (3,583 + 3,277); CON130 = 1 carga (7,242). Los textos reales caben en las columnas.
- Pruebas: 97 pasan y 1 se salta.

### 1.2 — Lector del Excel de Variance (2026-09-30)
- `fpa/ingesta/variance_base_datos.py`: lee la hoja "Base de Datos" (julio + agosto) por nombre de columna, tolerando los caracteres dañados de Débito/Crédito.
- Sin control Débito = Crédito (es un subconjunto de cuentas de resultados). Cantidad y costo se conservan con todos sus decimales.
- Avisos (no errores): mes en texto distinto al de la fecha, cuenta con dos nombres, movimiento sin importe (fila 4389).
- Prueba dorada: 6,860 movimientos (3,583 julio + 3,277 agosto), 296 cuentas, Débito 12,650,614.04 y Crédito 12,037,735.88.
- Pruebas: 76 pasan y 1 se salta.

### 1.1 — Contrato común de lectura (2026-09-30)
- `fpa/ingesta/contrato.py`: `Movimiento` (con `cantidad` y `costo` opcionales), `Cuenta`, `Titulo`, `ResultadoLectura` (periodos, rango de fechas, `controla_balance`) y `Fuente`.
- `fpa/ingesta/utilidades.py`: conversiones comunes (montos con comas, fechas dd/mm/aaaa).
- El lector del CON130 devuelve también los 145 títulos de la jerarquía de cuentas.
- Pruebas: 62 pasan y 1 se salta.

### 1.0 — Cimientos de datos (2026-09-30)
- Herramientas de calidad: `ruff` (estilo) y `mypy` estricto, configurados en `backend/pyproject.toml`.
- Modelos `Organizacion`, `Hotel`, `Usuario`, `Rol`, `Asignacion` y el tipo `Dinero` (decimales exactos también en SQLite).
- Alembic con la migración `0001`; prueba de que sube, baja y no se desvía de los modelos.
- Identidad: proveedor de desarrollo (cabecera `X-Usuario-Dev`), cerrado por defecto (`FPA_ENTORNO=produccion`).
- Permisos por rol y dependencias `principal_actual` y `hotel_autorizado` (401 / 403 / 404).
- Endpoints `GET /api/v1/yo`, `GET /api/v1/hoteles`, `GET /api/v1/hoteles/{id}`.
- `python -m fpa.semilla` (idempotente) y `iniciar_servidores.bat` ahora migra, siembra y arranca.
- ADR 0002 (dinero en SQLite) y ADR 0003 (carga vigente por periodo, aislamiento e identidad de desarrollo).
- Pruebas: 54 pasan y 1 se salta (migración en PostgreSQL).

## 0.1.0 — 2026-09-30 (Fase 0)
- Repositorio creado con estructura backend / frontend / docs / datos_prueba.
- Backend: FastAPI con `GET /api/health` y `GET /api/ready`, SQLite por configuración, CORS limitado al frontend local.
- Lector del reporte CON130 de Novohit (`backend/fpa/ingesta/novohit_con130.py`) trasladado al repositorio.
- Frontend: React + TypeScript + Vite con una pantalla que consulta la API.
- `iniciar_servidores.bat` para levantar todo en local (puertos 8100 y 5180).
- Documentación viva: `CLAUDE.md`, estado del proyecto, arquitectura, blueprint, ADR 0001 y cambios futuros de tecnología.
- Pruebas: 17 pasan (13 del lector del CON130 incluida la del archivo real, 4 de salud y CORS).
