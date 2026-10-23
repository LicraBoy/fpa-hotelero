// `plotly.js-basic-dist-min` no trae tipos propios (es el build minificado de Plotly, sin `.d.ts`).
// Se usa como el `Plotly: unknown` que pide `react-plotly.js/factory`'s `createPlotlyComponent`.
declare module 'plotly.js-basic-dist-min' {
  const Plotly: unknown
  export default Plotly
}
