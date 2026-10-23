import type { components } from '../../../api/schema'
import type { LineaEdicionBudget } from '../../../api/tipos'
import {
  aMicros,
  claveActual,
  claveCelda,
  diferenciaVsObjetivo,
  formatoMicros,
  sumarMicros,
  textoDeMicros,
} from '../calculo'
import { ObjetivoCelda } from '../PanelBudget'
import { SelectorPerfilDistribucion } from './SelectorPerfilDistribucion'

type LineaCaptura = components['schemas']['LineaCapturaSalida']
type Perfil = components['schemas']['PerfilSalida']
type LineaMensual = components['schemas']['LineaMensualSalida']

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
const etiquetaMes = (periodo: string) => `${MESES[Number(periodo.slice(5, 7)) - 1]} ${periodo.slice(2, 4)}`

const ESTADO_ETIQUETA: Record<string, string> = { pendiente: 'Pendiente', capturada: 'Capturada' }

interface Props {
  linea: LineaEdicionBudget
  periodos: string[]
  ediciones: ReadonlyMap<string, string>
  budget: ReadonlyMap<string, bigint | null>
  alEditar: (linea: number, periodo: string, valor: string) => void
  alEditarActual: (linea: number, periodo: string, valor: string) => void
  puedeEditarBudget: boolean
  puedeEditarActual: boolean
  captura: LineaCaptura | undefined
  puedeObjetivo: boolean
  hotelId: number
  cicloId: number | null
  perfiles: Perfil[]
  puedeRellenarConPerfil: boolean
  alRellenarMeses: (linea: number, valores: LineaMensual[]) => void
  alCambiarCiclo: () => void
}

/**
 * Detalle de una línea (spec §5.1/§5.2): objetivo, propuesta anual, diferencia, estado, nota y los
 * 12 meses en una cuadrícula compacta julio-junio. Reutiliza exactamente los mismos manejadores
 * (`alEditar`/`alEditarActual`) que la tabla: es otra presentación del mismo estado, no una captura
 * paralela — guardar/descartar siguen siendo los de la barra de acciones de siempre.
 */
export function DetalleCapturaLinea({
  linea,
  periodos,
  ediciones,
  budget,
  alEditar,
  alEditarActual,
  puedeEditarBudget,
  puedeEditarActual,
  captura,
  puedeObjetivo,
  hotelId,
  cicloId,
  perfiles,
  puedeRellenarConPerfil,
  alRellenarMeses,
  alCambiarCiclo,
}: Props) {
  const calculados = periodos.map((per) => budget.get(claveCelda(linea.linea_id, per)) ?? null)
  const anual = sumarMicros(calculados)
  const diferencia = captura?.objetivo != null && anual !== null ? diferenciaVsObjetivo(captura.objetivo, textoDeMicros(anual)) : null
  const puedeRellenar = puedeRellenarConPerfil && linea.tipo === 'detalle' && cicloId !== null && perfiles.length > 0 && anual !== null

  return (
    <section className="detalle-captura-linea tarjeta" aria-label={`Detalle de ${linea.descripcion}`}>
      <header>
        <h3>{linea.descripcion}</h3>
        {linea.codigo_corporativo && <p className="suave">{linea.codigo_corporativo}</p>}
      </header>

      <dl className="detalle-captura-resumen">
        <div>
          <dt>Objetivo</dt>
          <dd>
            {cicloId !== null && captura ? (
              <ObjetivoCelda
                hotelId={hotelId}
                cicloId={cicloId}
                linea={linea.linea_id}
                descripcion={linea.descripcion}
                objetivoInicial={captura.objetivo}
                puedeEditar={puedeObjetivo}
                alGuardar={alCambiarCiclo}
              />
            ) : (
              '—'
            )}
          </dd>
        </div>
        <div>
          <dt>Propuesta anual</dt>
          <dd>{linea.tipo === 'informativa' ? '—' : formatoMicros(anual)}</dd>
        </div>
        <div>
          <dt>Diferencia vs. objetivo</dt>
          <dd>
            {diferencia?.diferenciaMicros != null
              ? `${formatoMicros(diferencia.diferenciaMicros)} (${
                  diferencia.estado === 'sobre' ? 'sobre' : diferencia.estado === 'bajo' ? 'bajo' : 'dentro del'
                } objetivo)`
              : '—'}
          </dd>
        </div>
        {captura && (
          <div>
            <dt>Estado de captura</dt>
            <dd>{ESTADO_ETIQUETA[captura.estado] ?? captura.estado}</dd>
          </div>
        )}
        {captura?.nota && (
          <div>
            <dt>Nota</dt>
            <dd>{captura.nota}</dd>
          </div>
        )}
      </dl>

      {puedeRellenar && cicloId !== null && anual !== null && (
        <SelectorPerfilDistribucion
          hotelId={hotelId}
          cicloId={cicloId}
          linea={linea.linea_id}
          anual={textoDeMicros(anual)}
          perfiles={perfiles}
          periodos={periodos}
          alAplicar={(valores) => alRellenarMeses(linea.linea_id, valores)}
        />
      )}

      <div className="cuadricula-meses">
        {linea.meses.map((c, i) => {
          const clave = claveCelda(linea.linea_id, c.periodo)
          const editado = ediciones.get(clave)
          const invalido = editado !== undefined && editado.trim() !== '' && aMicros(editado) === null
          const claveA = claveActual(linea.linea_id, c.periodo)
          const editadoA = ediciones.get(claveA)
          const actualMicros = c.actual === null ? null : aMicros(c.actual)
          return (
            <div key={c.periodo} className="mes-captura">
              <span className="mes-captura-etiqueta">{etiquetaMes(c.periodo)}</span>
              {puedeEditarBudget ? (
                <input
                  type="text"
                  inputMode="decimal"
                  className={invalido ? 'entrada-budget entrada-invalida' : 'entrada-budget'}
                  aria-label={`Budget de ${linea.descripcion}, ${etiquetaMes(c.periodo)}`}
                  aria-invalid={invalido || undefined}
                  placeholder="—"
                  value={editado ?? (calculados[i] === null ? '' : formatoMicros(calculados[i]))}
                  onChange={(e) => alEditar(linea.linea_id, c.periodo, e.target.value)}
                />
              ) : (
                <span className="num">{formatoMicros(calculados[i])}</span>
              )}
              {puedeEditarActual ? (
                <input
                  type="text"
                  inputMode="decimal"
                  aria-label={`Actual de ${linea.descripcion}, ${etiquetaMes(c.periodo)}`}
                  className="entrada-budget"
                  placeholder="—"
                  value={editadoA ?? (actualMicros === null ? '' : formatoMicros(actualMicros))}
                  onChange={(e) => alEditarActual(linea.linea_id, c.periodo, e.target.value)}
                />
              ) : (
                <span className="num suave">{formatoMicros(actualMicros)}</span>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
