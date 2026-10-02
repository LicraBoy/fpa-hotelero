import { useState } from 'react'
import { fijarUsuarioDev, obtenerTipado } from './api/cliente'
import { useDatos } from './api/useDatos'
import { EstadoApi } from './componentes/EstadoApi'
import { Cargando, Insignia, MensajeError } from './componentes/Insignia'
import { PanelAuditoria } from './componentes/PanelAuditoria'
import { PanelCargas } from './componentes/PanelCargas'
import { PanelCatalogo } from './componentes/PanelCatalogo'
import { PanelSaldos } from './componentes/PanelSaldos'
import { PanelBudget } from './pantallas/budget/PanelBudget'
import { PanelVariance } from './pantallas/variance/PanelVariance'
import { RutaProtegida } from './ruta/RutaProtegida'
import { permisoDeRuta } from './ruta/ruta'
import { useRuta } from './ruta/useRuta'
import { NOMBRE_ROL, USUARIOS_DESARROLLO, puede } from './permisos'
import { guardarUsuarioDev, leerUsuarioDev } from './util/preferencias'

type Pestana = 'cargas' | 'catalogo' | 'saldos' | 'variance' | 'budget' | 'auditoria'

function usuarioInicial(): string {
  const guardado = leerUsuarioDev()
  if (guardado && USUARIOS_DESARROLLO.some((u) => u.email === guardado)) return guardado
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

  const hoteles = useDatos(() => obtenerTipado('/api/v1/hoteles', {}), [usuario])

  // El hotel activo se deriva: el elegido si sigue disponible, si no el primero del usuario.
  // Mientras se recarga (cambio de usuario) no hay hotel ni rol: los datos que quedan en memoria son
  // del usuario anterior y no deben decidir qué pantallas se montan ni qué consultas se hacen.
  const hotel = hoteles.cargando
    ? undefined
    : (hoteles.datos?.find((h) => h.id === hotelId) ?? hoteles.datos?.[0])
  const rol = hotel?.rol

  const pestanas: { id: Pestana; nombre: string; visible: boolean }[] = [
    { id: 'cargas', nombre: 'Cargas', visible: puede(rol, 'carga:leer') || puede(rol, 'carga:crear') },
    { id: 'catalogo', nombre: 'Catálogo', visible: puede(rol, 'catalogo:leer') },
    { id: 'saldos', nombre: 'Saldos', visible: puede(rol, 'saldos:leer') },
    { id: 'variance', nombre: 'Variance', visible: puede(rol, 'variance:leer') },
    { id: 'budget', nombre: 'Budget', visible: puede(rol, 'budget:importar') },
    { id: 'auditoria', nombre: 'Auditoría', visible: puede(rol, 'auditoria:leer') },
  ]
  const visibles = pestanas.filter((p) => p.visible)
  // Una ruta de Variance (#/variance/...) manda: abre esa pestaña aunque el rol no la tenga
  // visible; `RutaProtegida` decide si se muestra o responde "Sin acceso" (sin consultar nada).
  const { ruta } = useRuta()
  const enRutaVariance = ['variance', 'desglose', 'cuenta', 'asiento'].includes(ruta.tipo)
  const activa = enRutaVariance
    ? 'variance'
    : visibles.some((p) => p.id === pestana)
      ? pestana
      : visibles[0]?.id

  function cambiarUsuario(email: string) {
    fijarUsuarioDev(email) // antes de que los paneles vuelvan a consultar
    guardarUsuarioDev(email)
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
                  onClick={() => {
                    setPestana(p.id)
                    window.location.hash = p.id === 'variance' ? '#/variance' : ''
                  }}
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
              {activa === 'catalogo' && (
                <PanelCatalogo
                  hotelId={hotel.id}
                  version={version}
                  puedeImportar={puede(rol, 'catalogo:importar')}
                  alCambiar={() => setVersion((v) => v + 1)}
                />
              )}
              {activa === 'saldos' && (
                <PanelSaldos
                  hotelId={hotel.id}
                  version={version}
                  puedeVerCargas={puede(rol, 'carga:leer')}
                />
              )}
              {activa === 'variance' && (
                <RutaProtegida rol={rol} permiso={permisoDeRuta(ruta) ?? 'variance:leer'}>
                  <PanelVariance
                    hotelId={hotel.id}
                    rol={rol}
                    alIrABudget={
                      puede(rol, 'budget:importar')
                        ? () => {
                            setPestana('budget')
                            window.location.hash = ''
                          }
                        : undefined
                    }
                  />
                </RutaProtegida>
              )}
              {activa === 'budget' && <PanelBudget hotelId={hotel.id} />}
              {activa === 'auditoria' && <PanelAuditoria hotelId={hotel.id} version={version} />}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
