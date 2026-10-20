import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/inter/index.css'
import './index.css'
import Raiz from './Raiz.tsx'
import { aplicarTema } from './util/aplicarTema'
import { leerTema } from './util/preferencias'

// Antes de pintar: evita el parpadeo del tema al cargar
aplicarTema(leerTema())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Raiz />
  </StrictMode>,
)
