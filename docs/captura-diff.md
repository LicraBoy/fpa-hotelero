# Captura presupuestaria: diferencias contra la referencia (1536 × 1024)

Referencia: `docs/imagenes/rediseno/diseño para la captura del presupusto.png`.
Capturas: `docs/imagenes/rediseno/r3-final.png` (app real), `comparacion-lado-a-lado.png`,
`comparacion-overlay-50.png`.

## Colores muestreados de la referencia (píxeles reales)

| Elemento | Referencia | Usado |
|---|---|---|
| Sidebar | `#0f284a` → `#12294f` | degradado `#0f284a → #12294f → #0e2547` |
| Grupo activo / subitem activo | `#1e54af` / `#1b51ad` | `#1e54af` / `#1b51ad` |
| Botones primarios | `#165ef1`–`#1a63f1` | `#1a63f1` |
| Check completado | `#04987b` | `#04987b` |
| Fondo principal | `#f2f8fc` | `--fondo` del proyecto (`#f3f6fa`) |

## Diferencias que había y se corrigieron

- Sidebar 236 px sin marca/usuario/hotel → 198 px, "FPA Hotelero / Planificación Financiera
  Avanzada", Budget Studio expandido con Resumen/Captura/Versiones, usuario y hotel al pie.
- Barra superior con selector de hotel y usuario → migaja + punto de API + ayuda + tema.
- Cabecera en tarjeta con "BUDGET STUDIO" y "Ver versiones" → título 34 px, insignias de estado y
  cobertura reales, ejercicio fiscal, "Versión oficial vN".
- Ciclo con scroll y anillo "Cobertura" → una fila de ≈84 px con chip "Budget vN", acción de
  transición real, "Actividad del ciclo" y menú ⋮ para transiciones secundarias.
- Filtros en bloques → una fila; segunda barra con Tabla/Árbol, ajuste % y "Solo meses sin Budget";
  botón "Copiar el Actual a las líneas que se ven" en su propia fila.
- Dos inputs por mes → una cifra por celda; solo la celda activa es input; Actual en tooltip y en
  la gráfica del panel.
- Total de sección que sumaba subtotales (riesgo de duplicar) → se suma solo `detalle`.
- Página con scroll vertical → a 1536×1024 `scrollHeight == innerHeight`; scroll solo en la
  cuadrícula y el panel.
- Panel que aparecía al hacer clic → siempre visible (276 px) con "Detalle de línea".

## Desviaciones que quedan (con motivo)

- **"Inicio", "Hoteles", "Reportes", "Configuración" y "Actividad del ciclo" no están en el
  menú**: no tienen destino real. Cargas, Catálogo, Auditoría y Usuarios van en el grupo
  "Administración"; Saldos pasó a Financiero.
- **Sin campana de notificaciones**: no hay notificaciones reales.
- **Pestaña Historial y acciones "Copiar línea" / "Historial de la línea" omitidas**: el backend
  no audita por línea ni ofrece copiar a otra línea.
- **Importes de meses a 10.5 px** (no 11) para que quepan 12 meses en ≈62 px por columna sin
  recortar cifras de 6 dígitos.
- **Iconos de línea todos en el mismo color**: los datos no distinguen ingresos de gastos.
- **Diferencia en verde**: se muestra sin color semántico (no hay regla favorable/desfavorable para
  Budget); solo el chip del porcentaje va en verde como en la referencia.
- **Menú lateral en pantallas <1024 px**: arranca contraído y se abre como bloque superior con el
  botón de menú (no es un cajón lateral).
- **El Actual capturable a mano** (líneas sin cuentas, p. ej. Exchange Rate) se escribe en el panel,
  en "Actual por mes".
- Pegado desde Excel en la cuadrícula: no existía antes y no se agregó.
- Posiciones verticales ≈ 3–6 px por encima de la referencia (migaja, título) por el alto de la
  barra superior.
