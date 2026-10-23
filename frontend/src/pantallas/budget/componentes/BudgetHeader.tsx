import { Icono } from '../../../componentes/Iconos'
import { Insignia, MensajeError } from '../../../componentes/Insignia'

interface VersionVigente {
  numero: number
  nombre_archivo: string
}

interface Props {
  anoFiscal: string
  version: VersionVigente | null
  puedeAdministrarCiclo: boolean
  cicloAbierto: boolean
  abriendoCiclo: boolean
  errorCiclo: string | null
  onAbrirCiclo: () => void
  rangoFiscal?: string
  onVerVersiones?: () => void
}

function calcularRangoPorDefecto(anoFiscal: string): string {
  const partes = anoFiscal.split('/')
  if (partes.length === 2 && partes[0].length === 4) {
    const inicio = partes[0]
    const fin = partes[1].length === 2 ? `20${partes[1]}` : partes[1]
    return `Jul ${inicio} – Jun ${fin}`
  }
  return anoFiscal
}

/**
 * Encabezado profesional de Budget Studio (spec §3 y referencia visual):
 * Título de ejercicio fiscal, badge de fechas, versión oficial vigente, acceso a versiones y acción del ciclo.
 */
export function BudgetHeader({
  anoFiscal,
  version,
  puedeAdministrarCiclo,
  cicloAbierto,
  abriendoCiclo,
  errorCiclo,
  onAbrirCiclo,
  rangoFiscal,
  onVerVersiones,
}: Props) {
  const fechas = rangoFiscal || calcularRangoPorDefecto(anoFiscal)

  return (
    <header className="budget-header" aria-labelledby="titulo-budget">
      <div className="budget-header-principal">
        <div className="budget-header-izq">
          <div className="budget-header-identificador">
            <Icono nombre="presupuesto" tamano={15} />
            <span>Budget Studio</span>
          </div>
          <div className="budget-header-titulo-fila">
            <h1 id="titulo-budget">Presupuesto {anoFiscal}</h1>
            <span className="budget-rango-badge" title="Rango del ejercicio fiscal">
              <Icono nombre="calendario" tamano={14} />
              <span>{fechas}</span>
            </span>
          </div>
          <p className="budget-header-subtitulo">
            Planifica, analiza y controla el desempeño financiero de tu hotel en un solo lugar.
          </p>
        </div>

        <div className="budget-header-der">
          {version ? (
            <div className="budget-version-pill" title={`Archivo de origen: ${version.nombre_archivo}`}>
              <span className="budget-version-pill-punto" aria-hidden="true" />
              <span className="budget-version-pill-texto">
                Versión oficial <strong>v{version.numero}</strong>
              </span>
            </div>
          ) : (
            <Insignia tono="aviso">Sin versión oficial</Insignia>
          )}

          <div className="budget-header-acciones">
            {onVerVersiones && (
              <button
                type="button"
                className="boton boton-secundario budget-btn-historial"
                onClick={onVerVersiones}
                title="Consultar historial de versiones del plan"
              >
                <Icono nombre="auditoria" tamano={15} />
                <span>Historial</span>
              </button>
            )}

            {!cicloAbierto && puedeAdministrarCiclo && (
              <button
                type="button"
                className="boton boton-abrir-ciclo"
                disabled={abriendoCiclo}
                onClick={onAbrirCiclo}
              >
                <Icono nombre="objetivo" tamano={16} />
                <span>{abriendoCiclo ? 'Abriendo…' : 'Abrir ciclo de presupuesto'}</span>
              </button>
            )}
          </div>
        </div>
      </div>
      {errorCiclo && <MensajeError texto={errorCiclo} />}
    </header>
  )
}
