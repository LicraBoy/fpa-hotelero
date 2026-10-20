# Visión integral del producto (requisito permanente)

La aplicación forma parte de una plataforma SaaS de **Inteligencia Integral para Hoteles**. No debe
concebirse como un sistema exclusivamente contable ni como un dashboard aislado.

A largo plazo conectará información de Habitaciones, Recepción, Revenue, Alimentos y Bebidas, Ama de
Llaves, Mantenimiento, Compras, Almacenes, Recursos Humanos, Contabilidad, Tesorería y demás
departamentos aplicables a cada propiedad.

La plataforma es **independiente** y no sustituye los sistemas operativos existentes: consumirá su
información mediante archivos, interfaces, APIs u otros mecanismos que se validen después.

El modelo de información debe permitir relacionar datos operativos y financieros por **propiedad,
departamento, centro de costo, cuenta, periodo** y otras dimensiones pertinentes.

## Reglas que se derivan para el producto

1. **No inventar** datos, integraciones ni capacidades que todavía no existan.
2. **La navegación no presenta módulos futuros como si estuvieran implementados.** Hoy solo hay
   entradas para lo que existe (Variance, Budget, Cargas, Catálogo, Saldos, Auditoría, Usuarios).
   Cuando exista un módulo nuevo se agrega una entrada en `frontend/src/ruta/navegacion.ts`; nada más.
3. La estructura de navegación (grupos, contexto de propiedad, rutas por pantalla) debe poder crecer
   sin rehacerse.
4. Lo que no esté confirmado se marca `[POR VALIDAR]`.

## Alcance del rediseño de interfaz (octubre 2026)

Solo la interfaz y las funcionalidades de las fases ya desarrolladas (Fases 1 a 5, incluidas las
pantallas de comentarios, cierre, usuarios e historial). No se agregan módulos departamentales,
integraciones ni funciones nuevas como parte del rediseño visual.
