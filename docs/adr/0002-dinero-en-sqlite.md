# ADR 0002 — Dinero exacto también en SQLite

- **Fecha:** 30-sep-2026
- **Estado:** Aceptada

## Contexto
Los montos contables nunca pueden ser `float`. SQLite no tiene un tipo decimal exacto: SQLAlchemy convierte `Numeric` a float al guardar, lo que puede alterar centavos. Las pruebas y el desarrollo usan SQLite; producción usará PostgreSQL (`NUMERIC(18,2)`).

## Decisión
- Tipo propio `Dinero` (`fpa/modelos/tipos.py`): en PostgreSQL es `NUMERIC(18,2)`; en SQLite se guarda como **texto canónico** (`"1234.50"`).
- Rechaza `float` y montos con más de dos decimales.
- **Las sumas se hacen en Python con `Decimal`**, no con `SUM()` de SQL (en SQLite sumaría texto como número flotante).

## Consecuencias
- Los saldos mensuales y cualquier agregado se calculan en Python: portable y exacto. El volumen es pequeño (unos 7,000 movimientos por mes y hotel), así que el costo es bajo.
- Si en el futuro se agregan sumas en SQL sobre PostgreSQL por rendimiento, deben validarse contra el cálculo en Python.
- Probado con ejemplos y con una prueba de propiedades (`hypothesis`).
