// Recorta (y amplía) una zona de una imagen para medirla: útil para comparar con la referencia.
//   node scripts/recortar_imagen.mjs <entrada.png> <x> <y> <ancho> <alto> <escala> <salida.png>
// Con `muestreo` como 8.º argumento («x,y;x,y») imprime el color de esos píxeles.
import { chromium } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'

const [entrada, x, y, ancho, alto, escala, salida, muestreo] = process.argv.slice(2)
if (!salida) {
  console.error('Uso: node scripts/recortar_imagen.mjs <entrada> <x> <y> <ancho> <alto> <escala> <salida> [x,y;x,y]')
  process.exit(1)
}
const navegador = await chromium.launch()
const pagina = await navegador.newPage()
const r = await pagina.evaluate(
  async ([src, x, y, w, h, k, puntos]) => {
    const img = await new Promise((ok, mal) => {
      const i = new Image()
      i.onload = () => ok(i)
      i.onerror = mal
      i.src = src
    })
    const c = document.createElement('canvas')
    c.width = w * k
    c.height = h * k
    const cx = c.getContext('2d')
    cx.imageSmoothingEnabled = false
    cx.drawImage(img, x, y, w, h, 0, 0, w * k, h * k)
    const base = document.createElement('canvas')
    base.width = img.width
    base.height = img.height
    const cb = base.getContext('2d')
    cb.drawImage(img, 0, 0)
    const colores = (puntos ? puntos.split(';') : []).map((p) => {
      const [px, py] = p.split(',').map(Number)
      const d = cb.getImageData(px, py, 1, 1).data
      return `${p} = #${[d[0], d[1], d[2]].map((n) => n.toString(16).padStart(2, '0')).join('')}`
    })
    return { png: c.toDataURL('image/png'), colores, tam: [img.width, img.height] }
  },
  [`data:image/png;base64,${readFileSync(entrada).toString('base64')}`, +x, +y, +ancho, +alto, +escala, muestreo ?? ''],
)
writeFileSync(salida, Buffer.from(r.png.split(',')[1], 'base64'))
console.log('tamaño', r.tam.join('x'))
for (const c of r.colores) console.log(c)
await navegador.close()
