// Compara la referencia con una captura de la app: lado a lado y superposición al 50 %.
// Sin dependencias nuevas: usa Chromium de Playwright para componer las imágenes en un canvas.
//   node scripts/comparar_imagenes.mjs <referencia.png> <captura.png> <salida-sin-extension>
import { chromium } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'

const [referencia, captura, salida] = process.argv.slice(2)
if (!referencia || !captura || !salida) {
  console.error('Uso: node scripts/comparar_imagenes.mjs <referencia> <captura> <salida-sin-extension>')
  process.exit(1)
}

const uri = (ruta) => `data:image/png;base64,${readFileSync(ruta).toString('base64')}`
const navegador = await chromium.launch()
const pagina = await navegador.newPage()

const resultado = await pagina.evaluate(
  async ([a, b]) => {
    const cargar = (src) =>
      new Promise((ok, mal) => {
        const i = new Image()
        i.onload = () => ok(i)
        i.onerror = mal
        i.src = src
      })
    const [ia, ib] = await Promise.all([cargar(a), cargar(b)])
    const ancho = Math.max(ia.width, ib.width)
    const alto = Math.max(ia.height, ib.height)

    const lado = document.createElement('canvas')
    lado.width = ancho * 2 + 20
    lado.height = alto
    const cl = lado.getContext('2d')
    cl.fillStyle = '#ffffff'
    cl.fillRect(0, 0, lado.width, lado.height)
    cl.drawImage(ia, 0, 0)
    cl.drawImage(ib, ancho + 20, 0)

    const sup = document.createElement('canvas')
    sup.width = ancho
    sup.height = alto
    const cs = sup.getContext('2d')
    cs.fillStyle = '#ffffff'
    cs.fillRect(0, 0, ancho, alto)
    cs.globalAlpha = 0.5
    cs.drawImage(ia, 0, 0)
    cs.drawImage(ib, 0, 0)

    return {
      lado: lado.toDataURL('image/png'),
      superposicion: sup.toDataURL('image/png'),
      medidas: { referencia: [ia.width, ia.height], captura: [ib.width, ib.height] },
    }
  },
  [uri(referencia), uri(captura)],
)

const aBytes = (url) => Buffer.from(url.split(',')[1], 'base64')
writeFileSync(`${salida}-lado-a-lado.png`, aBytes(resultado.lado))
writeFileSync(`${salida}-overlay-50.png`, aBytes(resultado.superposicion))
console.log('medidas', JSON.stringify(resultado.medidas))
await navegador.close()
