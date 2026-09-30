import { useState } from 'react'
import { fijarUsuarioDev, obtener } from './api/cliente'
import type { Hotel } from './api/tipos'
import { useDatos } from './api/useDatos'
import { EstadoApi } from './componentes/EstadoApi'
import { Cargando, Insignia, MensajeError } from './componentes/Insignia'
import { PanelAuditoria } from './componentes/PanelAuditoria'
import { PanelCargas } from './componentes/PanelCargas'
import { PanelCatalogo } from './componentes/PanelCatalogo'
import { PanelSaldos } from './componentes/PanelSaldos'
import { NOMBRE_ROL, USUARIOS_DESARROLLO, puede } from './permisos'

type Pestana = 'cargas' | 'catalogo' | 'saldos' | 'auditoria'

const CLAVE_USUARIO = 'fpa_usuario_dev'

function usuarioInicial(): string {
  try {
    const guardado = localStorage.getItem(CLAVE_USUARIO)
    if (guardado && USUARIOS_DESARROLLO.some((u) => u.email === guardado)) return guardado
  } catch {
    // sin almacenamiento local (modo privado): se usa el predeterminado
  }
  return USUARIOS_DESARROLLO[0].email
}

export default function App() {
  const [usuario, setUsuario] = useState(() => {
    const inicial = usuarioInicial()
    fijarUsuarioDev(inicial)
    return inicial
  })
  const [hotelId, setHotelId] = useState<number | null>(null)
  const [pestana, setPestana] = useState<Pestana>('cargas')
  const [version, setVersion] = useState(0)

  const hoteles = useDatos(() => obtener<Hotel[]>('/hoteles'), [usuario])

  // El hotel activo se deriva: el elegido si sigue disponible, si no el primero del usuario.
  const hotel = hoteles.datos?.find((h) => h.id === hotelId) ?? hoteles.datos?.[0]
  const rol = hotel?.rol

  const pestanas: { id: Pestana; nombre: string; visible: boolean }[] = [
    { id: 'cargas', nombre: 'Cargas', visible: puede(rol, 'carga:leer') || puede(rol, 'carga:crear') },
    { id: 'catalogo', nombre: 'Catálogo', visible: puede(rol, 'catalogo:leer') },
    { id: 'saldos', nombre: 'Saldos', visible: puede(rol, 'saldos:leer') },
    { id: 'auditoria', nombre: 'Auditoría', visible: puede(rol, 'auditoria:leer') },
  ]
  const visibles = pestanas.filter((p) => p.visible)
  const activa = visibles.some((p) => p.id === pestana) ? pestana : visibles[0]?.id

  function cambiarUsuario(email: string) {
    fijarUsuarioDev(email) // antes de que los paneles vuelvan a consultar
    try {
      localStorage.setItem(CLAVE_USUARIO, email)
    } catch {
      // sin almacenamiento local: solo vale para esta sesión
    }
    setUsuario(email)
    setHotelId(null)
  }

  return (
    <div className="app">
      <header className="barra">
        <div>
          <h1>Plataforma FP&amp;A Hotelera</h1>
          <p className="suave">Torres Mazatlán · Actuals</p>
        </div>
        <div className="barra-controles">
          <EstadoApi />
          <label>
            Usuario (desarrollo)
            <select value={usuario} onChange={(e) => cambiarUsuario(e.target.value)}>
              {USUARIOS_DESARROLLO.map((u) => (
                <option key={u.email} value={u.email}>
                  {u.nombre}
                </option>
              ))}
            </select>
          </label>
          {hoteles.datos && hoteles.datos.length > 0 && (
            <label>
              Hotel
              <select value={hotel?.id ?? ''} onChange={(e) => setHotelId(Number(e.target.value))}>
                {hoteles.datos.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.nombre}
                  </option>
                ))}
              </select>
            </label>
          )}
          {rol && <Insignia tono="info">{NOMBRE_ROL[rol] ?? rol}</Insignia>}
        </div>
      </header>

      <p className="aviso-desarrollo" role="note">
        Modo desarrollo: el usuario se elige a mano. En producción entrará con el inicio de sesión
        corporativo.
      </p>

      <main className="contenido">
        {hoteles.cargando && <Cargando />}
        {hoteles.error && (
          <MensajeError
            texto={`${hoteles.error}. Si la API está encendida, verifica que corra con FPA_ENTORNO=desarrollo.`}
          />
        )}
        {hoteles.datos && hoteles.datos.length === 0 && (
          <p className="mensaje mensaje-aviso">Este usuario no tiene hoteles asignados.</p>
        )}

        {hotel && activa && (
          <>
            <nav className="pestanas" aria-label="Secciones">
              {visibles.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className={p.id === activa ? 'pestana activa' : 'pestana'}
                  aria-current={p.id === activa ? 'page' : undefined}
                  onClick={() => setPestana(p.id)}
                >
                  {p.nombre}
                </button>
              ))}
            </nav>
            <div key={`${usuario}-${hotel.id}`}>
              {activa === 'cargas' && (
                <PanelCargas
                  hotelId={hotel.id}
                  puedeCargar={puede(rol, 'carga:crear')}
                  version={version}
                  alCambiar={() => setVersion((v) => v + 1)}
                />
              )}
              {activa === 'catalogo' && <PanelCatalogo hotelId={hotel.id} version={version} />}
              {activa === 'saldos' && (
                <PanelSaldos
                  hotelId={hotel.id}
                  version={version}
                  puedeVerCargas={puede(rol, 'carga:leer')}
                />
              )}
              {activa === 'auditoria' && <PanelAuditoria hotelId={hotel.id} version={version} />}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
