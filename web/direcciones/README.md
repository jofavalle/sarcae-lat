# Direcciones visuales: prototipo de la decisión #20

La primera pantalla de SARCAE-LAT en las dos direcciones que se comparan en la issue #20. Las
dos comparten la composición y cambian solo los tokens de `tokens.css`:

- **A · Noche**: azul noche profundo con un halo, como el cielo sobre la maqueta. La maqueta va
  al centro, la lectura a la izquierda, la conversación a la derecha y los mandos debajo.
- **B · Día**: la misma composición sobre papel cálido, con luz de mañana.

La composición viene de `34-percent.vercel.app/simulate` (NASA Space Apps): el modelo al centro y
los mandos alrededor. De `micro-g.pages.dev` viene la caja de preguntas con aviso de privacidad, y
de `astrofire-3d.vercel.app/simulator`, la línea de límites. Se toma la composición, no el código
ni los recursos.

**El criterio de estilo** (revisiones del 2026-11-28): atractivo para estudiantes y docentes, sin
sobresaturar, y sin parecer un panel de indicadores genérico. La referencia que no gusta es un
tablero de ventas de Geckoboard: cifras enormes con rótulos diminutos en mosaicos oscuros,
minigráficos decorativos y emojis. Una versión intermedia, sobria y sin halos, resultó demasiado
formal. Por eso aquí:

- **Fondo y paneles:** halo de fondo, paneles de cristal con desenfoque y esquinas suaves.
- **Color:** un acento cálido solo para acciones y selección. El calor y el agua tienen color
  solo en los datos.
- **Cifras:** van en filas con su rótulo y un icono pequeño (termómetro, gota), o en una tabla;
  nunca en mosaicos.
- **Detalles que explican algo:**
  - la línea de tiempo pinta el ciclo del día, y su tirador es el sol;
  - la brújula solar sitúa el sol en el cielo;
  - las paradas llevan su número en un círculo.
- **Tipografía:** rótulos en minúscula inicial. IBM Plex Mono solo para la lectura de la hora.

## Las tres vistas

- **Maqueta**: SVG isométrico, la vista ligera de la primera pantalla. Calcula el sol, las
  sombras y la parte del patio que queda a la sombra. Tiene tres capas: sombra, calor de
  superficie y agua de lluvia.
- **Mapa 2D**: la escuela desde arriba, con las sombras del sol de la hora elegida, el recorrido
  del agua y una escala.
  - Se abre con la escuela llenando la vista.
  - Con la capa de calor, el encuadre se abre para enseñar los cuadros de 100 m del entorno
    (700 × 500 m en total), con el de la escuela en trazos. La leyenda de clases va en HTML.
  - Arrastrar desplaza el mapa, y no gira.
- **3D**: los volúmenes del esquema extruidos, con la luz del sol de la hora elegida.
  - Arrastrar con el botón principal gira (horizontal) e inclina (vertical) la maqueta alrededor
    de su centro. La rueda o el pellizco acercan.
  - Los botones "Girar" y "Vista inicial" hacen lo mismo sin arrastrar.

El mapa 2D y la 3D usan MapLibre GL JS 6.20.0 de `web/vendor/` y solo se cargan al pedirlos
(ADR-001). No hay mapa base ni texto dentro del lienzo.

**La capa de calor respeta lo que mide Landsat:** cuadros de 100 m, servidos a 30 m. Una
escuela cabe entera en uno, así que la maqueta no reparte temperaturas por techo: tiñe todo el
terreno con un solo valor. La comparación entre zonas del entorno va en el mapa 2D (#30).

## Abrirlo

Desde la raíz del repositorio:

```
python -m http.server 8765 --directory web
```

y en el navegador, `http://127.0.0.1:8765/direcciones/`. Con `?direccion=dia` se abre la B.
Hace falta un servidor porque la página lee dos JSON, y `file://` no lo permite.

## Lo que es y lo que no

- **Las cifras son de ejemplo** (`ficha-ejemplo.json`, y los cuadros de calor de
  `escuela-esquema.json`): no son de la escuela ancla. Se sustituyen por las del contrato de
  datos, y los indicadores, por los de la #22.
- **La maqueta es un esquema** (`escuela-esquema.json`) de una escuela tipo, en metros: dos
  pabellones de aulas, dirección, sanitarios, techo del patio, cancha y árboles. Solo
  volúmenes, sin distribución interior, puertas ni accesos. Se sustituye por Google Open
  Buildings y NASADEM cuando estén en el repositorio.
- **Lo que sí se calcula es geometría:**
  - la posición del sol, con las ecuaciones aproximadas de la NOAA para la latitud de El
    Salvador (13,7° N, UTC-6);
  - las sombras de cada volumen;
  - la parte del patio que queda a la sombra, con una muestra cada medio metro.
- **El asistente** no está conectado: el formulario solo enseña cómo se verá, y no envía nada.

## Accesibilidad

- **Contraste**, medido con la fórmula de WCAG 2.2:
  - texto secundario sobre el fondo: 9,2 a 1 en A y 6,0 en B;
  - texto sobre el botón de acción: 9,7 en A y 5,3 en B;
  - lo que flota sobre la escena (brújula, ayuda del mapa y botones) usa un cristal con
    opacidad 0,9: su texto queda en 4,7 a 1 o más sobre el color más claro o más oscuro que
    pueda tener debajo (un muro, el cuadro de calor más intenso).
- **Nada depende solo del color:**
  - en la maqueta, el cuadro de calor lleva su valor escrito;
  - en el mapa 2D, la leyenda HTML da las clases, y una tabla desplegable bajo los mandos da el
    valor de cada uno de los 35 cuadros, con el de la escuela marcado con texto;
  - el agua lleva flechas y rótulos.
- **Controles nativos** (`<input type="radio">`, `<input type="range">`, `<select>`,
  `<button>`), manejables con teclado. La hora anuncia su momento ("10:00, el recreo").
- **Texto de la maqueta:** tiene un `<desc>` que se actualiza con la hora, la sombra del patio,
  la capa y la parada. El recorrido entero está también en texto, bajo el escenario.
- **Movimiento reducido:** el agua no se anima, y los cambios de cámara del mapa son inmediatos.
- **Sin WebGL2:** el mapa y la 3D no se abren, y la interfaz lo dice. La maqueta y la ficha
  siguen disponibles.

## Presupuesto

Medido con `python -m src.presupuesto web/direcciones --limite-kb 70`: 31,1 KB con `gzip -9`
para toda la carpeta. De ellos, `mapa.js` (4,7 KB) solo se carga con el mapa o la 3D, y el
`README.md` (3,0 KB) no lo carga la página.

Las cuatro fuentes woff2 de `web/fonts/` suman 76,4 KB (límite de la ADR-001: 80 KB). La primera
pantalla queda en unos 100 KB, por debajo de los 150 KB de la ADR-001.
