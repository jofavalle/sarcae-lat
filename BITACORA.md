# Bitácora de sarcae-lat

Estado del proyecto entre sesiones, para todo el equipo. Se versiona y la escribe quien
coordina, por PR como todo lo demás. El estado de cada tarea no va aquí: vive en las issues y
en sus PR. **Se mantiene corta a propósito**: lo que deje de estar vigente se borra, no se
acumula.

## Estado actual

**2026-11-28, 11:17 (hora de El Salvador).** El repositorio nació el 27 para el reto 10 de
CoAfina 2026. Es público y protege `main`: cada PR necesita una aprobación y el check `higiene`
en verde. jofavalle, aalexanderrz, cesarp03 y bm20004 tienen permiso de escritura.

En `main`:
- el brief, `docs/PLAN.md`, y la ficha del Manual de Diseño Mi Nueva Escuela (PR #1 y #2);
- la ADR-001 del front (orden #5, PR #7): HTML, CSS y JavaScript sin framework, MapLibre GL JS
  para el mapa y la maqueta, y mapa base sin OpenStreetMap;
- las licencias de las fuentes, comprobadas y citadas en el README, y el modelo de elevación
  elegido, NASADEM (orden #6, PR #8);
- la descarga de ERA5 por punto, `src/era5.py` (orden #4, PR #14). Probada con el aeropuerto
  de Ilopango, la serie de 1940 a 2025 tardó 122 s y pasó todos los controles. Desde la orden
  #37 (PR #42) llega hasta el 2026-01-01, y la lluvia anual se suma solo en años completos;
- MapLibre GL JS 6.20.0 en `web/vendor/`, con su presupuesto de carga (orden #10, PR #29). La
  ADR-001 aclara que su tabla de tamaños es de GNU gzip (orden #33, PR #43);
- la fundación del front (orden #40, PR #41): `web/index.html`, el CSS base y los tokens de
  A · Noche en `web/estilo/`;
- CHIRPS fijado en la v3.0, y en el README las atribuciones de las fuentes y el código de
  terceros (orden #9, PR #44);
- las preguntas de prueba del asistente (orden #12, PR #25), y los límites en tres registros
  con el glosario (orden #13, PR #26);
- los recortes en `recortes/<escuela>/<fuente>/`, con su manifiesto (decisión #21, PR #34);
- las teselas de relieve en terrarium a partir de NASADEM, `src/relieve.py` (orden #11, PR #45);
- los límites en el README (orden #27, PR #48), con Landsat en cuadros de 100 m (orden #30,
  PR #49), y las filas 1 y 23 de las preguntas de prueba ajustadas al brief (orden #31, PR #51);
- las licencias del repositorio, MIT para el código y CC BY 4.0 para el material (orden #28,
  PR #52), y en el `CLAUDE.md` las licencias de terceros admitidas (orden #32, PR #50);
- la prueba del asistente, una Function de Pages con Workers AI y Mistral Small 3.1, y la
  ADR-002: 16 de 24 respuestas conformes en la batería (orden #38, PR #53).

Las decisiones de las issues #15 a #23 están integradas en `docs/PLAN.md`, y su sección 12 es la
tabla vigente. Las escuelas son la 88118 en El Salvador (ancla), el Nicolás Esguerra en Bogotá y
el Rafael María Baralt en Maracaibo. El canal del reto respondió a la #17: ERA5-Land se admite,
y los criterios pesan casi lo mismo, con la usabilidad y la creatividad como lo que decide.
La validación quedó decidida (#46 y #39): en las tres sedes la serie de la estación no se
versiona y solo se publica la métrica, porque el inventario de C3S y NCEI marca las estaciones
como `non_commercial`. En la ancla, Nueva Concepción, del MARN, no se usa por no declarar
licencia, y ERA5 se contrasta con Santa Ana/El Palmar hora a hora en el horario escolar. La
pregunta de la #39 al retador sobre esa licencia sigue sin respuesta. Del asistente queda por
decidir si producción responde con el LLM o solo con respuestas de reserva (#72).

Desde la mañana del 28 entraron en `main` los primeros datos versionados:
- la validación de las réplicas (#56, PR #85, cerrada) y la de la ancla (#54, PR #86, con
  `Refs #54`: el código y una métrica provisional, porque `z_celda` es ficticia);
- los manifiestos de los recortes (#59, PR #87), el contrato de datos (#58, PR #88) y las
  coordenadas de las tres escuelas en `web/datos/escuelas.json` (#57, PR #89);
- el relieve de las tres escuelas (#60, PR #90) y las capas de Landsat, WorldCover y Open
  Buildings (#62, PR #93);
- los indicadores de la 88118, con la serie de ERA5 ficticia (#61, PR #91, `Refs #61`).

El plan está entero en órdenes (`gh issue list --label orden`): la #54 y la #56, de la
validación, y 25 más de la #57 a la #82, con la decisión #72 entre ellas. Cada una de las 25
dice su prioridad (P1, imprescindible para la entrega; P2, completa el plan; P3, si da tiempo),
qué necesita en `main` antes de empezar y, si las hay, qué órdenes esperan por ella.

## Siguiente paso

1. **La validación**: la orden #54 contrasta ERA5 con Santa Ana/El Palmar en la ancla, y la #56,
   con El Dorado y La Chinita en las réplicas. La #71 lleva la métrica a la ficha. Si el
   retador responde en la #39 que esos datos no se pueden usar, la métrica de Santa Ana se
   retira. Los rangos de `src/era5_checks.py` son de El Salvador: en las réplicas, un fallo solo
   en temperatura o en lluvia se anota en el PR y no detiene la orden (comentario en la #56),
   hasta que la #69 traiga los rangos por sede.

   **La #54 sigue abierta, a cargo de cesarp03.** Solo espera el geopotencial de Santa Ana
   (petición `9ea2bc4a-4cba-44c6-938e-2901a967af25`, en la cola del CDS). Cuando llegue, el PR
   que la cierra sale de la misma rama, `cesarp03/orden-54`, con los pasos de su comentario del
   28: la corrida con la carpeta real, los controles de la orden y `Closes #54`. Hasta entonces,
   las cifras de la ancla **con corrección por altura** son provisionales y no se citan como
   definitivas, tampoco en el formulario; las cifras sin corrección ya son definitivas.
2. **El contrato de datos y la construcción.** El contrato es la orden #58, y de él salen las
   de construcción, una por pantalla o flujo, ya escritas. La ruta crítica es #57 → #60 → #61 →
   #67 → #68 para la demo de la ancla, y #58 → #64 → #66 para el sitio. Al final van #80 → #81 →
   el envío final de la #82, y la #80 espera además a la #62, la #63 y la #69. Sin esperar a
   nada pueden empezar la #57, la #58, la #59, la etapa 1 de la #64 y el guion de la #81. Las
   tres primeras desbloquean casi todo lo demás: con la cola limitada a tres PR, conviene
   revisarlas en cuanto lleguen.

   **Bogotá no tiene capa de calor** (PR #93). Solo 2 escenas de Landsat pasan el filtro de
   nubes, y sus 441 cuadros van `sin_dato`. La orden #96 (P2) vuelve a extraerla con un umbral
   de `CLOUD_COVER` más alto solo en Bogotá; si no entra antes de congelar el código, se
   presenta sin esa capa y se declara como límite. La #66 tiene anotado en un comentario cómo
   tratar una escuela con todos los cuadros sin dato.

   **La #61 va con datos ficticios provisionales** (PR #91 y #94, `Refs #61`, decisión del
   equipo en la issue). La serie completa de ERA5 de la 88118 está pedida al CDS, pero todavía
   no se puede descargar, así que `web/datos/sv-88118/escuela.json` y `clima.json` llevan un
   campo `datos_ficticios`. La #64 (ficha), la #67 (recorrido) y la #73 (asistente) tienen
   pedido enseñarlo o propagarlo. La altura de la escuela ya es la real: con el relieve del #90,
   el #94 recalculó sin `--altitud`, y `z_escuela` pasó de 400 m ficticios a los 313,8 m de
   NASADEM. La serie y `z_celda` siguen siendo ficticias. Para cerrar la #61 falta:
   - la serie real, con `--comprobar` en verde, su recorte versionado en `recortes/sv-88118/era5/`
     y volver a calcular, sin `--recorte`;
   - revisar la lluvia: la descarga de prueba de 2025 da 573 mm en la celda y no pasa el
     control de `src/era5_checks.py` (de 1,0 a 3,5 m al año). Se mira con la serie completa y
     contra CHIRPS (#79);
   - una orden que recoja `datos_ficticios` en `docs/contrato-datos.md`, que la #61 no podía
     tocar.

   La serie ficticia solo existe en la máquina de cesarp03 y sale de
   `data/raw/era5/.parcial-prueba-88118-2025-20ndmhlw/`, que no se borra mientras haga falta.
3. **El asistente**: la #72 decide, antes del domingo 29 a las 04:00, si producción responde
   con el LLM o solo con respuestas de reserva, que es la propuesta. La orden #73 deja la
   reserva funcionando en cualquier caso, y su parte de producción espera a la #72.
4. **Lo que no viaja por git**, en cada máquina que descargue datos:
   - el `.venv`: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`;
   - una cuenta del Climate Data Store con la "CC-BY licence" aceptada en la pestaña
     "Download" de un dataset de ERA5 (es la misma para los dos que usa `src/era5.py`), y para
     la orden #54, las licencias que pida `insitu-observations-surface-land`;
   - `~/.cdsapirc`, con `url: https://cds.climate.copernicus.eu/api` y `key:` seguido del
     token del perfil, que no lleva dos puntos. Se escribe con un editor y permisos 600: ni con
     `echo`, que lo deja en el historial, ni pegado en el chat de un asistente;
   - para la #60, una cuenta gratuita de NASA Earthdata, con las credenciales en `~/.netrc`,
     escrito con los mismos cuidados;
   - para la #62, una cuenta de Google Earth Engine con un proyecto de Cloud registrado para uso
     no comercial. Ni la cuenta ni el proyecto se nombran en el repositorio.
5. **Con Codex o Devin**, la capa vale igual: leen `AGENTS.md` y las skills de
   `.agents/skills/`. Codex no puede negar lecturas desde el proyecto, así que a ningún asistente
   se le pide abrir `~/.cdsapirc`, `~/.netrc` ni `.env`. Devin en la nube no tiene esas
   credenciales ni las necesita: las pruebas no usan la red. Cada PR declara la herramienta y el
   modelo que usó.
6. **Cada integrante comprueba su clon** (`CONTRIBUTING.md`, "Comprobación del primer día").
7. **El último marcador pendiente del `CLAUDE.md`**, el comando de ejecución, lo resuelve la
   orden #80 con `python -m src.generar --todas --comprobar`.
8. **Lo que hace una persona y no una orden**:
   - buscar ya un docente para la sesión de 20 minutos de la #76, antes de congelar el código;
   - activar GitHub Pages con la fuente "GitHub Actions", que solo puede hacer quien administra
     el repositorio, para la #78;
   - el enlace del formulario, que da quien coordina, para la #82. El primer envío va con lo que
     esté publicado a las 20:00.

**Hitos** (hora de El Salvador): primer envío del formulario el sábado 28 a las 20:00, código
congelado el domingo 29 a las 8:00 y entrega a las 11:00.

## Decisiones vigentes

- **2026-11-27. El alcance del brief.** Un motor y tres escuelas: la 88118 de El Salvador como
  ancla, y Bogotá y Maracaibo como réplicas con datos globales (#15 y #16). Riesgos de calor y
  agua; los incendios de vegetación, como ampliación declarada fuera de la primera entrega. Un
  asistente con LLM que responde solo desde la ficha de la escuela. Accesibilidad WCAG 2.2 AA.
  La herramienta no se presenta como pronóstico ni como evaluación oficial de riesgo, y las
  rutas de evacuación que se comparan son hipotéticas, sobre una maqueta genérica.
- **2026-11-27. Las decisiones del plan viven en su sección 12.** Las de las issues #15 a #23 se
  integraron en `docs/PLAN.md`; si una issue y el plan discrepan, se corrige el plan por PR.
- **2026-11-27. Público desde el nacimiento, con `main` protegido.** Se hizo público después de
  auditar su historial entero: en un repositorio público, reescribir el historial no retira
  nada, porque GitHub sigue sirviendo los commits viejos por SHA. La protección exige una
  aprobación y el check `higiene`, y no permite push forzado ni borrado. Todo PR lo revisa
  alguien distinto de su autor.
- **2026-11-27. La capa de Claude Code se versiona.** `CLAUDE.md`, `BITACORA.md` y `.claude/`
  son del equipo, para que cada sesión arranque con las mismas reglas. Lo de cada uno
  (`CLAUDE.local.md`, `.claude/settings.local.json`) queda fuera por el `.gitignore`.
- **2026-11-27. Ni modelo ni atribución en la capa.** El `.claude/settings.json` del proyecto se
  impone al de cada uno: un modelo fijado ahí obligaría a todas las cuentas, así que cada uno lo
  elige con `/model`. La atribución va vacía y el uso de IA se declara en cada PR.
- **2026-11-27. Decisiones y órdenes, separadas.** Lo que falta decidir del plan va en issues
  con la etiqueta `decision`, y se cierra con un comentario que diga lo decidido. La
  implementación va en órdenes, con la etiqueta `orden`. La sección 12 del brief se pone al día
  en el PR de la bitácora.
- **2026-11-27. ERA5 por punto** (orden #4). La serie sale de
  `reanalysis-era5-single-levels-timeseries`, de 1940-01-01 a 2026-01-01 (orden #37): años
  completos, sin los meses preliminares de ERA5T, y el día que completa el último día local de
  2025 en las tres sedes. El recorte a las 06:00 UTC lo hace el contrato de datos. Se guarda tal
  como llega (UTC, K y m) en `data/raw/era5/<nombre>/`, con un `registro.json` de rutas
  relativas. La altura de la celda sale del geopotencial de `reanalysis-era5-single-levels`.
- **2026-11-28. Una orden que espera un dato externo entra por partes** (#54, PR #86). Si el
  código está listo y solo falta un dato, entra en `main` con `Refs #N` y el valor provisional
  marcado `datos_ficticios`, para no frenar a las órdenes que dependen de ella. El PR que cierra
  la orden sale de la misma rama cuando llega el dato.
- **2026-11-28. Las capas de Earth Engine se aceptan con dos límites** (PR #93, revisión de
  cesarp03). Bogotá queda `sin_dato` en `calor.geojson` hasta la #96. Y el control del 2 % del
  área de un edificio se hace con el contorno del recorte, no con el de `edificios.geojson`:
  el redondeo a 6 decimales del contrato mueve hasta un 5 % el área de las huellas pequeñas.
- **2026-11-28. La validación publica la métrica, no la serie** (#46 y #39). Las series de las
  estaciones se bajan a `data/raw/`, y en el repositorio entran el script que las baja y el
  `metrics.json` del experimento, con la cita de la estación. En la ancla, Santa Ana/El Palmar
  se contrasta hora a hora de 07:00 a 17:00 hora local, porque solo tiene datos de día; las
  máximas y mínimas diarias se validan solo en las réplicas.
