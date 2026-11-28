// Maqueta esquemática en SVG isométrico: el sol de un día y una hora, las sombras que
// proyectan los volúmenes, y las capas de calor y de agua. Es la vista ligera de la primera
// pantalla; la 3D con MapLibre se carga solo cuando se pide (maqueta3d.js).

const RAD = Math.PI / 180;
const SVG = "http://www.w3.org/2000/svg";
const GROSOR_TECHO = 0.25;

// Posición del sol con las ecuaciones aproximadas de la NOAA (General Solar Position
// Calculations). Azimut en grados desde el norte, en el sentido de las agujas del reloj.
export function posicionSol(diaDelAnio, horaLocal, lat, lon, husoHoras) {
  const g = (2 * Math.PI / 365) * (diaDelAnio - 1 + (horaLocal - 12) / 24);
  const ecTiempo = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g)
    - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
  const decl = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g)
    - 0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g)
    - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
  const tiempoSolar = horaLocal * 60 + ecTiempo + 4 * lon - 60 * husoHoras;
  const ha = (tiempoSolar / 4 - 180) * RAD;
  const phi = lat * RAD;
  const cosZ = Math.sin(phi) * Math.sin(decl) + Math.cos(phi) * Math.cos(decl) * Math.cos(ha);
  const elevacion = 90 - Math.acos(Math.min(1, Math.max(-1, cosZ))) / RAD;
  const azimut = (Math.atan2(Math.sin(ha), Math.cos(ha) * Math.sin(phi) - Math.tan(decl) * Math.cos(phi)) / RAD + 540) % 360;
  return { elevacion, azimut };
}

const RUMBOS = ["el norte", "el noreste", "el este", "el sureste", "el sur", "el suroeste", "el oeste", "el noroeste"];
export function rumbo(azimut) {
  return RUMBOS[Math.round(azimut / 45) % 8];
}

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

// Las sombras en el suelo: polígonos convexos y círculos, en metros.
export function sombras(esquema, sol) {
  if (sol.elevacion <= 2) return { poligonos: [], circulos: [] };
  const k = 1 / Math.tan(sol.elevacion * RAD);
  const dx = -Math.sin(sol.azimut * RAD) * k;
  const dy = -Math.cos(sol.azimut * RAD) * k;
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

// Qué parte del patio queda a la sombra: una muestra cada medio metro.
export function sombraEnPatio(esquema, s) {
  const patio = esquema.superficies.find((x) => x.id === "patio");
  let total = 0;
  let enSombra = 0;
  for (let x = patio.x0 + 0.25; x < patio.x1; x += 0.5) {
    for (let y = patio.y0 + 0.25; y < patio.y1; y += 0.5) {
      total++;
      if (s.poligonos.some((q) => dentroConvexo(q, x, y))
        || s.circulos.some((c) => (x - c.x) ** 2 + (y - c.y) ** 2 <= c.r ** 2)) enSombra++;
    }
  }
  return enSombra / total;
}

// Luz difusa de una cara según el sol: 0 de espaldas, 1 de frente.
function luz(normal, sol) {
  if (sol.elevacion <= 0) return 0.15;
  const ce = Math.cos(sol.elevacion * RAD);
  const s = [Math.sin(sol.azimut * RAD) * ce, Math.cos(sol.azimut * RAD) * ce, Math.sin(sol.elevacion * RAD)];
  const d = normal[0] * s[0] + normal[1] * s[1] + normal[2] * s[2];
  return 0.25 + 0.75 * Math.max(0, d);
}
function tono(claro, oscuro, f) {
  return `color-mix(in oklab, var(${claro}) ${Math.round(f * 100)}%, var(${oscuro}))`;
}

function claseCalor(t) {
  if (t >= 60) return "muy-caliente";
  if (t >= 50) return "caliente";
  if (t >= 40) return "templado";
  return "fresco";
}

function caja(g, x0, y0, x1, y1, z0, z1, sol, cls, rellenoSup) {
  // Caras visibles desde el suroeste: sur, oeste y la de arriba.
  el("polygon", {
    points: puntos([[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]]),
    style: `fill:${tono("--muro-claro", "--muro-oscuro", luz([0, -1, 0], sol))}`,
    class: `${cls} cara`,
  }, g);
  el("polygon", {
    points: puntos([[x0, y0, z0], [x0, y1, z0], [x0, y1, z1], [x0, y0, z1]]),
    style: `fill:${tono("--muro-claro", "--muro-oscuro", luz([-1, 0, 0], sol))}`,
    class: `${cls} cara`,
  }, g);
  if (rellenoSup) {
    el("polygon", { points: puntos(rect(x0, y0, x1, y1, z1)), style: `fill:${rellenoSup}`, class: `${cls} arriba` }, g);
  }
}

function losa(g, x0, y0, x1, y1, z, material, sol, capa, t, id) {
  const z1 = z + GROSOR_TECHO;
  const lado = tono(material === "losa" ? "--techo" : "--techo-lamina", "--techo-lado", 0.35 + 0.4 * luz([0, -1, 0], sol));
  el("polygon", { points: puntos([[x0, y0, z], [x1, y0, z], [x1, y0, z1], [x0, y0, z1]]), style: `fill:${lado}` }, g);
  el("polygon", { points: puntos([[x0, y0, z], [x0, y1, z], [x0, y1, z1], [x0, y0, z1]]), style: `fill:${lado}` }, g);
  const arriba = el("polygon", {
    points: puntos(rect(x0, y0, x1, y1, z1)),
    style: `fill:${tono(material === "losa" ? "--techo" : "--techo-lamina", "--techo-lado", 0.45 + 0.55 * luz([0, 0, 1], sol))}`,
    class: "techo",
    "data-id": id,
  }, g);
  if (capa === "calor") {
    arriba.classList.add("calor", claseCalor(t));
    if (t >= 60) el("polygon", { points: puntos(rect(x0, y0, x1, y1, z1)), class: "trama" }, g);
  }
}

// Dibuja la escena entera en el <svg> dado.
export function dibujar(svg, esquema, estado) {
  const { sol, capa, seleccion } = estado;
  // Se conservan el <title> y el <desc>, que dan el texto de la maqueta al lector de pantalla.
  for (const n of [...svg.children]) if (n.localName !== "title" && n.localName !== "desc") n.remove();
  const T = esquema.terreno;
  const esp = T.espesor;

  const defs = el("defs", {}, svg);
  const trama = el("pattern", { id: "trama-calor", width: 1.6, height: 1.6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(35)" }, defs);
  el("line", { x1: 0, y1: 0, x2: 0, y2: 1.6, class: "trama-linea" }, trama);
  const flecha = el("marker", { id: "flecha-agua", viewBox: "0 0 10 10", refX: 6, refY: 5, markerWidth: 5, markerHeight: 5, orient: "auto-start-reverse" }, defs);
  el("path", { d: "M0,0 L10,5 L0,10 z", class: "flecha" }, flecha);
  const recorte = el("clipPath", { id: "recorte-terreno" }, defs);
  el("polygon", { points: puntos(rect(T.x0, T.y0, T.x1, T.y1, 0)) }, recorte);

  // Base de la maqueta, con su espesor.
  const base = el("g", { class: "base" }, svg);
  el("polygon", { points: puntos([[T.x0, T.y0, -esp], [T.x1, T.y0, -esp], [T.x1, T.y0, 0], [T.x0, T.y0, 0]]), style: "fill:var(--suelo-lado-2)" }, base);
  el("polygon", { points: puntos([[T.x0, T.y0, -esp], [T.x0, T.y1, -esp], [T.x0, T.y1, 0], [T.x0, T.y0, 0]]), style: "fill:var(--suelo-lado)" }, base);
  el("polygon", { points: puntos(rect(T.x0, T.y0, T.x1, T.y1, 0)), style: "fill:var(--suelo)" }, base);

  // Superficies del suelo.
  for (const s of esquema.superficies) {
    const pol = el("polygon", { points: puntos(rect(s.x0, s.y0, s.x1, s.y1, 0)), style: `fill:var(--${s.rol})`, "data-id": s.id }, base);
    if (capa === "calor") pol.classList.add("calor", claseCalor(s.t_superficie));
    if (s.rol === "cancha") {
      const cx = (s.x0 + s.x1) / 2;
      el("polygon", { points: puntos(rect(s.x0 + 1, s.y0 + 1, s.x1 - 1, s.y1 - 1, 0)), class: "cancha-linea" }, base);
      el("polyline", { points: puntos([[cx, s.y0 + 1, 0], [cx, s.y1 - 1, 0]]), class: "cancha-linea" }, base);
    }
  }

  // Sombras, recortadas al terreno.
  if (capa !== "agua") {
    const s = sombras(esquema, sol);
    const gs = el("g", { class: "sombras", "clip-path": "url(#recorte-terreno)" }, svg);
    for (const q of s.poligonos) el("polygon", { points: puntos(q.map(([x, y]) => [x, y, 0])) }, gs);
    for (const c of s.circulos) {
      const [px, py] = p(c.x, c.y, 0);
      el("ellipse", { cx: px.toFixed(2), cy: py.toFixed(2), rx: (c.r * 1.22).toFixed(2), ry: (c.r * 0.7).toFixed(2) }, gs);
    }
  }

  // Agua: canaleta, recorridos y punto bajo.
  if (capa === "agua") {
    const ga = el("g", { class: "agua" }, svg);
    el("polyline", { points: puntos(esquema.agua.canaleta.map(([x, y]) => [x, y, 0])), class: "canaleta" }, ga);
    for (const l of esquema.agua.lineas) {
      el("polyline", { points: puntos(l.map(([x, y]) => [x, y, 0])), class: "flujo", "marker-end": "url(#flecha-agua)" }, ga);
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
    const g = el("g", { class: `objeto ${o.id === seleccion ? "seleccionado" : ""}`, "data-id": o.id || "" }, gv);
    if (tipo === "volumen") {
      caja(g, o.x0, o.y0, o.x1, o.y1, 0, o.altura, sol, "muro");
      const a = o.alero;
      losa(g, o.x0 - a, o.y0 - a, o.x1 + a, o.y1 + a, o.altura, o.techo === "losa" ? "losa" : "lamina", sol, capa, o.t_superficie, o.id);
    } else if (tipo === "cubierta") {
      for (const [x, y] of [[o.x0, o.y0], [o.x1, o.y0], [o.x0, o.y1], [o.x1, o.y1]]) {
        caja(g, x - 0.15, y - 0.15, x + 0.15, y + 0.15, 0, o.altura, sol, "columna", "var(--muro-oscuro)");
      }
      losa(g, o.x0, o.y0, o.x1, o.y1, o.altura, "lamina", sol, capa, o.t_superficie, o.id);
    } else {
      const [tx, ty] = p(o.x, o.y, 0);
      const [cx, cy] = p(o.x, o.y, o.altura - o.radio * 0.6);
      el("line", { x1: tx, y1: ty, x2: cx, y2: cy, class: "tronco" }, g);
      const copa = el("circle", { cx: cx.toFixed(2), cy: cy.toFixed(2), r: o.radio, class: "copa" }, g);
      if (capa === "calor") copa.classList.add("calor", claseCalor(o.t_superficie));
    }
  }

  // Rótulos: el volumen seleccionado y, en la capa de calor, las temperaturas.
  const gr = el("g", { class: "rotulos" }, svg);
  const rotular = (x, y, z, texto, cls) => {
    const [px, py] = p(x, y, z);
    const g = el("g", { class: `rotulo ${cls}`, transform: `translate(${px.toFixed(2)} ${py.toFixed(2)})` }, gr);
    const ancho = texto.length * 1.02 + 2.4;
    el("rect", { x: -ancho / 2, y: -2.1, width: ancho, height: 3.2, rx: 0.5 }, g);
    const t = el("text", { x: 0, y: 0.4, "text-anchor": "middle" }, g);
    t.textContent = texto;
  };
  const todos = [...esquema.volumenes, ...esquema.cubiertas];
  if (capa === "calor") {
    for (const v of todos) rotular((v.x0 + v.x1) / 2, (v.y0 + v.y1) / 2, v.altura + 1.2, `${v.t_superficie} °C`, "dato");
    for (const s of esquema.superficies) rotular((s.x0 + s.x1) / 2 + (s.id === "patio" ? -8 : 0), (s.y0 + s.y1) / 2 + (s.id === "patio" ? -4 : 0), 0.6, `${s.t_superficie} °C`, "dato");
    const t = esquema.arboles[1];
    rotular(t.x, t.y, t.altura + 1.2, `${t.t_superficie} °C`, "dato");
  } else if (capa === "agua") {
    rotular(...esquema.agua.punto_bajo, 1.5, "punto bajo", "dato");
    rotular(-13, -11, 1.2, "canaleta", "dato");
  }
  const sel = todos.find((v) => v.id === seleccion);
  if (sel) rotular((sel.x0 + sel.x1) / 2, (sel.y0 + sel.y1) / 2, sel.altura + (capa === "calor" ? 5 : 2.6), sel.nombre, "nombre");

  svg.classList.toggle("sin-sol", sol.elevacion <= 0);
}

// La caja que abarca la maqueta entera, para el viewBox.
export function encuadre(esquema, margen = 1) {
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
