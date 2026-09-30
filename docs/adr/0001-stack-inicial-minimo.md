# ADR 0001 — Stack inicial mínimo

- **Fecha:** 30-sep-2026
- **Estado:** Aceptada (por el equipo; TI aún no ha opinado)

## Contexto
Hay que levantar un proyecto full stack sin decidir todavía la infraestructura corporativa. El equipo pidió usar lo básico para arrancar y hablar de las tecnologías nuevas más adelante, con TI.

## Decisión
- Backend: **Python 3.13 + FastAPI + SQLAlchemy 2**, con entorno propio (`backend/.venv`) y versiones fijas en `requirements.txt`.
- Base de datos: **SQLite** para desarrollo y pruebas; la URL sale de la variable `FPA_DATABASE_URL`.
- Frontend: **React + TypeScript + Vite**, con proxy de `/api` hacia el backend.
- Puertos propios: **8100** (API) y **5180** (web), para no chocar con otros sistemas del mismo equipo.
- Arranque local con `iniciar_servidores.bat`.
- Sin Docker, CI, autenticación, Alembic ni Playwright todavía.

## Alternativas consideradas
- Empezar ya con Docker, CI y PostgreSQL: descartado para la Fase 0 por pedido explícito de "lo básico"; queda como cambio futuro.
- Java/Spring y Oracle: no se eligen sin justificación y sin hablar con TI.

## Consecuencias
- Arranque rápido y simple.
- Riesgo: SQLite oculta diferencias con PostgreSQL. Mitigación: cambiar el motor solo por configuración, no escribir SQL propio de un motor, y correr las pruebas en ambos motores cuando se agregue PostgreSQL.
- La lista completa de cambios previstos está en `docs/CAMBIOS_FUTUROS_DE_TECNOLOGIA.md`.
