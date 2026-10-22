# ADR 0011 — ClamAV para escanear archivos subidos

Estado: aceptada (Fase 6) · Fecha: 2026-10-22 · **Avisar a TI**

## Contexto
`docs/Arquitectura_Tecnica_FPA_Hotelero.md` §11 deja abierto "¿Antivirus corporativo para archivos
subidos?". Hoy `fpa/seguridad/archivos.py` ya valida estructura (extensión real por bytes, rechaza
macros/zip-bombs/path-traversal/contenido activo en PDF) pero **no escanea el contenido contra firmas
de malware conocido** — es una validación de forma, no de firma.

## Decisión
1. Se usa **ClamAV** (motor libre, sin licencia, con daemon `clamd` + CLI `clamscan`/`clamdscan`).
2. Integración en `fpa/seguridad/archivos.py`: después de pasar las validaciones de estructura, el
   archivo se manda a `clamd` (vía socket; librería `python-clamd` o llamada directa) antes de guardarse
   en `storage/`. Si `clamd` no está disponible, el intento de subida falla (no se sube "por si acaso").
3. Base de firmas: `freshclam` corre como tarea periódica (diaria) para mantenerla actualizada.
4. Prueba: el archivo de prueba estándar EICAR (no es un virus real, es la cadena de prueba que
   reconocen todos los antivirus) debe ser rechazado por el endpoint de subida.

## Alternativas descartadas
- **Un antivirus corporativo pagado**: TI no ha dado ninguno; se prefiere no bloquear el piloto
  esperando esa decisión. Si TI define uno después, se sustituye `clamd` por el que corresponda detrás
  de la misma función de validación (un solo punto de inserción).
- **No escanear malware, solo validar estructura**: es lo que hay hoy; no cumple lo que pide la Fase 6.

## Qué debe saber TI
- Nuevo servicio en esta máquina: `clamd` (daemon) + `freshclam` (actualización de firmas) — necesita
  permisos para correr como servicio o tarea programada; sin permisos de administrador en esta PC (ver
  ADR 0005), puede que TI tenga que instalarlo o darnos ese permiso puntual.
- Si TI prefiere un antivirus corporativo ya licenciado, se reemplaza en un solo punto
  (`fpa/seguridad/archivos.py`), sin tocar el resto del flujo de subida.

## Consecuencias
- Toda subida de archivo pasa primero por `clamd`; si el daemon no responde, la subida se rechaza (no
  se degrada a "sin escanear").
- El ADR queda documentado antes de implementar, por si la instalación de `clamd` resulta bloqueada por
  los mismos permisos de administrador que ya afectan a este proyecto.
