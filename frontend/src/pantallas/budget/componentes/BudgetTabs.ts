import type { NombreIcono } from '../../../componentes/nombreIcono'

export type PestanaBudget = 'resumen' | 'captura' | 'versiones'

/** Sub-navegación de Budget Studio. Se dibuja en el sidebar global (App.tsx), no dentro de la pantalla. */
export const PESTANAS_BUDGET: { id: PestanaBudget; etiqueta: string; icono: NombreIcono }[] = [
  { id: 'resumen', etiqueta: 'Resumen', icono: 'informe' },
  { id: 'captura', etiqueta: 'Captura', icono: 'presupuesto' },
  { id: 'versiones', etiqueta: 'Versiones', icono: 'auditoria' },
]
