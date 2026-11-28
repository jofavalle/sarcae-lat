// La maqueta genérica (orden #65): una escuela tipo en SVG isométrico, con el sol y las
// sombras del día y la hora elegidos en la latitud de la escuela seleccionada, y la tabla de
// la sombra del patio. Es la escena del prototipo de web/direcciones/maqueta.js (PR #35),
// portada a este módulo. Nunca representa una escuela concreta (docs/PLAN.md, sección 7): los
// volúmenes son los de comun/maqueta-generica.json, y de la escuela elegida solo se toma el sol.
//
// Punto de montaje: #maqueta, dentro de .lienzo. Activa los mandos del día y de la capa, que
// app.js ya enlaza al estado; la vista se queda como está, porque es del mapa (#66). Llena
// también la altura del sol y el patio a la sombra de la barra, y la frase del sol bajo la
// hora. Su CSS es estilo/maqueta.css.
//
// Las sombras se calculan aquí y no en Python: son geometría interactiva, no una cifra del
// clima (ADR-001). La posición del sol sale de ./sol.js.

import { posicionSol } from "./sol.js";

const RAD = Math.PI / 180;
const SVG = "http://www.w3.org/2000/svg";
const GROSOR_TECHO = 0.25;
// Con el sol a menos de 2° no se dibujan sombras: serían más largas que el terreno.
const SOL_MINIMO = 2;
const HORAS_TABLA = [7, 10, 12, 15];
const ROTULO = "Maqueta genérica: no es la escuela";
// La pregunta de la #23, literal.
const PREGUNTA_ALEROS = "¿Qué ventanas reciben sol directo por la tarde y qué sombra les dan los aleros o parteluces?";
// El punto del ejemplo (docs/contrato-datos.md), si la escuela elegida no trae el suyo.
const PUNTO_EJEMPLO = { lat: 13.7, lon: -89.2, huso: -6 };

const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
  "septiembre", "octubre", "noviembre", "diciembre"];
const DIAS_MES = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const RUMBOS = ["el norte", "el noreste", "el este", "el sureste", "el sur", "el suroeste", "el oeste", "el noroeste"];

// Textos

export function fechaTexto(dia) {
  let d = dia;
  for (let m = 0; m < 12; m++) {
    if (d <= DIAS_MES[m]) return `${d} de ${MESES[m]}`;
    d -= DIAS_MES[m];
  }
  return "31 de diciembre";
}

function horaTexto(h) {
  const hh = Math.floor(h);
  const mm = Math.round((h - hh) * 60);
  return `${hh}:${String(mm).padStart(2, "0")}`;
}

const coma = (n) => String(n).replace(".", ",");
const rumbo = (acimut) => RUMBOS[Math.round(acimut / 45) % 8];

// Geometría, en metros: x hacia el este, y hacia el norte.

function rect(x0, y0, x1, y1, z) {
  return [[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]];
}

// Envolvente convexa (cadena monótona de Andrew).
function envolvente(pts) {
  const s = [...pts].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cruz = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const inf = [];
  for (const q of s) {
    while (inf.length >= 2 && cruz(inf[inf.length - 2], inf[inf.length - 1], q) <= 0) inf.pop();
    inf.push(q);
  }
  const sup = [];
  for (const q of s.reverse()) {
    while (sup.length >= 2 && cruz(sup[sup.length - 2], sup[sup.length - 1], q) <= 0) sup.pop();
    sup.push(q);
  }
  return inf.slice(0, -1).concat(sup.slice(0, -1));
}

function dentroConvexo(poli, x, y) {
  let signo = 0;
  for (let i = 0; i < poli.length; i++) {
    const [ax, ay] = poli[i];
    const [bx, by] = poli[(i + 1) % poli.length];
    const c = (bx - ax) * (y - ay) - (by - ay) * (x - ax);
    if (c !== 0) {
      if (signo === 0) signo = Math.sign(c);
      else if (Math.sign(c) !== signo) return false;
    }
  }
  return true;
}

/**
 * Las sombras en el suelo, en metros: polígonos convexos para los volúmenes con su alero y
 * para las cubiertas, y círculos para las copas de los árboles. Con el sol en el cenit, cada
 * sombra es la planta del volumen con su alero. El acimut se mide desde el norte en el
 * sentido de las agujas del reloj, así que la sombra va hacia el lado contrario del sol.
 */
export function sombras(esquema, sol) {
  if (sol.altura <= SOL_MINIMO) return { poligonos: [], circulos: [] };
  const k = 1 / Math.tan(sol.altura * RAD);
  const dx = -Math.sin(sol.acimut * RAD) * k;
  const dy = -Math.cos(sol.acimut * RAD) * k;
  const poligonos = [];
  for (const v of esquema.volumenes) {
    const h = v.altura + GROSOR_TECHO;
    const a = v.alero;
    const base = rect(v.x0, v.y0, v.x1, v.y1, 0).map(([x, y]) => [x, y]);
    const techo = rect(v.x0 - a, v.y0 - a, v.x1 + a, v.y1 + a, 0).map(([x, y]) => [x + dx * h, y + dy * h]);
    poligonos.push(envolvente(base.concat(techo)));
  }
  for (const c of esquema.cubiertas) {
    const h = c.altura + GROSOR_TECHO;
    poligonos.push(rect(c.x0, c.y0, c.x1, c.y1, 0).map(([x, y]) => [x + dx * h, y + dy * h]));
  }
  const circulos = esquema.arboles.map((t) => ({
    x: t.x + dx * (t.altura - t.radio * 0.6),
    y: t.y + dy * (t.altura - t.radio * 0.6),
    r: t.radio,
  }));
  return { poligonos, circulos };
}

export function enSombra(s, x, y) {
  return s.poligonos.some((q) => dentroConvexo(q, x, y))
    || s.circulos.some((c) => (x - c.x) ** 2 + (y - c.y) ** 2 <= c.r ** 2);
}

/** La parte del patio a la sombra, de 0 a 1: una muestra cada medio metro. */
export function sombraEnPatio(esquema, s) {
  const patio = esquema.superficies.find((x) => x.id === "patio");
  let total = 0;
  let sombra = 0;
  for (let x = patio.x0 + 0.25; x < patio.x1; x += 0.5) {
    for (let y = patio.y0 + 0.25; y < patio.y1; y += 0.5) {
      total++;
      if (enSombra(s, x, y)) sombra++;
    }
  }
  return sombra / total;
}

/** El sol en el lugar de la escuela, y el porcentaje del patio a la sombra, o null sin sol. */
function momento(esquema, punto, dia, hora) {
  const sol = posicionSol({ lat: punto.lat, lon: punto.lon, huso: punto.huso, dia, hora });
  const s = sombras(esquema, sol);
  const patio = sol.altura > SOL_MINIMO ? Math.round(sombraEnPatio(esquema, s) * 100) : null;
  return { sol, s, patio };
}

// El dibujo

// Proyección isométrica vista desde el suroeste: el noreste queda al fondo.
const C30 = Math.cos(30 * RAD);
function p(x, y, z = 0) {
  return [(x - y) * C30, -((x + y) * 0.5 + z)];
}
function puntos(lista) {
  return lista.map(([x, y, z]) => p(x, y, z).map((v) => v.toFixed(2)).join(",")).join(" ");
}

function el(nombre, attrs = {}, padre) {
  const n = document.createElementNS(SVG, nombre);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (padre) padre.appendChild(n);
  return n;
}

function html(nombre, attrs = {}, ...hijos) {
  const n = document.createElement(nombre);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "texto") n.textContent = v;
    else n.setAttribute(k, v);
  }
  n.append(...hijos);
  return n;
}

// Luz difusa de una cara según el sol: 0 de espaldas, 1 de frente.
function luz(normal, sol) {
  if (sol.altura <= 0) return 0.15;
  const ce = Math.cos(sol.altura * RAD);
  const s = [Math.sin(sol.acimut * RAD) * ce, Math.cos(sol.acimut * RAD) * ce, Math.sin(sol.altura * RAD)];
  const d = normal[0] * s[0] + normal[1] * s[1] + normal[2] * s[2];
  return 0.25 + 0.75 * Math.max(0, d);
}
function tono(claro, oscuro, f) {
  return `color-mix(in oklab, var(${claro}) ${Math.round(f * 100)}%, var(${oscuro}))`;
}

function caja(g, x0, y0, x1, y1, z0, z1, sol, rellenoSup) {
  // Caras visibles desde el suroeste: sur, oeste y la de arriba.
  el("polygon", {
    points: puntos([[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]]),
    style: `fill:${tono("--muro-claro", "--muro-oscuro", luz([0, -1, 0], sol))}`,
  }, g);
  el("polygon", {
    points: puntos([[x0, y0, z0], [x0, y1, z0], [x0, y1, z1], [x0, y0, z1]]),
    style: `fill:${tono("--muro-claro", "--muro-oscuro", luz([-1, 0, 0], sol))}`,
  }, g);
  if (rellenoSup) el("polygon", { points: puntos(rect(x0, y0, x1, y1, z1)), style: `fill:${rellenoSup}` }, g);
}

function losa(g, x0, y0, x1, y1, z, material, sol) {
  const z1 = z + GROSOR_TECHO;
  const claro = material === "losa" ? "--techo" : "--techo-lamina";
  const lado = tono(claro, "--techo-lado", 0.35 + 0.4 * luz([0, -1, 0], sol));
  el("polygon", { points: puntos([[x0, y0, z], [x1, y0, z], [x1, y0, z1], [x0, y0, z1]]), style: `fill:${lado}` }, g);
  el("polygon", { points: puntos([[x0, y0, z], [x0, y1, z], [x0, y1, z1], [x0, y0, z1]]), style: `fill:${lado}` }, g);
  el("polygon", {
    points: puntos(rect(x0, y0, x1, y1, z1)),
    style: `fill:${tono(claro, "--techo-lado", 0.45 + 0.55 * luz([0, 0, 1], sol))}`,
  }, g);
}

/** Dibuja la escena en el <svg> dado, sin tocar su <title> ni su <desc>. */
function dibujar(svg, esquema, { sol, s, capa }) {
  for (const n of [...svg.children]) if (n.localName !== "title" && n.localName !== "desc") n.remove();
  const T = esquema.terreno;
  const esp = T.espesor;

  const defs = el("defs", {}, svg);
  const flecha = el("marker", { id: "mq-flecha-agua", viewBox: "0 0 10 10", refX: 6, refY: 5, markerWidth: 5, markerHeight: 5, orient: "auto-start-reverse" }, defs);
  el("path", { d: "M0,0 L10,5 L0,10 z", class: "flecha" }, flecha);
  const recorte = el("clipPath", { id: "mq-recorte-terreno" }, defs);
  el("polygon", { points: puntos(rect(T.x0, T.y0, T.x1, T.y1, 0)) }, recorte);

  // La base, con su espesor, y las superficies del suelo.
  const base = el("g", { class: "base" }, svg);
  el("polygon", { points: puntos([[T.x0, T.y0, -esp], [T.x1, T.y0, -esp], [T.x1, T.y0, 0], [T.x0, T.y0, 0]]), style: "fill:var(--suelo-lado-2)" }, base);
  el("polygon", { points: puntos([[T.x0, T.y0, -esp], [T.x0, T.y1, -esp], [T.x0, T.y1, 0], [T.x0, T.y0, 0]]), style: "fill:var(--suelo-lado)" }, base);
  el("polygon", { points: puntos(rect(T.x0, T.y0, T.x1, T.y1, 0)), style: "fill:var(--suelo)" }, base);
  for (const sup of esquema.superficies) {
    el("polygon", { points: puntos(rect(sup.x0, sup.y0, sup.x1, sup.y1, 0)), style: `fill:var(--${sup.rol})` }, base);
    if (sup.rol === "cancha") {
      const cx = (sup.x0 + sup.x1) / 2;
      el("polygon", { points: puntos(rect(sup.x0 + 1, sup.y0 + 1, sup.x1 - 1, sup.y1 - 1, 0)), class: "cancha-linea" }, base);
      el("polyline", { points: puntos([[cx, sup.y0 + 1, 0], [cx, sup.y1 - 1, 0]]), class: "cancha-linea" }, base);
    }
    // Capa de calor: el suelo del patio y de la cancha se tiñe, y la sombra lo tapa donde
    // cae. Lo teñido es lo que recibe sol directo a esta hora; no es una temperatura.
    if (capa === "calor" && sol.altura > SOL_MINIMO) {
      el("polygon", { points: puntos(rect(sup.x0, sup.y0, sup.x1, sup.y1, 0)), class: "suelo-al-sol" }, base);
    }
  }

  // Las sombras, recortadas al terreno. En la capa de agua no se dibujan, como en el prototipo.
  if (capa !== "agua") {
    const gs = el("g", { class: "sombras", "clip-path": "url(#mq-recorte-terreno)" }, svg);
    for (const q of s.poligonos) el("polygon", { points: puntos(q.map(([x, y]) => [x, y, 0])) }, gs);
    for (const c of s.circulos) {
      const [px, py] = p(c.x, c.y, 0);
      el("ellipse", { cx: px.toFixed(2), cy: py.toFixed(2), rx: (c.r * 1.22).toFixed(2), ry: (c.r * 0.7).toFixed(2) }, gs);
    }
  } else {
    // Capa de agua: canaleta, recorridos y punto bajo, según la pendiente del esquema.
    const ga = el("g", { class: "agua" }, svg);
    el("polyline", { points: puntos(esquema.agua.canaleta.map(([x, y]) => [x, y, 0])), class: "canaleta" }, ga);
    for (const l of esquema.agua.lineas) {
      el("polyline", { points: puntos(l.map(([x, y]) => [x, y, 0])), class: "flujo", "marker-end": "url(#mq-flecha-agua)" }, ga);
    }
    const [bx, by] = p(...esquema.agua.punto_bajo, 0);
    el("ellipse", { cx: bx, cy: by, rx: 2.4, ry: 1.4, class: "punto-bajo" }, ga);
  }

  // Volúmenes, cubiertas y árboles, del fondo hacia delante.
  const objetos = [
    ...esquema.volumenes.map((v) => ({ tipo: "volumen", o: v, prof: (v.x0 + v.x1 + v.y0 + v.y1) / 2 })),
    ...esquema.cubiertas.map((c) => ({ tipo: "cubierta", o: c, prof: (c.x0 + c.x1 + c.y0 + c.y1) / 2 })),
    ...esquema.arboles.map((t) => ({ tipo: "arbol", o: t, prof: t.x + t.y })),
  ].sort((a, b) => b.prof - a.prof);
  const gv = el("g", { class: "volumenes" }, svg);
  for (const { tipo, o } of objetos) {
    const g = el("g", {}, gv);
    if (tipo === "volumen") {
      caja(g, o.x0, o.y0, o.x1, o.y1, 0, o.altura, sol);
      const a = o.alero;
      losa(g, o.x0 - a, o.y0 - a, o.x1 + a, o.y1 + a, o.altura, o.techo === "losa" ? "losa" : "lamina", sol);
    } else if (tipo === "cubierta") {
      for (const [x, y] of [[o.x0, o.y0], [o.x1, o.y0], [o.x0, o.y1], [o.x1, o.y1]]) {
        caja(g, x - 0.15, y - 0.15, x + 0.15, y + 0.15, 0, o.altura, sol, "var(--muro-oscuro)");
      }
      losa(g, o.x0, o.y0, o.x1, o.y1, o.altura, "lamina", sol);
    } else {
      const [tx, ty] = p(o.x, o.y, 0);
      const [cx, cy] = p(o.x, o.y, o.altura - o.radio * 0.6);
      el("line", { x1: tx, y1: ty, x2: cx, y2: cy, class: "tronco" }, g);
      el("circle", { cx: cx.toFixed(2), cy: cy.toFixed(2), r: o.radio, class: "copa" }, g);
    }
  }

  if (capa === "agua") {
    const gr = el("g", { class: "rotulos" }, svg);
    const rotular = (x, y, z, texto) => {
      const [px, py] = p(x, y, z);
      const g = el("g", { class: "rotulo-svg", transform: `translate(${px.toFixed(2)} ${py.toFixed(2)})` }, gr);
      const ancho = texto.length * 1.02 + 2.4;
      el("rect", { x: -ancho / 2, y: -2.1, width: ancho, height: 3.2, rx: 0.2 }, g);
      el("text", { x: 0, y: 0.4, "text-anchor": "middle" }, g).textContent = texto;
    };
    rotular(...esquema.agua.punto_bajo, 1.5, "punto bajo");
  }

  svg.classList.toggle("sin-sol", sol.altura <= 0);
}

// La caja que abarca la maqueta entera, para el viewBox.
function encuadre(esquema, margen = 1) {
  const T = esquema.terreno;
  const alto = Math.max(...esquema.volumenes.map((v) => v.altura), ...esquema.cubiertas.map((c) => c.altura), ...esquema.arboles.map((a) => a.altura)) + 3;
  const esquinas = [
    p(T.x0, T.y0, -T.espesor), p(T.x1, T.y0, -T.espesor), p(T.x0, T.y1, -T.espesor),
    p(T.x1, T.y1, alto), p(T.x0, T.y1, alto), p(T.x1, T.y0, alto),
  ];
  const xs = esquinas.map((e) => e[0]);
  const ys = esquinas.map((e) => e[1]);
  const x = Math.min(...xs) - margen;
  const y = Math.min(...ys) - margen;
  return `${x.toFixed(1)} ${y.toFixed(1)} ${(Math.max(...xs) - x + margen).toFixed(1)} ${(Math.max(...ys) - y + margen).toFixed(1)}`;
}

// La brújula: el cielo visto desde arriba, tumbado en la misma proyección que la maqueta, con
// el sol a una distancia del centro que crece al bajar (en el borde, el horizonte).
const R_CIELO = 40;
function brujula() {
  const fig = html("figure", { class: "brujula", "aria-hidden": "true" });
  const svg = el("svg", { viewBox: "-56 -38 112 76" });
  const circulo = (r, cls) => el("ellipse", { rx: (r * C30 * Math.SQRT2).toFixed(2), ry: (r * 0.5 * Math.SQRT2).toFixed(2), class: cls }, svg);
  circulo(R_CIELO, "cielo");
  circulo(R_CIELO / 2, "anillo");
  for (const [x, y] of [[0, R_CIELO], [R_CIELO, 0]]) {
    const [ax, ay] = p(-x, -y);
    const [bx, by] = p(x, y);
    el("line", { x1: ax.toFixed(2), y1: ay.toFixed(2), x2: bx.toFixed(2), y2: by.toFixed(2), class: "eje" }, svg);
  }
  for (const [letra, x, y] of [["N", 0, 1], ["E", 1, 0], ["S", 0, -1], ["O", -1, 0]]) {
    const [tx, ty] = p(x * (R_CIELO + 8), y * (R_CIELO + 8));
    el("text", { x: tx.toFixed(2), y: (ty + 3).toFixed(2), class: `rumbo${letra === "N" ? " norte" : ""}` }, svg).textContent = letra;
  }
  const sol = el("circle", { r: 5, class: "sol" }, svg);
  fig.append(svg, html("figcaption", { texto: "Sol en el cielo" }));
  return {
    fig,
    pintar(s) {
      sol.style.display = s.altura > 0 ? "" : "none";
      const r = ((90 - Math.max(0, s.altura)) / 90) * R_CIELO;
      const [x, y] = p(r * Math.sin(s.acimut * RAD), r * Math.cos(s.acimut * RAD));
      sol.setAttribute("cx", x.toFixed(2));
      sol.setAttribute("cy", y.toFixed(2));
    },
  };
}

// El módulo

// La latitud, la longitud y el huso de la escuela elegida: de su escuela.json o de su fila en
// escuelas.json. Sin ninguno de los dos, el punto del ejemplo.
function puntoDeLaEscuela(ctx) {
  const fila = ctx.datos.escuelas?.escuelas?.find((e) => e.slug === ctx.estado.escuela);
  for (const f of [ctx.datos.escuela, fila]) {
    if (f && [f.lat, f.lon, f.huso_horas].every(Number.isFinite)) {
      return { lat: f.lat, lon: f.lon, huso: f.huso_horas, nombre: f.nombre ?? "la escuela elegida" };
    }
  }
  return { ...PUNTO_EJEMPLO, nombre: "la escuela de ejemplo" };
}

// Los huecos de la barra que llena este módulo: por su id, si index.html lo lleva, o por el
// rótulo de su celda.
function hueco(id, rotulo) {
  const porId = document.getElementById(id);
  if (porId) return porId;
  const celda = [...document.querySelectorAll(".barra .celda")]
    .find((c) => c.querySelector(".rotulo")?.textContent.trim() === rotulo);
  return celda?.querySelector(".valor") ?? null;
}

// Si el día de la URL no es uno de los del selector (el 21 de junio, por ejemplo), se añade
// como opción, en su sitio, para que el selector diga qué día se ve.
function asegurarDia(select, dia) {
  if ([...select.options].some((o) => Number(o.value) === dia)) return;
  const opcion = new Option(fechaTexto(dia), String(dia));
  const despues = [...select.options].find((o) => Number(o.value) > dia);
  select.add(opcion, despues ?? null);
  select.value = String(dia);
}

function sinMaqueta(montaje) {
  montaje.replaceChildren(html("div", { class: "lienzo-vacio" },
    html("p", { class: "rotulo-acento", texto: "La escena" }),
    html("p", { texto: "Todavía no hay maqueta genérica: falta comun/maqueta-generica.json." })));
}

export function iniciar(ctx) {
  const montaje = document.getElementById("maqueta");
  const esquema = ctx.datos.maquetaGenerica;
  if (!montaje) return;
  if (!esquema) {
    sinMaqueta(montaje);
    return;
  }
  const punto = puntoDeLaEscuela(ctx);

  // La escena: el rótulo, la brújula y el SVG con su <title> y su <desc>.
  const titulo = el("title", { id: "maqueta-titulo" });
  titulo.textContent = `${ROTULO}. Escuela tipo con el sol de ${punto.nombre}`;
  const desc = el("desc", { id: "maqueta-desc" });
  const svg = el("svg", {
    class: "maqueta-svg", role: "img", "aria-labelledby": "maqueta-titulo maqueta-desc",
    viewBox: encuadre(esquema), preserveAspectRatio: "xMidYMid meet",
  });
  svg.append(titulo, desc);
  const rosa = brujula();
  const leyenda = html("p", { class: "leyenda maqueta-leyenda" });
  const escena = html("div", { class: "maqueta-escena" },
    html("p", { class: "maqueta-rotulo", texto: ROTULO }), rosa.fig, svg);

  // La sombra del patio a cuatro horas del día elegido, y la pregunta de la #23.
  const tituloPatio = html("h2", { class: "maqueta-titulo", id: "patio-titulo" });
  const leyendaTabla = html("caption", { class: "visualmente-oculto" });
  const cuerpoTabla = html("tbody");
  const bloquePatio = html("section", { class: "maqueta-bloque", "aria-labelledby": "patio-titulo" },
    tituloPatio,
    html("table", { class: "tabla tabla-patio" }, leyendaTabla,
      html("thead", {}, html("tr", {},
        html("th", { scope: "col", texto: "Hora" }),
        html("th", { scope: "col", class: "num", texto: "Patio a la sombra" }))),
      cuerpoTabla),
    html("p", { class: "maqueta-pregunta" },
      html("span", { class: "rotulo", texto: "Para conversar" }), html("span", { texto: PREGUNTA_ALEROS })));

  montaje.classList.add("con-escena");
  montaje.replaceChildren(escena, leyenda, html("div", { class: "maqueta-texto" }, bloquePatio));

  // Los mandos que activa este módulo: el día y la capa.
  const fecha = document.getElementById("fecha");
  if (fecha) {
    asegurarDia(fecha, ctx.estado.dia);
    fecha.disabled = false;
  }
  const capa = document.querySelector('input[name="capa"]')?.closest("fieldset");
  if (capa) capa.disabled = false;
  const nota = document.getElementById("mandos-nota");
  if (nota) nota.textContent = "La hora, el día y la capa mueven la maqueta genérica. La vista se activa con el mapa.";

  const solValor = hueco("sol-valor", "Sol");
  const patioValor = hueco("patio-valor", "Patio a la sombra");
  const frase = document.querySelector(".lectura-hora .estado");
  const alero = esquema.volumenes.find((v) => v.id === "pabellon-a")?.alero;

  const pintarTabla = (estado) => {
    const dia = fechaTexto(estado.dia);
    tituloPatio.textContent = `La sombra del patio, el ${dia}`;
    leyendaTabla.textContent = `Parte del patio de la maqueta genérica a la sombra el ${dia}, con el sol de ${punto.nombre}`;
    cuerpoTabla.replaceChildren(...HORAS_TABLA.map((h) => {
      const { patio } = momento(esquema, punto, estado.dia, h);
      return html("tr", {},
        html("th", { scope: "row", texto: horaTexto(h) }),
        html("td", { class: "num", texto: patio === null ? "sin sol directo" : `${patio} %` }));
    }));
  };

  const pintar = (estado) => {
    const { sol, s, patio } = momento(esquema, punto, estado.dia, estado.hora);
    const conSol = sol.altura > SOL_MINIMO;
    const dia = fechaTexto(estado.dia);
    const hora = horaTexto(estado.hora);
    dibujar(svg, esquema, { sol, s, capa: estado.capa });
    rosa.pintar(sol);
    escena.hidden = estado.vista !== "maqueta";

    const textoSol = sol.altura > 0
      ? `${Math.round(sol.altura)}°, hacia ${rumbo(sol.acimut)}`
      : "Bajo el horizonte";
    if (solValor) {
      solValor.textContent = textoSol;
      solValor.classList.remove("hueco");
    }
    if (patioValor) {
      patioValor.textContent = patio === null ? "Sin sol directo" : `${patio} %`;
      patioValor.classList.remove("hueco");
    }
    if (frase) {
      frase.textContent = sol.altura > 0
        ? `${dia}, en ${punto.nombre}: el sol está a ${Math.round(sol.altura)}° de altura, hacia ${rumbo(sol.acimut)}.`
        : `${dia}, en ${punto.nombre}: el sol está bajo el horizonte.`;
    }

    leyenda.textContent = {
      sombra: `Sombras con el sol de ${punto.nombre}, sobre una escuela tipo: los edificios no son los suyos. El alero de los pabellones de aulas mide ${coma(alero)} m.`,
      calor: "Tiñe el suelo del patio y de la cancha que recibe sol directo a esta hora. No es una temperatura: la de superficie, de Landsat, se ve en el mapa del entorno.",
      agua: "Por dónde tendería a correr el agua de lluvia según la pendiente dibujada de la escuela tipo, hacia el punto bajo de la esquina suroeste. No es el relieve de la escuela.",
    }[estado.capa];

    const partes = [
      `Escuela tipo, no es ${punto.nombre}: dos pabellones de aulas, la dirección, los sanitarios, un techo sobre el patio, una cancha y árboles.`,
      `${dia}, ${hora}.`,
      sol.altura > 0 ? `El sol está a ${Math.round(sol.altura)}° de altura, hacia ${rumbo(sol.acimut)}.` : "El sol está bajo el horizonte.",
    ];
    if (conSol) partes.push(`El ${patio} % del patio queda a la sombra.`);
    if (estado.capa === "agua") partes.push("Capa de agua: el agua baja de los techos hacia la canaleta del pabellón de aulas B y corre hacia el punto bajo, en la esquina suroeste.");
    desc.textContent = partes.join(" ");
  };

  ctx.alCambiar((estado, cambiadas) => {
    if (cambiadas.includes("dia")) pintarTabla(estado);
    if (cambiadas.some((c) => ["dia", "hora", "capa", "vista"].includes(c))) pintar(estado);
  });
  pintarTabla(ctx.estado);
  pintar(ctx.estado);
}
