// Mapa 2D y maqueta 3D con MapLibre GL JS, la única biblioteca del front (ADR-001). Se
// importa solo cuando se pide. Las dos vistas comparten un mismo mapa:
// - 2D: la escuela y su entorno desde arriba, con las sombras del sol, los cuadros de calor de
//   100 m y el recorrido del agua;
// - 3D: los volúmenes del esquema extruidos, con la luz del sol de la hora elegida. Arrastrar
//   con el botón principal gira e inclina la maqueta alrededor de su centro.
// Sin mapa base ni texto dentro del lienzo: la leyenda va en HTML.

const VENDOR = "../vendor/maplibre-gl-6.20.0/";
let modulo = null;

// Clases de la temperatura de superficie del mapa 2D, en °C. La leyenda sale de aquí.
export const CLASES_CALOR = [
  { hasta: 40, texto: "menos de 40 °C", peso: 0.12 },
  { hasta: 44, texto: "de 40 a 43 °C", peso: 0.32 },
  { hasta: 47, texto: "de 44 a 46 °C", peso: 0.52 },
  { hasta: 50, texto: "de 47 a 49 °C", peso: 0.74 },
  { hasta: Infinity, texto: "50 °C o más", peso: 0.95 },
];

// Lo que enseña cada vista al abrirse, en metros alrededor del centro del esquema.
// En 2D, la escuela llena la vista; con la capa de calor se abre para ver los cuadros vecinos.
const ENCUADRE_2D = [-46, -31, 46, 31];
const ENCUADRE_2D_CALOR = [-170, -120, 170, 120];
const RUMBO_3D = 45;
const INCLINACION_3D = 55;

function cargarCss() {
  if (document.querySelector("link[data-maplibre]")) return;
  const l = document.createElement("link");
  l.rel = "stylesheet";
  l.href = VENDOR + "maplibre-gl.css";
  l.dataset.maplibre = "";
  document.head.appendChild(l);
}

function webgl2() {
  try {
    return !!document.createElement("canvas").getContext("webgl2");
  } catch {
    return false;
  }
}

const reducido = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

// MapLibre no entiende color-mix(): las mezclas se calculan aquí, sobre los hex de los tokens.
function mezclar(a, b, peso) {
  const n = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [x, y] = [n(a), n(b)];
  return "#" + x.map((v, i) => Math.round(v * peso + y[i] * (1 - peso)).toString(16).padStart(2, "0")).join("");
}

// Metros locales a longitud y latitud alrededor del origen del esquema.
function aLonLat(esquema, x, y) {
  const lat0 = esquema.latitud;
  return [esquema.longitud + x / (111320 * Math.cos(lat0 * Math.PI / 180)), lat0 + y / 110540];
}
function anillo(esquema, puntos) {
  const a = puntos.map(([x, y]) => aLonLat(esquema, x, y));
  a.push(a[0]);
  return a;
}
function poligono(esquema, x0, y0, x1, y1, props) {
  return { type: "Feature", properties: props, geometry: { type: "Polygon", coordinates: [anillo(esquema, [[x0, y0], [x1, y0], [x1, y1], [x0, y1]])] } };
}
function circulo(esquema, cx, cy, r, props, lados = 12) {
  const pts = Array.from({ length: lados }, (_, i) => {
    const a = (i / lados) * 2 * Math.PI;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  });
  return { type: "Feature", properties: props, geometry: { type: "Polygon", coordinates: [anillo(esquema, pts)] } };
}
const coleccion = (features) => ({ type: "FeatureCollection", features });

function limites(esquema, [x0, y0, x1, y1]) {
  return [aLonLat(esquema, x0, y0), aLonLat(esquema, x1, y1)];
}

function datosSombras(esquema, s) {
  if (!s) return coleccion([]);
  return coleccion([
    ...s.poligonos.map((q) => ({ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [anillo(esquema, q)] } })),
    ...s.circulos.map((c) => circulo(esquema, c.x, c.y, c.r, {})),
  ]);
}

function datos(esquema) {
  const css = getComputedStyle(document.documentElement);
  const c = (v) => css.getPropertyValue(v).trim();
  const T = esquema.terreno;

  const suelo = [poligono(esquema, T.x0, T.y0, T.x1, T.y1, { color: c("--suelo") })];
  for (const s of esquema.superficies) suelo.push(poligono(esquema, s.x0, s.y0, s.x1, s.y1, { color: c(`--${s.rol}`) }));

  const vol = [];
  const planta = [];
  for (const v of esquema.volumenes) {
    vol.push(poligono(esquema, v.x0, v.y0, v.x1, v.y1, { base: 0, altura: v.altura, color: c("--muro-claro") }));
    const a = v.alero;
    const techo = c(v.techo === "losa" ? "--techo" : "--techo-lamina");
    vol.push(poligono(esquema, v.x0 - a, v.y0 - a, v.x1 + a, v.y1 + a, { base: v.altura, altura: v.altura + 0.25, color: techo }));
    planta.push(poligono(esquema, v.x0 - a, v.y0 - a, v.x1 + a, v.y1 + a, { color: techo }));
  }
  for (const k of esquema.cubiertas) {
    for (const [x, y] of [[k.x0, k.y0], [k.x1, k.y0], [k.x0, k.y1], [k.x1, k.y1]]) {
      vol.push(poligono(esquema, x - 0.15, y - 0.15, x + 0.15, y + 0.15, { base: 0, altura: k.altura, color: c("--muro-oscuro") }));
    }
    vol.push(poligono(esquema, k.x0, k.y0, k.x1, k.y1, { base: k.altura, altura: k.altura + 0.25, color: c("--techo-lamina") }));
    planta.push(poligono(esquema, k.x0, k.y0, k.x1, k.y1, { color: c("--techo-lamina") }));
  }
  for (const t of esquema.arboles) {
    vol.push(circulo(esquema, t.x, t.y, 0.3, { base: 0, altura: t.altura - t.radio, color: c("--tronco") }, 6));
    vol.push(circulo(esquema, t.x, t.y, t.radio, { base: t.altura - t.radio * 1.4, altura: t.altura, color: c("--copa") }, 10));
    planta.push(circulo(esquema, t.x, t.y, t.radio, { color: c("--copa") }));
  }

  const E = esquema.entorno_calor;
  const calor = c("--calor");
  const fondo = c("--fondo-escena");
  const cuadros = [];
  E.valores.forEach((fila, i) => fila.forEach((t, j) => {
    const x0 = E.x0 + j * E.lado_m;
    const y0 = E.y0 + i * E.lado_m;
    const clase = CLASES_CALOR.find((k) => t < k.hasta);
    cuadros.push(poligono(esquema, x0, y0, x0 + E.lado_m, y0 + E.lado_m, { t, color: mezclar(calor, fondo, clase.peso) }));
  }));
  const cl = esquema.calor_landsat.lado_m / 2;

  const agua = esquema.agua.lineas.map((l) => ({
    type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: l.map(([x, y]) => aLonLat(esquema, x, y)) },
  }));

  return {
    colores: {
      fondo,
      texto: c("--texto"),
      agua: c("--agua"),
      sombra: c("--sombra-mapa"),
      sombraOpacidad: Number(c("--sombra-mapa-opacidad")) || 0.4,
    },
    suelo: coleccion(suelo),
    volumenes: coleccion(vol),
    planta: coleccion(planta),
    cuadros: coleccion(cuadros),
    cuadroEscuela: coleccion([poligono(esquema, -cl, -cl, cl, cl, {})]),
    agua: coleccion(agua),
    puntoBajo: coleccion([circulo(esquema, ...esquema.agua.punto_bajo, 1.6, {})]),
  };
}

const ATRIBUCION = "Esquema de una escuela tipo y cifras de ejemplo, no datos de la escuela";

function luz(sol) {
  return {
    anchor: "map",
    position: [1.4, sol.azimut, Math.min(88, Math.max(10, 90 - sol.elevacion))],
    intensity: 0.45,
  };
}

function estilo(esquema, sol, vista, capa, sombras) {
  const d = datos(esquema);
  const ver = (si) => ({ visibility: si ? "visible" : "none" });
  const en2d = vista === "2d";
  const calor2d = en2d && capa === "calor";
  return {
    version: 8,
    sources: {
      cuadros: { type: "geojson", data: d.cuadros, attribution: ATRIBUCION },
      cuadroEscuela: { type: "geojson", data: d.cuadroEscuela },
      suelo: { type: "geojson", data: d.suelo },
      sombras: { type: "geojson", data: datosSombras(esquema, sombras) },
      planta: { type: "geojson", data: d.planta },
      volumenes: { type: "geojson", data: d.volumenes },
      agua: { type: "geojson", data: d.agua },
      puntoBajo: { type: "geojson", data: d.puntoBajo },
    },
    light: luz(sol),
    layers: [
      { id: "fondo", type: "background", paint: { "background-color": d.colores.fondo, "background-opacity": 0 } },
      { id: "cuadros", type: "fill", source: "cuadros", layout: ver(calor2d), paint: { "fill-color": ["get", "color"] } },
      { id: "cuadros-borde", type: "line", source: "cuadros", layout: ver(calor2d), paint: { "line-color": d.colores.fondo, "line-width": 1.5 } },
      { id: "suelo", type: "fill", source: "suelo", paint: { "fill-color": ["get", "color"], "fill-opacity": calor2d ? 0.45 : 1 } },
      { id: "sombras", type: "fill", source: "sombras", layout: ver(en2d && capa === "sombra"), paint: { "fill-color": d.colores.sombra, "fill-opacity": d.colores.sombraOpacidad } },
      { id: "planta", type: "fill", source: "planta", layout: ver(en2d), paint: { "fill-color": ["get", "color"], "fill-outline-color": d.colores.texto } },
      { id: "cuadro-escuela", type: "line", source: "cuadroEscuela", layout: ver(calor2d), paint: { "line-color": d.colores.texto, "line-width": 2, "line-dasharray": [2, 1.5] } },
      { id: "agua", type: "line", source: "agua", layout: { ...ver(capa === "agua"), "line-cap": "round" }, paint: { "line-color": d.colores.agua, "line-width": 3, "line-dasharray": [1.5, 1] } },
      { id: "punto-bajo", type: "fill", source: "puntoBajo", layout: ver(capa === "agua"), paint: { "fill-color": d.colores.agua, "fill-opacity": 0.6 } },
      {
        id: "volumenes",
        type: "fill-extrusion",
        source: "volumenes",
        layout: ver(!en2d),
        paint: {
          "fill-extrusion-color": ["get", "color"],
          "fill-extrusion-base": ["get", "base"],
          "fill-extrusion-height": ["get", "altura"],
          "fill-extrusion-vertical-gradient": false,
        },
      },
    ],
  };
}

export class Mapa {
  constructor(contenedor, esquema) {
    this.contenedor = contenedor;
    this.esquema = esquema;
    this.mapa = null;
    this.vista = null;
    this.clave = "";
    this.arrastre = null;
  }

  async abrir(vista, sol, capa, sombras) {
    if (!webgl2()) {
      throw new Error("Este equipo no tiene WebGL2, que el mapa y la maqueta 3D necesitan. La maqueta esquemática y la ficha siguen disponibles.");
    }
    cargarCss();
    modulo ??= await import(VENDOR + "maplibre-gl.mjs");
    this.vista = vista;
    this.capa = capa;
    this.clave = this.claveDe(vista, capa);
    this.mapa = new modulo.Map({
      container: this.contenedor,
      style: estilo(this.esquema, sol, vista, capa, sombras),
      bounds: limites(this.esquema, ENCUADRE_2D),
      maxPitch: 80,
      attributionControl: { compact: true },
    });
    this.mapa.addControl(new modulo.NavigationControl({ visualizePitch: true }), "top-right");
    this.mapa.addControl(new modulo.ScaleControl({ unit: "metric" }), "bottom-left");
    this.orbita();
    await new Promise((ok) => this.mapa.once("load", ok));
    this.interaccion();
    this.encuadrar(false);
  }

  claveDe(vista, capa) {
    return `${vista}|${capa}|${document.documentElement.dataset.direccion}`;
  }

  // En 3D, arrastrar con el botón principal gira (horizontal) e inclina (vertical) la maqueta
  // alrededor de su centro, sin desplazarla. En 2D, arrastrar desplaza el mapa y no gira.
  orbita() {
    const lienzo = this.mapa.getCanvasContainer();
    lienzo.addEventListener("pointerdown", (e) => {
      if (this.vista !== "3d" || e.button !== 0) return;
      this.arrastre = { x: e.clientX, y: e.clientY, rumbo: this.mapa.getBearing(), inclinacion: this.mapa.getPitch() };
      lienzo.setPointerCapture(e.pointerId);
    });
    lienzo.addEventListener("pointermove", (e) => {
      if (!this.arrastre) return;
      const a = this.arrastre;
      this.mapa.jumpTo({
        bearing: a.rumbo - (e.clientX - a.x) * 0.4,
        pitch: Math.min(80, Math.max(0, a.inclinacion - (e.clientY - a.y) * 0.3)),
      });
    });
    const soltar = (e) => {
      if (!this.arrastre) return;
      this.arrastre = null;
      if (lienzo.hasPointerCapture(e.pointerId)) lienzo.releasePointerCapture(e.pointerId);
    };
    lienzo.addEventListener("pointerup", soltar);
    lienzo.addEventListener("pointercancel", soltar);
  }

  interaccion() {
    const m = this.mapa;
    if (this.vista === "3d") {
      m.dragPan.disable();
      m.dragRotate.enable();
      m.touchZoomRotate.enableRotation();
      m.keyboard.enableRotation();
    } else {
      m.dragPan.enable();
      m.dragRotate.disable();
      m.touchZoomRotate.disableRotation();
      m.keyboard.disableRotation();
    }
  }

  encuadrar(animar = true) {
    const m = this.mapa;
    let opciones;
    if (this.vista === "2d") {
      const caja = this.capa === "calor" ? ENCUADRE_2D_CALOR : ENCUADRE_2D;
      opciones = { ...m.cameraForBounds(limites(this.esquema, caja), { padding: 24 }), bearing: 0, pitch: 0 };
    } else {
      const T = this.esquema.terreno;
      const cam = m.cameraForBounds(limites(this.esquema, [T.x0, T.y0, T.x1, T.y1]), { padding: 40, bearing: RUMBO_3D });
      opciones = { center: cam.center, zoom: cam.zoom + 0.6, bearing: RUMBO_3D, pitch: INCLINACION_3D };
    }
    if (animar && !reducido()) m.easeTo({ ...opciones, duration: 600 });
    else m.jumpTo(opciones);
  }

  girar(grados) {
    if (!this.mapa) return;
    this.mapa.easeTo({ bearing: this.mapa.getBearing() + grados, duration: reducido() ? 0 : 400 });
  }

  actualizar(vista, sol, capa, sombras) {
    if (!this.mapa) return;
    const clave = this.claveDe(vista, capa);
    const cambiaVista = vista !== this.vista;
    const cambiaEncuadre = vista === "2d" && (capa === "calor") !== (this.capa === "calor");
    this.vista = vista;
    this.capa = capa;
    if (clave === this.clave && this.mapa.isStyleLoaded()) {
      // Solo cambió la hora o el día: se actualizan la luz y las sombras sin rehacer el estilo.
      this.mapa.getSource("sombras")?.setData(datosSombras(this.esquema, sombras));
      this.mapa.setLight(luz(sol));
      return;
    }
    this.clave = clave;
    this.mapa.setStyle(estilo(this.esquema, sol, vista, capa, sombras));
    if (cambiaVista) this.interaccion();
    if (cambiaVista || cambiaEncuadre) this.encuadrar();
  }

  cerrar() {
    this.mapa?.remove();
    this.mapa = null;
    this.vista = null;
    this.clave = "";
  }
}
