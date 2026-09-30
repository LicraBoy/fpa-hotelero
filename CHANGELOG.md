# Changelog

## 0.1.0 — 2026-09-30 (Fase 0)
- Repositorio creado con estructura backend / frontend / docs / datos_prueba.
- Backend: FastAPI con `GET /api/health` y `GET /api/ready`, SQLite por configuración, CORS limitado al frontend local.
- Lector del reporte CON130 de Novohit (`backend/fpa/ingesta/novohit_con130.py`) trasladado al repositorio.
- Frontend: React + TypeScript + Vite con una pantalla que consulta la API.
- `iniciar_servidores.bat` para levantar todo en local (puertos 8100 y 5180).
- Documentación viva: `CLAUDE.md`, estado del proyecto, arquitectura, blueprint, ADR 0001 y cambios futuros de tecnología.
- Pruebas: 17 pasan (13 del lector del CON130 incluida la del archivo real, 4 de salud y CORS).
