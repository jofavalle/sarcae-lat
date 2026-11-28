// La primera pantalla: carga los datos de la escuela elegida, guarda el estado en la URL y
// arranca los módulos. La interfaz no recalcula lo que ya calculó Python (ADR-001): los
// números llegan redondeados desde web/datos/, como dice docs/contrato-datos.md.
//
// El contrato de módulos (orden #64). Cada módulo de js/ exporta iniciar(ctx), y ctx lleva:
//   - estado: el estado actual, de solo lectura (ver ESTADO, abajo);
//   - datos: los JSON cargados, cada uno null si falta o no se puede leer (ver cargar());
//   - cambiar(parcial): actualiza el estado con las claves dadas, lo escribe en la URL y avisa
//     a los suscritos. Un valor que no vale se ignora, y una clave desconocida es un error;
//   - alCambiar(fn): suscribe fn(estado, cambiadas), con cambiadas como lista de claves.
// Así cada orden llena su módulo sin editar este archivo ni los de las demás.
//
// Todas las rutas son relativas, sin «/» al principio: el sitio funciona igual en la raíz de
// Cloudflare Pages que en /sarcae-lat/ de GitHub Pages.

import * as ficha from "./js/ficha.js";
import * as maqueta from "./js/maqueta.js";
import * as mapa from "./js/mapa.js";
import * as recorrido from "./js/recorrido.js";
import * as asistente from "./js/asistente.js";
// sol.js no es un módulo con iniciar: es la función pura de la posición del sol, que importa
// la maqueta. Se importa aquí para que entre en la primera pantalla con los demás.
import "./js/sol.js";

const MODULOS = { ficha, maqueta, mapa, recorrido, asistente };

const REGISTROS = ["estudiante", "docente", "direccion"];
const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
// test() convierte null en "null", que pasaría por un slug: se exige texto.
const esSlug = (v) => typeof v === "string" && SLUG.test(v);

const entero = (min, max) => (v) => {
  if (v === "" || v === null) return undefined;
  const n = Number(v);
  return Number.isInteger(n) && n >= min && n <= max ? n : undefined;
};
const opcion = (lista) => (v) => (lista.includes(v) ? v : undefined);

// El estado: cada clave, su valor por defecto y cómo se valida. La URL solo lleva escuela,
// registro y lo que no esté en su valor por defecto.
//   escuela       el slug de escuelas.json, o "ejemplo"
//   registro      estudiante, docente o direccion
//   dia           día del año, de 1 a 366, para el sol de la maqueta (105 es el 15 de abril)
//   hora          hora local, de 6 a 18, en cuartos de hora
//   capa          sombra, calor o agua
//   vista         maqueta, 2d o 3d
//   parada        el id de una parada de recorrido.json, o null para la primera
//   episodio      el índice de clima.json → episodios.lista, de 0 a 2, o null sin episodio
//   horaEpisodio  la hora local del episodio, de 0 a 23, o null
const ESTADO = {
  escuela: { defecto: null, validar: (v) => (esSlug(v) ? v : undefined) },
  registro: { defecto: "docente", validar: opcion(REGISTROS) },
  dia: { defecto: 105, validar: entero(1, 366) },
  hora: {
    defecto: 10,
    validar: (v) => {
      if (v === "" || v === null) return undefined;
      const n = Number(v);
      return Number.isFinite(n) && n >= 6 && n <= 18 && Number.isInteger(n * 4) ? n : undefined;
    },
  },
  capa: { defecto: "sombra", validar: opcion(["sombra", "calor", "agua"]) },
  vista: { defecto: "maqueta", validar: opcion(["maqueta", "2d", "3d"]) },
  parada: { defecto: null, validar: (v) => (v === null || esSlug(v) ? v : undefined) },
  episodio: { defecto: null, validar: (v) => (v === null ? v : entero(0, 2)(v)) },
  horaEpisodio: { defecto: null, validar: (v) => (v === null ? v : entero(0, 23)(v)) },
};
const SIEMPRE_EN_URL = ["escuela", "registro"];

function estadoDeLaUrl() {
  const params = new URLSearchParams(location.search);
  const estado = {};
  for (const [clave, { defecto, validar }] of Object.entries(ESTADO)) {
    const texto = params.get(clave);
    const valor = texto === null || texto === "" ? undefined : validar(texto);
    estado[clave] = valor === undefined ? defecto : valor;
  }
  return estado;
}

function urlDelEstado(estado) {
  const params = new URLSearchParams();
  for (const [clave, { defecto }] of Object.entries(ESTADO)) {
    const valor = estado[clave];
    if (valor !== null && (SIEMPRE_EN_URL.includes(clave) || valor !== defecto)) {
      params.set(clave, String(valor));
    }
  }
  return `${location.pathname}?${params}${location.hash}`;
}

// Un JSON de web/datos/, o null si falta o no se puede leer. La ruta se resuelve contra este
// archivo y no contra la página, para que no dependa de si la URL acaba en «/».
async function json(ruta) {
  try {
    const respuesta = await fetch(new URL(ruta, import.meta.url));
    return respuesta.ok ? await respuesta.json() : null;
  } catch (error) {
    console.warn(`No se pudo leer ${ruta}:`, error);
    return null;
  }
}

// La escuela que se enseña: la pedida, si existe; si no, la ancla de escuelas.json, o el
// ejemplo si ese archivo no existe. Devuelve también el aviso, si la pedida no existía.
function elegirEscuela(pedida, escuelas) {
  const lista = escuelas?.escuelas ?? [];
  if (pedida === "ejemplo" || lista.some((e) => e.slug === pedida)) return { slug: pedida };
  const porDefecto = (lista.find((e) => e.ancla) ?? lista[0])?.slug ?? "ejemplo";
  const aviso = pedida === null ? null : `No hay ninguna escuela «${pedida}». Se muestra la escuela por defecto.`;
  return { slug: porDefecto, aviso };
}

// Lo que necesita la primera pantalla (docs/contrato-datos.md). Las capas del mapa, el STL,
// la reserva del asistente y los PDF los carga cada módulo cuando se piden.
async function cargar(slug, escuelas) {
  const carpeta = `datos/${slug}/`;
  const rutas = {
    escuela: `${carpeta}escuela.json`,
    clima: `${carpeta}clima.json`,
    validacion: `${carpeta}validacion.json`,
    recorrido: `${carpeta}recorrido.json`,
    limites: "datos/comun/limites.json",
    glosario: "datos/comun/glosario.json",
    maquetaGenerica: "datos/comun/maqueta-generica.json",
    material: "material/material.json",
  };
  // El ejemplo no tiene STL (contrato de datos): no se pide, para no buscar un archivo que no
  // va a existir.
  if (slug !== "ejemplo") rutas.maquetaStl = `${carpeta}maqueta-stl.json`;
  const claves = Object.keys(rutas);
  const valores = await Promise.all(claves.map((c) => json(rutas[c])));
  const datos = { escuelas };
  claves.forEach((c, i) => { datos[c] = valores[i]; });
  datos.maquetaStl ??= null;
  return datos;
}

function textoHora(h) {
  const hh = Math.floor(h);
  const mm = Math.round((h - hh) * 60);
  return `${hh}:${String(mm).padStart(2, "0")}`;
}

// El selector de escuela: las de escuelas.json y, si es la elegida, el ejemplo.
function llenarEscuelas(select, escuelas, elegida) {
  const opciones = (escuelas?.escuelas ?? []).map((e) => [e.slug, `${e.nombre} (${e.pais})`]);
  if (elegida === "ejemplo") opciones.push(["ejemplo", "Escuela de ejemplo, con cifras ficticias"]);
  select.replaceChildren(...opciones.map(([slug, texto]) => new Option(texto, slug, false, slug === elegida)));
  select.disabled = opciones.length < 2;
}

function mostrarAvisos(avisos) {
  const caja = document.getElementById("avisos");
  const textos = avisos.filter(Boolean);
  caja.replaceChildren(...textos.map((t) => Object.assign(document.createElement("p"), { textContent: t })));
  caja.hidden = textos.length === 0;
}

// Los mandos que son estado y no de un módulo: la escuela, el registro, la hora, el día, la
// capa y la vista. Se enlazan aquí, una sola vez, para que la maqueta y el mapa no se los
// disputen; el día, la capa y la vista siguen desactivados hasta que un módulo los active.
function enlazarMandos(ctx) {
  const $ = (id) => document.getElementById(id);
  const radios = (nombre) => [...document.querySelectorAll(`input[name="${nombre}"]`)];

  $("escuela").addEventListener("change", (e) => ctx.cambiar({ escuela: e.target.value }));
  for (const nombre of ["registro", "capa", "vista"]) {
    for (const r of radios(nombre)) r.addEventListener("change", () => ctx.cambiar({ [nombre]: r.value }));
  }
  $("hora").addEventListener("input", (e) => ctx.cambiar({ hora: Number(e.target.value) }));
  $("fecha").addEventListener("change", (e) => ctx.cambiar({ dia: Number(e.target.value) }));

  const pintar = (estado) => {
    for (const nombre of ["registro", "capa", "vista"]) {
      for (const r of radios(nombre)) r.checked = r.value === estado[nombre];
    }
    const hora = textoHora(estado.hora);
    $("hora").value = String(estado.hora);
    $("hora").setAttribute("aria-valuetext", hora);
    $("hora-grande").textContent = hora;
    $("fecha").value = String(estado.dia);
  };
  ctx.alCambiar(pintar);
  pintar(ctx.estado);
}

async function arrancar() {
  let estado = estadoDeLaUrl();
  const escuelas = await json("datos/escuelas.json");
  const { slug, aviso } = elegirEscuela(estado.escuela, escuelas);
  estado.escuela = slug;
  const datos = await cargar(slug, escuelas);

  const suscritos = [];
  let urlPendiente = null;
  const ctx = {
    get estado() { return estado; },
    datos,
    cambiar(parcial) {
      const nuevo = { ...estado };
      const cambiadas = [];
      for (const [clave, valor] of Object.entries(parcial)) {
        if (!(clave in ESTADO)) throw new Error(`El estado no tiene la clave «${clave}»`);
        const valido = ESTADO[clave].validar(valor);
        if (valido !== undefined && valido !== estado[clave]) {
          nuevo[clave] = valido;
          cambiadas.push(clave);
        }
      }
      if (cambiadas.length === 0) return;
      // Otra escuela son otros datos: se carga la página de nuevo, con el resto del estado.
      if (cambiadas.includes("escuela")) {
        location.assign(urlDelEstado(nuevo));
        return;
      }
      estado = Object.freeze(nuevo);
      // La URL se escribe un momento después: arrastrar la hora la cambiaría decenas de veces
      // por segundo, y Safari limita las llamadas a history.replaceState.
      clearTimeout(urlPendiente);
      urlPendiente = setTimeout(() => history.replaceState(null, "", urlDelEstado(estado)), 250);
      for (const fn of suscritos) {
        try { fn(estado, cambiadas); } catch (error) { console.error(error); }
      }
    },
    alCambiar(fn) { suscritos.push(fn); },
  };
  estado = Object.freeze(estado);
  history.replaceState(null, "", urlDelEstado(estado));

  llenarEscuelas(document.getElementById("escuela"), escuelas, slug);
  // Con ?escuela=ejemplo, el aviso de que sus cifras son ficticias se ve siempre.
  const avisoEjemplo = slug === "ejemplo"
    ? datos.escuela?.aviso ?? "Esta es la escuela de ejemplo: sus cifras son ficticias."
    : null;
  mostrarAvisos([aviso, avisoEjemplo]);
  enlazarMandos(ctx);

  // Un módulo que falla no tumba a los demás.
  for (const [nombre, modulo] of Object.entries(MODULOS)) {
    try {
      modulo.iniciar(ctx);
    } catch (error) {
      console.error(`El módulo ${nombre} no pudo arrancar:`, error);
    }
  }
}

arrancar();
