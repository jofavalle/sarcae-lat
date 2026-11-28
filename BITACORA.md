# Bitácora de sarcae-lat

Estado del proyecto entre sesiones, para todo el equipo. Se versiona y la escribe quien
coordina, por PR como todo lo demás. El estado de cada tarea no va aquí: vive en las issues y
en sus PR. **Se mantiene corta a propósito**: lo que deje de estar vigente se borra, no se
acumula.

## Estado actual

**2026-11-27, 22:50 (hora de El Salvador).** El repositorio nació el 27 para el reto 10 de
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
- los recortes en `recortes/<escuela>/<fuente>/`, con su manifiesto (decisión #21, PR #34).

Las decisiones de las issues #15 a #23 están integradas en `docs/PLAN.md`, y su sección 12 es la
tabla vigente. Las escuelas son la 88118 en El Salvador (ancla), el Nicolás Esguerra en Bogotá y
el Rafael María Baralt en Maracaibo. El canal del reto respondió a la #17: ERA5-Land se admite,
y los criterios pesan casi lo mismo, con la usabilidad y la creatividad como lo que decide.
Quedan abiertos la prueba del proveedor del LLM (orden #38), la estación de la escuela ancla
(orden #39) y la decisión #46. La #46 decide cómo validar ERA5 en las réplicas, porque la #9
no pudo confirmar que las series de GHCNh de El Dorado y La Chinita se puedan redistribuir.
Todavía no hay datos versionados: antes hace falta el contrato de datos.

## Siguiente paso

1. **Revisar el PR #45**, las teselas de relieve de NASADEM (orden #11).
2. **El contrato de datos de la 88118**, con los indicadores de la #22. Antes de bajar la serie
   de las tres escuelas, una descarga de prueba contra el CDS con `src/era5.py` de `main`, que
   la revisión de la #37 no hizo: del 2025-01-01 al 2026-01-01 en una carpeta nueva, con 8784
   filas y todos los controles en verde. Del contrato salen las órdenes de construcción, una
   por pantalla o flujo.
3. **El asistente**: la orden #38 prueba Workers AI con Mistral Small 3.1 desde Pages Functions
   con una ficha de prueba, pasa la batería de la #12 y escribe la ADR-002.
4. **La validación**: la orden #39 pide al MARN la serie diaria de Nueva Concepción y sus
   condiciones de uso, y la decisión #46 dice cómo se valida en las réplicas.
5. **Lo que no viaja por git**, en cada máquina que descargue datos:
   - el `.venv`: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`;
   - una cuenta del Climate Data Store con la "CC-BY licence" aceptada en la pestaña
     "Download" de un dataset de ERA5 (es la misma para los dos que usa `src/era5.py`);
   - `~/.cdsapirc`, con `url: https://cds.climate.copernicus.eu/api` y `key:` seguido del
     token del perfil, que no lleva dos puntos. Se escribe con un editor y permisos 600: ni con
     `echo`, que lo deja en el historial, ni pegado en el chat de un asistente.
6. **Con Codex o Devin**, la capa vale igual: leen `AGENTS.md` y las skills de
   `.agents/skills/`. Codex no puede negar lecturas desde el proyecto, así que a ningún asistente
   se le pide abrir `~/.cdsapirc` ni `.env`. Devin en la nube no tiene esas credenciales ni las
   necesita: las pruebas no usan la red. Cada PR declara la herramienta y el modelo que usó.
7. **Cada integrante comprueba su clon** (`CONTRIBUTING.md`, "Comprobación del primer día").
8. **El último marcador pendiente del `CLAUDE.md`**, el comando de ejecución, se resuelve
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
