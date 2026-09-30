# ADR 0003 — Carga vigente por periodo, aislamiento y identidad de desarrollo

- **Fecha:** 30-sep-2026
- **Estado:** Aceptada (la identidad de producción queda por validar con TI)

## Decisiones

**1. Una carga vigente por (hotel, periodo).** Un archivo con dos meses (p. ej. el Excel del Variance, julio y agosto) genera dos cargas con el mismo SHA-256. Así no se suma dos veces el mismo mes si llegan el CON130 y el Variance. Recargar un periodo con otro archivo pide confirmación; al confirmar, la carga anterior pasa a `reemplazada` (se conserva el historial) y se audita.

**2. Idempotencia por hash.** El mismo archivo con los mismos periodos no cambia nada. Las filas repetidas exactas existen legítimamente en los datos (5 en el Variance, 14 en el CON130), por eso **no** se usan como clave ni se rechazan: generan un aviso.

**3. Aislamiento.** Todo dato de negocio lleva `hotel_id`. Un usuario solo accede a los hoteles con `Asignacion`. Respuestas:
- sin sesión → **401**;
- hotel al que no tiene acceso (ajeno o inexistente) → **404**, idéntica en ambos casos para no revelar si el hotel existe;
- hotel propio pero sin el permiso → **403**.

**4. Identidad de desarrollo segura por defecto.** `FPA_ENTORNO` vale `produccion` por defecto: en ese modo nadie se autentica (`ProveedorNoConfigurado`) hasta que TI defina OIDC. Solo con `FPA_ENTORNO=desarrollo` se habilita la cabecera `X-Usuario-Dev`. El proveedor real se enchufa implementando `ProveedorIdentidad`, sin tocar el resto.

**5. Permisos por rol en código** (`fpa/identidad/permisos.py`): contralor, analista, responsable de área, dirección y auditoría. Es una propuesta del Blueprint §30 `[POR VALIDAR con Contraloría]`.

## Consecuencias
- Un error de configuración deja el sistema cerrado, no abierto.
- Las pruebas de aislamiento corren hoy en SQLite; Row Level Security de PostgreSQL se suma como defensa adicional cuando exista ese motor.
