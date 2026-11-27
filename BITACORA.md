# Bitácora de sarcae-lat

Estado del proyecto entre sesiones, para todo el equipo. Se versiona y la escribe quien
coordina, por PR como todo lo demás. El estado de cada tarea no va aquí: vive en las issues y
en sus PR. **Se mantiene corta a propósito**: lo que deje de estar vigente se borra, no se
acumula.

## Estado actual

**2026-11-27, 16:40 (hora de El Salvador).** El repositorio nació el 27 para el reto 10 de
CoAfina 2026. Es público y protege `main`: cada PR necesita una aprobación y el check `higiene`
en verde. jofavalle, aalexanderrz, cesarp03 y bm20004 tienen permiso de escritura.

En `main`:
- el brief, `docs/PLAN.md`, y la ficha del Manual de Diseño Mi Nueva Escuela (PR #1 y #2);
- la ADR-001 del front (orden #5, PR #7): HTML, CSS y JavaScript sin framework, MapLibre GL JS
  para el mapa y la maqueta, y mapa base sin OpenStreetMap;
- las licencias de las fuentes, comprobadas y citadas en el README, y el modelo de elevación
  elegido, NASADEM (orden #6, PR #8);
- la descarga de ERA5 por punto, `src/era5.py` (orden #4, PR #14). Probada con el aeropuerto
  de Ilopango, la serie de 1940 a 2025 tardó 122 s y pasó todos los controles.

Las decisiones que el plan dejaba abiertas son ahora issues con la etiqueta `decision`, de la
#15 a la #23. Todavía no hay datos versionados ni front.

## Siguiente paso

1. **La escuela ancla, #15**, hoy por la noche. El contrato de datos, la dirección visual y la
   ficha esperan por ella. No se nombra en el repositorio hasta confirmarla.
2. **Las preguntas al canal del reto, #17**, en el canal público y no por privado.
3. **Con la escuela ancla**: cerrar #21 (dónde se versionan los recortes) y #22 (indicadores),
   bajar su serie con `python -m src.era5`, y escribir el contrato de datos. De ahí salen las
   órdenes de construcción, una por pantalla o flujo. Las referencias visuales de #20 se
   pueden aportar ya.
4. **Lo que no viaja por git**, en cada máquina que descargue datos:
   - el `.venv`: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`;
   - una cuenta del Climate Data Store con la "CC-BY licence" aceptada en la pestaña
     "Download" de un dataset de ERA5 (es la misma para los dos que usa `src/era5.py`);
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

- **2026-11-27. El alcance del brief.** Un motor y tres escuelas: El Salvador como ancla, y
  Colombia y Venezuela como réplicas con datos globales. Riesgos de calor y agua. Un asistente
  con LLM que responde solo desde la ficha de la escuela. Accesibilidad WCAG 2.2 AA. La
  herramienta no se presenta como pronóstico ni como evaluación oficial de riesgo.
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
  `reanalysis-era5-single-levels-timeseries`, de 1940-01-01 a 2025-12-31: años completos, sin
  los meses preliminares de ERA5T. Se guarda tal como llega (UTC, K y m) en
  `data/raw/era5/<nombre>/`, con un `registro.json` de rutas relativas. La altura de la celda
  sale del geopotencial de `reanalysis-era5-single-levels`.
