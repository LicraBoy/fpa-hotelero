# ADR 0006 — Bitácora con cadena de hashes

Estado: aceptada (Fase 5.5) · Fecha: 2026-10-20

## Contexto
La bitácora ya no permitía modificar ni borrar eventos **desde la aplicación** (eventos de
SQLAlchemy). Quien tuviera acceso directo a la base de datos sí podía alterarla sin que nadie lo
notara. La salida de la Fase 5 pide poder reconstruir «quién cambió qué cifra y cuándo» con la
seguridad de que ese rastro no se editó.

## Decisión
1. **Cadena por organización.** Cada evento guarda `hash` = SHA-256 de su contenido canónico y
   `hash_previo` = el hash del evento anterior de la misma organización (el primero usa 64 ceros).
   El contenido firmado es: hash previo, organización, hotel, usuario, acción, entidad, id de la
   entidad, detalle (JSON con llaves ordenadas) y fecha en UTC con microsegundos. El `id` no se firma.
2. **Un solo punto de escritura.** Todo evento nace en `servicios/auditoria.auditar`, que escribe lo
   pendiente, busca el último hash y sella el evento nuevo. Una prueba recorre todas las rutas que
   escriben y falla si alguna no deja evento (o no está declarada como delegada en un servicio).
3. **Verificación.** `GET /hoteles/{id}/auditoria/verificar` (Contralor y Auditoría) recorre la
   cadena y responde si está íntegra, cuántos eventos tiene, el primer evento alterado y el motivo
   («cambió su contenido» o «falta un evento»). La pantalla de Auditoría muestra «Cadena íntegra» o
   «Cadena alterada».
4. **Lo que la cadena no puede probar sola:** que se hayan borrado los **últimos** eventos. Por eso la
   verificación devuelve el último hash: conviene anotarlo aparte (p. ej. en el acta de cada cierre
   o en un correo mensual); si luego no coincide con el que muestra el sistema, faltan eventos.
5. **Eventos anteriores a la 5.5.** La migración `0020` los selló en orden. Desde ahí se puede
   demostrar que no cambiaron; **antes de esa fecha nada lo prueba**.
6. **Concurrencia.** Con SQLite (un solo escritor) la cadena no se bifurca. Con PostgreSQL hay que
   serializar la escritura de la cadena (bloqueo consultivo por organización) antes de usar más de
   un proceso de la API `[PENDIENTE de la migración a PostgreSQL]`.
7. **PostgreSQL.** Además, al migrar se quita `UPDATE` y `DELETE` sobre `evento_auditoria` al
   usuario de la aplicación: ver `docs/bitacora_postgresql.sql`.

## Alternativas descartadas
- **Firmar con una llave secreta (HMAC):** protegería contra quien recalcule la cadena completa,
  pero exige custodiar una llave; queda como mejora `[POR VALIDAR con TI]`.
- **Anclar el hash en un servicio externo:** fuera de alcance; el procedimiento manual del punto 4
  cumple mientras tanto.

## Historial de la cifra
En el panel de cada línea, `GET /hoteles/{id}/variance/lineas/{id}/historial` arma la cronología de
lo que afectó la cifra: cargas de los meses del acumulado (con su hash), cambios al mapeo de esa
línea y versiones aprobadas, capturas manuales, comentarios y cambios de estado del cierre. Quien
tiene el acceso limitado a sus secciones solo ve comentarios, capturas y cambios de mapeo de su línea.
