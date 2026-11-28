// Maqueta 3D con MapLibre GL JS, la única biblioteca del front (ADR-001). Se importa solo
// cuando se pide, y dibuja el mismo esquema que la vista isométrica: volúmenes extruidos
// sobre un plano, sin mapa base ni texto dentro del lienzo.

const VENDOR = "../vendor/maplibre-gl-6.20.0/";
let modulo = null;

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

// Metros locales a longitud y latitud alrededor del origen del esquema.
function aLonLat(esquema, x, y) {
  const lat0 = esquema.latitud;
  return [esquema.longitud + x / (111320 * Math.cos(lat0 * Math.PI / 180)), lat0 + y / 110540];
}
function poligono(esquema, x0, y0, x1, y1, props) {
  const anillo = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]].map(([x, y]) => aLonLat(esquema, x, y));
  return { type: "Feature", properties: props, geometry: { type: "Polygon", coordinates: [anillo] } };
}
function octogono(esquema, cx, cy, r, props) {
  const anillo = [];
  for (let i = 0; i <= 8; i++) {
    const a = (i % 8) * Math.PI / 4;
    anillo.push(aLonLat(esquema, cx + r * Math.cos(a), cy + r * Math.sin(a)));
  }
  return { type: "Feature", properties: props, geometry: { type: "Polygon", coordinates: [anillo] } };
}

function datos(esquema) {
  const css = getComputedStyle(document.documentElement);
  const c = (v) => css.getPropertyValue(v).trim();
  const T = esquema.terreno;
  const suelo = [poligono(esquema, T.x0, T.y0, T.x1, T.y1, { color: c("--suelo") })];
  for (const s of esquema.superficies) suelo.push(poligono(esquema, s.x0, s.y0, s.x1, s.y1, { color: c(`--${s.rol}`) }));
  const vol = [];
  for (const v of esquema.volumenes) {
    vol.push(poligono(esquema, v.x0, v.y0, v.x1, v.y1, { base: 0, altura: v.altura, color: c("--muro-claro") }));
    const a = v.alero;
    vol.push(poligono(esquema, v.x0 - a, v.y0 - a, v.x1 + a, v.y1 + a,
      { base: v.altura, altura: v.altura + 0.25, color: c(v.techo === "losa" ? "--techo" : "--techo-lamina") }));
  }
  for (const k of esquema.cubiertas) {
    for (const [x, y] of [[k.x0, k.y0], [k.x1, k.y0], [k.x0, k.y1], [k.x1, k.y1]]) {
      vol.push(poligono(esquema, x - 0.15, y - 0.15, x + 0.15, y + 0.15, { base: 0, altura: k.altura, color: c("--muro-oscuro") }));
    }
    vol.push(poligono(esquema, k.x0, k.y0, k.x1, k.y1, { base: k.altura, altura: k.altura + 0.25, color: c("--techo-lamina") }));
  }
  for (const t of esquema.arboles) {
    vol.push(octogono(esquema, t.x, t.y, 0.3, { base: 0, altura: t.altura - t.radio, color: c("--tronco") }));
    vol.push(octogono(esquema, t.x, t.y, t.radio, { base: t.altura - t.radio * 1.4, altura: t.altura, color: c("--copa") }));
  }
  return {
    fondo: c("--fondo-escena"),
    suelo: { type: "FeatureCollection", features: suelo },
    volumenes: { type: "FeatureCollection", features: vol },
  };
}

function estilo(esquema, sol) {
  const d = datos(esquema);
  return {
    version: 8,
    sources: {
      suelo: { type: "geojson", data: d.suelo },
      volumenes: {
        type: "geojson",
        data: d.volumenes,
        attribution: "Esquema de volúmenes de una escuela tipo, no la planta de una escuela",
      },
    },
    light: {
      anchor: "map",
      position: [1.4, sol.azimut, Math.min(88, Math.max(10, 90 - sol.elevacion))],
      intensity: 0.45,
    },
    layers: [
      { id: "fondo", type: "background", paint: { "background-color": d.fondo } },
      { id: "suelo", type: "fill", source: "suelo", paint: { "fill-color": ["get", "color"] } },
      {
        id: "volumenes",
        type: "fill-extrusion",
        source: "volumenes",
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

export class Maqueta3D {
  constructor(contenedor, esquema) {
    this.contenedor = contenedor;
    this.esquema = esquema;
    this.mapa = null;
  }

  async abrir(sol) {
    if (!webgl2()) {
      throw new Error("Este equipo no tiene WebGL2, que la maqueta 3D necesita. La vista esquemática y la ficha siguen disponibles.");
    }
    cargarCss();
    modulo ??= await import(VENDOR + "maplibre-gl.mjs");
    this.mapa = new modulo.Map({
      container: this.contenedor,
      style: estilo(this.esquema, sol),
      center: aLonLat(this.esquema, -2, 0),
      zoom: 18.9,
      pitch: 58,
      bearing: 45,
      maxPitch: 75,
      attributionControl: { compact: true },
    });
    this.mapa.addControl(new modulo.NavigationControl({ visualizePitch: true }), "bottom-right");
    await new Promise((ok) => this.mapa.once("load", ok));
  }

  actualizar(sol) {
    if (!this.mapa) return;
    this.mapa.setStyle(estilo(this.esquema, sol));
  }

  cerrar() {
    this.mapa?.remove();
    this.mapa = null;
  }
}
