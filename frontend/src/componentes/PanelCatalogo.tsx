import { useMemo, useState } from 'react'
import { obtenerTipado } from '../api/cliente'
import type { NodoCatalogo } from '../api/tipos'
import { useDatos } from '../api/useDatos'
import { ImportarCatalogo } from './ImportarCatalogo'
import { EncabezadoPagina } from './EncabezadoPagina'
import { Cargando, EstadoVacio, Insignia, MensajeError } from './Insignia'

function textoBuscable(n: NodoCatalogo): string {
  return [n.codigo, n.descripcion, n.depto_ef, n.grupo_ef, n.cuenta_sat, n.tipo]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

type EstadoCatalogo = 'todos' | 'movimientos' | 'sin_jerarquia' | 'fuera'

const ESTADOS: { id: EstadoCatalogo; etiqueta: string }[] = [
  { id: 'todos', etiqueta: 'Todas' },
  { id: 'movimientos', etiqueta: 'Con movimientos' },
  { id: 'sin_jerarquia', etiqueta: 'Sin jerarquía' },
  { id: 'fuera', etiqueta: 'Fuera del catálogo' },
]

/** Tiene movimientos pero no está en el catálogo oficial (y el CON130 tampoco le dio tipo). */
function fueraDelCatalogo(n: NodoCatalogo): boolean {
  return n.con_movimientos && !n.en_catalogo_oficial && n.tipo === null
}

function cumpleEstado(n: NodoCatalogo, estado: EstadoCatalogo): boolean {
  if (estado === 'movimientos') return n.con_movimientos
  if (estado === 'sin_jerarquia') return n.sin_jerarquia
  if (estado === 'fuera') return fueraDelCatalogo(n)
  return true
}

/** Conserva los nodos que cumplen la búsqueda y el estado elegido, junto con sus ancestros. */
function filtrar(nodos: NodoCatalogo[], consulta: string, estado: EstadoCatalogo): NodoCatalogo[] {
  const q = consulta.trim().toLowerCase()
  if (!q && estado === 'todos') return nodos
  const resultado: NodoCatalogo[] = []
  for (const n of nodos) {
    const hijos = filtrar(n.hijos, consulta, estado)
    const coincide = (!q || textoBuscable(n).includes(q)) && cumpleEstado(n, estado)
    // si el nodo coincide por la búsqueda sola, se conservan todos sus hijos (como antes)
    const todosLosHijos = coincide && estado === 'todos'
    if (coincide || hijos.length > 0) resultado.push({ ...n, hijos: todosLosHijos ? n.hijos : hijos })
  }
  return resultado
}

function contar(nodos: NodoCatalogo[]): number {
  return nodos.reduce((acc, n) => acc + 1 + contar(n.hijos), 0)
}

interface Props {
  hotelId: number
  version: number
  puedeImportar: boolean
  alCambiar: () => void
}

export function PanelCatalogo({ hotelId, version, puedeImportar, alCambiar }: Props) {
  const arbol = useDatos(
    () => obtenerTipado('/api/v1/hoteles/{hotel_id}/catalogo/arbol', {
        path: { hotel_id: hotelId },
      }),
    [hotelId, version],
  )
  const [consulta, setConsulta] = useState('')
  const [estado, setEstado] = useState<EstadoCatalogo>('todos')
  const [seleccionada, setSeleccionada] = useState<NodoCatalogo | null>(null)
  const visibles = useMemo(
    () => (arbol.datos ? filtrar(arbol.datos, consulta, estado) : []),
    [arbol.datos, consulta, estado],
  )
  const filtrando = consulta.trim() !== '' || estado !== 'todos'

  return (
    <div className="pantalla-datos">
      {puedeImportar && <ImportarCatalogo hotelId={hotelId} alCambiar={alCambiar} />}
      <section className="tarjeta" aria-labelledby="titulo-catalogo">
        <EncabezadoPagina id="titulo-catalogo" titulo="Catálogo de cuentas" />
        {arbol.cargando && <Cargando />}
        {arbol.error && <MensajeError texto={arbol.error} />}
        {arbol.datos && arbol.datos.length === 0 && (
          <EstadoVacio>
            El catálogo se forma al importar el catálogo oficial o al cargar el primer archivo.
          </EstadoVacio>
        )}
        {arbol.datos && arbol.datos.length > 0 && (
          <>
            <div className="filtros">
              <label className="chip-filtro chip-ancho">
                Buscar cuenta
                <input
                  type="search"
                  placeholder="Código, nombre, departamento o código SAT"
                  value={consulta}
                  onChange={(e) => setConsulta(e.target.value)}
                />
              </label>
              <div className="chips-estado" role="group" aria-label="Filtrar por estado">
                {ESTADOS.map((e) => (
                  <button
                    key={e.id}
                    type="button"
                    className={estado === e.id ? 'chip chip-activo' : 'chip'}
                    aria-pressed={estado === e.id}
                    onClick={() => setEstado(e.id)}
                  >
                    {e.etiqueta}
                  </button>
                ))}
              </div>
            </div>
            <p className="suave" role="status">
              {contar(visibles)} de {contar(arbol.datos)} nodos.
            </p>
            <div className="catalogo-cuerpo">
              <ul className="arbol" role="tree">
                {visibles.map((n) => (
                  <Nodo
                    key={n.codigo}
                    nodo={n}
                    abiertoPorDefecto={filtrando}
                    elegida={seleccionada?.codigo ?? null}
                    alElegir={setSeleccionada}
                  />
                ))}
              </ul>
              <aside className="detalle-cuenta" aria-label="Detalle de la cuenta">
                <DetalleCuenta nodo={seleccionada} />
              </aside>
            </div>
          </>
        )}
      </section>
    </div>
  )
}

function Nodo({
  nodo,
  abiertoPorDefecto,
  elegida,
  alElegir,
}: {
  nodo: NodoCatalogo
  abiertoPorDefecto: boolean
  elegida: string | null
  alElegir: (n: NodoCatalogo) => void
}) {
  const [abierto, setAbierto] = useState(false)
  const expandido = abiertoPorDefecto || abierto
  const tieneHijos = nodo.hijos.length > 0
  const fuera = fueraDelCatalogo(nodo)
  return (
    <li role="treeitem" aria-expanded={tieneHijos ? expandido : undefined}>
      <div className={elegida === nodo.codigo ? 'nodo nodo-elegido' : 'nodo'}>
        {tieneHijos ? (
          <button
            type="button"
            className="nodo-boton"
            onClick={() => setAbierto(!abierto)}
            aria-label={`${expandido ? 'Contraer' : 'Expandir'} ${nodo.codigo}`}
          >
            {expandido ? '▾' : '▸'}
          </button>
        ) : (
          <span className="nodo-espacio" />
        )}
        <button
          type="button"
          className="nodo-seleccion"
          aria-pressed={elegida === nodo.codigo}
          onClick={() => alElegir(nodo)}
        >
          <code>{nodo.codigo}</code>
          <span className={nodo.activa ? undefined : 'fila-apagada'}>
            {nodo.descripcion ?? <em className="suave">sin descripción</em>}
          </span>
        </button>
        {nodo.es_titulo && <Insignia tono="neutro">título</Insignia>}
        {nodo.tipo && (
          <Insignia tono={nodo.tipo === 'Acreedor' ? 'aviso' : 'info'}>{nodo.tipo}</Insignia>
        )}
        {nodo.depto_ef && <Insignia tono="neutro">{nodo.depto_ef}</Insignia>}
        {nodo.con_movimientos && <Insignia tono="info">movimientos</Insignia>}
        {!nodo.activa && <Insignia tono="error">inactiva</Insignia>}
        {nodo.sin_jerarquia && <Insignia tono="aviso">sin jerarquía</Insignia>}
        {fuera && <Insignia tono="aviso">fuera del catálogo</Insignia>}
        {nodo.cuenta_sat && <span className="suave">SAT {nodo.cuenta_sat}</span>}
      </div>
      {tieneHijos && expandido && (
        <ul role="group">
          {nodo.hijos.map((h) => (
            <Nodo
              key={h.codigo}
              nodo={h}
              abiertoPorDefecto={abiertoPorDefecto}
              elegida={elegida}
              alElegir={alElegir}
            />
          ))}
        </ul>
      )}
    </li>
  )
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string | null }) {
  return (
    <>
      <dt>{etiqueta}</dt>
      <dd>{valor ?? <span className="suave">—</span>}</dd>
    </>
  )
}

/** Detalle de la cuenta elegida en el árbol: solo lo que ya trae el catálogo. */
function DetalleCuenta({ nodo }: { nodo: NodoCatalogo | null }) {
  if (!nodo) return <EstadoVacio>Elige una cuenta del árbol para ver su detalle.</EstadoVacio>
  return (
    <>
      <h3>{nodo.codigo}</h3>
      <p>{nodo.descripcion ?? <em className="suave">sin descripción</em>}</p>
      <p className="estados-cuenta">
        {nodo.es_titulo && <Insignia tono="neutro">título</Insignia>}
        {nodo.con_movimientos && <Insignia tono="info">movimientos</Insignia>}
        {!nodo.activa && <Insignia tono="error">inactiva</Insignia>}
        {nodo.sin_jerarquia && <Insignia tono="aviso">sin jerarquía</Insignia>}
        {fueraDelCatalogo(nodo) && <Insignia tono="aviso">fuera del catálogo</Insignia>}
        {nodo.en_catalogo_oficial && <Insignia tono="ok">catálogo oficial</Insignia>}
      </p>
      <dl className="datos-cuenta">
        <Dato etiqueta="Tipo" valor={nodo.tipo} />
        <Dato etiqueta="Departamento" valor={nodo.depto_ef} />
        <Dato etiqueta="Grupo" valor={nodo.grupo_ef} />
        <Dato etiqueta="Cuenta SAT" valor={nodo.cuenta_sat} />
        <Dato etiqueta="Clase" valor={nodo.clase} />
        <Dato etiqueta="Nivel" valor={nodo.nivel === null ? null : String(nodo.nivel)} />
        <Dato etiqueta="Subcuentas" valor={String(nodo.hijos.length)} />
      </dl>
    </>
  )
}
