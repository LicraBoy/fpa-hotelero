interface Dato {
  etiqueta: string
  valor: string
}

/** Franja de «dónde estoy» del drill-down: reporte, periodo, nivel y objeto que se está mirando. */
export function ContextoDrilldown({ datos }: { datos: Dato[] }) {
  return (
    <ul className="contexto-drill" aria-label="Contexto de la consulta">
      {datos.map((d) => (
        <li key={`${d.etiqueta}-${d.valor}`} className="chip-dato">
          <span>{d.etiqueta}</span>
          <strong>{d.valor}</strong>
        </li>
      ))}
    </ul>
  )
}
