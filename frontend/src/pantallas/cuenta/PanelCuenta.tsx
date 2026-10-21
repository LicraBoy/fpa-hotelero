import { useState, type FormEvent } from 'react'
import {
  cambiarPassword,
  confirmarMfa,
  desactivarMfa,
  iniciarMfa,
  type MfaIniciada,
  type UsuarioSesion,
} from '../../api/auth'
import { ErrorApi } from '../../api/cliente'
import { EncabezadoPagina } from '../../componentes/EncabezadoPagina'
import { Insignia, MensajeError } from '../../componentes/Insignia'

interface Props {
  usuario: UsuarioSesion
  /** Vuelve a pedir el estado de la sesión (p. ej. tras activar el segundo factor). */
  alCambiar: () => void
}

function texto(e: unknown): string {
  return e instanceof ErrorApi ? e.detalle : 'No se pudo completar la acción'
}

export function PanelCuenta({ usuario, alCambiar }: Props) {
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [msgPass, setMsgPass] = useState<{ ok: boolean; texto: string } | null>(null)
  const [mfa, setMfa] = useState<MfaIniciada | null>(null)
  const [codigo, setCodigo] = useState('')
  const [passMfa, setPassMfa] = useState('')
  const [errorMfa, setErrorMfa] = useState<string | null>(null)

  async function guardarPassword(e: FormEvent) {
    e.preventDefault()
    setMsgPass(null)
    try {
      await cambiarPassword(actual, nueva)
      setActual('')
      setNueva('')
      setMsgPass({ ok: true, texto: 'Contraseña actualizada. Las demás sesiones se cerraron.' })
      alCambiar()
    } catch (err) {
      setMsgPass({ ok: false, texto: texto(err) })
    }
  }

  async function empezarMfa() {
    setErrorMfa(null)
    try {
      setMfa(await iniciarMfa())
    } catch (err) {
      setErrorMfa(texto(err))
    }
  }

  async function terminarMfa(e: FormEvent) {
    e.preventDefault()
    setErrorMfa(null)
    try {
      await confirmarMfa(codigo.trim())
      setMfa(null)
      setCodigo('')
      alCambiar()
    } catch (err) {
      setErrorMfa(texto(err))
    }
  }

  async function quitarMfa(e: FormEvent) {
    e.preventDefault()
    setErrorMfa(null)
    try {
      await desactivarMfa(passMfa)
      setPassMfa('')
      alCambiar()
    } catch (err) {
      setErrorMfa(texto(err))
    }
  }

  return (
    <section className="cuenta" aria-labelledby="titulo-cuenta">
      <EncabezadoPagina
        id="titulo-cuenta"
        titulo="Mi cuenta"
        subtitulo={`${usuario.nombre} · ${usuario.email}`}
      />
      {usuario.debe_cambiar_password && (
        <p className="mensaje mensaje-aviso" role="status">
          Tu contraseña es temporal: cámbiala ahora.
        </p>
      )}

      <section className="tarjeta" aria-labelledby="t-pass">
        <h3 id="t-pass">Cambiar contraseña</h3>
        <form className="formulario" onSubmit={guardarPassword}>
          <label>
            Contraseña actual
            <input
              type="password"
              autoComplete="current-password"
              value={actual}
              onChange={(e) => setActual(e.target.value)}
              required
            />
          </label>
          <label>
            Contraseña nueva
            <span className="suave">Mínimo 10 caracteres, con letras y números</span>
            <input
              type="password"
              autoComplete="new-password"
              value={nueva}
              onChange={(e) => setNueva(e.target.value)}
              required
            />
          </label>
          <button type="submit" className="boton">
            Guardar contraseña
          </button>
        </form>
        {msgPass &&
          (msgPass.ok ? (
            <p className="mensaje mensaje-ok" role="status">
              {msgPass.texto}
            </p>
          ) : (
            <MensajeError texto={msgPass.texto} />
          ))}
      </section>

      <section className="tarjeta" aria-labelledby="t-mfa">
        <h3 id="t-mfa">
          Verificación en dos pasos{' '}
          <Insignia tono={usuario.totp_activo ? 'ok' : 'neutro'}>
            {usuario.totp_activo ? 'Activa' : 'Desactivada'}
          </Insignia>
        </h3>
        {usuario.debe_activar_mfa && (
          <p className="mensaje mensaje-aviso" role="status">
            Tu rol requiere verificación en dos pasos: actívala.
          </p>
        )}
        {!usuario.totp_activo && !mfa && (
          <button type="button" className="boton" onClick={empezarMfa}>
            Activar verificación en dos pasos
          </button>
        )}
        {mfa && (
          <form className="formulario" onSubmit={terminarMfa}>
            <p>
              En tu app de autenticación (Microsoft Authenticator, Google Authenticator…) agrega una
              cuenta con esta clave y escribe el código de 6 dígitos que muestre.
            </p>
            <p>
              Clave: <code className="clave-mfa">{mfa.secreto}</code>
            </p>
            <p className="suave">
              Dirección para apps que la aceptan: <code className="clave-mfa">{mfa.uri}</code>
            </p>
            <label>
              Código de 6 dígitos
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={7}
                value={codigo}
                onChange={(e) => setCodigo(e.target.value)}
                required
              />
            </label>
            <button type="submit" className="boton">
              Confirmar y activar
            </button>
          </form>
        )}
        {usuario.totp_activo && (
          <form className="formulario" onSubmit={quitarMfa}>
            <label>
              Contraseña para desactivarla
              <input
                type="password"
                autoComplete="current-password"
                value={passMfa}
                onChange={(e) => setPassMfa(e.target.value)}
                required
              />
            </label>
            <button type="submit" className="boton boton-secundario">
              Desactivar verificación en dos pasos
            </button>
          </form>
        )}
        {errorMfa && <MensajeError texto={errorMfa} />}
      </section>
    </section>
  )
}
