# ADR 0009 — PostgreSQL como motor de producción (no Oracle)

Estado: aceptada (Fase 6) · Fecha: 2026-10-22 · **Avisar a TI**

## Contexto
`docs/Arquitectura_Tecnica_FPA_Hotelero.md` §11 deja abierto "¿PostgreSQL es aceptable o la política
exige Oracle?". No hay ningún indicio en el proyecto de que Oracle sea un requisito corporativo, y la
arquitectura ya está construida pensando en Postgres como destino natural:
- `fpa/modelos/tipos.py` aísla el único caso especial de SQLite (dinero/medidas como texto exacto) y
  usa `NUMERIC` en cualquier otro dialecto — Postgres incluido, Oracle no necesitaría nada distinto
  tampoco, pero no hay nada ya preparado para Oracle (sintaxis, tipos, bitácora).
- `docs/bitacora_postgresql.sql` ya existe: revoca `UPDATE`/`DELETE` sobre la tabla de auditoría a nivel
  de motor, pensado específicamente para Postgres.
- `backend/tests/test_migraciones.py` ya tiene una prueba para Postgres (hoy se salta por falta de
  instancia), ninguna para Oracle.

## Decisión
1. El motor de producción es **PostgreSQL** (versión 16 o superior).
2. Se agrega el driver `psycopg[binary]` a `backend/requirements.txt`.
3. La suite de pruebas corre en **ambos** motores (SQLite para desarrollo rápido, PostgreSQL como
   verificación real) vía `FPA_TEST_POSTGRES_URL` — ya soportado por `test_migraciones.py`, se extiende
   al resto de la suite en la Etapa 2 de Fase 6 (CI).
4. Oracle queda descartado para esta fase; si TI lo exige más adelante, es un ADR nuevo y trabajo
   adicional (no hay nada de lo construido hoy que lo prepare).

## Alternativas descartadas
- **Oracle**: sin indicio de requerirlo, y con costo de licencia/operación que no se justifica sin que
  TI lo pida explícitamente.
- **Seguir solo con SQLite en producción**: no soporta el nivel de concurrencia ni el aislamiento por
  hotel (RLS) que el plan prevé para producción multi-hotel.

## Qué debe saber TI
- Nueva dependencia del backend: `psycopg[binary]` (sin versión fijada todavía; se fija al instalar).
- Se necesita una instancia de PostgreSQL 16+ para producción y, para CI, una efímera (contenedor).
- `docs/bitacora_postgresql.sql` debe aplicarse una vez contra la base de producción (revoca permisos
  de UPDATE/DELETE en la tabla de auditoría) — ver ADR 0006.

## Consecuencias
- El trabajo de la Etapa 2 (Fase 6.6) instala el driver, corre la suite completa contra Postgres real y
  monta CI con ambos motores.
- Si TI más adelante exige Oracle, este ADR se reemplaza por uno nuevo.
