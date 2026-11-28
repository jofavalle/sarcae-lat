// La ficha de la escuela (orden #64, etapa 2): su nombre y su lugar, el clima de la zona con
// la serie anual, los límites en el registro elegido, las fuentes, el glosario y el material.
//
// Puntos de montaje: #ficha-escuela y #ficha-lecturas, en la primera pantalla, y las
// secciones #clima, #limites, #fuentes, #glosario y #material. Su CSS es estilo/ficha.css.
//
// Las cifras llegan redondeadas desde web/datos/ (docs/contrato-datos.md): aquí solo se les
// pone la coma decimal. Nada se recalcula: los promedios de cada periodo vienen en clima.json.

const SVG = "http://www.w3.org/2000/svg";
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
  "septiembre", "octubre", "noviembre", "diciembre"];
const LICENCIAS = {
  "CC0-1.0": "CC0 1.0",
  "CC-BY-4.0": "CC BY 4.0",
  "dominio-publico": "dominio público",
  cita: "se citan sus criterios, sin copiar nada",
};
const REGISTROS = { estudiante: "Estudiante", docente: "Docente", direccion: "Dirección" };
const ICONOS = {
  calor: '<path d="M10 13.2V4a2 2 0 1 0-4 0v9.2a3.4 3.4 0 1 0 4 0Z"/><path d="M8 9v5"/>',
  lluvia: '<path d="M8 2s-4.5 5-4.5 8.5a4.5 4.5 0 0 0 9 0C12.5 7 8 2 8 2Z"/>',
};

// La coma decimal y el signo menos tipográfico. Nada más: la cifra ya viene redondeada. Con
// `decimales`, se escribe con los que fija el contrato, porque JSON lee 5.0 como 5: toFixed
// solo da formato a una cifra que ya tiene esos decimales, no la redondea de nuevo.
export function coma(n, decimales) {
  const texto = decimales === undefined ? String(n) : n.toFixed(decimales);
  return texto.replace(".", ",").replace(/^-/, "−");
}
const d1 = (n) => coma(n, 1);

function el(nombre, attrs = {}, ...hijos) {
  const n = document.createElement(nombre);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "texto") n.textContent = v;
    else n.setAttribute(k, v);
  }
  n.append(...hijos);
  return n;
}

function svg(nombre, attrs = {}, padre) {
  const n = document.createElementNS(SVG, nombre);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
  if (padre) padre.appendChild(n);
  return n;
}

function icono(nombre) {
  const n = svg("svg", { class: `icono icono-${nombre}`, viewBox: "0 0 16 16", "aria-hidden": "true" });
  n.innerHTML = ICONOS[nombre];
  return n;
}

// Una escuela con datos provisionales lleva `datos_ficticios` en escuela.json o clima.json
// (comentario de la #61 en la #64). Mientras esté, el aviso va junto a las cifras, en los tres
// registros y también al imprimir. Sin el campo, no se enseña nada.
const AVISO_FICTICIOS = "Cifras provisionales y ficticias: la serie de ERA5 de esta escuela todavía no está descargada.";

function notasFicticias(datos) {
  const notas = [datos.escuela?.datos_ficticios, datos.clima?.datos_ficticios]
    .filter((t) => typeof t === "string" && t.trim() !== "");
  return [...new Set(notas)];
}

// desplegable: en la primera pantalla, la nota va en un <details> para no alargar la columna.
function avisoFicticios(notas, { desplegable }) {
  const caja = el("div", { class: "aviso-datos", role: "note" },
    el("p", {}, el("strong", { texto: "Aviso: " }), AVISO_FICTICIOS));
  const textos = notas.map((n) => el("p", { class: "nota", texto: n }));
  if (desplegable) caja.append(el("details", {}, el("summary", { texto: "Qué es ficticio" }), ...textos));
  else caja.append(...textos);
  return caja;
}

function pintarAviso(ctx) {
  const caja = document.getElementById("ficha-aviso");
  const notas = notasFicticias(ctx.datos);
  caja.replaceChildren(...(notas.length ? [avisoFicticios(notas, { desplegable: true })] : []));
  caja.hidden = notas.length === 0;
}

const falta = (que) => el("p", { class: "hueco", texto: `Todavía no hay ${que} para esta escuela.` });
const url = (ruta) => new URL(`../${ruta}`, import.meta.url).href;

// La identidad: escuela.json si está; si no, su fila de escuelas.json.
function identidad(ctx) {
  const { escuela, escuelas } = ctx.datos;
  return escuela ?? escuelas?.escuelas?.find((e) => e.slug === ctx.estado.escuela) ?? null;
}

function pintarEscuela(ctx) {
  const caja = document.getElementById("ficha-escuela");
  const e = identidad(ctx);
  const punto = el("span", { class: "punto", "aria-hidden": "true" });
  if (!e) {
    caja.replaceChildren(punto, el("span", { texto: "Escuela sin datos" }));
    return;
  }
  const partes = [el("span", { texto: `${e.nombre} · ${e.municipio}, ${e.pais}` })];
  // Fuera de El Salvador, los criterios del manual salvadoreño son una referencia de
  // comparación (#16), y la ficha lo declara.
  const criterios = e.criterios ?? (e.iso_pais === "SV" ? "propios" : "referencia de comparación");
  if (criterios === "referencia de comparación") {
    partes.push(el("span", { class: "insignia", texto: "Referencia de comparación" }));
  }
  caja.replaceChildren(punto, ...partes);
}

// Los tres indicadores de la #22: horas sobre 27 °C, el p99 de la lluvia diaria y los días que
// lo superan, con su valor en 1961–1990 y en 1996–2025. El p99 es un umbral fijo de 1961–1990,
// así que no tiene valor de 1996–2025 (ahora: null).
function indicadores(clima) {
  const { calor, lluvia } = clima;
  const p99 = lluvia.p99;
  return [
    {
      icono: "calor",
      nombre: `Horas al año por encima de ${coma(calor.umbral.valor)} ${calor.umbral.unidad} en horario de clase`,
      antes: `${d1(calor.horas_1961_1990)} ${calor.unidad}`,
      ahora: `${d1(calor.horas_1996_2025)} ${calor.unidad}`,
    },
    {
      icono: "lluvia",
      nombre: `Lluvia de un día muy lluvioso: el percentil 99 de ${p99.periodo[0]}–${p99.periodo[1]}`,
      antes: `${d1(p99.valor)} ${p99.unidad}`,
      ahora: null,
    },
    {
      icono: "lluvia",
      nombre: `Días al año con más lluvia que ese umbral`,
      antes: `${d1(lluvia.dias_1961_1990)} ${lluvia.unidad}`,
      ahora: `${d1(lluvia.dias_1996_2025)} ${lluvia.unidad}`,
    },
  ];
}

function pintarLecturas(ctx) {
  const dl = document.getElementById("ficha-lecturas");
  const { clima } = ctx.datos;
  if (!clima) {
    dl.replaceChildren(el("div", {}, el("dt", { texto: "Clima de la zona" }),
      el("dd", { class: "hueco", texto: "Todavía no hay datos del clima para esta escuela." })));
    return;
  }
  dl.replaceChildren(...indicadores(clima).map((i) => el("div", {},
    el("dt", {}, icono(i.icono), i.nombre),
    el("dd", {}, el("span", { texto: i.ahora ?? i.antes }),
      // El espacio del principio separa la cifra y su periodo para el lector de pantalla.
      el("span", { class: "periodo", texto: i.ahora ? ` en 1996–2025; ${i.antes} en 1961–1990` : " de 1961–1990" })),
  )));
}

// Una escala con 3 o 4 marcas redondas (1, 2 o 5 por una potencia de 10) desde 0.
function escala(maximo) {
  if (maximo <= 0) return { tope: 1, paso: 1 };
  const bruto = maximo / 4;
  const pot = 10 ** Math.floor(Math.log10(bruto));
  const paso = [1, 2, 5, 10].map((m) => m * pot).find((p) => p >= bruto);
  return { tope: Math.ceil(maximo / paso) * paso, paso };
}

// La serie anual en barras, hecha a mano en SVG y dibujada al ancho real de su caja, para que
// el texto no encoja en un móvil. Los promedios de cada periodo son los de clima.json.
function dibujarSerie(figura, { serie, clave, unidad, clase, promedios, titulo }) {
  const ancho = Math.max(280, figura.querySelector(".lamina").clientWidth || 640);
  const alto = 200;
  const m = { izq: 40, der: 8, arr: 22, aba: 24 };
  const anios = serie.map((p) => p.anio);
  const primero = anios[0];
  const n = anios.length;
  const banda = (ancho - m.izq - m.der) / n;
  const { tope, paso } = escala(Math.max(...serie.map((p) => p[clave]), ...promedios.map((p) => p.valor)));
  const y = (v) => m.arr + (alto - m.arr - m.aba) * (1 - v / tope);
  const x = (anio) => m.izq + (anio - primero) * banda;

  const s = svg("svg", { class: "serie", width: ancho, height: alto, viewBox: `0 0 ${ancho} ${alto}`, role: "img", "aria-labelledby": `${figura.id}-t ${figura.id}-d` });
  svg("title", { id: `${figura.id}-t` }, s).textContent = titulo;
  svg("desc", { id: `${figura.id}-d` }, s).textContent =
    `Una barra por año, de ${primero} a ${anios[n - 1]}. ` +
    promedios.map((p) => `Promedio de ${p.desde}–${p.hasta}: ${d1(p.valor)} ${unidad}.`).join(" ") +
    " Todas las cifras están en la tabla de debajo.";

  const ejes = svg("g", { class: "ejes", "aria-hidden": "true" }, s);
  for (let v = 0; v <= tope + 1e-9; v += paso) {
    svg("line", { x1: m.izq, x2: ancho - m.der, y1: y(v), y2: y(v), class: v === 0 ? "base" : "rejilla" }, ejes);
    svg("text", { x: m.izq - 6, y: y(v) + 4, "text-anchor": "end" }, ejes).textContent = coma(Math.round(v * 100) / 100);
  }
  for (const anio of anios.filter((a) => a % 20 === 0)) {
    svg("text", { x: x(anio) + banda / 2, y: alto - 6, "text-anchor": "middle" }, ejes).textContent = anio;
  }

  const barras = svg("g", { class: `barras ${clase}` }, s);
  const hueco = banda > 4 ? 1 : 0;
  for (const p of serie) {
    const v = p[clave];
    const r = svg("rect", { x: x(p.anio) + hueco / 2, y: y(v), width: Math.max(1, banda - hueco), height: Math.max(0, y(0) - y(v)) }, barras);
    svg("title", {}, r).textContent = `${p.anio}: ${coma(v)} ${unidad}`;
  }

  // Los promedios: una línea de trazos sobre los años de su periodo, rotulada.
  const medias = svg("g", { class: "promedios" }, s);
  for (const p of promedios) {
    const x1 = x(p.desde);
    const x2 = x(p.hasta) + banda;
    svg("line", { x1, x2, y1: y(p.valor), y2: y(p.valor) }, medias);
    const t = svg("text", { x: (x1 + x2) / 2, y: y(p.valor) - 6, "text-anchor": "middle" }, medias);
    t.textContent = `${p.desde}–${p.hasta}: ${d1(p.valor)}`;
  }
  figura.querySelector(".lamina").replaceChildren(s);
}

function figuraSerie(id, opciones) {
  // La lámina tiene el alto del gráfico fijado en ficha.css: dibujar dentro no cambia su
  // tamaño, y el observador no se vuelve a disparar por el propio dibujo.
  const lamina = el("div", { class: "lamina" });
  const figura = el("figure", { class: "grafico", id },
    el("figcaption", { class: "rotulo", texto: opciones.titulo }), lamina);
  // pintar() dibuja si el ancho de la lámina cambió. pintarClima la llama en cuanto la figura
  // está en la página, y el observador en cada cambio de ancho. Dibujar dentro de la lámina no
  // cambia su tamaño (alto fijo y overflow oculto), así que el observador no entra en bucle.
  let ultimo = 0;
  const pintar = () => {
    const w = Math.round(lamina.clientWidth);
    if (w > 0 && w !== ultimo) {
      ultimo = w;
      dibujarSerie(figura, opciones);
    }
  };
  new ResizeObserver(pintar).observe(lamina);
  return { figura, pintar };
}

function pintarClima(ctx) {
  const seccion = document.getElementById("clima");
  const { clima } = ctx.datos;
  const cabeza = [...seccion.querySelectorAll(":scope > h2, :scope > .entradilla")];
  if (!clima) {
    seccion.replaceChildren(...cabeza, falta("datos del clima"));
    return;
  }
  const { calor, lluvia, correccion } = clima;

  const filas = indicadores(clima).map((i) => el("tr", {},
    el("th", { scope: "row" }, icono(i.icono), i.nombre),
    el("td", { class: "num", texto: i.antes }),
    el("td", { class: i.ahora ? "num" : "num secundario", texto: i.ahora ?? "el mismo umbral" })));
  const tabla = el("table", { class: "tabla" },
    el("caption", { class: "visualmente-oculto", texto: "Indicadores de calor y de lluvia de la zona, en los dos periodos" }),
    el("thead", {}, el("tr", {},
      el("th", { scope: "col", texto: "Indicador" }),
      el("th", { scope: "col", class: "num", texto: "1961–1990" }),
      el("th", { scope: "col", class: "num", texto: "1996–2025" }))),
    el("tbody", {}, ...filas));

  const notas = el("p", { class: "nota", texto:
    `Horario de clase: ${calor.horario}. La temperatura de ERA5 se corrige por la altura de la ` +
    `escuela (${d1(correccion.z_escuela.valor)} ${correccion.z_escuela.unidad}) frente a la de su celda ` +
    `(${d1(correccion.z_celda.valor)} ${correccion.z_celda.unidad}): ${d1(correccion.correccion.valor)} ${correccion.correccion.unidad}.` });

  const pm = calor.por_mes;
  const meses = el("table", { class: "tabla tabla-meses" },
    el("caption", { class: "rotulo", texto: `Horas por encima de ${coma(calor.umbral.valor)} ${calor.umbral.unidad} en horario de clase, por mes, promedio de ${pm.periodo[0]}–${pm.periodo[1]}` }),
    el("thead", {}, el("tr", {}, el("th", { scope: "col", texto: "Mes" }), el("th", { scope: "col", class: "num", texto: "Horas" }))),
    el("tbody", {}, ...pm.meses.map((x) => el("tr", {},
      el("th", { scope: "row", texto: MESES[x.mes - 1] }),
      el("td", { class: "num", texto: d1(x.horas) })))));

  const series = [
    figuraSerie("serie-calor", {
      serie: calor.serie, clave: "horas", unidad: calor.unidad, clase: "calor",
      titulo: `Horas al año por encima de ${coma(calor.umbral.valor)} ${calor.umbral.unidad} en horario de clase, de ${calor.serie[0].anio} a ${calor.serie.at(-1).anio}`,
      promedios: [
        { desde: 1961, hasta: 1990, valor: calor.horas_1961_1990 },
        { desde: 1996, hasta: 2025, valor: calor.horas_1996_2025 },
      ],
    }),
    figuraSerie("serie-lluvia", {
      serie: lluvia.serie, clave: "dias", unidad: lluvia.unidad, clase: "lluvia",
      titulo: `Días al año con más de ${d1(lluvia.p99.valor)} ${lluvia.p99.unidad} de lluvia, de ${lluvia.serie[0].anio} a ${lluvia.serie.at(-1).anio}`,
      promedios: [
        { desde: 1961, hasta: 1990, valor: lluvia.dias_1961_1990 },
        { desde: 1996, hasta: 2025, valor: lluvia.dias_1996_2025 },
      ],
    }),
  ];
  const graficos = el("div", { class: "graficos" }, ...series.map((s) => s.figura));

  // La tabla alternativa de los dos gráficos: un año por fila.
  const dias = new Map(lluvia.serie.map((p) => [p.anio, p.dias]));
  const serie = el("details", { class: "serie-tabla" },
    el("summary", { texto: "Ver la serie anual en una tabla" }),
    el("table", { class: "tabla" },
      el("caption", { class: "visualmente-oculto", texto: "Serie anual de los dos indicadores" }),
      el("thead", {}, el("tr", {},
        el("th", { scope: "col", texto: "Año" }),
        el("th", { scope: "col", class: "num", texto: `Horas por encima de ${coma(calor.umbral.valor)} ${calor.umbral.unidad}` }),
        el("th", { scope: "col", class: "num", texto: `Días con más de ${d1(lluvia.p99.valor)} ${lluvia.p99.unidad}` }))),
      el("tbody", {}, ...calor.serie.map((p) => el("tr", {},
        el("th", { scope: "row", texto: String(p.anio) }),
        el("td", { class: "num", texto: coma(p.horas) }),
        el("td", { class: "num", texto: dias.has(p.anio) ? coma(dias.get(p.anio)) : "—" }))))));

  const ficticias = notasFicticias(ctx.datos);
  const aviso = ficticias.length ? [avisoFicticios(ficticias, { desplegable: false })] : [];
  seccion.replaceChildren(...cabeza, ...aviso, tabla, notas,
    el("h3", { texto: "Cómo ha cambiado desde 1940" }), graficos, serie,
    el("h3", { texto: "En qué meses hace más calor en horario de clase" }), meses);
  for (const s of series) s.pintar();
}

function pintarLimites(ctx) {
  const { limites } = ctx.datos;
  // Sin limites.json se quedan los límites escritos en index.html.
  if (!limites) return;
  const registro = ctx.estado.registro;
  const lista = document.querySelector("#limites .lista-limites");
  lista.replaceChildren(...limites.limites.map((l) => el("li", { id: `limite-${l.id}` },
    el("strong", { texto: l.titulo }), ". ", l[registro])));
  const rotulo = document.getElementById("limites-registro");
  rotulo.textContent = `Explicados para ${REGISTROS[registro].toLowerCase()}.`;
}

// Las fuentes de todos los JSON cargados, sin repetir, con lo que alimenta cada una.
function pintarFuentes(ctx) {
  const PARA = {
    escuelas: "la ubicación de la escuela", escuela: "la escuela y su altitud", clima: "el clima de la zona",
    validacion: "la comparación con una estación", recorrido: "el recorrido",
    limites: "los límites", glosario: "el glosario", maquetaGenerica: "la maqueta genérica",
    material: "el material para imprimir", maquetaStl: "la maqueta en STL",
  };
  const vistas = new Map();
  const anotar = (f, para) => {
    const clave = `${f.nombre}|${f.version ?? ""}|${f.url ?? ""}`;
    if (!vistas.has(clave)) vistas.set(clave, { ...f, para: [] });
    const v = vistas.get(clave);
    if (!v.para.includes(para)) v.para.push(para);
  };
  for (const [nombre, json] of Object.entries(ctx.datos)) {
    if (!json || nombre === "escuelas") continue;
    for (const f of json.fuentes ?? []) anotar(f, PARA[nombre] ?? nombre);
  }
  // escuelas.json no lleva fuentes: la de las coordenadas va en cada escuela.
  const fila = ctx.datos.escuelas?.escuelas?.find((e) => e.slug === ctx.estado.escuela);
  if (fila?.fuente_coordenadas) {
    const f = fila.fuente_coordenadas;
    anotar({ nombre: f.nombre, version: `consultada el ${f.fecha_consulta}`, licencia: f.licencia, url: f.url }, PARA.escuelas);
  }

  const cuerpo = document.querySelector("#fuentes tbody");
  const tipografia = cuerpo.querySelector("tr[data-fija]");
  const filas = [...vistas.values()].map((f) => {
    let version = String(f.version ?? "").replace(/^(sha256:[0-9a-f]{12})[0-9a-f]+$/, "$1…");
    if (/^[0-9.]+$/.test(version)) version = `versión ${version}`;
    const nombre = f.url ? el("a", { href: f.url, texto: f.nombre }) : f.nombre;
    return el("tr", {},
      el("td", {}, nombre, version ? el("span", { class: "secundario", texto: ` (${version})` }) : ""),
      el("td", { texto: f.licencia ? LICENCIAS[f.licencia] ?? f.licencia : "sin licencia declarada" }),
      el("td", { texto: f.para.join(", ") }));
  });
  cuerpo.replaceChildren(...filas, tipografia);
  document.getElementById("fuentes-hueco")?.remove();
}

function pintarGlosario(ctx) {
  const seccion = document.getElementById("glosario");
  const h2 = seccion.querySelector("h2");
  const { glosario } = ctx.datos;
  if (!glosario) {
    seccion.replaceChildren(h2, el("p", { class: "hueco", texto: "Todavía no hay glosario." }));
    return;
  }
  seccion.replaceChildren(h2, el("dl", { class: "glosario" },
    ...glosario.terminos.flatMap((t) => [el("dt", { texto: t.termino }), el("dd", { texto: t.definicion })])));
}

// Los PDF de material.json y la maqueta en STL, solo si existen.
function pintarMaterial(ctx) {
  const seccion = document.getElementById("material");
  const { material, maquetaStl } = ctx.datos;
  const slug = ctx.estado.escuela;
  const enlaces = [];
  for (const pdf of material?.pdfs?.filter((p) => p.escuela === slug) ?? []) {
    enlaces.push(el("li", {}, el("a", { href: url(`material/${pdf.archivo}`), texto: `Ficha para imprimir: ${REGISTROS[pdf.registro] ?? pdf.registro}` }),
      el("span", { class: "secundario", texto: ` (PDF, ${pdf.paginas} páginas, ${d1(pdf.kb)} KB)` })));
  }
  if (maquetaStl) {
    enlaces.push(el("li", {}, el("a", { href: url(`datos/${slug}/maqueta.stl`), download: "", texto: "Maqueta para imprimir en 3D" }),
      el("span", { class: "secundario", texto: ` (STL, escala ${maquetaStl.escala}, ${coma(maquetaStl.lado_mm)} mm de lado). ${maquetaStl.limite}` })));
  }
  seccion.hidden = enlaces.length === 0;
  if (enlaces.length) {
    seccion.replaceChildren(seccion.querySelector("h2"), el("ul", { class: "lista-material" }, ...enlaces));
  }
}

export function iniciar(ctx) {
  pintarEscuela(ctx);
  pintarAviso(ctx);
  pintarLecturas(ctx);
  pintarClima(ctx);
  pintarLimites(ctx);
  pintarFuentes(ctx);
  pintarGlosario(ctx);
  pintarMaterial(ctx);
  ctx.alCambiar((estado, cambiadas) => {
    if (cambiadas.includes("registro")) pintarLimites(ctx);
  });
}
