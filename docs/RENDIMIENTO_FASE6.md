# Fase 6.3 — Resultado de la prueba de carga/rendimiento

Medido el 2026-10-22 contra el backend de desarrollo (`iniciar_servidores.bat`, un solo proceso
uvicorn con `--reload`, SQLite), hotel Torres Mazatlán, periodo 2026-08 (mapeo v7 aprobado, Budget
vigente). Script: `backend/scripts/prueba_de_carga.py`.

## Contra los objetivos de §4.5

| Objetivo (`[PROPUESTA]`, §4.5) | Medido | Resultado |
|---|---|---|
| Variance mensual con caché: p95 < 500 ms | p50 = 10 ms, p95 = 11 ms | **Cumple**, con margen amplio |
| Variance mensual sin caché: p95 < 2 s | p50 = 11 ms, p95 = 17 ms | **Cumple**, con margen amplio |
| Carga de un CON130 de 10 mil filas: < 10 s | — | **No medido hoy** (ver pendiente abajo) |
| 50 usuarios concurrentes sin degradar | línea base 12 ms → mediana con 50 a la vez: **2,237 ms** (183×) | **No cumple** |

## Hallazgo: el servidor de desarrollo no aguanta 50 peticiones a la vez

No es un problema de las consultas (Variance en sí es rapidísimo, 10-17 ms). El cuello de botella
es el servidor: `iniciar_servidores.bat` arranca **un solo proceso uvicorn** (`--reload`, pensado
para desarrollo) y FastAPI corre los endpoints síncronos (los que usan `Session` de SQLAlchemy,
que es síncrona) en el *threadpool* por defecto de `anyio` — tope de **40 hilos**. Con 50
peticiones a la vez, 10 se quedan en cola esperando un hilo libre antes de ejecutarse; de ahí el
salto de 12 ms a >2 s.

**Esto es esperable en modo desarrollo y no refleja cómo se desplegaría en producción.** Mitigación
para el piloto (Fase 6.8, cuando se decida hosting — ADR 0008):
1. Correr uvicorn con varios workers (`--workers 4`, sin `--reload`) o detrás de un proxy que
   reparta a varios procesos — cada proceso tiene su propio threadpool de 40.
2. Si no basta, subir el límite del threadpool (`anyio.to_thread.current_default_thread_limiter`)
   o mover las rutas más pedidas a sesión async de SQLAlchemy (cambio más grande, no se hizo hoy).

No se tocó nada de esto hoy — es un hallazgo de la medición, no un cambio de arquitectura; se deja
para cuando se decida cómo se despliega en producción.

## Pendiente: carga de 10 mil filas

No se midió hoy el tiempo de carga de un CON130 de 10 mil filas: generar un archivo sintético
válido para `fpa/ingesta/novohit_con130.py` sin un ejemplo real de Novohit de ese tamaño es
arriesgado (un archivo mal formado no mide nada real). Se necesita un CON130 real de ~10 mil filas
(o uno de Torres recortado/replicado) para medirlo correctamente — queda pendiente de la próxima
pasada de Fase 6.3.
