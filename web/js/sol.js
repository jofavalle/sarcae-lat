// La posición del sol, como función pura: sin DOM, sin estado y sin datos de ninguna escuela.
// Son las ecuaciones aproximadas de la NOAA (General Solar Position Calculations), las mismas
// de web/direcciones/maqueta.js (PR #35). La importa la maqueta (#65). No es una cifra del
// clima: es geometría, y por eso se calcula en el navegador (ADR-001).

const RAD = Math.PI / 180;

/**
 * Altura y acimut del sol, en grados.
 *
 * @param {object} p
 * @param {number} p.lat   latitud, en grados (norte positivo)
 * @param {number} p.lon   longitud, en grados (este positivo)
 * @param {number} p.huso  huso horario fijo, en horas respecto a UTC (−6 en El Salvador)
 * @param {number} p.dia   día del año, de 1 a 366
 * @param {number} p.hora  hora local, en horas con decimales (10.5 son las 10:30)
 * @returns {{altura: number, acimut: number}} la altura sobre el horizonte, de −90 a 90, y el
 *   acimut desde el norte en el sentido de las agujas del reloj, de 0 a 360
 */
export function posicionSol({ lat, lon, huso, dia, hora }) {
  const g = (2 * Math.PI / 365) * (dia - 1 + (hora - 12) / 24);
  const ecTiempo = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g)
    - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
  const decl = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g)
    - 0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g)
    - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
  const tiempoSolar = hora * 60 + ecTiempo + 4 * lon - 60 * huso;
  const ha = (tiempoSolar / 4 - 180) * RAD;
  const phi = lat * RAD;
  const cosZ = Math.sin(phi) * Math.sin(decl) + Math.cos(phi) * Math.cos(decl) * Math.cos(ha);
  const altura = 90 - Math.acos(Math.min(1, Math.max(-1, cosZ))) / RAD;
  const acimut = (Math.atan2(Math.sin(ha), Math.cos(ha) * Math.sin(phi) - Math.tan(decl) * Math.cos(phi)) / RAD + 540) % 360;
  return { altura, acimut };
}
