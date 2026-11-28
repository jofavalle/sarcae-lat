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
  fecha: "abr",
  hora: 10,
};

let esquema;
let ficha;
let maqueta3d = null;

function textoHora(h) {
  const hh = Math.floor(h);
  const mm = Math.round((h - hh) * 60);
  return `${hh}:${String(mm).padStart(2, "0")}`;
}

function momento(h) {
  if (h < 7) return "antes de la entrada";
  if (h < 7.5) return "entrada";
  if (h >= 9.75 && h <= 10.25) return "recreo";
  if (h < 12) return "turno de la mañana";
  if (h < 13) return "mediodía";
  if (h < 17) return "turno de la tarde";
  return "después de clase";
}

function solActual() {
  const f = ficha.fechas.find((x) => x.id === estado.fecha);
  return posicionSol(f.dia_del_anio, estado.hora, esquema.latitud, esquema.longitud, esquema.huso_horas);
}

const LEYENDAS = {
  sombra: "Sombra calculada con la posición del sol en la latitud de El Salvador · el alero de los pabellones mide 1,2 m",
  calor: "Temperatura de superficie de ejemplo, como la que mide Landsat hacia las 10:30 · la trama marca 60 °C o más · no es la temperatura del aire",
  agua: "Recorrido del agua de lluvia según la pendiente del esquema · la real saldrá de NASADEM",
};

function pintar() {
  const sol = solActual();
  const fecha = ficha.fechas.find((x) => x.id === estado.fecha).texto;
  const parada = ficha.paradas[estado.parada];
  const s = sombras(esquema, sol);
  const conSol = sol.elevacion > 2;
  const patio = conSol ? Math.round(sombraEnPatio(esquema, s) * 100) : null;

  dibujar($("maqueta"), esquema, { sol, capa: estado.capa, seleccion: parada.volumen });

  const hora = textoHora(estado.hora);
  $("hora-grande").textContent = hora;
  $("hora").setAttribute("aria-valuetext", `${hora}, ${momento(estado.hora)}`);
  const solTexto = conSol
    ? `${Math.round(sol.elevacion)}° de altura, desde ${rumbo(sol.azimut)}`
    : "bajo el horizonte";
  $("estado-sol").textContent = `${fecha} · ${momento(estado.hora)} · el sol a ${solTexto}`;
  $("sol-valor").textContent = conSol ? `${Math.round(sol.elevacion)}° · ${rumbo(sol.azimut).replace("el ", "")}` : "no ha salido";
  $("patio-valor").textContent = patio === null ? "—" : `${patio} %`;
  $("leyenda").textContent = maqueta3d
    ? "Maqueta 3D: solo los volúmenes, con la luz del sol de la hora elegida · las capas se ven en la vista esquemática"
    : LEYENDAS[estado.capa];

  const desc = [`Esquema de una escuela tipo a las ${hora} del ${fecha}.`];
  if (patio !== null) desc.push(`El ${patio} % del patio queda a la sombra.`);
  if (estado.capa === "calor") desc.push("Capa de calor: los techos de lámina, de 60 a 64 °C, son la superficie más caliente; las copas de los árboles, unos 31 °C.");
  if (estado.capa === "agua") desc.push("Capa de agua: el agua baja de los techos hacia la canaleta del pabellón B y corre hacia el punto bajo, en la esquina suroeste.");
  desc.push(`Parada: ${parada.titulo}.`);
  $("maqueta-desc").textContent = desc.join(" ");

  maqueta3d?.actualizar(sol);
}

function pintarTextos() {
  const r = ficha.registros[estado.registro];
  $("titulo").textContent = r.titulo;
  const parada = ficha.paradas[estado.parada];
  $("panel-eyebrow").textContent = `Parada ${estado.parada + 1} de ${ficha.paradas.length} · ${parada.titulo}`;
  $("panel-titulo").textContent = parada.pregunta[estado.registro];
  $("panel-texto").textContent = parada.texto[estado.registro];
  document.querySelectorAll(".parada").forEach((b, i) => b.setAttribute("aria-pressed", String(i === estado.parada)));
  $("anterior").disabled = estado.parada === 0;
  $("siguiente").disabled = estado.parada === ficha.paradas.length - 1;

  $("lista-paradas").replaceChildren(...ficha.paradas.map((p, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<p class="eyebrow mono">Parada ${i + 1}</p><h3></h3><p></p><p class="pregunta-texto"></p>`;
    li.querySelector("h3").textContent = p.titulo;
    li.querySelectorAll("p")[1].textContent = p.texto[estado.registro];
    li.querySelector(".pregunta-texto").textContent = p.pregunta[estado.registro];
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

function construir() {
  $("maqueta").setAttribute("viewBox", encuadre(esquema));
  $("escuela-nombre").textContent = `${ficha.escuela.nombre} · ${ficha.escuela.pais}`;

  $("fecha").replaceChildren(...ficha.fechas.map((f) => new Option(f.texto, f.id, false, f.id === estado.fecha)));

  $("paradas").replaceChildren(...ficha.paradas.map((p, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "parada";
    b.innerHTML = `<span class="mono">${i + 1}</span> `;
    b.append(p.titulo);
    b.addEventListener("click", () => irAParada(i));
    return b;
  }));

  $("lecturas").replaceChildren(...ficha.clima.cifras.slice(0, 3).flatMap((c) => {
    const dt = document.createElement("dt");
    dt.textContent = c.rotulo;
    const dd = document.createElement("dd");
    dd.className = "mono";
    dd.textContent = `${c.valor}${c.unidad ? " " + c.unidad : ""}`;
    const div = document.createElement("div");
    div.append(dt, dd);
    return [div];
  }));

  $("clima-nota").textContent = `${ficha.clima.nota} ${ficha.clima.fuente}`;
  $("cifras").replaceChildren(...ficha.clima.cifras.map((c) => {
    const div = document.createElement("div");
    div.innerHTML = `<dt></dt><dd class="mono cifra-numero"><span class="cifra-valor"></span> <span class="cifra-unidad"></span></dd><dd class="cifra-detalle"></dd>`;
    div.querySelector(".cifra-valor").textContent = c.valor;
    div.querySelector(".cifra-unidad").textContent = c.unidad;
    div.querySelector("dt").textContent = c.rotulo;
    div.querySelector(".cifra-detalle").textContent = c.detalle;
    return div;
  }));

  $("lista-limites").replaceChildren(...ficha.limites.map((t) => Object.assign(document.createElement("li"), { textContent: t })));
  $("lista-fuentes").replaceChildren(...ficha.fuentes.map((f) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="fuente-nombre"></span> <span class="mono fuente-licencia"></span> <span class="fuente-uso"></span>`;
    li.querySelector(".fuente-nombre").textContent = f.nombre;
    li.querySelector(".fuente-licencia").textContent = f.licencia;
    li.querySelector(".fuente-uso").textContent = f.uso;
    return li;
  }));

  // Controles.
  document.querySelectorAll('input[name="direccion"]').forEach((r) => r.addEventListener("change", () => {
    estado.direccion = r.value;
    raiz.dataset.direccion = r.value;
    localStorage.setItem("sarcae-direccion", r.value);
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
  $("hora").addEventListener("input", (e) => {
    estado.hora = Number(e.target.value);
    pintar();
  });
  $("fecha").addEventListener("change", (e) => {
    estado.fecha = e.target.value;
    pintar();
  });
  $("anterior").addEventListener("click", () => irAParada(Math.max(0, estado.parada - 1)));
  $("siguiente").addEventListener("click", () => irAParada(Math.min(ficha.paradas.length - 1, estado.parada + 1)));
  $("abrir-3d").addEventListener("click", alternar3d);
  $("form-pregunta").addEventListener("submit", (e) => {
    e.preventDefault();
    $("respuesta").textContent = "El asistente todavía no está conectado en este prototipo: no se envió nada.";
  });
}

async function alternar3d() {
  const boton = $("abrir-3d");
  const caja = $("mapa3d");
  if (maqueta3d) {
    maqueta3d.cerrar();
    maqueta3d = null;
    caja.hidden = true;
    $("maqueta").removeAttribute("hidden");
    boton.innerHTML = 'Maqueta 3D <span class="mono">· 470 KB</span>';
    pintar();
    return;
  }
  boton.disabled = true;
  boton.textContent = "Cargando la maqueta 3D…";
  try {
    const { Maqueta3D } = await import("./maqueta3d.js");
    caja.hidden = false;
    maqueta3d = new Maqueta3D(caja, esquema);
    await maqueta3d.abrir(solActual());
    $("maqueta").setAttribute("hidden", "");
    boton.textContent = "Vista esquemática";
    pintar();
  } catch (err) {
    maqueta3d = null;
    caja.hidden = true;
    boton.innerHTML = 'Maqueta 3D <span class="mono">· 470 KB</span>';
    $("leyenda").textContent = err.message;
  } finally {
    boton.disabled = false;
  }
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
