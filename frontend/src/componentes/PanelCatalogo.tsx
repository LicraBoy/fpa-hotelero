import { useMemo, useState } from 'react'
import { obtener } from '../api/cliente'
import type { NodoCatalogo } from '../api/tipos'
import { useDatos } from '../api/useDatos'
import { ImportarCatalogo } from './ImportarCatalogo'
import { Cargando, Insignia, MensajeError } from './Insignia'

function textoBuscable(n: NodoCatalogo): string {
  return [n.codigo, n.descripcion, n.depto_ef, n.grupo_ef, n.cuenta_sat, n.tipo]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

/** Conserva los nodos que coinciden con la búsqueda y sus ancestros. */
function filtrar(nodos: NodoCatalogo[], consulta: string): NodoCatalogo[] {
  const q = consulta.trim().toLowerCase()
  if (!q) return nodos
  const resultado: NodoCatalogo[] = []
  for (const n of nodos) {
    const hijos = filtrar(n.hijos, consulta)
    const coincide = textoBuscable(n).includes(q)
    if (coincide || hijos.length > 0) resultado.push({ ...n, hijos: coincide ? n.hijos : hijos })
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
    () => obtener<NodoCatalogo[]>(`/hoteles/${hotelId}/catalogo/arbol`),
    [hotelId, version],
  )
  const [consulta, setConsulta] = useState('')
  const visibles = useMemo(
    () => (arbol.datos ? filtrar(arbol.datos, consulta) : []),
    [arbol.datos, consulta],
  )

  return (
    <>
      {puedeImportar && <ImportarCatalogo hotelId={hotelId} alCambiar={alCambiar} />}
      <section className="tarjeta" aria-labelledby="titulo-catalogo">
        <h2 id="titulo-catalogo">Catálogo de cuentas</h2>
        {arbol.cargando && <Cargando />}
        {arbol.error && <MensajeError texto={arbol.error} />}
        {arbol.datos && arbol.datos.length === 0 && (
          <p className="suave">
            El catálogo se forma al importar el catálogo oficial o al cargar el primer archivo.
          </p>
        )}
        {arbol.datos && arbol.datos.length > 0 && (
          <>
            <label className="buscador">
              Buscar cuenta
              <input
                type="search"
                placeholder="Código, nombre, departamento o código SAT"
                value={consulta}
                onChange={(e) => setConsulta(e.target.value)}
              />
            </label>
            <p className="suave">
              {contar(visibles)} de {contar(arbol.datos)} nodos.{' '}
              <Insignia tono="info">movimientos</Insignia> = cuenta con movimientos,{' '}
              <Insignia tono="neutro">título</Insignia> = grupo de la jerarquía,{' '}
              <Insignia tono="aviso">sin jerarquía</Insignia> = falta importar el catálogo oficial o
              cargar un CON130 que la ubique,{' '}
              <Insignia tono="aviso">fuera del catálogo</Insignia> = tiene movimientos pero no está
              en el catálogo oficial.
            </p>
            <ul className="arbol" role="tree">
              {visibles.map((n) => (
                <Nodo key={n.codigo} nodo={n} abiertoPorDefecto={consulta.trim() !== ''} />
              ))}
            </ul>
          </>
        )}
      </section>
    </>
  )
}

function Nodo({ nodo, abiertoPorDefecto }: { nodo: NodoCatalogo; abiertoPorDefecto: boolean }) {
  const [abierto, setAbierto] = useState(false)
  const expandido = abiertoPorDefecto || abierto
  const tieneHijos = nodo.hijos.length > 0
  const fueraDelCatalogo = nodo.con_movimientos && !nodo.en_catalogo_oficial && nodo.tipo === null
  return (
    <li role="treeitem" aria-expanded={tieneHijos ? expandido : undefined}>
      <div className="nodo">
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
        <code>{nodo.codigo}</code>
        <span className={nodo.activa ? undefined : 'fila-apagada'}>
          {nodo.descripcion ?? <em className="suave">sin descripción</em>}
        </span>
        {nodo.es_titulo && <Insignia tono="neutro">título</Insignia>}
        {nodo.tipo && (
          <Insignia tono={nodo.tipo === 'Acreedor' ? 'aviso' : 'info'}>{nodo.tipo}</Insignia>
        )}
        {nodo.depto_ef && <Insignia tono="neutro">{nodo.depto_ef}</Insignia>}
        {nodo.con_movimientos && <Insignia tono="info">movimientos</Insignia>}
        {!nodo.activa && <Insignia tono="error">inactiva</Insignia>}
        {nodo.sin_jerarquia && <Insignia tono="aviso">sin jerarquía</Insignia>}
        {fueraDelCatalogo && <Insignia tono="aviso">fuera del catálogo</Insignia>}
        {nodo.cuenta_sat && <span className="suave">SAT {nodo.cuenta_sat}</span>}
      </div>
      {tieneHijos && expandido && (
        <ul role="group">
          {nodo.hijos.map((h) => (
            <Nodo key={h.codigo} nodo={h} abiertoPorDefecto={abiertoPorDefecto} />
          ))}
        </ul>
      )}
    </li>
  )
}
