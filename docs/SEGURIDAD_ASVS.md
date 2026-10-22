# Revisión de seguridad — OWASP ASVS nivel 2 (Fase 6.1)

Checklist contra lo ya construido, hecha el 2026-10-22. Solo se marca "cumple" lo que existe y se pudo
verificar leyendo el código; lo demás queda como pendiente explícito. No sustituye un pentest (Fase 6.2).

## V1 — Arquitectura y diseño

| Punto | Estado | Evidencia |
|---|---|---|
| Separación cliente/servidor, API solo datos | Cumple | `fpa/seguridad/cabeceras.py`: `default-src 'none'` en toda `/api/*` |
| Decisiones de seguridad documentadas (ADR) | Cumple | `docs/adr/0004` a `0011` |
| Todo input no confiable se valida antes de usarse | Cumple (archivos); parcial (resto) | `fpa/seguridad/archivos.py` es fuerte; no se auditó input validation campo por campo en cada endpoint |

## V2 — Autenticación

| Punto | Estado | Evidencia |
|---|---|---|
| Contraseñas con hash lento (argon2id) | Cumple | ADR 0005, `argon2-cffi` |
| Política de longitud/complejidad mínima | Cumple | ADR 0005 (10+ caracteres, letra y número) |
| Bloqueo tras intentos fallidos | Cumple | `FPA_LOGIN_MAX_INTENTOS`/`FPA_LOGIN_BLOQUEO_MIN` (5 intentos / 15 min) |
| Mismo tiempo/respuesta para usuario inexistente vs contraseña mala | Cumple | ADR 0005 punto 4 (hash de relleno) |
| Segundo factor disponible | Cumple (opcional) | TOTP vía `pyotp`; obligatorio por rol **sin configurar todavía** (`FPA_MFA_ROLES_OBLIGATORIOS` vacío) |
| MFA obligatorio para roles sensibles | **Pendiente** | Depende de que Contraloría/TI decida qué roles — abierto desde ADR 0005 |

## V3 — Gestión de sesión

| Punto | Estado | Evidencia |
|---|---|---|
| Token de sesión aleatorio, no predecible | Cumple | 256 bits, `fpa/seguridad/sesiones.py` |
| Cookie `HttpOnly`, `SameSite=Strict` | Cumple | ADR 0005 |
| Cookie `Secure` en producción | Cumple (configurable) | `FPA_COOKIE_SEGURA`; **riesgo si queda en `false` en producción real sin HTTPS** |
| Expiración por inactividad y máxima | Cumple | 8h / 12h, `FPA_SESION_INACTIVIDAD_MIN`/`FPA_SESION_MAXIMA_H` |
| Revocación al cerrar sesión / cambiar contraseña | Cumple | ADR 0005 |
| Solo se guarda el hash del token, no el token | Cumple | ADR 0005 |

## V4 — Control de acceso

| Punto | Estado | Evidencia |
|---|---|---|
| Autorización por módulo en cada ruta | Cumple | `requiere(<modulo>)` en cada router (`tests/test_autorizacion_rutas.py` falla si falta) |
| Aislamiento de datos por hotel | Parcial | Filtrado por `hotel_id` en repositorios; **RLS a nivel de motor pendiente** (solo tiene sentido con Postgres, ADR 0009) |
| Principio de menor privilegio por rol | Cumple | Matriz `permisos_rol` (módulo 9, CLAUDE.md) |

## V5 — Validación, sanitización y codificación

| Punto | Estado | Evidencia |
|---|---|---|
| Validación de archivos subidos (extensión real, macros, zip-bomb, path traversal) | Cumple, fuerte | `fpa/seguridad/archivos.py` |
| Escaneo de malware real (firmas) | **Pendiente** | ADR 0011 (ClamAV) — diseñado, no implementado todavía |
| ORM parametrizado (sin SQL armado a mano) | Cumple | SQLAlchemy en todo el proyecto; `bandit` no encontró uso de SQL crudo con interpolación |
| Sin `eval`/deserialización insegura | Cumple | `bandit -r fpa` sin hallazgos (2026-10-22) |

## V7 — Manejo de errores y registro (logging)

| Punto | Estado | Evidencia |
|---|---|---|
| Los errores no filtran detalles internos al cliente | Parcial | No auditado endpoint por endpoint; FastAPI por defecto no filtra stacktraces en producción si `DEBUG` está apagado — confirmar `fpa/config.py` |
| Registro de eventos de seguridad (login, cambios de permisos) | Cumple | Bitácora con cadena de hashes, ADR 0006 |
| Registro estructurado con correlación (request id) | **Pendiente** | Hoy es `logging` suelto en 4 archivos — Fase 6.5 (observabilidad) |

## V8 — Protección de datos

| Punto | Estado | Evidencia |
|---|---|---|
| Credenciales nunca en `localStorage`/`sessionStorage` | Cumple | ADR 0004/0005 |
| Secretos fuera del repositorio | Cumple | `.env`, `FPA_RESPALDO_CLAVE` (ADR 0010) vía variables de entorno |
| Respaldo cifrado de la base | **Pendiente** | ADR 0010 — diseñado, no implementado (Fase 6.4) |
| TOTP secret cifrado en reposo | **Pendiente** | ADR 0005 lo marca como mejora futura, hoy sin cifrar |

## V9 — Comunicaciones

| Punto | Estado | Evidencia |
|---|---|---|
| CSP sin `unsafe-inline`/`unsafe-eval` en producción | Cumple | ADR 0004 |
| Cabeceras de seguridad (`X-Content-Type-Options`, `X-Frame-Options`, etc.) | Cumple | `fpa/seguridad/cabeceras.py`, `frontend/vite.config.ts` |
| HTTPS en producción | **Depende de TI/hosting** | ADR 0008 — no resuelto hasta que TI defina destino |

## V10 — Código malicioso

| Punto | Estado | Evidencia |
|---|---|---|
| Análisis estático de dependencias (SCA) | Cumple | `pip-audit` (0 hallazgos, 2026-10-22), `npm audit` (0 tras `npm audit fix`) |
| Análisis estático del código propio (SAST) | Cumple | `bandit -r fpa` (0 hallazgos) |
| Ejecutado en cada cambio (CI) | **Pendiente** | Hoy es manual; Fase 6.6 lo automatiza |

## V12 — Archivos y recursos

| Punto | Estado | Evidencia |
|---|---|---|
| Límite de tamaño en subidas | Cumple | `fpa/seguridad/archivos.py` |
| Sin ejecución de contenido subido | Cumple | Mismo archivo; PDFs con `/JavaScript`/`/Launch` se rechazan |
| Rate limiting general de la API | **Pendiente** | Solo existe para login (bloqueo de cuenta); no hay límite general por IP/usuario |

## V13 — API

| Punto | Estado | Evidencia |
|---|---|---|
| CSRF más allá de `SameSite` | Cumple | `fpa/seguridad/origen.py` (verificación de `Origin`) |
| Esquema de errores consistente | No auditado | — |
| Documentación de la API no expuesta sin control | Pendiente de revisar | `/docs` (Swagger) — confirmar si debe deshabilitarse en producción |

## Resumen de pendientes reales (no simulados, confirmados hoy)
1. MFA obligatorio por rol — decisión de Contraloría/TI, no técnica.
2. RLS por hotel en Postgres — depende de ADR 0009 (migración a Postgres).
3. Escaneo de malware (ClamAV) — ADR 0011, pendiente de implementar.
4. Logging estructurado con request id — Fase 6.5.
5. Respaldo cifrado — ADR 0010, pendiente de implementar.
6. Cifrado de secretos TOTP en reposo — mejora, no bloqueante.
7. CI que corra `pip-audit`/`bandit`/`npm audit`/`gitleaks` en cada cambio — Fase 6.6.
8. Rate limiting general de la API — no diseñado todavía, queda abierto para decidir alcance.
9. Confirmar si `/docs` (Swagger) debe apagarse en producción.
10. Confirmar `FPA_COOKIE_SEGURA` siempre en `true` en cualquier despliegue real.
