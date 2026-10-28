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
  /** Estado real del ciclo (borrador, enviado…) y su cobertura de captura, si hay ciclo. */
  estadoCiclo?: string | null
  cobertura?: { capturadas: number; total: number } | null
}

const ETIQUETA_ESTADO: Record<string, string> = {
  borrador: 'Borrador',
  enviado: 'Enviado',
  revision: 'Revisión',
  aprobado: 'Aprobado',
  bloqueado: 'Bloqueado',
}

/** «2026/27» -> «Jul 2026 – Jun 2027» (el ejercicio fiscal va de julio a junio). */
function rangoLargo(anoFiscal: string): string {
  const partes = anoFiscal.split('/')
  if (partes.length === 2 && partes[0].length === 4) {
    const fin = partes[1].length === 2 ? `20${partes[1]}` : partes[1]
    return `Jul ${partes[0]} – Jun ${fin}`
  }
  return anoFiscal
}

/**
 * Cabecera de Captura según la referencia (oct-2026): título grande, insignias de estado y
 * cobertura, subtítulo con el ejercicio y, a la derecha, la versión oficial vigente.
 */
export function BudgetHeader({
  anoFiscal,
  version,
  puedeAdministrarCiclo,
  cicloAbierto,
  abriendoCiclo,
  errorCiclo,
  onAbrirCiclo,
  estadoCiclo,
  cobertura,
}: Props) {
  return (
    <header className="captura-cabecera" aria-labelledby="titulo-budget">
      <div className="captura-cabecera-izq">
        <div className="captura-cabecera-titulo">
          <h1 id="titulo-budget">Captura presupuestaria</h1>
          {estadoCiclo && (
            <span className="insignia-pill" title="Estado del ciclo de presupuesto">
              <Icono nombre="presupuesto" tamano={14} />
              {ETIQUETA_ESTADO[estadoCiclo] ?? estadoCiclo}
            </span>
          )}
          {cobertura && (
            <span className="insignia-pill" title="Líneas con propuesta capturada">
              <span className="punto-verde" aria-hidden="true" />
              <strong>{cobertura.capturadas}</strong> / {cobertura.total} líneas
            </span>
          )}
        </div>
        <p className="captura-cabecera-sub">
          Ejercicio fiscal {anoFiscal} <span aria-hidden="true">·</span> {rangoLargo(anoFiscal)}
        </p>
      </div>

      <div className="captura-cabecera-der">
        {version ? (
          <span className="version-oficial" title={`Archivo de origen: ${version.nombre_archivo}`}>
            <Icono nombre="objetivo" tamano={16} />
            Versión oficial <strong>v{version.numero}</strong>
            <Icono nombre="check" tamano={14} />
          </span>
        ) : (
          <Insignia tono="aviso">Sin versión oficial</Insignia>
        )}
        {!cicloAbierto && puedeAdministrarCiclo && (
          <button type="button" className="boton boton-abrir-ciclo" disabled={abriendoCiclo} onClick={onAbrirCiclo}>
            <Icono nombre="objetivo" tamano={16} />
            <span>{abriendoCiclo ? 'Abriendo…' : 'Abrir ciclo de presupuesto'}</span>
          </button>
        )}
      </div>
      {errorCiclo && <MensajeError texto={errorCiclo} />}
    </header>
  )
}
