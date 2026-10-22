# Traspaso para continuar en otro chat (22-oct-2026)

Pega esto (o dile al asistente que lo lea) al empezar el chat nuevo. Repositorio:
`C:\Users\mzamora\Desktop\fpa-hotelero`, rama `main`, último commit `8f464e3`, árbol limpio salvo
cambios de imágenes sin relación (`docs/imagenes/`, del usuario, no tocar sin preguntar).
**Este documento reemplaza a `docs/TRASPASO_OCTUBRE_2026.md` (ya desactualizado — todo lo que
bloqueaba ahí ya se resolvió).**

## 1. Qué pasó desde el traspaso anterior

- **El mapeo completo de cuentas de Contraloría ya se aplicó** (Mapeo v7, 715 vínculos) —
  resuelto buscando por código en "PESO COMPARATIVO MZT" y agrupando las cuentas sin línea propia
  en la línea genérica existente de su sección (sin tocar la estructura del reporte ni el Budget).
  **Falta que el Contralor revise y confirme el Variance con ese mapeo** — eso sigue pendiente, es
  lo único que falta de la Fase 2 (y de la 6.7, ver abajo).
- **Se hizo toda la Fase 6 que no depende de actores externos** (ver §3). Las decisiones de TI
  (hosting, PostgreSQL, respaldos, antivirus) se tomaron por cuenta propia en vez de esperar a TI,
  documentadas como ADR 0008-0011.
- **Se actualizó `docs/FASES_FUTURAS.md`** con una revisión externa de gobierno/control (requisitos
  transversales, detalle de las Fases 7-14, criterios de aceptación) y con referencias al nuevo
  `docs/Anexo_Futuro_Capa_Datos_Operativos_Hoteleros.md` (PMS/Cloudbeds, condicional, no priorizado).
- **Se diseñó (sin programar) la Fase 7 — Budget**: `docs/DISENO_FASE7_BUDGET.md`.
- El rediseño del frontend (Variance, Budget, Por departamento) sigue donde quedó — no se tocó en
  esta sesión salvo exponer el Vite a la red (`frontend/vite.config.ts`, `host: true`) y un
  vigilante nuevo (`scripts/vigilante.ps1`, `iniciar_servidores.bat` actualizado) para levantar
  backend+frontend de forma resiliente.

## 2. Qué es el proyecto

Sin cambios respecto al traspaso anterior — ver ahí §2, o `docs/VISION_DEL_PRODUCTO.md` /
`docs/contexto.md`. Pila: backend FastAPI + SQLAlchemy 2 + SQLite (Postgres ya soportado en
pruebas, ver §3) + Alembic (puerto 8100); frontend React 19 + TS + Vite (puerto 5180).

## 3. Estado de las fases

| Fase | Estado |
|---|---|
| 0 a 5 | Hechas |
| **6** | **Casi cerrada** — todo hecho salvo 6.2 (pentest, externo) y 6.7 (acta de aceptación del Contralor, pendiente) |
| **7** | **Diseñada** (`docs/DISENO_FASE7_BUDGET.md`), sin programar — abierta en paralelo sin esperar a que 6.2/6.7 cierren formalmente, por decisión del usuario |
| 8 a 15 | Pendientes, con más detalle que antes en `docs/FASES_FUTURAS.md` (requisitos transversales + lo que señaló la revisión externa por fase) |

**Fase 6, en una línea cada sub-fase:**
- **6.1 Seguridad:** 4 ADR nuevos (0008 hosting, 0009 PostgreSQL, 0010 respaldos, 0011 ClamAV);
  `pip-audit`/`bandit`/`npm audit` sin hallazgos; checklist OWASP ASVS L2 en
  `docs/SEGURIDAD_ASVS.md`; ClamAV integrado en código (`fpa/seguridad/archivos.py`) pero
  **apagado en esta máquina** (`FPA_CLAMAV_ACTIVO=false` en pruebas, sin `clamd` instalado por
  falta de permisos de administrador — se activa solo al instalar `clamd` en otra máquina).
- **6.2 Pentest:** no hecho, necesita pentester externo.
- **6.3 Carga/rendimiento:** `scripts/prueba_de_carga.py`. Variance cumple de sobra (p95 11-17 ms).
  Hallazgo real: 50 peticiones concurrentes degradan 183× en el servidor dev de un solo proceso
  (límite de threadpool, no de las consultas) — `docs/RENDIMIENTO_FASE6.md`. Falta medir carga de
  10 mil filas (necesita un CON130 real de ese tamaño).
- **6.4 Respaldos:** `backend/scripts/respaldar_bd.py` / `restaurar_bd.py`, cifrados (Fernet,
  `FPA_RESPALDO_CLAVE`), rotación a 14, ensayo de restauración real hecho (diferencia cero, 29
  tablas comparadas por hash de datos).
- **6.5 Observabilidad:** `fpa/observabilidad/` (logging JSON con `request_id`, métricas
  Prometheus en `/api/metrics`, alerta mínima por webhook o log crítico).
- **6.6 PostgreSQL y CI:** driver `psycopg` instalado; suite de pruebas corre en ambos motores
  (`FPA_TEST_POSTGRES_URL`, ver `tests/conftest.py::engine`) — **no se probó contra un Postgres
  real todavía** (Docker Desktop no se levantó en esta máquina, quedó pendiente); workflow
  `.github/workflows/ci.yml` listo, **no corre hasta que exista un repositorio remoto**.
- **6.7 Aceptación de Contraloría:** pendiente (ver §1).
- **6.8 Puesta en producción:** `docs/RUNBOOK_DESPLIEGUE.md` (arranque, despliegue, reversa);
  falta el ensayo cronometrado real.

**Suite completa al cierre de esta sesión:** 794 pruebas pasan, 2 se saltan (necesitan Postgres
real), 0 fallos. `ruff`/`mypy`/`bandit`/`pip-audit`/`npm audit` limpios.

## 4. Documentos que leer primero (en este orden)

1. Este documento.
2. `docs/FASES_FUTURAS.md` (roadmap actualizado — requisitos transversales + detalle por fase).
3. `docs/DISENO_FASE7_BUDGET.md` (si la tarea es empezar a programar Budget).
4. `docs/SEGURIDAD_ASVS.md`, `docs/RENDIMIENTO_FASE6.md`, `docs/RUNBOOK_DESPLIEGUE.md` (detalle de
   Fase 6, solo si la tarea toca eso).
5. `docs/ESTADO_DEL_PROYECTO.md`, `docs/RESUMEN_DEL_FRONTEND.md`, `docs/VISION_DEL_PRODUCTO.md` —
   igual que antes, para contexto general.
6. `docs/adr/0001` a `0011` (las 0008-0011 son nuevas de esta sesión).

## 5. Pendiente

**De Contraloría (bloquea 6.7, y por lo tanto el cierre formal de la Fase 6):**
- Revisar y confirmar el Variance con el Mapeo v7.
- 1 cuenta sin resolver: `4003001.002` → el código real es `4003001.02` (ya en el catálogo) pero
  sin tipo Deudor/Acreedor asignado.
- 3 códigos nunca encontrados en ningún lado: `1002009`, `1002002`, `5001002`.
- Las preguntas de `docs/FASES_FUTURAS.md` → "Decisiones pendientes que afectan estas fases" siguen
  abiertas (año fiscal, clave única de línea, árbol de departamentos, etc.) — varias las necesita
  ya el diseño de la Fase 7 (ver `docs/DISENO_FASE7_BUDGET.md` §8).

**De TI:**
- Firewall de Windows: puerto 5180 bloqueado para acceso en red local — necesita que alguien con
  permisos de administrador corra `netsh advfirewall firewall add rule name="FPA Hotelero Vite
  5180" dir=in action=allow protocol=TCP localport=5180 profile=private` en esta máquina.
- `clamd` (antivirus, ADR 0011) necesita instalarse en la máquina real de producción — aquí no se
  pudo por falta de permisos de administrador.
- Repositorio remoto: sin esto, el CI (`.github/workflows/ci.yml`) no corre nunca.
- Las 4 decisiones de TI que se tomaron sin esperar (ADR 0008-0011) deben avisarse formalmente a
  TI tarde o temprano — son interinas, no definitivas.

**Del usuario:**
- Decidir si se sigue con el pentest (6.2) por cuenta propia (herramienta automatizada tipo OWASP
  ZAP) o se espera a un externo.
- Cuando Contraloría confirme el mapeo: avisar para cerrar formalmente la Fase 6 y reabrir la
  pregunta de si la Fase 7 ya puede "abrirse" del todo (hoy solo está diseñada, no programada, por
  decisión explícita de avanzar en paralelo).

## 6. Cómo operar (sin cambios importantes respecto al traspaso anterior)

- **Arrancar:** `iniciar_servidores.bat` (actualizado esta sesión — ahora usa
  `scripts/vigilante.ps1`, dos ventanas "Vigilante" que reinician solas si algo se cae o el puerto
  queda ocupado). Primera vez tarda varios minutos (migración + siembra).
- **Exponer a la red:** `frontend/vite.config.ts` ya tiene `host: true` — `npm run dev` solo ya
  queda en `0.0.0.0:5180`. Falta la regla de firewall (ver §5) para que se pueda conectar desde
  otra máquina.
- **Respaldo manual:** `FPA_RESPALDO_CLAVE=<clave> .venv\Scripts\python scripts\respaldar_bd.py`
  (generar una clave nueva con `python -c "from cryptography.fernet import Fernet;
  print(Fernet.generate_key().decode())"` si no hay una ya elegida para esta máquina).
- Resto de comandos (pytest, ruff, mypy, npm) igual que antes — ver traspaso anterior §8 si hace
  falta el detalle exacto.

## 7. Preferencias del usuario

Igual que antes: respuestas cortas y claras en español, sin saturar de detalle; decidir por
defecto lo razonable, preguntar antes de lo irreversible o lo que sale del equipo. **Nuevo en esta
sesión:** el usuario prefiere avanzar en paralelo en vez de esperar bloqueos externos (TI,
Contraloría) cuando es razonable hacerlo — toma la decisión él mismo y lo documenta como ADR o nota
explícita, en vez de detener el trabajo. Cuando un bloqueo es real (permisos de administrador,
pentest externo, firma de Contraloría), lo dice claro y sigue con lo que sí se puede.

## 8. Primer mensaje sugerido para el chat nuevo

«Lee `docs/TRASPASO_OCTUBRE_2026_v2.md`, `docs/FASES_FUTURAS.md` y `docs/DISENO_FASE7_BUDGET.md`.
El mapeo ya se aplicó (v7), falta que el Contralor lo confirme. La Fase 6 está casi cerrada (solo
faltan pentest y la aceptación del Contralor). Vamos a [programar la Fase 7 / lo que sigue].»
