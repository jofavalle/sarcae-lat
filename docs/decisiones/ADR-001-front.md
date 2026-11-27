# ADR-001: el front de SARCAE-LAT

- **Fecha:** 2026-11-27
- **Estado:** propuesta. Pasa a "aceptada" cuando se fusiona.

## Contexto

SARCAE-LAT muestra a estudiantes, docentes y dirección de escuelas públicas de América Latina la
ficha de su escuela, un mapa con capas de calor y agua, y una maqueta digital interactiva con el
relieve y los edificios en volumen (`docs/PLAN.md`, sección 6). Esta ADR cierra la decisión 3
del brief, el stack del front, con lo que la sección 11 deja a esta ADR: el alojamiento y el
presupuesto de carga.

Lo que condiciona la decisión:

- **Equipos y conexiones.** Móvil y escritorio, con conexiones lentas y equipos modestos en
  mente. Accesibilidad WCAG 2.2 AA, y la maqueta 3D nunca es el único canal: lo que enseña está
  también en texto, en el mapa y en la ficha (sección 10).
- **Rendimiento.** La primera pantalla es ligera, y el mapa y la maqueta se cargan solo cuando
  se piden (sección 11).
- **Sin servicios en vivo.** La demo no consulta servicios en vivo, salvo el asistente
  (sección 4). No se versionan extractos de OpenStreetMap, que son ODbL ("Lo que no se usa").
- **Reproducibilidad.** El jurado tiene que poder abrir y reproducir la herramienta sin
  instalar nada más que lo que pide el README.
- **El asistente.** Su clave vive en el servidor, nunca en el navegador, con un límite de
  peticiones (sección 8).
- **El plazo.** La entrega es el domingo 29 de noviembre de 2026 a las 11:00 en El Salvador:
  cuanto menos haya que montar, mejor.

## Decisión

| Capa | Elección | Licencia |
|---|---|---|
| Lenguaje y estructura | HTML, CSS y JavaScript sin framework ni paso de build, con módulos ES nativos | no aplica |
| Diseño | Tokens en `tokens.css`: color por rol, escala tipográfica, espaciado con base de 4 px, radios y movimiento. Elementos nativos primero: `<button>`, `<dialog>`, `<details>`, `<select>`, `<table>` | MIT, código propio |
| Tipografía | Dos familias como máximo, en woff2 servidas desde el sitio, con su licencia al lado. Ni Inter, ni Roboto, ni Arial, ni la fuente del sistema como identidad | SIL OFL 1.1 |
| Gráficos | SVG hecho a mano | MIT, código propio |
| Datos | JSON estático versionado, generado por Python. La interfaz no recalcula lo que ya calculó Python | CC BY 4.0, datos propios; los de terceros, con la suya |
| Mapa y maqueta | MapLibre GL JS 6.20.0, la única biblioteca. Se sirve como archivo desde el sitio, no desde un CDN, y se carga solo al abrir el mapa o la maqueta | BSD-3-Clause |
| Mapa base | Opción (a): sin OpenStreetMap. Relieve sombreado, cobertura del suelo y edificios propios, servidos desde el sitio | la de cada fuente |
| Exportación a STL | La genera Python y se sirve como archivo. La biblioteca se elige en la orden de la maqueta | por decidir |
| Asistente | Una Function de Cloudflare Pages guarda la clave y limita las peticiones. Su interfaz no depende del proveedor, que sigue abierto (decisión 6 del brief) | MIT, código propio |
| Alojamiento | Cloudflare Pages y, de reserva, GitHub Pages sin asistente | no aplica |
| Licencias propias | MIT para el código; CC BY 4.0 para la documentación, el material y los modelos | MIT, CC BY 4.0 |

### Por qué este stack

- **Sin framework ni build.** El sitio se abre y se reproduce sin herramientas: basta un
  servidor de archivos estáticos. Además pesa poco en conexiones lentas y equipos modestos.
- **Una sola biblioteca.** MapLibre GL JS dibuja el mapa y también la maqueta: el relieve como
  terreno 3D, los edificios como extrusiones y las capas encima. Así hay un solo formato de
  datos y una sola dependencia que auditar.
- **Servida desde el sitio, con la versión fijada.** La demo no depende de que un CDN responda,
  y lo que ve el jurado es lo que está en el repositorio. El módulo principal busca su worker al
  lado de sí mismo (`new URL('./maplibre-gl-worker.mjs', import.meta.url)`), así que basta con
  servir los dos archivos en la misma carpeta.
- **Python calcula, la interfaz enseña.** Cada número tiene un solo origen reproducible, y el
  navegador no repite cálculos.

### El mapa base: opción (a)

El mapa base se compone solo con datos que el proyecto sirve desde su propio sitio:

- el relieve sombreado, que MapLibre dibuja con su capa `hillshade` a partir de las mismas
  teselas de elevación que usa el terreno 3D;
- la cobertura del suelo, una imagen del recorte de la zona;
- los contornos y las alturas de los edificios;
- las capas de calor y agua.

Así la demo cumple la sección 4 del brief tal como está escrita, funciona sin conexión a
servicios de terceros una vez cargada, y cada capa tiene una fuente y una licencia que se citan
en el README.

### El presupuesto de carga

Los tamaños van comprimidos con `gzip -9`, en KB de 1000 bytes. La medida se escoge
conservadora: el alojamiento puede servir Brotli, que comprime más.

**La carga de MapLibre, medida** sobre los archivos de la versión 6.20.0 el 27 de noviembre de
2026:

| Archivo | Sin comprimir | `gzip -9` | `brotli -q 11`, de referencia |
|---|---|---|---|
| `dist/maplibre-gl.mjs` | 1120,7 KB | 301,6 KB | 248,7 KB |
| `dist/maplibre-gl-worker.mjs` | 556,6 KB | 158,8 KB | 131,9 KB |
| `dist/maplibre-gl.css` | 71,6 KB | 10,2 KB | 8,3 KB |
| **Total** | **1748,9 KB** | **470,6 KB** | **388,9 KB** |

**La primera pantalla, sin el mapa ni la maqueta**, como límite que el código no supera:

| Parte | Límite (`gzip -9`) |
|---|---|
| HTML y CSS, con `tokens.css` | 25 KB |
| JavaScript propio | 25 KB |
| Tipografía: dos familias como máximo, en woff2, que ya viene comprimido | 80 KB |
| Datos de la ficha (JSON) y SVG de sus gráficos | 20 KB |
| **Total** | **150 KB** |

Ciento cincuenta KB son la tercera parte de lo que pesa MapLibre por sí solo. Con una conexión
de 1 Mbit/s, la primera pantalla tarda poco más de un segundo y MapLibre unos cuatro.

**Los datos del mapa y la maqueta**, como límite por escuela: 2000 KB entre el relieve, la
cobertura del suelo, los edificios y las capas. El contrato de datos lo comprueba con los
recortes reales de la escuela ancla. Si no cabe, se baja la resolución o el área, y se cambia
esta ADR.

## Por qué no las otras

- **Svelte**, y con él cualquier framework con compilación (React, Vue): añade un paso de build
  y una cadena de herramientas que hay que instalar para reproducir el sitio, a cambio de nada
  que esta herramienta necesite.
- **Leaflet**, para el mapa: no tiene terreno 3D ni extrusiones, así que la maqueta necesitaría
  una segunda biblioteca, con su propio formato de datos.
- **Three.js** o **deck.gl**, para la maqueta: una segunda biblioteca al lado del mapa. MapLibre
  ya cubre el relieve, los volúmenes y las capas.
- **CesiumJS**: pesa bastante más que MapLibre, y sus datos de terreno y de edificios suelen
  venir de un servicio en vivo.
- **MapLibre desde un CDN**: añade un servicio en vivo y una dependencia que el proyecto no
  controla.
- **Mapa base (b), teselas de un servicio público de OpenStreetMap**: sería una segunda
  excepción a "sin servicios en vivo", sin garantía de que el servicio responda el día de la
  evaluación, y obligaría a corregir la sección 4 del brief. La opción (a) da la orientación que
  hace falta con los datos que el proyecto ya tiene.
- **Solo GitHub Pages**: no ejecuta código en el servidor, así que la clave del asistente no
  tendría dónde vivir. Por eso queda de reserva, sin asistente.

## Riesgos

- **WebGL2 es obligatorio.** MapLibre 6.20.0 pide un contexto `webgl2` y, si no lo obtiene,
  lanza "WebGL2 is required to display this map". En un equipo sin WebGL2 no hay mapa ni
  maqueta. Mitigación: la ficha, con sus gráficos en SVG y el texto de cada parada del
  recorrido, funciona sin MapLibre. Si el mapa no se puede abrir, la interfaz lo dice y remite
  a la ficha.
- **El peso de MapLibre:** 470,6 KB comprimidos. En una conexión lenta tarda varios segundos.
  Mitigación: se carga solo cuando se pide, y el botón que abre el mapa anuncia su tamaño
  aproximado.
- **El lienzo del mapa no es accesible** para un lector de pantalla. Mitigación: lo que enseñan
  el mapa y la maqueta también está en texto (sección 10 del brief), y los controles propios son
  elementos nativos manejables con teclado.
- **Edificios sobre el terreno.** Que las extrusiones se apoyen bien sobre el relieve 3D se
  comprueba con datos reales en la orden de la maqueta. Si no, la maqueta muestra el relieve
  exagerado o los edificios sobre un plano, y lo dice.
- **Límites de Cloudflare Pages**, según su documentación consultada el 27 de noviembre de 2026:
  20 000 archivos por sitio en el plan gratuito, 25 MiB por archivo, y 100 000 peticiones
  diarias en el plan gratuito, compartidas entre las Functions y los Workers de la cuenta. Las
  peticiones a archivos estáticos no cuentan. Las teselas de elevación son muchos archivos
  pequeños, y el contrato de datos cuenta cuántas salen. El asistente lleva su propio límite de
  peticiones, por debajo del de la plataforma.
- **El asistente depende de un servicio en vivo**, como ya prevé el brief. Si la Function o el
  proveedor fallan, quedan las respuestas de reserva escritas por el equipo (sección 8).

## Consecuencias

- **Para el contrato de datos**, MapLibre necesita estos formatos:
  - **Relieve:** una fuente `raster-dem` en teselas XYZ en PNG, en Web Mercator (EPSG:3857),
    con codificación `terrarium` o `mapbox` (la versión fijada admite además `custom`) y teselas
    de 256 o 512 px. Las mismas teselas alimentan el terreno 3D (`terrain`) y el sombreado
    (`hillshade`). Las genera Python a partir del modelo de elevación.
  - **Edificios:** una fuente `geojson` con polígonos en longitud y latitud (EPSG:4326, RFC
    7946), con la altura y la base de cada volumen en metros como propiedades numéricas, para
    una capa `fill-extrusion`. Solo contornos y alturas: nada de distribución interior, puertas
    ni accesos (sección 7 del brief).
  - **Cobertura del suelo y capas de calor:** una fuente `image`, un PNG con las coordenadas de
    sus cuatro esquinas, o una fuente `raster` en teselas XYZ si el área lo pide.
  - **Agua:** líneas de flujo como `geojson` para una capa `line`, o una imagen como la
    anterior.
  - **Atribución:** cada fuente lleva su texto de atribución, que MapLibre enseña en su control
    de atribución y que coincide con lo citado en el README.
- **Sin texto dentro del lienzo.** Una capa `symbol` con texto necesita glifos, que tendrían que
  servirse también desde el sitio. Las etiquetas y la leyenda van en HTML, fuera del lienzo, lo
  que además ayuda al lector de pantalla.
- **Lo que se versiona del front:** `dist/maplibre-gl.mjs`, `dist/maplibre-gl-worker.mjs`,
  `dist/maplibre-gl.css` y `LICENSE.txt` de la versión 6.20.0, juntos en una carpeta del sitio.
  El `LICENSE.txt` incluye los avisos de mapbox-gl-js v1.13 (BSD-3-Clause), glfx.js (MIT) y
  d3-color (BSD-3-Clause). El paquete trae además sus dependencias empaquetadas, todas con
  licencias permisivas (ISC, MIT, BSD-2-Clause, BSD-3-Clause, MIT o Apache-2.0). El README las
  cita cuando el front entre en el repositorio.
- **El presupuesto se comprueba:** la orden que construya la primera pantalla mide sus KB con
  `gzip -9` contra las tablas de arriba. Cambiar un límite es cambiar esta ADR.
- **Cambiar de versión de MapLibre** es cambiar esta ADR: la licencia y los tamaños se vuelven
  a medir sobre los archivos de la versión nueva.
- **La sección 12 del brief:** la decisión 3 se marca como cerrada después de fusionar esta ADR
  y la orden de licencias.
