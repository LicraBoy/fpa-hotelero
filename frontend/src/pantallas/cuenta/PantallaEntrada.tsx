import { useState, type FormEvent } from 'react'
import { ErrorApi } from '../../api/cliente'
import { iniciarSesion, type UsuarioSesion } from '../../api/auth'
import { Logo } from '../../componentes/Iconos'
import { MensajeError } from '../../componentes/Insignia'

interface Props {
  alEntrar: (usuario: UsuarioSesion) => void
  /** Solo en desarrollo: volver al selector de usuarios de prueba. */
  alVolver?: () => void
}

export function PantallaEntrada({ alEntrar, alVolver }: Props) {
  const [usuario, setUsuario] = useState('')
  const [password, setPassword] = useState('')
  const [codigo, setCodigo] = useState('')
  const [pideCodigo, setPideCodigo] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      alEntrar(await iniciarSesion(usuario.trim(), password, codigo.trim()))
    } catch (err) {
      if (err instanceof ErrorApi && err.detalle.startsWith('Falta el código')) {
        setPideCodigo(true)
      } else {
        setError(err instanceof ErrorApi ? err.detalle : 'No se pudo iniciar sesión')
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <main className="entrada">
      <section className="tarjeta entrada-tarjeta" aria-labelledby="titulo-entrada">
        <div className="marca">
          <Logo />
          <div>
            <h1 id="titulo-entrada">Plataforma FP&amp;A Hotelera</h1>
            <p className="suave">Inicia sesión para continuar</p>
          </div>
        </div>
        <form className="formulario" onSubmit={enviar}>
          <label>
            Usuario (correo)
            <input
              type="text"
              autoComplete="username"
              value={usuario}
              onChange={(e) => setUsuario(e.target.value)}
              required
            />
          </label>
          <label>
            Contraseña
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {pideCodigo && (
            <label>
              Código de verificación
              <span className="suave">Los 6 dígitos de tu app de autenticación</span>
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={7}
                value={codigo}
                onChange={(e) => setCodigo(e.target.value)}
                required
                autoFocus
              />
            </label>
          )}
          <button type="submit" className="boton" disabled={enviando}>
            {enviando ? 'Entrando…' : 'Entrar'}
          </button>
        </form>
        {error && <MensajeError texto={error} />}
        {alVolver && (
          <button type="button" className="boton boton-secundario" onClick={alVolver}>
            Volver al selector de desarrollo
          </button>
        )}
      </section>
    </main>
  )
}
