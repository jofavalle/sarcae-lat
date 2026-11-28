# Direcciones visuales: prototipo de la decisión #20

La primera pantalla de SARCAE-LAT en las dos direcciones que se comparan en la issue #20. Las
dos comparten la composición y cambian solo los tokens de `tokens.css`:

- **A · Noche**: el instrumento sobre fondo oscuro. La maqueta flota en el centro, la
  información a la izquierda, la conversación a la derecha y los mandos abajo, con una línea
  de tiempo.
- **B · Día**: el mismo esquema en claro y cálido, como una maqueta sobre papel.

Las referencias son de NASA Space Apps y se citan en la issue: `34-percent.vercel.app/simulate`
(composición), `micro-g.pages.dev` (cifras clave, caja de preguntas con aviso de privacidad) y
`astrofire-3d.vercel.app/simulator` (paneles laterales y la línea de límites bajo la escena). De
ellas se toma la composición, no el código ni los recursos.

## Abrirlo

Desde la raíz del repositorio:

```
python -m http.server 8765 --directory web
```

y en el navegador, `http://127.0.0.1:8765/direcciones/`. Con `?direccion=dia` abre la B. Hace
falta un servidor porque la página lee dos JSON, y `file://` no lo permite.

## Lo que es y lo que no

- **Las cifras son de ejemplo** (`ficha-ejemplo.json`): no son de la escuela ancla. Se
  sustituyen por las del contrato de datos, y los indicadores, por los de la #22.
- **La maqueta es un esquema** (`escuela-esquema.json`) de una escuela tipo, en metros: dos
  pabellones de aulas, dirección, sanitarios, techo del patio, cancha y árboles. Solo volúmenes,
  sin distribución interior, puertas ni accesos. Se sustituye por Google Open Buildings y
  NASADEM cuando estén en el repositorio.
- **Lo que sí se calcula** es geometría: la posición del sol con las ecuaciones aproximadas de
  la NOAA para la latitud de El Salvador (13,7° N, UTC-6), las sombras de cada volumen y qué
  parte del patio queda a la sombra, con una muestra cada medio metro.
- **La maqueta 3D** usa MapLibre GL JS 6.20.0 de `web/vendor/` y solo se carga al pulsar su
  botón (ADR-001). Muestra los volúmenes con la luz del sol de la hora elegida; las capas de
  sombra, calor y agua están en la vista esquemática, en SVG.
- **El asistente** no está conectado: el formulario solo enseña cómo se verá y no envía nada.

## Accesibilidad

- Contraste de texto, medido con la fórmula de WCAG 2.2 sobre el fondo y sobre los paneles:
  A · Noche, de 8,4 a 18,1 a 1; B · Día, de 4,9 a 15,1 a 1. El texto sobre el botón de acción,
  8,6 (A) y 5,6 (B).
- Nada depende solo del color: la capa de calor rotula cada superficie con su temperatura y
  marca con trama las de 60 °C o más; el agua lleva flechas y rótulos.
- Los controles son elementos nativos (`<input type="radio">`, `<input type="range">`,
  `<select>`, `<button>`), manejables con teclado. La hora anuncia su momento ("10:00,
  recreo").
- La maqueta tiene un `<desc>` que se actualiza con la hora, la sombra del patio y la parada, y
  el recorrido entero está también en texto, bajo el escenario.
- Con movimiento reducido no se anima nada.

## Presupuesto

Medido con `python -m src.presupuesto web/direcciones --limite-kb 70`: 21,9 KB con `gzip -9`
entre HTML, CSS, JavaScript y los dos JSON. De ellos, `maqueta3d.js` (2,0 KB) solo se carga con
la 3D. Las cuatro fuentes woff2 de `web/fonts/` suman 76,4 KB (ADR-001: 80 KB). La primera
pantalla queda en unos 96 KB, por debajo de los 150 KB de la ADR-001.
