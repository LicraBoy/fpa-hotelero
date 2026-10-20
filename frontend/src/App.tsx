import { useState } from 'react'
import type { UsuarioSesion } from './api/auth'
import { fijarUsuarioDev, obtenerTipado } from './api/cliente'
import { useDatos } from './api/useDatos'
import { BarraSuperior } from './componentes/BarraSuperior'
import { Icono, Logo, type NombreIcono } from './componentes/Iconos'
import { Cargando, MensajeError } from './componentes/Insignia'
import { PanelAuditoria } from './componentes/PanelAuditoria'
import { PanelCargas } from './componentes/PanelCargas'
import { PanelCatalogo } from './componentes/PanelCatalogo'
import { PanelSaldos } from './componentes/PanelSaldos'
import { PanelCuenta } from './pantallas/cuenta/PanelCuenta'
import { PanelBudget } from './pantallas/budget/PanelBudget'
import { PanelVariance } from './pantallas/variance/PanelVariance'
import { RutaProtegida } from './ruta/RutaProtegida'
import { permisoDeRuta } from './ruta/ruta'
import { useRuta } from './ruta/useRuta'
import { NOMBRE_ROL, USUARIOS_DESARROLLO, puede } from './permisos'
import { guardarLateralPlegado, guardarUsuarioDev, leerLateralPlegado, leerUsuarioDev } from './util/preferencias'

type Pestana = 'cargas' | 'catalogo' | 'saldos' | 'variance' | 'budget' | 'auditoria' | 'cuenta'

/** Sesión real (inicio de sesión con contraseña); sin ella se usa el selector de desarrollo. */
export interface SesionApp {
  usuario: UsuarioSesion
  recargar: () => void
  cerrar: () => void
}

function usuarioInicial(): string {
  const guardado = leerUsuarioDev()
  if (guardado && USUARIOS_DESARROLLO.some((u) => u.email === guardado)) return guardado
  return USUARIOS_DESARROLLO[0].email
}

export default function App({
  sesion,
  alProbarLogin,
}: {
  sesion?: SesionApp
  alProbarLogin?: () => void
}) {
  const [usuarioDev, setUsuario] = useState(() => {
    const inicial = usuarioInicial()
    fijarUsuarioDev(sesion ? null : inicial)
    return inicial
  })
  // Quién está activo: la persona con sesión o el usuario de prueba elegido a mano
  const usuario = sesion ? `sesion-${sesion.usuario.usuario_id}` : usuarioDev
  const [hotelId, setHotelId] = useState<number | null>(null)
  const [pestana, setPestana] = useState<Pestana>('cargas')
  const [version, setVersion] = useState(0)
  // Barra lateral plegada (solo iconos): deja todo el ancho a las tablas anchas
  const [lateralPlegado, setLateralPlegado] = useState(leerLateralPlegado)

  const hoteles = useDatos(() => obtenerTipado('/api/v1/hoteles', {}), [usuario])

  // El hotel activo se deriva: el elegido si sigue disponible, si no el primero del usuario.
  // Mientras se recarga (cambio de usuario) no hay hotel ni rol: los datos que quedan en memoria son
  // del usuario anterior y no deben decidir qué pantallas se montan ni qué consultas se hacen.
  const hotel = hoteles.cargando
    ? undefined
    : (hoteles.datos?.find((h) => h.id === hotelId) ?? hoteles.datos?.[0])
  const rol = hotel?.rol

  // La barra lateral agrupa las secciones; el orden de los grupos y de sus ítems es el de lectura.
  const grupos: { titulo: string; items: { id: Pestana; nombre: string; icono: NombreIcono; visible: boolean }[] }[] = [
    {
      titulo: 'Reportes',
      items: [
        { id: 'variance', nombre: 'Variance', icono: 'informe', visible: puede(rol, 'variance:leer') },
        { id: 'budget', nombre: 'Budget', icono: 'presupuesto', visible: puede(rol, 'budget:importar') },
      ],
    },
    {
      titulo: 'Datos',
      items: [
        { id: 'cargas', nombre: 'Cargas', icono: 'subir', visible: puede(rol, 'carga:leer') || puede(rol, 'carga:crear') },
        { id: 'catalogo', nombre: 'Catálogo', icono: 'catalogo', visible: puede(rol, 'catalogo:leer') },
        { id: 'saldos', nombre: 'Saldos', icono: 'saldos', visible: puede(rol, 'saldos:leer') },
      ],
    },
    {
      titulo: 'Control',
      items: [
        { id: 'auditoria', nombre: 'Auditoría', icono: 'auditoria', visible: puede(rol, 'auditoria:leer') },
        { id: 'cuenta', nombre: 'Mi cuenta', icono: 'usuario', visible: sesion !== undefined },
      ],
    },
  ]
  const visibles = grupos.flatMap((g) => g.items).filter((p) => p.visible)
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

  const nombreActiva = visibles.find((p) => p.id === activa)?.nombre
  const grupoActivo = grupos.find((g) => g.items.some((p) => p.id === activa))?.titulo
  const detalle: Record<string, string> = { desglose: 'Desglose', cuenta: 'Movimientos', asiento: 'Asiento' }
  const ubicacion = [
    ...(grupoActivo ? [grupoActivo] : []),
    ...(nombreActiva ? [nombreActiva] : []),
    ...(activa === 'variance' && detalle[ruta.tipo] ? [detalle[ruta.tipo]] : []),
  ]
  const nombreUsuario = sesion
    ? sesion.usuario.nombre
    : (USUARIOS_DESARROLLO.find((u) => u.email === usuarioDev)?.nombre ?? usuarioDev)

  return (
    <div className={lateralPlegado ? 'app app-plegado' : 'app'}>
      <aside className="lateral">
        <div className="marca">
          <Logo />
          <div>
            <h1>Plataforma FP&amp;A Hotelera</h1>
            <p className="suave">{hotel?.nombre ?? 'Torres Mazatlán'}</p>
          </div>
        </div>

        {hotel && activa && (
          <nav className="navegacion" aria-label="Secciones">
            {grupos.map((g) => {
              const items = g.items.filter((p) => p.visible)
              if (items.length === 0) return null
              return (
                <div key={g.titulo} className="nav-grupo" role="group" aria-label={g.titulo}>
                  <p className="nav-titulo" aria-hidden="true">
                    {g.titulo}
                  </p>
                  {items.map((p) => (
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
                      <Icono nombre={p.icono} />
                      <span>{p.nombre}</span>
                    </button>
                  ))}
                </div>
              )
            })}
          </nav>
        )}

        {sesion ? (
          <div className="lateral-pie">
            <p className="lateral-usuario">
              {sesion.usuario.nombre}
              <span className="suave">{sesion.usuario.email}</span>
            </p>
            <button type="button" className="boton boton-secundario" onClick={sesion.cerrar}>
              Cerrar sesión
            </button>
          </div>
        ) : (
          <div className="lateral-pie">
            <label>
              Usuario (desarrollo)
              <select value={usuarioDev} onChange={(e) => cambiarUsuario(e.target.value)}>
                {USUARIOS_DESARROLLO.map((u) => (
                  <option key={u.email} value={u.email}>
                    {u.nombre}
                  </option>
                ))}
              </select>
            </label>
            <p className="aviso-desarrollo" role="note">
              Modo desarrollo: el usuario se elige a mano. En producción se entra con usuario y
              contraseña.
            </p>
            {alProbarLogin && (
              <button type="button" className="boton boton-secundario" onClick={alProbarLogin}>
                Probar inicio de sesión real
              </button>
            )}
          </div>
        )}
      </aside>

      <div className="principal">
        <BarraSuperior
          lateralPlegado={lateralPlegado}
          alAlternarLateral={() => {
            guardarLateralPlegado(!lateralPlegado)
            setLateralPlegado(!lateralPlegado)
          }}
          ubicacion={ubicacion.length > 0 ? ubicacion : ['Inicio']}
          nombreUsuario={nombreUsuario}
          rol={rol ? (NOMBRE_ROL[rol] ?? rol) : undefined}
          hotel={
            hoteles.datos && hoteles.datos.length > 0 ? (
              <label className="selector-hotel">
                <Icono nombre="hotel" />
                <span className="solo-lectores">Hotel</span>
                <select value={hotel?.id ?? ''} onChange={(e) => setHotelId(Number(e.target.value))}>
                  {hoteles.datos.map((h) => (
                    <option key={h.id} value={h.id}>
                      {h.nombre}
                    </option>
                  ))}
                </select>
              </label>
            ) : undefined
          }
        />
        <main className={activa === 'variance' ? 'contenido' : 'contenido contenido-estrecho'}>
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
              {activa === 'cuenta' && sesion && (
                <PanelCuenta usuario={sesion.usuario} alCambiar={sesion.recargar} />
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
