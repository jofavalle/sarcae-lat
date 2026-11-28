# Contrato de datos del sitio

Qué archivos lee el sitio de `web/datos/`, qué orden produce cada uno y qué lleva cada
campo. Python calcula y la interfaz enseña (ADR-001): los números llegan redondeados, y la
interfaz solo les pone la coma decimal.

Esta es la versión 1 del contrato. La comprueba `python -m src.contrato`, que se describe al
final, y el ejemplo de `web/datos/ejemplo/` la cumple.

## Los archivos

| Archivo | Lo produce | Se carga |
|---|---|---|
| `web/datos/escuelas.json` | la orden #57 | en la primera pantalla |
| `web/datos/<slug>/escuela.json` y `clima.json` | la de los indicadores de la 88118 (#61) y la de las réplicas (#69) | en la primera pantalla |
| `web/datos/<slug>/validacion.json` | la que lleva a la ficha la métrica de la #54 y la #56 (#71) | en la primera pantalla |
| `web/datos/<slug>/recorrido.json` | la del recorrido de la 88118 (#67) y la de las réplicas (#70) | en la primera pantalla |
| `web/datos/<slug>/relieve/relieve.json` y `relieve/{z}/{x}/{y}.png` | la del relieve (#60) | con el mapa |
| `web/datos/<slug>/edificios.geojson`, `calor.geojson`, `cobertura.png` y `capas.json` | la de Earth Engine (#62) | con el mapa |
| `web/datos/<slug>/agua.geojson` | la de la escorrentía (#63) | con el mapa |
| `web/datos/<slug>/maqueta.stl` y `maqueta-stl.json` | la del STL (#75) | a petición |
| `web/datos/comun/limites.json` y `glosario.json` | la de los manifiestos y el material (#59) | en la primera pantalla |
| `web/datos/comun/maqueta-generica.json` | la de la maqueta genérica (#65) | en la primera pantalla |
| `web/datos/comun/reserva.json` | la del asistente (#73) | a petición |
| `web/material/material.json` y los PDF | la del material para imprimir (#74) | a petición |
| `web/datos/ejemplo/{escuela,clima,validacion,recorrido}.json` | esta orden (#58) | con `?escuela=ejemplo` |
| las capas del mapa en `web/datos/ejemplo/` | la del mapa (#66) | con el mapa |

`<slug>` es el de `escuelas.json`: `sv-88118`, `co-nicolas-esguerra` y
`ve-rafael-maria-baralt`. Al fusionarse, cada orden enlaza aquí el número de su PR; este
documento no se reescribe por eso.

`maqueta-stl.json` y `material.json` son pequeños, y la ficha los lee para enlazar el STL y
los PDF. No entran en los 20 KB de datos del contrato: los cuenta la lista de la primera
pantalla de la orden #64, que mide los 150 KB de la ADR-001.

## Las reglas comunes

- **Cabecera.** Cada JSON lleva:
  - `"contrato": 1`, la versión de este documento;
  - `generado`, con `utc` (ISO 8601 con zona, como `2026-11-28T18:00:00+00:00`), `commit`
    (el hash de git, de 7 a 40 cifras hexadecimales) y `comando`, la orden que lo escribió;
  - `fuentes`, una lista con al menos una fuente, cada una con `nombre`, `version`,
    `licencia` y `url`.

  Las capas GeoJSON lo llevan en `metadatos`, fuera de `features`. `escuelas.json` no lleva
  `fuentes`: la orden #57 la pone en cada escuela, en `fuente_coordenadas`.
- **Licencias**, en `fuentes[].licencia`: `CC0-1.0`, `CC-BY-4.0` o `dominio-publico` (#32), o
  `cita` para una obra sin licencia declarada de la que solo se citan criterios, sin copiar
  nada, como el Manual de Diseño Mi Nueva Escuela.
- **Números.** Vienen redondeados a los decimales con que se muestran, y con su unidad: en un
  campo `unidad` del objeto que los contiene, o como sufijo del nombre (`_m`, `_km`, `_c`,
  `_m2`, `_mm`) en los campos que fijan otras órdenes. La interfaz no recalcula: solo cambia el
  punto por la coma.
- **Registros.** Se llaman `estudiante`, `docente` y `direccion`, sin tilde, como en
  `web/direcciones/ficha-ejemplo.json`. En pantalla se lee «Dirección».
- **Lenguaje.** Los campos `texto` y `pregunta` de `recorrido.json` y `validacion.json` no
  llevan ninguna de las palabras de `PALABRAS_PROHIBIDAS` (alerta, predicción, predice,
  pronóstico, pronostica, riesgo, peligro, deben, tienen que, obligatorio) ni de
  `PALABRAS_INTERIOR` (interior, puerta, acceso), con sus plurales y su femenino, sin
  distinguir mayúsculas ni tildes. Las dos listas están en `src/contrato.py`. `limites.json`
  queda fuera de la regla: sus textos niegan esas palabras a propósito.
- **Archivos que faltan.** Si un archivo falta, la interfaz dice «todavía no hay … para esta
  escuela», y el validador no lo cuenta como error. Si está, tiene que estar completo. Un
  archivo que no está en este documento sí es un error.
- **Fechas** en `AAAA-MM-DD`, y horas en `HH:MM`, las dos en hora local salvo `generado.utc`.
- Todo en UTF-8.

## `escuelas.json`

Lo describe la orden #57, tal cual. Lleva `contrato`, `generado` y una lista `escuelas`; por
escuela:

| Campo | Tipo | Unidad y decimales |
|---|---|---|
| `slug` | texto: `sv-88118`, `co-nicolas-esguerra`, `ve-rafael-maria-baralt` | |
| `nombre`, `municipio`, `division`, `pais` | texto | |
| `codigo` | texto o `null` | el código oficial |
| `iso_pais` | texto: `SV`, `CO`, `VE` | |
| `lat`, `lon` | número | grados WGS84, 5 decimales |
| `huso_horas` | entero: −6, −5, −4 | horas respecto a UTC |
| `ancla` | booleano | `true` solo en la 88118 |
| `estacion` | objeto: `nombre`, `lat`, `lon`, `distancia_km` | la distancia con una décima |
| `fuente_coordenadas` | objeto: `nombre`, `url`, `fecha_consulta`, `metodo` (`directorio` o `direccion-en-mapa`) y, si la fuente la declara, `licencia` | |

El ejemplo no está en `escuelas.json`: la interfaz lo abre con `?escuela=ejemplo`.

## `<slug>/escuela.json`

La identidad de la escuela y lo que la sitúa. Lleva la cabecera y:

| Campo | Tipo | Unidad y decimales |
|---|---|---|
| `slug` | texto | el nombre de la carpeta |
| `nombre`, `municipio`, `division`, `pais`, `iso_pais` | texto | los de `escuelas.json` |
| `codigo` | texto o `null` | |
| `lat`, `lon` | número | grados, 5 decimales, iguales a los de `escuelas.json` |
| `huso_horas` | entero | igual al de `escuelas.json` |
| `altitud` | `{valor, unidad: "m", fuente: "NASADEM"}` | una décima: `altitud_escuela_m` de `relieve.json` |
| `zona_diseno` | texto o `null` | `costera`, `tropical caliente` o `montañosa`; `null` fuera de El Salvador |
| `zona_diseno_franja` | `{desde, hasta, unidad: "m", referencia}` | metros enteros; `hasta` es `null` en la montañosa |
| `celda_era5` | `{lat, lon, resolucion: 0.25, unidad: "grados"}` | el punto de la rejilla más cercano |
| `criterios` | texto | `propios` en El Salvador; `referencia de comparación` fuera (#16) |

**La zona de diseño** sale de la altitud con el Manual Mi Nueva Escuela, anexo 8, p. 16: costera
de 0 a 300 m, tropical caliente de 300 a 700 m y montañosa por encima de 700, con el límite
inferior dentro y el superior fuera. Solo se da en El Salvador. Donde el manual no da una
referencia de alero aplicable a la sede y a la fachada, la ficha no da una longitud de alero,
solo la pregunta (#23).

## `<slug>/clima.json`

Los indicadores de la #22 en la celda de ERA5 de la escuela. Lleva la cabecera y `escuela`, el
slug.

**Las reglas de cálculo**, que repiten las órdenes de los indicadores:

- **Husos fijos:** UTC−6 en El Salvador, UTC−5 en Colombia y UTC−4 en Venezuela, sin horario de
  verano. La serie llega hasta el 1 de enero de 2026 a las 06:00 UTC, para completar el último
  día local de 2025.
- **Corrección por altura:** `T_local = T_ERA5 − Γ·(z_escuela − z_celda)`, con Γ = 6,5 K/km.
  Si la escuela está más baja que la celda, la corrección es positiva.
- **Calor:** horas de lunes a viernes, de las 07:00 a las 16:00 locales (las 17:00 fuera: diez
  horas por día), en que `T_local` pasa de 27 °C, estricto. El día de la semana se toma en hora
  local. Un año tiene como mucho 262 días laborables, así que 2620 horas.
- **Lluvia:** la de la fila T de ERA5 es la de la hora que termina en T, y el día local suma
  (00:00, 24:00] local. El p99 se calcula con `numpy.percentile`, lineal, sobre los 10 957 días
  locales de 1961–1990, contando los secos. «Supera» es >.
- **Promedios:** de 1961–1990 y de 1996–2025, como la media de la serie anual del periodo.
- **Episodios:** los tres días locales de 1996–2025 con más lluvia entre los que superan el
  p99.

**Los campos:**

| Campo | Tipo | Unidad y decimales |
|---|---|---|
| `correccion.formula` | texto | |
| `correccion.z_escuela` | `{valor, unidad: "m"}` | una décima; es `escuela.json → altitud.valor` |
| `correccion.z_celda` | `{valor, unidad: "m"}` | una décima; el geopotencial de ERA5 entre g |
| `correccion.gamma` | `{valor: 6.5, unidad: "K/km"}` | |
| `correccion.correccion` | `{valor, unidad: "K"}` | una décima: −Γ·(z_escuela − z_celda) |
| `calor.umbral` | `{valor: 27, unidad: "°C"}` | |
| `calor.horario` | texto | el horario, dicho para la pantalla |
| `calor.unidad` | `"horas"` | la de los promedios y la serie |
| `calor.horas_1961_1990`, `calor.horas_1996_2025` | número | horas al año, una décima, de 0 a 2620 |
| `calor.serie` | lista de 86 `{anio, horas}` | de 1940 a 2025 en orden; horas enteras, de 0 a 2620 |
| `calor.por_mes.periodo` | `[1996, 2025]` | |
| `calor.por_mes.unidad` | `"horas"` | |
| `calor.por_mes.meses` | lista de 12 `{mes, horas}` | `mes` de 1 a 12 en orden; horas con una décima, de 0 a 230 |
| `lluvia.p99` | `{valor, unidad: "mm", periodo: [1961, 1990], dias_base: 10957}` | mm por día, una décima |
| `lluvia.unidad` | `"días"` | |
| `lluvia.dias_1961_1990`, `lluvia.dias_1996_2025` | número | días al año, una décima, de 0 a 366 |
| `lluvia.serie` | lista de 86 `{anio, dias}` | de 1940 a 2025 en orden; días enteros, de 0 a 366 |
| `episodios.unidades` | `{lluvia: "mm", temperatura: "°C"}` | |
| `episodios.lista` | lista de 3 `{fecha, lluvia_total, lluvia, temperatura}` | de más lluvia a menos |
| `episodios.lista[].fecha` | texto `AAAA-MM-DD` | el día local, en 1996–2025 |
| `episodios.lista[].lluvia_total` | número | mm, una décima, por encima del p99 |
| `episodios.lista[].lluvia` | lista de 24 números | mm, una décima; la posición i es la hora local que termina a las i+1 |
| `episodios.lista[].temperatura` | lista de 24 números | °C corregidos, una décima, a las i+1 locales |
| `limites` | lista de textos | los `id` de `comun/limites.json` que se aplican |

**Lo que tiene que cuadrar**, y el validador comprueba:

- cada promedio es la media de la serie de su periodo, hasta el redondeo (0,05);
- las horas de los 12 meses suman el promedio anual de 1996–2025, hasta el redondeo de cada
  mes (0,65 como mucho);
- la corrección es −Γ·(z_escuela − z_celda) con una décima, y `z_escuela` es la altitud de
  `escuela.json`;
- las 24 horas de lluvia de un episodio suman su `lluvia_total`, hasta el redondeo, y el año de
  cada episodio tiene al menos un día sobre el p99 en la serie.

Con el p99 de 1961–1990, unos 110 días de ese periodo lo superan, 3,7 al año: menos solo si hay
empates en el umbral.

## `<slug>/validacion.json`

La métrica de la validación de ERA5 contra una estación, como límite declarado y no como
calificación (#19, #54 y #56). La escribe `src/validacion_ficha.py` desde el `metrics.json`
del experimento (#71). Lleva la cabecera y:

| Campo | Tipo | Unidad y decimales |
|---|---|---|
| `escuela` | texto | el slug |
| `estado` | `publicada` o `retirada` | `retirada` si la #39 dice que esos datos no se usan |
| `motivo` | texto o `null` | obligatorio con `retirada` |
| `estacion` | `{nombre, fuente, distancia, altitud}` | `distancia` en `{valor, unidad: "km"}` y `altitud` en `{valor, unidad: "m"}`, con una décima |
| `periodo` | `{desde, hasta}` | fechas `AAAA-MM-DD` |
| `que_se_valida` | texto | en la ancla, la temperatura del horario escolar, sin máximas ni mínimas; en las réplicas, la media, la máxima y la mínima diarias |
| `unidad` | `"K"` | la del sesgo y el error |
| `variables` | lista de `{id, nombre, emparejados, sin_correccion, con_correccion}` | `id`: `horaria`, `media`, `maxima` o `minima` |
| `variables[].emparejados` | `{valor, unidad}` | entero; `horas` o `días` |
| `variables[].sin_correccion`, `con_correccion` | `{sesgo, error_cuadratico_medio}` | K, una décima |
| `nota_licencia` | texto | la serie de la estación no está en el repositorio: solo se publica la métrica (#46 y #39) |
| `experimento` | `{ruta, commit}` | `experiments/<AAAAMMDD>-<slug>`; `null` solo en el ejemplo |
| `texto` | `{estudiante, docente, direccion}` | el sesgo es una limitación que se declara, no una calificación |

Con `estado: "retirada"` el archivo lleva la cabecera, `escuela`, `estado`, `motivo` y
`texto`, sin cifras.

## `<slug>/recorrido.json`

Las paradas del recorrido guiado y sus preguntas para conversar, en los tres registros. Lo
escribe `src/recorrido.py`, que resuelve los marcadores (`{{clima.calor.horas_1996_2025}}`)
contra `escuela.json`, `clima.json` y `validacion.json` (#67). Lleva la cabecera y:

| Campo | Tipo | Unidad y decimales |
|---|---|---|
| `escuela` | texto | el slug |
| `registros.<registro>` | `{nombre, titulo, entrada}` | uno por registro |
| `paradas` | lista de paradas | `id` distintos |
| `paradas[].id`, `titulo` | texto | |
| `paradas[].maqueta` | `{volumen, capa, hora}` | `capa`: `calor`, `sombra` o `agua`; `hora` entera, de 0 a 23, local |
| `paradas[].mapa` | `{vista, capa}` | `vista`: `2d` o `3d`; `capa`: `relieve`, `calor`, `cobertura` o `agua` |
| `paradas[].texto` | `{estudiante, docente, direccion}` | 450 caracteres como mucho cada uno |
| `paradas[].pregunta` | `{estudiante, docente, direccion}` | entre «¿» y «?» |

Ningún texto lleva un marcador sin resolver (`{{` o `}}`).

## Las capas del mapa

Siguen los formatos de la ADR-001. Las coordenadas van en longitud y latitud (EPSG:4326,
RFC 7946), con 6 decimales como mucho. Cada geometría tiene la estructura de su tipo: un
`Point` es una posición; un `LineString`, dos o más; un `Polygon`, una lista de anillos de
cuatro posiciones o más, con la última igual a la primera; un `MultiPolygon`, una lista de
polígonos.

- **`relieve/relieve.json`**, con la cabecera y `escuela`, `granulos` (lista de textos, como
  `n13w090`), `bounds` (`[oeste, sur, este, norte]` del recorte), `minzoom` y `maxzoom`
  (enteros), `precision_m` (0,25) y `altitud_escuela_m` (una décima). Sus teselas son
  `relieve/{z}/{x}/{y}.png`, en terrarium y en Web Mercator, con `z` entre `minzoom` y
  `maxzoom` (#60).
- **`edificios.geojson`**: polígonos (`Polygon` o `MultiPolygon`), con `altura` y `base` en m,
  con una décima, y `altura_supuesta` (booleano: `true` si falta el dato y la altura es 3,0 m).
  Solo contornos exteriores (#62).
- **`calor.geojson`**: los cuadros de 100 m de Landsat, como `Polygon`, con `t_superficie_c`
  (°C, una décima, o `null` con `sin_dato`), `n_escenas` (entero) y `sin_dato` (booleano:
  menos de 3 escenas). Es la temperatura de techos y suelos cuando pasa el satélite, no la del
  aire (#62).
- **`cobertura.png`**: la cobertura del suelo de WorldCover, una imagen para una fuente
  `image`. Sus esquinas van en `capas.json`.
- **`capas.json`**, con la cabecera y:
  - `cobertura.esquinas`: cuatro `[lon, lat]`, en el orden de MapLibre (arriba a la
    izquierda, arriba a la derecha, abajo a la derecha, abajo a la izquierda);
  - `clases`: lista de `{clase, nombre, color}`, con la clase de WorldCover (entero), su nombre
    en español y su color en `#rrggbb`, en minúsculas y sin rojo;
  - `landsat`: `{periodo: {desde, hasta}, escenas, hora_local}`, con la hora media de paso en
    `HH:MM`;
  - `edificios`: `{con_altura, sin_altura}`, enteros.
- **`agua.geojson`**, con `metadatos.limite`, el texto del límite que enseña la interfaz, y
  rasgos de dos `tipo`:
  - `escorrentia`, un `LineString` con `acumulacion_celdas` (entero) en su extremo aguas abajo;
  - `punto_bajo`, un `Point` con `relleno_m` (dos decimales) y `area_m2`.

  Dice «por dónde tiende a correr» y «dónde tiende a juntarse»: no simula caudal ni
  profundidad (#63).

## La maqueta en STL

- **`maqueta.stl`**: STL binario, de 3 MB como mucho (#75).
- **`maqueta-stl.json`**, con la cabecera y `escala` (`1:5000`), `exageracion` (2),
  `lado_mm`, `triangulos` y `bytes` (enteros, los del STL) y `limite`, el texto que dice que
  son volúmenes estimados, sin interiores.

## Los archivos comunes

- **`comun/limites.json`**, con la cabecera y `limites`: lista de `{id, titulo, estudiante,
  docente, direccion}`. El `id` es el título en minúsculas, sin tildes y con guiones, como
  `era5-describe-la-zona-no-la-escuela`. Sale de `docs/material/limites.md` (#59).
- **`comun/glosario.json`**, con la cabecera y `terminos`: lista de `{termino, definicion}`.
  Sale de `docs/material/glosario.md` (#59).
- **`comun/maqueta-generica.json`**, con la cabecera, `aviso`, `volumenes`, `superficies`,
  `cubiertas` y `arboles` (listas), y `agua` (objeto), en metros, como en
  `web/direcciones/escuela-esquema.json`. Sin `lat`, `lon` ni ningún punto geográfico: el sol
  sale de la escuela elegida. Con la etapa 2 de la #65 gana `rutas`.
- **`comun/reserva.json`**, con la cabecera y `registros.<registro>`: lista de `{pregunta,
  respuesta, fila_bateria}`, con `fila_bateria` entero. Sin cifras de ninguna escuela (#73).
- **`web/material/material.json`**, con la cabecera y `pdfs`: lista de `{escuela, registro,
  archivo, paginas, kb}`, con `archivo` al lado del JSON, 4 páginas como mucho y 500 KB como
  mucho, con una décima (#74).

## El ejemplo

`web/datos/ejemplo/` tiene `escuela.json`, `clima.json`, `validacion.json` y `recorrido.json`,
con cifras inventadas, plausibles y coherentes entre sí. La orden #66 añade las capas del
mapa.

- Cada archivo lleva `"ejemplo": true` y un `aviso` que dice que sus cifras son ficticias.
  Ningún archivo fuera de `ejemplo/` lleva `"ejemplo": true`.
- El punto es el de `web/direcciones/escuela-esquema.json`: 13,7; −89,2, en UTC−6, en El
  Salvador, y por eso con zona de diseño y criterios propios.
- Las horas de los 12 meses suman el promedio anual de 1996–2025, y los 110 días sobre el p99
  de 1961–1990 dan 3,7 al año.
- El ejemplo no está en `escuelas.json`: la interfaz lo abre con `?escuela=ejemplo`.

## El validador

```
python -m src.contrato web/datos/ejemplo
python -m src.contrato web/datos/sv-88118
python -m src.contrato --todas
```

- Con una carpeta, valida esa escuela o el ejemplo, con lo que exista de `escuelas.json` y
  `comun/` en la carpeta de al lado. Con `--todas`, todas las carpetas de `web/datos/`, más
  `escuelas.json`, `comun/` y `web/material/material.json`.
- Comprueba lo que dice este documento: los campos obligatorios, los tipos, las unidades, los
  decimales, `contrato`, `generado` y `fuentes`, los rangos, la coherencia de `clima.json`, el
  lenguaje y los archivos que no están en el contrato. Todo archivo JSON es un objeto en la
  raíz: uno que contiene solo `null` es un error, no un archivo completo.
- **Presupuestos**, con gzip -9 y en KB de 1000 bytes, medidos con `src.presupuesto.medir`:
  - **la primera pantalla de una escuela**, 20 KB como mucho: `escuelas.json`, su
    `escuela.json`, `clima.json`, `validacion.json` y `recorrido.json`, y `comun/limites.json`,
    `glosario.json` y `maqueta-generica.json`;
  - **el mapa**, 2000 KB como mucho: `relieve/`, `edificios.geojson`, `calor.geojson`,
    `cobertura.png`, `capas.json` y `agua.geojson`;
  - `maqueta.stl`, `maqueta-stl.json` y `comun/reserva.json` no cuentan: se cargan a petición.
- Imprime una fila por archivo, con su estado y sus KB, los dos totales de cada escuela y los
  errores, cada uno con su archivo y su campo (`ejemplo/clima.json: lluvia.p99: falta`). Sale
  con 1 si algo falla.
- Las listas `PALABRAS_PROHIBIDAS` y `PALABRAS_INTERIOR`, y la función `vetadas(texto)`, se
  importan desde `src.contrato`.

Cambiar un campo es cambiar este documento y el validador en el mismo PR, y subir `contrato`
si un archivo de la versión anterior deja de ser válido.
