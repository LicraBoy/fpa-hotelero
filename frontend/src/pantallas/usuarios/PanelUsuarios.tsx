import { useState, type FormEvent } from 'react'
import { ErrorApi, enviarJson, obtenerTipado } from '../../api/cliente'
import type { components } from '../../api/schema'
import { useDatos } from '../../api/useDatos'
import { EncabezadoPagina } from '../../componentes/EncabezadoPagina'
import { Cargando, EstadoVacio, Insignia, MensajeError } from '../../componentes/Insignia'

type Usuario = components['schemas']['UsuarioAdmin']
type Lista = components['schemas']['ListaUsuarios']

interface Formulario {
  email: string
  nombre: string
  rol: string
  secciones: string[]
}

const VACIO: Formulario = { email: '', nombre: '', rol: 'analista', secciones: [] }

function texto(e: unknown): string {
  return e instanceof ErrorApi ? e.detalle : 'No se pudo completar la acción'
}

/** Selector de secciones del reporte (solo para los roles que las usan). */
function Secciones({
  disponibles,
  elegidas,
  alCambiar,
}: {
  disponibles: string[]
  elegidas: string[]
  alCambiar: (nuevas: string[]) => void
}) {
  if (disponibles.length === 0) {
    return <p className="suave">Todavía no hay una estructura del reporte cargada: no hay secciones que asignar.</p>
  }
  return (
    <fieldset className="grupo-secciones">
      <legend>Secciones del Variance que verá y comentará</legend>
      {disponibles.map((s) => (
        <label key={s} className="opcion-seccion">
          <input
            type="checkbox"
            checked={elegidas.includes(s)}
            onChange={(e) =>
              alCambiar(e.target.checked ? [...elegidas, s] : elegidas.filter((x) => x !== s))
            }
          />
          {s}
        </label>
      ))}
    </fieldset>
  )
}

export function PanelUsuarios({ hotelId, yoId }: { hotelId: number; yoId?: number }) {
  const lista = useDatos(
    () => obtenerTipado('/api/v1/hoteles/{hotel_id}/usuarios', { path: { hotel_id: hotelId } }),
    [hotelId],
  )
  const [nuevo, setNuevo] = useState<Formulario | null>(null)
  const [editando, setEditando] = useState<(Formulario & { id: number; activo: boolean }) | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [clave, setClave] = useState<{ para: string; valor: string } | null>(null)

  const base = `/api/v1/hoteles/${hotelId}/usuarios`

  async function accion(fn: () => Promise<void>) {
    setError(null)
    setAviso(null)
    try {
      await fn()
      lista.recargar()
    } catch (e) {
      setError(texto(e))
    }
  }

  function crear(e: FormEvent, datos: Lista) {
    e.preventDefault()
    if (!nuevo) return
    const conSecciones = datos.roles_por_seccion.includes(nuevo.rol)
    void accion(async () => {
      const r = await enviarJson<components['schemas']['UsuarioCreado']>('POST', base, {
        email: nuevo.email,
        nombre: nuevo.nombre,
        rol: nuevo.rol,
        secciones: conSecciones ? nuevo.secciones : [],
      })
      if (r?.password_temporal) setClave({ para: r.usuario.email, valor: r.password_temporal })
      else setAviso('Se agregó el acceso al hotel (la persona ya tenía cuenta).')
      setNuevo(null)
    })
  }

  function guardar(e: FormEvent, datos: Lista) {
    e.preventDefault()
    if (!editando) return
    const conSecciones = datos.roles_por_seccion.includes(editando.rol)
    void accion(async () => {
      await enviarJson('PATCH', `${base}/${editando.id}`, {
        nombre: editando.nombre,
        rol: editando.rol,
        activo: editando.activo,
        ...(conSecciones ? { secciones: editando.secciones } : {}),
      })
      setAviso('Cambios guardados.')
      setEditando(null)
    })
  }

  function restablecer(u: Usuario) {
    void accion(async () => {
      const r = await enviarJson<{ password_temporal: string }>(
        'POST',
        `${base}/${u.usuario_id}/restablecer-password`,
      )
      if (r) setClave({ para: u.email, valor: r.password_temporal })
    })
  }

  function desbloquear(u: Usuario) {
    void accion(async () => {
      await enviarJson('POST', `${base}/${u.usuario_id}/desbloquear`)
      setAviso(`Cuenta desbloqueada: ${u.email}.`)
    })
  }

  return (
    <section aria-labelledby="titulo-usuarios">
      <EncabezadoPagina
        id="titulo-usuarios"
        titulo="Usuarios"
        subtitulo="Quién entra a este hotel, con qué rol y qué secciones del Variance ve cada responsable."
        acciones={
          lista.datos && (
            <button
              type="button"
              className="boton"
              onClick={() => {
                setClave(null)
                setEditando(null)
                setNuevo({ ...VACIO })
              }}
            >
              Nuevo usuario
            </button>
          )
        }
      />
      {lista.cargando && <Cargando />}
      {lista.error && <MensajeError texto={lista.error} />}
      {error && <MensajeError texto={error} />}
      {aviso && (
        <p className="mensaje mensaje-ok" role="status">
          {aviso}
        </p>
      )}
      {clave && (
        <div className="mensaje mensaje-aviso" role="status">
          <p>
            Contraseña temporal de <strong>{clave.para}</strong>:
          </p>
          <code className="clave-mfa">{clave.valor}</code>
          <p className="suave">
            Entrégala por un medio seguro. No se vuelve a mostrar y la persona deberá cambiarla al
            entrar.
          </p>
        </div>
      )}

      {lista.datos && (
        <>
          {nuevo && (
            <form className="tarjeta formulario" onSubmit={(e) => crear(e, lista.datos!)}>
              <h3>Nuevo usuario</h3>
              <label>
                Correo (es su usuario de entrada)
                <input
                  type="email"
                  value={nuevo.email}
                  onChange={(e) => setNuevo({ ...nuevo, email: e.target.value })}
                  required
                />
              </label>
              <label>
                Nombre
                <input
                  type="text"
                  value={nuevo.nombre}
                  onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })}
                  required
                />
              </label>
              <label>
                Rol
                <select aria-label="Rol" value={nuevo.rol} onChange={(e) => setNuevo({ ...nuevo, rol: e.target.value })}>
                  {Object.entries(lista.datos.roles).map(([codigo, nombre]) => (
                    <option key={codigo} value={codigo}>
                      {nombre}
                    </option>
                  ))}
                </select>
              </label>
              {lista.datos.roles_por_seccion.includes(nuevo.rol) && (
                <Secciones
                  disponibles={lista.datos.secciones_disponibles}
                  elegidas={nuevo.secciones}
                  alCambiar={(secciones) => setNuevo({ ...nuevo, secciones })}
                />
              )}
              <div className="acciones-formulario">
                <button type="submit" className="boton">
                  Crear usuario
                </button>
                <button type="button" className="boton boton-secundario" onClick={() => setNuevo(null)}>
                  Cancelar
                </button>
              </div>
            </form>
          )}

          {editando && (
            <form className="tarjeta formulario" onSubmit={(e) => guardar(e, lista.datos!)}>
              <h3>Editar usuario</h3>
              <label>
                Nombre
                <input
                  type="text"
                  value={editando.nombre}
                  onChange={(e) => setEditando({ ...editando, nombre: e.target.value })}
                  required
                />
              </label>
              <label>
                Rol
                <select
                  aria-label="Rol"
                  value={editando.rol}
                  disabled={editando.id === yoId}
                  onChange={(e) => setEditando({ ...editando, rol: e.target.value })}
                >
                  {Object.entries(lista.datos.roles).map(([codigo, nombre]) => (
                    <option key={codigo} value={codigo}>
                      {nombre}
                    </option>
                  ))}
                </select>
              </label>
              {lista.datos.roles_por_seccion.includes(editando.rol) && (
                <Secciones
                  disponibles={lista.datos.secciones_disponibles}
                  elegidas={editando.secciones}
                  alCambiar={(secciones) => setEditando({ ...editando, secciones })}
                />
              )}
              <label className="opcion-seccion">
                <input
                  type="checkbox"
                  checked={editando.activo}
                  disabled={editando.id === yoId}
                  onChange={(e) => setEditando({ ...editando, activo: e.target.checked })}
                />
                Cuenta activa
              </label>
              <div className="acciones-formulario">
                <button type="submit" className="boton">
                  Guardar cambios
                </button>
                <button type="button" className="boton boton-secundario" onClick={() => setEditando(null)}>
                  Cancelar
                </button>
              </div>
            </form>
          )}

          {lista.datos.usuarios.length === 0 ? (
            <EstadoVacio>Este hotel todavía no tiene usuarios.</EstadoVacio>
          ) : (
            <div className="tabla-contenedor">
              <table className="tabla">
                <caption className="solo-lectores">Usuarios del hotel</caption>
                <thead>
                  <tr>
                    <th scope="col">Nombre</th>
                    <th scope="col">Rol</th>
                    <th scope="col">Secciones</th>
                    <th scope="col">Estado</th>
                    <th scope="col">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {lista.datos.usuarios.map((u) => (
                    <tr key={u.usuario_id}>
                      <th scope="row">
                        {u.nombre}
                        <span className="suave bloque">{u.email}</span>
                      </th>
                      <td>{u.rol_nombre}</td>
                      <td>
                        {lista.datos!.roles_por_seccion.includes(u.rol)
                          ? u.secciones.length > 0
                            ? u.secciones.join(', ')
                            : 'Ninguna (no ve líneas)'
                          : 'Todo el reporte'}
                      </td>
                      <td>
                        {!u.activo ? (
                          <Insignia tono="error">Inactiva</Insignia>
                        ) : u.bloqueado ? (
                          <Insignia tono="aviso">Bloqueada</Insignia>
                        ) : (
                          <Insignia tono="ok">Activa</Insignia>
                        )}{' '}
                        {u.totp_activo && <Insignia tono="info">2 pasos</Insignia>}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="boton boton-secundario"
                          onClick={() => {
                            setClave(null)
                            setNuevo(null)
                            setEditando({
                              id: u.usuario_id,
                              email: u.email,
                              nombre: u.nombre,
                              rol: u.rol,
                              secciones: u.secciones,
                              activo: u.activo,
                            })
                          }}
                        >
                          Editar {u.nombre}
                        </button>
                        <button
                          type="button"
                          className="boton boton-secundario"
                          onClick={() => restablecer(u)}
                        >
                          Restablecer contraseña de {u.nombre}
                        </button>
                        {u.bloqueado && (
                          <button
                            type="button"
                            className="boton boton-secundario"
                            onClick={() => desbloquear(u)}
                          >
                            Desbloquear a {u.nombre}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  )
}
