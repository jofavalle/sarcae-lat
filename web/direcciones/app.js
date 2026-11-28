// La primera pantalla del prototipo: lee el esquema y la ficha de ejemplo, y enlaza los
// controles con la maqueta. La interfaz no recalcula cifras del clima: solo el sol y las
// sombras del esquema, que son geometría.

import { posicionSol, rumbo, dibujar, encuadre, sombras, sombraEnPatio } from "./maqueta.js";

const $ = (id) => document.getElementById(id);
const raiz = document.documentElement;

const estado = {
  direccion: "noche",
  registro: "docente",
  parada: 0,
  capa: "sombra",
  vista: "maqueta",
  fecha: "abr",
  hora: 10,
};

let esquema;
let ficha;
let mapa = null;
let modMapa = null;

function textoHora(h) {
  const hh = Math.floor(h);
  const mm = Math.round((h - hh) * 60);
  return `${hh}:${String(mm).padStart(2, "0")}`;
}

function momento(h) {
  if (h < 7) return "antes de la entrada";
  if (h < 7.5) return "la entrada";
  if (h >= 9.75 && h <= 10.25) return "el recreo";
  if (h < 12) return "el turno de la mañana";
  if (h < 13) return "el mediodía";
  if (h < 17) return "el turno de la tarde";
  return "después de clase";
}

const ICONOS = {
  calor: '<path d="M10 13.2V4a2 2 0 1 0-4 0v9.2a3.4 3.4 0 1 0 4 0Z"/><path d="M8 9v5"/>',
  lluvia: '<path d="M8 2s-4.5 5-4.5 8.5a4.5 4.5 0 0 0 9 0C12.5 7 8 2 8 2Z"/>',
  calendario: '<rect x="2.5" y="3.5" width="11" height="10" rx="1.5"/><path d="M2.5 6.5h11M5.5 2v3M10.5 2v3"/>',
};
function icono(nombre) {
  return `<svg class="icono icono-${nombre}" viewBox="0 0 16 16" aria-hidden="true">${ICONOS[nombre] ?? ""}</svg>`;
}

// La brújula solar: el sol en una vista del cielo desde arriba, con el centro en el cénit.
// En la maqueta isométrica el norte apunta arriba a la izquierda (60° a la izquierda).
function pintarBrujula(sol) {
  const giro = estado.vista === "maqueta" ? -60 : 0;
  $("brujula").hidden = estado.vista === "3d";
  $("brujula-rosa").setAttribute("transform", `rotate(${giro})`);
  document.querySelectorAll("#brujula .rumbo").forEach((t) => {
    t.setAttribute("transform", `rotate(${-giro} ${t.getAttribute("x")} ${t.getAttribute("y")})`);
  });
  const punto = $("brujula-sol");
  punto.style.display = sol.elevacion > 0 ? "" : "none";
  const r = ((90 - Math.max(0, sol.elevacion)) / 90) * 40;
  punto.setAttribute("cx", (r * Math.sin(sol.azimut * Math.PI / 180)).toFixed(1));
  punto.setAttribute("cy", (-r * Math.cos(sol.azimut * Math.PI / 180)).toFixed(1));
}

function solActual() {
  const f = ficha.fechas.find((x) => x.id === estado.fecha);
  return posicionSol(f.dia_del_anio, estado.hora, esquema.latitud, esquema.longitud, esquema.huso_horas);
}

function leyenda() {
  const c = esquema.calor_landsat;
  if (estado.vista === "maqueta") {
    return {
      sombra: "Sombra calculada con la posición del sol en la latitud de El Salvador. El alero de los pabellones mide 1,2 m. El mapa 2D y la vista 3D descargan 470 KB la primera vez.",
      calor: `Landsat mide la temperatura de superficie en cuadros de ${c.lado_m} m, y la escuela entera cabe en uno: no separa el techo del patio. Para comparar zonas del entorno, abre el mapa 2D. Cifra de ejemplo; no es la temperatura del aire.`,
      agua: "Recorrido del agua de lluvia según la pendiente del esquema. La pendiente real saldrá de NASADEM.",
    }[estado.capa];
  }
  if (estado.vista === "2d") {
    return {
      sombra: "Mapa del entorno con la planta del esquema. Las sombras se ven en la maqueta; el calor del entorno, en la capa de calor.",
      calor: `Temperatura de superficie de ejemplo en cuadros de ${c.lado_m} m alrededor de la escuela. El cuadro de trazos es el de la escuela. Compara zonas del entorno, no techos.`,
      agua: "Recorrido del agua de lluvia en la planta del esquema, hacia el punto bajo de la esquina suroeste.",
    }[estado.capa];
  }
  return "Vista 3D: los volúmenes del esquema con la luz del sol de la hora elegida. Las capas se ven en la maqueta y en el mapa 2D.";
}

function pintar() {
  const sol = solActual();
  const fecha = ficha.fechas.find((x) => x.id === estado.fecha).texto;
  const parada = ficha.paradas[estado.parada];
  const conSol = sol.elevacion > 2;
  const s = sombras(esquema, sol);
  const patio = conSol ? Math.round(sombraEnPatio(esquema, s) * 100) : null;

  dibujar($("maqueta"), esquema, { sol, capa: estado.capa, seleccion: parada.volumen });

  const hora = textoHora(estado.hora);
  $("hora-grande").textContent = hora;
  $("hora").setAttribute("aria-valuetext", `${hora}, ${momento(estado.hora)}`);
  $("estado-sol").textContent = conSol
    ? `${fecha}, ${momento(estado.hora)}. El sol está a ${Math.round(sol.elevacion)}° de altura, hacia ${rumbo(sol.azimut)}.`
    : `${fecha}, ${momento(estado.hora)}. El sol está bajo el horizonte.`;
  $("sol-valor").textContent = conSol ? `${Math.round(sol.elevacion)}°, hacia ${rumbo(sol.azimut)}` : "Bajo el horizonte";
  $("patio-valor").textContent = patio === null ? "—" : `${patio} %`;
  $("leyenda").textContent = leyenda();
  $("clases-calor").hidden = $("tabla-calor").hidden = !(estado.vista === "2d" && estado.capa === "calor");

  const desc = [`Esquema de una escuela tipo a las ${hora} del ${fecha}.`];
  if (patio !== null) desc.push(`El ${patio} % del patio queda a la sombra.`);
  if (estado.capa === "calor") desc.push(`Capa de calor: la escuela entera cae en un solo cuadro de Landsat de ${esquema.calor_landsat.lado_m} m, con ${esquema.calor_landsat.t_superficie} °C de temperatura de superficie de ejemplo.`);
  if (estado.capa === "agua") desc.push("Capa de agua: el agua baja de los techos hacia la canaleta del pabellón B y corre hacia el punto bajo, en la esquina suroeste.");
  desc.push(`Parada: ${parada.titulo}.`);
  $("maqueta-desc").textContent = desc.join(" ");

  pintarBrujula(sol);
  const conMapa = estado.vista !== "maqueta" && !!mapa;
  $("controles-mapa").hidden = !conMapa;
  $("girar-izq").hidden = $("girar-der").hidden = estado.vista !== "3d";
  $("pista-uso").textContent = estado.vista === "3d"
    ? "Arrastra para girar e inclinar la maqueta. Usa la rueda o pellizca para acercar."
    : "Arrastra para mover el mapa. Usa la rueda o pellizca para acercar.";
  mapa?.actualizar(estado.vista, sol, estado.capa, s);
}

function pintarTextos() {
  const r = ficha.registros[estado.registro];
  $("titulo").textContent = r.titulo;
  const parada = ficha.paradas[estado.parada];
  $("panel-eyebrow").textContent = `Parada ${estado.parada + 1} de ${ficha.paradas.length}: ${parada.titulo}`;
  $("panel-titulo").textContent = parada.pregunta[estado.registro];
  $("panel-texto").textContent = parada.texto[estado.registro];
  document.querySelectorAll(".parada").forEach((b, i) => b.setAttribute("aria-pressed", String(i === estado.parada)));
  $("anterior").disabled = estado.parada === 0;
  $("siguiente").disabled = estado.parada === ficha.paradas.length - 1;

  $("lista-paradas").replaceChildren(...ficha.paradas.map((p, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<p class="numero-grande" aria-hidden="true"></p><h3></h3><p class="texto"></p><p class="pregunta-texto"><strong>Para conversar</strong><span></span></p>`;
    li.querySelector(".numero-grande").textContent = i + 1;
    li.querySelector("h3").textContent = p.titulo;
    li.querySelector(".texto").textContent = p.texto[estado.registro];
    li.querySelector(".pregunta-texto span").textContent = p.pregunta[estado.registro];
    return li;
  }));
}

function irAParada(i) {
  estado.parada = i;
  const p = ficha.paradas[i];
  estado.capa = p.capa;
  estado.hora = p.hora;
  $("hora").value = p.hora;
  document.querySelector(`input[name="capa"][value="${p.capa}"]`).checked = true;
  pintarTextos();
  pintar();
}

// Los cuadros de calor del mapa 2D también en una tabla, para que no dependan solo del color.
// Filas de norte a sur y columnas de oeste a este, como se ven en el mapa.
function construirTablaCalor() {
  const E = esquema.entorno_calor;
  const centro = (o, i) => o + i * E.lado_m + E.lado_m / 2;
  const nombre = (d, mas, menos) => (d === 0 ? "escuela" : `${Math.abs(d)} m al ${d > 0 ? mas : menos}`);
  const cabeza = document.createElement("tr");
  cabeza.innerHTML = '<td></td>';
  E.valores[0].forEach((_, j) => {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = nombre(centro(E.x0, j), "este", "oeste");
    cabeza.append(th);
  });
  $("cuadros-cabeza").replaceChildren(cabeza);
  const filas = E.valores.map((fila, i) => {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = nombre(centro(E.y0, i), "norte", "sur");
    tr.append(th);
    fila.forEach((t, j) => {
      const td = document.createElement("td");
      td.className = "num";
      td.textContent = `${t}`;
      if (centro(E.x0, j) === 0 && centro(E.y0, i) === 0) {
        td.classList.add("cuadro-escuela");
        td.textContent = `${t} (escuela)`;
      }
      tr.append(td);
    });
    return tr;
  });
  $("cuadros-calor").replaceChildren(...filas.reverse());
}

// La leyenda de clases del mapa 2D: muestra de color y texto, en HTML.
function pintarClases() {
  if (!modMapa) return;
  const css = getComputedStyle(raiz);
  const calor = css.getPropertyValue("--calor").trim();
  const fondo = css.getPropertyValue("--fondo-escena").trim();
  const n = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  $("clases-calor").replaceChildren(...modMapa.CLASES_CALOR.map((k) => {
    const li = document.createElement("li");
    const m = n(calor).map((v, i) => Math.round(v * k.peso + n(fondo)[i] * (1 - k.peso)));
    li.innerHTML = `<span class="muestra" style="background: rgb(${m.join(" ")})"></span>`;
    li.append(k.texto);
    return li;
  }));
}

async function cambiarVista(vista) {
  const caja = $("mapa");
  const svg = $("maqueta");
  const anterior = estado.vista;
  estado.vista = vista;
  if (vista === "maqueta") {
    mapa?.cerrar();
    mapa = null;
    caja.hidden = true;
    svg.removeAttribute("hidden");
    pintar();
    return;
  }
  if (mapa) {
    pintar();
    return;
  }
  $("leyenda").textContent = "Cargando MapLibre (470 KB)…";
  try {
    modMapa ??= await import("./mapa.js");
    caja.hidden = false;
    mapa = new modMapa.Mapa(caja, esquema);
    const sol = solActual();
    await mapa.abrir(vista, sol, estado.capa, sombras(esquema, sol));
    svg.setAttribute("hidden", "");
    pintarClases();
    pintar();
  } catch (err) {
    mapa = null;
    caja.hidden = true;
    estado.vista = anterior === vista ? "maqueta" : anterior;
    document.querySelector(`input[name="vista"][value="${estado.vista}"]`).checked = true;
    $("leyenda").textContent = err.message;
  }
}

function construir() {
  construirTablaCalor();
  $("maqueta").setAttribute("viewBox", encuadre(esquema));
  $("escuela-nombre").textContent = `${ficha.escuela.nombre}, ${ficha.escuela.pais}`;

  $("fecha").replaceChildren(...ficha.fechas.map((f) => new Option(f.texto, f.id, false, f.id === estado.fecha)));

  $("escala").replaceChildren(...Array.from({ length: 13 }, (_, k) => {
    const h = 6 + k;
    const s = document.createElement("span");
    s.style.left = `${(k / 12) * 100}%`;
    s.textContent = `${h}:00`;
    if (h % 2) s.className = "menor";
    return s;
  }));

  $("paradas").replaceChildren(...ficha.paradas.map((p, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "parada";
    b.innerHTML = `<span class="numero">${i + 1}</span>`;
    b.append(p.titulo);
    b.addEventListener("click", () => irAParada(i));
    return b;
  }));

  $("lecturas").replaceChildren(...ficha.clima.cifras.slice(0, 3).map((c) => {
    const div = document.createElement("div");
    const dt = document.createElement("dt");
    dt.innerHTML = icono(c.icono);
    dt.append(c.rotulo_corto);
    const dd = document.createElement("dd");
    dd.textContent = `${c.valor}${c.unidad ? " " + c.unidad : ""}`;
    div.append(dt, dd);
    return div;
  }));

  $("clima-nota").textContent = ficha.clima.nota;
  $("clima-fuente").textContent = `Fuente: ${ficha.clima.fuente}`;
  $("cifras").replaceChildren(...ficha.clima.cifras.map((c) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td></td><td class="num"></td><td class="secundario"></td>`;
    const [a, b, d] = tr.children;
    a.innerHTML = icono(c.icono);
    a.append(c.rotulo);
    b.textContent = `${c.valor}${c.unidad ? " " + c.unidad : ""}`;
    d.textContent = c.detalle;
    return tr;
  }));

  $("lista-limites").replaceChildren(...ficha.limites.map((t) => Object.assign(document.createElement("li"), { textContent: t })));
  $("lista-fuentes").replaceChildren(...ficha.fuentes.map((f) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td></td><td></td><td class="secundario"></td>`;
    const [a, b, d] = tr.children;
    a.textContent = f.nombre;
    b.textContent = f.licencia;
    d.textContent = f.uso;
    return tr;
  }));

  // Controles.
  document.querySelectorAll('input[name="direccion"]').forEach((r) => r.addEventListener("change", () => {
    estado.direccion = r.value;
    raiz.dataset.direccion = r.value;
    localStorage.setItem("sarcae-direccion", r.value);
    pintarClases();
    pintar();
  }));
  document.querySelectorAll('input[name="registro"]').forEach((r) => r.addEventListener("change", () => {
    estado.registro = r.value;
    pintarTextos();
  }));
  document.querySelectorAll('input[name="capa"]').forEach((r) => r.addEventListener("change", () => {
    estado.capa = r.value;
    pintar();
  }));
  document.querySelectorAll('input[name="vista"]').forEach((r) => r.addEventListener("change", () => cambiarVista(r.value)));
  $("hora").addEventListener("input", (e) => {
    estado.hora = Number(e.target.value);
    pintar();
  });
  $("fecha").addEventListener("change", (e) => {
    estado.fecha = e.target.value;
    pintar();
  });
  $("girar-izq").addEventListener("click", () => mapa?.girar(-45));
  $("girar-der").addEventListener("click", () => mapa?.girar(45));
  $("encuadrar").addEventListener("click", () => mapa?.encuadrar());
  $("anterior").addEventListener("click", () => irAParada(Math.max(0, estado.parada - 1)));
  $("siguiente").addEventListener("click", () => irAParada(Math.min(ficha.paradas.length - 1, estado.parada + 1)));
  $("form-pregunta").addEventListener("submit", (e) => {
    e.preventDefault();
    $("respuesta").textContent = "El asistente todavía no está conectado en este prototipo: no se envió nada.";
  });
}

async function iniciar() {
  const guardada = localStorage.getItem("sarcae-direccion");
  const pedida = new URLSearchParams(location.search).get("direccion");
  const dir = ["noche", "dia"].includes(pedida) ? pedida : ["noche", "dia"].includes(guardada) ? guardada : "noche";
  estado.direccion = dir;
  raiz.dataset.direccion = dir;
  document.querySelector(`input[name="direccion"][value="${dir}"]`).checked = true;

  [esquema, ficha] = await Promise.all([
    fetch("escuela-esquema.json").then((r) => r.json()),
    fetch("ficha-ejemplo.json").then((r) => r.json()),
  ]);
  construir();
  irAParada(1);
}

iniciar().catch((err) => {
  $("estado-sol").textContent = `No se pudieron cargar los datos del prototipo (${err.message}). Ábrelo con un servidor: ver README.md.`;
});
