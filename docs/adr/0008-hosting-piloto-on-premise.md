# ADR 0008 — Hosting del piloto: on-premise, Docker Compose listo para cuando TI defina destino

Estado: aceptada (Fase 6) · Fecha: 2026-10-22 · **Avisar a TI**

## Contexto
El plan (`docs/Arquitectura_Tecnica_FPA_Hotelero.md` §11) deja "dónde se aloja" como decisión abierta
de TI, y la Fase 6 la lista como precondición. TI no ha dado una fecha. Para no detener el piloto, se
toma una decisión interina que no cierra puertas: nada de lo que se construye en Fase 6 asume un
proveedor de nube específico.

## Decisión
1. El piloto sigue corriendo **on-premise**, en la misma PC/servidor de la empresa donde corre hoy
   (`iniciar_servidores.bat`), sin depender de un destino cloud.
2. Se prepara `docker-compose.yml` (API + PostgreSQL + frontend, ver ADR 0009) para que el cambio de
   máquina sea mecánico el día que TI defina destino — pero no se exige usarlo para el piloto.
3. Nada en el código asume rutas, nombres de host o credenciales de un proveedor de nube; todo sigue
   configurable por variables de entorno (`fpa/config.py`).

## Alternativas descartadas
- **Esperar a que TI decida**: deja el piloto sin fecha; el plan ya identificó este riesgo.
- **Elegir un proveedor de nube nosotros**: mayor compromiso del que corresponde tomar sin TI; se
  prefiere dejarlo abierto con Docker Compose listo en vez de atarlo a AWS/Azure/GCP.

## Qué debe saber TI
- Esto es una decisión **interina**, no definitiva — se revisita en cuanto TI tenga fecha/destino.
- El `docker-compose.yml` nuevo (Etapa 2) sirve igual on-premise (un solo servidor con Docker) que en
  cualquier nube; no hay trabajo perdido si TI decide después.

## Consecuencias
- La Fase 6.8 (puesta en producción) seguirá siendo on-premise hasta que esto cambie.
- El "ensayo de despliegue y reversa" de 6.8 se hace contra la máquina actual, no contra un entorno cloud.
