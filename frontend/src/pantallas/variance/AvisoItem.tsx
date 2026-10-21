import { useState } from 'react'
import { Icono } from '../../componentes/Iconos'

const LIMITE = 170

/** Un aviso del reporte: si es muy largo se recorta a dos líneas y se puede abrir completo. */
export function AvisoItem({ texto }: { texto: string }) {
  const [abierto, setAbierto] = useState(false)
  const largo = texto.length > LIMITE
  return (
    <>
      <span className="aviso-icono" aria-hidden="true">
        <Icono nombre="alerta" tamano={14} />
      </span>
      <span className={largo && !abierto ? 'aviso-texto aviso-recortado' : 'aviso-texto'}>{texto}</span>
      {largo && (
        <button
          type="button"
          className="enlace aviso-mas"
          aria-expanded={abierto}
          onClick={() => setAbierto((v) => !v)}
        >
          {abierto ? 'Ver menos' : 'Ver todo'}
        </button>
      )}
    </>
  )
}
