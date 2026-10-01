// Verificaciones de seguridad del frontend que el linter no cubre. Sin dependencias.
//   - Nada que inyecte HTML o ejecute texto como código.
//   - Nada de almacenamiento del navegador salvo la lista blanca (y nunca con nombres de credencial).
//   - Nada de estilos o scripts en línea (la CSP los prohíbe).
// Corre dentro de `npm run lint`. Falla con código 1 y la lista de hallazgos.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative, sep } from 'node:path'

const RAIZ = process.cwd()
const SRC = join(RAIZ, 'src')

// Archivos generados o de prueba que no son código de la aplicación
const EXCLUIDOS = new Set(['src/api/schema.d.ts'])

// Único lugar donde se permite almacenamiento del navegador y con qué API.
const ALMACENAMIENTO_PERMITIDO = { 'src/util/preferencias.ts': ['sessionStorage'] }
const NOMBRE_DE_CREDENCIAL = /token|jwt|bearer|secret|password|contrase|credencial|apikey|api_key/i

const PROHIBIDOS = [
  [/dangerouslySetInnerHTML/, 'dangerouslySetInnerHTML (inyecta HTML sin escapar)'],
  [/\.(innerHTML|outerHTML)\b/, 'innerHTML/outerHTML'],
  [/insertAdjacentHTML/, 'insertAdjacentHTML'],
  [/document\.write/, 'document.write'],
  [/\beval\s*\(/, 'eval()'],
  [/new\s+Function\s*\(/, 'new Function()'],
  [/\bset(Timeout|Interval)\s*\(\s*['"`]/, 'setTimeout/setInterval con texto'],
  [/javascript:/i, 'URL javascript:'],
  [/\bstyle=\{\{/, 'estilo en línea (style={{...}}): la CSP lo bloquea; usa una clase CSS'],
  [/\bstyle="/, 'estilo en línea (style="..."): la CSP lo bloquea; usa una clase CSS'],
]

function archivos(dir) {
  const salida = []
  for (const nombre of readdirSync(dir)) {
    const ruta = join(dir, nombre)
    if (statSync(ruta).isDirectory()) salida.push(...archivos(ruta))
    else if (/\.(ts|tsx|js|jsx|mjs|html|css)$/.test(nombre)) salida.push(ruta)
  }
  return salida
}

const hallazgos = []
const rel = (ruta) => relative(RAIZ, ruta).split(sep).join('/')

for (const ruta of [...archivos(SRC), join(RAIZ, 'index.html')]) {
  const nombre = rel(ruta)
  if (EXCLUIDOS.has(nombre) || nombre.endsWith('.test.ts')) continue // las pruebas no se publican
  const lineas = readFileSync(ruta, 'utf8').split(/\r?\n/)
  lineas.forEach((linea, i) => {
    const codigo = linea.replace(/\/\/.*$/, '') // los comentarios pueden mencionar lo prohibido
    for (const [patron, motivo] of PROHIBIDOS) {
      if (patron.test(codigo) && !/^\s*(\*|\/\*)/.test(linea)) {
        hallazgos.push(`${nombre}:${i + 1}: ${motivo}`)
      }
    }
    for (const api of ['localStorage', 'sessionStorage', 'indexedDB', 'document.cookie']) {
      if (codigo.includes(api)) {
        const permitidas = ALMACENAMIENTO_PERMITIDO[nombre] ?? []
        if (!permitidas.includes(api)) {
          hallazgos.push(`${nombre}:${i + 1}: uso de ${api} fuera de la lista blanca`)
        } else if (NOMBRE_DE_CREDENCIAL.test(linea)) {
          hallazgos.push(`${nombre}:${i + 1}: ${api} con un nombre que parece una credencial`)
        }
      }
    }
  })
}

const html = readFileSync(join(RAIZ, 'index.html'), 'utf8')
if (/<script(?![^>]*\bsrc=)[^>]*>/i.test(html)) hallazgos.push('index.html: <script> en línea')
if (/<style[\s>]/i.test(html)) hallazgos.push('index.html: <style> en línea')

if (hallazgos.length > 0) {
  console.error('Verificación de seguridad del frontend: HALLAZGOS')
  for (const h of hallazgos) console.error(`  - ${h}`)
  process.exit(1)
}
console.log('Verificación de seguridad del frontend: sin hallazgos')
