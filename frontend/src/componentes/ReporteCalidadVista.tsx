import type { ReporteCalidad, Severidad } from '../api/tipos'
import { Insignia, type Tono } from './Insignia'

const TONO: Record<Severidad, Tono> = { ok: 'ok', aviso: 'aviso', error: 'error' }
const ETIQUETA: Record<Severidad, string> = { ok: 'OK', aviso: 'Aviso', error: 'Error' }

/** Controles de calidad de una carga: primero los errores, luego avisos y por último los OK. */
export function ReporteCalidadVista({ reporte }: { reporte: ReporteCalidad }) {
  const orden: Record<Severidad, number> = { error: 0, aviso: 1, ok: 2 }
  const controles = [...reporte.controles].sort((a, b) => orden[a.severidad] - orden[b.severidad])
  return (
    <div className="reporte-calidad">
      <p className="calidad-cabecera">
        <strong>Calidad de datos:</strong>{' '}
        <Insignia tono={reporte.aprobado ? 'ok' : 'error'}>
          {reporte.aprobado ? 'Aprobado' : 'Rechazado'}
        </Insignia>
      </p>
      <ul className="controles">
        {controles.map((c) => (
          <li key={c.codigo}>
            <Insignia tono={TONO[c.severidad]}>{ETIQUETA[c.severidad]}</Insignia> {c.resumen}
            {c.ejemplos.length > 0 && (
              <ul className="ejemplos">
                {c.ejemplos.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
