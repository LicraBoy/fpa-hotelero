-- Bitácora de solo inserción en PostgreSQL (ADR 0006). NO aplica a SQLite.
-- Ejecutar con el usuario dueño del esquema, DESPUÉS de las migraciones de Alembic.
-- Sustituir fpa_app por el usuario con el que corre la API.

REVOKE UPDATE, DELETE, TRUNCATE ON TABLE evento_auditoria FROM fpa_app;
GRANT SELECT, INSERT ON TABLE evento_auditoria TO fpa_app;

-- Lo mismo para el historial de cierres (solo se inserta)
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE cierre_transicion FROM fpa_app;
GRANT SELECT, INSERT ON TABLE cierre_transicion TO fpa_app;

-- Y para las versiones del texto de los comentarios
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE comentario_revision FROM fpa_app;
GRANT SELECT, INSERT ON TABLE comentario_revision TO fpa_app;

-- La cadena de hashes necesita que un solo proceso escriba a la vez por organización. En auditar():
--   SELECT pg_advisory_xact_lock(organizacion_id);
-- antes de leer el último hash. [PENDIENTE al migrar a PostgreSQL]
