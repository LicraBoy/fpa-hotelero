# ADR 0005 — Identidad local con contraseña, TOTP y sesiones del servidor

Estado: aceptada (Fase 5.1) · Fecha: 2026-10-20 · **Avisar a TI** (nuevas dependencias abajo)

## Contexto
La Arquitectura previó OIDC con el proveedor de identidad de la empresa y, como respaldo, usuarios
locales con `argon2id` + TOTP. TI dio libertad de tecnología a cambio de que se le avise cuál se usa.
Hoy no hay un proveedor OIDC confirmado, la plataforma corre en una PC de la empresa sin permisos de
administrador y debe poder usarse sin depender de un servicio externo.

## Decisión
1. **Usuarios locales.** Entrada por usuario (correo) y contraseña. La contraseña se guarda solo como
   hash `argon2id` (`argon2-cffi`, parámetros por defecto RFC 9106; se rehace el hash si cambian).
   Política: mínimo 10 caracteres, letra y número, sin el nombre de usuario, sin claves comunes.
2. **Segundo factor TOTP opcional** (`pyotp`, app de autenticación). `FPA_MFA_ROLES_OBLIGATORIOS`
   permite exigirlo por rol (vacío por ahora `[POR VALIDAR con Contraloría/TI]`). El secreto TOTP se
   guarda en la base sin cifrar; cifrarlo con una llave de la aplicación queda como mejora.
3. **Sesiones del lado del servidor.** Al entrar se crea un token aleatorio (256 bits) que viaja en la
   cookie `fpa_sesion` (`HttpOnly`, `SameSite=Strict`, `Secure` configurable, ruta `/api`). La base
   guarda solo su SHA-256. Caduca a las 8 h sin uso y a las 12 h como máximo; se revoca al cerrar
   sesión, al cambiar la contraseña (las demás sesiones) o desde la base.
4. **Bloqueo:** 5 intentos fallidos seguidos bloquean la cuenta 15 minutos. Usuario inexistente,
   contraseña mala y código malo responden **lo mismo** (y tardan lo mismo: se verifica contra un hash
   de relleno). Todo intento queda en la bitácora.
5. **CSRF:** además de `SameSite=Strict`, un middleware rechaza (403) las peticiones que modifican
   datos, traen la cookie y vienen de un `Origin` fuera de `FPA_CORS_ORIGINS`.
6. **Desarrollo:** la cabecera `X-Usuario-Dev` sigue existiendo **solo** con `FPA_ENTORNO=desarrollo`;
   en producción no autentica (prueba). El primer usuario real se crea con
   `scripts/crear_contralor.py` (contraseña temporal que debe cambiarse al entrar; el mismo script
   restablece contraseñas y desbloquea cuentas).
7. **Frontend:** pantalla de entrada, "Mi cuenta" (contraseña y TOTP con clave y dirección
   `otpauth://`, sin librería de QR) y cierre de sesión. Nada en `localStorage`/`sessionStorage`; un
   401 con sesión real devuelve a la pantalla de entrada.

## Alternativas descartadas
- **OIDC con el proveedor de la empresa:** sigue siendo lo ideal, pero hoy no existe ni hay fecha. Queda
  detrás de la interfaz `ProveedorIdentidad`: se agregaría otro proveedor sin tocar el resto.
- **JWT en el navegador:** no se pueden revocar sin lista negra y el JavaScript podría leerlos.

## Qué debe saber TI
- Dependencias nuevas del backend: **`argon2-cffi` 25.1.0** y **`pyotp` 2.10.0** (ninguna en el frontend).
- Detrás de HTTPS la cookie lleva `Secure` (por defecto). Sin HTTPS en la red interna, `FPA_COOKIE_SEGURA=false`
  (menos seguro). Los tiempos y límites se ajustan con `FPA_SESION_INACTIVIDAD_MIN`, `FPA_SESION_MAXIMA_H`,
  `FPA_LOGIN_MAX_INTENTOS`, `FPA_LOGIN_BLOQUEO_MIN`, `FPA_PASSWORD_MIN_LARGO`.
- Si más adelante TI ofrece OIDC, la sustitución se hace en `fpa/identidad/proveedor.py`.

## Consecuencias
- Contraloría o TI deben custodiar el procedimiento de restablecer contraseñas (hoy, el script).
- Las sesiones y los intentos fallidos viven en la misma base (tabla `sesion`; migración `0016`).
