# Plan de SARCAE-LAT

Sistema de aprendizaje sobre riesgos de calor y agua en escuelas latinoamericanas.

Brief redactado el 27 de noviembre de 2026 y puesto al día el mismo día con las decisiones de
las issues #15 a #23. Lo que sigue pendiente se marca como "(abierto)", con la issue que lo
resuelve, y se reúne en la sección 12.

## Brief

### 1. El reto

Reto 10 de CoAfina 2026, "Protégete de los riesgos climáticos: una escuela, datos y una
maqueta", propuesto por la Universidad de Salamanca.

Entregable, tal como lo escribe la ficha del reto:

> Ficha de un centro o comunidad, análisis reproducible con datos reales de ERA5, mapa y
> material educativo claro, más una maqueta digital interactiva documentada y explicación de
> sus límites.

Límite, en la misma ficha:

> La maqueta servirá para conversar sobre preparación y rutas posibles, sin presentarse como
> pronóstico ni evaluación oficial de riesgo.

Criterios de evaluación, según la presentación del reto. Esa presentación es un borrador que
la organización preparó a partir de la propuesta del retador, y no publica los pesos. En el
canal público del reto, el 27 de noviembre, respondieron que los criterios sí tienen
porcentajes distintos, pero que entre el de más peso y el de menos no hay más de un 5 o un 10 %
de diferencia, y que "usabilidad y Creatividad es lo define ganadores" (#17). No se preguntó si
el retador forma parte del jurado: al equipo le pareció impertinente.

| Criterio | Qué se valora |
|---|---|
| Datos reales | El equipo usa datos reales de ERA5. |
| Mensaje claro | Se entiende para quien visita el centro o la comunidad. |
| Maqueta | Está creada y documentada. |
| Novedad | La propuesta es novedosa. |
| Uso de la IA | Sirve de apoyo y el equipo explica qué decidió por su cuenta. |

Fuentes: la ficha del reto en `retos.json` del repositorio público `laa-hecap/coafina`
(commit `927fbb9`) y la presentación del reto, compartida en su canal de Discord el 27 de
noviembre de 2026.

### 2. Quién lo usa y qué decide

Estudiantes, docentes y dirección de escuelas públicas de América Latina. Cada texto existe en
tres registros, uno por público.

La decisión que apoya es qué revisar o preparar en la escuela ante el calor y el agua, y de qué
conversar con la comunidad. No decide evacuaciones ni sustituye a la autoridad de protección
civil: las rutas que se comparan en la maqueta son hipotéticas, y las decisiones de evacuación
las orienta el protocolo vigente de cada centro.

La primera pantalla contesta tres preguntas:

1. ¿Cuánto calor y cuánta lluvia extrema hay en el lugar de la escuela, y cómo han cambiado
   desde 1940?
2. ¿En qué partes de la escuela y de su entorno se acumula más el calor, y por dónde podría
   llegar el agua?
3. ¿Qué se puede revisar o preparar en la escuela, y de qué conviene conversar?

Además dice, en cinco segundos, qué es la herramienta, para quién es y qué hacer primero.

### 3. Alcance: un motor, tres escuelas

El motor recibe las coordenadas de una escuela y produce su ficha, sus capas y su maqueta. Usa
solo datos globales, así que funciona igual en cualquier país de la región. Lo local se añade
donde existe y no es condición para que la herramienta funcione.

| País | Escuela | Profundidad |
|---|---|---|
| El Salvador | Centro Escolar Católico San Pablo Apóstol (código MINED 88118), San Pablo Tacachico | Escuela ancla: datos locales, validación y prueba del mensaje con un docente |
| Colombia | Colegio Nacional Nicolás Esguerra, Bogotá | Réplica con datos globales |
| Venezuela | Unidad Educativa Nacional Rafael María Baralt, Maracaibo | Réplica con datos globales |

Las tres se confirmaron el 27 de noviembre (#15 y #16). Se puede sumar un segundo centro
salvadoreño si es de gestión oficial, tiene un diseño de Mi Nueva Escuela documentado y cuenta
con datos suficientes para la maqueta.

Riesgos de la primera entrega: calor y agua. Los incendios de vegetación quedan como ampliación
declarada, fuera de la primera entrega (#16).

### 4. Datos

| Dato | Para qué | Resolución | Licencia | Estado |
|---|---|---|---|---|
| ERA5, niveles de superficie (Copernicus, Climate Data Store) | Clima de la zona desde 1940: temperatura, humedad y lluvia | 0,25° (unos 28 km), horario | CC BY 4.0, también la serie por punto | Obligatorio por el reto. El CDS publica además una serie horaria por punto desde 1940; falta medir cuánto tarda su descarga |
| ERA5-Land | Refinamiento del anterior | 0,1° | CC BY 4.0 | Admitido: en el canal del reto respondieron que se use lo que permita una buena demo, desde 1950 si basta (#17). La serie anual desde 1940 que pide la #22 solo la da ERA5, así que ERA5 sigue de base mientras el equipo no decida otra cosa, y ERA5-Land queda como capa opcional; su celda de 0,1° afinaría, por ejemplo, el relieve de Bogotá |
| Modelo de elevación: Copernicus DEM GLO-30 o NASADEM | Corrección por altura y flujo del agua | 30 m | NASADEM: CC0, por la política de datos de NASA. Copernicus DEM: su instancia pública, GLO-30-F, tiene una licencia propia ("Full, Free & Open") que permite reproducir, distribuir y adaptar gratis (art. 4 y 5), pero su art. 6 exige un aviso que termina en "all rights reserved" y una cláusula de exención de responsabilidad, y obliga a los usuarios posteriores; no es compatible | Cerrada: NASADEM (sección 12, decisión 8) |
| Landsat 8 y 9, temperatura de superficie | Dónde se calienta más la superficie | banda térmica de 100 m, servida a 30 m | dominio público, sin restricciones de uso, según el USGS | |
| ESA WorldCover | Cobertura del suelo: vegetación, construcción, agua | 10 m | CC BY 4.0 | |
| Google Open Buildings v3 | Contornos de los edificios | | CC BY 4.0 u ODbL, a elección; se usa con CC BY 4.0 | Comprobadas la licencia y la cobertura: El Salvador, Colombia y Venezuela están en la lista de países del sitio |
| Google Open Buildings 2.5D Temporal | Alturas de los edificios, 2016 a 2023 | error medio de 1,5 m | CC BY 4.0 u ODbL, a elección | Comprobadas la licencia y la cobertura de los tres países |
| CHIRPS | Lluvia, para comparar con ERA5 | 0,05° | v2.0: dominio público; v3.0: CC BY 4.0, según el Climate Hazards Center | Comprobada en la fuente original. La v2.0 deja de producirse después de diciembre de 2026 |
| Estaciones meteorológicas | Validación de ERA5 | puntual, horaria | NOAA GHCNh: CC0, según su ficha de metadatos en NCEI. MARN: por comprobar | Elegidas para las réplicas (#19): El Dorado, a 8,1 km del colegio de Bogotá, y La Chinita, a 16,5 km de la escuela de Maracaibo, las dos de NOAA GHCNh. (abierto) la de la escuela ancla: la candidata es Nueva Concepción, del MARN, a 17,5 km y a 320 m de altitud, pendiente del acceso a su serie diaria y de sus condiciones de reutilización |
| Manual de Diseño Mi Nueva Escuela (MINEDUCYT, 2022) | Medidas de referencia de aulas y tipologías, y criterios de ventilación, sombra y aguas lluvias | | sin licencia declarada | Solo se usan sus medidas y criterios, citando el manual; no se copian sus figuras |

Las licencias del cuadro se consultaron el 27 de noviembre de 2026 en el sitio de quien produce
el dato. La de NOAA GHCNh se leyó para la #19; la orden #9 comprueba qué dice NCEI de los datos
de otros países (Resolución 40 de la OMM) y la cita en el README, y la del MARN sigue por ver.
Los enlaces están en el README, sección "Fuentes y licencias".

**Volumen y frecuencia.** Los datos se descargan una sola vez, con la fecha y la versión
registradas, y los recortes de las tres zonas pesan poco. La demo no consulta servicios en
vivo, salvo el asistente de la sección 8.

**Dónde se versionan los recortes** (#21): en `recortes/<escuela>/<fuente>/`, fuera de `data/`,
con un `manifiesto.json` por carpeta que da la fuente y su versión, la licencia con su enlace, la
fecha de descarga y el SHA-256 de cada archivo. Se admiten CSV, Parquet, GeoTIFF y JSON, con un
tope de 50 MB por archivo, y solo lo que tenga licencia compatible. `data/raw/` sigue inmutable y
sin versionar: el recorte es una copia derivada, no el original.

**Calidad.** ERA5 es un reanálisis, la combinación de un modelo con observaciones, y no una
medición directa en la escuela. Por eso se valida contra estaciones donde las haya.

**Google Earth Engine** se usa solo para extraer recortes, que se exportan a `recortes/` con su
manifiesto. El análisis corre desde esos recortes, sin cuenta de Earth Engine, para que
el jurado pueda reproducirlo.

**Lo que no se usa:**
- Imágenes y modelos 3D de Google Maps, Google Earth o Esri: su licencia no permite copiarlos.
- Extractos de OpenStreetMap guardados en el repositorio: siguen siendo ODbL, que no figura
  entre las licencias de la regla 6 del hackathon. Un mapa base dibujado con OpenStreetMap sí
  se puede usar, con su atribución.
- Meteostat: su licencia es no comercial (CC BY-NC).
- Planos de escuelas concretas (sección 7).

### 5. Método, en un minuto

1. **El tiempo, con ERA5.** En la celda de cada escuela se calculan tres indicadores (#22), que
   el contrato de datos recoge tal cual:
   - **Calor:** horas al año con la temperatura del aire a 2 m, corregida por altura (punto 2),
     por encima de 27 °C, el límite superior del rango de confort del Manual Mi Nueva Escuela
     (A8 p. 11). Se cuentan de lunes a viernes, de 07:00 a 17:00 hora local con las 17:00
     excluidas, todo el año: es un supuesto declarado, que no modela el calendario escolar de
     cada país. El umbral es el mismo en las tres escuelas, y sus fichas citan el manual
     salvadoreño como origen de esa referencia. La humedad no entra en el indicador.
   - **Lluvia extrema:** el percentil 99 de la lluvia diaria de 1961 a 1990 en cada sede, con los
     días secos incluidos y solo días locales completos. El umbral queda fijo y se muestra en
     milímetros, junto al número de días de cada año que lo superan.
   - **Cambio:** los promedios anuales de 1961 a 1990 frente a los de 1996 a 2025, dos periodos
     de 30 años, y la serie anual desde 1940.

   ERA5 llega en UTC, y se aplican husos fijos: UTC-6 en El Salvador, UTC-5 en Colombia y UTC-4
   en Venezuela, los tres sin horario de verano. Para completar el último día local de 2025 en
   las tres sedes, la serie llega hasta el 1 de enero de 2026 a las 06:00 UTC.

   Son criterios de diseño de edificios, no umbrales de salud: cada indicador se presenta como
   una pregunta para conversar.
2. **El espacio, con datos finos.** ERA5 no ve nada por debajo de su celda: unas 28 celdas
   cubren El Salvador entero. El detalle sale de variables con información fina real:
   - corrección por altura con el modelo de elevación,
     `T_local = T_ERA5 - Γ·(z_local - z_celda)`, con Γ ≈ 6,5 K/km o estimado de los datos;
   - temperatura de superficie de Landsat para el calor;
   - acumulación de flujo sobre el modelo de elevación para el agua.
3. **La validación** (#19). ERA5 se compara con cada estación en la ubicación de la estación, no
   en la de la escuela: se emparejan las mismas horas y se calculan el sesgo y el error
   cuadrático medio de la temperatura media, máxima y mínima diarias, con y sin corrección por
   altura, para medir cuánto mejora la corrección con observaciones reales.
   - Un día cuenta si tiene al menos 20 horas con datos de calidad, repartidas entre madrugada,
     mañana, tarde y noche. Es un criterio preliminar.
   - Donde falten meses, como en La Chinita, se informa sobre los días disponibles y se muestra
     la cobertura de cada mes.
   - Ilopango y Santa Ana no tienen ningún día que cumpla el criterio en 2024 ni en 2025: sirven
     para contrastar horas coincidentes, no máximas ni mínimas diarias.

   La métrica se publica en la ficha como límite, no como calificación. La temperatura dentro
   del recinto escolar queda fuera del alcance de las estaciones.

La interpolación del campo de ERA5 solo sirve para dibujar un mapa continuo, y se declara como
tal: no añade información por debajo de la celda.

### 6. Lo que se entrega

Lo que pide el reto:

1. **Ficha de cada escuela:** ubicación, clima de la zona, calor y agua en su entorno,
   preguntas para conversar, fuentes y límites. Donde el manual no da una referencia de alero
   aplicable a la sede y a la fachada, la ficha no da una longitud de alero, solo la pregunta
   (#23):
   - **88118:** su altitud estimada cae en la franja que el manual usa para las simulaciones de
     clima tropical caliente, y la ficha lo dice. Su pregunta es "¿Qué ventanas reciben sol
     directo por la tarde y qué sombra les dan los aleros o parteluces?", y la maqueta ilustra
     esa sombra con volúmenes genéricos.
   - **Bogotá y Maracaibo:** preguntas generales, con las referencias locales que se verifiquen.
     Las de sombra, ventilación y agua se adaptan a cada sede (#16).
   - **Futuras sedes salvadoreñas:** las asignaciones expresas del manual cuando estén
     disponibles, también por encima de 900 m.
2. **Análisis reproducible:** código con el entorno fijado y datos con su fecha y su versión.
3. **Mapa:** capas de calor y agua sobre el entorno de la escuela.
4. **Material educativo:** en la web y en PDF para imprimir, en los tres registros.
5. **Maqueta digital interactiva:** relieve y edificios en volumen, con las capas encima, un
   recorrido guiado y dos escenarios educativos (#16 y #22):
   - **Lluvia intensa:** con episodios históricos elegidos con el indicador de lluvia y su
     secuencia horaria, muestra por dónde tendería a escurrir el agua según el relieve y dónde
     podría acumularse.
   - **Calor:** compara cómo cambian la exposición al sol y la sombra a lo largo del día.

   Con ellos, la comunidad discute qué zonas exteriores conviene revisar y compara rutas de
   evacuación hipotéticas en una maqueta genérica, nunca en la de una escuela concreta
   (sección 7). Se puede exportar a STL para construir una maqueta física.

   El caso del agua se comprueba de dos maneras: si el recorrido que muestra la maqueta
   coincide con un anegamiento documentado, y si un docente, después de usarla, sabe explicar
   qué revisaría y por qué.
6. **Explicación de los límites:** en la herramienta y en el README.

Lo que pide el hackathon: repositorio público con README reproducible, demo desplegada, video
de 5 minutos como máximo en YouTube y el formulario de entrega. Licencias (regla 6): MIT para
el código; CC BY 4.0 para la documentación, el material y los modelos propios.

### 7. Límites que se dicen en la herramienta

- No es un pronóstico ni una evaluación oficial de riesgo. Las preguntas para conversar no son
  una calificación de la escuela.
- ERA5 describe la zona, no la escuela: su celda mide unos 28 km.
- La temperatura de superficie de Landsat es la de techos y suelos a la hora en que pasa el
  satélite, no la del aire.
- Las alturas de los edificios son estimaciones, con un error medio de 1,5 m.
- Los criterios del Manual de Diseño Mi Nueva Escuela son salvadoreños. En Colombia y Venezuela
  se usan los mismos indicadores como referencia de comparación, y su ficha lo declara (#16).
- Las estaciones validan ERA5 donde están, no en la escuela.
- La maqueta muestra volúmenes: contornos, alturas, techos, patio y drenaje. Nunca la
  distribución interior, las puertas ni los accesos de una escuela concreta, por la seguridad
  de quienes la ocupan. Las rutas de evacuación que se comparan son hipotéticas y van sobre una
  maqueta genérica.

### 8. El asistente

Un asistente con un LLM ayuda a estudiantes, docentes y dirección a usar la herramienta.

- Responde solo desde la ficha de la escuela: indicadores, fuentes y límites, en un JSON que
  cabe en el contexto del modelo.
- No pronostica ni evalúa riesgo. Ante una emergencia remite a la autoridad de protección civil
  del país.
- Habla en el registro de quien pregunta: estudiante, docente o dirección.
- El acceso al modelo vive en el servidor, nunca en el navegador, con un límite de peticiones.
- Se prueba con unas 20 preguntas, entre ellas trampas como "¿se va a inundar mi escuela
  mañana?". El resultado es la evidencia del criterio de uso de la IA.
- Si se agota la cuota, quedan respuestas de reserva escritas por el equipo.
- No es la pieza principal: lo central son la ficha, el mapa y la maqueta.

**Proveedor** (#18): Cloudflare Workers AI con Mistral Small 3.1, que Mistral publica con
licencia Apache 2.0. La Function de Cloudflare Pages lo llama por un binding de Cloudflare, sin
clave de API en el código.

- **Gemini queda descartado**, en AI Studio y en Vertex AI: los términos de los dos restringen
  su uso en aplicaciones dirigidas a menores de 18 años o que probablemente usen menores.
- **Coste:** con 2.000 tokens de entrada y 250 de salida por consulta, la cuota gratuita
  publicada daría unas 130 consultas al día, si está disponible entera. Es una estimación.
- **Lo que falta para confirmarlo:** una llamada desde Pages Functions con una ficha de prueba,
  y la batería de preguntas de la #12 (`docs/asistente/preguntas-prueba.md`), que comprueba que
  responde en español, se ciñe a la ficha y maneja las preguntas fuera de alcance. El resultado
  es la evidencia de una ADR corta en `docs/decisiones/`, con la licencia y las condiciones de
  uso comprobadas.

### 9. Marca, tono y referencias visuales

- No hay marca previa. El nombre es SARCAE-LAT.
- Tono claro y cercano, sin alarmismo: habla de preparación, no de peligro.
- **Referencias visuales** (#20). Gustan tres simuladores de NASA Space Apps, 34 Percent,
  micro-G y AstroFire 3D, de los que se toma la composición y no el código ni los recursos. No
  gusta un tablero de ventas de Geckoboard, porque parece un artefacto genérico: mosaicos
  iguales, minigráficos que decoran y todo con el mismo peso.
- **Dirección visual:** A · Noche, elegida y congelada en la #20 (sección 12, decisión 9). Las
  cifras van en filas con su rótulo o en tablas, nunca en mosaicos, y el acento cálido solo
  marca acciones y selección: el calor y el agua tienen color solo en los datos.
- **Falta comprobar**, sin que cambie la elección: la primera pantalla con datos reales de la
  escuela ancla, y la prueba de los cinco segundos con alguien ajeno al equipo. Las dos van en
  la orden que construya la primera pantalla.

### 10. Dispositivos, accesibilidad e idioma

- **Dispositivos:** móvil y escritorio, en navegadores actuales, con conexiones lentas y equipos
  modestos en mente.
- **Accesibilidad:** WCAG 2.2 AA:
  - contraste de 4,5 a 1;
  - manejo completo con teclado y con lector de pantalla;
  - respeto a la preferencia de movimiento reducido;
  - nada que dependa solo del color.
- **La maqueta 3D nunca es el único canal:** cada parada del recorrido tiene su texto, y lo mismo
  está en el mapa y en la ficha.
- **Idioma:** español, en lenguaje claro y con glosario. Si el tiempo alcanza, narración en audio
  grabada.

### 11. Restricciones

- **Plazo:** entrega el domingo 29 de noviembre de 2026 a las 11:00 en El Salvador (12:00 GMT-5).
- **Alojamiento:** Cloudflare Pages, más una Function para el asistente, y GitHub Pages sin
  asistente como reserva (`docs/decisiones/ADR-001-front.md`).
- **Rendimiento:** la primera pantalla es ligera y la maqueta 3D se carga solo cuando se pide.
  El presupuesto de carga está en la ADR-001.
- **Privacidad:** al proveedor del LLM solo van la ficha de la escuela, que son datos públicos y
  agregados, y la pregunta que escribe la persona. La interfaz avisa de que la pregunta sale a
  un servicio externo y pide no escribir nombres ni datos personales. Cloudflare declara que no
  entrena modelos con el contenido de Workers AI y que, en la inferencia sin estado, solo
  conserva entradas y salidas el tiempo necesario para responder, con excepciones; sus términos
  contemplan además usar el contenido para operar y mejorar el servicio. La ADR del asistente
  deja escrita esa distinción.
- **Costes:** la cuota gratuita de Workers AI y el límite de peticiones de la Function. Si la
  cuota se agota, responden las respuestas de reserva de la sección 8.

### 12. Decisiones

| N.º | Decisión | Issue | Estado |
|---|---|---|---|
| 1 | Escuela ancla: Centro Escolar Católico San Pablo Apóstol, código MINED 88118 (sección 3) | #15 | cerrada |
| 2 | Escuelas réplica: Colegio Nacional Nicolás Esguerra, en Bogotá, y Unidad Educativa Nacional Rafael María Baralt, en Maracaibo (sección 3). Riesgos de la primera entrega: calor y agua; incendios de vegetación como ampliación declarada | #16 | cerrada |
| 3 | Stack del front: HTML, CSS y JavaScript sin framework, con MapLibre GL JS para el mapa y la maqueta, y mapa base sin OpenStreetMap (`docs/decisiones/ADR-001-front.md`, PR #7) | #5 | cerrada |
| 4 | ERA5-Land cuenta: el canal del reto dice que se use lo que dé una buena demo, desde 1950 si basta. La serie anual desde 1940 de la #22 solo la da ERA5, así que ERA5 sigue de base mientras el equipo no decida otra cosa, y ERA5-Land queda como capa opcional (sección 4) | #17 | cerrada |
| 5 | Pesos de los criterios: distintos, con no más de un 5 o un 10 % de diferencia entre el de más peso y el de menos; deciden la usabilidad y la creatividad (sección 1). Lo del jurado no se preguntó | #17 | cerrada |
| 6 | Proveedor del LLM: Cloudflare Workers AI con Mistral Small 3.1; Gemini descartado por la edad del público (sección 8) | #18 | elegido; (abierto) su confirmación, con la prueba desde Pages Functions, la batería de la #12 y la ADR |
| 7 | Estaciones para la validación: El Dorado y La Chinita, de NOAA GHCNh, para las réplicas; Nueva Concepción, del MARN, como candidata para la ancla (secciones 4 y 5) | #19 | elegidas para las réplicas; (abierto) la licencia de sus datos, que comprueba la #9 (Resolución 40 de la OMM), y la estación de la ancla, que busca la #39 |
| 8 | Modelo de elevación: NASADEM. Es el único de los dos con licencia compatible (CC0, por la política de datos de NASA), y sus recortes se versionan (sección 4). El Copernicus DEM es más reciente (2011 a 2015, frente a febrero de 2000), pero la licencia de su instancia pública, GLO-30-F, es propia y no CC0, CC BY ni dominio público: aunque permite distribuir (art. 4), su art. 6 exige un aviso que termina en "all rights reserved" y una cláusula de exención de responsabilidad, y obliga a los usuarios posteriores | #6 | cerrada |
| 9 | Dirección visual: A · Noche, elegida y congelada en la issue #20 entre dos direcciones del prototipo del PR #35. Azul noche con halo, paneles de cristal, IBM Plex Sans y Mono, y un acento cálido (`#ffa45c`) solo para acciones y selección. Sus tokens son el bloque `noche` y la escala común de `web/direcciones/tokens.css`, y pasan al PR de la fundación del front. No se reestiliza sin una decisión escrita | #20 | cerrada |
| 10 | Criterios en Colombia y Venezuela: los mismos indicadores que en El Salvador, como referencia de comparación declarada en la ficha, con las preguntas adaptadas a cada sede (opción a) | #16 | cerrada |
| 11 | Recortes de datos: en `recortes/<escuela>/<fuente>/`, con su manifiesto (sección 4, PR #34) | #21 | cerrada |
| 12 | Indicadores de calor, de lluvia y de cambio, con el horario de clase y los husos (sección 5) | #22 | cerrada |
| 13 | Aleros fuera de la tabla del manual: sin longitud de alero, solo la pregunta (opción a, sección 6) | #23 | cerrada |
