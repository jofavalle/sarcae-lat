# Bitácora de sarcae-lat

Estado del proyecto entre sesiones, para todo el equipo. Se versiona y la escribe quien
coordina, por PR como todo lo demás. El estado de cada tarea no va aquí: vive en las issues y
en sus PR. **Se mantiene corta a propósito**: lo que deje de estar vigente se borra, no se
acumula.

## Estado actual

**2026-11-28, 00:45 (hora de El Salvador).** El repositorio nació el 27 para el reto 10 de
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
pregunta de la #39 al retador sobre esa licencia sigue sin respuesta. Sigue abierta la decisión
del proveedor del asistente para el público escolar (ADR-002). Todavía no hay datos
versionados: antes hace falta el contrato de datos.

## Siguiente paso

1. **La validación**: la orden #54 contrasta ERA5 con Santa Ana/El Palmar en la ancla, y su
   función de emparejado y métricas la reusa la orden de las réplicas, que falta escribir con
   lo decidido en la #46. Si el retador responde en la #39 que esos datos no se pueden usar, la
   métrica de Santa Ana se retira.
2. **El contrato de datos de la 88118**, con los indicadores de la #22. Antes de bajar la serie
   de las tres escuelas, una descarga de prueba contra el CDS con `src/era5.py` de `main`, que
   la revisión de la #37 no hizo: del 2025-01-01 al 2026-01-01 en una carpeta nueva, con 8784
   filas y todos los controles en verde. Del contrato salen las órdenes de construcción, una
   por pantalla o flujo.
3. **El asistente**: decidir el proveedor para el público escolar con la ADR-002, que dejó la
   prueba técnica completada con 16 de 24 respuestas conformes.
4. **Lo que no viaja por git**, en cada máquina que descargue datos:
   - el `.venv`: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`;
   - una cuenta del Climate Data Store con la "CC-BY licence" aceptada en la pestaña
     "Download" de un dataset de ERA5 (es la misma para los dos que usa `src/era5.py`), y para
     la orden #54, las licencias que pida `insitu-observations-surface-land`;
   - `~/.cdsapirc`, con `url: https://cds.climate.copernicus.eu/api` y `key:` seguido del
     token del perfil, que no lleva dos puntos. Se escribe con un editor y permisos 600: ni con
     `echo`, que lo deja en el historial, ni pegado en el chat de un asistente.
5. **Con Codex o Devin**, la capa vale igual: leen `AGENTS.md` y las skills de
   `.agents/skills/`. Codex no puede negar lecturas desde el proyecto, así que a ningún asistente
   se le pide abrir `~/.cdsapirc` ni `.env`. Devin en la nube no tiene esas credenciales ni las
   necesita: las pruebas no usan la red. Cada PR declara la herramienta y el modelo que usó.
6. **Cada integrante comprueba su clon** (`CONTRIBUTING.md`, "Comprobación del primer día").
7. **El último marcador pendiente del `CLAUDE.md`**, el comando de ejecución, se resuelve
   cuando exista el comando que genera la ficha.

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
- **2026-11-28. La validación publica la métrica, no la serie** (#46 y #39). Las series de las
  estaciones se bajan a `data/raw/`, y en el repositorio entran el script que las baja y el
  `metrics.json` del experimento, con la cita de la estación. En la ancla, Santa Ana/El Palmar
  se contrasta hora a hora de 07:00 a 17:00 hora local, porque solo tiene datos de día; las
  máximas y mínimas diarias se validan solo en las réplicas.
