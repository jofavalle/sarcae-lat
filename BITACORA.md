# Bitácora de sarcae-lat

Estado del proyecto entre sesiones, para todo el equipo. Se versiona y la escribe quien
coordina, por PR como todo lo demás. El estado de cada tarea no va aquí: vive en las issues y
en sus PR. **Se mantiene corta a propósito**: lo que deje de estar vigente se borra, no se
acumula.

## Estado actual

**2026-11-27, 14:20 (hora de El Salvador).** El repositorio nació el 27 para el reto 10 de
CoAfina 2026. Es público y protege `main`: cada PR necesita una aprobación y el check `higiene`
en verde. jofavalle, aalexanderrz, cesarp03 y bm20004 tienen permiso de escritura.

En `main`, desde los PR #1 y #2, que revisó y fusionó cesarp03:
- el brief del proyecto, `docs/PLAN.md`, con diez decisiones abiertas en su sección 12;
- las convenciones y trampas propias del `CLAUDE.md`;
- la ficha de referencia del Manual de Diseño Mi Nueva Escuela,
  `docs/refs/manual-mi-nueva-escuela.md`.

Todavía no hay código ni datos. El aviso `main por PR` salió en verde en las dos fusiones: la X
del commit inicial fue solo la del primer push.

## Siguiente paso

1. **Cerrar las decisiones abiertas del brief** (sección 12 de `docs/PLAN.md`). Las primeras son
   la escuela ancla en El Salvador, que no se nombra en el repositorio hasta confirmarla, las
   escuelas de Colombia y Venezuela, y el stack del front, que se decide en una ADR en
   `docs/decisiones/`.
2. **Preguntar en el canal del reto**, nunca por privado: si ERA5-Land cuenta como "datos de
   ERA5", si los criterios tienen pesos y si el retador estará en el jurado.
3. **Cuentas de datos:** quien descargue necesita una cuenta del Climate Data Store con la
   licencia de ERA5 aceptada, y un proyecto de Google Earth Engine registrado como no comercial.
   Las claves van en `.env` o en `~/.cdsapirc`, nunca en el repositorio.
4. **El contrato de datos** (el esquema de los JSON que lee el front) **y las dos direcciones
   visuales**, con datos reales de la escuela ancla. De ahí salen las órdenes de construcción,
   una por pantalla o flujo.
5. **Cada integrante comprueba su clon:** activa los ganchos con
   `git config core.hooksPath .githooks`, abre `claude` en la raíz, mira con `/memory` que carga
   este `CLAUDE.md` y con `/tomar-orden` que las skills están, y ejecuta
   `python3 .github/higiene.py`, que tiene que pasar en su máquina.
6. **El último marcador pendiente del `CLAUDE.md`**, el comando de ejecución, se resuelve
   cuando exista ese comando.

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
