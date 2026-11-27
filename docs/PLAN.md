# Plan de SARCAE-LAT

Sistema de aprendizaje sobre riesgos de calor y agua en escuelas latinoamericanas.

Borrador del brief (fase 0), redactado el 27 de noviembre de 2026 para su aprobación por PR.
Lo que sigue sin decidir se marca como "(abierto)" y se reúne en la sección 12.

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
la organización preparó a partir de la propuesta del retador, sin pesos, así que los criterios
pueden cambiar (sección 12):

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
civil.

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
| El Salvador | (abierto) | Escuela ancla: datos locales, validación y prueba del mensaje con un docente |
| Colombia | (abierto) | Réplica con datos globales |
| Venezuela | (abierto) | Réplica con datos globales |

Riesgos: calor y agua. Los incendios quedan fuera.

### 4. Datos

| Dato | Para qué | Resolución | Licencia | Estado |
|---|---|---|---|---|
| ERA5, niveles de superficie (Copernicus, Climate Data Store) | Clima de la zona desde 1940: temperatura, humedad y lluvia | 0,25° (unos 28 km), horario | CC BY 4.0 | Obligatorio por el reto. El CDS publica además una serie horaria por punto desde 1940; falta medir cuánto tarda su descarga |
| ERA5-Land | Refinamiento del anterior | 0,1° | por comprobar | (abierto) si cuenta como "datos de ERA5" (sección 12) |
| Modelo de elevación: Copernicus DEM GLO-30 o NASADEM | Corrección por altura y flujo del agua | 30 m | Copernicus DEM: licencia propia con aviso obligatorio. NASADEM: por comprobar | (abierto) cuál de los dos |
| Landsat 8 y 9, temperatura de superficie | Dónde se calienta más la superficie | banda térmica de 100 m, servida a 30 m | por comprobar | |
| ESA WorldCover | Cobertura del suelo: vegetación, construcción, agua | 10 m | por comprobar | |
| Google Open Buildings v3 | Contornos de los edificios | | CC BY 4.0 u ODbL, a elección; se usa con CC BY 4.0 | Comprobada la licencia. Falta comprobar la cobertura de los tres países |
| Google Open Buildings 2.5D Temporal | Alturas de los edificios, 2016 a 2023 | error medio de 1,5 m | CC BY 4.0 u ODbL, a elección | Comprobada la licencia |
| CHIRPS | Lluvia, para comparar con ERA5 | 0,05° | dominio público, según el catálogo de Earth Engine | Falta confirmarlo en la fuente original |
| Estaciones meteorológicas | Validación de ERA5 | puntual | según la fuente | (abierto) cuáles |
| Manual de Diseño Mi Nueva Escuela (MINEDUCYT, 2022) | Medidas de referencia de aulas y tipologías, y criterios de ventilación, sombra y aguas lluvias | | sin licencia declarada | Solo se usan sus medidas y criterios, citando el manual; no se copian sus figuras |

Las licencias marcadas como comprobadas se consultaron el 27 de noviembre de 2026.

**Volumen y frecuencia.** Los datos se descargan una sola vez, con la fecha y la versión
registradas, y los recortes de las tres zonas pesan poco. La demo no consulta servicios en
vivo, salvo el asistente de la sección 8.

**Calidad.** ERA5 es un reanálisis, la combinación de un modelo con observaciones, y no una
medición directa en la escuela. Por eso se valida contra estaciones donde las haya.

**Google Earth Engine** se usa solo para extraer recortes, que se exportan al repositorio con su
fecha y su licencia. El análisis corre desde esos recortes, sin cuenta de Earth Engine, para que
el jurado pueda reproducirlo.

**Lo que no se usa:**
- Imágenes y modelos 3D de Google Maps, Google Earth o Esri: su licencia no permite copiarlos.
- Extractos de OpenStreetMap guardados en el repositorio: siguen siendo ODbL, que no figura
  entre las licencias de la regla 6 del hackathon. Un mapa base dibujado con OpenStreetMap sí
  se puede usar, con su atribución.
- Meteostat: su licencia es no comercial (CC BY-NC).
- Planos de escuelas concretas (sección 7).

### 5. Método, en un minuto

1. **El tiempo, con ERA5.** En la celda de la escuela se calculan los indicadores de calor
   (temperatura y humedad a 2 m) y de lluvia extrema, y su cambio desde 1940. Los umbrales se
   fijan con el contrato de datos.
2. **El espacio, con datos finos.** ERA5 no ve nada por debajo de su celda: unas 28 celdas
   cubren El Salvador entero. El detalle sale de variables con información fina real:
   - corrección por altura con el modelo de elevación,
     `T_local = T_ERA5 - Γ·(z_local - z_celda)`, con Γ ≈ 6,5 K/km o estimado de los datos;
   - temperatura de superficie de Landsat para el calor;
   - acumulación de flujo sobre el modelo de elevación para el agua.
3. **La validación.** ERA5, interpolado y corregido, se compara con estaciones donde existan, y
   se publica la métrica.

La interpolación del campo de ERA5 solo sirve para dibujar un mapa continuo, y se declara como
tal: no añade información por debajo de la celda.

### 6. Lo que se entrega

Lo que pide el reto:

1. **Ficha de cada escuela:** ubicación, clima de la zona, calor y agua en su entorno,
   preguntas para conversar, fuentes y límites.
2. **Análisis reproducible:** código con el entorno fijado y datos con su fecha y su versión.
3. **Mapa:** capas de calor y agua sobre el entorno de la escuela.
4. **Material educativo:** en la web y en PDF para imprimir, en los tres registros.
5. **Maqueta digital interactiva:** relieve y edificios en volumen, con las capas encima, y un
   recorrido guiado. Se puede exportar a STL para construir una maqueta física.
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
  se usan criterios generales mientras no se encuentren sus equivalentes (abierto).
- La maqueta muestra volúmenes: contornos, alturas, techos, patio y drenaje. Nunca la
  distribución interior, las puertas ni los accesos de una escuela concreta, por la seguridad
  de quienes la ocupan.

### 8. El asistente

Un asistente con un LLM ayuda a estudiantes, docentes y dirección a usar la herramienta.

- Responde solo desde la ficha de la escuela: indicadores, fuentes y límites, en un JSON que
  cabe en el contexto del modelo.
- No pronostica ni evalúa riesgo. Ante una emergencia remite a la autoridad de protección civil
  del país.
- Habla en el registro de quien pregunta: estudiante, docente o dirección.
- La clave de la API vive en el servidor, nunca en el navegador, con un límite de peticiones.
- Se prueba con unas 20 preguntas, entre ellas trampas como "¿se va a inundar mi escuela
  mañana?". El resultado es la evidencia del criterio de uso de la IA.
- Si se agota la cuota, quedan respuestas de reserva escritas por el equipo.
- No es la pieza principal: lo central son la ficha, el mapa y la maqueta.

Proveedor (abierto). Candidato: Gemini en Vertex AI, pagado con los créditos de Google Cloud
del equipo. Según la documentación de Google, esos créditos de prueba cubren Vertex AI y no la
API de Gemini de AI Studio.

### 9. Marca, tono y referencias visuales

- No hay marca previa. El nombre es SARCAE-LAT.
- Tono claro y cercano, sin alarmismo: habla de preparación, no de peligro.
- Referencias visuales (abierto): tres que gusten y una que no, cada una con su porqué, antes
  de las dos direcciones visuales.

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
- **Alojamiento:** Cloudflare Pages, previsto, más una función de servidor para el asistente. Se
  decide en la ADR del front (sección 12).
- **Rendimiento:** la primera pantalla es ligera y la maqueta 3D se carga solo cuando se pide.
  El presupuesto exacto se fija en la ADR del front.
- **Privacidad:** al proveedor del LLM solo van la ficha de la escuela, que son datos públicos y
  agregados, y la pregunta que escribe la persona. La interfaz avisa de que la pregunta sale a
  un servicio externo y pide no escribir nombres ni datos personales.
- **Costes:** alerta de presupuesto en Google Cloud y claves restringidas.

### 12. Decisiones abiertas

| N.º | Decisión | Antes de |
|---|---|---|
| 1 | Escuela ancla en El Salvador | las direcciones visuales |
| 2 | Escuelas de Colombia y Venezuela | el contrato de datos |
| 3 | Stack del front, en una ADR. Recomendación: HTML, CSS y JavaScript sin framework, con MapLibre GL JS para el mapa y la maqueta; alternativa, Svelte | la construcción |
| 4 | Si ERA5-Land cuenta como "datos de ERA5": se pregunta en el canal del reto | el contrato de datos |
| 5 | Pesos de los criterios y presencia del retador en el jurado: se pregunta en el canal del reto | la construcción |
| 6 | Proveedor del LLM | la integración |
| 7 | Estaciones para la validación | el contrato de datos |
| 8 | Modelo de elevación: Copernicus DEM o NASADEM | el contrato de datos |
| 9 | Referencias visuales | las direcciones visuales |
| 10 | Criterios equivalentes al manual salvadoreño para Colombia y Venezuela | la ficha |
