import { useEffect, useRef, useState } from 'react'
import { Icono } from './Iconos'

interface Props {
  nombre: string
  correo: string
  alAbrirCuenta: () => void
  alCerrarSesion: () => void
}

function iniciales(nombre: string): string {
  const letras = nombre
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p.replace(/[^\p{L}\p{N}]/gu, '')[0]?.toUpperCase() ?? '')
  return letras.join('') || '?'
}

/** Menú de la persona con sesión: su cuenta y cerrar sesión (no son destinos de administración). */
export function MenuUsuario({ nombre, correo, alAbrirCuenta, alCerrarSesion }: Props) {
  const [abierto, setAbierto] = useState(false)
  const raiz = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!abierto) return
    const fuera = (e: MouseEvent) => {
      if (raiz.current && !raiz.current.contains(e.target as Node)) setAbierto(false)
    }
    const tecla = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAbierto(false)
    }
    document.addEventListener('mousedown', fuera)
    document.addEventListener('keydown', tecla)
    return () => {
      document.removeEventListener('mousedown', fuera)
      document.removeEventListener('keydown', tecla)
    }
  }, [abierto])

  return (
    <div className="menu-usuario" ref={raiz}>
      {abierto && (
        <div className="menu-usuario-lista" role="group" aria-label="Opciones de la cuenta">
          <button
            type="button"
            className="menu-usuario-opcion"
            onClick={() => {
              setAbierto(false)
              alAbrirCuenta()
            }}
          >
            <Icono nombre="usuario" tamano={16} />
            Mi cuenta
          </button>
          <button
            type="button"
            className="menu-usuario-opcion"
            onClick={() => {
              setAbierto(false)
              alCerrarSesion()
            }}
          >
            <Icono nombre="cerrar" tamano={16} />
            Cerrar sesión
          </button>
        </div>
      )}
      <button
        type="button"
        className="menu-usuario-boton"
        aria-expanded={abierto}
        aria-haspopup="true"
        aria-label="Menú de usuario"
        onClick={() => setAbierto((a) => !a)}
      >
        <span className="avatar" aria-hidden="true">
          {iniciales(nombre)}
        </span>
        <span className="menu-usuario-datos">
          <strong>{nombre}</strong>
          <span className="suave">{correo}</span>
        </span>
        <Icono nombre="expandir" tamano={14} />
      </button>
    </div>
  )
}
