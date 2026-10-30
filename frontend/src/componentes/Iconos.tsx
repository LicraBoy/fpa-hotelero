// Iconos de línea propios (SVG en el código): sin dependencias y compatibles con la CSP estricta.
// Son decorativos (`aria-hidden`): el texto que los acompaña es lo que lee un lector de pantalla.

import type { NombreIcono } from './nombreIcono.ts'

export type { NombreIcono }

const TRAZOS: Record<NombreIcono, string[]> = {
  informe: ['M5 3h10l4 4v14H5z', 'M15 3v4h4', 'M8 17v-4', 'M12 17v-7', 'M16 17v-2'],
  presupuesto: ['M3 7h18v12H3z', 'M3 7l2-3h14l2 3', 'M16 13h2', 'M7 13h4'],
  subir: ['M12 16V4', 'M7 9l5-5 5 5', 'M4 16v4h16v-4'],
  catalogo: ['M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z', 'M5 17a3 3 0 0 1 3-3h11', 'M9 8h6'],
  saldos: ['M4 20h16', 'M6 20V10', 'M11 20V5', 'M16 20v-8', 'M21 20V8'],
  auditoria: ['M12 3l8 3v6c0 4.5-3.4 7.8-8 9-4.6-1.2-8-4.5-8-9V6z', 'M9 12l2.2 2.2L15.5 10'],
  buscar: ['M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15z', 'M16 16l5 5'],
  exportar: ['M12 4v12', 'M7 11l5 5 5-5', 'M4 20h16'],
  sol: ['M12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8z', 'M12 2v2', 'M12 20v2', 'M2 12h2', 'M20 12h2', 'M5 5l1.5 1.5', 'M17.5 17.5L19 19', 'M5 19l1.5-1.5', 'M17.5 6.5L19 5'],
  luna: ['M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z'],
  chevron: ['M9 6l6 6-6 6'],
  alerta: ['M12 3l10 18H2z', 'M12 10v5', 'M12 18h.01'],
  hotel: ['M4 21V5l8-2v18', 'M12 8h8v13', 'M7 9h2', 'M7 13h2', 'M7 17h2', 'M15 12h2', 'M15 16h2'],
  menu: ['M4 7h16', 'M4 12h16', 'M4 17h16'],
  expandir: ['M7 4l5 5 5-5', 'M7 14l5 5 5-5'],
  plegar: ['M7 10l5-5 5 5', 'M7 20l5-5 5 5'],
  densidad: ['M4 6h16', 'M4 10h16', 'M4 14h16', 'M4 18h16'],
  imprimir: ['M7 9V3h10v6', 'M7 17H4v-7h16v7h-3', 'M7 14h10v7H7z'],
  cerrar: ['M6 6l12 12', 'M18 6L6 18'],
  tendenciaAbajo: ['M3 7l6 6 4-4 8 8', 'M15 17h6v-6'],
  tendenciaArriba: ['M3 17l6-6 4 4 8-8', 'M15 7h6v6'],
  objetivo: ['M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18z', 'M12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8z', 'M12 12h.01'],
  calendario: ['M4 6h16v14H4z', 'M4 10h16', 'M8 3v4', 'M16 3v4'],
  comentario: ['M4 5h16v11H9l-5 4z', 'M8 9h8', 'M8 12h5'],
  usuario: ['M12 12a4 4 0 1 1 0-8 4 4 0 0 1 0 8z', 'M4 21a8 8 0 0 1 16 0'],
  info: ['M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18z', 'M12 11v6', 'M12 7.5h.01'],
  check: ['M5 12l5 5 9-10'],
  lapiz: ['M4 20l1-4L16 5l3 3L8 19z', 'M14 7l3 3'],
  embudo: ['M4 5h16l-6 7v6l-4 2v-8z'],
  tabla: ['M4 5h16v14H4z', 'M4 10h16', 'M4 15h16', 'M10 5v14'],
  baseDatos: ['M5 6c0-1.7 3.1-3 7-3s7 1.3 7 3-3.1 3-7 3-7-1.3-7-3z', 'M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6', 'M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6'],
  flechaArriba: ['M12 19V5', 'M6 11l6-6 6 6'],
  mas: ['M5 12h.01', 'M12 12h.01', 'M19 12h.01'],
  ampliar: ['M4 9V4h5', 'M20 9V4h-5', 'M4 15v5h5', 'M20 15v5h-5'],
  cuentas: ['M4 7h16', 'M4 12h16', 'M4 17h10', 'M18 16v4', 'M16 18h4'],
  volver: ['M15 6l-6 6 6 6'],
  guardar: ['M5 4h11l3 3v13H5z', 'M8 4v5h7V4', 'M8 20v-6h8v6'],
}

export function Icono({ nombre, tamano = 18 }: { nombre: NombreIcono; tamano?: number }) {
  return (
    <svg
      className="icono"
      width={tamano}
      height={tamano}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {TRAZOS[nombre].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  )
}

/** Marca del producto: un anillo con punto central (identidad propia, sin texto). */
export function Logo({ tamano = 34 }: { tamano?: number }) {
  return (
    <svg
      className="logo"
      width={tamano}
      height={tamano}
      viewBox="0 0 40 40"
      aria-hidden="true"
      focusable="false"
    >
      <rect width="40" height="40" rx="11" className="logo-fondo" />
      <circle cx="20" cy="20" r="9" fill="none" className="logo-trazo" strokeWidth="3.2" />
      <circle cx="20" cy="20" r="3.2" className="logo-punto" />
    </svg>
  )
}
