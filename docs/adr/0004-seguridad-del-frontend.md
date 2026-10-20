# ADR 0004 — Seguridad del frontend

Estado: aceptada (Fase 4.3) · Fecha: 2026-10-01

## Contexto
El frontend muestra cifras financieras y asientos con conceptos escritos por terceros (proveedores,
huéspedes). Un XSS ahí expondría datos de todo el hotel. Hoy la identidad es una cabecera de
desarrollo; TI definirá el inicio de sesión corporativo (OIDC).

> **Actualización (Fase 5.1, ADR 0005):** la sesión real ya existe y va en la cookie `HttpOnly` del punto 4; el punto 3 sigue vigente (nada de credenciales en el almacenamiento del navegador).

## Decisión
1. **CSP estricta, sin nada en línea.** El frontend se sirve con
   `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self';
   connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`
   más `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`.
   Sin `'unsafe-inline'` ni `'unsafe-eval'`: se usan clases CSS, nunca `style={{...}}`. La política
   vive en `frontend/vite.config.ts` (desarrollo: solo añade `'unsafe-inline'` por el refresco en
   caliente; `vite preview`: la de producción) y **debe replicarse en el proxy de producción** (TI).
   La API responde `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`,
   `Cache-Control: no-store` y `nosniff` en todo `/api` (`backend/fpa/seguridad/cabeceras.py`).
2. **Nada que inyecte HTML o ejecute texto.** Prohibidos `dangerouslySetInnerHTML`, `innerHTML`,
   `insertAdjacentHTML`, `document.write`, `eval`, `new Function` y `javascript:` (reglas de
   `oxlint` + `scripts/verificar_seguridad.mjs`, que corre en `npm run lint`). Todo texto de la API se
   muestra como texto de React (escapado).
3. **Credenciales fuera del almacenamiento del navegador.** Ni `localStorage` ni `sessionStorage` ni
   `document.cookie` guardan credenciales. La sesión vive en memoria (`src/api/sesion.ts`). La única
   excepción es la **preferencia** del usuario de desarrollo en `sessionStorage`
   (`src/util/preferencias.ts`, lista blanca), que no es un secreto y solo existe con
   `FPA_ENTORNO=desarrollo`.
4. **Con OIDC:** la sesión irá en una cookie `HttpOnly; Secure; SameSite=Strict` que el navegador
   envía solo; el JavaScript nunca verá el token. Si TI exige un token de portador, vivirá solo en
   memoria con renovación por cookie. Pendiente de la decisión de TI (Fase 5.1).
5. **Entrada de la barra de direcciones = entrada del usuario.** Las rutas por hash se validan con
   listas blancas de caracteres antes de usarse (`src/ruta/ruta.ts`).
6. **Dependencias de desarrollo únicamente:** `openapi-typescript` (tipos generados del OpenAPI) y
   `Schemathesis` (contrato de la API). Ninguna llega al navegador.

## Verificación automática
- `npm run lint` (reglas + verificador, con su propia prueba: `npm run test:unit`).
- `npm run e2e` corre **contra el build de producción con su CSP**: falla ante cualquier violación,
  script o estilo en línea, credencial en el almacenamiento o ruta maliciosa que ejecute código.
- `backend/tests/test_cabeceras_seguridad.py` para las cabeceras de la API.

## Consecuencias
- Un componente de terceros que use estilos en línea no se puede adoptar sin revisar esta política.
- Mostrar HTML de la API (p. ej. notas con formato) requeriría un sanitizador aprobado; hoy no hace
  falta: todo es texto.
