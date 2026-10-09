interface Tramo {
  etiqueta: string
  cantidad: number
  tono: 'favorable' | 'desfavorable' | 'neutro'
}

/** Barra horizontal apilada de conteos (no de dinero), con su leyenda. SVG con atributos: sin `style=`. */
export function BarraApilada({ tramos }: { tramos: Tramo[] }) {
  const total = tramos.reduce((n, t) => n + t.cantidad, 0)
  if (total === 0) return null
  // Posición de cada tramo = suma de los anteriores (sin reasignar variables durante el render)
  const posiciones = tramos.map((_, i) => tramos.slice(0, i).reduce((n, t) => n + t.cantidad, 0))
  return (
    <div className="barra-apilada">
      <svg viewBox="0 0 100 6" preserveAspectRatio="none" role="img" aria-label={tramos.map((t) => `${t.cantidad} ${t.etiqueta}`).join(', ')}>
        {tramos.map((t, i) =>
          t.cantidad > 0 ? (
            <rect
              key={t.etiqueta}
              className={`tramo-${t.tono}`}
              x={(posiciones[i] * 100) / total}
              y="0"
              width={(t.cantidad * 100) / total}
              height="6"
            />
          ) : null,
        )}
      </svg>
      <ul className="barra-leyenda">
        {tramos.map((t) => (
          <li key={t.etiqueta}>
            <span className={`punto punto-${t.tono}`} aria-hidden="true" /> {t.cantidad} {t.etiqueta}
          </li>
        ))}
      </ul>
    </div>
  )
}
