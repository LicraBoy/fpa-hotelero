import { EncabezadoPagina } from '../../../componentes/EncabezadoPagina'
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
}

/** Encabezado persistente de Budget: año fiscal, versión vigente y "Abrir ciclo" (spec §3). */
export function BudgetHeader({
  anoFiscal,
  version,
  puedeAdministrarCiclo,
  cicloAbierto,
  abriendoCiclo,
  errorCiclo,
  onAbrirCiclo,
}: Props) {
  return (
    <EncabezadoPagina
      id="titulo-budget"
      titulo={`Budget ${anoFiscal}`}
      subtitulo={
        version ? (
          <span className="meta-version">
            Versión {version.numero} · {version.nombre_archivo}
          </span>
        ) : (
          <Insignia tono="aviso">Todavía no hay Budget para este año</Insignia>
        )
      }
      acciones={
        !cicloAbierto &&
        puedeAdministrarCiclo && (
          <>
            <button type="button" className="boton boton-secundario" disabled={abriendoCiclo} onClick={onAbrirCiclo}>
              {abriendoCiclo ? 'Abriendo…' : 'Abrir ciclo de presupuesto'}
            </button>
            {errorCiclo && <MensajeError texto={errorCiclo} />}
          </>
        )
      }
    />
  )
}
