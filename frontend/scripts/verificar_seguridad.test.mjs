// Prueba del verificador: debe fallar ante código peligroso y pasar ante código limpio.
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { test } from 'node:test'

const VERIFICADOR = resolve('scripts/verificar_seguridad.mjs')
const HTML_LIMPIO = '<!doctype html><html><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>'

function verificar(archivos, html = HTML_LIMPIO) {
  const raiz = mkdtempSync(join(tmpdir(), 'fpa-seg-'))
  try {
    mkdirSync(join(raiz, 'src', 'util'), { recursive: true })
    writeFileSync(join(raiz, 'index.html'), html)
    for (const [ruta, contenido] of Object.entries(archivos)) {
      writeFileSync(join(raiz, 'src', ruta), contenido)
    }
    const r = spawnSync(process.execPath, [VERIFICADOR], { cwd: raiz, encoding: 'utf8' })
    return { codigo: r.status, salida: r.stdout + r.stderr }
  } finally {
    rmSync(raiz, { recursive: true, force: true })
  }
}

test('código limpio pasa', () => {
  const r = verificar({ 'App.tsx': 'export const a = 1\n' })
  assert.equal(r.codigo, 0, r.salida)
})

for (const [nombre, codigo] of [
  ['dangerouslySetInnerHTML', 'const x = <div dangerouslySetInnerHTML={{ __html: h }} />'],
  ['innerHTML', 'el.innerHTML = texto'],
  ['eval', 'eval(texto)'],
  ['new Function', 'const f = new Function("return 1")'],
  ['localStorage', 'localStorage.setItem("a", "b")'],
  ['sessionStorage fuera de la lista blanca', 'sessionStorage.setItem("a", "b")'],
  ['document.cookie', 'document.cookie = "a=b"'],
  ['estilo en línea', 'const x = <p style={{ color: "red" }} />'],
  // oxlint-disable-next-line no-script-url -- es justo el patrón que el verificador debe detectar
  ['javascript:', 'const u = "javascript:alert(1)"'],
]) {
  test(`falla ante ${nombre}`, () => {
    const r = verificar({ 'App.tsx': `${codigo}\n` })
    assert.equal(r.codigo, 1, r.salida)
    assert.match(r.salida, /HALLAZGOS/)
  })
}

test('una credencial en el almacenamiento permitido también falla', () => {
  const r = verificar({
    'util/preferencias.ts': 'sessionStorage.setItem("access_token", t)\n',
  })
  assert.equal(r.codigo, 1, r.salida)
  assert.match(r.salida, /credencial/)
})

test('el almacenamiento permitido sin credenciales pasa', () => {
  const r = verificar({ 'util/preferencias.ts': 'sessionStorage.getItem("fpa_usuario_dev")\n' })
  assert.equal(r.codigo, 0, r.salida)
})

test('un comentario que menciona lo prohibido no cuenta', () => {
  const r = verificar({ 'App.tsx': '// no usar eval() ni localStorage\nexport const a = 1\n' })
  assert.equal(r.codigo, 0, r.salida)
})

test('scripts o estilos en línea en index.html fallan', () => {
  assert.equal(verificar({}, '<html><script>alert(1)</script></html>').codigo, 1)
  assert.equal(verificar({}, '<html><style>p{}</style></html>').codigo, 1)
})
