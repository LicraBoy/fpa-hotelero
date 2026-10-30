import { useEffect, useState } from 'react'
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
import { PanelDepartamentos } from './pantallas/departamentos/PanelDepartamentos'
import { PanelBudget } from './pantallas/budget/PanelBudget'
import { PESTANAS_BUDGET, type PestanaBudget } from './pantallas/budget/componentes/BudgetTabs'
import { PanelVariance } from './pantallas/variance/PanelVariance'
import { MenuUsuario } from './componentes/MenuUsuario'
import { PANTALLAS, pantallaDe, puedeAbrir, rutaDe, type IdPantalla } from './ruta/navegacion'
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

const IDS_FINANCIERO: IdPantalla[] = ['variance', 'departamentos', 'saldos']
const IDS_OTROS: IdPantalla[] = ['cargas', 'catalogo', 'auditoria', 'usuarios']

function inicialesDe(nombre: string): string {
  return (
    nombre
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p.replace(/[^\p{L}\p{N}]/gu, '')[0]?.toUpperCase() ?? '')
      .join('') || '?'
  )
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
  const [lateralPlegado, setLateralPlegado] = useState(() => leerLateralPlegado() || window.innerWidth < 1024)
  // Sub-navegación de Budget Studio (Resumen/Captura/Versiones): vive aquí, no en PanelBudget, para
  // que el sidebar la controle igual que cualquier otra sección — sin inventar rutas nuevas.
  const [pestanaBudget, setPestanaBudget] = useState<PestanaBudget>('resumen')

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

  // Sin ruta (o con una que no existe) la barra de direcciones pasa a la pantalla que se está viendo,
  // sin agregar un paso al historial; así lo que se ve siempre se puede enlazar.
  const rutaDeVariance = window.location.hash.startsWith('#/variance')
  useEffect(() => {
    if (!hotel || !activa || !permitida) return
    if (ruta.tipo === 'sin-ruta' || (ruta.tipo === 'invalida' && !rutaDeVariance)) {
      window.location.replace(rutaDe(activa))
    }
  }, [hotel, activa, permitida, ruta.tipo, rutaDeVariance])

  function cambiarUsuario(email: string) {
    fijarUsuarioDev(email) // antes de que los paneles vuelvan a consultar
    guardarUsuarioDev(email)
    setUsuario(email)
    setHotelId(null)
  }

  const actual = activa ? pantallaDe(activa) : undefined
  const detalle: Record<string, string> = { desglose: 'Desglose', cuenta: 'Movimientos', asiento: 'Asiento' }
  const etiquetaPestanaBudget = PESTANAS_BUDGET.find((p) => p.id === pestanaBudget)?.etiqueta ?? ''
  const ubicacion =
    activa === 'budget'
      ? ['Budget Studio', etiquetaPestanaBudget]
      : [
          ...(activa && IDS_FINANCIERO.includes(activa) ? ['Financiero'] : actual?.grupo ? [actual.grupo] : []),
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
            <h1>FPA Hotelero</h1>
            <p>Planificación Financiera Avanzada</p>
          </div>
        </div>

        {hotel && activa && (
          <nav className="navegacion" aria-label="Secciones">
            <div className="nav-grupo" role="group" aria-label="Financiero">
              {abribles
                .filter((p) => IDS_FINANCIERO.includes(p.id))
                .map((p) => (
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

            {abribles.some((p) => p.id === 'budget') && (
              <div className="nav-grupo" role="group" aria-label="Budget Studio">
                <button
                  type="button"
                  className={activa === 'budget' ? 'pestana pestana-grupo activa' : 'pestana pestana-grupo'}
                  aria-current={activa === 'budget' ? 'page' : undefined}
                  aria-expanded={activa === 'budget'}
                  onClick={() => {
                    window.location.hash = rutaDe('budget')
                  }}
                >
                  <Icono nombre={pantallaDe('budget').icono} />
                  <span>Budget Studio</span>
                  <Icono nombre="chevron" tamano={13} />
                </button>
                {activa === 'budget' && (
                  <div className="nav-subgrupo" role="tablist" aria-label="Secciones de Budget Studio">
                    {PESTANAS_BUDGET.map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        role="tab"
                        id={`budget-tab-${p.id}`}
                        aria-selected={pestanaBudget === p.id}
                        aria-controls={`budget-panel-${p.id}`}
                        className={pestanaBudget === p.id ? 'pestana pestana-sub activa' : 'pestana pestana-sub'}
                        onClick={() => setPestanaBudget(p.id)}
                      >
                        <Icono nombre={p.icono} tamano={16} />
                        <span>{p.etiqueta}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {abribles.some((p) => IDS_OTROS.includes(p.id)) && (
              <details className="nav-grupo nav-desplegable" open>
                <summary className="pestana pestana-grupo">
                  <Icono nombre="catalogo" />
                  <span>Administración</span>
                  <Icono nombre="chevron" tamano={13} />
                </summary>
                <div className="nav-subgrupo" role="group" aria-label="Administración">
                  {abribles
                    .filter((p) => IDS_OTROS.includes(p.id))
                    .map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        className={p.id === activa ? 'pestana pestana-sub activa' : 'pestana pestana-sub'}
                        aria-current={p.id === activa ? 'page' : undefined}
                        onClick={() => {
                          window.location.hash = rutaDe(p.id)
                        }}
                      >
                        <Icono nombre={p.icono} tamano={16} />
                        <span>{p.nombre}</span>
                      </button>
                    ))}
                </div>
              </details>
            )}
          </nav>
        )}

        <div className="lateral-pie">
          {sesion ? (
            <MenuUsuario
              nombre={sesion.usuario.nombre}
              correo={sesion.usuario.email}
              alAbrirCuenta={() => {
                window.location.hash = rutaDe('cuenta')
              }}
              alCerrarSesion={sesion.cerrar}
            />
          ) : (
            <div className="usuario-lateral">
              <span className="avatar avatar-lateral" aria-hidden="true">
                {inicialesDe(nombreUsuario)}
              </span>
              <label>
                <span className="solo-lectores">Usuario (desarrollo)</span>
                <select
                  aria-label="Usuario (desarrollo)"
                  value={usuarioDev}
                  title="Modo desarrollo: el usuario se elige a mano. En producción se entra con usuario y contraseña."
                  onChange={(e) => cambiarUsuario(e.target.value)}
                >
                  {USUARIOS_DESARROLLO.map((u) => (
                    <option key={u.email} value={u.email}>
                      {u.nombre}
                    </option>
                  ))}
                </select>
                <span className="usuario-lateral-rol">{rol ? (NOMBRE_ROL[rol] ?? rol) : 'Modo desarrollo'}</span>
              </label>
              {alProbarLogin && (
                <button
                  type="button"
                  className="boton-icono boton-engranaje"
                  onClick={alProbarLogin}
                  aria-label="Probar inicio de sesión real"
                  title="Probar inicio de sesión real"
                >
                  <Icono nombre="usuario" tamano={16} />
                </button>
              )}
            </div>
          )}
          {hoteles.datos && hoteles.datos.length > 0 && (
            <label className="selector-hotel-lateral">
              <span className="avatar avatar-hotel" aria-hidden="true">
                <Icono nombre="hotel" tamano={18} />
              </span>
              <span className="solo-lectores">Hotel</span>
              <select aria-label="Hotel" value={hotel?.id ?? ''} onChange={(e) => setHotelId(Number(e.target.value))}>
                {hoteles.datos.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.nombre}
                  </option>
                ))}
              </select>
              <span className="selector-hotel-rol">{rol ? (NOMBRE_ROL[rol] ?? rol) : ''}</span>
              <Icono nombre="chevron" tamano={14} />
            </label>
          )}
        </div>
      </aside>

      <div className="principal">
        <BarraSuperior
          lateralPlegado={lateralPlegado}
          alAlternarLateral={() => {
            guardarLateralPlegado(!lateralPlegado)
            setLateralPlegado(!lateralPlegado)
          }}
          ubicacion={ubicacion.length > 0 ? ubicacion : ['Inicio']}
          ayuda={
            activa === 'budget' && pestanaBudget === 'captura' ? (
              <>
                <strong>¿Cómo funciona Captura?</strong>
                <p>
                  Haz clic en una celda para escribir el Budget de ese mes. Los totales se calculan
                  solos y el Actual se ve al pasar el cursor. Si hay un ciclo abierto, Guardar manda
                  tu propuesta al ciclo; si no, crea una versión nueva del Budget.
                </p>
              </>
            ) : undefined
          }
        />
        <main
          className={
            activa === 'budget' && pestanaBudget === 'captura'
              ? 'contenido contenido-captura'
              : activa === 'variance' || activa === 'budget'
                ? 'contenido'
                : 'contenido contenido-estrecho'
          }
        >
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
              {activa === 'budget' && (
                <PanelBudget
                  hotelId={hotel.id}
                  rol={rol}
                  pestana={pestanaBudget}
                  onCambiarPestana={setPestanaBudget}
                />
              )}
              {activa === 'departamentos' && (
                <PanelDepartamentos
                  hotelId={hotel.id}
                  puedeVerCargas={puede(rol, 'carga:leer')}
                  puedeDesglosar={puede(rol, 'drilldown:leer')}
                />
              )}
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
