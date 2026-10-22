# Runbook de despliegue y reversa (Fase 6.8)

Interino mientras TI no defina hosting (ADR 0008). Válido para el piloto on-premise actual; se
revisa en cuanto haya un destino distinto.

## Arrancar

1. `iniciar_servidores.bat` (raíz del repo) — levanta backend (8100) y frontend (5180) bajo
   `scripts/vigilante.ps1`, que los reinicia solos si se caen o no responden.
2. Confirmar: `http://127.0.0.1:8100/api/health` (backend) y `http://127.0.0.1:5180/` (frontend).
3. Antes de dar por bueno un arranque en limpio, correr el respaldo manual una vez
   (`scripts/respaldar_bd.py`, con `FPA_RESPALDO_CLAVE` puesta) para confirmar que la clave de
   respaldo de esa máquina funciona.

## Apagar

`detener_servidores.bat` (si existe en esa máquina) o cerrar las ventanas "Vigilante"; sin ellas,
matar los procesos en 8100 y 5180 por PID (`netstat -ano | findstr :8100`).

## Desplegar una actualización de código

1. Respaldo manual (`scripts/respaldar_bd.py`) **antes** de tocar nada — es la red de seguridad.
2. `git pull`.
3. Backend: `.venv\Scripts\pip install -r requirements.txt` (si cambiaron dependencias),
   `.venv\Scripts\alembic upgrade head` (migraciones).
4. Frontend: `npm install` (si cambió `package.json`), `npm run build` si se sirve el build de
   producción (no el `npm run dev`).
5. Reiniciar (`detener_servidores.bat` + `iniciar_servidores.bat`, o deja que el vigilante lo
   recoja solo si corre `--reload`).
6. Verificar: `/api/health`, `/api/ready` (confirma que la base responde), una pantalla real
   (Variance de un periodo conocido) antes de avisar que ya quedó.

## Plan de reversa

1. **Código**: `git checkout <commit-anterior>` (o `git revert`) + repetir el paso 3-5 de arriba.
2. **Migraciones**: `alembic downgrade -1` (una migración) o al `revision_id` anterior conocido —
   **probar esto en un ambiente de prueba antes de necesitarlo en serio**; no toda migración tiene
   un `downgrade()` ejercitado.
3. **Datos**: si la reversa de código/migración no basta (p. ej. una carga mala ya aprobada),
   `scripts/restaurar_bd.py` contra el respaldo cifrado más reciente de ANTES del cambio
   (ADR 0010) — esto reemplaza la base completa, úsalo solo si el problema es de datos, no de
   código.
4. Después de cualquier reversa: repetir la verificación del paso 6 de "Desplegar".

## Pendiente para el ensayo real (Fase 6.8)

- No se ha hecho un ensayo de despliegue+reversa cronometrado de principio a fin — este runbook es
  la base para hacerlo, pero falta ejecutarlo una vez y medir cuánto tarda cada paso.
- El runbook asume el hosting on-premise actual (ADR 0008); si TI define un destino distinto, se
  reescribe esta sección antes del piloto real.
