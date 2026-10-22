# ADR 0010 — Política de respaldos: diario, cifrado, con restauración probada

Estado: aceptada (Fase 6) · Fecha: 2026-10-22 · **Avisar a TI**

## Contexto
`docs/Arquitectura_Tecnica_FPA_Hotelero.md` §11 deja abierto "¿Hay política de respaldos, RPO y RTO?".
Hoy **no existe ningún mecanismo de respaldo** en este proyecto (a diferencia de otros proyectos de la
empresa que sí lo tienen) — se investigó y confirmó antes de escribir este ADR. La Fase 6.4 del plan
exige "respaldo cifrado y restauración probada" con la prueba "restaurar y repetir [el mes] con
diferencia cero".

## Decisión
1. **RPO: 24 horas.** Respaldo automático diario (al iniciar el servidor y, si queda corriendo varios
   días, una vez al día) de la base completa.
2. **RTO: el que tarde restaurar el archivo + repetir el cierre del mes** — no hay un objetivo de
   minutos exigido todavía; se mide la primera vez que se hace el ensayo (Fase 6.4) y se documenta aquí
   después.
3. **Cifrado**: el respaldo se cifra con una clave simétrica leída de `FPA_RESPALDO_CLAVE` (variable de
   entorno, nunca en el repo ni en el respaldo mismo). Sin esa variable, el script falla en vez de
   respaldar sin cifrar.
4. **Rotación**: se conservan los últimos 14 respaldos (mismo criterio que otros proyectos de la
   empresa), borrando los más viejos.
5. **Restauración probada**: `scripts/respaldar_bd.py` tiene su contraparte `scripts/restaurar_bd.py`;
   la Fase 6.4 agrega una prueba que restaura el respaldo más reciente contra una base aparte y compara
   contra el original (diferencia cero).
6. Motor: hoy SQLite (copia de archivo + cifrado); cuando el motor de producción sea PostgreSQL (ADR
   0009), el respaldo pasa a `pg_dump` cifrado — mismo script, rama por dialecto.

## Alternativas descartadas
- **Respaldo sin cifrar**: el plan exige cifrado explícitamente; los datos son financieros reales.
- **Respaldo manual**: no cumple "automatizado y probado" que pide la Fase 6.

## Qué debe saber TI
- Nueva variable de entorno obligatoria para producción: `FPA_RESPALDO_CLAVE`.
- Los respaldos (cifrados) se guardan en `backend/backups/` — TI decide si además se copian a otro
  destino (red, nube) fuera de esta máquina; eso no está resuelto aquí.

## Consecuencias
- Sin `FPA_RESPALDO_CLAVE` configurada, el respaldo automático falla de forma visible (no silenciosa).
- El RTO real solo se conoce después del primer ensayo de restauración (Fase 6.4).
