import { useCallback, useEffect, useState } from 'react'
import App from './App'
import { cerrarSesion, estadoAuth, type EstadoAuth, type UsuarioSesion } from './api/auth'
import { usarSesionReal } from './api/sesion'
import { Cargando, MensajeError } from './componentes/Insignia'
import { PantallaEntrada } from './pantallas/cuenta/PantallaEntrada'

/**
 * Decide cómo entra el usuario: con inicio de sesión (producción) o, en desarrollo, con el selector
 * de usuarios de prueba (que además permite probar el inicio de sesión real).
 */
export default function Raiz() {
  const [estado, setEstado] = useState<EstadoAuth | null>(null)
  const [usuario, setUsuario] = useState<UsuarioSesion | null>(null)
  const [probarLogin, setProbarLogin] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const consultar = useCallback(
    () =>
      estadoAuth()
        .then((e) => {
          setEstado(e)
          setUsuario(e.usuario ?? null)
        })
        .catch(() => setError('No se pudo contactar a la API')),
    [],
  )

  useEffect(() => {
    void consultar()
  }, [consultar])

  const sesionReal = estado !== null && (estado.entorno !== 'desarrollo' || probarLogin)

  useEffect(() => {
    usarSesionReal(sesionReal, () => setUsuario(null))
    return () => usarSesionReal(false)
  }, [sesionReal])

  if (error) return <MensajeError texto={error} />
  if (!estado) return <Cargando />

  if (!sesionReal) {
    return <App key="dev" alProbarLogin={() => setProbarLogin(true)} />
  }
  if (!usuario) {
    return (
      <PantallaEntrada
        alEntrar={setUsuario}
        alVolver={estado.entorno === 'desarrollo' ? () => setProbarLogin(false) : undefined}
      />
    )
  }
  return (
    <App
      key="sesion"
      sesion={{
        usuario,
        recargar: () => void consultar(),
        cerrar: async () => {
          try {
            await cerrarSesion()
          } finally {
            setUsuario(null)
          }
        },
      }}
    />
  )
}
