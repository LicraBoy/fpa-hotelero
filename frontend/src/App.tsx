import { useState } from 'react'
import type { UsuarioSesion } from './api/auth'
import { fijarUsuarioDev, obtenerTipado } from './api/cliente'
import { useDatos } from './api/useDatos'
import { BarraSuperior } from './componentes/BarraSuperior'
import { Icono, Logo } from './componentes/Iconos'
import { Cargando, MensajeError } from './componentes/Insignia'
import { PanelAuditoria } from './componentes/PanelAuditoria'
import { PanelCargas } from './componentes/PanelCargas'
import { PanelCatalogo } from './componentes/PanelCatalogo'
import { PanelSaldos } from './componentes/PanelSaldos'
import { PanelUsuarios } from './pantallas/usuarios/PanelUsuarios'
import { PanelCuenta } from './pantallas/cuenta/PanelCuenta'
import { PanelBudget } from './pantallas/budget/PanelBudget'
import { PanelVariance } from './pantallas/variance/PanelVariance'
import { MenuUsuario } from './componentes/MenuUsuario'
import { GRUPOS, PANTALLAS, pantallaDe, puedeAbrir, rutaDe, type IdPantalla } from './ruta/navegacion'
import { RutaProtegida, SinAcceso } from './ruta/RutaProtegida'
import { permisoDeRuta } from './ruta/ruta'
import { useRuta } from './ruta/useRuta'
import { NOMBRE_ROL, USUARIOS_DESARROLLO, puede } from './permisos'
import { guardarLateralPlegado, guardarUsuarioDev, leerLateralPlegado, leerUsuarioDev } from './util/preferencias'

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

  // Qué pantalla pide la ruta (la barra de direcciones manda: se puede enlazar y sobrevive a recargar).
  // Sin ruta válida se abre la primera a la que el rol tiene acceso.
  const { ruta } = useRuta()
  const conSesion = sesion !== undefined
  const abribles = PANTALLAS.filter((p) => puedeAbrir(p, rol, conSesion))
  const pedida: IdPantalla | null =
    ruta.tipo === 'pantalla'
      ? ruta.id
      : ['variance', 'desglose', 'cuenta', 'asiento'].includes(ruta.tipo)
        ? 'variance'
        : null
  const activa: IdPantalla | undefined = pedida ?? abribles[0]?.id
  const permitida = activa !== undefined && abribles.some((p) => p.id === activa)

  function cambiarUsuario(email: string) {
    fijarUsuarioDev(email) // antes de que los paneles vuelvan a consultar
    guardarUsuarioDev(email)
    setUsuario(email)
    setHotelId(null)
  }

  const actual = activa ? pantallaDe(activa) : undefined
  const detalle: Record<string, string> = { desglose: 'Desglose', cuenta: 'Movimientos', asiento: 'Asiento' }
  const ubicacion = [
    ...(actual?.grupo ? [actual.grupo] : []),
    ...(actual ? [actual.nombre] : []),
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
            {GRUPOS.map((grupo) => {
              const items = abribles.filter((p) => p.grupo === grupo)
              if (items.length === 0) return null
              return (
                <div key={grupo} className="nav-grupo" role="group" aria-label={grupo}>
                  <p className="nav-titulo" aria-hidden="true">
                    {grupo}
                  </p>
                  {items.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      className={p.id === activa ? 'pestana activa' : 'pestana'}
                      aria-current={p.id === activa ? 'page' : undefined}
                      onClick={() => {
                        window.location.hash = rutaDe(p.id)
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
            <MenuUsuario
              nombre={sesion.usuario.nombre}
              correo={sesion.usuario.email}
              alAbrirCuenta={() => {
                window.location.hash = rutaDe('cuenta')
              }}
              alCerrarSesion={sesion.cerrar}
            />
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

          {hotel && activa && !permitida && activa !== 'variance' && <SinAcceso />}
          {hotel && activa && (permitida || activa === 'variance') && (
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
                            window.location.hash = rutaDe('budget')
                          }
                        : undefined
                    }
                  />
                </RutaProtegida>
              )}
              {activa === 'budget' && <PanelBudget hotelId={hotel.id} />}
              {activa === 'auditoria' && <PanelAuditoria hotelId={hotel.id} version={version} />}
              {activa === 'usuarios' && (
                <PanelUsuarios hotelId={hotel.id} yoId={sesion?.usuario.usuario_id} />
              )}
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
